"""Tests for configuration modules."""
import pytest

from src.config.cost_estimator import CostEstimate, CostEstimator
from src.config.presets import (
    MODEL_ALIASES,
    PRESETS,
    EvalPreset,
    get_preset,
    list_presets,
)
from src.config.settings import Settings


class TestSettings:
    """Tests for Settings."""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default settings values."""
        # Clear the test fixture's log level override
        monkeypatch.delenv("EVAL_LOG_LEVEL", raising=False)
        settings = Settings()  # type: ignore[call-arg]
        assert settings.log_level == "INFO"
        assert settings.max_concurrent_requests == 10
        assert settings.budget_limit == 1000.0
        assert settings.max_retries == 3

    def test_api_key_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key is required."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        # Create settings without loading from .env file to test validation
        with pytest.raises(Exception):  # Pydantic validation error
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_path_properties(self) -> None:
        """Test path property methods."""
        settings = Settings()  # type: ignore[call-arg]
        assert settings.companies_file.name == "companies.json"
        assert settings.names_file.name == "names.json"
        assert settings.naics_crosswalk_file.name == "naics_soc_crosswalk.json"


class TestPresets:
    """Tests for presets configuration."""

    def test_all_presets_exist(self) -> None:
        """Test all expected presets are defined."""
        expected = ["smoke", "dev", "quick", "standard", "comprehensive", "full"]
        for name in expected:
            assert name in PRESETS

    def test_get_preset(self) -> None:
        """Test getting preset by name."""
        preset = get_preset("smoke")
        assert preset.name == "smoke"
        assert preset.prompt_count == 10
        assert preset.estimated_cost_usd == 5.0

    def test_get_unknown_preset(self) -> None:
        """Test getting unknown preset raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_preset("unknown")  # type: ignore[arg-type]
        assert "Unknown preset" in str(exc_info.value)

    def test_list_presets(self) -> None:
        """Test listing all presets."""
        presets = list_presets()
        assert len(presets) == 6
        assert all(isinstance(p, EvalPreset) for p in presets)

    def test_preset_immutability(self) -> None:
        """Test presets are frozen dataclasses."""
        preset = get_preset("smoke")
        with pytest.raises(Exception):  # FrozenInstanceError
            preset.prompt_count = 100  # type: ignore[misc]

    def test_model_aliases(self) -> None:
        """Test model aliases are defined."""
        assert "gemini_pro" in MODEL_ALIASES
        assert "gpt_pro" in MODEL_ALIASES
        assert "judge_claude" in MODEL_ALIASES
        assert MODEL_ALIASES["gemini_pro"].startswith("google/")


class TestCostEstimator:
    """Tests for cost estimation."""

    def test_smoke_preset_estimate(self) -> None:
        """Test cost estimate for smoke preset."""
        estimator = CostEstimator()
        estimate = estimator.estimate_full_eval(
            prompt_count=10,
            model_count=2,
            judge_count=1,
            persona_count=1,
            votes_per_judge=1,
            position_shuffle=False,
        )
        assert isinstance(estimate, CostEstimate)
        assert estimate.total_cost > 0
        assert estimate.response_generation_cost > 0
        assert estimate.judging_cost > 0

    def test_position_shuffle_doubles_cost(self) -> None:
        """Test position shuffle increases judge cost."""
        estimator = CostEstimator()

        without_shuffle = estimator.estimate_full_eval(
            prompt_count=10,
            model_count=2,
            judge_count=1,
            persona_count=1,
            votes_per_judge=1,
            position_shuffle=False,
        )

        with_shuffle = estimator.estimate_full_eval(
            prompt_count=10,
            model_count=2,
            judge_count=1,
            persona_count=1,
            votes_per_judge=1,
            position_shuffle=True,
        )

        # Position shuffle should roughly double judge calls
        assert with_shuffle.judging_cost > without_shuffle.judging_cost * 1.5

    def test_votes_multiply_cost(self) -> None:
        """Test more votes increase cost proportionally."""
        estimator = CostEstimator()

        one_vote = estimator.estimate_full_eval(
            prompt_count=10,
            model_count=2,
            judge_count=1,
            persona_count=1,
            votes_per_judge=1,
            position_shuffle=False,
        )

        five_votes = estimator.estimate_full_eval(
            prompt_count=10,
            model_count=2,
            judge_count=1,
            persona_count=1,
            votes_per_judge=5,
            position_shuffle=False,
        )

        # 5 votes should roughly 5x the judge cost
        assert five_votes.judging_cost > one_vote.judging_cost * 4

    def test_breakdown_fields(self) -> None:
        """Test breakdown contains expected fields."""
        estimator = CostEstimator()
        estimate = estimator.estimate_full_eval(
            prompt_count=10,
            model_count=2,
            judge_count=1,
            persona_count=1,
            votes_per_judge=1,
            position_shuffle=False,
        )

        assert "response_calls" in estimate.breakdown
        assert "total_comparisons" in estimate.breakdown
        assert "total_judge_calls" in estimate.breakdown
        assert "enrichment_calls" in estimate.breakdown

    def test_estimate_str(self) -> None:
        """Test string representation of estimate."""
        estimate = CostEstimate(
            response_generation_cost=10.0,
            judging_cost=50.0,
            enrichment_cost=5.0,
            total_cost=65.0,
        )
        output = str(estimate)
        assert "Response generation" in output
        assert "Judging" in output
        assert "Total" in output
        assert "$65.00" in output
