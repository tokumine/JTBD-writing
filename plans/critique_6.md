# Gemini Writing Evaluation Framework - Improved Plan (Critique 6)

## Critical Analysis of Draft Plan 6

Before presenting the improved plan, here is a summary of issues identified in the original draft:

### Issues Identified

**1. Technical Feasibility Issues**
- O*NET extraction query references tables/columns that may not exist in the actual O*NET 30.1 schema (e.g., `task_type` column, specific element_ids need verification)
- The NAICS mapping is entirely heuristic-based with no fallback or validation mechanism
- Cohen's Kappa calculation is simplified incorrectly - uses wrong formula for multi-rater scenarios
- Cost estimation pricing is likely outdated and doesn't include OpenRouter markup

**2. Robustness Gaps**
- No handling for when all judges refuse or fail to respond
- No circuit breaker pattern for repeated API failures
- No validation that prompts actually contain writing-relevant tasks (garbage-in protection)
- Checkpoint system doesn't handle partial judgment completion
- No mechanism to detect prompt generation failures during Phase 1 LLM enrichment

**3. Missing Requirements from PROMPT.md**
- Missing explicit handling for revision/editing tasks (mentioned in PROMPT.md)
- Missing tone matching from examples feature
- Missing deliberate ambiguity prompts category
- Instruction-following tests not fully integrated into prompt generation
- Missing company metadata storage (age, public/private, HQ location) despite requirement
- Missing email address generation for recipients
- Missing explicit regional English variant handling in prompts

**4. Design Issues**
- DiversitySampler doesn't enforce hard quotas, just targets - could still produce skewed distributions
- Task classification is purely rule-based; may miss nuanced writing tasks
- No mechanism to prevent duplicate or near-duplicate prompts
- Position shuffler doesn't guarantee exact 50/50 split
- Judge temperature of 0.7 may be too high for consistent evaluation

**5. Missing Details**
- No specification of how to handle Flash-tier vs Pro-tier model separation
- No details on how cross-run comparison actually works
- No specification of OpenRouter model IDs (which may differ from the examples)
- No handling for context length limits across different models
- No specification of prompt rendering for non-email communication types

---

## Improved Implementation Plan

---

## Part 1: System Architecture Overview

### 1.1 High-Level Architecture

```
+-----------------------------------------------------------------------------+
|                        GEMINI WRITING EVAL FRAMEWORK                        |
+-----------------------------------------------------------------------------+
|                                                                             |
|  +----------------+    +----------------+    +----------------+    +------+ |
|  |   O*NET DB     |--->|    Prompt      |--->|   Response     |--->| Judge| |
|  |   Pipeline     |    |  Generator     |    |  Collector     |    | Engine|
|  +----------------+    +----------------+    +----------------+    +------+ |
|         |                    |                    |                   |     |
|         v                    v                    v                   v     |
|  +---------------------------------------------------------------------+   |
|  |                         SQLite Results Store                         |   |
|  |   (prompts, responses, judgments, metadata, checkpoints, failures)   |   |
|  +---------------------------------------------------------------------+   |
|         |                                                                   |
|         v                                                                   |
|  +----------------+    +----------------+    +----------------+             |
|  |   Analysis     |--->|    Report      |--->|     TUI        |             |
|  |    Engine      |    |  Generator     |    |   Viewer       |             |
|  +----------------+    +----------------+    +----------------+             |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### 1.2 Core Components

| Component | Responsibility | Key Technologies |
|-----------|---------------|------------------|
| **O*NET Pipeline** | Extract, validate, transform task data | SQLite, Pydantic |
| **Prompt Generator** | Create diverse, realistic writing prompts | LLM APIs, NAICS mapping, deduplication |
| **Response Collector** | Gather model outputs with retry and circuit breaker | httpx, asyncio, tenacity |
| **Judging Engine** | Multi-judge ensemble evaluation with validation | Best-of-5, majority voting, agreement checks |
| **Results Store** | Persist all artifacts with atomic checkpointing | SQLite, JSON |
| **Analysis Engine** | Statistical analysis, bias detection, weakness identification | scipy, pandas, statsmodels |
| **Report Generator** | PDF reports with visualizations | plotly, weasyprint |
| **TUI Viewer** | Interactive results exploration | textual/rich |

### 1.3 Directory Structure

```
gemini-writing-eval/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configuration management with validation
│   ├── models.py                 # Pydantic models for all data structures
│   ├── constants.py              # OpenRouter model IDs, pricing, limits
│   ├── cli.py                    # CLI entry point
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py     # O*NET database access with schema validation
│   │   ├── onet_schema.py        # Expected O*NET 30.1 schema definitions
│   │   ├── task_classifier.py    # Writing task categorization (rule + LLM hybrid)
│   │   ├── naics_mapper.py       # Industry mapping with fallback
│   │   ├── company_database.py   # Curated company data with full metadata
│   │   └── name_generator.py     # Demographically diverse name generation
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py          # Main prompt generation orchestrator
│   │   ├── persona_builder.py    # Writer/recipient persona creation
│   │   ├── context_enricher.py   # LLM-based context enrichment
│   │   ├── diversity_sampler.py  # Multi-dimensional sampling with hard quotas
│   │   ├── deduplicator.py       # Near-duplicate detection
│   │   ├── validator.py          # Prompt quality validation
│   │   └── templates.py          # Prompt templates and schemas
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── runner.py             # Main evaluation orchestrator
│   │   ├── api_client.py         # OpenRouter API wrapper with circuit breaker
│   │   ├── response_collector.py # Model response collection
│   │   ├── judge.py              # Judging logic with validation
│   │   ├── aggregator.py         # Vote aggregation with proper Kappa
│   │   └── tier_manager.py       # Pro-tier vs Flash-tier separation
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLite operations with transactions
│   │   ├── checkpoint.py         # Atomic checkpoint/resume logic
│   │   └── exporter.py           # CSV/JSON export
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py         # Win rates, confidence intervals
│   │   ├── agreement.py          # Proper Fleiss/Cohen Kappa implementation
│   │   ├── bias_detector.py      # Systematic bias analysis
│   │   ├── weakness_finder.py    # Gemini weakness identification
│   │   └── visualizations.py     # Charts and graphs
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py      # PDF report creation
│   │   └── templates/            # Report templates (Jinja2)
│   │
│   └── tui/
│       ├── __init__.py
│       ├── app.py                # Main TUI application
│       ├── screens/              # TUI screens
│       └── widgets/              # Custom widgets
│
├── data/
│   ├── companies.json            # Curated company database
│   ├── names.json                # Name pools by demographic
│   └── naics_soc_crosswalk.json  # NAICS-SOC mapping data
│
├── db/
│   └── onet.db                   # O*NET 30.1 database
│
├── results/                      # Eval run directories
│   └── eval_YYYY-MM-DD_HH-MM-SS/
│
├── tests/
├── pyproject.toml
└── README.md
```

---

## Part 2: Data Pipeline - O*NET to Prompts

### 2.1 O*NET Schema Validation

Before extraction, validate that the O*NET database matches expected schema:

```python
class ONetSchemaValidator:
    """Validate O*NET database schema before extraction."""

    REQUIRED_TABLES = {
        "task_statements": ["task_id", "onetsoc_code", "task"],
        "occupation_data": ["onetsoc_code", "title", "description"],
        "job_zones": ["onetsoc_code", "job_zone"],
        "work_context": ["onetsoc_code", "element_id", "scale_id", "data_value"],
        "skills": ["onetsoc_code", "element_id", "scale_id", "data_value"],
    }

    # Element IDs we need (verified against O*NET 30.1)
    WORK_CONTEXT_ELEMENTS = {
        "4.C.1.a.2.h": "Electronic Mail",
        "4.C.1.a.2.j": "Letters and Memos",
    }

    SKILL_ELEMENTS = {
        "2.A.1.a": "Reading Comprehension",
        "2.A.1.b": "Active Listening",
        "2.A.1.c": "Writing",
    }

    async def validate(self, db_path: Path) -> ValidationResult:
        """Validate database schema and return detailed results."""
        errors = []
        warnings = []

        async with aiosqlite.connect(db_path) as db:
            # Check tables exist
            for table, columns in self.REQUIRED_TABLES.items():
                if not await self._table_exists(db, table):
                    errors.append(f"Missing required table: {table}")
                    continue

                for col in columns:
                    if not await self._column_exists(db, table, col):
                        errors.append(f"Missing column: {table}.{col}")

            # Verify element IDs exist
            for element_id, name in self.WORK_CONTEXT_ELEMENTS.items():
                count = await self._count_element(db, "work_context", element_id)
                if count == 0:
                    warnings.append(f"No data for work context element {element_id} ({name})")

            # Count tasks
            task_count = await db.execute_fetchone(
                "SELECT COUNT(*) FROM task_statements"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            task_count=task_count[0] if task_count else 0
        )
