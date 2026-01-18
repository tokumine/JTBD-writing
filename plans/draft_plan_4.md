# Gemini Writing Evaluation Framework - Implementation Plan (Draft 4)

## Executive Summary

This implementation plan details the architecture and methodology for a comprehensive writing evaluation framework that compares Gemini 3.0 Pro and 3.0 Flash against competing frontier LLMs on realistic professional writing tasks derived from the O*NET database. The system leverages OpenRouter API for unified model access, employs a rigorous multi-judge evaluation methodology, and provides extensive visualization and analysis capabilities.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Gemini Writing Evaluation Framework                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   CLI/TUI    │  │    Config    │  │   Prompt     │  │  Evaluation  │    │
│  │   Interface  │  │   Manager    │  │   Generator  │  │    Engine    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ┌──────┴─────────────────┴─────────────────┴─────────────────┴───────┐    │
│  │                       Core Orchestrator                             │    │
│  └──────┬─────────────────┬─────────────────┬─────────────────┬───────┘    │
│         │                 │                 │                 │             │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐    │
│  │  OpenRouter  │  │    O*NET     │  │    Judge     │  │   Results    │    │
│  │    Client    │  │   Database   │  │   Manager    │  │   Storage    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Analysis & Reporting Layer                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ Statistics  │  │   Charts    │  │    PDF      │  │    Bias     │  │   │
│  │  │   Engine    │  │  Generator  │  │   Report    │  │  Detection  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async support, rich ecosystem |
| Async HTTP | httpx | Modern async client with retry support |
| Data Validation | Pydantic v2 | Type-safe schemas, JSON serialization |
| Database | SQLite | Simple, portable, no server required |
| TUI Framework | textual/rich | Modern terminal UI capabilities |
| Visualization | plotly | Interactive charts for analysis |
| PDF Generation | reportlab + weasyprint | Professional report output |
| CLI | click | Robust command-line interface |
| Configuration | TOML + pydantic-settings | Type-safe configuration |

### 1.3 Project Structure

```
gemini-writing-eval/
├── pyproject.toml              # Project configuration, dependencies
├── README.md                   # Project documentation
├── .env.example                # Environment variable template
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # Configuration management
│   │   ├── presets.py          # 10 evaluation presets
│   │   └── cost_estimator.py   # Cost/time estimation
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py   # O*NET database interface
│   │   ├── naics_mapper.py     # Industry code mapping
│   │   ├── company_database.py # Real company name database
│   │   └── name_generator.py   # Realistic name generation
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py        # Three-phase prompt generation
│   │   ├── enricher.py         # LLM enrichment layer
│   │   ├── schemas.py          # Prompt data models
│   │   └── templates.py        # Prompt templates
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py # OpenRouter API wrapper
│   │   ├── rate_limiter.py     # Rate limiting logic
│   │   ├── retry_handler.py    # Exponential backoff
│   │   └── models.py           # Model configuration
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py           # Core evaluation orchestrator
│   │   ├── judge.py            # Judge persona implementation
│   │   ├── comparator.py       # Pairwise comparison logic
│   │   ├── aggregator.py       # Vote aggregation
│   │   └── schemas.py          # Evaluation data models
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite interface
│   │   ├── checkpoint.py       # Resume/checkpoint logic
│   │   └── exporter.py         # CSV/JSON export
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py       # Statistical analysis
│   │   ├── bias_detector.py    # Systematic bias detection
│   │   └── weakness_finder.py  # Weakness identification
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py              # Main TUI application
│   │   ├── progress.py         # Progress dashboard
│   │   ├── viewer.py           # Results viewer
│   │   └── widgets.py          # Custom UI components
│   │
│   └── reports/
│       ├── __init__.py
│       ├── pdf_generator.py    # PDF report creation
│       ├── charts.py           # Visualization generation
│       └── templates/          # Report templates
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
    ├── test_prompts.py
    ├── test_eval.py
    ├── test_api.py
    └── test_analysis.py
```

---

## 2. Data Layer Implementation

### 2.1 O*NET Database Interface

The O*NET database (v30.1) contains 18,796 task statements across 1,016 occupations. The data layer must efficiently extract and categorize writing-relevant tasks.

#### 2.1.1 Task Extraction Strategy

```python
# src/data/onet_extractor.py
from dataclasses import dataclass
from typing import List, Optional
import sqlite3

@dataclass
class ONetTask:
    task_id: str
    onetsoc_code: str
    occupation_title: str
    occupation_description: str
    task: str
    task_type: str  # Core, Supplemental, or None
    job_zone: int   # 1-5 skill level
    writing_category: str  # Inferred category
    email_frequency: Optional[float]
    correspondence_frequency: Optional[float]
    writing_skill_importance: Optional[float]

class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database."""

    WRITING_CATEGORIES = {
        'explicit_writing': [
            '%write%', '%draft%', '%document%',
            '%prepare report%', '%prepare%proposal%', '%compose%'
        ],
        'correspondence': [
            '%correspond%', '%email%', '%letter%',
            '%memo%', '%notify%customer%', '%inform%customer%'
        ],
        'reports_analysis': [
            '%report%', '%present%finding%', '%present%result%',
            '%summarize%', '%prepare%presentation%'
        ],
        'persuasion_negotiation': [
            '%negotiat%', '%propos%', '%persuad%',
            '%recommend%', '%advise%client%', '%advise%customer%'
        ],
        'policy_procedure': [
            '%develop%polic%', '%implement%polic%', '%write%procedure%',
            '%prepare%guideline%', '%establish%standard%'
        ],
        'customer_communication': [
            '%customer%question%', '%client%question%', '%answer%question%',
            '%resolve%complaint%', '%explain%to%customer%'
        ],
        'instructional': [
            '%train%staff%', '%train%employee%', '%instruct%',
            '%develop%curriculum%', '%prepare%manual%'
        ],
        'internal_coordination': [
            '%confer with%', '%coordinate with%', '%collaborate with%',
            '%meet with%', '%communicate with%management%'
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

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def extract_writing_tasks(self) -> List[ONetTask]:
        """Extract all writing-relevant tasks with full context."""
        tasks = []

        for category, patterns in self.WRITING_CATEGORIES.items():
            where_clauses = ' OR '.join([f"t.task LIKE '{p}'" for p in patterns])

            query = f"""
                SELECT DISTINCT
                    t.task_id,
                    t.onetsoc_code,
                    o.title as occupation_title,
                    o.description as occupation_description,
                    t.task,
                    t.task_type,
                    jz.job_zone,
                    wc_email.data_value as email_freq,
                    wc_letter.data_value as letter_freq,
                    sk.data_value as writing_skill
                FROM task_statements t
                JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
                LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
                LEFT JOIN work_context wc_email
                    ON t.onetsoc_code = wc_email.onetsoc_code
                    AND wc_email.element_id = '4.C.1.a.2.h'
                    AND wc_email.scale_id = 'CX'
                LEFT JOIN work_context wc_letter
                    ON t.onetsoc_code = wc_letter.onetsoc_code
                    AND wc_letter.element_id = '4.C.1.a.2.j'
                    AND wc_letter.scale_id = 'CX'
                LEFT JOIN skills sk
                    ON t.onetsoc_code = sk.onetsoc_code
                    AND sk.element_id = '2.A.1.c'
                    AND sk.scale_id = 'IM'
                WHERE {where_clauses}
            """

            cursor = self.conn.execute(query)
            for row in cursor:
                tasks.append(ONetTask(
                    task_id=row['task_id'],
                    onetsoc_code=row['onetsoc_code'],
                    occupation_title=row['occupation_title'],
                    occupation_description=row['occupation_description'],
                    task=row['task'],
                    task_type=row['task_type'] or 'Unknown',
                    job_zone=row['job_zone'] or 3,
                    writing_category=category,
                    email_frequency=row['email_freq'],
                    correspondence_frequency=row['letter_freq'],
                    writing_skill_importance=row['writing_skill']
                ))

        return tasks

    def get_soc_major_group(self, onetsoc_code: str) -> str:
        """Get the SOC major group (2-digit code) for an occupation."""
        soc_major = onetsoc_code[:2]
        soc_groups = {
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
        return soc_groups.get(soc_major, 'Unknown')
```

### 2.2 NAICS Industry Mapping

Since O*NET doesn't contain NAICS codes directly, we implement a mapping layer using BLS occupation-industry crosswalk data and built-in knowledge.

```python
# src/data/naics_mapper.py
from dataclasses import dataclass
from typing import List, Dict
import random

@dataclass
class NAICSIndustry:
    code: str
    title: str
    sector: str

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
    '56': 'Administrative and Support and Waste Management',
    '61': 'Educational Services',
    '62': 'Health Care and Social Assistance',
    '71': 'Arts, Entertainment, and Recreation',
    '72': 'Accommodation and Food Services',
    '81': 'Other Services (except Public Administration)',
    '92': 'Public Administration'
}

class NAICSMapper:
    """Map occupations to NAICS industries for diversity sampling."""

    def __init__(self):
        self.occupation_industry_map = self._build_occupation_industry_map()

    def _build_occupation_industry_map(self) -> Dict[str, List[str]]:
        """Build mapping from SOC major groups to typical NAICS sectors."""
        # Based on BLS occupation-industry relationships
        return {
            '11': ['52', '54', '55', '62', '92'],  # Management
            '13': ['52', '54', '55', '56'],        # Business/Financial
            '15': ['51', '54', '52'],              # Computer/Math
            '17': ['23', '31-33', '54'],           # Engineering
            '19': ['54', '61', '62'],              # Science
            '21': ['62', '92', '81'],              # Community/Social
            '23': ['54', '92'],                    # Legal
            '25': ['61'],                          # Education
            '27': ['51', '71', '54'],              # Arts/Media
            '29': ['62'],                          # Healthcare Practitioners
            '31': ['62'],                          # Healthcare Support
            '33': ['92'],                          # Protective Service
            '35': ['72'],                          # Food Service
            '37': ['56', '72'],                    # Building/Grounds
            '39': ['62', '71', '72', '81'],        # Personal Care
            '41': ['44-45', '52', '53'],           # Sales
            '43': ['52', '54', '56', '92'],        # Office/Admin
            '45': ['11'],                          # Farming/Fishing
            '47': ['23', '21'],                    # Construction
            '49': ['23', '31-33', '48-49'],        # Maintenance
            '51': ['31-33'],                       # Production
            '53': ['48-49', '42'],                 # Transportation
            '55': ['92']                           # Military
        }

    def get_industries_for_occupation(self, onetsoc_code: str) -> List[NAICSIndustry]:
        """Get applicable NAICS industries for an occupation."""
        soc_major = onetsoc_code[:2]
        naics_codes = self.occupation_industry_map.get(soc_major, ['54'])

        industries = []
        for code in naics_codes:
            industries.append(NAICSIndustry(
                code=code,
                title=NAICS_SECTORS.get(code, 'Unknown'),
                sector=code[:2]
            ))
        return industries

    def sample_industry(self, onetsoc_code: str, seed: int) -> NAICSIndustry:
        """Sample a single industry for an occupation deterministically."""
        random.seed(seed)
        industries = self.get_industries_for_occupation(onetsoc_code)
        return random.choice(industries)
```

### 2.3 Real Company Database

The framework uses real company names for realism. This component manages a curated database of companies across sizes and industries.

