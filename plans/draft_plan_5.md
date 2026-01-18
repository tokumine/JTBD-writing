# Draft Plan 5: Gemini Writing Evaluation Framework

## Executive Summary

This implementation plan provides a comprehensive approach to building the Gemini Writing Evaluation Framework, a system designed to compare Gemini 3.0 Pro and Flash against competing frontier LLMs (GPT-5.2, Claude Opus 4.5, Grok-4.1, Kimi K2, GPT-4.1, Claude Sonnet) on realistic professional writing tasks derived from the O*NET 30.1 database.

The framework extracts writing-related tasks from 18,796 O*NET task statements, enriches them with realistic personas, companies, and contextual details, then evaluates model outputs using a robust ensemble judging methodology with majority-of-majorities voting.

---

## Part 1: System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GEMINI WRITING EVAL                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                │
│  │   CLI/TUI    │   │   Config     │   │   Presets    │                │
│  │   Interface  │   │   Manager    │   │   (1-10)     │                │
│  └──────────────┘   └──────────────┘   └──────────────┘                │
│          │                  │                  │                        │
│          ▼                  ▼                  ▼                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    ORCHESTRATION ENGINE                         │    │
│  │  - Cost/Time Estimation                                        │    │
│  │  - Checkpoint/Resume Management                                │    │
│  │  - Progress Coordination                                       │    │
│  └────────────────────────────────────────────────────────────────┘    │
│          │                                                             │
│          ▼                                                             │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    PROMPT GENERATION PIPELINE                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │  Phase 1:    │  │  Phase 2:    │  │  Phase 3:    │         │    │
│  │  │  O*NET       │─▶│  Algorithmic │─▶│  LLM         │         │    │
│  │  │  Extraction  │  │  Combination │  │  Enrichment  │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│          │                                                             │
│          ▼                                                             │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    EVALUATION ENGINE                            │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │  Response    │  │  Judgment    │  │  Result      │         │    │
│  │  │  Generation  │  │  Pipeline    │  │  Aggregation │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│          │                                                             │
│          ▼                                                             │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    ANALYSIS & REPORTING                         │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │  Statistical │  │  Bias        │  │  PDF Report  │         │    │
│  │  │  Analysis    │  │  Detection   │  │  Generator   │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│          │                                                             │
│          ▼                                                             │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    STORAGE LAYER                                │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │    │
│  │  │  SQLite      │  │  JSON        │  │  Checkpoint  │         │    │
│  │  │  Database    │  │  Files       │  │  System      │         │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Directory Structure

```
gemini-writing-eval/
├── pyproject.toml              # Project configuration (poetry/uv)
├── README.md                   # Project documentation
├── .env.example                # Environment variable template
├── config/
│   └── presets.yaml            # 10 preset configurations
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # Pydantic settings/configuration
│   │   ├── presets.py          # Preset configuration loader
│   │   └── cost_estimator.py   # Cost/time estimation logic
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py   # O*NET database interface
│   │   ├── naics_mapper.py     # NAICS industry mapping
│   │   ├── company_database.py # Real company data
│   │   └── name_generator.py   # Realistic name generation
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Three-phase generation pipeline
│   │   ├── phase1_extraction.py
│   │   ├── phase2_combination.py
│   │   ├── phase3_enrichment.py
│   │   ├── schemas.py          # Prompt data models
│   │   └── templates/
│   │       └── enrichment_prompts.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py # OpenRouter API wrapper
│   │   ├── rate_limiter.py      # Rate limiting logic
│   │   ├── retry_handler.py     # Exponential backoff retry
│   │   └── circuit_breaker.py   # Circuit breaker pattern
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py           # Main evaluation orchestrator
│   │   ├── response_generator.py
│   │   ├── judge.py            # Judgment logic
│   │   ├── judge_prompts.py    # Judge persona prompts
│   │   ├── vote_aggregator.py  # Majority-of-majorities
│   │   └── schemas.py          # Evaluation data models
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py       # Statistical analysis
│   │   ├── bias_detection.py   # Systematic bias detection
│   │   ├── weakness_finder.py  # Gemini weakness identification
│   │   └── visualizations.py   # Chart generation
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py    # PDF report creation
│   │   ├── templates/          # Report templates
│   │   └── charts/             # Chart generators
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite operations
│   │   ├── checkpoint.py       # Checkpoint/resume logic
│   │   └── exporter.py         # CSV/JSON exports
│   │
│   └── tui/
│       ├── __init__.py
│       ├── app.py              # Main TUI application
│       ├── progress_dashboard.py
│       ├── results_viewer.py
│       └── components/         # Reusable TUI components
│
├── db/
│   └── onet.db                 # O*NET 30.1 database
│
├── results/                    # Evaluation run outputs
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── fixtures/
```

### 1.3 Core Dependencies

```toml
[project]
dependencies = [
    # Core
    "python>=3.11",
    "pydantic>=2.5",
    "pydantic-settings>=2.1",

    # Async HTTP
    "httpx>=0.26",
    "anyio>=4.2",

    # Database
    "aiosqlite>=0.19",

    # TUI
    "textual>=0.47",
    "rich>=13.7",

    # Data Processing
    "pandas>=2.1",
    "numpy>=1.26",

    # Statistics
    "scipy>=1.12",
    "statsmodels>=0.14",

    # Visualization
    "plotly>=5.18",
    "kaleido>=0.2",  # For static image export

    # PDF Generation
    "weasyprint>=60",
    "jinja2>=3.1",

    # Utilities
    "python-dotenv>=1.0",
    "click>=8.1",
    "tenacity>=8.2",
    "structlog>=24.1",
]
```

---

## Part 2: Data Models and Schemas

### 2.1 Prompt Schema

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

class MessagePosition(str, Enum):
    INITIAL = "initial_outreach"
    REPLY = "reply_in_thread"
    FOLLOWUP = "follow_up"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict_resolution"
    BAD_NEWS = "bad_news_delivery"

class SensitiveTopic(str, Enum):
    HR_ISSUES = "hr_issues"
    LEGAL = "legal_matters"
    BAD_NEWS = "bad_news_delivery"
    CONFIDENTIAL = "confidential_information"
    CONFLICT = "conflict_situations"

class WriterPersona(BaseModel):
    """Detailed writer persona for prompt contextualization"""
    name: str
    email: Optional[str] = None
    age: int = Field(ge=18, le=80)
    generation: Literal["gen_z", "millennial", "gen_x", "boomer"]
    job_title: str
    skill_level: Literal["entry", "mid", "senior", "executive"]
    english_variant: EnglishVariant = EnglishVariant.US

class RecipientPersona(BaseModel):
    """Target recipient/audience details"""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship: Literal["new_contact", "acquaintance", "colleague", "manager", "direct_report", "client", "vendor"]
    english_variant: EnglishVariant = EnglishVariant.US
    is_technical: bool = False

class CompanyContext(BaseModel):
    """Company information for grounding"""
    name: str
    size: Literal["startup", "small", "mid_market", "enterprise", "fortune_500"]
    industry_naics: str
    industry_name: str
    is_public: bool = False
    hq_location: Optional[str] = None
    employee_count: Optional[int] = None

class Attachment(BaseModel):
    """Mock attachment or reference content"""
    type: Literal["report", "email", "meeting_notes", "resume", "document", "data"]
    description: str
    content: str  # Summary or key points

class ConstraintSpec(BaseModel):
    """Explicit instruction-following constraints"""
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    description: str
    specific_requirement: str

class WritingPrompt(BaseModel):
    """Complete writing prompt with all context"""
    # Identifiers
    prompt_id: str
    onet_task_id: str
    onet_task: str

    # Occupation context
    occupation_code: str
    occupation_title: str
    job_zone: int = Field(ge=1, le=5)
    soc_major_group: str

    # Industry context
    naics_code: str
    naics_sector: str
    company: CompanyContext

    # Personas
    writer: WriterPersona
    recipients: list[RecipientPersona]
    audience_size: Literal["one_on_one", "small_group", "department", "company_wide", "public"]

    # Communication context
    formality_level: int = Field(ge=1, le=5)  # 1=very casual, 5=very formal
    urgency_level: int = Field(ge=1, le=5)    # 1=routine, 5=critical
    message_position: MessagePosition
    emotional_context: EmotionalContext
    communication_channel: Optional[str] = None  # email, memo, report, etc.

    # Content context
    prior_context: Optional[str] = None  # Reply-to content
    attachments: list[Attachment] = []
    competing_objectives: Optional[str] = None
    tone_example: Optional[str] = None  # Example to match

    # Task type
    is_revision_task: bool = False
    original_draft: Optional[str] = None  # For revision tasks
    revision_instruction: Optional[str] = None

    # Constraints
    constraints: list[ConstraintSpec] = []
    is_ambiguous: bool = False  # Deliberately vague prompt

    # Metadata
    sensitive_topics: list[SensitiveTopic] = []
    writing_category: str  # From O*NET inferred categories

    # Language
    language: str = "en"
    language_variant: str = "en-US"

    # Temporal
    temporal_context: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # The actual prompt text
    full_prompt: str  # Generated prompt text to send to models
```

### 2.2 Response Schema

```python
class ModelResponse(BaseModel):
    """Single model response to a prompt"""
    response_id: str
    prompt_id: str
    model_id: str
    model_name: str

    # Response content
    response_text: str

    # Metadata
    response_time_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int

    # Status
    status: Literal["success", "refused", "error", "timeout", "incomplete", "off_topic"]
    refusal_category: Optional[Literal[
        "safety_refusal",
        "capability_limitation",
        "misunderstanding",
        "incomplete_response",
        "off_topic"
    ]] = None
    error_message: Optional[str] = None

    # Format detection
    used_bullet_points: bool = False
    used_headers: bool = False
    has_greeting: bool = False
    has_signoff: bool = False
    word_count: int = 0
    character_count: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2.3 Judgment Schema

```python
class JudgePersona(str, Enum):
    WRITING_EXPERT = "writing_expert"
    TARGET_RECIPIENT = "target_recipient"

class SingleVote(BaseModel):
    """Single vote from a judge"""
    vote_id: str
    judge_model: str
    judge_persona: JudgePersona
    prompt_id: str
    response_a_id: str  # Model response ID
    response_b_id: str  # Model response ID

    # Position info (for bias detection)
    gemini_position: Literal["A", "B"]

    # Vote result
    winner: Literal["A", "B", "tie"]
    confidence: float = Field(ge=0, le=1)

    # Rubric scores (1-5 scale)
    scores_a: dict[str, float]  # {criterion: score}
    scores_b: dict[str, float]

    # Reasoning
    reasoning: str

    # Metadata
    response_time_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class JudgeAggregation(BaseModel):
    """Aggregated votes from one judge model (best-of-5)"""
    judge_model: str
    judge_persona: JudgePersona
    prompt_id: str

    votes: list[SingleVote]
    majority_winner: Literal["A", "B", "tie"]
    vote_count_a: int
    vote_count_b: int
    vote_count_tie: int

    # Gemini-relative result
    gemini_win: bool
    gemini_loss: bool
    is_tie: bool

class ComparisonResult(BaseModel):
    """Full comparison result for one prompt between two models"""
    comparison_id: str
    prompt_id: str

    # Models
    gemini_model: str
    competitor_model: str
    gemini_response_id: str
    competitor_response_id: str

    # Judge results (per judge model, per persona)
    judge_results: list[JudgeAggregation]

    # Final aggregation (majority of majorities)
    final_winner: Literal["gemini", "competitor", "tie"]
    judges_for_gemini: int
    judges_for_competitor: int
    judges_tie: int

    # Auto-loss tracking
    gemini_auto_loss: bool = False
    competitor_auto_loss: bool = False
    auto_loss_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2.4 Configuration Schema

```python
class ModelConfig(BaseModel):
    """Model configuration"""
    model_id: str
    model_name: str
    tier: Literal["pro", "flash"]
    openrouter_id: str
    max_tokens: int = 4096
    temperature: float = 0.7

class JudgeConfig(BaseModel):
    """Judge configuration"""
    models: list[str]  # Model IDs to use as judges
    votes_per_judge: int = Field(default=5, ge=1, le=10)
    use_both_personas: bool = True

class SamplingConfig(BaseModel):
    """Sampling configuration"""
    random_seed: int
    total_prompts: int
    stratify_by_job_zone: bool = True
    stratify_by_soc_group: bool = True
    stratify_by_naics: bool = True
    max_per_occupation: Optional[int] = None
    max_per_industry: Optional[int] = None

    # Filters
    occupation_codes: Optional[list[str]] = None
    naics_codes: Optional[list[str]] = None
    job_zones: Optional[list[int]] = None
    formality_range: Optional[tuple[int, int]] = None
    age_range: Optional[tuple[int, int]] = None

class EvalConfig(BaseModel):
    """Complete evaluation configuration"""
    # Run identification
    run_id: str
    run_name: str
    preset_level: Optional[int] = None

    # Models
    gemini_models: list[ModelConfig]
    competitor_models: list[ModelConfig]
    model_pairs: list[tuple[str, str]]  # (gemini_id, competitor_id)

    # Judges
    judge_config: JudgeConfig

    # Sampling
    sampling: SamplingConfig

    # API
    openrouter_api_key: str
    max_concurrent_requests: int = 10
    request_timeout_seconds: int = 120
    max_retries: int = 3

    # Output
    output_dir: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Part 3: O*NET Data Extraction and Processing

### 3.1 Database Interface

