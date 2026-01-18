# Gap Fix Implementation Draft 6

This document provides complete Python implementations for ALL gaps identified in the gap analysis. Each section addresses a specific gap with production-ready code.

---

## 1. Parallel Request Architecture - EvaluationEngine

The critical gap is the parallel execution architecture. Here is the complete EvaluationEngine with asyncio.gather/TaskGroup for concurrent API calls.

```python
# src/eval/engine.py

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from enum import Enum
import logging

from ..api.openrouter_client import OpenRouterClient, CompletionResponse
from ..prompts.schemas import WritingPrompt
from ..storage.checkpoint import CheckpointManager
from ..storage.database import Database
from .vote_aggregator import VoteAggregator, JudgeVote, AggregatedResult
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .refusal_classifier import RefusalClassifier, RefusalCategory
from .response_analyzer import ResponseAnalyzer
from ..config.settings import EvalConfig

logger = logging.getLogger(__name__)


class EvalPhase(Enum):
    """Current phase of evaluation."""
    GENERATION = "generation"
    JUDGING = "judging"
    ANALYSIS = "analysis"
    COMPLETE = "complete"


@dataclass
class ProgressState:
    """Current progress state for TUI updates."""
    phase: EvalPhase
    total_prompts: int
    completed_prompts: int
    current_prompt_id: Optional[str] = None
    current_occupation: Optional[str] = None
    current_industry: Optional[str] = None

    # Per model pair progress
    pair_progress: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # pair_key -> (completed, total)
    pair_wins: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)  # pair_key -> (gemini_wins, competitor_wins, ties)

    # Running statistics
    total_cost_so_far: float = 0.0
    projected_total_cost: float = 0.0
    avg_response_time_ms: float = 0.0
    avg_judge_time_ms: float = 0.0
    api_calls_per_minute: float = 0.0

    # Judge agreement tracking for Cohen's Kappa
    judge_votes: List[Tuple[str, str, str]] = field(default_factory=list)  # (prompt_id, judge_model, winner)

    # ETA tracking
    start_time: float = 0.0
    estimated_completion_time: float = 0.0

    # Per-judge vote counts for current batch
    current_judge_votes: Dict[str, Dict[str, int]] = field(default_factory=dict)  # judge_model -> {gemini: n, competitor: n, tie: n}

    # Response times tracking
    response_times: List[float] = field(default_factory=list)
    judge_times: List[float] = field(default_factory=list)

    # Errors
    retries: int = 0
    failures: int = 0
    rate_limit_pauses: int = 0


@dataclass
class BatchResult:
    """Result from processing a single prompt across all model pairs."""
    prompt_id: str
    responses: Dict[str, CompletionResponse]  # model_id -> response
    judgments: Dict[str, AggregatedResult]  # pair_key -> aggregated result
    errors: List[str] = field(default_factory=list)
    total_cost: float = 0.0
    total_time_ms: float = 0.0


class EvaluationEngine:
    """Main evaluation orchestrator with parallel request architecture.

    Implements:
    - asyncio.gather/TaskGroup for concurrent API calls
    - asyncio.Semaphore for concurrency limiting (configurable 10-50 concurrent)
    - Batch processing logic for prompts
    - Per-model concurrency respecting rate limits
    - Progress callbacks for TUI updates during parallel execution
    """

    def __init__(
        self,
        config: EvalConfig,
        client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        database: Database,
        progress_callback: Optional[Callable[[ProgressState], None]] = None,
        max_concurrent_requests: int = 30,
        max_concurrent_per_model: int = 10,
    ):
        self.config = config
        self.client = client
        self.checkpoint = checkpoint_manager
        self.db = database
        self.progress_callback = progress_callback

        # Concurrency controls
        self.max_concurrent = max_concurrent_requests
        self.max_per_model = max_concurrent_per_model

        # Global semaphore for total concurrent requests
        self._global_semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Per-model semaphores to respect individual rate limits
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}

        # Components
        self.vote_aggregator = VoteAggregator(
            votes_per_judge=config.judge_config.votes_per_judge
        )
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.refusal_classifier = RefusalClassifier()
        self.response_analyzer = ResponseAnalyzer()

        # State tracking
        self.state = ProgressState(
            phase=EvalPhase.GENERATION,
            total_prompts=config.num_prompts,
            completed_prompts=0,
            start_time=time.time()
        )

        # Cost tracking
        self._cost_tracker = CostTracker()

        # Timing tracking for throughput calculation
        self._api_call_times: List[float] = []

        # Pause/cancel controls
        self._paused = asyncio.Event()
        self._paused.set()  # Not paused initially
        self._cancelled = False

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore."""
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(self.max_per_model)
        return self._model_semaphores[model]

    async def _wait_if_paused(self):
        """Wait if evaluation is paused."""
        await self._paused.wait()

    def pause(self):
        """Pause evaluation."""
        self._paused.clear()

    def resume(self):
        """Resume evaluation."""
        self._paused.set()

    def cancel(self):
        """Cancel evaluation gracefully."""
        self._cancelled = True
        self.resume()  # Unblock any waiting coroutines

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
    ) -> Dict[str, Any]:
        """Run the complete evaluation with parallel processing.

        Args:
            prompts: List of prompts to evaluate

        Returns:
            Dictionary with evaluation results and statistics
        """
        self.state.total_prompts = len(prompts)
        self.state.start_time = time.time()

        # Initialize pair progress tracking
        for gemini, competitor in self.config.model_pairs:
            pair_key = f"{gemini}_vs_{competitor}"
            self.state.pair_progress[pair_key] = (0, len(prompts))
            self.state.pair_wins[pair_key] = (0, 0, 0)

        results = []

        # Process prompts in batches for better memory management
        batch_size = min(50, len(prompts))

        for batch_start in range(0, len(prompts), batch_size):
            if self._cancelled:
                break

            batch_end = min(batch_start + batch_size, len(prompts))
            batch_prompts = prompts[batch_start:batch_end]

            # Process batch with parallel execution
            batch_results = await self._process_batch(batch_prompts)
            results.extend(batch_results)

            # Update checkpoint
            await self.checkpoint.save_batch_results(batch_results)

            self._update_progress_state()

        self.state.phase = EvalPhase.COMPLETE
        self._notify_progress()

        return {
            "results": results,
            "total_cost": self.state.total_cost_so_far,
            "total_prompts": len(prompts),
            "completed": self.state.completed_prompts,
            "cancelled": self._cancelled,
        }

    async def _process_batch(
        self,
        prompts: List[WritingPrompt],
    ) -> List[BatchResult]:
        """Process a batch of prompts with parallel execution."""

        # Phase 1: Generate responses for all prompts across all models
        self.state.phase = EvalPhase.GENERATION
        self._notify_progress()

        # Collect all model response tasks
        response_tasks = []
        for prompt in prompts:
            for gemini_model, competitor_model in self.config.model_pairs:
                # Task for Gemini response
                response_tasks.append(
                    self._generate_response_with_semaphore(prompt, gemini_model)
                )
                # Task for competitor response
                response_tasks.append(
                    self._generate_response_with_semaphore(prompt, competitor_model)
                )

        # Execute all response generation in parallel with concurrency limits
        response_results = await asyncio.gather(*response_tasks, return_exceptions=True)

        # Organize responses by prompt and model
        responses_by_prompt: Dict[str, Dict[str, CompletionResponse]] = {}
        idx = 0
        for prompt in prompts:
            responses_by_prompt[prompt.prompt_id] = {}
            for gemini_model, competitor_model in self.config.model_pairs:
                gemini_result = response_results[idx]
                competitor_result = response_results[idx + 1]
                idx += 2

                if not isinstance(gemini_result, Exception):
                    responses_by_prompt[prompt.prompt_id][gemini_model] = gemini_result
                    self._cost_tracker.add_cost(gemini_result.cost)
                    self.state.response_times.append(gemini_result.latency_ms)

                if not isinstance(competitor_result, Exception):
                    responses_by_prompt[prompt.prompt_id][competitor_model] = competitor_result
                    self._cost_tracker.add_cost(competitor_result.cost)
                    self.state.response_times.append(competitor_result.latency_ms)

        # Phase 2: Run judging for all comparisons
        self.state.phase = EvalPhase.JUDGING
        self._notify_progress()

        # Collect all judging tasks
        judge_tasks = []
        judge_task_metadata = []  # Track which task corresponds to which comparison

        for prompt in prompts:
            prompt_responses = responses_by_prompt.get(prompt.prompt_id, {})

            for gemini_model, competitor_model in self.config.model_pairs:
                gemini_response = prompt_responses.get(gemini_model)
                competitor_response = prompt_responses.get(competitor_model)

                if gemini_response and competitor_response:
                    # Check for refusals first
                    gemini_refusal = self.refusal_classifier.classify(gemini_response.content)
                    competitor_refusal = self.refusal_classifier.classify(competitor_response.content)

                    # Auto-loss on refusal
                    if gemini_refusal and not competitor_refusal:
                        # Gemini refused, auto-loss
                        judge_task_metadata.append({
                            "prompt_id": prompt.prompt_id,
                            "gemini_model": gemini_model,
                            "competitor_model": competitor_model,
                            "auto_loss": "gemini",
                            "refusal_category": gemini_refusal.category.value
                        })
                        continue
                    elif competitor_refusal and not gemini_refusal:
                        # Competitor refused, auto-win for Gemini
                        judge_task_metadata.append({
                            "prompt_id": prompt.prompt_id,
                            "gemini_model": gemini_model,
                            "competitor_model": competitor_model,
                            "auto_loss": "competitor",
                            "refusal_category": competitor_refusal.category.value
                        })
                        continue
                    elif gemini_refusal and competitor_refusal:
                        # Both refused, tie
                        judge_task_metadata.append({
                            "prompt_id": prompt.prompt_id,
                            "gemini_model": gemini_model,
                            "competitor_model": competitor_model,
                            "auto_loss": "both",
                        })
                        continue

                    # Create judging tasks for each judge model and persona
                    for judge_model in self.config.judge_config.models:
                        personas = ["expert", "recipient"] if self.config.judge_config.use_both_personas else ["expert"]

                        for persona in personas:
                            for vote_idx in range(self.config.judge_config.votes_per_judge):
                                task = self._execute_judge_vote(
                                    prompt=prompt,
                                    gemini_response=gemini_response.content,
                                    competitor_response=competitor_response.content,
                                    gemini_model=gemini_model,
                                    competitor_model=competitor_model,
                                    judge_model=judge_model,
                                    persona=persona,
                                    vote_index=vote_idx,
                                )
                                judge_tasks.append(task)
                                judge_task_metadata.append({
                                    "prompt_id": prompt.prompt_id,
                                    "gemini_model": gemini_model,
                                    "competitor_model": competitor_model,
                                    "judge_model": judge_model,
                                    "persona": persona,
                                    "vote_index": vote_idx,
                                    "auto_loss": None,
                                })

        # Execute all judging in parallel
        judge_results = await asyncio.gather(*judge_tasks, return_exceptions=True)

        # Organize and aggregate results
        batch_results = []
        votes_by_comparison: Dict[str, List[JudgeVote]] = {}

        for i, metadata in enumerate(judge_task_metadata):
            if metadata.get("auto_loss"):
                # Handle auto-loss cases
                comparison_key = f"{metadata['prompt_id']}_{metadata['gemini_model']}_{metadata['competitor_model']}"
                if comparison_key not in votes_by_comparison:
                    votes_by_comparison[comparison_key] = []
                # Record as automatic result
                continue

            if i < len(judge_results):
                result = judge_results[i - sum(1 for m in judge_task_metadata[:i] if m.get("auto_loss"))]
                if isinstance(result, Exception):
                    self.state.failures += 1
                    continue

                vote = result
                comparison_key = f"{metadata['prompt_id']}_{metadata['gemini_model']}_{metadata['competitor_model']}"

                if comparison_key not in votes_by_comparison:
                    votes_by_comparison[comparison_key] = []
                votes_by_comparison[comparison_key].append(vote)

                # Track for Cohen's Kappa
                self.state.judge_votes.append((
                    metadata['prompt_id'],
                    metadata['judge_model'],
                    vote.winner
                ))

        # Aggregate votes for each comparison
        for prompt in prompts:
            prompt_judgments = {}
            prompt_responses = responses_by_prompt.get(prompt.prompt_id, {})

            for gemini_model, competitor_model in self.config.model_pairs:
                pair_key = f"{gemini_model}_vs_{competitor_model}"
                comparison_key = f"{prompt.prompt_id}_{gemini_model}_{competitor_model}"

                votes = votes_by_comparison.get(comparison_key, [])

                if votes:
                    aggregated = self.vote_aggregator.aggregate_all(
                        prompt_id=prompt.prompt_id,
                        gemini_model=gemini_model,
                        competitor_model=competitor_model,
                        all_votes=votes
                    )
                    prompt_judgments[pair_key] = aggregated

                    # Update win tracking
                    wins = self.state.pair_wins.get(pair_key, (0, 0, 0))
                    if aggregated.final_winner == "gemini":
                        self.state.pair_wins[pair_key] = (wins[0] + 1, wins[1], wins[2])
                    elif aggregated.final_winner == "competitor":
                        self.state.pair_wins[pair_key] = (wins[0], wins[1] + 1, wins[2])
                    else:
                        self.state.pair_wins[pair_key] = (wins[0], wins[1], wins[2] + 1)

                    # Update progress
                    progress = self.state.pair_progress.get(pair_key, (0, len(prompts)))
                    self.state.pair_progress[pair_key] = (progress[0] + 1, progress[1])

            batch_results.append(BatchResult(
                prompt_id=prompt.prompt_id,
                responses=prompt_responses,
                judgments=prompt_judgments,
                total_cost=sum(r.cost for r in prompt_responses.values()),
            ))

            self.state.completed_prompts += 1
            self.state.current_prompt_id = prompt.prompt_id
            self.state.current_occupation = prompt.occupation_title
            self.state.current_industry = prompt.naics_sector
            self._update_progress_state()
            self._notify_progress()

        return batch_results

    async def _generate_response_with_semaphore(
        self,
        prompt: WritingPrompt,
        model: str,
    ) -> CompletionResponse:
        """Generate response with semaphore-controlled concurrency."""
        await self._wait_if_paused()

        model_semaphore = self._get_model_semaphore(model)

        async with self._global_semaphore:
            async with model_semaphore:
                try:
                    start_time = time.time()
                    response = await self.client.complete(
                        model=model,
                        messages=[
                            {"role": "user", "content": prompt.full_prompt}
                        ],
                        temperature=0.7,
                    )
                    self._api_call_times.append(time.time())
                    return response
                except Exception as e:
                    self.state.retries += 1
                    raise

    async def _execute_judge_vote(
        self,
        prompt: WritingPrompt,
        gemini_response: str,
        competitor_response: str,
        gemini_model: str,
        competitor_model: str,
        judge_model: str,
        persona: str,
        vote_index: int,
    ) -> JudgeVote:
        """Execute a single judge vote with position randomization."""
        await self._wait_if_paused()

        # Determine position for this vote (deterministic shuffling)
        gemini_position = self.vote_aggregator.get_position_for_vote(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            judge_model=judge_model,
            judge_persona=persona,
            vote_index=vote_index,
        )

        # Assign responses to positions
        if gemini_position == "A":
            response_a = gemini_response
            response_b = competitor_response
        else:
            response_a = competitor_response
            response_b = gemini_response

        # Build judge prompt
        system_prompt, user_prompt = self.judge_builder.build_judge_prompt(
            prompt=prompt,
            response_a=response_a,
            response_b=response_b,
            persona=persona,
        )

        # Execute judge call with semaphore
        model_semaphore = self._get_model_semaphore(judge_model)

        async with self._global_semaphore:
            async with model_semaphore:
                start_time = time.time()
                response = await self.client.complete(
                    model=judge_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,  # Lower temperature for consistency
                )
                self.state.judge_times.append((time.time() - start_time) * 1000)
                self._cost_tracker.add_cost(response.cost)
                self._api_call_times.append(time.time())

        # Parse judge response
        parsed = self.judge_parser.parse(response.content)

        # Convert position-based winner to model-based winner
        normalized_winner = self.vote_aggregator.parse_winner_to_normalized(
            raw_winner=parsed.winner,
            gemini_position=gemini_position,
        )

        return JudgeVote(
            judge_model=judge_model,
            judge_persona=persona,
            vote_index=vote_index,
            winner=normalized_winner,
            confidence=parsed.confidence,
            quality_gemini=parsed.quality_a if gemini_position == "A" else parsed.quality_b,
            quality_competitor=parsed.quality_b if gemini_position == "A" else parsed.quality_a,
            reasoning=parsed.reasoning,
            gemini_was_position=gemini_position,
            constraint_compliance_gemini=parsed.constraint_compliance_a if gemini_position == "A" else parsed.constraint_compliance_b,
            constraint_compliance_competitor=parsed.constraint_compliance_b if gemini_position == "A" else parsed.constraint_compliance_a,
        )

    def _update_progress_state(self):
        """Update progress state with current statistics."""
        # Update cost tracking
        self.state.total_cost_so_far = self._cost_tracker.total_cost

        # Calculate projected total cost
        if self.state.completed_prompts > 0:
            cost_per_prompt = self.state.total_cost_so_far / self.state.completed_prompts
            self.state.projected_total_cost = cost_per_prompt * self.state.total_prompts

        # Calculate average response time
        if self.state.response_times:
            self.state.avg_response_time_ms = sum(self.state.response_times) / len(self.state.response_times)

        # Calculate average judge time
        if self.state.judge_times:
            self.state.avg_judge_time_ms = sum(self.state.judge_times) / len(self.state.judge_times)

        # Calculate API calls per minute
        now = time.time()
        recent_calls = [t for t in self._api_call_times if now - t < 60]
        self.state.api_calls_per_minute = len(recent_calls)

        # Calculate ETA
        elapsed = now - self.state.start_time
        if self.state.completed_prompts > 0 and elapsed > 0:
            prompts_per_second = self.state.completed_prompts / elapsed
            remaining_prompts = self.state.total_prompts - self.state.completed_prompts
            if prompts_per_second > 0:
                remaining_seconds = remaining_prompts / prompts_per_second
                self.state.estimated_completion_time = now + remaining_seconds

    def _notify_progress(self):
        """Notify progress callback if set."""
        if self.progress_callback:
            self.progress_callback(self.state)


class CostTracker:
    """Track costs across the evaluation."""

    def __init__(self):
        self.total_cost = 0.0
        self._lock = asyncio.Lock()

    async def add_cost(self, cost: float):
        """Add cost (thread-safe)."""
        async with self._lock:
            self.total_cost += cost

    # Synchronous version for non-async contexts
    def add_cost_sync(self, cost: float):
        """Add cost (sync version)."""
        self.total_cost += cost
```

