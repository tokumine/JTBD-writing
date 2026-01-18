# Gemini Writing Evaluation Framework - Implementation Plan (Draft 1)

## Executive Summary

This implementation plan details the architecture and methodology for building a comprehensive writing evaluation framework that compares Gemini 3.0 Pro and Flash against competing frontier LLMs on realistic professional writing tasks derived from O*NET occupational data. The framework uses OpenRouter API as a unified interface to all models and produces statistically robust side-by-side comparisons with detailed analysis reporting.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GEMINI WRITING EVAL FRAMEWORK                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   CLI/TUI    │  │   Config     │  │   Storage    │  │   Reports    │    │
│  │   Interface  │  │   Manager    │  │   Layer      │  │   Generator  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ┌──────▼─────────────────▼─────────────────▼─────────────────▼──────┐     │
│  │                        ORCHESTRATION ENGINE                        │     │
│  │  ┌─────────────────────────────────────────────────────────────┐  │     │
│  │  │  Checkpoint Manager  │  Rate Limiter  │  Error Handler      │  │     │
│  │  └─────────────────────────────────────────────────────────────┘  │     │
│  └───────────────────────────────┬───────────────────────────────────┘     │
│                                  │                                          │
│  ┌───────────────────────────────▼───────────────────────────────────┐     │
│  │                       EVALUATION PIPELINE                          │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │     │
│  │  │  Prompt     │  │  Response   │  │  Judgment   │                │     │
│  │  │  Generator  │─▶│  Collector  │─▶│  Aggregator │                │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │     │
│  └───────────────────────────────┬───────────────────────────────────┘     │
│                                  │                                          │
│  ┌───────────────────────────────▼───────────────────────────────────┐     │
│  │                         DATA LAYER                                 │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │     │
│  │  │  O*NET DB   │  │  Company    │  │  Name       │                │     │
│  │  │  Extractor  │  │  Database   │  │  Generator  │                │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                      OPENROUTER API CLIENT                         │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │     │
│  │  │  Async      │  │  Retry      │  │  Token      │                │     │
│  │  │  HTTP Pool  │  │  Logic      │  │  Counter    │                │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async support, rich ecosystem |
| HTTP Client | httpx | Async-first, connection pooling |
| Validation | pydantic v2 | Type-safe schemas, JSON serialization |
| Database | SQLite | Zero config, portable, SQL support |
| TUI | textual/rich | Modern terminal UI framework |
| Charts | plotly | Interactive, PDF export support |
| PDF Generation | reportlab + plotly | Publication-quality output |
| CLI | typer | Type hints, auto-help |
| Config | TOML + pydantic | Human-readable, validated |

### 1.3 Directory Structure

```
gemini-writing-eval/
├── pyproject.toml                 # Project dependencies and metadata
├── README.md                      # Project documentation
├── .env.example                   # Environment variable template
│
├── src/
│   ├── __init__.py
│   │
│   ├── cli.py                     # Main CLI entry point (typer)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Pydantic settings model
│   │   ├── presets.py             # 10 preset configurations
│   │   └── cost_estimator.py      # Token/cost estimation
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py      # O*NET database queries
│   │   ├── naics_mapper.py        # Industry code mapping
│   │   ├── company_database.py    # Real company data
│   │   └── name_generator.py      # Realistic name generation
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Prompt data models
│   │   ├── generator.py           # Three-phase prompt generation
│   │   ├── enrichment.py          # LLM enrichment logic
│   │   └── templates.py           # Prompt templates
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py   # OpenRouter API client
│   │   ├── rate_limiter.py        # Token bucket rate limiting
│   │   ├── retry_handler.py       # Exponential backoff logic
│   │   └── token_counter.py       # Token estimation
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py              # Main evaluation orchestrator
│   │   ├── response_collector.py  # Model response collection
│   │   ├── judge.py               # Judge prompt construction
│   │   ├── vote_aggregator.py     # Majority-of-majorities logic
│   │   └── schemas.py             # Evaluation data models
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite operations
│   │   ├── checkpoint.py          # Resume/checkpoint logic
│   │   └── exporter.py            # CSV/JSON export
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # Win rates, confidence intervals
│   │   ├── bias_detection.py      # Systematic bias analysis
│   │   └── weakness_finder.py     # Gemini weakness identification
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── progress.py            # Live progress dashboard
│   │   ├── viewer.py              # Results viewer
│   │   └── components.py          # Reusable UI components
│   │
│   └── reports/
│       ├── __init__.py
│       ├── charts.py              # Plotly chart generation
│       └── pdf_generator.py       # Final PDF report
│
├── db/
│   ├── onet.db                    # O*NET 30.1 database
│   └── ONET_WRITING_REFERENCE.md  # O*NET usage guide
│
├── results/                       # Eval run outputs (gitignored)
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py                # Pytest fixtures
    ├── unit/                      # Unit tests
    └── integration/               # Integration tests
```

---

## 2. Data Models and Schemas

### 2.1 Core Prompt Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class Formality(str, Enum):
    VERY_CASUAL = "very_casual"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    VERY_FORMAL = "very_formal"

class Generation(str, Enum):
    GEN_Z = "gen_z"         # Born 1997-2012
    GEN_A = "gen_a"         # Born 2013+
    MILLENNIAL = "millennial"  # Born 1981-1996
    GEN_X = "gen_x"         # Born 1965-1980
    BOOMER = "boomer"       # Born 1946-1964

class WriterPersona(BaseModel):
    name: str                              # e.g., "Sarah Chen"
    email: Optional[str] = None            # e.g., "sarah.chen@acme.com"
    role: str                              # e.g., "VP of Marketing"
    age: int                               # Specific age
    generation: Generation                 # Generational cohort
    skill_level: Literal[1, 2, 3, 4, 5]   # 1=novice, 5=expert
    english_variant: EnglishVariant = EnglishVariant.EN_US

class RecipientPersona(BaseModel):
    name: str
    email: Optional[str] = None
    role: str
    relationship: str                      # e.g., "direct report", "client", "stranger"
    english_variant: EnglishVariant = EnglishVariant.EN_US

class CompanyContext(BaseModel):
    name: str                              # Real company name
    industry: str                          # Industry description
    naics_code: str                        # 2-6 digit NAICS
    size_category: Literal["startup", "small", "mid_market", "large", "enterprise"]
    employee_count: Optional[int] = None
    public_private: Literal["public", "private"]
    hq_location: str                       # City, Country

class TemporalContext(BaseModel):
    current_date: Optional[str] = None     # e.g., "January 6, 2026"
    deadline: Optional[str] = None         # e.g., "Friday, January 10th"
    reference_event: Optional[str] = None  # e.g., "last week's quarterly review"

class Attachment(BaseModel):
    type: str                              # "report", "email_thread", "resume", etc.
    summary: str                           # Content summary for context
    key_points: list[str]                  # Bullet points of relevant info

class InstructionConstraint(BaseModel):
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    description: str                       # Human-readable constraint
    testable_criteria: str                 # How to verify compliance

class WritingPrompt(BaseModel):
    prompt_id: str                         # Unique identifier

    # O*NET Source
    onet_task_id: str                      # Original task statement ID
    onet_occupation_code: str              # SOC code
    onet_occupation_title: str
    onet_task_statement: str               # Original task text
    job_zone: Literal[1, 2, 3, 4, 5]

    # Generated Context
    writer: WriterPersona
    recipient: RecipientPersona
    company: CompanyContext

    # Task Details
    writing_task: str                      # Full enriched prompt
    formality: Formality
    urgency: Literal["low", "medium", "high", "critical"]
    audience_size: Literal["one_on_one", "small_group", "department", "company_wide", "public"]
    emotional_context: str                 # e.g., "routine", "celebration", "crisis"
    message_position: Literal["initial", "reply", "follow_up"]

    # Optional Enhancements
    temporal: Optional[TemporalContext] = None
    attachments: list[Attachment] = []
    prior_message: Optional[str] = None    # For reply-to scenarios
    tone_example: Optional[str] = None     # For tone-matching tasks
    cc_recipients: list[RecipientPersona] = []

    # Constraints
    constraints: list[InstructionConstraint] = []
    competing_objectives: list[str] = []   # e.g., ["be brief", "be comprehensive"]

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    communication_channel: Optional[str] = None  # Inferred: email, memo, slack, etc.
    is_revision_task: bool = False
    original_text_to_revise: Optional[str] = None
    is_ambiguous: bool = False             # Deliberately vague prompt
    sensitive_topic: Optional[str] = None  # HR, legal, bad_news, confidential, conflict
    writing_category: str                  # From ONET_WRITING_REFERENCE categories

    # Generation Metadata
    generation_phase: Literal[1, 2, 3]     # Which phase generated this
    enrichment_model: Optional[str] = None # Model used for LLM enrichment
    random_seed: int                       # For reproducibility
    created_at: datetime
```

### 2.2 Response Schema

```python
class ModelResponse(BaseModel):
    response_id: str
    prompt_id: str
    model_id: str                          # OpenRouter model identifier
    model_name: str                        # Human-readable name

    # Response Content
    response_text: str

    # Metadata
    response_time_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int

    # Detected Patterns
    word_count: int
    char_count: int
    has_greeting: bool
    has_signoff: bool
    uses_bullet_points: bool
    uses_headers: bool
    paragraph_count: int

    # Status
    status: Literal["success", "refused", "error", "timeout", "off_topic"]
    refusal_category: Optional[str] = None  # safety, capability, misunderstanding, incomplete, off_topic
    error_message: Optional[str] = None

    created_at: datetime

class ComparisonPair(BaseModel):
    comparison_id: str
    prompt_id: str

    # Responses
    gemini_response_id: str
    competitor_response_id: str
    competitor_model: str

    # Randomized Order
    response_a_id: str                     # Shuffled for position bias
    response_b_id: str
    gemini_position: Literal["A", "B"]
    shuffle_seed: int

### 2.3 Judgment Schema