```python
# src/data/onet_extractor.py

import aiosqlite
from pathlib import Path
from typing import AsyncGenerator
from dataclasses import dataclass

@dataclass
class ONetTask:
    """Raw O*NET task data"""
    task_id: str
    onetsoc_code: str
    task: str
    task_type: str  # Core, Supplemental, or NULL
    occupation_title: str
    occupation_description: str
    job_zone: int
    soc_major_group: str
    writing_category: str  # Inferred category

class ONetExtractor:
    """Interface to O*NET 30.1 SQLite database"""

    WRITING_CATEGORIES = {
        "explicit_writing": [
            "%write%", "%draft%", "%document%", "%compose%", "%author%"
        ],
        "correspondence": [
            "%correspond%", "%email%", "%letter%", "%memo%"
        ],
        "reports_presentations": [
            "%report%", "%present%finding%", "%present%result%", "%summarize%"
        ],
        "proposals_negotiation": [
            "%propos%", "%negotiat%", "%persuad%", "%pitch%"
        ],
        "policy_procedure": [
            "%polic%", "%procedure%", "%guideline%", "%protocol%"
        ],
        "customer_communication": [
            "%customer%question%", "%client%question%", "%resolve%complaint%"
        ],
        "training_instruction": [
            "%train%staff%", "%train%employee%", "%instruct%", "%curriculum%"
        ],
        "internal_coordination": [
            "%confer with%", "%coordinate with%", "%collaborate with%"
        ],
        "contracts_legal": [
            "%contract%", "%agreement%", "%compliance%", "%permit%"
        ],
        "feedback_evaluation": [
            "%evaluat%performance%", "%provide%feedback%", "%assess%report%"
        ]
    }

    SOC_MAJOR_GROUPS = {
        "11": "Management",
        "13": "Business and Financial Operations",
        "15": "Computer and Mathematical",
        "17": "Architecture and Engineering",
        "19": "Life, Physical, and Social Science",
        "21": "Community and Social Service",
        "23": "Legal",
        "25": "Educational Instruction and Library",
        "27": "Arts, Design, Entertainment, Sports, Media",
        "29": "Healthcare Practitioners and Technical",
        "31": "Healthcare Support",
        "33": "Protective Service",
        "35": "Food Preparation and Serving",
        "37": "Building and Grounds Cleaning",
        "39": "Personal Care and Service",
        "41": "Sales and Related",
        "43": "Office and Administrative Support",
        "45": "Farming, Fishing, and Forestry",
        "47": "Construction and Extraction",
        "49": "Installation, Maintenance, Repair",
        "51": "Production",
        "53": "Transportation and Material Moving",
        "55": "Military Specific"
    }

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def extract_writing_tasks(
        self,
        job_zones: list[int] | None = None,
        occupation_codes: list[str] | None = None,
        categories: list[str] | None = None
    ) -> AsyncGenerator[ONetTask, None]:
        """Extract writing-relevant tasks with filtering"""

        async with aiosqlite.connect(self.db_path) as db:
            # Build dynamic query
            query = """
                SELECT
                    t.task_id,
                    t.onetsoc_code,
                    t.task,
                    t.task_type,
                    o.title as occupation_title,
                    o.description as occupation_description,
                    jz.job_zone
                FROM task_statements t
                JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
                JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
                WHERE 1=1
            """
            params = []

            # Add job zone filter
            if job_zones:
                placeholders = ",".join("?" * len(job_zones))
                query += f" AND jz.job_zone IN ({placeholders})"
                params.extend(job_zones)

            # Add occupation filter
            if occupation_codes:
                placeholders = ",".join("?" * len(occupation_codes))
                query += f" AND t.onetsoc_code IN ({placeholders})"
                params.extend(occupation_codes)

            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    task_text = row[2]

                    # Determine writing category
                    writing_category = self._classify_task(task_text)

                    if writing_category is None:
                        continue

                    if categories and writing_category not in categories:
                        continue

                    soc_major = row[1][:2]

                    yield ONetTask(
                        task_id=row[0],
                        onetsoc_code=row[1],
                        task=task_text,
                        task_type=row[3] or "Unknown",
                        occupation_title=row[4],
                        occupation_description=row[5],
                        job_zone=row[6],
                        soc_major_group=self.SOC_MAJOR_GROUPS.get(soc_major, "Unknown"),
                        writing_category=writing_category
                    )

    def _classify_task(self, task_text: str) -> str | None:
        """Classify task into writing category"""
        task_lower = task_text.lower()

        for category, patterns in self.WRITING_CATEGORIES.items():
            for pattern in patterns:
                # Convert SQL LIKE pattern to simple substring check
                search_term = pattern.replace("%", "")
                if search_term in task_lower:
                    return category

        return None

    async def get_occupation_context(
        self,
        occupation_code: str
    ) -> dict:
        """Get additional context for an occupation"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get work context scores
            work_context = {}
            query = """
                SELECT cm.element_name, wc.data_value
                FROM work_context wc
                JOIN content_model_reference cm ON wc.element_id = cm.element_id
                WHERE wc.onetsoc_code = ? AND wc.scale_id = 'CX'
            """
            async with db.execute(query, [occupation_code]) as cursor:
                async for row in cursor:
                    work_context[row[0]] = row[1]

            # Get skills
            skills = {}
            query = """
                SELECT cm.element_name, sk.data_value
                FROM skills sk
                JOIN content_model_reference cm ON sk.element_id = cm.element_id
                WHERE sk.onetsoc_code = ? AND sk.scale_id = 'IM'
            """
            async with db.execute(query, [occupation_code]) as cursor:
                async for row in cursor:
                    skills[row[0]] = row[1]

            return {
                "work_context": work_context,
                "skills": skills
            }

    async def get_task_counts_by_category(self) -> dict[str, int]:
        """Get count of tasks per writing category"""
        counts = {}
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT task FROM task_statements"
            async with db.execute(query) as cursor:
                async for row in cursor:
                    category = self._classify_task(row[0])
                    if category:
                        counts[category] = counts.get(category, 0) + 1
        return counts
```

### 3.2 NAICS Industry Mapping

```python
# src/data/naics_mapper.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class NAICSIndustry:
    """NAICS industry information"""
    code: str
    sector_code: str  # 2-digit
    sector_name: str
    subsector_name: str
    industry_group: Optional[str] = None

class NAICSMapper:
    """Maps occupations to NAICS industries for diversity"""

    # Major NAICS sectors (2-digit codes)
    SECTORS = {
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
        "81": "Other Services (except Public Administration)",
        "92": "Public Administration"
    }

    # Mapping from SOC major groups to likely NAICS sectors
    # This is a simplified heuristic - real implementation would use BLS crosswalk
    SOC_TO_NAICS_LIKELY = {
        "11": ["54", "52", "55", "31-33", "62"],  # Management
        "13": ["54", "52", "55", "56"],           # Business/Financial
        "15": ["54", "51", "52"],                 # Computer/Math
        "17": ["54", "23", "31-33"],              # Architecture/Engineering
        "19": ["54", "61", "62"],                 # Life/Physical Science
        "21": ["62", "92"],                       # Community/Social Service
        "23": ["54", "92"],                       # Legal
        "25": ["61"],                             # Education
        "27": ["51", "71"],                       # Arts/Media
        "29": ["62"],                             # Healthcare Practitioners
        "31": ["62"],                             # Healthcare Support
        "33": ["92"],                             # Protective Service
        "35": ["72"],                             # Food Service
        "37": ["56", "72"],                       # Building/Grounds
        "39": ["72", "81"],                       # Personal Care
        "41": ["44-45", "42"],                    # Sales
        "43": ["54", "52", "56"],                 # Office/Admin
        "45": ["11"],                             # Farming/Fishing
        "47": ["23", "21"],                       # Construction
        "49": ["81", "31-33"],                    # Maintenance/Repair
        "51": ["31-33"],                          # Production
        "53": ["48-49"],                          # Transportation
    }

    def get_industries_for_occupation(
        self,
        soc_major: str,
        count: int = 5
    ) -> list[NAICSIndustry]:
        """Get likely NAICS industries for a SOC major group"""
        likely_codes = self.SOC_TO_NAICS_LIKELY.get(soc_major, ["54"])

        industries = []
        for code in likely_codes[:count]:
            sector_name = self.SECTORS.get(code, "Other")
            industries.append(NAICSIndustry(
                code=code,
                sector_code=code[:2] if "-" not in code else code.split("-")[0],
                sector_name=sector_name,
                subsector_name=sector_name  # Simplified
            ))

        return industries

    def sample_diverse_industries(
        self,
        count: int,
        exclude_sectors: list[str] | None = None
    ) -> list[NAICSIndustry]:
        """Sample diverse industries across sectors"""
        import random

        available_sectors = list(self.SECTORS.keys())
        if exclude_sectors:
            available_sectors = [s for s in available_sectors if s not in exclude_sectors]

        sampled = random.sample(available_sectors, min(count, len(available_sectors)))

        return [
            NAICSIndustry(
                code=code,
                sector_code=code[:2] if "-" not in code else code.split("-")[0],
                sector_name=self.SECTORS[code],
                subsector_name=self.SECTORS[code]
            )
            for code in sampled
        ]
```

### 3.3 Real Company Database

```python
# src/data/company_database.py

from dataclasses import dataclass
from typing import Literal
import random

@dataclass
class Company:
    """Real company information"""
    name: str
    size: Literal["startup", "small", "mid_market", "enterprise", "fortune_500"]
    industry_naics: str
    sector_name: str
    is_public: bool
    hq_location: str
    employee_count_approx: int
    founded_year: int | None = None

class CompanyDatabase:
    """Database of real companies for prompt grounding"""

    # Sample companies by NAICS sector and size
    # This would be expanded significantly in production
    COMPANIES = {
        "52": {  # Finance and Insurance
            "fortune_500": [
                Company("JPMorgan Chase", "fortune_500", "52", "Finance", True, "New York, NY", 270000, 1799),
                Company("Bank of America", "fortune_500", "52", "Finance", True, "Charlotte, NC", 213000, 1904),
                Company("Goldman Sachs", "fortune_500", "52", "Finance", True, "New York, NY", 45000, 1869),
                Company("Morgan Stanley", "fortune_500", "52", "Finance", True, "New York, NY", 82000, 1935),
                Company("Citigroup", "fortune_500", "52", "Finance", True, "New York, NY", 240000, 1812),
            ],
            "enterprise": [
                Company("Capital One", "enterprise", "52", "Finance", True, "McLean, VA", 52000, 1994),
                Company("Charles Schwab", "enterprise", "52", "Finance", True, "San Francisco, CA", 33000, 1971),
                Company("Northern Trust", "enterprise", "52", "Finance", True, "Chicago, IL", 22000, 1889),
            ],
            "mid_market": [
                Company("Wintrust Financial", "mid_market", "52", "Finance", True, "Rosemont, IL", 5500, 1991),
                Company("Valley National Bank", "mid_market", "52", "Finance", True, "Wayne, NJ", 3000, 1927),
            ],
            "small": [
                Company("Harbor Capital Advisors", "small", "52", "Finance", False, "Chicago, IL", 200, 1983),
                Company("Midwest Community Bank", "small", "52", "Finance", False, "Milwaukee, WI", 75, 1995),
            ],
            "startup": [
                Company("FinTech Solutions", "startup", "52", "Finance", False, "Austin, TX", 25, 2021),
                Company("Robo-Advisor Inc", "startup", "52", "Finance", False, "San Francisco, CA", 15, 2022),
            ]
        },
        "54": {  # Professional Services
            "fortune_500": [
                Company("Accenture", "fortune_500", "54", "Professional Services", True, "Dublin, Ireland", 738000, 1989),
                Company("Deloitte", "fortune_500", "54", "Professional Services", False, "London, UK", 415000, 1845),
                Company("McKinsey & Company", "fortune_500", "54", "Professional Services", False, "New York, NY", 45000, 1926),
            ],
            "enterprise": [
                Company("Booz Allen Hamilton", "enterprise", "54", "Professional Services", True, "McLean, VA", 30000, 1914),
                Company("CBRE Group", "enterprise", "54", "Professional Services", True, "Dallas, TX", 115000, 1906),
            ],
            "mid_market": [
                Company("West Monroe Partners", "mid_market", "54", "Professional Services", False, "Chicago, IL", 2000, 2002),
                Company("Slalom Consulting", "mid_market", "54", "Professional Services", False, "Seattle, WA", 13000, 2001),
            ],
            "small": [
                Company("Apex Strategy Group", "small", "54", "Professional Services", False, "Boston, MA", 50, 2015),
                Company("DataDriven Consulting", "small", "54", "Professional Services", False, "Denver, CO", 30, 2018),
            ],
            "startup": [
                Company("AI Advisory Co", "startup", "54", "Professional Services", False, "Palo Alto, CA", 8, 2023),
                Company("GreenTech Consultants", "startup", "54", "Professional Services", False, "Portland, OR", 12, 2022),
            ]
        },
        "62": {  # Healthcare
            "fortune_500": [
                Company("UnitedHealth Group", "fortune_500", "62", "Healthcare", True, "Minnetonka, MN", 400000, 1977),
                Company("CVS Health", "fortune_500", "62", "Healthcare", True, "Woonsocket, RI", 300000, 1963),
                Company("Kaiser Permanente", "fortune_500", "62", "Healthcare", False, "Oakland, CA", 300000, 1945),
            ],
            "enterprise": [
                Company("HCA Healthcare", "enterprise", "62", "Healthcare", True, "Nashville, TN", 283000, 1968),
                Company("Mayo Clinic", "enterprise", "62", "Healthcare", False, "Rochester, MN", 76000, 1889),
            ],
            "mid_market": [
                Company("Mercy Health System", "mid_market", "62", "Healthcare", False, "St. Louis, MO", 40000, 1986),
                Company("Northwell Health", "mid_market", "62", "Healthcare", False, "New Hyde Park, NY", 80000, 1997),
            ],
            "small": [
                Company("Coastal Family Medicine", "small", "62", "Healthcare", False, "San Diego, CA", 45, 2005),
                Company("Mountain View Clinic", "small", "62", "Healthcare", False, "Denver, CO", 25, 2010),
            ],
            "startup": [
                Company("TeleHealth Plus", "startup", "62", "Healthcare", False, "Austin, TX", 18, 2021),
                Company("MindWell Therapy", "startup", "62", "Healthcare", False, "Los Angeles, CA", 10, 2023),
            ]
        },
        "51": {  # Information/Tech
            "fortune_500": [
                Company("Apple", "fortune_500", "51", "Technology", True, "Cupertino, CA", 164000, 1976),
                Company("Microsoft", "fortune_500", "51", "Technology", True, "Redmond, WA", 221000, 1975),
                Company("Alphabet (Google)", "fortune_500", "51", "Technology", True, "Mountain View, CA", 190000, 1998),
                Company("Meta", "fortune_500", "51", "Technology", True, "Menlo Park, CA", 67000, 2004),
                Company("Amazon", "fortune_500", "51", "Technology", True, "Seattle, WA", 1540000, 1994),
            ],
            "enterprise": [
                Company("Salesforce", "enterprise", "51", "Technology", True, "San Francisco, CA", 79000, 1999),
                Company("Adobe", "enterprise", "51", "Technology", True, "San Jose, CA", 29000, 1982),
                Company("ServiceNow", "enterprise", "51", "Technology", True, "Santa Clara, CA", 22000, 2004),
            ],
            "mid_market": [
                Company("Datadog", "mid_market", "51", "Technology", True, "New York, NY", 5500, 2010),
                Company("Twilio", "mid_market", "51", "Technology", True, "San Francisco, CA", 8000, 2008),
            ],
            "small": [
                Company("CloudOps Solutions", "small", "51", "Technology", False, "Austin, TX", 85, 2017),
                Company("DevSecure Inc", "small", "51", "Technology", False, "Seattle, WA", 45, 2019),
            ],
            "startup": [
                Company("AI Vision Labs", "startup", "51", "Technology", False, "San Francisco, CA", 22, 2023),
                Company("Quantum Computing Co", "startup", "51", "Technology", False, "Boston, MA", 15, 2022),
            ]
        },
        "31-33": {  # Manufacturing
            "fortune_500": [
                Company("General Motors", "fortune_500", "31-33", "Manufacturing", True, "Detroit, MI", 167000, 1908),
                Company("Ford Motor Company", "fortune_500", "31-33", "Manufacturing", True, "Dearborn, MI", 173000, 1903),
                Company("Boeing", "fortune_500", "31-33", "Manufacturing", True, "Arlington, VA", 172000, 1916),
                Company("3M", "fortune_500", "31-33", "Manufacturing", True, "Saint Paul, MN", 92000, 1902),
            ],
            "enterprise": [
                Company("Parker Hannifin", "enterprise", "31-33", "Manufacturing", True, "Cleveland, OH", 58000, 1917),
                Company("Illinois Tool Works", "enterprise", "31-33", "Manufacturing", True, "Glenview, IL", 46000, 1912),
            ],
            "mid_market": [
                Company("Graco Inc", "mid_market", "31-33", "Manufacturing", True, "Minneapolis, MN", 3500, 1926),
                Company("Lincoln Electric", "mid_market", "31-33", "Manufacturing", True, "Cleveland, OH", 12000, 1895),
            ],
            "small": [
                Company("Precision Machining LLC", "small", "31-33", "Manufacturing", False, "Grand Rapids, MI", 75, 1998),
                Company("Advanced Composites Inc", "small", "31-33", "Manufacturing", False, "Phoenix, AZ", 120, 2005),
            ],
            "startup": [
                Company("3D Print Innovations", "startup", "31-33", "Manufacturing", False, "Austin, TX", 18, 2022),
                Company("Sustainable Packaging Co", "startup", "31-33", "Manufacturing", False, "Portland, OR", 25, 2021),
            ]
        },
    }

    def get_company(
        self,
        naics_sector: str,
        size: str | None = None,
        exclude_names: list[str] | None = None
    ) -> Company | None:
        """Get a company from the database"""
        sector_companies = self.COMPANIES.get(naics_sector, {})

        if not sector_companies:
            # Fall back to any sector
            all_companies = []
            for s in self.COMPANIES.values():
                for size_group in s.values():
                    all_companies.extend(size_group)
            if all_companies:
                return random.choice(all_companies)
            return None

        if size:
            companies = sector_companies.get(size, [])
        else:
            companies = []
            for size_group in sector_companies.values():
                companies.extend(size_group)

        if exclude_names:
            companies = [c for c in companies if c.name not in exclude_names]

        return random.choice(companies) if companies else None

    def sample_companies_diverse(
        self,
        count: int,
        naics_sector: str | None = None
    ) -> list[Company]:
        """Sample diverse companies across sizes"""
        sizes = ["fortune_500", "enterprise", "mid_market", "small", "startup"]
        companies = []

        for i in range(count):
            size = sizes[i % len(sizes)]
            if naics_sector:
                company = self.get_company(naics_sector, size)
            else:
                # Random sector
                sector = random.choice(list(self.COMPANIES.keys()))
                company = self.get_company(sector, size)

            if company:
                companies.append(company)

        return companies
```

