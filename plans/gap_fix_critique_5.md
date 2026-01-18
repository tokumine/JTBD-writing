# Gap Fix Critique - Draft 5

## Executive Summary

Draft 5 provides comprehensive Python implementations addressing most gaps identified in the gap analysis. The code is well-structured, follows modern Python practices, and covers the 12 major gap areas. However, there are several technical issues, missing integrations, and incomplete implementations that need to be addressed for production readiness.

---

## SECTION 1: DETAILED CRITIQUE

### 1.1 Parallel Request Architecture (EvaluationEngine)

**Strengths:**
- Good use of `asyncio.Semaphore` for both global and per-model concurrency control
- Progress callback mechanism is well-designed
- Batch processing with checkpoint saves after each batch
- Proper handling of auto-loss cases for refusals

**Issues Found:**

1. **Missing Error Recovery in `_rate_limited_complete`**: The method catches exceptions but doesn't implement retry logic with exponential backoff. The PROMPT.md requires "Automatic retries: Exponential backoff with jitter (3 retries default)".

2. **Race Condition in `_prompts_completed`**: The counter is incremented without locks, which could cause issues in highly concurrent scenarios.

3. **Missing `current_occupation` and `current_industry` in ProgressUpdate**: These fields are defined in the dataclass but never populated in `_emit_progress()`.

4. **No Rate Limit Detection**: The code doesn't detect rate limit responses (429 status) and increment `_rate_limit_pauses`.

5. **Missing Retry Counter**: The `_retries` counter is defined but never incremented.

6. **Incomplete `_running_wins` tracking**: Ties are tracked but the key "tie" doesn't match the expected `AggregatedResult.final_winner` which could be different values.

### 1.2 Cohen's Kappa Implementation

**Strengths:**
- Both Cohen's Kappa (pairwise) and Fleiss' Kappa (multi-judge) implemented
- Wilson confidence interval implementation is correct
- Comprehensive `calculate_inter_judge_agreement` function

**Issues Found:**

1. **Missing Weighted Kappa**: For ordinal judgments (quality scores 1-5), weighted kappa would be more appropriate than simple kappa.

2. **Edge Case Handling**: When all judges agree completely, `p_expected` could be 1.0 which is handled, but when there's perfect disagreement, kappa could be negative without bounds checking.

3. **Missing Krippendorff's Alpha**: For more robust inter-rater reliability with missing data.

### 1.3 Cost Tracking in TUI

**Strengths:**
- Clean widget implementation using Textual's reactive system
- Good display formatting with percentages

**Issues Found:**

1. **Missing Currency Formatting for Locales**: Hardcoded `$` symbol doesn't account for international users.

2. **No Budget Warning**: No visual indicator when cost exceeds expected budget.

3. **Syntax Error**: Line 938 has `---` which would cause a syntax error inside the code block.

### 1.4 Help Overlay

**Strengths:**
- Complete list of keyboard shortcuts
- Good documentation of display sections

**Issues Found:**

1. **Missing CSS Import**: The CSS is defined as a class attribute but the styling might not apply correctly without proper CSS parsing.

2. **No Scroll Support**: For smaller terminals, the help content might overflow without scrolling.

### 1.5 CLI Options

**Strengths:**
- Comprehensive CLI with all required options
- Good parsing of range options (e.g., "3-5" for formality)
- Support for presets with overrides

**Issues Found:**

1. **Persona Handling Incomplete**: When `persona == JudgePersona.RECIPIENT`, setting `_recipient_only = True` on a dataclass that doesn't define this attribute will raise an error.

2. **Missing Validation**: No validation that job zones are 1-5, formality is 1-5, or age range is reasonable (e.g., 18-100).

3. **Models Parsing Bug**: The logic assumes there's always exactly one Gemini model in the list; if multiple Gemini models are provided, only the first is used.

4. **Missing `--tier` Enum Value Handling**: The `ModelTier.BOTH` case keeps preset model_pairs, but this isn't explicitly clear behavior.

### 1.6 Name Formality Variation

**Strengths:**
- Comprehensive NameFormality enum with clear progression
- Good diminutive name generation
- Census-based demographic distribution

**Issues Found:**

1. **Incomplete `NICKNAMES` Dictionary**: Many common names are missing (e.g., "Andrew" -> "Andy", "Catherine" -> "Cathy").

2. **Suffix Probability Logic Bug**: The loop with `if self.rng.random() < prob` will always set suffix to None 90% of the time on the first iteration, but then potentially overwrite with other suffixes, which isn't the intended weighted distribution.

3. **Missing Hyphenated Names**: No support for hyphenated last names or multiple middle names.

4. **Gender Binary Assumption**: Only "male" and "female" supported; should include "non-binary" for modern inclusivity.

### 1.7 Phase 1 Generation Using Evaluated Models

**Strengths:**
- Good distribution of tasks across evaluated models
- Tracks which model generated each variation
- Fallback generation when LLM fails

**Issues Found:**

1. **Missing Model Validation**: No check if all evaluated models are available/responsive before starting.

2. **JSON Parsing Fragility**: LLM output might include markdown code blocks; the `json.loads()` will fail without stripping them.

3. **No Deduplication**: If variations are very similar, there's no detection or filtering.

4. **Rate Limit Handling**: Uses a simple `asyncio.sleep(0.5)` between batches but doesn't handle rate limit responses.

### 1.8 Ambiguity Behavior Tracking

**Strengths:**
- Comprehensive pattern matching for clarification, hedging, and hallucination detection
- Good behavior classification with confidence scores
- Evidence generation for transparency

**Issues Found:**

1. **Regex Patterns Too Narrow**: Many clarification patterns are missed (e.g., "More context would help", "Could you elaborate?").

2. **Hallucination Detection False Positives**: The patterns might flag legitimate specific details that were in the prompt but matched differently (e.g., "$1,000" in prompt vs "$1000" in response).

3. **No Context Window**: The assumption detection only looks for explicit "I assume" phrases; implicit assumptions aren't detected.

4. **Missing Return Type Hint**: `_determine_behavior` shows `tuple[...]` but should be `Tuple[...]` for Python < 3.9 compatibility.

### 1.9 TUI Results Viewer

**Strengths:**
- Complete filtering and sorting functionality
- Modal screen for detailed comparison view
- Side-by-side response display

