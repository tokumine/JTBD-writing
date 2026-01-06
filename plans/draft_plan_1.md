# Gemini Writing Evaluation Framework - Implementation Plan

## Executive Summary

This document provides a comprehensive implementation plan for building a robust, production-grade evaluation framework to compare Gemini 3.0 Pro and Flash against competing frontier LLMs on realistic professional writing tasks derived from the O*NET occupational database.

The evaluation will leverage:
- **O*NET task-level data**: ~20,000 individual writing tasks across 1,000+ US occupations
- **NAICS industry codes**: Systematic industry diversity within occupations
- **Real company databases**: Authentic organizational context using actual company names
- **OpenRouter API**: Unified interface to all evaluated models
- **Multi-judge ensemble**: Claude Opus 4.5, GPT-5.2, and Gemini 3.0 Pro as independent judges
- **Dual persona judging**: Both writing expert and target recipient perspectives
- **Best-of-5 majority voting**: Robust aggregation with majority-of-majorities across judges

---

## 1. Data Acquisition & Preparation

### 1.1 O*NET Database Integration

**Objective**: Extract all writing-related tasks from the O*NET database at the deepest granularity (task-level).

**Implementation**:

```python
# onet_downloader.py
import requests
import zipfile
import pandas as pd
from pathlib import Path

class OnetDownloader:
    """Downloads and extracts O*NET database files"""

    ONET_BASE_URL = "https://www.onetcenter.org/dl_files/database/"
    CURRENT_VERSION = "28_3"  # Update as needed

    def __init__(self, data_dir: Path = Path("data/onet")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download_database(self):
        """Download complete O*NET database"""
        url = f"{self.ONET_BASE_URL}db_{self.CURRENT_VERSION}_excel.zip"
        zip_path = self.data_dir / "onet_database.zip"

        print(f"Downloading O*NET database version {self.CURRENT_VERSION}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print("Extracting database files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.data_dir)

        print(f"O*NET database downloaded to {self.data_dir}")
        return self.data_dir
```

**Key O*NET Files**:
- `Task Statements.xlsx`: Individual task descriptions per occupation
- `Occupation Data.xlsx`: Occupation metadata (title, code, job zone)
- `Task Categories.xlsx`: Task type categorization
- `Work Activities.xlsx`: Generalized work activities including "Communicating with People Outside Organization"

**Data Schema**:
```python
# onet_models.py
from pydantic import BaseModel
from typing import Optional

class OnetTask(BaseModel):
    """Individual O*NET task statement"""
    task_id: str  # e.g., "11-1011.00-T1"
    occupation_code: str  # e.g., "11-1011.00"
    occupation_title: str  # e.g., "Chief Executives"
    task_statement: str  # e.g., "Direct, plan, or implement policies and strategies"
    task_type: Optional[str]  # If categorized
    job_zone: int  # 1-5 skill level

class OnetOccupation(BaseModel):
    """O*NET occupation metadata"""
    code: str
    title: str
    description: str
    job_zone: int  # Education/experience level 1-5
    job_zone_label: str  # e.g., "Extensive preparation needed"
```

**Writing Task Filtering**:

```python
# onet_processor.py
import pandas as pd
from typing import List

class WritingTaskExtractor:
    """Filters O*NET tasks to identify writing-related activities"""

    # Keywords that indicate writing tasks
    WRITING_KEYWORDS = [
        "write", "draft", "prepare", "compose", "document",
        "correspondence", "email", "memo", "report", "letter",
        "communication", "message", "proposal", "brief",
        "summary", "review", "edit", "revise"
    ]

    def __init__(self, onet_data_dir: Path):
        self.data_dir = onet_data_dir
        self.tasks_df = None
        self.occupations_df = None

    def load_data(self):
        """Load O*NET data files"""
        self.tasks_df = pd.read_excel(
            self.data_dir / "Task Statements.xlsx"
        )
        self.occupations_df = pd.read_excel(
            self.data_dir / "Occupation Data.xlsx"
        )

    def extract_writing_tasks(self) -> List[OnetTask]:
        """Filter tasks containing writing-related activities"""
        writing_tasks = []

        for _, row in self.tasks_df.iterrows():
            task_text = row['Task'].lower()

            # Check if task involves writing
            if any(keyword in task_text for keyword in self.WRITING_KEYWORDS):
                occupation = self.occupations_df[
                    self.occupations_df['O*NET-SOC Code'] == row['O*NET-SOC Code']
                ].iloc[0]

                task = OnetTask(
                    task_id=f"{row['O*NET-SOC Code']}-T{row['Task ID']}",
                    occupation_code=row['O*NET-SOC Code'],
                    occupation_title=occupation['Title'],
                    task_statement=row['Task'],
                    job_zone=occupation['Job Zone']
                )
                writing_tasks.append(task)

        return writing_tasks
```

### 1.2 NAICS Industry Code Integration

**Objective**: Provide systematic industry diversity by mapping occupations to NAICS codes.

**Data Source**: US Census Bureau NAICS classification system

**Implementation**:

```python
# naics_downloader.py
import requests
import pandas as pd

class NAICSDownloader:
    """Downloads NAICS industry classification data"""

    NAICS_URL = "https://www.census.gov/naics/2022NAICS/2022_NAICS_Descriptions.xlsx"

    def __init__(self, data_dir: Path = Path("data/naics")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download_naics(self):
        """Download NAICS classification codes and descriptions"""
        filepath = self.data_dir / "naics_2022.xlsx"

        print("Downloading NAICS 2022 codes...")
        response = requests.get(self.NAICS_URL)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"NAICS data downloaded to {filepath}")
        return filepath

# naics_models.py
class NAICSCode(BaseModel):
    """NAICS industry classification"""
    code: str  # e.g., "541512"
    title: str  # e.g., "Computer Systems Design Services"
    sector: str  # 2-digit code, e.g., "54" (Professional Services)
    sector_title: str
    description: Optional[str]

class NAICSProcessor:
    """Process and organize NAICS codes"""

    def __init__(self, naics_file: Path):
        self.df = pd.read_excel(naics_file)
        self.codes = self._parse_codes()

    def _parse_codes(self) -> List[NAICSCode]:
        """Parse NAICS codes into structured format"""
        codes = []
        for _, row in self.df.iterrows():
            code = NAICSCode(
                code=str(row['Code']),
                title=row['Title'],
                sector=str(row['Code'])[:2],
                sector_title=self._get_sector_title(str(row['Code'])[:2]),
                description=row.get('Description', None)
            )
            codes.append(code)
        return codes

    def sample_industries(self, n: int, level: int = 6) -> List[NAICSCode]:
        """
        Sample diverse industries evenly across sectors

        Args:
            n: Number of industries to sample
            level: Digit level (2=sector, 3=subsector, 6=industry)
        """
        # Filter to specified digit level
        level_codes = [c for c in self.codes if len(c.code) == level]

        # Group by sector for even distribution
        from collections import defaultdict
        by_sector = defaultdict(list)
        for code in level_codes:
            by_sector[code.sector].append(code)

        # Sample evenly across sectors
        samples = []
        sectors = list(by_sector.keys())
        per_sector = n // len(sectors)

        for sector in sectors:
            sector_samples = random.sample(
                by_sector[sector],
                min(per_sector, len(by_sector[sector]))
            )
            samples.extend(sector_samples)

        # Fill remaining slots randomly
        if len(samples) < n:
            remaining = [c for c in level_codes if c not in samples]
            samples.extend(random.sample(remaining, n - len(samples)))

        return samples[:n]
```

### 1.3 Company Database Integration

**Objective**: Ground prompts in reality using actual company names mapped to NAICS codes.

**Data Sources**:
1. **SEC EDGAR**: Public company data with industry codes
2. **Crunchbase Open Data**: Startups and private companies
3. **Fortune 500/1000 Lists**: Well-known large companies
4. **Wikipedia Lists**: Curated company lists by industry

**Implementation**:

```python
# company_database.py
import sqlite3
from typing import List, Optional
from enum import Enum

class CompanySize(Enum):
    STARTUP = "startup"  # <50 employees
    SMALL = "small"  # 50-500
    MEDIUM = "medium"  # 500-5000
    LARGE = "large"  # 5000-50000
    ENTERPRISE = "enterprise"  # 50000+

class Company(BaseModel):
    """Real company entity"""
    id: str
    name: str
    naics_code: str
    naics_title: str
    size: CompanySize
    is_public: bool
    founded_year: Optional[int]
    headquarters_location: Optional[str]
    description: Optional[str]
    training_cutoff_concern: bool  # Founded after typical LLM training cutoffs

class CompanyDatabase:
    """Manages company data for prompt grounding"""

    def __init__(self, db_path: Path = Path("data/companies.db")):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_schema()

    def _create_schema(self):
        """Create company database schema"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                naics_code TEXT NOT NULL,
                naics_title TEXT,
                size TEXT NOT NULL,
                is_public BOOLEAN,
                founded_year INTEGER,
                headquarters_location TEXT,
                description TEXT,
                training_cutoff_concern BOOLEAN DEFAULT FALSE
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_naics ON companies(naics_code)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_size ON companies(size)
        """)
        self.conn.commit()

    def get_companies_for_industry(
        self,
        naics_code: str,
        size_distribution: Optional[List[CompanySize]] = None,
        n: int = 5
    ) -> List[Company]:
        """
        Get diverse companies for a NAICS industry

        Args:
            naics_code: 6-digit NAICS code or 2-4 digit sector/subsector
            size_distribution: Desired company sizes, defaults to even mix
            n: Number of companies to return
        """
        if size_distribution is None:
            size_distribution = [
                CompanySize.STARTUP,
                CompanySize.SMALL,
                CompanySize.MEDIUM,
                CompanySize.LARGE,
                CompanySize.ENTERPRISE
            ]

        # Match NAICS code at appropriate level (prefix matching)
        query = """
            SELECT * FROM companies
            WHERE naics_code LIKE ? AND size = ?
            ORDER BY RANDOM()
            LIMIT ?
        """

        companies = []
        per_size = max(1, n // len(size_distribution))

        for size in size_distribution:
            cursor = self.conn.execute(
                query,
                (f"{naics_code}%", size.value, per_size)
            )
            rows = cursor.fetchall()
            companies.extend([self._row_to_company(row) for row in rows])

        return companies[:n]
```

**Company Data Scraping Scripts**:

```python
# scrapers/sec_edgar.py
import requests
from sec_api import QueryApi

def scrape_sec_companies():
    """Scrape public company data from SEC EDGAR"""
    # Use SEC EDGAR API or screen scraping
    # Extract: company name, CIK, SIC code (map to NAICS), size metrics
    pass

# scrapers/fortune_lists.py
def scrape_fortune_lists():
    """Scrape Fortune 500/1000 company lists"""
    # Wikipedia has reliable Fortune lists with industry data
    pass
```

### 1.4 Name Database

**Objective**: Generate realistic, demographically diverse names for writers and recipients.

**Data Source**: US Census Bureau name frequency data + international name databases

**Implementation**:

```python
# name_database.py
from typing import List, Optional
from enum import Enum

class NameGender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"

class NameEthnicity(Enum):
    DIVERSE = "diverse"  # Mixed/unknown
    EAST_ASIAN = "east_asian"
    SOUTH_ASIAN = "south_asian"
    HISPANIC = "hispanic"
    AFRICAN_AMERICAN = "african_american"
    MIDDLE_EASTERN = "middle_eastern"
    EUROPEAN = "european"

class PersonName(BaseModel):
    first_name: str
    last_name: str
    gender: NameGender
    ethnicity: NameEthnicity
    age_cohort: Optional[str]  # "GenZ", "Millennial", "GenX", "Boomer"
    formality_variants: List[str]  # ["Dr. Smith", "Jane Smith", "Jane", "J. Smith"]

class NameDatabase:
    """Database of realistic names with demographic metadata"""

    def __init__(self, db_path: Path = Path("data/names.db")):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_schema()
        self._load_census_data()

    def _load_census_data(self):
        """Load US Census name frequency data"""
        # First names by decade (to match age cohorts)
        # Last names by ethnicity
        pass

    def generate_name(
        self,
        age_cohort: Optional[str] = None,
        ethnicity: Optional[NameEthnicity] = None,
        gender: Optional[NameGender] = None,
        formality: str = "medium"
    ) -> PersonName:
        """
        Generate a realistic name with specified demographics

        Args:
            age_cohort: Target generation (affects first name popularity)
            ethnicity: Ethnic background (affects name selection)
            gender: Gender (affects first name)
            formality: How the name is formatted in prompt
        """
        # Sample from appropriate demographic distributions
        pass

    def get_formality_variant(self, name: PersonName, level: str) -> str:
        """
        Return name in appropriate formality format

        Levels:
        - "very_formal": "Dr. Williams" or "Michael T. Williams"
        - "formal": "Michael Williams"
        - "medium": "Mike Williams"
        - "casual": "Mike"
        """
        pass
```

---

## 2. Prompt Generation Pipeline

### 2.1 Three-Phase Prompt Generation

The prompt generation follows a three-phase approach to maximize diversity and realism:

**Phase 1: LLM-Based Persona/Context Generation (Offline)**
**Phase 2: Algorithmic Combination (Deterministic)**
**Phase 3: LLM Enrichment (For Complex Scenarios)**

### 2.2 Prompt Schema

```python
# prompt_models.py
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class CommunicationChannel(Enum):
    EMAIL = "email"
    MEMO = "memo"
    REPORT = "report"
    LETTER = "letter"
    MESSAGE = "message"
    PROPOSAL = "proposal"
    SUMMARY = "summary"
    ANNOUNCEMENT = "announcement"
    SLACK = "slack"
    OTHER = "other"

class FormalityLevel(Enum):
    VERY_CASUAL = 1
    CASUAL = 2
    NEUTRAL = 3
    FORMAL = 4
    VERY_FORMAL = 5

class UrgencyLevel(Enum):
    ROUTINE = "routine"
    MODERATE = "moderate"
    URGENT = "urgent"
    CRITICAL = "critical"

class AudienceSize(Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"  # 2-5 people
    TEAM = "team"  # 5-20
    DEPARTMENT = "department"  # 20-100
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class RelationshipContext(Enum):
    FIRST_CONTACT = "first_contact"
    EARLY_RELATIONSHIP = "early_relationship"
    ESTABLISHED = "established"
    LONG_TERM = "long_term"

class EmotionalContext(Enum):
    ROUTINE = "routine"
    POSITIVE = "positive"  # Celebration, good news
    NEGATIVE = "negative"  # Bad news, rejection
    CRISIS = "crisis"
    CONFLICT = "conflict"
    SENSITIVE = "sensitive"  # HR, legal, confidential

class WriterPersona(BaseModel):
    """The person writing the message"""
    name: str  # Full realistic name
    role: str  # From O*NET occupation
    age: int
    generation: str  # "GenZ", "Millennial", "GenX", "Boomer"
    seniority_level: str  # "junior", "mid", "senior", "executive"
    years_experience: int
    writing_skill: str  # "developing", "competent", "advanced"
    company: Company
    email: Optional[str]

class RecipientPersona(BaseModel):
    """The target audience/recipient"""
    name: Optional[str]  # Specific person or None for groups
    role: Optional[str]
    relationship_to_writer: str  # "boss", "peer", "report", "client", "external"
    seniority_level: Optional[str]
    company: Optional[Company]  # May be same or different from writer
    english_variant: str  # "en-US", "en-GB", "en-AU", "non-native"
    audience_size: AudienceSize

class PromptContext(BaseModel):
    """Additional context for the writing task"""
    temporal_context: Optional[str]  # "Q4 2024", "Friday deadline", etc.
    prior_message: Optional[str]  # For reply scenarios
    attachments: Optional[List[Dict[str, str]]]  # Mock attachment summaries
    tone_example: Optional[str]  # Example writing to match
    draft_to_revise: Optional[str]  # For editing tasks
    constraints: List[str]  # Explicit requirements: length, format, exclusions
    competing_objectives: Optional[List[str]]  # Trade-offs to navigate

class WritingPrompt(BaseModel):
    """Complete prompt for writing evaluation"""
    prompt_id: str
    onet_task: OnetTask
    industry: NAICSCode
    company: Company
    writer: WriterPersona
    recipient: RecipientPersona
    channel: CommunicationChannel
    formality: FormalityLevel
    urgency: UrgencyLevel
    relationship: RelationshipContext
    emotional_context: EmotionalContext
    context: PromptContext
    prompt_text: str  # The actual prompt given to models
    generation_method: str  # "phase1_llm", "phase2_algo", "phase3_enriched"
    random_seed: int  # For reproducibility
    metadata: Dict[str, Any]  # Additional tracking fields

    # Metadata flags
    is_revision_task: bool = False
    is_reply_task: bool = False
    has_constraints: bool = False
    is_sensitive: bool = False
    sensitive_category: Optional[str] = None
```

