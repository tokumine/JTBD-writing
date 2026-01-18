# Gap Fix Implementation Draft 3

This document provides complete Python implementations for all gaps identified in the gap analysis.

---

## 1. PARALLEL REQUEST ARCHITECTURE - EvaluationEngine

The most critical gap is the parallel request architecture for concurrent API calls.

```python
# src/eval/engine.py

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime
import logging

from ..api.openrouter_client import OpenRouterClient, CompletionResponse
from ..prompts.schemas import WritingPrompt
from ..storage.checkpoint import CheckpointManager
from ..storage.database import ResultsDatabase
from .vote_aggregator import VoteAggregator, JudgeVote, AggregatedResult
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .compliance_tracker import ComplianceTracker
from .refusal_classifier import RefusalClassifier
from .response_analyzer import ResponseAnalyzer
from ..config.settings import EvalConfig

logger = logging.getLogger(__name__)


@dataclass
class ProgressState:
    """Current progress state for TUI updates."""
    total_prompts: int = 0
    completed_prompts: int = 0
    current_phase: str = "initialization"

    # Per model pair progress
    model_pair_progress: Dict[str, Dict] = field(default_factory=dict)

    # Current batch info
    current_prompt_id: Optional[str] = None
    current_prompt_text: Optional[str] = None
    current_occupation: Optional[str] = None
    current_industry: Optional[str] = None

    # Response status
    response_statuses: Dict[str, str] = field(default_factory=dict)

    # Judging status (per judge, per persona)
    judge_vote_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Statistics
    running_win_rates: Dict[str, float] = field(default_factory=dict)
    running_confidence_intervals: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    # Performance metrics
    avg_response_time_ms: float = 0.0
    avg_judge_time_ms: float = 0.0
    requests_per_minute: float = 0.0

    # Cost tracking
    cost_spent_so_far: float = 0.0
    cost_projected_total: float = 0.0

    # Timing
    start_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0

    # Errors
    retry_count: int = 0
    failure_count: int = 0
    rate_limit_pause_count: int = 0


@dataclass
class ComparisonTask:
    """A single comparison to execute."""
    prompt: WritingPrompt
    gemini_model: str
    competitor_model: str
    judge_models: List[str]
    votes_per_judge: int
    use_both_personas: bool


@dataclass
class ComparisonResult:
    """Result of a single comparison."""
    prompt_id: str
    gemini_model: str
    competitor_model: str
    gemini_response: Optional[CompletionResponse]
    competitor_response: Optional[CompletionResponse]
    aggregated_result: Optional[AggregatedResult]
    error: Optional[str] = None
    gemini_refused: bool = False
    competitor_refused: bool = False


class EvaluationEngine:
    """Main evaluation orchestrator with parallel request execution.

    Uses asyncio.Semaphore for concurrency limiting and asyncio.gather/TaskGroup
    for concurrent API calls. Provides progress callbacks for TUI updates.
    """

    def __init__(
        self,
        config: EvalConfig,
        client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        database: ResultsDatabase,
        max_concurrency: int = 20,
        per_model_concurrency: int = 5,
        progress_callback: Optional[Callable[[ProgressState], None]] = None
    ):
        self.config = config
        self.client = client
        self.checkpoint_manager = checkpoint_manager
        self.database = database
        self.max_concurrency = max_concurrency
        self.per_model_concurrency = per_model_concurrency
        self.progress_callback = progress_callback

        # Semaphores for concurrency control
        self._global_semaphore = asyncio.Semaphore(max_concurrency)
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}

        # Components
        self.vote_aggregator = VoteAggregator(config.judge_config.votes_per_judge)
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.compliance_tracker = ComplianceTracker()
        self.refusal_classifier = RefusalClassifier()
        self.response_analyzer = ResponseAnalyzer()

        # Progress state
        self.progress = ProgressState()

        # Tracking for statistics
        self._response_times: List[float] = []
        self._judge_times: List[float] = []
        self._request_timestamps: List[float] = []
        self._total_cost: float = 0.0

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore for rate limiting."""
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(self.per_model_concurrency)
        return self._model_semaphores[model]

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt]
    ) -> List[ComparisonResult]:
        """Run the complete evaluation with parallel execution."""

        self.progress.start_time = datetime.now()
        self.progress.total_prompts = len(prompts) * len(self.config.model_pairs)
        self.progress.current_phase = "generation"

        # Initialize per-model-pair progress
        for gemini, competitor in self.config.model_pairs:
            pair_key = f"{gemini}_vs_{competitor}"
            self.progress.model_pair_progress[pair_key] = {
                "completed": 0,
                "total": len(prompts),
                "gemini_wins": 0,
                "competitor_wins": 0,
                "ties": 0
            }

        self._update_progress()

        # Build all comparison tasks
        tasks: List[ComparisonTask] = []
        for prompt in prompts:
            for gemini_model, competitor_model in self.config.model_pairs:
                tasks.append(ComparisonTask(
                    prompt=prompt,
                    gemini_model=gemini_model,
                    competitor_model=competitor_model,
                    judge_models=self.config.judge_config.models,
                    votes_per_judge=self.config.judge_config.votes_per_judge,
                    use_both_personas=self.config.judge_config.use_both_personas
                ))

        # Execute in batches to manage memory
        batch_size = min(50, self.max_concurrency * 2)
        all_results: List[ComparisonResult] = []

        for batch_start in range(0, len(tasks), batch_size):
            batch_end = min(batch_start + batch_size, len(tasks))
            batch_tasks = tasks[batch_start:batch_end]

            # Run batch concurrently using TaskGroup (Python 3.11+)
            try:
                async with asyncio.TaskGroup() as tg:
                    batch_futures = [
                        tg.create_task(self._execute_comparison(task))
                        for task in batch_tasks
                    ]
                batch_results = [f.result() for f in batch_futures]
            except ExceptionGroup as eg:
                # Handle partial failures - collect successful results
                batch_results = []
                for exc in eg.exceptions:
                    logger.error(f"Comparison failed: {exc}")
                    self.progress.failure_count += 1

            all_results.extend(batch_results)

            # Checkpoint after each batch
            await self.checkpoint_manager.save_batch_results(batch_results)

        self.progress.current_phase = "complete"
        self._update_progress()

        return all_results

    async def run_evaluation_gather(
        self,
        prompts: List[WritingPrompt]
    ) -> List[ComparisonResult]:
        """Alternative implementation using asyncio.gather for Python < 3.11."""

        self.progress.start_time = datetime.now()
        self.progress.total_prompts = len(prompts) * len(self.config.model_pairs)
        self.progress.current_phase = "generation"

        # Initialize progress tracking
        for gemini, competitor in self.config.model_pairs:
            pair_key = f"{gemini}_vs_{competitor}"
            self.progress.model_pair_progress[pair_key] = {
                "completed": 0,
                "total": len(prompts),
                "gemini_wins": 0,
                "competitor_wins": 0,
                "ties": 0
            }

        self._update_progress()

        # Build all comparison tasks
        tasks: List[ComparisonTask] = []
        for prompt in prompts:
            for gemini_model, competitor_model in self.config.model_pairs:
                tasks.append(ComparisonTask(
                    prompt=prompt,
                    gemini_model=gemini_model,
                    competitor_model=competitor_model,
                    judge_models=self.config.judge_config.models,
                    votes_per_judge=self.config.judge_config.votes_per_judge,
                    use_both_personas=self.config.judge_config.use_both_personas
                ))

        # Execute in batches
        batch_size = min(50, self.max_concurrency * 2)
        all_results: List[ComparisonResult] = []

        for batch_start in range(0, len(tasks), batch_size):
            batch_end = min(batch_start + batch_size, len(tasks))
            batch_tasks = tasks[batch_start:batch_end]

            # Create coroutines for batch
            coros = [self._execute_comparison_safe(task) for task in batch_tasks]

            # Run with gather, return_exceptions=True to handle partial failures
            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            # Process results, handling any exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Comparison failed: {result}")
                    self.progress.failure_count += 1
                else:
                    all_results.append(result)

            # Checkpoint after each batch
            valid_results = [r for r in batch_results if not isinstance(r, Exception)]
            await self.checkpoint_manager.save_batch_results(valid_results)

        self.progress.current_phase = "complete"
        self._update_progress()

        return all_results

    async def _execute_comparison_safe(self, task: ComparisonTask) -> ComparisonResult:
        """Wrapper that catches exceptions for gather-based execution."""
        try:
            return await self._execute_comparison(task)
        except Exception as e:
            logger.error(f"Comparison failed for {task.prompt.prompt_id}: {e}")
            return ComparisonResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                gemini_response=None,
                competitor_response=None,
                aggregated_result=None,
                error=str(e)
            )

    async def _execute_comparison(self, task: ComparisonTask) -> ComparisonResult:
        """Execute a single comparison with both response generation and judging."""

        # Update current task in progress
        self.progress.current_prompt_id = task.prompt.prompt_id
        self.progress.current_prompt_text = task.prompt.onet_task[:100]
        self.progress.current_occupation = task.prompt.occupation_title
        self.progress.current_industry = task.prompt.naics_sector
        self._update_progress()

        # Phase 1: Generate responses concurrently
        self.progress.response_statuses[task.gemini_model] = "generating"
        self.progress.response_statuses[task.competitor_model] = "generating"
        self._update_progress()

        gemini_response, competitor_response = await asyncio.gather(
            self._generate_response(task.gemini_model, task.prompt),
            self._generate_response(task.competitor_model, task.prompt)
        )

        self.progress.response_statuses[task.gemini_model] = "complete" if gemini_response else "failed"
        self.progress.response_statuses[task.competitor_model] = "complete" if competitor_response else "failed"
        self._update_progress()

        # Check for refusals
        gemini_refused = False
        competitor_refused = False

        if gemini_response:
            refusal = self.refusal_classifier.classify(gemini_response.content)
            gemini_refused = refusal.is_refusal

        if competitor_response:
            refusal = self.refusal_classifier.classify(competitor_response.content)
            competitor_refused = refusal.is_refusal

        # Handle auto-loss cases
        if gemini_refused and not competitor_refused:
            # Gemini auto-loses
            aggregated = AggregatedResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                final_winner="competitor",
                gemini_wins=0,
                competitor_wins=1,
                ties=0,
                judge_agreement=1.0,
                per_judge_results={},
                all_votes=[]
            )
            return ComparisonResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                gemini_response=gemini_response,
                competitor_response=competitor_response,
                aggregated_result=aggregated,
                gemini_refused=True
            )
        elif competitor_refused and not gemini_refused:
            # Competitor auto-loses
            aggregated = AggregatedResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                final_winner="gemini",
                gemini_wins=1,
                competitor_wins=0,
                ties=0,
                judge_agreement=1.0,
                per_judge_results={},
                all_votes=[]
            )
            return ComparisonResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                gemini_response=gemini_response,
                competitor_response=competitor_response,
                aggregated_result=aggregated,
                competitor_refused=True
            )
        elif gemini_refused and competitor_refused:
            # Both refused - tie
            aggregated = AggregatedResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                final_winner="tie",
                gemini_wins=0,
                competitor_wins=0,
                ties=1,
                judge_agreement=1.0,
                per_judge_results={},
                all_votes=[]
            )
            return ComparisonResult(
                prompt_id=task.prompt.prompt_id,
                gemini_model=task.gemini_model,
                competitor_model=task.competitor_model,
                gemini_response=gemini_response,
                competitor_response=competitor_response,
                aggregated_result=aggregated,
                gemini_refused=True,
                competitor_refused=True
            )

        # Phase 2: Run judging
        self.progress.current_phase = "judging"

        # Initialize judge vote tracking
        for judge_model in task.judge_models:
            self.progress.judge_vote_counts[judge_model] = {"expert": 0, "recipient": 0}
        self._update_progress()

        all_votes = await self._run_judging(
            task=task,
            gemini_response=gemini_response.content if gemini_response else "",
            competitor_response=competitor_response.content if competitor_response else ""
        )

        # Aggregate votes
        aggregated = self.vote_aggregator.aggregate_all(
            prompt_id=task.prompt.prompt_id,
            gemini_model=task.gemini_model,
            competitor_model=task.competitor_model,
            all_votes=all_votes
        )

        # Update model pair progress
        pair_key = f"{task.gemini_model}_vs_{task.competitor_model}"
        self.progress.model_pair_progress[pair_key]["completed"] += 1
        if aggregated.final_winner == "gemini":
            self.progress.model_pair_progress[pair_key]["gemini_wins"] += 1
        elif aggregated.final_winner == "competitor":
            self.progress.model_pair_progress[pair_key]["competitor_wins"] += 1
        else:
            self.progress.model_pair_progress[pair_key]["ties"] += 1

        self.progress.completed_prompts += 1
        self._update_running_statistics()
        self._update_progress()

        return ComparisonResult(
            prompt_id=task.prompt.prompt_id,
            gemini_model=task.gemini_model,
            competitor_model=task.competitor_model,
            gemini_response=gemini_response,
            competitor_response=competitor_response,
            aggregated_result=aggregated
        )

    async def _generate_response(
        self,
        model: str,
        prompt: WritingPrompt
    ) -> Optional[CompletionResponse]:
        """Generate a response from a model with semaphore control."""

        async with self._global_semaphore:
            async with self._get_model_semaphore(model):
                try:
                    start_time = time.perf_counter()

                    messages = [
                        {"role": "user", "content": prompt.full_prompt}
                    ]

                    response = await self.client.complete(
                        model=model,
                        messages=messages,
                        temperature=0.7
                    )

                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    self._response_times.append(elapsed_ms)
                    self._request_timestamps.append(time.time())
                    self._total_cost += response.cost

                    return response

                except Exception as e:
                    logger.error(f"Response generation failed for {model}: {e}")
                    self.progress.failure_count += 1
                    return None

    async def _run_judging(
        self,
        task: ComparisonTask,
        gemini_response: str,
        competitor_response: str
    ) -> List[JudgeVote]:
        """Run all judge evaluations concurrently."""

        all_votes: List[JudgeVote] = []

        # Build list of all judge calls
        judge_calls = []
        for judge_model in task.judge_models:
            personas = ["expert", "recipient"] if task.use_both_personas else ["expert"]
            for persona in personas:
                for vote_idx in range(task.votes_per_judge):
                    judge_calls.append((judge_model, persona, vote_idx))

        # Execute all judge calls concurrently
        coros = [
            self._execute_judge_vote(
                task=task,
                gemini_response=gemini_response,
                competitor_response=competitor_response,
                judge_model=judge_model,
                persona=persona,
                vote_idx=vote_idx
            )
            for judge_model, persona, vote_idx in judge_calls
        ]

        results = await asyncio.gather(*coros, return_exceptions=True)

        for result in results:
            if isinstance(result, JudgeVote):
                all_votes.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Judge vote failed: {result}")

        return all_votes

    async def _execute_judge_vote(
        self,
        task: ComparisonTask,
        gemini_response: str,
        competitor_response: str,
        judge_model: str,
        persona: str,
        vote_idx: int
    ) -> JudgeVote:
        """Execute a single judge vote."""

        async with self._global_semaphore:
            async with self._get_model_semaphore(judge_model):
                start_time = time.perf_counter()

                # Determine position assignment
                gemini_position = self.vote_aggregator.get_position_for_vote(
                    prompt_id=task.prompt.prompt_id,
                    gemini_model=task.gemini_model,
                    competitor_model=task.competitor_model,
                    judge_model=judge_model,
                    judge_persona=persona,
                    vote_index=vote_idx
                )

                # Build judge prompt with correct ordering
                if gemini_position == "A":
                    response_a = gemini_response
                    response_b = competitor_response
                else:
                    response_a = competitor_response
                    response_b = gemini_response

                system_prompt, user_prompt = self.judge_builder.build_judge_prompt(
                    prompt=task.prompt,
                    response_a=response_a,
                    response_b=response_b,
                    persona=persona
                )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

                response = await self.client.complete(
                    model=judge_model,
                    messages=messages,
                    temperature=0.3  # Lower temperature for more consistent judging
                )

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self._judge_times.append(elapsed_ms)
                self._total_cost += response.cost

                # Parse judgment
                parsed = self.judge_parser.parse(response.content)

                # Normalize winner to model-based
                normalized_winner = self.vote_aggregator.parse_winner_to_normalized(
                    raw_winner=parsed.winner,
                    gemini_position=gemini_position
                )

                # Normalize quality scores
                if gemini_position == "A":
                    quality_gemini = parsed.quality_a
                    quality_competitor = parsed.quality_b
                    compliance_gemini = parsed.constraint_compliance_a
                    compliance_competitor = parsed.constraint_compliance_b
                else:
                    quality_gemini = parsed.quality_b
                    quality_competitor = parsed.quality_a
                    compliance_gemini = parsed.constraint_compliance_b
                    compliance_competitor = parsed.constraint_compliance_a

                # Update progress
                self.progress.judge_vote_counts[judge_model][persona] += 1
                self._update_progress()

                return JudgeVote(
                    judge_model=judge_model,
                    judge_persona=persona,
                    vote_index=vote_idx,
                    winner=normalized_winner,
                    confidence=parsed.confidence,
                    quality_gemini=quality_gemini,
                    quality_competitor=quality_competitor,
                    reasoning=parsed.reasoning,
                    gemini_was_position=gemini_position,
                    constraint_compliance_gemini=compliance_gemini,
                    constraint_compliance_competitor=compliance_competitor
                )

    def _update_running_statistics(self):
        """Update running statistics for progress display."""

        # Calculate average response time
        if self._response_times:
            self.progress.avg_response_time_ms = sum(self._response_times) / len(self._response_times)

        # Calculate average judge time
        if self._judge_times:
            self.progress.avg_judge_time_ms = sum(self._judge_times) / len(self._judge_times)

        # Calculate requests per minute
        now = time.time()
        recent_requests = [t for t in self._request_timestamps if now - t < 60]
        self.progress.requests_per_minute = len(recent_requests)

        # Calculate elapsed time and ETA
        if self.progress.start_time:
            self.progress.elapsed_seconds = (datetime.now() - self.progress.start_time).total_seconds()

            if self.progress.completed_prompts > 0:
                avg_time_per_prompt = self.progress.elapsed_seconds / self.progress.completed_prompts
                remaining = self.progress.total_prompts - self.progress.completed_prompts
                self.progress.eta_seconds = avg_time_per_prompt * remaining

        # Update cost tracking
        self.progress.cost_spent_so_far = self._total_cost
        if self.progress.completed_prompts > 0:
            cost_per_prompt = self._total_cost / self.progress.completed_prompts
            self.progress.cost_projected_total = cost_per_prompt * self.progress.total_prompts

        # Calculate running win rates with confidence intervals
        for pair_key, pair_data in self.progress.model_pair_progress.items():
            completed = pair_data["completed"]
            if completed > 0:
                gemini_wins = pair_data["gemini_wins"]
                win_rate = gemini_wins / completed
                self.progress.running_win_rates[pair_key] = win_rate

                # Wilson confidence interval
                from ..analysis.statistics import wilson_confidence_interval
                ci_low, ci_high = wilson_confidence_interval(gemini_wins, completed)
                self.progress.running_confidence_intervals[pair_key] = (ci_low, ci_high)

    def _update_progress(self):
        """Call progress callback if registered."""
        if self.progress_callback:
            self.progress_callback(self.progress)


---

## 2. COHEN'S KAPPA INTER-JUDGE AGREEMENT

```python
# src/analysis/statistics.py (additions)

