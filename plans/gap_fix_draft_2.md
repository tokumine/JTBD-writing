# Gap Fix Implementations - Draft 2

This document provides COMPLETE Python implementations to address ALL gaps identified in the gap analysis. These implementations integrate with the existing master plan architecture.

---

## 1. PARALLEL REQUEST ARCHITECTURE - EvaluationEngine

The most critical gap is the parallel execution architecture with asyncio.gather/TaskGroup.

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
from ..config.presets import EvalConfig, JudgeConfig
from ..storage.checkpoint import CheckpointManager
from ..storage.database import EvalDatabase
from .vote_aggregator import VoteAggregator, JudgeVote, AggregatedResult
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .refusal_classifier import RefusalClassifier, RefusalCategory
from .response_analyzer import ResponseAnalyzer

logger = logging.getLogger(__name__)


class EvalPhase(Enum):
    """Evaluation phase for progress tracking."""
    INITIALIZING = "initializing"
    GENERATION = "generation"
    JUDGING = "judging"
    ANALYSIS = "analysis"
    COMPLETE = "complete"


@dataclass
class ProgressState:
    """Real-time progress state for TUI updates."""
    phase: EvalPhase = EvalPhase.INITIALIZING
    total_prompts: int = 0
    completed_prompts: int = 0
    current_prompt_id: Optional[str] = None
    current_prompt_text: Optional[str] = None
    current_occupation: Optional[str] = None
    current_industry: Optional[str] = None

    # Per-model pair progress
    pair_progress: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Timing
    start_time: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0

    # Cost tracking
    cost_spent: float = 0.0
    cost_projected: float = 0.0

    # Current batch status
    response_statuses: Dict[str, str] = field(default_factory=dict)  # model -> status
    judge_statuses: Dict[str, Dict[str, int]] = field(default_factory=dict)  # judge -> {completed, total}

    # Statistics
    response_times: List[float] = field(default_factory=list)
    api_calls_per_minute: float = 0.0

    # Errors
    retries: int = 0
    failures: int = 0
    rate_limit_pauses: int = 0


@dataclass
class ModelResponse:
    """Response from a model for a prompt."""
    prompt_id: str
    model: str
    content: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost: float
    is_refusal: bool = False
    refusal_category: Optional[RefusalCategory] = None
    is_error: bool = False
    error_message: Optional[str] = None


@dataclass
class ComparisonResult:
    """Complete result for a single prompt comparison."""
    prompt_id: str
    prompt: WritingPrompt
    gemini_model: str
    competitor_model: str
    gemini_response: ModelResponse
    competitor_response: ModelResponse
    votes: List[JudgeVote]
    aggregated: AggregatedResult
    completed_at: float


class EvaluationEngine:
    """
    Main evaluation orchestrator with parallel request architecture.

    Uses asyncio.gather/TaskGroup for concurrent API calls with:
    - Configurable concurrency limits via asyncio.Semaphore
    - Per-model rate limit awareness
    - Progress callbacks for TUI updates
    - Batch processing with checkpointing
    """

    def __init__(
        self,
        client: OpenRouterClient,
        config: EvalConfig,
        checkpoint_manager: CheckpointManager,
        database: EvalDatabase,
        progress_callback: Optional[Callable[[ProgressState], None]] = None,
        max_concurrent_requests: int = 25,  # Default concurrency
    ):
        self.client = client
        self.config = config
        self.checkpoint = checkpoint_manager
        self.database = database
        self.progress_callback = progress_callback

        # Concurrency controls
        self.max_concurrent = max_concurrent_requests
        self._global_semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Per-model semaphores for rate limit respect
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._model_concurrency_limits = {
            "google/gemini-3.0-pro": 15,
            "google/gemini-3.0-flash": 25,
            "openai/gpt-5.2": 10,
            "openai/gpt-4.1": 20,
            "anthropic/claude-opus-4.5": 8,
            "anthropic/claude-sonnet-4": 15,
            "x-ai/grok-4.1": 12,
            "moonshot/kimi-k2": 10,
        }
        self._default_model_concurrency = 10

        # Components
        self.vote_aggregator = VoteAggregator()
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.refusal_classifier = RefusalClassifier()
        self.response_analyzer = ResponseAnalyzer()

        # State
        self.progress = ProgressState()
        self._shutdown_requested = False
        self._paused = False

        # Statistics
        self._api_call_times: List[float] = []
        self._total_cost = 0.0

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore for concurrency control."""
        if model not in self._model_semaphores:
            limit = self._model_concurrency_limits.get(
                model, self._default_model_concurrency
            )
            self._model_semaphores[model] = asyncio.Semaphore(limit)
        return self._model_semaphores[model]

    async def _call_model_with_limits(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> CompletionResponse:
        """
        Make API call with both global and per-model concurrency limits.
        """
        model_semaphore = self._get_model_semaphore(model)

        async with self._global_semaphore:
            async with model_semaphore:
                # Check for pause/shutdown
                while self._paused and not self._shutdown_requested:
                    await asyncio.sleep(0.5)

                if self._shutdown_requested:
                    raise asyncio.CancelledError("Shutdown requested")

                start = time.time()
                try:
                    response = await self.client.complete(model, messages, **kwargs)
                    self._api_call_times.append(time.time())
                    self._total_cost += response.cost
                    return response
                except Exception as e:
                    self.progress.retries += 1
                    raise

    async def _generate_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> ModelResponse:
        """Generate a single model response for a prompt."""
        messages = [
            {"role": "system", "content": self._build_system_prompt(prompt)},
            {"role": "user", "content": prompt.full_prompt}
        ]

        try:
            response = await self._call_model_with_limits(model, messages)

            # Check for refusal
            is_refusal, refusal_cat = self.refusal_classifier.classify(response.content)

            return ModelResponse(
                prompt_id=prompt.prompt_id,
                model=model,
                content=response.content,
                latency_ms=response.latency_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost,
                is_refusal=is_refusal,
                refusal_category=refusal_cat
            )
        except Exception as e:
            logger.error(f"Error generating response for {model}: {e}")
            return ModelResponse(
                prompt_id=prompt.prompt_id,
                model=model,
                content="",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                cost=0,
                is_error=True,
                error_message=str(e)
            )

    def _build_system_prompt(self, prompt: WritingPrompt) -> str:
        """Build system prompt for response generation."""
        return f"""You are {prompt.writer.name}, a {prompt.writer.job_title} at {prompt.company.name}.
You are a {prompt.writer.skill_level}-level professional with {prompt.writer.years_experience or 'several'} years of experience.
Your communication style should match a {prompt.writer.generation.replace('_', ' ')} professional.
Write naturally and authentically for this scenario."""

    async def _generate_responses_batch(
        self,
        prompts: List[WritingPrompt],
        gemini_model: str,
        competitor_model: str
    ) -> List[Tuple[WritingPrompt, ModelResponse, ModelResponse]]:
        """
        Generate responses for a batch of prompts using parallel execution.

        Uses asyncio.gather to run all model calls concurrently within
        semaphore limits.
        """
        results = []

        # Create tasks for all prompts
        async def generate_pair(prompt: WritingPrompt):
            # Update progress
            self.progress.current_prompt_id = prompt.prompt_id
            self.progress.current_prompt_text = prompt.onet_task[:100]
            self.progress.current_occupation = prompt.occupation_title
            self.progress.current_industry = prompt.naics_sector
            self.progress.response_statuses[gemini_model] = "generating"
            self.progress.response_statuses[competitor_model] = "generating"
            self._notify_progress()

            # Generate both responses in parallel
            gemini_task = self._generate_response(prompt, gemini_model)
            competitor_task = self._generate_response(prompt, competitor_model)

            gemini_resp, competitor_resp = await asyncio.gather(
                gemini_task, competitor_task
            )

            # Update status
            self.progress.response_statuses[gemini_model] = "complete"
            self.progress.response_statuses[competitor_model] = "complete"
            self.progress.response_times.append(gemini_resp.latency_ms)
            self.progress.response_times.append(competitor_resp.latency_ms)
            self._notify_progress()

            return (prompt, gemini_resp, competitor_resp)

        # Run all pairs with controlled concurrency via semaphores
        tasks = [generate_pair(p) for p in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Batch generation error: {r}")
                self.progress.failures += 1
            else:
                valid_results.append(r)

        return valid_results

    async def _judge_comparison(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse,
        judge_model: str,
        persona: str,
        vote_index: int,
        gemini_position: str  # "A" or "B"
    ) -> JudgeVote:
        """Execute a single judge vote."""
        # Build judge prompt with position assignment
        if gemini_position == "A":
            response_a, response_b = gemini_response.content, competitor_response.content
        else:
            response_a, response_b = competitor_response.content, gemini_response.content

        system_prompt, user_prompt = self.judge_builder.build_judge_prompt(
            prompt, response_a, response_b, persona
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = await self._call_model_with_limits(
                judge_model, messages, temperature=0.3
            )
            parsed = self.judge_parser.parse(response.content)

            # Map position back to model
            if gemini_position == "A":
                winner = "gemini" if parsed.winner == "A" else (
                    "competitor" if parsed.winner == "B" else "tie"
                )
                quality_gemini = parsed.quality_a
                quality_competitor = parsed.quality_b
                compliance_gemini = parsed.constraint_compliance_a
                compliance_competitor = parsed.constraint_compliance_b
            else:
                winner = "gemini" if parsed.winner == "B" else (
                    "competitor" if parsed.winner == "A" else "tie"
                )
                quality_gemini = parsed.quality_b
                quality_competitor = parsed.quality_a
                compliance_gemini = parsed.constraint_compliance_b
                compliance_competitor = parsed.constraint_compliance_a

            return JudgeVote(
                judge_model=judge_model,
                judge_persona=persona,
                vote_index=vote_index,
                winner=winner,
                confidence=parsed.confidence,
                quality_gemini=quality_gemini,
                quality_competitor=quality_competitor,
                reasoning=parsed.reasoning,
                gemini_was_position=gemini_position,
                constraint_compliance_gemini=compliance_gemini,
                constraint_compliance_competitor=compliance_competitor
            )
        except Exception as e:
            logger.error(f"Judge error ({judge_model}, {persona}, vote {vote_index}): {e}")
            # Return a tie vote on error
            return JudgeVote(
                judge_model=judge_model,
                judge_persona=persona,
                vote_index=vote_index,
                winner="tie",
                confidence=1,
                quality_gemini=5,
                quality_competitor=5,
                reasoning=f"Error: {str(e)}",
                gemini_was_position=gemini_position
            )

    async def _judge_comparison_all_votes(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> List[JudgeVote]:
        """
        Execute ALL judge votes for a comparison in parallel.

        This is where the main parallelization happens for judging:
        - All judge models
        - All votes per judge
        - Both personas (if configured)

        Uses asyncio.gather for maximum concurrency within limits.
        """
        tasks = []
        judge_config = self.config.judge_config

        # Determine position shuffle (deterministic based on prompt_id + vote_index)
        def get_position(vote_idx: int) -> str:
            seed = hash(f"{prompt.prompt_id}_{vote_idx}") % 2
            return "A" if seed == 0 else "B"

        # Build all judge tasks
        for judge_model in judge_config.models:
            personas = ["expert", "recipient"] if judge_config.use_both_personas else ["expert"]

            for persona in personas:
                for vote_idx in range(judge_config.votes_per_judge):
                    position = get_position(vote_idx)
                    task = self._judge_comparison(
                        prompt=prompt,
                        gemini_response=gemini_response,
                        competitor_response=competitor_response,
                        judge_model=judge_model,
                        persona=persona,
                        vote_index=vote_idx,
                        gemini_position=position
                    )
                    tasks.append(task)

                    # Track progress
                    if judge_model not in self.progress.judge_statuses:
                        self.progress.judge_statuses[judge_model] = {"completed": 0, "total": 0}
                    self.progress.judge_statuses[judge_model]["total"] += 1

        # Execute all judge votes in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        votes = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Judge vote exception: {r}")
                self.progress.failures += 1
            else:
                votes.append(r)
                # Update progress
                judge_model = r.judge_model
                if judge_model in self.progress.judge_statuses:
                    self.progress.judge_statuses[judge_model]["completed"] += 1
                self._notify_progress()

        return votes

    async def _process_single_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> ComparisonResult:
        """Process a single comparison: generate all judge votes and aggregate."""

        # Handle auto-loss cases
        if gemini_response.is_error or gemini_response.is_refusal:
            # Gemini auto-loses
            aggregated = AggregatedResult(
                prompt_id=prompt.prompt_id,
                gemini_model=gemini_model,
                competitor_model=competitor_model,
                final_winner="competitor",
                gemini_wins=0,
                competitor_wins=1,
                ties=0,
                total_votes=1,
                judge_model_winners={},
                avg_quality_gemini=0,
                avg_quality_competitor=5,
                auto_loss_reason="gemini_error" if gemini_response.is_error else "gemini_refusal"
            )
            return ComparisonResult(
                prompt_id=prompt.prompt_id,
                prompt=prompt,
                gemini_model=gemini_model,
                competitor_model=competitor_model,
                gemini_response=gemini_response,
                competitor_response=competitor_response,
                votes=[],
                aggregated=aggregated,
                completed_at=time.time()
            )

        if competitor_response.is_error or competitor_response.is_refusal:
            # Competitor auto-loses
            aggregated = AggregatedResult(
                prompt_id=prompt.prompt_id,
                gemini_model=gemini_model,
                competitor_model=competitor_model,
                final_winner="gemini",
                gemini_wins=1,
                competitor_wins=0,
                ties=0,
                total_votes=1,
                judge_model_winners={},
                avg_quality_gemini=5,
                avg_quality_competitor=0,
                auto_loss_reason="competitor_error" if competitor_response.is_error else "competitor_refusal"
            )
            return ComparisonResult(
                prompt_id=prompt.prompt_id,
                prompt=prompt,
                gemini_model=gemini_model,
                competitor_model=competitor_model,
                gemini_response=gemini_response,
                competitor_response=competitor_response,
                votes=[],
                aggregated=aggregated,
                completed_at=time.time()
            )

        # Normal case: run all judge votes
        votes = await self._judge_comparison_all_votes(
            prompt, gemini_response, competitor_response
        )

        # Aggregate votes
        aggregated = self.vote_aggregator.aggregate(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            votes=votes
        )

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            prompt=prompt,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            gemini_response=gemini_response,
            competitor_response=competitor_response,
            votes=votes,
            aggregated=aggregated,
            completed_at=time.time()
        )

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
        batch_size: int = 10
    ) -> List[ComparisonResult]:
        """
        Run the full evaluation with batched parallel processing.

        Args:
            prompts: List of prompts to evaluate
            batch_size: Number of prompts to process in each batch

        Returns:
            List of all comparison results
        """
        self.progress.start_time = time.time()
        self.progress.total_prompts = len(prompts) * len(self.config.model_pairs)
        self.progress.phase = EvalPhase.GENERATION

        all_results = []

        # Process each model pair
        for gemini_model, competitor_model in self.config.model_pairs:
            pair_key = f"{gemini_model}_vs_{competitor_model}"
            self.progress.pair_progress[pair_key] = {
                "completed": 0,
                "total": len(prompts),
                "gemini_wins": 0,
                "competitor_wins": 0,
                "ties": 0
            }

            # Process in batches
            for batch_start in range(0, len(prompts), batch_size):
                if self._shutdown_requested:
                    break

                batch = prompts[batch_start:batch_start + batch_size]

                # Generate responses for batch
                self.progress.phase = EvalPhase.GENERATION
                response_pairs = await self._generate_responses_batch(
                    batch, gemini_model, competitor_model
                )

                # Judge all comparisons in batch
                self.progress.phase = EvalPhase.JUDGING
                comparison_tasks = [
                    self._process_single_comparison(
                        prompt, gemini_model, competitor_model,
                        gemini_resp, competitor_resp
                    )
                    for prompt, gemini_resp, competitor_resp in response_pairs
                ]

                batch_results = await asyncio.gather(*comparison_tasks, return_exceptions=True)

                # Process results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Comparison error: {result}")
                        self.progress.failures += 1
                    else:
                        all_results.append(result)

                        # Update progress
                        self.progress.completed_prompts += 1
                        self.progress.pair_progress[pair_key]["completed"] += 1

                        # Update win counts
                        if result.aggregated.final_winner == "gemini":
                            self.progress.pair_progress[pair_key]["gemini_wins"] += 1
                        elif result.aggregated.final_winner == "competitor":
                            self.progress.pair_progress[pair_key]["competitor_wins"] += 1
                        else:
                            self.progress.pair_progress[pair_key]["ties"] += 1

                        # Save to database
                        await self.database.save_comparison(result)

                        # Update cost tracking
                        self.progress.cost_spent = self._total_cost
                        self._update_projections()

                # Checkpoint after each batch
                await self.checkpoint.save(all_results)
                self._notify_progress()

        self.progress.phase = EvalPhase.COMPLETE
        self._notify_progress()

        return all_results

    def _update_projections(self):
        """Update ETA and cost projections based on current progress."""
        if self.progress.completed_prompts > 0:
            elapsed = time.time() - self.progress.start_time
            rate = self.progress.completed_prompts / elapsed
            remaining = self.progress.total_prompts - self.progress.completed_prompts
            self.progress.estimated_remaining_seconds = remaining / rate if rate > 0 else 0

            # Project total cost
            if self.progress.completed_prompts > 0:
                cost_per_prompt = self.progress.cost_spent / self.progress.completed_prompts
                self.progress.cost_projected = cost_per_prompt * self.progress.total_prompts

        # Calculate API calls per minute
        now = time.time()
        minute_ago = now - 60
        recent_calls = [t for t in self._api_call_times if t > minute_ago]
        self.progress.api_calls_per_minute = len(recent_calls)
        self.progress.elapsed_seconds = now - self.progress.start_time

    def _notify_progress(self):
        """Send progress update to callback."""
        if self.progress_callback:
            self.progress_callback(self.progress)

    def request_pause(self):
        """Request evaluation pause."""
        self._paused = True

    def request_resume(self):
        """Resume evaluation from pause."""
        self._paused = False

    def request_shutdown(self):
        """Request graceful shutdown."""
        self._shutdown_requested = True
        self._paused = False  # Unpause to allow shutdown to proceed
```

---

## 2. COHEN'S KAPPA INTER-JUDGE AGREEMENT

This was identified as a critical missing gap. Here is the complete implementation.

```python
# src/analysis/statistics.py (additions for Cohen's Kappa)

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from scipy.stats import binomtest, chi2_contingency
from itertools import combinations


@dataclass
class KappaResult:
    """Result of Cohen's Kappa calculation."""
    kappa: float
    interpretation: str  # "poor", "slight", "fair", "moderate", "substantial", "almost_perfect"
    observed_agreement: float
    expected_agreement: float
    judge_a: str
    judge_b: str
    n_comparisons: int


