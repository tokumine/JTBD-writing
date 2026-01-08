"""Command-line interface for Gemini Writing Evaluation."""
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.config import CostEstimator, get_preset, list_presets
from src.config.presets import MODEL_ALIASES, PresetName

app = typer.Typer(
    name="gemini-eval",
    help="Gemini Writing Evaluation Framework",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    preset: PresetName = typer.Option(
        "smoke",
        "--preset",
        "-p",
        help="Evaluation preset to use",
    ),
    prompts: Optional[int] = typer.Option(
        None,
        "--prompts",
        "-n",
        help="Override number of prompts (overrides preset)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: results/)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be run without executing",
    ),
) -> None:
    """Run an evaluation with the specified preset."""
    preset_config = get_preset(preset)

    if dry_run:
        console.print(f"\n[bold]Would run evaluation with preset: {preset}[/bold]")
        console.print(f"  Prompts: {prompts or preset_config.prompt_count}")
        console.print(f"  Models: {', '.join(preset_config.models)}")
        console.print(f"  Judges: {', '.join(preset_config.judge_models)}")
        console.print(f"  Estimated cost: ${preset_config.estimated_cost_usd:.2f}")
        return

    import asyncio

    from src.eval.engine import run_evaluation

    console.print(f"\n[bold green]Starting evaluation: {preset}[/bold green]")
    console.print(f"Prompts: {prompts or preset_config.prompt_count}")
    console.print(f"Models: {', '.join(preset_config.models)}")

    try:
        result = asyncio.run(
            run_evaluation(
                preset=preset_config,
                output_dir=output_dir,
                prompt_count=prompts,
            )
        )
        if result.get("status") == "complete":
            console.print("\n[bold green]Evaluation completed successfully![/bold green]")
        else:
            console.print(f"\n[yellow]Evaluation ended: {result.get('status')}[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Evaluation interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Evaluation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def estimate(
    preset: PresetName = typer.Option(
        "standard",
        "--preset",
        "-p",
        help="Preset to estimate cost for",
    ),
    prompts: Optional[int] = typer.Option(
        None,
        "--prompts",
        "-n",
        help="Override number of prompts",
    ),
) -> None:
    """Estimate cost for an evaluation run."""
    preset_config = get_preset(preset)
    estimator = CostEstimator()

    prompt_count = prompts or preset_config.prompt_count

    estimate = estimator.estimate_full_eval(
        prompt_count=prompt_count,
        model_count=len(preset_config.models),
        judge_count=len(preset_config.judge_models),
        persona_count=len(preset_config.judge_personas),
        votes_per_judge=preset_config.votes_per_judge,
        position_shuffle=preset_config.position_shuffle,
    )

    console.print(f"\n[bold]Cost Estimate for preset: {preset}[/bold]")
    console.print(f"Prompts: {prompt_count}")
    console.print()
    console.print(str(estimate))
    console.print()
    console.print(f"[dim]Estimated runtime: ~{preset_config.estimated_runtime_hours:.1f} hours[/dim]")


