# Gemini Writing Evaluation Framework: Implementation Plan

## Executive Summary

This plan details the complete implementation of a production-grade evaluation framework for comparing Gemini 3.0 Pro and Flash against competing frontier LLMs on realistic professional writing tasks. The system leverages the O*NET 30.1 database (18,796 task statements across 1,016 occupations) to generate authentic, diverse writing prompts that span every job in the US economy.

---

## 1. SYSTEM ARCHITECTURE

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GEMINI WRITING EVALUATION FRAMEWORK                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   O*NET DB   │───▶│    PROMPT    │───▶│   RESPONSE   │───▶│  JUDGING  │ │
│  │   Pipeline   │    │  GENERATOR   │    │  GENERATOR   │    │   ENGINE  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                   │                   │                  │        │
│         ▼                   ▼                   ▼                  ▼        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         RESULTS DATABASE                             │  │
│  │                      (SQLite + JSON files)                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │                   │                   │                  │        │
│         ▼                   ▼                   ▼                  ▼        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   PROGRESS   │    │   ANALYSIS   │    │   REPORTS    │    │    TUI    │ │
│  │   TRACKER    │    │    ENGINE    │    │  GENERATOR   │    │  VIEWER   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Directory Structure

```
gemini-writing-eval/
├── src/
│   ├── __init__.py
│   ├── main.py                    # CLI entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Pydantic settings
│   │   ├── presets.py             # 10 eval presets
│   │   └── models.py              # Model configuration
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py      # O*NET database access
│   │   ├── task_sampler.py        # Stratified sampling
│   │   ├── naics_mapper.py        # Industry mapping
│   │   └── company_db.py          # Real company names
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py           # Three-phase prompt generation
│   │   ├── personas.py            # Writer/recipient personas
│   │   ├── enrichment.py          # LLM enrichment logic
│   │   └── schemas.py             # Pydantic prompt schemas
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── runner.py              # Main eval orchestrator
│   │   ├── response_gen.py        # Model response collection
│   │   ├── judge.py               # Judging logic
│   │   ├── voting.py              # Majority-of-majorities
│   │   └── bias_detection.py      # Position/length bias
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite operations
│   │   ├── checkpoint.py          # Resume/checkpoint
│   │   └── exporter.py            # CSV/JSON export
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter.py          # OpenRouter client
│   │   ├── rate_limiter.py        # Adaptive rate limiting
│   │   └── retry.py               # Exponential backoff
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── progress.py            # Rich TUI progress
│   │   ├── viewer.py              # Results viewer TUI
│   │   └── components.py          # Shared UI components
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # Win rates, CI, significance
│   │   ├── weakness.py            # Weakness identification
│   │   └── visualizations.py      # Chart generation
│   └── reports/
│       ├── __init__.py
│       ├── pdf_generator.py       # PDF report
│       └── templates/             # Report templates
├── db/
│   ├── onet.db                    # O*NET 30.1 database
│   └── ONET_WRITING_REFERENCE.md
├── results/                       # Eval run outputs
├── tests/
│   ├── __init__.py
│   ├── test_prompts.py
│   ├── test_evaluation.py
│   └── test_storage.py
├── pyproject.toml
├── README.md
└── .env.example
```

### 1.3 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async support, rich ecosystem |
| HTTP Client | httpx | Async support, modern API |
| Data Models | Pydantic v2 | Validation, serialization, settings |
| Database | SQLite + aiosqlite | Simple, portable, async-capable |
| TUI | Textual (rich-based) | Modern terminal UI framework |
| Charts | Plotly | Interactive, PDF-exportable |
| PDF | ReportLab + Plotly | Professional PDF generation |
| CLI | Typer | Type-annotated CLI |
| Config | python-dotenv | Environment configuration |

### 1.4 Key Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27"
pydantic = "^2.5"
pydantic-settings = "^2.1"
aiosqlite = "^0.19"
textual = "^0.41"
typer = "^0.9"
plotly = "^5.18"
kaleido = "^0.2"  # Plotly export
reportlab = "^4.0"
python-dotenv = "^1.0"
numpy = "^1.26"
scipy = "^1.11"   # Statistical tests
pandas = "^2.1"   # Data analysis
```

---

## 2. DATA PIPELINE: O*NET TO PROMPTS

### 2.1 O*NET Data Extraction

The O*NET 30.1 database contains 18,796 task statements across 923 occupations with tasks. We extract and enrich this data systematically.

#### 2.1.1 Core Extraction Query

```python
class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database."""

    WRITING_TASK_QUERY = """
    SELECT
        t.task_id,
        t.onetsoc_code,
        o.title AS occupation_title,
        o.description AS occupation_desc,
        t.task AS task_statement,
        t.task_type,
        jz.job_zone,
        SUBSTR(t.onetsoc_code, 1, 2) AS soc_major_code
    FROM task_statements t
    JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
    LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
    WHERE
        t.task LIKE '%write%' OR t.task LIKE '%draft%' OR
        t.task LIKE '%document%' OR t.task LIKE '%correspond%' OR
        t.task LIKE '%report%' OR t.task LIKE '%prepare%' OR
        t.task LIKE '%email%' OR t.task LIKE '%memo%' OR
        t.task LIKE '%proposal%' OR t.task LIKE '%communicate%' OR
        t.task LIKE '%notify%' OR t.task LIKE '%inform%' OR
        t.task LIKE '%negotiate%' OR t.task LIKE '%recommend%' OR
        t.task LIKE '%evaluate%' OR t.task LIKE '%review%'
    ORDER BY jz.job_zone, t.onetsoc_code
    """
```

#### 2.1.2 Writing Context Enrichment

```python
WRITING_CONTEXT_QUERY = """
SELECT
    o.onetsoc_code,
    o.title,
    MAX(CASE WHEN wc.element_id = '4.C.1.a.2.h' THEN wc.data_value END) AS email_frequency,
    MAX(CASE WHEN wc.element_id = '4.C.1.a.2.j' THEN wc.data_value END) AS letter_frequency,
    MAX(CASE WHEN sk.element_id = '2.A.1.c' THEN sk.data_value END) AS writing_skill_importance,
    MAX(CASE WHEN ab.element_id = '1.A.1.a.4' THEN ab.data_value END) AS written_expression_ability
