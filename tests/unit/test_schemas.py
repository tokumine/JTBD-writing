"""Tests for Pydantic schemas."""
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.eval.schemas import (
    AggregatedResult,
    EvalState,
    JudgmentResult,
    ModelResponse,
    ShuffledJudgment,
)
from src.prompts.schemas import (
    BasePrompt,
    Company,
    EnrichedPrompt,
    ONetTask,
    Persona,
    PersonName,
    PromptConstraint,
    ScenarioSeed,
)


class TestONetTask:
    """Tests for ONetTask schema."""

    def test_valid_task(self, sample_onet_task_data: dict) -> None:
        """Test creating valid task."""
        task = ONetTask(**sample_onet_task_data)
        assert task.task_id == "T1234"
        assert task.job_zone == 5
        assert task.writing_relevance_score == 0.95

    def test_invalid_onetsoc_code(self, sample_onet_task_data: dict) -> None:
        """Test invalid O*NET SOC code pattern."""
        sample_onet_task_data["onetsoc_code"] = "invalid"
        with pytest.raises(ValidationError):
            ONetTask(**sample_onet_task_data)

    def test_invalid_job_zone(self, sample_onet_task_data: dict) -> None:
        """Test job zone must be 1-5."""
        sample_onet_task_data["job_zone"] = 6
        with pytest.raises(ValidationError):
            ONetTask(**sample_onet_task_data)

    def test_invalid_relevance_score(self, sample_onet_task_data: dict) -> None:
        """Test relevance score must be 0-1."""
        sample_onet_task_data["writing_relevance_score"] = 1.5
        with pytest.raises(ValidationError):
            ONetTask(**sample_onet_task_data)


class TestPersona:
    """Tests for Persona schema."""

    def test_valid_persona(self, sample_persona_data: dict) -> None:
        """Test creating valid persona."""
        persona = Persona(**sample_persona_data)
        assert persona.id == "persona_001"
        assert persona.experience_level == "senior"
        assert persona.age_group == "millennial"

    def test_invalid_experience_level(self, sample_persona_data: dict) -> None:
        """Test invalid experience level."""
        sample_persona_data["experience_level"] = "expert"
        with pytest.raises(ValidationError):
            Persona(**sample_persona_data)

    def test_optional_fields(self) -> None:
        """Test optional fields can be None."""
        persona = Persona(
            id="p1",
            job_title="Engineer",
            experience_level="mid",
            age_group="gen_z",
            communication_style="casual",
            industry_background="Tech",
        )
        assert persona.education_level is None
        assert persona.years_experience is None


class TestCompany:
    """Tests for Company schema."""

    def test_valid_company(self, sample_company_data: dict) -> None:
        """Test creating valid company."""
        company = Company(**sample_company_data)
        assert company.name == "Acme Corporation"
        assert company.size == "large"
        assert company.is_public is True

    def test_invalid_size(self, sample_company_data: dict) -> None:
        """Test invalid company size."""
        sample_company_data["size"] = "huge"
        with pytest.raises(ValidationError):
            Company(**sample_company_data)


class TestPersonName:
    """Tests for PersonName schema."""

    def test_valid_name(self, sample_person_name_data: dict) -> None:
        """Test creating valid person name."""
        name = PersonName(**sample_person_name_data)
        assert name.full == "Sarah Chen"
        assert name.formality_variants["formal"] == "Ms. Chen"

    def test_minimal_name(self) -> None:
        """Test minimal required fields."""
        name = PersonName(
            first="John",
            last="Doe",
            full="John Doe",
            demographic="white",
            gender="male",
        )
        assert name.email is None
        assert name.formality_variants == {}


class TestModelResponse:
    """Tests for ModelResponse schema."""

    def test_success_response(self) -> None:
        """Test successful response."""
        response = ModelResponse(
            prompt_id="p1",
            model_id="openai/gpt-4",
            response_text="Hello world",
            status="success",
            latency_ms=1234.5,
            input_tokens=100,
            output_tokens=50,
        )
        assert response.status == "success"
        assert response.word_count is None  # Populated post-collection

    def test_error_response(self) -> None:
        """Test error response."""
        response = ModelResponse(
            prompt_id="p1",
            model_id="openai/gpt-4",
            error="Model timeout",
            status="timeout",
            latency_ms=30000.0,
        )
        assert response.status == "timeout"
        assert response.response_text is None


class TestJudgmentResult:
    """Tests for JudgmentResult schema."""

    def test_valid_judgment(self) -> None:
        """Test valid judgment."""
        judgment = JudgmentResult(
            winner="A",
            confidence="high",
            reasoning="Response A was clearer",
            scores={
                "clarity": {"A": 5, "B": 3},
                "tone": {"A": 4, "B": 4},
            },
        )
        assert judgment.winner == "A"
        assert judgment.parse_success is True

    def test_tie_judgment(self) -> None:
        """Test tie judgment."""
        judgment = JudgmentResult(
            winner="TIE",
            confidence="medium",
            reasoning="Both responses were equivalent",
        )
        assert judgment.winner == "TIE"

    def test_parse_error(self) -> None:
        """Test parse error judgment."""
        judgment = JudgmentResult(
            winner="PARSE_ERROR",
            parse_success=False,
            raw_response="Invalid JSON output",
        )
        assert judgment.parse_success is False


class TestShuffledJudgment:
    """Tests for ShuffledJudgment schema."""

    def test_shuffled_judgment(self) -> None:
        """Test shuffled judgment with position info."""
        judgment = ShuffledJudgment(
            judge_model="claude-opus",
            persona_type="writing_expert",
            position_order="AB",
            position_a_model="gemini-pro",
            position_b_model="gpt-5.2",
            judgment=JudgmentResult(winner="A", confidence="high"),
        )
        assert judgment.position_a_model == "gemini-pro"
        assert judgment.judgment.winner == "A"


class TestAggregatedResult:
    """Tests for AggregatedResult schema."""

    def test_aggregated_result(self) -> None:
        """Test aggregated comparison result."""
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
        assert result.winner == "gemini-pro"
        assert result.votes_model_a == 4


class TestEvalState:
    """Tests for EvalState schema."""

    def test_eval_state(self) -> None:
        """Test evaluation state."""
        state = EvalState(
            run_id="run_123",
            phase="response_collection",
            total_prompts=100,
            completed_count=50,
            total_cost_usd=25.50,
        )
        assert state.phase == "response_collection"
        assert state.completed_count == 50

    def test_state_with_sets(self) -> None:
        """Test state with prompt ID sets."""
        state = EvalState(
            run_id="run_123",
            phase="judging",
            total_prompts=10,
            completed_prompt_ids={"p1", "p2", "p3"},
            pending_prompt_ids={"p4", "p5"},
            failed_prompt_ids={"p6"},
        )
        assert len(state.completed_prompt_ids) == 3
        assert "p4" in state.pending_prompt_ids
