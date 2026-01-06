# Gemini Writing Evaluation Framework - Implementation Plan

## Executive Summary

This document provides a comprehensive implementation plan for the Gemini Writing Evaluation Framework, a high-quality evaluation system comparing Gemini 3.0 Pro and Flash against competing frontier LLMs on realistic professional writing tasks.

The system leverages O*NET occupational data to generate diverse, authentic writing prompts across the entire US economy, evaluates model responses using a robust ensemble judging methodology, and produces actionable insights about model performance and weaknesses.

## Architecture Overview

### System Components

1. **Data Acquisition Layer**
   - O*NET database downloader and parser
   - NAICS industry code database
   - Company database integration (SEC/Crunchbase)
   - Name generation system

2. **Prompt Generation Engine**
   - Phase 1: LLM-based persona/context generation
   - Phase 2: Algorithmic combination system
   - Phase 3: LLM enrichment pipeline

3. **Evaluation Infrastructure**
   - OpenRouter API client with retry/rate-limiting
   - Async evaluation orchestrator
   - Response collection and storage

4. **Judge System**
   - Ensemble judge implementation (3 models)
   - Dual persona judging (expert + recipient)
   - Best-of-N voting aggregation

5. **Analysis & Reporting**
   - Statistical analysis engine
   - Weakness identification system
   - PDF report generator
   - Interactive TUI viewer

6. **Storage & Persistence**
   - SQLite database schema
   - Checkpoint/resume system
   - Timestamped run directories

---

## 1. Data Acquisition

### 1.1 O*NET Database Integration

**Objective:** Extract task-level writing activities from O*NET database (~20,000+ tasks across 1,000+ occupations).

**Implementation:**

```python
# data_acquisition/onet_downloader.py

import requests
import zipfile
import sqlite3
from pathlib import Path
from typing import List, Dict
import pandas as pd

class ONetDownloader:
    """Downloads and processes O*NET database files."""

    ONET_VERSION = "30.0"  # Latest as of 2026
    BASE_URL = "https://www.onetcenter.org/dl_files/database/db_{version}_text/"

    REQUIRED_FILES = [
        "Task Statements.txt",
        "Occupation Data.txt",
        "Task Categories.txt",
        "Job Zones.txt",
        "Content Model Reference.txt"
    ]

    def __init__(self, data_dir: Path = Path("data/onet")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "onet.db"

    async def download_database(self):
        """Download all required O*NET data files."""
        version_url = self.BASE_URL.format(version=self.ONET_VERSION.replace(".", "_"))

        # Download database zip
        zip_url = f"{version_url}db_{self.ONET_VERSION.replace('.', '_')}_text.zip"
        zip_path = self.data_dir / "onet_db.zip"

        print(f"Downloading O*NET {self.ONET_VERSION} database...")
        async with httpx.AsyncClient() as client:
            response = await client.get(zip_url)
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                f.write(response.content)

        # Extract required files
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.data_dir)

        print("Database downloaded and extracted successfully")

    def load_to_sqlite(self):
        """Load O*NET text files into SQLite database for efficient querying."""
        conn = sqlite3.connect(self.db_path)

        # Load task statements (core data)
        tasks_df = pd.read_csv(
            self.data_dir / "Task Statements.txt",
            sep="\t",
            encoding="utf-8"
        )
        tasks_df.to_sql("task_statements", conn, if_exists="replace", index=False)

        # Load occupation data
        occupations_df = pd.read_csv(
            self.data_dir / "Occupation Data.txt",
            sep="\t",
            encoding="utf-8"
        )
        occupations_df.to_sql("occupations", conn, if_exists="replace", index=False)

        # Load job zones (skill levels 1-5)
        job_zones_df = pd.read_csv(
            self.data_dir / "Job Zones.txt",
            sep="\t",
            encoding="utf-8"
        )
        job_zones_df.to_sql("job_zones", conn, if_exists="replace", index=False)

        # Create indexes for efficient querying
        conn.execute("CREATE INDEX IF NOT EXISTS idx_onet_code ON task_statements(O*NET-SOC Code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_type ON task_statements(Task Type)")

        conn.commit()
        conn.close()

        print(f"Loaded O*NET data to SQLite: {self.db_path}")

    def extract_writing_tasks(self) -> pd.DataFrame:
        """Extract only tasks that involve writing."""
        conn = sqlite3.connect(self.db_path)

        # Keywords that indicate writing tasks
        writing_keywords = [
            "write", "draft", "compose", "prepare", "document",
            "email", "report", "correspondence", "memo", "letter",
            "proposal", "communicate", "notification", "message"
        ]

        keyword_conditions = " OR ".join([
            f"LOWER(Task) LIKE '%{keyword}%'"
            for keyword in writing_keywords
        ])

        query = f"""
        SELECT
            ts.`O*NET-SOC Code` as onet_code,
            ts.Task as task_description,
            ts.`Task ID` as task_id,
            ts.`Task Type` as task_type,
            o.Title as occupation_title,
            jz.`Job Zone` as job_zone,
            jz.Description as job_zone_description
        FROM task_statements ts
        JOIN occupations o ON ts.`O*NET-SOC Code` = o.`O*NET-SOC Code`
        LEFT JOIN job_zones jz ON ts.`O*NET-SOC Code` = jz.`O*NET-SOC Code`
        WHERE {keyword_conditions}
        ORDER BY ts.`O*NET-SOC Code`, ts.`Task ID`
        """

        writing_tasks_df = pd.read_sql(query, conn)
        conn.close()

        print(f"Extracted {len(writing_tasks_df)} writing-related tasks")
        return writing_tasks_df
```

**Download Script:**

```python
# scripts/download_onet.py

import asyncio
from data_acquisition.onet_downloader import ONetDownloader

async def main():
    downloader = ONetDownloader()

    # Download database
    await downloader.download_database()

    # Load to SQLite
    downloader.load_to_sqlite()

    # Extract writing tasks
    writing_tasks = downloader.extract_writing_tasks()

    # Save to CSV for inspection
    writing_tasks.to_csv("data/writing_tasks.csv", index=False)
    print(f"Writing tasks saved to data/writing_tasks.csv")

if __name__ == "__main__":
    asyncio.run(main())
```

### 1.2 NAICS Industry Code Database

**Objective:** Provide systematic industry coverage for prompt generation.

**Implementation:**

```python
# data_acquisition/naics_loader.py

import requests
import pandas as pd
from pathlib import Path
import sqlite3

class NAICSLoader:
    """Loads and processes NAICS industry classification codes."""

    # US Census Bureau NAICS data
    NAICS_URL = "https://www.census.gov/naics/2022NAICS/2022_NAICS_Descriptions.xlsx"

    def __init__(self, data_dir: Path = Path("data/naics")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "naics.db"

    def download_naics(self):
        """Download NAICS codes from Census Bureau."""
        excel_path = self.data_dir / "naics_2022.xlsx"

        print("Downloading NAICS 2022 codes...")
        response = requests.get(self.NAICS_URL)
        response.raise_for_status()

        with open(excel_path, 'wb') as f:
            f.write(response.content)

        print(f"NAICS data downloaded to {excel_path}")
        return excel_path

    def load_to_sqlite(self, excel_path: Path):
        """Load NAICS codes into SQLite."""
        # Read Excel file
        naics_df = pd.read_excel(excel_path)

        # Clean and structure data
        naics_df = naics_df.rename(columns={
            "Code": "naics_code",
            "Title": "industry_title",
            "Description": "description"
        })

        # Add hierarchy levels
        naics_df["level"] = naics_df["naics_code"].astype(str).apply(len)
        naics_df["sector"] = naics_df["naics_code"].astype(str).str[:2]

        # Save to SQLite
        conn = sqlite3.connect(self.db_path)
        naics_df.to_sql("naics_codes", conn, if_exists="replace", index=False)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_naics_code ON naics_codes(naics_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sector ON naics_codes(sector)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_level ON naics_codes(level)")

        conn.commit()
        conn.close()

        print(f"Loaded {len(naics_df)} NAICS codes to SQLite")

    def get_industry_sample(self, n_industries: int = 50, level: int = 4) -> pd.DataFrame:
        """Get stratified sample of industries for diversity."""
        conn = sqlite3.connect(self.db_path)

        # Get even distribution across sectors
        query = f"""
        WITH sector_counts AS (
            SELECT sector, COUNT(*) as cnt
            FROM naics_codes
            WHERE level = {level}
            GROUP BY sector
        ),
        per_sector AS (
            SELECT
                sector,
                CAST({n_industries} * 1.0 / (SELECT COUNT(DISTINCT sector) FROM sector_counts) AS INTEGER) as target
            FROM sector_counts
        )
        SELECT n.naics_code, n.industry_title, n.description, n.sector
        FROM naics_codes n
        JOIN per_sector ps ON n.sector = ps.sector
        WHERE n.level = {level}
        ORDER BY RANDOM()
        LIMIT (SELECT target FROM per_sector WHERE sector = n.sector)
        """

        industries_df = pd.read_sql(query, conn)
        conn.close()

        return industries_df
```

### 1.3 Company Database Integration

**Objective:** Ground prompts in real companies for authenticity.

**Implementation:**

