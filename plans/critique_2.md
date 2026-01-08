# Gemini Writing Evaluation Framework - Improved Implementation Plan

## Critique of Draft Plan 2

Before presenting the improved plan, here are the key issues identified in Draft Plan 2:

### Critical Issues

1. **Missing BLS Data Acquisition Strategy**: The draft assumes `bls_occ_industry_matrix.csv` exists but provides no guidance on how to obtain it. This is a critical external dependency that needs verification and download instructions.

2. **Company Database Source Unspecified**: Claims to have "~5,000+ companies" but doesn't explain where this data comes from. No API or data source is identified. This is a blocker for implementation.

3. **Name Database Source Unspecified**: References "SSA name data and census demographics" but provides no download URLs or integration strategy.

4. **O*NET Element IDs Not Verified**: Uses specific element IDs like '2.A.1.c' and '4.C.1.a.2.h' without verifying they exist in the actual O*NET 30.1 database schema. The ONET_REFERENCE.md should be consulted.

5. **OpenRouter Model Names Unverified**: Uses model identifiers like 'google/gemini-3.0-pro' and 'moonshot/kimi-k2-thinking' without verifying they exist on OpenRouter. These need to be validated against the actual OpenRouter API.

6. **Missing Token Estimation Logic**: The cost estimator uses hardcoded token counts without explaining how prompt complexity affects these estimates.

7. **No Error Recovery for Prompt Generation**: Phase 1-3 prompt generation has no retry logic or error handling for LLM failures during enrichment.

8. **Incomplete Judge Prompt Structure**: The judge prompt template lacks explicit JSON output format enforcement, which can lead to parsing failures.

9. **Missing Parallelization Strategy**: No discussion of concurrency limits, semaphores, or how to prevent rate limiting during parallel API calls.

10. **No Data Validation Pipeline**: Missing validation steps to ensure generated prompts meet diversity requirements before evaluation begins.

### Moderate Issues

11. **Ambiguity Handling Not Implemented**: PROMPT.md requires testing how models handle vague prompts, but the draft has no concrete implementation.

12. **Instruction Constraint Verification Missing**: No mechanism to verify if models followed explicit constraints (word counts, format requirements).

13. **Sensitive Topic Tagging Unclear**: No clear algorithm for automatically tagging sensitive topics during prompt generation.

14. **Regional English Variant Implementation Weak**: Only mentions 90% en-US / 10% international split but no implementation details.

15. **Tone Example Generation Missing**: PROMPT.md requires tone matching examples but the draft doesn't show how to generate them.

---

## Part 1: System Architecture Overview (Revised)

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

### 1.2 Core Components (with Dependencies Verified)

| Component | Responsibility | Key Dependencies | Verification Status |
|-----------|----------------|------------------|---------------------|
| **Orchestrator** | Coordinates all evaluation phases, manages state | All components | Internal |
| **Prompt Pipeline** | Extracts O*NET tasks, generates diverse prompts | O*NET DB (verified: db/onet.db exists) | MUST verify schema |
| **Response Generator** | Sends prompts to models via OpenRouter | OpenRouter API | MUST verify model names |
| **Judge Engine** | Evaluates response pairs with ensemble voting | OpenRouter API | MUST verify model names |
| **Results Store** | Persists all data to SQLite | sqlite3 (stdlib) | OK |
| **TUI Module** | Real-time progress visualization | textual (pypi) | OK |
| **Report Generator** | Produces PDF analysis reports | plotly, reportlab (pypi) | OK |
| **Checkpoint Manager** | Handles pause/resume/crash recovery | Filesystem | OK |

### 1.3 Technology Stack (with Versions)

```toml
# pyproject.toml - verified compatible versions
[project]
requires-python = ">=3.11"

dependencies = [
    # Core - async framework
    "pydantic>=2.5",      # Data validation with strict mode
    "httpx>=0.26",        # Async HTTP client
    "aiosqlite>=0.19",    # Async SQLite
    "tenacity>=8.2",      # Retry logic with backoff

    # CLI
    "typer>=0.9",         # CLI framework
    "rich>=13.7",         # Terminal formatting

    # TUI
    "textual>=0.47",      # Rich TUI framework (latest stable)

    # Data Analysis
    "pandas>=2.1",        # DataFrames
    "numpy>=1.26",        # Numerical
    "scipy>=1.11",        # Statistical tests

    # Visualization
    "plotly>=5.18",       # Interactive charts
    "kaleido>=0.2",       # Plotly static export

    # PDF Generation
    "reportlab>=4.0",     # PDF generation

    # Utilities
    "python-dotenv>=1.0", # Environment config
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
    "mypy>=1.8",
    "ruff>=0.1",
]
```

---

## Part 2: External Data Dependencies (CRITICAL - NEW SECTION)

### 2.1 Required External Data Sources

Before implementation can proceed, these data sources must be acquired and verified:

#### 2.1.1 BLS Occupation-Industry Employment Matrix

**Purpose**: Map O*NET occupations to NAICS industries for realistic industry assignment.

**Official Source**: Bureau of Labor Statistics
- URL: https://www.bls.gov/emp/tables/industry-occupation-matrix.htm
- Format: Excel/CSV files by industry
- Update frequency: Annual

**Acquisition Steps**:
```bash
# Download the matrix (must verify URL is current)
mkdir -p data/bls
curl -o data/bls/industry_occupation_matrix.xlsx \
  "https://www.bls.gov/emp/ind-occ-matrix/ind-occ-matrix.xlsx"

# Convert to CSV for processing
python scripts/convert_bls_matrix.py data/bls/industry_occupation_matrix.xlsx \
  --output data/bls_occ_industry_matrix.csv
```

**Fallback Strategy**: If BLS data is unavailable, use NAICS codes from O*NET's related occupations or implement LLM-based industry inference.

#### 2.1.2 Company Database Strategy

**Problem**: No single free, comprehensive database of companies by NAICS code exists.

**Solution**: Multi-source approach with LLM augmentation:

```python
# src/data/company_database.py

class CompanyDatabase:
    """Generates company names using hybrid approach."""

    # Seed database with well-known companies (manually curated)
    SEED_COMPANIES = {
        '11': [  # Agriculture
            Company("Cargill", "large", "11", private=True),
            Company("Archer Daniels Midland", "fortune500", "11", ticker="ADM"),
            Company("Tyson Foods", "fortune500", "11", ticker="TSN"),
        ],
        '52': [  # Finance
            Company("JPMorgan Chase", "fortune500", "52", ticker="JPM"),
            Company("Goldman Sachs", "fortune500", "52", ticker="GS"),
            Company("Local Credit Union", "small", "52"),
        ],
        # ... curated list for each 2-digit NAICS sector
    }

    async def get_company_for_prompt(
        self,
        naics_sector: str,
        size_category: str,
        seed: int
    ) -> Company:
        """Get or generate a company for the prompt."""

        # First, try seed database
        sector_companies = self.SEED_COMPANIES.get(naics_sector, [])
        matching = [c for c in sector_companies if c.size_category == size_category]

        if matching:
            return matching[seed % len(matching)]

        # Fallback: Use LLM to generate realistic company
        return await self._generate_company_via_llm(naics_sector, size_category, seed)

    async def _generate_company_via_llm(
        self,
        naics_sector: str,
        size_category: str,
        seed: int
    ) -> Company:
        """Generate a realistic company using LLM."""
        prompt = f"""Generate a realistic company name for:
        - NAICS Sector: {naics_sector} ({NAICS_SECTOR_NAMES[naics_sector]})
        - Size: {size_category}

        Output JSON: {{"name": "...", "hq_city": "...", "employee_count": "..."}}
        Use your knowledge of real companies in this sector.
        If generating a fictional company, make it sound realistic."""

        # Rotate through models to avoid bias
        models = ['gemini-3.0-pro', 'gpt-4.1', 'claude-sonnet']
        model = models[seed % len(models)]

        response = await self.openrouter.generate(model, prompt)
        return self._parse_company_response(response)
```

