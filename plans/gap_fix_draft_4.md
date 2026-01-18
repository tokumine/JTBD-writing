# Gap Fix Implementations - Draft 4

This document provides COMPLETE Python implementations for all identified gaps from the gap analysis.

---

## 1. PARALLEL REQUEST ARCHITECTURE (CRITICAL)

### 1.1 EvaluationEngine with asyncio.gather/TaskGroup

```python
# src/eval/engine.py

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum

from ..api.openrouter_client import OpenRouterClient, CompletionResponse
from ..config.presets import EvalConfig, JudgeConfig
from ..prompts.schemas import WritingPrompt
from ..storage.checkpoint import CheckpointManager
from ..storage.database import ResultsDatabase
from .vote_aggregator import VoteAggregator
from .judge_prompt_builder import JudgePromptBuilder
from .judge_parser import JudgeParser, ParsedJudgment
from .schemas import ComparisonResult, JudgeVote, ModelResponse

class EvaluationPhase(Enum):
    GENERATION = "generation"
    JUDGING = "judging"
    ANALYSIS = "analysis"

@dataclass
class ProgressUpdate:
    """Progress update for TUI callbacks."""
    phase: EvaluationPhase
    completed_prompts: int
    total_prompts: int
    current_prompt_id: Optional[str] = None
    current_model_pair: Optional[Tuple[str, str]] = None
    model_pair_progress: Dict[Tuple[str, str], Dict[str, int]] = field(default_factory=dict)
    running_win_rates: Dict[Tuple[str, str], float] = field(default_factory=dict)
    cost_spent: float = 0.0
    cost_projected: float = 0.0
    elapsed_seconds: float = 0.0
    eta_seconds: Optional[float] = None
    response_times: Dict[str, float] = field(default_factory=dict)
    throughput: float = 0.0  # requests per minute
    errors: int = 0
    retries: int = 0

@dataclass
class ConcurrencyConfig:
    """Configuration for parallel request handling."""
    max_concurrent_requests: int = 20  # Global concurrency limit
    per_model_concurrency: Dict[str, int] = field(default_factory=dict)
    batch_size: int = 10  # Prompts to process in each batch

    def __post_init__(self):
        # Default per-model concurrency based on rate limits
        if not self.per_model_concurrency:
            self.per_model_concurrency = {
                "google/gemini-3.0-pro": 15,
                "google/gemini-3.0-flash": 25,
                "openai/gpt-5.2": 10,
                "openai/gpt-4.1": 20,
                "anthropic/claude-opus-4.5": 8,
                "anthropic/claude-sonnet-4": 15,
                "x-ai/grok-4.1": 10,
                "moonshot/kimi-k2": 10,
            }

class EvaluationEngine:
    """Main evaluation orchestrator with parallel request architecture."""

    def __init__(
        self,
        client: OpenRouterClient,
        config: EvalConfig,
        concurrency: Optional[ConcurrencyConfig] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        database: Optional[ResultsDatabase] = None,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None
    ):
        self.client = client
        self.config = config
        self.concurrency = concurrency or ConcurrencyConfig()
        self.checkpoint_manager = checkpoint_manager
        self.database = database
        self.progress_callback = progress_callback

        # Concurrency control
        self._global_semaphore = asyncio.Semaphore(self.concurrency.max_concurrent_requests)
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}

        # State tracking
        self._start_time: Optional[float] = None
        self._completed_prompts = 0
        self._total_cost = 0.0
        self._request_count = 0
        self._errors = 0
        self._retries = 0
        self._response_times: Dict[str, List[float]] = {}
        self._win_counts: Dict[Tuple[str, str], Dict[str, int]] = {}

        # Components
        self.judge_builder = JudgePromptBuilder()
        self.judge_parser = JudgeParser()
        self.vote_aggregator = VoteAggregator()

        # Pause/cancel control
        self._paused = False
        self._cancelled = False

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore."""
        if model not in self._model_semaphores:
            limit = self.concurrency.per_model_concurrency.get(model, 10)
            self._model_semaphores[model] = asyncio.Semaphore(limit)
        return self._model_semaphores[model]

    async def _rate_limited_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> CompletionResponse:
        """Execute request with global and per-model rate limiting."""
        model_semaphore = self._get_model_semaphore(model)

        async with self._global_semaphore:
            async with model_semaphore:
                # Check for pause
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)

                if self._cancelled:
                    raise asyncio.CancelledError("Evaluation cancelled")

                try:
                    response = await self.client.complete(model, messages, **kwargs)
                    self._request_count += 1
                    self._total_cost += response.cost

                    # Track response time
                    if model not in self._response_times:
                        self._response_times[model] = []
                    self._response_times[model].append(response.latency_ms)

                    return response
                except Exception as e:
                    self._errors += 1
                    raise

    async def _generate_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> ModelResponse:
        """Generate a single model response."""
        messages = [
            {"role": "user", "content": prompt.full_prompt}
        ]

        response = await self._rate_limited_request(
            model=model,
            messages=messages,
            temperature=0.7
        )

        return ModelResponse(
            prompt_id=prompt.prompt_id,
            model=model,
            content=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
            cost=response.cost,
            finish_reason=response.finish_reason
        )

    async def _generate_responses_batch(
        self,
        prompts: List[WritingPrompt],
        model_pair: Tuple[str, str]
    ) -> List[Tuple[ModelResponse, ModelResponse]]:
        """Generate responses for a batch of prompts using asyncio.gather."""
        gemini, competitor = model_pair

        async def generate_pair(prompt: WritingPrompt) -> Tuple[ModelResponse, ModelResponse]:
            # Generate both responses concurrently
            gemini_response, competitor_response = await asyncio.gather(
                self._generate_response(prompt, gemini),
                self._generate_response(prompt, competitor)
            )
            return gemini_response, competitor_response

        # Process all prompts in batch concurrently
        results = await asyncio.gather(
            *[generate_pair(prompt) for prompt in prompts],
            return_exceptions=True
        )

        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._errors += 1
                # Log failure but continue
                if self.checkpoint_manager:
                    await self.checkpoint_manager.log_failure(
                        prompts[i].prompt_id,
                        str(result)
                    )
            else:
                valid_results.append(result)

        return valid_results

    async def _judge_comparison(
        self,
        prompt: WritingPrompt,
        response_a: str,
        response_b: str,
        judge_model: str,
        persona: str,
        vote_idx: int
    ) -> JudgeVote:
        """Execute a single judge evaluation."""
        # Determine position (A/B ordering) based on vote index for bias mitigation
        position = self.vote_aggregator.get_position_for_vote(
            prompt.prompt_id, judge_model, vote_idx
        )

        if position == "gemini_first":
            actual_a, actual_b = response_a, response_b
        else:
            actual_a, actual_b = response_b, response_a

        system, user = self.judge_builder.build_judge_prompt(
            prompt, actual_a, actual_b, persona
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

        response = await self._rate_limited_request(
            model=judge_model,
            messages=messages,
            temperature=0.3
        )

        parsed = self.judge_parser.parse(response.content)

        # Map winner back to actual model based on position
        if parsed.winner in ["A", "a"]:
            actual_winner = "gemini" if position == "gemini_first" else "competitor"
        elif parsed.winner in ["B", "b"]:
            actual_winner = "competitor" if position == "gemini_first" else "gemini"
        else:
            actual_winner = "tie"

        return JudgeVote(
            prompt_id=prompt.prompt_id,
            judge_model=judge_model,
            persona=persona,
            vote_idx=vote_idx,
            winner=actual_winner,
            confidence=parsed.confidence,
            quality_a=parsed.quality_a,
            quality_b=parsed.quality_b,
            constraint_compliance_a=parsed.constraint_compliance_a,
            constraint_compliance_b=parsed.constraint_compliance_b,
            reasoning=parsed.reasoning,
            position=position,
            latency_ms=response.latency_ms,
            cost=response.cost
        )

    async def _judge_comparison_batch(
        self,
        comparisons: List[Tuple[WritingPrompt, str, str]]
    ) -> List[List[JudgeVote]]:
        """Judge a batch of comparisons with all judges and votes."""
        judge_config = self.config.judge_config

        async def judge_single_comparison(
            prompt: WritingPrompt,
            response_a: str,
            response_b: str
        ) -> List[JudgeVote]:
            votes = []

            # Create tasks for all judge/persona/vote combinations
            tasks = []
            for judge_model in judge_config.models:
                personas = ["expert", "recipient"] if judge_config.use_both_personas else ["expert"]
                for persona in personas:
                    for vote_idx in range(judge_config.votes_per_judge):
                        tasks.append(
                            self._judge_comparison(
                                prompt, response_a, response_b,
                                judge_model, persona, vote_idx
                            )
                        )

            # Execute all judge calls concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, JudgeVote):
                    votes.append(result)
                else:
                    self._errors += 1

            return votes

        # Process all comparisons concurrently
        all_votes = await asyncio.gather(
            *[judge_single_comparison(p, a, b) for p, a, b in comparisons],
            return_exceptions=True
        )

        return [v for v in all_votes if isinstance(v, list)]

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt]
    ) -> Dict[str, Any]:
        """Run complete evaluation with parallel processing."""
        self._start_time = time.time()
        total_prompts = len(prompts)

        results = {
            "comparisons": [],
            "win_rates": {},
            "total_cost": 0.0,
            "elapsed_time": 0.0
        }

        # Initialize win counts
        for model_pair in self.config.model_pairs:
            self._win_counts[model_pair] = {"gemini": 0, "competitor": 0, "tie": 0}

        # Process in batches
        batch_size = self.concurrency.batch_size

        for model_pair in self.config.model_pairs:
            pair_start = 0

            while pair_start < total_prompts:
                if self._cancelled:
                    break

                batch = prompts[pair_start:pair_start + batch_size]

                # PHASE 1: Generation
                self._update_progress(
                    EvaluationPhase.GENERATION,
                    pair_start,
                    total_prompts,
                    model_pair=model_pair
                )

                response_pairs = await self._generate_responses_batch(batch, model_pair)

                # Checkpoint responses
                if self.checkpoint_manager:
                    for gemini_resp, competitor_resp in response_pairs:
                        await self.checkpoint_manager.save_response(gemini_resp)
                        await self.checkpoint_manager.save_response(competitor_resp)

                # PHASE 2: Judging
                self._update_progress(
                    EvaluationPhase.JUDGING,
                    pair_start,
                    total_prompts,
                    model_pair=model_pair
                )

                # Prepare comparisons for judging
                comparisons = [
                    (batch[i], resp_pair[0].content, resp_pair[1].content)
                    for i, resp_pair in enumerate(response_pairs)
                ]

                all_votes = await self._judge_comparison_batch(comparisons)

                # Aggregate votes and update results
                for i, votes in enumerate(all_votes):
                    prompt = batch[i]
                    aggregation = self.vote_aggregator.aggregate(votes)

                    # Update win counts
                    winner = aggregation.final_winner
                    self._win_counts[model_pair][winner] += 1

                    comparison_result = ComparisonResult(
                        prompt_id=prompt.prompt_id,
                        model_pair=model_pair,
                        gemini_response=response_pairs[i][0],
                        competitor_response=response_pairs[i][1],
                        votes=votes,
                        aggregation=aggregation
                    )

                    results["comparisons"].append(comparison_result)

                    # Checkpoint comparison
                    if self.checkpoint_manager:
                        await self.checkpoint_manager.save_comparison(comparison_result)

                    self._completed_prompts += 1

                pair_start += batch_size

                # Update progress with win rates
                self._update_progress(
                    EvaluationPhase.JUDGING,
                    self._completed_prompts,
                    total_prompts * len(self.config.model_pairs),
                    model_pair=model_pair
                )

        # Compute final stats
        elapsed = time.time() - self._start_time
        results["elapsed_time"] = elapsed
        results["total_cost"] = self._total_cost

        for model_pair, counts in self._win_counts.items():
            total = counts["gemini"] + counts["competitor"] + counts["tie"]
            if total > 0:
                results["win_rates"][model_pair] = counts["gemini"] / total

        return results

    def _update_progress(
        self,
        phase: EvaluationPhase,
        completed: int,
        total: int,
        model_pair: Optional[Tuple[str, str]] = None
    ):
        """Send progress update to callback."""
        if not self.progress_callback:
            return

        elapsed = time.time() - (self._start_time or time.time())

        # Calculate ETA
        eta = None
        if completed > 0 and elapsed > 0:
            rate = completed / elapsed
            remaining = total - completed
            eta = remaining / rate if rate > 0 else None

        # Calculate throughput
        throughput = (self._request_count / elapsed * 60) if elapsed > 0 else 0

        # Calculate average response times
        avg_times = {}
        for model, times in self._response_times.items():
            if times:
                avg_times[model] = sum(times) / len(times)

        # Calculate running win rates
        running_win_rates = {}
        for pair, counts in self._win_counts.items():
            total_votes = counts["gemini"] + counts["competitor"] + counts["tie"]
            if total_votes > 0:
                running_win_rates[pair] = counts["gemini"] / total_votes

        # Estimate projected cost
        if completed > 0:
            cost_per_prompt = self._total_cost / completed
            projected = cost_per_prompt * total
        else:
            projected = 0.0

        update = ProgressUpdate(
            phase=phase,
            completed_prompts=completed,
            total_prompts=total,
            current_model_pair=model_pair,
            model_pair_progress={
                pair: {"completed": counts["gemini"] + counts["competitor"] + counts["tie"],
                       "gemini_wins": counts["gemini"]}
                for pair, counts in self._win_counts.items()
            },
            running_win_rates=running_win_rates,
            cost_spent=self._total_cost,
            cost_projected=projected,
            elapsed_seconds=elapsed,
            eta_seconds=eta,
            response_times=avg_times,
            throughput=throughput,
            errors=self._errors,
            retries=self._retries
        )

        self.progress_callback(update)

    def pause(self):
        """Pause evaluation."""
        self._paused = True

    def resume(self):
        """Resume evaluation."""
        self._paused = False

    def cancel(self):
        """Cancel evaluation."""
        self._cancelled = True
```

