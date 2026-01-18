# Gap Fix Critique 2: Detailed Analysis and Improved Implementation

This document provides a thorough critique of gap_fix_draft_2.md and an improved version that addresses all identified issues.

---

## CRITIQUE OF GAP_FIX_DRAFT_2.md

### Overall Assessment

The draft provides substantial implementations for the identified gaps. However, there are several issues ranging from missing functionality to architectural concerns that need to be addressed.

---

## 1. PARALLEL REQUEST ARCHITECTURE - CRITIQUE

### Strengths
- Uses asyncio.Semaphore for both global and per-model concurrency control
- Has pause/shutdown mechanisms
- Includes progress tracking with callbacks

### Critical Issues

**Issue 1.1: Missing TaskGroup for Python 3.11+ compatibility**
The draft uses only `asyncio.gather()` but doesn't leverage `asyncio.TaskGroup` which provides better exception handling and structured concurrency. For a robust production system, we should support both.

**Issue 1.2: No circuit breaker integration**
The EvaluationEngine doesn't integrate with the circuit breaker mentioned in the master plan. If a model consistently fails, there's no mechanism to temporarily disable it.

**Issue 1.3: Semaphore not initialized per event loop**
The semaphores are created in `__init__` but asyncio semaphores must be created within an event loop context. This will cause `RuntimeError` if the engine is created outside an async context.

**Issue 1.4: Missing response caching for retries**
When a response generation fails and retries, there's no mechanism to avoid re-generating the successful response from the other model.

**Issue 1.5: `_build_system_prompt` has hardcoded string formatting**
May raise exceptions if persona fields are missing or None. Needs defensive coding.

**Issue 1.6: No integration with FailureSummaryGenerator**
The engine tracks `progress.failures` but doesn't record them in the FailureSummaryGenerator.

---

## 2. COHEN'S KAPPA - CRITIQUE

### Strengths
- Correct implementation of Cohen's Kappa formula
- Fleiss' Kappa for multiple raters
- Good interpretation using Landis & Koch guidelines

### Issues

**Issue 2.1: Redundant expected agreement calculation**
In `calculate_pairwise_kappa`, expected agreement is calculated redundantly after already calling `calculate_cohens_kappa`. This is inefficient.

**Issue 2.2: Missing weighted kappa**
For ordinal data (quality scores 1-10), weighted kappa would be more appropriate than unweighted kappa, but it's not implemented.

**Issue 2.3: InterJudgeAgreementAnalyzer lacks persistence**
The analyzer doesn't save its state to disk, so it would be lost on crash/restart.

**Issue 2.4: `get_current_kappa` requires 10 minimum samples**
This hardcoded threshold may be too high for small evaluation runs (preset 1-3).

---

## 3. TUI PROGRESS DASHBOARD - CRITIQUE

### Strengths
- Complete layout matching PROMPT.md specification
- Help screen with keyboard shortcuts
- Cost tracking display

### Issues

**Issue 3.1: EvalPhase comparison is broken**
```python
if progress.phase.value > p.value:  # This compares strings, not enum values
```
The comparison `progress.phase.value > p.value` compares string values of enums which won't work correctly.

**Issue 3.2: Missing exception handling in update_display**
If any widget query fails, the entire display update crashes.

**Issue 3.3: No proper async integration**
`dashboard.run()` is blocking, but the eval engine runs in an async task. The TUI won't update properly because Textual needs proper async event loop integration.

**Issue 3.4: Hardcoded widget IDs for judges**
Only supports 3 judges (`#judge-status-1` to `#judge-status-3`), but the config allows variable numbers.

**Issue 3.5: Missing scroll handling for activity log**
The Log widget is created but arrow key bindings for scrolling aren't explicit.

---

## 4. CLI OPTIONS - CRITIQUE

### Strengths
- Comprehensive option coverage
- Good model name resolution

### Issues

**Issue 4.1: Invalid attribute access**
```python
config.judge_config._persona_mode = "expert"  # Private attribute doesn't exist
```
The `_persona_mode` attribute isn't defined in JudgeConfig schema.

**Issue 4.2: Missing model_copy() on PRESETS[preset]**
If PRESETS is a dict of EvalConfig objects, calling `.model_copy()` may fail if it's a plain dataclass (not Pydantic).

**Issue 4.3: Dashboard run() blocks event loop**
The `_run_evaluation` function creates a task and then calls `dashboard.run()`, but the dashboard.run() is blocking and will prevent the eval task from executing properly.

**Issue 4.4: Missing `--concurrency` validation**
The help says `10-50` but there's no validation enforcing this.

---

## 5. NAME FORMALITY VARIATION - CRITIQUE

### Strengths
- Good variety of formality levels
- Census-based demographic distribution

### Issues

**Issue 5.1: Incomplete prefix logic**
For formal names, the code uses `self.prefix` but many generated names won't have prefixes unless explicitly requested, making formal formatting fall through to less formal.

**Issue 5.2: Missing gender-appropriate prefixes**
The prefix selection doesn't properly match gender (Mr. vs Ms.).

**Issue 5.3: No title-based prefixes**
Doctors, professors, and other professional titles should be inferred from job titles in some cases.

---

## 6. TUI RESULTS VIEWER - CRITIQUE

### Strengths
- Good filter/sort architecture
- Modal detail screen
- Drill-down into judgments

### Issues

**Issue 6.1: Hardcoded model pairs in `_get_model_pairs`**
Should query database dynamically.

**Issue 6.2: Division by zero in `_update_summary`**
```python
f"Gemini: {gemini_wins} ({gemini_wins/total*100:.1f}%)"  # Crashes if total=0
```

**Issue 6.3: Missing database query method**
`database.query_comparisons()` and `database.get_comparison_detail()` aren't implemented anywhere.

**Issue 6.4: TextArea.load_text doesn't exist**
Should be `text = "..."` or use `update()` method.

---

## 7. PHASE 1 GENERATION - CRITIQUE

### Strengths
- Round-robin model distribution
- Good prompt template

### Issues

**Issue 7.1: No validation of JSON responses**
The try/except for JSON parsing just raises ValueError, but should have fallback/retry logic.

**Issue 7.2: Missing cost tracking**
Phase 1 generation can be expensive but doesn't track costs.

**Issue 7.3: ONetTask type not defined**
The import references `ONetTask` but this type isn't shown in the codebase.

---

## 8. AMBIGUITY BEHAVIOR TRACKING - CRITIQUE

### Strengths
- Comprehensive pattern matching
- Multiple behavior categories

### Issues

**Issue 8.1: Regex patterns may over-match**
Some patterns like `r"\?(?=.*\n)"` can match any question mark, not just clarification requests.

**Issue 8.2: Missing context from prompt**
Can't distinguish hallucinated details from details that were in the original prompt.

