# Gemini Writing Evaluation Framework - Master Plan

## Executive Summary

This master plan synthesizes insights from 6 independent critiques and rewrites of the initial draft plans. It represents the unified, consensus-driven implementation approach for building a robust writing evaluation framework that compares Gemini 3.0 Pro/Flash against competing frontier LLMs on realistic professional writing tasks.

### Key Design Principles (Consensus Across All Critiques)

1. **Data-Driven Diversity**: Let O*NET task statements drive writing task variety programmatically - avoid hardcoded categories
2. **Verified External Dependencies**: All external data sources (O*NET schema, OpenRouter model IDs, BLS data) must be verified before implementation
3. **Robust Error Handling**: Every API call, file operation, and data transformation must have proper error handling with fallbacks
4. **Dual-Persona Judging**: Each comparison evaluated by BOTH writing expert AND simulated recipient personas
5. **Statistical Rigor**: Majority-of-majorities voting, proper inter-rater agreement metrics, confidence intervals
6. **Full Resumability**: Checkpoint system with atomic writes enabling complete recovery from any failure

---

## Part 1: System Architecture

### 1.1 High-Level Architecture (Consensus View)

```
+-----------------------------------------------------------------------------+
|                     GEMINI WRITING EVALUATION FRAMEWORK                      |
+-----------------------------------------------------------------------------+
|                                                                              |
|  +----------------+    +----------------+    +----------------+              |
|  |   VALIDATION   |    |    PROMPT      |    |   RESPONSE     |              |
|  |   & STARTUP    |--->|   GENERATION   |--->|   COLLECTOR    |              |
|  | (Schema/Model) |    | (3-Phase)      |    | (Parallel)     |              |
|  +----------------+    +----------------+    +----------------+              |
|         |                     |                     |                        |
|         v                     v                     v                        |
|  +----------------------------------------------------------------------+   |
|  |                       EVALUATION ENGINE                               |   |
|  |  Response Pairs --> Position Shuffle --> Judge Ensemble --> Aggregate |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------------------------------------------------------------+   |
|  |                       DATA LAYER (SQLite + JSON)                      |   |
|  |  Prompts | Responses | Judgments | Checkpoints | Failures             |   |
|  +----------------------------------------------------------------------+   |
|         |                                                                    |
|         v                                                                    |
|  +----------------+    +----------------+    +----------------+              |
|  |   ANALYSIS     |    |   REPORTING    |    |     TUI        |              |
|  |   ENGINE       |--->|   (PDF)        |    |   VIEWER       |              |
|  +----------------+    +----------------+    +----------------+              |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 1.2 Core Components

| Component | Technology | Responsibility | Key Requirements |
|-----------|------------|----------------|------------------|
| **Validation Module** | Python | Verify O*NET schema, OpenRouter models, API keys | Fail fast with clear errors |
| **Prompt Generation** | Python + LLM | 3-phase pipeline (offline LLM, algorithmic, enrichment) | No hardcoded categories |
| **Response Collector** | httpx + asyncio | Parallel model queries with retry | Rate limiting, circuit breaker |
| **Judge Engine** | OpenRouter API | Multi-model ensemble with dual personas | Robust JSON parsing, fallbacks |
| **Vote Aggregator** | Pure Python | Majority-of-majorities computation | Proper Fleiss/Cohen Kappa |
| **Results Store** | SQLite + aiosqlite | All artifacts with atomic checkpointing | WAL mode for concurrency |
| **Analysis Engine** | pandas + scipy | Win rates, CIs, bias detection, weakness finding | Statistical significance |
| **TUI Viewer** | textual/rich | Live progress, results exploration | Interactive, keyboard controls |
| **Report Generator** | weasyprint + plotly | PDF reports with visualizations | Executive + comprehensive |

### 1.3 Directory Structure (Unified)

```
gemini-writing-eval/
+-- pyproject.toml
+-- README.md
+-- .env.example
|
+-- src/
|   +-- __init__.py
|   +-- cli.py                          # Typer-based CLI entry point
|   +-- config/
|   |   +-- settings.py                 # Pydantic settings with env vars
|   |   +-- presets.py                  # 10 preset configurations
|   |   +-- models.py                   # Model registry with verified IDs
|   |   +-- cost_estimator.py           # Dynamic pricing estimation
|   |   +-- budget.py                   # Budget limits and cost tracking
|   |
|   +-- validation/
|   |   +-- onet_schema.py              # O*NET schema validation
|   |   +-- model_verifier.py           # OpenRouter model ID verification
|   |   +-- api_validator.py            # API key validation
|   |   +-- warmup.py                   # Pre-flight checks and calibration
|   |
|   +-- data/
|   |   +-- onet_extractor.py           # O*NET database extraction
|   |   +-- onet_reference.py           # Parse ONET_REFERENCE.md guidance
|   |   +-- naics_mapper.py             # Industry mapping with fallbacks
|   |   +-- company_database.py         # Real company data with generation
|   |   +-- name_generator.py           # Demographically diverse names
|   |   +-- sensitive_detector.py       # Sensitive topic classification
|   |
|   +-- prompts/
|   |   +-- generator.py                # Main prompt orchestrator
|   |   +-- phase1_personas.py          # Offline LLM persona generation
|   |   +-- phase2_combiner.py          # Algorithmic combination
|   |   +-- phase3_enricher.py          # LLM context enrichment
|   |   +-- diversity_sampler.py        # Multi-dimensional stratified sampling
|   |   +-- revision_generator.py       # Revision/editing task generation
|   |   +-- constraint_generator.py     # Instruction-following constraints
|   |   +-- ambiguity_generator.py      # Deliberately vague prompts
|   |   +-- deduplicator.py             # Near-duplicate detection
|   |   +-- validator.py                # Prompt quality validation
|   |   +-- schemas.py                  # Pydantic models
|   |
|   +-- eval/
|   |   +-- orchestrator.py             # Main evaluation loop
|   |   +-- response_collector.py       # Model response gathering
|   |   +-- judge_engine.py             # Multi-model judging
|   |   +-- judge_parser.py             # Robust JSON extraction
|   |   +-- dual_persona.py             # Writing expert + recipient personas
|   |   +-- vote_aggregator.py          # Majority-of-majorities
|   |   +-- auto_loss_detector.py       # Refusal/failure detection
|   |   +-- constraint_checker.py       # Instruction compliance verification
|   |   +-- tier_manager.py             # Pro-tier vs Flash-tier separation
|   |
|   +-- api/
|   |   +-- openrouter_client.py        # OpenRouter API wrapper
|   |   +-- connection_pool.py          # Connection pool management
|   |   +-- rate_limiter.py             # Token bucket rate limiting
|   |   +-- circuit_breaker.py          # Failure handling circuit breaker
|   |   +-- retry_handler.py            # Exponential backoff with jitter
|   |
|   +-- storage/
|   |   +-- database.py                 # SQLite with WAL mode
|   |   +-- write_coalescer.py          # Batch writes for performance
|   |   +-- checkpoint.py               # Atomic checkpoint/resume
|   |   +-- run_manager.py              # Run directory lifecycle
|   |   +-- exporter.py                 # CSV/JSON export
|   |
|   +-- analysis/
|   |   +-- statistics.py               # Win rates, confidence intervals
|   |   +-- agreement.py                # Fleiss/Cohen Kappa implementation
|   |   +-- bias_detector.py            # Position, length, model bias detection
|   |   +-- weakness_finder.py          # Gemini weakness identification
|   |   +-- refusal_analyzer.py         # Refusal pattern analysis
|   |   +-- regional_analysis.py        # English variant analysis
|   |   +-- cross_run.py                # Cross-run comparison
|   |
|   +-- reports/
|   |   +-- pdf_generator.py            # PDF report creation
|   |   +-- chart_builder.py            # Plotly visualizations
|   |   +-- executive_summary.py        # Summary generation
|   |   +-- templates/                  # Jinja2 report templates
|   |
|   +-- tui/
|       +-- app.py                      # Main textual application
|       +-- progress_screen.py          # Live progress dashboard
|       +-- results_browser.py          # Results exploration
|       +-- comparison_viewer.py        # Side-by-side response view
|       +-- error_recovery.py           # Error state handling
|
+-- db/
|   +-- onet.db                         # O*NET 30.1 database
|   +-- ONET_REFERENCE.md               # Pre-processed writing task guide
|
+-- data/
|   +-- companies.json                  # Curated company database
|   +-- names.json                      # Name pools by demographic
|   +-- naics_soc_crosswalk.json        # NAICS-SOC mapping data
|
+-- results/                            # Eval run directories (gitignored)
+-- tests/
```

### 1.4 Technology Stack (Verified Dependencies)

```toml
[project]
requires-python = ">=3.11"

dependencies = [
    # Core async framework
    "pydantic>=2.5",
    "pydantic-settings>=2.1",
    "httpx>=0.27",
    "aiosqlite>=0.19",
    "tenacity>=8.2",
    "anyio>=4.2",

    # CLI and TUI
    "typer[all]>=0.9",
    "rich>=13.7",
    "textual>=0.52",

    # Data analysis
    "pandas>=2.2",
    "numpy>=1.26",
    "scipy>=1.12",
    "scikit-learn>=1.4",

    # Visualization and reporting
    "plotly>=5.18",
    "kaleido>=0.2",
    "weasyprint>=61",
    "jinja2>=3.1",

    # Utilities
    "python-dotenv>=1.0",
    "structlog>=24.1",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "mypy>=1.8",
    "ruff>=0.2",
]
```

---

## Part 2: Pre-Implementation Verification (Critical)

### 2.1 O*NET Schema Validation

**Consensus**: All critiques identified that draft plans assumed O*NET table/column names without verification. The implementation MUST validate schema before any queries.

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

    # Element IDs to verify exist (from O*NET Content Model)
    REQUIRED_ELEMENTS = {
        "2.A.1.c": "Writing Skill",
        "4.C.1.a.2.h": "Electronic Mail Work Context",
        "4.C.1.a.2.j": "Letters and Memos Work Context",
    }

    async def validate(self, db_path: Path) -> ValidationResult:
        """Validate schema and return detailed results."""
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

            # Verify element IDs have data
            for element_id, name in self.REQUIRED_ELEMENTS.items():
                count = await self._count_element(db, element_id)
                if count == 0:
                    warnings.append(f"No data for element {element_id} ({name})")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
```

### 2.2 OpenRouter Model ID Verification

**Consensus**: Model IDs like "google/gemini-3-pro" are speculative. Must verify against actual OpenRouter API at runtime.