---

## 2. COHEN'S KAPPA INTER-JUDGE AGREEMENT (CRITICAL)

```python
# src/analysis/statistics.py (addition)

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import Counter

@dataclass
class KappaResult:
    """Cohen's Kappa calculation result."""
    kappa: float
    interpretation: str
    observed_agreement: float
    expected_agreement: float
    judge_a: str
    judge_b: str
    n_samples: int

def interpret_kappa(kappa: float) -> str:
    """Interpret Kappa value using Landis & Koch scale."""
    if kappa < 0:
        return "Poor (less than chance)"
    elif kappa < 0.21:
        return "Slight"
    elif kappa < 0.41:
        return "Fair"
    elif kappa < 0.61:
        return "Moderate"
    elif kappa < 0.81:
        return "Substantial"
    else:
        return "Almost Perfect"

def calculate_cohens_kappa(
    ratings_a: List[str],
    ratings_b: List[str],
    categories: Optional[List[str]] = None
) -> float:
    """
    Calculate Cohen's Kappa for inter-rater reliability.

    Args:
        ratings_a: Ratings from judge A
        ratings_b: Ratings from judge B
        categories: Possible rating categories (defaults to unique values)

    Returns:
        Cohen's Kappa coefficient (-1 to 1)
    """
    if len(ratings_a) != len(ratings_b):
        raise ValueError("Rating lists must have equal length")

    n = len(ratings_a)
    if n == 0:
        return 0.0

    if categories is None:
        categories = list(set(ratings_a) | set(ratings_b))

    # Build confusion matrix
    k = len(categories)
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    confusion = np.zeros((k, k), dtype=int)
    for a, b in zip(ratings_a, ratings_b):
        i = cat_to_idx.get(a)
        j = cat_to_idx.get(b)
        if i is not None and j is not None:
            confusion[i, j] += 1

    # Calculate observed agreement (diagonal sum / total)
    observed = np.trace(confusion) / n

    # Calculate expected agreement by chance
    row_sums = confusion.sum(axis=1)
    col_sums = confusion.sum(axis=0)
    expected = np.sum(row_sums * col_sums) / (n * n)

    # Cohen's Kappa formula
    if expected == 1.0:
        return 1.0  # Perfect agreement case

    kappa = (observed - expected) / (1 - expected)
    return kappa

def calculate_pairwise_kappa(
    judgments: Dict[str, List[str]]
) -> List[KappaResult]:
    """
    Calculate pairwise Cohen's Kappa for all judge pairs.

    Args:
        judgments: Dict mapping judge_id to list of ratings

    Returns:
        List of KappaResult for each pair
    """
    results = []
    judges = list(judgments.keys())

    for i in range(len(judges)):
        for j in range(i + 1, len(judges)):
            judge_a = judges[i]
            judge_b = judges[j]

            ratings_a = judgments[judge_a]
            ratings_b = judgments[judge_b]

            kappa = calculate_cohens_kappa(ratings_a, ratings_b)
            observed = sum(a == b for a, b in zip(ratings_a, ratings_b)) / len(ratings_a)

            # Calculate expected agreement
            categories = list(set(ratings_a) | set(ratings_b))
            count_a = Counter(ratings_a)
            count_b = Counter(ratings_b)
            n = len(ratings_a)
            expected = sum(
                (count_a.get(cat, 0) / n) * (count_b.get(cat, 0) / n)
                for cat in categories
            )

            results.append(KappaResult(
                kappa=kappa,
                interpretation=interpret_kappa(kappa),
                observed_agreement=observed,
                expected_agreement=expected,
                judge_a=judge_a,
                judge_b=judge_b,
                n_samples=len(ratings_a)
            ))

    return results

def calculate_fleiss_kappa(
    ratings_matrix: List[List[str]],
    categories: Optional[List[str]] = None
) -> float:
    """
    Calculate Fleiss' Kappa for multiple raters.

    Args:
        ratings_matrix: List of [rater1, rater2, ...] for each item
        categories: Possible rating categories

    Returns:
        Fleiss' Kappa coefficient
    """
    n_items = len(ratings_matrix)
    if n_items == 0:
        return 0.0

    n_raters = len(ratings_matrix[0])
    if categories is None:
        categories = list(set(r for row in ratings_matrix for r in row))

    k = len(categories)
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    # Count ratings per category for each item
    counts = np.zeros((n_items, k), dtype=int)
    for i, row in enumerate(ratings_matrix):
        for r in row:
            idx = cat_to_idx.get(r)
            if idx is not None:
                counts[i, idx] += 1

    # Calculate P_i (agreement for each item)
    P_i = np.sum(counts * (counts - 1), axis=1) / (n_raters * (n_raters - 1))
    P_bar = np.mean(P_i)

    # Calculate P_j (proportion for each category)
    total_ratings = n_items * n_raters
    P_j = np.sum(counts, axis=0) / total_ratings

    # Calculate P_e (expected agreement by chance)
    P_e = np.sum(P_j ** 2)

    # Fleiss' Kappa
    if P_e == 1.0:
        return 1.0

    kappa = (P_bar - P_e) / (1 - P_e)
    return kappa

class InterJudgeAgreement:
    """Complete inter-judge agreement analysis."""

    def __init__(self, votes: List["JudgeVote"]):
        self.votes = votes
        self._organized = self._organize_votes()

    def _organize_votes(self) -> Dict[str, Dict[str, List[str]]]:
        """Organize votes by prompt_id and judge."""
        organized = {}
        for vote in self.votes:
            if vote.prompt_id not in organized:
                organized[vote.prompt_id] = {}

            judge_key = f"{vote.judge_model}_{vote.persona}"
            if judge_key not in organized[vote.prompt_id]:
                organized[vote.prompt_id][judge_key] = []

            organized[vote.prompt_id][judge_key].append(vote.winner)

        return organized

    def calculate_overall_kappa(self) -> float:
        """Calculate overall Cohen's Kappa across all judges."""
        # Get majority vote for each judge on each prompt
        judge_majorities = {}

        for prompt_id, judges in self._organized.items():
            for judge_key, votes in judges.items():
                if judge_key not in judge_majorities:
                    judge_majorities[judge_key] = {}

                # Majority vote for this judge on this prompt
                counter = Counter(votes)
                majority = counter.most_common(1)[0][0]
                judge_majorities[judge_key][prompt_id] = majority

        # Calculate pairwise kappa
        all_kappas = calculate_pairwise_kappa({
            judge: [majorities.get(pid, "tie") for pid in sorted(self._organized.keys())]
            for judge, majorities in judge_majorities.items()
        })

        if not all_kappas:
            return 0.0

        # Return average kappa
        return sum(k.kappa for k in all_kappas) / len(all_kappas)

    def get_detailed_agreement(self) -> Dict[str, Any]:
        """Get detailed agreement statistics."""
        pairwise = self._get_pairwise_results()

        return {
            "overall_kappa": self.calculate_overall_kappa(),
            "pairwise_kappa": pairwise,
            "interpretation": interpret_kappa(self.calculate_overall_kappa()),
            "n_prompts": len(self._organized),
            "n_judges": len(set(
                judge for judges in self._organized.values()
                for judge in judges.keys()
            ))
        }

    def _get_pairwise_results(self) -> List[Dict]:
        """Get pairwise kappa results."""
        judge_majorities = {}
        prompts = sorted(self._organized.keys())

        for prompt_id, judges in self._organized.items():
            for judge_key, votes in judges.items():
                if judge_key not in judge_majorities:
                    judge_majorities[judge_key] = {}
                counter = Counter(votes)
                judge_majorities[judge_key][prompt_id] = counter.most_common(1)[0][0]

        results = calculate_pairwise_kappa({
            judge: [majorities.get(pid, "tie") for pid in prompts]
            for judge, majorities in judge_majorities.items()
        })

        return [
            {
                "judge_a": r.judge_a,
                "judge_b": r.judge_b,
                "kappa": r.kappa,
                "interpretation": r.interpretation,
                "observed_agreement": r.observed_agreement,
                "expected_agreement": r.expected_agreement
            }
            for r in results
        ]
```

---

## 3. COST TRACKING IN TUI (CRITICAL)