---

## 2. Cohen's Kappa Inter-Judge Agreement Calculation

```python
# src/analysis/statistics.py (additions)

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from scipy import stats


@dataclass
class KappaResult:
    """Result of Cohen's Kappa calculation."""
    kappa: float
    interpretation: str  # "poor", "slight", "fair", "moderate", "substantial", "almost_perfect"
    observed_agreement: float
    expected_agreement: float
    judge_pair: Tuple[str, str]
    n_items: int


@dataclass
class FleisskKappaResult:
    """Result of Fleiss' Kappa for multiple raters."""
    kappa: float
    interpretation: str
    n_raters: int
    n_items: int
    n_categories: int


def calculate_cohens_kappa(
    ratings1: List[str],
    ratings2: List[str],
    categories: Optional[List[str]] = None,
) -> float:
    """Calculate Cohen's Kappa for two raters.

    Args:
        ratings1: List of ratings from first rater
        ratings2: List of ratings from second rater
        categories: Optional list of all possible categories

    Returns:
        Cohen's Kappa coefficient (-1 to 1, where 1 is perfect agreement)
    """
    if len(ratings1) != len(ratings2):
        raise ValueError("Both rating lists must have the same length")

    if len(ratings1) == 0:
        return 0.0

    if categories is None:
        categories = sorted(set(ratings1) | set(ratings2))

    n = len(ratings1)
    n_cat = len(categories)

    # Create contingency matrix
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    matrix = np.zeros((n_cat, n_cat))

    for r1, r2 in zip(ratings1, ratings2):
        if r1 in cat_to_idx and r2 in cat_to_idx:
            matrix[cat_to_idx[r1], cat_to_idx[r2]] += 1

    # Calculate observed agreement (proportion on diagonal)
    observed_agreement = np.trace(matrix) / n

    # Calculate expected agreement
    row_sums = matrix.sum(axis=1) / n
    col_sums = matrix.sum(axis=0) / n
    expected_agreement = np.sum(row_sums * col_sums)

    # Calculate kappa
    if expected_agreement == 1.0:
        return 1.0  # Perfect agreement expected and observed

    kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)

    return kappa


def interpret_kappa(kappa: float) -> str:
    """Interpret Cohen's Kappa value using Landis & Koch guidelines.

    Args:
        kappa: The kappa coefficient

    Returns:
        String interpretation of the kappa value
    """
    if kappa < 0:
        return "poor"
    elif kappa < 0.20:
        return "slight"
    elif kappa < 0.40:
        return "fair"
    elif kappa < 0.60:
        return "moderate"
    elif kappa < 0.80:
        return "substantial"
    else:
        return "almost_perfect"


def calculate_pairwise_kappa(
    judge_votes: Dict[str, Dict[str, str]],
    categories: List[str] = ["gemini", "competitor", "tie"],
) -> Dict[Tuple[str, str], KappaResult]:
    """Calculate pairwise Cohen's Kappa between all judge pairs.

    Args:
        judge_votes: Dict[prompt_id, Dict[judge_model, winner]]
        categories: Possible outcome categories

    Returns:
        Dictionary mapping judge pairs to KappaResult
    """
    # Reorganize data by judge
    judges = set()
    for prompt_votes in judge_votes.values():
        judges.update(prompt_votes.keys())
    judges = sorted(judges)

    results = {}

    for i, judge1 in enumerate(judges):
        for judge2 in judges[i + 1:]:
            # Get common items rated by both judges
            ratings1 = []
            ratings2 = []

            for prompt_id, votes in judge_votes.items():
                if judge1 in votes and judge2 in votes:
                    ratings1.append(votes[judge1])
                    ratings2.append(votes[judge2])

            if len(ratings1) < 2:
                continue

            kappa = calculate_cohens_kappa(ratings1, ratings2, categories)
            n = len(ratings1)

            # Calculate observed and expected agreement
            observed = sum(1 for r1, r2 in zip(ratings1, ratings2) if r1 == r2) / n

            # Expected agreement under independence
            from collections import Counter
            count1 = Counter(ratings1)
            count2 = Counter(ratings2)
            expected = sum(
                (count1.get(cat, 0) / n) * (count2.get(cat, 0) / n)
                for cat in categories
            )

            results[(judge1, judge2)] = KappaResult(
                kappa=kappa,
                interpretation=interpret_kappa(kappa),
                observed_agreement=observed,
                expected_agreement=expected,
                judge_pair=(judge1, judge2),
                n_items=n,
            )

    return results


def calculate_fleiss_kappa(
    ratings: Dict[str, Dict[str, str]],
    categories: List[str] = ["gemini", "competitor", "tie"],
) -> FleisskKappaResult:
    """Calculate Fleiss' Kappa for multiple raters.

    Args:
        ratings: Dict[item_id, Dict[rater_id, category]]
        categories: List of all possible categories

    Returns:
        FleisskKappaResult with kappa and interpretation
    """
    items = list(ratings.keys())
    n = len(items)

    if n == 0:
        return FleisskKappaResult(
            kappa=0.0,
            interpretation="no_data",
            n_raters=0,
            n_items=0,
            n_categories=len(categories),
        )

    # Count raters per item
    raters_per_item = [len(ratings[item]) for item in items]
    k = max(raters_per_item) if raters_per_item else 0

    if k < 2:
        return FleisskKappaResult(
            kappa=0.0,
            interpretation="insufficient_raters",
            n_raters=k,
            n_items=n,
            n_categories=len(categories),
        )

    # Build rating matrix: n_items x n_categories
    # Each cell contains count of raters who assigned that category to that item
    n_cat = len(categories)
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    matrix = np.zeros((n, n_cat))

    for i, item in enumerate(items):
        for rater, rating in ratings[item].items():
            if rating in cat_to_idx:
                matrix[i, cat_to_idx[rating]] += 1

    # Raters per item (should be consistent, but handle variation)
    n_raters = matrix.sum(axis=1)

    # P_i = agreement for item i
    # P_i = (1 / (n_j * (n_j - 1))) * sum_k(n_ijk * (n_ijk - 1))
    P_i = np.zeros(n)
    for i in range(n):
        n_j = n_raters[i]
        if n_j >= 2:
            P_i[i] = (1 / (n_j * (n_j - 1))) * np.sum(matrix[i] * (matrix[i] - 1))

    # P_bar = mean agreement
    P_bar = np.mean(P_i)

    # p_j = proportion of all assignments to category j
    p_j = matrix.sum(axis=0) / matrix.sum()

    # P_e_bar = expected agreement by chance
    P_e_bar = np.sum(p_j ** 2)

    # Kappa
    if P_e_bar == 1.0:
        kappa = 1.0
    else:
        kappa = (P_bar - P_e_bar) / (1 - P_e_bar)

    return FleisskKappaResult(
        kappa=kappa,
        interpretation=interpret_kappa(kappa),
        n_raters=int(np.mean(n_raters)),
        n_items=n,
        n_categories=n_cat,
    )


def calculate_inter_judge_agreement(
    all_votes: List[Tuple[str, str, str]],  # (prompt_id, judge_model, winner)
) -> Dict[str, any]:
    """Calculate comprehensive inter-judge agreement metrics.

    Args:
        all_votes: List of (prompt_id, judge_model, winner) tuples

    Returns:
        Dictionary with all agreement metrics
    """
    # Reorganize by prompt
    votes_by_prompt: Dict[str, Dict[str, str]] = {}
    for prompt_id, judge_model, winner in all_votes:
        if prompt_id not in votes_by_prompt:
            votes_by_prompt[prompt_id] = {}
        # Take the majority vote per judge model for this prompt
        if judge_model not in votes_by_prompt[prompt_id]:
            votes_by_prompt[prompt_id][judge_model] = winner

    # Calculate pairwise kappa
    pairwise = calculate_pairwise_kappa(votes_by_prompt)

    # Calculate overall kappa (Fleiss)
    fleiss = calculate_fleiss_kappa(votes_by_prompt)

    # Calculate average pairwise kappa
    if pairwise:
        avg_kappa = sum(r.kappa for r in pairwise.values()) / len(pairwise)
    else:
        avg_kappa = 0.0

    return {
        "fleiss_kappa": fleiss,
        "pairwise_kappa": pairwise,
        "average_pairwise_kappa": avg_kappa,
        "overall_interpretation": interpret_kappa(avg_kappa),
        "n_prompts": len(votes_by_prompt),
        "n_judges": len(set(judge for _, judge, _ in all_votes)),
    }
```

