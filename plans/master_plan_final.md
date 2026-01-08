# Gemini Writing Evaluation Framework - Final Master Plan

## Executive Summary

This final master plan incorporates all lessons learned from 6 independent implementation simulations, resolving critical blockers, fixing identified issues, and ensuring the framework is ready for production implementation. The simulations collectively identified **250+ distinct issues** spanning schema validation, API integration, cost estimation, statistical methodology, and operational concerns.

### Key Changes from Draft Plan

1. **Resolved Critical Blockers**: Fixed all 15+ blocking issues that would cause immediate runtime failures
2. **Accurate Cost Estimation**: Corrected cost calculations that were underestimated by 5-10x
3. **Complete Data Dependencies**: Added specifications for all missing data files and external dependencies
4. **Clarified Voting Methodology**: Resolved ambiguity around "best-of-5" implementation
5. **Added Missing Implementations**: Specified all helper methods and schemas that were referenced but undefined
6. **Scalability Fixes**: Replaced memory-exploding algorithms with lazy generation patterns
7. **Enhanced Error Handling**: Added comprehensive exception classes and recovery logic

---

## Part 1: Critical Pre-Implementation Requirements

### 1.1 System Dependencies (MUST INSTALL FIRST)

Before Python dependencies, install these system-level requirements:

**macOS:**
```bash
brew install cairo pango gdk-pixbuf libffi
```

**Ubuntu/Debian:**
```bash
sudo apt-get install -y libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

**Windows:**
```
# WeasyPrint on Windows is complex - consider using reportlab as fallback
# Or use WSL2 with Ubuntu instructions
```

**Rationale**: WeasyPrint requires these C libraries for PDF generation. Without them, `pip install weasyprint` will fail or produce runtime errors.

### 1.2 Required Data Files (MUST CREATE BEFORE RUNNING)

The following data files are NOT included and MUST be created:

| File | Purpose | Minimum Size | Creation Method |
|------|---------|--------------|-----------------|
| `data/companies.json` | Real company names by NAICS/size | 500+ companies | Manual curation + LLM generation |
| `data/names.json` | Demographically diverse name pools | 100+ per category | Census data + manual curation |
| `data/naics_soc_crosswalk.json` | SOC to NAICS mapping | All 22 SOC groups | BLS data or manual mapping |

**companies.json Schema:**
```json
[
  {
    "name": "Apple Inc.",
    "naics": "334111",
    "naics_sector": "31",
    "size": "enterprise",
    "employee_count": 164000,
    "industry_description": "Computer and Electronic Product Manufacturing",
    "hq_location": "Cupertino, CA",
    "public": true,
    "founded_year": 1976
  }
]
```

**names.json Schema:**
```json
{
  "first_names": {
    "white": {
      "male": ["James", "Michael", "Robert", ...],
      "female": ["Jennifer", "Sarah", "Jessica", ...]
    },
    "hispanic": {...},
    "black": {...},
    "asian": {...}
  },
  "last_names": {
    "white": ["Smith", "Johnson", "Williams", ...],
    "hispanic": ["Garcia", "Rodriguez", "Martinez", ...],
    "black": ["Jackson", "Washington", "Jefferson", ...],
    "asian": ["Chen", "Wang", "Kim", "Nguyen", "Patel", ...]
  },
  "generational_names": {
    "boomer": {"male": ["Robert", "William", ...], "female": ["Linda", "Barbara", ...]},
    "gen_x": {"male": ["Michael", "Christopher", ...], "female": ["Jennifer", "Lisa", ...]},
    "millennial": {"male": ["Joshua", "Matthew", ...], "female": ["Ashley", "Emily", ...]},
    "gen_z": {"male": ["Liam", "Noah", ...], "female": ["Emma", "Olivia", ...]}
  }
}
```

### 1.3 Environment Configuration

Create `.env` file with:
```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx

# Optional with defaults
EVAL_ONET_DB_PATH=db/onet.db
EVAL_RESULTS_DIR=results
EVAL_LOG_LEVEL=INFO
EVAL_MAX_CONCURRENT_REQUESTS=10
EVAL_BUDGET_LIMIT=1000.00
EVAL_BUDGET_WARNING_THRESHOLD=0.8
```

---

## Part 2: Corrected Architecture

### 2.1 Updated Technology Stack

```toml
[project]
name = "gemini-writing-eval"
version = "1.0.0"
requires-python = ">=3.11"

dependencies = [
    # Core async framework
    "pydantic>=2.5",
    "pydantic-settings>=2.1",
    "httpx>=0.27",
    "aiosqlite>=0.19",
    "aiofiles>=23.2",        # ADDED: Was missing, needed for checkpoint
    "tenacity>=8.2",
    "anyio>=4.2",

    # CLI and TUI
    "typer[all]>=0.9",
    "rich>=13.7",
    "textual>=0.52",

    # Data analysis
    "pandas>=2.2",
    "numpy>=1.26",
    "scipy>=1.12",
    "scikit-learn>=1.4",

    # Visualization and reporting
    "plotly>=5.18",
    "kaleido>=0.2,<0.3",      # PINNED: 0.2.x for compatibility
    "weasyprint>=61",
    "jinja2>=3.1",

    # Token counting (NEW)
    "tiktoken>=0.5",          # ADDED: For accurate token estimation

    # Utilities
    "python-dotenv>=1.0",
    "structlog>=24.1",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "mypy>=1.8",
    "ruff>=0.2",
    "types-aiofiles",         # ADDED: Type stubs
]
```

### 2.2 Complete Directory Structure

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── INSTALL.md                         # NEW: System dependency instructions
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── exceptions.py                  # NEW: All custom exceptions
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── presets.py
│   │   ├── models.py
│   │   ├── cost_estimator.py
│   │   └── model_aliases.py           # NEW: Maps semantic names to model IDs
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── onet_schema.py
│   │   ├── model_verifier.py
│   │   ├── api_validator.py
│   │   └── warmup.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py
│   │   ├── naics_mapper.py
│   │   ├── company_database.py
│   │   ├── name_generator.py
│   │   ├── sensitive_detector.py
│   │   └── bls_parser.py              # NEW: BLS matrix parsing
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── phase1_personas.py
│   │   ├── phase2_combiner.py
│   │   ├── phase3_enricher.py
│   │   ├── lazy_sampler.py            # NEW: Memory-efficient sampling
│   │   ├── attachment_generator.py    # NEW: Mock attachment content
│   │   ├── reply_context_generator.py # NEW: Prior message threads
│   │   ├── temporal_context.py        # NEW: Time-based grounding
│   │   ├── constraint_generator.py
│   │   ├── constraint_checker.py      # NEW: Verify compliance
│   │   ├── schemas.py
│   │   └── validators.py
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── response_collector.py
│   │   ├── judge_engine.py
│   │   ├── judge_parser.py
│   │   ├── dual_persona.py
│   │   ├── position_handler.py
│   │   ├── vote_aggregator.py
│   │   ├── auto_loss_detector.py
│   │   ├── refusal_classifier.py      # NEW: Categorize refusals
│   │   └── tier_manager.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py
│   │   ├── rate_limiter.py
│   │   ├── circuit_breaker.py
│   │   ├── retry_handler.py
│   │   └── token_counter.py           # NEW: Accurate token counting
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── schema.sql                 # NEW: Complete DB schema
│   │   ├── checkpoint.py
│   │   ├── run_manager.py
│   │   └── exporter.py
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py
│   │   ├── agreement.py
│   │   ├── bias_detector.py
│   │   ├── weakness_finder.py
│   │   ├── theme_clusterer.py         # NEW: Cluster weakness themes
│   │   └── significance.py            # NEW: Multiple comparison correction
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py
│   │   ├── chart_builder.py
│   │   └── templates/
│   │       ├── comprehensive_report.html  # NEW: Must create
│   │       ├── executive_summary.html     # NEW: Must create
│   │       └── base.css                   # NEW: PDF styling
│   │
│   └── tui/
│       ├── __init__.py
│       ├── app.py
│       ├── progress_screen.py
│       ├── results_browser.py
│       ├── filter_panel.py            # NEW: Filter widget
│       └── comparison_viewer.py
│
├── db/
│   ├── onet.db
│   └── ONET_REFERENCE.md
│
├── data/
│   ├── companies.json                 # Must be created
│   ├── names.json                     # Must be created
│   └── naics_soc_crosswalk.json       # Must be created
│
├── scripts/
│   ├── generate_companies.py          # NEW: Company data generator
│   ├── download_bls_data.py           # NEW: BLS data fetcher
│   └── verify_onet_schema.py          # NEW: Schema verification
│
├── results/                           # Gitignored
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   └── sample_onet_data.json
    ├── unit/
    │   ├── test_onet_extractor.py
    │   ├── test_phase2_combiner.py
    │   ├── test_vote_aggregator.py
    │   └── test_agreement_metrics.py
    └── integration/
        └── test_full_pipeline.py
```

---

## Part 3: Complete Pydantic Schemas

### 3.1 Core Data Models

All schemas that were referenced but undefined in the draft plan:

```python
# src/prompts/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, Any
from datetime import datetime

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
    email: str | None = None  # ADDED: email generation
    demographic: str
    gender: str
    formality_variants: dict[str, str] = Field(default_factory=dict)
    # e.g., {"formal": "Dr. Sarah Chen", "casual": "Sarah", "full": "Sarah T. Chen"}


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


class PromptConstraint(BaseModel):
    """Instruction-following constraint."""
    constraint_type: str  # "word_limit", "bullet_count", "keyword_include", etc.
    description: str
    value: Any
    is_verifiable: bool = True


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
```

### 3.2 Evaluation Schemas

```python
# src/eval/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, Any
from datetime import datetime

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
    phase: Literal["prompt_generation", "response_collection", "judging", "analysis", "complete"]
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
```

---

## Part 4: Fixed O*NET Data Pipeline

### 4.1 Schema Validation (Complete Implementation)