```python
# src/data/company_database.py
from dataclasses import dataclass
from typing import List, Dict, Optional
import random
from enum import Enum

class CompanySize(Enum):
    FORTUNE_500 = "fortune_500"
    MID_MARKET = "mid_market"      # 500-5000 employees
    SMALL_BUSINESS = "small_business"  # 50-500 employees
    STARTUP = "startup"             # <50 employees

@dataclass
class Company:
    name: str
    size: CompanySize
    industry_naics: str
    hq_location: str
    founded_year: Optional[int]
    public: bool
    employee_count_range: str
    description: str

class CompanyDatabase:
    """Database of real companies for prompt grounding."""

    def __init__(self):
        self.companies = self._load_companies()
        self.by_industry: Dict[str, List[Company]] = {}
        self.by_size: Dict[CompanySize, List[Company]] = {}
        self._index_companies()

    def _load_companies(self) -> List[Company]:
        """Load curated company database."""
        # This would be loaded from a JSON/CSV file in practice
        # Sample entries shown for structure
        return [
            # Fortune 500 - Technology
            Company("Apple Inc.", CompanySize.FORTUNE_500, "51",
                   "Cupertino, CA", 1976, True, "100,000+",
                   "Consumer electronics and software"),
            Company("Microsoft Corporation", CompanySize.FORTUNE_500, "51",
                   "Redmond, WA", 1975, True, "100,000+",
                   "Software and cloud services"),
            Company("Alphabet Inc.", CompanySize.FORTUNE_500, "51",
                   "Mountain View, CA", 2015, True, "100,000+",
                   "Internet services and advertising"),

            # Fortune 500 - Finance
            Company("JPMorgan Chase & Co.", CompanySize.FORTUNE_500, "52",
                   "New York, NY", 2000, True, "100,000+",
                   "Financial services and banking"),
            Company("Goldman Sachs Group, Inc.", CompanySize.FORTUNE_500, "52",
                   "New York, NY", 1869, True, "40,000+",
                   "Investment banking and financial services"),

            # Fortune 500 - Healthcare
            Company("UnitedHealth Group", CompanySize.FORTUNE_500, "62",
                   "Minnetonka, MN", 1977, True, "100,000+",
                   "Health insurance and services"),
            Company("Johnson & Johnson", CompanySize.FORTUNE_500, "31-33",
                   "New Brunswick, NJ", 1886, True, "100,000+",
                   "Pharmaceuticals and medical devices"),

            # Mid-market companies
            Company("Zoom Video Communications", CompanySize.MID_MARKET, "51",
                   "San Jose, CA", 2011, True, "5,000-10,000",
                   "Video communications platform"),
            Company("DocuSign, Inc.", CompanySize.MID_MARKET, "51",
                   "San Francisco, CA", 2003, True, "5,000-10,000",
                   "Electronic signature software"),

            # Small businesses
            Company("Basecamp", CompanySize.SMALL_BUSINESS, "51",
                   "Chicago, IL", 1999, False, "50-100",
                   "Project management software"),
            Company("Mailchimp", CompanySize.SMALL_BUSINESS, "51",
                   "Atlanta, GA", 2001, False, "100-500",
                   "Email marketing platform"),

            # Startups
            Company("Notion Labs", CompanySize.STARTUP, "51",
                   "San Francisco, CA", 2016, False, "200-500",
                   "Productivity and note-taking software"),
            Company("Linear", CompanySize.STARTUP, "51",
                   "San Francisco, CA", 2019, False, "<50",
                   "Issue tracking software"),

            # Add many more across industries...
        ]

    def _index_companies(self):
        """Build indexes for efficient lookup."""
        for company in self.companies:
            # Index by industry
            if company.industry_naics not in self.by_industry:
                self.by_industry[company.industry_naics] = []
            self.by_industry[company.industry_naics].append(company)

            # Index by size
            if company.size not in self.by_size:
                self.by_size[company.size] = []
            self.by_size[company.size].append(company)

    def get_company(
        self,
        industry_naics: Optional[str] = None,
        size: Optional[CompanySize] = None,
        seed: int = 0
    ) -> Company:
        """Get a company matching criteria, with deterministic selection."""
        random.seed(seed)

        candidates = self.companies

        if industry_naics:
            # Match on sector (first 2 digits)
            sector = industry_naics[:2]
            candidates = [c for c in candidates
                         if c.industry_naics.startswith(sector)]

        if size:
            candidates = [c for c in candidates if c.size == size]

        if not candidates:
            candidates = self.companies  # Fall back to all

        return random.choice(candidates)

    def sample_companies_by_size_distribution(
        self,
        count: int,
        seed: int = 0
    ) -> List[Company]:
        """Sample companies with realistic size distribution."""
        random.seed(seed)

        # Distribution: 10% Fortune 500, 25% mid-market,
        # 40% small business, 25% startup
        distribution = {
            CompanySize.FORTUNE_500: int(count * 0.10),
            CompanySize.MID_MARKET: int(count * 0.25),
            CompanySize.SMALL_BUSINESS: int(count * 0.40),
            CompanySize.STARTUP: int(count * 0.25)
        }

        result = []
        for size, n in distribution.items():
            candidates = self.by_size.get(size, self.companies)
            result.extend(random.choices(candidates, k=n))

        random.shuffle(result)
        return result[:count]
```

### 2.4 Realistic Name Generator

Generate diverse, realistic names for writer and recipient personas.

```python
# src/data/name_generator.py
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import random

class Generation(Enum):
    GEN_Z = "gen_z"           # Born 1997-2012
    MILLENNIAL = "millennial"  # Born 1981-1996
    GEN_X = "gen_x"           # Born 1965-1980
    BOOMER = "boomer"         # Born 1946-1964

class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"

@dataclass
class PersonName:
    first_name: str
    last_name: str
    formal_name: str          # "Dr. Sarah Chen" or "Mr. Williams"
    informal_name: str        # "Sarah" or "Mike"
    full_name: str            # "Sarah Chen" or "Michael T. Williams"
    email_style: str          # "sarah.chen" or "s.chen" or "schen"
    generation: Generation
    gender: Gender
    ethnicity: str

class NameGenerator:
    """Generate diverse, realistic names for personas."""

    # Name pools organized by ethnicity for diversity
    FIRST_NAMES = {
        'east_asian': {
            Gender.FEMALE: ['Wei', 'Mei', 'Lin', 'Yuki', 'Sakura', 'Ji-Young',
                          'Xia', 'Keiko', 'Soo-Min', 'Aiko'],
            Gender.MALE: ['Wei', 'Jun', 'Hiroshi', 'Takeshi', 'Min-Jun',
                         'Kenji', 'Chen', 'Ryu', 'Sung', 'Kazuki'],
        },
        'south_asian': {
            Gender.FEMALE: ['Priya', 'Ananya', 'Deepa', 'Lakshmi', 'Sita',
                          'Nisha', 'Kavita', 'Meera', 'Anjali', 'Sunita'],
            Gender.MALE: ['Raj', 'Vikram', 'Arjun', 'Sanjay', 'Ravi',
                         'Amit', 'Deepak', 'Suresh', 'Naveen', 'Prakash'],
        },
        'hispanic': {
            Gender.FEMALE: ['Maria', 'Sofia', 'Isabella', 'Carmen', 'Elena',
                          'Gabriela', 'Valentina', 'Lucia', 'Ana', 'Rosa'],
            Gender.MALE: ['Carlos', 'Miguel', 'Jose', 'Luis', 'Diego',
                         'Antonio', 'Rafael', 'Roberto', 'Fernando', 'Juan'],
        },
        'african_american': {
            Gender.FEMALE: ['Aaliyah', 'Destiny', 'Jasmine', 'Brianna', 'Keisha',
                          'Tamika', 'Latoya', 'Shanice', 'Ebony', 'Monique'],
            Gender.MALE: ['DeShawn', 'Jamal', 'Terrence', 'Marcus', 'Darnell',
                         'Tyrone', 'Malik', 'Andre', 'Jerome', 'Rashid'],
        },
        'european': {
            Gender.FEMALE: ['Emma', 'Olivia', 'Sarah', 'Jennifer', 'Amanda',
                          'Rebecca', 'Katherine', 'Elizabeth', 'Margaret', 'Patricia'],
            Gender.MALE: ['James', 'Michael', 'William', 'David', 'Robert',
                         'John', 'Thomas', 'Charles', 'Daniel', 'Matthew'],
        },
        'middle_eastern': {
            Gender.FEMALE: ['Fatima', 'Aisha', 'Leila', 'Nadia', 'Zahra',
                          'Maryam', 'Yasmin', 'Samira', 'Hana', 'Dina'],
            Gender.MALE: ['Mohammed', 'Ahmed', 'Ali', 'Omar', 'Hassan',
                         'Khalid', 'Ibrahim', 'Yusuf', 'Tariq', 'Kareem'],
        },
    }

    LAST_NAMES = {
        'east_asian': ['Chen', 'Wang', 'Li', 'Zhang', 'Liu', 'Kim', 'Park',
                      'Lee', 'Tanaka', 'Yamamoto', 'Suzuki', 'Nguyen', 'Tran'],
        'south_asian': ['Patel', 'Sharma', 'Singh', 'Kumar', 'Gupta', 'Shah',
                       'Reddy', 'Rao', 'Desai', 'Mehta', 'Chopra', 'Kapoor'],
        'hispanic': ['Garcia', 'Rodriguez', 'Martinez', 'Lopez', 'Hernandez',
                    'Gonzalez', 'Perez', 'Sanchez', 'Rivera', 'Torres', 'Flores'],
        'african_american': ['Washington', 'Jefferson', 'Jackson', 'Robinson',
                            'Williams', 'Johnson', 'Brown', 'Davis', 'Wilson', 'Taylor'],
        'european': ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones',
                    'Miller', 'Davis', 'Anderson', 'Wilson', 'Thompson', 'Moore'],
        'middle_eastern': ['Al-Rashid', 'Khan', 'Hassan', 'Ibrahim', 'Mansour',
                          'Nasser', 'Farouk', 'Sadiq', 'Hosseini', 'Tehrani'],
    }

    TITLES = {
        'dr': ['Dr.'],
        'mr': ['Mr.'],
        'ms': ['Ms.'],
        'mrs': ['Mrs.'],
    }

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def generate_name(
        self,
        generation: Optional[Generation] = None,
        gender: Optional[Gender] = None,
        ethnicity: Optional[str] = None,
        include_title: bool = False,
        title_probability: float = 0.2
    ) -> PersonName:
        """Generate a realistic name with demographic diversity."""

        # Random selection if not specified
        if ethnicity is None:
            ethnicity = self.rng.choice(list(self.FIRST_NAMES.keys()))
        if gender is None:
            gender = self.rng.choice([Gender.MALE, Gender.FEMALE])
        if generation is None:
            generation = self.rng.choice(list(Generation))

        # Select names
        first_names = self.FIRST_NAMES[ethnicity][gender]
        last_names = self.LAST_NAMES[ethnicity]

        first_name = self.rng.choice(first_names)
        last_name = self.rng.choice(last_names)

        # Build name variants
        full_name = f"{first_name} {last_name}"

        # Formal name (with potential title)
        if include_title and self.rng.random() < title_probability:
            if gender == Gender.MALE:
                title = "Mr."
            else:
                title = self.rng.choice(["Ms.", "Dr."])
            formal_name = f"{title} {last_name}"
        else:
            formal_name = full_name

        # Email style variations
        email_styles = [
            f"{first_name.lower()}.{last_name.lower()}",
            f"{first_name[0].lower()}.{last_name.lower()}",
            f"{first_name.lower()}{last_name[0].lower()}",
            f"{first_name.lower()}_{last_name.lower()}",
        ]
        email_style = self.rng.choice(email_styles)

        return PersonName(
            first_name=first_name,
            last_name=last_name,
            formal_name=formal_name,
            informal_name=first_name,
            full_name=full_name,
            email_style=email_style,
            generation=generation,
            gender=gender,
            ethnicity=ethnicity
        )

    def generate_diverse_names(self, count: int) -> List[PersonName]:
        """Generate a diverse set of names with even distribution."""
        names = []
        ethnicities = list(self.FIRST_NAMES.keys())
        genders = [Gender.MALE, Gender.FEMALE]
        generations = list(Generation)

        for i in range(count):
            ethnicity = ethnicities[i % len(ethnicities)]
            gender = genders[i % len(genders)]
            generation = generations[i % len(generations)]

            names.append(self.generate_name(
                generation=generation,
                gender=gender,
                ethnicity=ethnicity
            ))

        self.rng.shuffle(names)
        return names
```

---

## 3. Prompt Generation System

### 3.1 Three-Phase Generation Methodology

The prompt generation follows a three-phase approach as specified in PROMPT.md.

#### Phase 1: Offline LLM Generation

Pre-generate diverse persona/context variations using the models being evaluated.

#### Phase 2: Algorithmic Combinations

Programmatically combine O*NET tasks with personas, industries, and dimensions.

#### Phase 3: LLM Enrichment

Enrich context-heavy prompts with additional detail and realism.

### 3.2 Prompt Schema Definition

```python
# src/prompts/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

class FormalityLevel(Enum):
    VERY_CASUAL = 1
    CASUAL = 2
    NEUTRAL = 3
    FORMAL = 4
    VERY_FORMAL = 5

class UrgencyLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class RelationshipContext(Enum):
    FIRST_CONTACT = "first_contact"
    NEW_RELATIONSHIP = "new_relationship"
    ESTABLISHED = "established"
    LONG_TERM = "long_term"

class AudienceSize(Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class EmotionalContext(Enum):
    ROUTINE = "routine"
    CELEBRATION = "celebration"
    CRISIS = "crisis"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"

class MessagePosition(Enum):
    INITIAL = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"

class EnglishVariant(Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class WriterPersona(BaseModel):
    """The person writing the communication."""
    name: str
    email: Optional[str] = None
    role: str
    company: str
    company_size: str
    industry: str
    generation: str              # gen_z, millennial, gen_x, boomer
    skill_level: int = Field(ge=1, le=5)  # 1-5 corresponding to job zone
    english_variant: EnglishVariant = EnglishVariant.EN_US
    additional_context: Optional[str] = None

class RecipientPersona(BaseModel):
    """The intended recipient(s) of the communication."""
    name: str
    email: Optional[str] = None
    role: str
    company: Optional[str] = None
    relationship_to_writer: str
    english_variant: EnglishVariant = EnglishVariant.EN_US
    additional_context: Optional[str] = None

class Attachment(BaseModel):
    """Mock attachment or reference content."""
    type: str               # "report", "email", "notes", "resume", etc.
    description: str
    content: str            # Summary or key details

class CompetingObjectives(BaseModel):
    """Tension between goals the writing must navigate."""
    objective_a: str
    objective_b: str
    context: Optional[str] = None

class InstructionConstraint(BaseModel):
    """Explicit instruction to test compliance."""
    constraint_type: str    # "length", "format", "tone", "exclusion"
    instruction: str
    verification_criteria: str

class WritingPrompt(BaseModel):
    """Complete prompt for a writing task."""
    # Identifiers
    prompt_id: str
    version: str = "1.0"

    # O*NET Source
    onet_task_id: str
    onet_task: str
    onetsoc_code: str
    occupation_title: str
    job_zone: int
    writing_category: str

    # Industry/Company Context
    naics_code: str
    industry_name: str
    company: str
    company_size: str
    company_context: Optional[str] = None

    # Personas
    writer: WriterPersona
    recipient: RecipientPersona
    cc_recipients: Optional[List[RecipientPersona]] = None

    # Communication Context
    communication_channel: str     # email, memo, report, slack, etc.
    formality_level: FormalityLevel
    urgency_level: UrgencyLevel
    relationship_context: RelationshipContext
    audience_size: AudienceSize
    emotional_context: EmotionalContext
    message_position: MessagePosition

    # Temporal Context
    current_date: Optional[str] = None
    deadline: Optional[str] = None
    recent_event: Optional[str] = None

    # Content Enhancements
    attachments: Optional[List[Attachment]] = None
    prior_message: Optional[str] = None
    tone_example: Optional[str] = None
    existing_draft: Optional[str] = None    # For revision tasks

    # Competing Objectives
    competing_objectives: Optional[CompetingObjectives] = None

    # Instruction Constraints
    instruction_constraints: Optional[List[InstructionConstraint]] = None

    # Task Characteristics
    is_revision_task: bool = False
    is_ambiguous: bool = False
    is_sensitive: bool = False
    sensitive_category: Optional[str] = None

    # Language
    language: str = "en"
    language_variant: str = "en-US"

    # The actual prompt text
    prompt_text: str

    # Metadata for analysis
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_full_context(self) -> str:
        """Generate full context string for judge evaluation."""
        context_parts = [
            f"Occupation: {self.occupation_title}",
            f"Industry: {self.industry_name}",
            f"Company: {self.company} ({self.company_size})",
            f"Writer: {self.writer.name}, {self.writer.role}",
            f"Recipient: {self.recipient.name}, {self.recipient.role}",
            f"Formality: {self.formality_level.name}",
            f"Urgency: {self.urgency_level.name}",
            f"Channel: {self.communication_channel}",
        ]

        if self.competing_objectives:
            context_parts.append(
                f"Tension: {self.competing_objectives.objective_a} vs "
                f"{self.competing_objectives.objective_b}"
            )

        return "\n".join(context_parts)
```

