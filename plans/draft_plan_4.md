# Gemini Writing Evaluation Framework - Implementation Plan

## Executive Overview

This document presents a comprehensive implementation plan for the Gemini Writing Evaluation Framework - a system designed to rigorously compare Gemini 3.0 Pro and Flash against competing frontier LLMs (GPT-5.2, Claude Opus 4.5, Grok-4.1, Kimi K2, etc.) on realistic professional writing tasks derived from the US economy.

The framework leverages the O*NET 30.1 database (18,796 task statements across 1,016 occupations) to generate writing prompts that span every job in the US economy, ensuring evaluations reflect real-world writing needs rather than synthetic benchmarks.

---

## Part 1: System Architecture

### 1.1 High-Level Architecture

```
+------------------------------------------------------------------+
|                    GEMINI WRITING EVAL FRAMEWORK                   |
+------------------------------------------------------------------+
|                                                                    |
|  +-----------------+      +------------------+      +------------+ |
|  |   Data Layer    |----->|  Prompt Engine   |----->|  Eval Core | |
|  |  (O*NET + NAICS)|      | (3-Phase Gen)    |      |  (SxS)     | |
|  +-----------------+      +------------------+      +------------+ |
|          |                        |                      |         |
|          v                        v                      v         |
|  +-----------------+      +------------------+      +------------+ |
|  | Company/Name DB |      | Persona Generator|      | Judge Panel| |
|  | (Real entities) |      | (Diversity dims) |      | (Ensemble) | |
|  +-----------------+      +------------------+      +------------+ |
|                                                          |         |
|                                                          v         |
|  +-----------------+      +------------------+      +------------+ |
|  |   Results DB    |<-----|  Analysis Engine |<-----|  Vote Agg  | |
|  |   (SQLite)      |      |  (Stats/Charts)  |      | (Maj-of-M) | |
|  +-----------------+      +------------------+      +------------+ |
|          |                                                         |
|          v                                                         |
|  +-----------------+      +------------------+                     |
|  |   TUI Viewer    |      |   PDF Reporter   |                     |
|  |   (Textual)     |      |  (Final Report)  |                     |
|  +-----------------+      +------------------+                     |
|                                                                    |
+------------------------------------------------------------------+
```

### 1.2 Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Data Layer** | SQLite + Python sqlite3 | O*NET access, results storage |
| **Prompt Engine** | Python + Pydantic | Three-phase prompt generation |
| **Eval Core** | asyncio + httpx | Parallel model API calls via OpenRouter |
| **Judge Panel** | OpenRouter API | Ensemble judging with multiple LLMs |
| **Vote Aggregator** | Pure Python | Majority-of-majorities logic |
| **Analysis Engine** | pandas + scipy + plotly | Statistical analysis and visualization |
| **TUI Viewer** | Textual (rich) | Interactive results exploration |
| **PDF Reporter** | WeasyPrint or ReportLab | Final analyst report generation |
| **Progress Dashboard** | Textual (rich) | Live evaluation monitoring |

### 1.3 Directory Structure

```
gemini-writing-eval/
├── pyproject.toml                    # Project configuration
├── README.md                         # Setup and usage instructions
├── config/
│   ├── presets.yaml                  # 10 preset configurations
│   ├── models.yaml                   # Model definitions and pricing
│   └── judge_prompts.yaml            # Judge persona templates
├── src/
│   ├── __init__.py
│   ├── cli.py                        # Main CLI entry point
│   ├── config.py                     # Configuration management
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_loader.py            # O*NET database interface
│   │   ├── naics_mapper.py           # NAICS industry mapping
│   │   ├── company_db.py             # Real company database
│   │   └── name_generator.py         # Realistic name generation
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py              # Main prompt generation orchestrator
│   │   ├── phase1_llm.py             # Phase 1: LLM persona variations
│   │   ├── phase2_algorithmic.py     # Phase 2: Deterministic combinations
│   │   ├── phase3_enrichment.py      # Phase 3: LLM context enrichment
│   │   └── schemas.py                # Pydantic models for prompts
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── runner.py                 # Main evaluation orchestrator
│   │   ├── api_client.py             # OpenRouter API wrapper
│   │   ├── judge.py                  # Judge implementation
│   │   ├── vote_aggregator.py        # Majority-of-majorities
│   │   └── checkpoint.py             # Checkpoint/resume system
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py             # Statistical tests
│   │   ├── bias_detection.py         # Systematic bias analysis
│   │   ├── visualizations.py         # Chart generation
│   │   └── weakness_finder.py        # Weakness identification
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py          # PDF report creation
│   │   └── templates/                # Report templates
│   └── tui/
│       ├── __init__.py
│       ├── app.py                    # Main TUI application
│       ├── progress.py               # Progress dashboard
│       └── viewer.py                 # Results viewer
├── db/
│   ├── onet.db                       # O*NET 30.1 database
│   └── companies.db                  # Company database
├── results/                          # Evaluation run outputs
└── tests/
    ├── test_prompts.py
    ├── test_eval.py
    └── test_analysis.py
```

---

## Part 2: Data Pipeline

### 2.1 O*NET Data Extraction

The O*NET 30.1 database serves as the foundation for writing task identification. The system extracts tasks using a comprehensive approach.

#### 2.1.1 Task Extraction Strategy

```python
# src/data/onet_loader.py

from dataclasses import dataclass
from enum import Enum
import sqlite3
from typing import Iterator

class WritingCategory(Enum):
    EXPLICIT_WRITING = "explicit_writing"           # ~2,500 tasks
    CORRESPONDENCE = "correspondence"               # ~1,500 tasks
    REPORTS_ANALYSIS = "reports_analysis"           # ~3,000 tasks
    PERSUASION_NEGOTIATION = "persuasion"          # ~1,200 tasks
    POLICY_PROCEDURE = "policy_procedure"           # ~800 tasks
    CUSTOMER_COMMUNICATION = "customer_comm"        # ~2,000 tasks
    INSTRUCTIONAL = "instructional"                 # ~1,000 tasks
    INTERNAL_COORDINATION = "internal_coord"        # ~2,500 tasks
    CONTRACTS_LEGAL = "contracts_legal"             # ~600 tasks
    FEEDBACK_EVALUATION = "feedback_eval"           # ~1,500 tasks

@dataclass
class OnetTask:
    task_id: str
    onetsoc_code: str
    occupation_title: str
    occupation_description: str
    task: str
    task_type: str  # Core, Supplemental, or NULL
    job_zone: int   # 1-5 skill level
    soc_major_group: str
    writing_category: WritingCategory
    writing_skill_importance: float  # 1-5 scale
    email_frequency: float           # 1-5 scale
    correspondence_frequency: float  # 1-5 scale

class OnetLoader:
    """Interface to O*NET 30.1 database for writing task extraction."""

    WRITING_PATTERNS = {
        WritingCategory.EXPLICIT_WRITING: [
            '%write%', '%draft%', '%document%', '%compose%', '%author%'
        ],
        WritingCategory.CORRESPONDENCE: [
            '%correspond%', '%email%', '%letter%', '%memo%', '%notify%'
        ],
        WritingCategory.REPORTS_ANALYSIS: [
            '%report%', '%present%finding%', '%summarize%', '%prepare%presentation%'
        ],
        WritingCategory.PERSUASION_NEGOTIATION: [
            '%negotiat%', '%propos%', '%persuad%', '%recommend%'
        ],
        WritingCategory.POLICY_PROCEDURE: [
            '%develop%polic%', '%implement%polic%', '%write%procedure%'
        ],
        WritingCategory.CUSTOMER_COMMUNICATION: [
            '%customer%question%', '%client%question%', '%resolve%complaint%'
        ],
        WritingCategory.INSTRUCTIONAL: [
            '%train%staff%', '%instruct%', '%develop%curriculum%', '%prepare%manual%'
        ],
        WritingCategory.INTERNAL_COORDINATION: [
            '%confer with%', '%coordinate with%', '%collaborate with%', '%meet with%'
        ],
        WritingCategory.CONTRACTS_LEGAL: [
            '%prepare%contract%', '%draft%contract%', '%write%agreement%'
        ],
        WritingCategory.FEEDBACK_EVALUATION: [
            '%evaluate%performance%', '%provide%feedback%', '%assess%and%report%'
        ]
    }

    def __init__(self, db_path: str = "db/onet.db"):
        self.db_path = db_path

    def extract_writing_tasks(self) -> Iterator[OnetTask]:
        """Extract all writing-relevant tasks with full context."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Build comprehensive query joining all relevant tables
            query = """
            SELECT
                t.task_id,
                t.onetsoc_code,
                o.title as occupation_title,
                o.description as occupation_description,
                t.task,
                t.task_type,
                COALESCE(jz.job_zone, 3) as job_zone,
                SUBSTR(t.onetsoc_code, 1, 2) as soc_major_group,
                COALESCE(ws.data_value, 3.0) as writing_skill,
                COALESCE(ef.data_value, 3.0) as email_freq,
                COALESCE(cf.data_value, 3.0) as corresp_freq
            FROM task_statements t
            JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
            LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
            LEFT JOIN skills ws ON t.onetsoc_code = ws.onetsoc_code
                AND ws.element_id = '2.A.1.c' AND ws.scale_id = 'IM'
            LEFT JOIN work_context ef ON t.onetsoc_code = ef.onetsoc_code
                AND ef.element_id = '4.C.1.a.2.h' AND ef.scale_id = 'CX'
            LEFT JOIN work_context cf ON t.onetsoc_code = cf.onetsoc_code
                AND cf.element_id = '4.C.1.a.2.j' AND cf.scale_id = 'CX'
            """

            for row in conn.execute(query):
                category = self._classify_task(row['task'])
                if category:
                    yield OnetTask(
                        task_id=row['task_id'],
                        onetsoc_code=row['onetsoc_code'],
                        occupation_title=row['occupation_title'],
                        occupation_description=row['occupation_description'],
                        task=row['task'],
                        task_type=row['task_type'] or 'Unspecified',
                        job_zone=row['job_zone'],
                        soc_major_group=row['soc_major_group'],
                        writing_category=category,
                        writing_skill_importance=row['writing_skill'],
                        email_frequency=row['email_freq'],
                        correspondence_frequency=row['corresp_freq']
                    )

    def _classify_task(self, task_text: str) -> WritingCategory | None:
        """Classify a task into a writing category based on patterns."""
        task_lower = task_text.lower()
        for category, patterns in self.WRITING_PATTERNS.items():
            for pattern in patterns:
                if self._match_pattern(task_lower, pattern.replace('%', '')):
                    return category
        return None

    def _match_pattern(self, text: str, pattern: str) -> bool:
        """Check if pattern exists in text."""
        return pattern in text
```

### 2.2 NAICS Industry Mapping

Since O*NET does not directly contain NAICS codes, we implement a mapping layer.

```python
# src/data/naics_mapper.py

from dataclasses import dataclass
from typing import Dict, List
import json

@dataclass
class NAICSIndustry:
    code: str
    title: str
    sector: str
    typical_companies: List[str]  # Pre-populated examples

class NAICSMapper:
    """Maps occupations to NAICS industries for diversity sampling."""

    # SOC Major Group to likely NAICS sectors mapping
    SOC_TO_NAICS_MAPPING = {
        '11': ['52', '54', '55', '62', '71', '72'],  # Management -> Finance, Professional, HQ, Healthcare, Arts, Hospitality
        '13': ['52', '54', '55'],                     # Business/Financial -> Finance, Professional, HQ
        '15': ['51', '54'],                           # Computer -> Information, Professional
        '17': ['23', '31-33', '54'],                  # Engineering -> Construction, Manufacturing, Professional
        '19': ['54', '61', '62'],                     # Science -> Professional, Education, Healthcare
        '21': ['62', '92', '81'],                     # Community/Social -> Healthcare, Government, Other Services
        '23': ['54'],                                 # Legal -> Professional Services
        '25': ['61'],                                 # Education -> Educational Services
        '27': ['51', '71'],                           # Arts/Media -> Information, Arts/Entertainment
        '29': ['62'],                                 # Healthcare Practitioners -> Healthcare
        '31': ['62'],                                 # Healthcare Support -> Healthcare
        '33': ['92'],                                 # Protective Service -> Government
        '35': ['72'],                                 # Food -> Accommodation/Food
        '37': ['56', '81'],                           # Cleaning -> Admin Support, Other Services
        '39': ['81', '62', '71'],                     # Personal Care -> Other Services, Healthcare, Arts
        '41': ['44-45', '52', '53'],                  # Sales -> Retail, Finance, Real Estate
        '43': ['52', '54', '55', '56'],               # Office/Admin -> Finance, Professional, HQ, Admin
        '45': ['11'],                                 # Farming -> Agriculture
        '47': ['23'],                                 # Construction -> Construction
        '49': ['23', '31-33', '48-49'],               # Maintenance -> Construction, Manufacturing, Transport
        '51': ['31-33'],                              # Production -> Manufacturing
        '53': ['48-49', '44-45'],                     # Transportation -> Transport, Retail
    }

    # NAICS sector definitions
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
        '92': 'Public Administration',
    }

    def get_industries_for_occupation(self, soc_major_group: str) -> List[NAICSIndustry]:
        """Get relevant NAICS industries for a SOC major group."""
        naics_codes = self.SOC_TO_NAICS_MAPPING.get(soc_major_group, ['54'])
        return [
            NAICSIndustry(
                code=code,
                title=self.NAICS_SECTORS.get(code, 'Unknown'),
                sector=code,
                typical_companies=self._get_typical_companies(code)
            )
            for code in naics_codes
        ]

    def _get_typical_companies(self, naics_code: str) -> List[str]:
        """Get example companies for an industry."""
        # This would be populated from company_db
        return []
```

### 2.3 Company Database

Real company names ground prompts in reality.