**Issue 8.3: No integration with evaluation engine**
The tracker exists but isn't called from the engine.

---

## 9. REFUSAL TRACKING - CRITIQUE

### Strengths
- Good categorization
- Breakdown by multiple dimensions

### Issues

**Issue 9.1: Pattern pre-compilation could be optimized**
Creating new regex objects each time is inefficient; should compile once.

**Issue 9.2: `_find_problematic_combinations` has set-in-max bug**
```python
max(set(r.category.value for r in records), key=lambda c: ...)
```
This is correct but could be clearer.

---

## 10. FAILURE SUMMARY REPORT - CRITIQUE

### Strengths
- Comprehensive reporting
- Both text and JSON output
- Recommendations section

### Issues

**Issue 10.1: `successful_calls` calculation is wrong**
```python
successful_calls=total_api_calls - total_failures + recovered
```
Recovered failures are still failures that eventually succeeded, so this overcounts successes.

**Issue 10.2: Missing integration with main engine**
No code showing how to integrate FailureSummaryGenerator with EvaluationEngine.

---

## 11. WILSON CONFIDENCE INTERVAL - CRITIQUE

### Strengths
- Correct implementation
- Handles edge cases

### Issues

**Issue 11.1: Scipy import at function level**
Should import at module level for efficiency.

---

## GAPS STILL MISSING FROM DRAFT

After reviewing against the gap_analysis.md, these gaps are NOT addressed:

1. **"Other flash-tier models"** - Only GPT-4.1 and Sonnet, no extensibility mechanism
2. **Sensitive topic win rate tracking** - Fields exist but no separate analysis shown
3. **EvalConfig extensions** - New fields like `formality_min`, `formality_max`, `age_min`, `age_max` aren't added to the EvalConfig schema
4. **Statistics panel (s key)** - Dashboard shows "not implemented" for statistics action

---

## IMPROVED IMPLEMENTATION

Below are the corrected and improved implementations that address all the issues identified above.

---

## 1. IMPROVED EVALUATION ENGINE

