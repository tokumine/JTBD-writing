"""Tests for evaluation modules."""
import pytest

from src.eval.judge_parser import JudgeParser
from src.eval.schemas import JudgmentResult, ShuffledJudgment
from src.eval.vote_aggregator import (
    VoteAggregator,
    calculate_inter_judge_agreement,
    calculate_position_consistency,
)


class TestJudgeParser:
    """Tests for judgment parsing."""

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON response."""
        parser = JudgeParser()
        response = '''
        {
            "winner": "A",
            "confidence": "high",
            "reasoning": "Response A was clearer and more professional",
            "scores": {
                "clarity": {"A": 5, "B": 3},
                "tone": {"A": 4, "B": 4}
            },
            "weaknesses_a": ["slightly verbose"],
            "weaknesses_b": ["too casual", "missing greeting"]
        }
        '''

        result = parser.parse(response)

        assert result.winner == "A"
        assert result.confidence == "high"
        assert result.parse_success is True
        assert "clearer" in result.reasoning
        assert len(result.weaknesses_b) == 2

    def test_parse_markdown_json(self) -> None:
        """Test parsing JSON in markdown code block."""
        parser = JudgeParser()
        response = '''Here is my evaluation:

        ```json
        {
            "winner": "B",
            "confidence": "medium",
            "reasoning": "Better formatting"
        }
        ```
        '''

        result = parser.parse(response)

        assert result.winner == "B"
        assert result.confidence == "medium"
        assert result.parse_success is True

    def test_parse_tie(self) -> None:
        """Test parsing tie judgment."""
        parser = JudgeParser()
        response = '{"winner": "TIE", "confidence": "low", "reasoning": "Both equivalent"}'

        result = parser.parse(response)

        assert result.winner == "TIE"
        assert result.parse_success is True

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON returns error result."""
        parser = JudgeParser()
        response = "This is not JSON at all, just random text."

        result = parser.parse(response)

        assert result.winner == "PARSE_ERROR"
        assert result.parse_success is False

    def test_parse_invalid_winner(self) -> None:
        """Test parsing invalid winner value."""
        parser = JudgeParser()
        response = '{"winner": "C", "confidence": "high"}'

        result = parser.parse(response)

        assert result.winner == "PARSE_ERROR"
        assert result.parse_success is False


class TestVoteAggregator:
    """Tests for vote aggregation."""

    def _make_judgment(
        self,
        judge: str,
        persona: str,
        winner: str,
        position_order: str = "AB",
        pos_a_model: str = "gemini",
        pos_b_model: str = "gpt",
    ) -> ShuffledJudgment:
        """Helper to create judgment."""
        return ShuffledJudgment(
            judge_model=judge,
            persona_type=persona,  # type: ignore
            position_order=position_order,  # type: ignore
            position_a_model=pos_a_model,
            position_b_model=pos_b_model,
            judgment=JudgmentResult(winner=winner, confidence="high"),  # type: ignore
        )

    def test_simple_majority(self) -> None:
        """Test simple majority wins."""
        aggregator = VoteAggregator()

        judgments = [
            self._make_judgment("claude", "writing_expert", "A"),  # gemini wins
            self._make_judgment("gpt", "writing_expert", "A"),  # gemini wins
            self._make_judgment("gemini_judge", "writing_expert", "B"),  # gpt wins
        ]

        result = aggregator.aggregate_comparison(judgments, "gemini", "gpt")

        assert result.winner == "gemini"
        assert result.votes_a > result.votes_b

    def test_tie_result(self) -> None:
        """Test tie when votes are equal."""
        aggregator = VoteAggregator()

        judgments = [
            self._make_judgment("claude", "writing_expert", "A"),
            self._make_judgment("gpt", "writing_expert", "B"),
            self._make_judgment("gemini_judge", "writing_expert", "TIE"),
        ]

        result = aggregator.aggregate_comparison(judgments, "gemini", "gpt")

        # With one vote each plus tie, it should be a tie
        assert result.winner in ["gemini", "gpt", "TIE"]

    def test_position_handling(self) -> None:
        """Test handling of position shuffling."""
        aggregator = VoteAggregator()

        # Same judge says A wins in AB order, and B wins in BA order
        # This means gemini wins in both cases
        judgments = [
            self._make_judgment("claude", "writing_expert", "A", "AB", "gemini", "gpt"),
            self._make_judgment("claude", "writing_expert", "B", "BA", "gpt", "gemini"),
        ]

        result = aggregator.aggregate_comparison(judgments, "gemini", "gpt")

        # Both should count as gemini wins
        assert result.winner == "gemini"

    def test_empty_judgments(self) -> None:
        """Test handling empty judgments."""
        aggregator = VoteAggregator()
        result = aggregator.aggregate_comparison([], "gemini", "gpt")

        assert result.winner == "TIE"
        assert result.confidence == "low"


