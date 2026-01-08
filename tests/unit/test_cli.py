"""Tests for CLI commands."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


class TestEstimateCommand:
    """Tests for estimate command."""

    def test_estimate_smoke_preset(self) -> None:
        """Test cost estimate for smoke preset."""
        result = runner.invoke(app, ["estimate", "--preset", "smoke"])

        assert result.exit_code == 0
        assert "Cost Estimate" in result.stdout
        assert "smoke" in result.stdout
        assert "$" in result.stdout

    def test_estimate_standard_preset(self) -> None:
        """Test cost estimate for standard preset."""
        result = runner.invoke(app, ["estimate", "--preset", "standard"])

        assert result.exit_code == 0
        assert "standard" in result.stdout

    def test_estimate_with_custom_prompts(self) -> None:
        """Test estimate with custom prompt count."""
        result = runner.invoke(app, ["estimate", "--preset", "smoke", "--prompts", "50"])

        assert result.exit_code == 0
        assert "50" in result.stdout


class TestPresetsCommand:
    """Tests for presets command."""

    def test_list_presets(self) -> None:
        """Test listing all presets."""
        result = runner.invoke(app, ["presets"])

        assert result.exit_code == 0
        assert "smoke" in result.stdout
        assert "dev" in result.stdout
        assert "standard" in result.stdout
        assert "full" in result.stdout


class TestModelsCommand:
    """Tests for models command."""

    def test_list_models(self) -> None:
        """Test listing model aliases."""
        result = runner.invoke(app, ["models"])

        assert result.exit_code == 0
        assert "gemini_pro" in result.stdout
        assert "gpt_pro" in result.stdout
        assert "judge_claude" in result.stdout


class TestRunCommand:
    """Tests for run command."""

    def test_dry_run(self) -> None:
        """Test dry run mode."""
        result = runner.invoke(app, ["run", "--preset", "smoke", "--dry-run"])

        assert result.exit_code == 0
        assert "Would run" in result.stdout
        assert "smoke" in result.stdout


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_no_db(self) -> None:
        """Test validate when DB doesn't exist."""
        result = runner.invoke(app, ["validate", "--no-check-api"])

        # Should complete (may have warnings about missing DB)
        assert result.exit_code == 0


class TestListCommand:
    """Tests for list command."""

    def test_list_empty(self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing when no runs exist."""
        monkeypatch.setenv("EVAL_RESULTS_DIR", str(temp_dir))

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No evaluation runs" in result.stdout or "Run ID" in result.stdout


class TestResumeCommand:
    """Tests for resume command."""

    def test_resume_nonexistent(self, temp_dir: Path) -> None:
        """Test resume with nonexistent directory."""
        result = runner.invoke(app, ["resume", str(temp_dir / "nonexistent")])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestExportCommand:
    """Tests for export command."""

    def test_export_nonexistent(self, temp_dir: Path) -> None:
        """Test export with nonexistent directory."""
        result = runner.invoke(app, ["export", str(temp_dir / "nonexistent")])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()