```python
class ModelVerifier:
    """Verify model availability on OpenRouter."""

    # Expected model IDs (must be verified at runtime)
    EXPECTED_MODELS = {
        # Pro tier
        "gemini_pro": "google/gemini-3.0-pro",
        "gpt_pro": "openai/gpt-5.2",
        "claude_pro": "anthropic/claude-opus-4.5",
        "grok": "x-ai/grok-4.1",
        "kimi": "moonshot/kimi-k2",
        # Flash tier
        "gemini_flash": "google/gemini-3.0-flash",
        "gpt_flash": "openai/gpt-4.1",
        "claude_flash": "anthropic/claude-sonnet",
        # Judges
        "judge_claude": "anthropic/claude-opus-4.5",
        "judge_gpt": "openai/gpt-5.2",
        "judge_gemini": "google/gemini-3.0-pro",
    }

    async def verify_models(self, client: httpx.AsyncClient, api_key: str) -> dict[str, str]:
        """Verify which models are available and return ID mappings."""
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()

        available = {m["id"] for m in response.json()["data"]}
        verified = {}
        missing = []

        for key, expected_id in self.EXPECTED_MODELS.items():
            if expected_id in available:
                verified[key] = expected_id
            else:
                # Try to find similar model
                similar = self._find_similar(expected_id, available)
                if similar:
                    verified[key] = similar
                    logger.warning(f"Using {similar} instead of {expected_id}")
                else:
                    missing.append(expected_id)

        if missing:
            raise ModelNotFoundError(f"Models not available: {missing}")

        return verified

    def _find_similar(self, target: str, available: set) -> str | None:
        """Find similar model ID in available set."""
        provider, name = target.split("/")
        for model_id in available:
            if provider in model_id and any(
                part in model_id for part in name.split("-")
            ):
                return model_id
        return None
```

### 2.3 Warmup and Calibration Phase

**Consensus from Critiques 3 and 5**: Run pre-flight checks before committing to full evaluation.

```python
class WarmupPhase:
    """Pre-evaluation verification and calibration."""

    async def run(self, config: EvalConfig, api_client: APIClient) -> WarmupResult:
        """
        Run all pre-flight checks:
        1. Verify API connectivity
        2. Verify all models are available
        3. Run calibration prompts to estimate token usage
        4. Verify sufficient API credits
        5. Test judge models with sample comparison
        """
        results = WarmupResult()

        # 1. API connectivity
        try:
            await api_client.health_check()
            results.api_connected = True
        except Exception as e:
            results.errors.append(f"API connection failed: {e}")
            return results

        # 2. Model verification
        verifier = ModelVerifier()
        try:
            results.verified_models = await verifier.verify_models(
                api_client.client, config.api_key
            )
            results.models_verified = True
        except ModelNotFoundError as e:
            results.errors.append(str(e))
            return results

        # 3. Token calibration with sample prompts
        calibration = await self._run_calibration(config, api_client)
        results.token_estimates = calibration

        # 4. Cost estimation
        estimated_cost = self._estimate_total_cost(config, calibration)
        if config.budget_limit and estimated_cost > config.budget_limit:
            results.warnings.append(
                f"Estimated cost ${estimated_cost:.2f} exceeds budget ${config.budget_limit:.2f}"
            )
        results.estimated_cost = estimated_cost

        # 5. Judge test
        judge_test = await self._test_judges(config, api_client)
        results.judges_verified = judge_test.success

        return results
```

---

## Part 3: O*NET Data Pipeline

### 3.1 Task Extraction (No Hardcoded Categories)

**Key Consensus**: Let O*NET data drive task categorization. Use writing relevance scores from skill/work context data, not keyword matching alone.

```python
class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database."""

    # Writing indicators for relevance scoring
    WRITING_INDICATORS = [
        (r'\bwrite\b', 1.0),
        (r'\bdraft\b', 1.0),
        (r'\bcompose\b', 1.0),
        (r'\bdocument\b', 0.8),
        (r'\breport\b', 0.7),
        (r'\bcorrespond', 0.9),
        (r'\bemail\b', 0.9),
        (r'\bmemo\b', 0.9),
        (r'\bletter\b', 0.8),
        (r'\bcommunicat', 0.6),
        (r'\bpresent\b', 0.5),
        (r'\bsummariz', 0.7),
        (r'\bpropos', 0.7),
    ]

    async def extract_writing_tasks(
        self,
        min_relevance: float = 0.5,
        job_zones: list[int] | None = None,
        soc_codes: list[str] | None = None
    ) -> list[ONetTask]:
        """Extract tasks where writing is likely needed."""

        query = """
        SELECT
            t.task_id,
            t.onetsoc_code,
            o.title as occupation_title,
            o.description as occupation_description,
            t.task,
            COALESCE(jz.job_zone, 3) as job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major,
            COALESCE(ws.data_value, 2.5) as writing_skill,
            COALESCE(email_wc.data_value, 2.5) as email_freq,
            COALESCE(letter_wc.data_value, 2.5) as letter_freq
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        LEFT JOIN skills ws ON t.onetsoc_code = ws.onetsoc_code
            AND ws.element_id = '2.A.1.c' AND ws.scale_id = 'IM'
        LEFT JOIN work_context email_wc ON t.onetsoc_code = email_wc.onetsoc_code
            AND email_wc.element_id = '4.C.1.a.2.h' AND email_wc.scale_id = 'CX'
        LEFT JOIN work_context letter_wc ON t.onetsoc_code = letter_wc.onetsoc_code
            AND letter_wc.element_id = '4.C.1.a.2.j' AND letter_wc.scale_id = 'CX'
        """

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query)
            rows = await cursor.fetchall()

        tasks = []
        for row in rows:
            relevance = self._compute_writing_relevance(dict(row))
            if relevance >= min_relevance:
                # Apply filters
                if job_zones and row['job_zone'] not in job_zones:
                    continue
                if soc_codes and row['soc_major'] not in soc_codes:
                    continue

                tasks.append(ONetTask(
                    task_id=row['task_id'],
                    onetsoc_code=row['onetsoc_code'],
                    task=row['task'],
                    occupation_title=row['occupation_title'],
                    job_zone=row['job_zone'],
                    soc_major_group=row['soc_major'],
                    writing_relevance_score=relevance,
                    # Infer category from task text (not hardcoded enum)
                    inferred_category=self._infer_category(row['task']),
                    inferred_channel=self._infer_channel(row['task'])
                ))

        return tasks

    def _compute_writing_relevance(self, row: dict) -> float:
        """Compute writing relevance score from task text and O*NET data."""
        task_lower = row['task'].lower()
        max_pattern_score = 0.0

        for pattern, weight in self.WRITING_INDICATORS:
            if re.search(pattern, task_lower):
                max_pattern_score = max(max_pattern_score, weight)

        # Combine with O*NET skill/context scores
        onet_score = (
            row.get('writing_skill', 2.5) * 0.4 +
            row.get('email_freq', 2.5) * 0.3 +
            row.get('letter_freq', 2.5) * 0.3
        ) / 5.0  # Normalize to 0-1

        return max(max_pattern_score, onet_score)

    def _infer_category(self, task_text: str) -> str:
        """Infer writing category from task text (data-driven, not enum)."""
        task_lower = task_text.lower()

        # Priority order - more specific patterns first
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
        else:
            return 'unspecified'  # Let Phase 3 enrichment determine
```

### 3.2 NAICS Industry Mapping

**Consensus**: Use BLS Occupation-Industry Matrix when available, with robust fallback.

```python
class NAICSMapper:
    """Map SOC codes to NAICS industries with fallback strategies."""

    # SOC major group to likely NAICS sectors (fallback)
    FALLBACK_SOC_TO_NAICS = {
        "11": [("54", 0.25), ("52", 0.15), ("62", 0.12), ("31", 0.10)],  # Management
        "13": [("54", 0.30), ("52", 0.25), ("55", 0.10), ("92", 0.08)],  # Business/Financial
        "15": [("54", 0.35), ("51", 0.25), ("52", 0.12), ("31", 0.08)],  # Computer/Math
        "17": [("54", 0.30), ("23", 0.25), ("31", 0.25), ("22", 0.08)],  # Engineering
        # ... complete mapping for all 22 SOC major groups
    }

    NAICS_SECTORS = {
        "11": "Agriculture, Forestry, Fishing and Hunting",
        "21": "Mining, Quarrying, and Oil and Gas Extraction",
        "22": "Utilities",
        "23": "Construction",
        "31": "Manufacturing",
        "42": "Wholesale Trade",
        "44": "Retail Trade",
        "48": "Transportation and Warehousing",
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
        "92": "Public Administration",
    }

    def __init__(self, bls_matrix_path: Path | None = None):
        """Initialize with optional BLS matrix data."""
        self._bls_matrix = None
        if bls_matrix_path and bls_matrix_path.exists():
            self._bls_matrix = self._load_bls_matrix(bls_matrix_path)

    def sample_industry(
        self,
        soc_code: str,
        seed: int,
        exclude: set[str] | None = None
    ) -> tuple[str, str]:
        """Sample appropriate industry for occupation."""
        rng = random.Random(seed)
        exclude = exclude or set()
        soc_major = soc_code[:2]

        # Try BLS matrix first
        if self._bls_matrix and soc_code in self._bls_matrix:
            weights = self._bls_matrix[soc_code]
        elif soc_major in self.FALLBACK_SOC_TO_NAICS:
            weights = self.FALLBACK_SOC_TO_NAICS[soc_major]
        else:
            # Ultimate fallback: uniform distribution
            weights = [(k, 1.0) for k in self.NAICS_SECTORS.keys()]

        # Remove excluded and normalize
        available = [(code, w) for code, w in weights if code not in exclude]
        if not available:
            available = weights

        total = sum(w for _, w in available)
        normalized = [(code, w/total) for code, w in available]

        # Weighted sample
        codes, probs = zip(*normalized)
        naics = rng.choices(codes, weights=probs)[0]

        return naics, self.NAICS_SECTORS.get(naics, "General Business")
```

### 3.3 Company Database with Generation Fallback

**Consensus from Critiques 2, 4, 6**: Use real companies when possible, with LLM-generated plausible alternatives.

```python
class CompanyDatabase:
    """Database of real and generated companies for realistic prompts."""

    def __init__(self, companies_path: Path):
        """Load curated company database."""
        with open(companies_path) as f:
            self._companies = json.load(f)
        self._generated_cache: dict[str, list[Company]] = {}

    def get_company(
        self,
        naics_code: str,
        company_size: CompanySize,
        seed: int,
        use_real: bool = True,
        llm_client: LLMClient | None = None
    ) -> Company:
        """Get a company matching criteria, generating if necessary."""
        rng = random.Random(seed)

        if use_real:
            # Try to find matching real company
            candidates = [
                c for c in self._companies
                if c['naics'].startswith(naics_code[:2])
                and c['size'] == company_size.value
            ]
            if candidates:
                selected = rng.choice(candidates)
                return Company(
                    name=selected['name'],
                    industry=selected['industry'],
                    size=company_size,
                    naics=selected['naics'],
                    is_generated=False
                )

        # Generate company if no match or real companies disabled
        cache_key = f"{naics_code}_{company_size.value}"
        if cache_key not in self._generated_cache and llm_client:
            self._generated_cache[cache_key] = await self._generate_companies(
                naics_code, company_size, llm_client
            )

        if cache_key in self._generated_cache:
            return rng.choice(self._generated_cache[cache_key])

        # Ultimate fallback: generic placeholder
        return Company(
            name=f"Acme {self._naics_to_industry(naics_code)} Corp",
            industry=self._naics_to_industry(naics_code),
            size=company_size,
            naics=naics_code,
            is_generated=True
        )

    async def _generate_companies(
        self,
        naics_code: str,
        size: CompanySize,
        llm_client: LLMClient,
        count: int = 10
    ) -> list[Company]:
        """Generate plausible company names using LLM."""
        prompt = f"""Generate {count} realistic but fictional company names for:
- Industry: {self._naics_to_industry(naics_code)}
- Size: {size.value} company

Requirements:
- Names should sound professional and believable
- Mix of naming styles (founder names, descriptive, modern)
- Return as JSON array: [{{"name": "...", "tagline": "..."}}]"""

        response = await llm_client.generate(prompt, model="cheap_fast")
        companies_data = self._parse_json_response(response)

        return [
            Company(
                name=c['name'],
                industry=self._naics_to_industry(naics_code),
                size=size,
                naics=naics_code,
                is_generated=True
            )
            for c in companies_data
        ]
```