FROM occupation_data o
LEFT JOIN work_context wc ON o.onetsoc_code = wc.onetsoc_code AND wc.scale_id = 'CX'
LEFT JOIN skills sk ON o.onetsoc_code = sk.onetsoc_code AND sk.scale_id = 'IM'
LEFT JOIN abilities ab ON o.onetsoc_code = ab.onetsoc_code AND ab.scale_id = 'IM'
GROUP BY o.onetsoc_code, o.title
"""
```

### 2.2 Task Classification

Rather than hardcoding categories, we use pattern-based inference that lets the data drive classification:

```python
class TaskClassifier:
    """Infer writing task characteristics from task statement text."""

    PATTERNS = {
        # Communication medium inference
        'medium': [
            (r'\bemail\b', 'email'),
            (r'\bmemo\b', 'memo'),
            (r'\breport\b', 'report'),
            (r'\bletter\b', 'letter'),
            (r'\bpresent(ation)?\b', 'presentation'),
            (r'\bproposal\b', 'proposal'),
            (r'\bcontract\b', 'contract'),
            (r'\bpolic(y|ies)\b', 'policy_document'),
        ],
        # Recipient inference
        'recipient_type': [
            (r'\bcustomer\b', 'external_customer'),
            (r'\bclient\b', 'external_client'),
            (r'\bstaff\b', 'internal_staff'),
            (r'\bmanagement\b', 'internal_management'),
            (r'\bpublic\b', 'public'),
            (r'\bvendor\b', 'external_vendor'),
            (r'\bpatient\b', 'patient'),
        ],
        # Formality inference from job zone
        'formality_base': {
            1: 'casual_to_standard',
            2: 'standard',
            3: 'standard_to_formal',
            4: 'formal',
            5: 'highly_formal',
        }
    }

    def classify(self, task: str, job_zone: int) -> TaskClassification:
        """Classify task based on text patterns and job zone."""
        ...
```

### 2.3 Stratified Sampling Strategy

To ensure diversity across all dimensions:

```python
class TaskSampler:
    """Stratified sampling across O*NET dimensions."""

    def sample(
        self,
        n_prompts: int,
        seed: int,
        stratification: dict
    ) -> list[SampledTask]:
        """
        Sample tasks with configurable stratification.

        Default stratification ensures even distribution across:
        - 5 job zones
        - 22 SOC major groups
        - 10 inferred writing categories
        - Core vs supplemental tasks
        """
        # Calculate target counts per stratum
        strata = self._build_strata(stratification)

        # Sample within each stratum
        samples = []
        for stratum in strata:
            stratum_tasks = self._get_stratum_tasks(stratum)
            n_sample = self._calculate_stratum_size(stratum, n_prompts)
            samples.extend(self._random_sample(stratum_tasks, n_sample, seed))

        return samples
```

### 2.4 NAICS Industry Mapping

Since O*NET lacks direct NAICS codes, we implement a mapping layer:

```python
class NAICSMapper:
    """Map O*NET occupations to NAICS industry codes."""

    # SOC-to-NAICS crosswalk based on BLS Occupation-Industry Matrix
    # This is embedded data derived from public BLS statistics
    SOC_NAICS_CROSSWALK = {
        '11': ['52', '54', '62', '31-33'],  # Management -> Finance, Prof Services, Healthcare, Manufacturing
        '13': ['52', '54', '55'],            # Business/Financial -> Finance, Prof Services, Mgmt Companies
        '15': ['54', '51'],                  # Computer -> Prof Services, Information
        # ... complete mapping for all 22 SOC major groups
    }

    def get_industries_for_occupation(
        self,
        soc_code: str
    ) -> list[NAICSIndustry]:
        """Get plausible NAICS industries for an occupation."""
        ...

    def sample_industry(
        self,
        soc_code: str,
        seed: int
    ) -> NAICSIndustry:
        """Sample a specific industry for an occupation."""
        ...
```

---

## 3. PROMPT GENERATION METHODOLOGY

### 3.1 Three-Phase Generation Architecture

The prompt generation follows the PROMPT.md specification with three distinct phases:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROMPT GENERATION PIPELINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PHASE 1: OFFLINE LLM GENERATION (Preprocessing)                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Input: O*NET task statements                             │   │
│  │  Output: Persona/context variations database              │   │
│  │  Models: Use evaluated models (Gemini, GPT, Claude)       │   │
│  │  Storage: personas.db with 50+ variations per task type   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│  PHASE 2: ALGORITHMIC COMBINATION (Deterministic)               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Input: Task + Persona DB + NAICS + Random seed          │   │
│  │  Output: Structured prompt with all dimensions            │   │
│  │  Operations: Sampling, matching, constraint satisfaction  │   │
│  │  Property: Fully reproducible with same seed             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│  PHASE 3: LLM ENRICHMENT (Context-Heavy Prompts)                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Input: Structured prompt needing additional context      │   │
│  │  Output: Fully realized prompt with attachments/context   │   │
│  │  Trigger: Task requires mock data, prior emails, etc.    │   │
│  │  Models: Same evaluated models for fairness              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Prompt Schema Definition

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import date

class FormalityLevel(str, Enum):
    HIGHLY_CASUAL = "highly_casual"
    CASUAL = "casual"
    STANDARD = "standard"
    FORMAL = "formal"
    HIGHLY_FORMAL = "highly_formal"

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    INITIAL = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"

class WriterPersona(BaseModel):
    """The person writing the content."""
    name: str
    email: Optional[str] = None
    age: int = Field(ge=18, le=75)
    generation: str  # GenZ, Millennial, GenX, Boomer
    job_title: str
    years_experience: int
    skill_level: str  # junior, mid, senior, executive
    english_variant: EnglishVariant = EnglishVariant.EN_US

class RecipientPersona(BaseModel):
    """The intended reader(s) of the content."""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship_to_writer: str  # manager, peer, report, external, unknown
    english_variant: EnglishVariant = EnglishVariant.EN_US
    prior_contact: bool = True  # Have they communicated before?

class CompanyContext(BaseModel):
    """Real company grounding for the scenario."""
    name: str
    industry_naics: str
    industry_name: str
    size_category: str  # startup, small, medium, large, enterprise
    employee_count_range: str
    public_private: str
    hq_location: str

class AttachmentContext(BaseModel):
    """Mock attachments or referenced content."""
    attachment_type: str  # report, email_thread, meeting_notes, resume, etc.
    summary: str
    key_points: list[str]

class TemporalContext(BaseModel):
    """Time-sensitive information."""
    current_date: date
    deadline: Optional[str] = None
    recent_event: Optional[str] = None
    quarter: Optional[str] = None

class WritingPrompt(BaseModel):
    """Complete prompt for writing evaluation."""
    # Identifiers
    prompt_id: str
    onet_task_id: str
    onet_soc_code: str
    occupation_title: str
    original_task: str

    # Core prompt
    prompt_text: str  # The actual instruction to the model

    # Context
    writer: WriterPersona
    recipients: list[RecipientPersona]
    company: CompanyContext

    # Communication characteristics
    formality: FormalityLevel
    urgency: str  # routine, time_sensitive, urgent, critical
    emotional_context: str  # routine, celebration, crisis, conflict, bad_news
    audience_size: str  # one_on_one, small_group, department, company_wide, public
    message_position: MessagePosition
    communication_medium: str  # email, memo, report, slack, letter, etc.

    # Additional context
    attachments: list[AttachmentContext] = []
    temporal_context: Optional[TemporalContext] = None
    prior_message: Optional[str] = None  # For reply scenarios
    tone_example: Optional[str] = None  # For tone matching

    # Constraints
    explicit_constraints: list[str] = []  # e.g., "under 100 words"
    competing_objectives: list[str] = []  # e.g., "be brief but comprehensive"

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    job_zone: int
    is_sensitive: bool = False
    sensitive_category: Optional[str] = None
    is_revision_task: bool = False
    is_ambiguous: bool = False

    # Generation metadata
    generation_phase: int  # 1, 2, or 3
    generation_model: Optional[str] = None  # Which model enriched this
    generation_seed: int
```

### 3.3 Phase 1: Persona Database Generation

Pre-generate diverse personas and contexts offline:

```python
class PersonaGenerator:
    """Generate diverse personas for prompt enrichment."""

    GENERATION_PROMPT = """
    Generate 10 diverse writer personas for the occupation: {occupation_title}

    Requirements:
    - Vary ages from 22-65
    - Include all generations (GenZ, Millennial, GenX, Boomer)
    - Vary skill levels (junior, mid, senior, executive)
    - Use realistic, demographically diverse names
    - Include realistic email addresses

    Return as JSON array with fields:
    - name, email, age, generation, job_title, years_experience, skill_level
    """

    async def generate_personas_for_occupation(
        self,
        occupation: str,
        model: str,
        n_personas: int = 10
    ) -> list[WriterPersona]:
        """Generate personas using specified model."""
        ...

    async def build_persona_database(
        self,
        occupations: list[str],
        models: list[str]
    ) -> PersonaDatabase:
        """Build complete persona database across all occupations."""
        # Use multiple models to avoid bias
        # Store in SQLite for fast lookup
        ...
```

### 3.4 Phase 2: Algorithmic Combination

Deterministic combination of elements:

```python
class PromptCombiner:
    """Algorithmically combine prompt elements."""

    def combine(
        self,
        task: SampledTask,
        persona_db: PersonaDatabase,
        company_db: CompanyDatabase,
        seed: int
    ) -> WritingPrompt:
        """Combine task with personas, company, and context."""
        rng = random.Random(seed)

        # Select writer persona matching occupation
        writer = self._select_writer(task, persona_db, rng)

        # Infer recipient from task
        recipients = self._infer_recipients(task, persona_db, rng)

        # Select real company in appropriate industry
        company = self._select_company(task, company_db, rng)

        # Determine formality from job zone and task
        formality = self._determine_formality(task, rng)

        # Infer communication medium
        medium = self._infer_medium(task)

        # Determine if needs Phase 3 enrichment
        needs_enrichment = self._needs_enrichment(task)

        return WritingPrompt(
            prompt_id=self._generate_id(task, seed),
            onet_task_id=task.task_id,
            # ... fill all fields
            generation_phase=2 if not needs_enrichment else 2,
            generation_seed=seed,
        )
```

### 3.5 Phase 3: LLM Enrichment

Add rich context for complex prompts:

```python
class PromptEnricher:
    """Enrich prompts with LLM-generated context."""

    ENRICHMENT_TRIGGERS = [
        'attached', 'report', 'meeting notes', 'prior email',
        'following up', 'per our conversation', 'resume', 'proposal'
    ]

    ENRICHMENT_PROMPT = """
    You are enriching a professional writing prompt with realistic context.

    Original task: {original_task}
    Writer: {writer_name}, {writer_title} at {company_name}
    Recipient: {recipient_name}, {recipient_title}

    This prompt needs: {enrichment_type}

    Generate realistic:
    {enrichment_instructions}

    Return as JSON with the enrichment content.
    """

    async def enrich(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> WritingPrompt:
        """Add LLM-generated context to prompt."""
        if self._needs_attachment(prompt):
            prompt = await self._add_attachment(prompt, model)

        if self._needs_prior_message(prompt):
            prompt = await self._add_prior_message(prompt, model)

        if self._needs_temporal_context(prompt):
            prompt = await self._add_temporal_context(prompt, model)

        prompt.generation_phase = 3
        prompt.generation_model = model
        return prompt
```

### 3.6 Company Database

Embed real company knowledge for grounding:

```python
class CompanyDatabase:
    """Database of real companies for prompt grounding."""

    # Structured by NAICS sector and size
    COMPANIES = {
        "52": {  # Finance and Insurance
            "enterprise": [
                Company("JPMorgan Chase", "52211", "Commercial Banking",
                        "enterprise", "250,000+", "public", "New York, NY"),
                Company("Goldman Sachs", "52311", "Investment Banking",
                        "enterprise", "40,000+", "public", "New York, NY"),
                # ... more
            ],
            "large": [...],
            "medium": [...],
            "small": [...],
            "startup": [...],
        },
        # ... all NAICS sectors
    }

    def get_company(
        self,
        naics_code: str,
        size: str,
        seed: int
    ) -> CompanyContext:
        """Get a real company matching criteria."""
        ...

---

## 4. EVALUATION FLOW AND JUDGING SYSTEM

### 4.1 Evaluation Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVALUATION PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐                                                          │
│  │ PROMPT BATCH   │ (Prompts loaded/generated)                              │
│  └───────┬────────┘                                                          │
│          │                                                                   │
│          ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ RESPONSE GENERATION (Parallel per model pair)                          │ │
│  │                                                                         │ │
│  │  For each prompt:                                                       │ │
│  │  ┌─────────────────┐    ┌─────────────────┐                            │ │
│  │  │ Gemini 3.0 Pro  │    │ Competitor      │   (Run in parallel)        │ │
│  │  │ or Flash        │    │ (GPT/Claude/    │                            │ │
│  │  │                 │    │  Grok/Kimi)     │                            │ │
│  │  └────────┬────────┘    └────────┬────────┘                            │ │
│  │           │                      │                                      │ │
│  │           └──────────┬───────────┘                                      │ │
│  │                      ▼                                                  │ │
│  │              ┌───────────────┐                                          │ │
│  │              │ Response Pair │                                          │ │
│  │              │ (A, B order   │                                          │ │
│  │              │  randomized)  │                                          │ │
│  │              └───────┬───────┘                                          │ │
│  └──────────────────────┼──────────────────────────────────────────────────┘ │
│                         │                                                    │
│                         ▼                                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ JUDGING (Best-of-5 × 3 Judges × 2 Personas)                            │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Judge 1: Claude Opus 4.5                                        │   │ │
│  │  │   Vote 1: [A/B/Tie] + Reasoning                                 │   │ │
│  │  │   Vote 2: [A/B/Tie] + Reasoning                                 │   │ │
│  │  │   Vote 3: [A/B/Tie] + Reasoning                                 │   │ │
│  │  │   Vote 4: [A/B/Tie] + Reasoning                                 │   │ │
│  │  │   Vote 5: [A/B/Tie] + Reasoning                                 │   │ │
│  │  │   → Judge 1 Majority: [A/B/Tie]                                 │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Judge 2: GPT-5.2                                                │   │ │
│  │  │   (Same 5-vote structure)                                       │   │ │
│  │  │   → Judge 2 Majority: [A/B/Tie]                                 │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ Judge 3: Gemini 3 Pro                                           │   │ │
│  │  │   (Same 5-vote structure)                                       │   │ │
│  │  │   → Judge 3 Majority: [A/B/Tie]                                 │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                         │ │
│  │  FINAL RESULT = Majority of Judge Majorities                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Model Configuration

```python
from enum import Enum
from pydantic import BaseModel

class ModelTier(str, Enum):
    PRO = "pro"
    FLASH = "flash"

class ModelConfig(BaseModel):
    """Configuration for a model."""
    name: str
    openrouter_id: str
    tier: ModelTier
    is_gemini: bool = False
    input_price_per_1m: float  # dollars per 1M tokens
    output_price_per_1m: float

# Pro-Tier Models
MODELS = {
    "gemini-3-pro": ModelConfig(
        name="Gemini 3.0 Pro",
        openrouter_id="google/gemini-3-pro",
        tier=ModelTier.PRO,
        is_gemini=True,
        input_price_per_1m=2.50,
        output_price_per_1m=10.00,
    ),
    "gpt-5.2-thinking": ModelConfig(
        name="GPT-5.2 Thinking",
        openrouter_id="openai/gpt-5.2-thinking",
        tier=ModelTier.PRO,
        input_price_per_1m=5.00,
        output_price_per_1m=15.00,
    ),
    "claude-opus-4.5": ModelConfig(
        name="Claude Opus 4.5",
        openrouter_id="anthropic/claude-opus-4-5",
        tier=ModelTier.PRO,
        input_price_per_1m=15.00,
        output_price_per_1m=75.00,
    ),
    "grok-4.1-thinking": ModelConfig(
        name="Grok-4.1 Thinking",
        openrouter_id="x-ai/grok-4.1-thinking",
        tier=ModelTier.PRO,
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
    ),
    "kimi-k2-thinking": ModelConfig(
        name="Kimi K2 Thinking",
        openrouter_id="moonshot/kimi-k2-thinking",
        tier=ModelTier.PRO,
        input_price_per_1m=2.00,
        output_price_per_1m=8.00,
    ),
    # Flash-Tier Models
    "gemini-3-flash": ModelConfig(
        name="Gemini 3.0 Flash",
        openrouter_id="google/gemini-3-flash",
        tier=ModelTier.FLASH,
        is_gemini=True,
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
    ),
    "gpt-4.1": ModelConfig(
        name="GPT-4.1",
        openrouter_id="openai/gpt-4.1",
        tier=ModelTier.FLASH,
        input_price_per_1m=2.00,
        output_price_per_1m=8.00,
    ),
    "claude-sonnet": ModelConfig(
        name="Claude Sonnet",
        openrouter_id="anthropic/claude-sonnet-4",
        tier=ModelTier.FLASH,
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
    ),
}

# Judge Models
JUDGE_MODELS = ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
```

### 4.3 Response Generation

```python
class ResponseGenerator:
    """Generate responses from models for evaluation."""

    async def generate_pair(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        competitor_model: str,
        seed: int
    ) -> ResponsePair:
        """Generate responses from both models."""

        # Run both models in parallel
        gemini_response, competitor_response = await asyncio.gather(
            self._generate_single(prompt, gemini_model),
            self._generate_single(prompt, competitor_model),
            return_exceptions=True
        )

        # Handle failures
        gemini_failed = isinstance(gemini_response, Exception)
        competitor_failed = isinstance(competitor_response, Exception)

        if gemini_failed and not competitor_failed:
            return ResponsePair(
                winner="competitor",
                reason="gemini_failure",
                gemini_response=None,
                competitor_response=competitor_response,
            )
        # ... similar for other failure cases

        # Randomize order (deterministic based on seed)
        rng = random.Random(seed)
        if rng.random() < 0.5:
            response_a, response_b = gemini_response, competitor_response
            order = "gemini_first"
        else:
            response_a, response_b = competitor_response, gemini_response
            order = "competitor_first"

        return ResponsePair(
            response_a=response_a,
            response_b=response_b,
            order=order,
            gemini_response=gemini_response,
            competitor_response=competitor_response,
        )

    async def _generate_single(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> ModelResponse:
        """Generate a single response with metadata tracking."""
        start_time = time.time()

        try:
            response = await self.client.generate(
                model=model,
                prompt=self._format_prompt(prompt),
                temperature=0.7,  # Some variation
            )

            return ModelResponse(
                model=model,
                content=response.content,
                latency=time.time() - start_time,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                word_count=len(response.content.split()),
                char_count=len(response.content),
                format_features=self._detect_format(response.content),
            )

        except RefusalError as e:
            return ModelResponse(
                model=model,
                content=None,
                refused=True,
                refusal_category=self._categorize_refusal(e),
                refusal_reason=str(e),
            )
```

### 4.4 Judging System

#### 4.4.1 Judge Personas

```python
WRITING_EXPERT_PROMPT = """
You are an expert writing professional evaluating two responses to the same writing task.
You have decades of experience in professional communication, technical writing, and business writing.

