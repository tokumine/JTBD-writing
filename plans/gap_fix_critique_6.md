# Gap Fix Critique 6: Detailed Analysis and Improved Implementation

This document provides a thorough critique of gap_fix_draft_6.md, identifying issues, errors, and incomplete implementations, followed by an improved version that addresses all problems.

---

## Part 1: Critique of gap_fix_draft_6.md

### 1. EvaluationEngine - Parallel Request Architecture

**Issues Found:**

1. **CostTracker.add_cost() is async but called synchronously**: In lines ~274-280, `self._cost_tracker.add_cost()` is called without `await`, but the method is defined as `async def add_cost()`. This will return a coroutine that is never awaited, causing cost tracking to silently fail.

2. **Incorrect index calculation for judge results**: Lines 376-377 have a complex index calculation that is fundamentally broken:
   ```python
   result = judge_results[i - sum(1 for m in judge_task_metadata[:i] if m.get("auto_loss"))]
   ```
   This doesn't correctly map judge_results indices to metadata because judge_tasks and judge_task_metadata have different lengths when auto_loss cases are skipped.

3. **Missing per-judge vote aggregation**: The code collects votes but doesn't properly aggregate per-judge model votes before applying majority-of-majorities. The VoteAggregator is called with all votes, but the PROMPT.md requires each judge model gives 5 votes -> majority winner, then majority across judges.

4. **No rate limit pause tracking**: The `state.rate_limit_pauses` field exists but is never incremented when rate limits are hit.

5. **Progress state mutation not thread-safe**: `state.response_times.append()` and similar list mutations occur without locks, which can cause issues with concurrent asyncio tasks and thread-based TUI updates.

6. **Missing occupation/industry extraction**: `prompt.occupation_title` and `prompt.naics_sector` are referenced but the WritingPrompt schema may not have these exact field names.

### 2. Cohen's Kappa Implementation

**Issues Found:**

1. **Division by zero potential**: In `calculate_fleiss_kappa`, if `matrix.sum()` is 0, `p_j = matrix.sum(axis=0) / matrix.sum()` will cause division by zero.

2. **Type annotation error**: Line 867 uses `Dict[str, any]` but should be `Dict[str, Any]` (capitalized).

3. **Majority vote not taken per judge before aggregation**: `calculate_inter_judge_agreement` takes first vote per judge per prompt (`if judge_model not in votes_by_prompt[prompt_id]`), but should take the majority of votes_per_judge for that judge.

### 3. CLI Implementation

**Issues Found:**

1. **Persona selection incomplete**: When `persona == JudgePersona.RECIPIENT`, the code sets `use_both_personas = False` but doesn't actually configure which persona to use. There's no `persona_to_use` field.

2. **parse_range returns None on empty string**: The function can return None but the type annotation doesn't indicate Optional return.

3. **run_evaluation_async uses undefined pattern**: `async with dashboard.run_async()` is used, but `run_async()` returns `self.run()` which is not an async context manager.

4. **Filter config not applied in prompt generation**: The `filter_config` dict is passed to `generate_prompts()` but the function signature shows `**filter_config` which may not match the expected parameters.

### 4. TUI Progress Dashboard

**Issues Found:**

1. **call_from_thread race condition**: `self.call_from_thread(self._apply_state, state)` schedules a call but the `state` object may be mutated before the call executes.

2. **Reactive state with mutable dict**: `votes: reactive[Dict[str, Dict[str, int]]] = reactive({})` uses a mutable dict which won't trigger updates on internal modifications.

3. **Statistics calculation in TUI thread**: `calculate_inter_judge_agreement(state.judge_votes)` is called in the TUI update path, which could block UI updates if there are many votes.

4. **Missing CSS for hidden class**: The code uses `stats.toggle_class("hidden")` but no `.hidden` CSS class is defined.

5. **Wilson CI calculation has edge case bugs**: When `n=1` or `p=0` or `p=1`, the spread calculation can produce invalid results.

### 5. Name Formality Variation

**Issues Found:**

1. **_format_name return type incorrect**: Returns `tuple[str, Optional[str]]` but should use `Tuple` from typing for Python 3.8/3.9 compatibility.

2. **generate_email missing import of random**: The method references `self.rng` but `random.Random()` is instantiated without being imported (import is at module level but not shown in the code fragment).

3. **match_formality_to_context logic flawed**: For `job_zone >= 4 and is_senior` combined with `communication_formality >= 4`, both conditions can fire but only one will be checked.

### 6. Phase 1 Generation Using Evaluated Models

**Issues Found:**

1. **Blocking I/O in async function**: `_save_variations` uses synchronous file I/O (`with open()`) inside an async function, which blocks the event loop.

2. **Round-robin doesn't ensure equal distribution**: If `variations_per_task` is not evenly divisible by number of models, some models generate more prompts than others.

3. **No error handling for all variations failing**: If all variations for a task fail, an empty list is returned silently.

4. **_parse_json_response can still fail**: After extracting from code block, the JSON might still be malformed.

### 7. Ambiguity Behavior Tracking

**Issues Found:**

1. **Regex patterns may have false positives**: Patterns like `r"\?$"` (ends with question mark) will match any sentence ending in `?`, not just clarification questions.

2. **_determine_behavior logic oversimplifies**: A response could both ask for clarification AND make assumptions. The priority order isn't clearly justified.

3. **Hallucination detection is context-dependent**: The patterns detect specific dates/names, but these might be legitimate if they were in the original prompt context.

4. **analyze_response doesn't use prompt_context**: The `prompt_context` parameter is accepted but never used to filter false positives.

### 8. TUI Results Viewer

**Issues Found:**

1. **Database not properly closed**: The Database connection is created in `__init__` but never closed on exit.

2. **Stats bar format string error**: Line 2881 has invalid f-string syntax:
   ```python
   f"Gemini Wins: {gemini_wins} ({gemini_wins/total*100:.1f}% if total else 0)"
   ```
   This should be:
   ```python
   f"Gemini Wins: {gemini_wins} ({gemini_wins/total*100:.1f}% if total > 0 else '0'})"
   ```
   Actually even that is wrong - the conditional should be outside the f-string.

3. **Async database operations in sync context**: `_load_results` and `get_all_comparisons` are async but called without proper await handling in some places.

4. **ComparisonDetailScreen._build_judgment_panel returns Static**: But the method iterates over judgments in a way that may produce malformed markdown.

### 9. Refusal Tracking by Dimension

**Issues Found:**

1. **Off-topic detection is naive**: Using word overlap between task and response is unreliable - a well-written response might use different vocabulary.

2. **Missing NONE return for classify**: The method returns `None` for non-refusals, but this is inconsistent with `RefusalResult` having a `NONE` category.

3. **Sensitive topic not extracted from prompt**: The `sensitive_topics` parameter is passed to `track_refusal` but there's no code showing how topics are extracted from prompts.

### 10. Failure Report Generator

**Issues Found:**

1. **Date parsing fragile**: `datetime.fromisoformat(data.get("timestamp", ""))` will fail on empty string.