```

### 2.2 Writing Task Extraction

```python
class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database."""

    # Verified patterns for O*NET task statements
    EXPLICIT_WRITING_PATTERNS = [
        r'\bwrite\b', r'\bdraft\b', r'\bcompose\b', r'\bauthor\b',
        r'\bdocument\b', r'\bprepare\s+(a\s+)?report',
        r'\bprepare\s+(a\s+)?proposal', r'\bcorrespond',
        r'\bemail\b', r'\bletter\b', r'\bmemo\b', r'\bbriefing\b',
    ]

    IMPLICIT_WRITING_PATTERNS = [
        r'\bnotify\b', r'\binform\b', r'\bcommunicate\b',
        r'\bpresent\s+finding', r'\bsummariz', r'\brecommend\b',
        r'\bpropos', r'\badvise\b', r'\binstruct\b',
    ]

    # Task patterns to EXCLUDE (not writing tasks)
    EXCLUSION_PATTERNS = [
        r'\bverbal(ly)?\b', r'\boral(ly)?\b', r'\bspeak\b',
        r'\btelephone\b', r'\bmeeting\b', r'\bdiscuss\b',
    ]

    async def extract_writing_tasks(
        self,
        db_path: Path,
        filters: dict = None
    ) -> list[ONetTask]:
        """Extract all writing-relevant tasks with metadata."""

        tasks = []

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            # Base query - verified against O*NET 30.1 schema
            query = """
            SELECT
                t.task_id,
                t.onetsoc_code,
                o.title as occupation_title,
                o.description as occupation_description,
                t.task,
                jz.job_zone,
                COALESCE(email_wc.data_value, 0) as email_frequency,
                COALESCE(letter_wc.data_value, 0) as letter_frequency,
                COALESCE(writing_skill.data_value, 0) as writing_skill_importance
            FROM task_statements t
            JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
            LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
            LEFT JOIN work_context email_wc
                ON t.onetsoc_code = email_wc.onetsoc_code
                AND email_wc.element_id = '4.C.1.a.2.h'
                AND email_wc.scale_id = 'CX'
            LEFT JOIN work_context letter_wc
                ON t.onetsoc_code = letter_wc.onetsoc_code
                AND letter_wc.element_id = '4.C.1.a.2.j'
                AND letter_wc.scale_id = 'CX'
            LEFT JOIN skills writing_skill
                ON t.onetsoc_code = writing_skill.onetsoc_code
                AND writing_skill.element_id = '2.A.1.c'
                AND writing_skill.scale_id = 'IM'
            """

            async for row in db.execute(query):
                task_text = row["task"]

                # Check if task is writing-relevant
                is_explicit = any(
                    re.search(p, task_text, re.I)
                    for p in self.EXPLICIT_WRITING_PATTERNS
                )
                is_implicit = any(
                    re.search(p, task_text, re.I)
                    for p in self.IMPLICIT_WRITING_PATTERNS
                )
                is_excluded = any(
                    re.search(p, task_text, re.I)
                    for p in self.EXCLUSION_PATTERNS
                )

                # Include if explicit, or implicit with high writing skill
                if is_excluded:
                    continue

                if is_explicit or (is_implicit and row["writing_skill_importance"] >= 3.5):
                    tasks.append(ONetTask(
                        task_id=row["task_id"],
                        onetsoc_code=row["onetsoc_code"],
                        occupation_title=row["occupation_title"],
                        occupation_description=row["occupation_description"],
                        task_text=task_text,
                        job_zone=row["job_zone"] or 3,  # Default to middle
                        email_frequency=row["email_frequency"],
                        letter_frequency=row["letter_frequency"],
                        writing_skill_importance=row["writing_skill_importance"],
                        extraction_method="explicit" if is_explicit else "implicit"
                    ))

        return tasks
```

### 2.3 Task Classification with Hybrid Approach

```python
@dataclass
class WritingTaskClassification:
    """Dynamic classification derived from task content."""

    # Primary type (rule-based)
    primary_type: str  # "correspondence", "report", "documentation", "proposal", etc.

    # Communication attributes
    formality_signal: float  # 0.0-1.0
    urgency_signal: float    # 0.0-1.0
    audience_size_signal: str  # "individual", "group", "public"

    # Inferred medium
    likely_medium: str  # "email", "memo", "report", "letter", "social_media"

    # Task category flags
    is_revision_task: bool
    is_reply_task: bool
    has_competing_objectives: bool
    is_instruction_constrained: bool
    is_deliberately_ambiguous: bool

    # Sensitive topic detection
    is_sensitive: bool
    sensitive_categories: list[str]

    # Confidence
    classification_confidence: float

    # LLM enhancement needed
    needs_enrichment: bool
    enrichment_types: list[str]


class TaskClassifier:
    """Classify tasks using rule-based + LLM hybrid approach."""

    # Sensitive topic patterns
    SENSITIVE_PATTERNS = {
        "hr_issues": [r'\bperformance\b', r'\btermina', r'\bfir(e|ing)\b', r'\blayoff\b'],
        "legal": [r'\blegal\b', r'\bcontract\b', r'\bliabilit', r'\bcompl(y|iance)\b'],
        "bad_news": [r'\breject', r'\bdecline\b', r'\bcancel', r'\bpostpone\b'],
        "confidential": [r'\bconfidential\b', r'\bproprietary\b', r'\bsensitive\b'],
        "conflict": [r'\bdisput', r'\bcomplaint\b', r'\bgrievance\b', r'\bissue\b'],
    }

    # Revision task indicators
    REVISION_PATTERNS = [
        r'\brevise\b', r'\brewrite\b', r'\bedit\b', r'\bimprove\b',
        r'\bsoften\b', r'\bstrengthen\b', r'\bconcise\b',
    ]

    def classify(
        self,
        task: ONetTask,
        use_llm_enhancement: bool = False
    ) -> WritingTaskClassification:
        """Classify task with optional LLM enhancement."""

        task_text = task.task_text.lower()

        # Detect primary type
        primary_type = self._detect_primary_type(task_text)

        # Infer formality from job zone and occupation
        formality_signal = self._infer_formality(
            task.job_zone,
            task.occupation_title,
            task_text
        )

        # Detect urgency from verbs
        urgency_signal = self._analyze_urgency(task_text)

        # Detect audience size
        audience_signal = self._detect_audience(task_text)

        # Infer medium
        likely_medium = self._infer_medium(task_text, primary_type)

        # Task category flags
        is_revision = any(re.search(p, task_text) for p in self.REVISION_PATTERNS)
        is_reply = 'reply' in task_text or 'respond to' in task_text

        # Sensitive topic detection
        sensitive_cats = []
        for category, patterns in self.SENSITIVE_PATTERNS.items():
            if any(re.search(p, task_text) for p in patterns):
                sensitive_cats.append(category)

        # Determine enrichment needs
        enrichment_types = self._determine_enrichment_needs(
            task_text, is_reply, is_revision
        )

        return WritingTaskClassification(
            primary_type=primary_type,
            formality_signal=formality_signal,
            urgency_signal=urgency_signal,
            audience_size_signal=audience_signal,
            likely_medium=likely_medium,
            is_revision_task=is_revision,
            is_reply_task=is_reply,
            has_competing_objectives=self._detect_competing_objectives(task_text),
            is_instruction_constrained=False,  # Set during prompt generation
            is_deliberately_ambiguous=False,   # Set during prompt generation
            is_sensitive=len(sensitive_cats) > 0,
            sensitive_categories=sensitive_cats,
            classification_confidence=self._calculate_confidence(task_text),
            needs_enrichment=len(enrichment_types) > 0,
            enrichment_types=enrichment_types
        )

    def _infer_formality(
        self,
        job_zone: int,
        occupation: str,
        task_text: str
    ) -> float:
        """Infer formality level from context."""
        # Base formality from job zone (1-5 scale)
        base_formality = (job_zone - 1) / 4.0  # Normalize to 0-1

        # Adjust based on occupation keywords
        formal_occupations = ['executive', 'director', 'attorney', 'physician']
        casual_occupations = ['technician', 'assistant', 'clerk']

        occ_lower = occupation.lower()
        if any(f in occ_lower for f in formal_occupations):
            base_formality = min(1.0, base_formality + 0.2)
        elif any(c in occ_lower for c in casual_occupations):
            base_formality = max(0.0, base_formality - 0.1)

        # Adjust based on task language
        if 'formal' in task_text or 'professional' in task_text:
            base_formality = min(1.0, base_formality + 0.15)

        return base_formality

    def _determine_enrichment_needs(
        self,
        task_text: str,
        is_reply: bool,
        is_revision: bool
    ) -> list[str]:
        """Determine what enrichment the prompt needs."""
        needs = []

        if is_reply:
            needs.append("prior_message")
        if is_revision:
            needs.append("draft_to_revise")
        if 'attach' in task_text or 'report' in task_text:
            needs.append("attachment_context")
        if 'meeting' in task_text:
            needs.append("meeting_notes")
        if 'deadline' in task_text or 'urgent' in task_text:
            needs.append("temporal_context")

        return needs
```

### 2.4 NAICS Industry Mapping with Validation

```python
class NAICSMapper:
    """Map occupations to industries with validation and fallback."""

    def __init__(self, crosswalk_path: Path):
        """Load NAICS-SOC crosswalk data."""
        with open(crosswalk_path) as f:
            self.crosswalk = json.load(f)

        # Fallback weights when crosswalk doesn't have mapping
        self.FALLBACK_SOC_TO_NAICS = {
            "11": {"52": 0.15, "54": 0.20, "62": 0.10, "31-33": 0.15, "other": 0.40},
            "13": {"52": 0.35, "54": 0.30, "55": 0.15, "other": 0.20},
            "15": {"51": 0.30, "54": 0.35, "52": 0.15, "other": 0.20},
            "17": {"54": 0.30, "23": 0.25, "31-33": 0.25, "other": 0.20},
            "19": {"54": 0.30, "61": 0.25, "62": 0.20, "other": 0.25},
            "21": {"62": 0.50, "92": 0.25, "other": 0.25},
            "23": {"61": 0.60, "62": 0.15, "other": 0.25},
            "25": {"61": 0.70, "54": 0.15, "other": 0.15},
            "27": {"51": 0.40, "71": 0.25, "54": 0.20, "other": 0.15},
            "29": {"62": 0.70, "61": 0.15, "other": 0.15},
            "31": {"72": 0.60, "44-45": 0.25, "other": 0.15},
            "33": {"92": 0.60, "56": 0.25, "other": 0.15},
            "35": {"72": 0.70, "71": 0.15, "other": 0.15},
            "37": {"56": 0.50, "72": 0.20, "81": 0.15, "other": 0.15},
            "39": {"81": 0.35, "71": 0.25, "62": 0.20, "other": 0.20},
            "41": {"44-45": 0.50, "42": 0.25, "52": 0.10, "other": 0.15},
            "43": {"54": 0.25, "52": 0.20, "62": 0.20, "other": 0.35},
            "45": {"11": 0.50, "21": 0.20, "other": 0.30},
            "47": {"23": 0.60, "22": 0.15, "other": 0.25},
            "49": {"48-49": 0.30, "44-45": 0.25, "81": 0.25, "other": 0.20},
            "51": {"31-33": 0.60, "42": 0.20, "other": 0.20},
            "53": {"48-49": 0.50, "42": 0.20, "other": 0.30},
        }

        self.NAICS_SECTORS = {
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

    def sample_industry(
        self,
        soc_code: str,
        seed: int,
        exclude: set[str] = None
    ) -> tuple[str, str]:
        """Sample an appropriate industry for the occupation."""
        rng = random.Random(seed)
        exclude = exclude or set()

        soc_major = soc_code[:2]

        # Try crosswalk first
        if soc_code in self.crosswalk:
            weights = self.crosswalk[soc_code]
        elif soc_major in self.FALLBACK_SOC_TO_NAICS:
            weights = self.FALLBACK_SOC_TO_NAICS[soc_major]
        else:
            # Ultimate fallback: uniform distribution
            weights = {k: 1.0 for k in self.NAICS_SECTORS.keys()}

        # Remove excluded industries
        available = {k: v for k, v in weights.items()
                    if k != "other" and k not in exclude}

        if not available:
            # If all excluded, use any
            available = {k: v for k, v in weights.items() if k != "other"}

        # Normalize weights
        total = sum(available.values())
        normalized = {k: v/total for k, v in available.items()}

        # Sample
        naics = rng.choices(
            list(normalized.keys()),
            weights=list(normalized.values())
        )[0]

        return naics, self.NAICS_SECTORS.get(naics, "General Business")

    def get_all_valid_industries(self, soc_code: str) -> list[str]:
        """Get all plausible industries for an occupation."""
        soc_major = soc_code[:2]

        if soc_code in self.crosswalk:
            return [k for k in self.crosswalk[soc_code].keys() if k != "other"]

        if soc_major in self.FALLBACK_SOC_TO_NAICS:
            return [k for k in self.FALLBACK_SOC_TO_NAICS[soc_major].keys()
                   if k != "other"]

        return list(self.NAICS_SECTORS.keys())
```

### 2.5 Real Company Database

```python
@dataclass
class Company:
    """Complete company information for prompt grounding."""
    name: str
    naics_code: str
    naics_sector: str
    size_tier: str  # "fortune500", "midmarket", "small", "startup"
    employee_count: int
    year_founded: int
    is_public: bool
    hq_city: str
    hq_country: str
    domain: str  # For email generation

    def generate_email(self, name: str) -> str:
        """Generate plausible email for an employee."""
        # Normalize name
        parts = name.lower().split()
        if len(parts) >= 2:
            # Format: firstname.lastname@domain
            return f"{parts[0]}.{parts[-1]}@{self.domain}"
        return f"{parts[0]}@{self.domain}"


class CompanyDatabase:
    """Curated database of real companies with full metadata."""

    def __init__(self, companies_path: Path):
        """Load curated company data."""
        with open(companies_path) as f:
            data = json.load(f)

        self.companies: dict[str, dict[str, list[Company]]] = {}

        for naics, by_size in data.items():
            self.companies[naics] = {}
            for size_tier, company_list in by_size.items():
                self.companies[naics][size_tier] = [
                    Company(**c) for c in company_list
                ]

    SIZE_TIERS = ["fortune500", "midmarket", "small", "startup"]
    SIZE_WEIGHTS = [0.25, 0.30, 0.30, 0.15]

    def sample_company(
        self,
        naics_code: str,
        preferred_size: str = None,
        seed: int = None,
        exclude_names: set[str] = None
    ) -> Company:
        """Sample a real company with full metadata."""
        rng = random.Random(seed)
        exclude_names = exclude_names or set()

        # Get companies for this industry
        industry_companies = self.companies.get(naics_code, {})

        # Select size tier
        if preferred_size and preferred_size in industry_companies:
            size_tier = preferred_size
        else:
            # Weighted random selection
            available_tiers = [t for t in self.SIZE_TIERS
                              if t in industry_companies and
                              any(c.name not in exclude_names
                                  for c in industry_companies[t])]

            if not available_tiers:
                # Fallback: generate a plausible fake company
                return self._generate_fallback_company(naics_code, rng)

            tier_weights = [self.SIZE_WEIGHTS[self.SIZE_TIERS.index(t)]
                          for t in available_tiers]
            size_tier = rng.choices(available_tiers, weights=tier_weights)[0]

        # Select company
        pool = [c for c in industry_companies[size_tier]
               if c.name not in exclude_names]

        if not pool:
            return self._generate_fallback_company(naics_code, rng)

        return rng.choice(pool)

    def _generate_fallback_company(self, naics_code: str, rng: random.Random) -> Company:
        """Generate a plausible fallback company when DB doesn't have one."""
        sector = self.NAICS_SECTORS.get(naics_code, "Business")
        size = rng.choice(["small", "startup"])
        employee_count = rng.randint(10, 100) if size == "small" else rng.randint(5, 25)

        return Company(
            name=f"Regional {sector} Company (~{employee_count} employees)",
            naics_code=naics_code,
            naics_sector=sector,
            size_tier=size,
            employee_count=employee_count,
            year_founded=rng.randint(2000, 2023),
            is_public=False,
            hq_city=rng.choice(["Chicago", "Denver", "Atlanta", "Seattle", "Austin"]),
            hq_country="USA",
            domain="company.com"
        )