**Curated Seed List Requirements**:
- Minimum 5 companies per NAICS sector (100 companies total)
- Mix of Fortune 500, large, mid-market, small, startup
- Include both well-known and lesser-known companies

#### 2.1.3 Name Database

**Source**: US Social Security Administration baby name data + Census surname data

**Acquisition**:
```bash
# SSA Names (public domain)
mkdir -p data/names
curl -o data/names/names.zip \
  "https://www.ssa.gov/oact/babynames/names.zip"
unzip data/names/names.zip -d data/names/ssa/

# Census Surnames (public domain)
curl -o data/names/surnames.csv \
  "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
```

**Implementation**:
```python
# src/data/name_generator.py

class NameGenerator:
    """Generates demographically diverse names."""

    def __init__(self, ssa_dir: Path, census_file: Path):
        self.first_names = self._load_ssa_names(ssa_dir)
        self.last_names = self._load_census_surnames(census_file)

    def _load_ssa_names(self, ssa_dir: Path) -> Dict[str, List[NameEntry]]:
        """Load names by decade for generation matching."""
        names_by_decade = defaultdict(list)

        for year_file in ssa_dir.glob("yob*.txt"):
            year = int(year_file.stem[3:])
            decade = (year // 10) * 10

            with open(year_file) as f:
                for line in f:
                    name, gender, count = line.strip().split(',')
                    names_by_decade[decade].append(
                        NameEntry(name, gender, int(count))
                    )

        return names_by_decade

    def generate_name(
        self,
        generation: str,
        gender_presentation: str = 'any',
        seed: int = None
    ) -> PersonaName:
        """Generate a name matching the generation."""

        rng = random.Random(seed)

        # Map generation to birth decade
        decade = self._generation_to_decade(generation)

        # Sample first name from that era
        first_names = self.first_names.get(decade, self.first_names[1990])
        if gender_presentation != 'any':
            first_names = [n for n in first_names if n.gender_matches(gender_presentation)]

        first_name = self._weighted_sample(first_names, rng)

        # Sample last name (diversity-weighted)
        last_name = self._sample_diverse_surname(rng)

        return PersonaName(
            first_name=first_name.name,
            last_name=last_name,
            generation=generation
        )
```

### 2.2 O*NET Schema Verification

**CRITICAL**: Before using element IDs, verify against db/ONET_REFERENCE.md and actual database:

```python
# scripts/verify_onet_schema.py

import sqlite3

def verify_onet_elements(db_path: str):
    """Verify required O*NET elements exist."""

    conn = sqlite3.connect(db_path)

    required_elements = {
        'skills': [
            ('2.A.1.c', 'Writing Skill'),  # Must verify this ID
        ],
        'abilities': [
            ('1.A.1.a.4', 'Written Expression'),  # Must verify
        ],
        'work_context': [
            ('4.C.1.a.2.h', 'Electronic Mail'),  # Must verify
            ('4.C.1.a.2.j', 'Letters and Memos'),  # Must verify
        ]
    }

    for table, elements in required_elements.items():
        for element_id, description in elements:
            cursor = conn.execute(f"""
                SELECT DISTINCT element_id
                FROM {table}
                WHERE element_id = ?
            """, (element_id,))

            if not cursor.fetchone():
                print(f"WARNING: Element {element_id} ({description}) not found in {table}")
                # Query what elements exist
                cursor = conn.execute(f"""
                    SELECT DISTINCT element_id, element_name
                    FROM {table} t
                    JOIN content_model_reference cmr ON t.element_id = cmr.element_id
                    LIMIT 20
                """)
                print(f"Available elements: {cursor.fetchall()}")

    conn.close()

if __name__ == "__main__":
    verify_onet_elements("db/onet.db")
```

### 2.3 OpenRouter Model Verification

**CRITICAL**: Verify all model identifiers before implementation:

```python
# scripts/verify_openrouter_models.py

import httpx
import os

async def verify_models():
    """Verify required models are available on OpenRouter."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        available_models = {m['id'] for m in response.json()['data']}

    required_models = {
        # Pro tier
        'google/gemini-3.0-pro',       # VERIFY
        'openai/gpt-5.2',              # VERIFY - may be gpt-5.2-thinking
        'anthropic/claude-opus-4.5',   # VERIFY - may be claude-4-opus
        'x-ai/grok-4.1-thinking',      # VERIFY
        'moonshot/kimi-k2-thinking',   # VERIFY

        # Flash tier
        'google/gemini-3.0-flash',     # VERIFY
        'openai/gpt-4.1',              # VERIFY
        'anthropic/claude-sonnet',     # VERIFY - may be claude-3.5-sonnet
    }

    for model in required_models:
        if model in available_models:
            print(f"OK: {model}")
        else:
            print(f"MISSING: {model}")
            # Find similar
            similar = [m for m in available_models if any(
                part in m.lower() for part in model.split('/')[-1].split('-')
            )]
            if similar:
                print(f"  Suggestions: {similar[:5]}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_models())
```

---

## Part 3: O*NET Data Extraction (Revised)

### 3.1 Database Schema Understanding

First, consult db/ONET_REFERENCE.md for actual schema details. The extraction should adapt to the actual schema rather than assuming element IDs.

