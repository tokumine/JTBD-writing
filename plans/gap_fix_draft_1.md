# Gap Fix Implementation: Complete Python Code

This document provides complete Python implementations for ALL gaps identified in gap_analysis.md.

---

## 1. PARALLEL REQUEST ARCHITECTURE - EvaluationEngine

```python
# src/eval/engine.py

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from datetime import datetime
import time
import random

from ..api.openrouter_client import OpenRouterClient, CompletionResponse
from ..config.settings import EvalConfig
from ..storage.checkpoint import CheckpointManager
from ..storage.database import EvalDatabase
from ..prompts.schemas import WritingPrompt
from .schemas import Comparison, JudgeVote, ModelResponse
from .vote_aggregator import VoteAggregator
from .judge_prompt_builder import build_judge_prompt
from .judge_parser import parse_judge_response
from .refusal_classifier import classify_refusal
from .response_analyzer import analyze_response

@dataclass
class ProgressUpdate:
    """Progress update for TUI callbacks."""
    phase: str  # "generation" | "judging" | "analysis"
    total_prompts: int
    completed_prompts: int
    current_prompt_id: Optional[str]
    current_occupation: Optional[str]
    current_industry: Optional[str]
    model_pair_progress: Dict[str, Tuple[int, int, float]]  # model_pair -> (completed, total, win_rate)
    per_judge_votes: Dict[str, Dict[str, int]]  # judge_model -> {model_a: votes, model_b: votes, tie: votes}
    elapsed_seconds: float
    eta_seconds: Optional[float]
    cost_spent: float
    cost_projected: float
    response_times: List[float]  # Recent response latencies
    api_throughput: float  # Calls per minute
    errors: int
    retries: int
    rate_limit_pauses: int

@dataclass
class BatchResult:
    """Result from processing a batch of prompts."""
    prompt_id: str
    model_a_response: Optional[ModelResponse]
    model_b_response: Optional[ModelResponse]
    judgments: List[JudgeVote]
    winner: Optional[str]
    cost: float
    errors: List[str]

class EvaluationEngine:
    """Main evaluation orchestrator with parallel request handling."""

    def __init__(
        self,
        config: EvalConfig,
        client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        database: EvalDatabase,
        progress_callback: Optional[Callable[[ProgressUpdate], None]] = None,
        max_concurrent: int = 20
    ):
        self.config = config
        self.client = client
        self.checkpoint_manager = checkpoint_manager
        self.database = database
        self.progress_callback = progress_callback
        self.max_concurrent = max_concurrent

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Per-model semaphores for respecting individual rate limits
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}

        # Statistics tracking
        self._start_time: Optional[float] = None
        self._completed_prompts = 0
        self._total_cost = 0.0
        self._response_times: List[float] = []
        self._api_call_times: List[float] = []
        self._errors = 0
        self._retries = 0
        self._rate_limit_pauses = 0

        # Per-model pair tracking
        self._pair_results: Dict[str, Dict[str, int]] = {}  # pair_key -> {gemini: wins, opponent: wins, tie: count}

        # Per-judge vote tracking
        self._judge_votes: Dict[str, Dict[str, int]] = {}  # judge_model -> {model_a: votes, model_b: votes, tie: votes}

        # Vote aggregator
        self.vote_aggregator = VoteAggregator(
            judge_models=config.judge_config.models,
            votes_per_judge=config.judge_config.votes_per_judge
        )

    def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
        """Get or create per-model semaphore based on rate limits."""
        if model not in self._model_semaphores:
            # Get model-specific concurrency from rate limits
            limits = self.client.MODEL_RATE_LIMITS.get(
                model,
                self.client.DEFAULT_RATE_LIMIT
            )
            # Allow concurrent requests up to 80% of RPM
            max_concurrent = max(1, int(limits["rpm"] * 0.8 / 60 * 10))  # ~10 second window
            self._model_semaphores[model] = asyncio.Semaphore(max_concurrent)
        return self._model_semaphores[model]

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
        batch_size: int = 10
    ) -> List[BatchResult]:
        """Run full evaluation with parallel processing."""
        self._start_time = time.time()
        results: List[BatchResult] = []

        # Resume from checkpoint if available
        completed_ids = await self.checkpoint_manager.get_completed_prompt_ids()
        remaining_prompts = [p for p in prompts if p.prompt_id not in completed_ids]

        self._completed_prompts = len(completed_ids)
        total_prompts = len(prompts)

        # Process in batches
        for batch_start in range(0, len(remaining_prompts), batch_size):
            batch = remaining_prompts[batch_start:batch_start + batch_size]

            # Process batch with parallel execution
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)

            # Save checkpoint after each batch
            await self.checkpoint_manager.save_batch_results(batch_results)

            # Update progress
            self._completed_prompts += len(batch)
            await self._emit_progress("generation", total_prompts, batch[-1] if batch else None)

        return results

    async def _process_batch(
        self,
        prompts: List[WritingPrompt]
    ) -> List[BatchResult]:
        """Process a batch of prompts with parallel execution."""

        # Create tasks for all model pairs and prompts
        tasks = []
        for prompt in prompts:
            for gemini_model, competitor_model in self.config.model_pairs:
                tasks.append(
                    self._process_single_comparison(
                        prompt, gemini_model, competitor_model
                    )
                )

        # Execute all tasks concurrently with semaphore limiting
        if hasattr(asyncio, 'TaskGroup'):
            # Python 3.11+ TaskGroup for better error handling
            async with asyncio.TaskGroup() as tg:
                task_handles = [tg.create_task(t) for t in tasks]
            results = [t.result() for t in task_handles]
        else:
            # Fallback to gather for older Python
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log errors
        batch_results = []
        for r in results:
            if isinstance(r, Exception):
                self._errors += 1
            elif r is not None:
                batch_results.append(r)

        return batch_results

    async def _process_single_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str
    ) -> Optional[BatchResult]:
        """Process a single prompt comparison with both models."""

        async with self._semaphore:  # Global concurrency limit
            errors = []
            total_cost = 0.0

            # Generate responses from both models in parallel
            async with self._get_model_semaphore(gemini_model):
                gemini_task = self._generate_response(prompt, gemini_model)

            async with self._get_model_semaphore(competitor_model):
                competitor_task = self._generate_response(prompt, competitor_model)

            gemini_response, competitor_response = await asyncio.gather(
                gemini_task, competitor_task, return_exceptions=True
            )

            # Handle generation errors
            if isinstance(gemini_response, Exception):
                errors.append(f"Gemini generation failed: {gemini_response}")
                gemini_response = None
            else:
                total_cost += gemini_response.cost if gemini_response else 0

            if isinstance(competitor_response, Exception):
                errors.append(f"Competitor generation failed: {competitor_response}")
                competitor_response = None
            else:
                total_cost += competitor_response.cost if competitor_response else 0

            # Run judging if we have both responses
            judgments = []
            winner = None

            if gemini_response and competitor_response:
                judgments, judge_cost = await self._run_judging(
                    prompt, gemini_response, competitor_response,
                    gemini_model, competitor_model
                )
                total_cost += judge_cost

                # Aggregate votes to determine winner
                winner = self.vote_aggregator.aggregate(judgments)

                # Update pair tracking
                pair_key = f"{gemini_model}_vs_{competitor_model}"
                if pair_key not in self._pair_results:
                    self._pair_results[pair_key] = {"gemini": 0, "opponent": 0, "tie": 0}

                if winner == gemini_model:
                    self._pair_results[pair_key]["gemini"] += 1
                elif winner == competitor_model:
                    self._pair_results[pair_key]["opponent"] += 1
                else:
                    self._pair_results[pair_key]["tie"] += 1

            elif gemini_response and not competitor_response:
                # Auto-win for Gemini
                winner = gemini_model
            elif competitor_response and not gemini_response:
                # Auto-loss for Gemini
                winner = competitor_model

            self._total_cost += total_cost

            return BatchResult(
                prompt_id=prompt.prompt_id,
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
        """Generate a response from a model."""
        start_time = time.time()

        try:
            messages = [
                {"role": "system", "content": self._build_system_prompt(prompt)},
                {"role": "user", "content": prompt.full_prompt_text}
            ]

            response = await self.client.complete(
                model=model,
                messages=messages,
                temperature=0.7
            )

            latency = (time.time() - start_time) * 1000
            self._response_times.append(latency)
            self._api_call_times.append(time.time())

            # Analyze response
            metrics = analyze_response(response.content)
            refusal = classify_refusal(response.content, prompt)

            return ModelResponse(
                model=model,
                content=response.content,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=latency,
                cost=response.cost,
                metrics=metrics,
                refusal_type=refusal
            )

        except Exception as e:
            self._errors += 1
            raise

    async def _run_judging(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        model_a: str,
        model_b: str
    ) -> Tuple[List[JudgeVote], float]:
        """Run all judges on a comparison with parallel execution."""

        judgments = []
        total_cost = 0.0

        # Determine position shuffling for each vote (deterministic)
        seed = hash(f"{prompt.prompt_id}_{model_a}_{model_b}")

        # Create all judging tasks
        judge_tasks = []
        for judge_model in self.config.judge_config.models:
            for vote_idx in range(self.config.judge_config.votes_per_judge):
                # Deterministic position assignment
                position_seed = seed + vote_idx + hash(judge_model)
                a_is_first = (position_seed % 2) == 0

                # Both personas if configured
                personas = ["writing_expert", "recipient"] if self.config.judge_config.use_both_personas else ["writing_expert"]

                for persona in personas:
                    judge_tasks.append(
                        self._single_judge_call(
                            prompt, response_a, response_b,
                            model_a, model_b,
                            judge_model, persona,
                            a_is_first, vote_idx
                        )
                    )

        # Execute all judge calls in parallel
        results = await asyncio.gather(*judge_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self._errors += 1
            elif result:
                vote, cost = result
                judgments.append(vote)
                total_cost += cost

                # Track per-judge votes
                if vote.judge_model not in self._judge_votes:
                    self._judge_votes[vote.judge_model] = {"model_a": 0, "model_b": 0, "tie": 0}

                if vote.winner == model_a:
                    self._judge_votes[vote.judge_model]["model_a"] += 1
                elif vote.winner == model_b:
                    self._judge_votes[vote.judge_model]["model_b"] += 1
                else:
                    self._judge_votes[vote.judge_model]["tie"] += 1

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

        async with self._get_model_semaphore(judge_model):
            try:
                # Build judge prompt with position shuffling
                if a_is_first:
                    first_response, second_response = response_a.content, response_b.content
                    first_model, second_model = model_a, model_b
                else:
                    first_response, second_response = response_b.content, response_a.content
                    first_model, second_model = model_b, model_a

                judge_prompt = build_judge_prompt(
                    prompt=prompt,
                    response_a=first_response,
                    response_b=second_response,
                    persona=persona
                )

                messages = [
                    {"role": "system", "content": judge_prompt["system"]},
                    {"role": "user", "content": judge_prompt["user"]}
                ]

                response = await self.client.complete(
                    model=judge_model,
                    messages=messages,
                    temperature=0.3  # Lower temperature for more consistent judging
                )

                self._api_call_times.append(time.time())

                # Parse judgment
                parsed = parse_judge_response(response.content)

                # Map back to actual models
                if parsed.winner == "A":
                    actual_winner = first_model
                elif parsed.winner == "B":
                    actual_winner = second_model
                else:
                    actual_winner = None  # Tie

                vote = JudgeVote(
                    judge_model=judge_model,
                    persona=persona,
                    vote_index=vote_idx,
                    winner=actual_winner,
                    reasoning=parsed.reasoning,
                    confidence=parsed.confidence,
                    criteria_scores=parsed.criteria_scores,
                    position_a_was=first_model
                )

                return vote, response.cost

            except Exception as e:
                self._errors += 1
                return None

    def _build_system_prompt(self, prompt: WritingPrompt) -> str:
        """Build system prompt for response generation."""
        parts = [
            f"You are {prompt.writer.name}, {prompt.writer.job_title}.",
            f"Age: {prompt.writer.age}, Generation: {prompt.writer.generation}.",
        ]

        if prompt.writer.company:
            parts.append(f"Company: {prompt.writer.company.name} ({prompt.writer.company.size}).")

        parts.append(f"Writing skill level: {prompt.writer.skill_level}/5.")
        parts.append(f"Formality level for this communication: {prompt.formality_level}/5.")

        return " ".join(parts)

    async def _emit_progress(
        self,
        phase: str,
        total_prompts: int,
        current_prompt: Optional[WritingPrompt]
    ):
        """Emit progress update to callback."""
        if not self.progress_callback:
            return

        elapsed = time.time() - self._start_time if self._start_time else 0

        # Calculate ETA
        if self._completed_prompts > 0:
            rate = self._completed_prompts / elapsed
            remaining = total_prompts - self._completed_prompts
            eta = remaining / rate if rate > 0 else None
        else:
            eta = None

        # Calculate throughput (calls per minute in last 60 seconds)
        recent_calls = [t for t in self._api_call_times if t > time.time() - 60]
        throughput = len(recent_calls)

        # Calculate cost projection
        if self._completed_prompts > 0:
            cost_per_prompt = self._total_cost / self._completed_prompts
            projected_cost = cost_per_prompt * total_prompts
        else:
            projected_cost = 0.0

        # Build model pair progress
        pair_progress = {}
        for pair_key, results in self._pair_results.items():
            total = results["gemini"] + results["opponent"] + results["tie"]
            if total > 0:
                win_rate = results["gemini"] / (results["gemini"] + results["opponent"]) if (results["gemini"] + results["opponent"]) > 0 else 0.5
            else:
                win_rate = 0.0
            pair_progress[pair_key] = (total, total_prompts, win_rate)

        update = ProgressUpdate(
            phase=phase,
            total_prompts=total_prompts,
            completed_prompts=self._completed_prompts,
            current_prompt_id=current_prompt.prompt_id if current_prompt else None,
            current_occupation=current_prompt.onet_task.occupation_title if current_prompt else None,
            current_industry=current_prompt.company.industry if current_prompt and current_prompt.company else None,
            model_pair_progress=pair_progress,
            per_judge_votes=self._judge_votes.copy(),
            elapsed_seconds=elapsed,
            eta_seconds=eta,
            cost_spent=self._total_cost,
            cost_projected=projected_cost,
            response_times=self._response_times[-100:],  # Last 100
            api_throughput=throughput,
            errors=self._errors,
            retries=self._retries,
            rate_limit_pauses=self._rate_limit_pauses
        )

        self.progress_callback(update)
```