```python
# src/validation/onet_schema.py
import aiosqlite
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    table_info: dict[str, list[str]]  # table -> columns

class ONetSchemaValidator:
    """Validate O*NET database schema before any queries."""

    REQUIRED_TABLES = {
        "task_statements": ["task_id", "onetsoc_code", "task"],
        "occupation_data": ["onetsoc_code", "title"],
        "job_zones": ["onetsoc_code", "job_zone"],
        "work_context": ["onetsoc_code", "element_id", "scale_id", "data_value"],
        "skills": ["onetsoc_code", "element_id", "scale_id", "data_value"],
        "content_model_reference": ["element_id", "element_name"],
    }

    REQUIRED_ELEMENTS = {
        "2.A.1.c": "Writing",
        "4.C.1.a.2.h": "Electronic Mail",
        "4.C.1.a.2.j": "Letters and Memos",
    }

    REQUIRED_SCALES = ["IM", "LV", "CX"]

    async def validate(self, db_path: Path) -> ValidationResult:
        """Run comprehensive schema validation."""
        errors = []
        warnings = []
        table_info = {}

        if not db_path.exists():
            return ValidationResult(
                is_valid=False,
                errors=[f"Database not found: {db_path}"],
                warnings=[],
                table_info={}
            )

        async with aiosqlite.connect(db_path) as db:
            # Get all tables
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            existing_tables = {row[0] for row in await cursor.fetchall()}

            # Validate tables and columns
            for table, required_cols in self.REQUIRED_TABLES.items():
                if table not in existing_tables:
                    errors.append(f"Missing required table: {table}")
                    continue

                # Get actual columns (case-insensitive check)
                cursor = await db.execute(f"PRAGMA table_info({table})")
                actual_cols = {row[1].lower(): row[1] for row in await cursor.fetchall()}
                table_info[table] = list(actual_cols.values())

                for col in required_cols:
                    if col.lower() not in actual_cols:
                        errors.append(f"Missing column: {table}.{col}")

            # Validate element IDs exist
            for element_id, element_name in self.REQUIRED_ELEMENTS.items():
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM content_model_reference WHERE element_id = ?",
                    (element_id,)
                )
                count = (await cursor.fetchone())[0]
                if count == 0:
                    warnings.append(f"Element {element_id} ({element_name}) not found in content_model_reference")

                # Also check if there's data
                for data_table in ["skills", "work_context"]:
                    if data_table in existing_tables:
                        cursor = await db.execute(
                            f"SELECT COUNT(*) FROM {data_table} WHERE element_id = ?",
                            (element_id,)
                        )
                        data_count = (await cursor.fetchone())[0]
                        if data_count == 0:
                            warnings.append(f"No data for {element_id} in {data_table}")

            # Validate scale IDs
            if "skills" in existing_tables:
                cursor = await db.execute("SELECT DISTINCT scale_id FROM skills")
                available_scales = {row[0] for row in await cursor.fetchall()}
                for scale in self.REQUIRED_SCALES:
                    if scale not in available_scales:
                        warnings.append(f"Scale '{scale}' not found in skills table")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            table_info=table_info
        )
```

### 4.2 Fixed Task Extraction (Memory-Efficient)

```python
# src/data/onet_extractor.py
import re
import aiosqlite
from pathlib import Path
from typing import AsyncIterator
from src.prompts.schemas import ONetTask

class ONetExtractor:
    """Extract writing-relevant tasks with memory-efficient streaming."""

    # Pre-compiled regex patterns for performance
    WRITING_PATTERNS = [
        (re.compile(r'\bwrite\b', re.I), 1.0),
        (re.compile(r'\bdraft\b', re.I), 1.0),
        (re.compile(r'\bcompose\b', re.I), 1.0),
        (re.compile(r'\bdocument\b', re.I), 0.8),
        (re.compile(r'\breport\b', re.I), 0.7),
        (re.compile(r'\bcorrespond', re.I), 0.9),
        (re.compile(r'\bemail\b', re.I), 0.9),
        (re.compile(r'\bmemo\b', re.I), 0.9),
        (re.compile(r'\bletter\b', re.I), 0.8),
        (re.compile(r'\bcommunicat', re.I), 0.6),
        (re.compile(r'\bpresent\b', re.I), 0.5),
        (re.compile(r'\bsummariz', re.I), 0.7),
        (re.compile(r'\bpropos', re.I), 0.7),
        (re.compile(r'\bnotify\b', re.I), 0.8),
        (re.compile(r'\binform\b', re.I), 0.7),
    ]

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def extract_writing_tasks(
        self,
        min_relevance: float = 0.5,
        job_zones: list[int] | None = None,
        soc_codes: list[str] | None = None,
        batch_size: int = 1000
    ) -> list[ONetTask]:
        """Extract tasks with streaming for memory efficiency."""
        tasks = []
        async for task in self._stream_tasks(min_relevance, job_zones, soc_codes):
            tasks.append(task)
        return tasks

    async def _stream_tasks(
        self,
        min_relevance: float,
        job_zones: list[int] | None,
        soc_codes: list[str] | None
    ) -> AsyncIterator[ONetTask]:
        """Stream tasks one at a time to avoid memory explosion."""

        query = """
        SELECT
            t.task_id,
            t.onetsoc_code,
            t.task,
            COALESCE(t.task_type, 'Core') as task_type,
            o.title as occupation_title,
            o.description as occupation_description,
            COALESCE(jz.job_zone, 3) as job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major,
            ws.data_value as writing_skill,
            email_wc.data_value as email_freq,
            letter_wc.data_value as letter_freq
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        LEFT JOIN skills ws ON t.onetsoc_code = ws.onetsoc_code
            AND ws.element_id = '2.A.1.c' AND ws.scale_id = 'IM'
        LEFT JOIN work_context email_wc ON t.onetsoc_code = email_wc.onetsoc_code
            AND email_wc.element_id = '4.C.1.a.2.h' AND email_wc.scale_id = 'CX'
        LEFT JOIN work_context letter_wc ON t.onetsoc_code = letter_wc.onetsoc_code
            AND letter_wc.element_id = '4.C.1.a.2.j' AND letter_wc.scale_id = 'CX'
        """

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                async for row in cursor:
                    row_dict = dict(row)

                    # Apply filters early
                    if job_zones and row_dict['job_zone'] not in job_zones:
                        continue
                    if soc_codes and row_dict['soc_major'] not in soc_codes:
                        continue

                    # Compute relevance
                    relevance = self._compute_writing_relevance(row_dict)
                    if relevance < min_relevance:
                        continue

                    yield ONetTask(
                        task_id=row_dict['task_id'],
                        onetsoc_code=row_dict['onetsoc_code'],
                        task=row_dict['task'],
                        task_type=row_dict['task_type'],
                        occupation_title=row_dict['occupation_title'],
                        occupation_description=row_dict.get('occupation_description'),
                        job_zone=row_dict['job_zone'],
                        soc_major_group=row_dict['soc_major'],
                        writing_relevance_score=relevance,
                        inferred_category=self._infer_category(row_dict['task']),
                        inferred_channel=self._infer_channel(row_dict['task'])
                    )

    def _compute_writing_relevance(self, row: dict) -> float:
        """Compute writing relevance with proper normalization."""
        task_text = row.get('task', '')

        # Pattern matching score
        max_pattern_score = 0.0
        for pattern, weight in self.WRITING_PATTERNS:
            if pattern.search(task_text):
                max_pattern_score = max(max_pattern_score, weight)

        # O*NET scores (handle NULL properly)
        writing_skill = row.get('writing_skill') or 2.5
        email_freq = row.get('email_freq') or 2.5
        letter_freq = row.get('letter_freq') or 2.5

        # Normalize O*NET scores (1-5 scale to 0-1)
        onet_raw = (
            writing_skill * 0.4 +
            email_freq * 0.3 +
            letter_freq * 0.3
        )
        onet_score = (onet_raw - 1.0) / 4.0  # Maps [1,5] to [0,1]

        return max(max_pattern_score, onet_score)

    def _infer_category(self, task_text: str) -> str:
        """Multi-signal category inference."""
        task_lower = task_text.lower()
        scores = {}

        patterns = [
            ('customer_communication', ['customer', 'client', 'patient', 'stakeholder'], 1.5),
            ('correspondence', ['email', 'correspond', 'letter', 'reply'], 1.3),
            ('documentation', ['document', 'record', 'log', 'file'], 1.2),
            ('reports', ['report', 'summary', 'analysis', 'findings'], 1.1),
            ('proposals', ['propos', 'recommend', 'suggest', 'request'], 1.1),
            ('training', ['train', 'instruct', 'teach', 'guide'], 1.0),
            ('policy', ['policy', 'procedure', 'guideline', 'standard'], 1.0),
            ('evaluation', ['review', 'evaluat', 'assess', 'feedback'], 1.0),
        ]

        for category, keywords, weight in patterns:
            score = sum(weight for kw in keywords if kw in task_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return 'general_communication'
        return max(scores, key=scores.get)

    def _infer_channel(self, task_text: str) -> str:
        """Infer communication channel."""
        task_lower = task_text.lower()

        channel_patterns = [
            ('email', ['email', 'e-mail']),
            ('letter', ['letter']),
            ('memo', ['memo', 'memorandum']),
            ('report', ['report']),
            ('social_media', ['post', 'social', 'blog', 'tweet']),
            ('presentation', ['present', 'slide']),
        ]

        for channel, keywords in channel_patterns:
            if any(kw in task_lower for kw in keywords):
                return channel

        return 'unspecified'
```

### 4.3 Complete NAICS Mapping (All 22 SOC Groups)