```python
class JudgeVote(BaseModel):
    vote_id: str
    comparison_id: str
    judge_model: str                       # claude-opus-4-5, gpt-5.2, gemini-3-pro
    judge_persona: Literal["writing_expert", "recipient"]
    vote_number: int                       # 1-5 within best-of-5

    # Vote Result
    winner: Literal["A", "B", "tie"]
    winner_model: Optional[str] = None     # Resolved after position reveal

    # Rubric Scores (1-5 scale)
    scores_response_a: dict[str, int]      # {criterion: score}
    scores_response_b: dict[str, int]

    # Reasoning
    reasoning: str                         # Judge's explanation

    # Metadata
    response_time_ms: int
    input_tokens: int
    output_tokens: int
    created_at: datetime

class JudgeAggregation(BaseModel):
    aggregation_id: str
    comparison_id: str

    # Per-Judge Majority
    claude_majority: Literal["gemini", "competitor", "tie"]
    gpt_majority: Literal["gemini", "competitor", "tie"]
    gemini_judge_majority: Literal["gemini", "competitor", "tie"]

    # Final Result (majority of majorities)
    final_winner: Literal["gemini", "competitor", "tie"]

    # Vote Counts
    gemini_wins: int
    competitor_wins: int
    ties: int

    # Agreement Metrics
    inter_judge_agreement: float           # Cohen's Kappa
    position_bias_detected: bool
```

### 2.4 Evaluation Rubric Schema

```python
class EvaluationCriterion(BaseModel):
    name: str
    weight: float                          # 0.0-1.0, all weights sum to 1.0
    description: str
    scoring_guide: dict[int, str]          # {1: "Poor", 2: "Below Avg", ..., 5: "Excellent"}

EVALUATION_RUBRIC = [
    EvaluationCriterion(
        name="writing_quality",
        weight=0.15,
        description="Overall quality of prose, grammar, syntax, and style",
        scoring_guide={
            1: "Poor grammar, unclear prose",
            2: "Some errors, awkward phrasing",
            3: "Competent writing, minor issues",
            4: "Strong writing, polished prose",
            5: "Exceptional quality, publishable"
        }
    ),
    EvaluationCriterion(
        name="length_appropriateness",
        weight=0.10,
        description="Is the response the right length for this specific task?",
        scoring_guide={
            1: "Far too long/short for task",
            2: "Somewhat inappropriate length",
            3: "Acceptable length",
            4: "Well-calibrated length",
            5: "Perfectly appropriate length"
        }
    ),
    EvaluationCriterion(
        name="tone_appropriateness",
        weight=0.15,
        description="Does tone match formality, context, and relationship?",
        scoring_guide={
            1: "Completely wrong tone",
            2: "Tone somewhat off",
            3: "Acceptable tone",
            4: "Well-matched tone",
            5: "Perfect tone for context"
        }
    ),
    EvaluationCriterion(
        name="effectiveness",
        weight=0.15,
        description="Would this achieve the writer's goals?",
        scoring_guide={
            1: "Would not achieve goal",
            2: "Might partially succeed",
            3: "Would likely achieve goal",
            4: "Would clearly achieve goal",
            5: "Exceeds expectations for goal"
        }
    ),
    EvaluationCriterion(
        name="clarity",
        weight=0.10,
        description="How easy is it to understand the message?",
        scoring_guide={
            1: "Confusing or unclear",
            2: "Some confusion possible",
            3: "Generally clear",
            4: "Very clear",
            5: "Crystal clear, no ambiguity"
        }
    ),
    EvaluationCriterion(
        name="task_completion",
        weight=0.10,
        description="Does it address all aspects of the task?",
        scoring_guide={
            1: "Misses major requirements",
            2: "Partial completion",
            3: "Meets basic requirements",
            4: "Thoroughly complete",
            5: "Complete with valuable additions"
        }
    ),
    EvaluationCriterion(
        name="authenticity",
        weight=0.15,
        description="Does it read as human-like vs obviously AI-generated?",
        scoring_guide={
            1: "Clearly AI-generated",
            2: "Somewhat robotic",
            3: "Could be either",
            4: "Reads naturally",
            5: "Completely authentic voice"
        }
    ),
    EvaluationCriterion(
        name="cliche_avoidance",
        weight=0.10,
        description="Avoids AI patterns and boilerplate phrases?",
        scoring_guide={
            1: "Full of AI clichés",
            2: "Several obvious patterns",
            3: "Some clichés present",
            4: "Mostly original",
            5: "Fresh, original language"
        }
    ),
]
```

---

## 3. O*NET Data Integration

### 3.1 Task Extraction Strategy

The O*NET database contains 18,796 task statements across 923 occupations. We will extract writing-relevant tasks using the categories defined in ONET_WRITING_REFERENCE.md.

```python
class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database."""

    WRITING_CATEGORIES = {
        "explicit_writing": [
            "%write%", "%draft%", "%document%",
            "%prepare report%", "%prepare%proposal%", "%compose%"
        ],
        "correspondence": [
            "%correspond%", "%email%", "%letter%",
            "%memo%", "%notify%customer%", "%inform%customer%"
        ],
        "reports_analysis": [
            "%report%", "%present%finding%", "%present%result%",
            "%summarize%", "%prepare%presentation%"
        ],
        "persuasion_negotiation": [
            "%negotiat%", "%propos%", "%persuad%",
            "%recommend%", "%advise%client%", "%advise%customer%"
        ],
        "policy_procedure": [
            "%develop%polic%", "%implement%polic%",
            "%write%procedure%", "%prepare%guideline%", "%establish%standard%"
        ],
        "customer_communication": [
            "%customer%question%", "%client%question%",
            "%answer%question%", "%resolve%complaint%",
            "%explain%to%customer%", "%respond%to%customer%"
        ],
        "training_instruction": [
            "%train%staff%", "%train%employee%", "%instruct%",
            "%develop%curriculum%", "%prepare%manual%", "%prepare%training%"
        ],
        "internal_coordination": [
            "%confer with%", "%coordinate with%", "%collaborate with%",
            "%meet with%", "%communicate with%management%", "%communicate with%staff%"
        ],
        "contracts_legal": [
            "%prepare%contract%", "%draft%contract%",
            "%write%agreement%", "%prepare%permit%", "%prepare%compliance%"
        ],
        "feedback_evaluation": [
            "%evaluate%performance%", "%provide%feedback%",
            "%review%and%recommend%", "%assess%and%report%"
        ]
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def extract_all_writing_tasks(self) -> list[dict]:
        """Extract all tasks matching writing categories."""
        tasks = []
        for category, patterns in self.WRITING_CATEGORIES.items():
            category_tasks = self._query_tasks_by_patterns(patterns)
            for task in category_tasks:
                task["writing_category"] = category
            tasks.extend(category_tasks)
        return self._deduplicate(tasks)

    def _query_tasks_by_patterns(self, patterns: list[str]) -> list[dict]:
        """Query tasks matching LIKE patterns."""
        where_clauses = " OR ".join([f"t.task LIKE '{p}'" for p in patterns])
        query = f"""
            SELECT DISTINCT
                t.task_id,
                t.onetsoc_code,
                o.title as occupation_title,
                o.description as occupation_desc,
                t.task,
                t.task_type,
                jz.job_zone
            FROM task_statements t
            JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
            LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
            WHERE {where_clauses}
        """
        # Execute and return results
        pass

    def get_occupation_context(self, onet_code: str) -> dict:
        """Get full occupation context for enrichment."""
        query = """
            SELECT
                o.onetsoc_code,
                o.title,
                o.description,
                jz.job_zone,
                wc_email.data_value as email_frequency,
                wc_letter.data_value as letter_frequency,
                sk.data_value as writing_skill_importance
            FROM occupation_data o
            LEFT JOIN job_zones jz ON o.onetsoc_code = jz.onetsoc_code
            LEFT JOIN work_context wc_email ON o.onetsoc_code = wc_email.onetsoc_code
                AND wc_email.element_id = '4.C.1.a.2.h' AND wc_email.scale_id = 'CX'
            LEFT JOIN work_context wc_letter ON o.onetsoc_code = wc_letter.onetsoc_code
                AND wc_letter.element_id = '4.C.1.a.2.j' AND wc_letter.scale_id = 'CX'
            LEFT JOIN skills sk ON o.onetsoc_code = sk.onetsoc_code
                AND sk.element_id = '2.A.1.c' AND sk.scale_id = 'IM'
            WHERE o.onetsoc_code = ?
        """
        pass

    def get_soc_major_group(self, onet_code: str) -> tuple[str, str]:
        """Extract SOC major group from O*NET code."""
        soc_major = onet_code[:2]
        group_names = {
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
            "55": "Military Specific",
        }
        return soc_major, group_names.get(soc_major, "Unknown")
```

### 3.2 Sampling Strategy for Diversity

```python
class StratifiedSampler:
    """Ensure diverse sampling across all dimensions."""

    def __init__(self, tasks: list[dict], config: SamplingConfig):
        self.tasks = tasks
        self.config = config

    def sample(self, n: int, seed: int) -> list[dict]:
        """Sample n tasks with stratification."""
        rng = random.Random(seed)

        # Group tasks by stratification dimensions
        by_job_zone = self._group_by(self.tasks, "job_zone")
        by_soc_major = self._group_by(self.tasks, "soc_major")
        by_writing_category = self._group_by(self.tasks, "writing_category")

        # Calculate quotas for each dimension
        quotas = self._calculate_quotas(n)

        # Sample with constraints
        sampled = []
        remaining = n

        # First pass: ensure minimum representation per dimension
        for dimension, groups in [
            ("job_zone", by_job_zone),
            ("soc_major", by_soc_major),
            ("writing_category", by_writing_category)
        ]:
            min_per_group = max(1, n // (len(groups) * 3))
            for group_name, group_tasks in groups.items():
                available = [t for t in group_tasks if t not in sampled]
                to_sample = min(min_per_group, len(available), remaining)
                sampled.extend(rng.sample(available, to_sample))
                remaining -= to_sample

        # Second pass: fill remaining with proportional sampling
        all_remaining = [t for t in self.tasks if t not in sampled]
        if remaining > 0 and all_remaining:
            sampled.extend(rng.sample(all_remaining, min(remaining, len(all_remaining))))

        return sampled[:n]
```

