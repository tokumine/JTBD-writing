# Gemini Writing Evaluation Framework - Implementation Plan (Draft 3)

## Executive Summary

This document presents a comprehensive implementation plan for the Gemini Writing Evaluation Framework, a sophisticated evaluation system designed to compare Gemini 3.0 Pro and Flash models against competing frontier LLMs on realistic professional writing tasks derived from the O*NET database. The framework will produce statistically rigorous, reproducible evaluations that identify specific strengths and weaknesses in Gemini's writing capabilities across all professional contexts in the US economy.

---

## Part 1: System Architecture Overview

### 1.1 High-Level Architecture

The framework consists of seven primary subsystems organized into a layered architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────────┐   │
│  │   CLI Module  │  │   TUI Module  │  │   Configuration Manager       │   │
│  │   (argparse)  │  │   (textual)   │  │   (Presets & Custom)          │   │
│  └───────────────┘  └───────────────┘  └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Evaluation Engine (Core)                            │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │ Task Queue  │ │ Scheduler   │ │ Checkpoint  │ │ Cost Estimator  │  │  │
│  │  │ Manager     │ │ (asyncio)   │ │ Manager     │ │ & Tracker       │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────────┐
│   PROMPT GENERATION │ │   MODEL EXECUTION   │ │     EVALUATION ENGINE       │
│  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────────────┐  │
│  │ O*NET Loader  │  │ │  │ OpenRouter    │  │ │  │ Judge Orchestrator    │  │
│  │ NAICS Mapper  │  │ │  │ Client        │  │ │  │ (Multi-model/persona) │  │
│  │ Company DB    │  │ │  │ (httpx async) │  │ │  └───────────────────────┘  │
│  │ Name Generator│  │ │  └───────────────┘  │ │  ┌───────────────────────┐  │
│  │ LLM Enricher  │  │ │  ┌───────────────┐  │ │  │ Vote Aggregator       │  │
│  └───────────────┘  │ │  │ Rate Limiter  │  │ │  │ (Majority-of-majority)│  │
└─────────────────────┘ │  │ Retry Handler │  │ │  └───────────────────────┘  │
                        │  │ Circuit Break │  │ │  ┌───────────────────────┐  │
                        │  └───────────────┘  │ │  │ Bias Detector         │  │
                        └─────────────────────┘ │  └───────────────────────┘  │
                                                └─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PERSISTENCE LAYER                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────────┐   │
│  │   SQLite DB   │  │  File Store   │  │   Checkpoint System           │   │
│  │   (results)   │  │  (JSON/logs)  │  │   (Resume capability)         │   │
│  └───────────────┘  └───────────────┘  └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANALYSIS & REPORTING LAYER                           │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────────┐   │
│  │ Statistics    │  │ Visualization │  │   PDF Report Generator        │   │
│  │ Calculator    │  │ (plotly)      │  │   (reportlab/weasyprint)      │   │
│  └───────────────┘  └───────────────┘  └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async support, rich ecosystem |
| HTTP Client | httpx | Async-native, connection pooling |
| Data Validation | Pydantic v2 | Fast validation, JSON schema generation |
| Terminal UI | Textual | Modern rich TUI framework |
| Database | SQLite | Lightweight, portable, no server needed |
| Visualization | Plotly | Interactive charts, PDF export |
| PDF Generation | WeasyPrint + reportlab | Professional PDF output |
| Async | asyncio | Native Python concurrency |
| CLI | Typer (with Rich) | Type-safe CLI with beautiful output |
| Testing | pytest + pytest-asyncio | Async test support |

### 1.3 Directory Structure

```
gemini-writing-eval/
├── pyproject.toml                   # Project configuration (Poetry/PDM)
├── README.md                        # Project documentation
├── .env.example                     # Environment variables template
│
├── src/
│   ├── __init__.py
│   │
│   ├── cli/                         # Command-line interface
│   │   ├── __init__.py
│   │   ├── main.py                  # CLI entry point
│   │   ├── commands/                # Command implementations
│   │   │   ├── run.py               # Main eval command
│   │   │   ├── resume.py            # Resume command
│   │   │   ├── compare.py           # Cross-run comparison
│   │   │   └── viewer.py            # TUI viewer launch
│   │   └── presets.py               # Preset configurations
│   │
│   ├── config/                      # Configuration management
│   │   ├── __init__.py
│   │   ├── settings.py              # Global settings (Pydantic BaseSettings)
│   │   ├── models.py                # Model configuration schemas
│   │   └── presets.py               # 10 preset configurations
│   │
│   ├── data/                        # Data layer
│   │   ├── __init__.py
│   │   ├── onet/                    # O*NET database interface
│   │   │   ├── __init__.py
│   │   │   ├── loader.py            # SQLite query interface
│   │   │   ├── models.py            # Pydantic models for O*NET data
│   │   │   └── queries.py           # Pre-built SQL queries
│   │   ├── naics/                   # NAICS mapping
│   │   │   ├── __init__.py
│   │   │   ├── mapper.py            # NAICS code mapper
│   │   │   └── crosswalk.py         # SOC-NAICS crosswalk
│   │   ├── companies/               # Company database
│   │   │   ├── __init__.py
│   │   │   ├── database.py          # Company lookup
│   │   │   └── generator.py         # Company context generator
│   │   └── names/                   # Name generation
│   │       ├── __init__.py
│   │       └── generator.py         # Diverse name generator
│   │
│   ├── prompts/                     # Prompt generation pipeline
│   │   ├── __init__.py
│   │   ├── pipeline.py              # Three-phase generation pipeline
│   │   ├── schemas.py               # Prompt data models
│   │   ├── enricher.py              # LLM enrichment (Phase 3)
│   │   ├── sampler.py               # Stratified sampling
│   │   └── validators.py            # Prompt validation
│   │
│   ├── api/                         # API client layer
│   │   ├── __init__.py
│   │   ├── openrouter.py            # OpenRouter client
│   │   ├── rate_limiter.py          # Rate limiting
│   │   ├── retry.py                 # Retry with exponential backoff
│   │   └── circuit_breaker.py       # Circuit breaker pattern
│   │
│   ├── eval/                        # Evaluation engine
│   │   ├── __init__.py
│   │   ├── engine.py                # Main evaluation orchestrator
│   │   ├── generator.py             # Response generator
│   │   ├── judge.py                 # Judge orchestrator
│   │   ├── rubric.py                # Evaluation rubric
│   │   ├── aggregator.py            # Vote aggregation
│   │   └── bias.py                  # Bias detection
│   │
│   ├── storage/                     # Data persistence
│   │   ├── __init__.py
│   │   ├── database.py              # SQLite operations
│   │   ├── schemas.py               # Database schemas
│   │   ├── checkpoint.py            # Checkpoint management
│   │   └── export.py                # CSV/JSON export
│   │
│   ├── tui/                         # Terminal UI
│   │   ├── __init__.py
│   │   ├── app.py                   # Main TUI application
│   │   ├── screens/                 # TUI screens
│   │   │   ├── progress.py          # Progress dashboard
│   │   │   ├── viewer.py            # Results viewer
│   │   │   └── stats.py             # Statistics view
│   │   └── widgets/                 # Custom widgets
│   │       ├── progress_bar.py
│   │       └── comparison.py
│   │
│   ├── analysis/                    # Statistical analysis
│   │   ├── __init__.py
│   │   ├── statistics.py            # Win rates, CI, significance
│   │   ├── reliability.py           # Inter-rater reliability
│   │   └── weakness.py              # Weakness identification
│   │
│   └── reports/                     # Report generation
│       ├── __init__.py
│       ├── generator.py             # Report orchestrator
│       ├── charts.py                # Plotly chart generation
│       ├── pdf.py                   # PDF generation
│       └── templates/               # Report templates
│
├── db/                              # Database files
│   ├── onet.db                      # O*NET 30.1 database
│   └── ONET_WRITING_REFERENCE.md    # O*NET reference documentation
│
├── results/                         # Evaluation results (gitignored)
│   └── eval_YYYY-MM-DD_HH-MM-SS/    # Per-run directories
│
└── tests/                           # Test suite
    ├── __init__.py
    ├── conftest.py                  # Pytest fixtures
    ├── unit/                        # Unit tests
    ├── integration/                 # Integration tests
    └── fixtures/                    # Test data
```

---

## Part 2: Data Models and Schemas

### 2.1 Core Prompt Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class EnglishVariant(str, Enum):
    US = "en-US"
    GB = "en-GB"
    AU = "en-AU"
    NON_NATIVE = "non-native"

class CommunicationChannel(str, Enum):
    EMAIL = "email"
    MEMO = "memo"
    REPORT = "report"
    LETTER = "letter"
    PRESENTATION = "presentation"
    SOCIAL_MEDIA = "social_media"
    INSTANT_MESSAGE = "instant_message"
    OTHER = "other"

class SensitiveCategory(str, Enum):
    HR_ISSUE = "hr_issue"
    LEGAL = "legal"
    BAD_NEWS = "bad_news"
    CONFIDENTIAL = "confidential"
    CONFLICT = "conflict"
    NONE = "none"

class Persona(BaseModel):
    """Writer or recipient persona"""
    name: str
    email: Optional[str] = None
    role: str
    age_range: Optional[str] = None  # e.g., "25-35", "55-65"
    generation: Optional[str] = None  # e.g., "GenZ", "Millennial", "Boomer"
    skill_level: Optional[int] = Field(None, ge=1, le=5)  # 1=novice, 5=expert
    english_variant: EnglishVariant = EnglishVariant.US

class Company(BaseModel):
    """Company context"""
    name: str
    industry_naics: str  # 2-digit NAICS code
    industry_name: str
    size_category: Literal["startup", "small", "medium", "large", "fortune500"]
    employee_count: Optional[int] = None
    public_private: Literal["public", "private"]
    hq_location: Optional[str] = None
    founded_year: Optional[int] = None

class AttachmentReference(BaseModel):
    """Mock attachment or prior context"""
    type: Literal["report", "email_thread", "meeting_notes", "resume", "document", "data"]
    description: str
    content: str  # Actual content to include

class InstructionConstraint(BaseModel):
    """Explicit instruction to test compliance"""
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    constraint: str
    verifiable: bool = True  # Can be programmatically verified

class WritingPrompt(BaseModel):
    """Complete writing prompt schema"""
    # Identifiers
    prompt_id: str
    onet_task_id: str
    onet_soc_code: str

    # Core task
    task_statement: str  # Original O*NET task
    enriched_prompt: str  # Full prompt with all context

    # Occupation context
    occupation_title: str
    occupation_description: Optional[str] = None
    job_zone: int = Field(ge=1, le=5)
    soc_major_group: str  # 2-digit SOC code

    # Industry context
    company: Company

    # Personas
    writer: Persona
    recipients: list[Persona] = Field(default_factory=list)
    cc_recipients: list[Persona] = Field(default_factory=list)

    # Communication context
    channel: CommunicationChannel
    formality_level: int = Field(ge=1, le=5)  # 1=very casual, 5=very formal
    urgency_level: int = Field(ge=1, le=5)  # 1=low, 5=critical
    relationship_context: Literal["first_contact", "ongoing", "established"]
    audience_size: Literal["one_on_one", "small_group", "department", "company", "public"]
    emotional_context: Optional[str] = None  # e.g., "crisis", "celebration", "routine"
    message_position: Literal["initial", "reply", "follow_up"]

    # Additional context
    temporal_context: Optional[str] = None  # e.g., "Q4 2024", "Friday deadline"
    attachments: list[AttachmentReference] = Field(default_factory=list)
    prior_message: Optional[str] = None  # For reply scenarios
    tone_example: Optional[str] = None  # For tone matching
    competing_objectives: list[str] = Field(default_factory=list)

    # Revision tasks
    is_revision_task: bool = False
    original_text: Optional[str] = None  # Text to revise if applicable
    revision_instruction: Optional[str] = None

    # Ambiguity handling
    deliberate_ambiguity: bool = False
    ambiguity_type: Optional[str] = None

    # Instruction following
    explicit_constraints: list[InstructionConstraint] = Field(default_factory=list)

    # Sensitive content
    sensitive_category: SensitiveCategory = SensitiveCategory.NONE

    # Categorization metadata
    writing_category: str  # e.g., "correspondence", "report", "proposal"

    # Language
    language: str = "en"
    language_variant: str = "en-US"

    # Generation metadata
    generation_phase: int  # 1, 2, or 3
    generation_model: Optional[str] = None  # Model used for enrichment
    generation_timestamp: datetime
    random_seed: int