---

## 2. COHEN'S KAPPA INTER-JUDGE AGREEMENT

```python
# src/analysis/statistics.py (additions)

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from scipy import stats
from collections import Counter

@dataclass
class KappaResult:
    """Result of Cohen's Kappa calculation."""
    kappa: float
    interpretation: str
    observed_agreement: float
    expected_agreement: float
    judges_compared: Tuple[str, str]
    n_samples: int

    @staticmethod
    def interpret(kappa: float) -> str:
        """Interpret kappa value using Landis & Koch scale."""
        if kappa < 0:
            return "Poor (less than chance)"
        elif kappa < 0.20:
            return "Slight"
        elif kappa < 0.40:
            return "Fair"
        elif kappa < 0.60:
            return "Moderate"
        elif kappa < 0.80:
            return "Substantial"
        else:
            return "Almost Perfect"


def calculate_cohens_kappa(
    votes_judge_1: List[str],
    votes_judge_2: List[str],
    judge_1_name: str = "Judge 1",
    judge_2_name: str = "Judge 2"
) -> KappaResult:
    """
    Calculate Cohen's Kappa for inter-judge agreement.

    Args:
        votes_judge_1: List of winner labels from judge 1 (e.g., ["A", "B", "A", "tie", ...])
        votes_judge_2: List of winner labels from judge 2
        judge_1_name: Name of first judge
        judge_2_name: Name of second judge

    Returns:
        KappaResult with kappa value and interpretation
    """
    if len(votes_judge_1) != len(votes_judge_2):
        raise ValueError("Vote lists must have same length")

    n = len(votes_judge_1)
    if n == 0:
        return KappaResult(
            kappa=0.0,
            interpretation="No data",
            observed_agreement=0.0,
            expected_agreement=0.0,
            judges_compared=(judge_1_name, judge_2_name),
            n_samples=0
        )

    # Get all unique categories
    all_categories = set(votes_judge_1) | set(votes_judge_2)
    categories = sorted(list(all_categories))
    n_categories = len(categories)

    # Build confusion matrix
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    confusion = np.zeros((n_categories, n_categories), dtype=int)

    for v1, v2 in zip(votes_judge_1, votes_judge_2):
        confusion[cat_to_idx[v1], cat_to_idx[v2]] += 1

    # Calculate observed agreement (proportion on diagonal)
    observed_agreement = np.trace(confusion) / n

    # Calculate expected agreement by chance
    row_totals = confusion.sum(axis=1)
    col_totals = confusion.sum(axis=0)
    expected_agreement = np.sum(row_totals * col_totals) / (n * n)

    # Calculate kappa
    if expected_agreement == 1.0:
        kappa = 1.0  # Perfect agreement by chance
    else:
        kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)

    return KappaResult(
        kappa=kappa,
        interpretation=KappaResult.interpret(kappa),
        observed_agreement=observed_agreement,
        expected_agreement=expected_agreement,
        judges_compared=(judge_1_name, judge_2_name),
        n_samples=n
    )


def calculate_fleiss_kappa(
    all_judge_votes: Dict[str, List[str]]
) -> float:
    """
    Calculate Fleiss' Kappa for agreement among multiple judges.

    Args:
        all_judge_votes: Dict mapping judge name to list of votes
                        All lists must have same length

    Returns:
        Fleiss' kappa value
    """
    judges = list(all_judge_votes.keys())
    if len(judges) < 2:
        return 1.0  # Single judge always agrees with self

    n_judges = len(judges)
    n_samples = len(all_judge_votes[judges[0]])

    # Get all categories
    all_categories = set()
    for votes in all_judge_votes.values():
        all_categories.update(votes)
    categories = sorted(list(all_categories))
    n_categories = len(categories)

    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    # Build matrix: n_samples x n_categories
    # Each cell (i, j) = number of judges who assigned category j to sample i
    matrix = np.zeros((n_samples, n_categories), dtype=int)

    for judge_votes in all_judge_votes.values():
        for i, vote in enumerate(judge_votes):
            matrix[i, cat_to_idx[vote]] += 1

    # Calculate P_i for each sample (agreement within sample)
    P_i = np.zeros(n_samples)
    for i in range(n_samples):
        row = matrix[i]
        P_i[i] = (np.sum(row ** 2) - n_judges) / (n_judges * (n_judges - 1))

    # Calculate P_bar (mean agreement)
    P_bar = np.mean(P_i)

    # Calculate P_e (expected agreement by chance)
    p_j = matrix.sum(axis=0) / (n_samples * n_judges)  # Proportion for each category
    P_e = np.sum(p_j ** 2)

    # Calculate Fleiss' kappa
    if P_e == 1.0:
        return 1.0

    kappa = (P_bar - P_e) / (1 - P_e)
    return kappa


def calculate_all_pairwise_kappas(
    all_judge_votes: Dict[str, List[str]]
) -> List[KappaResult]:
    """
    Calculate Cohen's Kappa for all pairs of judges.

    Args:
        all_judge_votes: Dict mapping judge name to list of votes

    Returns:
        List of KappaResult for each pair
    """
    judges = list(all_judge_votes.keys())
    results = []

    for i in range(len(judges)):
        for j in range(i + 1, len(judges)):
            judge_1, judge_2 = judges[i], judges[j]
            result = calculate_cohens_kappa(
                all_judge_votes[judge_1],
                all_judge_votes[judge_2],
                judge_1,
                judge_2
            )
            results.append(result)

    return results


@dataclass
class InterJudgeAgreement:
    """Complete inter-judge agreement analysis."""
    fleiss_kappa: float
    fleiss_interpretation: str
    pairwise_kappas: List[KappaResult]
    average_pairwise_kappa: float
    min_pairwise_kappa: float
    max_pairwise_kappa: float

    @classmethod
    def from_judge_votes(cls, all_judge_votes: Dict[str, List[str]]) -> "InterJudgeAgreement":
        """Calculate all agreement metrics from judge votes."""
        fleiss = calculate_fleiss_kappa(all_judge_votes)
        pairwise = calculate_all_pairwise_kappas(all_judge_votes)

        if pairwise:
            avg = sum(k.kappa for k in pairwise) / len(pairwise)
            min_k = min(k.kappa for k in pairwise)
            max_k = max(k.kappa for k in pairwise)
        else:
            avg = min_k = max_k = 0.0

        return cls(
            fleiss_kappa=fleiss,
            fleiss_interpretation=KappaResult.interpret(fleiss),
            pairwise_kappas=pairwise,
            average_pairwise_kappa=avg,
            min_pairwise_kappa=min_k,
            max_pairwise_kappa=max_k
        )
```

---

## 3. COST TRACKING IN TUI

```python
# src/tui/components.py (additions)

from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from rich.table import Table
from rich.panel import Panel

class CostTracker(Static):
    """Widget displaying cost tracking information."""

    cost_spent = reactive(0.0)
    cost_projected = reactive(0.0)
    budget_limit = reactive(None)  # Optional budget limit

    def __init__(self, budget_limit: float = None, **kwargs):
        super().__init__(**kwargs)
        self.budget_limit = budget_limit

    def render(self) -> Panel:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")

        # Current spend
        spent_style = "green" if self.cost_spent < (self.budget_limit or float('inf')) * 0.8 else "yellow"
        if self.budget_limit and self.cost_spent >= self.budget_limit:
            spent_style = "red bold"

        table.add_row("Spent so far:", f"[{spent_style}]${self.cost_spent:,.2f}[/]")

        # Projected total
        projected_style = "cyan"
        if self.budget_limit and self.cost_projected > self.budget_limit:
            projected_style = "red"

        table.add_row("Projected total:", f"[{projected_style}]${self.cost_projected:,.2f}[/]")

        # Budget remaining (if set)
        if self.budget_limit:
            remaining = self.budget_limit - self.cost_spent
            remaining_style = "green" if remaining > 0 else "red"
            table.add_row("Budget remaining:", f"[{remaining_style}]${remaining:,.2f}[/]")

            # Percentage used
            pct = (self.cost_spent / self.budget_limit) * 100
            bar_width = 20
            filled = int(bar_width * min(pct, 100) / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            table.add_row("Budget used:", f"[{spent_style}]{bar}[/] {pct:.1f}%")

        return Panel(table, title="Cost Tracking", border_style="blue")

    def update_costs(self, spent: float, projected: float):
        """Update cost values."""
        self.cost_spent = spent
        self.cost_projected = projected


class PerformanceMetrics(Static):
    """Widget displaying performance metrics."""

    response_times: List[float] = []
    api_throughput = reactive(0.0)

    def render(self) -> Panel:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        if self.response_times:
            avg_time = sum(self.response_times) / len(self.response_times)
            min_time = min(self.response_times)
            max_time = max(self.response_times)
            p95_time = sorted(self.response_times)[int(len(self.response_times) * 0.95)] if len(self.response_times) >= 20 else max_time

            table.add_row("Avg response:", f"{avg_time:.0f}ms")
            table.add_row("Min/Max:", f"{min_time:.0f}ms / {max_time:.0f}ms")
            table.add_row("P95:", f"{p95_time:.0f}ms")
        else:
            table.add_row("Avg response:", "--")

        table.add_row("Throughput:", f"{self.api_throughput:.1f} calls/min")

        return Panel(table, title="Performance", border_style="green")

    def update_metrics(self, response_times: List[float], throughput: float):
        """Update performance metrics."""
        self.response_times = response_times
        self.api_throughput = throughput
        self.refresh()


class JudgeVotesDisplay(Static):
    """Widget displaying per-judge vote breakdown."""

    judge_votes: Dict[str, Dict[str, int]] = {}

    def render(self) -> Panel:
        if not self.judge_votes:
            return Panel("No votes yet", title="Judge Votes")

        table = Table(show_header=True, box=None)
        table.add_column("Judge", style="cyan")
        table.add_column("Model A", justify="center")
        table.add_column("Model B", justify="center")
        table.add_column("Tie", justify="center")
        table.add_column("Total", justify="center")

        for judge, votes in self.judge_votes.items():
            # Shorten judge name for display
            short_name = judge.split("/")[-1][:15]
            total = votes["model_a"] + votes["model_b"] + votes["tie"]

            table.add_row(
                short_name,
                str(votes["model_a"]),
                str(votes["model_b"]),
                str(votes["tie"]),
                str(total)
            )

        return Panel(table, title="Per-Judge Votes", border_style="magenta")

    def update_votes(self, judge_votes: Dict[str, Dict[str, int]]):
        """Update vote counts."""
        self.judge_votes = judge_votes
        self.refresh()
```

