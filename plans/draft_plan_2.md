# Gemini Writing Evaluation Framework - Draft Implementation Plan 2

## Executive Summary

This document presents a comprehensive implementation plan for the Gemini Writing Evaluation Framework - a rigorous, scalable system for comparing Gemini 3.0 Pro/Flash against competing frontier LLMs on realistic professional writing tasks derived from O*NET occupational data. The framework emphasizes statistical robustness, cost transparency, full resumability, and actionable weakness identification.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GEMINI WRITING EVAL FRAMEWORK                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   CLI/CONFIG    │───▶│  ORCHESTRATOR   │───▶│   TUI DISPLAY   │          │
│  │    MANAGER      │    │     ENGINE      │    │    (Rich)       │          │
│  └─────────────────┘    └────────┬────────┘    └─────────────────┘          │
│                                  │                                           │
│         ┌────────────────────────┼────────────────────────────┐             │
│         ▼                        ▼                            ▼             │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐          │
│  │   PROMPT     │    │    EVALUATION     │    │    ANALYSIS &    │          │
│  │  GENERATION  │    │      ENGINE       │    │    REPORTING     │          │
│  │   PIPELINE   │    │                   │    │                  │          │
│  └──────┬───────┘    └────────┬──────────┘    └────────┬─────────┘          │
│         │                     │                        │                     │
│         ▼                     ▼                        ▼                     │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐          │
│  │   O*NET DB   │    │   OPENROUTER      │    │    RESULTS DB    │          │
│  │  + NAICS +   │    │   API CLIENT      │    │    (SQLite)      │          │
│  │  COMPANIES   │    │                   │    │                  │          │
│  └──────────────┘    └───────────────────┘    └──────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Components

| Component | Responsibility | Key Dependencies |
|-----------|---------------|------------------|
| CLI/Config Manager | User configuration, presets, dry-run estimates | Click/Typer, Pydantic |
| Orchestrator Engine | Workflow coordination, checkpointing, resumption | asyncio, State Machine |
| Prompt Generation Pipeline | O*NET extraction, persona enrichment, diversity sampling | SQLite, HTTPX |
| Evaluation Engine | Model invocation, judging, vote aggregation | OpenRouter API |
| TUI Display | Real-time progress visualization | Rich/Textual |
| Analysis & Reporting | Statistics, weakness detection, PDF generation | Pandas, Plotly, ReportLab |
| Results DB | Persistent storage, querying, exports | SQLite |

### 1.3 Technology Stack

```python
# Core Framework
python = ">=3.11"
asyncio        # Async I/O for concurrent API calls
httpx          # Modern async HTTP client
pydantic       # Data validation and settings

# Data & Storage
sqlite3        # Results database (built-in)
pandas         # Data analysis
numpy          # Numerical operations

# UI & Visualization
rich           # Terminal formatting and progress
textual        # Full TUI application
plotly         # Interactive charts
reportlab      # PDF generation

# CLI
typer          # CLI framework with type hints

# Testing
pytest         # Test framework
pytest-asyncio # Async test support
```

---

## 2. Data Models and Schemas

### 2.1 Core Pydantic Models

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

# ============ PROMPT SCHEMAS ============

class JobZone(int, Enum):
    """O*NET Job Zone skill levels"""
    LITTLE_PREP = 1
    SOME_PREP = 2
    MEDIUM_PREP = 3
    CONSIDERABLE_PREP = 4
    EXTENSIVE_PREP = 5

class PersonaGeneration(str, Enum):
    """Age/generation categories for personas"""
    GEN_Z = "gen_z"           # 1997-2012
    MILLENNIAL = "millennial"  # 1981-1996
    GEN_X = "gen_x"           # 1965-1980
    BOOMER = "boomer"         # 1946-1964
    SILENT = "silent"         # Before 1946

class EnglishVariant(str, Enum):
    """English language variants"""
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    """Position in communication thread"""
    INITIAL = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"

class EmotionalContext(str, Enum):
    """Emotional tone of the situation"""
    ROUTINE = "routine"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"
    NEGOTIATION = "negotiation"

class WriterPersona(BaseModel):
    """Complete writer persona specification"""
    name: str
    email: Optional[str] = None
    job_title: str
    occupation_code: str
    generation: PersonaGeneration
    years_experience: int
    skill_level: Literal["junior", "mid", "senior", "executive"]
    english_variant: EnglishVariant = EnglishVariant.EN_US