```python
# data_acquisition/company_database.py

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import requests

class CompanyDatabase:
    """Manages real company data for prompt grounding."""

    def __init__(self, data_dir: Path = Path("data/companies")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "companies.db"
        self._init_database()

    def _init_database(self):
        """Initialize company database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                naics_code TEXT,
                industry_sector TEXT,
                company_size TEXT,  -- 'fortune500', 'midmarket', 'small', 'startup'
                is_public BOOLEAN,
                founded_year INTEGER,
                hq_location TEXT,
                description TEXT,
                data_source TEXT,  -- 'sec', 'crunchbase', 'manual'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_naics ON companies(naics_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_size ON companies(company_size)")
        conn.commit()
        conn.close()

    def load_fortune500(self, csv_path: Optional[Path] = None):
        """Load Fortune 500 companies."""
        # Fortune 500 data (public dataset or manual CSV)
        if csv_path is None:
            # Use built-in seed data
            fortune500 = pd.DataFrame([
                {"name": "Walmart", "naics_code": "452", "sector": "Retail", "size": "fortune500"},
                {"name": "Amazon.com", "naics_code": "454", "sector": "E-commerce", "size": "fortune500"},
                {"name": "Apple", "naics_code": "334", "sector": "Technology", "size": "fortune500"},
                # ... more companies
            ])
        else:
            fortune500 = pd.read_csv(csv_path)

        fortune500["is_public"] = True
        fortune500["data_source"] = "fortune500_list"

        conn = sqlite3.connect(self.db_path)
        fortune500.to_sql("companies", conn, if_exists="append", index=False)
        conn.close()

    def load_sec_filings(self, naics_codes: List[str]):
        """Load companies from SEC EDGAR database."""
        # SEC EDGAR API provides company listings
        # Implementation would query SEC API for companies by NAICS
        pass  # Detailed implementation would go here

    def get_companies_for_industry(self, naics_code: str, limit: int = 10) -> pd.DataFrame:
        """Get diverse companies for a given industry."""
        conn = sqlite3.connect(self.db_path)

        query = """
        SELECT name, naics_code, industry_sector, company_size, is_public
        FROM companies
        WHERE naics_code LIKE ?
        ORDER BY RANDOM()
        LIMIT ?
        """

        companies_df = pd.read_sql(query, conn, params=(f"{naics_code}%", limit))
        conn.close()

        return companies_df
```

### 1.4 Name Generation System

**Objective:** Generate realistic, demographically diverse names for personas.

**Implementation:**

```python
# data_acquisition/name_generator.py

import random
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class PersonName:
    """Represents a person's name with metadata."""
    first_name: str
    last_name: str
    full_name: str
    formality: str  # 'casual', 'professional', 'formal'
    email_local: str  # 'john.doe', 'j.doe', 'jdoe'

class NameGenerator:
    """Generates realistic names with demographic diversity."""

    # Name databases with demographic representation
    FIRST_NAMES = {
        "genZ": ["Ava", "Noah", "Emma", "Liam", "Zoe", "Kai"],
        "millennial": ["Emily", "Michael", "Sarah", "David", "Jessica", "Chris"],
        "genX": ["Jennifer", "James", "Michelle", "Robert", "Lisa", "Mark"],
        "boomer": ["Patricia", "Richard", "Barbara", "William", "Susan", "John"]
    }

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
        "Martinez", "Lee", "Kim", "Chen", "Patel", "Singh",
        "O'Brien", "Rodriguez", "Wilson", "Anderson", "Taylor"
    ]

    def generate_name(self,
                     generation: str = "millennial",
                     formality: str = "professional") -> PersonName:
        """Generate a realistic name."""
        first = random.choice(self.FIRST_NAMES.get(generation, self.FIRST_NAMES["millennial"]))
        last = random.choice(self.LAST_NAMES)

        # Generate email variations
        email_local = self._generate_email_local(first, last, formality)

        # Format full name based on formality
        if formality == "formal":
            full_name = f"Dr. {first} {last}"
        elif formality == "casual":
            full_name = first
        else:
            full_name = f"{first} {last}"

        return PersonName(
            first_name=first,
            last_name=last,
            full_name=full_name,
            formality=formality,
            email_local=email_local
        )

    def _generate_email_local(self, first: str, last: str, formality: str) -> str:
        """Generate email local part."""
        first_lower = first.lower()
        last_lower = last.lower()

        if formality == "formal":
            return f"{first_lower}.{last_lower}"
        elif formality == "casual":
            return first_lower[:1] + last_lower
        else:
            return f"{first_lower}.{last_lower}"
```

---

## 2. Prompt Generation Engine

### 2.1 Three-Phase Prompt Generation

The prompt generation system follows a three-phase approach:

1. **Phase 1**: LLM generates persona/context variations (offline preprocessing)
2. **Phase 2**: Algorithmic combination of tasks with dimensions (deterministic)
3. **Phase 3**: LLM enrichment for context-heavy prompts (as needed)

### 2.2 Prompt Schema

```python
# prompt_generation/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class WriterPersona(BaseModel):
    """The person doing the writing."""
    name: str
    role: str
    company: str
    generation: str  # genZ, millennial, genX, boomer
    skill_level: int  # 1-5 from O*NET job zones
    formality_preference: str  # casual, professional, formal

class RecipientPersona(BaseModel):
    """The person receiving the writing."""
    name: str
    role: str
    relationship: str  # peer, superior, subordinate, client, external
    english_variant: str  # en-US, en-GB, en-AU, non-native

class PromptContext(BaseModel):
    """Additional context for the writing task."""
    urgency: str  # routine, moderate, urgent, critical
    audience_size: str  # one-on-one, small-group, department, company, public
    emotional_context: str  # routine, crisis, celebration, conflict, bad_news
    message_position: str  # initial, reply, followup
    has_attachments: bool = False
    attachment_summaries: Optional[List[str]] = None
    prior_messages: Optional[List[Dict]] = None
    temporal_context: Optional[str] = None
    competing_objectives: Optional[List[str]] = None

class WritingPrompt(BaseModel):
    """Complete writing prompt for evaluation."""
    prompt_id: str
    onet_code: str
    occupation_title: str
    task_description: str  # Original O*NET task
    naics_code: str
    industry_title: str
    company_name: str

    writer_persona: WriterPersona
    recipient_persona: RecipientPersona
    context: PromptContext

    # Full prompt text
    prompt_text: str

    # Metadata for analysis
    task_type: str  # email, report, memo, proposal, etc.
    formality_level: str
    is_sensitive: bool = False
    sensitive_categories: Optional[List[str]] = None
    has_constraints: bool = False
    constraints: Optional[List[str]] = None

    language: str = "en"
    language_variant: str = "en-US"

    created_at: datetime = Field(default_factory=datetime.utcnow)
    generation_phase: str  # "phase1", "phase2", "phase3"
    random_seed: Optional[int] = None
```

### 2.3 Phase 1: LLM-Based Persona/Context Generation

**Objective:** Generate diverse persona and context variations for each O*NET task type using LLMs.

**Implementation:**

```python
# prompt_generation/phase1_llm_generation.py

import asyncio
from openai import AsyncOpenAI
from typing import List, Dict
import json

class Phase1Generator:
    """Generates persona/context variations using LLMs."""

    def __init__(self, openrouter_api_key: str):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key
        )

        # Use the models being evaluated for generation
        self.generation_models = [
            "google/gemini-3.0-pro",
            "openai/gpt-5.2-thinking",
            "anthropic/claude-opus-4.5"
        ]

    async def generate_persona_variations(self,
                                         task_description: str,
                                         occupation_title: str,
                                         n_variations: int = 10) -> List[Dict]:
        """Generate diverse persona variations for a task."""

        prompt = f"""
Given this occupational writing task, generate {n_variations} diverse persona and context variations.

Task: {task_description}
Occupation: {occupation_title}

For each variation, provide:
1. Writer characteristics (age/generation, skill level, formality preference)
2. Recipient characteristics (role, relationship, english variant)
3. Context details (urgency, audience size, emotional context, etc.)

Focus on MAXIMUM DIVERSITY across:
- Generational range (GenZ to Boomer)
- Formality spectrum (casual to formal)
- Urgency levels (routine to critical)
- Relationship contexts (first contact to ongoing)
- Emotional contexts (routine to crisis)

Return as JSON array of variations.
"""

        # Rotate through models for generation
        variations_all = []

        for model in self.generation_models:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,  # High temperature for diversity
                max_tokens=4000
            )

            try:
                variations = json.loads(response.choices[0].message.content)
                variations_all.extend(variations)
            except json.JSONDecodeError:
                # Fallback: extract JSON from markdown code blocks
                content = response.choices[0].message.content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                    variations = json.loads(json_str)
                    variations_all.extend(variations)

        # Return requested number, ensuring diversity
        return variations_all[:n_variations]

    async def enrich_task_with_specifics(self, task: Dict) -> Dict:
        """Phase 3: Enrich context-heavy prompts with specific details."""

        if not task.get("needs_enrichment", False):
            return task

        prompt = f"""
Enrich this writing task with realistic, specific details:

Task: {task['task_description']}
Writer: {task['writer_persona']['name']}, {task['writer_persona']['role']} at {task['company_name']}
Recipient: {task['recipient_persona']['name']}, {task['recipient_persona']['role']}

Add realistic details such as:
- Specific dates/deadlines if relevant
- Mock attachment summaries if needed
- Prior message content if this is a reply
- Specific constraints or competing objectives
- Any other context that makes this feel like a real workplace task

Return the enriched task as JSON.
"""

        response = await self.client.chat.completions.create(
            model="anthropic/claude-opus-4.5",  # Use best model for enrichment
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        enriched = json.loads(response.choices[0].message.content)
        return enriched
```

### 2.4 Phase 2: Algorithmic Combination

**Objective:** Deterministically combine O*NET tasks with industries, companies, and personas.