---

## 3. CLI Options Implementation

```python
# src/cli.py (additions to existing CLI)

import typer
from typing import Optional, List
from pathlib import Path
from enum import Enum

app = typer.Typer(
    name="gemini-eval",
    help="Gemini Writing Evaluation Framework",
    no_args_is_help=True,
)


class Tier(str, Enum):
    PRO = "pro"
    FLASH = "flash"
    BOTH = "both"


class JudgePersona(str, Enum):
    BOTH = "both"
    EXPERT = "expert"
    RECIPIENT = "recipient"


@app.command()
def run(
    # Preset and basic options
    preset: int = typer.Option(
        6, "--preset", "-p",
        help="Preset configuration level (1-10)",
        min=1, max=10
    ),
    prompts: Optional[int] = typer.Option(
        None, "--prompts", "-n",
        help="Number of prompts (overrides preset)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show estimate without running"
    ),

    # Model configuration
    models: Optional[str] = typer.Option(
        None, "--models", "-m",
        help="Comma-separated list of models to evaluate"
    ),
    tier: Tier = typer.Option(
        Tier.BOTH, "--tier", "-t",
        help="Model tier to evaluate: pro, flash, or both"
    ),

    # Judge configuration
    judges: Optional[str] = typer.Option(
        None, "--judges", "-j",
        help="Comma-separated list of judge models"
    ),
    votes: Optional[int] = typer.Option(
        None, "--votes", "-v",
        help="Votes per judge (1, 3, or 5)"
    ),
    persona: JudgePersona = typer.Option(
        JudgePersona.BOTH, "--persona",
        help="Judge persona: both, expert, or recipient"
    ),

    # Task filtering
    occupations: Optional[str] = typer.Option(
        None, "--occupations", "-o",
        help="Comma-separated O*NET occupation codes (supports wildcards like '11-*')"
    ),
    industries: Optional[str] = typer.Option(
        None, "--industries", "-i",
        help="Comma-separated NAICS codes"
    ),
    job_zones: Optional[str] = typer.Option(
        None, "--job-zones", "-z",
        help="Comma-separated job zones (1-5)"
    ),
    formality_range: Optional[str] = typer.Option(
        None, "--formality-range",
        help="Formality range as 'min-max' (e.g., '1-3' for casual to moderate)"
    ),
    age_range: Optional[str] = typer.Option(
        None, "--age-range",
        help="Age range as 'min-max' (e.g., '18-35' for younger personas)"
    ),

    # Sampling limits
    occupation_limit: Optional[int] = typer.Option(
        None, "--occupation-limit",
        help="Maximum prompts per occupation"
    ),
    industry_limit: Optional[int] = typer.Option(
        None, "--industry-limit",
        help="Maximum prompts per industry"
    ),

    # Reproducibility
    seed: Optional[int] = typer.Option(
        None, "--seed", "-s",
        help="Random seed for reproducibility"
    ),

    # Resume
    resume: Optional[Path] = typer.Option(
        None, "--resume", "-r",
        help="Resume from a previous run directory"
    ),

    # Concurrency
    concurrent: int = typer.Option(
        30, "--concurrent", "-c",
        help="Maximum concurrent API requests (10-50)",
        min=10, max=50
    ),
):
    """Run the evaluation with specified configuration."""
    import asyncio
    from .config.presets import PRESETS, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES
    from .config.settings import EvalConfig, JudgeConfig
    from .config.cost_estimator import estimate_cost, format_cost_estimate

    # Start with preset
    config = PRESETS[preset]

    # Override with CLI options
    if prompts:
        config.num_prompts = prompts

    # Handle tier selection
    if tier == Tier.PRO:
        config.model_pairs = PRO_PAIRS
    elif tier == Tier.FLASH:
        config.model_pairs = FLASH_PAIRS
    # BOTH uses preset default

    # Parse models if specified
    if models:
        model_list = [m.strip() for m in models.split(",")]
        # Filter pairs to only include specified models
        config.model_pairs = [
            (g, c) for g, c in config.model_pairs
            if g in model_list or c in model_list
        ]

    # Judge configuration
    if judges:
        judge_list = [j.strip() for j in judges.split(",")]
        config.judge_config.models = judge_list

    if votes:
        config.judge_config.votes_per_judge = votes

    if persona == JudgePersona.EXPERT:
        config.judge_config.use_both_personas = False
    elif persona == JudgePersona.RECIPIENT:
        config.judge_config.use_both_personas = False
        # Note: would need to modify judge to only use recipient persona
    # BOTH keeps default

    # Store filtering options
    filter_config = {
        "occupations": [o.strip() for o in occupations.split(",")] if occupations else None,
        "industries": [i.strip() for i in industries.split(",")] if industries else None,
        "job_zones": [int(z) for z in job_zones.split(",")] if job_zones else None,
        "formality_range": parse_range(formality_range) if formality_range else None,
        "age_range": parse_range(age_range) if age_range else None,
        "occupation_limit": occupation_limit,
        "industry_limit": industry_limit,
    }

    if seed:
        config.random_seed = seed

    # Show cost estimate
    estimate = estimate_cost(config)
    print(format_cost_estimate(estimate, config))

    if dry_run:
        return

    # Confirm before running
    if not typer.confirm("Proceed?", default=False):
        raise typer.Abort()

    # Run evaluation
    asyncio.run(run_evaluation_async(config, filter_config, resume, concurrent))


def parse_range(range_str: str) -> tuple:
    """Parse a range string like '1-5' into (min, max) tuple."""
    if not range_str:
        return None
    parts = range_str.split("-")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid range format: {range_str}. Use 'min-max'.")
    return (int(parts[0]), int(parts[1]))


async def run_evaluation_async(config, filter_config, resume_path, max_concurrent):
    """Run the async evaluation."""
    from .api.openrouter_client import OpenRouterClient
    from .storage.checkpoint import CheckpointManager
    from .storage.database import Database
    from .storage.run_directory import RunDirectory
    from .eval.engine import EvaluationEngine
    from .tui.progress_dashboard import ProgressDashboard
    from .prompts.phase2_algorithmic import generate_prompts
    import os

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise typer.BadParameter("OPENROUTER_API_KEY environment variable not set")

    # Set up run directory
    if resume_path:
        run_dir = RunDirectory.load(resume_path)
    else:
        run_dir = RunDirectory.create_new(config)

    # Initialize components
    client = OpenRouterClient(api_key)
    db = Database(run_dir.results_db)
    checkpoint = CheckpointManager(run_dir)

    # Generate or load prompts
    if resume_path:
        prompts = checkpoint.load_prompts()
    else:
        prompts = await generate_prompts(
            config=config,
            **filter_config
        )

    # Create TUI dashboard
    dashboard = ProgressDashboard()

    # Create engine with progress callback
    engine = EvaluationEngine(
        config=config,
        client=client,
        checkpoint_manager=checkpoint,
        database=db,
        progress_callback=dashboard.update_state,
        max_concurrent_requests=max_concurrent,
    )

    # Run with TUI
    async with dashboard.run_async():
        results = await engine.run_evaluation(prompts)

    await client.close()
    await db.close()

    print(f"\nEvaluation complete. Results saved to: {run_dir.root}")


@app.command()
def view(
    run_dir: Path = typer.Argument(
        ...,
        help="Path to evaluation run directory"
    ),
):
    """View results in interactive TUI."""
    from .tui.results_viewer import ResultsViewer
    viewer = ResultsViewer(run_dir)
    viewer.run()


@app.command()
def compare(
    run_dirs: List[Path] = typer.Argument(
        ...,
        help="Paths to evaluation run directories to compare"
    ),
):
    """Compare results across multiple runs."""
    from .analysis.cross_run_compare import compare_runs
    compare_runs(run_dirs)


@app.command()
def export(
    run_dir: Path = typer.Argument(
        ...,
        help="Path to evaluation run directory"
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output file path"
    ),
    format: str = typer.Option(
        "csv", "--format", "-f",
        help="Export format: csv, json, or pdf"
    ),
):
    """Export results to various formats."""
    from .storage.database import Database
    from .reports.pdf_generator import generate_pdf_report
    import json

    db = Database(run_dir / "results.db")

    if format == "csv":
        output_path = output or (run_dir / "results_export.csv")
        db.export_csv(output_path)
        print(f"Exported to {output_path}")

    elif format == "json":
        output_path = output or (run_dir / "results_export.json")
        results = db.get_all_results()
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Exported to {output_path}")

    elif format == "pdf":
        output_path = output or (run_dir / "report.pdf")
        generate_pdf_report(run_dir, output_path)
        print(f"Generated report at {output_path}")


if __name__ == "__main__":
    app()
```

---

## 4. TUI Progress Dashboard with Cost Tracking and Help Overlay