---

## 4. Prompt Generation Pipeline

### 4.1 Three-Phase Generation Approach

The prompt generation follows a three-phase approach as specified in PROMPT.md:

**Phase 1: Offline LLM Generation** - Pre-generate diverse persona/context variations
**Phase 2: Algorithmic Combinations** - Deterministic combination with NAICS sampling
**Phase 3: LLM Enrichment** - Context-heavy prompts get additional LLM enrichment

```python
class PromptGenerator:
    """Three-phase prompt generation pipeline."""

    def __init__(
        self,
        onet_extractor: ONetExtractor,
        company_db: CompanyDatabase,
        name_generator: NameGenerator,
        llm_client: OpenRouterClient,
        config: PromptGenerationConfig
    ):
        self.onet = onet_extractor
        self.companies = company_db
        self.names = name_generator
        self.llm = llm_client
        self.config = config

    async def generate_prompts(
        self,
        n_prompts: int,
        seed: int
    ) -> list[WritingPrompt]:
        """Generate n prompts using three-phase approach."""

        rng = random.Random(seed)

        # Extract and sample O*NET tasks
        all_tasks = self.onet.extract_all_writing_tasks()
        sampler = StratifiedSampler(all_tasks, self.config.sampling)
        selected_tasks = sampler.sample(n_prompts, seed)

        prompts = []
        for i, task in enumerate(selected_tasks):
            prompt_seed = seed + i

            # Phase 2: Algorithmic combination
            prompt = self._phase2_algorithmic(task, prompt_seed)

            # Phase 3: LLM enrichment (if needed)
            if self._needs_enrichment(task):
                prompt = await self._phase3_enrichment(prompt, prompt_seed)

            prompts.append(prompt)

        return prompts

    def _phase2_algorithmic(
        self,
        task: dict,
        seed: int
    ) -> WritingPrompt:
        """Phase 2: Deterministic algorithmic combination."""
        rng = random.Random(seed)

        # Generate writer persona
        writer = self._generate_writer_persona(
            task["occupation_title"],
            task["job_zone"],
            rng
        )

        # Generate recipient persona
        recipient = self._generate_recipient_persona(task, rng)

        # Select company context
        company = self._select_company(task, rng)

        # Determine formality based on job zone and context
        formality = self._determine_formality(task["job_zone"], rng)

        # Select other dimensions
        urgency = rng.choice(["low", "medium", "high", "critical"])
        audience_size = self._select_audience_size(task, rng)
        emotional_context = self._select_emotional_context(rng)
        message_position = rng.choice(["initial", "reply", "follow_up"])

        return WritingPrompt(
            prompt_id=f"prompt_{seed:08d}",
            onet_task_id=task["task_id"],
            onet_occupation_code=task["onetsoc_code"],
            onet_occupation_title=task["occupation_title"],
            onet_task_statement=task["task"],
            job_zone=task["job_zone"],
            writer=writer,
            recipient=recipient,
            company=company,
            writing_task=task["task"],  # Will be enriched in Phase 3
            formality=formality,
            urgency=urgency,
            audience_size=audience_size,
            emotional_context=emotional_context,
            message_position=message_position,
            writing_category=task["writing_category"],
            generation_phase=2,
            random_seed=seed,
            created_at=datetime.utcnow()
        )

    def _generate_writer_persona(
        self,
        occupation_title: str,
        job_zone: int,
        rng: random.Random
    ) -> WriterPersona:
        """Generate realistic writer persona."""

        # Age distribution based on job zone
        age_ranges = {
            1: (18, 35),   # Entry level
            2: (22, 45),
            3: (25, 55),
            4: (28, 60),
            5: (30, 65),   # Senior/expert
        }
        min_age, max_age = age_ranges.get(job_zone, (25, 55))
        age = rng.randint(min_age, max_age)

        # Determine generation from age
        generation = self._age_to_generation(age)

        # Generate demographically diverse name
        name_data = self.names.generate_name(rng)

        # Skill level correlates loosely with age and job zone
        skill_base = min(job_zone, 4)
        skill_adjustment = (age - min_age) / (max_age - min_age)
        skill_level = min(5, max(1, int(skill_base + skill_adjustment * 2)))

        return WriterPersona(
            name=name_data["full_name"],
            email=f"{name_data['email_prefix']}@{rng.choice(['company.com', 'corp.com', 'org.com'])}",
            role=occupation_title,
            age=age,
            generation=generation,
            skill_level=skill_level,
            english_variant=rng.choice(list(EnglishVariant))
        )

    async def _phase3_enrichment(
        self,
        prompt: WritingPrompt,
        seed: int
    ) -> WritingPrompt:
        """Phase 3: LLM enrichment for context-heavy prompts."""

        enrichment_prompt = f"""
You are helping create a realistic writing evaluation prompt. Enrich this task with specific context.

Original O*NET Task: {prompt.onet_task_statement}
Occupation: {prompt.onet_occupation_title}
Writer: {prompt.writer.name}, {prompt.writer.role} ({prompt.writer.age} years old)
Company: {prompt.company.name} ({prompt.company.industry})
Recipient: {prompt.recipient.name}, {prompt.recipient.role}
Formality Level: {prompt.formality.value}

Create a specific, realistic writing task scenario that:
1. Grounds the task in a concrete situation
2. Adds temporal context if appropriate (dates, deadlines)
3. Includes relevant attachments or prior context if realistic
4. Specifies any competing objectives the writer faces
5. Does NOT include word count or format constraints unless explicitly testing instruction-following

Return a JSON object with:
- "writing_task": The full enriched prompt (what to write)
- "temporal_context": {{current_date, deadline, reference_event}} or null
- "attachments": [{{type, summary, key_points}}] or []
- "prior_message": Prior email/message content if this is a reply, or null
- "competing_objectives": ["objective1", "objective2"] or []
- "communication_channel": Inferred medium (email, memo, slack, report, etc.)
"""

        response = await self.llm.generate(
            model=self.config.enrichment_model,
            messages=[{"role": "user", "content": enrichment_prompt}],
            response_format={"type": "json_object"}
        )

        enrichment = json.loads(response.content)

        # Update prompt with enrichment
        prompt.writing_task = enrichment["writing_task"]
        prompt.enrichment_model = self.config.enrichment_model
        prompt.generation_phase = 3

        if enrichment.get("temporal_context"):
            prompt.temporal = TemporalContext(**enrichment["temporal_context"])

        if enrichment.get("attachments"):
            prompt.attachments = [Attachment(**a) for a in enrichment["attachments"]]

        if enrichment.get("prior_message"):
            prompt.prior_message = enrichment["prior_message"]
            prompt.message_position = "reply"

        if enrichment.get("competing_objectives"):
            prompt.competing_objectives = enrichment["competing_objectives"]

        if enrichment.get("communication_channel"):
            prompt.communication_channel = enrichment["communication_channel"]

        return prompt
```

### 4.2 Company Database

```python
class CompanyDatabase:
    """Database of real companies for prompt grounding."""

    def __init__(self):
        # Built-in knowledge of real companies organized by size and industry
        self.companies = self._load_companies()

    def _load_companies(self) -> dict[str, list[CompanyContext]]:
        """Load company data organized by NAICS sector."""

        # Example structure - would be much larger in practice
        return {
            "54": [  # Professional Services
                CompanyContext(
                    name="McKinsey & Company",
                    industry="Management Consulting",
                    naics_code="541611",
                    size_category="large",
                    employee_count=45000,
                    public_private="private",
                    hq_location="New York, USA"
                ),
                CompanyContext(
                    name="Accenture",
                    industry="IT Consulting",
                    naics_code="541512",
                    size_category="enterprise",
                    employee_count=750000,
                    public_private="public",
                    hq_location="Dublin, Ireland"
                ),
                # ... more companies
            ],
            "52": [  # Finance and Insurance
                CompanyContext(
                    name="JPMorgan Chase",
                    industry="Investment Banking",
                    naics_code="522110",
                    size_category="enterprise",
                    employee_count=300000,
                    public_private="public",
                    hq_location="New York, USA"
                ),
                # ... more companies
            ],
            # All 20 NAICS sectors represented
        }

    def get_company_for_occupation(
        self,
        occupation_code: str,
        rng: random.Random
    ) -> CompanyContext:
        """Select appropriate company based on occupation."""
        # Map occupation to likely NAICS sectors
        naics_sectors = self._occupation_to_naics(occupation_code)
        sector = rng.choice(naics_sectors)
        companies = self.companies.get(sector, self.companies["54"])
        return rng.choice(companies)
```

### 4.3 Name Generator

```python
class NameGenerator:
    """Generate demographically diverse realistic names."""

    def __init__(self):
        # Name pools with demographic representation
        self.first_names = {
            "male": {
                "anglo": ["James", "Michael", "William", "David", "Robert"],
                "hispanic": ["Carlos", "Miguel", "Jose", "Luis", "Diego"],
                "asian": ["Wei", "Jin", "Hiroshi", "Raj", "Pradeep"],
                "african": ["Kwame", "Jamal", "Marcus", "Darius", "Terrell"],
            },
            "female": {
                "anglo": ["Sarah", "Jennifer", "Elizabeth", "Jessica", "Emily"],
                "hispanic": ["Maria", "Ana", "Carmen", "Sofia", "Isabella"],
                "asian": ["Wei", "Mei", "Yuki", "Priya", "Aisha"],
                "african": ["Amara", "Nia", "Keisha", "Aaliyah", "Imani"],
            }
        }
        self.last_names = {
            "anglo": ["Smith", "Johnson", "Williams", "Brown", "Davis"],
            "hispanic": ["Garcia", "Rodriguez", "Martinez", "Lopez", "Hernandez"],
            "asian": ["Chen", "Wang", "Kim", "Patel", "Singh"],
            "african": ["Williams", "Jackson", "Washington", "Robinson", "Carter"],
        }

    def generate_name(self, rng: random.Random) -> dict:
        """Generate a name with demographic diversity."""
        gender = rng.choice(["male", "female"])
        ethnicity = rng.choice(["anglo", "hispanic", "asian", "african"])

        first = rng.choice(self.first_names[gender][ethnicity])
        last = rng.choice(self.last_names[ethnicity])

        return {
            "full_name": f"{first} {last}",
            "first_name": first,
            "last_name": last,
            "email_prefix": f"{first.lower()}.{last.lower()}",
            "gender": gender,
            "ethnicity": ethnicity
        }
```