### 3.4 Demographically Diverse Name Generation

**Consensus**: Names should reflect workforce demographics. Use Census data distributions.

```python
class NameGenerator:
    """Generate demographically diverse names for realistic prompts."""

    # From US Census Bureau (approximate distributions)
    DEMOGRAPHIC_WEIGHTS = {
        "white": 0.61,
        "hispanic": 0.19,
        "black": 0.13,
        "asian": 0.06,
        "other": 0.01,
    }

    # Name pools by demographic group (sample)
    NAME_POOLS = {
        "white": {
            "first_male": ["James", "Michael", "Robert", "William", "David", "John", "Richard"],
            "first_female": ["Jennifer", "Elizabeth", "Patricia", "Mary", "Susan", "Karen", "Lisa"],
            "last": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis"],
        },
        "hispanic": {
            "first_male": ["Carlos", "José", "Miguel", "Luis", "Juan", "Antonio", "Francisco"],
            "first_female": ["Maria", "Carmen", "Rosa", "Ana", "Isabel", "Sofia", "Lucia"],
            "last": ["Garcia", "Rodriguez", "Martinez", "Lopez", "Hernandez", "Gonzalez"],
        },
        "black": {
            "first_male": ["Marcus", "Jamal", "Terrence", "Andre", "Darnell", "Jerome", "Tyrone"],
            "first_female": ["Latoya", "Ebony", "Jasmine", "Keisha", "Tiffany", "Aaliyah"],
            "last": ["Washington", "Jefferson", "Jackson", "Freeman", "Robinson", "Harris"],
        },
        "asian": {
            "first_male": ["Wei", "Jin", "Hiroshi", "Kenji", "Raj", "Anil", "David", "Kevin"],
            "first_female": ["Mei", "Yuki", "Priya", "Aisha", "Michelle", "Amy", "Grace"],
            "last": ["Wong", "Chen", "Kim", "Park", "Patel", "Singh", "Nguyen", "Tanaka"],
        },
    }

    def generate_name(
        self,
        seed: int,
        gender: str | None = None,
        demographic: str | None = None,
    ) -> PersonName:
        """Generate a demographically appropriate name."""
        rng = random.Random(seed)

        # Sample demographic if not specified
        if demographic is None:
            demographic = rng.choices(
                list(self.DEMOGRAPHIC_WEIGHTS.keys()),
                weights=list(self.DEMOGRAPHIC_WEIGHTS.values())
            )[0]

        # Sample gender if not specified (50/50)
        if gender is None:
            gender = rng.choice(["male", "female"])

        pool = self.NAME_POOLS.get(demographic, self.NAME_POOLS["white"])
        first_key = f"first_{gender}"

        first = rng.choice(pool.get(first_key, pool["first_male"]))
        last = rng.choice(pool["last"])

        return PersonName(
            first=first,
            last=last,
            full=f"{first} {last}",
            demographic=demographic,
            gender=gender
        )

    def generate_pair(self, seed: int) -> tuple[PersonName, PersonName]:
        """Generate a pair of names (e.g., sender/recipient)."""
        return (
            self.generate_name(seed),
            self.generate_name(seed + 1000)  # Different seed for variety
        )
```

---

## Part 4: Prompt Generation Pipeline (3-Phase Architecture)

### 4.1 Architecture Overview

**Strong Consensus**: All 6 critiques endorsed the 3-phase approach with variations on execution.

```
Phase 1 (Offline/Cached):        Phase 2 (Algorithmic):           Phase 3 (Online/Enrichment):
+-------------------+            +----------------------+          +----------------------+
| LLM generates     |            | Combine components:  |          | LLM adds:            |
| - Base personas   |            | - O*NET task         |          | - Realistic context  |
| - Scenario seeds  |  ------>   | - Persona            |  ----->  | - Company details    |
| - Writing styles  |            | - Company/Industry   |          | - Specific numbers   |
+-------------------+            | - Constraints        |          | - Urgency/stakes     |
                                 +----------------------+          +----------------------+
                                          |
                                 Multi-dimensional
                                 stratified sampling
```

### 4.2 Phase 1: Offline Persona/Scenario Generation

**Consensus from Critiques 1, 3, 5**: Pre-generate diverse components, cache for reuse.

```python
class Phase1Generator:
    """Generate and cache base prompt components offline."""

    PERSONA_GENERATION_PROMPT = """
Generate {count} diverse professional personas for writing evaluation.
Each persona should have:
- job_title: A real job title (from any industry)
- experience_level: junior/mid/senior/executive
- communication_style: formal/casual/technical/persuasive
- industry_focus: General industry area
- personality_traits: 2-3 relevant traits affecting writing
- challenges: Common writing challenges for this role

Diversity requirements:
- Mix of seniority levels
- Mix of industries
- Mix of communication styles
- Include both individual contributors and managers

Return as JSON array.
"""

    async def generate_personas(
        self,
        count: int,
        llm_client: LLMClient,
        cache_path: Path
    ) -> list[Persona]:
        """Generate or load cached personas."""
        if cache_path.exists():
            with open(cache_path) as f:
                return [Persona(**p) for p in json.load(f)]

        response = await llm_client.generate(
            self.PERSONA_GENERATION_PROMPT.format(count=count),
            model="smart_cheap"  # Good quality but not expensive
        )

        personas = self._parse_personas(response)

        # Cache for reuse
        with open(cache_path, 'w') as f:
            json.dump([p.model_dump() for p in personas], f, indent=2)

        return personas

    async def generate_scenario_seeds(
        self,
        onet_tasks: list[ONetTask],
        count: int,
        llm_client: LLMClient,
        cache_path: Path
    ) -> list[ScenarioSeed]:
        """Generate scenario seeds from O*NET tasks."""
        if cache_path.exists():
            with open(cache_path) as f:
                return [ScenarioSeed(**s) for s in json.load(f)]

        # Sample diverse O*NET tasks
        sampled_tasks = self._stratified_sample(onet_tasks, count)

        prompt = """
For each O*NET task statement below, generate a realistic writing scenario:

Tasks:
{tasks}

For each, provide:
- scenario_type: email/report/memo/proposal/etc.
- context: Why this writing is needed now
- stakes: What depends on this communication
- audience: Who will read this
- key_challenges: What makes this writing task difficult

Return as JSON array matching the task order.
"""

        response = await llm_client.generate(
            prompt.format(tasks="\n".join(f"- {t.task}" for t in sampled_tasks)),
            model="smart_cheap"
        )

        seeds = self._parse_seeds(response, sampled_tasks)

        with open(cache_path, 'w') as f:
            json.dump([s.model_dump() for s in seeds], f, indent=2)

        return seeds
```

### 4.3 Phase 2: Algorithmic Combination with Stratified Sampling

**Strong Consensus**: Multi-dimensional stratification is critical for prompt diversity.

```python
class Phase2Combiner:
    """Algorithmic combination with stratified sampling."""

    STRATIFICATION_DIMENSIONS = [
        "job_zone",           # O*NET job complexity (1-5)
        "writing_category",   # Inferred from task
        "channel",            # Email, report, memo, etc.
        "formality",          # From persona
        "word_count_tier",    # Short/medium/long
        "urgency",            # Low/medium/high
        "soc_major_group",    # Occupation group
        "naics_sector",       # Industry
    ]

    def __init__(
        self,
        tasks: list[ONetTask],
        personas: list[Persona],
        scenario_seeds: list[ScenarioSeed],
        name_generator: NameGenerator,
        company_database: CompanyDatabase,
        naics_mapper: NAICSMapper
    ):
        self.tasks = tasks
        self.personas = personas
        self.scenario_seeds = scenario_seeds
        self.name_generator = name_generator
        self.company_database = company_database
        self.naics_mapper = naics_mapper

    def generate_prompts(
        self,
        count: int,
        seed: int,
        constraints: PromptConstraints | None = None
    ) -> list[BasePrompt]:
        """Generate stratified prompt combinations."""
        rng = random.Random(seed)

        # Build combination space
        all_combinations = self._generate_all_combinations()

        # Stratified sampling to ensure diversity
        sampled = self._stratified_sample(
            all_combinations,
            count,
            rng,
            self.STRATIFICATION_DIMENSIONS
        )

        # Apply constraints if provided
        if constraints:
            sampled = [c for c in sampled if self._meets_constraints(c, constraints)]

        return [self._combination_to_prompt(c, rng) for c in sampled]

    def _stratified_sample(
        self,
        combinations: list[dict],
        count: int,
        rng: random.Random,
        dimensions: list[str]
    ) -> list[dict]:
        """Multi-dimensional stratified sampling."""
        # Group by all dimension combinations
        strata = defaultdict(list)
        for combo in combinations:
            key = tuple(combo.get(d, "unknown") for d in dimensions)
            strata[key].append(combo)

        # Calculate samples per stratum (proportional with floor of 1)
        total_strata = len(strata)
        base_per_stratum = max(1, count // total_strata)

        sampled = []
        remaining = count

        # First pass: sample from each stratum
        for key, items in strata.items():
            n = min(base_per_stratum, len(items), remaining)
            sampled.extend(rng.sample(items, n))
            remaining -= n

        # Second pass: fill remaining from largest strata
        if remaining > 0:
            large_strata = sorted(strata.items(), key=lambda x: len(x[1]), reverse=True)
            for key, items in large_strata:
                available = [i for i in items if i not in sampled]
                n = min(remaining, len(available))
                sampled.extend(rng.sample(available, n))
                remaining -= n
                if remaining <= 0:
                    break

        return sampled

    def _combination_to_prompt(self, combo: dict, rng: random.Random) -> BasePrompt:
        """Convert combination dict to BasePrompt."""
        seed = rng.randint(0, 2**32)

        # Get names
        sender, recipient = self.name_generator.generate_pair(seed)

        # Get company
        naics, industry = self.naics_mapper.sample_industry(
            combo['task'].onetsoc_code, seed
        )
        company = self.company_database.get_company(
            naics,
            self._infer_company_size(combo['persona']),
            seed
        )

        return BasePrompt(
            id=f"prompt_{seed:08x}",
            task=combo['task'],
            persona=combo['persona'],
            scenario_seed=combo['scenario_seed'],
            sender=sender,
            recipient=recipient,
            company=company,
            industry=industry,
            word_count_tier=combo.get('word_count_tier', 'medium'),
            urgency=combo.get('urgency', 'medium'),
            formality=combo['persona'].communication_style,
            raw_combined=True,
            needs_enrichment=True
        )
```

### 4.4 Phase 3: LLM Context Enrichment

**Consensus from Critiques 2, 4, 6**: LLM enrichment adds realism but must be carefully prompted.