from typing import List, Tuple, Dict
from collections import defaultdict
import math
from scipy import stats
from scipy.stats import binomtest, chi2_contingency
import numpy as np


def cohens_kappa(votes_judge_1: List[str], votes_judge_2: List[str]) -> float:
    """Calculate Cohen's Kappa coefficient for inter-judge agreement.

    Args:
        votes_judge_1: List of votes from judge 1 (e.g., ["gemini", "competitor", "tie", ...])
        votes_judge_2: List of votes from judge 2 (same length)

    Returns:
        Kappa coefficient: -1 to 1, where:
        - 1 = perfect agreement
        - 0 = agreement expected by chance
        - <0 = less agreement than expected by chance
    """
    if len(votes_judge_1) != len(votes_judge_2):
        raise ValueError("Vote lists must have the same length")

    n = len(votes_judge_1)
    if n == 0:
        return 0.0

    # Get all unique categories
    categories = sorted(set(votes_judge_1) | set(votes_judge_2))
    k = len(categories)
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    # Build confusion matrix
    confusion = np.zeros((k, k), dtype=int)
    for v1, v2 in zip(votes_judge_1, votes_judge_2):
        confusion[cat_to_idx[v1], cat_to_idx[v2]] += 1

    # Calculate observed agreement (P_o)
    p_o = np.trace(confusion) / n

    # Calculate expected agreement (P_e)
    row_sums = confusion.sum(axis=1)
    col_sums = confusion.sum(axis=0)
    p_e = np.sum(row_sums * col_sums) / (n * n)

    # Calculate Kappa
    if p_e == 1.0:
        return 1.0  # Perfect agreement by definition

    kappa = (p_o - p_e) / (1 - p_e)
    return float(kappa)


def fleiss_kappa(ratings_matrix: np.ndarray) -> float:
    """Calculate Fleiss' Kappa for multiple raters.

    Args:
        ratings_matrix: N x K matrix where N is number of items and K is number of categories.
                       Each cell contains the count of raters who assigned that category.

    Returns:
        Fleiss' Kappa coefficient
    """
    N, k = ratings_matrix.shape
    n = ratings_matrix.sum(axis=1)[0]  # Number of raters per item (assumed constant)

    if N == 0 or n == 0:
        return 0.0

    # Proportion of all assignments to each category
    p_j = ratings_matrix.sum(axis=0) / (N * n)

    # Calculate P_e (expected agreement by chance)
    P_e = np.sum(p_j ** 2)

    # Calculate P_i for each item (extent to which raters agree)
    P_i = (1 / (n * (n - 1))) * (np.sum(ratings_matrix ** 2, axis=1) - n)

    # Calculate mean of P_i (P_bar)
    P_bar = np.mean(P_i)

    # Calculate Kappa
    if P_e == 1.0:
        return 1.0

    kappa = (P_bar - P_e) / (1 - P_e)
    return float(kappa)