```

### 2.2 Response Schema

```python
class ModelResponse(BaseModel):
    """Model response with metadata"""
    response_id: str
    prompt_id: str
    model_id: str
    model_name: str

    # Response content
    response_text: str

    # Response metadata
    response_length_chars: int
    response_length_words: int
    response_length_tokens: int
    response_time_ms: int

    # Format detection
    uses_bullet_points: bool
    uses_headers: bool
    uses_numbered_list: bool
    greeting_type: Optional[str] = None  # "formal", "casual", "none"
    signoff_type: Optional[str] = None

    # Status
    status: Literal["success", "refused", "error", "timeout", "incomplete"]
    refusal_category: Optional[str] = None
    error_message: Optional[str] = None

    # API metadata
    openrouter_request_id: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cost_usd: float

    timestamp: datetime
```

### 2.3 Judgment Schema

```python
class JudgmentVote(BaseModel):
    """Single judgment vote"""
    vote_id: str
    comparison_id: str
    judge_model: str
    judge_persona: Literal["writing_expert", "recipient"]
    vote_number: int  # 1-5 for best-of-5

    # Ordering (for bias detection)
    response_a_model: str
    response_b_model: str
    position_a_was_gemini: bool

    # Judgment
    winner: Literal["A", "B", "tie"]
    winner_model: Optional[str] = None

    # Criteria scores (optional detailed breakdown)
    quality_score_a: Optional[int] = Field(None, ge=1, le=5)
    quality_score_b: Optional[int] = Field(None, ge=1, le=5)
    tone_score_a: Optional[int] = Field(None, ge=1, le=5)
    tone_score_b: Optional[int] = Field(None, ge=1, le=5)
    length_appropriateness_a: Optional[int] = Field(None, ge=1, le=5)
    length_appropriateness_b: Optional[int] = Field(None, ge=1, le=5)
    authenticity_score_a: Optional[int] = Field(None, ge=1, le=5)
    authenticity_score_b: Optional[int] = Field(None, ge=1, le=5)
    task_completion_a: Optional[int] = Field(None, ge=1, le=5)
    task_completion_b: Optional[int] = Field(None, ge=1, le=5)

    # Instruction compliance (if applicable)
    constraint_compliance_a: Optional[dict] = None
    constraint_compliance_b: Optional[dict] = None

    # Reasoning
    reasoning: str

    # Metadata
    judge_response_time_ms: int
    judge_tokens_used: int
    timestamp: datetime

class ComparisonResult(BaseModel):
    """Aggregated comparison result"""
    comparison_id: str
    prompt_id: str
    gemini_model: str
    competitor_model: str

    # Individual judge results
    votes: list[JudgmentVote]

    # Per-judge majority
    claude_opus_majority: Optional[Literal["gemini", "competitor", "tie"]] = None
    gpt52_majority: Optional[Literal["gemini", "competitor", "tie"]] = None
    gemini_judge_majority: Optional[Literal["gemini", "competitor", "tie"]] = None

    # Final result (majority of majorities)
    final_winner: Literal["gemini", "competitor", "tie"]
    judge_agreement_count: int  # How many judges agreed on winner

    # Auto-loss handling
    gemini_auto_loss: bool = False
    competitor_auto_loss: bool = False
    auto_loss_reason: Optional[str] = None

    timestamp: datetime
```

---

## Part 3: Prompt Generation Pipeline

### 3.1 Three-Phase Generation Architecture

The prompt generation pipeline implements the three-phase approach specified in PROMPT.md:

#### Phase 1: Offline LLM Generation
- Use evaluated models to generate diverse persona/context variations
- Pre-generate a large pool of enrichment templates
- Store as reusable templates for Phase 3

#### Phase 2: Algorithmic Combinations
- Extract writing-relevant tasks from O*NET
- Combine with randomized dimensions programmatically
- Ensure deterministic reproducibility via seeded random

#### Phase 3: LLM Enrichment
- Further enrich complex prompts requiring additional context
- Add realistic details, attachments, prior messages
- Use model ensemble to avoid bias

### 3.2 O*NET Task Extraction

```python
class ONetLoader:
    """Load and filter writing-relevant tasks from O*NET database"""

    WRITING_CATEGORIES = {
        "explicit_writing": [
            "%write%", "%draft%", "%document%", "%compose%", "%author%"
        ],
        "correspondence": [
            "%correspond%", "%email%", "%letter%", "%memo%"
        ],
        "reports": [
            "%report%", "%present%finding%", "%summarize%"
        ],
        "proposals": [
            "%propos%", "%negotiat%", "%recommend%"
        ],
        "policy": [
            "%develop%polic%", "%procedure%", "%guideline%"
        ],
        "customer_communication": [
            "%customer%", "%client%", "%resolve%complaint%"
        ],
        "training": [
            "%train%", "%instruct%", "%curriculum%"
        ],
        "coordination": [
            "%confer with%", "%coordinate with%", "%collaborate%"
        ],
        "contracts": [
            "%contract%", "%agreement%", "%compliance%"
        ],
        "feedback": [
            "%evaluat%performance%", "%feedback%", "%review%recommend%"
        ]
    }

    async def extract_writing_tasks(self) -> list[ONetTask]:
        """Extract all writing-relevant tasks with occupation context"""
        # Build dynamic query from categories
        # Join with occupation_data, job_zones
        # Return enriched task list
        pass

    async def get_occupation_context(self, soc_code: str) -> OccupationContext:
        """Get full occupation context including work_context scores"""
        pass
```

### 3.3 NAICS Industry Mapping

Since O*NET doesn't contain NAICS codes directly, we implement a mapping layer:

```python
class NAICSMapper:
    """Map occupations to industries using BLS crosswalk and heuristics"""

    # 20 NAICS sectors for sampling
    NAICS_SECTORS = {
        "11": "Agriculture, Forestry, Fishing and Hunting",
        "21": "Mining, Quarrying, and Oil and Gas Extraction",
        "22": "Utilities",
        "23": "Construction",
        "31-33": "Manufacturing",
        "42": "Wholesale Trade",
        "44-45": "Retail Trade",
        "48-49": "Transportation and Warehousing",
        "51": "Information",
        "52": "Finance and Insurance",
        "53": "Real Estate and Rental and Leasing",
        "54": "Professional, Scientific, and Technical Services",
        "55": "Management of Companies and Enterprises",
        "56": "Administrative and Support Services",
        "61": "Educational Services",
        "62": "Health Care and Social Assistance",
        "71": "Arts, Entertainment, and Recreation",
        "72": "Accommodation and Food Services",
        "81": "Other Services",
        "92": "Public Administration"
    }

    def get_plausible_industries(self, soc_code: str) -> list[str]:
        """Return plausible NAICS codes for an occupation"""
        # Use built-in knowledge to map occupations to industries
        # Most occupations can exist in multiple industries
        pass

    def sample_industry(self, soc_code: str, seed: int) -> str:
        """Sample a single industry for this occupation"""
        pass
```

### 3.4 Company Database

```python
class CompanyDatabase:
    """Database of real companies for realistic grounding"""

    def __init__(self):
        # Built-in knowledge of companies by industry and size
        self.companies = self._initialize_company_database()

    def _initialize_company_database(self) -> dict:
        """Initialize with real companies across all industries and sizes"""
        # Structure: {naics_code: {size_category: [Company, ...]}}
        # Include Fortune 500, mid-market, small business, startups
        # Store metadata: size, age, public/private, HQ location
        pass

    def get_company(
        self,
        naics_code: str,
        size_category: Optional[str] = None,
        seed: int = None
    ) -> Company:
        """Get a real company for the given industry and size"""
        pass

    def get_random_company(self, seed: int) -> Company:
        """Get a random company across all industries"""
        pass
```

### 3.5 Name Generator

```python
class NameGenerator:
    """Generate demographically diverse realistic names"""

    def __init__(self):
        # Name pools stratified by:
        # - Apparent ethnicity/cultural background
        # - Generation (for age-appropriate names)
        # - Gender
        self.name_pools = self._initialize_name_pools()

    def generate_persona(
        self,
        role: str,
        generation: Optional[str] = None,  # GenZ, Millennial, GenX, Boomer
        formality_level: int = 3,
        seed: int = None
    ) -> Persona:
        """Generate a complete persona with appropriate name"""
        # Match name formality to context
        # Generate realistic email address
        # Include appropriate skill level
        pass

    def format_name(
        self,
        first_name: str,
        last_name: str,
        formality: Literal["very_formal", "formal", "neutral", "casual", "very_casual"]
    ) -> str:
        """Format name appropriately: 'Dr. Williams', 'Mike', 'Michael T. Williams'"""
        pass
```

### 3.6 Stratified Sampling

```python
class PromptSampler:
    """Stratified sampling across all diversity dimensions"""

    def __init__(self, config: SamplingConfig):
        self.config = config
        self.rng = random.Random(config.seed)

    def sample_prompts(
        self,
        tasks: list[ONetTask],
        n_prompts: int
    ) -> list[WritingPrompt]:
        """Sample prompts with stratification across dimensions"""

        # Stratification dimensions:
        # 1. Job zones (1-5) - skill level diversity
        # 2. SOC major groups (22 groups) - occupation diversity
        # 3. NAICS sectors (20 sectors) - industry diversity
        # 4. Writing categories (10 categories) - task type diversity
        # 5. Formality levels (1-5)
        # 6. Age/generation (4-5 groups)
        # 7. Channel types (email, memo, report, etc.)

        # Algorithm:
        # 1. Calculate target counts per stratum
        # 2. Sample proportionally or evenly based on config
        # 3. Fill remaining quota with random sampling
        # 4. Apply occupation/industry limits

        pass

    def _ensure_diversity(self, prompts: list[WritingPrompt]) -> list[WritingPrompt]:
        """Verify diversity requirements are met"""
        pass
```

### 3.7 LLM Enrichment Pipeline

```python
class PromptEnricher:
    """Phase 3 LLM enrichment for context-heavy prompts"""

    def __init__(self, api_client: OpenRouterClient):
        self.client = api_client
        # Use ensemble of evaluated models
        self.enrichment_models = [
            "google/gemini-3-pro",
            "openai/gpt-5.2",
            "anthropic/claude-opus"
        ]

    async def enrich_prompt(
        self,
        base_prompt: WritingPrompt,
        enrichment_type: str
    ) -> WritingPrompt:
        """Add LLM-generated context to a prompt"""

        enrichment_types = {
            "attachment": self._generate_attachment,
            "prior_message": self._generate_prior_message,
            "tone_example": self._generate_tone_example,
            "competing_objectives": self._generate_competing_objectives,
            "temporal_context": self._generate_temporal_context,
            "revision_text": self._generate_revision_text,
            "ambiguous_context": self._generate_ambiguous_context
        }

        return await enrichment_types[enrichment_type](base_prompt)

    async def _generate_attachment(self, prompt: WritingPrompt) -> WritingPrompt:
        """Generate realistic mock attachment content"""
        # e.g., Q3 report summary, meeting notes, resume
        pass

    async def _generate_prior_message(self, prompt: WritingPrompt) -> WritingPrompt:
        """Generate prior message for reply scenarios"""
        # e.g., angry customer email, vague request from boss
        pass