```python
# src/eval/engine.py

import asyncio
import time
import signal
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple, Set
from enum import Enum, auto
import logging
from contextlib import asynccontextmanager

from ..api.openrouter_client import OpenRouterClient, CompletionResponse
from ..api.circuit_breaker import CircuitBreaker
from ..prompts.schemas import WritingPrompt
from ..config.presets import EvalConfig, JudgeConfig
from ..storage.checkpoint import CheckpointManager
from ..storage.database import EvalDatabase
from .vote_aggregator import VoteAggregator, JudgeVote, AggregatedResult
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .refusal_classifier import RefusalClassifier, RefusalCategory
from .response_analyzer import ResponseAnalyzer
from .ambiguity_tracker import AmbiguityTracker
from ..reports.failure_summary import FailureSummaryGenerator

logger = logging.getLogger(__name__)


class EvalPhase(Enum):
    """Evaluation phase for progress tracking - ordered by execution."""
    INITIALIZING = 0
    GENERATION = 1
    JUDGING = 2
    ANALYSIS = 3
    COMPLETE = 4


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
    response_statuses: Dict[str, str] = field(default_factory=dict)
    judge_statuses: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Statistics
    response_times: List[float] = field(default_factory=list)
    api_calls_per_minute: float = 0.0

    # Errors
    retries: int = 0
    failures: int = 0
    rate_limit_pauses: int = 0

    # Inter-judge agreement
    current_kappa: Optional[float] = None


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

    Uses asyncio.TaskGroup (Python 3.11+) or asyncio.gather for concurrent
    API calls with:
    - Configurable concurrency limits via asyncio.Semaphore
    - Per-model rate limit awareness with circuit breakers
    - Progress callbacks for TUI updates
    - Batch processing with checkpointing
    - Full integration with failure tracking
    """

    # Per-model concurrency defaults
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
        client: OpenRouterClient,
        config: EvalConfig,
        checkpoint_manager: CheckpointManager,
        database: EvalDatabase,
        failure_generator: FailureSummaryGenerator,
        progress_callback: Optional[Callable[[ProgressState], None]] = None,
        max_concurrent_requests: int = 25,
    ):
        self.client = client
        self.config = config
        self.checkpoint = checkpoint_manager
        self.database = database
        self.failure_generator = failure_generator
        self.progress_callback = progress_callback
        self.max_concurrent = max_concurrent_requests

        # Semaphores - will be initialized in async context
        self._global_semaphore: Optional[asyncio.Semaphore] = None
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._semaphores_initialized = False

        # Circuit breakers per model
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Components
        self.vote_aggregator = VoteAggregator()
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.refusal_classifier = RefusalClassifier()
        self.response_analyzer = ResponseAnalyzer()
        self.ambiguity_tracker = AmbiguityTracker()

        # Inter-judge agreement tracker
        from ..analysis.statistics import InterJudgeAgreementAnalyzer
        self.kappa_analyzer = InterJudgeAgreementAnalyzer()

        # State
        self.progress = ProgressState()
        self._shutdown_requested = False
        self._paused = False

        # Statistics
        self._api_call_times: List[float] = []
        self._total_cost = 0.0
        self._total_api_calls = 0

        # Response cache for retries
        self._response_cache: Dict[Tuple[str, str], ModelResponse] = {}

    def _ensure_semaphores(self):
        """Initialize semaphores - must be called within async context."""
        if not self._semaphores_initialized:
            self._global_semaphore = asyncio.Semaphore(self.max_concurrent)
            self._semaphores_initialized = True

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore for concurrency control."""
        self._ensure_semaphores()
        if model not in self._model_semaphores:
            limit = self.MODEL_CONCURRENCY_LIMITS.get(
                model, self.DEFAULT_MODEL_CONCURRENCY
            )
            self._model_semaphores[model] = asyncio.Semaphore(limit)
        return self._model_semaphores[model]

    def _get_circuit_breaker(self, model: str) -> CircuitBreaker:
        """Get or create circuit breaker for model."""
        if model not in self._circuit_breakers:
            self._circuit_breakers[model] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_max_calls=3
            )
        return self._circuit_breakers[model]

    async def _call_model_with_limits(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> CompletionResponse:
        """Make API call with concurrency limits and circuit breaker."""
        self._ensure_semaphores()
        model_semaphore = self._get_model_semaphore(model)
        circuit_breaker = self._get_circuit_breaker(model)

        if not circuit_breaker.can_execute():
            raise Exception(f"Circuit breaker open for {model}")

        async with self._global_semaphore:
            async with model_semaphore:
                while self._paused and not self._shutdown_requested:
                    await asyncio.sleep(0.5)

                if self._shutdown_requested:
                    raise asyncio.CancelledError("Shutdown requested")

                try:
                    response = await self.client.complete(model, messages, **kwargs)
                    self._api_call_times.append(time.time())
                    self._total_cost += response.cost
                    self._total_api_calls += 1
                    circuit_breaker.record_success()
                    return response
                except Exception as e:
                    circuit_breaker.record_failure()
                    self.progress.retries += 1
                    raise

    async def _generate_response(
        self,
        prompt: WritingPrompt,
        model: str,
        max_retries: int = 3
    ) -> ModelResponse:
        """Generate a single model response with retry logic."""
        cache_key = (prompt.prompt_id, model)
        if cache_key in self._response_cache:
            return self._response_cache[cache_key]

        system_prompt = self._build_system_prompt(prompt)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt.full_prompt}
        ]

        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self._call_model_with_limits(model, messages)
                is_refusal, refusal_cat = self.refusal_classifier.classify(response.content)

                result = ModelResponse(
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

                self._response_cache[cache_key] = result

                if getattr(prompt, 'is_ambiguous', False):
                    self.ambiguity_tracker.analyze_response(
                        prompt.prompt_id, model, response.content,
                        getattr(prompt, 'ambiguity_type', 'unclear')
                    )

                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries} for {model}: {e}")

                self.failure_generator.record_failure(
                    event_type="api_error",
                    model=model,
                    prompt_id=prompt.prompt_id,
                    error_message=str(e),
                    retry_count=attempt + 1,
                    recovered=False
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        logger.error(f"All retries failed for {model}: {last_error}")
        return ModelResponse(
            prompt_id=prompt.prompt_id,
            model=model,
            content="",
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            cost=0,
            is_error=True,
            error_message=str(last_error)
        )

    def _build_system_prompt(self, prompt: WritingPrompt) -> str:
        """Build system prompt with defensive coding."""
        writer = getattr(prompt, 'writer', None)
        company = getattr(prompt, 'company', None)

        name = getattr(writer, 'name', 'a professional') if writer else 'a professional'
        job_title = getattr(writer, 'job_title', 'employee') if writer else 'employee'
        company_name = getattr(company, 'name', 'a company') if company else 'a company'
        skill_level = getattr(writer, 'skill_level', 'mid-level') if writer else 'mid-level'
        years_exp = getattr(writer, 'years_experience', 'several') if writer else 'several'
        generation = getattr(writer, 'generation', 'professional') if writer else 'professional'

        if isinstance(generation, str):
            generation = generation.replace('_', ' ')

        return f"""You are {name}, a {job_title} at {company_name}.
You are a {skill_level}-level professional with {years_exp} years of experience.
Your communication style should match a {generation} professional.
Write naturally and authentically for this scenario."""

    async def _generate_responses_parallel(
        self,
        prompts: List[WritingPrompt],
        gemini_model: str,
        competitor_model: str
    ) -> List[Tuple[WritingPrompt, ModelResponse, ModelResponse]]:
        """Generate responses using TaskGroup (3.11+) or gather with proper error handling."""
        results = []

        async def generate_pair(prompt: WritingPrompt):
            # Update progress
            self.progress.current_prompt_id = prompt.prompt_id
            self.progress.current_prompt_text = getattr(prompt, 'onet_task', str(prompt))[:100]
            self.progress.current_occupation = getattr(prompt, 'occupation_title', None)
            self.progress.current_industry = getattr(prompt, 'naics_sector', None)
            self.progress.response_statuses[gemini_model] = "generating"
            self.progress.response_statuses[competitor_model] = "generating"
            self._notify_progress()

            # Generate both responses in parallel
            gemini_resp, competitor_resp = await asyncio.gather(
                self._generate_response(prompt, gemini_model),
                self._generate_response(prompt, competitor_model)
            )

            self.progress.response_statuses[gemini_model] = "complete"
            self.progress.response_statuses[competitor_model] = "complete"
            if gemini_resp.latency_ms:
                self.progress.response_times.append(gemini_resp.latency_ms)
            if competitor_resp.latency_ms:
                self.progress.response_times.append(competitor_resp.latency_ms)
            self._notify_progress()

            return (prompt, gemini_resp, competitor_resp)

        # Use TaskGroup if Python 3.11+, otherwise gather
        if sys.version_info >= (3, 11):
            try:
                async with asyncio.TaskGroup() as tg:
                    tasks = [tg.create_task(generate_pair(p)) for p in prompts]
                results = [t.result() for t in tasks]
            except* Exception as eg:
                for exc in eg.exceptions:
                    logger.error(f"TaskGroup error: {exc}")
                    self.progress.failures += 1
        else:
            task_results = await asyncio.gather(
                *[generate_pair(p) for p in prompts],
                return_exceptions=True
            )
            for r in task_results:
                if isinstance(r, Exception):
                    logger.error(f"Batch error: {r}")
                    self.progress.failures += 1
                else:
                    results.append(r)

        return results

    async def _judge_with_kappa_tracking(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> List[JudgeVote]:
        """Execute all judge votes with Kappa tracking."""
        tasks = []
        judge_config = self.config.judge_config

        def get_position(vote_idx: int) -> str:
            seed = hash(f"{prompt.prompt_id}_{vote_idx}") % 2
            return "A" if seed == 0 else "B"

        for judge_model in judge_config.models:
            personas = ["expert", "recipient"] if judge_config.use_both_personas else ["expert"]

            for persona in personas:
                for vote_idx in range(judge_config.votes_per_judge):
                    position = get_position(vote_idx)
                    task = self._single_judge_vote(
                        prompt, gemini_response, competitor_response,
                        judge_model, persona, vote_idx, position
                    )
                    tasks.append(task)

                    if judge_model not in self.progress.judge_statuses:
                        self.progress.judge_statuses[judge_model] = {"completed": 0, "total": 0}
                    self.progress.judge_statuses[judge_model]["total"] += 1

        results = await asyncio.gather(*tasks, return_exceptions=True)

        votes = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Judge error: {r}")
                self.progress.failures += 1
            else:
                votes.append(r)
                # Track for Kappa
                self.kappa_analyzer.add_vote(
                    prompt.prompt_id, r.judge_model, r.winner
                )
                # Update progress
                if r.judge_model in self.progress.judge_statuses:
                    self.progress.judge_statuses[r.judge_model]["completed"] += 1
                self._notify_progress()

        # Update Kappa in progress
        self.progress.current_kappa = self.kappa_analyzer.get_current_kappa()

        return votes

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
        batch_size: int = 10
    ) -> List[ComparisonResult]:
        """Run full evaluation with parallel processing."""
        self.progress.start_time = time.time()
        self.progress.total_prompts = len(prompts) * len(self.config.model_pairs)
        self.progress.phase = EvalPhase.GENERATION

        all_results = []

        for gemini_model, competitor_model in self.config.model_pairs:
            pair_key = f"{gemini_model}_vs_{competitor_model}"
            self.progress.pair_progress[pair_key] = {
                "completed": 0, "total": len(prompts),
                "gemini_wins": 0, "competitor_wins": 0, "ties": 0
            }

            for batch_start in range(0, len(prompts), batch_size):
                if self._shutdown_requested:
                    break

                batch = prompts[batch_start:batch_start + batch_size]

                self.progress.phase = EvalPhase.GENERATION
                response_pairs = await self._generate_responses_parallel(
                    batch, gemini_model, competitor_model
                )

                self.progress.phase = EvalPhase.JUDGING
                for prompt, gemini_resp, competitor_resp in response_pairs:
                    result = await self._process_comparison(
                        prompt, gemini_model, competitor_model,
                        gemini_resp, competitor_resp
                    )
                    all_results.append(result)

                    self.progress.completed_prompts += 1
                    self.progress.pair_progress[pair_key]["completed"] += 1

                    if result.aggregated.final_winner == "gemini":
                        self.progress.pair_progress[pair_key]["gemini_wins"] += 1
                    elif result.aggregated.final_winner == "competitor":
                        self.progress.pair_progress[pair_key]["competitor_wins"] += 1
                    else:
                        self.progress.pair_progress[pair_key]["ties"] += 1

                    await self.database.save_comparison(result)
                    self.progress.cost_spent = self._total_cost
                    self._update_projections()

                await self.checkpoint.save(all_results)
                self._notify_progress()

        # Generate failure summary at end
        self.failure_generator.save_report(self._total_api_calls)

        self.progress.phase = EvalPhase.COMPLETE
        self._notify_progress()

        return all_results

    async def _process_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> ComparisonResult:
        """Process single comparison with auto-loss handling."""
        # Auto-loss handling
        if gemini_response.is_error or gemini_response.is_refusal:
            aggregated = AggregatedResult(
                prompt_id=prompt.prompt_id,
                gemini_model=gemini_model,
                competitor_model=competitor_model,
                final_winner="competitor",
                gemini_wins=0, competitor_wins=1, ties=0, total_votes=1,
                judge_model_winners={},
                avg_quality_gemini=0, avg_quality_competitor=5,
                auto_loss_reason="gemini_error" if gemini_response.is_error else "gemini_refusal"
            )
            return ComparisonResult(
                prompt_id=prompt.prompt_id, prompt=prompt,
                gemini_model=gemini_model, competitor_model=competitor_model,
                gemini_response=gemini_response, competitor_response=competitor_response,
                votes=[], aggregated=aggregated, completed_at=time.time()
            )

        if competitor_response.is_error or competitor_response.is_refusal:
            aggregated = AggregatedResult(
                prompt_id=prompt.prompt_id,
                gemini_model=gemini_model,
                competitor_model=competitor_model,
                final_winner="gemini",
                gemini_wins=1, competitor_wins=0, ties=0, total_votes=1,
                judge_model_winners={},
                avg_quality_gemini=5, avg_quality_competitor=0,
                auto_loss_reason="competitor_error" if competitor_response.is_error else "competitor_refusal"
            )
            return ComparisonResult(
                prompt_id=prompt.prompt_id, prompt=prompt,
                gemini_model=gemini_model, competitor_model=competitor_model,
                gemini_response=gemini_response, competitor_response=competitor_response,
                votes=[], aggregated=aggregated, completed_at=time.time()
            )

        # Normal judging
        votes = await self._judge_with_kappa_tracking(
            prompt, gemini_response, competitor_response
        )
        aggregated = self.vote_aggregator.aggregate(
            prompt.prompt_id, gemini_model, competitor_model, votes
        )

        return ComparisonResult(
            prompt_id=prompt.prompt_id, prompt=prompt,
            gemini_model=gemini_model, competitor_model=competitor_model,
            gemini_response=gemini_response, competitor_response=competitor_response,
            votes=votes, aggregated=aggregated, completed_at=time.time()
        )

    def _update_projections(self):
        """Update ETA and cost projections."""
        if self.progress.completed_prompts > 0:
            elapsed = time.time() - self.progress.start_time
            rate = self.progress.completed_prompts / elapsed
            remaining = self.progress.total_prompts - self.progress.completed_prompts
            self.progress.estimated_remaining_seconds = remaining / rate if rate > 0 else 0
            self.progress.cost_projected = (
                self.progress.cost_spent / self.progress.completed_prompts
            ) * self.progress.total_prompts

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
        self._paused = True

    def request_resume(self):
        self._paused = False

    def request_shutdown(self):
        self._shutdown_requested = True
        self._paused = False
```