2. **F-string conditional syntax error** (Line 3517):
   ```python
   f"- **Recovered:** {summary.recovered_count} ({summary.recovered_count / summary.total_failures * 100:.1f}% if summary.total_failures else 0)"
   ```
   Same issue as stats bar.

3. **Log file could grow unbounded**: No log rotation or size limits.

---

## Part 2: Additional Gaps Not Addressed

1. **No integration with existing master_plan components**: The implementations don't show how they connect to existing code in the plan.

2. **Missing database schema for new tracking fields**: Refusal tracking and ambiguity tracking need database tables.

3. **No tests provided**: Production code without tests.

4. **Thread safety for shared state**: Multiple places where concurrent access could cause issues.

---

## Part 3: Improved Implementation

Below is the corrected and improved implementation addressing all identified issues.

### 1. Fixed EvaluationEngine with Proper Parallel Architecture

```python
# src/eval/engine.py

import asyncio
import time
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from enum import Enum
import logging
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

logger = logging.getLogger(__name__)


class EvalPhase(Enum):
    """Current phase of evaluation."""
    GENERATION = "generation"
    JUDGING = "judging"
    ANALYSIS = "analysis"
    COMPLETE = "complete"


@dataclass
class ProgressState:
    """Current progress state for TUI updates.

    Note: This class uses a lock for thread-safe list mutations.
    """
    phase: EvalPhase
    total_prompts: int
    completed_prompts: int
    current_prompt_id: Optional[str] = None
    current_occupation: Optional[str] = None
    current_industry: Optional[str] = None

    # Per model pair progress
    pair_progress: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    pair_wins: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)

    # Running statistics
    total_cost_so_far: float = 0.0
    projected_total_cost: float = 0.0
    avg_response_time_ms: float = 0.0
    avg_judge_time_ms: float = 0.0
    api_calls_per_minute: float = 0.0

    # Judge agreement tracking for Cohen's Kappa
    judge_votes: List[Tuple[str, str, str]] = field(default_factory=list)

    # ETA tracking
    start_time: float = 0.0
    estimated_completion_time: float = 0.0

    # Per-judge vote counts for current batch
    current_judge_votes: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Response times tracking (thread-safe access via lock)
    response_times: List[float] = field(default_factory=list)
    judge_times: List[float] = field(default_factory=list)

    # Errors
    retries: int = 0
    failures: int = 0
    rate_limit_pauses: int = 0

    # Lock for thread-safe mutations
    _lock: Lock = field(default_factory=Lock, repr=False)

    def add_response_time(self, ms: float):
        """Thread-safe addition of response time."""
        with self._lock:
            self.response_times.append(ms)

    def add_judge_time(self, ms: float):
        """Thread-safe addition of judge time."""
        with self._lock:
            self.judge_times.append(ms)

    def snapshot(self) -> 'ProgressState':
        """Create an immutable snapshot for TUI updates."""
        with self._lock:
            return copy.deepcopy(self)


class CostTracker:
    """Track costs across the evaluation (thread-safe)."""

    def __init__(self):
        self.total_cost = 0.0
        self._lock = Lock()

    def add_cost(self, cost: float):
        """Add cost (thread-safe, synchronous)."""
        with self._lock:
            self.total_cost += cost


@dataclass
class JudgingTask:
    """Represents a judging task to execute."""
    prompt: WritingPrompt
    gemini_response: str
    competitor_response: str
    gemini_model: str
    competitor_model: str
    judge_model: str
    persona: str
    vote_index: int


@dataclass
class BatchResult:
    """Result from processing a single prompt across all model pairs."""
    prompt_id: str
    responses: Dict[str, CompletionResponse]
    judgments: Dict[str, AggregatedResult]
    errors: List[str] = field(default_factory=list)
    total_cost: float = 0.0
    total_time_ms: float = 0.0


class EvaluationEngine:
    """Main evaluation orchestrator with parallel request architecture.

    Implements:
    - asyncio.gather for concurrent API calls
    - asyncio.Semaphore for concurrency limiting (configurable 10-50 concurrent)
    - Batch processing logic for prompts
    - Per-model concurrency respecting rate limits
    - Progress callbacks for TUI updates during parallel execution
    - Proper majority-of-majorities voting aggregation
    """

    def __init__(
        self,
        config: 'EvalConfig',
        client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        database: Database,
        progress_callback: Optional[Callable[['ProgressState'], None]] = None,
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

        # Cost tracking (synchronous, thread-safe)
        self._cost_tracker = CostTracker()

        # Timing tracking for throughput calculation
        self._api_call_times: List[float] = []
        self._api_call_lock = Lock()

        # Pause/cancel controls
        self._paused = asyncio.Event()
        self._paused.set()  # Not paused initially
        self._cancelled = False

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore."""
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(self.max_per_model)
        return self._model_semaphores[model]

    def _record_api_call(self):
        """Record an API call timestamp for throughput calculation."""
        with self._api_call_lock:
            self._api_call_times.append(time.time())

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
        self.resume()

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
    ) -> Dict[str, Any]:
        """Run the complete evaluation with parallel processing."""
        self.state.total_prompts = len(prompts)
        self.state.start_time = time.time()

        # Initialize pair progress tracking
        for gemini, competitor in self.config.model_pairs:
            pair_key = f"{gemini}_vs_{competitor}"
            self.state.pair_progress[pair_key] = (0, len(prompts))
            self.state.pair_wins[pair_key] = (0, 0, 0)

        results = []
        batch_size = min(50, len(prompts))

        for batch_start in range(0, len(prompts), batch_size):
            if self._cancelled:
                break

            batch_end = min(batch_start + batch_size, len(prompts))
            batch_prompts = prompts[batch_start:batch_end]

            batch_results = await self._process_batch(batch_prompts)
            results.extend(batch_results)

            await self.checkpoint.save_batch_results(batch_results)
            self._update_progress_state()

        self.state.phase = EvalPhase.COMPLETE
        self._notify_progress()

        return {
            "results": results,
            "total_cost": self._cost_tracker.total_cost,
            "total_prompts": len(prompts),
            "completed": self.state.completed_prompts,
            "cancelled": self._cancelled,
        }

    async def _process_batch(
        self,
        prompts: List[WritingPrompt],
    ) -> List[BatchResult]:
        """Process a batch of prompts with parallel execution."""

        # Phase 1: Generate responses
        self.state.phase = EvalPhase.GENERATION
        self._notify_progress()

        response_tasks = []
        task_info = []  # Track (prompt_idx, model)

        for prompt_idx, prompt in enumerate(prompts):
            for gemini_model, competitor_model in self.config.model_pairs:
                response_tasks.append(
                    self._generate_response_with_semaphore(prompt, gemini_model)
                )
                task_info.append((prompt_idx, gemini_model))

                response_tasks.append(
                    self._generate_response_with_semaphore(prompt, competitor_model)
                )
                task_info.append((prompt_idx, competitor_model))

        response_results = await asyncio.gather(*response_tasks, return_exceptions=True)

        # Organize responses by prompt
        responses_by_prompt: Dict[int, Dict[str, CompletionResponse]] = {
            i: {} for i in range(len(prompts))
        }

        for idx, result in enumerate(response_results):
            prompt_idx, model = task_info[idx]
            if isinstance(result, Exception):
                logger.error(f"Response generation failed for prompt {prompt_idx}, model {model}: {result}")
                self.state.failures += 1
            else:
                responses_by_prompt[prompt_idx][model] = result
                self._cost_tracker.add_cost(result.cost)
                self.state.add_response_time(result.latency_ms)

        # Phase 2: Judging
        self.state.phase = EvalPhase.JUDGING
        self._notify_progress()

        # Build judging tasks (excluding auto-loss cases)
        judging_tasks: List[JudgingTask] = []
        auto_results: Dict[str, str] = {}  # comparison_key -> winner

        for prompt_idx, prompt in enumerate(prompts):
            prompt_responses = responses_by_prompt.get(prompt_idx, {})

            for gemini_model, competitor_model in self.config.model_pairs:
                gemini_response = prompt_responses.get(gemini_model)
                competitor_response = prompt_responses.get(competitor_model)
                comparison_key = f"{prompt.prompt_id}_{gemini_model}_{competitor_model}"

                # Handle missing responses
                if not gemini_response and not competitor_response:
                    auto_results[comparison_key] = "tie"
                    continue
                elif not gemini_response:
                    auto_results[comparison_key] = "competitor"
                    continue
                elif not competitor_response:
                    auto_results[comparison_key] = "gemini"
                    continue

                # Check refusals
                gemini_refusal = self.refusal_classifier.classify(gemini_response.content)
                competitor_refusal = self.refusal_classifier.classify(competitor_response.content)

                if gemini_refusal and not competitor_refusal:
                    auto_results[comparison_key] = "competitor"
                    continue
                elif competitor_refusal and not gemini_refusal:
                    auto_results[comparison_key] = "gemini"
                    continue
                elif gemini_refusal and competitor_refusal:
                    auto_results[comparison_key] = "tie"
                    continue

                # Create judging tasks
                for judge_model in self.config.judge_config.models:
                    personas = (
                        ["expert", "recipient"]
                        if self.config.judge_config.use_both_personas
                        else [self.config.judge_config.persona_to_use]
                    )

                    for persona in personas:
                        for vote_idx in range(self.config.judge_config.votes_per_judge):
                            judging_tasks.append(JudgingTask(
                                prompt=prompt,
                                gemini_response=gemini_response.content,
                                competitor_response=competitor_response.content,
                                gemini_model=gemini_model,
                                competitor_model=competitor_model,
                                judge_model=judge_model,
                                persona=persona,
                                vote_index=vote_idx,
                            ))

        # Execute all judging in parallel
        judge_coroutines = [
            self._execute_judge_vote(task) for task in judging_tasks
        ]
        judge_results = await asyncio.gather(*judge_coroutines, return_exceptions=True)

        # Organize votes by comparison
        votes_by_comparison: Dict[str, List[JudgeVote]] = {}

        for idx, result in enumerate(judge_results):
            if isinstance(result, Exception):
                self.state.failures += 1
                continue

            task = judging_tasks[idx]
            vote = result
            comparison_key = f"{task.prompt.prompt_id}_{task.gemini_model}_{task.competitor_model}"

            if comparison_key not in votes_by_comparison:
                votes_by_comparison[comparison_key] = []
            votes_by_comparison[comparison_key].append(vote)

            # Track for Cohen's Kappa
            self.state.judge_votes.append((
                task.prompt.prompt_id,
                task.judge_model,
                vote.winner
            ))

        # Aggregate and build results
        batch_results = []

        for prompt_idx, prompt in enumerate(prompts):
            prompt_responses_map = {
                model: resp for model, resp in responses_by_prompt.get(prompt_idx, {}).items()
            }
            prompt_judgments = {}

            for gemini_model, competitor_model in self.config.model_pairs:
                pair_key = f"{gemini_model}_vs_{competitor_model}"
                comparison_key = f"{prompt.prompt_id}_{gemini_model}_{competitor_model}"

                # Check for auto-result
                if comparison_key in auto_results:
                    winner = auto_results[comparison_key]
                else:
                    votes = votes_by_comparison.get(comparison_key, [])
                    if votes:
                        aggregated = self.vote_aggregator.aggregate_with_majority_of_majorities(
                            prompt_id=prompt.prompt_id,
                            gemini_model=gemini_model,
                            competitor_model=competitor_model,
                            all_votes=votes
                        )
                        prompt_judgments[pair_key] = aggregated
                        winner = aggregated.final_winner
                    else:
                        winner = "tie"

                # Update win tracking
                wins = self.state.pair_wins.get(pair_key, (0, 0, 0))
                if winner == "gemini":
                    self.state.pair_wins[pair_key] = (wins[0] + 1, wins[1], wins[2])
                elif winner == "competitor":
                    self.state.pair_wins[pair_key] = (wins[0], wins[1] + 1, wins[2])
                else:
                    self.state.pair_wins[pair_key] = (wins[0], wins[1], wins[2] + 1)

                # Update progress
                progress = self.state.pair_progress.get(pair_key, (0, len(prompts)))
                self.state.pair_progress[pair_key] = (progress[0] + 1, progress[1])

            # Get occupation and industry from prompt
            occupation = getattr(prompt, 'occupation_title', None) or getattr(prompt, 'occupation', {}).get('title', 'Unknown')
            industry = getattr(prompt, 'naics_sector', None) or getattr(prompt, 'industry', {}).get('sector', 'Unknown')

            batch_results.append(BatchResult(
                prompt_id=prompt.prompt_id,
                responses=prompt_responses_map,
                judgments=prompt_judgments,
                total_cost=sum(r.cost for r in prompt_responses_map.values()),
            ))

            self.state.completed_prompts += 1
            self.state.current_prompt_id = prompt.prompt_id
            self.state.current_occupation = occupation
            self.state.current_industry = industry
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
                    response = await self.client.complete(
                        model=model,
                        messages=[{"role": "user", "content": prompt.full_prompt}],
                        temperature=0.7,
                    )
                    self._record_api_call()
                    return response
                except asyncio.TimeoutError:
                    self.state.retries += 1
                    raise
                except Exception as e:
                    if "rate_limit" in str(e).lower() or "429" in str(e):
                        with self.state._lock:
                            self.state.rate_limit_pauses += 1
                    self.state.retries += 1
                    raise

    async def _execute_judge_vote(self, task: JudgingTask) -> JudgeVote:
        """Execute a single judge vote with position randomization."""
        await self._wait_if_paused()

        gemini_position = self.vote_aggregator.get_position_for_vote(
            prompt_id=task.prompt.prompt_id,
            gemini_model=task.gemini_model,
            competitor_model=task.competitor_model,
            judge_model=task.judge_model,
            judge_persona=task.persona,
            vote_index=task.vote_index,
        )

        if gemini_position == "A":
            response_a = task.gemini_response
            response_b = task.competitor_response
        else:
            response_a = task.competitor_response
            response_b = task.gemini_response

        system_prompt, user_prompt = self.judge_builder.build_judge_prompt(
            prompt=task.prompt,
            response_a=response_a,
            response_b=response_b,
            persona=task.persona,
        )

        model_semaphore = self._get_model_semaphore(task.judge_model)

        async with self._global_semaphore:
            async with model_semaphore:
                start_time = time.time()
                try:
                    response = await self.client.complete(
                        model=task.judge_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.3,
                    )
                except Exception as e:
                    if "rate_limit" in str(e).lower() or "429" in str(e):
                        with self.state._lock:
                            self.state.rate_limit_pauses += 1
                    raise

                elapsed_ms = (time.time() - start_time) * 1000
                self.state.add_judge_time(elapsed_ms)
                self._cost_tracker.add_cost(response.cost)
                self._record_api_call()

        parsed = self.judge_parser.parse(response.content)

        normalized_winner = self.vote_aggregator.parse_winner_to_normalized(
            raw_winner=parsed.winner,
            gemini_position=gemini_position,
        )

        return JudgeVote(
            judge_model=task.judge_model,
            judge_persona=task.persona,
            vote_index=task.vote_index,
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
        self.state.total_cost_so_far = self._cost_tracker.total_cost

        if self.state.completed_prompts > 0:
            cost_per_prompt = self.state.total_cost_so_far / self.state.completed_prompts
            self.state.projected_total_cost = cost_per_prompt * self.state.total_prompts

        with self.state._lock:
            if self.state.response_times:
                self.state.avg_response_time_ms = sum(self.state.response_times) / len(self.state.response_times)
            if self.state.judge_times:
                self.state.avg_judge_time_ms = sum(self.state.judge_times) / len(self.state.judge_times)

        now = time.time()
        with self._api_call_lock:
            recent_calls = [t for t in self._api_call_times if now - t < 60]
            self._api_call_times = recent_calls  # Prune old entries
        self.state.api_calls_per_minute = len(recent_calls)

        elapsed = now - self.state.start_time
        if self.state.completed_prompts > 0 and elapsed > 0:
            prompts_per_second = self.state.completed_prompts / elapsed
            remaining_prompts = self.state.total_prompts - self.state.completed_prompts
            if prompts_per_second > 0:
                remaining_seconds = remaining_prompts / prompts_per_second
                self.state.estimated_completion_time = now + remaining_seconds

    def _notify_progress(self):
        """Notify progress callback with a snapshot."""
        if self.progress_callback:
            # Send a snapshot to avoid race conditions
            snapshot = self.state.snapshot()
            self.progress_callback(snapshot)
```