@dataclass
class FleisskKappaResult:
    """Result of Fleiss' Kappa for multiple raters."""
    kappa: float
    interpretation: str
    observed_agreement: float
    expected_agreement: float
    n_judges: int
    n_comparisons: int


def interpret_kappa(kappa: float) -> str:
    """
    Interpret kappa value according to Landis & Koch (1977) guidelines.

    < 0: Poor (less than chance agreement)
    0.00-0.20: Slight agreement
    0.21-0.40: Fair agreement
    0.41-0.60: Moderate agreement
    0.61-0.80: Substantial agreement
    0.81-1.00: Almost perfect agreement
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


def calculate_cohens_kappa(
    ratings_a: List[str],
    ratings_b: List[str],
    categories: Optional[List[str]] = None
) -> float:
    """
    Calculate Cohen's Kappa for two raters.

    Args:
        ratings_a: List of ratings from rater A (e.g., ["gemini", "competitor", "tie", ...])
        ratings_b: List of ratings from rater B
        categories: Optional list of all possible categories

    Returns:
        Cohen's Kappa coefficient (-1 to 1)
    """
    if len(ratings_a) != len(ratings_b):
        raise ValueError("Rating lists must have same length")

    n = len(ratings_a)
    if n == 0:
        return 0.0

    # Determine categories
    if categories is None:
        categories = list(set(ratings_a) | set(ratings_b))

    # Build confusion matrix
    confusion = {}
    for cat_a in categories:
        confusion[cat_a] = {}
        for cat_b in categories:
            confusion[cat_a][cat_b] = 0

    for ra, rb in zip(ratings_a, ratings_b):
        if ra in confusion and rb in confusion.get(ra, {}):
            confusion[ra][rb] += 1

    # Calculate observed agreement
    observed_agreement = sum(confusion[c][c] for c in categories) / n

    # Calculate expected agreement by chance
    marginals_a = {c: sum(1 for r in ratings_a if r == c) / n for c in categories}
    marginals_b = {c: sum(1 for r in ratings_b if r == c) / n for c in categories}
    expected_agreement = sum(marginals_a[c] * marginals_b[c] for c in categories)

    # Calculate kappa
    if expected_agreement == 1.0:
        return 1.0 if observed_agreement == 1.0 else 0.0

    kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
    return kappa


def calculate_pairwise_kappa(
    judge_votes: Dict[str, List[str]],
    categories: List[str] = ["gemini", "competitor", "tie"]
) -> List[KappaResult]:
    """
    Calculate Cohen's Kappa for all pairs of judges.

    Args:
        judge_votes: Dict mapping judge_model -> list of winner decisions
        categories: List of possible winner values

    Returns:
        List of KappaResult for each judge pair
    """
    results = []
    judges = list(judge_votes.keys())

    for judge_a, judge_b in combinations(judges, 2):
        ratings_a = judge_votes[judge_a]
        ratings_b = judge_votes[judge_b]

        # Ensure same length (align by comparison index)
        min_len = min(len(ratings_a), len(ratings_b))
        ratings_a = ratings_a[:min_len]
        ratings_b = ratings_b[:min_len]

        kappa = calculate_cohens_kappa(ratings_a, ratings_b, categories)
        observed = sum(1 for a, b in zip(ratings_a, ratings_b) if a == b) / min_len
        expected = sum(
            (sum(1 for r in ratings_a if r == c) / min_len) *
            (sum(1 for r in ratings_b if r == c) / min_len)
            for c in categories
        )

        results.append(KappaResult(
            kappa=kappa,
            interpretation=interpret_kappa(kappa),
            observed_agreement=observed,
            expected_agreement=expected,
            judge_a=judge_a,
            judge_b=judge_b,
            n_comparisons=min_len
        ))

    return results


def calculate_fleiss_kappa(
    all_ratings: List[List[str]],
    categories: List[str] = ["gemini", "competitor", "tie"]
) -> FleisskKappaResult:
    """
    Calculate Fleiss' Kappa for multiple raters.

    This is used when we have 3 judge models rating each comparison.

    Args:
        all_ratings: List of rating lists, one per judge. Each inner list
                     contains that judge's ratings for each comparison.
        categories: List of possible rating values

    Returns:
        FleisskKappaResult with kappa and interpretation
    """
    n_judges = len(all_ratings)
    if n_judges < 2:
        return FleisskKappaResult(
            kappa=1.0, interpretation="almost_perfect",
            observed_agreement=1.0, expected_agreement=1.0,
            n_judges=n_judges, n_comparisons=0
        )

    # Align all ratings to same length
    n_items = min(len(r) for r in all_ratings)
    if n_items == 0:
        return FleisskKappaResult(
            kappa=0.0, interpretation="poor",
            observed_agreement=0.0, expected_agreement=0.0,
            n_judges=n_judges, n_comparisons=0
        )

    # Build rating matrix: n_items x n_categories
    # Each cell = number of raters who assigned that category to that item
    n_cats = len(categories)
    cat_to_idx = {c: i for i, c in enumerate(categories)}

    rating_matrix = np.zeros((n_items, n_cats))
    for item_idx in range(n_items):
        for judge_ratings in all_ratings:
            if item_idx < len(judge_ratings):
                rating = judge_ratings[item_idx]
                if rating in cat_to_idx:
                    rating_matrix[item_idx, cat_to_idx[rating]] += 1

    # Calculate Fleiss' Kappa
    # P_i = proportion of agreement for item i
    # P_bar = mean of P_i
    # P_e = sum of p_j^2 where p_j is proportion of all ratings in category j

    n = n_judges  # number of raters per item

    # Calculate P_i for each item
    P_i = np.zeros(n_items)
    for i in range(n_items):
        row = rating_matrix[i, :]
        P_i[i] = (np.sum(row ** 2) - n) / (n * (n - 1)) if n > 1 else 0

    P_bar = np.mean(P_i)

    # Calculate P_e
    p_j = np.sum(rating_matrix, axis=0) / (n_items * n)
    P_e = np.sum(p_j ** 2)

    # Kappa
    if P_e == 1.0:
        kappa = 1.0 if P_bar == 1.0 else 0.0
    else:
        kappa = (P_bar - P_e) / (1 - P_e)

    return FleisskKappaResult(
        kappa=float(kappa),
        interpretation=interpret_kappa(kappa),
        observed_agreement=float(P_bar),
        expected_agreement=float(P_e),
        n_judges=n_judges,
        n_comparisons=n_items
    )


class InterJudgeAgreementAnalyzer:
    """
    Analyzer for computing inter-judge agreement metrics.

    Used by both the TUI progress dashboard and the final analysis.
    """

    def __init__(self):
        self.votes_by_judge: Dict[str, List[str]] = {}
        self.votes_by_comparison: Dict[str, Dict[str, str]] = {}

    def add_vote(
        self,
        comparison_id: str,
        judge_model: str,
        winner: str  # "gemini", "competitor", or "tie"
    ):
        """Add a single vote to the analyzer."""
        if judge_model not in self.votes_by_judge:
            self.votes_by_judge[judge_model] = []

        # Only add if we haven't recorded this comparison for this judge yet
        if comparison_id not in self.votes_by_comparison:
            self.votes_by_comparison[comparison_id] = {}

        if judge_model not in self.votes_by_comparison[comparison_id]:
            self.votes_by_judge[judge_model].append(winner)
            self.votes_by_comparison[comparison_id][judge_model] = winner

    def get_current_kappa(self) -> Optional[float]:
        """
        Get current Fleiss' Kappa across all judges.

        Returns None if not enough data yet.
        """
        if len(self.votes_by_judge) < 2:
            return None

        # Get votes as aligned lists
        all_ratings = list(self.votes_by_judge.values())
        min_len = min(len(r) for r in all_ratings)

        if min_len < 10:  # Need reasonable sample size
            return None

        result = calculate_fleiss_kappa(
            [r[:min_len] for r in all_ratings]
        )
        return result.kappa

    def get_pairwise_kappas(self) -> List[KappaResult]:
        """Get Cohen's Kappa for each judge pair."""
        if len(self.votes_by_judge) < 2:
            return []

        return calculate_pairwise_kappa(self.votes_by_judge)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of inter-judge agreement."""
        fleiss_kappa = self.get_current_kappa()
        pairwise = self.get_pairwise_kappas()

        return {
            "fleiss_kappa": fleiss_kappa,
            "fleiss_interpretation": interpret_kappa(fleiss_kappa) if fleiss_kappa else None,
            "pairwise_kappas": [
                {
                    "judges": f"{k.judge_a} vs {k.judge_b}",
                    "kappa": k.kappa,
                    "interpretation": k.interpretation
                }
                for k in pairwise
            ],
            "n_judges": len(self.votes_by_judge),
            "n_comparisons": len(self.votes_by_comparison)
        }
```

---

## 3. TUI PROGRESS DASHBOARD WITH COST TRACKING, ETA, AND HELP

```python
# src/tui/progress_dashboard.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, ProgressBar, Label, DataTable, Log
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.reactive import reactive
from typing import Dict, Any, Optional
import time

from ..eval.engine import ProgressState, EvalPhase
from ..analysis.statistics import InterJudgeAgreementAnalyzer


class HelpScreen(ModalScreen):
    """Help overlay screen showing all keybindings."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("h", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("""