```python
# src/data/onet_extractor.py

from dataclasses import dataclass
from typing import List, Optional, Dict
import sqlite3
from pathlib import Path

@dataclass
class ONetTask:
    """Represents an O*NET task with metadata."""
    task_id: int
    onetsoc_code: str
    task: str
    task_type: str
    occupation_title: str
    occupation_description: str
    job_zone: int
    soc_major_group: str
    soc_group_name: str
    writing_relevance_score: float  # Computed, not from fixed element
    inferred_writing_category: str
    inferred_communication_channel: str

class ONetExtractor:
    """Extracts writing-relevant tasks from O*NET database."""

    # Writing relevance patterns (data-driven, not hardcoded categories)
    WRITING_INDICATORS = [
        # High confidence
        (r'\bwrite\b', 1.0),
        (r'\bdraft\b', 1.0),
        (r'\bcompose\b', 1.0),
        (r'\bdocument\b', 0.8),
        (r'\breport\b', 0.7),
        (r'\bcorrespond', 0.9),
        (r'\bemail\b', 0.9),
        (r'\bmemo\b', 0.9),
        (r'\bletter\b', 0.8),
        # Medium confidence
        (r'\bcommunicat', 0.6),
        (r'\bpresent\b', 0.5),
        (r'\bsummariz', 0.7),
        (r'\bpropos', 0.7),
        (r'\brecommend', 0.6),
        (r'\binform\b', 0.5),
        (r'\bnotif', 0.7),
        # Lower confidence
        (r'\bconfer\b', 0.4),
        (r'\bdiscuss\b', 0.3),
        (r'\bcoordinat', 0.4),
    ]

    def __init__(self, db_path: str = "db/onet.db"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"O*NET database not found: {db_path}")

        self._verify_schema()

    def _verify_schema(self):
        """Verify required tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        required = {'task_statements', 'occupation_data'}
        missing = required - tables
        if missing:
            raise ValueError(f"Missing required tables: {missing}")

    def extract_writing_tasks(
        self,
        min_relevance: float = 0.5,
        job_zones: Optional[List[int]] = None,
        soc_codes: Optional[List[str]] = None
    ) -> List[ONetTask]:
        """Extract tasks where writing is likely needed."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Base query - adapt column names to actual schema
        query = """
        SELECT
            t.task_id,
            t.onetsoc_code,
            t.task,
            t.task_type,
            o.title as occupation_title,
            o.description as occupation_description,
            COALESCE(jz.job_zone, 3) as job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        WHERE 1=1
        """

        params = []
        if job_zones:
            query += f" AND jz.job_zone IN ({','.join('?' * len(job_zones))})"
            params.extend(job_zones)

        if soc_codes:
            placeholders = ','.join('?' * len(soc_codes))
            query += f" AND SUBSTR(t.onetsoc_code, 1, 2) IN ({placeholders})"
            params.extend(soc_codes)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Score and filter tasks
        tasks = []
        for row in rows:
            relevance = self._compute_writing_relevance(row['task'])
            if relevance >= min_relevance:
                tasks.append(ONetTask(
                    task_id=row['task_id'],
                    onetsoc_code=row['onetsoc_code'],
                    task=row['task'],
                    task_type=row['task_type'] or 'Core',
                    occupation_title=row['occupation_title'],
                    occupation_description=row['occupation_description'],
                    job_zone=row['job_zone'],
                    soc_major_group=row['soc_major'],
                    soc_group_name=self._get_soc_group_name(row['soc_major']),
                    writing_relevance_score=relevance,
                    inferred_writing_category=self._infer_category(row['task']),
                    inferred_communication_channel=self._infer_channel(row['task'])
                ))

        return tasks

    def _compute_writing_relevance(self, task_text: str) -> float:
        """Compute writing relevance score for a task."""
        import re

        task_lower = task_text.lower()
        max_score = 0.0

        for pattern, weight in self.WRITING_INDICATORS:
            if re.search(pattern, task_lower):
                max_score = max(max_score, weight)

        return max_score

    def _infer_category(self, task_text: str) -> str:
        """Infer writing category from task text."""
        task_lower = task_text.lower()

        # Let the data drive categories rather than hardcoding
        if any(w in task_lower for w in ['report', 'document', 'record']):
            return 'documentation'
        elif any(w in task_lower for w in ['email', 'correspond', 'letter']):
            return 'correspondence'
        elif any(w in task_lower for w in ['propos', 'recommend', 'suggest']):
            return 'proposals'
        elif any(w in task_lower for w in ['customer', 'client', 'patient']):
            return 'customer_communication'
        elif any(w in task_lower for w in ['train', 'instruct', 'teach']):
            return 'training'
        elif any(w in task_lower for w in ['policy', 'procedure', 'guideline']):
            return 'policy'
        elif any(w in task_lower for w in ['review', 'evaluat', 'assess']):
            return 'evaluation'
        elif any(w in task_lower for w in ['contract', 'agreement', 'legal']):
            return 'contracts'
        else:
            return 'general_communication'

    def _infer_channel(self, task_text: str) -> str:
        """Infer communication channel from task text."""
        task_lower = task_text.lower()

        if 'email' in task_lower:
            return 'email'
        elif 'letter' in task_lower:
            return 'letter'
        elif 'memo' in task_lower:
            return 'memo'
        elif 'report' in task_lower:
            return 'report'
        elif any(w in task_lower for w in ['post', 'social', 'blog']):
            return 'social_media'
        elif 'present' in task_lower:
            return 'presentation'
        elif any(w in task_lower for w in ['message', 'text', 'chat']):
            return 'instant_message'
        else:
            return 'unspecified'  # Let Phase 3 enrichment determine

    SOC_MAJOR_GROUPS = {
        '11': 'Management',
        '13': 'Business and Financial Operations',
        '15': 'Computer and Mathematical',
        '17': 'Architecture and Engineering',
        '19': 'Life, Physical, and Social Science',
        '21': 'Community and Social Service',
        '23': 'Legal',
        '25': 'Educational Instruction and Library',
        '27': 'Arts, Design, Entertainment, Sports, and Media',
        '29': 'Healthcare Practitioners and Technical',
        '31': 'Healthcare Support',
        '33': 'Protective Service',
        '35': 'Food Preparation and Serving Related',
        '37': 'Building and Grounds Cleaning and Maintenance',
        '39': 'Personal Care and Service',
        '41': 'Sales and Related',
        '43': 'Office and Administrative Support',
        '45': 'Farming, Fishing, and Forestry',
        '47': 'Construction and Extraction',
        '49': 'Installation, Maintenance, and Repair',
        '51': 'Production',
        '53': 'Transportation and Material Moving',
    }

    def _get_soc_group_name(self, soc_major: str) -> str:
        return self.SOC_MAJOR_GROUPS.get(soc_major, 'Unknown')
```

---

## Part 4: Prompt Generation Pipeline (Revised with Error Handling)

### 4.1 Three-Phase Pipeline with Robustness