```python
# src/data/company_db.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import random

class CompanySize(Enum):
    STARTUP = "startup"           # <50 employees
    SMALL = "small"               # 50-200 employees
    MIDMARKET = "midmarket"       # 200-2000 employees
    ENTERPRISE = "enterprise"     # 2000-10000 employees
    FORTUNE_500 = "fortune_500"   # 10000+ employees

@dataclass
class Company:
    name: str
    size: CompanySize
    industry_naics: str
    founded_year: Optional[int]
    hq_location: str
    public: bool
    employee_count_approx: int
    description: str

class CompanyDatabase:
    """Database of real companies for prompt grounding."""

    # Curated list of companies by industry and size
    # In production, this would be loaded from companies.db
    COMPANIES = {
        '52': {  # Finance
            CompanySize.FORTUNE_500: [
                Company("JPMorgan Chase", CompanySize.FORTUNE_500, "52", 1799, "New York, NY", True, 290000, "Global financial services"),
                Company("Bank of America", CompanySize.FORTUNE_500, "52", 1784, "Charlotte, NC", True, 212000, "Multinational bank"),
                Company("Goldman Sachs", CompanySize.FORTUNE_500, "52", 1869, "New York, NY", True, 49000, "Investment banking"),
            ],
            CompanySize.ENTERPRISE: [
                Company("Ally Financial", CompanySize.ENTERPRISE, "52", 1919, "Detroit, MI", True, 11000, "Digital financial services"),
                Company("Synchrony Financial", CompanySize.ENTERPRISE, "52", 2014, "Stamford, CT", True, 20000, "Consumer financial services"),
            ],
            CompanySize.MIDMARKET: [
                Company("Greenlight Financial", CompanySize.MIDMARKET, "52", 2014, "Atlanta, GA", False, 400, "Family fintech"),
            ],
            CompanySize.STARTUP: [
                Company("Ramp", CompanySize.STARTUP, "52", 2019, "New York, NY", False, 350, "Corporate card platform"),
            ],
        },
        '54': {  # Professional Services
            CompanySize.FORTUNE_500: [
                Company("Deloitte", CompanySize.FORTUNE_500, "54", 1845, "London, UK", False, 415000, "Professional services"),
                Company("Accenture", CompanySize.FORTUNE_500, "54", 1989, "Dublin, Ireland", True, 733000, "IT consulting"),
            ],
            CompanySize.ENTERPRISE: [
                Company("Booz Allen Hamilton", CompanySize.ENTERPRISE, "54", 1914, "McLean, VA", True, 30000, "Management consulting"),
            ],
            CompanySize.MIDMARKET: [
                Company("West Monroe", CompanySize.MIDMARKET, "54", 2002, "Chicago, IL", False, 1500, "Business and tech consulting"),
            ],
            CompanySize.STARTUP: [
                Company("Pilot", CompanySize.STARTUP, "54", 2017, "San Francisco, CA", False, 400, "Bookkeeping startup"),
            ],
        },
        # ... Additional industries would be populated
    }

    def get_company(
        self,
        naics_code: str,
        size: Optional[CompanySize] = None,
        seed: Optional[int] = None
    ) -> Company:
        """Get a company matching criteria."""
        if seed is not None:
            random.seed(seed)

        industry_companies = self.COMPANIES.get(naics_code, {})
        if not industry_companies:
            # Fallback to generic company generation
            return self._generate_generic_company(naics_code, size)

        if size:
            companies = industry_companies.get(size, [])
        else:
            # Flatten all sizes
            companies = [c for sizes in industry_companies.values() for c in sizes]

        if not companies:
            return self._generate_generic_company(naics_code, size)

        return random.choice(companies)

    def _generate_generic_company(self, naics_code: str, size: Optional[CompanySize]) -> Company:
        """Generate a plausible generic company when no real one available."""
        # Would use LLM to generate realistic company details
        pass

### 2.4 Name Generator

Realistic names add authenticity to prompts.

```python
# src/data/name_generator.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import random

class Generation(Enum):
    GEN_Z = "gen_z"           # 1997-2012, ages ~12-27
    MILLENNIAL = "millennial" # 1981-1996, ages ~28-43
    GEN_X = "gen_x"           # 1965-1980, ages ~44-59
    BOOMER = "boomer"         # 1946-1964, ages ~60-78

class NameFormality(Enum):
    CASUAL = "casual"         # Mike, Lisa
    STANDARD = "standard"     # Michael Chen, Lisa Johnson
    FORMAL = "formal"         # Dr. Michael T. Chen, Ms. Lisa M. Johnson

@dataclass
class PersonName:
    first_name: str
    last_name: str
    full_name: str
    email: str
    title_prefix: Optional[str]  # Dr., Mr., Ms., etc.
    generation: Generation
    formality: NameFormality