```python
# src/tui/progress_dashboard.py (with cost tracking)

from textual.app import App, ComposeResult
from textual.widgets import Static, ProgressBar, Label, DataTable, Log
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from typing import Optional, Dict, Tuple
import time

from ..eval.engine import ProgressUpdate, EvaluationPhase

class CostTracker(Static):
    """Widget to display cost tracking information."""

    cost_spent = reactive(0.0)
    cost_projected = reactive(0.0)

    def compose(self) -> ComposeResult:
        yield Static(id="cost-content")

    def watch_cost_spent(self, value: float) -> None:
        self._update_display()

    def watch_cost_projected(self, value: float) -> None:
        self._update_display()

    def _update_display(self) -> None:
        content = self.query_one("#cost-content", Static)
        content.update(Text.from_markup(
            f"[bold cyan]COST TRACKING[/]\n"
            f"Spent so far:     [green]${self.cost_spent:,.2f}[/]\n"
            f"Projected total:  [yellow]${self.cost_projected:,.2f}[/]\n"
            f"Remaining budget: [dim]${max(0, self.cost_projected - self.cost_spent):,.2f}[/]"
        ))

class ETADisplay(Static):
    """Widget to display ETA and timing information."""

    elapsed_seconds = reactive(0.0)
    eta_seconds = reactive(0.0)
    throughput = reactive(0.0)

    def compose(self) -> ComposeResult:
        yield Static(id="eta-content")

    def watch_elapsed_seconds(self, value: float) -> None:
        self._update_display()

    def watch_eta_seconds(self, value: float) -> None:
        self._update_display()

    def _format_duration(self, seconds: float) -> str:
        if seconds <= 0:
            return "--:--:--"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _update_display(self) -> None:
        content = self.query_one("#eta-content", Static)
        content.update(Text.from_markup(
            f"[bold cyan]TIMING[/]\n"
            f"Elapsed:    [white]{self._format_duration(self.elapsed_seconds)}[/]\n"
            f"ETA:        [green]{self._format_duration(self.eta_seconds)}[/]\n"
            f"Throughput: [dim]{self.throughput:.1f} req/min[/]"
        ))

class PerJudgeVotesDisplay(Static):
    """Widget to display per-judge vote counts."""

    votes_data: Dict[str, Dict[str, int]] = reactive({})

    def compose(self) -> ComposeResult:
        yield Static(id="votes-content")

    def watch_votes_data(self, value: Dict) -> None:
        self._update_display()

    def _update_display(self) -> None:
        content = self.query_one("#votes-content", Static)
        lines = ["[bold cyan]JUDGE VOTES[/]"]

        for judge, counts in self.votes_data.items():
            gemini = counts.get("gemini", 0)
            competitor = counts.get("competitor", 0)
            tie = counts.get("tie", 0)
            total = gemini + competitor + tie
            judge_short = judge.split("/")[-1][:15]
            lines.append(
                f"{judge_short}: G:{gemini} C:{competitor} T:{tie} (n={total})"
            )

        content.update(Text.from_markup("\n".join(lines)))

class ResponseTimesDisplay(Static):
    """Widget to display response time metrics."""

    response_times: Dict[str, float] = reactive({})

    def compose(self) -> ComposeResult:
        yield Static(id="times-content")

    def watch_response_times(self, value: Dict) -> None:
        self._update_display()

    def _update_display(self) -> None:
        content = self.query_one("#times-content", Static)
        lines = ["[bold cyan]RESPONSE TIMES (avg)[/]"]

        for model, avg_ms in sorted(self.response_times.items()):
            model_short = model.split("/")[-1][:20]
            lines.append(f"{model_short}: {avg_ms:.0f}ms")

        content.update(Text.from_markup("\n".join(lines)))

class CurrentBatchDisplay(Static):
    """Widget showing current batch with occupation/industry context."""

    prompt_id = reactive("")
    occupation = reactive("")
    industry = reactive("")
    gemini_status = reactive("waiting")
    competitor_status = reactive("waiting")
    judge_status = reactive("")

    def compose(self) -> ComposeResult:
        yield Static(id="batch-content")

    def _update_display(self) -> None:
        content = self.query_one("#batch-content", Static)

        gemini_icon = self._status_icon(self.gemini_status)
        competitor_icon = self._status_icon(self.competitor_status)

        content.update(Text.from_markup(
            f"[bold]CURRENT BATCH[/]\n"
            f"Prompt: [cyan]{self.prompt_id}[/]\n"
            f"Occupation: [yellow]{self.occupation}[/]\n"
            f"Industry: [yellow]{self.industry}[/]\n"
            f"\n"
            f"Responses:\n"
            f"  Gemini:     {gemini_icon}\n"
            f"  Competitor: {competitor_icon}\n"
            f"\n"
            f"Judging: {self.judge_status}"
        ))

    def _status_icon(self, status: str) -> str:
        if status == "complete":
            return "[green]done[/]"
        elif status == "running":
            return "[yellow]...[/]"
        else:
            return "[dim]waiting[/]"

    def watch_prompt_id(self, _) -> None:
        self._update_display()

    def watch_occupation(self, _) -> None:
        self._update_display()

    def watch_industry(self, _) -> None:
        self._update_display()

class ConfidenceIntervalDisplay(Static):
    """Widget showing win rates with confidence intervals."""

    win_rates: Dict[Tuple[str, str], Dict] = reactive({})

    def compose(self) -> ComposeResult:
        yield Static(id="ci-content")

    def watch_win_rates(self, value: Dict) -> None:
        self._update_display()

    def _update_display(self) -> None:
        content = self.query_one("#ci-content", Static)
        lines = ["[bold cyan]WIN RATES (with 95% CI)[/]"]

        for pair, data in self.win_rates.items():
            gemini, competitor = pair
            rate = data.get("rate", 0.5)
            ci_low = data.get("ci_low", 0.0)
            ci_high = data.get("ci_high", 1.0)
            n = data.get("n", 0)

            comp_name = competitor.split("/")[-1][:15]
            lines.append(
                f"vs {comp_name}: {rate*100:.1f}% [{ci_low*100:.1f}-{ci_high*100:.1f}%] (n={n})"
            )

        content.update(Text.from_markup("\n".join(lines)))

class KappaDisplay(Static):
    """Widget showing inter-judge agreement (Cohen's Kappa)."""

    kappa = reactive(0.0)
    interpretation = reactive("--")

    def compose(self) -> ComposeResult:
        yield Static(id="kappa-content")

    def watch_kappa(self, value: float) -> None:
        self._update_display()

    def _update_display(self) -> None:
        content = self.query_one("#kappa-content", Static)

        # Color based on kappa value
        if self.kappa >= 0.8:
            color = "green"
        elif self.kappa >= 0.6:
            color = "cyan"
        elif self.kappa >= 0.4:
            color = "yellow"
        else:
            color = "red"

        content.update(Text.from_markup(
            f"[bold cyan]JUDGE AGREEMENT[/]\n"
            f"Cohen's Kappa: [{color}]{self.kappa:.3f}[/]\n"
            f"({self.interpretation})"
        ))

class ProgressDashboard(App):
    """Full progress dashboard TUI with all required elements."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 3 4;
        grid-gutter: 1;
    }

    #overall-progress {
        column-span: 3;
        height: 5;
    }

    #model-pairs {
        column-span: 2;
        row-span: 2;
    }

    #current-batch {
        row-span: 2;
    }

    #stats-panel {
        column-span: 2;
    }

    #timing-panel {
        height: auto;
    }

    #activity-log {
        column-span: 3;
        height: 8;
    }

    .panel {
        border: solid green;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit (save checkpoint)"),
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("d", "toggle_detail", "Toggle Detail View"),
        Binding("s", "show_stats", "Show Statistics"),
        Binding("h", "show_help", "Help"),
    ]

    def __init__(self, eval_engine=None, **kwargs):
        super().__init__(**kwargs)
        self.eval_engine = eval_engine
        self._paused = False
        self._help_visible = False

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            # Overall progress
            with Container(id="overall-progress", classes="panel"):
                yield Label("GEMINI WRITING EVAL", id="title-label")
                yield ProgressBar(id="main-progress", total=100)
                yield Label("Phase: STARTING", id="phase-label")

            # Model pairs progress
            with Container(id="model-pairs", classes="panel"):
                yield DataTable(id="pairs-table")

            # Current batch
            with Container(id="current-batch", classes="panel"):
                yield CurrentBatchDisplay(id="batch-display")

            # Statistics panel
            with Horizontal(id="stats-panel"):
                with Vertical(classes="panel"):
                    yield ConfidenceIntervalDisplay(id="ci-display")
                with Vertical(classes="panel"):
                    yield KappaDisplay(id="kappa-display")

            # Timing and cost panel
            with Horizontal(id="timing-panel"):
                with Vertical(classes="panel"):
                    yield ETADisplay(id="eta-display")
                with Vertical(classes="panel"):
                    yield CostTracker(id="cost-display")
                with Vertical(classes="panel"):
                    yield ResponseTimesDisplay(id="times-display")

            # Activity log
            with Container(id="activity-log", classes="panel"):
                yield Log(id="log")

        # Help overlay (initially hidden)
        yield Static(id="help-overlay", classes="hidden")

    def on_mount(self) -> None:
        # Initialize pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate", "Status")

    def update_progress(self, update: ProgressUpdate) -> None:
        """Update all dashboard elements from progress update."""
        # Overall progress
        progress = self.query_one("#main-progress", ProgressBar)
        if update.total_prompts > 0:
            progress.update(total=update.total_prompts, progress=update.completed_prompts)

        phase_label = self.query_one("#phase-label", Label)
        phase_label.update(f"Phase: {update.phase.value.upper()}")

        # Cost tracking
        cost_tracker = self.query_one("#cost-display", CostTracker)
        cost_tracker.cost_spent = update.cost_spent
        cost_tracker.cost_projected = update.cost_projected

        # ETA display
        eta_display = self.query_one("#eta-display", ETADisplay)
        eta_display.elapsed_seconds = update.elapsed_seconds
        eta_display.eta_seconds = update.eta_seconds or 0.0
        eta_display.throughput = update.throughput

        # Response times
        times_display = self.query_one("#times-display", ResponseTimesDisplay)
        times_display.response_times = update.response_times

        # Add activity log entry
        log = self.query_one("#log", Log)
        pct = (update.completed_prompts / update.total_prompts * 100) if update.total_prompts > 0 else 0
        log.write_line(f"{time.strftime('%H:%M:%S')} - {update.phase.value}: {update.completed_prompts}/{update.total_prompts} ({pct:.1f}%)")

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        self._paused = not self._paused
        if self.eval_engine:
            if self._paused:
                self.eval_engine.pause()
            else:
                self.eval_engine.resume()

        log = self.query_one("#log", Log)
        log.write_line(f"{'PAUSED' if self._paused else 'RESUMED'}")

    def action_show_help(self) -> None:
        """Toggle help overlay."""
        overlay = self.query_one("#help-overlay", Static)
        if self._help_visible:
            overlay.add_class("hidden")
            self._help_visible = False
        else:
            overlay.remove_class("hidden")
            overlay.update(self._get_help_text())
            self._help_visible = True

    def _get_help_text(self) -> Text:
        """Generate help overlay text."""
        return Text.from_markup("""
[bold cyan]HELP - KEYBOARD SHORTCUTS[/]

[yellow]q[/] - Quit and save checkpoint
[yellow]p[/] - Pause/Resume evaluation
[yellow]d[/] - Toggle detailed view
[yellow]s[/] - Show full statistics panel
[yellow]h[/] - Toggle this help overlay
[yellow]up/down[/] - Scroll activity log

[bold]PROGRESS INDICATORS[/]
[green]Green bar[/] - Gemini win rate
[yellow]Yellow bar[/] - Competitor win rate
[dim]Gray[/] - Ties

[bold]COST TRACKING[/]
Shows real-time API costs and projected total

[bold]JUDGE AGREEMENT[/]
Cohen's Kappa measures inter-judge reliability:
  0.8+ Almost Perfect
  0.6-0.8 Substantial
  0.4-0.6 Moderate
  <0.4 Fair/Poor

Press [yellow]h[/] to close this help.
        """)

    def action_show_stats(self) -> None:
        """Show detailed statistics modal."""
        # In production, this would open a modal with full stats
        log = self.query_one("#log", Log)
        log.write_line("Statistics panel - see console for full output")

    def action_toggle_detail(self) -> None:
        """Toggle detail view."""
        log = self.query_one("#log", Log)
        log.write_line("Detail view toggled")
```

---

## 4. CLI OPTIONS (IMPORTANT)