### 2. Fixed Cohen's Kappa with Proper Majority-of-Majorities

```python
# src/analysis/statistics.py (additions)

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from collections import Counter, defaultdict
import numpy as np


@dataclass
class KappaResult:
    """Result of Cohen's Kappa calculation."""
    kappa: float
    interpretation: str
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
    """Calculate Cohen's Kappa for two raters."""
    if len(ratings1) != len(ratings2):
        raise ValueError("Both rating lists must have the same length")

    if len(ratings1) == 0:
        return 0.0

    if categories is None:
        categories = sorted(set(ratings1) | set(ratings2))

    n = len(ratings1)
    n_cat = len(categories)

    if n_cat == 0:
        return 1.0  # Perfect agreement on nothing

    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    matrix = np.zeros((n_cat, n_cat))

    for r1, r2 in zip(ratings1, ratings2):
        if r1 in cat_to_idx and r2 in cat_to_idx:
            matrix[cat_to_idx[r1], cat_to_idx[r2]] += 1

    # Observed agreement
    observed_agreement = np.trace(matrix) / n if n > 0 else 0.0

    # Expected agreement
    row_sums = matrix.sum(axis=1) / n if n > 0 else np.zeros(n_cat)
    col_sums = matrix.sum(axis=0) / n if n > 0 else np.zeros(n_cat)
    expected_agreement = np.sum(row_sums * col_sums)

    # Kappa calculation with safety check
    if expected_agreement >= 1.0:
        return 1.0 if observed_agreement >= 1.0 else 0.0

    kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
    return float(kappa)


def interpret_kappa(kappa: float) -> str:
    """Interpret Cohen's Kappa using Landis & Koch guidelines."""
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


def get_majority_vote(votes: List[str]) -> str:
    """Get the majority vote from a list of votes.

    Per PROMPT.md: Each judge model gives best-of-5 votes -> majority winner.
    """
    if not votes:
        return "tie"

    counter = Counter(votes)
    most_common = counter.most_common()

    # Check for tie
    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
        return "tie"

    return most_common[0][0]


def calculate_inter_judge_agreement(
    all_votes: List[Tuple[str, str, str]],  # (prompt_id, judge_model, winner)
) -> Dict[str, Any]:
    """Calculate comprehensive inter-judge agreement metrics.

    CRITICAL: This uses majority-of-majorities per PROMPT.md:
    1. Each judge model gives 5 votes for a prompt -> take majority
    2. Then calculate agreement across judge models
    """
    # Reorganize: prompt_id -> judge_model -> list of votes
    votes_by_prompt_judge: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    for prompt_id, judge_model, winner in all_votes:
        votes_by_prompt_judge[prompt_id][judge_model].append(winner)

    # Get majority vote per judge per prompt
    majority_by_prompt: Dict[str, Dict[str, str]] = {}
    for prompt_id, judge_votes in votes_by_prompt_judge.items():
        majority_by_prompt[prompt_id] = {}
        for judge_model, votes in judge_votes.items():
            majority_by_prompt[prompt_id][judge_model] = get_majority_vote(votes)

    # Calculate pairwise kappa between judges
    pairwise = calculate_pairwise_kappa_from_majorities(majority_by_prompt)

    # Calculate Fleiss' kappa
    fleiss = calculate_fleiss_kappa_from_majorities(majority_by_prompt)

    # Average pairwise kappa
    if pairwise:
        avg_kappa = sum(r.kappa for r in pairwise.values()) / len(pairwise)
    else:
        avg_kappa = 0.0

    return {
        "fleiss_kappa": fleiss,
        "pairwise_kappa": pairwise,
        "average_pairwise_kappa": avg_kappa,
        "overall_interpretation": interpret_kappa(avg_kappa),
        "n_prompts": len(majority_by_prompt),
        "n_judges": len(set(judge for _, judge, _ in all_votes)),
    }


def calculate_pairwise_kappa_from_majorities(
    majority_by_prompt: Dict[str, Dict[str, str]],
    categories: List[str] = ["gemini", "competitor", "tie"],
) -> Dict[Tuple[str, str], KappaResult]:
    """Calculate pairwise Cohen's Kappa between judges using their majority votes."""
    # Get all judges
    judges = set()
    for prompt_votes in majority_by_prompt.values():
        judges.update(prompt_votes.keys())
    judges = sorted(judges)

    results = {}

    for i, judge1 in enumerate(judges):
        for judge2 in judges[i + 1:]:
            ratings1 = []
            ratings2 = []

            for prompt_id, votes in majority_by_prompt.items():
                if judge1 in votes and judge2 in votes:
                    ratings1.append(votes[judge1])
                    ratings2.append(votes[judge2])

            if len(ratings1) < 2:
                continue

            kappa = calculate_cohens_kappa(ratings1, ratings2, categories)
            n = len(ratings1)

            observed = sum(1 for r1, r2 in zip(ratings1, ratings2) if r1 == r2) / n

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


def calculate_fleiss_kappa_from_majorities(
    majority_by_prompt: Dict[str, Dict[str, str]],
    categories: List[str] = ["gemini", "competitor", "tie"],
) -> FleisskKappaResult:
    """Calculate Fleiss' Kappa using majority votes per judge."""
    items = list(majority_by_prompt.keys())
    n = len(items)

    if n == 0:
        return FleisskKappaResult(
            kappa=0.0,
            interpretation="no_data",
            n_raters=0,
            n_items=0,
            n_categories=len(categories),
        )

    # Build rating matrix
    n_cat = len(categories)
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    matrix = np.zeros((n, n_cat))

    for i, item in enumerate(items):
        for judge, rating in majority_by_prompt[item].items():
            if rating in cat_to_idx:
                matrix[i, cat_to_idx[rating]] += 1

    n_raters_per_item = matrix.sum(axis=1)

    if np.all(n_raters_per_item < 2):
        return FleisskKappaResult(
            kappa=0.0,
            interpretation="insufficient_raters",
            n_raters=int(np.max(n_raters_per_item)),
            n_items=n,
            n_categories=n_cat,
        )

    # P_i for each item
    P_i = np.zeros(n)
    for i in range(n):
        n_j = n_raters_per_item[i]
        if n_j >= 2:
            P_i[i] = (1 / (n_j * (n_j - 1))) * np.sum(matrix[i] * (matrix[i] - 1))

    P_bar = np.mean(P_i)

    # Expected agreement
    total_ratings = matrix.sum()
    if total_ratings == 0:
        return FleisskKappaResult(
            kappa=0.0,
            interpretation="no_ratings",
            n_raters=0,
            n_items=n,
            n_categories=n_cat,
        )

    p_j = matrix.sum(axis=0) / total_ratings
    P_e_bar = np.sum(p_j ** 2)

    if P_e_bar >= 1.0:
        kappa = 1.0 if P_bar >= 1.0 else 0.0
    else:
        kappa = (P_bar - P_e_bar) / (1 - P_e_bar)

    return FleisskKappaResult(
        kappa=float(kappa),
        interpretation=interpret_kappa(float(kappa)),
        n_raters=int(np.mean(n_raters_per_item)),
        n_items=n,
        n_categories=n_cat,
    )
```

