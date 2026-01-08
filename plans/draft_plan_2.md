# Gemini Writing Evaluation Framework - Implementation Plan (Draft 2)

## Executive Summary

This document presents a comprehensive implementation plan for the Gemini Writing Evaluation Framework - a robust, scalable system for comparing Gemini 3.0 Pro/Flash against competing frontier LLMs (GPT-5.2, Claude Opus 4.5, Grok-4.1, Kimi K2, etc.) on realistic professional writing tasks derived from O*NET occupational data.

The framework prioritizes:
- **Realism**: Prompts grounded in actual US workforce writing tasks with real companies and names
- **Diversity**: Systematic coverage across 1,000+ occupations, 22 SOC groups, all job zones, and NAICS industries
- **Robustness**: Multi-judge ensemble with majority-of-majorities voting, position bias mitigation, and statistical rigor
- **Usability**: Rich TUI for progress visualization and results inspection, presets for cost control, full resumability

---

## Part 1: System Architecture Overview

### 1.1 High-Level Architecture

```
                                    +------------------+
                                    |   OpenRouter     |
                                    |   API Gateway    |
                                    +--------+---------+
                                             |
                     +-----------------------+-----------------------+
                     |                       |                       |
              +------v------+        +-------v-------+       +-------v-------+
              | Response    |        |    Judge      |       |   Prompt      |
              | Generator   |        |    Engine     |       |   Enricher    |
              +------+------+        +-------+-------+       +-------+-------+
                     |                       |                       |
                     +-----------------------+-----------------------+
                                             |
                                    +--------v---------+
                                    |   Orchestrator   |
                                    |   (Core Engine)  |
                                    +--------+---------+
                                             |
           +----------------+----------------+----------------+----------------+
           |                |                |                |                |
    +------v------+  +------v------+  +------v------+  +------v------+  +------v------+
    |   Prompt    |  |  Results    |  |    TUI      |  |   Report    |  | Checkpoint  |
    |  Pipeline   |  |   Store     |  |   Module    |  |  Generator  |  |   Manager   |
    +-------------+  +-------------+  +-------------+  +-------------+  +-------------+
           |                |
    +------v------+  +------v------+
    |   O*NET     |  |   SQLite    |
    |   Database  |  |   Results   |
    +-------------+  +-------------+
```

### 1.2 Core Components

| Component | Responsibility | Key Dependencies |
|-----------|----------------|------------------|
| **Orchestrator** | Coordinates all evaluation phases, manages state | All components |
| **Prompt Pipeline** | Extracts O*NET tasks, generates diverse prompts | O*NET DB, NAICS crosswalk |
| **Response Generator** | Sends prompts to models via OpenRouter | OpenRouter API |
| **Judge Engine** | Evaluates response pairs with ensemble voting | OpenRouter API |
| **Results Store** | Persists all data to SQLite | SQLite |
| **TUI Module** | Real-time progress visualization | rich/textual |
| **Report Generator** | Produces PDF analysis reports | plotly, reportlab |
| **Checkpoint Manager** | Handles pause/resume/crash recovery | Filesystem |

### 1.3 Technology Stack

```python
# Core Framework
python >= 3.11
asyncio                    # Async coordination
httpx                      # Async HTTP client for OpenRouter
pydantic >= 2.0            # Data validation and schemas

# Data & Storage
sqlite3                    # Results database
pandas                     # Data analysis
numpy                      # Numerical operations

# User Interface
textual >= 0.40            # Rich TUI framework
rich                       # Terminal formatting

# Visualization & Reporting
plotly                     # Interactive charts
matplotlib                 # Static visualizations
reportlab                  # PDF generation
weasyprint                 # HTML to PDF (alternative)

# Testing & Quality
pytest                     # Testing framework
pytest-asyncio             # Async test support
mypy                       # Type checking
ruff                       # Linting
```

---

## Part 2: Data Pipeline from O*NET to Prompts

### 2.1 O*NET Data Extraction Layer

#### 2.1.1 Database Schema Understanding

The O*NET 30.1 database contains 18,796 task statements across 923 occupations with tasks. Key tables:

```
task_statements -----> occupation_data -----> job_zones
      |                      |
      |                      +-----> skills
      |                      +-----> abilities
      |                      +-----> work_context
      |
      +-----> tasks_to_dwas -----> dwa_reference
```

#### 2.1.2 Task Extraction Module

```python
# src/data/onet_extractor.py

from dataclasses import dataclass
from typing import List, Optional
import sqlite3

@dataclass
class ONetTask:
    task_id: int
    onetsoc_code: str
    task: str
    task_type: str  # Core, Supplemental, or None
    occupation_title: str
    occupation_description: str
    job_zone: int  # 1-5
    soc_major_group: str  # 11-55
    soc_group_name: str
    writing_skill_importance: float  # 1-5 scale
    written_expression_ability: float  # 1-5 scale
    email_frequency: float  # 1-5 scale
    letter_memo_frequency: float  # 1-5 scale
    inferred_writing_category: str  # One of 10 categories

class ONetExtractor:
    """Extracts and enriches O*NET task data for prompt generation."""

    WRITING_CATEGORIES = {
        'explicit_writing': ['write', 'draft', 'compose', 'author'],
        'correspondence': ['correspond', 'email', 'letter', 'memo'],
        'reports': ['report', 'present', 'summarize'],
        'proposals': ['propos', 'negotiat', 'recommend'],
        'policy': ['polic', 'procedure', 'guideline'],
        'customer': ['customer', 'client', 'patient'],
        'training': ['train', 'instruct', 'curriculum'],
        'coordination': ['confer', 'coordinate', 'collaborate'],
        'contracts': ['contract', 'agreement', 'legal'],
        'feedback': ['evaluat', 'assess', 'feedback']
    }

    def __init__(self, db_path: str = "db/onet.db"):
        self.db_path = db_path

    def extract_all_writing_tasks(self) -> List[ONetTask]:
        """Extract all tasks where writing is likely needed."""
        query = """
        SELECT
            t.task_id,
            t.onetsoc_code,
            t.task,
            t.task_type,
            o.title as occupation_title,
            o.description as occupation_description,
            jz.job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major,
            COALESCE(sk.data_value, 0) as writing_skill,
            COALESCE(ab.data_value, 0) as written_expression,
            COALESCE(wc_email.data_value, 0) as email_freq,
            COALESCE(wc_letter.data_value, 0) as letter_freq
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        LEFT JOIN skills sk ON t.onetsoc_code = sk.onetsoc_code
            AND sk.element_id = '2.A.1.c' AND sk.scale_id = 'IM'
        LEFT JOIN abilities ab ON t.onetsoc_code = ab.onetsoc_code
            AND ab.element_id = '1.A.1.a.4' AND ab.scale_id = 'IM'
        LEFT JOIN work_context wc_email ON t.onetsoc_code = wc_email.onetsoc_code
            AND wc_email.element_id = '4.C.1.a.2.h' AND wc_email.scale_id = 'CX'
        LEFT JOIN work_context wc_letter ON t.onetsoc_code = wc_letter.onetsoc_code
            AND wc_letter.element_id = '4.C.1.a.2.j' AND wc_letter.scale_id = 'CX'
        WHERE {writing_filter}
        """
        # Build dynamic filter for writing-related tasks
        filters = self._build_writing_filter()
        # Execute and return enriched tasks
        ...

    def _classify_writing_category(self, task_text: str) -> str:
        """Infer the writing category from task text."""
        task_lower = task_text.lower()
        for category, keywords in self.WRITING_CATEGORIES.items():
            if any(kw in task_lower for kw in keywords):
                return category
        return 'general_communication'
```

### 2.2 Industry Mapping via NAICS Crosswalk

#### 2.2.1 BLS Occupation-Industry Matrix Integration

Since O*NET lacks direct NAICS codes, we use the BLS Occupation-Industry Matrix:

```python
# src/data/naics_mapper.py

@dataclass
class NAICSIndustry:
    naics_code: str
    naics_title: str
    sector: str  # 2-digit NAICS sector
    employment_share: float  # Percentage of occupation in this industry

class NAICSMapper:
    """Maps O*NET occupations to NAICS industries using BLS crosswalk."""

    # 20 NAICS Sectors
    NAICS_SECTORS = {
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

    def __init__(self, crosswalk_path: str = "data/bls_occ_industry_matrix.csv"):
        self.crosswalk = self._load_crosswalk(crosswalk_path)

    def get_industries_for_occupation(self, soc_code: str) -> List[NAICSIndustry]:
        """Return all industries where this occupation exists, with employment shares."""
        ...

    def sample_industry_for_task(self, soc_code: str, seed: int = None) -> NAICSIndustry:
        """Sample an industry weighted by employment share or uniformly."""
        ...
```

### 2.3 Company Grounding System

#### 2.3.1 Real Company Database

```python
# src/data/company_database.py

@dataclass
class Company:
    name: str
    ticker: Optional[str]
    naics_code: str
    naics_sector: str
    size_category: str  # 'fortune500', 'large', 'midmarket', 'small', 'startup'
    employee_count_range: str  # '1-10', '11-50', '51-200', '201-1000', '1001-10000', '10001+'
    founding_year: Optional[int]
    hq_location: str
    is_public: bool
    industry_description: str

class CompanyDatabase:
    """Provides real company names for prompt grounding."""

    def __init__(self):
        # Pre-populated database of ~5,000+ companies across all NAICS sectors
        # Includes mix of Fortune 500, mid-market, small businesses, startups
        self.companies = self._load_company_data()

    def sample_company(
        self,
        naics_sector: str,
        size_category: Optional[str] = None,
        seed: int = None
    ) -> Company:
        """Sample a real company matching the sector and optional size."""
        ...

    def get_companies_by_sector(self, naics_sector: str) -> List[Company]:
        """Get all companies in a NAICS sector."""
        ...
```

#### 2.3.2 Company Categories and Distribution

| Size Category | Definition | Target % in Prompts |
|---------------|------------|---------------------|
| Fortune 500 | Fortune 500 list | 15% |
| Large | >10,000 employees | 15% |
| Mid-market | 201-10,000 employees | 25% |
| Small | 11-200 employees | 25% |
| Startup | 1-10 employees, <5 years | 20% |

### 2.4 Realistic Name Generation

#### 2.4.1 Name Database with Demographics