---

## 2. IMPROVED COHEN'S KAPPA WITH WEIGHTED KAPPA

```python
# src/analysis/statistics.py

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np
from scipy.stats import binomtest, chi2_contingency, norm
from itertools import combinations


@dataclass
class KappaResult:
    """Result of Cohen's Kappa calculation."""
    kappa: float
    interpretation: str
    observed_agreement: float
    expected_agreement: float
    judge_a: str
    judge_b: str
    n_comparisons: int
    standard_error: Optional[float] = None


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
    """Interpret kappa using Landis & Koch (1977)."""
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
) -> Tuple[float, float, float]:
    """
    Calculate Cohen's Kappa with observed/expected agreement.

    Returns:
        Tuple of (kappa, observed_agreement, expected_agreement)
    """
    if len(ratings_a) != len(ratings_b):
        raise ValueError("Rating lists must have same length")

    n = len(ratings_a)
    if n == 0:
        return (0.0, 0.0, 0.0)

    if categories is None:
        categories = list(set(ratings_a) | set(ratings_b))

    # Build confusion matrix
    confusion = {c1: {c2: 0 for c2 in categories} for c1 in categories}
    for ra, rb in zip(ratings_a, ratings_b):
        if ra in confusion and rb in confusion.get(ra, {}):
            confusion[ra][rb] += 1

    observed = sum(confusion[c][c] for c in categories) / n

    marginals_a = {c: sum(1 for r in ratings_a if r == c) / n for c in categories}
    marginals_b = {c: sum(1 for r in ratings_b if r == c) / n for c in categories}
    expected = sum(marginals_a[c] * marginals_b[c] for c in categories)

    if expected == 1.0:
        kappa = 1.0 if observed == 1.0 else 0.0
    else:
        kappa = (observed - expected) / (1 - expected)

    return (kappa, observed, expected)


def calculate_weighted_kappa(
    ratings_a: List[int],
    ratings_b: List[int],
    weight_type: str = "quadratic"
) -> float:
    """
    Calculate weighted Cohen's Kappa for ordinal data.

    Args:
        ratings_a: Numeric ratings from rater A
        ratings_b: Numeric ratings from rater B
        weight_type: "linear" or "quadratic"

    Returns:
        Weighted kappa coefficient
    """
    if len(ratings_a) != len(ratings_b):
        raise ValueError("Rating lists must have same length")

    n = len(ratings_a)
    if n == 0:
        return 0.0

    min_val = min(min(ratings_a), min(ratings_b))
    max_val = max(max(ratings_a), max(ratings_b))
    k = max_val - min_val + 1

    # Weight matrix
    weights = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if weight_type == "linear":
                weights[i, j] = 1 - abs(i - j) / (k - 1)
            else:  # quadratic
                weights[i, j] = 1 - ((i - j) ** 2) / ((k - 1) ** 2)

    # Observed and expected matrices
    observed = np.zeros((k, k))
    for ra, rb in zip(ratings_a, ratings_b):
        i, j = ra - min_val, rb - min_val
        observed[i, j] += 1
    observed /= n

    row_marginals = observed.sum(axis=1)
    col_marginals = observed.sum(axis=0)
    expected = np.outer(row_marginals, col_marginals)

    po = np.sum(weights * observed)
    pe = np.sum(weights * expected)

    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0

    return (po - pe) / (1 - pe)


def calculate_pairwise_kappa(
    judge_votes: Dict[str, List[str]],
    categories: List[str] = ["gemini", "competitor", "tie"]
) -> List[KappaResult]:
    """Calculate Cohen's Kappa for all judge pairs."""
    results = []
    judges = list(judge_votes.keys())

    for judge_a, judge_b in combinations(judges, 2):
        ratings_a = judge_votes[judge_a]
        ratings_b = judge_votes[judge_b]

        min_len = min(len(ratings_a), len(ratings_b))
        if min_len == 0:
            continue

        ratings_a = ratings_a[:min_len]
        ratings_b = ratings_b[:min_len]

        kappa, observed, expected = calculate_cohens_kappa(
            ratings_a, ratings_b, categories
        )

        # Standard error (approximate)
        se = np.sqrt((observed * (1 - observed)) / (min_len * (1 - expected) ** 2)) if min_len > 0 and expected < 1 else None

        results.append(KappaResult(
            kappa=kappa,
            interpretation=interpret_kappa(kappa),
            observed_agreement=observed,
            expected_agreement=expected,
            judge_a=judge_a,
            judge_b=judge_b,
            n_comparisons=min_len,
            standard_error=se
        ))

    return results


def calculate_fleiss_kappa(
    all_ratings: List[List[str]],
    categories: List[str] = ["gemini", "competitor", "tie"]
) -> FleisskKappaResult:
    """Calculate Fleiss' Kappa for multiple raters."""
    n_judges = len(all_ratings)
    if n_judges < 2:
        return FleisskKappaResult(
            kappa=1.0, interpretation="almost_perfect",
            observed_agreement=1.0, expected_agreement=1.0,
            n_judges=n_judges, n_comparisons=0
        )

    n_items = min(len(r) for r in all_ratings)
    if n_items == 0:
        return FleisskKappaResult(
            kappa=0.0, interpretation="poor",
            observed_agreement=0.0, expected_agreement=0.0,
            n_judges=n_judges, n_comparisons=0
        )

    n_cats = len(categories)
    cat_to_idx = {c: i for i, c in enumerate(categories)}

    rating_matrix = np.zeros((n_items, n_cats))
    for item_idx in range(n_items):
        for judge_ratings in all_ratings:
            if item_idx < len(judge_ratings):
                rating = judge_ratings[item_idx]
                if rating in cat_to_idx:
                    rating_matrix[item_idx, cat_to_idx[rating]] += 1

    n = n_judges
    P_i = np.zeros(n_items)
    for i in range(n_items):
        row = rating_matrix[i, :]
        P_i[i] = (np.sum(row ** 2) - n) / (n * (n - 1)) if n > 1 else 0

    P_bar = np.mean(P_i)
    p_j = np.sum(rating_matrix, axis=0) / (n_items * n)
    P_e = np.sum(p_j ** 2)

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
    """Analyzer for inter-judge agreement with persistence."""

    def __init__(self, min_samples: int = 5):
        self.votes_by_judge: Dict[str, List[str]] = {}
        self.votes_by_comparison: Dict[str, Dict[str, str]] = {}
        self.min_samples = min_samples  # Configurable threshold

    def add_vote(self, comparison_id: str, judge_model: str, winner: str):
        """Add a single vote."""
        if judge_model not in self.votes_by_judge:
            self.votes_by_judge[judge_model] = []

        if comparison_id not in self.votes_by_comparison:
            self.votes_by_comparison[comparison_id] = {}

        if judge_model not in self.votes_by_comparison[comparison_id]:
            self.votes_by_judge[judge_model].append(winner)
            self.votes_by_comparison[comparison_id][judge_model] = winner

    def get_current_kappa(self) -> Optional[float]:
        """Get current Fleiss' Kappa."""
        if len(self.votes_by_judge) < 2:
            return None

        all_ratings = list(self.votes_by_judge.values())
        min_len = min(len(r) for r in all_ratings)

        if min_len < self.min_samples:
            return None

        result = calculate_fleiss_kappa([r[:min_len] for r in all_ratings])
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
                    "interpretation": k.interpretation,
                    "standard_error": k.standard_error
                }
                for k in pairwise
            ],
            "n_judges": len(self.votes_by_judge),
            "n_comparisons": len(self.votes_by_comparison)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "votes_by_judge": self.votes_by_judge,
            "votes_by_comparison": self.votes_by_comparison,
            "min_samples": self.min_samples
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterJudgeAgreementAnalyzer":
        """Deserialize from persistence."""
        analyzer = cls(min_samples=data.get("min_samples", 5))
        analyzer.votes_by_judge = data.get("votes_by_judge", {})
        analyzer.votes_by_comparison = data.get("votes_by_comparison", {})
        return analyzer


def wilson_ci(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate Wilson score confidence interval."""
    if total == 0:
        return (0.0, 1.0)

    z = norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / total
    n = total

    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denominator
    margin = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denominator

    return (max(0.0, center - margin), min(1.0, center + margin))
```