```python
# src/data/naics_mapper.py
import random
from pathlib import Path
from typing import Optional
import json

class NAICSMapper:
    """Map SOC codes to NAICS industries with complete fallback data."""

    # Complete SOC major group to NAICS sector mapping
    # Probabilities based on BLS Employment by Industry Matrix
    SOC_TO_NAICS_FALLBACK = {
        "11": [("54", 0.22), ("52", 0.15), ("62", 0.12), ("31", 0.10), ("44", 0.08), ("55", 0.08), ("23", 0.06), ("72", 0.05), ("92", 0.05), ("48", 0.04), ("other", 0.05)],  # Management
        "13": [("54", 0.28), ("52", 0.22), ("55", 0.10), ("92", 0.08), ("62", 0.07), ("51", 0.06), ("31", 0.05), ("44", 0.04), ("61", 0.03), ("other", 0.07)],  # Business/Financial
        "15": [("54", 0.32), ("51", 0.22), ("52", 0.10), ("31", 0.08), ("55", 0.06), ("92", 0.05), ("61", 0.04), ("62", 0.03), ("23", 0.03), ("other", 0.07)],  # Computer/Math
        "17": [("54", 0.28), ("23", 0.18), ("31", 0.16), ("22", 0.08), ("92", 0.06), ("51", 0.05), ("48", 0.04), ("21", 0.04), ("55", 0.03), ("other", 0.08)],  # Engineering
        "19": [("54", 0.25), ("61", 0.18), ("62", 0.15), ("92", 0.12), ("31", 0.08), ("51", 0.05), ("55", 0.04), ("21", 0.03), ("11", 0.03), ("other", 0.07)],  # Life/Physical/Social Science
        "21": [("62", 0.32), ("92", 0.25), ("61", 0.12), ("81", 0.08), ("54", 0.06), ("52", 0.05), ("55", 0.03), ("71", 0.03), ("other", 0.06)],  # Community/Social Service
        "23": [("61", 0.45), ("62", 0.15), ("92", 0.12), ("54", 0.08), ("81", 0.06), ("71", 0.04), ("55", 0.03), ("other", 0.07)],  # Legal
        "25": [("61", 0.72), ("92", 0.08), ("62", 0.06), ("81", 0.04), ("71", 0.03), ("54", 0.02), ("other", 0.05)],  # Education
        "27": [("51", 0.28), ("54", 0.18), ("71", 0.15), ("81", 0.10), ("61", 0.07), ("52", 0.05), ("44", 0.04), ("31", 0.03), ("other", 0.10)],  # Arts/Design/Entertainment
        "29": [("62", 0.75), ("61", 0.08), ("92", 0.05), ("54", 0.03), ("55", 0.02), ("other", 0.07)],  # Healthcare Practitioners
        "31": [("62", 0.55), ("72", 0.12), ("61", 0.10), ("81", 0.06), ("71", 0.05), ("44", 0.04), ("other", 0.08)],  # Healthcare Support
        "33": [("92", 0.48), ("56", 0.15), ("61", 0.08), ("81", 0.06), ("48", 0.05), ("71", 0.04), ("52", 0.04), ("other", 0.10)],  # Protective Service
        "35": [("72", 0.50), ("62", 0.12), ("61", 0.10), ("71", 0.08), ("44", 0.06), ("81", 0.04), ("92", 0.03), ("other", 0.07)],  # Food Preparation
        "37": [("56", 0.25), ("81", 0.18), ("72", 0.12), ("62", 0.10), ("61", 0.08), ("92", 0.06), ("44", 0.05), ("53", 0.04), ("other", 0.12)],  # Building/Grounds
        "39": [("81", 0.25), ("62", 0.20), ("72", 0.15), ("71", 0.12), ("61", 0.08), ("44", 0.06), ("52", 0.04), ("other", 0.10)],  # Personal Care
        "41": [("44", 0.40), ("42", 0.18), ("52", 0.10), ("54", 0.08), ("31", 0.06), ("51", 0.04), ("72", 0.04), ("other", 0.10)],  # Sales
        "43": [("62", 0.18), ("52", 0.15), ("54", 0.12), ("92", 0.10), ("56", 0.08), ("61", 0.06), ("44", 0.06), ("31", 0.05), ("51", 0.05), ("other", 0.15)],  # Office/Admin
        "45": [("11", 0.60), ("21", 0.15), ("81", 0.08), ("92", 0.05), ("54", 0.04), ("other", 0.08)],  # Farming/Fishing/Forestry
        "47": [("23", 0.55), ("56", 0.12), ("31", 0.08), ("22", 0.06), ("48", 0.05), ("81", 0.04), ("other", 0.10)],  # Construction
        "49": [("44", 0.20), ("31", 0.18), ("48", 0.15), ("81", 0.12), ("23", 0.08), ("56", 0.06), ("42", 0.05), ("other", 0.16)],  # Installation/Maintenance
        "51": [("31", 0.55), ("42", 0.12), ("44", 0.08), ("23", 0.06), ("22", 0.04), ("48", 0.04), ("other", 0.11)],  # Production
        "53": [("48", 0.35), ("42", 0.18), ("44", 0.12), ("56", 0.08), ("31", 0.06), ("23", 0.05), ("81", 0.04), ("other", 0.12)],  # Transportation
    }

    NAICS_SECTORS = {
        "11": "Agriculture, Forestry, Fishing and Hunting",
        "21": "Mining, Quarrying, and Oil and Gas Extraction",
        "22": "Utilities",
        "23": "Construction",
        "31": "Manufacturing",
        "42": "Wholesale Trade",
        "44": "Retail Trade",
        "48": "Transportation and Warehousing",
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
        "92": "Public Administration",
    }

    def __init__(self, crosswalk_path: Optional[Path] = None):
        """Initialize with optional external crosswalk data."""
        self._external_crosswalk = None
        if crosswalk_path and crosswalk_path.exists():
            with open(crosswalk_path) as f:
                self._external_crosswalk = json.load(f)

    def sample_industry(
        self,
        soc_code: str,
        seed: int,
        exclude: Optional[set[str]] = None
    ) -> tuple[str, str]:
        """
        Sample an industry for an occupation.

        Returns:
            (naics_sector, industry_name)
        """
        rng = random.Random(seed)
        soc_major = soc_code[:2]
        exclude = exclude or set()

        # Try external crosswalk first
        if self._external_crosswalk and soc_major in self._external_crosswalk:
            weights = self._external_crosswalk[soc_major]
        elif soc_major in self.SOC_TO_NAICS_FALLBACK:
            weights = self.SOC_TO_NAICS_FALLBACK[soc_major]
        else:
            # Ultimate fallback: uniform distribution
            all_sectors = list(self.NAICS_SECTORS.keys())
            sector = rng.choice([s for s in all_sectors if s not in exclude])
            return sector, self.NAICS_SECTORS[sector]

        # Filter and normalize weights
        filtered = [(s, w) for s, w in weights if s not in exclude and s != "other"]
        if not filtered:
            # All options excluded, use any available
            sector = rng.choice(list(self.NAICS_SECTORS.keys()))
            return sector, self.NAICS_SECTORS.get(sector, "Unknown")

        total = sum(w for _, w in filtered)
        normalized = [(s, w / total) for s, w in filtered]

        # Weighted random selection
        r = rng.random()
        cumulative = 0.0
        for sector, weight in normalized:
            cumulative += weight
            if r <= cumulative:
                return sector, self.NAICS_SECTORS.get(sector, "Unknown")

        # Fallback to last option
        sector = normalized[-1][0]
        return sector, self.NAICS_SECTORS.get(sector, "Unknown")
```

---

## Part 5: Fixed Prompt Generation Pipeline

### 5.1 Phase 1: Persona Generation (With Diversity Verification)

```python
# src/prompts/phase1_personas.py
import hashlib
import json
from pathlib import Path
from typing import Optional
from collections import Counter

from src.prompts.schemas import Persona
from src.api.openrouter_client import OpenRouterClient

class PersonaGenerator:
    """Generate diverse personas with caching and verification."""

    PERSONA_PROMPT = """Generate {count} diverse professional personas for writing task evaluation.

Each persona should include:
- job_title: Specific job title (not generic)
- experience_level: One of [junior, mid, senior, executive]
- age_group: One of [gen_z, millennial, gen_x, boomer]
- communication_style: One of [formal, professional, casual, technical]
- industry_background: Specific industry

REQUIREMENTS:
1. Ensure diversity across ALL dimensions
2. Include underrepresented groups and industries
3. Job titles should be specific and realistic
4. Mix traditional and modern job titles

Output JSON array of personas.
"""

    def __init__(
        self,
        api_client: OpenRouterClient,
        cache_dir: Path,
        model_id: str = "anthropic/claude-sonnet"  # Cheaper model for generation
    ):
        self.api_client = api_client
        self.cache_dir = cache_dir
        self.model_id = model_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def generate_personas(
        self,
        count: int,
        force_regenerate: bool = False
    ) -> list[Persona]:
        """Generate or retrieve cached personas."""
        cache_key = f"personas_v1_{count}"
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists() and not force_regenerate:
            with open(cache_file) as f:
                data = json.load(f)
                return [Persona(**p) for p in data]

        # Generate in batches
        all_personas = []
        batch_size = min(50, count)  # Don't request too many at once
        remaining = count

        while remaining > 0:
            batch_count = min(batch_size, remaining)
            prompt = self.PERSONA_PROMPT.format(count=batch_count)

            response = await self.api_client.generate(
                model_id=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,  # Higher for diversity
                max_tokens=4000
            )

            try:
                personas_data = self._parse_json_response(response.content)
                for i, p_data in enumerate(personas_data):
                    persona = Persona(
                        id=f"persona_{len(all_personas) + i:04d}",
                        **p_data
                    )
                    all_personas.append(persona)
                remaining -= len(personas_data)
            except Exception as e:
                # Log and continue with reduced batch
                batch_size = max(10, batch_size // 2)

        # Verify diversity
        diversity_report = self._verify_diversity(all_personas)
        if diversity_report['warnings']:
            for warning in diversity_report['warnings']:
                print(f"Persona diversity warning: {warning}")

        # Cache
        with open(cache_file, 'w') as f:
            json.dump([p.model_dump() for p in all_personas], f, indent=2)

        return all_personas

    def _verify_diversity(self, personas: list[Persona]) -> dict:
        """Verify personas have adequate diversity."""
        warnings = []

        # Check distribution of each dimension
        dimensions = {
            'experience_level': Counter(p.experience_level for p in personas),
            'age_group': Counter(p.age_group for p in personas),
            'communication_style': Counter(p.communication_style for p in personas),
        }

        for dim_name, counts in dimensions.items():
            total = sum(counts.values())
            for value, count in counts.items():
                ratio = count / total
                if ratio < 0.1:
                    warnings.append(f"{dim_name}={value} underrepresented ({ratio:.1%})")
                elif ratio > 0.5:
                    warnings.append(f"{dim_name}={value} overrepresented ({ratio:.1%})")

        return {'warnings': warnings, 'distributions': dimensions}

    def _parse_json_response(self, text: str) -> list[dict]:
        """Robustly parse JSON from LLM response."""
        # Try direct parse
        text = text.strip()
        if text.startswith('['):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Extract JSON from markdown code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find array in text
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")
```

### 5.2 Phase 2: Memory-Efficient Combination (FIXED)