```python
# src/prompts/pipeline.py

import asyncio
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class PromptGenerationResult:
    """Result of prompt generation with status tracking."""
    prompts: List['FinalPrompt']
    failed_tasks: List[tuple]  # (task, error)
    generation_stats: dict

class PromptGenerationPipeline:
    """Orchestrates the three-phase prompt generation."""

    def __init__(
        self,
        onet_extractor: 'ONetExtractor',
        openrouter_client: 'OpenRouterClient',
        company_db: 'CompanyDatabase',
        name_generator: 'NameGenerator',
        seed: int = 42
    ):
        self.onet = onet_extractor
        self.openrouter = openrouter_client
        self.companies = company_db
        self.names = name_generator
        self.seed = seed
        self._rng = random.Random(seed)

    async def generate_prompts(
        self,
        num_prompts: int,
        config: 'PromptConfig'
    ) -> PromptGenerationResult:
        """Generate prompts through all three phases."""

        # Extract O*NET tasks
        tasks = self.onet.extract_writing_tasks(
            min_relevance=0.5,
            job_zones=config.job_zones,
            soc_codes=config.soc_codes
        )

        if len(tasks) < num_prompts:
            logger.warning(
                f"Only {len(tasks)} tasks available, requested {num_prompts}"
            )

        # Sample tasks with stratification
        selected_tasks = self._stratified_sample(tasks, num_prompts, config)

        # Phase 1: Generate persona variations (with retry)
        personas_by_task = await self._phase1_generate_personas(
            selected_tasks,
            variations_per_task=3
        )

        # Phase 2: Algorithmic combination
        skeletons = self._phase2_combine(selected_tasks, personas_by_task)

        # Phase 3: LLM enrichment (with retry)
        prompts, failures = await self._phase3_enrich(skeletons)

        # Validate diversity
        self._validate_diversity(prompts, config)

        return PromptGenerationResult(
            prompts=prompts,
            failed_tasks=failures,
            generation_stats=self._compute_stats(prompts)
        )

    async def _phase1_generate_personas(
        self,
        tasks: List['ONetTask'],
        variations_per_task: int = 3
    ) -> Dict[int, List['PersonaContext']]:
        """Phase 1: Generate diverse persona variations."""

        personas = {}
        semaphore = asyncio.Semaphore(10)  # Limit concurrent API calls

        async def generate_for_task(task: 'ONetTask'):
            async with semaphore:
                try:
                    result = await self._generate_personas_with_retry(
                        task,
                        variations_per_task
                    )
                    personas[task.task_id] = result
                except Exception as e:
                    logger.error(f"Failed to generate personas for task {task.task_id}: {e}")
                    # Fallback: use default personas
                    personas[task.task_id] = self._get_default_personas(variations_per_task)

        await asyncio.gather(*[generate_for_task(t) for t in tasks])
        return personas

    async def _generate_personas_with_retry(
        self,
        task: 'ONetTask',
        num_variations: int,
        max_retries: int = 3
    ) -> List['PersonaContext']:
        """Generate personas with retry logic."""

        # Rotate through models to avoid bias
        models = [
            'google/gemini-3.0-pro',
            'openai/gpt-4.1',
            'anthropic/claude-sonnet'
        ]

        system_prompt = self._build_persona_system_prompt()
        user_prompt = self._build_persona_user_prompt(task, num_variations)

        for attempt in range(max_retries):
            model = models[attempt % len(models)]

            try:
                response = await self.openrouter.generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.8
                )

                return self._parse_personas(response.content)

            except Exception as e:
                logger.warning(f"Persona generation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        raise RuntimeError("All persona generation attempts failed")

    def _build_persona_system_prompt(self) -> str:
        return """You are helping create diverse writing task scenarios for an LLM evaluation.

Generate realistic persona contexts that vary across these dimensions:
- Age/generation (GenZ: 12-27, Millennial: 28-43, GenX: 44-59, Boomer: 60-78)
- Skill/experience level (entry: 0-2 years, mid: 3-7 years, senior: 8-15 years, executive: 15+ years)
- Formality requirements (1=very casual to 5=extremely formal)
- Urgency (1=routine to 5=critical)
- Relationship context (new_contact, colleague, manager, direct_report, client, vendor)
- Emotional context (routine, positive, negative, crisis, celebratory, conflict)

IMPORTANT: Output ONLY valid JSON. No markdown, no explanation."""

    def _build_persona_user_prompt(self, task: 'ONetTask', num_variations: int) -> str:
        return f"""O*NET Occupation: {task.occupation_title}
Job Zone (skill level 1-5): {task.job_zone}
Task: {task.task}

Generate {num_variations} diverse persona contexts as a JSON array:
[
  {{
    "writer_name": "First Last",
    "writer_generation": "GenZ|Millennial|GenX|Boomer",
    "writer_job_title": "specific title matching occupation",
    "writer_years_experience": number,
    "recipient_name": "First Last",
    "recipient_title": "specific title",
    "recipient_relationship": "new_contact|colleague|manager|direct_report|client|vendor",
    "formality_level": 1-5,
    "urgency_level": 1-5,
    "emotional_context": "routine|positive|negative|crisis|celebratory|conflict",
    "audience_size": "one_to_one|small_group|department|company_wide|public"
  }}
]

Ensure MAXIMUM diversity - each persona should feel distinctly different."""

    def _phase2_combine(
        self,
        tasks: List['ONetTask'],
        personas_by_task: Dict[int, List['PersonaContext']]
    ) -> List['PromptSkeleton']:
        """Phase 2: Algorithmic combination of components."""

        skeletons = []

        for task in tasks:
            personas = personas_by_task.get(task.task_id, [])
            if not personas:
                continue

            for persona in personas:
                # Deterministic seeding for reproducibility
                combo_seed = hash(f"{self.seed}:{task.task_id}:{persona.writer_name}") % (2**31)
                rng = random.Random(combo_seed)

                # Sample industry
                industry = self._sample_industry(task.onetsoc_code, rng)

                # Sample company matching industry
                company = self.companies.get_company_for_prompt(
                    naics_sector=industry['sector'],
                    size_category=self._determine_company_size(persona, task.job_zone),
                    seed=combo_seed
                )

                # Generate names
                writer_name = self.names.generate_name(
                    generation=persona.writer_generation,
                    seed=combo_seed
                )
                recipient_name = self.names.generate_name(
                    seed=combo_seed + 1
                )

                # Determine additional context
                temporal_context = self._maybe_generate_temporal_context(
                    task, persona, rng
                )
                attachments = self._maybe_generate_attachments(task, rng)
                message_position = self._sample_message_position(persona, rng)
                english_variant = self._sample_english_variant(rng)

                skeletons.append(PromptSkeleton(
                    task=task,
                    persona=persona,
                    industry=industry,
                    company=company,
                    writer_name=writer_name,
                    recipient_name=recipient_name,
                    temporal_context=temporal_context,
                    attachments=attachments,
                    message_position=message_position,
                    english_variant=english_variant,
                    seed=combo_seed
                ))

        return skeletons

    def _determine_company_size(self, persona: 'PersonaContext', job_zone: int) -> str:
        """Determine appropriate company size based on context."""
        # Higher formality often correlates with larger companies
        if persona.formality_level >= 4:
            return random.choice(['fortune500', 'large', 'midmarket'])
        elif persona.formality_level <= 2:
            return random.choice(['small', 'startup', 'midmarket'])
        else:
            return random.choice(['large', 'midmarket', 'small'])

    def _sample_english_variant(self, rng: random.Random) -> str:
        """Sample English variant (90% US, 10% international)."""
        roll = rng.random()
        if roll < 0.90:
            return 'en-US'
        elif roll < 0.94:
            return 'en-GB'
        elif roll < 0.97:
            return 'en-AU'
        else:
            return 'non-native'

    async def _phase3_enrich(
        self,
        skeletons: List['PromptSkeleton']
    ) -> tuple[List['FinalPrompt'], List[tuple]]:
        """Phase 3: LLM enrichment for context-heavy prompts."""

        prompts = []
        failures = []
        semaphore = asyncio.Semaphore(10)

        async def enrich_skeleton(skeleton: 'PromptSkeleton'):
            async with semaphore:
                try:
                    prompt = await self._enrich_with_retry(skeleton)
                    prompts.append(prompt)
                except Exception as e:
                    logger.error(f"Failed to enrich skeleton: {e}")
                    # Try to create a minimal prompt without enrichment
                    try:
                        prompt = self._create_minimal_prompt(skeleton)
                        prompts.append(prompt)
                    except Exception as e2:
                        failures.append((skeleton, e2))

        await asyncio.gather(*[enrich_skeleton(s) for s in skeletons])
        return prompts, failures

    async def _enrich_with_retry(
        self,
        skeleton: 'PromptSkeleton',
        max_retries: int = 3
    ) -> 'FinalPrompt':
        """Enrich a skeleton with LLM-generated context."""

        # Determine what enrichment is needed
        needs_prior_context = skeleton.message_position in ['reply', 'followup']
        needs_attachments = len(skeleton.attachments) > 0
        needs_tone_example = self._should_add_tone_example(skeleton)
        make_ambiguous = self._should_be_ambiguous(skeleton)

        if not any([needs_prior_context, needs_attachments, needs_tone_example]):
            # Simple prompt - no LLM enrichment needed
            return self._build_prompt_from_skeleton(skeleton)

        # Build enrichment prompt
        enrichment_prompt = self._build_enrichment_prompt(
            skeleton,
            needs_prior_context=needs_prior_context,
            needs_attachments=needs_attachments,
            needs_tone_example=needs_tone_example,
            make_ambiguous=make_ambiguous
        )

        # Rotate models
        models = ['google/gemini-3.0-pro', 'openai/gpt-4.1', 'anthropic/claude-sonnet']

        for attempt in range(max_retries):
            model = models[(skeleton.seed + attempt) % len(models)]

            try:
                response = await self.openrouter.generate(
                    model=model,
                    system_prompt="Generate realistic context for writing prompts. Output JSON only.",
                    user_prompt=enrichment_prompt,
                    temperature=0.7
                )

                enriched_context = self._parse_enrichment(response.content)
                return self._build_prompt_from_skeleton(skeleton, enriched_context)

            except Exception as e:
                logger.warning(f"Enrichment attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("All enrichment attempts failed")

    def _validate_diversity(self, prompts: List['FinalPrompt'], config: 'PromptConfig'):
        """Validate that prompts meet diversity requirements."""

        # Check distribution across key dimensions
        distributions = {
            'job_zone': Counter(p.job_zone for p in prompts),
            'soc_major_group': Counter(p.soc_major_group for p in prompts),
            'formality_level': Counter(p.formality_level.value for p in prompts),
            'writer_generation': Counter(p.writer.generation for p in prompts),
            'urgency_level': Counter(p.urgency_level.value for p in prompts),
        }

        for dimension, counts in distributions.items():
            if len(counts) < 3:
                logger.warning(f"Low diversity in {dimension}: only {len(counts)} unique values")

            # Check for severe imbalance
            total = sum(counts.values())
            max_share = max(counts.values()) / total
            if max_share > 0.5:
                logger.warning(
                    f"Imbalanced {dimension}: {max(counts, key=counts.get)} has {max_share:.1%}"
                )
```