---

## Part 4: OpenRouter API Integration

### 4.1 OpenRouter Client Architecture

```python
class OpenRouterClient:
    """Async OpenRouter API client with robust error handling"""

    BASE_URL = "https://openrouter.ai/api/v1"

    # Model identifiers for OpenRouter
    MODELS = {
        # Pro-tier
        "gemini-pro": "google/gemini-3-pro",
        "gpt-5.2-thinking": "openai/gpt-5.2-thinking",
        "claude-opus": "anthropic/claude-opus-4.5",
        "grok-4.1-thinking": "x-ai/grok-4.1-thinking",
        "kimi-k2-thinking": "moonshot/kimi-k2-thinking",

        # Flash-tier
        "gemini-flash": "google/gemini-3-flash",
        "gpt-4.1": "openai/gpt-4.1",
        "claude-sonnet": "anthropic/claude-sonnet",

        # Judge models
        "judge-opus": "anthropic/claude-opus-4.5",
        "judge-gpt": "openai/gpt-5.2",
        "judge-gemini": "google/gemini-3-pro"
    }

    def __init__(
        self,
        api_key: str,
        rate_limiter: RateLimiter,
        retry_config: RetryConfig,
        circuit_breaker: CircuitBreaker
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.retry_config = retry_config
        self.circuit_breaker = circuit_breaker
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),  # 2 minute timeout
            limits=httpx.Limits(max_connections=50)
        )

    async def generate_response(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> ModelResponse:
        """Generate a model response with full error handling"""
        pass

    async def batch_generate(
        self,
        requests: list[GenerationRequest],
        concurrency: int = 10
    ) -> list[ModelResponse]:
        """Batch generation with concurrency control"""
        pass
```

### 4.2 Rate Limiter

```python
class RateLimiter:
    """Token bucket rate limiter with per-model limits"""

    def __init__(self, config: RateLimitConfig):
        # Different limits per model/provider
        self.limits = {
            "openai": TokenBucket(requests_per_min=60, tokens_per_min=150000),
            "anthropic": TokenBucket(requests_per_min=50, tokens_per_min=100000),
            "google": TokenBucket(requests_per_min=60, tokens_per_min=120000),
            "x-ai": TokenBucket(requests_per_min=30, tokens_per_min=60000),
            "moonshot": TokenBucket(requests_per_min=30, tokens_per_min=60000)
        }

    async def acquire(self, provider: str, tokens: int = 0) -> None:
        """Acquire rate limit permission, waiting if necessary"""
        bucket = self.limits[provider]
        await bucket.acquire(tokens)

    def get_wait_time(self, provider: str) -> float:
        """Get estimated wait time until next request can be made"""
        return self.limits[provider].get_wait_time()

class TokenBucket:
    """Token bucket implementation for rate limiting"""

    def __init__(self, requests_per_min: int, tokens_per_min: int):
        self.request_rate = requests_per_min / 60  # per second
        self.token_rate = tokens_per_min / 60
        self.request_tokens = requests_per_min
        self.token_tokens = tokens_per_min
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 0) -> None:
        """Acquire tokens, waiting if necessary"""
        async with self._lock:
            self._refill()
            while self.request_tokens < 1 or (tokens > 0 and self.token_tokens < tokens):
                wait_time = self._calculate_wait_time(tokens)
                await asyncio.sleep(wait_time)
                self._refill()
            self.request_tokens -= 1
            if tokens > 0:
                self.token_tokens -= tokens
```

### 4.3 Retry Handler with Exponential Backoff

```python
class RetryHandler:
    """Retry logic with exponential backoff and jitter"""

    def __init__(self, config: RetryConfig):
        self.max_retries = config.max_retries  # Default: 3
        self.base_delay = config.base_delay  # Default: 1.0 second
        self.max_delay = config.max_delay  # Default: 60.0 seconds
        self.exponential_base = config.exponential_base  # Default: 2.0
        self.jitter = config.jitter  # Default: 0.5 (50% jitter)

    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with retry logic"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except RetryableError as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except NonRetryableError:
                raise

        raise MaxRetriesExceeded(
            f"Max retries ({self.max_retries}) exceeded",
            last_exception
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        # Add jitter: delay * (1 - jitter/2) to delay * (1 + jitter/2)
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range / 2, jitter_range / 2)
        return max(0, delay)
```

### 4.4 Circuit Breaker

```python
class CircuitBreaker:
    """Circuit breaker pattern for API fault tolerance"""

    class State(Enum):
        CLOSED = "closed"  # Normal operation
        OPEN = "open"  # Failing, reject requests
        HALF_OPEN = "half_open"  # Testing if recovered

    def __init__(self, config: CircuitBreakerConfig):
        self.failure_threshold = config.failure_threshold  # Default: 5
        self.recovery_timeout = config.recovery_timeout  # Default: 30 seconds
        self.half_open_requests = config.half_open_requests  # Default: 3

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_successes = 0
        self._lock = asyncio.Lock()

    async def call(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation through circuit breaker"""
        async with self._lock:
            if self._state == self.State.OPEN:
                if self._should_attempt_reset():
                    self._state = self.State.HALF_OPEN
                    self._half_open_successes = 0
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker is open. "
                        f"Wait {self._time_until_reset():.1f}s"
                    )

        try:
            result = await operation(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call"""
        async with self._lock:
            if self._state == self.State.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_requests:
                    self._state = self.State.CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = self.State.OPEN
```

### 4.5 Cost Tracking

```python
class CostTracker:
    """Track and estimate API costs"""

    # OpenRouter pricing (per 1M tokens) - as of Jan 2026
    PRICING = {
        "google/gemini-3-pro": {"input": 2.50, "output": 7.50},
        "google/gemini-3-flash": {"input": 0.10, "output": 0.30},
        "openai/gpt-5.2-thinking": {"input": 5.00, "output": 15.00},
        "openai/gpt-4.1": {"input": 0.50, "output": 1.50},
        "anthropic/claude-opus-4.5": {"input": 3.00, "output": 15.00},
        "anthropic/claude-sonnet": {"input": 0.60, "output": 3.00},
        "x-ai/grok-4.1-thinking": {"input": 3.00, "output": 9.00},
        "moonshot/kimi-k2-thinking": {"input": 2.00, "output": 6.00}
    }

    def __init__(self):
        self.total_cost = 0.0
        self.cost_by_model = defaultdict(float)
        self.cost_by_phase = defaultdict(float)
        self._lock = asyncio.Lock()

    def estimate_run_cost(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost for an evaluation run"""

        # Response generation cost
        avg_input_tokens = 2000  # Average prompt length
        avg_output_tokens = 500  # Average response length

        generation_cost = 0.0
        for model_pair in config.model_pairs:
            for model in [model_pair.gemini, model_pair.competitor]:
                pricing = self.PRICING[model]
                cost = (
                    (avg_input_tokens / 1_000_000) * pricing["input"] +
                    (avg_output_tokens / 1_000_000) * pricing["output"]
                )
                generation_cost += cost * config.num_prompts

        # Judging cost
        avg_judge_input = 3000  # Prompt + both responses
        avg_judge_output = 300  # Judgment reasoning

        judging_cost = 0.0
        for judge_model in config.judge_models:
            pricing = self.PRICING[judge_model]
            cost = (
                (avg_judge_input / 1_000_000) * pricing["input"] +
                (avg_judge_output / 1_000_000) * pricing["output"]
            )
            # votes_per_judge * judge_personas * model_pairs * prompts
            num_judge_calls = (
                config.votes_per_judge *
                len(config.judge_personas) *
                len(config.model_pairs) *
                config.num_prompts
            )
            judging_cost += cost * num_judge_calls

        return CostEstimate(
            generation_cost_low=generation_cost * 0.8,
            generation_cost_high=generation_cost * 1.2,
            judging_cost_low=judging_cost * 0.8,
            judging_cost_high=judging_cost * 1.2,
            total_cost_low=(generation_cost + judging_cost) * 0.8,
            total_cost_high=(generation_cost + judging_cost) * 1.2
        )

    async def record_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        phase: str
    ) -> float:
        """Record actual cost for an API call"""
        pricing = self.PRICING[model]
        cost = (
            (input_tokens / 1_000_000) * pricing["input"] +
            (output_tokens / 1_000_000) * pricing["output"]
        )

        async with self._lock:
            self.total_cost += cost
            self.cost_by_model[model] += cost
            self.cost_by_phase[phase] += cost

        return cost
```

---

## Part 5: Evaluation Engine

### 5.1 Core Evaluation Orchestrator

```python
class EvaluationEngine:
    """Main orchestrator for the evaluation process"""

    def __init__(
        self,
        config: EvalConfig,
        api_client: OpenRouterClient,
        storage: StorageManager,
        tui: Optional[ProgressTUI] = None
    ):
        self.config = config
        self.api_client = api_client
        self.storage = storage
        self.tui = tui

        self.response_generator = ResponseGenerator(api_client)
        self.judge_orchestrator = JudgeOrchestrator(api_client, config)
        self.cost_tracker = CostTracker()
        self.checkpoint = CheckpointManager(storage)

    async def run_evaluation(self) -> EvaluationResult:
        """Run complete evaluation pipeline"""

        # Phase 1: Generate prompts (or load from checkpoint)
        prompts = await self._get_or_generate_prompts()

        # Phase 2: Generate responses
        for model_pair in self.config.model_pairs:
            await self._generate_responses_for_pair(prompts, model_pair)

        # Phase 3: Run judging
        for model_pair in self.config.model_pairs:
            await self._judge_pair(prompts, model_pair)

        # Phase 4: Aggregate results
        results = await self._aggregate_results()

        return results

    async def _generate_responses_for_pair(
        self,
        prompts: list[WritingPrompt],
        model_pair: ModelPair
    ) -> None:
        """Generate responses for both models in a pair"""

        incomplete_prompts = await self.checkpoint.get_incomplete_prompts(
            model_pair, "generation"
        )

        async for prompt in self._batch_iterate(incomplete_prompts):
            # Generate both responses concurrently
            gemini_response, competitor_response = await asyncio.gather(
                self.response_generator.generate(
                    model_pair.gemini, prompt
                ),
                self.response_generator.generate(
                    model_pair.competitor, prompt
                )
            )

            # Store responses
            await self.storage.save_response(gemini_response)
            await self.storage.save_response(competitor_response)

            # Update checkpoint
            await self.checkpoint.mark_complete(
                prompt.prompt_id, model_pair, "generation"
            )

            # Update TUI
            if self.tui:
                await self.tui.update_progress(
                    phase="generation",
                    model_pair=model_pair,
                    completed=prompt.prompt_id
                )

    async def _judge_pair(
        self,
        prompts: list[WritingPrompt],
        model_pair: ModelPair
    ) -> None:
        """Run judging for a model pair"""

        incomplete_prompts = await self.checkpoint.get_incomplete_prompts(
            model_pair, "judging"
        )

        async for prompt in self._batch_iterate(incomplete_prompts):
            # Get responses
            gemini_response = await self.storage.get_response(
                prompt.prompt_id, model_pair.gemini
            )
            competitor_response = await self.storage.get_response(
                prompt.prompt_id, model_pair.competitor
            )

            # Handle auto-loss cases
            if gemini_response.status != "success":
                await self._record_auto_loss(
                    prompt, model_pair, winner="competitor",
                    reason=f"Gemini {gemini_response.status}"
                )
                continue

            if competitor_response.status != "success":
                await self._record_auto_loss(
                    prompt, model_pair, winner="gemini",
                    reason=f"Competitor {competitor_response.status}"
                )
                continue

            # Run judging
            comparison = await self.judge_orchestrator.judge_comparison(
                prompt, gemini_response, competitor_response, model_pair
            )

            # Store result
            await self.storage.save_comparison(comparison)

            # Update checkpoint
            await self.checkpoint.mark_complete(
                prompt.prompt_id, model_pair, "judging"
            )
```