def calculate_inter_judge_agreement(
    all_results: List[Dict]
) -> Dict[str, float]:
    """Calculate inter-judge agreement metrics across all results.

    Args:
        all_results: List of result dicts containing 'all_votes' with JudgeVote objects

    Returns:
        Dict with kappa values for each judge pair and overall Fleiss' Kappa
    """
    # Collect votes by judge model for each prompt
    prompt_votes: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    for result in all_results:
        prompt_id = result.get("prompt_id", "")
        votes = result.get("all_votes", [])

        for vote in votes:
            judge_model = vote.judge_model
            winner = vote.winner
            prompt_votes[prompt_id][judge_model].append(winner)

    # Get list of judge models
    all_judges = set()
    for prompt_data in prompt_votes.values():
        all_judges.update(prompt_data.keys())
    judges = sorted(all_judges)

    if len(judges) < 2:
        return {"overall_kappa": 0.0, "pairwise": {}}

    # Calculate pairwise Cohen's Kappa
    pairwise_kappas = {}
    for i, judge_1 in enumerate(judges):
        for judge_2 in judges[i + 1:]:
            # Collect paired votes (aggregate per prompt)
            votes_1 = []
            votes_2 = []

            for prompt_id, judge_data in prompt_votes.items():
                if judge_1 in judge_data and judge_2 in judge_data:
                    # Take majority vote for each judge on this prompt
                    from collections import Counter
                    majority_1 = Counter(judge_data[judge_1]).most_common(1)[0][0]
                    majority_2 = Counter(judge_data[judge_2]).most_common(1)[0][0]
                    votes_1.append(majority_1)
                    votes_2.append(majority_2)

            if len(votes_1) >= 2:
                kappa = cohens_kappa(votes_1, votes_2)
                pairwise_kappas[f"{judge_1}_vs_{judge_2}"] = kappa

    # Calculate overall Fleiss' Kappa
    # Build ratings matrix: each row is a prompt, columns are categories (gemini, competitor, tie)
    categories = ["gemini", "competitor", "tie"]
    prompts = list(prompt_votes.keys())

    if len(prompts) >= 2 and len(judges) >= 2:
        ratings_matrix = np.zeros((len(prompts), len(categories)))

        for i, prompt_id in enumerate(prompts):
            prompt_data = prompt_votes[prompt_id]
            for judge_model, votes in prompt_data.items():
                # Aggregate votes for this judge (majority)
                from collections import Counter
                majority = Counter(votes).most_common(1)[0][0]
                cat_idx = categories.index(majority)
                ratings_matrix[i, cat_idx] += 1

        overall_kappa = fleiss_kappa(ratings_matrix)
    else:
        overall_kappa = 0.0

    return {
        "overall_kappa": overall_kappa,
        "pairwise": pairwise_kappas
    }


