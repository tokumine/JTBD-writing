# Gemini Writing Evaluation Framework - Implementation Plan

## Document Info
- **Plan Version**: Draft 5
- **Date**: January 8, 2026
- **Scope**: Complete system architecture and implementation details

---

## 1. Executive Summary

This plan describes a comprehensive writing evaluation framework that compares Gemini 3.0 Pro and Flash against competing frontier LLMs across realistic professional writing tasks. The system leverages the O*NET 30.1 database (18,796 task statements across 1,016 occupations) to generate diverse, authentic writing prompts that represent the full spectrum of workplace communication.

### Core Design Principles

1. **Data-Driven Diversity**: Let O*NET task data drive prompt variety rather than hardcoding categories
2. **Statistical Rigor**: Majority-of-majorities voting with ensemble judges for robustness
3. **Full Reproducibility**: Deterministic shuffling, saved seeds, and comprehensive checkpointing
4. **Cost Transparency**: Real-time cost estimation and configurable evaluation presets
5. **Operational Resilience**: Graceful failure handling, automatic retries, and full resumability

---

## 2. System Architecture Overview

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GEMINI WRITING EVAL FRAMEWORK                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   CONFIG    │───▶│   PROMPT    │───▶│  RESPONSE   │───▶│   JUDGE     │  │
│  │   MODULE    │    │  GENERATOR  │    │  COLLECTOR  │    │   MODULE    │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         DATA LAYER (SQLite)                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │   │
│  │  │ O*NET DB │  │ Prompts  │  │Responses │  │Judgments │             │   │
│  │  │ (source) │  │ (frozen) │  │(per model)│  │(per eval) │             │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │  ANALYSIS   │───▶│   REPORT    │───▶│    TUI      │                     │
│  │   ENGINE    │    │  GENERATOR  │    │   VIEWER    │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async support, rich ecosystem |
| Async HTTP | httpx | Modern, async-native HTTP client |
| Data Validation | Pydantic v2 | Type-safe schemas, JSON serialization |
| Database | SQLite + aiosqlite | Simple, portable, async-compatible |
| TUI Framework | textual | Rich terminal UI with modern widgets |
| Visualization | plotly | Interactive charts, PDF export |
| PDF Generation | reportlab + matplotlib | Publication-quality reports |
| CLI Framework | typer | Modern CLI with automatic help |
| Config Management | pydantic-settings | Environment + file config |

### 2.3 Directory Structure

```
gemini-writing-eval/
├── pyproject.toml                 # Project dependencies and metadata
├── README.md                      # Setup and usage instructions
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                      # Core domain models and interfaces
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic models for all entities
│   │   ├── interfaces.py          # Abstract base classes
│   │   └── enums.py               # Enumerations (JudgeVerdict, etc.)
│   │
│   ├── config/                    # Configuration management
│   │   ├── __init__.py
│   │   ├── settings.py            # Global settings and presets
│   │   ├── presets.py             # 10 eval preset definitions
│   │   └── cost_estimator.py      # Token/cost estimation
│   │
│   ├── data/                      # Data layer
│   │   ├── __init__.py
│   │   ├── onet_extractor.py      # O*NET database queries
│   │   ├── naics_mapper.py        # Industry code mapping
│   │   ├── company_sampler.py     # Real company selection
│   │   ├── name_generator.py      # Realistic name generation
│   │   └── results_db.py          # Results SQLite operations
│   │
│   ├── prompts/                   # Prompt generation pipeline
│   │   ├── __init__.py
│   │   ├── task_selector.py       # O*NET task sampling
│   │   ├── persona_generator.py   # Writer/recipient personas
│   │   ├── context_builder.py     # Context enrichment
│   │   ├── prompt_assembler.py    # Final prompt construction
│   │   └── enrichment_llm.py      # LLM-based enrichment (Phase 3)
│   │
│   ├── eval/                      # Evaluation execution
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # Main eval loop coordinator
│   │   ├── response_collector.py  # Model response gathering
│   │   ├── judge_module.py        # Judging logic
│   │   ├── vote_aggregator.py     # Majority-of-majorities
│   │   └── checkpoint_manager.py  # Resume/checkpoint handling
│   │
│   ├── api/                       # External API integrations
│   │   ├── __init__.py
│   │   ├── openrouter_client.py   # OpenRouter API wrapper
│   │   ├── rate_limiter.py        # Rate limiting with backoff
│   │   └── retry_handler.py       # Retry logic with jitter
│   │
│   ├── analysis/                  # Post-eval analysis
│   │   ├── __init__.py
│   │   ├── win_rate_calculator.py # Win rate computation
│   │   ├── confidence_intervals.py # CI calculations
│   │   ├── bias_detector.py       # Systematic bias detection
│   │   ├── weakness_analyzer.py   # Weakness identification
│   │   └── statistical_tests.py   # Significance testing
│   │
│   ├── reports/                   # Report generation
│   │   ├── __init__.py
│   │   ├── pdf_generator.py       # PDF report assembly
│   │   ├── chart_builder.py       # Visualization creation
│   │   └── executive_summary.py   # Summary generation
│   │
│   ├── tui/                       # Terminal UI
│   │   ├── __init__.py
│   │   ├── app.py                 # Main textual app
│   │   ├── progress_screen.py     # Live progress dashboard
│   │   ├── results_browser.py     # Results exploration
│   │   └── comparison_viewer.py   # Side-by-side response view
│   │
│   └── cli/                       # Command-line interface
│       ├── __init__.py
│       ├── main.py                # Entry point
│       ├── run_cmd.py             # Run evaluation command
│       ├── view_cmd.py            # View results command
│       └── compare_cmd.py         # Cross-run comparison
│
├── db/
│   └── onet.db                    # O*NET 30.1 database (provided)
│
├── results/                       # Evaluation outputs (gitignored)
│   └── eval_YYYY-MM-DD_HH-MM-SS/
│       └── ...                    # Run-specific files
│
└── tests/
    ├── __init__.py
    ├── test_prompt_generation.py
    ├── test_judging.py
    ├── test_analysis.py
    └── fixtures/
        └── sample_prompts.json
```

---

## 3. Core Data Models (Pydantic Schemas)

### 3.1 Prompt Models

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class FormailtyLevel(str, Enum):
    VERY_CASUAL = "very_casual"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    VERY_FORMAL = "very_formal"

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    INITIAL = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"