Evaluate based on:
- Quality of writing craft
- Appropriate length and tone
- Clarity and structure
- Professionalism
- Authenticity (does it sound human-written?)
- Avoidance of AI clichés and boilerplate

CRITICAL: The writing should be appropriate for the specific persona and context provided.
A GenZ startup employee writes differently than a Boomer executive at a Fortune 500.
"""

RECIPIENT_PROMPT = """
You are the intended recipient of this writing. Evaluate from your perspective as {recipient_name}, {recipient_title}.

Consider:
- Would this email/document achieve its purpose?
- Is it appropriate for your relationship with the sender?
- Would you find this effective and professional?
- Does it respect your time and give you what you need?
- Does it feel authentic, like a real person wrote it?
"""
```

#### 4.4.2 Judgment Schema

```python
class JudgmentVote(BaseModel):
    """A single judgment vote."""
    winner: str  # "A", "B", or "Tie"
    confidence: float  # 0-1
    reasoning: str
    criteria_scores: dict[str, int]  # Per-criterion scores 1-5
    detected_issues: list[str]  # e.g., "AI clichés detected"

class JudgeResult(BaseModel):
    """Results from a single judge (5 votes)."""
    judge_model: str
    judge_persona: str  # "writing_expert" or "recipient"
    votes: list[JudgmentVote]
    majority_winner: str
    vote_distribution: dict[str, int]  # {"A": 3, "B": 2, "Tie": 0}

class ComparisonResult(BaseModel):
    """Complete comparison result."""
    prompt_id: str
    gemini_model: str
    competitor_model: str
    response_order: str  # "gemini_first" or "competitor_first"

    judge_results: list[JudgeResult]  # 3 judges × 2 personas = 6

    # Aggregated results
    final_winner: str  # "gemini", "competitor", or "tie"
    judge_agreement: float  # Cohen's Kappa
    gemini_response: ModelResponse
    competitor_response: ModelResponse
```

#### 4.4.3 Judging Logic

```python
class JudgeEngine:
    """Execute judging with majority-of-majorities logic."""

    JUDGE_PROMPT_TEMPLATE = """
{persona_prompt}