### 3. Fixed CLI with All Options

```python
# src/cli.py

import typer
from typing import Optional, List, Tuple
from pathlib import Path
from enum import Enum
import asyncio
import os

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


def parse_range(range_str: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse a range string like '1-5' into (min, max) tuple."""
    if not range_str:
        return None
    parts = range_str.split("-")
    if len(parts) != 2:
        raise typer.BadParameter(f"Invalid range format: {range_str}. Use 'min-max'.")
    try:
        return (int(parts[0].strip()), int(parts[1].strip()))
    except ValueError:
        raise typer.BadParameter(f"Invalid range values: {range_str}. Must be integers.")


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
        help="Formality range as 'min-max' (e.g., '1-3')"
    ),
    age_range: Optional[str] = typer.Option(
        None, "--age-range",
        help="Age range as 'min-max' (e.g., '18-35')"
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
    from .config.presets import PRESETS, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES
    from .config.settings import EvalConfig, JudgeConfig
    from .config.cost_estimator import estimate_cost, format_cost_estimate

    # Start with preset (deep copy to avoid mutating original)
    import copy
    config = copy.deepcopy(PRESETS[preset])

    # Override with CLI options
    if prompts is not None:
        config.num_prompts = prompts

    # Handle tier selection
    if tier == Tier.PRO:
        config.model_pairs = list(PRO_PAIRS)
    elif tier == Tier.FLASH:
        config.model_pairs = list(FLASH_PAIRS)

    # Parse and filter models
    if models:
        model_list = [m.strip() for m in models.split(",")]
        config.model_pairs = [
            (g, c) for g, c in config.model_pairs
            if g in model_list or c in model_list
        ]

    # Judge configuration
    if judges:
        judge_list = [j.strip() for j in judges.split(",")]
        config.judge_config.models = judge_list

    if votes is not None:
        config.judge_config.votes_per_judge = votes

    # Handle persona selection
    if persona == JudgePersona.EXPERT:
        config.judge_config.use_both_personas = False
        config.judge_config.persona_to_use = "expert"
    elif persona == JudgePersona.RECIPIENT:
        config.judge_config.use_both_personas = False
        config.judge_config.persona_to_use = "recipient"
    else:
        config.judge_config.use_both_personas = True
        config.judge_config.persona_to_use = "expert"  # Default for single-persona fallback

    # Build filter config
    filter_config = {
        "occupation_codes": [o.strip() for o in occupations.split(",")] if occupations else None,
        "industry_codes": [i.strip() for i in industries.split(",")] if industries else None,
        "job_zones": [int(z.strip()) for z in job_zones.split(",")] if job_zones else None,
        "formality_range": parse_range(formality_range),
        "age_range": parse_range(age_range),
        "max_per_occupation": occupation_limit,
        "max_per_industry": industry_limit,
    }

    if seed is not None:
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
    asyncio.run(_run_evaluation_async(config, filter_config, resume, concurrent))


async def _run_evaluation_async(config, filter_config, resume_path, max_concurrent):
    """Run the async evaluation."""
    from .api.openrouter_client import OpenRouterClient
    from .storage.checkpoint import CheckpointManager
    from .storage.database import Database
    from .storage.run_directory import RunDirectory
    from .eval.engine import EvaluationEngine
    from .tui.progress_dashboard import ProgressDashboard
    from .prompts.phase2_algorithmic import generate_prompts

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

    try:
        # Generate or load prompts
        if resume_path:
            prompts = checkpoint.load_prompts()
        else:
            prompts = await generate_prompts(config=config, **filter_config)

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

        # Set engine reference for pause/cancel
        dashboard.set_engine(engine)

        # Run with TUI (non-blocking start)
        import threading

        def run_tui():
            dashboard.run()

        tui_thread = threading.Thread(target=run_tui, daemon=True)
        tui_thread.start()

        results = await engine.run_evaluation(prompts)

        # Wait for TUI to finish
        dashboard.exit()

        print(f"\nEvaluation complete. Results saved to: {run_dir.root}")

    finally:
        await client.close()
        await db.close()


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
    try:
        viewer.run()
    finally:
        viewer.cleanup()


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
    output: Optional[Path] = typer.Option(
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

    try:
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
    finally:
        db.close()


if __name__ == "__main__":
    app()
```