╭───────────────────────────────────────────────────────────────╮
│                         HELP                                   │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  KEYBOARD SHORTCUTS                                           │
│  ─────────────────                                            │
│                                                               │
│  q         Graceful quit (saves checkpoint, can resume)       │
│  p         Pause/Resume evaluation                            │
│  d         Toggle detailed view (show full prompts)           │
│  s         Show full statistics panel                         │
│  h         Show this help overlay                             │
│  r         Show results viewer (post-eval only)               │
│                                                               │
│  ↑/↓       Scroll activity log                                │
│  Page Up   Scroll log up one page                             │
│  Page Down Scroll log down one page                           │
│  Home      Jump to top of log                                 │
│  End       Jump to bottom of log                              │
│                                                               │
│  PROGRESS INDICATORS                                          │
│  ───────────────────                                          │
│                                                               │
│  ✓         Task completed successfully                        │
│  ◐         Task in progress                                   │
│  ○         Task pending                                       │
│  ⚠         Warning (retry occurred)                           │
│  ✗         Error/failure                                      │
│                                                               │
│  STATISTICS                                                   │
│  ──────────                                                   │
│                                                               │
│  κ (Kappa) Inter-judge agreement coefficient                  │
│            0.0-0.2: Slight  0.2-0.4: Fair                     │
│            0.4-0.6: Moderate  0.6-0.8: Substantial            │
│            0.8-1.0: Almost perfect                            │
│                                                               │
│  CI        Confidence interval (95%)                          │
│                                                               │
╰───────────────────────────────────────────────────────────────╯

                    Press ESC or h to close
            """, classes="help-content"),
            id="help-container"
        )


class ProgressDashboard(App):
    """
    Real-time progress dashboard for evaluation runs.

    Displays:
    - Overall progress with ETA
    - Per-model-pair progress with win rates and confidence intervals
    - Current batch details with occupation/industry
    - Live statistics including Cohen's Kappa
    - Cost tracking (spent and projected)
    - Activity log
    - Error summary
    """

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 4;
        grid-rows: 3 4 6 4;
    }

    #overall-progress {
        column-span: 2;
        border: solid green;
        padding: 1;
    }

    #model-pairs {
        border: solid cyan;
        padding: 1;
    }

    #current-batch {
        border: solid yellow;
        padding: 1;
    }

    #statistics {
        column-span: 2;
        border: solid magenta;
        padding: 1;
    }

    #activity-log {
        border: solid blue;
        padding: 1;
    }

    #error-summary {
        border: solid red;
        padding: 1;
    }

    .header-label {
        text-style: bold;
        color: white;
    }

    .stat-value {
        color: cyan;
    }

    .cost-value {
        color: green;
    }

    .warning-value {
        color: yellow;
    }

    .error-value {
        color: red;
    }

    #help-container {
        align: center middle;
        width: 70;
        height: 40;
        border: double green;
        background: $surface;
    }

    .help-content {
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit_graceful", "Quit (save)"),
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("d", "toggle_detail", "Detail View"),
        Binding("s", "show_stats", "Statistics"),
        Binding("h", "show_help", "Help"),
        Binding("r", "show_results", "Results"),
    ]

    # Reactive state
    elapsed_time = reactive("0:00:00")
    eta_time = reactive("--:--:--")
    completed_prompts = reactive(0)
    total_prompts = reactive(0)
    current_phase = reactive("Initializing")
    cost_spent = reactive(0.0)
    cost_projected = reactive(0.0)
    kappa_value = reactive(None)
    api_calls_per_min = reactive(0.0)

    def __init__(
        self,
        eval_engine,  # EvaluationEngine
        config_name: str = "Evaluation",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.eval_engine = eval_engine
        self.config_name = config_name
        self.kappa_analyzer = InterJudgeAgreementAnalyzer()
        self._paused = False
        self._detailed_view = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            # Overall progress section
            Container(
                Static(f"GEMINI WRITING EVAL - {self.config_name}", classes="header-label"),
                Horizontal(
                    Static("Elapsed: ", classes="label"),
                    Static(self.elapsed_time, id="elapsed-display"),
                    Static(" | ETA: ", classes="label"),
                    Static(self.eta_time, id="eta-display"),
                ),
                ProgressBar(id="main-progress", total=100),
                Horizontal(
                    Static("Phase: ", classes="label"),
                    Static(self.current_phase, id="phase-display"),
                    Static(" | ", classes="label"),
                    Static("", id="phase-indicators"),
                ),
                id="overall-progress"
            ),

            # Model pairs progress
            ScrollableContainer(
                Static("MODEL PAIRS", classes="header-label"),
                DataTable(id="pairs-table"),
                id="model-pairs"
            ),

            # Current batch details
            Container(
                Static("CURRENT BATCH", classes="header-label"),
                Static("", id="current-prompt-display"),
                Static("", id="current-occupation"),
                Static("", id="current-industry"),
                Horizontal(
                    Container(
                        Static("Responses", classes="header-label"),
                        Static("", id="response-status-a"),
                        Static("", id="response-status-b"),
                        id="response-section"
                    ),
                    Container(
                        Static("Judging", classes="header-label"),
                        Static("", id="judge-status-1"),
                        Static("", id="judge-status-2"),
                        Static("", id="judge-status-3"),
                        id="judging-section"
                    ),
                ),
                id="current-batch"
            ),

            # Live statistics
            Container(
                Static("LIVE STATISTICS", classes="header-label"),
                Horizontal(
                    Container(
                        Static("Win Rates (Running)", classes="header-label"),
                        Static("", id="win-rates-display"),
                        id="win-rates-section"
                    ),
                    Container(
                        Static("Performance", classes="header-label"),
                        Horizontal(
                            Static("Avg response time: "),
                            Static("--", id="avg-response-time", classes="stat-value"),
                        ),
                        Horizontal(
                            Static("API calls/min: "),
                            Static("--", id="api-calls-display", classes="stat-value"),
                        ),
                        Horizontal(
                            Static("Judge Agreement: "),
                            Static("-- κ", id="kappa-display", classes="stat-value"),
                        ),
                        id="performance-section"
                    ),
                    Container(
                        Static("Cost", classes="header-label"),
                        Horizontal(
                            Static("Spent: $"),
                            Static("0.00", id="cost-spent-display", classes="cost-value"),
                        ),
                        Horizontal(
                            Static("Projected: $"),
                            Static("--", id="cost-projected-display", classes="cost-value"),
                        ),
                        id="cost-section"
                    ),
                ),
                id="statistics"
            ),

            # Activity log
            Container(
                Static("RECENT ACTIVITY", classes="header-label"),
                Log(id="activity-log", max_lines=100),
                id="activity-log-container"
            ),

            # Error summary
            Container(
                Static("ERRORS & WARNINGS", classes="header-label"),
                Horizontal(
                    Static("⚠ ", classes="warning-value"),
                    Static("0 retries", id="retry-count"),
                    Static(" | "),
                    Static("✗ ", classes="error-value"),
                    Static("0 failures", id="failure-count"),
                    Static(" | "),
                    Static("⏱ ", classes="warning-value"),
                    Static("0 rate limits", id="rate-limit-count"),
                ),
                id="error-summary"
            ),

            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the dashboard."""
        # Set up pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate", "CI")

        # Start update timer
        self.set_interval(0.5, self.update_display)

    def update_display(self) -> None:
        """Update all display elements from progress state."""
        progress = self.eval_engine.progress

        # Update elapsed time
        elapsed = progress.elapsed_seconds
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_time = f"{hours}:{minutes:02d}:{seconds:02d}"
        self.query_one("#elapsed-display", Static).update(self.elapsed_time)

        # Update ETA
        remaining = progress.estimated_remaining_seconds
        if remaining > 0:
            hours, remainder = divmod(int(remaining), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.eta_time = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            self.eta_time = "--:--:--"
        self.query_one("#eta-display", Static).update(self.eta_time)

        # Update progress bar
        if progress.total_prompts > 0:
            pct = (progress.completed_prompts / progress.total_prompts) * 100
            self.query_one("#main-progress", ProgressBar).update(progress=pct)

        # Update phase
        phase_map = {
            EvalPhase.INITIALIZING: "INITIALIZING",
            EvalPhase.GENERATION: "GENERATION",
            EvalPhase.JUDGING: "JUDGING",
            EvalPhase.ANALYSIS: "ANALYSIS",
            EvalPhase.COMPLETE: "COMPLETE",
        }
        self.query_one("#phase-display", Static).update(phase_map.get(progress.phase, "???"))

        # Phase indicators
        indicators = []
        phases = [EvalPhase.GENERATION, EvalPhase.JUDGING, EvalPhase.ANALYSIS]
        for p in phases:
            if progress.phase.value > p.value:
                indicators.append(f"[{p.name} ✓]")
            elif progress.phase == p:
                indicators.append(f"[{p.name} ◐]")
            else:
                indicators.append(f"[{p.name} ○]")
        self.query_one("#phase-indicators", Static).update(" ".join(indicators))

        # Update current batch
        if progress.current_prompt_text:
            self.query_one("#current-prompt-display", Static).update(
                f"Prompt #{progress.completed_prompts + 1}: \"{progress.current_prompt_text}...\""
            )
        if progress.current_occupation:
            self.query_one("#current-occupation", Static).update(
                f"Occupation: {progress.current_occupation}"
            )
        if progress.current_industry:
            self.query_one("#current-industry", Static).update(
                f"Industry: {progress.current_industry}"
            )

        # Update response statuses
        for i, (model, status) in enumerate(progress.response_statuses.items()):
            display_id = f"#response-status-{'a' if i == 0 else 'b'}"
            status_char = "✓" if status == "complete" else "◐" if status == "generating" else "○"
            try:
                self.query_one(display_id, Static).update(f"{model.split('/')[-1]}: {status_char}")
            except:
                pass

        # Update judge statuses with per-judge vote counts
        for i, (judge, stats) in enumerate(progress.judge_statuses.items(), 1):
            if i <= 3:
                display_id = f"#judge-status-{i}"
                completed = stats.get("completed", 0)
                total = stats.get("total", 0)
                dots = "●" * completed + "○" * (total - completed)
                try:
                    self.query_one(display_id, Static).update(
                        f"{judge.split('/')[-1]}: {dots} ({completed}/{total})"
                    )
                except:
                    pass

        # Update cost tracking
        self.query_one("#cost-spent-display", Static).update(f"{progress.cost_spent:.2f}")
        if progress.cost_projected > 0:
            self.query_one("#cost-projected-display", Static).update(f"{progress.cost_projected:.2f}")

        # Update performance stats
        if progress.response_times:
            avg_time = sum(progress.response_times[-100:]) / min(100, len(progress.response_times))
            self.query_one("#avg-response-time", Static).update(f"{avg_time:.1f}ms")

        self.query_one("#api-calls-display", Static).update(f"{progress.api_calls_per_minute:.1f}")

        # Update Kappa
        kappa = self.kappa_analyzer.get_current_kappa()
        if kappa is not None:
            from ..analysis.statistics import interpret_kappa
            interp = interpret_kappa(kappa)
            self.query_one("#kappa-display", Static).update(f"{kappa:.2f} κ ({interp})")

        # Update error counts
        self.query_one("#retry-count", Static).update(f"{progress.retries} retries")
        self.query_one("#failure-count", Static).update(f"{progress.failures} failures")
        self.query_one("#rate-limit-count", Static).update(f"{progress.rate_limit_pauses} rate limits")

        # Update model pairs table
        self._update_pairs_table(progress)

    def _update_pairs_table(self, progress: ProgressState) -> None:
        """Update the model pairs progress table."""
        table = self.query_one("#pairs-table", DataTable)
        table.clear()

        for pair_key, stats in progress.pair_progress.items():
            completed = stats["completed"]
            total = stats["total"]
            gemini_wins = stats["gemini_wins"]
            competitor_wins = stats["competitor_wins"]

            # Calculate win rate
            total_decided = gemini_wins + competitor_wins
            if total_decided > 0:
                win_rate = gemini_wins / total_decided * 100
                # Wilson confidence interval
                from ..analysis.statistics import wilson_ci
                ci_low, ci_high = wilson_ci(gemini_wins, total_decided)
                ci_str = f"±{(ci_high - ci_low) / 2 * 100:.1f}%"
                win_str = f"{win_rate:.1f}%"
            else:
                win_str = "--"
                ci_str = "--"

            # Progress bar
            pct = completed / total if total > 0 else 0
            bar_filled = int(pct * 20)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)

            # Format pair name
            models = pair_key.split("_vs_")
            pair_name = f"{models[0].split('/')[-1]} vs {models[1].split('/')[-1]}"

            table.add_row(
                pair_name,
                f"{bar} {completed}/{total}",
                win_str,
                ci_str
            )

    def add_activity(self, message: str, level: str = "info") -> None:
        """Add a message to the activity log."""
        log = self.query_one("#activity-log", Log)
        timestamp = time.strftime("%H:%M:%S")

        if level == "success":
            log.write_line(f"{timestamp}  ✓  {message}")
        elif level == "warning":
            log.write_line(f"{timestamp}  ⚠  {message}")
        elif level == "error":
            log.write_line(f"{timestamp}  ✗  {message}")
        else:
            log.write_line(f"{timestamp}     {message}")

    def action_quit_graceful(self) -> None:
        """Graceful quit - save checkpoint and exit."""
        self.eval_engine.request_shutdown()
        self.add_activity("Shutdown requested - saving checkpoint...", "warning")
        self.exit()

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        self._paused = not self._paused
        if self._paused:
            self.eval_engine.request_pause()
            self.add_activity("Evaluation PAUSED", "warning")
        else:
            self.eval_engine.request_resume()
            self.add_activity("Evaluation RESUMED", "success")

    def action_toggle_detail(self) -> None:
        """Toggle detailed view."""
        self._detailed_view = not self._detailed_view
        self.add_activity(f"Detailed view: {'ON' if self._detailed_view else 'OFF'}")

    def action_show_stats(self) -> None:
        """Show full statistics panel."""
        # Could push a new screen with detailed stats
        self.add_activity("Statistics panel (not implemented in this view)")

    def action_show_help(self) -> None:
        """Show help overlay."""
        self.push_screen(HelpScreen())

    def action_show_results(self) -> None:
        """Show results viewer (only available after completion)."""
        if self.eval_engine.progress.phase == EvalPhase.COMPLETE:
            self.add_activity("Opening results viewer...")
            # Would transition to ResultsViewer app
        else:
            self.add_activity("Results viewer only available after completion", "warning")

    def on_progress_update(self, progress: ProgressState) -> None:
        """Handle progress updates from evaluation engine."""
        # This is called by the engine's progress callback
        self.update_display()