## Writing Task
{prompt_text}

## Writer Context
{writer}: {writer_title} at {company}
{recipient}: {recipient_title}
Formality: {formality}
Communication type: {medium}

## Response A
{response_a}

## Response B
{response_b}

## Your Evaluation
Which response better accomplishes the writing task? Consider all criteria.
Respond with JSON:
{{
    "winner": "A" | "B" | "Tie",
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation...",
    "criteria_scores": {{
        "response_a": {{"quality": 1-5, "tone": 1-5, "clarity": 1-5, "authenticity": 1-5, "length_appropriateness": 1-5}},
        "response_b": {{"quality": 1-5, "tone": 1-5, "clarity": 1-5, "authenticity": 1-5, "length_appropriateness": 1-5}}
    }},
    "detected_issues": ["list of any AI clichés, boilerplate, or problems detected"]
}}
"""

    async def judge_comparison(
        self,
        prompt: WritingPrompt,
        response_pair: ResponsePair,
        judge_models: list[str],
        votes_per_judge: int = 5
    ) -> ComparisonResult:
        """Execute full judging pipeline."""

        judge_results = []

        for judge_model in judge_models:
            for persona in ["writing_expert", "recipient"]:
                # Generate N votes
                votes = await asyncio.gather(*[
                    self._single_vote(prompt, response_pair, judge_model, persona)
                    for _ in range(votes_per_judge)
                ])

                # Compute majority
                majority = self._compute_majority(votes)

                judge_results.append(JudgeResult(
                    judge_model=judge_model,
                    judge_persona=persona,
                    votes=votes,
                    majority_winner=majority,
                    vote_distribution=self._vote_distribution(votes),
                ))

        # Compute majority of majorities
        final_winner = self._majority_of_majorities(judge_results)

        # Map back to actual models
        if response_pair.order == "gemini_first":
            winner_model = "gemini" if final_winner == "A" else "competitor" if final_winner == "B" else "tie"
        else:
            winner_model = "competitor" if final_winner == "A" else "gemini" if final_winner == "B" else "tie"

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            final_winner=winner_model,
            judge_results=judge_results,
            judge_agreement=self._compute_agreement(judge_results),
            # ... other fields
        )

    def _compute_majority(self, votes: list[JudgmentVote]) -> str:
        """Compute majority winner from votes."""
        counts = {"A": 0, "B": 0, "Tie": 0}
        for vote in votes:
            counts[vote.winner] += 1

        if counts["A"] > counts["B"]:
            return "A"
        elif counts["B"] > counts["A"]:
            return "B"
        else:
            return "Tie"

    def _majority_of_majorities(self, results: list[JudgeResult]) -> str:
        """Compute final winner from judge majorities."""
        majorities = [r.majority_winner for r in results]
        a_wins = sum(1 for m in majorities if m == "A")
        b_wins = sum(1 for m in majorities if m == "B")

        if a_wins > b_wins:
            return "A"
        elif b_wins > a_wins:
            return "B"
        else:
            return "Tie"
```

### 4.5 Bias Detection and Mitigation

```python
class BiasDetector:
    """Detect and report on systematic biases."""

    def detect_position_bias(
        self,
        results: list[ComparisonResult]
    ) -> PositionBiasReport:
        """Detect if judges systematically prefer Response A or B."""
        a_wins = sum(1 for r in results if r.final_winner == "A")
        b_wins = sum(1 for r in results if r.final_winner == "B")
        total = a_wins + b_wins

        if total == 0:
            return PositionBiasReport(detected=False)

        a_rate = a_wins / total
        # Chi-square test for position bias
        chi2, p_value = stats.chisquare([a_wins, b_wins])

        return PositionBiasReport(
            detected=p_value < 0.05,
            a_win_rate=a_rate,
            b_win_rate=1 - a_rate,
            chi2=chi2,
            p_value=p_value,
        )

    def detect_length_bias(
        self,
        results: list[ComparisonResult]
    ) -> LengthBiasReport:
        """Detect if longer/shorter responses win more."""
        length_diffs = []
        wins = []

        for r in results:
            if r.final_winner in ["gemini", "competitor"]:
                winner_len = (
                    r.gemini_response.word_count
                    if r.final_winner == "gemini"
                    else r.competitor_response.word_count
                )
                loser_len = (
                    r.competitor_response.word_count
                    if r.final_winner == "gemini"
                    else r.gemini_response.word_count
                )
                length_diffs.append(winner_len - loser_len)

        # Correlation between length difference and winning
        # Positive = longer wins more, Negative = shorter wins more
        mean_diff = np.mean(length_diffs)
        t_stat, p_value = stats.ttest_1samp(length_diffs, 0)

        return LengthBiasReport(
            detected=p_value < 0.05,
            mean_length_advantage=mean_diff,
            direction="longer_wins" if mean_diff > 0 else "shorter_wins",
            t_statistic=t_stat,
            p_value=p_value,
        )
```

---

## 5. RESULTS STORAGE AND ANALYSIS

### 5.1 Database Schema

```sql
-- Core tables
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    config_json TEXT NOT NULL,
    preset_name TEXT,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed', 'interrupted'
    random_seed INTEGER NOT NULL,
    total_prompts INTEGER NOT NULL,
    completed_prompts INTEGER DEFAULT 0
);

CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    onet_task_id TEXT NOT NULL,
    onet_soc_code TEXT NOT NULL,
    occupation_title TEXT NOT NULL,
    job_zone INTEGER NOT NULL,
    prompt_json TEXT NOT NULL,  -- Full WritingPrompt as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexed metadata for fast filtering
    formality TEXT NOT NULL,
    industry_naics TEXT,
    audience_size TEXT,
    is_sensitive BOOLEAN DEFAULT FALSE,
    is_revision_task BOOLEAN DEFAULT FALSE
);

CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model TEXT NOT NULL,
    content TEXT,
    refused BOOLEAN DEFAULT FALSE,
    refusal_category TEXT,
    refusal_reason TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    word_count INTEGER,
    char_count INTEGER,
    format_features_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    gemini_response_id TEXT REFERENCES responses(response_id),
    competitor_response_id TEXT REFERENCES responses(response_id),
    response_order TEXT NOT NULL,  -- 'gemini_first' or 'competitor_first'
    final_winner TEXT NOT NULL,  -- 'gemini', 'competitor', 'tie'
    judge_agreement REAL,  -- Cohen's Kappa
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),
    judge_model TEXT NOT NULL,
    judge_persona TEXT NOT NULL,  -- 'writing_expert' or 'recipient'
    vote_number INTEGER NOT NULL,
    winner TEXT NOT NULL,  -- 'A', 'B', 'Tie'
    confidence REAL,
    reasoning TEXT,
    criteria_scores_json TEXT,
    detected_issues_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated views for fast queries
CREATE VIEW comparison_summary AS
SELECT
    c.comparison_id,
    c.prompt_id,
    c.gemini_model,
    c.competitor_model,
    c.final_winner,
    p.occupation_title,
    p.job_zone,
    p.formality,
    p.industry_naics,
    p.is_sensitive,
    gr.word_count as gemini_word_count,
    cr.word_count as competitor_word_count
FROM comparisons c
JOIN prompts p ON c.prompt_id = p.prompt_id
LEFT JOIN responses gr ON c.gemini_response_id = gr.response_id
LEFT JOIN responses cr ON c.competitor_response_id = cr.response_id;

-- Indexes for common queries
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onet_soc_code);
CREATE INDEX idx_prompts_formality ON prompts(formality);
CREATE INDEX idx_comparisons_winner ON comparisons(final_winner);
CREATE INDEX idx_comparisons_models ON comparisons(gemini_model, competitor_model);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
```

### 5.2 Checkpoint System

```python
class CheckpointManager:
    """Manage evaluation checkpoints for resumability."""

    CHECKPOINT_SCHEMA = {
        "run_id": str,
        "last_updated": str,  # ISO timestamp
        "phase": str,  # "generation", "judging", "analysis"
        "completed_prompts": list[str],  # Prompt IDs
        "in_progress": list[str],  # Currently processing
        "failed": list[dict],  # Failed with reason
        "stats": {
            "total": int,
            "completed": int,
            "failed": int,
            "remaining": int,
        }
    }

    async def save_checkpoint(self, state: EvalState) -> None:
        """Save checkpoint atomically."""
        checkpoint = {
            "run_id": state.run_id,
            "last_updated": datetime.utcnow().isoformat(),
            "phase": state.phase,
            "completed_prompts": list(state.completed),
            "in_progress": list(state.in_progress),
            "failed": [
                {"prompt_id": p, "reason": str(e)}
                for p, e in state.failed.items()
            ],
            "stats": {
                "total": state.total_prompts,
                "completed": len(state.completed),
                "failed": len(state.failed),
                "remaining": state.total_prompts - len(state.completed) - len(state.failed),
            }
        }

        # Atomic write
        temp_path = self.checkpoint_path.with_suffix('.tmp')
        async with aiofiles.open(temp_path, 'w') as f:
            await f.write(json.dumps(checkpoint, indent=2))
        temp_path.rename(self.checkpoint_path)

    async def load_checkpoint(self, run_dir: Path) -> Optional[EvalState]:
        """Load checkpoint for resumption."""
        checkpoint_path = run_dir / "checkpoint.json"
        if not checkpoint_path.exists():
            return None

        async with aiofiles.open(checkpoint_path) as f:
            data = json.loads(await f.read())

        return EvalState(
            run_id=data["run_id"],
            phase=data["phase"],
            completed=set(data["completed_prompts"]),
            in_progress=set(),  # Reset in-progress on resume
            failed={p["prompt_id"]: p["reason"] for p in data["failed"]},
            total_prompts=data["stats"]["total"],
        )
```

### 5.3 Results Directory Structure

```python
class ResultsOrganizer:
    """Organize evaluation results in timestamped directories."""

    def create_run_directory(self, run_id: str) -> Path:
        """Create and initialize a new run directory."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = self.results_base / f"eval_{timestamp}"
        run_dir.mkdir(parents=True)

        # Create subdirectories
        (run_dir / "prompts").mkdir()
        (run_dir / "responses" / "by_prompt").mkdir(parents=True)
        (run_dir / "responses" / "by_model").mkdir(parents=True)
        (run_dir / "judgments" / "raw").mkdir(parents=True)
        (run_dir / "judgments" / "aggregated").mkdir(parents=True)
        (run_dir / "analysis").mkdir()
        (run_dir / "reports" / "charts").mkdir(parents=True)
        (run_dir / "logs").mkdir()

        # Update latest symlink
        latest_link = self.results_base / "latest"
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(run_dir)

        return run_dir