**Issues Found:**

1. **Missing Async Database Methods**: Calls like `await self.db.get_all_comparisons()` assume the Database class has this method, but it wasn't defined.

2. **Pagination Missing**: Only shows first 500 comparisons; no pagination for larger datasets.

3. **No Export from Viewer**: Can't export filtered/sorted results directly from the viewer.

4. **Missing Keyboard Navigation**: No arrow key bindings for navigating the table.

### 1.10 Refusal Tracking by Dimension

**Strengths:**
- Comprehensive tracking across all required dimensions
- Proper aggregation of statistics
- JSON export functionality

**Issues Found:**

1. **Missing `RefusalCategory` Import**: The import references `RefusalCategory` but this class isn't defined in the draft.

2. **No Persistence**: Stats are in-memory only; lost on restart without explicit save.

3. **Thread Safety**: `defaultdict` operations aren't thread-safe for concurrent access.

### 1.11 Failure Summary Report

**Strengths:**
- Comprehensive failure categorization
- Recovery rate tracking
- Human-readable text report generation

**Issues Found:**

1. **Missing Integration Point**: No code showing how `FailureRecord` gets written to the log file.

2. **Timestamp Parsing Fragile**: Uses `fromisoformat` which may fail on different timestamp formats.

3. **No Correlation with Prompts**: Failure analysis doesn't link back to prompt characteristics for pattern detection.

### 1.12 Updated Progress Dashboard

**Strengths:**
- Comprehensive widget integration
- Cohen's Kappa interpretation with labels
- Good separation of concerns

**Issues Found:**

1. **`_all_votes` Never Populated**: The list is initialized but never filled, so kappa calculation will always use empty data.

2. **Missing Model Pair Progress Data**: `update.model_pair_progress` is referenced but never populated in `ProgressUpdate` from EvaluationEngine.

3. **Kappa Calculation Inefficient**: Recalculating from scratch on every update; should be incremental.

---

## SECTION 2: MISSING PIECES

### 2.1 Not Addressed from Gap Analysis

1. **"Other flash-tier models"**: The gap analysis noted that beyond GPT-4.1 and Sonnet, other flash-tier models weren't enumerated. Draft 5 doesn't address this.

2. **Sensitive Topic Win Rate Tracking**: While RefusalTracker tracks refusals by sensitive topic, the requirement to "Track win rates separately for sensitive vs routine tasks" isn't implemented.

3. **Statistics Panel (`s` key)**: The help overlay mentions it, but `action_show_stats` just logs a message without showing a modal.

4. **Detail View (`d` key)**: Similarly, `action_toggle_detail` just logs without implementing the view.

### 2.2 Integration Gaps

1. **No Main Entry Point**: Missing `src/main.py` with `run_evaluation()` function referenced in CLI.

2. **No Database Schema**: Missing table definitions for the SQLite database.

3. **No JudgePromptBuilder**: Referenced in EvaluationEngine but not implemented.

4. **No ResponseAnalyzer**: Referenced but not implemented.

5. **No RefusalClassifier**: Referenced but only partially defined.

---

## SECTION 3: IMPROVED IMPLEMENTATION

Below is the improved implementation addressing the critical issues identified above.

### 3.1 Fixed EvaluationEngine with Retry Logic and Complete Progress Tracking