### 5.2 Judge Orchestrator

```python
class JudgeOrchestrator:
    """Orchestrates multi-model, multi-persona judging"""

    JUDGE_MODELS = [
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2",
        "google/gemini-3-pro"
    ]

    JUDGE_PERSONAS = ["writing_expert", "recipient"]

    def __init__(self, api_client: OpenRouterClient, config: EvalConfig):
        self.api_client = api_client
        self.config = config
        self.rubric = EvaluationRubric()

    async def judge_comparison(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        model_pair: ModelPair
    ) -> ComparisonResult:
        """Run full judging process for a comparison"""

        # Determine response ordering (shuffle for bias mitigation)
        ordering = self._get_ordering(prompt.prompt_id, model_pair)

        if ordering.gemini_is_a:
            display_a, display_b = response_a, response_b
        else:
            display_a, display_b = response_b, response_a

        # Collect all votes
        all_votes = []

        for judge_model in self.config.judge_models:
            for persona in self.config.judge_personas:
                # Get best-of-N votes
                votes = await self._get_votes(
                    judge_model=judge_model,
                    persona=persona,
                    prompt=prompt,
                    response_a=display_a,
                    response_b=display_b,
                    n_votes=self.config.votes_per_judge,
                    ordering=ordering
                )
                all_votes.extend(votes)

        # Aggregate votes
        return self._aggregate_votes(all_votes, model_pair, prompt)

    async def _get_votes(
        self,
        judge_model: str,
        persona: str,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        n_votes: int,
        ordering: Ordering
    ) -> list[JudgmentVote]:
        """Get N votes from a single judge/persona combination"""

        judge_prompt = self._build_judge_prompt(
            persona=persona,
            writing_prompt=prompt,
            response_a=response_a.response_text,
            response_b=response_b.response_text
        )

        votes = []
        for vote_num in range(n_votes):
            response = await self.api_client.generate_response(
                model=judge_model,
                prompt=judge_prompt,
                temperature=0.7  # Some variation for independence
            )

            vote = self._parse_judgment(
                response=response,
                judge_model=judge_model,
                persona=persona,
                vote_number=vote_num + 1,
                ordering=ordering
            )
            votes.append(vote)

        return votes

    def _build_judge_prompt(
        self,
        persona: str,
        writing_prompt: WritingPrompt,
        response_a: str,
        response_b: str
    ) -> str:
        """Build the judge prompt with full context"""

        if persona == "writing_expert":
            persona_instruction = self.rubric.WRITING_EXPERT_PERSONA
        else:
            # Build recipient persona based on prompt context
            persona_instruction = self._build_recipient_persona(writing_prompt)

        return f"""
{persona_instruction}

## Writing Task Context

**Occupation**: {writing_prompt.occupation_title}
**Industry**: {writing_prompt.company.industry_name}
**Company**: {writing_prompt.company.name} ({writing_prompt.company.size_category})

**Writer**: {writing_prompt.writer.name}, {writing_prompt.writer.role}
{f"Age Range: {writing_prompt.writer.age_range}" if writing_prompt.writer.age_range else ""}
{f"Generation: {writing_prompt.writer.generation}" if writing_prompt.writer.generation else ""}

**Recipient(s)**: {', '.join([f"{r.name} ({r.role})" for r in writing_prompt.recipients])}

**Communication Context**:
- Channel: {writing_prompt.channel.value}
- Formality Level: {writing_prompt.formality_level}/5
- Urgency: {writing_prompt.urgency_level}/5
- Relationship: {writing_prompt.relationship_context}
- Audience Size: {writing_prompt.audience_size}

{f"**Temporal Context**: {writing_prompt.temporal_context}" if writing_prompt.temporal_context else ""}
{f"**Emotional Context**: {writing_prompt.emotional_context}" if writing_prompt.emotional_context else ""}

## The Writing Task

{writing_prompt.enriched_prompt}

{self._format_attachments(writing_prompt)}
{self._format_prior_message(writing_prompt)}
{self._format_constraints(writing_prompt)}

## Response A

{response_a}

## Response B

{response_b}

## Your Evaluation

{self.rubric.EVALUATION_CRITERIA}

{self.rubric.OUTPUT_FORMAT}
"""

    def _get_ordering(self, prompt_id: str, model_pair: ModelPair) -> Ordering:
        """Get deterministic but shuffled ordering"""
        # Use hash of prompt_id + model_pair for deterministic shuffle
        seed = hash(f"{prompt_id}_{model_pair.gemini}_{model_pair.competitor}")
        rng = random.Random(seed)
        gemini_is_a = rng.choice([True, False])
        return Ordering(gemini_is_a=gemini_is_a)

    def _aggregate_votes(
        self,
        votes: list[JudgmentVote],
        model_pair: ModelPair,
        prompt: WritingPrompt
    ) -> ComparisonResult:
        """Aggregate votes using majority-of-majorities"""

        # Group by judge model
        by_judge = defaultdict(list)
        for vote in votes:
            by_judge[vote.judge_model].append(vote)

        # Get majority for each judge
        judge_majorities = {}
        for judge_model, judge_votes in by_judge.items():
            gemini_wins = sum(1 for v in judge_votes if v.winner_model == model_pair.gemini)
            competitor_wins = sum(1 for v in judge_votes if v.winner_model == model_pair.competitor)
            ties = sum(1 for v in judge_votes if v.winner == "tie")

            if gemini_wins > competitor_wins and gemini_wins > ties:
                judge_majorities[judge_model] = "gemini"
            elif competitor_wins > gemini_wins and competitor_wins > ties:
                judge_majorities[judge_model] = "competitor"
            else:
                judge_majorities[judge_model] = "tie"

        # Majority of majorities
        final_counts = Counter(judge_majorities.values())
        if final_counts["gemini"] > final_counts["competitor"]:
            final_winner = "gemini"
        elif final_counts["competitor"] > final_counts["gemini"]:
            final_winner = "competitor"
        else:
            final_winner = "tie"

        return ComparisonResult(
            comparison_id=f"{prompt.prompt_id}_{model_pair.gemini}_{model_pair.competitor}",
            prompt_id=prompt.prompt_id,
            gemini_model=model_pair.gemini,
            competitor_model=model_pair.competitor,
            votes=votes,
            claude_opus_majority=judge_majorities.get("anthropic/claude-opus-4.5"),
            gpt52_majority=judge_majorities.get("openai/gpt-5.2"),
            gemini_judge_majority=judge_majorities.get("google/gemini-3-pro"),
            final_winner=final_winner,
            judge_agreement_count=max(final_counts.values()),
            timestamp=datetime.utcnow()
        )
```

### 5.3 Evaluation Rubric

```python
class EvaluationRubric:
    """Evaluation criteria and judge instructions"""

    WRITING_EXPERT_PERSONA = """
You are a professional writing expert and communications specialist with 20+ years
of experience across corporate, technical, and creative writing. You have worked
as a senior editor, corporate communications director, and writing coach.

Your role is to evaluate the quality of two writing samples for the same task,
judging them on the craft of writing itself: clarity, structure, tone,
professionalism, and effectiveness.

You value:
- Clear, concise communication that respects the reader's time
- Appropriate tone and register for the context
- Strong structure and logical flow
- Natural, authentic voice (not robotic or generic)
- Absence of cliches and AI-typical patterns
- Correct grammar, spelling, and punctuation
"""

    EVALUATION_CRITERIA = """
Evaluate both responses on these criteria:

1. **Writing Quality** (clarity, grammar, structure, flow)
2. **Tone Appropriateness** (matches formality level, audience, and context)
3. **Length Appropriateness** (right length for this specific task - not too long, not too short)
4. **Task Completion** (fully addresses all aspects of the request)
5. **Authenticity** (reads like natural human writing, not generic AI output)
6. **Cliche Avoidance** (avoids "I hope this email finds you well", "Please don't hesitate to reach out", excessive bullet points, etc.)
7. **Effectiveness** (would achieve its intended purpose)

For reply/revision tasks, also consider:
- Context awareness (appropriately references prior communication)
- Tone matching (consistent with established patterns if provided)

For tasks with explicit constraints, also consider:
- Constraint compliance (followed word limits, format requirements, etc.)
"""

    OUTPUT_FORMAT = """
Provide your evaluation in this format:

### Analysis

**Response A Strengths:**
[List 2-3 specific strengths]

**Response A Weaknesses:**
[List any weaknesses]

**Response B Strengths:**
[List 2-3 specific strengths]

**Response B Weaknesses:**
[List any weaknesses]

### Scores (1-5 scale)

| Criterion | Response A | Response B |
|-----------|------------|------------|
| Writing Quality | X | X |
| Tone Appropriateness | X | X |
| Length Appropriateness | X | X |
| Task Completion | X | X |
| Authenticity | X | X |
| Cliche Avoidance | X | X |
| Effectiveness | X | X |

### Verdict

**Winner: [A / B / Tie]**

**Reasoning:** [2-3 sentences explaining your decision]
"""

    def build_recipient_persona(self, prompt: WritingPrompt) -> str:
        """Build a recipient persona based on the prompt context"""
        recipient = prompt.recipients[0] if prompt.recipients else None

        if not recipient:
            return self._generic_recipient_persona()

        return f"""
You are {recipient.name}, {recipient.role} at {prompt.company.name}.
{f"You are in the {recipient.age_range} age range." if recipient.age_range else ""}
{f"You belong to the {recipient.generation} generation." if recipient.generation else ""}

You are reading two versions of a message intended for you. Evaluate them from
your perspective as the recipient:

- Does it respect your time and get to the point?
- Is it appropriately professional for your relationship with the writer?
- Would you respond positively or feel annoyed/confused?
- Does it seem authentic or like generic template text?
- Does it give you what you need to take action?
"""
```

---

## Part 6: Data Storage and Checkpointing

### 6.1 SQLite Database Schema

```sql
-- Core tables for evaluation data

CREATE TABLE IF NOT EXISTS eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    config JSON NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    random_seed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    onet_task_id TEXT NOT NULL,
    onet_soc_code TEXT NOT NULL,
    occupation_title TEXT NOT NULL,
    job_zone INTEGER NOT NULL,
    task_statement TEXT NOT NULL,
    enriched_prompt TEXT NOT NULL,
    company_json JSON NOT NULL,
    writer_json JSON NOT NULL,
    recipients_json JSON NOT NULL,
    channel TEXT NOT NULL,
    formality_level INTEGER NOT NULL,
    urgency_level INTEGER NOT NULL,
    writing_category TEXT NOT NULL,
    sensitive_category TEXT,
    is_revision_task BOOLEAN DEFAULT FALSE,
    deliberate_ambiguity BOOLEAN DEFAULT FALSE,
    explicit_constraints_json JSON,
    metadata_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model_id TEXT NOT NULL,
    response_text TEXT NOT NULL,
    response_length_chars INTEGER NOT NULL,
    response_length_words INTEGER NOT NULL,
    response_length_tokens INTEGER NOT NULL,
    response_time_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    refusal_category TEXT,
    error_message TEXT,
    format_metadata_json JSON,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_id)
);

CREATE TABLE IF NOT EXISTS judgments (
    vote_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    judge_model TEXT NOT NULL,
    judge_persona TEXT NOT NULL,
    vote_number INTEGER NOT NULL,
    response_a_model TEXT NOT NULL,
    response_b_model TEXT NOT NULL,
    position_a_was_gemini BOOLEAN NOT NULL,
    winner TEXT NOT NULL,
    winner_model TEXT,
    scores_json JSON,
    reasoning TEXT NOT NULL,
    judge_response_time_ms INTEGER NOT NULL,
    judge_tokens_used INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    claude_opus_majority TEXT,
    gpt52_majority TEXT,
    gemini_judge_majority TEXT,
    final_winner TEXT NOT NULL,
    judge_agreement_count INTEGER NOT NULL,
    gemini_auto_loss BOOLEAN DEFAULT FALSE,
    competitor_auto_loss BOOLEAN DEFAULT FALSE,
    auto_loss_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, gemini_model, competitor_model)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    phase TEXT NOT NULL,
    model_pair TEXT,
    last_completed_prompt TEXT,
    completed_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onet_soc_code);
CREATE INDEX idx_prompts_category ON prompts(writing_category);
CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model_id);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
CREATE INDEX idx_comparisons_prompt ON comparisons(prompt_id);
CREATE INDEX idx_comparisons_winner ON comparisons(final_winner);
```