```

### 5.4 Statistical Analysis

```python
class StatisticalAnalyzer:
    """Compute win rates, confidence intervals, and significance tests."""

    def compute_win_rate(
        self,
        results: list[ComparisonResult],
        target: str = "gemini"
    ) -> WinRateResult:
        """Compute win rate with confidence interval."""
        wins = sum(1 for r in results if r.final_winner == target)
        losses = sum(1 for r in results if r.final_winner != target and r.final_winner != "tie")
        ties = sum(1 for r in results if r.final_winner == "tie")
        total = wins + losses

        if total == 0:
            return WinRateResult(rate=0.5, ci_low=0, ci_high=1, n=0)

        rate = wins / total
        # Wilson score interval for proportions
        ci_low, ci_high = self._wilson_interval(wins, total, alpha=0.05)

        return WinRateResult(
            rate=rate,
            ci_low=ci_low,
            ci_high=ci_high,
            n=total,
            wins=wins,
            losses=losses,
            ties=ties,
        )

    def _wilson_interval(self, wins: int, n: int, alpha: float) -> tuple[float, float]:
        """Wilson score confidence interval."""
        if n == 0:
            return (0, 1)

        z = stats.norm.ppf(1 - alpha / 2)
        p = wins / n

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        spread = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator

        return (max(0, center - spread), min(1, center + spread))

    def compute_significance(
        self,
        results: list[ComparisonResult]
    ) -> SignificanceResult:
        """Test if win rate differs significantly from 50%."""
        wins = sum(1 for r in results if r.final_winner == "gemini")
        losses = sum(1 for r in results if r.final_winner == "competitor")
        total = wins + losses

        if total < 20:
            return SignificanceResult(
                significant=False,
                reason="insufficient_sample_size",
                n=total,
            )

        # Binomial test against 50%
        p_value = stats.binom_test(wins, total, 0.5, alternative='two-sided')

        return SignificanceResult(
            significant=p_value < 0.05,
            p_value=p_value,
            wins=wins,
            losses=losses,
            n=total,
            effect_size=(wins - losses) / total,  # Simple effect size
        )

    def compute_inter_rater_reliability(
        self,
        results: list[ComparisonResult]
    ) -> float:
        """Compute Cohen's Kappa for judge agreement."""
        # Flatten all judge decisions
        judge_decisions = {}  # {comparison_id: {judge_model: decision}}

        for r in results:
            comparison_decisions = {}
            for jr in r.judge_results:
                key = f"{jr.judge_model}_{jr.judge_persona}"
                comparison_decisions[key] = jr.majority_winner
            judge_decisions[r.comparison_id] = comparison_decisions

        # Compute pairwise kappa and average
        judges = list(next(iter(judge_decisions.values())).keys())
        kappas = []

        for i, j1 in enumerate(judges):
            for j2 in judges[i+1:]:
                ratings1 = [judge_decisions[cid][j1] for cid in judge_decisions]
                ratings2 = [judge_decisions[cid][j2] for cid in judge_decisions]
                kappa = self._cohens_kappa(ratings1, ratings2)
                kappas.append(kappa)

        return np.mean(kappas) if kappas else 0.0

    def _cohens_kappa(self, rater1: list, rater2: list) -> float:
        """Compute Cohen's Kappa between two raters."""
        labels = list(set(rater1 + rater2))
        matrix = np.zeros((len(labels), len(labels)))

        for r1, r2 in zip(rater1, rater2):
            i, j = labels.index(r1), labels.index(r2)
            matrix[i, j] += 1

        n = matrix.sum()
        po = np.diag(matrix).sum() / n  # Observed agreement
        pe = sum(matrix.sum(axis=0) * matrix.sum(axis=1)) / (n ** 2)  # Expected

        if pe == 1:
            return 1.0
        return (po - pe) / (1 - pe)