---

## 5. OpenRouter API Integration

### 5.1 API Client

```python
import httpx
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelConfig:
    """Configuration for an OpenRouter model."""
    model_id: str
    display_name: str
    tier: Literal["pro", "flash"]
    input_cost_per_1k: float
    output_cost_per_1k: float
    context_window: int
    max_output_tokens: int

# Model registry - Jan 2026 models
MODELS = {
    # Pro-tier (Gemini 3.0 Pro competitors)
    "gemini-3-pro": ModelConfig(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro",
        tier="pro",
        input_cost_per_1k=0.0075,
        output_cost_per_1k=0.03,
        context_window=1000000,
        max_output_tokens=8192
    ),
    "gpt-5.2-thinking": ModelConfig(
        model_id="openai/gpt-5.2-thinking",
        display_name="GPT-5.2 Thinking",
        tier="pro",
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.06,
        context_window=128000,
        max_output_tokens=16384
    ),
    "claude-opus-4.5": ModelConfig(
        model_id="anthropic/claude-opus-4-5-20251101",
        display_name="Claude Opus 4.5",
        tier="pro",
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.075,
        context_window=200000,
        max_output_tokens=8192
    ),
    "grok-4.1-thinking": ModelConfig(
        model_id="x-ai/grok-4.1-thinking",
        display_name="Grok 4.1 Thinking",
        tier="pro",
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.015,
        context_window=131072,
        max_output_tokens=8192
    ),
    "kimi-k2-thinking": ModelConfig(
        model_id="moonshot/kimi-k2-thinking",
        display_name="Kimi K2 Thinking",
        tier="pro",
        input_cost_per_1k=0.006,
        output_cost_per_1k=0.018,
        context_window=200000,
        max_output_tokens=8192
    ),
    # Flash-tier (Gemini 3.0 Flash competitors)
    "gemini-3-flash": ModelConfig(
        model_id="google/gemini-3.0-flash",
        display_name="Gemini 3.0 Flash",
        tier="flash",
        input_cost_per_1k=0.00035,
        output_cost_per_1k=0.0015,
        context_window=1000000,
        max_output_tokens=8192
    ),
    "gpt-4.1": ModelConfig(
        model_id="openai/gpt-4.1",
        display_name="GPT-4.1",
        tier="flash",
        input_cost_per_1k=0.002,
        output_cost_per_1k=0.008,
        context_window=128000,
        max_output_tokens=8192
    ),
    "claude-sonnet": ModelConfig(
        model_id="anthropic/claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        tier="flash",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        context_window=200000,
        max_output_tokens=8192
    ),
}

class OpenRouterClient:
    """Async OpenRouter API client with rate limiting and retries."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        rate_limiter: RateLimiter,
        retry_config: RetryConfig
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.retry_config = retry_config
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),
            limits=httpx.Limits(max_connections=100)
        )

    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None
    ) -> GenerationResponse:
        """Generate a response from a model."""

        model_config = MODELS[model]

        payload = {
            "model": model_config.model_id,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "gemini-writing-eval",
            "X-Title": "Gemini Writing Evaluation Framework"
        }

        # Rate limiting
        await self.rate_limiter.acquire()

        # Retry logic
        for attempt in range(self.retry_config.max_retries):
            try:
                start_time = time.monotonic()
                response = await self.client.post(
                    f"{self.BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers
                )
                response_time_ms = int((time.monotonic() - start_time) * 1000)

                if response.status_code == 429:
                    # Rate limited - back off
                    wait_time = self._calculate_backoff(attempt)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                return GenerationResponse(
                    content=data["choices"][0]["message"]["content"],
                    input_tokens=data["usage"]["prompt_tokens"],
                    output_tokens=data["usage"]["completion_tokens"],
                    response_time_ms=response_time_ms,
                    model=model
                )

            except httpx.TimeoutException:
                if attempt == self.retry_config.max_retries - 1:
                    raise
                await asyncio.sleep(self._calculate_backoff(attempt))

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    if attempt == self.retry_config.max_retries - 1:
                        raise
                    await asyncio.sleep(self._calculate_backoff(attempt))
                else:
                    raise

    def _calculate_backoff(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        base = self.retry_config.base_delay
        max_delay = self.retry_config.max_delay
        delay = min(base * (2 ** attempt), max_delay)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
```

### 5.2 Rate Limiter

```python
class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000
    ):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_bucket = TokenBucket(requests_per_minute, requests_per_minute / 60)
        self.token_bucket = TokenBucket(tokens_per_minute, tokens_per_minute / 60)
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000):
        """Acquire permission to make an API call."""
        async with self._lock:
            while not self.request_bucket.consume(1):
                await asyncio.sleep(0.1)
            while not self.token_bucket.consume(estimated_tokens):
                await asyncio.sleep(0.1)

class TokenBucket:
    """Simple token bucket implementation."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self, tokens: int) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
```

### 5.3 Cost Estimator

```python
class CostEstimator:
    """Estimate costs for evaluation runs."""

    def __init__(self, models: dict[str, ModelConfig]):
        self.models = models

    def estimate_run_cost(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost for an evaluation run."""

        # Estimate tokens per prompt
        avg_prompt_tokens = 1500  # Task + context
        avg_response_tokens = 800  # Model response

        # Response generation costs
        response_costs = {}
        for model_pair in config.model_pairs:
            gemini_model = model_pair.gemini
            competitor_model = model_pair.competitor

            gemini_cost = self._model_cost(
                gemini_model,
                config.num_prompts * avg_prompt_tokens,
                config.num_prompts * avg_response_tokens
            )
            competitor_cost = self._model_cost(
                competitor_model,
                config.num_prompts * avg_prompt_tokens,
                config.num_prompts * avg_response_tokens
            )
            response_costs[f"{gemini_model} vs {competitor_model}"] = gemini_cost + competitor_cost

        # Judging costs
        judge_prompt_tokens = 3000  # Both responses + rubric
        judge_response_tokens = 500  # Judgment + reasoning

        total_judge_calls = (
            config.num_prompts *
            len(config.model_pairs) *
            len(config.judge_models) *
            config.votes_per_judge *
            len(config.judge_personas)
        )

        judge_costs = {}
        for judge in config.judge_models:
            judge_cost = self._model_cost(
                judge,
                total_judge_calls * judge_prompt_tokens // len(config.judge_models),
                total_judge_calls * judge_response_tokens // len(config.judge_models)
            )
            judge_costs[judge] = judge_cost

        return CostEstimate(
            response_generation_cost=sum(response_costs.values()),
            judging_cost=sum(judge_costs.values()),
            total_cost=sum(response_costs.values()) + sum(judge_costs.values()),
            response_costs_by_pair=response_costs,
            judge_costs_by_model=judge_costs,
            total_api_calls=total_judge_calls + config.num_prompts * len(config.model_pairs) * 2
        )

    def _model_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost for a model."""
        config = self.models[model]
        return (
            input_tokens / 1000 * config.input_cost_per_1k +
            output_tokens / 1000 * config.output_cost_per_1k
        )
```

---

## 6. Evaluation Engine

### 6.1 Main Orchestrator

```python
class EvaluationEngine:
    """Main orchestrator for the evaluation pipeline."""

    def __init__(
        self,
        config: EvalConfig,
        api_client: OpenRouterClient,
        storage: StorageManager,
        checkpoint: CheckpointManager
    ):
        self.config = config
        self.api = api_client
        self.storage = storage
        self.checkpoint = checkpoint
        self.progress_callback: Optional[Callable] = None

    async def run(self) -> EvalResults:
        """Run the full evaluation pipeline."""

        # Load or generate prompts
        if self.checkpoint.has_checkpoint():
            state = self.checkpoint.load()
            prompts = state.prompts
            completed = state.completed_comparisons
        else:
            prompts = await self._generate_prompts()
            completed = set()
            self.checkpoint.save(prompts, completed)

        # Run evaluations
        results = []
        for prompt in prompts:
            if prompt.prompt_id in completed:
                continue

            for model_pair in self.config.model_pairs:
                comparison_result = await self._evaluate_comparison(
                    prompt,
                    model_pair
                )
                results.append(comparison_result)
                completed.add(prompt.prompt_id)
                self.checkpoint.save(prompts, completed)

                if self.progress_callback:
                    self.progress_callback(len(completed), len(prompts))

        # Aggregate and analyze
        aggregated = self._aggregate_results(results)
        return aggregated

    async def _evaluate_comparison(
        self,
        prompt: WritingPrompt,
        model_pair: ModelPair
    ) -> ComparisonResult:
        """Evaluate a single prompt comparison."""

        # Generate responses from both models
        gemini_response, competitor_response = await asyncio.gather(
            self._generate_response(prompt, model_pair.gemini),
            self._generate_response(prompt, model_pair.competitor)
        )

        # Handle failures
        if gemini_response.status != "success":
            return ComparisonResult(
                prompt_id=prompt.prompt_id,
                winner="competitor",
                reason="gemini_failure",
                gemini_response=gemini_response,
                competitor_response=competitor_response
            )

        if competitor_response.status != "success":
            return ComparisonResult(
                prompt_id=prompt.prompt_id,
                winner="gemini",
                reason="competitor_failure",
                gemini_response=gemini_response,
                competitor_response=competitor_response
            )

        # Shuffle responses for position bias mitigation
        comparison = self._create_comparison_pair(
            prompt,
            gemini_response,
            competitor_response
        )

        # Collect judgments
        judgments = await self._collect_judgments(prompt, comparison)

        # Aggregate votes
        final_winner = self._aggregate_votes(judgments)

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            winner=final_winner,
            gemini_response=gemini_response,
            competitor_response=competitor_response,
            judgments=judgments,
            comparison=comparison
        )

    def _create_comparison_pair(
        self,
        prompt: WritingPrompt,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> ComparisonPair:
        """Create shuffled comparison pair."""
        rng = random.Random(prompt.random_seed)
        if rng.random() < 0.5:
            return ComparisonPair(
                comparison_id=f"cmp_{prompt.prompt_id}",
                prompt_id=prompt.prompt_id,
                gemini_response_id=gemini_response.response_id,
                competitor_response_id=competitor_response.response_id,
                competitor_model=competitor_response.model_id,
                response_a_id=gemini_response.response_id,
                response_b_id=competitor_response.response_id,
                gemini_position="A",
                shuffle_seed=prompt.random_seed
            )
        else:
            return ComparisonPair(
                comparison_id=f"cmp_{prompt.prompt_id}",
                prompt_id=prompt.prompt_id,
                gemini_response_id=gemini_response.response_id,
                competitor_response_id=competitor_response.response_id,
                competitor_model=competitor_response.model_id,
                response_a_id=competitor_response.response_id,
                response_b_id=gemini_response.response_id,
                gemini_position="B",
                shuffle_seed=prompt.random_seed
            )
```