---

## Part 5: Evaluation and Judging (Revised)

### 5.1 Judge Engine with Robust JSON Parsing

```python
# src/evaluation/judge_engine.py

import json
import re
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class JudgmentVote:
    """A single vote from one judge."""
    judge_model: str
    persona: str
    vote: str  # 'A', 'B', 'TIE'
    confidence: float
    reasoning: str
    raw_response: str  # For debugging

class JudgeEngine:
    """Implements dual-persona ensemble judging with robust parsing."""

    JUDGE_MODELS = [
        'anthropic/claude-opus-4.5',
        'openai/gpt-5.2',
        'google/gemini-3.0-pro'
    ]

    def __init__(self, openrouter_client: 'OpenRouterClient', config: 'JudgeConfig'):
        self.openrouter = openrouter_client
        self.config = config

    async def judge_comparison(
        self,
        prompt: 'FinalPrompt',
        response_a: 'ModelResponse',
        response_b: 'ModelResponse',
        order: 'ResponseOrder'
    ) -> 'EnsembleJudgment':
        """Run full ensemble judgment with all judges and personas."""

        all_votes = []

        # Prepare ordered responses
        ordered = self._apply_order(response_a, response_b, order)

        # Build context once
        judge_context = self._build_judge_context(prompt)

        # Collect votes from all judges
        for judge_model in self._get_active_judges():
            for persona in self.config.personas:
                votes = await self._get_n_judgments(
                    judge_model=judge_model,
                    persona=persona,
                    context=judge_context,
                    responses=ordered,
                    n=self.config.votes_per_judge
                )
                all_votes.extend(votes)

        # Aggregate using majority-of-majorities
        return self._aggregate_votes(all_votes, order, prompt.prompt_id)

    async def _get_n_judgments(
        self,
        judge_model: str,
        persona: str,
        context: str,
        responses: tuple,
        n: int
    ) -> List[JudgmentVote]:
        """Get N judgment votes from a single judge."""

        votes = []
        system_prompt = self._get_system_prompt(persona, context)
        user_prompt = self._build_comparison_prompt(responses, context)

        for i in range(n):
            try:
                response = await self.openrouter.generate(
                    model=judge_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.3  # Low temp for more consistent judging
                )

                vote = self._parse_judgment_robust(response.content, judge_model, persona)
                votes.append(vote)

            except Exception as e:
                logger.error(f"Judge {judge_model} failed on vote {i}: {e}")
                # Record as abstention
                votes.append(JudgmentVote(
                    judge_model=judge_model,
                    persona=persona,
                    vote='ABSTAIN',
                    confidence=0.0,
                    reasoning=f"Error: {str(e)}",
                    raw_response=""
                ))

        return votes

    def _parse_judgment_robust(
        self,
        content: str,
        judge_model: str,
        persona: str
    ) -> JudgmentVote:
        """Robustly parse judgment response with multiple fallback strategies."""

        raw = content

        # Strategy 1: Try direct JSON parse
        try:
            # Look for JSON in the response
            json_match = re.search(r'\{[^{}]*"winner"[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return JudgmentVote(
                    judge_model=judge_model,
                    persona=persona,
                    vote=self._normalize_vote(data.get('winner', 'TIE')),
                    confidence=float(data.get('confidence', 0.5)),
                    reasoning=data.get('reasoning', ''),
                    raw_response=raw
                )
        except json.JSONDecodeError:
            pass

        # Strategy 2: Look for explicit winner statement
        content_lower = content.lower()
        if 'response a' in content_lower and 'wins' in content_lower:
            return JudgmentVote(
                judge_model=judge_model,
                persona=persona,
                vote='A',
                confidence=0.7,
                reasoning=content[:500],
                raw_response=raw
            )
        elif 'response b' in content_lower and 'wins' in content_lower:
            return JudgmentVote(
                judge_model=judge_model,
                persona=persona,
                vote='B',
                confidence=0.7,
                reasoning=content[:500],
                raw_response=raw
            )

        # Strategy 3: Look for "winner: A" or "winner: B" pattern
        winner_match = re.search(r'winner[:\s]+["\']?([AB]|tie)["\']?', content, re.IGNORECASE)
        if winner_match:
            return JudgmentVote(
                judge_model=judge_model,
                persona=persona,
                vote=self._normalize_vote(winner_match.group(1)),
                confidence=0.6,
                reasoning=content[:500],
                raw_response=raw
            )

        # Strategy 4: Default to TIE with low confidence
        logger.warning(f"Could not parse judgment from {judge_model}, defaulting to TIE")
        return JudgmentVote(
            judge_model=judge_model,
            persona=persona,
            vote='TIE',
            confidence=0.3,
            reasoning=f"Parse failure: {content[:200]}",
            raw_response=raw
        )

    def _normalize_vote(self, vote: str) -> str:
        """Normalize vote to A, B, or TIE."""
        vote = vote.upper().strip()
        if vote in ['A', 'RESPONSE A', 'FIRST']:
            return 'A'
        elif vote in ['B', 'RESPONSE B', 'SECOND']:
            return 'B'
        else:
            return 'TIE'

    def _build_comparison_prompt(
        self,
        responses: tuple,
        context: str
    ) -> str:
        """Build the comparison prompt for judges."""
        response_a, response_b = responses

        return f"""{context}

---

## Response A

{response_a.content}

---

## Response B

{response_b.content}

---

## Your Evaluation

Compare the two responses above and determine which better accomplishes the writing task.

Consider:
1. **Task Completion**: Does it fully address what was asked?
2. **Tone Appropriateness**: Is the tone right for this specific writer/recipient/context?
3. **Authenticity**: Does it read like a real person wrote it, not AI?
4. **Effectiveness**: Would the recipient respond positively?
5. **Quality**: Clarity, structure, flow, word choice
6. **Length**: Is it the right length for this task?
7. **Cliche Avoidance**: Does it avoid obvious AI patterns?

You MUST respond with ONLY this JSON format, nothing else:
```json
{{
    "winner": "A" or "B" or "TIE",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief 1-2 sentence explanation"
}}
```"""

    def _aggregate_votes(
        self,
        votes: List[JudgmentVote],
        order: 'ResponseOrder',
        prompt_id: str
    ) -> 'EnsembleJudgment':
        """Aggregate votes using majority-of-majorities."""

        # Filter out abstentions
        valid_votes = [v for v in votes if v.vote != 'ABSTAIN']

        if not valid_votes:
            return EnsembleJudgment(
                prompt_id=prompt_id,
                final_winner='tie',
                agreement_score=0.0,
                is_valid=False,
                error="All judges abstained"
            )

        # Group by judge model
        by_judge = defaultdict(list)
        for v in valid_votes:
            by_judge[v.judge_model].append(v)

        # Get majority for each judge
        judge_winners = []
        for judge_model, judge_votes in by_judge.items():
            counts = Counter(v.vote for v in judge_votes)
            if counts['A'] > counts['B']:
                winner = 'A'
            elif counts['B'] > counts['A']:
                winner = 'B'
            else:
                winner = 'TIE'
            judge_winners.append(winner)

        # Get majority across judges
        final_counts = Counter(judge_winners)
        if final_counts['A'] > final_counts['B']:
            final_winner_ordered = 'A'
        elif final_counts['B'] > final_counts['A']:
            final_winner_ordered = 'B'
        else:
            final_winner_ordered = 'TIE'

        # Unmap to actual models
        if final_winner_ordered == 'A':
            final_winner = 'gemini' if order.a_is_gemini else 'competitor'
        elif final_winner_ordered == 'B':
            final_winner = 'competitor' if order.a_is_gemini else 'gemini'
        else:
            final_winner = 'tie'

        # Calculate agreement
        agreement = self._calculate_fleiss_kappa(valid_votes)

        return EnsembleJudgment(
            prompt_id=prompt_id,
            final_winner=final_winner,
            final_winner_ordered=final_winner_ordered,
            all_votes=votes,
            judge_winners=judge_winners,
            agreement_score=agreement,
            is_valid=True
        )
```