```python
# src/data/name_generator.py

@dataclass
class PersonaName:
    first_name: str
    last_name: str
    full_name: str  # May include middle initial, title
    email_format: str  # firstname.lastname@company.com pattern
    generation: str  # 'GenZ', 'Millennial', 'GenX', 'Boomer', 'Silent'
    estimated_age_range: Tuple[int, int]
    gender_presentation: str  # 'masculine', 'feminine', 'neutral'
    ethnic_background: str  # For diversity tracking

class NameGenerator:
    """Generates realistic names with demographic diversity."""

    # Based on SSA name data and census demographics
    GENERATION_BIRTH_YEARS = {
        'GenZ': (1997, 2012),
        'Millennial': (1981, 1996),
        'GenX': (1965, 1980),
        'Boomer': (1946, 1964),
        'Silent': (1928, 1945)
    }

    def __init__(self):
        # Load name databases by decade and ethnicity
        self.first_names = self._load_first_names()
        self.last_names = self._load_last_names()

    def generate_name(
        self,
        generation: Optional[str] = None,
        ethnic_diversity_weight: float = 0.5,
        seed: int = None
    ) -> PersonaName:
        """Generate a realistic name optionally constrained by generation."""
        ...

    def format_email(self, name: PersonaName, company: Company) -> str:
        """Generate realistic email address."""
        patterns = [
            f"{name.first_name.lower()}.{name.last_name.lower()}@{company.name.lower().replace(' ', '')}.com",
            f"{name.first_name[0].lower()}{name.last_name.lower()}@{company.name.lower().replace(' ', '')}.com",
            f"{name.first_name.lower()}{name.last_name[0].lower()}@{company.name.lower().replace(' ', '')}.com"
        ]
        return random.choice(patterns)
```

---

## Part 3: Prompt Generation Methodology

### 3.1 Three-Phase Generation Pipeline

#### Phase 1: Offline LLM-Based Persona Generation (Pre-processing)

Before evaluation runs, generate diverse persona/context variations:

```python
# src/prompts/phase1_persona_generator.py

class PersonaGenerator:
    """Generates diverse persona contexts using frontier LLMs."""

    # Use multiple models to avoid single-model bias
    GENERATION_MODELS = [
        'google/gemini-3.0-pro',
        'openai/gpt-5.2',
        'anthropic/claude-opus-4.5'
    ]

    async def generate_persona_variations(
        self,
        onet_task: ONetTask,
        num_variations: int = 10
    ) -> List[PersonaContext]:
        """Generate persona variations for a single O*NET task."""

        system_prompt = """
        You are helping create diverse writing task scenarios for an LLM evaluation.
        Given an O*NET occupational task, generate realistic persona contexts that vary across:
        - Age/generation (GenZ to Boomer)
        - Skill/experience level (entry to executive)
        - Formality requirements (casual to extremely formal)
        - Urgency (routine to crisis)
        - Relationship context (first contact to long-term)
        - Emotional context (neutral to high-stakes)

        Output JSON with exactly these fields:
        {
            "writer_name": "realistic full name",
            "writer_generation": "GenZ|Millennial|GenX|Boomer",
            "writer_job_title": "specific title",
            "writer_years_experience": number,
            "recipient_name": "realistic full name",
            "recipient_title": "specific title",
            "recipient_relationship": "new_contact|colleague|manager|direct_report|client|vendor",
            "formality_level": 1-5,
            "urgency_level": 1-5,
            "emotional_context": "routine|positive|negative|crisis|celebratory",
            "audience_size": "one_to_one|small_group|department|company_wide|public",
            "competing_objectives": ["list of any tensions in the task"]
        }
        """

        user_prompt = f"""
        O*NET Occupation: {onet_task.occupation_title}
        Job Zone (skill level 1-5): {onet_task.job_zone}
        Task: {onet_task.task}

        Generate {num_variations} diverse persona contexts for this task.
        Ensure maximum diversity - each should feel distinctly different.
        """

        # Rotate through generation models
        model = random.choice(self.GENERATION_MODELS)
        response = await self.openrouter_client.generate(model, system_prompt, user_prompt)
        return self._parse_persona_contexts(response)
```

#### Phase 2: Algorithmic Combination (Deterministic)

```python
# src/prompts/phase2_combiner.py

@dataclass
class PromptSkeleton:
    """Intermediate representation before final enrichment."""
    task_id: str
    onet_task: ONetTask
    persona: PersonaContext
    industry: NAICSIndustry
    company: Company
    writer_name: PersonaName
    recipient_name: PersonaName
    temporal_context: Optional[TemporalContext]
    attachments: List[AttachmentReference]
    message_position: str  # 'initial', 'reply', 'followup'
    english_variant: str  # 'en-US', 'en-GB', 'en-AU', 'non-native'

class PromptCombiner:
    """Algorithmically combines components into prompt skeletons."""

    def __init__(
        self,
        onet_extractor: ONetExtractor,
        naics_mapper: NAICSMapper,
        company_db: CompanyDatabase,
        name_generator: NameGenerator,
        seed: int = 42
    ):
        self.random = random.Random(seed)
        # ... store components

    def create_prompt_skeleton(
        self,
        onet_task: ONetTask,
        persona: PersonaContext
    ) -> PromptSkeleton:
        """Create a complete prompt skeleton from components."""

        # Sample industry based on occupation
        industry = self.naics_mapper.sample_industry_for_task(
            onet_task.onetsoc_code,
            seed=self._next_seed()
        )

        # Sample real company matching industry and appropriate size
        company = self.company_db.sample_company(
            naics_sector=industry.sector,
            size_category=self._determine_company_size(persona),
            seed=self._next_seed()
        )

        # Generate names matching persona characteristics
        writer_name = self.name_generator.generate_name(
            generation=persona.writer_generation,
            seed=self._next_seed()
        )
        recipient_name = self.name_generator.generate_name(seed=self._next_seed())

        # Determine if temporal context is relevant
        temporal_context = self._generate_temporal_context(onet_task, persona)

        # Determine if attachments are realistic for this task
        attachments = self._generate_attachment_refs(onet_task)

        # Determine message position
        message_position = self._sample_message_position(persona)

        # Sample English variant (90% en-US, 10% international)
        english_variant = self._sample_english_variant()

        return PromptSkeleton(...)

    def generate_prompt_set(
        self,
        num_prompts: int,
        stratification: StratificationConfig
    ) -> List[PromptSkeleton]:
        """Generate a stratified set of prompt skeletons."""

        # Ensure even distribution across:
        # - Job zones (1-5)
        # - SOC major groups (22 groups)
        # - NAICS sectors (20 sectors)
        # - Formality levels (5 levels)
        # - Generations (5 groups)
        # - Writing categories (10 categories)

        prompts = []
        quotas = self._calculate_quotas(num_prompts, stratification)

        for quota_bucket, count in quotas.items():
            bucket_prompts = self._generate_for_bucket(quota_bucket, count)
            prompts.extend(bucket_prompts)

        self.random.shuffle(prompts)
        return prompts[:num_prompts]
```

#### Phase 3: LLM Enrichment (Context-Heavy Prompts)

```python
# src/prompts/phase3_enricher.py

class PromptEnricher:
    """Uses LLM to add rich context to prompt skeletons."""

    async def enrich_prompt(self, skeleton: PromptSkeleton) -> FinalPrompt:
        """Transform skeleton into a fully-realized prompt."""

        # Determine enrichment needs
        needs_attachments = len(skeleton.attachments) > 0
        needs_prior_context = skeleton.message_position in ['reply', 'followup']
        needs_tone_example = self._should_include_tone_example(skeleton)
        is_ambiguous = self._should_be_ambiguous(skeleton)

        # Build enrichment request
        enrichment_prompt = self._build_enrichment_prompt(
            skeleton,
            needs_attachments=needs_attachments,
            needs_prior_context=needs_prior_context,
            needs_tone_example=needs_tone_example,
            make_ambiguous=is_ambiguous
        )

        # Use rotating LLMs for generation
        model = self._select_enrichment_model()
        enriched = await self.openrouter_client.generate(model, enrichment_prompt)

        return self._construct_final_prompt(skeleton, enriched)
```

### 3.2 Final Prompt Schema

```python
# src/schemas/prompt_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class FormalityLevel(Enum):
    VERY_CASUAL = 1
    CASUAL = 2
    NEUTRAL = 3
    FORMAL = 4
    VERY_FORMAL = 5

class UrgencyLevel(Enum):
    ROUTINE = 1
    LOW = 2
    MODERATE = 3
    HIGH = 4
    CRITICAL = 5

class EmotionalContext(Enum):
    ROUTINE = "routine"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CRISIS = "crisis"
    CELEBRATORY = "celebratory"
    CONFLICT = "conflict"

class WriterPersona(BaseModel):
    name: str
    email: str
    job_title: str
    generation: str  # GenZ, Millennial, GenX, Boomer
    years_experience: int
    skill_level: str  # entry, mid, senior, executive
    english_variant: str = "en-US"

class RecipientPersona(BaseModel):
    name: str
    email: Optional[str]
    job_title: str
    relationship_to_writer: str
    english_variant: str = "en-US"

class CompanyContext(BaseModel):
    name: str
    size_category: str
    employee_count: str
    naics_code: str
    naics_sector: str
    industry_description: str
    hq_location: str

class Attachment(BaseModel):
    reference_text: str  # "See attached Q3 report"
    summary_content: str  # Actual content/summary to include

class PriorMessage(BaseModel):
    sender: str
    content: str
    timestamp: Optional[str]

class InstructionConstraint(BaseModel):
    constraint_type: str  # 'length', 'format', 'tone', 'exclusion'
    constraint_value: str
    is_explicit: bool = True

class FinalPrompt(BaseModel):
    """Complete prompt ready for model evaluation."""

    # Identifiers
    prompt_id: str
    version: str = "1.0"

    # O*NET Source
    onet_task_id: int
    onet_soc_code: str
    onet_occupation_title: str
    onet_task_statement: str
    job_zone: int
    soc_major_group: str
    inferred_writing_category: str

    # Industry & Company
    naics_code: str
    naics_sector: str
    company: CompanyContext

    # Personas
    writer: WriterPersona
    recipients: List[RecipientPersona]
    cc_recipients: List[RecipientPersona] = []

    # Context
    formality_level: FormalityLevel
    urgency_level: UrgencyLevel
    emotional_context: EmotionalContext
    audience_size: str
    message_position: str  # 'initial', 'reply', 'followup'
    communication_channel: str  # inferred: 'email', 'memo', 'report', 'message', 'post'

    # Temporal
    temporal_context: Optional[str]  # "It's Q4 2025, the board meeting is Friday..."

    # Content
    task_description: str  # The full writing task prompt
    prior_messages: List[PriorMessage] = []
    attachments: List[Attachment] = []
    tone_example: Optional[str] = None

    # Constraints
    competing_objectives: List[str] = []
    instruction_constraints: List[InstructionConstraint] = []

    # Metadata for analysis
    is_sensitive_topic: bool = False
    sensitive_topic_category: Optional[str]
    is_ambiguous: bool = False
    is_revision_task: bool = False

    # Language (for future extensibility)
    language: str = "en"
    language_variant: str = "en-US"

    # Generation metadata
    generated_by_model: str
    generation_timestamp: str
    random_seed: int
```

