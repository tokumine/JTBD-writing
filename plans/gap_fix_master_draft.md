# Master Gap Fix Plan: Synthesized Implementation

This document provides the complete, production-ready Python implementations synthesizing the best solutions from all 6 gap fix drafts and critiques.

---

## Table of Contents

1. [EvaluationEngine with Parallel Request Architecture](#1-evaluationengine-with-parallel-request-architecture)
2. [Cohen's Kappa and Inter-Judge Agreement](#2-cohens-kappa-and-inter-judge-agreement)
3. [Cost Tracking in TUI](#3-cost-tracking-in-tui)
4. [Help Overlay](#4-help-overlay)
5. [Complete CLI Options](#5-complete-cli-options)
6. [TUI Enhancements](#6-tui-enhancements)
7. [Name Formality Variation](#7-name-formality-variation)
8. [Ambiguity Behavior Tracking](#8-ambiguity-behavior-tracking)
9. [Refusal Tracking by Dimension](#9-refusal-tracking-by-dimension)
10. [Failure Summary Reports](#10-failure-summary-reports)
11. [Updated Config Classes](#11-updated-config-classes)
12. [Results Viewer](#12-results-viewer)

---

## 1. EvaluationEngine with Parallel Request Architecture

This is the complete, production-ready EvaluationEngine synthesizing all fixes from the critiques:

```python
# src/eval/engine.py

import asyncio
import time
import random
import copy
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from enum import Enum
from threading import Lock

from ..api.openrouter_client import OpenRouterClient, CompletionResponse
from ..prompts.schemas import WritingPrompt
from ..storage.checkpoint import CheckpointManager
from ..storage.database import Database
from .vote_aggregator import VoteAggregator, JudgeVote, AggregatedResult
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .refusal_classifier import RefusalClassifier, RefusalCategory
from .response_analyzer import ResponseAnalyzer
from .ambiguity_tracker import AmbiguityTracker
from ..config.settings import EvalConfig, JudgeConfig
from ..reports.failure_report import FailureLogger

logger = logging.getLogger(__name__)


class EvalPhase(Enum):
    """Current phase of evaluation."""
    INITIALIZING = "initializing"
    GENERATION = "generation"
    JUDGING = "judging"
    ANALYSIS = "analysis"
    COMPLETE = "complete"


@dataclass
class ProgressUpdate:
    """Progress update for TUI callbacks.

    This class is designed to be thread-safe via snapshot mechanism.
    """
    phase: EvalPhase
    total_prompts: int
    completed_prompts: int
    current_prompt_id: Optional[str] = None
    current_occupation: Optional[str] = None
    current_occupation_code: Optional[str] = None
    current_industry: Optional[str] = None
    current_industry_code: Optional[str] = None

    # Per model pair progress: pair_key -> (completed, total, win_rate, ci_low, ci_high)
    model_pair_progress: Dict[str, Tuple[int, int, float, float, float]] = field(default_factory=dict)

    # Per-judge vote tracking for kappa and display
    per_judge_votes: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Inter-judge agreement metrics
    kappa_scores: Dict[str, float] = field(default_factory=dict)
    fleiss_kappa: Optional[float] = None

    # Timing
    elapsed_seconds: float = 0.0
    eta_seconds: Optional[float] = None

    # Cost tracking
    cost_spent: float = 0.0
    cost_projected: float = 0.0

    # Performance metrics
    response_times_ms: List[float] = field(default_factory=list)
    avg_response_time_ms: float = 0.0
    api_throughput: float = 0.0  # Calls per minute

    # Errors
    errors: int = 0
    retries: int = 0
    rate_limit_pauses: int = 0

    # For Kappa calculation - all votes as tuples (prompt_id, judge_model, winner)
    all_votes: List[Tuple[str, str, str]] = field(default_factory=list)


@dataclass
class ModelResponse:
    """A complete response from a model."""
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: float
    refusal_type: Optional[str] = None
    is_error: bool = False
    error_message: Optional[str] = None


@dataclass
class BatchResult:
    """Result from processing a single comparison."""
    prompt_id: str
    model_a: str
    model_b: str
    model_a_response: Optional[ModelResponse]
    model_b_response: Optional[ModelResponse]
    judgments: List[JudgeVote]
    winner: Optional[str]
    cost: float
    errors: List[str] = field(default_factory=list)


class CostTracker:
    """Thread-safe cost tracking."""

    def __init__(self):
        self.total_cost = 0.0
        self._lock = Lock()

    def add_cost(self, cost: float):
        """Add cost (thread-safe, synchronous)."""
        with self._lock:
            self.total_cost += cost

    def get_total(self) -> float:
        """Get total cost (thread-safe)."""
        with self._lock:
            return self.total_cost


class EvaluationEngine:
    """
    Main evaluation orchestrator with parallel request architecture.

    Features:
    - asyncio.gather/TaskGroup for concurrent API calls
    - asyncio.Semaphore for global concurrency limiting (configurable 10-50)
    - Per-model semaphores respecting individual rate limits
    - Exponential backoff with jitter for retries (3 retries default)
    - Progress callbacks for TUI updates during parallel execution
    - Proper majority-of-majorities voting aggregation
    - Thread-safe state mutations
    - Graceful pause/cancel support
    """

    # Per-model concurrency defaults based on typical rate limits
    MODEL_CONCURRENCY_LIMITS = {
        "google/gemini-3.0-pro": 15,
        "google/gemini-3.0-flash": 25,
        "openai/gpt-5.2": 10,
        "openai/gpt-4.1": 20,
        "anthropic/claude-opus-4.5": 8,
        "anthropic/claude-sonnet-4": 15,
        "x-ai/grok-4.1": 12,
        "moonshot/kimi-k2": 10,
    }
    DEFAULT_MODEL_CONCURRENCY = 10

    def __init__(
        self,
        config: EvalConfig,
        client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        database: Database,
        failure_logger: Optional[FailureLogger] = None,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None,
        max_concurrent_global: int = 30,
        max_concurrent_per_model: int = 10,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
    ):
        self.config = config
        self.client = client
        self.checkpoint_manager = checkpoint_manager
        self.database = database
        self.failure_logger = failure_logger
        self.progress_callback = progress_callback
        self.max_concurrent_global = max_concurrent_global
        self.max_concurrent_per_model = max_concurrent_per_model
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay

        # Semaphores - initialized lazily in async context
        self._global_semaphore: Optional[asyncio.Semaphore] = None
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._semaphores_initialized = False

        # Thread-safe locks
        self._state_lock = Lock()
        self._cost_lock = Lock()

        # Cost tracking
        self._cost_tracker = CostTracker()

        # Components
        self.vote_aggregator = VoteAggregator(
            votes_per_judge=config.judge_config.votes_per_judge
        )
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.refusal_classifier = RefusalClassifier()
        self.response_analyzer = ResponseAnalyzer()
        self.ambiguity_tracker = AmbiguityTracker()

        # Statistics tracking
        self._start_time: Optional[float] = None
        self._completed_prompts = 0
        self._response_times: List[float] = []
        self._api_call_timestamps: List[float] = []
        self._errors = 0
        self._retries = 0
        self._rate_limit_pauses = 0
        self._current_phase = EvalPhase.INITIALIZING

        # Per-model pair tracking
        self._pair_results: Dict[str, Dict[str, int]] = {}

        # Per-judge vote tracking for kappa calculation
        self._per_judge_votes: Dict[str, Dict[str, int]] = {}
        self._all_vote_records: List[Tuple[str, str, str]] = []

        # Pause/cancel control
        self._paused = asyncio.Event()
        self._paused.set()  # Not paused initially
        self._shutdown_requested = False

        # ETA calculation state
        self._batch_completion_times: List[float] = []

        # Response cache for retries
        self._response_cache: Dict[Tuple[str, str], ModelResponse] = {}

    def _ensure_semaphores(self):
        """Initialize semaphores - must be called within async context."""
        if not self._semaphores_initialized:
            self._global_semaphore = asyncio.Semaphore(self.max_concurrent_global)
            self._semaphores_initialized = True

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore for concurrency control."""
        self._ensure_semaphores()
        if model not in self._model_semaphores:
            limit = self.MODEL_CONCURRENCY_LIMITS.get(
                model, self.DEFAULT_MODEL_CONCURRENCY
            )
            limit = min(limit, self.max_concurrent_per_model)
            self._model_semaphores[model] = asyncio.Semaphore(limit)
        return self._model_semaphores[model]

    def pause(self):
        """Pause evaluation."""
        self._paused.clear()

    def resume(self):
        """Resume evaluation."""
        self._paused.set()

    def request_shutdown(self):
        """Request graceful shutdown."""
        self._shutdown_requested = True
        self.resume()  # Unpause to allow shutdown

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
        batch_size: int = 10
    ) -> List[BatchResult]:
        """Run full evaluation with parallel processing."""
        self._start_time = time.time()
        self._current_phase = EvalPhase.GENERATION
        results: List[BatchResult] = []

        # Resume from checkpoint if available
        completed_ids = await self.checkpoint_manager.get_completed_prompt_ids()
        remaining_prompts = [p for p in prompts if p.prompt_id not in completed_ids]

        self._completed_prompts = len(completed_ids)
        total_prompts = len(prompts)

        # Initialize pair tracking
        for gemini_model, competitor_model in self.config.model_pairs:
            pair_key = f"{gemini_model}_vs_{competitor_model}"
            self._pair_results[pair_key] = {"gemini": 0, "competitor": 0, "tie": 0}

        logger.info(f"Starting evaluation: {len(remaining_prompts)} remaining of {total_prompts} prompts")

        # Process prompts in batches
        for batch_start in range(0, len(remaining_prompts), batch_size):
            if self._shutdown_requested:
                logger.info("Shutdown requested, saving checkpoint...")
                break

            # Wait if paused
            await self._paused.wait()

            batch_end = min(batch_start + batch_size, len(remaining_prompts))
            batch = remaining_prompts[batch_start:batch_end]
            batch_start_time = time.time()

            # Process all prompts in batch
            batch_results = await self._process_batch(batch, total_prompts)
            results.extend(batch_results)

            # Save checkpoint after each batch
            await self.checkpoint_manager.save_batch_results(batch_results)

            # Track batch completion time for ETA
            batch_time = time.time() - batch_start_time
            self._batch_completion_times.append(batch_time)
            if len(self._batch_completion_times) > 10:
                self._batch_completion_times.pop(0)

        self._current_phase = EvalPhase.COMPLETE
        await self._emit_progress(total_prompts, None)

        # Generate failure summary if logger available
        if self.failure_logger:
            self.failure_logger.generate_report()

        return results

    async def _process_batch(
        self,
        prompts: List[WritingPrompt],
        total_prompts: int
    ) -> List[BatchResult]:
        """Process a batch of prompts across all model pairs."""
        results = []

        for prompt in prompts:
            if self._shutdown_requested:
                break

            # Wait if paused
            await self._paused.wait()

            # Process all model pairs for this prompt
            prompt_results = await self._process_prompt_all_pairs(prompt)
            results.extend(prompt_results)

            # Update progress
            with self._state_lock:
                self._completed_prompts += 1

            await self._emit_progress(total_prompts, prompt)

        return results

    async def _process_prompt_all_pairs(
        self,
        prompt: WritingPrompt
    ) -> List[BatchResult]:
        """Process a single prompt against all model pairs."""

        # Collect all unique models needed
        models_needed = set()
        for gemini_model, competitor_model in self.config.model_pairs:
            models_needed.add(gemini_model)
            models_needed.add(competitor_model)

        # Generate responses in parallel with proper semaphore handling
        self._current_phase = EvalPhase.GENERATION
        model_responses: Dict[str, ModelResponse] = {}

        async def generate_with_semaphore(model: str) -> Tuple[str, Optional[ModelResponse]]:
            async with self._global_semaphore:
                async with self._get_model_semaphore(model):
                    response = await self._generate_response(prompt, model)
                    return model, response

        # Execute all generation in parallel
        tasks = [generate_with_semaphore(m) for m in models_needed]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results_raw:
            if isinstance(result, Exception):
                logger.error(f"Generation failed: {result}")
                with self._state_lock:
                    self._errors += 1
            elif result:
                model, response = result
                if response:
                    model_responses[model] = response

        # Now run judging for each pair
        self._current_phase = EvalPhase.JUDGING
        batch_results = []

        for gemini_model, competitor_model in self.config.model_pairs:
            gemini_response = model_responses.get(gemini_model)
            competitor_response = model_responses.get(competitor_model)

            result = await self._run_comparison(
                prompt,
                gemini_model, competitor_model,
                gemini_response, competitor_response
            )
            batch_results.append(result)

        return batch_results

    async def _run_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_response: Optional[ModelResponse],
        competitor_response: Optional[ModelResponse]
    ) -> BatchResult:
        """Run judging for a single comparison."""

        errors = []
        total_cost = 0.0
        judgments = []
        winner = None

        # Track costs from responses
        if gemini_response:
            total_cost += gemini_response.cost
        if competitor_response:
            total_cost += competitor_response.cost

        # Handle auto-loss cases
        if not gemini_response and competitor_response:
            winner = competitor_model
            errors.append(f"Gemini ({gemini_model}) failed - auto-loss")
        elif gemini_response and not competitor_response:
            winner = gemini_model
            errors.append(f"Competitor ({competitor_model}) failed - auto-loss")
        elif not gemini_response and not competitor_response:
            winner = None
            errors.append("Both models failed")
        else:
            # Check for refusals
            gemini_refused = gemini_response.refusal_type is not None
            competitor_refused = competitor_response.refusal_type is not None

            if gemini_refused and not competitor_refused:
                winner = competitor_model
                errors.append(f"Gemini refused ({gemini_response.refusal_type}) - auto-loss")
            elif competitor_refused and not gemini_refused:
                winner = gemini_model
                errors.append(f"Competitor refused ({competitor_response.refusal_type}) - auto-loss")
            elif gemini_refused and competitor_refused:
                winner = None
                errors.append("Both models refused - tie")
            else:
                # Run full judging
                judgments, judge_cost = await self._run_judging(
                    prompt, gemini_response, competitor_response,
                    gemini_model, competitor_model
                )
                total_cost += judge_cost
                winner = self.vote_aggregator.aggregate_majority_of_majorities(
                    judgments, gemini_model, competitor_model
                )

        # Update pair tracking
        pair_key = f"{gemini_model}_vs_{competitor_model}"
        with self._state_lock:
            if pair_key not in self._pair_results:
                self._pair_results[pair_key] = {"gemini": 0, "competitor": 0, "tie": 0}

            if winner == gemini_model:
                self._pair_results[pair_key]["gemini"] += 1
            elif winner == competitor_model:
                self._pair_results[pair_key]["competitor"] += 1
            else:
                self._pair_results[pair_key]["tie"] += 1

        self._cost_tracker.add_cost(total_cost)

        return BatchResult(
            prompt_id=prompt.prompt_id,
            model_a=gemini_model,
            model_b=competitor_model,
            model_a_response=gemini_response,
            model_b_response=competitor_response,
            judgments=judgments,
            winner=winner,
            cost=total_cost,
            errors=errors
        )

    async def _generate_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> Optional[ModelResponse]:
        """Generate a single model response with retry logic."""

        # Check cache first
        cache_key = (prompt.prompt_id, model)
        if cache_key in self._response_cache:
            return self._response_cache[cache_key]

        system_prompt = self._build_system_prompt(prompt)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt.full_prompt}
        ]

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                response = await self.client.complete(
                    model=model,
                    messages=messages,
                    temperature=0.7
                )

                latency = (time.time() - start_time) * 1000
                with self._state_lock:
                    self._response_times.append(latency)
                    self._api_call_timestamps.append(time.time())

                # Check for refusal
                refusal = self.refusal_classifier.classify(response.content)

                # Track ambiguity handling if prompt was ambiguous
                if getattr(prompt, 'is_ambiguous', False):
                    self.ambiguity_tracker.analyze_response(
                        prompt.prompt_id,
                        model,
                        getattr(prompt, 'ambiguity_type', 'unknown'),
                        response.content,
                        prompt.full_prompt
                    )

                # Calculate cost if not provided
                cost = response.cost
                if cost is None or cost == 0:
                    cost = self._estimate_cost(model, response.input_tokens, response.output_tokens)

                result = ModelResponse(
                    model=model,
                    content=response.content,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    latency_ms=latency,
                    cost=cost,
                    refusal_type=refusal
                )

                # Cache successful response
                self._response_cache[cache_key] = result
                return result

            except Exception as e:
                last_error = e
                with self._state_lock:
                    self._retries += 1

                # Check for rate limit
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    with self._state_lock:
                        self._rate_limit_pauses += 1

                # Log failure
                if self.failure_logger:
                    self.failure_logger.log_failure(
                        prompt_id=prompt.prompt_id,
                        model=model,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        retry_count=attempt + 1,
                        recovered=False
                    )

                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self.base_retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)

        with self._state_lock:
            self._errors += 1
        logger.error(f"Generation failed after {self.max_retries} attempts for {model}: {last_error}")

        return ModelResponse(
            model=model,
            content="",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            cost=0,
            is_error=True,
            error_message=str(last_error)
        )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on model pricing."""
        pricing = {
            "google/gemini-3.0-pro": {"input": 0.00125, "output": 0.005},
            "google/gemini-3.0-flash": {"input": 0.000075, "output": 0.0003},
            "openai/gpt-5.2": {"input": 0.015, "output": 0.06},
            "openai/gpt-4.1": {"input": 0.002, "output": 0.008},
            "anthropic/claude-opus-4.5": {"input": 0.015, "output": 0.075},
            "anthropic/claude-sonnet-4": {"input": 0.003, "output": 0.015},
            "x-ai/grok-4.1": {"input": 0.005, "output": 0.015},
            "moonshot/kimi-k2": {"input": 0.003, "output": 0.009},
        }
        rates = pricing.get(model, {"input": 0.01, "output": 0.03})
        return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])

    async def _run_judging(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        model_a: str,
        model_b: str
    ) -> Tuple[List[JudgeVote], float]:
        """Run all judges with proper concurrency control."""

        judgments = []
        total_cost = 0.0

        # Determine position shuffling seed (deterministic)
        seed = hash(f"{prompt.prompt_id}_{model_a}_{model_b}")

        # Determine which personas to use
        if self.config.judge_config.use_both_personas:
            personas = ["writing_expert", "recipient"]
        elif hasattr(self.config.judge_config, 'persona_to_use'):
            personas = [self.config.judge_config.persona_to_use]
        else:
            personas = ["writing_expert"]

        # Create all judging tasks
        judge_tasks = []
        task_metadata = []

        for judge_model in self.config.judge_config.models:
            for vote_idx in range(self.config.judge_config.votes_per_judge):
                # Deterministic position assignment
                position_seed = seed + vote_idx + hash(judge_model)
                a_is_first = (position_seed % 2) == 0

                for persona in personas:
                    task = self._single_judge_call(
                        prompt, response_a, response_b,
                        model_a, model_b,
                        judge_model, persona,
                        a_is_first, vote_idx
                    )
                    judge_tasks.append(task)
                    task_metadata.append({
                        "judge_model": judge_model,
                        "persona": persona,
                        "vote_idx": vote_idx
                    })

        # Execute with concurrency control
        async def run_judge_with_semaphore(task_coro, judge_model):
            async with self._global_semaphore:
                async with self._get_model_semaphore(judge_model):
                    return await task_coro

        # Build wrapped tasks
        wrapped_tasks = []
        for i, (task, meta) in enumerate(zip(judge_tasks, task_metadata)):
            wrapped_tasks.append(
                run_judge_with_semaphore(task, meta["judge_model"])
            )

        results = await asyncio.gather(*wrapped_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                with self._state_lock:
                    self._errors += 1
                logger.error(f"Judge call failed: {result}")
            elif result:
                vote, cost = result
                judgments.append(vote)
                total_cost += cost

                # Track for kappa calculation
                meta = task_metadata[i]
                judge_key = meta["judge_model"]

                with self._state_lock:
                    if judge_key not in self._per_judge_votes:
                        self._per_judge_votes[judge_key] = {"gemini": 0, "competitor": 0, "tie": 0}

                    vote_label = "gemini" if vote.winner == model_a else ("competitor" if vote.winner == model_b else "tie")
                    self._per_judge_votes[judge_key][vote_label] += 1

                    self._all_vote_records.append((
                        prompt.prompt_id,
                        judge_key,
                        vote_label
                    ))

        return judgments, total_cost

    async def _single_judge_call(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        model_a: str,
        model_b: str,
        judge_model: str,
        persona: str,
        a_is_first: bool,
        vote_idx: int
    ) -> Optional[Tuple[JudgeVote, float]]:
        """Execute a single judge call."""

        try:
            # Position shuffling
            if a_is_first:
                first_response, second_response = response_a.content, response_b.content
                first_model, second_model = model_a, model_b
            else:
                first_response, second_response = response_b.content, response_a.content
                first_model, second_model = model_b, model_a

            system_prompt, user_prompt = self.judge_builder.build_judge_prompt(
                prompt=prompt,
                response_a=first_response,
                response_b=second_response,
                persona=persona
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = await self.client.complete(
                model=judge_model,
                messages=messages,
                temperature=0.3
            )

            with self._state_lock:
                self._api_call_timestamps.append(time.time())

            # Parse judgment
            parsed = self.judge_parser.parse(response.content)

            # Map back to actual models
            if parsed.winner == "A":
                actual_winner = first_model
            elif parsed.winner == "B":
                actual_winner = second_model
            else:
                actual_winner = None

            vote = JudgeVote(
                judge_model=judge_model,
                persona=persona,
                vote_index=vote_idx,
                winner=actual_winner,
                reasoning=parsed.reasoning,
                confidence=parsed.confidence,
                quality_a=parsed.quality_a if a_is_first else parsed.quality_b,
                quality_b=parsed.quality_b if a_is_first else parsed.quality_a,
                position_a_was=first_model
            )

            cost = response.cost or self._estimate_cost(
                judge_model, response.input_tokens, response.output_tokens
            )

            return vote, cost

        except Exception as e:
            logger.error(f"Judge call failed for {judge_model}: {e}")
            return None

    def _build_system_prompt(self, prompt: WritingPrompt) -> str:
        """Build system prompt for response generation with defensive coding."""
        writer = getattr(prompt, 'writer', None)
        company = getattr(prompt, 'company', None)

        name = getattr(writer, 'name', 'a professional') if writer else 'a professional'
        job_title = getattr(writer, 'job_title', 'employee') if writer else 'employee'
        company_name = getattr(company, 'name', 'a company') if company else 'a company'
        skill_level = getattr(writer, 'skill_level', 3) if writer else 3
        age = getattr(writer, 'age', 35) if writer else 35
        generation = getattr(writer, 'generation', 'professional') if writer else 'professional'
        formality = getattr(prompt, 'formality_level', 3)

        parts = [
            f"You are {name}, a {job_title} at {company_name}.",
            f"You are {age} years old ({generation} generation).",
            f"Your writing skill level is {skill_level}/5.",
            f"This communication requires formality level {formality}/5.",
            "Write naturally and authentically for this scenario."
        ]

        return " ".join(parts)

    async def _emit_progress(
        self,
        total_prompts: int,
        current_prompt: Optional[WritingPrompt]
    ):
        """Emit progress update to callback."""
        if not self.progress_callback:
            return

        elapsed = time.time() - self._start_time if self._start_time else 0

        # Calculate ETA using batch completion times
        eta = self._calculate_eta(self._completed_prompts, total_prompts, elapsed)

        # Calculate throughput (calls per minute in last 60 seconds)
        now = time.time()
        cutoff = now - 60
        with self._state_lock:
            recent_calls = [t for t in self._api_call_timestamps if t > cutoff]
        throughput = len(recent_calls)

        # Calculate cost projection
        total_cost = self._cost_tracker.get_total()
        if self._completed_prompts > 0:
            cost_per_prompt = total_cost / self._completed_prompts
            projected_cost = cost_per_prompt * total_prompts
        else:
            projected_cost = 0.0

        # Calculate win rates with confidence intervals
        pair_progress = {}
        for pair_key, results in self._pair_results.items():
            wins = results["gemini"]
            total = results["gemini"] + results["competitor"] + results["tie"]
            non_tie_total = results["gemini"] + results["competitor"]

            if non_tie_total > 0:
                from ..analysis.statistics import wilson_confidence_interval
                win_rate = wins / non_tie_total
                ci_low, ci_high = wilson_confidence_interval(wins, non_tie_total)
            else:
                win_rate, ci_low, ci_high = 0.5, 0.0, 1.0

            pair_progress[pair_key] = (total, total_prompts, win_rate, ci_low, ci_high)

        # Calculate kappa scores
        kappa_scores = {}
        fleiss_kappa = None
        if len(self._all_vote_records) >= 10:
            try:
                from ..analysis.statistics import calculate_inter_judge_agreement
                agreement = calculate_inter_judge_agreement(self._all_vote_records)
                fleiss_kappa = agreement.get("fleiss_kappa", {}).kappa if agreement.get("fleiss_kappa") else None
                for pair, result in agreement.get("pairwise_kappa", {}).items():
                    kappa_scores[f"{pair[0]}_vs_{pair[1]}"] = result.kappa
            except Exception as e:
                logger.warning(f"Could not calculate kappa: {e}")

        # Average response time
        with self._state_lock:
            avg_response_time = sum(self._response_times) / len(self._response_times) if self._response_times else 0
            response_times_copy = self._response_times[-100:].copy()

        # Get current prompt context
        current_occupation = None
        current_occupation_code = None
        current_industry = None
        current_industry_code = None
        current_prompt_id = None

        if current_prompt:
            current_prompt_id = current_prompt.prompt_id
            current_occupation = getattr(current_prompt, 'occupation_title', None) or getattr(getattr(current_prompt, 'onet_task', None), 'occupation_title', None)
            current_occupation_code = getattr(current_prompt, 'occupation_code', None) or getattr(getattr(current_prompt, 'onet_task', None), 'occupation_code', None)
            current_industry = getattr(current_prompt, 'industry_name', None) or getattr(getattr(current_prompt, 'company', None), 'industry', None)
            current_industry_code = getattr(current_prompt, 'naics_code', None) or getattr(getattr(current_prompt, 'company', None), 'naics_code', None)

        update = ProgressUpdate(
            phase=self._current_phase,
            total_prompts=total_prompts,
            completed_prompts=self._completed_prompts,
            current_prompt_id=current_prompt_id,
            current_occupation=current_occupation,
            current_occupation_code=current_occupation_code,
            current_industry=current_industry,
            current_industry_code=current_industry_code,
            model_pair_progress=pair_progress,
            per_judge_votes=copy.deepcopy(self._per_judge_votes),
            kappa_scores=kappa_scores,
            fleiss_kappa=fleiss_kappa,
            elapsed_seconds=elapsed,
            eta_seconds=eta,
            cost_spent=total_cost,
            cost_projected=projected_cost,
            response_times_ms=response_times_copy,
            avg_response_time_ms=avg_response_time,
            api_throughput=throughput,
            errors=self._errors,
            retries=self._retries,
            rate_limit_pauses=self._rate_limit_pauses,
            all_votes=self._all_vote_records.copy()
        )

        self.progress_callback(update)

    def _calculate_eta(self, completed: int, total: int, elapsed: float) -> Optional[float]:
        """Calculate ETA using batch completion patterns."""
        if completed == 0 or elapsed == 0:
            return None

        # Use weighted average of recent batch times if available
        if self._batch_completion_times:
            # Weight recent batches more heavily
            weights = [1.5 ** i for i in range(len(self._batch_completion_times))]
            weighted_avg = sum(t * w for t, w in zip(self._batch_completion_times, weights))
            weighted_avg /= sum(weights)

            batch_size = 10  # Default
            remaining_batches = (total - completed) / batch_size
            return remaining_batches * weighted_avg

        # Fallback to linear extrapolation
        rate = completed / elapsed
        remaining = total - completed
        return remaining / rate if rate > 0 else None
```

---

## 2. Cohen's Kappa and Inter-Judge Agreement

Complete implementation for inter-judge agreement metrics:

```python
# src/analysis/statistics.py

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
import math


@dataclass
class KappaResult:
    """Result of kappa calculation."""
    kappa: float
    observed_agreement: float
    expected_agreement: float
    n_samples: int
    interpretation: str  # "poor", "slight", "fair", "moderate", "substantial", "almost_perfect"

    @staticmethod
    def interpret_kappa(kappa: float) -> str:
        """Interpret kappa value using Landis & Koch scale."""
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


@dataclass
class AgreementMetrics:
    """Complete inter-judge agreement metrics."""
    fleiss_kappa: Optional[KappaResult] = None
    pairwise_kappa: Dict[Tuple[str, str], KappaResult] = field(default_factory=dict)
    overall_agreement_rate: float = 0.0
    per_category_agreement: Dict[str, float] = field(default_factory=dict)


def cohens_kappa(
    ratings_1: List[str],
    ratings_2: List[str],
    categories: Optional[List[str]] = None
) -> KappaResult:
    """
    Calculate Cohen's Kappa for two raters.

    Args:
        ratings_1: List of ratings from first rater
        ratings_2: List of ratings from second rater (same order as ratings_1)
        categories: Optional list of all possible categories

    Returns:
        KappaResult with kappa value and interpretation
    """
    if len(ratings_1) != len(ratings_2):
        raise ValueError("Rating lists must have the same length")

    n = len(ratings_1)
    if n == 0:
        return KappaResult(
            kappa=0.0,
            observed_agreement=0.0,
            expected_agreement=0.0,
            n_samples=0,
            interpretation="poor"
        )

    # Get all categories
    if categories is None:
        categories = list(set(ratings_1) | set(ratings_2))

    # Build confusion matrix
    matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r1, r2 in zip(ratings_1, ratings_2):
        matrix[r1][r2] += 1

    # Calculate observed agreement (diagonal sum / total)
    observed_agreement = sum(matrix[cat][cat] for cat in categories) / n

    # Calculate expected agreement
    # P(both rate as category c) = P(rater1 = c) * P(rater2 = c)
    expected_agreement = 0.0
    for cat in categories:
        p1 = sum(matrix[cat].values()) / n  # P(rater1 = cat)
        p2 = sum(matrix[r][cat] for r in categories) / n  # P(rater2 = cat)
        expected_agreement += p1 * p2

    # Cohen's Kappa formula
    if expected_agreement == 1.0:
        kappa = 1.0 if observed_agreement == 1.0 else 0.0
    else:
        kappa = (observed_agreement - expected_agreement) / (1.0 - expected_agreement)

    return KappaResult(
        kappa=kappa,
        observed_agreement=observed_agreement,
        expected_agreement=expected_agreement,
        n_samples=n,
        interpretation=KappaResult.interpret_kappa(kappa)
    )


def fleiss_kappa(
    ratings_matrix: List[Dict[str, int]],
    categories: Optional[List[str]] = None
) -> KappaResult:
    """
    Calculate Fleiss' Kappa for multiple raters.

    Args:
        ratings_matrix: List of dicts, one per subject, mapping category to count of raters
                       who assigned that category. E.g., [{"gemini": 2, "competitor": 1}, ...]
        categories: Optional list of all possible categories

    Returns:
        KappaResult with Fleiss' kappa value
    """
    if not ratings_matrix:
        return KappaResult(
            kappa=0.0,
            observed_agreement=0.0,
            expected_agreement=0.0,
            n_samples=0,
            interpretation="poor"
        )

    N = len(ratings_matrix)  # Number of subjects

    # Get all categories and number of raters
    if categories is None:
        categories = list(set(cat for row in ratings_matrix for cat in row.keys()))

    # Get number of raters per subject (should be consistent)
    n = sum(ratings_matrix[0].values())  # Number of raters

    # Calculate proportion of all assignments to each category (P_j)
    category_proportions: Dict[str, float] = {}
    total_assignments = N * n

    for cat in categories:
        cat_count = sum(row.get(cat, 0) for row in ratings_matrix)
        category_proportions[cat] = cat_count / total_assignments if total_assignments > 0 else 0

    # Calculate P_bar (mean of P_i)
    # P_i = (1 / (n*(n-1))) * sum_j(n_ij * (n_ij - 1)) for each subject i
    p_i_values = []
    for row in ratings_matrix:
        sum_squared = sum(row.get(cat, 0) ** 2 for cat in categories)
        if n > 1:
            p_i = (sum_squared - n) / (n * (n - 1))
        else:
            p_i = 1.0
        p_i_values.append(p_i)

    P_bar = sum(p_i_values) / N if N > 0 else 0  # Observed agreement

    # Calculate P_e (expected agreement by chance)
    P_e = sum(p ** 2 for p in category_proportions.values())

    # Fleiss' Kappa
    if P_e == 1.0:
        kappa = 1.0 if P_bar == 1.0 else 0.0
    else:
        kappa = (P_bar - P_e) / (1.0 - P_e)

    return KappaResult(
        kappa=kappa,
        observed_agreement=P_bar,
        expected_agreement=P_e,
        n_samples=N,
        interpretation=KappaResult.interpret_kappa(kappa)
    )


def calculate_inter_judge_agreement(
    vote_records: List[Tuple[str, str, str]]
) -> Dict[str, any]:
    """
    Calculate comprehensive inter-judge agreement metrics.

    Args:
        vote_records: List of (prompt_id, judge_model, vote) tuples
                     where vote is "gemini", "competitor", or "tie"

    Returns:
        Dictionary with:
        - "fleiss_kappa": KappaResult for all judges
        - "pairwise_kappa": Dict mapping (judge1, judge2) -> KappaResult
        - "overall_agreement_rate": float
        - "per_category_agreement": Dict[str, float]
    """
    if not vote_records:
        return {
            "fleiss_kappa": None,
            "pairwise_kappa": {},
            "overall_agreement_rate": 0.0,
            "per_category_agreement": {}
        }

    # Organize by prompt
    prompt_votes: Dict[str, Dict[str, str]] = defaultdict(dict)
    judges: Set[str] = set()
    categories = {"gemini", "competitor", "tie"}

    for prompt_id, judge_model, vote in vote_records:
        prompt_votes[prompt_id][judge_model] = vote
        judges.add(judge_model)

    judges_list = sorted(judges)
    prompts_list = sorted(prompt_votes.keys())

    # Filter to prompts where all judges voted
    complete_prompts = [
        p for p in prompts_list
        if all(j in prompt_votes[p] for j in judges_list)
    ]

    if not complete_prompts:
        return {
            "fleiss_kappa": None,
            "pairwise_kappa": {},
            "overall_agreement_rate": 0.0,
            "per_category_agreement": {}
        }

    # Build ratings matrix for Fleiss' Kappa
    ratings_matrix = []
    for prompt_id in complete_prompts:
        category_counts = {cat: 0 for cat in categories}
        for judge in judges_list:
            vote = prompt_votes[prompt_id].get(judge)
            if vote in categories:
                category_counts[vote] += 1
        ratings_matrix.append(category_counts)

    fleiss = fleiss_kappa(ratings_matrix, list(categories))

    # Calculate pairwise Cohen's Kappa
    pairwise = {}
    for i, judge1 in enumerate(judges_list):
        for judge2 in judges_list[i+1:]:
            ratings_1 = [prompt_votes[p][judge1] for p in complete_prompts]
            ratings_2 = [prompt_votes[p][judge2] for p in complete_prompts]
            kappa = cohens_kappa(ratings_1, ratings_2, list(categories))
            pairwise[(judge1, judge2)] = kappa

    # Calculate overall agreement rate (all judges agree)
    agreements = 0
    for prompt_id in complete_prompts:
        votes = [prompt_votes[prompt_id][j] for j in judges_list]
        if len(set(votes)) == 1:
            agreements += 1
    overall_agreement = agreements / len(complete_prompts) if complete_prompts else 0.0

    # Per-category agreement (when majority votes for category, what % is unanimous?)
    per_category = {}
    for cat in categories:
        majority_count = 0
        unanimous_count = 0
        for prompt_id in complete_prompts:
            votes = [prompt_votes[prompt_id][j] for j in judges_list]
            cat_votes = sum(1 for v in votes if v == cat)
            if cat_votes > len(votes) / 2:  # Majority
                majority_count += 1
                if cat_votes == len(votes):  # Unanimous
                    unanimous_count += 1
        per_category[cat] = unanimous_count / majority_count if majority_count > 0 else 0.0

    return {
        "fleiss_kappa": fleiss,
        "pairwise_kappa": pairwise,
        "overall_agreement_rate": overall_agreement,
        "per_category_agreement": per_category
    }


def wilson_confidence_interval(
    successes: int,
    total: int,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """
    Calculate Wilson score confidence interval for a proportion.

    More accurate than normal approximation for small samples.

    Args:
        successes: Number of successes
        total: Total number of trials
        confidence: Confidence level (default 0.95)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if total == 0:
        return (0.0, 1.0)

    # Z-score for confidence level
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence, 1.96)

    p_hat = successes / total

    denominator = 1 + z**2 / total
    center = (p_hat + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * total)) / total) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return (lower, upper)


def bootstrap_confidence_interval(
    data: List[float],
    statistic_fn: callable = lambda x: sum(x) / len(x),
    confidence: float = 0.95,
    n_bootstrap: int = 1000
) -> Tuple[float, float]:
    """
    Calculate bootstrap confidence interval for any statistic.

    Args:
        data: List of values
        statistic_fn: Function to compute statistic (default: mean)
        confidence: Confidence level
        n_bootstrap: Number of bootstrap samples

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    import random

    if not data:
        return (0.0, 0.0)

    n = len(data)
    statistics = []

    for _ in range(n_bootstrap):
        sample = [random.choice(data) for _ in range(n)]
        statistics.append(statistic_fn(sample))

    statistics.sort()
    alpha = 1 - confidence
    lower_idx = int(alpha / 2 * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap)

    return (statistics[lower_idx], statistics[upper_idx])
```

---

## 3. Cost Tracking in TUI

Complete cost tracking widget for the TUI progress dashboard:

```python
# src/tui/widgets/cost_tracker.py

from textual.widgets import Static
from textual.reactive import reactive
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typing import Optional


class CostTrackerWidget(Static):
    """Widget displaying real-time cost tracking with projections."""

    cost_spent: reactive[float] = reactive(0.0)
    cost_projected: reactive[float] = reactive(0.0)
    cost_budget: reactive[Optional[float]] = reactive(None)

    def __init__(
        self,
        budget: Optional[float] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.cost_budget = budget

    def compose(self):
        yield Static(id="cost-display")

    def watch_cost_spent(self, value: float) -> None:
        self._update_display()

    def watch_cost_projected(self, value: float) -> None:
        self._update_display()

    def _update_display(self) -> None:
        table = Table(box=None, show_header=False, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")

        # Current spend
        spent_text = Text(f"${self.cost_spent:.4f}", style="green")
        table.add_row("Spent:", spent_text)

        # Projected total
        proj_style = "yellow"
        if self.cost_budget and self.cost_projected > self.cost_budget:
            proj_style = "red bold"
        proj_text = Text(f"${self.cost_projected:.4f}", style=proj_style)
        table.add_row("Projected:", proj_text)

        # Budget if set
        if self.cost_budget:
            budget_text = Text(f"${self.cost_budget:.4f}", style="blue")
            table.add_row("Budget:", budget_text)

            # Remaining/over budget
            remaining = self.cost_budget - self.cost_spent
            if remaining >= 0:
                rem_text = Text(f"${remaining:.4f}", style="green")
                table.add_row("Remaining:", rem_text)
            else:
                over_text = Text(f"-${abs(remaining):.4f}", style="red bold")
                table.add_row("Over Budget:", over_text)

            # Progress bar
            pct = min(1.0, self.cost_spent / self.cost_budget) if self.cost_budget > 0 else 0
            bar_width = 20
            filled = int(pct * bar_width)
            bar_color = "green" if pct < 0.8 else ("yellow" if pct < 1.0 else "red")
            bar = f"[{bar_color}]{'█' * filled}{'░' * (bar_width - filled)}[/] {pct*100:.0f}%"
            table.add_row("", Text.from_markup(bar))

        panel = Panel(
            table,
            title="[bold]Cost Tracking[/]",
            border_style="cyan"
        )

        self.query_one("#cost-display", Static).update(panel)

    def update_costs(self, spent: float, projected: float) -> None:
        """Update cost values."""
        self.cost_spent = spent
        self.cost_projected = projected


class CostBreakdownWidget(Static):
    """Widget showing cost breakdown by model and phase."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._model_costs: dict = {}
        self._phase_costs: dict = {}

    def update_breakdown(
        self,
        model_costs: dict,
        phase_costs: dict
    ) -> None:
        """Update cost breakdown data."""
        self._model_costs = model_costs
        self._phase_costs = phase_costs
        self._render()

    def _render(self) -> None:
        table = Table(title="Cost Breakdown", box=None)
        table.add_column("Category", style="cyan")
        table.add_column("Cost", justify="right")
        table.add_column("% of Total", justify="right")

        total = sum(self._model_costs.values()) if self._model_costs else 0.01

        # By phase
        table.add_row("[bold]By Phase[/]", "", "")
        for phase, cost in sorted(self._phase_costs.items()):
            pct = (cost / total * 100) if total > 0 else 0
            table.add_row(f"  {phase}", f"${cost:.4f}", f"{pct:.1f}%")

        table.add_row("", "", "")

        # By model
        table.add_row("[bold]By Model[/]", "", "")
        for model, cost in sorted(self._model_costs.items(), key=lambda x: -x[1])[:5]:
            pct = (cost / total * 100) if total > 0 else 0
            short_model = model.split("/")[-1][:15]
            table.add_row(f"  {short_model}", f"${cost:.4f}", f"{pct:.1f}%")

        self.update(Panel(table, border_style="dim"))
```

---

## 4. Help Overlay

Complete help overlay system with 'h' key binding:

```python
# src/tui/widgets/help_overlay.py

from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Vertical, Container
from textual.binding import Binding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class HelpOverlay(ModalScreen):
    """Modal help overlay showing all keyboard shortcuts."""

    BINDINGS = [
        Binding("h", "dismiss", "Close Help"),
        Binding("escape", "dismiss", "Close Help"),
        Binding("q", "dismiss", "Close Help"),
    ]

    CSS = """
    HelpOverlay {
        align: center middle;
    }

    #help-container {
        width: 70;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #help-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
    }

    #help-content {
        height: auto;
    }
    """

    def compose(self):
        with Container(id="help-container"):
            yield Static("[bold cyan]Keyboard Shortcuts[/]", id="help-title")
            yield Static(self._build_help_content(), id="help-content")

    def _build_help_content(self) -> Panel:
        """Build the help content panel."""
        table = Table(box=None, show_header=True, padding=(0, 2))
        table.add_column("Key", style="bold yellow", width=12)
        table.add_column("Action", style="white")

        shortcuts = [
            # Navigation
            ("", "[bold]Navigation[/]"),
            ("h / ?", "Show this help"),
            ("q / Ctrl+C", "Quit application"),
            ("Tab", "Next widget"),
            ("Shift+Tab", "Previous widget"),

            # Evaluation Control
            ("", ""),
            ("", "[bold]Evaluation Control[/]"),
            ("Space / p", "Pause/Resume evaluation"),
            ("s", "Save checkpoint and continue"),
            ("Ctrl+S", "Save checkpoint and pause"),
            ("x", "Cancel evaluation (saves checkpoint)"),

            # View Control
            ("", ""),
            ("", "[bold]View Control[/]"),
            ("1-5", "Switch to tab 1-5"),
            ("r", "Refresh display"),
            ("d", "Toggle detailed view"),
            ("l", "Toggle log panel"),

            # Results Navigation
            ("", ""),
            ("", "[bold]Results Navigation[/]"),
            ("Up/Down", "Navigate results list"),
            ("Enter", "View result details"),
            ("f", "Filter results"),
            ("e", "Export current view"),

            # Advanced
            ("", ""),
            ("", "[bold]Advanced[/]"),
            ("c", "Show cost breakdown"),
            ("k", "Show kappa details"),
            ("m", "Model comparison view"),
            ("t", "Response time histogram"),
        ]

        for key, action in shortcuts:
            if key == "":
                table.add_row("", action)
            else:
                table.add_row(f"[yellow]{key}[/]", action)

        footer = Text("\nPress h, Escape, or q to close", style="dim italic")

        content = Table.grid()
        content.add_row(table)
        content.add_row(footer)

        return Panel(
            content,
            border_style="cyan",
            title="[bold]Help[/]",
            title_align="center"
        )


# Integration into main TUI app
class HelpBindingMixin:
    """Mixin to add help binding to any Textual App."""

    BINDINGS = [
        Binding("h", "show_help", "Help", show=True),
        Binding("question_mark", "show_help", "Help", show=False),
    ]

    def action_show_help(self) -> None:
        """Show the help overlay."""
        self.push_screen(HelpOverlay())


# Usage in main app:
# class EvalTUIApp(HelpBindingMixin, App):
#     BINDINGS = HelpBindingMixin.BINDINGS + [
#         ... other bindings
#     ]
```

---

## 5. Complete CLI Options

Complete CLI implementation with all required options:

```python
# src/cli.py

import typer
from pathlib import Path
from typing import Optional, List
from enum import Enum
import sys
import json

app = typer.Typer(
    name="gemini-eval",
    help="Gemini Writing Evaluation Framework - Compare LLMs on professional writing tasks",
    add_completion=False
)


class OutputFormat(str, Enum):
    """Output format options."""
    json = "json"
    csv = "csv"
    markdown = "markdown"
    pdf = "pdf"


class JudgePersona(str, Enum):
    """Judge persona options."""
    writing_expert = "writing_expert"
    recipient = "recipient"
    both = "both"


def validate_model(value: str) -> str:
    """Validate model format."""
    if not value:
        return value
    # Expected format: provider/model-name
    if "/" not in value:
        raise typer.BadParameter(
            f"Model must be in format 'provider/model-name', got: {value}"
        )
    return value


def validate_model_list(values: Optional[List[str]]) -> Optional[List[str]]:
    """Validate list of models."""
    if not values:
        return values
    return [validate_model(v) for v in values]


def validate_positive(value: int, name: str) -> int:
    """Validate positive integer."""
    if value <= 0:
        raise typer.BadParameter(f"{name} must be positive, got: {value}")
    return value


def validate_range(value: float, min_val: float, max_val: float, name: str) -> float:
    """Validate value is within range."""
    if not min_val <= value <= max_val:
        raise typer.BadParameter(
            f"{name} must be between {min_val} and {max_val}, got: {value}"
        )
    return value


@app.command()
def run(
    # === Core Options ===
    prompts: int = typer.Option(
        100,
        "--prompts", "-n",
        help="Number of prompts to generate/evaluate",
        min=1, max=10000
    ),
    output: Path = typer.Option(
        Path("./results"),
        "--output", "-o",
        help="Output directory for results and checkpoints"
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.json,
        "--format", "-f",
        help="Output format for results"
    ),

    # === Model Selection ===
    gemini_model: str = typer.Option(
        "google/gemini-3.0-pro",
        "--gemini", "-g",
        help="Gemini model to evaluate",
        callback=lambda v: validate_model(v)
    ),
    competitors: Optional[List[str]] = typer.Option(
        None,
        "--competitor", "-c",
        help="Competitor models (can specify multiple)"
    ),
    judge_models: Optional[List[str]] = typer.Option(
        None,
        "--judge", "-j",
        help="Judge models (can specify multiple)"
    ),

    # === Judge Configuration ===
    votes_per_judge: int = typer.Option(
        3,
        "--votes",
        help="Number of votes per judge per comparison",
        min=1, max=9
    ),
    judge_persona: JudgePersona = typer.Option(
        JudgePersona.both,
        "--persona",
        help="Judge persona to use"
    ),

    # === Evaluation Settings ===
    batch_size: int = typer.Option(
        10,
        "--batch-size", "-b",
        help="Prompts per batch",
        min=1, max=100
    ),
    max_concurrent: int = typer.Option(
        30,
        "--concurrent",
        help="Maximum concurrent API calls (10-50)",
        min=10, max=50
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        help="API call timeout in seconds",
        min=10, max=600
    ),
    max_retries: int = typer.Option(
        3,
        "--retries",
        help="Maximum retry attempts per call",
        min=0, max=10
    ),

    # === Cost Control ===
    budget: Optional[float] = typer.Option(
        None,
        "--budget",
        help="Maximum budget in USD (stops when reached)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Estimate costs without running evaluation"
    ),

    # === Checkpoint/Resume ===
    resume: Optional[Path] = typer.Option(
        None,
        "--resume", "-r",
        help="Resume from checkpoint file"
    ),
    checkpoint_interval: int = typer.Option(
        10,
        "--checkpoint-interval",
        help="Save checkpoint every N prompts",
        min=1, max=100
    ),

    # === UI Options ===
    no_tui: bool = typer.Option(
        False,
        "--no-tui",
        help="Disable TUI, use simple progress output"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose logging"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Suppress all output except errors"
    ),

    # === Prompt Configuration ===
    occupation_filter: Optional[str] = typer.Option(
        None,
        "--occupation",
        help="Filter prompts by O*NET occupation code pattern"
    ),
    industry_filter: Optional[str] = typer.Option(
        None,
        "--industry",
        help="Filter prompts by NAICS industry code pattern"
    ),
    task_type: Optional[str] = typer.Option(
        None,
        "--task-type",
        help="Filter by task type (email, report, proposal, etc.)"
    ),
    formality_range: Optional[str] = typer.Option(
        None,
        "--formality",
        help="Formality level range, e.g., '1-3' or '4-5'"
    ),

    # === Analysis Options ===
    confidence_level: float = typer.Option(
        0.95,
        "--confidence",
        help="Confidence level for intervals (0.0-1.0)",
        min=0.5, max=0.99
    ),
    include_refusals: bool = typer.Option(
        True,
        "--include-refusals/--exclude-refusals",
        help="Include refusal analysis in results"
    ),

    # === API Configuration ===
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="OPENROUTER_API_KEY",
        help="OpenRouter API key"
    ),
    api_base: str = typer.Option(
        "https://openrouter.ai/api/v1",
        "--api-base",
        help="OpenRouter API base URL"
    ),
):
    """
    Run the Gemini writing evaluation.

    Examples:

        # Basic run with defaults
        gemini-eval run

        # Custom model selection
        gemini-eval run -g google/gemini-3.0-flash -c openai/gpt-5.2 -c anthropic/claude-opus-4.5

        # Resume from checkpoint
        gemini-eval run --resume ./results/checkpoint.json

        # Dry run to estimate costs
        gemini-eval run -n 1000 --dry-run

        # Filter by occupation
        gemini-eval run --occupation "15-*" --prompts 50
    """
    import asyncio
    from .config.settings import EvalConfig, JudgeConfig
    from .eval.engine import EvaluationEngine
    from .api.openrouter_client import OpenRouterClient
    from .storage.checkpoint import CheckpointManager
    from .storage.database import Database
    from .config.cost_estimator import CostEstimator

    # Validate API key
    if not api_key:
        typer.echo("Error: OPENROUTER_API_KEY not set", err=True)
        raise typer.Exit(1)

    # Validate competitor models
    if competitors:
        competitors = validate_model_list(competitors)
    else:
        competitors = [
            "openai/gpt-5.2",
            "anthropic/claude-opus-4.5",
            "x-ai/grok-4.1"
        ]

    # Validate judge models
    if judge_models:
        judge_models = validate_model_list(judge_models)
    else:
        judge_models = [
            "openai/gpt-5.2",
            "anthropic/claude-opus-4.5",
            "google/gemini-3.0-pro"
        ]

    # Build model pairs
    model_pairs = [(gemini_model, comp) for comp in competitors]

    # Parse formality range
    formality_min, formality_max = 1, 5
    if formality_range:
        try:
            parts = formality_range.split("-")
            formality_min = int(parts[0])
            formality_max = int(parts[1]) if len(parts) > 1 else formality_min
        except (ValueError, IndexError):
            typer.echo(f"Invalid formality range: {formality_range}", err=True)
            raise typer.Exit(1)

    # Determine persona setting
    use_both_personas = judge_persona == JudgePersona.both
    persona_to_use = None if use_both_personas else judge_persona.value

    # Build config
    judge_config = JudgeConfig(
        models=judge_models,
        votes_per_judge=votes_per_judge,
        use_both_personas=use_both_personas,
        persona_to_use=persona_to_use
    )

    config = EvalConfig(
        num_prompts=prompts,
        model_pairs=model_pairs,
        judge_config=judge_config,
        batch_size=batch_size,
        max_concurrent_global=max_concurrent,
        timeout_seconds=timeout,
        max_retries=max_retries,
        budget_usd=budget,
        checkpoint_interval=checkpoint_interval,
        output_dir=output,
        output_format=format.value,
        occupation_filter=occupation_filter,
        industry_filter=industry_filter,
        task_type_filter=task_type,
        formality_range=(formality_min, formality_max),
        confidence_level=confidence_level,
        include_refusals=include_refusals
    )

    # Dry run - just estimate costs
    if dry_run:
        estimator = CostEstimator(config)
        estimate = estimator.estimate()

        typer.echo("\n=== Cost Estimate ===\n")
        typer.echo(f"Prompts:           {prompts}")
        typer.echo(f"Model pairs:       {len(model_pairs)}")
        typer.echo(f"Judges:            {len(judge_models)}")
        typer.echo(f"Votes per judge:   {votes_per_judge}")
        typer.echo(f"Personas:          {'both' if use_both_personas else persona_to_use}")
        typer.echo(f"\nEstimated API calls: {estimate.total_api_calls:,}")
        typer.echo(f"Estimated tokens:    {estimate.total_tokens:,}")
        typer.echo(f"Estimated cost:      ${estimate.total_cost:.2f}")
        typer.echo(f"Estimated time:      {estimate.estimated_minutes:.0f} minutes")

        if budget and estimate.total_cost > budget:
            typer.echo(f"\n⚠️  Warning: Estimated cost exceeds budget of ${budget:.2f}")

        return

    # Initialize components
    output.mkdir(parents=True, exist_ok=True)

    client = OpenRouterClient(
        api_key=api_key,
        base_url=api_base,
        timeout=timeout
    )

    checkpoint_manager = CheckpointManager(output / "checkpoint.json")
    database = Database(output / "results.db")

    # Load checkpoint if resuming
    if resume and resume.exists():
        checkpoint_manager.load(resume)
        if not quiet:
            typer.echo(f"Resuming from checkpoint: {resume}")

    # Progress callback
    def progress_callback(update):
        if quiet:
            return
        if no_tui:
            pct = (update.completed_prompts / update.total_prompts * 100) if update.total_prompts > 0 else 0
            typer.echo(
                f"\r[{update.phase.value}] {update.completed_prompts}/{update.total_prompts} "
                f"({pct:.1f}%) | Cost: ${update.cost_spent:.4f} | "
                f"ETA: {update.eta_seconds/60:.1f}m" if update.eta_seconds else "",
                nl=False
            )

    engine = EvaluationEngine(
        config=config,
        client=client,
        checkpoint_manager=checkpoint_manager,
        database=database,
        progress_callback=progress_callback if no_tui else None,
        max_concurrent_global=max_concurrent,
        max_retries=max_retries
    )

    # Run with TUI or simple mode
    if no_tui:
        # Simple async run
        from .prompts.generator import PromptGenerator
        generator = PromptGenerator(config)
        prompts_list = generator.generate(prompts)
        results = asyncio.run(engine.run_evaluation(prompts_list, batch_size))
    else:
        # TUI mode
        from .tui import EvalTUIApp
        tui_app = EvalTUIApp(engine, config)
        tui_app.run()
        results = tui_app.results

    # Export results
    if results:
        from .reports.exporter import ResultsExporter
        exporter = ResultsExporter(config)
        output_file = output / f"results.{format.value}"
        exporter.export(results, output_file, format.value)
        if not quiet:
            typer.echo(f"\nResults saved to: {output_file}")


@app.command()
def view(
    results_path: Path = typer.Argument(
        ...,
        help="Path to results file or directory"
    ),
    format: OutputFormat = typer.Option(
        None,
        "--format", "-f",
        help="Override output format detection"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Use interactive TUI viewer"
    ),
):
    """
    View evaluation results.

    Examples:
        gemini-eval view ./results/results.json
        gemini-eval view ./results --no-interactive
    """
    from .tui.results_viewer import ResultsViewer

    if not results_path.exists():
        typer.echo(f"Error: Path not found: {results_path}", err=True)
        raise typer.Exit(1)

    if interactive:
        viewer = ResultsViewer(results_path)
        viewer.run()
    else:
        # Simple text output
        from .reports.summary import generate_text_summary
        summary = generate_text_summary(results_path)
        typer.echo(summary)


@app.command()
def estimate(
    prompts: int = typer.Option(100, "--prompts", "-n"),
    gemini_model: str = typer.Option("google/gemini-3.0-pro", "--gemini"),
    competitors: Optional[List[str]] = typer.Option(None, "--competitor", "-c"),
    judges: Optional[List[str]] = typer.Option(None, "--judge", "-j"),
    votes: int = typer.Option(3, "--votes"),
    persona: JudgePersona = typer.Option(JudgePersona.both, "--persona"),
):
    """
    Estimate evaluation costs without running.

    Examples:
        gemini-eval estimate -n 500
        gemini-eval estimate -n 1000 -c openai/gpt-5.2 -c anthropic/claude-opus-4.5
    """
    from .config.cost_estimator import CostEstimator, QuickEstimate

    if not competitors:
        competitors = ["openai/gpt-5.2", "anthropic/claude-opus-4.5", "x-ai/grok-4.1"]
    if not judges:
        judges = ["openai/gpt-5.2", "anthropic/claude-opus-4.5", "google/gemini-3.0-pro"]

    estimate = QuickEstimate.calculate(
        num_prompts=prompts,
        num_model_pairs=len(competitors),
        num_judges=len(judges),
        votes_per_judge=votes,
        both_personas=(persona == JudgePersona.both)
    )

    typer.echo("\n=== Cost Estimate ===\n")
    typer.echo(f"Configuration:")
    typer.echo(f"  Prompts:         {prompts:,}")
    typer.echo(f"  Gemini model:    {gemini_model}")
    typer.echo(f"  Competitors:     {len(competitors)}")
    typer.echo(f"  Judges:          {len(judges)}")
    typer.echo(f"  Votes/judge:     {votes}")
    typer.echo(f"  Personas:        {'both' if persona == JudgePersona.both else persona.value}")

    typer.echo(f"\nEstimates:")
    typer.echo(f"  API calls:       {estimate.api_calls:,}")
    typer.echo(f"  Input tokens:    {estimate.input_tokens:,}")
    typer.echo(f"  Output tokens:   {estimate.output_tokens:,}")
    typer.echo(f"  Total cost:      ${estimate.total_cost:.2f}")
    typer.echo(f"  Time estimate:   {estimate.time_minutes:.0f} minutes")


@app.command()
def models():
    """List available models and their pricing."""
    from .config.presets import MODEL_PRICING

    typer.echo("\n=== Available Models ===\n")

    table_data = []
    for model, pricing in sorted(MODEL_PRICING.items()):
        table_data.append([
            model,
            f"${pricing['input']:.6f}",
            f"${pricing['output']:.6f}"
        ])

    # Simple table output
    typer.echo(f"{'Model':<40} {'Input/1K':<12} {'Output/1K':<12}")
    typer.echo("-" * 64)
    for row in table_data:
        typer.echo(f"{row[0]:<40} {row[1]:<12} {row[2]:<12}")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
```

---

## 6. TUI Enhancements

Complete TUI Progress Dashboard with all widgets:

```python
# src/tui/__init__.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive
import asyncio
from typing import Optional

from .widgets.progress_bar import ProgressBarWidget
from .widgets.cost_tracker import CostTrackerWidget, CostBreakdownWidget
from .widgets.model_pairs import ModelPairsWidget
from .widgets.kappa_display import KappaDisplayWidget
from .widgets.timing_stats import TimingStatsWidget
from .widgets.log_panel import LogPanelWidget
from .widgets.help_overlay import HelpOverlay, HelpBindingMixin
from .widgets.context_display import ContextDisplayWidget

from ..eval.engine import EvaluationEngine, ProgressUpdate, EvalPhase
from ..config.settings import EvalConfig


class EvalTUIApp(HelpBindingMixin, App):
    """Main TUI application for evaluation progress."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 2fr 1fr;
        grid-rows: auto 1fr;
    }

    #progress-section {
        row-span: 1;
        column-span: 2;
        height: auto;
        max-height: 10;
    }

    #left-panel {
        row-span: 1;
        column-span: 1;
    }

    #right-panel {
        row-span: 1;
        column-span: 1;
    }

    .widget-box {
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    #log-container {
        dock: bottom;
        height: 10;
        display: none;
    }

    #log-container.visible {
        display: block;
    }
    """

    BINDINGS = HelpBindingMixin.BINDINGS + [
        Binding("q", "quit", "Quit", show=True),
        Binding("space", "toggle_pause", "Pause/Resume", show=True),
        Binding("p", "toggle_pause", "Pause/Resume", show=False),
        Binding("s", "save_checkpoint", "Save", show=True),
        Binding("x", "cancel", "Cancel", show=True),
        Binding("l", "toggle_log", "Log", show=True),
        Binding("d", "toggle_detail", "Detail", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("1", "tab_1", "Tab 1", show=False),
        Binding("2", "tab_2", "Tab 2", show=False),
        Binding("3", "tab_3", "Tab 3", show=False),
    ]

    # Reactive state
    is_paused: reactive[bool] = reactive(False)
    show_log: reactive[bool] = reactive(False)

    def __init__(
        self,
        engine: EvaluationEngine,
        config: EvalConfig,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.engine = engine
        self.config = config
        self.results = []
        self._eval_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main-container"):
            # Top progress section
            with Container(id="progress-section", classes="widget-box"):
                yield ProgressBarWidget(id="progress-bar")
                yield ContextDisplayWidget(id="context-display")

            # Left panel - model pairs and stats
            with Container(id="left-panel"):
                with TabbedContent():
                    with TabPane("Model Pairs", id="tab-pairs"):
                        yield ModelPairsWidget(id="model-pairs")
                    with TabPane("Statistics", id="tab-stats"):
                        yield TimingStatsWidget(id="timing-stats")
                    with TabPane("Kappa", id="tab-kappa"):
                        yield KappaDisplayWidget(id="kappa-display")

            # Right panel - costs
            with Container(id="right-panel"):
                yield CostTrackerWidget(
                    budget=self.config.budget_usd,
                    id="cost-tracker",
                    classes="widget-box"
                )
                yield CostBreakdownWidget(id="cost-breakdown", classes="widget-box")

        # Log panel (hidden by default)
        with Container(id="log-container"):
            yield LogPanelWidget(id="log-panel")

        yield Footer()

    async def on_mount(self) -> None:
        """Start evaluation when app mounts."""
        # Set up progress callback
        self.engine.progress_callback = self._handle_progress

        # Start evaluation in background
        self._eval_task = asyncio.create_task(self._run_evaluation())

    async def _run_evaluation(self) -> None:
        """Run the evaluation."""
        try:
            from ..prompts.generator import PromptGenerator
            generator = PromptGenerator(self.config)
            prompts = generator.generate(self.config.num_prompts)
            self.results = await self.engine.run_evaluation(
                prompts,
                self.config.batch_size
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log_message(f"Error: {e}", level="error")

    def _handle_progress(self, update: ProgressUpdate) -> None:
        """Handle progress updates from engine."""
        # Update progress bar
        self.query_one("#progress-bar", ProgressBarWidget).update_progress(
            completed=update.completed_prompts,
            total=update.total_prompts,
            phase=update.phase.value,
            eta_seconds=update.eta_seconds
        )

        # Update context display
        self.query_one("#context-display", ContextDisplayWidget).update_context(
            prompt_id=update.current_prompt_id,
            occupation=update.current_occupation,
            occupation_code=update.current_occupation_code,
            industry=update.current_industry,
            industry_code=update.current_industry_code
        )

        # Update model pairs
        self.query_one("#model-pairs", ModelPairsWidget).update_pairs(
            update.model_pair_progress
        )

        # Update costs
        self.query_one("#cost-tracker", CostTrackerWidget).update_costs(
            spent=update.cost_spent,
            projected=update.cost_projected
        )

        # Update timing stats
        self.query_one("#timing-stats", TimingStatsWidget).update_stats(
            response_times=update.response_times_ms,
            avg_time=update.avg_response_time_ms,
            throughput=update.api_throughput,
            errors=update.errors,
            retries=update.retries,
            rate_limits=update.rate_limit_pauses
        )

        # Update kappa display
        self.query_one("#kappa-display", KappaDisplayWidget).update_kappa(
            fleiss_kappa=update.fleiss_kappa,
            pairwise_kappa=update.kappa_scores,
            per_judge_votes=update.per_judge_votes
        )

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        if self.is_paused:
            self.engine.resume()
            self.is_paused = False
            self.log_message("Resumed evaluation")
        else:
            self.engine.pause()
            self.is_paused = True
            self.log_message("Paused evaluation")

    def action_save_checkpoint(self) -> None:
        """Save checkpoint."""
        asyncio.create_task(self._save_checkpoint())

    async def _save_checkpoint(self) -> None:
        """Actually save the checkpoint."""
        await self.engine.checkpoint_manager.save()
        self.log_message("Checkpoint saved")

    def action_cancel(self) -> None:
        """Cancel evaluation."""
        self.engine.request_shutdown()
        self.log_message("Cancellation requested...")

    def action_toggle_log(self) -> None:
        """Toggle log panel visibility."""
        self.show_log = not self.show_log
        log_container = self.query_one("#log-container")
        if self.show_log:
            log_container.add_class("visible")
        else:
            log_container.remove_class("visible")

    def action_toggle_detail(self) -> None:
        """Toggle detailed view."""
        pass  # Implement as needed

    def action_refresh(self) -> None:
        """Force refresh display."""
        self.refresh()

    def action_tab_1(self) -> None:
        """Switch to tab 1."""
        self.query_one(TabbedContent).active = "tab-pairs"

    def action_tab_2(self) -> None:
        """Switch to tab 2."""
        self.query_one(TabbedContent).active = "tab-stats"

    def action_tab_3(self) -> None:
        """Switch to tab 3."""
        self.query_one(TabbedContent).active = "tab-kappa"

    def log_message(self, message: str, level: str = "info") -> None:
        """Add message to log panel."""
        self.query_one("#log-panel", LogPanelWidget).add_message(message, level)


# Widget implementations
class ProgressBarWidget(Static):
    """Progress bar with ETA display."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._completed = 0
        self._total = 0
        self._phase = "initializing"
        self._eta = None

    def update_progress(
        self,
        completed: int,
        total: int,
        phase: str,
        eta_seconds: Optional[float]
    ) -> None:
        self._completed = completed
        self._total = total
        self._phase = phase
        self._eta = eta_seconds
        self._render()

    def _render(self) -> None:
        from rich.progress import BarColumn, Progress, TextColumn
        from rich.table import Table

        pct = (self._completed / self._total * 100) if self._total > 0 else 0
        bar_width = 40
        filled = int(pct / 100 * bar_width)

        bar = f"[green]{'█' * filled}[/][dim]{'░' * (bar_width - filled)}[/]"

        eta_str = ""
        if self._eta:
            mins = int(self._eta // 60)
            secs = int(self._eta % 60)
            eta_str = f" | ETA: {mins}m {secs}s"

        self.update(
            f"[bold]{self._phase.upper()}[/] {bar} "
            f"{self._completed}/{self._total} ({pct:.1f}%){eta_str}"
        )


class ContextDisplayWidget(Static):
    """Display current prompt context (occupation, industry)."""

    def update_context(
        self,
        prompt_id: Optional[str],
        occupation: Optional[str],
        occupation_code: Optional[str],
        industry: Optional[str],
        industry_code: Optional[str]
    ) -> None:
        parts = []
        if occupation:
            code_str = f" ({occupation_code})" if occupation_code else ""
            parts.append(f"[cyan]Occupation:[/] {occupation}{code_str}")
        if industry:
            code_str = f" ({industry_code})" if industry_code else ""
            parts.append(f"[yellow]Industry:[/] {industry}{code_str}")
        if prompt_id:
            parts.append(f"[dim]ID: {prompt_id}[/]")

        self.update(" | ".join(parts) if parts else "[dim]Initializing...[/]")


class ModelPairsWidget(Static):
    """Display model pair results with win rates and CIs."""

    def update_pairs(self, pair_progress: dict) -> None:
        from rich.table import Table

        table = Table(title="Model Comparisons", box=None)
        table.add_column("Pair", style="cyan")
        table.add_column("Done", justify="right")
        table.add_column("Win Rate", justify="right")
        table.add_column("95% CI", justify="right")

        for pair_key, (done, total, win_rate, ci_low, ci_high) in pair_progress.items():
            # Format pair name
            parts = pair_key.split("_vs_")
            gemini = parts[0].split("/")[-1][:12] if len(parts) > 0 else "?"
            competitor = parts[1].split("/")[-1][:12] if len(parts) > 1 else "?"
            pair_name = f"{gemini} vs {competitor}"

            # Color based on win rate
            if win_rate > 0.55:
                wr_style = "green"
            elif win_rate < 0.45:
                wr_style = "red"
            else:
                wr_style = "yellow"

            table.add_row(
                pair_name,
                f"{done}/{total}",
                f"[{wr_style}]{win_rate*100:.1f}%[/]",
                f"({ci_low*100:.1f}%-{ci_high*100:.1f}%)"
            )

        self.update(table)


class KappaDisplayWidget(Static):
    """Display inter-judge agreement metrics."""

    def update_kappa(
        self,
        fleiss_kappa: Optional[float],
        pairwise_kappa: dict,
        per_judge_votes: dict
    ) -> None:
        from rich.table import Table
        from rich.panel import Panel

        content = Table.grid(padding=(0, 1))

        # Fleiss' Kappa
        if fleiss_kappa is not None:
            interpretation = self._interpret_kappa(fleiss_kappa)
            color = self._kappa_color(fleiss_kappa)
            content.add_row(
                "Fleiss' Kappa (all judges):",
                f"[{color}]{fleiss_kappa:.3f}[/] ({interpretation})"
            )
        else:
            content.add_row("Fleiss' Kappa:", "[dim]Calculating...[/]")

        # Pairwise
        if pairwise_kappa:
            content.add_row("", "")
            content.add_row("[bold]Pairwise Cohen's Kappa:[/]", "")
            for pair, kappa in sorted(pairwise_kappa.items()):
                color = self._kappa_color(kappa)
                content.add_row(f"  {pair}:", f"[{color}]{kappa:.3f}[/]")

        # Per-judge vote distribution
        if per_judge_votes:
            content.add_row("", "")
            content.add_row("[bold]Judge Vote Distribution:[/]", "")
            for judge, votes in per_judge_votes.items():
                short_judge = judge.split("/")[-1][:15]
                total = sum(votes.values())
                if total > 0:
                    gemini_pct = votes.get("gemini", 0) / total * 100
                    comp_pct = votes.get("competitor", 0) / total * 100
                    tie_pct = votes.get("tie", 0) / total * 100
                    content.add_row(
                        f"  {short_judge}:",
                        f"G:{gemini_pct:.0f}% C:{comp_pct:.0f}% T:{tie_pct:.0f}%"
                    )

        self.update(Panel(content, title="Inter-Judge Agreement", border_style="blue"))

    def _interpret_kappa(self, kappa: float) -> str:
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
            return "almost perfect"

    def _kappa_color(self, kappa: float) -> str:
        if kappa < 0.40:
            return "red"
        elif kappa < 0.60:
            return "yellow"
        else:
            return "green"


class TimingStatsWidget(Static):
    """Display timing and performance statistics."""

    def update_stats(
        self,
        response_times: list,
        avg_time: float,
        throughput: float,
        errors: int,
        retries: int,
        rate_limits: int
    ) -> None:
        from rich.table import Table

        table = Table(box=None, show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Avg Response Time:", f"{avg_time:.0f}ms")
        table.add_row("Throughput:", f"{throughput:.1f} calls/min")
        table.add_row("", "")
        table.add_row("Errors:", f"[red]{errors}[/]" if errors > 0 else "0")
        table.add_row("Retries:", f"[yellow]{retries}[/]" if retries > 0 else "0")
        table.add_row("Rate Limits:", f"[yellow]{rate_limits}[/]" if rate_limits > 0 else "0")

        # Mini histogram of response times
        if response_times:
            table.add_row("", "")
            table.add_row("[bold]Response Time Distribution:[/]", "")
            hist = self._make_histogram(response_times)
            table.add_row("", hist)

        self.update(table)

    def _make_histogram(self, times: list, bins: int = 5) -> str:
        if not times:
            return ""

        min_t, max_t = min(times), max(times)
        if min_t == max_t:
            return f"[dim]All: {min_t:.0f}ms[/]"

        bin_width = (max_t - min_t) / bins
        counts = [0] * bins

        for t in times:
            idx = min(int((t - min_t) / bin_width), bins - 1)
            counts[idx] += 1

        max_count = max(counts) if counts else 1
        bars = []
        for c in counts:
            height = int(c / max_count * 5)
            bars.append("▁▂▃▄▅▆▇█"[height] if height > 0 else "▁")

        return f"[green]{''.join(bars)}[/] ({min_t:.0f}-{max_t:.0f}ms)"


class LogPanelWidget(Static):
    """Log message display panel."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages = []
        self._max_messages = 100

    def add_message(self, message: str, level: str = "info") -> None:
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = {"info": "white", "warning": "yellow", "error": "red"}.get(level, "white")

        formatted = f"[dim]{timestamp}[/] [{color}]{message}[/]"
        self._messages.append(formatted)

        if len(self._messages) > self._max_messages:
            self._messages.pop(0)

        self.update("\n".join(self._messages[-20:]))
```

---

## 7. Name Formality Variation

Complete name generator with formality levels:

```python
# src/data/name_generator.py

import random
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import IntEnum


class FormalityLevel(IntEnum):
    """Formality levels for name presentation."""
    VERY_INFORMAL = 1  # "Mike"
    INFORMAL = 2       # "Mike Johnson"
    NEUTRAL = 3        # "Michael Johnson"
    FORMAL = 4         # "Mr. Johnson" or "Michael R. Johnson"
    VERY_FORMAL = 5    # "Mr. Michael R. Johnson, CPA"


@dataclass
class GeneratedName:
    """A generated name with all components."""
    first_name: str
    last_name: str
    middle_initial: Optional[str] = None
    nickname: Optional[str] = None
    prefix: Optional[str] = None  # Mr., Ms., Dr., etc.
    suffix: Optional[str] = None  # Jr., III, CPA, PhD, etc.
    gender: Optional[str] = None

    def format(self, formality: FormalityLevel) -> str:
        """Format name according to formality level."""
        if formality == FormalityLevel.VERY_INFORMAL:
            # Use nickname or shortened first name
            return self.nickname or self._shorten(self.first_name)

        elif formality == FormalityLevel.INFORMAL:
            # First Last
            name = self.nickname or self.first_name
            return f"{name} {self.last_name}"

        elif formality == FormalityLevel.NEUTRAL:
            # Full First Last
            return f"{self.first_name} {self.last_name}"

        elif formality == FormalityLevel.FORMAL:
            # Prefix + Last OR Full name with middle initial
            if self.prefix and random.random() < 0.5:
                return f"{self.prefix} {self.last_name}"
            else:
                middle = f" {self.middle_initial}." if self.middle_initial else ""
                return f"{self.first_name}{middle} {self.last_name}"

        else:  # VERY_FORMAL
            # Full formal with prefix and suffix
            parts = []
            if self.prefix:
                parts.append(self.prefix)
            parts.append(self.first_name)
            if self.middle_initial:
                parts.append(f"{self.middle_initial}.")
            parts.append(self.last_name)
            if self.suffix:
                parts.append(f", {self.suffix}")
            return " ".join(parts)

    def _shorten(self, name: str) -> str:
        """Get shortened/nickname version of a name."""
        shortcuts = {
            "Michael": "Mike", "William": "Will", "Robert": "Rob",
            "Elizabeth": "Liz", "Jennifer": "Jen", "Katherine": "Kate",
            "Christopher": "Chris", "Jonathan": "Jon", "Benjamin": "Ben",
            "Alexandra": "Alex", "Samantha": "Sam", "Nicholas": "Nick",
            "Timothy": "Tim", "Anthony": "Tony", "Patricia": "Pat",
            "Rebecca": "Becca", "Matthew": "Matt", "Theodore": "Ted",
            "Richard": "Rich", "Stephen": "Steve", "Daniel": "Dan",
        }
        return shortcuts.get(name, name)


class NameGenerator:
    """Generate realistic names with demographic variation."""

    # Name pools by perceived ethnicity/origin for diversity
    FIRST_NAMES = {
        "male": {
            "common": ["James", "Michael", "Robert", "David", "William", "John",
                      "Christopher", "Daniel", "Matthew", "Anthony"],
            "modern": ["Liam", "Noah", "Ethan", "Mason", "Lucas", "Oliver",
                      "Aiden", "Elijah", "Logan", "Alexander"],
            "traditional": ["Charles", "Edward", "George", "Henry", "Thomas",
                           "Richard", "Joseph", "Benjamin", "Theodore", "Arthur"],
            "hispanic": ["Carlos", "Miguel", "Jose", "Juan", "Luis", "Diego",
                        "Antonio", "Francisco", "Rafael", "Alejandro"],
            "asian": ["Kevin", "Brian", "Eric", "Steven", "Andrew", "Jason",
                     "Ryan", "Justin", "Brandon", "Jonathan"],
        },
        "female": {
            "common": ["Mary", "Jennifer", "Linda", "Elizabeth", "Susan",
                      "Margaret", "Jessica", "Sarah", "Karen", "Nancy"],
            "modern": ["Emma", "Olivia", "Ava", "Sophia", "Isabella", "Mia",
                      "Charlotte", "Amelia", "Harper", "Evelyn"],
            "traditional": ["Catherine", "Margaret", "Eleanor", "Victoria",
                           "Caroline", "Beatrice", "Dorothy", "Frances"],
            "hispanic": ["Maria", "Ana", "Carmen", "Rosa", "Elena", "Lucia",
                        "Sofia", "Isabella", "Valentina", "Gabriela"],
            "asian": ["Michelle", "Christine", "Lisa", "Amy", "Jennifer",
                     "Karen", "Grace", "Emily", "Stephanie", "Angela"],
        }
    }

    LAST_NAMES = {
        "common": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Rodriguez", "Martinez"],
        "anglo": ["Anderson", "Thompson", "White", "Harris", "Clark", "Lewis",
                 "Robinson", "Walker", "Hall", "Young"],
        "germanic": ["Mueller", "Schmidt", "Schneider", "Fischer", "Weber",
                    "Meyer", "Wagner", "Becker", "Schulz", "Hoffmann"],
        "hispanic": ["Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez",
                    "Ramirez", "Torres", "Flores", "Rivera", "Gomez"],
        "asian": ["Kim", "Lee", "Park", "Chen", "Wang", "Liu", "Zhang",
                 "Huang", "Lin", "Wu", "Nguyen", "Tran", "Patel", "Shah"],
        "other": ["O'Brien", "O'Connor", "Murphy", "Kelly", "Sullivan",
                 "Cohen", "Shapiro", "Rosenberg", "Kowalski", "Novak"],
    }

    MIDDLE_INITIALS = list("ABCDEFGHJKLMNPRSTW")

    PREFIXES = {
        "male": ["Mr."],
        "female": ["Ms.", "Mrs."],
        "neutral": ["Dr.", "Prof."],
    }

    PROFESSIONAL_SUFFIXES = [
        "CPA", "MBA", "PhD", "JD", "MD", "PE", "PMP", "SHRM-CP",
        "CISSP", "CFP", "CFA", "SPHR", "Esq."
    ]

    GENERATIONAL_SUFFIXES = ["Jr.", "Sr.", "II", "III", "IV"]

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate(
        self,
        gender: Optional[str] = None,
        include_middle: bool = True,
        include_prefix: bool = False,
        include_suffix: bool = False,
        professional_context: bool = False,
        age_group: Optional[str] = None,  # "young", "middle", "senior"
    ) -> GeneratedName:
        """Generate a name with optional components."""

        # Determine gender if not specified
        if gender is None:
            gender = self.rng.choice(["male", "female"])

        # Select name style based on age
        if age_group == "young":
            first_pool = "modern"
        elif age_group == "senior":
            first_pool = "traditional"
        else:
            first_pool = self.rng.choice(["common", "modern", "traditional"])

        # Add some diversity
        if self.rng.random() < 0.2:
            first_pool = self.rng.choice(["hispanic", "asian"])

        first_name = self.rng.choice(self.FIRST_NAMES[gender][first_pool])

        # Last name with diversity
        last_pool = self.rng.choices(
            ["common", "anglo", "germanic", "hispanic", "asian", "other"],
            weights=[30, 20, 10, 20, 15, 5]
        )[0]
        last_name = self.rng.choice(self.LAST_NAMES[last_pool])

        # Optional components
        middle_initial = None
        if include_middle and self.rng.random() < 0.7:
            middle_initial = self.rng.choice(self.MIDDLE_INITIALS)

        prefix = None
        if include_prefix:
            if professional_context and self.rng.random() < 0.3:
                prefix = self.rng.choice(self.PREFIXES["neutral"])
            else:
                prefix = self.rng.choice(self.PREFIXES[gender])

        suffix = None
        if include_suffix:
            if professional_context and self.rng.random() < 0.4:
                suffix = self.rng.choice(self.PROFESSIONAL_SUFFIXES)
            elif self.rng.random() < 0.1:
                suffix = self.rng.choice(self.GENERATIONAL_SUFFIXES)

        # Determine nickname
        nickname = None
        common_nicknames = {
            "Michael": "Mike", "William": "Will", "Robert": "Rob",
            "Elizabeth": "Liz", "Jennifer": "Jen", "Katherine": "Kate",
        }
        if first_name in common_nicknames:
            nickname = common_nicknames[first_name]

        return GeneratedName(
            first_name=first_name,
            last_name=last_name,
            middle_initial=middle_initial,
            nickname=nickname,
            prefix=prefix,
            suffix=suffix,
            gender=gender
        )

    def generate_for_formality(
        self,
        formality: FormalityLevel,
        **kwargs
    ) -> Tuple[GeneratedName, str]:
        """Generate a name and format it for the given formality level."""

        # Adjust generation based on formality
        include_prefix = formality >= FormalityLevel.FORMAL
        include_suffix = formality == FormalityLevel.VERY_FORMAL
        include_middle = formality >= FormalityLevel.FORMAL

        name = self.generate(
            include_middle=include_middle,
            include_prefix=include_prefix,
            include_suffix=include_suffix,
            **kwargs
        )

        formatted = name.format(formality)
        return name, formatted


# Usage example:
# generator = NameGenerator(seed=42)
# name, formatted = generator.generate_for_formality(FormalityLevel.FORMAL)
# print(formatted)  # "Mr. Johnson" or "Michael R. Johnson"
```

---

## 8. Ambiguity Behavior Tracking

Complete implementation for tracking how models handle ambiguous prompts:

```python
# src/eval/ambiguity_tracker.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import defaultdict
import re


class AmbiguityType(str, Enum):
    """Types of ambiguity in prompts."""
    MISSING_CONTEXT = "missing_context"  # Missing key details
    UNCLEAR_AUDIENCE = "unclear_audience"  # Who is the recipient
    CONFLICTING_GOALS = "conflicting_goals"  # Multiple objectives
    VAGUE_TONE = "vague_tone"  # Unclear formality/tone
    UNDEFINED_SCOPE = "undefined_scope"  # How detailed/comprehensive
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"  # Deadline, timing unclear


class AmbiguityResponse(str, Enum):
    """How a model responded to ambiguity."""
    CLARIFIED = "clarified"  # Asked for clarification
    ASSUMED = "assumed"  # Made assumptions and stated them
    IGNORED = "ignored"  # Proceeded without addressing
    PARTIAL = "partial"  # Partially addressed ambiguity
    REFUSED = "refused"  # Refused due to ambiguity


@dataclass
class AmbiguityAnalysis:
    """Analysis of how a model handled ambiguity."""
    prompt_id: str
    model: str
    ambiguity_type: AmbiguityType
    response_behavior: AmbiguityResponse
    assumptions_stated: List[str] = field(default_factory=list)
    clarification_requested: bool = False
    confidence_expressed: Optional[str] = None
    raw_signals: Dict[str, any] = field(default_factory=dict)


class AmbiguityTracker:
    """Track and analyze how models handle ambiguous prompts."""

    # Patterns that suggest clarification requests
    CLARIFICATION_PATTERNS = [
        r"(?:could you|can you|would you).{0,20}(?:clarify|specify|provide|tell me)",
        r"(?:i need|i would need|i require).{0,30}(?:more information|details|context)",
        r"(?:what|which|who|when|where|how).{0,20}(?:specifically|exactly|precisely)",
        r"(?:before i|to better|in order to).{0,30}(?:proceed|help|assist)",
        r"(?:please|kindly).{0,20}(?:clarify|specify|confirm|let me know)",
    ]

    # Patterns suggesting assumptions were made
    ASSUMPTION_PATTERNS = [
        r"(?:i(?:'ll| will)? assume|assuming|i(?:'m| am) assuming)",
        r"(?:based on|given that|since you|as you)",
        r"(?:i(?:'ll| will) proceed with|proceeding with the assumption)",
        r"(?:unless.{0,30}otherwise|if.{0,30}different)",
        r"(?:taking this to mean|interpreting this as)",
    ]

    # Hedging language suggesting uncertainty
    HEDGE_PATTERNS = [
        r"(?:might|may|could|possibly|perhaps|potentially)",
        r"(?:it seems|it appears|it looks like)",
        r"(?:i think|i believe|i suspect|in my view)",
        r"(?:not entirely clear|somewhat unclear|bit ambiguous)",
    ]

    def __init__(self):
        self._analyses: Dict[str, List[AmbiguityAnalysis]] = defaultdict(list)
        self._model_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def analyze_response(
        self,
        prompt_id: str,
        model: str,
        ambiguity_type: str,
        response_text: str,
        original_prompt: str
    ) -> AmbiguityAnalysis:
        """Analyze how a model's response handled ambiguity."""

        response_lower = response_text.lower()

        # Check for clarification requests
        clarification_requested = any(
            re.search(pattern, response_lower)
            for pattern in self.CLARIFICATION_PATTERNS
        )

        # Check for stated assumptions
        assumptions = self._extract_assumptions(response_text)

        # Check for hedging
        hedge_count = sum(
            1 for pattern in self.HEDGE_PATTERNS
            if re.search(pattern, response_lower)
        )

        # Determine response behavior
        if clarification_requested:
            behavior = AmbiguityResponse.CLARIFIED
        elif len(assumptions) >= 2:
            behavior = AmbiguityResponse.ASSUMED
        elif len(assumptions) >= 1 or hedge_count >= 2:
            behavior = AmbiguityResponse.PARTIAL
        elif len(response_text) < 100:  # Very short response might be refusal
            behavior = AmbiguityResponse.REFUSED
        else:
            behavior = AmbiguityResponse.IGNORED

        # Confidence expression
        confidence = self._assess_confidence(response_text)

        analysis = AmbiguityAnalysis(
            prompt_id=prompt_id,
            model=model,
            ambiguity_type=AmbiguityType(ambiguity_type) if isinstance(ambiguity_type, str) else ambiguity_type,
            response_behavior=behavior,
            assumptions_stated=assumptions,
            clarification_requested=clarification_requested,
            confidence_expressed=confidence,
            raw_signals={
                "hedge_count": hedge_count,
                "response_length": len(response_text),
                "has_questions": "?" in response_text,
            }
        )

        # Store for aggregation
        self._analyses[model].append(analysis)
        self._model_stats[model][behavior.value] += 1

        return analysis

    def _extract_assumptions(self, text: str) -> List[str]:
        """Extract stated assumptions from response text."""
        assumptions = []
        lines = text.split("\n")

        for line in lines:
            line_lower = line.lower()
            for pattern in self.ASSUMPTION_PATTERNS:
                if re.search(pattern, line_lower):
                    # Clean up the assumption
                    clean = line.strip()
                    if len(clean) > 20:
                        assumptions.append(clean[:200])
                    break

        return assumptions

    def _assess_confidence(self, text: str) -> Optional[str]:
        """Assess expressed confidence level."""
        text_lower = text.lower()

        high_confidence = [
            "clearly", "certainly", "definitely", "absolutely",
            "without doubt", "i'm confident"
        ]
        low_confidence = [
            "not sure", "uncertain", "unclear", "unsure",
            "hard to say", "difficult to determine"
        ]

        high_count = sum(1 for word in high_confidence if word in text_lower)
        low_count = sum(1 for word in low_confidence if word in text_lower)

        if high_count > low_count:
            return "high"
        elif low_count > high_count:
            return "low"
        else:
            return "neutral"

    def get_model_summary(self, model: str) -> Dict[str, any]:
        """Get summary statistics for a model's ambiguity handling."""
        analyses = self._analyses.get(model, [])

        if not analyses:
            return {"total": 0, "behaviors": {}, "by_type": {}}

        behavior_counts = defaultdict(int)
        type_behavior = defaultdict(lambda: defaultdict(int))

        for a in analyses:
            behavior_counts[a.response_behavior.value] += 1
            type_behavior[a.ambiguity_type.value][a.response_behavior.value] += 1

        total = len(analyses)

        return {
            "total": total,
            "behaviors": {
                k: {"count": v, "pct": v / total * 100}
                for k, v in behavior_counts.items()
            },
            "by_type": dict(type_behavior),
            "clarification_rate": sum(
                1 for a in analyses if a.clarification_requested
            ) / total * 100,
            "assumption_rate": sum(
                1 for a in analyses if a.assumptions_stated
            ) / total * 100,
        }

    def get_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare ambiguity handling across models."""
        comparison = {}

        for model in self._analyses:
            summary = self.get_model_summary(model)
            behaviors = summary.get("behaviors", {})

            comparison[model] = {
                "clarification_rate": behaviors.get("clarified", {}).get("pct", 0),
                "assumption_rate": behaviors.get("assumed", {}).get("pct", 0),
                "ignore_rate": behaviors.get("ignored", {}).get("pct", 0),
                "total_analyzed": summary.get("total", 0),
            }

        return comparison

    def export_report(self) -> Dict[str, any]:
        """Export complete ambiguity analysis report."""
        return {
            "summary_by_model": {
                model: self.get_model_summary(model)
                for model in self._analyses
            },
            "comparison": self.get_comparison(),
            "detailed_analyses": {
                model: [
                    {
                        "prompt_id": a.prompt_id,
                        "ambiguity_type": a.ambiguity_type.value,
                        "behavior": a.response_behavior.value,
                        "clarified": a.clarification_requested,
                        "assumptions": a.assumptions_stated,
                        "confidence": a.confidence_expressed,
                    }
                    for a in analyses
                ]
                for model, analyses in self._analyses.items()
            }
        }
```

---

## 9. Refusal Tracking by Dimension

Complete refusal classifier and tracker:

```python
# src/eval/refusal_classifier.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
from collections import defaultdict
import re


class RefusalCategory(str, Enum):
    """Categories of refusal."""
    SAFETY = "safety"  # Safety/harm concerns
    CAPABILITY = "capability"  # Claims inability
    POLICY = "policy"  # Policy restrictions
    ETHICS = "ethics"  # Ethical concerns
    PRIVACY = "privacy"  # Privacy concerns
    LEGAL = "legal"  # Legal concerns
    INAPPROPRIATE = "inappropriate"  # Inappropriate request
    UNCLEAR = "unclear"  # Couldn't understand request
    PARTIAL = "partial"  # Partial refusal with caveats
    NONE = "none"  # Not a refusal


class RefusalDimension(str, Enum):
    """Dimensions for analyzing refusals."""
    TOPIC = "topic"  # Topic-related refusal
    CONTENT = "content"  # Content-related
    FORMAT = "format"  # Format-related
    PERSONA = "persona"  # Persona/role-related
    AUDIENCE = "audience"  # Audience-related


@dataclass
class RefusalAnalysis:
    """Detailed analysis of a refusal."""
    is_refusal: bool
    category: RefusalCategory
    dimensions: List[RefusalDimension] = field(default_factory=list)
    confidence: float = 0.0
    key_phrases: List[str] = field(default_factory=list)
    partial_completion: bool = False
    alternative_offered: bool = False


class RefusalClassifier:
    """Classify and analyze model refusals."""

    # Strong refusal indicators
    STRONG_REFUSAL_PATTERNS = [
        r"i (?:cannot|can't|won't|will not|am unable to|am not able to)",
        r"i(?:'m| am) (?:sorry|afraid).{0,30}(?:cannot|can't|unable|not able)",
        r"(?:this|that) (?:is|would be).{0,20}(?:inappropriate|unethical|harmful)",
        r"(?:against|violates?).{0,20}(?:my|our|the).{0,20}(?:guidelines|policies|principles)",
        r"i (?:must|need to) (?:decline|refuse|refrain)",
    ]

    # Soft refusal indicators
    SOFT_REFUSAL_PATTERNS = [
        r"i(?:'d| would) (?:prefer|rather|suggest).{0,30}(?:not|instead)",
        r"(?:not|don't) feel comfortable",
        r"(?:hesitant|reluctant) to",
        r"(?:may|might|could) not be (?:appropriate|suitable|advisable)",
        r"let me (?:offer|suggest|provide).{0,20}(?:alternative|different)",
    ]

    # Category-specific patterns
    CATEGORY_PATTERNS = {
        RefusalCategory.SAFETY: [
            r"(?:harm|harmful|dangerous|unsafe|risk)",
            r"(?:safety|security).{0,20}concern",
            r"(?:could|might|may).{0,20}(?:harm|hurt|damage)",
        ],
        RefusalCategory.POLICY: [
            r"(?:policy|policies|guidelines|terms)",
            r"(?:against|violate).{0,20}(?:rules|guidelines)",
            r"(?:not allowed|prohibited|restricted)",
        ],
        RefusalCategory.ETHICS: [
            r"(?:ethical|ethics|morally|moral)",
            r"(?:integrity|principle|value)",
            r"(?:responsible|responsibility)",
        ],
        RefusalCategory.PRIVACY: [
            r"(?:privacy|private|personal|confidential)",
            r"(?:data protection|information security)",
            r"(?:sensitive information|personal data)",
        ],
        RefusalCategory.LEGAL: [
            r"(?:legal|illegal|law|lawsuit)",
            r"(?:copyright|trademark|intellectual property)",
            r"(?:liability|compliance|regulation)",
        ],
        RefusalCategory.CAPABILITY: [
            r"(?:don't have|lack|without).{0,20}(?:ability|capability|access)",
            r"(?:beyond|outside).{0,20}(?:my|capability)",
            r"(?:not designed|wasn't trained) to",
        ],
        RefusalCategory.INAPPROPRIATE: [
            r"(?:inappropriate|unsuitable|improper)",
            r"(?:offensive|objectionable|problematic)",
            r"(?:not appropriate|wouldn't be right)",
        ],
        RefusalCategory.UNCLEAR: [
            r"(?:don't understand|unclear|confusing)",
            r"(?:need more|require additional).{0,20}(?:information|context|detail)",
            r"(?:could you|please).{0,20}(?:clarify|explain|rephrase)",
        ],
    }

    # Dimension patterns
    DIMENSION_PATTERNS = {
        RefusalDimension.TOPIC: [
            r"(?:this topic|subject matter|the topic)",
            r"(?:discuss|write about|address).{0,20}(?:this|such)",
        ],
        RefusalDimension.CONTENT: [
            r"(?:this content|the content|such content)",
            r"(?:generate|create|produce|write).{0,20}(?:this|such|that)",
        ],
        RefusalDimension.FORMAT: [
            r"(?:in this format|this way|like this)",
            r"(?:format|style|structure)",
        ],
        RefusalDimension.PERSONA: [
            r"(?:as|pretend|role|character)",
            r"(?:persona|identity|acting as)",
        ],
        RefusalDimension.AUDIENCE: [
            r"(?:for this audience|to this recipient)",
            r"(?:recipient|audience|reader)",
        ],
    }

    # Alternative offer patterns
    ALTERNATIVE_PATTERNS = [
        r"(?:instead|alternatively|however).{0,30}(?:can|could|would|may)",
        r"(?:offer|suggest|provide|give).{0,20}(?:alternative|different|another)",
        r"(?:happy|glad|willing) to.{0,30}(?:help|assist).{0,30}(?:with|by)",
        r"what i (?:can|could) do.{0,20}(?:instead|is)",
    ]

    def classify(self, response_text: str) -> Optional[str]:
        """Quick classification - returns category string or None."""
        analysis = self.analyze(response_text)
        if analysis.is_refusal:
            return analysis.category.value
        return None

    def analyze(self, response_text: str) -> RefusalAnalysis:
        """Full refusal analysis."""
        text_lower = response_text.lower()

        # Check for strong refusal
        strong_matches = []
        for pattern in self.STRONG_REFUSAL_PATTERNS:
            matches = re.findall(pattern, text_lower)
            strong_matches.extend(matches)

        # Check for soft refusal
        soft_matches = []
        for pattern in self.SOFT_REFUSAL_PATTERNS:
            matches = re.findall(pattern, text_lower)
            soft_matches.extend(matches)

        # Determine if it's a refusal
        is_refusal = len(strong_matches) > 0 or len(soft_matches) >= 2
        is_partial = len(soft_matches) > 0 and len(strong_matches) == 0

        if not is_refusal and not is_partial:
            return RefusalAnalysis(
                is_refusal=False,
                category=RefusalCategory.NONE,
                confidence=0.9
            )

        # Determine category
        category_scores = {}
        for category, patterns in self.CATEGORY_PATTERNS.items():
            score = sum(
                1 for p in patterns
                if re.search(p, text_lower)
            )
            if score > 0:
                category_scores[category] = score

        if category_scores:
            category = max(category_scores, key=category_scores.get)
        else:
            category = RefusalCategory.PARTIAL if is_partial else RefusalCategory.SAFETY

        # Determine dimensions
        dimensions = []
        for dimension, patterns in self.DIMENSION_PATTERNS.items():
            if any(re.search(p, text_lower) for p in patterns):
                dimensions.append(dimension)

        # Check for alternatives
        alternative_offered = any(
            re.search(p, text_lower)
            for p in self.ALTERNATIVE_PATTERNS
        )

        # Calculate confidence
        confidence = min(0.95, 0.5 + len(strong_matches) * 0.2 + len(soft_matches) * 0.1)

        # Collect key phrases
        key_phrases = strong_matches + soft_matches
        key_phrases = [p.strip() for p in key_phrases[:5]]

        return RefusalAnalysis(
            is_refusal=is_refusal or is_partial,
            category=RefusalCategory.PARTIAL if is_partial else category,
            dimensions=dimensions,
            confidence=confidence,
            key_phrases=key_phrases,
            partial_completion=is_partial,
            alternative_offered=alternative_offered
        )


class RefusalTracker:
    """Track refusals across models and dimensions."""

    def __init__(self):
        self.classifier = RefusalClassifier()
        self._refusals: Dict[str, List[RefusalAnalysis]] = defaultdict(list)
        self._prompt_refusals: Dict[str, Dict[str, RefusalAnalysis]] = defaultdict(dict)

    def track(
        self,
        prompt_id: str,
        model: str,
        response_text: str,
        prompt_metadata: Optional[Dict] = None
    ) -> RefusalAnalysis:
        """Track a response for refusal."""
        analysis = self.classifier.analyze(response_text)

        if analysis.is_refusal:
            self._refusals[model].append(analysis)
            self._prompt_refusals[prompt_id][model] = analysis

        return analysis

    def get_model_stats(self, model: str) -> Dict[str, any]:
        """Get refusal statistics for a model."""
        refusals = self._refusals.get(model, [])

        if not refusals:
            return {"total": 0, "by_category": {}, "by_dimension": {}}

        category_counts = defaultdict(int)
        dimension_counts = defaultdict(int)

        for r in refusals:
            category_counts[r.category.value] += 1
            for d in r.dimensions:
                dimension_counts[d.value] += 1

        return {
            "total": len(refusals),
            "by_category": dict(category_counts),
            "by_dimension": dict(dimension_counts),
            "alternative_rate": sum(1 for r in refusals if r.alternative_offered) / len(refusals) * 100,
            "partial_rate": sum(1 for r in refusals if r.partial_completion) / len(refusals) * 100,
        }

    def get_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare refusal rates across models."""
        comparison = {}

        for model, refusals in self._refusals.items():
            stats = self.get_model_stats(model)
            comparison[model] = {
                "refusal_count": stats["total"],
                "safety_refusals": stats["by_category"].get("safety", 0),
                "policy_refusals": stats["by_category"].get("policy", 0),
                "capability_refusals": stats["by_category"].get("capability", 0),
                "alternative_rate": stats.get("alternative_rate", 0),
            }

        return comparison

    def get_prompts_with_refusals(self) -> List[Tuple[str, Dict[str, str]]]:
        """Get prompts that had refusals and which models refused."""
        results = []

        for prompt_id, model_refusals in self._prompt_refusals.items():
            refused_models = {
                model: analysis.category.value
                for model, analysis in model_refusals.items()
            }
            if refused_models:
                results.append((prompt_id, refused_models))

        return results

    def export_report(self) -> Dict[str, any]:
        """Export complete refusal tracking report."""
        return {
            "by_model": {
                model: self.get_model_stats(model)
                for model in self._refusals
            },
            "comparison": self.get_comparison(),
            "prompts_with_refusals": self.get_prompts_with_refusals(),
        }
```

---

## 10. Failure Summary Reports

Complete failure logging and reporting system:

```python
# src/reports/failure_report.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class FailureRecord:
    """Record of a single failure."""
    timestamp: datetime
    prompt_id: str
    model: str
    phase: str  # "generation", "judging", "analysis"
    error_type: str
    error_message: str
    retry_count: int
    recovered: bool
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureSummary:
    """Summary of failures for a category."""
    count: int
    examples: List[str]
    first_occurrence: datetime
    last_occurrence: datetime
    recovery_rate: float
    affected_prompts: int
    affected_models: List[str]


class FailureLogger:
    """Log and track failures during evaluation."""

    def __init__(
        self,
        output_dir: Path,
        max_examples_per_type: int = 10
    ):
        self.output_dir = Path(output_dir)
        self.max_examples = max_examples_per_type
        self._failures: List[FailureRecord] = []
        self._by_type: Dict[str, List[FailureRecord]] = defaultdict(list)
        self._by_model: Dict[str, List[FailureRecord]] = defaultdict(list)
        self._by_prompt: Dict[str, List[FailureRecord]] = defaultdict(list)
        self._by_phase: Dict[str, List[FailureRecord]] = defaultdict(list)

    def log_failure(
        self,
        prompt_id: str,
        model: str,
        error_type: str,
        error_message: str,
        phase: str = "generation",
        retry_count: int = 0,
        recovered: bool = False,
        context: Optional[Dict] = None
    ) -> FailureRecord:
        """Log a failure event."""
        record = FailureRecord(
            timestamp=datetime.now(),
            prompt_id=prompt_id,
            model=model,
            phase=phase,
            error_type=error_type,
            error_message=error_message,
            retry_count=retry_count,
            recovered=recovered,
            context=context or {}
        )

        self._failures.append(record)
        self._by_type[error_type].append(record)
        self._by_model[model].append(record)
        self._by_prompt[prompt_id].append(record)
        self._by_phase[phase].append(record)

        logger.warning(
            f"Failure logged: {error_type} for {model} on {prompt_id} "
            f"(retry={retry_count}, recovered={recovered})"
        )

        return record

    def get_summary_by_type(self) -> Dict[str, FailureSummary]:
        """Get failure summary grouped by error type."""
        summaries = {}

        for error_type, records in self._by_type.items():
            if not records:
                continue

            examples = [
                f"{r.model}: {r.error_message[:100]}"
                for r in records[:self.max_examples]
            ]

            affected_prompts = set(r.prompt_id for r in records)
            affected_models = list(set(r.model for r in records))
            recovered_count = sum(1 for r in records if r.recovered)

            summaries[error_type] = FailureSummary(
                count=len(records),
                examples=examples,
                first_occurrence=min(r.timestamp for r in records),
                last_occurrence=max(r.timestamp for r in records),
                recovery_rate=recovered_count / len(records) * 100 if records else 0,
                affected_prompts=len(affected_prompts),
                affected_models=affected_models
            )

        return summaries

    def get_summary_by_model(self) -> Dict[str, Dict[str, int]]:
        """Get failure counts by model and type."""
        summary = {}

        for model, records in self._by_model.items():
            type_counts = defaultdict(int)
            for r in records:
                type_counts[r.error_type] += 1

            summary[model] = {
                "total": len(records),
                "by_type": dict(type_counts),
                "recovery_rate": sum(1 for r in records if r.recovered) / len(records) * 100 if records else 0
            }

        return summary

    def get_problem_prompts(self, min_failures: int = 2) -> List[Dict[str, Any]]:
        """Get prompts with multiple failures."""
        problems = []

        for prompt_id, records in self._by_prompt.items():
            if len(records) >= min_failures:
                problems.append({
                    "prompt_id": prompt_id,
                    "failure_count": len(records),
                    "models_affected": list(set(r.model for r in records)),
                    "error_types": list(set(r.error_type for r in records)),
                    "all_recovered": all(r.recovered for r in records)
                })

        return sorted(problems, key=lambda x: -x["failure_count"])

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive failure report."""
        if not self._failures:
            return {"status": "no_failures", "total": 0}

        report = {
            "status": "failures_recorded",
            "generated_at": datetime.now().isoformat(),
            "total_failures": len(self._failures),
            "total_recovered": sum(1 for f in self._failures if f.recovered),
            "overall_recovery_rate": sum(1 for f in self._failures if f.recovered) / len(self._failures) * 100,

            "by_error_type": {
                k: {
                    "count": v.count,
                    "recovery_rate": v.recovery_rate,
                    "affected_prompts": v.affected_prompts,
                    "affected_models": v.affected_models,
                    "examples": v.examples
                }
                for k, v in self.get_summary_by_type().items()
            },

            "by_model": self.get_summary_by_model(),

            "by_phase": {
                phase: len(records)
                for phase, records in self._by_phase.items()
            },

            "problem_prompts": self.get_problem_prompts(),

            "timeline": self._get_timeline(),
        }

        # Save to file
        report_path = self.output_dir / "failure_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Failure report saved to {report_path}")

        return report

    def _get_timeline(self, bucket_minutes: int = 5) -> List[Dict[str, Any]]:
        """Get failure counts over time."""
        if not self._failures:
            return []

        # Bucket failures by time
        buckets = defaultdict(int)
        for f in self._failures:
            bucket_key = f.timestamp.replace(
                minute=(f.timestamp.minute // bucket_minutes) * bucket_minutes,
                second=0, microsecond=0
            )
            buckets[bucket_key] += 1

        return [
            {"time": k.isoformat(), "count": v}
            for k, v in sorted(buckets.items())
        ]

    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        report = self.generate_report()

        if report["status"] == "no_failures":
            return "No failures recorded during evaluation."

        lines = [
            "=" * 60,
            "FAILURE SUMMARY REPORT",
            "=" * 60,
            f"Generated: {report['generated_at']}",
            f"Total Failures: {report['total_failures']}",
            f"Recovered: {report['total_recovered']} ({report['overall_recovery_rate']:.1f}%)",
            "",
            "-" * 40,
            "FAILURES BY ERROR TYPE",
            "-" * 40,
        ]

        for error_type, data in report["by_error_type"].items():
            lines.append(f"\n{error_type}:")
            lines.append(f"  Count: {data['count']}")
            lines.append(f"  Recovery Rate: {data['recovery_rate']:.1f}%")
            lines.append(f"  Affected Models: {', '.join(data['affected_models'])}")
            lines.append(f"  Example: {data['examples'][0] if data['examples'] else 'N/A'}")

        lines.extend([
            "",
            "-" * 40,
            "FAILURES BY MODEL",
            "-" * 40,
        ])

        for model, data in report["by_model"].items():
            short_model = model.split("/")[-1]
            lines.append(f"\n{short_model}:")
            lines.append(f"  Total: {data['total']}")
            lines.append(f"  Recovery Rate: {data['recovery_rate']:.1f}%")
            for error_type, count in data["by_type"].items():
                lines.append(f"    - {error_type}: {count}")

        if report["problem_prompts"]:
            lines.extend([
                "",
                "-" * 40,
                "PROBLEM PROMPTS (2+ failures)",
                "-" * 40,
            ])
            for p in report["problem_prompts"][:10]:
                lines.append(f"\n{p['prompt_id']}:")
                lines.append(f"  Failures: {p['failure_count']}")
                lines.append(f"  Models: {', '.join(p['models_affected'])}")

        return "\n".join(lines)
```

---

## 11. Updated Config Classes

Complete configuration classes with all options:

```python
# src/config/settings.py

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from enum import Enum


class OutputFormat(str, Enum):
    """Output format options."""
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    PDF = "pdf"


@dataclass
class JudgeConfig:
    """Configuration for judge panel."""
    models: List[str] = field(default_factory=lambda: [
        "openai/gpt-5.2",
        "anthropic/claude-opus-4.5",
        "google/gemini-3.0-pro"
    ])
    votes_per_judge: int = 3
    use_both_personas: bool = True
    persona_to_use: Optional[str] = None  # "writing_expert" or "recipient"
    temperature: float = 0.3
    max_tokens: int = 2000

    def __post_init__(self):
        if self.votes_per_judge < 1:
            raise ValueError("votes_per_judge must be at least 1")
        if self.votes_per_judge > 9:
            raise ValueError("votes_per_judge should not exceed 9")
        if self.persona_to_use and self.persona_to_use not in ["writing_expert", "recipient"]:
            raise ValueError("persona_to_use must be 'writing_expert' or 'recipient'")


@dataclass
class PromptConfig:
    """Configuration for prompt generation."""
    occupation_filter: Optional[str] = None  # O*NET code pattern
    industry_filter: Optional[str] = None  # NAICS code pattern
    task_type_filter: Optional[str] = None  # email, report, etc.
    formality_range: Tuple[int, int] = (1, 5)
    include_ambiguous: bool = True
    ambiguity_percentage: float = 0.1  # 10% ambiguous prompts
    seed: Optional[int] = None

    def __post_init__(self):
        if not (1 <= self.formality_range[0] <= self.formality_range[1] <= 5):
            raise ValueError("formality_range must be within 1-5")
        if not (0 <= self.ambiguity_percentage <= 1):
            raise ValueError("ambiguity_percentage must be 0-1")


@dataclass
class APIConfig:
    """Configuration for API access."""
    api_key: Optional[str] = None
    api_base: str = "https://openrouter.ai/api/v1"
    timeout_seconds: int = 120
    max_retries: int = 3
    base_retry_delay: float = 1.0
    max_concurrent_global: int = 30
    max_concurrent_per_model: int = 10

    def __post_init__(self):
        if not (10 <= self.max_concurrent_global <= 50):
            raise ValueError("max_concurrent_global must be 10-50")
        if self.timeout_seconds < 10:
            raise ValueError("timeout_seconds must be at least 10")


@dataclass
class StorageConfig:
    """Configuration for data storage."""
    output_dir: Path = Path("./results")
    output_format: OutputFormat = OutputFormat.JSON
    checkpoint_interval: int = 10
    database_path: Optional[Path] = None

    def __post_init__(self):
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if self.database_path is None:
            self.database_path = self.output_dir / "results.db"


@dataclass
class AnalysisConfig:
    """Configuration for analysis and reporting."""
    confidence_level: float = 0.95
    include_refusals: bool = True
    track_ambiguity: bool = True
    generate_pdf: bool = False
    include_per_judge_breakdown: bool = True
    include_response_times: bool = True

    def __post_init__(self):
        if not (0.5 <= self.confidence_level <= 0.99):
            raise ValueError("confidence_level must be 0.5-0.99")


@dataclass
class EvalConfig:
    """Complete evaluation configuration."""
    # Core settings
    num_prompts: int = 100
    model_pairs: List[Tuple[str, str]] = field(default_factory=lambda: [
        ("google/gemini-3.0-pro", "openai/gpt-5.2"),
        ("google/gemini-3.0-pro", "anthropic/claude-opus-4.5"),
        ("google/gemini-3.0-pro", "x-ai/grok-4.1"),
    ])
    batch_size: int = 10
    budget_usd: Optional[float] = None

    # Sub-configs
    judge_config: JudgeConfig = field(default_factory=JudgeConfig)
    prompt_config: PromptConfig = field(default_factory=PromptConfig)
    api_config: APIConfig = field(default_factory=APIConfig)
    storage_config: StorageConfig = field(default_factory=StorageConfig)
    analysis_config: AnalysisConfig = field(default_factory=AnalysisConfig)

    # Convenience aliases (for backward compatibility)
    @property
    def output_dir(self) -> Path:
        return self.storage_config.output_dir

    @property
    def output_format(self) -> str:
        return self.storage_config.output_format.value

    @property
    def checkpoint_interval(self) -> int:
        return self.storage_config.checkpoint_interval

    @property
    def max_concurrent_global(self) -> int:
        return self.api_config.max_concurrent_global

    @property
    def timeout_seconds(self) -> int:
        return self.api_config.timeout_seconds

    @property
    def max_retries(self) -> int:
        return self.api_config.max_retries

    @property
    def confidence_level(self) -> float:
        return self.analysis_config.confidence_level

    @property
    def include_refusals(self) -> bool:
        return self.analysis_config.include_refusals

    @property
    def occupation_filter(self) -> Optional[str]:
        return self.prompt_config.occupation_filter

    @property
    def industry_filter(self) -> Optional[str]:
        return self.prompt_config.industry_filter

    @property
    def task_type_filter(self) -> Optional[str]:
        return self.prompt_config.task_type_filter

    @property
    def formality_range(self) -> Tuple[int, int]:
        return self.prompt_config.formality_range

    def __post_init__(self):
        if self.num_prompts < 1:
            raise ValueError("num_prompts must be at least 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.budget_usd is not None and self.budget_usd <= 0:
            raise ValueError("budget_usd must be positive")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "num_prompts": self.num_prompts,
            "model_pairs": self.model_pairs,
            "batch_size": self.batch_size,
            "budget_usd": self.budget_usd,
            "judge_config": {
                "models": self.judge_config.models,
                "votes_per_judge": self.judge_config.votes_per_judge,
                "use_both_personas": self.judge_config.use_both_personas,
                "persona_to_use": self.judge_config.persona_to_use,
            },
            "prompt_config": {
                "occupation_filter": self.prompt_config.occupation_filter,
                "industry_filter": self.prompt_config.industry_filter,
                "formality_range": self.prompt_config.formality_range,
            },
            "api_config": {
                "timeout_seconds": self.api_config.timeout_seconds,
                "max_retries": self.api_config.max_retries,
                "max_concurrent_global": self.api_config.max_concurrent_global,
            },
            "storage_config": {
                "output_dir": str(self.storage_config.output_dir),
                "output_format": self.storage_config.output_format.value,
            },
            "analysis_config": {
                "confidence_level": self.analysis_config.confidence_level,
                "include_refusals": self.analysis_config.include_refusals,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalConfig":
        """Create from dictionary."""
        judge_data = data.get("judge_config", {})
        prompt_data = data.get("prompt_config", {})
        api_data = data.get("api_config", {})
        storage_data = data.get("storage_config", {})
        analysis_data = data.get("analysis_config", {})

        return cls(
            num_prompts=data.get("num_prompts", 100),
            model_pairs=data.get("model_pairs", []),
            batch_size=data.get("batch_size", 10),
            budget_usd=data.get("budget_usd"),
            judge_config=JudgeConfig(**judge_data) if judge_data else JudgeConfig(),
            prompt_config=PromptConfig(
                occupation_filter=prompt_data.get("occupation_filter"),
                industry_filter=prompt_data.get("industry_filter"),
                formality_range=tuple(prompt_data.get("formality_range", (1, 5))),
            ) if prompt_data else PromptConfig(),
            api_config=APIConfig(**api_data) if api_data else APIConfig(),
            storage_config=StorageConfig(
                output_dir=Path(storage_data.get("output_dir", "./results")),
                output_format=OutputFormat(storage_data.get("output_format", "json")),
            ) if storage_data else StorageConfig(),
            analysis_config=AnalysisConfig(**analysis_data) if analysis_data else AnalysisConfig(),
        )
```

---

## 12. Results Viewer

Complete TUI results viewer:

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, DataTable, TabbedContent, TabPane,
    Input, Button, Label
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.binding import Binding
from textual.screen import ModalScreen
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from ..storage.database import Database
from ..analysis.statistics import (
    wilson_confidence_interval,
    calculate_inter_judge_agreement
)


class ResultDetailScreen(ModalScreen):
    """Modal screen showing details of a single result."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    CSS = """
    ResultDetailScreen {
        align: center middle;
    }

    #detail-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    """

    def __init__(self, result_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.result_data = result_data

    def compose(self) -> ComposeResult:
        with Container(id="detail-container"):
            yield Static(self._build_detail_view(), id="detail-content")

    def _build_detail_view(self) -> Panel:
        """Build the detail view content."""
        r = self.result_data

        content = Table.grid(padding=(0, 2))

        # Header info
        content.add_row(
            f"[bold cyan]Prompt ID:[/]",
            f"{r.get('prompt_id', 'N/A')}"
        )
        content.add_row(
            f"[bold cyan]Model A:[/]",
            f"{r.get('model_a', 'N/A')}"
        )
        content.add_row(
            f"[bold cyan]Model B:[/]",
            f"{r.get('model_b', 'N/A')}"
        )
        content.add_row(
            f"[bold cyan]Winner:[/]",
            f"[green]{r.get('winner', 'N/A')}[/]"
        )
        content.add_row("", "")

        # Judge votes
        content.add_row("[bold]Judge Votes:[/]", "")
        judgments = r.get("judgments", [])
        for j in judgments:
            judge = j.get("judge_model", "unknown").split("/")[-1]
            vote = j.get("winner", "N/A")
            persona = j.get("persona", "N/A")
            content.add_row(
                f"  {judge} ({persona}):",
                f"{vote}"
            )

        content.add_row("", "")

        # Response previews
        content.add_row("[bold]Response A Preview:[/]", "")
        response_a = r.get("model_a_response", {}).get("content", "")[:500]
        content.add_row("", f"[dim]{response_a}...[/]")

        content.add_row("", "")
        content.add_row("[bold]Response B Preview:[/]", "")
        response_b = r.get("model_b_response", {}).get("content", "")[:500]
        content.add_row("", f"[dim]{response_b}...[/]")

        return Panel(
            content,
            title="[bold]Result Details[/]",
            border_style="cyan"
        )


class FilterScreen(ModalScreen):
    """Modal screen for filtering results."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    CSS = """
    FilterScreen {
        align: center middle;
    }

    #filter-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="filter-container"):
            yield Label("Filter Results")
            yield Input(placeholder="Model filter...", id="model-filter")
            yield Input(placeholder="Winner filter...", id="winner-filter")
            yield Input(placeholder="Occupation filter...", id="occupation-filter")
            with Horizontal():
                yield Button("Apply", id="apply-filter", variant="primary")
                yield Button("Clear", id="clear-filter")
                yield Button("Cancel", id="cancel-filter")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-filter":
            self.dismiss(None)
        elif event.button.id == "clear-filter":
            self.dismiss({})
        elif event.button.id == "apply-filter":
            filters = {
                "model": self.query_one("#model-filter", Input).value,
                "winner": self.query_one("#winner-filter", Input).value,
                "occupation": self.query_one("#occupation-filter", Input).value,
            }
            self.dismiss({k: v for k, v in filters.items() if v})


class ResultsViewer(App):
    """TUI application for viewing evaluation results."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 1 2;
        grid-rows: auto 1fr;
    }

    #summary-section {
        height: auto;
        max-height: 15;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    #results-section {
        border: solid $secondary;
        margin: 1;
    }

    .stat-box {
        width: 1fr;
        height: auto;
        border: solid $primary-lighten-2;
        padding: 0 1;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("f", "filter", "Filter", show=True),
        Binding("e", "export", "Export", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("enter", "view_detail", "Details", show=True),
        Binding("h", "show_help", "Help", show=True),
        Binding("1", "tab_summary", "Summary", show=False),
        Binding("2", "tab_model", "By Model", show=False),
        Binding("3", "tab_kappa", "Agreement", show=False),
    ]

    def __init__(self, results_path: Path, **kwargs):
        super().__init__(**kwargs)
        self.results_path = Path(results_path)
        self.results: List[Dict[str, Any]] = []
        self.filtered_results: List[Dict[str, Any]] = []
        self.current_filters: Dict[str, str] = {}
        self.database: Optional[Database] = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-container"):
            with Container(id="summary-section"):
                with Horizontal():
                    yield Static(id="total-stats", classes="stat-box")
                    yield Static(id="win-rates", classes="stat-box")
                    yield Static(id="kappa-summary", classes="stat-box")

            with Container(id="results-section"):
                with TabbedContent():
                    with TabPane("Results", id="tab-results"):
                        yield DataTable(id="results-table")
                    with TabPane("By Model", id="tab-model"):
                        yield Static(id="model-breakdown")
                    with TabPane("Agreement", id="tab-agreement"):
                        yield Static(id="agreement-stats")

        yield Footer()

    async def on_mount(self) -> None:
        """Load data when app mounts."""
        await self._load_results()
        self._update_display()

    async def _load_results(self) -> None:
        """Load results from file or database."""
        if self.results_path.is_dir():
            # Try loading from database
            db_path = self.results_path / "results.db"
            if db_path.exists():
                self.database = Database(db_path)
                self.results = await self._load_from_database()
            else:
                # Load from JSON files
                json_path = self.results_path / "results.json"
                if json_path.exists():
                    self.results = self._load_from_json(json_path)
        else:
            # Single file
            if self.results_path.suffix == ".json":
                self.results = self._load_from_json(self.results_path)
            elif self.results_path.suffix == ".db":
                self.database = Database(self.results_path)
                self.results = await self._load_from_database()

        self.filtered_results = self.results.copy()

    def _load_from_json(self, path: Path) -> List[Dict[str, Any]]:
        """Load results from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("results", [])

    async def _load_from_database(self) -> List[Dict[str, Any]]:
        """Load results from database."""
        if not self.database:
            return []
        return await self.database.get_all_results()

    def _update_display(self) -> None:
        """Update all display elements."""
        self._update_summary_stats()
        self._update_results_table()
        self._update_model_breakdown()
        self._update_agreement_stats()

    def _update_summary_stats(self) -> None:
        """Update summary statistics."""
        total = len(self.filtered_results)

        # Count wins
        wins = {"gemini": 0, "competitor": 0, "tie": 0}
        for r in self.filtered_results:
            winner = r.get("winner")
            model_a = r.get("model_a", "")
            if winner == model_a:
                wins["gemini"] += 1
            elif winner:
                wins["competitor"] += 1
            else:
                wins["tie"] += 1

        # Total stats
        total_stats = Table.grid()
        total_stats.add_row("[bold]Total Results:[/]", f"{total}")
        total_stats.add_row("[bold]Gemini Wins:[/]", f"[green]{wins['gemini']}[/]")
        total_stats.add_row("[bold]Competitor Wins:[/]", f"[red]{wins['competitor']}[/]")
        total_stats.add_row("[bold]Ties:[/]", f"[yellow]{wins['tie']}[/]")
        self.query_one("#total-stats", Static).update(
            Panel(total_stats, title="Totals", border_style="cyan")
        )

        # Win rates with CI
        non_tie = wins["gemini"] + wins["competitor"]
        if non_tie > 0:
            win_rate = wins["gemini"] / non_tie
            ci_low, ci_high = wilson_confidence_interval(wins["gemini"], non_tie)
        else:
            win_rate, ci_low, ci_high = 0.5, 0.0, 1.0

        win_stats = Table.grid()
        win_stats.add_row(
            "[bold]Gemini Win Rate:[/]",
            f"[green]{win_rate*100:.1f}%[/]"
        )
        win_stats.add_row(
            "[bold]95% CI:[/]",
            f"({ci_low*100:.1f}% - {ci_high*100:.1f}%)"
        )
        self.query_one("#win-rates", Static).update(
            Panel(win_stats, title="Win Rate", border_style="green")
        )

        # Kappa summary (placeholder - calculated in _update_agreement_stats)
        self.query_one("#kappa-summary", Static).update(
            Panel("[dim]See Agreement tab[/]", title="Inter-Judge", border_style="blue")
        )

    def _update_results_table(self) -> None:
        """Update the results data table."""
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)

        table.add_column("ID", width=12)
        table.add_column("Model A", width=15)
        table.add_column("Model B", width=15)
        table.add_column("Winner", width=15)
        table.add_column("Votes", width=10)

        for r in self.filtered_results[:100]:  # Limit display
            prompt_id = r.get("prompt_id", "")[:10]
            model_a = r.get("model_a", "").split("/")[-1][:12]
            model_b = r.get("model_b", "").split("/")[-1][:12]
            winner = r.get("winner", "tie")
            if winner:
                winner = winner.split("/")[-1][:12]
            else:
                winner = "tie"

            judgments = r.get("judgments", [])
            vote_summary = f"{len(judgments)} votes"

            table.add_row(prompt_id, model_a, model_b, winner, vote_summary)

    def _update_model_breakdown(self) -> None:
        """Update model-by-model breakdown."""
        # Group by model pair
        pair_stats = {}
        for r in self.filtered_results:
            pair_key = f"{r.get('model_a', '')} vs {r.get('model_b', '')}"
            if pair_key not in pair_stats:
                pair_stats[pair_key] = {"gemini": 0, "competitor": 0, "tie": 0}

            winner = r.get("winner")
            model_a = r.get("model_a", "")
            if winner == model_a:
                pair_stats[pair_key]["gemini"] += 1
            elif winner:
                pair_stats[pair_key]["competitor"] += 1
            else:
                pair_stats[pair_key]["tie"] += 1

        table = Table(title="Results by Model Pair")
        table.add_column("Pair")
        table.add_column("Gemini Wins", justify="right")
        table.add_column("Competitor Wins", justify="right")
        table.add_column("Ties", justify="right")
        table.add_column("Win Rate", justify="right")

        for pair, stats in pair_stats.items():
            non_tie = stats["gemini"] + stats["competitor"]
            win_rate = stats["gemini"] / non_tie * 100 if non_tie > 0 else 50
            table.add_row(
                pair[:40],
                str(stats["gemini"]),
                str(stats["competitor"]),
                str(stats["tie"]),
                f"{win_rate:.1f}%"
            )

        self.query_one("#model-breakdown", Static).update(table)

    def _update_agreement_stats(self) -> None:
        """Update inter-judge agreement statistics."""
        # Collect all votes
        vote_records = []
        for r in self.filtered_results:
            prompt_id = r.get("prompt_id", "")
            model_a = r.get("model_a", "")
            for j in r.get("judgments", []):
                judge_model = j.get("judge_model", "")
                winner = j.get("winner")
                if winner == model_a:
                    vote = "gemini"
                elif winner:
                    vote = "competitor"
                else:
                    vote = "tie"
                vote_records.append((prompt_id, judge_model, vote))

        if len(vote_records) < 10:
            self.query_one("#agreement-stats", Static).update(
                "[dim]Not enough data for agreement analysis[/]"
            )
            return

        try:
            agreement = calculate_inter_judge_agreement(vote_records)

            content = Table.grid(padding=(0, 2))

            fleiss = agreement.get("fleiss_kappa")
            if fleiss:
                interp = fleiss.interpretation
                color = "green" if fleiss.kappa >= 0.6 else ("yellow" if fleiss.kappa >= 0.4 else "red")
                content.add_row(
                    "[bold]Fleiss' Kappa:[/]",
                    f"[{color}]{fleiss.kappa:.3f}[/] ({interp})"
                )

            content.add_row("", "")
            content.add_row("[bold]Pairwise Cohen's Kappa:[/]", "")

            for (j1, j2), kappa in agreement.get("pairwise_kappa", {}).items():
                j1_short = j1.split("/")[-1][:10]
                j2_short = j2.split("/")[-1][:10]
                color = "green" if kappa.kappa >= 0.6 else ("yellow" if kappa.kappa >= 0.4 else "red")
                content.add_row(
                    f"  {j1_short} vs {j2_short}:",
                    f"[{color}]{kappa.kappa:.3f}[/]"
                )

            overall = agreement.get("overall_agreement_rate", 0)
            content.add_row("", "")
            content.add_row(
                "[bold]Overall Agreement:[/]",
                f"{overall*100:.1f}%"
            )

            self.query_one("#agreement-stats", Static).update(
                Panel(content, title="Inter-Judge Agreement", border_style="blue")
            )

        except Exception as e:
            self.query_one("#agreement-stats", Static).update(
                f"[red]Error calculating agreement: {e}[/]"
            )

    def action_filter(self) -> None:
        """Show filter dialog."""
        def apply_filter(filters):
            if filters is None:
                return
            self.current_filters = filters
            self._apply_filters()

        self.push_screen(FilterScreen(), apply_filter)

    def _apply_filters(self) -> None:
        """Apply current filters to results."""
        self.filtered_results = self.results.copy()

        for key, value in self.current_filters.items():
            if not value:
                continue
            value_lower = value.lower()

            if key == "model":
                self.filtered_results = [
                    r for r in self.filtered_results
                    if value_lower in r.get("model_a", "").lower() or
                       value_lower in r.get("model_b", "").lower()
                ]
            elif key == "winner":
                self.filtered_results = [
                    r for r in self.filtered_results
                    if value_lower in (r.get("winner") or "").lower()
                ]
            elif key == "occupation":
                self.filtered_results = [
                    r for r in self.filtered_results
                    if value_lower in str(r.get("metadata", {}).get("occupation", "")).lower()
                ]

        self._update_display()

    def action_view_detail(self) -> None:
        """View details of selected result."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.filtered_results):
            result = self.filtered_results[table.cursor_row]
            self.push_screen(ResultDetailScreen(result))

    def action_export(self) -> None:
        """Export filtered results."""
        output_path = self.results_path.parent / "filtered_results.json"
        with open(output_path, "w") as f:
            json.dump(self.filtered_results, f, indent=2, default=str)
        self.notify(f"Exported to {output_path}")

    def action_refresh(self) -> None:
        """Refresh data from source."""
        import asyncio
        asyncio.create_task(self._load_results())
        self._update_display()
        self.notify("Refreshed")

    def action_tab_summary(self) -> None:
        self.query_one(TabbedContent).active = "tab-results"

    def action_tab_model(self) -> None:
        self.query_one(TabbedContent).active = "tab-model"

    def action_tab_kappa(self) -> None:
        self.query_one(TabbedContent).active = "tab-agreement"

    def action_show_help(self) -> None:
        """Show help."""
        from .widgets.help_overlay import HelpOverlay
        self.push_screen(HelpOverlay())
```

---

## Summary

This master gap fix plan provides complete, production-ready implementations for all 12 identified gaps:

1. **EvaluationEngine** - Complete parallel request architecture with asyncio.gather, per-model semaphores, retry logic with exponential backoff
2. **Cohen's Kappa** - Full implementation of Cohen's and Fleiss' Kappa with interpretation
3. **Cost Tracking** - Real-time TUI widget with projections and budget tracking
4. **Help Overlay** - Modal help screen with all keyboard shortcuts
5. **CLI Options** - Complete Typer CLI with all required options and validation
6. **TUI Enhancements** - Full progress dashboard with model pairs, timing, kappa display
7. **Name Formality** - Name generator with 5-level formality formatting
8. **Ambiguity Tracking** - Classification and tracking of model responses to ambiguous prompts
9. **Refusal Tracking** - Multi-dimensional refusal classification and analysis
10. **Failure Reports** - Comprehensive failure logging and reporting system
11. **Config Classes** - Complete dataclass-based configuration with validation
12. **Results Viewer** - Full TUI application for viewing and analyzing results

All implementations follow Python best practices, include proper type hints, and are designed to integrate seamlessly with the existing codebase structure.