```

### 5.5 Weakness Analysis

```python
class WeaknessAnalyzer:
    """Identify specific areas where Gemini underperforms."""

    def analyze_by_dimension(
        self,
        results: list[ComparisonResult],
        prompts: dict[str, WritingPrompt]
    ) -> WeaknessReport:
        """Find dimensions where Gemini performs poorly."""

        dimensions = {
            "job_zone": {},
            "formality": {},
            "occupation_group": {},
            "industry": {},
            "audience_size": {},
            "emotional_context": {},
            "is_sensitive": {},
            "is_revision": {},
        }

        for r in results:
            prompt = prompts[r.prompt_id]

            # Group by each dimension
            for dim in dimensions:
                value = getattr(prompt, dim, None) or self._extract_dimension(prompt, dim)
                if value not in dimensions[dim]:
                    dimensions[dim][value] = []
                dimensions[dim][value].append(r)

        # Compute win rates per dimension value
        weaknesses = []
        for dim, groups in dimensions.items():
            for value, group_results in groups.items():
                if len(group_results) < 10:
                    continue  # Skip small samples

                win_rate = self.stat_analyzer.compute_win_rate(group_results)

                if win_rate.rate < 0.45:  # Potential weakness
                    weaknesses.append(Weakness(
                        dimension=dim,
                        value=value,
                        win_rate=win_rate.rate,
                        ci_low=win_rate.ci_low,
                        ci_high=win_rate.ci_high,
                        sample_size=len(group_results),
                        severity="high" if win_rate.rate < 0.35 else "medium",
                    ))

        # Sort by severity
        weaknesses.sort(key=lambda w: w.win_rate)

        return WeaknessReport(
            weaknesses=weaknesses,
            dimension_summaries=self._summarize_dimensions(dimensions),
        )
```

---

## 6. TUI IMPLEMENTATION

### 6.1 Progress Dashboard (Textual)

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

class EvalProgressApp(App):
    """Real-time evaluation progress dashboard."""

    CSS = """
    #progress-container {
        height: 6;
        border: solid green;
        margin: 1;
    }

    #model-pairs {
        height: 10;
        border: solid blue;
        margin: 1;
    }

    #current-batch {
        height: 12;
        border: solid cyan;
        margin: 1;
    }

    #statistics {
        height: 10;
        border: solid yellow;
        margin: 1;
    }

    #activity-log {
        height: 8;
        border: solid white;
        margin: 1;
    }
    """

    # Reactive state
    total_prompts = reactive(0)
    completed_prompts = reactive(0)
    current_prompt = reactive("")
    elapsed_time = reactive(0)
    eta = reactive(0)

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main"):
            # Overall progress
            with Container(id="progress-container"):
                yield Static("OVERALL PROGRESS", classes="section-title")
                yield ProgressBar(id="main-progress")
                yield Static(id="progress-stats")

            # Model pairs progress
            with Container(id="model-pairs"):
                yield Static("MODEL PAIRS", classes="section-title")
                yield DataTable(id="pairs-table")

            # Current batch details
            with Horizontal(id="current-batch"):
                with Vertical():
                    yield Static("CURRENT PROMPT", classes="section-title")
                    yield Static(id="current-prompt-details")
                with Vertical():
                    yield Static("RESPONSES", classes="section-title")
                    yield Static(id="response-status")
                with Vertical():
                    yield Static("JUDGING", classes="section-title")
                    yield Static(id="judging-status")

            # Live statistics
            with Horizontal(id="statistics"):
                with Vertical():
                    yield Static("WIN RATES", classes="section-title")
                    yield Static(id="win-rates")
                with Vertical():
                    yield Static("PERFORMANCE", classes="section-title")
                    yield Static(id="performance-stats")

            # Activity log
            with Container(id="activity-log"):
                yield Static("RECENT ACTIVITY", classes="section-title")
                yield Static(id="activity-entries")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the dashboard."""
        self._setup_tables()
        self._start_refresh_timer()

    def update_progress(self, state: EvalState) -> None:
        """Update dashboard with current state."""
        self.completed_prompts = len(state.completed)
        self.total_prompts = state.total_prompts

        # Update progress bar
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(total=self.total_prompts, progress=self.completed_prompts)

        # Update stats
        stats = self.query_one("#progress-stats", Static)
        stats.update(
            f"{self.completed_prompts}/{self.total_prompts} prompts "
            f"({100*self.completed_prompts/self.total_prompts:.1f}%) | "
            f"Elapsed: {self._format_time(self.elapsed_time)} | "
            f"ETA: {self._format_time(self.eta)}"
        )

    def add_activity(self, message: str, status: str = "info") -> None:
        """Add entry to activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = {"success": "[green]✓[/]", "warning": "[yellow]⚠[/]", "error": "[red]✗[/]"}
        entry = f"{timestamp}  {icon.get(status, '•')}  {message}"
        # Prepend to activity log (keep last N entries)
        ...
```

### 6.2 Results Viewer TUI

```python
class ResultsViewerApp(App):
    """Interactive results exploration TUI."""

    BINDINGS = [
        ("f", "filter", "Filter"),
        ("s", "sort", "Sort"),
        ("d", "details", "Details"),
        ("e", "export", "Export"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            # Left panel: filters
            with Vertical(id="filters", classes="sidebar"):
                yield Static("FILTERS")
                yield Select(id="occupation-filter", prompt="Occupation")
                yield Select(id="industry-filter", prompt="Industry")
                yield Select(id="winner-filter", prompt="Winner")
                yield Select(id="formality-filter", prompt="Formality")

            # Main panel: results table
            with Vertical(id="main-content"):
                yield DataTable(id="results-table")

            # Right panel: details
            with Vertical(id="details-panel", classes="sidebar"):
                yield Static("COMPARISON DETAILS")
                yield Static(id="prompt-display")
                yield Static(id="response-a-display")
                yield Static(id="response-b-display")
                yield Static(id="judgment-display")

        yield Footer()

    async def action_details(self) -> None:
        """Show detailed view of selected comparison."""
        table = self.query_one("#results-table", DataTable)
        row_key = table.cursor_row

        if row_key is not None:
            comparison = await self.db.get_comparison(row_key)
            self._show_comparison_details(comparison)

    def _show_comparison_details(self, comparison: ComparisonResult) -> None:
        """Display full comparison with responses and judgments."""
        # Show prompt
        prompt_panel = self.query_one("#prompt-display", Static)
        prompt_panel.update(Panel(
            comparison.prompt.prompt_text,
            title="Writing Task",
            border_style="blue"
        ))

        # Show responses side-by-side
        response_a = self.query_one("#response-a-display", Static)
        response_a.update(Panel(
            comparison.response_a.content or "[red]REFUSED[/]",
            title=f"Response A ({comparison.response_order})",
            border_style="green" if comparison.final_winner == "A" else "dim"
        ))

        # Show judgments
        judgment_panel = self.query_one("#judgment-display", Static)
        judgment_text = self._format_judgments(comparison.judge_results)
        judgment_panel.update(Panel(judgment_text, title="Judgments"))
```

---

## 7. ROBUSTNESS REQUIREMENTS

### 7.1 API Retry and Rate Limiting