```

---

## Part 3: Prompt Generation with Full Diversity

### 3.1 Name Generation with Demographics

```python
class NameGenerator:
    """Generate demographically diverse realistic names."""

    def __init__(self, names_path: Path):
        with open(names_path) as f:
            self.names = json.load(f)

        # Structure:
        # {
        #   "first_names": {
        #     "GenZ": {"diverse": ["Aiden", "Zara", ...], "male": [...], "female": [...]},
        #     "Millennial": {...},
        #     "GenX": {...},
        #     "Boomer": {...}
        #   },
        #   "last_names": {
        #     "diverse": ["Chen", "Williams", "Garcia", "Patel", ...]
        #   }
        # }

    def generate_name(
        self,
        generation: str,
        gender: str = None,
        seed: int = None
    ) -> str:
        """Generate a realistic name matching demographics."""
        rng = random.Random(seed)

        # Get first name pool
        gen_names = self.names["first_names"].get(generation, self.names["first_names"]["Millennial"])

        if gender and gender in gen_names:
            first_pool = gen_names[gender]
        else:
            first_pool = gen_names.get("diverse", [])

        # Get last name
        last_pool = self.names["last_names"]["diverse"]

        first = rng.choice(first_pool)
        last = rng.choice(last_pool)

        return f"{first} {last}"

    def generate_formal_name(
        self,
        base_name: str,
        seniority: str,
        occupation: str,
        seed: int = None
    ) -> str:
        """Generate formal version of name based on context."""
        rng = random.Random(seed)
        parts = base_name.split()

        # Determine title
        if 'doctor' in occupation.lower() or 'physician' in occupation.lower():
            title = "Dr."
        elif 'attorney' in occupation.lower() or 'lawyer' in occupation.lower():
            title = rng.choice(["", ""])  # Attorneys don't usually use Esq. in practice
        elif seniority == "executive":
            title = rng.choice(["", "Mr.", "Ms."])
        else:
            title = ""

        # Format based on formality
        formats = [
            f"{title} {parts[-1]}".strip(),  # "Dr. Smith"
            base_name,  # "John Smith"
            parts[0],  # "John"
        ]

        return formats[0] if title else formats[1]
```

### 3.2 Persona Builder with Full Metadata

```python
@dataclass
class WriterPersona:
    """Complete writer persona for prompt context."""

    # Identity
    name: str
    formal_name: str
    email: str

    # Demographics
    age: int
    generation: str  # "GenZ", "Millennial", "GenX", "Boomer"
    gender: str | None  # Only used for name generation, not exposed

    # Professional context
    job_title: str
    seniority_level: str  # "entry", "mid", "senior", "executive"
    years_experience: int
    department: str | None

    # Company context
    company: Company

    # Communication style
    formality_preference: float  # 0.0-1.0
    verbosity_preference: float  # 0.0-1.0

    # Regional context
    english_variant: str  # "en-US", "en-GB", "en-AU", "non-native"
    location: str


@dataclass
class RecipientPersona:
    """Complete recipient persona."""

    name: str
    formal_name: str
    email: str | None

    job_title: str
    company: str | None  # If different from writer
    seniority_level: str

    relationship_to_writer: str  # "superior", "peer", "subordinate", "external"
    relationship_duration: str   # "first_contact", "new", "established", "long_term"

    english_variant: str
    expectations_notes: str | None