### 3.3 Prompt Generator Implementation

```python
# src/prompts/generator.py
from typing import List, Optional, Dict, Any
import random
import hashlib
from datetime import datetime, timedelta

from .schemas import (
    WritingPrompt, WriterPersona, RecipientPersona, Attachment,
    CompetingObjectives, InstructionConstraint, FormalityLevel,
    UrgencyLevel, RelationshipContext, AudienceSize, EmotionalContext,
    MessagePosition, EnglishVariant
)
from ..data.onet_extractor import ONetExtractor, ONetTask
from ..data.naics_mapper import NAICSMapper
from ..data.company_database import CompanyDatabase, CompanySize
from ..data.name_generator import NameGenerator, Generation

class PromptGenerator:
    """Three-phase prompt generation system."""

    def __init__(
        self,
        onet_db_path: str,
        seed: int = 42,
        enable_llm_enrichment: bool = True
    ):
        self.onet_extractor = ONetExtractor(onet_db_path)
        self.naics_mapper = NAICSMapper()
        self.company_db = CompanyDatabase()
        self.name_generator = NameGenerator(seed)
        self.rng = random.Random(seed)
        self.seed = seed
        self.enable_llm_enrichment = enable_llm_enrichment

    def generate_prompts(
        self,
        count: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[WritingPrompt]:
        """Generate prompts using three-phase methodology."""

        # Phase 1: Extract O*NET tasks
        all_tasks = self.onet_extractor.extract_writing_tasks()

        # Apply filters
        tasks = self._filter_tasks(all_tasks, filters or {})

        # Phase 2: Algorithmic sampling and combination
        sampled_tasks = self._stratified_sample(tasks, count)

        # Generate prompts for each task
        prompts = []
        for i, task in enumerate(sampled_tasks):
            prompt = self._generate_single_prompt(task, i)
            prompts.append(prompt)

        # Phase 3: LLM enrichment (optional)
        if self.enable_llm_enrichment:
            prompts = self._enrich_prompts(prompts)

        return prompts

    def _filter_tasks(
        self,
        tasks: List[ONetTask],
        filters: Dict[str, Any]
    ) -> List[ONetTask]:
        """Apply user-specified filters to tasks."""
        filtered = tasks

        if 'occupations' in filters:
            codes = filters['occupations']
            filtered = [t for t in filtered
                       if any(t.onetsoc_code.startswith(c) for c in codes)]

        if 'job_zones' in filters:
            zones = filters['job_zones']
            filtered = [t for t in filtered if t.job_zone in zones]

        if 'writing_categories' in filters:
            cats = filters['writing_categories']
            filtered = [t for t in filtered if t.writing_category in cats]

        return filtered

    def _stratified_sample(
        self,
        tasks: List[ONetTask],
        count: int
    ) -> List[ONetTask]:
        """Stratified sampling across dimensions for diversity."""

        # Group by multiple dimensions
        by_job_zone: Dict[int, List[ONetTask]] = {}
        by_category: Dict[str, List[ONetTask]] = {}
        by_soc_major: Dict[str, List[ONetTask]] = {}

        for task in tasks:
            # By job zone
            if task.job_zone not in by_job_zone:
                by_job_zone[task.job_zone] = []
            by_job_zone[task.job_zone].append(task)

            # By writing category
            if task.writing_category not in by_category:
                by_category[task.writing_category] = []
            by_category[task.writing_category].append(task)

            # By SOC major group
            soc_major = task.onetsoc_code[:2]
            if soc_major not in by_soc_major:
                by_soc_major[soc_major] = []
            by_soc_major[soc_major].append(task)

        # Sample evenly from job zones
        sampled = []
        zones = sorted(by_job_zone.keys())
        per_zone = count // len(zones)
        remainder = count % len(zones)

        for i, zone in enumerate(zones):
            zone_count = per_zone + (1 if i < remainder else 0)
            zone_tasks = by_job_zone[zone]
            self.rng.shuffle(zone_tasks)
            sampled.extend(zone_tasks[:zone_count])

        self.rng.shuffle(sampled)
        return sampled[:count]

    def _generate_single_prompt(
        self,
        task: ONetTask,
        index: int
    ) -> WritingPrompt:
        """Generate a complete prompt from an O*NET task."""

        # Deterministic seed for this prompt
        prompt_seed = self.seed + index
        local_rng = random.Random(prompt_seed)

        # Get industry and company
        industry = self.naics_mapper.sample_industry(
            task.onetsoc_code, prompt_seed
        )
        company = self.company_db.get_company(
            industry_naics=industry.code,
            seed=prompt_seed
        )

        # Generate personas
        writer_name = self.name_generator.generate_name(
            generation=self._map_job_zone_to_generation(task.job_zone, local_rng)
        )
        recipient_name = self.name_generator.generate_name()

        # Map job zone to formality
        formality = self._infer_formality(task.job_zone, local_rng)

        # Sample other dimensions
        urgency = local_rng.choice(list(UrgencyLevel))
        relationship = local_rng.choice(list(RelationshipContext))
        audience = local_rng.choice(list(AudienceSize))
        emotional = local_rng.choice(list(EmotionalContext))
        message_pos = local_rng.choice(list(MessagePosition))

        # Infer communication channel from task
        channel = self._infer_channel(task.task)

        # Create writer persona
        writer = WriterPersona(
            name=writer_name.full_name,
            email=f"{writer_name.email_style}@{company.name.lower().replace(' ', '').replace(',', '')}.com",
            role=task.occupation_title,
            company=company.name,
            company_size=company.employee_count_range,
            industry=industry.title,
            generation=writer_name.generation.value,
            skill_level=task.job_zone
        )

        # Create recipient persona
        recipient = RecipientPersona(
            name=recipient_name.full_name,
            email=f"{recipient_name.email_style}@example.com",
            role=self._generate_recipient_role(task, local_rng),
            relationship_to_writer=self._generate_relationship(relationship, local_rng)
        )

        # Generate prompt ID
        prompt_id = self._generate_prompt_id(task, index)

        # Build prompt text
        prompt_text = self._build_prompt_text(
            task, writer, recipient, company, channel, formality, urgency
        )

        # Check for sensitive content
        is_sensitive, sensitive_cat = self._check_sensitive(task.task)

        return WritingPrompt(
            prompt_id=prompt_id,
            onet_task_id=task.task_id,
            onet_task=task.task,
            onetsoc_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            job_zone=task.job_zone,
            writing_category=task.writing_category,
            naics_code=industry.code,
            industry_name=industry.title,
            company=company.name,
            company_size=company.employee_count_range,
            writer=writer,
            recipient=recipient,
            communication_channel=channel,
            formality_level=formality,
            urgency_level=urgency,
            relationship_context=relationship,
            audience_size=audience,
            emotional_context=emotional,
            message_position=message_pos,
            is_sensitive=is_sensitive,
            sensitive_category=sensitive_cat,
            prompt_text=prompt_text
        )

    def _infer_formality(
        self,
        job_zone: int,
        rng: random.Random
    ) -> FormalityLevel:
        """Infer formality level from job zone with some randomness."""
        base_formality = {
            1: [FormalityLevel.VERY_CASUAL, FormalityLevel.CASUAL],
            2: [FormalityLevel.CASUAL, FormalityLevel.NEUTRAL],
            3: [FormalityLevel.NEUTRAL, FormalityLevel.FORMAL],
            4: [FormalityLevel.FORMAL, FormalityLevel.VERY_FORMAL],
            5: [FormalityLevel.FORMAL, FormalityLevel.VERY_FORMAL]
        }
        return rng.choice(base_formality.get(job_zone, [FormalityLevel.NEUTRAL]))

    def _infer_channel(self, task: str) -> str:
        """Infer communication channel from task description."""
        task_lower = task.lower()

        if 'email' in task_lower:
            return 'email'
        elif 'memo' in task_lower:
            return 'memo'
        elif 'report' in task_lower:
            return 'report'
        elif 'letter' in task_lower:
            return 'letter'
        elif 'present' in task_lower:
            return 'presentation'
        elif 'social' in task_lower or 'twitter' in task_lower:
            return 'social_media'
        elif 'slack' in task_lower or 'message' in task_lower:
            return 'instant_message'
        else:
            return 'email'  # Default to email

    def _map_job_zone_to_generation(
        self,
        job_zone: int,
        rng: random.Random
    ) -> Generation:
        """Map job zone to likely generation with variation."""
        # Higher job zones = more experience = older generations
        zone_generations = {
            1: [Generation.GEN_Z, Generation.MILLENNIAL],
            2: [Generation.GEN_Z, Generation.MILLENNIAL, Generation.GEN_X],
            3: [Generation.MILLENNIAL, Generation.GEN_X],
            4: [Generation.MILLENNIAL, Generation.GEN_X, Generation.BOOMER],
            5: [Generation.GEN_X, Generation.BOOMER]
        }
        return rng.choice(zone_generations.get(job_zone, [Generation.MILLENNIAL]))

    def _generate_recipient_role(
        self,
        task: ONetTask,
        rng: random.Random
    ) -> str:
        """Generate a realistic recipient role based on task."""
        # Parse task for clues about recipient
        task_lower = task.task.lower()

        if 'customer' in task_lower or 'client' in task_lower:
            return rng.choice(['Customer', 'Client', 'Account Manager'])
        elif 'supervisor' in task_lower or 'manager' in task_lower:
            return rng.choice(['Manager', 'Director', 'Team Lead'])
        elif 'colleague' in task_lower or 'team' in task_lower:
            return rng.choice(['Colleague', 'Team Member', 'Peer'])
        elif 'executive' in task_lower:
            return rng.choice(['VP', 'Executive', 'C-Suite'])
        else:
            return rng.choice(['Manager', 'Colleague', 'Client', 'Stakeholder'])

    def _generate_relationship(
        self,
        context: RelationshipContext,
        rng: random.Random
    ) -> str:
        """Generate relationship description."""
        relationships = {
            RelationshipContext.FIRST_CONTACT: [
                "First contact", "New connection", "Cold outreach"
            ],
            RelationshipContext.NEW_RELATIONSHIP: [
                "Met recently", "New colleague", "Recent client"
            ],
            RelationshipContext.ESTABLISHED: [
                "Worked together for 6 months", "Regular collaborator",
                "Ongoing client relationship"
            ],
            RelationshipContext.LONG_TERM: [
                "5+ year working relationship", "Long-time colleague",
                "Trusted partner"
            ]
        }
        return rng.choice(relationships.get(context, ["Professional acquaintance"]))

    def _check_sensitive(self, task: str) -> tuple:
        """Check if task involves sensitive topics."""
        task_lower = task.lower()

        sensitive_patterns = {
            'hr_issues': ['performance', 'termination', 'complaint', 'discipline'],
            'legal': ['contract', 'liability', 'compliance', 'legal'],
            'bad_news': ['layoff', 'cancel', 'reject', 'deny'],
            'confidential': ['confidential', 'financial result', 'merger'],
            'conflict': ['dispute', 'conflict', 'complaint', 'grievance']
        }

        for category, patterns in sensitive_patterns.items():
            if any(p in task_lower for p in patterns):
                return True, category

        return False, None

    def _generate_prompt_id(self, task: ONetTask, index: int) -> str:
        """Generate unique, deterministic prompt ID."""
        content = f"{task.task_id}_{index}_{self.seed}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _build_prompt_text(
        self,
        task: ONetTask,
        writer: WriterPersona,
        recipient: RecipientPersona,
        company,
        channel: str,
        formality: FormalityLevel,
        urgency: UrgencyLevel
    ) -> str:
        """Build the actual prompt text."""
        prompt_parts = [
            f"You are {writer.name}, {writer.role} at {company.name}.",
            f"",
            f"**Task**: {task.task}",
            f"",
            f"**Recipient**: {recipient.name}, {recipient.role}",
            f"**Communication type**: {channel}",
            f"**Formality level**: {formality.name.replace('_', ' ').title()}",
        ]

        if urgency in [UrgencyLevel.HIGH, UrgencyLevel.CRITICAL]:
            prompt_parts.append(f"**Urgency**: {urgency.name}")

        prompt_parts.append("")
        prompt_parts.append("Write the communication now.")

        return "\n".join(prompt_parts)

    def _enrich_prompts(
        self,
        prompts: List[WritingPrompt]
    ) -> List[WritingPrompt]:
        """Phase 3: LLM enrichment for complex prompts."""
        # This would call an LLM to add:
        # - Attachments/mock content
        # - Prior messages for replies
        # - Competing objectives
        # - Temporal context
        # Implementation would use OpenRouter client
        return prompts  # Placeholder
```