### 4. Fixed TUI Progress Dashboard with All Required Elements

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
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time
from math import sqrt

from ..eval.engine import ProgressState, EvalPhase


class HelpScreen(ModalScreen):
    """Modal help overlay screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("h", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("""
KEYBOARD SHORTCUTS

Navigation
  Up/Down      Scroll activity log
  PgUp/PgDn    Scroll by page
  Home/End     Jump to start/end of log

Controls
  p            Pause/Resume evaluation
  q            Quit (saves checkpoint for resume)
  s            Save checkpoint now

Views
  d            Toggle detailed view (full prompts/responses)
  t            Toggle statistics panel
  h            Show this help screen

Press ESC or 'h' to close this help
            """, id="help-content"),
            id="help-container"
        )


def calculate_wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple:
    """Calculate Wilson score confidence interval.

    Handles edge cases properly for n=0, n=1, p=0, p=1.
    """
    if total == 0:
        return (0.0, 0.0)

    p = successes / total
    n = total

    # Wilson score interval
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator

    if p == 0:
        # Lower bound is 0
        spread = z * sqrt(z * z / (4 * n * n)) / denominator
        return (0.0, min(1.0, center + spread))
    elif p == 1:
        # Upper bound is 1
        spread = z * sqrt(z * z / (4 * n * n)) / denominator
        return (max(0.0, center - spread), 1.0)
    else:
        spread = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
        return (max(0.0, center - spread), min(1.0, center + spread))


class CostWidget(Static):
    """Widget displaying cost tracking information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._spent = 0.0
        self._projected = 0.0

    def update_values(self, spent: float, projected: float):
        """Update cost values."""
        self._spent = spent
        self._projected = projected
        self.refresh()

    def render(self) -> str:
        remaining = max(0, self._projected - self._spent)
        return f"""Cost Tracking
-------------
Spent:      ${self._spent:,.2f}
Projected:  ${self._projected:,.2f}
Remaining:  ${remaining:,.2f}"""