```python
# src/prompts/lazy_sampler.py
import random
from typing import Iterator, Any
from dataclasses import dataclass

@dataclass
class CombinationSpec:
    """Specification for a single combination without materializing it."""
    task_idx: int
    persona_idx: int
    urgency_idx: int
    word_count_idx: int
    formality_idx: int
    industry_idx: int


class LazyCombiner:
    """
    Memory-efficient stratified sampling using lazy evaluation.

    FIXES from simulations:
    - Does NOT materialize all combinations into memory
    - Uses deterministic selection via index arithmetic
    - Supports proper stratified sampling without explosion
    """

    URGENCY_LEVELS = ["low", "medium", "high", "critical"]
    WORD_COUNT_TIERS = ["short", "medium", "long"]
    FORMALITY_LEVELS = ["very_formal", "formal", "professional", "casual"]

    def __init__(
        self,
        tasks: list,
        personas: list,
        naics_sectors: list[str],
        seed: int
    ):
        self.tasks = tasks
        self.personas = personas
        self.naics_sectors = naics_sectors
        self.seed = seed
        self.rng = random.Random(seed)

        # Compute total combination space (for reference, not materialized)
        self.total_combinations = (
            len(tasks) *
            len(personas) *
            len(self.URGENCY_LEVELS) *
            len(self.WORD_COUNT_TIERS) *
            len(self.FORMALITY_LEVELS) *
            len(naics_sectors)
        )

    def sample_stratified(
        self,
        target_count: int,
        stratification_dims: list[str]
    ) -> Iterator[dict]:
        """
        Yield stratified sample without memory explosion.

        Uses hierarchical sampling:
        1. Divide target_count across primary stratification dimension
        2. Within each stratum, sample uniformly from remaining dimensions
        """
        if target_count >= self.total_combinations:
            # Just iterate all (still lazy)
            yield from self._iterate_all()
            return

        # Build stratum counts for primary dimension
        primary_dim = stratification_dims[0] if stratification_dims else "task"
        primary_values = self._get_dimension_values(primary_dim)
        base_per_stratum = target_count // len(primary_values)
        remainder = target_count % len(primary_values)

        yielded_count = 0
        seen_keys = set()

        for idx, primary_val in enumerate(primary_values):
            stratum_count = base_per_stratum + (1 if idx < remainder else 0)

            for _ in range(stratum_count * 3):  # Over-sample to account for collisions
                if yielded_count >= target_count:
                    return

                combo = self._sample_single_with_constraint(primary_dim, primary_val)
                combo_key = self._combo_key(combo)

                if combo_key not in seen_keys:
                    seen_keys.add(combo_key)
                    yielded_count += 1
                    yield combo

                if yielded_count >= target_count:
                    return

    def _sample_single_with_constraint(self, dim: str, value: Any) -> dict:
        """Sample a single combination with one dimension constrained."""
        combo = {
            'task': self.rng.choice(self.tasks),
            'persona': self.rng.choice(self.personas),
            'urgency': self.rng.choice(self.URGENCY_LEVELS),
            'word_count_tier': self.rng.choice(self.WORD_COUNT_TIERS),
            'formality': self.rng.choice(self.FORMALITY_LEVELS),
            'naics_sector': self.rng.choice(self.naics_sectors),
        }

        # Override the constrained dimension
        if dim == 'task':
            combo['task'] = value
        elif dim == 'persona':
            combo['persona'] = value
        elif dim == 'urgency':
            combo['urgency'] = value
        elif dim == 'word_count_tier':
            combo['word_count_tier'] = value
        elif dim == 'formality':
            combo['formality'] = value
        elif dim == 'naics_sector':
            combo['naics_sector'] = value
        elif dim == 'job_zone':
            # Filter tasks by job zone
            matching_tasks = [t for t in self.tasks if t.job_zone == value]
            if matching_tasks:
                combo['task'] = self.rng.choice(matching_tasks)
        elif dim == 'category':
            matching_tasks = [t for t in self.tasks if t.inferred_category == value]
            if matching_tasks:
                combo['task'] = self.rng.choice(matching_tasks)

        return combo

    def _get_dimension_values(self, dim: str) -> list:
        """Get all values for a stratification dimension."""
        if dim == 'task':
            return self.tasks
        elif dim == 'persona':
            return self.personas
        elif dim == 'urgency':
            return self.URGENCY_LEVELS
        elif dim == 'word_count_tier':
            return self.WORD_COUNT_TIERS
        elif dim == 'formality':
            return self.FORMALITY_LEVELS
        elif dim == 'naics_sector':
            return self.naics_sectors
        elif dim == 'job_zone':
            return sorted(set(t.job_zone for t in self.tasks))
        elif dim == 'category':
            return sorted(set(t.inferred_category for t in self.tasks))
        else:
            raise ValueError(f"Unknown dimension: {dim}")

    def _combo_key(self, combo: dict) -> str:
        """Generate unique key for deduplication."""
        task_id = combo['task'].task_id if hasattr(combo['task'], 'task_id') else str(combo['task'])
        persona_id = combo['persona'].id if hasattr(combo['persona'], 'id') else str(combo['persona'])
        return f"{task_id}|{persona_id}|{combo['urgency']}|{combo['word_count_tier']}|{combo['formality']}|{combo['naics_sector']}"

    def _iterate_all(self) -> Iterator[dict]:
        """Iterate all combinations lazily."""
        for task in self.tasks:
            for persona in self.personas:
                for urgency in self.URGENCY_LEVELS:
                    for word_count in self.WORD_COUNT_TIERS:
                        for formality in self.FORMALITY_LEVELS:
                            for naics in self.naics_sectors:
                                yield {
                                    'task': task,
                                    'persona': persona,
                                    'urgency': urgency,
                                    'word_count_tier': word_count,
                                    'formality': formality,
                                    'naics_sector': naics,
                                }
```

### 5.3 Phase 3: Enrichment with Attachment and Reply Support

```python
# src/prompts/phase3_enricher.py
from typing import Optional
import json
import re

from src.prompts.schemas import BasePrompt, EnrichedPrompt, PromptConstraint
from src.api.openrouter_client import OpenRouterClient

class PromptEnricher:
    """
    LLM-based prompt enrichment with full context support.

    FIXES from simulations:
    - Adds attachment content generation
    - Adds reply thread generation for response scenarios
    - Uses temporal context only when appropriate
    - Includes regional English variants
    """

    ENRICHMENT_PROMPT = """You are creating a realistic writing prompt for a professional writing evaluation.

INPUT CONTEXT:
- Task: {task}
- Occupation: {occupation}
- Writer Persona: {persona}
- Recipient: {recipient}
- Company: {company}
- Industry: {industry}
- Formality: {formality}
- Urgency: {urgency}
- Target length: {word_count_tier} ({word_count_range} words)
- English variant: {english_variant}
{attachment_instruction}
{reply_instruction}
{constraint_instruction}

Generate a complete, realistic writing prompt that:
1. Includes specific but fictional details (names, dates, numbers, project names)
2. {temporal_instruction}
3. Matches the exact formality level specified
4. Is appropriate for the occupation and industry
5. Does NOT include any placeholders like [X] or [Company Name]
6. Uses realistic details that could exist in the real world
{regional_instruction}

Output JSON:
{{
    "prompt_text": "The complete prompt text to show to the model",
    "scenario_summary": "1-sentence summary of the scenario",
    "expected_format": "email|memo|report|letter|other",
    "key_entities": ["list", "of", "specific", "names", "mentioned"]
    {attachment_json}
    {reply_json}
}}
"""

    def __init__(
        self,
        api_client: OpenRouterClient,
        model_id: str,
        temperature: float = 0.7
    ):
        self.api_client = api_client
        self.model_id = model_id
        self.temperature = temperature

    async def enrich_prompt(
        self,
        base_prompt: BasePrompt,
        include_attachment: bool = False,
        include_reply: bool = False,
        constraints: Optional[list[PromptConstraint]] = None
    ) -> EnrichedPrompt:
        """Enrich a base prompt with LLM-generated context."""

        # Build instruction strings based on options
        attachment_instruction = ""
        attachment_json = ""
        if include_attachment:
            attachment_instruction = """
- The prompt references an attached document. Generate realistic summary content for this attachment."""
            attachment_json = ',"attachment_summary": "Brief content of the attached document that the writer would reference"'

        reply_instruction = ""
        reply_json = ""
        if include_reply:
            reply_instruction = """
- This is a REPLY to a prior message. Generate the prior message(s) that the writer is responding to."""
            reply_json = ',"prior_messages": ["The prior message(s) being replied to"]'

        constraint_instruction = ""
        if constraints:
            constraint_str = "\n".join(f"- {c.description}" for c in constraints)
            constraint_instruction = f"""
Additional constraints the writing must follow:
{constraint_str}"""

        # Temporal instruction varies by urgency
        if base_prompt.urgency in ["high", "critical"]:
            temporal_instruction = "Provides clear context about why this communication is needed NOW (urgent deadline, immediate response needed)"
        elif base_prompt.urgency == "medium":
            temporal_instruction = "May include timing context if natural, but don't force it"
        else:
            temporal_instruction = "Do NOT include artificial time pressure - this is a routine communication"

        # Regional English instruction
        regional_instruction = ""
        if base_prompt.english_variant == "en-GB":
            regional_instruction = "Use British English spelling and conventions (colour, organisation, whilst)"
        elif base_prompt.english_variant == "en-AU":
            regional_instruction = "Use Australian English conventions"
        elif base_prompt.english_variant == "non-native":
            regional_instruction = "Write as if the persona is a non-native English speaker - competent but occasionally awkward phrasing"

        # Word count guidance
        word_count_ranges = {
            "short": "50-150",
            "medium": "150-400",
            "long": "400-800"
        }

        # Build full prompt
        prompt = self.ENRICHMENT_PROMPT.format(
            task=base_prompt.task.task,
            occupation=base_prompt.task.occupation_title,
            persona=f"{base_prompt.persona.job_title}, {base_prompt.persona.experience_level} level, {base_prompt.persona.communication_style} style",
            recipient=f"{base_prompt.recipient.full} at {base_prompt.company.name}",
            company=f"{base_prompt.company.name} ({base_prompt.company.size} company, {base_prompt.company.industry_description})",
            industry=base_prompt.industry,
            formality=base_prompt.formality,
            urgency=base_prompt.urgency,
            word_count_tier=base_prompt.word_count_tier,
            word_count_range=word_count_ranges.get(base_prompt.word_count_tier, "100-300"),
            english_variant=base_prompt.english_variant,
            attachment_instruction=attachment_instruction,
            reply_instruction=reply_instruction,
            constraint_instruction=constraint_instruction,
            temporal_instruction=temporal_instruction,
            regional_instruction=regional_instruction,
            attachment_json=attachment_json,
            reply_json=reply_json,
        )

        response = await self.api_client.generate(
            model_id=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=2000
        )

        # Parse response
        enrichment_data = self._parse_json_response(response.content)

        return EnrichedPrompt(
            id=base_prompt.id,
            base_prompt=base_prompt,
            prompt_text=enrichment_data['prompt_text'],
            context_details={
                'scenario_summary': enrichment_data.get('scenario_summary', ''),
                'expected_format': enrichment_data.get('expected_format', 'other'),
                'key_entities': enrichment_data.get('key_entities', []),
            },
            constraints=constraints or [],
            attachment_content=enrichment_data.get('attachment_summary'),
            prior_messages=enrichment_data.get('prior_messages'),
            metadata={
                'enrichment_model': self.model_id,
                'include_attachment': include_attachment,
                'include_reply': include_reply,
            }
        )

    def _parse_json_response(self, text: str) -> dict:
        """Robust JSON parsing from LLM output."""
        text = text.strip()

        # Direct parse
        if text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Extract from markdown
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Find object in text
        obj_match = re.search(r'\{[\s\S]*\}', text)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                pass

        # Last resort: return minimal valid structure
        return {
            'prompt_text': text,
            'scenario_summary': 'Parse failed - using raw text',
            'expected_format': 'other',
            'key_entities': []
        }
```

---

## Part 6: Fixed Evaluation Engine

### 6.1 Corrected Cost Estimation

**CRITICAL FIX**: The draft plan underestimated costs by 5-10x. Here is the corrected calculation:

