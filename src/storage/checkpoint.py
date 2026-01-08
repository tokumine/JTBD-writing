"""Checkpoint system for resumable evaluations."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from src.eval.schemas import EvalState


class CheckpointManager:
    """Manage evaluation checkpoints for resumability."""

    CHECKPOINT_FILE = "checkpoint.json"

    def __init__(self, run_dir: Path):
        """
        Initialize checkpoint manager.

        Args:
            run_dir: Directory for this evaluation run
        """
        self.run_dir = run_dir
        self.checkpoint_path = run_dir / self.CHECKPOINT_FILE

    async def save(self, state: EvalState) -> None:
        """
        Save checkpoint state.

        Args:
            state: Current evaluation state
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Convert sets to lists for JSON serialization
        state_dict = state.model_dump()
        state_dict["completed_prompt_ids"] = list(state.completed_prompt_ids)
        state_dict["pending_prompt_ids"] = list(state.pending_prompt_ids)
        state_dict["failed_prompt_ids"] = list(state.failed_prompt_ids)
        state_dict["last_checkpoint"] = datetime.now().isoformat()

        # Convert datetime to ISO format
        if state.started_at:
            state_dict["started_at"] = state.started_at.isoformat()

        async with aiofiles.open(self.checkpoint_path, "w") as f:
            await f.write(json.dumps(state_dict, indent=2))

    async def load(self) -> EvalState | None:
        """
        Load checkpoint state.

        Returns:
            EvalState if checkpoint exists, None otherwise
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            async with aiofiles.open(self.checkpoint_path) as f:
                content = await f.read()
                data = json.loads(content)

            # Convert lists back to sets
            data["completed_prompt_ids"] = set(data.get("completed_prompt_ids", []))
            data["pending_prompt_ids"] = set(data.get("pending_prompt_ids", []))
            data["failed_prompt_ids"] = set(data.get("failed_prompt_ids", []))

            # Convert ISO strings back to datetime
            if data.get("started_at"):
                data["started_at"] = datetime.fromisoformat(data["started_at"])
            if data.get("last_checkpoint"):
                data["last_checkpoint"] = datetime.fromisoformat(data["last_checkpoint"])

            return EvalState(**data)

        except Exception as e:
            # Log error but return None to allow fresh start
            print(f"Warning: Failed to load checkpoint: {e}")
            return None

    async def exists(self) -> bool:
        """Check if checkpoint exists."""
        return self.checkpoint_path.exists()

    async def delete(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()


class RunManager:
    """Manage evaluation run directories."""

    def __init__(self, results_dir: Path):
        """
        Initialize run manager.

        Args:
            results_dir: Base directory for all runs
        """
        self.results_dir = results_dir

    def create_run_dir(self, run_id: str | None = None) -> Path:
        """
        Create a new run directory.

        Args:
            run_id: Optional run ID, generates timestamp-based if None

        Returns:
            Path to the run directory
        """
        if run_id is None:
            run_id = datetime.now().strftime("eval_%Y-%m-%d_%H-%M-%S")

        run_dir = self.results_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (run_dir / "responses").mkdir(exist_ok=True)
        (run_dir / "judgments").mkdir(exist_ok=True)
        (run_dir / "analysis").mkdir(exist_ok=True)
        (run_dir / "reports").mkdir(exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)

        # Update latest symlink
        latest = self.results_dir / "latest"
        if latest.is_symlink():
            latest.unlink()
        elif latest.exists():
            latest.unlink()
        latest.symlink_to(run_dir.name)

        return run_dir

    def list_runs(self) -> list[dict[str, Any]]:
        """
        List all evaluation runs.

        Returns:
            List of run info dictionaries
        """
        runs = []

        if not self.results_dir.exists():
            return runs

        for entry in self.results_dir.iterdir():
            if entry.is_dir() and entry.name.startswith("eval_"):
                checkpoint_path = entry / "checkpoint.json"
                run_info: dict[str, Any] = {
                    "run_id": entry.name,
                    "path": str(entry),
                    "has_checkpoint": checkpoint_path.exists(),
                }

                if checkpoint_path.exists():
                    try:
                        with open(checkpoint_path) as f:
                            checkpoint = json.load(f)
                        run_info["phase"] = checkpoint.get("phase")
                        run_info["completed_count"] = checkpoint.get("completed_count", 0)
                        run_info["total_prompts"] = checkpoint.get("total_prompts", 0)
                    except Exception:
                        pass

                runs.append(run_info)

        # Sort by name (which includes timestamp)
        runs.sort(key=lambda x: x["run_id"], reverse=True)
        return runs

    def get_latest_run(self) -> Path | None:
        """
        Get the latest run directory.

        Returns:
            Path to latest run, or None if no runs exist
        """
        latest = self.results_dir / "latest"
        if latest.is_symlink():
            return latest.resolve()
        return None