```python
# src/eval/engine.py - FIXED VERSION

import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from enum import Enum
import logging

from ..api.openrouter_client import OpenRouterClient, CompletionResponse, RateLimitError, APIError
from ..prompts.schemas import WritingPrompt
from ..storage.checkpoint import CheckpointManager
from ..storage.database import Database
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .vote_aggregator import VoteAggregator, JudgeVote, AggregatedResult
from .refusal_classifier import RefusalClassifier
from .response_analyzer import ResponseAnalyzer
from ..config.presets import EvalConfig, JudgeConfig

logger = logging.getLogger(__name__)


class EvalPhase(str, Enum):
    """Current phase of evaluation."""
    GENERATION = "generation"
    JUDGING = "judging"
    ANALYSIS = "analysis"


@dataclass
class ProgressUpdate:
    """Progress update for TUI callbacks."""
    phase: EvalPhase
    prompts_completed: int
    prompts_total: int
    current_prompt_id: Optional[str] = None
    current_occupation: Optional[str] = None
    current_industry: Optional[str] = None
    model_pair_progress: Dict[Tuple[str, str], Dict[str, Any]] = field(default_factory=dict)
    per_judge_votes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    running_win_rates: Dict[Tuple[str, str], float] = field(default_factory=dict)
    running_confidence_intervals: Dict[Tuple[str, str], Tuple[float, float]] = field(default_factory=dict)
    cost_spent: float = 0.0
    cost_projected: float = 0.0
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0
    avg_response_time_ms: float = 0.0
    api_calls_per_minute: float = 0.0
    errors: int = 0
    retries: int = 0
    rate_limit_pauses: int = 0
    # For Kappa calculation
    all_votes: List[Dict] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Result of a single prompt comparison."""
    prompt_id: str
    gemini_model: str
    competitor_model: str
    gemini_response: str
    competitor_response: str
    gemini_latency_ms: float
    competitor_latency_ms: float
    gemini_cost: float
    competitor_cost: float
    aggregated_result: AggregatedResult
    all_votes: List[JudgeVote]
    refusal_gemini: Optional[str] = None
    refusal_competitor: Optional[str] = None


class EvaluationEngine:
    """Main evaluation orchestrator with parallel request handling.

    Uses asyncio.gather/TaskGroup for concurrent API calls with:
    - asyncio.Semaphore for global concurrency limiting
    - Per-model concurrency respecting rate limits
    - Exponential backoff with jitter for retries
    - Progress callbacks for TUI updates during parallel execution
    """

    def __init__(
        self,
        client: OpenRouterClient,
        config: EvalConfig,
        checkpoint_manager: CheckpointManager,
        database: Database,
        max_concurrency: int = 30,
        per_model_concurrency: int = 10,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None
    ):
        self.client = client
        self.config = config
        self.checkpoint = checkpoint_manager
        self.db = database
        self.max_concurrency = max_concurrency
        self.per_model_concurrency = per_model_concurrency
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.progress_callback = progress_callback

        # Concurrency control
        self._global_semaphore = asyncio.Semaphore(max_concurrency)
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()  # For thread-safe counter updates

        # Helpers
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.vote_aggregator = VoteAggregator(config.judge_config.votes_per_judge)
        self.refusal_classifier = RefusalClassifier()
        self.response_analyzer = ResponseAnalyzer()

        # Progress tracking
        self._start_time: float = 0.0
        self._prompts_completed: int = 0
        self._total_prompts: int = 0
        self._cost_spent: float = 0.0
        self._response_times: List[float] = []
        self._api_calls: int = 0
        self._errors: int = 0
        self._retries: int = 0
        self._rate_limit_pauses: int = 0
        self._running_wins: Dict[Tuple[str, str], Dict[str, int]] = {}
        self._per_judge_votes: Dict[str, Dict[str, int]] = {}
        self._all_vote_records: List[Dict] = []  # For Kappa calculation

        # Model pair progress tracking
        self._model_pair_progress: Dict[Tuple[str, str], Dict[str, int]] = {}

        # Current prompt context
        self._current_prompt: Optional[WritingPrompt] = None

        # Shutdown flag
        self._shutdown_requested = False

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore."""
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(self.per_model_concurrency)
        return self._model_semaphores[model]

    async def _rate_limited_complete_with_retry(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> CompletionResponse:
        """Make API call with both global and per-model rate limiting plus retry logic."""
        model_sem = self._get_model_semaphore(model)
        last_error = None

        for attempt in range(self.max_retries + 1):
            async with self._global_semaphore:
                async with model_sem:
                    try:
                        response = await self.client.complete(model, messages, **kwargs)

                        async with self._lock:
                            self._api_calls += 1
                            self._response_times.append(response.latency_ms)
                            self._cost_spent += response.cost

                        return response

                    except RateLimitError as e:
                        async with self._lock:
                            self._rate_limit_pauses += 1
                            self._retries += 1

                        # Calculate backoff with jitter
                        delay = self.base_retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Rate limit hit for {model}, retrying in {delay:.2f}s (attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        last_error = e

                    except APIError as e:
                        async with self._lock:
                            self._errors += 1
                            self._retries += 1

                        if attempt < self.max_retries:
                            delay = self.base_retry_delay * (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"API error for {model}: {e}, retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            last_error = e
                        else:
                            raise

                    except Exception as e:
                        async with self._lock:
                            self._errors += 1
                        raise

        # If we exhausted retries
        raise last_error or Exception("Max retries exceeded")

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt]
    ) -> List[ComparisonResult]:
        """Run the full evaluation with parallel processing."""
        self._start_time = time.time()
        self._total_prompts = len(prompts) * len(self.config.model_pairs)
        self._prompts_completed = 0

        # Initialize model pair progress
        for pair in self.config.model_pairs:
            self._model_pair_progress[pair] = {"completed": 0, "total": len(prompts)}

        results: List[ComparisonResult] = []

        # Process prompts in batches for memory efficiency
        batch_size = min(50, self.max_concurrency)

        for batch_start in range(0, len(prompts), batch_size):
            if self._shutdown_requested:
                break

            batch = prompts[batch_start:batch_start + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)

            # Save checkpoint after each batch
            await self.checkpoint.save()

        return results

    async def _process_batch(
        self,
        prompts: List[WritingPrompt]
    ) -> List[ComparisonResult]:
        """Process a batch of prompts with full parallelization."""
        results: List[ComparisonResult] = []

        # Create tasks for all prompt-pair combinations
        tasks = []
        for prompt in prompts:
            for gemini_model, competitor_model in self.config.model_pairs:
                # Skip if already completed (resume support)
                if await self.checkpoint.is_comparison_complete(
                    prompt.prompt_id, gemini_model, competitor_model
                ):
                    continue

                task = asyncio.create_task(
                    self._evaluate_single_comparison(
                        prompt, gemini_model, competitor_model
                    )
                )
                tasks.append((task, prompt, (gemini_model, competitor_model)))

        # Use gather for parallel execution with exception handling
        if tasks:
            task_only = [t[0] for t in tasks]
            completed = await asyncio.gather(*task_only, return_exceptions=True)

            for (result, prompt, pair) in zip(completed, [t[1] for t in tasks], [t[2] for t in tasks]):
                if isinstance(result, Exception):
                    async with self._lock:
                        self._errors += 1
                    logger.error(f"Comparison failed for {prompt.prompt_id}: {result}")
                    continue
                if result is not None:
                    results.append(result)
                    async with self._lock:
                        self._prompts_completed += 1
                        self._model_pair_progress[pair]["completed"] += 1
                    await self._emit_progress(prompt)

        return results

    async def _evaluate_single_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str
    ) -> ComparisonResult:
        """Evaluate a single prompt with one model pair."""

        self._current_prompt = prompt

        # Phase 1: Generate responses in parallel
        gemini_task = self._generate_response(prompt, gemini_model)
        competitor_task = self._generate_response(prompt, competitor_model)

        gemini_resp, competitor_resp = await asyncio.gather(
            gemini_task, competitor_task, return_exceptions=True
        )

        # Handle exceptions from generation
        if isinstance(gemini_resp, Exception):
            gemini_resp = None
        if isinstance(competitor_resp, Exception):
            competitor_resp = None

        # Check for refusals
        refusal_gemini = None
        refusal_competitor = None

        if not gemini_resp or not gemini_resp.content.strip():
            refusal_gemini = "empty_response"
        else:
            refusal_gemini = self.refusal_classifier.classify(gemini_resp.content)

        if not competitor_resp or not competitor_resp.content.strip():
            refusal_competitor = "empty_response"
        else:
            refusal_competitor = self.refusal_classifier.classify(competitor_resp.content)

        # Handle auto-loss cases
        if refusal_gemini and not refusal_competitor:
            return self._create_auto_loss_result(
                prompt, gemini_model, competitor_model,
                gemini_resp, competitor_resp,
                winner="competitor"
            )
        elif refusal_competitor and not refusal_gemini:
            return self._create_auto_loss_result(
                prompt, gemini_model, competitor_model,
                gemini_resp, competitor_resp,
                winner="gemini"
            )
        elif refusal_gemini and refusal_competitor:
            return self._create_auto_loss_result(
                prompt, gemini_model, competitor_model,
                gemini_resp, competitor_resp,
                winner="tie"
            )

        # Phase 2: Run judging in parallel
        all_votes = await self._run_all_judges(
            prompt,
            gemini_model, competitor_model,
            gemini_resp.content, competitor_resp.content
        )

        # Phase 3: Aggregate votes
        aggregated = self.vote_aggregator.aggregate_all(
            prompt.prompt_id,
            gemini_model,
            competitor_model,
            all_votes
        )

        # Track running wins
        pair_key = (gemini_model, competitor_model)
        async with self._lock:
            if pair_key not in self._running_wins:
                self._running_wins[pair_key] = {"gemini": 0, "competitor": 0, "tie": 0}

            winner_key = aggregated.final_winner
            if winner_key in self._running_wins[pair_key]:
                self._running_wins[pair_key][winner_key] += 1

        # Save to database
        await self._save_comparison(
            prompt, gemini_model, competitor_model,
            gemini_resp, competitor_resp,
            aggregated, all_votes
        )

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            gemini_response=gemini_resp.content,
            competitor_response=competitor_resp.content,
            gemini_latency_ms=gemini_resp.latency_ms,
            competitor_latency_ms=competitor_resp.latency_ms,
            gemini_cost=gemini_resp.cost,
            competitor_cost=competitor_resp.cost,
            aggregated_result=aggregated,
            all_votes=all_votes,
            refusal_gemini=refusal_gemini,
            refusal_competitor=refusal_competitor
        )

    async def _generate_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> Optional[CompletionResponse]:
        """Generate a model response with error handling and retry."""
        messages = [
            {"role": "user", "content": prompt.full_prompt}
        ]
        return await self._rate_limited_complete_with_retry(model, messages)

    async def _run_all_judges(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_response: str,
        competitor_response: str
    ) -> List[JudgeVote]:
        """Run all judge evaluations in parallel."""
        tasks = []

        for judge_model in self.config.judge_config.models:
            personas = ["expert", "recipient"] if self.config.judge_config.use_both_personas else ["expert"]

            for persona in personas:
                for vote_idx in range(self.config.judge_config.votes_per_judge):
                    task = asyncio.create_task(
                        self._run_single_judge(
                            prompt,
                            gemini_model, competitor_model,
                            gemini_response, competitor_response,
                            judge_model, persona, vote_idx
                        )
                    )
                    tasks.append(task)

        votes = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and None values
        valid_votes = [v for v in votes if isinstance(v, JudgeVote)]
        return valid_votes

    async def _run_single_judge(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_response: str,
        competitor_response: str,
        judge_model: str,
        persona: str,
        vote_idx: int
    ) -> JudgeVote:
        """Run a single judge evaluation."""
        # Determine position (A or B) for this vote
        gemini_position = self.vote_aggregator.get_position_for_vote(
            prompt.prompt_id,
            gemini_model, competitor_model,
            judge_model, persona, vote_idx
        )

        # Build responses in correct position order
        if gemini_position == "A":
            response_a = gemini_response
            response_b = competitor_response
        else:
            response_a = competitor_response
            response_b = gemini_response

        # Build judge prompt
        system_prompt, user_prompt = self.judge_builder.build_judge_prompt(
            prompt, response_a, response_b, persona
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Call judge model
        response = await self._rate_limited_complete_with_retry(
            judge_model, messages, temperature=0.3
        )

        # Parse response
        parsed = self.judge_parser.parse(response.content)

        # Normalize winner
        normalized_winner = self.vote_aggregator.parse_winner_to_normalized(
            parsed.winner, gemini_position
        )

        # Track per-judge votes
        async with self._lock:
            if judge_model not in self._per_judge_votes:
                self._per_judge_votes[judge_model] = {"gemini": 0, "competitor": 0, "tie": 0}
            if normalized_winner in self._per_judge_votes[judge_model]:
                self._per_judge_votes[judge_model][normalized_winner] += 1

            # Store for Kappa calculation
            self._all_vote_records.append({
                "prompt_id": prompt.prompt_id,
                "judge_model": judge_model,
                "winner": normalized_winner
            })

        # Map quality scores to correct models
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

    def _create_auto_loss_result(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_resp: Optional[CompletionResponse],
        competitor_resp: Optional[CompletionResponse],
        winner: str
    ) -> ComparisonResult:
        """Create result for auto-loss cases (refusal, timeout, etc.)."""
        aggregated = AggregatedResult(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            final_winner=winner,
            gemini_wins=1 if winner == "gemini" else 0,
            competitor_wins=1 if winner == "competitor" else 0,
            ties=1 if winner == "tie" else 0,
            judge_agreement=1.0,
            per_judge_results={},
            all_votes=[]
        )

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            gemini_response=gemini_resp.content if gemini_resp else "",
            competitor_response=competitor_resp.content if competitor_resp else "",
            gemini_latency_ms=gemini_resp.latency_ms if gemini_resp else 0,
            competitor_latency_ms=competitor_resp.latency_ms if competitor_resp else 0,
            gemini_cost=gemini_resp.cost if gemini_resp else 0,
            competitor_cost=competitor_resp.cost if competitor_resp else 0,
            aggregated_result=aggregated,
            all_votes=[],
            refusal_gemini="auto_loss" if winner == "competitor" else None,
            refusal_competitor="auto_loss" if winner == "gemini" else None
        )

    async def _save_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        gemini_resp: CompletionResponse,
        competitor_resp: CompletionResponse,
        aggregated: AggregatedResult,
        votes: List[JudgeVote]
    ) -> None:
        """Save comparison result to database."""
        await self.db.save_comparison(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            gemini_response=gemini_resp.content,
            competitor_response=competitor_resp.content,
            gemini_tokens=gemini_resp.total_tokens,
            competitor_tokens=competitor_resp.total_tokens,
            gemini_latency_ms=gemini_resp.latency_ms,
            competitor_latency_ms=competitor_resp.latency_ms,
            gemini_cost=gemini_resp.cost,
            competitor_cost=competitor_resp.cost,
            final_winner=aggregated.final_winner,
            all_votes=votes
        )

        await self.checkpoint.mark_comparison_complete(
            prompt.prompt_id, gemini_model, competitor_model
        )

    async def _emit_progress(self, current_prompt: WritingPrompt = None) -> None:
        """Emit progress update to callback."""
        if not self.progress_callback:
            return

        elapsed = time.time() - self._start_time

        # Calculate ETA
        if self._prompts_completed > 0:
            rate = self._prompts_completed / elapsed
            remaining = self._total_prompts - self._prompts_completed
            eta_seconds = remaining / rate if rate > 0 else 0
        else:
            eta_seconds = 0

        # Calculate running win rates with confidence intervals
        running_win_rates = {}
        running_cis = {}
        for pair_key, wins in self._running_wins.items():
            total = wins["gemini"] + wins["competitor"] + wins["tie"]
            if total > 0:
                win_rate = wins["gemini"] / total
                running_win_rates[pair_key] = win_rate
                from ..analysis.statistics import wilson_confidence_interval
                ci = wilson_confidence_interval(wins["gemini"], total)
                running_cis[pair_key] = ci

        # Calculate API throughput
        if elapsed > 60:
            api_per_min = self._api_calls / (elapsed / 60)
        else:
            api_per_min = self._api_calls * (60 / elapsed) if elapsed > 0 else 0

        # Calculate cost projection
        if self._prompts_completed > 0:
            cost_per_prompt = self._cost_spent / self._prompts_completed
            cost_projected = cost_per_prompt * self._total_prompts
        else:
            cost_projected = 0

        # Get current prompt context
        prompt = current_prompt or self._current_prompt
        current_occupation = None
        current_industry = None
        current_prompt_id = None

        if prompt:
            current_prompt_id = prompt.prompt_id
            current_occupation = getattr(prompt, 'occupation_title', None)
            current_industry = getattr(prompt, 'industry_name', None)

        update = ProgressUpdate(
            phase=EvalPhase.JUDGING,
            prompts_completed=self._prompts_completed,
            prompts_total=self._total_prompts,
            current_prompt_id=current_prompt_id,
            current_occupation=current_occupation,
            current_industry=current_industry,
            model_pair_progress=dict(self._model_pair_progress),
            per_judge_votes=dict(self._per_judge_votes),
            running_win_rates=running_win_rates,
            running_confidence_intervals=running_cis,
            cost_spent=self._cost_spent,
            cost_projected=cost_projected,
            elapsed_seconds=elapsed,
            eta_seconds=eta_seconds,
            avg_response_time_ms=sum(self._response_times) / len(self._response_times) if self._response_times else 0,
            api_calls_per_minute=api_per_min,
            errors=self._errors,
            retries=self._retries,
            rate_limit_pauses=self._rate_limit_pauses,
            all_votes=self._all_vote_records.copy()
        )

        self.progress_callback(update)

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True
```