```python
# prompt_generation/phase2_combination.py

import random
from typing import List, Dict
import pandas as pd
from .schemas import WritingPrompt, WriterPersona, RecipientPersona, PromptContext
from data_acquisition.onet_downloader import ONetDownloader
from data_acquisition.naics_loader import NAICSLoader
from data_acquisition.company_database import CompanyDatabase
from data_acquisition.name_generator import NameGenerator

class Phase2Combiner:
    """Algorithmically combines tasks with personas, industries, companies."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        random.seed(random_seed)

        self.onet = ONetDownloader()
        self.naics = NAICSLoader()
        self.companies = CompanyDatabase()
        self.names = NameGenerator()

    def generate_prompts(self,
                        n_prompts: int = 500,
                        occupation_codes: Optional[List[str]] = None,
                        industry_codes: Optional[List[str]] = None) -> List[WritingPrompt]:
        """Generate prompts by combining tasks with context."""

        # Load writing tasks from O*NET
        writing_tasks = self.onet.extract_writing_tasks()

        # Filter by occupation if specified
        if occupation_codes:
            writing_tasks = writing_tasks[
                writing_tasks['onet_code'].str.startswith(tuple(occupation_codes))
            ]

        # Sample tasks
        sampled_tasks = writing_tasks.sample(n=min(n_prompts, len(writing_tasks)))

        prompts = []

        for idx, task_row in sampled_tasks.iterrows():
            # Get industry for this task
            if industry_codes:
                naics_code = random.choice(industry_codes)
            else:
                industries = self.naics.get_industry_sample(n_industries=1)
                naics_code = industries.iloc[0]['naics_code']

            # Get company in this industry
            companies = self.companies.get_companies_for_industry(naics_code, limit=5)
            if len(companies) > 0:
                company = companies.sample(1).iloc[0]
                company_name = company['name']
            else:
                company_name = f"Company in {naics_code}"

            # Generate personas
            generation = random.choice(["genZ", "millennial", "genX", "boomer"])
            writer_name = self.names.generate_name(generation=generation)
            recipient_name = self.names.generate_name()

            writer_persona = WriterPersona(
                name=writer_name.full_name,
                role=task_row['occupation_title'],
                company=company_name,
                generation=generation,
                skill_level=int(task_row.get('job_zone', 3)),
                formality_preference=random.choice(["casual", "professional", "formal"])
            )

            recipient_persona = RecipientPersona(
                name=recipient_name.full_name,
                role=self._infer_recipient_role(task_row['task_description']),
                relationship=random.choice(["peer", "superior", "subordinate", "client", "external"]),
                english_variant=random.choice(["en-US", "en-GB", "en-AU"])
            )

            # Generate context
            context = PromptContext(
                urgency=random.choice(["routine", "moderate", "urgent", "critical"]),
                audience_size=random.choice(["one-on-one", "small-group", "department", "company"]),
                emotional_context=random.choice(["routine", "celebration", "conflict", "bad_news"]),
                message_position=random.choice(["initial", "reply", "followup"])
            )

            # Build prompt text
            prompt_text = self._build_prompt_text(
                task_row['task_description'],
                writer_persona,
                recipient_persona,
                context
            )

            # Create prompt object
            prompt = WritingPrompt(
                prompt_id=f"prompt_{idx:06d}",
                onet_code=task_row['onet_code'],
                occupation_title=task_row['occupation_title'],
                task_description=task_row['task_description'],
                naics_code=str(naics_code),
                industry_title=task_row.get('industry_title', ''),
                company_name=company_name,
                writer_persona=writer_persona,
                recipient_persona=recipient_persona,
                context=context,
                prompt_text=prompt_text,
                task_type=self._infer_task_type(task_row['task_description']),
                formality_level=writer_persona.formality_preference,
                generation_phase="phase2",
                random_seed=self.random_seed
            )

            prompts.append(prompt)

        return prompts

    def _infer_recipient_role(self, task_description: str) -> str:
        """Infer recipient role from task description."""
        task_lower = task_description.lower()

        if "executive" in task_lower or "ceo" in task_lower:
            return "Executive"
        elif "client" in task_lower or "customer" in task_lower:
            return "Client"
        elif "team" in task_lower:
            return "Team Member"
        elif "manager" in task_lower:
            return "Manager"
        else:
            return "Colleague"

    def _infer_task_type(self, task_description: str) -> str:
        """Infer communication type from task."""
        task_lower = task_description.lower()

        if "email" in task_lower or "correspondence" in task_lower:
            return "email"
        elif "report" in task_lower:
            return "report"
        elif "memo" in task_lower or "memorandum" in task_lower:
            return "memo"
        elif "proposal" in task_lower:
            return "proposal"
        elif "letter" in task_lower:
            return "letter"
        else:
            return "general_writing"

    def _build_prompt_text(self,
                          task: str,
                          writer: WriterPersona,
                          recipient: RecipientPersona,
                          context: PromptContext) -> str:
        """Build full prompt text from components."""

        prompt_parts = []

        # Context setting
        prompt_parts.append(f"You are {writer.name}, {writer.role} at {writer.company}.")

        # Task
        prompt_parts.append(f"\nTask: {task}")

        # Recipient
        prompt_parts.append(f"\nRecipient: {recipient.name} ({recipient.role})")

        # Context details
        if context.urgency != "routine":
            prompt_parts.append(f"\nUrgency: {context.urgency}")

        if context.emotional_context != "routine":
            prompt_parts.append(f"\nContext: {context.emotional_context}")

        # Temporal context (if relevant)
        if context.temporal_context:
            prompt_parts.append(f"\n{context.temporal_context}")

        # Attachments
        if context.has_attachments and context.attachment_summaries:
            prompt_parts.append("\nAttachments:")
            for att in context.attachment_summaries:
                prompt_parts.append(f"- {att}")

        # Prior messages
        if context.prior_messages:
            prompt_parts.append("\nPrevious message:")
            prompt_parts.append(context.prior_messages[0]['content'])

        prompt_parts.append("\n\nWrite the message:")

        return "\n".join(prompt_parts)
```

### 2.5 Prompt Storage and Management

```python
# prompt_generation/prompt_manager.py

import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from .schemas import WritingPrompt

class PromptManager:
    """Manages storage and retrieval of generated prompts."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize prompt storage schema."""
        conn = sqlite3.connect(self.db_path)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                prompt_id TEXT PRIMARY KEY,
                onet_code TEXT,
                occupation_title TEXT,
                task_description TEXT,
                naics_code TEXT,
                industry_title TEXT,
                company_name TEXT,
                writer_persona TEXT,  -- JSON
                recipient_persona TEXT,  -- JSON
                context TEXT,  -- JSON
                prompt_text TEXT,
                task_type TEXT,
                formality_level TEXT,
                is_sensitive BOOLEAN,
                sensitive_categories TEXT,  -- JSON array
                has_constraints BOOLEAN,
                constraints TEXT,  -- JSON array
                language TEXT,
                language_variant TEXT,
                generation_phase TEXT,
                random_seed INTEGER,
                created_at TIMESTAMP
            )
        """)

        # Indexes for filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_onet ON prompts(onet_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_naics ON prompts(naics_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_type ON prompts(task_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_formality ON prompts(formality_level)")

        conn.commit()
        conn.close()

    def save_prompts(self, prompts: List[WritingPrompt]):
        """Save generated prompts to database."""
        conn = sqlite3.connect(self.db_path)

        for prompt in prompts:
            conn.execute("""
                INSERT OR REPLACE INTO prompts VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                prompt.prompt_id,
                prompt.onet_code,
                prompt.occupation_title,
                prompt.task_description,
                prompt.naics_code,
                prompt.industry_title,
                prompt.company_name,
                json.dumps(prompt.writer_persona.dict()),
                json.dumps(prompt.recipient_persona.dict()),
                json.dumps(prompt.context.dict()),
                prompt.prompt_text,
                prompt.task_type,
                prompt.formality_level,
                prompt.is_sensitive,
                json.dumps(prompt.sensitive_categories or []),
                prompt.has_constraints,
                json.dumps(prompt.constraints or []),
                prompt.language,
                prompt.language_variant,
                prompt.generation_phase,
                prompt.random_seed,
                prompt.created_at.isoformat()
            ))

        conn.commit()
        conn.close()

    def load_prompts(self, prompt_ids: Optional[List[str]] = None) -> List[WritingPrompt]:
        """Load prompts from database."""
        conn = sqlite3.connect(self.db_path)

        if prompt_ids:
            placeholders = ','.join('?' * len(prompt_ids))
            query = f"SELECT * FROM prompts WHERE prompt_id IN ({placeholders})"
            cursor = conn.execute(query, prompt_ids)
        else:
            cursor = conn.execute("SELECT * FROM prompts")

        prompts = []
        for row in cursor.fetchall():
            # Reconstruct prompt object from row
            # (detailed deserialization logic)
            pass

        conn.close()
        return prompts
```

---

## 3. Evaluation Infrastructure

### 3.1 OpenRouter API Client

**Objective:** Robust API client with retry logic, rate limiting, and error handling.

