"""Pydantic schemas for evaluation results."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ModelResponse(BaseModel):
    """Response from a model."""

    prompt_id: str
    model_id: str
    response_text: str | None = None
    error: str | None = None
    status: Literal["success", "error", "timeout", "refused", "empty"]
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    # Response analysis (populated post-collection)
    format_detected: str | None = None  # email, memo, report, etc.
    has_greeting: bool | None = None
    has_signoff: bool | None = None
    bullet_count: int | None = None
    paragraph_count: int | None = None
    word_count: int | None = None


class JudgmentResult(BaseModel):
    """Single judgment from a judge model."""

    winner: Literal["A", "B", "TIE", "PARSE_ERROR"]
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    reasoning: str = ""
    scores: dict[str, dict[str, float]] | None = None
    # e.g., {"appropriateness": {"A": 4, "B": 3}, "clarity": {"A": 5, "B": 4}}
    weaknesses_a: list[str] = Field(default_factory=list)
    weaknesses_b: list[str] = Field(default_factory=list)
    parse_success: bool = True
    raw_response: str | None = None


class ShuffledJudgment(BaseModel):
    """Judgment with position information."""

    judge_model: str
    persona_type: Literal["writing_expert", "recipient"]
    position_order: Literal["AB", "BA"]
    position_a_model: str  # Which actual model was in position A
    position_b_model: str  # Which actual model was in position B
    judgment: JudgmentResult


class AggregatedResult(BaseModel):
    """Final aggregated comparison result."""

    prompt_id: str
    model_a: str
    model_b: str
    winner: str  # model_a, model_b, or "TIE"
    gemini_model_id: str  # Track which model is Gemini for weakness analysis
    gemini_was_a: bool  # True if Gemini was in model_a position

    # Vote counts
    votes_model_a: int
    votes_model_b: int
    votes_tie: int

    # Agreement metrics
    inter_judge_agreement: float  # Fleiss Kappa
    position_consistency: float  # Agreement across position shuffles

    # Per-judge-persona breakdown
    judge_persona_votes: dict[str, str] = Field(default_factory=dict)
    # e.g., {"claude_expert": "model_a", "claude_recipient": "model_b", ...}

    # Raw judgments for detailed analysis
    raw_judgments: list[ShuffledJudgment] = Field(default_factory=list)

    # Confidence
    margin: float  # Difference in vote proportions
    confidence: Literal["high", "medium", "low"]


class EvalState(BaseModel):
    """Current state of evaluation for checkpointing."""

    run_id: str
    phase: Literal[
        "prompt_generation", "response_collection", "judging", "analysis", "complete"
    ]
    completed_prompt_ids: set[str] = Field(default_factory=set)
    pending_prompt_ids: set[str] = Field(default_factory=set)
    failed_prompt_ids: set[str] = Field(default_factory=set)

    # Progress tracking
    total_prompts: int
    completed_count: int = 0

    # Cost tracking
    total_cost_usd: float = 0.0

    # Timing
    started_at: datetime | None = None
    last_checkpoint: datetime | None = None

    class Config:
        """Pydantic config."""

        # Allow set type
        arbitrary_types_allowed = True