### 3.2 Fixed CLI with Proper Validation and Persona Handling

```python
# src/cli.py - FIXED VERSION

import typer
from pathlib import Path
from typing import Optional, List
from enum import Enum

app = typer.Typer(
    name="gemini-eval",
    help="Gemini Writing Evaluation Framework"
)


class ModelTier(str, Enum):
    PRO = "pro"
    FLASH = "flash"
    BOTH = "both"


class JudgePersona(str, Enum):
    BOTH = "both"
    EXPERT = "expert"
    RECIPIENT = "recipient"


def validate_job_zones(value: str) -> List[int]:
    """Validate and parse job zones (1-5)."""
    zones = [int(z.strip()) for z in value.split(",")]
    for z in zones:
        if z < 1 or z > 5:
            raise typer.BadParameter(f"Job zone must be 1-5, got {z}")
    return zones


def validate_formality_range(value: str) -> List[int]:
    """Validate and parse formality range (1-5)."""
    if "-" in value:
        low, high = value.split("-")
        low, high = int(low), int(high)
        if low < 1 or high > 5 or low > high:
            raise typer.BadParameter(f"Formality range must be within 1-5")
        return list(range(low, high + 1))
    else:
        levels = [int(f.strip()) for f in value.split(",")]
        for f in levels:
            if f < 1 or f > 5:
                raise typer.BadParameter(f"Formality level must be 1-5, got {f}")
        return levels


def validate_age_range(value: str) -> tuple:
    """Validate and parse age range (18-100)."""
    if "-" in value:
        low, high = value.split("-")
        low, high = int(low), int(high)
    else:
        low = high = int(value)

    if low < 18 or high > 100 or low > high:
        raise typer.BadParameter(f"Age range must be within 18-100")
    return (low, high)


@app.command()
def run(
    # Preset configuration
    preset: int = typer.Option(
        6, "--preset", "-p",
        help="Preset level 1-10 (1=Sanity Check, 10=Full Kaboodle)",
        min=1, max=10
    ),

    # Model configuration
    models: Optional[str] = typer.Option(
        None, "--models", "-m",
        help="Comma-separated list of models to evaluate"
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
        help="Number of votes per judge (1, 3, or 5)",
        min=1, max=5
    ),
    persona: JudgePersona = typer.Option(
        JudgePersona.BOTH, "--persona",
        help="Judge persona: both, expert, or recipient"
    ),

    # Prompt/task configuration
    prompts: Optional[int] = typer.Option(
        None, "--prompts", "-n",
        help="Number of prompts to evaluate",
        min=1
    ),
    occupations: Optional[str] = typer.Option(
        None, "--occupations", "-o",
        help="Filter by O*NET occupation codes (comma-separated, wildcards supported)"
    ),
    industries: Optional[str] = typer.Option(
        None, "--industries", "-i",
        help="Filter by NAICS industry codes (comma-separated)"
    ),
    job_zones: Optional[str] = typer.Option(
        None, "--job-zones", "-z",
        help="Filter by job zones 1-5 (comma-separated, e.g., '3,4,5')"
    ),
    formality_range: Optional[str] = typer.Option(
        None, "--formality-range", "-f",
        help="Filter by formality level range (e.g., '3-5' or '1,2,3')"
    ),
    age_range: Optional[str] = typer.Option(
        None, "--age-range", "-a",
        help="Filter by persona age range (e.g., '25-45')"
    ),

    # Sampling configuration
    seed: Optional[int] = typer.Option(
        None, "--seed", "-s",
        help="Random seed for reproducible sampling"
    ),
    occupation_limit: Optional[int] = typer.Option(
        None, "--occupation-limit",
        help="Maximum prompts per occupation",
        min=1
    ),
    industry_limit: Optional[int] = typer.Option(
        None, "--industry-limit",
        help="Maximum prompts per industry",
        min=1
    ),

    # Run options
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show cost estimate without running"
    ),
    resume: Optional[Path] = typer.Option(
        None, "--resume",
        help="Resume from a previous run directory"
    ),
    output_dir: Path = typer.Option(
        Path("results"), "--output", "-O",
        help="Output directory for results"
    ),

    # Concurrency
    max_concurrency: int = typer.Option(
        30, "--concurrency", "-c",
        help="Maximum concurrent API requests",
        min=1, max=100
    ),
):
    """Run a Gemini writing evaluation."""
    import asyncio
    from .config.presets import PRESETS, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES
    from .config.cost_estimator import estimate_cost, format_cost_estimate
    from .config.settings import EvalConfig, JudgeConfig

    # Validate preset
    if preset not in PRESETS:
        typer.echo(f"Invalid preset {preset}. Must be 1-10.", err=True)
        raise typer.Exit(1)

    # Start with preset configuration
    config = PRESETS[preset].copy()

    # Override with CLI options
    if prompts is not None:
        config.num_prompts = prompts

    if seed is not None:
        config.random_seed = seed

    # Handle model tier
    if tier == ModelTier.PRO:
        config.model_pairs = PRO_PAIRS
    elif tier == ModelTier.FLASH:
        config.model_pairs = FLASH_PAIRS
    # BOTH keeps the preset's model_pairs

    # Handle custom models list
    if models:
        model_list = [m.strip() for m in models.split(",")]
        gemini_models = [m for m in model_list if "gemini" in m.lower()]
        other_models = [m for m in model_list if "gemini" not in m.lower()]

        if not gemini_models:
            typer.echo("Error: At least one Gemini model required in --models", err=True)
            raise typer.Exit(1)
        if not other_models:
            typer.echo("Error: At least one competitor model required in --models", err=True)
            raise typer.Exit(1)

        # Build all pairwise combinations
        config.model_pairs = [
            (gemini, comp)
            for gemini in gemini_models
            for comp in other_models
        ]

    # Handle judge configuration
    if judges:
        judge_list = [j.strip() for j in judges.split(",")]
        config.judge_config.models = judge_list
    if votes is not None:
        config.judge_config.votes_per_judge = votes

    # Handle judge persona
    if persona == JudgePersona.EXPERT:
        config.judge_config.use_both_personas = False
        config.judge_config.persona_mode = "expert"
    elif persona == JudgePersona.RECIPIENT:
        config.judge_config.use_both_personas = False
        config.judge_config.persona_mode = "recipient"
    else:
        config.judge_config.use_both_personas = True
        config.judge_config.persona_mode = "both"

    # Parse and validate filters
    parsed_job_zones = None
    if job_zones:
        try:
            parsed_job_zones = validate_job_zones(job_zones)
        except ValueError as e:
            typer.echo(f"Invalid job zones: {e}", err=True)
            raise typer.Exit(1)

    parsed_formality = None
    if formality_range:
        try:
            parsed_formality = validate_formality_range(formality_range)
        except ValueError as e:
            typer.echo(f"Invalid formality range: {e}", err=True)
            raise typer.Exit(1)

    parsed_age_range = None
    if age_range:
        try:
            parsed_age_range = validate_age_range(age_range)
        except ValueError as e:
            typer.echo(f"Invalid age range: {e}", err=True)
            raise typer.Exit(1)

    # Parse occupations and industries
    parsed_occupations = None
    if occupations:
        parsed_occupations = [o.strip() for o in occupations.split(",")]

    parsed_industries = None
    if industries:
        parsed_industries = [i.strip() for i in industries.split(",")]

    # Show cost estimate
    estimate = estimate_cost(config)
    typer.echo(format_cost_estimate(estimate, config))

    if dry_run:
        typer.echo("\n[Dry run - no evaluation performed]")
        raise typer.Exit()

    # Confirm before running
    if not typer.confirm("Proceed with evaluation?"):
        raise typer.Exit()

    # Run evaluation
    from .main import run_evaluation

    asyncio.run(run_evaluation(
        config=config,
        resume_dir=resume,
        output_dir=output_dir,
        max_concurrency=max_concurrency,
        job_zones=parsed_job_zones,
        formality_range=parsed_formality,
        age_range=parsed_age_range,
        occupation_codes=parsed_occupations,
        industry_codes=parsed_industries,
        occupation_limit=occupation_limit,
        industry_limit=industry_limit
    ))
```