```python
# evaluation/openrouter_client.py

import asyncio
import httpx
from typing import Dict, Optional, List
import time
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """Async client for OpenRouter API with robust error handling."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, timeout: int = 120):
        self.api_key = api_key
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/gemini-eval",
                "X-Title": "Gemini Writing Evaluation"
            },
            timeout=httpx.Timeout(timeout)
        )

        # Track usage for cost estimation
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def chat_completion(self,
                             model: str,
                             messages: List[Dict],
                             temperature: float = 0.7,
                             max_tokens: int = 4000) -> Dict:
        """Make chat completion request with retries."""

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        start_time = time.time()

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()

            result = response.json()
            elapsed = time.time() - start_time

            # Track usage
            usage = result.get("usage", {})
            self.total_input_tokens += usage.get("prompt_tokens", 0)
            self.total_output_tokens += usage.get("completion_tokens", 0)
            self.api_calls += 1

            logger.info(f"API call to {model} completed in {elapsed:.2f}s")

            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limit - exponential backoff will handle
                logger.warning(f"Rate limit hit for {model}, retrying...")
                raise
            elif e.response.status_code >= 500:
                # Server error - retry
                logger.warning(f"Server error for {model}: {e.response.status_code}, retrying...")
                raise
            else:
                # Client error - don't retry
                logger.error(f"Client error for {model}: {e.response.status_code}")
                return {"error": str(e), "model": model}

        except httpx.TimeoutException:
            logger.warning(f"Timeout for {model}, retrying...")
            raise

        except Exception as e:
            logger.error(f"Unexpected error for {model}: {e}")
            return {"error": str(e), "model": model}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def get_cost_estimate(self, pricing: Dict[str, Dict]) -> float:
        """Estimate cost based on token usage and pricing."""
        total_cost = 0.0

        for model, prices in pricing.items():
            input_cost = (self.total_input_tokens / 1_000_000) * prices.get("input", 0)
            output_cost = (self.total_output_tokens / 1_000_000) * prices.get("output", 0)
            total_cost += input_cost + output_cost

        return total_cost
```

### 3.2 Evaluation Orchestrator

**Objective:** Coordinate prompt evaluation across multiple models with parallelization.

```python
# evaluation/evaluator.py

import asyncio
from typing import List, Dict, Optional
from pathlib import Path
import json
import time
from dataclasses import dataclass
from .openrouter_client import OpenRouterClient
from prompt_generation.schemas import WritingPrompt

@dataclass
class ModelResponse:
    """Model response to a writing prompt."""
    prompt_id: str
    model: str
    response_text: str
    response_time: float
    tokens_used: Dict[str, int]
    error: Optional[str] = None
    is_refusal: bool = False
    refusal_category: Optional[str] = None

class Evaluator:
    """Orchestrates evaluation of prompts across models."""

    def __init__(self,
                 api_key: str,
                 models: List[str],
                 max_concurrent: int = 10):
        self.client = OpenRouterClient(api_key)
        self.models = models
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def evaluate_prompt(self,
                            prompt: WritingPrompt,
                            model: str) -> ModelResponse:
        """Evaluate a single prompt with a single model."""

        async with self.semaphore:
            start_time = time.time()

            messages = [{"role": "user", "content": prompt.prompt_text}]

            result = await self.client.chat_completion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )

            elapsed = time.time() - start_time

            # Check for errors
            if "error" in result:
                return ModelResponse(
                    prompt_id=prompt.prompt_id,
                    model=model,
                    response_text="",
                    response_time=elapsed,
                    tokens_used={},
                    error=result["error"]
                )

            response_text = result["choices"][0]["message"]["content"]

            # Detect refusals
            is_refusal, refusal_category = self._detect_refusal(response_text)

            return ModelResponse(
                prompt_id=prompt.prompt_id,
                model=model,
                response_text=response_text,
                response_time=elapsed,
                tokens_used=result.get("usage", {}),
                is_refusal=is_refusal,
                refusal_category=refusal_category
            )

    def _detect_refusal(self, response: str) -> tuple[bool, Optional[str]]:
        """Detect if response is a refusal."""
        response_lower = response.lower()

        refusal_patterns = {
            "safety": ["cannot", "policy", "safety", "inappropriate"],
            "capability": ["unable to", "can't do", "not capable"],
            "misunderstanding": ["not sure what you mean", "unclear"],
        }

        for category, patterns in refusal_patterns.items():
            if any(pattern in response_lower for pattern in patterns):
                return True, category

        # Check if response is suspiciously short (likely incomplete)
        if len(response.split()) < 20:
            return True, "incomplete"

        return False, None

    async def evaluate_prompts_batch(self,
                                    prompts: List[WritingPrompt],
                                    models: List[str]) -> Dict[str, List[ModelResponse]]:
        """Evaluate a batch of prompts across all models."""

        tasks = []
        for prompt in prompts:
            for model in models:
                tasks.append(self.evaluate_prompt(prompt, model))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Organize by prompt_id
        responses_by_prompt = {}
        for response in responses:
            if isinstance(response, Exception):
                continue
            if response.prompt_id not in responses_by_prompt:
                responses_by_prompt[response.prompt_id] = []
            responses_by_prompt[response.prompt_id].append(response)

        return responses_by_prompt

    async def close(self):
        """Cleanup resources."""
        await self.client.close()
```

---

## 4. Judge System

### 4.1 Judge Implementation

**Objective:** Ensemble judging with dual personas (expert + recipient) and best-of-N voting.