class TestInterJudgeAgreement:
    """Tests for inter-judge agreement calculation."""

    def _make_judgment(
        self,
        winner: str,
        pos_a: str = "gemini",
        pos_b: str = "gpt",
    ) -> ShuffledJudgment:
        """Helper to create judgment."""
        return ShuffledJudgment(
            judge_model="judge",
            persona_type="writing_expert",  # type: ignore
            position_order="AB",  # type: ignore
            position_a_model=pos_a,
            position_b_model=pos_b,
            judgment=JudgmentResult(winner=winner, confidence="high"),  # type: ignore
        )

    def test_perfect_agreement(self) -> None:
        """Test perfect agreement gives 1.0."""
        judgments = [
            self._make_judgment("A"),
            self._make_judgment("A"),
            self._make_judgment("A"),
        ]

        agreement = calculate_inter_judge_agreement(judgments, "gemini", "gpt")
        assert agreement == 1.0

    def test_no_agreement(self) -> None:
        """Test low agreement."""
        judgments = [
            self._make_judgment("A"),
            self._make_judgment("B"),
            self._make_judgment("TIE"),
        ]

        agreement = calculate_inter_judge_agreement(judgments, "gemini", "gpt")
        # With even split, agreement should be low
        assert agreement < 0.5


class TestPositionConsistency:
    """Tests for position consistency calculation."""

    def _make_judgment(
        self,
        judge: str,
        persona: str,
        winner: str,
        order: str,
        pos_a: str,
        pos_b: str,
    ) -> ShuffledJudgment:
        """Helper to create judgment."""
        # Use valid persona types
        valid_persona = "writing_expert" if "expert" in persona else "recipient"
        return ShuffledJudgment(
            judge_model=judge,
            persona_type=valid_persona,  # type: ignore
            position_order=order,  # type: ignore
            position_a_model=pos_a,
            position_b_model=pos_b,
            judgment=JudgmentResult(winner=winner, confidence="high"),  # type: ignore
        )

    def test_perfect_consistency(self) -> None:
        """Test perfect position consistency."""
        judgments = [
            # Judge says A wins when gemini is A, and B wins when gpt is A
            # This means gemini wins consistently
            self._make_judgment("claude", "expert", "A", "AB", "gemini", "gpt"),
            self._make_judgment("claude", "expert", "B", "BA", "gpt", "gemini"),
        ]

        consistency = calculate_position_consistency(judgments, "gemini", "gpt")
        assert consistency == 1.0

    def test_inconsistent_positions(self) -> None:
        """Test inconsistent position handling."""
        judgments = [
            # Judge says A wins regardless of order - position bias!
            self._make_judgment("claude", "expert", "A", "AB", "gemini", "gpt"),
            self._make_judgment("claude", "expert", "A", "BA", "gpt", "gemini"),
        ]

        consistency = calculate_position_consistency(judgments, "gemini", "gpt")
        # Different models win based on position, so low consistency
        assert consistency < 1.0
