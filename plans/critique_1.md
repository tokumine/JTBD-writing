# Gemini Writing Evaluation Framework: Improved Implementation Plan

## Critical Analysis of Original Draft

### Strengths of Original Draft
1. Comprehensive architecture with clear component separation
2. Good Pydantic schema definitions for type safety
3. Reasonable technology stack choices
4. Solid database schema design
5. Good understanding of the three-phase prompt generation approach

### Critical Issues Identified

#### Issue 1: OpenRouter Model IDs are Speculative
The original draft uses model IDs like `google/gemini-3-pro`, `openai/gpt-5.2-thinking`, etc. These are **fabricated identifiers** that don't exist on OpenRouter. The plan must:
- Verify actual OpenRouter model availability at runtime
- Use a configuration file for model mappings that can be updated
- Include a model discovery/verification step before evaluation runs

#### Issue 2: Missing O*NET Reference File Usage
The PROMPT.md specifies that `db/ONET_REFERENCE.md` contains pre-processed guidance, but the draft ignores this entirely. The plan should:
- Read and incorporate the O*NET reference guide
- Use the pre-identified writing-relevant tasks rather than rediscovering them

#### Issue 3: Incomplete Company Database Strategy
The draft mentions embedding company knowledge but provides no realistic implementation. Real companies require:
- Verification that named companies still exist and are relevant
- Handling of company name changes, mergers, acquisitions
- A fallback strategy when company data is outdated
- Legal/trademark considerations for using real company names

#### Issue 4: Phase 3 LLM Enrichment Model Selection Bias
Using "the same models being evaluated" for prompt generation creates circular bias. The draft acknowledges this but provides no mitigation. Better approach:
- Use a **separate model** not in the evaluation set for enrichment
- Or use multiple models and track which model generated each enrichment

#### Issue 5: Insufficient Error Handling for Judge Parsing
The judging system assumes judges will return valid JSON. In practice:
- LLMs often return malformed JSON
- Judges may refuse certain comparisons
- Response format may vary between models
- Need robust JSON extraction with fallbacks

#### Issue 6: Missing Dual Persona Implementation Details
The draft mentions dual judge personas but the actual prompts are incomplete:
- No template for how recipient persona receives context
- No handling of how to simulate being the actual recipient

#### Issue 7: Cost Estimation Inaccuracies
The cost estimation uses hardcoded token counts (800 input, 400 output) which will be wildly inaccurate for:
- Context-heavy prompts with attachments (could be 2000+ tokens)
- Long-form writing tasks (responses could be 1000+ tokens)
- Judge prompts which include two full responses (3000+ tokens)

#### Issue 8: Missing Sensitive Topic Detection Implementation
PROMPT.md requires flagging sensitive topics, but the draft has no implementation for detecting them during prompt generation.

#### Issue 9: No Instruction-Following Test Implementation
PROMPT.md specifies testing explicit constraints like "under 100 words" but the draft doesn't include:
- Generation of constrained prompts
- Compliance checking
- Separate tracking of instruction-following success

#### Issue 10: Ambiguity Handling Not Implemented
PROMPT.md requires deliberately vague prompts and tracking how models handle them, but no implementation is provided.

---

## IMPROVED IMPLEMENTATION PLAN

## 1. SYSTEM ARCHITECTURE

### 1.1 High-Level Architecture

```
+-----------------------------------------------------------------------------+
|                     GEMINI WRITING EVALUATION FRAMEWORK                      |
+-----------------------------------------------------------------------------+
|                                                                              |
|  +----------------+    +----------------+    +----------------+              |
|  |  CONFIGURATION |    |    O*NET       |    |   OPENROUTER   |              |
|  |    MANAGER     |    |   PIPELINE     |    |    CLIENT      |              |
|  +----------------+    +----------------+    +----------------+              |
|         |                     |                     |                        |
|         v                     v                     v                        |
|  +----------------------------------------------------------------------+   |
|  |                      PROMPT GENERATION ENGINE                         |   |
|  |  Phase 1: Offline LLM Generation (uses dedicated enrichment model)    |   |
|  |  Phase 2: Algorithmic Combination (deterministic with seed)           |   |
|  |  Phase 3: LLM Enrichment (context-heavy prompts only)                 |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                      EVALUATION ENGINE                                |   |
|  |  Response Generator -> Position Randomizer -> Judge Orchestrator      |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                      STORAGE & CHECKPOINTING                          |   |
|  |  SQLite Results DB | JSON Checkpoints | Atomic Writes                 |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------+    +----------------+    +----------------+              |
|  |    ANALYSIS    |    |   PROGRESS     |    |    REPORT      |              |
|  |    ENGINE      |    |   TUI          |    |   GENERATOR    |              |
|  +----------------+    +----------------+    +----------------+              |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 1.2 Directory Structure (Improved)

```
gemini-writing-eval/
├── src/
│   ├── __init__.py
│   ├── main.py                    # CLI entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Pydantic settings with env vars
│   │   ├── presets.py             # 10 eval presets with validation
│   │   ├── models.py              # Model registry with OpenRouter IDs
│   │   └── models.yaml            # External model config (updateable)
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_loader.py         # Load O*NET with reference guide
│   │   ├── task_sampler.py        # Stratified sampling with validation
│   │   ├── naics_mapper.py        # SOC-to-NAICS crosswalk
│   │   ├── company_registry.py    # Real company data with fallbacks
│   │   ├── name_generator.py      # Diverse realistic names
│   │   └── sensitive_detector.py  # Sensitive topic classification
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py           # Three-phase orchestrator
│   │   ├── phase1_personas.py     # Offline persona generation
│   │   ├── phase2_combiner.py     # Algorithmic combination
│   │   ├── phase3_enricher.py     # LLM context enrichment
│   │   ├── constraint_gen.py      # Instruction-following constraints
│   │   ├── ambiguity_gen.py       # Deliberately vague prompts
│   │   └── schemas.py             # Pydantic models
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── runner.py              # Main orchestrator with lifecycle
│   │   ├── response_gen.py        # Model response collection
│   │   ├── judge_engine.py        # Multi-model judging
│   │   ├── judge_parser.py        # Robust JSON extraction
│   │   ├── voting.py              # Majority-of-majorities
│   │   ├── compliance_checker.py  # Instruction-following validation
│   │   └── refusal_classifier.py  # Categorize model refusals
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite with migrations
│   │   ├── checkpoint.py          # Atomic checkpointing
│   │   ├── run_manager.py         # Run directory lifecycle
│   │   └── exporter.py            # CSV/JSON export
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter.py          # OpenRouter client
│   │   ├── model_verifier.py      # Verify model availability
│   │   ├── rate_limiter.py        # Per-model adaptive limits
│   │   └── retry.py               # Exponential backoff with jitter
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── progress.py            # Rich TUI progress dashboard
│   │   ├── viewer.py              # Results viewer TUI
│   │   ├── cost_display.py        # Live cost estimation display
│   │   └── components.py          # Shared UI components
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # Win rates, CI, significance
│   │   ├── bias_detector.py       # Position, length, model biases
│   │   ├── weakness_finder.py     # Multi-dimensional weakness analysis
│   │   ├── agreement_calc.py      # Inter-rater reliability
│   │   └── visualizations.py      # Plotly chart generation
│   └── reports/
│       ├── __init__.py
│       ├── pdf_generator.py       # ReportLab PDF generation
│       ├── narrative_gen.py       # LLM-assisted report narratives
│       └── templates/             # Report templates
├── db/
│   ├── onet.db                    # O*NET 30.1 database
│   └── ONET_REFERENCE.md          # Pre-processed writing task guide
├── config/
│   ├── models.yaml                # Model configuration (editable)
│   └── companies.yaml             # Company registry (editable)
├── results/                       # Eval run outputs
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── pyproject.toml
└── .env.example
```

### 1.3 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async, type hints, pattern matching |
| HTTP Client | httpx | Async support, connection pooling, timeouts |
| Data Models | Pydantic v2 | Validation, serialization, settings management |
| Database | SQLite + aiosqlite | Portable, ACID, async-capable |
| TUI | Textual | Rich terminal UI framework, responsive |
| Charts | Plotly | Interactive, exports to PNG/PDF via Kaleido |
| PDF | ReportLab | Professional PDF generation |
| CLI | Typer | Type-annotated CLI with auto-help |
| Config | pydantic-settings + python-dotenv | Type-safe config from env/files |
| Testing | pytest + pytest-asyncio | Async test support |
| YAML | PyYAML | External configuration files |

### 1.4 Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27"
pydantic = "^2.5"
pydantic-settings = "^2.1"
aiosqlite = "^0.19"
textual = "^0.47"
typer = {extras = ["all"], version = "^0.9"}
plotly = "^5.18"
kaleido = "^0.2"
reportlab = "^4.0"
python-dotenv = "^1.0"
numpy = "^1.26"
scipy = "^1.12"
pandas = "^2.1"
pyyaml = "^6.0"
tenacity = "^8.2"  # Retry library
structlog = "^24.1"  # Structured logging

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
pytest-cov = "^4.1"
mypy = "^1.8"
ruff = "^0.2"
```

---

## 2. DATA PIPELINE: O*NET TO PROMPTS

### 2.1 O*NET Data Extraction (Using Reference Guide)

The implementation MUST first read `db/ONET_REFERENCE.md` to understand the pre-processed task structure.

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import sqlite3

@dataclass
class ONetTask:
    """A single O*NET task statement."""
    task_id: str
    onetsoc_code: str
    occupation_title: str
    task_statement: str
    task_type: str  # 'Core' or 'Supplemental'
    job_zone: int  # 1-5
    soc_major_group: str  # First 2 digits
    writing_relevance_score: float  # From reference guide
    inferred_medium: Optional[str]  # email, memo, report, etc.
    inferred_recipient_type: Optional[str]