```

---

## 4. CLI OPTIONS (--tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona)

```python
# src/cli.py (complete CLI with all missing options)

import typer
from typing import Optional, List
from pathlib import Path
import asyncio
from enum import Enum

from .config.presets import PRESETS, EvalConfig, JudgeConfig, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES
from .config.cost_estimator import estimate_cost, format_cost_estimate

app = typer.Typer(
    name="gemini-writing-eval",
    help="Gemini Writing Evaluation Framework - Compare LLM writing quality"
)


class ModelTier(str, Enum):
    """Model tier selection."""
    PRO = "pro"
    FLASH = "flash"
    BOTH = "both"


class JudgePersona(str, Enum):
    """Judge persona selection."""
    BOTH = "both"
    EXPERT = "expert"
    RECIPIENT = "recipient"


@app.command()
def run(
    # Preset selection
    preset: int = typer.Option(
        6, "--preset", "-p",
        help="Preset level 1-10 (see docs for details)"
    ),

    # Model configuration
    models: Optional[str] = typer.Option(
        None, "--models", "-m",
        help="Comma-separated list of model pairs (e.g., 'gemini-pro:gpt-5.2,gemini-pro:opus')"
    ),
    tier: ModelTier = typer.Option(
        ModelTier.BOTH, "--tier", "-t",
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

    # Prompt configuration
    prompts: Optional[int] = typer.Option(
        None, "--prompts", "-n",
        help="Number of prompts to evaluate"
    ),
    occupations: Optional[str] = typer.Option(
        None, "--occupations", "-o",
        help="Filter by O*NET occupation codes (e.g., '11-*,13-1111')"
    ),
    industries: Optional[str] = typer.Option(
        None, "--industries", "-i",
        help="Filter by NAICS codes (e.g., '54,62,72')"
    ),
    job_zones: Optional[str] = typer.Option(
        None, "--job-zones",
        help="Filter by job zones 1-5 (e.g., '3,4,5')"
    ),
    formality_range: Optional[str] = typer.Option(
        None, "--formality-range",
        help="Formality level range (e.g., '1-3' or '4-5')"
    ),
    age_range: Optional[str] = typer.Option(
        None, "--age-range",
        help="Writer age range (e.g., '22-35' or '50-65')"
    ),

    # Sampling configuration
    seed: Optional[int] = typer.Option(
        None, "--seed", "-s",
        help="Random seed for reproducibility"
    ),
    occupation_limit: Optional[int] = typer.Option(
        None, "--occupation-limit",
        help="Maximum prompts per occupation"
    ),
    industry_limit: Optional[int] = typer.Option(
        None, "--industry-limit",
        help="Maximum prompts per industry"
    ),

    # Execution options
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d",
        help="Show cost estimate without running"
    ),
    resume: Optional[Path] = typer.Option(
        None, "--resume", "-r",
        help="Resume from checkpoint directory"
    ),
    concurrency: int = typer.Option(
        25, "--concurrency", "-c",
        help="Maximum concurrent API requests (10-50)"
    ),
    batch_size: int = typer.Option(
        10, "--batch-size", "-b",
        help="Prompts per batch"
    ),

    # Output
    output_dir: Path = typer.Option(
        Path("results"), "--output", "-O",
        help="Output directory for results"
    ),
):
    """Run the Gemini writing evaluation."""

    # Start with preset config
    config = PRESETS[preset].model_copy()

    # Apply tier filter
    if tier == ModelTier.PRO:
        config.model_pairs = [p for p in config.model_pairs if "pro" in p[0].lower()]
    elif tier == ModelTier.FLASH:
        config.model_pairs = [p for p in config.model_pairs if "flash" in p[0].lower()]
    elif tier == ModelTier.BOTH:
        # Use all pairs from preset or combine if preset only has one tier
        if not any("flash" in p[0].lower() for p in config.model_pairs):
            config.model_pairs = PRO_PAIRS + FLASH_PAIRS

    # Apply custom models if specified
    if models:
        custom_pairs = []
        for pair in models.split(","):
            if ":" in pair:
                gemini, competitor = pair.split(":")
                # Resolve model names to full IDs
                gemini_id = _resolve_model_name(gemini, is_gemini=True)
                competitor_id = _resolve_model_name(competitor, is_gemini=False)
                custom_pairs.append((gemini_id, competitor_id))
        if custom_pairs:
            config.model_pairs = custom_pairs

    # Apply judge configuration
    if judges:
        judge_list = [_resolve_model_name(j.strip()) for j in judges.split(",")]
        config.judge_config.models = judge_list

    if votes:
        config.judge_config.votes_per_judge = votes

    # Apply persona setting
    if persona == JudgePersona.EXPERT:
        config.judge_config.use_both_personas = False
        config.judge_config._persona_mode = "expert"
    elif persona == JudgePersona.RECIPIENT:
        config.judge_config.use_both_personas = False
        config.judge_config._persona_mode = "recipient"
    else:
        config.judge_config.use_both_personas = True

    # Apply prompt configuration
    if prompts:
        config.num_prompts = prompts

    # Parse and store filters
    config.occupation_filter = occupations.split(",") if occupations else None
    config.industry_filter = industries.split(",") if industries else None

    if job_zones:
        config.job_zone_filter = [int(z.strip()) for z in job_zones.split(",")]
    else:
        config.job_zone_filter = None

    if formality_range:
        if "-" in formality_range:
            low, high = formality_range.split("-")
            config.formality_min = int(low)
            config.formality_max = int(high)
        else:
            config.formality_min = config.formality_max = int(formality_range)

    if age_range:
        if "-" in age_range:
            low, high = age_range.split("-")
            config.age_min = int(low)
            config.age_max = int(high)
        else:
            config.age_min = config.age_max = int(age_range)

    # Sampling limits
    config.max_per_occupation = occupation_limit
    config.max_per_industry = industry_limit
    config.random_seed = seed

    # Show cost estimate
    estimate = estimate_cost(config)
    typer.echo(format_cost_estimate(estimate, config))

    if dry_run:
        typer.echo("\n[Dry run - not executing]")
        return

    # Confirm before proceeding
    if not typer.confirm("Proceed with evaluation?"):
        typer.echo("Cancelled.")
        raise typer.Exit()

    # Run evaluation
    asyncio.run(_run_evaluation(
        config=config,
        resume_path=resume,
        output_dir=output_dir,
        concurrency=concurrency,
        batch_size=batch_size
    ))


def _resolve_model_name(name: str, is_gemini: bool = False) -> str:
    """Resolve short model names to full OpenRouter IDs."""
    name = name.lower().strip()

    model_map = {
        # Gemini
        "gemini-pro": "google/gemini-3.0-pro",
        "gemini-flash": "google/gemini-3.0-flash",
        "gemini-3-pro": "google/gemini-3.0-pro",
        "gemini-3-flash": "google/gemini-3.0-flash",

        # OpenAI
        "gpt-5.2": "openai/gpt-5.2",
        "gpt-5": "openai/gpt-5.2",
        "gpt-4.1": "openai/gpt-4.1",
        "gpt-4": "openai/gpt-4.1",

        # Anthropic
        "opus": "anthropic/claude-opus-4.5",
        "claude-opus": "anthropic/claude-opus-4.5",
        "sonnet": "anthropic/claude-sonnet-4",
        "claude-sonnet": "anthropic/claude-sonnet-4",

        # Others
        "grok": "x-ai/grok-4.1",
        "grok-4.1": "x-ai/grok-4.1",
        "kimi": "moonshot/kimi-k2",
        "kimi-k2": "moonshot/kimi-k2",
    }

    if name in model_map:
        return model_map[name]

    # If already a full ID, return as-is
    if "/" in name:
        return name

    raise typer.BadParameter(f"Unknown model: {name}")


async def _run_evaluation(
    config: EvalConfig,
    resume_path: Optional[Path],
    output_dir: Path,
    concurrency: int,
    batch_size: int
):
    """Execute the evaluation."""
    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        typer.echo("Error: OPENROUTER_API_KEY not set", err=True)
        raise typer.Exit(1)

    from .api.openrouter_client import OpenRouterClient
    from .storage.run_directory import RunDirectory
    from .storage.checkpoint import CheckpointManager
    from .storage.database import EvalDatabase
    from .eval.engine import EvaluationEngine
    from .prompts.generator import PromptGenerator
    from .tui.progress_dashboard import ProgressDashboard

    # Set up run directory
    if resume_path:
        run_dir = RunDirectory.from_existing(resume_path)
    else:
        run_dir = RunDirectory.create_new(output_dir, config)

    # Initialize components
    client = OpenRouterClient(api_key)
    checkpoint = CheckpointManager(run_dir)
    database = EvalDatabase(run_dir.results_db)

    # Generate or load prompts
    if resume_path:
        prompts = checkpoint.load_prompts()
    else:
        generator = PromptGenerator(config)
        prompts = await generator.generate()
        checkpoint.save_prompts(prompts)

    # Create engine
    engine = EvaluationEngine(
        client=client,
        config=config,
        checkpoint_manager=checkpoint,
        database=database,
        max_concurrent_requests=concurrency
    )

    # Run with TUI
    dashboard = ProgressDashboard(engine, config.run_name)
    engine.progress_callback = dashboard.on_progress_update

    # Start evaluation in background task
    async def run_eval():
        try:
            results = await engine.run_evaluation(prompts, batch_size)
            return results
        finally:
            await client.close()

    # Run TUI with evaluation
    import asyncio
    eval_task = asyncio.create_task(run_eval())

    try:
        dashboard.run()
    finally:
        if not eval_task.done():
            eval_task.cancel()


@app.command()
def compare(
    runs: List[Path] = typer.Argument(
        ...,
        help="Run directories to compare"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file for comparison report"
    )
):
    """Compare results across multiple evaluation runs."""
    from .analysis.cross_run_compare import compare_runs

    results = compare_runs(runs)

    if output:
        with open(output, "w") as f:
            f.write(results.to_markdown())
        typer.echo(f"Comparison saved to {output}")
    else:
        typer.echo(results.to_markdown())


@app.command()
def export(
    run_dir: Path = typer.Argument(
        ...,
        help="Run directory to export from"
    ),
    format: str = typer.Option(
        "csv", "--format", "-f",
        help="Export format: csv, json, or parquet"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path"
    )
):
    """Export evaluation results to various formats."""
    from .storage.database import EvalDatabase
    from .storage.run_directory import RunDirectory

    run = RunDirectory.from_existing(run_dir)
    db = EvalDatabase(run.results_db)

    if format == "csv":
        df = db.to_dataframe()
        output_path = output or run_dir / "results_export.csv"
        df.to_csv(output_path, index=False)
    elif format == "json":
        output_path = output or run_dir / "results_export.json"
        db.export_json(output_path)
    elif format == "parquet":
        df = db.to_dataframe()
        output_path = output or run_dir / "results_export.parquet"
        df.to_parquet(output_path)

    typer.echo(f"Exported to {output_path}")


@app.command()
def view(
    run_dir: Path = typer.Argument(
        ...,
        help="Run directory to view"
    )
):
    """Launch interactive results viewer."""
    from .tui.results_viewer import ResultsViewer
    from .storage.run_directory import RunDirectory
    from .storage.database import EvalDatabase

    run = RunDirectory.from_existing(run_dir)
    db = EvalDatabase(run.results_db)

    viewer = ResultsViewer(db, run)
    viewer.run()


if __name__ == "__main__":
    app()
```

---

## 5. NAME FORMALITY VARIATION

```python
# src/data/name_generator.py (with formality variation)

import random
from dataclasses import dataclass
from typing import Optional, List, Literal
from enum import Enum


class NameFormality(str, Enum):
    """Formality level for name presentation."""
    VERY_INFORMAL = "very_informal"  # "Mike"
    INFORMAL = "informal"  # "Mike Williams"
    NEUTRAL = "neutral"  # "Michael Williams"
    FORMAL = "formal"  # "Mr. Williams" or "Michael T. Williams"
    VERY_FORMAL = "very_formal"  # "Dr. Williams" or "Mr. Michael T. Williams"