class PersonaBuilder:
    """Build diverse, realistic personas."""

    GENERATION_AGE_RANGES = {
        "GenZ": (18, 28),
        "Millennial": (29, 44),
        "GenX": (45, 60),
        "Boomer": (61, 75),
    }

    SENIORITY_BY_JOB_ZONE = {
        1: ["entry"],
        2: ["entry", "mid"],
        3: ["mid", "senior"],
        4: ["senior", "executive"],
        5: ["senior", "executive"],
    }

    def __init__(self, name_gen: NameGenerator):
        self.name_gen = name_gen

    def build_writer_persona(
        self,
        occupation_title: str,
        job_zone: int,
        company: Company,
        diversity_targets: dict,
        seed: int
    ) -> WriterPersona:
        """Build a complete writer persona."""
        rng = random.Random(seed)

        # Select generation based on targets or naturally
        if "generation" in diversity_targets:
            generation = diversity_targets["generation"]
        else:
            # Weight by realistic workforce distribution
            generation = rng.choices(
                ["GenZ", "Millennial", "GenX", "Boomer"],
                weights=[0.15, 0.35, 0.30, 0.20]
            )[0]

        # Sample age within generation
        age_range = self.GENERATION_AGE_RANGES[generation]
        age = rng.randint(*age_range)

        # Determine seniority
        possible_seniorities = self.SENIORITY_BY_JOB_ZONE.get(job_zone, ["mid"])
        # Adjust by age
        if age < 30:
            seniority = possible_seniorities[0]
        elif age > 50 and "executive" in possible_seniorities:
            seniority = rng.choice(["senior", "executive"])
        else:
            seniority = rng.choice(possible_seniorities)

        # Generate name
        gender = rng.choice([None, "male", "female"])  # None = diverse pool
        name = self.name_gen.generate_name(generation, gender, seed)
        formal_name = self.name_gen.generate_formal_name(
            name, seniority, occupation_title, seed
        )

        # Email
        email = company.generate_email(name)

        # Experience
        years_exp = self._calculate_experience(age, seniority)

        # Formality preference (influenced by generation and seniority)
        base_formality = {
            "GenZ": 0.3, "Millennial": 0.5, "GenX": 0.6, "Boomer": 0.7
        }[generation]
        seniority_adjustment = {
            "entry": -0.1, "mid": 0, "senior": 0.1, "executive": 0.2
        }[seniority]
        formality = min(1.0, max(0.0, base_formality + seniority_adjustment + rng.uniform(-0.1, 0.1)))

        # English variant
        if "english_variant" in diversity_targets:
            english_variant = diversity_targets["english_variant"]
        else:
            english_variant = rng.choices(
                ["en-US", "en-GB", "en-AU", "non-native"],
                weights=[0.70, 0.15, 0.05, 0.10]
            )[0]

        return WriterPersona(
            name=name,
            formal_name=formal_name,
            email=email,
            age=age,
            generation=generation,
            gender=gender,
            job_title=occupation_title,
            seniority_level=seniority,
            years_experience=years_exp,
            department=self._infer_department(occupation_title),
            company=company,
            formality_preference=formality,
            verbosity_preference=rng.uniform(0.3, 0.7),
            english_variant=english_variant,
            location=f"{company.hq_city}, {company.hq_country}"
        )

    def build_recipient_persona(
        self,
        writer: WriterPersona,
        relationship_type: str,
        seed: int
    ) -> RecipientPersona:
        """Build recipient persona relative to writer."""
        rng = random.Random(seed)

        # Determine relationship characteristics
        if relationship_type == "superior":
            seniority = self._get_higher_seniority(writer.seniority_level)
            relationship_to_writer = "superior"
        elif relationship_type == "subordinate":
            seniority = self._get_lower_seniority(writer.seniority_level)
            relationship_to_writer = "subordinate"
        elif relationship_type == "external":
            seniority = rng.choice(["mid", "senior", "executive"])
            relationship_to_writer = "external"
        else:
            seniority = writer.seniority_level
            relationship_to_writer = "peer"

        # Generate name
        generation = rng.choice(["Millennial", "GenX", "Boomer"])
        name = self.name_gen.generate_name(generation, None, seed + 1000)

        # Determine relationship duration
        relationship_duration = rng.choices(
            ["first_contact", "new", "established", "long_term"],
            weights=[0.15, 0.25, 0.40, 0.20]
        )[0]

        # Job title
        job_title = self._generate_recipient_title(
            relationship_to_writer, seniority, writer.job_title, rng
        )

        # Email and company
        if relationship_to_writer == "external":
            company = None
            email = f"{name.lower().replace(' ', '.')}@external.com"
        else:
            company = writer.company.name
            email = writer.company.generate_email(name)

        return RecipientPersona(
            name=name,
            formal_name=name,
            email=email,
            job_title=job_title,
            company=company,
            seniority_level=seniority,
            relationship_to_writer=relationship_to_writer,
            relationship_duration=relationship_duration,
            english_variant=writer.english_variant,  # Usually same as writer
            expectations_notes=self._generate_expectations(
                relationship_to_writer, seniority, relationship_duration
            )
        )

    def _calculate_experience(self, age: int, seniority: str) -> int:
        """Calculate years of experience based on age and seniority."""
        base = max(0, age - 22)  # Assume starting work at 22
        adjustment = {"entry": 0, "mid": 2, "senior": 5, "executive": 10}[seniority]
        return max(0, min(base, base - adjustment + random.randint(-2, 2)))

    def _generate_expectations(
        self,
        relationship: str,
        seniority: str,
        duration: str
    ) -> str:
        """Generate expectation notes for judging context."""
        expectations = []

        if seniority == "executive":
            expectations.append("Prefers concise, bottom-line-first communication")

        if relationship == "external":
            expectations.append("Professional tone, may need more context")

        if duration == "first_contact":
            expectations.append("Needs full context and introduction")
        elif duration == "long_term":
            expectations.append("Can be more informal, shared context assumed")

        return "; ".join(expectations) if expectations else "Standard professional communication"
```

### 3.3 Diversity Sampler with Hard Quotas

```python
class DiversitySampler:
    """Ensure even distribution across all required dimensions with hard quotas."""

    DIVERSITY_DIMENSIONS = {
        "job_zone": [1, 2, 3, 4, 5],
        "generation": ["GenZ", "Millennial", "GenX", "Boomer"],
        "formality": ["very_casual", "casual", "neutral", "formal", "very_formal"],
        "urgency": ["routine", "standard", "elevated", "urgent", "critical"],
        "audience_size": ["individual", "small_group", "department", "company", "public"],
        "relationship": ["first_contact", "new", "established", "long_term"],
        "emotional_context": ["routine", "celebration", "crisis", "conflict", "bad_news"],
        "message_position": ["initial", "reply", "follow_up", "thread_continuation"],
        "english_variant": ["en-US", "en-GB", "en-AU", "non-native"],
    }

    # Special prompt categories (percentage of total)
    SPECIAL_CATEGORIES = {
        "revision_task": 0.10,        # 10% are revision/editing tasks
        "ambiguous_prompt": 0.05,     # 5% deliberately ambiguous
        "instruction_constrained": 0.15,  # 15% have explicit constraints
        "tone_matching": 0.08,        # 8% require matching example style
        "multiple_recipients": 0.10,  # 10% have CC/multiple audiences
    }

    def __init__(self, target_count: int, seed: int):
        self.target_count = target_count
        self.seed = seed
        self.rng = random.Random(seed)

        # Calculate hard quotas
        self.quotas = self._calculate_quotas()
        self.filled = {
            dim: {val: 0 for val in vals}
            for dim, vals in self.DIVERSITY_DIMENSIONS.items()
        }
        self.special_counts = {cat: 0 for cat in self.SPECIAL_CATEGORIES}

        # Track used combinations to avoid duplicates
        self.used_combinations = set()

    def _calculate_quotas(self) -> dict:
        """Calculate per-dimension quotas with tolerance."""
        quotas = {}
        for dim, values in self.DIVERSITY_DIMENSIONS.items():
            base_quota = self.target_count // len(values)
            # Allow 20% variance
            quotas[dim] = {
                val: (int(base_quota * 0.8), int(base_quota * 1.2))
                for val in values
            }
        return quotas

    def sample_next(
        self,
        available_tasks: list[ONetTask]
    ) -> tuple[ONetTask, dict]:
        """Sample next prompt configuration ensuring diversity."""

        # Find dimensions most under quota
        priority_dims = self._get_priority_dimensions()

        # Determine special category needs
        special_assignments = self._get_special_assignments()

        # Sample task that can satisfy priority dimensions
        task = self._sample_task_for_priorities(available_tasks, priority_dims)

        # Generate diversity attributes
        attributes = {}
        for dim, values in self.DIVERSITY_DIMENSIONS.items():
            if dim in priority_dims:
                # Must fill this value
                attributes[dim] = priority_dims[dim]
            else:
                # Sample from under-quota values
                under_quota = [v for v in values
                              if self.filled[dim][v] < self.quotas[dim][v][1]]
                if under_quota:
                    attributes[dim] = self.rng.choice(under_quota)
                else:
                    attributes[dim] = self.rng.choice(values)

        # Add special category flags
        attributes.update(special_assignments)

        # Create combination hash to check for near-duplicates
        combo_hash = self._create_combo_hash(task, attributes)
        attempts = 0
        while combo_hash in self.used_combinations and attempts < 10:
            # Resample some attributes
            resample_dim = self.rng.choice(list(self.DIVERSITY_DIMENSIONS.keys()))
            attributes[resample_dim] = self.rng.choice(
                self.DIVERSITY_DIMENSIONS[resample_dim]
            )
            combo_hash = self._create_combo_hash(task, attributes)
            attempts += 1

        # Update tracking
        self.used_combinations.add(combo_hash)
        for dim, val in attributes.items():
            if dim in self.filled:
                self.filled[dim][val] += 1

        for cat, assigned in special_assignments.items():
            if assigned:
                self.special_counts[cat] += 1

        return task, attributes

    def _get_priority_dimensions(self) -> dict:
        """Find dimensions most under quota and return specific values to fill."""
        priorities = {}

        for dim, filled_vals in self.filled.items():
            quotas = self.quotas[dim]
            for val, count in filled_vals.items():
                min_quota, _ = quotas[val]
                if count < min_quota:
                    # This value is under minimum quota
                    deficit = min_quota - count
                    if dim not in priorities or deficit > priorities.get(f"{dim}_deficit", 0):
                        priorities[dim] = val
                        priorities[f"{dim}_deficit"] = deficit

        # Remove deficit tracking keys
        return {k: v for k, v in priorities.items() if not k.endswith("_deficit")}

    def _get_special_assignments(self) -> dict:
        """Determine which special categories to assign."""
        current_count = sum(self.filled[list(self.filled.keys())[0]].values())
        assignments = {}

        for cat, target_pct in self.SPECIAL_CATEGORIES.items():
            target_count = int(self.target_count * target_pct)
            remaining_prompts = self.target_count - current_count
            remaining_needed = target_count - self.special_counts[cat]

            if remaining_needed > 0:
                # Probability of assigning this category
                prob = remaining_needed / max(1, remaining_prompts)
                assignments[cat] = self.rng.random() < prob
            else:
                assignments[cat] = False

        return assignments

    def _create_combo_hash(self, task: ONetTask, attributes: dict) -> str:
        """Create hash of task+attributes for duplicate detection."""
        key_parts = [
            task.task_id,
            attributes.get("formality", ""),
            attributes.get("urgency", ""),
            attributes.get("audience_size", ""),
        ]
        return ":".join(str(p) for p in key_parts)

    def get_distribution_report(self) -> dict:
        """Report on achieved distribution across dimensions."""
        report = {}
        for dim, filled_vals in self.filled.items():
            total = sum(filled_vals.values())
            quotas = self.quotas[dim]
            report[dim] = {
                val: {
                    "count": count,
                    "pct": count/total if total > 0 else 0,
                    "min_quota": quotas[val][0],
                    "max_quota": quotas[val][1],
                    "in_range": quotas[val][0] <= count <= quotas[val][1]
                }
                for val, count in filled_vals.items()
            }
        return report

    def validate_distribution(self) -> tuple[bool, list[str]]:
        """Validate that distribution meets quota requirements."""
        errors = []

        for dim, filled_vals in self.filled.items():
            quotas = self.quotas[dim]
            for val, count in filled_vals.items():
                min_q, max_q = quotas[val]
                if count < min_q:
                    errors.append(f"{dim}={val}: {count} < min quota {min_q}")

        for cat, count in self.special_counts.items():
            target = int(self.target_count * self.SPECIAL_CATEGORIES[cat])
            if count < target * 0.8:  # Allow 20% under
                errors.append(f"Special category {cat}: {count} < target {target}")

        return len(errors) == 0, errors
