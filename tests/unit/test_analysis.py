"""Tests for analysis and statistics modules."""
import pytest

from src.analysis.statistics import (
    WinRateStats,
    bonferroni_correction,
    calculate_effect_size,
    calculate_win_rates,
    mcnemars_test,
    wilson_score_interval,
)


class TestWilsonScoreInterval:
    """Tests for Wilson score confidence interval."""

    def test_perfect_win_rate(self) -> None:
        """Test confidence interval for 100% wins."""
        lower, upper = wilson_score_interval(wins=10, total=10)

        assert lower > 0.5
        assert upper == 1.0

    def test_zero_win_rate(self) -> None:
        """Test confidence interval for 0% wins."""
        lower, upper = wilson_score_interval(wins=0, total=10)

        assert lower == 0.0
        assert upper < 0.5

    def test_fifty_percent(self) -> None:
        """Test confidence interval for 50% wins."""
        lower, upper = wilson_score_interval(wins=50, total=100)

        assert lower < 0.5
        assert upper > 0.5

    def test_zero_total(self) -> None:
        """Test handling of zero total."""
        lower, upper = wilson_score_interval(wins=0, total=0)

        assert lower == 0.0
        assert upper == 1.0


class TestCalculateWinRates:
    """Tests for win rate calculation."""

    def test_simple_win_rates(self) -> None:
        """Test simple win rate calculation."""
        results = [
            {"model_a": "gemini", "model_b": "gpt", "winner": "gemini"},
            {"model_a": "gemini", "model_b": "gpt", "winner": "gemini"},
            {"model_a": "gemini", "model_b": "gpt", "winner": "gpt"},
            {"model_a": "gemini", "model_b": "gpt", "winner": "TIE"},
        ]

        stats = calculate_win_rates(results, "gemini")

        assert stats.model_id == "gemini"
        assert stats.wins == 2
        assert stats.losses == 1
        assert stats.ties == 1
        assert stats.win_rate == 0.5

    def test_no_comparisons(self) -> None:
        """Test handling model with no comparisons."""
        results = [
            {"model_a": "gpt", "model_b": "claude", "winner": "gpt"},
        ]

        stats = calculate_win_rates(results, "gemini")

        assert stats.total_comparisons == 0
        assert stats.win_rate == 0.0


class TestMcnemarsTest:
    """Tests for McNemar's test."""

    def test_significant_difference(self) -> None:
        """Test detecting significant difference."""
        # Create results where model_a clearly wins more
        results = [{"model_a": "gemini", "model_b": "gpt", "winner": "gemini"}] * 15
        results += [{"model_a": "gemini", "model_b": "gpt", "winner": "gpt"}] * 3

        test_result = mcnemars_test(results, "gemini", "gpt")

        assert test_result["model_a_wins"] == 15
        assert test_result["model_b_wins"] == 3
        assert test_result["p_value"] < 0.05

    def test_no_difference(self) -> None:
        """Test when there's no significant difference."""
        results = [{"model_a": "gemini", "model_b": "gpt", "winner": "gemini"}] * 10
        results += [{"model_a": "gemini", "model_b": "gpt", "winner": "gpt"}] * 10

        test_result = mcnemars_test(results, "gemini", "gpt")

        assert test_result["model_a_wins"] == 10
        assert test_result["model_b_wins"] == 10
        # P-value should be high (not significant)
        assert test_result["p_value"] > 0.05


class TestBonferroniCorrection:
    """Tests for Bonferroni correction."""

    def test_correction_applied(self) -> None:
        """Test correction is properly applied."""
        p_values = [0.005, 0.02, 0.03, 0.04, 0.05]

        result = bonferroni_correction(p_values, alpha=0.05)

        assert result["corrected_alpha"] == 0.01  # 0.05 / 5
        assert result["corrected_p_values"][0] == 0.025  # 0.005 * 5
        assert result["significant"][0] is True  # 0.005 < 0.01

    def test_multiple_significant(self) -> None:
        """Test identifying multiple significant results."""
        p_values = [0.001, 0.005, 0.02]

        result = bonferroni_correction(p_values, alpha=0.05)

        # First two should be significant after correction
        assert result["significant"][0] is True
        assert result["significant"][1] is True
        assert result["significant"][2] is False


class TestCalculateEffectSize:
    """Tests for effect size calculation."""

    def test_no_effect(self) -> None:
        """Test effect size when results are equal."""
        results = [
            {"model_a": "gemini", "model_b": "gpt", "winner": "gemini"},
            {"model_a": "gemini", "model_b": "gpt", "winner": "gpt"},
        ]

        h = calculate_effect_size(results, "gemini", "gpt")

        # Should be close to zero
        assert abs(h) < 0.5

    def test_large_effect(self) -> None:
        """Test effect size with clear winner."""
        results = [{"model_a": "gemini", "model_b": "gpt", "winner": "gemini"}] * 10

        h = calculate_effect_size(results, "gemini", "gpt")

        # Should be positive (gemini favored) and large
        assert h > 1.0

    def test_empty_results(self) -> None:
        """Test effect size with empty results."""
        h = calculate_effect_size([], "gemini", "gpt")

        assert h == 0.0