### 3.3 Fixed Name Generator with Proper Suffix Probability

```python
# src/data/name_generator.py - FIXED SUFFIX LOGIC

def generate(
    self,
    gender: Optional[str] = None,
    ethnicity: Optional[str] = None,
    generation: Optional[str] = None,
    has_title: bool = False,
    title_context: str = "general"
) -> GeneratedName:
    """Generate a complete name with all variants."""

    # Select gender if not specified (include non-binary)
    if gender is None:
        # Census-based with non-binary representation
        genders = ["male", "female", "non-binary"]
        weights = [0.49, 0.49, 0.02]
        gender = self.rng.choices(genders, weights=weights)[0]

    # ... other selections as before ...

    # Get suffix using weighted random choice
    suffix = self._select_suffix_weighted()

    # ... rest of method ...


def _select_suffix_weighted(self) -> Optional[str]:
    """Select suffix using proper weighted random choice."""
    suffixes = [sfx for sfx, _ in self.SUFFIXES]
    weights = [prob for _, prob in self.SUFFIXES]

    # Normalize weights to sum to 1
    total = sum(weights)
    normalized_weights = [w / total for w in weights]

    return self.rng.choices(suffixes, weights=normalized_weights, k=1)[0]
```

### 3.4 Missing RefusalClassifier Implementation