class AudienceSize(str, Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"

class WriterPersona(BaseModel):
    """Full specification of the person writing"""
    name: str
    email: Optional[str] = None
    job_title: str
    department: Optional[str] = None
    age_range: str  # e.g., "25-35", "55-65"
    generation: str  # e.g., "GenZ", "Millennial", "GenX", "Boomer"
    skill_level: Literal["junior", "mid", "senior", "executive"]
    years_experience: int
    english_variant: EnglishVariant = EnglishVariant.EN_US
    communication_style_notes: Optional[str] = None

class RecipientPersona(BaseModel):
    """Full specification of the target reader"""
    name: str
    email: Optional[str] = None
    job_title: str
    company: Optional[str] = None
    relationship_to_writer: str  # e.g., "direct report", "client", "vendor"
    familiarity: Literal["first_contact", "acquaintance", "established", "close"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    technical_level: Literal["non_technical", "somewhat_technical", "technical", "expert"]

class CompanyContext(BaseModel):
    """Real company grounding"""
    name: str
    industry: str
    naics_code: str
    size_category: Literal["startup", "small", "medium", "large", "enterprise"]
    employee_count_range: str  # e.g., "10-50", "10000+"
    public_private: Literal["public", "private", "nonprofit", "government"]
    hq_location: str
    founded_year: Optional[int] = None

class AttachmentReference(BaseModel):
    """Mock attachment or reference content"""
    attachment_type: str  # "report", "email_thread", "meeting_notes", "resume", etc.
    description: str
    content_summary: str  # The actual content to include

class WritingPrompt(BaseModel):
    """Complete prompt specification"""
    prompt_id: str

    # O*NET source
    onet_task_id: str
    onet_task_statement: str
    onet_occupation_code: str
    onet_occupation_title: str
    onet_job_zone: int  # 1-5
    soc_major_group: str

    # Company context
    company: CompanyContext

    # People
    writer: WriterPersona
    recipients: list[RecipientPersona]  # May be multiple (CC situations)

    # Communication context
    formality_level: FormailtyLevel
    message_position: MessagePosition
    audience_size: AudienceSize
    emotional_context: EmotionalContext
    urgency: Literal["low", "medium", "high", "critical"]

    # Content requirements
    communication_channel: Optional[str] = None  # "email", "memo", "report", etc.
    competing_objectives: list[str] = Field(default_factory=list)
    explicit_constraints: list[str] = Field(default_factory=list)

    # Attachments/context
    attachments: list[AttachmentReference] = Field(default_factory=list)
    prior_messages: list[str] = Field(default_factory=list)  # For reply scenarios
    tone_example: Optional[str] = None  # Example to match

    # Temporal
    temporal_context: Optional[str] = None

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    sensitive_topic_tags: list[str] = Field(default_factory=list)
    inferred_writing_category: str  # From O*NET WRITING_REFERENCE categories
    is_revision_task: bool = False
    is_ambiguous_task: bool = False
    has_instruction_constraints: bool = False

    # The actual prompt text sent to models
    assembled_prompt: str

    # Generation metadata
    generation_seed: int
    generation_timestamp: datetime
```

### 3.2 Response Models

```python
class ModelResponse(BaseModel):
    """A single model's response to a prompt"""
    response_id: str
    prompt_id: str
    model_id: str  # OpenRouter model identifier
    model_display_name: str

    # Response content
    response_text: str

    # Metadata
    response_time_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int

    # Format analysis
    word_count: int
    character_count: int
    has_bullet_points: bool
    has_headers: bool
    has_greeting: bool
    has_signoff: bool
    paragraph_count: int

    # Status
    is_refusal: bool = False
    refusal_category: Optional[str] = None  # "safety", "capability", "misunderstanding", etc.
    is_incomplete: bool = False
    is_off_topic: bool = False

    # Raw API response
    raw_api_response: dict

    timestamp: datetime

class ResponsePair(BaseModel):
    """A pair of responses for side-by-side comparison"""
    pair_id: str
    prompt_id: str
    response_a: ModelResponse
    response_b: ModelResponse

    # Ordering (for position bias mitigation)
    gemini_position: Literal["A", "B"]
    shuffle_seed: int
```

### 3.3 Judgment Models

```python
class JudgeVerdict(str, Enum):
    RESPONSE_A_WINS = "A"
    RESPONSE_B_WINS = "B"
    TIE = "TIE"

class JudgePersona(str, Enum):
    WRITING_EXPERT = "writing_expert"
    TARGET_RECIPIENT = "target_recipient"

class SingleJudgment(BaseModel):
    """One judge's single vote"""
    judgment_id: str
    pair_id: str
    judge_model_id: str
    judge_persona: JudgePersona
    vote_index: int  # Which of the 5 votes (0-4)

    verdict: JudgeVerdict

    # Detailed reasoning
    reasoning: str

    # Criteria scores (1-5 scale)
    quality_score_a: int
    quality_score_b: int
    tone_appropriateness_a: int
    tone_appropriateness_b: int
    length_appropriateness_a: int
    length_appropriateness_b: int
    effectiveness_a: int
    effectiveness_b: int
    authenticity_a: int  # Human-like quality
    authenticity_b: int
    cliche_avoidance_a: int
    cliche_avoidance_b: int
    instruction_compliance_a: Optional[int] = None
    instruction_compliance_b: Optional[int] = None

    # Metadata
    response_time_ms: int
    timestamp: datetime

class JudgeModelResult(BaseModel):
    """Aggregated result from one judge model (5 votes -> majority)"""
    judge_model_id: str
    judge_persona: JudgePersona
    pair_id: str

    individual_votes: list[JudgeVerdict]
    majority_verdict: JudgeVerdict
    vote_count_a: int
    vote_count_b: int
    vote_count_tie: int

class ComparisonResult(BaseModel):
    """Final result for one prompt comparison"""
    comparison_id: str
    pair_id: str
    prompt_id: str

    # Models being compared
    gemini_model_id: str
    opponent_model_id: str

    # Per-judge-model results
    judge_results: list[JudgeModelResult]

    # Final aggregation (majority of majorities)
    final_verdict: JudgeVerdict
    judges_for_gemini: int
    judges_for_opponent: int
    judges_tie: int

    # Confidence
    unanimous: bool

    # Auto-loss tracking
    gemini_auto_loss: bool = False
    opponent_auto_loss: bool = False
    auto_loss_reason: Optional[str] = None
```

---

## 4. Data Pipeline: O*NET to Prompts

### 4.1 Phase 1: Task Extraction and Filtering

The pipeline begins by extracting writing-relevant tasks from the O*NET database.

#### 4.1.1 Writing Task Identification Strategy

Rather than relying solely on keyword matching, use a multi-signal approach:

```python
class TaskWritingSignals(BaseModel):
    """Signals indicating writing relevance for a task"""
    has_explicit_writing_keyword: bool  # write, draft, document, etc.
    has_communication_keyword: bool  # correspond, notify, inform, etc.
    occupation_writing_skill_score: float  # From skills table
    occupation_email_frequency: float  # From work_context
    occupation_correspondence_frequency: float  # From work_context
    inferred_category: Optional[str]  # From 10 categories in REFERENCE

    @property
    def composite_score(self) -> float:
        """Calculate overall writing relevance score"""
        score = 0.0
        if self.has_explicit_writing_keyword:
            score += 3.0
        if self.has_communication_keyword:
            score += 2.0
        score += self.occupation_writing_skill_score * 0.5
        score += self.occupation_email_frequency * 0.3
        score += self.occupation_correspondence_frequency * 0.3
        return score
```

#### 4.1.2 Task Extraction SQL

```python
EXTRACT_WRITING_TASKS_SQL = """
WITH writing_skills AS (
    SELECT onetsoc_code, data_value as writing_skill
    FROM skills
    WHERE element_id = '2.A.1.c' AND scale_id = 'IM'
),
email_freq AS (
    SELECT onetsoc_code, data_value as email_frequency
    FROM work_context
    WHERE element_id = '4.C.1.a.2.h' AND scale_id = 'CX'
),
correspondence_freq AS (
    SELECT onetsoc_code, data_value as correspondence_frequency
    FROM work_context
    WHERE element_id = '4.C.1.a.2.j' AND scale_id = 'CX'
)
SELECT
    t.task_id,
    t.task,
    t.task_type,
    t.onetsoc_code,
    o.title as occupation_title,
    o.description as occupation_description,
    jz.job_zone,
    SUBSTR(t.onetsoc_code, 1, 2) as soc_major,
    COALESCE(ws.writing_skill, 2.5) as writing_skill,
    COALESCE(ef.email_frequency, 2.5) as email_frequency,
    COALESCE(cf.correspondence_frequency, 2.5) as correspondence_frequency,
    -- Keyword detection
    CASE WHEN t.task LIKE '%write%' OR t.task LIKE '%draft%'
         OR t.task LIKE '%document%' OR t.task LIKE '%compose%'
         OR t.task LIKE '%author%' THEN 1 ELSE 0 END as has_writing_keyword,
    CASE WHEN t.task LIKE '%correspond%' OR t.task LIKE '%email%'
         OR t.task LIKE '%notify%' OR t.task LIKE '%inform%'
         OR t.task LIKE '%communicate%' OR t.task LIKE '%contact%'
         THEN 1 ELSE 0 END as has_comm_keyword
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
LEFT JOIN writing_skills ws ON t.onetsoc_code = ws.onetsoc_code
LEFT JOIN email_freq ef ON t.onetsoc_code = ef.onetsoc_code
LEFT JOIN correspondence_freq cf ON t.onetsoc_code = cf.onetsoc_code
WHERE
    -- At least one signal of writing relevance
    (t.task LIKE '%write%' OR t.task LIKE '%draft%'
     OR t.task LIKE '%document%' OR t.task LIKE '%prepare%'
     OR t.task LIKE '%correspond%' OR t.task LIKE '%report%'
     OR t.task LIKE '%email%' OR t.task LIKE '%present%'
     OR t.task LIKE '%memo%' OR t.task LIKE '%letter%'
     OR t.task LIKE '%propos%' OR t.task LIKE '%recommend%'
     OR t.task LIKE '%notify%' OR t.task LIKE '%inform%'
     OR t.task LIKE '%communicate%' OR t.task LIKE '%evaluat%'
     OR t.task LIKE '%confer%' OR t.task LIKE '%coordinate%'
     OR COALESCE(ws.writing_skill, 0) >= 3.5
     OR COALESCE(ef.email_frequency, 0) >= 3.5
     OR COALESCE(cf.correspondence_frequency, 0) >= 3.5)
ORDER BY
    (CASE WHEN t.task LIKE '%write%' OR t.task LIKE '%draft%' THEN 3 ELSE 0 END +
     CASE WHEN t.task LIKE '%correspond%' OR t.task LIKE '%email%' THEN 2 ELSE 0 END +
     COALESCE(ws.writing_skill, 2.5) * 0.5) DESC;
"""
```

#### 4.1.3 Writing Category Classification

Map each task to one of the 10 inferred categories from ONET_WRITING_REFERENCE.md:

```python
WRITING_CATEGORY_PATTERNS = {
    "explicit_writing": [
        r"\bwrite\b", r"\bdraft\b", r"\bdocument\b", r"\bcompose\b", r"\bauthor\b"
    ],
    "correspondence": [
        r"\bcorrespond\b", r"\bemail\b", r"\bletter\b", r"\bmemo\b"
    ],
    "reports_presentations": [
        r"\breport\b", r"\bpresent\b", r"\bsummariz\b"
    ],
    "persuasion_negotiation": [
        r"\bnegotiat\b", r"\bpropos\b", r"\bpersuad\b", r"\brecommend\b"
    ],
    "policy_procedure": [
        r"\bpolic\w*\b", r"\bprocedure\b", r"\bguideline\b", r"\bstandard\b"
    ],
    "customer_communication": [
        r"\bcustomer\b", r"\bclient\b", r"\bpatient\b", r"\bexplain\b.*\bto\b"
    ],
    "training_instruction": [
        r"\btrain\b", r"\binstruct\b", r"\bteach\b", r"\bcurriculum\b"
    ],
    "internal_coordination": [
        r"\bconfer\b", r"\bcoordinate\b", r"\bcollaborat\b", r"\bmeet\b"
    ],
    "contracts_legal": [
        r"\bcontract\b", r"\bagreement\b", r"\blegal\b", r"\blicense\b"
    ],
    "feedback_evaluation": [
        r"\bevaluat\b.*\breport\b", r"\bfeedback\b", r"\breview\b.*\brecommend\b"
    ]
}

def classify_task_category(task_text: str) -> str:
    """Classify task into writing category, returning first match or 'general'"""
    import re
    task_lower = task_text.lower()
    for category, patterns in WRITING_CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, task_lower):
                return category
    return "general"
```

### 4.2 Phase 2: Algorithmic Diversity Sampling

#### 4.2.1 NAICS Industry Mapping

Since O*NET lacks direct NAICS codes, we need an external mapping strategy:

```python
class NAICSMapper:
    """Maps O*NET occupations to NAICS industries"""

    # SOC major group to primary NAICS sectors mapping
    SOC_TO_NAICS_PRIMARY = {
        "11": ["52", "54", "55", "61"],  # Management -> Finance, Prof Services, etc.
        "13": ["52", "54", "55"],         # Business/Financial -> Finance, Prof Services
        "15": ["51", "54"],               # Computer/Math -> Information, Prof Services
        "17": ["54", "23", "31-33"],      # Engineering -> Prof Services, Construction, Mfg
        "19": ["54", "61", "62"],         # Science -> Prof Services, Education, Healthcare
        "21": ["62", "92"],               # Social Service -> Healthcare, Public Admin
        "23": ["54"],                     # Legal
        "25": ["61"],                     # Education
        "27": ["51", "71"],               # Arts/Media -> Information, Entertainment
        "29": ["62"],                     # Healthcare Practitioners
        "31": ["62"],                     # Healthcare Support
        "33": ["92"],                     # Protective Service
        "35": ["72"],                     # Food Service
        "37": ["56"],                     # Building/Grounds
        "39": ["72", "81"],               # Personal Care
        "41": ["44-45", "52"],            # Sales
        "43": ["All"],                    # Office/Admin - crosses all industries
        "45": ["11"],                     # Agriculture
        "47": ["23"],                     # Construction
        "49": ["31-33", "81"],            # Maintenance
        "51": ["31-33"],                  # Production
        "53": ["48-49"],                  # Transportation
        "55": ["92"],                     # Military
    }

    # Full NAICS sector definitions
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
        "92": "Public Administration",
    }

    def get_industries_for_occupation(
        self, soc_major: str, diversify: bool = True
    ) -> list[str]:
        """Get applicable NAICS codes for an occupation"""
        primary = self.SOC_TO_NAICS_PRIMARY.get(soc_major, ["54"])
        if "All" in primary:
            return list(self.NAICS_SECTORS.keys())
        if diversify:
            # Add some cross-industry possibilities
            return primary + random.sample(
                [k for k in self.NAICS_SECTORS.keys() if k not in primary],
                min(2, len(self.NAICS_SECTORS) - len(primary))
            )
        return primary
```

#### 4.2.2 Real Company Sampler

```python
class CompanySampler:
    """Samples real companies with metadata for prompt grounding"""

    # Company database organized by NAICS and size
    # This would be populated from LLM knowledge or external data
    COMPANY_DATABASE = {
        # Format: (name, size_category, employee_range, public/private, hq, founded)
        "52": [  # Finance
            ("JPMorgan Chase", "enterprise", "250000+", "public", "New York, NY", 1799),
            ("Goldman Sachs", "enterprise", "40000+", "public", "New York, NY", 1869),
            ("Stripe", "large", "5000-10000", "private", "San Francisco, CA", 2010),
            ("Chime", "medium", "1000-5000", "private", "San Francisco, CA", 2013),
            ("Acorns", "small", "100-500", "private", "Irvine, CA", 2012),
        ],
        "54": [  # Professional Services
            ("McKinsey & Company", "enterprise", "30000+", "private", "New York, NY", 1926),
            ("Deloitte", "enterprise", "400000+", "private", "London, UK", 1845),
            ("IDEO", "medium", "500-1000", "private", "Palo Alto, CA", 1991),
            ("Clarity Consulting", "small", "50-100", "private", "Chicago, IL", 2002),
        ],
        # ... extensive database for all NAICS sectors
    }

    def sample_company(
        self,
        naics_code: str,
        size_preference: Optional[str] = None,
        seed: Optional[int] = None
    ) -> CompanyContext:
        """Sample a real company for prompt grounding"""
        rng = random.Random(seed)
        companies = self.COMPANY_DATABASE.get(naics_code, self.COMPANY_DATABASE["54"])

        if size_preference:
            filtered = [c for c in companies if c[1] == size_preference]
            if filtered:
                companies = filtered

        company = rng.choice(companies)
        return CompanyContext(
            name=company[0],
            industry=NAICSMapper.NAICS_SECTORS[naics_code],
            naics_code=naics_code,
            size_category=company[1],
            employee_count_range=company[2],
            public_private=company[3],
            hq_location=company[4],
            founded_year=company[5] if len(company) > 5 else None
        )