class ONetLoader:
    """Load O*NET data using the pre-processed reference guide."""

    def __init__(self, db_path: Path, reference_path: Path):
        self.db_path = db_path
        self.reference_path = reference_path
        self._reference_guide = None

    def load_reference_guide(self) -> dict:
        """Parse ONET_REFERENCE.md for pre-identified writing tasks."""
        if self._reference_guide is None:
            content = self.reference_path.read_text()
            self._reference_guide = self._parse_reference(content)
        return self._reference_guide

    def _parse_reference(self, content: str) -> dict:
        """Extract task IDs and metadata from reference guide."""
        # Parse markdown to extract:
        # - Pre-identified writing-relevant task IDs
        # - Task categorizations
        # - Recommended query patterns
        # Implementation depends on ONET_REFERENCE.md format
        ...

    def get_writing_tasks(
        self,
        limit: Optional[int] = None,
        job_zones: Optional[list[int]] = None,
        soc_codes: Optional[list[str]] = None,
    ) -> list[ONetTask]:
        """
        Retrieve writing-relevant tasks using reference guide.

        Falls back to keyword search only if reference guide unavailable.
        """
        reference = self.load_reference_guide()

        # Build query from reference guide recommendations
        with sqlite3.connect(self.db_path) as conn:
            # Use task IDs from reference guide if available
            if reference.get('task_ids'):
                placeholders = ','.join('?' * len(reference['task_ids']))
                query = f"""
                    SELECT
                        t.task_id,
                        t.onetsoc_code,
                        o.title,
                        t.task,
                        t.task_type,
                        jz.job_zone
                    FROM task_statements t
                    JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
                    LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
                    WHERE t.task_id IN ({placeholders})
                """
                params = reference['task_ids']
            else:
                # Fallback to keyword search
                query = self._build_keyword_query()
                params = []

            # Apply filters
            if job_zones:
                query += " AND jz.job_zone IN ({})".format(
                    ','.join('?' * len(job_zones))
                )
                params.extend(job_zones)

            if soc_codes:
                soc_patterns = [f"{code}%" for code in soc_codes]
                query += " AND ({})".format(
                    ' OR '.join('t.onetsoc_code LIKE ?' for _ in soc_codes)
                )
                params.extend(soc_patterns)

            if limit:
                query += f" LIMIT {limit}"

            cursor = conn.execute(query, params)
            return [self._row_to_task(row) for row in cursor.fetchall()]
```

### 2.2 Stratified Sampling with Validation

```python
from collections import defaultdict
import random

class StratifiedTaskSampler:
    """
    Sample tasks ensuring diversity across multiple dimensions.

    Validates that sample meets diversity requirements.
    """

    DIMENSIONS = [
        'job_zone',           # 5 levels
        'soc_major_group',    # 22 groups
        'task_type',          # Core vs Supplemental
        'inferred_medium',    # email, memo, report, etc.
    ]

    def __init__(self, tasks: list[ONetTask], seed: int):
        self.tasks = tasks
        self.rng = random.Random(seed)
        self._build_indices()

    def _build_indices(self):
        """Build indices for each dimension."""
        self.indices = {dim: defaultdict(list) for dim in self.DIMENSIONS}
        for i, task in enumerate(self.tasks):
            for dim in self.DIMENSIONS:
                value = getattr(task, dim, 'unknown')
                self.indices[dim][value].append(i)

    def sample(
        self,
        n: int,
        stratify_by: list[str] = None,
        min_per_stratum: int = 1,
    ) -> list[ONetTask]:
        """
        Sample n tasks with stratification.

        Args:
            n: Number of tasks to sample
            stratify_by: Dimensions to stratify by (default: all)
            min_per_stratum: Minimum samples per stratum

        Returns:
            List of sampled tasks

        Raises:
            ValueError: If n is too small for stratification requirements
        """
        stratify_by = stratify_by or self.DIMENSIONS

        # Calculate stratum sizes
        strata = self._calculate_strata(stratify_by)
        n_strata = len(strata)

        if n < n_strata * min_per_stratum:
            raise ValueError(
                f"n={n} too small for {n_strata} strata with "
                f"min_per_stratum={min_per_stratum}"
            )

        # Allocate samples to strata
        base_per_stratum = n // n_strata
        remainder = n % n_strata

        sampled_indices = set()
        for i, stratum_indices in enumerate(strata.values()):
            stratum_n = base_per_stratum + (1 if i < remainder else 0)
            stratum_n = min(stratum_n, len(stratum_indices))

            # Sample from stratum
            available = [idx for idx in stratum_indices if idx not in sampled_indices]
            chosen = self.rng.sample(available, min(stratum_n, len(available)))
            sampled_indices.update(chosen)

        # Fill remaining with random sampling
        remaining = n - len(sampled_indices)
        if remaining > 0:
            available = [i for i in range(len(self.tasks)) if i not in sampled_indices]
            additional = self.rng.sample(available, min(remaining, len(available)))
            sampled_indices.update(additional)

        return [self.tasks[i] for i in sorted(sampled_indices)]

    def validate_diversity(self, sample: list[ONetTask]) -> dict:
        """Check sample meets diversity requirements."""
        report = {}
        for dim in self.DIMENSIONS:
            values = [getattr(t, dim, 'unknown') for t in sample]
            unique = set(values)
            counts = {v: values.count(v) for v in unique}
            coverage = len(unique) / len(self.indices[dim])

            report[dim] = {
                'unique_values': len(unique),
                'total_possible': len(self.indices[dim]),
                'coverage': coverage,
                'distribution': counts,
                'is_balanced': max(counts.values()) / min(counts.values()) < 3
            }

        return report
```

### 2.3 Company Registry with Fallbacks

```python
from dataclasses import dataclass
from pathlib import Path
import yaml
from typing import Optional

@dataclass
class Company:
    """A real company for prompt grounding."""
    name: str
    naics_code: str
    industry_name: str
    size_category: str  # startup, small, medium, large, enterprise
    employee_range: str
    public_private: str
    hq_location: str
    founded_year: Optional[int] = None
    verified_date: Optional[str] = None  # When this data was verified

    @property
    def is_stale(self) -> bool:
        """Check if company data may be outdated (>1 year old)."""
        if not self.verified_date:
            return True
        from datetime import datetime, timedelta
        verified = datetime.fromisoformat(self.verified_date)
        return datetime.now() - verified > timedelta(days=365)


class CompanyRegistry:
    """
    Registry of real companies for prompt grounding.

    Uses external YAML config for easy updates.
    Falls back to generic descriptions when company unavailable.
    """

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._companies = None

    def load(self) -> dict[str, dict[str, list[Company]]]:
        """Load companies from YAML config."""
        if self._companies is None:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    data = yaml.safe_load(f)
                self._companies = self._parse_companies(data)
            else:
                # Generate default company list
                self._companies = self._generate_defaults()
        return self._companies

    def get_company(
        self,
        naics_sector: str,
        size: str,
        seed: int
    ) -> Company:
        """
        Get a company matching criteria.

        Falls back to:
        1. Same sector, different size
        2. Related sector
        3. Generic company description

        Args:
            naics_sector: 2-digit NAICS sector code
            size: startup/small/medium/large/enterprise
            seed: Random seed for reproducible selection

        Returns:
            Company instance
        """
        rng = random.Random(seed)
        companies = self.load()

        # Try exact match
        if naics_sector in companies and size in companies[naics_sector]:
            candidates = companies[naics_sector][size]
            if candidates:
                return rng.choice(candidates)

        # Fallback 1: Same sector, any size
        if naics_sector in companies:
            all_in_sector = []
            for size_companies in companies[naics_sector].values():
                all_in_sector.extend(size_companies)
            if all_in_sector:
                return rng.choice(all_in_sector)

        # Fallback 2: Generate generic company
        return self._generate_generic(naics_sector, size, seed)

    def _generate_generic(
        self,
        naics_sector: str,
        size: str,
        seed: int
    ) -> Company:
        """Generate a plausible generic company description."""
        sector_names = {
            '11': 'Agriculture',
            '21': 'Mining',
            '22': 'Utilities',
            '23': 'Construction',
            '31': 'Manufacturing',
            '42': 'Wholesale Trade',
            '44': 'Retail Trade',
            '48': 'Transportation',
            '51': 'Information',
            '52': 'Finance',
            '53': 'Real Estate',
            '54': 'Professional Services',
            '55': 'Management',
            '56': 'Administrative Services',
            '61': 'Education',
            '62': 'Healthcare',
            '71': 'Arts & Entertainment',
            '72': 'Accommodation & Food',
            '81': 'Other Services',
            '92': 'Government',
        }

        size_ranges = {
            'startup': '5-20',
            'small': '20-100',
            'medium': '100-500',
            'large': '500-5,000',
            'enterprise': '5,000+',
        }

        industry = sector_names.get(naics_sector[:2], 'Services')
        return Company(
            name=f"[{size.title()} {industry} Company]",
            naics_code=naics_sector,
            industry_name=industry,
            size_category=size,
            employee_range=size_ranges.get(size, '100-500'),
            public_private='private' if size in ['startup', 'small'] else 'varies',
            hq_location='United States',
        )
```

### 2.4 Realistic Name Generator

```python
from dataclasses import dataclass
from typing import Literal
import random

@dataclass
class PersonName:
    """A realistic person name with demographics."""
    first_name: str
    last_name: str
    full_name: str
    email_username: str  # e.g., 'sarah.chen'
    generation: Literal['GenZ', 'Millennial', 'GenX', 'Boomer']
    gender_presentation: str  # For analysis, not assumptions
    ethnicity_indicator: str  # For diversity tracking

    def format_email(self, domain: str) -> str:
        return f"{self.email_username}@{domain}"

    def format_formal(self, title: str = None) -> str:
        if title:
            return f"{title} {self.last_name}"
        return f"{self.first_name} {self.last_name}"