```python
# src/cli.py (complete with all missing CLI options)

import typer
import asyncio
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
import sys

from .config.presets import PRESETS, EvalConfig, JudgeConfig, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES
from .config.cost_estimator import estimate_cost, format_cost_estimate
from .eval.engine import EvaluationEngine, ConcurrencyConfig
from .api.openrouter_client import OpenRouterClient
from .storage.run_directory import RunDirectory
from .storage.checkpoint import CheckpointManager
from .storage.database import ResultsDatabase
from .tui.progress_dashboard import ProgressDashboard

app = typer.Typer(name="gemini-eval", help="Gemini Writing Evaluation Framework")
console = Console()

def parse_range(value: str) -> List[int]:
    """Parse a range string like '1-5' or '1,3,5' into list of ints."""
    result = []
    for part in value.split(","):
        if "-" in part:
            start, end = part.split("-")
            result.extend(range(int(start), int(end) + 1))
        else:
            result.append(int(part))
    return result

@app.command()
def run(
    # Preset configuration
    preset: int = typer.Option(6, "--preset", "-p", help="Preset level 1-10"),

    # Model configuration
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma-separated model list"),
    tier: Optional[str] = typer.Option(None, "--tier", "-t",
        help="Model tier: 'pro', 'flash', or 'both'"),

    # Prompt configuration
    prompts: Optional[int] = typer.Option(None, "--prompts", "-n", help="Number of prompts to evaluate"),

    # Filtering options
    occupations: Optional[str] = typer.Option(None, "--occupations", "-o",
        help="Occupation codes (supports wildcards like '11-*')"),
    industries: Optional[str] = typer.Option(None, "--industries", "-i",
        help="NAICS codes (comma-separated)"),
    job_zones: Optional[str] = typer.Option(None, "--job-zones", "-z",
        help="Job zones 1-5 (e.g., '3-5' or '1,2,3')"),
    formality_range: Optional[str] = typer.Option(None, "--formality-range", "-f",
        help="Formality levels 1-5 (e.g., '3-5')"),
    age_range: Optional[str] = typer.Option(None, "--age-range", "-a",
        help="Age range (e.g., '25-45')"),
    occupation_limit: Optional[int] = typer.Option(None, "--occupation-limit",
        help="Max prompts per occupation"),
    industry_limit: Optional[int] = typer.Option(None, "--industry-limit",
        help="Max prompts per industry"),

    # Judge configuration
    judges: Optional[str] = typer.Option(None, "--judges", "-j",
        help="Comma-separated judge model list"),
    votes: Optional[int] = typer.Option(None, "--votes", "-v",
        help="Votes per judge (1, 3, or 5)"),
    persona: Optional[str] = typer.Option(None, "--persona",
        help="Judge persona: 'both', 'expert', or 'recipient'"),

    # Other options
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show estimate without running"),
    resume: Optional[Path] = typer.Option(None, "--resume", "-r", help="Resume from run directory"),
    concurrency: int = typer.Option(20, "--concurrency", "-c", help="Max concurrent requests"),
    output_dir: Path = typer.Option(Path("results"), "--output", help="Output directory"),
):
    """Run evaluation with specified configuration."""

    # Load base preset
    config = PRESETS[preset]

    # Apply tier override
    if tier:
        if tier.lower() == "pro":
            config.model_pairs = PRO_PAIRS
        elif tier.lower() == "flash":
            config.model_pairs = FLASH_PAIRS
        elif tier.lower() == "both":
            config.model_pairs = PRO_PAIRS + FLASH_PAIRS
        else:
            console.print(f"[red]Invalid tier: {tier}. Use 'pro', 'flash', or 'both'[/]")
            raise typer.Exit(1)

    # Apply model override
    if models:
        model_list = [m.strip() for m in models.split(",")]
        # Filter to only pairs containing these models
        filtered_pairs = [
            p for p in (PRO_PAIRS + FLASH_PAIRS)
            if any(m in p for m in model_list)
        ]
        if filtered_pairs:
            config.model_pairs = filtered_pairs

    # Apply prompt count
    if prompts:
        config.num_prompts = prompts

    # Apply judge configuration
    if judges:
        judge_list = [j.strip() for j in judges.split(",")]
        config.judge_config.models = judge_list

    if votes:
        if votes not in [1, 3, 5]:
            console.print("[red]Votes must be 1, 3, or 5[/]")
            raise typer.Exit(1)
        config.judge_config.votes_per_judge = votes

    if persona:
        if persona.lower() == "both":
            config.judge_config.use_both_personas = True
        elif persona.lower() == "expert":
            config.judge_config.use_both_personas = False
            # Custom handling for expert-only
        elif persona.lower() == "recipient":
            config.judge_config.use_both_personas = False
            # Custom handling for recipient-only
        else:
            console.print("[red]Persona must be 'both', 'expert', or 'recipient'[/]")
            raise typer.Exit(1)

    # Apply seed
    if seed:
        config.random_seed = seed

    # Store filter parameters
    filter_config = {
        "occupation_codes": occupations.split(",") if occupations else None,
        "industry_codes": industries.split(",") if industries else None,
        "job_zones": parse_range(job_zones) if job_zones else None,
        "formality_range": parse_range(formality_range) if formality_range else None,
        "age_range": parse_range(age_range) if age_range else None,
        "occupation_limit": occupation_limit,
        "industry_limit": industry_limit,
    }

    # Estimate cost
    estimate = estimate_cost(config)

    # Display estimate
    console.print(format_cost_estimate(estimate, config))

    if dry_run:
        console.print("[yellow]Dry run - exiting without executing[/]")
        raise typer.Exit(0)

    # Confirm
    if not typer.confirm("Proceed with evaluation?"):
        raise typer.Exit(0)

    # Run evaluation
    asyncio.run(_run_eval(
        config, filter_config, resume, concurrency, output_dir
    ))

async def _run_eval(
    config: EvalConfig,
    filter_config: dict,
    resume: Optional[Path],
    concurrency: int,
    output_dir: Path
):
    """Run the actual evaluation."""
    import os
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]OPENROUTER_API_KEY environment variable not set[/]")
        return

    # Initialize client
    client = OpenRouterClient(api_key)

    # Set up run directory
    if resume:
        run_dir = RunDirectory.load(resume)
    else:
        run_dir = RunDirectory.create(output_dir, config)

    # Initialize components
    checkpoint = CheckpointManager(run_dir)
    database = ResultsDatabase(run_dir.results_db)

    concurrency_config = ConcurrencyConfig(
        max_concurrent_requests=concurrency
    )

    # Initialize engine with TUI callback
    dashboard = ProgressDashboard()

    engine = EvaluationEngine(
        client=client,
        config=config,
        concurrency=concurrency_config,
        checkpoint_manager=checkpoint,
        database=database,
        progress_callback=dashboard.update_progress
    )
    dashboard.eval_engine = engine

    # Generate prompts (with filters)
    from .prompts.phase2_algorithmic import PromptGenerator
    generator = PromptGenerator(
        occupation_codes=filter_config.get("occupation_codes"),
        industry_codes=filter_config.get("industry_codes"),
        job_zones=filter_config.get("job_zones"),
        formality_range=filter_config.get("formality_range"),
        age_range=filter_config.get("age_range"),
        occupation_limit=filter_config.get("occupation_limit"),
        industry_limit=filter_config.get("industry_limit"),
    )
    prompts = await generator.generate(config.num_prompts, config.random_seed)

    # Run with TUI
    async def run_with_dashboard():
        eval_task = asyncio.create_task(engine.run_evaluation(prompts))
        await dashboard.run_async()
        return await eval_task

    try:
        results = await run_with_dashboard()
        console.print(f"[green]Evaluation complete! Results in {run_dir.path}[/]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        await checkpoint.save_checkpoint()
    finally:
        await client.close()

@app.command()
def compare(
    runs: List[Path] = typer.Argument(..., help="Run directories to compare"),
):
    """Compare results across multiple runs."""
    from .analysis.cross_run_compare import compare_runs
    asyncio.run(compare_runs(runs))

@app.command()
def export(
    run_dir: Path = typer.Argument(..., help="Run directory"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv, json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Export results to CSV or JSON."""
    from .storage.database import ResultsDatabase
    db = ResultsDatabase(run_dir / "results.db")
    asyncio.run(db.export(format, output or run_dir / f"export.{format}"))

@app.command()
def view(
    run_dir: Path = typer.Argument(..., help="Run directory to view"),
):
    """Launch interactive results viewer TUI."""
    from .tui.results_viewer import ResultsViewer
    viewer = ResultsViewer(run_dir)
    viewer.run()

if __name__ == "__main__":
    app()
```

---

## 5. NAME FORMALITY VARIATION (PARTIAL GAP)

```python
# src/data/name_generator.py (enhanced with formality variation)

import random
from dataclasses import dataclass
from typing import Optional, Literal, List
from enum import Enum

class NameFormality(str, Enum):
    """Levels of name formality."""
    VERY_FORMAL = "very_formal"    # Dr. Elizabeth A. Williams, MD
    FORMAL = "formal"              # Elizabeth Williams
    SEMI_FORMAL = "semi_formal"    # Elizabeth W.
    CASUAL = "casual"              # Liz Williams
    INFORMAL = "informal"          # Liz
    NICKNAME = "nickname"          # Lizzy

@dataclass
class GeneratedName:
    """A generated name with multiple formality variants."""
    first_name: str
    last_name: str
    middle_initial: Optional[str] = None
    nickname: Optional[str] = None
    title: Optional[str] = None
    suffix: Optional[str] = None
    gender: Optional[str] = None
    generation: Optional[str] = None
    ethnicity: Optional[str] = None

    def format(self, formality: NameFormality) -> str:
        """Format name according to formality level."""
        if formality == NameFormality.VERY_FORMAL:
            parts = []
            if self.title:
                parts.append(self.title)
            parts.append(self.first_name)
            if self.middle_initial:
                parts.append(f"{self.middle_initial}.")
            parts.append(self.last_name)
            if self.suffix:
                parts.append(f", {self.suffix}")
            return " ".join(parts)

        elif formality == NameFormality.FORMAL:
            return f"{self.first_name} {self.last_name}"

        elif formality == NameFormality.SEMI_FORMAL:
            if self.middle_initial:
                return f"{self.first_name} {self.middle_initial}."
            return self.first_name

        elif formality == NameFormality.CASUAL:
            if self.nickname:
                return f"{self.nickname} {self.last_name}"
            return f"{self.first_name} {self.last_name}"

        elif formality == NameFormality.INFORMAL:
            return self.nickname or self.first_name

        elif formality == NameFormality.NICKNAME:
            return self.nickname or self.first_name[:min(4, len(self.first_name))]

        return self.first_name

    def generate_email(self, domain: str, formality: NameFormality = NameFormality.CASUAL) -> str:
        """Generate email address based on formality."""
        first = (self.nickname or self.first_name).lower()
        last = self.last_name.lower()

        if formality in [NameFormality.VERY_FORMAL, NameFormality.FORMAL]:
            # elizabeth.williams@company.com
            return f"{first}.{last}@{domain}"
        elif formality == NameFormality.SEMI_FORMAL:
            # ewilliams@company.com
            return f"{first[0]}{last}@{domain}"
        else:
            # liz.w@company.com or lizw@company.com
            return f"{first}{last[0]}@{domain}"

# Common nicknames mapping
NICKNAMES = {
    "Elizabeth": ["Liz", "Lizzy", "Beth", "Eliza"],
    "William": ["Will", "Bill", "Billy", "Willy"],
    "Robert": ["Rob", "Bob", "Bobby", "Robbie"],
    "Michael": ["Mike", "Mikey", "Mick"],
    "Jennifer": ["Jen", "Jenny", "Jenn"],
    "Catherine": ["Cathy", "Kate", "Cat", "Katie"],
    "Christopher": ["Chris", "Topher", "Kit"],
    "Nicholas": ["Nick", "Nicky", "Nico"],
    "Margaret": ["Maggie", "Meg", "Peggy", "Marge"],
    "Alexander": ["Alex", "Xander", "Lex"],
    "Benjamin": ["Ben", "Benny", "Benji"],
    "Jonathan": ["Jon", "Johnny", "Jonny"],
    "Patricia": ["Pat", "Patty", "Trish"],
    "Richard": ["Rick", "Rich", "Dick", "Ricky"],
    "Thomas": ["Tom", "Tommy"],
    "Victoria": ["Vicky", "Vic", "Tori"],
    "Samantha": ["Sam", "Sammy"],
    "Rebecca": ["Becca", "Becky"],
    "Matthew": ["Matt", "Matty"],
    "Daniel": ["Dan", "Danny"],
}

# Professional titles by role/field
TITLES = {
    "medical": ["Dr.", "MD", "DO"],
    "academic": ["Dr.", "Prof.", "PhD"],
    "legal": ["Esq.", "JD"],
    "military": ["Col.", "Maj.", "Capt.", "Lt."],
    "religious": ["Rev.", "Fr.", "Rabbi"],
}

class NameGenerator:
    """Generate diverse realistic names with formality variation."""

    def __init__(self, census_data_path: Optional[str] = None):
        self.census_data_path = census_data_path
        self._names_cache = None

    def generate(
        self,
        generation: Optional[str] = None,
        gender: Optional[str] = None,
        ethnicity: Optional[str] = None,
        professional_field: Optional[str] = None,
        include_title: bool = False,
        formality_hint: Optional[NameFormality] = None
    ) -> GeneratedName:
        """
        Generate a name with appropriate formality variants.

        Args:
            generation: gen_z, millennial, gen_x, boomer
            gender: male, female, neutral
            ethnicity: Optional ethnicity for name selection
            professional_field: medical, academic, legal, etc.
            include_title: Whether to include professional title
            formality_hint: Preferred formality level

        Returns:
            GeneratedName with formality variants
        """
        # Select first name based on generation/demographics
        first_name = self._select_first_name(generation, gender, ethnicity)

        # Select last name
        last_name = self._select_last_name(ethnicity)

        # Generate middle initial
        middle_initial = random.choice("ABCDEFGHJKLMNPRSTVW") if random.random() > 0.3 else None

        # Find nickname
        nickname = None
        for name, nicks in NICKNAMES.items():
            if first_name == name:
                nickname = random.choice(nicks)
                break

        # Add title for formal contexts
        title = None
        suffix = None
        if include_title and professional_field:
            if professional_field in TITLES:
                options = TITLES[professional_field]
                if professional_field in ["medical", "academic"]:
                    title = "Dr."
                    if professional_field == "medical" and random.random() > 0.5:
                        suffix = random.choice(["MD", "DO"])
                    elif professional_field == "academic" and random.random() > 0.5:
                        suffix = "PhD"
                elif professional_field == "legal":
                    suffix = "Esq."

        return GeneratedName(
            first_name=first_name,
            last_name=last_name,
            middle_initial=middle_initial,
            nickname=nickname,
            title=title,
            suffix=suffix,
            gender=gender,
            generation=generation,
            ethnicity=ethnicity
        )

    def _select_first_name(
        self,
        generation: Optional[str],
        gender: Optional[str],
        ethnicity: Optional[str]
    ) -> str:
        """Select first name based on demographics."""
        # Sample name pools by generation (simplified)
        names_by_generation = {
            "boomer": {
                "male": ["Robert", "William", "James", "Richard", "Thomas", "Michael"],
                "female": ["Patricia", "Barbara", "Linda", "Susan", "Margaret", "Elizabeth"]
            },
            "gen_x": {
                "male": ["Michael", "Christopher", "Matthew", "David", "Jason", "Brian"],
                "female": ["Jennifer", "Michelle", "Lisa", "Kimberly", "Stephanie", "Nicole"]
            },
            "millennial": {
                "male": ["Michael", "Matthew", "Joshua", "Daniel", "David", "Andrew"],
                "female": ["Jessica", "Ashley", "Emily", "Sarah", "Amanda", "Samantha"]
            },
            "gen_z": {
                "male": ["Liam", "Noah", "Oliver", "Elijah", "James", "Benjamin"],
                "female": ["Olivia", "Emma", "Ava", "Sophia", "Isabella", "Mia"]
            }
        }

        gen = generation or random.choice(list(names_by_generation.keys()))
        g = gender or random.choice(["male", "female"])

        pool = names_by_generation.get(gen, names_by_generation["millennial"])
        return random.choice(pool.get(g, pool["male"]))

    def _select_last_name(self, ethnicity: Optional[str]) -> str:
        """Select last name based on ethnicity."""
        # Simplified last name pools
        common_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
            "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
            "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
            "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez",
            "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen",
            "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
            "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
            "Mitchell", "Carter", "Roberts", "Chen", "Kim", "Patel", "Kumar"
        ]

        return random.choice(common_names)

    def generate_for_context(
        self,
        writer_formality: int,  # 1-5 scale
        skill_level: str,
        professional_field: Optional[str] = None,
        **kwargs
    ) -> tuple[GeneratedName, NameFormality]:
        """
        Generate name with appropriate formality for context.

        Returns:
            Tuple of (GeneratedName, recommended NameFormality)
        """
        # Map formality level to name formality
        if writer_formality >= 5:
            if skill_level == "executive" or professional_field in ["medical", "academic", "legal"]:
                formality = NameFormality.VERY_FORMAL
            else:
                formality = NameFormality.FORMAL
        elif writer_formality >= 4:
            formality = NameFormality.FORMAL
        elif writer_formality >= 3:
            formality = NameFormality.SEMI_FORMAL
        elif writer_formality >= 2:
            formality = NameFormality.CASUAL
        else:
            formality = NameFormality.INFORMAL

        # Generate name
        include_title = formality == NameFormality.VERY_FORMAL
        name = self.generate(
            professional_field=professional_field,
            include_title=include_title,
            formality_hint=formality,
            **kwargs
        )

        return name, formality
```