### 3.4 Realistic Name Generator

```python
# src/data/name_generator.py

import random
from dataclasses import dataclass
from typing import Literal

@dataclass
class GeneratedPerson:
    """Generated person with demographic info"""
    first_name: str
    last_name: str
    full_name: str
    email: str
    age: int
    generation: Literal["gen_z", "millennial", "gen_x", "boomer"]
    formality: Literal["casual", "standard", "formal"]

class NameGenerator:
    """Generate realistic, diverse names"""

    # First names by approximate demographic distribution
    FIRST_NAMES = {
        "male": [
            # Common across demographics
            "James", "Michael", "David", "John", "Robert", "William", "Richard",
            "Joseph", "Thomas", "Christopher", "Daniel", "Matthew", "Anthony",
            # More diverse
            "Carlos", "Miguel", "Juan", "Jose", "Luis", "Marco", "Diego",
            "Wei", "Chen", "Ming", "Hiroshi", "Kenji", "Raj", "Anil", "Vikram",
            "Mohammed", "Ahmed", "Omar", "Jamal", "DeShawn", "Terrell", "Marcus",
            "Andrei", "Pavel", "Dmitri", "Patrick", "Sean", "Liam", "Ethan",
            "Noah", "Oliver", "Aiden", "Lucas", "Mason", "Elijah", "Alexander",
        ],
        "female": [
            # Common across demographics
            "Jennifer", "Lisa", "Michelle", "Jessica", "Amanda", "Sarah", "Emily",
            "Elizabeth", "Maria", "Patricia", "Susan", "Margaret", "Dorothy",
            # More diverse
            "Sofia", "Isabella", "Camila", "Valentina", "Lucia", "Carmen", "Ana",
            "Wei", "Mei", "Yuki", "Akiko", "Priya", "Ananya", "Deepa",
            "Fatima", "Aisha", "Zahra", "Imani", "Keisha", "Aaliyah", "Jasmine",
            "Olga", "Natasha", "Svetlana", "Siobhan", "Fiona", "Emma", "Olivia",
            "Ava", "Charlotte", "Sophia", "Amelia", "Harper", "Evelyn", "Abigail",
        ]
    }

    LAST_NAMES = [
        # Common American
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        # East Asian
        "Chen", "Wang", "Li", "Zhang", "Liu", "Yang", "Huang", "Wu", "Kim",
        "Park", "Lee", "Choi", "Jung", "Yamamoto", "Tanaka", "Suzuki",
        # South Asian
        "Patel", "Singh", "Kumar", "Shah", "Sharma", "Gupta", "Reddy", "Rao",
        # Middle Eastern
        "Ahmed", "Ali", "Khan", "Hassan", "Hussein", "Mohammad", "Ibrahim",
        # European
        "Mueller", "Schmidt", "Fischer", "Weber", "Russo", "Romano", "Rossi",
        "Kowalski", "Novak", "Petrov", "O'Brien", "Murphy", "Kelly", "Sullivan",
        # African American
        "Washington", "Jefferson", "Freeman", "Carter", "Robinson", "Harris",
    ]

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def generate_person(
        self,
        age: int | None = None,
        gender: Literal["male", "female"] | None = None,
        company_domain: str | None = None
    ) -> GeneratedPerson:
        """Generate a realistic person"""

        # Determine age
        if age is None:
            age = self.rng.randint(22, 68)

        # Determine generation based on age (as of 2026)
        if age <= 28:
            generation = "gen_z"
        elif age <= 44:
            generation = "millennial"
        elif age <= 60:
            generation = "gen_x"
        else:
            generation = "boomer"

        # Determine gender if not specified
        if gender is None:
            gender = self.rng.choice(["male", "female"])

        # Select names
        first_name = self.rng.choice(self.FIRST_NAMES[gender])
        last_name = self.rng.choice(self.LAST_NAMES)

        # Determine formality based on generation (tendency)
        if generation in ["gen_z", "millennial"]:
            formality_weights = [0.4, 0.5, 0.1]  # More casual
        elif generation == "gen_x":
            formality_weights = [0.2, 0.6, 0.2]  # Balanced
        else:
            formality_weights = [0.1, 0.4, 0.5]  # More formal

        formality = self.rng.choices(
            ["casual", "standard", "formal"],
            weights=formality_weights
        )[0]

        # Generate full name based on formality
        if formality == "casual":
            full_name = first_name
        elif formality == "formal":
            full_name = f"{first_name[0]}. {last_name}"
        else:
            full_name = f"{first_name} {last_name}"

        # Generate email
        domain = company_domain or "company.com"
        email_formats = [
            f"{first_name.lower()}.{last_name.lower()}@{domain}",
            f"{first_name[0].lower()}{last_name.lower()}@{domain}",
            f"{first_name.lower()}{last_name[0].lower()}@{domain}",
        ]
        email = self.rng.choice(email_formats)

        return GeneratedPerson(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=email,
            age=age,
            generation=generation,
            formality=formality
        )

    def generate_batch(
        self,
        count: int,
        ensure_diversity: bool = True
    ) -> list[GeneratedPerson]:
        """Generate multiple diverse people"""
        people = []

        if ensure_diversity:
            # Ensure age/generation diversity
            age_ranges = [
                (22, 28),   # Gen Z
                (29, 44),   # Millennial
                (45, 60),   # Gen X
                (61, 70),   # Boomer
            ]
            genders = ["male", "female"]

            for i in range(count):
                age_range = age_ranges[i % len(age_ranges)]
                gender = genders[i % len(genders)]
                age = self.rng.randint(*age_range)
                people.append(self.generate_person(age=age, gender=gender))
        else:
            for _ in range(count):
                people.append(self.generate_person())

        return people
```

---

## Part 4: Prompt Generation Pipeline

### 4.1 Three-Phase Pipeline Overview

```python
# src/prompts/pipeline.py

from dataclasses import dataclass
from typing import AsyncGenerator
import asyncio

from src.data.onet_extractor import ONetExtractor, ONetTask
from src.data.naics_mapper import NAICSMapper
from src.data.company_database import CompanyDatabase
from src.data.name_generator import NameGenerator
from src.prompts.schemas import WritingPrompt
from src.api.openrouter_client import OpenRouterClient

@dataclass
class PipelineConfig:
    """Configuration for prompt generation pipeline"""
    random_seed: int
    total_prompts: int
    db_path: str
    api_client: OpenRouterClient

    # Sampling parameters
    stratify_by_job_zone: bool = True
    stratify_by_soc_group: bool = True
    max_per_occupation: int | None = None

    # Enrichment parameters
    enrichment_model: str = "anthropic/claude-3-5-sonnet-20241022"
    context_rich_ratio: float = 0.4  # 40% get LLM enrichment

class PromptGenerationPipeline:
    """Three-phase prompt generation pipeline"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.onet = ONetExtractor(config.db_path)
        self.naics = NAICSMapper()
        self.companies = CompanyDatabase()
        self.names = NameGenerator(seed=config.random_seed)
        self.rng = __import__("random").Random(config.random_seed)

    async def generate_prompts(self) -> AsyncGenerator[WritingPrompt, None]:
        """Execute the full pipeline"""

        # Phase 1: Extract O*NET tasks
        tasks = await self._phase1_extract_tasks()

        # Phase 2: Algorithmic combination
        combined_prompts = await self._phase2_combine(tasks)

        # Phase 3: LLM enrichment for subset
        async for prompt in self._phase3_enrich(combined_prompts):
            yield prompt

    async def _phase1_extract_tasks(self) -> list[ONetTask]:
        """Phase 1: Extract writing-relevant tasks from O*NET"""
        tasks = []

        async for task in self.onet.extract_writing_tasks():
            tasks.append(task)

        # Stratified sampling
        if self.config.stratify_by_job_zone:
            tasks = self._stratify_by_field(tasks, "job_zone", 5)

        if self.config.stratify_by_soc_group:
            tasks = self._stratify_by_field(tasks, "soc_major_group", 22)

        # Limit to requested count
        if len(tasks) > self.config.total_prompts:
            tasks = self.rng.sample(tasks, self.config.total_prompts)

        return tasks

    def _stratify_by_field(
        self,
        tasks: list[ONetTask],
        field: str,
        num_groups: int
    ) -> list[ONetTask]:
        """Stratify tasks by a field for even distribution"""
        from collections import defaultdict

        # Group tasks
        groups = defaultdict(list)
        for task in tasks:
            key = getattr(task, field)
            groups[key].append(task)

        # Sample evenly
        per_group = self.config.total_prompts // num_groups
        stratified = []

        for group_tasks in groups.values():
            sample_size = min(per_group, len(group_tasks))
            stratified.extend(self.rng.sample(group_tasks, sample_size))

        return stratified

    async def _phase2_combine(
        self,
        tasks: list[ONetTask]
    ) -> list[WritingPrompt]:
        """Phase 2: Algorithmic combination of tasks with context"""
        prompts = []

        for i, task in enumerate(tasks):
            prompt_id = f"prompt_{i:05d}"

            # Get industry for this occupation
            soc_major = task.onetsoc_code[:2]
            industries = self.naics.get_industries_for_occupation(soc_major)
            industry = self.rng.choice(industries) if industries else None

            # Get company
            company = None
            if industry:
                company = self.companies.get_company(industry.sector_code)

            # Generate writer persona
            writer_person = self.names.generate_person()
            skill_level = self._job_zone_to_skill(task.job_zone)

            # Generate recipient(s)
            num_recipients = self.rng.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
            recipients = []
            for _ in range(num_recipients):
                recipient_person = self.names.generate_person()
                recipients.append(RecipientPersona(
                    name=recipient_person.full_name,
                    email=recipient_person.email,
                    job_title=self._generate_recipient_title(task),
                    relationship=self.rng.choice([
                        "colleague", "manager", "direct_report", "client"
                    ]),
                    english_variant=EnglishVariant.US,
                    is_technical=self.rng.random() < 0.3
                ))

            # Determine context dimensions
            formality = self._determine_formality(task.job_zone)
            urgency = self.rng.randint(1, 5)
            message_position = self.rng.choice(list(MessagePosition))
            emotional_context = self.rng.choices(
                list(EmotionalContext),
                weights=[0.6, 0.1, 0.1, 0.1, 0.1]
            )[0]
            audience_size = self.rng.choices(
                ["one_on_one", "small_group", "department", "company_wide", "public"],
                weights=[0.5, 0.25, 0.15, 0.07, 0.03]
            )[0]

            # Detect sensitive topics
            sensitive = self._detect_sensitive_topics(task.task)

            # Build prompt
            prompt = WritingPrompt(
                prompt_id=prompt_id,
                onet_task_id=task.task_id,
                onet_task=task.task,
                occupation_code=task.onetsoc_code,
                occupation_title=task.occupation_title,
                job_zone=task.job_zone,
                soc_major_group=task.soc_major_group,
                naics_code=industry.code if industry else "54",
                naics_sector=industry.sector_name if industry else "Professional Services",
                company=CompanyContext(
                    name=company.name if company else "Acme Corp",
                    size=company.size if company else "mid_market",
                    industry_naics=company.industry_naics if company else "54",
                    industry_name=company.sector_name if company else "Professional Services",
                    is_public=company.is_public if company else False,
                    hq_location=company.hq_location if company else "New York, NY",
                    employee_count=company.employee_count_approx if company else 500
                ),
                writer=WriterPersona(
                    name=writer_person.full_name,
                    email=writer_person.email,
                    age=writer_person.age,
                    generation=writer_person.generation,
                    job_title=task.occupation_title,
                    skill_level=skill_level,
                    english_variant=EnglishVariant.US
                ),
                recipients=recipients,
                audience_size=audience_size,
                formality_level=formality,
                urgency_level=urgency,
                message_position=message_position,
                emotional_context=emotional_context,
                sensitive_topics=sensitive,
                writing_category=task.writing_category,
                full_prompt=""  # Will be generated
            )

            # Generate the full prompt text
            prompt.full_prompt = self._build_prompt_text(prompt)
            prompts.append(prompt)

        return prompts

    def _job_zone_to_skill(self, job_zone: int) -> str:
        """Convert O*NET job zone to skill level"""
        mapping = {1: "entry", 2: "entry", 3: "mid", 4: "senior", 5: "executive"}
        return mapping.get(job_zone, "mid")

    def _determine_formality(self, job_zone: int) -> int:
        """Determine formality level based on job zone with variation"""
        base = job_zone
        variation = self.rng.randint(-1, 1)
        return max(1, min(5, base + variation))

    def _generate_recipient_title(self, task: ONetTask) -> str:
        """Generate appropriate recipient title for task"""
        titles_by_category = {
            "customer_communication": ["Customer", "Client", "Account Manager"],
            "internal_coordination": ["Manager", "Director", "Team Lead", "Colleague"],
            "reports_presentations": ["Executive", "Board Member", "Stakeholder"],
            "feedback_evaluation": ["Employee", "Team Member", "Direct Report"],
        }
        titles = titles_by_category.get(
            task.writing_category,
            ["Colleague", "Manager", "Client"]
        )
        return self.rng.choice(titles)

    def _detect_sensitive_topics(self, task_text: str) -> list[SensitiveTopic]:
        """Detect sensitive topics in task text"""
        sensitive = []
        task_lower = task_text.lower()

        if any(w in task_lower for w in ["performance", "termination", "disciplin"]):
            sensitive.append(SensitiveTopic.HR_ISSUES)
        if any(w in task_lower for w in ["legal", "compliance", "lawsuit", "contract"]):
            sensitive.append(SensitiveTopic.LEGAL)
        if any(w in task_lower for w in ["layoff", "downsiz", "reject", "cancel"]):
            sensitive.append(SensitiveTopic.BAD_NEWS)
        if any(w in task_lower for w in ["confidential", "proprietary", "sensitive"]):
            sensitive.append(SensitiveTopic.CONFIDENTIAL)
        if any(w in task_lower for w in ["complaint", "dispute", "conflict", "grievance"]):
            sensitive.append(SensitiveTopic.CONFLICT)

        return sensitive

    def _build_prompt_text(self, prompt: WritingPrompt) -> str:
        """Build the full prompt text from structured data"""
        parts = []

        # Context introduction
        parts.append(f"You are {prompt.writer.name}, a {prompt.writer.job_title} "
                     f"at {prompt.company.name}.")

        if prompt.company.size in ["startup", "small"]:
            parts.append(f"{prompt.company.name} is a {prompt.company.size} "
                         f"company with about {prompt.company.employee_count} employees.")

        # Task description
        parts.append(f"\nYour task: {prompt.onet_task}")

        # Recipient context
        if len(prompt.recipients) == 1:
            r = prompt.recipients[0]
            parts.append(f"\nWrite to {r.name}, {r.job_title}.")
        else:
            recipient_list = ", ".join(
                f"{r.name} ({r.job_title})" for r in prompt.recipients
            )
            parts.append(f"\nWrite to: {recipient_list}")

        # Additional context based on dimensions
        if prompt.urgency_level >= 4:
            parts.append("\nThis is urgent and time-sensitive.")

        if prompt.formality_level >= 4:
            parts.append("\nMaintain a formal, professional tone.")
        elif prompt.formality_level <= 2:
            parts.append("\nA casual, conversational tone is appropriate.")

        return "\n".join(parts)

    async def _phase3_enrich(
        self,
        prompts: list[WritingPrompt]
    ) -> AsyncGenerator[WritingPrompt, None]:
        """Phase 3: LLM enrichment for context-heavy prompts"""

        # Determine which prompts need enrichment
        enrichment_count = int(len(prompts) * self.config.context_rich_ratio)
        prompts_to_enrich = set(self.rng.sample(
            range(len(prompts)),
            enrichment_count
        ))

        for i, prompt in enumerate(prompts):
            if i in prompts_to_enrich:
                # Enrich with LLM
                enriched = await self._enrich_prompt(prompt)
                yield enriched
            else:
                yield prompt

    async def _enrich_prompt(self, prompt: WritingPrompt) -> WritingPrompt:
        """Enrich a single prompt with LLM-generated context"""

        enrichment_request = f"""
Given this writing task scenario, generate additional realistic context.

SCENARIO:
- Writer: {prompt.writer.name}, {prompt.writer.job_title} at {prompt.company.name}
- Task: {prompt.onet_task}
- Recipient(s): {', '.join(r.name for r in prompt.recipients)}
- Formality: {prompt.formality_level}/5
- Urgency: {prompt.urgency_level}/5

Generate:
1. A specific temporal context (date, deadline, recent event) if relevant
2. Any competing objectives the writer should balance
3. Mock attachment summaries if the task implies references
4. Prior email thread content if this is a reply

Return JSON with keys: temporal_context, competing_objectives, attachments, prior_context
Only include non-null values for what's relevant to THIS specific task.
"""

        try:
            response = await self.config.api_client.complete(
                model=self.config.enrichment_model,
                prompt=enrichment_request,
                max_tokens=500
            )

            # Parse enrichment
            import json
            enrichment = json.loads(response)

            if enrichment.get("temporal_context"):
                prompt.temporal_context = enrichment["temporal_context"]
            if enrichment.get("competing_objectives"):
                prompt.competing_objectives = enrichment["competing_objectives"]
            if enrichment.get("prior_context"):
                prompt.prior_context = enrichment["prior_context"]
                prompt.message_position = MessagePosition.REPLY
            if enrichment.get("attachments"):
                for att in enrichment["attachments"]:
                    prompt.attachments.append(Attachment(
                        type=att.get("type", "document"),
                        description=att.get("description", ""),
                        content=att.get("content", "")
                    ))

            # Rebuild prompt text with enrichment
            prompt.full_prompt = self._build_enriched_prompt_text(prompt)

        except Exception as e:
            # Log error but continue with unenriched prompt
            pass

        return prompt

    def _build_enriched_prompt_text(self, prompt: WritingPrompt) -> str:
        """Build enriched prompt text with all context"""
        parts = [self._build_prompt_text(prompt)]

        if prompt.temporal_context:
            parts.append(f"\nContext: {prompt.temporal_context}")

        if prompt.competing_objectives:
            parts.append(f"\nNote: {prompt.competing_objectives}")

        if prompt.prior_context:
            parts.append(f"\n--- Previous message ---\n{prompt.prior_context}\n---")

        if prompt.attachments:
            parts.append("\nReference materials:")
            for att in prompt.attachments:
                parts.append(f"- {att.description}: {att.content}")

        if prompt.constraints:
            parts.append("\nSpecific requirements:")
            for c in prompt.constraints:
                parts.append(f"- {c.description}")

        return "\n".join(parts)
```