### 6.2 Judge Implementation

```python
class JudgeManager:
    """Manages the dual-persona judging process."""

    WRITING_EXPERT_SYSTEM_PROMPT = """You are an expert writing evaluator with decades of experience
assessing professional communication. You evaluate writing based on craft, clarity, structure,
tone appropriateness, and effectiveness.

You will be given:
1. A writing task/scenario with full context
2. Two responses labeled Response A and Response B
3. An evaluation rubric with specific criteria

Your job is to:
1. Score each response on each criterion (1-5 scale)
2. Determine which response is better overall
3. Provide specific reasoning for your decision

IMPORTANT: Do not try to identify which model wrote which response. Judge purely on merit."""

    RECIPIENT_SYSTEM_PROMPT = """You are the intended recipient/reader of the writing being evaluated.
You will be given details about who you are and the context of receiving this communication.

Evaluate the responses from the perspective of: Would this writing be effective for me?
Does it address my needs? Is it appropriate for our relationship and the situation?

Score based on:
- How helpful/useful is this to me as the recipient?
- Does the tone feel right for our relationship?
- Would I respond positively to this communication?
- Does it accomplish what the sender intended?"""

    def __init__(
        self,
        api_client: OpenRouterClient,
        config: JudgeConfig
    ):
        self.api = api_client
        self.config = config

    async def collect_judgments(
        self,
        prompt: WritingPrompt,
        comparison: ComparisonPair,
        response_a_text: str,
        response_b_text: str
    ) -> list[JudgeVote]:
        """Collect all judgments for a comparison."""

        votes = []

        # Collect votes from each judge model
        for judge_model in self.config.judge_models:
            # Collect votes for each persona
            for persona in self.config.judge_personas:
                # Best-of-N votes
                for vote_num in range(1, self.config.votes_per_judge + 1):
                    vote = await self._get_judgment(
                        prompt=prompt,
                        comparison=comparison,
                        response_a_text=response_a_text,
                        response_b_text=response_b_text,
                        judge_model=judge_model,
                        persona=persona,
                        vote_number=vote_num
                    )
                    votes.append(vote)

        return votes

    async def _get_judgment(
        self,
        prompt: WritingPrompt,
        comparison: ComparisonPair,
        response_a_text: str,
        response_b_text: str,
        judge_model: str,
        persona: str,
        vote_number: int
    ) -> JudgeVote:
        """Get a single judgment vote."""

        if persona == "writing_expert":
            system_prompt = self.WRITING_EXPERT_SYSTEM_PROMPT
        else:
            system_prompt = self._build_recipient_prompt(prompt)

        user_prompt = self._build_judgment_prompt(
            prompt,
            response_a_text,
            response_b_text
        )

        response = await self.api.generate(
            model=judge_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3 + (vote_number - 1) * 0.1  # Slight variation for diversity
        )

        judgment = json.loads(response.content)

        return JudgeVote(
            vote_id=f"vote_{comparison.comparison_id}_{judge_model}_{persona}_{vote_number}",
            comparison_id=comparison.comparison_id,
            judge_model=judge_model,
            judge_persona=persona,
            vote_number=vote_number,
            winner=judgment["winner"],
            scores_response_a=judgment["scores_a"],
            scores_response_b=judgment["scores_b"],
            reasoning=judgment["reasoning"],
            response_time_ms=response.response_time_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            created_at=datetime.utcnow()
        )

    def _build_judgment_prompt(
        self,
        prompt: WritingPrompt,
        response_a: str,
        response_b: str
    ) -> str:
        """Build the full judgment prompt with context."""

        return f"""
## WRITING TASK

**Writer Profile:**
- Name: {prompt.writer.name}
- Role: {prompt.writer.role}
- Age: {prompt.writer.age} ({prompt.writer.generation.value})
- Company: {prompt.company.name} ({prompt.company.industry})

**Recipient Profile:**
- Name: {prompt.recipient.name}
- Role: {prompt.recipient.role}
- Relationship to writer: {prompt.recipient.relationship}

**Context:**
- Formality Level: {prompt.formality.value}
- Urgency: {prompt.urgency}
- Audience Size: {prompt.audience_size}
- Emotional Context: {prompt.emotional_context}

**Task:**
{prompt.writing_task}

{self._format_attachments(prompt)}
{self._format_prior_message(prompt)}

---

## RESPONSE A

{response_a}

---

## RESPONSE B

{response_b}

---

## EVALUATION RUBRIC

Score each response on these criteria (1-5 scale):

{self._format_rubric()}

---

## YOUR JUDGMENT

Provide your evaluation as JSON:
{{
    "scores_a": {{"writing_quality": N, "length_appropriateness": N, ...}},
    "scores_b": {{"writing_quality": N, "length_appropriateness": N, ...}},
    "winner": "A" | "B" | "tie",
    "reasoning": "Detailed explanation of your decision..."
}}
"""
```

### 6.3 Vote Aggregation

```python
class VoteAggregator:
    """Implements majority-of-majorities vote aggregation."""

    def aggregate(
        self,
        votes: list[JudgeVote],
        comparison: ComparisonPair
    ) -> JudgeAggregation:
        """Aggregate votes using majority-of-majorities."""

        # Group votes by judge model
        by_judge = defaultdict(list)
        for vote in votes:
            by_judge[vote.judge_model].append(vote)

        # Get majority for each judge
        judge_majorities = {}
        for judge_model, judge_votes in by_judge.items():
            majority = self._get_majority(judge_votes, comparison)
            judge_majorities[judge_model] = majority

        # Get final majority across judges
        gemini_votes = sum(1 for m in judge_majorities.values() if m == "gemini")
        competitor_votes = sum(1 for m in judge_majorities.values() if m == "competitor")
        tie_votes = sum(1 for m in judge_majorities.values() if m == "tie")

        if gemini_votes > competitor_votes and gemini_votes > tie_votes:
            final_winner = "gemini"
        elif competitor_votes > gemini_votes and competitor_votes > tie_votes:
            final_winner = "competitor"
        else:
            final_winner = "tie"

        # Calculate inter-judge agreement
        kappa = self._calculate_cohens_kappa(votes, comparison)

        # Detect position bias
        position_bias = self._detect_position_bias(votes, comparison)

        return JudgeAggregation(
            aggregation_id=f"agg_{comparison.comparison_id}",
            comparison_id=comparison.comparison_id,
            claude_majority=judge_majorities.get("claude-opus-4.5", "tie"),
            gpt_majority=judge_majorities.get("gpt-5.2-thinking", "tie"),
            gemini_judge_majority=judge_majorities.get("gemini-3-pro", "tie"),
            final_winner=final_winner,
            gemini_wins=gemini_votes,
            competitor_wins=competitor_votes,
            ties=tie_votes,
            inter_judge_agreement=kappa,
            position_bias_detected=position_bias
        )

    def _get_majority(
        self,
        votes: list[JudgeVote],
        comparison: ComparisonPair
    ) -> str:
        """Get majority winner for a set of votes."""
        # Convert A/B to gemini/competitor
        converted = []
        for vote in votes:
            if vote.winner == "tie":
                converted.append("tie")
            elif vote.winner == comparison.gemini_position:
                converted.append("gemini")
            else:
                converted.append("competitor")

        counts = Counter(converted)
        if counts["gemini"] > counts["competitor"] and counts["gemini"] > counts["tie"]:
            return "gemini"
        elif counts["competitor"] > counts["gemini"] and counts["competitor"] > counts["tie"]:
            return "competitor"
        return "tie"

    def _calculate_cohens_kappa(
        self,
        votes: list[JudgeVote],
        comparison: ComparisonPair
    ) -> float:
        """Calculate Cohen's Kappa for inter-judge agreement."""
        # Group by judge pairs
        by_judge = defaultdict(list)
        for vote in votes:
            winner = self._resolve_winner(vote, comparison)
            by_judge[vote.judge_model].append(winner)

        if len(by_judge) < 2:
            return 1.0

        # Calculate pairwise kappa and average
        judges = list(by_judge.keys())
        kappas = []
        for i in range(len(judges)):
            for j in range(i + 1, len(judges)):
                k = self._pairwise_kappa(
                    by_judge[judges[i]],
                    by_judge[judges[j]]
                )
                kappas.append(k)

        return sum(kappas) / len(kappas) if kappas else 0.0

    def _detect_position_bias(
        self,
        votes: list[JudgeVote],
        comparison: ComparisonPair
    ) -> bool:
        """Detect if there's significant position bias."""
        a_wins = sum(1 for v in votes if v.winner == "A")
        b_wins = sum(1 for v in votes if v.winner == "B")
        total = a_wins + b_wins

        if total == 0:
            return False

        # Chi-squared test for significant deviation from 50/50
        expected = total / 2
        chi_sq = ((a_wins - expected) ** 2 + (b_wins - expected) ** 2) / expected
        # Chi-squared critical value at p=0.05 with df=1 is 3.84
        return chi_sq > 3.84
```