```python
class Phase3Enricher:
    """Enrich base prompts with LLM-generated context."""

    ENRICHMENT_PROMPT = """
You are creating a realistic writing prompt for evaluating AI writing assistants.

Base scenario:
- Writer role: {persona.job_title} at {company.name} ({industry})
- Task from O*NET: {task.task}
- Writing type: {scenario_seed.scenario_type}
- Recipient: {recipient.full}
- Context: {scenario_seed.context}

Generate a complete, realistic writing prompt that:
1. Includes specific but fictional details (names, dates, numbers, project names)
2. Provides clear context about why this communication is needed NOW
3. Specifies what the recipient needs to know or do
4. Includes any constraints: {word_count_tier} length, {urgency} urgency, {formality} tone
5. Does NOT include placeholder text like [X] or [COMPANY] - use specific values

Format the output as a JSON object:
{{
    "prompt_text": "The complete prompt the AI model should respond to",
    "expected_format": "email/memo/report/etc.",
    "key_points_to_cover": ["point1", "point2", ...],
    "quality_signals": ["What would make this response excellent"],
    "context_details": {{
        "project_name": "...",
        "deadline": "...",
        "specific_numbers": [...],
        "stakeholders": [...]
    }}
}}
"""

    async def enrich_prompt(
        self,
        base_prompt: BasePrompt,
        llm_client: LLMClient
    ) -> EnrichedPrompt:
        """Add realistic context to a base prompt."""
        filled_prompt = self.ENRICHMENT_PROMPT.format(
            persona=base_prompt.persona,
            company=base_prompt.company,
            industry=base_prompt.industry,
            task=base_prompt.task,
            scenario_seed=base_prompt.scenario_seed,
            recipient=base_prompt.recipient,
            word_count_tier=base_prompt.word_count_tier,
            urgency=base_prompt.urgency,
            formality=base_prompt.formality
        )

        response = await llm_client.generate(
            filled_prompt,
            model="smart_cheap",
            temperature=0.7  # Some creativity for variety
        )

        enrichment = self._parse_enrichment(response)

        return EnrichedPrompt(
            **base_prompt.model_dump(),
            prompt_text=enrichment['prompt_text'],
            expected_format=enrichment['expected_format'],
            key_points=enrichment['key_points_to_cover'],
            quality_signals=enrichment['quality_signals'],
            context_details=enrichment['context_details'],
            enriched_at=datetime.utcnow(),
            enrichment_model=llm_client.last_model_used
        )

    async def enrich_batch(
        self,
        prompts: list[BasePrompt],
        llm_client: LLMClient,
        concurrency: int = 5,
        checkpoint_callback: Callable[[EnrichedPrompt], Awaitable[None]] | None = None
    ) -> list[EnrichedPrompt]:
        """Enrich multiple prompts with concurrency control."""
        semaphore = asyncio.Semaphore(concurrency)
        results = []

        async def enrich_with_semaphore(prompt: BasePrompt) -> EnrichedPrompt:
            async with semaphore:
                enriched = await self.enrich_prompt(prompt, llm_client)
                if checkpoint_callback:
                    await checkpoint_callback(enriched)
                return enriched

        tasks = [enrich_with_semaphore(p) for p in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failures
        enriched = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Enrichment failed: {r}")
            else:
                enriched.append(r)

        return enriched
```

### 4.5 Special Prompt Types

**Consensus**: Include revision tasks, ambiguous prompts, and constraint-heavy prompts.

```python
class RevisionGenerator:
    """Generate revision/editing tasks from completed responses."""

    REVISION_TYPES = [
        "shorten",      # Make more concise
        "formalize",    # Make more formal
        "simplify",     # Reduce jargon/complexity
        "expand",       # Add more detail
        "soften",       # Make less direct
        "strengthen",   # Make more assertive
        "restructure",  # Reorganize content
    ]

    async def generate_revision_prompt(
        self,
        original_prompt: EnrichedPrompt,
        original_response: str,
        revision_type: str,
        llm_client: LLMClient
    ) -> RevisionPrompt:
        """Create a revision prompt from an original exchange."""
        instruction = self._get_revision_instruction(revision_type)

        return RevisionPrompt(
            id=f"revision_{original_prompt.id}_{revision_type}",
            original_prompt=original_prompt,
            original_response=original_response,
            revision_type=revision_type,
            prompt_text=f"""
Here is a {original_prompt.expected_format} that was written:

---
{original_response}
---

Please revise this {original_prompt.expected_format} to {instruction}.

Keep the core message and purpose the same, but adjust the style/length as requested.
""",
            expected_changes=instruction
        )


class ConstraintGenerator:
    """Add instruction-following constraints to prompts."""

    CONSTRAINT_TYPES = {
        "word_limit": lambda n: f"Your response must be exactly {n} words.",
        "sentence_limit": lambda n: f"Use exactly {n} sentences.",
        "bullet_points": lambda n: f"Include exactly {n} bullet points.",
        "no_jargon": lambda: "Avoid all technical jargon - explain for a general audience.",
        "formal_only": lambda: "Use strictly formal language throughout.",
        "include_keyword": lambda w: f"You must include the word '{w}' at least 3 times.",
        "start_with": lambda w: f"Begin your response with the word '{w}'.",
        "end_with": lambda w: f"End your response with the phrase '{w}'.",
        "paragraph_count": lambda n: f"Structure your response in exactly {n} paragraphs.",
    }

    def add_constraints(
        self,
        prompt: EnrichedPrompt,
        constraint_count: int,
        seed: int
    ) -> ConstrainedPrompt:
        """Add verifiable constraints to a prompt."""
        rng = random.Random(seed)
        constraints = []

        selected = rng.sample(list(self.CONSTRAINT_TYPES.keys()), constraint_count)

        for constraint_type in selected:
            generator = self.CONSTRAINT_TYPES[constraint_type]

            # Generate appropriate parameter
            if constraint_type == "word_limit":
                param = rng.choice([50, 100, 150, 200, 250])
                constraint_text = generator(param)
            elif constraint_type in ["sentence_limit", "bullet_points", "paragraph_count"]:
                param = rng.randint(3, 7)
                constraint_text = generator(param)
            elif constraint_type in ["include_keyword", "start_with", "end_with"]:
                keywords = ["however", "therefore", "importantly", "specifically", "ultimately"]
                param = rng.choice(keywords)
                constraint_text = generator(param)
            else:
                constraint_text = generator()
                param = None

            constraints.append(PromptConstraint(
                type=constraint_type,
                text=constraint_text,
                parameter=param,
                verifiable=True
            ))

        # Modify prompt text
        constraint_block = "\n\nIMPORTANT CONSTRAINTS:\n" + "\n".join(
            f"- {c.text}" for c in constraints
        )

        return ConstrainedPrompt(
            **prompt.model_dump(),
            id=f"constrained_{prompt.id}",
            prompt_text=prompt.prompt_text + constraint_block,
            constraints=constraints
        )
```

---

## Part 5: Evaluation Flow and Judging System

### 5.1 Response Collection with Parallel Execution

**Consensus**: Collect responses from all models in parallel with proper error handling.

```python
class ResponseCollector:
    """Collect responses from multiple models in parallel."""

    def __init__(
        self,
        api_client: OpenRouterClient,
        tier_config: TierConfig,
        rate_limiter: RateLimiter,
        circuit_breaker: CircuitBreaker
    ):
        self.api_client = api_client
        self.tier_config = tier_config
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker

    async def collect_responses(
        self,
        prompt: EnrichedPrompt,
        tier: str,  # "pro" or "flash"
        checkpoint_callback: Callable[[ModelResponse], Awaitable[None]] | None = None
    ) -> dict[str, ModelResponse]:
        """Collect responses from all models in a tier."""
        models = self.tier_config.get_models(tier)
        tasks = []

        for model_id in models:
            tasks.append(self._collect_single(prompt, model_id, checkpoint_callback))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = {}
        for model_id, result in zip(models, results):
            if isinstance(result, Exception):
                responses[model_id] = ModelResponse(
                    prompt_id=prompt.id,
                    model_id=model_id,
                    response_text=None,
                    error=str(result),
                    status="failed",
                    latency_ms=0,
                    token_count=0
                )
            else:
                responses[model_id] = result

        return responses

    async def _collect_single(
        self,
        prompt: EnrichedPrompt,
        model_id: str,
        checkpoint_callback: Callable | None
    ) -> ModelResponse:
        """Collect response from a single model."""
        # Check circuit breaker
        if not self.circuit_breaker.allow_request(model_id):
            raise CircuitBreakerOpen(f"Circuit open for {model_id}")

        # Rate limiting
        await self.rate_limiter.acquire(model_id)

        start = time.perf_counter()
        try:
            response = await self.api_client.generate(
                prompt=prompt.prompt_text,
                model=model_id,
                max_tokens=self._estimate_max_tokens(prompt),
                temperature=0.7
            )

            latency = (time.perf_counter() - start) * 1000

            result = ModelResponse(
                prompt_id=prompt.id,
                model_id=model_id,
                response_text=response.content,
                error=None,
                status="success",
                latency_ms=latency,
                token_count=response.usage.total_tokens,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens
            )

            self.circuit_breaker.record_success(model_id)

            if checkpoint_callback:
                await checkpoint_callback(result)

            return result

        except Exception as e:
            self.circuit_breaker.record_failure(model_id)
            raise
```

### 5.2 Dual-Persona Judging System

**Strong Consensus**: Every comparison judged by BOTH writing expert AND simulated recipient.

```python
class DualPersonaJudge:
    """Judge comparisons using two complementary personas."""

    WRITING_EXPERT_SYSTEM = """
You are an expert writing evaluator with 20+ years of experience in professional communication.
You evaluate writing based on:
- Clarity and organization
- Appropriate tone for context
- Grammar and mechanics
- Effectiveness in achieving communication goals
- Professional standards for the document type

You are objective and focus on craft quality rather than personal preference.
"""

    RECIPIENT_SYSTEM_TEMPLATE = """
You are {recipient_name}, {recipient_role} at {company}.
You are the intended recipient of this communication.
You will evaluate which response better serves YOUR needs:
- Does it give you what you need to know/do?
- Is it appropriately professional for your relationship?
- Is it clear and easy to act on?
- Does it respect your time?

Think from YOUR perspective as the reader, not as a writing critic.
"""

    COMPARISON_PROMPT = """
You are comparing two responses to this writing prompt:

PROMPT:
{prompt_text}

RESPONSE A:
{response_a}

RESPONSE B:
{response_b}

Evaluate both responses and determine which is better.

Provide your judgment as JSON:
{{
    "reasoning": "Brief explanation of your evaluation (2-3 sentences)",
    "winner": "A" or "B" or "TIE",
    "confidence": "high" or "medium" or "low",
    "strengths_a": ["strength1", "strength2"],
    "strengths_b": ["strength1", "strength2"],
    "weaknesses_a": ["weakness1"],
    "weaknesses_b": ["weakness1"]
}}

Be decisive - only choose TIE if responses are genuinely equivalent.
"""

    async def judge_comparison(
        self,
        prompt: EnrichedPrompt,
        response_a: str,
        response_b: str,
        judge_model: str,
        api_client: OpenRouterClient
    ) -> tuple[JudgmentResult, JudgmentResult]:
        """Get judgments from both personas."""

        # Writing expert judgment
        expert_result = await self._judge_with_persona(
            prompt, response_a, response_b, judge_model, api_client,
            system_prompt=self.WRITING_EXPERT_SYSTEM,
            persona_type="writing_expert"
        )

        # Simulated recipient judgment
        recipient_system = self.RECIPIENT_SYSTEM_TEMPLATE.format(
            recipient_name=prompt.recipient.full,
            recipient_role=self._infer_recipient_role(prompt),
            company=prompt.company.name
        )

        recipient_result = await self._judge_with_persona(
            prompt, response_a, response_b, judge_model, api_client,
            system_prompt=recipient_system,
            persona_type="simulated_recipient"
        )

        return expert_result, recipient_result

    async def _judge_with_persona(
        self,
        prompt: EnrichedPrompt,
        response_a: str,
        response_b: str,
        judge_model: str,
        api_client: OpenRouterClient,
        system_prompt: str,
        persona_type: str
    ) -> JudgmentResult:
        """Get judgment from a specific persona."""
        comparison_prompt = self.COMPARISON_PROMPT.format(
            prompt_text=prompt.prompt_text,
            response_a=response_a,
            response_b=response_b
        )

        response = await api_client.generate(
            prompt=comparison_prompt,
            model=judge_model,
            system=system_prompt,
            temperature=0.3  # Lower temperature for consistency
        )

        parsed = self._parse_judgment(response.content)

        return JudgmentResult(
            prompt_id=prompt.id,
            judge_model=judge_model,
            persona_type=persona_type,
            winner=parsed.get('winner', 'PARSE_ERROR'),
            confidence=parsed.get('confidence', 'unknown'),
            reasoning=parsed.get('reasoning', ''),
            strengths_a=parsed.get('strengths_a', []),
            strengths_b=parsed.get('strengths_b', []),
            weaknesses_a=parsed.get('weaknesses_a', []),
            weaknesses_b=parsed.get('weaknesses_b', []),
            raw_response=response.content,
            parse_success=parsed.get('_parse_success', False)
        )
```