### 3.3 Example Generated Prompts

#### Example 1: Formal Executive Communication

```json
{
  "prompt_id": "eval_2025_001_00142",
  "onet_task_statement": "Draft correspondence for executive review",
  "onet_occupation_title": "Administrative Services Manager",
  "job_zone": 4,
  "company": {
    "name": "Deloitte",
    "size_category": "large",
    "naics_sector": "54"
  },
  "writer": {
    "name": "Marcus Thompson",
    "job_title": "Senior Administrative Manager",
    "generation": "GenX",
    "years_experience": 18
  },
  "recipients": [{
    "name": "Patricia Gomez",
    "job_title": "Chief Operating Officer",
    "relationship_to_writer": "skip_level_manager"
  }],
  "formality_level": 5,
  "urgency_level": 3,
  "temporal_context": "Q1 2026 budget planning is underway. The executive committee meets Thursday.",
  "task_description": "Draft an email to Patricia Gomez, COO, summarizing the proposed administrative cost reduction initiatives for Q1 2026. The email will be reviewed by the CFO before being included in the executive committee's budget materials. Be comprehensive but the COO has limited time - keep it scannable.",
  "competing_objectives": ["Be comprehensive but concise", "Sound confident but not presumptuous"],
  "attachments": [{
    "reference_text": "Per the attached analysis",
    "summary_content": "Cost Analysis Summary: Three initiatives identified - consolidating vendor contracts (est. $340K savings), automating AP workflow (est. $180K), reducing office footprint (est. $520K). Total projected annual savings: $1.04M. Implementation timeline: 6-9 months."
  }]
}
```

#### Example 2: Casual Internal Communication

```json
{
  "prompt_id": "eval_2025_001_00287",
  "onet_task_statement": "Communicate with team members to coordinate activities",
  "onet_occupation_title": "Software Developer",
  "job_zone": 4,
  "company": {
    "name": "Figma",
    "size_category": "midmarket",
    "naics_sector": "51"
  },
  "writer": {
    "name": "Jordan Kim",
    "job_title": "Senior Software Engineer",
    "generation": "Millennial",
    "years_experience": 7
  },
  "recipients": [{
    "name": "The frontend team",
    "job_title": "Team Channel",
    "relationship_to_writer": "peers"
  }],
  "formality_level": 2,
  "urgency_level": 2,
  "communication_channel": "slack_message",
  "task_description": "Write a Slack message to the frontend team channel about pushing the component library migration to next sprint. The original deadline was this Friday but two unexpected bugs came up. You need to explain the delay without making it sound like an excuse, and ask if anyone can help with the bug fixes.",
  "competing_objectives": ["Explain the situation honestly without sounding defensive"],
  "emotional_context": "negative"
}
```

#### Example 3: Customer Complaint Response

```json
{
  "prompt_id": "eval_2025_001_00563",
  "onet_task_statement": "Resolve customer complaints regarding sales and service",
  "onet_occupation_title": "Customer Service Representative",
  "job_zone": 2,
  "company": {
    "name": "Chewy",
    "size_category": "large",
    "naics_sector": "44-45"
  },
  "writer": {
    "name": "Aisha Patel",
    "job_title": "Customer Experience Specialist",
    "generation": "GenZ",
    "years_experience": 2
  },
  "recipients": [{
    "name": "Robert Chen",
    "relationship_to_writer": "customer"
  }],
  "message_position": "reply",
  "prior_messages": [{
    "sender": "Robert Chen",
    "content": "This is ridiculous. I ordered food for my dog THREE WEEKS AGO and it still hasn't arrived. My dog has special dietary needs and I've had to buy expensive food locally because of your incompetence. I've been a loyal customer for 5 years and this is how you treat me? I want a full refund AND compensation for the extra money I've spent. If this isn't resolved immediately I'm canceling my Autoship and telling everyone I know to avoid Chewy."
  }],
  "task_description": "Respond to this upset customer email. Acknowledge their frustration, take ownership of the issue, explain what you can do (you can offer full refund + $50 credit, expedited reshipping, or both), and try to retain them as a customer. Be empathetic but don't be overly apologetic or make promises you can't keep.",
  "competing_objectives": ["Be empathetic without being excessively apologetic", "Retain the customer while being honest about what you can offer"],
  "is_sensitive_topic": false
}
```

---

## Part 4: Evaluation Flow and Judging System

### 4.1 Evaluation Orchestration

#### 4.1.1 Core Evaluation Loop

```python
# src/evaluation/orchestrator.py

class EvaluationOrchestrator:
    """Main coordinator for evaluation runs."""

    def __init__(
        self,
        config: EvalConfig,
        openrouter_client: OpenRouterClient,
        checkpoint_manager: CheckpointManager,
        results_store: ResultsStore,
        tui: ProgressTUI
    ):
        self.config = config
        self.openrouter = openrouter_client
        self.checkpoint = checkpoint_manager
        self.results = results_store
        self.tui = tui

    async def run_evaluation(self) -> EvalResults:
        """Execute the full evaluation pipeline."""

        # Phase 1: Load or generate prompts
        prompts = await self._load_prompts()
        self.tui.set_total_prompts(len(prompts))

        # Phase 2: Generate responses from all models
        await self._generate_all_responses(prompts)
        self.tui.mark_phase_complete('generation')

        # Phase 3: Judge all comparisons
        await self._judge_all_comparisons(prompts)
        self.tui.mark_phase_complete('judging')

        # Phase 4: Compute statistics and generate reports
        results = await self._analyze_results()
        self.tui.mark_phase_complete('analysis')

        return results

    async def _generate_all_responses(self, prompts: List[FinalPrompt]):
        """Generate responses from all models for all prompts."""

        for prompt in prompts:
            if self.checkpoint.is_prompt_complete(prompt.prompt_id, 'responses'):
                continue

            # Generate responses in parallel for all models
            tasks = []
            for model in self.config.models:
                tasks.append(self._generate_response(prompt, model))

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle failures
            for model, response in zip(self.config.models, responses):
                if isinstance(response, Exception):
                    self._handle_generation_failure(prompt, model, response)
                else:
                    await self.results.store_response(prompt.prompt_id, model, response)

            self.checkpoint.mark_prompt_responses_complete(prompt.prompt_id)
            self.tui.update_progress()

    async def _judge_all_comparisons(self, prompts: List[FinalPrompt]):
        """Judge all pairwise comparisons for all prompts."""

        for prompt in prompts:
            for model_pair in self.config.model_pairs:
                if self.checkpoint.is_comparison_complete(
                    prompt.prompt_id, model_pair
                ):
                    continue

                # Get responses
                response_a = await self.results.get_response(
                    prompt.prompt_id, model_pair.gemini_model
                )
                response_b = await self.results.get_response(
                    prompt.prompt_id, model_pair.competitor_model
                )

                # Determine shuffle order (deterministic)
                order = self._determine_order(prompt.prompt_id, model_pair)

                # Run ensemble judging
                judgment = await self._run_ensemble_judgment(
                    prompt, response_a, response_b, order
                )

                await self.results.store_judgment(
                    prompt.prompt_id, model_pair, judgment
                )
                self.checkpoint.mark_comparison_complete(
                    prompt.prompt_id, model_pair
                )
                self.tui.update_judgment_progress(model_pair, judgment)
```

#### 4.1.2 Model Pairing Configuration

```python
# src/config/model_pairs.py

@dataclass
class ModelPair:
    gemini_model: str
    competitor_model: str
    tier: str  # 'pro' or 'flash'

# Pro-tier comparisons
PRO_PAIRS = [
    ModelPair('google/gemini-3.0-pro', 'openai/gpt-5.2-thinking', 'pro'),
    ModelPair('google/gemini-3.0-pro', 'anthropic/claude-opus-4.5', 'pro'),
    ModelPair('google/gemini-3.0-pro', 'x-ai/grok-4.1-thinking', 'pro'),
    ModelPair('google/gemini-3.0-pro', 'moonshot/kimi-k2-thinking', 'pro'),
]

# Flash-tier comparisons
FLASH_PAIRS = [
    ModelPair('google/gemini-3.0-flash', 'openai/gpt-4.1', 'flash'),
    ModelPair('google/gemini-3.0-flash', 'anthropic/claude-sonnet', 'flash'),
]
```

### 4.2 Judge Engine Design

#### 4.2.1 Dual Persona Judging

```python
# src/evaluation/judge_engine.py

class JudgeEngine:
    """Implements dual-persona ensemble judging."""

    JUDGE_MODELS = [
        'anthropic/claude-opus-4.5',
        'openai/gpt-5.2',
        'google/gemini-3.0-pro'
    ]

    WRITING_EXPERT_SYSTEM_PROMPT = """
    You are an expert writing professional evaluating the quality of two written responses.
    You have extensive experience in professional communication, copywriting, and business writing.

    Evaluate based on:
    - Quality of writing craft (clarity, structure, flow, word choice)
    - Appropriate length for the task
    - Tone appropriateness for the context
    - Professionalism and polish
    - Authenticity - does it read like a real human wrote it, not AI-generated?
    - Avoidance of cliches and boilerplate (e.g., "I hope this email finds you well")
    - Task completion - did it fully address what was asked?

    IMPORTANT: Consider the full context of WHO is writing and TO WHOM.
    A casual Slack message from a GenZ engineer should sound different from
    a formal memo from a Boomer executive.
    """

    RECIPIENT_PERSONA_SYSTEM_PROMPT = """
    You are the intended recipient of these written communications.
    You will be given context about who you are and your relationship to the writer.

    Evaluate based on:
    - Would this message be effective for you?
    - Is it appropriate given your relationship with the sender?
    - Is it actionable and clear about what you should do?
    - Does the tone feel right for this context?
    - Would you perceive this as authentic human communication?
    - Would you respond positively to this message?

    Judge from YOUR perspective as the recipient, not as a writing expert.
    """

    async def judge_comparison(
        self,
        prompt: FinalPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        order: ResponseOrder
    ) -> EnsembleJudgment:
        """Run full ensemble judgment on a comparison."""

        # Prepare context for judges
        judge_context = self._build_judge_context(prompt)

        # Apply ordering (A/B shuffling)
        ordered_responses = self._apply_order(response_a, response_b, order)

        # Collect judgments from all judges and personas
        all_judgments = []

        for judge_model in self.JUDGE_MODELS:
            # Writing expert persona
            expert_judgments = await self._get_n_judgments(
                judge_model=judge_model,
                persona='writing_expert',
                system_prompt=self.WRITING_EXPERT_SYSTEM_PROMPT,
                context=judge_context,
                responses=ordered_responses,
                n=self.config.votes_per_judge
            )
            all_judgments.extend(expert_judgments)

            # Simulated recipient persona
            recipient_judgments = await self._get_n_judgments(
                judge_model=judge_model,
                persona='recipient',
                system_prompt=self._build_recipient_prompt(prompt),
                context=judge_context,
                responses=ordered_responses,
                n=self.config.votes_per_judge
            )
            all_judgments.extend(recipient_judgments)

        # Aggregate using majority-of-majorities
        return self._aggregate_judgments(all_judgments, order)

    def _build_recipient_prompt(self, prompt: FinalPrompt) -> str:
        """Build recipient-specific system prompt."""
        recipient = prompt.recipients[0]
        return f"""
        {self.RECIPIENT_PERSONA_SYSTEM_PROMPT}

        YOU ARE: {recipient.name}, {recipient.job_title}
        Your relationship to the writer: {recipient.relationship_to_writer}
        Company: {prompt.company.name}
        Context: {prompt.emotional_context.value}
        """
```