---

## 4. HELP OVERLAY (h key) IN TUI

```python
# src/tui/progress_dashboard.py (additions to existing class)

from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Container
from textual.binding import Binding
from rich.panel import Panel
from rich.table import Table

class HelpOverlay(ModalScreen):
    """Help overlay showing keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close help"),
        Binding("h", "dismiss", "Close help"),
        Binding("?", "dismiss", "Close help"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self.build_help_content()),
            id="help-container"
        )

    def build_help_content(self) -> Panel:
        """Build the help content panel."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Key", style="yellow", width=12)
        table.add_column("Action", style="white")

        shortcuts = [
            ("q", "Graceful quit - saves checkpoint and exits safely"),
            ("p", "Pause/Resume - toggle evaluation pause"),
            ("d", "Detailed view - toggle full prompt/response display"),
            ("s", "Statistics - show expanded statistics panel"),
            ("h / ?", "Help - show this help overlay"),
            ("↑ / ↓", "Scroll - navigate activity log"),
            ("Page Up", "Scroll up one page in log"),
            ("Page Down", "Scroll down one page in log"),
            ("Home", "Jump to top of log"),
            ("End", "Jump to bottom of log"),
            ("Escape", "Close any overlay or modal"),
        ]

        for key, action in shortcuts:
            table.add_row(key, action)

        # Add section for status indicators
        status_table = Table(show_header=True, header_style="bold green", box=None)
        status_table.add_column("Symbol", style="yellow", width=12)
        status_table.add_column("Meaning", style="white")

        statuses = [
            ("✓", "Task completed successfully"),
            ("○", "Task pending/not started"),
            ("◐", "Task in progress"),
            ("⚠", "Warning - retry occurred but recovered"),
            ("✗", "Error - task failed"),
            ("⏱", "Rate limit pause in effect"),
        ]

        for symbol, meaning in statuses:
            status_table.add_row(symbol, meaning)

        content = Table.grid(padding=1)
        content.add_row(Panel(table, title="Keyboard Shortcuts", border_style="cyan"))
        content.add_row(Panel(status_table, title="Status Indicators", border_style="green"))

        return Panel(
            content,
            title="[bold]Gemini Writing Eval - Help[/bold]",
            subtitle="Press [yellow]Escape[/yellow] or [yellow]h[/yellow] to close",
            border_style="blue"
        )


class ProgressDashboard(App):
    """Main progress dashboard with help overlay support."""

    CSS = """
    #help-container {
        align: center middle;
        width: 70;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit_graceful", "Quit"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("d", "toggle_detailed", "Details"),
        Binding("s", "show_statistics", "Stats"),
        Binding("h", "show_help", "Help"),
        Binding("?", "show_help", "Help"),
    ]

    def action_show_help(self) -> None:
        """Show the help overlay."""
        self.push_screen(HelpOverlay())

    def action_quit_graceful(self) -> None:
        """Gracefully quit with checkpoint save."""
        # Signal to save checkpoint
        if hasattr(self, 'on_graceful_quit'):
            self.on_graceful_quit()
        self.exit()

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        if hasattr(self, 'paused'):
            self.paused = not self.paused
            if hasattr(self, 'on_pause_toggle'):
                self.on_pause_toggle(self.paused)

    def action_toggle_detailed(self) -> None:
        """Toggle detailed view mode."""
        if hasattr(self, 'detailed_mode'):
            self.detailed_mode = not self.detailed_mode
            self.refresh()

    def action_show_statistics(self) -> None:
        """Show expanded statistics panel."""
        # This would push a statistics screen
        pass


---

## 5. CLI OPTIONS: --tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona

```python
# src/cli.py (complete implementation with all CLI options)

import typer
from pathlib import Path
from typing import Optional, List
import asyncio
from enum import Enum

from .config.presets import PRESETS, PRO_PAIRS, FLASH_PAIRS, ALL_JUDGES, EvalConfig, JudgeConfig
from .config.cost_estimator import estimate_cost, format_cost_estimate
from .api.openrouter_client import OpenRouterClient
from .storage.run_directory import RunDirectory
from .storage.checkpoint import CheckpointManager
from .storage.database import EvalDatabase
from .eval.engine import EvaluationEngine
from .tui.progress_dashboard import ProgressDashboard
from .prompts.generator import generate_prompts

app = typer.Typer(name="gemini-eval", help="Gemini Writing Evaluation Framework")

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
    # Preset and basic options
    preset: int = typer.Option(None, "--preset", "-p", help="Use preset configuration (1-10)"),
    prompts: int = typer.Option(None, "--prompts", "-n", help="Number of prompts to evaluate"),
    seed: int = typer.Option(None, "--seed", help="Random seed for reproducibility"),

    # Model configuration
    models: str = typer.Option(None, "--models", "-m", help="Comma-separated model IDs to evaluate"),
    tier: ModelTier = typer.Option(None, "--tier", "-t", help="Model tier: pro, flash, or both"),

    # Judge configuration
    judges: str = typer.Option(None, "--judges", "-j", help="Comma-separated judge model IDs"),
    votes: int = typer.Option(None, "--votes", "-v", help="Votes per judge (1, 3, or 5)"),
    persona: JudgePersona = typer.Option(None, "--persona", help="Judge persona: both, expert, or recipient"),

    # Prompt/Task filters
    occupations: str = typer.Option(None, "--occupations", "-o", help="O*NET occupation codes (comma-separated, wildcards OK)"),
    industries: str = typer.Option(None, "--industries", "-i", help="NAICS industry codes (comma-separated)"),
    job_zones: str = typer.Option(None, "--job-zones", "-z", help="O*NET job zones (1-5, comma-separated)"),
    formality_range: str = typer.Option(None, "--formality-range", "-f", help="Formality level range (e.g., '1-3' or '3,4,5')"),
    age_range: str = typer.Option(None, "--age-range", "-a", help="Writer age range (e.g., '25-45')"),

    # Sampling limits
    occupation_limit: int = typer.Option(None, "--occupation-limit", help="Maximum prompts per occupation"),
    industry_limit: int = typer.Option(None, "--industry-limit", help="Maximum prompts per industry"),

    # Execution options
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    resume: Path = typer.Option(None, "--resume", help="Resume from checkpoint directory"),
    max_concurrent: int = typer.Option(20, "--max-concurrent", help="Maximum concurrent API calls"),
    output_dir: Path = typer.Option(Path("results"), "--output", help="Output directory for results"),
):
    """Run a Gemini writing evaluation."""

    # Start with preset if specified, otherwise default
    if preset:
        if preset not in PRESETS:
            typer.echo(f"Invalid preset: {preset}. Must be 1-10.")
            raise typer.Exit(1)
        config = PRESETS[preset]
    else:
        config = PRESETS[6]  # Default to Standard Eval

    # Apply model tier filter
    if tier:
        if tier == ModelTier.PRO:
            config.model_pairs = PRO_PAIRS
        elif tier == ModelTier.FLASH:
            config.model_pairs = FLASH_PAIRS
        elif tier == ModelTier.BOTH:
            config.model_pairs = PRO_PAIRS + FLASH_PAIRS

    # Apply specific models if provided
    if models:
        model_list = [m.strip() for m in models.split(",")]
        # Filter pairs to only include specified models
        config.model_pairs = [
            (a, b) for (a, b) in config.model_pairs
            if a in model_list or b in model_list
        ]

    # Apply prompt count override
    if prompts:
        config.num_prompts = prompts

    # Apply seed
    if seed:
        config.random_seed = seed

    # Apply judge configuration
    if judges:
        judge_list = [j.strip() for j in judges.split(",")]
        config.judge_config.models = judge_list

    if votes:
        if votes not in [1, 3, 5]:
            typer.echo("Votes must be 1, 3, or 5")
            raise typer.Exit(1)
        config.judge_config.votes_per_judge = votes

    if persona:
        if persona == JudgePersona.BOTH:
            config.judge_config.use_both_personas = True
        elif persona == JudgePersona.EXPERT:
            config.judge_config.use_both_personas = False
            # Set flag for expert-only (would need to add to JudgeConfig)
        elif persona == JudgePersona.RECIPIENT:
            config.judge_config.use_both_personas = False
            # Set flag for recipient-only

    # Parse occupation filter
    occupation_codes = None
    if occupations:
        occupation_codes = [o.strip() for o in occupations.split(",")]

    # Parse industry filter
    industry_codes = None
    if industries:
        industry_codes = [i.strip() for i in industries.split(",")]

    # Parse job zones filter
    job_zone_list = None
    if job_zones:
        job_zone_list = [int(z.strip()) for z in job_zones.split(",")]

    # Parse formality range
    formality_levels = None
    if formality_range:
        if "-" in formality_range:
            start, end = formality_range.split("-")
            formality_levels = list(range(int(start), int(end) + 1))
        else:
            formality_levels = [int(f.strip()) for f in formality_range.split(",")]

    # Parse age range
    age_min, age_max = None, None
    if age_range:
        if "-" in age_range:
            age_min, age_max = [int(x.strip()) for x in age_range.split("-")]
        else:
            age_min = age_max = int(age_range)

    # Store sampling limits in config (would need to add to EvalConfig)
    if occupation_limit:
        config.occupation_limit = occupation_limit
    if industry_limit:
        config.industry_limit = industry_limit

    # Calculate estimate
    estimate = estimate_cost(config)
    typer.echo(format_cost_estimate(estimate, config))

    if dry_run:
        typer.echo("Dry run - not executing evaluation.")
        raise typer.Exit(0)

    # Confirm before proceeding
    if not typer.confirm("Proceed with evaluation?"):
        raise typer.Exit(0)

    # Run the evaluation
    asyncio.run(_run_evaluation(
        config=config,
        occupation_codes=occupation_codes,
        industry_codes=industry_codes,
        job_zones=job_zone_list,
        formality_levels=formality_levels,
        age_range=(age_min, age_max) if age_min else None,
        max_concurrent=max_concurrent,
        output_dir=output_dir,
        resume_path=resume
    ))