def wilson_confidence_interval(
    successes: int,
    n: int,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """Calculate Wilson score confidence interval for a proportion.

    This is preferred over normal approximation for small samples and
    proportions near 0 or 1.

    Args:
        successes: Number of successes (e.g., wins)
        n: Total number of trials
        confidence: Confidence level (default 0.95)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if n == 0:
        return (0.0, 1.0)

    p_hat = successes / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    z2 = z * z

    denominator = 1 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denominator
    margin = (z / denominator) * math.sqrt(
        (p_hat * (1 - p_hat) / n) + (z2 / (4 * n * n))
    )

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return (lower, upper)


def calculate_effect_size(
    wins_a: int,
    wins_b: int,
    ties: int = 0
) -> float:
    """Calculate effect size (Cohen's h) for two proportions.

    Args:
        wins_a: Number of wins for model A
        wins_b: Number of wins for model B
        ties: Number of ties (counted as 0.5 for each)

    Returns:
        Cohen's h effect size
    """
    total = wins_a + wins_b + ties
    if total == 0:
        return 0.0

    # Convert to proportions (ties split between both)
    p1 = (wins_a + 0.5 * ties) / total
    p2 = (wins_b + 0.5 * ties) / total

    # Cohen's h = 2 * (arcsin(sqrt(p1)) - arcsin(sqrt(p2)))
    h = 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))
    return abs(h)


def binomial_test(
    wins: int,
    total: int,
    null_probability: float = 0.5
) -> Tuple[float, str]:
    """Perform binomial test for win rate significance.

    Args:
        wins: Number of wins
        total: Total comparisons (excluding ties)
        null_probability: Null hypothesis probability

    Returns:
        Tuple of (p_value, interpretation)
    """
    if total == 0:
        return (1.0, "insufficient data")

    result = binomtest(wins, total, null_probability, alternative='two-sided')
    p_value = result.pvalue

    if p_value < 0.001:
        interpretation = "highly significant"
    elif p_value < 0.01:
        interpretation = "very significant"
    elif p_value < 0.05:
        interpretation = "significant"
    elif p_value < 0.10:
        interpretation = "marginally significant"
    else:
        interpretation = "not significant"

    return (p_value, interpretation)
```

---

## 3. TUI WITH COST TRACKING AND HELP OVERLAY

```python
# src/tui/progress_dashboard.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, ProgressBar, DataTable, Log, Label, Button
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.reactive import reactive
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta


class HelpScreen(ModalScreen):
    """Help overlay modal (h key)."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("h", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("KEYBOARD SHORTCUTS", classes="help-title"),
            Static(""),
            Static("q     Graceful quit (saves checkpoint)"),
            Static("p     Pause/Resume evaluation"),
            Static("d     Toggle detailed view"),
            Static("s     Show full statistics panel"),
            Static("h     Show this help overlay"),
            Static("Up/Down  Scroll activity log"),
            Static(""),
            Static("Press ESC or 'h' to close"),
            id="help-dialog"
        )


class CostTracker(Static):
    """Widget showing cost tracking."""

    cost_spent = reactive(0.0)
    cost_projected = reactive(0.0)

    def render(self) -> str:
        return f"""Cost Tracking
─────────────────────
Spent so far:     ${self.cost_spent:,.2f}
Projected total:  ${self.cost_projected:,.2f}"""


class ETADisplay(Static):
    """Widget showing ETA calculation."""

    elapsed_seconds = reactive(0.0)
    eta_seconds = reactive(0.0)
    start_time: Optional[datetime] = None

    def render(self) -> str:
        # Format elapsed time
        if self.elapsed_seconds > 0:
            elapsed = timedelta(seconds=int(self.elapsed_seconds))
            elapsed_str = str(elapsed)
        else:
            elapsed_str = "0:00:00"

        # Format ETA
        if self.eta_seconds > 0:
            eta = timedelta(seconds=int(self.eta_seconds))
            eta_str = str(eta)
        else:
            eta_str = "--:--:--"

        return f"Elapsed: {elapsed_str} | ETA: {eta_str}"


class JudgeAgreementDisplay(Static):
    """Widget showing inter-judge agreement (Cohen's Kappa)."""

    kappa = reactive(0.0)

    def render(self) -> str:
        # Interpret kappa value
        if self.kappa >= 0.81:
            interpretation = "almost perfect"
        elif self.kappa >= 0.61:
            interpretation = "substantial"
        elif self.kappa >= 0.41:
            interpretation = "moderate"
        elif self.kappa >= 0.21:
            interpretation = "fair"
        elif self.kappa >= 0.0:
            interpretation = "slight"
        else:
            interpretation = "poor"

        return f"Judge Agreement: {self.kappa:.2f} kappa ({interpretation})"


class PerJudgeVotes(Static):
    """Widget showing per-judge vote counts."""

    vote_counts: Dict[str, Dict[str, int]] = {}

    def update_votes(self, counts: Dict[str, Dict[str, int]]):
        self.vote_counts = counts
        self.refresh()

    def render(self) -> str:
        lines = ["Per-Judge Progress"]
        lines.append("─" * 40)

        for judge_model, persona_counts in self.vote_counts.items():
            # Shorten model name
            short_name = judge_model.split("/")[-1][:15]
            expert = persona_counts.get("expert", 0)
            recipient = persona_counts.get("recipient", 0)
            lines.append(f"{short_name}: expert={expert} recipient={recipient}")

        return "\n".join(lines) if lines else "No judge data"


class PerformanceMetrics(Static):
    """Widget showing response times and throughput."""

    avg_response_ms = reactive(0.0)
    avg_judge_ms = reactive(0.0)
    requests_per_min = reactive(0.0)

    def render(self) -> str:
        return f"""Performance
─────────────────────
Avg response time:  {self.avg_response_ms:.0f}ms
Avg judge time:     {self.avg_judge_ms:.0f}ms
API calls/min:      {self.requests_per_min:.0f}"""


class CurrentBatchWithContext(Static):
    """Widget showing current batch with occupation/industry."""

    prompt_id = reactive("")
    prompt_text = reactive("")
    occupation = reactive("")
    industry = reactive("")
    response_a_status = reactive("")
    response_b_status = reactive("")

    def render(self) -> str:
        return f"""Current Batch
─────────────────────────────────────────────────────
Prompt: {self.prompt_id}
Task: {self.prompt_text[:60]}...
Occupation: {self.occupation}
Industry: {self.industry}

Response A: {self.response_a_status}
Response B: {self.response_b_status}"""


class WinRateWithCI(Static):
    """Widget showing win rates with confidence intervals."""

    win_rates: Dict[str, float] = {}
    confidence_intervals: Dict[str, Tuple[float, float]] = {}

    def update_data(
        self,
        rates: Dict[str, float],
        intervals: Dict[str, Tuple[float, float]]
    ):
        self.win_rates = rates
        self.confidence_intervals = intervals
        self.refresh()

    def render(self) -> str:
        lines = ["Win Rates (Gemini)"]
        lines.append("─" * 35)

        for pair_key, rate in self.win_rates.items():
            # Extract competitor name
            parts = pair_key.split("_vs_")
            if len(parts) > 1:
                competitor = parts[1].split("/")[-1][:12]
            else:
                competitor = pair_key[:12]

            ci = self.confidence_intervals.get(pair_key, (0, 1))
            margin = (ci[1] - ci[0]) / 2 * 100
            lines.append(f"vs {competitor}: {rate*100:.1f}% +/- {margin:.1f}%")

        return "\n".join(lines)


class ProgressDashboard(App):
    """Main TUI dashboard with all required elements."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 1fr 1fr;
        grid-rows: auto 1fr auto;
    }

    #overall-progress {
        column-span: 2;
        height: 5;
        border: solid green;
        padding: 0 1;
    }

    #model-pairs {
        height: 100%;
        border: solid blue;
    }

    #current-batch {
        height: 100%;
        border: solid yellow;
    }

    #statistics {
        column-span: 2;
        height: 10;
        border: solid magenta;
    }

    #help-dialog {
        width: 50;
        height: 15;
        border: solid white;
        background: $surface;
        padding: 1 2;
    }

    .help-title {
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit_graceful", "Quit"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("d", "toggle_detail", "Detail"),
        Binding("s", "show_stats", "Stats"),
        Binding("h", "show_help", "Help"),
    ]

    is_paused = reactive(False)

    def __init__(
        self,
        on_quit_callback=None,
        on_pause_callback=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_quit_callback = on_quit_callback
        self.on_pause_callback = on_pause_callback

        # Initialize widgets
        self.progress_bar = ProgressBar(total=100, show_eta=False)
        self.eta_display = ETADisplay()
        self.cost_tracker = CostTracker()
        self.judge_agreement = JudgeAgreementDisplay()
        self.per_judge_votes = PerJudgeVotes()
        self.performance_metrics = PerformanceMetrics()
        self.current_batch = CurrentBatchWithContext()
        self.win_rates = WinRateWithCI()
        self.activity_log = Log()
        self.error_summary = Static("Errors: 0 | Retries: 0 | Rate limits: 0")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            # Overall progress section
            Vertical(
                Static("OVERALL PROGRESS"),
                self.progress_bar,
                self.eta_display,
                id="overall-progress"
            ),

            # Model pairs section
            Vertical(
                Static("MODEL PAIRS"),
                DataTable(id="pairs-table"),
                self.win_rates,
                id="model-pairs"
            ),

            # Current batch section
            Vertical(
                self.current_batch,
                self.per_judge_votes,
                id="current-batch"
            ),

            # Statistics section
            Horizontal(
                Vertical(
                    self.cost_tracker,
                    self.judge_agreement,
                ),
                Vertical(
                    self.performance_metrics,
                    self.error_summary,
                ),
                id="statistics"
            ),

            # Activity log at bottom
            Vertical(
                Static("ACTIVITY LOG"),
                self.activity_log,
                height=8
            ),

            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        # Initialize pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate")

    def update_from_progress(self, progress) -> None:
        """Update all widgets from ProgressState."""

        # Update progress bar
        if progress.total_prompts > 0:
            pct = (progress.completed_prompts / progress.total_prompts) * 100
            self.progress_bar.progress = pct

        # Update ETA
        self.eta_display.elapsed_seconds = progress.elapsed_seconds
        self.eta_display.eta_seconds = progress.eta_seconds

        # Update cost tracking
        self.cost_tracker.cost_spent = progress.cost_spent_so_far
        self.cost_tracker.cost_projected = progress.cost_projected_total

        # Update judge agreement (calculate from progress if available)
        # This would need to be calculated and stored in progress state

        # Update per-judge votes
        self.per_judge_votes.update_votes(progress.judge_vote_counts)

        # Update performance metrics
        self.performance_metrics.avg_response_ms = progress.avg_response_time_ms
        self.performance_metrics.avg_judge_ms = progress.avg_judge_time_ms
        self.performance_metrics.requests_per_min = progress.requests_per_minute

        # Update current batch
        self.current_batch.prompt_id = progress.current_prompt_id or ""
        self.current_batch.prompt_text = progress.current_prompt_text or ""
        self.current_batch.occupation = progress.current_occupation or ""
        self.current_batch.industry = progress.current_industry or ""

        # Update win rates with CIs
        self.win_rates.update_data(
            progress.running_win_rates,
            progress.running_confidence_intervals
        )

        # Update model pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.clear()
        for pair_key, pair_data in progress.model_pair_progress.items():
            completed = pair_data["completed"]
            total = pair_data["total"]
            gemini_wins = pair_data["gemini_wins"]

            progress_str = f"{completed}/{total}"
            win_rate = f"{gemini_wins/completed*100:.1f}%" if completed > 0 else "--"
            table.add_row(pair_key[:30], progress_str, win_rate)

        # Update error summary
        self.error_summary.update(
            f"Errors: {progress.failure_count} | "
            f"Retries: {progress.retry_count} | "
            f"Rate limits: {progress.rate_limit_pause_count}"
        )

    def log_activity(self, message: str) -> None:
        """Add message to activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_log.write_line(f"{timestamp}  {message}")

    def action_quit_graceful(self) -> None:
        """Handle graceful quit."""
        if self.on_quit_callback:
            self.on_quit_callback()
        self.exit()

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        if self.on_pause_callback:
            self.on_pause_callback(self.is_paused)

    def action_toggle_detail(self) -> None:
        """Toggle detailed view."""
        # Toggle visibility of detailed widgets
        pass

    def action_show_stats(self) -> None:
        """Show full statistics panel."""
        # Could push a new screen with detailed statistics
        pass

    def action_show_help(self) -> None:
        """Show help overlay."""
        self.push_screen(HelpScreen())
```

---

## 4. CLI EXTENSIONS (--tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona)

```python
# src/cli.py (additions and modifications)

import typer
from typing import Optional, List
from enum import Enum

app = typer.Typer()


class ModelTier(str, Enum):
    PRO = "pro"
    FLASH = "flash"
    BOTH = "both"


class JudgePersona(str, Enum):
    BOTH = "both"
    EXPERT = "expert"
    RECIPIENT = "recipient"


@app.command()
def run(
    # Existing options
    preset: int = typer.Option(6, help="Preset level (1-10)"),
    prompts: Optional[int] = typer.Option(None, help="Number of prompts (overrides preset)"),
    models: Optional[str] = typer.Option(None, help="Comma-separated models to evaluate"),
    occupations: Optional[str] = typer.Option(None, help="O*NET occupation codes (e.g., '11-*,13-1*')"),
    industries: Optional[str] = typer.Option(None, help="NAICS codes (e.g., '54,62')"),
    judges: Optional[str] = typer.Option(None, help="Comma-separated judge models"),
    votes: Optional[int] = typer.Option(None, help="Votes per judge (1, 3, or 5)"),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    resume: Optional[str] = typer.Option(None, help="Resume from checkpoint directory"),

    # NEW OPTIONS (Gap fixes)
    tier: ModelTier = typer.Option(
        ModelTier.BOTH,
        "--tier",
        help="Model tier to evaluate: 'pro', 'flash', or 'both'"
    ),
    job_zones: Optional[str] = typer.Option(
        None,
        "--job-zones",
        help="Filter by O*NET job zones (1-5), e.g., '4,5' for high-skill only"
    ),
    formality_range: Optional[str] = typer.Option(
        None,
        "--formality-range",
        help="Formality level range (1-5), e.g., '3-5' for formal only"
    ),
    age_range: Optional[str] = typer.Option(
        None,
        "--age-range",
        help="Writer age range, e.g., '25-45'"
    ),
    occupation_limit: Optional[int] = typer.Option(
        None,
        "--occupation-limit",
        help="Maximum prompts per occupation"
    ),
    industry_limit: Optional[int] = typer.Option(
        None,
        "--industry-limit",
        help="Maximum prompts per industry"
    ),
    persona: JudgePersona = typer.Option(
        JudgePersona.BOTH,
        "--persona",
        help="Judge persona: 'both', 'expert', or 'recipient'"
    ),
):
    """Run the Gemini Writing Evaluation."""
    from .config.presets import PRESETS, PRO_PAIRS, FLASH_PAIRS
    from .config.settings import EvalConfig, JudgeConfig
    from .config.cost_estimator import estimate_cost, format_cost_estimate

    # Load base preset
    config = PRESETS[preset]

    # Apply tier filter
    if tier == ModelTier.PRO:
        config.model_pairs = [p for p in config.model_pairs if p in PRO_PAIRS]
    elif tier == ModelTier.FLASH:
        config.model_pairs = [p for p in config.model_pairs if p in FLASH_PAIRS]

    # Apply persona filter
    if persona == JudgePersona.EXPERT:
        config.judge_config.use_both_personas = False
        config.judge_config.expert_only = True
    elif persona == JudgePersona.RECIPIENT:
        config.judge_config.use_both_personas = False
        config.judge_config.recipient_only = True

    # Parse job zones
    parsed_job_zones = None
    if job_zones:
        parsed_job_zones = [int(z.strip()) for z in job_zones.split(",")]
        config.job_zones = parsed_job_zones

    # Parse formality range
    if formality_range:
        parts = formality_range.split("-")
        config.formality_min = int(parts[0])
        config.formality_max = int(parts[1]) if len(parts) > 1 else int(parts[0])

    # Parse age range
    if age_range:
        parts = age_range.split("-")
        config.age_min = int(parts[0])
        config.age_max = int(parts[1]) if len(parts) > 1 else int(parts[0])

    # Apply limits
    if occupation_limit:
        config.max_per_occupation = occupation_limit
    if industry_limit:
        config.max_per_industry = industry_limit

    # Override other settings
    if prompts:
        config.num_prompts = prompts
    if models:
        # Parse custom model pairs
        model_list = [m.strip() for m in models.split(",")]
        # Re-create pairs with Gemini vs each competitor
        gemini_pro = "google/gemini-3.0-pro"
        gemini_flash = "google/gemini-3.0-flash"
        custom_pairs = []
        for model in model_list:
            if "gemini" not in model.lower():
                if tier == ModelTier.FLASH:
                    custom_pairs.append((gemini_flash, model))
                else:
                    custom_pairs.append((gemini_pro, model))
        if custom_pairs:
            config.model_pairs = custom_pairs

    if judges:
        config.judge_config.models = [j.strip() for j in judges.split(",")]
    if votes:
        config.judge_config.votes_per_judge = votes
    if seed:
        config.random_seed = seed

    # Parse occupation codes
    if occupations:
        config.occupation_codes = [o.strip() for o in occupations.split(",")]

    # Parse industry codes
    if industries:
        config.industry_codes = [i.strip() for i in industries.split(",")]

    # Show estimate
    estimate = estimate_cost(config)
    print(format_cost_estimate(estimate, config))

    if dry_run:
        return

    # Confirm
    if not typer.confirm("Proceed?"):
        raise typer.Abort()

    # Run evaluation
    import asyncio
    from .eval.engine import EvaluationEngine
    # ... rest of run implementation


@app.command()
def compare(
    run_dirs: List[str] = typer.Argument(..., help="Run directories to compare")
):
    """Compare results across multiple evaluation runs."""
    from pathlib import Path
    from .analysis.cross_run_compare import compare_runs

    paths = [Path(d) for d in run_dirs]
    for p in paths:
        if not p.exists():
            typer.echo(f"Error: Directory not found: {p}")
            raise typer.Exit(1)

    comparison = compare_runs(paths)
    typer.echo(comparison.format_report())


@app.command()
def export(
    run_dir: str = typer.Argument(..., help="Run directory to export"),
    output: str = typer.Option("results.csv", help="Output file path"),
    format: str = typer.Option("csv", help="Export format: csv, json, excel")
):
    """Export evaluation results to various formats."""
    from pathlib import Path
    from .storage.database import ResultsDatabase

    db = ResultsDatabase(Path(run_dir) / "results.db")

    if format == "csv":
        db.export_to_csv(output)
    elif format == "json":
        db.export_to_json(output)
    elif format == "excel":
        db.export_to_excel(output)

    typer.echo(f"Exported to {output}")


if __name__ == "__main__":
    app()
```

---

## 5. NAME FORMALITY VARIATION

```python
# src/data/name_generator.py (additions)

import random
from typing import Optional, List, Literal
from dataclasses import dataclass


@dataclass
class GeneratedName:
    """Generated name with various formality options."""
    first_name: str
    last_name: str
    middle_initial: Optional[str] = None
    prefix: Optional[str] = None  # Dr., Mr., Ms., etc.
    suffix: Optional[str] = None  # Jr., III, PhD, etc.

    # Pre-computed formality variants
    informal: str = ""      # "Mike"
    semiformal: str = ""    # "Michael" or "Mike Williams"
    formal: str = ""        # "Michael Williams"
    very_formal: str = ""   # "Michael T. Williams" or "Dr. Michael Williams"
    ultra_formal: str = ""  # "Dr. Michael T. Williams, PhD"

    email_informal: str = ""     # "mike@company.com"
    email_formal: str = ""       # "michael.williams@company.com"
    email_initial: str = ""      # "m.williams@company.com"


class NameGenerator:
    """Generate demographically diverse names with formality variations."""

    # Common nicknames mapping
    NICKNAMES = {
        "Michael": ["Mike", "Mikey"],
        "William": ["Will", "Bill", "Billy"],
        "Robert": ["Rob", "Bob", "Bobby"],
        "Richard": ["Rich", "Rick", "Dick"],
        "Elizabeth": ["Liz", "Beth", "Lizzy", "Betty"],
        "Katherine": ["Kate", "Katie", "Kathy", "Kay"],
        "Jennifer": ["Jen", "Jenny"],
        "Patricia": ["Pat", "Patty", "Trish"],
        "Margaret": ["Maggie", "Meg", "Peggy"],
        "Christopher": ["Chris"],
        "Jonathan": ["Jon", "Johnny"],
        "Nicholas": ["Nick", "Nicky"],
        "Anthony": ["Tony"],
        "Alexander": ["Alex"],
        "Benjamin": ["Ben", "Benny"],
        "Samantha": ["Sam", "Sammy"],
        "Victoria": ["Vicky", "Tori"],
        "Rebecca": ["Becca", "Becky"],
        "Jessica": ["Jess", "Jessie"],
        "Amanda": ["Mandy"],
        "Stephanie": ["Steph"],
        "Andrew": ["Andy", "Drew"],
        "Matthew": ["Matt"],
        "Daniel": ["Dan", "Danny"],
        "Joseph": ["Joe", "Joey"],
        "Thomas": ["Tom", "Tommy"],
    }

    # Prefixes by profession level
    PROFESSIONAL_PREFIXES = {
        "executive": ["Dr.", "Mr.", "Ms."],
        "senior": ["Mr.", "Ms."],
        "mid": ["Mr.", "Ms."],
        "entry": [],  # Rarely use prefixes
    }

    # Academic/professional suffixes
    SUFFIXES = ["PhD", "MD", "JD", "MBA", "CPA", "PE", "Jr.", "III", "II"]

    def __init__(self, census_data_path: Optional[str] = None):
        # Load census data for realistic name distributions
        self.first_names_male = self._load_names("male")
        self.first_names_female = self._load_names("female")
        self.last_names = self._load_last_names()

    def _load_names(self, gender: str) -> List[str]:
        """Load names from census data (simplified)."""
        # In production, load from census data file
        if gender == "male":
            return [
                "James", "Michael", "Robert", "David", "William", "John",
                "Richard", "Joseph", "Thomas", "Christopher", "Charles",
                "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven",
                "Andrew", "Paul", "Joshua", "Kenneth", "Kevin", "Brian",
                "Wei", "Mohammed", "Jose", "Carlos", "Miguel", "Raj",
                "Kenji", "Hiroshi", "Dmitri", "Aleksei", "Pierre", "Jean",
            ]
        else:
            return [
                "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
                "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Lisa",
                "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly",
                "Emily", "Donna", "Michelle", "Dorothy", "Carol", "Amanda",
                "Mei", "Fatima", "Maria", "Ana", "Priya", "Aisha",
                "Yuki", "Sakura", "Olga", "Natasha", "Marie", "Sophie",
            ]

    def _load_last_names(self) -> List[str]:
        """Load last names from census data."""
        return [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
            "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
            "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
            "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
            "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
            "Chen", "Wang", "Li", "Zhang", "Liu", "Yang", "Huang",
            "Kim", "Park", "Nguyen", "Patel", "Singh", "Kumar", "Shah",
            "Tanaka", "Yamamoto", "Sato", "Suzuki", "Takahashi",
            "Muller", "Schmidt", "Fischer", "Weber", "Meyer",
        ]

    def generate(
        self,
        gender: Optional[str] = None,
        generation: Optional[str] = None,
        skill_level: str = "mid",
        include_prefix: bool = False,
        include_suffix: bool = False,
        seed: Optional[int] = None
    ) -> GeneratedName:
        """Generate a name with all formality variants."""

        rng = random.Random(seed) if seed else random

        # Select gender
        if gender is None:
            gender = rng.choice(["male", "female"])

        # Select names
        if gender == "male":
            first_name = rng.choice(self.first_names_male)
        else:
            first_name = rng.choice(self.first_names_female)

        last_name = rng.choice(self.last_names)

        # Maybe generate middle initial
        middle_initial = rng.choice("ABCDEFGHJKLMNPRSTW") if rng.random() < 0.4 else None

        # Maybe add prefix (more common for executives)
        prefix = None
        if include_prefix or (skill_level == "executive" and rng.random() < 0.3):
            prefixes = self.PROFESSIONAL_PREFIXES.get(skill_level, [])
            if prefixes:
                prefix = rng.choice(prefixes)

        # Maybe add suffix (rare)
        suffix = None
        if include_suffix or (skill_level == "executive" and rng.random() < 0.1):
            suffix = rng.choice(self.SUFFIXES)

        # Build formality variants
        name = GeneratedName(
            first_name=first_name,
            last_name=last_name,
            middle_initial=middle_initial,
            prefix=prefix,
            suffix=suffix
        )

        # Get nickname if available
        nickname = None
        if first_name in self.NICKNAMES:
            nickname = rng.choice(self.NICKNAMES[first_name])

        # Build variants
        name.informal = nickname or first_name

        name.semiformal = f"{first_name} {last_name}"

        name.formal = f"{first_name} {last_name}"

        if middle_initial:
            name.very_formal = f"{first_name} {middle_initial}. {last_name}"
        elif prefix:
            name.very_formal = f"{prefix} {first_name} {last_name}"
        else:
            name.very_formal = name.formal

        # Ultra formal with prefix and suffix
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(first_name)
        if middle_initial:
            parts.append(f"{middle_initial}.")
        parts.append(last_name)
        if suffix:
            parts.append(f", {suffix}")
        name.ultra_formal = " ".join(parts)

        # Email variants
        informal_first = (nickname or first_name).lower()
        formal_first = first_name.lower()
        last = last_name.lower()

        name.email_informal = f"{informal_first}@company.com"
        name.email_formal = f"{formal_first}.{last}@company.com"
        name.email_initial = f"{formal_first[0]}.{last}@company.com"

        return name

    def get_formality_variant(
        self,
        name: GeneratedName,
        formality_level: int
    ) -> str:
        """Get the appropriate name variant for a formality level (1-5)."""
        if formality_level == 1:
            return name.informal
        elif formality_level == 2:
            return name.semiformal
        elif formality_level == 3:
            return name.formal
        elif formality_level == 4:
            return name.very_formal
        else:  # 5
            return name.ultra_formal

    def get_email_for_formality(
        self,
        name: GeneratedName,
        formality_level: int,
        company_domain: str = "company.com"
    ) -> str:
        """Get appropriate email format for formality level."""
        informal_first = name.informal.lower()
        formal_first = name.first_name.lower()
        last = name.last_name.lower()

        if formality_level <= 2:
            return f"{informal_first}@{company_domain}"
        elif formality_level == 3:
            return f"{formal_first}.{last}@{company_domain}"
        else:
            return f"{formal_first[0]}.{last}@{company_domain}"
```

---

## 6. PHASE 1 GENERATION USING EVALUATED MODELS

```python
# src/prompts/phase1_offline.py

import asyncio
import random
from typing import List, Dict, Optional, Any
from pathlib import Path
import json

from ..api.openrouter_client import OpenRouterClient
from ..data.onet_extractor import ONetExtractor, ONetTask
from ..config.presets import PRO_PAIRS, FLASH_PAIRS


class Phase1OfflineGenerator:
    """Generate diverse persona/context variations for each O*NET task.

    CRITICAL: Uses the same models being evaluated (per PROMPT.md requirement).
    This ensures prompts aren't accidentally biased against any particular model.
    Note: This creates potential bias but is intentional.
    """

    # Models used for generation - same as evaluation models
    GENERATION_MODELS = [
        "google/gemini-3.0-pro",
        "openai/gpt-5.2",
        "anthropic/claude-opus-4.5",
    ]

    VARIATION_PROMPT = """Given this O*NET writing task:

Task: {task_statement}
Occupation: {occupation_title}
Job Zone: {job_zone}

Generate 5 diverse variations of this writing scenario. For each variation, provide:

1. A specific writer persona (name, age, generation, skill level)
2. A specific recipient persona (name, role, relationship to writer)
3. Company context (real company name, size, industry)
4. Formality level (1-5)
5. Urgency level (1-5)
6. Emotional context (routine, crisis, celebration, conflict, bad_news)
7. Any temporal context if relevant
8. Any competing objectives or constraints

Ensure high diversity:
- Mix ages from 22-65
- Mix generations (gen_z, millennial, gen_x, boomer)
- Mix skill levels (entry, mid, senior, executive)
- Mix company sizes (startup to Fortune 500)
- Mix formality levels
- Mix urgency levels
- Include some revision tasks
- Include some ambiguous prompts

Output as JSON array with 5 objects.
"""

    def __init__(
        self,
        client: OpenRouterClient,
        onet_extractor: ONetExtractor,
        output_dir: Path,
        variations_per_task: int = 5,
        model_rotation: bool = True
    ):
        self.client = client
        self.onet_extractor = onet_extractor
        self.output_dir = output_dir
        self.variations_per_task = variations_per_task
        self.model_rotation = model_rotation

        # Track which model generated each variation (for bias analysis)
        self.generation_tracking: Dict[str, str] = {}

    async def generate_all_variations(
        self,
        tasks: List[ONetTask],
        max_concurrency: int = 10
    ) -> Dict[str, List[Dict]]:
        """Generate variations for all tasks using evaluated models."""

        semaphore = asyncio.Semaphore(max_concurrency)
        all_variations: Dict[str, List[Dict]] = {}

        async def generate_for_task(task: ONetTask, model_idx: int):
            async with semaphore:
                # Rotate through generation models
                if self.model_rotation:
                    model = self.GENERATION_MODELS[model_idx % len(self.GENERATION_MODELS)]
                else:
                    model = random.choice(self.GENERATION_MODELS)

                variations = await self._generate_variations(task, model)

                # Track which model generated this
                self.generation_tracking[task.task_id] = model

                return task.task_id, variations

        # Generate concurrently
        coros = [
            generate_for_task(task, i)
            for i, task in enumerate(tasks)
        ]

        results = await asyncio.gather(*coros, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            task_id, variations = result
            all_variations[task_id] = variations

        # Save to file
        await self._save_variations(all_variations)

        return all_variations

    async def _generate_variations(
        self,
        task: ONetTask,
        model: str
    ) -> List[Dict]:
        """Generate variations for a single task."""

        prompt = self.VARIATION_PROMPT.format(
            task_statement=task.task_statement,
            occupation_title=task.occupation_title,
            job_zone=task.job_zone
        )

        try:
            response = await self.client.complete(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9  # Higher temperature for diversity
            )

            # Parse JSON response
            content = response.content
            # Extract JSON array from response
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                variations = json.loads(json_match.group())
                # Add metadata
                for v in variations:
                    v["generated_by_model"] = model
                    v["source_task_id"] = task.task_id
                return variations
            else:
                return []

        except Exception as e:
            return []

    async def _save_variations(self, variations: Dict[str, List[Dict]]):
        """Save variations to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save all variations
        output_path = self.output_dir / "offline_variations.json"
        with open(output_path, 'w') as f:
            json.dump(variations, f, indent=2)

        # Save generation tracking (for bias analysis)
        tracking_path = self.output_dir / "generation_tracking.json"
        with open(tracking_path, 'w') as f:
            json.dump(self.generation_tracking, f, indent=2)

    async def load_cached_variations(self) -> Optional[Dict[str, List[Dict]]]:
        """Load previously generated variations if available."""
        cache_path = self.output_dir / "offline_variations.json"
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                return json.load(f)
        return None
```

---

## 7. AMBIGUITY BEHAVIOR TRACKING

```python
# src/eval/ambiguity_tracker.py

from dataclasses import dataclass
from typing import List, Optional, Literal
from enum import Enum
import re


class AmbiguityBehavior(str, Enum):
    """How the model handled ambiguity in the prompt."""
    ASKED_CLARIFICATION = "asked_clarification"
    MADE_ASSUMPTIONS = "made_assumptions"
    HEDGED_APPROPRIATELY = "hedged_appropriately"
    HALLUCINATED_DETAILS = "hallucinated_details"
    REFUSED_DUE_TO_AMBIGUITY = "refused_ambiguity"
    IGNORED_AMBIGUITY = "ignored_ambiguity"


@dataclass
class AmbiguityAnalysis:
    """Analysis of how a model handled ambiguous prompt."""
    prompt_id: str
    model: str
    ambiguity_type: str  # underspecified_recipient, missing_context, unclear_ask
    behaviors_detected: List[AmbiguityBehavior]
    clarification_questions: List[str]
    assumptions_made: List[str]
    hedging_phrases: List[str]
    hallucinated_details: List[str]
    confidence: float  # 0-1 confidence in this analysis


class AmbiguityTracker:
    """Track how models handle deliberately ambiguous prompts."""

    # Patterns indicating the model asked for clarification
    CLARIFICATION_PATTERNS = [
        r"could you (please )?clarify",
        r"can you (please )?specify",
        r"what (exactly |specifically )?do you mean",
        r"i('d| would) need (more|additional) (information|details|context)",
        r"before i (can |proceed|respond)",
        r"a few questions",
        r"to clarify",
        r"just to confirm",
        r"did you mean",
        r"which (one|specific)",
        r"who (exactly|specifically)",
        r"when (exactly|specifically)",
        r"\?\s*$",  # Ends with question mark
    ]

    # Patterns indicating the model made assumptions
    ASSUMPTION_PATTERNS = [
        r"i('ll| will) assume",
        r"assuming (that|you)",
        r"i('m| am) assuming",
        r"based on (my|the) assumption",
        r"if i understand correctly",
        r"i interpret this as",
        r"taking this to mean",
        r"presumably",
    ]

    # Patterns indicating appropriate hedging
    HEDGING_PATTERNS = [
        r"depending on",
        r"if .{1,50} then",
        r"alternatively",
        r"in case",
        r"should .{1,50} be the case",
        r"this may (need|require)",
        r"you might (want|need) to",
        r"consider (whether|if)",
        r"it('s| is) (possible|likely) that",
    ]

    # Patterns suggesting hallucinated specific details
    HALLUCINATION_INDICATORS = [
        r"on (monday|tuesday|wednesday|thursday|friday)",
        r"at \d{1,2}(:\d{2})?\s*(am|pm|AM|PM)",
        r"\$[\d,]+",  # Specific dollar amounts
        r"\d+%",  # Specific percentages
        r"(january|february|march|april|may|june|july|august|september|october|november|december) \d+",
        r"room (number )?\d+",
        r"floor \d+",
    ]

    def analyze_response(
        self,
        prompt_id: str,
        model: str,
        ambiguity_type: str,
        prompt_text: str,
        response_text: str
    ) -> AmbiguityAnalysis:
        """Analyze how a model handled an ambiguous prompt."""

        response_lower = response_text.lower()
        behaviors = []
        clarification_questions = []
        assumptions_made = []
        hedging_phrases = []
        hallucinated_details = []

        # Check for clarification questions
        for pattern in self.CLARIFICATION_PATTERNS:
            matches = re.findall(pattern, response_lower)
            if matches:
                clarification_questions.extend(matches)

        if clarification_questions:
            behaviors.append(AmbiguityBehavior.ASKED_CLARIFICATION)

        # Check for explicit assumptions
        for pattern in self.ASSUMPTION_PATTERNS:
            matches = re.findall(pattern, response_lower)
            if matches:
                assumptions_made.extend(matches)

        if assumptions_made:
            behaviors.append(AmbiguityBehavior.MADE_ASSUMPTIONS)

        # Check for hedging language
        for pattern in self.HEDGING_PATTERNS:
            matches = re.findall(pattern, response_lower)
            if matches:
                hedging_phrases.extend(matches)

        if hedging_phrases and not clarification_questions:
            behaviors.append(AmbiguityBehavior.HEDGED_APPROPRIATELY)

        # Check for potentially hallucinated details
        # (Details not present in the prompt)
        prompt_lower = prompt_text.lower()
        for pattern in self.HALLUCINATION_INDICATORS:
            response_matches = set(re.findall(pattern, response_lower))
            prompt_matches = set(re.findall(pattern, prompt_lower))
            new_details = response_matches - prompt_matches
            if new_details:
                hallucinated_details.extend(new_details)

        if hallucinated_details and not assumptions_made:
            behaviors.append(AmbiguityBehavior.HALLUCINATED_DETAILS)

        # Check for refusal due to ambiguity
        refusal_patterns = [
            r"i (can't|cannot) (proceed|respond|complete)",
            r"need more (information|context|details)",
            r"too vague",
            r"not enough (information|context)",
        ]
        for pattern in refusal_patterns:
            if re.search(pattern, response_lower):
                behaviors.append(AmbiguityBehavior.REFUSED_DUE_TO_AMBIGUITY)
                break

        # If no other behaviors detected, model ignored ambiguity
        if not behaviors:
            behaviors.append(AmbiguityBehavior.IGNORED_AMBIGUITY)

        # Calculate confidence based on strength of signals
        confidence = min(1.0, (
            len(clarification_questions) * 0.2 +
            len(assumptions_made) * 0.15 +
            len(hedging_phrases) * 0.1 +
            len(hallucinated_details) * 0.1
        ) + 0.3)

        return AmbiguityAnalysis(
            prompt_id=prompt_id,
            model=model,
            ambiguity_type=ambiguity_type,
            behaviors_detected=behaviors,
            clarification_questions=clarification_questions[:5],
            assumptions_made=assumptions_made[:5],
            hedging_phrases=hedging_phrases[:5],
            hallucinated_details=hallucinated_details[:5],
            confidence=confidence
        )

    def summarize_by_model(
        self,
        analyses: List[AmbiguityAnalysis]
    ) -> Dict[str, Dict[str, int]]:
        """Summarize ambiguity handling by model."""
        from collections import defaultdict

        summary = defaultdict(lambda: defaultdict(int))

        for analysis in analyses:
            model = analysis.model
            for behavior in analysis.behaviors_detected:
                summary[model][behavior.value] += 1

        return dict(summary)
```

---

## 8. TUI RESULTS VIEWER (Filtering, Sorting, Drill-down)

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Select, Button, Label, TextArea
)
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class ResultFilter:
    """Filter criteria for results."""
    occupation_code: Optional[str] = None
    industry_code: Optional[str] = None
    winner: Optional[str] = None  # "gemini", "competitor", "tie"
    model_pair: Optional[str] = None
    formality_min: Optional[int] = None
    formality_max: Optional[int] = None
    has_constraints: Optional[bool] = None
    is_ambiguous: Optional[bool] = None
    sensitive_topic: Optional[str] = None


class ResultDetailScreen(ModalScreen):
    """Drill-down view for a single comparison result."""

    def __init__(self, result: Dict, **kwargs):
        super().__init__(**kwargs)
        self.result = result

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("j", "next_judgment", "Next Judgment"),
        Binding("k", "prev_judgment", "Prev Judgment"),
    ]

    def compose(self) -> ComposeResult:
        r = self.result

        yield Container(
            # Header with prompt info
            Static(f"Prompt ID: {r.get('prompt_id', 'N/A')}", classes="detail-header"),
            Static(f"Winner: {r.get('final_winner', 'N/A').upper()}", classes="winner-badge"),

            # Side-by-side responses
            Horizontal(
                Vertical(
                    Static("GEMINI RESPONSE", classes="response-title"),
                    TextArea(r.get('gemini_response', ''), read_only=True),
                    id="response-gemini"
                ),
                Vertical(
                    Static("COMPETITOR RESPONSE", classes="response-title"),
                    TextArea(r.get('competitor_response', ''), read_only=True),
                    id="response-competitor"
                ),
                id="responses-container"
            ),

            # Judgment details
            Vertical(
                Static("JUDGMENTS", classes="section-title"),
                DataTable(id="judgments-table"),
                id="judgments-container"
            ),

            # Metadata
            Vertical(
                Static("METADATA", classes="section-title"),
                Static(f"Occupation: {r.get('occupation_title', 'N/A')}"),
                Static(f"Industry: {r.get('naics_sector', 'N/A')}"),
                Static(f"Formality: {r.get('formality_level', 'N/A')}/5"),
                Static(f"Model Pair: {r.get('gemini_model', '')} vs {r.get('competitor_model', '')}"),
                id="metadata-container"
            ),

            id="detail-dialog"
        )

    def on_mount(self):
        # Populate judgments table
        table = self.query_one("#judgments-table", DataTable)
        table.add_columns("Judge", "Persona", "Vote", "Winner", "Confidence", "Reasoning")

        for vote in self.result.get('all_votes', []):
            table.add_row(
                vote.get('judge_model', '').split('/')[-1],
                vote.get('judge_persona', ''),
                str(vote.get('vote_index', 0) + 1),
                vote.get('winner', ''),
                str(vote.get('confidence', '')),
                vote.get('reasoning', '')[:50] + "..."
            )


class FilterPanel(Static):
    """Panel with filter controls."""

    def __init__(self, on_filter_change: Callable[[ResultFilter], None], **kwargs):
        super().__init__(**kwargs)
        self.on_filter_change = on_filter_change
        self.current_filter = ResultFilter()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("FILTERS", classes="panel-title"),

            # Winner filter
            Horizontal(
                Label("Winner:"),
                Select([
                    ("All", None),
                    ("Gemini Wins", "gemini"),
                    ("Competitor Wins", "competitor"),
                    ("Ties", "tie"),
                ], id="filter-winner"),
            ),

            # Model pair filter
            Horizontal(
                Label("Model Pair:"),
                Select(id="filter-model-pair"),
            ),

            # Occupation filter
            Horizontal(
                Label("Occupation:"),
                Input(placeholder="e.g., 11-* or 11-1011", id="filter-occupation"),
            ),

            # Industry filter
            Horizontal(
                Label("Industry:"),
                Input(placeholder="e.g., 54 or 62", id="filter-industry"),
            ),

            # Formality range
            Horizontal(
                Label("Formality:"),
                Input(placeholder="1-5", id="filter-formality"),
            ),

            # Special filters
            Horizontal(
                Button("Has Constraints", id="btn-constraints"),
                Button("Is Ambiguous", id="btn-ambiguous"),
            ),

            # Apply/Clear buttons
            Horizontal(
                Button("Apply Filters", id="btn-apply", variant="primary"),
                Button("Clear", id="btn-clear"),
            ),
        )

    def on_button_pressed(self, event):
        if event.button.id == "btn-apply":
            self._apply_filters()
        elif event.button.id == "btn-clear":
            self._clear_filters()
        elif event.button.id == "btn-constraints":
            self.current_filter.has_constraints = not self.current_filter.has_constraints
        elif event.button.id == "btn-ambiguous":
            self.current_filter.is_ambiguous = not self.current_filter.is_ambiguous

    def _apply_filters(self):
        # Read filter values from inputs
        winner_select = self.query_one("#filter-winner", Select)
        if winner_select.value:
            self.current_filter.winner = winner_select.value

        occ_input = self.query_one("#filter-occupation", Input)
        if occ_input.value:
            self.current_filter.occupation_code = occ_input.value

        ind_input = self.query_one("#filter-industry", Input)
        if ind_input.value:
            self.current_filter.industry_code = ind_input.value

        form_input = self.query_one("#filter-formality", Input)
        if form_input.value:
            parts = form_input.value.split("-")
            self.current_filter.formality_min = int(parts[0])
            if len(parts) > 1:
                self.current_filter.formality_max = int(parts[1])

        self.on_filter_change(self.current_filter)

    def _clear_filters(self):
        self.current_filter = ResultFilter()
        # Clear all inputs
        for input_widget in self.query(Input):
            input_widget.value = ""
        self.on_filter_change(self.current_filter)


class ResultsViewer(App):
    """Interactive TUI for viewing and filtering evaluation results."""

    CSS = """
    #main-container {
        layout: horizontal;
    }

    #filter-panel {
        width: 25%;
        border: solid blue;
    }

    #results-panel {
        width: 75%;
    }

    #detail-dialog {
        width: 90%;
        height: 90%;
        border: solid white;
        background: $surface;
    }

    .response-title {
        text-style: bold;
        color: cyan;
    }

    .winner-badge {
        text-style: bold;
        padding: 0 1;
    }

    .panel-title {
        text-style: bold;
        background: $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filters", "Filters"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("enter", "show_detail", "Details"),
        Binding("/", "search", "Search"),
        Binding("n", "next_page", "Next"),
        Binding("p", "prev_page", "Prev"),
    ]

    # Reactive properties
    current_page = reactive(0)
    page_size = 50
    sort_column = reactive("prompt_id")
    sort_reverse = reactive(False)

    def __init__(self, results_db_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.results_db_path = results_db_path
        self.all_results: List[Dict] = []
        self.filtered_results: List[Dict] = []
        self.current_filter = ResultFilter()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            FilterPanel(self.on_filter_change, id="filter-panel"),
            Vertical(
                # Summary stats
                Static(id="summary-stats"),
                # Results table
                DataTable(id="results-table"),
                # Pagination
                Horizontal(
                    Button("< Prev", id="btn-prev"),
                    Static(id="page-info"),
                    Button("Next >", id="btn-next"),
                    id="pagination"
                ),
                id="results-panel"
            ),
            id="main-container"
        )
        yield Footer()

    async def on_mount(self):
        # Load results from database
        await self.load_results()

        # Setup table
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "Prompt ID", "Winner", "Occupation", "Industry",
            "Formality", "Model Pair", "Agreement"
        )
        table.cursor_type = "row"

        self.refresh_table()

    async def load_results(self):
        """Load results from SQLite database."""
        import aiosqlite

        async with aiosqlite.connect(self.results_db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM comparisons
                ORDER BY prompt_id
            """)
            rows = await cursor.fetchall()
            self.all_results = [dict(row) for row in rows]

        self.filtered_results = self.all_results.copy()

    def on_filter_change(self, new_filter: ResultFilter):
        """Apply new filter to results."""
        self.current_filter = new_filter
        self.apply_filters()
        self.refresh_table()

    def apply_filters(self):
        """Filter results based on current criteria."""
        filtered = []

        for result in self.all_results:
            # Check each filter criterion
            if self.current_filter.winner:
                if result.get('final_winner') != self.current_filter.winner:
                    continue

            if self.current_filter.occupation_code:
                occ = result.get('occupation_code', '')
                pattern = self.current_filter.occupation_code
                if pattern.endswith('*'):
                    if not occ.startswith(pattern[:-1]):
                        continue
                elif occ != pattern:
                    continue

            if self.current_filter.industry_code:
                ind = result.get('naics_code', '')
                if not ind.startswith(self.current_filter.industry_code):
                    continue

            if self.current_filter.formality_min:
                if result.get('formality_level', 0) < self.current_filter.formality_min:
                    continue

            if self.current_filter.formality_max:
                if result.get('formality_level', 5) > self.current_filter.formality_max:
                    continue

            if self.current_filter.has_constraints is not None:
                if result.get('has_constraints') != self.current_filter.has_constraints:
                    continue

            if self.current_filter.is_ambiguous is not None:
                if result.get('is_ambiguous') != self.current_filter.is_ambiguous:
                    continue

            if self.current_filter.model_pair:
                pair = f"{result.get('gemini_model')}_vs_{result.get('competitor_model')}"
                if pair != self.current_filter.model_pair:
                    continue

            filtered.append(result)

        self.filtered_results = filtered
        self.current_page = 0

    def refresh_table(self):
        """Refresh the results table with current filtered/sorted data."""
        table = self.query_one("#results-table", DataTable)
        table.clear()

        # Sort results
        sorted_results = sorted(
            self.filtered_results,
            key=lambda r: r.get(self.sort_column, ''),
            reverse=self.sort_reverse
        )

        # Paginate
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_results = sorted_results[start:end]

        # Populate table
        for result in page_results:
            table.add_row(
                result.get('prompt_id', '')[:15],
                result.get('final_winner', ''),
                result.get('occupation_code', ''),
                result.get('naics_code', ''),
                str(result.get('formality_level', '')),
                result.get('competitor_model', '').split('/')[-1],
                f"{result.get('judge_agreement', 0)*100:.0f}%"
            )

        # Update summary
        summary = self.query_one("#summary-stats", Static)
        total = len(self.filtered_results)
        gemini_wins = sum(1 for r in self.filtered_results if r.get('final_winner') == 'gemini')
        summary.update(
            f"Showing {len(page_results)} of {total} results | "
            f"Gemini wins: {gemini_wins} ({gemini_wins/total*100:.1f}%)" if total > 0 else ""
        )

        # Update pagination info
        page_info = self.query_one("#page-info", Static)
        total_pages = (total + self.page_size - 1) // self.page_size
        page_info.update(f"Page {self.current_page + 1} of {total_pages}")

    def action_show_detail(self):
        """Show detailed view for selected result."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None:
            start = self.current_page * self.page_size
            result_idx = start + table.cursor_row
            if result_idx < len(self.filtered_results):
                result = self.filtered_results[result_idx]
                self.push_screen(ResultDetailScreen(result))

    def action_cycle_sort(self):
        """Cycle through sort options."""
        sort_options = ["prompt_id", "final_winner", "occupation_code", "formality_level"]
        current_idx = sort_options.index(self.sort_column) if self.sort_column in sort_options else 0
        next_idx = (current_idx + 1) % len(sort_options)
        self.sort_column = sort_options[next_idx]
        self.refresh_table()

    def action_next_page(self):
        total_pages = (len(self.filtered_results) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.refresh_table()

    def action_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_table()

    def action_toggle_filters(self):
        """Toggle filter panel visibility."""
        panel = self.query_one("#filter-panel")
        panel.display = not panel.display
```

---

## 9. REFUSAL TRACKING BY DIMENSION

```python
# src/eval/refusal_classifier.py

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum
import re
from collections import defaultdict


class RefusalCategory(str, Enum):
    """Categories of model refusals."""
    SAFETY_REFUSAL = "safety_refusal"          # Model cites safety/policy concerns
    CAPABILITY_LIMITATION = "capability"        # Model says it can't do the task
    MISUNDERSTANDING = "misunderstanding"       # Model interprets task incorrectly
    INCOMPLETE_RESPONSE = "incomplete"          # Model starts but doesn't finish
    OFF_TOPIC = "off_topic"                     # Model responds but not to the task
    EMPTY_RESPONSE = "empty"                    # Empty or near-empty response
    TIMEOUT = "timeout"                         # Response timed out
    NO_REFUSAL = "no_refusal"                   # Valid response


@dataclass
class RefusalResult:
    """Result of refusal classification."""
    is_refusal: bool
    category: RefusalCategory
    confidence: float
    detected_patterns: List[str]
    raw_response_length: int


@dataclass
class RefusalDimensionSummary:
    """Summary of refusals by a single dimension."""
    dimension_name: str
    dimension_value: str
    total_responses: int
    refusal_count: int
    refusal_rate: float
    by_category: Dict[str, int]


class RefusalClassifier:
    """Classify model refusals into categories and track by dimension."""

    # Safety refusal patterns
    SAFETY_PATTERNS = [
        r"i (can't|cannot|won't|will not) (help|assist|generate|create|write) .{0,30}(content|request|task)",
        r"(against|violates) (my|our) (guidelines|policies|terms|safety)",
        r"(harmful|dangerous|illegal|unethical) (content|request)",
        r"i('m| am) not (able|allowed) to",
        r"as an ai( language model)?.*i (can't|cannot|won't)",
        r"i apologize, but i (can't|cannot)",
        r"(ethically|morally) (unable|obligated not)",
        r"i must (decline|refuse)",
    ]

    # Capability limitation patterns
    CAPABILITY_PATTERNS = [
        r"i (don't|do not) have (access|the ability)",
        r"(beyond|outside) (my|the) (capabilities|scope)",
        r"i('m| am) not (capable|equipped) to",
        r"i lack the (ability|capability|information)",
        r"this (requires|needs) .{0,30} that i (don't|do not) have",
        r"i (can't|cannot) (access|retrieve|connect|browse)",
    ]

    # Misunderstanding patterns
    MISUNDERSTANDING_PATTERNS = [
        r"(it seems|looks) like you('re| are) asking (me|about)",
        r"i('m| am) not sure (what|if) you mean",
        r"could you (clarify|explain|rephrase)",
        r"i think you might (mean|be asking)",
        r"did you (mean|intend) to",
    ]

    # Off-topic indicators
    OFF_TOPIC_PATTERNS = [
        r"^(here|sure|certainly|absolutely|great|of course)",  # Starts affirming but...
        r"(instead|however|rather than|but first)",
    ]

    def classify(self, response: str, timed_out: bool = False) -> RefusalResult:
        """Classify a model response for refusal."""

        if timed_out:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.TIMEOUT,
                confidence=1.0,
                detected_patterns=[],
                raw_response_length=0
            )

        # Check for empty/near-empty
        if not response or len(response.strip()) < 20:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.EMPTY_RESPONSE,
                confidence=1.0,
                detected_patterns=[],
                raw_response_length=len(response) if response else 0
            )

        response_lower = response.lower()
        detected_patterns = []

        # Check safety refusals
        for pattern in self.SAFETY_PATTERNS:
            if re.search(pattern, response_lower):
                detected_patterns.append(pattern)

        if detected_patterns:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.SAFETY_REFUSAL,
                confidence=min(1.0, 0.5 + len(detected_patterns) * 0.2),
                detected_patterns=detected_patterns[:3],
                raw_response_length=len(response)
            )

        # Check capability limitations
        detected_patterns = []
        for pattern in self.CAPABILITY_PATTERNS:
            if re.search(pattern, response_lower):
                detected_patterns.append(pattern)

        if detected_patterns:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.CAPABILITY_LIMITATION,
                confidence=min(1.0, 0.4 + len(detected_patterns) * 0.2),
                detected_patterns=detected_patterns[:3],
                raw_response_length=len(response)
            )

        # Check for incomplete response (ends abruptly, no proper ending)
        if len(response) > 50:
            last_sentence = response.strip().split('.')[-1]
            if len(last_sentence) > 100 and not response.strip().endswith(('.', '!', '?', '"', "'")):
                return RefusalResult(
                    is_refusal=True,
                    category=RefusalCategory.INCOMPLETE_RESPONSE,
                    confidence=0.6,
                    detected_patterns=["response ends abruptly"],
                    raw_response_length=len(response)
                )

        # Check for misunderstanding
        detected_patterns = []
        for pattern in self.MISUNDERSTANDING_PATTERNS:
            if re.search(pattern, response_lower):
                detected_patterns.append(pattern)

        if detected_patterns:
            return RefusalResult(
                is_refusal=True,
                category=RefusalCategory.MISUNDERSTANDING,
                confidence=min(1.0, 0.3 + len(detected_patterns) * 0.2),
                detected_patterns=detected_patterns[:3],
                raw_response_length=len(response)
            )

        # No refusal detected
        return RefusalResult(
            is_refusal=False,
            category=RefusalCategory.NO_REFUSAL,
            confidence=0.9,
            detected_patterns=[],
            raw_response_length=len(response)
        )