---

## 4. OpenRouter API Integration

### 4.1 Client Architecture

```python
# src/api/openrouter_client.py
import httpx
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class ModelConfig:
    model_id: str
    display_name: str
    tier: str  # "pro" or "flash"
    provider: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    max_context: int

# Model configurations for January 2026
MODELS = {
    # Pro-tier Gemini
    "gemini-3-pro": ModelConfig(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro",
        tier="pro",
        provider="Google",
        input_cost_per_1k=0.0025,
        output_cost_per_1k=0.01,
        max_context=1000000
    ),
    # Pro-tier competitors
    "gpt-5.2-thinking": ModelConfig(
        model_id="openai/gpt-5.2-thinking",
        display_name="GPT-5.2 Thinking",
        tier="pro",
        provider="OpenAI",
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.06,
        max_context=128000
    ),
    "claude-opus-4.5": ModelConfig(
        model_id="anthropic/claude-opus-4.5",
        display_name="Claude Opus 4.5",
        tier="pro",
        provider="Anthropic",
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.075,
        max_context=200000
    ),
    "grok-4.1-thinking": ModelConfig(
        model_id="x-ai/grok-4.1-thinking",
        display_name="Grok-4.1 Thinking",
        tier="pro",
        provider="xAI",
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.015,
        max_context=131072
    ),
    "kimi-k2-thinking": ModelConfig(
        model_id="moonshot/kimi-k2-thinking",
        display_name="Kimi K2 Thinking",
        tier="pro",
        provider="Moonshot",
        input_cost_per_1k=0.002,
        output_cost_per_1k=0.006,
        max_context=200000
    ),

    # Flash-tier Gemini
    "gemini-3-flash": ModelConfig(
        model_id="google/gemini-3.0-flash",
        display_name="Gemini 3.0 Flash",
        tier="flash",
        provider="Google",
        input_cost_per_1k=0.000075,
        output_cost_per_1k=0.0003,
        max_context=1000000
    ),
    # Flash-tier competitors
    "gpt-4.1": ModelConfig(
        model_id="openai/gpt-4.1",
        display_name="GPT-4.1",
        tier="flash",
        provider="OpenAI",
        input_cost_per_1k=0.002,
        output_cost_per_1k=0.008,
        max_context=128000
    ),
    "claude-sonnet": ModelConfig(
        model_id="anthropic/claude-sonnet-4",
        display_name="Claude Sonnet 4",
        tier="flash",
        provider="Anthropic",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        max_context=200000
    ),
}

# Judge models
JUDGE_MODELS = ["claude-opus-4.5", "gpt-5.2-thinking", "gemini-3-pro"]

@dataclass
class APIResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: float
    finish_reason: str
    raw_response: Dict[str, Any]

class OpenRouterClient:
    """Async client for OpenRouter API with retry and rate limiting."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        timeout: float = 120.0,
        rate_limit_rpm: int = 60
    ):
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit_rpm = rate_limit_rpm

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "gemini-writing-eval",
                "X-Title": "Gemini Writing Evaluation Framework"
            },
            timeout=httpx.Timeout(timeout)
        )

        self._request_times: List[datetime] = []
        self._lock = asyncio.Lock()

    async def complete(
        self,
        model_key: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> APIResponse:
        """Send completion request with rate limiting and retry."""

        model_config = MODELS.get(model_key)
        if not model_config:
            raise ValueError(f"Unknown model: {model_key}")

        # Rate limiting
        await self._wait_for_rate_limit()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_config.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = datetime.now()

                response = await self._client.post(
                    "/chat/completions",
                    json=payload
                )
                response.raise_for_status()

                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                data = response.json()

                # Parse response
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                # Calculate cost
                cost = (
                    (input_tokens / 1000) * model_config.input_cost_per_1k +
                    (output_tokens / 1000) * model_config.output_cost_per_1k
                )

                return APIResponse(
                    content=content,
                    model=model_key,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost=cost,
                    finish_reason=data["choices"][0].get("finish_reason", "unknown"),
                    raw_response=data
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    # Rate limit - wait longer
                    wait_time = 2 ** attempt * 5
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:
                    # Server error - retry
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)

        raise last_error or Exception("Max retries exceeded")

    async def _wait_for_rate_limit(self):
        """Enforce rate limiting."""
        async with self._lock:
            now = datetime.now()

            # Remove old requests outside the window
            window_start = now - timedelta(minutes=1)
            self._request_times = [
                t for t in self._request_times if t > window_start
            ]

            # Wait if at rate limit
            if len(self._request_times) >= self.rate_limit_rpm:
                oldest = min(self._request_times)
                wait_seconds = (oldest + timedelta(minutes=1) - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

            self._request_times.append(now)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
```

---

## 5. Evaluation Engine

### 5.1 Core Evaluation Loop

The evaluation engine orchestrates the comparison process with pairwise SxS methodology.

```python
# src/eval/engine.py
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random

from ..prompts.schemas import WritingPrompt
from ..api.openrouter_client import OpenRouterClient, APIResponse, JUDGE_MODELS
from ..storage.database import ResultsDatabase
from ..storage.checkpoint import CheckpointManager
from .judge import JudgePersona, JudgeManager
from .aggregator import VoteAggregator

class ComparisonResult(Enum):
    GEMINI_WINS = "gemini_wins"
    OPPONENT_WINS = "opponent_wins"
    TIE = "tie"
    INCONCLUSIVE = "inconclusive"

@dataclass
class ResponsePair:
    prompt_id: str
    gemini_model: str
    opponent_model: str
    gemini_response: APIResponse
    opponent_response: APIResponse
    gemini_first: bool  # Position randomization

@dataclass
class JudgmentVote:
    judge_model: str
    judge_persona: str
    winner: str  # "response_a", "response_b", or "tie"
    confidence: float
    reasoning: str
    raw_response: str

@dataclass
class ComparisonOutcome:
    prompt_id: str
    gemini_model: str
    opponent_model: str
    result: ComparisonResult
    gemini_response: str
    opponent_response: str
    judgments: List[JudgmentVote]
    aggregated_scores: Dict[str, Any]
    metadata: Dict[str, Any]

class EvaluationEngine:
    """Core evaluation orchestrator."""

    def __init__(
        self,
        api_client: OpenRouterClient,
        db: ResultsDatabase,
        checkpoint_manager: CheckpointManager,
        config: Dict[str, Any]
    ):
        self.api_client = api_client
        self.db = db
        self.checkpoint = checkpoint_manager
        self.config = config

        self.judge_manager = JudgeManager(api_client, config)
        self.vote_aggregator = VoteAggregator()

        # Model pairs configuration
        self.model_pairs = self._build_model_pairs()

        # Progress tracking
        self.completed_comparisons = 0
        self.total_comparisons = 0
        self._progress_callback = None

    def _build_model_pairs(self) -> List[tuple]:
        """Build list of model pairs for comparison."""
        pairs = []

        # Pro-tier comparisons
        if self.config.get('run_pro_tier', True):
            gemini_pro = 'gemini-3-pro'
            pro_competitors = self.config.get('pro_competitors', [
                'gpt-5.2-thinking', 'claude-opus-4.5',
                'grok-4.1-thinking', 'kimi-k2-thinking'
            ])
            for competitor in pro_competitors:
                pairs.append((gemini_pro, competitor))

        # Flash-tier comparisons
        if self.config.get('run_flash_tier', True):
            gemini_flash = 'gemini-3-flash'
            flash_competitors = self.config.get('flash_competitors', [
                'gpt-4.1', 'claude-sonnet'
            ])
            for competitor in flash_competitors:
                pairs.append((gemini_flash, competitor))

        return pairs

    async def run_evaluation(
        self,
        prompts: List[WritingPrompt],
        progress_callback=None
    ) -> Dict[str, Any]:
        """Run the full evaluation pipeline."""
        self._progress_callback = progress_callback
        self.total_comparisons = len(prompts) * len(self.model_pairs)
        self.completed_comparisons = 0

        results = []

        for prompt in prompts:
            # Check if already processed (for resume)
            if self.checkpoint.is_prompt_complete(prompt.prompt_id):
                continue

            for gemini_model, opponent_model in self.model_pairs:
                try:
                    outcome = await self._run_single_comparison(
                        prompt, gemini_model, opponent_model
                    )
                    results.append(outcome)

                    # Save to database
                    await self.db.save_comparison(outcome)

                    # Update checkpoint
                    self.checkpoint.mark_comparison_complete(
                        prompt.prompt_id, gemini_model, opponent_model
                    )

                    self.completed_comparisons += 1
                    if self._progress_callback:
                        await self._progress_callback(self._get_progress_state())

                except Exception as e:
                    # Log failure but continue
                    await self.db.log_failure(
                        prompt.prompt_id, gemini_model, opponent_model, str(e)
                    )

        return self._compile_final_results(results)

    async def _run_single_comparison(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        opponent_model: str
    ) -> ComparisonOutcome:
        """Run a single pairwise comparison."""

        # Step 1: Generate responses from both models
        responses = await self._generate_responses(
            prompt, gemini_model, opponent_model
        )

        # Step 2: Randomize position (deterministic based on prompt_id)
        response_pair = self._create_randomized_pair(
            prompt.prompt_id, gemini_model, opponent_model,
            responses[0], responses[1]
        )

        # Step 3: Collect judgments from all judges
        judgments = await self._collect_judgments(prompt, response_pair)

        # Step 4: Aggregate votes
        result, scores = self.vote_aggregator.aggregate(
            judgments, response_pair.gemini_first
        )

        return ComparisonOutcome(
            prompt_id=prompt.prompt_id,
            gemini_model=gemini_model,
            opponent_model=opponent_model,
            result=result,
            gemini_response=responses[0].content,
            opponent_response=responses[1].content,
            judgments=judgments,
            aggregated_scores=scores,
            metadata={
                'gemini_latency_ms': responses[0].latency_ms,
                'opponent_latency_ms': responses[1].latency_ms,
                'gemini_tokens': responses[0].output_tokens,
                'opponent_tokens': responses[1].output_tokens,
                'gemini_first': response_pair.gemini_first,
                'total_cost': responses[0].cost + responses[1].cost
            }
        )

    async def _generate_responses(
        self,
        prompt: WritingPrompt,
        gemini_model: str,
        opponent_model: str
    ) -> tuple:
        """Generate responses from both models in parallel."""

        tasks = [
            self.api_client.complete(
                gemini_model,
                prompt.prompt_text,
                system_prompt=self._get_system_prompt(prompt)
            ),
            self.api_client.complete(
                opponent_model,
                prompt.prompt_text,
                system_prompt=self._get_system_prompt(prompt)
            )
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle failures
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                model = gemini_model if i == 0 else opponent_model
                raise RuntimeError(f"Model {model} failed: {resp}")

        return responses

    def _create_randomized_pair(
        self,
        prompt_id: str,
        gemini_model: str,
        opponent_model: str,
        gemini_response: APIResponse,
        opponent_response: APIResponse
    ) -> ResponsePair:
        """Create response pair with deterministic position randomization."""
        # Deterministic randomization based on prompt_id
        rng = random.Random(hash(prompt_id))
        gemini_first = rng.choice([True, False])

        return ResponsePair(
            prompt_id=prompt_id,
            gemini_model=gemini_model,
            opponent_model=opponent_model,
            gemini_response=gemini_response,
            opponent_response=opponent_response,
            gemini_first=gemini_first
        )

    async def _collect_judgments(
        self,
        prompt: WritingPrompt,
        response_pair: ResponsePair
    ) -> List[JudgmentVote]:
        """Collect judgments from all judge models with all personas."""

        judgments = []
        judge_models = self.config.get('judge_models', JUDGE_MODELS)
        votes_per_judge = self.config.get('votes_per_judge', 5)
        personas = self.config.get('judge_personas', ['writing_expert', 'recipient'])

        for judge_model in judge_models:
            for persona in personas:
                for vote_idx in range(votes_per_judge):
                    judgment = await self.judge_manager.get_judgment(
                        prompt=prompt,
                        response_pair=response_pair,
                        judge_model=judge_model,
                        persona=persona,
                        vote_index=vote_idx
                    )
                    judgments.append(judgment)

        return judgments

    def _get_system_prompt(self, prompt: WritingPrompt) -> str:
        """Generate system prompt for response generation."""
        return """You are a helpful assistant completing a professional writing task.
Write naturally and appropriately for the context given.
Do not explain your response or add meta-commentary.
Simply write the requested content."""

    def _get_progress_state(self) -> Dict[str, Any]:
        """Get current progress state for UI."""
        return {
            'completed': self.completed_comparisons,
            'total': self.total_comparisons,
            'percentage': (self.completed_comparisons / self.total_comparisons * 100)
                         if self.total_comparisons > 0 else 0
        }

    def _compile_final_results(
        self,
        results: List[ComparisonOutcome]
    ) -> Dict[str, Any]:
        """Compile final results summary."""
        by_pair = {}

        for outcome in results:
            key = f"{outcome.gemini_model}_vs_{outcome.opponent_model}"
            if key not in by_pair:
                by_pair[key] = {
                    'gemini_wins': 0,
                    'opponent_wins': 0,
                    'ties': 0,
                    'inconclusive': 0,
                    'total': 0
                }

            by_pair[key]['total'] += 1
            if outcome.result == ComparisonResult.GEMINI_WINS:
                by_pair[key]['gemini_wins'] += 1
            elif outcome.result == ComparisonResult.OPPONENT_WINS:
                by_pair[key]['opponent_wins'] += 1
            elif outcome.result == ComparisonResult.TIE:
                by_pair[key]['ties'] += 1
            else:
                by_pair[key]['inconclusive'] += 1

        # Calculate win rates
        for key, stats in by_pair.items():
            decisive = stats['gemini_wins'] + stats['opponent_wins']
            if decisive > 0:
                stats['win_rate'] = stats['gemini_wins'] / decisive
            else:
                stats['win_rate'] = 0.5

        return {
            'by_pair': by_pair,
            'total_comparisons': len(results),
            'timestamp': datetime.now().isoformat()
        }
```

