"""Pydantic schemas for prompts and related data structures."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ONetTask(BaseModel):
    """O*NET task statement with writing relevance."""

    task_id: str
    onetsoc_code: str = Field(..., pattern=r"^\d{2}-\d{4}\.\d{2}$")
    task: str
    task_type: Literal["Core", "Supplemental"] | None = None
    occupation_title: str
    occupation_description: str | None = None
    job_zone: int = Field(..., ge=1, le=5)
    soc_major_group: str = Field(..., pattern=r"^\d{2}$")
    writing_relevance_score: float = Field(..., ge=0.0, le=1.0)
    inferred_category: str
    inferred_channel: str


class Persona(BaseModel):
    """Professional persona for writing tasks."""

    id: str
    job_title: str
    experience_level: Literal["junior", "mid", "senior", "executive"]
    age_group: Literal["gen_z", "millennial", "gen_x", "boomer"]
    communication_style: Literal["formal", "professional", "casual", "technical"]
    industry_background: str
    education_level: str | None = None
    years_experience: int | None = None


class Company(BaseModel):
    """Company for grounding prompts in reality."""

    name: str
    naics_code: str
    naics_sector: str
    size: Literal["startup", "small", "medium", "large", "enterprise"]
    employee_count: int | None = None
    industry_description: str
    hq_location: str | None = None
    is_public: bool = False


class PersonName(BaseModel):
    """Generated person name with metadata."""

    first: str
    last: str
    full: str
    email: str | None = None
    demographic: str
    gender: str
    formality_variants: dict[str, str] = Field(default_factory=dict)


class ScenarioSeed(BaseModel):
    """Seed for generating specific writing scenario."""

    id: str
    scenario_type: str  # e.g., "request", "response", "announcement"
    context: str
    audience_type: str
    formality_hint: str | None = None
    urgency_hint: str | None = None
    has_attachment: bool = False
    is_reply: bool = False


class PromptConstraint(BaseModel):
    """Instruction-following constraint."""

    constraint_type: str  # "word_limit", "bullet_count", "keyword_include", etc.
    description: str
    value: Any
    is_verifiable: bool = True


class BasePrompt(BaseModel):
    """Pre-enrichment prompt skeleton."""

    id: str
    task: ONetTask
    persona: Persona
    recipient: PersonName
    company: Company
    industry: str
    scenario_seed: ScenarioSeed
    formality: Literal["very_formal", "formal", "professional", "casual", "very_casual"]
    urgency: Literal["low", "medium", "high", "critical"]
    word_count_tier: Literal["short", "medium", "long"]
    english_variant: Literal["en-US", "en-GB", "en-AU", "non-native"] = "en-US"


class EnrichedPrompt(BaseModel):
    """Fully enriched prompt ready for evaluation."""

    id: str
    base_prompt: BasePrompt
    prompt_text: str  # The actual text sent to models
    context_details: dict[str, Any] = Field(default_factory=dict)
    constraints: list[PromptConstraint] = Field(default_factory=list)
    attachment_content: str | None = None  # Mock attachment text
    prior_messages: list[str] | None = None  # For reply scenarios
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