```

#### 4.2.3 Stratified Sampling Strategy

```python
class StratifiedTaskSampler:
    """Ensures diverse sampling across all dimensions"""

    def __init__(self, tasks: list[dict], config: SamplingConfig):
        self.tasks = tasks
        self.config = config

    def sample(self, n: int, seed: int) -> list[dict]:
        """Sample n tasks with stratification across dimensions"""
        rng = random.Random(seed)

        # Build stratification buckets
        buckets = {
            "job_zone": defaultdict(list),      # 5 zones
            "soc_major": defaultdict(list),     # 22 groups
            "writing_category": defaultdict(list),  # 10 categories
        }

        for task in self.tasks:
            buckets["job_zone"][task["job_zone"]].append(task)
            buckets["soc_major"][task["soc_major"]].append(task)
            buckets["writing_category"][task["inferred_category"]].append(task)

        # Calculate target distribution
        # Aim for even distribution but allow natural weighting
        selected = []
        selected_ids = set()

        # Round-robin across dimensions to ensure coverage
        dimensions = ["job_zone", "soc_major", "writing_category"]

        while len(selected) < n:
            for dim in dimensions:
                if len(selected) >= n:
                    break
                # Pick from least-sampled bucket in this dimension
                bucket_counts = {
                    k: len([t for t in v if t["task_id"] not in selected_ids])
                    for k, v in buckets[dim].items()
                }
                # Weight by inverse of current selection from that bucket
                for bucket_key in sorted(bucket_counts.keys(),
                                        key=lambda k: -bucket_counts[k]):
                    available = [
                        t for t in buckets[dim][bucket_key]
                        if t["task_id"] not in selected_ids
                    ]
                    if available:
                        task = rng.choice(available)
                        selected.append(task)
                        selected_ids.add(task["task_id"])
                        break

        return selected[:n]
```

### 4.3 Phase 3: LLM Enrichment

#### 4.3.1 Persona Generation

```python
class PersonaGenerator:
    """Generates realistic writer and recipient personas"""

    AGE_GENERATION_MAP = {
        "18-25": "GenZ",
        "26-35": "Millennial",
        "36-45": "Millennial/GenX",
        "46-55": "GenX",
        "56-65": "Boomer",
        "65+": "Boomer/Silent"
    }

    # Name pools with demographic diversity
    FIRST_NAMES = {
        "male": ["James", "Michael", "David", "Wei", "Carlos", "Mohammed",
                 "Raj", "Brandon", "Tyler", "Andre", "Kenji", "Patrick"],
        "female": ["Sarah", "Jennifer", "Maria", "Priya", "Aisha", "Mei",
                   "Olga", "Jessica", "Fatima", "Yuki", "Grace", "Isabella"],
        "neutral": ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Sam"]
    }

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Chen", "Patel", "Garcia",
        "Kim", "Nguyen", "Martinez", "Anderson", "Thomas", "Jackson",
        "White", "Harris", "Robinson", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Moore", "Taylor", "Brown", "Lee", "Miller"
    ]

    def generate_writer_persona(
        self,
        occupation_title: str,
        job_zone: int,
        company: CompanyContext,
        seed: int
    ) -> WriterPersona:
        """Generate a realistic writer persona for the given context"""
        rng = random.Random(seed)

        # Age/generation correlates loosely with job zone and skill level
        if job_zone <= 2:
            age_range = rng.choice(["18-25", "26-35", "36-45"])
            skill_level = rng.choice(["junior", "mid"])
            years_exp = rng.randint(0, 5)
        elif job_zone == 3:
            age_range = rng.choice(["26-35", "36-45", "46-55"])
            skill_level = rng.choice(["mid", "senior"])
            years_exp = rng.randint(3, 15)
        elif job_zone == 4:
            age_range = rng.choice(["36-45", "46-55", "56-65"])
            skill_level = rng.choice(["senior", "executive"])
            years_exp = rng.randint(10, 25)
        else:  # Zone 5
            age_range = rng.choice(["36-45", "46-55", "56-65", "65+"])
            skill_level = rng.choice(["senior", "executive"])
            years_exp = rng.randint(15, 35)

        gender = rng.choice(["male", "female", "neutral"])
        first_name = rng.choice(self.FIRST_NAMES[gender])
        last_name = rng.choice(self.LAST_NAMES)

        # Generate email
        email_formats = [
            f"{first_name.lower()}.{last_name.lower()}@{company.name.lower().replace(' ', '')}.com",
            f"{first_name[0].lower()}{last_name.lower()}@{company.name.lower().replace(' ', '')}.com",
            f"{first_name.lower()}{last_name[0].lower()}@{company.name.lower().replace(' ', '')}.com",
        ]

        return WriterPersona(
            name=f"{first_name} {last_name}",
            email=rng.choice(email_formats),
            job_title=occupation_title,
            age_range=age_range,
            generation=self.AGE_GENERATION_MAP[age_range],
            skill_level=skill_level,
            years_experience=years_exp,
            english_variant=EnglishVariant.EN_US
        )
```

#### 4.3.2 Context Enrichment via LLM

For complex prompts requiring additional context, use LLM-based enrichment:

```python
class LLMContextEnricher:
    """Uses LLM to add realistic context to prompts"""

    ENRICHMENT_PROMPT_TEMPLATE = """
You are helping create realistic writing task prompts for an evaluation. Given the following task and context, generate additional realistic details.

**Task**: {task_statement}
**Occupation**: {occupation_title}
**Company**: {company_name} ({company_industry})
**Writer**: {writer_name}, {writer_title}

Generate the following (be specific and realistic):

1. **Recipient Details**: Who would realistically receive this communication? Include name, title, relationship.

2. **Scenario Context**: What specific situation makes this writing necessary now? Include any relevant background.

3. **Competing Objectives**: What trade-offs might the writer face? (e.g., be thorough but concise)

4. **Attachments/References**: Would this task realistically reference prior documents? If so, provide mock content.

5. **Temporal Context**: Is timing relevant? If so, add specific dates/deadlines.

6. **Prior Messages**: If this is a reply, what might the prior message have said?

Return as JSON with these exact keys: recipient, scenario, competing_objectives (list), attachments (list), temporal_context, prior_messages (list)
"""

    async def enrich_prompt(
        self,
        task: dict,
        company: CompanyContext,
        writer: WriterPersona,
        client: OpenRouterClient
    ) -> dict:
        """Enrich a prompt with LLM-generated context"""
        prompt = self.ENRICHMENT_PROMPT_TEMPLATE.format(
            task_statement=task["task"],
            occupation_title=task["occupation_title"],
            company_name=company.name,
            company_industry=company.industry,
            writer_name=writer.name,
            writer_title=writer.job_title
        )

        # Use one of the evaluation models (rotating to avoid bias)
        models = ["claude-3-opus", "gpt-4-turbo", "gemini-1.5-pro"]
        model = random.choice(models)

        response = await client.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )

        return json.loads(response.content)
```

#### 4.3.3 Final Prompt Assembly

```python
class PromptAssembler:
    """Assembles all components into final prompt text"""

    PROMPT_TEMPLATE = """
You are {writer_name}, a {writer_title} at {company_name}.

**Your Background:**
- Age: {writer_age_range} ({writer_generation})
- Experience: {writer_years} years in the field
- Skill Level: {writer_skill_level}

**Company Context:**
{company_name} is a {company_size} {company_industry} company headquartered in {company_hq}.
{company_context}

**Your Task:**
{task_statement}

**Recipient(s):**
{recipient_details}

**Communication Context:**
- Channel: {channel}
- Formality: {formality}
- Urgency: {urgency}
- This is: {message_position}
{emotional_context}

{prior_messages_section}

{attachments_section}

{constraints_section}

{competing_objectives_section}

{temporal_context_section}

Write the {communication_type} now. Be authentic to your persona and context.
"""

    def assemble(self, prompt_data: WritingPrompt) -> str:
        """Assemble all prompt components into final text"""

        # Build conditional sections
        prior_messages_section = ""
        if prompt_data.prior_messages:
            prior_messages_section = "**Prior Message(s) in Thread:**\n"
            for i, msg in enumerate(prompt_data.prior_messages):
                prior_messages_section += f"---\n{msg}\n---\n"

        attachments_section = ""
        if prompt_data.attachments:
            attachments_section = "**Referenced Materials:**\n"
            for att in prompt_data.attachments:
                attachments_section += f"[{att.attachment_type.upper()}] {att.description}\n"
                attachments_section += f"{att.content_summary}\n\n"

        constraints_section = ""
        if prompt_data.explicit_constraints:
            constraints_section = "**Specific Requirements:**\n"
            for constraint in prompt_data.explicit_constraints:
                constraints_section += f"- {constraint}\n"

        competing_objectives_section = ""
        if prompt_data.competing_objectives:
            competing_objectives_section = "**Balance These Considerations:**\n"
            for obj in prompt_data.competing_objectives:
                competing_objectives_section += f"- {obj}\n"

        temporal_section = ""
        if prompt_data.temporal_context:
            temporal_section = f"**Timing:** {prompt_data.temporal_context}"

        # Format recipients
        recipient_details = ""
        for r in prompt_data.recipients:
            recipient_details += f"- {r.name}, {r.job_title}"
            if r.company:
                recipient_details += f" at {r.company}"
            recipient_details += f" ({r.relationship_to_writer}, {r.familiarity} relationship)\n"

        # Determine communication type from channel or task
        comm_type = prompt_data.communication_channel or "response"

        return self.PROMPT_TEMPLATE.format(
            writer_name=prompt_data.writer.name,
            writer_title=prompt_data.writer.job_title,
            company_name=prompt_data.company.name,
            writer_age_range=prompt_data.writer.age_range,
            writer_generation=prompt_data.writer.generation,
            writer_years=prompt_data.writer.years_experience,
            writer_skill_level=prompt_data.writer.skill_level,
            company_size=prompt_data.company.size_category,
            company_industry=prompt_data.company.industry,
            company_hq=prompt_data.company.hq_location,
            company_context="",  # Optional additional context
            task_statement=prompt_data.onet_task_statement,
            recipient_details=recipient_details,
            channel=prompt_data.communication_channel or "appropriate format",
            formality=prompt_data.formality_level.value,
            urgency=prompt_data.urgency,
            message_position=prompt_data.message_position.value,
            emotional_context=f"- Emotional Context: {prompt_data.emotional_context.value}" if prompt_data.emotional_context != EmotionalContext.ROUTINE else "",
            prior_messages_section=prior_messages_section,
            attachments_section=attachments_section,
            constraints_section=constraints_section,
            competing_objectives_section=competing_objectives_section,
            temporal_context_section=temporal_section,
            communication_type=comm_type
        )
```

---

## 5. Evaluation Flow and Judging System

### 5.1 Orchestrator Architecture

```python
class EvalOrchestrator:
    """Main orchestrator for evaluation runs"""

    def __init__(
        self,
        config: EvalConfig,
        api_client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        progress_callback: Optional[Callable] = None
    ):
        self.config = config
        self.api_client = api_client
        self.checkpoint = checkpoint_manager
        self.progress_callback = progress_callback

    async def run(self) -> EvalRunResult:
        """Execute full evaluation run"""
        # Phase 1: Load or generate prompts
        prompts = await self._load_or_generate_prompts()

        # Phase 2: Collect responses
        for model_pair in self.config.model_pairs:
            await self._evaluate_pair(prompts, model_pair)

        # Phase 3: Analyze results
        analysis = await self._run_analysis()

        # Phase 4: Generate report
        report = await self._generate_report(analysis)

        return EvalRunResult(prompts=prompts, analysis=analysis, report=report)

    async def _evaluate_pair(
        self,
        prompts: list[WritingPrompt],
        model_pair: ModelPair
    ):
        """Evaluate one model pair across all prompts"""
        for prompt in prompts:
            # Check if already completed (for resume)
            if self.checkpoint.is_completed(prompt.prompt_id, model_pair):
                continue

            try:
                # Step 1: Get responses from both models
                responses = await self._collect_responses(prompt, model_pair)

                # Step 2: Create comparison pair with shuffled ordering
                pair = self._create_response_pair(prompt, responses, model_pair)

                # Step 3: Run judging
                result = await self._judge_pair(prompt, pair)

                # Step 4: Save result
                await self.checkpoint.save_comparison(result)

                # Step 5: Update progress
                if self.progress_callback:
                    self.progress_callback(prompt.prompt_id, result)

            except Exception as e:
                await self.checkpoint.log_failure(prompt.prompt_id, model_pair, e)