### 5.3 Position Bias Mitigation

**Consensus from Critiques 1, 3, 4**: Shuffle response positions and aggregate.

```python
class PositionBiasHandler:
    """Handle position bias in pairwise comparisons."""

    async def judge_with_position_shuffle(
        self,
        prompt: EnrichedPrompt,
        responses: dict[str, str],  # model_id -> response
        judge: DualPersonaJudge,
        judge_models: list[str],
        api_client: OpenRouterClient
    ) -> list[ShuffledJudgment]:
        """Judge comparison with both position orderings."""
        model_ids = list(responses.keys())
        if len(model_ids) != 2:
            raise ValueError("Pairwise comparison requires exactly 2 responses")

        model_a, model_b = model_ids
        judgments = []

        for judge_model in judge_models:
            # Order 1: A first, B second
            expert_ab, recipient_ab = await judge.judge_comparison(
                prompt,
                responses[model_a],  # Position A
                responses[model_b],  # Position B
                judge_model,
                api_client
            )

            # Order 2: B first, A second
            expert_ba, recipient_ba = await judge.judge_comparison(
                prompt,
                responses[model_b],  # Position A
                responses[model_a],  # Position B
                judge_model,
                api_client
            )

            # Map position winners back to actual models
            judgments.append(ShuffledJudgment(
                judge_model=judge_model,
                judgments={
                    'expert_ab': self._map_winner(expert_ab, model_a, model_b),
                    'expert_ba': self._map_winner(expert_ba, model_b, model_a),
                    'recipient_ab': self._map_winner(recipient_ab, model_a, model_b),
                    'recipient_ba': self._map_winner(recipient_ba, model_b, model_a),
                },
                position_agreement=self._check_position_agreement(
                    expert_ab, expert_ba, recipient_ab, recipient_ba
                )
            ))

        return judgments

    def _map_winner(
        self,
        judgment: JudgmentResult,
        pos_a_model: str,
        pos_b_model: str
    ) -> str:
        """Map positional winner to actual model ID."""
        if judgment.winner == "A":
            return pos_a_model
        elif judgment.winner == "B":
            return pos_b_model
        else:
            return "TIE"
```

### 5.4 Majority-of-Majorities Vote Aggregation

**Strong Consensus**: Robust aggregation with proper agreement metrics.

```python
class VoteAggregator:
    """Aggregate judgments using majority-of-majorities."""

    def aggregate_comparison(
        self,
        shuffled_judgments: list[ShuffledJudgment],
        model_a: str,
        model_b: str
    ) -> AggregatedResult:
        """Aggregate judgments with majority-of-majorities."""

        # Step 1: For each (judge, persona), determine winner across positions
        judge_persona_winners = []

        for sj in shuffled_judgments:
            # Expert persona - majority across positions
            expert_winners = [
                sj.judgments['expert_ab'],
                sj.judgments['expert_ba']
            ]
            expert_winner = self._position_majority(expert_winners, model_a, model_b)

            # Recipient persona - majority across positions
            recipient_winners = [
                sj.judgments['recipient_ab'],
                sj.judgments['recipient_ba']
            ]
            recipient_winner = self._position_majority(recipient_winners, model_a, model_b)

            judge_persona_winners.extend([
                (sj.judge_model, 'expert', expert_winner),
                (sj.judge_model, 'recipient', recipient_winner)
            ])

        # Step 2: Majority across all judge-persona combinations
        all_winners = [w for _, _, w in judge_persona_winners]
        final_winner = self._simple_majority(all_winners, model_a, model_b)

        # Calculate agreement metrics
        agreement = self._calculate_agreement(judge_persona_winners)

        return AggregatedResult(
            winner=final_winner,
            model_a=model_a,
            model_b=model_b,
            vote_breakdown={
                model_a: all_winners.count(model_a),
                model_b: all_winners.count(model_b),
                "TIE": all_winners.count("TIE")
            },
            judge_persona_votes=judge_persona_winners,
            inter_judge_agreement=agreement['inter_judge'],
            inter_persona_agreement=agreement['inter_persona'],
            position_consistency=agreement['position_consistency'],
            confidence=self._compute_confidence(all_winners, model_a, model_b)
        )

    def _position_majority(
        self,
        winners: list[str],
        model_a: str,
        model_b: str
    ) -> str:
        """Determine winner across position shuffles."""
        a_count = winners.count(model_a)
        b_count = winners.count(model_b)

        if a_count > b_count:
            return model_a
        elif b_count > a_count:
            return model_b
        else:
            return "TIE"

    def _calculate_agreement(
        self,
        judge_persona_winners: list[tuple[str, str, str]]
    ) -> dict:
        """Calculate various agreement metrics."""
        # Group by judge
        by_judge = defaultdict(list)
        for judge, persona, winner in judge_persona_winners:
            by_judge[judge].append(winner)

        # Group by persona
        by_persona = defaultdict(list)
        for judge, persona, winner in judge_persona_winners:
            by_persona[persona].append(winner)

        # Inter-judge agreement (do different judges agree?)
        judge_majorities = [
            self._simple_majority(winners, None, None)
            for winners in by_judge.values()
        ]
        inter_judge = len(set(judge_majorities)) == 1

        # Inter-persona agreement (do expert and recipient agree?)
        persona_majorities = {
            persona: self._simple_majority(winners, None, None)
            for persona, winners in by_persona.items()
        }
        inter_persona = len(set(persona_majorities.values())) == 1

        return {
            'inter_judge': inter_judge,
            'inter_persona': inter_persona,
            'position_consistency': self._compute_position_consistency(judge_persona_winners)
        }
```

### 5.5 Robust JSON Parsing for Judgments

**Consensus from Critiques 2, 4, 5**: LLM judge outputs need robust parsing.

```python
class JudgeParser:
    """Robust JSON extraction from judge responses."""

    def parse_judgment(self, raw_response: str) -> dict:
        """Extract judgment from possibly malformed JSON."""

        # Strategy 1: Direct JSON parse
        try:
            return self._extract_json_block(raw_response)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Find JSON-like structure
        try:
            return self._find_json_structure(raw_response)
        except Exception:
            pass

        # Strategy 3: Regex extraction of key fields
        try:
            return self._regex_extraction(raw_response)
        except Exception:
            pass

        # Strategy 4: Return parse failure indicator
        return {
            '_parse_success': False,
            'winner': 'PARSE_ERROR',
            'reasoning': f'Failed to parse: {raw_response[:200]}...',
            'confidence': 'unknown'
        }

    def _extract_json_block(self, text: str) -> dict:
        """Extract JSON from code block or raw text."""
        # Try code block first
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block_match:
            return json.loads(code_block_match.group(1))

        # Try raw JSON
        json_match = re.search(r'\{[^{}]*"winner"[^{}]*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        raise json.JSONDecodeError("No JSON found", text, 0)

    def _find_json_structure(self, text: str) -> dict:
        """Find and fix common JSON issues."""
        # Find potential JSON
        start = text.find('{')
        if start == -1:
            raise ValueError("No JSON structure found")

        # Balance braces
        depth = 0
        end = start
        for i, char in enumerate(text[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        json_str = text[start:end]

        # Common fixes
        json_str = re.sub(r',\s*}', '}', json_str)  # Trailing commas
        json_str = re.sub(r"'", '"', json_str)      # Single quotes

        return json.loads(json_str)

    def _regex_extraction(self, text: str) -> dict:
        """Last resort: extract fields via regex."""
        result = {'_parse_success': False}

        # Winner extraction
        winner_match = re.search(r'"?winner"?\s*:\s*"?([ABab]|TIE|tie)"?', text, re.I)
        if winner_match:
            result['winner'] = winner_match.group(1).upper()
            result['_parse_success'] = True

        # Confidence extraction
        conf_match = re.search(r'"?confidence"?\s*:\s*"?(high|medium|low)"?', text, re.I)
        if conf_match:
            result['confidence'] = conf_match.group(1).lower()

        # Reasoning extraction
        reason_match = re.search(r'"?reasoning"?\s*:\s*"([^"]+)"', text)
        if reason_match:
            result['reasoning'] = reason_match.group(1)

        return result
```

---

## Part 6: Analysis and Reporting

### 6.1 Statistical Analysis Engine

**Consensus**: Proper statistical methods with confidence intervals and significance tests.