---

## Part 5: OpenRouter API Integration

### 5.1 OpenRouter Client

```python
# src/api/openrouter_client.py

import httpx
import asyncio
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger()

@dataclass
class APIResponse:
    """Standardized API response"""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    raw_response: dict

class OpenRouterClient:
    """Async client for OpenRouter API"""

    BASE_URL = "https://openrouter.ai/api/v1"

    # Model ID mapping for OpenRouter
    MODEL_IDS = {
        # Pro-tier Gemini
        "gemini-3-pro": "google/gemini-3.0-pro",
        # Flash-tier Gemini
        "gemini-3-flash": "google/gemini-3.0-flash",
        # Pro-tier competitors
        "gpt-5.2-thinking": "openai/gpt-5.2-thinking",
        "claude-opus-4.5": "anthropic/claude-opus-4-5-20251101",
        "grok-4.1-thinking": "x-ai/grok-4.1-thinking",
        "kimi-k2-thinking": "moonshot/kimi-k2-thinking",
        # Flash-tier competitors
        "gpt-4.1": "openai/gpt-4.1",
        "claude-sonnet": "anthropic/claude-3-5-sonnet-20241022",
    }

    # Pricing per million tokens (input, output)
    PRICING = {
        "google/gemini-3.0-pro": (3.0, 15.0),
        "google/gemini-3.0-flash": (0.075, 0.30),
        "openai/gpt-5.2-thinking": (5.0, 20.0),
        "anthropic/claude-opus-4-5-20251101": (15.0, 75.0),
        "x-ai/grok-4.1-thinking": (5.0, 20.0),
        "moonshot/kimi-k2-thinking": (4.0, 16.0),
        "openai/gpt-4.1": (2.0, 8.0),
        "anthropic/claude-3-5-sonnet-20241022": (3.0, 15.0),
    }

    def __init__(
        self,
        api_key: str,
        max_concurrent: int = 10,
        timeout_seconds: int = 120
    ):
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.timeout = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://gemini-writing-eval.example.com",
                "X-Title": "Gemini Writing Eval Framework"
            },
            timeout=httpx.Timeout(self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def complete(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> APIResponse:
        """Send completion request to OpenRouter"""

        # Resolve model ID
        model_id = self.MODEL_IDS.get(model, model)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        async with self.semaphore:
            start_time = datetime.now()

            response = await self._client.post(
                "/chat/completions",
                json=payload
            )
            response.raise_for_status()

            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            data = response.json()

            return APIResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                input_tokens=data["usage"]["prompt_tokens"],
                output_tokens=data["usage"]["completion_tokens"],
                total_tokens=data["usage"]["total_tokens"],
                latency_ms=latency_ms,
                raw_response=data
            )

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost for a request"""
        model_id = self.MODEL_IDS.get(model, model)
        pricing = self.PRICING.get(model_id, (5.0, 20.0))

        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]

        return input_cost + output_cost
```

### 5.2 Rate Limiter

```python
# src/api/rate_limiter.py

import asyncio
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass

@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    burst_allowance: float = 1.2  # Allow 20% burst

class AdaptiveRateLimiter:
    """Adaptive rate limiter with token and request tracking"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times: deque = deque()
        self.token_usage: deque = deque()
        self._lock = asyncio.Lock()

        # Adaptive backoff state
        self.consecutive_rate_limits = 0
        self.base_delay = 0.0

    async def acquire(self, estimated_tokens: int = 1000):
        """Acquire permission to make a request"""
        async with self._lock:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)

            # Clean old entries
            while self.request_times and self.request_times[0] < minute_ago:
                self.request_times.popleft()
            while self.token_usage and self.token_usage[0][0] < minute_ago:
                self.token_usage.popleft()

            # Check request rate
            max_requests = int(self.config.requests_per_minute * self.config.burst_allowance)
            if len(self.request_times) >= max_requests:
                wait_time = (self.request_times[0] - minute_ago).total_seconds()
                await asyncio.sleep(max(wait_time, 0.1))

            # Check token rate
            current_tokens = sum(t[1] for t in self.token_usage)
            max_tokens = int(self.config.tokens_per_minute * self.config.burst_allowance)
            if current_tokens + estimated_tokens > max_tokens:
                # Wait proportionally
                wait_time = (estimated_tokens / self.config.tokens_per_minute) * 60
                await asyncio.sleep(wait_time)

            # Apply adaptive backoff if needed
            if self.base_delay > 0:
                await asyncio.sleep(self.base_delay)

            # Record this request
            self.request_times.append(datetime.now())

    def record_usage(self, tokens: int):
        """Record token usage after a request"""
        self.token_usage.append((datetime.now(), tokens))

    def record_rate_limit(self):
        """Record a rate limit hit for adaptive backoff"""
        self.consecutive_rate_limits += 1
        self.base_delay = min(30.0, 2 ** self.consecutive_rate_limits)

    def record_success(self):
        """Record a successful request"""
        self.consecutive_rate_limits = max(0, self.consecutive_rate_limits - 1)
        if self.consecutive_rate_limits == 0:
            self.base_delay = 0.0
```

### 5.3 Retry Handler with Circuit Breaker

```python
# src/api/retry_handler.py

import asyncio
import random
from typing import Callable, TypeVar, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import httpx

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class RetryConfig:
    """Retry configuration"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.5

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

class CircuitBreaker:
    """Circuit breaker for API calls"""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        """Check if execution is allowed"""
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if we should try half-open
                if self.last_failure_time:
                    elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                    if elapsed >= self.config.recovery_timeout:
                        self.state = CircuitState.HALF_OPEN
                        self.half_open_calls = 0
                        return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return self.half_open_calls < self.config.half_open_max_calls

        return False

    async def record_success(self):
        """Record a successful call"""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0

            self.failure_count = max(0, self.failure_count - 1)

    async def record_failure(self):
        """Record a failed call"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

async def retry_with_backoff(
    func: Callable[..., T],
    config: RetryConfig = RetryConfig(),
    circuit_breaker: CircuitBreaker | None = None,
    retryable_exceptions: tuple = (httpx.HTTPStatusError, httpx.TimeoutException)
) -> T:
    """Execute function with exponential backoff retry"""

    last_exception = None

    for attempt in range(config.max_retries + 1):
        # Check circuit breaker
        if circuit_breaker and not await circuit_breaker.can_execute():
            raise RuntimeError("Circuit breaker is open")

        try:
            result = await func()

            if circuit_breaker:
                await circuit_breaker.record_success()

            return result

        except retryable_exceptions as e:
            last_exception = e

            if circuit_breaker:
                await circuit_breaker.record_failure()

            if attempt < config.max_retries:
                # Calculate delay with exponential backoff and jitter
                delay = config.base_delay * (config.exponential_base ** attempt)
                delay = min(delay, config.max_delay)
                jitter = delay * config.jitter * random.random()
                delay += jitter

                await asyncio.sleep(delay)

    raise last_exception
```

---

## Part 6: Evaluation Engine

### 6.1 Core Evaluation Engine