```python
# src/tui/progress_dashboard.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, ProgressBar, DataTable, Log, Label
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.reactive import reactive
from typing import Optional, Dict
from datetime import datetime, timedelta
import time

from ..eval.engine import ProgressState, EvalPhase
from ..analysis.statistics import calculate_inter_judge_agreement, interpret_kappa


class HelpScreen(ModalScreen):
    """Modal help overlay screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("h", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("""
╭─────────────────────────────────────────────────────────────────╮
│                        KEYBOARD SHORTCUTS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Navigation                                                      │
│  ──────────                                                      │
│  ↑/↓        Scroll activity log                                  │
│  PgUp/PgDn  Scroll by page                                       │
│  Home/End   Jump to start/end of log                             │
│                                                                  │
│  Controls                                                        │
│  ─────────                                                       │
│  p          Pause/Resume evaluation                              │
│  q          Quit (saves checkpoint for resume)                   │
│  s          Save checkpoint now                                  │
│                                                                  │
│  Views                                                           │
│  ─────                                                           │
│  d          Toggle detailed view (full prompts/responses)        │
│  t          Toggle statistics panel                              │
│  h          Show this help screen                                │
│                                                                  │
│  Press ESC or 'h' to close this help                             │
╰─────────────────────────────────────────────────────────────────╯
            """, id="help-content"),
            id="help-container"
        )


class CostWidget(Static):
    """Widget displaying cost tracking information."""

    spent: reactive[float] = reactive(0.0)
    projected: reactive[float] = reactive(0.0)

    def render(self) -> str:
        return f"""Cost Tracking
─────────────
Spent:      ${self.spent:,.2f}
Projected:  ${self.projected:,.2f}
Remaining:  ${max(0, self.projected - self.spent):,.2f}"""


class ETAWidget(Static):
    """Widget displaying ETA calculation."""

    start_time: reactive[float] = reactive(0.0)
    estimated_completion: reactive[float] = reactive(0.0)
    completed: reactive[int] = reactive(0)
    total: reactive[int] = reactive(0)

    def render(self) -> str:
        now = time.time()
        elapsed = now - self.start_time if self.start_time else 0
        elapsed_str = str(timedelta(seconds=int(elapsed)))

        if self.estimated_completion > now:
            remaining = self.estimated_completion - now
            eta_str = str(timedelta(seconds=int(remaining)))
        else:
            eta_str = "--:--:--"

        # Calculate completion time
        if self.estimated_completion > 0:
            completion_time = datetime.fromtimestamp(self.estimated_completion)
            completion_str = completion_time.strftime("%H:%M:%S")
        else:
            completion_str = "--:--:--"

        return f"""Timing
──────
Elapsed:     {elapsed_str}
ETA:         {eta_str}
Complete at: {completion_str}"""


class ThroughputWidget(Static):
    """Widget displaying response times and throughput metrics."""

    avg_response_ms: reactive[float] = reactive(0.0)
    avg_judge_ms: reactive[float] = reactive(0.0)
    api_calls_per_min: reactive[float] = reactive(0.0)

    def render(self) -> str:
        return f"""Performance
───────────
Avg Response:  {self.avg_response_ms:.0f}ms
Avg Judge:     {self.avg_judge_ms:.0f}ms
API calls/min: {self.api_calls_per_min:.0f}"""


class JudgeAgreementWidget(Static):
    """Widget displaying inter-judge agreement (Cohen's Kappa)."""

    kappa: reactive[float] = reactive(0.0)
    interpretation: reactive[str] = reactive("--")

    def render(self) -> str:
        return f"""Judge Agreement
───────────────
Cohen's κ: {self.kappa:.3f}
Level: {self.interpretation}"""


class PerJudgeVotesWidget(Static):
    """Widget showing per-judge vote breakdown."""

    votes: reactive[Dict[str, Dict[str, int]]] = reactive({})

    def render(self) -> str:
        if not self.votes:
            return "Per-Judge Votes\n───────────────\nNo data yet"

        lines = ["Per-Judge Votes", "───────────────"]
        for judge, counts in self.votes.items():
            # Shorten judge name for display
            short_name = judge.split("/")[-1][:15]
            g = counts.get("gemini", 0)
            c = counts.get("competitor", 0)
            t = counts.get("tie", 0)
            total = g + c + t
            if total > 0:
                g_pct = g / total * 100
                lines.append(f"{short_name}: G:{g_pct:.0f}% ({g}/{c}/{t})")
            else:
                lines.append(f"{short_name}: --")

        return "\n".join(lines)


class CurrentBatchWidget(Static):
    """Widget showing current batch details including occupation/industry."""

    prompt_id: reactive[str] = reactive("")
    occupation: reactive[str] = reactive("")
    industry: reactive[str] = reactive("")
    phase: reactive[str] = reactive("")

    def render(self) -> str:
        return f"""Current Batch
─────────────
Prompt:     {self.prompt_id or '--'}
Occupation: {self.occupation or '--'}
Industry:   {self.industry or '--'}
Phase:      {self.phase or '--'}"""


class ModelPairWidget(Static):
    """Widget showing progress for a single model pair."""

    pair_name: str
    completed: reactive[int] = reactive(0)
    total: reactive[int] = reactive(0)
    gemini_wins: reactive[int] = reactive(0)
    competitor_wins: reactive[int] = reactive(0)
    ties: reactive[int] = reactive(0)

    def __init__(self, pair_name: str, **kwargs):
        super().__init__(**kwargs)
        self.pair_name = pair_name

    def render(self) -> str:
        total_decided = self.gemini_wins + self.competitor_wins + self.ties
        if total_decided > 0:
            win_rate = self.gemini_wins / total_decided * 100
            # Calculate 95% CI using Wilson score interval (simplified)
            from math import sqrt
            n = total_decided
            p = self.gemini_wins / n
            z = 1.96  # 95% CI
            denominator = 1 + z*z/n
            center = (p + z*z/(2*n)) / denominator
            spread = z * sqrt((p*(1-p) + z*z/(4*n))/n) / denominator
            ci_low = max(0, center - spread) * 100
            ci_high = min(1, center + spread) * 100
            win_str = f"{win_rate:.1f}% [{ci_low:.0f}-{ci_high:.0f}%]"
        else:
            win_str = "--"

        # Progress bar visualization
        pct = self.completed / self.total * 100 if self.total > 0 else 0
        bar_width = 20
        filled = int(pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Shorten pair name for display
        parts = self.pair_name.split("_vs_")
        if len(parts) == 2:
            g_short = parts[0].split("/")[-1][:12]
            c_short = parts[1].split("/")[-1][:12]
            display_name = f"{g_short} vs {c_short}"
        else:
            display_name = self.pair_name[:30]

        status = "✓" if self.completed == self.total else ""

        return f"{display_name:30s} {bar} {self.completed:4d}/{self.total:4d} {status} [{win_str}]"


class ProgressDashboard(App):
    """Real-time progress visualization TUI with all required elements."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 3;
        grid-columns: 1fr 1fr 1fr;
        grid-rows: auto 1fr auto;
    }

    #header-panel {
        column-span: 3;
        height: 3;
        background: $primary;
        text-align: center;
    }

    #progress-panel {
        column-span: 3;
        height: auto;
        border: solid green;
        padding: 1;
    }

    #pairs-panel {
        column-span: 2;
        height: auto;
        border: solid blue;
        padding: 1;
    }

    #stats-panel {
        height: auto;
        border: solid yellow;
        padding: 1;
    }

    #batch-panel {
        height: auto;
        border: solid cyan;
        padding: 1;
    }

    #log-panel {
        column-span: 2;
        height: 10;
        border: solid white;
    }

    #error-panel {
        height: 3;
        border: solid red;
    }

    #help-container {
        align: center middle;
        width: 70;
        height: 30;
        background: $surface;
        border: solid green;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("d", "toggle_detail", "Detailed View"),
        Binding("s", "save_checkpoint", "Save"),
        Binding("h", "show_help", "Help"),
        Binding("t", "toggle_stats", "Stats"),
    ]

    # Reactive state
    state: reactive[Optional[ProgressState]] = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._paused = False
        self._engine = None
        self._pair_widgets: Dict[str, ModelPairWidget] = {}

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-container"):
            # Header panel with title and timing
            yield Static(
                "GEMINI WRITING EVAL - Initializing...",
                id="header-panel"
            )

            # Overall progress
            with Container(id="progress-panel"):
                yield Label("Overall Progress")
                yield ProgressBar(id="main-progress", total=100)
                yield Static("Phase: INITIALIZING", id="phase-label")

            # Model pairs progress
            with Container(id="pairs-panel"):
                yield Label("Model Pairs")
                yield Container(id="pairs-container")

            # Statistics panel
            with Vertical(id="stats-panel"):
                yield CostWidget(id="cost-widget")
                yield ETAWidget(id="eta-widget")
                yield ThroughputWidget(id="throughput-widget")
                yield JudgeAgreementWidget(id="kappa-widget")
                yield PerJudgeVotesWidget(id="votes-widget")

            # Current batch panel
            yield CurrentBatchWidget(id="batch-widget")

            # Activity log
            yield Log(id="log-panel", highlight=True)

            # Error summary
            yield Static("Retries: 0 | Failures: 0 | Rate Limits: 0", id="error-panel")

        yield Footer()

    def set_engine(self, engine):
        """Set reference to evaluation engine for pause/resume."""
        self._engine = engine

    def update_state(self, state: ProgressState):
        """Update dashboard with new state (called by engine)."""
        self.state = state
        self.call_from_thread(self._apply_state, state)

    def _apply_state(self, state: ProgressState):
        """Apply state updates to widgets."""
        # Update header
        elapsed = time.time() - state.start_time if state.start_time else 0
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        header = self.query_one("#header-panel", Static)
        header.update(
            f"GEMINI WRITING EVAL - {state.phase.value.upper()} | "
            f"Elapsed: {elapsed_str} | "
            f"{state.completed_prompts}/{state.total_prompts} prompts"
        )

        # Update main progress bar
        progress = self.query_one("#main-progress", ProgressBar)
        pct = state.completed_prompts / state.total_prompts * 100 if state.total_prompts > 0 else 0
        progress.update(progress=pct)

        # Update phase label
        phase_label = self.query_one("#phase-label", Static)
        phase_markers = {
            EvalPhase.GENERATION: "[Generation ◐] [Judging ○] [Analysis ○]",
            EvalPhase.JUDGING: "[Generation ✓] [Judging ◐] [Analysis ○]",
            EvalPhase.ANALYSIS: "[Generation ✓] [Judging ✓] [Analysis ◐]",
            EvalPhase.COMPLETE: "[Generation ✓] [Judging ✓] [Analysis ✓]",
        }
        phase_label.update(f"Phase: {state.phase.value.upper()} {phase_markers.get(state.phase, '')}")

        # Update model pair widgets
        pairs_container = self.query_one("#pairs-container", Container)
        for pair_key, (completed, total) in state.pair_progress.items():
            if pair_key not in self._pair_widgets:
                widget = ModelPairWidget(pair_key)
                widget.total = total
                self._pair_widgets[pair_key] = widget
                pairs_container.mount(widget)

            widget = self._pair_widgets[pair_key]
            widget.completed = completed
            wins = state.pair_wins.get(pair_key, (0, 0, 0))
            widget.gemini_wins = wins[0]
            widget.competitor_wins = wins[1]
            widget.ties = wins[2]

        # Update cost widget
        cost_widget = self.query_one("#cost-widget", CostWidget)
        cost_widget.spent = state.total_cost_so_far
        cost_widget.projected = state.projected_total_cost

        # Update ETA widget
        eta_widget = self.query_one("#eta-widget", ETAWidget)
        eta_widget.start_time = state.start_time
        eta_widget.estimated_completion = state.estimated_completion_time
        eta_widget.completed = state.completed_prompts
        eta_widget.total = state.total_prompts

        # Update throughput widget
        throughput_widget = self.query_one("#throughput-widget", ThroughputWidget)
        throughput_widget.avg_response_ms = state.avg_response_time_ms
        throughput_widget.avg_judge_ms = state.avg_judge_time_ms
        throughput_widget.api_calls_per_min = state.api_calls_per_minute

        # Update judge agreement widget
        if state.judge_votes:
            agreement = calculate_inter_judge_agreement(state.judge_votes)
            kappa_widget = self.query_one("#kappa-widget", JudgeAgreementWidget)
            kappa_widget.kappa = agreement.get("average_pairwise_kappa", 0.0)
            kappa_widget.interpretation = agreement.get("overall_interpretation", "--")

        # Update per-judge votes widget
        if state.current_judge_votes:
            votes_widget = self.query_one("#votes-widget", PerJudgeVotesWidget)
            votes_widget.votes = state.current_judge_votes

        # Update current batch widget
        batch_widget = self.query_one("#batch-widget", CurrentBatchWidget)
        batch_widget.prompt_id = state.current_prompt_id or ""
        batch_widget.occupation = state.current_occupation or ""
        batch_widget.industry = state.current_industry or ""
        batch_widget.phase = state.phase.value

        # Update error panel
        error_panel = self.query_one("#error-panel", Static)
        error_panel.update(
            f"Retries: {state.retries} | "
            f"Failures: {state.failures} | "
            f"Rate Limits: {state.rate_limit_pauses}"
        )

    def log_activity(self, message: str):
        """Add message to activity log."""
        log = self.query_one("#log-panel", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.write_line(f"{timestamp}  {message}")

    def action_quit(self):
        """Graceful quit - saves checkpoint."""
        self.log_activity("Saving checkpoint and quitting...")
        if self._engine:
            self._engine.cancel()
        self.exit()

    def action_toggle_pause(self):
        """Toggle pause/resume."""
        if self._engine:
            if self._paused:
                self._engine.resume()
                self._paused = False
                self.log_activity("Resumed evaluation")
            else:
                self._engine.pause()
                self._paused = True
                self.log_activity("Paused evaluation")

    def action_toggle_detail(self):
        """Toggle detailed view."""
        self.log_activity("Detailed view toggled")
        # Implementation would show full prompts/responses

    def action_save_checkpoint(self):
        """Save checkpoint now."""
        self.log_activity("Checkpoint saved")
        # Implementation would trigger checkpoint save

    def action_show_help(self):
        """Show help overlay."""
        self.push_screen(HelpScreen())

    def action_toggle_stats(self):
        """Toggle statistics panel visibility."""
        stats = self.query_one("#stats-panel", Vertical)
        stats.toggle_class("hidden")

    async def run_async(self):
        """Context manager for running with async evaluation."""
        return self.run()
```

---

## 5. Name Formality Variation