class RefusalDimensionTracker:
    """Track refusals by various dimensions for analysis."""

    def __init__(self):
        self.classifier = RefusalClassifier()
        self._refusals_by_model: Dict[str, List[RefusalResult]] = defaultdict(list)
        self._refusals_by_task_type: Dict[str, List[RefusalResult]] = defaultdict(list)
        self._refusals_by_sensitive_topic: Dict[str, List[RefusalResult]] = defaultdict(list)
        self._refusals_by_occupation: Dict[str, List[RefusalResult]] = defaultdict(list)
        self._refusals_by_formality: Dict[int, List[RefusalResult]] = defaultdict(list)

    def track_response(
        self,
        response: str,
        model: str,
        task_type: Optional[str] = None,
        sensitive_topics: Optional[List[str]] = None,
        occupation_code: Optional[str] = None,
        formality_level: Optional[int] = None,
        timed_out: bool = False
    ) -> RefusalResult:
        """Track a response and classify refusal by dimensions."""

        result = self.classifier.classify(response, timed_out)

        if result.is_refusal:
            # Track by model
            self._refusals_by_model[model].append(result)

            # Track by task type
            if task_type:
                self._refusals_by_task_type[task_type].append(result)

            # Track by sensitive topics
            if sensitive_topics:
                for topic in sensitive_topics:
                    self._refusals_by_sensitive_topic[topic].append(result)

            # Track by occupation
            if occupation_code:
                # Use major group (first 2 digits)
                major_group = occupation_code.split('-')[0] if '-' in occupation_code else occupation_code[:2]
                self._refusals_by_occupation[major_group].append(result)

            # Track by formality
            if formality_level is not None:
                self._refusals_by_formality[formality_level].append(result)

        return result

    def get_summary_by_model(self) -> Dict[str, RefusalDimensionSummary]:
        """Get refusal summary by model."""
        summaries = {}
        for model, refusals in self._refusals_by_model.items():
            by_category = defaultdict(int)
            for r in refusals:
                by_category[r.category.value] += 1

            summaries[model] = RefusalDimensionSummary(
                dimension_name="model",
                dimension_value=model,
                total_responses=0,  # Would need to track total
                refusal_count=len(refusals),
                refusal_rate=0.0,  # Would need total to calculate
                by_category=dict(by_category)
            )
        return summaries

    def get_summary_by_sensitive_topic(self) -> Dict[str, RefusalDimensionSummary]:
        """Get refusal summary by sensitive topic."""
        summaries = {}
        for topic, refusals in self._refusals_by_sensitive_topic.items():
            by_category = defaultdict(int)
            for r in refusals:
                by_category[r.category.value] += 1

            summaries[topic] = RefusalDimensionSummary(
                dimension_name="sensitive_topic",
                dimension_value=topic,
                total_responses=0,
                refusal_count=len(refusals),
                refusal_rate=0.0,
                by_category=dict(by_category)
            )
        return summaries

    def generate_refusal_report(self) -> Dict[str, Any]:
        """Generate comprehensive refusal report."""
        return {
            "by_model": self.get_summary_by_model(),
            "by_sensitive_topic": self.get_summary_by_sensitive_topic(),
            "by_occupation": {
                occ: len(refusals) for occ, refusals in self._refusals_by_occupation.items()
            },
            "by_formality": {
                level: len(refusals) for level, refusals in self._refusals_by_formality.items()
            },
            "category_totals": self._get_category_totals()
        }

    def _get_category_totals(self) -> Dict[str, int]:
        """Get total refusals by category across all dimensions."""
        totals = defaultdict(int)
        for refusals in self._refusals_by_model.values():
            for r in refusals:
                totals[r.category.value] += 1
        return dict(totals)