class NameGenerator:
    """
    Generate demographically diverse realistic names.

    Uses census data distributions for authenticity.
    Tracks generation demographics for bias analysis.
    """

    # First names by approximate generation and demographic
    # Based on US Census and SSA data
    FIRST_NAMES = {
        'GenZ': {
            'M': ['Liam', 'Noah', 'Ethan', 'Mason', 'Aiden', 'Lucas', 'Jayden',
                  'Mateo', 'Kai', 'Santiago'],
            'F': ['Emma', 'Olivia', 'Ava', 'Isabella', 'Sophia', 'Mia',
                  'Luna', 'Camila', 'Aria', 'Aaliyah'],
        },
        'Millennial': {
            'M': ['Michael', 'Christopher', 'Matthew', 'Joshua', 'David',
                  'Andrew', 'Daniel', 'Justin', 'Kevin', 'Brandon'],
            'F': ['Jessica', 'Ashley', 'Jennifer', 'Amanda', 'Sarah',
                  'Stephanie', 'Nicole', 'Elizabeth', 'Brittany', 'Megan'],
        },
        'GenX': {
            'M': ['Jason', 'Brian', 'Eric', 'Scott', 'Jeffrey', 'Todd',
                  'Mark', 'Steven', 'Timothy', 'Kenneth'],
            'F': ['Michelle', 'Lisa', 'Kimberly', 'Angela', 'Heather',
                  'Amy', 'Christine', 'Melissa', 'Tammy', 'Tracy'],
        },
        'Boomer': {
            'M': ['Robert', 'James', 'John', 'William', 'Richard', 'David',
                  'Thomas', 'Charles', 'Gary', 'Larry'],
            'F': ['Mary', 'Patricia', 'Linda', 'Barbara', 'Susan', 'Karen',
                  'Nancy', 'Betty', 'Dorothy', 'Sandra'],
        },
    }

    # Last names with ethnic diversity indicators
    # Based on US Census surname distributions
    LAST_NAMES = [
        ('Smith', 'Anglo'),
        ('Johnson', 'Anglo'),
        ('Williams', 'Anglo/African-American'),
        ('Brown', 'Anglo/African-American'),
        ('Garcia', 'Hispanic'),
        ('Martinez', 'Hispanic'),
        ('Rodriguez', 'Hispanic'),
        ('Lee', 'Asian'),
        ('Chen', 'Asian'),
        ('Kim', 'Asian'),
        ('Patel', 'South Asian'),
        ('Nguyen', 'Vietnamese'),
        ('Washington', 'African-American'),
        ('Jackson', 'African-American'),
        ('Thompson', 'Anglo'),
        ('White', 'Anglo'),
        ('Lopez', 'Hispanic'),
        ('Gonzalez', 'Hispanic'),
        ('Wilson', 'Anglo'),
        ('Anderson', 'Scandinavian'),
        ('Thomas', 'Anglo'),
        ('Taylor', 'Anglo'),
        ('Moore', 'Anglo/African-American'),
        ('Davis', 'Anglo/African-American'),
        ('Miller', 'Anglo'),
    ]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def generate(
        self,
        generation: str = None,
        gender: str = None,
    ) -> PersonName:
        """
        Generate a realistic name.

        Args:
            generation: Specific generation or None for random
            gender: 'M', 'F', or None for random

        Returns:
            PersonName with full details
        """
        if generation is None:
            # Weighted toward working-age generations
            generation = self.rng.choices(
                ['GenZ', 'Millennial', 'GenX', 'Boomer'],
                weights=[15, 35, 30, 20],
            )[0]

        if gender is None:
            gender = self.rng.choice(['M', 'F'])

        first_name = self.rng.choice(self.FIRST_NAMES[generation][gender])
        last_name, ethnicity = self.rng.choice(self.LAST_NAMES)

        email_username = f"{first_name.lower()}.{last_name.lower()}"

        return PersonName(
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            email_username=email_username,
            generation=generation,
            gender_presentation=gender,
            ethnicity_indicator=ethnicity,
        )

    def generate_batch(
        self,
        n: int,
        ensure_diversity: bool = True,
    ) -> list[PersonName]:
        """Generate n names with demographic diversity."""
        names = []

        if ensure_diversity:
            # Ensure representation across generations and genders
            for gen in self.FIRST_NAMES:
                for gender in ['M', 'F']:
                    count = max(1, n // 8)  # At least 1 per category
                    for _ in range(count):
                        if len(names) < n:
                            names.append(self.generate(gen, gender))

        # Fill remainder randomly
        while len(names) < n:
            names.append(self.generate())

        self.rng.shuffle(names)
        return names[:n]
```

### 2.5 Sensitive Topic Detector

```python
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class SensitivityClassification:
    """Classification of prompt sensitivity."""
    is_sensitive: bool
    category: Optional[str]  # HR, legal, bad_news, confidential, conflict
    confidence: float
    triggers: list[str]  # What triggered the classification

SENSITIVITY_PATTERNS = {
    'hr_issues': [
        r'\b(termination|terminate|fired|firing|dismiss)\b',
        r'\b(performance\s+(review|issue|problem|improvement))\b',
        r'\b(harassment|discrimination|complaint)\b',
        r'\b(warning|probation|disciplinary)\b',
        r'\b(layoff|reduction\s+in\s+force|rif)\b',
    ],
    'legal': [
        r'\b(contract|agreement|lawsuit|litigation)\b',
        r'\b(liability|negligence|breach)\b',
        r'\b(compliance|violation|regulatory)\b',
        r'\b(settlement|damages|indemnif)\b',
    ],
    'bad_news': [
        r'\b(reject|rejection|denied|decline)\b',
        r'\b(cancel|cancellation|discontinue)\b',
        r'\b(delay|postpone|defer)\b',
        r'\b(price\s+increase|rate\s+change)\b',
        r'\b(sorry\s+to\s+inform|regret\s+to)\b',
    ],
    'confidential': [
        r'\b(confidential|proprietary|trade\s+secret)\b',
        r'\b(merger|acquisition|m&a)\b',
        r'\b(financial\s+results?|earnings)\b',
        r'\b(non-?disclosure|nda)\b',
    ],
    'conflict': [
        r'\b(dispute|disagreement|conflict)\b',
        r'\b(complaint|grievance)\b',
        r'\b(negotiate|negotiation)\b',
        r'\b(mediat|arbitrat)\b',
    ],
}


class SensitiveTopicDetector:
    """Detect and classify sensitive topics in prompts."""

    def __init__(self):
        self.compiled_patterns = {
            category: [re.compile(p, re.IGNORECASE) for p in patterns]
            for category, patterns in SENSITIVITY_PATTERNS.items()
        }

    def classify(self, text: str) -> SensitivityClassification:
        """
        Classify text for sensitive topics.

        Returns classification with category and confidence.
        """
        triggers = []
        category_scores = {}

        for category, patterns in self.compiled_patterns.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(text)
                matches.extend(found)

            if matches:
                category_scores[category] = len(matches)
                triggers.extend(matches[:3])  # Limit trigger examples

        if not category_scores:
            return SensitivityClassification(
                is_sensitive=False,
                category=None,
                confidence=0.0,
                triggers=[],
            )

        # Pick category with most matches
        top_category = max(category_scores, key=category_scores.get)
        confidence = min(1.0, category_scores[top_category] / 3)

        return SensitivityClassification(
            is_sensitive=True,
            category=top_category,
            confidence=confidence,
            triggers=list(set(triggers))[:5],
        )
```

---

## 3. PROMPT GENERATION (THREE-PHASE)

### 3.1 Prompt Schema (Complete)

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import date
from enum import Enum

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

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CELEBRATION = "celebration"
    CRISIS = "crisis"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"

class AudienceSize(str, Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class WriterPersona(BaseModel):
    """The person writing the content."""
    name: str
    email: Optional[str] = None
    age: int = Field(ge=18, le=75)
    generation: Literal['GenZ', 'Millennial', 'GenX', 'Boomer']
    job_title: str
    years_experience: int = Field(ge=0, le=50)
    skill_level: Literal['junior', 'mid', 'senior', 'executive']
    english_variant: EnglishVariant = EnglishVariant.EN_US

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v

class RecipientPersona(BaseModel):
    """The intended reader of the content."""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship_to_writer: Literal[
        'manager', 'peer', 'direct_report', 'external_client',
        'external_vendor', 'unknown', 'public'
    ]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    prior_contact: bool = True
    technical_level: Literal['non_technical', 'some_technical', 'highly_technical'] = 'some_technical'

class CompanyContext(BaseModel):
    """Company grounding for the scenario."""
    name: str
    industry_naics: str
    industry_name: str
    size_category: Literal['startup', 'small', 'medium', 'large', 'enterprise']
    employee_count_range: str
    public_private: str
    hq_location: str
    is_real_company: bool = True  # False for generic fallbacks

class AttachmentContext(BaseModel):
    """Mock attachment or referenced content."""
    attachment_type: Literal[
        'report', 'email_thread', 'meeting_notes', 'resume',
        'proposal', 'contract', 'data_table', 'presentation'
    ]
    summary: str
    key_points: list[str]
    raw_content: Optional[str] = None  # For reply-to scenarios

class TemporalContext(BaseModel):
    """Time-sensitive information."""
    current_date: date
    deadline: Optional[str] = None
    recent_event: Optional[str] = None
    quarter: Optional[str] = None

class ExplicitConstraint(BaseModel):
    """An explicit instruction to follow."""
    constraint_type: Literal[
        'length_max', 'length_min', 'format', 'tone',
        'exclusion', 'inclusion', 'structure'
    ]
    description: str
    checkable: bool = True  # Can we verify compliance?
    check_method: Optional[str] = None  # How to verify

class CompetingObjective(BaseModel):
    """A tension between goals."""
    objective_a: str
    objective_b: str
    description: str  # e.g., "Be brief but comprehensive"

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
    urgency: Literal['routine', 'time_sensitive', 'urgent', 'critical']
    emotional_context: EmotionalContext
    audience_size: AudienceSize
    message_position: MessagePosition
    communication_medium: str

    # Additional context (optional)
    attachments: list[AttachmentContext] = []
    temporal_context: Optional[TemporalContext] = None
    prior_message: Optional[str] = None
    tone_example: Optional[str] = None

    # Constraints and objectives
    explicit_constraints: list[ExplicitConstraint] = []
    competing_objectives: list[CompetingObjective] = []

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    job_zone: int = Field(ge=1, le=5)

    # Flags
    is_sensitive: bool = False
    sensitive_category: Optional[str] = None
    is_revision_task: bool = False
    is_ambiguous: bool = False
    has_instruction_constraints: bool = False

    # Generation metadata
    generation_phase: int = Field(ge=1, le=3)
    generation_model: Optional[str] = None
    generation_seed: int

    def model_post_init(self, __context):
        """Set derived flags."""
        self.has_instruction_constraints = len(self.explicit_constraints) > 0
```

### 3.2 Phase 1: Offline Persona Generation (IMPROVED)

**Critical improvement**: Use a dedicated model NOT in the evaluation set to avoid circular bias.

```python
from pathlib import Path
import json
import asyncio
from typing import Optional

class PersonaDatabaseBuilder:
    """
    Build persona database using a dedicated enrichment model.

    IMPORTANT: The enrichment model should NOT be one of the models
    being evaluated to avoid circular bias.
    """

    # Use a capable model that is NOT in the evaluation set
    ENRICHMENT_MODEL = "anthropic/claude-3-5-sonnet"  # Not evaluated

    PERSONA_GENERATION_PROMPT = '''
You are generating diverse writer personas for a professional writing evaluation.

Occupation: {occupation_title}
Job Zone: {job_zone} (1=entry level, 5=expert)
Typical Tasks: {sample_tasks}

Generate {n_personas} diverse personas who would realistically hold this job.

Requirements:
- Vary ages realistically for this occupation (entry-level jobs skew younger)
- Include all generations where realistic (GenZ, Millennial, GenX, Boomer)
- Vary skill levels (junior to senior/executive as appropriate)
- Use demographically diverse names (see US Census data)
- Include realistic email username formats

Return JSON array:
[
    {{
        "name": "First Last",
        "email_username": "first.last",
        "age": 32,
        "generation": "Millennial",
        "years_experience": 8,
        "skill_level": "senior",
        "typical_communication_style": "concise, action-oriented"
    }},
    ...
]
'''

    def __init__(
        self,
        api_client,
        output_dir: Path,
    ):
        self.api_client = api_client
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def build_database(
        self,
        occupations: list[dict],
        personas_per_occupation: int = 10,
    ) -> Path:
        """
        Generate persona database for all occupations.

        Returns path to the generated database file.
        """
        all_personas = {}

        # Batch occupations to avoid rate limits
        batch_size = 5
        for i in range(0, len(occupations), batch_size):
            batch = occupations[i:i + batch_size]

            tasks = [
                self._generate_for_occupation(occ, personas_per_occupation)
                for occ in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for occ, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"Failed for {occ['title']}: {result}")
                    continue
                all_personas[occ['soc_code']] = result

            # Save incrementally
            self._save_checkpoint(all_personas)

        # Save final database
        db_path = self.output_dir / "personas.json"
        with open(db_path, 'w') as f:
            json.dump(all_personas, f, indent=2)

        return db_path

    async def _generate_for_occupation(
        self,
        occupation: dict,
        n_personas: int,
    ) -> list[dict]:
        """Generate personas for a single occupation."""
        prompt = self.PERSONA_GENERATION_PROMPT.format(
            occupation_title=occupation['title'],
            job_zone=occupation.get('job_zone', 3),
            sample_tasks=occupation.get('sample_tasks', 'Various professional tasks'),
            n_personas=n_personas,
        )

        response = await self.api_client.generate(
            model=self.ENRICHMENT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,  # Some creativity
        )

        # Parse JSON from response
        return self._parse_personas(response.content)

    def _parse_personas(self, content: str) -> list[dict]:
        """Robustly extract JSON from LLM response."""
        # Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON array from markdown
        import re
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return empty on failure
        return []
```

### 3.3 Phase 2: Algorithmic Combination (Deterministic)

```python
import hashlib
from dataclasses import dataclass
from typing import Optional

@dataclass
class CombinationContext:
    """All elements needed for combination."""
    task: ONetTask
    persona_db: dict
    company_registry: CompanyRegistry
    name_generator: NameGenerator
    sensitive_detector: SensitiveTopicDetector
    seed: int


class AlgorithmicCombiner:
    """
    Deterministically combine O*NET tasks with personas and context.

    All randomness is derived from the seed for reproducibility.
    """

    def __init__(self, context: CombinationContext):
        self.ctx = context
        self.rng = random.Random(context.seed)

    def combine(self, task: ONetTask) -> WritingPrompt:
        """Create a complete prompt from a task."""
        # Generate deterministic seed for this task
        task_seed = self._derive_seed(task.task_id)

        # Select writer persona
        writer = self._select_writer(task, task_seed)

        # Infer and select recipients
        recipients = self._select_recipients(task, task_seed + 1)

        # Select company
        company = self._select_company(task, task_seed + 2)

        # Determine communication characteristics
        formality = self._determine_formality(task, writer)
        medium = self._infer_medium(task)
        urgency = self._determine_urgency(task, task_seed + 3)
        emotional_context = self._determine_emotional_context(task)
        audience_size = self._infer_audience_size(task, recipients)
        message_position = self._determine_message_position(task, task_seed + 4)

        # Check for sensitivity
        sensitivity = self.ctx.sensitive_detector.classify(task.task_statement)

        # Build prompt text
        prompt_text = self._build_prompt_text(
            task, writer, recipients, company, formality, medium
        )

        # Determine if needs Phase 3 enrichment
        needs_enrichment = self._needs_enrichment(task, prompt_text)

        return WritingPrompt(
            prompt_id=self._generate_prompt_id(task, task_seed),
            onet_task_id=task.task_id,
            onet_soc_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            original_task=task.task_statement,
            prompt_text=prompt_text,
            writer=writer,
            recipients=recipients,
            company=company,
            formality=formality,
            urgency=urgency,
            emotional_context=emotional_context,
            audience_size=audience_size,
            message_position=message_position,
            communication_medium=medium,
            job_zone=task.job_zone,
            is_sensitive=sensitivity.is_sensitive,
            sensitive_category=sensitivity.category,
            generation_phase=2 if not needs_enrichment else 2,  # Mark for Phase 3
            generation_seed=task_seed,
        )

    def _derive_seed(self, task_id: str) -> int:
        """Derive deterministic seed from task ID and base seed."""
        combined = f"{self.ctx.seed}:{task_id}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        return int.from_bytes(hash_bytes[:4], 'big')

    def _select_writer(self, task: ONetTask, seed: int) -> WriterPersona:
        """Select appropriate writer persona for task."""
        rng = random.Random(seed)

        # Check persona database for this occupation
        personas = self.ctx.persona_db.get(task.onetsoc_code, [])

        if personas:
            persona_data = rng.choice(personas)
            name_parts = persona_data['name'].split()
            return WriterPersona(
                name=persona_data['name'],
                email=f"{persona_data.get('email_username', name_parts[0].lower())}@{self._company_domain(task)}",
                age=persona_data.get('age', 35),
                generation=persona_data.get('generation', 'Millennial'),
                job_title=task.occupation_title,
                years_experience=persona_data.get('years_experience', 5),
                skill_level=persona_data.get('skill_level', 'mid'),
            )

        # Fallback: generate name based on job zone
        generated_name = self.ctx.name_generator.generate()
        skill_level = self._job_zone_to_skill(task.job_zone)

        return WriterPersona(
            name=generated_name.full_name,
            email=f"{generated_name.email_username}@company.com",
            age=self._skill_to_typical_age(skill_level, rng),
            generation=generated_name.generation,
            job_title=task.occupation_title,
            years_experience=self._skill_to_experience(skill_level, rng),
            skill_level=skill_level,
        )

    def _infer_medium(self, task: ONetTask) -> str:
        """Infer communication medium from task statement."""
        text = task.task_statement.lower()

        patterns = [
            ('email', ['email', 'e-mail', 'correspond']),
            ('memo', ['memo', 'memorand']),
            ('report', ['report', 'analysis', 'summary', 'findings']),
            ('letter', ['letter', 'formal correspondence']),
            ('presentation', ['present', 'brief', 'pitch']),
            ('proposal', ['proposal', 'recommend']),
            ('policy', ['policy', 'procedure', 'guideline']),
            ('documentation', ['document', 'manual', 'guide']),
            ('slack_message', ['message', 'notify', 'inform']),
        ]

        for medium, keywords in patterns:
            if any(kw in text for kw in keywords):
                return medium

        # Default based on job zone
        if task.job_zone >= 4:
            return 'email'  # Professional default
        return 'slack_message'  # Casual default

    def _determine_formality(
        self,
        task: ONetTask,
        writer: WriterPersona
    ) -> FormalityLevel:
        """Determine appropriate formality level."""
        # Base on job zone
        base_formality = {
            1: FormalityLevel.CASUAL,
            2: FormalityLevel.CASUAL,
            3: FormalityLevel.STANDARD,
            4: FormalityLevel.FORMAL,
            5: FormalityLevel.HIGHLY_FORMAL,
        }.get(task.job_zone, FormalityLevel.STANDARD)

        # Adjust for writer generation (younger tends more casual)
        if writer.generation == 'GenZ' and base_formality != FormalityLevel.HIGHLY_FORMAL:
            base_idx = list(FormalityLevel).index(base_formality)
            base_formality = list(FormalityLevel)[max(0, base_idx - 1)]

        return base_formality

    def _needs_enrichment(self, task: ONetTask, prompt_text: str) -> bool:
        """Determine if this prompt needs Phase 3 LLM enrichment."""
        enrichment_triggers = [
            'attached', 'enclosed', 'see below', 'per our',
            'following up', 'as discussed', 'meeting notes',
            'review the', 'based on', 'resume', 'application',
        ]

        text = f"{task.task_statement} {prompt_text}".lower()
        return any(trigger in text for trigger in enrichment_triggers)

    def _build_prompt_text(
        self,
        task: ONetTask,
        writer: WriterPersona,
        recipients: list[RecipientPersona],
        company: CompanyContext,
        formality: FormalityLevel,
        medium: str,
    ) -> str:
        """Build the actual prompt text for the model."""
        recipient_names = ", ".join(r.name for r in recipients[:2])
        if len(recipients) > 2:
            recipient_names += f" and {len(recipients) - 2} others"

        prompt = f"""You are {writer.name}, {writer.job_title} at {company.name}.

{task.task_statement}

Write {self._medium_description(medium)} to {recipient_names}.

Context:
- Your experience level: {writer.skill_level} ({writer.years_experience} years)
- Recipient(s): {self._describe_recipients(recipients)}
- Company: {company.name} ({company.industry_name}, {company.size_category})
- Formality: {formality.value.replace('_', ' ')}
"""
        return prompt

    def _medium_description(self, medium: str) -> str:
        """Convert medium to natural description."""
        descriptions = {
            'email': 'an email',
            'memo': 'a memo',
            'report': 'a report',
            'letter': 'a formal letter',
            'presentation': 'presentation content',
            'proposal': 'a proposal',
            'slack_message': 'a Slack message',
            'documentation': 'documentation',
        }
        return descriptions.get(medium, 'professional communication')
```

### 3.4 Phase 3: LLM Enrichment with Robust Parsing

```python
class ContextEnricher:
    """
    Enrich prompts with LLM-generated context.

    Handles attachments, prior messages, and complex scenarios.
    """

    # Use same enrichment model as Phase 1
    ENRICHMENT_MODEL = "anthropic/claude-3-5-sonnet"

    ATTACHMENT_PROMPT = '''
Generate realistic mock content for a professional writing task.

Context:
- Writer: {writer_name}, {writer_title} at {company_name}
- Recipient: {recipient_name}, {recipient_title}
- Task: {task_description}
- Attachment type needed: {attachment_type}

Generate realistic {attachment_type} content that would be attached to or referenced in this communication.

Return JSON:
{{
    "summary": "Brief summary of the attachment",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "raw_content": "The actual content if it's a short document like an email thread"
}}
'''

    PRIOR_MESSAGE_PROMPT = '''
Generate a realistic prior message that requires a response.

Context:
- Original sender: {sender_name}, {sender_title}
- Will reply: {responder_name}, {responder_title}
- Topic: {topic}
- Tone: {tone}

Generate the message that requires a response. Make it realistic - include typical email quirks, typos are OK, appropriate formality for the relationship.

Return the message content only, no JSON wrapper.
'''

    def __init__(self, api_client):
        self.api_client = api_client

    async def enrich(self, prompt: WritingPrompt) -> WritingPrompt:
        """Add LLM-generated context to prompt."""
        enriched = prompt.model_copy()

        # Add attachments if needed
        if self._needs_attachment(prompt):
            attachment = await self._generate_attachment(prompt)
            if attachment:
                enriched.attachments.append(attachment)

        # Add prior message for reply scenarios
        if prompt.message_position in [MessagePosition.REPLY, MessagePosition.FOLLOW_UP]:
            prior = await self._generate_prior_message(prompt)
            if prior:
                enriched.prior_message = prior

        # Add temporal context if task is time-sensitive
        if prompt.urgency in ['urgent', 'critical', 'time_sensitive']:
            enriched.temporal_context = self._generate_temporal_context(prompt)

        enriched.generation_phase = 3
        enriched.generation_model = self.ENRICHMENT_MODEL
        return enriched

    async def _generate_attachment(self, prompt: WritingPrompt) -> Optional[AttachmentContext]:
        """Generate mock attachment content."""
        attachment_type = self._infer_attachment_type(prompt)
        if not attachment_type:
            return None

        formatted = self.ATTACHMENT_PROMPT.format(
            writer_name=prompt.writer.name,
            writer_title=prompt.writer.job_title,
            company_name=prompt.company.name,
            recipient_name=prompt.recipients[0].name if prompt.recipients else "colleague",
            recipient_title=prompt.recipients[0].job_title if prompt.recipients else "",
            task_description=prompt.original_task,
            attachment_type=attachment_type,
        )

        try:
            response = await self.api_client.generate(
                model=self.ENRICHMENT_MODEL,
                messages=[{"role": "user", "content": formatted}],
                temperature=0.7,
            )
            data = self._parse_json_response(response.content)

            return AttachmentContext(
                attachment_type=attachment_type,
                summary=data.get('summary', ''),
                key_points=data.get('key_points', []),
                raw_content=data.get('raw_content'),
            )
        except Exception as e:
            # Log but don't fail - enrichment is optional
            print(f"Attachment generation failed: {e}")
            return None

    def _parse_json_response(self, content: str) -> dict:
        """Robustly parse JSON from LLM response."""
        import re

        # Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Extract JSON object from markdown/text
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # Markdown code block
            r'```\s*([\s\S]*?)\s*```',       # Generic code block
            r'\{[\s\S]*\}',                   # Raw JSON object
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group()
                    return json.loads(json_str)
                except (json.JSONDecodeError, IndexError):
                    continue

        # Return empty dict on failure
        return {}

    def _infer_attachment_type(self, prompt: WritingPrompt) -> Optional[str]:
        """Infer what type of attachment is needed."""
        text = prompt.original_task.lower()

        type_patterns = [
            ('report', ['report', 'analysis', 'findings', 'data']),
            ('email_thread', ['reply', 'respond', 'following up', 'thread']),
            ('meeting_notes', ['meeting', 'discussed', 'call']),
            ('resume', ['resume', 'candidate', 'applicant', 'application']),
            ('proposal', ['proposal', 'quote', 'estimate']),
            ('contract', ['contract', 'agreement', 'terms']),
        ]

        for att_type, keywords in type_patterns:
            if any(kw in text for kw in keywords):
                return att_type

        return None
```

### 3.5 Constraint and Ambiguity Generator

```python
class ConstraintGenerator:
    """Generate instruction-following constraints for some prompts."""

    LENGTH_CONSTRAINTS = [
        ExplicitConstraint(
            constraint_type='length_max',
            description='Keep this under 100 words.',
            check_method='word_count < 100',
        ),
        ExplicitConstraint(
            constraint_type='length_max',
            description='Be concise - maximum 3 sentences.',
            check_method='sentence_count <= 3',
        ),
        ExplicitConstraint(
            constraint_type='length_min',
            description='This should be comprehensive, at least 300 words.',
            check_method='word_count >= 300',
        ),
    ]

    FORMAT_CONSTRAINTS = [
        ExplicitConstraint(
            constraint_type='format',
            description='Use exactly 3 bullet points.',
            check_method='bullet_count == 3',
        ),
        ExplicitConstraint(
            constraint_type='format',
            description='Write in paragraph form only - no bullet points or lists.',
            check_method='bullet_count == 0',
        ),
        ExplicitConstraint(
            constraint_type='structure',
            description='Include a clear subject line.',
            check_method='has_subject_line',
        ),
    ]

    TONE_CONSTRAINTS = [
        ExplicitConstraint(
            constraint_type='tone',
            description='Be direct and avoid pleasantries.',
            checkable=False,  # Requires human judgment
        ),
        ExplicitConstraint(
            constraint_type='tone',
            description='Use a warm, encouraging tone.',
            checkable=False,
        ),
    ]

    EXCLUSION_CONSTRAINTS = [
        ExplicitConstraint(
            constraint_type='exclusion',
            description='Do not mention the budget.',
            check_method='budget_not_mentioned',
        ),
        ExplicitConstraint(
            constraint_type='exclusion',
            description='Avoid technical jargon.',
            checkable=False,
        ),
    ]

    def add_constraint(
        self,
        prompt: WritingPrompt,
        seed: int,
        probability: float = 0.2,  # 20% of prompts get constraints
    ) -> WritingPrompt:
        """Optionally add constraint to prompt."""
        rng = random.Random(seed)

        if rng.random() > probability:
            return prompt

        # Select constraint type
        all_constraints = (
            self.LENGTH_CONSTRAINTS +
            self.FORMAT_CONSTRAINTS +
            self.TONE_CONSTRAINTS +
            self.EXCLUSION_CONSTRAINTS
        )

        constraint = rng.choice(all_constraints)

        # Add to prompt
        enriched = prompt.model_copy()
        enriched.explicit_constraints.append(constraint)
        enriched.prompt_text += f"\n\nIMPORTANT: {constraint.description}"

        return enriched


class AmbiguityGenerator:
    """Generate deliberately vague prompts for testing ambiguity handling."""

    AMBIGUOUS_TEMPLATES = [
        "Write to the team about the project.",
        "Follow up on our conversation.",
        "Put together something for the client.",
        "Send an update on the situation.",
        "Draft a response to the feedback.",
    ]

    def create_ambiguous_prompt(
        self,
        task: ONetTask,
        writer: WriterPersona,
        company: CompanyContext,
        seed: int,
    ) -> WritingPrompt:
        """Create a deliberately vague prompt."""
        rng = random.Random(seed)
        template = rng.choice(self.AMBIGUOUS_TEMPLATES)

        return WritingPrompt(
            prompt_id=f"ambig_{task.task_id}_{seed}",
            onet_task_id=task.task_id,
            onet_soc_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            original_task=task.task_statement,
            prompt_text=f"You are {writer.name}, {writer.job_title} at {company.name}.\n\n{template}",
            writer=writer,
            recipients=[],  # Deliberately unspecified
            company=company,
            formality=FormalityLevel.STANDARD,
            urgency='routine',
            emotional_context=EmotionalContext.ROUTINE,
            audience_size=AudienceSize.ONE_ON_ONE,
            message_position=MessagePosition.INITIAL,
            communication_medium='email',
            job_zone=task.job_zone,
            is_ambiguous=True,
            generation_phase=2,
            generation_seed=seed,
        )
```

---

## 4. EVALUATION ENGINE (IMPROVED)

### 4.1 OpenRouter Client with Model Verification

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class GenerationResult:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: int


class OpenRouterClient:
    """
    OpenRouter API client with verification, retry, and rate limiting.

    CRITICAL: Verifies model availability before evaluation starts.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self._verified_models: set[str] = set()
        self._rate_limiters: dict[str, asyncio.Semaphore] = {}

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://gemini-eval.internal",
            },
            timeout=timeout,
        )

    async def verify_models(self, model_ids: list[str]) -> dict[str, bool]:
        """
        Verify which models are available on OpenRouter.

        Returns dict of model_id -> is_available.
        """
        # Fetch available models
        response = await self.client.get("/models")
        response.raise_for_status()

        available = {m['id'] for m in response.json()['data']}

        results = {}
        for model_id in model_ids:
            is_available = model_id in available
            results[model_id] = is_available
            if is_available:
                self._verified_models.add(model_id)

        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
    )
    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        """Generate completion with retry logic."""
        if model not in self._verified_models:
            raise ValueError(f"Model {model} not verified. Call verify_models first.")

        # Acquire rate limit
        semaphore = self._get_rate_limiter(model)
        async with semaphore:
            start = asyncio.get_event_loop().time()

            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )

            elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)

            if response.status_code == 429:
                # Rate limited - extract retry-after and raise for retry
                retry_after = int(response.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after)
                raise httpx.HTTPStatusError(
                    "Rate limited",
                    request=response.request,
                    response=response,
                )

            response.raise_for_status()
            data = response.json()

            return GenerationResult(
                content=data["choices"][0]["message"]["content"],
                input_tokens=data["usage"]["prompt_tokens"],
                output_tokens=data["usage"]["completion_tokens"],
                model=model,
                latency_ms=elapsed_ms,
            )

    def _get_rate_limiter(self, model: str) -> asyncio.Semaphore:
        """Get or create rate limiter for model."""
        if model not in self._rate_limiters:
            # Default: 10 concurrent requests per model
            self._rate_limiters[model] = asyncio.Semaphore(10)
        return self._rate_limiters[model]

    async def close(self):
        await self.client.aclose()
```

### 4.2 Model Configuration (External YAML)

```yaml
# config/models.yaml
# Model configuration - update these IDs as OpenRouter changes

pro_tier:
  gemini:
    name: "Gemini 3.0 Pro"
    openrouter_id: "google/gemini-pro"  # UPDATE if changed
    input_price_per_1m: 2.50
    output_price_per_1m: 10.00

  competitors:
    - name: "GPT-4 Turbo"
      openrouter_id: "openai/gpt-4-turbo"  # UPDATE if changed
      input_price_per_1m: 10.00
      output_price_per_1m: 30.00

    - name: "Claude 3.5 Opus"
      openrouter_id: "anthropic/claude-3-5-opus-20241022"  # UPDATE if changed
      input_price_per_1m: 15.00
      output_price_per_1m: 75.00

flash_tier:
  gemini:
    name: "Gemini 3.0 Flash"
    openrouter_id: "google/gemini-flash"  # UPDATE if changed
    input_price_per_1m: 0.075
    output_price_per_1m: 0.30

  competitors:
    - name: "GPT-4o Mini"
      openrouter_id: "openai/gpt-4o-mini"
      input_price_per_1m: 0.15
      output_price_per_1m: 0.60

    - name: "Claude 3.5 Sonnet"
      openrouter_id: "anthropic/claude-3-5-sonnet-20241022"
      input_price_per_1m: 3.00
      output_price_per_1m: 15.00

judges:
  - name: "Claude 3.5 Opus"
    openrouter_id: "anthropic/claude-3-5-opus-20241022"

  - name: "GPT-4 Turbo"
    openrouter_id: "openai/gpt-4-turbo"

  - name: "Gemini Pro"
    openrouter_id: "google/gemini-pro"

# Model used for prompt enrichment (NOT in evaluation set)
enrichment_model: "anthropic/claude-3-5-sonnet-20241022"
```

### 4.3 Judging System with Robust JSON Parsing

```python
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class JudgmentVote:
    winner: str  # "A", "B", or "Tie"
    confidence: float
    reasoning: str
    criteria_scores: dict[str, dict[str, int]]
    detected_issues: list[str]
    raw_response: str  # Keep original for debugging


class JudgeResponseParser:
    """
    Robust parser for judge responses.

    Handles various LLM response formats and malformed JSON.
    """

    def parse(self, response: str) -> JudgmentVote:
        """
        Parse judge response into structured vote.

        Falls back gracefully if JSON parsing fails.
        """
        # Try structured JSON extraction
        parsed = self._extract_json(response)

        if parsed and 'winner' in parsed:
            return JudgmentVote(
                winner=self._normalize_winner(parsed.get('winner', 'Tie')),
                confidence=float(parsed.get('confidence', 0.5)),
                reasoning=parsed.get('reasoning', ''),
                criteria_scores=parsed.get('criteria_scores', {}),
                detected_issues=parsed.get('detected_issues', []),
                raw_response=response,
            )

        # Fallback: extract winner from text
        winner = self._extract_winner_from_text(response)
        return JudgmentVote(
            winner=winner,
            confidence=0.5,  # Low confidence for fallback
            reasoning=response[:500],  # First 500 chars as reasoning
            criteria_scores={},
            detected_issues=[],
            raw_response=response,
        )

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from various response formats."""
        # Pattern 1: ```json ... ```
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Pattern 2: ``` ... ```
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Pattern 3: Raw JSON object
        match = re.search(r'\{[\s\S]*"winner"[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Pattern 4: Fix common JSON issues and retry
        cleaned = self._fix_common_json_issues(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        return None

    def _fix_common_json_issues(self, text: str) -> str:
        """Fix common LLM JSON generation issues."""
        # Extract just the JSON part
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1:
            return text

        json_str = text[start:end + 1]

        # Fix trailing commas
        json_str = re.sub(r',\s*([\]}])', r'\1', json_str)

        # Fix single quotes to double quotes
        # (Simple version - doesn't handle all edge cases)
        json_str = json_str.replace("'", '"')

        return json_str

    def _normalize_winner(self, winner: str) -> str:
        """Normalize winner value to A, B, or Tie."""
        winner_upper = winner.upper().strip()

        if winner_upper in ['A', 'RESPONSE A', 'OPTION A', '1']:
            return 'A'
        elif winner_upper in ['B', 'RESPONSE B', 'OPTION B', '2']:
            return 'B'
        else:
            return 'Tie'

    def _extract_winner_from_text(self, text: str) -> str:
        """Fallback: extract winner from natural language response."""
        text_lower = text.lower()

        # Strong indicators for A
        a_patterns = [
            r'response a (is )?better',
            r'prefer response a',
            r'winner[:\s]+a',
            r'a is the winner',
            r'response a wins',
        ]
        for pattern in a_patterns:
            if re.search(pattern, text_lower):
                return 'A'

        # Strong indicators for B
        b_patterns = [
            r'response b (is )?better',
            r'prefer response b',
            r'winner[:\s]+b',
            r'b is the winner',
            r'response b wins',
        ]
        for pattern in b_patterns:
            if re.search(pattern, text_lower):
                return 'B'

        # Tie indicators
        tie_patterns = [
            r'tie',
            r'equal',
            r'both (are )?good',
            r'neither (is )?better',
            r'cannot decide',
        ]
        for pattern in tie_patterns:
            if re.search(pattern, text_lower):
                return 'Tie'

        # Default to tie if unclear
        return 'Tie'


class JudgeEngine:
    """
    Execute judging with majority-of-majorities voting.

    Provides full context to judges as required by PROMPT.md.
    """

    WRITING_EXPERT_SYSTEM = """You are an expert writing professional with decades of experience in professional communication.

Your role is to evaluate two written responses to the same task and determine which is better.

Evaluate based on:
- Quality of writing craft (grammar, style, flow)
- Appropriate length for the task (not too long, not too short)
- Tone appropriateness for the context and relationship
- Clarity and structure
- Professionalism
- Authenticity (does it sound like a real person wrote it?)
- Avoidance of AI cliches ("I hope this email finds you well", "Please don't hesitate to reach out", excessive bullet points)

CRITICAL: The writing should be appropriate for the SPECIFIC persona and context. A GenZ startup employee writes differently than a Boomer executive at Fortune 500."""

    RECIPIENT_SYSTEM = """You are the intended recipient of this writing: {recipient_name}, {recipient_title}.

Your relationship to the sender: {relationship}

Evaluate from YOUR perspective as the actual reader:
- Would this communication achieve its purpose for you?
- Is it appropriate for your relationship with the sender?
- Would you find this effective and professional?
- Does it respect your time and give you what you need?
- Does it feel authentic - like a real person wrote it?

Do not evaluate generic "good writing" - evaluate whether THIS message works for YOU in THIS situation."""

    JUDGE_PROMPT = """## Writing Task
{prompt_text}

## Writer Context
- Name: {writer_name}
- Title: {writer_title}
- Company: {company_name} ({company_industry}, {company_size})
- Experience: {writer_experience} years, {writer_skill_level} level
- Generation: {writer_generation} (age {writer_age})

## Recipient Context
- Name: {recipient_name}
- Title: {recipient_title}
- Relationship: {relationship}

## Communication Context
- Formality: {formality}
- Medium: {medium}
- Urgency: {urgency}

## Response A
{response_a}

## Response B
{response_b}

## Your Evaluation
Which response better accomplishes the writing task for this specific scenario?

Respond with JSON:
{{
    "winner": "A" | "B" | "Tie",
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation of your decision...",
    "criteria_scores": {{
        "response_a": {{"quality": 1-5, "tone": 1-5, "clarity": 1-5, "authenticity": 1-5, "length_appropriateness": 1-5}},
        "response_b": {{"quality": 1-5, "tone": 1-5, "clarity": 1-5, "authenticity": 1-5, "length_appropriateness": 1-5}}
    }},
    "detected_issues": ["list any AI cliches, problems, or notable issues in either response"]
}}"""

    def __init__(self, api_client, parser: JudgeResponseParser = None):
        self.api_client = api_client
        self.parser = parser or JudgeResponseParser()

    async def judge_comparison(
        self,
        prompt: WritingPrompt,
        response_a: str,
        response_b: str,
        judge_models: list[str],
        votes_per_judge: int = 5,
        use_both_personas: bool = True,
    ) -> dict:
        """Execute full judging pipeline."""
        results = []

        personas = ['writing_expert']
        if use_both_personas and prompt.recipients:
            personas.append('recipient')

        for judge_model in judge_models:
            for persona in personas:
                # Generate votes (can run in parallel)
                vote_tasks = [
                    self._single_vote(prompt, response_a, response_b, judge_model, persona)
                    for _ in range(votes_per_judge)
                ]
                votes = await asyncio.gather(*vote_tasks, return_exceptions=True)

                # Filter out errors
                valid_votes = [v for v in votes if isinstance(v, JudgmentVote)]

                # Compute majority
                majority = self._compute_majority(valid_votes)

                results.append({
                    'judge_model': judge_model,
                    'persona': persona,
                    'votes': valid_votes,
                    'majority': majority,
                    'vote_distribution': self._vote_distribution(valid_votes),
                })

        # Compute majority of majorities
        final_winner = self._majority_of_majorities(results)

        return {
            'final_winner': final_winner,
            'judge_results': results,
            'agreement': self._compute_agreement(results),
        }

    async def _single_vote(
        self,
        prompt: WritingPrompt,
        response_a: str,
        response_b: str,
        judge_model: str,
        persona: str,
    ) -> JudgmentVote:
        """Get single vote from judge."""
        # Build system prompt based on persona
        if persona == 'writing_expert':
            system = self.WRITING_EXPERT_SYSTEM
        else:
            recipient = prompt.recipients[0] if prompt.recipients else None
            system = self.RECIPIENT_SYSTEM.format(
                recipient_name=recipient.name if recipient else "the recipient",
                recipient_title=recipient.job_title if recipient else "",
                relationship=recipient.relationship_to_writer if recipient else "colleague",
            )

        # Build user prompt with full context
        user_prompt = self.JUDGE_PROMPT.format(
            prompt_text=prompt.prompt_text,
            writer_name=prompt.writer.name,
            writer_title=prompt.writer.job_title,
            company_name=prompt.company.name,
            company_industry=prompt.company.industry_name,
            company_size=prompt.company.size_category,
            writer_experience=prompt.writer.years_experience,
            writer_skill_level=prompt.writer.skill_level,
            writer_generation=prompt.writer.generation,
            writer_age=prompt.writer.age,
            recipient_name=prompt.recipients[0].name if prompt.recipients else "colleague",
            recipient_title=prompt.recipients[0].job_title if prompt.recipients else "",
            relationship=prompt.recipients[0].relationship_to_writer if prompt.recipients else "colleague",
            formality=prompt.formality.value,
            medium=prompt.communication_medium,
            urgency=prompt.urgency,
            response_a=response_a,
            response_b=response_b,
        )

        result = await self.api_client.generate(
            model=judge_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Lower temperature for more consistent judging
        )

        return self.parser.parse(result.content)

    def _compute_majority(self, votes: list[JudgmentVote]) -> str:
        """Compute majority from votes."""
        if not votes:
            return 'Tie'

        counts = {'A': 0, 'B': 0, 'Tie': 0}
        for vote in votes:
            counts[vote.winner] += 1

        if counts['A'] > counts['B']:
            return 'A'
        elif counts['B'] > counts['A']:
            return 'B'
        return 'Tie'

    def _majority_of_majorities(self, results: list[dict]) -> str:
        """Compute final winner from judge majorities."""
        majorities = [r['majority'] for r in results]

        a_count = sum(1 for m in majorities if m == 'A')
        b_count = sum(1 for m in majorities if m == 'B')

        if a_count > b_count:
            return 'A'
        elif b_count > a_count:
            return 'B'
        return 'Tie'
```

### 4.4 Compliance Checker for Instruction-Following

```python
import re

class ComplianceChecker:
    """Check if responses comply with explicit constraints."""

    def check(self, response: str, constraint: ExplicitConstraint) -> dict:
        """
        Check if response complies with constraint.

        Returns dict with 'compliant' bool and 'details'.
        """
        if not constraint.checkable:
            return {'compliant': None, 'details': 'Requires human judgment'}

        method = constraint.check_method
        if not method:
            return {'compliant': None, 'details': 'No check method specified'}

        # Word count checks
        if 'word_count' in method:
            word_count = len(response.split())
            if 'word_count < ' in method:
                limit = int(re.search(r'word_count < (\d+)', method).group(1))
                return {
                    'compliant': word_count < limit,
                    'details': f'Word count: {word_count}, limit: {limit}'
                }
            elif 'word_count >= ' in method:
                limit = int(re.search(r'word_count >= (\d+)', method).group(1))
                return {
                    'compliant': word_count >= limit,
                    'details': f'Word count: {word_count}, minimum: {limit}'
                }

        # Sentence count checks
        if 'sentence_count' in method:
            sentences = len(re.split(r'[.!?]+', response.strip()))
            if 'sentence_count <= ' in method:
                limit = int(re.search(r'sentence_count <= (\d+)', method).group(1))
                return {
                    'compliant': sentences <= limit,
                    'details': f'Sentence count: {sentences}, limit: {limit}'
                }

        # Bullet point checks
        if 'bullet_count' in method:
            bullets = len(re.findall(r'^[\s]*[-*•]\s', response, re.MULTILINE))
            if 'bullet_count == ' in method:
                expected = int(re.search(r'bullet_count == (\d+)', method).group(1))
                return {
                    'compliant': bullets == expected,
                    'details': f'Bullet count: {bullets}, expected: {expected}'
                }

        # Subject line check
        if 'has_subject_line' in method:
            has_subject = bool(re.search(r'^(Subject|Re|Fwd):', response, re.MULTILINE | re.IGNORECASE))
            return {
                'compliant': has_subject,
                'details': f'Has subject line: {has_subject}'
            }

        # Exclusion checks
        if 'budget_not_mentioned' in method:
            mentioned = bool(re.search(r'\bbudget\b', response, re.IGNORECASE))
            return {
                'compliant': not mentioned,
                'details': f'Budget mentioned: {mentioned}'
            }

        return {'compliant': None, 'details': f'Unknown check method: {method}'}
```

---

## 5. STORAGE, CHECKPOINTING, AND ANALYSIS

### 5.1 Improved Database Schema

```sql
-- Run metadata
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    config_json TEXT NOT NULL,
    preset_name TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'interrupted')),
    random_seed INTEGER NOT NULL,
    total_prompts INTEGER NOT NULL,
    completed_prompts INTEGER DEFAULT 0,
    models_verified BOOLEAN DEFAULT FALSE
);