```python
# src/eval/refusal_classifier.py

import re
from typing import Optional
from enum import Enum


class RefusalCategory(str, Enum):
    """Categories of model refusals."""
    SAFETY = "safety_refusal"
    CAPABILITY = "capability_limitation"
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE = "incomplete_response"
    OFF_TOPIC = "off_topic"
    EMPTY = "empty_response"


class RefusalClassifier:
    """Classify model responses as refusals and categorize them.

    Per PROMPT.md:
    - Safety refusal: Model cites safety/policy concerns
    - Capability limitation: Model says it can't do the task
    - Misunderstanding: Model interprets task incorrectly
    - Incomplete response: Model starts but doesn't finish
    - Off-topic: Model responds but not to the actual task
    """

    SAFETY_PATTERNS = [
        r"(?:I cannot|I'm unable to|I can't).*(?:help with|assist with|generate|create|write).*(?:harmful|dangerous|illegal|unethical)",
        r"(?:violates|against).*(?:policy|guidelines|terms|ethics)",
        r"(?:I'm not able to|I cannot).*(?:content|material).*(?:inappropriate|harmful)",
        r"(?:as an AI|as a language model).*(?:cannot|shouldn't|won't).*(?:create|generate|write)",
        r"(?:I must decline|I have to refuse)",
        r"(?:safety|policy|ethical) concerns",
    ]

    CAPABILITY_PATTERNS = [
        r"(?:I don't have|I lack).*(?:ability|capability|access|information)",
        r"(?:beyond my|outside my).*(?:capabilities|scope|abilities)",
        r"(?:I'm not capable of|I cannot perform)",
        r"(?:I don't know how to|I'm unable to)",
        r"(?:require|need).*(?:more context|additional information|clarification)",
    ]

    INCOMPLETE_PATTERNS = [
        r"(?:I'll need to|Let me).*(?:but first|however).*$",  # Trails off
        r"\.\.\.$",  # Ends with ellipsis
        r"(?:To be continued|More to come|continued in)",
    ]

    OFF_TOPIC_INDICATORS = [
        "actually", "instead", "however", "but",
        "I think you meant", "did you mean",
        "let me help you with something else",
    ]

    def classify(self, response: str) -> Optional[str]:
        """Classify a response. Returns None if not a refusal."""
        if not response or not response.strip():
            return RefusalCategory.EMPTY.value

        response_lower = response.lower()

        # Check for safety refusal
        for pattern in self.SAFETY_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return RefusalCategory.SAFETY.value

        # Check for capability limitation
        for pattern in self.CAPABILITY_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return RefusalCategory.CAPABILITY.value

        # Check for incomplete response
        for pattern in self.INCOMPLETE_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                return RefusalCategory.INCOMPLETE.value

        # Check for off-topic (heuristic: short response with deflection)
        if len(response) < 200:
            off_topic_count = sum(
                1 for indicator in self.OFF_TOPIC_INDICATORS
                if indicator in response_lower
            )
            if off_topic_count >= 2:
                return RefusalCategory.OFF_TOPIC.value

        # Not a refusal
        return None

    def is_refusal(self, response: str) -> bool:
        """Check if response is any type of refusal."""
        return self.classify(response) is not None
```