### 2.3 Phase 1: LLM Persona Generation

**Objective**: Use LLMs to generate diverse persona and context variations offline.

```python
# prompt_generator_phase1.py
import asyncio
from typing import List

class Phase1PersonaGenerator:
    """Generate diverse personas using LLMs (offline preprocessing)"""

    def __init__(self, openrouter_client):
        self.client = openrouter_client
        # Use the models being evaluated for generation (bias note in docs)
        self.generation_models = [
            "google/gemini-3.0-pro",
            "anthropic/claude-opus-4.5",
            "openai/gpt-5.2"
        ]

    async def generate_persona_variations(
        self,
        onet_task: OnetTask,
        n_variations: int = 10
    ) -> List[WriterPersona]:
        """
        Generate diverse writer personas for a given occupation

        Uses all eval models in rotation to avoid bias
        """
        personas = []

        prompt = f"""
        Generate {n_variations} diverse, realistic writer personas for the occupation:
        {onet_task.occupation_title}

        For each persona, provide:
        - Realistic first and last name (vary ethnicity, gender, age-appropriate names)
        - Age (25-65)
        - Generation (GenZ, Millennial, GenX, Boomer)
        - Seniority level and years of experience
        - Writing skill level

        Ensure maximum diversity across age, background, and experience.
        Output as JSON array.
        """

        # Rotate through generation models
        model_idx = 0
        for i in range(n_variations):
            model = self.generation_models[model_idx % len(self.generation_models)]
            response = await self.client.generate(model, prompt)
            # Parse and store persona
            model_idx += 1

        return personas
```

### 2.4 Phase 2: Algorithmic Combination

**Objective**: Deterministically combine O*NET tasks with industries, companies, personas, and context dimensions.

```python
# prompt_generator_phase2.py
import random
from typing import List

class Phase2AlgorithmicGenerator:
    """Deterministic prompt generation via algorithmic combination"""

    def __init__(
        self,
        onet_tasks: List[OnetTask],
        naics_processor: NAICSProcessor,
        company_db: CompanyDatabase,
        name_db: NameDatabase,
        random_seed: int = 42
    ):
        self.onet_tasks = onet_tasks
        self.naics = naics_processor
        self.companies = company_db
        self.names = name_db
        self.rng = random.Random(random_seed)

    def generate_prompts(self, n: int) -> List[WritingPrompt]:
        """
        Generate N prompts by algorithmic combination

        Ensures even distribution across:
        - Occupations (job zones)
        - Industries (NAICS sectors)
        - Company sizes
        - Formality levels
        - Age cohorts
        - Urgency levels
        - Relationship contexts
        """
        prompts = []

        # Stratified sampling across key dimensions
        for i in range(n):
            # Select O*NET task (stratify by job zone for even skill distribution)
            task = self._sample_task_stratified()

            # Select industry (stratify by NAICS sector)
            industry = self._sample_industry_stratified()

            # Select company in that industry (stratify by size)
            company = self._sample_company_stratified(industry)

            # Generate writer persona
            writer = self._generate_writer(task, company)

            # Generate recipient persona
            recipient = self._generate_recipient(writer)

            # Assign context dimensions
            formality = self._sample_enum(FormalityLevel)
            urgency = self._sample_enum(UrgencyLevel)
            relationship = self._sample_enum(RelationshipContext)
            emotional = self._sample_enum(EmotionalContext)
            channel = self._infer_channel(task.task_statement)

            # Generate base prompt text
            prompt_text = self._construct_prompt_text(
                task, writer, recipient, formality, urgency
            )

            # Create prompt object
            prompt = WritingPrompt(
                prompt_id=f"prompt_{i:06d}",
                onet_task=task,
                industry=industry,
                company=company,
                writer=writer,
                recipient=recipient,
                channel=channel,
                formality=formality,
                urgency=urgency,
                relationship=relationship,
                emotional_context=emotional,
                context=PromptContext(constraints=[]),
                prompt_text=prompt_text,
                generation_method="phase2_algo",
                random_seed=self.rng.randint(0, 2**31),
                metadata={}
            )

            prompts.append(prompt)

        return prompts

    def _construct_prompt_text(
        self,
        task: OnetTask,
        writer: WriterPersona,
        recipient: RecipientPersona,
        formality: FormalityLevel,
        urgency: UrgencyLevel
    ) -> str:
        """Construct the actual prompt text given to models"""

        # Base task description
        prompt_parts = [
            f"You are {writer.name}, {writer.role} at {writer.company.name}.",
            f"",
            f"Task: {task.task_statement}",
            f"",
        ]

        # Recipient context
        if recipient.name:
            prompt_parts.append(f"Recipient: {recipient.name}, {recipient.role}")
            if recipient.company and recipient.company.name != writer.company.name:
                prompt_parts.append(f"Company: {recipient.company.name}")
        else:
            prompt_parts.append(f"Audience: {recipient.audience_size.value}")

        # Formality guidance (implicit, from persona context)
        if formality == FormalityLevel.VERY_FORMAL:
            prompt_parts.append("This requires formal, professional communication.")
        elif formality == FormalityLevel.VERY_CASUAL:
            prompt_parts.append("This is internal and casual communication is appropriate.")

        # Urgency context
        if urgency == UrgencyLevel.URGENT:
            prompt_parts.append("This is time-sensitive and needs immediate attention.")
        elif urgency == UrgencyLevel.CRITICAL:
            prompt_parts.append("This is critical and requires urgent action.")

        return "\n".join(prompt_parts)
```

### 2.5 Phase 3: LLM Enrichment

**Objective**: Add realistic detail to context-rich prompts that need more sophisticated scenarios.

```python
# prompt_generator_phase3.py

class Phase3Enrichment:
    """LLM-based enrichment for complex scenarios"""

    def __init__(self, openrouter_client):
        self.client = openrouter_client

    async def enrich_prompt(self, base_prompt: WritingPrompt) -> WritingPrompt:
        """
        Add rich contextual details to prompts that need them

        Examples:
        - Generate mock attachment content
        - Create prior email threads for reply scenarios
        - Add competing objectives for nuanced tasks
        - Create tone examples for matching tasks
        """

        enrichment_needed = self._assess_enrichment_need(base_prompt)

        if not enrichment_needed:
            return base_prompt

        # Generate enrichment via LLM
        if base_prompt.is_reply_task:
            base_prompt.context.prior_message = await self._generate_prior_message(
                base_prompt
            )

        if base_prompt.emotional_context == EmotionalContext.SENSITIVE:
            base_prompt.context.competing_objectives = await self._generate_tensions(
                base_prompt
            )

        # Add mock attachments for relevant tasks
        if "report" in base_prompt.onet_task.task_statement.lower():
            base_prompt.context.attachments = await self._generate_mock_attachment(
                base_prompt
            )

        base_prompt.generation_method = "phase3_enriched"
        return base_prompt

    async def _generate_prior_message(self, prompt: WritingPrompt) -> str:
        """Generate realistic prior message for reply scenarios"""
        llm_prompt = f"""
        Generate a realistic email message that would require this response:
        Context: {prompt.onet_task.task_statement}
        Writer: {prompt.writer.name} ({prompt.writer.role})
        Will respond to: {prompt.recipient.name} ({prompt.recipient.role})

        Generate the incoming message that requires a response.
        """
        response = await self.client.generate("anthropic/claude-opus-4.5", llm_prompt)
        return response.text
```

### 2.6 Prompt Storage