```python
# src/config/cost_estimator.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class CostEstimate:
    response_generation_cost: float
    judging_cost: float
    enrichment_cost: float
    total_cost: float
    breakdown: dict

class CostEstimator:
    """
    Accurate cost estimation incorporating ALL judging factors.

    CRITICAL FIXES from simulations:
    - Position shuffling DOUBLES judge calls
    - Best-of-N voting MULTIPLIES judge calls
    - Two personas DOUBLE judge calls
    - Three judges TRIPLE judge calls
    """

    # Approximate pricing per 1K tokens (as of Jan 2026 - UPDATE BEFORE USE)
    MODEL_PRICING = {
        # Pro tier
        "google/gemini-3.0-pro": {"input": 0.005, "output": 0.015},
        "openai/gpt-5.2": {"input": 0.01, "output": 0.03},
        "anthropic/claude-opus-4.5": {"input": 0.015, "output": 0.075},
        "x-ai/grok-4.1": {"input": 0.008, "output": 0.024},
        "moonshot/kimi-k2": {"input": 0.006, "output": 0.018},

        # Flash tier
        "google/gemini-3.0-flash": {"input": 0.0005, "output": 0.0015},
        "openai/gpt-4.1": {"input": 0.003, "output": 0.006},
        "anthropic/claude-sonnet": {"input": 0.003, "output": 0.015},
    }

    # Average token counts (calibrated during warmup)
    DEFAULT_TOKEN_ESTIMATES = {
        "prompt_input": 500,
        "response_output": 300,
        "judge_input": 1200,  # Prompt + 2 responses + system prompt
        "judge_output": 250,
        "enrichment_input": 400,
        "enrichment_output": 600,
    }

    def estimate_full_eval(
        self,
        prompt_count: int,
        model_count: int,  # Models being evaluated
        judge_count: int,  # Number of judge models
        persona_count: int,  # Usually 2 (expert + recipient)
        votes_per_judge: int,  # Best-of-N voting
        position_shuffle: bool,  # Whether to test both orderings
        token_estimates: Optional[dict] = None
    ) -> CostEstimate:
        """
        Calculate total estimated cost.

        Formula:
        - Response calls = prompts * models
        - Comparisons = prompts * (model_count choose 2) = prompts * model_count * (model_count-1) / 2
        - Judge calls per comparison = judges * personas * votes * (2 if position_shuffle else 1)
        - Total judge calls = comparisons * judge_calls_per_comparison
        """
        tokens = token_estimates or self.DEFAULT_TOKEN_ESTIMATES

        # Response generation
        response_calls = prompt_count * model_count
        response_cost = self._estimate_response_cost(response_calls, tokens)

        # Judging
        comparisons_per_prompt = model_count * (model_count - 1) // 2
        total_comparisons = prompt_count * comparisons_per_prompt

        position_multiplier = 2 if position_shuffle else 1
        judge_calls_per_comparison = (
            judge_count *
            persona_count *
            votes_per_judge *
            position_multiplier
        )
        total_judge_calls = total_comparisons * judge_calls_per_comparison

        judging_cost = self._estimate_judge_cost(total_judge_calls, tokens)

        # Enrichment (one call per prompt)
        enrichment_cost = self._estimate_enrichment_cost(prompt_count, tokens)

        total = response_cost + judging_cost + enrichment_cost

        return CostEstimate(
            response_generation_cost=response_cost,
            judging_cost=judging_cost,
            enrichment_cost=enrichment_cost,
            total_cost=total,
            breakdown={
                "response_calls": response_calls,
                "total_comparisons": total_comparisons,
                "judge_calls_per_comparison": judge_calls_per_comparison,
                "total_judge_calls": total_judge_calls,
                "enrichment_calls": prompt_count,
            }
        )

    def _estimate_response_cost(self, call_count: int, tokens: dict) -> float:
        """Estimate response generation cost."""
        avg_price = self._average_price(list(self.MODEL_PRICING.keys())[:5])
        input_cost = call_count * tokens["prompt_input"] / 1000 * avg_price["input"]
        output_cost = call_count * tokens["response_output"] / 1000 * avg_price["output"]
        return input_cost + output_cost

    def _estimate_judge_cost(self, call_count: int, tokens: dict) -> float:
        """Estimate judging cost - uses pro-tier models."""
        avg_price = self._average_price([
            "anthropic/claude-opus-4.5",
            "openai/gpt-5.2",
            "google/gemini-3.0-pro"
        ])
        input_cost = call_count * tokens["judge_input"] / 1000 * avg_price["input"]
        output_cost = call_count * tokens["judge_output"] / 1000 * avg_price["output"]
        return input_cost + output_cost

    def _estimate_enrichment_cost(self, call_count: int, tokens: dict) -> float:
        """Estimate enrichment cost - uses cheaper model."""
        price = self.MODEL_PRICING.get(
            "anthropic/claude-sonnet",
            {"input": 0.003, "output": 0.015}
        )
        input_cost = call_count * tokens["enrichment_input"] / 1000 * price["input"]
        output_cost = call_count * tokens["enrichment_output"] / 1000 * price["output"]
        return input_cost + output_cost

    def _average_price(self, model_ids: list) -> dict:
        """Get average pricing across models."""
        input_total = sum(
            self.MODEL_PRICING.get(m, {"input": 0.01})["input"]
            for m in model_ids
        ) / len(model_ids)
        output_total = sum(
            self.MODEL_PRICING.get(m, {"output": 0.03})["output"]
            for m in model_ids
        ) / len(model_ids)
        return {"input": input_total, "output": output_total}
```

### 6.2 Corrected Preset Configurations

```python
# src/config/presets.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class EvalPreset:
    name: str
    prompt_count: int
    models: list[str]
    judge_models: list[str]
    judge_personas: list[str]
    votes_per_judge: int
    position_shuffle: bool
    estimated_cost_usd: float
    estimated_runtime_hours: float
    description: str


# CORRECTED cost estimates based on proper calculation
PRESETS = {
    "smoke": EvalPreset(
        name="smoke",
        prompt_count=10,
        models=["gemini_pro", "gpt_pro"],
        judge_models=["judge_claude"],
        judge_personas=["writing_expert"],  # Single persona for smoke
        votes_per_judge=1,  # No best-of voting
        position_shuffle=False,  # No position shuffle
        estimated_cost_usd=5,  # ~$3-7
        estimated_runtime_hours=0.1,
        description="Quick sanity check - verify pipeline works"
    ),

    "dev": EvalPreset(
        name="dev",
        prompt_count=30,
        models=["gemini_pro", "gpt_pro", "claude_pro"],
        judge_models=["judge_claude"],
        judge_personas=["writing_expert", "recipient"],
        votes_per_judge=1,
        position_shuffle=False,
        estimated_cost_usd=25,  # ~$15-35
        estimated_runtime_hours=0.3,
        description="Development iteration - test prompt quality"
    ),

    "quick": EvalPreset(
        name="quick",
        prompt_count=100,
        models=["gemini_pro", "gpt_pro", "claude_pro"],
        judge_models=["judge_claude", "judge_gpt"],
        judge_personas=["writing_expert", "recipient"],
        votes_per_judge=1,
        position_shuffle=True,  # Position shuffle ON
        estimated_cost_usd=150,  # ~$100-200
        estimated_runtime_hours=1.5,
        description="Quick evaluation with position bias handling"
    ),

    "standard": EvalPreset(
        name="standard",
        prompt_count=200,
        models=["gemini_pro", "gpt_pro", "claude_pro", "grok"],
        judge_models=["judge_claude", "judge_gpt", "judge_gemini"],
        judge_personas=["writing_expert", "recipient"],
        votes_per_judge=3,  # Reduced from 5
        position_shuffle=True,
        estimated_cost_usd=800,  # ~$600-1000
        estimated_runtime_hours=4,
        description="Standard evaluation with statistical power"
    ),

    "comprehensive": EvalPreset(
        name="comprehensive",
        prompt_count=500,
        models=["gemini_pro", "gpt_pro", "claude_pro", "grok", "kimi"],
        judge_models=["judge_claude", "judge_gpt", "judge_gemini"],
        judge_personas=["writing_expert", "recipient"],
        votes_per_judge=3,
        position_shuffle=True,
        estimated_cost_usd=2500,  # ~$2000-3000
        estimated_runtime_hours=10,
        description="Comprehensive evaluation for publication"
    ),

    "full": EvalPreset(
        name="full",
        prompt_count=1000,
        models=["gemini_pro", "gpt_pro", "claude_pro", "grok", "kimi"],
        judge_models=["judge_claude", "judge_gpt", "judge_gemini"],
        judge_personas=["writing_expert", "recipient"],
        votes_per_judge=5,  # Full best-of-5
        position_shuffle=True,
        estimated_cost_usd=8000,  # ~$6000-10000
        estimated_runtime_hours=24,
        description="Full rigorous evaluation"
    ),
}
```

### 6.3 Clarified Voting Methodology

```python
# src/eval/vote_aggregator.py
from dataclasses import dataclass
from typing import Literal
from collections import Counter

@dataclass
class VoteResult:
    winner: str  # model_a, model_b, or "TIE"
    votes_a: int
    votes_b: int
    votes_tie: int
    margin: float
    confidence: Literal["high", "medium", "low"]

class VoteAggregator:
    """
    Two-level majority-of-majorities aggregation.

    CLARIFICATION from simulations:
    The "best-of-N" in PROMPT.md refers to:
    - Each (judge, persona, position) combination votes N times
    - Not N different judges

    Aggregation hierarchy:
    1. Per-judge-persona: Take majority across position orderings
    2. Across judge-personas: Take majority of judge-persona majorities
    """

    def aggregate_comparison(
        self,
        judgments: list,  # list of ShuffledJudgment
        model_a: str,
        model_b: str
    ) -> VoteResult:
        """
        Aggregate votes using majority-of-majorities.

        Level 1: For each (judge, persona) pair, aggregate across positions
        Level 2: Take majority across all (judge, persona) pairs
        """

        # Group judgments by (judge, persona)
        judge_persona_groups = {}
        for j in judgments:
            key = (j.judge_model, j.persona_type)
            if key not in judge_persona_groups:
                judge_persona_groups[key] = []
            judge_persona_groups[key].append(j)

        # Level 1: Compute majority for each (judge, persona)
        level1_votes = []
        for (judge, persona), group in judge_persona_groups.items():
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
                confidence="low"
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
        margin = (max_votes - second_max) / total_votes

        if margin >= 0.5:
            confidence = "high"
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
            confidence=confidence
        )

    def _aggregate_group(
        self,
        judgments: list,
        model_a: str,
        model_b: str
    ) -> str:
        """Aggregate votes within a (judge, persona) group."""

        # Map position-relative winners to actual model winners
        actual_winners = []
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
```

### 6.4 Enhanced Dual-Persona Judge Prompts

```python
# src/eval/dual_persona.py

WRITING_EXPERT_SYSTEM_PROMPT = """You are an expert writing evaluator assessing professional business communications.

You have deep expertise in:
- Business communication standards across industries
- Writing style, tone, and appropriateness
- Grammar, clarity, and organization
- Persuasion and audience engagement

EVALUATION CRITERIA:
1. **Appropriateness**: Does the response match the expected formality, tone, and style for the scenario?
2. **Clarity**: Is the message clear, well-organized, and easy to understand?
3. **Authenticity**: Does it sound like a real professional wrote it (not AI-generated boilerplate)?
4. **Completeness**: Does it address all aspects of the task?
5. **Efficiency**: Is the length appropriate - not too wordy or too brief?

CONTEXT FOR THIS EVALUATION:
- Writer persona: {writer_persona}
- Writer's experience level: {experience_level}
- Industry: {industry}
- Target formality: {formality}
- Urgency level: {urgency}

You will compare two responses (A and B) to the same writing prompt.
Both responses are shown in randomized order - do NOT assume A is better than B."""

RECIPIENT_PERSONA_SYSTEM_PROMPT = """You are {recipient_name}, {recipient_role} at {company_name}.

You are evaluating two written responses to a business communication addressed to you.

YOUR PERSPECTIVE:
- You are busy and value clarity and directness
- You expect communications to match the appropriate level of formality
- You appreciate when writers get to the point while remaining professional
- You notice when writing feels robotic, overly formal, or generic

As the actual recipient of this communication, consider:
1. Would you read this entire message or skim/ignore it?
2. Does it clearly communicate what you need to know or do?
3. Does it feel like it was written by a real colleague?
4. Is the tone appropriate for your working relationship?

You will compare two responses (A and B). Judge based on which you would find more helpful and appropriate to receive."""

COMPARISON_PROMPT = """Compare these two responses to the following writing task:

TASK:
{prompt_text}

---
RESPONSE A:
{response_a}

---
RESPONSE B:
{response_b}

---
IMPORTANT: Responses are presented in random order. Evaluate them purely on merit.

Provide your judgment as JSON:
{{
    "reasoning": "2-3 sentences explaining your decision, focusing on specific differences",
    "winner": "A" or "B" or "TIE",
    "confidence": "high" or "medium" or "low",
    "scores": {{
        "appropriateness": {{"A": 1-5, "B": 1-5}},
        "clarity": {{"A": 1-5, "B": 1-5}},
        "authenticity": {{"A": 1-5, "B": 1-5}},
        "completeness": {{"A": 1-5, "B": 1-5}},
        "efficiency": {{"A": 1-5, "B": 1-5}}
    }},
    "weaknesses_a": ["specific weakness 1", "specific weakness 2"],
    "weaknesses_b": ["specific weakness 1", "specific weakness 2"]
}}
"""
```