### 5.2 Instruction Constraint Verification

```python
# src/evaluation/constraint_checker.py

class ConstraintChecker:
    """Verifies if model responses followed explicit instructions."""

    def check_constraints(
        self,
        response: 'ModelResponse',
        constraints: List['InstructionConstraint']
    ) -> Dict[str, bool]:
        """Check all constraints and return compliance status."""

        results = {}

        for constraint in constraints:
            if constraint.constraint_type == 'length_max':
                results[f'length_max_{constraint.constraint_value}'] = \
                    self._check_length_max(response.content, int(constraint.constraint_value))

            elif constraint.constraint_type == 'length_min':
                results[f'length_min_{constraint.constraint_value}'] = \
                    self._check_length_min(response.content, int(constraint.constraint_value))

            elif constraint.constraint_type == 'format':
                results[f'format_{constraint.constraint_value}'] = \
                    self._check_format(response.content, constraint.constraint_value)

            elif constraint.constraint_type == 'exclusion':
                results[f'excludes_{constraint.constraint_value}'] = \
                    self._check_exclusion(response.content, constraint.constraint_value)

            elif constraint.constraint_type == 'tone':
                results[f'tone_{constraint.constraint_value}'] = \
                    self._check_tone(response.content, constraint.constraint_value)

        return results

    def _check_length_max(self, content: str, max_words: int) -> bool:
        word_count = len(content.split())
        return word_count <= max_words

    def _check_length_min(self, content: str, min_words: int) -> bool:
        word_count = len(content.split())
        return word_count >= min_words

    def _check_format(self, content: str, format_req: str) -> bool:
        if format_req == 'no_bullets':
            return '- ' not in content and '* ' not in content
        elif format_req == 'bullets_only':
            return '- ' in content or '* ' in content
        elif format_req == 'paragraphs_only':
            return '- ' not in content and '* ' not in content and '\n1.' not in content
        elif format_req.startswith('exactly_'):
            count = int(format_req.split('_')[1])
            bullet_count = content.count('- ') + content.count('* ')
            return bullet_count == count
        return True

    def _check_exclusion(self, content: str, exclusion: str) -> bool:
        return exclusion.lower() not in content.lower()

    def _check_tone(self, content: str, tone_req: str) -> bool:
        # Basic heuristic checks
        content_lower = content.lower()

        if tone_req == 'no_pleasantries':
            pleasantries = ['hope this finds you', 'hope you are well', 'trust you are']
            return not any(p in content_lower for p in pleasantries)

        elif tone_req == 'direct':
            # Check for hedging language
            hedging = ['perhaps', 'maybe', 'might consider', 'just wanted to']
            return not any(h in content_lower for h in hedging)

        return True
```

---

## Part 6: Robustness and Concurrency (NEW - Addressing Missing Details)

### 6.1 Concurrency Management

```python
# src/core/concurrency.py

import asyncio
from typing import Dict, Optional
from dataclasses import dataclass, field
import time

@dataclass
class RateLimitConfig:
    """Rate limiting configuration per model."""
    requests_per_minute: int = 60
    max_concurrent: int = 10
    retry_on_429: bool = True
    max_retries: int = 3

class ConcurrencyManager:
    """Manages concurrent API calls with rate limiting."""

    def __init__(self):
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._rate_limiters: Dict[str, 'TokenBucketRateLimiter'] = {}
        self._configs: Dict[str, RateLimitConfig] = {}

    def configure_model(self, model: str, config: RateLimitConfig):
        """Configure rate limiting for a specific model."""
        self._configs[model] = config
        self._semaphores[model] = asyncio.Semaphore(config.max_concurrent)
        self._rate_limiters[model] = TokenBucketRateLimiter(
            tokens_per_minute=config.requests_per_minute
        )

    async def acquire(self, model: str):
        """Acquire permission to make an API call."""
        if model not in self._semaphores:
            # Default config
            self.configure_model(model, RateLimitConfig())

        # First, wait for semaphore (concurrency limit)
        await self._semaphores[model].acquire()

        # Then, wait for rate limit
        await self._rate_limiters[model].acquire()

    def release(self, model: str):
        """Release the semaphore after completing a call."""
        if model in self._semaphores:
            self._semaphores[model].release()

class TokenBucketRateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, tokens_per_minute: int):
        self.rate = tokens_per_minute / 60.0  # tokens per second
        self.max_tokens = tokens_per_minute
        self.tokens = tokens_per_minute
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
```

### 6.2 Improved Checkpoint System