```python
# src/eval/engine.py

import asyncio
from typing import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import structlog

from src.prompts.schemas import WritingPrompt
from src.eval.schemas import (
    ModelResponse, ComparisonResult, JudgeAggregation, SingleVote
)
from src.api.openrouter_client import OpenRouterClient
from src.storage.checkpoint import CheckpointManager
from src.config.settings import EvalConfig

logger = structlog.get_logger()

@dataclass
class EvalProgress:
    """Current evaluation progress"""
    total_prompts: int
    completed_prompts: int
    current_phase: str  # "generation", "judging", "analysis"
    model_pair_progress: dict[str, tuple[int, int]]  # model_pair -> (completed, total)
    running_win_rates: dict[str, float]
    estimated_cost: float
    elapsed_seconds: int
    eta_seconds: int

class EvaluationEngine:
    """Main evaluation orchestrator"""

    def __init__(
        self,
        config: EvalConfig,
        api_client: OpenRouterClient,
        checkpoint: CheckpointManager
    ):
        self.config = config
        self.api = api_client
        self.checkpoint = checkpoint
        self.progress = EvalProgress(
            total_prompts=0,
            completed_prompts=0,
            current_phase="initialization",
            model_pair_progress={},
            running_win_rates={},
            estimated_cost=0.0,
            elapsed_seconds=0,
            eta_seconds=0
        )
        self._start_time: datetime | None = None
        self._cancel_event = asyncio.Event()

    async def run_evaluation(
        self,
        prompts: list[WritingPrompt]
    ) -> AsyncGenerator[ComparisonResult, None]:
        """Run full evaluation pipeline"""

        self._start_time = datetime.now()
        self.progress.total_prompts = len(prompts)
        self.progress.current_phase = "generation"

        # Initialize model pair progress
        for gemini, competitor in self.config.model_pairs:
            pair_key = f"{gemini}_vs_{competitor}"
            self.progress.model_pair_progress[pair_key] = (0, len(prompts))

        # Process each prompt
        for prompt in prompts:
            if self._cancel_event.is_set():
                logger.info("Evaluation cancelled")
                break

            # Check if already completed
            if self.checkpoint.is_prompt_completed(prompt.prompt_id):
                self.progress.completed_prompts += 1
                continue

            # Generate responses for all models
            responses = await self._generate_responses(prompt)

            # Judge all model pairs
            self.progress.current_phase = "judging"
            for gemini_model, competitor_model in self.config.model_pairs:
                gemini_response = responses.get(gemini_model)
                competitor_response = responses.get(competitor_model)

                if not gemini_response or not competitor_response:
                    continue

                # Run comparison
                result = await self._judge_comparison(
                    prompt, gemini_response, competitor_response
                )

                # Save checkpoint
                await self.checkpoint.save_comparison(result)

                # Update progress
                pair_key = f"{gemini_model}_vs_{competitor_model}"
                completed, total = self.progress.model_pair_progress[pair_key]
                self.progress.model_pair_progress[pair_key] = (completed + 1, total)

                # Update running win rate
                await self._update_win_rate(pair_key, result)

                yield result

            self.progress.completed_prompts += 1
            self._update_eta()

    async def _generate_responses(
        self,
        prompt: WritingPrompt
    ) -> dict[str, ModelResponse]:
        """Generate responses from all models for a prompt"""

        responses = {}

        # Get unique models from pairs
        models = set()
        for gemini, competitor in self.config.model_pairs:
            models.add(gemini)
            models.add(competitor)

        # Generate responses concurrently
        tasks = []
        for model in models:
            tasks.append(self._generate_single_response(prompt, model))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for model, result in zip(models, results):
            if isinstance(result, Exception):
                logger.error("Response generation failed", model=model, error=str(result))
                responses[model] = self._create_error_response(prompt, model, result)
            else:
                responses[model] = result

        return responses

    async def _generate_single_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> ModelResponse:
        """Generate a single response from a model"""

        start_time = datetime.now()

        try:
            api_response = await self.api.complete(
                model=model,
                prompt=prompt.full_prompt,
                max_tokens=4096,
                temperature=0.7
            )

            # Detect response format
            response_text = api_response.content
            word_count = len(response_text.split())

            return ModelResponse(
                response_id=f"{prompt.prompt_id}_{model}_{int(start_time.timestamp())}",
                prompt_id=prompt.prompt_id,
                model_id=model,
                model_name=model,
                response_text=response_text,
                response_time_ms=api_response.latency_ms,
                input_tokens=api_response.input_tokens,
                output_tokens=api_response.output_tokens,
                total_tokens=api_response.total_tokens,
                status="success",
                used_bullet_points="- " in response_text or "* " in response_text,
                used_headers=any(line.startswith("#") for line in response_text.split("\n")),
                has_greeting=any(g in response_text.lower()[:100] for g in ["dear", "hi ", "hello"]),
                has_signoff=any(s in response_text.lower()[-100:] for s in ["regards", "sincerely", "best"]),
                word_count=word_count,
                character_count=len(response_text)
            )

        except Exception as e:
            return self._create_error_response(prompt, model, e)

    def _create_error_response(
        self,
        prompt: WritingPrompt,
        model: str,
        error: Exception
    ) -> ModelResponse:
        """Create error response for failed generation"""
        return ModelResponse(
            response_id=f"{prompt.prompt_id}_{model}_error",
            prompt_id=prompt.prompt_id,
            model_id=model,
            model_name=model,
            response_text="",
            response_time_ms=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            status="error",
            error_message=str(error),
            word_count=0,
            character_count=0
        )

    async def _judge_comparison(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> ComparisonResult:
        """Judge a comparison between Gemini and competitor"""

        # Handle auto-loss cases
        if gemini_response.status != "success":
            return self._create_auto_loss_result(
                prompt, gemini_response, competitor_response,
                gemini_lost=True, reason=gemini_response.error_message
            )

        if competitor_response.status != "success":
            return self._create_auto_loss_result(
                prompt, gemini_response, competitor_response,
                gemini_lost=False, reason=competitor_response.error_message
            )

        # Run judges
        judge_results = []

        for judge_model in self.config.judge_config.models:
            for persona in self._get_judge_personas():
                aggregation = await self._run_judge_votes(
                    prompt, gemini_response, competitor_response,
                    judge_model, persona
                )
                judge_results.append(aggregation)

        # Aggregate final result
        final_winner = self._aggregate_judge_results(judge_results)

        return ComparisonResult(
            comparison_id=f"{prompt.prompt_id}_{gemini_response.model_id}_vs_{competitor_response.model_id}",
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_response.model_id,
            competitor_model=competitor_response.model_id,
            gemini_response_id=gemini_response.response_id,
            competitor_response_id=competitor_response.response_id,
            judge_results=judge_results,
            final_winner=final_winner,
            judges_for_gemini=sum(1 for j in judge_results if j.gemini_win),
            judges_for_competitor=sum(1 for j in judge_results if j.gemini_loss),
            judges_tie=sum(1 for j in judge_results if j.is_tie)
        )

    async def _run_judge_votes(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse,
        judge_model: str,
        persona: str
    ) -> JudgeAggregation:
        """Run best-of-N votes for a single judge"""

        votes = []
        vote_count = self.config.judge_config.votes_per_judge

        for vote_num in range(vote_count):
            # Deterministic shuffle based on vote number
            import hashlib
            shuffle_seed = int(hashlib.md5(
                f"{prompt.prompt_id}_{judge_model}_{persona}_{vote_num}".encode()
            ).hexdigest()[:8], 16)

            gemini_position = "A" if shuffle_seed % 2 == 0 else "B"

            vote = await self._run_single_vote(
                prompt, gemini_response, competitor_response,
                judge_model, persona, gemini_position
            )
            votes.append(vote)

        # Aggregate votes
        gemini_wins = sum(1 for v in votes if v.winner == gemini_position)
        competitor_wins = sum(1 for v in votes if v.winner != gemini_position and v.winner != "tie")
        ties = sum(1 for v in votes if v.winner == "tie")

        if gemini_wins > competitor_wins:
            majority = "gemini"
        elif competitor_wins > gemini_wins:
            majority = "competitor"
        else:
            majority = "tie"

        return JudgeAggregation(
            judge_model=judge_model,
            judge_persona=persona,
            prompt_id=prompt.prompt_id,
            votes=votes,
            majority_winner=majority,
            vote_count_a=gemini_wins if gemini_position == "A" else competitor_wins,
            vote_count_b=competitor_wins if gemini_position == "A" else gemini_wins,
            vote_count_tie=ties,
            gemini_win=majority == "gemini",
            gemini_loss=majority == "competitor",
            is_tie=majority == "tie"
        )

    async def _run_single_vote(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse,
        judge_model: str,
        persona: str,
        gemini_position: str
    ) -> SingleVote:
        """Run a single judge vote"""

        # Build judge prompt
        if gemini_position == "A":
            response_a = gemini_response.response_text
            response_b = competitor_response.response_text
        else:
            response_a = competitor_response.response_text
            response_b = gemini_response.response_text

        judge_prompt = self._build_judge_prompt(
            prompt, response_a, response_b, persona
        )

        start_time = datetime.now()

        api_response = await self.api.complete(
            model=judge_model,
            prompt=judge_prompt,
            max_tokens=1500,
            temperature=0.3
        )

        # Parse judge response
        parsed = self._parse_judge_response(api_response.content)

        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return SingleVote(
            vote_id=f"{prompt.prompt_id}_{judge_model}_{persona}_{gemini_position}",
            judge_model=judge_model,
            judge_persona=persona,
            prompt_id=prompt.prompt_id,
            response_a_id=gemini_response.response_id if gemini_position == "A" else competitor_response.response_id,
            response_b_id=competitor_response.response_id if gemini_position == "A" else gemini_response.response_id,
            gemini_position=gemini_position,
            winner=parsed["winner"],
            confidence=parsed.get("confidence", 0.5),
            scores_a=parsed.get("scores_a", {}),
            scores_b=parsed.get("scores_b", {}),
            reasoning=parsed.get("reasoning", ""),
            response_time_ms=latency_ms
        )

    def _get_judge_personas(self) -> list[str]:
        """Get list of judge personas to use"""
        if self.config.judge_config.use_both_personas:
            return ["writing_expert", "target_recipient"]
        return ["writing_expert"]

    def _aggregate_judge_results(
        self,
        judge_results: list[JudgeAggregation]
    ) -> str:
        """Aggregate judge results using majority-of-majorities"""
        gemini_wins = sum(1 for j in judge_results if j.gemini_win)
        competitor_wins = sum(1 for j in judge_results if j.gemini_loss)

        if gemini_wins > competitor_wins:
            return "gemini"
        elif competitor_wins > gemini_wins:
            return "competitor"
        return "tie"

    def cancel(self):
        """Cancel the evaluation"""
        self._cancel_event.set()

    def _update_eta(self):
        """Update estimated time remaining"""
        if self._start_time and self.progress.completed_prompts > 0:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            rate = self.progress.completed_prompts / elapsed
            remaining = self.progress.total_prompts - self.progress.completed_prompts
            self.progress.eta_seconds = int(remaining / rate) if rate > 0 else 0
            self.progress.elapsed_seconds = int(elapsed)
```

### 6.2 Judge Prompts

```python
# src/eval/judge_prompts.py

WRITING_EXPERT_SYSTEM = """You are an expert writing evaluator with decades of experience
assessing professional communication. Your expertise spans business writing, technical
documentation, creative content, and interpersonal correspondence.

You will evaluate two responses to the same writing task. Focus on:
- Quality of writing craft (clarity, structure, flow)
- Appropriate length for the task
- Tone appropriateness for the context
- Effectiveness in achieving the communication goal
- Authenticity - does it read as realistic human writing, not AI-generated?
- Avoidance of cliches and boilerplate phrases
- Task completion - does it fully address what was asked?

Be objective. Evaluate based on the specific scenario provided."""

TARGET_RECIPIENT_SYSTEM = """You are roleplaying as the target recipient of this writing.
Based on the scenario provided, evaluate which response would be more effective FROM YOUR
PERSPECTIVE as the recipient.

Consider:
- Would you understand the message clearly?
- Is the tone appropriate for your relationship with the sender?
- Does it address your needs/concerns?
- Would you feel respected and valued?
- Is the length appropriate - not too long or too short?
- Would you be able to take action based on this communication?

Be objective. Think about what YOU as the recipient would actually prefer."""

JUDGE_PROMPT_TEMPLATE = """
WRITING TASK:
{task_description}

WRITER CONTEXT:
- Name: {writer_name}, {writer_title}
- Company: {company_name} ({company_size})
- Experience Level: {skill_level}
- Generation: {generation}

RECIPIENT CONTEXT:
{recipient_context}

FORMALITY LEVEL: {formality}/5
URGENCY LEVEL: {urgency}/5

---

RESPONSE A:
{response_a}

---

RESPONSE B:
{response_b}

---

Evaluate both responses on these criteria (1-5 scale each):
1. Writing Quality - clarity, structure, professionalism
2. Tone Appropriateness - matches formality and context
3. Length Appropriateness - right amount of content for the task
4. Task Completion - fully addresses the writing task
5. Authenticity - reads as natural human writing, not AI-generated
6. Cliche Avoidance - avoids overused phrases and AI patterns
7. Effectiveness - would achieve the communication goal

Then determine the winner: A, B, or tie.

Respond in this exact JSON format:
{{
  "scores_a": {{"quality": N, "tone": N, "length": N, "completion": N, "authenticity": N, "cliche_avoidance": N, "effectiveness": N}},
  "scores_b": {{"quality": N, "tone": N, "length": N, "completion": N, "authenticity": N, "cliche_avoidance": N, "effectiveness": N}},
  "winner": "A" or "B" or "tie",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your decision"
}}
"""

def build_judge_prompt(
    prompt: "WritingPrompt",
    response_a: str,
    response_b: str,
    persona: str
) -> tuple[str, str]:
    """Build judge prompt with system and user messages"""

    system = WRITING_EXPERT_SYSTEM if persona == "writing_expert" else TARGET_RECIPIENT_SYSTEM

    # Build recipient context
    recipient_lines = []
    for r in prompt.recipients:
        recipient_lines.append(f"- {r.name}, {r.job_title} ({r.relationship})")
    recipient_context = "\n".join(recipient_lines)

    user_prompt = JUDGE_PROMPT_TEMPLATE.format(
        task_description=prompt.onet_task,
        writer_name=prompt.writer.name,
        writer_title=prompt.writer.job_title,
        company_name=prompt.company.name,
        company_size=prompt.company.size,
        skill_level=prompt.writer.skill_level,
        generation=prompt.writer.generation,
        recipient_context=recipient_context,
        formality=prompt.formality_level,
        urgency=prompt.urgency_level,
        response_a=response_a,
        response_b=response_b
    )

    return system, user_prompt
```

---

## Part 7: Storage, Checkpointing, and Analysis

### 7.1 SQLite Database Schema