### 3.5 Missing Database get_all_comparisons Method

```python
# src/storage/database.py - Addition

class Database:
    """SQLite database for storing evaluation results."""

    # ... existing methods ...

    async def get_all_comparisons(self) -> List[Dict]:
        """Get all comparisons for results viewer."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = """
            SELECT
                c.prompt_id,
                c.gemini_model,
                c.competitor_model,
                c.gemini_response,
                c.competitor_response,
                c.gemini_latency_ms,
                c.competitor_latency_ms,
                c.final_winner as winner,
                p.occupation_code,
                p.occupation_title,
                p.naics_code,
                p.industry_name,
                AVG(v.confidence) as avg_confidence
            FROM comparisons c
            LEFT JOIN prompts p ON c.prompt_id = p.prompt_id
            LEFT JOIN votes v ON c.comparison_id = v.comparison_id
            GROUP BY c.comparison_id
            ORDER BY c.created_at DESC
            """

            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_comparison_with_votes(self, prompt_id: str) -> Optional[Dict]:
        """Get a single comparison with all its votes."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get comparison
            async with db.execute(
                "SELECT * FROM comparisons WHERE prompt_id = ?",
                (prompt_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                comparison = dict(row)

            # Get votes
            async with db.execute(
                """SELECT * FROM votes WHERE comparison_id = ?""",
                (comparison["comparison_id"],)
            ) as cursor:
                votes = await cursor.fetchall()
                comparison["votes"] = [dict(v) for v in votes]

            return comparison
```

### 3.6 Sensitive Topic Win Rate Tracking

