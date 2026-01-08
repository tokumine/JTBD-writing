"""Vote aggregation for evaluation judgments."""
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from src.eval.schemas import ShuffledJudgment


@dataclass
class VoteResult:
    """Result of vote aggregation."""

    winner: str  # model_a, model_b, or "TIE"
    votes_a: int
    votes_b: int
    votes_tie: int
    margin: float
    confidence: Literal["high", "medium", "low"]


class VoteAggregator:
    """
    Two-level majority-of-majorities aggregation.

    Aggregation hierarchy:
    1. Per-judge-persona: Take majority across position orderings
    2. Across judge-personas: Take majority of judge-persona majorities
    """

    def aggregate_comparison(
        self,
        judgments: list[ShuffledJudgment],
        model_a: str,
        model_b: str,
    ) -> VoteResult:
        """
        Aggregate votes using majority-of-majorities.

        Level 1: For each (judge, persona) pair, aggregate across positions
        Level 2: Take majority across all (judge, persona) pairs
        """
        # Group judgments by (judge, persona)
        judge_persona_groups: dict[tuple[str, str], list[ShuffledJudgment]] = {}
        for j in judgments:
            key = (j.judge_model, j.persona_type)
            if key not in judge_persona_groups:
                judge_persona_groups[key] = []
            judge_persona_groups[key].append(j)

        # Level 1: Compute majority for each (judge, persona)
        level1_votes: list[str] = []
        for group in judge_persona_groups.values():
            group_winner = self._aggregate_group(group, model_a, model_b)
            level1_votes.append(group_winner)

        # Level 2: Majority across groups
        vote_counts = Counter(level1_votes)
        votes_a = vote_counts.get(model_a, 0)
        votes_b = vote_counts.get(model_b, 0)
        votes_tie = vote_counts.get("TIE", 0)

        total_votes = votes_a + votes_b + votes_tie
        if total_votes == 0:
            return VoteResult(
                winner="TIE",
                votes_a=0,
                votes_b=0,
                votes_tie=0,
                margin=0.0,
                confidence="low",
            )

        # Determine winner
        if votes_a > votes_b and votes_a > votes_tie:
            winner = model_a
        elif votes_b > votes_a and votes_b > votes_tie:
            winner = model_b
        else:
            winner = "TIE"

        # Calculate margin and confidence
        max_votes = max(votes_a, votes_b, votes_tie)
        second_max = sorted([votes_a, votes_b, votes_tie])[-2]
        margin = (max_votes - second_max) / total_votes if total_votes > 0 else 0.0

        if margin >= 0.5:
            confidence: Literal["high", "medium", "low"] = "high"
        elif margin >= 0.2:
            confidence = "medium"
        else:
            confidence = "low"

        return VoteResult(
            winner=winner,
            votes_a=votes_a,
            votes_b=votes_b,
            votes_tie=votes_tie,
            margin=margin,
            confidence=confidence,
        )

    def _aggregate_group(
        self,
        judgments: list[ShuffledJudgment],
        model_a: str,
        model_b: str,
    ) -> str:
        """Aggregate votes within a (judge, persona) group."""
        # Map position-relative winners to actual model winners
        actual_winners: list[str] = []
        for j in judgments:
            if j.judgment.winner == "A":
                actual_winners.append(j.position_a_model)
            elif j.judgment.winner == "B":
                actual_winners.append(j.position_b_model)
            else:
                actual_winners.append("TIE")

        # Count and return majority
        counts = Counter(actual_winners)
        count_a = counts.get(model_a, 0)
        count_b = counts.get(model_b, 0)
        count_tie = counts.get("TIE", 0)

        if count_a > count_b and count_a > count_tie:
            return model_a
        elif count_b > count_a and count_b > count_tie:
            return model_b
        else:
            return "TIE"


def calculate_inter_judge_agreement(
    judgments: list[ShuffledJudgment],
    model_a: str,
    model_b: str,
) -> float:
    """
    Calculate inter-judge agreement using Fleiss' Kappa.

    Simplified version that measures agreement on the winner.
    """
    if len(judgments) < 2:
        return 1.0

    # Get winner calls per judgment
    winners: list[str] = []
    for j in judgments:
        if j.judgment.winner == "A":
            winners.append(j.position_a_model)
        elif j.judgment.winner == "B":
            winners.append(j.position_b_model)
        else:
            winners.append("TIE")

    # Calculate observed agreement
    counts = Counter(winners)
    n = len(winners)

    # Proportion agreement (simplified Kappa proxy)
    max_count = max(counts.values())
    observed_agreement = max_count / n

    # Expected agreement under random voting (1/3 for three outcomes)
    expected_agreement = 1.0 / 3.0

    # Kappa
    if expected_agreement >= 1.0:
        return 1.0

    kappa = (observed_agreement - expected_agreement) / (1.0 - expected_agreement)
    return max(0.0, min(1.0, kappa))


def calculate_position_consistency(
    judgments: list[ShuffledJudgment],
    model_a: str,
    model_b: str,
) -> float:
    """
    Calculate consistency across position orderings.

    Measures whether judges give consistent results regardless of
    which model is shown as "A" or "B".
    """
    # Group by (judge, persona)
    by_key: dict[tuple[str, str], list[ShuffledJudgment]] = {}
    for j in judgments:
        key = (j.judge_model, j.persona_type)
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(j)

    # For each group, check if AB and BA orderings agree
    consistent = 0
    total_pairs = 0

    for group in by_key.values():
        ab_judgments = [j for j in group if j.position_order == "AB"]
        ba_judgments = [j for j in group if j.position_order == "BA"]

        if not ab_judgments or not ba_judgments:
            continue

        # Get majority winner for each ordering
        ab_winner = _get_majority_winner(ab_judgments, model_a, model_b)
        ba_winner = _get_majority_winner(ba_judgments, model_a, model_b)

        total_pairs += 1
        if ab_winner == ba_winner:
            consistent += 1

    if total_pairs == 0:
        return 1.0

    return consistent / total_pairs


def _get_majority_winner(
    judgments: list[ShuffledJudgment],
    model_a: str,
    model_b: str,
) -> str:
    """Get majority winner from a list of judgments."""
    winners: list[str] = []
    for j in judgments:
        if j.judgment.winner == "A":
            winners.append(j.position_a_model)
        elif j.judgment.winner == "B":
            winners.append(j.position_b_model)
        else:
            winners.append("TIE")

    counts = Counter(winners)
    count_a = counts.get(model_a, 0)
    count_b = counts.get(model_b, 0)
    count_tie = counts.get("TIE", 0)

    if count_a > count_b and count_a > count_tie:
        return model_a
    elif count_b > count_a and count_b > count_tie:
        return model_b
    return "TIE"