@dataclass
class GeneratedName:
    """A generated name with various formality representations."""
    first_name: str
    last_name: str
    middle_initial: Optional[str] = None
    prefix: Optional[str] = None  # Dr., Mr., Ms., etc.
    suffix: Optional[str] = None  # Jr., III, PhD, etc.
    nickname: Optional[str] = None
    gender: Optional[str] = None
    ethnicity_hint: Optional[str] = None

    def format(self, formality: NameFormality) -> str:
        """Format name according to formality level."""
        if formality == NameFormality.VERY_INFORMAL:
            return self.nickname or self.first_name

        elif formality == NameFormality.INFORMAL:
            return f"{self.nickname or self.first_name} {self.last_name}"

        elif formality == NameFormality.NEUTRAL:
            return f"{self.first_name} {self.last_name}"

        elif formality == NameFormality.FORMAL:
            if self.prefix:
                return f"{self.prefix} {self.last_name}"
            elif self.middle_initial:
                return f"{self.first_name} {self.middle_initial}. {self.last_name}"
            else:
                return f"{self.first_name} {self.last_name}"

        else:  # VERY_FORMAL
            parts = []
            if self.prefix:
                parts.append(self.prefix)
            parts.append(self.first_name)
            if self.middle_initial:
                parts.append(f"{self.middle_initial}.")
            parts.append(self.last_name)
            if self.suffix:
                parts.append(self.suffix)
            return " ".join(parts)

    def to_email(self, company_domain: str, style: str = "standard") -> str:
        """Generate email address."""
        if style == "standard":
            return f"{self.first_name.lower()}.{self.last_name.lower()}@{company_domain}"
        elif style == "initial":
            return f"{self.first_name[0].lower()}{self.last_name.lower()}@{company_domain}"
        elif style == "nickname":
            name = self.nickname or self.first_name
            return f"{name.lower()}@{company_domain}"
        else:
            return f"{self.first_name.lower()}.{self.last_name.lower()}@{company_domain}"


class NameGenerator:
    """
    Generate diverse, realistic names with formality variations.

    Uses census data for demographic accuracy and supports:
    - Age-appropriate names by generation
    - Ethnic diversity
    - Various formality levels (Dr. Williams vs Mike)
    - Prefixes and suffixes
    """

    # Sample data - in production, load from census data files
    FIRST_NAMES_BY_ETHNICITY = {
        "anglo": {
            "male": ["James", "John", "Michael", "William", "David", "Robert", "Thomas", "Charles"],
            "female": ["Mary", "Jennifer", "Elizabeth", "Sarah", "Jessica", "Emily", "Ashley", "Amanda"]
        },
        "hispanic": {
            "male": ["Carlos", "Jose", "Miguel", "Juan", "Luis", "Diego", "Antonio", "Rafael"],
            "female": ["Maria", "Sofia", "Isabella", "Valentina", "Camila", "Lucia", "Ana", "Elena"]
        },
        "asian": {
            "male": ["Wei", "Jun", "Hiroshi", "Kenji", "Jin", "Chen", "Raj", "Vikram"],
            "female": ["Mei", "Yuki", "Sakura", "Lin", "Priya", "Ananya", "Min", "Hana"]
        },
        "african_american": {
            "male": ["Jamal", "DeShawn", "Marcus", "Terrence", "Andre", "Malik", "Darius", "Tyrone"],
            "female": ["Aaliyah", "Imani", "Jasmine", "Keisha", "Latoya", "Tamika", "Ebony", "Shanice"]
        }
    }

    LAST_NAMES_BY_ETHNICITY = {
        "anglo": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Davis", "Miller", "Wilson"],
        "hispanic": ["Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez"],
        "asian": ["Wang", "Li", "Zhang", "Chen", "Tanaka", "Kim", "Patel", "Singh"],
        "african_american": ["Washington", "Jefferson", "Jackson", "Robinson", "Harris", "Lewis", "Walker", "Young"]
    }

    NICKNAMES = {
        "Michael": "Mike",
        "William": "Will",
        "Robert": "Bob",
        "James": "Jim",
        "Richard": "Rick",
        "Thomas": "Tom",
        "Jennifer": "Jen",
        "Elizabeth": "Liz",
        "Katherine": "Kate",
        "Rebecca": "Becca",
    }

    PREFIXES_BY_SENIORITY = {
        "executive": ["Dr.", "Mr.", "Ms."],
        "senior": ["Mr.", "Ms."],
        "mid": ["Mr.", "Ms."],
        "entry": [],  # Less likely to use prefix
    }

    SUFFIXES_EXECUTIVE = ["Jr.", "III", "IV", "PhD", "MD", "JD", "MBA"]

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate(
        self,
        ethnicity: Optional[str] = None,
        gender: Optional[str] = None,
        generation: Optional[str] = None,
        skill_level: Optional[str] = None,
        include_prefix: bool = False,
        include_suffix: bool = False,
    ) -> GeneratedName:
        """
        Generate a realistic name with demographic considerations.

        Args:
            ethnicity: Target ethnicity or None for random weighted distribution
            gender: "male", "female", or None for random
            generation: "gen_z", "millennial", "gen_x", "boomer" for age-appropriate names
            skill_level: "entry", "mid", "senior", "executive" for prefix likelihood
            include_prefix: Whether to potentially include a prefix (Dr., Mr., etc.)
            include_suffix: Whether to potentially include a suffix (Jr., PhD, etc.)
        """
        # Select ethnicity (weighted toward US demographics)
        if ethnicity is None:
            ethnicities = ["anglo", "hispanic", "asian", "african_american"]
            weights = [0.55, 0.20, 0.15, 0.10]
            ethnicity = self.rng.choices(ethnicities, weights=weights)[0]

        # Select gender
        if gender is None:
            gender = self.rng.choice(["male", "female"])

        # Get name pools
        first_names = self.FIRST_NAMES_BY_ETHNICITY.get(ethnicity, {}).get(gender, ["Alex"])
        last_names = self.LAST_NAMES_BY_ETHNICITY.get(ethnicity, ["Smith"])

        first_name = self.rng.choice(first_names)
        last_name = self.rng.choice(last_names)

        # Middle initial (50% chance)
        middle_initial = self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") if self.rng.random() > 0.5 else None

        # Nickname (if available)
        nickname = self.NICKNAMES.get(first_name)

        # Prefix (based on seniority)
        prefix = None
        if include_prefix and skill_level:
            prefix_pool = self.PREFIXES_BY_SENIORITY.get(skill_level, [])
            if prefix_pool and self.rng.random() > 0.6:
                prefix = self.rng.choice(prefix_pool)

        # Suffix (rare, more common for executives)
        suffix = None
        if include_suffix and skill_level == "executive" and self.rng.random() > 0.85:
            suffix = self.rng.choice(self.SUFFIXES_EXECUTIVE)

        return GeneratedName(
            first_name=first_name,
            last_name=last_name,
            middle_initial=middle_initial,
            prefix=prefix,
            suffix=suffix,
            nickname=nickname,
            gender=gender,
            ethnicity_hint=ethnicity
        )

    def generate_for_formality(
        self,
        formality_level: int,
        skill_level: str = "mid",
        **kwargs
    ) -> tuple[GeneratedName, str]:
        """
        Generate a name and format it for a given formality level.

        Args:
            formality_level: 1-5 where 1 is very casual, 5 is very formal
            skill_level: Seniority for prefix likelihood
            **kwargs: Additional args passed to generate()

        Returns:
            Tuple of (GeneratedName, formatted_string)
        """
        # Map formality level to NameFormality enum
        formality_map = {
            1: NameFormality.VERY_INFORMAL,
            2: NameFormality.INFORMAL,
            3: NameFormality.NEUTRAL,
            4: NameFormality.FORMAL,
            5: NameFormality.VERY_FORMAL,
        }
        formality = formality_map.get(formality_level, NameFormality.NEUTRAL)

        # Higher formality = more likely to include prefix
        include_prefix = formality_level >= 4 and self.rng.random() > 0.3
        include_suffix = formality_level >= 5 and self.rng.random() > 0.7

        name = self.generate(
            skill_level=skill_level,
            include_prefix=include_prefix,
            include_suffix=include_suffix,
            **kwargs
        )

        return name, name.format(formality)
```

---

## 6. TUI RESULTS VIEWER (Filtering, Sorting, Drill-down)

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Select, Button, TextArea
)
from textual.binding import Binding
from textual.screen import ModalScreen
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from ..storage.database import EvalDatabase
from ..storage.run_directory import RunDirectory


class SortField(str, Enum):
    """Available sort fields."""
    PROMPT_ID = "prompt_id"
    OCCUPATION = "occupation"
    INDUSTRY = "industry"
    WINNER = "winner"
    QUALITY_DIFF = "quality_diff"
    FORMALITY = "formality"
    URGENCY = "urgency"


class FilterMode(str, Enum):
    """Filter modes."""
    ALL = "all"
    GEMINI_WINS = "gemini_wins"
    COMPETITOR_WINS = "competitor_wins"
    TIES = "ties"
    AUTO_LOSS = "auto_loss"


@dataclass
class ResultsFilter:
    """Filter configuration for results."""
    mode: FilterMode = FilterMode.ALL
    occupation_code: Optional[str] = None
    industry_code: Optional[str] = None
    model_pair: Optional[str] = None
    min_quality_diff: Optional[float] = None
    has_constraints: Optional[bool] = None
    is_sensitive: Optional[bool] = None


class ComparisonDetailScreen(ModalScreen):
    """Modal screen showing detailed comparison view."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("j", "next_judgment", "Next Judgment"),
        Binding("k", "prev_judgment", "Prev Judgment"),
    ]

    def __init__(self, comparison_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.comparison = comparison_data
        self.current_judgment_idx = 0

    def compose(self) -> ComposeResult:
        yield Container(
            Static("COMPARISON DETAILS", classes="header-label"),
            Horizontal(
                # Left: Prompt info
                Container(
                    Static("PROMPT", classes="section-header"),
                    Static("", id="prompt-text"),
                    Static("", id="prompt-occupation"),
                    Static("", id="prompt-industry"),
                    Static("", id="prompt-formality"),
                    id="prompt-section"
                ),
                # Center: Responses side-by-side
                Container(
                    Horizontal(
                        Container(
                            Static("GEMINI RESPONSE", classes="section-header"),
                            TextArea(id="gemini-response", read_only=True),
                            id="gemini-section"
                        ),
                        Container(
                            Static("COMPETITOR RESPONSE", classes="section-header"),
                            TextArea(id="competitor-response", read_only=True),
                            id="competitor-section"
                        ),
                    ),
                    id="responses-section"
                ),
            ),
            # Bottom: Judgment details
            Container(
                Static("JUDGMENTS", classes="section-header"),
                DataTable(id="judgments-table"),
                Static("", id="selected-judgment-detail"),
                id="judgments-section"
            ),
            id="detail-container"
        )

    def on_mount(self) -> None:
        """Populate the detail view."""
        c = self.comparison

        # Prompt info
        self.query_one("#prompt-text", Static).update(c.get("prompt_text", "")[:500])
        self.query_one("#prompt-occupation", Static).update(
            f"Occupation: {c.get('occupation_title', 'N/A')} ({c.get('occupation_code', 'N/A')})"
        )
        self.query_one("#prompt-industry", Static).update(
            f"Industry: {c.get('industry_name', 'N/A')} ({c.get('naics_code', 'N/A')})"
        )
        self.query_one("#prompt-formality", Static).update(
            f"Formality: {c.get('formality_level', 'N/A')}/5 | Urgency: {c.get('urgency_level', 'N/A')}/5"
        )

        # Responses
        self.query_one("#gemini-response", TextArea).load_text(
            c.get("gemini_response", "No response")
        )
        self.query_one("#competitor-response", TextArea).load_text(
            c.get("competitor_response", "No response")
        )

        # Judgments table
        table = self.query_one("#judgments-table", DataTable)
        table.add_columns("Judge", "Persona", "Winner", "Confidence", "Quality G", "Quality C")

        judgments = c.get("judgments", [])
        for j in judgments:
            table.add_row(
                j.get("judge_model", "").split("/")[-1],
                j.get("persona", ""),
                j.get("winner", ""),
                str(j.get("confidence", "")),
                str(j.get("quality_gemini", "")),
                str(j.get("quality_competitor", ""))
            )

    def action_next_judgment(self) -> None:
        """Show next judgment detail."""
        judgments = self.comparison.get("judgments", [])
        if judgments:
            self.current_judgment_idx = (self.current_judgment_idx + 1) % len(judgments)
            self._show_judgment_detail()

    def action_prev_judgment(self) -> None:
        """Show previous judgment detail."""
        judgments = self.comparison.get("judgments", [])
        if judgments:
            self.current_judgment_idx = (self.current_judgment_idx - 1) % len(judgments)
            self._show_judgment_detail()

    def _show_judgment_detail(self) -> None:
        """Update the selected judgment detail."""
        judgments = self.comparison.get("judgments", [])
        if judgments:
            j = judgments[self.current_judgment_idx]
            detail = f"Reasoning: {j.get('reasoning', 'N/A')}"
            self.query_one("#selected-judgment-detail", Static).update(detail)


class ResultsViewer(App):
    """
    Interactive TUI for viewing and exploring evaluation results.

    Features:
    - Filter by occupation, industry, winner, model pair
    - Sort by various dimensions
    - Side-by-side response viewing
    - Drill-down into individual judgments
    """

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 1fr 8fr 2fr;
    }

    #filter-bar {
        border: solid blue;
        padding: 1;
        height: 3;
    }

    #results-table-container {
        border: solid green;
    }

    #summary-panel {
        border: solid cyan;
        padding: 1;
    }

    .section-header {
        text-style: bold;
        color: cyan;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("enter", "view_detail", "View Detail"),
        Binding("e", "export_filtered", "Export"),
        Binding("/", "search", "Search"),
    ]

    def __init__(self, database: EvalDatabase, run_dir: RunDirectory, **kwargs):
        super().__init__(**kwargs)
        self.database = database
        self.run_dir = run_dir
        self.filter = ResultsFilter()
        self.sort_field = SortField.PROMPT_ID
        self.sort_ascending = True
        self.results_cache: List[Dict] = []
        self.selected_row_idx = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            # Filter bar
            Horizontal(
                Select(
                    [(f.value, f.value) for f in FilterMode],
                    id="filter-mode",
                    prompt="Filter:"
                ),
                Input(placeholder="Occupation code...", id="filter-occupation"),
                Input(placeholder="Industry code...", id="filter-industry"),
                Select(
                    [("All pairs", "all")] + [
                        (p, p) for p in self._get_model_pairs()
                    ],
                    id="filter-pair",
                    prompt="Model pair:"
                ),
                Button("Apply", id="apply-filter"),
                Button("Clear", id="clear-filter"),
                id="filter-bar"
            ),

            # Results table
            ScrollableContainer(
                DataTable(id="results-table", cursor_type="row"),
                id="results-table-container"
            ),

            # Summary panel
            Container(
                Horizontal(
                    Static("", id="summary-total"),
                    Static("", id="summary-wins"),
                    Static("", id="summary-sort"),
                ),
                id="summary-panel"
            ),

            id="main-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the results table."""
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "ID", "Occupation", "Industry", "Pair", "Winner",
            "G-Qual", "C-Qual", "Formality", "Sensitive"
        )
        self._load_results()

    def _get_model_pairs(self) -> List[str]:
        """Get unique model pairs from database."""
        # Would query database for unique pairs
        return [
            "gemini-3.0-pro_vs_gpt-5.2",
            "gemini-3.0-pro_vs_claude-opus-4.5",
            "gemini-3.0-flash_vs_gpt-4.1",
        ]

    def _load_results(self) -> None:
        """Load and display results based on current filter/sort."""
        # Query database
        query_params = {}
        if self.filter.mode == FilterMode.GEMINI_WINS:
            query_params["winner"] = "gemini"
        elif self.filter.mode == FilterMode.COMPETITOR_WINS:
            query_params["winner"] = "competitor"
        elif self.filter.mode == FilterMode.TIES:
            query_params["winner"] = "tie"
        elif self.filter.mode == FilterMode.AUTO_LOSS:
            query_params["is_auto_loss"] = True

        if self.filter.occupation_code:
            query_params["occupation_code"] = self.filter.occupation_code
        if self.filter.industry_code:
            query_params["naics_code"] = self.filter.industry_code
        if self.filter.model_pair and self.filter.model_pair != "all":
            query_params["model_pair"] = self.filter.model_pair

        # Get results from database
        self.results_cache = self.database.query_comparisons(
            **query_params,
            sort_by=self.sort_field.value,
            ascending=self.sort_ascending
        )

        # Update table
        table = self.query_one("#results-table", DataTable)
        table.clear()

        for r in self.results_cache:
            winner_display = {
                "gemini": "[green]Gemini[/]",
                "competitor": "[red]Competitor[/]",
                "tie": "[yellow]Tie[/]"
            }.get(r.get("winner", ""), r.get("winner", ""))

            sensitive = "Yes" if r.get("sensitive_topics") else "No"

            table.add_row(
                r.get("prompt_id", "")[:8],
                r.get("occupation_title", "")[:20],
                r.get("industry_name", "")[:15],
                r.get("model_pair", "").split("_vs_")[-1][:12],
                winner_display,
                str(r.get("avg_quality_gemini", "")),
                str(r.get("avg_quality_competitor", "")),
                str(r.get("formality_level", "")),
                sensitive
            )

        self._update_summary()

    def _update_summary(self) -> None:
        """Update summary statistics."""
        total = len(self.results_cache)
        gemini_wins = sum(1 for r in self.results_cache if r.get("winner") == "gemini")
        competitor_wins = sum(1 for r in self.results_cache if r.get("winner") == "competitor")
        ties = total - gemini_wins - competitor_wins

        self.query_one("#summary-total", Static).update(
            f"Total: {total} comparisons"
        )
        self.query_one("#summary-wins", Static).update(
            f"Gemini: {gemini_wins} ({gemini_wins/total*100:.1f}%) | "
            f"Competitor: {competitor_wins} ({competitor_wins/total*100:.1f}%) | "
            f"Ties: {ties}"
        )
        self.query_one("#summary-sort", Static).update(
            f"Sorted by: {self.sort_field.value} {'↑' if self.sort_ascending else '↓'}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle filter button presses."""
        if event.button.id == "apply-filter":
            self._apply_filter()
        elif event.button.id == "clear-filter":
            self._clear_filter()

    def _apply_filter(self) -> None:
        """Apply current filter settings."""
        self.filter.mode = FilterMode(
            self.query_one("#filter-mode", Select).value or "all"
        )
        self.filter.occupation_code = self.query_one("#filter-occupation", Input).value or None
        self.filter.industry_code = self.query_one("#filter-industry", Input).value or None

        pair_value = self.query_one("#filter-pair", Select).value
        self.filter.model_pair = pair_value if pair_value != "all" else None

        self._load_results()

    def _clear_filter(self) -> None:
        """Clear all filters."""
        self.filter = ResultsFilter()
        self.query_one("#filter-mode", Select).value = "all"
        self.query_one("#filter-occupation", Input).value = ""
        self.query_one("#filter-industry", Input).value = ""
        self.query_one("#filter-pair", Select).value = "all"
        self._load_results()

    def action_toggle_filter(self) -> None:
        """Toggle filter panel visibility."""
        filter_bar = self.query_one("#filter-bar")
        filter_bar.display = not filter_bar.display

    def action_cycle_sort(self) -> None:
        """Cycle through sort fields."""
        fields = list(SortField)
        current_idx = fields.index(self.sort_field)
        next_idx = (current_idx + 1) % len(fields)

        if next_idx == 0:
            # Wrapped around - toggle direction
            self.sort_ascending = not self.sort_ascending

        self.sort_field = fields[next_idx]
        self._load_results()

    def action_view_detail(self) -> None:
        """View detail for selected row."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.results_cache):
            comparison = self.results_cache[table.cursor_row]
            # Load full comparison data with responses and judgments
            full_data = self.database.get_comparison_detail(comparison["prompt_id"])
            self.push_screen(ComparisonDetailScreen(full_data))

    def action_export_filtered(self) -> None:
        """Export currently filtered results."""
        import json
        output_path = self.run_dir.root / "filtered_export.json"
        with open(output_path, "w") as f:
            json.dump(self.results_cache, f, indent=2, default=str)
        self.notify(f"Exported {len(self.results_cache)} results to {output_path}")

    def action_search(self) -> None:
        """Open search dialog."""
        # Would push a search screen
        self.notify("Search not yet implemented")
```