#### 4.2.2 Judgment Aggregation - Majority of Majorities

```python
# src/evaluation/aggregation.py

@dataclass
class JudgmentVote:
    judge_model: str
    persona: str  # 'writing_expert' or 'recipient'
    vote: str  # 'A', 'B', or 'TIE'
    confidence: float
    reasoning: str

@dataclass
class JudgeModelResult:
    judge_model: str
    votes: List[JudgmentVote]
    majority_winner: str  # 'A', 'B', or 'TIE'

@dataclass
class EnsembleJudgment:
    prompt_id: str
    model_pair: ModelPair
    order: ResponseOrder
    judge_results: List[JudgeModelResult]
    final_winner: str  # 'gemini', 'competitor', or 'tie'
    winner_unshuffled: str  # Actual model that won
    agreement_score: float  # Inter-judge agreement

class JudgmentAggregator:
    """Implements majority-of-majorities aggregation."""

    def aggregate(
        self,
        judgments: List[JudgmentVote],
        order: ResponseOrder
    ) -> EnsembleJudgment:
        """Aggregate votes using majority-of-majorities."""

        # Group by judge model
        by_judge = defaultdict(list)
        for j in judgments:
            by_judge[j.judge_model].append(j)

        # Get majority for each judge model
        judge_results = []
        for judge_model, votes in by_judge.items():
            majority = self._get_majority(votes)
            judge_results.append(JudgeModelResult(
                judge_model=judge_model,
                votes=votes,
                majority_winner=majority
            ))

        # Get majority across judges
        judge_winners = [jr.majority_winner for jr in judge_results]
        final_winner = self._get_majority_from_list(judge_winners)

        # Map back to actual models
        winner_unshuffled = self._unmap_winner(final_winner, order)

        # Calculate agreement
        agreement = self._calculate_agreement(judge_results)

        return EnsembleJudgment(
            judge_results=judge_results,
            final_winner=final_winner,
            winner_unshuffled=winner_unshuffled,
            agreement_score=agreement
        )

    def _get_majority(self, votes: List[JudgmentVote]) -> str:
        """Get majority winner from votes."""
        counts = Counter(v.vote for v in votes)
        if counts['A'] > counts['B']:
            return 'A'
        elif counts['B'] > counts['A']:
            return 'B'
        else:
            return 'TIE'

    def _calculate_agreement(
        self,
        judge_results: List[JudgeModelResult]
    ) -> float:
        """Calculate Fleiss' Kappa for inter-judge agreement."""
        # Implementation of Fleiss' Kappa
        ...
```

### 4.3 Position Bias Mitigation

#### 4.3.1 Deterministic Response Shuffling

```python
# src/evaluation/ordering.py

@dataclass
class ResponseOrder:
    """Tracks which model's response is shown as A vs B."""
    a_is_gemini: bool
    seed: int

class OrderingManager:
    """Manages deterministic response ordering to mitigate position bias."""

    def __init__(self, master_seed: int = 42):
        self.random = random.Random(master_seed)
        self._order_cache = {}

    def get_order(
        self,
        prompt_id: str,
        model_pair: ModelPair
    ) -> ResponseOrder:
        """Get deterministic order for a prompt-pair combination."""

        cache_key = f"{prompt_id}:{model_pair.gemini_model}:{model_pair.competitor_model}"
        if cache_key in self._order_cache:
            return self._order_cache[cache_key]

        # Use hash of cache_key for deterministic random
        seed = int(hashlib.sha256(cache_key.encode()).hexdigest()[:8], 16)
        a_is_gemini = seed % 2 == 0

        order = ResponseOrder(a_is_gemini=a_is_gemini, seed=seed)
        self._order_cache[cache_key] = order
        return order

    def validate_balance(
        self,
        prompts: List[str],
        model_pair: ModelPair
    ) -> Dict[str, int]:
        """Verify that ordering is approximately balanced."""
        gemini_as_a = sum(
            1 for p in prompts
            if self.get_order(p, model_pair).a_is_gemini
        )
        return {
            'gemini_as_a': gemini_as_a,
            'gemini_as_b': len(prompts) - gemini_as_a,
            'balance_ratio': gemini_as_a / len(prompts)
        }
```

### 4.4 Judge Prompt Template

```python
# src/evaluation/judge_prompts.py

JUDGE_PROMPT_TEMPLATE = """
## Writing Task Context

**Occupation:** {occupation_title}
**Industry:** {company_name} ({naics_sector})
**Task Type:** {writing_category}

### Writer Profile
- **Name:** {writer_name}
- **Role:** {writer_job_title}
- **Generation:** {writer_generation}
- **Experience:** {writer_years_experience} years

### Recipient Profile
- **Name:** {recipient_name}
- **Role:** {recipient_job_title}
- **Relationship:** {recipient_relationship}

### Communication Context
- **Channel:** {communication_channel}
- **Formality Level:** {formality_level}/5
- **Urgency:** {urgency_level}/5
- **Emotional Context:** {emotional_context}
- **Audience Size:** {audience_size}

### The Writing Task
{task_description}

{attachments_section}

{prior_messages_section}

{constraints_section}

---

## Response A
{response_a}

---

## Response B
{response_b}

---

## Your Evaluation

Compare the two responses above and determine which better accomplishes the writing task.

Consider:
1. **Task Completion**: Does it fully address what was asked?
2. **Tone Appropriateness**: Is the tone right for this specific writer/recipient/context?
3. **Authenticity**: Does it read like {writer_name} actually wrote it, not AI?
4. **Effectiveness**: Would {recipient_name} respond positively?
5. **Quality**: Clarity, structure, flow, word choice
6. **Length**: Is it the right length for this task?
7. **Cliche Avoidance**: Does it avoid obvious AI patterns?

{explicit_constraints_evaluation}

Output your judgment in this exact format:
```json
{{
    "winner": "A" | "B" | "TIE",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of your judgment"
}}
```
"""
```

### 4.5 Failure Handling

#### 4.5.1 Response Generation Failures

```python
# src/evaluation/failure_handler.py

class FailureCategory(Enum):
    SAFETY_REFUSAL = "safety_refusal"
    CAPABILITY_LIMITATION = "capability_limitation"
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE = "incomplete"
    OFF_TOPIC = "off_topic"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    RATE_LIMIT = "rate_limit"

@dataclass
class ResponseFailure:
    prompt_id: str
    model: str
    category: FailureCategory
    error_message: str
    response_content: Optional[str]  # Partial/problematic content if any
    timestamp: datetime
    retry_count: int

class FailureHandler:
    """Handles and categorizes response failures."""

    def categorize_failure(
        self,
        response: ModelResponse,
        error: Optional[Exception] = None
    ) -> FailureCategory:
        """Categorize the type of failure."""

        if error:
            if "rate limit" in str(error).lower():
                return FailureCategory.RATE_LIMIT
            if "timeout" in str(error).lower():
                return FailureCategory.TIMEOUT
            return FailureCategory.API_ERROR

        content = response.content.lower()

        # Check for safety refusals
        safety_patterns = [
            "i cannot", "i won't", "i'm not able to",
            "against my guidelines", "harmful", "inappropriate"
        ]
        if any(p in content for p in safety_patterns):
            return FailureCategory.SAFETY_REFUSAL

        # Check for capability limitations
        capability_patterns = [
            "i don't have access to", "i cannot browse",
            "i'm not able to see"
        ]
        if any(p in content for p in capability_patterns):
            return FailureCategory.CAPABILITY_LIMITATION

        # Check for incomplete responses
        if len(content) < 50 or response.finish_reason == "length":
            return FailureCategory.INCOMPLETE

        # Check for off-topic (requires LLM analysis)
        return self._check_off_topic(response)

    def apply_auto_loss(
        self,
        prompt_id: str,
        model_pair: ModelPair,
        failed_model: str
    ) -> EnsembleJudgment:
        """Create auto-loss judgment for failed model."""

        winner = 'gemini' if failed_model != model_pair.gemini_model else 'competitor'

        return EnsembleJudgment(
            prompt_id=prompt_id,
            model_pair=model_pair,
            final_winner=winner,
            winner_unshuffled=winner,
            agreement_score=1.0,  # Unanimous by definition
            is_auto_loss=True,
            auto_loss_reason=failed_model
        )
```

---

## Part 5: Results Storage and Analysis

### 5.1 SQLite Database Schema