```python
# prompt_storage.py
import sqlite3
import json

class PromptDatabase:
    """Store and retrieve generated prompts"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_schema()

    def _create_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                prompt_id TEXT PRIMARY KEY,
                onet_code TEXT NOT NULL,
                onet_title TEXT,
                naics_code TEXT,
                company_name TEXT,
                formality INTEGER,
                urgency TEXT,
                job_zone INTEGER,
                generation_method TEXT,
                is_sensitive BOOLEAN,
                random_seed INTEGER,
                prompt_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for filtering
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_onet ON prompts(onet_code)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_naics ON prompts(naics_code)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_zone ON prompts(job_zone)
        """)

    def store_prompt(self, prompt: WritingPrompt):
        """Store a generated prompt"""
        self.conn.execute("""
            INSERT INTO prompts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prompt.prompt_id,
            prompt.onet_task.occupation_code,
            prompt.onet_task.occupation_title,
            prompt.industry.code,
            prompt.company.name,
            prompt.formality.value,
            prompt.urgency.value,
            prompt.onet_task.job_zone,
            prompt.generation_method,
            prompt.is_sensitive,
            prompt.random_seed,
            prompt.json(),
            None  # created_at auto-populated
        ))
        self.conn.commit()
```

---

## 3. Evaluation Infrastructure

### 3.1 OpenRouter API Client

```python
# openrouter_client.py
import httpx
import asyncio
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

class OpenRouterClient:
    """Async client for OpenRouter API with robust error handling"""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response from a model via OpenRouter

        Includes automatic retry with exponential backoff
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limit hit - will retry via tenacity
                raise
            elif e.response.status_code >= 500:
                # Server error - will retry
                raise
            else:
                # Client error - don't retry
                raise

    async def close(self):
        await self.client.aclose()
```

### 3.2 Model Response Generator

```python
# response_generator.py
from typing import List, Dict
import asyncio

class ResponseGenerator:
    """Generate model responses for evaluation prompts"""

    def __init__(self, openrouter_client: OpenRouterClient):
        self.client = openrouter_client

    async def generate_response(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> ModelResponse:
        """Generate a single model response"""

        start_time = time.time()

        try:
            result = await self.client.generate(
                model=model,
                prompt=prompt.prompt_text,
                temperature=1.0  # Allow natural variation
            )

            response = ModelResponse(
                prompt_id=prompt.prompt_id,
                model=model,
                response_text=result['choices'][0]['message']['content'],
                response_time=time.time() - start_time,
                token_count=result['usage']['total_tokens'],
                completion_tokens=result['usage']['completion_tokens'],
                status="success",
                metadata={}
            )

        except Exception as e:
            response = ModelResponse(
                prompt_id=prompt.prompt_id,
                model=model,
                response_text="",
                response_time=time.time() - start_time,
                token_count=0,
                completion_tokens=0,
                status="failed",
                error=str(e),
                metadata={}
            )

        return response

class ModelResponse(BaseModel):
    """Model's response to a writing prompt"""
    prompt_id: str
    model: str
    response_text: str
    response_time: float  # seconds
    token_count: int
    completion_tokens: int
    status: str  # "success", "failed", "refusal"
    error: Optional[str] = None
    metadata: Dict[str, Any]

    # Computed fields
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    has_bullet_points: Optional[bool] = None
    has_greeting: Optional[bool] = None
    has_signature: Optional[bool] = None
```

### 3.3 Judge Implementation

**Objective**: Implement dual-persona, multi-model ensemble judging with best-of-5 voting.

```python
# judge.py
from typing import List, Dict
from enum import Enum

class JudgePersona(Enum):
    WRITING_EXPERT = "writing_expert"
    TARGET_RECIPIENT = "target_recipient"

class JudgeVerdict(Enum):
    MODEL_A_WINS = "model_a"
    MODEL_B_WINS = "model_b"
    TIE = "tie"

class Judge:
    """Individual judge (one model + one persona)"""

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        judge_model: str,
        persona: JudgePersona
    ):
        self.client = openrouter_client
        self.model = judge_model
        self.persona = persona

    async def judge_comparison(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        n_votes: int = 5
    ) -> JudgmentResult:
        """
        Judge a pairwise comparison with best-of-N voting

        Args:
            prompt: The original writing prompt
            response_a: First model's response
            response_b: Second model's response
            n_votes: Number of independent judgments (default 5)

        Returns:
            JudgmentResult with majority verdict and all individual votes
        """
        votes = []

        for i in range(n_votes):
            # Shuffle response order to eliminate position bias
            # Use deterministic shuffle based on prompt seed + vote number
            shuffle_seed = prompt.random_seed + i
            rng = random.Random(shuffle_seed)
            if rng.random() < 0.5:
                order = ("A", "B")
                resp_1, resp_2 = response_a, response_b
            else:
                order = ("B", "A")
                resp_1, resp_2 = response_b, response_a

            # Generate judge prompt
            judge_prompt = self._construct_judge_prompt(
                prompt, resp_1, resp_2, order
            )

            # Get judgment
            result = await self.client.generate(
                model=self.model,
                prompt=judge_prompt,
                temperature=0.3  # Low temp for consistency
            )

            # Parse verdict
            verdict = self._parse_verdict(result, order, response_a.model, response_b.model)
            votes.append(verdict)

        # Compute majority
        a_votes = votes.count(JudgeVerdict.MODEL_A_WINS)
        b_votes = votes.count(JudgeVerdict.MODEL_B_WINS)
        tie_votes = votes.count(JudgeVerdict.TIE)

        if a_votes > b_votes and a_votes > tie_votes:
            majority = JudgeVerdict.MODEL_A_WINS
        elif b_votes > a_votes and b_votes > tie_votes:
            majority = JudgeVerdict.MODEL_B_WINS
        else:
            majority = JudgeVerdict.TIE

        return JudgmentResult(
            judge_model=self.model,
            persona=self.persona,
            votes=votes,
            majority_verdict=majority,
            model_a=response_a.model,
            model_b=response_b.model,
            vote_distribution={
                "model_a": a_votes,
                "model_b": b_votes,
                "tie": tie_votes
            }
        )

    def _construct_judge_prompt(
        self,
        prompt: WritingPrompt,
        resp_1: ModelResponse,
        resp_2: ModelResponse,
        order: tuple
    ) -> str:
        """Construct judge evaluation prompt with full context"""

        if self.persona == JudgePersona.WRITING_EXPERT:
            persona_context = """
You are an expert writing coach and professional communications consultant.
Evaluate the quality, clarity, professionalism, and craft of the writing.
Consider: tone appropriateness, structure, length, authenticity, avoidance of clichés.
"""
        else:  # TARGET_RECIPIENT
            persona_context = f"""
You are {prompt.recipient.name or 'the intended recipient'} receiving this communication.
Evaluate effectiveness, relevance, actionability, and appropriateness for YOU specifically.
Consider: Would this achieve its purpose? Is it appropriate for your relationship?
"""

        judge_text = f"""
{persona_context}

## SCENARIO
Writer: {prompt.writer.name}, {prompt.writer.role} at {prompt.company.name}
Recipient: {prompt.recipient.name or prompt.recipient.audience_size.value}
Formality: {prompt.formality.name}
Context: {prompt.emotional_context.name}

## TASK
{prompt.onet_task.task_statement}

## FULL PROMPT
{prompt.prompt_text}

## RESPONSE {order[0]}
{resp_1.response_text}

## RESPONSE {order[1]}
{resp_2.response_text}

## EVALUATION CRITERIA
- Writing quality and clarity
- Appropriate length for the task
- Tone appropriateness
- Effectiveness for the intended purpose
- Task completion
- Authenticity (sounds human, not AI-generated)
- Avoidance of AI clichés and boilerplate
- Adherence to any explicit constraints

## YOUR JUDGMENT
Which response is better overall? Consider all criteria above.

Respond with:
- "Response {order[0]} is better" OR
- "Response {order[1]} is better" OR
- "Tie - both equally good/bad"

Then provide 2-3 sentences explaining your reasoning.
"""
        return judge_text

    def _parse_verdict(
        self,
        result: Dict[str, Any],
        order: tuple,
        model_a_name: str,
        model_b_name: str
    ) -> JudgeVerdict:
        """Parse judge's response into structured verdict"""
        text = result['choices'][0]['message']['content'].lower()

        # Map shuffled response back to actual models
        if f"response {order[0].lower()} is better" in text:
            # First response shown was better
            return JudgeVerdict.MODEL_A_WINS if order[0] == "A" else JudgeVerdict.MODEL_B_WINS
        elif f"response {order[1].lower()} is better" in text:
            # Second response shown was better
            return JudgeVerdict.MODEL_B_WINS if order[1] == "B" else JudgeVerdict.MODEL_A_WINS
        else:
            return JudgeVerdict.TIE


class JudgmentResult(BaseModel):
    """Result from a single judge's best-of-N evaluation"""
    judge_model: str
    persona: JudgePersona
    votes: List[JudgeVerdict]
    majority_verdict: JudgeVerdict
    model_a: str
    model_b: str
    vote_distribution: Dict[str, int]


class EnsembleJudge:
    """Ensemble of multiple judge models with dual personas"""

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        judge_models: List[str] = None,
        n_votes: int = 5
    ):
        self.client = openrouter_client
        self.n_votes = n_votes

        if judge_models is None:
            judge_models = [
                "anthropic/claude-opus-4.5",
                "openai/gpt-5.2",
                "google/gemini-3.0-pro"
            ]

        # Create all judge instances (model × persona combinations)
        self.judges = []
        for model in judge_models:
            for persona in JudgePersona:
                self.judges.append(Judge(self.client, model, persona))

    async def evaluate_comparison(
        self,
        prompt: WritingPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse
    ) -> ComparisonResult:
        """
        Full ensemble evaluation with majority-of-majorities aggregation

        Each judge gives best-of-N verdict → majority across all judges
        """
        # Parallel judging
        judgment_tasks = [
            judge.judge_comparison(prompt, response_a, response_b, self.n_votes)
            for judge in self.judges
        ]

        judgments = await asyncio.gather(*judgment_tasks)

        # Aggregate: majority of majorities
        a_wins = sum(1 for j in judgments if j.majority_verdict == JudgeVerdict.MODEL_A_WINS)
        b_wins = sum(1 for j in judgments if j.majority_verdict == JudgeVerdict.MODEL_B_WINS)
        ties = sum(1 for j in judgments if j.majority_verdict == JudgeVerdict.TIE)

        if a_wins > b_wins and a_wins > ties:
            final_verdict = JudgeVerdict.MODEL_A_WINS
        elif b_wins > a_wins and b_wins > ties:
            final_verdict = JudgeVerdict.MODEL_B_WINS
        else:
            final_verdict = JudgeVerdict.TIE

        return ComparisonResult(
            prompt_id=prompt.prompt_id,
            model_a=response_a.model,
            model_b=response_b.model,
            final_verdict=final_verdict,
            individual_judgments=judgments,
            judge_agreement=self._compute_agreement(judgments)
        )

    def _compute_agreement(self, judgments: List[JudgmentResult]) -> float:
        """Compute Cohen's Kappa for inter-judge agreement"""
        # Implementation of Cohen's Kappa across all judge pairs
        # This measures reliability of the judging process
        pass


class ComparisonResult(BaseModel):
    """Final aggregated comparison result"""
    prompt_id: str
    model_a: str
    model_b: str
    final_verdict: JudgeVerdict
    individual_judgments: List[JudgmentResult]
    judge_agreement: float  # Cohen's Kappa
```