```

### 5.2 Response Collection

```python
class ResponseCollector:
    """Collects responses from models with retry handling"""

    def __init__(
        self,
        client: OpenRouterClient,
        retry_handler: RetryHandler,
        timeout_ms: int = 60000
    ):
        self.client = client
        self.retry_handler = retry_handler
        self.timeout_ms = timeout_ms

    async def collect(
        self,
        prompt: WritingPrompt,
        model_id: str
    ) -> ModelResponse:
        """Collect response from a single model"""

        start_time = time.time()

        try:
            response = await self.retry_handler.execute_with_retry(
                lambda: self.client.complete(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt.assembled_prompt}],
                    max_tokens=4000,
                    temperature=0.7
                ),
                max_retries=3,
                timeout_ms=self.timeout_ms
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # Analyze response
            analysis = self._analyze_response(response.content)

            return ModelResponse(
                response_id=f"{prompt.prompt_id}_{model_id}_{int(time.time())}",
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                model_display_name=MODEL_DISPLAY_NAMES.get(model_id, model_id),
                response_text=response.content,
                response_time_ms=response_time_ms,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                **analysis,
                is_refusal=self._detect_refusal(response.content),
                refusal_category=self._categorize_refusal(response.content),
                raw_api_response=response.raw,
                timestamp=datetime.now()
            )

        except Exception as e:
            # Return error response
            return ModelResponse(
                response_id=f"{prompt.prompt_id}_{model_id}_error",
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                model_display_name=MODEL_DISPLAY_NAMES.get(model_id, model_id),
                response_text="[ERROR: Failed to get response]",
                response_time_ms=-1,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                word_count=0,
                character_count=0,
                has_bullet_points=False,
                has_headers=False,
                has_greeting=False,
                has_signoff=False,
                paragraph_count=0,
                is_refusal=True,
                refusal_category="api_error",
                raw_api_response={"error": str(e)},
                timestamp=datetime.now()
            )

    def _analyze_response(self, text: str) -> dict:
        """Analyze response format and structure"""
        return {
            "word_count": len(text.split()),
            "character_count": len(text),
            "has_bullet_points": bool(re.search(r'^[\s]*[-*•]', text, re.MULTILINE)),
            "has_headers": bool(re.search(r'^#+\s|^[A-Z][^.!?]*:\s*$', text, re.MULTILINE)),
            "has_greeting": bool(re.search(r'^(Dear|Hi|Hello|Hey|Good\s)', text, re.IGNORECASE)),
            "has_signoff": bool(re.search(r'(Sincerely|Best|Regards|Thanks|Cheers)\s*,?\s*$', text, re.IGNORECASE | re.MULTILINE)),
            "paragraph_count": len([p for p in text.split('\n\n') if p.strip()])
        }

    def _detect_refusal(self, text: str) -> bool:
        """Detect if response is a refusal"""
        refusal_patterns = [
            r"I cannot|I can't|I am unable|I'm unable",
            r"I apologize, but|Sorry, but I cannot",
            r"against my guidelines|violates my policies",
            r"I don't feel comfortable"
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in refusal_patterns)

    def _categorize_refusal(self, text: str) -> Optional[str]:
        """Categorize the type of refusal"""
        if not self._detect_refusal(text):
            return None

        if re.search(r"safety|harmful|inappropriate", text, re.IGNORECASE):
            return "safety"
        elif re.search(r"cannot|unable|don't have", text, re.IGNORECASE):
            return "capability"
        elif re.search(r"clarify|unclear|more information", text, re.IGNORECASE):
            return "misunderstanding"
        else:
            return "other"
```

### 5.3 Judging Module

```python
class JudgeModule:
    """Handles all judging logic with ensemble voting"""

    JUDGE_PROMPT_TEMPLATE = """
You are evaluating two writing responses for the same task. You are acting as a {judge_persona}.

## TASK CONTEXT

**Writing Task:**
{task_statement}

**Writer Persona:**
- Name: {writer_name}
- Role: {writer_title} at {company_name}
- Age/Generation: {writer_age} ({writer_generation})
- Skill Level: {writer_skill_level}

**Recipient(s):**
{recipient_details}

**Communication Context:**
- Formality: {formality}
- Urgency: {urgency}
- Message Type: {message_type}

{additional_context}

---

## RESPONSE A

{response_a}

---

## RESPONSE B

{response_b}

---

## YOUR EVALUATION

As a {judge_persona}, evaluate which response is better for THIS SPECIFIC scenario.

{persona_specific_instructions}

Rate each response on these criteria (1-5 scale):

1. **Quality of Writing** (grammar, clarity, structure)
2. **Tone Appropriateness** (matches the scenario requirements)
3. **Length Appropriateness** (right length for this task)
4. **Effectiveness** (achieves the communication goal)
5. **Authenticity** (reads like realistic human writing from this persona, not AI-generated)
6. **Cliche Avoidance** (avoids generic AI patterns like "I hope this email finds you well")
{instruction_compliance_line}

Provide your scores and reasoning, then give your final verdict: A, B, or TIE.

Return as JSON:
{{
    "reasoning": "...",
    "quality_a": X, "quality_b": X,
    "tone_a": X, "tone_b": X,
    "length_a": X, "length_b": X,
    "effectiveness_a": X, "effectiveness_b": X,
    "authenticity_a": X, "authenticity_b": X,
    "cliche_a": X, "cliche_b": X,
    {instruction_compliance_json}
    "verdict": "A" | "B" | "TIE"
}}
"""

    PERSONA_INSTRUCTIONS = {
        JudgePersona.WRITING_EXPERT: """
As a **Writing Expert**, focus on:
- Craft quality: Is the writing technically excellent?
- Appropriate register: Does the formality match the context?
- Structure: Is information organized logically?
- Concision: Is it the right length without padding or missing key points?
- Professional standards: Would this pass review in a professional context?
""",
        JudgePersona.TARGET_RECIPIENT: """
As the **Target Recipient** of this communication:
- Would you understand the message clearly?
- Would you feel the tone is appropriate for your relationship with the writer?
- Would you be able to take action based on this message?
- Does it feel authentic and human, or robotic and AI-generated?
- Would you feel respected and considered as the audience?
"""
    }

    async def judge_pair(
        self,
        prompt: WritingPrompt,
        pair: ResponsePair,
        judge_model_id: str,
        judge_persona: JudgePersona,
        vote_index: int
    ) -> SingleJudgment:
        """Execute a single judgment vote"""

        # Build judge prompt
        judge_prompt = self._build_judge_prompt(prompt, pair, judge_persona)

        # Get judgment
        response = await self.client.complete(
            model=judge_model_id,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.3,  # Lower temperature for more consistent judging
            max_tokens=1000
        )

        # Parse response
        result = json.loads(response.content)

        return SingleJudgment(
            judgment_id=f"{pair.pair_id}_{judge_model_id}_{judge_persona.value}_{vote_index}",
            pair_id=pair.pair_id,
            judge_model_id=judge_model_id,
            judge_persona=judge_persona,
            vote_index=vote_index,
            verdict=JudgeVerdict(result["verdict"]),
            reasoning=result["reasoning"],
            quality_score_a=result["quality_a"],
            quality_score_b=result["quality_b"],
            tone_appropriateness_a=result["tone_a"],
            tone_appropriateness_b=result["tone_b"],
            length_appropriateness_a=result["length_a"],
            length_appropriateness_b=result["length_b"],
            effectiveness_a=result["effectiveness_a"],
            effectiveness_b=result["effectiveness_b"],
            authenticity_a=result["authenticity_a"],
            authenticity_b=result["authenticity_b"],
            cliche_avoidance_a=result["cliche_a"],
            cliche_avoidance_b=result["cliche_b"],
            instruction_compliance_a=result.get("compliance_a"),
            instruction_compliance_b=result.get("compliance_b"),
            response_time_ms=int(response.response_time * 1000),
            timestamp=datetime.now()
        )
```

### 5.4 Vote Aggregation (Majority of Majorities)

```python
class VoteAggregator:
    """Implements majority-of-majorities voting logic"""

    def aggregate_judge_votes(
        self,
        judgments: list[SingleJudgment]
    ) -> JudgeModelResult:
        """Aggregate 5 votes from one judge model into majority verdict"""

        # Count votes
        vote_counts = {
            JudgeVerdict.RESPONSE_A_WINS: 0,
            JudgeVerdict.RESPONSE_B_WINS: 0,
            JudgeVerdict.TIE: 0
        }

        for j in judgments:
            vote_counts[j.verdict] += 1

        # Determine majority
        if vote_counts[JudgeVerdict.RESPONSE_A_WINS] >= 3:
            majority = JudgeVerdict.RESPONSE_A_WINS
        elif vote_counts[JudgeVerdict.RESPONSE_B_WINS] >= 3:
            majority = JudgeVerdict.RESPONSE_B_WINS
        else:
            majority = JudgeVerdict.TIE

        return JudgeModelResult(
            judge_model_id=judgments[0].judge_model_id,
            judge_persona=judgments[0].judge_persona,
            pair_id=judgments[0].pair_id,
            individual_votes=[j.verdict for j in judgments],
            majority_verdict=majority,
            vote_count_a=vote_counts[JudgeVerdict.RESPONSE_A_WINS],
            vote_count_b=vote_counts[JudgeVerdict.RESPONSE_B_WINS],
            vote_count_tie=vote_counts[JudgeVerdict.TIE]
        )

    def aggregate_ensemble(
        self,
        judge_results: list[JudgeModelResult],
        pair: ResponsePair
    ) -> ComparisonResult:
        """Aggregate across 3 judge models for final verdict"""

        # Count judge majorities
        judges_for_a = sum(1 for r in judge_results
                          if r.majority_verdict == JudgeVerdict.RESPONSE_A_WINS)
        judges_for_b = sum(1 for r in judge_results
                          if r.majority_verdict == JudgeVerdict.RESPONSE_B_WINS)
        judges_tie = sum(1 for r in judge_results
                        if r.majority_verdict == JudgeVerdict.TIE)

        # Final verdict
        if judges_for_a >= 2:
            final = JudgeVerdict.RESPONSE_A_WINS
        elif judges_for_b >= 2:
            final = JudgeVerdict.RESPONSE_B_WINS
        else:
            final = JudgeVerdict.TIE

        # Convert to Gemini win/loss based on position
        if pair.gemini_position == "A":
            gemini_wins = final == JudgeVerdict.RESPONSE_A_WINS
            opponent_wins = final == JudgeVerdict.RESPONSE_B_WINS
        else:
            gemini_wins = final == JudgeVerdict.RESPONSE_B_WINS
            opponent_wins = final == JudgeVerdict.RESPONSE_A_WINS

        return ComparisonResult(
            comparison_id=f"cmp_{pair.pair_id}_{int(time.time())}",
            pair_id=pair.pair_id,
            prompt_id=pair.prompt_id,
            gemini_model_id=pair.response_a.model_id if pair.gemini_position == "A" else pair.response_b.model_id,
            opponent_model_id=pair.response_b.model_id if pair.gemini_position == "A" else pair.response_a.model_id,
            judge_results=judge_results,
            final_verdict=final,
            judges_for_gemini=judges_for_a if pair.gemini_position == "A" else judges_for_b,
            judges_for_opponent=judges_for_b if pair.gemini_position == "A" else judges_for_a,
            judges_tie=judges_tie,
            unanimous=(judges_for_a == 3 or judges_for_b == 3 or judges_tie == 3)
        )
```

---

## 6. Results Storage and Analysis

### 6.1 SQLite Database Schema

```sql
-- Core tables for results storage
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    config_json TEXT NOT NULL,
    preset_name TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed, paused
    total_prompts INTEGER,
    completed_prompts INTEGER DEFAULT 0,
    random_seed INTEGER
);

CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES eval_runs(run_id),
    onet_task_id TEXT NOT NULL,
    onet_task_statement TEXT NOT NULL,
    onet_occupation_code TEXT NOT NULL,
    onet_occupation_title TEXT NOT NULL,
    onet_job_zone INTEGER,
    soc_major_group TEXT,
    company_name TEXT,
    company_industry TEXT,
    company_naics TEXT,
    company_size TEXT,
    writer_name TEXT,
    writer_title TEXT,
    writer_age_range TEXT,
    writer_generation TEXT,
    writer_skill_level TEXT,
    formality_level TEXT,
    message_position TEXT,
    audience_size TEXT,
    emotional_context TEXT,
    urgency TEXT,
    communication_channel TEXT,
    inferred_writing_category TEXT,
    is_revision_task BOOLEAN DEFAULT FALSE,
    is_ambiguous_task BOOLEAN DEFAULT FALSE,
    has_instruction_constraints BOOLEAN DEFAULT FALSE,
    sensitive_topic_tags TEXT,  -- JSON array
    assembled_prompt TEXT NOT NULL,
    generation_seed INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    model_id TEXT NOT NULL,
    model_display_name TEXT,
    response_text TEXT NOT NULL,
    response_time_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    word_count INTEGER,
    character_count INTEGER,
    has_bullet_points BOOLEAN,
    has_headers BOOLEAN,
    has_greeting BOOLEAN,
    has_signoff BOOLEAN,
    paragraph_count INTEGER,
    is_refusal BOOLEAN DEFAULT FALSE,
    refusal_category TEXT,
    is_incomplete BOOLEAN DEFAULT FALSE,
    is_off_topic BOOLEAN DEFAULT FALSE,
    raw_api_response TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE response_pairs (
    pair_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    response_a_id TEXT REFERENCES responses(response_id),
    response_b_id TEXT REFERENCES responses(response_id),
    gemini_position TEXT CHECK (gemini_position IN ('A', 'B')),
    shuffle_seed INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    pair_id TEXT REFERENCES response_pairs(pair_id),
    judge_model_id TEXT NOT NULL,
    judge_persona TEXT NOT NULL,  -- 'writing_expert' or 'target_recipient'
    vote_index INTEGER NOT NULL,
    verdict TEXT CHECK (verdict IN ('A', 'B', 'TIE')),
    reasoning TEXT,
    quality_score_a INTEGER,
    quality_score_b INTEGER,
    tone_appropriateness_a INTEGER,
    tone_appropriateness_b INTEGER,
    length_appropriateness_a INTEGER,
    length_appropriateness_b INTEGER,
    effectiveness_a INTEGER,
    effectiveness_b INTEGER,
    authenticity_a INTEGER,
    authenticity_b INTEGER,
    cliche_avoidance_a INTEGER,
    cliche_avoidance_b INTEGER,
    instruction_compliance_a INTEGER,
    instruction_compliance_b INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comparison_results (
    comparison_id TEXT PRIMARY KEY,
    pair_id TEXT REFERENCES response_pairs(pair_id),
    prompt_id TEXT REFERENCES prompts(prompt_id),
    gemini_model_id TEXT NOT NULL,
    opponent_model_id TEXT NOT NULL,
    final_verdict TEXT CHECK (final_verdict IN ('A', 'B', 'TIE')),
    gemini_verdict TEXT CHECK (gemini_verdict IN ('WIN', 'LOSS', 'TIE')),
    judges_for_gemini INTEGER,
    judges_for_opponent INTEGER,
    judges_tie INTEGER,
    unanimous BOOLEAN,
    gemini_auto_loss BOOLEAN DEFAULT FALSE,
    opponent_auto_loss BOOLEAN DEFAULT FALSE,
    auto_loss_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onet_occupation_code);
CREATE INDEX idx_prompts_industry ON prompts(company_naics);
CREATE INDEX idx_prompts_job_zone ON prompts(onet_job_zone);
CREATE INDEX idx_prompts_category ON prompts(inferred_writing_category);
CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model_id);
CREATE INDEX idx_judgments_pair ON judgments(pair_id);
CREATE INDEX idx_judgments_judge ON judgments(judge_model_id);
CREATE INDEX idx_comparisons_models ON comparison_results(gemini_model_id, opponent_model_id);
CREATE INDEX idx_comparisons_verdict ON comparison_results(gemini_verdict);

-- View for aggregate win rates
CREATE VIEW win_rate_summary AS
SELECT
    gemini_model_id,
    opponent_model_id,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN gemini_verdict = 'WIN' THEN 1 ELSE 0 END) as gemini_wins,
    SUM(CASE WHEN gemini_verdict = 'LOSS' THEN 1 ELSE 0 END) as opponent_wins,
    SUM(CASE WHEN gemini_verdict = 'TIE' THEN 1 ELSE 0 END) as ties,
    ROUND(100.0 * SUM(CASE WHEN gemini_verdict = 'WIN' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
    ROUND(100.0 * SUM(CASE WHEN gemini_verdict = 'TIE' THEN 1 ELSE 0 END) / COUNT(*), 2) as tie_rate
FROM comparison_results
GROUP BY gemini_model_id, opponent_model_id;
```

### 6.2 Analysis Engine

```python
class AnalysisEngine:
    """Computes all statistical analysis on evaluation results"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def compute_win_rates(self) -> dict[str, WinRateResult]:
        """Compute win rates with confidence intervals for all model pairs"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT gemini_model_id, opponent_model_id,
                       COUNT(*) as n,
                       SUM(CASE WHEN gemini_verdict = 'WIN' THEN 1 ELSE 0 END) as wins
                FROM comparison_results
                GROUP BY gemini_model_id, opponent_model_id
            """)
            rows = await cursor.fetchall()

        results = {}
        for gemini_id, opponent_id, n, wins in rows:
            win_rate = wins / n
            # Wilson score interval for binomial proportion
            ci_low, ci_high = self._wilson_ci(wins, n)

            results[f"{gemini_id}_vs_{opponent_id}"] = WinRateResult(
                gemini_model=gemini_id,
                opponent_model=opponent_id,
                total_comparisons=n,
                gemini_wins=wins,
                win_rate=win_rate,
                ci_low=ci_low,
                ci_high=ci_high
            )
        return results

    def _wilson_ci(self, wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
        """Calculate Wilson score confidence interval"""
        if n == 0:
            return (0, 0)

        p = wins / n
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denominator
        spread = z * math.sqrt((p*(1-p) + z**2/(4*n)) / n) / denominator

        return (max(0, center - spread), min(1, center + spread))

    async def compute_win_rates_by_dimension(
        self,
        dimension: str  # 'occupation', 'industry', 'job_zone', 'formality', 'category'
    ) -> dict[str, dict[str, WinRateResult]]:
        """Compute win rates broken down by a specific dimension"""
        dimension_col = {
            'occupation': 'p.onet_occupation_code',
            'industry': 'p.company_naics',
            'job_zone': 'p.onet_job_zone',
            'formality': 'p.formality_level',
            'category': 'p.inferred_writing_category',
            'generation': 'p.writer_generation',
            'urgency': 'p.urgency'
        }[dimension]

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                SELECT {dimension_col} as dim_value,
                       cr.gemini_model_id, cr.opponent_model_id,
                       COUNT(*) as n,
                       SUM(CASE WHEN cr.gemini_verdict = 'WIN' THEN 1 ELSE 0 END) as wins
                FROM comparison_results cr
                JOIN prompts p ON cr.prompt_id = p.prompt_id
                GROUP BY dim_value, cr.gemini_model_id, cr.opponent_model_id
            """)
            rows = await cursor.fetchall()

        results = defaultdict(dict)
        for dim_val, gemini_id, opponent_id, n, wins in rows:
            win_rate = wins / n
            ci_low, ci_high = self._wilson_ci(wins, n)
            key = f"{gemini_id}_vs_{opponent_id}"
            results[str(dim_val)][key] = WinRateResult(
                gemini_model=gemini_id,
                opponent_model=opponent_id,
                total_comparisons=n,
                gemini_wins=wins,
                win_rate=win_rate,
                ci_low=ci_low,
                ci_high=ci_high
            )
        return dict(results)

    async def compute_inter_judge_agreement(self) -> JudgeAgreementStats:
        """Calculate Cohen's Kappa for inter-judge agreement"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get all judge verdicts grouped by pair
            cursor = await db.execute("""
                SELECT pair_id, judge_model_id, verdict
                FROM judgments
                WHERE vote_index = 0  -- Use first vote for agreement calc
                ORDER BY pair_id, judge_model_id
            """)
            rows = await cursor.fetchall()

        # Build verdict matrix
        pairs = defaultdict(dict)
        for pair_id, judge_id, verdict in rows:
            pairs[pair_id][judge_id] = verdict

        # Calculate pairwise Kappa for each judge pair
        judge_ids = list(set(r[1] for r in rows))
        kappa_scores = {}

        for i, j1 in enumerate(judge_ids):
            for j2 in judge_ids[i+1:]:
                verdicts_1 = []
                verdicts_2 = []
                for pair_id, judges in pairs.items():
                    if j1 in judges and j2 in judges:
                        verdicts_1.append(judges[j1])
                        verdicts_2.append(judges[j2])

                kappa = self._cohens_kappa(verdicts_1, verdicts_2)
                kappa_scores[f"{j1}_vs_{j2}"] = kappa

        avg_kappa = sum(kappa_scores.values()) / len(kappa_scores) if kappa_scores else 0

        return JudgeAgreementStats(
            pairwise_kappa=kappa_scores,
            average_kappa=avg_kappa,
            interpretation=self._interpret_kappa(avg_kappa)
        )

    def _cohens_kappa(self, y1: list, y2: list) -> float:
        """Calculate Cohen's Kappa statistic"""
        if len(y1) != len(y2) or len(y1) == 0:
            return 0.0

        categories = list(set(y1 + y2))
        n = len(y1)

        # Build confusion matrix
        matrix = defaultdict(lambda: defaultdict(int))
        for v1, v2 in zip(y1, y2):
            matrix[v1][v2] += 1

        # Calculate observed agreement
        observed = sum(matrix[c][c] for c in categories) / n

        # Calculate expected agreement
        expected = 0
        for c in categories:
            p1 = sum(1 for v in y1 if v == c) / n
            p2 = sum(1 for v in y2 if v == c) / n
            expected += p1 * p2

        if expected == 1:
            return 1.0

        return (observed - expected) / (1 - expected)

    def _interpret_kappa(self, kappa: float) -> str:
        """Interpret Kappa value"""
        if kappa < 0:
            return "Poor (worse than chance)"
        elif kappa < 0.2:
            return "Slight agreement"
        elif kappa < 0.4:
            return "Fair agreement"
        elif kappa < 0.6:
            return "Moderate agreement"
        elif kappa < 0.8:
            return "Substantial agreement"
        else:
            return "Almost perfect agreement"

    async def detect_biases(self) -> BiasReport:
        """Detect systematic biases in models and judges"""

        position_bias = await self._detect_position_bias()
        length_bias = await self._detect_length_bias()
        judge_model_bias = await self._detect_judge_model_bias()

        return BiasReport(
            position_bias=position_bias,
            length_bias=length_bias,
            judge_model_bias=judge_model_bias
        )

    async def _detect_position_bias(self) -> PositionBiasResult:
        """Check if judges systematically prefer position A or B"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT verdict, COUNT(*) as count
                FROM judgments
                GROUP BY verdict
            """)
            rows = await cursor.fetchall()

        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        a_rate = counts.get('A', 0) / total
        b_rate = counts.get('B', 0) / total

        # Chi-square test for significant difference
        expected = total / 3
        chi_sq = sum((counts.get(v, 0) - expected)**2 / expected for v in ['A', 'B', 'TIE'])
        p_value = 1 - stats.chi2.cdf(chi_sq, df=2)

        return PositionBiasResult(
            a_preference_rate=a_rate,
            b_preference_rate=b_rate,
            chi_square=chi_sq,
            p_value=p_value,
            significant=p_value < 0.05
        )

    async def identify_weaknesses(self) -> list[WeaknessArea]:
        """Identify specific areas where Gemini underperforms"""
        weaknesses = []

        # Check by writing category
        category_rates = await self.compute_win_rates_by_dimension('category')
        for category, model_rates in category_rates.items():
            for pair_key, result in model_rates.items():
                if result.win_rate < 0.45 and result.total_comparisons >= 10:
                    weaknesses.append(WeaknessArea(
                        dimension='writing_category',
                        value=category,
                        model_pair=pair_key,
                        win_rate=result.win_rate,
                        sample_size=result.total_comparisons,
                        ci_low=result.ci_low,
                        ci_high=result.ci_high
                    ))

        # Check by occupation
        occupation_rates = await self.compute_win_rates_by_dimension('occupation')
        for occupation, model_rates in occupation_rates.items():
            for pair_key, result in model_rates.items():
                if result.win_rate < 0.40 and result.total_comparisons >= 5:
                    weaknesses.append(WeaknessArea(
                        dimension='occupation',
                        value=occupation,
                        model_pair=pair_key,
                        win_rate=result.win_rate,
                        sample_size=result.total_comparisons,
                        ci_low=result.ci_low,
                        ci_high=result.ci_high
                    ))

        # Sort by win rate (worst first)
        weaknesses.sort(key=lambda w: w.win_rate)

        return weaknesses