@app.command()
def presets() -> None:
    """List all available presets."""
    table = Table(title="Available Evaluation Presets")

    table.add_column("Name", style="cyan")
    table.add_column("Prompts", justify="right")
    table.add_column("Models", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Runtime", justify="right")
    table.add_column("Description")

    for preset in list_presets():
        table.add_row(
            preset.name,
            str(preset.prompt_count),
            str(len(preset.models)),
            f"~${preset.estimated_cost_usd:,.0f}",
            f"~{preset.estimated_runtime_hours:.1f}h",
            preset.description,
        )

    console.print(table)


@app.command()
def models() -> None:
    """List available model aliases."""
    table = Table(title="Model Aliases")

    table.add_column("Alias", style="cyan")
    table.add_column("OpenRouter Model ID")
    table.add_column("Tier")

    pro_models = ["gemini_pro", "gpt_pro", "claude_pro", "grok", "kimi"]
    flash_models = ["gemini_flash", "gpt_flash", "claude_flash"]
    judge_models = ["judge_claude", "judge_gpt", "judge_gemini"]

    for alias in pro_models:
        if alias in MODEL_ALIASES:
            table.add_row(alias, MODEL_ALIASES[alias], "Pro")

    for alias in flash_models:
        if alias in MODEL_ALIASES:
            table.add_row(alias, MODEL_ALIASES[alias], "Flash")

    for alias in judge_models:
        if alias in MODEL_ALIASES:
            table.add_row(alias, MODEL_ALIASES[alias], "Judge")

    console.print(table)


@app.command()
def validate(
    check_api: bool = typer.Option(
        True,
        "--check-api/--no-check-api",
        help="Check API key validity",
    ),
    check_db: bool = typer.Option(
        True,
        "--check-db/--no-check-db",
        help="Check O*NET database",
    ),
) -> None:
    """Validate configuration and dependencies."""
    import asyncio

    from src.config import get_settings

    console.print("\n[bold]Validating configuration...[/bold]\n")

    errors: list[str] = []
    warnings: list[str] = []

    # Check settings
    try:
        settings = get_settings()
        console.print("[green]✓[/green] Settings loaded successfully")

        if settings.openrouter_api_key.startswith("sk-test"):
            warnings.append("API key appears to be a test key")

    except Exception as e:
        errors.append(f"Settings error: {e}")
        console.print(f"[red]✗[/red] Settings: {e}")
        return

    # Check O*NET database
    if check_db:
        if settings.onet_db_path.exists():
            console.print(f"[green]✓[/green] O*NET database found: {settings.onet_db_path}")

            # Validate schema
            from src.validation.onet_schema import ONetSchemaValidator

            async def check_schema() -> None:
                validator = ONetSchemaValidator()
                result = await validator.validate(settings.onet_db_path)
                if result.is_valid:
                    console.print("[green]✓[/green] Database schema valid")
                else:
                    for err in result.errors:
                        errors.append(err)
                        console.print(f"[red]✗[/red] Schema: {err}")
                for warn in result.warnings:
                    warnings.append(warn)

            asyncio.run(check_schema())
        else:
            errors.append(f"O*NET database not found: {settings.onet_db_path}")
            console.print(f"[red]✗[/red] O*NET database not found: {settings.onet_db_path}")

    # Check API
    if check_api:
        console.print("[dim]API validation skipped (would require actual API call)[/dim]")

    # Summary
    console.print()
    if errors:
        console.print(f"[bold red]Validation failed with {len(errors)} error(s)[/bold red]")
        for err in errors:
            console.print(f"  [red]•[/red] {err}")
    elif warnings:
        console.print(f"[bold yellow]Validation passed with {len(warnings)} warning(s)[/bold yellow]")
        for warn in warnings:
            console.print(f"  [yellow]•[/yellow] {warn}")
    else:
        console.print("[bold green]All validations passed![/bold green]")


@app.command()
def resume(
    run_dir: Path = typer.Argument(
        ...,
        help="Path to run directory to resume",
    ),
) -> None:
    """Resume an interrupted evaluation."""
    from src.storage.checkpoint import CheckpointManager

    import asyncio

    if not run_dir.exists():
        console.print(f"[red]Run directory not found: {run_dir}[/red]")
        raise typer.Exit(1)

    manager = CheckpointManager(run_dir)

    async def load_checkpoint():
        return await manager.load()

    checkpoint = asyncio.run(load_checkpoint())

    if not checkpoint:
        console.print(f"[red]No checkpoint found in: {run_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Found checkpoint for run: {checkpoint.run_id}[/bold]")
    console.print(f"  Phase: {checkpoint.phase}")
    console.print(f"  Progress: {checkpoint.completed_count}/{checkpoint.total_prompts}")
    console.print(f"  Cost so far: ${checkpoint.total_cost_usd:.2f}")

    # TODO: Implement actual resume
    console.print("\n[yellow]Resume not yet implemented[/yellow]")


@app.command("list")
def list_runs() -> None:
    """List all evaluation runs."""
    from src.config import get_settings
    from src.storage.checkpoint import RunManager

    settings = get_settings()
    manager = RunManager(settings.results_dir)

    runs = manager.list_runs()

    if not runs:
        console.print("[dim]No evaluation runs found[/dim]")
        return

    table = Table(title="Evaluation Runs")

    table.add_column("Run ID", style="cyan")
    table.add_column("Phase")
    table.add_column("Progress", justify="right")
    table.add_column("Path")

    for run in runs:
        progress = ""
        if "completed_count" in run and "total_prompts" in run:
            progress = f"{run['completed_count']}/{run['total_prompts']}"

        table.add_row(
            run["run_id"],
            run.get("phase", "unknown"),
            progress,
            run["path"],
        )

    console.print(table)


@app.command()
def export(
    run_dir: Path = typer.Argument(
        ...,
        help="Run directory to export",
    ),
    output: Path = typer.Option(
        Path("export.csv"),
        "--output",
        "-o",
        help="Output file path",
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Export format (csv, json)",
    ),
) -> None:
    """Export evaluation results."""
    if not run_dir.exists():
        console.print(f"[red]Run directory not found: {run_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Exporting {run_dir} to {output} ({format})[/dim]")
    # TODO: Implement export
    console.print("[yellow]Export not yet implemented[/yellow]")


@app.command()
def report(
    run_dir: Path = typer.Argument(
        ...,
        help="Run directory to generate report for",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: <run_dir>/report.html or .pdf)",
    ),
    format: str = typer.Option(
        "auto",
        "--format",
        "-f",
        help="Report format: auto, html, or pdf (pdf requires system deps)",
    ),
) -> None:
    """Generate report for an evaluation run."""
    if not run_dir.exists():
        console.print(f"[red]Run directory not found: {run_dir}[/red]")
        raise typer.Exit(1)

    from src.reports.pdf_generator import generate_report

    console.print(f"\n[bold]Generating report for: {run_dir.name}[/bold]")

    try:
        output_path = generate_report(run_dir, output, format=format)
        console.print(f"\n[green]Report generated: {output_path}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to generate report: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