async def _run_evaluation(
    config: EvalConfig,
    occupation_codes: Optional[List[str]],
    industry_codes: Optional[List[str]],
    job_zones: Optional[List[int]],
    formality_levels: Optional[List[int]],
    age_range: Optional[tuple],
    max_concurrent: int,
    output_dir: Path,
    resume_path: Optional[Path]
):
    """Run the actual evaluation."""
    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        typer.echo("Error: OPENROUTER_API_KEY not found in environment")
        raise typer.Exit(1)

    # Create or resume run directory
    if resume_path:
        run_dir = RunDirectory.load(resume_path)
    else:
        run_dir = RunDirectory.create(output_dir)

    # Initialize components
    client = OpenRouterClient(api_key)
    checkpoint_manager = CheckpointManager(run_dir)
    database = EvalDatabase(run_dir.results_db)

    # Generate prompts with filters
    prompts = await generate_prompts(
        config=config,
        occupation_codes=occupation_codes,
        industry_codes=industry_codes,
        job_zones=job_zones,
        formality_levels=formality_levels,
        age_range=age_range
    )

    # Create and run TUI with evaluation engine
    dashboard = ProgressDashboard()

    engine = EvaluationEngine(
        config=config,
        client=client,
        checkpoint_manager=checkpoint_manager,
        database=database,
        progress_callback=dashboard.update_progress,
        max_concurrent=max_concurrent
    )

    # Set up graceful quit handler
    dashboard.on_graceful_quit = lambda: asyncio.create_task(checkpoint_manager.save_final())

    try:
        # Run TUI and evaluation in parallel
        async with asyncio.TaskGroup() as tg:
            tg.create_task(dashboard.run_async())
            results = await engine.run_evaluation(prompts)
    finally:
        await client.close()
        await database.close()

    typer.echo(f"\nEvaluation complete. Results saved to: {run_dir.path}")


@app.command()
def view(
    run_path: Path = typer.Argument(..., help="Path to evaluation run directory"),
    filter_occupation: str = typer.Option(None, "--occupation", "-o", help="Filter by occupation code"),
    filter_industry: str = typer.Option(None, "--industry", "-i", help="Filter by NAICS code"),
    filter_winner: str = typer.Option(None, "--winner", "-w", help="Filter by winner (gemini/opponent/tie)"),
    sort_by: str = typer.Option("prompt_id", "--sort", "-s", help="Sort by field"),
):
    """View evaluation results interactively."""
    from .tui.results_viewer import ResultsViewer

    viewer = ResultsViewer(
        run_path=run_path,
        filter_occupation=filter_occupation,
        filter_industry=filter_industry,
        filter_winner=filter_winner,
        sort_by=sort_by
    )
    viewer.run()