---

## 7. Storage and Checkpointing

### 7.1 SQLite Schema

```sql
-- Core tables
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    config_json TEXT,
    status TEXT,
    total_prompts INTEGER,
    completed_prompts INTEGER
);

CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES eval_runs(run_id),
    onet_task_id TEXT,
    onet_occupation_code TEXT,
    onet_occupation_title TEXT,
    onet_task_statement TEXT,
    job_zone INTEGER,
    writing_category TEXT,
    formality TEXT,
    urgency TEXT,
    full_prompt_json TEXT,
    created_at TIMESTAMP
);

CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    model_id TEXT,
    model_name TEXT,
    response_text TEXT,
    status TEXT,
    refusal_category TEXT,
    error_message TEXT,
    response_time_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    word_count INTEGER,
    has_greeting BOOLEAN,
    has_signoff BOOLEAN,
    uses_bullets BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    gemini_response_id TEXT REFERENCES responses(response_id),
    competitor_response_id TEXT REFERENCES responses(response_id),
    competitor_model TEXT,
    gemini_position TEXT,
    shuffle_seed INTEGER
);

CREATE TABLE judge_votes (
    vote_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    judge_model TEXT,
    judge_persona TEXT,
    vote_number INTEGER,
    winner TEXT,
    scores_a_json TEXT,
    scores_b_json TEXT,
    reasoning TEXT,
    response_time_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TIMESTAMP
);

CREATE TABLE aggregations (
    aggregation_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    final_winner TEXT,
    gemini_wins INTEGER,
    competitor_wins INTEGER,
    ties INTEGER,
    inter_judge_agreement REAL,
    position_bias_detected BOOLEAN
);

-- Indexes for efficient querying
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onet_occupation_code);
CREATE INDEX idx_prompts_category ON prompts(writing_category);
CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model_id);
CREATE INDEX idx_votes_comparison ON judge_votes(comparison_id);
CREATE INDEX idx_aggregations_winner ON aggregations(final_winner);
```

### 7.2 Checkpoint Manager

```python
class CheckpointManager:
    """Manages checkpoints for resumable evaluation runs."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_path = run_dir / "checkpoint.json"

    def has_checkpoint(self) -> bool:
        """Check if a checkpoint exists."""
        return self.checkpoint_path.exists()

    def save(
        self,
        prompts: list[WritingPrompt],
        completed_comparisons: set[str],
        current_state: Optional[dict] = None
    ):
        """Save checkpoint state."""
        checkpoint = {
            "version": "1.0",
            "saved_at": datetime.utcnow().isoformat(),
            "total_prompts": len(prompts),
            "completed_count": len(completed_comparisons),
            "completed_comparisons": list(completed_comparisons),
            "current_state": current_state
        }

        # Write atomically
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(checkpoint, f, indent=2)
        temp_path.rename(self.checkpoint_path)

    def load(self) -> CheckpointState:
        """Load checkpoint state."""
        with open(self.checkpoint_path) as f:
            data = json.load(f)

        return CheckpointState(
            completed_comparisons=set(data["completed_comparisons"]),
            current_state=data.get("current_state")
        )

    def clear(self):
        """Clear checkpoint after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
```

---

## 8. TUI and Progress Visualization

### 8.1 Progress Dashboard

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ProgressBar, Static, DataTable
from textual.containers import Container, Horizontal, Vertical
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

class EvalProgressApp(App):
    """Real-time progress visualization for evaluation runs."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 4;
        grid-rows: auto 1fr 1fr auto;
    }

    #header {
        column-span: 2;
        background: $primary;
        padding: 1;
    }

    #overall-progress {
        column-span: 2;
        border: solid green;
        padding: 1;
    }

    #model-pairs {
        border: solid blue;
        padding: 1;
    }

    #current-batch {
        border: solid yellow;
        padding: 1;
    }

    #statistics {
        column-span: 2;
        border: solid cyan;
        padding: 1;
    }

    #activity-log {
        column-span: 2;
        border: solid white;
        height: 10;
    }
    """

    def __init__(self, eval_engine: EvaluationEngine):
        super().__init__()
        self.engine = eval_engine
        self.stats = EvalStats()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("OVERALL PROGRESS", id="overall-progress"),
            Static("MODEL PAIRS", id="model-pairs"),
            Static("CURRENT BATCH", id="current-batch"),
            Static("LIVE STATISTICS", id="statistics"),
            Static("RECENT ACTIVITY", id="activity-log"),
        )
        yield Footer()

    def on_mount(self):
        """Start the evaluation when mounted."""
        self.run_worker(self._run_eval())

    async def _run_eval(self):
        """Run evaluation with progress updates."""
        self.engine.progress_callback = self._update_progress

        try:
            results = await self.engine.run()
            self._show_completion(results)
        except Exception as e:
            self._show_error(e)

    def _update_progress(self, completed: int, total: int, **kwargs):
        """Update progress display."""
        overall = self.query_one("#overall-progress")
        overall.update(self._render_overall_progress(completed, total))

        if "model_pair" in kwargs:
            pairs = self.query_one("#model-pairs")
            pairs.update(self._render_model_pairs(kwargs["model_pair_stats"]))

        if "current_prompt" in kwargs:
            batch = self.query_one("#current-batch")
            batch.update(self._render_current_batch(kwargs["current_prompt"]))

        stats = self.query_one("#statistics")
        stats.update(self._render_statistics())

    def _render_overall_progress(self, completed: int, total: int) -> str:
        """Render overall progress section."""
        pct = completed / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 2.5) + "░" * (40 - int(pct / 2.5))

        elapsed = datetime.utcnow() - self.stats.started_at
        eta = elapsed / pct * (100 - pct) if pct > 0 else timedelta(0)

        return f"""
OVERALL PROGRESS
{bar}  {completed}/{total} prompts ({pct:.1f}%)

Phase: {self.stats.current_phase}
Elapsed: {elapsed}  |  ETA: {eta}
"""

    def _render_model_pairs(self, pair_stats: dict) -> str:
        """Render model pairs progress."""
        lines = ["MODEL PAIRS", ""]
        for pair, stats in pair_stats.items():
            pct = stats["completed"] / stats["total"] * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            win_rate = stats.get("win_rate", "--")
            lines.append(f"{pair[:30]:<30}  {bar}  {stats['completed']}/{stats['total']}  [{win_rate}]")
        return "\n".join(lines)

    def _render_current_batch(self, prompt: WritingPrompt) -> str:
        """Render current batch details."""
        return f"""
CURRENT BATCH

Prompt #{prompt.prompt_id}: "{prompt.onet_task_statement[:50]}..."
Occupation: {prompt.onet_occupation_title} ({prompt.onet_occupation_code})
Industry: {prompt.company.industry}
"""

    def _render_statistics(self) -> str:
        """Render live statistics."""
        return f"""
LIVE STATISTICS

Win Rates (Running)                 Performance
─────────────────────────           ──────────────────────────────
vs GPT-5.2:    {self.stats.win_rates.get('gpt-5.2', '--')}%        Avg response time:  {self.stats.avg_response_time}s
vs Opus:       {self.stats.win_rates.get('opus', '--')}%          Avg judge time:     {self.stats.avg_judge_time}s
vs Grok:       {self.stats.win_rates.get('grok', '--')}%          API calls/min:      {self.stats.api_calls_per_min}
                                    Est. cost so far:   ${self.stats.cost_so_far:.2f}
Judge Agreement: {self.stats.avg_kappa:.2f} κ
"""
```

### 8.2 Results Viewer TUI

```python
class ResultsViewerApp(App):
    """Interactive TUI for exploring evaluation results."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("s", "sort", "Sort"),
        ("d", "detail", "Detail View"),
        ("/", "search", "Search"),
    ]

    def __init__(self, db_path: str):
        super().__init__()
        self.db = ResultsDatabase(db_path)
        self.filters = {}
        self.sort_by = "prompt_id"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Static("Filters: [none]", id="filter-bar"),
                Static("Sort: prompt_id", id="sort-bar"),
            ),
            DataTable(id="results-table"),
            Container(
                Static("", id="response-a"),
                Static("", id="response-b"),
                id="detail-panel"
            ),
        )
        yield Footer()

    def on_mount(self):
        """Load initial data."""
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "Prompt ID", "Occupation", "Category",
            "Winner", "Gemini", "Competitor", "Agreement"
        )
        self._load_results()

    def _load_results(self):
        """Load results with current filters."""
        results = self.db.query_results(
            filters=self.filters,
            order_by=self.sort_by
        )

        table = self.query_one("#results-table", DataTable)
        table.clear()

        for r in results:
            table.add_row(
                r.prompt_id,
                r.occupation_title[:30],
                r.writing_category,
                r.winner,
                r.gemini_score,
                r.competitor_score,
                f"{r.agreement:.2f}"
            )

    def action_filter(self):
        """Show filter dialog."""
        self.push_screen(FilterDialog(self.filters))

    def action_detail(self):
        """Show detailed view of selected row."""
        table = self.query_one("#results-table", DataTable)
        if table.cursor_row is not None:
            prompt_id = table.get_row_at(table.cursor_row)[0]
            self._show_detail(prompt_id)

    def _show_detail(self, prompt_id: str):
        """Show side-by-side response detail."""
        comparison = self.db.get_comparison(prompt_id)

        response_a = self.query_one("#response-a")
        response_b = self.query_one("#response-b")

        response_a.update(f"""
