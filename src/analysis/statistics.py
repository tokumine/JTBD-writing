"""Statistical analysis functions."""
from collections import Counter
from dataclasses import dataclass


@dataclass
class WinRateStats:
    """Win rate statistics for a model."""

    model_id: str
    total_comparisons: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    confidence_interval: tuple[float, float]


def wilson_score_interval(
    wins: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Calculate Wilson score confidence interval for proportions.

    More accurate than normal approximation for extreme proportions.
    """
    import math

    if total == 0:
        return (0.0, 1.0)

    # Z-score for confidence level
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence, 1.96)

    p = wins / total

    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator

    return (max(0.0, center - margin), min(1.0, center + margin))


def calculate_win_rates(
    results: list[dict],
    model_id: str,
) -> WinRateStats:
    """
    Calculate win rate statistics for a model.

    Args:
        results: List of result dicts with 'winner', 'model_a', 'model_b'
        model_id: Model to calculate stats for

    Returns:
        WinRateStats for the model
    """
    wins = 0
    losses = 0
    ties = 0

    for r in results:
        if r["model_a"] == model_id or r["model_b"] == model_id:
            if r["winner"] == model_id:
                wins += 1
            elif r["winner"] == "TIE":
                ties += 1
            else:
                losses += 1

    total = wins + losses + ties
    win_rate = wins / total if total > 0 else 0.0
    ci = wilson_score_interval(wins, total)

    return WinRateStats(
        model_id=model_id,
        total_comparisons=total,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=win_rate,
        confidence_interval=ci,
    )


def mcnemars_test(
    results: list[dict],
    model_a: str,
    model_b: str,
) -> dict:
    """
    McNemar's test for paired comparisons.

    Better than binomial because results are paired (same prompt).
    """
    import math

    # Count discordant pairs (one model wins, other loses)
    a_wins = sum(1 for r in results if r["winner"] == model_a)
    b_wins = sum(1 for r in results if r["winner"] == model_b)

    n = a_wins + b_wins
    if n < 10:
        # Use exact binomial for small samples
        from math import comb

        k = min(a_wins, b_wins)
        p_value = sum(comb(n, i) * (0.5 ** n) for i in range(k + 1)) * 2
        chi2 = None
    else:
        # Use chi-square approximation with continuity correction
        chi2 = (abs(a_wins - b_wins) - 1) ** 2 / n if n > 0 else 0
        # Simple p-value approximation
        p_value = math.exp(-chi2 / 2) if chi2 else 1.0

    return {
        "statistic": chi2,
        "p_value": p_value,
        "model_a_wins": a_wins,
        "model_b_wins": b_wins,
        "test_type": "mcnemar",
    }


def bonferroni_correction(
    p_values: list[float],
    alpha: float = 0.05,
) -> dict:
    """Apply Bonferroni correction for multiple comparisons."""
    n_tests = len(p_values)
    corrected_alpha = alpha / n_tests if n_tests > 0 else alpha
    corrected_p_values = [min(1.0, p * n_tests) for p in p_values]
    significant = [p < corrected_alpha for p in p_values]

    return {
        "original_alpha": alpha,
        "corrected_alpha": corrected_alpha,
        "original_p_values": p_values,
        "corrected_p_values": corrected_p_values,
        "significant": significant,
        "method": "bonferroni",
    }


def calculate_effect_size(
    results: list[dict],
    model_a: str,
    model_b: str,
) -> float:
    """
    Calculate effect size (Cohen's h) for win rate difference.

    h = 2 * arcsin(sqrt(p1)) - 2 * arcsin(sqrt(p2))
    """
    import math

    a_wins = sum(1 for r in results if r["winner"] == model_a)
    b_wins = sum(1 for r in results if r["winner"] == model_b)
    total = len(results)

    if total == 0:
        return 0.0

    p_a = a_wins / total
    p_b = b_wins / total

    h = 2 * math.asin(math.sqrt(p_a)) - 2 * math.asin(math.sqrt(p_b))
    return h