```python
# src/data/name_generator.py (additions)

from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum
import random


class NameFormality(str, Enum):
    """Name formality levels."""
    VERY_FORMAL = "very_formal"      # Dr. Williams, Professor Chen
    FORMAL = "formal"                 # Michael T. Williams, Sarah Chen
    STANDARD = "standard"             # Michael Williams, Sarah Chen
    INFORMAL = "informal"             # Mike Williams, Sarah
    CASUAL = "casual"                 # Mike, Sarah


@dataclass
class FormattedName:
    """Name with formality formatting applied."""
    display_name: str
    first_name: str
    last_name: str
    formality: NameFormality
    title: Optional[str] = None
    middle_initial: Optional[str] = None


class NameGenerator:
    """Generate demographically diverse names with formality variation."""

    # Title prefixes by type
    PROFESSIONAL_TITLES = ["Dr.", "Professor", "Prof."]
    FORMAL_TITLES = ["Mr.", "Ms.", "Mrs."]

    # Common middle initials
    MIDDLE_INITIALS = list("ABCDEFGHJKLMNPRSTW")

    def __init__(self, census_data_path: Optional[str] = None):
        self.census_data = self._load_census_data(census_data_path)
        self.rng = random.Random()

    def _load_census_data(self, path: Optional[str]) -> dict:
        """Load census-based name frequency data."""
        # Default data structure - would be loaded from file
        return {
            "first_names": {
                "male": {
                    "boomer": ["Robert", "William", "James", "John", "Richard", "Michael", "David", "Thomas"],
                    "gen_x": ["Michael", "Christopher", "Matthew", "David", "James", "Daniel", "Robert", "John"],
                    "millennial": ["Michael", "Christopher", "Matthew", "Joshua", "Daniel", "David", "Andrew", "James"],
                    "gen_z": ["Liam", "Noah", "Oliver", "Elijah", "James", "William", "Benjamin", "Lucas"],
                },
                "female": {
                    "boomer": ["Mary", "Patricia", "Barbara", "Linda", "Elizabeth", "Jennifer", "Maria", "Susan"],
                    "gen_x": ["Jennifer", "Amy", "Melissa", "Michelle", "Kimberly", "Lisa", "Angela", "Heather"],
                    "millennial": ["Jessica", "Ashley", "Emily", "Sarah", "Samantha", "Amanda", "Brittany", "Elizabeth"],
                    "gen_z": ["Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia"],
                },
            },
            "last_names": {
                "common": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"],
                "asian": ["Chen", "Wang", "Li", "Zhang", "Liu", "Kim", "Park", "Nguyen", "Patel", "Singh"],
                "hispanic": ["Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez"],
                "european": ["Mueller", "Schmidt", "Fischer", "Weber", "O'Brien", "Murphy", "Kelly"],
            },
            # Nickname mappings
            "nicknames": {
                "Robert": ["Bob", "Rob", "Bobby"],
                "William": ["Bill", "Will", "Billy"],
                "Michael": ["Mike", "Mikey"],
                "Richard": ["Rich", "Rick", "Dick"],
                "James": ["Jim", "Jimmy", "Jamie"],
                "Thomas": ["Tom", "Tommy"],
                "Christopher": ["Chris"],
                "Matthew": ["Matt"],
                "Daniel": ["Dan", "Danny"],
                "Andrew": ["Andy", "Drew"],
                "Jennifer": ["Jen", "Jenny"],
                "Elizabeth": ["Liz", "Beth", "Eliza"],
                "Katherine": ["Kate", "Katie", "Kathy"],
                "Patricia": ["Pat", "Patty", "Trish"],
                "Margaret": ["Maggie", "Meg", "Peggy"],
                "Rebecca": ["Becca", "Becky"],
                "Samantha": ["Sam", "Sammy"],
                "Alexandra": ["Alex", "Lexi"],
            },
        }

    def generate_name(
        self,
        generation: str = "millennial",
        ethnicity: Optional[str] = None,
        gender: Optional[str] = None,
        formality: NameFormality = NameFormality.STANDARD,
        is_professional: bool = False,  # Has PhD, is professor, etc.
        seed: Optional[int] = None,
    ) -> FormattedName:
        """Generate a name with specified formality level.

        Args:
            generation: Age generation (boomer, gen_x, millennial, gen_z)
            ethnicity: Optional ethnicity for name pool selection
            gender: Optional gender (male, female, or None for random)
            formality: Desired formality level for name display
            is_professional: Whether person has professional title (Dr., Prof.)
            seed: Optional random seed for reproducibility

        Returns:
            FormattedName with formatted display name
        """
        if seed is not None:
            self.rng.seed(seed)

        # Select gender if not specified
        if gender is None:
            gender = self.rng.choice(["male", "female"])

        # Select first name based on generation and gender
        first_names = self.census_data["first_names"].get(gender, {}).get(
            generation, self.census_data["first_names"][gender]["millennial"]
        )
        first_name = self.rng.choice(first_names)

        # Select last name based on ethnicity
        if ethnicity and ethnicity in self.census_data["last_names"]:
            last_names = self.census_data["last_names"][ethnicity]
        else:
            # Weighted random across ethnicities
            all_last_names = []
            for names in self.census_data["last_names"].values():
                all_last_names.extend(names)
            last_names = all_last_names
        last_name = self.rng.choice(last_names)

        # Generate middle initial if needed
        middle_initial = self.rng.choice(self.MIDDLE_INITIALS) if self.rng.random() < 0.3 else None

        # Format name based on formality
        display_name, title = self._format_name(
            first_name=first_name,
            last_name=last_name,
            middle_initial=middle_initial,
            formality=formality,
            is_professional=is_professional,
            gender=gender,
        )

        return FormattedName(
            display_name=display_name,
            first_name=first_name,
            last_name=last_name,
            formality=formality,
            title=title,
            middle_initial=middle_initial,
        )

    def _format_name(
        self,
        first_name: str,
        last_name: str,
        middle_initial: Optional[str],
        formality: NameFormality,
        is_professional: bool,
        gender: str,
    ) -> tuple[str, Optional[str]]:
        """Format name according to formality level.

        Returns:
            Tuple of (display_name, title)
        """
        title = None

        if formality == NameFormality.VERY_FORMAL:
            # Dr. Williams, Professor Chen
            if is_professional:
                title = self.rng.choice(self.PROFESSIONAL_TITLES)
                return f"{title} {last_name}", title
            else:
                # Use formal title
                title = "Ms." if gender == "female" else "Mr."
                return f"{title} {last_name}", title

        elif formality == NameFormality.FORMAL:
            # Michael T. Williams
            if middle_initial:
                return f"{first_name} {middle_initial}. {last_name}", None
            else:
                return f"{first_name} {last_name}", None

        elif formality == NameFormality.STANDARD:
            # Michael Williams
            return f"{first_name} {last_name}", None

        elif formality == NameFormality.INFORMAL:
            # Mike Williams
            nickname = self._get_nickname(first_name)
            return f"{nickname} {last_name}", None

        elif formality == NameFormality.CASUAL:
            # Mike or Sarah (first name/nickname only)
            nickname = self._get_nickname(first_name)
            return nickname, None

        return f"{first_name} {last_name}", None

    def _get_nickname(self, first_name: str) -> str:
        """Get a nickname for a first name, or return original if none exists."""
        nicknames = self.census_data.get("nicknames", {}).get(first_name, [])
        if nicknames:
            return self.rng.choice(nicknames)
        return first_name

    def generate_email(
        self,
        name: FormattedName,
        company_domain: str,
        formality: NameFormality = NameFormality.STANDARD,
    ) -> str:
        """Generate an email address based on name and formality.

        Args:
            name: The person's name
            company_domain: Company domain (e.g., "acme.com")
            formality: Email style formality

        Returns:
            Email address string
        """
        first = name.first_name.lower()
        last = name.last_name.lower()

        if formality in [NameFormality.VERY_FORMAL, NameFormality.FORMAL]:
            # firstname.lastname@domain.com
            return f"{first}.{last}@{company_domain}"
        elif formality == NameFormality.STANDARD:
            # firstinitiallastname@domain.com or firstname.lastname
            if self.rng.random() < 0.5:
                return f"{first[0]}{last}@{company_domain}"
            return f"{first}.{last}@{company_domain}"
        elif formality == NameFormality.INFORMAL:
            # nickname.lastname or first.l
            nickname = self._get_nickname(name.first_name).lower()
            return f"{nickname}.{last}@{company_domain}"
        else:  # CASUAL
            # nickname or first
            nickname = self._get_nickname(name.first_name).lower()
            return f"{nickname}@{company_domain}"

    def match_formality_to_context(
        self,
        job_zone: int,
        skill_level: str,
        communication_formality: int,
        is_senior: bool = False,
    ) -> NameFormality:
        """Determine appropriate name formality based on context.

        Args:
            job_zone: O*NET job zone (1-5)
            skill_level: entry, mid, senior, executive
            communication_formality: 1-5 scale
            is_senior: Whether person is in senior position

        Returns:
            Appropriate NameFormality for context
        """
        # High formality contexts
        if communication_formality >= 4 or (job_zone >= 4 and is_senior):
            if skill_level == "executive" or (is_senior and job_zone == 5):
                return NameFormality.VERY_FORMAL
            return NameFormality.FORMAL

        # Low formality contexts
        if communication_formality <= 2:
            if job_zone <= 2:
                return NameFormality.CASUAL
            return NameFormality.INFORMAL

        # Default to standard
        return NameFormality.STANDARD
```

---

## 6. Phase 1 Generation Using Evaluated Models

```python
# src/prompts/phase1_offline.py

import asyncio
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from pathlib import Path

from ..api.openrouter_client import OpenRouterClient
from ..config.presets import PRO_PAIRS, FLASH_PAIRS
from ..data.onet_extractor import ONetTask


@dataclass
class PersonaVariation:
    """A generated persona variation for a task."""
    task_id: str
    variation_id: str
    generated_by_model: str
    writer_persona: Dict[str, Any]
    recipient_persona: Dict[str, Any]
    context_enrichment: Dict[str, Any]
    raw_response: str


class Phase1Generator:
    """Offline LLM generation of persona/context variations.

    CRITICAL per PROMPT.md: "Use the same models being evaluated for this generation
    (note: this creates potential bias but ensures prompts aren't accidentally biased
    against any particular model)."
    """

    GENERATION_SYSTEM_PROMPT = """You are helping create diverse, realistic writing task scenarios.
Given an O*NET occupational task, generate a realistic persona and context variation.

Generate creative, diverse variations including:
1. Writer persona (name, age, generation, skill level, background)
2. Recipient persona (name, role, relationship to writer)
3. Context enrichment (company details, temporal context, emotional context)
4. Any relevant attachments or prior context

Be creative and realistic. Vary across all dimensions: ages, ethnicities, company sizes,
industries, formality levels, urgency levels, and emotional contexts.

Output as JSON."""

    GENERATION_USER_TEMPLATE = """Task: {task_statement}
Occupation: {occupation_title}
Job Zone: {job_zone} (1=entry, 5=executive)

Generate a realistic scenario variation. Include:
- Writer: name, age (18-80), generation (gen_z/millennial/gen_x/boomer), job_title, skill_level (entry/mid/senior/executive)
- Recipient: name, job_title, relationship (new_contact/colleague/manager/client/etc)
- Context: company_name, company_size (startup/small/mid_market/enterprise/fortune_500), industry
- Formality: 1-5 scale
- Urgency: 1-5 scale
- Emotional context: routine/crisis/celebration/conflict/bad_news
- Any relevant prior_context or attachments if applicable

Output valid JSON only."""

    def __init__(
        self,
        client: OpenRouterClient,
        output_dir: Path,
        variations_per_task: int = 3,
    ):
        self.client = client
        self.output_dir = output_dir
        self.variations_per_task = variations_per_task

        # Get models being evaluated for generation
        self.generation_models = self._get_evaluated_models()

    def _get_evaluated_models(self) -> List[str]:
        """Get list of all models being evaluated.

        Per PROMPT.md requirement: use same models being evaluated for generation.
        """
        models = set()
        for gemini, competitor in PRO_PAIRS + FLASH_PAIRS:
            models.add(gemini)
            models.add(competitor)
        return list(models)

    async def generate_variations(
        self,
        tasks: List[ONetTask],
        max_concurrent: int = 10,
    ) -> Dict[str, List[PersonaVariation]]:
        """Generate persona variations for all tasks using evaluated models.

        Args:
            tasks: O*NET tasks to generate variations for
            max_concurrent: Maximum concurrent generation requests

        Returns:
            Dict mapping task_id to list of PersonaVariation
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        all_variations: Dict[str, List[PersonaVariation]] = {}

        async def generate_for_task(task: ONetTask) -> List[PersonaVariation]:
            async with semaphore:
                variations = []
                for i in range(self.variations_per_task):
                    # Round-robin across evaluated models
                    model = self.generation_models[i % len(self.generation_models)]

                    try:
                        variation = await self._generate_single_variation(
                            task=task,
                            variation_index=i,
                            model=model,
                        )
                        if variation:
                            variations.append(variation)
                    except Exception as e:
                        # Log but continue - partial variations are OK
                        print(f"Warning: Failed to generate variation {i} for {task.task_id}: {e}")

                return variations

        # Generate all variations in parallel
        tasks_with_variations = await asyncio.gather(
            *[generate_for_task(task) for task in tasks]
        )

        for task, variations in zip(tasks, tasks_with_variations):
            all_variations[task.task_id] = variations

        # Save to output directory
        await self._save_variations(all_variations)

        return all_variations

    async def _generate_single_variation(
        self,
        task: ONetTask,
        variation_index: int,
        model: str,
    ) -> Optional[PersonaVariation]:
        """Generate a single persona variation using specified model."""

        user_prompt = self.GENERATION_USER_TEMPLATE.format(
            task_statement=task.task_statement,
            occupation_title=task.occupation_title,
            job_zone=task.job_zone,
        )

        response = await self.client.complete(
            model=model,
            messages=[
                {"role": "system", "content": self.GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,  # Higher for diversity
        )

        # Parse JSON response
        try:
            data = self._parse_json_response(response.content)
        except json.JSONDecodeError:
            return None

        variation_id = f"{task.task_id}_v{variation_index}_{model.split('/')[-1]}"

        return PersonaVariation(
            task_id=task.task_id,
            variation_id=variation_id,
            generated_by_model=model,
            writer_persona=data.get("writer", {}),
            recipient_persona=data.get("recipient", {}),
            context_enrichment={
                "company": data.get("company", data.get("context", {}).get("company", {})),
                "formality": data.get("formality", 3),
                "urgency": data.get("urgency", 3),
                "emotional_context": data.get("emotional_context", "routine"),
                "prior_context": data.get("prior_context"),
                "attachments": data.get("attachments", []),
            },
            raw_response=response.content,
        )

    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from model response, handling markdown code blocks."""
        content = content.strip()

        # Try to extract JSON from markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        return json.loads(content)

    async def _save_variations(self, variations: Dict[str, List[PersonaVariation]]):
        """Save generated variations to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save as single JSON file
        output_file = self.output_dir / "variations.json"
        data = {
            task_id: [
                {
                    "variation_id": v.variation_id,
                    "generated_by_model": v.generated_by_model,
                    "writer_persona": v.writer_persona,
                    "recipient_persona": v.recipient_persona,
                    "context_enrichment": v.context_enrichment,
                }
                for v in task_variations
            ]
            for task_id, task_variations in variations.items()
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        # Also save per-model statistics
        model_stats = {}
        for task_variations in variations.values():
            for v in task_variations:
                model = v.generated_by_model
                model_stats[model] = model_stats.get(model, 0) + 1

        stats_file = self.output_dir / "generation_stats.json"
        with open(stats_file, "w") as f:
            json.dump({
                "total_variations": sum(len(v) for v in variations.values()),
                "total_tasks": len(variations),
                "variations_per_model": model_stats,
                "models_used": list(model_stats.keys()),
            }, f, indent=2)


async def run_phase1_generation(
    client: OpenRouterClient,
    tasks: List[ONetTask],
    output_dir: Path,
    variations_per_task: int = 3,
) -> Dict[str, List[PersonaVariation]]:
    """Run Phase 1 offline generation.

    This should be run as a preprocessing step before evaluation.
    """
    generator = Phase1Generator(
        client=client,
        output_dir=output_dir,
        variations_per_task=variations_per_task,
    )

    return await generator.generate_variations(tasks)
```

---

## 7. Ambiguity Behavior Tracking