```sql
-- src/data/schema.sql

-- Core tables for evaluation data
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    config_json TEXT NOT NULL,
    preset_level INTEGER,
    total_prompts INTEGER NOT NULL,
    status TEXT DEFAULT 'running',  -- running, completed, failed, paused
    random_seed INTEGER NOT NULL
);

CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    prompt_json TEXT NOT NULL,  -- Full FinalPrompt as JSON
    onet_task_id INTEGER,
    onet_soc_code TEXT,
    occupation_title TEXT,
    job_zone INTEGER,
    soc_major_group TEXT,
    naics_code TEXT,
    naics_sector TEXT,
    company_name TEXT,
    company_size TEXT,
    formality_level INTEGER,
    urgency_level INTEGER,
    emotional_context TEXT,
    writing_category TEXT,
    writer_generation TEXT,
    is_sensitive_topic BOOLEAN,
    is_ambiguous BOOLEAN,
    is_revision_task BOOLEAN,
    communication_channel TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model TEXT NOT NULL,
    content TEXT NOT NULL,
    response_length_chars INTEGER,
    response_length_words INTEGER,
    response_time_ms INTEGER,
    finish_reason TEXT,
    is_failure BOOLEAN DEFAULT FALSE,
    failure_category TEXT,
    failure_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model)
);

CREATE TABLE judgments (
    judgment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    judge_persona TEXT NOT NULL,  -- 'writing_expert' or 'recipient'
    vote_number INTEGER NOT NULL,  -- 1-5 for best-of-5
    response_a_is_gemini BOOLEAN NOT NULL,
    vote TEXT NOT NULL,  -- 'A', 'B', 'TIE'
    confidence REAL,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comparison_results (
    comparison_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    final_winner TEXT NOT NULL,  -- 'gemini', 'competitor', 'tie'
    is_auto_loss BOOLEAN DEFAULT FALSE,
    auto_loss_model TEXT,
    auto_loss_reason TEXT,
    agreement_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, gemini_model, competitor_model)
);

-- Indexes for common query patterns
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onet_soc_code);
CREATE INDEX idx_prompts_industry ON prompts(naics_sector);
CREATE INDEX idx_prompts_category ON prompts(writing_category);
CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model);
CREATE INDEX idx_judgments_prompt ON judgments(prompt_id);
CREATE INDEX idx_comparisons_winner ON comparison_results(final_winner);

-- Aggregation views
CREATE VIEW win_rates_by_pair AS
SELECT
    gemini_model,
    competitor_model,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN final_winner = 'gemini' THEN 1 ELSE 0 END) as gemini_wins,
    SUM(CASE WHEN final_winner = 'competitor' THEN 1 ELSE 0 END) as competitor_wins,
    SUM(CASE WHEN final_winner = 'tie' THEN 1 ELSE 0 END) as ties,
    ROUND(100.0 * SUM(CASE WHEN final_winner = 'gemini' THEN 1 ELSE 0 END) / COUNT(*), 2) as gemini_win_rate
FROM comparison_results
GROUP BY gemini_model, competitor_model;

CREATE VIEW win_rates_by_occupation AS
SELECT
    cr.gemini_model,
    cr.competitor_model,
    p.soc_major_group,
    p.occupation_title,
    COUNT(*) as total,
    ROUND(100.0 * SUM(CASE WHEN cr.final_winner = 'gemini' THEN 1 ELSE 0 END) / COUNT(*), 2) as gemini_win_rate
FROM comparison_results cr
JOIN prompts p ON cr.prompt_id = p.prompt_id
GROUP BY cr.gemini_model, cr.competitor_model, p.soc_major_group, p.occupation_title;

CREATE VIEW win_rates_by_writing_category AS
SELECT
    cr.gemini_model,
    cr.competitor_model,
    p.writing_category,
    COUNT(*) as total,
    ROUND(100.0 * SUM(CASE WHEN cr.final_winner = 'gemini' THEN 1 ELSE 0 END) / COUNT(*), 2) as gemini_win_rate
FROM comparison_results cr
JOIN prompts p ON cr.prompt_id = p.prompt_id
GROUP BY cr.gemini_model, cr.competitor_model, p.writing_category;
```

### 5.2 Results Store Implementation

```python
# src/data/results_store.py

class ResultsStore:
    """Manages persistent storage of all evaluation data."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.db_path = run_dir / "results.db"
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with schema."""
        with open("src/data/schema.sql") as f:
            schema = f.read()
        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema)
        conn.close()

    async def store_response(
        self,
        prompt_id: str,
        model: str,
        response: ModelResponse
    ):
        """Store a model response."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO responses
                (prompt_id, model, content, response_length_chars,
                 response_length_words, response_time_ms, finish_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt_id, model, response.content,
                len(response.content),
                len(response.content.split()),
                response.latency_ms,
                response.finish_reason
            ))
            await db.commit()

        # Also write to JSON file for easy access
        response_file = self.run_dir / "responses" / "by_prompt" / f"{prompt_id}_{model.replace('/', '_')}.json"
        response_file.parent.mkdir(parents=True, exist_ok=True)
        with open(response_file, 'w') as f:
            json.dump(response.dict(), f, indent=2)

    async def store_judgment(
        self,
        prompt_id: str,
        model_pair: ModelPair,
        judgment: EnsembleJudgment
    ):
        """Store complete judgment results."""
        async with aiosqlite.connect(self.db_path) as db:
            # Store individual votes
            for jr in judgment.judge_results:
                for vote in jr.votes:
                    await db.execute("""
                        INSERT INTO judgments
                        (prompt_id, gemini_model, competitor_model, judge_model,
                         judge_persona, vote_number, response_a_is_gemini,
                         vote, confidence, reasoning)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        prompt_id, model_pair.gemini_model,
                        model_pair.competitor_model, vote.judge_model,
                        vote.persona, vote.vote_number,
                        judgment.order.a_is_gemini, vote.vote,
                        vote.confidence, vote.reasoning
                    ))

            # Store aggregated result
            await db.execute("""
                INSERT INTO comparison_results
                (prompt_id, gemini_model, competitor_model, final_winner,
                 is_auto_loss, auto_loss_model, agreement_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt_id, model_pair.gemini_model,
                model_pair.competitor_model, judgment.winner_unshuffled,
                judgment.is_auto_loss, judgment.auto_loss_reason,
                judgment.agreement_score
            ))
            await db.commit()
```

### 5.3 Statistical Analysis Module

```python
# src/analysis/statistics.py

from scipy import stats
import numpy as np

class StatisticalAnalyzer:
    """Computes statistical metrics for evaluation results."""

    def compute_win_rate_with_ci(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95
    ) -> WinRateResult:
        """Compute win rate with Wilson score confidence interval."""
        if total == 0:
            return WinRateResult(rate=0, ci_low=0, ci_high=0, n=0)

        rate = wins / total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)

        # Wilson score interval
        denominator = 1 + z**2 / total
        center = (rate + z**2 / (2 * total)) / denominator
        spread = z * np.sqrt(rate * (1 - rate) / total + z**2 / (4 * total**2)) / denominator

        return WinRateResult(
            rate=rate * 100,
            ci_low=max(0, (center - spread) * 100),
            ci_high=min(100, (center + spread) * 100),
            n=total
        )

    def compute_cohens_kappa(
        self,
        judgments: List[JudgmentVote]
    ) -> float:
        """Compute Cohen's Kappa for inter-rater agreement."""
        # Group votes by (prompt, model_pair) to get pairs of raters
        # Compute observed agreement vs expected by chance
        ...

    def compute_fleiss_kappa(
        self,
        judge_results: List[JudgeModelResult]
    ) -> float:
        """Compute Fleiss' Kappa for multiple raters."""
        # For 3+ judges
        ...

    def significance_test(
        self,
        gemini_wins: int,
        competitor_wins: int,
        ties: int = 0
    ) -> SignificanceResult:
        """Two-tailed binomial test for win rate significance."""
        total = gemini_wins + competitor_wins  # Exclude ties
        if total == 0:
            return SignificanceResult(p_value=1.0, is_significant=False)

        # H0: win rate = 0.5
        p_value = stats.binom_test(gemini_wins, total, 0.5, alternative='two-sided')

        return SignificanceResult(
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=self._compute_effect_size(gemini_wins, competitor_wins)
        )

    def _compute_effect_size(self, wins_a: int, wins_b: int) -> float:
        """Compute effect size (Cohen's h for proportions)."""
        total = wins_a + wins_b
        if total == 0:
            return 0
        p1 = wins_a / total
        p2 = 0.5  # Expected under null
        h = 2 * (np.arcsin(np.sqrt(p1)) - np.arcsin(np.sqrt(p2)))
        return h
```

### 5.4 Bias Detection Module

```python
# src/analysis/bias_detection.py

class BiasDetector:
    """Detects systematic biases in models and judges."""

    async def detect_all_biases(
        self,
        results_store: ResultsStore
    ) -> BiasReport:
        """Run all bias detection analyses."""

        return BiasReport(
            position_bias=await self._detect_position_bias(results_store),
            length_bias=await self._detect_length_bias(results_store),
            format_bias=await self._detect_format_bias(results_store),
            judge_model_bias=await self._detect_judge_model_bias(results_store),
            formality_drift=await self._detect_formality_drift(results_store)
        )

    async def _detect_position_bias(
        self,
        store: ResultsStore
    ) -> PositionBiasResult:
        """Detect if judges prefer Response A over B systematically."""
        async with aiosqlite.connect(store.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    judge_model,
                    SUM(CASE WHEN vote = 'A' THEN 1 ELSE 0 END) as a_votes,
                    SUM(CASE WHEN vote = 'B' THEN 1 ELSE 0 END) as b_votes,
                    COUNT(*) as total
                FROM judgments
                WHERE vote != 'TIE'
                GROUP BY judge_model
            """)
            rows = await cursor.fetchall()

        biases = []
        for judge_model, a_votes, b_votes, total in rows:
            # Chi-square test for position preference
            expected = total / 2
            chi2 = ((a_votes - expected)**2 + (b_votes - expected)**2) / expected
            p_value = 1 - stats.chi2.cdf(chi2, df=1)

            biases.append({
                'judge_model': judge_model,
                'a_preference': a_votes / total,
                'b_preference': b_votes / total,
                'chi2': chi2,
                'p_value': p_value,
                'is_significant': p_value < 0.05
            })

        return PositionBiasResult(biases=biases)

    async def _detect_length_bias(
        self,
        store: ResultsStore
    ) -> LengthBiasResult:
        """Detect if longer/shorter responses win more often."""
        async with aiosqlite.connect(store.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    cr.final_winner,
                    r_gemini.response_length_words as gemini_length,
                    r_comp.response_length_words as competitor_length
                FROM comparison_results cr
                JOIN responses r_gemini ON cr.prompt_id = r_gemini.prompt_id
                    AND r_gemini.model = cr.gemini_model
                JOIN responses r_comp ON cr.prompt_id = r_comp.prompt_id
                    AND r_comp.model = cr.competitor_model
            """)
            rows = await cursor.fetchall()

        # Analyze correlation between length difference and outcome
        ...

    async def _detect_format_bias(
        self,
        store: ResultsStore
    ) -> FormatBiasResult:
        """Detect if models overuse certain formats (bullets, headers)."""
        async with aiosqlite.connect(store.db_path) as db:
            cursor = await db.execute("""
                SELECT model, content FROM responses
            """)
            rows = await cursor.fetchall()

        format_counts = defaultdict(lambda: defaultdict(int))
        for model, content in rows:
            if '- ' in content or '* ' in content:
                format_counts[model]['bullet_lists'] += 1
            if content.count('#') > 0:
                format_counts[model]['headers'] += 1
            if '1.' in content or '1)' in content:
                format_counts[model]['numbered_lists'] += 1
            format_counts[model]['total'] += 1

        return FormatBiasResult(format_counts=dict(format_counts))
```

---

## Part 6: TUI Implementation

### 6.1 Progress Dashboard with Textual