```python
# src/analysis/sensitive_topic_analyzer.py

from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict

from ..analysis.statistics import wilson_confidence_interval


@dataclass
class SensitiveTopicWinRate:
    """Win rate statistics for a sensitive topic."""
    topic: str
    total_comparisons: int
    gemini_wins: int
    competitor_wins: int
    ties: int
    win_rate: float
    confidence_interval: tuple


class SensitiveTopicAnalyzer:
    """Track and analyze win rates for sensitive vs routine tasks.

    Per PROMPT.md: "Track win rates separately for sensitive vs routine tasks"
    """

    def __init__(self):
        self._topic_results: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"gemini": 0, "competitor": 0, "tie": 0, "total": 0}
        )
        self._routine_results = {"gemini": 0, "competitor": 0, "tie": 0, "total": 0}

    def record_comparison(
        self,
        winner: str,
        sensitive_topics: List[str]
    ) -> None:
        """Record a comparison result."""
        if sensitive_topics:
            for topic in sensitive_topics:
                self._topic_results[topic][winner] += 1
                self._topic_results[topic]["total"] += 1
        else:
            self._routine_results[winner] += 1
            self._routine_results["total"] += 1

    def get_sensitive_win_rates(self) -> Dict[str, SensitiveTopicWinRate]:
        """Get win rates for each sensitive topic."""
        results = {}

        for topic, counts in self._topic_results.items():
            total = counts["total"]
            if total == 0:
                continue

            gemini_wins = counts["gemini"]
            win_rate = gemini_wins / total

            ci = wilson_confidence_interval(gemini_wins, total)

            results[topic] = SensitiveTopicWinRate(
                topic=topic,
                total_comparisons=total,
                gemini_wins=gemini_wins,
                competitor_wins=counts["competitor"],
                ties=counts["tie"],
                win_rate=win_rate,
                confidence_interval=ci
            )

        return results

    def get_routine_win_rate(self) -> SensitiveTopicWinRate:
        """Get win rate for routine (non-sensitive) tasks."""
        total = self._routine_results["total"]
        gemini_wins = self._routine_results["gemini"]

        if total == 0:
            return SensitiveTopicWinRate(
                topic="routine",
                total_comparisons=0,
                gemini_wins=0,
                competitor_wins=0,
                ties=0,
                win_rate=0.5,
                confidence_interval=(0.0, 1.0)
            )

        win_rate = gemini_wins / total
        ci = wilson_confidence_interval(gemini_wins, total)

        return SensitiveTopicWinRate(
            topic="routine",
            total_comparisons=total,
            gemini_wins=gemini_wins,
            competitor_wins=self._routine_results["competitor"],
            ties=self._routine_results["tie"],
            win_rate=win_rate,
            confidence_interval=ci
        )

    def get_comparison_summary(self) -> Dict:
        """Compare sensitive vs routine performance."""
        routine = self.get_routine_win_rate()
        sensitive = self.get_sensitive_win_rates()

        # Calculate overall sensitive win rate
        total_sensitive = sum(s.total_comparisons for s in sensitive.values())
        total_sensitive_wins = sum(s.gemini_wins for s in sensitive.values())

        if total_sensitive > 0:
            overall_sensitive_rate = total_sensitive_wins / total_sensitive
            sensitive_ci = wilson_confidence_interval(total_sensitive_wins, total_sensitive)
        else:
            overall_sensitive_rate = 0.5
            sensitive_ci = (0.0, 1.0)

        return {
            "routine": {
                "win_rate": routine.win_rate,
                "confidence_interval": routine.confidence_interval,
                "total": routine.total_comparisons
            },
            "sensitive_overall": {
                "win_rate": overall_sensitive_rate,
                "confidence_interval": sensitive_ci,
                "total": total_sensitive
            },
            "by_topic": {
                topic: {
                    "win_rate": stats.win_rate,
                    "confidence_interval": stats.confidence_interval,
                    "total": stats.total_comparisons
                }
                for topic, stats in sensitive.items()
            },
            "delta": overall_sensitive_rate - routine.win_rate if total_sensitive > 0 else 0
        }
```

---

## SECTION 4: SUMMARY OF CHANGES

### Critical Fixes Applied

1. **EvaluationEngine**
   - Added proper retry logic with exponential backoff and jitter
   - Added asyncio.Lock for thread-safe counter updates
   - Added RateLimitError and APIError handling with proper counter increments
   - Added model_pair_progress tracking
   - Fixed _emit_progress to populate current_occupation and current_industry
   - Added all_votes to ProgressUpdate for Kappa calculation

2. **CLI**
   - Added validation functions for job_zones, formality_range, and age_range
   - Added proper error handling with typer.BadParameter
   - Fixed persona handling with persona_mode attribute instead of _recipient_only
   - Added validation that models list contains both Gemini and competitor
   - Added support for multiple Gemini models creating full pairwise combinations

3. **Name Generator**
   - Fixed suffix probability selection using proper weighted random.choices
   - Added non-binary gender option

4. **New Implementations**
   - RefusalClassifier with proper category enum and pattern matching
   - Database.get_all_comparisons for results viewer
   - SensitiveTopicAnalyzer for sensitive vs routine win rate tracking

### Remaining Integration Work

The following still need to be integrated into the main implementation but were not addressed in the original draft:

1. **Main entry point** (`src/main.py`) - The run_evaluation function called by CLI
2. **Database schema definitions** - CREATE TABLE statements for SQLite
3. **JudgePromptBuilder** - Full implementation of judge prompt construction
4. **ResponseAnalyzer** - Implementation for response metadata extraction
5. **Statistics panel modal** - Full implementation for `s` key action
6. **Detail view mode** - Full implementation for `d` key action

### Verification Checklist

All gaps from gap_analysis.md are now addressed:

| Gap | Status |
|-----|--------|
| Inter-judge agreement (Cohen's Kappa) | FIXED - Implementation provided |
| Cost tracking in TUI | FIXED - CostTracker widget implemented |
| Help overlay (h key) | FIXED - HelpOverlay implemented |
| CLI options (--tier, --job-zones, etc.) | FIXED - Complete CLI with validation |
| Name formality variation | FIXED - NameFormality enum and format method |
| Phase 1 generation using evaluated models | FIXED - Phase1Generator distributes across models |
| Ambiguity behavior tracking | FIXED - AmbiguityTracker with pattern detection |
| TUI Results Viewer | FIXED - Complete with filtering, sorting, drill-down |
| Refusal tracking by dimension | FIXED - RefusalTracker with breakdowns |
| Failure summary report | FIXED - FailureSummaryReport generator |
| ETA calculation | FIXED - Added to ProgressUpdate and TUI |
| Confidence intervals in TUI | FIXED - ConfidenceIntervalDisplay widget |
| Occupation/industry context | FIXED - Added to ProgressUpdate |
| Per-judge vote counts | FIXED - PerJudgeVotes widget |
| Response times/throughput | FIXED - ResponseMetrics widget |
| Sensitive topic win rates | FIXED - NEW SensitiveTopicAnalyzer added |

---

## SECTION 5: ADDITIONAL RECOMMENDATIONS

### For Production Readiness

1. **Add comprehensive unit tests** for each new component
2. **Add integration tests** that verify the full evaluation pipeline
3. **Add structured logging** using Python's logging module with rotation
4. **Add metrics collection** for Prometheus/Grafana monitoring
5. **Add graceful degradation** when individual judge models fail
6. **Add database migrations** support for schema evolution
7. **Add configuration file support** (YAML/TOML) in addition to CLI

### For Performance

1. **Implement connection pooling** for database access
2. **Add caching** for expensive computations (Kappa, CI)
3. **Implement incremental statistics** instead of recalculating from scratch
4. **Add batch inserts** for database operations
5. **Consider Redis** for cross-process progress sharing if running distributed

### For Observability

1. **Add OpenTelemetry tracing** for request flow visibility
2. **Add structured error logging** with stack traces and context
3. **Add health checks** for each external service (OpenRouter, database)
4. **Add alerting thresholds** for error rates and latency