```python
# judging/judge.py

import asyncio
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
from .openrouter_client import OpenRouterClient
from prompt_generation.schemas import WritingPrompt
from evaluation.evaluator import ModelResponse
import random

class JudgmentChoice(str, Enum):
    """Possible judgment outcomes."""
    RESPONSE_A = "response_a"
    RESPONSE_B = "response_b"
    TIE = "tie"
    INCONCLUSIVE = "inconclusive"

@dataclass
class Judgment:
    """Single judgment from one judge."""
    judge_model: str
    judge_persona: str  # "expert" or "recipient"
    choice: JudgmentChoice
    reasoning: str
    confidence: float  # 0.0 to 1.0

@dataclass
class AggregatedJudgment:
    """Aggregated judgment across all judges and votes."""
    prompt_id: str
    model_a: str
    model_b: str
    judgments: List[Judgment]
    final_winner: str  # model name or "tie"
    vote_breakdown: Dict[str, int]  # counts per choice
    inter_judge_agreement: float  # Cohen's Kappa

class Judge:
    """Evaluates model responses using dual persona approach."""

    JUDGE_MODELS = [
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2-thinking",
        "google/gemini-3.0-pro"
    ]

    def __init__(self, api_key: str, votes_per_judge: int = 5):
        self.client = OpenRouterClient(api_key)
        self.votes_per_judge = votes_per_judge

    def _build_expert_judge_prompt(self,
                                   prompt: WritingPrompt,
                                   response_a: str,
                                   response_b: str) -> str:
        """Build prompt for writing expert persona."""

        return f"""
You are an expert writing coach and professional editor evaluating two writing samples.

CONTEXT:
{self._format_prompt_context(prompt)}

TASK:
{prompt.task_description}

--- RESPONSE A ---
{response_a}

--- RESPONSE B ---
{response_b}

EVALUATION CRITERIA:
Evaluate both responses as a writing expert on:

1. **Quality of writing**: Grammar, clarity, structure, coherence
2. **Tone appropriateness**: Does the tone match the context (formality, urgency, relationship)?
3. **Length appropriateness**: Is it the RIGHT length for this specific task?
4. **Task completion**: Does it fully address what was requested?
5. **Effectiveness**: Would this achieve the intended communication goal?
6. **Authenticity**: Does it sound like natural human writing, or overly "AI-generated"?
7. **Cliché avoidance**: Does it avoid obvious AI patterns and boilerplate language?
8. **Professional polish**: Is it ready to send as-is?

Which response is better overall for this specific task?

Respond in JSON format:
{{
  "choice": "response_a" | "response_b" | "tie",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your choice focusing on key differentiators"
}}
"""

    def _build_recipient_judge_prompt(self,
                                     prompt: WritingPrompt,
                                     response_a: str,
                                     response_b: str) -> str:
        """Build prompt for recipient persona."""

        recipient = prompt.recipient_persona

        return f"""
You are {recipient.name}, {recipient.role}, receiving this communication.

CONTEXT:
{self._format_prompt_context(prompt)}

You're receiving this message from {prompt.writer_persona.name} ({prompt.writer_persona.role}) at {prompt.company_name}.

--- MESSAGE A ---
{response_a}

--- MESSAGE B ---
{response_b}

EVALUATION:
As the RECIPIENT, which message would you find more effective and appropriate?

Consider:
1. **Clarity**: Is it immediately clear what is being communicated?
2. **Relevance**: Does it address what you need to know?
3. **Actionability**: Do you know what to do next (if action is needed)?
4. **Respect for your time**: Is it appropriately concise/detailed?
5. **Tone**: Does it feel appropriate for your relationship and the situation?
6. **Trust**: Does it feel authentic and genuine vs formulaic?

Which message would you prefer to receive?

Respond in JSON format:
{{
  "choice": "response_a" | "response_b" | "tie",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation from recipient's perspective"
}}
"""

    def _format_prompt_context(self, prompt: WritingPrompt) -> str:
        """Format prompt context for judge."""
        parts = [
            f"Writer: {prompt.writer_persona.name}, {prompt.writer_persona.role}",
            f"Company: {prompt.company_name} ({prompt.industry_title})",
            f"Recipient: {prompt.recipient_persona.name}, {prompt.recipient_persona.role}",
            f"Relationship: {prompt.recipient_persona.relationship}",
            f"Urgency: {prompt.context.urgency}",
            f"Context: {prompt.context.emotional_context}"
        ]
        return "\n".join(parts)

    async def judge_comparison(self,
                              prompt: WritingPrompt,
                              response_a: ModelResponse,
                              response_b: ModelResponse) -> AggregatedJudgment:
        """Judge a pairwise comparison with ensemble voting."""

        # Shuffle responses to eliminate position bias
        # Use deterministic shuffle based on prompt_id for reproducibility
        random.seed(prompt.prompt_id)
        if random.random() > 0.5:
            response_a, response_b = response_b, response_a
            swapped = True
        else:
            swapped = False

        all_judgments = []

        # Get judgments from each judge model with both personas
        for judge_model in self.JUDGE_MODELS:
            # Expert persona votes
            expert_votes = await self._get_votes(
                judge_model,
                "expert",
                prompt,
                response_a.response_text,
                response_b.response_text,
                n_votes=self.votes_per_judge
            )
            all_judgments.extend(expert_votes)

            # Recipient persona votes
            recipient_votes = await self._get_votes(
                judge_model,
                "recipient",
                prompt,
                response_a.response_text,
                response_b.response_text,
                n_votes=self.votes_per_judge
            )
            all_judgments.extend(recipient_votes)

        # Un-swap if needed
        if swapped:
            for judgment in all_judgments:
                if judgment.choice == JudgmentChoice.RESPONSE_A:
                    judgment.choice = JudgmentChoice.RESPONSE_B
                elif judgment.choice == JudgmentChoice.RESPONSE_B:
                    judgment.choice = JudgmentChoice.RESPONSE_A

        # Aggregate using majority-of-majorities
        final_winner = self._aggregate_votes(all_judgments, response_a.model, response_b.model)

        # Calculate inter-judge agreement
        agreement = self._calculate_agreement(all_judgments)

        # Vote breakdown
        vote_breakdown = {
            response_a.model: sum(1 for j in all_judgments if j.choice == JudgmentChoice.RESPONSE_A),
            response_b.model: sum(1 for j in all_judgments if j.choice == JudgmentChoice.RESPONSE_B),
            "tie": sum(1 for j in all_judgments if j.choice == JudgmentChoice.TIE)
        }

        return AggregatedJudgment(
            prompt_id=prompt.prompt_id,
            model_a=response_a.model,
            model_b=response_b.model,
            judgments=all_judgments,
            final_winner=final_winner,
            vote_breakdown=vote_breakdown,
            inter_judge_agreement=agreement
        )

    async def _get_votes(self,
                        judge_model: str,
                        persona: str,
                        prompt: WritingPrompt,
                        response_a: str,
                        response_b: str,
                        n_votes: int) -> List[Judgment]:
        """Get multiple votes from a judge with a specific persona."""

        if persona == "expert":
            judge_prompt = self._build_expert_judge_prompt(prompt, response_a, response_b)
        else:
            judge_prompt = self._build_recipient_judge_prompt(prompt, response_a, response_b)

        votes = []
        tasks = []

        for _ in range(n_votes):
            task = self.client.chat_completion(
                model=judge_model,
                messages=[{"role": "user", "content": judge_prompt}],
                temperature=0.3,  # Some variation but mostly consistent
                max_tokens=500
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue

            try:
                import json
                content = result["choices"][0]["message"]["content"]

                # Parse JSON response
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                    judgment_data = json.loads(json_str)
                else:
                    judgment_data = json.loads(content)

                choice_str = judgment_data["choice"]
                choice = JudgmentChoice(choice_str)

                judgment = Judgment(
                    judge_model=judge_model,
                    judge_persona=persona,
                    choice=choice,
                    reasoning=judgment_data["reasoning"],
                    confidence=judgment_data["confidence"]
                )
                votes.append(judgment)

            except Exception as e:
                # Failed to parse - skip this vote
                continue

        return votes

    def _aggregate_votes(self,
                        judgments: List[Judgment],
                        model_a: str,
                        model_b: str) -> str:
        """Aggregate votes using majority-of-majorities."""

        # Group by judge model + persona
        groups = {}
        for j in judgments:
            key = (j.judge_model, j.judge_persona)
            if key not in groups:
                groups[key] = []
            groups[key].append(j)

        # Get majority winner for each group
        group_winners = []
        for group_judgments in groups.values():
            votes = [j.choice for j in group_judgments]
            vote_counts = {
                JudgmentChoice.RESPONSE_A: votes.count(JudgmentChoice.RESPONSE_A),
                JudgmentChoice.RESPONSE_B: votes.count(JudgmentChoice.RESPONSE_B),
                JudgmentChoice.TIE: votes.count(JudgmentChoice.TIE)
            }
            majority_choice = max(vote_counts, key=vote_counts.get)
            group_winners.append(majority_choice)

        # Final majority across groups
        final_votes = {
            JudgmentChoice.RESPONSE_A: group_winners.count(JudgmentChoice.RESPONSE_A),
            JudgmentChoice.RESPONSE_B: group_winners.count(JudgmentChoice.RESPONSE_B),
            JudgmentChoice.TIE: group_winners.count(JudgmentChoice.TIE)
        }

        winner_choice = max(final_votes, key=final_votes.get)

        if winner_choice == JudgmentChoice.RESPONSE_A:
            return model_a
        elif winner_choice == JudgmentChoice.RESPONSE_B:
            return model_b
        else:
            return "tie"

    def _calculate_agreement(self, judgments: List[Judgment]) -> float:
        """Calculate inter-judge agreement (simplified Kappa)."""
        if len(judgments) < 2:
            return 1.0

        # Calculate pairwise agreement
        agreements = []
        for i in range(len(judgments)):
            for j in range(i+1, len(judgments)):
                if judgments[i].choice == judgments[j].choice:
                    agreements.append(1)
                else:
                    agreements.append(0)

        return sum(agreements) / len(agreements) if agreements else 0.0

    async def close(self):
        """Cleanup resources."""
        await self.client.close()
```

### 4.2 Judgment Storage

```python
# judging/judgment_storage.py

import sqlite3
import json
from pathlib import Path
from typing import List
from .judge import AggregatedJudgment, Judgment

class JudgmentStorage:
    """Stores judgment results."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize judgment storage schema."""
        conn = sqlite3.connect(self.db_path)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS judgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT,
                model_a TEXT,
                model_b TEXT,
                judge_model TEXT,
                judge_persona TEXT,
                choice TEXT,
                reasoning TEXT,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS aggregated_judgments (
                prompt_id TEXT PRIMARY KEY,
                model_a TEXT,
                model_b TEXT,
                final_winner TEXT,
                vote_breakdown TEXT,  -- JSON
                inter_judge_agreement REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_judgment ON judgments(prompt_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_winner ON aggregated_judgments(final_winner)")

        conn.commit()
        conn.close()

    def save_aggregated_judgment(self, agg_judgment: AggregatedJudgment):
        """Save aggregated judgment result."""
        conn = sqlite3.connect(self.db_path)

        # Save individual judgments
        for judgment in agg_judgment.judgments:
            conn.execute("""
                INSERT INTO judgments (prompt_id, model_a, model_b, judge_model, judge_persona, choice, reasoning, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agg_judgment.prompt_id,
                agg_judgment.model_a,
                agg_judgment.model_b,
                judgment.judge_model,
                judgment.judge_persona,
                judgment.choice.value,
                judgment.reasoning,
                judgment.confidence
            ))

        # Save aggregated result
        conn.execute("""
            INSERT OR REPLACE INTO aggregated_judgments
            (prompt_id, model_a, model_b, final_winner, vote_breakdown, inter_judge_agreement)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            agg_judgment.prompt_id,
            agg_judgment.model_a,
            agg_judgment.model_b,
            agg_judgment.final_winner,
            json.dumps(agg_judgment.vote_breakdown),
            agg_judgment.inter_judge_agreement
        ))

        conn.commit()
        conn.close()
```

---

## 5. Configuration System

### 5.1 Evaluation Configuration