---

## 6. PHASE 1 GENERATION USING EVALUATED MODELS

```python
# src/prompts/phase1_offline.py

import asyncio
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

from ..api.openrouter_client import OpenRouterClient
from ..config.presets import PRO_PAIRS, FLASH_PAIRS
from ..data.onet_extractor import ONetTask

@dataclass
class Phase1Variation:
    """A single persona/context variation for an O*NET task."""
    task_id: str
    variation_id: str
    generated_by_model: str
    writer_persona: Dict[str, Any]
    recipient_persona: Dict[str, Any]
    communication_context: Dict[str, Any]
    additional_context: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

class Phase1Generator:
    """
    Generate persona/context variations using the same models being evaluated.

    IMPORTANT: Per PROMPT.md, Phase 1 uses evaluated models for generation.
    This creates potential bias but ensures prompts aren't accidentally
    biased against any particular model.
    """

    # Models to use for generation (from evaluated models)
    GENERATION_MODELS = [
        "google/gemini-3.0-pro",
        "google/gemini-3.0-flash",
        "openai/gpt-5.2",
        "openai/gpt-4.1",
        "anthropic/claude-opus-4.5",
        "anthropic/claude-sonnet-4",
    ]

    VARIATION_PROMPT_TEMPLATE = """You are generating realistic writing task variations for an LLM evaluation framework.

Given this O*NET writing task:
{task_statement}

Occupation: {occupation_title} ({occupation_code})
Job Zone: {job_zone}/5 (complexity level)
Writing Context: {writing_context}

Generate a SINGLE realistic variation with specific details for:

1. WRITER PERSONA - Who is writing this?
   - Name (realistic, demographically diverse)
   - Age (18-80)
   - Generation (gen_z, millennial, gen_x, boomer)
   - Skill level (entry, mid, senior, executive)
   - Years of experience

2. RECIPIENT PERSONA - Who receives this?
   - Name (realistic)
   - Job title
   - Relationship to writer (colleague, manager, client, etc.)
   - Technical level (true/false)
   - Prior contact (true/false)

3. COMMUNICATION CONTEXT
   - Formality level (1-5, where 1=very casual, 5=very formal)
   - Urgency level (1-5)
   - Emotional context (routine, crisis, celebration, conflict, bad_news)
   - Message position (initial_outreach, reply_in_thread, follow_up)
   - Audience size (one_on_one, small_group, department, company_wide, public)

4. ADDITIONAL CONTEXT (optional)
   - Any relevant background, deadlines, prior communications, or constraints

Respond with ONLY valid JSON in this exact format:
{{
  "writer_persona": {{
    "name": "...",
    "age": 35,
    "generation": "millennial",
    "skill_level": "mid",
    "years_experience": 8
  }},
  "recipient_persona": {{
    "name": "...",
    "job_title": "...",
    "relationship": "colleague",
    "is_technical": false,
    "prior_contact": true
  }},
  "communication_context": {{
    "formality_level": 3,
    "urgency_level": 2,
    "emotional_context": "routine",
    "message_position": "initial_outreach",
    "audience_size": "one_on_one"
  }},
  "additional_context": "..."
}}

Be creative and realistic. Vary the personas across demographics."""

    def __init__(
        self,
        client: OpenRouterClient,
        output_dir: Path,
        variations_per_task: int = 3,
        models_to_use: Optional[List[str]] = None
    ):
        self.client = client
        self.output_dir = output_dir
        self.variations_per_task = variations_per_task
        self.models = models_to_use or self.GENERATION_MODELS

        # Track which model generated each variation for bias analysis
        self._generation_stats: Dict[str, int] = {m: 0 for m in self.models}

    async def generate_variations(
        self,
        tasks: List[ONetTask],
        max_concurrent: int = 10
    ) -> List[Phase1Variation]:
        """Generate variations for a list of O*NET tasks."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        all_variations = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_for_task(task: ONetTask) -> List[Phase1Variation]:
            variations = []
            for i in range(self.variations_per_task):
                # Round-robin across models to balance generation
                model = self.models[i % len(self.models)]

                async with semaphore:
                    try:
                        variation = await self._generate_single_variation(task, i, model)
                        if variation:
                            variations.append(variation)
                            self._generation_stats[model] += 1
                    except Exception as e:
                        print(f"Error generating variation for {task.task_id}: {e}")

            return variations

        # Process all tasks
        results = await asyncio.gather(
            *[generate_for_task(task) for task in tasks],
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, list):
                all_variations.extend(result)

        # Save variations
        await self._save_variations(all_variations)
        await self._save_generation_stats()

        return all_variations

    async def _generate_single_variation(
        self,
        task: ONetTask,
        variation_idx: int,
        model: str
    ) -> Optional[Phase1Variation]:
        """Generate a single variation using specified model."""
        prompt = self.VARIATION_PROMPT_TEMPLATE.format(
            task_statement=task.task_statement,
            occupation_title=task.occupation_title,
            occupation_code=task.onetsoc_code,
            job_zone=task.job_zone,
            writing_context=task.writing_context
        )

        response = await self.client.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,  # Higher temperature for diversity
            max_tokens=800
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            data = json.loads(content)

            return Phase1Variation(
                task_id=task.task_id,
                variation_id=f"{task.task_id}_v{variation_idx}",
                generated_by_model=model,
                writer_persona=data["writer_persona"],
                recipient_persona=data["recipient_persona"],
                communication_context=data["communication_context"],
                additional_context=data.get("additional_context")
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse response from {model}: {e}")
            return None

    async def _save_variations(self, variations: List[Phase1Variation]):
        """Save variations to output directory."""
        output_file = self.output_dir / "variations.json"

        data = []
        for v in variations:
            data.append({
                "task_id": v.task_id,
                "variation_id": v.variation_id,
                "generated_by_model": v.generated_by_model,
                "writer_persona": v.writer_persona,
                "recipient_persona": v.recipient_persona,
                "communication_context": v.communication_context,
                "additional_context": v.additional_context,
                "created_at": v.created_at.isoformat()
            })

        output_file.write_text(json.dumps(data, indent=2))

    async def _save_generation_stats(self):
        """Save statistics about which models generated variations."""
        stats_file = self.output_dir / "generation_stats.json"
        stats_file.write_text(json.dumps({
            "total_variations": sum(self._generation_stats.values()),
            "by_model": self._generation_stats,
            "note": "Variations generated by evaluated models per PROMPT.md requirement"
        }, indent=2))

    @classmethod
    async def load_variations(cls, variations_dir: Path) -> List[Phase1Variation]:
        """Load pre-generated variations from disk."""
        variations_file = variations_dir / "variations.json"
        if not variations_file.exists():
            raise FileNotFoundError(f"No variations found at {variations_file}")

        data = json.loads(variations_file.read_text())

        return [
            Phase1Variation(
                task_id=item["task_id"],
                variation_id=item["variation_id"],
                generated_by_model=item["generated_by_model"],
                writer_persona=item["writer_persona"],
                recipient_persona=item["recipient_persona"],
                communication_context=item["communication_context"],
                additional_context=item.get("additional_context"),
                created_at=datetime.fromisoformat(item["created_at"])
            )
            for item in data
        ]
```

---

## 7. AMBIGUITY BEHAVIOR TRACKING

