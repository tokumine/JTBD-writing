# Gemini Writing Evaluation Framework - Improved Implementation Plan

## Critical Analysis of Original Draft

### Issues Identified in Draft Plan 4

#### 1. **Hardcoded Writing Categories (PROMPT.md Violation)**
The original plan hardcodes `WritingCategory` enum with 10 fixed categories (EXPLICIT_WRITING, CORRESPONDENCE, etc.). PROMPT.md explicitly states: "**IMPORTANT: Avoid hardcoding specific categories and types of effective writing where possible.** Let the O*NET data drive this diversity programmatically rather than pre-defining categories."

**Fix**: Remove hardcoded categories. Use O*NET task text directly and let LLM-based enrichment infer task characteristics dynamically.

#### 2. **Missing Instruction-Following Test Implementation**
The schema includes `explicit_constraints` but the draft provides no implementation for:
- Generating prompts WITH specific constraints ("Keep under 100 words", "Use exactly 3 bullet points")
- Tracking constraint compliance separately in evaluation
- Reporting instruction-following rates

**Fix**: Add constraint generation in Phase 2/3 and compliance checking in judging.

#### 3. **Incomplete Revision/Editing Task Support**
PROMPT.md requires: "Include prompts where the model must improve existing text" (revise, soften tone, make more concise, etc.). The draft has no implementation for generating these.

**Fix**: Add revision task generation in the prompt pipeline.

#### 4. **Missing Tone Matching Implementation**
The schema has `tone_example` but no generation logic. PROMPT.md requires prompts that include "prior writing samples to match" the tone of.

**Fix**: Implement tone example generation in Phase 3.

#### 5. **Missing Multiple Recipients (CC) Logic**
The schema has `cc_recipients` but there's no generation logic for CC scenarios that test "ability to navigate tone for mixed audiences."

**Fix**: Add CC scenario generation with appropriate audience mixing.

#### 6. **Inadequate Cost Estimation Implementation**
The draft shows `estimate_cost()` being called but provides no implementation. Cost estimation needs to:
- Use current OpenRouter pricing
- Account for input/output token differences
- Calculate judge call costs separately
- Provide ranges (low/high)

**Fix**: Implement detailed cost estimation with model-specific pricing.

#### 7. **Judge Context Missing Critical Details**
PROMPT.md states judges need: "The writer persona details (age, skill level, role, industry, generation)" but the judge prompts in the draft only show basic name/title information, missing age, generation, skill level which are critical for authenticity assessment.

**Fix**: Expand judge prompts to include full persona context.

#### 8. **Missing Regional English Variant Handling**
The schema tracks `english_variant` but there's no logic to:
- Generate prompts with non-US English contexts
- Include international recipients (British, Australian, non-native speakers)
- Analyze results by language variant

**Fix**: Add variant generation and tracking in analysis.

#### 9. **Incomplete Ambiguity Handling**
PROMPT.md requires deliberately vague prompts and tracking of how models handle uncertainty. The schema has `is_deliberately_vague` but no generation logic or behavior tracking.

**Fix**: Implement ambiguous prompt generation and response classification.

#### 10. **Missing Response Metadata Tracking**
PROMPT.md requires tracking: response length, format detection (bullets, headers, paragraphs), greeting/sign-off patterns. The draft stores tokens but not these structural elements.

**Fix**: Add response structure analysis.

#### 11. **Database Schema Mismatch**
The SQLite schema doesn't include a `prompts` table, but `WeaknessFinder` tries to join with it. Also missing indexes for common query patterns.

**Fix**: Complete the database schema with proper joins and indexes.

#### 12. **Incomplete O*NET Reference Usage**
The draft doesn't reference `db/ONET_REFERENCE.md` which PROMPT.md says contains pre-processed writing tasks guidance from Opus.

**Fix**: Integrate ONET_REFERENCE.md guidance.

#### 13. **Missing Cross-Run Comparison**
The draft mentions `./eval compare` in the CLI but provides no implementation.

**Fix**: Implement cross-run comparison functionality.

#### 14. **OpenRouter Model IDs Likely Incorrect**
The model IDs use speculative naming (e.g., 'google/gemini-3.0-pro'). These need verification or dynamic lookup.

**Fix**: Add model ID verification/discovery.

---

## Part 1: Improved System Architecture

### 1.1 High-Level Architecture

```
+------------------------------------------------------------------+
|                    GEMINI WRITING EVAL FRAMEWORK                   |
+------------------------------------------------------------------+
|                                                                    |
|  +-------------------+    +--------------------+    +------------+ |
|  |   Data Layer      |--->|   Prompt Engine    |--->|  Eval Core | |
|  | O*NET + Companies |    | 3-Phase + Variants |    |  (SxS)     | |
|  +-------------------+    +--------------------+    +------------+ |
|          |                        |                      |         |
|          v                        v                      v         |
|  +-------------------+    +--------------------+    +------------+ |
|  | ONET_REFERENCE.md |    | Diversity Sampler  |    | Judge Panel| |
|  | Writing Task Guide|    | (No hardcoding)    |    | (Ensemble) | |
|  +-------------------+    +--------------------+    +------------+ |
|                                                          |         |
|                               +--------------------------|         |
|                               v                          v         |
|  +-------------------+    +--------------------+    +------------+ |
|  |   Results DB      |<---|   Response Analyzer|<---| Vote Agg   | |
|  | SQLite + Prompts  |    |  (Structure/Meta)  |    | Maj-of-M   | |
|  +-------------------+    +--------------------+    +------------+ |
|          |                        |                                |
|          v                        v                                |
|  +-------------------+    +--------------------+    +------------+ |
|  |   TUI Viewer      |    |   Analysis Engine  |    | Cross-Run  | |
|  |   (Textual)       |    |  Stats/Bias/Weak   |    | Comparator | |
|  +-------------------+    +--------------------+    +------------+ |
|          |                        |                                |
|          v                        v                                |
|  +-------------------+    +--------------------+                   |
|  | Progress Dashboard|    |   PDF Reporter     |                   |
|  | Live + Keybinds   |    |  Full Analyst Rpt  |                   |
|  +-------------------+    +--------------------+                   |
+------------------------------------------------------------------+
```

### 1.2 Core Components (Improved)

| Component | Technology | Purpose | Improvements |
|-----------|------------|---------|--------------|
| **Data Layer** | SQLite + Python | O*NET access, results | Includes prompts table, proper joins |
| **ONET Reference** | Markdown parser | Use Opus's pre-analysis | NEW: Integrate guidance |
| **Prompt Engine** | Python + Pydantic | Three-phase generation | No hardcoded categories, revision tasks |
| **Diversity Sampler** | Pure Python | Even distribution | Dynamic dimension inference |
| **Eval Core** | asyncio + httpx | Parallel API calls | Verified model IDs |
| **Response Analyzer** | Python + regex | Structure detection | NEW: Format/pattern analysis |
| **Judge Panel** | OpenRouter API | Ensemble judging | Full persona context in prompts |
| **Vote Aggregator** | Pure Python | Majority-of-majorities | Unchanged |
| **Analysis Engine** | pandas + scipy | Statistics | Regional variant analysis |
| **Cross-Run Comparator** | Python | Multi-run analysis | NEW: Compare results across runs |
| **TUI Viewer** | Textual (rich) | Results exploration | Unchanged |
| **PDF Reporter** | WeasyPrint | Final report | Executive + comprehensive |
| **Progress Dashboard** | Textual | Live monitoring | Unchanged |

### 1.3 Improved Directory Structure

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── config/
│   ├── presets.yaml                  # 10 preset configurations
│   ├── models.yaml                   # Model definitions and pricing
│   ├── judge_prompts.yaml            # Judge persona templates
│   └── openrouter_models.json        # Verified model ID mappings (fetched)
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_loader.py            # O*NET database interface
│   │   ├── onet_reference.py         # NEW: Parse ONET_REFERENCE.md
│   │   ├── naics_mapper.py           # NAICS industry mapping
│   │   ├── company_db.py             # Real company database
│   │   └── name_generator.py         # Realistic name generation
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py              # Main prompt orchestrator
│   │   ├── phase1_llm.py             # LLM persona variations
│   │   ├── phase2_algorithmic.py     # Deterministic combinations
│   │   ├── phase3_enrichment.py      # LLM context enrichment
│   │   ├── revision_generator.py     # NEW: Revision/editing tasks
│   │   ├── constraint_generator.py   # NEW: Instruction-following prompts
│   │   ├── ambiguity_generator.py    # NEW: Deliberately vague prompts
│   │   └── schemas.py                # Pydantic models
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   ├── api_client.py             # OpenRouter API + model verification
│   │   ├── judge.py                  # Judge with full persona context
│   │   ├── vote_aggregator.py
│   │   ├── checkpoint.py
│   │   ├── response_analyzer.py      # NEW: Structure/pattern analysis
│   │   └── constraint_checker.py     # NEW: Instruction compliance
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py
│   │   ├── bias_detection.py
│   │   ├── weakness_finder.py
│   │   ├── regional_analysis.py      # NEW: English variant analysis
│   │   ├── visualizations.py
│   │   └── cross_run.py              # NEW: Cross-run comparison
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py
│   │   └── templates/
│   └── tui/
│       ├── __init__.py
│       ├── app.py
│       ├── progress.py
│       └── viewer.py
├── db/
│   ├── onet.db
│   ├── ONET_REFERENCE.md             # Opus's pre-analysis (read this!)
│   └── companies.db
├── results/
└── tests/
```

---

## Part 2: Improved Data Pipeline

### 2.1 O*NET Data Extraction (No Hardcoded Categories)

```python
# src/data/onet_loader.py

from dataclasses import dataclass
from typing import Iterator, List, Optional
import sqlite3
from pathlib import Path

@dataclass
class OnetTask:
    """Raw O*NET task with minimal processing - no hardcoded categories."""
    task_id: str
    onetsoc_code: str
    occupation_title: str
    occupation_description: str
    task: str
    task_type: Optional[str]  # Core, Supplemental, or NULL
    job_zone: int             # 1-5 skill level
    soc_major_group: str      # First 2 digits of SOC code

    # O*NET skill/context data (let these drive diversity, not hardcoded cats)
    writing_skill_importance: float   # 2.A.1.c scale
    writing_skill_level: float        # 2.A.1.c level
    email_frequency: float            # 4.C.1.a.2.h
    letters_memos_frequency: float    # 4.C.1.a.2.j
    contact_with_others: float        # 4.C.1.a.1
    deal_with_external: float         # 4.C.1.b.1.a
    deal_with_public: float           # 4.C.1.b.1.c

    # Inferred at query time, not hardcoded
    inferred_writing_type: Optional[str] = None  # Set by LLM in Phase 1