### 6.2 Checkpoint Manager

```python
class CheckpointManager:
    """Manages checkpointing for resumable evaluations"""

    def __init__(self, storage: StorageManager):
        self.storage = storage

    async def save_checkpoint(
        self,
        run_id: str,
        phase: str,
        model_pair: Optional[ModelPair],
        last_completed: str,
        completed_count: int,
        total_count: int
    ) -> None:
        """Save checkpoint state"""
        await self.storage.execute("""
            INSERT OR REPLACE INTO checkpoints
            (run_id, phase, model_pair, last_completed_prompt,
             completed_count, total_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            run_id, phase,
            f"{model_pair.gemini}:{model_pair.competitor}" if model_pair else None,
            last_completed, completed_count, total_count
        ))

    async def get_checkpoint(
        self,
        run_id: str,
        phase: str,
        model_pair: Optional[ModelPair] = None
    ) -> Optional[Checkpoint]:
        """Get checkpoint for resume"""
        model_pair_str = f"{model_pair.gemini}:{model_pair.competitor}" if model_pair else None

        result = await self.storage.fetch_one("""
            SELECT * FROM checkpoints
            WHERE run_id = ? AND phase = ?
            AND (model_pair = ? OR (model_pair IS NULL AND ? IS NULL))
        """, (run_id, phase, model_pair_str, model_pair_str))

        if result:
            return Checkpoint(**result)
        return None

    async def get_incomplete_prompts(
        self,
        run_id: str,
        model_pair: ModelPair,
        phase: str
    ) -> list[str]:
        """Get prompt IDs that haven't been completed"""
        if phase == "generation":
            # Prompts without responses for both models
            completed = await self.storage.fetch_all("""
                SELECT DISTINCT p.prompt_id
                FROM prompts p
                JOIN responses r1 ON p.prompt_id = r1.prompt_id AND r1.model_id = ?
                JOIN responses r2 ON p.prompt_id = r2.prompt_id AND r2.model_id = ?
                WHERE p.run_id = ?
            """, (model_pair.gemini, model_pair.competitor, run_id))
        else:  # judging
            # Prompts without comparison results
            completed = await self.storage.fetch_all("""
                SELECT DISTINCT prompt_id
                FROM comparisons
                WHERE gemini_model = ? AND competitor_model = ?
            """, (model_pair.gemini, model_pair.competitor))

        completed_ids = {r['prompt_id'] for r in completed}

        all_prompts = await self.storage.fetch_all("""
            SELECT prompt_id FROM prompts WHERE run_id = ?
        """, (run_id,))

        return [p['prompt_id'] for p in all_prompts if p['prompt_id'] not in completed_ids]

    async def can_resume(self, run_dir: Path) -> bool:
        """Check if a run directory can be resumed"""
        checkpoint_file = run_dir / "checkpoint.json"
        db_file = run_dir / "results.db"
        return checkpoint_file.exists() and db_file.exists()
```

### 6.3 Results Directory Structure

```python
class ResultsManager:
    """Manages results directory structure"""

    def __init__(self, base_dir: Path = Path("results")):
        self.base_dir = base_dir

    def create_run_directory(self, config: EvalConfig) -> Path:
        """Create a new timestamped run directory"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = self.base_dir / f"eval_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (run_dir / "prompts").mkdir()
        (run_dir / "prompts" / "by_occupation").mkdir()
        (run_dir / "prompts" / "by_industry").mkdir()
        (run_dir / "responses").mkdir()
        (run_dir / "responses" / "by_prompt").mkdir()
        (run_dir / "responses" / "by_model").mkdir()
        (run_dir / "judgments").mkdir()
        (run_dir / "judgments" / "raw").mkdir()
        (run_dir / "judgments" / "aggregated").mkdir()
        (run_dir / "analysis").mkdir()
        (run_dir / "reports").mkdir()
        (run_dir / "reports" / "charts").mkdir()
        (run_dir / "logs").mkdir()

        # Save config
        (run_dir / "config.json").write_text(config.model_dump_json(indent=2))

        # Save human-readable config summary
        (run_dir / "config_summary.txt").write_text(self._format_config_summary(config))

        # Save random seed
        (run_dir / "random_seed.txt").write_text(str(config.random_seed))

        # Update latest symlink
        latest_link = self.base_dir / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(run_dir.name)

        return run_dir
```

---

## Part 7: Terminal User Interface (TUI)

### 7.1 Progress Dashboard

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive

class EvalProgressApp(App):
    """Rich TUI for evaluation progress monitoring"""

    CSS = """
    #overall-progress { height: 5; }
    #model-pairs { height: 10; }
    #current-batch { height: 12; }
    #live-stats { height: 8; }
    #activity-log { height: 10; }
    #errors { height: 3; }

    .progress-container { padding: 1; border: solid green; }
    .stats-container { padding: 1; border: solid blue; }
    .log-container { padding: 1; border: solid yellow; }
    """

    BINDINGS = [
        ("q", "quit_safely", "Quit (saves checkpoint)"),
        ("p", "pause", "Pause"),
        ("d", "toggle_detail", "Detail view"),
        ("s", "show_stats", "Full statistics"),
        ("h", "show_help", "Help"),
    ]

    # Reactive state
    current_phase = reactive("generation")
    prompts_completed = reactive(0)
    total_prompts = reactive(0)
    elapsed_time = reactive(0.0)
    estimated_total = reactive(0.0)
    current_cost = reactive(0.0)

    def __init__(self, config: EvalConfig, engine: EvaluationEngine):
        super().__init__()
        self.config = config
        self.engine = engine
        self.model_pair_progress = {}

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main"):
            # Overall progress section
            with Container(id="overall-progress", classes="progress-container"):
                yield Static("OVERALL PROGRESS", classes="section-title")
                yield ProgressBar(id="main-progress")
                yield Static(id="phase-indicator")

            # Model pairs progress
            with Container(id="model-pairs", classes="progress-container"):
                yield Static("MODEL PAIRS", classes="section-title")
                yield DataTable(id="pairs-table")

            # Current batch details
            with Horizontal(id="current-batch"):
                with Container(classes="progress-container"):
                    yield Static("CURRENT PROMPT", classes="section-title")
                    yield Static(id="current-prompt-info")
                with Container(classes="progress-container"):
                    yield Static("JUDGING PROGRESS", classes="section-title")
                    yield Static(id="judging-status")

            # Live statistics
            with Horizontal(id="live-stats"):
                with Container(classes="stats-container"):
                    yield Static("WIN RATES (Running)", classes="section-title")
                    yield Static(id="win-rates")
                with Container(classes="stats-container"):
                    yield Static("PERFORMANCE", classes="section-title")
                    yield Static(id="performance-stats")

            # Activity log
            with Container(id="activity-log", classes="log-container"):
                yield Static("RECENT ACTIVITY", classes="section-title")
                yield Log(id="activity")

            # Error summary
            with Container(id="errors"):
                yield Static(id="error-summary")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the UI"""
        # Set up model pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate", "Status")

        for pair in self.config.model_pairs:
            table.add_row(
                f"Gemini vs {pair.competitor}",
                "0/0",
                "--",
                "Pending"
            )

    async def update_progress(
        self,
        phase: str,
        model_pair: ModelPair,
        completed: str,
        win_rate: Optional[float] = None
    ) -> None:
        """Update progress display"""
        self.current_phase = phase
        self.prompts_completed += 1

        # Update progress bar
        progress = self.query_one("#main-progress", ProgressBar)
        progress.progress = self.prompts_completed / self.total_prompts

        # Update model pair table
        # ... (table update logic)

        # Log activity
        log = self.query_one("#activity", Log)
        log.write_line(f"Completed {completed}: {phase}")

    def action_quit_safely(self) -> None:
        """Quit with checkpoint save"""
        self.engine.request_stop()
        self.exit()

    def action_pause(self) -> None:
        """Toggle pause state"""
        self.engine.toggle_pause()
```

### 7.2 Results Viewer TUI

```python
class ResultsViewerApp(App):
    """TUI for browsing and inspecting evaluation results"""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("s", "sort", "Sort"),
        ("enter", "view_detail", "View Detail"),
        ("/", "search", "Search"),
    ]

    def __init__(self, run_dir: Path):
        super().__init__()
        self.run_dir = run_dir
        self.storage = StorageManager(run_dir / "results.db")
        self.current_filters = {}
        self.current_sort = "prompt_id"

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            # Filters sidebar
            with Container(id="filters", classes="sidebar"):
                yield Static("FILTERS", classes="section-title")
                yield FilterPanel(id="filter-panel")

            # Main content
            with Container(id="main-content"):
                # Summary stats
                with Container(id="summary"):
                    yield Static(id="summary-stats")

                # Results table
                yield DataTable(id="results-table")

                # Detail panel (hidden by default)
                with Container(id="detail-panel", classes="hidden"):
                    yield Static(id="prompt-detail")
                    yield Horizontal(
                        Container(Static(id="response-a"), id="response-a-container"),
                        Container(Static(id="response-b"), id="response-b-container"),
                    )
                    yield Static(id="judgment-detail")

        yield Footer()

    async def load_results(self) -> None:
        """Load results with current filters"""
        query = self._build_query()
        results = await self.storage.fetch_all(query, self.current_filters)

        table = self.query_one("#results-table", DataTable)
        table.clear()

        for result in results:
            table.add_row(
                result['prompt_id'][:8],
                result['occupation_title'][:30],
                result['writing_category'],
                result['final_winner'],
                f"{result['judge_agreement_count']}/3"
            )

    def action_view_detail(self) -> None:
        """Show detailed view of selected comparison"""
        table = self.query_one("#results-table", DataTable)
        row_key = table.cursor_row

        if row_key is not None:
            prompt_id = table.get_row_at(row_key)[0]
            self._show_detail(prompt_id)

    def _show_detail(self, prompt_id: str) -> None:
        """Display detailed comparison view"""
        # Load full prompt, responses, and judgments
        # Display side-by-side with full context
        pass
```

---

## Part 8: Statistical Analysis and Reporting

### 8.1 Statistical Analysis Module

```python
class StatisticalAnalyzer:
    """Comprehensive statistical analysis of evaluation results"""

    def __init__(self, storage: StorageManager):
        self.storage = storage

    async def compute_win_rates(
        self,
        model_pair: Optional[ModelPair] = None
    ) -> dict[str, WinRateResult]:
        """Compute win rates with confidence intervals"""

        if model_pair:
            comparisons = await self.storage.fetch_all("""
                SELECT * FROM comparisons
                WHERE gemini_model = ? AND competitor_model = ?
            """, (model_pair.gemini, model_pair.competitor))
        else:
            comparisons = await self.storage.fetch_all("""
                SELECT * FROM comparisons
            """)

        # Group by model pair
        by_pair = defaultdict(list)
        for c in comparisons:
            pair_key = f"{c['gemini_model']}_vs_{c['competitor_model']}"
            by_pair[pair_key].append(c)

        results = {}
        for pair_key, pair_comparisons in by_pair.items():
            n = len(pair_comparisons)
            gemini_wins = sum(1 for c in pair_comparisons if c['final_winner'] == 'gemini')
            ties = sum(1 for c in pair_comparisons if c['final_winner'] == 'tie')

            win_rate = gemini_wins / n if n > 0 else 0
            win_rate_excluding_ties = gemini_wins / (n - ties) if (n - ties) > 0 else 0

            # Wilson score confidence interval
            ci_lower, ci_upper = self._wilson_ci(gemini_wins, n, confidence=0.95)

            results[pair_key] = WinRateResult(
                pair_key=pair_key,
                total_comparisons=n,
                gemini_wins=gemini_wins,
                competitor_wins=n - gemini_wins - ties,
                ties=ties,
                win_rate=win_rate,
                win_rate_excluding_ties=win_rate_excluding_ties,
                ci_lower=ci_lower,
                ci_upper=ci_upper
            )

        return results

    def _wilson_ci(
        self,
        successes: int,
        n: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Wilson score confidence interval for proportions"""
        from scipy import stats

        if n == 0:
            return (0.0, 1.0)

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = successes / n

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        margin = (z / denominator) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))

        return (max(0, center - margin), min(1, center + margin))

    async def compute_inter_rater_reliability(self) -> ReliabilityResult:
        """Compute Cohen's Kappa for inter-judge agreement"""

        judgments = await self.storage.fetch_all("""
            SELECT comparison_id, judge_model, winner
            FROM judgments
        """)

        # Build agreement matrix between each pair of judges
        judges = list(set(j['judge_model'] for j in judgments))

        if len(judges) < 2:
            return ReliabilityResult(kappa=None, message="Insufficient judges")

        # Group judgments by comparison
        by_comparison = defaultdict(dict)
        for j in judgments:
            by_comparison[j['comparison_id']][j['judge_model']] = j['winner']

        # Compute pairwise kappa
        kappas = []
        for i, judge_a in enumerate(judges):
            for judge_b in judges[i+1:]:
                # Get shared comparisons
                shared = []
                for comp_id, votes in by_comparison.items():
                    if judge_a in votes and judge_b in votes:
                        shared.append((votes[judge_a], votes[judge_b]))

                if len(shared) > 10:  # Minimum sample
                    kappa = self._cohens_kappa(shared)
                    kappas.append(kappa)

        avg_kappa = sum(kappas) / len(kappas) if kappas else None

        return ReliabilityResult(
            kappa=avg_kappa,
            pairwise_kappas=kappas,
            interpretation=self._interpret_kappa(avg_kappa)
        )

    def _cohens_kappa(self, pairs: list[tuple[str, str]]) -> float:
        """Compute Cohen's Kappa for a list of rating pairs"""
        from sklearn.metrics import cohen_kappa_score

        a_ratings = [p[0] for p in pairs]
        b_ratings = [p[1] for p in pairs]

        return cohen_kappa_score(a_ratings, b_ratings)

    def _interpret_kappa(self, kappa: Optional[float]) -> str:
        """Interpret kappa value"""
        if kappa is None:
            return "Insufficient data"
        if kappa < 0:
            return "Poor agreement (worse than chance)"
        if kappa < 0.20:
            return "Slight agreement"
        if kappa < 0.40:
            return "Fair agreement"
        if kappa < 0.60:
            return "Moderate agreement"
        if kappa < 0.80:
            return "Substantial agreement"
        return "Almost perfect agreement"

    async def compute_bias_analysis(self) -> BiasAnalysisResult:
        """Detect systematic biases in models and judges"""

        # Position bias: Do judges prefer A over B?
        position_bias = await self._analyze_position_bias()

        # Length bias: Do judges prefer longer/shorter?
        length_bias = await self._analyze_length_bias()

        # Model fingerprinting: Can judges identify models?
        fingerprint_risk = await self._analyze_fingerprinting()

        # Per-model response patterns
        model_patterns = await self._analyze_model_patterns()

        return BiasAnalysisResult(
            position_bias=position_bias,
            length_bias=length_bias,
            fingerprint_risk=fingerprint_risk,
            model_patterns=model_patterns
        )

    async def _analyze_position_bias(self) -> PositionBiasResult:
        """Check if judges prefer Response A or B"""
        judgments = await self.storage.fetch_all("""
            SELECT winner, position_a_was_gemini FROM judgments
        """)

        a_wins = sum(1 for j in judgments if j['winner'] == 'A')
        b_wins = sum(1 for j in judgments if j['winner'] == 'B')
        total = len(judgments)

        # Chi-squared test for position bias
        from scipy.stats import chisquare
        expected = total / 2
        chi2, p_value = chisquare([a_wins, b_wins], [expected, expected])

        return PositionBiasResult(
            a_win_rate=a_wins / total if total > 0 else 0,
            b_win_rate=b_wins / total if total > 0 else 0,
            chi_squared=chi2,
            p_value=p_value,
            significant=p_value < 0.05
        )

    async def identify_weaknesses(self) -> WeaknessAnalysisResult:
        """Identify specific areas where Gemini underperforms"""

        # Win rates by occupation
        by_occupation = await self._win_rates_by_dimension("onet_soc_code")

        # Win rates by writing category
        by_category = await self._win_rates_by_dimension("writing_category")

        # Win rates by job zone
        by_job_zone = await self._win_rates_by_dimension("job_zone")

        # Win rates by formality level
        by_formality = await self._win_rates_by_dimension("formality_level")

        # Win rates by sensitive category
        by_sensitive = await self._win_rates_by_dimension("sensitive_category")

        # Find statistically significant weak areas
        weak_areas = []
        for dim_name, dim_results in [
            ("occupation", by_occupation),
            ("category", by_category),
            ("job_zone", by_job_zone),
            ("formality", by_formality),
            ("sensitive", by_sensitive)
        ]:
            for value, result in dim_results.items():
                if result.win_rate < 0.45 and result.total_comparisons >= 20:
                    weak_areas.append(WeakArea(
                        dimension=dim_name,
                        value=value,
                        win_rate=result.win_rate,
                        sample_size=result.total_comparisons,
                        ci_lower=result.ci_lower,
                        ci_upper=result.ci_upper
                    ))

        # Sort by win rate (lowest first)
        weak_areas.sort(key=lambda x: x.win_rate)

        return WeaknessAnalysisResult(
            by_occupation=by_occupation,
            by_category=by_category,
            by_job_zone=by_job_zone,
            by_formality=by_formality,
            by_sensitive=by_sensitive,
            significant_weak_areas=weak_areas[:20]  # Top 20 weak areas
        )