```python
# src/storage/database.py

import aiosqlite
from pathlib import Path
from datetime import datetime

SCHEMA = """
-- Prompts table
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    onet_task_id TEXT,
    onet_task TEXT,
    occupation_code TEXT,
    occupation_title TEXT,
    job_zone INTEGER,
    soc_major_group TEXT,
    naics_code TEXT,
    naics_sector TEXT,
    company_name TEXT,
    company_size TEXT,
    writer_name TEXT,
    writer_age INTEGER,
    writer_generation TEXT,
    writer_skill_level TEXT,
    formality_level INTEGER,
    urgency_level INTEGER,
    audience_size TEXT,
    emotional_context TEXT,
    writing_category TEXT,
    is_revision_task BOOLEAN,
    is_ambiguous BOOLEAN,
    full_prompt TEXT,
    created_at TIMESTAMP
);

-- Model responses table
CREATE TABLE IF NOT EXISTS responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT,
    model_id TEXT,
    model_name TEXT,
    response_text TEXT,
    response_time_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    status TEXT,
    refusal_category TEXT,
    error_message TEXT,
    used_bullet_points BOOLEAN,
    used_headers BOOLEAN,
    has_greeting BOOLEAN,
    has_signoff BOOLEAN,
    word_count INTEGER,
    character_count INTEGER,
    created_at TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);

-- Individual votes table
CREATE TABLE IF NOT EXISTS votes (
    vote_id TEXT PRIMARY KEY,
    judge_model TEXT,
    judge_persona TEXT,
    prompt_id TEXT,
    response_a_id TEXT,
    response_b_id TEXT,
    gemini_position TEXT,
    winner TEXT,
    confidence REAL,
    scores_a_json TEXT,
    scores_b_json TEXT,
    reasoning TEXT,
    response_time_ms INTEGER,
    created_at TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);

-- Comparison results table
CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT,
    gemini_model TEXT,
    competitor_model TEXT,
    gemini_response_id TEXT,
    competitor_response_id TEXT,
    final_winner TEXT,
    judges_for_gemini INTEGER,
    judges_for_competitor INTEGER,
    judges_tie INTEGER,
    gemini_auto_loss BOOLEAN,
    competitor_auto_loss BOOLEAN,
    auto_loss_reason TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_responses_prompt ON responses(prompt_id);
CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
CREATE INDEX IF NOT EXISTS idx_votes_prompt ON votes(prompt_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_models ON comparisons(gemini_model, competitor_model);
CREATE INDEX IF NOT EXISTS idx_comparisons_winner ON comparisons(final_winner);
CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(occupation_code);
CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(writing_category);
"""

class ResultsDatabase:
    """SQLite database for evaluation results"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self):
        """Initialize database and create schema"""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.executescript(SCHEMA)
        await self._connection.commit()

    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()

    async def save_prompt(self, prompt: "WritingPrompt"):
        """Save a prompt to the database"""
        await self._connection.execute("""
            INSERT OR REPLACE INTO prompts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prompt.prompt_id, prompt.onet_task_id, prompt.onet_task,
            prompt.occupation_code, prompt.occupation_title, prompt.job_zone,
            prompt.soc_major_group, prompt.naics_code, prompt.naics_sector,
            prompt.company.name, prompt.company.size, prompt.writer.name,
            prompt.writer.age, prompt.writer.generation, prompt.writer.skill_level,
            prompt.formality_level, prompt.urgency_level, prompt.audience_size,
            prompt.emotional_context.value, prompt.writing_category,
            prompt.is_revision_task, prompt.is_ambiguous, prompt.full_prompt,
            datetime.utcnow()
        ))
        await self._connection.commit()

    async def save_response(self, response: "ModelResponse"):
        """Save a model response to the database"""
        await self._connection.execute("""
            INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.response_id, response.prompt_id, response.model_id,
            response.model_name, response.response_text, response.response_time_ms,
            response.input_tokens, response.output_tokens, response.total_tokens,
            response.status, response.refusal_category, response.error_message,
            response.used_bullet_points, response.used_headers, response.has_greeting,
            response.has_signoff, response.word_count, response.character_count,
            datetime.utcnow()
        ))
        await self._connection.commit()

    async def save_comparison(self, comparison: "ComparisonResult"):
        """Save a comparison result to the database"""
        await self._connection.execute("""
            INSERT OR REPLACE INTO comparisons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comparison.comparison_id, comparison.prompt_id, comparison.gemini_model,
            comparison.competitor_model, comparison.gemini_response_id,
            comparison.competitor_response_id, comparison.final_winner,
            comparison.judges_for_gemini, comparison.judges_for_competitor,
            comparison.judges_tie, comparison.gemini_auto_loss,
            comparison.competitor_auto_loss, comparison.auto_loss_reason,
            datetime.utcnow()
        ))
        await self._connection.commit()

    async def get_win_rates(self, model_pair: str | None = None) -> dict:
        """Get win rates aggregated by model pair"""
        query = """
            SELECT
                gemini_model || '_vs_' || competitor_model as pair,
                COUNT(*) as total,
                SUM(CASE WHEN final_winner = 'gemini' THEN 1 ELSE 0 END) as gemini_wins,
                SUM(CASE WHEN final_winner = 'competitor' THEN 1 ELSE 0 END) as competitor_wins,
                SUM(CASE WHEN final_winner = 'tie' THEN 1 ELSE 0 END) as ties
            FROM comparisons
        """
        if model_pair:
            query += " WHERE gemini_model || '_vs_' || competitor_model = ?"
            query += " GROUP BY pair"
            cursor = await self._connection.execute(query, [model_pair])
        else:
            query += " GROUP BY pair"
            cursor = await self._connection.execute(query)

        results = {}
        async for row in cursor:
            pair, total, gemini_wins, competitor_wins, ties = row
            results[pair] = {
                "total": total,
                "gemini_wins": gemini_wins,
                "competitor_wins": competitor_wins,
                "ties": ties,
                "gemini_win_rate": gemini_wins / total if total > 0 else 0
            }
        return results

    async def get_win_rates_by_dimension(
        self,
        dimension: str  # occupation_code, writing_category, job_zone, etc.
    ) -> dict:
        """Get win rates broken down by a dimension"""
        query = f"""
            SELECT
                p.{dimension},
                c.gemini_model || '_vs_' || c.competitor_model as pair,
                COUNT(*) as total,
                SUM(CASE WHEN c.final_winner = 'gemini' THEN 1 ELSE 0 END) as gemini_wins
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            GROUP BY p.{dimension}, pair
        """
        cursor = await self._connection.execute(query)

        results = {}
        async for row in cursor:
            dim_value, pair, total, gemini_wins = row
            if dim_value not in results:
                results[dim_value] = {}
            results[dim_value][pair] = {
                "total": total,
                "gemini_wins": gemini_wins,
                "win_rate": gemini_wins / total if total > 0 else 0
            }
        return results
```

### 7.2 Checkpoint Manager

```python
# src/storage/checkpoint.py

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class CheckpointState:
    """Checkpoint state for resumability"""
    run_id: str
    total_prompts: int
    completed_prompt_ids: list[str]
    completed_comparison_ids: list[str]
    last_updated: str
    phase: str  # "generation", "judging", "analysis"

class CheckpointManager:
    """Manages checkpointing for resumable evaluation"""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"
        self.state: CheckpointState | None = None

    def initialize(self, run_id: str, total_prompts: int):
        """Initialize a new checkpoint"""
        self.state = CheckpointState(
            run_id=run_id,
            total_prompts=total_prompts,
            completed_prompt_ids=[],
            completed_comparison_ids=[],
            last_updated=datetime.utcnow().isoformat(),
            phase="generation"
        )
        self._save()

    def load(self) -> bool:
        """Load existing checkpoint if available"""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file) as f:
                data = json.load(f)
                self.state = CheckpointState(**data)
            return True
        return False

    def is_prompt_completed(self, prompt_id: str) -> bool:
        """Check if a prompt has been completed"""
        if not self.state:
            return False
        return prompt_id in self.state.completed_prompt_ids

    def mark_prompt_completed(self, prompt_id: str):
        """Mark a prompt as completed"""
        if self.state and prompt_id not in self.state.completed_prompt_ids:
            self.state.completed_prompt_ids.append(prompt_id)
            self.state.last_updated = datetime.utcnow().isoformat()
            self._save()

    async def save_comparison(self, comparison: "ComparisonResult"):
        """Save a comparison and update checkpoint"""
        if self.state:
            if comparison.comparison_id not in self.state.completed_comparison_ids:
                self.state.completed_comparison_ids.append(comparison.comparison_id)
                self.state.last_updated = datetime.utcnow().isoformat()
                self._save()

    def set_phase(self, phase: str):
        """Update current phase"""
        if self.state:
            self.state.phase = phase
            self.state.last_updated = datetime.utcnow().isoformat()
            self._save()

    def _save(self):
        """Save checkpoint to disk"""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_file, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def get_progress(self) -> tuple[int, int]:
        """Get progress as (completed, total)"""
        if not self.state:
            return (0, 0)
        return (len(self.state.completed_prompt_ids), self.state.total_prompts)
```

### 7.3 Statistical Analysis

```python
# src/analysis/statistics.py

import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import Optional

@dataclass
class WinRateStats:
    """Win rate with statistical analysis"""
    win_rate: float
    n_total: int
    n_wins: int
    n_losses: int
    n_ties: int
    confidence_interval_95: tuple[float, float]
    standard_error: float
    is_significant: bool  # vs 50% baseline
    p_value: float

@dataclass
class EffectSize:
    """Effect size metrics"""
    cohens_h: float  # For proportions
    interpretation: str  # small, medium, large

def calculate_win_rate_stats(
    wins: int,
    losses: int,
    ties: int
) -> WinRateStats:
    """Calculate win rate with confidence intervals"""

    total = wins + losses + ties
    if total == 0:
        return WinRateStats(
            win_rate=0.5, n_total=0, n_wins=0, n_losses=0, n_ties=0,
            confidence_interval_95=(0, 1), standard_error=0,
            is_significant=False, p_value=1.0
        )

    # Win rate (excluding ties)
    decisive = wins + losses
    if decisive == 0:
        win_rate = 0.5
    else:
        win_rate = wins / decisive

    # Standard error (Wilson score interval)
    se = np.sqrt(win_rate * (1 - win_rate) / decisive) if decisive > 0 else 0

    # 95% confidence interval (Wilson score)
    z = 1.96
    if decisive > 0:
        denominator = 1 + z**2 / decisive
        center = (win_rate + z**2 / (2 * decisive)) / denominator
        margin = z * np.sqrt(win_rate * (1 - win_rate) / decisive + z**2 / (4 * decisive**2)) / denominator
        ci_lower = max(0, center - margin)
        ci_upper = min(1, center + margin)
    else:
        ci_lower, ci_upper = 0, 1

    # Binomial test against 50%
    if decisive > 0:
        p_value = stats.binom_test(wins, decisive, 0.5, alternative='two-sided')
    else:
        p_value = 1.0

    is_significant = p_value < 0.05

    return WinRateStats(
        win_rate=win_rate,
        n_total=total,
        n_wins=wins,
        n_losses=losses,
        n_ties=ties,
        confidence_interval_95=(ci_lower, ci_upper),
        standard_error=se,
        is_significant=is_significant,
        p_value=p_value
    )

def calculate_cohens_kappa(
    ratings_1: list[str],
    ratings_2: list[str],
    categories: list[str] = ["A", "B", "tie"]
) -> float:
    """Calculate Cohen's Kappa for inter-rater reliability"""

    if len(ratings_1) != len(ratings_2):
        raise ValueError("Rating lists must have same length")

    n = len(ratings_1)
    if n == 0:
        return 0.0

    # Build contingency matrix
    matrix = np.zeros((len(categories), len(categories)))
    cat_to_idx = {c: i for i, c in enumerate(categories)}

    for r1, r2 in zip(ratings_1, ratings_2):
        if r1 in cat_to_idx and r2 in cat_to_idx:
            matrix[cat_to_idx[r1], cat_to_idx[r2]] += 1

    # Calculate observed agreement
    po = np.trace(matrix) / n

    # Calculate expected agreement
    row_totals = matrix.sum(axis=1)
    col_totals = matrix.sum(axis=0)
    pe = np.sum(row_totals * col_totals) / (n ** 2)

    # Cohen's Kappa
    if pe == 1:
        return 1.0
    kappa = (po - pe) / (1 - pe)

    return kappa

def calculate_effect_size(p1: float, p2: float) -> EffectSize:
    """Calculate Cohen's h for two proportions"""

    # Transform proportions using arcsine
    phi1 = 2 * np.arcsin(np.sqrt(p1))
    phi2 = 2 * np.arcsin(np.sqrt(p2))

    h = abs(phi1 - phi2)

    # Interpret effect size
    if h < 0.2:
        interpretation = "negligible"
    elif h < 0.5:
        interpretation = "small"
    elif h < 0.8:
        interpretation = "medium"
    else:
        interpretation = "large"

    return EffectSize(cohens_h=h, interpretation=interpretation)

def identify_significant_weaknesses(
    win_rates_by_dimension: dict[str, dict],
    min_samples: int = 10,
    significance_threshold: float = 0.05
) -> list[dict]:
    """Identify statistically significant weaknesses"""

    weaknesses = []

    for dimension_value, pairs in win_rates_by_dimension.items():
        for pair, stats_dict in pairs.items():
            if stats_dict["total"] < min_samples:
                continue

            win_rate = stats_dict["win_rate"]

            # Check if significantly below 50%
            stats_result = calculate_win_rate_stats(
                wins=int(stats_dict["gemini_wins"]),
                losses=stats_dict["total"] - int(stats_dict["gemini_wins"]),
                ties=0
            )

            if stats_result.is_significant and win_rate < 0.5:
                effect = calculate_effect_size(win_rate, 0.5)
                weaknesses.append({
                    "dimension_value": dimension_value,
                    "model_pair": pair,
                    "win_rate": win_rate,
                    "sample_size": stats_dict["total"],
                    "p_value": stats_result.p_value,
                    "effect_size": effect.cohens_h,
                    "effect_interpretation": effect.interpretation,
                    "confidence_interval": stats_result.confidence_interval_95
                })

    # Sort by effect size (largest weakness first)
    weaknesses.sort(key=lambda x: x["effect_size"], reverse=True)

    return weaknesses
```

---

## Part 8: TUI Progress Dashboard and CLI

### 8.1 Progress Dashboard with Textual

```python
# src/tui/progress_dashboard.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from datetime import timedelta

class OverallProgress(Static):
    """Overall progress display"""

    progress = reactive(0.0)
    phase = reactive("initialization")
    eta = reactive(0)

    def render(self) -> Panel:
        bar = "[" + "=" * int(self.progress * 40) + " " * (40 - int(self.progress * 40)) + "]"
        eta_str = str(timedelta(seconds=self.eta)) if self.eta > 0 else "--:--:--"

        content = f"""
{bar} {self.progress * 100:.1f}%

Phase: {self.phase.upper()}  |  ETA: {eta_str}
"""
        return Panel(content, title="Overall Progress", border_style="blue")

class ModelPairProgress(Static):
    """Progress for each model pair"""

    def __init__(self, pairs: list[tuple[str, str]], **kwargs):
        super().__init__(**kwargs)
        self.pairs = pairs
        self.progress_data = {f"{g}_vs_{c}": (0, 0, 0.0) for g, c in pairs}

    def update_pair(self, pair_key: str, completed: int, total: int, win_rate: float):
        self.progress_data[pair_key] = (completed, total, win_rate)
        self.refresh()

    def render(self) -> Panel:
        lines = []
        for pair, (completed, total, win_rate) in self.progress_data.items():
            pct = completed / total if total > 0 else 0
            bar = "=" * int(pct * 20) + " " * (20 - int(pct * 20))
            status = "DONE" if completed == total else ""
            wr = f"{win_rate * 100:.1f}%" if completed > 0 else "--"
            lines.append(f"{pair:30} [{bar}] {completed:4}/{total:4} {status:4} [{wr:>6}]")

        return Panel("\n".join(lines), title="Model Pairs", border_style="green")

class CurrentBatch(Static):
    """Current batch being processed"""

    prompt_id = reactive("")
    occupation = reactive("")
    industry = reactive("")
    response_status = reactive({})
    judge_status = reactive({})

    def render(self) -> Panel:
        # Response status
        resp_lines = []
        for model, (status, time_ms) in self.response_status.items():
            icon = "[green]OK[/]" if status == "done" else "[yellow]...[/]"
            time_str = f"{time_ms/1000:.1f}s" if time_ms else ""
            resp_lines.append(f"  {model:20} {icon} {time_str}")

        # Judge status
        judge_lines = []
        for judge, (done, total, result) in self.judge_status.items():
            dots = "*" * done + "." * (total - done)
            judge_lines.append(f"  {judge:15} [{dots}] {result}")

        content = f"""
Prompt: {self.prompt_id}
Occupation: {self.occupation}
Industry: {self.industry}

Responses:
{chr(10).join(resp_lines)}

Judging:
{chr(10).join(judge_lines)}
"""
        return Panel(content, title="Current Batch", border_style="yellow")

class LiveStats(Static):
    """Live statistics display"""

    win_rates = reactive({})
    kappa = reactive(0.0)
    avg_response_time = reactive(0.0)
    cost_so_far = reactive(0.0)
    cost_projected = reactive(0.0)

    def render(self) -> Panel:
        wr_lines = []
        for pair, rate in self.win_rates.items():
            ci = 4.3  # Placeholder
            wr_lines.append(f"  {pair:25} {rate*100:5.1f}% +/- {ci:.1f}%")

        content = f"""
Win Rates (Running)              Performance
-------------------------        ---------------------------
{chr(10).join(wr_lines)}

Judge Agreement: {self.kappa:.2f} kappa       Avg response: {self.avg_response_time:.1f}s
                                   Cost so far: ${self.cost_so_far:.2f}
                                   Projected:   ${self.cost_projected:.2f}
"""
        return Panel(content, title="Live Statistics", border_style="cyan")

class ActivityLog(Log):
    """Scrolling activity log"""
    pass

class ProgressDashboard(App):
    """Main TUI application for progress visualization"""

    CSS = """
    #main {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 2fr 1fr;
    }
    OverallProgress { row-span: 1; }
    ModelPairProgress { row-span: 1; }
    CurrentBatch { row-span: 1; }
    LiveStats { row-span: 1; }
    ActivityLog { row-span: 1; column-span: 2; height: 10; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause"),
        ("d", "detail", "Detail View"),
        ("h", "help", "Help"),
    ]

    def __init__(self, model_pairs: list[tuple[str, str]], **kwargs):
        super().__init__(**kwargs)
        self.model_pairs = model_pairs

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            yield OverallProgress(id="overall")
            yield ModelPairProgress(self.model_pairs, id="pairs")
            yield CurrentBatch(id="current")
            yield LiveStats(id="stats")
            yield ActivityLog(id="log")
        yield Footer()

    def action_quit(self):
        self.exit()

    def action_pause(self):
        self.log_message("Evaluation paused...")

    def action_detail(self):
        self.log_message("Switching to detail view...")

    def log_message(self, message: str):
        log = self.query_one("#log", ActivityLog)
        log.write_line(message)

    # Update methods called from evaluation engine
    def update_overall(self, progress: float, phase: str, eta: int):
        overall = self.query_one("#overall", OverallProgress)
        overall.progress = progress
        overall.phase = phase
        overall.eta = eta

    def update_pair_progress(self, pair: str, completed: int, total: int, win_rate: float):
        pairs = self.query_one("#pairs", ModelPairProgress)
        pairs.update_pair(pair, completed, total, win_rate)
```