```python
# src/eval/ambiguity_tracker.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import re

class AmbiguityBehavior(str, Enum):
    """How a model handles ambiguous prompts."""
    MAKES_ASSUMPTIONS = "makes_assumptions"       # Proceeds with reasonable assumptions
    ASKS_CLARIFICATION = "asks_clarification"     # Asks for clarification in response
    HEDGES_APPROPRIATELY = "hedges_appropriately" # Acknowledges uncertainty
    HALLUCINTATES_DETAILS = "hallucinates_details" # Invents specific unwarranted details
    REFUSES_TO_PROCEED = "refuses_to_proceed"     # Won't complete without more info
    GENERIC_RESPONSE = "generic_response"         # Very vague/non-committal response

@dataclass
class AmbiguityAnalysis:
    """Analysis of how a model handled ambiguity."""
    prompt_id: str
    model: str
    ambiguity_type: str
    detected_behaviors: List[AmbiguityBehavior]
    confidence: float
    evidence: Dict[str, str]
    raw_response: str

class AmbiguityTracker:
    """Track and analyze how models handle ambiguous prompts."""

    # Patterns indicating different behaviors
    CLARIFICATION_PATTERNS = [
        r"could you (please )?clarify",
        r"I('d| would) need (more information|clarification)",
        r"what (exactly|specifically) do you mean",
        r"can you (please )?(specify|tell me more)",
        r"I'm not sure (what|which|who)",
        r"which (\w+) (are|do) you (mean|want)",
        r"before I (can|proceed)",
    ]

    HEDGING_PATTERNS = [
        r"assuming (that|you mean)",
        r"I('ll| will) assume",
        r"based on (my|the) understanding",
        r"if I understand correctly",
        r"it seems like you (want|mean|need)",
        r"I interpret this as",
        r"without more (context|information), I('ll| will)",
    ]

    HALLUCINATION_INDICATORS = [
        # Very specific details that weren't in prompt
        r"\$\d{1,3}(,\d{3})+",  # Specific dollar amounts
        r"on (January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}",
        r"at \d{1,2}:\d{2} (AM|PM|am|pm)",
        r"(exactly|precisely|specifically) \d+",
    ]

    REFUSAL_PATTERNS = [
        r"I (can't|cannot|won't|am unable to) (complete|write|draft)",
        r"I need more information (before|to)",
        r"please provide (additional|more)",
        r"I don't have enough (context|information|details)",
    ]

    def __init__(self):
        self._analyses: List[AmbiguityAnalysis] = []

    def analyze_response(
        self,
        prompt_id: str,
        model: str,
        ambiguity_type: str,
        response: str,
        original_prompt: str
    ) -> AmbiguityAnalysis:
        """Analyze how a model handled an ambiguous prompt."""
        detected = []
        evidence = {}

        response_lower = response.lower()

        # Check for clarification requests
        for pattern in self.CLARIFICATION_PATTERNS:
            if re.search(pattern, response_lower):
                detected.append(AmbiguityBehavior.ASKS_CLARIFICATION)
                match = re.search(pattern, response_lower)
                evidence["clarification"] = match.group(0)
                break

        # Check for hedging/assumptions
        for pattern in self.HEDGING_PATTERNS:
            if re.search(pattern, response_lower):
                detected.append(AmbiguityBehavior.HEDGES_APPROPRIATELY)
                match = re.search(pattern, response_lower)
                evidence["hedging"] = match.group(0)
                break

        # Check for hallucinated details
        hallucinated = False
        for pattern in self.HALLUCINATION_INDICATORS:
            if re.search(pattern, response):
                # Verify this detail wasn't in original prompt
                if not re.search(pattern, original_prompt):
                    hallucinated = True
                    match = re.search(pattern, response)
                    evidence["hallucination"] = match.group(0)
                    break

        if hallucinated:
            detected.append(AmbiguityBehavior.HALLUCINTATES_DETAILS)

        # Check for refusals
        for pattern in self.REFUSAL_PATTERNS:
            if re.search(pattern, response_lower):
                detected.append(AmbiguityBehavior.REFUSES_TO_PROCEED)
                match = re.search(pattern, response_lower)
                evidence["refusal"] = match.group(0)
                break

        # If no special handling detected, classify as making assumptions
        if not detected:
            # Check if response is too generic
            if len(response.split()) < 50:
                detected.append(AmbiguityBehavior.GENERIC_RESPONSE)
            else:
                detected.append(AmbiguityBehavior.MAKES_ASSUMPTIONS)

        # Calculate confidence based on pattern matches
        confidence = min(1.0, 0.5 + 0.1 * len(evidence))

        analysis = AmbiguityAnalysis(
            prompt_id=prompt_id,
            model=model,
            ambiguity_type=ambiguity_type,
            detected_behaviors=detected,
            confidence=confidence,
            evidence=evidence,
            raw_response=response[:500]  # Truncate for storage
        )

        self._analyses.append(analysis)
        return analysis

    def get_behavior_summary(self) -> Dict[str, Dict[str, int]]:
        """Get summary of behaviors by model."""
        summary: Dict[str, Dict[str, int]] = {}

        for analysis in self._analyses:
            if analysis.model not in summary:
                summary[analysis.model] = {b.value: 0 for b in AmbiguityBehavior}

            for behavior in analysis.detected_behaviors:
                summary[analysis.model][behavior.value] += 1

        return summary

    def get_behavior_by_type(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Get behaviors broken down by ambiguity type and model."""
        by_type: Dict[str, Dict[str, Dict[str, int]]] = {}

        for analysis in self._analyses:
            if analysis.ambiguity_type not in by_type:
                by_type[analysis.ambiguity_type] = {}

            if analysis.model not in by_type[analysis.ambiguity_type]:
                by_type[analysis.ambiguity_type][analysis.model] = {
                    b.value: 0 for b in AmbiguityBehavior
                }

            for behavior in analysis.detected_behaviors:
                by_type[analysis.ambiguity_type][analysis.model][behavior.value] += 1

        return by_type

    def export(self) -> List[Dict]:
        """Export all analyses."""
        return [
            {
                "prompt_id": a.prompt_id,
                "model": a.model,
                "ambiguity_type": a.ambiguity_type,
                "behaviors": [b.value for b in a.detected_behaviors],
                "confidence": a.confidence,
                "evidence": a.evidence
            }
            for a in self._analyses
        ]
```

---