-- Prompts with full metadata
CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    onet_task_id TEXT NOT NULL,
    onet_soc_code TEXT NOT NULL,
    occupation_title TEXT NOT NULL,
    job_zone INTEGER NOT NULL,
    prompt_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexed metadata for filtering
    formality TEXT NOT NULL,
    industry_naics TEXT,
    audience_size TEXT,
    communication_medium TEXT,
    urgency TEXT,
    emotional_context TEXT,

    -- Flags
    is_sensitive BOOLEAN DEFAULT FALSE,
    sensitive_category TEXT,
    is_revision_task BOOLEAN DEFAULT FALSE,
    is_ambiguous BOOLEAN DEFAULT FALSE,
    has_constraints BOOLEAN DEFAULT FALSE,

    -- Generation metadata
    generation_phase INTEGER NOT NULL,
    generation_model TEXT
);

-- Model responses with metadata
CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model_id TEXT NOT NULL,
    model_name TEXT NOT NULL,

    content TEXT,
    refused BOOLEAN DEFAULT FALSE,
    refusal_category TEXT,
    refusal_reason TEXT,

    -- Metrics
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    word_count INTEGER,
    char_count INTEGER,

    -- Format analysis
    has_bullets BOOLEAN,
    bullet_count INTEGER,
    has_headers BOOLEAN,
    paragraph_count INTEGER,

    -- Compliance (for constrained prompts)
    constraint_compliant BOOLEAN,
    constraint_details TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Comparisons
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),

    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    gemini_response_id TEXT REFERENCES responses(response_id),
    competitor_response_id TEXT REFERENCES responses(response_id),

    -- Position randomization
    response_order TEXT NOT NULL CHECK (response_order IN ('gemini_first', 'competitor_first')),
    position_seed INTEGER NOT NULL,

    -- Final result
    final_winner TEXT NOT NULL CHECK (final_winner IN ('gemini', 'competitor', 'tie')),
    final_winner_raw TEXT NOT NULL CHECK (final_winner_raw IN ('A', 'B', 'Tie')),

    -- Agreement metrics
    judge_agreement REAL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual judge votes
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),

    judge_model TEXT NOT NULL,
    judge_persona TEXT NOT NULL CHECK (judge_persona IN ('writing_expert', 'recipient')),
    vote_number INTEGER NOT NULL,

    winner TEXT NOT NULL CHECK (winner IN ('A', 'B', 'Tie')),
    confidence REAL,
    reasoning TEXT,
    criteria_scores_json TEXT,
    detected_issues_json TEXT,

    -- Parsing metadata
    parsed_successfully BOOLEAN DEFAULT TRUE,
    raw_response TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onet_soc_code);