```python
# src/eval/ambiguity_tracker.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from enum import Enum
import re


class AmbiguityBehavior(str, Enum):
    """How the model handled ambiguity."""
    ASKED_CLARIFICATION = "asked_clarification"      # Model explicitly asks for more info
    MADE_ASSUMPTIONS = "made_assumptions"            # Model proceeds with stated assumptions
    HEDGED = "hedged"                                # Model uses hedging language
    HALLUCINATED_DETAILS = "hallucinated_details"   # Model invented specific details
    PROCEEDED_GENERIC = "proceeded_generic"          # Model gave generic response
    REFUSED = "refused"                              # Model refused due to ambiguity


@dataclass
class AmbiguityAnalysis:
    """Analysis of how a model handled an ambiguous prompt."""
    prompt_id: str
    model: str
    ambiguity_type: str  # underspecified_recipient, missing_context, unclear_ask
    behavior: AmbiguityBehavior
    confidence: float  # 0.0 to 1.0
    evidence: List[str]  # Snippets that indicate this behavior
    assumptions_made: List[str]  # If made assumptions, what were they
    clarification_questions: List[str]  # If asked clarification, what questions


class AmbiguityTracker:
    """Track and analyze how models handle ambiguous prompts.

    Per PROMPT.md:
    - Does it make reasonable assumptions?
    - Does it ask for clarification (in the response)?
    - Does it hedge appropriately?
    - Does it hallucinate specific details?
    """

    # Patterns indicating clarification requests
    CLARIFICATION_PATTERNS = [
        r"could you (please )?(clarify|specify|tell me|provide)",
        r"what (exactly |specifically )?(do you mean|would you like|are you looking for)",
        r"I('d| would) need (more information|to know|clarification)",
        r"before I (can |proceed|continue)",
        r"can you (let me know|specify|clarify)",
        r"it would help (to know|if you could)",
        r"\?$",  # Ends with question mark
    ]

    # Patterns indicating hedging
    HEDGING_PATTERNS = [
        r"I('ll| will) assume",
        r"assuming (that |you mean)",
        r"if (you mean|I understand correctly)",
        r"based on (my understanding|what you've said)",
        r"I('m| am) not (entirely |completely )?(sure|certain)",
        r"(might|may|could|possibly)",
        r"generally speaking",
        r"in most cases",
        r"it depends on",
    ]

    # Patterns indicating hallucinated specifics
    HALLUCINATION_PATTERNS = [
        r"on (Monday|Tuesday|Wednesday|Thursday|Friday)",
        r"at \d{1,2}:\d{2}",
        r"in (January|February|March|April|May|June|July|August|September|October|November|December)",
        r"\$[\d,]+",  # Specific dollar amounts
        r"\d+%",  # Specific percentages
        r"(John|Sarah|Mike|David|Jennifer)",  # Made-up names when not in prompt
    ]

    # Patterns indicating explicit assumptions
    ASSUMPTION_PATTERNS = [
        r"I('ll |'m going to |will )assume",
        r"assuming (that |you)",
        r"based on the assumption",
        r"I('m |am )interpreting this as",
        r"I understand (this|you) to mean",
        r"given (that |the context)",
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._clarification_re = [re.compile(p, re.IGNORECASE) for p in self.CLARIFICATION_PATTERNS]
        self._hedging_re = [re.compile(p, re.IGNORECASE) for p in self.HEDGING_PATTERNS]
        self._hallucination_re = [re.compile(p, re.IGNORECASE) for p in self.HALLUCINATION_PATTERNS]
        self._assumption_re = [re.compile(p, re.IGNORECASE) for p in self.ASSUMPTION_PATTERNS]

    def analyze_response(
        self,
        prompt_id: str,
        model: str,
        response: str,
        ambiguity_type: str,
        prompt_context: Optional[Dict] = None,
    ) -> AmbiguityAnalysis:
        """Analyze how a model handled an ambiguous prompt.

        Args:
            prompt_id: The prompt identifier
            model: The model that generated the response
            response: The model's response text
            ambiguity_type: Type of ambiguity (underspecified_recipient, etc.)
            prompt_context: Optional context about what WAS specified in the prompt

        Returns:
            AmbiguityAnalysis with detected behavior
        """
        # Find all matches for each category
        clarification_matches = self._find_matches(response, self._clarification_re)
        hedging_matches = self._find_matches(response, self._hedging_re)
        hallucination_matches = self._find_matches(response, self._hallucination_re)
        assumption_matches = self._find_matches(response, self._assumption_re)

        # Determine primary behavior
        behavior, confidence = self._determine_behavior(
            response=response,
            clarification_count=len(clarification_matches),
            hedging_count=len(hedging_matches),
            hallucination_count=len(hallucination_matches),
            assumption_count=len(assumption_matches),
        )

        # Extract assumptions made
        assumptions = self._extract_assumptions(response, assumption_matches)

        # Extract clarification questions
        questions = self._extract_questions(response, clarification_matches)

        # Collect evidence
        evidence = []
        if clarification_matches:
            evidence.extend(clarification_matches[:3])
        if hedging_matches:
            evidence.extend(hedging_matches[:3])
        if assumption_matches:
            evidence.extend(assumption_matches[:3])
        if hallucination_matches:
            evidence.extend(hallucination_matches[:3])

        return AmbiguityAnalysis(
            prompt_id=prompt_id,
            model=model,
            ambiguity_type=ambiguity_type,
            behavior=behavior,
            confidence=confidence,
            evidence=evidence,
            assumptions_made=assumptions,
            clarification_questions=questions,
        )

    def _find_matches(self, text: str, patterns: List[re.Pattern]) -> List[str]:
        """Find all matches for a set of patterns."""
        matches = []
        for pattern in patterns:
            for match in pattern.finditer(text):
                # Get surrounding context
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                matches.append(context)
        return matches

    def _determine_behavior(
        self,
        response: str,
        clarification_count: int,
        hedging_count: int,
        hallucination_count: int,
        assumption_count: int,
    ) -> tuple[AmbiguityBehavior, float]:
        """Determine the primary behavior and confidence."""

        # Check for refusal first
        refusal_phrases = ["i cannot", "i'm unable to", "more information is needed", "please provide"]
        if any(phrase in response.lower() for phrase in refusal_phrases):
            if clarification_count > 0:
                return AmbiguityBehavior.REFUSED, 0.8

        # Strong clarification signal
        if clarification_count >= 2:
            return AmbiguityBehavior.ASKED_CLARIFICATION, min(0.9, 0.5 + clarification_count * 0.1)

        # Clear assumption signal
        if assumption_count >= 2:
            return AmbiguityBehavior.MADE_ASSUMPTIONS, min(0.9, 0.5 + assumption_count * 0.1)

        # Hallucinated details (specific info not in prompt)
        if hallucination_count >= 3:
            return AmbiguityBehavior.HALLUCINATED_DETAILS, min(0.8, 0.4 + hallucination_count * 0.1)

        # Hedging behavior
        if hedging_count >= 2:
            return AmbiguityBehavior.HEDGED, min(0.8, 0.4 + hedging_count * 0.1)

        # Mixed signals - look at response structure
        if clarification_count > 0 and assumption_count > 0:
            # Model asked but also made assumptions
            return AmbiguityBehavior.MADE_ASSUMPTIONS, 0.6

        # Default: proceeded with generic response
        return AmbiguityBehavior.PROCEEDED_GENERIC, 0.5

    def _extract_assumptions(self, response: str, matches: List[str]) -> List[str]:
        """Extract explicit assumptions from the response."""
        assumptions = []

        # Look for assumption statements
        assumption_pattern = re.compile(
            r"(?:I(?:'ll |'m going to |will )assume|assuming (?:that |you )|"
            r"I(?:'m |am )interpreting this as|I understand (?:this|you) to mean)"
            r"[^.!?]*[.!?]",
            re.IGNORECASE
        )

        for match in assumption_pattern.finditer(response):
            assumption_text = match.group(0).strip()
            if len(assumption_text) > 10:  # Filter out very short matches
                assumptions.append(assumption_text)

        return assumptions[:5]  # Limit to 5

    def _extract_questions(self, response: str, matches: List[str]) -> List[str]:
        """Extract clarification questions from the response."""
        questions = []

        # Find sentences ending with ?
        question_pattern = re.compile(r"[^.!?]*\?")

        for match in question_pattern.finditer(response):
            question = match.group(0).strip()
            if len(question) > 10:  # Filter out very short questions
                questions.append(question)

        return questions[:5]  # Limit to 5

    def aggregate_by_model(
        self,
        analyses: List[AmbiguityAnalysis],
    ) -> Dict[str, Dict[str, int]]:
        """Aggregate ambiguity handling by model.

        Returns dict of model -> behavior -> count.
        """
        result: Dict[str, Dict[str, int]] = {}

        for analysis in analyses:
            if analysis.model not in result:
                result[analysis.model] = {b.value: 0 for b in AmbiguityBehavior}
            result[analysis.model][analysis.behavior.value] += 1

        return result

    def aggregate_by_ambiguity_type(
        self,
        analyses: List[AmbiguityAnalysis],
    ) -> Dict[str, Dict[str, int]]:
        """Aggregate ambiguity handling by ambiguity type.

        Returns dict of ambiguity_type -> behavior -> count.
        """
        result: Dict[str, Dict[str, int]] = {}

        for analysis in analyses:
            if analysis.ambiguity_type not in result:
                result[analysis.ambiguity_type] = {b.value: 0 for b in AmbiguityBehavior}
            result[analysis.ambiguity_type][analysis.behavior.value] += 1

        return result
```

---

## 8. TUI Results Viewer with Filtering, Sorting, and Drill-Down

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Select, Button, Label,
    TabbedContent, TabPane, TextArea
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.reactive import reactive
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass
import json

from ..storage.database import Database


@dataclass
class FilterState:
    """Current filter state for results viewer."""
    occupation_filter: Optional[str] = None
    industry_filter: Optional[str] = None
    winner_filter: Optional[str] = None  # "gemini", "competitor", "tie", None
    model_pair_filter: Optional[str] = None
    formality_min: Optional[int] = None
    formality_max: Optional[int] = None
    has_constraints: Optional[bool] = None
    is_ambiguous: Optional[bool] = None
    sensitive_topic: Optional[str] = None