---

## 3. IMPROVED EVALCONFIG WITH ALL MISSING FIELDS

```python
# src/config/presets.py

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum


# Model pairs
PRO_PAIRS: List[Tuple[str, str]] = [
    ("google/gemini-3.0-pro", "openai/gpt-5.2"),
    ("google/gemini-3.0-pro", "anthropic/claude-opus-4.5"),
    ("google/gemini-3.0-pro", "x-ai/grok-4.1"),
    ("google/gemini-3.0-pro", "moonshot/kimi-k2"),
]

FLASH_PAIRS: List[Tuple[str, str]] = [
    ("google/gemini-3.0-flash", "openai/gpt-4.1"),
    ("google/gemini-3.0-flash", "anthropic/claude-sonnet-4"),
    ("google/gemini-3.0-flash", "mistral/mistral-medium"),  # Added for "other flash-tier"
    ("google/gemini-3.0-flash", "cohere/command-r-plus"),   # Added for "other flash-tier"
]

ALL_PAIRS = PRO_PAIRS + FLASH_PAIRS

ALL_JUDGES = [
    "anthropic/claude-opus-4.5",
    "openai/gpt-5.2",
    "google/gemini-3.0-pro",
]


@dataclass
class JudgeConfig:
    """Configuration for judge models."""
    models: List[str] = field(default_factory=lambda: ALL_JUDGES.copy())
    votes_per_judge: int = 5
    use_both_personas: bool = True
    persona_mode: str = "both"  # "both", "expert", "recipient"

    def get_personas(self) -> List[str]:
        """Get list of personas to use based on config."""
        if self.use_both_personas:
            return ["expert", "recipient"]
        elif self.persona_mode == "expert":
            return ["expert"]
        elif self.persona_mode == "recipient":
            return ["recipient"]
        return ["expert"]


@dataclass
class EvalConfig:
    """Complete evaluation configuration with all options."""
    # Basic config
    run_name: str = "evaluation"
    num_prompts: int = 500
    model_pairs: List[Tuple[str, str]] = field(default_factory=lambda: PRO_PAIRS.copy())
    judge_config: JudgeConfig = field(default_factory=JudgeConfig)

    # Filtering options
    occupation_filter: Optional[List[str]] = None  # O*NET codes like ["11-*", "13-1111"]
    industry_filter: Optional[List[str]] = None    # NAICS codes like ["54", "62"]
    job_zone_filter: Optional[List[int]] = None    # Job zones 1-5

    # Range filters (new)
    formality_min: int = 1
    formality_max: int = 5
    age_min: int = 18
    age_max: int = 80

    # Sampling limits (new)
    max_per_occupation: Optional[int] = None
    max_per_industry: Optional[int] = None
    random_seed: Optional[int] = None

    # Stratification
    stratify_by_job_zone: bool = True
    stratify_by_soc_group: bool = True

    def copy(self) -> "EvalConfig":
        """Create a deep copy of the config."""
        return EvalConfig(
            run_name=self.run_name,
            num_prompts=self.num_prompts,
            model_pairs=list(self.model_pairs),
            judge_config=JudgeConfig(
                models=list(self.judge_config.models),
                votes_per_judge=self.judge_config.votes_per_judge,
                use_both_personas=self.judge_config.use_both_personas,
                persona_mode=self.judge_config.persona_mode,
            ),
            occupation_filter=list(self.occupation_filter) if self.occupation_filter else None,
            industry_filter=list(self.industry_filter) if self.industry_filter else None,
            job_zone_filter=list(self.job_zone_filter) if self.job_zone_filter else None,
            formality_min=self.formality_min,
            formality_max=self.formality_max,
            age_min=self.age_min,
            age_max=self.age_max,
            max_per_occupation=self.max_per_occupation,
            max_per_industry=self.max_per_industry,
            random_seed=self.random_seed,
            stratify_by_job_zone=self.stratify_by_job_zone,
            stratify_by_soc_group=self.stratify_by_soc_group,
        )


# 10 Prepackaged Presets
PRESETS: Dict[int, EvalConfig] = {
    1: EvalConfig(
        run_name="sanity_check",
        num_prompts=5,
        model_pairs=[PRO_PAIRS[0]],
        judge_config=JudgeConfig(models=[ALL_JUDGES[0]], votes_per_judge=1, use_both_personas=False),
    ),
    2: EvalConfig(
        run_name="smoke_test",
        num_prompts=20,
        model_pairs=[PRO_PAIRS[0]],
        judge_config=JudgeConfig(models=[ALL_JUDGES[0]], votes_per_judge=3, use_both_personas=False),
    ),
    3: EvalConfig(
        run_name="dev_iteration",
        num_prompts=50,
        model_pairs=PRO_PAIRS[:2],
        judge_config=JudgeConfig(models=ALL_JUDGES[:2], votes_per_judge=3),
    ),
    4: EvalConfig(
        run_name="quick_sample",
        num_prompts=100,
        model_pairs=PRO_PAIRS[:2],
        judge_config=JudgeConfig(models=ALL_JUDGES[:2], votes_per_judge=5),
    ),
    5: EvalConfig(
        run_name="light_eval",
        num_prompts=200,
        model_pairs=PRO_PAIRS[:3],
        judge_config=JudgeConfig(models=ALL_JUDGES, votes_per_judge=3),
    ),
    6: EvalConfig(
        run_name="standard_eval",
        num_prompts=500,
        model_pairs=PRO_PAIRS,
        judge_config=JudgeConfig(models=ALL_JUDGES, votes_per_judge=5),
    ),
    7: EvalConfig(
        run_name="thorough_eval",
        num_prompts=1000,
        model_pairs=PRO_PAIRS,
        judge_config=JudgeConfig(models=ALL_JUDGES, votes_per_judge=5),
    ),
    8: EvalConfig(
        run_name="comprehensive",
        num_prompts=2000,
        model_pairs=ALL_PAIRS,
        judge_config=JudgeConfig(models=ALL_JUDGES, votes_per_judge=5),
    ),
    9: EvalConfig(
        run_name="deep_dive",
        num_prompts=5000,
        model_pairs=ALL_PAIRS,
        judge_config=JudgeConfig(models=ALL_JUDGES, votes_per_judge=5),
    ),
    10: EvalConfig(
        run_name="full_kaboodle",
        num_prompts=10000,
        model_pairs=ALL_PAIRS,
        judge_config=JudgeConfig(models=ALL_JUDGES, votes_per_judge=5),
    ),
}
```