CREATE INDEX idx_prompts_formality ON prompts(formality);
CREATE INDEX idx_prompts_sensitive ON prompts(is_sensitive);
CREATE INDEX idx_comparisons_winner ON comparisons(final_winner);
CREATE INDEX idx_comparisons_models ON comparisons(gemini_model, competitor_model);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);

-- View for analysis queries
CREATE VIEW win_rates_by_dimension AS
SELECT
    p.formality,
    p.job_zone,
    p.industry_naics,
    p.is_sensitive,
    c.gemini_model,
    c.competitor_model,
    COUNT(*) as total,
    SUM(CASE WHEN c.final_winner = 'gemini' THEN 1 ELSE 0 END) as gemini_wins,
    SUM(CASE WHEN c.final_winner = 'competitor' THEN 1 ELSE 0 END) as competitor_wins,
    SUM(CASE WHEN c.final_winner = 'tie' THEN 1 ELSE 0 END) as ties,
    CAST(SUM(CASE WHEN c.final_winner = 'gemini' THEN 1 ELSE 0 END) AS REAL) /
        NULLIF(SUM(CASE WHEN c.final_winner != 'tie' THEN 1 ELSE 0 END), 0) as win_rate
FROM comparisons c
JOIN prompts p ON c.prompt_id = p.prompt_id
GROUP BY p.formality, p.job_zone, p.industry_naics, p.is_sensitive, c.gemini_model, c.competitor_model;
```

### 5.2 Improved Cost Estimator

```python
class AccurateCostEstimator:
    """
    Cost estimator with realistic token counts.

    Uses prompt complexity to estimate tokens more accurately.
    """

    # Token estimation based on prompt characteristics
    TOKEN_ESTIMATES = {
        'simple_prompt': {'input': 400, 'output': 200},
        'standard_prompt': {'input': 800, 'output': 400},
        'complex_prompt': {'input': 1500, 'output': 600},
        'context_heavy': {'input': 2500, 'output': 800},
        'judge_simple': {'input': 1200, 'output': 300},
        'judge_standard': {'input': 2000, 'output': 400},
        'judge_complex': {'input': 3500, 'output': 500},
    }

    def estimate_prompt_tokens(self, prompt: WritingPrompt) -> dict:
        """Estimate tokens for a specific prompt."""
        # Base complexity from prompt characteristics
        if prompt.attachments or prompt.prior_message:
            category = 'context_heavy'
        elif len(prompt.explicit_constraints) > 0 or prompt.competing_objectives:
            category = 'complex_prompt'
        elif prompt.job_zone >= 4:
            category = 'standard_prompt'
        else:
            category = 'simple_prompt'

        return self.TOKEN_ESTIMATES[category]

    def estimate_judge_tokens(self, prompt: WritingPrompt) -> dict:
        """Estimate tokens for judging this prompt."""
        # Judge tokens include two responses
        prompt_tokens = self.estimate_prompt_tokens(prompt)
        estimated_response_len = prompt_tokens['output']

        # Judge prompt = original prompt + 2 responses + judge instructions
        judge_input = prompt_tokens['input'] + (estimated_response_len * 2) + 500

        if judge_input > 3000:
            return self.TOKEN_ESTIMATES['judge_complex']
        elif judge_input > 1500:
            return self.TOKEN_ESTIMATES['judge_standard']
        return self.TOKEN_ESTIMATES['judge_simple']

    def estimate_run(self, config: EvalConfig, prompts: list[WritingPrompt]) -> CostEstimate:
        """Compute detailed cost estimate for a run."""
        response_costs = {}
        judge_costs = {}

        for pair in config.model_pairs:
            gemini_model = config.get_model(pair[0])
            competitor_model = config.get_model(pair[1])

            pair_response_cost = 0
            pair_judge_cost = 0

            for prompt in prompts:
                # Response generation cost
                tokens = self.estimate_prompt_tokens(prompt)

                gemini_cost = (
                    (gemini_model.input_price_per_1m * tokens['input'] / 1_000_000) +
                    (gemini_model.output_price_per_1m * tokens['output'] / 1_000_000)
                )
                competitor_cost = (
                    (competitor_model.input_price_per_1m * tokens['input'] / 1_000_000) +
                    (competitor_model.output_price_per_1m * tokens['output'] / 1_000_000)
                )
                pair_response_cost += gemini_cost + competitor_cost

                # Judge cost
                judge_tokens = self.estimate_judge_tokens(prompt)
                judge_calls = (
                    len(config.judge_models) *
                    config.votes_per_judge *
                    (2 if config.use_both_personas else 1)
                )

                for judge_model_id in config.judge_models:
                    judge_model = config.get_model(judge_model_id)
                    per_call = (
                        (judge_model.input_price_per_1m * judge_tokens['input'] / 1_000_000) +
                        (judge_model.output_price_per_1m * judge_tokens['output'] / 1_000_000)
                    )
                    pair_judge_cost += per_call * config.votes_per_judge * (2 if config.use_both_personas else 1)

            response_costs[f"{pair[0]} vs {pair[1]}"] = pair_response_cost
            judge_costs[f"{pair[0]} vs {pair[1]}"] = pair_judge_cost

        total_response = sum(response_costs.values())
        total_judge = sum(judge_costs.values())

        return CostEstimate(
            response_generation=total_response,
            judging=total_judge,
            total=total_response + total_judge,
            low_estimate=(total_response + total_judge) * 0.8,
            high_estimate=(total_response + total_judge) * 1.3,
            breakdown={
                'response_by_pair': response_costs,
                'judge_by_pair': judge_costs,
            },
            assumptions={
                'avg_prompt_tokens': 'varies by complexity',
                'avg_response_tokens': 'varies by complexity',
                'avg_judge_tokens': 'varies by prompt complexity',
            }
        )