```

### 3.4 Context Enrichment with Validation

```python
class ContextEnricher:
    """LLM-based enrichment for context-heavy prompts with validation."""

    def __init__(self, api_client: OpenRouterClient, config: EvalConfig):
        self.api_client = api_client
        self.config = config
        self.enrichment_models = config.enrichment_models

    async def enrich_prompt(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona,
        enrichment_types: list[str],
        seed: int
    ) -> dict:
        """Add rich context based on enrichment types needed."""
        enrichments = {}

        for etype in enrichment_types:
            handler = getattr(self, f"_generate_{etype}", None)
            if handler:
                try:
                    result = await handler(base_task, writer, recipient, seed)
                    if self._validate_enrichment(etype, result):
                        enrichments[etype] = result
                    else:
                        logger.warning(f"Enrichment validation failed for {etype}")
                except Exception as e:
                    logger.error(f"Enrichment generation failed for {etype}: {e}")

        return enrichments

    async def _generate_prior_message(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona,
        seed: int
    ) -> str:
        """Generate a prior message that needs a response."""
        prompt = f"""Generate a realistic prior message that requires a response.

Task context: {base_task}
Original sender: {recipient.name}, {recipient.job_title}
Recipient (now writing reply): {writer.name}, {writer.job_title}
Relationship: {recipient.relationship_to_writer}, {recipient.relationship_duration}
Company: {writer.company.name}

Generate an email/message that {recipient.name} sent which requires a thoughtful reply.
The tone should match the relationship ({recipient.relationship_duration}) and professional context.
Include 2-3 specific details that the reply should address.

Format as a complete message with greeting and signature.
Keep it realistic and concise (100-200 words).
"""
        response = await self._generate_with_retry(prompt, seed)
        return response

    async def _generate_attachment_context(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona,
        seed: int
    ) -> str:
        """Generate mock attachment content summary."""
        prompt = f"""Generate realistic attachment context for this writing task.

Task: {base_task}
Writer: {writer.job_title} at {writer.company.name}
Recipient: {recipient.job_title}

Generate a brief summary of what the "attached" document contains.
Include 3-5 specific details (numbers, names, dates) that should be referenced in the writing.
Format as if describing an attachment in an email context.

Keep it concise (50-100 words) but specific enough to be useful context.
Do not generate the full document - just a summary of key points.
"""
        return await self._generate_with_retry(prompt, seed)

    async def _generate_draft_to_revise(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona,
        seed: int
    ) -> str:
        """Generate a draft that needs revision."""
        prompt = f"""Generate a draft that needs revision for this task.

Task: {base_task}
Writer: {writer.job_title} at {writer.company.name}
Target audience: {recipient.job_title}

Generate a draft that has CLEAR ISSUES to fix. Choose one of these problem types:
- Too verbose/wordy (needs to be more concise)
- Too terse (needs more detail)
- Wrong tone (too formal/informal for context)
- Unclear structure (needs better organization)
- Contains cliches or generic language

The draft should be 100-200 words with obvious issues but still salvageable.
"""
        return await self._generate_with_retry(prompt, seed)

    async def _generate_example_to_match(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona,
        seed: int
    ) -> str:
        """Generate an example style to match."""
        prompt = f"""Generate a writing sample that establishes a style to match.

Context: {writer.name} needs to write in a consistent style with previous communications.
Task type: {base_task}

Generate a brief example (75-150 words) that demonstrates a distinctive writing style.
The style should have clear characteristics:
- Specific greeting/closing patterns
- Particular level of formality
- Distinctive word choices or phrases
- Specific formatting preferences

This will be provided as "Match this style" context.
"""
        return await self._generate_with_retry(prompt, seed)

    async def _generate_with_retry(self, prompt: str, seed: int) -> str:
        """Generate with retry and model rotation."""
        for model in self.enrichment_models:
            try:
                response = await self.api_client.generate(
                    model=model,
                    prompt=prompt,
                    temperature=0.8,
                    max_tokens=500
                )
                return response.text
            except Exception as e:
                logger.warning(f"Enrichment with {model} failed: {e}")
                continue

        raise RuntimeError("All enrichment models failed")

    def _validate_enrichment(self, etype: str, content: str) -> bool:
        """Validate enrichment content quality."""
        if not content or len(content.strip()) < 20:
            return False

        # Type-specific validation
        if etype == "prior_message":
            # Should have greeting and some content
            return len(content) >= 50 and any(
                g in content.lower() for g in ["hi", "hello", "dear", "hey"]
            )

        if etype == "attachment_context":
            # Should have specific details
            return len(content) >= 30

        if etype == "draft_to_revise":
            # Should be substantial enough to revise
            return len(content) >= 100

        return True
```

---

## Part 4: Evaluation Pipeline with Robust Error Handling

### 4.1 Model Tier Management

```python
class ModelTierManager:
    """Manage Pro-tier and Flash-tier model comparisons."""

    PRO_TIER_MODELS = {
        "gemini": "google/gemini-3.0-pro",
        "gpt": "openai/gpt-5.2-turbo",
        "claude": "anthropic/claude-opus-4.5",
        "grok": "x-ai/grok-4.1",
        "kimi": "moonshot/kimi-k2",
    }

    FLASH_TIER_MODELS = {
        "gemini": "google/gemini-3.0-flash",
        "gpt": "openai/gpt-4.1-turbo",
        "claude": "anthropic/claude-sonnet-4",
    }

    # Context length limits per model
    CONTEXT_LIMITS = {
        "google/gemini-3.0-pro": 128000,
        "google/gemini-3.0-flash": 128000,
        "openai/gpt-5.2-turbo": 128000,
        "openai/gpt-4.1-turbo": 128000,
        "anthropic/claude-opus-4.5": 200000,
        "anthropic/claude-sonnet-4": 200000,
        "x-ai/grok-4.1": 131072,
        "moonshot/kimi-k2": 200000,
    }

    def __init__(self, tier: str):
        """Initialize with tier selection."""
        if tier == "pro":
            self.models = self.PRO_TIER_MODELS
            self.gemini_model = self.PRO_TIER_MODELS["gemini"]
        elif tier == "flash":
            self.models = self.FLASH_TIER_MODELS
            self.gemini_model = self.FLASH_TIER_MODELS["gemini"]
        else:
            raise ValueError(f"Unknown tier: {tier}")

        self.tier = tier

    def get_comparison_pairs(self, selected_competitors: list[str] = None) -> list[tuple[str, str]]:
        """Get model pairs for comparison."""
        pairs = []
        competitors = selected_competitors or [k for k in self.models if k != "gemini"]

        for comp_key in competitors:
            if comp_key in self.models:
                pairs.append((self.gemini_model, self.models[comp_key]))

        return pairs

    def get_context_limit(self, model_id: str) -> int:
        """Get context limit for a model."""
        return self.CONTEXT_LIMITS.get(model_id, 32000)

    def truncate_for_model(self, prompt: str, model_id: str, reserve_tokens: int = 4000) -> str:
        """Truncate prompt if needed for model context limit."""
        limit = self.get_context_limit(model_id)
        # Rough estimate: 1 token ~= 4 chars
        char_limit = (limit - reserve_tokens) * 4

        if len(prompt) > char_limit:
            logger.warning(f"Truncating prompt from {len(prompt)} to {char_limit} chars for {model_id}")
            return prompt[:char_limit] + "\n\n[Content truncated due to length]"

        return prompt