### 5.2 Judge Implementation

```python
# src/eval/judge.py
from typing import Optional
from dataclasses import dataclass

from ..api.openrouter_client import OpenRouterClient
from ..prompts.schemas import WritingPrompt

@dataclass
class JudgmentVote:
    judge_model: str
    judge_persona: str
    winner: str  # "response_a", "response_b", or "tie"
    confidence: float
    reasoning: str
    raw_response: str

class JudgePersona:
    """Judge persona configurations."""

    WRITING_EXPERT = """You are an expert writing professional evaluating the quality
of two written communications. You have decades of experience in professional
communications, technical writing, and corporate correspondence.

Evaluate based on:
- Quality of craft and writing mechanics
- Appropriate length and tone for the context
- Clarity and structure
- Professionalism and polish
- Authenticity (does it sound natural, not AI-generated?)
- Avoidance of cliches and boilerplate phrases

Be critical and discerning. Good writing is rare."""

    RECIPIENT = """You are the intended recipient of this communication: {recipient_context}

Evaluate based on:
- Does this achieve its purpose effectively?
- Is the tone appropriate for our relationship?
- Is the length appropriate (not too long, not too short)?
- Would I find this helpful/actionable/informative?
- Does it feel authentic, like a real person wrote it?
- Does it respect my time?

Judge as if you actually received this in your inbox."""

class JudgeManager:
    """Manages judge model calls and prompt construction."""

    def __init__(self, api_client: OpenRouterClient, config: dict):
        self.api_client = api_client
        self.config = config

    async def get_judgment(
        self,
        prompt: WritingPrompt,
        response_pair,
        judge_model: str,
        persona: str,
        vote_index: int
    ) -> JudgmentVote:
        """Get a single judgment from a judge model."""

        # Build judge prompt
        judge_prompt = self._build_judge_prompt(
            prompt, response_pair, persona
        )

        # Get system prompt for persona
        system_prompt = self._get_persona_prompt(prompt, persona)

        # Call judge model
        response = await self.api_client.complete(
            judge_model,
            judge_prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent judging
        )

        # Parse judgment
        winner, confidence, reasoning = self._parse_judgment(response.content)

        return JudgmentVote(
            judge_model=judge_model,
            judge_persona=persona,
            winner=winner,
            confidence=confidence,
            reasoning=reasoning,
            raw_response=response.content
        )

    def _build_judge_prompt(
        self,
        prompt: WritingPrompt,
        response_pair,
        persona: str
    ) -> str:
        """Build the judgment prompt."""

        # Determine response order
        if response_pair.gemini_first:
            response_a = response_pair.gemini_response.content
            response_b = response_pair.opponent_response.content
        else:
            response_a = response_pair.opponent_response.content
            response_b = response_pair.gemini_response.content

        return f"""## Task Context

{prompt.get_full_context()}

## Writing Task

{prompt.prompt_text}

---

## Response A

{response_a}

---

## Response B

{response_b}

---

## Your Judgment

Compare Response A and Response B. Which one better accomplishes the writing task
given the context above?

Consider:
1. Overall quality and effectiveness
2. Appropriateness for the specific context (writer, recipient, formality, urgency)
3. Natural, authentic voice (not obviously AI-generated)
4. Appropriate length
5. Clarity and professionalism

Provide your judgment in this format:

WINNER: [A/B/TIE]
CONFIDENCE: [HIGH/MEDIUM/LOW]
REASONING: [2-3 sentences explaining your choice]"""

    def _get_persona_prompt(self, prompt: WritingPrompt, persona: str) -> str:
        """Get system prompt for judge persona."""
        if persona == 'writing_expert':
            return JudgePersona.WRITING_EXPERT
        elif persona == 'recipient':
            recipient_context = f"{prompt.recipient.name}, {prompt.recipient.role}"
            return JudgePersona.RECIPIENT.format(recipient_context=recipient_context)
        else:
            return JudgePersona.WRITING_EXPERT

    def _parse_judgment(self, response: str) -> tuple:
        """Parse judgment response to extract winner, confidence, reasoning."""
        lines = response.strip().split('\n')

        winner = 'tie'
        confidence = 0.5
        reasoning = ''

        for line in lines:
            line_upper = line.upper()
            if line_upper.startswith('WINNER:'):
                w = line.split(':', 1)[1].strip().upper()
                if 'A' in w and 'B' not in w:
                    winner = 'response_a'
                elif 'B' in w and 'A' not in w:
                    winner = 'response_b'
                else:
                    winner = 'tie'
            elif line_upper.startswith('CONFIDENCE:'):
                c = line.split(':', 1)[1].strip().upper()
                if 'HIGH' in c:
                    confidence = 0.9
                elif 'MEDIUM' in c:
                    confidence = 0.7
                else:
                    confidence = 0.5
            elif line_upper.startswith('REASONING:'):
                reasoning = line.split(':', 1)[1].strip()

        return winner, confidence, reasoning
```

### 5.3 Vote Aggregation

```python
# src/eval/aggregator.py
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .engine import ComparisonResult, JudgmentVote

class VoteAggregator:
    """Implements majority-of-majorities voting logic."""

    def aggregate(
        self,
        judgments: List[JudgmentVote],
        gemini_was_first: bool
    ) -> Tuple[ComparisonResult, Dict[str, Any]]:
        """Aggregate votes using majority-of-majorities."""

        # Group judgments by judge model
        by_judge: Dict[str, List[JudgmentVote]] = defaultdict(list)
        for j in judgments:
            by_judge[j.judge_model].append(j)

        # Get majority vote per judge model
        judge_majorities = {}
        for judge_model, votes in by_judge.items():
            majority = self._get_majority(votes, gemini_was_first)
            judge_majorities[judge_model] = majority

        # Get majority of judge majorities
        final_result = self._get_final_majority(judge_majorities)

        # Compile scores
        scores = {
            'by_judge': judge_majorities,
            'final_result': final_result.value,
            'total_votes': len(judgments),
            'gemini_was_first': gemini_was_first
        }

        return final_result, scores

    def _get_majority(
        self,
        votes: List[JudgmentVote],
        gemini_was_first: bool
    ) -> str:
        """Get majority winner from a list of votes."""
        gemini_votes = 0
        opponent_votes = 0
        ties = 0

        for vote in votes:
            if vote.winner == 'tie':
                ties += 1
            elif vote.winner == 'response_a':
                if gemini_was_first:
                    gemini_votes += 1
                else:
                    opponent_votes += 1
            elif vote.winner == 'response_b':
                if gemini_was_first:
                    opponent_votes += 1
                else:
                    gemini_votes += 1

        if gemini_votes > opponent_votes:
            return 'gemini'
        elif opponent_votes > gemini_votes:
            return 'opponent'
        else:
            return 'tie'

    def _get_final_majority(
        self,
        judge_majorities: Dict[str, str]
    ) -> ComparisonResult:
        """Get final result from judge majorities."""
        gemini_wins = sum(1 for v in judge_majorities.values() if v == 'gemini')
        opponent_wins = sum(1 for v in judge_majorities.values() if v == 'opponent')
        ties = sum(1 for v in judge_majorities.values() if v == 'tie')

        total_judges = len(judge_majorities)
        majority_threshold = total_judges // 2 + 1

        if gemini_wins >= majority_threshold:
            return ComparisonResult.GEMINI_WINS
        elif opponent_wins >= majority_threshold:
            return ComparisonResult.OPPONENT_WINS
        elif ties >= majority_threshold:
            return ComparisonResult.TIE
        else:
            return ComparisonResult.INCONCLUSIVE
```

---

## 6. Storage and Persistence

### 6.1 SQLite Database Schema

```python
# src/storage/database.py
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

class ResultsDatabase:
    """SQLite database for evaluation results."""

    SCHEMA = """
    -- Prompts table
    CREATE TABLE IF NOT EXISTS prompts (
        prompt_id TEXT PRIMARY KEY,
        onet_task_id TEXT,
        onet_task TEXT,
        onetsoc_code TEXT,
        occupation_title TEXT,
        job_zone INTEGER,
        writing_category TEXT,
        naics_code TEXT,
        industry_name TEXT,
        company TEXT,
        company_size TEXT,
        communication_channel TEXT,
        formality_level TEXT,
        urgency_level TEXT,
        is_sensitive INTEGER,
        sensitive_category TEXT,
        prompt_text TEXT,
        full_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Model responses table
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT,
        model TEXT,
        response_text TEXT,
        input_tokens INTEGER,
        output_tokens INTEGER,
        latency_ms REAL,
        cost REAL,
        finish_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Judgments table
    CREATE TABLE IF NOT EXISTS judgments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT,
        gemini_model TEXT,
        opponent_model TEXT,
        judge_model TEXT,
        judge_persona TEXT,
        winner TEXT,
        confidence REAL,
        reasoning TEXT,
        raw_response TEXT,
        gemini_was_first INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Comparison results table
    CREATE TABLE IF NOT EXISTS comparisons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT,
        gemini_model TEXT,
        opponent_model TEXT,
        result TEXT,
        gemini_response_id INTEGER,
        opponent_response_id INTEGER,
        aggregated_scores TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
        FOREIGN KEY (gemini_response_id) REFERENCES responses(id),
        FOREIGN KEY (opponent_response_id) REFERENCES responses(id)
    );

    -- Failures log table
    CREATE TABLE IF NOT EXISTS failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT,
        gemini_model TEXT,
        opponent_model TEXT,
        error_message TEXT,
        error_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for efficient querying
    CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(onetsoc_code);
    CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(writing_category);
    CREATE INDEX IF NOT EXISTS idx_comparisons_result ON comparisons(result);
    CREATE INDEX IF NOT EXISTS idx_comparisons_models ON comparisons(gemini_model, opponent_model);
    CREATE INDEX IF NOT EXISTS idx_judgments_prompt ON judgments(prompt_id);
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()

    async def save_prompt(self, prompt) -> None:
        """Save a writing prompt to the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prompts
            (prompt_id, onet_task_id, onet_task, onetsoc_code, occupation_title,
             job_zone, writing_category, naics_code, industry_name, company,
             company_size, communication_channel, formality_level, urgency_level,
             is_sensitive, sensitive_category, prompt_text, full_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prompt.prompt_id,
            prompt.onet_task_id,
            prompt.onet_task,
            prompt.onetsoc_code,
            prompt.occupation_title,
            prompt.job_zone,
            prompt.writing_category,
            prompt.naics_code,
            prompt.industry_name,
            prompt.company,
            prompt.company_size,
            prompt.communication_channel,
            prompt.formality_level.name,
            prompt.urgency_level.name,
            1 if prompt.is_sensitive else 0,
            prompt.sensitive_category,
            prompt.prompt_text,
            prompt.model_dump_json()
        ))
        self.conn.commit()

    async def save_comparison(self, outcome) -> None:
        """Save a comparison outcome to the database."""
        cursor = self.conn.cursor()

        # Save responses
        cursor.execute("""
            INSERT INTO responses (prompt_id, model, response_text, input_tokens,
                                  output_tokens, latency_ms, cost, finish_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            outcome.prompt_id,
            outcome.gemini_model,
            outcome.gemini_response,
            outcome.metadata.get('gemini_tokens', 0),
            outcome.metadata.get('gemini_tokens', 0),
            outcome.metadata.get('gemini_latency_ms', 0),
            outcome.metadata.get('total_cost', 0) / 2,
            'complete'
        ))
        gemini_response_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO responses (prompt_id, model, response_text, input_tokens,
                                  output_tokens, latency_ms, cost, finish_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            outcome.prompt_id,
            outcome.opponent_model,
            outcome.opponent_response,
            outcome.metadata.get('opponent_tokens', 0),
            outcome.metadata.get('opponent_tokens', 0),
            outcome.metadata.get('opponent_latency_ms', 0),
            outcome.metadata.get('total_cost', 0) / 2,
            'complete'
        ))
        opponent_response_id = cursor.lastrowid

        # Save judgments
        for judgment in outcome.judgments:
            cursor.execute("""
                INSERT INTO judgments (prompt_id, gemini_model, opponent_model,
                                      judge_model, judge_persona, winner,
                                      confidence, reasoning, raw_response, gemini_was_first)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome.prompt_id,
                outcome.gemini_model,
                outcome.opponent_model,
                judgment.judge_model,
                judgment.judge_persona,
                judgment.winner,
                judgment.confidence,
                judgment.reasoning,
                judgment.raw_response,
                1 if outcome.metadata.get('gemini_first', True) else 0
            ))

        # Save comparison result
        cursor.execute("""
            INSERT INTO comparisons (prompt_id, gemini_model, opponent_model,
                                    result, gemini_response_id, opponent_response_id,
                                    aggregated_scores, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            outcome.prompt_id,
            outcome.gemini_model,
            outcome.opponent_model,
            outcome.result.value,
            gemini_response_id,
            opponent_response_id,
            json.dumps(outcome.aggregated_scores),
            json.dumps(outcome.metadata)
        ))

        self.conn.commit()

    async def log_failure(
        self,
        prompt_id: str,
        gemini_model: str,
        opponent_model: str,
        error: str
    ) -> None:
        """Log a failure."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO failures (prompt_id, gemini_model, opponent_model,
                                 error_message, error_type)
            VALUES (?, ?, ?, ?, ?)
        """, (
            prompt_id,
            gemini_model,
            opponent_model,
            error,
            type(error).__name__ if isinstance(error, Exception) else 'str'
        ))
        self.conn.commit()

    def get_win_rates(self) -> Dict[str, Dict[str, float]]:
        """Get win rates by model pair."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                gemini_model,
                opponent_model,
                result,
                COUNT(*) as count
            FROM comparisons
            GROUP BY gemini_model, opponent_model, result
        """)

        results = {}
        for row in cursor:
            key = f"{row['gemini_model']}_vs_{row['opponent_model']}"
            if key not in results:
                results[key] = {
                    'gemini_wins': 0,
                    'opponent_wins': 0,
                    'ties': 0,
                    'total': 0
                }

            if row['result'] == 'gemini_wins':
                results[key]['gemini_wins'] = row['count']
            elif row['result'] == 'opponent_wins':
                results[key]['opponent_wins'] = row['count']
            else:
                results[key]['ties'] = row['count']

            results[key]['total'] += row['count']

        # Calculate win rates
        for key, stats in results.items():
            decisive = stats['gemini_wins'] + stats['opponent_wins']
            stats['win_rate'] = stats['gemini_wins'] / decisive if decisive > 0 else 0.5

        return results

    def close(self):
        """Close database connection."""
        self.conn.close()
```

