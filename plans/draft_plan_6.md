# Gemini Writing Evaluation Framework - Implementation Plan (Draft 6)

## Executive Summary

This plan details a comprehensive implementation for a writing evaluation framework that compares Gemini 3.0 Pro and Flash against competing frontier LLMs on realistic professional writing tasks. The system leverages O*NET 30.1 occupational data (18,796 tasks across 1,016 occupations) to generate diverse, realistic writing prompts and uses a robust multi-judge ensemble methodology to produce trustworthy results.

---

## 1. Architecture Overview

### 1.1 High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GEMINI WRITING EVAL FRAMEWORK                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │   CLI/TUI    │   │   Prompt     │   │    Eval      │   │   Report     │  │
│  │  Interface   │──▶│  Generator   │──▶│   Engine     │──▶│  Generator   │  │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘  │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        DATA LAYER (SQLite)                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  O*NET DB   │  │   Prompts   │  │  Responses  │  │  Judgments  │  │   │
│  │  │  (onet.db)  │  │   Store     │  │   Store     │  │   Store     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        API LAYER (OpenRouter)                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │   Rate      │  │   Circuit   │  │   Retry     │  │   Cost      │  │   │
│  │  │   Limiter   │  │   Breaker   │  │   Handler   │  │   Tracker   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Components

| Component | Responsibility | Key Libraries |
|-----------|----------------|---------------|
| CLI/TUI Interface | User interaction, configuration, progress display | `textual`, `rich`, `click` |
| Prompt Generator | O*NET extraction, persona generation, LLM enrichment | `sqlite3`, `pydantic` |
| Eval Engine | Response generation, judging, vote aggregation | `asyncio`, `httpx` |
| Report Generator | PDF reports, visualizations, statistical analysis | `plotly`, `reportlab`, `scipy` |
| Data Layer | Persistence, checkpointing, results storage | `sqlite3`, `aiosqlite` |
| API Layer | OpenRouter integration, rate limiting, retries | `httpx`, `tenacity` |

### 1.3 Directory Structure

```
gemini-writing-eval/
├── pyproject.toml                 # Project configuration (poetry/uv)
├── README.md
├── CLAUDE.md
├── PROMPT.md
│
├── db/
│   ├── onet.db                    # O*NET 30.1 database
│   └── ONET_WRITING_REFERENCE.md  # O*NET reference documentation
│
├── src/
│   ├── __init__.py
│   ├── cli.py                     # CLI entry point (click)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Configuration management
│   │   ├── presets.py             # 10 preset configurations
│   │   └── cost_estimator.py      # Cost/time estimation
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py      # O*NET task extraction
│   │   ├── naics_mapper.py        # NAICS industry mapping
│   │   ├── company_database.py    # Real company name lookup
│   │   └── name_generator.py      # Realistic person name generation
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic schemas for prompts
│   │   ├── generator.py           # Three-phase prompt generation
│   │   ├── enricher.py            # LLM enrichment (Phase 3)
│   │   └── sampler.py             # Stratified sampling logic
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Response/judgment schemas
│   │   ├── engine.py              # Main evaluation orchestrator
│   │   ├── response_generator.py  # Model response collection
│   │   ├── judge.py               # Judge prompt construction
│   │   ├── vote_aggregator.py     # Majority-of-majorities logic
│   │   └── failure_handler.py     # Refusal categorization
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py   # OpenRouter API wrapper
│   │   ├── rate_limiter.py        # Token bucket rate limiting
│   │   ├── circuit_breaker.py     # Circuit breaker pattern
│   │   └── token_counter.py       # Token counting utilities
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite schema and operations
│   │   ├── checkpoint.py          # Checkpoint/resume logic
│   │   └── exporter.py            # CSV/JSON export utilities
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # Win rates, confidence intervals
│   │   ├── bias_detector.py       # Systematic bias detection
│   │   ├── weakness_finder.py     # Gemini weakness identification
│   │   └── agreement.py           # Inter-judge agreement (Cohen's κ)
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py       # PDF report generation
│   │   ├── visualizations.py      # Plotly charts
│   │   └── templates/             # Report templates
│   │
│   └── tui/
│       ├── __init__.py
│       ├── app.py                 # Main Textual application
│       ├── screens/
│       │   ├── progress.py        # Live progress dashboard
│       │   ├── results.py         # Results viewer
│       │   └── config.py          # Configuration screen
│       └── widgets/
│           ├── model_pair.py      # Per-pair progress widget
│           └── statistics.py      # Live statistics widget
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── unit/
│   │   ├── test_prompts.py
│   │   ├── test_eval.py
│   │   ├── test_api.py
│   │   └── test_analysis.py
│   └── integration/
│       ├── test_e2e.py
│       └── test_openrouter.py
│
└── results/                       # Evaluation run outputs
    └── .gitkeep
```

---

## 2. Data Models and Schemas

### 2.1 Prompt Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class FormattingLevel(str, Enum):
    HIGHLY_CASUAL = "highly_casual"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    HIGHLY_FORMAL = "highly_formal"

class GenerationDemographic(str, Enum):
    GEN_Z = "gen_z"          # Born 1997-2012
    MILLENNIAL = "millennial" # Born 1981-1996
    GEN_X = "gen_x"          # Born 1965-1980
    BOOMER = "boomer"        # Born 1946-1964
    SILENT = "silent"        # Born 1928-1945

class UrgencyLevel(str, Enum):
    ROUTINE = "routine"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CELEBRATION = "celebration"
    CRISIS = "crisis"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"
    SENSITIVE = "sensitive"