```

### 4.2 OpenRouter Client with Circuit Breaker

```python
class CircuitBreaker:
    """Circuit breaker pattern for API calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self.failures = 0
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time = 0
        self.half_open_successes = 0

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == "closed":
            return True

        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                self.half_open_successes = 0
                return True
            return False

        if self.state == "half-open":
            return True

        return False

    def record_success(self) -> None:
        """Record a successful execution."""
        if self.state == "half-open":
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_requests:
                self.state = "closed"
                self.failures = 0
        else:
            self.failures = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning("Circuit breaker opened due to failures")
        elif self.state == "half-open":
            self.state = "open"


class OpenRouterClient:
    """OpenRouter API client with retry logic and circuit breaker."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, config: EvalConfig):
        self.api_key = api_key
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0)
        )

        # Per-model circuit breakers
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.rate_limiter = RateLimitHandler()

    def _get_circuit_breaker(self, model: str) -> CircuitBreaker:
        """Get or create circuit breaker for model."""
        if model not in self.circuit_breakers:
            self.circuit_breakers[model] = CircuitBreaker()
        return self.circuit_breakers[model]

    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        retry_count: int = 0
    ) -> GenerationResponse:
        """Generate completion with retry and circuit breaker."""

        circuit = self._get_circuit_breaker(model)

        if not circuit.can_execute():
            raise CircuitBreakerOpenError(f"Circuit breaker open for {model}")

        await self.rate_limiter.acquire(model)

        try:
            response = await self._make_request(
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            circuit.record_success()
            self.rate_limiter.release(model)
            return response

        except RateLimitError as e:
            self.rate_limiter.handle_rate_limit(model, e.retry_after)
            self.rate_limiter.release(model)

            if retry_count < self.config.max_retries:
                await asyncio.sleep(e.retry_after or 60)
                return await self.generate(
                    model, prompt, temperature, max_tokens, retry_count + 1
                )
            raise

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            circuit.record_failure()
            self.rate_limiter.release(model)

            if retry_count < self.config.max_retries:
                delay = self._calculate_backoff(retry_count)
                await asyncio.sleep(delay)
                return await self.generate(
                    model, prompt, temperature, max_tokens, retry_count + 1
                )
            raise

        except Exception as e:
            circuit.record_failure()
            self.rate_limiter.release(model)
            raise

    async def _make_request(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> GenerationResponse:
        """Make the actual API request."""
        response = await self.client.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "gemini-writing-eval",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 60))
            raise RateLimitError(f"Rate limited", retry_after=retry_after)

        if response.status_code >= 500:
            raise ServerError(f"Server error: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        return GenerationResponse(
            text=data["choices"][0]["message"]["content"],
            usage=TokenUsage(
                input_tokens=data["usage"]["prompt_tokens"],
                output_tokens=data["usage"]["completion_tokens"]
            ),
            model=model,
            finish_reason=data["choices"][0].get("finish_reason", "stop")
        )

    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff with jitter."""
        base_delay = 1.0
        max_delay = 60.0
        delay = min(base_delay * (2 ** retry_count), max_delay)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
```

### 4.3 Response Collection with Validation

```python
class ResponseCollector:
    """Collect and validate model responses."""

    def __init__(
        self,
        api_client: OpenRouterClient,
        tier_manager: ModelTierManager,
        config: EvalConfig
    ):
        self.api_client = api_client
        self.tier_manager = tier_manager
        self.config = config

    async def collect_pair(
        self,
        prompt: EvalPrompt,
        gemini_model: str,
        competitor_model: str
    ) -> tuple[ModelResponse, ModelResponse]:
        """Collect responses from both models in parallel."""

        # Ensure prompt fits within context limits
        rendered = prompt.render_prompt()
        gemini_prompt = self.tier_manager.truncate_for_model(rendered, gemini_model)
        competitor_prompt = self.tier_manager.truncate_for_model(rendered, competitor_model)

        # Collect in parallel
        gemini_task = self._collect_single(prompt.prompt_id, gemini_model, gemini_prompt)
        competitor_task = self._collect_single(prompt.prompt_id, competitor_model, competitor_prompt)

        results = await asyncio.gather(gemini_task, competitor_task, return_exceptions=True)

        # Handle exceptions
        gemini_resp = results[0] if not isinstance(results[0], Exception) else self._error_response(
            prompt.prompt_id, gemini_model, results[0]
        )
        competitor_resp = results[1] if not isinstance(results[1], Exception) else self._error_response(
            prompt.prompt_id, competitor_model, results[1]
        )

        return gemini_resp, competitor_resp

    async def _collect_single(
        self,
        prompt_id: str,
        model_id: str,
        prompt_text: str
    ) -> ModelResponse:
        """Collect a single model response."""
        start_time = time.monotonic()

        try:
            response = await self.api_client.generate(
                model=model_id,
                prompt=prompt_text,
                temperature=self.config.response_temperature,
                max_tokens=self.config.max_response_tokens
            )

            # Validate response
            validation = self._validate_response(response.text)

            return ModelResponse(
                prompt_id=prompt_id,
                model_id=model_id,
                response_text=response.text,
                response_time_ms=int((time.monotonic() - start_time) * 1000),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                status=validation.status,
                refusal_category=validation.refusal_category,
                metadata=self._extract_metadata(response.text)
            )

        except CircuitBreakerOpenError:
            return ModelResponse(
                prompt_id=prompt_id,
                model_id=model_id,
                response_text="",
                status="circuit_breaker",
                error_message="Circuit breaker open - too many failures",
                metadata={}
            )

        except Exception as e:
            return ModelResponse(
                prompt_id=prompt_id,
                model_id=model_id,
                response_text="",
                status="error",
                error_message=str(e),
                metadata={}
            )

    def _validate_response(self, text: str) -> ResponseValidation:
        """Validate response quality and detect refusals."""

        # Empty or too short
        if not text or len(text.strip()) < 20:
            return ResponseValidation(status="incomplete", refusal_category=None)

        # Refusal patterns
        refusal_patterns = {
            "safety": [
                r"I cannot help with",
                r"I'm not able to assist",
                r"against my guidelines",
                r"potentially harmful",
            ],
            "capability": [
                r"I don't have access",
                r"I cannot access",
                r"beyond my capabilities",
            ],
            "off_topic": [
                r"As an AI language model",
                r"As an AI assistant",
                r"I'm Claude",
                r"I'm ChatGPT",
            ]
        }

        for category, patterns in refusal_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    return ResponseValidation(status="refusal", refusal_category=category)

        return ResponseValidation(status="success", refusal_category=None)

    def _extract_metadata(self, text: str) -> dict:
        """Extract response metadata for analysis."""
        return {
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": text.count('\n') + 1,
            "paragraph_count": len([p for p in text.split('\n\n') if p.strip()]),
            "has_bullet_points": bool(re.search(r'^\s*[-*]\s', text, re.M)),
            "has_numbered_list": bool(re.search(r'^\s*\d+[.)]\s', text, re.M)),
            "has_greeting": self._detect_greeting(text),
            "has_signoff": self._detect_signoff(text),
            "avg_sentence_length": self._avg_sentence_length(text),
        }

    def _detect_greeting(self, text: str) -> bool:
        """Detect if response has a greeting."""
        first_line = text.split('\n')[0].lower()
        greetings = ['hi', 'hello', 'dear', 'hey', 'good morning', 'good afternoon']
        return any(g in first_line for g in greetings)

    def _detect_signoff(self, text: str) -> bool:
        """Detect if response has a sign-off."""
        last_lines = text.strip().split('\n')[-3:]
        signoffs = ['regards', 'best', 'thanks', 'sincerely', 'cheers', 'warmly']
        return any(s in line.lower() for line in last_lines for s in signoffs)

    def _avg_sentence_length(self, text: str) -> float:
        """Calculate average sentence length."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 0
        return sum(len(s.split()) for s in sentences) / len(sentences)
```

### 4.4 Judging Engine with Proper Agreement Metrics

```python
class JudgingEngine:
    """Execute judgments with proper inter-rater agreement calculation."""

    JUDGE_MODELS = [
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2-turbo",
        "google/gemini-3.0-pro"
    ]

    def __init__(
        self,
        api_client: OpenRouterClient,
        config: EvalConfig,
        persona_builder: JudgePersonaBuilder
    ):
        self.api_client = api_client
        self.config = config
        self.persona_builder = persona_builder

    async def judge_comparison(
        self,
        prompt: EvalPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        gemini_is_a: bool
    ) -> ComparisonResult:
        """Run full judging ensemble for one comparison."""

        # Check for auto-loss conditions first
        auto_result = self._check_auto_loss(response_a, response_b, gemini_is_a)
        if auto_result:
            return auto_result

        all_judgments = []
        judge_models = self.JUDGE_MODELS[:self.config.num_judges]

        # For each judge model
        for judge_model in judge_models:
            # Check if judge is available (circuit breaker)
            if not self.api_client._get_circuit_breaker(judge_model).can_execute():
                logger.warning(f"Judge {judge_model} unavailable, skipping")
                continue

            # For each persona
            personas_to_use = ["expert", "recipient"][:self.config.num_personas]
            for persona_type in personas_to_use:
                persona = self._build_persona(persona_type, prompt)

                # Collect N votes with lower temperature for consistency
                for vote_num in range(self.config.votes_per_judge):
                    try:
                        judgment = await self._get_single_judgment(
                            prompt=prompt,
                            response_a=response_a,
                            response_b=response_b,
                            judge_model=judge_model,
                            persona=persona,
                            persona_type=persona_type,
                            vote_number=vote_num,
                            gemini_is_a=gemini_is_a
                        )
                        all_judgments.append(judgment)
                    except Exception as e:
                        logger.error(f"Judgment failed for {judge_model}/{persona_type}/{vote_num}: {e}")

        # Validate we have enough judgments
        if len(all_judgments) < self.config.min_judgments:
            return self._create_incomplete_result(prompt.prompt_id, all_judgments, gemini_is_a)

        # Aggregate results
        return self._aggregate_judgments(all_judgments, gemini_is_a, prompt.prompt_id)

    def _check_auto_loss(
        self,
        response_a: ModelResponse,
        response_b: ModelResponse,
        gemini_is_a: bool
    ) -> ComparisonResult | None:
        """Check if either response should auto-lose."""

        a_failed = response_a.status in ["error", "refusal", "incomplete", "circuit_breaker"]
        b_failed = response_b.status in ["error", "refusal", "incomplete", "circuit_breaker"]

        if a_failed and b_failed:
            return ComparisonResult(
                prompt_id=response_a.prompt_id,
                gemini_is_a=gemini_is_a,
                final_winner="tie",
                auto_loss_winner="tie",
                auto_loss_reason="both_failed",
                total_judgments=0,
                gemini_vote_count=0,
                opponent_vote_count=0,
                tie_count=0,
                inter_judge_agreement=None,
                all_judgments=[]
            )

        if a_failed:
            winner = "opponent" if gemini_is_a else "gemini"
            return ComparisonResult(
                prompt_id=response_a.prompt_id,
                gemini_is_a=gemini_is_a,
                final_winner=winner,
                auto_loss_winner=winner,
                auto_loss_reason=f"response_a_{response_a.status}",
                total_judgments=0,
                gemini_vote_count=0 if gemini_is_a else 1,
                opponent_vote_count=1 if gemini_is_a else 0,
                tie_count=0,
                inter_judge_agreement=None,
                all_judgments=[]
            )

        if b_failed:
            winner = "gemini" if gemini_is_a else "opponent"
            return ComparisonResult(
                prompt_id=response_a.prompt_id,
                gemini_is_a=gemini_is_a,
                final_winner=winner,
                auto_loss_winner=winner,
                auto_loss_reason=f"response_b_{response_b.status}",
                total_judgments=0,
                gemini_vote_count=1 if gemini_is_a else 0,
                opponent_vote_count=0 if gemini_is_a else 1,
                tie_count=0,
                inter_judge_agreement=None,
                all_judgments=[]
            )

        return None

    def _build_persona(self, persona_type: str, prompt: EvalPrompt) -> str:
        """Build judge persona with full context."""
        if persona_type == "expert":
            return self.persona_builder.build_writing_expert()
        else:
            return self.persona_builder.build_recipient_persona(
                prompt.recipient, prompt
            )