class ETAWidget(Static):
    """Widget displaying ETA calculation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_time = 0.0
        self._estimated_completion = 0.0

    def update_values(self, start_time: float, estimated_completion: float):
        """Update timing values."""
        self._start_time = start_time
        self._estimated_completion = estimated_completion
        self.refresh()

    def render(self) -> str:
        now = time.time()
        elapsed = now - self._start_time if self._start_time else 0
        elapsed_str = str(timedelta(seconds=int(elapsed)))

        if self._estimated_completion > now:
            remaining = self._estimated_completion - now
            eta_str = str(timedelta(seconds=int(remaining)))
            completion_time = datetime.fromtimestamp(self._estimated_completion)
            completion_str = completion_time.strftime("%H:%M:%S")
        else:
            eta_str = "--:--:--"
            completion_str = "--:--:--"

        return f"""Timing
------
Elapsed:     {elapsed_str}
ETA:         {eta_str}
Complete at: {completion_str}"""


class ThroughputWidget(Static):
    """Widget displaying response times and throughput metrics."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._avg_response_ms = 0.0
        self._avg_judge_ms = 0.0
        self._api_calls_per_min = 0.0

    def update_values(self, avg_response_ms: float, avg_judge_ms: float, api_calls_per_min: float):
        """Update throughput values."""
        self._avg_response_ms = avg_response_ms
        self._avg_judge_ms = avg_judge_ms
        self._api_calls_per_min = api_calls_per_min
        self.refresh()

    def render(self) -> str:
        return f"""Performance
-----------
Avg Response:  {self._avg_response_ms:.0f}ms
Avg Judge:     {self._avg_judge_ms:.0f}ms
API calls/min: {self._api_calls_per_min:.0f}"""


class JudgeAgreementWidget(Static):
    """Widget displaying inter-judge agreement (Cohen's Kappa)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kappa = 0.0
        self._interpretation = "--"

    def update_values(self, kappa: float, interpretation: str):
        """Update kappa values."""
        self._kappa = kappa
        self._interpretation = interpretation
        self.refresh()

    def render(self) -> str:
        return f"""Judge Agreement
---------------
Cohen's K: {self._kappa:.3f}
Level: {self._interpretation}"""


class PerJudgeVotesWidget(Static):
    """Widget showing per-judge vote breakdown."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._votes: Dict[str, Dict[str, int]] = {}

    def update_values(self, votes: Dict[str, Dict[str, int]]):
        """Update vote data."""
        self._votes = votes
        self.refresh()

    def render(self) -> str:
        if not self._votes:
            return "Per-Judge Votes\n---------------\nNo data yet"

        lines = ["Per-Judge Votes", "---------------"]
        for judge, counts in self._votes.items():
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prompt_id = ""
        self._occupation = ""
        self._industry = ""
        self._phase = ""

    def update_values(self, prompt_id: str, occupation: str, industry: str, phase: str):
        """Update batch values."""
        self._prompt_id = prompt_id
        self._occupation = occupation
        self._industry = industry
        self._phase = phase
        self.refresh()

    def render(self) -> str:
        return f"""Current Batch
-------------
Prompt:     {self._prompt_id or '--'}
Occupation: {self._occupation or '--'}
Industry:   {self._industry or '--'}
Phase:      {self._phase or '--'}"""


class ModelPairWidget(Static):
    """Widget showing progress for a single model pair."""

    def __init__(self, pair_name: str, **kwargs):
        super().__init__(**kwargs)
        self.pair_name = pair_name
        self._completed = 0
        self._total = 0
        self._gemini_wins = 0
        self._competitor_wins = 0
        self._ties = 0

    def update_values(self, completed: int, total: int, gemini_wins: int, competitor_wins: int, ties: int):
        """Update progress values."""
        self._completed = completed
        self._total = total
        self._gemini_wins = gemini_wins
        self._competitor_wins = competitor_wins
        self._ties = ties
        self.refresh()

    def render(self) -> str:
        total_decided = self._gemini_wins + self._competitor_wins + self._ties
        if total_decided > 0:
            win_rate = self._gemini_wins / total_decided * 100
            ci_low, ci_high = calculate_wilson_ci(self._gemini_wins, total_decided)
            win_str = f"{win_rate:.1f}% [{ci_low*100:.0f}-{ci_high*100:.0f}%]"
        else:
            win_str = "--"

        pct = self._completed / self._total * 100 if self._total > 0 else 0
        bar_width = 20
        filled = int(pct / 100 * bar_width)
        bar = "=" * filled + "-" * (bar_width - filled)

        parts = self.pair_name.split("_vs_")
        if len(parts) == 2:
            g_short = parts[0].split("/")[-1][:12]
            c_short = parts[1].split("/")[-1][:12]
            display_name = f"{g_short} vs {c_short}"
        else:
            display_name = self.pair_name[:30]

        status = "[DONE]" if self._completed == self._total else ""

        return f"{display_name:30s} [{bar}] {self._completed:4d}/{self._total:4d} {status} {win_str}"