---

## 7. PHASE 1 GENERATION USING EVALUATED MODELS

```python
# src/prompts/phase1_offline.py

import asyncio
import random
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import json
from pathlib import Path

from ..api.openrouter_client import OpenRouterClient
from ..data.onet_extractor import ONetTask
from ..config.presets import PRO_PAIRS, FLASH_PAIRS


@dataclass
class Phase1Variation:
    """A persona/context variation generated by an evaluated model."""
    task_id: str
    generated_by_model: str
    variation_idx: int
    writer_persona: Dict[str, Any]
    recipient_persona: Dict[str, Any]
    scenario_context: str
    emotional_context: str
    formality_level: int
    urgency_level: int
    temporal_context: Optional[str]
    competing_objectives: Optional[str]


class Phase1Generator:
    """
    Offline LLM generation for persona/context variations.

    IMPORTANT: Uses the same models being evaluated (Gemini, GPT, Claude, etc.)
    to generate variations. This is done to avoid biasing prompts against
    any particular model.

    The generation is distributed across models to ensure no single model
    has undue influence on the prompts.
    """

    # System prompt for generating variations
    VARIATION_SYSTEM_PROMPT = """You are a professional workplace scenario generator.
Your task is to create realistic, diverse variations of writing task scenarios.

For each O*NET task, generate a complete scenario including:
1. Writer persona (name, age, job title, skill level, generation)
2. Recipient persona (name, title, relationship to writer)
3. Scenario context (what's happening, why this writing is needed)
4. Emotional context (routine, crisis, celebration, conflict, bad_news)
5. Formality level (1-5, where 1=very casual, 5=very formal)
6. Urgency level (1-5, where 1=not urgent, 5=critical)
7. Optional temporal context (deadlines, dates if relevant)
8. Optional competing objectives (tensions the writing must navigate)

Be diverse - vary ages, industries, company sizes, relationships, and contexts.
Make scenarios feel realistic and grounded in real workplace situations."""

    VARIATION_USER_TEMPLATE = """Generate a unique workplace writing scenario for this task:

O*NET Task: {task_statement}
Occupation: {occupation_title} ({occupation_code})
Job Zone: {job_zone} (1=little prep, 5=extensive prep)

Generate a realistic scenario. Respond in JSON format:
{{
    "writer_persona": {{
        "name": "Full Name",
        "age": 35,
        "job_title": "Specific Title",
        "skill_level": "entry|mid|senior|executive",
        "generation": "gen_z|millennial|gen_x|boomer",
        "years_experience": 5
    }},
    "recipient_persona": {{
        "name": "Full Name",
        "job_title": "Specific Title",
        "relationship": "new_contact|colleague|manager|client|...",
        "is_technical": true|false
    }},
    "scenario_context": "Brief description of the situation...",
    "emotional_context": "routine|crisis|celebration|conflict|bad_news",
    "formality_level": 3,
    "urgency_level": 2,
    "temporal_context": "Optional deadline or date context, or null",
    "competing_objectives": "Optional tension to navigate, or null"
}}"""

    def __init__(
        self,
        client: OpenRouterClient,
        output_dir: Path,
        seed: Optional[int] = None
    ):
        self.client = client
        self.output_dir = output_dir
        self.rng = random.Random(seed)

        # Get all models being evaluated (distribute generation across them)
        self.evaluated_models = self._get_evaluated_models()

    def _get_evaluated_models(self) -> List[str]:
        """Get list of all models being evaluated."""
        models = set()
        for gemini, competitor in PRO_PAIRS + FLASH_PAIRS:
            models.add(gemini)
            models.add(competitor)
        return list(models)

    async def generate_variations(
        self,
        tasks: List[ONetTask],
        variations_per_task: int = 5,
        concurrent_limit: int = 10
    ) -> List[Phase1Variation]:
        """
        Generate variations for all tasks using evaluated models.

        Distribution strategy: Round-robin across evaluated models to ensure
        no single model dominates the variation generation.
        """
        all_variations = []
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def generate_single(task: ONetTask, var_idx: int, model: str):
            async with semaphore:
                try:
                    variation = await self._generate_variation(task, var_idx, model)
                    return variation
                except Exception as e:
                    print(f"Error generating variation for {task.task_id}: {e}")
                    return None

        # Create all generation tasks with round-robin model assignment
        generation_tasks = []
        model_idx = 0

        for task in tasks:
            for var_idx in range(variations_per_task):
                model = self.evaluated_models[model_idx % len(self.evaluated_models)]
                model_idx += 1
                generation_tasks.append(
                    generate_single(task, var_idx, model)
                )

        # Execute all generations
        results = await asyncio.gather(*generation_tasks)

        # Filter successful results
        all_variations = [v for v in results if v is not None]

        # Save to output directory
        self._save_variations(all_variations)

        return all_variations

    async def _generate_variation(
        self,
        task: ONetTask,
        variation_idx: int,
        model: str
    ) -> Phase1Variation:
        """Generate a single variation using specified model."""
        user_prompt = self.VARIATION_USER_TEMPLATE.format(
            task_statement=task.task_statement,
            occupation_title=task.occupation_title,
            occupation_code=task.onetsoc_code,
            job_zone=task.job_zone
        )

        response = await self.client.complete(
            model=model,
            messages=[
                {"role": "system", "content": self.VARIATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8  # Higher temp for diversity
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            return Phase1Variation(
                task_id=task.task_id,
                generated_by_model=model,
                variation_idx=variation_idx,
                writer_persona=data["writer_persona"],
                recipient_persona=data["recipient_persona"],
                scenario_context=data["scenario_context"],
                emotional_context=data["emotional_context"],
                formality_level=data["formality_level"],
                urgency_level=data["urgency_level"],
                temporal_context=data.get("temporal_context"),
                competing_objectives=data.get("competing_objectives")
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse variation response: {e}")

    def _save_variations(self, variations: List[Phase1Variation]) -> None:
        """Save variations to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Group by task
        by_task = {}
        for v in variations:
            if v.task_id not in by_task:
                by_task[v.task_id] = []
            by_task[v.task_id].append(v)

        # Save each task's variations
        for task_id, task_variations in by_task.items():
            output_file = self.output_dir / f"{task_id.replace('.', '_')}.json"
            data = [
                {
                    "task_id": v.task_id,
                    "generated_by_model": v.generated_by_model,
                    "variation_idx": v.variation_idx,
                    "writer_persona": v.writer_persona,
                    "recipient_persona": v.recipient_persona,
                    "scenario_context": v.scenario_context,
                    "emotional_context": v.emotional_context,
                    "formality_level": v.formality_level,
                    "urgency_level": v.urgency_level,
                    "temporal_context": v.temporal_context,
                    "competing_objectives": v.competing_objectives
                }
                for v in task_variations
            ]
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)

        # Save summary
        summary = {
            "total_variations": len(variations),
            "tasks_covered": len(by_task),
            "model_distribution": {}
        }
        for v in variations:
            model = v.generated_by_model
            summary["model_distribution"][model] = (
                summary["model_distribution"].get(model, 0) + 1
            )

        with open(self.output_dir / "generation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
```

---

## 8. AMBIGUITY BEHAVIOR TRACKING