```

### 8.2 PDF Report Generator

```python
class PDFReportGenerator:
    """Generate comprehensive PDF evaluation report"""

    def __init__(self, run_dir: Path, analyzer: StatisticalAnalyzer):
        self.run_dir = run_dir
        self.analyzer = analyzer
        self.charts_dir = run_dir / "reports" / "charts"

    async def generate_report(self) -> Path:
        """Generate complete PDF report"""

        # Gather all analysis data
        win_rates = await self.analyzer.compute_win_rates()
        reliability = await self.analyzer.compute_inter_rater_reliability()
        biases = await self.analyzer.compute_bias_analysis()
        weaknesses = await self.analyzer.identify_weaknesses()

        # Generate charts
        charts = await self._generate_charts(win_rates, weaknesses)

        # Build report sections
        sections = [
            self._build_executive_summary(win_rates, weaknesses),
            self._build_methodology_section(),
            self._build_overall_results(win_rates),
            self._build_win_rate_breakdown(win_rates, weaknesses),
            self._build_reliability_section(reliability),
            self._build_bias_analysis(biases),
            self._build_weakness_deep_dive(weaknesses),
            self._build_statistical_appendix(win_rates, reliability)
        ]

        # Render PDF
        output_path = self.run_dir / "reports" / "report.pdf"
        await self._render_pdf(sections, charts, output_path)

        return output_path

    def _build_executive_summary(
        self,
        win_rates: dict,
        weaknesses: WeaknessAnalysisResult
    ) -> ReportSection:
        """Build executive summary section"""

        # Overall win rate across all comparisons
        total_wins = sum(r.gemini_wins for r in win_rates.values())
        total_comparisons = sum(r.total_comparisons for r in win_rates.values())
        overall_win_rate = total_wins / total_comparisons if total_comparisons > 0 else 0

        # Key findings
        findings = []

        # Best/worst model comparisons
        sorted_pairs = sorted(win_rates.items(), key=lambda x: x[1].win_rate, reverse=True)
        best_pair = sorted_pairs[0] if sorted_pairs else None
        worst_pair = sorted_pairs[-1] if sorted_pairs else None

        if best_pair:
            findings.append(f"Strongest performance: vs {best_pair[0]} ({best_pair[1].win_rate:.1%})")
        if worst_pair:
            findings.append(f"Weakest performance: vs {worst_pair[0]} ({worst_pair[1].win_rate:.1%})")

        # Top weaknesses
        if weaknesses.significant_weak_areas:
            top_weak = weaknesses.significant_weak_areas[0]
            findings.append(
                f"Most significant weakness: {top_weak.dimension}={top_weak.value} "
                f"({top_weak.win_rate:.1%} win rate)"
            )

        return ReportSection(
            title="Executive Summary",
            content={
                "overall_win_rate": overall_win_rate,
                "total_comparisons": total_comparisons,
                "key_findings": findings,
                "recommendation_summary": self._generate_recommendations(weaknesses)
            }
        )

    async def _generate_charts(
        self,
        win_rates: dict,
        weaknesses: WeaknessAnalysisResult
    ) -> dict[str, Path]:
        """Generate all charts for the report"""
        import plotly.graph_objects as go
        import plotly.express as px

        charts = {}

        # Overall win rate bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=[pair for pair in win_rates.keys()],
                y=[r.win_rate for r in win_rates.values()],
                error_y=dict(
                    type='data',
                    symmetric=False,
                    array=[r.ci_upper - r.win_rate for r in win_rates.values()],
                    arrayminus=[r.win_rate - r.ci_lower for r in win_rates.values()]
                )
            )
        ])
        fig.add_hline(y=0.5, line_dash="dash", line_color="red")
        fig.update_layout(
            title="Gemini Win Rates by Model Comparison",
            yaxis_title="Win Rate",
            yaxis_range=[0, 1]
        )
        chart_path = self.charts_dir / "win_rates_overall.png"
        fig.write_image(str(chart_path))
        charts["overall_win_rates"] = chart_path

        # Win rates heatmap by occupation and category
        occupation_data = weaknesses.by_occupation
        category_data = weaknesses.by_category

        # Create heatmap matrix
        # ... (heatmap generation code)

        return charts

    def _generate_recommendations(
        self,
        weaknesses: WeaknessAnalysisResult
    ) -> list[str]:
        """Generate actionable recommendations based on weaknesses"""
        recommendations = []

        # Group weak areas by dimension
        by_dimension = defaultdict(list)
        for weak in weaknesses.significant_weak_areas:
            by_dimension[weak.dimension].append(weak)

        # Generate recommendations for each dimension
        if "category" in by_dimension:
            weak_categories = [w.value for w in by_dimension["category"][:3]]
            recommendations.append(
                f"Focus training on {', '.join(weak_categories)} writing tasks"
            )

        if "occupation" in by_dimension:
            weak_occupations = [w.value for w in by_dimension["occupation"][:3]]
            recommendations.append(
                f"Improve performance for {', '.join(weak_occupations)} occupations"
            )

        if "formality" in by_dimension:
            weak_formality = by_dimension["formality"][0]
            if weak_formality.value in [1, 2]:
                recommendations.append(
                    "Improve casual/informal writing tone capabilities"
                )
            elif weak_formality.value in [4, 5]:
                recommendations.append(
                    "Improve formal/professional writing capabilities"
                )

        return recommendations
```

---

## Part 9: CLI and Configuration

### 9.1 CLI Interface

```python
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(help="Gemini Writing Evaluation Framework")
console = Console()