```python
class StatisticsEngine:
    """Compute win rates, confidence intervals, and significance tests."""

    def compute_win_rates(
        self,
        results: list[AggregatedResult],
        model_id: str
    ) -> WinRateStats:
        """Compute win rate with confidence interval."""
        wins = sum(1 for r in results if r.winner == model_id)
        losses = sum(1 for r in results if r.winner != model_id and r.winner != "TIE")
        ties = sum(1 for r in results if r.winner == "TIE")
        total = len(results)

        win_rate = wins / total if total > 0 else 0.0

        # Wilson score confidence interval (more accurate for proportions)
        ci_low, ci_high = self._wilson_score_interval(wins, total, confidence=0.95)

        return WinRateStats(
            model_id=model_id,
            wins=wins,
            losses=losses,
            ties=ties,
            total=total,
            win_rate=win_rate,
            win_rate_excluding_ties=wins / (wins + losses) if (wins + losses) > 0 else 0.0,
            confidence_interval=(ci_low, ci_high),
            confidence_level=0.95
        )

    def _wilson_score_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Wilson score interval for binomial proportion."""
        if total == 0:
            return (0.0, 0.0)

        from scipy import stats
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p_hat = successes / total

        denominator = 1 + z**2 / total
        center = (p_hat + z**2 / (2 * total)) / denominator
        margin = (z / denominator) * math.sqrt(
            (p_hat * (1 - p_hat) + z**2 / (4 * total)) / total
        )

        return (max(0, center - margin), min(1, center + margin))

    def head_to_head_matrix(
        self,
        results: list[AggregatedResult],
        models: list[str]
    ) -> pd.DataFrame:
        """Create head-to-head win rate matrix."""
        matrix = pd.DataFrame(index=models, columns=models, dtype=float)

        for model_a in models:
            for model_b in models:
                if model_a == model_b:
                    matrix.loc[model_a, model_b] = 0.5
                    continue

                relevant = [
                    r for r in results
                    if {r.model_a, r.model_b} == {model_a, model_b}
                ]

                wins = sum(1 for r in relevant if r.winner == model_a)
                total = len(relevant)
                matrix.loc[model_a, model_b] = wins / total if total > 0 else 0.5

        return matrix


class AgreementMetrics:
    """Calculate inter-rater agreement metrics."""

    def fleiss_kappa(
        self,
        ratings: list[list[str]],
        categories: list[str]
    ) -> float:
        """Calculate Fleiss' Kappa for multiple raters."""
        n_items = len(ratings)
        n_raters = len(ratings[0]) if ratings else 0
        n_categories = len(categories)

        if n_items == 0 or n_raters == 0:
            return 0.0

        # Count ratings per category per item
        category_counts = []
        for item_ratings in ratings:
            counts = {cat: 0 for cat in categories}
            for rating in item_ratings:
                if rating in counts:
                    counts[rating] += 1
            category_counts.append(counts)

        # Calculate P_i (agreement for each item)
        P_items = []
        for counts in category_counts:
            sum_sq = sum(c**2 for c in counts.values())
            P_i = (sum_sq - n_raters) / (n_raters * (n_raters - 1)) if n_raters > 1 else 0
            P_items.append(P_i)

        P_bar = sum(P_items) / n_items if n_items > 0 else 0

        # Calculate P_e (expected agreement by chance)
        category_totals = {cat: 0 for cat in categories}
        for counts in category_counts:
            for cat, count in counts.items():
                category_totals[cat] += count

        total_ratings = n_items * n_raters
        P_e = sum((c / total_ratings)**2 for c in category_totals.values())

        # Fleiss' Kappa
        if P_e == 1:
            return 1.0
        return (P_bar - P_e) / (1 - P_e)

    def cohen_kappa(
        self,
        ratings_a: list[str],
        ratings_b: list[str]
    ) -> float:
        """Calculate Cohen's Kappa for two raters."""
        from sklearn.metrics import cohen_kappa_score
        return cohen_kappa_score(ratings_a, ratings_b)
```

### 6.2 Weakness Finding Analysis

**Consensus from Critiques 1, 3, 5**: Identify specific patterns where Gemini underperforms.

```python
class WeaknessFinder:
    """Identify patterns in Gemini losses for actionable insights."""

    def analyze_losses(
        self,
        results: list[AggregatedResult],
        prompts: dict[str, EnrichedPrompt],
        gemini_model_id: str
    ) -> WeaknessReport:
        """Analyze Gemini losses to identify weakness patterns."""
        losses = [
            r for r in results
            if r.winner != gemini_model_id and r.winner != "TIE"
            and gemini_model_id in {r.model_a, r.model_b}
        ]

        # Group by various dimensions
        by_category = self._group_by_dimension(losses, prompts, 'inferred_category')
        by_channel = self._group_by_dimension(losses, prompts, 'expected_format')
        by_formality = self._group_by_dimension(losses, prompts, 'formality')
        by_job_zone = self._group_by_dimension(losses, prompts, 'job_zone')
        by_industry = self._group_by_dimension(losses, prompts, 'industry')

        # Find statistically significant patterns
        significant_patterns = []

        for dimension, groups in [
            ('category', by_category),
            ('channel', by_channel),
            ('formality', by_formality),
            ('job_zone', by_job_zone),
            ('industry', by_industry)
        ]:
            for value, loss_results in groups.items():
                loss_rate = len(loss_results) / len(results)
                baseline_rate = len(losses) / len(results)

                # Chi-squared test for significance
                if self._is_significant_pattern(loss_rate, baseline_rate, len(results)):
                    significant_patterns.append(WeaknessPattern(
                        dimension=dimension,
                        value=value,
                        loss_count=len(loss_results),
                        total_count=sum(1 for r in results if self._matches_dimension(r, prompts, dimension, value)),
                        loss_rate=loss_rate,
                        baseline_rate=baseline_rate,
                        relative_risk=loss_rate / baseline_rate if baseline_rate > 0 else 0,
                        sample_prompts=[prompts[r.prompt_id] for r in loss_results[:5]]
                    ))

        # Analyze judge reasoning for common themes
        reasoning_themes = self._extract_reasoning_themes(losses)

        return WeaknessReport(
            total_losses=len(losses),
            total_comparisons=len(results),
            significant_patterns=sorted(significant_patterns, key=lambda p: -p.relative_risk),
            reasoning_themes=reasoning_themes,
            recommendations=self._generate_recommendations(significant_patterns)
        )

    def _extract_reasoning_themes(
        self,
        losses: list[AggregatedResult]
    ) -> list[ReasoningTheme]:
        """Extract common themes from judge reasoning."""
        all_weaknesses = []
        for loss in losses:
            # Collect weaknesses attributed to Gemini
            for judgment in loss.raw_judgments:
                if loss.gemini_position == 'A':
                    all_weaknesses.extend(judgment.weaknesses_a)
                else:
                    all_weaknesses.extend(judgment.weaknesses_b)

        # Count and rank themes
        theme_counts = Counter(all_weaknesses)
        total = len(all_weaknesses)

        return [
            ReasoningTheme(
                theme=theme,
                count=count,
                frequency=count / total if total > 0 else 0
            )
            for theme, count in theme_counts.most_common(20)
        ]
```

### 6.3 Bias Detection

**Consensus**: Detect and report position bias, length bias, and model self-preference.

```python
class BiasDetector:
    """Detect various biases in the evaluation."""

    def detect_position_bias(
        self,
        shuffled_judgments: list[ShuffledJudgment]
    ) -> PositionBiasReport:
        """Detect if judges favor position A or B."""
        position_a_wins = 0
        position_b_wins = 0
        total = 0

        for sj in shuffled_judgments:
            for key, winner in sj.judgments.items():
                if '_ab' in key:  # Original order
                    if winner == sj.model_a_in_position_a:
                        position_a_wins += 1
                    elif winner != "TIE":
                        position_b_wins += 1
                total += 1

        # Binomial test for position bias
        from scipy import stats
        p_value = stats.binom_test(
            position_a_wins,
            position_a_wins + position_b_wins,
            p=0.5,
            alternative='two-sided'
        )

        return PositionBiasReport(
            position_a_win_rate=position_a_wins / total if total > 0 else 0.5,
            position_b_win_rate=position_b_wins / total if total > 0 else 0.5,
            bias_detected=p_value < 0.05,
            p_value=p_value,
            recommendation="Position bias detected - review shuffling mechanism" if p_value < 0.05 else None
        )

    def detect_length_bias(
        self,
        results: list[AggregatedResult],
        responses: dict[str, dict[str, ModelResponse]]
    ) -> LengthBiasReport:
        """Detect if longer responses tend to win."""
        length_diffs = []
        winner_longer = 0
        total = 0

        for result in results:
            if result.winner == "TIE":
                continue

            prompt_responses = responses.get(result.prompt_id, {})
            len_a = len(prompt_responses.get(result.model_a, {}).get('response_text', '') or '')
            len_b = len(prompt_responses.get(result.model_b, {}).get('response_text', '') or '')

            if result.winner == result.model_a:
                winner_longer += 1 if len_a > len_b else 0
            else:
                winner_longer += 1 if len_b > len_a else 0

            length_diffs.append(abs(len_a - len_b))
            total += 1

        # Correlation test
        from scipy import stats
        correlation, p_value = stats.pearsonr(
            [1 if r.winner == r.model_a else 0 for r in results if r.winner != "TIE"],
            length_diffs[:len([r for r in results if r.winner != "TIE"])]
        ) if length_diffs else (0, 1)

        return LengthBiasReport(
            winner_longer_rate=winner_longer / total if total > 0 else 0.5,
            correlation=correlation,
            bias_detected=p_value < 0.05 and abs(correlation) > 0.3,
            p_value=p_value
        )

    def detect_self_preference(
        self,
        results: list[AggregatedResult],
        judge_model_mapping: dict[str, str]  # judge_id -> provider (openai/anthropic/google)
    ) -> SelfPreferenceReport:
        """Detect if judges favor their own provider's models."""
        preferences = defaultdict(lambda: {'same_provider': 0, 'different_provider': 0})

        for result in results:
            for judge_model, persona, winner in result.judge_persona_votes:
                if winner == "TIE":
                    continue

                judge_provider = judge_model_mapping.get(judge_model, 'unknown')
                winner_provider = self._get_provider(winner)

                if judge_provider == winner_provider:
                    preferences[judge_model]['same_provider'] += 1
                else:
                    preferences[judge_model]['different_provider'] += 1

        # Test each judge for self-preference
        biased_judges = []
        for judge, counts in preferences.items():
            same = counts['same_provider']
            diff = counts['different_provider']
            total = same + diff

            if total > 30:  # Minimum sample size
                from scipy import stats
                p_value = stats.binom_test(same, total, p=0.5, alternative='greater')
                if p_value < 0.05:
                    biased_judges.append((judge, same / total, p_value))

        return SelfPreferenceReport(
            preferences_by_judge=dict(preferences),
            biased_judges=biased_judges,
            recommendation="Consider excluding biased judges" if biased_judges else None
        )
```

### 6.4 PDF Report Generation

**Consensus**: Generate professional PDF reports with executive summary and detailed findings.

```python
class PDFReportGenerator:
    """Generate comprehensive PDF reports."""

    def __init__(self, template_dir: Path):
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True
        )

    async def generate_report(
        self,
        run_results: RunResults,
        output_path: Path,
        report_type: str = "comprehensive"
    ) -> Path:
        """Generate PDF report from evaluation results."""

        # Prepare data for template
        context = {
            'run_id': run_results.run_id,
            'timestamp': run_results.completed_at,
            'config': run_results.config,

            # Executive summary
            'summary': self._generate_executive_summary(run_results),

            # Win rates
            'win_rates': self._format_win_rates(run_results.statistics.win_rates),
            'head_to_head': self._format_head_to_head(run_results.statistics.head_to_head_matrix),

            # Charts
            'win_rate_chart': self._create_win_rate_chart(run_results),
            'confidence_chart': self._create_confidence_chart(run_results),
            'breakdown_charts': self._create_breakdown_charts(run_results),

            # Weakness analysis
            'weakness_report': run_results.weakness_report,

            # Bias analysis
            'bias_reports': run_results.bias_reports,

            # Agreement metrics
            'agreement': run_results.statistics.agreement_metrics,

            # Sample comparisons
            'sample_wins': self._select_sample_comparisons(run_results, 'wins', 5),
            'sample_losses': self._select_sample_comparisons(run_results, 'losses', 5),
        }

        # Render template
        template = self.env.get_template(f'{report_type}_report.html')
        html_content = template.render(**context)

        # Convert to PDF
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(output_path)

        return output_path

    def _create_win_rate_chart(self, results: RunResults) -> str:
        """Create win rate bar chart as base64 image."""
        import plotly.graph_objects as go

        models = list(results.statistics.win_rates.keys())
        win_rates = [results.statistics.win_rates[m].win_rate for m in models]
        ci_lows = [results.statistics.win_rates[m].confidence_interval[0] for m in models]
        ci_highs = [results.statistics.win_rates[m].confidence_interval[1] for m in models]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Win Rate',
            x=models,
            y=win_rates,
            error_y=dict(
                type='data',
                symmetric=False,
                array=[h - w for w, h in zip(win_rates, ci_highs)],
                arrayminus=[w - l for w, l in zip(win_rates, ci_lows)]
            )
        ))

        fig.update_layout(
            title='Model Win Rates (95% CI)',
            yaxis_title='Win Rate',
            yaxis_range=[0, 1]
        )

        # Convert to base64 for embedding in PDF
        import base64
        img_bytes = fig.to_image(format='png', width=800, height=400)
        return base64.b64encode(img_bytes).decode('utf-8')
```