```

---

## 7. TUI Implementation

### 7.1 Progress Dashboard (Live Evaluation View)

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive

class EvalProgressApp(App):
    """Live progress dashboard for evaluation runs"""

    CSS = """
    #overall-progress {
        height: 5;
        border: solid green;
        margin: 1;
    }

    #model-pairs {
        height: auto;
        max-height: 12;
        border: solid blue;
        margin: 1;
    }

    #current-batch {
        height: 10;
        border: solid cyan;
        margin: 1;
    }

    #statistics {
        height: 8;
        border: solid yellow;
        margin: 1;
    }

    #activity-log {
        height: 8;
        border: solid magenta;
        margin: 1;
    }

    .win-rate {
        color: green;
    }

    .loss-rate {
        color: red;
    }
    """

    BINDINGS = [
        ("q", "quit_safely", "Quit (save checkpoint)"),
        ("p", "pause", "Pause"),
        ("d", "toggle_detail", "Detail View"),
        ("s", "show_stats", "Full Stats"),
    ]

    # Reactive properties for live updates
    total_prompts = reactive(0)
    completed_prompts = reactive(0)
    current_phase = reactive("Initializing")
    elapsed_seconds = reactive(0)
    estimated_remaining = reactive(0)
    current_cost = reactive(0.0)

    def __init__(self, orchestrator: EvalOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.model_pair_progress = {}
        self.running_win_rates = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            self._make_overall_progress(),
            self._make_model_pairs_panel(),
            Horizontal(
                self._make_current_batch_panel(),
                self._make_statistics_panel(),
            ),
            self._make_activity_log(),
        )
        yield Footer()

    def _make_overall_progress(self) -> Container:
        return Container(
            Static("OVERALL PROGRESS", classes="section-title"),
            ProgressBar(total=100, show_eta=True),
            Static(id="phase-indicator"),
            id="overall-progress"
        )

    def _make_model_pairs_panel(self) -> Container:
        table = DataTable(id="pairs-table")
        table.add_columns("Model Pair", "Progress", "Win Rate", "Status")
        return Container(
            Static("MODEL PAIRS"),
            table,
            id="model-pairs"
        )

    def _make_current_batch_panel(self) -> Container:
        return Container(
            Static("CURRENT BATCH"),
            Static(id="current-prompt"),
            Static(id="current-occupation"),
            Horizontal(
                Static(id="response-status"),
                Static(id="judging-status"),
            ),
            id="current-batch"
        )

    def _make_statistics_panel(self) -> Container:
        return Container(
            Static("LIVE STATISTICS"),
            Static(id="win-rates-summary"),
            Static(id="performance-stats"),
            Static(id="cost-tracker"),
            id="statistics"
        )

    def _make_activity_log(self) -> Container:
        return Container(
            Static("RECENT ACTIVITY"),
            Log(id="activity", max_lines=100),
            id="activity-log"
        )

    def watch_completed_prompts(self, value: int) -> None:
        """Update progress bar when completed_prompts changes"""
        if self.total_prompts > 0:
            progress = (value / self.total_prompts) * 100
            self.query_one(ProgressBar).update(progress=progress)

    async def on_eval_progress(self, event: EvalProgressEvent) -> None:
        """Handle progress updates from orchestrator"""
        self.completed_prompts = event.completed
        self.current_phase = event.phase

        # Update model pair progress
        pair_key = f"{event.gemini_model}_vs_{event.opponent_model}"
        self.model_pair_progress[pair_key] = event.pair_progress

        # Update running win rate
        if event.result:
            self._update_running_win_rate(pair_key, event.result)

        # Log activity
        log = self.query_one("#activity", Log)
        log.write_line(
            f"{event.timestamp:%H:%M:%S}  "
            f"{'✓' if event.success else '✗'}  "
            f"Prompt #{event.prompt_index}: {event.summary}"
        )

    def action_quit_safely(self) -> None:
        """Graceful quit with checkpoint save"""
        self.orchestrator.request_pause()
        self.exit(message="Checkpoint saved. Run --resume to continue.")

    def action_pause(self) -> None:
        """Toggle pause state"""
        if self.orchestrator.is_paused:
            self.orchestrator.resume()
        else:
            self.orchestrator.request_pause()
```

### 7.2 Results Browser (Post-Evaluation View)

```python
class ResultsBrowserApp(App):
    """Interactive browser for evaluation results"""

    CSS = """
    #filters {
        height: 5;
        dock: top;
    }

    #results-table {
        height: 1fr;
    }

    #detail-panel {
        height: 40%;
        dock: bottom;
        display: none;
    }

    #detail-panel.visible {
        display: block;
    }

    .response-a {
        border: solid blue;
        width: 50%;
    }

    .response-b {
        border: solid green;
        width: 50%;
    }
    """

    BINDINGS = [
        ("f", "show_filters", "Filters"),
        ("enter", "show_detail", "View Detail"),
        ("j", "show_judgments", "View Judgments"),
        ("e", "export", "Export CSV"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.current_filters = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            self._make_filter_bar(),
            self._make_results_table(),
            self._make_detail_panel(),
        )
        yield Footer()

    def _make_filter_bar(self) -> Container:
        return Container(
            Horizontal(
                Select(options=self._get_occupation_options(), id="filter-occupation"),
                Select(options=self._get_industry_options(), id="filter-industry"),
                Select(options=self._get_verdict_options(), id="filter-verdict"),
                Select(options=self._get_model_options(), id="filter-model"),
                Button("Apply", id="apply-filters"),
                Button("Clear", id="clear-filters"),
            ),
            id="filters"
        )

    def _make_results_table(self) -> DataTable:
        table = DataTable(id="results-table", cursor_type="row")
        table.add_columns(
            "Prompt ID",
            "Occupation",
            "Industry",
            "Gemini",
            "Opponent",
            "Verdict",
            "Judges",
            "Category"
        )
        return table

    def _make_detail_panel(self) -> Container:
        return Container(
            Horizontal(
                Vertical(
                    Static("Response A (Gemini)", classes="response-header"),
                    Static(id="response-a-content"),
                    classes="response-a"
                ),
                Vertical(
                    Static("Response B (Opponent)", classes="response-header"),
                    Static(id="response-b-content"),
                    classes="response-b"
                ),
            ),
            id="detail-panel"
        )

    async def load_results(self, filters: dict = None) -> None:
        """Load results from database with optional filters"""
        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT cr.comparison_id, p.prompt_id, p.onet_occupation_title,
                       p.company_industry, cr.gemini_model_id, cr.opponent_model_id,
                       cr.gemini_verdict, cr.judges_for_gemini, cr.judges_for_opponent,
                       p.inferred_writing_category
                FROM comparison_results cr
                JOIN prompts p ON cr.prompt_id = p.prompt_id
            """

            where_clauses = []
            params = []

            if filters:
                if filters.get('occupation'):
                    where_clauses.append("p.onet_occupation_code = ?")
                    params.append(filters['occupation'])
                if filters.get('industry'):
                    where_clauses.append("p.company_naics = ?")
                    params.append(filters['industry'])
                if filters.get('verdict'):
                    where_clauses.append("cr.gemini_verdict = ?")
                    params.append(filters['verdict'])

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            query += " ORDER BY cr.created_at DESC LIMIT 1000"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        table = self.query_one("#results-table", DataTable)
        table.clear()
        for row in rows:
            verdict_display = {
                "WIN": "[green]WIN[/]",
                "LOSS": "[red]LOSS[/]",
                "TIE": "[yellow]TIE[/]"
            }.get(row[6], row[6])

            judges_display = f"{row[7]}-{row[8]}"

            table.add_row(
                row[1][:12],  # Prompt ID
                row[2][:25],  # Occupation
                row[3][:20],  # Industry
                row[4].split("/")[-1],  # Gemini model
                row[5].split("/")[-1],  # Opponent model
                verdict_display,
                judges_display,
                row[9][:15]   # Category
            )

    async def action_show_detail(self) -> None:
        """Show side-by-side response detail for selected row"""
        table = self.query_one("#results-table", DataTable)
        row = table.get_row_at(table.cursor_row)

        if not row:
            return

        prompt_id = row[0]

        # Load full responses
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT r.model_id, r.response_text
                FROM responses r
                WHERE r.prompt_id = ?
            """, (prompt_id,))
            responses = await cursor.fetchall()

        # Display in detail panel
        detail_panel = self.query_one("#detail-panel")
        detail_panel.add_class("visible")

        for model_id, text in responses:
            if "gemini" in model_id.lower():
                self.query_one("#response-a-content").update(text[:2000])
            else:
                self.query_one("#response-b-content").update(text[:2000])
```

---

## 8. Configuration and Presets

### 8.1 Configuration Schema

```python
class ModelConfig(BaseModel):
    """Configuration for a single model"""
    model_id: str  # OpenRouter model ID
    display_name: str
    tier: Literal["pro", "flash"]
    is_gemini: bool = False
    input_cost_per_1k: float  # USD per 1000 tokens
    output_cost_per_1k: float

class JudgeConfig(BaseModel):
    """Configuration for judging"""
    judge_models: list[str] = [
        "anthropic/claude-3-opus",
        "openai/gpt-5.2",
        "google/gemini-3-pro"
    ]
    votes_per_judge: int = 5
    judge_personas: list[JudgePersona] = [
        JudgePersona.WRITING_EXPERT,
        JudgePersona.TARGET_RECIPIENT
    ]
    temperature: float = 0.3

class SamplingConfig(BaseModel):
    """Configuration for prompt sampling"""
    num_prompts: int
    random_seed: Optional[int] = None

    # Filters
    occupations: Optional[list[str]] = None  # O*NET codes
    industries: Optional[list[str]] = None   # NAICS codes
    job_zones: Optional[list[int]] = None    # 1-5
    writing_categories: Optional[list[str]] = None

    # Stratification
    stratify: bool = True
    max_per_occupation: Optional[int] = None
    max_per_industry: Optional[int] = None

class EvalConfig(BaseModel):
    """Complete evaluation configuration"""
    # Identity
    run_name: Optional[str] = None
    preset_name: Optional[str] = None

    # Models
    gemini_pro_model: str = "google/gemini-3-pro"
    gemini_flash_model: str = "google/gemini-3-flash"
    pro_tier_opponents: list[str] = [
        "openai/gpt-5.2-thinking",
        "anthropic/claude-opus-4.5",
        "x-ai/grok-4.1-thinking",
        "moonshot/kimi-k2-thinking"
    ]
    flash_tier_opponents: list[str] = [
        "openai/gpt-4.1",
        "anthropic/claude-sonnet"
    ]
    run_pro_tier: bool = True
    run_flash_tier: bool = True

    # Judging
    judge_config: JudgeConfig = JudgeConfig()

    # Sampling
    sampling_config: SamplingConfig

    # Execution
    max_concurrent_requests: int = 10
    request_timeout_ms: int = 60000
    max_retries: int = 3

    # Output
    output_dir: str = "results"
```

### 8.2 Preset Definitions