@app.command()
def run(
    preset: int = typer.Option(None, "--preset", "-p", help="Use preset configuration (1-10)"),
    prompts: int = typer.Option(None, "--prompts", "-n", help="Number of prompts"),
    models: str = typer.Option(None, "--models", "-m", help="Comma-separated model pairs"),
    judges: str = typer.Option(None, "--judges", "-j", help="Comma-separated judge models"),
    votes: int = typer.Option(None, "--votes", "-v", help="Votes per judge"),
    occupations: str = typer.Option(None, "--occupations", help="Filter by occupation codes"),
    industries: str = typer.Option(None, "--industries", help="Filter by NAICS codes"),
    job_zones: str = typer.Option(None, "--job-zones", help="Filter by job zones (1-5)"),
    seed: int = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    output_dir: str = typer.Option("results", "--output", "-o", help="Output directory"),
):
    """Run a writing evaluation"""

    # Load base config
    if preset:
        config = PRESETS[preset].copy()
    else:
        config = EvalConfig()

    # Apply overrides
    if prompts:
        config.num_prompts = prompts
    if models:
        config.model_pairs = parse_model_pairs(models)
    if judges:
        config.judge_models = judges.split(",")
    if votes:
        config.votes_per_judge = votes
    if occupations:
        config.occupation_filter = occupations.split(",")
    if industries:
        config.industry_filter = industries.split(",")
    if job_zones:
        config.job_zone_filter = [int(z) for z in job_zones.split(",")]
    if seed:
        config.random_seed = seed

    # Show cost estimate
    cost_tracker = CostTracker()
    estimate = cost_tracker.estimate_run_cost(config)

    display_estimate(config, estimate)

    if dry_run:
        return

    # Confirm before running
    if not typer.confirm("Proceed with evaluation?"):
        raise typer.Abort()

    # Run evaluation
    asyncio.run(run_evaluation(config, output_dir))

@app.command()
def resume(
    run_dir: str = typer.Argument(..., help="Path to run directory to resume"),
):
    """Resume an interrupted evaluation"""
    run_path = Path(run_dir)

    if not CheckpointManager.can_resume(run_path):
        console.print("[red]Cannot resume: missing checkpoint or database[/red]")
        raise typer.Exit(1)

    config = EvalConfig.model_validate_json((run_path / "config.json").read_text())
    asyncio.run(run_evaluation(config, run_path, resume=True))

@app.command()
def view(
    run_dir: str = typer.Argument("results/latest", help="Path to run directory"),
):
    """Launch interactive results viewer"""
    run_path = Path(run_dir)
    if run_path.is_symlink():
        run_path = run_path.resolve()

    app = ResultsViewerApp(run_path)
    app.run()

@app.command()
def compare(
    run_dirs: list[str] = typer.Argument(..., help="Run directories to compare"),
):
    """Compare results across multiple runs"""
    # Load and compare results from multiple runs
    pass

@app.command()
def report(
    run_dir: str = typer.Argument("results/latest", help="Path to run directory"),
    output: str = typer.Option(None, "--output", "-o", help="Output path for report"),
):
    """Generate PDF report for a run"""
    run_path = Path(run_dir)
    if run_path.is_symlink():
        run_path = run_path.resolve()

    storage = StorageManager(run_path / "results.db")
    analyzer = StatisticalAnalyzer(storage)
    generator = PDFReportGenerator(run_path, analyzer)

    report_path = asyncio.run(generator.generate_report())
    console.print(f"[green]Report generated: {report_path}[/green]")

def display_estimate(config: EvalConfig, estimate: CostEstimate):
    """Display cost and time estimate"""
    table = Table(title="EVAL RUN ESTIMATE", box=box.ROUNDED)

    table.add_row("Prompts", str(config.num_prompts))
    table.add_row("Model pairs", f"{len(config.model_pairs)}")
    table.add_row("Total comparisons", f"{config.num_prompts * len(config.model_pairs)}")
    table.add_row("", "")
    table.add_row(
        "Judge config",
        f"{len(config.judge_models)} judges x {config.votes_per_judge} votes x "
        f"{len(config.judge_personas)} personas"
    )
    table.add_row(
        "Total judge calls",
        f"{config.num_prompts * len(config.model_pairs) * len(config.judge_models) * config.votes_per_judge * len(config.judge_personas):,}"
    )
    table.add_row("", "")
    table.add_row("ESTIMATED COST", "")
    table.add_row(
        "  Response generation",
        f"${estimate.generation_cost_low:.0f} - ${estimate.generation_cost_high:.0f}"
    )
    table.add_row(
        "  Judging",
        f"${estimate.judging_cost_low:.0f} - ${estimate.judging_cost_high:.0f}"
    )
    table.add_row(
        "  Total",
        f"[bold]${estimate.total_cost_low:.0f} - ${estimate.total_cost_high:.0f}[/bold]"
    )

    console.print(table)