RESPONSE A ({comparison.response_a_model})
{'─' * 40}
{comparison.response_a_text}
        """)

        response_b.update(f"""
RESPONSE B ({comparison.response_b_model})
{'─' * 40}
{comparison.response_b_text}
        """)
```

---

## 9. Analysis and Reporting

### 9.1 Statistical Analysis

```python
import numpy as np
from scipy import stats
from dataclasses import dataclass

@dataclass
class WinRateResult:
    win_rate: float
    ci_lower: float
    ci_upper: float
    n_samples: int
    p_value: float  # vs 50%

class StatisticalAnalyzer:
    """Statistical analysis of evaluation results."""

    def calculate_win_rate(
        self,
        results: list[ComparisonResult],
        model_pair: str,
        confidence: float = 0.95
    ) -> WinRateResult:
        """Calculate win rate with confidence interval."""

        wins = sum(1 for r in results if r.winner == "gemini")
        total = len(results)

        if total == 0:
            return WinRateResult(0, 0, 0, 0, 1.0)

        win_rate = wins / total

        # Wilson score interval for binomial proportion
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        denominator = 1 + z**2 / total
        center = (win_rate + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt(win_rate * (1 - win_rate) / total + z**2 / (4 * total**2)) / denominator

        ci_lower = center - margin
        ci_upper = center + margin

        # Two-tailed test vs 0.5
        test_stat = (win_rate - 0.5) / np.sqrt(0.5 * 0.5 / total)
        p_value = 2 * (1 - stats.norm.cdf(abs(test_stat)))

        return WinRateResult(
            win_rate=win_rate,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=total,
            p_value=p_value
        )

    def analyze_by_dimension(
        self,
        results: list[ComparisonResult],
        dimension: str
    ) -> dict[str, WinRateResult]:
        """Analyze win rates broken down by a dimension."""

        by_dim = defaultdict(list)
        for r in results:
            dim_value = getattr(r.prompt, dimension, "unknown")
            by_dim[dim_value].append(r)

        return {
            dim_value: self.calculate_win_rate(dim_results, "")
            for dim_value, dim_results in by_dim.items()
        }

    def detect_systematic_biases(
        self,
        results: list[ComparisonResult]
    ) -> BiasReport:
        """Detect systematic biases in results."""

        # Length bias
        gemini_lengths = [r.gemini_response.word_count for r in results]
        competitor_lengths = [r.competitor_response.word_count for r in results]
        length_diff = np.mean(gemini_lengths) - np.mean(competitor_lengths)
        length_t, length_p = stats.ttest_ind(gemini_lengths, competitor_lengths)

        # Winner length correlation
        winner_lengths = []
        loser_lengths = []
        for r in results:
            if r.winner == "gemini":
                winner_lengths.append(r.gemini_response.word_count)
                loser_lengths.append(r.competitor_response.word_count)
            elif r.winner == "competitor":
                winner_lengths.append(r.competitor_response.word_count)
                loser_lengths.append(r.gemini_response.word_count)

        winner_length_corr = np.mean(winner_lengths) - np.mean(loser_lengths)

        # Position bias
        a_wins = sum(1 for r in results for v in r.judgments if v.winner == "A")
        b_wins = sum(1 for r in results for v in r.judgments if v.winner == "B")
        position_chi_sq, position_p = stats.chisquare([a_wins, b_wins])

        return BiasReport(
            length_bias=length_diff,
            length_bias_significant=length_p < 0.05,
            winner_length_correlation=winner_length_corr,
            position_bias_chi_sq=position_chi_sq,
            position_bias_significant=position_p < 0.05
        )
```

### 9.2 Weakness Finder

```python
class WeaknessFinder:
    """Identify specific areas of Gemini weakness."""

    def __init__(self, results: list[ComparisonResult]):
        self.results = results

    def find_weaknesses(self) -> WeaknessReport:
        """Find systematic weaknesses in Gemini performance."""

        weaknesses = []

        # Analyze by writing category
        by_category = self._analyze_dimension("writing_category")
        for category, stats in by_category.items():
            if stats.win_rate < 0.45 and stats.p_value < 0.05:
                weaknesses.append(Weakness(
                    dimension="writing_category",
                    value=category,
                    win_rate=stats.win_rate,
                    confidence_interval=(stats.ci_lower, stats.ci_upper),
                    sample_size=stats.n_samples,
                    significance=stats.p_value
                ))

        # Analyze by occupation
        by_occupation = self._analyze_dimension("onet_occupation_title")
        for occ, stats in by_occupation.items():
            if stats.win_rate < 0.40 and stats.n_samples >= 10:
                weaknesses.append(Weakness(
                    dimension="occupation",
                    value=occ,
                    win_rate=stats.win_rate,
                    confidence_interval=(stats.ci_lower, stats.ci_upper),
                    sample_size=stats.n_samples,
                    significance=stats.p_value
                ))

        # Analyze by formality level
        by_formality = self._analyze_dimension("formality")
        for form, stats in by_formality.items():
            if stats.win_rate < 0.45 and stats.p_value < 0.05:
                weaknesses.append(Weakness(
                    dimension="formality",
                    value=form,
                    win_rate=stats.win_rate,
                    confidence_interval=(stats.ci_lower, stats.ci_upper),
                    sample_size=stats.n_samples,
                    significance=stats.p_value
                ))

        # Analyze by job zone
        by_job_zone = self._analyze_dimension("job_zone")
        for zone, stats in by_job_zone.items():
            if stats.win_rate < 0.45 and stats.p_value < 0.05:
                weaknesses.append(Weakness(
                    dimension="job_zone",
                    value=str(zone),
                    win_rate=stats.win_rate,
                    confidence_interval=(stats.ci_lower, stats.ci_upper),
                    sample_size=stats.n_samples,
                    significance=stats.p_value
                ))

        # Analyze by rubric criterion
        criterion_scores = self._analyze_criteria_scores()
        for criterion, score_diff in criterion_scores.items():
            if score_diff < -0.3:  # Gemini scores worse by >0.3 on average
                weaknesses.append(Weakness(
                    dimension="criterion",
                    value=criterion,
                    win_rate=None,
                    score_difference=score_diff,
                    sample_size=len(self.results)
                ))

        return WeaknessReport(
            weaknesses=sorted(weaknesses, key=lambda w: w.win_rate or 0),
            total_comparisons=len(self.results),
            overall_win_rate=sum(1 for r in self.results if r.winner == "gemini") / len(self.results)
        )

    def _analyze_dimension(self, dimension: str) -> dict[str, WinRateResult]:
        """Analyze win rates by a specific dimension."""
        analyzer = StatisticalAnalyzer()
        return analyzer.analyze_by_dimension(self.results, dimension)
```

### 9.3 PDF Report Generator

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet
import plotly.graph_objects as go
import plotly.express as px

class PDFReportGenerator:
    """Generate publication-quality PDF reports."""

    def __init__(self, results: EvalResults, output_path: str):
        self.results = results
        self.output_path = output_path
        self.styles = getSampleStyleSheet()

    def generate(self):
        """Generate the full PDF report."""

        doc = SimpleDocTemplate(self.output_path, pagesize=letter)
        story = []

        # Executive Summary
        story.extend(self._executive_summary())

        # Overall Results
        story.extend(self._overall_results())

        # Win Rate Charts
        story.extend(self._win_rate_charts())

        # Breakdown by Dimension
        story.extend(self._dimension_breakdowns())

        # Statistical Analysis
        story.extend(self._statistical_analysis())

        # Weakness Analysis
        story.extend(self._weakness_analysis())

        # Appendix: Methodology
        story.extend(self._methodology_appendix())

        doc.build(story)

    def _executive_summary(self) -> list:
        """Generate executive summary section."""
        return [
            Paragraph("Executive Summary", self.styles['Heading1']),
            Paragraph(f"""
This evaluation compared Gemini 3.0 Pro/Flash against {len(self.results.competitors)} competing models
across {self.results.total_comparisons} writing task comparisons derived from O*NET occupational data.