### 8.2 CLI Interface

```python
# src/cli.py

import click
import asyncio
from pathlib import Path
from datetime import datetime

from src.config.settings import EvalConfig, load_config
from src.config.presets import PRESETS, get_preset
from src.config.cost_estimator import estimate_run_cost
from src.api.openrouter_client import OpenRouterClient
from src.prompts.pipeline import PromptGenerationPipeline, PipelineConfig
from src.eval.engine import EvaluationEngine
from src.storage.database import ResultsDatabase
from src.storage.checkpoint import CheckpointManager
from src.tui.progress_dashboard import ProgressDashboard
from src.reports.pdf_generator import generate_report

@click.group()
def cli():
    """Gemini Writing Evaluation Framework"""
    pass

@cli.command()
@click.option('--preset', '-p', type=int, help='Preset level (1-10)')
@click.option('--prompts', '-n', type=int, help='Number of prompts')
@click.option('--models', '-m', multiple=True, help='Models to evaluate')
@click.option('--judges', '-j', multiple=True, help='Judge models')
@click.option('--votes', '-v', type=int, default=5, help='Votes per judge')
@click.option('--occupations', '-o', multiple=True, help='Filter by occupation codes')
@click.option('--industries', '-i', multiple=True, help='Filter by NAICS codes')
@click.option('--job-zones', '-z', multiple=True, type=int, help='Filter by job zones')
@click.option('--seed', type=int, help='Random seed for reproducibility')
@click.option('--dry-run', is_flag=True, help='Show estimate without running')
@click.option('--resume', type=Path, help='Resume from checkpoint directory')
@click.option('--output', '-O', type=Path, default='results', help='Output directory')
def run(preset, prompts, models, judges, votes, occupations, industries, job_zones, seed, dry_run, resume, output):
    """Run an evaluation"""

    # Build configuration
    if preset:
        config = get_preset(preset)
        click.echo(f"Using preset {preset}: {config.run_name}")
    else:
        config = EvalConfig(
            run_id=f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            run_name="Custom Evaluation"
        )

    # Override with CLI options
    if prompts:
        config.sampling.total_prompts = prompts
    if models:
        config.model_pairs = list(models)
    if judges:
        config.judge_config.models = list(judges)
    if votes:
        config.judge_config.votes_per_judge = votes
    if seed:
        config.sampling.random_seed = seed

    # Estimate costs
    estimate = estimate_run_cost(config)

    # Display estimate
    click.echo(render_estimate(estimate))

    if dry_run:
        return

    # Confirm
    if not click.confirm("Proceed?"):
        return

    # Run evaluation
    asyncio.run(run_evaluation(config, resume, output))

def render_estimate(estimate: dict) -> str:
    """Render cost/time estimate as ASCII box"""
    return f"""
+-------------------------------------------------------------+
|                    EVAL RUN ESTIMATE                        |
+-------------------------------------------------------------+
| Prompts:              {estimate['prompts']:,}                |
| Model pairs:          {estimate['model_pairs']}              |
| Total comparisons:    {estimate['total_comparisons']:,}      |
|                                                             |
| Judge config:         {estimate['judge_config']}             |
| Total judge calls:    {estimate['total_judge_calls']:,}      |
|                                                             |
| ESTIMATED COST                                              |
|   Response generation:  ${estimate['response_cost']:.0f} - ${estimate['response_cost']*1.2:.0f}  |
|   Judging:              ${estimate['judge_cost']:.0f} - ${estimate['judge_cost']*1.2:.0f}        |
|   Total:                ${estimate['total_cost']:.0f} - ${estimate['total_cost']*1.2:.0f}        |
|                                                             |
| ESTIMATED TIME                                              |
|   With rate limits:     {estimate['time_limited']}           |
|   Parallelized:         {estimate['time_parallel']}          |
+-------------------------------------------------------------+
"""

async def run_evaluation(config: EvalConfig, resume: Path | None, output: Path):
    """Main evaluation runner"""

    # Setup output directory
    if resume:
        run_dir = resume
    else:
        run_dir = output / config.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

    # Initialize components
    db = ResultsDatabase(run_dir / "results.db")
    await db.initialize()

    checkpoint = CheckpointManager(run_dir)
    if resume:
        checkpoint.load()
    else:
        checkpoint.initialize(config.run_id, config.sampling.total_prompts)

    async with OpenRouterClient(config.openrouter_api_key) as api:
        # Generate prompts
        pipeline = PromptGenerationPipeline(PipelineConfig(
            random_seed=config.sampling.random_seed,
            total_prompts=config.sampling.total_prompts,
            db_path="db/onet.db",
            api_client=api
        ))

        prompts = []
        async for prompt in pipeline.generate_prompts():
            prompts.append(prompt)
            await db.save_prompt(prompt)

        # Run evaluation with TUI
        engine = EvaluationEngine(config, api, checkpoint)

        # Start TUI in background
        tui = ProgressDashboard(config.model_pairs)

        async def update_tui():
            while True:
                tui.update_overall(
                    engine.progress.completed_prompts / engine.progress.total_prompts,
                    engine.progress.current_phase,
                    engine.progress.eta_seconds
                )
                await asyncio.sleep(0.5)

        asyncio.create_task(update_tui())

        # Run evaluation
        async for result in engine.run_evaluation(prompts):
            await db.save_comparison(result)
            tui.log_message(f"Completed: {result.prompt_id} - Winner: {result.final_winner}")

    # Generate report
    await generate_report(db, run_dir / "reports")

    click.echo(f"Evaluation complete. Results in {run_dir}")

@cli.command()
@click.argument('run_dirs', nargs=-1, type=Path)
def compare(run_dirs):
    """Compare results across multiple runs"""
    click.echo(f"Comparing {len(run_dirs)} runs...")
    # Implementation for cross-run comparison

@cli.command()
@click.argument('run_dir', type=Path)
def view(run_dir):
    """Interactive viewer for evaluation results"""
    from src.tui.results_viewer import ResultsViewer
    viewer = ResultsViewer(run_dir)
    viewer.run()

@cli.command()
def presets():
    """List available presets"""
    click.echo("\nAvailable Presets:\n")
    click.echo(f"{'Level':<6} {'Name':<20} {'Prompts':<10} {'Models':<10} {'Est. Cost':<12} {'Est. Time':<12}")
    click.echo("-" * 70)
    for level, preset in enumerate(PRESETS, 1):
        click.echo(f"{level:<6} {preset['name']:<20} {preset['prompts']:<10} {preset['model_pairs']:<10} ${preset['cost']:<11} {preset['time']:<12}")

if __name__ == "__main__":
    cli()
```

### 8.3 Preset Configurations

```python
# src/config/presets.py

PRESETS = [
    {
        "level": 1,
        "name": "Sanity Check",
        "prompts": 5,
        "model_pairs": 1,
        "judges": 1,
        "votes": 1,
        "cost": 1,
        "time": "2 min",
        "description": "Does the system work?"
    },
    {
        "level": 2,
        "name": "Smoke Test",
        "prompts": 20,
        "model_pairs": 1,
        "judges": 1,
        "votes": 3,
        "cost": 5,
        "time": "5 min",
        "description": "Quick functionality test"
    },
    {
        "level": 3,
        "name": "Dev Iteration",
        "prompts": 50,
        "model_pairs": 2,
        "judges": 2,
        "votes": 3,
        "cost": 25,
        "time": "15 min",
        "description": "Development/debugging"
    },
    {
        "level": 4,
        "name": "Quick Sample",
        "prompts": 100,
        "model_pairs": 2,
        "judges": 2,
        "votes": 5,
        "cost": 75,
        "time": "30 min",
        "description": "Fast directional signal"
    },
    {
        "level": 5,
        "name": "Light Eval",
        "prompts": 200,
        "model_pairs": 3,
        "judges": 3,
        "votes": 3,
        "cost": 150,
        "time": "1 hr",
        "description": "Light but meaningful eval"
    },
    {
        "level": 6,
        "name": "Standard Eval",
        "prompts": 500,
        "model_pairs": 4,
        "judges": 3,
        "votes": 5,
        "cost": 500,
        "time": "3 hrs",
        "description": "Standard evaluation run"
    },
    {
        "level": 7,
        "name": "Thorough Eval",
        "prompts": 1000,
        "model_pairs": 4,
        "judges": 3,
        "votes": 5,
        "cost": 1000,
        "time": "6 hrs",
        "description": "Thorough with good power"
    },
    {
        "level": 8,
        "name": "Comprehensive",
        "prompts": 2000,
        "model_pairs": 6,
        "judges": 3,
        "votes": 5,
        "cost": 2500,
        "time": "12 hrs",
        "description": "High statistical power"
    },
    {
        "level": 9,
        "name": "Deep Dive",
        "prompts": 5000,
        "model_pairs": 6,
        "judges": 3,
        "votes": 5,
        "cost": 6000,
        "time": "24 hrs",
        "description": "Publication-grade"
    },
    {
        "level": 10,
        "name": "Full Kaboodle",
        "prompts": 10000,
        "model_pairs": 6,
        "judges": 3,
        "votes": 5,
        "cost": 12000,
        "time": "48 hrs",
        "description": "Maximum coverage"
    }
]

def get_preset(level: int) -> "EvalConfig":
    """Get configuration for a preset level"""
    if level < 1 or level > 10:
        raise ValueError(f"Preset level must be 1-10, got {level}")

    preset = PRESETS[level - 1]

    from src.config.settings import (
        EvalConfig, ModelConfig, JudgeConfig, SamplingConfig
    )
    from datetime import datetime
    import random

    # Default model pairs based on level
    all_pro_pairs = [
        ("gemini-3-pro", "gpt-5.2-thinking"),
        ("gemini-3-pro", "claude-opus-4.5"),
        ("gemini-3-pro", "grok-4.1-thinking"),
        ("gemini-3-pro", "kimi-k2-thinking"),
    ]
    all_flash_pairs = [
        ("gemini-3-flash", "gpt-4.1"),
        ("gemini-3-flash", "claude-sonnet"),
    ]

    # Select pairs based on level
    if preset["model_pairs"] <= 2:
        pairs = all_pro_pairs[:preset["model_pairs"]]
    elif preset["model_pairs"] <= 4:
        pairs = all_pro_pairs[:preset["model_pairs"]]
    else:
        pairs = all_pro_pairs + all_flash_pairs[:preset["model_pairs"] - 4]

    # Judge models
    judge_models = ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"][:preset["judges"]]

    return EvalConfig(
        run_id=f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        run_name=preset["name"],
        preset_level=level,
        gemini_models=[],  # Derived from pairs
        competitor_models=[],  # Derived from pairs
        model_pairs=pairs,
        judge_config=JudgeConfig(
            models=judge_models,
            votes_per_judge=preset["votes"],
            use_both_personas=preset["judges"] >= 2
        ),
        sampling=SamplingConfig(
            random_seed=random.randint(1, 1000000),
            total_prompts=preset["prompts"],
            stratify_by_job_zone=True,
            stratify_by_soc_group=True
        ),
        openrouter_api_key="",  # Must be provided
        max_concurrent_requests=10,
        request_timeout_seconds=120,
        max_retries=3,
        output_dir="results"
    )
```

---

## Part 9: PDF Report Generation

### 9.1 Report Generator