```python
# src/tui/progress_app.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable
from textual.containers import Container, Horizontal, Vertical

class EvalProgressApp(App):
    """Real-time progress visualization for evaluation runs."""

    CSS = """
    #overall-progress {
        height: 5;
        border: solid green;
        padding: 1;
    }

    #model-pairs {
        height: auto;
        border: solid blue;
    }

    #current-batch {
        height: 12;
        border: solid yellow;
    }

    #statistics {
        height: 8;
        border: solid magenta;
    }

    #activity-log {
        height: 8;
        border: solid cyan;
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
        ("d", "toggle_detail", "Detail view"),
        ("s", "show_stats", "Statistics"),
        ("h", "help", "Help"),
    ]

    def __init__(self, orchestrator: EvaluationOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.stats = RunningStats()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(id="run-info"),
            ProgressBar(id="overall-progress"),
            Static(id="phase-indicator"),
            id="overall-container"
        )
        yield Container(
            DataTable(id="model-pairs-table"),
            id="model-pairs"
        )
        yield Horizontal(
            Container(
                Static(id="current-prompt"),
                Horizontal(
                    Static(id="response-status"),
                    Static(id="judge-status"),
                ),
                id="current-batch"
            ),
            Container(
                Static(id="win-rates"),
                Static(id="performance"),
                id="statistics"
            ),
        )
        yield Container(
            Static(id="activity-log"),
            id="activity"
        )
        yield Container(
            Static(id="errors"),
            id="error-summary"
        )
        yield Footer()

    def on_mount(self):
        """Initialize the display."""
        self._setup_model_pairs_table()
        self._start_update_timer()

    def _setup_model_pairs_table(self):
        """Configure the model pairs progress table."""
        table = self.query_one("#model-pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate", "Status")

        for pair in self.orchestrator.config.model_pairs:
            table.add_row(
                f"Gemini vs {pair.competitor_model.split('/')[-1]}",
                "[dim]0/0[/dim]",
                "[dim]--[/dim]",
                "pending"
            )

    def update_progress(self, stats: ProgressStats):
        """Update all progress displays."""
        # Update overall progress
        progress = self.query_one("#overall-progress", ProgressBar)
        progress.update(total=stats.total_prompts, progress=stats.completed_prompts)

        # Update phase indicator
        phase = self.query_one("#phase-indicator", Static)
        phase.update(self._render_phase_indicator(stats.current_phase))

        # Update model pairs table
        self._update_model_pairs(stats.pair_stats)

        # Update current batch
        self._update_current_batch(stats.current_batch)

        # Update statistics
        self._update_statistics(stats)

    def _render_phase_indicator(self, current_phase: str) -> str:
        phases = ['Generation', 'Judging', 'Analysis']
        indicators = []
        for phase in phases:
            if phase.lower() == current_phase:
                indicators.append(f"[bold green]{phase} ◐[/bold green]")
            elif phases.index(phase) < phases.index(current_phase.capitalize()):
                indicators.append(f"[green]{phase} ✓[/green]")
            else:
                indicators.append(f"[dim]{phase} ○[/dim]")
        return " → ".join(indicators)

    def action_quit_safely(self):
        """Save checkpoint and quit."""
        self.orchestrator.checkpoint.save()
        self.exit()

    def action_pause(self):
        """Pause the evaluation."""
        self.orchestrator.pause()
        self.notify("Evaluation paused. Press 'p' again to resume.")
```

### 6.2 Results Viewer TUI

```python
# src/tui/results_viewer.py

class ResultsViewerApp(App):
    """Interactive viewer for exploring evaluation results."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Container(
                    FilterPanel(id="filters"),
                    id="filter-container"
                ),
                Container(
                    DataTable(id="results-table"),
                    id="results-container"
                ),
            ),
            id="main-content"
        )
        yield Container(
            Horizontal(
                Container(
                    Static(id="response-a"),
                    id="response-a-container"
                ),
                Container(
                    Static(id="response-b"),
                    id="response-b-container"
                ),
            ),
            id="comparison-view"
        )
        yield Container(
            Static(id="judgment-details"),
            id="judgment-container"
        )
        yield Footer()

    BINDINGS = [
        ("f", "toggle_filters", "Filters"),
        ("j", "next_result", "Next"),
        ("k", "prev_result", "Previous"),
        ("enter", "view_details", "View Details"),
        ("e", "export", "Export"),
    ]
```

---

## Part 7: Robustness Requirements Implementation

### 7.1 Checkpoint System

```python
# src/core/checkpoint.py

@dataclass
class CheckpointState:
    run_id: str
    phase: str  # 'generation', 'judging', 'analysis'
    completed_prompts: Set[str]
    completed_responses: Dict[str, Set[str]]  # prompt_id -> set of models
    completed_judgments: Set[str]  # "prompt_id:gemini_model:competitor_model"
    last_update: datetime
    error_count: int

class CheckpointManager:
    """Manages checkpoint state for resumability."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"
        self.state = self._load_or_create()

    def _load_or_create(self) -> CheckpointState:
        """Load existing checkpoint or create new one."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file) as f:
                data = json.load(f)
            return CheckpointState(
                run_id=data['run_id'],
                phase=data['phase'],
                completed_prompts=set(data['completed_prompts']),
                completed_responses={k: set(v) for k, v in data['completed_responses'].items()},
                completed_judgments=set(data['completed_judgments']),
                last_update=datetime.fromisoformat(data['last_update']),
                error_count=data['error_count']
            )
        return CheckpointState(
            run_id=str(uuid.uuid4()),
            phase='generation',
            completed_prompts=set(),
            completed_responses={},
            completed_judgments=set(),
            last_update=datetime.now(),
            error_count=0
        )

    def save(self):
        """Persist checkpoint to disk."""
        self.state.last_update = datetime.now()
        data = {
            'run_id': self.state.run_id,
            'phase': self.state.phase,
            'completed_prompts': list(self.state.completed_prompts),
            'completed_responses': {k: list(v) for k, v in self.state.completed_responses.items()},
            'completed_judgments': list(self.state.completed_judgments),
            'last_update': self.state.last_update.isoformat(),
            'error_count': self.state.error_count
        }
        # Atomic write
        temp_file = self.checkpoint_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        temp_file.rename(self.checkpoint_file)

    def is_prompt_complete(self, prompt_id: str, phase: str) -> bool:
        """Check if a prompt has been completed for a phase."""
        if phase == 'responses':
            return prompt_id in self.state.completed_prompts
        return False

    def is_comparison_complete(self, prompt_id: str, pair: ModelPair) -> bool:
        """Check if a specific comparison has been judged."""
        key = f"{prompt_id}:{pair.gemini_model}:{pair.competitor_model}"
        return key in self.state.completed_judgments

    def mark_prompt_responses_complete(self, prompt_id: str):
        """Mark all responses for a prompt as complete."""
        self.state.completed_prompts.add(prompt_id)
        self.save()

    def mark_comparison_complete(self, prompt_id: str, pair: ModelPair):
        """Mark a comparison as judged."""
        key = f"{prompt_id}:{pair.gemini_model}:{pair.competitor_model}"
        self.state.completed_judgments.add(key)
        self.save()
```

### 7.2 API Retry Logic

```python
# src/api/openrouter_client.py

class OpenRouterClient:
    """Async client for OpenRouter API with retry logic."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: float = 120.0
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://gemini-writing-eval.example.com",
                "X-Title": "Gemini Writing Evaluation"
            }
        )
        self._rate_limiter = RateLimiter()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7
    ) -> ModelResponse:
        """Generate a completion with retry logic."""

        await self._rate_limiter.acquire(model)

        start_time = time.time()
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temperature
                }
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = int((time.time() - start_time) * 1000)

            return ModelResponse(
                content=data['choices'][0]['message']['content'],
                model=model,
                latency_ms=latency_ms,
                finish_reason=data['choices'][0].get('finish_reason'),
                usage=data.get('usage', {})
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - extract retry-after if available
                retry_after = int(e.response.headers.get('Retry-After', 60))
                await asyncio.sleep(retry_after)
                raise  # Will be retried
            raise

class RateLimiter:
    """Token bucket rate limiter per model."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self._tokens = defaultdict(lambda: requests_per_minute)
        self._last_refill = defaultdict(lambda: time.time())
        self._lock = asyncio.Lock()

    async def acquire(self, model: str):
        """Acquire a rate limit token for a model."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_refill[model]
            refill = elapsed * (self.rpm / 60)
            self._tokens[model] = min(self.rpm, self._tokens[model] + refill)
            self._last_refill[model] = now

            if self._tokens[model] < 1:
                wait_time = (1 - self._tokens[model]) * (60 / self.rpm)
                await asyncio.sleep(wait_time)
                self._tokens[model] = 1

            self._tokens[model] -= 1
```

### 7.3 Graceful Shutdown Handler

```python
# src/core/shutdown.py

class GracefulShutdown:
    """Handles graceful shutdown on SIGINT/SIGTERM."""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint = checkpoint_manager
        self.shutdown_requested = False
        self._setup_handlers()

    def _setup_handlers(self):
        """Register signal handlers."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal."""
        if self.shutdown_requested:
            # Second signal - force exit
            sys.exit(1)

        self.shutdown_requested = True
        logger.info("Shutdown requested. Saving checkpoint...")
        self.checkpoint.save()
        logger.info("Checkpoint saved. Exiting gracefully.")
        sys.exit(0)

    def check_shutdown(self):
        """Check if shutdown was requested (for cooperative checking)."""
        return self.shutdown_requested
```

---

## Part 8: Report Generation

### 8.1 PDF Report Generator