### 3.4 Evaluation Orchestrator

```python
# evaluator.py
import asyncio
from typing import List, Dict
from pathlib import Path
import time

class EvaluationOrchestrator:
    """Main orchestrator for running evaluations"""

    def __init__(
        self,
        config: EvalConfig,
        openrouter_client: OpenRouterClient,
        results_dir: Path
    ):
        self.config = config
        self.client = openrouter_client
        self.results_dir = results_dir
        self.response_gen = ResponseGenerator(client)
        self.ensemble_judge = EnsembleJudge(client, config.judge_models, config.n_votes)

        # Create results structure
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._setup_checkpoint()

    async def run_evaluation(self, prompts: List[WritingPrompt]):
        """
        Run full evaluation on a set of prompts

        Phases:
        1. Generate responses from all models
        2. Judge all pairwise comparisons
        3. Aggregate and save results
        """
        total_comparisons = len(prompts) * len(self.config.model_pairs)

        print(f"Starting evaluation: {len(prompts)} prompts × {len(self.config.model_pairs)} pairs")
        print(f"Total comparisons: {total_comparisons}")

        # Phase 1: Generate all responses
        print("\n=== Phase 1: Generating Responses ===")
        responses = await self._generate_all_responses(prompts)

        # Phase 2: Judge all comparisons
        print("\n=== Phase 2: Judging Comparisons ===")
        results = await self._judge_all_comparisons(prompts, responses)

        # Phase 3: Save and analyze
        print("\n=== Phase 3: Saving Results ===")
        self._save_results(results)

        return results

    async def _generate_all_responses(
        self,
        prompts: List[WritingPrompt]
    ) -> Dict[str, Dict[str, ModelResponse]]:
        """
        Generate responses from all models for all prompts

        Returns: {prompt_id: {model_name: response}}
        """
        all_responses = {}

        # Get unique models from all pairs
        all_models = set()
        for pair in self.config.model_pairs:
            all_models.update(pair)

        tasks = []
        for prompt in prompts:
            for model in all_models:
                tasks.append(self._generate_with_tracking(prompt, model))

        # Run in parallel with concurrency limit
        responses = await self._run_with_concurrency(tasks, max_concurrent=20)

        # Organize by prompt_id and model
        for response in responses:
            if response.prompt_id not in all_responses:
                all_responses[response.prompt_id] = {}
            all_responses[response.prompt_id][response.model] = response

        return all_responses

    async def _judge_all_comparisons(
        self,
        prompts: List[WritingPrompt],
        responses: Dict[str, Dict[str, ModelResponse]]
    ) -> List[ComparisonResult]:
        """Judge all pairwise comparisons"""
        results = []

        tasks = []
        for prompt in prompts:
            for model_a, model_b in self.config.model_pairs:
                response_a = responses[prompt.prompt_id][model_a]
                response_b = responses[prompt.prompt_id][model_b]

                # Skip if either response failed
                if response_a.status != "success" or response_b.status != "success":
                    # Auto-loss for failed responses
                    results.append(self._handle_failure(prompt, response_a, response_b))
                    continue

                tasks.append(
                    self.ensemble_judge.evaluate_comparison(prompt, response_a, response_b)
                )

        # Run judgments in parallel
        comparison_results = await self._run_with_concurrency(tasks, max_concurrent=10)
        results.extend(comparison_results)

        return results

    async def _run_with_concurrency(self, tasks, max_concurrent: int):
        """Run async tasks with concurrency limit"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_task(task):
            async with semaphore:
                return await task

        return await asyncio.gather(*[bounded_task(t) for t in tasks])


class EvalConfig(BaseModel):
    """Configuration for an evaluation run"""
    run_id: str
    prompts_count: int
    model_pairs: List[tuple]  # [(gemini-pro, gpt-5.2), ...]
    judge_models: List[str]
    n_votes: int  # Best-of-N per judge
    random_seed: int
    filters: Dict[str, Any]  # Occupation/industry/formality filters
```

---

## 4. User Configuration & Cost Control

### 4.1 Configuration System