```python
# src/reports/pdf_generator.py

from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import plotly.graph_objects as go
import plotly.express as px
from plotly.io import write_image

from src.storage.database import ResultsDatabase
from src.analysis.statistics import (
    calculate_win_rate_stats, calculate_cohens_kappa,
    identify_significant_weaknesses
)

class ReportGenerator:
    """Generate PDF evaluation report"""

    def __init__(self, db: ResultsDatabase, output_dir: Path):
        self.db = db
        self.output_dir = output_dir
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)

        # Setup Jinja2
        self.env = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "templates")
        )

    async def generate(self) -> Path:
        """Generate the full report"""

        # Gather all data
        data = await self._collect_data()

        # Generate charts
        charts = await self._generate_charts(data)

        # Render HTML
        template = self.env.get_template("report.html")
        html_content = template.render(
            data=data,
            charts=charts,
            generated_at=datetime.now().isoformat()
        )

        # Convert to PDF
        output_path = self.output_dir / "report.pdf"
        HTML(string=html_content).write_pdf(output_path)

        # Also save HTML
        html_path = self.output_dir / "report.html"
        with open(html_path, 'w') as f:
            f.write(html_content)

        return output_path

    async def _collect_data(self) -> dict:
        """Collect all data for the report"""

        # Overall win rates
        win_rates = await self.db.get_win_rates()

        # Win rates by dimension
        by_occupation = await self.db.get_win_rates_by_dimension("soc_major_group")
        by_category = await self.db.get_win_rates_by_dimension("writing_category")
        by_job_zone = await self.db.get_win_rates_by_dimension("job_zone")
        by_formality = await self.db.get_win_rates_by_dimension("formality_level")
        by_generation = await self.db.get_win_rates_by_dimension("writer_generation")

        # Calculate statistics
        stats = {}
        for pair, data in win_rates.items():
            stats[pair] = calculate_win_rate_stats(
                data["gemini_wins"],
                data["competitor_wins"],
                data["ties"]
            )

        # Identify weaknesses
        weaknesses = identify_significant_weaknesses(by_category)

        return {
            "overall_win_rates": win_rates,
            "statistics": stats,
            "by_occupation": by_occupation,
            "by_category": by_category,
            "by_job_zone": by_job_zone,
            "by_formality": by_formality,
            "by_generation": by_generation,
            "weaknesses": weaknesses
        }

    async def _generate_charts(self, data: dict) -> dict:
        """Generate all visualization charts"""
        charts = {}

        # Overall win rates bar chart
        fig = go.Figure()
        for pair, stats in data["statistics"].items():
            fig.add_trace(go.Bar(
                name=pair,
                x=[pair],
                y=[stats.win_rate * 100],
                error_y=dict(
                    type='data',
                    array=[(stats.confidence_interval_95[1] - stats.win_rate) * 100],
                    arrayminus=[(stats.win_rate - stats.confidence_interval_95[0]) * 100]
                )
            ))
        fig.update_layout(
            title="Gemini Win Rates by Model Pair",
            yaxis_title="Win Rate (%)",
            showlegend=False
        )
        fig.add_hline(y=50, line_dash="dash", line_color="gray")
        charts["overall"] = self._save_chart(fig, "overall_win_rates")

        # Heatmap by occupation
        occ_data = data["by_occupation"]
        pairs = list(data["statistics"].keys())
        occupations = list(occ_data.keys())

        z_values = []
        for occ in occupations:
            row = []
            for pair in pairs:
                if pair in occ_data.get(occ, {}):
                    row.append(occ_data[occ][pair]["win_rate"] * 100)
                else:
                    row.append(None)
            z_values.append(row)

        fig = go.Figure(data=go.Heatmap(
            z=z_values,
            x=pairs,
            y=occupations,
            colorscale='RdYlGn',
            zmid=50
        ))
        fig.update_layout(
            title="Win Rate Heatmap by Occupation Group",
            xaxis_title="Model Pair",
            yaxis_title="Occupation Group"
        )
        charts["occupation_heatmap"] = self._save_chart(fig, "occupation_heatmap")

        # Win rates by writing category
        categories = list(data["by_category"].keys())
        first_pair = pairs[0] if pairs else None

        if first_pair:
            cat_rates = [
                data["by_category"].get(cat, {}).get(first_pair, {}).get("win_rate", 0.5) * 100
                for cat in categories
            ]

            fig = go.Figure(data=go.Bar(
                x=categories,
                y=cat_rates,
                marker_color=['green' if r > 50 else 'red' for r in cat_rates]
            ))
            fig.update_layout(
                title=f"Win Rates by Writing Category ({first_pair})",
                yaxis_title="Win Rate (%)",
                xaxis_tickangle=-45
            )
            fig.add_hline(y=50, line_dash="dash", line_color="gray")
            charts["category_bars"] = self._save_chart(fig, "category_win_rates")

        # Job zone trend
        job_zones = sorted(data["by_job_zone"].keys())
        if first_pair:
            jz_rates = [
                data["by_job_zone"].get(jz, {}).get(first_pair, {}).get("win_rate", 0.5) * 100
                for jz in job_zones
            ]

            fig = go.Figure(data=go.Scatter(
                x=job_zones,
                y=jz_rates,
                mode='lines+markers'
            ))
            fig.update_layout(
                title="Win Rate by Job Zone (Skill Level)",
                xaxis_title="Job Zone (1=Low, 5=High)",
                yaxis_title="Win Rate (%)"
            )
            fig.add_hline(y=50, line_dash="dash", line_color="gray")
            charts["job_zone_trend"] = self._save_chart(fig, "job_zone_trend")

        return charts

    def _save_chart(self, fig: go.Figure, name: str) -> str:
        """Save chart and return path"""
        path = self.charts_dir / f"{name}.png"
        write_image(fig, str(path), width=800, height=500)
        return str(path)

async def generate_report(db: ResultsDatabase, output_dir: Path) -> Path:
    """Convenience function to generate report"""
    generator = ReportGenerator(db, output_dir)
    return await generator.generate()
```

### 9.2 Report Template

```html
<!-- src/reports/templates/report.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Gemini Writing Evaluation Report</title>
    <style>
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px;
            color: #333;
        }
        h1 { color: #1a73e8; border-bottom: 3px solid #1a73e8; padding-bottom: 10px; }
        h2 { color: #202124; margin-top: 40px; }
        h3 { color: #5f6368; }
        .executive-summary {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .metric-card {
            display: inline-block;
            background: white;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 20px;
            margin: 10px;
            min-width: 200px;
            text-align: center;
        }
        .metric-value { font-size: 32px; font-weight: bold; color: #1a73e8; }
        .metric-label { color: #5f6368; margin-top: 5px; }
        .win { color: #34a853; }
        .loss { color: #ea4335; }
        .tie { color: #fbbc04; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dadce0;
        }
        th { background: #f8f9fa; font-weight: 600; }
        .chart { margin: 30px 0; text-align: center; }
        .chart img { max-width: 100%; }
        .weakness-item {
            background: #fce8e6;
            border-left: 4px solid #ea4335;
            padding: 15px;
            margin: 10px 0;
        }
        .footer { margin-top: 50px; text-align: center; color: #5f6368; font-size: 12px; }
    </style>
</head>
<body>
    <h1>Gemini Writing Evaluation Report</h1>
    <p>Generated: {{ generated_at }}</p>

    <div class="executive-summary">
        <h2>Executive Summary</h2>

        <div class="metric-card">
            <div class="metric-value">{{ data.statistics|length }}</div>
            <div class="metric-label">Model Pairs Evaluated</div>
        </div>

        <div class="metric-card">
            <div class="metric-value">{{ data.overall_win_rates.values()|sum(attribute='total') }}</div>
            <div class="metric-label">Total Comparisons</div>
        </div>

        {% for pair, stats in data.statistics.items() %}
        <div class="metric-card">
            <div class="metric-value {% if stats.win_rate > 0.5 %}win{% elif stats.win_rate < 0.5 %}loss{% else %}tie{% endif %}">
                {{ "%.1f"|format(stats.win_rate * 100) }}%
            </div>
            <div class="metric-label">{{ pair }}</div>
        </div>
        {% endfor %}
    </div>

    <h2>Key Findings</h2>
    <ul>
        {% for pair, stats in data.statistics.items() %}
        <li>
            <strong>{{ pair }}</strong>:
            {% if stats.is_significant %}
                Gemini {{ "wins" if stats.win_rate > 0.5 else "loses" }} with
                <strong>{{ "%.1f"|format(stats.win_rate * 100) }}%</strong> win rate
                (p={{ "%.4f"|format(stats.p_value) }}, statistically significant)
            {% else %}
                No statistically significant difference detected
                ({{ "%.1f"|format(stats.win_rate * 100) }}%, p={{ "%.4f"|format(stats.p_value) }})
            {% endif %}
        </li>
        {% endfor %}
    </ul>

    <h2>Overall Win Rates</h2>
    <div class="chart">
        <img src="{{ charts.overall }}" alt="Overall Win Rates">
    </div>

    <table>
        <thead>
            <tr>
                <th>Model Pair</th>
                <th>Win Rate</th>
                <th>95% CI</th>
                <th>Wins</th>
                <th>Losses</th>
                <th>Ties</th>
                <th>p-value</th>
                <th>Significant</th>
            </tr>
        </thead>
        <tbody>
            {% for pair, stats in data.statistics.items() %}
            <tr>
                <td>{{ pair }}</td>
                <td class="{% if stats.win_rate > 0.5 %}win{% elif stats.win_rate < 0.5 %}loss{% endif %}">
                    {{ "%.1f"|format(stats.win_rate * 100) }}%
                </td>
                <td>[{{ "%.1f"|format(stats.confidence_interval_95[0] * 100) }}%, {{ "%.1f"|format(stats.confidence_interval_95[1] * 100) }}%]</td>
                <td>{{ stats.n_wins }}</td>
                <td>{{ stats.n_losses }}</td>
                <td>{{ stats.n_ties }}</td>
                <td>{{ "%.4f"|format(stats.p_value) }}</td>
                <td>{{ "Yes" if stats.is_significant else "No" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <h2>Win Rates by Occupation Group</h2>
    <div class="chart">
        <img src="{{ charts.occupation_heatmap }}" alt="Occupation Heatmap">
    </div>

    <h2>Win Rates by Writing Category</h2>
    <div class="chart">
        <img src="{{ charts.category_bars }}" alt="Category Win Rates">
    </div>

    <h2>Win Rate by Job Zone (Skill Level)</h2>
    <div class="chart">
        <img src="{{ charts.job_zone_trend }}" alt="Job Zone Trend">
    </div>

    <h2>Identified Weaknesses</h2>
    {% if data.weaknesses %}
        <p>The following areas show statistically significant underperformance by Gemini:</p>
        {% for weakness in data.weaknesses[:10] %}
        <div class="weakness-item">
            <strong>{{ weakness.dimension_value }}</strong> ({{ weakness.model_pair }})<br>
            Win Rate: {{ "%.1f"|format(weakness.win_rate * 100) }}% (n={{ weakness.sample_size }})<br>
            Effect Size: {{ "%.3f"|format(weakness.effect_size) }} ({{ weakness.effect_interpretation }})<br>
            p-value: {{ "%.4f"|format(weakness.p_value) }}
        </div>
        {% endfor %}
    {% else %}
        <p>No statistically significant weaknesses identified.</p>
    {% endif %}

    <h2>Methodology</h2>
    <ul>
        <li><strong>Prompt Source</strong>: O*NET 30.1 database writing tasks</li>
        <li><strong>Comparison Method</strong>: Pairwise, side-by-side evaluation</li>
        <li><strong>Judging</strong>: Ensemble of 3 judge models, best-of-5 votes each</li>
        <li><strong>Aggregation</strong>: Majority-of-majorities voting</li>
        <li><strong>Position Bias Control</strong>: Deterministic shuffling of response order</li>
        <li><strong>Statistical Tests</strong>: Binomial test against 50% baseline</li>
        <li><strong>Confidence Intervals</strong>: Wilson score interval</li>
    </ul>

    <div class="footer">
        <p>Gemini Writing Evaluation Framework</p>
        <p>Report generated automatically. Results are based on AI judge evaluations.</p>
    </div>
</body>
</html>
```

---

## Part 10: Implementation Roadmap

### 10.1 Phase 1: Foundation (Week 1-2)

1. **Project Setup**
   - Initialize Python project with pyproject.toml
   - Set up directory structure
   - Configure dependencies (pydantic, httpx, textual, etc.)
   - Set up development environment with pre-commit hooks

2. **Data Layer**
   - Implement O*NET extractor with async SQLite access
   - Build NAICS mapper with SOC crosswalk
   - Create company database with Fortune 500 and smaller companies
   - Implement name generator with demographic diversity

3. **Core Schemas**
   - Define all Pydantic models (prompts, responses, judgments)
   - Create database schema for results storage
   - Implement checkpoint state serialization

### 10.2 Phase 2: Prompt Generation (Week 2-3)

1. **Phase 1 Pipeline**
   - Task extraction from O*NET with filtering
   - Writing category classification
   - Stratified sampling implementation

2. **Phase 2 Pipeline**
   - Algorithmic combination of tasks with personas
   - Company and industry assignment
   - Formality/urgency determination
   - Prompt text generation

3. **Phase 3 Pipeline**
   - LLM enrichment for context-rich prompts
   - Attachment/reference generation
   - Prior message thread generation
   - Competing objectives injection

### 10.3 Phase 3: API & Evaluation (Week 3-4)

1. **OpenRouter Integration**
   - Async HTTP client with connection pooling
   - Rate limiter with adaptive backoff
   - Circuit breaker for fault tolerance
   - Cost tracking and estimation

2. **Evaluation Engine**
   - Response generation with parallel execution
   - Judge prompt construction
   - Vote aggregation (majority-of-majorities)
   - Auto-loss handling

3. **Robustness**
   - Checkpoint/resume system
   - Error recovery and logging
   - Graceful shutdown handling

### 10.4 Phase 4: TUI & Reporting (Week 4-5)

1. **Progress Dashboard**
   - Textual app structure
   - Real-time progress updates
   - Interactive controls (pause, quit, detail view)
   - Activity log

2. **Results Viewer**
   - Filtering and sorting
   - Side-by-side response comparison
   - Drill-down into judgments

3. **PDF Report**
   - Chart generation with Plotly
   - HTML template with Jinja2
   - PDF rendering with WeasyPrint
   - Executive summary generation

### 10.5 Phase 5: Analysis & Refinement (Week 5-6)

1. **Statistical Analysis**
   - Win rate calculations with confidence intervals
   - Inter-judge agreement (Cohen's Kappa)
   - Bias detection algorithms
   - Weakness identification

2. **Testing**
   - Unit tests for all components
   - Integration tests for pipelines
   - End-to-end evaluation tests

3. **Documentation**
   - API documentation
   - User guide
   - Developer setup guide

---

## Part 11: Key Design Decisions

### 11.1 Prompt Generation Philosophy

1. **O*NET-Driven Diversity**: Let the 18,796 task statements drive diversity rather than hardcoding writing categories. The inferred categories help with analysis but don't constrain generation.

2. **Real Companies**: Using real company names grounds prompts in reality and makes evaluation more authentic. Track companies used to analyze potential bias.

3. **Realistic Names**: Demographic diversity in names (age, ethnicity, gender) reflects real workplace communication.

4. **Context Richness Spectrum**: Not all prompts need enrichment. Simple tasks get algorithmic generation; complex tasks get LLM enrichment.

### 11.2 Evaluation Robustness

1. **Ensemble Judging**: Three judge models prevent any single model's bias from dominating.

2. **Majority-of-Majorities**: Best-of-5 votes per judge, then majority across judges, maximizes reliability.

3. **Deterministic Shuffling**: Position bias is controlled through reproducible response ordering.

4. **Dual Personas**: Writing expert and recipient perspectives capture different quality dimensions.

### 11.3 Operational Reliability

1. **Checkpoint Everything**: Every comparison is saved immediately. Resume from any point.

2. **Circuit Breaker**: Prevent cascade failures when API issues occur.

3. **Adaptive Rate Limiting**: Respond to rate limit signals automatically.

4. **Graceful Degradation**: Continue evaluation even with partial failures.

### 11.4 Cost Awareness

1. **Live Estimates**: Always show cost before running.

2. **Presets**: 10 levels from $1 to $12,000+ for different needs.

3. **Fine-Grained Control**: Every cost parameter is configurable.

4. **Progress Tracking**: Real-time cost tracking during execution.

---

## Conclusion

This implementation plan provides a comprehensive blueprint for the Gemini Writing Evaluation Framework. The design prioritizes:

- **Realism**: O*NET tasks, real companies, realistic names
- **Diversity**: Systematic coverage across occupations, industries, formality levels
- **Robustness**: Ensemble judging, checkpoint/resume, circuit breakers
- **Usability**: Rich TUI, 10 presets, live cost estimates
- **Trustworthiness**: Statistical rigor, bias detection, transparent methodology

The modular architecture allows for incremental development and testing, with each component independently testable and replaceable. The three-phase prompt generation pipeline balances efficiency (algorithmic) with quality (LLM enrichment), while the evaluation engine ensures reliable, resumable execution at scale.