### 6.2 Checkpoint Manager

```python
# src/storage/checkpoint.py
import json
from pathlib import Path
from typing import Set, Dict, Any
from datetime import datetime

class CheckpointManager:
    """Manages evaluation checkpoints for resume capability."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.checkpoint_file = results_dir / "checkpoint.json"
        self.completed_comparisons: Set[str] = set()
        self._load_checkpoint()

    def _load_checkpoint(self):
        """Load checkpoint from file if exists."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file) as f:
                data = json.load(f)
                self.completed_comparisons = set(data.get('completed', []))

    def _save_checkpoint(self):
        """Save checkpoint to file."""
        data = {
            'completed': list(self.completed_comparisons),
            'last_updated': datetime.now().isoformat()
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)

    def is_prompt_complete(self, prompt_id: str) -> bool:
        """Check if all comparisons for a prompt are complete."""
        # Would need to check against all model pairs
        return False  # Simplified

    def mark_comparison_complete(
        self,
        prompt_id: str,
        gemini_model: str,
        opponent_model: str
    ):
        """Mark a specific comparison as complete."""
        key = f"{prompt_id}_{gemini_model}_{opponent_model}"
        self.completed_comparisons.add(key)
        self._save_checkpoint()

    def is_comparison_complete(
        self,
        prompt_id: str,
        gemini_model: str,
        opponent_model: str
    ) -> bool:
        """Check if a specific comparison is complete."""
        key = f"{prompt_id}_{gemini_model}_{opponent_model}"
        return key in self.completed_comparisons

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress statistics."""
        return {
            'completed_comparisons': len(self.completed_comparisons),
            'last_checkpoint': self.checkpoint_file.stat().st_mtime
                              if self.checkpoint_file.exists() else None
        }
```

---

## 7. Configuration and Presets

### 7.1 Configuration Schema

```python
# src/config/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from enum import Enum

class EvalPreset(Enum):
    SANITY_CHECK = 1
    SMOKE_TEST = 2
    DEV_ITERATION = 3
    QUICK_SAMPLE = 4
    LIGHT_EVAL = 5
    STANDARD_EVAL = 6
    THOROUGH_EVAL = 7
    COMPREHENSIVE = 8
    DEEP_DIVE = 9
    FULL_KABOODLE = 10

class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # API Configuration
    openrouter_api_key: str = Field(..., env='OPENROUTER_API_KEY')
    api_timeout: float = 120.0
    api_max_retries: int = 3
    api_rate_limit_rpm: int = 60

    # O*NET Database
    onet_db_path: str = "db/onet.db"

    # Evaluation Settings
    preset: Optional[EvalPreset] = None
    num_prompts: int = 500
    random_seed: int = 42

    # Model Configuration
    run_pro_tier: bool = True
    run_flash_tier: bool = True
    pro_competitors: List[str] = [
        'gpt-5.2-thinking', 'claude-opus-4.5',
        'grok-4.1-thinking', 'kimi-k2-thinking'
    ]
    flash_competitors: List[str] = ['gpt-4.1', 'claude-sonnet']

    # Judge Configuration
    judge_models: List[str] = [
        'claude-opus-4.5', 'gpt-5.2-thinking', 'gemini-3-pro'
    ]
    votes_per_judge: int = 5
    judge_personas: List[str] = ['writing_expert', 'recipient']

    # Filtering
    occupation_filter: Optional[List[str]] = None
    industry_filter: Optional[List[str]] = None
    job_zone_filter: Optional[List[int]] = None

    # Output
    results_dir: str = "results"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 7.2 Preset Configurations

```python
# src/config/presets.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class PresetConfig:
    name: str
    num_prompts: int
    model_pairs: int
    judge_count: int
    votes_per_judge: int
    estimated_cost: str
    estimated_time: str
    use_case: str

PRESETS = {
    1: PresetConfig(
        name="Sanity Check",
        num_prompts=5,
        model_pairs=1,
        judge_count=1,
        votes_per_judge=1,
        estimated_cost="~$1",
        estimated_time="~2 min",
        use_case="Does the system work?"
    ),
    2: PresetConfig(
        name="Smoke Test",
        num_prompts=20,
        model_pairs=1,
        judge_count=1,
        votes_per_judge=3,
        estimated_cost="~$5",
        estimated_time="~5 min",
        use_case="Quick functionality test"
    ),
    3: PresetConfig(
        name="Dev Iteration",
        num_prompts=50,
        model_pairs=2,
        judge_count=2,
        votes_per_judge=3,
        estimated_cost="~$25",
        estimated_time="~15 min",
        use_case="Development/debugging"
    ),
    4: PresetConfig(
        name="Quick Sample",
        num_prompts=100,
        model_pairs=2,
        judge_count=2,
        votes_per_judge=5,
        estimated_cost="~$75",
        estimated_time="~30 min",
        use_case="Fast directional signal"
    ),
    5: PresetConfig(
        name="Light Eval",
        num_prompts=200,
        model_pairs=3,
        judge_count=3,
        votes_per_judge=3,
        estimated_cost="~$150",
        estimated_time="~1 hr",
        use_case="Light but meaningful eval"
    ),
    6: PresetConfig(
        name="Standard Eval",
        num_prompts=500,
        model_pairs=4,
        judge_count=3,
        votes_per_judge=5,
        estimated_cost="~$500",
        estimated_time="~3 hrs",
        use_case="Standard evaluation run"
    ),
    7: PresetConfig(
        name="Thorough Eval",
        num_prompts=1000,
        model_pairs=4,
        judge_count=3,
        votes_per_judge=5,
        estimated_cost="~$1,000",
        estimated_time="~6 hrs",
        use_case="Thorough with good power"
    ),
    8: PresetConfig(
        name="Comprehensive",
        num_prompts=2000,
        model_pairs=6,
        judge_count=3,
        votes_per_judge=5,
        estimated_cost="~$2,500",
        estimated_time="~12 hrs",
        use_case="High statistical power"
    ),
    9: PresetConfig(
        name="Deep Dive",
        num_prompts=5000,
        model_pairs=6,
        judge_count=3,
        votes_per_judge=5,
        estimated_cost="~$6,000",
        estimated_time="~24 hrs",
        use_case="Publication-grade"
    ),
    10: PresetConfig(
        name="Full Kaboodle",
        num_prompts=10000,
        model_pairs=6,
        judge_count=3,
        votes_per_judge=5,
        estimated_cost="~$12,000+",
        estimated_time="~48 hrs",
        use_case="Maximum coverage"
    )
}

def get_preset(level: int) -> PresetConfig:
    """Get preset configuration by level."""
    return PRESETS.get(level, PRESETS[6])
```

### 7.3 Cost Estimator

```python
# src/config/cost_estimator.py
from dataclasses import dataclass
from typing import Dict, List
from ..api.openrouter_client import MODELS

@dataclass
class CostEstimate:
    response_generation_min: float
    response_generation_max: float
    judging_min: float
    judging_max: float
    total_min: float
    total_max: float
    estimated_time_min: str
    estimated_time_max: str

class CostEstimator:
    """Estimate costs and time for evaluation runs."""

    # Average tokens per response/judgment
    AVG_PROMPT_TOKENS = 500
    AVG_RESPONSE_TOKENS = 400
    AVG_JUDGE_INPUT_TOKENS = 1500
    AVG_JUDGE_OUTPUT_TOKENS = 150

    def estimate(
        self,
        num_prompts: int,
        model_pairs: List[tuple],
        judge_models: List[str],
        votes_per_judge: int,
        judge_personas: int = 2
    ) -> CostEstimate:
        """Estimate cost and time for an evaluation run."""

        # Response generation costs
        response_cost = 0.0
        for gemini, opponent in model_pairs:
            gemini_cfg = MODELS[gemini]
            opponent_cfg = MODELS[opponent]

            cost_per_prompt = (
                # Gemini
                (self.AVG_PROMPT_TOKENS / 1000) * gemini_cfg.input_cost_per_1k +
                (self.AVG_RESPONSE_TOKENS / 1000) * gemini_cfg.output_cost_per_1k +
                # Opponent
                (self.AVG_PROMPT_TOKENS / 1000) * opponent_cfg.input_cost_per_1k +
                (self.AVG_RESPONSE_TOKENS / 1000) * opponent_cfg.output_cost_per_1k
            )
            response_cost += cost_per_prompt * num_prompts

        # Judging costs
        total_judgments = (
            num_prompts *
            len(model_pairs) *
            len(judge_models) *
            votes_per_judge *
            judge_personas
        )

        judge_cost = 0.0
        for judge in judge_models:
            judge_cfg = MODELS[judge]
            judgments_per_judge = total_judgments // len(judge_models)

            cost = (
                (self.AVG_JUDGE_INPUT_TOKENS / 1000) * judge_cfg.input_cost_per_1k +
                (self.AVG_JUDGE_OUTPUT_TOKENS / 1000) * judge_cfg.output_cost_per_1k
            ) * judgments_per_judge
            judge_cost += cost

        # Time estimation (rough)
        total_api_calls = (
            num_prompts * len(model_pairs) * 2 +  # Response generation
            total_judgments                        # Judging
        )
        # Assume ~2 seconds per API call average
        time_seconds = total_api_calls * 2
        time_hours = time_seconds / 3600

        return CostEstimate(
            response_generation_min=response_cost * 0.8,
            response_generation_max=response_cost * 1.2,
            judging_min=judge_cost * 0.8,
            judging_max=judge_cost * 1.2,
            total_min=(response_cost + judge_cost) * 0.8,
            total_max=(response_cost + judge_cost) * 1.2,
            estimated_time_min=f"{time_hours * 0.7:.1f} hours",
            estimated_time_max=f"{time_hours * 1.3:.1f} hours"
        )
```

---

## 8. Terminal User Interface (TUI)

### 8.1 Progress Dashboard

The TUI provides real-time progress visualization using the textual library.

```python
# src/tui/app.py
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Static, ProgressBar, DataTable, Log, Label
)
from textual.reactive import reactive
from rich.table import Table
from rich.panel import Panel
from typing import Dict, Any