```

### 9.2 Preset Configurations

```python
PRESETS = {
    1: EvalConfig(
        name="Sanity Check",
        num_prompts=5,
        model_pairs=[ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking")],
        judge_models=["anthropic/claude-opus-4.5"],
        votes_per_judge=1,
        judge_personas=["writing_expert"],
        estimated_cost=1,
        estimated_time_minutes=2,
        description="Does the system work?"
    ),

    2: EvalConfig(
        name="Smoke Test",
        num_prompts=20,
        model_pairs=[ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking")],
        judge_models=["anthropic/claude-opus-4.5"],
        votes_per_judge=3,
        judge_personas=["writing_expert"],
        estimated_cost=5,
        estimated_time_minutes=5,
        description="Quick functionality test"
    ),

    3: EvalConfig(
        name="Dev Iteration",
        num_prompts=50,
        model_pairs=[
            ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking"),
            ModelPair("google/gemini-3-pro", "anthropic/claude-opus-4.5")
        ],
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2"],
        votes_per_judge=3,
        judge_personas=["writing_expert", "recipient"],
        estimated_cost=25,
        estimated_time_minutes=15,
        description="Development/debugging"
    ),

    4: EvalConfig(
        name="Quick Sample",
        num_prompts=100,
        model_pairs=[
            ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking"),
            ModelPair("google/gemini-3-pro", "anthropic/claude-opus-4.5")
        ],
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2"],
        votes_per_judge=5,
        judge_personas=["writing_expert", "recipient"],
        estimated_cost=75,
        estimated_time_minutes=30,
        description="Fast directional signal"
    ),

    5: EvalConfig(
        name="Light Eval",
        num_prompts=200,
        model_pairs=[
            ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking"),
            ModelPair("google/gemini-3-pro", "anthropic/claude-opus-4.5"),
            ModelPair("google/gemini-3-pro", "x-ai/grok-4.1-thinking")
        ],
        judge_models=[
            "anthropic/claude-opus-4.5",
            "openai/gpt-5.2",
            "google/gemini-3-pro"
        ],
        votes_per_judge=3,
        judge_personas=["writing_expert", "recipient"],
        estimated_cost=150,
        estimated_time_minutes=60,
        description="Light but meaningful eval"
    ),

    6: EvalConfig(
        name="Standard Eval",
        num_prompts=500,
        model_pairs=[
            ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking"),
            ModelPair("google/gemini-3-pro", "anthropic/claude-opus-4.5"),
            ModelPair("google/gemini-3-pro", "x-ai/grok-4.1-thinking"),
            ModelPair("google/gemini-3-pro", "moonshot/kimi-k2-thinking")
        ],
        judge_models=[
            "anthropic/claude-opus-4.5",
            "openai/gpt-5.2",
            "google/gemini-3-pro"
        ],
        votes_per_judge=5,
        judge_personas=["writing_expert", "recipient"],
        estimated_cost=500,
        estimated_time_minutes=180,
        description="Standard evaluation run"
    ),

    7: EvalConfig(
        name="Thorough Eval",
        num_prompts=1000,
        # ... (same structure as preset 6 but with 1000 prompts)
        estimated_cost=1000,
        estimated_time_minutes=360,
        description="Thorough with good power"
    ),

    8: EvalConfig(
        name="Comprehensive",
        num_prompts=2000,
        # ... (all model pairs)
        estimated_cost=2500,
        estimated_time_minutes=720,
        description="High statistical power"
    ),

    9: EvalConfig(
        name="Deep Dive",
        num_prompts=5000,
        # ... (all model pairs)
        estimated_cost=6000,
        estimated_time_minutes=1440,
        description="Publication-grade"
    ),

    10: EvalConfig(
        name="Full Kaboodle",
        num_prompts=10000,
        # ... (all model pairs)
        estimated_cost=12000,
        estimated_time_minutes=2880,
        description="Maximum coverage"
    )
}
```

---

## Part 10: Implementation Phases and Testing

### 10.1 Implementation Phases

The implementation should proceed in the following phases:

#### Phase 1: Foundation (Week 1-2)

**Goals:** Establish core infrastructure and data access

1. **Project Setup**
   - Initialize Python project with pyproject.toml
   - Set up dependency management (Poetry or PDM)
   - Configure linting, formatting, type checking
   - Set up pytest with asyncio support

2. **O*NET Data Layer**
   - Implement ONetLoader for SQLite access
   - Define Pydantic models for O*NET data
   - Build SQL queries for writing task extraction
   - Test with sample queries

3. **Configuration System**
   - Implement EvalConfig Pydantic model
   - Create preset configurations (all 10 levels)
   - Build configuration validation

4. **Basic CLI**
   - Set up Typer CLI structure
   - Implement `--dry-run` cost estimation
   - Create basic command scaffolding

#### Phase 2: Prompt Generation (Week 2-3)

**Goals:** Build the complete prompt generation pipeline

1. **Algorithmic Generation (Phase 2 of PROMPT.md)**
   - Implement NAICSMapper
   - Build CompanyDatabase with real companies
   - Create NameGenerator for diverse personas
   - Implement PromptSampler with stratification

2. **LLM Enrichment (Phase 3 of PROMPT.md)**
   - Implement PromptEnricher for complex prompts
   - Build attachment generation
   - Create prior message generation
   - Implement tone example generation

3. **Prompt Validation**
   - Validate all generated prompts against schema
   - Ensure diversity requirements are met
   - Test prompt quality with sample generation

#### Phase 3: API Integration (Week 3-4)

**Goals:** Robust API client with error handling

1. **OpenRouter Client**
   - Implement async HTTP client with httpx
   - Build request/response handling
   - Implement authentication

2. **Robustness Layer**
   - Implement RateLimiter with per-provider limits
   - Build RetryHandler with exponential backoff
   - Create CircuitBreaker for fault tolerance

3. **Cost Tracking**
   - Implement CostTracker
   - Build cost estimation logic
   - Create cost reporting

#### Phase 4: Evaluation Engine (Week 4-5)

**Goals:** Core evaluation logic and judging

1. **Response Generation**
   - Implement ResponseGenerator
   - Build response metadata extraction
   - Handle refusals and errors

2. **Judge Orchestrator**
   - Implement multi-model judging
   - Build dual-persona evaluation
   - Create vote aggregation (majority-of-majorities)

3. **Evaluation Rubric**
   - Implement EvaluationRubric
   - Build judge prompts with full context
   - Create judgment parsing

#### Phase 5: Storage and Checkpointing (Week 5-6)

**Goals:** Persistent storage with resume capability

1. **Database Layer**
   - Implement SQLite schema
   - Build StorageManager with async operations
   - Create indexes for efficient queries

2. **Checkpoint System**
   - Implement CheckpointManager
   - Build resume logic
   - Test interruption and recovery

3. **Results Organization**
   - Implement ResultsManager
   - Create directory structure
   - Build export functionality

#### Phase 6: TUI and Reporting (Week 6-7)

**Goals:** User interfaces and analysis

1. **Progress TUI**
   - Implement EvalProgressApp with Textual
   - Build real-time progress display
   - Create interactive controls

2. **Results Viewer**
   - Implement ResultsViewerApp
   - Build filtering and sorting
   - Create detail views

3. **Statistical Analysis**
   - Implement StatisticalAnalyzer
   - Build bias detection
   - Create weakness identification

4. **PDF Reports**
   - Implement PDFReportGenerator
   - Build chart generation with Plotly
   - Create report sections

#### Phase 7: Integration and Polish (Week 7-8)

**Goals:** End-to-end testing and refinement

1. **Integration Testing**
   - Full pipeline tests
   - Cross-run comparison testing
   - Performance optimization

2. **Documentation**
   - API documentation
   - Usage examples
   - Troubleshooting guide

3. **Polish**
   - Error message improvements
   - Edge case handling
   - UI refinements

### 10.2 Testing Strategy

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from pathlib import Path

@pytest.fixture
def onet_db_path():
    """Path to test O*NET database"""
    return Path("db/onet.db")

@pytest.fixture
def sample_prompt():
    """Sample WritingPrompt for testing"""
    return WritingPrompt(
        prompt_id="test_001",
        onet_task_id="1234",
        onet_soc_code="11-1011.00",
        task_statement="Draft quarterly report",
        enriched_prompt="You are a CEO...",
        occupation_title="Chief Executive",
        job_zone=5,
        soc_major_group="11",
        company=Company(
            name="Acme Corp",
            industry_naics="54",
            industry_name="Professional Services",
            size_category="medium",
            public_private="private"
        ),
        writer=Persona(name="John Smith", role="CEO"),
        recipients=[Persona(name="Board of Directors", role="Board")],
        channel=CommunicationChannel.REPORT,
        formality_level=5,
        urgency_level=3,
        relationship_context="established",
        audience_size="small_group",
        message_position="initial",
        writing_category="reports",
        generation_phase=2,
        generation_timestamp=datetime.utcnow(),
        random_seed=42
    )

@pytest_asyncio.fixture
async def mock_openrouter():
    """Mock OpenRouter client for testing"""
    # Return mock responses
    pass

# tests/unit/test_onet_loader.py
class TestONetLoader:
    async def test_extract_writing_tasks(self, onet_db_path):
        """Test that writing tasks are extracted correctly"""
        loader = ONetLoader(onet_db_path)
        tasks = await loader.extract_writing_tasks()

        assert len(tasks) > 1000  # Should have many writing tasks
        assert all(t.task_id for t in tasks)
        assert all(t.onetsoc_code for t in tasks)

    async def test_writing_categories_coverage(self, onet_db_path):
        """Test that all writing categories are represented"""
        loader = ONetLoader(onet_db_path)
        tasks = await loader.extract_writing_tasks()

        categories = set(t.inferred_category for t in tasks)
        expected_categories = {
            "explicit_writing", "correspondence", "reports",
            "proposals", "policy", "customer_communication",
            "training", "coordination", "contracts", "feedback"
        }

        assert categories >= expected_categories

# tests/unit/test_judge_aggregation.py
class TestVoteAggregation:
    def test_majority_of_majorities(self):
        """Test vote aggregation logic"""
        votes = [
            # Claude: 3 gemini, 2 competitor
            JudgmentVote(judge_model="claude", winner_model="gemini"),
            JudgmentVote(judge_model="claude", winner_model="gemini"),
            JudgmentVote(judge_model="claude", winner_model="gemini"),
            JudgmentVote(judge_model="claude", winner_model="competitor"),
            JudgmentVote(judge_model="claude", winner_model="competitor"),
            # GPT: 2 gemini, 3 competitor
            JudgmentVote(judge_model="gpt", winner_model="gemini"),
            JudgmentVote(judge_model="gpt", winner_model="gemini"),
            JudgmentVote(judge_model="gpt", winner_model="competitor"),
            JudgmentVote(judge_model="gpt", winner_model="competitor"),
            JudgmentVote(judge_model="gpt", winner_model="competitor"),
            # Gemini: 4 gemini, 1 competitor
            JudgmentVote(judge_model="gemini_judge", winner_model="gemini"),
            JudgmentVote(judge_model="gemini_judge", winner_model="gemini"),
            JudgmentVote(judge_model="gemini_judge", winner_model="gemini"),
            JudgmentVote(judge_model="gemini_judge", winner_model="gemini"),
            JudgmentVote(judge_model="gemini_judge", winner_model="competitor"),
        ]

        aggregator = VoteAggregator()
        result = aggregator.aggregate(votes)

        # Claude: gemini wins, GPT: competitor wins, Gemini: gemini wins
        # Majority of majorities: gemini wins (2-1)
        assert result.final_winner == "gemini"
        assert result.judge_agreement_count == 2

# tests/integration/test_full_pipeline.py
class TestFullPipeline:
    @pytest.mark.integration
    async def test_small_eval_run(self, mock_openrouter):
        """Test a complete small evaluation run"""
        config = PRESETS[1]  # Sanity check preset

        engine = EvaluationEngine(
            config=config,
            api_client=mock_openrouter
        )

        result = await engine.run_evaluation()

        assert result.total_comparisons == 5
        assert len(result.comparisons) == 5
        assert all(c.final_winner in ["gemini", "competitor", "tie"]
                   for c in result.comparisons)
```

### 10.3 Dependencies (pyproject.toml)

```toml
[project]
name = "gemini-writing-eval"
version = "0.1.0"
description = "Gemini Writing Evaluation Framework"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "typer>=0.9.0",
    "rich>=13.7.0",
    "textual>=0.47.0",
    "plotly>=5.18.0",
    "kaleido>=0.2.1",
    "weasyprint>=60.1",
    "scipy>=1.12.0",
    "scikit-learn>=1.4.0",
    "aiosqlite>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
    "pre-commit>=3.6.0",
]

[project.scripts]
eval = "src.cli.main:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.ruff]
line-length = 100
target-version = "py311"
```

---

## Part 11: Key Design Decisions and Trade-offs

### 11.1 Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Database** | SQLite | Portable, no server, sufficient for eval data volumes |
| **Async** | Full asyncio | Maximize API throughput, handle concurrent requests |
| **TUI Framework** | Textual | Modern, rich features, good async support |
| **Data Validation** | Pydantic v2 | Fast, type-safe, JSON schema generation |
| **HTTP Client** | httpx | Async-native, connection pooling, modern API |
| **Determinism** | Seeded random | Reproducible sampling while allowing variation |
| **Vote Aggregation** | Majority-of-majorities | Most robust against individual judge bias |
| **Prompt Generation** | Three-phase | Balance between diversity and consistency |

### 11.2 Known Trade-offs

1. **Using Evaluated Models for Enrichment**
   - Trade-off: Potential bias in prompt generation
   - Mitigation: Document which models generated which prompts, analyze for bias

2. **Real Company Names**
   - Trade-off: Models may have uneven training data about companies
   - Mitigation: Track company usage, analyze for correlation with win rates

3. **English-Only v1**
   - Trade-off: Limited international applicability
   - Mitigation: Schema supports language field for future extension

4. **No Human Baselines**
   - Trade-off: Cannot compare to human-written text
   - Mitigation: Focus on model-vs-model comparison, which is the stated goal

5. **Judge Model Overlap**
   - Trade-off: Gemini judges Gemini responses
   - Mitigation: Ensemble of 3 judges reduces individual bias impact

### 11.3 Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| API rate limits | High | Medium | Adaptive rate limiting, circuit breaker |
| Judge inconsistency | High | Medium | Multiple judges, best-of-5, reliability metrics |
| Prompt bias | Medium | Medium | Document generation, analyze correlations |
| Cost overruns | Medium | Low | Pre-run estimates, confirmation prompt |
| Data loss | High | Low | Checkpointing, atomic writes |
| Model availability | Medium | Low | Graceful degradation, skip unavailable |

---

## Appendix A: Sample Prompts

### A.1 Simple Prompt Example

```json
{
  "prompt_id": "p_001_simple",
  "onet_task_id": "T_11-1011_01",
  "onet_soc_code": "11-1011.00",
  "task_statement": "Draft correspondence for executive review",
  "enriched_prompt": "You are Sarah Chen, CEO of Patagonia, writing to your board of directors. Draft a brief email summarizing your key strategic priorities for Q1 2026.",
  "occupation_title": "Chief Executive",
  "job_zone": 5,
  "company": {
    "name": "Patagonia",
    "industry_naics": "44",
    "industry_name": "Retail Trade",
    "size_category": "large",
    "public_private": "private"
  },
  "writer": {
    "name": "Sarah Chen",
    "role": "CEO",
    "age_range": "45-55",
    "generation": "GenX"
  },
  "recipients": [
    {"name": "Board of Directors", "role": "Board"}
  ],
  "channel": "email",
  "formality_level": 5,
  "urgency_level": 2,
  "writing_category": "correspondence"
}
```

### A.2 Complex Prompt Example (with attachments and prior context)

```json
{
  "prompt_id": "p_002_complex",
  "onet_task_id": "T_13-1111_03",
  "onet_soc_code": "13-1111.00",
  "task_statement": "Resolve customer complaints regarding sales and service",
  "enriched_prompt": "You are Marcus Johnson, Customer Success Manager at Salesforce. An enterprise client has sent an angry email about service disruptions. Write a response that acknowledges their concerns, explains the situation, and proposes next steps.",
  "occupation_title": "Management Analyst",
  "job_zone": 4,
  "company": {
    "name": "Salesforce",
    "industry_naics": "51",
    "industry_name": "Information",
    "size_category": "fortune500",
    "public_private": "public"
  },
  "writer": {
    "name": "Marcus Johnson",
    "role": "Customer Success Manager",
    "age_range": "30-40",
    "generation": "Millennial"
  },
  "recipients": [
    {"name": "Jennifer Walsh", "role": "VP of IT", "email": "j.walsh@acme.com"}
  ],
  "cc_recipients": [
    {"name": "Tom Rodriguez", "role": "Account Executive"}
  ],
  "channel": "email",
  "formality_level": 4,
  "urgency_level": 4,
  "emotional_context": "conflict",
  "message_position": "reply",
  "prior_message": "Marcus,\n\nThis is unacceptable. We've had three service outages in the past month and your team has been completely unresponsive. We're paying enterprise rates for enterprise support and getting neither.\n\nI'm escalating this to our executive team and will be reviewing our contract renewal.\n\n- Jennifer",
  "attachments": [
    {
      "type": "document",
      "description": "Service incident log",
      "content": "Incident #4521: 2h downtime on Jan 3\nIncident #4523: 45min degraded performance on Jan 12\nIncident #4527: 3h partial outage on Jan 18"
    }
  ],
  "competing_objectives": [
    "Be apologetic without admitting fault",
    "Retain the customer while being honest about limitations"
  ],
  "sensitive_category": "conflict",
  "writing_category": "customer_communication"
}
```

---

## Appendix B: Evaluation Rubric Details

### B.1 Scoring Guidelines

| Criterion | 1 (Poor) | 3 (Adequate) | 5 (Excellent) |
|-----------|----------|--------------|---------------|
| Writing Quality | Unclear, poor grammar, disorganized | Competent but unremarkable | Clear, polished, well-structured |
| Tone Appropriateness | Wrong tone for context | Generally appropriate | Perfectly matched to situation |
| Length Appropriateness | Way too long/short | Acceptable length | Exactly right for the task |
| Task Completion | Misses key requirements | Addresses main points | Fully complete and thorough |
| Authenticity | Obviously AI-generated | Mostly natural | Reads like human writing |
| Cliche Avoidance | Full of AI cliches | Some generic phrases | Fresh, specific language |
| Effectiveness | Would not achieve goal | Might work | Would definitely succeed |

### B.2 Common AI Writing Patterns to Detect

- "I hope this email finds you well"
- "Please don't hesitate to reach out"
- "I'm happy to help"
- "Thank you for your patience"
- Excessive bullet points for simple content
- Overly formal language in casual contexts
- Generic sign-offs ("Best regards" in every email)
- Unnecessary hedging ("I think", "perhaps", "maybe")
- Excessive positivity ("excited", "thrilled", "delighted")

---

*End of Implementation Plan Draft 3*