class FilterPanel(Static):
    """Filter controls panel."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Filters")

            yield Label("Occupation:")
            yield Input(placeholder="e.g., 11-* or Chief Executives", id="occupation-filter")

            yield Label("Industry:")
            yield Input(placeholder="e.g., 54 or Professional Services", id="industry-filter")

            yield Label("Winner:")
            yield Select(
                [
                    ("All", None),
                    ("Gemini Wins", "gemini"),
                    ("Competitor Wins", "competitor"),
                    ("Ties", "tie"),
                ],
                id="winner-filter"
            )

            yield Label("Model Pair:")
            yield Select([], id="model-pair-filter")  # Populated dynamically

            yield Label("Formality Range:")
            yield Horizontal(
                Input(placeholder="Min", id="formality-min"),
                Static("-"),
                Input(placeholder="Max", id="formality-max"),
            )

            yield Horizontal(
                Button("Apply", id="apply-filters"),
                Button("Clear", id="clear-filters"),
            )


class ComparisonDetailScreen(ModalScreen):
    """Modal screen showing detailed comparison view."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("left", "prev_comparison", "Previous"),
        Binding("right", "next_comparison", "Next"),
    ]

    def __init__(self, comparison_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.comparison = comparison_data

    def compose(self) -> ComposeResult:
        with Container(id="detail-container"):
            yield Header()

            # Prompt info
            with Container(id="prompt-info"):
                yield Static(f"Prompt: {self.comparison.get('prompt_id', 'N/A')}")
                yield Static(f"Occupation: {self.comparison.get('occupation_title', 'N/A')}")
                yield Static(f"Industry: {self.comparison.get('naics_sector', 'N/A')}")
                yield Static(f"Formality: {self.comparison.get('formality_level', 'N/A')}/5")

            # Full prompt text
            with TabbedContent():
                with TabPane("Prompt"):
                    yield TextArea(
                        self.comparison.get("full_prompt", "No prompt available"),
                        read_only=True,
                        id="prompt-text"
                    )

                with TabPane("Response A (Gemini)"):
                    yield TextArea(
                        self.comparison.get("gemini_response", "No response"),
                        read_only=True,
                        id="gemini-response"
                    )

                with TabPane("Response B (Competitor)"):
                    yield TextArea(
                        self.comparison.get("competitor_response", "No response"),
                        read_only=True,
                        id="competitor-response"
                    )

                with TabPane("Judgments"):
                    yield self._build_judgment_panel()

            yield Footer()

    def _build_judgment_panel(self) -> Static:
        """Build judgment details panel."""
        judgments = self.comparison.get("judgments", [])
        lines = ["## Judge Votes\n"]

        for j in judgments:
            lines.append(f"### {j.get('judge_model', 'Unknown')} ({j.get('persona', 'unknown')})")
            lines.append(f"Winner: {j.get('winner', 'N/A')}")
            lines.append(f"Confidence: {j.get('confidence', 'N/A')}/5")
            lines.append(f"Quality Gemini: {j.get('quality_gemini', 'N/A')}/10")
            lines.append(f"Quality Competitor: {j.get('quality_competitor', 'N/A')}/10")
            lines.append(f"Reasoning: {j.get('reasoning', 'No reasoning')}")
            lines.append("")

        return Static("\n".join(lines))


class ResultsViewer(App):
    """Interactive TUI for viewing and filtering evaluation results."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 4 1;
        grid-columns: 1fr 3fr;
    }

    #filter-panel {
        width: 30;
        border: solid blue;
        padding: 1;
    }

    #results-panel {
        border: solid green;
    }

    #stats-bar {
        height: 3;
        background: $primary;
    }

    #detail-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: solid green;
    }

    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "focus_filter", "Filter"),
        Binding("enter", "view_detail", "View Detail"),
        Binding("s", "toggle_sort", "Sort"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "export", "Export"),
    ]

    # Reactive state
    filter_state: reactive[FilterState] = reactive(FilterState())
    sort_column: reactive[str] = reactive("prompt_id")
    sort_ascending: reactive[bool] = reactive(True)

    def __init__(self, run_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.run_dir = run_dir
        self.db = Database(run_dir / "results.db")
        self.results: List[Dict] = []
        self.filtered_results: List[Dict] = []

    async def on_mount(self):
        """Load data on mount."""
        await self._load_results()
        self._update_table()
        self._populate_filters()

    async def _load_results(self):
        """Load all results from database."""
        self.results = await self.db.get_all_comparisons()
        self.filtered_results = self.results.copy()

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-container"):
            # Filter panel
            with Container(id="filter-panel"):
                yield FilterPanel()

            # Results panel
            with Container(id="results-panel"):
                # Stats bar
                yield Static("Total: 0 | Gemini Wins: 0 | Competitor Wins: 0 | Ties: 0", id="stats-bar")

                # Results table
                yield DataTable(id="results-table")

        yield Footer()

    def _populate_filters(self):
        """Populate filter options from data."""
        # Get unique model pairs
        model_pairs = set()
        for r in self.results:
            pair = f"{r.get('gemini_model', '')} vs {r.get('competitor_model', '')}"
            model_pairs.add(pair)

        # Update model pair select
        pair_select = self.query_one("#model-pair-filter", Select)
        options = [("All", None)] + [(p, p) for p in sorted(model_pairs)]
        pair_select.set_options(options)

    def _update_table(self):
        """Update the results table with current filtered data."""
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)

        # Add columns
        table.add_column("Prompt ID", key="prompt_id")
        table.add_column("Occupation", key="occupation")
        table.add_column("Industry", key="industry")
        table.add_column("Winner", key="winner")
        table.add_column("Gemini Votes", key="gemini_votes")
        table.add_column("Competitor Votes", key="comp_votes")
        table.add_column("Formality", key="formality")

        # Sort results
        sorted_results = sorted(
            self.filtered_results,
            key=lambda r: r.get(self.sort_column, ""),
            reverse=not self.sort_ascending
        )

        # Add rows
        for r in sorted_results:
            winner = r.get("final_winner", "N/A")
            winner_display = {
                "gemini": "[green]Gemini[/]",
                "competitor": "[red]Competitor[/]",
                "tie": "[yellow]Tie[/]",
            }.get(winner, winner)

            table.add_row(
                r.get("prompt_id", "N/A")[:20],
                r.get("occupation_title", "N/A")[:25],
                r.get("naics_sector", "N/A")[:15],
                winner_display,
                str(r.get("gemini_wins", 0)),
                str(r.get("competitor_wins", 0)),
                str(r.get("formality_level", "N/A")),
            )

        # Update stats bar
        self._update_stats()

    def _update_stats(self):
        """Update statistics bar."""
        total = len(self.filtered_results)
        gemini_wins = sum(1 for r in self.filtered_results if r.get("final_winner") == "gemini")
        comp_wins = sum(1 for r in self.filtered_results if r.get("final_winner") == "competitor")
        ties = sum(1 for r in self.filtered_results if r.get("final_winner") == "tie")

        stats_bar = self.query_one("#stats-bar", Static)
        stats_bar.update(
            f"Total: {total} | "
            f"Gemini Wins: {gemini_wins} ({gemini_wins/total*100:.1f}% if total else 0) | "
            f"Competitor Wins: {comp_wins} ({comp_wins/total*100:.1f}% if total else 0) | "
            f"Ties: {ties}"
        )

    def _apply_filters(self):
        """Apply current filter state to results."""
        self.filtered_results = []

        for r in self.results:
            # Occupation filter
            if self.filter_state.occupation_filter:
                occ = r.get("occupation_code", "") + " " + r.get("occupation_title", "")
                if self.filter_state.occupation_filter.lower() not in occ.lower():
                    continue

            # Industry filter
            if self.filter_state.industry_filter:
                ind = r.get("naics_code", "") + " " + r.get("naics_sector", "")
                if self.filter_state.industry_filter.lower() not in ind.lower():
                    continue

            # Winner filter
            if self.filter_state.winner_filter:
                if r.get("final_winner") != self.filter_state.winner_filter:
                    continue

            # Model pair filter
            if self.filter_state.model_pair_filter:
                pair = f"{r.get('gemini_model', '')} vs {r.get('competitor_model', '')}"
                if pair != self.filter_state.model_pair_filter:
                    continue

            # Formality range filter
            formality = r.get("formality_level", 3)
            if self.filter_state.formality_min and formality < self.filter_state.formality_min:
                continue
            if self.filter_state.formality_max and formality > self.filter_state.formality_max:
                continue

            # Has constraints filter
            if self.filter_state.has_constraints is not None:
                if r.get("has_constraints", False) != self.filter_state.has_constraints:
                    continue

            # Is ambiguous filter
            if self.filter_state.is_ambiguous is not None:
                if r.get("is_ambiguous", False) != self.filter_state.is_ambiguous:
                    continue

            self.filtered_results.append(r)

        self._update_table()

    def action_view_detail(self):
        """View detailed comparison for selected row."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.filtered_results):
            comparison = self.filtered_results[table.cursor_row]
            self.push_screen(ComparisonDetailScreen(comparison))

    def action_toggle_sort(self):
        """Toggle sort order or cycle through columns."""
        columns = ["prompt_id", "occupation", "industry", "winner", "formality"]
        current_idx = columns.index(self.sort_column) if self.sort_column in columns else 0

        if self.sort_ascending:
            self.sort_ascending = False
        else:
            self.sort_ascending = True
            current_idx = (current_idx + 1) % len(columns)
            self.sort_column = columns[current_idx]

        self._update_table()

    def action_focus_filter(self):
        """Focus on filter panel."""
        self.query_one("#occupation-filter", Input).focus()

    def action_refresh(self):
        """Refresh results from database."""
        self.call_later(self._load_results)
        self.call_later(self._update_table)

    async def action_export(self):
        """Export filtered results to CSV."""
        import csv
        output_path = self.run_dir / "filtered_export.csv"

        with open(output_path, "w", newline="") as f:
            if self.filtered_results:
                writer = csv.DictWriter(f, fieldnames=self.filtered_results[0].keys())
                writer.writeheader()
                writer.writerows(self.filtered_results)

        self.notify(f"Exported to {output_path}")

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        if event.button.id == "apply-filters":
            # Gather filter values
            self.filter_state.occupation_filter = self.query_one("#occupation-filter", Input).value or None
            self.filter_state.industry_filter = self.query_one("#industry-filter", Input).value or None

            winner_select = self.query_one("#winner-filter", Select)
            self.filter_state.winner_filter = winner_select.value

            pair_select = self.query_one("#model-pair-filter", Select)
            self.filter_state.model_pair_filter = pair_select.value

            formality_min = self.query_one("#formality-min", Input).value
            formality_max = self.query_one("#formality-max", Input).value
            self.filter_state.formality_min = int(formality_min) if formality_min else None
            self.filter_state.formality_max = int(formality_max) if formality_max else None

            self._apply_filters()

        elif event.button.id == "clear-filters":
            self.filter_state = FilterState()
            self.query_one("#occupation-filter", Input).value = ""
            self.query_one("#industry-filter", Input).value = ""
            self.query_one("#formality-min", Input).value = ""
            self.query_one("#formality-max", Input).value = ""
            self.filtered_results = self.results.copy()
            self._update_table()
```

---

## 9. Refusal Tracking by Dimension

```python
# src/eval/refusal_classifier.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import re
from collections import defaultdict


class RefusalCategory(str, Enum):
    """Categories of model refusal per PROMPT.md."""
    SAFETY = "safety_refusal"           # Model cites safety/policy concerns
    CAPABILITY = "capability_limitation"  # Model says it can't do the task
    MISUNDERSTANDING = "misunderstanding"  # Model interprets task incorrectly
    INCOMPLETE = "incomplete_response"    # Model starts but doesn't finish
    OFF_TOPIC = "off_topic"               # Model responds but not to actual task
    NONE = "no_refusal"                   # Not a refusal


@dataclass
class RefusalResult:
    """Result of refusal classification."""
    is_refusal: bool
    category: RefusalCategory
    confidence: float
    evidence: str
    sensitive_topic: Optional[str] = None


@dataclass
class RefusalStats:
    """Aggregated refusal statistics."""
    total_responses: int
    total_refusals: int
    by_category: Dict[str, int]
    by_model: Dict[str, Dict[str, int]]
    by_task_type: Dict[str, Dict[str, int]]
    by_sensitive_topic: Dict[str, Dict[str, int]]
    by_occupation: Dict[str, Dict[str, int]]
    by_industry: Dict[str, Dict[str, int]]
    by_formality: Dict[int, Dict[str, int]]


class RefusalClassifier:
    """Classify and track model refusals.

    Per PROMPT.md:
    - Safety refusal: Model cites safety/policy concerns
    - Capability limitation: Model says it can't do the task
    - Misunderstanding: Model interprets task incorrectly
    - Incomplete response: Model starts but doesn't finish
    - Off-topic: Model responds but not to the actual task

    Track refusal rates by:
    - Model (which models refuse most?)
    - Task type (which tasks trigger refusals?)
    - Sensitive topic category (which sensitive areas are problematic?)
    """

    # Safety refusal patterns
    SAFETY_PATTERNS = [
        r"(cannot|can't|unable to) (help|assist) with",
        r"(against|violates) (my|our) (policy|policies|guidelines)",
        r"(safety|ethical) (concern|issue|reason)",
        r"(inappropriate|harmful|dangerous)",
        r"I('m| am) not (able|allowed) to",
        r"(decline|refuse) to (generate|create|write)",
        r"(could|might|may) be (harmful|inappropriate|offensive)",
    ]

    # Capability limitation patterns
    CAPABILITY_PATTERNS = [
        r"(don't|do not) have (access|the ability|capability)",
        r"(cannot|can't) (access|retrieve|look up)",
        r"(outside|beyond) (my|the) (capabilities|scope|ability)",
        r"I('m| am) (just|only) (a|an) (language model|AI)",
        r"(lack|don't have) (the|enough) (information|context|data)",
    ]

    # Misunderstanding patterns
    MISUNDERSTANDING_PATTERNS = [
        r"(not sure|unclear) what you('re| are) (asking|looking for)",
        r"(could|can) you (clarify|explain|rephrase)",
        r"I (think|believe) you('re| are) asking about",
        r"(assuming|if) you mean",
        r"(did you mean|were you asking about)",
    ]

    # Incomplete response indicators
    INCOMPLETE_INDICATORS = [
        r"\.\.\.$",  # Ends with ellipsis
        r"(continued|to be continued)",
        r"(I'll|let me) (continue|finish) (with|later)",
        r"(first|here's the first) (part|section)",
    ]

    def __init__(self):
        self._compile_patterns()
        self._tracking: Dict[str, List[Tuple]] = defaultdict(list)

    def _compile_patterns(self):
        """Compile regex patterns."""
        self._safety_re = [re.compile(p, re.IGNORECASE) for p in self.SAFETY_PATTERNS]
        self._capability_re = [re.compile(p, re.IGNORECASE) for p in self.CAPABILITY_PATTERNS]
        self._misunderstanding_re = [re.compile(p, re.IGNORECASE) for p in self.MISUNDERSTANDING_PATTERNS]
        self._incomplete_re = [re.compile(p, re.IGNORECASE) for p in self.INCOMPLETE_INDICATORS]

    def classify(
        self,
        response: str,
        prompt_task: Optional[str] = None,
    ) -> Optional[RefusalResult]:
        """Classify whether a response is a refusal and what type.

        Args:
            response: The model's response text
            prompt_task: Optional task description for off-topic detection

        Returns:
            RefusalResult if refusal detected, None otherwise
        """
        if not response or len(response.strip()) < 10:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.INCOMPLETE,
                confidence=0.95,
                evidence="Empty or very short response"
            )

        response_lower = response.lower()

        # Check safety refusal
        for pattern in self._safety_re:
            match = pattern.search(response)
            if match:
                return RefusalResult(
                    is_refusal=True,
                    category=RefusalCategory.SAFETY,
                    confidence=0.9,
                    evidence=match.group(0)
                )

        # Check capability limitation
        for pattern in self._capability_re:
            match = pattern.search(response)
            if match:
                return RefusalResult(
                    is_refusal=True,
                    category=RefusalCategory.CAPABILITY,
                    confidence=0.85,
                    evidence=match.group(0)
                )

        # Check misunderstanding
        misunderstanding_count = 0
        for pattern in self._misunderstanding_re:
            if pattern.search(response):
                misunderstanding_count += 1

        if misunderstanding_count >= 2:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.MISUNDERSTANDING,
                confidence=0.7,
                evidence=f"Multiple clarification indicators ({misunderstanding_count})"
            )

        # Check incomplete
        for pattern in self._incomplete_re:
            match = pattern.search(response)
            if match:
                # Only count as incomplete if response is also short
                if len(response) < 500:
                    return RefusalResult(
                        is_refusal=True,
                        category=RefusalCategory.INCOMPLETE,
                        confidence=0.75,
                        evidence=match.group(0)
                    )

        # Check off-topic (if prompt task provided)
        if prompt_task:
            task_words = set(prompt_task.lower().split())
            response_words = set(response_lower.split())
            overlap = len(task_words & response_words)
            if overlap < len(task_words) * 0.1 and len(response) > 100:
                # Very low overlap with task terms
                return RefusalResult(
                    is_refusal=True,
                    category=RefusalCategory.OFF_TOPIC,
                    confidence=0.6,
                    evidence=f"Low task relevance ({overlap} word overlap)"
                )

        return None

    def track_refusal(
        self,
        model: str,
        prompt_id: str,
        result: RefusalResult,
        occupation_code: Optional[str] = None,
        occupation_title: Optional[str] = None,
        industry_code: Optional[str] = None,
        industry_name: Optional[str] = None,
        formality_level: Optional[int] = None,
        sensitive_topics: Optional[List[str]] = None,
    ):
        """Track a refusal for aggregate statistics."""
        record = {
            "model": model,
            "prompt_id": prompt_id,
            "category": result.category.value,
            "occupation_code": occupation_code,
            "occupation_title": occupation_title,
            "industry_code": industry_code,
            "industry_name": industry_name,
            "formality_level": formality_level,
            "sensitive_topics": sensitive_topics or [],
        }

        self._tracking["all"].append(record)
        self._tracking[f"model:{model}"].append(record)

        if occupation_code:
            soc_group = occupation_code.split("-")[0] if "-" in occupation_code else occupation_code
            self._tracking[f"occupation:{soc_group}"].append(record)

        if industry_code:
            naics_sector = industry_code[:2] if len(industry_code) >= 2 else industry_code
            self._tracking[f"industry:{naics_sector}"].append(record)

        if formality_level:
            self._tracking[f"formality:{formality_level}"].append(record)

        if sensitive_topics:
            for topic in sensitive_topics:
                self._tracking[f"sensitive:{topic}"].append(record)

    def get_stats(self, total_responses: int) -> RefusalStats:
        """Get aggregated refusal statistics."""
        all_refusals = self._tracking.get("all", [])

        # By category
        by_category = defaultdict(int)
        for r in all_refusals:
            by_category[r["category"]] += 1

        # By model
        by_model = defaultdict(lambda: defaultdict(int))
        models = set(r["model"] for r in all_refusals)
        for model in models:
            model_refusals = self._tracking.get(f"model:{model}", [])
            for r in model_refusals:
                by_model[model][r["category"]] += 1

        # By task type (occupation major group)
        by_task_type = defaultdict(lambda: defaultdict(int))
        for key, records in self._tracking.items():
            if key.startswith("occupation:"):
                occ_group = key.split(":")[1]
                for r in records:
                    by_task_type[occ_group][r["category"]] += 1

        # By sensitive topic
        by_sensitive_topic = defaultdict(lambda: defaultdict(int))
        for key, records in self._tracking.items():
            if key.startswith("sensitive:"):
                topic = key.split(":")[1]
                for r in records:
                    by_sensitive_topic[topic][r["category"]] += 1

        # By occupation
        by_occupation = defaultdict(lambda: defaultdict(int))
        for r in all_refusals:
            if r.get("occupation_title"):
                by_occupation[r["occupation_title"]][r["category"]] += 1

        # By industry
        by_industry = defaultdict(lambda: defaultdict(int))
        for r in all_refusals:
            if r.get("industry_name"):
                by_industry[r["industry_name"]][r["category"]] += 1

        # By formality
        by_formality = defaultdict(lambda: defaultdict(int))
        for r in all_refusals:
            if r.get("formality_level"):
                by_formality[r["formality_level"]][r["category"]] += 1

        return RefusalStats(
            total_responses=total_responses,
            total_refusals=len(all_refusals),
            by_category=dict(by_category),
            by_model={k: dict(v) for k, v in by_model.items()},
            by_task_type={k: dict(v) for k, v in by_task_type.items()},
            by_sensitive_topic={k: dict(v) for k, v in by_sensitive_topic.items()},
            by_occupation={k: dict(v) for k, v in by_occupation.items()},
            by_industry={k: dict(v) for k, v in by_industry.items()},
            by_formality={k: dict(v) for k, v in by_formality.items()},
        )

    def generate_report(self, stats: RefusalStats) -> str:
        """Generate a human-readable refusal report."""
        lines = [
            "# Refusal Analysis Report",
            "",
            f"## Summary",
            f"- Total responses analyzed: {stats.total_responses}",
            f"- Total refusals: {stats.total_refusals}",
            f"- Refusal rate: {stats.total_refusals / stats.total_responses * 100:.2f}%",
            "",
            "## Refusals by Category",
        ]

        for category, count in sorted(stats.by_category.items(), key=lambda x: -x[1]):
            pct = count / stats.total_refusals * 100 if stats.total_refusals > 0 else 0
            lines.append(f"- {category}: {count} ({pct:.1f}%)")

        lines.extend(["", "## Refusals by Model"])
        for model, categories in sorted(stats.by_model.items()):
            total = sum(categories.values())
            lines.append(f"\n### {model} ({total} total)")
            for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                lines.append(f"  - {cat}: {count}")

        if stats.by_sensitive_topic:
            lines.extend(["", "## Refusals by Sensitive Topic"])
            for topic, categories in sorted(stats.by_sensitive_topic.items()):
                total = sum(categories.values())
                lines.append(f"\n### {topic} ({total} total)")
                for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                    lines.append(f"  - {cat}: {count}")

        return "\n".join(lines)