```python
# src/core/checkpoint.py

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Optional
from dataclasses import dataclass, asdict
import threading

@dataclass
class CheckpointState:
    """Complete checkpoint state."""
    run_id: str
    phase: str
    total_prompts: int
    completed_prompt_responses: Set[str]  # prompt_ids with all responses done
    completed_judgments: Set[str]  # "prompt_id:model_pair" keys
    failed_prompts: Dict[str, str]  # prompt_id -> error message
    started_at: str
    last_updated: str
    error_count: int
    retry_count: int

class CheckpointManager:
    """Thread-safe checkpoint management with atomic writes."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"
        self.backup_file = run_dir / "checkpoint.backup.json"
        self._lock = threading.Lock()
        self.state = self._load_or_create()
        self._save_interval = 10  # Save every N updates
        self._pending_updates = 0

    def _load_or_create(self) -> CheckpointState:
        """Load existing checkpoint or create new one."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file) as f:
                    data = json.load(f)
                return CheckpointState(
                    run_id=data['run_id'],
                    phase=data['phase'],
                    total_prompts=data['total_prompts'],
                    completed_prompt_responses=set(data['completed_prompt_responses']),
                    completed_judgments=set(data['completed_judgments']),
                    failed_prompts=data.get('failed_prompts', {}),
                    started_at=data['started_at'],
                    last_updated=data['last_updated'],
                    error_count=data.get('error_count', 0),
                    retry_count=data.get('retry_count', 0)
                )
            except (json.JSONDecodeError, KeyError) as e:
                # Try backup
                if self.backup_file.exists():
                    return self._load_backup()
                raise

        # New checkpoint
        now = datetime.now().isoformat()
        return CheckpointState(
            run_id=self._generate_run_id(),
            phase='initialization',
            total_prompts=0,
            completed_prompt_responses=set(),
            completed_judgments=set(),
            failed_prompts={},
            started_at=now,
            last_updated=now,
            error_count=0,
            retry_count=0
        )

    def save(self, force: bool = False):
        """Save checkpoint with atomic write."""
        with self._lock:
            self._pending_updates += 1

            if not force and self._pending_updates < self._save_interval:
                return

            self._pending_updates = 0
            self.state.last_updated = datetime.now().isoformat()

            # Prepare data
            data = {
                'run_id': self.state.run_id,
                'phase': self.state.phase,
                'total_prompts': self.state.total_prompts,
                'completed_prompt_responses': list(self.state.completed_prompt_responses),
                'completed_judgments': list(self.state.completed_judgments),
                'failed_prompts': self.state.failed_prompts,
                'started_at': self.state.started_at,
                'last_updated': self.state.last_updated,
                'error_count': self.state.error_count,
                'retry_count': self.state.retry_count
            }

            # Atomic write: write to temp, then rename
            temp_file = self.checkpoint_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Backup current checkpoint
            if self.checkpoint_file.exists():
                self.checkpoint_file.rename(self.backup_file)

            # Move temp to checkpoint
            temp_file.rename(self.checkpoint_file)

    def mark_response_complete(self, prompt_id: str, model: str):
        """Mark a response as complete."""
        with self._lock:
            # Track per-model completion (not implemented in basic version)
            pass

    def mark_prompt_responses_complete(self, prompt_id: str):
        """Mark all responses for a prompt as complete."""
        with self._lock:
            self.state.completed_prompt_responses.add(prompt_id)
        self.save()

    def mark_judgment_complete(self, prompt_id: str, model_pair: str):
        """Mark a judgment as complete."""
        key = f"{prompt_id}:{model_pair}"
        with self._lock:
            self.state.completed_judgments.add(key)
        self.save()

    def is_response_complete(self, prompt_id: str) -> bool:
        """Check if all responses for a prompt are complete."""
        return prompt_id in self.state.completed_prompt_responses

    def is_judgment_complete(self, prompt_id: str, model_pair: str) -> bool:
        """Check if a judgment is complete."""
        key = f"{prompt_id}:{model_pair}"
        return key in self.state.completed_judgments

    def record_failure(self, prompt_id: str, error: str):
        """Record a failure."""
        with self._lock:
            self.state.failed_prompts[prompt_id] = error
            self.state.error_count += 1
        self.save()

    def get_progress(self) -> dict:
        """Get current progress statistics."""
        return {
            'phase': self.state.phase,
            'total_prompts': self.state.total_prompts,
            'completed_responses': len(self.state.completed_prompt_responses),
            'completed_judgments': len(self.state.completed_judgments),
            'failures': len(self.state.failed_prompts),
            'errors': self.state.error_count,
            'retries': self.state.retry_count
        }
```

### 6.3 OpenRouter Client with Full Error Handling

```python
# src/api/openrouter_client.py

import httpx
import asyncio
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)

@dataclass
class ModelResponse:
    """Response from a model."""
    content: str
    model: str
    latency_ms: int
    finish_reason: str
    usage: Dict[str, int]
    is_error: bool = False
    error_type: Optional[str] = None

class OpenRouterClient:
    """Async client for OpenRouter with comprehensive error handling."""

    def __init__(
        self,
        api_key: str,
        concurrency_manager: 'ConcurrencyManager',
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 120.0
    ):
        self.api_key = api_key
        self.concurrency = concurrency_manager
        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://gemini-writing-eval.example.com",
                "X-Title": "Gemini Writing Evaluation Framework"
            }
        )

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_retries: int = 3
    ) -> ModelResponse:
        """Generate a completion with retry logic and rate limiting."""

        last_error = None

        for attempt in range(max_retries):
            try:
                await self.concurrency.acquire(model)
                try:
                    return await self._make_request(
                        model, system_prompt, user_prompt, temperature
                    )
                finally:
                    self.concurrency.release(model)

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited on {model}, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif e.response.status_code >= 500:
                    # Server error - exponential backoff
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error on {model}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    # Client error - don't retry
                    raise

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Timeout on {model}, attempt {attempt + 1}")
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on {model}: {e}")
                await asyncio.sleep(2 ** attempt)

        # All retries exhausted
        raise last_error or RuntimeError(f"Failed to generate from {model}")

    async def _make_request(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float
    ) -> ModelResponse:
        """Make a single API request."""
        import time

        start_time = time.time()

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

        latency_ms = int((time.time() - start_time) * 1000)
        data = response.json()

        return ModelResponse(
            content=data['choices'][0]['message']['content'],
            model=model,
            latency_ms=latency_ms,
            finish_reason=data['choices'][0].get('finish_reason', 'unknown'),
            usage=data.get('usage', {})
        )

    async def verify_models(self, required_models: list) -> Dict[str, bool]:
        """Verify which models are available."""
        response = await self.client.get(f"{self.base_url}/models")
        response.raise_for_status()

        available = {m['id'] for m in response.json().get('data', [])}

        return {model: model in available for model in required_models}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
```

---

## Part 7: Cost Estimation (Improved)

### 7.1 Dynamic Cost Estimation

```python
# src/config/cost_estimator.py

from dataclasses import dataclass
from typing import Dict, Optional
import httpx

@dataclass
class CostEstimate:
    """Detailed cost breakdown."""
    response_generation_cost: float
    judging_cost: float
    total_low: float
    total_high: float
    num_api_calls: int
    estimated_time_minutes: float
    breakdown_by_model: Dict[str, float]
    warnings: list

class CostEstimator:
    """Estimates API costs with dynamic pricing."""

    # Fallback pricing if API unavailable (per 1M tokens)
    FALLBACK_PRICING = {
        'google/gemini-3.0-pro': {'input': 1.25, 'output': 5.00},
        'google/gemini-3.0-flash': {'input': 0.075, 'output': 0.30},
        'openai/gpt-5.2': {'input': 2.50, 'output': 10.00},
        'openai/gpt-4.1': {'input': 0.15, 'output': 0.60},
        'anthropic/claude-opus-4.5': {'input': 3.00, 'output': 15.00},
        'anthropic/claude-sonnet': {'input': 0.80, 'output': 4.00},
    }

    # Token estimates vary by prompt complexity
    TOKEN_ESTIMATES = {
        'simple_prompt': {'input': 500, 'output': 300},
        'medium_prompt': {'input': 800, 'output': 400},
        'complex_prompt': {'input': 1500, 'output': 600},
        'judge_input': 1800,  # Both responses + context
        'judge_output': 150
    }

    def __init__(self, openrouter_client: Optional['OpenRouterClient'] = None):
        self.client = openrouter_client
        self._pricing_cache = None

    async def fetch_current_pricing(self) -> Dict[str, Dict[str, float]]:
        """Fetch current pricing from OpenRouter API."""
        if self._pricing_cache:
            return self._pricing_cache

        if not self.client:
            return self.FALLBACK_PRICING

        try:
            response = await self.client.client.get(
                "https://openrouter.ai/api/v1/models"
            )
            response.raise_for_status()

            pricing = {}
            for model in response.json().get('data', []):
                model_id = model['id']
                pricing[model_id] = {
                    'input': float(model.get('pricing', {}).get('prompt', 0)) * 1_000_000,
                    'output': float(model.get('pricing', {}).get('completion', 0)) * 1_000_000
                }

            self._pricing_cache = pricing
            return pricing

        except Exception as e:
            logger.warning(f"Could not fetch pricing: {e}, using fallback")
            return self.FALLBACK_PRICING

    async def estimate(self, config: 'EvalConfig') -> CostEstimate:
        """Estimate total cost for an evaluation run."""

        pricing = await self.fetch_current_pricing()
        warnings = []

        # Response generation cost
        response_cost = 0
        breakdown = {}

        for model in config.models:
            if model not in pricing:
                warnings.append(f"No pricing for {model}, using estimate")
                model_pricing = {'input': 2.0, 'output': 8.0}
            else:
                model_pricing = pricing[model]

            # Estimate tokens based on prompt complexity distribution
            avg_input = (
                self.TOKEN_ESTIMATES['simple_prompt']['input'] * 0.3 +
                self.TOKEN_ESTIMATES['medium_prompt']['input'] * 0.5 +
                self.TOKEN_ESTIMATES['complex_prompt']['input'] * 0.2
            )
            avg_output = (
                self.TOKEN_ESTIMATES['simple_prompt']['output'] * 0.3 +
                self.TOKEN_ESTIMATES['medium_prompt']['output'] * 0.5 +
                self.TOKEN_ESTIMATES['complex_prompt']['output'] * 0.2
            )

            input_cost = (config.num_prompts * avg_input / 1_000_000) * model_pricing['input']
            output_cost = (config.num_prompts * avg_output / 1_000_000) * model_pricing['output']

            model_cost = input_cost + output_cost
            response_cost += model_cost
            breakdown[model] = model_cost

        # Judging cost
        num_comparisons = config.num_prompts * len(config.model_pairs)
        num_judge_calls = (
            num_comparisons *
            len(config.judges) *
            config.votes_per_judge *
            len(config.personas)
        )

        judge_cost = 0
        for judge_model in config.judges:
            if judge_model not in pricing:
                judge_pricing = {'input': 2.0, 'output': 8.0}
            else:
                judge_pricing = pricing[judge_model]

            calls_per_judge = num_judge_calls / len(config.judges)
            input_cost = (calls_per_judge * self.TOKEN_ESTIMATES['judge_input'] / 1_000_000) * judge_pricing['input']
            output_cost = (calls_per_judge * self.TOKEN_ESTIMATES['judge_output'] / 1_000_000) * judge_pricing['output']

            model_judge_cost = input_cost + output_cost
            judge_cost += model_judge_cost
            breakdown[f"{judge_model} (judging)"] = model_judge_cost

        # Add buffer for retries and variance
        base_total = response_cost + judge_cost
        total_low = base_total * 0.85
        total_high = base_total * 1.25  # 25% buffer for retries

        # Time estimate
        total_api_calls = config.num_prompts * len(config.models) + num_judge_calls
        # Assume average 1.5s per call with parallelization
        estimated_minutes = (total_api_calls * 1.5) / 60 / config.parallelism

        return CostEstimate(
            response_generation_cost=response_cost,
            judging_cost=judge_cost,
            total_low=total_low,
            total_high=total_high,
            num_api_calls=total_api_calls,
            estimated_time_minutes=estimated_minutes,
            breakdown_by_model=breakdown,
            warnings=warnings
        )
```