class RecipientPersona(BaseModel):
    """Complete recipient/reader specification"""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship: Literal["superior", "peer", "subordinate", "external", "public"]
    familiarity: Literal["first_contact", "acquaintance", "established", "close"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    technical_level: Literal["non_technical", "somewhat_technical", "technical", "expert"]

class CompanyContext(BaseModel):
    """Company grounding for realism"""
    name: str
    size: Literal["startup", "small", "medium", "large", "enterprise"]
    employee_count: Optional[int] = None
    industry_naics: str
    industry_name: str
    public_private: Literal["public", "private", "nonprofit", "government"]
    founded_year: Optional[int] = None
    hq_location: Optional[str] = None

class AttachmentReference(BaseModel):
    """Mock attachment or reference content"""
    type: Literal["report", "email", "meeting_notes", "resume", "document", "data"]
    description: str
    content_summary: str

class InstructionConstraint(BaseModel):
    """Explicit constraints to test instruction following"""
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    description: str

class WritingPrompt(BaseModel):
    """Complete writing prompt specification"""
    prompt_id: str

    # O*NET source
    onet_task_id: str
    onet_task_text: str
    occupation_code: str
    occupation_title: str
    job_zone: JobZone
    soc_major_group: str

    # Enriched prompt
    prompt_text: str

    # Context dimensions
    writer: WriterPersona
    recipient: RecipientPersona
    company: CompanyContext

    # Communication context
    formality_level: int = Field(ge=1, le=5)
    urgency_level: int = Field(ge=1, le=5)
    audience_size: Literal["one_on_one", "small_group", "department", "company_wide", "public"]
    message_position: MessagePosition
    emotional_context: EmotionalContext

    # Optional enrichments
    temporal_context: Optional[str] = None
    attachments: list[AttachmentReference] = []
    reply_context: Optional[str] = None
    tone_example: Optional[str] = None
    competing_objectives: Optional[str] = None
    constraints: list[InstructionConstraint] = []

    # Metadata
    inferred_channel: Optional[str] = None  # email, memo, report, etc.
    writing_category: str  # From O*NET reference categories
    sensitive_topic: Optional[str] = None
    language: str = "en"
    language_variant: str = "en-US"

    # Generation metadata
    generation_phase: Literal["phase1_llm", "phase2_algorithmic", "phase3_enriched"]
    random_seed: int
    created_at: datetime
```

### 2.2 Response and Judgment Schemas

```python
class ModelResponse(BaseModel):
    """Response from a model being evaluated"""
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
    finish_reason: str

    # Analysis metadata
    word_count: int
    character_count: int
    detected_format: list[str]  # bullet_points, headers, paragraphs, etc.
    greeting_pattern: Optional[str] = None
    signoff_pattern: Optional[str] = None

    # Failure tracking
    is_refusal: bool = False
    refusal_category: Optional[str] = None
    is_off_topic: bool = False

    created_at: datetime

class JudgeVote(BaseModel):
    """Single vote from a judge"""
    vote_id: str
    comparison_id: str
    judge_model: str
    judge_persona: Literal["writing_expert", "target_recipient"]
    vote_number: int  # 1-5 for best-of-5

    # Verdict
    winner: Literal["model_a", "model_b", "tie"]
    confidence: int = Field(ge=1, le=5)

    # Reasoning
    reasoning: str

    # Criteria scores (1-5 scale)
    quality_score_a: int
    quality_score_b: int
    length_appropriateness_a: int
    length_appropriateness_b: int
    tone_appropriateness_a: int
    tone_appropriateness_b: int
    effectiveness_a: int
    effectiveness_b: int
    clarity_a: int
    clarity_b: int
    task_completion_a: int
    task_completion_b: int
    authenticity_a: int
    authenticity_b: int
    cliche_avoidance_a: int
    cliche_avoidance_b: int

    # Instruction following (if applicable)
    instruction_compliance_a: Optional[int] = None
    instruction_compliance_b: Optional[int] = None

    # Position tracking for bias detection
    model_a_position: Literal["first", "second"]

    created_at: datetime

class Comparison(BaseModel):
    """Complete comparison between two models"""
    comparison_id: str
    prompt_id: str

    # Models
    model_a_id: str
    model_b_id: str
    model_a_name: str
    model_b_name: str

    # Responses
    response_a_id: str
    response_b_id: str

    # Judge votes
    votes: list[JudgeVote]

    # Aggregated results per judge model
    claude_verdict: Optional[Literal["model_a", "model_b", "tie"]] = None
    gpt_verdict: Optional[Literal["model_a", "model_b", "tie"]] = None
    gemini_verdict: Optional[Literal["model_a", "model_b", "tie"]] = None

    # Final aggregated result
    final_winner: Optional[Literal["model_a", "model_b", "tie"]] = None
    gemini_won: Optional[bool] = None  # True if Gemini won, False if opponent, None if tie

    # Metadata
    presentation_order_seed: int  # For reproducible shuffling
    created_at: datetime
```

### 2.3 Configuration Schemas

```python
class ModelConfig(BaseModel):
    """Configuration for a single model"""
    model_id: str
    display_name: str
    openrouter_id: str
    tier: Literal["pro", "flash"]
    is_gemini: bool
    input_price_per_1m: float
    output_price_per_1m: float

class JudgeConfig(BaseModel):
    """Judge configuration"""
    model: ModelConfig
    votes_per_comparison: int = 5
    personas: list[Literal["writing_expert", "target_recipient"]] = ["writing_expert", "target_recipient"]

class EvalConfig(BaseModel):
    """Complete evaluation configuration"""
    # Run identification
    run_id: str
    preset_name: Optional[str] = None

    # Models
    gemini_models: list[ModelConfig]
    competitor_models: list[ModelConfig]
    model_pairs: list[tuple[str, str]]  # (gemini_id, competitor_id)

    # Judges
    judges: list[JudgeConfig]

    # Prompt generation
    num_prompts: int
    random_seed: int

    # Filters
    occupation_filter: Optional[list[str]] = None  # O*NET codes or prefixes
    industry_filter: Optional[list[str]] = None    # NAICS codes
    job_zone_filter: Optional[list[int]] = None
    formality_filter: Optional[tuple[int, int]] = None
    generation_filter: Optional[list[PersonaGeneration]] = None

    # Sampling
    stratify_by: list[str] = ["job_zone", "soc_major_group"]
    max_per_occupation: Optional[int] = None
    max_per_industry: Optional[int] = None

    # API settings
    openrouter_api_key: str
    max_retries: int = 3
    timeout_seconds: int = 120
    max_concurrent_requests: int = 10
    rate_limit_rpm: int = 60

    # Output settings
    output_dir: str

    created_at: datetime
```

---

## 3. O*NET Data Integration

### 3.1 Database Access Layer

```python
# src/data/onet_extractor.py

import sqlite3
from typing import Iterator
from dataclasses import dataclass

@dataclass
class ONetTask:
    """Raw O*NET task data"""
    task_id: str
    onetsoc_code: str
    task: str
    task_type: str  # Core, Supplemental, or None
    occupation_title: str
    occupation_description: str
    job_zone: int
    soc_major_group: str
    soc_group_name: str

class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database"""

    WRITING_CATEGORIES = {
        'explicit_writing': [
            '%write%', '%draft%', '%document%', '%prepare report%',
            '%prepare%proposal%', '%compose%', '%author%'
        ],
        'correspondence': [
            '%correspond%', '%email%', '%letter%', '%memo%',
            '%notify%customer%', '%inform%customer%'
        ],
        'reports_presentations': [
            '%report%', '%present%finding%', '%present%result%',
            '%summarize%', '%prepare%presentation%'
        ],
        'persuasion_negotiation': [
            '%negotiat%', '%propos%', '%persuad%', '%recommend%',
            '%advise%client%', '%advise%customer%'
        ],
        'policy_procedure': [
            '%develop%polic%', '%implement%polic%', '%write%procedure%',
            '%prepare%guideline%', '%establish%standard%'
        ],
        'customer_communication': [
            '%customer%question%', '%client%question%', '%answer%question%',
            '%resolve%complaint%', '%explain%to%customer%', '%respond%to%customer%'
        ],
        'training_instruction': [
            '%train%staff%', '%train%employee%', '%instruct%',
            '%develop%curriculum%', '%prepare%manual%', '%prepare%training%'
        ],
        'internal_coordination': [
            '%confer with%', '%coordinate with%', '%collaborate with%',
            '%meet with%', '%communicate with%management%', '%communicate with%staff%'
        ],
        'contracts_legal': [
            '%prepare%contract%', '%draft%contract%', '%write%agreement%',
            '%prepare%permit%', '%prepare%compliance%'
        ],
        'feedback_evaluation': [
            '%evaluate%performance%', '%provide%feedback%',
            '%review%and%recommend%', '%assess%and%report%'
        ]
    }

    SOC_MAJOR_GROUPS = {
        '11': 'Management',
        '13': 'Business and Financial Operations',
        '15': 'Computer and Mathematical',
        '17': 'Architecture and Engineering',
        '19': 'Life, Physical, and Social Science',
        '21': 'Community and Social Service',
        '23': 'Legal',
        '25': 'Educational Instruction and Library',
        '27': 'Arts, Design, Entertainment, Sports, Media',
        '29': 'Healthcare Practitioners and Technical',
        '31': 'Healthcare Support',
        '33': 'Protective Service',
        '35': 'Food Preparation and Serving',
        '37': 'Building and Grounds Cleaning',
        '39': 'Personal Care and Service',
        '41': 'Sales and Related',
        '43': 'Office and Administrative Support',
        '45': 'Farming, Fishing, and Forestry',
        '47': 'Construction and Extraction',
        '49': 'Installation, Maintenance, Repair',
        '51': 'Production',
        '53': 'Transportation and Material Moving',
        '55': 'Military Specific'
    }

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def extract_writing_tasks(self,
                              categories: list[str] | None = None,
                              job_zones: list[int] | None = None,
                              soc_prefixes: list[str] | None = None) -> Iterator[ONetTask]:
        """
        Extract writing-relevant tasks with optional filtering.

        Args:
            categories: Specific writing categories to include (default: all)
            job_zones: Filter by job zone levels (1-5)
            soc_prefixes: Filter by SOC code prefixes (e.g., ['11', '13'])
        """
        conn = self._get_connection()

        # Build category conditions
        if categories is None:
            categories = list(self.WRITING_CATEGORIES.keys())

        like_conditions = []
        for cat in categories:
            if cat in self.WRITING_CATEGORIES:
                for pattern in self.WRITING_CATEGORIES[cat]:
                    like_conditions.append(f"t.task LIKE '{pattern}'")

        where_clause = f"({' OR '.join(like_conditions)})"

        # Add job zone filter
        if job_zones:
            where_clause += f" AND jz.job_zone IN ({','.join(map(str, job_zones))})"

        # Add SOC prefix filter
        if soc_prefixes:
            soc_conditions = [f"t.onetsoc_code LIKE '{p}%'" for p in soc_prefixes]
            where_clause += f" AND ({' OR '.join(soc_conditions)})"

        query = f"""
        SELECT DISTINCT
            t.task_id,
            t.onetsoc_code,
            t.task,
            t.task_type,
            o.title as occupation_title,
            o.description as occupation_description,
            jz.job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major_group
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        WHERE {where_clause}
        ORDER BY t.onetsoc_code, t.task_id
        """

        cursor = conn.execute(query)

        for row in cursor:
            soc_code = row['soc_major_group']
            yield ONetTask(
                task_id=row['task_id'],
                onetsoc_code=row['onetsoc_code'],
                task=row['task'],
                task_type=row['task_type'] or 'Unknown',
                occupation_title=row['occupation_title'],
                occupation_description=row['occupation_description'],
                job_zone=row['job_zone'],
                soc_major_group=soc_code,
                soc_group_name=self.SOC_MAJOR_GROUPS.get(soc_code, 'Unknown')
            )

        conn.close()

    def get_task_count_by_category(self) -> dict[str, int]:
        """Get count of writing tasks per category"""
        conn = self._get_connection()
        counts = {}

        for cat, patterns in self.WRITING_CATEGORIES.items():
            conditions = [f"task LIKE '{p}'" for p in patterns]
            query = f"SELECT COUNT(DISTINCT task_id) FROM task_statements WHERE {' OR '.join(conditions)}"
            cursor = conn.execute(query)
            counts[cat] = cursor.fetchone()[0]

        conn.close()
        return counts

    def get_occupation_writing_scores(self) -> dict[str, float]:
        """Get writing skill importance scores by occupation"""
        conn = self._get_connection()

        query = """
        SELECT o.onetsoc_code, o.title, sk.data_value as writing_score
        FROM occupation_data o
        JOIN skills sk ON o.onetsoc_code = sk.onetsoc_code
        JOIN content_model_reference cm ON sk.element_id = cm.element_id
        WHERE cm.element_name = 'Writing' AND sk.scale_id = 'IM'
        ORDER BY sk.data_value DESC
        """

        cursor = conn.execute(query)
        scores = {row['onetsoc_code']: row['writing_score'] for row in cursor}
        conn.close()
        return scores
```

### 3.2 NAICS Industry Mapping

```python
# src/data/naics_mapper.py

from dataclasses import dataclass

@dataclass
class NAICSIndustry:
    """NAICS industry sector"""
    code: str
    name: str
    sector: str

class NAICSMapper:
    """Map occupations to NAICS industries for diversity sampling"""

    # Top-level NAICS sectors
    SECTORS = {
        '11': 'Agriculture, Forestry, Fishing and Hunting',
        '21': 'Mining, Quarrying, and Oil and Gas Extraction',
        '22': 'Utilities',
        '23': 'Construction',
        '31-33': 'Manufacturing',
        '42': 'Wholesale Trade',
        '44-45': 'Retail Trade',
        '48-49': 'Transportation and Warehousing',
        '51': 'Information',
        '52': 'Finance and Insurance',
        '53': 'Real Estate and Rental and Leasing',
        '54': 'Professional, Scientific, and Technical Services',
        '55': 'Management of Companies and Enterprises',
        '56': 'Administrative and Support Services',
        '61': 'Educational Services',
        '62': 'Health Care and Social Assistance',
        '71': 'Arts, Entertainment, and Recreation',
        '72': 'Accommodation and Food Services',
        '81': 'Other Services',
        '92': 'Public Administration'
    }

    # SOC to likely NAICS mappings (simplified - real implementation would use BLS crosswalk)
    SOC_TO_NAICS = {
        '11': ['52', '54', '55', '92'],  # Management spans many
        '13': ['52', '54', '55'],         # Business/Financial
        '15': ['51', '54'],               # Computer/Math
        '17': ['23', '31-33', '54'],      # Engineering
        '19': ['54', '61', '62'],         # Science
        '21': ['62', '92'],               # Community/Social
        '23': ['54'],                     # Legal
        '25': ['61'],                     # Education
        '27': ['51', '71'],               # Arts/Media
        '29': ['62'],                     # Healthcare
        '31': ['62'],                     # Healthcare Support
        '33': ['92'],                     # Protective Service
        '35': ['72'],                     # Food Service
        '37': ['56', '81'],               # Cleaning/Grounds
        '39': ['81', '72'],               # Personal Care
        '41': ['42', '44-45'],            # Sales
        '43': ['52', '54', '55'],         # Office/Admin
        '45': ['11'],                     # Farming
        '47': ['23'],                     # Construction
        '49': ['48-49', '81'],            # Maintenance
        '51': ['31-33'],                  # Production
        '53': ['48-49'],                  # Transportation
        '55': ['92']                      # Military
    }

    def get_industries_for_occupation(self, soc_major: str) -> list[NAICSIndustry]:
        """Get likely NAICS industries for an occupation's SOC major group"""
        naics_codes = self.SOC_TO_NAICS.get(soc_major, ['54'])  # Default to professional services
        return [
            NAICSIndustry(
                code=code,
                name=self.SECTORS.get(code, 'Unknown'),
                sector=code[:2]
            )
            for code in naics_codes
        ]

    def sample_industry(self, soc_major: str, seed: int) -> NAICSIndustry:
        """Deterministically sample an industry for an occupation"""
        import random
        rng = random.Random(seed)
        industries = self.get_industries_for_occupation(soc_major)
        return rng.choice(industries)
```

---

## 4. Prompt Generation Pipeline

### 4.1 Three-Phase Generation Architecture

The prompt generation follows a three-phase approach as specified in PROMPT.md:

1. **Phase 1 - Offline LLM Generation**: Generate diverse persona/context variations
2. **Phase 2 - Algorithmic Combinations**: Deterministic combination of dimensions
3. **Phase 3 - LLM Enrichment**: Add realistic details for complex prompts

### 4.2 Company Database

```python
# src/data/company_database.py

from dataclasses import dataclass
from typing import Optional
import random

@dataclass
class Company:
    """Real company for grounding prompts"""
    name: str
    size: str  # startup, small, medium, large, enterprise
    employee_count: Optional[int]
    naics_codes: list[str]
    industry_description: str
    public_private: str
    founded_year: Optional[int]
    hq_location: str
    annual_revenue: Optional[str]

class CompanyDatabase:
    """
    Database of real companies for realistic prompt grounding.
    Uses built-in knowledge to provide company examples.
    """

    # Sample companies by size and industry (to be expanded)
    COMPANIES = {
        'enterprise': {
            '52': [  # Finance
                Company('JPMorgan Chase', 'enterprise', 300000, ['52', '5221'], 'Banking', 'public', 1799, 'New York, NY', '$130B+'),
                Company('Goldman Sachs', 'enterprise', 50000, ['52', '5231'], 'Investment Banking', 'public', 1869, 'New York, NY', '$50B+'),
                Company('Visa', 'enterprise', 30000, ['52', '5221'], 'Financial Services', 'public', 1958, 'San Francisco, CA', '$30B+'),
            ],
            '54': [  # Professional Services
                Company('Deloitte', 'enterprise', 415000, ['54', '5412'], 'Consulting', 'private', 1845, 'London, UK', '$60B+'),
                Company('McKinsey & Company', 'enterprise', 38000, ['54', '5416'], 'Management Consulting', 'private', 1926, 'New York, NY', '$15B+'),
                Company('Accenture', 'enterprise', 700000, ['54', '5415'], 'IT Consulting', 'public', 1989, 'Dublin, Ireland', '$60B+'),
            ],
            '51': [  # Information Technology
                Company('Microsoft', 'enterprise', 220000, ['51', '5112'], 'Technology', 'public', 1975, 'Redmond, WA', '$200B+'),
                Company('Google', 'enterprise', 180000, ['51', '5182'], 'Technology', 'public', 1998, 'Mountain View, CA', '$280B+'),
                Company('Amazon', 'enterprise', 1500000, ['51', '4541'], 'E-commerce/Cloud', 'public', 1994, 'Seattle, WA', '$500B+'),
            ],
            '62': [  # Healthcare
                Company('UnitedHealth Group', 'enterprise', 400000, ['62', '6241'], 'Healthcare', 'public', 1977, 'Minneapolis, MN', '$300B+'),
                Company('CVS Health', 'enterprise', 300000, ['62', '4461'], 'Pharmacy/Healthcare', 'public', 1963, 'Woonsocket, RI', '$320B+'),
                Company('Kaiser Permanente', 'enterprise', 300000, ['62', '6211'], 'Healthcare', 'nonprofit', 1945, 'Oakland, CA', '$90B+'),
            ],
        },
        'large': {
            '52': [
                Company('Charles Schwab', 'large', 35000, ['52', '5231'], 'Financial Services', 'public', 1971, 'Westlake, TX', '$20B+'),
                Company('Capital One', 'large', 55000, ['52', '5221'], 'Banking', 'public', 1994, 'McLean, VA', '$35B+'),
            ],
            '54': [
                Company('KPMG', 'large', 265000, ['54', '5412'], 'Accounting', 'private', 1987, 'Amstelveen, Netherlands', '$35B+'),
                Company('Booz Allen Hamilton', 'large', 32000, ['54', '5416'], 'Consulting', 'public', 1914, 'McLean, VA', '$9B+'),
            ],
            '51': [
                Company('Salesforce', 'large', 70000, ['51', '5112'], 'CRM Software', 'public', 1999, 'San Francisco, CA', '$30B+'),
                Company('Adobe', 'large', 30000, ['51', '5112'], 'Creative Software', 'public', 1982, 'San Jose, CA', '$18B+'),
            ],
        },
        'medium': {
            '54': [
                Company('Thoughtworks', 'medium', 12000, ['54', '5415'], 'Software Consulting', 'private', 1993, 'Chicago, IL', '$1B+'),
                Company('West Monroe', 'medium', 2000, ['54', '5416'], 'Management Consulting', 'private', 2002, 'Chicago, IL', '$500M+'),
            ],
            '51': [
                Company('Datadog', 'medium', 5000, ['51', '5112'], 'Monitoring Software', 'public', 2010, 'New York, NY', '$2B+'),
                Company('Notion', 'medium', 800, ['51', '5112'], 'Productivity Software', 'private', 2013, 'San Francisco, CA', '$100M+'),
            ],
        },
        'small': {
            '54': [
                Company('Lighthouse Labs', 'small', 150, ['54', '6114'], 'Tech Education', 'private', 2013, 'Vancouver, BC', '$20M+'),
                Company('Atomic Object', 'small', 70, ['54', '5415'], 'Software Development', 'private', 2001, 'Grand Rapids, MI', '$10M+'),
            ],
        },
        'startup': {
            '51': [
                Company('TechStartup (YC W24)', 'startup', 15, ['51', '5112'], 'AI Software', 'private', 2023, 'San Francisco, CA', 'Pre-revenue'),
                Company('HealthAI Labs', 'startup', 8, ['51', '62'], 'Healthcare AI', 'private', 2024, 'Boston, MA', 'Seed Stage'),
            ],
        }
    }

    def get_company(self, naics_sector: str, size: str, seed: int) -> Company:
        """Get a company matching industry and size, deterministically"""
        rng = random.Random(seed)

        # Try exact match first
        if size in self.COMPANIES and naics_sector in self.COMPANIES[size]:
            companies = self.COMPANIES[size][naics_sector]
            return rng.choice(companies)

        # Fall back to any company of that size
        if size in self.COMPANIES:
            all_companies = []
            for industry_companies in self.COMPANIES[size].values():
                all_companies.extend(industry_companies)
            if all_companies:
                return rng.choice(all_companies)

        # Ultimate fallback
        return Company(
            name=f"Acme {naics_sector} Corp",
            size=size,
            employee_count=100 if size == 'small' else 1000,
            naics_codes=[naics_sector],
            industry_description='General Business',
            public_private='private',
            founded_year=2010,
            hq_location='New York, NY',
            annual_revenue='$50M+'
        )
```

### 4.3 Name Generator for Personas

```python
# src/data/name_generator.py

import random
from dataclasses import dataclass

@dataclass
class PersonName:
    """Generated person name with demographic hints"""
    first_name: str
    last_name: str
    full_name: str
    email_name: str  # lowercase for email generation
    formal_name: str  # Dr., Mr., Ms. version if appropriate
    generation_hint: str

class NameGenerator:
    """
    Generate realistic, demographically diverse names.
    Names are chosen to reflect US workforce diversity.
    """

    # Name pools by perceived generation (not prescriptive, just variety)
    FIRST_NAMES = {
        'gen_z': {
            'neutral': ['Jordan', 'Riley', 'Casey', 'Quinn', 'Avery', 'Morgan'],
            'traditionally_masculine': ['Liam', 'Noah', 'Ethan', 'Aiden', 'Mason', 'Jayden'],
            'traditionally_feminine': ['Emma', 'Olivia', 'Sophia', 'Isabella', 'Mia', 'Zoe'],
        },
        'millennial': {
            'neutral': ['Taylor', 'Alex', 'Sam', 'Jamie', 'Drew', 'Blake'],
            'traditionally_masculine': ['Michael', 'Christopher', 'Matthew', 'Joshua', 'David', 'Daniel'],
            'traditionally_feminine': ['Jessica', 'Ashley', 'Amanda', 'Sarah', 'Jennifer', 'Melissa'],
        },
        'gen_x': {
            'neutral': ['Chris', 'Pat', 'Kim', 'Terry', 'Robin', 'Shannon'],
            'traditionally_masculine': ['Jason', 'Brian', 'Kevin', 'Scott', 'Eric', 'Jeff'],
            'traditionally_feminine': ['Lisa', 'Michelle', 'Kimberly', 'Angela', 'Heather', 'Stephanie'],
        },
        'boomer': {
            'neutral': ['Leslie', 'Dana', 'Lee', 'Dale', 'Gene', 'Lynn'],
            'traditionally_masculine': ['Robert', 'James', 'John', 'William', 'Richard', 'Thomas'],
            'traditionally_feminine': ['Linda', 'Barbara', 'Patricia', 'Susan', 'Nancy', 'Karen'],
        },
        'silent': {
            'neutral': ['Francis', 'Marion', 'Carroll', 'Aubrey', 'Laurie', 'Shirley'],
            'traditionally_masculine': ['Donald', 'George', 'Kenneth', 'Edward', 'Harold', 'Raymond'],
            'traditionally_feminine': ['Dorothy', 'Betty', 'Helen', 'Margaret', 'Ruth', 'Virginia'],
        }
    }

    # Diverse last names reflecting US demographics
    LAST_NAMES = [
        # European origin
        'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller', 'Davis',
        'Wilson', 'Anderson', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee',
        'Thompson', 'White', 'Harris', 'Clark', 'Lewis', 'Robinson', 'Walker',
        # Hispanic/Latino
        'Garcia', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez',
        'Perez', 'Sanchez', 'Ramirez', 'Torres', 'Flores', 'Rivera',
        # Asian
        'Chen', 'Wang', 'Liu', 'Kim', 'Park', 'Lee', 'Nguyen', 'Tran', 'Patel',
        'Shah', 'Singh', 'Kumar', 'Tanaka', 'Yamamoto', 'Suzuki',
        # Other origins
        'O\'Brien', 'Murphy', 'Kelly', 'Sullivan', 'Cohen', 'Friedman', 'Russo',
        'Romano', 'Schmidt', 'Mueller', 'Johansson', 'Andersen',
    ]

    def generate(self, generation: str, seed: int, use_formal: bool = False) -> PersonName:
        """Generate a diverse name deterministically"""
        rng = random.Random(seed)

        # Get generation-appropriate first name pool
        gen_names = self.FIRST_NAMES.get(generation, self.FIRST_NAMES['millennial'])

        # Pick randomly from all categories for diversity
        all_first_names = []
        for category in gen_names.values():
            all_first_names.extend(category)

        first_name = rng.choice(all_first_names)
        last_name = rng.choice(self.LAST_NAMES)

        full_name = f"{first_name} {last_name}"
        email_name = f"{first_name.lower()}.{last_name.lower().replace(\"'\", '')}"

        formal_prefix = rng.choice(['Dr.', 'Mr.', 'Ms.']) if use_formal else ''
        formal_name = f"{formal_prefix} {last_name}" if formal_prefix else full_name

        return PersonName(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email_name=email_name,
            formal_name=formal_name,
            generation_hint=generation
        )
```

### 4.4 Prompt Generator

```python
# src/prompts/generator.py

import random
import hashlib
from datetime import datetime
from typing import Optional
import asyncio

from ..data.onet_extractor import ONetExtractor, ONetTask
from ..data.naics_mapper import NAICSMapper, NAICSIndustry
from ..data.company_database import CompanyDatabase, Company
from ..data.name_generator import NameGenerator
from ..schemas import (
    WritingPrompt, WriterPersona, RecipientPersona, CompanyContext,
    PersonaGeneration, EnglishVariant, MessagePosition, EmotionalContext,
    JobZone, AttachmentReference, InstructionConstraint
)

class PromptGenerator:
    """
    Generate diverse, realistic writing prompts from O*NET tasks.
    Implements three-phase generation as per PROMPT.md.
    """

    def __init__(self,
                 onet_db_path: str,
                 openrouter_client: Optional['OpenRouterClient'] = None):
        self.onet = ONetExtractor(onet_db_path)
        self.naics = NAICSMapper()
        self.companies = CompanyDatabase()
        self.names = NameGenerator()
        self.openrouter = openrouter_client

    def _generate_seed(self, task_id: str, dimension: str, base_seed: int) -> int:
        """Generate deterministic seed for a specific dimension"""
        combined = f"{task_id}:{dimension}:{base_seed}"
        return int(hashlib.md5(combined.encode()).hexdigest()[:8], 16)

    def _select_generation(self, job_zone: int, seed: int) -> PersonaGeneration:
        """Select writer generation based on job zone and randomness"""
        rng = random.Random(seed)

        # Higher job zones more likely to have older workers (more experience)
        weights = {
            1: [0.4, 0.35, 0.15, 0.08, 0.02],   # Gen Z heavy for entry-level
            2: [0.25, 0.40, 0.20, 0.12, 0.03],
            3: [0.15, 0.35, 0.30, 0.15, 0.05],
            4: [0.10, 0.30, 0.35, 0.20, 0.05],
            5: [0.05, 0.25, 0.35, 0.28, 0.07],  # More senior for high skill
        }

        generations = list(PersonaGeneration)
        zone_weights = weights.get(job_zone, weights[3])
        return rng.choices(generations, weights=zone_weights, k=1)[0]

    def _select_formality(self, job_zone: int, emotional_context: EmotionalContext, seed: int) -> int:
        """Select formality level 1-5 based on context"""
        rng = random.Random(seed)

        # Base formality from job zone
        base = min(5, job_zone + 1)

        # Adjust for emotional context
        adjustments = {
            EmotionalContext.CRISIS: +1,
            EmotionalContext.BAD_NEWS: +1,
            EmotionalContext.NEGOTIATION: +1,
            EmotionalContext.CELEBRATION: -1,
            EmotionalContext.ROUTINE: 0,
            EmotionalContext.CONFLICT: 0,
        }

        adjusted = base + adjustments.get(emotional_context, 0)
        # Add some randomness
        adjusted += rng.choice([-1, 0, 0, 0, 1])

        return max(1, min(5, adjusted))

    def _select_urgency(self, task_text: str, seed: int) -> int:
        """Infer urgency from task text"""
        rng = random.Random(seed)

        # Keywords suggesting urgency
        urgent_keywords = ['immediate', 'urgent', 'deadline', 'emergency', 'asap', 'critical']
        routine_keywords = ['routine', 'regular', 'periodic', 'scheduled', 'maintain']

        task_lower = task_text.lower()

        if any(kw in task_lower for kw in urgent_keywords):
            return rng.choice([4, 5])
        elif any(kw in task_lower for kw in routine_keywords):
            return rng.choice([1, 2])
        else:
            return rng.choice([2, 3, 3, 4])  # Default to medium

    def _infer_channel(self, task_text: str) -> Optional[str]:
        """Infer communication channel from task text"""
        task_lower = task_text.lower()

        channel_keywords = {
            'email': ['email', 'e-mail', 'message'],
            'memo': ['memo', 'memorandum'],
            'report': ['report', 'analysis', 'assessment'],
            'letter': ['letter', 'correspondence'],
            'proposal': ['proposal', 'pitch', 'bid'],
            'presentation': ['presentation', 'present', 'brief'],
            'documentation': ['document', 'manual', 'guide'],
            'social_media': ['social media', 'post', 'tweet'],
        }

        for channel, keywords in channel_keywords.items():
            if any(kw in task_lower for kw in keywords):
                return channel

        return None  # Let LLM enrichment decide

    def _detect_sensitive_topic(self, task_text: str) -> Optional[str]:
        """Detect if task involves sensitive topics"""
        task_lower = task_text.lower()

        sensitive_patterns = {
            'hr_issues': ['performance', 'termination', 'complaint', 'disciplinary', 'harassment'],
            'legal_matters': ['legal', 'contract', 'compliance', 'liability', 'lawsuit'],
            'bad_news': ['rejection', 'denial', 'cancellation', 'layoff', 'closure'],
            'confidential': ['confidential', 'classified', 'proprietary', 'sensitive'],
            'conflict': ['dispute', 'conflict', 'grievance', 'complaint', 'mediat'],
        }

        for category, keywords in sensitive_patterns.items():
            if any(kw in task_lower for kw in keywords):
                return category

        return None

    async def generate_prompt_phase1(self,
                                     task: ONetTask,
                                     base_seed: int) -> WritingPrompt:
        """
        Phase 1: Generate basic prompt with algorithmic persona assignment.
        No LLM enrichment yet.
        """
        # Generate deterministic seeds for each dimension
        gen_seed = self._generate_seed(task.task_id, 'generation', base_seed)
        form_seed = self._generate_seed(task.task_id, 'formality', base_seed)
        urg_seed = self._generate_seed(task.task_id, 'urgency', base_seed)
        name_seed = self._generate_seed(task.task_id, 'names', base_seed)
        company_seed = self._generate_seed(task.task_id, 'company', base_seed)
        context_seed = self._generate_seed(task.task_id, 'context', base_seed)

        rng = random.Random(context_seed)

        # Select dimensions
        generation = self._select_generation(task.job_zone, gen_seed)
        emotional_context = rng.choice(list(EmotionalContext))
        formality = self._select_formality(task.job_zone, emotional_context, form_seed)
        urgency = self._select_urgency(task.task, urg_seed)

        # Generate industry and company
        industry = self.naics.sample_industry(task.soc_major_group, company_seed)
        company = self.companies.get_company(industry.code,
                                              rng.choice(['startup', 'small', 'medium', 'large', 'enterprise']),
                                              company_seed)

        # Generate names
        writer_name = self.names.generate(generation.value, name_seed)
        recipient_name = self.names.generate(
            rng.choice(list(PersonaGeneration)).value,
            name_seed + 1
        )

        # Determine skill level from job zone
        skill_levels = {1: 'junior', 2: 'junior', 3: 'mid', 4: 'senior', 5: 'executive'}
        skill_level = skill_levels.get(task.job_zone, 'mid')

        # Years experience based on generation and skill
        exp_ranges = {
            ('gen_z', 'junior'): (0, 3),
            ('gen_z', 'mid'): (2, 5),
            ('millennial', 'junior'): (1, 4),
            ('millennial', 'mid'): (3, 8),
            ('millennial', 'senior'): (6, 12),
            ('gen_x', 'mid'): (8, 15),
            ('gen_x', 'senior'): (12, 25),
            ('gen_x', 'executive'): (15, 30),
            ('boomer', 'senior'): (20, 35),
            ('boomer', 'executive'): (25, 40),
        }
        exp_range = exp_ranges.get((generation.value, skill_level), (5, 15))
        years_exp = rng.randint(*exp_range)

        # Create personas
        writer = WriterPersona(
            name=writer_name.full_name,
            email=f"{writer_name.email_name}@{company.name.lower().replace(' ', '')}.com",
            job_title=task.occupation_title,
            occupation_code=task.onetsoc_code,
            generation=generation,
            years_experience=years_exp,
            skill_level=skill_level,
            english_variant=EnglishVariant.EN_US
        )

        # Recipient relationship based on task context
        relationships = ['superior', 'peer', 'subordinate', 'external']
        relationship = rng.choice(relationships)

        recipient = RecipientPersona(
            name=recipient_name.full_name,
            email=f"{recipient_name.email_name}@external.com" if relationship == 'external' else None,
            job_title=rng.choice(['Manager', 'Director', 'Analyst', 'Specialist', 'Coordinator']),
            relationship=relationship,
            familiarity=rng.choice(['first_contact', 'acquaintance', 'established', 'close']),
            english_variant=rng.choice(list(EnglishVariant)),
            technical_level=rng.choice(['non_technical', 'somewhat_technical', 'technical', 'expert'])
        )

        # Company context
        company_context = CompanyContext(
            name=company.name,
            size=company.size,
            employee_count=company.employee_count,
            industry_naics=industry.code,
            industry_name=industry.name,
            public_private=company.public_private,
            founded_year=company.founded_year,
            hq_location=company.hq_location
        )

        # Message context
        audience_sizes = ['one_on_one', 'small_group', 'department', 'company_wide', 'public']
        audience_size = rng.choice(audience_sizes)
        message_position = rng.choice(list(MessagePosition))

        # Create prompt ID
        prompt_id = f"p_{task.task_id}_{base_seed}"

        # Infer channel and sensitive topics
        channel = self._infer_channel(task.task)
        sensitive = self._detect_sensitive_topic(task.task)

        # Determine writing category from task patterns
        writing_category = self._categorize_task(task.task)

        return WritingPrompt(
            prompt_id=prompt_id,
            onet_task_id=task.task_id,
            onet_task_text=task.task,
            occupation_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            job_zone=JobZone(task.job_zone),
            soc_major_group=task.soc_major_group,
            prompt_text=task.task,  # Will be enriched in Phase 3
            writer=writer,
            recipient=recipient,
            company=company_context,
            formality_level=formality,
            urgency_level=urgency,
            audience_size=audience_size,
            message_position=message_position,
            emotional_context=emotional_context,
            inferred_channel=channel,
            writing_category=writing_category,
            sensitive_topic=sensitive,
            generation_phase='phase2_algorithmic',
            random_seed=base_seed,
            created_at=datetime.utcnow()
        )

    def _categorize_task(self, task_text: str) -> str:
        """Categorize task into writing category"""
        task_lower = task_text.lower()

        for category, patterns in self.onet.WRITING_CATEGORIES.items():
            for pattern in patterns:
                clean_pattern = pattern.replace('%', '')
                if clean_pattern in task_lower:
                    return category

        return 'general_writing'

    async def enrich_prompt_phase3(self, prompt: WritingPrompt) -> WritingPrompt:
        """
        Phase 3: Enrich prompt with LLM-generated details.
        Adds temporal context, attachments, competing objectives, etc.
        """
        if not self.openrouter:
            return prompt

        # Build enrichment request
        enrichment_prompt = f"""
You are enriching a writing task prompt to make it more realistic and specific.

Original O*NET Task: {prompt.onet_task_text}
Writer: {prompt.writer.name}, {prompt.writer.job_title} at {prompt.company.name}
Writer Profile: {prompt.writer.generation.value} generation, {prompt.writer.years_experience} years experience
Recipient: {prompt.recipient.name}, {prompt.recipient.job_title}
Relationship: {prompt.recipient.relationship}, familiarity: {prompt.recipient.familiarity}
Company: {prompt.company.name} ({prompt.company.size}, {prompt.company.industry_name})
Formality: {prompt.formality_level}/5, Urgency: {prompt.urgency_level}/5
Emotional Context: {prompt.emotional_context.value}
Message Position: {prompt.message_position.value}

Generate a highly specific, realistic prompt that:
1. Keeps the core task from O*NET
2. Adds realistic temporal context if urgency > 3 (e.g., "The board meeting is Friday...")
3. Adds relevant attachment references if the task implies external content
4. Includes competing objectives if the task has inherent tensions
5. Makes names, companies, and context feel real and grounded

Return ONLY the enriched prompt text (no explanations).
"""

        try:
            response = await self.openrouter.complete(
                model="anthropic/claude-sonnet",  # Use same models being evaluated
                prompt=enrichment_prompt,
                max_tokens=1000
            )

            enriched_prompt = prompt.model_copy()
            enriched_prompt.prompt_text = response.text
            enriched_prompt.generation_phase = 'phase3_enriched'
            return enriched_prompt

        except Exception as e:
            # Fall back to non-enriched prompt
            return prompt

    async def generate_prompts(self,
                               num_prompts: int,
                               base_seed: int,
                               config: 'EvalConfig') -> list[WritingPrompt]:
        """Generate the full set of prompts for evaluation"""
        prompts = []

        # Extract all writing tasks
        tasks = list(self.onet.extract_writing_tasks(
            job_zones=config.job_zone_filter,
            soc_prefixes=config.occupation_filter
        ))

        # Sample tasks evenly across dimensions
        rng = random.Random(base_seed)
        rng.shuffle(tasks)

        # Apply stratification if requested
        if config.stratify_by:
            tasks = self._stratify_sample(tasks, num_prompts, config.stratify_by, rng)
        else:
            tasks = tasks[:num_prompts]

        # Generate prompts (Phase 1 + 2)
        for i, task in enumerate(tasks[:num_prompts]):
            task_seed = base_seed + i
            prompt = await self.generate_prompt_phase1(task, task_seed)
            prompts.append(prompt)

        # Phase 3: Enrich complex prompts
        if self.openrouter:
            enrichment_tasks = []
            for prompt in prompts:
                # Enrich prompts with high urgency or complex context
                if prompt.urgency_level >= 4 or prompt.sensitive_topic:
                    enrichment_tasks.append(self.enrich_prompt_phase3(prompt))

            if enrichment_tasks:
                enriched = await asyncio.gather(*enrichment_tasks)
                # Replace prompts with enriched versions
                enriched_map = {p.prompt_id: p for p in enriched}
                prompts = [enriched_map.get(p.prompt_id, p) for p in prompts]

        return prompts

    def _stratify_sample(self,
                         tasks: list[ONetTask],
                         num_prompts: int,
                         stratify_by: list[str],
                         rng: random.Random) -> list[ONetTask]:
        """Stratify sampling to ensure even distribution"""
        from collections import defaultdict

        # Group by stratification keys
        groups = defaultdict(list)
        for task in tasks:
            key_parts = []
            for dim in stratify_by:
                if dim == 'job_zone':
                    key_parts.append(str(task.job_zone))
                elif dim == 'soc_major_group':
                    key_parts.append(task.soc_major_group)
            key = '|'.join(key_parts)
            groups[key].append(task)

        # Sample evenly from each group
        per_group = max(1, num_prompts // len(groups))
        sampled = []

        for group_tasks in groups.values():
            rng.shuffle(group_tasks)
            sampled.extend(group_tasks[:per_group])

        # Fill remaining slots randomly
        remaining = num_prompts - len(sampled)
        if remaining > 0:
            unused = [t for t in tasks if t not in sampled]
            rng.shuffle(unused)
            sampled.extend(unused[:remaining])

        return sampled[:num_prompts]
```

---

## 5. OpenRouter API Integration

### 5.1 API Client Architecture

```python
# src/api/openrouter_client.py

import asyncio
import httpx
import time
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class APIResponse:
    """Standardized API response"""
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    latency_ms: int
    raw_response: dict

@dataclass
class RateLimitState:
    """Track rate limit state"""
    requests_this_minute: int = 0
    minute_start: float = field(default_factory=time.time)
    tokens_this_minute: int = 0

class OpenRouterClient:
    """
    Async client for OpenRouter API with rate limiting,
    retries, and circuit breaker.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self,
                 api_key: str,
                 max_retries: int = 3,
                 timeout_seconds: int = 120,
                 max_concurrent: int = 10,
                 rate_limit_rpm: int = 60):
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout_seconds
        self.rate_limit_rpm = rate_limit_rpm

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Rate limiting
        self.rate_state = RateLimitState()
        self.rate_lock = asyncio.Lock()

        # Circuit breaker
        self.failures = 0
        self.circuit_open = False
        self.circuit_opened_at: Optional[float] = None
        self.circuit_break_threshold = 5
        self.circuit_recovery_seconds = 60

        # HTTP client
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "gemini-writing-eval",
                "X-Title": "Gemini Writing Evaluation Framework"
            },
            timeout=httpx.Timeout(self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def _wait_for_rate_limit(self):
        """Wait if rate limit would be exceeded"""
        async with self.rate_lock:
            now = time.time()

            # Reset if new minute
            if now - self.rate_state.minute_start >= 60:
                self.rate_state.requests_this_minute = 0
                self.rate_state.minute_start = now

            # Wait if at limit
            if self.rate_state.requests_this_minute >= self.rate_limit_rpm:
                wait_time = 60 - (now - self.rate_state.minute_start)
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    self.rate_state.requests_this_minute = 0
                    self.rate_state.minute_start = time.time()

            self.rate_state.requests_this_minute += 1

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows request"""
        if not self.circuit_open:
            return True

        # Check if recovery period passed
        if time.time() - self.circuit_opened_at >= self.circuit_recovery_seconds:
            self.circuit_open = False
            self.failures = 0
            logger.info("Circuit breaker closed, resuming requests")
            return True

        return False

    def _record_failure(self):
        """Record a failure for circuit breaker"""
        self.failures += 1
        if self.failures >= self.circuit_break_threshold:
            self.circuit_open = True
            self.circuit_opened_at = time.time()
            logger.warning(f"Circuit breaker opened after {self.failures} failures")

    def _record_success(self):
        """Record success, reset failure count"""
        self.failures = 0

    async def complete(self,
                       model: str,
                       prompt: str,
                       max_tokens: int = 4096,
                       temperature: float = 0.7,
                       system_prompt: Optional[str] = None) -> APIResponse:
        """
        Make a completion request with retries and rate limiting.
        """
        if not self._check_circuit_breaker():
            raise Exception("Circuit breaker open, API temporarily unavailable")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        last_error = None

        for attempt in range(self.max_retries):
            try:
                await self._wait_for_rate_limit()

                async with self.semaphore:
                    start_time = time.time()

                    response = await self.client.post(
                        "/chat/completions",
                        json=request_body
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 429:
                        # Rate limited, exponential backoff
                        wait = (2 ** attempt) + (0.1 * attempt)
                        logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1})")
                        await asyncio.sleep(wait)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    self._record_success()

                    return APIResponse(
                        text=data["choices"][0]["message"]["content"],
                        model=data.get("model", model),
                        input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                        output_tokens=data.get("usage", {}).get("completion_tokens", 0),
                        finish_reason=data["choices"][0].get("finish_reason", "unknown"),
                        latency_ms=latency_ms,
                        raw_response=data
                    )

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    logger.warning(f"Server error on attempt {attempt + 1}: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                await asyncio.sleep(2 ** attempt)

        self._record_failure()
        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    async def get_model_info(self) -> list[dict]:
        """Get available models from OpenRouter"""
        response = await self.client.get("/models")
        response.raise_for_status()
        return response.json().get("data", [])
```

### 5.2 Model Configuration

```python
# src/config/models.py

from dataclasses import dataclass
from typing import Literal

@dataclass
class ModelSpec:
    """Specification for a model"""
    id: str
    name: str
    openrouter_id: str
    tier: Literal["pro", "flash"]
    is_gemini: bool
    input_price_per_1m: float  # USD per 1M input tokens
    output_price_per_1m: float  # USD per 1M output tokens
    context_window: int
    max_output: int

# Pro-tier models (as of Jan 2026)
MODELS = {
    # Gemini
    "gemini-3-pro": ModelSpec(
        id="gemini-3-pro",
        name="Gemini 3.0 Pro",
        openrouter_id="google/gemini-3.0-pro",
        tier="pro",
        is_gemini=True,
        input_price_per_1m=5.0,
        output_price_per_1m=15.0,
        context_window=1000000,
        max_output=8192
    ),
    "gemini-3-flash": ModelSpec(
        id="gemini-3-flash",
        name="Gemini 3.0 Flash",
        openrouter_id="google/gemini-3.0-flash",
        tier="flash",
        is_gemini=True,
        input_price_per_1m=0.5,
        output_price_per_1m=1.5,
        context_window=1000000,
        max_output=8192
    ),

    # Pro-tier competitors
    "gpt-5.2-thinking": ModelSpec(
        id="gpt-5.2-thinking",
        name="GPT-5.2 Thinking",
        openrouter_id="openai/gpt-5.2-thinking",
        tier="pro",
        is_gemini=False,
        input_price_per_1m=10.0,
        output_price_per_1m=30.0,
        context_window=128000,
        max_output=16384
    ),
    "claude-opus-4.5": ModelSpec(
        id="claude-opus-4.5",
        name="Claude Opus 4.5",
        openrouter_id="anthropic/claude-opus-4.5",
        tier="pro",
        is_gemini=False,
        input_price_per_1m=15.0,
        output_price_per_1m=75.0,
        context_window=200000,
        max_output=8192
    ),
    "grok-4.1-thinking": ModelSpec(
        id="grok-4.1-thinking",
        name="Grok-4.1 Thinking",
        openrouter_id="x-ai/grok-4.1-thinking",
        tier="pro",
        is_gemini=False,
        input_price_per_1m=8.0,
        output_price_per_1m=24.0,
        context_window=131072,
        max_output=8192
    ),
    "kimi-k2-thinking": ModelSpec(
        id="kimi-k2-thinking",
        name="Kimi K2 Thinking",
        openrouter_id="moonshot/kimi-k2-thinking",
        tier="pro",
        is_gemini=False,
        input_price_per_1m=6.0,
        output_price_per_1m=18.0,
        context_window=128000,
        max_output=8192
    ),

    # Flash-tier competitors
    "gpt-4.1": ModelSpec(
        id="gpt-4.1",
        name="GPT-4.1",
        openrouter_id="openai/gpt-4.1",
        tier="flash",
        is_gemini=False,
        input_price_per_1m=2.5,
        output_price_per_1m=10.0,
        context_window=128000,
        max_output=16384
    ),
    "claude-sonnet": ModelSpec(
        id="claude-sonnet",
        name="Claude Sonnet",
        openrouter_id="anthropic/claude-sonnet-4",
        tier="flash",
        is_gemini=False,
        input_price_per_1m=3.0,
        output_price_per_1m=15.0,
        context_window=200000,
        max_output=8192
    ),
}

# Default model pairs
PRO_PAIRS = [
    ("gemini-3-pro", "gpt-5.2-thinking"),
    ("gemini-3-pro", "claude-opus-4.5"),
    ("gemini-3-pro", "grok-4.1-thinking"),
    ("gemini-3-pro", "kimi-k2-thinking"),
]

FLASH_PAIRS = [
    ("gemini-3-flash", "gpt-4.1"),
    ("gemini-3-flash", "claude-sonnet"),
]

# Judge models
JUDGE_MODELS = [
    MODELS["claude-opus-4.5"],
    MODELS["gpt-5.2-thinking"],
    MODELS["gemini-3-pro"],
]
```

### 5.3 Cost Estimator

```python
# src/config/cost_estimator.py

from dataclasses import dataclass
from .models import ModelSpec, MODELS, JUDGE_MODELS

@dataclass
class CostEstimate:
    """Cost estimate for an evaluation run"""
    response_generation_low: float
    response_generation_high: float
    judging_low: float
    judging_high: float
    total_low: float
    total_high: float

    # Breakdown
    num_prompts: int
    num_model_pairs: int
    num_comparisons: int
    num_judge_calls: int

    # Token estimates
    avg_prompt_tokens: int
    avg_response_tokens: int
    avg_judge_input_tokens: int
    avg_judge_output_tokens: int

class CostEstimator:
    """Estimate costs for evaluation runs"""

    # Average token estimates (can be refined with real data)
    AVG_PROMPT_TOKENS = 500
    AVG_RESPONSE_TOKENS = 800
    AVG_JUDGE_INPUT_TOKENS = 2500  # Prompt + both responses + rubric
    AVG_JUDGE_OUTPUT_TOKENS = 500

    def estimate(self,
                 num_prompts: int,
                 model_pairs: list[tuple[str, str]],
                 judge_configs: list[dict],
                 personas_per_judge: int = 2) -> CostEstimate:
        """
        Estimate total cost for an evaluation run.

        Args:
            num_prompts: Number of prompts to evaluate
            model_pairs: List of (gemini_id, competitor_id) tuples
            judge_configs: List of {model_id, votes} dicts
            personas_per_judge: Number of judge personas (default 2)
        """
        num_pairs = len(model_pairs)
        num_comparisons = num_prompts * num_pairs

        # Response generation cost
        response_cost_low = 0.0
        response_cost_high = 0.0

        for gemini_id, competitor_id in model_pairs:
            gemini = MODELS[gemini_id]
            competitor = MODELS[competitor_id]

            # Each comparison needs 2 responses (Gemini + competitor)
            for model in [gemini, competitor]:
                input_cost = (num_prompts * self.AVG_PROMPT_TOKENS / 1_000_000) * model.input_price_per_1m
                output_cost_low = (num_prompts * self.AVG_RESPONSE_TOKENS * 0.7 / 1_000_000) * model.output_price_per_1m
                output_cost_high = (num_prompts * self.AVG_RESPONSE_TOKENS * 1.3 / 1_000_000) * model.output_price_per_1m

                response_cost_low += input_cost + output_cost_low
                response_cost_high += input_cost + output_cost_high

        # Judge cost
        total_judge_calls = 0
        judge_cost_low = 0.0
        judge_cost_high = 0.0

        for jc in judge_configs:
            judge = MODELS[jc['model_id']]
            votes = jc.get('votes', 5)
            calls = num_comparisons * votes * personas_per_judge
            total_judge_calls += calls

            input_cost = (calls * self.AVG_JUDGE_INPUT_TOKENS / 1_000_000) * judge.input_price_per_1m
            output_cost_low = (calls * self.AVG_JUDGE_OUTPUT_TOKENS * 0.7 / 1_000_000) * judge.output_price_per_1m
            output_cost_high = (calls * self.AVG_JUDGE_OUTPUT_TOKENS * 1.3 / 1_000_000) * judge.output_price_per_1m

            judge_cost_low += input_cost + output_cost_low
            judge_cost_high += input_cost + output_cost_high

        return CostEstimate(
            response_generation_low=response_cost_low,
            response_generation_high=response_cost_high,
            judging_low=judge_cost_low,
            judging_high=judge_cost_high,
            total_low=response_cost_low + judge_cost_low,
            total_high=response_cost_high + judge_cost_high,
            num_prompts=num_prompts,
            num_model_pairs=num_pairs,
            num_comparisons=num_comparisons,
            num_judge_calls=total_judge_calls,
            avg_prompt_tokens=self.AVG_PROMPT_TOKENS,
            avg_response_tokens=self.AVG_RESPONSE_TOKENS,
            avg_judge_input_tokens=self.AVG_JUDGE_INPUT_TOKENS,
            avg_judge_output_tokens=self.AVG_JUDGE_OUTPUT_TOKENS
        )

    def estimate_time(self,
                      num_comparisons: int,
                      num_judge_calls: int,
                      max_concurrent: int = 10,
                      avg_response_time_s: float = 3.0,
                      avg_judge_time_s: float = 1.5) -> tuple[float, float]:
        """Estimate time in hours (low, high)"""
        # Response generation
        response_batches = num_comparisons * 2 / max_concurrent  # 2 models per comparison
        response_time = response_batches * avg_response_time_s

        # Judging
        judge_batches = num_judge_calls / max_concurrent
        judge_time = judge_batches * avg_judge_time_s

        total_seconds = response_time + judge_time

        # Add buffer for rate limits and retries
        low_hours = total_seconds / 3600
        high_hours = (total_seconds * 1.5) / 3600  # 50% buffer

        return (low_hours, high_hours)
```

---

## 6. Evaluation Engine

### 6.1 Core Evaluation Loop

```python
# src/eval/engine.py

import asyncio
import random
from typing import AsyncIterator, Optional
from datetime import datetime
import logging

from ..api.openrouter_client import OpenRouterClient, APIResponse
from ..schemas import (
    WritingPrompt, ModelResponse, JudgeVote, Comparison,
    EvalConfig
)
from ..storage.checkpoint import CheckpointManager
from .judge_prompts import build_judge_prompt

logger = logging.getLogger(__name__)

class EvaluationEngine:
    """
    Core evaluation engine that orchestrates:
    1. Response generation from models
    2. Judge voting
    3. Result aggregation
    """

    def __init__(self,
                 config: EvalConfig,
                 openrouter: OpenRouterClient,
                 checkpoint_mgr: CheckpointManager):
        self.config = config
        self.openrouter = openrouter
        self.checkpoint = checkpoint_mgr

    async def generate_response(self,
                                prompt: WritingPrompt,
                                model_id: str) -> ModelResponse:
        """Generate a response from a model for a prompt"""
        model = self.config.get_model(model_id)

        # Build the full prompt with context
        full_prompt = self._build_model_prompt(prompt)

        start_time = datetime.utcnow()

        try:
            response = await self.openrouter.complete(
                model=model.openrouter_id,
                prompt=full_prompt,
                max_tokens=model.max_output,
                temperature=0.7
            )

            # Analyze response
            word_count = len(response.text.split())
            char_count = len(response.text)
            formats = self._detect_formats(response.text)
            greeting = self._detect_greeting(response.text)
            signoff = self._detect_signoff(response.text)

            # Check for refusal/off-topic
            is_refusal, refusal_cat = self._detect_refusal(response.text)
            is_off_topic = self._detect_off_topic(response.text, prompt)

            return ModelResponse(
                response_id=f"r_{prompt.prompt_id}_{model_id}_{int(datetime.utcnow().timestamp())}",
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                model_name=model.name,
                response_text=response.text,
                response_time_ms=response.latency_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                finish_reason=response.finish_reason,
                word_count=word_count,
                character_count=char_count,
                detected_format=formats,
                greeting_pattern=greeting,
                signoff_pattern=signoff,
                is_refusal=is_refusal,
                refusal_category=refusal_cat,
                is_off_topic=is_off_topic,
                created_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to generate response for {model_id}: {e}")
            # Return failure response
            return ModelResponse(
                response_id=f"r_{prompt.prompt_id}_{model_id}_failed",
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                model_name=model.name,
                response_text="",
                response_time_ms=0,
                input_tokens=0,
                output_tokens=0,
                finish_reason="error",
                word_count=0,
                character_count=0,
                detected_format=[],
                is_refusal=True,
                refusal_category="api_error",
                is_off_topic=False,
                created_at=datetime.utcnow()
            )

    def _build_model_prompt(self, prompt: WritingPrompt) -> str:
        """Build the full prompt to send to the model"""
        parts = [
            f"You are {prompt.writer.name}, a {prompt.writer.job_title} at {prompt.company.name}.",
            f"You have {prompt.writer.years_experience} years of experience.",
            "",
            "TASK:",
            prompt.prompt_text,
            "",
            f"Write to: {prompt.recipient.name} ({prompt.recipient.job_title})",
            f"Your relationship: {prompt.recipient.relationship}, familiarity: {prompt.recipient.familiarity}",
            f"Formality level: {prompt.formality_level}/5",
            f"Urgency: {prompt.urgency_level}/5",
        ]

        if prompt.temporal_context:
            parts.append(f"\nTiming: {prompt.temporal_context}")

        if prompt.attachments:
            parts.append("\nReferences/Attachments:")
            for att in prompt.attachments:
                parts.append(f"- {att.type}: {att.content_summary}")

        if prompt.reply_context:
            parts.append(f"\nPrior message to reply to:\n{prompt.reply_context}")

        if prompt.competing_objectives:
            parts.append(f"\nNote: {prompt.competing_objectives}")

        if prompt.constraints:
            parts.append("\nConstraints:")
            for c in prompt.constraints:
                parts.append(f"- {c.description}")

        parts.append("\nWrite your response:")

        return "\n".join(parts)

    def _detect_formats(self, text: str) -> list[str]:
        """Detect formatting patterns in response"""
        formats = []
        if '- ' in text or '* ' in text:
            formats.append('bullet_points')
        if text.count('\n\n') > 2:
            formats.append('paragraphs')
        if any(line.startswith('#') for line in text.split('\n')):
            formats.append('headers')
        if '1.' in text or '2.' in text:
            formats.append('numbered_list')
        return formats

    def _detect_greeting(self, text: str) -> Optional[str]:
        """Detect greeting pattern"""
        greetings = ['Dear', 'Hi ', 'Hello', 'Good morning', 'Good afternoon', 'Hey ']
        first_line = text.split('\n')[0] if text else ''
        for g in greetings:
            if first_line.startswith(g):
                return g.strip()
        return None

    def _detect_signoff(self, text: str) -> Optional[str]:
        """Detect sign-off pattern"""
        signoffs = ['Best', 'Regards', 'Sincerely', 'Thanks', 'Thank you', 'Cheers', 'Best regards']
        lines = text.strip().split('\n')[-3:]  # Check last 3 lines
        for line in lines:
            for s in signoffs:
                if line.strip().startswith(s):
                    return s
        return None

    def _detect_refusal(self, text: str) -> tuple[bool, Optional[str]]:
        """Detect if model refused the task"""
        refusal_patterns = {
            'safety': ['I cannot', 'I\'m not able to', 'I apologize but I cannot', 'against my guidelines'],
            'capability': ['I don\'t have access', 'I cannot access', 'I\'m not sure how to'],
            'misunderstanding': ['I\'m not sure what you\'re asking', 'Could you clarify'],
        }

        text_lower = text.lower()
        for category, patterns in refusal_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return (True, category)

        return (False, None)

    def _detect_off_topic(self, text: str, prompt: WritingPrompt) -> bool:
        """Detect if response is off-topic"""
        # Simple heuristic: check if response mentions key elements from prompt
        key_terms = [
            prompt.recipient.name.split()[0].lower(),
            prompt.company.name.split()[0].lower(),
        ]

        text_lower = text.lower()
        matches = sum(1 for term in key_terms if term in text_lower)

        # If none of the key terms appear and response is short, likely off-topic
        if matches == 0 and len(text.split()) < 50:
            return True

        return False

    async def run_judge_vote(self,
                             prompt: WritingPrompt,
                             response_a: ModelResponse,
                             response_b: ModelResponse,
                             judge_model_id: str,
                             judge_persona: str,
                             vote_number: int,
                             presentation_seed: int) -> JudgeVote:
        """Run a single judge vote"""
        judge_model = self.config.get_model(judge_model_id)

        # Determine presentation order (shuffle deterministically)
        rng = random.Random(presentation_seed + vote_number)
        if rng.random() < 0.5:
            first, second = response_a, response_b
            model_a_position = "first"
        else:
            first, second = response_b, response_a
            model_a_position = "second"

        # Build judge prompt
        judge_prompt = build_judge_prompt(
            prompt=prompt,
            response_first=first.response_text,
            response_second=second.response_text,
            persona=judge_persona
        )

        response = await self.openrouter.complete(
            model=judge_model.openrouter_id,
            prompt=judge_prompt,
            max_tokens=1500,
            temperature=0.3  # Lower temperature for more consistent judging
        )

        # Parse judge response
        parsed = self._parse_judge_response(response.text, model_a_position)

        return JudgeVote(
            vote_id=f"v_{prompt.prompt_id}_{judge_model_id}_{vote_number}_{int(datetime.utcnow().timestamp())}",
            comparison_id="",  # Set by caller
            judge_model=judge_model_id,
            judge_persona=judge_persona,
            vote_number=vote_number,
            model_a_position=model_a_position,
            created_at=datetime.utcnow(),
            **parsed
        )

    def _parse_judge_response(self, text: str, model_a_position: str) -> dict:
        """Parse structured judge response"""
        # This would parse the JSON or structured response from judge
        # Implementation depends on judge prompt format
        # Placeholder implementation:
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                # Map "first"/"second" winner to model_a/model_b
                winner = data.get('winner', 'tie')
                if winner == 'first':
                    winner = 'model_a' if model_a_position == 'first' else 'model_b'
                elif winner == 'second':
                    winner = 'model_b' if model_a_position == 'first' else 'model_a'
                else:
                    winner = 'tie'

                return {
                    'winner': winner,
                    'confidence': data.get('confidence', 3),
                    'reasoning': data.get('reasoning', ''),
                    'quality_score_a': data.get('scores', {}).get('first' if model_a_position == 'first' else 'second', {}).get('quality', 3),
                    'quality_score_b': data.get('scores', {}).get('second' if model_a_position == 'first' else 'first', {}).get('quality', 3),
                    # ... other scores
                }
            except json.JSONDecodeError:
                pass

        # Fallback parsing
        return {
            'winner': 'tie',
            'confidence': 1,
            'reasoning': text[:500],
            'quality_score_a': 3,
            'quality_score_b': 3,
            'length_appropriateness_a': 3,
            'length_appropriateness_b': 3,
            'tone_appropriateness_a': 3,
            'tone_appropriateness_b': 3,
            'effectiveness_a': 3,
            'effectiveness_b': 3,
            'clarity_a': 3,
            'clarity_b': 3,
            'task_completion_a': 3,
            'task_completion_b': 3,
            'authenticity_a': 3,
            'authenticity_b': 3,
            'cliche_avoidance_a': 3,
            'cliche_avoidance_b': 3,
        }

    async def evaluate_prompt(self,
                              prompt: WritingPrompt,
                              model_pair: tuple[str, str]) -> Comparison:
        """Run full evaluation for a single prompt and model pair"""
        gemini_id, competitor_id = model_pair

        # Generate responses
        gemini_response, competitor_response = await asyncio.gather(
            self.generate_response(prompt, gemini_id),
            self.generate_response(prompt, competitor_id)
        )

        # Handle failures (auto-loss)
        if gemini_response.is_refusal and not competitor_response.is_refusal:
            # Gemini auto-loses
            return self._create_auto_loss_comparison(
                prompt, gemini_response, competitor_response, loser='gemini'
            )
        elif competitor_response.is_refusal and not gemini_response.is_refusal:
            # Competitor auto-loses (Gemini wins)
            return self._create_auto_loss_comparison(
                prompt, gemini_response, competitor_response, loser='competitor'
            )
        elif gemini_response.is_refusal and competitor_response.is_refusal:
            # Both refused - tie
            return self._create_auto_loss_comparison(
                prompt, gemini_response, competitor_response, loser='both'
            )

        # Run judge voting
        presentation_seed = hash(f"{prompt.prompt_id}:{gemini_id}:{competitor_id}")
        votes = []

        for judge_config in self.config.judges:
            for persona in judge_config.personas:
                for vote_num in range(judge_config.votes_per_comparison):
                    vote = await self.run_judge_vote(
                        prompt=prompt,
                        response_a=gemini_response,
                        response_b=competitor_response,
                        judge_model_id=judge_config.model.id,
                        judge_persona=persona,
                        vote_number=vote_num,
                        presentation_seed=presentation_seed
                    )
                    votes.append(vote)

        # Aggregate results
        comparison = self._aggregate_votes(
            prompt=prompt,
            response_a=gemini_response,
            response_b=competitor_response,
            votes=votes,
            presentation_seed=presentation_seed
        )

        return comparison

    def _create_auto_loss_comparison(self,
                                      prompt: WritingPrompt,
                                      gemini_response: ModelResponse,
                                      competitor_response: ModelResponse,
                                      loser: str) -> Comparison:
        """Create comparison for auto-loss scenarios"""
        if loser == 'gemini':
            final_winner = 'model_b'
            gemini_won = False
        elif loser == 'competitor':
            final_winner = 'model_a'
            gemini_won = True
        else:
            final_winner = 'tie'
            gemini_won = None

        return Comparison(
            comparison_id=f"c_{prompt.prompt_id}_{gemini_response.model_id}_{competitor_response.model_id}",
            prompt_id=prompt.prompt_id,
            model_a_id=gemini_response.model_id,
            model_b_id=competitor_response.model_id,
            model_a_name=gemini_response.model_name,
            model_b_name=competitor_response.model_name,
            response_a_id=gemini_response.response_id,
            response_b_id=competitor_response.response_id,
            votes=[],
            final_winner=final_winner,
            gemini_won=gemini_won,
            presentation_order_seed=0,
            created_at=datetime.utcnow()
        )

    def _aggregate_votes(self,
                         prompt: WritingPrompt,
                         response_a: ModelResponse,
                         response_b: ModelResponse,
                         votes: list[JudgeVote],
                         presentation_seed: int) -> Comparison:
        """Aggregate votes using majority-of-majorities"""
        from collections import Counter

        # Group votes by judge model
        judge_verdicts = {}
        for judge_id in set(v.judge_model for v in votes):
            judge_votes = [v for v in votes if v.judge_model == judge_id]
            winners = [v.winner for v in judge_votes]
            # Majority for this judge
            counter = Counter(winners)
            most_common = counter.most_common(1)[0]
            judge_verdicts[judge_id] = most_common[0]

        # Majority of judge verdicts
        final_counter = Counter(judge_verdicts.values())
        final_winner = final_counter.most_common(1)[0][0]

        gemini_won = final_winner == 'model_a' if final_winner != 'tie' else None

        return Comparison(
            comparison_id=f"c_{prompt.prompt_id}_{response_a.model_id}_{response_b.model_id}",
            prompt_id=prompt.prompt_id,
            model_a_id=response_a.model_id,
            model_b_id=response_b.model_id,
            model_a_name=response_a.model_name,
            model_b_name=response_b.model_name,
            response_a_id=response_a.response_id,
            response_b_id=response_b.response_id,
            votes=votes,
            claude_verdict=judge_verdicts.get('claude-opus-4.5'),
            gpt_verdict=judge_verdicts.get('gpt-5.2-thinking'),
            gemini_verdict=judge_verdicts.get('gemini-3-pro'),
            final_winner=final_winner,
            gemini_won=gemini_won,
            presentation_order_seed=presentation_seed,
            created_at=datetime.utcnow()
        )
```

### 6.2 Judge Prompt Construction

```python
# src/eval/judge_prompts.py

from ..schemas import WritingPrompt

def build_judge_prompt(prompt: WritingPrompt,
                       response_first: str,
                       response_second: str,
                       persona: str) -> str:
    """
    Build the judge prompt with full context.
    Judges need complete scenario context to evaluate appropriately.
    """

    if persona == "writing_expert":
        persona_intro = """You are a professional writing expert and editor with decades of experience
evaluating business and professional communication. You assess writing quality, craft,
structure, tone appropriateness, and effectiveness."""
    else:  # target_recipient
        persona_intro = f"""You are simulating {prompt.recipient.name}, the {prompt.recipient.job_title}.
Your relationship with the writer is: {prompt.recipient.relationship} (familiarity: {prompt.recipient.familiarity}).
Your technical level: {prompt.recipient.technical_level}.
Evaluate from the perspective of how you would receive and react to these messages."""

    context = f"""
## SCENARIO CONTEXT

**Writer**: {prompt.writer.name}, {prompt.writer.job_title} at {prompt.company.name}
- Generation: {prompt.writer.generation.value}
- Experience: {prompt.writer.years_experience} years
- Skill level: {prompt.writer.skill_level}

**Recipient**: {prompt.recipient.name}, {prompt.recipient.job_title}
- Relationship: {prompt.recipient.relationship}
- Familiarity: {prompt.recipient.familiarity}
- Technical level: {prompt.recipient.technical_level}

**Company**: {prompt.company.name}
- Size: {prompt.company.size}
- Industry: {prompt.company.industry_name}

**Communication Context**:
- Formality expected: {prompt.formality_level}/5
- Urgency: {prompt.urgency_level}/5
- Audience size: {prompt.audience_size}
- Message position: {prompt.message_position.value}
- Emotional context: {prompt.emotional_context.value}

**Original Task**:
{prompt.prompt_text}
"""

    if prompt.constraints:
        context += "\n**Explicit Constraints**:\n"
        for c in prompt.constraints:
            context += f"- {c.description}\n"

    rubric = """
## EVALUATION CRITERIA

Rate each response on a 1-5 scale for each criterion:

1. **Quality of Writing** (grammar, style, professionalism)
2. **Length Appropriateness** (right length for this specific task)
3. **Tone Appropriateness** (matches formality, relationship, context)
4. **Effectiveness** (achieves the communication goal)
5. **Clarity** (easy to understand, well-organized)
6. **Task Completion** (addresses all requirements)
7. **Authenticity** (feels like real human writing, not AI-generated)
8. **Cliche Avoidance** (avoids overused phrases like "I hope this finds you well")
"""

    if prompt.constraints:
        rubric += "9. **Instruction Compliance** (follows explicit constraints)\n"

    output_format = """
## OUTPUT FORMAT

Respond with a JSON object:
```json
{
  "winner": "first" | "second" | "tie",
  "confidence": 1-5,
  "reasoning": "Brief explanation of your decision",
  "scores": {
    "first": {
      "quality": 1-5,
      "length": 1-5,
      "tone": 1-5,
      "effectiveness": 1-5,
      "clarity": 1-5,
      "task_completion": 1-5,
      "authenticity": 1-5,
      "cliche_avoidance": 1-5
    },
    "second": {
      // same structure
    }
  }
}
```
"""

    full_prompt = f"""{persona_intro}

{context}

## RESPONSES TO EVALUATE

### RESPONSE A (First):
{response_first}

### RESPONSE B (Second):
{response_second}

{rubric}

{output_format}

Evaluate these responses and provide your judgment:
"""

    return full_prompt
```

---

## 7. Storage and Checkpointing

### 7.1 SQLite Database Schema

```python
# src/storage/database.py

import sqlite3
from pathlib import Path
from datetime import datetime
import json

class ResultsDatabase:
    """SQLite database for storing evaluation results"""

    SCHEMA = """
    -- Prompts table
    CREATE TABLE IF NOT EXISTS prompts (
        prompt_id TEXT PRIMARY KEY,
        onet_task_id TEXT NOT NULL,
        onet_task_text TEXT NOT NULL,
        occupation_code TEXT NOT NULL,
        occupation_title TEXT NOT NULL,
        job_zone INTEGER NOT NULL,
        soc_major_group TEXT NOT NULL,
        prompt_text TEXT NOT NULL,
        writer_json TEXT NOT NULL,
        recipient_json TEXT NOT NULL,
        company_json TEXT NOT NULL,
        formality_level INTEGER NOT NULL,
        urgency_level INTEGER NOT NULL,
        audience_size TEXT NOT NULL,
        message_position TEXT NOT NULL,
        emotional_context TEXT NOT NULL,
        inferred_channel TEXT,
        writing_category TEXT NOT NULL,
        sensitive_topic TEXT,
        generation_phase TEXT NOT NULL,
        random_seed INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL
    );

    -- Responses table
    CREATE TABLE IF NOT EXISTS responses (
        response_id TEXT PRIMARY KEY,
        prompt_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        response_text TEXT NOT NULL,
        response_time_ms INTEGER NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        finish_reason TEXT NOT NULL,
        word_count INTEGER NOT NULL,
        character_count INTEGER NOT NULL,
        detected_format TEXT NOT NULL,  -- JSON array
        greeting_pattern TEXT,
        signoff_pattern TEXT,
        is_refusal INTEGER NOT NULL,
        refusal_category TEXT,
        is_off_topic INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Comparisons table
    CREATE TABLE IF NOT EXISTS comparisons (
        comparison_id TEXT PRIMARY KEY,
        prompt_id TEXT NOT NULL,
        model_a_id TEXT NOT NULL,
        model_b_id TEXT NOT NULL,
        model_a_name TEXT NOT NULL,
        model_b_name TEXT NOT NULL,
        response_a_id TEXT NOT NULL,
        response_b_id TEXT NOT NULL,
        claude_verdict TEXT,
        gpt_verdict TEXT,
        gemini_verdict TEXT,
        final_winner TEXT,
        gemini_won INTEGER,
        presentation_order_seed INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
        FOREIGN KEY (response_a_id) REFERENCES responses(response_id),
        FOREIGN KEY (response_b_id) REFERENCES responses(response_id)
    );

    -- Judge votes table
    CREATE TABLE IF NOT EXISTS judge_votes (
        vote_id TEXT PRIMARY KEY,
        comparison_id TEXT NOT NULL,
        judge_model TEXT NOT NULL,
        judge_persona TEXT NOT NULL,
        vote_number INTEGER NOT NULL,
        winner TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        reasoning TEXT NOT NULL,
        quality_score_a INTEGER NOT NULL,
        quality_score_b INTEGER NOT NULL,
        length_appropriateness_a INTEGER NOT NULL,
        length_appropriateness_b INTEGER NOT NULL,
        tone_appropriateness_a INTEGER NOT NULL,
        tone_appropriateness_b INTEGER NOT NULL,
        effectiveness_a INTEGER NOT NULL,
        effectiveness_b INTEGER NOT NULL,
        clarity_a INTEGER NOT NULL,
        clarity_b INTEGER NOT NULL,
        task_completion_a INTEGER NOT NULL,
        task_completion_b INTEGER NOT NULL,
        authenticity_a INTEGER NOT NULL,
        authenticity_b INTEGER NOT NULL,
        cliche_avoidance_a INTEGER NOT NULL,
        cliche_avoidance_b INTEGER NOT NULL,
        instruction_compliance_a INTEGER,
        instruction_compliance_b INTEGER,
        model_a_position TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(occupation_code);
    CREATE INDEX IF NOT EXISTS idx_prompts_job_zone ON prompts(job_zone);
    CREATE INDEX IF NOT EXISTS idx_prompts_soc_group ON prompts(soc_major_group);
    CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
    CREATE INDEX IF NOT EXISTS idx_comparisons_winner ON comparisons(final_winner);
    CREATE INDEX IF NOT EXISTS idx_comparisons_gemini ON comparisons(gemini_won);
    CREATE INDEX IF NOT EXISTS idx_votes_judge ON judge_votes(judge_model);
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    def insert_prompt(self, prompt: 'WritingPrompt'):
        self.conn.execute("""
            INSERT INTO prompts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prompt.prompt_id,
            prompt.onet_task_id,
            prompt.onet_task_text,
            prompt.occupation_code,
            prompt.occupation_title,
            prompt.job_zone.value,
            prompt.soc_major_group,
            prompt.prompt_text,
            json.dumps(prompt.writer.model_dump()),
            json.dumps(prompt.recipient.model_dump()),
            json.dumps(prompt.company.model_dump()),
            prompt.formality_level,
            prompt.urgency_level,
            prompt.audience_size,
            prompt.message_position.value,
            prompt.emotional_context.value,
            prompt.inferred_channel,
            prompt.writing_category,
            prompt.sensitive_topic,
            prompt.generation_phase,
            prompt.random_seed,
            prompt.created_at.isoformat()
        ))
        self.conn.commit()

    def insert_response(self, response: 'ModelResponse'):
        self.conn.execute("""
            INSERT INTO responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.response_id,
            response.prompt_id,
            response.model_id,
            response.model_name,
            response.response_text,
            response.response_time_ms,
            response.input_tokens,
            response.output_tokens,
            response.finish_reason,
            response.word_count,
            response.character_count,
            json.dumps(response.detected_format),
            response.greeting_pattern,
            response.signoff_pattern,
            int(response.is_refusal),
            response.refusal_category,
            int(response.is_off_topic),
            response.created_at.isoformat()
        ))
        self.conn.commit()

    def insert_comparison(self, comparison: 'Comparison'):
        self.conn.execute("""
            INSERT INTO comparisons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comparison.comparison_id,
            comparison.prompt_id,
            comparison.model_a_id,
            comparison.model_b_id,
            comparison.model_a_name,
            comparison.model_b_name,
            comparison.response_a_id,
            comparison.response_b_id,
            comparison.claude_verdict,
            comparison.gpt_verdict,
            comparison.gemini_verdict,
            comparison.final_winner,
            comparison.gemini_won if comparison.gemini_won is not None else None,
            comparison.presentation_order_seed,
            comparison.created_at.isoformat()
        ))
        self.conn.commit()

    def insert_vote(self, vote: 'JudgeVote'):
        self.conn.execute("""
            INSERT INTO judge_votes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vote.vote_id,
            vote.comparison_id,
            vote.judge_model,
            vote.judge_persona,
            vote.vote_number,
            vote.winner,
            vote.confidence,
            vote.reasoning,
            vote.quality_score_a,
            vote.quality_score_b,
            vote.length_appropriateness_a,
            vote.length_appropriateness_b,
            vote.tone_appropriateness_a,
            vote.tone_appropriateness_b,
            vote.effectiveness_a,
            vote.effectiveness_b,
            vote.clarity_a,
            vote.clarity_b,
            vote.task_completion_a,
            vote.task_completion_b,
            vote.authenticity_a,
            vote.authenticity_b,
            vote.cliche_avoidance_a,
            vote.cliche_avoidance_b,
            vote.instruction_compliance_a,
            vote.instruction_compliance_b,
            vote.model_a_position,
            vote.created_at.isoformat()
        ))
        self.conn.commit()

    def get_win_rates(self, model_pair: tuple[str, str] = None) -> dict:
        """Get win rates, optionally filtered by model pair"""
        query = """
            SELECT
                model_a_id as gemini_model,
                model_b_id as competitor_model,
                COUNT(*) as total,
                SUM(CASE WHEN gemini_won = 1 THEN 1 ELSE 0 END) as gemini_wins,
                SUM(CASE WHEN gemini_won = 0 THEN 1 ELSE 0 END) as competitor_wins,
                SUM(CASE WHEN gemini_won IS NULL THEN 1 ELSE 0 END) as ties
            FROM comparisons
        """
        if model_pair:
            query += " WHERE model_a_id = ? AND model_b_id = ?"
            query += " GROUP BY model_a_id, model_b_id"
            cursor = self.conn.execute(query, model_pair)
        else:
            query += " GROUP BY model_a_id, model_b_id"
            cursor = self.conn.execute(query)

        results = {}
        for row in cursor:
            key = (row['gemini_model'], row['competitor_model'])
            results[key] = {
                'total': row['total'],
                'gemini_wins': row['gemini_wins'],
                'competitor_wins': row['competitor_wins'],
                'ties': row['ties'],
                'gemini_win_rate': row['gemini_wins'] / row['total'] if row['total'] > 0 else 0
            }
        return results

    def export_csv(self, output_path: Path):
        """Export results to CSV"""
        import csv

        # Export comparisons summary
        cursor = self.conn.execute("""
            SELECT
                c.comparison_id,
                c.prompt_id,
                p.occupation_title,
                p.job_zone,
                p.writing_category,
                c.model_a_name,
                c.model_b_name,
                c.final_winner,
                c.gemini_won
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
        """)

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([col[0] for col in cursor.description])
            writer.writerows(cursor.fetchall())
```

### 7.2 Checkpoint Manager

```python
# src/storage/checkpoint.py

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Set

@dataclass
class CheckpointState:
    """State that can be checkpointed and resumed"""
    run_id: str
    config_hash: str
    total_prompts: int
    total_model_pairs: int

    # Progress tracking
    completed_prompt_ids: Set[str]
    completed_comparison_ids: Set[str]

    # Current position
    current_prompt_index: int
    current_model_pair_index: int

    # Phase tracking
    phase: str  # 'generation', 'judging', 'analysis'

    # Timestamps
    started_at: str
    last_checkpoint: str

    # Statistics
    total_responses_generated: int
    total_judgments_completed: int
    total_api_calls: int
    total_cost_usd: float

class CheckpointManager:
    """Manage checkpoints for resumable evaluation"""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"
        self.state: Optional[CheckpointState] = None

    def initialize(self, config: 'EvalConfig', num_prompts: int):
        """Initialize a new checkpoint"""
        self.state = CheckpointState(
            run_id=config.run_id,
            config_hash=self._hash_config(config),
            total_prompts=num_prompts,
            total_model_pairs=len(config.model_pairs),
            completed_prompt_ids=set(),
            completed_comparison_ids=set(),
            current_prompt_index=0,
            current_model_pair_index=0,
            phase='generation',
            started_at=datetime.utcnow().isoformat(),
            last_checkpoint=datetime.utcnow().isoformat(),
            total_responses_generated=0,
            total_judgments_completed=0,
            total_api_calls=0,
            total_cost_usd=0.0
        )
        self.save()

    def load(self) -> bool:
        """Load existing checkpoint, returns True if found"""
        if not self.checkpoint_file.exists():
            return False

        with open(self.checkpoint_file) as f:
            data = json.load(f)

        # Convert sets from lists
        data['completed_prompt_ids'] = set(data['completed_prompt_ids'])
        data['completed_comparison_ids'] = set(data['completed_comparison_ids'])

        self.state = CheckpointState(**data)
        return True

    def save(self):
        """Save current checkpoint"""
        if not self.state:
            return

        self.state.last_checkpoint = datetime.utcnow().isoformat()

        data = asdict(self.state)
        # Convert sets to lists for JSON
        data['completed_prompt_ids'] = list(data['completed_prompt_ids'])
        data['completed_comparison_ids'] = list(data['completed_comparison_ids'])

        # Write atomically
        temp_file = self.checkpoint_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        temp_file.rename(self.checkpoint_file)

    def mark_prompt_complete(self, prompt_id: str):
        self.state.completed_prompt_ids.add(prompt_id)
        self.state.current_prompt_index = len(self.state.completed_prompt_ids)

    def mark_comparison_complete(self, comparison_id: str):
        self.state.completed_comparison_ids.add(comparison_id)

    def is_prompt_complete(self, prompt_id: str) -> bool:
        return prompt_id in self.state.completed_prompt_ids

    def is_comparison_complete(self, comparison_id: str) -> bool:
        return comparison_id in self.state.completed_comparison_ids

    def update_stats(self, responses: int = 0, judgments: int = 0, api_calls: int = 0, cost: float = 0.0):
        self.state.total_responses_generated += responses
        self.state.total_judgments_completed += judgments
        self.state.total_api_calls += api_calls
        self.state.total_cost_usd += cost

    def get_progress(self) -> dict:
        """Get current progress for display"""
        total_comparisons = self.state.total_prompts * self.state.total_model_pairs
        return {
            'prompts_completed': len(self.state.completed_prompt_ids),
            'prompts_total': self.state.total_prompts,
            'comparisons_completed': len(self.state.completed_comparison_ids),
            'comparisons_total': total_comparisons,
            'phase': self.state.phase,
            'api_calls': self.state.total_api_calls,
            'cost_usd': self.state.total_cost_usd
        }

    def _hash_config(self, config: 'EvalConfig') -> str:
        """Hash config for validation on resume"""
        import hashlib
        key_fields = f"{config.num_prompts}:{config.random_seed}:{sorted(config.model_pairs)}"
        return hashlib.md5(key_fields.encode()).hexdigest()

    def validate_config(self, config: 'EvalConfig') -> bool:
        """Validate that config matches checkpoint"""
        return self._hash_config(config) == self.state.config_hash
```

---

## 8. TUI Progress Display

### 8.1 Rich/Textual Dashboard

```python
# src/tui/dashboard.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from datetime import datetime, timedelta
import asyncio

class EvalDashboard(App):
    """Real-time progress dashboard for evaluation runs"""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 2fr 1fr;
    }

    #overall-progress {
        row-span: 1;
        column-span: 2;
    }

    #model-pairs {
        row-span: 2;
    }

    #current-batch {
        row-span: 1;
    }

    #statistics {
        row-span: 1;
    }

    #activity-log {
        row-span: 1;
        column-span: 2;
    }

    .panel {
        border: solid green;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause"),
        ("d", "toggle_detail", "Detail View"),
        ("s", "show_stats", "Statistics"),
    ]

    # Reactive state
    prompts_completed = reactive(0)
    prompts_total = reactive(100)
    current_phase = reactive("Generation")
    elapsed_seconds = reactive(0)
    estimated_remaining = reactive(0)

    def __init__(self, checkpoint_manager, **kwargs):
        super().__init__(**kwargs)
        self.checkpoint = checkpoint_manager
        self.model_pair_progress = {}
        self.current_prompt_info = {}
        self.running_stats = {
            'win_rates': {},
            'api_calls_per_min': 0,
            'avg_response_time': 0,
            'cost_so_far': 0.0,
            'estimated_total_cost': 0.0,
            'judge_agreement': 0.0
        }
        self.activity_log = []
        self.paused = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(id="overall-progress", classes="panel"),
            Static(id="model-pairs", classes="panel"),
            Static(id="current-batch", classes="panel"),
            Static(id="statistics", classes="panel"),
            Log(id="activity-log", classes="panel"),
            id="main-container"
        )
        yield Footer()

    def on_mount(self):
        """Start update loop"""
        self.set_interval(1.0, self.update_display)

    def update_display(self):
        """Update all display panels"""
        self.elapsed_seconds += 1
        self._update_overall_progress()
        self._update_model_pairs()
        self._update_current_batch()
        self._update_statistics()

    def _update_overall_progress(self):
        """Update overall progress panel"""
        progress = self.checkpoint.get_progress()

        pct = progress['prompts_completed'] / progress['prompts_total'] * 100 if progress['prompts_total'] > 0 else 0
        bar_width = 50
        filled = int(pct / 100 * bar_width)

        elapsed = timedelta(seconds=self.elapsed_seconds)
        if pct > 0:
            total_est = self.elapsed_seconds / (pct / 100)
            remaining = timedelta(seconds=int(total_est - self.elapsed_seconds))
        else:
            remaining = timedelta(seconds=0)

        content = f"""
GEMINI WRITING EVAL - Running [Preset: Standard]
Started: {datetime.now() - elapsed:%Y-%m-%d %H:%M:%S} | Elapsed: {elapsed} | ETA: {remaining}

[{'█' * filled}{'░' * (bar_width - filled)}] {progress['prompts_completed']}/{progress['prompts_total']} ({pct:.1f}%)

Phase: {progress['phase'].upper()}  [Generation {'✓' if progress['phase'] != 'generation' else '◐'}] [Judging {'✓' if progress['phase'] == 'analysis' else '○'}] [Analysis ○]
"""
        self.query_one("#overall-progress").update(Panel(content, title="Overall Progress"))

    def _update_model_pairs(self):
        """Update model pairs progress"""
        table = Table(show_header=True, header_style="bold")
        table.add_column("Model Pair")
        table.add_column("Progress")
        table.add_column("Win Rate")

        for pair, data in self.model_pair_progress.items():
            pct = data['completed'] / data['total'] * 100 if data['total'] > 0 else 0
            bar = f"{'█' * int(pct / 5)}{'░' * (20 - int(pct / 5))}"
            win_rate = f"{data.get('win_rate', 0):.1f}%" if data.get('win_rate') is not None else "--"

            table.add_row(
                f"Gemini vs {pair[1]}",
                f"{bar} {data['completed']}/{data['total']}",
                win_rate
            )

        self.query_one("#model-pairs").update(Panel(table, title="Model Pairs"))

    def _update_current_batch(self):
        """Update current batch info"""
        info = self.current_prompt_info

        if not info:
            content = "Waiting for next prompt..."
        else:
            content = f"""
Prompt #{info.get('index', '?')}: "{info.get('task', 'Loading...')[:60]}..."
Occupation: {info.get('occupation', 'N/A')}
Industry: {info.get('industry', 'N/A')}

Responses:                  Judging:
  Gemini: {info.get('gemini_status', '○')}              Judge 1: {info.get('judge1_status', '○')}
  Competitor: {info.get('competitor_status', '○')}      Judge 2: {info.get('judge2_status', '○')}
                            Judge 3: {info.get('judge3_status', '○')}
"""
        self.query_one("#current-batch").update(Panel(content, title="Current Batch"))

    def _update_statistics(self):
        """Update live statistics"""
        stats = self.running_stats

        content = f"""
Win Rates (Running)           Performance
─────────────────────         ──────────────────
vs GPT-5.2:    {stats['win_rates'].get('gpt', '--')}   Avg response: {stats['avg_response_time']:.1f}s
vs Opus:       {stats['win_rates'].get('opus', '--')}  API calls/min: {stats['api_calls_per_min']}
vs Grok:       {stats['win_rates'].get('grok', '--')}  Cost so far: ${stats['cost_so_far']:.2f}

Judge Agreement: {stats['judge_agreement']:.2f} κ     Est. total: ${stats['estimated_total_cost']:.2f}
"""
        self.query_one("#statistics").update(Panel(content, title="Live Statistics"))

    def log_activity(self, message: str, level: str = "info"):
        """Add entry to activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = {"info": "✓", "warning": "⚠", "error": "✗"}.get(level, "•")
        self.query_one("#activity-log").write_line(f"{timestamp}  {icon}  {message}")

    def update_model_pair(self, pair: tuple, completed: int, total: int, win_rate: float = None):
        """Update progress for a model pair"""
        self.model_pair_progress[pair] = {
            'completed': completed,
            'total': total,
            'win_rate': win_rate
        }

    def update_current_prompt(self, info: dict):
        """Update current prompt information"""
        self.current_prompt_info = info

    def update_stats(self, stats: dict):
        """Update running statistics"""
        self.running_stats.update(stats)

    def action_quit(self):
        """Handle quit action"""
        self.exit()

    def action_pause(self):
        """Toggle pause state"""
        self.paused = not self.paused
        self.log_activity("Evaluation paused" if self.paused else "Evaluation resumed", "warning")
```

---

## 9. Analysis and Reporting

### 9.1 Statistical Analysis

```python
# src/analysis/statistics.py

import numpy as np
from scipy import stats
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class WinRateResult:
    """Win rate with confidence interval"""
    win_rate: float
    ci_low: float
    ci_high: float
    n_samples: int
    p_value: float  # Against null hypothesis of 50%

@dataclass
class BiasAnalysis:
    """Analysis of systematic biases"""
    position_bias: float  # Preference for first vs second position
    position_bias_p: float
    length_correlation: float  # Correlation between length and win
    length_correlation_p: float
    judge_agreement_kappa: float

class StatisticalAnalyzer:
    """Statistical analysis for evaluation results"""

    def __init__(self, db: 'ResultsDatabase'):
        self.db = db

    def compute_win_rate(self, model_pair: Tuple[str, str],
                         confidence: float = 0.95) -> WinRateResult:
        """Compute win rate with Wilson score confidence interval"""
        data = self.db.get_win_rates(model_pair)
        if model_pair not in data:
            return None

        stats_data = data[model_pair]
        n = stats_data['total']
        wins = stats_data['gemini_wins']

        if n == 0:
            return WinRateResult(0, 0, 1, 0, 1.0)

        p = wins / n

        # Wilson score interval
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        spread = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator

        ci_low = max(0, center - spread)
        ci_high = min(1, center + spread)

        # Binomial test against 50%
        p_value = stats.binom_test(wins, n, 0.5, alternative='two-sided')

        return WinRateResult(
            win_rate=p,
            ci_low=ci_low,
            ci_high=ci_high,
            n_samples=n,
            p_value=p_value
        )

    def analyze_position_bias(self) -> Tuple[float, float]:
        """Analyze if judges prefer first or second position"""
        cursor = self.db.conn.execute("""
            SELECT model_a_position, winner
            FROM judge_votes
            WHERE winner != 'tie'
        """)

        first_won = 0
        total = 0

        for row in cursor:
            total += 1
            if (row['model_a_position'] == 'first' and row['winner'] == 'model_a') or \
               (row['model_a_position'] == 'second' and row['winner'] == 'model_b'):
                first_won += 1

        if total == 0:
            return 0.5, 1.0

        bias = first_won / total
        p_value = stats.binom_test(first_won, total, 0.5)

        return bias, p_value

    def analyze_length_bias(self) -> Tuple[float, float]:
        """Analyze correlation between response length and winning"""
        cursor = self.db.conn.execute("""
            SELECT
                ra.word_count as length_a,
                rb.word_count as length_b,
                c.final_winner
            FROM comparisons c
            JOIN responses ra ON c.response_a_id = ra.response_id
            JOIN responses rb ON c.response_b_id = rb.response_id
            WHERE c.final_winner != 'tie'
        """)

        length_diffs = []
        wins = []  # 1 if longer won, 0 if shorter won

        for row in cursor:
            diff = row['length_a'] - row['length_b']
            won = 1 if (diff > 0 and row['final_winner'] == 'model_a') or \
                       (diff < 0 and row['final_winner'] == 'model_b') else 0
            length_diffs.append(abs(diff))
            wins.append(won)

        if len(length_diffs) < 10:
            return 0, 1.0

        correlation, p_value = stats.pointbiserialr(wins, length_diffs)
        return correlation, p_value

    def compute_judge_agreement(self) -> float:
        """Compute Cohen's Kappa for inter-judge agreement"""
        cursor = self.db.conn.execute("""
            SELECT comparison_id, judge_model, winner
            FROM judge_votes
            GROUP BY comparison_id, judge_model
        """)

        # Build comparison matrix
        from collections import defaultdict
        comparisons = defaultdict(dict)

        for row in cursor:
            comparisons[row['comparison_id']][row['judge_model']] = row['winner']

        # Compute pairwise kappa
        judges = list(set(j for c in comparisons.values() for j in c.keys()))
        if len(judges) < 2:
            return 1.0

        kappas = []
        for i, j1 in enumerate(judges):
            for j2 in judges[i+1:]:
                ratings1 = []
                ratings2 = []
                for comp in comparisons.values():
                    if j1 in comp and j2 in comp:
                        ratings1.append(comp[j1])
                        ratings2.append(comp[j2])

                if len(ratings1) > 10:
                    kappa = stats.cohens_kappa(ratings1, ratings2)
                    kappas.append(kappa)

        return np.mean(kappas) if kappas else 0

    def compute_effect_sizes(self, model_pair: Tuple[str, str]) -> Dict:
        """Compute effect sizes for win rate differences"""
        cursor = self.db.conn.execute("""
            SELECT
                p.job_zone,
                p.writing_category,
                p.soc_major_group,
                c.gemini_won
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            WHERE c.model_a_id = ? AND c.model_b_id = ?
              AND c.gemini_won IS NOT NULL
        """, model_pair)

        results = {
            'by_job_zone': {},
            'by_writing_category': {},
            'by_soc_group': {}
        }

        from collections import defaultdict
        data = defaultdict(lambda: defaultdict(list))

        for row in cursor:
            data['job_zone'][row['job_zone']].append(row['gemini_won'])
            data['writing_category'][row['writing_category']].append(row['gemini_won'])
            data['soc_major_group'][row['soc_major_group']].append(row['gemini_won'])

        for dim, groups in data.items():
            dim_key = f'by_{dim}'
            for group, wins in groups.items():
                if len(wins) >= 10:
                    win_rate = sum(wins) / len(wins)
                    # Cohen's h for effect size
                    h = 2 * np.arcsin(np.sqrt(win_rate)) - 2 * np.arcsin(np.sqrt(0.5))
                    results[dim_key][group] = {
                        'win_rate': win_rate,
                        'n': len(wins),
                        'effect_size_h': h
                    }

        return results

    def identify_weaknesses(self, model_pair: Tuple[str, str],
                            threshold: float = 0.4) -> List[Dict]:
        """Identify areas where Gemini underperforms"""
        effect_sizes = self.compute_effect_sizes(model_pair)
        weaknesses = []

        for dimension, groups in effect_sizes.items():
            for group, data in groups.items():
                if data['win_rate'] < threshold and data['n'] >= 20:
                    weaknesses.append({
                        'dimension': dimension.replace('by_', ''),
                        'category': group,
                        'win_rate': data['win_rate'],
                        'n_samples': data['n'],
                        'effect_size': data['effect_size_h'],
                        'severity': 'high' if data['win_rate'] < 0.35 else 'moderate'
                    })

        # Sort by severity and sample size
        weaknesses.sort(key=lambda x: (x['win_rate'], -x['n_samples']))
        return weaknesses
```

### 9.2 PDF Report Generator

```python
# src/reports/pdf_generator.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime

class PDFReportGenerator:
    """Generate comprehensive PDF evaluation report"""

    def __init__(self, db: 'ResultsDatabase', analyzer: 'StatisticalAnalyzer',
                 output_dir: Path):
        self.db = db
        self.analyzer = analyzer
        self.output_dir = output_dir
        self.charts_dir = output_dir / "charts"
        self.charts_dir.mkdir(exist_ok=True)

        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='Title1',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        ))
        self.styles.add(ParagraphStyle(
            name='ExecutiveSummary',
            parent=self.styles['Normal'],
            fontSize=12,
            leading=18,
            spaceAfter=12
        ))

    def generate_report(self, config: 'EvalConfig') -> Path:
        """Generate the complete PDF report"""
        output_path = self.output_dir / "report.pdf"

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Title page
        story.extend(self._build_title_page(config))

        # Executive Summary
        story.append(PageBreak())
        story.extend(self._build_executive_summary())

        # Methodology
        story.append(PageBreak())
        story.extend(self._build_methodology_section(config))

        # Results Overview
        story.append(PageBreak())
        story.extend(self._build_results_overview())

        # Detailed Analysis
        story.append(PageBreak())
        story.extend(self._build_detailed_analysis())

        # Weakness Analysis
        story.append(PageBreak())
        story.extend(self._build_weakness_analysis())

        # Statistical Appendix
        story.append(PageBreak())
        story.extend(self._build_statistical_appendix())

        doc.build(story)
        return output_path

    def _build_title_page(self, config: 'EvalConfig') -> list:
        """Build title page"""
        elements = []

        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph(
            "Gemini Writing Evaluation Report",
            self.styles['Title1']
        ))
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(
            f"Comprehensive Analysis of Gemini 3.0 Pro/Flash<br/>"
            f"vs Competing Frontier Models",
            self.styles['Heading2']
        ))
        elements.append(Spacer(1, 1*inch))
        elements.append(Paragraph(
            f"Generated: {datetime.now():%Y-%m-%d %H:%M}<br/>"
            f"Run ID: {config.run_id}<br/>"
            f"Total Prompts: {config.num_prompts}<br/>"
            f"Model Pairs: {len(config.model_pairs)}",
            self.styles['Normal']
        ))

        return elements

    def _build_executive_summary(self) -> list:
        """Build executive summary section"""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['Title1']))

        # Get overall results
        win_rates = self.db.get_win_rates()

        summary_text = """
        This report presents the results of a comprehensive evaluation comparing
        Gemini 3.0 Pro and Flash against competing frontier language models on
        realistic professional writing tasks derived from O*NET occupational data.
        """
        elements.append(Paragraph(summary_text, self.styles['ExecutiveSummary']))

        # Key findings table
        findings_data = [["Model Pair", "Win Rate", "CI (95%)", "Significance"]]

        for pair, data in win_rates.items():
            result = self.analyzer.compute_win_rate(pair)
            if result:
                sig = "***" if result.p_value < 0.001 else "**" if result.p_value < 0.01 else "*" if result.p_value < 0.05 else "ns"
                findings_data.append([
                    f"Gemini vs {pair[1]}",
                    f"{result.win_rate:.1%}",
                    f"[{result.ci_low:.1%}, {result.ci_high:.1%}]",
                    sig
                ])

        table = Table(findings_data, colWidths=[2*inch, 1*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.5*inch))

        # Top weaknesses
        elements.append(Paragraph("Key Weaknesses Identified", self.styles['Heading2']))

        for pair in win_rates.keys():
            weaknesses = self.analyzer.identify_weaknesses(pair, threshold=0.45)[:3]
            if weaknesses:
                elements.append(Paragraph(f"vs {pair[1]}:", self.styles['Heading3']))
                items = []
                for w in weaknesses:
                    items.append(ListItem(Paragraph(
                        f"{w['dimension']}: {w['category']} ({w['win_rate']:.1%} win rate, n={w['n_samples']})",
                        self.styles['Normal']
                    )))
                elements.append(ListFlowable(items, bulletType='bullet'))

        return elements

    def _build_methodology_section(self, config: 'EvalConfig') -> list:
        """Build methodology section"""
        elements = []
        elements.append(Paragraph("Methodology", self.styles['Title1']))

        methodology_text = """
        <b>Data Source:</b> O*NET 30.1 database containing 18,796 task statements
        across 923 occupations covering the full US economy.<br/><br/>

        <b>Prompt Generation:</b> Three-phase approach combining algorithmic
        dimension sampling with LLM enrichment for realistic context.<br/><br/>

        <b>Evaluation:</b> Pairwise comparison using best-of-5 voting from
        3 judge models (Claude Opus 4.5, GPT-5.2, Gemini 3 Pro) with
        majority-of-majorities aggregation.<br/><br/>

        <b>Judge Personas:</b> Each comparison evaluated by both a
        simulated writing expert and simulated target recipient.<br/><br/>

        <b>Position Bias Mitigation:</b> Response ordering randomized with
        deterministic shuffling for reproducibility.
        """
        elements.append(Paragraph(methodology_text, self.styles['Normal']))

        return elements

    def _build_results_overview(self) -> list:
        """Build results overview with charts"""
        elements = []
        elements.append(Paragraph("Results Overview", self.styles['Title1']))

        # Generate and embed win rate chart
        self._generate_win_rate_chart()
        elements.append(Image(str(self.charts_dir / "win_rates.png"), width=6*inch, height=4*inch))

        # Generate heatmap by dimension
        self._generate_heatmap()
        elements.append(Image(str(self.charts_dir / "heatmap.png"), width=6*inch, height=4*inch))

        return elements

    def _generate_win_rate_chart(self):
        """Generate win rate bar chart"""
        win_rates = self.db.get_win_rates()

        models = []
        rates = []
        errors = []

        for pair, data in win_rates.items():
            result = self.analyzer.compute_win_rate(pair)
            if result:
                models.append(f"vs {pair[1]}")
                rates.append(result.win_rate * 100)
                errors.append((result.ci_high - result.ci_low) / 2 * 100)

        fig = go.Figure(data=[
            go.Bar(
                x=models,
                y=rates,
                error_y=dict(type='data', array=errors),
                marker_color=['green' if r > 50 else 'red' for r in rates]
            )
        ])

        fig.add_hline(y=50, line_dash="dash", line_color="gray")
        fig.update_layout(
            title="Gemini Win Rates by Competitor",
            yaxis_title="Win Rate (%)",
            yaxis_range=[0, 100]
        )

        fig.write_image(str(self.charts_dir / "win_rates.png"))

    def _generate_heatmap(self):
        """Generate win rate heatmap by dimension"""
        # Implementation would query database and create heatmap
        pass

    def _build_detailed_analysis(self) -> list:
        """Build detailed analysis section"""
        elements = []
        elements.append(Paragraph("Detailed Analysis", self.styles['Title1']))

        # Bias analysis
        elements.append(Paragraph("Bias Analysis", self.styles['Heading2']))

        position_bias, p_pos = self.analyzer.analyze_position_bias()
        length_bias, p_len = self.analyzer.analyze_length_bias()
        judge_kappa = self.analyzer.compute_judge_agreement()

        bias_text = f"""
        <b>Position Bias:</b> {position_bias:.1%} preference for first position
        (p={p_pos:.4f}, {'significant' if p_pos < 0.05 else 'not significant'})<br/><br/>

        <b>Length Bias:</b> Correlation = {length_bias:.3f}
        (p={p_len:.4f}, {'significant' if p_len < 0.05 else 'not significant'})<br/><br/>

        <b>Inter-Judge Agreement:</b> Cohen's Kappa = {judge_kappa:.3f}
        ({'substantial' if judge_kappa > 0.6 else 'moderate' if judge_kappa > 0.4 else 'fair'} agreement)
        """
        elements.append(Paragraph(bias_text, self.styles['Normal']))

        return elements

    def _build_weakness_analysis(self) -> list:
        """Build comprehensive weakness analysis"""
        elements = []
        elements.append(Paragraph("Weakness Analysis", self.styles['Title1']))

        win_rates = self.db.get_win_rates()

        for pair in win_rates.keys():
            elements.append(Paragraph(f"Gemini vs {pair[1]}", self.styles['Heading2']))

            weaknesses = self.analyzer.identify_weaknesses(pair)

            if not weaknesses:
                elements.append(Paragraph("No significant weaknesses identified.", self.styles['Normal']))
                continue

            # Create weakness table
            weakness_data = [["Category", "Win Rate", "N", "Effect Size", "Severity"]]
            for w in weaknesses[:10]:
                weakness_data.append([
                    f"{w['dimension']}: {w['category']}",
                    f"{w['win_rate']:.1%}",
                    str(w['n_samples']),
                    f"{w['effect_size']:.3f}",
                    w['severity']
                ])

            table = Table(weakness_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.25*inch))

        return elements

    def _build_statistical_appendix(self) -> list:
        """Build statistical appendix"""
        elements = []
        elements.append(Paragraph("Statistical Appendix", self.styles['Title1']))

        appendix_text = """
        <b>Confidence Intervals:</b> Wilson score intervals at 95% confidence level.<br/><br/>

        <b>Significance Testing:</b> Two-tailed binomial test against null hypothesis
        of 50% win rate. Significance levels: * p<0.05, ** p<0.01, *** p<0.001.<br/><br/>

        <b>Effect Size:</b> Cohen's h for comparing proportions.<br/><br/>

        <b>Inter-rater Reliability:</b> Cohen's Kappa computed pairwise between
        judge models, then averaged.
        """
        elements.append(Paragraph(appendix_text, self.styles['Normal']))

        return elements