```python
class OpenRouterClient:
    """Robust OpenRouter API client with retry and rate limiting."""

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        self.api_key = api_key
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.rate_limiters: dict[str, asyncio.Semaphore] = {}
        self.client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,
        )

    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate with exponential backoff and jitter."""

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # Acquire rate limit permit
                await self._acquire_rate_limit(model)

                response = await self.client.post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                )

                if response.status_code == 429:
                    # Rate limited - extract retry-after
                    retry_after = int(response.headers.get("Retry-After", 5))
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                return GenerationResult(
                    content=data["choices"][0]["message"]["content"],
                    usage=Usage(
                        prompt_tokens=data["usage"]["prompt_tokens"],
                        completion_tokens=data["usage"]["completion_tokens"],
                    ),
                    model=model,
                )

            except httpx.TimeoutException as e:
                last_error = e
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

            except httpx.HTTPStatusError as e:
                if e.response.status_code in [500, 502, 503, 504]:
                    last_error = e
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise RetryExhaustedError(
            f"Failed after {self.max_retries} retries",
            last_error=last_error
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = min(
            self.base_delay * (2 ** attempt),
            self.max_delay
        )
        # Add jitter: 0.5x to 1.5x
        jitter = 0.5 + random.random()
        return delay * jitter
```

### 7.2 Graceful Shutdown

```python
class EvalRunner:
    """Main evaluation runner with graceful shutdown."""

    def __init__(self):
        self.shutdown_requested = False
        self.current_batch: list[str] = []

    async def run(self, config: EvalConfig) -> None:
        """Run evaluation with interrupt handling."""

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._request_shutdown())
            )

        try:
            await self._run_evaluation(config)
        finally:
            await self._cleanup()

    async def _request_shutdown(self) -> None:
        """Handle shutdown request."""
        if self.shutdown_requested:
            # Second interrupt - force exit
            raise KeyboardInterrupt("Force shutdown")

        self.shutdown_requested = True
        print("\n[yellow]Shutdown requested. Finishing current batch...[/]")
        print("[dim]Press Ctrl+C again to force quit (may lose data)[/]")

    async def _run_evaluation(self, config: EvalConfig) -> None:
        """Core evaluation loop."""
        state = await self.checkpoint.load_or_create(config)

        prompts = await self._load_prompts(config)
        remaining = [p for p in prompts if p.prompt_id not in state.completed]

        for batch in self._batch(remaining, config.batch_size):
            if self.shutdown_requested:
                break

            self.current_batch = [p.prompt_id for p in batch]

            # Process batch
            results = await self._process_batch(batch, config)

            # Save results
            await self.storage.save_results(results)

            # Update checkpoint
            state.completed.update(self.current_batch)
            await self.checkpoint.save(state)

            self.current_batch = []

        if not self.shutdown_requested:
            # Run analysis
            await self._run_analysis(state)
```

### 7.3 Failure Tracking

```python
class FailureTracker:
    """Track and report on failures during evaluation."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.failures: list[FailureRecord] = []

    async def record_failure(
        self,
        prompt_id: str,
        model: str,
        error: Exception,
        phase: str,  # "generation", "judging"
        context: dict = None,
    ) -> None:
        """Record a failure with full context."""
        record = FailureRecord(
            timestamp=datetime.utcnow().isoformat(),
            prompt_id=prompt_id,
            model=model,
            phase=phase,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            context=context or {},
        )

        self.failures.append(record)

        # Append to log file
        async with aiofiles.open(self.log_path, 'a') as f:
            await f.write(json.dumps(record.dict()) + '\n')

    def generate_report(self) -> FailureReport:
        """Generate summary report of all failures."""
        by_model = defaultdict(list)
        by_phase = defaultdict(list)
        by_error_type = defaultdict(list)

        for f in self.failures:
            by_model[f.model].append(f)
            by_phase[f.phase].append(f)
            by_error_type[f.error_type].append(f)

        return FailureReport(
            total_failures=len(self.failures),
            by_model={k: len(v) for k, v in by_model.items()},
            by_phase={k: len(v) for k, v in by_phase.items()},
            by_error_type={k: len(v) for k, v in by_error_type.items()},
            samples=self.failures[:10],  # First 10 for inspection
        )
```

---

## 8. CLI AND CONFIGURATION

### 8.1 CLI Interface

```python
import typer
from typing import Optional

app = typer.Typer(name="gemini-eval", help="Gemini Writing Evaluation Framework")

@app.command()
def run(
    preset: Optional[int] = typer.Option(None, help="Preset level 1-10"),
    prompts: Optional[int] = typer.Option(None, help="Number of prompts"),
    models: Optional[str] = typer.Option(None, help="Comma-separated model pairs"),
    judges: Optional[str] = typer.Option(None, help="Comma-separated judge models"),
    votes: int = typer.Option(5, help="Votes per judge"),
    occupations: Optional[str] = typer.Option(None, help="O*NET occupation filter"),
    industries: Optional[str] = typer.Option(None, help="NAICS industry filter"),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility"),
    dry_run: bool = typer.Option(False, help="Show estimate without running"),
    resume: Optional[str] = typer.Option(None, help="Resume from run directory"),
):
    """Run writing evaluation."""
    config = build_config(
        preset=preset,
        prompts=prompts,
        models=models,
        judges=judges,
        votes=votes,
        occupations=occupations,
        industries=industries,
        seed=seed,
    )

    if dry_run:
        show_estimate(config)
        return

    if resume:
        asyncio.run(resume_evaluation(resume))
    else:
        asyncio.run(run_evaluation(config))


@app.command()
def view(
    run_dir: str = typer.Argument(..., help="Results directory to view"),
):
    """View evaluation results in TUI."""
    app = ResultsViewerApp(run_dir)
    app.run()


@app.command()
def compare(
    run_dirs: list[str] = typer.Argument(..., help="Run directories to compare"),
    output: Optional[str] = typer.Option(None, help="Output comparison report"),
):
    """Compare results across multiple runs."""
    asyncio.run(compare_runs(run_dirs, output))


@app.command()
def report(
    run_dir: str = typer.Argument(..., help="Results directory"),
    output: Optional[str] = typer.Option(None, help="Output PDF path"),
    format: str = typer.Option("pdf", help="Output format: pdf, html, md"),
):
    """Generate analysis report."""
    asyncio.run(generate_report(run_dir, output, format))
```

### 8.2 Preset Configurations

```python
PRESETS = {
    1: EvalPreset(
        name="Sanity Check",
        prompts=5,
        model_pairs=[("gemini-3-pro", "gpt-5.2-thinking")],
        judge_models=["claude-opus-4.5"],
        votes_per_judge=1,
        use_both_personas=False,
        estimated_cost=1.0,
        estimated_time_minutes=2,
        description="Does the system work?",
    ),
    2: EvalPreset(
        name="Smoke Test",
        prompts=20,
        model_pairs=[("gemini-3-pro", "gpt-5.2-thinking")],
        judge_models=["claude-opus-4.5"],
        votes_per_judge=3,
        use_both_personas=True,
        estimated_cost=5.0,
        estimated_time_minutes=5,
        description="Quick functionality test",
    ),
    3: EvalPreset(
        name="Dev Iteration",
        prompts=50,
        model_pairs=[
            ("gemini-3-pro", "gpt-5.2-thinking"),
            ("gemini-3-pro", "claude-opus-4.5"),
        ],
        judge_models=["claude-opus-4.5", "gpt-5.2-thinking"],
        votes_per_judge=3,
        use_both_personas=True,
        estimated_cost=25.0,
        estimated_time_minutes=15,
        description="Development/debugging",
    ),
    # ... presets 4-10
    10: EvalPreset(
        name="Full Kaboodle",
        prompts=10000,
        model_pairs="all",
        judge_models=["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"],
        votes_per_judge=5,
        use_both_personas=True,
        estimated_cost=12000.0,
        estimated_time_minutes=48*60,
        description="Maximum coverage",
    ),
}
```

### 8.3 Cost Estimation