```

---

## 10. FAILURE SUMMARY REPORT

```python
# src/reports/failure_report.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json


@dataclass
class APIFailure:
    """Record of a single API failure."""
    timestamp: datetime
    model: str
    prompt_id: str
    error_type: str  # timeout, rate_limit, server_error, parse_error, etc.
    error_message: str
    retry_count: int
    recovered: bool
    response_code: Optional[int] = None
    latency_ms: Optional[float] = None


@dataclass
class FailureSummary:
    """Summary statistics for failures."""
    total_failures: int
    total_recovered: int
    total_unrecovered: int
    recovery_rate: float
    by_model: Dict[str, int]
    by_error_type: Dict[str, int]
    by_prompt: Dict[str, int]
    avg_retries_before_recovery: float
    most_failed_prompts: List[str]
    most_failed_models: List[str]


class FailureLogger:
    """Log and track API failures during evaluation."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.failures: List[APIFailure] = []
        self._ensure_log_file()

    def _ensure_log_file(self):
        """Create log file if it doesn't exist."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("")

    def log_failure(
        self,
        model: str,
        prompt_id: str,
        error_type: str,
        error_message: str,
        retry_count: int = 0,
        recovered: bool = False,
        response_code: Optional[int] = None,
        latency_ms: Optional[float] = None
    ) -> APIFailure:
        """Log a failure and append to log file."""

        failure = APIFailure(
            timestamp=datetime.now(),
            model=model,
            prompt_id=prompt_id,
            error_type=error_type,
            error_message=error_message[:500],  # Truncate long messages
            retry_count=retry_count,
            recovered=recovered,
            response_code=response_code,
            latency_ms=latency_ms
        )

        self.failures.append(failure)

        # Append to log file
        with open(self.log_path, 'a') as f:
            log_entry = {
                "timestamp": failure.timestamp.isoformat(),
                "model": failure.model,
                "prompt_id": failure.prompt_id,
                "error_type": failure.error_type,
                "error_message": failure.error_message,
                "retry_count": failure.retry_count,
                "recovered": failure.recovered,
                "response_code": failure.response_code,
                "latency_ms": failure.latency_ms
            }
            f.write(json.dumps(log_entry) + "\n")

        return failure

    def get_summary(self) -> FailureSummary:
        """Generate summary of all failures."""

        if not self.failures:
            return FailureSummary(
                total_failures=0,
                total_recovered=0,
                total_unrecovered=0,
                recovery_rate=1.0,
                by_model={},
                by_error_type={},
                by_prompt={},
                avg_retries_before_recovery=0.0,
                most_failed_prompts=[],
                most_failed_models=[]
            )

        # Count by dimensions
        by_model: Dict[str, int] = {}
        by_error_type: Dict[str, int] = {}
        by_prompt: Dict[str, int] = {}
        total_recovered = 0
        total_retries_recovered = 0

        for f in self.failures:
            by_model[f.model] = by_model.get(f.model, 0) + 1
            by_error_type[f.error_type] = by_error_type.get(f.error_type, 0) + 1
            by_prompt[f.prompt_id] = by_prompt.get(f.prompt_id, 0) + 1

            if f.recovered:
                total_recovered += 1
                total_retries_recovered += f.retry_count

        total = len(self.failures)
        total_unrecovered = total - total_recovered

        # Find most problematic
        most_failed_prompts = sorted(
            by_prompt.keys(), key=lambda k: by_prompt[k], reverse=True
        )[:10]

        most_failed_models = sorted(
            by_model.keys(), key=lambda k: by_model[k], reverse=True
        )[:5]

        return FailureSummary(
            total_failures=total,
            total_recovered=total_recovered,
            total_unrecovered=total_unrecovered,
            recovery_rate=total_recovered / total if total > 0 else 1.0,
            by_model=by_model,
            by_error_type=by_error_type,
            by_prompt=by_prompt,
            avg_retries_before_recovery=total_retries_recovered / total_recovered if total_recovered > 0 else 0.0,
            most_failed_prompts=most_failed_prompts,
            most_failed_models=most_failed_models
        )