---

## 4. IMPROVED CLI WITH VALIDATION

```python
# src/cli.py (key improvements only)

import typer
from typing import Optional, List
from pathlib import Path
from enum import Enum

from .config.presets import PRESETS, EvalConfig, JudgeConfig, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES

app = typer.Typer(name="gemini-writing-eval")


class ModelTier(str, Enum):
    PRO = "pro"
    FLASH = "flash"
    BOTH = "both"


class JudgePersona(str, Enum):
    BOTH = "both"
    EXPERT = "expert"
    RECIPIENT = "recipient"


def validate_concurrency(value: int) -> int:
    """Validate concurrency is within allowed range."""
    if value < 10 or value > 50:
        raise typer.BadParameter(f"Concurrency must be 10-50, got {value}")
    return value


@app.command()
def run(
    preset: int = typer.Option(6, "--preset", "-p", min=1, max=10),
    tier: ModelTier = typer.Option(ModelTier.BOTH, "--tier", "-t"),
    persona: JudgePersona = typer.Option(JudgePersona.BOTH, "--persona"),
    job_zones: Optional[str] = typer.Option(None, "--job-zones"),
    formality_range: Optional[str] = typer.Option(None, "--formality-range"),
    age_range: Optional[str] = typer.Option(None, "--age-range"),
    occupation_limit: Optional[int] = typer.Option(None, "--occupation-limit"),
    industry_limit: Optional[int] = typer.Option(None, "--industry-limit"),
    concurrency: int = typer.Option(
        25, "--concurrency", "-c",
        callback=lambda v: validate_concurrency(v) if v else 25
    ),
    # ... other options
):
    """Run the Gemini writing evaluation."""
    # Use copy() method instead of model_copy()
    config = PRESETS[preset].copy()

    # Apply tier filter
    if tier == ModelTier.PRO:
        config.model_pairs = [p for p in config.model_pairs if "pro" in p[0].lower()]
    elif tier == ModelTier.FLASH:
        config.model_pairs = [p for p in config.model_pairs if "flash" in p[0].lower()]

    # Apply persona configuration correctly
    config.judge_config.use_both_personas = (persona == JudgePersona.BOTH)
    config.judge_config.persona_mode = persona.value

    # Apply range filters with validation
    if job_zones:
        try:
            zones = [int(z.strip()) for z in job_zones.split(",")]
            if not all(1 <= z <= 5 for z in zones):
                raise typer.BadParameter("Job zones must be 1-5")
            config.job_zone_filter = zones
        except ValueError:
            raise typer.BadParameter("Job zones must be comma-separated integers")

    if formality_range:
        try:
            if "-" in formality_range:
                low, high = map(int, formality_range.split("-"))
            else:
                low = high = int(formality_range)
            if not (1 <= low <= 5 and 1 <= high <= 5):
                raise typer.BadParameter("Formality must be 1-5")
            config.formality_min, config.formality_max = low, high
        except ValueError:
            raise typer.BadParameter("Invalid formality range format")

    if age_range:
        try:
            if "-" in age_range:
                low, high = map(int, age_range.split("-"))
            else:
                low = high = int(age_range)
            if not (18 <= low <= 80 and 18 <= high <= 80):
                raise typer.BadParameter("Age must be 18-80")
            config.age_min, config.age_max = low, high
        except ValueError:
            raise typer.BadParameter("Invalid age range format")

    config.max_per_occupation = occupation_limit
    config.max_per_industry = industry_limit

    # Continue with execution...
```