class ProgressDashboard(App):
    """Main TUI application for evaluation progress."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1;
    }

    #overall-progress {
        column-span: 2;
        height: auto;
    }

    #model-pairs {
        height: 100%;
    }

    #current-batch {
        height: 100%;
    }

    #statistics {
        height: 100%;
    }

    #activity-log {
        height: 100%;
    }

    #error-summary {
        column-span: 2;
        height: auto;
    }

    .panel-title {
        text-style: bold;
        color: cyan;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause"),
        ("d", "detail", "Detail View"),
        ("s", "stats", "Statistics"),
        ("h", "help", "Help"),
    ]

    # Reactive state
    completed = reactive(0)
    total = reactive(0)
    current_prompt = reactive("")
    win_rates = reactive({})

    def compose(self) -> ComposeResult:
        yield Header()

        yield Container(
            Static(id="overall-progress"),
            id="progress-container"
        )

        yield Container(
            DataTable(id="model-pairs-table"),
            id="model-pairs"
        )

        yield Container(
            Static(id="current-batch-info"),
            id="current-batch"
        )

        yield Container(
            Static(id="live-statistics"),
            id="statistics"
        )

        yield Container(
            Log(id="activity-log"),
            id="activity-log"
        )

        yield Container(
            Static(id="error-summary"),
            id="error-summary"
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the dashboard on mount."""
        # Set up model pairs table
        table = self.query_one("#model-pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate")

        # Initial update
        self.update_display()

    def update_display(self) -> None:
        """Update all display elements."""
        self._update_overall_progress()
        self._update_model_pairs()
        self._update_statistics()
        self._update_error_summary()

    def _update_overall_progress(self) -> None:
        """Update overall progress panel."""
        progress_pct = (self.completed / self.total * 100) if self.total > 0 else 0

        content = f"""
[bold]OVERALL PROGRESS[/bold]

{self._create_progress_bar(progress_pct)}

{self.completed:,} / {self.total:,} comparisons ({progress_pct:.1f}%)

Current: {self.current_prompt}
"""
        self.query_one("#overall-progress", Static).update(content)

    def _update_model_pairs(self) -> None:
        """Update model pairs table."""
        table = self.query_one("#model-pairs-table", DataTable)
        table.clear()

        for pair, stats in self.win_rates.items():
            progress = f"{stats.get('completed', 0)}/{stats.get('total', 0)}"
            win_rate = f"{stats.get('win_rate', 0.5) * 100:.1f}%"
            table.add_row(pair, progress, win_rate)

    def _update_statistics(self) -> None:
        """Update live statistics panel."""
        stats_content = """
[bold]LIVE STATISTICS[/bold]

Win Rates (Running)
-------------------
vs GPT-5.2:    51.2% +/- 4.3%
vs Opus:       48.1% +/- 5.1%
vs Grok:       52.7% +/- 7.2%

Performance
-----------
Avg response time:  2.8s
Avg judge time:     1.2s
API calls/min:      45
Est. cost so far:   $234.50
"""
        self.query_one("#live-statistics", Static).update(stats_content)

    def _update_error_summary(self) -> None:
        """Update error summary panel."""
        error_content = "0 retries | 0 failures | 0 rate limit pauses"
        self.query_one("#error-summary", Static).update(error_content)

    def _create_progress_bar(self, percentage: float) -> str:
        """Create ASCII progress bar."""
        width = 50
        filled = int(width * percentage / 100)
        empty = width - filled
        return f"[{'=' * filled}{' ' * empty}]"

    def log_activity(self, message: str) -> None:
        """Add message to activity log."""
        log = self.query_one("#activity-log", Log)
        log.write_line(message)

    async def update_progress(self, state: Dict[str, Any]) -> None:
        """Update progress from evaluation engine."""
        self.completed = state.get('completed', 0)
        self.total = state.get('total', 0)
        self.current_prompt = state.get('current_prompt', '')
        self.win_rates = state.get('win_rates', {})
        self.update_display()

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_pause(self) -> None:
        """Pause evaluation."""
        self.log_activity("Evaluation paused...")

    def action_detail(self) -> None:
        """Show detail view."""
        pass  # Would switch to detail view

    def action_stats(self) -> None:
        """Show full statistics."""
        pass  # Would show statistics panel
```

### 8.2 Results Viewer

```python
# src/tui/viewer.py
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Select, Button, TextArea
)
from textual.screen import Screen
from typing import List, Dict, Any

class ResultsViewer(App):
    """TUI for viewing and exploring evaluation results."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;
        grid-gutter: 1;
    }

    #filters {
        column-span: 3;
        height: auto;
    }

    #results-table {
        column-span: 2;
        height: 100%;
    }

    #detail-panel {
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("e", "export", "Export"),
        ("/", "search", "Search"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        yield Container(
            Horizontal(
                Select(
                    options=[("All", "all"), ("Gemini Wins", "gemini"),
                            ("Opponent Wins", "opponent"), ("Ties", "tie")],
                    value="all",
                    id="result-filter"
                ),
                Select(
                    options=[("All Occupations", "all")],
                    value="all",
                    id="occupation-filter"
                ),
                Select(
                    options=[("All Industries", "all")],
                    value="all",
                    id="industry-filter"
                ),
                Input(placeholder="Search prompts...", id="search-input"),
            ),
            id="filters"
        )

        yield Container(
            DataTable(id="results-table"),
            id="results-list"
        )

        yield Container(
            ScrollableContainer(
                Static(id="detail-content"),
            ),
            id="detail-panel"
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the viewer."""
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "ID", "Occupation", "Result", "Win Rate", "Judges"
        )
        table.cursor_type = "row"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection to show detail."""
        row_key = event.row_key
        self._show_detail(row_key)

    def _show_detail(self, row_key) -> None:
        """Show detail panel for selected comparison."""
        detail_content = """
[bold]Prompt Details[/bold]

Task: Draft quarterly performance review for junior analyst
Occupation: Human Resources Manager (11-3121)
Industry: Professional Services (NAICS 54)
Company: Deloitte (100,000+ employees)

[bold]Writer[/bold]
Sarah Chen, HR Manager
Generation: Millennial
Formality: Formal

[bold]Recipient[/bold]
James Wilson, Senior Analyst
Relationship: Direct Report

---

[bold]Gemini Response[/bold]

[Response content here...]

---

[bold]Opponent Response[/bold]

[Response content here...]

---

[bold]Judgments[/bold]

Claude Opus (Writing Expert): Gemini wins (HIGH confidence)
"Response A demonstrated better structure and..."

GPT-5.2 (Recipient): Gemini wins (MEDIUM confidence)
"As the recipient, Response A was more..."

Gemini Pro (Writing Expert): Tie
"Both responses were competent..."

[bold]Final Result: GEMINI WINS[/bold]
"""
        self.query_one("#detail-content", Static).update(detail_content)

    def load_results(self, results: List[Dict[str, Any]]) -> None:
        """Load results into the table."""
        table = self.query_one("#results-table", DataTable)
        table.clear()

        for result in results:
            table.add_row(
                result['prompt_id'][:8],
                result['occupation'][:30],
                result['result'],
                f"{result['win_rate']:.1%}",
                result['judge_agreement']
            )
```

---

## 9. Analysis and Statistics

### 9.1 Statistical Analysis Engine

```python
# src/analysis/statistics.py
import numpy as np
from scipy import stats
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

@dataclass
class WinRateAnalysis:
    win_rate: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    n_samples: int
    margin_of_error: float

@dataclass
class StatisticalTest:
    test_name: str
    statistic: float
    p_value: float
    significant: bool
    effect_size: float

class StatisticsEngine:
    """Statistical analysis for evaluation results."""

    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.z_score = stats.norm.ppf((1 + confidence_level) / 2)

    def calculate_win_rate(
        self,
        gemini_wins: int,
        opponent_wins: int,
        ties: int = 0
    ) -> WinRateAnalysis:
        """Calculate win rate with confidence interval."""
        # For win rate, exclude ties
        n = gemini_wins + opponent_wins
        if n == 0:
            return WinRateAnalysis(0.5, 0.0, 1.0, 0, 0.5)

        p = gemini_wins / n

        # Wilson score interval for proportions
        denominator = 1 + self.z_score ** 2 / n
        center = (p + self.z_score ** 2 / (2 * n)) / denominator
        spread = self.z_score * np.sqrt(
            (p * (1 - p) + self.z_score ** 2 / (4 * n)) / n
        ) / denominator

        ci_lower = max(0, center - spread)
        ci_upper = min(1, center + spread)
        margin = (ci_upper - ci_lower) / 2

        return WinRateAnalysis(
            win_rate=p,
            confidence_interval_lower=ci_lower,
            confidence_interval_upper=ci_upper,
            n_samples=n,
            margin_of_error=margin
        )

    def binomial_test(
        self,
        gemini_wins: int,
        opponent_wins: int,
        null_hypothesis: float = 0.5
    ) -> StatisticalTest:
        """Perform binomial test for win rate significance."""
        n = gemini_wins + opponent_wins
        if n == 0:
            return StatisticalTest(
                "binomial", 0, 1.0, False, 0.0
            )

        result = stats.binomtest(
            gemini_wins, n, null_hypothesis, alternative='two-sided'
        )

        # Cohen's h for effect size
        p = gemini_wins / n
        effect_size = 2 * (np.arcsin(np.sqrt(p)) - np.arcsin(np.sqrt(null_hypothesis)))

        return StatisticalTest(
            test_name="binomial",
            statistic=gemini_wins,
            p_value=result.pvalue,
            significant=result.pvalue < (1 - self.confidence_level),
            effect_size=abs(effect_size)
        )

    def calculate_cohens_kappa(
        self,
        judgments: List[Dict[str, str]]
    ) -> float:
        """Calculate Cohen's Kappa for inter-judge agreement."""
        if len(judgments) < 2:
            return 0.0

        # Build agreement matrix
        judges = list(set(j['judge_model'] for j in judgments))
        if len(judges) < 2:
            return 0.0

        # Pairwise kappa and average
        kappas = []
        for i, judge1 in enumerate(judges):
            for judge2 in judges[i + 1:]:
                j1_votes = {j['prompt_id']: j['winner']
                           for j in judgments if j['judge_model'] == judge1}
                j2_votes = {j['prompt_id']: j['winner']
                           for j in judgments if j['judge_model'] == judge2}

                common_prompts = set(j1_votes.keys()) & set(j2_votes.keys())
                if len(common_prompts) < 10:
                    continue

                agreements = sum(1 for p in common_prompts
                               if j1_votes[p] == j2_votes[p])
                total = len(common_prompts)

                # Simple kappa calculation
                p_o = agreements / total
                # Assuming random agreement at 1/3 (3 choices)
                p_e = 1 / 3
                kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 0

                kappas.append(kappa)

        return np.mean(kappas) if kappas else 0.0

    def analyze_by_dimension(
        self,
        results: List[Dict[str, Any]],
        dimension: str
    ) -> Dict[str, WinRateAnalysis]:
        """Analyze win rates broken down by a dimension."""
        by_value = {}

        for result in results:
            value = result.get(dimension, 'unknown')
            if value not in by_value:
                by_value[value] = {'gemini': 0, 'opponent': 0, 'tie': 0}

            if result['result'] == 'gemini_wins':
                by_value[value]['gemini'] += 1
            elif result['result'] == 'opponent_wins':
                by_value[value]['opponent'] += 1
            else:
                by_value[value]['tie'] += 1

        analysis = {}
        for value, counts in by_value.items():
            analysis[value] = self.calculate_win_rate(
                counts['gemini'], counts['opponent'], counts['tie']
            )

        return analysis
```

### 9.2 Bias Detection

```python
# src/analysis/bias_detector.py
from typing import Dict, List, Any
from dataclasses import dataclass
import numpy as np
from scipy import stats

@dataclass
class BiasReport:
    bias_type: str
    detected: bool
    magnitude: float
    p_value: float
    description: str