---

## Part 7: TUI Implementation

### 7.1 Main Application Structure

**Consensus from Critiques 2, 4, 6**: Rich TUI for monitoring progress and exploring results.

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, DataTable, ProgressBar, Tree
from textual.reactive import reactive


class EvalTUI(App):
    """Main TUI application for evaluation monitoring."""

    CSS = """
    #progress-container {
        height: 30%;
        border: solid green;
    }
    #stats-container {
        height: 40%;
    }
    #log-container {
        height: 30%;
        border: solid blue;
    }
    .model-card {
        width: 1fr;
        padding: 1;
        border: solid white;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("e", "export", "Export Results"),
        ("d", "details", "View Details"),
    ]

    # Reactive state
    prompts_completed = reactive(0)
    prompts_total = reactive(0)
    current_phase = reactive("Initializing")
    model_stats = reactive({})

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            ProgressPanel(id="progress-panel"),
            id="progress-container"
        )
        yield Container(
            ModelStatsPanel(id="stats-panel"),
            id="stats-container"
        )
        yield Container(
            LogPanel(id="log-panel"),
            id="log-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Set up periodic refresh."""
        self.set_interval(1.0, self.refresh_data)

    async def refresh_data(self) -> None:
        """Refresh data from evaluation state."""
        if self.eval_state:
            self.prompts_completed = self.eval_state.completed_count
            self.prompts_total = self.eval_state.total_count
            self.current_phase = self.eval_state.current_phase
            self.model_stats = self.eval_state.model_stats

    def watch_prompts_completed(self, value: int) -> None:
        """Update progress display when completed count changes."""
        self.query_one("#progress-panel").update_progress(
            value, self.prompts_total
        )


class ProgressPanel(Static):
    """Panel showing overall progress."""

    def compose(self) -> ComposeResult:
        yield Static("Phase: Initializing", id="phase-label")
        yield ProgressBar(total=100, id="main-progress")
        yield Horizontal(
            Static("Prompts: 0/0", id="prompt-count"),
            Static("Responses: 0", id="response-count"),
            Static("Judgments: 0", id="judgment-count"),
        )
        yield Static("ETA: --:--:--", id="eta-label")

    def update_progress(self, completed: int, total: int) -> None:
        progress = (completed / total * 100) if total > 0 else 0
        self.query_one("#main-progress").update(progress=progress)
        self.query_one("#prompt-count").update(f"Prompts: {completed}/{total}")


class ModelStatsPanel(Static):
    """Panel showing per-model statistics."""

    def compose(self) -> ComposeResult:
        yield DataTable(id="model-table")

    def on_mount(self) -> None:
        table = self.query_one("#model-table")
        table.add_columns("Model", "Responses", "Wins", "Losses", "Ties", "Win Rate", "Avg Latency")

    def update_stats(self, stats: dict) -> None:
        table = self.query_one("#model-table")
        table.clear()
        for model_id, data in stats.items():
            win_rate = data['wins'] / (data['wins'] + data['losses']) if (data['wins'] + data['losses']) > 0 else 0
            table.add_row(
                model_id,
                str(data['responses']),
                str(data['wins']),
                str(data['losses']),
                str(data['ties']),
                f"{win_rate:.1%}",
                f"{data['avg_latency']:.0f}ms"
            )
```

### 7.2 Results Browser

**Consensus**: Interactive exploration of results with filtering and comparison views.

```python
class ResultsBrowser(App):
    """TUI for browsing evaluation results."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("/", "search", "Search"),
        ("enter", "view_details", "View Details"),
        ("c", "compare", "Side-by-Side Compare"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            FilterPanel(id="filters"),
            Container(
                ResultsTable(id="results-table"),
                id="results-container"
            ),
        )
        yield Footer()

    def action_view_details(self) -> None:
        """Show detailed view of selected comparison."""
        table = self.query_one("#results-table")
        if table.cursor_row is not None:
            result = self.results[table.cursor_row]
            self.push_screen(ComparisonDetailScreen(result))

    def action_compare(self) -> None:
        """Show side-by-side response comparison."""
        table = self.query_one("#results-table")
        if table.cursor_row is not None:
            result = self.results[table.cursor_row]
            self.push_screen(SideBySideScreen(result))


class SideBySideScreen(Screen):
    """Side-by-side response comparison view."""

    def __init__(self, result: AggregatedResult):
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Prompt: {self.result.prompt_id}", id="prompt-header")
        yield Horizontal(
            Vertical(
                Static(f"Model A: {self.result.model_a}", classes="model-header"),
                Static(self.result.response_a, classes="response-text"),
                id="response-a-container"
            ),
            Vertical(
                Static(f"Model B: {self.result.model_b}", classes="model-header"),
                Static(self.result.response_b, classes="response-text"),
                id="response-b-container"
            ),
        )
        yield Static(f"Winner: {self.result.winner}", id="winner-label")
        yield Footer()
```

---

## Part 8: Configuration Presets

### 8.1 Ten Preset Configurations

**Consensus**: Provide sensible presets from quick testing to comprehensive evaluation.

```python
PRESETS = {
    "smoke": PresetConfig(
        name="smoke",
        description="Quick sanity check (5 prompts, 1 judge)",
        prompts=5,
        judges=1,
        judge_models=["anthropic/claude-sonnet"],
        tiers=["flash"],
        constraints=False,
        revision_tasks=False,
        estimated_cost=0.50,
        estimated_time_minutes=2,
    ),

    "dev": PresetConfig(
        name="dev",
        description="Development testing (20 prompts, 1 judge)",
        prompts=20,
        judges=1,
        judge_models=["anthropic/claude-sonnet"],
        tiers=["flash"],
        constraints=False,
        revision_tasks=False,
        estimated_cost=2.00,
        estimated_time_minutes=5,
    ),

    "quick": PresetConfig(
        name="quick",
        description="Quick evaluation (50 prompts, 2 judges)",
        prompts=50,
        judges=2,
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2"],
        tiers=["flash"],
        constraints=True,
        revision_tasks=False,
        estimated_cost=10.00,
        estimated_time_minutes=15,
    ),

    "standard": PresetConfig(
        name="standard",
        description="Standard evaluation (200 prompts, 3 judges, both tiers)",
        prompts=200,
        judges=3,
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
        tiers=["pro", "flash"],
        constraints=True,
        revision_tasks=True,
        revision_percentage=0.1,
        estimated_cost=75.00,
        estimated_time_minutes=60,
    ),

    "comprehensive": PresetConfig(
        name="comprehensive",
        description="Comprehensive evaluation (500 prompts, full analysis)",
        prompts=500,
        judges=3,
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
        tiers=["pro", "flash"],
        constraints=True,
        revision_tasks=True,
        revision_percentage=0.2,
        ambiguous_prompts=True,
        ambiguous_percentage=0.1,
        estimated_cost=200.00,
        estimated_time_minutes=180,
    ),

    "pro-focused": PresetConfig(
        name="pro-focused",
        description="Pro tier only evaluation (300 prompts)",
        prompts=300,
        judges=3,
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
        tiers=["pro"],
        constraints=True,
        revision_tasks=True,
        revision_percentage=0.15,
        estimated_cost=150.00,
        estimated_time_minutes=120,
    ),

    "flash-focused": PresetConfig(
        name="flash-focused",
        description="Flash tier only evaluation (400 prompts)",
        prompts=400,
        judges=2,
        judge_models=["anthropic/claude-sonnet", "openai/gpt-4.1"],
        tiers=["flash"],
        constraints=True,
        revision_tasks=True,
        revision_percentage=0.15,
        estimated_cost=50.00,
        estimated_time_minutes=90,
    ),

    "weakness-hunt": PresetConfig(
        name="weakness-hunt",
        description="Targeted weakness identification (300 prompts, high diversity)",
        prompts=300,
        judges=3,
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
        tiers=["pro", "flash"],
        constraints=True,
        revision_tasks=True,
        ambiguous_prompts=True,
        force_diversity=True,
        estimated_cost=175.00,
        estimated_time_minutes=150,
    ),

    "budget": PresetConfig(
        name="budget",
        description="Budget-conscious evaluation (100 prompts, cheaper judges)",
        prompts=100,
        judges=2,
        judge_models=["anthropic/claude-sonnet", "openai/gpt-4.1"],
        tiers=["flash"],
        constraints=False,
        revision_tasks=False,
        estimated_cost=15.00,
        estimated_time_minutes=30,
    ),

    "full": PresetConfig(
        name="full",
        description="Full production evaluation (1000 prompts)",
        prompts=1000,
        judges=3,
        judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
        tiers=["pro", "flash"],
        constraints=True,
        revision_tasks=True,
        revision_percentage=0.2,
        ambiguous_prompts=True,
        ambiguous_percentage=0.1,
        estimated_cost=500.00,
        estimated_time_minutes=360,
    ),
}
```

---

## Part 9: Error Handling and Recovery

### 9.1 Checkpoint System

**Strong Consensus**: Atomic checkpointing for full recoverability.

```python
class CheckpointManager:
    """Manage evaluation checkpoints for recovery."""

    def __init__(self, run_dir: Path, db: Database):
        self.run_dir = run_dir
        self.db = db
        self.checkpoint_file = run_dir / "checkpoint.json"
        self.temp_file = run_dir / "checkpoint.json.tmp"

    async def save_checkpoint(self, state: EvalState) -> None:
        """Atomically save checkpoint state."""
        checkpoint_data = {
            "version": 1,
            "timestamp": datetime.utcnow().isoformat(),
            "phase": state.current_phase,
            "completed_prompt_ids": list(state.completed_prompts),
            "pending_prompt_ids": list(state.pending_prompts),
            "failed_prompt_ids": list(state.failed_prompts),
            "model_progress": {
                model_id: {
                    "completed": list(progress.completed),
                    "pending": list(progress.pending),
                    "failed": list(progress.failed),
                }
                for model_id, progress in state.model_progress.items()
            },
            "judgment_progress": {
                "completed_pairs": [
                    {"prompt_id": p, "model_a": a, "model_b": b}
                    for p, a, b in state.completed_judgments
                ],
                "pending_pairs": [
                    {"prompt_id": p, "model_a": a, "model_b": b}
                    for p, a, b in state.pending_judgments
                ],
            },
            "statistics": state.current_statistics.model_dump() if state.current_statistics else None,
        }

        # Atomic write: write to temp, then rename
        async with aiofiles.open(self.temp_file, 'w') as f:
            await f.write(json.dumps(checkpoint_data, indent=2))

        # Atomic rename
        self.temp_file.rename(self.checkpoint_file)

        # Also persist to database for redundancy
        await self.db.save_checkpoint(checkpoint_data)

    async def load_checkpoint(self) -> EvalState | None:
        """Load checkpoint if exists."""
        if not self.checkpoint_file.exists():
            # Try database fallback
            db_checkpoint = await self.db.load_latest_checkpoint()
            if db_checkpoint:
                return self._checkpoint_to_state(db_checkpoint)
            return None

        async with aiofiles.open(self.checkpoint_file) as f:
            data = json.loads(await f.read())

        return self._checkpoint_to_state(data)

    async def resume_evaluation(
        self,
        orchestrator: EvalOrchestrator,
        checkpoint: EvalState
    ) -> None:
        """Resume evaluation from checkpoint."""
        logger.info(f"Resuming from checkpoint at phase: {checkpoint.current_phase}")

        # Restore state
        orchestrator.state = checkpoint

        # Resume from appropriate phase
        if checkpoint.current_phase == "prompt_generation":
            await orchestrator.continue_prompt_generation()
        elif checkpoint.current_phase == "response_collection":
            await orchestrator.continue_response_collection()
        elif checkpoint.current_phase == "judging":
            await orchestrator.continue_judging()
        elif checkpoint.current_phase == "analysis":
            await orchestrator.run_analysis()


class FailureHandler:
    """Handle and recover from various failure modes."""

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 5, 30]  # Exponential backoff

    async def with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str,
        checkpoint_callback: Callable[[], Awaitable[None]] | None = None
    ) -> T:
        """Execute operation with retry and checkpointing."""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await operation()

                # Checkpoint on success
                if checkpoint_callback:
                    await checkpoint_callback()

                return result

            except RateLimitError as e:
                # Rate limit: wait longer
                wait_time = e.retry_after or self.RETRY_DELAYS[attempt] * 10
                logger.warning(f"{operation_name} rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                last_error = e

            except TransientError as e:
                # Transient error: standard backoff
                wait_time = self.RETRY_DELAYS[attempt]
                logger.warning(f"{operation_name} transient error, retry in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
                last_error = e

            except PermanentError as e:
                # Permanent error: don't retry
                logger.error(f"{operation_name} permanent error: {e}")
                raise

        # All retries exhausted
        raise MaxRetriesExceeded(f"{operation_name} failed after {self.MAX_RETRIES} retries: {last_error}")
```

### 9.2 Circuit Breaker Pattern

**Consensus from Critiques 3, 5**: Protect against cascading failures.

```python
class CircuitBreaker:
    """Circuit breaker for API calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self._states: dict[str, CircuitState] = {}
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._last_failure_time: dict[str, float] = {}
        self._half_open_successes: dict[str, int] = defaultdict(int)

    def allow_request(self, service_id: str) -> bool:
        """Check if request should be allowed."""
        state = self._states.get(service_id, CircuitState.CLOSED)

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            last_failure = self._last_failure_time.get(service_id, 0)
            if time.time() - last_failure >= self.recovery_timeout:
                self._states[service_id] = CircuitState.HALF_OPEN
                self._half_open_successes[service_id] = 0
                return True
            return False

        if state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open state
            return True

        return False

    def record_success(self, service_id: str) -> None:
        """Record successful request."""
        state = self._states.get(service_id, CircuitState.CLOSED)

        if state == CircuitState.HALF_OPEN:
            self._half_open_successes[service_id] += 1
            if self._half_open_successes[service_id] >= self.half_open_requests:
                # Recovered - close circuit
                self._states[service_id] = CircuitState.CLOSED
                self._failure_counts[service_id] = 0

        # Reset failure count on success in closed state
        if state == CircuitState.CLOSED:
            self._failure_counts[service_id] = 0

    def record_failure(self, service_id: str) -> None:
        """Record failed request."""
        state = self._states.get(service_id, CircuitState.CLOSED)

        if state == CircuitState.HALF_OPEN:
            # Failure in half-open: reopen circuit
            self._states[service_id] = CircuitState.OPEN
            self._last_failure_time[service_id] = time.time()
            return

        # Increment failure count
        self._failure_counts[service_id] += 1
        self._last_failure_time[service_id] = time.time()

        if self._failure_counts[service_id] >= self.failure_threshold:
            self._states[service_id] = CircuitState.OPEN
            logger.warning(f"Circuit opened for {service_id}")