```python
# config.py
from typing import List, Optional, Dict
from pydantic import BaseModel

class UserConfig(BaseModel):
    """User-configurable evaluation parameters"""

    # Model selection
    eval_models: List[str]  # Which models to evaluate
    model_pairs: Optional[List[tuple]] = None  # Custom pairs or auto-generate
    model_tier: str = "both"  # "pro", "flash", "both"

    # Judge configuration
    judge_models: List[str] = [
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2",
        "google/gemini-3.0-pro"
    ]
    n_votes_per_judge: int = 5
    judge_personas: List[str] = ["writing_expert", "target_recipient"]

    # Prompt/task configuration
    n_prompts: int
    occupation_filters: Optional[List[str]] = None  # O*NET codes
    industry_filters: Optional[List[str]] = None  # NAICS codes
    job_zone_filters: Optional[List[int]] = None  # 1-5
    formality_filters: Optional[List[int]] = None  # 1-5
    age_filters: Optional[List[str]] = None  # Generations

    # Sampling configuration
    random_seed: int = 42
    stratify: bool = True  # Ensure even distribution
    max_per_occupation: Optional[int] = None
    max_per_industry: Optional[int] = None

class CostEstimator:
    """Estimate costs and time for evaluation runs"""

    # OpenRouter pricing (update with actual pricing)
    PRICING = {
        "google/gemini-3.0-pro": {"input": 0.10, "output": 0.30},  # per 1M tokens
        "google/gemini-3.0-flash": {"input": 0.05, "output": 0.15},
        "anthropic/claude-opus-4.5": {"input": 1.50, "output": 7.50},
        "openai/gpt-5.2": {"input": 1.00, "output": 3.00},
        # ... other models
    }

    def estimate_cost(self, config: UserConfig) -> Dict[str, float]:
        """
        Estimate total cost for evaluation run

        Returns:
            {
                "response_generation": cost,
                "judging": cost,
                "total_min": min_estimate,
                "total_max": max_estimate
            }
        """
        # Response generation costs
        response_cost = self._estimate_response_cost(config)

        # Judging costs
        judging_cost = self._estimate_judging_cost(config)

        return {
            "response_generation": response_cost,
            "judging": judging_cost,
            "total_min": response_cost + judging_cost * 0.9,
            "total_max": response_cost + judging_cost * 1.1
        }

    def estimate_time(self, config: UserConfig) -> Dict[str, float]:
        """
        Estimate runtime for evaluation

        Returns time estimates in hours
        """
        # Estimate based on:
        # - Number of API calls
        # - Rate limits per provider
        # - Parallel execution capacity

        total_response_calls = config.n_prompts * len(self._get_unique_models(config))
        total_judge_calls = (
            config.n_prompts *
            len(config.model_pairs) *
            len(config.judge_models) *
            len(config.judge_personas) *
            config.n_votes_per_judge
        )

        # Assume 20 concurrent calls, 2s avg per response, 1s avg per judgment
        response_time = (total_response_calls * 2) / (20 * 3600)  # hours
        judging_time = (total_judge_calls * 1) / (20 * 3600)

        return {
            "response_generation": response_time,
            "judging": judging_time,
            "total_parallelized": max(response_time, judging_time * 0.5),  # Overlap phases
            "total_sequential": response_time + judging_time
        }


# Preset configurations
PRESETS = {
    "sanity_check": UserConfig(
        eval_models=["google/gemini-3.0-pro", "openai/gpt-5.2"],
        n_prompts=5,
        judge_models=["anthropic/claude-opus-4.5"],
        n_votes_per_judge=1
    ),
    "smoke_test": UserConfig(
        eval_models=["google/gemini-3.0-pro", "openai/gpt-5.2"],
        n_prompts=20,
        judge_models=["anthropic/claude-opus-4.5"],
        n_votes_per_judge=3
    ),
    "standard_eval": UserConfig(
        eval_models=["google/gemini-3.0-pro", "openai/gpt-5.2",
                     "anthropic/claude-opus-4.5", "x-ai/grok-4.1"],
        n_prompts=500,
        n_votes_per_judge=5
    ),
    # ... more presets
}
```

### 4.2 Cost Display

```python
# cli_interface.py
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

def display_cost_estimate(config: UserConfig):
    """Display cost and time estimates before run"""

    estimator = CostEstimator()
    costs = estimator.estimate_cost(config)
    times = estimator.estimate_time(config)

    console = Console()

    # Create estimate panel
    estimate_text = f"""
[bold]Prompts:[/bold]              {config.n_prompts}
[bold]Model pairs:[/bold]          {len(config.model_pairs)}
[bold]Total comparisons:[/bold]    {config.n_prompts * len(config.model_pairs)}

[bold]Judge config:[/bold]         {len(config.judge_models)} judges × {config.n_votes_per_judge} votes × {len(config.judge_personas)} personas
[bold]Total judge calls:[/bold]    {config.n_prompts * len(config.model_pairs) * len(config.judge_models) * config.n_votes_per_judge * len(config.judge_personas)}

[bold cyan]ESTIMATED COST[/bold cyan]
  Response generation:  ${costs['response_generation']:.2f}
  Judging:              ${costs['judging']:.2f}
  [bold]Total:                ${costs['total_min']:.2f} - ${costs['total_max']:.2f}[/bold]

[bold cyan]ESTIMATED TIME[/bold cyan]
  With rate limits:     {times['total_sequential']:.1f} hours
  Parallelized:         {times['total_parallelized']:.1f} hours
"""

    panel = Panel(
        estimate_text,
        title="[bold]EVAL RUN ESTIMATE[/bold]",
        border_style="cyan"
    )

    console.print(panel)

    # Confirm
    proceed = console.input("\n[bold]Proceed? [y/N]:[/bold] ")
    return proceed.lower() == 'y'
```

---

## 5. Live Progress Visualization

### 5.1 Rich TUI Dashboard

```python
# progress_ui.py
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.console import Group
import time

class EvaluationDashboard:
    """Real-time evaluation progress dashboard using Rich"""

    def __init__(self, config: EvalConfig):
        self.config = config
        self.start_time = time.time()
        self.stats = {
            "prompts_completed": 0,
            "total_prompts": config.prompts_count,
            "current_prompt": None,
            "win_rates": {},
            "errors": 0,
            "retries": 0,
            "rate_limit_pauses": 0
        }

    def create_layout(self) -> Layout:
        """Create dashboard layout"""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="overall", size=5),
            Layout(name="pairs", size=len(self.config.model_pairs) + 2),
            Layout(name="current", size=12),
            Layout(name="stats", size=8),
            Layout(name="activity", size=8),
            Layout(name="errors", size=3)
        )

        return layout

    def render_header(self) -> Panel:
        """Render header with run info"""
        elapsed = time.time() - self.start_time
        eta = self._estimate_remaining_time()

        header = f"[bold]GEMINI WRITING EVAL[/bold] - Running [Preset: {self.config.preset_name}]\n"
        header += f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))} | "
        header += f"Elapsed: {self._format_time(elapsed)} | ETA: {self._format_time(eta)}"

        return Panel(header, style="bold cyan")

    def render_overall_progress(self) -> Panel:
        """Render overall progress bar"""
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=60),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
        )

        task = progress.add_task(
            f"{self.stats['prompts_completed']}/{self.stats['total_prompts']} prompts",
            total=self.stats['total_prompts'],
            completed=self.stats['prompts_completed']
        )

        phase_status = "[green]✓[/green] Generation | [yellow]◐[/yellow] Judging | [dim]○[/dim] Analysis"

        return Panel(
            Group(progress, phase_status),
            title="OVERALL PROGRESS",
            border_style="cyan"
        )

    def render_model_pairs(self) -> Panel:
        """Render per-pair progress"""
        table = Table(show_header=False, box=None)

        for pair in self.config.model_pairs:
            model_a, model_b = pair
            progress = self.stats.get(f"pair_{pair}", {})

            completed = progress.get("completed", 0)
            total = self.stats['total_prompts']
            win_rate = progress.get("win_rate", 0.0)

            # Progress bar
            bar_width = 40
            filled = int((completed / total) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)

            status = "✓" if completed == total else ""
            table.add_row(
                f"Gemini vs {model_b}",
                f"{bar}  {completed}/{total} {status}",
                f"[{win_rate:.0f}% win]"
            )

        return Panel(table, title="MODEL PAIRS", border_style="cyan")

    def update(self, **kwargs):
        """Update dashboard statistics"""
        self.stats.update(kwargs)

    async def run_with_dashboard(self, evaluation_coro):
        """Run evaluation with live dashboard"""
        layout = self.create_layout()

        with Live(layout, refresh_per_second=4) as live:
            # Update layout in background while eval runs
            async def update_dashboard():
                while not self.stats.get("complete", False):
                    layout["header"].update(self.render_header())
                    layout["overall"].update(self.render_overall_progress())
                    layout["pairs"].update(self.render_model_pairs())
                    # ... update other sections
                    await asyncio.sleep(0.25)

            # Run both tasks concurrently
            await asyncio.gather(
                evaluation_coro,
                update_dashboard()
            )
```

---

## 6. Results Storage & Analysis

### 6.1 Results Database Schema