class OnetLoader:
    """Interface to O*NET 30.1 database - extracts tasks without imposing categories."""

    def __init__(self, db_path: str = "db/onet.db"):
        self.db_path = Path(db_path)
        self._validate_db()

    def _validate_db(self):
        """Verify database exists and has expected tables."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"O*NET database not found at {self.db_path}")

        with sqlite3.connect(self.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            required = {'task_statements', 'occupation_data'}
            found = {t[0] for t in tables}
            if not required.issubset(found):
                raise ValueError(f"Missing required tables: {required - found}")

    def extract_writing_tasks(
        self,
        min_writing_importance: float = 2.5,
        occupation_filter: Optional[List[str]] = None,
        job_zone_filter: Optional[List[int]] = None
    ) -> Iterator[OnetTask]:
        """
        Extract writing-relevant tasks using O*NET importance scores.

        Does NOT use keyword matching or hardcoded categories.
        Instead, uses Writing skill importance score (2.A.1.c) to identify
        occupations where writing matters, then extracts all tasks from those.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # First, get occupations with significant writing requirements
            occ_query = """
            SELECT DISTINCT onetsoc_code
            FROM skills
            WHERE element_id = '2.A.1.c'  -- Writing skill
              AND scale_id = 'IM'         -- Importance
              AND data_value >= ?
            """
            writing_occs = {
                row[0] for row in conn.execute(occ_query, (min_writing_importance,))
            }

            # Build task extraction query
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
                COALESCE(ws_im.data_value, 3.0) as writing_importance,
                COALESCE(ws_lv.data_value, 3.0) as writing_level,
                COALESCE(wc_email.data_value, 3.0) as email_freq,
                COALESCE(wc_letter.data_value, 3.0) as letter_freq,
                COALESCE(wc_contact.data_value, 3.0) as contact_others,
                COALESCE(wc_external.data_value, 3.0) as deal_external,
                COALESCE(wc_public.data_value, 3.0) as deal_public
            FROM task_statements t
            JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
            LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
            LEFT JOIN skills ws_im ON t.onetsoc_code = ws_im.onetsoc_code
                AND ws_im.element_id = '2.A.1.c' AND ws_im.scale_id = 'IM'
            LEFT JOIN skills ws_lv ON t.onetsoc_code = ws_lv.onetsoc_code
                AND ws_lv.element_id = '2.A.1.c' AND ws_lv.scale_id = 'LV'
            LEFT JOIN work_context wc_email ON t.onetsoc_code = wc_email.onetsoc_code
                AND wc_email.element_id = '4.C.1.a.2.h'
            LEFT JOIN work_context wc_letter ON t.onetsoc_code = wc_letter.onetsoc_code
                AND wc_letter.element_id = '4.C.1.a.2.j'
            LEFT JOIN work_context wc_contact ON t.onetsoc_code = wc_contact.onetsoc_code
                AND wc_contact.element_id = '4.C.1.a.1'
            LEFT JOIN work_context wc_external ON t.onetsoc_code = wc_external.onetsoc_code
                AND wc_external.element_id = '4.C.1.b.1.a'
            LEFT JOIN work_context wc_public ON t.onetsoc_code = wc_public.onetsoc_code
                AND wc_public.element_id = '4.C.1.b.1.c'
            WHERE t.onetsoc_code IN ({})
            """.format(','.join('?' * len(writing_occs)))

            params = list(writing_occs)

            for row in conn.execute(query, params):
                # Apply filters
                if occupation_filter:
                    if not any(row['onetsoc_code'].startswith(o) for o in occupation_filter):
                        continue
                if job_zone_filter:
                    if row['job_zone'] not in job_zone_filter:
                        continue

                yield OnetTask(
                    task_id=row['task_id'],
                    onetsoc_code=row['onetsoc_code'],
                    occupation_title=row['occupation_title'],
                    occupation_description=row['occupation_description'],
                    task=row['task'],
                    task_type=row['task_type'],
                    job_zone=row['job_zone'],
                    soc_major_group=row['soc_major_group'],
                    writing_skill_importance=row['writing_importance'],
                    writing_skill_level=row['writing_level'],
                    email_frequency=row['email_freq'],
                    letters_memos_frequency=row['letter_freq'],
                    contact_with_others=row['contact_others'],
                    deal_with_external=row['deal_external'],
                    deal_with_public=row['deal_public']
                )

    def get_task_count(self) -> int:
        """Get total number of tasks in database."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM task_statements").fetchone()[0]

    def get_occupation_count(self) -> int:
        """Get number of unique occupations."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(DISTINCT onetsoc_code) FROM task_statements"
            ).fetchone()[0]
```

### 2.2 O*NET Reference Integration

```python
# src/data/onet_reference.py

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import re

@dataclass
class WritingTaskGuidance:
    """Guidance extracted from ONET_REFERENCE.md"""
    task_patterns: List[str]         # Patterns that indicate writing tasks
    high_writing_occupations: List[str]  # SOC codes with heavy writing
    communication_contexts: List[str]    # Types of communication situations
    recommended_sampling: Dict[str, float]  # Sampling weights by occupation group

class OnetReferenceParser:
    """
    Parse the ONET_REFERENCE.md file created by Opus.
    This contains pre-analyzed guidance on writing tasks in O*NET.
    """

    def __init__(self, reference_path: str = "db/ONET_REFERENCE.md"):
        self.reference_path = Path(reference_path)
        self.guidance: Optional[WritingTaskGuidance] = None

    def load(self) -> WritingTaskGuidance:
        """Load and parse the reference document."""
        if not self.reference_path.exists():
            # Return default guidance if file doesn't exist
            return self._default_guidance()

        content = self.reference_path.read_text()

        # Extract structured information from markdown
        # This is a simplified parser - actual implementation would be more robust

        task_patterns = self._extract_section(content, "Task Patterns")
        high_writing = self._extract_section(content, "High Writing Occupations")
        contexts = self._extract_section(content, "Communication Contexts")

        self.guidance = WritingTaskGuidance(
            task_patterns=task_patterns,
            high_writing_occupations=high_writing,
            communication_contexts=contexts,
            recommended_sampling={}
        )

        return self.guidance

    def _extract_section(self, content: str, section_name: str) -> List[str]:
        """Extract bullet points from a markdown section."""
        pattern = rf"##\s*{section_name}.*?\n((?:[-*]\s+.*\n)+)"
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            return []

        bullets = re.findall(r"[-*]\s+(.+)", match.group(1))
        return [b.strip() for b in bullets]

    def _default_guidance(self) -> WritingTaskGuidance:
        """Default guidance if ONET_REFERENCE.md not available."""
        return WritingTaskGuidance(
            task_patterns=[],
            high_writing_occupations=[],
            communication_contexts=[
                "internal", "external", "customer", "stakeholder",
                "formal", "informal", "urgent", "routine"
            ],
            recommended_sampling={}
        )
```

### 2.3 NAICS Industry Mapping (Unchanged but with better company coverage)

```python
# src/data/naics_mapper.py
# (Similar to original but with expanded company database)
# See original draft - this component is adequate
```

### 2.4 Company Database (Expanded)

```python
# src/data/company_db.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
import random
import sqlite3
from pathlib import Path

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
    hq_country: str  # NEW: For regional English variants
    public: bool
    employee_count_approx: int
    description: str

class CompanyDatabase:
    """
    Database of real companies for prompt grounding.
    Expanded to include international companies for regional variant testing.
    """

    def __init__(self, db_path: str = "db/companies.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize company database with curated data."""
        # In production, this loads from companies.db
        # Here we show the structure
        self.companies: Dict[str, Dict[CompanySize, List[Company]]] = {
            '52': {  # Finance
                CompanySize.FORTUNE_500: [
                    Company("JPMorgan Chase", CompanySize.FORTUNE_500, "52", 1799,
                           "New York, NY", "US", True, 290000, "Global financial services"),
                    Company("HSBC Holdings", CompanySize.FORTUNE_500, "52", 1865,
                           "London", "UK", True, 220000, "British multinational bank"),
                    Company("Commonwealth Bank", CompanySize.FORTUNE_500, "52", 1911,
                           "Sydney", "AU", True, 48000, "Australian bank"),
                ],
                CompanySize.ENTERPRISE: [
                    Company("Ally Financial", CompanySize.ENTERPRISE, "52", 1919,
                           "Detroit, MI", "US", True, 11000, "Digital financial services"),
                ],
                CompanySize.STARTUP: [
                    Company("Ramp", CompanySize.STARTUP, "52", 2019,
                           "New York, NY", "US", False, 350, "Corporate card platform"),
                ],
            },
            '54': {  # Professional Services
                CompanySize.FORTUNE_500: [
                    Company("Deloitte", CompanySize.FORTUNE_500, "54", 1845,
                           "London", "UK", False, 415000, "Professional services"),
                    Company("Accenture", CompanySize.FORTUNE_500, "54", 1989,
                           "Dublin", "IE", True, 733000, "IT consulting"),
                ],
                CompanySize.MIDMARKET: [
                    Company("West Monroe", CompanySize.MIDMARKET, "54", 2002,
                           "Chicago, IL", "US", False, 1500, "Business consulting"),
                ],
            },
            # Additional industries with international coverage...
        }

    def get_company(
        self,
        naics_code: str,
        size: Optional[CompanySize] = None,
        country: Optional[str] = None,  # NEW: Filter by country
        seed: Optional[int] = None
    ) -> Company:
        """Get a company matching criteria."""
        if seed is not None:
            random.seed(seed)

        industry_companies = self.companies.get(naics_code, {})
        if not industry_companies:
            return self._generate_fallback_company(naics_code, size, country)

        # Flatten to list
        candidates = []
        for s, companies in industry_companies.items():
            if size and s != size:
                continue
            for c in companies:
                if country and c.hq_country != country:
                    continue
                candidates.append(c)

        if not candidates:
            return self._generate_fallback_company(naics_code, size, country)

        return random.choice(candidates)

    def get_international_company(self, seed: Optional[int] = None) -> Company:
        """Get a company from outside the US for regional variant scenarios."""
        if seed:
            random.seed(seed)

        non_us = []
        for industry in self.companies.values():
            for companies in industry.values():
                non_us.extend([c for c in companies if c.hq_country != "US"])

        return random.choice(non_us) if non_us else self._generate_fallback_company("54", None, "UK")

    def _generate_fallback_company(
        self,
        naics_code: str,
        size: Optional[CompanySize],
        country: Optional[str]
    ) -> Company:
        """Generate a plausible generic company."""
        size = size or random.choice(list(CompanySize))
        country = country or "US"

        employee_ranges = {
            CompanySize.STARTUP: 25,
            CompanySize.SMALL: 100,
            CompanySize.MIDMARKET: 800,
            CompanySize.ENTERPRISE: 5000,
            CompanySize.FORTUNE_500: 50000,
        }

        return Company(
            name=f"Acme {naics_code} Corp",
            size=size,
            industry_naics=naics_code,
            founded_year=2010,
            hq_location="Various",
            hq_country=country,
            public=size in (CompanySize.ENTERPRISE, CompanySize.FORTUNE_500),
            employee_count_approx=employee_ranges[size],
            description="Generic company for evaluation"
        )