```python
# config/eval_config.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from pathlib import Path

class ModelConfig(BaseModel):
    """Configuration for models to evaluate."""
    gemini_models: List[str] = Field(default=["google/gemini-3.0-pro", "google/gemini-3.0-flash"])
    competitor_models: Dict[str, List[str]] = Field(default={
        "pro": [
            "openai/gpt-5.2-thinking",
            "anthropic/claude-opus-4.5",
            "x-ai/grok-4.1-thinking",
            "moonshot/kimi-k2-thinking"
        ],
        "flash": [
            "openai/gpt-4.1",
            "anthropic/claude-sonnet-4.5"
        ]
    })

class JudgeConfig(BaseModel):
    """Configuration for judging."""
    judge_models: List[str] = Field(default=[
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2-thinking",
        "google/gemini-3.0-pro"
    ])
    votes_per_judge: int = Field(default=5)
    use_dual_persona: bool = Field(default=True)

class PromptConfig(BaseModel):
    """Configuration for prompt generation."""
    n_prompts: int = Field(default=500)
    occupation_codes: Optional[List[str]] = None
    industry_codes: Optional[List[str]] = None
    job_zones: Optional[List[int]] = None
    formality_levels: Optional[List[str]] = None
    random_seed: int = Field(default=42)

class EvalConfig(BaseModel):
    """Complete evaluation configuration."""
    run_name: Optional[str] = None
    preset: Optional[str] = None  # "sanity", "dev", "standard", etc.

    models: ModelConfig = Field(default_factory=ModelConfig)
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)

    max_concurrent: int = Field(default=10)
    checkpoint_interval: int = Field(default=10)  # Save checkpoint every N prompts

    output_dir: Path = Field(default=Path("results"))

    @classmethod
    def from_preset(cls, preset: str) -> "EvalConfig":
        """Load configuration from preset."""
        presets = {
            "sanity": {"prompts": {"n_prompts": 5}, "judge": {"votes_per_judge": 1}},
            "smoke": {"prompts": {"n_prompts": 20}, "judge": {"votes_per_judge": 3}},
            "dev": {"prompts": {"n_prompts": 50}, "judge": {"votes_per_judge": 3}},
            "quick": {"prompts": {"n_prompts": 100}, "judge": {"votes_per_judge": 5}},
            "light": {"prompts": {"n_prompts": 200}, "judge": {"votes_per_judge": 3}},
            "standard": {"prompts": {"n_prompts": 500}, "judge": {"votes_per_judge": 5}},
            "thorough": {"prompts": {"n_prompts": 1000}, "judge": {"votes_per_judge": 5}},
            "comprehensive": {"prompts": {"n_prompts": 2000}, "judge": {"votes_per_judge": 5}},
            "deep": {"prompts": {"n_prompts": 5000}, "judge": {"votes_per_judge": 5}},
            "full": {"prompts": {"n_prompts": 10000}, "judge": {"votes_per_judge": 5}},
        }

        preset_config = presets.get(preset, presets["standard"])

        config = cls()
        if "prompts" in preset_config:
            for k, v in preset_config["prompts"].items():
                setattr(config.prompts, k, v)
        if "judge" in preset_config:
            for k, v in preset_config["judge"].items():
                setattr(config.judge, k, v)

        config.preset = preset
        return config

    def estimate_cost(self) -> Dict[str, float]:
        """Estimate cost for this configuration."""
        # Simplified cost estimation
        # Real implementation would use OpenRouter pricing API

        n_prompts = self.prompts.n_prompts
        n_model_pairs = len(self.models.competitor_models["pro"]) + len(self.models.competitor_models["flash"])
        n_comparisons = n_prompts * n_model_pairs

        # Response generation
        avg_tokens_per_response = 500
        response_cost = (n_comparisons * 2 * avg_tokens_per_response * 0.01) / 1000

        # Judging
        n_judges = len(self.judge.judge_models)
        votes_per_comparison = self.judge.votes_per_judge * n_judges * (2 if self.judge.use_dual_persona else 1)
        total_judge_calls = n_comparisons * votes_per_comparison
        judge_cost = (total_judge_calls * 300 * 0.01) / 1000

        total_cost = response_cost + judge_cost

        return {
            "response_generation": response_cost,
            "judging": judge_cost,
            "total": total_cost,
            "n_prompts": n_prompts,
            "n_comparisons": n_comparisons,
            "total_judge_calls": total_judge_calls
        }
```

### 5.2 Cost Estimation Display

```python
# ui/cost_estimator.py

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from config.eval_config import EvalConfig

def display_cost_estimate(config: EvalConfig):
    """Display cost and time estimate before running eval."""
    console = Console()

    estimate = config.estimate_cost()

    # Build estimate panel
    content = f"""
[bold]Prompts:[/bold]              {estimate['n_prompts']}
[bold]Model pairs:[/bold]          {len(config.models.competitor_models['pro']) + len(config.models.competitor_models['flash'])}
[bold]Total comparisons:[/bold]    {estimate['n_comparisons']}

[bold]Judge config:[/bold]         {len(config.judge.judge_models)} judges × {config.judge.votes_per_judge} votes × {'2 personas' if config.judge.use_dual_persona else '1 persona'}
[bold]Total judge calls:[/bold]    {estimate['total_judge_calls']}

[bold cyan]ESTIMATED COST[/bold cyan]
  Response generation:  ${estimate['response_generation']:.2f}
  Judging:              ${estimate['judging']:.2f}
  [bold]Total:                ${estimate['total']:.2f}[/bold]

[bold cyan]ESTIMATED TIME[/bold cyan]
  With rate limits:     {estimate['n_comparisons'] // 100} - {estimate['n_comparisons'] // 50} hours
  Parallelized:         {estimate['n_comparisons'] // 200} - {estimate['n_comparisons'] // 100} hours
"""

    panel = Panel(
        content,
        title="[bold]EVAL RUN ESTIMATE[/bold]",
        border_style="cyan"
    )

    console.print(panel)
```

---

## 6. Progress Visualization

### 6.1 Live Progress Dashboard

```python
# ui/progress_dashboard.py

from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from rich.console import Group
from rich import box
import time

class ProgressDashboard:
    """Real-time progress visualization for evaluation runs."""

    def __init__(self, total_prompts: int, model_pairs: List[str]):
        self.total_prompts = total_prompts
        self.model_pairs = model_pairs
        self.start_time = time.time()

        self.completed_prompts = 0
        self.current_prompt_info = {}
        self.win_rates = {pair: {"wins": 0, "losses": 0, "ties": 0} for pair in model_pairs}
        self.errors = {"retries": 0, "failures": 0, "rate_limits": 0}

        self.layout = Layout()
        self._setup_layout()

    def _setup_layout(self):
        """Setup dashboard layout."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="progress", size=6),
            Layout(name="model_pairs", size=len(self.model_pairs) + 3),
            Layout(name="current", size=12),
            Layout(name="stats", size=8),
            Layout(name="activity", size=8),
            Layout(name="errors", size=3)
        )

    def build_display(self) -> Layout:
        """Build current display state."""
        # Header
        elapsed = time.time() - self.start_time
        eta = (elapsed / max(self.completed_prompts, 1)) * (self.total_prompts - self.completed_prompts)

        self.layout["header"].update(
            Panel(
                f"[bold]GEMINI WRITING EVAL[/bold] | "
                f"Elapsed: {self._format_time(elapsed)} | "
                f"ETA: {self._format_time(eta)}",
                style="bold cyan"
            )
        )

        # Overall progress
        progress_pct = (self.completed_prompts / self.total_prompts) * 100
        progress_bar = "█" * int(progress_pct // 2) + "░" * (50 - int(progress_pct // 2))
        self.layout["progress"].update(
            Panel(
                f"{progress_bar} {self.completed_prompts}/{self.total_prompts} ({progress_pct:.1f}%)",
                title="Overall Progress"
            )
        )

        # Model pairs
        pairs_table = Table(box=box.SIMPLE)
        pairs_table.add_column("Pair")
        pairs_table.add_column("Progress")
        pairs_table.add_column("Win Rate")

        for pair in self.model_pairs:
            stats = self.win_rates[pair]
            total = stats["wins"] + stats["losses"] + stats["ties"]
            win_rate = (stats["wins"] / total * 100) if total > 0 else 0
            progress = f"{total}/{self.total_prompts}"
            pairs_table.add_row(pair, progress, f"{win_rate:.1f}%")

        self.layout["model_pairs"].update(Panel(pairs_table, title="Model Pairs"))

        # Additional layouts...
        # (stats, activity, errors)

        return self.layout

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"

    def update(self, **kwargs):
        """Update dashboard state."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
```

---

## 7. Checkpoint and Resume System

### 7.1 Checkpoint Manager

```python
# persistence/checkpoint.py

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

class CheckpointManager:
    """Manages checkpoints for resumable evaluation."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_path = run_dir / "checkpoint.json"

    def save_checkpoint(self,
                       completed_prompts: List[str],
                       current_phase: str,
                       metadata: Dict):
        """Save current progress."""
        checkpoint = {
            "timestamp": datetime.utcnow().isoformat(),
            "completed_prompts": completed_prompts,
            "current_phase": current_phase,
            "metadata": metadata
        }

        with open(self.checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self) -> Optional[Dict]:
        """Load checkpoint if exists."""
        if not self.checkpoint_path.exists():
            return None

        with open(self.checkpoint_path, 'r') as f:
            return json.load(f)

    def has_checkpoint(self) -> bool:
        """Check if checkpoint exists."""
        return self.checkpoint_path.exists()
```

---

## 8. Analysis and Reporting

### 8.1 Statistical Analysis

```python
# analysis/statistical_analysis.py

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List
import sqlite3

class StatisticalAnalyzer:
    """Performs statistical analysis on evaluation results."""

    def __init__(self, results_db: Path):
        self.db_path = results_db
        self.conn = sqlite3.connect(results_db)

    def calculate_win_rates(self) -> pd.DataFrame:
        """Calculate win rates for each model pair."""
        query = """
        SELECT
            model_a,
            model_b,
            final_winner,
            COUNT(*) as count
        FROM aggregated_judgments
        GROUP BY model_a, model_b, final_winner
        """

        results = pd.read_sql(query, self.conn)

        # Pivot to get win/loss/tie counts
        win_rates = []
        for (model_a, model_b), group in results.groupby(['model_a', 'model_b']):
            total = group['count'].sum()
            wins_a = group[group['final_winner'] == model_a]['count'].sum()
            wins_b = group[group['final_winner'] == model_b]['count'].sum()
            ties = group[group['final_winner'] == 'tie']['count'].sum()

            # Calculate confidence intervals (Wilson score)
            win_rate, ci_low, ci_high = self._wilson_score_interval(wins_a, total)

            win_rates.append({
                'model_a': model_a,
                'model_b': model_b,
                'wins_a': wins_a,
                'wins_b': wins_b,
                'ties': ties,
                'total': total,
                'win_rate_a': win_rate,
                'ci_low': ci_low,
                'ci_high': ci_high
            })

        return pd.DataFrame(win_rates)

    def _wilson_score_interval(self, wins: int, total: int, confidence: float = 0.95) -> tuple:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return 0.0, 0.0, 0.0

        p = wins / total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)

        denominator = 1 + z**2 / total
        centre = (p + z**2 / (2 * total)) / denominator
        margin = (z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2))) / denominator

        return p, centre - margin, centre + margin

    def identify_weaknesses(self) -> Dict:
        """Identify specific areas of weakness."""
        # Analyze by occupation
        occupation_query = """
        SELECT
            p.occupation_title,
            aj.model_a,
            aj.final_winner,
            COUNT(*) as count
        FROM aggregated_judgments aj
        JOIN prompts p ON aj.prompt_id = p.prompt_id
        WHERE aj.model_a LIKE '%gemini%'
        GROUP BY p.occupation_title, aj.model_a, aj.final_winner
        """

        occupation_df = pd.read_sql(occupation_query, self.conn)

        # Find occupations where Gemini loses most
        weaknesses = {}
        # ... detailed analysis logic

        return weaknesses
```