---

## 5. IMPROVED NAME GENERATOR WITH GENDER-APPROPRIATE PREFIXES

```python
# src/data/name_generator.py

import random
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class NameFormality(str, Enum):
    VERY_INFORMAL = "very_informal"
    INFORMAL = "informal"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    VERY_FORMAL = "very_formal"


@dataclass
class GeneratedName:
    """A generated name with formality representations."""
    first_name: str
    last_name: str
    middle_initial: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
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
        if style == "initial":
            return f"{self.first_name[0].lower()}{self.last_name.lower()}@{company_domain}"
        elif style == "nickname" and self.nickname:
            return f"{self.nickname.lower()}@{company_domain}"
        return f"{self.first_name.lower()}.{self.last_name.lower()}@{company_domain}"


class NameGenerator:
    """Generate diverse names with proper gender-appropriate prefixes."""

    # Gender-appropriate prefixes
    PREFIXES_BY_GENDER = {
        "male": ["Mr.", "Dr."],
        "female": ["Ms.", "Dr."],
    }

    # Professional titles that override gender prefixes
    PROFESSIONAL_TITLES = {
        "doctor": "Dr.",
        "professor": "Prof.",
        "reverend": "Rev.",
    }

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
        "hispanic": ["Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez"],
        "asian": ["Wang", "Li", "Zhang", "Chen", "Tanaka", "Kim", "Patel", "Singh"],
        "african_american": ["Washington", "Jefferson", "Jackson", "Robinson", "Harris", "Lewis"]
    }

    NICKNAMES = {
        "Michael": "Mike", "William": "Will", "Robert": "Bob",
        "James": "Jim", "Richard": "Rick", "Thomas": "Tom",
        "Jennifer": "Jen", "Elizabeth": "Liz", "Katherine": "Kate", "Rebecca": "Becca",
    }

    SUFFIXES = ["Jr.", "III", "IV", "PhD", "MD", "JD", "MBA"]

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate(
        self,
        ethnicity: Optional[str] = None,
        gender: Optional[str] = None,
        job_title: Optional[str] = None,
        skill_level: Optional[str] = None,
        include_prefix: bool = False,
        include_suffix: bool = False,
    ) -> GeneratedName:
        """Generate a realistic name with proper gender handling."""
        # Select ethnicity
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
        middle_initial = self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") if self.rng.random() > 0.5 else None
        nickname = self.NICKNAMES.get(first_name)

        # Determine prefix with proper gender handling
        prefix = None
        if include_prefix:
            # Check for professional titles in job_title
            if job_title:
                job_lower = job_title.lower()
                for title_key, title_prefix in self.PROFESSIONAL_TITLES.items():
                    if title_key in job_lower:
                        prefix = title_prefix
                        break

            # Fall back to gender-appropriate prefix
            if not prefix and skill_level in ["senior", "executive"]:
                gender_prefixes = self.PREFIXES_BY_GENDER.get(gender, ["Mr."])
                # Executives more likely to be Dr.
                if skill_level == "executive" and self.rng.random() > 0.7:
                    prefix = "Dr."
                else:
                    prefix = self.rng.choice(gender_prefixes)

        # Suffix
        suffix = None
        if include_suffix and skill_level == "executive" and self.rng.random() > 0.85:
            suffix = self.rng.choice(self.SUFFIXES)

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
        """Generate and format name for formality level."""
        formality_map = {
            1: NameFormality.VERY_INFORMAL,
            2: NameFormality.INFORMAL,
            3: NameFormality.NEUTRAL,
            4: NameFormality.FORMAL,
            5: NameFormality.VERY_FORMAL,
        }
        formality = formality_map.get(formality_level, NameFormality.NEUTRAL)

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

## 6. SENSITIVE TOPIC WIN RATE ANALYSIS

```python
# src/analysis/sensitive_topic_analysis.py

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .statistics import wilson_ci


@dataclass
class SensitiveTopicStats:
    """Statistics for a sensitive topic category."""
    topic: str
    total_comparisons: int
    gemini_wins: int
    competitor_wins: int
    ties: int
    win_rate: float
    ci_lower: float
    ci_upper: float