```

---

## 6. IMPLEMENTATION TIMELINE (REVISED)

### Phase 1: Foundation (Week 1-2)
- Project setup with pyproject.toml and dependencies
- External configuration system (YAML model configs)
- OpenRouter client with model verification
- O*NET data loading using reference guide
- Basic prompt schema and validation
- SQLite database schema and migrations

### Phase 2: Prompt Generation (Week 3-4)
- Phase 1: Persona database builder (using non-evaluated model)
- Phase 2: Algorithmic combiner with all diversity dimensions
- Phase 3: Context enricher with robust JSON parsing
- Constraint generator for instruction-following tests
- Ambiguity generator for vague prompt tests
- Sensitive topic detector

### Phase 3: Evaluation Engine (Week 5-6)
- Response generation pipeline with parallel execution
- Judge engine with dual personas
- Robust judge response parsing (handles malformed JSON)
- Majority-of-majorities voting implementation
- Compliance checker for constraint verification
- Refusal categorization

### Phase 4: Robustness (Week 7)
- Checkpoint system with atomic writes
- Graceful shutdown handling
- Resume from checkpoint
- Failure tracking and reporting
- Rate limiting and retry logic

### Phase 5: Analysis & TUI (Week 8-9)
- Statistical analysis (win rates, CI, significance)
- Bias detection (position, length, model)
- Weakness analysis by dimension
- Progress dashboard TUI
- Results viewer TUI
- Cost estimation display

### Phase 6: Reports & Polish (Week 10)
- PDF report generation
- Visualization generation
- Cross-run comparison
- Documentation
- Testing and edge cases

---

## 7. SUCCESS CRITERIA (MEASURABLE)

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Model verification | 100% | All configured models verified available before run |
| Resume capability | 0% data loss | Interrupt at random points, verify resume works |
| Judge parsing | >95% success | Track parse failures, ensure fallback works |
| Position bias | <5% | Statistical test for A vs B preference |
| Inter-judge agreement | Kappa > 0.6 | Cohen's Kappa across judges |
| Cost accuracy | Within 30% | Compare estimate to actual |
| Prompt diversity | Coverage > 80% | All dimensions represented in samples |
| Weakness identification | Top 10 with p<0.05 | Statistical significance for weakness claims |
| Report quality | Executive-ready | PDF with visualizations, narrative, recommendations |
| TUI responsiveness | <100ms update | UI updates during long runs |

---

## 8. RISK MITIGATION (IMPROVED)

| Risk | Impact | Mitigation | Fallback |
|------|--------|------------|----------|
| OpenRouter model changes | High | External YAML config, verify at startup | Notify user, suggest alternatives |
| Judge JSON parsing fails | Medium | Robust parser with 4 fallback patterns | Extract winner from text |
| Cost overruns | High | Accurate estimator, confirmation required | Hard cost limit option |
| Circular bias from enrichment | Medium | Use non-evaluated model for enrichment | Document bias source |
| Long-running interruptions | High | Checkpoint every prompt | Resume exactly where stopped |
| Company data outdated | Low | Fallback to generic descriptions | Track real vs generic |
| O*NET data unavailable | Medium | Reference guide pre-processing | Keyword-based task detection |
| Rate limits | Medium | Per-model rate limiters | Exponential backoff |
| Statistical noise | Medium | Confidence intervals, significance tests | Flag low-confidence results |

---

## 9. KEY IMPROVEMENTS FROM ORIGINAL DRAFT

1. **Model verification at startup** - Don't assume model IDs are correct
2. **External YAML config for models** - Easy to update when OpenRouter changes
3. **Use non-evaluated model for enrichment** - Avoid circular bias
4. **Robust JSON parsing with fallbacks** - Handle malformed judge responses
5. **Accurate token estimation** - Based on prompt complexity, not fixed averages
6. **Read O*NET reference guide** - Use pre-processed task guidance
7. **Company registry with fallbacks** - Gracefully handle missing companies
8. **Constraint compliance checking** - Verify instruction-following
9. **Ambiguity prompt generation** - Test handling of vague prompts
10. **Sensitive topic detection** - Pattern-based classification
11. **Full context to judges** - As required by PROMPT.md
12. **Measurable success criteria** - Clear targets for each requirement