```

---

## Part 10: Implementation Timeline and Risk Mitigation

### 10.1 Phased Implementation Plan

**Consensus**: Build incrementally with validation at each phase.

```
Week 1-2: Foundation
- [ ] Project setup (pyproject.toml, directory structure)
- [ ] Pydantic schemas for all data models
- [ ] SQLite database with migrations
- [ ] Configuration management with presets
- [ ] Basic CLI skeleton

Week 3-4: Data Pipeline
- [ ] O*NET schema validation
- [ ] O*NET task extraction
- [ ] NAICS mapping with fallbacks
- [ ] Company database loader
- [ ] Name generator
- [ ] Phase 1: Persona generation (with caching)

Week 5-6: Prompt Generation
- [ ] Phase 2: Algorithmic combiner
- [ ] Phase 3: LLM enricher
- [ ] Constraint generator
- [ ] Revision generator
- [ ] Prompt deduplication
- [ ] Stratified sampling validation

Week 7-8: API Layer
- [ ] OpenRouter client
- [ ] Rate limiter
- [ ] Circuit breaker
- [ ] Model verifier
- [ ] Response collector
- [ ] Checkpoint system

Week 9-10: Evaluation Engine
- [ ] Dual-persona judge
- [ ] Position bias handler
- [ ] Vote aggregator
- [ ] Robust JSON parser
- [ ] Auto-loss detector
- [ ] Constraint checker

Week 11-12: Analysis & Reporting
- [ ] Statistics engine
- [ ] Agreement metrics
- [ ] Bias detector
- [ ] Weakness finder
- [ ] PDF report generator
- [ ] Chart builder

Week 13-14: TUI & Polish
- [ ] Progress dashboard
- [ ] Results browser
- [ ] Side-by-side viewer
- [ ] Error recovery UI
- [ ] Documentation
- [ ] Integration testing
```

### 10.2 Critical Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OpenRouter model IDs change | Medium | High | Runtime verification, fallback logic |
| O*NET schema differs from expected | Medium | High | Schema validation before queries |
| API rate limits exceeded | High | Medium | Adaptive rate limiting, circuit breaker |
| Judge parse failures | Medium | Medium | 4-tier fallback parsing |
| Budget overrun | Medium | High | Pre-evaluation cost estimation, hard limits |
| Checkpoint corruption | Low | High | Dual storage (file + DB), atomic writes |
| Position bias affects results | Medium | Medium | Shuffling, statistical detection |
| Judge self-preference | Medium | Medium | Cross-provider judging, bias detection |

### 10.3 Validation Milestones

1. **Milestone 1: Data Pipeline** (End of Week 4)
   - Can extract 1000+ writing tasks from O*NET
   - Diversity statistics across job zones, SOC codes
   - Company/name generation works correctly

2. **Milestone 2: Prompt Generation** (End of Week 6)
   - Can generate 500 diverse, enriched prompts
   - No near-duplicates detected
   - Stratification validates diversity

3. **Milestone 3: Response Collection** (End of Week 8)
   - Can collect responses from all models
   - Checkpoint/resume works across interruptions
   - Rate limiting prevents API errors

4. **Milestone 4: Evaluation** (End of Week 10)
   - Dual-persona judging produces valid results
   - Position shuffle eliminates position bias
   - Vote aggregation matches expected outcomes

5. **Milestone 5: Full System** (End of Week 14)
   - End-to-end smoke test passes
   - 200-prompt standard evaluation completes
   - PDF report generates correctly

---

## Appendix A: Pydantic Schema Definitions

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional


class CompanySize(str, Enum):
    STARTUP = "startup"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class PersonName(BaseModel):
    first: str
    last: str
    full: str
    demographic: str
    gender: str


class Company(BaseModel):
    name: str
    industry: str
    size: CompanySize
    naics: str
    is_generated: bool = False


class ONetTask(BaseModel):
    task_id: str
    onetsoc_code: str
    task: str
    occupation_title: str
    job_zone: int
    soc_major_group: str
    writing_relevance_score: float
    inferred_category: str
    inferred_channel: str


class Persona(BaseModel):
    id: str
    job_title: str
    experience_level: str
    communication_style: str
    industry_focus: str
    personality_traits: list[str]
    challenges: list[str]


class ScenarioSeed(BaseModel):
    id: str
    task_id: str
    scenario_type: str
    context: str
    stakes: str
    audience: str
    key_challenges: list[str]


class BasePrompt(BaseModel):
    id: str
    task: ONetTask
    persona: Persona
    scenario_seed: ScenarioSeed
    sender: PersonName
    recipient: PersonName
    company: Company
    industry: str
    word_count_tier: str
    urgency: str
    formality: str
    raw_combined: bool = True
    needs_enrichment: bool = True


class EnrichedPrompt(BasePrompt):
    prompt_text: str
    expected_format: str
    key_points: list[str]
    quality_signals: list[str]
    context_details: dict
    enriched_at: datetime
    enrichment_model: str


class ModelResponse(BaseModel):
    prompt_id: str
    model_id: str
    response_text: Optional[str]
    error: Optional[str]
    status: str
    latency_ms: float
    token_count: int
    input_tokens: int = 0
    output_tokens: int = 0


class JudgmentResult(BaseModel):
    prompt_id: str
    judge_model: str
    persona_type: str
    winner: str
    confidence: str
    reasoning: str
    strengths_a: list[str]
    strengths_b: list[str]
    weaknesses_a: list[str]
    weaknesses_b: list[str]
    raw_response: str
    parse_success: bool


class AggregatedResult(BaseModel):
    prompt_id: str
    winner: str
    model_a: str
    model_b: str
    vote_breakdown: dict[str, int]
    judge_persona_votes: list[tuple[str, str, str]]
    inter_judge_agreement: bool
    inter_persona_agreement: bool
    position_consistency: float
    confidence: str
```

---

## Appendix B: CLI Commands

```bash
# Run evaluation with preset
gemini-eval run --preset standard

# Run with custom config
gemini-eval run --prompts 300 --judges 3 --tiers pro,flash

# Resume interrupted evaluation
gemini-eval resume runs/2024-01-15_14-30-00

# View results in TUI
gemini-eval results runs/2024-01-15_14-30-00

# Generate PDF report
gemini-eval report runs/2024-01-15_14-30-00 --output report.pdf

# Export results to CSV
gemini-eval export runs/2024-01-15_14-30-00 --format csv

# Validate O*NET database
gemini-eval validate-onet db/onet.db

# Verify OpenRouter models
gemini-eval verify-models

# Estimate costs for a configuration
gemini-eval estimate --preset comprehensive

# Compare multiple runs
gemini-eval compare runs/run1 runs/run2 runs/run3
```

---

*End of Master Plan*