### 8.2 Interactive TUI Viewer

```python
# ui/eval_viewer.py

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Static
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
import sqlite3
from pathlib import Path

class EvalViewer(App):
    """Interactive TUI for browsing evaluation results."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "filter", "Filter"),
        Binding("s", "sort", "Sort"),
        ("d", "detail", "Detail View")
    ]

    def __init__(self, results_db: Path):
        super().__init__()
        self.db_path = results_db
        self.conn = sqlite3.connect(results_db)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            DataTable(id="results_table"),
            id="main_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Load data on mount."""
        table = self.query_one(DataTable)

        # Add columns
        table.add_columns("Prompt ID", "Occupation", "Industry", "Winner", "Votes")

        # Load data
        cursor = self.conn.execute("""
            SELECT
                aj.prompt_id,
                p.occupation_title,
                p.industry_title,
                aj.final_winner,
                aj.vote_breakdown
            FROM aggregated_judgments aj
            JOIN prompts p ON aj.prompt_id = p.prompt_id
            ORDER BY aj.prompt_id
        """)

        for row in cursor.fetchall():
            table.add_row(*row)

    def action_detail(self) -> None:
        """Show detailed view of selected prompt."""
        # Implementation for detailed drill-down
        pass
```

### 8.3 PDF Report Generator

```python
# reporting/pdf_generator.py

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.units import inch
from reportlab.lib import colors
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

class PDFReportGenerator:
    """Generates comprehensive PDF evaluation report."""

    def __init__(self, results_db: Path, output_path: Path):
        self.db_path = results_db
        self.output_path = output_path
        self.doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        self.styles = getSampleStyleSheet()
        self.story = []

    def generate_report(self):
        """Generate full PDF report."""
        self._add_cover_page()
        self._add_executive_summary()
        self._add_methodology()
        self._add_aggregate_results()
        self._add_statistical_analysis()
        self._add_weakness_analysis()
        self._add_detailed_breakdown()

        # Build PDF
        self.doc.build(self.story)

    def _add_cover_page(self):
        """Add cover page."""
        title = Paragraph(
            "Gemini Writing Evaluation Framework<br/>Final Analysis Report",
            self.styles['Title']
        )
        self.story.append(title)
        self.story.append(Spacer(1, 0.5*inch))
        # ... additional cover page content

    def _add_executive_summary(self):
        """Add executive summary section."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Executive Summary", self.styles['Heading1']))
        # ... summary content

    def _add_aggregate_results(self):
        """Add aggregate win rates and charts."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Aggregate Results", self.styles['Heading1']))

        # Generate charts
        self._generate_win_rate_chart()
        self._generate_heatmap()

        # Add to report
        # ...

    def _generate_win_rate_chart(self):
        """Generate win rate visualization."""
        # Load win rates from DB
        # Create matplotlib chart
        # Save as image
        # Return path to image
        pass

    def _add_weakness_analysis(self):
        """Add detailed weakness identification."""
        self.story.append(PageBreak())
        self.story.append(Paragraph("Weakness Analysis", self.styles['Heading1']))

        # Analyze by dimension
        self._analyze_by_occupation()
        self._analyze_by_formality()
        self._analyze_by_task_type()
        # ...
```

---

## 9. Main Orchestrator

### 9.1 Main Evaluation Runner

```python
# main.py

import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from rich.console import Console

from config.eval_config import EvalConfig
from data_acquisition.onet_downloader import ONetDownloader
from data_acquisition.naics_loader import NAICSLoader
from data_acquisition.company_database import CompanyDatabase
from prompt_generation.phase2_combination import Phase2Combiner
from prompt_generation.prompt_manager import PromptManager
from evaluation.evaluator import Evaluator
from judging.judge import Judge
from judging.judgment_storage import JudgmentStorage
from persistence.checkpoint import CheckpointManager
from ui.cost_estimator import display_cost_estimate
from ui.progress_dashboard import ProgressDashboard
from analysis.statistical_analysis import StatisticalAnalyzer
from reporting.pdf_generator import PDFReportGenerator

console = Console()

async def main():
    """Main entry point for evaluation framework."""
    parser = argparse.ArgumentParser(description="Gemini Writing Evaluation Framework")
    parser.add_argument("--preset", type=str, help="Use preset configuration")
    parser.add_argument("--prompts", type=int, help="Number of prompts to evaluate")
    parser.add_argument("--dry-run", action="store_true", help="Show estimate without running")
    parser.add_argument("--resume", type=str, help="Resume from checkpoint directory")
    parser.add_argument("--api-key", type=str, required=True, help="OpenRouter API key")

    args = parser.parse_args()

    # Load configuration
    if args.preset:
        config = EvalConfig.from_preset(args.preset)
    else:
        config = EvalConfig()

    if args.prompts:
        config.prompts.n_prompts = args.prompts

    # Display cost estimate
    display_cost_estimate(config)

    if args.dry_run:
        console.print("\n[yellow]Dry run - exiting without evaluation[/yellow]")
        return

    # Confirm to proceed
    if not console.input("\n[bold]Proceed? [y/N]: [/bold]").lower().startswith('y'):
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Setup run directory
    if args.resume:
        run_dir = Path(args.resume)
        console.print(f"[cyan]Resuming from {run_dir}[/cyan]")
    else:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        run_name = config.run_name or f"eval_{timestamp}"
        run_dir = config.output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[cyan]Starting new run: {run_dir}[/cyan]")

    # Initialize components
    checkpoint_mgr = CheckpointManager(run_dir)
    prompt_mgr = PromptManager(run_dir / "results.db")
    judgment_storage = JudgmentStorage(run_dir / "results.db")

    # Check for checkpoint
    checkpoint = checkpoint_mgr.load_checkpoint()
    if checkpoint:
        console.print(f"[green]Found checkpoint from {checkpoint['timestamp']}[/green]")
        completed_prompts = set(checkpoint['completed_prompts'])
    else:
        completed_prompts = set()

    # Stage 1: Data acquisition (if needed)
    console.print("\n[bold cyan]Stage 1: Data Acquisition[/bold cyan]")
    onet = ONetDownloader()
    if not onet.db_path.exists():
        await onet.download_database()
        onet.load_to_sqlite()

    naics = NAICSLoader()
    if not naics.db_path.exists():
        naics.download_naics()
        naics.load_to_sqlite(naics.data_dir / "naics_2022.xlsx")

    companies = CompanyDatabase()
    # Load company data if needed

    # Stage 2: Prompt generation
    console.print("\n[bold cyan]Stage 2: Prompt Generation[/bold cyan]")
    combiner = Phase2Combiner(random_seed=config.prompts.random_seed)
    prompts = combiner.generate_prompts(
        n_prompts=config.prompts.n_prompts,
        occupation_codes=config.prompts.occupation_codes,
        industry_codes=config.prompts.industry_codes
    )
    prompt_mgr.save_prompts(prompts)
    console.print(f"[green]Generated {len(prompts)} prompts[/green]")

    # Stage 3: Response generation
    console.print("\n[bold cyan]Stage 3: Response Generation[/bold cyan]")
    evaluator = Evaluator(
        api_key=args.api_key,
        models=config.models.gemini_models + config.models.competitor_models["pro"] + config.models.competitor_models["flash"],
        max_concurrent=config.max_concurrent
    )

    # Filter out completed prompts
    remaining_prompts = [p for p in prompts if p.prompt_id not in completed_prompts]

    # Setup progress dashboard
    dashboard = ProgressDashboard(
        total_prompts=len(prompts),
        model_pairs=["Gemini Pro vs GPT-5.2", "Gemini Pro vs Claude Opus", ...]
    )

    # Evaluate in batches with checkpoint
    batch_size = config.checkpoint_interval
    for i in range(0, len(remaining_prompts), batch_size):
        batch = remaining_prompts[i:i+batch_size]

        responses = await evaluator.evaluate_prompts_batch(
            batch,
            config.models.gemini_models + config.models.competitor_models["pro"]
        )

        # Stage 4: Judging
        judge = Judge(api_key=args.api_key, votes_per_judge=config.judge.votes_per_judge)

        for prompt in batch:
            prompt_responses = responses.get(prompt.prompt_id, [])

            # Create pairwise comparisons (Gemini vs each competitor)
            for gemini_response in [r for r in prompt_responses if "gemini" in r.model.lower()]:
                for competitor_response in [r for r in prompt_responses if "gemini" not in r.model.lower()]:
                    judgment = await judge.judge_comparison(
                        prompt,
                        gemini_response,
                        competitor_response
                    )
                    judgment_storage.save_aggregated_judgment(judgment)

        # Save checkpoint
        completed_prompts.update([p.prompt_id for p in batch])
        checkpoint_mgr.save_checkpoint(
            list(completed_prompts),
            "judging",
            {"total_prompts": len(prompts)}
        )

        # Update dashboard
        dashboard.update(completed_prompts=len(completed_prompts))

    await evaluator.close()

    # Stage 5: Analysis
    console.print("\n[bold cyan]Stage 5: Statistical Analysis[/bold cyan]")
    analyzer = StatisticalAnalyzer(run_dir / "results.db")
    win_rates = analyzer.calculate_win_rates()
    weaknesses = analyzer.identify_weaknesses()

    # Save analysis results
    win_rates.to_csv(run_dir / "analysis" / "win_rates.csv")

    # Stage 6: Report generation
    console.print("\n[bold cyan]Stage 6: Report Generation[/bold cyan]")
    report_gen = PDFReportGenerator(
        run_dir / "results.db",
        run_dir / "reports" / "report.pdf"
    )
    report_gen.generate_report()

    console.print(f"\n[bold green]Evaluation complete! Results saved to {run_dir}[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 10. Project Structure

### 10.1 Directory Layout

```
gemini-writing-eval/
├── README.md
├── requirements.txt
├── setup.py
├── main.py                      # Main entry point
├── config/
│   ├── __init__.py
│   └── eval_config.py           # Configuration classes
├── data_acquisition/
│   ├── __init__.py
│   ├── onet_downloader.py       # O*NET data acquisition
│   ├── naics_loader.py          # NAICS codes
│   ├── company_database.py      # Company data
│   └── name_generator.py        # Name generation
├── prompt_generation/
│   ├── __init__.py
│   ├── schemas.py               # Pydantic models
│   ├── phase1_llm_generation.py # LLM-based generation
│   ├── phase2_combination.py    # Algorithmic combination
│   └── prompt_manager.py        # Storage/retrieval
├── evaluation/
│   ├── __init__.py
│   ├── openrouter_client.py     # API client
│   └── evaluator.py             # Evaluation orchestrator
├── judging/
│   ├── __init__.py
│   ├── judge.py                 # Judge implementation
│   └── judgment_storage.py      # Judgment storage
├── persistence/
│   ├── __init__.py
│   └── checkpoint.py            # Checkpoint manager
├── analysis/
│   ├── __init__.py
│   ├── statistical_analysis.py  # Statistical analysis
│   └── weakness_identifier.py   # Weakness detection
├── reporting/
│   ├── __init__.py
│   └── pdf_generator.py         # PDF report generation
├── ui/
│   ├── __init__.py
│   ├── cost_estimator.py        # Cost display
│   ├── progress_dashboard.py    # Live progress
│   └── eval_viewer.py           # TUI viewer
├── scripts/
│   ├── download_onet.py         # Data download scripts
│   ├── download_naics.py
│   └── seed_companies.py
├── data/                        # Downloaded data (gitignored)
│   ├── onet/
│   ├── naics/
│   └── companies/
└── results/                     # Evaluation results (gitignored)
    ├── eval_2024-01-15_14-30-00/
    └── latest -> eval_2024-01-15_14-30-00/