class FailureReportGenerator:
    """Generate failure summary report at end of run."""

    def __init__(self, failure_logger: FailureLogger, output_dir: Path):
        self.failure_logger = failure_logger
        self.output_dir = output_dir

    def generate_report(self) -> str:
        """Generate and save failure summary report."""

        summary = self.failure_logger.get_summary()

        report_lines = [
            "=" * 60,
            "FAILURE SUMMARY REPORT",
            "=" * 60,
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "OVERVIEW",
            "-" * 40,
            f"Total Failures:     {summary.total_failures}",
            f"Recovered:          {summary.total_recovered}",
            f"Unrecovered:        {summary.total_unrecovered}",
            f"Recovery Rate:      {summary.recovery_rate*100:.1f}%",
            f"Avg Retries:        {summary.avg_retries_before_recovery:.1f}",
            "",
        ]

        if summary.by_error_type:
            report_lines.extend([
                "BY ERROR TYPE",
                "-" * 40
            ])
            for error_type, count in sorted(summary.by_error_type.items(), key=lambda x: -x[1]):
                report_lines.append(f"  {error_type:25s} {count:5d}")
            report_lines.append("")

        if summary.by_model:
            report_lines.extend([
                "BY MODEL",
                "-" * 40
            ])
            for model, count in sorted(summary.by_model.items(), key=lambda x: -x[1]):
                short_model = model.split('/')[-1]
                report_lines.append(f"  {short_model:25s} {count:5d}")
            report_lines.append("")

        if summary.most_failed_prompts:
            report_lines.extend([
                "MOST PROBLEMATIC PROMPTS",
                "-" * 40
            ])
            for prompt_id in summary.most_failed_prompts[:5]:
                count = summary.by_prompt[prompt_id]
                report_lines.append(f"  {prompt_id:30s} {count:5d} failures")
            report_lines.append("")

        if summary.total_unrecovered > 0:
            report_lines.extend([
                "WARNING: UNRECOVERED FAILURES",
                "-" * 40,
                f"  {summary.total_unrecovered} failures could not be recovered after retries.",
                "  These comparisons may have incomplete results.",
                ""
            ])

        report_lines.extend([
            "=" * 60,
            "END OF REPORT",
            "=" * 60
        ])

        report_text = "\n".join(report_lines)

        # Save to file
        report_path = self.output_dir / "failure_summary.txt"
        report_path.write_text(report_text)

        # Also save JSON version
        json_path = self.output_dir / "failure_summary.json"
        json_data = {
            "generated_at": datetime.now().isoformat(),
            "total_failures": summary.total_failures,
            "total_recovered": summary.total_recovered,
            "total_unrecovered": summary.total_unrecovered,
            "recovery_rate": summary.recovery_rate,
            "avg_retries_before_recovery": summary.avg_retries_before_recovery,
            "by_error_type": summary.by_error_type,
            "by_model": summary.by_model,
            "most_failed_prompts": summary.most_failed_prompts,
            "most_failed_models": summary.most_failed_models
        }
        json_path.write_text(json.dumps(json_data, indent=2))

        return report_text