```python
# src/reports/pdf_generator.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import plotly.express as px
import plotly.graph_objects as go

class PDFReportGenerator:
    """Generates comprehensive PDF analysis reports."""

    def __init__(self, results_store: ResultsStore, run_dir: Path):
        self.results = results_store
        self.run_dir = run_dir
        self.charts_dir = run_dir / "reports" / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)

    async def generate_full_report(self) -> Path:
        """Generate the complete evaluation report."""

        # Generate all charts first
        await self._generate_all_charts()

        # Build PDF document
        report_path = self.run_dir / "reports" / "report.pdf"
        doc = SimpleDocTemplate(str(report_path), pagesize=letter)

        story = []

        # Title page
        story.extend(self._build_title_page())

        # Executive summary
        story.extend(await self._build_executive_summary())

        # Methodology overview
        story.extend(self._build_methodology_section())

        # Overall results
        story.extend(await self._build_overall_results())

        # Breakdown by model pair
        story.extend(await self._build_model_pair_breakdowns())

        # Breakdown by dimension
        story.extend(await self._build_dimension_breakdowns())

        # Weakness analysis
        story.extend(await self._build_weakness_analysis())

        # Statistical appendix
        story.extend(await self._build_statistical_appendix())

        # Build the PDF
        doc.build(story)
        return report_path

    async def _build_executive_summary(self) -> List:
        """Build the executive summary section."""
        elements = []

        # Get high-level stats
        stats = await self._get_summary_stats()

        summary_text = f"""
        **Evaluation Overview**

        This evaluation compared Gemini 3.0 models against {stats['num_competitors']} competitor models
        across {stats['total_prompts']} diverse professional writing tasks derived from
        {stats['num_occupations']} O*NET occupations.

        **Key Findings**

        1. **Overall Win Rate**: Gemini achieved an overall win rate of {stats['overall_win_rate']:.1f}%
           (95% CI: {stats['win_rate_ci_low']:.1f}% - {stats['win_rate_ci_high']:.1f}%)

        2. **Strongest Performance**: {stats['strongest_area']}

        3. **Areas for Improvement**: {stats['weakest_area']}

        4. **Judge Agreement**: Inter-judge agreement was {stats['agreement']:.2f} (Fleiss' Kappa),
           indicating {self._interpret_kappa(stats['agreement'])} agreement.
        """

        elements.append(Paragraph(summary_text, self.styles['Normal']))
        elements.append(Image(str(self.charts_dir / "overall_win_rates.png"), width=400, height=250))

        return elements

    async def _build_weakness_analysis(self) -> List:
        """Build detailed weakness analysis section."""
        elements = []

        elements.append(Paragraph("Weakness Analysis", self.styles['Heading1']))

        # Query for areas where Gemini underperforms
        weaknesses = await self._identify_weaknesses()

        for weakness in weaknesses:
            elements.append(Paragraph(
                f"**{weakness['dimension']}**: {weakness['description']}",
                self.styles['Normal']
            ))
            elements.append(Paragraph(
                f"Win rate: {weakness['win_rate']:.1f}% vs {weakness['baseline']:.1f}% overall "
                f"(p={weakness['p_value']:.4f})",
                self.styles['Normal']
            ))
            if weakness.get('examples'):
                elements.append(Paragraph("Example tasks:", self.styles['Normal']))
                for example in weakness['examples'][:3]:
                    elements.append(Paragraph(f"- {example}", self.styles['Normal']))
            elements.append(Spacer(1, 12))

        return elements

    async def _identify_weaknesses(self) -> List[Dict]:
        """Identify specific areas where Gemini underperforms."""
        weaknesses = []

        # Check by writing category
        async with aiosqlite.connect(self.results.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    p.writing_category,
                    COUNT(*) as total,
                    SUM(CASE WHEN cr.final_winner = 'gemini' THEN 1 ELSE 0 END) as wins
                FROM comparison_results cr
                JOIN prompts p ON cr.prompt_id = p.prompt_id
                GROUP BY p.writing_category
                HAVING total >= 20
            """)
            rows = await cursor.fetchall()

        overall_rate = await self._get_overall_win_rate()

        for category, total, wins in rows:
            rate = wins / total * 100
            if rate < overall_rate - 5:  # More than 5% below average
                # Significance test
                p_value = stats.binom_test(wins, total, overall_rate/100, alternative='less')
                if p_value < 0.1:  # Marginally significant
                    weaknesses.append({
                        'dimension': f'Writing Category: {category}',
                        'description': f'Gemini underperforms on {category} tasks',
                        'win_rate': rate,
                        'baseline': overall_rate,
                        'p_value': p_value,
                        'n': total
                    })

        # Check by formality level
        # Check by generation
        # Check by occupation group
        # ... similar queries

        return sorted(weaknesses, key=lambda x: x['win_rate'])
```

### 8.2 Visualization Generator

```python
# src/reports/visualizations.py

class VisualizationGenerator:
    """Generates charts and visualizations for analysis."""

    def __init__(self, results_store: ResultsStore, output_dir: Path):
        self.results = results_store
        self.output_dir = output_dir

    async def generate_all_charts(self):
        """Generate all standard charts."""
        await asyncio.gather(
            self.generate_overall_win_rates(),
            self.generate_win_rate_by_occupation_heatmap(),
            self.generate_win_rate_by_formality(),
            self.generate_win_rate_by_generation(),
            self.generate_judge_agreement_chart(),
            self.generate_response_length_comparison(),
            self.generate_confidence_interval_forest_plot()
        )

    async def generate_overall_win_rates(self):
        """Generate bar chart of win rates per model pair."""
        data = await self._get_win_rates_by_pair()

        fig = go.Figure()
        for pair in data:
            fig.add_trace(go.Bar(
                name=pair['competitor'],
                x=['Gemini Wins', 'Competitor Wins', 'Ties'],
                y=[pair['gemini_wins'], pair['competitor_wins'], pair['ties']],
                text=[f"{pair['gemini_rate']:.1f}%", f"{pair['competitor_rate']:.1f}%", f"{pair['tie_rate']:.1f}%"],
                textposition='auto'
            ))

        fig.update_layout(
            title='Win Rates by Model Pair',
            barmode='group',
            xaxis_title='Outcome',
            yaxis_title='Count'
        )

        fig.write_image(str(self.output_dir / "overall_win_rates.png"))

    async def generate_win_rate_by_occupation_heatmap(self):
        """Generate heatmap of win rates across occupation groups."""
        data = await self._get_win_rates_by_occupation()

        # Pivot for heatmap
        df = pd.DataFrame(data)
        pivot = df.pivot(index='soc_major_group', columns='competitor', values='win_rate')

        fig = px.imshow(
            pivot,
            labels=dict(x="Competitor Model", y="SOC Major Group", color="Gemini Win Rate %"),
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=50
        )

        fig.update_layout(title='Gemini Win Rate by Occupation Group')
        fig.write_image(str(self.output_dir / "occupation_heatmap.png"))

    async def generate_confidence_interval_forest_plot(self):
        """Generate forest plot showing win rates with confidence intervals."""
        data = await self._get_win_rates_with_ci()

        fig = go.Figure()

        for i, pair in enumerate(data):
            fig.add_trace(go.Scatter(
                x=[pair['win_rate']],
                y=[i],
                mode='markers',
                marker=dict(size=10, color='blue'),
                error_x=dict(
                    type='data',
                    symmetric=False,
                    array=[pair['ci_high'] - pair['win_rate']],
                    arrayminus=[pair['win_rate'] - pair['ci_low']]
                ),
                name=pair['competitor']
            ))

        # Add reference line at 50%
        fig.add_vline(x=50, line_dash="dash", line_color="gray")

        fig.update_layout(
            title='Win Rates with 95% Confidence Intervals',
            xaxis_title='Gemini Win Rate (%)',
            yaxis=dict(
                tickvals=list(range(len(data))),
                ticktext=[d['competitor'] for d in data]
            )
        )

        fig.write_image(str(self.output_dir / "forest_plot.png"))
```

---

## Part 9: CLI Interface and Presets

### 9.1 Main CLI Entry Point

```python
# src/cli/main.py

import typer
from typing import Optional, List

app = typer.Typer(
    name="gemini-eval",
    help="Gemini Writing Evaluation Framework"
)

@app.command()
def run(
    preset: Optional[int] = typer.Option(None, "--preset", "-p", help="Preset level 1-10"),
    prompts: Optional[int] = typer.Option(None, "--prompts", "-n", help="Number of prompts"),
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma-separated model list"),
    judges: Optional[str] = typer.Option(None, "--judges", "-j", help="Comma-separated judge models"),
    votes: Optional[int] = typer.Option(5, "--votes", "-v", help="Votes per judge (1-5)"),
    occupations: Optional[str] = typer.Option(None, "--occupations", help="Filter by SOC codes"),
    industries: Optional[str] = typer.Option(None, "--industries", help="Filter by NAICS codes"),
    job_zones: Optional[str] = typer.Option(None, "--job-zones", help="Filter by job zone (1-5)"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory")
):
    """Run an evaluation."""

    # Build configuration
    config = build_config(
        preset=preset,
        prompts=prompts,
        models=models,
        judges=judges,
        votes=votes,
        occupations=occupations,
        industries=industries,
        job_zones=job_zones,
        seed=seed,
        output_dir=output_dir
    )

    # Show cost estimate
    estimate = CostEstimator().estimate(config)
    display_estimate(estimate)

    if dry_run:
        return

    # Confirm before proceeding
    if not typer.confirm(f"Proceed with evaluation? (Est. cost: ${estimate.total_cost:.2f})"):
        raise typer.Abort()

    # Run evaluation
    asyncio.run(run_evaluation(config))

@app.command()
def resume(
    run_dir: str = typer.Argument(..., help="Path to run directory to resume")
):
    """Resume an interrupted evaluation."""
    asyncio.run(resume_evaluation(Path(run_dir)))

@app.command()
def view(
    run_dir: str = typer.Argument(..., help="Path to run directory to view")
):
    """Launch interactive results viewer."""
    from src.tui.results_viewer import ResultsViewerApp
    app = ResultsViewerApp(Path(run_dir))
    app.run()

@app.command()
def report(
    run_dir: str = typer.Argument(..., help="Path to run directory"),
    format: str = typer.Option("pdf", "--format", "-f", help="Output format (pdf, html, csv)")
):
    """Generate analysis report from completed run."""
    asyncio.run(generate_report(Path(run_dir), format))

@app.command()
def compare(
    run_dirs: List[str] = typer.Argument(..., help="Run directories to compare")
):
    """Compare results across multiple evaluation runs."""
    asyncio.run(compare_runs([Path(d) for d in run_dirs]))

@app.command()
def presets():
    """Show available evaluation presets."""
    display_presets_table()
```

### 9.2 Preset Configurations

