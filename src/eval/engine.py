"""Evaluation engine orchestrating the full pipeline."""
import asyncio
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.api.openrouter_client import OpenRouterClient
from src.config import get_settings
from src.config.presets import MODEL_ALIASES, EvalPreset
from src.data.onet_extractor import ONetExtractor
from src.eval.judge_parser import JudgeParser
from src.eval.schemas import EvalState, ModelResponse, JudgmentResult, ShuffledJudgment, AggregatedResult
from src.eval.vote_aggregator import VoteAggregator
from src.prompts.schemas import ONetTask
from src.storage.checkpoint import CheckpointManager
from src.storage.database import EvalDatabase


console = Console()


class EvaluationEngine:
    """Orchestrates the full evaluation pipeline."""

    JUDGE_SYSTEM_PROMPT = """You are an expert evaluator of professional writing quality.
You will be shown two responses (A and B) to the same writing task.
Evaluate which response better accomplishes the task.

Consider:
- Appropriateness for the professional context
- Clarity and organization
- Tone and professionalism
- Completeness and relevance

Respond with JSON:
{
    "winner": "A" or "B" or "TIE",
    "confidence": "high" or "medium" or "low",
    "reasoning": "brief explanation",
    "scores": {
        "appropriateness": {"A": 1-5, "B": 1-5},
        "clarity": {"A": 1-5, "B": 1-5},
        "tone": {"A": 1-5, "B": 1-5}
    }
}"""

    def __init__(
        self,
        preset: EvalPreset,
        output_dir: Path | None = None,
        prompt_count_override: int | None = None,
    ):
        """Initialize evaluation engine."""
        self.settings = get_settings()
        self.preset = preset
        self.prompt_count = prompt_count_override or preset.prompt_count
        self.output_dir = output_dir or self.settings.results_dir

        self.run_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.run_dir = self.output_dir / self.run_id

        self.client: OpenRouterClient | None = None
        self.db: EvalDatabase | None = None
        self.checkpoint_manager: CheckpointManager | None = None
        self.judge_parser = JudgeParser()
        self.vote_aggregator = VoteAggregator()

        self.state: EvalState | None = None
        self.total_cost = 0.0

    async def __aenter__(self) -> "EvaluationEngine":
        """Enter async context."""
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.client = OpenRouterClient(
            self.settings.openrouter_api_key,
            timeout=self.settings.request_timeout,
            max_retries=self.settings.max_retries,
        )
        await self.client.__aenter__()

        self.db = EvalDatabase(self.run_dir / "eval.db")
        await self.db.connect()

        self.checkpoint_manager = CheckpointManager(self.run_dir)

        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        if self.client:
            await self.client.__aexit__(*args)
        if self.db:
            await self.db.close()

    async def run(self) -> dict[str, Any]:
        """Run the full evaluation pipeline."""
        console.print(f"\n[bold blue]Starting evaluation run: {self.run_id}[/bold blue]")
        console.print(f"Output directory: {self.run_dir}")

        # Initialize state
        self.state = EvalState(
            run_id=self.run_id,
            phase="prompt_generation",
            total_prompts=self.prompt_count,
            started_at=datetime.now(),
        )

        try:
            # Phase 1: Extract writing tasks
            tasks = await self._extract_tasks()
            if not tasks:
                console.print("[red]No writing tasks found in O*NET database[/red]")
                return {"status": "error", "reason": "no_tasks"}

            # Phase 2: Generate responses from each model
            self.state.phase = "response_collection"
            responses = await self._collect_responses(tasks)

            # Phase 3: Run judge evaluations
            self.state.phase = "judging"
            judgments = await self._run_judging(tasks, responses)

            # Phase 4: Aggregate results
            self.state.phase = "analysis"
            results = self._aggregate_results(judgments)

            # Phase 5: Save final results
            self.state.phase = "complete"
            await self._save_checkpoint()
            self._save_results(results)

            # Print summary
            self._print_summary(results)

            return {
                "status": "complete",
                "run_id": self.run_id,
                "total_prompts": len(tasks),
                "total_cost": self.total_cost,
                "results": results,
            }

        except Exception as e:
            console.print(f"[red]Evaluation failed: {e}[/red]")
            await self._save_checkpoint()
            raise

    async def _extract_tasks(self) -> list[ONetTask]:
        """Extract writing tasks from O*NET."""
        console.print("\n[bold]Phase 1: Extracting writing tasks[/bold]")

        extractor = ONetExtractor(self.settings.onet_db_path)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Extracting tasks...", total=None)
            tasks = await extractor.extract_writing_tasks(
                min_relevance=0.5,
                limit=self.prompt_count,
            )

        console.print(f"  Extracted {len(tasks)} writing tasks")

        # Shuffle for variety
        random.shuffle(tasks)
        return tasks[:self.prompt_count]

    async def _collect_responses(
        self, tasks: list[ONetTask]
    ) -> dict[str, dict[str, ModelResponse]]:
        """Collect responses from all models for all tasks (parallel)."""
        console.print("\n[bold]Phase 2: Collecting model responses[/bold]")

        model_ids = [MODEL_ALIASES.get(m, m) for m in self.preset.models]
        responses: dict[str, dict[str, ModelResponse]] = {t.task_id: {} for t in tasks}

        # Semaphore to limit concurrent requests (10 per model effectively)
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)

        async def fetch_response(
            task: ONetTask, model_alias: str, model_id: str
        ) -> tuple[str, str, ModelResponse]:
            """Fetch a single response with semaphore."""
            async with semaphore:
                prompt = self._format_task_prompt(task)
                try:
                    result = await self.client.generate(
                        model_id=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=2048,
                    )

                    response = ModelResponse(
                        prompt_id=task.task_id,
                        model_id=model_alias,
                        response_text=result.content,
                        status="success",
                        latency_ms=result.latency_ms,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        total_tokens=result.total_tokens,
                    )

                    # Thread-safe cost accumulation
                    self.total_cost += (result.input_tokens * 0.00001 + result.output_tokens * 0.00003)

                except Exception as e:
                    response = ModelResponse(
                        prompt_id=task.task_id,
                        model_id=model_alias,
                        error=str(e),
                        status="error",
                        latency_ms=0,
                    )

                return task.task_id, model_alias, response

        # Build all tasks
        all_tasks = [
            fetch_response(task, model_alias, model_id)
            for task in tasks
            for model_alias, model_id in zip(self.preset.models, model_ids)
        ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_progress = progress.add_task(
                "Collecting responses...",
                total=len(all_tasks),
            )

            # Run all requests in parallel with semaphore limiting concurrency
            for coro in asyncio.as_completed(all_tasks):
                task_id, model_alias, response = await coro
                responses[task_id][model_alias] = response
                progress.update(task_progress, advance=1)

        success_count = sum(
            1 for task_responses in responses.values()
            for r in task_responses.values()
            if r.status == "success"
        )
        console.print(f"  Collected {success_count} successful responses")

        return responses

    async def _run_judging(
        self,
        tasks: list[ONetTask],
        responses: dict[str, dict[str, ModelResponse]],
    ) -> dict[str, list[ShuffledJudgment]]:
        """Run judge evaluations on all model pairs (parallel)."""
        console.print("\n[bold]Phase 3: Running judge evaluations[/bold]")

        judge_ids = [MODEL_ALIASES.get(j, j) for j in self.preset.judge_models]
        judgments: dict[str, list[ShuffledJudgment]] = {t.task_id: [] for t in tasks}

        # Semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)

        # Generate all model pairs
        model_pairs = []
        models = list(self.preset.models)
        for i, model_a in enumerate(models):
            for model_b in models[i + 1:]:
                model_pairs.append((model_a, model_b))

        async def fetch_judgment(
            task: ONetTask,
            judge_id: str,
            judge_alias: str,
            persona: str,
            response_a: str,
            response_b: str,
            model_a: str,
            model_b: str,
            position_order: str,
        ) -> tuple[str, ShuffledJudgment]:
            """Fetch a single judgment with semaphore."""
            async with semaphore:
                judgment = await self._get_judgment(
                    judge_id=judge_id,
                    judge_alias=judge_alias,
                    persona=persona,
                    task=task,
                    response_a=response_a,
                    response_b=response_b,
                    model_a=model_a,
                    model_b=model_b,
                    position_order=position_order,
                )
                return task.task_id, judgment

        # Build all judgment tasks
        all_judgment_tasks = []
        for task in tasks:
            task_responses = responses.get(task.task_id, {})

            for model_a, model_b in model_pairs:
                resp_a = task_responses.get(model_a)
                resp_b = task_responses.get(model_b)

                if not resp_a or not resp_b or resp_a.status != "success" or resp_b.status != "success":
                    continue

                for judge_alias, judge_id in zip(self.preset.judge_models, judge_ids):
                    for persona in self.preset.judge_personas:
                        for vote_idx in range(self.preset.votes_per_judge):
                            # Original order (A=model_a, B=model_b)
                            all_judgment_tasks.append(
                                fetch_judgment(
                                    task, judge_id, judge_alias, persona,
                                    resp_a.response_text, resp_b.response_text,
                                    model_a, model_b, "AB"
                                )
                            )

                            # Shuffled order if enabled
                            if self.preset.position_shuffle:
                                all_judgment_tasks.append(
                                    fetch_judgment(
                                        task, judge_id, judge_alias, persona,
                                        resp_b.response_text, resp_a.response_text,
                                        model_b, model_a, "BA"
                                    )
                                )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_progress = progress.add_task(
                "Running judgments...",
                total=len(all_judgment_tasks),
            )

            # Run all judgments in parallel with semaphore limiting concurrency
            for coro in asyncio.as_completed(all_judgment_tasks):
                task_id, judgment = await coro
                judgments[task_id].append(judgment)
                progress.update(task_progress, advance=1)

        total_collected = sum(len(j) for j in judgments.values())
        console.print(f"  Collected {total_collected} judgments")

        return judgments

    async def _get_judgment(
        self,
        judge_id: str,
        judge_alias: str,
        persona: str,
        task: ONetTask,
        response_a: str,
        response_b: str,
        model_a: str,
        model_b: str,
        position_order: str,
    ) -> ShuffledJudgment:
        """Get a single judgment from a judge model."""
        judge_prompt = f"""Task: {task.task}
Occupation: {task.occupation_title}

Response A:
{response_a}

Response B:
{response_b}

Which response is better for this professional writing task?"""

        try:
            result = await self.client.generate(
                model_id=judge_id,
                messages=[{"role": "user", "content": judge_prompt}],
                system_prompt=self.JUDGE_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1024,
            )

            judgment = self.judge_parser.parse(result.content)
            self.total_cost += (result.input_tokens * 0.00001 + result.output_tokens * 0.00003)

        except Exception as e:
            judgment = JudgmentResult(
                winner="PARSE_ERROR",
                reasoning=str(e),
                parse_success=False,
            )

        return ShuffledJudgment(
            judge_model=judge_alias,
            persona_type=persona,
            position_order=position_order,
            position_a_model=model_a,
            position_b_model=model_b,
            judgment=judgment,
        )

    def _aggregate_results(
        self, judgments: dict[str, list[ShuffledJudgment]]
    ) -> dict[str, Any]:
        """Aggregate judgment results into final statistics."""
        console.print("\n[bold]Phase 4: Aggregating results[/bold]")

        # Count wins by model pair
        pair_results: dict[tuple[str, str], dict[str, int]] = {}

        for task_id, task_judgments in judgments.items():
            for j in task_judgments:
                if j.judgment.winner == "PARSE_ERROR":
                    continue

                # Normalize to consistent model order
                model_pair = tuple(sorted([j.position_a_model, j.position_b_model]))
                if model_pair not in pair_results:
                    pair_results[model_pair] = {"model_a": 0, "model_b": 0, "tie": 0}

                # Map winner back to actual model
                if j.judgment.winner == "A":
                    winner_model = j.position_a_model
                elif j.judgment.winner == "B":
                    winner_model = j.position_b_model
                else:
                    pair_results[model_pair]["tie"] += 1
                    continue

                if winner_model == model_pair[0]:
                    pair_results[model_pair]["model_a"] += 1
                else:
                    pair_results[model_pair]["model_b"] += 1

        # Calculate win rates
        results = {
            "model_pairs": {},
            "overall_rankings": {},
        }

        model_wins: dict[str, int] = {}
        model_total: dict[str, int] = {}

        for (model_a, model_b), counts in pair_results.items():
            total = counts["model_a"] + counts["model_b"] + counts["tie"]
            if total == 0:
                continue

            results["model_pairs"][f"{model_a}_vs_{model_b}"] = {
                f"{model_a}_wins": counts["model_a"],
                f"{model_b}_wins": counts["model_b"],
                "ties": counts["tie"],
                f"{model_a}_win_rate": counts["model_a"] / total if total > 0 else 0,
                f"{model_b}_win_rate": counts["model_b"] / total if total > 0 else 0,
            }

            # Accumulate for overall ranking
            model_wins[model_a] = model_wins.get(model_a, 0) + counts["model_a"]
            model_wins[model_b] = model_wins.get(model_b, 0) + counts["model_b"]
            model_total[model_a] = model_total.get(model_a, 0) + total
            model_total[model_b] = model_total.get(model_b, 0) + total

        # Overall rankings
        for model in model_wins:
            win_rate = model_wins[model] / model_total[model] if model_total[model] > 0 else 0
            results["overall_rankings"][model] = {
                "wins": model_wins[model],
                "total": model_total[model],
                "win_rate": win_rate,
            }

        return results

    def _format_task_prompt(self, task: ONetTask) -> str:
        """Format a task into a prompt for the model."""
        return f"""You are a {task.occupation_title}.

Task: {task.task}

Write a professional response appropriate for this workplace task. Be concise but complete."""

    async def _save_checkpoint(self) -> None:
        """Save current state to checkpoint."""
        if self.checkpoint_manager and self.state:
            self.state.last_checkpoint = datetime.now()
            self.state.total_cost_usd = self.total_cost
            await self.checkpoint_manager.save(self.state)

    def _save_results(self, results: dict[str, Any]) -> None:
        """Save results to JSON file."""
        import json

        results_file = self.run_dir / "results.json"
        results_data = {
            "run_id": self.run_id,
            "preset": self.preset.name,
            "total_prompts": self.prompt_count,
            "total_cost_usd": self.total_cost,
            **results,
        }
        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

    def _print_summary(self, results: dict[str, Any]) -> None:
        """Print evaluation summary."""
        console.print("\n" + "=" * 60)
        console.print("[bold green]Evaluation Complete![/bold green]")
        console.print("=" * 60)

        console.print(f"\nRun ID: {self.run_id}")
        console.print(f"Total cost: ${self.total_cost:.2f}")

        if results.get("overall_rankings"):
            console.print("\n[bold]Overall Rankings:[/bold]")
            rankings = sorted(
                results["overall_rankings"].items(),
                key=lambda x: x[1]["win_rate"],
                reverse=True,
            )
            for i, (model, stats) in enumerate(rankings, 1):
                console.print(
                    f"  {i}. {model}: {stats['win_rate']:.1%} "
                    f"({stats['wins']}/{stats['total']} wins)"
                )

        console.print(f"\nResults saved to: {self.run_dir}")


async def run_evaluation(
    preset: EvalPreset,
    output_dir: Path | None = None,
    prompt_count: int | None = None,
) -> dict[str, Any]:
    """Run evaluation with given preset."""
    async with EvaluationEngine(preset, output_dir, prompt_count) as engine:
        return await engine.run()