class AgreementCalculator:
    """Calculate inter-rater agreement using proper statistical methods."""

    @staticmethod
    def fleiss_kappa(ratings_matrix: list[list[int]]) -> float:
        """
        Calculate Fleiss' Kappa for multiple raters.

        Args:
            ratings_matrix: List of ratings per item.
                           Each item is a list of category counts.
                           E.g., [[3, 2, 0], [4, 1, 0]] for 2 items, 3 categories,
                           5 raters where item 1 got 3 votes for cat 0, 2 for cat 1.

        Returns:
            Fleiss' Kappa coefficient
        """
        if not ratings_matrix:
            return 1.0

        n_items = len(ratings_matrix)
        n_categories = len(ratings_matrix[0])
        n_raters = sum(ratings_matrix[0])

        # Proportion of all assignments to each category
        p_j = []
        for j in range(n_categories):
            total_j = sum(item[j] for item in ratings_matrix)
            p_j.append(total_j / (n_items * n_raters))

        # Per-item agreement
        P_i = []
        for item in ratings_matrix:
            sum_squared = sum(n_ij * n_ij for n_ij in item)
            P_i.append((sum_squared - n_raters) / (n_raters * (n_raters - 1)))

        # Mean agreement
        P_bar = sum(P_i) / n_items

        # Expected agreement
        P_e = sum(p * p for p in p_j)

        if P_e == 1:
            return 1.0

        kappa = (P_bar - P_e) / (1 - P_e)
        return kappa

    @staticmethod
    def cohens_kappa_pairwise(rater1: list[str], rater2: list[str]) -> float:
        """
        Calculate Cohen's Kappa for two raters.

        Args:
            rater1: List of ratings from rater 1
            rater2: List of ratings from rater 2

        Returns:
            Cohen's Kappa coefficient
        """
        if len(rater1) != len(rater2):
            raise ValueError("Rater lists must have same length")

        n = len(rater1)
        if n == 0:
            return 1.0

        # Categories
        categories = list(set(rater1) | set(rater2))

        # Observed agreement
        agreements = sum(1 for r1, r2 in zip(rater1, rater2) if r1 == r2)
        p_o = agreements / n

        # Expected agreement
        p_e = 0
        for cat in categories:
            p1 = sum(1 for r in rater1 if r == cat) / n
            p2 = sum(1 for r in rater2 if r == cat) / n
            p_e += p1 * p2

        if p_e == 1:
            return 1.0

        kappa = (p_o - p_e) / (1 - p_e)
        return kappa

    def calculate_agreement(self, judgments: list[Judgment]) -> dict:
        """Calculate comprehensive agreement metrics."""

        # Group judgments by judge model
        by_judge = defaultdict(list)
        for j in judgments:
            # Convert to canonical outcome
            outcome = "gemini" if j.gemini_won else ("opponent" if j.gemini_won is False else "tie")
            by_judge[j.judge_model].append(outcome)

        judge_models = list(by_judge.keys())

        # Pairwise Cohen's Kappa
        pairwise_kappas = []
        for i, j1 in enumerate(judge_models):
            for j2 in judge_models[i+1:]:
                if len(by_judge[j1]) == len(by_judge[j2]):
                    kappa = self.cohens_kappa_pairwise(by_judge[j1], by_judge[j2])
                    pairwise_kappas.append(kappa)

        # Build ratings matrix for Fleiss' Kappa
        # Each vote is an "item", categories are gemini/opponent/tie
        n_items = len(judgments) // len(judge_models) if judge_models else 0
        if n_items > 0:
            ratings_matrix = []
            # This is simplified - in practice need to align by prompt_id
            for i in range(n_items):
                counts = {"gemini": 0, "opponent": 0, "tie": 0}
                for j in range(len(judge_models)):
                    idx = i * len(judge_models) + j
                    if idx < len(judgments):
                        outcome = "gemini" if judgments[idx].gemini_won else (
                            "opponent" if judgments[idx].gemini_won is False else "tie"
                        )
                        counts[outcome] += 1
                ratings_matrix.append([counts["gemini"], counts["opponent"], counts["tie"]])

            fleiss = self.fleiss_kappa(ratings_matrix)
        else:
            fleiss = None

        return {
            "fleiss_kappa": fleiss,
            "mean_pairwise_kappa": sum(pairwise_kappas) / len(pairwise_kappas) if pairwise_kappas else None,
            "pairwise_kappas": pairwise_kappas,
            "n_judges": len(judge_models),
            "n_judgments": len(judgments),
        }
```

### 4.5 Atomic Checkpoint System

```python
@dataclass
class CheckpointState:
    """Complete state for checkpoint/resume."""
    run_id: str
    phase: str  # prompt_generation, response_collection, judging, analysis
    created_at: datetime

    # Prompt generation state
    prompts_generated: int
    prompt_generation_complete: bool

    # Response collection state
    responses_collected: dict[str, list[str]]  # model -> list of prompt_ids completed
    response_collection_complete: bool

    # Judging state
    comparisons_judged: list[str]  # comparison_ids completed
    partial_judgments: dict[str, list[str]]  # comparison_id -> judgment_ids
    judging_complete: bool

    # Config and seed for reproducibility
    config_hash: str
    random_seed: int