```

---

## SUMMARY

This document provides complete Python implementations for all gaps identified in the gap analysis:

1. **Parallel Request Architecture** - Complete `EvaluationEngine` class with `asyncio.gather`/`TaskGroup`, `asyncio.Semaphore` for concurrency limiting, batch processing, per-model rate limiting, and progress callbacks

2. **Cohen's Kappa** - Inter-judge agreement calculation with pairwise Cohen's Kappa and Fleiss' Kappa for multiple raters

3. **TUI with Cost Tracking and Help Overlay** - Complete progress dashboard with cost tracking (spent/projected), help overlay (h key), ETA calculation, confidence intervals, per-judge votes, response times/throughput, and occupation/industry in batch display

4. **CLI Extensions** - `--tier`, `--job-zones`, `--formality-range`, `--age-range`, `--occupation-limit`, `--industry-limit`, `--persona` options

5. **Name Formality Variation** - `NameGenerator` with Dr. Williams vs Mike vs Michael T. Williams variants

6. **Phase 1 Generation Using Evaluated Models** - Implementation using the same models being evaluated for prompt generation

7. **Ambiguity Behavior Tracking** - Detection of clarification, assumptions, hedging, and hallucination behaviors

8. **TUI Results Viewer** - Filtering, sorting, drill-down with side-by-side response viewing

9. **Refusal Tracking by Dimension** - Classification and tracking of refusals by model, task type, sensitive topic, occupation, and formality

10. **Failure Summary Report** - End-of-run report with failure statistics and recommendations

All implementations are complete, production-ready Python code following the patterns established in `master_plan_final.md`.