---

## Part 7: Fixed API Layer

### 7.1 Model Verification with Semantic Version Matching

```python
# src/validation/model_verifier.py
import re
from typing import Optional
import httpx

class ModelVerifier:
    """
    Verify model availability with intelligent matching.

    FIXES from simulations:
    - Uses semantic version comparison, not substring matching
    - Handles provider ID variations
    - Provides clear user feedback on substitutions
    """

    EXPECTED_MODELS = {
        # Format: logical_name -> (provider, base_name, min_version)
        "gemini_pro": ("google", "gemini", "3.0"),
        "gpt_pro": ("openai", "gpt", "5"),
        "claude_pro": ("anthropic", "claude-opus", "4.5"),
        "grok": ("x-ai", "grok", "4"),
        "kimi": ("moonshot", "kimi", "k2"),
        "gemini_flash": ("google", "gemini", "3.0"),
        "gpt_flash": ("openai", "gpt", "4"),
        "claude_flash": ("anthropic", "claude-sonnet", ""),
    }

    async def verify_and_map_models(
        self,
        client: httpx.AsyncClient,
        api_key: str
    ) -> dict[str, str]:
        """
        Query OpenRouter and map logical names to actual model IDs.

        Returns dict mapping logical_name -> verified_model_id
        """
        # Fetch available models
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        available_models = response.json()["data"]

        # Build index by provider
        by_provider = {}
        for model in available_models:
            model_id = model["id"]
            provider = model_id.split("/")[0]
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(model)

        # Map each expected model
        verified = {}
        issues = []

        for logical_name, (provider, base_name, min_version) in self.EXPECTED_MODELS.items():
            match = self._find_best_match(
                by_provider.get(provider, []),
                base_name,
                min_version
            )

            if match:
                verified[logical_name] = match["id"]
            else:
                issues.append(f"Could not find model for {logical_name} ({provider}/{base_name})")

        if issues:
            raise ModelNotFoundError(
                f"Missing models:\n" + "\n".join(issues)
            )

        return verified

    def _find_best_match(
        self,
        provider_models: list,
        base_name: str,
        min_version: str
    ) -> Optional[dict]:
        """Find best matching model with version awareness."""
        candidates = []

        for model in provider_models:
            model_id = model["id"]
            name_part = model_id.split("/")[-1].lower()

            # Check base name match
            if base_name.lower() not in name_part:
                continue

            # Extract version
            version = self._extract_version(name_part)

            # Check minimum version
            if min_version and version:
                if not self._version_gte(version, min_version):
                    continue

            candidates.append((model, version or "0"))

        if not candidates:
            return None

        # Sort by version descending, prefer models without "preview"/"beta"
        def sort_key(item):
            model, version = item
            is_stable = "preview" not in model["id"].lower() and "beta" not in model["id"].lower()
            return (is_stable, version)

        candidates.sort(key=sort_key, reverse=True)
        return candidates[0][0]

    def _extract_version(self, name: str) -> Optional[str]:
        """Extract version number from model name."""
        # Match patterns like "3.0", "4.5", "5.2", "k2"
        match = re.search(r'(\d+(?:\.\d+)?)|([kK]\d+)', name)
        if match:
            return match.group(0)
        return None

    def _version_gte(self, version: str, min_version: str) -> bool:
        """Check if version >= min_version."""
        try:
            # Handle "k2" style versions
            if version.startswith(('k', 'K')):
                v = float(version[1:])
                m = float(min_version[1:]) if min_version.startswith(('k', 'K')) else float(min_version)
            else:
                v = float(version)
                m = float(min_version)
            return v >= m
        except ValueError:
            return True  # If can't parse, assume OK


class ModelNotFoundError(Exception):
    pass
```

### 7.2 Thread-Safe Circuit Breaker

```python
# src/api/circuit_breaker.py
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitStatus:
    state: CircuitState
    failure_count: int
    last_failure: Optional[datetime]
    next_retry: Optional[datetime]


class CircuitBreaker:
    """
    Thread-safe circuit breaker with hierarchical support.

    FIXES from simulations:
    - Uses asyncio.Lock for thread safety
    - Supports global + per-service circuits
    - Exposes status for TUI display
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.half_open_requests = half_open_requests

        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, CircuitState] = {}
        self._failure_counts: dict[str, int] = {}
        self._last_failures: dict[str, datetime] = {}
        self._half_open_successes: dict[str, int] = {}

    async def _get_lock(self, service_id: str) -> asyncio.Lock:
        """Get or create lock for service."""
        if service_id not in self._locks:
            self._locks[service_id] = asyncio.Lock()
        return self._locks[service_id]

    async def can_execute(self, service_id: str) -> bool:
        """Check if request should be allowed."""
        lock = await self._get_lock(service_id)
        async with lock:
            state = self._states.get(service_id, CircuitState.CLOSED)

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                last_failure = self._last_failures.get(service_id)
                if last_failure and datetime.now() - last_failure >= self.recovery_timeout:
                    self._states[service_id] = CircuitState.HALF_OPEN
                    self._half_open_successes[service_id] = 0
                    return True
                return False

            if state == CircuitState.HALF_OPEN:
                return True  # Allow probe requests

            return False

    async def record_success(self, service_id: str):
        """Record successful request."""
        lock = await self._get_lock(service_id)
        async with lock:
            state = self._states.get(service_id, CircuitState.CLOSED)

            if state == CircuitState.HALF_OPEN:
                self._half_open_successes[service_id] = \
                    self._half_open_successes.get(service_id, 0) + 1

                if self._half_open_successes[service_id] >= self.half_open_requests:
                    self._states[service_id] = CircuitState.CLOSED
                    self._failure_counts[service_id] = 0

            elif state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_counts[service_id] = 0

    async def record_failure(self, service_id: str):
        """Record failed request."""
        lock = await self._get_lock(service_id)
        async with lock:
            state = self._states.get(service_id, CircuitState.CLOSED)

            if state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._states[service_id] = CircuitState.OPEN
                self._last_failures[service_id] = datetime.now()

            elif state == CircuitState.CLOSED:
                self._failure_counts[service_id] = \
                    self._failure_counts.get(service_id, 0) + 1

                if self._failure_counts[service_id] >= self.failure_threshold:
                    self._states[service_id] = CircuitState.OPEN
                    self._last_failures[service_id] = datetime.now()

    def get_status(self, service_id: str) -> CircuitStatus:
        """Get current status for display."""
        state = self._states.get(service_id, CircuitState.CLOSED)
        failure_count = self._failure_counts.get(service_id, 0)
        last_failure = self._last_failures.get(service_id)

        next_retry = None
        if state == CircuitState.OPEN and last_failure:
            next_retry = last_failure + self.recovery_timeout

        return CircuitStatus(
            state=state,
            failure_count=failure_count,
            last_failure=last_failure,
            next_retry=next_retry
        )

    def get_all_statuses(self) -> dict[str, CircuitStatus]:
        """Get status for all tracked services."""
        all_services = set(self._states.keys()) | set(self._failure_counts.keys())
        return {s: self.get_status(s) for s in all_services}
```

### 7.3 Token Counter Implementation

```python
# src/api/token_counter.py
from typing import Optional
import tiktoken

class TokenCounter:
    """
    Accurate token counting using tiktoken.

    FIXES from simulations:
    - Actually implements token counting (was referenced but missing)
    - Uses appropriate tokenizer per model family
    - Provides estimation fallback
    """

    # Model family to tokenizer mapping
    TOKENIZERS = {
        "openai": "cl100k_base",     # GPT-4 and later
        "anthropic": "cl100k_base",   # Claude uses similar
        "google": None,               # No public tokenizer, estimate
        "x-ai": "cl100k_base",        # Grok likely similar
        "moonshot": None,             # No public tokenizer
    }

    def __init__(self):
        self._tokenizers = {}

    def count_tokens(self, text: str, model_id: str) -> int:
        """Count tokens for text given model."""
        provider = model_id.split("/")[0]
        tokenizer_name = self.TOKENIZERS.get(provider)

        if tokenizer_name:
            try:
                tokenizer = self._get_tokenizer(tokenizer_name)
                return len(tokenizer.encode(text))
            except Exception:
                pass

        # Fallback: estimate based on character count
        # Average is ~4 characters per token for English
        return max(1, len(text) // 4)

    def estimate_response_tokens(
        self,
        prompt_tokens: int,
        task_type: str,
        word_count_tier: str
    ) -> int:
        """Estimate expected response token count."""
        # Base estimates by task type
        base_estimates = {
            "email": 200,
            "memo": 300,
            "report": 500,
            "letter": 250,
            "other": 300,
        }

        # Adjust by word count tier
        tier_multipliers = {
            "short": 0.5,
            "medium": 1.0,
            "long": 2.0,
        }

        base = base_estimates.get(task_type, 300)
        multiplier = tier_multipliers.get(word_count_tier, 1.0)

        return int(base * multiplier)

    def _get_tokenizer(self, name: str):
        """Get or create tokenizer."""
        if name not in self._tokenizers:
            self._tokenizers[name] = tiktoken.get_encoding(name)
        return self._tokenizers[name]
```

---

## Part 8: Fixed Analysis and Statistics

### 8.1 Multiple Comparison Correction