```python
# src/config/presets.py

PRESETS = {
    1: PresetConfig(
        name="Sanity Check",
        prompts=5,
        model_pairs=1,
        judges=1,
        votes_per_judge=1,
        personas=['writing_expert'],
        est_cost_low=0.50,
        est_cost_high=1.50,
        est_time_minutes=2,
        use_case="Does the system work?"
    ),
    2: PresetConfig(
        name="Smoke Test",
        prompts=20,
        model_pairs=1,
        judges=1,
        votes_per_judge=3,
        personas=['writing_expert'],
        est_cost_low=3,
        est_cost_high=8,
        est_time_minutes=5,
        use_case="Quick functionality test"
    ),
    3: PresetConfig(
        name="Dev Iteration",
        prompts=50,
        model_pairs=2,
        judges=2,
        votes_per_judge=3,
        personas=['writing_expert', 'recipient'],
        est_cost_low=20,
        est_cost_high=35,
        est_time_minutes=15,
        use_case="Development/debugging"
    ),
    4: PresetConfig(
        name="Quick Sample",
        prompts=100,
        model_pairs=2,
        judges=2,
        votes_per_judge=5,
        personas=['writing_expert', 'recipient'],
        est_cost_low=60,
        est_cost_high=90,
        est_time_minutes=30,
        use_case="Fast directional signal"
    ),
    5: PresetConfig(
        name="Light Eval",
        prompts=200,
        model_pairs=3,
        judges=3,
        votes_per_judge=3,
        personas=['writing_expert', 'recipient'],
        est_cost_low=120,
        est_cost_high=180,
        est_time_minutes=60,
        use_case="Light but meaningful eval"
    ),
    6: PresetConfig(
        name="Standard Eval",
        prompts=500,
        model_pairs=4,
        judges=3,
        votes_per_judge=5,
        personas=['writing_expert', 'recipient'],
        est_cost_low=400,
        est_cost_high=600,
        est_time_minutes=180,
        use_case="Standard evaluation run"
    ),
    7: PresetConfig(
        name="Thorough Eval",
        prompts=1000,
        model_pairs=4,
        judges=3,
        votes_per_judge=5,
        personas=['writing_expert', 'recipient'],
        est_cost_low=800,
        est_cost_high=1200,
        est_time_minutes=360,
        use_case="Thorough with good power"
    ),
    8: PresetConfig(
        name="Comprehensive",
        prompts=2000,
        model_pairs='all',
        judges=3,
        votes_per_judge=5,
        personas=['writing_expert', 'recipient'],
        est_cost_low=2000,
        est_cost_high=3000,
        est_time_minutes=720,
        use_case="High statistical power"
    ),
    9: PresetConfig(
        name="Deep Dive",
        prompts=5000,
        model_pairs='all',
        judges=3,
        votes_per_judge=5,
        personas=['writing_expert', 'recipient'],
        est_cost_low=5000,
        est_cost_high=7000,
        est_time_minutes=1440,
        use_case="Publication-grade"
    ),
    10: PresetConfig(
        name="Full Kaboodle",
        prompts=10000,
        model_pairs='all',
        judges=3,
        votes_per_judge=5,
        personas=['writing_expert', 'recipient'],
        est_cost_low=10000,
        est_cost_high=15000,
        est_time_minutes=2880,
        use_case="Maximum coverage"
    )
}
```

### 9.3 Cost Estimator

```python
# src/config/cost_estimator.py

class CostEstimator:
    """Estimates API costs for evaluation runs."""

    # OpenRouter pricing (per 1M tokens) - example values
    MODEL_PRICING = {
        'google/gemini-3.0-pro': {'input': 1.25, 'output': 5.00},
        'google/gemini-3.0-flash': {'input': 0.075, 'output': 0.30},
        'openai/gpt-5.2': {'input': 2.50, 'output': 10.00},
        'openai/gpt-4.1': {'input': 0.15, 'output': 0.60},
        'anthropic/claude-opus-4.5': {'input': 3.00, 'output': 15.00},
        'anthropic/claude-sonnet': {'input': 0.80, 'output': 4.00},
    }

    # Average token counts (empirical estimates)
    AVG_PROMPT_TOKENS = 800
    AVG_RESPONSE_TOKENS = 400
    AVG_JUDGE_INPUT_TOKENS = 1500  # Includes both responses + context
    AVG_JUDGE_OUTPUT_TOKENS = 150

    def estimate(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost for an evaluation run."""

        # Response generation costs
        response_cost = 0
        for model in config.models:
            pricing = self.MODEL_PRICING.get(model, {'input': 2.0, 'output': 8.0})
            input_cost = (config.num_prompts * self.AVG_PROMPT_TOKENS / 1_000_000) * pricing['input']
            output_cost = (config.num_prompts * self.AVG_RESPONSE_TOKENS / 1_000_000) * pricing['output']
            response_cost += input_cost + output_cost

        # Judging costs
        num_comparisons = config.num_prompts * len(config.model_pairs)
        num_judge_calls = (
            num_comparisons *
            len(config.judges) *
            config.votes_per_judge *
            len(config.personas)
        )

        judge_cost = 0
        for judge in config.judges:
            pricing = self.MODEL_PRICING.get(judge, {'input': 2.0, 'output': 8.0})
            calls_per_judge = num_judge_calls / len(config.judges)
            input_cost = (calls_per_judge * self.AVG_JUDGE_INPUT_TOKENS / 1_000_000) * pricing['input']
            output_cost = (calls_per_judge * self.AVG_JUDGE_OUTPUT_TOKENS / 1_000_000) * pricing['output']
            judge_cost += input_cost + output_cost

        # Add 15% buffer for retries and variance
        total_low = (response_cost + judge_cost) * 0.9
        total_high = (response_cost + judge_cost) * 1.15

        # Time estimate
        api_calls = config.num_prompts * len(config.models) + num_judge_calls
        time_estimate_minutes = api_calls * 0.5 / 60  # Assume 0.5s per call average

        return CostEstimate(
            response_cost=response_cost,
            judge_cost=judge_cost,
            total_low=total_low,
            total_high=total_high,
            num_api_calls=api_calls,
            time_estimate_minutes=time_estimate_minutes
        )
```

---

## Part 10: Directory Structure and File Organization

### 10.1 Complete Project Structure

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── PROMPT.md
│
├── src/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py                    # CLI entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── model_pairs.py             # Model pairing configuration
│   │   ├── presets.py                 # Evaluation presets
│   │   ├── cost_estimator.py          # Cost estimation
│   │   └── settings.py                # Global settings
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── checkpoint.py              # Checkpoint management
│   │   ├── shutdown.py                # Graceful shutdown
│   │   └── orchestrator.py            # Main evaluation coordinator
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── schema.sql                 # SQLite schema
│   │   ├── onet_extractor.py          # O*NET data extraction
│   │   ├── naics_mapper.py            # NAICS industry mapping
│   │   ├── company_database.py        # Real company data
│   │   ├── name_generator.py          # Realistic name generation
│   │   └── results_store.py           # Results persistence
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── phase1_persona_generator.py
│   │   ├── phase2_combiner.py
│   │   ├── phase3_enricher.py
│   │   └── templates.py               # Prompt templates
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── judge_engine.py            # Judging implementation
│   │   ├── aggregation.py             # Vote aggregation
│   │   ├── ordering.py                # Position bias mitigation
│   │   ├── judge_prompts.py           # Judge prompt templates
│   │   └── failure_handler.py         # Failure categorization
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py              # Statistical computations
│   │   └── bias_detection.py          # Bias detection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── openrouter_client.py       # OpenRouter API client
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── progress_app.py            # Progress visualization
│   │   └── results_viewer.py          # Results viewer
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py           # PDF report generation
│   │   └── visualizations.py          # Chart generation
│   │
│   └── schemas/
│       ├── __init__.py
│       └── prompt_schema.py           # Pydantic schemas
│
├── db/
│   ├── onet.db                        # O*NET database
│   └── ONET_WRITING_REFERENCE.md      # O*NET reference docs
│
├── data/
│   ├── companies/                     # Company data files
│   ├── names/                         # Name databases
│   └── bls_occ_industry_matrix.csv    # BLS crosswalk
│
├── results/                           # Evaluation run outputs
│   └── eval_YYYY-MM-DD_HH-MM-SS/
│       ├── config.json
│       ├── checkpoint.json
│       ├── prompts/
│       ├── responses/
│       ├── judgments/
│       ├── results.db
│       ├── analysis/
│       ├── reports/
│       └── logs/
│
├── tests/
│   ├── __init__.py
│   ├── test_onet_extractor.py
│   ├── test_prompt_generation.py
│   ├── test_judge_engine.py
│   ├── test_aggregation.py
│   └── test_statistics.py
│
└── plans/                             # Planning artifacts
    └── draft_plan_2.md
```

### 10.2 Dependencies (pyproject.toml)

```toml
[project]
name = "gemini-writing-eval"
version = "1.0.0"
description = "Gemini Writing Evaluation Framework"
requires-python = ">=3.11"

dependencies = [
    # Core
    "pydantic>=2.0",
    "httpx>=0.25",
    "aiosqlite>=0.19",
    "tenacity>=8.2",  # Retry logic

    # CLI
    "typer>=0.9",
    "rich>=13.0",

    # TUI
    "textual>=0.40",

    # Data Analysis
    "pandas>=2.0",
    "numpy>=1.24",
    "scipy>=1.11",

    # Visualization
    "plotly>=5.18",
    "matplotlib>=3.8",

    # PDF Generation
    "reportlab>=4.0",
    "weasyprint>=60.0",

    # Testing
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
]

[project.scripts]
gemini-eval = "src.cli.main:app"
```

---

## Part 11: Implementation Phases

### Phase 1: Foundation (Week 1)
1. Set up project structure and dependencies
2. Implement O*NET data extraction
3. Implement NAICS mapping
4. Create company and name databases
5. Build basic prompt schema

### Phase 2: Prompt Generation (Week 2)
1. Implement Phase 1 persona generation
2. Implement Phase 2 algorithmic combination
3. Implement Phase 3 LLM enrichment
4. Build prompt validation and quality checks

### Phase 3: Core Evaluation (Week 3)
1. Implement OpenRouter client with retries
2. Build response generation pipeline
3. Implement judge engine with dual personas
4. Implement majority-of-majorities aggregation
5. Add position bias mitigation

### Phase 4: Robustness (Week 4)
1. Implement checkpoint system
2. Add graceful shutdown handling
3. Build failure categorization
4. Add comprehensive logging
5. Implement resumability

### Phase 5: TUI and UX (Week 5)
1. Build progress dashboard
2. Build results viewer
3. Implement cost estimation display
4. Add interactive controls

### Phase 6: Analysis and Reporting (Week 6)
1. Implement statistical analysis
2. Build bias detection
3. Create visualization generator
4. Implement PDF report generation
5. Build executive summary module

### Phase 7: Testing and Polish (Week 7)
1. Write comprehensive tests
2. Run end-to-end validation
3. Performance optimization
4. Documentation
5. Final bug fixes

---

## Conclusion

This implementation plan provides a comprehensive, technically detailed blueprint for the Gemini Writing Evaluation Framework. Key strengths of this design include:

1. **Realistic Prompts**: Three-phase generation ensures diverse, realistic writing tasks grounded in actual US workforce data
2. **Robust Judging**: Multi-model ensemble with dual personas and majority-of-majorities aggregation
3. **Statistical Rigor**: Confidence intervals, significance testing, bias detection, and inter-rater reliability metrics
4. **Operational Excellence**: Full resumability, graceful shutdown, cost estimation, and rich progress visualization
5. **Actionable Insights**: Detailed weakness analysis and comprehensive PDF reporting

The system is designed to produce trustworthy, reproducible evaluations suitable for frontier AI lab researchers while maintaining practical usability and cost awareness.