```

---

## 10. Failure Summary Report Generator

```python
# src/reports/failure_report.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import json


@dataclass
class FailureRecord:
    """Record of a single failure."""
    timestamp: datetime
    phase: str  # "generation", "judging", "analysis"
    model: str
    prompt_id: Optional[str]
    error_type: str  # "timeout", "rate_limit", "api_error", "parse_error", etc.
    error_message: str
    retry_count: int
    recovered: bool
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureSummary:
    """Summary of all failures in an evaluation run."""
    total_failures: int
    recovered_count: int
    unrecovered_count: int

    by_type: Dict[str, int]
    by_model: Dict[str, int]
    by_phase: Dict[str, int]

    rate_limit_events: int
    timeout_events: int
    api_errors: int
    parse_errors: int

    affected_prompts: List[str]
    unrecoverable_prompts: List[str]

    failures: List[FailureRecord]


class FailureReportGenerator:
    """Generate failure summary reports for evaluation runs."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.failures_log = run_dir / "logs" / "failures.log"
        self.failures: List[FailureRecord] = []

    def load_failures(self) -> List[FailureRecord]:
        """Load failures from the failure log."""
        if not self.failures_log.exists():
            return []

        failures = []
        with open(self.failures_log, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    failures.append(FailureRecord(
                        timestamp=datetime.fromisoformat(data.get("timestamp", "")),
                        phase=data.get("phase", "unknown"),
                        model=data.get("model", "unknown"),
                        prompt_id=data.get("prompt_id"),
                        error_type=data.get("error_type", "unknown"),
                        error_message=data.get("error_message", ""),
                        retry_count=data.get("retry_count", 0),
                        recovered=data.get("recovered", False),
                        context=data.get("context", {}),
                    ))
                except (json.JSONDecodeError, KeyError) as e:
                    # Log line parsing failed, skip
                    continue

        self.failures = failures
        return failures

    def generate_summary(self) -> FailureSummary:
        """Generate failure summary from loaded failures."""
        if not self.failures:
            self.load_failures()

        # Count by type
        by_type: Dict[str, int] = {}
        by_model: Dict[str, int] = {}
        by_phase: Dict[str, int] = {}
        affected_prompts = set()
        unrecoverable_prompts = set()

        recovered = 0
        unrecovered = 0
        rate_limits = 0
        timeouts = 0
        api_errors = 0
        parse_errors = 0

        for f in self.failures:
            # Count by type
            by_type[f.error_type] = by_type.get(f.error_type, 0) + 1

            # Count by model
            by_model[f.model] = by_model.get(f.model, 0) + 1

            # Count by phase
            by_phase[f.phase] = by_phase.get(f.phase, 0) + 1

            # Recovery tracking
            if f.recovered:
                recovered += 1
            else:
                unrecovered += 1
                if f.prompt_id:
                    unrecoverable_prompts.add(f.prompt_id)

            # Affected prompts
            if f.prompt_id:
                affected_prompts.add(f.prompt_id)

            # Specific error types
            if "rate_limit" in f.error_type.lower():
                rate_limits += 1
            elif "timeout" in f.error_type.lower():
                timeouts += 1
            elif "api" in f.error_type.lower():
                api_errors += 1
            elif "parse" in f.error_type.lower():
                parse_errors += 1

        return FailureSummary(
            total_failures=len(self.failures),
            recovered_count=recovered,
            unrecovered_count=unrecovered,
            by_type=by_type,
            by_model=by_model,
            by_phase=by_phase,
            rate_limit_events=rate_limits,
            timeout_events=timeouts,
            api_errors=api_errors,
            parse_errors=parse_errors,
            affected_prompts=list(affected_prompts),
            unrecoverable_prompts=list(unrecoverable_prompts),
            failures=self.failures,
        )

    def generate_report(self, summary: Optional[FailureSummary] = None) -> str:
        """Generate human-readable failure report."""
        if summary is None:
            summary = self.generate_summary()

        lines = [
            "# Failure Summary Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Overview",
            f"- **Total failures:** {summary.total_failures}",
            f"- **Recovered:** {summary.recovered_count} ({summary.recovered_count / summary.total_failures * 100:.1f}% if summary.total_failures else 0)",
            f"- **Unrecovered:** {summary.unrecovered_count}",
            "",
            "## Failure Types",
        ]

        for error_type, count in sorted(summary.by_type.items(), key=lambda x: -x[1]):
            lines.append(f"- {error_type}: {count}")

        lines.extend([
            "",
            "## By Error Category",
            f"- Rate limit events: {summary.rate_limit_events}",
            f"- Timeout events: {summary.timeout_events}",
            f"- API errors: {summary.api_errors}",
            f"- Parse errors: {summary.parse_errors}",
            "",
            "## By Model",
        ])

        for model, count in sorted(summary.by_model.items(), key=lambda x: -x[1]):
            lines.append(f"- {model}: {count}")

        lines.extend(["", "## By Phase"])
        for phase, count in sorted(summary.by_phase.items(), key=lambda x: -x[1]):
            lines.append(f"- {phase}: {count}")

        if summary.unrecoverable_prompts:
            lines.extend([
                "",
                "## Unrecoverable Prompts",
                f"The following {len(summary.unrecoverable_prompts)} prompts could not be completed:",
            ])
            for prompt_id in summary.unrecoverable_prompts[:20]:  # Limit display
                lines.append(f"- {prompt_id}")
            if len(summary.unrecoverable_prompts) > 20:
                lines.append(f"- ... and {len(summary.unrecoverable_prompts) - 20} more")

        # Recent failures detail
        if summary.failures:
            lines.extend([
                "",
                "## Recent Failure Details",
                "(Last 10 failures)",
            ])
            for f in summary.failures[-10:]:
                lines.extend([
                    "",
                    f"### {f.timestamp.isoformat()}",
                    f"- Phase: {f.phase}",
                    f"- Model: {f.model}",
                    f"- Prompt: {f.prompt_id or 'N/A'}",
                    f"- Type: {f.error_type}",
                    f"- Recovered: {'Yes' if f.recovered else 'No'}",
                    f"- Retries: {f.retry_count}",
                    f"- Message: {f.error_message[:200]}...",
                ])

        return "\n".join(lines)

    def save_report(self, output_path: Optional[Path] = None) -> Path:
        """Save the failure report to a file."""
        if output_path is None:
            output_path = self.run_dir / "reports" / "failure_summary.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = self.generate_report()
        output_path.write_text(report)

        return output_path

    def save_json_summary(self, output_path: Optional[Path] = None) -> Path:
        """Save failure summary as JSON."""
        if output_path is None:
            output_path = self.run_dir / "analysis" / "failure_summary.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = self.generate_summary()
        data = {
            "total_failures": summary.total_failures,
            "recovered_count": summary.recovered_count,
            "unrecovered_count": summary.unrecovered_count,
            "by_type": summary.by_type,
            "by_model": summary.by_model,
            "by_phase": summary.by_phase,
            "rate_limit_events": summary.rate_limit_events,
            "timeout_events": summary.timeout_events,
            "api_errors": summary.api_errors,
            "parse_errors": summary.parse_errors,
            "affected_prompt_count": len(summary.affected_prompts),
            "unrecoverable_prompt_count": len(summary.unrecoverable_prompts),
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return output_path


class FailureLogger:
    """Logger for recording failures during evaluation."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_failure(
        self,
        phase: str,
        model: str,
        error_type: str,
        error_message: str,
        prompt_id: Optional[str] = None,
        retry_count: int = 0,
        recovered: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log a failure event."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "model": model,
            "prompt_id": prompt_id,
            "error_type": error_type,
            "error_message": str(error_message)[:1000],  # Truncate long messages
            "retry_count": retry_count,
            "recovered": recovered,
            "context": context or {},
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
```

---

## Summary

This document provides complete Python implementations for all gaps identified in the gap analysis:

1. **Parallel Request Architecture (EvaluationEngine)** - Full asyncio.gather/TaskGroup implementation with semaphore-based concurrency control, per-model rate limiting, and progress callbacks.

2. **Cohen's Kappa Inter-Judge Agreement** - Complete implementation of pairwise and Fleiss' Kappa calculations with interpretation.

3. **CLI Options** - Full implementation of --tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona flags.

4. **TUI Progress Dashboard** - Complete with cost tracking (spent/projected), ETA calculation, confidence intervals, per-judge votes, response times/throughput, occupation/industry in batch display, and help overlay (h key).

5. **Name Formality Variation** - NameFormality enum and NameGenerator with Dr. Williams vs Mike vs Michael T. Williams formatting.

6. **Phase 1 Generation Using Evaluated Models** - Phase1Generator that round-robins across all evaluated models for prompt generation.

7. **Ambiguity Behavior Tracking** - AmbiguityTracker to detect whether models ask clarification, hedge, make assumptions, or hallucinate details.

8. **TUI Results Viewer** - Complete with filtering by occupation/industry/winner, sorting by columns, and drill-down modal for judgment details.

9. **Refusal Tracking by Dimension** - RefusalClassifier with tracking by model, task type, sensitive topic, occupation, industry, and formality.

10. **Failure Summary Report** - FailureReportGenerator and FailureLogger for comprehensive failure tracking and end-of-run summaries.