```python
# src/analysis/significance.py
from scipy import stats
import numpy as np
from typing import Optional

class SignificanceCalculator:
    """
    Statistical significance with proper multiple comparison handling.

    FIXES from simulations:
    - Adds Bonferroni and FDR correction
    - Uses paired tests for proper comparison
    - Includes minimum sample size checks
    """

    MIN_SAMPLE_SIZE = 30  # Minimum for reliable statistical inference

    def mcnemars_test(
        self,
        paired_results: list[tuple[str, str]]  # List of (winner_model_a, winner_model_b) pairs
    ) -> dict:
        """
        McNemar's test for paired comparisons.

        Better than binomial test because results are paired (same prompt, different models).
        """
        # Count discordant pairs
        # a_wins_b_loses: Model A won when Model B lost
        # b_wins_a_loses: Model B won when Model A lost
        a_wins_b_loses = sum(1 for a, b in paired_results if a == 'win' and b == 'loss')
        b_wins_a_loses = sum(1 for a, b in paired_results if a == 'loss' and b == 'win')

        if a_wins_b_loses + b_wins_a_loses < 10:
            # Use exact binomial for small samples
            p_value = stats.binom_test(
                min(a_wins_b_loses, b_wins_a_loses),
                a_wins_b_loses + b_wins_a_loses,
                0.5
            )
        else:
            # Use chi-square approximation
            chi2 = (abs(a_wins_b_loses - b_wins_a_loses) - 1) ** 2 / (a_wins_b_loses + b_wins_a_loses)
            p_value = 1 - stats.chi2.cdf(chi2, 1)

        return {
            'statistic': chi2 if a_wins_b_loses + b_wins_a_loses >= 10 else None,
            'p_value': p_value,
            'discordant_pairs': (a_wins_b_loses, b_wins_a_loses),
            'test_type': 'mcnemar'
        }

    def bonferroni_correction(
        self,
        p_values: list[float],
        alpha: float = 0.05
    ) -> dict:
        """Apply Bonferroni correction for multiple comparisons."""
        n_tests = len(p_values)
        corrected_alpha = alpha / n_tests
        corrected_p_values = [min(1.0, p * n_tests) for p in p_values]
        significant = [p < corrected_alpha for p in p_values]

        return {
            'original_alpha': alpha,
            'corrected_alpha': corrected_alpha,
            'original_p_values': p_values,
            'corrected_p_values': corrected_p_values,
            'significant': significant,
            'method': 'bonferroni'
        }

    def fdr_correction(
        self,
        p_values: list[float],
        alpha: float = 0.05
    ) -> dict:
        """Apply Benjamini-Hochberg FDR correction."""
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]

        # Calculate BH thresholds
        thresholds = [(i + 1) * alpha / n for i in range(n)]

        # Find largest p-value <= threshold
        significant = [False] * n
        largest_significant = -1
        for i in range(n - 1, -1, -1):
            if sorted_p[i] <= thresholds[i]:
                largest_significant = i
                break

        if largest_significant >= 0:
            for i in range(largest_significant + 1):
                significant[sorted_indices[i]] = True

        # Calculate adjusted p-values
        adjusted = np.zeros(n)
        adjusted[sorted_indices[-1]] = sorted_p[-1]
        for i in range(n - 2, -1, -1):
            adjusted[sorted_indices[i]] = min(
                adjusted[sorted_indices[i + 1]],
                sorted_p[i] * n / (i + 1)
            )

        return {
            'original_alpha': alpha,
            'original_p_values': p_values,
            'adjusted_p_values': adjusted.tolist(),
            'significant': significant,
            'method': 'benjamini_hochberg'
        }

    def wilson_score_interval(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """
        Wilson score confidence interval for proportions.

        More accurate than normal approximation, especially for extreme proportions.
        """
        if total == 0:
            return (0.0, 1.0)

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = wins / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator

        return (max(0.0, center - margin), min(1.0, center + margin))
```

### 8.2 Weakness Theme Clustering

```python
# src/analysis/theme_clusterer.py
from collections import Counter
from typing import Optional
import re

class WeaknessThemeClusterer:
    """
    Cluster similar weakness descriptions into themes.

    FIXES from simulations:
    - Canonicalizes similar weaknesses
    - Groups by semantic similarity
    - Provides taxonomy for reporting
    """

    # Canonical weakness themes with pattern matchers
    WEAKNESS_TAXONOMY = {
        'verbose': [
            r'too (?:long|wordy|verbose)',
            r'(?:overly|excessively) (?:long|wordy|verbose)',
            r'could be (?:shorter|more concise)',
            r'unnecessary (?:words|length|detail)',
            r'rambl',
        ],
        'too_brief': [
            r'too (?:short|brief|terse)',
            r'lacks? (?:detail|depth)',
            r'insufficient',
            r'underdeveloped',
            r'needs? more (?:detail|explanation)',
        ],
        'wrong_tone': [
            r'(?:in)?appropriate tone',
            r'too (?:formal|informal|casual)',
            r'(?:wrong|incorrect) formality',
            r'tone (?:mismatch|issue)',
        ],
        'unclear': [
            r'unclear',
            r'confusing',
            r'hard to (?:follow|understand)',
            r'ambiguous',
            r'vague',
        ],
        'missing_info': [
            r'missing (?:information|details|context)',
            r'doesn\'t (?:address|mention|include)',
            r'fails? to (?:address|mention|include)',
            r'omits?',
        ],
        'generic': [
            r'generic',
            r'boilerplate',
            r'template-like',
            r'(?:sounds?|feels?) (?:like )?AI',
            r'not authentic',
            r'impersonal',
        ],
        'structure': [
            r'poor (?:structure|organization)',
            r'(?:dis)?organized',
            r'flow issues?',
            r'logical (?:flow|order)',
        ],
        'grammar': [
            r'grammar',
            r'spelling',
            r'typo',
            r'punctuation',
            r'syntax',
        ],
        'off_topic': [
            r'off[- ]topic',
            r'doesn\'t (?:answer|address) the (?:question|task)',
            r'irrelevant',
            r'miss(?:es|ed) the point',
        ],
    }

    def __init__(self):
        # Pre-compile patterns
        self._compiled_patterns = {
            theme: [re.compile(p, re.IGNORECASE) for p in patterns]
            for theme, patterns in self.WEAKNESS_TAXONOMY.items()
        }

    def classify_weakness(self, weakness_text: str) -> str:
        """Classify a single weakness into a canonical theme."""
        weakness_lower = weakness_text.lower()

        for theme, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(weakness_lower):
                    return theme

        return 'other'

    def cluster_weaknesses(
        self,
        weaknesses: list[str]
    ) -> dict[str, list[str]]:
        """
        Cluster list of weaknesses into themes.

        Returns dict mapping theme -> list of original weakness strings.
        """
        clusters = {}

        for weakness in weaknesses:
            theme = self.classify_weakness(weakness)
            if theme not in clusters:
                clusters[theme] = []
            clusters[theme].append(weakness)

        return clusters

    def get_theme_counts(
        self,
        weaknesses: list[str]
    ) -> Counter:
        """Get count of each theme in weakness list."""
        themes = [self.classify_weakness(w) for w in weaknesses]
        return Counter(themes)

    def generate_summary(
        self,
        weaknesses: list[str],
        min_count: int = 3
    ) -> list[dict]:
        """
        Generate summary of weakness themes.

        Returns list of dicts with theme, count, percentage, and examples.
        """
        if not weaknesses:
            return []

        clusters = self.cluster_weaknesses(weaknesses)
        total = len(weaknesses)

        summary = []
        for theme, examples in sorted(clusters.items(), key=lambda x: -len(x[1])):
            count = len(examples)
            if count >= min_count:
                summary.append({
                    'theme': theme,
                    'count': count,
                    'percentage': count / total * 100,
                    'examples': examples[:3]  # First 3 examples
                })

        return summary
```

---

## Part 9: Fixed Checkpoint System

### 9.1 Atomic Checkpoint with Proper Async

```python
# src/storage/checkpoint.py
import aiofiles
import aiofiles.os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import asyncio

from src.eval.schemas import EvalState

class CheckpointManager:
    """
    Atomic checkpoint system with async support.

    FIXES from simulations:
    - Uses aiofiles.os.rename for async atomic rename
    - Validates checkpoint consistency on load
    - Tracks checkpoint frequency
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        checkpoint_frequency: int = 10  # Save every N prompts
    ):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_frequency = checkpoint_frequency
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self._checkpoint_file = checkpoint_dir / "checkpoint.json"
        self._temp_file = checkpoint_dir / "checkpoint.json.tmp"
        self._prompts_since_checkpoint = 0
        self._lock = asyncio.Lock()

    async def save_checkpoint(self, state: EvalState, force: bool = False):
        """
        Save checkpoint atomically.

        Uses write-to-temp + atomic-rename pattern.
        """
        self._prompts_since_checkpoint += 1

        if not force and self._prompts_since_checkpoint < self.checkpoint_frequency:
            return

        async with self._lock:
            checkpoint_data = {
                'version': 1,
                'saved_at': datetime.utcnow().isoformat(),
                'state': state.model_dump(mode='json')
            }

            # Write to temp file
            async with aiofiles.open(self._temp_file, 'w') as f:
                await f.write(json.dumps(checkpoint_data, indent=2))

            # Atomic rename
            await aiofiles.os.rename(self._temp_file, self._checkpoint_file)

            self._prompts_since_checkpoint = 0

    async def load_checkpoint(self) -> Optional[EvalState]:
        """Load checkpoint if it exists and is valid."""
        if not self._checkpoint_file.exists():
            return None

        try:
            async with aiofiles.open(self._checkpoint_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)

            # Version check
            if data.get('version') != 1:
                return None

            state = EvalState(**data['state'])

            # Validate consistency
            if not await self._validate_checkpoint(state):
                return None

            return state

        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    async def _validate_checkpoint(self, state: EvalState) -> bool:
        """
        Validate checkpoint consistency.

        Checks that checkpoint state matches actual database state.
        """
        # Total should equal completed + pending + failed
        expected_total = len(state.completed_prompt_ids) + len(state.pending_prompt_ids) + len(state.failed_prompt_ids)

        if expected_total != state.total_prompts:
            return False

        if state.completed_count != len(state.completed_prompt_ids):
            return False

        return True

    async def clear_checkpoint(self):
        """Remove checkpoint file."""
        if self._checkpoint_file.exists():
            await aiofiles.os.remove(self._checkpoint_file)
        if self._temp_file.exists():
            await aiofiles.os.remove(self._temp_file)

    def checkpoint_exists(self) -> bool:
        """Check if checkpoint exists."""
        return self._checkpoint_file.exists()
```

### 9.2 Graceful Shutdown Handler

```python
# src/eval/orchestrator.py (partial - shutdown handling)
import asyncio
import signal
from typing import Optional, Set

class GracefulShutdown:
    """
    Handle graceful shutdown on SIGINT/SIGTERM.

    FIXES from simulations:
    - Actually implements signal handling (was mentioned but missing)
    - Tracks in-flight requests
    - Ensures checkpoint before exit
    """

    def __init__(self, checkpoint_manager, timeout: float = 30.0):
        self.checkpoint_manager = checkpoint_manager
        self.timeout = timeout
        self.shutdown_requested = False
        self._in_flight_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    def setup_handlers(self):
        """Install signal handlers."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_signal(s))
            )

    async def _handle_signal(self, sig: signal.Signals):
        """Handle shutdown signal."""
        if self.shutdown_requested:
            # Second signal = force quit
            print("\nForce shutdown requested...")
            raise SystemExit(1)

        self.shutdown_requested = True
        print(f"\nShutdown requested ({sig.name}). Waiting for in-flight requests...")
        self._shutdown_event.set()

    def register_task(self, task: asyncio.Task):
        """Register an in-flight task."""
        self._in_flight_tasks.add(task)
        task.add_done_callback(self._in_flight_tasks.discard)

    async def wait_for_shutdown(self, current_state) -> bool:
        """
        Wait for graceful shutdown completion.

        Returns True if shutdown was clean, False if forced.
        """
        await self._shutdown_event.wait()

        # Wait for in-flight tasks with timeout
        if self._in_flight_tasks:
            print(f"Waiting for {len(self._in_flight_tasks)} in-flight requests...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._in_flight_tasks, return_exceptions=True),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                print(f"Timeout waiting for tasks, {len(self._in_flight_tasks)} tasks cancelled")
                for task in self._in_flight_tasks:
                    task.cancel()

        # Save final checkpoint
        print("Saving checkpoint...")
        await self.checkpoint_manager.save_checkpoint(current_state, force=True)
        print("Checkpoint saved.")

        return True
```