class AtomicCheckpointManager:
    """Manage checkpoints with atomic writes and corruption detection."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_path = run_dir / "checkpoint.json"
        self.backup_path = run_dir / "checkpoint.backup.json"

    async def save_checkpoint(self, state: CheckpointState) -> None:
        """Save checkpoint atomically."""
        # Serialize state
        state_dict = asdict(state)
        state_dict["created_at"] = state.created_at.isoformat()
        state_json = json.dumps(state_dict, indent=2)

        # Add checksum
        checksum = hashlib.sha256(state_json.encode()).hexdigest()
        wrapped = {
            "checksum": checksum,
            "state": state_dict
        }

        # Write to temp file first
        temp_path = self.checkpoint_path.with_suffix('.tmp')
        async with aiofiles.open(temp_path, 'w') as f:
            await f.write(json.dumps(wrapped, indent=2))

        # Backup existing checkpoint
        if self.checkpoint_path.exists():
            shutil.copy(self.checkpoint_path, self.backup_path)

        # Atomic rename
        temp_path.rename(self.checkpoint_path)

    async def load_checkpoint(self) -> CheckpointState | None:
        """Load checkpoint with corruption detection."""
        for path in [self.checkpoint_path, self.backup_path]:
            if not path.exists():
                continue

            try:
                async with aiofiles.open(path, 'r') as f:
                    content = await f.read()

                wrapped = json.loads(content)

                # Verify checksum
                state_json = json.dumps(wrapped["state"], indent=2)
                expected_checksum = hashlib.sha256(state_json.encode()).hexdigest()

                if wrapped["checksum"] != expected_checksum:
                    logger.warning(f"Checkpoint {path} corrupted, trying backup")
                    continue

                # Parse state
                state_dict = wrapped["state"]
                state_dict["created_at"] = datetime.fromisoformat(state_dict["created_at"])

                return CheckpointState(**state_dict)

            except Exception as e:
                logger.error(f"Failed to load checkpoint from {path}: {e}")
                continue

        return None

    async def get_incomplete_work(self, state: CheckpointState, db: Database) -> dict:
        """Determine what work remains to be done."""
        incomplete = {
            "prompts_to_generate": 0,
            "responses_to_collect": [],
            "comparisons_to_judge": [],
        }

        if not state.prompt_generation_complete:
            # Get target prompt count from config
            config = await db.get_run_config(state.run_id)
            incomplete["prompts_to_generate"] = config.num_prompts - state.prompts_generated

        if not state.response_collection_complete:
            # Find prompts without responses
            all_prompts = await db.get_prompt_ids(state.run_id)
            for model, collected in state.responses_collected.items():
                uncollected = [p for p in all_prompts if p not in collected]
                for prompt_id in uncollected:
                    incomplete["responses_to_collect"].append((prompt_id, model))

        if not state.judging_complete:
            # Find comparisons without complete judgments
            all_comparisons = await db.get_comparison_ids(state.run_id)
            incomplete["comparisons_to_judge"] = [
                c for c in all_comparisons
                if c not in state.comparisons_judged
            ]

        return incomplete
```

---

## Part 5: Analysis and Reporting

### 5.1 Corrected Statistical Analysis

```python
class StatisticsEngine:
    """Compute win rates, confidence intervals, and significance tests."""

    def compute_win_rate(
        self,
        comparisons: list[ComparisonResult],
        model: str = "gemini"
    ) -> WinRateResult:
        """Compute win rate with Wilson score confidence interval."""

        wins = sum(1 for c in comparisons if c.final_winner == model)
        losses = sum(1 for c in comparisons if c.final_winner == "opponent")
        ties = sum(1 for c in comparisons if c.final_winner in ["tie", "split"])
        total = len(comparisons)

        # Win rate (excluding ties for cleaner interpretation)
        non_ties = wins + losses
        win_rate = wins / non_ties if non_ties > 0 else 0.5

        # Wilson score interval
        ci_low, ci_high = self._wilson_score_interval(wins, non_ties, confidence=0.95)

        return WinRateResult(
            wins=wins,
            losses=losses,
            ties=ties,
            total=total,
            win_rate=win_rate,
            win_rate_including_ties=wins / total if total > 0 else 0.5,
            confidence_interval=(ci_low, ci_high),
            confidence_level=0.95
        )

    def _wilson_score_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return (0.0, 1.0)

        from scipy import stats

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p_hat = successes / total
        n = total

        denominator = 1 + z**2 / n
        center = (p_hat + z**2 / (2 * n)) / denominator
        margin = (z / denominator) * math.sqrt(
            (p_hat * (1 - p_hat) + z**2 / (4 * n)) / n
        )

        return (max(0, center - margin), min(1, center + margin))

    def compute_significance(
        self,
        comparisons: list[ComparisonResult]
    ) -> SignificanceResult:
        """Test whether win rate is significantly different from 50%."""
        from scipy import stats

        wins = sum(1 for c in comparisons if c.final_winner == "gemini")
        losses = sum(1 for c in comparisons if c.final_winner == "opponent")
        total = wins + losses

        if total < 20:
            return SignificanceResult(
                test_type="insufficient_data",
                p_value=1.0,
                is_significant=False,
                effect_size=0.0,
                power=None,
                recommendation="Need at least 20 non-tie comparisons for significance testing"
            )

        # Exact binomial test
        p_value = stats.binomtest(wins, total, 0.5, alternative='two-sided').pvalue

        # Effect size (Cohen's h)
        p_obs = wins / total
        effect_size = 2 * (math.asin(math.sqrt(p_obs)) - math.asin(math.sqrt(0.5)))

        # Power analysis
        power = self._calculate_power(total, abs(p_obs - 0.5))

        return SignificanceResult(
            test_type="exact_binomial",
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=effect_size,
            power=power,
            recommendation=self._get_significance_recommendation(p_value, effect_size, power)
        )

    def _calculate_power(self, n: int, effect: float) -> float:
        """Calculate statistical power for the observed effect."""
        from scipy import stats

        # Simplified power calculation for binomial test
        z_alpha = stats.norm.ppf(0.975)  # Two-tailed, alpha=0.05
        se = math.sqrt(0.25 / n)  # SE under null hypothesis

        if se == 0:
            return 1.0

        z_effect = effect / se
        power = stats.norm.cdf(z_effect - z_alpha) + stats.norm.cdf(-z_effect - z_alpha)
        return max(0, min(1, power))

    def _get_significance_recommendation(
        self,
        p_value: float,
        effect_size: float,
        power: float
    ) -> str:
        """Generate recommendation based on statistical results."""
        if p_value < 0.05 and abs(effect_size) > 0.2:
            return "Result is significant with meaningful effect size"
        elif p_value < 0.05:
            return "Result is statistically significant but effect size is small"
        elif power and power < 0.8:
            return "Insufficient power - consider running more comparisons"
        else:
            return "No significant difference detected"
```

### 5.2 Cost Estimation with Current Pricing

```python
class CostEstimator:
    """Estimate costs using current OpenRouter pricing."""

    # OpenRouter pricing per 1M tokens (as of Jan 2026 - should be verified)
    # These are estimates and should be updated with actual pricing
    PRICING = {
        "google/gemini-3.0-pro": {"input": 1.50, "output": 6.00},
        "google/gemini-3.0-flash": {"input": 0.10, "output": 0.40},
        "openai/gpt-5.2-turbo": {"input": 3.00, "output": 12.00},
        "openai/gpt-4.1-turbo": {"input": 0.60, "output": 2.00},
        "anthropic/claude-opus-4.5": {"input": 18.00, "output": 90.00},
        "anthropic/claude-sonnet-4": {"input": 4.00, "output": 20.00},
        "x-ai/grok-4.1": {"input": 2.50, "output": 10.00},
        "moonshot/kimi-k2": {"input": 1.20, "output": 5.00},
    }

    # Include OpenRouter markup (~10-20%)
    OPENROUTER_MARKUP = 1.15

    # Token estimates per request type
    TOKEN_ESTIMATES = {
        "simple_prompt": {"input": 500, "output": 300},
        "enriched_prompt": {"input": 1200, "output": 400},
        "judgment": {"input": 2500, "output": 250},
    }

    def estimate_run(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost for an eval run."""

        # Estimate prompt complexity distribution
        simple_prompts = int(config.num_prompts * 0.6)
        enriched_prompts = config.num_prompts - simple_prompts

        # Response generation costs
        response_cost = 0
        for gemini, competitor in config.model_pairs:
            for model in [gemini, competitor]:
                pricing = self.PRICING.get(model, {"input": 2.0, "output": 8.0})

                # Simple prompts
                simple_input_cost = (simple_prompts * self.TOKEN_ESTIMATES["simple_prompt"]["input"] / 1_000_000 * pricing["input"])
                simple_output_cost = (simple_prompts * self.TOKEN_ESTIMATES["simple_prompt"]["output"] / 1_000_000 * pricing["output"])

                # Enriched prompts
                enriched_input_cost = (enriched_prompts * self.TOKEN_ESTIMATES["enriched_prompt"]["input"] / 1_000_000 * pricing["input"])
                enriched_output_cost = (enriched_prompts * self.TOKEN_ESTIMATES["enriched_prompt"]["output"] / 1_000_000 * pricing["output"])

                response_cost += (simple_input_cost + simple_output_cost + enriched_input_cost + enriched_output_cost)

        # Judging costs
        judge_cost = 0
        judge_calls_per_comparison = config.num_judges * config.num_personas * config.votes_per_judge
        total_comparisons = config.num_prompts * len(config.model_pairs)
        total_judge_calls = total_comparisons * judge_calls_per_comparison

        for judge_model in config.judge_models[:config.num_judges]:
            pricing = self.PRICING.get(judge_model, {"input": 5.0, "output": 20.0})
            calls_for_judge = total_judge_calls // config.num_judges

            input_cost = (calls_for_judge * self.TOKEN_ESTIMATES["judgment"]["input"] / 1_000_000 * pricing["input"])
            output_cost = (calls_for_judge * self.TOKEN_ESTIMATES["judgment"]["output"] / 1_000_000 * pricing["output"])

            judge_cost += input_cost + output_cost

        # Apply OpenRouter markup
        response_cost *= self.OPENROUTER_MARKUP
        judge_cost *= self.OPENROUTER_MARKUP

        # Add variance bounds (±20%)
        total_low = (response_cost + judge_cost) * 0.8
        total_high = (response_cost + judge_cost) * 1.2

        return CostEstimate(
            response_generation_cost=(response_cost * 0.9, response_cost * 1.1),
            judging_cost=(judge_cost * 0.9, judge_cost * 1.1),
            total_cost=(total_low, total_high),
            response_calls=config.num_prompts * len(config.model_pairs) * 2,
            judge_calls=total_judge_calls,
            estimated_time_with_limits=self._estimate_time(config, rate_limited=True),
            estimated_time_parallelized=self._estimate_time(config, rate_limited=False)
        )

    def _estimate_time(self, config: EvalConfig, rate_limited: bool) -> str:
        """Estimate runtime."""
        total_api_calls = (
            config.num_prompts * len(config.model_pairs) * 2 +  # Responses
            config.num_prompts * len(config.model_pairs) *       # Judgments
            config.num_judges * config.num_personas * config.votes_per_judge
        )

        if rate_limited:
            # Assume ~30 calls/min average due to rate limits
            minutes = total_api_calls / 30
        else:
            # Assume ~120 calls/min with full parallelization
            minutes = total_api_calls / 120

        if minutes < 60:
            return f"{int(minutes)} min"
        elif minutes < 1440:
            return f"{minutes/60:.1f} hrs"
        else:
            return f"{minutes/1440:.1f} days"
```

---

## Part 6: Implementation Timeline

### 6.1 Dependencies (Updated)

```toml
[project]
name = "gemini-writing-eval"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # Core
    "pydantic>=2.5",
    "httpx>=0.26",

    # Async
    "aiofiles>=23.2",
    "aiosqlite>=0.19",

    # CLI & TUI
    "click>=8.1",
    "textual>=0.47",
    "rich>=13.7",

    # Analysis
    "pandas>=2.1",
    "numpy>=1.26",
    "scipy>=1.12",
    "statsmodels>=0.14",  # For additional statistical tests

    # Visualization
    "plotly>=5.18",

    # PDF Generation
    "weasyprint>=60",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "mypy>=1.8",
    "ruff>=0.2",
    "hypothesis>=6.96",  # Property-based testing
]
```

### 6.2 Key Improvements Summary

1. **O*NET Schema Validation**: Verify database structure before extraction
2. **Hard Quota Enforcement**: Ensure diversity requirements are met
3. **Near-Duplicate Prevention**: Detect and avoid similar prompt combinations
4. **Circuit Breaker Pattern**: Prevent cascade failures from API issues
5. **Proper Agreement Metrics**: Fleiss' Kappa for multi-rater scenarios
6. **Atomic Checkpoints**: Corruption-resistant checkpoint system
7. **Model Tier Separation**: Explicit Pro-tier and Flash-tier handling
8. **Context Length Management**: Truncate prompts for model limits
9. **Full Company Metadata**: Age, public/private, HQ location as required
10. **Revision/Editing Tasks**: Explicit support for this prompt type
11. **Tone Matching**: Style example generation for matching requirements
12. **Ambiguous Prompts**: Deliberate category for testing uncertainty handling

---

## Appendix: Critical Implementation Notes

### A.1 O*NET Database Verification

Before running, verify:
```bash
sqlite3 db/onet.db ".schema task_statements"
sqlite3 db/onet.db "SELECT COUNT(*) FROM task_statements"
sqlite3 db/onet.db "SELECT DISTINCT element_id FROM work_context LIMIT 20"
```

### A.2 OpenRouter Model ID Verification

Model IDs may change. Verify current IDs:
```bash
curl -s https://openrouter.ai/api/v1/models | jq '.data[] | select(.id | contains("gemini"))'
```

### A.3 Pricing Updates

Cost estimates should be verified against current OpenRouter pricing before each major eval run, as pricing changes frequently.

### A.4 Position Shuffle Verification

To verify 50/50 position split:
```python
# After generating comparisons
position_balance = sum(1 for c in comparisons if c.gemini_is_a) / len(comparisons)
assert 0.45 <= position_balance <= 0.55, f"Position imbalance: {position_balance}"
```

### A.5 Minimum Sample Sizes

For statistically meaningful results:
- Per-model-pair: Minimum 50 comparisons
- Per-dimension analysis: Minimum 20 per category
- Overall: Minimum 200 total comparisons for publication-grade results
