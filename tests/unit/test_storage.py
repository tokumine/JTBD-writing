"""Tests for storage and checkpoint modules."""
from datetime import datetime
from pathlib import Path

import pytest

from src.eval.schemas import AggregatedResult, EvalState, ModelResponse
from src.storage.checkpoint import CheckpointManager, RunManager
from src.storage.database import EvalDatabase


class TestEvalDatabase:
    """Tests for database operations."""

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, temp_dir: Path) -> None:
        """Test connecting creates schema."""
        db_path = temp_dir / "test.db"
        async with EvalDatabase(db_path) as db:
            cursor = await db.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}

        assert "runs" in tables
        assert "prompts" in tables
        assert "responses" in tables
        assert "judgments" in tables
        assert "results" in tables

    @pytest.mark.asyncio
    async def test_create_and_get_run(self, temp_dir: Path) -> None:
        """Test creating and retrieving a run."""
        db_path = temp_dir / "test.db"
        async with EvalDatabase(db_path) as db:
            await db.create_run(
                run_id="test_run",
                preset_name="smoke",
                config={"prompts": 10},
                total_prompts=10,
            )

            run = await db.get_run("test_run")

        assert run is not None
        assert run["preset_name"] == "smoke"
        assert run["total_prompts"] == 10

    @pytest.mark.asyncio
    async def test_update_run_progress(self, temp_dir: Path) -> None:
        """Test updating run progress."""
        db_path = temp_dir / "test.db"
        async with EvalDatabase(db_path) as db:
            await db.create_run(
                run_id="test_run",
                preset_name="smoke",
                config={},
                total_prompts=10,
            )

            await db.update_run_progress("test_run", completed_prompts=5, total_cost_usd=2.50)

            run = await db.get_run("test_run")

        assert run["completed_prompts"] == 5
        assert run["total_cost_usd"] == 2.50

    @pytest.mark.asyncio
    async def test_save_response(self, temp_dir: Path) -> None:
        """Test saving model response."""
        db_path = temp_dir / "test.db"
        async with EvalDatabase(db_path) as db:
            response = ModelResponse(
                prompt_id="p1",
                model_id="openai/gpt-4",
                response_text="Hello world",
                status="success",
                latency_ms=1234.5,
                input_tokens=100,
                output_tokens=50,
            )
            await db.save_response(response)

            responses = await db.get_responses("p1")

        assert len(responses) == 1
        assert responses[0]["response_text"] == "Hello world"
        assert responses[0]["latency_ms"] == 1234.5

    @pytest.mark.asyncio
    async def test_save_result(self, temp_dir: Path) -> None:
        """Test saving aggregated result."""
        db_path = temp_dir / "test.db"
        async with EvalDatabase(db_path) as db:
            result = AggregatedResult(
                prompt_id="p1",
                model_a="gemini-pro",
                model_b="gpt-5.2",
                winner="gemini-pro",
                gemini_model_id="gemini-pro",
                gemini_was_a=True,
                votes_model_a=4,
                votes_model_b=2,
                votes_tie=0,
                inter_judge_agreement=0.75,
                position_consistency=0.83,
                margin=0.33,
                confidence="high",
            )
            await db.save_result(result)

            win_rates = await db.get_win_rates()

        key = "gemini-pro vs gpt-5.2"
        assert key in win_rates
        assert win_rates[key]["model_a_win_rate"] == 1.0


class TestCheckpointManager:
    """Tests for checkpoint management."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, temp_dir: Path) -> None:
        """Test saving and loading checkpoint."""
        manager = CheckpointManager(temp_dir)

        state = EvalState(
            run_id="test_run",
            phase="response_collection",
            total_prompts=100,
            completed_count=50,
            completed_prompt_ids={"p1", "p2", "p3"},
            pending_prompt_ids={"p4", "p5"},
            total_cost_usd=25.50,
            started_at=datetime.now(),
        )

        await manager.save(state)
        loaded = await manager.load()

        assert loaded is not None
        assert loaded.run_id == "test_run"
        assert loaded.phase == "response_collection"
        assert loaded.completed_count == 50
        assert loaded.completed_prompt_ids == {"p1", "p2", "p3"}
        assert abs(loaded.total_cost_usd - 25.50) < 0.001

    @pytest.mark.asyncio
    async def test_exists(self, temp_dir: Path) -> None:
        """Test checking if checkpoint exists."""
        manager = CheckpointManager(temp_dir)

        assert await manager.exists() is False

        state = EvalState(
            run_id="test",
            phase="judging",
            total_prompts=10,
        )
        await manager.save(state)

        assert await manager.exists() is True

    @pytest.mark.asyncio
    async def test_delete(self, temp_dir: Path) -> None:
        """Test deleting checkpoint."""
        manager = CheckpointManager(temp_dir)

        state = EvalState(
            run_id="test",
            phase="complete",
            total_prompts=10,
        )
        await manager.save(state)
        assert await manager.exists()

        await manager.delete()
        assert not await manager.exists()

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, temp_dir: Path) -> None:
        """Test loading nonexistent checkpoint."""
        manager = CheckpointManager(temp_dir / "nonexistent")
        loaded = await manager.load()

        assert loaded is None


class TestRunManager:
    """Tests for run directory management."""

    def test_create_run_dir(self, temp_dir: Path) -> None:
        """Test creating run directory."""
        manager = RunManager(temp_dir)
        run_dir = manager.create_run_dir("test_run")

        assert run_dir.exists()
        assert (run_dir / "responses").exists()
        assert (run_dir / "judgments").exists()
        assert (run_dir / "analysis").exists()
        assert (run_dir / "reports").exists()
        assert (run_dir / "logs").exists()

    def test_create_run_dir_with_timestamp(self, temp_dir: Path) -> None:
        """Test creating run directory with auto timestamp."""
        manager = RunManager(temp_dir)
        run_dir = manager.create_run_dir()

        assert run_dir.exists()
        assert run_dir.name.startswith("eval_")

    def test_latest_symlink(self, temp_dir: Path) -> None:
        """Test latest symlink is updated."""
        manager = RunManager(temp_dir)

        run1 = manager.create_run_dir("run1")
        latest = manager.get_latest_run()
        # Compare names instead of full paths (macOS symlink resolution differs)
        assert latest is not None
        assert latest.name == run1.name

        run2 = manager.create_run_dir("run2")
        latest = manager.get_latest_run()
        assert latest is not None
        assert latest.name == run2.name

    def test_list_runs(self, temp_dir: Path) -> None:
        """Test listing all runs."""
        manager = RunManager(temp_dir)

        manager.create_run_dir("eval_2024-01-01")
        manager.create_run_dir("eval_2024-01-02")

        runs = manager.list_runs()

        assert len(runs) == 2
        assert runs[0]["run_id"] == "eval_2024-01-02"  # More recent first

    def test_list_runs_empty(self, temp_dir: Path) -> None:
        """Test listing runs when none exist."""
        manager = RunManager(temp_dir / "nonexistent")
        runs = manager.list_runs()

        assert runs == []