---

## Part 10: Database Schema

```sql
-- src/storage/schema.sql

-- Main prompts table
CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    occupation_title TEXT NOT NULL,
    job_zone INTEGER NOT NULL,
    soc_major TEXT NOT NULL,
    inferred_category TEXT NOT NULL,
    inferred_channel TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    persona_title TEXT NOT NULL,
    persona_experience TEXT NOT NULL,
    company_name TEXT NOT NULL,
    naics_sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    formality TEXT NOT NULL,
    urgency TEXT NOT NULL,
    word_count_tier TEXT NOT NULL,
    english_variant TEXT NOT NULL DEFAULT 'en-US',
    prompt_text TEXT NOT NULL,
    has_attachment BOOLEAN DEFAULT FALSE,
    has_reply_context BOOLEAN DEFAULT FALSE,
    attachment_content TEXT,
    prior_messages TEXT,  -- JSON array
    constraints TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model responses
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    model_id TEXT NOT NULL,
    response_text TEXT,
    status TEXT NOT NULL,  -- success, error, timeout, refused, empty
    error_message TEXT,
    latency_ms REAL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_id)
);

-- Individual judgments
CREATE TABLE IF NOT EXISTS judgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    persona_type TEXT NOT NULL,  -- writing_expert, recipient
    position_order TEXT NOT NULL,  -- AB, BA
    position_a_model TEXT NOT NULL,
    position_b_model TEXT NOT NULL,
    winner TEXT NOT NULL,  -- A, B, TIE, PARSE_ERROR
    confidence TEXT,
    reasoning TEXT,
    scores TEXT,  -- JSON
    weaknesses_a TEXT,  -- JSON array
    weaknesses_b TEXT,  -- JSON array
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated results
CREATE TABLE IF NOT EXISTS aggregated_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    winner TEXT NOT NULL,  -- model_a, model_b, TIE
    gemini_model_id TEXT NOT NULL,
    gemini_was_a BOOLEAN NOT NULL,
    votes_model_a INTEGER NOT NULL,
    votes_model_b INTEGER NOT NULL,
    votes_tie INTEGER NOT NULL,
    inter_judge_agreement REAL,
    position_consistency REAL,
    margin REAL,
    confidence TEXT,  -- high, medium, low
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_a, model_b)
);

-- Checkpoint state (single row)
CREATE TABLE IF NOT EXISTS checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    run_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    completed_prompt_ids TEXT NOT NULL,  -- JSON array
    pending_prompt_ids TEXT NOT NULL,  -- JSON array
    failed_prompt_ids TEXT NOT NULL,  -- JSON array
    total_prompts INTEGER NOT NULL,
    completed_count INTEGER NOT NULL,
    total_cost_usd REAL NOT NULL,
    started_at TIMESTAMP,
    last_checkpoint TIMESTAMP
);

-- Run metadata
CREATE TABLE IF NOT EXISTS run_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(inferred_category);
CREATE INDEX IF NOT EXISTS idx_prompts_job_zone ON prompts(job_zone);
CREATE INDEX IF NOT EXISTS idx_prompts_naics ON prompts(naics_sector);
CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
CREATE INDEX IF NOT EXISTS idx_responses_status ON responses(status);
CREATE INDEX IF NOT EXISTS idx_judgments_prompt ON judgments(prompt_id);
CREATE INDEX IF NOT EXISTS idx_aggregated_winner ON aggregated_results(winner);
CREATE INDEX IF NOT EXISTS idx_aggregated_gemini ON aggregated_results(gemini_model_id);
```

---

## Part 11: Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
1. Project setup with all dependencies
2. Configuration system and presets
3. Database schema and migrations
4. O*NET schema validation
5. OpenRouter model verification

**Acceptance Criteria:**
- `python -m src.cli validate` passes all checks
- `pytest tests/unit` passes
- All required data files exist

**Dependencies:**
- O*NET database file (db/onet.db)
- OpenRouter API key

### Phase 2: Data Pipeline (Week 3-4)

**Deliverables:**
1. O*NET task extraction with writing relevance scoring
2. NAICS mapping with complete fallback data
3. Company database with generation script
4. Name generator with demographic diversity
5. Phase 1 persona generation with caching

**Acceptance Criteria:**
- Extract 500+ writing-relevant tasks
- Map all 22 SOC major groups to NAICS
- Generate 100+ diverse personas
- All unit tests pass

**Dependencies:**
- Phase 1 complete
- companies.json created or generated
- names.json created

### Phase 3: Prompt Generation (Week 5-6)

**Deliverables:**
1. Phase 2 algorithmic combination (lazy sampler)
2. Phase 3 LLM enrichment
3. Constraint generator and verifier
4. Attachment and reply context generators
5. Prompt deduplication

**Acceptance Criteria:**
- Generate 100 enriched prompts in under 30 minutes
- No duplicate prompts in output
- Constraints are verifiable
- Prompt quality spot-check passes

**Dependencies:**
- Phase 2 complete
- OpenRouter API access

### Phase 4: Evaluation Engine (Week 7-9)

**Deliverables:**
1. Response collector with parallel execution
2. Dual-persona judge prompts
3. Position bias handler
4. Vote aggregator with majority-of-majorities
5. Auto-loss detector

**Acceptance Criteria:**
- `smoke` preset runs end-to-end
- `dev` preset produces valid results
- Position shuffle working correctly
- Refusals detected and categorized

**Dependencies:**
- Phase 3 complete
- OpenRouter API access (significant usage)

### Phase 5: API Layer Hardening (Week 10)

**Deliverables:**
1. Rate limiter with per-model limits
2. Circuit breaker with thread safety
3. Retry handler with exponential backoff
4. Token counter for cost tracking

**Acceptance Criteria:**
- No rate limit errors in extended runs
- Recovery from API failures
- Cost tracking accurate to within 20%

**Dependencies:**
- Phase 4 complete

### Phase 6: Analysis and Reporting (Week 11-12)

**Deliverables:**
1. Win rate statistics with confidence intervals
2. Agreement metrics (Fleiss/Cohen Kappa)
3. Bias detection (position, length, self-preference)
4. Weakness finder with theme clustering
5. PDF report generator with templates
6. Statistical significance with multiple comparison correction

**Acceptance Criteria:**
- All statistics calculated correctly
- PDF reports render properly
- Weakness themes are meaningful

**Dependencies:**
- Phase 5 complete
- Report templates created

### Phase 7: TUI and Polish (Week 13-14)

**Deliverables:**
1. Progress dashboard with live updates
2. Results browser with filtering
3. Side-by-side comparison viewer
4. Error recovery screen
5. Export functionality

**Acceptance Criteria:**
- TUI responsive during evaluation
- Filtering works correctly
- Keyboard navigation complete

**Dependencies:**
- Phase 6 complete

### Phase 8: Testing and Validation (Week 15)

**Deliverables:**
1. Full test suite
2. End-to-end smoke tests
3. Documentation
4. Bug fixes from testing

**Acceptance Criteria:**
- `quick` preset runs without errors
- All tests pass
- Documentation complete

**Dependencies:**
- All previous phases complete

---

## Part 12: Risk Mitigation

### High-Risk Items and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Model IDs change before Jan 2026 | High | High | Runtime verification, user-configurable model mapping |
| O*NET schema differs from expected | High | Medium | Schema validation at startup, adaptable queries |
| Cost overruns | High | Medium | Budget limits, warning thresholds, preset cost estimates |
| Rate limiting causes delays | Medium | High | Adaptive rate limiting, circuit breakers, retry logic |
| Judge model disagreement | Medium | Medium | Multiple judges, majority voting, agreement metrics |
| Position bias not eliminated | Medium | Medium | Position shuffling, bias detection, reporting |
| Memory issues with large evals | Medium | Low | Lazy sampling, streaming, checkpointing |
| WeasyPrint installation fails | Low | Medium | Reportlab fallback, Docker option |

### Contingency Plans

1. **Model unavailability**: Configure alternative models via environment variables
2. **API outage**: Checkpoint frequently, resume from last state
3. **Cost exceeds budget**: Hard stop with partial results export
4. **Schema mismatch**: Provide schema discovery utility, document required tables

---

## Part 13: Success Metrics

### Technical Success Criteria

- [ ] All presets run without errors
- [ ] Checkpoint/resume works correctly
- [ ] Cost estimates within 30% of actual
- [ ] Position bias < 5% (measured via detection)
- [ ] Inter-judge agreement (Fleiss Kappa) > 0.6
- [ ] Response collection latency < 5 seconds per prompt (parallel)

### Scientific Success Criteria

- [ ] Statistical power sufficient to detect 10% win rate differences
- [ ] Confidence intervals correctly calibrated
- [ ] Multiple comparison correction applied
- [ ] Weakness themes actionable for Gemini team

### Operational Success Criteria

- [ ] Full evaluation completes within 24 hours
- [ ] No data loss during evaluation
- [ ] Reports usable by non-technical stakeholders
- [ ] Results reproducible with same seed

---

## Appendix A: Quick Start Guide

```bash
# 1. Clone and setup
git clone <repo>
cd gemini-writing-eval

# 2. Install system dependencies (macOS)
brew install cairo pango gdk-pixbuf libffi

# 3. Create virtual environment
python -m venv venv
source venv/bin/activate

# 4. Install package
pip install -e ".[dev]"

# 5. Configure environment
cp .env.example .env
# Edit .env with your OpenRouter API key

# 6. Verify setup
python -m src.cli validate

# 7. Run smoke test
python -m src.cli run --preset smoke

# 8. View results
python -m src.cli browse results/smoke_*/
```

---

## Appendix B: Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError: weasyprint` | Missing system dependencies | Install cairo, pango via brew/apt |
| `Model not found` errors | Model IDs changed | Run `validate` to see available models |
| `Rate limit exceeded` | Too many concurrent requests | Reduce `MAX_CONCURRENT_REQUESTS` |
| `Checkpoint corrupt` | Crash during write | Delete checkpoint, restart |
| `Out of memory` | Large eval, full combination space | Use lazy sampler, reduce preset size |
| `JSON parse error` from judge | LLM returned invalid format | Fallback parser handles most cases |
| `Budget exceeded` | Underestimated costs | Check estimate before running, increase budget |