```python
EVAL_PRESETS = {
    1: EvalConfig(
        preset_name="Sanity Check",
        sampling_config=SamplingConfig(num_prompts=5),
        pro_tier_opponents=["openai/gpt-5.2-thinking"],
        flash_tier_opponents=[],
        run_flash_tier=False,
        judge_config=JudgeConfig(
            judge_models=["anthropic/claude-3-opus"],
            votes_per_judge=1
        )
    ),
    2: EvalConfig(
        preset_name="Smoke Test",
        sampling_config=SamplingConfig(num_prompts=20),
        pro_tier_opponents=["openai/gpt-5.2-thinking"],
        flash_tier_opponents=[],
        run_flash_tier=False,
        judge_config=JudgeConfig(
            judge_models=["anthropic/claude-3-opus"],
            votes_per_judge=3
        )
    ),
    3: EvalConfig(
        preset_name="Dev Iteration",
        sampling_config=SamplingConfig(num_prompts=50),
        pro_tier_opponents=["openai/gpt-5.2-thinking", "anthropic/claude-opus-4.5"],
        flash_tier_opponents=[],
        run_flash_tier=False,
        judge_config=JudgeConfig(
            judge_models=["anthropic/claude-3-opus", "openai/gpt-5.2"],
            votes_per_judge=3
        )
    ),
    4: EvalConfig(
        preset_name="Quick Sample",
        sampling_config=SamplingConfig(num_prompts=100),
        pro_tier_opponents=["openai/gpt-5.2-thinking", "anthropic/claude-opus-4.5"],
        flash_tier_opponents=[],
        run_flash_tier=False,
        judge_config=JudgeConfig(votes_per_judge=5)
    ),
    5: EvalConfig(
        preset_name="Light Eval",
        sampling_config=SamplingConfig(num_prompts=200),
        pro_tier_opponents=[
            "openai/gpt-5.2-thinking",
            "anthropic/claude-opus-4.5",
            "x-ai/grok-4.1-thinking"
        ],
        judge_config=JudgeConfig(votes_per_judge=3)
    ),
    6: EvalConfig(
        preset_name="Standard Eval",
        sampling_config=SamplingConfig(num_prompts=500),
        judge_config=JudgeConfig(votes_per_judge=5)
    ),
    7: EvalConfig(
        preset_name="Thorough Eval",
        sampling_config=SamplingConfig(num_prompts=1000),
        judge_config=JudgeConfig(votes_per_judge=5)
    ),
    8: EvalConfig(
        preset_name="Comprehensive",
        sampling_config=SamplingConfig(num_prompts=2000),
        judge_config=JudgeConfig(votes_per_judge=5)
    ),
    9: EvalConfig(
        preset_name="Deep Dive",
        sampling_config=SamplingConfig(num_prompts=5000),
        judge_config=JudgeConfig(votes_per_judge=5)
    ),
    10: EvalConfig(
        preset_name="Full Kaboodle",
        sampling_config=SamplingConfig(num_prompts=10000),
        judge_config=JudgeConfig(votes_per_judge=5)
    )
}
```

### 8.3 Cost Estimation

```python
class CostEstimator:
    """Estimates cost and time for evaluation runs"""

    # Current OpenRouter pricing (USD per 1M tokens)
    MODEL_PRICING = {
        "google/gemini-3-pro": {"input": 7.0, "output": 21.0},
        "google/gemini-3-flash": {"input": 0.35, "output": 1.05},
        "openai/gpt-5.2-thinking": {"input": 15.0, "output": 60.0},
        "anthropic/claude-opus-4.5": {"input": 15.0, "output": 75.0},
        "x-ai/grok-4.1-thinking": {"input": 5.0, "output": 15.0},
        "moonshot/kimi-k2-thinking": {"input": 5.0, "output": 15.0},
        "openai/gpt-4.1": {"input": 2.0, "output": 8.0},
        "anthropic/claude-sonnet": {"input": 3.0, "output": 15.0},
    }

    # Estimated tokens per call
    AVG_PROMPT_TOKENS = 1500
    AVG_RESPONSE_TOKENS = 800
    AVG_JUDGE_PROMPT_TOKENS = 3500  # Includes both responses
    AVG_JUDGE_RESPONSE_TOKENS = 400

    def estimate(self, config: EvalConfig) -> CostEstimate:
        """Estimate cost and time for a given configuration"""

        num_prompts = config.sampling_config.num_prompts
        num_model_pairs = self._count_model_pairs(config)
        num_judges = len(config.judge_config.judge_models)
        votes_per_judge = config.judge_config.votes_per_judge
        num_personas = len(config.judge_config.judge_personas)

        # Response generation costs
        total_response_calls = num_prompts * num_model_pairs * 2  # 2 models per pair
        response_input_tokens = total_response_calls * self.AVG_PROMPT_TOKENS
        response_output_tokens = total_response_calls * self.AVG_RESPONSE_TOKENS

        # Judge costs
        total_judge_calls = (
            num_prompts * num_model_pairs *
            num_judges * votes_per_judge * num_personas
        )
        judge_input_tokens = total_judge_calls * self.AVG_JUDGE_PROMPT_TOKENS
        judge_output_tokens = total_judge_calls * self.AVG_JUDGE_RESPONSE_TOKENS

        # Calculate costs by model
        response_cost = self._calculate_response_cost(config, response_input_tokens, response_output_tokens)
        judge_cost = self._calculate_judge_cost(config, judge_input_tokens, judge_output_tokens)

        total_cost_low = (response_cost + judge_cost) * 0.8  # 20% buffer
        total_cost_high = (response_cost + judge_cost) * 1.2

        # Time estimation
        avg_response_time_s = 3.0
        avg_judge_time_s = 1.5
        parallelism = config.max_concurrent_requests

        sequential_time = (
            total_response_calls * avg_response_time_s +
            total_judge_calls * avg_judge_time_s
        )
        parallel_time = sequential_time / parallelism

        return CostEstimate(
            total_prompts=num_prompts,
            model_pairs=num_model_pairs,
            total_comparisons=num_prompts * num_model_pairs,
            total_response_calls=total_response_calls,
            total_judge_calls=total_judge_calls,
            response_cost_estimate=response_cost,
            judge_cost_estimate=judge_cost,
            total_cost_low=total_cost_low,
            total_cost_high=total_cost_high,
            estimated_time_sequential_hours=sequential_time / 3600,
            estimated_time_parallel_hours=parallel_time / 3600
        )

    def format_estimate(self, estimate: CostEstimate) -> str:
        """Format estimate for display"""
        return f"""
╭─────────────────────────────────────────────────────────────╮
│                    EVAL RUN ESTIMATE                        │
├─────────────────────────────────────────────────────────────┤
│ Prompts:              {estimate.total_prompts:<10}                          │
│ Model pairs:          {estimate.model_pairs:<10}                          │
│ Total comparisons:    {estimate.total_comparisons:<10}                          │
│                                                             │
│ Response calls:       {estimate.total_response_calls:<10}                          │
│ Judge calls:          {estimate.total_judge_calls:<10}                          │
│                                                             │
│ ESTIMATED COST                                              │
│   Response generation:  ${estimate.response_cost_estimate:,.0f}                          │
│   Judging:              ${estimate.judge_cost_estimate:,.0f}                          │
│   Total:                ${estimate.total_cost_low:,.0f} - ${estimate.total_cost_high:,.0f}                  │
│                                                             │
│ ESTIMATED TIME                                              │
│   Sequential:           {estimate.estimated_time_sequential_hours:.1f} hours                        │
│   Parallelized:         {estimate.estimated_time_parallel_hours:.1f} hours                        │
╰─────────────────────────────────────────────────────────────╯
"""
```

---

## 9. Robustness and Resumability

### 9.1 Checkpoint Manager

```python
class CheckpointManager:
    """Manages checkpointing and resume functionality"""

    def __init__(self, run_dir: str, db_path: str):
        self.run_dir = Path(run_dir)
        self.db_path = db_path
        self.checkpoint_path = self.run_dir / "checkpoint.json"

    def save_checkpoint(self, state: EvalState) -> None:
        """Save current evaluation state to checkpoint file"""
        checkpoint = {
            "run_id": state.run_id,
            "timestamp": datetime.now().isoformat(),
            "phase": state.current_phase,
            "completed_prompts": list(state.completed_prompt_ids),
            "completed_pairs": [
                {"prompt_id": p[0], "model_pair": p[1]}
                for p in state.completed_pairs
            ],
            "current_prompt_index": state.current_prompt_index,
            "stats": {
                "total_prompts": state.total_prompts,
                "total_pairs_completed": len(state.completed_pairs),
                "elapsed_seconds": state.elapsed_seconds,
                "cost_so_far": state.cost_so_far
            }
        }

        # Write atomically
        temp_path = self.checkpoint_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        temp_path.rename(self.checkpoint_path)

    def load_checkpoint(self) -> Optional[EvalState]:
        """Load checkpoint if it exists"""
        if not self.checkpoint_path.exists():
            return None

        with open(self.checkpoint_path) as f:
            checkpoint = json.load(f)

        return EvalState(
            run_id=checkpoint["run_id"],
            current_phase=checkpoint["phase"],
            completed_prompt_ids=set(checkpoint["completed_prompts"]),
            completed_pairs={
                (p["prompt_id"], p["model_pair"])
                for p in checkpoint["completed_pairs"]
            },
            current_prompt_index=checkpoint["current_prompt_index"],
            total_prompts=checkpoint["stats"]["total_prompts"],
            elapsed_seconds=checkpoint["stats"]["elapsed_seconds"],
            cost_so_far=checkpoint["stats"]["cost_so_far"]
        )

    def is_completed(self, prompt_id: str, model_pair: str) -> bool:
        """Check if a specific comparison is already completed"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 1 FROM comparison_results
                WHERE prompt_id = ? AND gemini_model_id || '_vs_' || opponent_model_id = ?
            """, (prompt_id, model_pair))
            return await cursor.fetchone() is not None

    async def save_comparison(self, result: ComparisonResult) -> None:
        """Save a completed comparison result"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO comparison_results
                (comparison_id, pair_id, prompt_id, gemini_model_id, opponent_model_id,
                 final_verdict, gemini_verdict, judges_for_gemini, judges_for_opponent,
                 judges_tie, unanimous, gemini_auto_loss, opponent_auto_loss, auto_loss_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.comparison_id, result.pair_id, result.prompt_id,
                result.gemini_model_id, result.opponent_model_id,
                result.final_verdict.value,
                "WIN" if result.judges_for_gemini > result.judges_for_opponent else
                "LOSS" if result.judges_for_opponent > result.judges_for_gemini else "TIE",
                result.judges_for_gemini, result.judges_for_opponent,
                result.judges_tie, result.unanimous,
                result.gemini_auto_loss, result.opponent_auto_loss, result.auto_loss_reason
            ))
            await db.commit()

    async def log_failure(
        self,
        prompt_id: str,
        model_pair: str,
        error: Exception
    ) -> None:
        """Log a failure for later analysis"""
        failure_log = self.run_dir / "failures.log"
        with open(failure_log, 'a') as f:
            f.write(f"{datetime.now().isoformat()} | {prompt_id} | {model_pair} | {type(error).__name__}: {error}\n")
```

### 9.2 Retry Handler with Exponential Backoff

```python
class RetryHandler:
    """Handles retries with exponential backoff and jitter"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_ms: int = 1000,
        max_delay_ms: int = 60000,
        jitter_factor: float = 0.25
    ):
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.jitter_factor = jitter_factor

    async def execute_with_retry(
        self,
        func: Callable[[], Awaitable[T]],
        timeout_ms: int = 60000
    ) -> T:
        """Execute function with retry logic"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    func(),
                    timeout=timeout_ms / 1000
                )

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Request timed out after {timeout_ms}ms")
                logger.warning(f"Attempt {attempt + 1} timed out")

            except RateLimitError as e:
                last_error = e
                # Use retry-after header if available
                delay = e.retry_after_ms or self._calculate_delay(attempt)
                logger.warning(f"Rate limited, waiting {delay}ms")
                await asyncio.sleep(delay / 1000)
                continue

            except APIError as e:
                last_error = e
                if e.status_code in (500, 502, 503, 504):
                    # Retry on server errors
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Server error {e.status_code}, retrying in {delay}ms")
                    await asyncio.sleep(delay / 1000)
                    continue
                else:
                    # Don't retry client errors
                    raise

            except Exception as e:
                last_error = e
                delay = self._calculate_delay(attempt)
                logger.warning(f"Unexpected error: {e}, retrying in {delay}ms")
                await asyncio.sleep(delay / 1000)

        raise RetryExhaustedError(
            f"Failed after {self.max_retries + 1} attempts",
            last_error=last_error
        )

    def _calculate_delay(self, attempt: int) -> int:
        """Calculate delay with exponential backoff and jitter"""
        base = self.base_delay_ms * (2 ** attempt)
        capped = min(base, self.max_delay_ms)
        jitter = random.uniform(
            -capped * self.jitter_factor,
            capped * self.jitter_factor
        )
        return int(capped + jitter)
```