```python
# results_database.py
import sqlite3
from pathlib import Path

class ResultsDatabase:
    """SQLite database for storing all evaluation results"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_schema()

    def _create_schema(self):
        """Create comprehensive results schema"""

        # Prompts table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                prompt_id TEXT PRIMARY KEY,
                onet_code TEXT,
                occupation_title TEXT,
                naics_code TEXT,
                industry_title TEXT,
                company_name TEXT,
                company_size TEXT,
                formality INTEGER,
                urgency TEXT,
                relationship_context TEXT,
                emotional_context TEXT,
                is_sensitive BOOLEAN,
                prompt_json TEXT
            )
        """)

        # Responses table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                response_id TEXT PRIMARY KEY,
                prompt_id TEXT,
                model TEXT,
                response_text TEXT,
                response_time REAL,
                token_count INTEGER,
                word_count INTEGER,
                char_count INTEGER,
                status TEXT,
                error TEXT,
                FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
            )
        """)

        # Judgments table (individual judge votes)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS judgments (
                judgment_id TEXT PRIMARY KEY,
                prompt_id TEXT,
                model_a TEXT,
                model_b TEXT,
                judge_model TEXT,
                judge_persona TEXT,
                vote_number INTEGER,
                verdict TEXT,
                reasoning TEXT,
                FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
            )
        """)

        # Comparisons table (aggregated results)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                comparison_id TEXT PRIMARY KEY,
                prompt_id TEXT,
                model_a TEXT,
                model_b TEXT,
                final_verdict TEXT,
                judge_agreement REAL,
                comparison_json TEXT,
                FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
            )
        """)

        # Create indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_comparisons_pair ON comparisons(model_a, model_b)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(onet_code)")

        self.conn.commit()
```

### 6.2 Statistical Analysis

```python
# analysis.py
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple

class ResultsAnalyzer:
    """Statistical analysis of evaluation results"""

    def __init__(self, db: ResultsDatabase):
        self.db = db
        self.df_comparisons = self._load_comparisons()
        self.df_prompts = self._load_prompts()

    def compute_win_rates(self) -> Dict[str, Dict]:
        """
        Compute win rates for all model pairs

        Returns:
            {
                "gemini-pro_vs_gpt-5.2": {
                    "win_rate": 0.52,
                    "confidence_interval": (0.48, 0.56),
                    "n_comparisons": 500,
                    "wins": 260,
                    "losses": 220,
                    "ties": 20
                },
                ...
            }
        """
        results = {}

        for pair in self.df_comparisons['pair'].unique():
            pair_data = self.df_comparisons[self.df_comparisons['pair'] == pair]

            wins = (pair_data['final_verdict'] == 'model_a').sum()
            losses = (pair_data['final_verdict'] == 'model_b').sum()
            ties = (pair_data['final_verdict'] == 'tie').sum()
            total = len(pair_data)

            win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.5

            # Wilson score confidence interval
            ci_lower, ci_upper = self._wilson_confidence_interval(wins, total)

            results[pair] = {
                "win_rate": win_rate,
                "confidence_interval": (ci_lower, ci_upper),
                "n_comparisons": total,
                "wins": wins,
                "losses": losses,
                "ties": ties
            }

        return results

    def _wilson_confidence_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Compute Wilson score confidence interval

        More accurate than normal approximation for proportions
        """
        if total == 0:
            return (0.0, 1.0)

        p = successes / total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt((p * (1 - p) / total + z**2 / (4 * total**2))) / denominator

        return (max(0, center - margin), min(1, center + margin))

    def breakdown_by_dimension(
        self,
        dimension: str  # "occupation", "industry", "formality", etc.
    ) -> pd.DataFrame:
        """
        Break down win rates by a specific dimension

        Returns DataFrame with win rates per dimension value
        """
        merged = self.df_comparisons.merge(self.df_prompts, on='prompt_id')

        results = []
        for value in merged[dimension].unique():
            subset = merged[merged[dimension] == value]

            for pair in subset['pair'].unique():
                pair_subset = subset[subset['pair'] == pair]
                wins = (pair_subset['final_verdict'] == 'model_a').sum()
                total = len(pair_subset)

                if total > 0:
                    results.append({
                        dimension: value,
                        "pair": pair,
                        "win_rate": wins / total,
                        "n": total
                    })

        return pd.DataFrame(results)

    def identify_weaknesses(
        self,
        model: str,
        min_sample_size: int = 20
    ) -> List[Dict]:
        """
        Identify specific areas of weakness for a model

        Returns list of dimensions where model underperforms significantly
        """
        weaknesses = []

        dimensions = ["occupation_title", "industry_title", "formality",
                      "urgency", "emotional_context"]

        for dim in dimensions:
            breakdown = self.breakdown_by_dimension(dim)
            model_data = breakdown[breakdown['pair'].str.contains(model)]

            for _, row in model_data.iterrows():
                if row['n'] >= min_sample_size and row['win_rate'] < 0.45:
                    weaknesses.append({
                        "dimension": dim,
                        "value": row[dim],
                        "win_rate": row['win_rate'],
                        "sample_size": row['n'],
                        "severity": 0.50 - row['win_rate']  # How far below 50%
                    })

        # Sort by severity
        weaknesses.sort(key=lambda x: x['severity'], reverse=True)
        return weaknesses
```

---

## 7. Reporting & Visualization

### 7.1 PDF Report Generation

```python
# report_generator.py
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
import plotly.graph_objects as go
from typing import List, Dict

class ReportGenerator:
    """Generate comprehensive PDF evaluation report"""

    def __init__(self, analyzer: ResultsAnalyzer, config: EvalConfig):
        self.analyzer = analyzer
        self.config = config
        self.charts_dir = Path("charts")
        self.charts_dir.mkdir(exist_ok=True)

    def generate_report(self, output_path: Path):
        """Generate full PDF report with all sections"""

        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        story = []

        # Executive Summary
        story.extend(self._generate_executive_summary())
        story.append(PageBreak())

        # Overall Win Rates
        story.extend(self._generate_overall_results())
        story.append(PageBreak())

        # Dimensional Breakdowns
        story.extend(self._generate_dimensional_analysis())
        story.append(PageBreak())

        # Weakness Analysis
        story.extend(self._generate_weakness_analysis())
        story.append(PageBreak())

        # Statistical Details
        story.extend(self._generate_statistical_details())

        doc.build(story)

    def _generate_win_rate_chart(self, win_rates: Dict) -> Path:
        """Generate win rate bar chart"""

        pairs = list(win_rates.keys())
        rates = [win_rates[p]["win_rate"] for p in pairs]
        ci_lower = [win_rates[p]["confidence_interval"][0] for p in pairs]
        ci_upper = [win_rates[p]["confidence_interval"][1] for p in pairs]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=pairs,
            y=rates,
            error_y=dict(
                type='data',
                symmetric=False,
                array=[u - r for r, u in zip(rates, ci_upper)],
                arrayminus=[r - l for r, l in zip(rates, ci_lower)]
            )
        ))

        fig.update_layout(
            title="Win Rates by Model Pair",
            xaxis_title="Model Pair",
            yaxis_title="Win Rate",
            yaxis=dict(range=[0, 1])
        )

        chart_path = self.charts_dir / "win_rates.png"
        fig.write_image(str(chart_path))
        return chart_path

    def _generate_heatmap(self, dimension: str) -> Path:
        """Generate heatmap of win rates across a dimension"""

        breakdown = self.analyzer.breakdown_by_dimension(dimension)

        # Pivot for heatmap
        pivot = breakdown.pivot(index=dimension, columns="pair", values="win_rate")

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale="RdYlGn",
            zmid=0.5
        ))

        fig.update_layout(title=f"Win Rates by {dimension}")

        chart_path = self.charts_dir / f"heatmap_{dimension}.png"
        fig.write_image(str(chart_path))
        return chart_path
```

---

## 8. CLI Interface

### 8.1 Main CLI