@app.command()
def export(
    run_path: Path = typer.Argument(..., help="Path to evaluation run directory"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv, json"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export evaluation results."""
    from .storage.database import EvalDatabase
    import json
    import csv

    db = EvalDatabase(run_path / "results.db")
    results = asyncio.run(db.get_all_results())

    if format == "csv":
        output_path = output or run_path / "export.csv"
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys() if results else [])
            writer.writeheader()
            writer.writerows(results)
    elif format == "json":
        output_path = output or run_path / "export.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    typer.echo(f"Exported to: {output_path}")


@app.command()
def compare(
    run_paths: List[Path] = typer.Argument(..., help="Paths to evaluation runs to compare"),
    output: Path = typer.Option(None, "--output", "-o", help="Output report path"),
):
    """Compare results across multiple evaluation runs."""
    from .analysis.cross_run_compare import compare_runs

    comparison = asyncio.run(compare_runs(run_paths))

    if output:
        comparison.save_report(output)
        typer.echo(f"Comparison report saved to: {output}")
    else:
        typer.echo(comparison.summary())


if __name__ == "__main__":
    app()
```

---

## 6. TUI ETA CALCULATION AND CONFIDENCE INTERVALS

```python
# src/tui/components.py (more additions)

from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from typing import Optional
import time
from datetime import timedelta

class ETADisplay(Static):
    """Widget displaying elapsed time and ETA."""

    elapsed_seconds = reactive(0.0)
    eta_seconds = reactive(None)
    start_time = reactive(None)

    def render(self) -> Panel:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")

        # Elapsed time
        elapsed_str = self._format_duration(self.elapsed_seconds)
        table.add_row("Elapsed:", elapsed_str)

        # ETA
        if self.eta_seconds is not None:
            eta_str = self._format_duration(self.eta_seconds)
            completion_time = time.time() + self.eta_seconds
            completion_str = time.strftime("%H:%M:%S", time.localtime(completion_time))
            table.add_row("ETA:", f"{eta_str} (at {completion_str})")
        else:
            table.add_row("ETA:", "Calculating...")

        # Total estimated
        if self.eta_seconds is not None:
            total = self.elapsed_seconds + self.eta_seconds
            table.add_row("Total est.:", self._format_duration(total))

        return Panel(table, title="Time", border_style="yellow")

    def _format_duration(self, seconds: float) -> str:
        """Format seconds as human-readable duration."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def update_time(self, elapsed: float, eta: Optional[float]):
        """Update time values."""
        self.elapsed_seconds = elapsed
        self.eta_seconds = eta
        self.refresh()


class WinRateWithCI(Static):
    """Widget displaying win rates with confidence intervals."""

    win_rates: Dict[str, tuple] = {}  # model_pair -> (win_rate, ci_lower, ci_upper, n_samples)

    def render(self) -> Panel:
        if not self.win_rates:
            return Panel("No data yet", title="Win Rates (95% CI)")

        table = Table(show_header=True, box=None)
        table.add_column("Model Pair", style="cyan")
        table.add_column("Win Rate", justify="center")
        table.add_column("95% CI", justify="center")
        table.add_column("N", justify="right")

        for pair, (rate, ci_low, ci_high, n) in self.win_rates.items():
            # Color based on win rate
            if rate >= 0.55:
                style = "green"
            elif rate <= 0.45:
                style = "red"
            else:
                style = "yellow"

            # Format with trend indicator
            if rate > 0.5:
                trend = "↑"
            elif rate < 0.5:
                trend = "↓"
            else:
                trend = "→"

            pair_short = pair.replace("google/gemini-3.0-", "G3").replace("_vs_", " vs ").split("/")[-1][:20]

            table.add_row(
                pair_short,
                f"[{style}]{rate:.1%} {trend}[/]",
                f"[dim]{ci_low:.1%} - {ci_high:.1%}[/]",
                str(n)
            )

        return Panel(table, title="Win Rates (95% CI)", border_style="cyan")

    def update_rates(self, win_rates: Dict[str, tuple]):
        """Update win rate data."""
        self.win_rates = win_rates
        self.refresh()


def calculate_wilson_ci(wins: int, total: int, confidence: float = 0.95) -> tuple:
    """Calculate Wilson score confidence interval for a proportion."""
    from scipy import stats

    if total == 0:
        return (0.0, 0.0, 1.0)

    p = wins / total
    z = stats.norm.ppf(1 - (1 - confidence) / 2)

    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * ((p * (1 - p) + z**2 / (4 * total)) / total) ** 0.5 / denominator

    return (p, max(0, center - margin), min(1, center + margin))
```

---

## 7. CURRENT BATCH DISPLAY WITH OCCUPATION/INDUSTRY

```python
# src/tui/components.py (more additions)

class CurrentBatchStatus(Static):
    """Widget showing current batch details including occupation and industry."""

    current_prompt_id = reactive(None)
    current_occupation = reactive(None)
    current_occupation_code = reactive(None)
    current_industry = reactive(None)
    current_industry_code = reactive(None)
    response_a_status = reactive("pending")  # pending, generating, complete, error
    response_b_status = reactive("pending")
    response_a_time = reactive(None)
    response_b_time = reactive(None)
    model_a_name = reactive("Model A")
    model_b_name = reactive("Model B")
    judging_progress = reactive({})  # judge_model -> (completed, total)

    def render(self) -> Panel:
        content = Table(show_header=False, box=None, padding=(0, 1))
        content.add_column("Label", style="dim", width=18)
        content.add_column("Value")

        # Prompt info
        content.add_row("Prompt:", self.current_prompt_id or "--")
        content.add_row(
            "Occupation:",
            f"{self.current_occupation or '--'} ({self.current_occupation_code or '--'})"
        )
        content.add_row(
            "Industry:",
            f"{self.current_industry or '--'} (NAICS {self.current_industry_code or '--'})"
        )

        # Response status
        status_icons = {
            "pending": "[dim]○[/]",
            "generating": "[yellow]◐[/]",
            "complete": "[green]✓[/]",
            "error": "[red]✗[/]"
        }

        a_status = status_icons.get(self.response_a_status, "?")
        b_status = status_icons.get(self.response_b_status, "?")

        a_time = f" ({self.response_a_time:.1f}s)" if self.response_a_time else ""
        b_time = f" ({self.response_b_time:.1f}s)" if self.response_b_time else ""

        content.add_row(f"{self.model_a_name}:", f"{a_status}{a_time}")
        content.add_row(f"{self.model_b_name}:", f"{b_status}{b_time}")

        # Judging progress with per-judge breakdown
        if self.judging_progress:
            judge_parts = []
            for judge, (completed, total) in self.judging_progress.items():
                short_name = judge.split("/")[-1][:10]
                dots = "●" * completed + "○" * (total - completed)
                judge_parts.append(f"{short_name}: {dots}")

            content.add_row("Judging:", "\n".join(judge_parts))

        return Panel(content, title="Current Batch", border_style="magenta")

    def update_batch(
        self,
        prompt_id: str,
        occupation: str,
        occupation_code: str,
        industry: str,
        industry_code: str,
        model_a: str,
        model_b: str
    ):
        """Update current batch information."""
        self.current_prompt_id = prompt_id
        self.current_occupation = occupation
        self.current_occupation_code = occupation_code
        self.current_industry = industry
        self.current_industry_code = industry_code
        self.model_a_name = model_a.split("/")[-1]
        self.model_b_name = model_b.split("/")[-1]
        self.refresh()

    def update_response_status(self, model: str, status: str, time_ms: float = None):
        """Update response generation status."""
        if "gemini" in model.lower():
            self.response_a_status = status
            if time_ms:
                self.response_a_time = time_ms / 1000
        else:
            self.response_b_status = status
            if time_ms:
                self.response_b_time = time_ms / 1000
        self.refresh()

    def update_judging(self, judge_progress: Dict[str, tuple]):
        """Update judging progress."""
        self.judging_progress = judge_progress
        self.refresh()
```

---

## 8. NAME FORMALITY VARIATION

```python
# src/data/name_generator.py (enhanced with formality variation)

import random
from dataclasses import dataclass
from typing import Optional, List, Literal
from enum import Enum

class NameFormality(str, Enum):
    VERY_FORMAL = "very_formal"      # Dr. Elizabeth A. Williams, MD
    FORMAL = "formal"                 # Elizabeth Williams
    SEMI_FORMAL = "semi_formal"       # Elizabeth
    CASUAL = "casual"                 # Liz
    VERY_CASUAL = "very_casual"       # Lizzy

@dataclass
class GeneratedName:
    """A generated name with all variations."""
    first_name: str
    last_name: str
    middle_initial: Optional[str]
    nickname: Optional[str]
    prefix: Optional[str]  # Dr., Mr., Ms., etc.
    suffix: Optional[str]  # Jr., III, PhD, etc.
    gender: str
    ethnicity: str
    generation: str  # boomer, gen_x, millennial, gen_z, gen_alpha

    def format(self, formality: NameFormality) -> str:
        """Format name according to formality level."""
        if formality == NameFormality.VERY_FORMAL:
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

        elif formality == NameFormality.FORMAL:
            return f"{self.first_name} {self.last_name}"

        elif formality == NameFormality.SEMI_FORMAL:
            return self.first_name

        elif formality == NameFormality.CASUAL:
            return self.nickname if self.nickname else self.first_name

        elif formality == NameFormality.VERY_CASUAL:
            # Use diminutive if available
            return self._get_diminutive()

        return f"{self.first_name} {self.last_name}"

    def _get_diminutive(self) -> str:
        """Get informal/diminutive version of name."""
        diminutives = {
            "Elizabeth": "Lizzy",
            "William": "Billy",
            "Michael": "Mikey",
            "Jennifer": "Jenny",
            "Robert": "Bobby",
            "Katherine": "Katie",
            "Richard": "Ricky",
            "Thomas": "Tommy",
            "Christopher": "Chris",
            "Patricia": "Patty",
            "Margaret": "Maggie",
            "James": "Jimmy",
            "Joseph": "Joey",
            "David": "Dave",
            "Alexander": "Alex",
            "Benjamin": "Benny",
            "Daniel": "Danny",
            "Matthew": "Matt",
            "Anthony": "Tony",
            "Steven": "Stevie",
        }
        return diminutives.get(self.first_name, self.nickname or self.first_name)

    def get_email(self, company_domain: str) -> str:
        """Generate realistic email address."""
        formats = [
            f"{self.first_name.lower()}.{self.last_name.lower()}@{company_domain}",
            f"{self.first_name[0].lower()}{self.last_name.lower()}@{company_domain}",
            f"{self.first_name.lower()}{self.last_name[0].lower()}@{company_domain}",
            f"{self.first_name.lower()}@{company_domain}",
        ]
        return random.choice(formats)


class NameGenerator:
    """Generate diverse, realistic names with formality variations."""

    # Census-based name frequencies (simplified)
    NAMES_BY_ETHNICITY = {
        "anglo": {
            "male": ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Christopher"],
            "female": ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
        },
        "hispanic": {
            "male": ["José", "Miguel", "Carlos", "Juan", "Luis", "Pedro", "Antonio", "Diego", "Alejandro", "Rafael"],
            "female": ["María", "Carmen", "Rosa", "Ana", "Lucia", "Isabella", "Sofia", "Valentina", "Camila", "Gabriela"]
        },
        "asian": {
            "male": ["Wei", "Hiroshi", "Kenji", "Raj", "Vikram", "Jin", "Chen", "Kevin", "Andrew", "Eric"],
            "female": ["Mei", "Yuki", "Priya", "Anita", "Lin", "Sakura", "Aiko", "Michelle", "Amy", "Grace"]
        },
        "african_american": {
            "male": ["Marcus", "Jamal", "Terrence", "Darnell", "DeShawn", "Tyrone", "Andre", "Malcolm", "Xavier", "Isaiah"],
            "female": ["Jasmine", "Aaliyah", "Imani", "Keisha", "Shaniqua", "Tamika", "Latoya", "Destiny", "Maya", "Zoe"]
        }
    }

    LAST_NAMES_BY_ETHNICITY = {
        "anglo": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Anderson", "Taylor"],
        "hispanic": ["García", "Rodríguez", "Martínez", "López", "González", "Hernández", "Pérez", "Sánchez", "Ramírez", "Torres"],
        "asian": ["Chen", "Wang", "Kim", "Nguyen", "Tanaka", "Suzuki", "Patel", "Singh", "Lee", "Zhang"],
        "african_american": ["Washington", "Jefferson", "Jackson", "Robinson", "Freeman", "Harris", "Brooks", "Coleman", "Hayes", "Jordan"]
    }

    NICKNAMES = {
        "Elizabeth": ["Liz", "Beth", "Lizzy"],
        "William": ["Will", "Bill", "Billy"],
        "Michael": ["Mike", "Mikey"],
        "Jennifer": ["Jen", "Jenny"],
        "Robert": ["Rob", "Bob", "Bobby"],
        "Katherine": ["Kate", "Katie", "Kathy"],
        "Richard": ["Rick", "Dick", "Richie"],
        "Thomas": ["Tom", "Tommy"],
        "Christopher": ["Chris", "Topher"],
        "Patricia": ["Pat", "Patty", "Trish"],
    }

    PREFIXES_BY_ROLE = {
        "medical": ["Dr."],
        "academic": ["Dr.", "Prof."],
        "military": ["Col.", "Maj.", "Capt."],
        "legal": ["Esq."],
        "religious": ["Rev.", "Fr."],
        "general": ["Mr.", "Ms.", "Mrs."]
    }

    SUFFIXES = ["Jr.", "Sr.", "III", "IV", "PhD", "MD", "JD", "MBA", "CPA"]

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed)

    def generate(
        self,
        gender: Optional[str] = None,
        ethnicity: Optional[str] = None,
        generation: Optional[str] = None,
        role_type: Optional[str] = None,
        include_prefix_probability: float = 0.1,
        include_suffix_probability: float = 0.05
    ) -> GeneratedName:
        """Generate a random name with specified characteristics."""

        # Random selection if not specified
        if gender is None:
            gender = self.rng.choice(["male", "female"])
        if ethnicity is None:
            # Weighted by US demographics (approximate)
            ethnicity = self.rng.choices(
                ["anglo", "hispanic", "asian", "african_american"],
                weights=[0.6, 0.18, 0.06, 0.13]
            )[0]
        if generation is None:
            generation = self.rng.choice(["boomer", "gen_x", "millennial", "gen_z", "gen_alpha"])

        # Select names
        first_names = self.NAMES_BY_ETHNICITY.get(ethnicity, self.NAMES_BY_ETHNICITY["anglo"])[gender]
        last_names = self.LAST_NAMES_BY_ETHNICITY.get(ethnicity, self.LAST_NAMES_BY_ETHNICITY["anglo"])

        first_name = self.rng.choice(first_names)
        last_name = self.rng.choice(last_names)

        # Middle initial
        middle_initial = self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") if self.rng.random() < 0.5 else None

        # Nickname
        nickname = None
        if first_name in self.NICKNAMES:
            nickname = self.rng.choice(self.NICKNAMES[first_name])

        # Prefix
        prefix = None
        if self.rng.random() < include_prefix_probability:
            prefixes = self.PREFIXES_BY_ROLE.get(role_type, self.PREFIXES_BY_ROLE["general"])
            prefix = self.rng.choice(prefixes)

        # Suffix
        suffix = None
        if self.rng.random() < include_suffix_probability:
            suffix = self.rng.choice(self.SUFFIXES)

        return GeneratedName(
            first_name=first_name,
            last_name=last_name,
            middle_initial=middle_initial,
            nickname=nickname,
            prefix=prefix,
            suffix=suffix,
            gender=gender,
            ethnicity=ethnicity,
            generation=generation
        )

    def generate_for_formality(
        self,
        formality_level: int,
        **kwargs
    ) -> tuple[GeneratedName, str]:
        """Generate name and format it for given formality level (1-5)."""

        # Map formality level (1-5) to NameFormality
        formality_map = {
            1: NameFormality.VERY_CASUAL,
            2: NameFormality.CASUAL,
            3: NameFormality.SEMI_FORMAL,
            4: NameFormality.FORMAL,
            5: NameFormality.VERY_FORMAL,
        }

        formality = formality_map.get(formality_level, NameFormality.FORMAL)

        # For formal communications, increase prefix probability
        if formality_level >= 4:
            kwargs["include_prefix_probability"] = kwargs.get("include_prefix_probability", 0.3)

        name = self.generate(**kwargs)
        formatted = name.format(formality)

        return name, formatted
```

---

## 9. PHASE 1 GENERATION USING EVALUATED MODELS

```python
# src/prompts/phase1_offline.py

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional
import json
import random

from ..api.openrouter_client import OpenRouterClient
from ..config.presets import PRO_PAIRS, FLASH_PAIRS
from .schemas import WritingPrompt, WriterPersona, RecipientPersona

@dataclass
class Phase1Variation:
    """A generated variation from Phase 1."""
    source_task_id: str
    generated_by_model: str
    persona_variation: Dict
    context_variation: Dict
    raw_generation: str

class Phase1Generator:
    """
    Phase 1 offline generation using the same models being evaluated.

    This creates potential bias but ensures prompts aren't accidentally
    biased against any particular model.
    """

    # Use the models being evaluated for generation
    GENERATION_MODELS = [
        "google/gemini-3.0-pro",
        "openai/gpt-5.2",
        "anthropic/claude-opus-4.5",
        "google/gemini-3.0-flash",
        "openai/gpt-4.1",
        "anthropic/claude-sonnet-4",
    ]

    VARIATION_PROMPT = '''Generate 5 diverse persona and context variations for this O*NET writing task.

Task: {task_statement}
Occupation: {occupation_title}
Job Zone: {job_zone}

For each variation, provide:
1. Writer persona (name, age, gender, skill level 1-5, generation)
2. Recipient persona (name, relationship to writer, their characteristics)
3. Context details (urgency 1-5, emotional context, specific situation)
4. Formality level (1-5)
5. Any special circumstances (deadline, CC'd parties, prior context needed)

Be DIVERSE across:
- Age ranges (18-70)
- Skill levels (entry-level to executive)
- Formality (very casual to extremely formal)
- Urgency (routine to critical)
- Emotional context (routine, celebration, crisis, conflict, bad news)

Return as JSON array with 5 objects.
'''

    def __init__(self, client: OpenRouterClient, seed: int = None):
        self.client = client
        self.rng = random.Random(seed)

    async def generate_variations(
        self,
        task_id: str,
        task_statement: str,
        occupation_title: str,
        job_zone: int,
        num_variations: int = 5
    ) -> List[Phase1Variation]:
        """Generate persona/context variations for a task using evaluated models."""

        # Rotate through models to avoid bias
        model = self.rng.choice(self.GENERATION_MODELS)

        prompt = self.VARIATION_PROMPT.format(
            task_statement=task_statement,
            occupation_title=occupation_title,
            job_zone=job_zone
        )

        try:
            response = await self.client.complete(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a creative writing scenario generator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9  # Higher temperature for diversity
            )

            # Parse JSON response
            content = response.content.strip()
            if content.startswith("```"):
                # Extract from code block
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            variations_data = json.loads(content)

            variations = []
            for var in variations_data[:num_variations]:
                variations.append(Phase1Variation(
                    source_task_id=task_id,
                    generated_by_model=model,
                    persona_variation=var.get("writer", {}),
                    context_variation=var.get("context", {}),
                    raw_generation=json.dumps(var)
                ))

            return variations

        except Exception as e:
            # Log error and return empty list
            print(f"Phase 1 generation failed for {task_id}: {e}")
            return []

    async def generate_batch(
        self,
        tasks: List[Dict],
        variations_per_task: int = 5,
        max_concurrent: int = 10
    ) -> Dict[str, List[Phase1Variation]]:
        """Generate variations for a batch of tasks."""

        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_generate(task):
            async with semaphore:
                return task["task_id"], await self.generate_variations(
                    task_id=task["task_id"],
                    task_statement=task["task_statement"],
                    occupation_title=task["occupation_title"],
                    job_zone=task["job_zone"],
                    num_variations=variations_per_task
                )

        results = await asyncio.gather(*[limited_generate(t) for t in tasks])
        return {task_id: variations for task_id, variations in results}

    def save_variations(self, variations: Dict[str, List[Phase1Variation]], output_path: str):
        """Save generated variations to file for offline use."""
        data = {}
        for task_id, task_variations in variations.items():
            data[task_id] = [
                {
                    "source_task_id": v.source_task_id,
                    "generated_by_model": v.generated_by_model,
                    "persona_variation": v.persona_variation,
                    "context_variation": v.context_variation,
                }
                for v in task_variations
            ]

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_variations(input_path: str) -> Dict[str, List[Phase1Variation]]:
        """Load previously generated variations."""
        with open(input_path) as f:
            data = json.load(f)

        result = {}
        for task_id, variations in data.items():
            result[task_id] = [
                Phase1Variation(
                    source_task_id=v["source_task_id"],
                    generated_by_model=v["generated_by_model"],
                    persona_variation=v["persona_variation"],
                    context_variation=v["context_variation"],
                    raw_generation=""
                )
                for v in variations
            ]
        return result
```

---

## 10. AMBIGUITY BEHAVIOR TRACKING

```python
# src/eval/ambiguity_tracker.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from enum import Enum
import re

class AmbiguityBehavior(str, Enum):
    """How model handled ambiguity in prompt."""
    MADE_ASSUMPTIONS = "made_assumptions"           # Proceeded with reasonable assumptions
    ASKED_CLARIFICATION = "asked_clarification"     # Asked questions in response
    HEDGED = "hedged"                                # Used qualifying language
    HALLUCINATED_DETAILS = "hallucinated_details"   # Made up specific details
    REFUSED = "refused"                              # Refused to proceed without clarification
    UNCLEAR = "unclear"                              # Could not determine behavior

@dataclass
class AmbiguityAnalysis:
    """Analysis of how a model handled ambiguous prompt."""
    prompt_id: str
    model: str
    ambiguity_type: str
    behavior: AmbiguityBehavior
    evidence: List[str]
    assumptions_made: List[str]
    clarification_questions: List[str]
    hedging_phrases: List[str]
    hallucinated_details: List[str]
    confidence: float  # 0-1, how confident are we in this classification

class AmbiguityTracker:
    """Track how models handle deliberately ambiguous prompts."""

    # Patterns indicating clarification questions
    CLARIFICATION_PATTERNS = [
        r"could you (please )?(clarify|specify|tell me|provide)",
        r"what (exactly|specifically) (do you mean|would you like)",
        r"I('d| would) need (more information|to know|clarification)",
        r"can you (be more specific|elaborate)",
        r"which (one|option|type) (do you|would you)",
        r"is (this|that) referring to",
        r"\?$",  # Questions at end
    ]

    # Patterns indicating hedging/qualifying language
    HEDGING_PATTERNS = [
        r"assuming (that|you mean)",
        r"I('ll| will) assume",
        r"if (I understand|you mean)",
        r"based on (my understanding|the context)",
        r"it (seems|appears) (like|that)",
        r"(perhaps|maybe|possibly)",
        r"without (more|additional) (context|information)",
        r"(depending on|subject to)",
        r"(might|may|could) (be|mean)",
    ]

    # Patterns indicating hallucinated specifics
    HALLUCINATION_INDICATORS = [
        r"(on|at) \d{1,2}[:/]\d{2}",  # Specific times
        r"\$[\d,]+(\.\d{2})?",  # Specific dollar amounts
        r"\d{1,2}/\d{1,2}/\d{2,4}",  # Specific dates
        r"(meeting|call|event) (on|at) (Monday|Tuesday|Wednesday|Thursday|Friday)",
        r"(room|floor|building) [A-Z]?\d+",  # Specific locations
    ]

    def __init__(self):
        self.analyses: List[AmbiguityAnalysis] = []

    def analyze_response(
        self,
        prompt_id: str,
        model: str,
        ambiguity_type: str,
        response_content: str
    ) -> AmbiguityAnalysis:
        """Analyze how a response handled ambiguity."""

        evidence = []
        assumptions = []
        clarifications = []
        hedging = []
        hallucinations = []

        content_lower = response_content.lower()

        # Check for clarification questions
        for pattern in self.CLARIFICATION_PATTERNS:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                clarifications.extend([str(m) for m in matches])
                evidence.append(f"Clarification pattern: {pattern}")

        # Check for hedging language
        for pattern in self.HEDGING_PATTERNS:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                hedging.extend([str(m) for m in matches])
                evidence.append(f"Hedging pattern: {pattern}")

        # Check for hallucinated details
        for pattern in self.HALLUCINATION_INDICATORS:
            matches = re.findall(pattern, response_content, re.IGNORECASE)
            if matches:
                hallucinations.extend([str(m) for m in matches])
                evidence.append(f"Potential hallucination: {pattern}")

        # Check for explicit assumptions
        assumption_patterns = [
            r"I('ll| will| am going to) assume",
            r"assuming",
            r"I('m| am) taking this to mean",
        ]
        for pattern in assumption_patterns:
            matches = re.findall(pattern, content_lower)
            if matches:
                assumptions.extend([str(m) for m in matches])

        # Determine primary behavior
        behavior = self._classify_behavior(
            clarifications, hedging, hallucinations, assumptions, response_content
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            behavior, clarifications, hedging, hallucinations, assumptions
        )

        analysis = AmbiguityAnalysis(
            prompt_id=prompt_id,
            model=model,
            ambiguity_type=ambiguity_type,
            behavior=behavior,
            evidence=evidence,
            assumptions_made=assumptions,
            clarification_questions=clarifications,
            hedging_phrases=hedging,
            hallucinated_details=hallucinations,
            confidence=confidence
        )

        self.analyses.append(analysis)
        return analysis

    def _classify_behavior(
        self,
        clarifications: List[str],
        hedging: List[str],
        hallucinations: List[str],
        assumptions: List[str],
        content: str
    ) -> AmbiguityBehavior:
        """Classify the primary ambiguity handling behavior."""

        # Priority order for classification
        if len(clarifications) >= 2 or "?" in content[-100:]:
            return AmbiguityBehavior.ASKED_CLARIFICATION

        if len(hallucinations) >= 2:
            return AmbiguityBehavior.HALLUCINATED_DETAILS

        if len(assumptions) >= 1 and len(hedging) >= 1:
            return AmbiguityBehavior.MADE_ASSUMPTIONS

        if len(hedging) >= 2:
            return AmbiguityBehavior.HEDGED

        if "cannot" in content.lower() or "unable to" in content.lower():
            return AmbiguityBehavior.REFUSED

        # Default: made assumptions (most common behavior)
        return AmbiguityBehavior.MADE_ASSUMPTIONS

    def _calculate_confidence(
        self,
        behavior: AmbiguityBehavior,
        clarifications: List[str],
        hedging: List[str],
        hallucinations: List[str],
        assumptions: List[str]
    ) -> float:
        """Calculate confidence in the classification."""

        # More evidence = higher confidence
        evidence_count = len(clarifications) + len(hedging) + len(hallucinations) + len(assumptions)

        if evidence_count == 0:
            return 0.3  # Low confidence if no clear evidence

        if evidence_count >= 5:
            return 0.9

        if evidence_count >= 3:
            return 0.7

        return 0.5

    def get_summary_by_model(self) -> Dict[str, Dict[str, int]]:
        """Get summary of behaviors by model."""
        summary = {}
        for analysis in self.analyses:
            if analysis.model not in summary:
                summary[analysis.model] = {b.value: 0 for b in AmbiguityBehavior}
            summary[analysis.model][analysis.behavior.value] += 1
        return summary

    def get_summary_by_ambiguity_type(self) -> Dict[str, Dict[str, int]]:
        """Get summary of behaviors by ambiguity type."""
        summary = {}
        for analysis in self.analyses:
            if analysis.ambiguity_type not in summary:
                summary[analysis.ambiguity_type] = {b.value: 0 for b in AmbiguityBehavior}
            summary[analysis.ambiguity_type][analysis.behavior.value] += 1
        return summary
```

---

## 11. TUI RESULTS VIEWER WITH FILTERING, SORTING, DRILL-DOWN

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Select,
    Button, Label, TabbedContent, TabPane, RichLog
)
from textual.binding import Binding
from textual.screen import ModalScreen
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from pathlib import Path
from typing import Optional, List, Dict
import json
import asyncio

from ..storage.database import EvalDatabase


class FilterBar(Static):
    """Filter controls for results viewer."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="filter-bar"):
            yield Label("Filters: ")
            yield Input(placeholder="Occupation code...", id="filter-occupation")
            yield Input(placeholder="Industry code...", id="filter-industry")
            yield Select(
                [("All", "all"), ("Gemini Wins", "gemini"), ("Opponent Wins", "opponent"), ("Ties", "tie")],
                id="filter-winner",
                value="all"
            )
            yield Select(
                [("Prompt ID", "prompt_id"), ("Win Rate", "win_rate"), ("Occupation", "occupation"), ("Industry", "industry")],
                id="sort-by",
                value="prompt_id"
            )
            yield Button("Apply", id="apply-filters", variant="primary")
            yield Button("Clear", id="clear-filters")


class ComparisonDetail(ModalScreen):
    """Modal showing detailed comparison view."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("left", "prev_comparison", "Previous"),
        Binding("right", "next_comparison", "Next"),
    ]

    def __init__(self, comparison_data: Dict, **kwargs):
        super().__init__(**kwargs)
        self.comparison = comparison_data

    def compose(self) -> ComposeResult:
        with Container(id="detail-container"):
            yield Static(self._build_header(), id="detail-header")

            with Horizontal(id="responses-container"):
                with Vertical(id="response-a"):
                    yield Static("[bold]Gemini Response[/bold]", id="response-a-title")
                    yield ScrollableContainer(
                        Static(self.comparison.get("response_a", "No response"), id="response-a-content")
                    )

                with Vertical(id="response-b"):
                    yield Static("[bold]Opponent Response[/bold]", id="response-b-title")
                    yield ScrollableContainer(
                        Static(self.comparison.get("response_b", "No response"), id="response-b-content")
                    )

            yield Static(self._build_judgments(), id="judgments-panel")
            yield Static(self._build_metadata(), id="metadata-panel")

    def _build_header(self) -> Panel:
        """Build header with prompt info."""
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Prompt ID:", self.comparison.get("prompt_id", "--"))
        table.add_row("Occupation:", self.comparison.get("occupation", "--"))
        table.add_row("Industry:", self.comparison.get("industry", "--"))
        table.add_row("Winner:", f"[bold]{self.comparison.get('winner', '--')}[/bold]")

        return Panel(table, title="Comparison Details")

    def _build_judgments(self) -> Panel:
        """Build judgments breakdown panel."""
        judgments = self.comparison.get("judgments", [])

        table = Table(show_header=True)
        table.add_column("Judge")
        table.add_column("Persona")
        table.add_column("Winner")
        table.add_column("Confidence")
        table.add_column("Reasoning")

        for j in judgments:
            table.add_row(
                j.get("judge_model", "--").split("/")[-1],
                j.get("persona", "--"),
                j.get("winner", "--"),
                f"{j.get('confidence', 0):.0%}",
                j.get("reasoning", "--")[:100] + "..."
            )

        return Panel(table, title="Judge Votes")

    def _build_metadata(self) -> Panel:
        """Build metadata panel."""
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Formality Level:", str(self.comparison.get("formality_level", "--")))
        table.add_row("Urgency Level:", str(self.comparison.get("urgency_level", "--")))
        table.add_row("Emotional Context:", self.comparison.get("emotional_context", "--"))
        table.add_row("Message Position:", self.comparison.get("message_position", "--"))

        return Panel(table, title="Prompt Metadata")


class ResultsViewer(App):
    """Interactive TUI for viewing evaluation results."""

    CSS = """
    #filter-bar {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    #results-table {
        height: 100%;
    }

    #detail-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    #responses-container {
        height: 60%;
    }

    #response-a, #response-b {
        width: 50%;
        border: solid $secondary;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filters", "Filters"),
        Binding("enter", "view_detail", "View Detail"),
        Binding("/", "search", "Search"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(
        self,
        run_path: Path,
        filter_occupation: str = None,
        filter_industry: str = None,
        filter_winner: str = None,
        sort_by: str = "prompt_id",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.run_path = run_path
        self.filter_occupation = filter_occupation
        self.filter_industry = filter_industry
        self.filter_winner = filter_winner
        self.sort_by = sort_by
        self.results: List[Dict] = []
        self.filtered_results: List[Dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield FilterBar()
        yield DataTable(id="results-table")
        yield Footer()

    async def on_mount(self):
        """Load data when app mounts."""
        await self._load_results()
        self._populate_table()

    async def _load_results(self):
        """Load results from database."""
        db = EvalDatabase(self.run_path / "results.db")
        self.results = await db.get_all_comparisons()
        self._apply_filters()

    def _apply_filters(self):
        """Apply current filters to results."""
        self.filtered_results = []

        for r in self.results:
            # Occupation filter
            if self.filter_occupation:
                if self.filter_occupation not in r.get("occupation_code", ""):
                    continue

            # Industry filter
            if self.filter_industry:
                if self.filter_industry not in r.get("industry_code", ""):
                    continue

            # Winner filter
            if self.filter_winner and self.filter_winner != "all":
                winner = r.get("winner", "")
                if self.filter_winner == "gemini" and "gemini" not in winner.lower():
                    continue
                elif self.filter_winner == "opponent" and "gemini" in winner.lower():
                    continue
                elif self.filter_winner == "tie" and winner:
                    continue

            self.filtered_results.append(r)

        # Sort
        if self.sort_by == "prompt_id":
            self.filtered_results.sort(key=lambda x: x.get("prompt_id", ""))
        elif self.sort_by == "occupation":
            self.filtered_results.sort(key=lambda x: x.get("occupation", ""))
        elif self.sort_by == "industry":
            self.filtered_results.sort(key=lambda x: x.get("industry", ""))

    def _populate_table(self):
        """Populate the data table."""
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)

        table.add_columns(
            "Prompt ID",
            "Occupation",
            "Industry",
            "Winner",
            "Judge Votes",
            "Formality",
            "Urgency"
        )

        for r in self.filtered_results:
            winner = r.get("winner", "--")
            winner_style = "green" if "gemini" in winner.lower() else "red" if winner else "yellow"

            table.add_row(
                r.get("prompt_id", "--"),
                r.get("occupation", "--")[:30],
                r.get("industry", "--")[:20],
                f"[{winner_style}]{winner}[/]",
                self._format_votes(r.get("judgments", [])),
                str(r.get("formality_level", "--")),
                str(r.get("urgency_level", "--"))
            )

    def _format_votes(self, judgments: List[Dict]) -> str:
        """Format judge votes for display."""
        gemini = sum(1 for j in judgments if "gemini" in j.get("winner", "").lower())
        opponent = sum(1 for j in judgments if j.get("winner") and "gemini" not in j.get("winner", "").lower())
        tie = len(judgments) - gemini - opponent

        return f"G:{gemini} O:{opponent} T:{tie}"

    def action_view_detail(self):
        """View detailed comparison for selected row."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.filtered_results):
            comparison = self.filtered_results[table.cursor_row]
            self.push_screen(ComparisonDetail(comparison))

    async def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        if event.button.id == "apply-filters":
            await self._apply_and_refresh()
        elif event.button.id == "clear-filters":
            self.filter_occupation = None
            self.filter_industry = None
            self.filter_winner = None
            await self._apply_and_refresh()

    async def _apply_and_refresh(self):
        """Apply filters and refresh table."""
        # Get filter values from inputs
        occ_input = self.query_one("#filter-occupation", Input)
        ind_input = self.query_one("#filter-industry", Input)
        winner_select = self.query_one("#filter-winner", Select)
        sort_select = self.query_one("#sort-by", Select)

        self.filter_occupation = occ_input.value or None
        self.filter_industry = ind_input.value or None
        self.filter_winner = winner_select.value
        self.sort_by = sort_select.value

        self._apply_filters()
        self._populate_table()
```

---

## 12. REFUSAL TRACKING BY DIMENSION

```python
# src/eval/refusal_classifier.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import re
from collections import defaultdict

class RefusalType(str, Enum):
    """Types of refusals."""
    SAFETY = "safety"                    # Model cites safety/policy concerns
    CAPABILITY = "capability"            # Model says it can't do the task
    MISUNDERSTANDING = "misunderstanding"  # Model interprets task incorrectly
    INCOMPLETE = "incomplete"            # Model starts but doesn't finish
    OFF_TOPIC = "off_topic"              # Model responds but not to the task
    NONE = "none"                        # Not a refusal

@dataclass
class RefusalAnalysis:
    """Analysis of a potential refusal."""
    is_refusal: bool
    refusal_type: RefusalType
    confidence: float
    evidence: List[str]
    sensitive_topics_triggered: List[str]

@dataclass
class RefusalTrackingStats:
    """Aggregated refusal statistics."""
    total_responses: int
    total_refusals: int
    refusal_rate: float
    by_type: Dict[str, int]
    by_model: Dict[str, Dict[str, int]]
    by_task_type: Dict[str, Dict[str, int]]
    by_sensitive_topic: Dict[str, Dict[str, int]]
    by_occupation: Dict[str, Dict[str, int]]
    by_industry: Dict[str, Dict[str, int]]
    by_formality: Dict[int, Dict[str, int]]

class RefusalClassifier:
    """Classify and track model refusals."""

    # Safety refusal patterns
    SAFETY_PATTERNS = [
        r"I (cannot|can't|am unable to|won't) (help with|assist with|provide|write)",
        r"(against|violates) (my|our) (guidelines|policies|terms)",
        r"(inappropriate|harmful|unethical|dangerous)",
        r"I'm (not able|unable) to (generate|create|write) (that|this)",
        r"(safety|ethical) (concerns|considerations|reasons)",
        r"I (must|need to) (decline|refuse)",
    ]

    # Capability limitation patterns
    CAPABILITY_PATTERNS = [
        r"I (don't|do not) have (access to|knowledge of|information about)",
        r"(beyond|outside) my (capabilities|abilities|scope)",
        r"I'm (just|only) an AI",
        r"I (cannot|can't) (access|retrieve|look up)",
        r"(real-time|current|live) (data|information) (is|are) not available",
    ]

    # Misunderstanding patterns
    MISUNDERSTANDING_PATTERNS = [
        r"I('m| am) not sure (what you|if you)",
        r"(Could you|Can you) (clarify|explain|specify)",
        r"I (don't|do not) (understand|follow) (the|your) (request|question)",
        r"(What do you mean|What are you asking)",
    ]

    # Off-topic patterns
    OFF_TOPIC_PATTERNS = [
        r"(Here's|Here is) (some|general) information about",
        r"(Instead|However), (let me|I'll) (explain|discuss|describe)",
        r"(That's an interesting|Great) question, (but|however)",
    ]

    def __init__(self):
        self.analyses: List[Tuple[RefusalAnalysis, Dict]] = []  # (analysis, metadata)

    def classify(
        self,
        response_content: str,
        prompt_metadata: Optional[Dict] = None
    ) -> RefusalAnalysis:
        """Classify whether a response is a refusal and what type."""

        evidence = []
        content_lower = response_content.lower()

        # Check for safety refusals
        safety_score = 0
        for pattern in self.SAFETY_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                safety_score += 1
                evidence.append(f"Safety pattern: {pattern}")

        # Check for capability limitations
        capability_score = 0
        for pattern in self.CAPABILITY_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                capability_score += 1
                evidence.append(f"Capability pattern: {pattern}")

        # Check for misunderstanding
        misunderstanding_score = 0
        for pattern in self.MISUNDERSTANDING_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                misunderstanding_score += 1
                evidence.append(f"Misunderstanding pattern: {pattern}")

        # Check for off-topic
        off_topic_score = 0
        for pattern in self.OFF_TOPIC_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                off_topic_score += 1
                evidence.append(f"Off-topic pattern: {pattern}")

        # Check for incomplete (very short response or ends abruptly)
        incomplete = len(response_content.strip()) < 50 or response_content.strip().endswith("...")

        # Determine refusal type
        max_score = max(safety_score, capability_score, misunderstanding_score, off_topic_score)

        if max_score == 0 and not incomplete:
            refusal_type = RefusalType.NONE
            is_refusal = False
            confidence = 0.9
        elif safety_score == max_score and safety_score >= 1:
            refusal_type = RefusalType.SAFETY
            is_refusal = True
            confidence = min(0.5 + safety_score * 0.15, 0.95)
        elif capability_score == max_score and capability_score >= 1:
            refusal_type = RefusalType.CAPABILITY
            is_refusal = True
            confidence = min(0.5 + capability_score * 0.15, 0.95)
        elif misunderstanding_score == max_score and misunderstanding_score >= 1:
            refusal_type = RefusalType.MISUNDERSTANDING
            is_refusal = True
            confidence = min(0.4 + misunderstanding_score * 0.15, 0.85)
        elif off_topic_score == max_score and off_topic_score >= 1:
            refusal_type = RefusalType.OFF_TOPIC
            is_refusal = True
            confidence = min(0.4 + off_topic_score * 0.15, 0.85)
        elif incomplete:
            refusal_type = RefusalType.INCOMPLETE
            is_refusal = True
            confidence = 0.6
        else:
            refusal_type = RefusalType.NONE
            is_refusal = False
            confidence = 0.7

        # Extract sensitive topics that may have triggered refusal
        sensitive_topics = []
        if prompt_metadata:
            sensitive_topics = prompt_metadata.get("sensitive_topics", [])

        analysis = RefusalAnalysis(
            is_refusal=is_refusal,
            refusal_type=refusal_type,
            confidence=confidence,
            evidence=evidence,
            sensitive_topics_triggered=sensitive_topics
        )

        # Store for aggregation
        if prompt_metadata:
            self.analyses.append((analysis, prompt_metadata))

        return analysis

    def get_statistics(self) -> RefusalTrackingStats:
        """Get aggregated refusal statistics across all dimensions."""

        total = len(self.analyses)
        refusals = sum(1 for a, _ in self.analyses if a.is_refusal)

        by_type = defaultdict(int)
        by_model = defaultdict(lambda: defaultdict(int))
        by_task_type = defaultdict(lambda: defaultdict(int))
        by_sensitive_topic = defaultdict(lambda: defaultdict(int))
        by_occupation = defaultdict(lambda: defaultdict(int))
        by_industry = defaultdict(lambda: defaultdict(int))
        by_formality = defaultdict(lambda: defaultdict(int))

        for analysis, metadata in self.analyses:
            if analysis.is_refusal:
                rtype = analysis.refusal_type.value

                # By type
                by_type[rtype] += 1

                # By model
                model = metadata.get("model", "unknown")
                by_model[model][rtype] += 1
                by_model[model]["total"] += 1

                # By task type (from O*NET task category)
                task_type = metadata.get("task_type", "unknown")
                by_task_type[task_type][rtype] += 1
                by_task_type[task_type]["total"] += 1

                # By sensitive topic
                for topic in analysis.sensitive_topics_triggered:
                    by_sensitive_topic[topic][rtype] += 1
                    by_sensitive_topic[topic]["total"] += 1

                # By occupation
                occupation = metadata.get("occupation_code", "unknown")
                by_occupation[occupation][rtype] += 1
                by_occupation[occupation]["total"] += 1

                # By industry
                industry = metadata.get("industry_code", "unknown")
                by_industry[industry][rtype] += 1
                by_industry[industry]["total"] += 1

                # By formality
                formality = metadata.get("formality_level", 3)
                by_formality[formality][rtype] += 1
                by_formality[formality]["total"] += 1

        return RefusalTrackingStats(
            total_responses=total,
            total_refusals=refusals,
            refusal_rate=refusals / total if total > 0 else 0,
            by_type=dict(by_type),
            by_model={k: dict(v) for k, v in by_model.items()},
            by_task_type={k: dict(v) for k, v in by_task_type.items()},
            by_sensitive_topic={k: dict(v) for k, v in by_sensitive_topic.items()},
            by_occupation={k: dict(v) for k, v in by_occupation.items()},
            by_industry={k: dict(v) for k, v in by_industry.items()},
            by_formality={k: dict(v) for k, v in by_formality.items()}
        )

    def generate_report(self) -> str:
        """Generate a text report of refusal patterns."""
        stats = self.get_statistics()

        lines = [
            "# Refusal Analysis Report",
            "",
            f"Total Responses: {stats.total_responses}",
            f"Total Refusals: {stats.total_refusals}",
            f"Refusal Rate: {stats.refusal_rate:.2%}",
            "",
            "## Refusals by Type",
        ]

        for rtype, count in sorted(stats.by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  - {rtype}: {count} ({count/stats.total_refusals:.1%})")

        lines.extend(["", "## Refusals by Model"])
        for model, counts in sorted(stats.by_model.items()):
            total = counts.get("total", 0)
            lines.append(f"  {model}: {total} refusals")

        lines.extend(["", "## Refusals by Sensitive Topic"])
        for topic, counts in sorted(stats.by_sensitive_topic.items(), key=lambda x: -x[1].get("total", 0)):
            total = counts.get("total", 0)
            lines.append(f"  {topic}: {total} refusals")

        return "\n".join(lines)
```

---

## 13. FAILURE SUMMARY REPORT

```python
# src/reports/failure_summary.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import json

@dataclass
class FailureEntry:
    """A single failure event."""
    timestamp: datetime
    failure_type: str  # api_error, timeout, rate_limit, parse_error, etc.
    model: str
    prompt_id: str
    error_message: str
    retry_count: int
    recovered: bool
    context: Dict

@dataclass
class FailureSummary:
    """Summary of all failures in an evaluation run."""
    total_failures: int
    recovered_failures: int
    unrecovered_failures: int
    by_type: Dict[str, int]
    by_model: Dict[str, int]
    by_phase: Dict[str, int]  # generation, judging
    rate_limit_pauses: int
    total_retry_attempts: int
    failure_rate: float  # failures / total_api_calls
    unrecovered_prompts: List[str]

class FailureLogger:
    """Log and track failures during evaluation."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.failures: List[FailureEntry] = []
        self.total_api_calls = 0

    def log_failure(
        self,
        failure_type: str,
        model: str,
        prompt_id: str,
        error_message: str,
        retry_count: int = 0,
        recovered: bool = False,
        context: Dict = None
    ):
        """Log a failure event."""
        entry = FailureEntry(
            timestamp=datetime.now(),
            failure_type=failure_type,
            model=model,
            prompt_id=prompt_id,
            error_message=error_message,
            retry_count=retry_count,
            recovered=recovered,
            context=context or {}
        )
        self.failures.append(entry)

        # Append to log file
        with open(self.log_path, "a") as f:
            f.write(json.dumps({
                "timestamp": entry.timestamp.isoformat(),
                "failure_type": entry.failure_type,
                "model": entry.model,
                "prompt_id": entry.prompt_id,
                "error_message": entry.error_message,
                "retry_count": entry.retry_count,
                "recovered": entry.recovered,
                "context": entry.context
            }) + "\n")

    def record_api_call(self):
        """Record that an API call was made."""
        self.total_api_calls += 1

    def get_summary(self) -> FailureSummary:
        """Generate failure summary."""
        by_type = {}
        by_model = {}
        by_phase = {"generation": 0, "judging": 0}
        rate_limit_pauses = 0
        total_retries = 0
        unrecovered = []

        for f in self.failures:
            # By type
            by_type[f.failure_type] = by_type.get(f.failure_type, 0) + 1

            # By model
            by_model[f.model] = by_model.get(f.model, 0) + 1

            # By phase (infer from context)
            phase = f.context.get("phase", "generation")
            by_phase[phase] = by_phase.get(phase, 0) + 1

            # Rate limits
            if f.failure_type == "rate_limit":
                rate_limit_pauses += 1

            # Retries
            total_retries += f.retry_count

            # Unrecovered
            if not f.recovered:
                unrecovered.append(f.prompt_id)

        return FailureSummary(
            total_failures=len(self.failures),
            recovered_failures=sum(1 for f in self.failures if f.recovered),
            unrecovered_failures=sum(1 for f in self.failures if not f.recovered),
            by_type=by_type,
            by_model=by_model,
            by_phase=by_phase,
            rate_limit_pauses=rate_limit_pauses,
            total_retry_attempts=total_retries,
            failure_rate=len(self.failures) / self.total_api_calls if self.total_api_calls > 0 else 0,
            unrecovered_prompts=list(set(unrecovered))
        )

    def generate_report(self) -> str:
        """Generate formatted failure report."""
        summary = self.get_summary()

        report = f"""
================================================================================
                         FAILURE SUMMARY REPORT
================================================================================

OVERVIEW
--------
Total API Calls:        {self.total_api_calls:,}
Total Failures:         {summary.total_failures:,}
Failure Rate:           {summary.failure_rate:.2%}
Recovered:              {summary.recovered_failures:,}
Unrecovered:            {summary.unrecovered_failures:,}
Rate Limit Pauses:      {summary.rate_limit_pauses:,}
Total Retry Attempts:   {summary.total_retry_attempts:,}

FAILURES BY TYPE
----------------"""

        for ftype, count in sorted(summary.by_type.items(), key=lambda x: -x[1]):
            report += f"\n  {ftype:25} {count:5} ({count/summary.total_failures:.1%})"

        report += """

FAILURES BY MODEL
-----------------"""

        for model, count in sorted(summary.by_model.items(), key=lambda x: -x[1]):
            model_short = model.split("/")[-1]
            report += f"\n  {model_short:25} {count:5}"

        report += """

FAILURES BY PHASE
-----------------"""

        for phase, count in sorted(summary.by_phase.items(), key=lambda x: -x[1]):
            report += f"\n  {phase:25} {count:5}"

        if summary.unrecovered_prompts:
            report += f"""

UNRECOVERED PROMPTS ({len(summary.unrecovered_prompts)})
--------------------"""
            for prompt_id in summary.unrecovered_prompts[:20]:
                report += f"\n  - {prompt_id}"
            if len(summary.unrecovered_prompts) > 20:
                report += f"\n  ... and {len(summary.unrecovered_prompts) - 20} more"

        report += """

================================================================================
"""
        return report

    def save_report(self, output_path: Path):
        """Save failure report to file."""
        report = self.generate_report()
        with open(output_path, "w") as f:
            f.write(report)

    @classmethod
    def load_from_log(cls, log_path: Path) -> "FailureLogger":
        """Load failures from existing log file."""
        logger = cls(log_path)

        if log_path.exists():
            with open(log_path) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        logger.failures.append(FailureEntry(
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            failure_type=data["failure_type"],
                            model=data["model"],
                            prompt_id=data["prompt_id"],
                            error_message=data["error_message"],
                            retry_count=data["retry_count"],
                            recovered=data["recovered"],
                            context=data.get("context", {})
                        ))

        return logger
```

---

## 14. UPDATED JUDGECONFIG WITH PERSONA SELECTION

```python
# src/config/settings.py (updated JudgeConfig)

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Literal
from enum import Enum

class JudgePersonaMode(str, Enum):
    """Which judge personas to use."""
    BOTH = "both"           # Use both writing expert and recipient personas
    EXPERT_ONLY = "expert"  # Only use writing expert persona
    RECIPIENT_ONLY = "recipient"  # Only use recipient persona

@dataclass
class JudgeConfig:
    """Configuration for judge models."""
    models: List[str]
    votes_per_judge: int
    persona_mode: JudgePersonaMode = JudgePersonaMode.BOTH

    @property
    def use_both_personas(self) -> bool:
        """Backward compatibility."""
        return self.persona_mode == JudgePersonaMode.BOTH

    @property
    def personas(self) -> List[str]:
        """Get list of personas to use."""
        if self.persona_mode == JudgePersonaMode.BOTH:
            return ["writing_expert", "recipient"]
        elif self.persona_mode == JudgePersonaMode.EXPERT_ONLY:
            return ["writing_expert"]
        else:
            return ["recipient"]

@dataclass
class EvalConfig:
    """Complete evaluation configuration."""
    preset_level: int
    run_name: str
    num_prompts: int
    model_pairs: List[Tuple[str, str]]
    judge_config: JudgeConfig
    random_seed: Optional[int] = None
    stratify_by_job_zone: bool = True
    stratify_by_soc_group: bool = True
    phase3_enrich_ratio: float = 0.3
    constraint_probability: float = 0.15
    revision_probability: float = 0.10
    ambiguity_probability: float = 0.05

    # Sampling limits (added for CLI options)
    occupation_limit: Optional[int] = None
    industry_limit: Optional[int] = None

    # Filter ranges (added for CLI options)
    formality_range: Optional[Tuple[int, int]] = None
    age_range: Optional[Tuple[int, int]] = None
    job_zones: Optional[List[int]] = None
```

---

## Summary

This document provides complete Python implementations for all gaps identified in the gap analysis:

1. **Parallel Request Architecture** - EvaluationEngine with asyncio.gather, Semaphore for concurrency, per-model rate limiting
2. **Cohen's Kappa** - Full implementation with Fleiss' Kappa for multiple judges
3. **Cost Tracking in TUI** - CostTracker widget with spent/projected/budget
4. **Help Overlay** - HelpOverlay modal screen with keyboard shortcuts
5. **CLI Options** - Full --tier, --job-zones, --formality-range, --age-range, --occupation-limit, --industry-limit, --persona
6. **ETA Calculation** - ETADisplay widget with formatted durations
7. **Confidence Intervals in TUI** - WinRateWithCI widget with Wilson CI
8. **Occupation/Industry in Batch Display** - CurrentBatchStatus widget enhancement
9. **Per-Judge Vote Display** - JudgeVotesDisplay widget
10. **Name Formality Variation** - NameGenerator with formal/informal name formatting
11. **Phase 1 Generation Using Evaluated Models** - Phase1Generator rotating through all models
12. **Ambiguity Behavior Tracking** - AmbiguityTracker classifying response behaviors
13. **TUI Results Viewer** - Full ResultsViewer with filtering, sorting, drill-down
14. **Refusal Tracking by Dimension** - RefusalClassifier with stats by model/task/topic
15. **Failure Summary Report** - FailureLogger with formatted report generation
16. **Updated JudgeConfig** - JudgePersonaMode enum for persona selection