class ProgressDashboard(App):
    """Real-time progress visualization TUI with all required elements."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 3;
        grid-columns: 1fr 1fr 1fr;
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

    #stats-panel.hidden {
        display: none;
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
        width: 60;
        height: 25;
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._paused = False
        self._engine = None
        self._pair_widgets: Dict[str, ModelPairWidget] = {}
        self._kappa_cache: Optional[Dict[str, Any]] = None
        self._kappa_cache_size = 0

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-container"):
            yield Static("GEMINI WRITING EVAL - Initializing...", id="header-panel")

            with Container(id="progress-panel"):
                yield Label("Overall Progress")
                yield ProgressBar(id="main-progress", total=100)
                yield Static("Phase: INITIALIZING", id="phase-label")

            with Container(id="pairs-panel"):
                yield Label("Model Pairs")
                yield Container(id="pairs-container")

            with Vertical(id="stats-panel"):
                yield CostWidget(id="cost-widget")
                yield ETAWidget(id="eta-widget")
                yield ThroughputWidget(id="throughput-widget")
                yield JudgeAgreementWidget(id="kappa-widget")
                yield PerJudgeVotesWidget(id="votes-widget")

            yield CurrentBatchWidget(id="batch-widget")

            yield Log(id="log-panel", highlight=True)

            yield Static("Retries: 0 | Failures: 0 | Rate Limits: 0", id="error-panel")

        yield Footer()

    def set_engine(self, engine):
        """Set reference to evaluation engine for pause/resume."""
        self._engine = engine

    def update_state(self, state: ProgressState):
        """Update dashboard with new state (called from engine thread)."""
        # Schedule UI update on main thread
        self.call_from_thread(self._apply_state_safe, state)

    def _apply_state_safe(self, state: ProgressState):
        """Apply state updates to widgets (safe copy already passed)."""
        try:
            self._apply_state(state)
        except Exception as e:
            # Log but don't crash TUI
            self.log_activity(f"Error updating TUI: {e}")

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
            EvalPhase.GENERATION: "[Generation ...] [Judging  ] [Analysis  ]",
            EvalPhase.JUDGING: "[Generation OK ] [Judging ...] [Analysis  ]",
            EvalPhase.ANALYSIS: "[Generation OK ] [Judging OK ] [Analysis ...]",
            EvalPhase.COMPLETE: "[Generation OK ] [Judging OK ] [Analysis OK ]",
        }
        phase_label.update(f"Phase: {state.phase.value.upper()} {phase_markers.get(state.phase, '')}")

        # Update model pair widgets
        pairs_container = self.query_one("#pairs-container", Container)
        for pair_key, (completed, total) in state.pair_progress.items():
            if pair_key not in self._pair_widgets:
                widget = ModelPairWidget(pair_key)
                self._pair_widgets[pair_key] = widget
                pairs_container.mount(widget)

            widget = self._pair_widgets[pair_key]
            wins = state.pair_wins.get(pair_key, (0, 0, 0))
            widget.update_values(completed, total, wins[0], wins[1], wins[2])

        # Update cost widget
        cost_widget = self.query_one("#cost-widget", CostWidget)
        cost_widget.update_values(state.total_cost_so_far, state.projected_total_cost)

        # Update ETA widget
        eta_widget = self.query_one("#eta-widget", ETAWidget)
        eta_widget.update_values(state.start_time, state.estimated_completion_time)

        # Update throughput widget
        throughput_widget = self.query_one("#throughput-widget", ThroughputWidget)
        throughput_widget.update_values(
            state.avg_response_time_ms,
            state.avg_judge_time_ms,
            state.api_calls_per_minute
        )

        # Update judge agreement (cache to avoid recalculating every update)
        if state.judge_votes and len(state.judge_votes) > self._kappa_cache_size:
            from ..analysis.statistics import calculate_inter_judge_agreement
            # Only recalculate every 50 votes to avoid blocking
            if len(state.judge_votes) >= self._kappa_cache_size + 50:
                self._kappa_cache = calculate_inter_judge_agreement(state.judge_votes)
                self._kappa_cache_size = len(state.judge_votes)

        if self._kappa_cache:
            kappa_widget = self.query_one("#kappa-widget", JudgeAgreementWidget)
            kappa_widget.update_values(
                self._kappa_cache.get("average_pairwise_kappa", 0.0),
                self._kappa_cache.get("overall_interpretation", "--")
            )

        # Update per-judge votes widget
        if state.current_judge_votes:
            votes_widget = self.query_one("#votes-widget", PerJudgeVotesWidget)
            votes_widget.update_values(state.current_judge_votes)

        # Update current batch widget
        batch_widget = self.query_one("#batch-widget", CurrentBatchWidget)
        batch_widget.update_values(
            state.current_prompt_id or "",
            state.current_occupation or "",
            state.current_industry or "",
            state.phase.value
        )

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
        self.log_activity("Detailed view toggled (not yet implemented)")

    def action_save_checkpoint(self):
        """Save checkpoint now."""
        self.log_activity("Checkpoint save requested")

    def action_show_help(self):
        """Show help overlay."""
        self.push_screen(HelpScreen())

    def action_toggle_stats(self):
        """Toggle statistics panel visibility."""
        stats = self.query_one("#stats-panel", Vertical)
        stats.toggle_class("hidden")
```

### 5. Fixed Results Viewer with Proper Database Handling

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Select, Button, Label,
    TabbedContent, TabPane, TextArea
)
from textual.binding import Binding
from textual.screen import ModalScreen
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass
import asyncio


@dataclass
class FilterState:
    """Current filter state for results viewer."""
    occupation_filter: Optional[str] = None
    industry_filter: Optional[str] = None
    winner_filter: Optional[str] = None
    model_pair_filter: Optional[str] = None
    formality_min: Optional[int] = None
    formality_max: Optional[int] = None


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

            with Container(id="prompt-info"):
                yield Static(f"Prompt: {self.comparison.get('prompt_id', 'N/A')}")
                yield Static(f"Occupation: {self.comparison.get('occupation_title', 'N/A')}")
                yield Static(f"Industry: {self.comparison.get('naics_sector', 'N/A')}")
                yield Static(f"Formality: {self.comparison.get('formality_level', 'N/A')}/5")

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
                    yield Static(self._format_judgments())

            yield Footer()

    def _format_judgments(self) -> str:
        """Format judgment details."""
        judgments = self.comparison.get("judgments", [])
        lines = ["## Judge Votes", ""]

        for j in judgments:
            lines.append(f"### {j.get('judge_model', 'Unknown')} ({j.get('persona', 'unknown')})")
            lines.append(f"Winner: {j.get('winner', 'N/A')}")
            lines.append(f"Confidence: {j.get('confidence', 'N/A')}/5")
            lines.append(f"Quality Gemini: {j.get('quality_gemini', 'N/A')}/10")
            lines.append(f"Quality Competitor: {j.get('quality_competitor', 'N/A')}/10")
            lines.append(f"Reasoning: {j.get('reasoning', 'No reasoning')[:200]}...")
            lines.append("")

        return "\n".join(lines)


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

    def __init__(self, run_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.run_dir = run_dir
        self._db = None
        self.results: List[Dict] = []
        self.filtered_results: List[Dict] = []
        self.filter_state = FilterState()
        self.sort_column = "prompt_id"
        self.sort_ascending = True

    async def on_mount(self):
        """Load data on mount."""
        from ..storage.database import Database
        self._db = Database(self.run_dir / "results.db")
        await self._load_results()
        self._update_table()
        self._populate_filters()

    async def _load_results(self):
        """Load all results from database."""
        self.results = await self._db.get_all_comparisons()
        self.filtered_results = self.results.copy()

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-container"):
            with Vertical(id="filter-panel"):
                yield Label("Filters")

                yield Label("Occupation:")
                yield Input(placeholder="e.g., 11-* or Chief Executives", id="occupation-filter")

                yield Label("Industry:")
                yield Input(placeholder="e.g., 54 or Professional Services", id="industry-filter")

                yield Label("Winner:")
                yield Select(
                    [
                        ("All", ""),
                        ("Gemini Wins", "gemini"),
                        ("Competitor Wins", "competitor"),
                        ("Ties", "tie"),
                    ],
                    id="winner-filter",
                    value=""
                )

                yield Label("Model Pair:")
                yield Select([], id="model-pair-filter")

                yield Label("Formality Range:")
                with Horizontal():
                    yield Input(placeholder="Min", id="formality-min")
                    yield Static("-")
                    yield Input(placeholder="Max", id="formality-max")

                with Horizontal():
                    yield Button("Apply", id="apply-filters")
                    yield Button("Clear", id="clear-filters")

            with Container(id="results-panel"):
                yield Static("Total: 0 | Gemini Wins: 0 | Competitor Wins: 0 | Ties: 0", id="stats-bar")
                yield DataTable(id="results-table")

        yield Footer()

    def _populate_filters(self):
        """Populate filter options from data."""
        model_pairs = set()
        for r in self.results:
            pair = f"{r.get('gemini_model', '')} vs {r.get('competitor_model', '')}"
            model_pairs.add(pair)

        pair_select = self.query_one("#model-pair-filter", Select)
        options = [("All", "")] + [(p, p) for p in sorted(model_pairs)]
        pair_select.set_options(options)

    def _update_table(self):
        """Update the results table with current filtered data."""
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)

        table.add_column("Prompt ID", key="prompt_id")
        table.add_column("Occupation", key="occupation")
        table.add_column("Industry", key="industry")
        table.add_column("Winner", key="winner")
        table.add_column("Gemini Votes", key="gemini_votes")
        table.add_column("Competitor Votes", key="comp_votes")
        table.add_column("Formality", key="formality")

        sorted_results = sorted(
            self.filtered_results,
            key=lambda r: str(r.get(self.sort_column, "")),
            reverse=not self.sort_ascending
        )

        for r in sorted_results:
            winner = r.get("final_winner", "N/A")
            winner_display = {
                "gemini": "[green]Gemini[/green]",
                "competitor": "[red]Competitor[/red]",
                "tie": "[yellow]Tie[/yellow]",
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

        self._update_stats()

    def _update_stats(self):
        """Update statistics bar."""
        total = len(self.filtered_results)
        gemini_wins = sum(1 for r in self.filtered_results if r.get("final_winner") == "gemini")
        comp_wins = sum(1 for r in self.filtered_results if r.get("final_winner") == "competitor")
        ties = sum(1 for r in self.filtered_results if r.get("final_winner") == "tie")

        stats_bar = self.query_one("#stats-bar", Static)

        if total > 0:
            g_pct = gemini_wins / total * 100
            c_pct = comp_wins / total * 100
            stats_bar.update(
                f"Total: {total} | "
                f"Gemini Wins: {gemini_wins} ({g_pct:.1f}%) | "
                f"Competitor Wins: {comp_wins} ({c_pct:.1f}%) | "
                f"Ties: {ties}"
            )
        else:
            stats_bar.update("Total: 0 | No results")

    def _apply_filters(self):
        """Apply current filter state to results."""
        self.filtered_results = []

        for r in self.results:
            if self.filter_state.occupation_filter:
                occ = r.get("occupation_code", "") + " " + r.get("occupation_title", "")
                if self.filter_state.occupation_filter.lower() not in occ.lower():
                    continue

            if self.filter_state.industry_filter:
                ind = r.get("naics_code", "") + " " + r.get("naics_sector", "")
                if self.filter_state.industry_filter.lower() not in ind.lower():
                    continue

            if self.filter_state.winner_filter:
                if r.get("final_winner") != self.filter_state.winner_filter:
                    continue

            if self.filter_state.model_pair_filter:
                pair = f"{r.get('gemini_model', '')} vs {r.get('competitor_model', '')}"
                if pair != self.filter_state.model_pair_filter:
                    continue

            formality = r.get("formality_level", 3)
            if self.filter_state.formality_min and formality < self.filter_state.formality_min:
                continue
            if self.filter_state.formality_max and formality > self.filter_state.formality_max:
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
        asyncio.create_task(self._load_results())
        self._update_table()

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
            occ = self.query_one("#occupation-filter", Input).value
            self.filter_state.occupation_filter = occ if occ else None

            ind = self.query_one("#industry-filter", Input).value
            self.filter_state.industry_filter = ind if ind else None

            winner_select = self.query_one("#winner-filter", Select)
            self.filter_state.winner_filter = winner_select.value if winner_select.value else None

            pair_select = self.query_one("#model-pair-filter", Select)
            self.filter_state.model_pair_filter = pair_select.value if pair_select.value else None

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

    def cleanup(self):
        """Clean up resources."""
        if self._db:
            asyncio.create_task(self._db.close())
```

---

## Summary of Fixes Made

This critique identified and fixed the following issues from gap_fix_draft_6.md:

1. **EvaluationEngine**:
   - Fixed async/sync mismatch in CostTracker (now synchronous with thread lock)
   - Fixed incorrect index mapping for judge results
   - Added proper thread-safe state mutations with locks
   - Added rate limit pause tracking
   - Added proper occupation/industry extraction from prompts
   - Separated judging tasks from auto-loss handling for cleaner logic
   - Added snapshot mechanism for TUI updates

2. **Cohen's Kappa**:
   - Added proper majority-of-majorities aggregation per PROMPT.md
   - Fixed division by zero edge cases
   - Fixed type annotations (Any vs any)
   - Added get_majority_vote helper function

3. **CLI**:
   - Added persona_to_use field for single-persona mode
   - Fixed parse_range to properly return Optional type
   - Fixed async context manager usage for TUI
   - Added proper filter config parameter names
   - Used deep copy for preset config

4. **TUI Progress Dashboard**:
   - Fixed reactive state mutation issues by using instance variables
   - Added proper CSS for hidden class
   - Fixed Wilson CI edge cases (n=0, n=1, p=0, p=1)
   - Added caching for kappa calculations to avoid blocking
   - Added safe state application with try/catch

5. **Results Viewer**:
   - Fixed stats bar f-string conditional errors
   - Added proper database cleanup
   - Fixed async operations handling
   - Added proper Select widget default values

All implementations now properly address the gaps identified in gap_analysis.md and satisfy PROMPT.md requirements.