```

---

## 10. CLI and Configuration Presets

### 10.1 CLI Interface

```python
# src/cli.py

import typer
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import asyncio

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config.presets import PRESETS, get_preset
from .config.cost_estimator import CostEstimator
from .config.settings import EvalConfig
from .prompts.generator import PromptGenerator
from .eval.engine import EvaluationEngine
from .api.openrouter_client import OpenRouterClient
from .storage.database import ResultsDatabase
from .storage.checkpoint import CheckpointManager
from .tui.dashboard import EvalDashboard
from .analysis.statistics import StatisticalAnalyzer
from .reports.pdf_generator import PDFReportGenerator

app = typer.Typer(name="gemini-eval", help="Gemini Writing Evaluation Framework")
console = Console()

@app.command()
def run(
    preset: int = typer.Option(None, "--preset", "-p", help="Preset level 1-10"),
    prompts: int = typer.Option(None, "--prompts", "-n", help="Number of prompts"),
    models: str = typer.Option(None, "--models", "-m", help="Comma-separated model pairs"),
    judges: str = typer.Option(None, "--judges", "-j", help="Comma-separated judge models"),
    votes: int = typer.Option(5, "--votes", "-v", help="Votes per judge"),
    occupations: str = typer.Option(None, "--occupations", "-o", help="O*NET occupation filter"),
    industries: str = typer.Option(None, "--industries", "-i", help="NAICS industry filter"),
    job_zones: str = typer.Option(None, "--job-zones", help="Job zone filter (1-5)"),
    seed: int = typer.Option(None, "--seed", "-s", help="Random seed"),
    output: Path = typer.Option(Path("results"), "--output", "-O", help="Output directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    resume: Path = typer.Option(None, "--resume", "-r", help="Resume from checkpoint"),
    api_key: str = typer.Option(None, "--api-key", envvar="OPENROUTER_API_KEY"),
):
    """Run a Gemini writing evaluation"""

    if not api_key:
        console.print("[red]Error: OpenRouter API key required[/red]")
        console.print("Set OPENROUTER_API_KEY environment variable or use --api-key")
        raise typer.Exit(1)

    # Build configuration
    if preset:
        config = get_preset(preset)
        config.openrouter_api_key = api_key
    else:
        config = EvalConfig(
            run_id=f"eval_{datetime.now():%Y%m%d_%H%M%S}",
            openrouter_api_key=api_key,
            num_prompts=prompts or 100,
            random_seed=seed or int(datetime.now().timestamp()),
            output_dir=str(output)
        )

    # Apply overrides
    if prompts:
        config.num_prompts = prompts
    if seed:
        config.random_seed = seed

    # Show cost estimate
    estimator = CostEstimator()
    estimate = estimator.estimate(
        num_prompts=config.num_prompts,
        model_pairs=config.model_pairs,
        judge_configs=[{'model_id': j.model.id, 'votes': j.votes_per_comparison} for j in config.judges]
    )
    time_low, time_high = estimator.estimate_time(
        estimate.num_comparisons,
        estimate.num_judge_calls
    )

    # Display estimate
    display_estimate(config, estimate, time_low, time_high)

    if dry_run:
        return

    # Confirm
    if not typer.confirm("Proceed with evaluation?"):
        raise typer.Exit(0)

    # Run evaluation
    asyncio.run(run_evaluation(config, resume))


def display_estimate(config: 'EvalConfig', estimate: 'CostEstimate',
                     time_low: float, time_high: float):
    """Display cost and time estimate"""
    table = Table(title="EVAL RUN ESTIMATE", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Prompts", str(estimate.num_prompts))
    table.add_row("Model pairs", str(estimate.num_model_pairs))
    table.add_row("Total comparisons", str(estimate.num_comparisons))
    table.add_row("", "")
    table.add_row("Judge config", f"{len(config.judges)} judges x 5 votes x 2 personas")
    table.add_row("Total judge calls", str(estimate.num_judge_calls))
    table.add_row("", "")
    table.add_row("ESTIMATED COST", "")
    table.add_row("  Response generation", f"${estimate.response_generation_low:.0f} - ${estimate.response_generation_high:.0f}")
    table.add_row("  Judging", f"${estimate.judging_low:.0f} - ${estimate.judging_high:.0f}")
    table.add_row("  Total", f"[bold]${estimate.total_low:.0f} - ${estimate.total_high:.0f}[/bold]")
    table.add_row("", "")
    table.add_row("ESTIMATED TIME", f"{time_low:.1f} - {time_high:.1f} hours")

    console.print(Panel(table))


async def run_evaluation(config: 'EvalConfig', resume_path: Optional[Path] = None):
    """Run the actual evaluation"""
    # Setup run directory
    run_dir = Path(config.output_dir) / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Initialize components
    db = ResultsDatabase(run_dir / "results.db")
    db.connect()

    checkpoint = CheckpointManager(run_dir)

    if resume_path:
        if not checkpoint.load():
            console.print("[red]No checkpoint found to resume[/red]")
            return
        if not checkpoint.validate_config(config):
            console.print("[red]Config mismatch with checkpoint[/red]")
            return
        console.print(f"[green]Resuming from checkpoint: {checkpoint.state.current_prompt_index} prompts completed[/green]")
    else:
        checkpoint.initialize(config, config.num_prompts)

    async with OpenRouterClient(
        api_key=config.openrouter_api_key,
        max_retries=config.max_retries,
        timeout_seconds=config.timeout_seconds,
        max_concurrent=config.max_concurrent_requests,
        rate_limit_rpm=config.rate_limit_rpm
    ) as openrouter:

        # Generate prompts
        generator = PromptGenerator(
            onet_db_path="db/onet.db",
            openrouter_client=openrouter
        )

        console.print("[cyan]Generating prompts...[/cyan]")
        prompts = await generator.generate_prompts(
            num_prompts=config.num_prompts,
            base_seed=config.random_seed,
            config=config
        )

        # Store prompts
        for prompt in prompts:
            if not checkpoint.is_prompt_complete(prompt.prompt_id):
                db.insert_prompt(prompt)

        # Initialize evaluation engine
        engine = EvaluationEngine(config, openrouter, checkpoint)

        # Run with TUI
        dashboard = EvalDashboard(checkpoint)

        async def evaluation_loop():
            for i, prompt in enumerate(prompts):
                if checkpoint.is_prompt_complete(prompt.prompt_id):
                    continue

                dashboard.update_current_prompt({
                    'index': i + 1,
                    'task': prompt.prompt_text,
                    'occupation': prompt.occupation_title,
                    'industry': prompt.company.industry_name
                })

                for model_pair in config.model_pairs:
                    comparison_id = f"c_{prompt.prompt_id}_{model_pair[0]}_{model_pair[1]}"
                    if checkpoint.is_comparison_complete(comparison_id):
                        continue

                    comparison = await engine.evaluate_prompt(prompt, model_pair)

                    db.insert_response(comparison.response_a)
                    db.insert_response(comparison.response_b)
                    db.insert_comparison(comparison)
                    for vote in comparison.votes:
                        vote.comparison_id = comparison.comparison_id
                        db.insert_vote(vote)

                    checkpoint.mark_comparison_complete(comparison_id)
                    checkpoint.save()

                    dashboard.log_activity(
                        f"Prompt #{i+1} vs {model_pair[1]}: {'Gemini wins' if comparison.gemini_won else 'Opponent wins' if comparison.gemini_won is False else 'Tie'}"
                    )

                checkpoint.mark_prompt_complete(prompt.prompt_id)
                checkpoint.save()

        # Run dashboard with evaluation
        dashboard.run()

    # Generate report
    console.print("[cyan]Generating report...[/cyan]")
    analyzer = StatisticalAnalyzer(db)
    reporter = PDFReportGenerator(db, analyzer, run_dir / "reports")
    report_path = reporter.generate_report(config)

    console.print(f"[green]Evaluation complete! Report: {report_path}[/green]")

    db.close()


@app.command()
def presets():
    """List available evaluation presets"""
    table = Table(title="Evaluation Presets")
    table.add_column("Level", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Prompts")
    table.add_column("Models")
    table.add_column("Est. Cost")
    table.add_column("Est. Time")
    table.add_column("Use Case")

    for level, preset in PRESETS.items():
        table.add_row(
            str(level),
            preset['name'],
            str(preset['prompts']),
            f"{preset['model_pairs']} pairs",
            preset['est_cost'],
            preset['est_time'],
            preset['use_case']
        )

    console.print(table)


@app.command()
def compare(
    runs: List[Path] = typer.Argument(..., help="Run directories to compare"),
):
    """Compare results across multiple evaluation runs"""
    console.print(f"Comparing {len(runs)} runs...")
    # Implementation for cross-run comparison


@app.command()
def view(
    run_dir: Path = typer.Argument(..., help="Run directory to view"),
):
    """Interactive TUI viewer for evaluation results"""
    # Launch result viewer TUI
    pass


if __name__ == "__main__":
    app()
```

### 10.2 Preset Configurations

```python
# src/config/presets.py

PRESETS = {
    1: {
        'name': 'Sanity Check',
        'prompts': 5,
        'model_pairs': 1,
        'judges': 1,
        'votes': 1,
        'est_cost': '~$1',
        'est_time': '~2 min',
        'use_case': 'Does the system work?'
    },
    2: {
        'name': 'Smoke Test',
        'prompts': 20,
        'model_pairs': 1,
        'judges': 1,
        'votes': 3,
        'est_cost': '~$5',
        'est_time': '~5 min',
        'use_case': 'Quick functionality test'
    },
    3: {
        'name': 'Dev Iteration',
        'prompts': 50,
        'model_pairs': 2,
        'judges': 2,
        'votes': 3,
        'est_cost': '~$25',
        'est_time': '~15 min',
        'use_case': 'Development/debugging'
    },
    4: {
        'name': 'Quick Sample',
        'prompts': 100,
        'model_pairs': 2,
        'judges': 2,
        'votes': 5,
        'est_cost': '~$75',
        'est_time': '~30 min',
        'use_case': 'Fast directional signal'
    },
    5: {
        'name': 'Light Eval',
        'prompts': 200,
        'model_pairs': 3,
        'judges': 3,
        'votes': 3,
        'est_cost': '~$150',
        'est_time': '~1 hr',
        'use_case': 'Light but meaningful eval'
    },
    6: {
        'name': 'Standard Eval',
        'prompts': 500,
        'model_pairs': 4,
        'judges': 3,
        'votes': 5,
        'est_cost': '~$500',
        'est_time': '~3 hrs',
        'use_case': 'Standard evaluation run'
    },
    7: {
        'name': 'Thorough Eval',
        'prompts': 1000,
        'model_pairs': 4,
        'judges': 3,
        'votes': 5,
        'est_cost': '~$1,000',
        'est_time': '~6 hrs',
        'use_case': 'Thorough with good power'
    },
    8: {
        'name': 'Comprehensive',
        'prompts': 2000,
        'model_pairs': 6,
        'judges': 3,
        'votes': 5,
        'est_cost': '~$2,500',
        'est_time': '~12 hrs',
        'use_case': 'High statistical power'
    },
    9: {
        'name': 'Deep Dive',
        'prompts': 5000,
        'model_pairs': 6,
        'judges': 3,
        'votes': 5,
        'est_cost': '~$6,000',
        'est_time': '~24 hrs',
        'use_case': 'Publication-grade'
    },
    10: {
        'name': 'Full Kaboodle',
        'prompts': 10000,
        'model_pairs': 6,
        'judges': 3,
        'votes': 5,
        'est_cost': '~$12,000+',
        'est_time': '~48 hrs',
        'use_case': 'Maximum coverage'
    }
}

def get_preset(level: int) -> 'EvalConfig':
    """Get a preset configuration by level"""
    from .settings import EvalConfig
    from .models import MODELS, PRO_PAIRS, FLASH_PAIRS, JUDGE_MODELS
    from datetime import datetime

    preset = PRESETS.get(level)
    if not preset:
        raise ValueError(f"Unknown preset level: {level}")

    # Select model pairs based on count
    all_pairs = PRO_PAIRS + FLASH_PAIRS
    model_pairs = all_pairs[:preset['model_pairs']]

    # Select judges based on count
    judges = JUDGE_MODELS[:preset['judges']]

    return EvalConfig(
        run_id=f"eval_{datetime.now():%Y%m%d_%H%M%S}",
        preset_name=preset['name'],
        num_prompts=preset['prompts'],
        model_pairs=model_pairs,
        judges=[{
            'model': j,
            'votes_per_comparison': preset['votes'],
            'personas': ['writing_expert', 'target_recipient']
        } for j in judges],
        random_seed=int(datetime.now().timestamp()),
        output_dir='results'
    )
```

---

## 11. Project Structure

```
gemini-writing-eval/
├── pyproject.toml              # Project configuration
├── README.md                   # Documentation
├── PROMPT.md                   # Requirements document
│
├── db/
│   ├── onet.db                 # O*NET SQLite database
│   └── ONET_WRITING_REFERENCE.md
│
├── src/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── openrouter_client.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py           # Model specifications
│   │   ├── presets.py          # Evaluation presets
│   │   ├── settings.py         # Configuration schemas
│   │   └── cost_estimator.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py
│   │   ├── naics_mapper.py
│   │   ├── company_database.py
│   │   └── name_generator.py
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── schemas.py
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── judge_prompts.py
│   │   └── vote_aggregator.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── checkpoint.py
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── dashboard.py
│   │   └── viewer.py
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── statistics.py
│   │
│   └── reports/
│       ├── __init__.py
│       └── pdf_generator.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_onet_extractor.py
│   ├── test_prompt_generator.py
│   ├── test_eval_engine.py
│   └── test_statistics.py
│
└── results/                    # Output directory (gitignored)
    └── eval_YYYY-MM-DD_HH-MM-SS/
        ├── config.json
        ├── checkpoint.json
        ├── prompts.json
        ├── results.db
        └── reports/
            └── report.pdf
```

---

## 12. Implementation Phases

### Phase 1: Foundation (Week 1)
- Set up project structure and dependencies
- Implement O*NET data extractor
- Create basic prompt generation (Phase 1 & 2)
- Implement OpenRouter API client with retry logic

### Phase 2: Core Evaluation (Week 2)
- Implement evaluation engine
- Build judge prompt construction
- Implement vote aggregation
- Create SQLite storage layer
- Implement checkpoint/resume system

### Phase 3: TUI and Reporting (Week 3)
- Build Rich/Textual dashboard
- Implement live progress updates
- Create statistical analysis module
- Build PDF report generator

### Phase 4: Polish and Testing (Week 4)
- Comprehensive testing
- Cost estimation refinement
- Documentation
- Performance optimization

---

## 13. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limits | Configurable rate limiting, exponential backoff, circuit breaker |
| Cost overruns | Live cost tracking, preset limits, dry-run estimates |
| Data loss | Atomic checkpoint writes, SQLite transactions, incremental saves |
| Judge bias | Randomized presentation order, multiple judges, position bias detection |
| Prompt quality | Three-phase generation, LLM enrichment, O*NET grounding |
| Model refusals | Auto-loss handling, refusal categorization, sensitive topic tracking |

---

## 14. Success Criteria

1. **Reproducibility**: Same seed produces same prompts and evaluation order
2. **Robustness**: Graceful handling of API failures, full resumability
3. **Trustworthiness**: Statistical rigor with confidence intervals, bias detection
4. **Actionability**: Clear weakness identification with effect sizes
5. **Usability**: Intuitive CLI, live progress, comprehensive reporting