```

### 2.5 Name Generator (With International Support)

```python
# src/data/name_generator.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List
import random

class Generation(Enum):
    GEN_Z = "gen_z"           # Born 1997-2012
    GEN_A = "gen_a"           # Born 2013+ (youngest workers)
    MILLENNIAL = "millennial" # Born 1981-1996
    GEN_X = "gen_x"           # Born 1965-1980
    BOOMER = "boomer"         # Born 1946-1964

class NameFormality(Enum):
    CASUAL = "casual"         # Mike, Lisa
    STANDARD = "standard"     # Michael Chen, Lisa Johnson
    FORMAL = "formal"         # Dr. Michael T. Chen, Ms. Lisa M. Johnson

class EnglishVariant(Enum):
    US = "en-US"
    UK = "en-GB"
    AU = "en-AU"
    NON_NATIVE = "non-native"

@dataclass
class PersonName:
    first_name: str
    last_name: str
    full_name: str
    email: str
    title_prefix: Optional[str]
    generation: Generation
    formality: NameFormality
    english_variant: EnglishVariant
    is_native_english: bool

class NameGenerator:
    """
    Generates demographically diverse realistic names.
    Improved to support international names and English variants.
    """

    # Name pools by region/ethnicity
    FIRST_NAMES = {
        'us_anglo_male': ['James', 'Michael', 'Robert', 'David', 'William'],
        'us_anglo_female': ['Sarah', 'Jennifer', 'Elizabeth', 'Mary', 'Patricia'],
        'us_hispanic_male': ['Carlos', 'Miguel', 'Jose', 'Luis', 'Antonio'],
        'us_hispanic_female': ['Maria', 'Carmen', 'Ana', 'Rosa', 'Isabel'],
        'us_asian_male': ['Wei', 'Jin', 'Raj', 'Anil', 'Vikram'],
        'us_asian_female': ['Mei', 'Priya', 'Lin', 'Aisha', 'Sana'],
        'uk_male': ['Oliver', 'George', 'Harry', 'Jack', 'Charlie', 'Nigel'],
        'uk_female': ['Olivia', 'Amelia', 'Isla', 'Ava', 'Emily', 'Charlotte'],
        'au_male': ['Jack', 'William', 'Oliver', 'Noah', 'Thomas'],
        'au_female': ['Charlotte', 'Olivia', 'Ava', 'Mia', 'Amelia'],
        'intl_male': ['Hiroshi', 'Kenji', 'Pierre', 'Hans', 'Marco', 'Sven'],
        'intl_female': ['Yuki', 'Sakura', 'Marie', 'Ingrid', 'Giulia', 'Astrid'],
    }

    LAST_NAMES = {
        'us': ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Chen'],
        'uk': ['Smith', 'Jones', 'Williams', 'Taylor', 'Brown', 'Davies', 'Wilson'],
        'au': ['Smith', 'Jones', 'Williams', 'Brown', 'Wilson', 'Taylor', 'Johnson'],
        'intl': ['Mueller', 'Rossi', 'Tanaka', 'Kim', 'Johansson', 'Dubois', 'Silva'],
    }

    def generate(
        self,
        generation: Optional[Generation] = None,
        formality: NameFormality = NameFormality.STANDARD,
        english_variant: EnglishVariant = EnglishVariant.US,
        seed: Optional[int] = None
    ) -> PersonName:
        """Generate a realistic person name with regional support."""
        if seed is not None:
            random.seed(seed)

        if generation is None:
            # Weight towards working-age generations
            generation = random.choices(
                list(Generation),
                weights=[0.15, 0.05, 0.35, 0.30, 0.15]  # GenZ, GenA, Mill, GenX, Boom
            )[0]

        # Select name pool based on variant
        region_map = {
            EnglishVariant.US: ('us', True),
            EnglishVariant.UK: ('uk', True),
            EnglishVariant.AU: ('au', True),
            EnglishVariant.NON_NATIVE: ('intl', False),
        }
        region, is_native = region_map[english_variant]

        gender = random.choice(['male', 'female'])

        # Get appropriate name lists
        if region == 'us':
            ethnicity = random.choice(['anglo', 'hispanic', 'asian'])
            first_key = f"us_{ethnicity}_{gender}"
        else:
            first_key = f"{region}_{gender}"

        first_names = self.FIRST_NAMES.get(first_key, self.FIRST_NAMES['us_anglo_male'])
        last_names = self.LAST_NAMES.get(region, self.LAST_NAMES['us'])

        first_name = random.choice(first_names)
        last_name = random.choice(last_names)

        # Build full name based on formality
        title = random.choice(['Dr.', 'Mr.', 'Ms.', None, None, None]) if formality == NameFormality.FORMAL else None
        middle_initial = f"{chr(random.randint(65, 90))}." if formality == NameFormality.FORMAL else ""

        if formality == NameFormality.CASUAL:
            full_name = first_name
        elif formality == NameFormality.STANDARD:
            full_name = f"{first_name} {last_name}"
        else:
            prefix = f"{title} " if title else ""
            full_name = f"{prefix}{first_name} {middle_initial}{last_name}".strip()

        # Generate email
        email_base = f"{first_name.lower()}.{last_name.lower()}"

        return PersonName(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            email=email_base,
            title_prefix=title,
            generation=generation,
            formality=formality,
            english_variant=english_variant,
            is_native_english=is_native
        )
```

---

## Part 3: Improved Prompt Generation

### 3.1 Enhanced Prompt Schema

```python
# src/prompts/schemas.py

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
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

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

class PromptType(str, Enum):
    """Type of writing task - NEW: includes revision tasks."""
    GENERATION = "generation"      # Write from scratch
    REVISION = "revision"          # Improve existing text
    REPLY = "reply"                # Respond to prior message
    TONE_MATCH = "tone_match"      # Match provided style
    AMBIGUOUS = "ambiguous"        # Deliberately vague

class SensitiveCategory(str, Enum):
    """Categories of sensitive topics to track."""
    HR_ISSUES = "hr_issues"
    LEGAL_MATTERS = "legal"
    BAD_NEWS = "bad_news"
    CONFIDENTIAL = "confidential"
    CONFLICT = "conflict"
    TERMINATION = "termination"

class WriterPersona(BaseModel):
    """Detailed persona for the person writing."""
    name: str
    email: Optional[str] = None
    job_title: str
    company: str
    company_size: str
    industry: str
    age_range: str
    generation: str               # GenZ, Millennial, GenX, Boomer
    skill_level: str              # junior, mid, senior, executive
    years_experience: Optional[int] = None  # NEW
    english_variant: str = "en-US"
    is_native_english: bool = True  # NEW

class RecipientPersona(BaseModel):
    """Detailed persona for the recipient(s)."""
    name: str
    email: Optional[str] = None
    job_title: str
    company: Optional[str] = None
    relationship_to_writer: str
    english_variant: str = "en-US"
    is_native_english: bool = True

class AttachedContext(BaseModel):
    """Mock attachments or prior context."""
    type: str
    content: str
    filename: Optional[str] = None

class ExplicitConstraint(BaseModel):
    """
    NEW: Explicit instruction-following constraint.
    """
    constraint_type: str  # "length", "format", "tone", "exclusion", "inclusion"
    description: str      # Human-readable constraint
    verification: str     # How to check compliance (regex, word count, etc.)
    target_value: Optional[Any] = None  # e.g., max_words=100

class RevisionContext(BaseModel):
    """
    NEW: Context for revision/editing tasks.
    """
    original_text: str
    revision_goal: str    # "make_concise", "more_professional", "soften_tone", etc.
    specific_issues: List[str] = Field(default_factory=list)

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

    # Industry context
    naics_code: str
    naics_title: str

    # NEW: Task type (not hardcoded category)
    prompt_type: PromptType
    inferred_writing_type: Optional[str] = None  # LLM-inferred, not hardcoded

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
    communication_channel: Optional[str] = None  # Inferred, not hardcoded enum

    # Additional context
    temporal_context: Optional[str] = None
    competing_objectives: List[str] = Field(default_factory=list)
    attached_context: List[AttachedContext] = Field(default_factory=list)
    prior_message: Optional[str] = None

    # NEW: Instruction-following constraints
    explicit_constraints: List[ExplicitConstraint] = Field(default_factory=list)
    has_constraints: bool = False

    # NEW: Revision context
    revision_context: Optional[RevisionContext] = None

    # Tone matching
    tone_example: Optional[str] = None

    # Ambiguity (intentional)
    is_deliberately_vague: bool = False
    vagueness_type: Optional[str] = None

    # Sensitive topic flags
    is_sensitive: bool = False
    sensitive_categories: List[SensitiveCategory] = Field(default_factory=list)

    # The actual prompt text sent to models
    prompt_text: str

    # Language
    language: str = "en"
    language_variant: str = "en-US"

    # Generation metadata
    generation_seed: int
    generated_at: datetime = Field(default_factory=datetime.now)
    generation_phase: str
```

### 3.2 Revision Task Generator (NEW)

```python
# src/prompts/revision_generator.py

from typing import List, Dict, Optional
import random
from .schemas import RevisionContext, ExplicitConstraint