class BiasDetector:
    """Detect systematic biases in evaluation results."""

    def detect_position_bias(
        self,
        judgments: List[Dict[str, Any]]
    ) -> BiasReport:
        """Detect if judges prefer Response A over Response B systematically."""
        a_wins = sum(1 for j in judgments if j['winner'] == 'response_a')
        b_wins = sum(1 for j in judgments if j['winner'] == 'response_b')

        if a_wins + b_wins == 0:
            return BiasReport(
                "position_bias", False, 0.0, 1.0,
                "No decisive judgments to analyze"
            )

        # Binomial test against 50%
        result = stats.binomtest(a_wins, a_wins + b_wins, 0.5)
        bias = abs(a_wins / (a_wins + b_wins) - 0.5)

        return BiasReport(
            bias_type="position_bias",
            detected=result.pvalue < 0.05,
            magnitude=bias,
            p_value=result.pvalue,
            description=f"Response A preferred {a_wins}/{a_wins + b_wins} times "
                       f"({'A' if a_wins > b_wins else 'B'} bias)"
        )

    def detect_length_bias(
        self,
        results: List[Dict[str, Any]]
    ) -> BiasReport:
        """Detect if longer responses tend to win."""
        winners_longer = 0
        losers_longer = 0

        for r in results:
            gemini_len = len(r.get('gemini_response', ''))
            opponent_len = len(r.get('opponent_response', ''))

            if r['result'] == 'gemini_wins':
                if gemini_len > opponent_len:
                    winners_longer += 1
                else:
                    losers_longer += 1
            elif r['result'] == 'opponent_wins':
                if opponent_len > gemini_len:
                    winners_longer += 1
                else:
                    losers_longer += 1

        if winners_longer + losers_longer == 0:
            return BiasReport(
                "length_bias", False, 0.0, 1.0,
                "No data to analyze"
            )

        result = stats.binomtest(winners_longer, winners_longer + losers_longer, 0.5)
        bias = abs(winners_longer / (winners_longer + losers_longer) - 0.5)

        return BiasReport(
            bias_type="length_bias",
            detected=result.pvalue < 0.05,
            magnitude=bias,
            p_value=result.pvalue,
            description=f"Longer response won {winners_longer}/{winners_longer + losers_longer} "
                       f"times (bias: {'longer' if winners_longer > losers_longer else 'shorter'})"
        )

    def detect_judge_model_bias(
        self,
        judgments: List[Dict[str, Any]]
    ) -> Dict[str, BiasReport]:
        """Detect if specific judge models have systematic biases."""
        by_judge = {}

        for j in judgments:
            judge = j['judge_model']
            if judge not in by_judge:
                by_judge[judge] = {'gemini': 0, 'opponent': 0, 'tie': 0}

            winner = j['winner']
            gemini_first = j.get('gemini_was_first', True)

            if winner == 'tie':
                by_judge[judge]['tie'] += 1
            elif (winner == 'response_a' and gemini_first) or \
                 (winner == 'response_b' and not gemini_first):
                by_judge[judge]['gemini'] += 1
            else:
                by_judge[judge]['opponent'] += 1

        reports = {}
        for judge, counts in by_judge.items():
            n = counts['gemini'] + counts['opponent']
            if n == 0:
                continue

            result = stats.binomtest(counts['gemini'], n, 0.5)
            bias = counts['gemini'] / n - 0.5

            reports[judge] = BiasReport(
                bias_type=f"judge_bias_{judge}",
                detected=result.pvalue < 0.05,
                magnitude=abs(bias),
                p_value=result.pvalue,
                description=f"{judge}: Gemini wins {counts['gemini']}/{n} "
                           f"({counts['gemini']/n*100:.1f}%)"
            )

        return reports

    def generate_full_bias_report(
        self,
        results: List[Dict[str, Any]],
        judgments: List[Dict[str, Any]]
    ) -> Dict[str, BiasReport]:
        """Generate comprehensive bias report."""
        report = {}

        report['position'] = self.detect_position_bias(judgments)
        report['length'] = self.detect_length_bias(results)

        judge_biases = self.detect_judge_model_bias(judgments)
        for judge, bias in judge_biases.items():
            report[f'judge_{judge}'] = bias

        return report
```

---

## 10. Reporting and Visualization

### 10.1 PDF Report Generator

```python
# src/reports/pdf_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

class PDFReportGenerator:
    """Generate comprehensive PDF evaluation reports."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self):
        """Add custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        ))
        self.styles.add(ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10
        ))

    def generate_report(
        self,
        results: Dict[str, Any],
        analysis: Dict[str, Any],
        charts_dir: Path
    ) -> Path:
        """Generate the full PDF report."""
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Title page
        story.extend(self._create_title_page(results))
        story.append(PageBreak())

        # Executive summary
        story.extend(self._create_executive_summary(results, analysis))
        story.append(PageBreak())

        # Overall results
        story.extend(self._create_overall_results(results))
        story.append(PageBreak())

        # Detailed breakdown
        story.extend(self._create_detailed_breakdown(analysis))
        story.append(PageBreak())

        # Weakness analysis
        story.extend(self._create_weakness_analysis(analysis))
        story.append(PageBreak())

        # Statistical appendix
        story.extend(self._create_statistical_appendix(analysis))

        doc.build(story)
        return self.output_path

    def _create_title_page(self, results: Dict[str, Any]) -> List:
        """Create report title page."""
        elements = []

        elements.append(Spacer(1, 2 * inch))
        elements.append(Paragraph(
            "Gemini Writing Evaluation Report",
            self.styles['CustomTitle']
        ))
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['Normal']
        ))
        elements.append(Paragraph(
            f"Total Comparisons: {results.get('total_comparisons', 0):,}",
            self.styles['Normal']
        ))

        return elements

    def _create_executive_summary(
        self,
        results: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> List:
        """Create executive summary section."""
        elements = []

        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))

        # Key findings
        elements.append(Paragraph("Key Findings:", self.styles['Heading3']))

        findings = [
            "Gemini 3.0 Pro shows competitive performance against frontier models",
            "Strongest performance in technical writing tasks",
            "Area for improvement: casual communication scenarios",
        ]

        for finding in findings:
            elements.append(Paragraph(f"* {finding}", self.styles['Normal']))

        elements.append(Spacer(1, 0.3 * inch))

        # Win rates summary table
        elements.append(Paragraph("Win Rates Summary:", self.styles['Heading3']))

        by_pair = results.get('by_pair', {})
        table_data = [['Model Pair', 'Win Rate', 'CI', 'n']]

        for pair, stats in by_pair.items():
            win_rate = f"{stats.get('win_rate', 0.5) * 100:.1f}%"
            ci = "+/- 4.3%"  # Would come from analysis
            n = str(stats.get('total', 0))
            table_data.append([pair, win_rate, ci, n])

        table = Table(table_data, colWidths=[2.5 * inch, 1 * inch, 1 * inch, 0.75 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)

        return elements

    def _create_overall_results(self, results: Dict[str, Any]) -> List:
        """Create overall results section."""
        elements = []
        elements.append(Paragraph("Overall Results", self.styles['SectionHeader']))
        # Add charts and detailed results
        return elements

    def _create_detailed_breakdown(self, analysis: Dict[str, Any]) -> List:
        """Create detailed breakdown by dimension."""
        elements = []
        elements.append(Paragraph("Detailed Breakdown", self.styles['SectionHeader']))
        # By occupation, industry, formality, etc.
        return elements

    def _create_weakness_analysis(self, analysis: Dict[str, Any]) -> List:
        """Create weakness analysis section."""
        elements = []
        elements.append(Paragraph("Weakness Analysis", self.styles['SectionHeader']))
        # Identified weaknesses and recommendations
        return elements

    def _create_statistical_appendix(self, analysis: Dict[str, Any]) -> List:
        """Create statistical appendix."""
        elements = []
        elements.append(Paragraph("Statistical Appendix", self.styles['SectionHeader']))
        # Detailed statistical tables
        return elements
```

---

## 11. CLI Interface

```python
# src/cli.py
import click
import asyncio
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config.settings import Settings
from .config.presets import get_preset, PRESETS
from .config.cost_estimator import CostEstimator
from .prompts.generator import PromptGenerator
from .api.openrouter_client import OpenRouterClient
from .eval.engine import EvaluationEngine
from .storage.database import ResultsDatabase
from .storage.checkpoint import CheckpointManager
from .tui.app import ProgressDashboard

console = Console()

@click.group()
def cli():
    """Gemini Writing Evaluation Framework CLI."""
    pass

@cli.command()
@click.option('--preset', '-p', type=int, default=6, help='Preset level (1-10)')
@click.option('--prompts', '-n', type=int, help='Number of prompts')
@click.option('--models', '-m', multiple=True, help='Specific models to evaluate')
@click.option('--dry-run', is_flag=True, help='Show estimate without running')
@click.option('--resume', type=click.Path(), help='Resume from previous run')
def run(preset, prompts, models, dry_run, resume):
    """Run an evaluation."""

    # Load settings
    settings = Settings()

    # Apply preset
    preset_config = get_preset(preset)
    if prompts:
        preset_config.num_prompts = prompts

    # Show estimate
    _show_estimate(preset_config, settings)

    if dry_run:
        return

    # Confirm
    if not click.confirm('Proceed with evaluation?'):
        return

    # Run evaluation
    asyncio.run(_run_evaluation(preset_config, settings, resume))

@cli.command()
def presets():
    """Show available presets."""
    table = Table(title="Evaluation Presets")
    table.add_column("Level", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Prompts")
    table.add_column("Cost")
    table.add_column("Time")
    table.add_column("Use Case")

    for level, config in PRESETS.items():
        table.add_row(
            str(level),
            config.name,
            str(config.num_prompts),
            config.estimated_cost,
            config.estimated_time,
            config.use_case
        )

    console.print(table)

@cli.command()
@click.argument('results_dir', type=click.Path(exists=True))
def view(results_dir):
    """View results from a previous run."""
    from .tui.viewer import ResultsViewer
    app = ResultsViewer()
    app.run()

@cli.command()
@click.argument('results_dirs', nargs=-1, type=click.Path(exists=True))
def compare(results_dirs):
    """Compare results across multiple runs."""
    console.print(f"Comparing {len(results_dirs)} runs...")
    # Implementation for cross-run comparison

def _show_estimate(preset_config, settings):
    """Show cost and time estimate."""
    estimator = CostEstimator()

    # Build model pairs
    model_pairs = []
    if settings.run_pro_tier:
        for c in settings.pro_competitors:
            model_pairs.append(('gemini-3-pro', c))
    if settings.run_flash_tier:
        for c in settings.flash_competitors:
            model_pairs.append(('gemini-3-flash', c))

    estimate = estimator.estimate(
        preset_config.num_prompts,
        model_pairs,
        settings.judge_models,
        preset_config.votes_per_judge
    )

    panel_content = f"""
[bold]Prompts:[/bold]              {preset_config.num_prompts}
[bold]Model pairs:[/bold]          {len(model_pairs)}
[bold]Total comparisons:[/bold]    {preset_config.num_prompts * len(model_pairs)}

[bold]Judge config:[/bold]         {len(settings.judge_models)} judges x {preset_config.votes_per_judge} votes x 2 personas
[bold]Total judge calls:[/bold]    {preset_config.num_prompts * len(model_pairs) * len(settings.judge_models) * preset_config.votes_per_judge * 2}

[bold cyan]ESTIMATED COST[/bold cyan]
  Response generation:  ${estimate.response_generation_min:.0f} - ${estimate.response_generation_max:.0f}
  Judging:              ${estimate.judging_min:.0f} - ${estimate.judging_max:.0f}
  [bold]Total:[/bold]                ${estimate.total_min:.0f} - ${estimate.total_max:.0f}

[bold cyan]ESTIMATED TIME[/bold cyan]
  {estimate.estimated_time_min} - {estimate.estimated_time_max}
"""

    console.print(Panel(panel_content, title="EVAL RUN ESTIMATE", border_style="blue"))

async def _run_evaluation(preset_config, settings, resume_path):
    """Run the evaluation pipeline."""
    # Create results directory
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    results_dir = Path(settings.results_dir) / f"eval_{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Initialize components
    api_client = OpenRouterClient(settings.openrouter_api_key)
    db = ResultsDatabase(str(results_dir / "results.db"))
    checkpoint = CheckpointManager(results_dir)

    # Generate prompts
    console.print("Generating prompts...")
    generator = PromptGenerator(settings.onet_db_path, settings.random_seed)
    prompts = generator.generate_prompts(preset_config.num_prompts)

    # Save prompts
    for prompt in prompts:
        await db.save_prompt(prompt)

    # Build config
    config = {
        'run_pro_tier': settings.run_pro_tier,
        'run_flash_tier': settings.run_flash_tier,
        'pro_competitors': settings.pro_competitors,
        'flash_competitors': settings.flash_competitors,
        'judge_models': settings.judge_models,
        'votes_per_judge': preset_config.votes_per_judge,
        'judge_personas': settings.judge_personas
    }

    # Run evaluation with TUI
    engine = EvaluationEngine(api_client, db, checkpoint, config)

    # Launch TUI
    app = ProgressDashboard()

    async def progress_callback(state):
        await app.update_progress(state)

    # Run in parallel with TUI
    import threading
    eval_thread = threading.Thread(
        target=lambda: asyncio.run(
            engine.run_evaluation(prompts, progress_callback)
        )
    )
    eval_thread.start()
    app.run()
    eval_thread.join()

    # Cleanup
    await api_client.close()
    db.close()

    console.print(f"\n[green]Evaluation complete![/green]")
    console.print(f"Results saved to: {results_dir}")

if __name__ == '__main__':
    cli()
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- Set up project structure and dependencies
- Implement O*NET data extraction
- Create prompt schema and basic generator
- Build OpenRouter API client with retry logic

### Phase 2: Core Evaluation (Week 2-3)
- Implement evaluation engine
- Build judge manager and vote aggregation
- Create SQLite storage layer
- Add checkpoint/resume capability

### Phase 3: User Interface (Week 3-4)
- Build CLI with click
- Implement progress dashboard TUI
- Create results viewer TUI
- Add cost estimation and presets

### Phase 4: Analysis & Reporting (Week 4-5)
- Implement statistical analysis
- Build bias detection
- Create PDF report generator
- Add visualization charts

### Phase 5: Polish & Testing (Week 5-6)
- Comprehensive testing
- Error handling improvements
- Documentation
- Performance optimization

---

## 13. Key Design Decisions

1. **Deterministic Randomization**: All randomization uses seeded RNGs for reproducibility
2. **Async Everything**: Core operations are async for parallelization
3. **Modular Architecture**: Clean separation of concerns for maintainability
4. **Rich TUI**: Modern terminal interface using textual/rich
5. **Comprehensive Logging**: Full audit trail for debugging and analysis
6. **Graceful Degradation**: System continues on partial failures
7. **Cost Awareness**: Real-time cost tracking and estimates