```python
# cli.py
import click
from pathlib import Path
import asyncio

@click.group()
def cli():
    """Gemini Writing Evaluation Framework"""
    pass

@cli.command()
@click.option('--preset', type=int, help='Use preset configuration (1-10)')
@click.option('--prompts', type=int, help='Number of prompts')
@click.option('--models', type=str, help='Comma-separated model list')
@click.option('--judges', type=str, help='Comma-separated judge models')
@click.option('--votes', type=int, default=5, help='Votes per judge')
@click.option('--dry-run', is_flag=True, help='Show estimate without running')
def run(preset, prompts, models, judges, votes, dry_run):
    """Run an evaluation"""

    # Load or create config
    if preset:
        config = PRESETS[f"preset_{preset}"]
    else:
        config = UserConfig(
            n_prompts=prompts,
            eval_models=models.split(',') if models else None,
            judge_models=judges.split(',') if judges else None,
            n_votes_per_judge=votes
        )

    # Show cost estimate
    if not display_cost_estimate(config):
        click.echo("Cancelled")
        return

    if dry_run:
        return

    # Run evaluation
    asyncio.run(run_evaluation(config))

@cli.command()
@click.argument('results_dir', type=click.Path(exists=True))
def analyze(results_dir):
    """Analyze results from a completed run"""

    db = ResultsDatabase(Path(results_dir) / "results.db")
    analyzer = ResultsAnalyzer(db)

    # Print summary
    win_rates = analyzer.compute_win_rates()
    for pair, stats in win_rates.items():
        click.echo(f"\n{pair}:")
        click.echo(f"  Win rate: {stats['win_rate']:.1%}")
        click.echo(f"  95% CI: [{stats['confidence_interval'][0]:.1%}, {stats['confidence_interval'][1]:.1%}]")

@cli.command()
@click.argument('results_dir', type=click.Path(exists=True))
def report(results_dir):
    """Generate PDF report from results"""

    db = ResultsDatabase(Path(results_dir) / "results.db")
    analyzer = ResultsAnalyzer(db)

    # Load config
    config_path = Path(results_dir) / "config.json"
    config = EvalConfig.parse_file(config_path)

    # Generate report
    generator = ReportGenerator(analyzer, config)
    output_path = Path(results_dir) / "report.pdf"
    generator.generate_report(output_path)

    click.echo(f"Report generated: {output_path}")

if __name__ == "__main__":
    cli()
```

---

## 9. Implementation Roadmap

### Phase 1: Data Pipeline (Week 1-2)
- [ ] O*NET downloader and parser
- [ ] NAICS data integration
- [ ] Company database scraping
- [ ] Name database setup
- [ ] Writing task extraction and filtering

### Phase 2: Prompt Generation (Week 2-3)
- [ ] Phase 1 LLM persona generation
- [ ] Phase 2 algorithmic combination engine
- [ ] Phase 3 enrichment system
- [ ] Prompt validation and quality checks
- [ ] Generate initial prompt set (10k+ prompts)

### Phase 3: Core Evaluation (Week 3-4)
- [ ] OpenRouter client with retry logic
- [ ] Response generation system
- [ ] Judge implementation (dual persona)
- [ ] Ensemble voting logic
- [ ] Position bias mitigation

### Phase 4: Infrastructure (Week 4-5)
- [ ] Results database schema
- [ ] Checkpoint/resume system
- [ ] Cost estimation system
- [ ] Live progress dashboard (Rich TUI)
- [ ] Error handling and logging

### Phase 5: Analysis & Reporting (Week 5-6)
- [ ] Statistical analysis engine
- [ ] Weakness identification algorithms
- [ ] Visualization generation (Plotly)
- [ ] PDF report generation
- [ ] Interactive results viewer (Rich TUI)

### Phase 6: Testing & Validation (Week 6-7)
- [ ] Run sanity check preset (5 prompts)
- [ ] Run smoke test preset (20 prompts)
- [ ] Validate judge agreement metrics
- [ ] Test resume/checkpoint functionality
- [ ] Validate cost estimates vs actual
- [ ] Fix bugs and edge cases

### Phase 7: Production Runs (Week 7-8)
- [ ] Run standard eval (500 prompts)
- [ ] Run comprehensive eval (2000 prompts)
- [ ] Generate final reports
- [ ] Weakness analysis
- [ ] Documentation

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_prompt_generation.py
import pytest
from prompt_generator import Phase2AlgorithmicGenerator

def test_stratified_sampling():
    """Test that prompts are evenly distributed across dimensions"""
    generator = Phase2AlgorithmicGenerator(...)
    prompts = generator.generate_prompts(n=100)

    # Check job zone distribution
    job_zones = [p.onet_task.job_zone for p in prompts]
    assert len(set(job_zones)) >= 4  # Should hit multiple job zones

    # Check formality distribution
    formality_levels = [p.formality for p in prompts]
    assert len(set(formality_levels)) >= 4

# tests/test_judge.py
def test_position_bias_mitigation():
    """Test that response order is properly shuffled"""
    judge = Judge(...)

    # Mock two responses
    response_a = ModelResponse(...)
    response_b = ModelResponse(...)

    # Run multiple judgments with different seeds
    orders_seen = set()
    for seed in range(10):
        prompt = WritingPrompt(random_seed=seed, ...)
        # Track which order was used
        # Should see both (A,B) and (B,A) orderings

    assert len(orders_seen) == 2  # Both orders used
```

### 10.2 Integration Tests

```python
# tests/test_e2e.py
async def test_end_to_end_mini():
    """Test complete eval pipeline with 2 prompts"""

    # Setup
    config = EvalConfig(
        prompts_count=2,
        model_pairs=[("gemini-pro", "gpt-5.2")],
        n_votes=1
    )

    # Generate prompts
    prompts = generate_test_prompts(2)

    # Run evaluation
    orchestrator = EvaluationOrchestrator(config, client, results_dir)
    results = await orchestrator.run_evaluation(prompts)

    # Validate results
    assert len(results) == 2
    assert all(r.final_verdict in [JudgeVerdict.MODEL_A_WINS,
                                     JudgeVerdict.MODEL_B_WINS,
                                     JudgeVerdict.TIE] for r in results)
```

---

## 11. Open Questions & Risks

### 11.1 Open Questions

1. **Model Availability**: Are all desired models available on OpenRouter with sufficient rate limits?
2. **Judge Bias**: How do we validate that judge models aren't biased toward their own provider?
3. **Prompt Quality**: How do we ensure generated prompts are realistic and not artificial?
4. **Company Data**: What's the best source for company-to-NAICS mapping at scale?
5. **Cost Validation**: Need to validate actual costs match estimates

### 11.2 Risks

1. **API Rate Limits**: May hit rate limits during large runs
   - *Mitigation*: Implement adaptive rate limiting and backoff

2. **Cost Overruns**: Actual costs may exceed estimates
   - *Mitigation*: Start with small presets, validate costs incrementally

3. **Judge Inconsistency**: Inter-judge agreement may be too low
   - *Mitigation*: Tune judge prompts, add more judges if needed

4. **Model Refusals**: Some models may refuse sensitive tasks
   - *Mitigation*: Track refusals separately, analyze patterns

5. **Data Quality**: O*NET tasks may not all be suitable for writing eval
   - *Mitigation*: Manual review of sample prompts, filtering pass

---

## 12. Success Criteria

The evaluation framework will be considered successful if it:

1. **Generates 10,000+ diverse, realistic writing prompts** from O*NET data
2. **Runs reliably** with checkpoint/resume for long evaluations
3. **Produces statistically significant results** with confidence intervals
4. **Identifies specific weaknesses** in Gemini vs competitors
5. **Costs match estimates** within 20% margin
6. **Completes standard eval (500 prompts)** in under 4 hours
7. **Achieves inter-judge agreement** (Cohen's Kappa) > 0.60
8. **Generates publication-quality PDF report** with all required sections
9. **Provides interactive results exploration** via Rich TUI

---

## Conclusion

This implementation plan provides a complete roadmap for building a robust, production-grade evaluation framework for comparing Gemini 3.0 Pro/Flash against competing frontier LLMs on realistic professional writing tasks. The system prioritizes:

- **Realism**: Real companies, real names, authentic scenarios
- **Diversity**: Maximum coverage across occupations, industries, personas, contexts
- **Robustness**: Multi-judge ensemble with best-of-N voting
- **Usability**: Cost control, live progress, interactive analysis
- **Trustworthiness**: Statistical rigor, bias detection, reproducibility

The phased implementation approach allows for iterative validation and adjustment, with clear success criteria at each stage.