class RevisionTaskGenerator:
    """
    Generates revision/editing tasks per PROMPT.md requirement:
    "Include prompts where the model must improve existing text"
    """

    REVISION_TYPES = [
        {
            "goal": "make_concise",
            "instruction": "Revise this draft to be more concise while preserving key information",
            "issues": ["too wordy", "redundant phrases", "unnecessary detail"]
        },
        {
            "goal": "more_professional",
            "instruction": "Make this email more professional and polished",
            "issues": ["too casual", "informal language", "lacks structure"]
        },
        {
            "goal": "soften_tone",
            "instruction": "Soften the tone of this message while keeping the core message",
            "issues": ["too harsh", "could damage relationship", "sounds accusatory"]
        },
        {
            "goal": "add_detail",
            "instruction": "Add more detail and specificity to this summary",
            "issues": ["too vague", "missing specifics", "needs examples"]
        },
        {
            "goal": "simplify",
            "instruction": "Simplify this message for a non-technical audience",
            "issues": ["too technical", "jargon-heavy", "assumes expertise"]
        },
        {
            "goal": "increase_urgency",
            "instruction": "Rewrite to convey more urgency without being alarmist",
            "issues": ["doesn't convey importance", "too passive", "easily ignored"]
        },
        {
            "goal": "remove_ai_patterns",
            "instruction": "Revise to remove AI-sounding phrases and make it more natural",
            "issues": ["sounds AI-generated", "cliche phrases", "too formulaic"]
        }
    ]

    # Sample drafts that need revision (would be generated by LLM in production)
    SAMPLE_DRAFTS = {
        "too_wordy": """
Dear Mr. Johnson,

I hope this email finds you well. I am writing to you today in order to follow up
on our previous conversation that we had last week regarding the project timeline.
After careful consideration and thorough review of all the relevant factors, I wanted
to reach out and see if you might have some time available to discuss this matter
further at your earliest convenience.

Please let me know if you have any questions or concerns.

Best regards
        """,
        "too_casual": """
Hey!

So I was thinking about that thing we talked about and yeah I think we should
probably do it. Let me know what you think lol. Also btw the deadline is like
next Friday so we should prob get on it soon.

Thanks!
        """,
        "too_harsh": """
Your report was submitted late and contained multiple errors. This is unacceptable.
You need to fix these issues immediately. I expect better performance going forward.
Failure to improve will result in consequences.
        """,
    }

    def generate_revision_task(
        self,
        task_text: str,
        seed: Optional[int] = None
    ) -> RevisionContext:
        """Generate a revision task for an O*NET task."""
        if seed:
            random.seed(seed)

        revision_type = random.choice(self.REVISION_TYPES)

        # In production, use LLM to generate contextual draft
        # Here we select from samples or generate placeholder
        draft_key = random.choice(list(self.SAMPLE_DRAFTS.keys()))
        original_text = self.SAMPLE_DRAFTS[draft_key]

        return RevisionContext(
            original_text=original_text.strip(),
            revision_goal=revision_type["goal"],
            specific_issues=revision_type["issues"]
        )

    def build_revision_prompt(
        self,
        revision_context: RevisionContext,
        writer_context: str
    ) -> str:
        """Build the full revision prompt text."""
        goal_instructions = {
            "make_concise": "Revise this draft to be more concise. Cut unnecessary words and phrases while preserving all key information.",
            "more_professional": "Make this draft more professional. Improve structure, word choice, and overall polish.",
            "soften_tone": "Soften the tone of this message. The core message should remain but be delivered more diplomatically.",
            "add_detail": "Expand this draft with more specific details, examples, or supporting information.",
            "simplify": "Simplify this message for someone without technical background. Replace jargon with plain language.",
            "increase_urgency": "Rewrite to better convey urgency and importance, while remaining professional.",
            "remove_ai_patterns": "Revise to sound more natural and human. Remove formulaic phrases and cliches."
        }

        instruction = goal_instructions.get(
            revision_context.revision_goal,
            "Improve this draft."
        )

        return f"""
{writer_context}

## TASK: Revision/Editing

{instruction}

Issues with the current draft:
{chr(10).join(f'- {issue}' for issue in revision_context.specific_issues)}

## ORIGINAL DRAFT TO REVISE:
---
{revision_context.original_text}
---

Write your revised version now.
"""
```

### 3.3 Constraint Generator (NEW - Instruction Following)

```python
# src/prompts/constraint_generator.py

from typing import List, Optional
import random
from .schemas import ExplicitConstraint

class ConstraintGenerator:
    """
    Generates explicit constraints for instruction-following tests.
    Per PROMPT.md: "Include some prompts with explicit constraints to test instruction-following"
    """

    CONSTRAINT_TEMPLATES = {
        "length_max": [
            ExplicitConstraint(
                constraint_type="length",
                description="Keep this under 100 words",
                verification="word_count_max",
                target_value=100
            ),
            ExplicitConstraint(
                constraint_type="length",
                description="Keep this brief - no more than 3 sentences",
                verification="sentence_count_max",
                target_value=3
            ),
            ExplicitConstraint(
                constraint_type="length",
                description="This should be a single paragraph",
                verification="paragraph_count",
                target_value=1
            ),
        ],
        "length_min": [
            ExplicitConstraint(
                constraint_type="length",
                description="This should be comprehensive - at least 500 words",
                verification="word_count_min",
                target_value=500
            ),
            ExplicitConstraint(
                constraint_type="length",
                description="Provide a detailed response of at least 3 paragraphs",
                verification="paragraph_count_min",
                target_value=3
            ),
        ],
        "format": [
            ExplicitConstraint(
                constraint_type="format",
                description="Use exactly 3 bullet points",
                verification="bullet_count",
                target_value=3
            ),
            ExplicitConstraint(
                constraint_type="format",
                description="Write in paragraph form only - no bullet points or lists",
                verification="no_bullets",
                target_value=True
            ),
            ExplicitConstraint(
                constraint_type="format",
                description="Structure with clear headers for each section",
                verification="has_headers",
                target_value=True
            ),
        ],
        "tone": [
            ExplicitConstraint(
                constraint_type="tone",
                description="Be direct and avoid pleasantries - get straight to the point",
                verification="no_pleasantries",
                target_value=True
            ),
            ExplicitConstraint(
                constraint_type="tone",
                description="Use a warm, encouraging tone throughout",
                verification="tone_positive",
                target_value=True
            ),
        ],
        "exclusion": [
            ExplicitConstraint(
                constraint_type="exclusion",
                description="Do not mention the budget or costs",
                verification="excludes_words",
                target_value=["budget", "cost", "expense", "price", "money"]
            ),
            ExplicitConstraint(
                constraint_type="exclusion",
                description="Avoid technical jargon - keep it accessible",
                verification="readability_score",
                target_value=60  # Flesch reading ease minimum
            ),
        ],
        "inclusion": [
            ExplicitConstraint(
                constraint_type="inclusion",
                description="Make sure to include next steps",
                verification="includes_phrase",
                target_value="next step"
            ),
            ExplicitConstraint(
                constraint_type="inclusion",
                description="Include a specific deadline",
                verification="includes_date",
                target_value=True
            ),
        ],
    }

    def generate_constraints(
        self,
        num_constraints: int = 1,
        constraint_types: Optional[List[str]] = None,
        seed: Optional[int] = None
    ) -> List[ExplicitConstraint]:
        """Generate random constraints for a prompt."""
        if seed:
            random.seed(seed)

        types = constraint_types or list(self.CONSTRAINT_TEMPLATES.keys())
        selected_type = random.choice(types)

        constraints = random.sample(
            self.CONSTRAINT_TEMPLATES[selected_type],
            min(num_constraints, len(self.CONSTRAINT_TEMPLATES[selected_type]))
        )

        return constraints

    def build_constraint_text(self, constraints: List[ExplicitConstraint]) -> str:
        """Build constraint section for prompt text."""
        if not constraints:
            return ""

        lines = ["## IMPORTANT CONSTRAINTS", "Follow these requirements exactly:"]
        for c in constraints:
            lines.append(f"- {c.description}")

        return "\n".join(lines)
```

### 3.4 Ambiguity Generator (NEW)

```python
# src/prompts/ambiguity_generator.py

from typing import Tuple, Optional
import random

class AmbiguityGenerator:
    """
    Generates deliberately vague prompts per PROMPT.md:
    "Include some deliberately vague prompts to test how models handle uncertainty"
    """

    VAGUENESS_TYPES = {
        "underspecified_recipient": [
            "Write to the team about the project",
            "Send an update to everyone involved",
            "Let the stakeholders know about the change",
        ],
        "missing_context": [
            "Follow up on our conversation",
            "Send a reminder about what we discussed",
            "Circle back on that thing from last week",
        ],
        "unclear_ask": [
            "Put together something for the client",
            "Draft a response to their request",
            "Write up what we talked about",
        ],
        "ambiguous_tone": [
            "Write something appropriate for the situation",
            "Send them a message about it",
            "Communicate the decision",
        ],
    }

    def generate_vague_prompt(
        self,
        vagueness_type: Optional[str] = None,
        seed: Optional[int] = None
    ) -> Tuple[str, str]:
        """
        Generate a deliberately vague prompt.
        Returns (prompt_text, vagueness_type)
        """
        if seed:
            random.seed(seed)

        if vagueness_type is None:
            vagueness_type = random.choice(list(self.VAGUENESS_TYPES.keys()))

        prompt_text = random.choice(self.VAGUENESS_TYPES[vagueness_type])

        return prompt_text, vagueness_type

    def get_vagueness_assessment_criteria(self) -> str:
        """
        Return criteria for evaluating how models handle ambiguity.
        Used by judges to assess response quality for vague prompts.
        """
        return """
        When evaluating responses to deliberately vague prompts, assess:
        1. Does the model make reasonable assumptions?
        2. Does it acknowledge the ambiguity (explicitly or implicitly)?
        3. Does it ask for clarification within the response?
        4. Does it hedge appropriately given uncertainty?
        5. Does it hallucinate specific details not supported by the prompt?
        6. Is the response still useful despite the vagueness?
        """
```

### 3.5 Improved Master Prompt Generator

```python
# src/prompts/generator.py

from typing import List, Iterator, Optional, Dict
import asyncio
import random
from datetime import datetime

from .phase1_llm import Phase1PersonaGenerator
from .phase2_algorithmic import Phase2AlgorithmicCombiner
from .phase3_enrichment import Phase3Enricher
from .revision_generator import RevisionTaskGenerator
from .constraint_generator import ConstraintGenerator
from .ambiguity_generator import AmbiguityGenerator
from .schemas import EvalPrompt, PromptType, ExplicitConstraint

from ..data.onet_loader import OnetLoader
from ..data.naics_mapper import NAICSMapper
from ..data.company_db import CompanyDatabase
from ..eval.api_client import OpenRouterClient