Key Findings:
• Overall Gemini win rate: {self.results.overall_win_rate:.1%}
• Strongest category: {self.results.strongest_category} ({self.results.strongest_win_rate:.1%})
• Weakest category: {self.results.weakest_category} ({self.results.weakest_win_rate:.1%})
• Judge agreement (Cohen's κ): {self.results.avg_kappa:.2f}
            """, self.styles['Normal']),
            Spacer(1, 20),
        ]

    def _win_rate_charts(self) -> list:
        """Generate win rate visualization charts."""

        # Overall win rate by competitor
        fig = go.Figure()
        for competitor in self.results.competitors:
            win_rate = self.results.win_rates[competitor]
            fig.add_trace(go.Bar(
                name=competitor,
                x=[competitor],
                y=[win_rate.win_rate],
                error_y=dict(
                    type='data',
                    array=[win_rate.ci_upper - win_rate.win_rate],
                    arrayminus=[win_rate.win_rate - win_rate.ci_lower]
                )
            ))

        fig.update_layout(
            title="Gemini Win Rate by Competitor",
            yaxis_title="Win Rate",
            yaxis_range=[0, 1],
            showlegend=False
        )

        # Save chart
        chart_path = self.output_path.replace('.pdf', '_winrate.png')
        fig.write_image(chart_path)

        return [
            Paragraph("Win Rates by Competitor", self.styles['Heading2']),
            Image(chart_path, width=400, height=300),
            Spacer(1, 20),
        ]

    def _weakness_analysis(self) -> list:
        """Generate weakness analysis section."""
        finder = WeaknessFinder(self.results.comparisons)
        report = finder.find_weaknesses()

        story = [
            Paragraph("Gemini Weakness Analysis", self.styles['Heading1']),
            Paragraph(f"""
The following areas show statistically significant underperformance by Gemini
compared to competitors. These represent opportunities for model improvement.
            """, self.styles['Normal']),
            Spacer(1, 10),
        ]

        # Weakness table
        data = [["Dimension", "Value", "Win Rate", "95% CI", "n", "p-value"]]
        for w in report.weaknesses[:20]:  # Top 20 weaknesses
            data.append([
                w.dimension,
                w.value[:30],
                f"{w.win_rate:.1%}" if w.win_rate else "N/A",
                f"({w.confidence_interval[0]:.1%}, {w.confidence_interval[1]:.1%})" if w.confidence_interval else "N/A",
                str(w.sample_size),
                f"{w.significance:.3f}" if w.significance else "N/A"
            ])

        table = Table(data)
        table.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])
        story.append(table)

        return story
```

---

## 10. CLI Interface

### 10.1 Main CLI

```python
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="gemini-eval", help="Gemini Writing Evaluation Framework")
console = Console()

@app.command()
def run(
    preset: int = typer.Option(None, "--preset", "-p", help="Use preset configuration (1-10)"),
    prompts: int = typer.Option(None, "--prompts", "-n", help="Number of prompts to evaluate"),
    models: str = typer.Option(None, "--models", "-m", help="Comma-separated model pairs"),
    judges: str = typer.Option(None, "--judges", "-j", help="Comma-separated judge models"),
    votes: int = typer.Option(5, "--votes", "-v", help="Votes per judge (1-5)"),
    seed: int = typer.Option(None, "--seed", "-s", help="Random seed for reproducibility"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    output_dir: Path = typer.Option(Path("results"), "--output", "-o", help="Output directory"),
    api_key: str = typer.Option(None, "--api-key", envvar="OPENROUTER_API_KEY"),
):
    """Run a writing evaluation."""

    # Load or build configuration
    if preset:
        config = load_preset(preset)
    else:
        config = EvalConfig()

    # Override with CLI options
    if prompts:
        config.num_prompts = prompts
    if models:
        config.model_pairs = parse_model_pairs(models)
    if judges:
        config.judge_models = judges.split(",")
    if votes:
        config.votes_per_judge = votes
    if seed:
        config.random_seed = seed

    # Show cost estimate
    estimator = CostEstimator(MODELS)
    estimate = estimator.estimate_run_cost(config)

    _display_estimate(config, estimate)

    if dry_run:
        return

    # Confirm
    if not typer.confirm("Proceed with evaluation?"):
        raise typer.Abort()

    # Run evaluation
    engine = EvaluationEngine(config, api_key, output_dir)

    with EvalProgressApp(engine) as app:
        app.run()

def _display_estimate(config: EvalConfig, estimate: CostEstimate):
    """Display cost and time estimate."""

    console.print()
    console.print("╭─────────────────────────────────────────────────────────────╮")
    console.print("│                    EVAL RUN ESTIMATE                        │")
    console.print("├─────────────────────────────────────────────────────────────┤")
    console.print(f"│ Prompts:              {config.num_prompts:<37}│")
    console.print(f"│ Model pairs:          {len(config.model_pairs):<37}│")
    console.print(f"│ Total comparisons:    {config.num_prompts * len(config.model_pairs):<37}│")
    console.print("│                                                             │")
    console.print(f"│ Judge config:         {len(config.judge_models)} judges × {config.votes_per_judge} votes × 2 personas{' ' * 10}│")
    console.print(f"│ Total judge calls:    {estimate.total_api_calls:<37}│")
    console.print("│                                                             │")
    console.print("│ ESTIMATED COST                                              │")
    console.print(f"│   Response generation:  ${estimate.response_generation_cost:<33.2f}│")
    console.print(f"│   Judging:              ${estimate.judging_cost:<33.2f}│")
    console.print(f"│   Total:                ${estimate.total_cost:<33.2f}│")
    console.print("╰─────────────────────────────────────────────────────────────╯")
    console.print()

@app.command()
def resume(
    run_dir: Path = typer.Argument(..., help="Path to run directory to resume"),
    api_key: str = typer.Option(None, "--api-key", envvar="OPENROUTER_API_KEY"),
):
    """Resume an interrupted evaluation run."""

    checkpoint = CheckpointManager(run_dir)
    if not checkpoint.has_checkpoint():
        console.print(f"[red]No checkpoint found in {run_dir}[/red]")
        raise typer.Abort()

    config = load_config(run_dir / "config.json")
    engine = EvaluationEngine(config, api_key, run_dir)

    with EvalProgressApp(engine) as app:
        app.run()

@app.command()
def view(
    run_dir: Path = typer.Argument(..., help="Path to run directory"),
):
    """View results in interactive TUI."""

    db_path = run_dir / "results.db"
    if not db_path.exists():
        console.print(f"[red]No results database found in {run_dir}[/red]")
        raise typer.Abort()

    app = ResultsViewerApp(str(db_path))
    app.run()

@app.command()
def report(
    run_dir: Path = typer.Argument(..., help="Path to run directory"),
    output: Path = typer.Option(None, "--output", "-o", help="Output PDF path"),
):
    """Generate PDF report from evaluation results."""

    if output is None:
        output = run_dir / "reports" / "report.pdf"

    output.parent.mkdir(parents=True, exist_ok=True)

    results = load_results(run_dir)
    generator = PDFReportGenerator(results, str(output))
    generator.generate()

    console.print(f"[green]Report generated: {output}[/green]")

@app.command()
def presets():
    """Show available preset configurations."""

    table = Table(title="Evaluation Presets")
    table.add_column("Level", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Prompts")
    table.add_column("Models")
    table.add_column("Judges")
    table.add_column("Est. Cost")
    table.add_column("Est. Time")
    table.add_column("Use Case")

    for preset in PRESETS:
        table.add_row(
            str(preset.level),
            preset.name,
            str(preset.prompts),
            f"{preset.model_pairs} pairs",
            f"{preset.judges}×{preset.votes}",
            f"~${preset.estimated_cost}",
            preset.estimated_time,
            preset.use_case
        )

    console.print(table)

if __name__ == "__main__":
    app()
```

---

## 11. Configuration Presets

```python
PRESETS = [
    PresetConfig(
        level=1,
        name="Sanity Check",
        prompts=5,
        model_pairs=1,
        judges=1,
        votes=1,
        estimated_cost=1,
        estimated_time="~2 min",
        use_case="Does the system work?"
    ),
    PresetConfig(
        level=2,
        name="Smoke Test",
        prompts=20,
        model_pairs=1,
        judges=1,
        votes=3,
        estimated_cost=5,
        estimated_time="~5 min",
        use_case="Quick functionality test"
    ),
    PresetConfig(
        level=3,
        name="Dev Iteration",
        prompts=50,
        model_pairs=2,
        judges=2,
        votes=3,
        estimated_cost=25,
        estimated_time="~15 min",
        use_case="Development/debugging"
    ),
    PresetConfig(
        level=4,
        name="Quick Sample",
        prompts=100,
        model_pairs=2,
        judges=2,
        votes=5,
        estimated_cost=75,
        estimated_time="~30 min",
        use_case="Fast directional signal"
    ),
    PresetConfig(
        level=5,
        name="Light Eval",
        prompts=200,
        model_pairs=3,
        judges=3,
        votes=3,
        estimated_cost=150,
        estimated_time="~1 hr",
        use_case="Light but meaningful eval"
    ),
    PresetConfig(
        level=6,
        name="Standard Eval",
        prompts=500,
        model_pairs=4,
        judges=3,
        votes=5,
        estimated_cost=500,
        estimated_time="~3 hrs",
        use_case="Standard evaluation run"
    ),
    PresetConfig(
        level=7,
        name="Thorough Eval",
        prompts=1000,
        model_pairs=4,
        judges=3,
        votes=5,
        estimated_cost=1000,
        estimated_time="~6 hrs",
        use_case="Thorough with good power"
    ),
    PresetConfig(
        level=8,
        name="Comprehensive",
        prompts=2000,
        model_pairs="all",
        judges=3,
        votes=5,
        estimated_cost=2500,
        estimated_time="~12 hrs",
        use_case="High statistical power"
    ),
    PresetConfig(
        level=9,
        name="Deep Dive",
        prompts=5000,
        model_pairs="all",
        judges=3,
        votes=5,
        estimated_cost=6000,
        estimated_time="~24 hrs",
        use_case="Publication-grade"
    ),
    PresetConfig(
        level=10,
        name="Full Kaboodle",
        prompts=10000,
        model_pairs="all",
        judges=3,
        votes=5,
        estimated_cost=12000,
        estimated_time="~48 hrs",
        use_case="Maximum coverage"
    ),
]
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- Project setup with pyproject.toml
- O*NET database extraction module
- Basic prompt schema and generation
- OpenRouter API client with rate limiting

### Phase 2: Core Pipeline (Week 2)
- Evaluation engine with checkpoint support
- Judge implementation with dual personas
- Vote aggregation logic
- SQLite storage layer

### Phase 3: TUI and CLI (Week 3)
- Progress dashboard implementation
- Results viewer TUI
- CLI interface with all commands
- Preset configurations

### Phase 4: Analysis and Reporting (Week 4)
- Statistical analysis module
- Weakness finder
- PDF report generation
- Cross-run comparison

### Phase 5: Polish and Testing (Week 5)
- Comprehensive unit tests
- Integration tests
- Documentation
- Performance optimization

---

## 13. Testing Strategy

### Unit Tests
- Prompt generation with mocked O*NET data
- Vote aggregation logic
- Statistical calculations
- Cost estimation

### Integration Tests
- Full pipeline with mock API responses
- Checkpoint/resume functionality
- Database operations

### End-to-End Tests
- Small-scale eval run with real API
- TUI functionality
- Report generation

---

This implementation plan provides a comprehensive blueprint for building the Gemini Writing Evaluation Framework. The modular architecture allows for parallel development across teams, while the detailed schemas and interfaces ensure consistent integration.