class AudienceSize(str, Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class MessagePosition(str, Enum):
    INITIAL_OUTREACH = "initial"
    REPLY_IN_THREAD = "reply"
    FOLLOW_UP = "follow_up"

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class WriterPersona(BaseModel):
    """Full writer persona specification"""
    name: str
    email: Optional[str] = None
    job_title: str
    occupation_code: str  # O*NET SOC code
    company_name: str
    company_size: str  # "Fortune 500", "mid-market", "small", "startup"
    company_industry_naics: str
    age_range: tuple[int, int]
    generation: GenerationDemographic
    skill_level: int = Field(ge=1, le=5)  # O*NET Job Zone
    years_experience: int
    english_variant: EnglishVariant = EnglishVariant.EN_US

class RecipientPersona(BaseModel):
    """Full recipient persona specification"""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship_to_writer: str  # "supervisor", "direct report", "peer", "external client", etc.
    prior_contact: bool  # Have they communicated before?
    english_variant: EnglishVariant = EnglishVariant.EN_US
    technical_level: Optional[str] = None  # "technical", "non-technical", "mixed"

class AdditionalRecipient(BaseModel):
    """For CC/BCC situations"""
    name: str
    job_title: str
    relationship: str
    visibility: str  # "cc", "bcc", "forwarded_to"

class Attachment(BaseModel):
    """Mock attachment content"""
    name: str
    type: str  # "report", "email", "meeting_notes", "resume", etc.
    summary: str

class PriorMessage(BaseModel):
    """For reply-to scenarios"""
    sender_name: str
    content: str
    timestamp: Optional[datetime] = None

class ToneExample(BaseModel):
    """For tone-matching scenarios"""
    context: str
    example_text: str

class InstructionConstraint(BaseModel):
    """Explicit instruction to test compliance"""
    type: str  # "length", "format", "tone", "exclusion"
    instruction: str
    expected_compliance: str

class WritingPrompt(BaseModel):
    """Complete writing prompt specification"""
    prompt_id: str

    # Core task
    onet_task_id: str
    onet_task_text: str
    onet_occupation_code: str
    onet_occupation_title: str
    onet_job_zone: int

    # Industry context
    naics_code: str
    naics_description: str

    # Personas
    writer: WriterPersona
    primary_recipient: RecipientPersona
    additional_recipients: List[AdditionalRecipient] = []

    # Context dimensions
    formality: FormattingLevel
    urgency: UrgencyLevel
    emotional_context: EmotionalContext
    audience_size: AudienceSize
    message_position: MessagePosition

    # Communication details
    communication_channel: Optional[str] = None  # Inferred from task
    temporal_context: Optional[str] = None

    # Enrichment content
    attachments: List[Attachment] = []
    prior_messages: List[PriorMessage] = []
    tone_examples: List[ToneExample] = []

    # Special scenarios
    competing_objectives: Optional[str] = None
    is_revision_task: bool = False
    revision_content: Optional[str] = None
    is_ambiguous: bool = False

    # Constraints
    instruction_constraints: List[InstructionConstraint] = []

    # Metadata
    sensitive_topic_category: Optional[str] = None
    language: str = "en"
    language_variant: str = "en-US"
    generation_seed: int

    # Computed fields
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0

    def render_prompt(self) -> str:
        """Render the full prompt text for model consumption"""
        # Implementation renders all fields into coherent prompt
        pass
```

### 2.2 Response Schema

```python
class ModelResponse(BaseModel):
    """Single model response to a writing prompt"""
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

    # Response characteristics (auto-detected)
    word_count: int
    character_count: int
    has_greeting: bool
    has_signoff: bool
    uses_bullet_points: bool
    uses_headers: bool
    paragraph_count: int

    # Failure tracking
    is_failure: bool = False
    failure_category: Optional[str] = None  # "safety_refusal", "capability_limitation", etc.
    failure_reason: Optional[str] = None

    # Timestamps
    generated_at: datetime
    retry_count: int = 0
```

### 2.3 Judgment Schema

```python
class JudgeVote(BaseModel):
    """Single vote from a judge"""
    vote_id: str
    comparison_id: str
    judge_model: str
    judge_persona: str  # "writing_expert" or "recipient"
    vote_number: int  # 1-5 for best-of-5

    # Position tracking (for bias detection)
    response_a_model: str
    response_b_model: str
    response_a_position: str  # "first" or "second" in presentation

    # Vote result
    winner: str  # "A", "B", or "tie"
    confidence: float = Field(ge=0.0, le=1.0)

    # Detailed scores (1-10 scale)
    scores_response_a: dict  # {"quality": 8, "tone": 7, "clarity": 9, ...}
    scores_response_b: dict

    # Reasoning
    reasoning: str

    # Metadata
    judge_response_time_ms: int
    judge_input_tokens: int
    judge_output_tokens: int
    judged_at: datetime

class JudgeAggregation(BaseModel):
    """Aggregated result from one judge (best-of-5)"""
    judge_model: str
    judge_persona: str

    votes: List[JudgeVote]
    winner: str  # Majority winner from 5 votes
    vote_distribution: dict  # {"A": 3, "B": 2, "tie": 0}

class ComparisonResult(BaseModel):
    """Complete comparison result for one prompt, one model pair"""
    comparison_id: str
    prompt_id: str

    # Models being compared
    gemini_model: str  # "gemini-3.0-pro" or "gemini-3.0-flash"
    competitor_model: str

    # Responses
    gemini_response: ModelResponse
    competitor_response: ModelResponse

    # Judge results (3 judges x 2 personas)
    judge_results: List[JudgeAggregation]

    # Final aggregation (majority of majorities)
    final_winner: str  # "gemini", "competitor", or "tie"
    judge_agreement: int  # 0, 1, 2, or 3 judges agreed with final

    # Analysis flags
    auto_loss_applied: bool = False
    auto_loss_reason: Optional[str] = None
```

---

## 3. O*NET Data Extraction and Processing

### 3.1 Task Extraction Strategy

The O*NET database contains 18,796 task statements. We will extract writing-relevant tasks using the following approach:

```python
class ONetExtractor:
    """Extract and process O*NET tasks for writing evaluation"""

    WRITING_KEYWORDS = [
        # Explicit writing
        'write', 'draft', 'compose', 'author', 'document',
        # Correspondence
        'correspond', 'email', 'letter', 'memo', 'notify', 'inform',
        # Reports
        'report', 'present', 'summarize', 'prepare',
        # Persuasion
        'negotiate', 'propose', 'persuade', 'recommend', 'advise',
        # Policy
        'policy', 'procedure', 'guideline', 'protocol',
        # Customer/client
        'customer', 'client', 'explain', 'respond', 'resolve',
        # Training
        'train', 'instruct', 'educate', 'curriculum',
        # Coordination
        'confer', 'coordinate', 'collaborate', 'communicate',
        # Legal/contracts
        'contract', 'agreement', 'compliance',
        # Feedback
        'evaluate', 'feedback', 'review', 'assess'
    ]

    def extract_writing_tasks(self) -> List[dict]:
        """Extract all tasks that involve writing"""
        query = """
        SELECT
            t.task_id,
            t.onetsoc_code,
            o.title as occupation_title,
            o.description as occupation_description,
            t.task,
            t.task_type,
            jz.job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major_code
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        WHERE {keyword_conditions}
        """
        # Build WHERE clause from keywords
        conditions = " OR ".join([
            f"LOWER(t.task) LIKE '%{kw}%'"
            for kw in self.WRITING_KEYWORDS
        ])

        # Execute and return results
        pass

    def classify_task_category(self, task_text: str) -> str:
        """Classify task into one of 10 inferred categories"""
        categories = {
            'explicit_writing': ['write', 'draft', 'compose', 'author'],
            'correspondence': ['correspond', 'email', 'letter', 'memo'],
            'reports_analysis': ['report', 'present', 'summarize'],
            'persuasion_negotiation': ['negotiate', 'propose', 'persuade'],
            'policy_procedure': ['policy', 'procedure', 'guideline'],
            'customer_communication': ['customer', 'client', 'explain to'],
            'training_instruction': ['train', 'instruct', 'educate'],
            'internal_coordination': ['confer', 'coordinate', 'collaborate'],
            'contracts_legal': ['contract', 'agreement', 'compliance'],
            'feedback_evaluation': ['evaluate', 'feedback', 'assess']
        }
        # Return first matching category
        task_lower = task_text.lower()
        for category, keywords in categories.items():
            if any(kw in task_lower for kw in keywords):
                return category
        return 'general_communication'

    def get_occupation_context(self, onet_code: str) -> dict:
        """Get full occupation context for enrichment"""
        query = """
        SELECT
            o.onetsoc_code,
            o.title,
            o.description,
            jz.job_zone,
            -- Communication frequency scores
            (SELECT data_value FROM work_context
             WHERE onetsoc_code = o.onetsoc_code
             AND element_id = '4.C.1.a.2.h' AND scale_id = 'CX') as email_freq,
            (SELECT data_value FROM work_context
             WHERE onetsoc_code = o.onetsoc_code
             AND element_id = '4.C.1.a.2.j' AND scale_id = 'CX') as letter_freq,
            -- Writing skill importance
            (SELECT data_value FROM skills sk
             JOIN content_model_reference cm ON sk.element_id = cm.element_id
             WHERE sk.onetsoc_code = o.onetsoc_code
             AND cm.element_name = 'Writing' AND sk.scale_id = 'IM') as writing_skill
        FROM occupation_data o
        LEFT JOIN job_zones jz ON o.onetsoc_code = jz.onetsoc_code
        WHERE o.onetsoc_code = ?
        """
        pass
```

### 3.2 Job Zone to Formality Mapping

Job zones provide a natural basis for formality expectations:

| Job Zone | Typical Occupations | Default Formality Range |
|----------|---------------------|------------------------|
| 1 | Food service, cleaning | Casual to Neutral |
| 2 | Sales, administrative | Casual to Formal |
| 3 | Trades, technical | Neutral to Formal |
| 4 | Professional, management | Formal to Highly Formal |
| 5 | Executive, scientific | Formal to Highly Formal |

---

## 4. NAICS Industry Mapping

### 4.1 Industry Diversity Strategy

Since O*NET does not contain NAICS codes directly, we implement a mapping system:

```python
class NAICSMapper:
    """Map occupations to industries using NAICS codes"""

    # NAICS 2-digit sector codes
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

    # Occupation-to-industry affinity matrix (SOC major to NAICS affinity)
    # This enables sampling across industries for each occupation
    OCCUPATION_INDUSTRY_AFFINITY = {
        "11": ["54", "52", "55", "92", "62"],  # Management -> Prof services, Finance, etc.
        "13": ["52", "54", "55", "92"],        # Business/Financial
        "15": ["51", "54", "52", "31-33"],     # Computer/Math
        "17": ["54", "23", "31-33", "21"],     # Architecture/Engineering
        "19": ["54", "61", "62", "92"],        # Science
        "21": ["92", "62", "81"],              # Community/Social
        "23": ["54", "92"],                    # Legal
        "25": ["61", "92"],                    # Education
        "27": ["51", "71", "54"],              # Arts/Media
        "29": ["62"],                          # Healthcare Practitioners
        "31": ["62"],                          # Healthcare Support
        "33": ["92"],                          # Protective Service
        "35": ["72"],                          # Food Preparation
        "37": ["56", "72", "92"],              # Building/Grounds
        "39": ["81", "71", "72"],              # Personal Care
        "41": ["44-45", "42", "52"],           # Sales
        "43": ["All sectors"],                 # Office/Admin - cross-cutting
        "45": ["11"],                          # Farming
        "47": ["23"],                          # Construction
        "49": ["48-49", "31-33", "44-45"],     # Installation/Maintenance
        "51": ["31-33"],                       # Production
        "53": ["48-49", "42"]                  # Transportation
    }

    def sample_industries_for_occupation(
        self,
        soc_major_code: str,
        n_samples: int = 5
    ) -> List[str]:
        """Sample diverse industries for an occupation"""
        affinity = self.OCCUPATION_INDUSTRY_AFFINITY.get(soc_major_code, ["54"])
        # Sample from affiliated industries with diversity
        pass
```

---

## 5. Company Database

### 5.1 Real Company Names for Realism

To ground prompts in reality, we maintain a database of real companies:

```python
class CompanyDatabase:
    """Database of real companies for prompt grounding"""

    # Structure: NAICS -> Size -> List of companies
    COMPANIES = {
        "52": {  # Finance and Insurance
            "fortune_500": [
                {"name": "JPMorgan Chase", "hq": "New York, NY", "employees": 270000, "public": True},
                {"name": "Bank of America", "hq": "Charlotte, NC", "employees": 213000, "public": True},
                {"name": "Wells Fargo", "hq": "San Francisco, CA", "employees": 247000, "public": True},
                {"name": "Citigroup", "hq": "New York, NY", "employees": 200000, "public": True},
            ],
            "mid_market": [
                {"name": "Regions Financial", "hq": "Birmingham, AL", "employees": 20000, "public": True},
                {"name": "Zions Bancorporation", "hq": "Salt Lake City, UT", "employees": 10000, "public": True},
            ],
            "small_business": [
                {"name": "Community First Bank", "employees": 150, "public": False},
                {"name": "Riverside Credit Union", "employees": 45, "public": False},
            ],
            "startup": [
                {"name": "Plaid", "employees": 1000, "stage": "Series D", "public": False},
                {"name": "Stripe", "employees": 7000, "stage": "Late Stage", "public": False},
            ]
        },
        # ... similar structure for all 20 NAICS sectors
    }

    def get_company(
        self,
        naics_code: str,
        size_category: str
    ) -> dict:
        """Get a company from the database"""
        pass

    def sample_companies_across_sizes(
        self,
        naics_code: str
    ) -> List[dict]:
        """Sample one company from each size category"""
        pass
```

---

## 6. Realistic Name Generation

### 6.1 Demographically Diverse Names

```python
class NameGenerator:
    """Generate realistic, demographically diverse names"""

    # Names organized by demographic characteristics
    NAMES_BY_GENERATION = {
        "gen_z": {
            "female": ["Olivia Chen", "Emma Garcia", "Ava Williams", "Sophia Kim", "Isabella Patel"],
            "male": ["Liam Johnson", "Noah Martinez", "Oliver Brown", "Aiden Nguyen", "Lucas Davis"],
        },
        "millennial": {
            "female": ["Sarah Mitchell", "Jennifer Lee", "Amanda Rodriguez", "Jessica Thompson", "Ashley Park"],
            "male": ["Michael Chen", "Christopher Garcia", "Matthew Kim", "David Patel", "James Wilson"],
        },
        "gen_x": {
            "female": ["Karen Johnson", "Lisa Williams", "Michelle Davis", "Kimberly Brown", "Angela Martinez"],
            "male": ["Robert Smith", "William Jones", "Richard Garcia", "Thomas Lee", "Charles Williams"],
        },
        "boomer": {
            "female": ["Patricia Anderson", "Linda Thomas", "Barbara Wilson", "Elizabeth Taylor", "Susan Moore"],
            "male": ["James Johnson", "John Smith", "Robert Williams", "Michael Brown", "William Davis"],
        }
    }

    def generate_name(
        self,
        generation: GenerationDemographic,
        gender: Optional[str] = None
    ) -> str:
        """Generate a name matching demographic characteristics"""
        pass

    def generate_email(
        self,
        name: str,
        company_name: str
    ) -> str:
        """Generate a realistic email address"""
        # Patterns: first.last@, f.last@, firstlast@, first_last@
        pass

    def generate_name_variant(
        self,
        name: str,
        formality: FormattingLevel
    ) -> str:
        """Generate appropriate name form based on formality"""
        # Highly formal: "Dr. Patricia A. Johnson"
        # Formal: "Ms. Patricia Johnson"
        # Neutral: "Patricia Johnson"
        # Casual: "Pat"
        pass

---

## 7. Three-Phase Prompt Generation

### 7.1 Phase 1: Offline LLM Generation

Pre-generate diverse persona/context variations for each O*NET task category:

```python
class Phase1Generator:
    """Offline LLM generation of persona variations"""

    PERSONA_GENERATION_PROMPT = """
    Given this O*NET writing task:
    "{task_text}"

    For the occupation: {occupation_title}

    Generate 10 diverse realistic scenarios with:
    1. Writer persona (name, age, experience level, communication style)
    2. Recipient persona (name, role, relationship to writer)
    3. Company context (real company name or realistic fictional, industry, size)
    4. Specific situation context (what prompted this writing need)
    5. Urgency level and emotional context
    6. Any competing objectives or constraints

    Ensure diversity across:
    - Age ranges (Gen Z to Boomer)
    - Skill levels (entry-level to senior)
    - Company sizes (startup to Fortune 500)
    - Formality levels
    - Urgency levels
    - Emotional contexts

    Output as JSON array with schema: [...]
    """

    async def generate_persona_variations(
        self,
        task: dict,
        model: str = "gemini-3.0-pro",
        n_variations: int = 10
    ) -> List[dict]:
        """Generate diverse persona variations for a task"""
        pass

    async def batch_generate(
        self,
        tasks: List[dict],
        models: List[str]  # Use multiple models to avoid bias
    ) -> dict:
        """Generate variations for all tasks using multiple models"""
        # Distribute tasks across models for diversity
        pass
```

### 7.2 Phase 2: Algorithmic Combination

Deterministic combination of O*NET tasks with dimensions:

```python
class Phase2Combiner:
    """Algorithmic combination of tasks with diversity dimensions"""

    def create_prompt_matrix(
        self,
        tasks: List[dict],
        seed: int
    ) -> List[WritingPrompt]:
        """Create deterministic prompt combinations"""
        rng = random.Random(seed)

        prompts = []
        for task in tasks:
            # Sample dimensions algorithmically
            formality = self._sample_formality(task['job_zone'], rng)
            urgency = self._sample_urgency(rng)
            emotional_context = self._sample_emotional(rng)
            generation = self._sample_generation(rng)

            # Get industry from affinity matrix
            industry = self._sample_industry(task['soc_major_code'], rng)

            # Get real company
            company = self._get_company(industry, rng)

            # Generate personas
            writer = self._generate_writer_persona(
                task, company, generation, formality, rng
            )
            recipient = self._generate_recipient_persona(
                task, formality, rng
            )

            prompt = WritingPrompt(
                prompt_id=self._generate_id(task, seed),
                onet_task_id=task['task_id'],
                onet_task_text=task['task'],
                # ... fill all fields
            )
            prompts.append(prompt)

        return prompts

    def _sample_formality(
        self,
        job_zone: int,
        rng: random.Random
    ) -> FormattingLevel:
        """Sample formality based on job zone with variation"""
        distributions = {
            1: [0.1, 0.4, 0.4, 0.1, 0.0],  # Skews casual
            2: [0.05, 0.3, 0.4, 0.2, 0.05],
            3: [0.02, 0.2, 0.4, 0.3, 0.08],
            4: [0.01, 0.1, 0.3, 0.4, 0.19],
            5: [0.0, 0.05, 0.25, 0.45, 0.25]  # Skews formal
        }
        levels = list(FormattingLevel)
        weights = distributions.get(job_zone, distributions[3])
        return rng.choices(levels, weights=weights)[0]
```

### 7.3 Phase 3: LLM Enrichment

Add rich context for complex prompts:

```python
class Phase3Enricher:
    """LLM enrichment for context-heavy prompts"""

    ENRICHMENT_PROMPT = """
    Enrich this writing prompt with realistic details.

    Base prompt:
    {base_prompt}

    Writer: {writer_description}
    Recipient: {recipient_description}
    Company: {company_context}
    Situation: {situation_context}

    Add the following where appropriate and realistic:
    1. Temporal context (if urgency matters, add specific dates/deadlines)
    2. Prior messages to reply to (if this is a response)
    3. Attachments/references (if the task implies external content)
    4. Tone examples (if matching existing style)
    5. Competing objectives (if realistic tensions exist)

    ONLY add elements that make sense for this specific task.
    Do NOT force all elements into every prompt.

    Output the enriched prompt as JSON matching schema: {...}
    """

    SPECIAL_SCENARIOS = {
        "revision_task": """
        This is a revision/editing task. Generate:
        1. The original draft to be revised (with realistic flaws)
        2. The specific revision instructions
        """,

        "reply_to": """
        This task requires replying to a prior message. Generate:
        1. The message being replied to
        2. The sender's name and role
        3. The tone of the original message
        """,

        "multi_recipient": """
        This task has multiple audiences. Generate:
        1. Primary recipient details
        2. CC recipients and their roles
        3. How the message might be forwarded
        """,

        "ambiguous": """
        This prompt should be deliberately vague to test ambiguity handling.
        Generate a realistic underspecified scenario.
        """
    }

    async def enrich_prompt(
        self,
        base_prompt: WritingPrompt,
        scenario_type: Optional[str] = None
    ) -> WritingPrompt:
        """Enrich a prompt with additional context"""
        pass

    def should_enrich(self, prompt: WritingPrompt) -> bool:
        """Determine if a prompt needs LLM enrichment"""
        # Enrich if:
        # - Task mentions attachments/references
        # - Task is a reply/response
        # - High formality + complex occupation
        # - Task involves sensitive topics
        pass
```

### 7.4 Stratified Sampling

Ensure diverse representation across all dimensions:

```python
class StratifiedSampler:
    """Stratified sampling for diverse prompt selection"""

    def sample_prompts(
        self,
        all_prompts: List[WritingPrompt],
        n_samples: int,
        seed: int,
        stratification: dict = None
    ) -> List[WritingPrompt]:
        """Sample prompts with stratification guarantees"""

        if stratification is None:
            stratification = {
                'job_zone': True,      # Even across 5 job zones
                'soc_major': True,     # Even across 22 occupation groups
                'naics_sector': True,  # Even across 20 industry sectors
                'formality': True,     # Even across 5 formality levels
                'generation': True,    # Even across generations
                'task_category': True  # Even across 10 writing categories
            }

        rng = random.Random(seed)

        # Build stratification groups
        groups = self._build_stratification_groups(all_prompts, stratification)

        # Sample evenly from each stratum
        samples_per_stratum = n_samples // len(groups)
        sampled = []

        for group in groups:
            group_samples = rng.sample(
                group,
                min(samples_per_stratum, len(group))
            )
            sampled.extend(group_samples)

        # Fill remaining with random samples if needed
        remaining = n_samples - len(sampled)
        if remaining > 0:
            available = [p for p in all_prompts if p not in sampled]
            sampled.extend(rng.sample(available, remaining))

        return sampled

    def apply_filters(
        self,
        prompts: List[WritingPrompt],
        filters: dict
    ) -> List[WritingPrompt]:
        """Apply user-specified filters"""
        filtered = prompts

        if 'occupations' in filters:
            # Filter by O*NET occupation codes (supports wildcards)
            filtered = [p for p in filtered
                       if self._matches_pattern(p.onet_occupation_code, filters['occupations'])]

        if 'industries' in filters:
            # Filter by NAICS codes
            filtered = [p for p in filtered
                       if p.naics_code.startswith(tuple(filters['industries']))]

        if 'job_zones' in filters:
            # Filter by job zone (skill level)
            filtered = [p for p in filtered
                       if p.onet_job_zone in filters['job_zones']]

        if 'formality_range' in filters:
            # Filter by formality level
            min_f, max_f = filters['formality_range']
            formality_order = list(FormattingLevel)
            filtered = [p for p in filtered
                       if min_f <= formality_order.index(p.formality) <= max_f]

        return filtered
```

---

## 8. Model Configuration

### 8.1 Supported Models via OpenRouter

```python
class ModelConfig:
    """Model configuration for OpenRouter API"""

    # Pro-tier models
    PRO_TIER = {
        "gemini-3.0-pro": {
            "openrouter_id": "google/gemini-3.0-pro",
            "context_window": 1000000,
            "input_price_per_1k": 0.0025,
            "output_price_per_1k": 0.0075,
            "tier": "pro"
        },
        "gpt-5.2-thinking": {
            "openrouter_id": "openai/gpt-5.2-thinking",
            "context_window": 128000,
            "input_price_per_1k": 0.015,
            "output_price_per_1k": 0.075,
            "tier": "pro"
        },
        "claude-opus-4.5": {
            "openrouter_id": "anthropic/claude-opus-4.5",
            "context_window": 200000,
            "input_price_per_1k": 0.015,
            "output_price_per_1k": 0.075,
            "tier": "pro"
        },
        "grok-4.1-thinking": {
            "openrouter_id": "x-ai/grok-4.1-thinking",
            "context_window": 131000,
            "input_price_per_1k": 0.005,
            "output_price_per_1k": 0.015,
            "tier": "pro"
        },
        "kimi-k2-thinking": {
            "openrouter_id": "moonshot/kimi-k2-thinking",
            "context_window": 128000,
            "input_price_per_1k": 0.006,
            "output_price_per_1k": 0.018,
            "tier": "pro"
        }
    }

    # Flash-tier models
    FLASH_TIER = {
        "gemini-3.0-flash": {
            "openrouter_id": "google/gemini-3.0-flash",
            "context_window": 1000000,
            "input_price_per_1k": 0.0001,
            "output_price_per_1k": 0.0004,
            "tier": "flash"
        },
        "gpt-4.1": {
            "openrouter_id": "openai/gpt-4.1",
            "context_window": 128000,
            "input_price_per_1k": 0.002,
            "output_price_per_1k": 0.008,
            "tier": "flash"
        },
        "claude-sonnet": {
            "openrouter_id": "anthropic/claude-sonnet-4",
            "context_window": 200000,
            "input_price_per_1k": 0.003,
            "output_price_per_1k": 0.015,
            "tier": "flash"
        }
    }

    # Judge models
    JUDGE_MODELS = ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3.0-pro"]

    @classmethod
    def get_model_pairs(cls, tier: str = "both") -> List[tuple]:
        """Get model pairs for comparison"""
        pairs = []

        if tier in ("pro", "both"):
            for competitor in ["gpt-5.2-thinking", "claude-opus-4.5",
                              "grok-4.1-thinking", "kimi-k2-thinking"]:
                pairs.append(("gemini-3.0-pro", competitor))

        if tier in ("flash", "both"):
            for competitor in ["gpt-4.1", "claude-sonnet"]:
                pairs.append(("gemini-3.0-flash", competitor))

        return pairs
```

---

## 9. OpenRouter API Client

### 9.1 Robust API Client Implementation

```python
import asyncio
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type
)

class OpenRouterClient:
    """Robust OpenRouter API client with rate limiting and retries"""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        max_concurrent: int = 10,
        timeout: float = 120.0
    ):
        self.api_key = api_key
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout
        self.rate_limiter = TokenBucketRateLimiter(
            tokens_per_second=50,
            bucket_size=100
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60
        )
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://gemini-eval.example.com",
                "X-Title": "Gemini Writing Evaluation"
            }
        )
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException))
    )
    async def complete(
        self,
        model: str,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> dict:
        """Send completion request with retries and rate limiting"""

        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            raise CircuitBreakerOpenError("Circuit breaker is open")

        # Wait for rate limit token
        await self.rate_limiter.acquire()

        # Acquire semaphore for concurrent request limit
        async with self.semaphore:
            try:
                response = await self._client.post(
                    f"{self.BASE_URL}/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                response.raise_for_status()

                self.circuit_breaker.record_success()
                return response.json()

            except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                self.circuit_breaker.record_failure()
                raise

    async def complete_with_tracking(
        self,
        model: str,
        messages: List[dict],
        **kwargs
    ) -> tuple[dict, dict]:
        """Complete with timing and token tracking"""
        start_time = asyncio.get_event_loop().time()

        result = await self.complete(model, messages, **kwargs)

        elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        tracking = {
            "response_time_ms": elapsed_ms,
            "input_tokens": result.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": result.get("usage", {}).get("completion_tokens", 0),
            "total_tokens": result.get("usage", {}).get("total_tokens", 0)
        }

        return result, tracking


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API calls"""

    def __init__(self, tokens_per_second: float, bucket_size: int):
        self.tokens_per_second = tokens_per_second
        self.bucket_size = bucket_size
        self.tokens = bucket_size
        self.last_update = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token, waiting if necessary"""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_update

            # Refill bucket
            self.tokens = min(
                self.bucket_size,
                self.tokens + elapsed * self.tokens_per_second
            )
            self.last_update = now

            if self.tokens < 1:
                # Wait for token
                wait_time = (1 - self.tokens) / self.tokens_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class CircuitBreaker:
    """Circuit breaker for API resilience"""

    def __init__(self, failure_threshold: int, recovery_timeout: float):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
```

---

## 10. Evaluation Engine

### 10.1 Core Evaluation Orchestrator

```python
class EvalEngine:
    """Main evaluation orchestrator"""

    def __init__(
        self,
        config: EvalConfig,
        client: OpenRouterClient,
        storage: StorageManager
    ):
        self.config = config
        self.client = client
        self.storage = storage
        self.checkpoint = CheckpointManager(storage)

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
        model_pairs: List[tuple]
    ) -> EvalResults:
        """Run complete evaluation"""

        # Initialize run
        run_id = self._create_run_id()
        await self.storage.initialize_run(run_id, self.config)

        # Check for resume
        if self.config.resume_from:
            completed = await self.checkpoint.load_progress()
            prompts = [p for p in prompts if p.prompt_id not in completed]

        total_comparisons = len(prompts) * len(model_pairs)
        progress = EvalProgress(total=total_comparisons)

        try:
            for prompt in prompts:
                for gemini_model, competitor_model in model_pairs:
                    # Generate responses
                    gemini_response = await self._generate_response(
                        prompt, gemini_model
                    )
                    competitor_response = await self._generate_response(
                        prompt, competitor_model
                    )

                    # Run judging
                    comparison = await self._run_judging(
                        prompt,
                        gemini_response,
                        competitor_response,
                        gemini_model,
                        competitor_model
                    )

                    # Save results
                    await self.storage.save_comparison(comparison)
                    await self.checkpoint.save_progress(prompt.prompt_id)

                    # Update progress
                    progress.update(comparison)

        except KeyboardInterrupt:
            # Graceful shutdown
            await self.checkpoint.save_final()
            raise

        return await self._compile_results(run_id)

    async def _generate_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> ModelResponse:
        """Generate a single model response"""

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt.render_prompt()}
        ]

        try:
            result, tracking = await self.client.complete_with_tracking(
                model=ModelConfig.get_openrouter_id(model),
                messages=messages,
                temperature=0.7
            )

            response_text = result["choices"][0]["message"]["content"]

            return ModelResponse(
                response_id=self._generate_id(),
                prompt_id=prompt.prompt_id,
                model_id=model,
                model_name=model,
                response_text=response_text,
                **tracking,
                **self._analyze_response(response_text),
                generated_at=datetime.now()
            )

        except Exception as e:
            # Handle failure - model auto-loses
            return ModelResponse(
                response_id=self._generate_id(),
                prompt_id=prompt.prompt_id,
                model_id=model,
                model_name=model,
                response_text="",
                is_failure=True,
                failure_category=self._categorize_failure(e),
                failure_reason=str(e),
                generated_at=datetime.now()
            )

    def _analyze_response(self, response_text: str) -> dict:
        """Analyze response characteristics"""
        words = response_text.split()
        paragraphs = response_text.split('\n\n')

        return {
            "word_count": len(words),
            "character_count": len(response_text),
            "has_greeting": self._detect_greeting(response_text),
            "has_signoff": self._detect_signoff(response_text),
            "uses_bullet_points": '•' in response_text or response_text.count('- ') > 2,
            "uses_headers": bool(re.search(r'^#+\s', response_text, re.MULTILINE)),
            "paragraph_count": len([p for p in paragraphs if p.strip()])
        }

    def _categorize_failure(self, error: Exception) -> str:
        """Categorize failure reason"""
        error_str = str(error).lower()

        if 'safety' in error_str or 'policy' in error_str or 'content' in error_str:
            return "safety_refusal"
        elif 'timeout' in error_str:
            return "timeout"
        elif 'rate' in error_str or '429' in error_str:
            return "rate_limit"
        elif 'capability' in error_str or 'cannot' in error_str:
            return "capability_limitation"
        else:
            return "other_error"
```

### 10.2 Judging System

```python
class JudgeSystem:
    """Multi-model, multi-persona judging system"""

    WRITING_EXPERT_PROMPT = """
    You are an expert writing evaluator with decades of experience in professional communication.

    Evaluate these two responses to the following writing task.

    ## Task Context
    {task_context}

    ## Writer Profile
    {writer_profile}

    ## Target Recipient
    {recipient_profile}

    ## Formality Level: {formality}
    ## Emotional Context: {emotional_context}
    ## Urgency: {urgency}

    ## Response A
    {response_a}

    ## Response B
    {response_b}

    Evaluate based on:
    1. **Writing Quality** (1-10): Grammar, vocabulary, flow, structure
    2. **Tone Appropriateness** (1-10): Does the tone match the formality level and context?
    3. **Length Appropriateness** (1-10): Is this the RIGHT length for this specific task?
    4. **Clarity** (1-10): Is the message clear and unambiguous?
    5. **Task Completion** (1-10): Does it fully address the task requirements?
    6. **Authenticity** (1-10): Does it read as natural human writing, not AI-generated?
    7. **Cliche/Boilerplate Avoidance** (1-10): Does it avoid AI patterns like "I hope this email finds you well"?

    {instruction_compliance_section}

    Provide your evaluation in this JSON format:
    {{
        "scores_a": {{"quality": X, "tone": X, "length": X, "clarity": X, "completion": X, "authenticity": X, "cliche_avoidance": X}},
        "scores_b": {{"quality": X, "tone": X, "length": X, "clarity": X, "completion": X, "authenticity": X, "cliche_avoidance": X}},
        "winner": "A" | "B" | "tie",
        "confidence": 0.0-1.0,
        "reasoning": "Detailed explanation..."
    }}
    """

    RECIPIENT_PERSONA_PROMPT = """
    You are simulating the perspective of {recipient_name}, {recipient_title}.

    You have received these two versions of a message and need to evaluate which
    better serves your needs as the recipient.

    ## Your Profile
    {recipient_full_profile}

    ## Your Relationship to Sender
    {relationship_context}

    ## The Message Task
    {task_context}

    ## Message A
    {response_a}

    ## Message B
    {response_b}

    As {recipient_name}, evaluate:
    1. **Effectiveness** (1-10): Does this message accomplish what it needs to?
    2. **Relevance** (1-10): Is the content relevant to your needs?
    3. **Actionability** (1-10): Is it clear what, if anything, you need to do?
    4. **Appropriateness** (1-10): Is this the right message for your relationship and context?
    5. **Professional Impression** (1-10): What impression does the sender make?

    Provide your evaluation in JSON format:
    {{
        "scores_a": {{"effectiveness": X, "relevance": X, "actionability": X, "appropriateness": X, "impression": X}},
        "scores_b": {{"effectiveness": X, "relevance": X, "actionability": X, "appropriateness": X, "impression": X}},
        "winner": "A" | "B" | "tie",
        "confidence": 0.0-1.0,
        "reasoning": "From your perspective as {recipient_name}..."
    }}
    """

    async def judge_comparison(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        presentation_order: tuple  # (model_a, model_b) - shuffled
    ) -> List[JudgeAggregation]:
        """Run full judging across all judges and personas"""

        results = []

        for judge_model in self.config.judge_models:
            for persona in ["writing_expert", "recipient"]:
                # Run best-of-5 votes
                votes = []
                for vote_num in range(self.config.votes_per_judge):
                    vote = await self._get_single_vote(
                        prompt,
                        response_a,
                        response_b,
                        judge_model,
                        persona,
                        vote_num,
                        presentation_order
                    )
                    votes.append(vote)

                # Aggregate votes
                winner = self._aggregate_votes(votes)
                results.append(JudgeAggregation(
                    judge_model=judge_model,
                    judge_persona=persona,
                    votes=votes,
                    winner=winner,
                    vote_distribution=self._count_votes(votes)
                ))

        return results

    def aggregate_final_result(
        self,
        judge_aggregations: List[JudgeAggregation]
    ) -> tuple[str, int]:
        """Apply majority-of-majorities aggregation"""

        # Get winner from each judge (across personas)
        judge_winners = {}
        for agg in judge_aggregations:
            if agg.judge_model not in judge_winners:
                judge_winners[agg.judge_model] = []
            judge_winners[agg.judge_model].append(agg.winner)

        # Majority winner per judge model
        model_winners = []
        for judge, winners in judge_winners.items():
            counts = {"A": 0, "B": 0, "tie": 0}
            for w in winners:
                counts[w] += 1
            if counts["A"] > counts["B"]:
                model_winners.append("A")
            elif counts["B"] > counts["A"]:
                model_winners.append("B")
            else:
                model_winners.append("tie")

        # Final majority
        final_counts = {"A": model_winners.count("A"),
                       "B": model_winners.count("B"),
                       "tie": model_winners.count("tie")}

        if final_counts["A"] > final_counts["B"]:
            final_winner = "A"
        elif final_counts["B"] > final_counts["A"]:
            final_winner = "B"
        else:
            final_winner = "tie"

        agreement = max(final_counts.values())

        return final_winner, agreement
```

### 10.3 Position Bias Prevention

```python
class PositionShuffler:
    """Deterministic shuffling to prevent position bias"""

    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)

    def get_presentation_order(
        self,
        prompt_id: str,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> tuple[ModelResponse, ModelResponse, str]:
        """Deterministically shuffle response presentation order"""

        # Use prompt_id + seed for deterministic but varied ordering
        combined_seed = hash(f"{self.seed}:{prompt_id}")
        local_rng = random.Random(combined_seed)

        if local_rng.random() < 0.5:
            # Gemini is A
            return (gemini_response, competitor_response, "gemini_first")
        else:
            # Competitor is A
            return (competitor_response, gemini_response, "competitor_first")
```

---

## 11. Cost Estimation

### 11.1 Live Cost Estimator

```python
class CostEstimator:
    """Estimate costs before and during evaluation runs"""

    def estimate_run_cost(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost for an evaluation run"""

        n_prompts = config.num_prompts
        n_model_pairs = len(config.model_pairs)
        n_judges = len(config.judge_models)
        n_votes = config.votes_per_judge
        n_personas = 2  # writing_expert + recipient

        # Estimate tokens per prompt
        avg_prompt_tokens = 500  # Input to model
        avg_response_tokens = 800  # Model output
        avg_judge_input_tokens = 2000  # Both responses + context
        avg_judge_output_tokens = 300  # Judgment

        # Response generation costs
        response_costs = {}
        for gemini, competitor in config.model_pairs:
            for model in [gemini, competitor]:
                model_config = ModelConfig.get_config(model)
                input_cost = avg_prompt_tokens * model_config["input_price_per_1k"] / 1000
                output_cost = avg_response_tokens * model_config["output_price_per_1k"] / 1000
                response_costs[model] = (input_cost + output_cost) * n_prompts

        total_response_cost = sum(response_costs.values())

        # Judging costs
        total_judge_calls = n_prompts * n_model_pairs * n_judges * n_votes * n_personas
        judge_costs = {}
        for judge in config.judge_models:
            judge_config = ModelConfig.get_config(judge)
            input_cost = avg_judge_input_tokens * judge_config["input_price_per_1k"] / 1000
            output_cost = avg_judge_output_tokens * judge_config["output_price_per_1k"] / 1000
            calls_per_judge = total_judge_calls // n_judges
            judge_costs[judge] = (input_cost + output_cost) * calls_per_judge

        total_judge_cost = sum(judge_costs.values())

        # Time estimation (assuming parallelization)
        avg_response_time = 3.0  # seconds
        avg_judge_time = 2.0  # seconds
        parallelization_factor = config.max_concurrent

        response_time = (n_prompts * n_model_pairs * 2 * avg_response_time) / parallelization_factor
        judge_time = (total_judge_calls * avg_judge_time) / parallelization_factor

        return CostEstimate(
            response_cost_range=(total_response_cost * 0.8, total_response_cost * 1.2),
            judge_cost_range=(total_judge_cost * 0.8, total_judge_cost * 1.2),
            total_cost_range=(
                (total_response_cost + total_judge_cost) * 0.8,
                (total_response_cost + total_judge_cost) * 1.2
            ),
            estimated_time_hours=(response_time + judge_time) / 3600,
            breakdown={
                "prompts": n_prompts,
                "model_pairs": n_model_pairs,
                "total_comparisons": n_prompts * n_model_pairs,
                "judge_calls": total_judge_calls,
                "response_costs": response_costs,
                "judge_costs": judge_costs
            }
        )
```

---

## 12. Presets Configuration

### 12.1 Ten Preset Levels

```python
class EvalPresets:
    """10 preset configurations from sanity check to full evaluation"""

    PRESETS = {
        1: {
            "name": "Sanity Check",
            "prompts": 5,
            "model_pairs": 1,  # Just Gemini Pro vs GPT-5.2
            "judges": 1,
            "votes_per_judge": 1,
            "description": "Does the system work?",
            "est_cost": "$1",
            "est_time": "2 min"
        },
        2: {
            "name": "Smoke Test",
            "prompts": 20,
            "model_pairs": 1,
            "judges": 1,
            "votes_per_judge": 3,
            "description": "Quick functionality test",
            "est_cost": "$5",
            "est_time": "5 min"
        },
        3: {
            "name": "Dev Iteration",
            "prompts": 50,
            "model_pairs": 2,
            "judges": 2,
            "votes_per_judge": 3,
            "description": "Development/debugging",
            "est_cost": "$25",
            "est_time": "15 min"
        },
        4: {
            "name": "Quick Sample",
            "prompts": 100,
            "model_pairs": 2,
            "judges": 2,
            "votes_per_judge": 5,
            "description": "Fast directional signal",
            "est_cost": "$75",
            "est_time": "30 min"
        },
        5: {
            "name": "Light Eval",
            "prompts": 200,
            "model_pairs": 3,
            "judges": 3,
            "votes_per_judge": 3,
            "description": "Light but meaningful eval",
            "est_cost": "$150",
            "est_time": "1 hr"
        },
        6: {
            "name": "Standard Eval",
            "prompts": 500,
            "model_pairs": 4,
            "judges": 3,
            "votes_per_judge": 5,
            "description": "Standard evaluation run",
            "est_cost": "$500",
            "est_time": "3 hrs"
        },
        7: {
            "name": "Thorough Eval",
            "prompts": 1000,
            "model_pairs": 4,
            "judges": 3,
            "votes_per_judge": 5,
            "description": "Thorough with good power",
            "est_cost": "$1,000",
            "est_time": "6 hrs"
        },
        8: {
            "name": "Comprehensive",
            "prompts": 2000,
            "model_pairs": "all",
            "judges": 3,
            "votes_per_judge": 5,
            "description": "High statistical power",
            "est_cost": "$2,500",
            "est_time": "12 hrs"
        },
        9: {
            "name": "Deep Dive",
            "prompts": 5000,
            "model_pairs": "all",
            "judges": 3,
            "votes_per_judge": 5,
            "description": "Publication-grade",
            "est_cost": "$6,000",
            "est_time": "24 hrs"
        },
        10: {
            "name": "Full Kaboodle",
            "prompts": 10000,
            "model_pairs": "all",
            "judges": 3,
            "votes_per_judge": 5,
            "description": "Maximum coverage",
            "est_cost": "$12,000+",
            "est_time": "48 hrs"
        }
    }

    @classmethod
    def get_preset(cls, level: int) -> EvalConfig:
        """Get configuration for a preset level"""
        preset = cls.PRESETS[level]

        model_pairs = preset["model_pairs"]
        if model_pairs == "all":
            model_pairs = ModelConfig.get_model_pairs("both")
        elif isinstance(model_pairs, int):
            model_pairs = ModelConfig.get_model_pairs("both")[:model_pairs]

        judges = preset["judges"]
        judge_models = ModelConfig.JUDGE_MODELS[:judges]

        return EvalConfig(
            preset_level=level,
            preset_name=preset["name"],
            num_prompts=preset["prompts"],
            model_pairs=model_pairs,
            judge_models=judge_models,
            votes_per_judge=preset["votes_per_judge"]
        )
```

---

## 13. Storage and Checkpointing

### 13.1 SQLite Database Schema

```python
class DatabaseSchema:
    """SQLite schema for evaluation results"""

    SCHEMA = """
    -- Run configuration
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        config_json TEXT,
        preset_level INTEGER,
        status TEXT,  -- 'running', 'completed', 'interrupted'
        random_seed INTEGER
    );

    -- Generated prompts
    CREATE TABLE IF NOT EXISTS prompts (
        prompt_id TEXT PRIMARY KEY,
        run_id TEXT,
        onet_task_id TEXT,
        onet_task_text TEXT,
        onet_occupation_code TEXT,
        onet_occupation_title TEXT,
        onet_job_zone INTEGER,
        naics_code TEXT,
        naics_description TEXT,
        writer_json TEXT,
        recipient_json TEXT,
        formality TEXT,
        urgency TEXT,
        emotional_context TEXT,
        full_prompt_json TEXT,
        rendered_prompt TEXT,
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    );

    -- Model responses
    CREATE TABLE IF NOT EXISTS responses (
        response_id TEXT PRIMARY KEY,
        prompt_id TEXT,
        model_id TEXT,
        response_text TEXT,
        response_time_ms INTEGER,
        input_tokens INTEGER,
        output_tokens INTEGER,
        word_count INTEGER,
        character_count INTEGER,
        has_greeting BOOLEAN,
        has_signoff BOOLEAN,
        uses_bullet_points BOOLEAN,
        uses_headers BOOLEAN,
        paragraph_count INTEGER,
        is_failure BOOLEAN,
        failure_category TEXT,
        failure_reason TEXT,
        generated_at TIMESTAMP,
        retry_count INTEGER,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Comparisons (one prompt, one model pair)
    CREATE TABLE IF NOT EXISTS comparisons (
        comparison_id TEXT PRIMARY KEY,
        prompt_id TEXT,
        gemini_model TEXT,
        competitor_model TEXT,
        gemini_response_id TEXT,
        competitor_response_id TEXT,
        presentation_order TEXT,  -- 'gemini_first' or 'competitor_first'
        final_winner TEXT,  -- 'gemini', 'competitor', 'tie'
        judge_agreement INTEGER,
        auto_loss_applied BOOLEAN,
        auto_loss_reason TEXT,
        completed_at TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
        FOREIGN KEY (gemini_response_id) REFERENCES responses(response_id),
        FOREIGN KEY (competitor_response_id) REFERENCES responses(response_id)
    );

    -- Individual judge votes
    CREATE TABLE IF NOT EXISTS judge_votes (
        vote_id TEXT PRIMARY KEY,
        comparison_id TEXT,
        judge_model TEXT,
        judge_persona TEXT,
        vote_number INTEGER,
        winner TEXT,
        confidence REAL,
        scores_a_json TEXT,
        scores_b_json TEXT,
        reasoning TEXT,
        judge_response_time_ms INTEGER,
        judge_input_tokens INTEGER,
        judge_output_tokens INTEGER,
        judged_at TIMESTAMP,
        FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
    );

    -- Aggregated judge results
    CREATE TABLE IF NOT EXISTS judge_aggregations (
        aggregation_id TEXT PRIMARY KEY,
        comparison_id TEXT,
        judge_model TEXT,
        judge_persona TEXT,
        winner TEXT,
        vote_distribution_json TEXT,
        FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
    );

    -- Indexes for efficient querying
    CREATE INDEX IF NOT EXISTS idx_prompts_run ON prompts(run_id);
    CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(onet_occupation_code);
    CREATE INDEX IF NOT EXISTS idx_prompts_naics ON prompts(naics_code);
    CREATE INDEX IF NOT EXISTS idx_responses_prompt ON responses(prompt_id);
    CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
    CREATE INDEX IF NOT EXISTS idx_comparisons_prompt ON comparisons(prompt_id);
    CREATE INDEX IF NOT EXISTS idx_comparisons_winner ON comparisons(final_winner);
    CREATE INDEX IF NOT EXISTS idx_votes_comparison ON judge_votes(comparison_id);
    """
```

### 13.2 Checkpoint Manager

```python
class CheckpointManager:
    """Manage checkpoints for resumable evaluation"""

    def __init__(self, storage: StorageManager, run_dir: Path):
        self.storage = storage
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"

    async def save_progress(self, prompt_id: str, comparison_id: str = None):
        """Save checkpoint after each completion"""
        checkpoint = await self.load_checkpoint()

        checkpoint["completed_prompts"].add(prompt_id)
        if comparison_id:
            checkpoint["completed_comparisons"].add(comparison_id)

        checkpoint["last_updated"] = datetime.now().isoformat()
        checkpoint["total_completed"] = len(checkpoint["completed_prompts"])

        await self._write_checkpoint(checkpoint)

    async def load_checkpoint(self) -> dict:
        """Load existing checkpoint or create new"""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file) as f:
                data = json.load(f)
                data["completed_prompts"] = set(data.get("completed_prompts", []))
                data["completed_comparisons"] = set(data.get("completed_comparisons", []))
                return data
        return {
            "completed_prompts": set(),
            "completed_comparisons": set(),
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "total_completed": 0
        }

    async def get_remaining_work(
        self,
        all_prompts: List[str],
        all_comparisons: List[str]
    ) -> tuple[List[str], List[str]]:
        """Get remaining prompts and comparisons after resume"""
        checkpoint = await self.load_checkpoint()

        remaining_prompts = [p for p in all_prompts
                           if p not in checkpoint["completed_prompts"]]
        remaining_comparisons = [c for c in all_comparisons
                                if c not in checkpoint["completed_comparisons"]]

        return remaining_prompts, remaining_comparisons

    async def _write_checkpoint(self, checkpoint: dict):
        """Write checkpoint to disk"""
        data = checkpoint.copy()
        data["completed_prompts"] = list(data["completed_prompts"])
        data["completed_comparisons"] = list(data["completed_comparisons"])

        with open(self.checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)
```

### 13.3 Results Export

```python
class ResultsExporter:
    """Export results to various formats"""

    async def export_csv(self, run_id: str, output_path: Path):
        """Export results to CSV"""
        query = """
        SELECT
            c.comparison_id,
            p.onet_occupation_title,
            p.onet_job_zone,
            p.naics_code,
            p.formality,
            c.gemini_model,
            c.competitor_model,
            c.final_winner,
            c.judge_agreement,
            r1.word_count as gemini_word_count,
            r2.word_count as competitor_word_count
        FROM comparisons c
        JOIN prompts p ON c.prompt_id = p.prompt_id
        JOIN responses r1 ON c.gemini_response_id = r1.response_id
        JOIN responses r2 ON c.competitor_response_id = r2.response_id
        WHERE p.run_id = ?
        """
        # Execute and write to CSV
        pass

    async def export_json(self, run_id: str, output_path: Path):
        """Export full results to JSON"""
        pass

    async def generate_run_summary(self, run_id: str) -> dict:
        """Generate summary statistics for a run"""
        pass
```

---

## 14. Live Progress TUI

### 14.1 Textual Application Structure

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive

class EvalProgressApp(App):
    """Live progress visualization TUI"""

    CSS = """
    #overall-progress {
        height: 5;
        margin: 1;
    }

    #model-pairs {
        height: auto;
        margin: 1;
    }

    #current-batch {
        height: 12;
        margin: 1;
    }

    #statistics {
        height: 10;
        margin: 1;
    }

    #activity-log {
        height: 8;
        margin: 1;
    }

    .panel-title {
        text-style: bold;
        color: cyan;
    }
    """

    BINDINGS = [
        ("q", "quit_safely", "Quit"),
        ("p", "pause", "Pause"),
        ("d", "toggle_detail", "Detail"),
        ("s", "show_stats", "Stats"),
        ("h", "show_help", "Help"),
    ]

    # Reactive state
    total_prompts = reactive(0)
    completed_prompts = reactive(0)
    current_phase = reactive("Generation")
    elapsed_time = reactive(0)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main"):
            yield OverallProgressPanel(id="overall-progress")
            yield ModelPairsPanel(id="model-pairs")
            yield CurrentBatchPanel(id="current-batch")

            with Horizontal():
                yield StatisticsPanel(id="statistics")
                yield ActivityLogPanel(id="activity-log")

            yield ErrorSummaryPanel(id="errors")

        yield Footer()

    async def update_progress(self, update: ProgressUpdate):
        """Update all panels with new progress data"""
        self.query_one("#overall-progress").update(update)
        self.query_one("#model-pairs").update(update)
        self.query_one("#current-batch").update(update)
        self.query_one("#statistics").update(update)
        self.query_one("#activity-log").add_entry(update)

    def action_quit_safely(self):
        """Graceful quit with checkpoint save"""
        self.notify("Saving checkpoint...")
        # Trigger checkpoint save
        self.exit(return_code=0)

    def action_pause(self):
        """Pause evaluation"""
        self.notify("Evaluation paused. Press 'p' to resume.")


class OverallProgressPanel(Static):
    """Overall progress display"""

    def update(self, data: ProgressUpdate):
        progress_pct = (data.completed / data.total) * 100 if data.total > 0 else 0

        self.update(f"""
        [bold]OVERALL PROGRESS[/bold]
        {'█' * int(progress_pct / 2.5)}{'░' * (40 - int(progress_pct / 2.5))}  {data.completed}/{data.total} ({progress_pct:.1f}%)

        Phase: {data.current_phase}  [Generation {'✓' if data.generation_complete else '◐'}] [Judging {'✓' if data.judging_complete else '◐'}] [Analysis {'◐' if data.analyzing else '○'}]
        Elapsed: {data.elapsed_str} | ETA: {data.eta_str}
        """)


class ModelPairsPanel(Static):
    """Per-model-pair progress"""

    def update(self, data: ProgressUpdate):
        lines = ["[bold]MODEL PAIRS[/bold]"]

        for pair, stats in data.model_pair_stats.items():
            gemini, competitor = pair
            progress = stats["completed"] / stats["total"] if stats["total"] > 0 else 0
            bar = '█' * int(progress * 20) + '░' * (20 - int(progress * 20))

            win_rate = f"{stats['win_rate']:.0f}% win" if stats['win_rate'] is not None else "--"
            status = "✓" if stats["completed"] == stats["total"] else ""

            lines.append(f"  {gemini} vs {competitor}: {bar} {stats['completed']}/{stats['total']} {status} [{win_rate}]")

        self.update("\n".join(lines))


class StatisticsPanel(Static):
    """Live statistics display"""

    def update(self, data: ProgressUpdate):
        self.update(f"""
        [bold]LIVE STATISTICS[/bold]

        Win Rates (Running)          │ Performance
        ─────────────────────────    │ ──────────────────────────────────
        vs GPT-5.2:  {data.win_rates.get('gpt-5.2', 'N/A')}    │ Avg response time: {data.avg_response_time:.1f}s
        vs Opus:     {data.win_rates.get('opus', 'N/A')}    │ Avg judge time:    {data.avg_judge_time:.1f}s
        vs Grok:     {data.win_rates.get('grok', 'N/A')}    │ API calls/min:     {data.api_calls_per_min}
                                     │ Est. cost so far:  ${data.cost_so_far:.2f}
        Judge Agreement: {data.judge_agreement:.2f} κ    │ Est. total cost:   ${data.est_total_cost:.2f}
        """)
```

---

## 15. Statistical Analysis

### 15.1 Win Rate Analysis

```python
from scipy import stats
import numpy as np

class WinRateAnalyzer:
    """Statistical analysis of win rates"""

    def calculate_win_rate(
        self,
        comparisons: List[ComparisonResult],
        model: str
    ) -> WinRateResult:
        """Calculate win rate with confidence interval"""

        wins = sum(1 for c in comparisons if c.final_winner == model)
        total = len(comparisons)
        ties = sum(1 for c in comparisons if c.final_winner == "tie")

        # Win rate (excluding ties)
        non_tie_total = total - ties
        if non_tie_total > 0:
            win_rate = wins / non_tie_total
        else:
            win_rate = 0.5

        # Wilson score confidence interval
        ci_lower, ci_upper = self._wilson_score_interval(
            wins, non_tie_total, confidence=0.95
        )

        return WinRateResult(
            win_rate=win_rate,
            wins=wins,
            losses=non_tie_total - wins,
            ties=ties,
            total=total,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=0.95
        )

    def _wilson_score_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Wilson score interval for binomial proportion"""
        if total == 0:
            return 0.0, 1.0

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p_hat = successes / total

        denominator = 1 + z**2 / total
        center = (p_hat + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * total)) / total) / denominator

        return max(0, center - margin), min(1, center + margin)

    def run_significance_test(
        self,
        comparisons: List[ComparisonResult],
        model_a: str,
        model_b: str
    ) -> SignificanceResult:
        """Run statistical significance test"""

        wins_a = sum(1 for c in comparisons if c.final_winner == model_a)
        wins_b = sum(1 for c in comparisons if c.final_winner == model_b)
        ties = sum(1 for c in comparisons if c.final_winner == "tie")

        # Binomial test (one-tailed)
        total_decided = wins_a + wins_b
        if total_decided > 0:
            p_value = stats.binom_test(wins_a, total_decided, 0.5, alternative='two-sided')
        else:
            p_value = 1.0

        # Effect size (Cohen's h for proportions)
        if total_decided > 0:
            p1 = wins_a / total_decided
            p2 = wins_b / total_decided
            effect_size = 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))
        else:
            effect_size = 0.0

        return SignificanceResult(
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=effect_size,
            effect_interpretation=self._interpret_effect_size(effect_size)
        )

    def _interpret_effect_size(self, h: float) -> str:
        """Interpret Cohen's h effect size"""
        h_abs = abs(h)
        if h_abs < 0.2:
            return "negligible"
        elif h_abs < 0.5:
            return "small"
        elif h_abs < 0.8:
            return "medium"
        else:
            return "large"


class InterJudgeAgreement:
    """Calculate inter-judge agreement metrics"""

    def calculate_cohens_kappa(
        self,
        votes: List[tuple[str, str]]  # (judge1_vote, judge2_vote)
    ) -> float:
        """Calculate Cohen's Kappa for two judges"""
        categories = ["A", "B", "tie"]

        # Build confusion matrix
        matrix = np.zeros((3, 3))
        for v1, v2 in votes:
            i = categories.index(v1)
            j = categories.index(v2)
            matrix[i, j] += 1

        total = len(votes)
        if total == 0:
            return 0.0

        # Observed agreement
        p_o = np.trace(matrix) / total

        # Expected agreement
        row_sums = matrix.sum(axis=1)
        col_sums = matrix.sum(axis=0)
        p_e = sum(row_sums[i] * col_sums[i] for i in range(3)) / (total ** 2)

        # Cohen's Kappa
        if p_e == 1:
            return 1.0
        return (p_o - p_e) / (1 - p_e)

    def calculate_fleiss_kappa(
        self,
        all_votes: List[List[str]]  # For each item, list of all judge votes
    ) -> float:
        """Calculate Fleiss' Kappa for multiple judges"""
        # Implementation for 3+ judges
        pass


class BiasDetector:
    """Detect systematic biases in evaluation"""

    def detect_position_bias(
        self,
        comparisons: List[ComparisonResult]
    ) -> PositionBiasResult:
        """Detect if judges prefer Response A or B systematically"""

        a_wins = sum(1 for c in c.judge_results
                    for v in c.votes
                    if v.winner == "A")
        b_wins = sum(1 for c in c.judge_results
                    for v in c.votes
                    if v.winner == "B")

        total = a_wins + b_wins
        if total == 0:
            return PositionBiasResult(detected=False, a_rate=0.5, b_rate=0.5)

        a_rate = a_wins / total
        b_rate = b_wins / total

        # Test for significant deviation from 50/50
        p_value = stats.binom_test(a_wins, total, 0.5, alternative='two-sided')

        return PositionBiasResult(
            detected=p_value < 0.05,
            a_rate=a_rate,
            b_rate=b_rate,
            p_value=p_value
        )

    def detect_length_bias(
        self,
        comparisons: List[ComparisonResult]
    ) -> LengthBiasResult:
        """Detect if judges prefer longer/shorter responses"""

        longer_wins = 0
        shorter_wins = 0

        for c in comparisons:
            len_a = c.response_a.word_count
            len_b = c.response_b.word_count

            if c.final_winner == "A" and len_a > len_b:
                longer_wins += 1
            elif c.final_winner == "B" and len_b > len_a:
                longer_wins += 1
            elif c.final_winner == "A" and len_a < len_b:
                shorter_wins += 1
            elif c.final_winner == "B" and len_b < len_a:
                shorter_wins += 1

        total = longer_wins + shorter_wins
        if total == 0:
            return LengthBiasResult(detected=False)

        longer_rate = longer_wins / total
        p_value = stats.binom_test(longer_wins, total, 0.5, alternative='two-sided')

        return LengthBiasResult(
            detected=p_value < 0.05,
            longer_win_rate=longer_rate,
            p_value=p_value,
            interpretation="Judges favor longer responses" if longer_rate > 0.5 else "Judges favor shorter responses"
        )
```

---

## 16. Weakness Analysis

### 16.1 Gemini Weakness Finder

```python
class WeaknessAnalyzer:
    """Identify specific areas where Gemini underperforms"""

    def analyze_weaknesses(
        self,
        comparisons: List[ComparisonResult],
        dimension: str  # 'occupation', 'industry', 'formality', 'task_category', etc.
    ) -> WeaknessReport:
        """Analyze win rates across a dimension to find weaknesses"""

        # Group comparisons by dimension
        grouped = self._group_by_dimension(comparisons, dimension)

        weakness_areas = []

        for group_value, group_comparisons in grouped.items():
            win_rate = self._calculate_gemini_win_rate(group_comparisons)

            if win_rate.win_rate < 0.45:  # Significant underperformance
                weakness_areas.append(WeaknessArea(
                    dimension=dimension,
                    value=group_value,
                    win_rate=win_rate.win_rate,
                    sample_size=win_rate.total,
                    confidence_interval=(win_rate.ci_lower, win_rate.ci_upper),
                    is_significant=win_rate.ci_upper < 0.5
                ))

        # Sort by severity
        weakness_areas.sort(key=lambda x: x.win_rate)

        return WeaknessReport(
            dimension=dimension,
            weaknesses=weakness_areas,
            strongest_areas=self._find_strongest_areas(grouped),
            total_comparisons=len(comparisons)
        )

    def multi_dimensional_analysis(
        self,
        comparisons: List[ComparisonResult]
    ) -> MultiDimensionalWeaknessReport:
        """Comprehensive weakness analysis across all dimensions"""

        dimensions = [
            'onet_occupation_code',
            'soc_major_group',
            'naics_sector',
            'job_zone',
            'formality',
            'urgency',
            'emotional_context',
            'task_category',
            'generation',
            'audience_size',
            'is_revision_task',
            'has_competing_objectives'
        ]

        reports = {}
        for dim in dimensions:
            reports[dim] = self.analyze_weaknesses(comparisons, dim)

        return MultiDimensionalWeaknessReport(
            dimension_reports=reports,
            critical_weaknesses=self._identify_critical_weaknesses(reports),
            recommendations=self._generate_recommendations(reports)
        )

    def _identify_critical_weaknesses(
        self,
        reports: dict
    ) -> List[CriticalWeakness]:
        """Identify the most severe, statistically significant weaknesses"""

        critical = []

        for dim, report in reports.items():
            for weakness in report.weaknesses:
                if weakness.is_significant and weakness.sample_size >= 20:
                    critical.append(CriticalWeakness(
                        dimension=dim,
                        value=weakness.value,
                        win_rate=weakness.win_rate,
                        sample_size=weakness.sample_size,
                        severity=self._calculate_severity(weakness)
                    ))

        critical.sort(key=lambda x: x.severity, reverse=True)
        return critical[:20]  # Top 20 critical weaknesses

    def _generate_recommendations(
        self,
        reports: dict
    ) -> List[str]:
        """Generate actionable recommendations based on weaknesses"""

        recommendations = []

        # Find patterns
        occupation_weaknesses = [w for w in reports['soc_major_group'].weaknesses
                                if w.is_significant]
        if occupation_weaknesses:
            recommendations.append(
                f"Focus on improving writing quality for {occupation_weaknesses[0].value} "
                f"occupations where win rate is only {occupation_weaknesses[0].win_rate:.0%}"
            )

        formality_weaknesses = [w for w in reports['formality'].weaknesses
                               if w.is_significant]
        if formality_weaknesses:
            level = formality_weaknesses[0].value
            recommendations.append(
                f"Gemini struggles with {level} writing contexts. "
                f"Consider fine-tuning on {level} professional communication."
            )

        return recommendations
```

---

## 17. PDF Report Generation

### 17.1 Report Generator

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import plotly.graph_objects as go
import plotly.express as px

class PDFReportGenerator:
    """Generate comprehensive PDF evaluation report"""

    def generate_report(
        self,
        run_id: str,
        output_path: Path
    ) -> Path:
        """Generate full PDF report"""

        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        story = []

        # Load data
        results = self._load_results(run_id)

        # 1. Executive Summary
        story.extend(self._generate_executive_summary(results))

        # 2. Methodology Overview
        story.extend(self._generate_methodology_section(results))

        # 3. Overall Results
        story.extend(self._generate_overall_results(results))

        # 4. Per-Model-Pair Analysis
        story.extend(self._generate_model_pair_analysis(results))

        # 5. Dimensional Breakdowns
        story.extend(self._generate_dimensional_analysis(results))

        # 6. Weakness Analysis
        story.extend(self._generate_weakness_section(results))

        # 7. Statistical Analysis
        story.extend(self._generate_statistical_section(results))

        # 8. Bias Detection
        story.extend(self._generate_bias_section(results))

        # 9. Appendices
        story.extend(self._generate_appendices(results))

        doc.build(story)
        return output_path

    def _generate_executive_summary(self, results) -> List:
        """Generate executive summary section"""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['Heading1']))
        elements.append(Spacer(1, 12))

        # Key findings
        summary_text = f"""
        <b>Evaluation Overview:</b><br/>
        This evaluation compared Gemini models against {len(results.model_pairs)} competitor models
        across {results.total_prompts} diverse professional writing tasks derived from O*NET
        occupational data.

        <br/><br/>
        <b>Key Findings:</b><br/>
        <ul>
        <li>Overall Gemini Pro win rate: {results.overall_gemini_pro_win_rate:.1%}
            ({results.gemini_pro_ci_lower:.1%} - {results.gemini_pro_ci_upper:.1%} 95% CI)</li>
        <li>Overall Gemini Flash win rate: {results.overall_gemini_flash_win_rate:.1%}</li>
        <li>Inter-judge agreement: {results.inter_judge_kappa:.2f} (Cohen's Kappa)</li>
        </ul>

        <br/>
        <b>Top Weaknesses Identified:</b><br/>
        <ul>
        {"".join(f"<li>{w.dimension}: {w.value} (win rate: {w.win_rate:.1%})</li>"
                 for w in results.critical_weaknesses[:5])}
        </ul>
        """

        elements.append(Paragraph(summary_text, self.styles['Normal']))

        # Summary chart
        chart = self._create_win_rate_summary_chart(results)
        elements.append(Image(chart, width=500, height=300))

        return elements

    def _generate_dimensional_analysis(self, results) -> List:
        """Generate dimensional breakdown section"""
        elements = []

        elements.append(Paragraph("Dimensional Analysis", self.styles['Heading1']))

        # By occupation group
        elements.append(Paragraph("Win Rates by Occupation Group", self.styles['Heading2']))
        occupation_chart = self._create_occupation_heatmap(results)
        elements.append(Image(occupation_chart, width=500, height=400))

        # By formality level
        elements.append(Paragraph("Win Rates by Formality Level", self.styles['Heading2']))
        formality_data = self._prepare_formality_table(results)
        elements.append(Table(formality_data))

        # By job zone
        elements.append(Paragraph("Win Rates by Job Zone (Skill Level)", self.styles['Heading2']))
        job_zone_chart = self._create_job_zone_chart(results)
        elements.append(Image(job_zone_chart, width=500, height=250))

        return elements

    def _create_win_rate_summary_chart(self, results) -> str:
        """Create summary win rate chart"""
        fig = go.Figure()

        for model_pair, stats in results.model_pair_stats.items():
            fig.add_trace(go.Bar(
                name=f"vs {model_pair[1]}",
                x=[model_pair[0]],
                y=[stats['win_rate']],
                error_y=dict(
                    type='data',
                    array=[stats['ci_upper'] - stats['win_rate']],
                    arrayminus=[stats['win_rate'] - stats['ci_lower']]
                )
            ))

        fig.add_hline(y=0.5, line_dash="dash", line_color="red",
                     annotation_text="50% (parity)")

        fig.update_layout(
            title="Gemini Win Rates by Model Pair (with 95% CI)",
            yaxis_title="Win Rate",
            yaxis_range=[0, 1],
            barmode='group'
        )

        chart_path = self._save_chart(fig, "win_rate_summary")
        return chart_path

    def _create_occupation_heatmap(self, results) -> str:
        """Create occupation group heatmap"""
        # Prepare data for heatmap
        occupation_groups = results.occupation_win_rates

        fig = px.imshow(
            occupation_groups,
            labels=dict(x="Competitor Model", y="Occupation Group", color="Win Rate"),
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0.5
        )

        fig.update_layout(title="Gemini Win Rates by Occupation Group and Competitor")

        chart_path = self._save_chart(fig, "occupation_heatmap")
        return chart_path
```

---

## 18. CLI Interface

### 18.1 Click-based CLI

```python
import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.group()
@click.option('--api-key', envvar='OPENROUTER_API_KEY', required=True,
              help='OpenRouter API key')
@click.pass_context
def cli(ctx, api_key):
    """Gemini Writing Evaluation Framework"""
    ctx.ensure_object(dict)
    ctx.obj['api_key'] = api_key


@cli.command()
@click.option('--preset', '-p', type=int, default=6,
              help='Preset level (1-10)')
@click.option('--prompts', '-n', type=int, default=None,
              help='Number of prompts (overrides preset)')
@click.option('--models', '-m', multiple=True,
              help='Model pairs to evaluate')
@click.option('--judges', '-j', multiple=True,
              help='Judge models to use')
@click.option('--votes', type=int, default=None,
              help='Votes per judge (overrides preset)')
@click.option('--occupations', multiple=True,
              help='Filter by O*NET occupation codes')
@click.option('--industries', multiple=True,
              help='Filter by NAICS codes')
@click.option('--job-zones', multiple=True, type=int,
              help='Filter by job zones (1-5)')
@click.option('--seed', type=int, default=None,
              help='Random seed for reproducibility')
@click.option('--dry-run', is_flag=True,
              help='Show estimate without running')
@click.pass_context
def run(ctx, preset, prompts, models, judges, votes, occupations,
        industries, job_zones, seed, dry_run):
    """Run an evaluation"""

    # Build configuration
    config = EvalPresets.get_preset(preset)

    if prompts:
        config.num_prompts = prompts
    if models:
        config.model_pairs = [tuple(m.split(',')) for m in models]
    if judges:
        config.judge_models = list(judges)
    if votes:
        config.votes_per_judge = votes
    if seed:
        config.random_seed = seed

    # Apply filters
    config.filters = {
        'occupations': occupations if occupations else None,
        'industries': industries if industries else None,
        'job_zones': job_zones if job_zones else None
    }

    # Show estimate
    estimator = CostEstimator()
    estimate = estimator.estimate_run_cost(config)

    display_estimate(estimate)

    if dry_run:
        return

    # Confirm
    if not click.confirm('Proceed with evaluation?'):
        return

    # Run evaluation
    asyncio.run(run_evaluation(ctx.obj['api_key'], config))


@cli.command()
@click.argument('run_dir', type=click.Path(exists=True))
def resume(run_dir):
    """Resume an interrupted evaluation"""
    asyncio.run(resume_evaluation(run_dir))


@cli.command()
@click.argument('run_dirs', type=click.Path(exists=True), nargs=-1)
def compare(run_dirs):
    """Compare results across multiple runs"""
    compare_runs(run_dirs)


@cli.command()
@click.argument('run_dir', type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['csv', 'json']),
              default='csv')
@click.option('--output', '-o', type=click.Path())
def export(run_dir, format, output):
    """Export results to CSV or JSON"""
    exporter = ResultsExporter()
    asyncio.run(exporter.export(run_dir, format, output))


@cli.command()
@click.argument('run_dir', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='report.pdf')
def report(run_dir, output):
    """Generate PDF report"""
    generator = PDFReportGenerator()
    path = generator.generate_report(run_dir, Path(output))
    console.print(f"Report generated: {path}")


@cli.command()
@click.argument('run_dir', type=click.Path(exists=True))
def view(run_dir):
    """Launch interactive TUI viewer"""
    app = ResultsViewerApp(run_dir)
    app.run()


def display_estimate(estimate: CostEstimate):
    """Display cost estimate in rich table"""
    console.print("\n[bold]EVAL RUN ESTIMATE[/bold]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Prompts:", str(estimate.breakdown['prompts']))
    table.add_row("Model pairs:", str(estimate.breakdown['model_pairs']))
    table.add_row("Total comparisons:", str(estimate.breakdown['total_comparisons']))
    table.add_row("", "")
    table.add_row("Judge calls:", str(estimate.breakdown['judge_calls']))
    table.add_row("", "")
    table.add_row("ESTIMATED COST", "")
    table.add_row("  Response generation:",
                 f"${estimate.response_cost_range[0]:.0f} - ${estimate.response_cost_range[1]:.0f}")
    table.add_row("  Judging:",
                 f"${estimate.judge_cost_range[0]:.0f} - ${estimate.judge_cost_range[1]:.0f}")
    table.add_row("  [bold]Total:[/bold]",
                 f"[bold]${estimate.total_cost_range[0]:.0f} - ${estimate.total_cost_range[1]:.0f}[/bold]")
    table.add_row("", "")
    table.add_row("ESTIMATED TIME:",
                 f"{estimate.estimated_time_hours:.1f} hours")

    console.print(table)


if __name__ == '__main__':
    cli()
```

---

## 19. Testing Strategy

### 19.1 Unit Tests

```python
# tests/unit/test_prompts.py

import pytest
from src.prompts.generator import Phase2Combiner
from src.prompts.schemas import WritingPrompt, FormattingLevel

class TestPromptGeneration:
    """Unit tests for prompt generation"""

    def test_formality_distribution_by_job_zone(self):
        """Test that formality distribution matches job zone"""
        combiner = Phase2Combiner()

        # Job zone 1 should skew casual
        samples = [combiner._sample_formality(1, random.Random(i))
                  for i in range(1000)]
        casual_count = sum(1 for s in samples
                         if s in [FormattingLevel.HIGHLY_CASUAL, FormattingLevel.CASUAL])
        assert casual_count / 1000 > 0.4  # More than 40% casual

        # Job zone 5 should skew formal
        samples = [combiner._sample_formality(5, random.Random(i))
                  for i in range(1000)]
        formal_count = sum(1 for s in samples
                          if s in [FormattingLevel.FORMAL, FormattingLevel.HIGHLY_FORMAL])
        assert formal_count / 1000 > 0.6  # More than 60% formal

    def test_prompt_id_deterministic(self):
        """Test that prompt IDs are deterministic with same seed"""
        combiner = Phase2Combiner()
        task = {"task_id": "test123", "task": "Write a memo"}

        id1 = combiner._generate_id(task, seed=42)
        id2 = combiner._generate_id(task, seed=42)
        id3 = combiner._generate_id(task, seed=43)

        assert id1 == id2
        assert id1 != id3

    def test_stratified_sampling(self):
        """Test stratified sampling produces even distribution"""
        sampler = StratifiedSampler()

        # Create prompts with varying job zones
        prompts = []
        for jz in range(1, 6):
            for i in range(100):
                prompts.append(WritingPrompt(
                    prompt_id=f"p_{jz}_{i}",
                    onet_job_zone=jz,
                    # ... other fields
                ))

        # Sample 50 prompts
        sampled = sampler.sample_prompts(prompts, 50, seed=42,
                                        stratification={'job_zone': True})

        # Check even distribution (10 per job zone +/- 2)
        for jz in range(1, 6):
            count = sum(1 for p in sampled if p.onet_job_zone == jz)
            assert 8 <= count <= 12


# tests/unit/test_eval.py

class TestJudging:
    """Unit tests for judging system"""

    def test_majority_aggregation(self):
        """Test majority-of-majorities logic"""
        judge_system = JudgeSystem()

        # Mock judge results
        mock_aggregations = [
            JudgeAggregation(judge_model="claude", winner="A"),
            JudgeAggregation(judge_model="gpt", winner="A"),
            JudgeAggregation(judge_model="gemini", winner="B"),
        ]

        final_winner, agreement = judge_system.aggregate_final_result(mock_aggregations)

        assert final_winner == "A"  # 2-1 majority
        assert agreement == 2

    def test_position_shuffling_deterministic(self):
        """Test that position shuffling is deterministic"""
        shuffler = PositionShuffler(seed=42)

        order1 = shuffler.get_presentation_order("prompt_1", mock_resp_a, mock_resp_b)
        order2 = shuffler.get_presentation_order("prompt_1", mock_resp_a, mock_resp_b)

        assert order1 == order2

    def test_auto_loss_on_failure(self):
        """Test that failed responses result in auto-loss"""
        # Implementation
        pass


# tests/unit/test_analysis.py

class TestStatistics:
    """Unit tests for statistical analysis"""

    def test_wilson_interval_edge_cases(self):
        """Test Wilson score interval handles edge cases"""
        analyzer = WinRateAnalyzer()

        # 0 successes
        ci = analyzer._wilson_score_interval(0, 100)
        assert ci[0] == 0.0
        assert ci[1] > 0.0

        # All successes
        ci = analyzer._wilson_score_interval(100, 100)
        assert ci[0] < 1.0
        assert ci[1] == 1.0

        # Empty sample
        ci = analyzer._wilson_score_interval(0, 0)
        assert ci == (0.0, 1.0)

    def test_cohens_kappa_perfect_agreement(self):
        """Test Cohen's Kappa with perfect agreement"""
        agreement = InterJudgeAgreement()

        votes = [("A", "A"), ("B", "B"), ("A", "A"), ("B", "B")]
        kappa = agreement.calculate_cohens_kappa(votes)

        assert kappa == 1.0

    def test_cohens_kappa_random_agreement(self):
        """Test Cohen's Kappa with random agreement"""
        agreement = InterJudgeAgreement()

        # Simulate random votes
        random.seed(42)
        votes = [(random.choice(["A", "B"]), random.choice(["A", "B"]))
                for _ in range(1000)]
        kappa = agreement.calculate_cohens_kappa(votes)

        # Should be close to 0
        assert -0.1 < kappa < 0.1
```

### 19.2 Integration Tests

```python
# tests/integration/test_e2e.py

@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests"""

    @pytest.fixture
    def api_client(self):
        """Create test API client"""
        return OpenRouterClient(
            api_key=os.environ.get("OPENROUTER_API_KEY_TEST"),
            max_concurrent=2
        )

    async def test_sanity_check_preset(self, api_client, tmp_path):
        """Test Level 1 preset (Sanity Check) runs successfully"""
        config = EvalPresets.get_preset(1)
        config.output_dir = tmp_path

        engine = EvalEngine(config, api_client, StorageManager(tmp_path))

        # Generate minimal prompts
        prompts = generate_test_prompts(5)

        results = await engine.run_evaluation(prompts, config.model_pairs)

        # Verify results
        assert results.total_comparisons == 5
        assert len(results.comparisons) == 5
        assert all(c.final_winner in ["gemini", "competitor", "tie"]
                  for c in results.comparisons)

    async def test_checkpoint_resume(self, api_client, tmp_path):
        """Test that interrupted evaluation can resume"""
        config = EvalPresets.get_preset(2)
        config.output_dir = tmp_path

        # Run partial evaluation
        engine = EvalEngine(config, api_client, StorageManager(tmp_path))
        prompts = generate_test_prompts(10)

        # Simulate interruption after 5 prompts
        async def limited_run():
            count = 0
            for prompt in prompts:
                if count >= 5:
                    raise KeyboardInterrupt()
                await engine._process_prompt(prompt)
                count += 1

        with pytest.raises(KeyboardInterrupt):
            await limited_run()

        # Verify checkpoint
        checkpoint = await engine.checkpoint.load_checkpoint()
        assert len(checkpoint["completed_prompts"]) == 5

        # Resume
        results = await engine.run_evaluation(prompts, config.model_pairs)

        # Verify completion
        assert results.total_comparisons == 10
```

---

## 20. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)

1. **Project Setup**
   - Initialize Python project with pyproject.toml
   - Set up directory structure
   - Configure testing framework (pytest)
   - Set up CI/CD

2. **Data Layer**
   - Implement SQLite database schema
   - Create O*NET extractor
   - Build NAICS mapping system
   - Implement company database

3. **API Layer**
   - Implement OpenRouter client
   - Add rate limiting
   - Add circuit breaker
   - Add retry logic

### Phase 2: Prompt Generation (Week 3-4)

4. **Prompt Schemas**
   - Define all Pydantic models
   - Implement validation

5. **Three-Phase Generation**
   - Implement Phase 1 (offline LLM generation)
   - Implement Phase 2 (algorithmic combination)
   - Implement Phase 3 (LLM enrichment)

6. **Sampling**
   - Implement stratified sampler
   - Build filter system

### Phase 3: Evaluation Engine (Week 5-6)

7. **Response Generation**
   - Implement model response collection
   - Add failure handling
   - Add response analysis

8. **Judging System**
   - Implement dual judge personas
   - Implement multi-model judging
   - Implement vote aggregation

9. **Checkpointing**
   - Implement checkpoint manager
   - Add resume functionality

### Phase 4: Analysis & Reporting (Week 7-8)

10. **Statistical Analysis**
    - Implement win rate calculator
    - Implement significance tests
    - Implement bias detection
    - Implement weakness finder

11. **Visualizations**
    - Create Plotly charts
    - Create heatmaps

12. **PDF Report**
    - Implement report generator
    - Create templates

### Phase 5: Interface & Polish (Week 9-10)

13. **CLI**
    - Implement Click commands
    - Add cost estimation display

14. **TUI**
    - Implement progress dashboard
    - Implement results viewer

15. **Testing & Documentation**
    - Write comprehensive tests
    - Write documentation
    - Performance optimization

---

## 21. Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| OpenRouter API instability | Circuit breaker, automatic retries, graceful degradation |
| High API costs | Pre-run cost estimation, presets for budget control, live cost tracking |
| Long run times | Parallelization, checkpointing, resume capability |
| Data loss | Immediate persistence, checkpoint after each comparison |
| Judge inconsistency | Multiple judges, best-of-5 voting, inter-judge agreement metrics |

### Methodological Risks

| Risk | Mitigation |
|------|------------|
| Position bias | Deterministic shuffling, bias detection |
| Model fingerprinting | Anonymized response presentation |
| Prompt bias | Use multiple models for generation, document bias sources |
| Insufficient statistical power | Power analysis, minimum sample recommendations |

---

## 22. Success Criteria

1. **Functional**: System can run all 10 preset levels successfully
2. **Reliable**: Checkpoint/resume works correctly across interruptions
3. **Accurate**: Inter-judge agreement > 0.6 Cohen's Kappa
4. **Comprehensive**: Reports include all required analyses
5. **Usable**: Clear CLI interface, intuitive TUI
6. **Documented**: Complete API documentation and user guide