### 9.3 OpenRouter Client with Rate Limiting

```python
class OpenRouterClient:
    """Async client for OpenRouter API with rate limiting"""

    def __init__(
        self,
        api_key: str,
        max_concurrent: int = 10,
        requests_per_minute: int = 60
    ):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "gemini-writing-eval",
                "Content-Type": "application/json"
            }
        )

    async def complete(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
    ) -> CompletionResponse:
        """Send completion request with rate limiting"""

        async with self.semaphore:
            await self.rate_limiter.acquire()

            start_time = time.time()
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs
                }
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise RateLimitError(
                    "Rate limit exceeded",
                    retry_after_ms=int(retry_after) * 1000
                )

            if response.status_code != 200:
                raise APIError(
                    f"API error: {response.text}",
                    status_code=response.status_code
                )

            data = response.json()
            response_time = time.time() - start_time

            return CompletionResponse(
                content=data["choices"][0]["message"]["content"],
                usage=TokenUsage(
                    prompt_tokens=data["usage"]["prompt_tokens"],
                    completion_tokens=data["usage"]["completion_tokens"],
                    total_tokens=data["usage"]["total_tokens"]
                ),
                model=data["model"],
                response_time=response_time,
                raw=data
            )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.tokens = requests_per_minute
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token, waiting if necessary"""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(
                self.requests_per_minute,
                self.tokens + elapsed * (self.requests_per_minute / 60)
            )
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60 / self.requests_per_minute)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
```

---

## 10. Report Generation

### 10.1 PDF Report Generator

```python
class ReportGenerator:
    """Generates comprehensive PDF evaluation report"""

    def __init__(self, analysis: AnalysisResults, config: EvalConfig):
        self.analysis = analysis
        self.config = config

    async def generate(self, output_path: str) -> None:
        """Generate full PDF report"""

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72, leftMargin=72,
            topMargin=72, bottomMargin=72
        )

        elements = []

        # Title page
        elements.extend(self._make_title_page())

        # Executive summary
        elements.extend(self._make_executive_summary())

        # Methodology section
        elements.extend(self._make_methodology_section())

        # Overall results
        elements.extend(self._make_overall_results())

        # Breakdown by dimension
        elements.extend(self._make_dimension_breakdowns())

        # Weakness analysis
        elements.extend(self._make_weakness_analysis())

        # Statistical appendix
        elements.extend(self._make_statistical_appendix())

        # Build PDF
        doc.build(elements)

    def _make_executive_summary(self) -> list:
        """Generate executive summary section"""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['Heading1']))

        # Key findings
        elements.append(Paragraph("Key Findings", self.styles['Heading2']))

        for model_pair, result in self.analysis.win_rates.items():
            verdict = "outperforms" if result.win_rate > 0.5 else "underperforms" if result.win_rate < 0.5 else "ties with"
            elements.append(Paragraph(
                f"Gemini {verdict} {result.opponent_model}: "
                f"{result.win_rate:.1%} win rate (95% CI: {result.ci_low:.1%}-{result.ci_high:.1%})",
                self.styles['Normal']
            ))

        # Top weaknesses
        elements.append(Paragraph("Areas for Improvement", self.styles['Heading2']))

        for weakness in self.analysis.weaknesses[:5]:
            elements.append(Paragraph(
                f"- {weakness.dimension}: {weakness.value} "
                f"({weakness.win_rate:.1%} win rate, n={weakness.sample_size})",
                self.styles['Normal']
            ))

        return elements

    def _make_overall_results(self) -> list:
        """Generate overall results with charts"""
        elements = []

        elements.append(Paragraph("Overall Results", self.styles['Heading1']))

        # Win rate bar chart
        win_rate_chart = self._create_win_rate_chart()
        elements.append(Image(win_rate_chart, width=6*inch, height=4*inch))

        # Results table
        table_data = [["Model Pair", "Win Rate", "95% CI", "N"]]
        for pair, result in self.analysis.win_rates.items():
            table_data.append([
                pair.replace("_vs_", " vs "),
                f"{result.win_rate:.1%}",
                f"{result.ci_low:.1%} - {result.ci_high:.1%}",
                str(result.total_comparisons)
            ])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)

        return elements

    def _create_win_rate_chart(self) -> str:
        """Create win rate bar chart"""
        fig = go.Figure()

        pairs = list(self.analysis.win_rates.keys())
        win_rates = [r.win_rate for r in self.analysis.win_rates.values()]
        ci_lows = [r.ci_low for r in self.analysis.win_rates.values()]
        ci_highs = [r.ci_high for r in self.analysis.win_rates.values()]

        fig.add_trace(go.Bar(
            x=pairs,
            y=win_rates,
            error_y=dict(
                type='data',
                symmetric=False,
                array=[h - w for w, h in zip(win_rates, ci_highs)],
                arrayminus=[w - l for w, l in zip(win_rates, ci_lows)]
            ),
            marker_color=['green' if r > 0.5 else 'red' if r < 0.5 else 'gray'
                         for r in win_rates]
        ))

        fig.add_hline(y=0.5, line_dash="dash", line_color="black")

        fig.update_layout(
            title="Gemini Win Rates by Model Pair",
            xaxis_title="Model Pair",
            yaxis_title="Win Rate",
            yaxis=dict(range=[0, 1])
        )

        # Save to temp file
        temp_path = "/tmp/win_rate_chart.png"
        fig.write_image(temp_path, scale=2)
        return temp_path

    def _make_weakness_analysis(self) -> list:
        """Generate detailed weakness analysis"""
        elements = []

        elements.append(Paragraph("Weakness Analysis", self.styles['Heading1']))

        elements.append(Paragraph(
            "The following areas show statistically significant underperformance:",
            self.styles['Normal']
        ))

        # Group weaknesses by dimension
        by_dimension = defaultdict(list)
        for w in self.analysis.weaknesses:
            by_dimension[w.dimension].append(w)

        for dimension, weaknesses in by_dimension.items():
            elements.append(Paragraph(f"By {dimension.replace('_', ' ').title()}", self.styles['Heading2']))

            # Create heatmap for this dimension
            heatmap = self._create_weakness_heatmap(dimension, weaknesses)
            if heatmap:
                elements.append(Image(heatmap, width=6*inch, height=4*inch))

            # List specific weaknesses
            for w in weaknesses[:10]:
                elements.append(Paragraph(
                    f"- {w.value}: {w.win_rate:.1%} win rate "
                    f"(CI: {w.ci_low:.1%}-{w.ci_high:.1%}, n={w.sample_size})",
                    self.styles['Normal']
                ))

        return elements
```

---

## 11. CLI Interface

```python
import typer
from pathlib import Path

app = typer.Typer(name="gemini-eval", help="Gemini Writing Evaluation Framework")

@app.command()
def run(
    preset: int = typer.Option(None, "--preset", "-p", help="Preset level (1-10)"),
    prompts: int = typer.Option(None, "--prompts", "-n", help="Number of prompts"),
    models: str = typer.Option(None, "--models", help="Comma-separated model IDs"),
    judges: str = typer.Option(None, "--judges", help="Comma-separated judge model IDs"),
    votes: int = typer.Option(None, "--votes", help="Votes per judge"),
    seed: int = typer.Option(None, "--seed", help="Random seed"),
    output: str = typer.Option("results", "--output", "-o", help="Output directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate only"),
    resume: str = typer.Option(None, "--resume", help="Resume from checkpoint dir")
):
    """Run an evaluation"""

    # Build config
    if preset:
        config = EVAL_PRESETS[preset].copy()
    else:
        config = EvalConfig(sampling_config=SamplingConfig(num_prompts=prompts or 100))

    # Apply overrides
    if prompts:
        config.sampling_config.num_prompts = prompts
    if models:
        model_list = models.split(",")
        config.pro_tier_opponents = [m for m in model_list if "pro" in m.lower()]
        config.flash_tier_opponents = [m for m in model_list if "flash" in m.lower()]
    if judges:
        config.judge_config.judge_models = judges.split(",")
    if votes:
        config.judge_config.votes_per_judge = votes
    if seed:
        config.sampling_config.random_seed = seed

    # Show estimate
    estimator = CostEstimator()
    estimate = estimator.estimate(config)
    typer.echo(estimator.format_estimate(estimate))

    if dry_run:
        return

    # Confirm
    if not typer.confirm("Proceed?"):
        raise typer.Abort()

    # Run evaluation
    asyncio.run(_run_eval(config, output, resume))


@app.command()
def view(
    run_dir: str = typer.Argument(..., help="Path to evaluation run directory")
):
    """View evaluation results in interactive TUI"""
    db_path = Path(run_dir) / "results.db"
    if not db_path.exists():
        typer.echo(f"No results found at {db_path}", err=True)
        raise typer.Exit(1)

    browser = ResultsBrowserApp(str(db_path))
    browser.run()


@app.command()
def compare(
    run_dirs: list[str] = typer.Argument(..., help="Paths to evaluation run directories")
):
    """Compare results across multiple runs"""
    # Load results from each run
    results = []
    for run_dir in run_dirs:
        db_path = Path(run_dir) / "results.db"
        if db_path.exists():
            results.append(load_results(str(db_path)))

    # Generate comparison report
    comparison = generate_comparison(results)
    typer.echo(format_comparison(comparison))


@app.command()
def report(
    run_dir: str = typer.Argument(..., help="Path to evaluation run directory"),
    output: str = typer.Option(None, "--output", "-o", help="Output PDF path")
):
    """Generate PDF report for an evaluation run"""
    db_path = Path(run_dir) / "results.db"
    output_path = output or str(Path(run_dir) / "report.pdf")

    # Run analysis
    analysis = asyncio.run(AnalysisEngine(str(db_path)).run_full_analysis())

    # Load config
    config_path = Path(run_dir) / "config.json"
    with open(config_path) as f:
        config = EvalConfig.parse_obj(json.load(f))

    # Generate report
    generator = ReportGenerator(analysis, config)
    asyncio.run(generator.generate(output_path))

    typer.echo(f"Report generated: {output_path}")


if __name__ == "__main__":
    app()
```

---

## 12. Implementation Timeline

### Phase 1: Foundation (Week 1-2)
- Set up project structure and dependencies
- Implement core data models (Pydantic schemas)
- Build O*NET database extraction layer
- Create basic OpenRouter client with retry handling

### Phase 2: Prompt Pipeline (Week 2-3)
- Implement task extraction and filtering
- Build NAICS mapping and company sampler
- Create persona generation
- Implement prompt assembly

### Phase 3: Evaluation Core (Week 3-4)
- Build response collector
- Implement judging module
- Create vote aggregator
- Build checkpoint manager

### Phase 4: Analysis & Reporting (Week 4-5)
- Implement analysis engine
- Build statistical tests
- Create chart generation
- Build PDF report generator

### Phase 5: TUI & Polish (Week 5-6)
- Build progress dashboard
- Implement results browser
- Create CLI interface
- End-to-end testing

### Phase 6: Validation (Week 6)
- Run small-scale evaluations
- Validate statistical methods
- Tune cost estimates
- Documentation

---

## 13. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limits | Configurable rate limiting, exponential backoff |
| High costs | Real-time cost tracking, presets, dry-run mode |
| Model refusals | Auto-loss handling, refusal categorization |
| Position bias | Deterministic shuffling, bias detection |
| Judge disagreement | Majority-of-majorities, agreement metrics |
| Interrupted runs | Full checkpointing, graceful shutdown |
| Data loss | SQLite with atomic writes, JSON backups |

---

## 14. Success Criteria

1. **Reproducibility**: Given same seed and config, produces identical prompts
2. **Robustness**: Handles all API failure modes gracefully
3. **Statistical Validity**: All win rates include proper confidence intervals
4. **Usability**: Clear CLI, informative TUI, comprehensive reports
5. **Efficiency**: Parallelizes API calls within rate limits
6. **Transparency**: Full audit trail of all judgments and reasoning