```python
class CostEstimator:
    """Estimate costs for evaluation runs."""

    def estimate(self, config: EvalConfig) -> CostEstimate:
        """Compute detailed cost estimate."""

        # Response generation costs
        response_costs = {}
        for gemini, competitor in config.model_pairs:
            gemini_model = MODELS[gemini]
            competitor_model = MODELS[competitor]

            # Estimate tokens (based on prompt complexity)
            avg_input = 800  # ~800 tokens average prompt
            avg_output = 400  # ~400 tokens average response

            per_prompt = (
                (gemini_model.input_price_per_1m * avg_input / 1_000_000) +
                (gemini_model.output_price_per_1m * avg_output / 1_000_000) +
                (competitor_model.input_price_per_1m * avg_input / 1_000_000) +
                (competitor_model.output_price_per_1m * avg_output / 1_000_000)
            )

            response_costs[f"{gemini} vs {competitor}"] = per_prompt * config.prompts

        total_response_cost = sum(response_costs.values())

        # Judging costs
        judge_calls_per_comparison = (
            len(config.judge_models) *
            config.votes_per_judge *
            (2 if config.use_both_personas else 1)
        )

        total_judge_calls = (
            config.prompts *
            len(config.model_pairs) *
            judge_calls_per_comparison
        )

        # Judge token estimates
        avg_judge_input = 1500  # Two responses + prompt
        avg_judge_output = 200  # Judgment

        judge_cost_per_call = sum(
            (MODELS[j].input_price_per_1m * avg_judge_input / 1_000_000) +
            (MODELS[j].output_price_per_1m * avg_judge_output / 1_000_000)
            for j in config.judge_models
        ) / len(config.judge_models)

        total_judge_cost = total_judge_calls * judge_cost_per_call

        return CostEstimate(
            response_generation=total_response_cost,
            judging=total_judge_cost,
            total=total_response_cost + total_judge_cost,
            total_api_calls=len(config.model_pairs) * config.prompts * 2 + total_judge_calls,
            breakdown={
                "response_by_pair": response_costs,
                "judge_calls": total_judge_calls,
            }
        )
```

---

## 9. REPORT GENERATION

### 9.1 PDF Report Structure

```python
class ReportGenerator:
    """Generate comprehensive PDF analysis reports."""

    SECTIONS = [
        "executive_summary",
        "methodology",
        "overall_results",
        "model_pair_analysis",
        "dimension_analysis",
        "weakness_identification",
        "bias_analysis",
        "statistical_appendix",
    ]

    async def generate(
        self,
        run_dir: Path,
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate full PDF report."""

        results = await self.load_results(run_dir)
        analysis = await self.analyzer.analyze(results)

        # Build report sections
        doc = PDFDocument()

        # Title page
        doc.add_title_page(
            title="Gemini Writing Evaluation Report",
            subtitle=f"Run: {run_dir.name}",
            date=datetime.now(),
        )

        # Executive summary
        doc.add_section("Executive Summary")
        doc.add_paragraph(self._generate_executive_summary(analysis))
        doc.add_chart(self._create_summary_chart(analysis))

        # Overall results
        doc.add_section("Overall Results")
        doc.add_table(self._create_win_rate_table(analysis))
        doc.add_chart(self._create_win_rate_chart(analysis))

        # Model pair deep dives
        for pair in analysis.model_pairs:
            doc.add_subsection(f"{pair.gemini} vs {pair.competitor}")
            doc.add_table(self._create_pair_table(pair))
            doc.add_chart(self._create_pair_chart(pair))

        # Dimension analysis
        doc.add_section("Analysis by Dimension")
        for dim in ["job_zone", "formality", "occupation", "industry"]:
            doc.add_subsection(dim.replace("_", " ").title())
            doc.add_chart(self._create_dimension_chart(analysis, dim))
            doc.add_table(self._create_dimension_table(analysis, dim))

        # Weakness identification
        doc.add_section("Identified Weaknesses")
        doc.add_paragraph(self._generate_weakness_narrative(analysis.weaknesses))
        doc.add_table(self._create_weakness_table(analysis.weaknesses))

        # Bias analysis
        doc.add_section("Bias Analysis")
        doc.add_paragraph(self._generate_bias_narrative(analysis.biases))

        # Statistical appendix
        doc.add_section("Statistical Appendix")
        doc.add_paragraph("Detailed statistical tests and confidence intervals.")
        doc.add_table(self._create_stats_table(analysis))

        # Save
        output = output_path or run_dir / "reports" / "report.pdf"
        doc.save(output)

        return output
```

### 9.2 Visualization Generation

```python
class ChartGenerator:
    """Generate charts for analysis and reports."""

    def create_win_rate_heatmap(
        self,
        analysis: Analysis,
        x_dimension: str,
        y_dimension: str,
    ) -> go.Figure:
        """Create heatmap of win rates across two dimensions."""
        # Pivot data into matrix
        matrix = []
        x_labels = []
        y_labels = []

        for x_val in analysis.get_dimension_values(x_dimension):
            row = []
            x_labels.append(x_val)
            for y_val in analysis.get_dimension_values(y_dimension):
                win_rate = analysis.get_win_rate(x_dimension=x_val, y_dimension=y_val)
                row.append(win_rate.rate if win_rate else None)
            matrix.append(row)

        if not y_labels:
            y_labels = list(analysis.get_dimension_values(y_dimension))

        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=y_labels,
            y=x_labels,
            colorscale=[
                [0, 'rgb(255,0,0)'],     # Red for <50%
                [0.5, 'rgb(255,255,255)'],  # White for 50%
                [1, 'rgb(0,255,0)'],     # Green for >50%
            ],
            zmin=0.3,
            zmax=0.7,
            text=[[f"{v:.1%}" if v else "" for v in row] for row in matrix],
            texttemplate="%{text}",
            textfont={"size": 10},
            hoverongaps=False,
        ))

        fig.update_layout(
            title=f"Win Rate by {x_dimension} and {y_dimension}",
            xaxis_title=y_dimension,
            yaxis_title=x_dimension,
        )

        return fig

    def create_confidence_interval_chart(
        self,
        win_rates: list[WinRateResult],
        labels: list[str],
    ) -> go.Figure:
        """Create chart with win rates and confidence intervals."""
        fig = go.Figure()

        # Add error bars
        fig.add_trace(go.Scatter(
            x=labels,
            y=[wr.rate for wr in win_rates],
            error_y=dict(
                type='data',
                symmetric=False,
                array=[wr.ci_high - wr.rate for wr in win_rates],
                arrayminus=[wr.rate - wr.ci_low for wr in win_rates],
            ),
            mode='markers',
            marker=dict(size=12),
            name='Win Rate',
        ))

        # Add 50% reference line
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray")

        fig.update_layout(
            title="Win Rates with 95% Confidence Intervals",
            yaxis_title="Win Rate",
            yaxis=dict(range=[0.3, 0.7]),
        )

        return fig
```

---

## 10. IMPLEMENTATION TIMELINE

### Phase 1: Foundation (Week 1-2)
- [ ] Project setup (pyproject.toml, dependencies)
- [ ] O*NET data extraction and task classification
- [ ] Basic prompt schema and generation (Phase 1-2)
- [ ] OpenRouter client with retry logic
- [ ] SQLite database schema

### Phase 2: Core Evaluation (Week 3-4)
- [ ] Response generation pipeline
- [ ] Judging system with dual personas
- [ ] Majority-of-majorities voting
- [ ] Checkpoint and resume system
- [ ] Basic CLI interface

### Phase 3: Analysis and TUI (Week 5-6)
- [ ] Statistical analysis (win rates, CI, significance)
- [ ] Bias detection
- [ ] Weakness analysis
- [ ] Progress dashboard TUI
- [ ] Results viewer TUI

### Phase 4: Reports and Polish (Week 7-8)
- [ ] PDF report generation
- [ ] Chart visualizations
- [ ] Cross-run comparison
- [ ] Documentation
- [ ] Testing and edge cases

---

## 11. RISK MITIGATION

| Risk | Mitigation |
|------|------------|
| OpenRouter rate limits | Adaptive rate limiting with exponential backoff |
| Model API changes | Abstract model interface, easy to update |
| Cost overruns | Live cost tracking, confirmation before expensive runs |
| Judge model bias | Multiple judges, position randomization, bias detection |
| Long-running interruptions | Checkpoint every batch, graceful shutdown |
| Prompt generation bias | Use evaluated models for generation, track metadata |
| Statistical noise | Wilson confidence intervals, significance testing |
| O*NET data changes | Version lock (30.1), store used version in run |

---

## 12. SUCCESS CRITERIA

1. **Functional**: Run complete evaluation at all 10 preset levels
2. **Robust**: Resume from any interruption point with no data loss
3. **Accurate**: Inter-judge agreement (Kappa) > 0.6
4. **Trustworthy**: Position bias < 5%, detected and reported
5. **Actionable**: Identify top 10 specific weaknesses with statistical significance
6. **Usable**: TUI enables inspection of any individual comparison
7. **Documented**: PDF report suitable for executive presentation