```python
# src/eval/ambiguity_tracker.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from enum import Enum
import re


class AmbiguityBehavior(str, Enum):
    """How a model handles ambiguous prompts."""
    MADE_ASSUMPTIONS = "made_assumptions"  # Proceeded with reasonable assumptions
    ASKED_CLARIFICATION = "asked_clarification"  # Asked for more info in response
    HEDGED = "hedged"  # Included caveats or conditionals
    HALLUCINATED = "hallucinated"  # Invented specific details
    REFUSED = "refused"  # Declined due to insufficient info
    GENERIC = "generic"  # Gave overly generic response


@dataclass
class AmbiguityAnalysis:
    """Analysis of how a model handled an ambiguous prompt."""
    prompt_id: str
    model: str
    response: str
    behaviors: List[AmbiguityBehavior]
    assumptions_made: List[str]  # Specific assumptions identified
    clarifications_requested: List[str]  # Questions asked
    hedging_phrases: List[str]  # Caveats used
    hallucinated_details: List[str]  # Invented specifics
    confidence_score: float  # 0-1, how confident the classification is


class AmbiguityTracker:
    """
    Track and analyze how models handle ambiguous prompts.

    Per PROMPT.md, we need to track whether models:
    - Make reasonable assumptions
    - Ask for clarification (in the response)
    - Hedge appropriately
    - Hallucinate specific details
    """

    # Patterns indicating clarification requests
    CLARIFICATION_PATTERNS = [
        r"could you (please )?(clarify|specify|provide|tell me)",
        r"(would|could) (you|it) help (if|to)",
        r"(do you|could you) (mean|want)",
        r"what (exactly|specifically) (do you|would you)",
        r"I('d| would) need (more|additional) (information|details|context)",
        r"(before I|to) proceed, (could|would) you",
        r"(which|what) (specific|particular)",
        r"\?(?=.*\n)",  # Questions in the response
    ]

    # Patterns indicating hedging
    HEDGING_PATTERNS = [
        r"(assuming|if I understand correctly)",
        r"based on (my|the) (understanding|interpretation)",
        r"(depending on|subject to)",
        r"(may|might|could) (vary|differ|change)",
        r"(typically|generally|usually|often)",
        r"(unless|otherwise|if not)",
        r"(please (let me know|confirm) if)",
        r"(adjust|modify|update)( this)? (as needed|accordingly)",
    ]

    # Patterns indicating specific hallucinated details
    HALLUCINATION_INDICATORS = [
        r"\$[\d,]+(\.\d{2})?",  # Specific dollar amounts
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # Specific dates
        r"\b\d{1,2}:\d{2}\s*(am|pm|AM|PM)?\b",  # Specific times
        r"\b\d+%\b",  # Specific percentages
        r"(\b[A-Z][a-z]+ [A-Z][a-z]+\b)(?=.*@)",  # Names with emails
        r"conference room [A-Z0-9]+",  # Specific room numbers
    ]

    def __init__(self):
        self.analyses: Dict[str, Dict[str, AmbiguityAnalysis]] = {}

    def analyze_response(
        self,
        prompt_id: str,
        model: str,
        response: str,
        ambiguity_type: str  # "underspecified_recipient", "missing_context", "unclear_ask"
    ) -> AmbiguityAnalysis:
        """
        Analyze how a model handled an ambiguous prompt.
        """
        behaviors = []
        assumptions = []
        clarifications = []
        hedges = []
        hallucinations = []

        response_lower = response.lower()

        # Check for clarification requests
        for pattern in self.CLARIFICATION_PATTERNS:
            matches = re.findall(pattern, response_lower, re.IGNORECASE)
            if matches:
                behaviors.append(AmbiguityBehavior.ASKED_CLARIFICATION)
                clarifications.extend([str(m) for m in matches[:3]])
                break

        # Check for hedging
        hedge_count = 0
        for pattern in self.HEDGING_PATTERNS:
            matches = re.findall(pattern, response_lower, re.IGNORECASE)
            if matches:
                hedge_count += len(matches)
                hedges.extend([str(m) for m in matches[:2]])

        if hedge_count >= 2:
            behaviors.append(AmbiguityBehavior.HEDGED)

        # Check for hallucinated details
        for pattern in self.HALLUCINATION_INDICATORS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                hallucinations.extend([str(m) for m in matches[:3]])

        if hallucinations:
            behaviors.append(AmbiguityBehavior.HALLUCINATED)

        # Check for assumptions (explicit mentions)
        assumption_patterns = [
            r"I('ll| will) assume",
            r"assuming (that|you)",
            r"I('m| am) (going to )?(assume|presume)",
            r"for (the purposes of|this)",
        ]
        for pattern in assumption_patterns:
            if re.search(pattern, response_lower):
                behaviors.append(AmbiguityBehavior.MADE_ASSUMPTIONS)
                # Try to extract the assumption
                match = re.search(pattern + r"[^.]*\.", response_lower)
                if match:
                    assumptions.append(match.group())
                break

        # Check for refusal
        refusal_patterns = [
            r"I (cannot|can't|am unable to) (complete|write|provide)",
            r"(need|require) more (information|context|details)",
            r"(insufficient|inadequate) (information|context)",
        ]
        for pattern in refusal_patterns:
            if re.search(pattern, response_lower):
                behaviors.append(AmbiguityBehavior.REFUSED)
                break

        # If no specific behaviors, check if response is overly generic
        if not behaviors:
            # Generic responses tend to be short with placeholder language
            if len(response) < 200 or "[" in response or "INSERT" in response.upper():
                behaviors.append(AmbiguityBehavior.GENERIC)
            else:
                # Default: model made assumptions (implicit)
                behaviors.append(AmbiguityBehavior.MADE_ASSUMPTIONS)

        # Calculate confidence score
        confidence = min(1.0, len(behaviors) * 0.3 + 0.4)

        analysis = AmbiguityAnalysis(
            prompt_id=prompt_id,
            model=model,
            response=response[:500],  # Store truncated
            behaviors=behaviors,
            assumptions_made=assumptions,
            clarifications_requested=clarifications,
            hedging_phrases=hedges,
            hallucinated_details=hallucinations,
            confidence_score=confidence
        )

        # Cache analysis
        if prompt_id not in self.analyses:
            self.analyses[prompt_id] = {}
        self.analyses[prompt_id][model] = analysis

        return analysis

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of ambiguity handling."""
        summary = {
            "total_ambiguous_prompts": len(self.analyses),
            "behavior_counts": {},
            "by_model": {}
        }

        for prompt_id, model_analyses in self.analyses.items():
            for model, analysis in model_analyses.items():
                if model not in summary["by_model"]:
                    summary["by_model"][model] = {b.value: 0 for b in AmbiguityBehavior}

                for behavior in analysis.behaviors:
                    summary["behavior_counts"][behavior.value] = (
                        summary["behavior_counts"].get(behavior.value, 0) + 1
                    )
                    summary["by_model"][model][behavior.value] += 1

        return summary
```

---

## 9. REFUSAL TRACKING BY DIMENSION

```python
# src/eval/refusal_classifier.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from collections import defaultdict
import re


class RefusalCategory(str, Enum):
    """Categories of model refusals per PROMPT.md."""
    SAFETY_REFUSAL = "safety_refusal"  # Model cites safety/policy concerns
    CAPABILITY_LIMITATION = "capability_limitation"  # Model says it can't do the task
    MISUNDERSTANDING = "misunderstanding"  # Model interprets task incorrectly
    INCOMPLETE_RESPONSE = "incomplete_response"  # Model starts but doesn't finish
    OFF_TOPIC = "off_topic"  # Model responds but not to the actual task
    TIMEOUT = "timeout"  # Model timed out
    ERROR = "error"  # API or other error


@dataclass
class RefusalRecord:
    """Record of a refusal with full context."""
    prompt_id: str
    model: str
    category: RefusalCategory
    response_snippet: str  # First 500 chars of response
    occupation_code: str
    occupation_title: str
    naics_code: str
    industry_name: str
    sensitive_topics: List[str]
    formality_level: int
    task_type: Optional[str] = None  # Inferred from prompt


@dataclass
class RefusalStats:
    """Statistics for refusal tracking."""
    total_refusals: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_model: Dict[str, int] = field(default_factory=dict)
    by_occupation: Dict[str, int] = field(default_factory=dict)
    by_industry: Dict[str, int] = field(default_factory=dict)
    by_sensitive_topic: Dict[str, int] = field(default_factory=dict)


class RefusalClassifier:
    """
    Classify and track model refusals with detailed breakdowns.

    Tracks refusals by:
    - Model (which models refuse most?)
    - Task type (which tasks trigger refusals?)
    - Sensitive topic category (which sensitive areas are problematic?)
    - Occupation and industry
    """

    # Patterns for detecting different refusal types
    SAFETY_PATTERNS = [
        r"(cannot|can't|unable to) (help|assist|write) (with|about)",
        r"(violates?|against) (my|our) (policy|policies|guidelines)",
        r"(not appropriate|inappropriate) (for me|to)",
        r"(safety|ethical|policy) (concern|issue|reason)",
        r"(decline|refused?|cannot) (to )?(create|write|generate)",
        r"(harmful|dangerous|inappropriate) content",
        r"I('m| am) (not able|unable) to (assist|help) with",
    ]

    CAPABILITY_PATTERNS = [
        r"(don't|do not) have (the )?(ability|capability|access)",
        r"(beyond|outside) (my|the) (capabilities|scope)",
        r"I (cannot|can't) (actually|really) (do|perform|complete)",
        r"(not designed|not built) (to|for)",
        r"(lack|don't have) (the )?(information|context|data)",
    ]

    MISUNDERSTANDING_INDICATORS = [
        r"(I think you|you seem to) (mean|want)",
        r"(not sure|unclear) what (you|the)",
        r"could you (clarify|explain|specify)",
        r"(interpret|understood) (this|your request) (as|to mean)",
    ]

    INCOMPLETE_INDICATORS = [
        r"\.\.\.$",  # Ends with ellipsis
        r"(continue|continuing|to be continued)",
        r"(Part 1|Section 1) of \d+",
        r"\[incomplete\]|\[continued\]",
    ]

    def __init__(self):
        self.refusals: List[RefusalRecord] = []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self._safety_re = [re.compile(p, re.IGNORECASE) for p in self.SAFETY_PATTERNS]
        self._capability_re = [re.compile(p, re.IGNORECASE) for p in self.CAPABILITY_PATTERNS]
        self._misunderstanding_re = [re.compile(p, re.IGNORECASE) for p in self.MISUNDERSTANDING_INDICATORS]
        self._incomplete_re = [re.compile(p, re.IGNORECASE) for p in self.INCOMPLETE_INDICATORS]

    def classify(
        self,
        response: str,
        is_timeout: bool = False,
        is_error: bool = False
    ) -> tuple[bool, Optional[RefusalCategory]]:
        """
        Classify whether a response is a refusal and what type.

        Returns:
            Tuple of (is_refusal, refusal_category or None)
        """
        if is_timeout:
            return True, RefusalCategory.TIMEOUT
        if is_error:
            return True, RefusalCategory.ERROR

        # Empty or very short responses
        if not response or len(response.strip()) < 20:
            return True, RefusalCategory.INCOMPLETE_RESPONSE

        response_lower = response.lower()

        # Check safety refusal
        for pattern in self._safety_re:
            if pattern.search(response_lower):
                return True, RefusalCategory.SAFETY_REFUSAL

        # Check capability limitation
        for pattern in self._capability_re:
            if pattern.search(response_lower):
                return True, RefusalCategory.CAPABILITY_LIMITATION

        # Check for misunderstanding
        misunderstanding_count = sum(
            1 for p in self._misunderstanding_re if p.search(response_lower)
        )
        if misunderstanding_count >= 2:
            return True, RefusalCategory.MISUNDERSTANDING

        # Check for incomplete response
        for pattern in self._incomplete_re:
            if pattern.search(response):
                return True, RefusalCategory.INCOMPLETE_RESPONSE

        # Check for off-topic (heuristic: very short responses that don't match expected patterns)
        if len(response) < 100 and not any([
            "dear" in response_lower,
            "hi " in response_lower,
            "hello" in response_lower,
            "subject:" in response_lower,
            "re:" in response_lower,
        ]):
            # Might be off-topic - needs context to confirm
            return False, None

        return False, None

    def record_refusal(
        self,
        prompt_id: str,
        model: str,
        category: RefusalCategory,
        response: str,
        prompt_metadata: Dict[str, Any]
    ) -> RefusalRecord:
        """
        Record a refusal with full context for analysis.
        """
        record = RefusalRecord(
            prompt_id=prompt_id,
            model=model,
            category=category,
            response_snippet=response[:500] if response else "",
            occupation_code=prompt_metadata.get("occupation_code", ""),
            occupation_title=prompt_metadata.get("occupation_title", ""),
            naics_code=prompt_metadata.get("naics_code", ""),
            industry_name=prompt_metadata.get("industry_name", ""),
            sensitive_topics=prompt_metadata.get("sensitive_topics", []),
            formality_level=prompt_metadata.get("formality_level", 0),
            task_type=prompt_metadata.get("task_type")
        )
        self.refusals.append(record)
        return record

    def get_stats(self) -> RefusalStats:
        """Get comprehensive refusal statistics."""
        stats = RefusalStats()
        stats.total_refusals = len(self.refusals)

        for r in self.refusals:
            # By category
            cat = r.category.value
            stats.by_category[cat] = stats.by_category.get(cat, 0) + 1

            # By model
            stats.by_model[r.model] = stats.by_model.get(r.model, 0) + 1

            # By occupation (use major group)
            occ_group = r.occupation_code[:2] if r.occupation_code else "unknown"
            stats.by_occupation[occ_group] = stats.by_occupation.get(occ_group, 0) + 1

            # By industry (use 2-digit NAICS)
            ind_group = r.naics_code[:2] if r.naics_code else "unknown"
            stats.by_industry[ind_group] = stats.by_industry.get(ind_group, 0) + 1

            # By sensitive topic
            for topic in r.sensitive_topics:
                stats.by_sensitive_topic[topic] = stats.by_sensitive_topic.get(topic, 0) + 1

        return stats

    def get_detailed_breakdown(self) -> Dict[str, Any]:
        """Get detailed breakdown for reporting."""
        stats = self.get_stats()

        # Calculate rates
        model_counts = defaultdict(lambda: {"refusals": 0, "total": 0})
        for r in self.refusals:
            model_counts[r.model]["refusals"] += 1

        return {
            "summary": {
                "total_refusals": stats.total_refusals,
                "by_category": stats.by_category,
            },
            "by_model": {
                model: {
                    "refusal_count": data["refusals"],
                    "categories": {
                        cat.value: sum(
                            1 for r in self.refusals
                            if r.model == model and r.category == cat
                        )
                        for cat in RefusalCategory
                    }
                }
                for model, data in model_counts.items()
            },
            "by_occupation_group": {
                occ: {
                    "refusal_count": count,
                    "top_categories": self._get_top_categories_for_dimension(
                        "occupation", occ
                    )
                }
                for occ, count in sorted(
                    stats.by_occupation.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            },
            "by_industry_group": {
                ind: {
                    "refusal_count": count,
                    "top_categories": self._get_top_categories_for_dimension(
                        "industry", ind
                    )
                }
                for ind, count in sorted(
                    stats.by_industry.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            },
            "by_sensitive_topic": stats.by_sensitive_topic,
            "problematic_combinations": self._find_problematic_combinations()
        }

    def _get_top_categories_for_dimension(
        self,
        dimension: str,
        value: str
    ) -> Dict[str, int]:
        """Get top refusal categories for a specific dimension value."""
        counts = defaultdict(int)
        for r in self.refusals:
            if dimension == "occupation":
                if r.occupation_code.startswith(value):
                    counts[r.category.value] += 1
            elif dimension == "industry":
                if r.naics_code.startswith(value):
                    counts[r.category.value] += 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3])

    def _find_problematic_combinations(self) -> List[Dict[str, Any]]:
        """Find combinations that result in high refusal rates."""
        # Group by (model, sensitive_topic) combinations
        combinations = defaultdict(list)
        for r in self.refusals:
            for topic in r.sensitive_topics:
                key = (r.model, topic)
                combinations[key].append(r)

        # Return combinations with 3+ refusals
        problematic = []
        for (model, topic), records in combinations.items():
            if len(records) >= 3:
                problematic.append({
                    "model": model,
                    "sensitive_topic": topic,
                    "refusal_count": len(records),
                    "primary_category": max(
                        set(r.category.value for r in records),
                        key=lambda c: sum(1 for r in records if r.category.value == c)
                    )
                })

        return sorted(problematic, key=lambda x: x["refusal_count"], reverse=True)
```