class NameGenerator:
    """Generates demographically diverse realistic names."""

    # Name pools by apparent ethnicity/origin (for diversity)
    FIRST_NAMES = {
        'anglo_male': ['James', 'Michael', 'Robert', 'David', 'William', 'John', 'Thomas', 'Daniel'],
        'anglo_female': ['Sarah', 'Jennifer', 'Elizabeth', 'Mary', 'Patricia', 'Linda', 'Barbara', 'Susan'],
        'hispanic_male': ['Carlos', 'Miguel', 'Jose', 'Luis', 'Antonio', 'Francisco', 'Juan', 'Pedro'],
        'hispanic_female': ['Maria', 'Carmen', 'Ana', 'Rosa', 'Isabel', 'Elena', 'Sofia', 'Lucia'],
        'asian_male': ['Wei', 'Jin', 'Hiroshi', 'Kenji', 'Raj', 'Anil', 'Vikram', 'Chen'],
        'asian_female': ['Mei', 'Yuki', 'Priya', 'Sakura', 'Lin', 'Aisha', 'Sana', 'Jing'],
        'african_american_male': ['Marcus', 'Darnell', 'Tyrone', 'Jamal', 'DeShawn', 'Terrell', 'Andre', 'Jerome'],
        'african_american_female': ['Keisha', 'Tamika', 'Latoya', 'Ebony', 'Shanice', 'Aaliyah', 'Jasmine', 'Diamond'],
    }

    LAST_NAMES = {
        'anglo': ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller', 'Davis', 'Wilson', 'Taylor', 'Anderson'],
        'hispanic': ['Garcia', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Perez', 'Sanchez'],
        'asian': ['Chen', 'Wang', 'Li', 'Zhang', 'Liu', 'Kim', 'Park', 'Patel', 'Singh', 'Nguyen', 'Tanaka', 'Yamamoto'],
        'african_american': ['Washington', 'Jefferson', 'Jackson', 'Robinson', 'Harris', 'Thompson', 'Moore', 'Clark'],
    }

    TITLES = ['Dr.', 'Mr.', 'Ms.', 'Mrs.', None, None, None]  # None weighted higher for no title

    def generate(
        self,
        generation: Optional[Generation] = None,
        formality: NameFormality = NameFormality.STANDARD,
        seed: Optional[int] = None
    ) -> PersonName:
        """Generate a realistic person name with demographic diversity."""
        if seed is not None:
            random.seed(seed)

        # Select ethnicity background randomly for diversity
        ethnicity = random.choice(['anglo', 'hispanic', 'asian', 'african_american'])
        gender = random.choice(['male', 'female'])

        first_name_key = f"{ethnicity}_{gender}" if ethnicity != 'anglo' else f"anglo_{gender}"
        first_names = self.FIRST_NAMES.get(first_name_key, self.FIRST_NAMES['anglo_male'])
        first_name = random.choice(first_names)

        last_names = self.LAST_NAMES.get(ethnicity, self.LAST_NAMES['anglo'])
        last_name = random.choice(last_names)

        # Generation defaults to random distribution
        if generation is None:
            generation = random.choice(list(Generation))

        # Build full name based on formality
        title = random.choice(self.TITLES) if formality == NameFormality.FORMAL else None
        middle_initial = f"{chr(random.randint(65, 90))}." if formality == NameFormality.FORMAL else ""

        if formality == NameFormality.CASUAL:
            full_name = first_name
        elif formality == NameFormality.STANDARD:
            full_name = f"{first_name} {last_name}"
        else:
            prefix = f"{title} " if title else ""
            full_name = f"{prefix}{first_name} {middle_initial}{last_name}"

        # Generate email
        email_formats = [
            f"{first_name.lower()}.{last_name.lower()}",
            f"{first_name[0].lower()}{last_name.lower()}",
            f"{first_name.lower()}{last_name[0].lower()}",
        ]
        email_base = random.choice(email_formats)

        return PersonName(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=email_base,  # Domain added during prompt generation
            title_prefix=title,
            generation=generation,
            formality=formality
        )
```

---

## Part 3: Prompt Generation Methodology

The prompt generation system implements a three-phase approach to create diverse, realistic writing tasks.

### 3.1 Prompt Schema

```python
# src/prompts/schemas.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class FormalityLevel(str, Enum):
    VERY_CASUAL = "very_casual"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    VERY_FORMAL = "very_formal"

class UrgencyLevel(str, Enum):
    LOW = "low"
    ROUTINE = "routine"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

class RelationshipContext(str, Enum):
    FIRST_CONTACT = "first_contact"
    NEW_RELATIONSHIP = "new_relationship"
    ESTABLISHED = "established"
    LONG_TERM = "long_term"

class AudienceSize(str, Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"      # 2-10 people
    DEPARTMENT = "department"         # 10-50 people
    COMPANY_WIDE = "company_wide"     # 50-500+ people
    PUBLIC = "public"                 # External/unlimited

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CELEBRATORY = "celebratory"
    URGENT = "urgent"
    CRISIS = "crisis"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"
    GOOD_NEWS = "good_news"

class MessagePosition(str, Enum):
    INITIAL_OUTREACH = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"
    FORWARD = "forward"

class CommunicationChannel(str, Enum):
    EMAIL = "email"
    MEMO = "memo"
    LETTER = "letter"
    REPORT = "report"
    PROPOSAL = "proposal"
    SLACK_MESSAGE = "slack"
    SOCIAL_POST = "social"
    SMS = "sms"
    PRESENTATION = "presentation"
    DOCUMENTATION = "documentation"

class WriterPersona(BaseModel):
    """Detailed persona for the person writing."""
    name: str
    email: Optional[str] = None
    job_title: str
    company: str
    company_size: str
    industry: str
    age_range: str
    generation: str
    skill_level: str  # junior, mid, senior, executive
    english_variant: str = "en-US"

class RecipientPersona(BaseModel):
    """Detailed persona for the recipient(s)."""
    name: str
    email: Optional[str] = None
    job_title: str
    company: Optional[str] = None  # Same company if internal
    relationship_to_writer: str
    english_variant: str = "en-US"
    is_native_english: bool = True

class AttachedContext(BaseModel):
    """Mock attachments or prior context."""
    type: str  # "prior_email", "report_summary", "meeting_notes", "resume", etc.
    content: str
    filename: Optional[str] = None

class EvalPrompt(BaseModel):
    """Complete writing evaluation prompt with all metadata."""

    # Core identification
    prompt_id: str
    onet_task_id: str
    onet_task_text: str

    # Occupation context
    occupation_code: str
    occupation_title: str
    job_zone: int
    soc_major_group: str
    writing_category: str

    # Industry context
    naics_code: str
    naics_title: str

    # Personas
    writer: WriterPersona
    primary_recipient: RecipientPersona
    cc_recipients: List[RecipientPersona] = Field(default_factory=list)

    # Context dimensions
    formality: FormalityLevel
    urgency: UrgencyLevel
    relationship_context: RelationshipContext
    audience_size: AudienceSize
    emotional_context: EmotionalContext
    message_position: MessagePosition
    channel: CommunicationChannel

    # Additional context
    temporal_context: Optional[str] = None  # "It's Q4 2024...", "The deadline is Friday..."
    competing_objectives: List[str] = Field(default_factory=list)  # Trade-offs to navigate
    attached_context: List[AttachedContext] = Field(default_factory=list)
    prior_message: Optional[str] = None  # For replies

    # Constraints (for instruction-following tests)
    explicit_constraints: List[str] = Field(default_factory=list)  # "Keep under 100 words"

    # Tone matching
    tone_example: Optional[str] = None  # Example of desired style

    # Ambiguity (intentional)
    is_deliberately_vague: bool = False
    vagueness_type: Optional[str] = None

    # Sensitive topic flags
    is_sensitive: bool = False
    sensitive_categories: List[str] = Field(default_factory=list)

    # The actual prompt text sent to models
    prompt_text: str

    # Language
    language: str = "en"
    language_variant: str = "en-US"

    # Generation metadata
    generation_seed: int
    generated_at: datetime = Field(default_factory=datetime.now)
    generation_phase: str  # Which phase generated this prompt
```

### 3.2 Phase 1: LLM-Based Persona Generation

```python
# src/prompts/phase1_llm.py

from typing import List, Dict
import asyncio
from .schemas import WriterPersona, RecipientPersona, EvalPrompt
from ..eval.api_client import OpenRouterClient

class Phase1PersonaGenerator:
    """Generate diverse persona variations using LLM."""

    PERSONA_GENERATION_PROMPT = '''
You are generating realistic professional personas for a writing evaluation.

Given this occupation and task:
- Occupation: {occupation_title}
- Task: {task_text}
- Industry: {industry}
- Company: {company_name} ({company_size})

Generate a diverse set of writer and recipient personas that would realistically perform this task.

Requirements:
1. Vary ages across generations (GenZ ~22-27, Millennial ~28-43, GenX ~44-59, Boomer ~60-75)
2. Include diverse names reflecting US workforce demographics
3. Vary skill levels (junior, mid-level, senior, executive)
4. Create realistic relationships (reports to, peer, cross-functional, external)
5. Include plausible email addresses

Output as JSON array with 5 variations:
```json
[
  {{
    "writer": {{
      "name": "Full Name",
      "email": "email@company.com",
      "job_title": "Specific Title",
      "age_range": "25-30",
      "generation": "millennial",
      "skill_level": "junior"
    }},
    "recipient": {{
      "name": "Full Name",
      "email": "email@company.com",
      "job_title": "Specific Title",
      "relationship_to_writer": "direct manager"
    }}
  }}
]
```
'''

    def __init__(self, client: OpenRouterClient, models: List[str]):
        self.client = client
        # Use the same models being evaluated to avoid bias
        self.models = models

    async def generate_personas(
        self,
        task: 'OnetTask',
        company: 'Company',
        industry: 'NAICSIndustry',
        num_variations: int = 5
    ) -> List[Dict]:
        """Generate persona variations for a task."""

        prompt = self.PERSONA_GENERATION_PROMPT.format(
            occupation_title=task.occupation_title,
            task_text=task.task,
            industry=industry.title,
            company_name=company.name,
            company_size=company.size.value
        )

        # Rotate through models for fairness
        model = self.models[hash(task.task_id) % len(self.models)]

        response = await self.client.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,  # Higher temp for diversity
            max_tokens=2000
        )

        return self._parse_personas(response.content)

    def _parse_personas(self, content: str) -> List[Dict]:
        """Parse LLM response into persona dictionaries."""
        import json
        # Extract JSON from response
        try:
            start = content.find('[')
            end = content.rfind(']') + 1
            return json.loads(content[start:end])
        except:
            return []
```

### 3.3 Phase 2: Algorithmic Combination

```python
# src/prompts/phase2_algorithmic.py

from typing import Iterator, List
import random
from .schemas import (
    EvalPrompt, FormalityLevel, UrgencyLevel, RelationshipContext,
    AudienceSize, EmotionalContext, MessagePosition, CommunicationChannel
)
from ..data.onet_loader import OnetTask, WritingCategory

class Phase2AlgorithmicCombiner:
    """Deterministically combine task with context dimensions."""

    # Mapping from job zone to typical formality range
    JOB_ZONE_FORMALITY = {
        1: [FormalityLevel.CASUAL, FormalityLevel.NEUTRAL],
        2: [FormalityLevel.CASUAL, FormalityLevel.NEUTRAL, FormalityLevel.FORMAL],
        3: [FormalityLevel.NEUTRAL, FormalityLevel.FORMAL],
        4: [FormalityLevel.NEUTRAL, FormalityLevel.FORMAL, FormalityLevel.VERY_FORMAL],
        5: [FormalityLevel.FORMAL, FormalityLevel.VERY_FORMAL],
    }

    # Writing category to typical channels
    CATEGORY_CHANNELS = {
        WritingCategory.EXPLICIT_WRITING: [CommunicationChannel.DOCUMENTATION, CommunicationChannel.REPORT],
        WritingCategory.CORRESPONDENCE: [CommunicationChannel.EMAIL, CommunicationChannel.LETTER],
        WritingCategory.REPORTS_ANALYSIS: [CommunicationChannel.REPORT, CommunicationChannel.PRESENTATION],
        WritingCategory.PERSUASION_NEGOTIATION: [CommunicationChannel.EMAIL, CommunicationChannel.PROPOSAL],
        WritingCategory.POLICY_PROCEDURE: [CommunicationChannel.MEMO, CommunicationChannel.DOCUMENTATION],
        WritingCategory.CUSTOMER_COMMUNICATION: [CommunicationChannel.EMAIL, CommunicationChannel.LETTER],
        WritingCategory.INSTRUCTIONAL: [CommunicationChannel.DOCUMENTATION, CommunicationChannel.EMAIL],
        WritingCategory.INTERNAL_COORDINATION: [CommunicationChannel.EMAIL, CommunicationChannel.SLACK_MESSAGE],
        WritingCategory.CONTRACTS_LEGAL: [CommunicationChannel.LETTER, CommunicationChannel.DOCUMENTATION],
        WritingCategory.FEEDBACK_EVALUATION: [CommunicationChannel.EMAIL, CommunicationChannel.REPORT],
    }

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_combinations(
        self,
        task: OnetTask,
        persona_variations: List[dict],
        company: 'Company',
        industry: 'NAICSIndustry',
        num_prompts: int = 10
    ) -> Iterator[dict]:
        """Generate deterministic combinations of task with context."""

        # Seed RNG for reproducibility
        self.rng.seed(hash((self.seed, task.task_id)))

        formality_options = self.JOB_ZONE_FORMALITY.get(task.job_zone, [FormalityLevel.NEUTRAL])
        channel_options = self.CATEGORY_CHANNELS.get(task.writing_category, [CommunicationChannel.EMAIL])

        for i in range(num_prompts):
            persona = self.rng.choice(persona_variations) if persona_variations else {}

            yield {
                'task': task,
                'company': company,
                'industry': industry,
                'persona': persona,
                'formality': self.rng.choice(formality_options),
                'urgency': self.rng.choice(list(UrgencyLevel)),
                'relationship': self.rng.choice(list(RelationshipContext)),
                'audience_size': self._infer_audience_size(task),
                'emotional_context': self._infer_emotional_context(task),
                'message_position': self.rng.choice(list(MessagePosition)),
                'channel': self.rng.choice(channel_options),
                'combination_seed': hash((self.seed, task.task_id, i)),
            }

    def _infer_audience_size(self, task: OnetTask) -> AudienceSize:
        """Infer typical audience size from task text."""
        task_lower = task.task.lower()
        if 'team' in task_lower or 'department' in task_lower:
            return AudienceSize.DEPARTMENT
        elif 'company' in task_lower or 'organization' in task_lower:
            return AudienceSize.COMPANY_WIDE
        elif 'public' in task_lower or 'press' in task_lower:
            return AudienceSize.PUBLIC
        else:
            return AudienceSize.ONE_ON_ONE

    def _infer_emotional_context(self, task: OnetTask) -> EmotionalContext:
        """Infer emotional context from task text."""
        task_lower = task.task.lower()
        if 'complaint' in task_lower or 'problem' in task_lower:
            return EmotionalContext.CONFLICT
        elif 'terminate' in task_lower or 'reject' in task_lower:
            return EmotionalContext.BAD_NEWS
        elif 'congratulat' in task_lower or 'award' in task_lower:
            return EmotionalContext.CELEBRATORY
        elif 'urgent' in task_lower or 'emergency' in task_lower:
            return EmotionalContext.URGENT
        else:
            return EmotionalContext.ROUTINE
```

### 3.4 Phase 3: LLM Enrichment

```python
# src/prompts/phase3_enrichment.py

from typing import Optional, List, Dict
import asyncio
from .schemas import EvalPrompt, AttachedContext
from ..eval.api_client import OpenRouterClient

class Phase3Enricher:
    """Enrich prompts with LLM-generated context where needed."""

    ENRICHMENT_PROMPT = '''
You are enriching a professional writing task with realistic context.

Task: {task_text}
Writer: {writer_name}, {writer_title} at {company}
Recipient: {recipient_name}, {recipient_title}
Relationship: {relationship}
Communication channel: {channel}
Urgency: {urgency}
Formality: {formality}

Generate realistic additional context to make this task concrete and evaluable.

Requirements:
1. If this is a REPLY scenario, create the prior message being replied to
2. If this references data/attachments, create plausible summary content
3. If temporal context is relevant, add specific dates/deadlines
4. Identify any competing objectives the writer must balance
5. Flag if this is a sensitive topic (HR, legal, bad news)

Output as JSON:
```json
{{
  "temporal_context": "It's January 15, 2026..." or null,
  "prior_message": "Email content if reply..." or null,
  "attached_context": [
    {{"type": "report_summary", "content": "Key findings...", "filename": "Q4_report.pdf"}}
  ],
  "competing_objectives": ["Be direct but diplomatic"],
  "is_sensitive": false,
  "sensitive_categories": [],
  "final_prompt": "Complete prompt text to send to models"
}}
```
'''

    PROMPT_TEMPLATE = '''
You are {writer_name}, {writer_title} at {company} ({company_size}, {industry}).

{temporal_context}

Your task: {task_text}

Recipient: {recipient_name}, {recipient_title}
{relationship_context}
Communication channel: {channel}

{prior_message_section}

{attached_context_section}

{constraints_section}

{competing_objectives_section}

Write the {channel} now. Be authentic to your role and relationship with the recipient.
'''

    def __init__(self, client: OpenRouterClient, models: List[str]):
        self.client = client
        self.models = models

    async def enrich_prompt(self, combination: Dict) -> EvalPrompt:
        """Enrich a prompt combination with full context."""

        task = combination['task']
        company = combination['company']
        persona = combination.get('persona', {})

        # Determine if enrichment is needed
        needs_enrichment = (
            combination['message_position'].value == 'reply' or
            self._references_attachments(task.task) or
            combination['urgency'].value in ('high', 'critical') or
            combination['emotional_context'].value in ('crisis', 'conflict', 'bad_news')
        )

        if needs_enrichment:
            enrichment = await self._generate_enrichment(combination)
        else:
            enrichment = self._minimal_enrichment(combination)

        # Build final prompt
        prompt_text = self._build_prompt_text(combination, enrichment)

        # Construct EvalPrompt object
        return EvalPrompt(
            prompt_id=f"prompt_{combination['combination_seed']}",
            onet_task_id=task.task_id,
            onet_task_text=task.task,
            occupation_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            job_zone=task.job_zone,
            soc_major_group=task.soc_major_group,
            writing_category=task.writing_category.value,
            naics_code=combination['industry'].code,
            naics_title=combination['industry'].title,
            writer=self._build_writer_persona(combination, persona),
            primary_recipient=self._build_recipient_persona(combination, persona),
            formality=combination['formality'],
            urgency=combination['urgency'],
            relationship_context=combination['relationship'],
            audience_size=combination['audience_size'],
            emotional_context=combination['emotional_context'],
            message_position=combination['message_position'],
            channel=combination['channel'],
            temporal_context=enrichment.get('temporal_context'),
            competing_objectives=enrichment.get('competing_objectives', []),
            attached_context=[
                AttachedContext(**ac) for ac in enrichment.get('attached_context', [])
            ],
            prior_message=enrichment.get('prior_message'),
            is_sensitive=enrichment.get('is_sensitive', False),
            sensitive_categories=enrichment.get('sensitive_categories', []),
            prompt_text=prompt_text,
            generation_seed=combination['combination_seed'],
            generation_phase='phase3'
        )

    def _references_attachments(self, task_text: str) -> bool:
        """Check if task references external documents."""
        keywords = ['attached', 'report', 'document', 'data', 'spreadsheet', 'resume', 'proposal']
        return any(kw in task_text.lower() for kw in keywords)

    async def _generate_enrichment(self, combination: Dict) -> Dict:
        """Use LLM to generate enrichment details."""
        # Implementation calls LLM with ENRICHMENT_PROMPT
        pass

    def _minimal_enrichment(self, combination: Dict) -> Dict:
        """Provide minimal enrichment for simple prompts."""
        return {
            'temporal_context': None,
            'prior_message': None,
            'attached_context': [],
            'competing_objectives': [],
            'is_sensitive': False,
            'sensitive_categories': []
        }

    def _build_prompt_text(self, combination: Dict, enrichment: Dict) -> str:
        """Construct the final prompt text."""
        # Implementation uses PROMPT_TEMPLATE
        pass
```

### 3.5 Master Prompt Generator

```python
# src/prompts/generator.py

from typing import List, Iterator, Optional
import asyncio
from .phase1_llm import Phase1PersonaGenerator
from .phase2_algorithmic import Phase2AlgorithmicCombiner
from .phase3_enrichment import Phase3Enricher
from .schemas import EvalPrompt
from ..data.onet_loader import OnetLoader
from ..data.naics_mapper import NAICSMapper
from ..data.company_db import CompanyDatabase

class PromptGenerator:
    """Orchestrates three-phase prompt generation."""

    def __init__(
        self,
        onet_loader: OnetLoader,
        naics_mapper: NAICSMapper,
        company_db: CompanyDatabase,
        api_client: 'OpenRouterClient',
        models: List[str],
        seed: int = 42
    ):
        self.onet_loader = onet_loader
        self.naics_mapper = naics_mapper
        self.company_db = company_db
        self.phase1 = Phase1PersonaGenerator(api_client, models)
        self.phase2 = Phase2AlgorithmicCombiner(seed)
        self.phase3 = Phase3Enricher(api_client, models)
        self.seed = seed

    async def generate_prompts(
        self,
        num_prompts: int,
        occupation_filter: Optional[List[str]] = None,
        industry_filter: Optional[List[str]] = None,
        job_zone_filter: Optional[List[int]] = None,
        stratify: bool = True
    ) -> List[EvalPrompt]:
        """Generate specified number of prompts with optional filters."""

        # Phase 1: Extract and filter tasks
        tasks = list(self.onet_loader.extract_writing_tasks())

        if occupation_filter:
            tasks = [t for t in tasks if any(t.onetsoc_code.startswith(o) for o in occupation_filter)]

        if job_zone_filter:
            tasks = [t for t in tasks if t.job_zone in job_zone_filter]

        # Stratified sampling across dimensions
        if stratify:
            tasks = self._stratified_sample(tasks, num_prompts)
        else:
            import random
            random.seed(self.seed)
            tasks = random.sample(tasks, min(len(tasks), num_prompts))

        prompts = []
        for task in tasks:
            # Get industry context
            industries = self.naics_mapper.get_industries_for_occupation(task.soc_major_group)
            if industry_filter:
                industries = [i for i in industries if i.code in industry_filter]
            industry = industries[0] if industries else None

            # Get company
            company = self.company_db.get_company(
                industry.code if industry else '54',
                seed=hash(task.task_id)
            )

            # Phase 1: Generate personas
            personas = await self.phase1.generate_personas(task, company, industry)

            # Phase 2: Generate combinations
            combinations = list(self.phase2.generate_combinations(
                task, personas, company, industry, num_prompts=1
            ))

            # Phase 3: Enrich
            for combo in combinations:
                prompt = await self.phase3.enrich_prompt(combo)
                prompts.append(prompt)

        return prompts

    def _stratified_sample(self, tasks: List, target_count: int) -> List:
        """Sample tasks with even distribution across dimensions."""
        # Stratify by: job_zone, soc_major_group, writing_category
        from collections import defaultdict
        import random

        random.seed(self.seed)
        strata = defaultdict(list)

        for task in tasks:
            key = (task.job_zone, task.soc_major_group, task.writing_category)
            strata[key].append(task)

        # Sample evenly from each stratum
        per_stratum = max(1, target_count // len(strata))
        sampled = []

        for key, stratum_tasks in strata.items():
            sample_size = min(per_stratum, len(stratum_tasks))
            sampled.extend(random.sample(stratum_tasks, sample_size))

        # Fill remaining quota randomly
        remaining = target_count - len(sampled)
        if remaining > 0:
            all_remaining = [t for t in tasks if t not in sampled]
            sampled.extend(random.sample(all_remaining, min(remaining, len(all_remaining))))

        return sampled[:target_count]
```

---

## Part 4: Evaluation Flow and Judging System

### 4.1 OpenRouter API Client

```python
# src/eval/api_client.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
import time

@dataclass
class ModelResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    finish_reason: str
    raw_response: Dict

@dataclass
class APIError:
    error_type: str  # "rate_limit", "timeout", "refusal", "error"
    message: str
    retryable: bool

class OpenRouterClient:
    """Unified client for OpenRouter API with robust error handling."""

    BASE_URL = "https://openrouter.ai/api/v1"

    # Model ID mappings for OpenRouter
    MODEL_IDS = {
        'gemini-3-pro': 'google/gemini-3.0-pro',
        'gemini-3-flash': 'google/gemini-3.0-flash',
        'gpt-5.2-thinking': 'openai/gpt-5.2-thinking',
        'gpt-4.1': 'openai/gpt-4.1',
        'claude-opus-4.5': 'anthropic/claude-opus-4.5',
        'claude-sonnet': 'anthropic/claude-sonnet',
        'grok-4.1-thinking': 'x-ai/grok-4.1-thinking',
        'kimi-k2-thinking': 'moonshot/kimi-k2-thinking',
    }

    # Pricing per 1M tokens (input/output)
    MODEL_PRICING = {
        'gemini-3-pro': (2.50, 10.00),
        'gemini-3-flash': (0.25, 1.00),
        'gpt-5.2-thinking': (15.00, 60.00),
        'gpt-4.1': (2.00, 8.00),
        'claude-opus-4.5': (15.00, 75.00),
        'claude-sonnet': (3.00, 15.00),
    }

    def __init__(self, api_key: str, timeout: float = 120.0):
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://gemini-writing-eval.internal",
                "X-Title": "Gemini Writing Eval"
            },
            timeout=httpx.Timeout(timeout)
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry_error_callback=lambda retry_state: retry_state.outcome.result()
    )
    async def complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> ModelResponse:
        """Send completion request with automatic retry."""

        model_id = self.MODEL_IDS.get(model, model)
        start_time = time.perf_counter()

        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": model_id,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs
                }
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            return ModelResponse(
                content=data['choices'][0]['message']['content'],
                model=model,
                prompt_tokens=data['usage']['prompt_tokens'],
                completion_tokens=data['usage']['completion_tokens'],
                latency_ms=latency_ms,
                finish_reason=data['choices'][0]['finish_reason'],
                raw_response=data
            )

        except httpx.TimeoutException:
            raise TimeoutError(f"Request to {model} timed out after {self.timeout}s")

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a completion."""
        pricing = self.MODEL_PRICING.get(model, (5.0, 20.0))
        return (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000

    async def close(self):
        await self.client.aclose()

class RateLimitError(Exception):
    pass
```

### 4.2 Evaluation Runner

```python
# src/eval/runner.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import asyncio
from datetime import datetime
import json
from pathlib import Path

from .api_client import OpenRouterClient, ModelResponse
from .judge import JudgePanel, JudgeResult
from .vote_aggregator import VoteAggregator, ComparisonResult
from .checkpoint import CheckpointManager
from ..prompts.schemas import EvalPrompt

@dataclass
class ModelPair:
    gemini_model: str  # Always Gemini
    competitor_model: str
    tier: str  # "pro" or "flash"

@dataclass
class EvalConfig:
    """Complete evaluation configuration."""
    # Model configuration
    model_pairs: List[ModelPair]

    # Judge configuration
    judge_models: List[str]
    votes_per_judge: int = 5
    use_both_personas: bool = True

    # Prompt configuration
    prompts: List[EvalPrompt]

    # Sampling
    random_seed: int = 42

    # Output
    output_dir: Path

    # Resume
    resume_from: Optional[Path] = None

class EvalRunner:
    """Orchestrates the complete evaluation process."""

    def __init__(
        self,
        config: EvalConfig,
        api_client: OpenRouterClient,
        progress_callback: Optional[callable] = None
    ):
        self.config = config
        self.client = api_client
        self.judge_panel = JudgePanel(api_client, config.judge_models, config.votes_per_judge)
        self.aggregator = VoteAggregator()
        self.checkpoint = CheckpointManager(config.output_dir)
        self.progress_callback = progress_callback

    async def run(self) -> Dict:
        """Execute the full evaluation."""

        # Initialize or resume
        if self.config.resume_from:
            state = self.checkpoint.load(self.config.resume_from)
        else:
            state = self._initialize_state()

        results = []

        for prompt_idx, prompt in enumerate(self.config.prompts):
            if prompt.prompt_id in state['completed_prompts']:
                continue

            for pair in self.config.model_pairs:
                # Generate responses
                gemini_response, competitor_response = await self._generate_responses(
                    prompt, pair
                )

                if gemini_response is None or competitor_response is None:
                    # Handle failure
                    result = self._handle_failure(prompt, pair, gemini_response, competitor_response)
                else:
                    # Judge responses
                    result = await self._judge_comparison(
                        prompt, pair, gemini_response, competitor_response
                    )

                results.append(result)

                # Update checkpoint
                self.checkpoint.save_result(result)

                # Progress callback
                if self.progress_callback:
                    self.progress_callback(prompt_idx, len(self.config.prompts), result)

            state['completed_prompts'].add(prompt.prompt_id)
            self.checkpoint.update_state(state)

        return self._compile_results(results)

    async def _generate_responses(
        self,
        prompt: EvalPrompt,
        pair: ModelPair
    ) -> Tuple[Optional[ModelResponse], Optional[ModelResponse]]:
        """Generate responses from both models in parallel."""

        async def get_response(model: str) -> Optional[ModelResponse]:
            try:
                return await self.client.complete(
                    model=model,
                    messages=[{"role": "user", "content": prompt.prompt_text}],
                    temperature=0.7
                )
            except Exception as e:
                return None

        gemini_task = get_response(pair.gemini_model)
        competitor_task = get_response(pair.competitor_model)

        return await asyncio.gather(gemini_task, competitor_task)

    async def _judge_comparison(
        self,
        prompt: EvalPrompt,
        pair: ModelPair,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> ComparisonResult:
        """Judge a comparison using the panel."""

        # Randomize order for position bias mitigation
        import random
        rng = random.Random(hash((prompt.prompt_id, pair.competitor_model)))

        if rng.random() < 0.5:
            response_a, response_b = gemini_response, competitor_response
            order = ('gemini', 'competitor')
        else:
            response_a, response_b = competitor_response, gemini_response
            order = ('competitor', 'gemini')

        # Get judgments from all judges
        judge_results = await self.judge_panel.judge(
            prompt=prompt,
            response_a=response_a.content,
            response_b=response_b.content,
            use_both_personas=self.config.use_both_personas
        )

        # Aggregate votes
        return self.aggregator.aggregate(
            prompt=prompt,
            pair=pair,
            judge_results=judge_results,
            response_order=order,
            gemini_response=gemini_response,
            competitor_response=competitor_response
        )
```

### 4.3 Judge Panel Implementation

```python
# src/eval/judge.py

from dataclasses import dataclass
from typing import List, Dict, Optional
import asyncio
from enum import Enum

from .api_client import OpenRouterClient

class JudgeVerdict(Enum):
    A_WINS = "a_wins"
    B_WINS = "b_wins"
    TIE = "tie"

@dataclass
class JudgeVote:
    verdict: JudgeVerdict
    confidence: float  # 0-1
    reasoning: str
    criteria_scores: Dict[str, Dict]  # {criterion: {a_score, b_score}}

@dataclass
class JudgeResult:
    judge_model: str
    persona: str  # "writing_expert" or "recipient"
    votes: List[JudgeVote]
    majority_verdict: JudgeVerdict

class JudgePanel:
    """Ensemble of LLM judges with dual personas."""

    WRITING_EXPERT_PROMPT = '''
You are an expert writing evaluator assessing professional communication quality.

## TASK CONTEXT
{task_context}

## WRITER PERSONA
{writer_context}

## RECIPIENT
{recipient_context}

## RESPONSE A
{response_a}

## RESPONSE B
{response_b}

## EVALUATION CRITERIA
Evaluate both responses on these criteria (1-5 scale each):

1. **Quality of Writing**: Grammar, clarity, flow, structure
2. **Appropriate Length**: Neither too verbose nor too terse for the task
3. **Tone Appropriateness**: Matches formality level and context
4. **Task Completion**: Fully addresses what was asked
5. **Clarity**: Easy to understand, unambiguous
6. **Authenticity**: Reads as natural human writing, not AI-generated
7. **Cliché Avoidance**: Avoids boilerplate phrases ("I hope this finds you well")
8. **Effectiveness**: Would achieve the writer's goal

## OUTPUT FORMAT
Provide your evaluation as JSON:
```json
{{
  "criteria_scores": {{
    "quality_of_writing": {{"a": 4, "b": 3}},
    "appropriate_length": {{"a": 3, "b": 4}},
    "tone_appropriateness": {{"a": 4, "b": 4}},
    "task_completion": {{"a": 5, "b": 4}},
    "clarity": {{"a": 4, "b": 3}},
    "authenticity": {{"a": 3, "b": 4}},
    "cliche_avoidance": {{"a": 2, "b": 4}},
    "effectiveness": {{"a": 4, "b": 4}}
  }},
  "verdict": "a_wins" | "b_wins" | "tie",
  "confidence": 0.85,
  "reasoning": "Response A excels in... but Response B..."
}}
```
'''

    RECIPIENT_PERSONA_PROMPT = '''
You are {recipient_name}, {recipient_title}, evaluating messages you received.

## YOUR CONTEXT
{recipient_context}

## MESSAGE FROM: {writer_name}, {writer_title}
## REGARDING: {task_summary}

You received two versions of this message. Which would you prefer to receive?

## VERSION A
{response_a}

## VERSION B
{response_b}

## EVALUATION CRITERIA
As the recipient, evaluate based on:

1. **Relevance**: Does this address what I need?
2. **Actionability**: Can I easily act on this?
3. **Respect for Time**: Appropriate length, gets to the point
4. **Professionalism**: Appropriate tone for our relationship
5. **Helpfulness**: Would this help me accomplish my goals?
6. **Clarity**: Do I understand what's being asked/communicated?

## OUTPUT FORMAT
```json
{{
  "criteria_scores": {{
    "relevance": {{"a": 4, "b": 3}},
    "actionability": {{"a": 3, "b": 4}},
    "respect_for_time": {{"a": 4, "b": 5}},
    "professionalism": {{"a": 4, "b": 4}},
    "helpfulness": {{"a": 4, "b": 3}},
    "clarity": {{"a": 4, "b": 4}}
  }},
  "verdict": "a_wins" | "b_wins" | "tie",
  "confidence": 0.75,
  "reasoning": "As the recipient, I prefer Version A because..."
}}
```
'''

    def __init__(
        self,
        client: OpenRouterClient,
        judge_models: List[str],
        votes_per_judge: int = 5
    ):
        self.client = client
        self.judge_models = judge_models
        self.votes_per_judge = votes_per_judge

    async def judge(
        self,
        prompt: 'EvalPrompt',
        response_a: str,
        response_b: str,
        use_both_personas: bool = True
    ) -> List[JudgeResult]:
        """Get judgments from all judges with specified personas."""

        tasks = []
        for model in self.judge_models:
            # Writing expert persona
            tasks.append(self._get_judge_result(
                model=model,
                persona="writing_expert",
                prompt=prompt,
                response_a=response_a,
                response_b=response_b
            ))

            # Recipient persona (if enabled)
            if use_both_personas:
                tasks.append(self._get_judge_result(
                    model=model,
                    persona="recipient",
                    prompt=prompt,
                    response_a=response_a,
                    response_b=response_b
                ))

        return await asyncio.gather(*tasks)

    async def _get_judge_result(
        self,
        model: str,
        persona: str,
        prompt: 'EvalPrompt',
        response_a: str,
        response_b: str
    ) -> JudgeResult:
        """Get best-of-N votes from a single judge."""

        judge_prompt = self._build_judge_prompt(persona, prompt, response_a, response_b)

        votes = []
        for i in range(self.votes_per_judge):
            response = await self.client.complete(
                model=model,
                messages=[{"role": "user", "content": judge_prompt}],
                temperature=0.3 + (i * 0.1),  # Slight variation
                max_tokens=1500
            )
            vote = self._parse_vote(response.content)
            votes.append(vote)

        # Determine majority
        verdicts = [v.verdict for v in votes]
        majority = max(set(verdicts), key=verdicts.count)

        return JudgeResult(
            judge_model=model,
            persona=persona,
            votes=votes,
            majority_verdict=majority
        )

    def _build_judge_prompt(
        self,
        persona: str,
        prompt: 'EvalPrompt',
        response_a: str,
        response_b: str
    ) -> str:
        """Build the appropriate judge prompt."""
        if persona == "writing_expert":
            return self.WRITING_EXPERT_PROMPT.format(
                task_context=prompt.onet_task_text,
                writer_context=f"{prompt.writer.name}, {prompt.writer.job_title} at {prompt.writer.company}",
                recipient_context=f"{prompt.primary_recipient.name}, {prompt.primary_recipient.job_title}",
                response_a=response_a,
                response_b=response_b
            )
        else:
            return self.RECIPIENT_PERSONA_PROMPT.format(
                recipient_name=prompt.primary_recipient.name,
                recipient_title=prompt.primary_recipient.job_title,
                recipient_context=f"You work at {prompt.writer.company}. Your relationship: {prompt.primary_recipient.relationship_to_writer}",
                writer_name=prompt.writer.name,
                writer_title=prompt.writer.job_title,
                task_summary=prompt.onet_task_text,
                response_a=response_a,
                response_b=response_b
            )

    def _parse_vote(self, content: str) -> JudgeVote:
        """Parse LLM response into a JudgeVote."""
        import json
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            data = json.loads(content[start:end])

            verdict_map = {
                'a_wins': JudgeVerdict.A_WINS,
                'b_wins': JudgeVerdict.B_WINS,
                'tie': JudgeVerdict.TIE
            }

            return JudgeVote(
                verdict=verdict_map.get(data['verdict'], JudgeVerdict.TIE),
                confidence=data.get('confidence', 0.5),
                reasoning=data.get('reasoning', ''),
                criteria_scores=data.get('criteria_scores', {})
            )
        except:
            return JudgeVote(
                verdict=JudgeVerdict.TIE,
                confidence=0.0,
                reasoning="Parse error",
                criteria_scores={}
            )
```

### 4.4 Vote Aggregator (Majority of Majorities)

```python
# src/eval/vote_aggregator.py

from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import Counter

from .judge import JudgeResult, JudgeVerdict

@dataclass
class ComparisonResult:
    """Complete result of a single comparison."""
    prompt_id: str
    gemini_model: str
    competitor_model: str

    # Responses
    gemini_response: str
    competitor_response: str
    gemini_latency_ms: float
    competitor_latency_ms: float
    gemini_tokens: int
    competitor_tokens: int

    # Presentation order
    response_order: Tuple[str, str]  # ('gemini', 'competitor') or ('competitor', 'gemini')

    # Judge results
    judge_results: List[JudgeResult]

    # Aggregated verdict
    final_verdict: str  # "gemini_wins", "competitor_wins", "tie"
    judge_verdicts: Dict[str, str]  # {judge_model: verdict}

    # Agreement metrics
    inter_judge_agreement: float  # Proportion agreeing with final verdict

    # Metadata
    is_auto_loss: bool  # If one model failed/refused
    auto_loss_reason: Optional[str]

class VoteAggregator:
    """Implements majority-of-majorities aggregation."""

    def aggregate(
        self,
        prompt: 'EvalPrompt',
        pair: 'ModelPair',
        judge_results: List[JudgeResult],
        response_order: Tuple[str, str],
        gemini_response: 'ModelResponse',
        competitor_response: 'ModelResponse'
    ) -> ComparisonResult:
        """Aggregate judge results into final verdict."""

        # Map position to model
        position_to_model = {
            'a': response_order[0],
            'b': response_order[1]
        }

        # Get each judge's majority verdict
        judge_verdicts = {}
        for result in judge_results:
            key = f"{result.judge_model}_{result.persona}"

            # Convert position verdict to model verdict
            if result.majority_verdict == JudgeVerdict.A_WINS:
                judge_verdicts[key] = position_to_model['a']
            elif result.majority_verdict == JudgeVerdict.B_WINS:
                judge_verdicts[key] = position_to_model['b']
            else:
                judge_verdicts[key] = 'tie'

        # Final majority of majorities
        verdict_counts = Counter(judge_verdicts.values())
        most_common = verdict_counts.most_common(1)[0]

        if most_common[1] > len(judge_verdicts) / 2:
            final_verdict = most_common[0]
            if final_verdict == 'gemini':
                final_verdict = 'gemini_wins'
            elif final_verdict == 'competitor':
                final_verdict = 'competitor_wins'
        else:
            final_verdict = 'tie'

        # Calculate agreement
        agreeing = sum(1 for v in judge_verdicts.values() if v == most_common[0])
        inter_judge_agreement = agreeing / len(judge_verdicts)

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            gemini_model=pair.gemini_model,
            competitor_model=pair.competitor_model,
            gemini_response=gemini_response.content,
            competitor_response=competitor_response.content,
            gemini_latency_ms=gemini_response.latency_ms,
            competitor_latency_ms=competitor_response.latency_ms,
            gemini_tokens=gemini_response.completion_tokens,
            competitor_tokens=competitor_response.completion_tokens,
            response_order=response_order,
            judge_results=judge_results,
            final_verdict=final_verdict,
            judge_verdicts=judge_verdicts,
            inter_judge_agreement=inter_judge_agreement,
            is_auto_loss=False,
            auto_loss_reason=None
        )
```

### 4.5 Checkpoint Manager

```python
# src/eval/checkpoint.py

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional
import json
import sqlite3

class CheckpointManager:
    """Manages checkpointing for resumable evaluations."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.checkpoint_file = output_dir / "checkpoint.json"
        self.db_path = output_dir / "results.db"

        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for results."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS comparisons (
                    id INTEGER PRIMARY KEY,
                    prompt_id TEXT NOT NULL,
                    gemini_model TEXT NOT NULL,
                    competitor_model TEXT NOT NULL,
                    final_verdict TEXT NOT NULL,
                    gemini_response TEXT,
                    competitor_response TEXT,
                    gemini_latency_ms REAL,
                    competitor_latency_ms REAL,
                    gemini_tokens INTEGER,
                    competitor_tokens INTEGER,
                    inter_judge_agreement REAL,
                    is_auto_loss INTEGER,
                    auto_loss_reason TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(prompt_id, competitor_model)
                );

                CREATE TABLE IF NOT EXISTS judge_votes (
                    id INTEGER PRIMARY KEY,
                    comparison_id INTEGER NOT NULL,
                    judge_model TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    vote_index INTEGER NOT NULL,
                    verdict TEXT NOT NULL,
                    confidence REAL,
                    reasoning TEXT,
                    criteria_scores TEXT,
                    FOREIGN KEY(comparison_id) REFERENCES comparisons(id)
                );

                CREATE INDEX IF NOT EXISTS idx_prompt_id ON comparisons(prompt_id);
                CREATE INDEX IF NOT EXISTS idx_verdict ON comparisons(final_verdict);
            ''')

    def save_result(self, result: 'ComparisonResult'):
        """Save a comparison result to database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO comparisons
                (prompt_id, gemini_model, competitor_model, final_verdict,
                 gemini_response, competitor_response, gemini_latency_ms,
                 competitor_latency_ms, gemini_tokens, competitor_tokens,
                 inter_judge_agreement, is_auto_loss, auto_loss_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.prompt_id,
                result.gemini_model,
                result.competitor_model,
                result.final_verdict,
                result.gemini_response,
                result.competitor_response,
                result.gemini_latency_ms,
                result.competitor_latency_ms,
                result.gemini_tokens,
                result.competitor_tokens,
                result.inter_judge_agreement,
                1 if result.is_auto_loss else 0,
                result.auto_loss_reason,
                datetime.now().isoformat()
            ))

            comparison_id = cursor.lastrowid

            # Save judge votes
            for judge_result in result.judge_results:
                for i, vote in enumerate(judge_result.votes):
                    conn.execute('''
                        INSERT INTO judge_votes
                        (comparison_id, judge_model, persona, vote_index,
                         verdict, confidence, reasoning, criteria_scores)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        comparison_id,
                        judge_result.judge_model,
                        judge_result.persona,
                        i,
                        vote.verdict.value,
                        vote.confidence,
                        vote.reasoning,
                        json.dumps(vote.criteria_scores)
                    ))

    def update_state(self, state: Dict):
        """Save checkpoint state."""
        checkpoint_data = {
            'completed_prompts': list(state['completed_prompts']),
            'last_updated': datetime.now().isoformat(),
            'total_comparisons': state.get('total_comparisons', 0)
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

    def load(self, resume_path: Optional[Path] = None) -> Dict:
        """Load checkpoint state."""
        path = resume_path or self.checkpoint_file
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return {
                    'completed_prompts': set(data['completed_prompts']),
                    'total_comparisons': data.get('total_comparisons', 0)
                }
        return {'completed_prompts': set(), 'total_comparisons': 0}
```

---

## Part 5: Results Storage and Analysis

### 5.1 Statistical Analysis Engine

```python
# src/analysis/statistics.py

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
from scipy import stats
import sqlite3
from pathlib import Path

@dataclass
class WinRateStats:
    """Win rate with confidence interval."""
    win_rate: float
    lower_bound: float
    upper_bound: float
    n_samples: int
    confidence_level: float

@dataclass
class ComparisonStats:
    """Statistics for a model pair comparison."""
    gemini_model: str
    competitor_model: str
    gemini_wins: int
    competitor_wins: int
    ties: int
    total: int
    gemini_win_rate: WinRateStats
    competitor_win_rate: WinRateStats
    p_value: float  # Statistical significance
    effect_size: float  # Cohen's h

class StatisticalAnalyzer:
    """Comprehensive statistical analysis of evaluation results."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def compute_overall_stats(self) -> Dict[str, ComparisonStats]:
        """Compute overall statistics per model pair."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT
                    competitor_model,
                    SUM(CASE WHEN final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) as gemini_wins,
                    SUM(CASE WHEN final_verdict = 'competitor_wins' THEN 1 ELSE 0 END) as competitor_wins,
                    SUM(CASE WHEN final_verdict = 'tie' THEN 1 ELSE 0 END) as ties,
                    COUNT(*) as total
                FROM comparisons
                GROUP BY competitor_model
            ''').fetchall()

        results = {}
        for row in rows:
            stats = self._compute_pair_stats(
                gemini_wins=row['gemini_wins'],
                competitor_wins=row['competitor_wins'],
                ties=row['ties'],
                competitor_model=row['competitor_model']
            )
            results[row['competitor_model']] = stats

        return results

    def compute_stats_by_dimension(
        self,
        dimension: str  # 'occupation', 'industry', 'job_zone', 'formality', etc.
    ) -> Dict[str, Dict[str, ComparisonStats]]:
        """Compute statistics broken down by a dimension."""
        # Would join with prompts table to get dimension values
        pass

    def _compute_pair_stats(
        self,
        gemini_wins: int,
        competitor_wins: int,
        ties: int,
        competitor_model: str
    ) -> ComparisonStats:
        """Compute statistics for a single pair."""
        total = gemini_wins + competitor_wins + ties
        total_decisive = gemini_wins + competitor_wins

        # Win rates (excluding ties)
        gemini_rate = gemini_wins / total_decisive if total_decisive > 0 else 0.5
        competitor_rate = competitor_wins / total_decisive if total_decisive > 0 else 0.5

        # Wilson score confidence intervals
        gemini_ci = self._wilson_confidence_interval(gemini_wins, total_decisive)
        competitor_ci = self._wilson_confidence_interval(competitor_wins, total_decisive)

        # Binomial test for statistical significance
        if total_decisive > 0:
            p_value = stats.binomtest(gemini_wins, total_decisive, 0.5).pvalue
        else:
            p_value = 1.0

        # Cohen's h effect size
        effect_size = self._cohens_h(gemini_rate, 0.5)

        return ComparisonStats(
            gemini_model="gemini",
            competitor_model=competitor_model,
            gemini_wins=gemini_wins,
            competitor_wins=competitor_wins,
            ties=ties,
            total=total,
            gemini_win_rate=WinRateStats(
                win_rate=gemini_rate,
                lower_bound=gemini_ci[0],
                upper_bound=gemini_ci[1],
                n_samples=total_decisive,
                confidence_level=0.95
            ),
            competitor_win_rate=WinRateStats(
                win_rate=competitor_rate,
                lower_bound=competitor_ci[0],
                upper_bound=competitor_ci[1],
                n_samples=total_decisive,
                confidence_level=0.95
            ),
            p_value=p_value,
            effect_size=effect_size
        )

    def _wilson_confidence_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Compute Wilson score confidence interval."""
        if total == 0:
            return (0.0, 1.0)

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = successes / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        spread = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator

        return (max(0, center - spread), min(1, center + spread))

    def _cohens_h(self, p1: float, p2: float) -> float:
        """Compute Cohen's h effect size for two proportions."""
        phi1 = 2 * np.arcsin(np.sqrt(p1))
        phi2 = 2 * np.arcsin(np.sqrt(p2))
        return abs(phi1 - phi2)

    def compute_inter_judge_agreement(self) -> Dict[str, float]:
        """Compute Cohen's Kappa for inter-judge agreement."""
        # Would compute pairwise agreement between judges
        pass
```

### 5.2 Bias Detection

```python
# src/analysis/bias_detection.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
from scipy import stats
import sqlite3
from pathlib import Path

@dataclass
class BiasReport:
    bias_type: str
    description: str
    severity: str  # "none", "low", "medium", "high"
    statistical_significance: float
    details: Dict

class BiasDetector:
    """Detect and report systematic biases."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def detect_all_biases(self) -> List[BiasReport]:
        """Run all bias detection analyses."""
        biases = []
        biases.extend(self.detect_position_bias())
        biases.extend(self.detect_length_bias())
        biases.extend(self.detect_judge_model_bias())
        return biases

    def detect_position_bias(self) -> List[BiasReport]:
        """Detect if judges prefer Response A or B systematically."""
        with sqlite3.connect(self.db_path) as conn:
            # Count A wins vs B wins across all votes
            result = conn.execute('''
                SELECT
                    verdict,
                    COUNT(*) as count
                FROM judge_votes
                WHERE verdict IN ('a_wins', 'b_wins')
                GROUP BY verdict
            ''').fetchall()

        if len(result) < 2:
            return []

        a_wins = sum(r[1] for r in result if r[0] == 'a_wins')
        b_wins = sum(r[1] for r in result if r[0] == 'b_wins')
        total = a_wins + b_wins

        # Binomial test for position bias
        p_value = stats.binomtest(a_wins, total, 0.5).pvalue
        bias_ratio = a_wins / total

        if p_value < 0.05:
            severity = "high" if abs(bias_ratio - 0.5) > 0.1 else "medium"
            return [BiasReport(
                bias_type="position_bias",
                description=f"Judges prefer {'Response A' if bias_ratio > 0.5 else 'Response B'} ({bias_ratio:.1%} vs {1-bias_ratio:.1%})",
                severity=severity,
                statistical_significance=p_value,
                details={"a_wins": a_wins, "b_wins": b_wins, "ratio": bias_ratio}
            )]

        return [BiasReport(
            bias_type="position_bias",
            description="No significant position bias detected",
            severity="none",
            statistical_significance=p_value,
            details={"a_wins": a_wins, "b_wins": b_wins, "ratio": bias_ratio}
        )]

    def detect_length_bias(self) -> List[BiasReport]:
        """Detect if longer/shorter responses win more often."""
        with sqlite3.connect(self.db_path) as conn:
            results = conn.execute('''
                SELECT
                    final_verdict,
                    gemini_tokens,
                    competitor_tokens
                FROM comparisons
                WHERE final_verdict != 'tie'
            ''').fetchall()

        if not results:
            return []

        # Calculate token differences
        gemini_wins_lengths = []
        competitor_wins_lengths = []

        for verdict, g_tokens, c_tokens in results:
            if verdict == 'gemini_wins':
                gemini_wins_lengths.append(g_tokens - c_tokens)
            else:
                competitor_wins_lengths.append(c_tokens - g_tokens)

        # T-test for length difference
        all_winner_diffs = gemini_wins_lengths + competitor_wins_lengths
        t_stat, p_value = stats.ttest_1samp(all_winner_diffs, 0)

        avg_diff = np.mean(all_winner_diffs)
        if p_value < 0.05 and abs(avg_diff) > 50:
            direction = "longer" if avg_diff > 0 else "shorter"
            return [BiasReport(
                bias_type="length_bias",
                description=f"Winners tend to be {direction} by ~{abs(avg_diff):.0f} tokens on average",
                severity="medium" if abs(avg_diff) > 100 else "low",
                statistical_significance=p_value,
                details={"average_token_difference": avg_diff, "t_statistic": t_stat}
            )]

        return []

    def detect_judge_model_bias(self) -> List[BiasReport]:
        """Detect if certain judge models favor certain contestants."""
        with sqlite3.connect(self.db_path) as conn:
            results = conn.execute('''
                SELECT
                    jv.judge_model,
                    c.final_verdict,
                    COUNT(*) as count
                FROM judge_votes jv
                JOIN comparisons c ON jv.comparison_id = c.id
                GROUP BY jv.judge_model, c.final_verdict
            ''').fetchall()

        # Analysis per judge model
        # Would compare each judge's verdict distribution
        return []
```

### 5.3 Weakness Finder

```python
# src/analysis/weakness_finder.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import sqlite3
from pathlib import Path
from collections import defaultdict

@dataclass
class Weakness:
    dimension: str  # 'occupation', 'industry', 'writing_category', etc.
    value: str      # The specific value where Gemini underperforms
    gemini_win_rate: float
    sample_size: int
    severity: str   # "critical", "significant", "notable", "minor"
    example_prompts: List[str]

class WeaknessFinder:
    """Identify specific areas where Gemini underperforms."""

    def __init__(self, db_path: Path, prompts_db_path: Path):
        self.db_path = db_path
        self.prompts_db_path = prompts_db_path

    def find_all_weaknesses(
        self,
        min_sample_size: int = 10,
        win_rate_threshold: float = 0.4
    ) -> List[Weakness]:
        """Find all areas where Gemini underperforms."""
        weaknesses = []

        # Check each dimension
        for dimension in ['occupation_code', 'job_zone', 'writing_category',
                          'naics_code', 'formality', 'urgency', 'channel']:
            dim_weaknesses = self._find_weaknesses_by_dimension(
                dimension, min_sample_size, win_rate_threshold
            )
            weaknesses.extend(dim_weaknesses)

        # Sort by severity
        severity_order = {'critical': 0, 'significant': 1, 'notable': 2, 'minor': 3}
        weaknesses.sort(key=lambda w: (severity_order[w.severity], -w.sample_size))

        return weaknesses

    def _find_weaknesses_by_dimension(
        self,
        dimension: str,
        min_sample_size: int,
        win_rate_threshold: float
    ) -> List[Weakness]:
        """Find weaknesses for a specific dimension."""
        # Query would join comparisons with prompts to get dimension values
        # Then calculate win rates per dimension value
        weaknesses = []

        # Example implementation
        with sqlite3.connect(self.db_path) as conn:
            # This would need to join with prompts table
            query = f'''
                SELECT
                    p.{dimension} as dim_value,
                    SUM(CASE WHEN c.final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) as wins,
                    COUNT(*) as total
                FROM comparisons c
                JOIN prompts p ON c.prompt_id = p.prompt_id
                GROUP BY p.{dimension}
                HAVING COUNT(*) >= ?
            '''
            # ... execute and process

        return weaknesses

    def generate_weakness_report(self) -> str:
        """Generate human-readable weakness report."""
        weaknesses = self.find_all_weaknesses()

        lines = ["# Gemini Writing Weaknesses Report\n"]

        # Group by severity
        by_severity = defaultdict(list)
        for w in weaknesses:
            by_severity[w.severity].append(w)

        for severity in ['critical', 'significant', 'notable', 'minor']:
            if by_severity[severity]:
                lines.append(f"\n## {severity.title()} Weaknesses\n")
                for w in by_severity[severity]:
                    lines.append(f"- **{w.dimension}={w.value}**: {w.gemini_win_rate:.1%} win rate (n={w.sample_size})")

        return "\n".join(lines)
```

---

## Part 6: TUI Implementation

### 6.1 Progress Dashboard

```python
# src/tui/progress.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from datetime import datetime, timedelta
from typing import Dict, Optional

class ProgressDashboard(App):
    """Real-time progress dashboard for evaluation runs."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1;
    }

    #overall-progress {
        column-span: 2;
        height: 6;
    }

    #model-pairs {
        height: 10;
    }

    #current-batch {
        height: 10;
    }

    #live-stats {
        height: 8;
    }

    #activity-log {
        height: 8;
    }

    #error-summary {
        column-span: 2;
        height: 3;
    }

    .progress-box {
        border: solid green;
        padding: 1;
    }
    """

    # Reactive state
    total_prompts = reactive(0)
    completed_prompts = reactive(0)
    current_prompt = reactive("")
    elapsed_time = reactive(timedelta())
    estimated_remaining = reactive(timedelta())

    def __init__(self, config: 'EvalConfig'):
        super().__init__()
        self.config = config
        self.start_time = datetime.now()
        self.model_pair_progress = {}
        self.recent_activity = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield OverallProgress(id="overall-progress")
            yield ModelPairsPanel(id="model-pairs")
            yield CurrentBatchPanel(id="current-batch")
            yield LiveStatsPanel(id="live-stats")
            yield ActivityLog(id="activity-log")
            yield ErrorSummary(id="error-summary")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize dashboard state."""
        self.total_prompts = len(self.config.prompts)
        self.set_interval(1.0, self._update_time)

    def _update_time(self) -> None:
        """Update elapsed time display."""
        self.elapsed_time = datetime.now() - self.start_time

        # Estimate remaining time
        if self.completed_prompts > 0:
            rate = self.completed_prompts / self.elapsed_time.total_seconds()
            remaining = (self.total_prompts - self.completed_prompts) / rate
            self.estimated_remaining = timedelta(seconds=remaining)

    def update_progress(self, prompt_idx: int, result: 'ComparisonResult'):
        """Called by eval runner to update progress."""
        self.completed_prompts = prompt_idx + 1
        self.current_prompt = result.prompt_id

        # Update model pair progress
        key = result.competitor_model
        if key not in self.model_pair_progress:
            self.model_pair_progress[key] = {'completed': 0, 'wins': 0, 'losses': 0}

        self.model_pair_progress[key]['completed'] += 1
        if result.final_verdict == 'gemini_wins':
            self.model_pair_progress[key]['wins'] += 1
        elif result.final_verdict == 'competitor_wins':
            self.model_pair_progress[key]['losses'] += 1

        # Add to activity log
        self.recent_activity.append(f"{datetime.now().strftime('%H:%M:%S')} - {result.prompt_id}: {result.final_verdict}")
        if len(self.recent_activity) > 10:
            self.recent_activity.pop(0)

        self.refresh()

class OverallProgress(Static):
    """Overall progress bar widget."""

    def render(self) -> Panel:
        app = self.app
        progress = app.completed_prompts / app.total_prompts if app.total_prompts > 0 else 0
        bar = "█" * int(progress * 40) + "░" * (40 - int(progress * 40))

        content = Text()
        content.append(f"{bar}  {app.completed_prompts}/{app.total_prompts} ({progress:.1%})\n", style="green")
        content.append(f"Elapsed: {app.elapsed_time}  |  ETA: {app.estimated_remaining}", style="dim")

        return Panel(content, title="Overall Progress", border_style="green")

class ModelPairsPanel(Static):
    """Per-model-pair progress."""

    def render(self) -> Panel:
        app = self.app
        lines = []
        for model, stats in app.model_pair_progress.items():
            total = stats['completed']
            wins = stats['wins']
            win_rate = wins / total if total > 0 else 0
            bar = "█" * int(win_rate * 20) + "░" * (20 - int(win_rate * 20))
            lines.append(f"vs {model:20s} [{bar}] {win_rate:.1%} ({total} done)")

        return Panel("\n".join(lines) or "No results yet", title="Model Pairs", border_style="blue")

class LiveStatsPanel(Static):
    """Live statistics panel."""

    def render(self) -> Panel:
        app = self.app

        # Calculate running stats
        total_wins = sum(s['wins'] for s in app.model_pair_progress.values())
        total_losses = sum(s['losses'] for s in app.model_pair_progress.values())
        total = total_wins + total_losses

        win_rate = total_wins / total if total > 0 else 0

        content = f"""
Win Rate: {win_rate:.1%} ({total_wins}W / {total_losses}L)
Total Comparisons: {total}
API Calls/min: ~{app.completed_prompts / max(1, app.elapsed_time.total_seconds() / 60):.1f}
        """
        return Panel(content.strip(), title="Live Statistics", border_style="yellow")

class ActivityLog(Log):
    """Scrolling activity log."""
    pass

class ErrorSummary(Static):
    """Error and warning summary."""

    def render(self) -> Panel:
        return Panel("No errors", title="Errors & Warnings", border_style="red")
```

### 6.2 Results Viewer TUI

```python
# src/tui/viewer.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, DataTable, Input, Select, Button, TextArea
from textual.binding import Binding
from pathlib import Path
import sqlite3

class ResultsViewer(App):
    """Interactive TUI for exploring evaluation results."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "filter", "Filter"),
        Binding("s", "sort", "Sort"),
        Binding("d", "details", "Details"),
        Binding("/", "search", "Search"),
    ]

    CSS = """
    #main-layout {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
    }

    #results-table {
        height: 100%;
    }

    #detail-panel {
        height: 100%;
        border: solid blue;
    }

    #filters {
        height: 5;
        dock: top;
    }
    """

    def __init__(self, db_path: Path):
        super().__init__()
        self.db_path = db_path
        self.current_selection = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="filters"):
            yield FilterBar()
        with Horizontal(id="main-layout"):
            yield ResultsTable(id="results-table")
            yield DetailPanel(id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        """Load initial data."""
        self.load_results()

    def load_results(self, filters: dict = None):
        """Load results from database with optional filters."""
        table = self.query_one(ResultsTable)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = '''
                SELECT
                    prompt_id,
                    competitor_model,
                    final_verdict,
                    inter_judge_agreement,
                    gemini_tokens,
                    competitor_tokens
                FROM comparisons
                ORDER BY created_at DESC
                LIMIT 1000
            '''
            rows = conn.execute(query).fetchall()

        table.load_data(rows)

    def show_details(self, prompt_id: str):
        """Show detailed view for a comparison."""
        panel = self.query_one(DetailPanel)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            comparison = conn.execute('''
                SELECT * FROM comparisons WHERE prompt_id = ?
            ''', (prompt_id,)).fetchone()

            votes = conn.execute('''
                SELECT * FROM judge_votes
                WHERE comparison_id = ?
            ''', (comparison['id'],)).fetchall()

        panel.show_comparison(comparison, votes)

class FilterBar(Static):
    """Filter controls."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Select(
                [(v, v) for v in ['All', 'gemini_wins', 'competitor_wins', 'tie']],
                prompt="Verdict",
                id="verdict-filter"
            )
            yield Select(
                [(v, v) for v in ['All', 'gpt-5.2', 'claude-opus', 'grok-4.1']],
                prompt="Competitor",
                id="competitor-filter"
            )
            yield Input(placeholder="Search prompts...", id="search-input")

class ResultsTable(DataTable):
    """Main results table."""

    def on_mount(self) -> None:
        self.add_columns(
            "Prompt ID", "vs Model", "Verdict", "Agreement", "G Tokens", "C Tokens"
        )
        self.cursor_type = "row"

    def load_data(self, rows):
        """Load data into table."""
        self.clear()
        for row in rows:
            self.add_row(
                row['prompt_id'][:20],
                row['competitor_model'],
                row['final_verdict'],
                f"{row['inter_judge_agreement']:.2f}",
                str(row['gemini_tokens']),
                str(row['competitor_tokens'])
            )

    def on_data_table_row_selected(self, event):
        """Handle row selection."""
        self.app.show_details(event.row_key.value)

class DetailPanel(ScrollableContainer):
    """Detail view for selected comparison."""

    def show_comparison(self, comparison: dict, votes: list):
        """Display comparison details."""
        # Clear existing content
        self.remove_children()

        # Add comparison details
        self.mount(Static(f"# {comparison['prompt_id']}", classes="title"))
        self.mount(Static(f"Verdict: {comparison['final_verdict']}"))

        # Add responses side by side
        self.mount(Static("## Gemini Response"))
        self.mount(TextArea(comparison['gemini_response'], read_only=True))

        self.mount(Static("## Competitor Response"))
        self.mount(TextArea(comparison['competitor_response'], read_only=True))

        # Add judge votes
        self.mount(Static("## Judge Votes"))
        for vote in votes:
            self.mount(Static(f"- {vote['judge_model']} ({vote['persona']}): {vote['verdict']}"))
```

---

## Part 7: CLI and Configuration

### 7.1 CLI Interface

```python
# src/cli.py

import click
import asyncio
from pathlib import Path
from datetime import datetime
import yaml

from .config import EvalConfig, load_preset, estimate_cost
from .eval.runner import EvalRunner
from .eval.api_client import OpenRouterClient
from .prompts.generator import PromptGenerator
from .data.onet_loader import OnetLoader
from .tui.progress import ProgressDashboard
from .tui.viewer import ResultsViewer
from .reporting.pdf_generator import PDFReportGenerator

@click.group()
def cli():
    """Gemini Writing Evaluation Framework"""
    pass

@cli.command()
@click.option('--preset', type=int, help='Preset level 1-10')
@click.option('--prompts', type=int, help='Number of prompts to evaluate')
@click.option('--models', type=str, help='Comma-separated model pairs')
@click.option('--judges', type=str, help='Comma-separated judge models')
@click.option('--votes', type=int, default=5, help='Votes per judge')
@click.option('--occupations', type=str, help='Filter by occupation codes')
@click.option('--industries', type=str, help='Filter by NAICS codes')
@click.option('--seed', type=int, default=42, help='Random seed')
@click.option('--output', type=Path, help='Output directory')
@click.option('--dry-run', is_flag=True, help='Show estimate without running')
@click.option('--api-key', envvar='OPENROUTER_API_KEY', help='OpenRouter API key')
def run(preset, prompts, models, judges, votes, occupations, industries, seed, output, dry_run, api_key):
    """Run an evaluation."""

    # Load configuration
    if preset:
        config = load_preset(preset)
    else:
        config = EvalConfig()

    # Override with CLI options
    if prompts:
        config.num_prompts = prompts
    if models:
        config.model_pairs = parse_models(models)
    if judges:
        config.judge_models = judges.split(',')
    if votes:
        config.votes_per_judge = votes
    if seed:
        config.random_seed = seed

    # Set output directory
    if not output:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output = Path(f'results/eval_{timestamp}')

    config.output_dir = output

    # Show cost estimate
    estimate = estimate_cost(config)
    display_estimate(estimate)

    if dry_run:
        return

    # Confirm
    if not click.confirm('Proceed with evaluation?'):
        return

    # Run evaluation
    asyncio.run(run_evaluation(config, api_key))

@cli.command()
@click.argument('results_dir', type=Path)
def view(results_dir):
    """View results in interactive TUI."""
    db_path = results_dir / 'results.db'
    if not db_path.exists():
        click.echo(f"No results found at {db_path}")
        return

    app = ResultsViewer(db_path)
    app.run()

@cli.command()
@click.argument('results_dir', type=Path)
def report(results_dir):
    """Generate PDF report from results."""
    generator = PDFReportGenerator(results_dir)
    output_path = generator.generate()
    click.echo(f"Report generated: {output_path}")

@cli.command()
@click.argument('results_dir', type=Path)
def resume(results_dir):
    """Resume an interrupted evaluation."""
    config_path = results_dir / 'config.json'
    if not config_path.exists():
        click.echo(f"No config found at {config_path}")
        return

    # Load config and resume
    asyncio.run(resume_evaluation(results_dir))

def display_estimate(estimate: dict):
    """Display cost and time estimate."""
    click.echo("""
╭─────────────────────────────────────────────────────────────╮
│                    EVAL RUN ESTIMATE                        │
├─────────────────────────────────────────────────────────────┤""")
    click.echo(f"│ Prompts:              {estimate['prompts']:,}".ljust(61) + "│")
    click.echo(f"│ Model pairs:          {estimate['model_pairs']}".ljust(61) + "│")
    click.echo(f"│ Total comparisons:    {estimate['total_comparisons']:,}".ljust(61) + "│")
    click.echo("│                                                             │")
    click.echo(f"│ Judge config:         {estimate['judge_config']}".ljust(61) + "│")
    click.echo(f"│ Total judge calls:    {estimate['total_judge_calls']:,}".ljust(61) + "│")
    click.echo("│                                                             │")
    click.echo("│ ESTIMATED COST                                              │")
    click.echo(f"│   Response generation:  ${estimate['response_cost_low']:.0f} - ${estimate['response_cost_high']:.0f}".ljust(61) + "│")
    click.echo(f"│   Judging:              ${estimate['judge_cost_low']:.0f} - ${estimate['judge_cost_high']:.0f}".ljust(61) + "│")
    click.echo(f"│   Total:                ${estimate['total_cost_low']:.0f} - ${estimate['total_cost_high']:.0f}".ljust(61) + "│")
    click.echo("│                                                             │")
    click.echo("│ ESTIMATED TIME                                              │")
    click.echo(f"│   With rate limits:     {estimate['time_with_limits']}".ljust(61) + "│")
    click.echo(f"│   Parallelized:         {estimate['time_parallel']}".ljust(61) + "│")
    click.echo("╰─────────────────────────────────────────────────────────────╯")

async def run_evaluation(config: EvalConfig, api_key: str):
    """Execute the evaluation."""
    # Initialize client
    client = OpenRouterClient(api_key)

    # Generate prompts
    onet_loader = OnetLoader()
    generator = PromptGenerator(onet_loader, client, config.random_seed)
    prompts = await generator.generate_prompts(config.num_prompts)

    config.prompts = prompts

    # Create runner
    runner = EvalRunner(config, client)

    # Run with progress dashboard
    app = ProgressDashboard(config)

    async def run_with_progress():
        def progress_callback(idx, total, result):
            app.update_progress(idx, result)

        runner.progress_callback = progress_callback
        await runner.run()

    # Run app and evaluation together
    await asyncio.gather(
        app.run_async(),
        run_with_progress()
    )

    await client.close()

if __name__ == '__main__':
    cli()
```

### 7.2 Preset Configurations

```yaml
# config/presets.yaml

presets:
  1:
    name: "Sanity Check"
    prompts: 5
    model_pairs: 1
    judge_models: ["claude-opus-4.5"]
    votes_per_judge: 1
    use_both_personas: false
    estimated_cost: 1
    estimated_time: "2 min"

  2:
    name: "Smoke Test"
    prompts: 20
    model_pairs: 1
    judge_models: ["claude-opus-4.5"]
    votes_per_judge: 3
    use_both_personas: false
    estimated_cost: 5
    estimated_time: "5 min"

  3:
    name: "Dev Iteration"
    prompts: 50
    model_pairs: 2
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking"]
    votes_per_judge: 3
    use_both_personas: true
    estimated_cost: 25
    estimated_time: "15 min"

  4:
    name: "Quick Sample"
    prompts: 100
    model_pairs: 2
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking"]
    votes_per_judge: 5
    use_both_personas: true
    estimated_cost: 75
    estimated_time: "30 min"

  5:
    name: "Light Eval"
    prompts: 200
    model_pairs: 3
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
    votes_per_judge: 3
    use_both_personas: true
    estimated_cost: 150
    estimated_time: "1 hr"

  6:
    name: "Standard Eval"
    prompts: 500
    model_pairs: 4
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
    votes_per_judge: 5
    use_both_personas: true
    estimated_cost: 500
    estimated_time: "3 hrs"

  7:
    name: "Thorough Eval"
    prompts: 1000
    model_pairs: 4
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
    votes_per_judge: 5
    use_both_personas: true
    estimated_cost: 1000
    estimated_time: "6 hrs"

  8:
    name: "Comprehensive"
    prompts: 2000
    model_pairs: "all"
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
    votes_per_judge: 5
    use_both_personas: true
    estimated_cost: 2500
    estimated_time: "12 hrs"

  9:
    name: "Deep Dive"
    prompts: 5000
    model_pairs: "all"
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
    votes_per_judge: 5
    use_both_personas: true
    estimated_cost: 6000
    estimated_time: "24 hrs"

  10:
    name: "Full Kaboodle"
    prompts: 10000
    model_pairs: "all"
    judge_models: ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]
    votes_per_judge: 5
    use_both_personas: true
    estimated_cost: 12000
    estimated_time: "48 hrs"
```

---

## Part 8: PDF Report Generation

### 8.1 Report Generator

```python
# src/reporting/pdf_generator.py

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

from weasyprint import HTML, CSS
import plotly.graph_objects as go
import plotly.express as px
from jinja2 import Environment, FileSystemLoader

from ..analysis.statistics import StatisticalAnalyzer
from ..analysis.bias_detection import BiasDetector
from ..analysis.weakness_finder import WeaknessFinder

@dataclass
class ReportSection:
    title: str
    content: str
    charts: List[str]  # Base64 encoded images

class PDFReportGenerator:
    """Generate comprehensive PDF analyst reports."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.db_path = results_dir / "results.db"
        self.config = self._load_config()

        self.analyzer = StatisticalAnalyzer(self.db_path)
        self.bias_detector = BiasDetector(self.db_path)
        self.weakness_finder = WeaknessFinder(self.db_path, self.db_path)

        self.env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))

    def _load_config(self) -> Dict:
        """Load evaluation configuration."""
        config_path = self.results_dir / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {}

    def generate(self) -> Path:
        """Generate the full PDF report."""
        # Collect all data
        overall_stats = self.analyzer.compute_overall_stats()
        biases = self.bias_detector.detect_all_biases()
        weaknesses = self.weakness_finder.find_all_weaknesses()

        # Generate charts
        charts = self._generate_all_charts(overall_stats)

        # Render HTML
        template = self.env.get_template("report.html")
        html_content = template.render(
            title="Gemini Writing Evaluation Report",
            generated_at=datetime.now().isoformat(),
            config=self.config,
            overall_stats=overall_stats,
            biases=biases,
            weaknesses=weaknesses,
            charts=charts,
            executive_summary=self._generate_executive_summary(overall_stats, weaknesses),
        )

        # Convert to PDF
        output_path = self.results_dir / "reports" / "report.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=html_content).write_pdf(
            output_path,
            stylesheets=[CSS(Path(__file__).parent / "templates" / "report.css")]
        )

        return output_path

    def _generate_all_charts(self, stats: Dict) -> Dict[str, str]:
        """Generate all visualization charts."""
        charts = {}

        # Win rate bar chart
        charts['win_rates'] = self._create_win_rate_chart(stats)

        # Confidence interval chart
        charts['confidence_intervals'] = self._create_ci_chart(stats)

        # Heatmap by dimension
        charts['occupation_heatmap'] = self._create_occupation_heatmap()

        # Judge agreement chart
        charts['judge_agreement'] = self._create_agreement_chart()

        return charts

    def _create_win_rate_chart(self, stats: Dict) -> str:
        """Create win rate comparison bar chart."""
        models = list(stats.keys())
        gemini_rates = [s.gemini_win_rate.win_rate for s in stats.values()]
        competitor_rates = [s.competitor_win_rate.win_rate for s in stats.values()]

        fig = go.Figure(data=[
            go.Bar(name='Gemini', x=models, y=gemini_rates, marker_color='#4285F4'),
            go.Bar(name='Competitor', x=models, y=competitor_rates, marker_color='#EA4335')
        ])

        fig.update_layout(
            title='Win Rates by Model Pair',
            yaxis_title='Win Rate',
            barmode='group',
            yaxis_range=[0, 1]
        )

        return self._fig_to_base64(fig)

    def _create_ci_chart(self, stats: Dict) -> str:
        """Create confidence interval chart."""
        models = list(stats.keys())
        rates = [s.gemini_win_rate.win_rate for s in stats.values()]
        lower = [s.gemini_win_rate.lower_bound for s in stats.values()]
        upper = [s.gemini_win_rate.upper_bound for s in stats.values()]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=models, y=rates,
            error_y=dict(
                type='data',
                symmetric=False,
                array=[u - r for r, u in zip(rates, upper)],
                arrayminus=[r - l for r, l in zip(rates, lower)]
            ),
            mode='markers',
            marker=dict(size=12, color='#4285F4'),
            name='Gemini Win Rate'
        ))

        fig.add_hline(y=0.5, line_dash="dash", line_color="gray", annotation_text="50%")

        fig.update_layout(
            title='Win Rates with 95% Confidence Intervals',
            yaxis_title='Win Rate',
            yaxis_range=[0, 1]
        )

        return self._fig_to_base64(fig)

    def _create_occupation_heatmap(self) -> str:
        """Create heatmap of win rates by occupation."""
        # Would query database and create heatmap
        fig = go.Figure()
        # ... implementation
        return self._fig_to_base64(fig)

    def _create_agreement_chart(self) -> str:
        """Create inter-judge agreement visualization."""
        fig = go.Figure()
        # ... implementation
        return self._fig_to_base64(fig)

    def _fig_to_base64(self, fig: go.Figure) -> str:
        """Convert plotly figure to base64 encoded image."""
        import base64
        img_bytes = fig.to_image(format="png", width=800, height=500)
        return base64.b64encode(img_bytes).decode()

    def _generate_executive_summary(
        self,
        stats: Dict,
        weaknesses: List
    ) -> str:
        """Generate executive summary text."""
        lines = []

        # Overall performance
        avg_win_rate = sum(s.gemini_win_rate.win_rate for s in stats.values()) / len(stats)
        lines.append(f"**Overall Performance**: Gemini achieved an average win rate of {avg_win_rate:.1%} across all comparisons.")

        # Top weaknesses
        if weaknesses:
            critical = [w for w in weaknesses if w.severity == 'critical']
            if critical:
                lines.append(f"\n**Critical Weaknesses Identified**: {len(critical)} areas require immediate attention:")
                for w in critical[:3]:
                    lines.append(f"  - {w.dimension}={w.value}: {w.gemini_win_rate:.1%} win rate")

        # Recommendations
        lines.append("\n**Key Recommendations**:")
        lines.append("  1. Focus improvement efforts on identified weak areas")
        lines.append("  2. Investigate low-agreement comparisons for potential eval issues")
        lines.append("  3. Consider additional evaluation on sensitive topics")

        return "\n".join(lines)
```

### 8.2 Report HTML Template

```html
<!-- src/reporting/templates/report.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
    <style>
        @page { size: A4; margin: 2cm; }
        body { font-family: 'Helvetica Neue', sans-serif; line-height: 1.6; }
        h1 { color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }
        h2 { color: #202124; margin-top: 30px; }
        .chart { width: 100%; max-width: 700px; margin: 20px auto; }
        .stat-box { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; }
        .weakness-critical { background: #fce8e6; border-left: 4px solid #ea4335; }
        .weakness-significant { background: #fef7e0; border-left: 4px solid #fbbc04; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
    </style>
</head>
<body>
    <h1>{{ title }}</h1>
    <p class="meta">Generated: {{ generated_at }} | Prompts: {{ config.num_prompts }} | Model Pairs: {{ config.model_pairs|length }}</p>

    <h2>Executive Summary</h2>
    <div class="stat-box">
        {{ executive_summary | safe }}
    </div>

    <h2>Overall Results</h2>
    <div class="chart">
        <img src="data:image/png;base64,{{ charts.win_rates }}" alt="Win Rates">
    </div>

    <table>
        <tr>
            <th>vs Model</th>
            <th>Gemini Wins</th>
            <th>Competitor Wins</th>
            <th>Ties</th>
            <th>Win Rate</th>
            <th>p-value</th>
        </tr>
        {% for model, stat in overall_stats.items() %}
        <tr>
            <td>{{ model }}</td>
            <td>{{ stat.gemini_wins }}</td>
            <td>{{ stat.competitor_wins }}</td>
            <td>{{ stat.ties }}</td>
            <td>{{ "%.1f" | format(stat.gemini_win_rate.win_rate * 100) }}%</td>
            <td>{{ "%.4f" | format(stat.p_value) }}</td>
        </tr>
        {% endfor %}
    </table>

    <h2>Statistical Confidence</h2>
    <div class="chart">
        <img src="data:image/png;base64,{{ charts.confidence_intervals }}" alt="Confidence Intervals">
    </div>

    <h2>Identified Weaknesses</h2>
    {% for weakness in weaknesses %}
    <div class="stat-box weakness-{{ weakness.severity }}">
        <strong>{{ weakness.dimension }}</strong>: {{ weakness.value }}<br>
        Win Rate: {{ "%.1f" | format(weakness.gemini_win_rate * 100) }}% (n={{ weakness.sample_size }})<br>
        Severity: {{ weakness.severity | upper }}
    </div>
    {% endfor %}

    <h2>Bias Analysis</h2>
    {% for bias in biases %}
    <div class="stat-box">
        <strong>{{ bias.bias_type | replace('_', ' ') | title }}</strong><br>
        {{ bias.description }}<br>
        Severity: {{ bias.severity | upper }} (p={{ "%.4f" | format(bias.statistical_significance) }})
    </div>
    {% endfor %}

    <h2>Performance by Occupation Group</h2>
    <div class="chart">
        <img src="data:image/png;base64,{{ charts.occupation_heatmap }}" alt="Occupation Heatmap">
    </div>

    <h2>Inter-Judge Agreement</h2>
    <div class="chart">
        <img src="data:image/png;base64,{{ charts.judge_agreement }}" alt="Judge Agreement">
    </div>

    <footer>
        <p>Gemini Writing Evaluation Framework | Confidential Research Document</p>
    </footer>
</body>
</html>
```

---

## Part 9: Robustness Requirements Implementation

### 9.1 Comprehensive Robustness Checklist

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| **Pairwise comparisons** | `EvalRunner` always compares Gemini vs one competitor | Unit test |
| **Best-of-5 judgments** | `JudgePanel.votes_per_judge = 5` | Config validation |
| **Majority-of-majorities** | `VoteAggregator.aggregate()` | Unit test with edge cases |
| **Position shuffling** | `EvalRunner._judge_comparison()` uses deterministic RNG | Verify distribution in logs |
| **Deterministic shuffling** | Seed from `hash((prompt_id, competitor_model))` | Reproducibility test |
| **Position bias detection** | `BiasDetector.detect_position_bias()` | Include in every report |
| **Inter-judge agreement** | Cohen's Kappa in `StatisticalAnalyzer` | Report threshold warnings |
| **Confidence intervals** | Wilson score intervals in `WinRateStats` | Verify bounds in tests |
| **Statistical significance** | Binomial test p-values | Report all p-values |
| **Automatic retries** | `@retry` decorator with exponential backoff | Integration test |
| **Rate limit handling** | `RateLimitError` caught and retried | Mock test |
| **Timeout handling** | `httpx.Timeout` configuration | Integration test |
| **Checkpoint/resume** | `CheckpointManager` saves after each result | Interrupt/resume test |
| **Failure logging** | `failures.log` in results directory | Verify logging |
| **Auto-loss on refusal** | `_handle_failure()` in `EvalRunner` | Unit test |
| **Refusal categorization** | `RefusalCategory` enum and tracking | Include in report |

### 9.2 Error Handling Flow

```python
# src/eval/error_handling.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ErrorCategory(Enum):
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    REFUSAL = "refusal"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"

class RefusalCategory(Enum):
    SAFETY = "safety"           # Model cites safety/policy
    CAPABILITY = "capability"   # Model says can't do task
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE = "incomplete"
    OFF_TOPIC = "off_topic"

@dataclass
class EvalError:
    category: ErrorCategory
    message: str
    model: str
    prompt_id: str
    timestamp: str
    refusal_category: Optional[RefusalCategory] = None
    retry_count: int = 0
    recovered: bool = False

class ErrorHandler:
    """Centralized error handling and logging."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.errors: List[EvalError] = []

    def log_error(self, error: EvalError):
        """Log an error to file and memory."""
        self.errors.append(error)

        with open(self.log_path, 'a') as f:
            f.write(f"{error.timestamp} | {error.category.value} | {error.model} | {error.prompt_id} | {error.message}\n")

    def classify_refusal(self, response_content: str) -> Optional[RefusalCategory]:
        """Classify why a model refused."""
        content_lower = response_content.lower()

        if any(kw in content_lower for kw in ['policy', 'safety', 'cannot assist', 'inappropriate']):
            return RefusalCategory.SAFETY
        elif any(kw in content_lower for kw in ["can't", "cannot", "unable to", "don't have"]):
            return RefusalCategory.CAPABILITY
        elif len(response_content) < 50:
            return RefusalCategory.INCOMPLETE

        return None

    def get_summary(self) -> Dict:
        """Get error summary statistics."""
        from collections import Counter
        categories = Counter(e.category for e in self.errors)
        recovered = sum(1 for e in self.errors if e.recovered)

        return {
            'total_errors': len(self.errors),
            'by_category': dict(categories),
            'recovered': recovered,
            'unrecovered': len(self.errors) - recovered
        }
```

---

## Part 10: Implementation Roadmap

### Phase 1: Foundation (Week 1)
1. Set up project structure and dependencies
2. Implement `OnetLoader` with database queries
3. Implement `NAICSMapper` and `CompanyDatabase`
4. Implement `NameGenerator`
5. Create Pydantic schemas for all data models
6. Write unit tests for data layer

### Phase 2: Prompt Generation (Week 2)
1. Implement Phase 1 LLM persona generation
2. Implement Phase 2 algorithmic combination
3. Implement Phase 3 LLM enrichment
4. Create `PromptGenerator` orchestrator
5. Test prompt diversity and quality
6. Generate sample prompt sets for validation

### Phase 3: Evaluation Core (Week 3)
1. Implement `OpenRouterClient` with retry logic
2. Implement `JudgePanel` with dual personas
3. Implement `VoteAggregator` with majority-of-majorities
4. Implement `CheckpointManager`
5. Implement `EvalRunner` orchestrator
6. Integration tests with mock API

### Phase 4: Analysis & Reporting (Week 4)
1. Implement `StatisticalAnalyzer`
2. Implement `BiasDetector`
3. Implement `WeaknessFinder`
4. Create visualization functions
5. Implement `PDFReportGenerator`
6. Design and test report templates

### Phase 5: TUI & CLI (Week 5)
1. Implement `ProgressDashboard`
2. Implement `ResultsViewer`
3. Create CLI with click
4. Implement preset configurations
5. Add cost estimation
6. End-to-end testing

### Phase 6: Polish & Documentation (Week 6)
1. Comprehensive testing with real API calls
2. Performance optimization
3. Documentation
4. Example runs and validation
5. Bug fixes and refinements

---

## Appendix A: Dependencies

```toml
# pyproject.toml

[project]
name = "gemini-writing-eval"
version = "1.0.0"
description = "Gemini Writing Evaluation Framework"
requires-python = ">=3.11"

dependencies = [
    "httpx>=0.25.0",
    "pydantic>=2.5.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "textual>=0.40.0",
    "plotly>=5.18.0",
    "pandas>=2.1.0",
    "scipy>=1.11.0",
    "numpy>=1.26.0",
    "weasyprint>=60.0",
    "jinja2>=3.1.0",
    "pyyaml>=6.0",
    "tenacity>=8.2.0",
    "kaleido>=0.2.0",  # For plotly image export
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
eval = "gemini_writing_eval.cli:cli"
```

---

## Appendix B: Sample Prompt Output

```json
{
  "prompt_id": "prompt_8472615938",
  "onet_task_id": "T123456",
  "onet_task_text": "Correspond with customers to answer questions or resolve complaints",
  "occupation_code": "43-4051.00",
  "occupation_title": "Customer Service Representatives",
  "job_zone": 2,
  "soc_major_group": "43",
  "writing_category": "customer_communication",
  "naics_code": "52",
  "naics_title": "Finance and Insurance",
  "writer": {
    "name": "Maria Santos",
    "email": "maria.santos@ally.com",
    "job_title": "Senior Customer Service Representative",
    "company": "Ally Financial",
    "company_size": "enterprise",
    "industry": "Finance and Insurance",
    "age_range": "28-35",
    "generation": "millennial",
    "skill_level": "mid",
    "english_variant": "en-US"
  },
  "primary_recipient": {
    "name": "Robert Chen",
    "email": "robert.chen@gmail.com",
    "job_title": "Customer",
    "company": null,
    "relationship_to_writer": "customer with escalated complaint",
    "english_variant": "en-US",
    "is_native_english": true
  },
  "formality": "neutral",
  "urgency": "moderate",
  "relationship_context": "established",
  "audience_size": "one_on_one",
  "emotional_context": "conflict",
  "message_position": "reply",
  "channel": "email",
  "temporal_context": "It's January 6, 2026. The customer has been waiting 5 business days for a resolution.",
  "competing_objectives": [
    "Maintain professional tone while acknowledging frustration",
    "Explain policy limitations while showing empathy",
    "Resolve the immediate issue while preventing future escalations"
  ],
  "attached_context": [],
  "prior_message": "This is unacceptable! I've been a customer for 8 years and this is how you treat me? The $75 fee should never have been charged in the first place. I want this resolved TODAY or I'm taking my business elsewhere and posting about this experience everywhere.",
  "explicit_constraints": [],
  "is_sensitive": false,
  "sensitive_categories": [],
  "prompt_text": "You are Maria Santos, Senior Customer Service Representative at Ally Financial (enterprise, Finance and Insurance).\n\nIt's January 6, 2026. The customer has been waiting 5 business days for a resolution.\n\nYour task: Correspond with customers to answer questions or resolve complaints\n\nRecipient: Robert Chen, Customer\nRelationship: customer with escalated complaint\nCommunication channel: email\n\n--- PRIOR MESSAGE FROM CUSTOMER ---\nThis is unacceptable! I've been a customer for 8 years and this is how you treat me? The $75 fee should never have been charged in the first place. I want this resolved TODAY or I'm taking my business elsewhere and posting about this experience everywhere.\n--- END PRIOR MESSAGE ---\n\nNavigate these competing objectives:\n- Maintain professional tone while acknowledging frustration\n- Explain policy limitations while showing empathy\n- Resolve the immediate issue while preventing future escalations\n\nWrite the email now. Be authentic to your role and relationship with the recipient.",
  "language": "en",
  "language_variant": "en-US",
  "generation_seed": 8472615938,
  "generation_phase": "phase3"
}
```

---

This implementation plan provides a comprehensive blueprint for building the Gemini Writing Evaluation Framework. The modular architecture allows for incremental development and testing, while the robust error handling and checkpoint system ensure reliable operation at scale. The three-phase prompt generation methodology ensures diverse, realistic writing tasks that comprehensively cover the US economy's writing needs as captured in O*NET.