```

### 10.2 Dependencies

```txt
# requirements.txt

# Core
python>=3.10
pydantic>=2.0
asyncio
aiofiles

# API & HTTP
httpx>=0.24
openai>=1.0  # For OpenAI-compatible client
tenacity>=8.0  # Retry logic

# Data & Analysis
pandas>=2.0
numpy>=1.24
scipy>=1.10
sqlite3

# Visualization & UI
rich>=13.0
textual>=0.40  # TUI framework
plotly>=5.0
matplotlib>=3.7

# PDF Generation
reportlab>=4.0

# Utilities
python-dotenv>=1.0
click>=8.0  # CLI framework (alternative to argparse)
```

---

## 11. Implementation Timeline

### Phase 1: Foundation (Weeks 1-2)
- Set up project structure
- Implement data acquisition (O*NET, NAICS, companies)
- Create prompt schemas and basic generation
- Build OpenRouter API client

### Phase 2: Core Evaluation (Weeks 3-4)
- Implement evaluation orchestrator
- Build judge system with dual personas
- Create checkpoint/resume functionality
- Develop configuration system

### Phase 3: User Experience (Week 5)
- Build live progress dashboard
- Implement cost estimation
- Create preset configurations
- Add interactive controls

### Phase 4: Analysis & Reporting (Week 6)
- Implement statistical analysis
- Build weakness identification
- Create TUI viewer
- Generate PDF reports

### Phase 5: Testing & Refinement (Weeks 7-8)
- Run test evaluations at multiple scales
- Validate statistical methodology
- Refine prompts based on pilot runs
- Optimize performance and cost

---

## 12. Key Design Decisions

### 12.1 Why OpenRouter?
- Unified API access to all models
- Automatic rate limiting and load balancing
- Cost tracking built-in
- No need to manage multiple API keys

### 12.2 Why SQLite?
- Self-contained, no server needed
- Efficient for read-heavy workloads
- Easy to backup and share
- Perfect for result storage and querying

### 12.3 Why Dual Judge Personas?
- Writing expert: Evaluates craft and quality
- Recipient: Evaluates effectiveness and appropriateness
- Together: More comprehensive than either alone
- Reflects real-world: writing must satisfy both producer and consumer

### 12.4 Why Majority-of-Majorities?
- Most robust aggregation method
- Reduces impact of any single judge's bias
- Each judge's internal consistency (best-of-5) before cross-judge aggregation
- Proven methodology in evaluation research

### 12.5 Why No Word Limits?
- Real writing doesn't have arbitrary limits
- Lets models demonstrate judgment about appropriate length
- More realistic to actual use cases
- Length appropriateness is an evaluation criterion, not a constraint

---

## 13. Risk Mitigation

### 13.1 API Reliability
**Risk:** API failures disrupt evaluation
**Mitigation:**
- Automatic retries with exponential backoff
- Checkpoint every N prompts
- Continue evaluation despite partial failures
- Comprehensive failure logging

### 13.2 Cost Overruns
**Risk:** Evaluation costs more than expected
**Mitigation:**
- Live cost estimation before execution
- User confirmation required
- Incremental preset system (start small)
- Checkpoint allows stopping and resuming

### 13.3 Judge Bias
**Risk:** Judges systematically favor certain models
**Mitigation:**
- Ensemble of 3 different judge models
- Deterministic response shuffling
- Position bias detection
- Inter-judge agreement metrics

### 13.4 Prompt Quality
**Risk:** Generated prompts don't represent real tasks
**Mitigation:**
- Ground in real O*NET occupational data
- Use real companies for authenticity
- Manual review of sample prompts
- Pilot runs to validate before large-scale

### 13.5 Statistical Validity
**Risk:** Results lack statistical power
**Mitigation:**
- Wilson score confidence intervals
- Preset system supports scaling to needed N
- Statistical significance testing
- Clear reporting of uncertainty

---

## 14. Success Criteria

The implementation will be considered successful if it achieves:

1. **Repeatable Evaluation**
   - Can run multiple times with reproducible results
   - Clear documentation of all configuration
   - Seed-based reproducibility where needed

2. **Meaningful Inspection**
   - Interactive TUI for detailed exploration
   - Drill-down from aggregate to individual judgments
   - Filter and sort by multiple dimensions

3. **High Trustworthiness**
   - Robust statistical methodology
   - Transparent bias detection and reporting
   - Comprehensive documentation
   - Clear confidence intervals

4. **Actionable Insights**
   - Specific areas of weakness identified
   - Breakdown by occupation, task type, formality
   - Comparative analysis across competitors
   - Recommendations for improvement

5. **Practical Usability**
   - Clear cost/time estimates
   - Preset configurations for different use cases
   - Checkpoint/resume for long runs
   - User-friendly CLI and TUI

---

## 15. Future Extensions

### 15.1 Multilingual Support
- Extend to non-English languages
- Regional variant handling (already in schema)
- Cross-lingual comparison

### 15.2 Human Baselines
- Collect human-written responses for subset
- Compare models to human performance
- Validate judge alignment with human preferences

### 15.3 Longitudinal Tracking
- Track model improvements over time
- Compare evaluation runs across model versions
- Trend analysis

### 15.4 Custom Prompt Sets
- Allow users to upload custom prompts
- Domain-specific evaluation tracks
- Company-specific use cases

### 15.5 Real-Time Monitoring
- Dashboard for ongoing model performance
- Alert system for degradation
- A/B testing integration

---

## Conclusion

This implementation plan provides a comprehensive blueprint for building the Gemini Writing Evaluation Framework. The system is designed to be:

- **Robust**: Handles failures gracefully, checkpoints progress, retries intelligently
- **Scalable**: From 5-prompt sanity checks to 10,000-prompt deep dives
- **Trustworthy**: Statistical rigor, bias detection, transparent methodology
- **Actionable**: Identifies specific weaknesses, not just aggregate scores
- **User-friendly**: Clear costs, live progress, interactive exploration

The modular architecture allows for iterative development and testing at each stage, with clear interfaces between components. The use of modern Python tooling (asyncio, pydantic, rich, textual) ensures a good developer experience and maintainable codebase.

Key innovations include:
- Grounding prompts in real occupational data (O*NET) and real companies
- Dual judge personas (expert + recipient) for comprehensive evaluation
- Majority-of-majorities aggregation for robust results
- Live cost estimation and progress visualization
- Comprehensive weakness identification across multiple dimensions

The framework is ready for implementation following the phased timeline outlined above.