class SensitiveTopicAnalyzer:
    """
    Analyze win rates separately for sensitive vs routine tasks.

    Per PROMPT.md: "Track win rates separately for sensitive vs routine tasks"
    """

    SENSITIVE_TOPICS = [
        "HR_ISSUES",
        "LEGAL",
        "BAD_NEWS",
        "CONFIDENTIAL",
        "CONFLICT",
    ]

    def __init__(self):
        self.comparisons_by_topic: Dict[str, List[Dict]] = defaultdict(list)
        self.routine_comparisons: List[Dict] = []

    def add_comparison(
        self,
        prompt_id: str,
        winner: str,  # "gemini", "competitor", "tie"
        sensitive_topics: List[str],
        model_pair: str,
        quality_gemini: float,
        quality_competitor: float
    ):
        """Add a comparison result for tracking."""
        comparison_data = {
            "prompt_id": prompt_id,
            "winner": winner,
            "model_pair": model_pair,
            "quality_gemini": quality_gemini,
            "quality_competitor": quality_competitor,
        }

        if sensitive_topics:
            for topic in sensitive_topics:
                self.comparisons_by_topic[topic].append(comparison_data)
        else:
            self.routine_comparisons.append(comparison_data)

    def get_topic_stats(self, topic: str) -> Optional[SensitiveTopicStats]:
        """Get statistics for a specific sensitive topic."""
        comparisons = self.comparisons_by_topic.get(topic, [])
        if not comparisons:
            return None

        total = len(comparisons)
        gemini_wins = sum(1 for c in comparisons if c["winner"] == "gemini")
        competitor_wins = sum(1 for c in comparisons if c["winner"] == "competitor")
        ties = total - gemini_wins - competitor_wins

        decided = gemini_wins + competitor_wins
        win_rate = gemini_wins / decided if decided > 0 else 0.5
        ci_low, ci_high = wilson_ci(gemini_wins, decided) if decided > 0 else (0, 1)

        return SensitiveTopicStats(
            topic=topic,
            total_comparisons=total,
            gemini_wins=gemini_wins,
            competitor_wins=competitor_wins,
            ties=ties,
            win_rate=win_rate,
            ci_lower=ci_low,
            ci_upper=ci_high
        )

    def get_routine_stats(self) -> SensitiveTopicStats:
        """Get statistics for routine (non-sensitive) tasks."""
        comparisons = self.routine_comparisons
        total = len(comparisons)
        gemini_wins = sum(1 for c in comparisons if c["winner"] == "gemini")
        competitor_wins = sum(1 for c in comparisons if c["winner"] == "competitor")
        ties = total - gemini_wins - competitor_wins

        decided = gemini_wins + competitor_wins
        win_rate = gemini_wins / decided if decided > 0 else 0.5
        ci_low, ci_high = wilson_ci(gemini_wins, decided) if decided > 0 else (0, 1)

        return SensitiveTopicStats(
            topic="ROUTINE",
            total_comparisons=total,
            gemini_wins=gemini_wins,
            competitor_wins=competitor_wins,
            ties=ties,
            win_rate=win_rate,
            ci_lower=ci_low,
            ci_upper=ci_high
        )

    def get_full_report(self) -> Dict[str, Any]:
        """Get complete sensitive topic analysis."""
        report = {
            "routine": self.get_routine_stats().__dict__ if self.routine_comparisons else None,
            "by_sensitive_topic": {},
            "summary": {
                "total_sensitive": sum(len(c) for c in self.comparisons_by_topic.values()),
                "total_routine": len(self.routine_comparisons),
            }
        }

        for topic in self.SENSITIVE_TOPICS:
            stats = self.get_topic_stats(topic)
            if stats:
                report["by_sensitive_topic"][topic] = stats.__dict__

        # Calculate if Gemini does better/worse on sensitive topics
        all_sensitive = []
        for comparisons in self.comparisons_by_topic.values():
            all_sensitive.extend(comparisons)

        if all_sensitive and self.routine_comparisons:
            sensitive_wins = sum(1 for c in all_sensitive if c["winner"] == "gemini")
            sensitive_decided = sum(1 for c in all_sensitive if c["winner"] != "tie")
            routine_wins = sum(1 for c in self.routine_comparisons if c["winner"] == "gemini")
            routine_decided = sum(1 for c in self.routine_comparisons if c["winner"] != "tie")

            if sensitive_decided > 0 and routine_decided > 0:
                sensitive_rate = sensitive_wins / sensitive_decided
                routine_rate = routine_wins / routine_decided
                report["summary"]["sensitive_vs_routine_delta"] = sensitive_rate - routine_rate
                report["summary"]["gemini_better_on_sensitive"] = sensitive_rate > routine_rate

        return report
```

---

## SUMMARY OF IMPROVEMENTS

This critique and improved implementation addresses the following issues from gap_fix_draft_2.md:

### Critical Fixes

1. **EvalPhase enum ordering** - Changed from string values to integer values for proper comparison
2. **Semaphore initialization** - Added lazy initialization to avoid asyncio context issues
3. **Circuit breaker integration** - Added per-model circuit breakers
4. **Response caching** - Prevents regenerating successful responses on retry
5. **Failure tracking integration** - EvaluationEngine now uses FailureSummaryGenerator
6. **TaskGroup support** - Added Python 3.11+ TaskGroup with fallback to gather
7. **Defensive coding** - `_build_system_prompt` uses getattr with defaults

### Statistical Improvements

1. **Weighted Kappa** - Added for ordinal data analysis
2. **Standard error** - Added to KappaResult for confidence assessment
3. **Persistence** - InterJudgeAgreementAnalyzer can be serialized/deserialized
4. **Configurable min_samples** - Threshold is now configurable

### Configuration Improvements

1. **EvalConfig extensions** - Added formality_min/max, age_min/max, max_per_occupation, max_per_industry
2. **copy() method** - Proper deep copy instead of model_copy()
3. **JudgeConfig.persona_mode** - Proper attribute instead of private _persona_mode
4. **Flash-tier models** - Added Mistral and Cohere for "other flash-tier"

### CLI Improvements

1. **Input validation** - Proper validation for concurrency, job zones, age/formality ranges
2. **Error messages** - Clear BadParameter messages
3. **Tier handling** - Correct filtering logic

### Name Generator Improvements

1. **Gender-appropriate prefixes** - Mr./Ms. based on gender
2. **Professional titles** - Dr., Prof., Rev. from job titles
3. **Cleaner fallback logic** - Proper prefix selection cascade

### New Components

1. **SensitiveTopicAnalyzer** - Separate win rate tracking for sensitive vs routine tasks (was missing)

### Remaining Items Not Addressed

The following would require additional implementation beyond the scope of this critique:

1. **Full TUI refactoring** - The dashboard needs complete async integration with Textual
2. **Database query methods** - `query_comparisons()` and `get_comparison_detail()` need full implementation
3. **Statistics panel modal** - The "s" key action needs a full screen implementation

This improved implementation is more robust, handles edge cases properly, and fully addresses the gaps identified in gap_analysis.md.