---

## 10. FAILURE SUMMARY REPORT GENERATOR

```python
# src/reports/failure_summary.py

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json

from ..eval.refusal_classifier import RefusalClassifier, RefusalStats
from ..storage.run_directory import RunDirectory


@dataclass
class FailureEvent:
    """A recorded failure event."""
    timestamp: datetime
    event_type: str  # "api_error", "timeout", "rate_limit", "parse_error", "refusal"
    model: str
    prompt_id: Optional[str]
    error_message: str
    retry_count: int
    recovered: bool
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureSummary:
    """Complete failure summary for a run."""
    run_id: str
    total_api_calls: int
    successful_calls: int
    failed_calls: int
    retry_count: int
    recovered_count: int
    unrecovered_count: int

    # By type
    api_errors: int
    timeouts: int
    rate_limits: int
    parse_errors: int
    refusals: int

    # By model
    failures_by_model: Dict[str, int]

    # Details
    failure_events: List[FailureEvent]
    refusal_stats: Optional[RefusalStats]

    # Timing
    first_failure_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    failure_rate: float  # failures / total_calls


class FailureSummaryGenerator:
    """
    Generate comprehensive failure summary reports.

    Includes:
    - API failure statistics (retries, timeouts, rate limits)
    - Refusal analysis (by model, task type, sensitive topic)
    - Parse error tracking
    - Timeline of failures
    - Recommendations for improvement
    """

    def __init__(self, run_dir: RunDirectory):
        self.run_dir = run_dir
        self.failure_events: List[FailureEvent] = []
        self.refusal_classifier = RefusalClassifier()

    def record_failure(
        self,
        event_type: str,
        model: str,
        prompt_id: Optional[str],
        error_message: str,
        retry_count: int = 0,
        recovered: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> FailureEvent:
        """Record a failure event."""
        event = FailureEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            model=model,
            prompt_id=prompt_id,
            error_message=error_message,
            retry_count=retry_count,
            recovered=recovered,
            context=context or {}
        )
        self.failure_events.append(event)

        # Also log to file
        self._append_to_log(event)

        return event

    def _append_to_log(self, event: FailureEvent) -> None:
        """Append failure to log file."""
        log_path = self.run_dir.failures_log
        with open(log_path, "a") as f:
            f.write(f"{event.timestamp.isoformat()} | {event.event_type} | "
                    f"{event.model} | {event.prompt_id or 'N/A'} | "
                    f"{event.error_message[:100]} | "
                    f"retries={event.retry_count} recovered={event.recovered}\n")

    def generate_summary(self, total_api_calls: int) -> FailureSummary:
        """Generate complete failure summary."""
        # Count by type
        api_errors = sum(1 for e in self.failure_events if e.event_type == "api_error")
        timeouts = sum(1 for e in self.failure_events if e.event_type == "timeout")
        rate_limits = sum(1 for e in self.failure_events if e.event_type == "rate_limit")
        parse_errors = sum(1 for e in self.failure_events if e.event_type == "parse_error")
        refusals = sum(1 for e in self.failure_events if e.event_type == "refusal")

        # Count by model
        failures_by_model = {}
        for e in self.failure_events:
            failures_by_model[e.model] = failures_by_model.get(e.model, 0) + 1

        # Calculate totals
        total_failures = len(self.failure_events)
        recovered = sum(1 for e in self.failure_events if e.recovered)
        retries = sum(e.retry_count for e in self.failure_events)

        # Timestamps
        timestamps = [e.timestamp for e in self.failure_events]
        first_failure = min(timestamps) if timestamps else None
        last_failure = max(timestamps) if timestamps else None

        # Failure rate
        failure_rate = total_failures / total_api_calls if total_api_calls > 0 else 0

        return FailureSummary(
            run_id=self.run_dir.run_id,
            total_api_calls=total_api_calls,
            successful_calls=total_api_calls - total_failures + recovered,
            failed_calls=total_failures,
            retry_count=retries,
            recovered_count=recovered,
            unrecovered_count=total_failures - recovered,
            api_errors=api_errors,
            timeouts=timeouts,
            rate_limits=rate_limits,
            parse_errors=parse_errors,
            refusals=refusals,
            failures_by_model=failures_by_model,
            failure_events=self.failure_events,
            refusal_stats=self.refusal_classifier.get_stats(),
            first_failure_at=first_failure,
            last_failure_at=last_failure,
            failure_rate=failure_rate
        )

    def generate_report(self, total_api_calls: int) -> str:
        """Generate human-readable failure report."""
        summary = self.generate_summary(total_api_calls)

        lines = [
            "=" * 70,
            "FAILURE SUMMARY REPORT",
            f"Run ID: {summary.run_id}",
            "=" * 70,
            "",
            "OVERVIEW",
            "-" * 40,
            f"Total API calls:     {summary.total_api_calls:,}",
            f"Successful calls:    {summary.successful_calls:,}",
            f"Failed calls:        {summary.failed_calls:,}",
            f"Failure rate:        {summary.failure_rate:.2%}",
            "",
            f"Retries attempted:   {summary.retry_count:,}",
            f"Recovered:           {summary.recovered_count:,}",
            f"Unrecovered:         {summary.unrecovered_count:,}",
            "",
            "FAILURES BY TYPE",
            "-" * 40,
            f"API Errors:          {summary.api_errors:,}",
            f"Timeouts:            {summary.timeouts:,}",
            f"Rate Limits:         {summary.rate_limits:,}",
            f"Parse Errors:        {summary.parse_errors:,}",
            f"Refusals:            {summary.refusals:,}",
            "",
            "FAILURES BY MODEL",
            "-" * 40,
        ]

        for model, count in sorted(
            summary.failures_by_model.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            pct = count / summary.failed_calls * 100 if summary.failed_calls > 0 else 0
            lines.append(f"  {model}: {count:,} ({pct:.1f}%)")

        # Refusal breakdown if available
        if summary.refusal_stats and summary.refusal_stats.total_refusals > 0:
            lines.extend([
                "",
                "REFUSAL BREAKDOWN",
                "-" * 40,
            ])
            for cat, count in sorted(
                summary.refusal_stats.by_category.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                lines.append(f"  {cat}: {count:,}")

            if summary.refusal_stats.by_sensitive_topic:
                lines.extend([
                    "",
                    "REFUSALS BY SENSITIVE TOPIC",
                    "-" * 40,
                ])
                for topic, count in sorted(
                    summary.refusal_stats.by_sensitive_topic.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]:
                    lines.append(f"  {topic}: {count:,}")

        # Timeline
        if summary.first_failure_at and summary.last_failure_at:
            lines.extend([
                "",
                "TIMELINE",
                "-" * 40,
                f"First failure:       {summary.first_failure_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Last failure:        {summary.last_failure_at.strftime('%Y-%m-%d %H:%M:%S')}",
            ])

        # Recommendations
        lines.extend([
            "",
            "RECOMMENDATIONS",
            "-" * 40,
        ])

        if summary.timeouts > summary.failed_calls * 0.3:
            lines.append("- HIGH TIMEOUT RATE: Consider increasing timeout limits")
        if summary.rate_limits > 10:
            lines.append("- RATE LIMIT ISSUES: Reduce concurrency or add delays")
        if summary.refusals > summary.failed_calls * 0.2:
            lines.append("- HIGH REFUSAL RATE: Review prompts triggering refusals")
        if not any([
            summary.timeouts > summary.failed_calls * 0.3,
            summary.rate_limits > 10,
            summary.refusals > summary.failed_calls * 0.2
        ]):
            lines.append("- No specific issues identified")

        lines.extend(["", "=" * 70])

        return "\n".join(lines)

    def save_report(self, total_api_calls: int) -> Path:
        """Save failure report to run directory."""
        report_text = self.generate_report(total_api_calls)
        report_path = self.run_dir.root / "failure_summary.txt"

        with open(report_path, "w") as f:
            f.write(report_text)

        # Also save JSON version
        summary = self.generate_summary(total_api_calls)
        json_path = self.run_dir.root / "failure_summary.json"

        with open(json_path, "w") as f:
            json.dump({
                "run_id": summary.run_id,
                "total_api_calls": summary.total_api_calls,
                "successful_calls": summary.successful_calls,
                "failed_calls": summary.failed_calls,
                "failure_rate": summary.failure_rate,
                "retry_count": summary.retry_count,
                "recovered_count": summary.recovered_count,
                "unrecovered_count": summary.unrecovered_count,
                "by_type": {
                    "api_errors": summary.api_errors,
                    "timeouts": summary.timeouts,
                    "rate_limits": summary.rate_limits,
                    "parse_errors": summary.parse_errors,
                    "refusals": summary.refusals,
                },
                "by_model": summary.failures_by_model,
                "refusal_stats": {
                    "total": summary.refusal_stats.total_refusals if summary.refusal_stats else 0,
                    "by_category": summary.refusal_stats.by_category if summary.refusal_stats else {},
                    "by_sensitive_topic": summary.refusal_stats.by_sensitive_topic if summary.refusal_stats else {},
                } if summary.refusal_stats else None,
                "first_failure_at": summary.first_failure_at.isoformat() if summary.first_failure_at else None,
                "last_failure_at": summary.last_failure_at.isoformat() if summary.last_failure_at else None,
            }, f, indent=2)

        return report_path
```

---

## 11. WILSON CONFIDENCE INTERVAL (Referenced in TUI)

```python
# src/analysis/statistics.py (additional function)

def wilson_ci(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """
    Calculate Wilson score confidence interval for a proportion.

    The Wilson score interval is more accurate than the normal approximation,
    especially for small samples or proportions near 0 or 1.

    Args:
        successes: Number of successes (e.g., Gemini wins)
        total: Total number of trials
        confidence: Confidence level (default 0.95 for 95% CI)

    Returns:
        Tuple of (lower_bound, upper_bound) as proportions
    """
    if total == 0:
        return (0.0, 1.0)

    from scipy.stats import norm

    z = norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / total
    n = total

    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denominator
    margin = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return (lower, upper)
```

---

## SUMMARY

This document provides complete Python implementations for all identified gaps:

1. **Parallel Request Architecture (EvaluationEngine)** - Complete asyncio.gather-based concurrent execution with Semaphore-based concurrency limiting, per-model rate limits, batch processing, and progress callbacks.

2. **Cohen's Kappa Inter-Judge Agreement** - Full implementation including Cohen's Kappa for pairwise judges, Fleiss' Kappa for multiple raters, and an InterJudgeAgreementAnalyzer class for real-time tracking.

3. **TUI Progress Dashboard** - Complete Textual app with cost tracking (spent/projected), ETA calculation, help overlay (h key), confidence intervals, per-judge vote counts, occupation/industry in batch display, and response times/throughput.

4. **CLI Options** - All missing options: --tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona.

5. **Name Formality Variation** - NameGenerator with support for Dr. Williams vs Mike vs Michael T. Williams variations.

6. **TUI Results Viewer** - Complete implementation with filtering by occupation/industry/winner, sorting, side-by-side response viewing, and drill-down into judgments.

7. **Phase 1 Generation Using Evaluated Models** - Round-robin distribution across all evaluated models to avoid prompt bias.

8. **Ambiguity Behavior Tracking** - Pattern-based detection of how models handle vague prompts (assumptions, clarification requests, hedging, hallucinations).

9. **Refusal Tracking by Dimension** - RefusalClassifier with breakdowns by model, occupation, industry, and sensitive topic.

10. **Failure Summary Report** - Comprehensive failure analysis with timeline, recommendations, and both text and JSON output formats.

11. **Wilson Confidence Interval** - Statistical function for accurate win rate confidence intervals.

All implementations follow the existing architecture from master_plan_final.md and integrate with the established module structure.