---

## Part 8: Implementation Phases (Revised)

### Phase 0: Prerequisites (Before Coding)

**Duration**: 1-2 days

1. **Verify External Dependencies**
   - Run `scripts/verify_onet_schema.py` to confirm O*NET element IDs
   - Run `scripts/verify_openrouter_models.py` to confirm model availability
   - Download BLS occupation-industry matrix
   - Download SSA name data and Census surnames

2. **Create Seed Data**
   - Curate company database (100+ real companies across NAICS sectors)
   - Verify name data is properly formatted

3. **Environment Setup**
   - Set up `.env` with `OPENROUTER_API_KEY`
   - Install dependencies with `pip install -e .`

### Phase 1: Core Infrastructure (Week 1)

1. **Day 1-2**: Project structure, schemas, and database
   - Set up project structure
   - Implement Pydantic schemas for all data types
   - Implement SQLite schema and ResultsStore

2. **Day 3-4**: O*NET extraction and data pipeline
   - Implement ONetExtractor with verified element IDs
   - Implement NAICS mapper (with fallback for missing BLS data)
   - Implement company and name generation

3. **Day 5**: OpenRouter client and concurrency
   - Implement OpenRouterClient with full error handling
   - Implement ConcurrencyManager with rate limiting
   - Write integration tests

### Phase 2: Prompt Generation (Week 2)

1. **Day 1-2**: Three-phase pipeline core
   - Implement Phase 1 persona generation with retry logic
   - Implement Phase 2 algorithmic combination

2. **Day 3-4**: Enrichment and validation
   - Implement Phase 3 LLM enrichment
   - Implement diversity validation
   - Implement ambiguity and constraint generation

3. **Day 5**: Testing and refinement
   - Generate sample prompts and manually review
   - Tune generation parameters
   - Fix edge cases

### Phase 3: Evaluation Engine (Week 3)

1. **Day 1-2**: Core evaluation loop
   - Implement EvaluationOrchestrator
   - Implement response generation pipeline
   - Implement checkpoint integration

2. **Day 3-4**: Judging system
   - Implement JudgeEngine with dual personas
   - Implement robust JSON parsing
   - Implement majority-of-majorities aggregation

3. **Day 5**: Constraint checking and failure handling
   - Implement ConstraintChecker
   - Implement failure categorization
   - Implement auto-loss logic

### Phase 4: TUI and User Experience (Week 4)

1. **Day 1-2**: Progress dashboard
   - Implement ProgressApp with Textual
   - Real-time statistics updating
   - Interactive controls

2. **Day 3**: Results viewer
   - Implement ResultsViewerApp
   - Side-by-side comparison view
   - Filtering and navigation

3. **Day 4-5**: CLI and presets
   - Implement CLI with Typer
   - Implement cost estimation display
   - Implement all 10 presets

### Phase 5: Analysis and Reporting (Week 5)

1. **Day 1-2**: Statistical analysis
   - Implement win rate calculations with CIs
   - Implement Fleiss' Kappa
   - Implement significance tests

2. **Day 3-4**: Bias detection and weakness analysis
   - Implement position/length/format bias detection
   - Implement weakness identification
   - Implement dimension breakdowns

3. **Day 5**: PDF report generation
   - Implement chart generation
   - Implement PDF layout
   - Implement executive summary

### Phase 6: Testing and Hardening (Week 6)

1. **Day 1-2**: Unit and integration tests
   - Test all components
   - Test error paths
   - Test resume functionality

2. **Day 3-4**: End-to-end validation
   - Run preset 1-3 evaluations
   - Validate results make sense
   - Fix discovered issues

3. **Day 5**: Documentation and polish
   - Write README with usage examples
   - Document configuration options
   - Clean up code and add comments

---

## Part 9: Key Improvements Summary

| Area | Draft Issue | Improvement |
|------|-------------|-------------|
| External Data | No acquisition strategy | Explicit download instructions and verification scripts |
| O*NET Schema | Assumed element IDs | Schema verification before use |
| Model Names | Unverified | Verification script against OpenRouter API |
| Company Data | Source unclear | Hybrid approach: curated seed + LLM generation |
| Name Data | No download info | SSA + Census data with download instructions |
| Error Handling | Minimal in prompt generation | Retry logic with fallbacks at every stage |
| JSON Parsing | Assumed clean output | Multi-strategy robust parsing |
| Concurrency | Not addressed | Semaphores + token bucket rate limiting |
| Cost Estimation | Static values | Dynamic pricing from API |
| Constraint Checking | Not implemented | Full constraint verification system |
| Checkpoint | Basic implementation | Atomic writes with backup |
| Diversity Validation | Not addressed | Explicit validation with warnings |

---

## Appendix: Verification Scripts

These scripts MUST be run before implementation proceeds:

```bash
# 1. Verify O*NET schema
python scripts/verify_onet_schema.py

# 2. Verify OpenRouter models (requires API key)
export OPENROUTER_API_KEY=your_key_here
python scripts/verify_openrouter_models.py

# 3. Download BLS data
./scripts/download_bls_data.sh

# 4. Download name data
./scripts/download_name_data.sh

# 5. Run all verifications
./scripts/verify_all.sh
```

Only after all verifications pass should implementation begin.