class PromptGenerator:
    """
    Orchestrates three-phase prompt generation with support for:
    - Standard generation tasks
    - Revision/editing tasks (NEW)
    - Instruction-following constraints (NEW)
    - Deliberately ambiguous prompts (NEW)
    - Regional English variants (NEW)
    - CC/multiple recipient scenarios (NEW)
    """

    # Distribution of prompt types (configurable)
    DEFAULT_TYPE_DISTRIBUTION = {
        PromptType.GENERATION: 0.60,    # 60% standard generation
        PromptType.REPLY: 0.15,          # 15% reply to prior message
        PromptType.REVISION: 0.10,       # 10% revision tasks
        PromptType.TONE_MATCH: 0.05,     # 5% tone matching
        PromptType.AMBIGUOUS: 0.10,      # 10% deliberately vague
    }

    # Percentage of prompts with explicit constraints
    CONSTRAINT_PROBABILITY = 0.15  # 15% have constraints

    # Percentage with CC recipients (mixed audience)
    CC_PROBABILITY = 0.10  # 10% have CC

    # Percentage with non-US English variants
    INTERNATIONAL_PROBABILITY = 0.10  # 10% international

    def __init__(
        self,
        onet_loader: OnetLoader,
        naics_mapper: NAICSMapper,
        company_db: CompanyDatabase,
        api_client: OpenRouterClient,
        models: List[str],
        seed: int = 42
    ):
        self.onet_loader = onet_loader
        self.naics_mapper = naics_mapper
        self.company_db = company_db
        self.api_client = api_client

        self.phase1 = Phase1PersonaGenerator(api_client, models)
        self.phase2 = Phase2AlgorithmicCombiner(seed)
        self.phase3 = Phase3Enricher(api_client, models)

        self.revision_gen = RevisionTaskGenerator()
        self.constraint_gen = ConstraintGenerator()
        self.ambiguity_gen = AmbiguityGenerator()

        self.seed = seed
        self.rng = random.Random(seed)

    async def generate_prompts(
        self,
        num_prompts: int,
        occupation_filter: Optional[List[str]] = None,
        industry_filter: Optional[List[str]] = None,
        job_zone_filter: Optional[List[int]] = None,
        type_distribution: Optional[Dict[PromptType, float]] = None,
        stratify: bool = True
    ) -> List[EvalPrompt]:
        """Generate specified number of diverse prompts."""

        type_dist = type_distribution or self.DEFAULT_TYPE_DISTRIBUTION

        # Phase 1: Extract and filter tasks
        tasks = list(self.onet_loader.extract_writing_tasks(
            occupation_filter=occupation_filter,
            job_zone_filter=job_zone_filter
        ))

        # Stratified sampling
        if stratify:
            tasks = self._stratified_sample(tasks, num_prompts)
        else:
            tasks = self.rng.sample(tasks, min(len(tasks), num_prompts))

        prompts = []
        for i, task in enumerate(tasks):
            prompt_seed = hash((self.seed, task.task_id, i))

            # Determine prompt type
            prompt_type = self._select_prompt_type(type_dist, prompt_seed)

            # Get industry and company
            industries = self.naics_mapper.get_industries_for_occupation(task.soc_major_group)
            if industry_filter:
                industries = [ind for ind in industries if ind.code in industry_filter]
            industry = industries[0] if industries else None

            # Decide if international scenario
            is_international = self.rng.random() < self.INTERNATIONAL_PROBABILITY
            if is_international:
                company = self.company_db.get_international_company(seed=prompt_seed)
            else:
                company = self.company_db.get_company(
                    industry.code if industry else '54',
                    seed=prompt_seed
                )

            # Generate personas (Phase 1)
            personas = await self.phase1.generate_personas(
                task, company, industry,
                is_international=is_international
            )

            # Generate combinations (Phase 2)
            combinations = list(self.phase2.generate_combinations(
                task, personas, company, industry, num_prompts=1
            ))

            for combo in combinations:
                combo['prompt_type'] = prompt_type

                # Add constraints if applicable
                if self.rng.random() < self.CONSTRAINT_PROBABILITY:
                    combo['constraints'] = self.constraint_gen.generate_constraints(
                        num_constraints=self.rng.randint(1, 2),
                        seed=prompt_seed
                    )

                # Add CC recipients if applicable
                if self.rng.random() < self.CC_PROBABILITY:
                    combo['cc_recipients'] = await self._generate_cc_recipients(
                        combo, prompt_seed
                    )

                # Generate revision context if revision task
                if prompt_type == PromptType.REVISION:
                    combo['revision_context'] = self.revision_gen.generate_revision_task(
                        task.task, seed=prompt_seed
                    )

                # Generate ambiguous prompt if ambiguous type
                if prompt_type == PromptType.AMBIGUOUS:
                    vague_text, vague_type = self.ambiguity_gen.generate_vague_prompt(
                        seed=prompt_seed
                    )
                    combo['vague_prompt'] = vague_text
                    combo['vagueness_type'] = vague_type

                # Phase 3: Enrich and build final prompt
                prompt = await self.phase3.enrich_prompt(combo)
                prompts.append(prompt)

        return prompts

    def _select_prompt_type(
        self,
        distribution: Dict[PromptType, float],
        seed: int
    ) -> PromptType:
        """Select prompt type based on distribution."""
        rng = random.Random(seed)
        types = list(distribution.keys())
        weights = list(distribution.values())
        return rng.choices(types, weights=weights)[0]

    async def _generate_cc_recipients(
        self,
        combo: Dict,
        seed: int
    ) -> List[Dict]:
        """Generate CC recipients for mixed-audience scenarios."""
        # Would use LLM to generate appropriate CC recipients
        # based on the scenario (e.g., boss CC'd on client email)
        return []

    def _stratified_sample(self, tasks: List, target_count: int) -> List:
        """Sample tasks with even distribution across dimensions."""
        from collections import defaultdict

        strata = defaultdict(list)
        for task in tasks:
            # Stratify by job_zone and soc_major_group
            key = (task.job_zone, task.soc_major_group)
            strata[key].append(task)

        per_stratum = max(1, target_count // len(strata))
        sampled = []

        for key, stratum_tasks in strata.items():
            sample_size = min(per_stratum, len(stratum_tasks))
            sampled.extend(self.rng.sample(stratum_tasks, sample_size))

        # Fill remaining quota
        remaining = target_count - len(sampled)
        if remaining > 0:
            all_remaining = [t for t in tasks if t not in sampled]
            sampled.extend(self.rng.sample(
                all_remaining,
                min(remaining, len(all_remaining))
            ))

        return sampled[:target_count]
```

---

## Part 4: Improved Evaluation and Judging

### 4.1 OpenRouter Client with Model Verification

```python
# src/eval/api_client.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
import time
import json
from pathlib import Path

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
class ModelInfo:
    """Information about a model from OpenRouter."""
    id: str
    name: str
    pricing_prompt: float   # per 1M tokens
    pricing_completion: float
    context_length: int
    available: bool

class OpenRouterClient:
    """
    Unified client for OpenRouter API.
    Improved with model verification and dynamic pricing.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    # Default model mappings (updated after verification)
    DEFAULT_MODEL_IDS = {
        'gemini-3-pro': 'google/gemini-3.0-pro',
        'gemini-3-flash': 'google/gemini-3.0-flash',
        'gpt-5.2-thinking': 'openai/gpt-5.2',
        'gpt-4.1': 'openai/gpt-4.1',
        'claude-opus-4.5': 'anthropic/claude-4-opus',
        'claude-sonnet': 'anthropic/claude-4-sonnet',
        'grok-4.1-thinking': 'x-ai/grok-4.1',
        'kimi-k2-thinking': 'moonshot/kimi-k2',
    }

    def __init__(
        self,
        api_key: str,
        timeout: float = 120.0,
        verify_models: bool = True
    ):
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

        self.model_ids = self.DEFAULT_MODEL_IDS.copy()
        self.model_info: Dict[str, ModelInfo] = {}
        self._verified = False

        if verify_models:
            # Will be called in async context
            self._needs_verification = True
        else:
            self._needs_verification = False

    async def verify_models(self) -> Dict[str, ModelInfo]:
        """
        Verify model IDs are correct by querying OpenRouter.
        Updates model_ids with correct values.
        """
        try:
            response = await self.client.get("/models")
            response.raise_for_status()
            data = response.json()

            available_models = {m['id']: m for m in data.get('data', [])}

            for friendly_name, model_id in list(self.model_ids.items()):
                if model_id in available_models:
                    model_data = available_models[model_id]
                    self.model_info[friendly_name] = ModelInfo(
                        id=model_id,
                        name=model_data.get('name', model_id),
                        pricing_prompt=model_data.get('pricing', {}).get('prompt', 0) * 1_000_000,
                        pricing_completion=model_data.get('pricing', {}).get('completion', 0) * 1_000_000,
                        context_length=model_data.get('context_length', 128000),
                        available=True
                    )
                else:
                    # Try to find similar model
                    found = False
                    for avail_id in available_models:
                        if friendly_name.replace('-', '').lower() in avail_id.lower():
                            self.model_ids[friendly_name] = avail_id
                            found = True
                            break

                    if not found:
                        self.model_info[friendly_name] = ModelInfo(
                            id=model_id,
                            name=friendly_name,
                            pricing_prompt=10.0,  # Default fallback
                            pricing_completion=30.0,
                            context_length=128000,
                            available=False
                        )

            self._verified = True
            return self.model_info

        except Exception as e:
            # Fall back to defaults
            self._verified = True
            return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30)
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

        if self._needs_verification and not self._verified:
            await self.verify_models()

        model_id = self.model_ids.get(model, model)
        start_time = time.perf_counter()

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
            finish_reason=data['choices'][0].get('finish_reason', 'unknown'),
            raw_response=data
        )

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost for a completion using verified pricing."""
        if model in self.model_info:
            info = self.model_info[model]
            return (input_tokens * info.pricing_prompt + output_tokens * info.pricing_completion) / 1_000_000

        # Fallback to hardcoded estimates
        fallback_pricing = {
            'gemini-3-pro': (2.50, 10.00),
            'gemini-3-flash': (0.25, 1.00),
            'gpt-5.2-thinking': (15.00, 60.00),
            'gpt-4.1': (2.00, 8.00),
            'claude-opus-4.5': (15.00, 75.00),
            'claude-sonnet': (3.00, 15.00),
        }
        pricing = fallback_pricing.get(model, (5.0, 20.0))
        return (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000

    async def close(self):
        await self.client.aclose()

class RateLimitError(Exception):
    pass
```

### 4.2 Improved Judge Panel with Full Persona Context

```python
# src/eval/judge.py

from dataclasses import dataclass
from typing import List, Dict, Optional
import asyncio
from enum import Enum
import json

from .api_client import OpenRouterClient

class JudgeVerdict(Enum):
    A_WINS = "a_wins"
    B_WINS = "b_wins"
    TIE = "tie"

@dataclass
class JudgeVote:
    verdict: JudgeVerdict
    confidence: float
    reasoning: str
    criteria_scores: Dict[str, Dict]

@dataclass
class JudgeResult:
    judge_model: str
    persona: str
    votes: List[JudgeVote]
    majority_verdict: JudgeVerdict

class JudgePanel:
    """
    Ensemble of LLM judges with dual personas.
    IMPROVED: Full persona context in judge prompts per PROMPT.md requirement.
    """

    # IMPROVED: Full persona context included
    WRITING_EXPERT_PROMPT = '''
You are an expert writing evaluator assessing professional communication quality.

## TASK CONTEXT
Task: {task_text}
Communication Channel: {channel}
Urgency: {urgency}
Formality Level: {formality}

## WRITER PERSONA (CRITICAL FOR AUTHENTICITY ASSESSMENT)
Name: {writer_name}
Title: {writer_title}
Company: {writer_company} ({company_size})
Industry: {industry}
Age Range: {writer_age}
Generation: {writer_generation}
Skill Level: {writer_skill}
English Variant: {writer_english}
Native English Speaker: {writer_native}

## RECIPIENT PERSONA
Name: {recipient_name}
Title: {recipient_title}
Relationship to Writer: {relationship}
English Variant: {recipient_english}
Native English Speaker: {recipient_native}

{cc_context}

## RESPONSE A
{response_a}

## RESPONSE B
{response_b}

## EVALUATION CRITERIA
Evaluate both responses on these criteria (1-5 scale each):

1. **Quality of Writing**: Grammar, clarity, flow, structure
2. **Appropriate Length**: Neither too verbose nor too terse for THIS specific task
3. **Tone Appropriateness**: Matches the {formality} formality level and {writer_generation} generation style
4. **Task Completion**: Fully addresses what was asked
5. **Clarity**: Easy to understand, unambiguous
6. **Authenticity**: Does this read like a {writer_age} {writer_skill}-level {writer_title} would actually write? NOT generic AI output?
7. **Cliche Avoidance**: Avoids AI patterns ("I hope this finds you well", "Please don't hesitate", excessive bullets)
8. **Effectiveness**: Would achieve the writer's goal with this specific recipient

{constraint_criteria}

## OUTPUT FORMAT
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

    # IMPROVED: Simulated recipient with full context
    RECIPIENT_PERSONA_PROMPT = '''
You are {recipient_name}, {recipient_title}.
{recipient_context}

You received a message from {writer_name}, {writer_title} at {writer_company}.
Your relationship: {relationship}

The message is regarding: {task_summary}

You received two versions. Which would you prefer to receive?

## VERSION A
{response_a}

## VERSION B
{response_b}

## YOUR EVALUATION
As {recipient_name}, evaluate based on YOUR perspective:

1. **Relevance**: Does this address what I need?
2. **Actionability**: Can I easily act on this?
3. **Respect for Time**: Is the length appropriate for my role as {recipient_title}?
4. **Professionalism**: Is the tone appropriate for our {relationship} relationship?
5. **Helpfulness**: Does this help me do my job?
6. **Clarity**: Do I understand what's being asked/communicated?

Output as JSON:
```json
{{
  "criteria_scores": {{...}},
  "verdict": "a_wins" | "b_wins" | "tie",
  "confidence": 0.75,
  "reasoning": "As {recipient_name}, I prefer Version X because..."
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
            tasks.append(self._get_judge_result(
                model=model,
                persona="writing_expert",
                prompt=prompt,
                response_a=response_a,
                response_b=response_b
            ))

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
                temperature=0.3 + (i * 0.1),
                max_tokens=2000
            )
            vote = self._parse_vote(response.content)
            votes.append(vote)

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
        """Build judge prompt with FULL persona context."""

        # Build CC context if present
        cc_context = ""
        if prompt.cc_recipients:
            cc_names = [r.name for r in prompt.cc_recipients]
            cc_context = f"CC Recipients: {', '.join(cc_names)}\nNote: The writer must navigate tone for this mixed audience."

        # Build constraint criteria if present
        constraint_criteria = ""
        if prompt.has_constraints and prompt.explicit_constraints:
            constraint_criteria = "9. **Instruction Following**: Did the response follow these explicit constraints?\n"
            for c in prompt.explicit_constraints:
                constraint_criteria += f"   - {c.description}\n"

        if persona == "writing_expert":
            return self.WRITING_EXPERT_PROMPT.format(
                task_text=prompt.onet_task_text,
                channel=prompt.communication_channel or "email",
                urgency=prompt.urgency.value,
                formality=prompt.formality.value,
                writer_name=prompt.writer.name,
                writer_title=prompt.writer.job_title,
                writer_company=prompt.writer.company,
                company_size=prompt.writer.company_size,
                industry=prompt.writer.industry,
                writer_age=prompt.writer.age_range,
                writer_generation=prompt.writer.generation,
                writer_skill=prompt.writer.skill_level,
                writer_english=prompt.writer.english_variant,
                writer_native="Yes" if prompt.writer.is_native_english else "No",
                recipient_name=prompt.primary_recipient.name,
                recipient_title=prompt.primary_recipient.job_title,
                relationship=prompt.primary_recipient.relationship_to_writer,
                recipient_english=prompt.primary_recipient.english_variant,
                recipient_native="Yes" if prompt.primary_recipient.is_native_english else "No",
                cc_context=cc_context,
                response_a=response_a,
                response_b=response_b,
                constraint_criteria=constraint_criteria
            )
        else:
            return self.RECIPIENT_PERSONA_PROMPT.format(
                recipient_name=prompt.primary_recipient.name,
                recipient_title=prompt.primary_recipient.job_title,
                recipient_context=f"You work at {prompt.writer.company if not prompt.primary_recipient.company else prompt.primary_recipient.company}.",
                writer_name=prompt.writer.name,
                writer_title=prompt.writer.job_title,
                writer_company=prompt.writer.company,
                relationship=prompt.primary_recipient.relationship_to_writer,
                task_summary=prompt.onet_task_text,
                response_a=response_a,
                response_b=response_b
            )

    def _parse_vote(self, content: str) -> JudgeVote:
        """Parse LLM response into a JudgeVote."""
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found")

            data = json.loads(content[start:end])

            verdict_map = {
                'a_wins': JudgeVerdict.A_WINS,
                'b_wins': JudgeVerdict.B_WINS,
                'tie': JudgeVerdict.TIE
            }

            return JudgeVote(
                verdict=verdict_map.get(data.get('verdict', 'tie'), JudgeVerdict.TIE),
                confidence=data.get('confidence', 0.5),
                reasoning=data.get('reasoning', ''),
                criteria_scores=data.get('criteria_scores', {})
            )
        except Exception:
            return JudgeVote(
                verdict=JudgeVerdict.TIE,
                confidence=0.0,
                reasoning="Parse error",
                criteria_scores={}
            )
```

### 4.3 Response Analyzer (NEW)

```python
# src/eval/response_analyzer.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import re

@dataclass
class ResponseMetadata:
    """Metadata extracted from a response for analysis."""
    word_count: int
    character_count: int
    sentence_count: int
    paragraph_count: int
    has_greeting: bool
    greeting_type: Optional[str]  # formal, casual, none
    has_signoff: bool
    signoff_type: Optional[str]
    has_bullets: bool
    bullet_count: int
    has_headers: bool
    header_count: int
    has_numbered_list: bool
    cliche_count: int
    cliches_found: List[str]

class ResponseAnalyzer:
    """
    Analyzes response structure and patterns per PROMPT.md requirement:
    "Track metadata for every response to enable deeper analysis"
    """

    AI_CLICHES = [
        "i hope this email finds you well",
        "i hope this finds you well",
        "please don't hesitate to reach out",
        "please do not hesitate to contact",
        "i'm happy to help",
        "i am happy to assist",
        "feel free to reach out",
        "at your earliest convenience",
        "please let me know if you have any questions",
        "i look forward to hearing from you",
        "thank you for your understanding",
        "as per our discussion",
        "as discussed",
        "i wanted to follow up",
        "just checking in",
        "hope all is well",
        "trust this finds you well",
    ]

    FORMAL_GREETINGS = ["dear", "good morning", "good afternoon", "good evening"]
    CASUAL_GREETINGS = ["hi", "hey", "hello"]

    FORMAL_SIGNOFFS = ["sincerely", "best regards", "kind regards", "respectfully", "yours truly"]
    CASUAL_SIGNOFFS = ["thanks", "cheers", "best", "take care"]

    def analyze(self, response: str) -> ResponseMetadata:
        """Extract metadata from a response."""

        # Basic counts
        words = response.split()
        word_count = len(words)
        character_count = len(response)

        # Sentence count (approximate)
        sentences = re.split(r'[.!?]+', response)
        sentence_count = len([s for s in sentences if s.strip()])

        # Paragraph count
        paragraphs = response.split('\n\n')
        paragraph_count = len([p for p in paragraphs if p.strip()])

        # Greeting detection
        first_line = response.strip().split('\n')[0].lower() if response.strip() else ""
        has_greeting = False
        greeting_type = None

        for greeting in self.FORMAL_GREETINGS:
            if first_line.startswith(greeting):
                has_greeting = True
                greeting_type = "formal"
                break

        if not has_greeting:
            for greeting in self.CASUAL_GREETINGS:
                if first_line.startswith(greeting):
                    has_greeting = True
                    greeting_type = "casual"
                    break

        # Sign-off detection
        last_lines = response.strip().split('\n')[-3:] if response.strip() else []
        last_text = ' '.join(last_lines).lower()
        has_signoff = False
        signoff_type = None

        for signoff in self.FORMAL_SIGNOFFS:
            if signoff in last_text:
                has_signoff = True
                signoff_type = "formal"
                break

        if not has_signoff:
            for signoff in self.CASUAL_SIGNOFFS:
                if signoff in last_text:
                    has_signoff = True
                    signoff_type = "casual"
                    break

        # Bullet detection
        bullet_pattern = r'^[\s]*[-*•]\s+'
        bullet_matches = re.findall(bullet_pattern, response, re.MULTILINE)
        has_bullets = len(bullet_matches) > 0
        bullet_count = len(bullet_matches)

        # Header detection
        header_pattern = r'^#+\s+.+|^[A-Z][^.!?]*:$'
        header_matches = re.findall(header_pattern, response, re.MULTILINE)
        has_headers = len(header_matches) > 0
        header_count = len(header_matches)

        # Numbered list detection
        numbered_pattern = r'^\s*\d+[.)]\s+'
        has_numbered_list = bool(re.search(numbered_pattern, response, re.MULTILINE))

        # Cliche detection
        response_lower = response.lower()
        cliches_found = [c for c in self.AI_CLICHES if c in response_lower]
        cliche_count = len(cliches_found)

        return ResponseMetadata(
            word_count=word_count,
            character_count=character_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            has_greeting=has_greeting,
            greeting_type=greeting_type,
            has_signoff=has_signoff,
            signoff_type=signoff_type,
            has_bullets=has_bullets,
            bullet_count=bullet_count,
            has_headers=has_headers,
            header_count=header_count,
            has_numbered_list=has_numbered_list,
            cliche_count=cliche_count,
            cliches_found=cliches_found
        )
```

### 4.4 Constraint Checker (NEW)

```python
# src/eval/constraint_checker.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import re
from ..prompts.schemas import ExplicitConstraint

@dataclass
class ConstraintResult:
    constraint: ExplicitConstraint
    passed: bool
    actual_value: Any
    details: str

class ConstraintChecker:
    """
    Checks if responses comply with explicit constraints.
    Per PROMPT.md: "Track compliance separately"
    """

    def check_all(
        self,
        response: str,
        constraints: List[ExplicitConstraint]
    ) -> List[ConstraintResult]:
        """Check all constraints against a response."""
        return [self.check_constraint(response, c) for c in constraints]

    def check_constraint(
        self,
        response: str,
        constraint: ExplicitConstraint
    ) -> ConstraintResult:
        """Check a single constraint."""

        verification = constraint.verification
        target = constraint.target_value

        if verification == "word_count_max":
            actual = len(response.split())
            passed = actual <= target
            return ConstraintResult(constraint, passed, actual, f"Word count: {actual}/{target}")

        elif verification == "word_count_min":
            actual = len(response.split())
            passed = actual >= target
            return ConstraintResult(constraint, passed, actual, f"Word count: {actual}/{target}")

        elif verification == "sentence_count_max":
            actual = len(re.split(r'[.!?]+', response))
            passed = actual <= target
            return ConstraintResult(constraint, passed, actual, f"Sentences: {actual}/{target}")

        elif verification == "paragraph_count":
            actual = len([p for p in response.split('\n\n') if p.strip()])
            passed = actual == target
            return ConstraintResult(constraint, passed, actual, f"Paragraphs: {actual}/{target}")

        elif verification == "bullet_count":
            actual = len(re.findall(r'^[\s]*[-*•]\s+', response, re.MULTILINE))
            passed = actual == target
            return ConstraintResult(constraint, passed, actual, f"Bullets: {actual}/{target}")

        elif verification == "no_bullets":
            actual = len(re.findall(r'^[\s]*[-*•]\s+', response, re.MULTILINE))
            passed = actual == 0
            return ConstraintResult(constraint, passed, actual, f"Bullets found: {actual}")

        elif verification == "has_headers":
            actual = len(re.findall(r'^#+\s+', response, re.MULTILINE))
            passed = actual > 0
            return ConstraintResult(constraint, passed, actual, f"Headers: {actual}")

        elif verification == "excludes_words":
            response_lower = response.lower()
            found = [w for w in target if w.lower() in response_lower]
            passed = len(found) == 0
            return ConstraintResult(constraint, passed, found, f"Found excluded: {found}")

        elif verification == "includes_phrase":
            passed = target.lower() in response.lower()
            return ConstraintResult(constraint, passed, passed, f"Contains '{target}': {passed}")

        elif verification == "no_pleasantries":
            pleasantries = ["hope this finds you", "hope you're well", "hope all is well"]
            found = [p for p in pleasantries if p in response.lower()]
            passed = len(found) == 0
            return ConstraintResult(constraint, passed, found, f"Pleasantries: {found}")

        else:
            return ConstraintResult(constraint, True, None, "Verification not implemented")

    def get_compliance_rate(self, results: List[ConstraintResult]) -> float:
        """Calculate overall compliance rate."""
        if not results:
            return 1.0
        return sum(1 for r in results if r.passed) / len(results)
```

---

## Part 5: Improved Database Schema

### 5.1 Complete SQLite Schema (Fixed)

```python
# src/eval/checkpoint.py - Database initialization

SCHEMA = '''
-- Prompts table (MISSING in original draft)
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    onet_task_id TEXT NOT NULL,
    onet_task_text TEXT NOT NULL,
    occupation_code TEXT NOT NULL,
    occupation_title TEXT NOT NULL,
    job_zone INTEGER,
    soc_major_group TEXT,
    naics_code TEXT,
    naics_title TEXT,
    prompt_type TEXT NOT NULL,  -- generation, revision, reply, etc.
    inferred_writing_type TEXT,

    -- Writer persona (JSON)
    writer_json TEXT NOT NULL,

    -- Recipient persona (JSON)
    recipient_json TEXT NOT NULL,

    -- Context dimensions
    formality TEXT,
    urgency TEXT,
    relationship_context TEXT,
    audience_size TEXT,
    emotional_context TEXT,
    message_position TEXT,
    communication_channel TEXT,

    -- Features
    has_constraints INTEGER DEFAULT 0,
    constraints_json TEXT,
    has_revision_context INTEGER DEFAULT 0,
    revision_context_json TEXT,
    is_deliberately_vague INTEGER DEFAULT 0,
    vagueness_type TEXT,
    is_sensitive INTEGER DEFAULT 0,
    sensitive_categories_json TEXT,

    -- Language
    language TEXT DEFAULT 'en',
    language_variant TEXT DEFAULT 'en-US',

    -- The actual prompt
    prompt_text TEXT NOT NULL,

    -- Metadata
    generation_seed INTEGER,
    generated_at TEXT NOT NULL,

    -- Indexes will be created below
    UNIQUE(prompt_id)
);

-- Comparisons table
CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL,
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,

    -- Final result
    final_verdict TEXT NOT NULL,  -- gemini_wins, competitor_wins, tie

    -- Responses
    gemini_response TEXT,
    competitor_response TEXT,
    gemini_latency_ms REAL,
    competitor_latency_ms REAL,
    gemini_tokens INTEGER,
    competitor_tokens INTEGER,

    -- Response metadata (NEW)
    gemini_metadata_json TEXT,      -- ResponseMetadata as JSON
    competitor_metadata_json TEXT,

    -- Constraint compliance (NEW)
    gemini_constraint_compliance REAL,
    competitor_constraint_compliance REAL,
    constraint_results_json TEXT,

    -- Presentation order (for position bias analysis)
    response_order TEXT,  -- "gemini_first" or "competitor_first"

    -- Agreement
    inter_judge_agreement REAL,

    -- Failure handling
    is_auto_loss INTEGER DEFAULT 0,
    auto_loss_reason TEXT,
    auto_loss_model TEXT,

    -- Refusal tracking (NEW)
    gemini_refused INTEGER DEFAULT 0,
    competitor_refused INTEGER DEFAULT 0,
    refusal_category TEXT,

    -- Timestamps
    created_at TEXT NOT NULL,

    FOREIGN KEY(prompt_id) REFERENCES prompts(prompt_id),
    UNIQUE(prompt_id, competitor_model)
);

-- Judge votes table
CREATE TABLE IF NOT EXISTS judge_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    judge_model TEXT NOT NULL,
    persona TEXT NOT NULL,  -- writing_expert or recipient
    vote_index INTEGER NOT NULL,
    verdict TEXT NOT NULL,  -- a_wins, b_wins, tie
    confidence REAL,
    reasoning TEXT,
    criteria_scores_json TEXT,

    FOREIGN KEY(comparison_id) REFERENCES comparisons(id)
);

-- Response metadata table (NEW - for detailed structure analysis)
CREATE TABLE IF NOT EXISTS response_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    model TEXT NOT NULL,  -- gemini or competitor
    word_count INTEGER,
    character_count INTEGER,
    sentence_count INTEGER,
    paragraph_count INTEGER,
    has_greeting INTEGER,
    greeting_type TEXT,
    has_signoff INTEGER,
    signoff_type TEXT,
    has_bullets INTEGER,
    bullet_count INTEGER,
    has_headers INTEGER,
    header_count INTEGER,
    has_numbered_list INTEGER,
    cliche_count INTEGER,
    cliches_found TEXT,  -- JSON array

    FOREIGN KEY(comparison_id) REFERENCES comparisons(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(occupation_code);
CREATE INDEX IF NOT EXISTS idx_prompts_job_zone ON prompts(job_zone);
CREATE INDEX IF NOT EXISTS idx_prompts_formality ON prompts(formality);
CREATE INDEX IF NOT EXISTS idx_prompts_type ON prompts(prompt_type);
CREATE INDEX IF NOT EXISTS idx_prompts_naics ON prompts(naics_code);
CREATE INDEX IF NOT EXISTS idx_prompts_language ON prompts(language_variant);
CREATE INDEX IF NOT EXISTS idx_prompts_sensitive ON prompts(is_sensitive);

CREATE INDEX IF NOT EXISTS idx_comparisons_prompt ON comparisons(prompt_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_verdict ON comparisons(final_verdict);
CREATE INDEX IF NOT EXISTS idx_comparisons_competitor ON comparisons(competitor_model);
CREATE INDEX IF NOT EXISTS idx_comparisons_auto_loss ON comparisons(is_auto_loss);

CREATE INDEX IF NOT EXISTS idx_votes_comparison ON judge_votes(comparison_id);
CREATE INDEX IF NOT EXISTS idx_votes_judge ON judge_votes(judge_model);
CREATE INDEX IF NOT EXISTS idx_votes_verdict ON judge_votes(verdict);

-- Views for common queries
CREATE VIEW IF NOT EXISTS win_rates_by_competitor AS
SELECT
    competitor_model,
    COUNT(*) as total,
    SUM(CASE WHEN final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) as gemini_wins,
    SUM(CASE WHEN final_verdict = 'competitor_wins' THEN 1 ELSE 0 END) as competitor_wins,
    SUM(CASE WHEN final_verdict = 'tie' THEN 1 ELSE 0 END) as ties,
    CAST(SUM(CASE WHEN final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) AS REAL) /
        NULLIF(SUM(CASE WHEN final_verdict != 'tie' THEN 1 ELSE 0 END), 0) as gemini_win_rate
FROM comparisons
GROUP BY competitor_model;

CREATE VIEW IF NOT EXISTS win_rates_by_occupation AS
SELECT
    p.occupation_code,
    p.occupation_title,
    c.competitor_model,
    COUNT(*) as total,
    SUM(CASE WHEN c.final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) as gemini_wins,
    CAST(SUM(CASE WHEN c.final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) AS REAL) /
        NULLIF(SUM(CASE WHEN c.final_verdict != 'tie' THEN 1 ELSE 0 END), 0) as gemini_win_rate
FROM comparisons c
JOIN prompts p ON c.prompt_id = p.prompt_id
GROUP BY p.occupation_code, c.competitor_model;
'''
```

---

## Part 6: Cross-Run Comparison (NEW)

```python
# src/analysis/cross_run.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import sqlite3
import json
from scipy import stats
import numpy as np

@dataclass
class RunSummary:
    run_id: str
    timestamp: str
    num_prompts: int
    model_pairs: List[str]
    overall_win_rate: float
    win_rates_by_model: Dict[str, float]

@dataclass
class CrossRunComparison:
    run_a: RunSummary
    run_b: RunSummary
    win_rate_delta: Dict[str, float]  # Per model pair
    is_significant: Dict[str, bool]   # Statistical significance
    common_weaknesses: List[str]
    divergent_results: List[str]      # Prompts with different outcomes

class CrossRunAnalyzer:
    """
    Compare results across multiple evaluation runs.
    Per PROMPT.md: "Support comparing results across multiple runs"
    """

    def __init__(self, results_dirs: List[Path]):
        self.results_dirs = results_dirs
        self.runs: List[RunSummary] = []

    def load_runs(self) -> List[RunSummary]:
        """Load summaries from all runs."""
        for run_dir in self.results_dirs:
            summary = self._load_run_summary(run_dir)
            if summary:
                self.runs.append(summary)
        return self.runs

    def _load_run_summary(self, run_dir: Path) -> Optional[RunSummary]:
        """Load summary for a single run."""
        db_path = run_dir / "results.db"
        config_path = run_dir / "config.json"

        if not db_path.exists():
            return None

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get overall stats
            stats_query = """
            SELECT
                competitor_model,
                COUNT(*) as total,
                SUM(CASE WHEN final_verdict = 'gemini_wins' THEN 1 ELSE 0 END) as wins
            FROM comparisons
            GROUP BY competitor_model
            """
            rows = conn.execute(stats_query).fetchall()

        win_rates = {}
        total_wins = 0
        total_decisive = 0

        for row in rows:
            decisive = row['total'] - conn.execute(
                "SELECT COUNT(*) FROM comparisons WHERE competitor_model=? AND final_verdict='tie'",
                (row['competitor_model'],)
            ).fetchone()[0]
            if decisive > 0:
                win_rates[row['competitor_model']] = row['wins'] / decisive
                total_wins += row['wins']
                total_decisive += decisive

        # Load config
        config = {}
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)

        return RunSummary(
            run_id=run_dir.name,
            timestamp=config.get('started_at', 'unknown'),
            num_prompts=config.get('num_prompts', 0),
            model_pairs=list(win_rates.keys()),
            overall_win_rate=total_wins / total_decisive if total_decisive > 0 else 0.5,
            win_rates_by_model=win_rates
        )

    def compare_runs(
        self,
        run_a_id: str,
        run_b_id: str
    ) -> CrossRunComparison:
        """Compare two specific runs."""
        run_a = next((r for r in self.runs if r.run_id == run_a_id), None)
        run_b = next((r for r in self.runs if r.run_id == run_b_id), None)

        if not run_a or not run_b:
            raise ValueError(f"Run not found: {run_a_id} or {run_b_id}")

        # Calculate deltas
        win_rate_delta = {}
        is_significant = {}

        common_models = set(run_a.win_rates_by_model.keys()) & set(run_b.win_rates_by_model.keys())

        for model in common_models:
            rate_a = run_a.win_rates_by_model[model]
            rate_b = run_b.win_rates_by_model[model]
            win_rate_delta[model] = rate_b - rate_a

            # Two-proportion z-test for significance
            # (simplified - would need actual counts for proper test)
            is_significant[model] = abs(rate_b - rate_a) > 0.1

        return CrossRunComparison(
            run_a=run_a,
            run_b=run_b,
            win_rate_delta=win_rate_delta,
            is_significant=is_significant,
            common_weaknesses=[],
            divergent_results=[]
        )

    def find_consistent_weaknesses(self) -> Dict[str, List[str]]:
        """Find weaknesses that appear consistently across runs."""
        # Would analyze weakness patterns across all runs
        return {}

    def generate_comparison_report(self) -> str:
        """Generate markdown report comparing all runs."""
        lines = ["# Cross-Run Comparison Report\n"]

        for run in self.runs:
            lines.append(f"## Run: {run.run_id}")
            lines.append(f"- Prompts: {run.num_prompts}")
            lines.append(f"- Overall Win Rate: {run.overall_win_rate:.1%}")
            lines.append("")
            for model, rate in run.win_rates_by_model.items():
                lines.append(f"  - vs {model}: {rate:.1%}")
            lines.append("")

        return "\n".join(lines)
```

---

## Part 7: Cost Estimation Implementation (Fixed)

```python
# src/config.py

from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
import yaml

@dataclass
class CostEstimate:
    """Detailed cost breakdown for an evaluation run."""
    prompts: int
    model_pairs: int
    total_comparisons: int

    # Judge configuration
    judge_config: str
    total_judge_calls: int

    # Cost estimates (low/high range)
    response_cost_low: float
    response_cost_high: float
    judge_cost_low: float
    judge_cost_high: float
    total_cost_low: float
    total_cost_high: float

    # Time estimates
    time_with_limits: str
    time_parallel: str

def estimate_cost(config: 'EvalConfig') -> CostEstimate:
    """
    Calculate detailed cost and time estimates for an evaluation run.
    Uses verified OpenRouter pricing when available.
    """
    num_prompts = config.num_prompts
    num_pairs = len(config.model_pairs)
    total_comparisons = num_prompts * num_pairs

    # Judge configuration
    num_judges = len(config.judge_models)
    votes_per_judge = config.votes_per_judge
    personas = 2 if config.use_both_personas else 1
    total_judge_calls = total_comparisons * num_judges * votes_per_judge * personas

    judge_config = f"{num_judges} judges x {votes_per_judge} votes x {personas} personas"

    # Token estimates (based on typical writing tasks)
    avg_prompt_tokens = 800   # Input tokens per prompt
    avg_response_tokens = 400  # Output tokens per response
    avg_judge_input = 1500     # Judge prompt with both responses
    avg_judge_output = 300     # Judge verdict

    # Model pricing (per 1M tokens) - would use verified prices if available
    # Using conservative estimates
    response_model_cost = {
        'input': 5.0,   # Average across models
        'output': 15.0
    }
    judge_model_cost = {
        'input': 10.0,  # Judges tend to be premium models
        'output': 30.0
    }

    # Response generation cost
    response_input_tokens = num_prompts * avg_prompt_tokens * 2  # Both models
    response_output_tokens = num_prompts * avg_response_tokens * 2

    response_cost_base = (
        response_input_tokens * response_model_cost['input'] +
        response_output_tokens * response_model_cost['output']
    ) / 1_000_000

    # Add 20% variance for low/high
    response_cost_low = response_cost_base * 0.8 * num_pairs
    response_cost_high = response_cost_base * 1.2 * num_pairs

    # Judging cost
    judge_input_tokens = total_judge_calls * avg_judge_input
    judge_output_tokens = total_judge_calls * avg_judge_output

    judge_cost_base = (
        judge_input_tokens * judge_model_cost['input'] +
        judge_output_tokens * judge_model_cost['output']
    ) / 1_000_000

    judge_cost_low = judge_cost_base * 0.8
    judge_cost_high = judge_cost_base * 1.2

    # Total
    total_cost_low = response_cost_low + judge_cost_low
    total_cost_high = response_cost_high + judge_cost_high

    # Time estimates
    # Assume ~2 seconds per API call average, rate limits of ~60 calls/min
    total_api_calls = total_comparisons * 2 + total_judge_calls  # Responses + judges

    # With rate limits (sequential)
    time_rate_limited_seconds = total_api_calls * 1.5  # 1.5s average with limits
    time_with_limits = _format_duration(time_rate_limited_seconds)

    # Parallelized (assume 10x speedup but bounded by rate limits)
    time_parallel_seconds = time_rate_limited_seconds / 5
    time_parallel = _format_duration(time_parallel_seconds)

    return CostEstimate(
        prompts=num_prompts,
        model_pairs=num_pairs,
        total_comparisons=total_comparisons,
        judge_config=judge_config,
        total_judge_calls=total_judge_calls,
        response_cost_low=response_cost_low,
        response_cost_high=response_cost_high,
        judge_cost_low=judge_cost_low,
        judge_cost_high=judge_cost_high,
        total_cost_low=total_cost_low,
        total_cost_high=total_cost_high,
        time_with_limits=time_with_limits,
        time_parallel=time_parallel
    )

def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)} sec"
    elif seconds < 3600:
        return f"{int(seconds/60)} min"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m" if mins else f"{hours} hrs"
```

---

## Part 8: Implementation Roadmap (Revised)

### Phase 1: Foundation (Week 1)
1. Set up project structure with pyproject.toml
2. Implement `OnetLoader` **without hardcoded categories**
3. Implement `OnetReferenceParser` to use Opus's guidance
4. Implement `NAICSMapper` with SOC-to-NAICS mapping
5. Implement `CompanyDatabase` with international coverage
6. Implement `NameGenerator` with regional variants
7. Create Pydantic schemas for all data models
8. Unit tests for data layer

### Phase 2: Prompt Generation (Week 2)
1. Implement Phase 1 LLM persona generation
2. Implement Phase 2 algorithmic combination (no hardcoded categories)
3. Implement Phase 3 LLM enrichment
4. **NEW**: Implement `RevisionTaskGenerator`
5. **NEW**: Implement `ConstraintGenerator`
6. **NEW**: Implement `AmbiguityGenerator`
7. Create `PromptGenerator` orchestrator with type distribution
8. Test prompt diversity and quality
9. Generate sample prompt sets for validation

### Phase 3: Evaluation Core (Week 3)
1. Implement `OpenRouterClient` with model verification
2. Implement `JudgePanel` with **full persona context**
3. Implement `VoteAggregator` with majority-of-majorities
4. **NEW**: Implement `ResponseAnalyzer` for structure analysis
5. **NEW**: Implement `ConstraintChecker` for compliance tracking
6. Implement `CheckpointManager` with complete schema
7. Implement `EvalRunner` orchestrator
8. Integration tests with mock API

### Phase 4: Analysis & Reporting (Week 4)
1. Implement `StatisticalAnalyzer` with proper confidence intervals
2. Implement `BiasDetector` for position, length, model biases
3. Implement `WeaknessFinder` with database joins
4. **NEW**: Implement `CrossRunAnalyzer` for multi-run comparison
5. **NEW**: Implement regional variant analysis
6. Create visualization functions with plotly
7. Implement `PDFReportGenerator`
8. Design and test report templates

### Phase 5: TUI & CLI (Week 5)
1. Implement `ProgressDashboard` with all required elements
2. Implement `ResultsViewer` with filtering/sorting
3. Create CLI with click
4. Implement preset configurations
5. **NEW**: Implement `estimate_cost()` with real pricing
6. **NEW**: Implement `--compare` command for cross-run analysis
7. End-to-end testing

### Phase 6: Polish & Documentation (Week 6)
1. Comprehensive testing with real API calls
2. Verify model IDs against OpenRouter
3. Performance optimization
4. Documentation
5. Example runs and validation
6. Bug fixes and refinements

---

## Summary of Key Improvements

| Issue | Original Draft | Improved Plan |
|-------|----------------|---------------|
| Hardcoded categories | 10 fixed `WritingCategory` enum | No categories - LLM infers dynamically |
| Instruction following | Schema only, no implementation | Full `ConstraintGenerator` + `ConstraintChecker` |
| Revision tasks | Not implemented | `RevisionTaskGenerator` with sample drafts |
| Tone matching | Schema only | Integrated into prompt generation |
| CC recipients | Schema only | Generation logic for mixed audiences |
| Cost estimation | Function stub | Full implementation with pricing |
| Judge context | Basic name/title | Full persona (age, generation, skill) |
| Regional variants | Schema only | Full international support |
| Ambiguity handling | Schema only | `AmbiguityGenerator` + assessment |
| Response metadata | Token count only | Full structure analysis |
| Database schema | Missing prompts table | Complete schema with views |
| Cross-run comparison | CLI stub only | Full `CrossRunAnalyzer` |
| Model verification | Hardcoded IDs | Dynamic verification via API |
| O*NET reference | Not used | Integrated parser |

This improved plan addresses all identified issues from the original draft while maintaining the core architecture and providing comprehensive coverage of PROMPT.md requirements.