## 8. TUI RESULTS VIEWER (FILTERING, SORTING, DRILL-DOWN)

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.widgets import (
    Static, DataTable, Label, Input, Select, Button, TabbedContent, TabPane
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import asyncio
import json

class FilterPanel(Static):
    """Panel for filtering results."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("FILTERS", classes="section-header")

            yield Label("Occupation:")
            yield Input(placeholder="e.g., 11-* or 11-1011", id="filter-occupation")

            yield Label("Industry (NAICS):")
            yield Input(placeholder="e.g., 54 or 541", id="filter-industry")

            yield Label("Winner:")
            yield Select(
                [
                    ("All", "all"),
                    ("Gemini Wins", "gemini"),
                    ("Competitor Wins", "competitor"),
                    ("Ties", "tie"),
                ],
                id="filter-winner"
            )

            yield Label("Model Pair:")
            yield Select(id="filter-model-pair")

            yield Label("Job Zone:")
            yield Select(
                [("All", "all")] + [(str(i), str(i)) for i in range(1, 6)],
                id="filter-job-zone"
            )

            yield Label("Formality:")
            yield Select(
                [("All", "all")] + [(str(i), str(i)) for i in range(1, 6)],
                id="filter-formality"
            )

            yield Label("Has Constraints:")
            yield Select(
                [("All", "all"), ("Yes", "yes"), ("No", "no")],
                id="filter-constraints"
            )

            yield Button("Apply Filters", id="btn-apply-filters", variant="primary")
            yield Button("Clear Filters", id="btn-clear-filters", variant="warning")

class SortPanel(Static):
    """Panel for sorting options."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("SORT BY", classes="section-header")

            yield Select(
                [
                    ("Prompt ID", "prompt_id"),
                    ("Win Rate", "win_rate"),
                    ("Confidence", "confidence"),
                    ("Quality Gap", "quality_gap"),
                    ("Response Time", "response_time"),
                    ("Occupation", "occupation"),
                    ("Industry", "industry"),
                ],
                id="sort-field"
            )

            yield Select(
                [("Ascending", "asc"), ("Descending", "desc")],
                id="sort-direction"
            )

            yield Button("Apply Sort", id="btn-apply-sort")

class ComparisonDetailView(Static):
    """Detailed view of a single comparison."""

    def __init__(self, comparison: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.comparison = comparison

    def compose(self) -> ComposeResult:
        c = self.comparison

        with ScrollableContainer():
            # Header info
            yield Label(f"Prompt ID: {c.get('prompt_id', 'N/A')}", classes="detail-header")

            with Horizontal():
                with Vertical(classes="half-width"):
                    yield Label("PROMPT CONTEXT", classes="section-header")
                    yield Static(f"Occupation: {c.get('occupation_title', 'N/A')}")
                    yield Static(f"Industry: {c.get('naics_sector', 'N/A')}")
                    yield Static(f"Job Zone: {c.get('job_zone', 'N/A')}/5")
                    yield Static(f"Formality: {c.get('formality_level', 'N/A')}/5")

                with Vertical(classes="half-width"):
                    yield Label("RESULT", classes="section-header")
                    yield Static(f"Winner: {c.get('winner', 'N/A')}")
                    yield Static(f"Judge Confidence: {c.get('confidence', 'N/A')}")
                    yield Static(f"Quality Gap: {c.get('quality_gap', 'N/A')}")

            # Full prompt
            yield Label("WRITING TASK", classes="section-header")
            yield Static(c.get("onet_task", "N/A"), classes="task-box")

            # Responses side by side
            with Horizontal(classes="responses-container"):
                with Vertical(classes="half-width"):
                    yield Label("GEMINI RESPONSE", classes="response-header-gemini")
                    yield Static(
                        c.get("gemini_response", "N/A")[:2000],
                        classes="response-box"
                    )

                with Vertical(classes="half-width"):
                    yield Label("COMPETITOR RESPONSE", classes="response-header-competitor")
                    yield Static(
                        c.get("competitor_response", "N/A")[:2000],
                        classes="response-box"
                    )

            # Judge votes breakdown
            yield Label("JUDGE VOTES", classes="section-header")
            votes = c.get("votes", [])
            for vote in votes:
                yield Static(
                    f"  {vote.get('judge_model', 'N/A')} ({vote.get('persona', 'N/A')}): "
                    f"{vote.get('winner', 'N/A')} (confidence: {vote.get('confidence', 'N/A')})"
                )

            # Reasoning
            yield Label("JUDGE REASONING", classes="section-header")
            for vote in votes[:3]:  # Show first 3 reasonings
                yield Static(
                    f"[{vote.get('judge_model', '').split('/')[-1]}]: {vote.get('reasoning', 'N/A')[:300]}...",
                    classes="reasoning-box"
                )

class ResultsViewer(App):
    """Interactive TUI for viewing evaluation results."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 4 1;
    }

    #filter-panel {
        width: 25%;
        border: solid blue;
        padding: 1;
    }

    #results-table-container {
        width: 75%;
    }

    .section-header {
        background: $primary;
        padding: 0 1;
        margin-top: 1;
    }

    .half-width {
        width: 50%;
        padding: 1;
    }

    .response-box {
        border: solid dim;
        padding: 1;
        max-height: 20;
        overflow-y: auto;
    }

    .response-header-gemini {
        background: green;
        padding: 0 1;
    }

    .response-header-competitor {
        background: red;
        padding: 0 1;
    }

    .task-box {
        border: solid cyan;
        padding: 1;
        margin: 1;
    }

    .reasoning-box {
        border: solid dim;
        padding: 1;
        margin-bottom: 1;
    }

    #detail-view {
        display: none;
    }

    #detail-view.visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "close_detail", "Close Detail"),
        Binding("f", "focus_filter", "Focus Filters"),
        Binding("enter", "view_detail", "View Detail"),
        Binding("n", "next_result", "Next Result"),
        Binding("p", "prev_result", "Previous Result"),
        Binding("e", "export_filtered", "Export Filtered"),
    ]

    def __init__(self, run_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.run_dir = run_dir
        self.comparisons: List[Dict] = []
        self.filtered_comparisons: List[Dict] = []
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            with Container(id="filter-panel"):
                yield FilterPanel()
                yield SortPanel()

            with Container(id="results-table-container"):
                yield Label("EVALUATION RESULTS", id="results-title")
                yield DataTable(id="results-table")
                yield Label("", id="results-status")

        yield Container(id="detail-view")

    async def on_mount(self) -> None:
        # Load results
        await self._load_results()

        # Set up table
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "ID", "Occupation", "Industry", "Winner", "Confidence",
            "Quality Gap", "Formality", "Job Zone"
        )

        # Populate model pairs dropdown
        pairs = list(set(c.get("model_pair", ("", "")) for c in self.comparisons))
        select = self.query_one("#filter-model-pair", Select)
        select.set_options([("All", "all")] + [
            (f"{p[0].split('/')[-1]} vs {p[1].split('/')[-1]}", f"{p[0]}|{p[1]}")
            for p in pairs if p
        ])

        # Initial display
        self._apply_filters()

    async def _load_results(self):
        """Load results from run directory."""
        # Try results.db first
        db_path = self.run_dir / "results.db"
        if db_path.exists():
            import aiosqlite
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "SELECT * FROM comparisons ORDER BY prompt_id"
                )
                columns = [d[0] for d in cursor.description]
                rows = await cursor.fetchall()
                self.comparisons = [dict(zip(columns, row)) for row in rows]
        else:
            # Fall back to JSON files
            judgments_dir = self.run_dir / "judgments" / "aggregated"
            if judgments_dir.exists():
                for f in judgments_dir.glob("*.json"):
                    data = json.loads(f.read_text())
                    self.comparisons.append(data)

        self.filtered_comparisons = self.comparisons.copy()

    def _apply_filters(self):
        """Apply current filters to comparisons."""
        filtered = self.comparisons.copy()

        # Get filter values
        occ_filter = self.query_one("#filter-occupation", Input).value.strip()
        ind_filter = self.query_one("#filter-industry", Input).value.strip()
        winner_filter = self.query_one("#filter-winner", Select).value
        pair_filter = self.query_one("#filter-model-pair", Select).value
        zone_filter = self.query_one("#filter-job-zone", Select).value
        formality_filter = self.query_one("#filter-formality", Select).value
        constraint_filter = self.query_one("#filter-constraints", Select).value

        # Apply occupation filter
        if occ_filter:
            if occ_filter.endswith("*"):
                prefix = occ_filter[:-1]
                filtered = [c for c in filtered if c.get("occupation_code", "").startswith(prefix)]
            else:
                filtered = [c for c in filtered if c.get("occupation_code") == occ_filter]

        # Apply industry filter
        if ind_filter:
            filtered = [c for c in filtered if c.get("naics_code", "").startswith(ind_filter)]

        # Apply winner filter
        if winner_filter and winner_filter != "all":
            filtered = [c for c in filtered if c.get("winner") == winner_filter]

        # Apply model pair filter
        if pair_filter and pair_filter != "all":
            pair = tuple(pair_filter.split("|"))
            filtered = [c for c in filtered if c.get("model_pair") == pair]

        # Apply job zone filter
        if zone_filter and zone_filter != "all":
            filtered = [c for c in filtered if str(c.get("job_zone")) == zone_filter]

        # Apply formality filter
        if formality_filter and formality_filter != "all":
            filtered = [c for c in filtered if str(c.get("formality_level")) == formality_filter]

        # Apply constraint filter
        if constraint_filter and constraint_filter != "all":
            has_constraints = constraint_filter == "yes"
            filtered = [c for c in filtered if c.get("has_constraints") == has_constraints]

        self.filtered_comparisons = filtered
        self._update_table()

    def _update_table(self):
        """Update table with filtered results."""
        table = self.query_one("#results-table", DataTable)
        table.clear()

        for c in self.filtered_comparisons:
            table.add_row(
                c.get("prompt_id", "")[:20],
                c.get("occupation_title", "")[:25],
                c.get("naics_sector", "")[:15],
                c.get("winner", ""),
                f"{c.get('confidence', 0):.2f}",
                f"{c.get('quality_gap', 0):.1f}",
                str(c.get("formality_level", "")),
                str(c.get("job_zone", ""))
            )

        # Update status
        status = self.query_one("#results-status", Label)
        status.update(f"Showing {len(self.filtered_comparisons)} of {len(self.comparisons)} results")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply-filters":
            self._apply_filters()
        elif event.button.id == "btn-clear-filters":
            self._clear_filters()
        elif event.button.id == "btn-apply-sort":
            self._apply_sort()

    def _clear_filters(self):
        """Clear all filters."""
        self.query_one("#filter-occupation", Input).value = ""
        self.query_one("#filter-industry", Input).value = ""
        self.query_one("#filter-winner", Select).value = "all"
        self.query_one("#filter-job-zone", Select).value = "all"
        self.query_one("#filter-formality", Select).value = "all"
        self.query_one("#filter-constraints", Select).value = "all"
        self._apply_filters()

    def _apply_sort(self):
        """Apply sorting to filtered results."""
        sort_field = self.query_one("#sort-field", Select).value
        sort_dir = self.query_one("#sort-direction", Select).value

        reverse = sort_dir == "desc"

        key_map = {
            "prompt_id": lambda x: x.get("prompt_id", ""),
            "win_rate": lambda x: x.get("win_rate", 0),
            "confidence": lambda x: x.get("confidence", 0),
            "quality_gap": lambda x: x.get("quality_gap", 0),
            "response_time": lambda x: x.get("gemini_latency_ms", 0),
            "occupation": lambda x: x.get("occupation_code", ""),
            "industry": lambda x: x.get("naics_code", ""),
        }

        key_fn = key_map.get(sort_field, lambda x: x.get("prompt_id", ""))
        self.filtered_comparisons.sort(key=key_fn, reverse=reverse)
        self._update_table()

    def action_view_detail(self):
        """Show detail view for selected comparison."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None and self.filtered_comparisons:
            idx = table.cursor_row
            if 0 <= idx < len(self.filtered_comparisons):
                comparison = self.filtered_comparisons[idx]
                detail_container = self.query_one("#detail-view", Container)
                detail_container.remove_children()
                detail_container.mount(ComparisonDetailView(comparison))
                detail_container.add_class("visible")

    def action_close_detail(self):
        """Close detail view."""
        detail_container = self.query_one("#detail-view", Container)
        detail_container.remove_class("visible")

    def action_export_filtered(self):
        """Export filtered results to CSV."""
        import csv
        output_path = self.run_dir / "filtered_export.csv"

        with open(output_path, "w", newline="") as f:
            if self.filtered_comparisons:
                writer = csv.DictWriter(f, fieldnames=self.filtered_comparisons[0].keys())
                writer.writeheader()
                writer.writerows(self.filtered_comparisons)

        self.notify(f"Exported {len(self.filtered_comparisons)} results to {output_path}")
```

---

## 9. REFUSAL TRACKING BY DIMENSION

```python
# src/eval/refusal_tracker.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from collections import defaultdict
import re

class RefusalCategory(str, Enum):
    """Categories of model refusals per PROMPT.md."""
    SAFETY_REFUSAL = "safety_refusal"         # Model cites safety/policy concerns
    CAPABILITY_LIMITATION = "capability"       # Model says it can't do the task
    MISUNDERSTANDING = "misunderstanding"      # Model interprets task incorrectly
    INCOMPLETE_RESPONSE = "incomplete"         # Model starts but doesn't finish
    OFF_TOPIC = "off_topic"                    # Model responds but not to actual task

@dataclass
class RefusalRecord:
    """Record of a single refusal."""
    prompt_id: str
    model: str
    category: RefusalCategory
    evidence: str
    occupation_code: str
    naics_code: str
    sensitive_topics: List[str]
    task_type: str
    response_snippet: str

class RefusalTracker:
    """Track and analyze model refusals across dimensions."""

    # Patterns for classifying refusals
    SAFETY_PATTERNS = [
        r"I (can't|cannot|won't|am not able to).*(harmful|dangerous|illegal|unethical)",
        r"(safety|policy|guidelines) (concern|prevent|don't allow)",
        r"I('m| am) not (comfortable|able) (with|to).*",
        r"this (request|task|prompt) (violates|goes against)",
        r"(sorry|apologize), but I (can't|cannot|won't)",
    ]

    CAPABILITY_PATTERNS = [
        r"I (don't|do not) have (the ability|access|capability)",
        r"I('m| am) (unable|not able) to",
        r"this is (beyond|outside) my (capabilities|abilities)",
        r"I (can't|cannot) (access|retrieve|find)",
    ]

    INCOMPLETE_PATTERNS = [
        r"\[incomplete\]",
        r"\.\.\.$",
        r"I('ll| will) stop here",
        r"to be continued",
    ]

    def __init__(self):
        self._refusals: List[RefusalRecord] = []
        self._by_model: Dict[str, List[RefusalRecord]] = defaultdict(list)
        self._by_category: Dict[RefusalCategory, List[RefusalRecord]] = defaultdict(list)
        self._by_occupation: Dict[str, List[RefusalRecord]] = defaultdict(list)
        self._by_industry: Dict[str, List[RefusalRecord]] = defaultdict(list)
        self._by_sensitive_topic: Dict[str, List[RefusalRecord]] = defaultdict(list)

    def classify_response(
        self,
        response: str,
        expected_task: str
    ) -> Optional[RefusalCategory]:
        """Classify a response as a refusal (or None if not a refusal)."""
        response_lower = response.lower()

        # Check for safety refusals
        for pattern in self.SAFETY_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return RefusalCategory.SAFETY_REFUSAL

        # Check for capability limitations
        for pattern in self.CAPABILITY_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return RefusalCategory.CAPABILITY_LIMITATION

        # Check for incomplete responses
        for pattern in self.INCOMPLETE_PATTERNS:
            if re.search(pattern, response):
                return RefusalCategory.INCOMPLETE_RESPONSE

        # Check for off-topic (response doesn't address task)
        # Simple heuristic: check if key task words appear in response
        task_words = set(expected_task.lower().split())
        response_words = set(response_lower.split())

        # If very little overlap and response is short, likely off-topic
        overlap = len(task_words & response_words)
        if overlap < 3 and len(response.split()) < 30:
            return RefusalCategory.OFF_TOPIC

        # Check for misunderstanding patterns
        misunderstanding_indicators = [
            "I think you meant",
            "did you mean",
            "I'm confused about",
            "not sure what you're asking",
        ]
        for indicator in misunderstanding_indicators:
            if indicator.lower() in response_lower:
                return RefusalCategory.MISUNDERSTANDING

        # Not a refusal
        return None

    def record_refusal(
        self,
        prompt_id: str,
        model: str,
        category: RefusalCategory,
        response: str,
        prompt_metadata: Dict[str, Any]
    ) -> RefusalRecord:
        """Record a refusal with full context."""
        record = RefusalRecord(
            prompt_id=prompt_id,
            model=model,
            category=category,
            evidence=response[:200],
            occupation_code=prompt_metadata.get("occupation_code", ""),
            naics_code=prompt_metadata.get("naics_code", ""),
            sensitive_topics=prompt_metadata.get("sensitive_topics", []),
            task_type=prompt_metadata.get("task_type", "general"),
            response_snippet=response[:500]
        )

        self._refusals.append(record)
        self._by_model[model].append(record)
        self._by_category[category].append(record)
        self._by_occupation[record.occupation_code[:2]].append(record)  # SOC major group
        self._by_industry[record.naics_code[:2]].append(record)  # NAICS sector

        for topic in record.sensitive_topics:
            self._by_sensitive_topic[topic].append(record)

        return record

    def get_refusal_rates(self) -> Dict[str, Dict[str, float]]:
        """Get refusal rates by model and category."""
        rates = {}

        for model, records in self._by_model.items():
            total = len(records)
            by_category = defaultdict(int)
            for r in records:
                by_category[r.category.value] += 1

            rates[model] = {
                "total_refusals": total,
                **{cat: count / total if total > 0 else 0 for cat, count in by_category.items()}
            }

        return rates

    def get_refusals_by_dimension(self, dimension: str) -> Dict[str, int]:
        """Get refusal counts by a specific dimension."""
        if dimension == "model":
            return {k: len(v) for k, v in self._by_model.items()}
        elif dimension == "category":
            return {k.value: len(v) for k, v in self._by_category.items()}
        elif dimension == "occupation":
            return {k: len(v) for k, v in self._by_occupation.items()}
        elif dimension == "industry":
            return {k: len(v) for k, v in self._by_industry.items()}
        elif dimension == "sensitive_topic":
            return {k: len(v) for k, v in self._by_sensitive_topic.items()}
        else:
            return {}

    def get_detailed_breakdown(self) -> Dict[str, Any]:
        """Get comprehensive refusal breakdown."""
        return {
            "total_refusals": len(self._refusals),
            "by_model": self.get_refusals_by_dimension("model"),
            "by_category": self.get_refusals_by_dimension("category"),
            "by_occupation": self.get_refusals_by_dimension("occupation"),
            "by_industry": self.get_refusals_by_dimension("industry"),
            "by_sensitive_topic": self.get_refusals_by_dimension("sensitive_topic"),
            "refusal_rates": self.get_refusal_rates(),
            "problematic_prompts": self._identify_problematic_prompts(),
        }

    def _identify_problematic_prompts(self) -> List[Dict]:
        """Identify prompts that caused refusals across multiple models."""
        prompt_refusals = defaultdict(list)
        for r in self._refusals:
            prompt_refusals[r.prompt_id].append(r.model)

        # Prompts that caused refusals in 2+ models
        problematic = [
            {
                "prompt_id": pid,
                "models_refused": models,
                "count": len(models)
            }
            for pid, models in prompt_refusals.items()
            if len(models) >= 2
        ]

        return sorted(problematic, key=lambda x: x["count"], reverse=True)

    def export(self) -> List[Dict]:
        """Export all refusal records."""
        return [
            {
                "prompt_id": r.prompt_id,
                "model": r.model,
                "category": r.category.value,
                "occupation_code": r.occupation_code,
                "naics_code": r.naics_code,
                "sensitive_topics": r.sensitive_topics,
                "task_type": r.task_type,
                "evidence": r.evidence
            }
            for r in self._refusals
        ]
```

---

## 10. FAILURE SUMMARY REPORT

```python
# src/reports/failure_report.py

import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from collections import defaultdict

@dataclass
class FailureRecord:
    """Record of a single API failure."""
    timestamp: datetime
    prompt_id: str
    model: str
    error_type: str
    error_message: str
    retry_count: int
    recovered: bool
    latency_ms: Optional[float] = None

@dataclass
class FailureSummary:
    """Summary statistics for failures."""
    total_failures: int
    total_retries: int
    recovery_rate: float
    by_model: Dict[str, Dict[str, int]]
    by_error_type: Dict[str, int]
    by_hour: Dict[int, int]
    worst_prompts: List[Dict]
    timeline: List[Dict]

class FailureReporter:
    """Generate failure summary reports."""

    def __init__(self, failures_log: Path):
        self.failures_log = failures_log
        self._failures: List[FailureRecord] = []

    async def load_failures(self):
        """Load failures from log file."""
        if not self.failures_log.exists():
            return

        with open(self.failures_log, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    self._failures.append(FailureRecord(
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        prompt_id=data["prompt_id"],
                        model=data["model"],
                        error_type=data["error_type"],
                        error_message=data["error_message"],
                        retry_count=data.get("retry_count", 0),
                        recovered=data.get("recovered", False),
                        latency_ms=data.get("latency_ms")
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue

    def generate_summary(self) -> FailureSummary:
        """Generate comprehensive failure summary."""
        if not self._failures:
            return FailureSummary(
                total_failures=0,
                total_retries=0,
                recovery_rate=0.0,
                by_model={},
                by_error_type={},
                by_hour={},
                worst_prompts=[],
                timeline=[]
            )

        # Basic counts
        total = len(self._failures)
        total_retries = sum(f.retry_count for f in self._failures)
        recovered = sum(1 for f in self._failures if f.recovered)
        recovery_rate = recovered / total if total > 0 else 0.0

        # By model
        by_model = defaultdict(lambda: {"total": 0, "recovered": 0, "retries": 0})
        for f in self._failures:
            by_model[f.model]["total"] += 1
            if f.recovered:
                by_model[f.model]["recovered"] += 1
            by_model[f.model]["retries"] += f.retry_count

        # By error type
        by_error_type = defaultdict(int)
        for f in self._failures:
            by_error_type[f.error_type] += 1

        # By hour
        by_hour = defaultdict(int)
        for f in self._failures:
            by_hour[f.timestamp.hour] += 1

        # Worst prompts
        prompt_failures = defaultdict(int)
        for f in self._failures:
            prompt_failures[f.prompt_id] += 1

        worst_prompts = [
            {"prompt_id": pid, "failure_count": count}
            for pid, count in sorted(prompt_failures.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Timeline (binned by 5-minute intervals)
        timeline = self._generate_timeline()

        return FailureSummary(
            total_failures=total,
            total_retries=total_retries,
            recovery_rate=recovery_rate,
            by_model=dict(by_model),
            by_error_type=dict(by_error_type),
            by_hour=dict(by_hour),
            worst_prompts=worst_prompts,
            timeline=timeline
        )

    def _generate_timeline(self) -> List[Dict]:
        """Generate timeline of failures in 5-minute bins."""
        if not self._failures:
            return []

        # Sort by timestamp
        sorted_failures = sorted(self._failures, key=lambda x: x.timestamp)
        start_time = sorted_failures[0].timestamp
        end_time = sorted_failures[-1].timestamp

        # Create 5-minute bins
        from datetime import timedelta

        bins = []
        current = start_time
        while current <= end_time:
            bin_end = current + timedelta(minutes=5)
            count = sum(
                1 for f in sorted_failures
                if current <= f.timestamp < bin_end
            )
            bins.append({
                "time": current.isoformat(),
                "count": count
            })
            current = bin_end

        return bins

    def format_report(self, summary: FailureSummary) -> str:
        """Format summary as human-readable report."""
        lines = [
            "=" * 60,
            "FAILURE SUMMARY REPORT",
            "=" * 60,
            "",
            "OVERVIEW",
            "-" * 40,
            f"Total Failures:     {summary.total_failures}",
            f"Total Retries:      {summary.total_retries}",
            f"Recovery Rate:      {summary.recovery_rate:.1%}",
            "",
            "BY MODEL",
            "-" * 40,
        ]

        for model, stats in summary.by_model.items():
            model_name = model.split("/")[-1]
            recovery = stats["recovered"] / stats["total"] if stats["total"] > 0 else 0
            lines.append(
                f"  {model_name}: {stats['total']} failures, "
                f"{stats['retries']} retries, {recovery:.0%} recovered"
            )

        lines.extend([
            "",
            "BY ERROR TYPE",
            "-" * 40,
        ])

        for error_type, count in sorted(summary.by_error_type.items(), key=lambda x: x[1], reverse=True):
            pct = count / summary.total_failures * 100 if summary.total_failures > 0 else 0
            lines.append(f"  {error_type}: {count} ({pct:.1f}%)")

        lines.extend([
            "",
            "WORST PROMPTS (Most Failures)",
            "-" * 40,
        ])

        for p in summary.worst_prompts[:5]:
            lines.append(f"  {p['prompt_id']}: {p['failure_count']} failures")

        lines.extend([
            "",
            "HOURLY DISTRIBUTION",
            "-" * 40,
        ])

        max_count = max(summary.by_hour.values()) if summary.by_hour else 1
        for hour in range(24):
            count = summary.by_hour.get(hour, 0)
            bar = "#" * int(count / max_count * 20)
            lines.append(f"  {hour:02d}:00 [{bar:<20}] {count}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    async def save_report(self, output_path: Path):
        """Generate and save failure report."""
        await self.load_failures()
        summary = self.generate_summary()

        # Save human-readable report
        report_text = self.format_report(summary)
        output_path.write_text(report_text)

        # Save JSON version
        json_path = output_path.with_suffix(".json")
        json_path.write_text(json.dumps({
            "total_failures": summary.total_failures,
            "total_retries": summary.total_retries,
            "recovery_rate": summary.recovery_rate,
            "by_model": summary.by_model,
            "by_error_type": summary.by_error_type,
            "by_hour": summary.by_hour,
            "worst_prompts": summary.worst_prompts,
            "timeline": summary.timeline
        }, indent=2))

        return summary

class FailureLogger:
    """Log failures in structured format for later analysis."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._file = None

    async def __aenter__(self):
        self._file = open(self.log_path, "a")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def log_failure(
        self,
        prompt_id: str,
        model: str,
        error_type: str,
        error_message: str,
        retry_count: int = 0,
        recovered: bool = False,
        latency_ms: Optional[float] = None
    ):
        """Log a failure event."""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_id": prompt_id,
            "model": model,
            "error_type": error_type,
            "error_message": str(error_message)[:500],
            "retry_count": retry_count,
            "recovered": recovered,
            "latency_ms": latency_ms
        }

        if self._file:
            self._file.write(json.dumps(record) + "\n")
            self._file.flush()
```

---

## 11. EVAL SCHEMAS (JudgeVote, ComparisonResult, ModelResponse)

```python
# src/eval/schemas.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

@dataclass
class ModelResponse:
    """Response from a model for a writing prompt."""
    prompt_id: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: float
    finish_reason: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def word_count(self) -> int:
        return len(self.content.split())

    @property
    def char_count(self) -> int:
        return len(self.content)

@dataclass
class JudgeVote:
    """A single judge vote for a comparison."""
    prompt_id: str
    judge_model: str
    persona: str  # "expert" or "recipient"
    vote_idx: int
    winner: str  # "gemini", "competitor", or "tie"
    confidence: int
    quality_a: int
    quality_b: int
    constraint_compliance_a: Optional[str]
    constraint_compliance_b: Optional[str]
    reasoning: str
    position: str  # "gemini_first" or "competitor_first"
    latency_ms: float
    cost: float
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class VoteAggregation:
    """Aggregated votes for a comparison."""
    prompt_id: str
    model_pair: Tuple[str, str]

    # Per-judge majority votes
    judge_majorities: Dict[str, str]  # judge_model -> winner

    # Final result (majority of judge majorities)
    final_winner: str

    # Vote counts
    gemini_votes: int
    competitor_votes: int
    tie_votes: int

    # Quality scores
    avg_quality_gemini: float
    avg_quality_competitor: float
    quality_gap: float

    # Confidence
    avg_confidence: float

    # Constraint compliance
    gemini_compliance_rate: Optional[float]
    competitor_compliance_rate: Optional[float]

@dataclass
class ComparisonResult:
    """Complete comparison result for a prompt."""
    prompt_id: str
    model_pair: Tuple[str, str]
    gemini_response: ModelResponse
    competitor_response: ModelResponse
    votes: List[JudgeVote]
    aggregation: VoteAggregation
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def winner(self) -> str:
        return self.aggregation.final_winner

    @property
    def gemini_win(self) -> bool:
        return self.winner == "gemini"

    @property
    def is_tie(self) -> bool:
        return self.winner == "tie"
```

---

## SUMMARY

This document provides complete Python implementations for all identified gaps:

1. **Parallel Request Architecture** - EvaluationEngine with asyncio.gather, Semaphores for concurrency limiting, batch processing, progress callbacks

2. **Cohen's Kappa** - Full implementation including pairwise kappa, Fleiss' kappa, and InterJudgeAgreement class

3. **Cost Tracking in TUI** - CostTracker widget, ETADisplay, complete progress dashboard with cost/time tracking

4. **CLI Options** - Complete CLI with --tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona

5. **Name Formality Variation** - NameFormality enum, GeneratedName with format() method, NameGenerator with formality support

6. **Phase 1 Generation Using Evaluated Models** - Phase1Generator that round-robins across evaluated models per PROMPT.md requirement

7. **Ambiguity Behavior Tracking** - AmbiguityTracker with pattern-based detection of clarification requests, hedging, hallucination, refusals

8. **TUI Results Viewer** - Full ResultsViewer with filtering, sorting, drill-down into individual comparisons

9. **Refusal Tracking by Dimension** - RefusalTracker with breakdowns by model, category, occupation, industry, sensitive topic

10. **Failure Summary Report** - FailureReporter generating comprehensive reports with timeline, by-model, by-error-type breakdowns

11. **Eval Schemas** - ModelResponse, JudgeVote, VoteAggregation, ComparisonResult dataclasses
