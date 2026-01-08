# Simulation 4: Implementation Dry-Run Analysis

## Executive Summary

This document simulates implementing the entire Gemini Writing Evaluation Framework master plan step-by-step, identifying what works well, what fails or is unclear, missing pieces, technical blockers, and specific improvements needed. The simulation walks through each component as if actually coding it, documenting every issue encountered.

---

## Part 1: Project Setup and Foundation

### 1.1 Directory Structure Creation

**Simulation Steps:**
1. Create `gemini-writing-eval/` root directory
2. Create all subdirectories per the plan
3. Initialize `pyproject.toml` with dependencies

**What Works Well:**
- Directory structure is comprehensive and well-organized
- Separation of concerns is clear (data, prompts, eval, api, storage, analysis, reports, tui)
- Technology stack is modern and well-chosen

**Issues Identified:**

1. **Missing `__init__.py` files**: The plan only shows `src/__init__.py` but not for subpackages. Every directory needs one for proper Python package structure.

2. **Dependency version conflicts**: The plan specifies `textual>=0.52` but current stable textual is around 0.47.x (as of late 2024). Need to verify actual available versions.

3. **WeasyPrint system dependencies**: WeasyPrint requires GTK/Pango system libraries that aren't mentioned. On macOS: `brew install pango gdk-pixbuf libffi cairo`. On Linux: `apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0`. This is a potential blocker for users without admin access.

4. **Missing test directory structure**: `tests/` exists but no organization (unit, integration, fixtures, conftest.py).

**Suggested Fix:**
```
tests/
  __init__.py
  conftest.py              # pytest fixtures
  fixtures/                # test data
  unit/
    test_onet_extractor.py
    test_prompt_generator.py
    ...
  integration/
    test_full_pipeline.py
```

### 1.2 Configuration Management

**Simulation Steps:**
1. Implement `src/config/settings.py` with Pydantic settings
2. Implement `src/config/presets.py` with 10 presets
3. Implement `src/config/models.py` with model registry

**What Works Well:**
- Using pydantic-settings for env var management
- 10 presets cover good range of use cases
- Estimated costs provided upfront

**Issues Identified:**

1. **Environment variable naming not specified**: The plan shows `.env.example` but doesn't define variable names. Critical ones needed:
   - `OPENROUTER_API_KEY`
   - `EVAL_RUN_DIR` (where to store results)
   - `ONET_DB_PATH` (path to O*NET database)
   - `LOG_LEVEL`

2. **Preset cost estimates are likely outdated**: Model pricing changes frequently. Need dynamic pricing from OpenRouter API.

3. **Missing budget validation**: The plan mentions budget limits but doesn't show how to enforce them mid-evaluation or warn before exceeding.

**Suggested Addition to settings.py:**
```python
class Settings(BaseSettings):
    openrouter_api_key: SecretStr
    onet_db_path: Path = Path("db/onet.db")
    results_dir: Path = Path("results")
    log_level: str = "INFO"
    max_concurrent_requests: int = 10
    budget_limit: float | None = None
    budget_warning_threshold: float = 0.8  # Warn at 80% of budget

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVAL_"
    )
```

---

## Part 2: O*NET Data Pipeline Simulation

### 2.1 Schema Validation

**Simulation Steps:**
1. Connect to `db/onet.db`
2. Query `sqlite_master` for table names
3. Verify required columns exist
4. Check for required element IDs

**What Works Well:**
- Validation-first approach catches schema mismatches early
- Clear error messages for missing tables/columns
- Warning system for missing data vs hard failures

**Issues Identified:**

1. **Actual O*NET schema differs from plan assumptions**: Looking at the `ONET_WRITING_REFERENCE.md`, the actual tables are:
   - `task_statements` (exists, columns match)
   - `occupation_data` (exists, columns match)
   - `job_zones` (exists, columns match)
   - `work_context` (exists, columns match)
   - `skills` (exists, columns match)

   However, the plan's validator checks for columns that may not exist exactly as named. Need to verify actual column names.

2. **Element IDs need verification**: The plan references:
   - `2.A.1.c` for Writing Skill
   - `4.C.1.a.2.h` for Email Work Context
   - `4.C.1.a.2.j` for Letters/Memos

   These need to be verified against actual `content_model_reference` table.

3. **Missing scale_id validation**: The plan uses `scale_id = 'IM'` for importance and `scale_id = 'CX'` for context, but doesn't validate these exist.

**Actual Query to Verify (from reference doc):**
```sql
SELECT element_id, element_name FROM content_model_reference
WHERE element_name LIKE '%Writing%' OR element_id LIKE '2.A.1%';
```

**Blocker Potential**: If element IDs don't match, the writing relevance scoring will fail silently (return NULLs that default to 2.5).

### 2.2 Task Extraction

**Simulation Steps:**
1. Execute the large JOIN query from `ONetExtractor`
2. Compute writing relevance scores
3. Filter by job zones and SOC codes
4. Return structured `ONetTask` objects

**What Works Well:**
- Multi-factor relevance scoring (text patterns + O*NET scores)
- Inference of category and channel from task text
- Filtering support for stratified sampling

**Issues Identified:**

1. **Query performance concern**: The query joins 5+ tables with potentially 18,796 rows. Missing indexes could make this slow.

2. **NULL handling incomplete**: The query uses `COALESCE(jz.job_zone, 3)` but job_zone 3 is "Medium Preparation" - this default may not be appropriate for all cases where data is missing.

3. **Writing relevance threshold (0.5) is arbitrary**: The `min_relevance=0.5` default needs validation. What percentage of tasks does this exclude? Should be configurable.

4. **Category inference is too simplistic**: The `_infer_category` method uses basic keyword matching with no disambiguation. For example, a task containing both "report" and "customer" would be categorized as "documentation" (first match) rather than potentially more appropriate "customer_communication".

5. **Missing emerging_tasks integration**: The reference doc mentions 328 emerging tasks in `emerging_tasks` table, but the extractor only queries `task_statements`. These newer tasks may reflect modern communication (email, social media) better.

**Suggested Fix for Category Inference:**
```python
def _infer_category(self, task_text: str) -> str:
    """Score-based category inference with multiple signals."""
    task_lower = task_text.lower()
    scores = defaultdict(float)

    # More specific patterns score higher
    patterns = [
        ('customer_communication', ['customer', 'client', 'patient'], 1.5),
        ('documentation', ['document', 'record'], 1.2),
        ('correspondence', ['email', 'correspond', 'letter'], 1.3),
        ('proposals', ['propos', 'recommend', 'suggest'], 1.1),
        ('reports', ['report', 'present'], 1.0),
        # ... etc
    ]

    for category, keywords, weight in patterns:
        for kw in keywords:
            if kw in task_lower:
                scores[category] += weight

    if not scores:
        return 'general_communication'
    return max(scores, key=scores.get)
```

### 2.3 NAICS Industry Mapping

**Simulation Steps:**
1. Load BLS Occupation-Industry Matrix (if available)
2. Fall back to SOC-to-NAICS mapping
3. Sample weighted by distribution

**What Works Well:**
- Multiple fallback strategies (BLS -> manual mapping -> uniform)
- Weighted sampling for realistic industry distribution
- Exclusion support for diversity

**Issues Identified:**

1. **BLS Matrix data source not specified**: The plan mentions `bls_matrix_path` but doesn't explain where to get this data or format. This is a critical external dependency.

2. **BLS data format unknown**: Is it CSV? Excel? What columns? How to parse? The plan assumes it exists but provides no integration code.

3. **NAICS code granularity mismatch**: The plan uses 2-digit NAICS sectors (20 categories) but real NAICS can be 6 digits. Many occupation-industry mappings use 3-4 digit codes.

4. **Missing NAICS validation**: When sampling an industry code, there's no validation that the returned code is a valid NAICS sector.

**Critical Gap - BLS Data Integration:**
The BLS publishes the "National Industry-Occupation Employment Matrix" at:
https://www.bls.gov/emp/tables/ind-occ-matrix.htm

This is an Excel file that needs to be:
1. Downloaded
2. Parsed (complex multi-sheet structure)
3. Converted to the expected format

Without this, the system falls back to manually specified mappings that may not reflect actual industry distributions.

**Suggested Addition:**
```python
class BLSMatrixParser:
    """Parse BLS Industry-Occupation Matrix Excel file."""

    def parse(self, excel_path: Path) -> dict[str, list[tuple[str, float]]]:
        """
        Returns: {soc_code: [(naics_code, employment_share), ...]}
        """
        import openpyxl
        # Complex parsing logic for BLS format
        # Multiple sheets, merged cells, footnotes to handle
```

### 2.4 Company Database

**Simulation Steps:**
1. Load curated `data/companies.json`
2. Match by NAICS and size
3. Fall back to LLM generation
4. Ultimate fallback to generic names

**What Works Well:**
- Real companies for realism
- LLM generation fallback
- Caching of generated companies
- Size diversity (startup to enterprise)

**Issues Identified:**

1. **`companies.json` not provided**: The plan assumes this file exists with structure:
   ```json
   [{"name": "...", "naics": "...", "size": "...", "industry": "..."}]
   ```
   But no actual data is provided. This is a critical missing asset.

2. **Minimum company count needed**: How many companies per NAICS/size combination? With 20 NAICS sectors x 5 sizes = 100 cells, need ~500+ companies for reasonable diversity.

3. **Async in sync context**: The `get_company` method has `await self._generate_companies(...)` but the method isn't marked async. This will fail.

4. **LLM client dependency**: The company generation requires an LLM client, but this creates circular dependency - we need companies to generate prompts, but prompts go to LLMs.

5. **Company data currency**: Real company data becomes stale (acquisitions, bankruptcies, name changes). Need update mechanism or recency check.

**Suggested Fix:**
```python
# Create separate script to pre-generate companies.json
# scripts/generate_companies.py

async def generate_company_database(
    naics_sectors: list[str],
    sizes: list[str],
    companies_per_cell: int = 10,
    llm_client: LLMClient
) -> list[dict]:
    """Pre-generate company database offline."""
    companies = []
    for naics in naics_sectors:
        for size in sizes:
            generated = await generate_companies_for_sector(
                naics, size, companies_per_cell, llm_client
            )
            companies.extend(generated)

    # Add curated real companies
    companies.extend(load_curated_companies())

    return companies
```

---

## Part 3: Prompt Generation Pipeline Simulation

### 3.1 Phase 1: Offline Persona Generation

**Simulation Steps:**
1. Check for cached personas at `cache_path`
2. If not found, generate via LLM
3. Parse response JSON
4. Cache to file

**What Works Well:**
- Caching prevents repeated LLM calls
- Diversity requirements specified in prompt
- Reusable across evaluation runs

**Issues Identified:**

1. **LLM client not defined**: The plan uses `llm_client.generate(...)` but doesn't show the `LLMClient` interface or implementation. Critical missing piece.

2. **Model selection unclear**: `model="smart_cheap"` - what model is this? Need mapping to actual OpenRouter model IDs.

3. **Parse error handling missing**: If LLM returns malformed JSON, `_parse_personas` will fail. No retry or fallback logic shown.

4. **Persona count not specified**: How many personas should be generated? 50? 100? 500? This affects diversity.

5. **Persona validation missing**: Generated personas could be duplicates, unrealistic, or miss required fields. No validation shown.

**Suggested Model Mapping:**
```python
MODEL_ALIASES = {
    "smart_cheap": "anthropic/claude-3-haiku",  # Fast, cheap, decent
    "smart_medium": "anthropic/claude-3-sonnet",
    "smart_expensive": "anthropic/claude-opus-4.5",
    "cheap_fast": "openai/gpt-4o-mini",
}
```

### 3.2 Phase 2: Algorithmic Combination

**Simulation Steps:**
1. Build all possible combinations
2. Apply multi-dimensional stratified sampling
3. Convert combinations to `BasePrompt` objects

**What Works Well:**
- Clear stratification dimensions
- Multi-pass sampling ensures coverage
- Deterministic with seed

**Issues Identified:**

1. **Combinatorial explosion**: With 18,000 tasks x 100 personas x 20 industries x 3 formalities x 3 urgencies = billions of combinations. The `_generate_all_combinations()` method will run out of memory.

2. **Sampling strategy is O(n^2)**: The `_stratified_sample` method iterates through all combinations multiple times. With billions of items, this is infeasible.

3. **Missing dimension values**: The combination dict needs values for all stratification dimensions, but some (like `word_count_tier`, `urgency`) aren't clearly sourced.

4. **`ScenarioSeed` matching unclear**: How does a task get matched to a scenario seed? The plan shows separate generation but not the pairing logic.

**Critical Fix - Lazy Sampling:**
```python
def generate_prompts(self, count: int, seed: int) -> list[BasePrompt]:
    """Generate prompts using lazy evaluation - NOT exhaustive enumeration."""
    rng = random.Random(seed)
    prompts = []

    # Track stratum coverage
    stratum_counts = defaultdict(int)
    min_per_stratum = max(1, count // (5 * 10 * 6 * 3))  # Rough estimate

    for _ in range(count * 10):  # Oversample then trim
        # Sample each dimension independently
        task = rng.choice(self.tasks)
        persona = rng.choice(self.personas)
        scenario_seed = self._match_scenario_seed(task, rng)
        urgency = rng.choice(['low', 'medium', 'high'])
        word_count = rng.choice(['short', 'medium', 'long'])

        # Build stratum key
        stratum = (
            task.job_zone,
            task.inferred_category,
            task.inferred_channel,
            persona.communication_style,
            word_count,
            urgency,
            task.soc_major_group,
            # NAICS sampled separately
        )

        # Accept if stratum underrepresented
        if stratum_counts[stratum] < min_per_stratum:
            stratum_counts[stratum] += 1
            prompts.append(self._build_prompt(task, persona, scenario_seed, ...))

        if len(prompts) >= count:
            break

    return prompts[:count]
```

### 3.3 Phase 3: LLM Enrichment

**Simulation Steps:**
1. Format enrichment prompt with base prompt data
2. Call LLM to generate full prompt text
3. Parse structured response
4. Create `EnrichedPrompt`

**What Works Well:**
- Clear prompt template
- Structured JSON output
- Batch processing with concurrency control
- Checkpoint callback support

**Issues Identified:**

1. **Prompt template has dangerous `.format()` calls**: If any field contains `{` or `}` characters, the format string will break.

2. **Temperature 0.7 may cause inconsistency**: For evaluation prompts, we want consistent quality. High temperature increases variance.

3. **No length limit on generated prompts**: The LLM might generate very long prompt_text that exceeds context limits when used for evaluation.

4. **Missing retry on parse failure**: If `_parse_enrichment` fails, the whole batch fails.

5. **Concurrency of 5 may hit rate limits**: Depending on models used, 5 concurrent requests might exceed OpenRouter rate limits.

**Suggested Fix for Template:**
```python
ENRICHMENT_PROMPT = """
You are creating a realistic writing prompt for evaluating AI writing assistants.

Base scenario:
- Writer role: {persona_job_title} at {company_name} ({industry})
- Task from O*NET: {task_description}
- Writing type: {scenario_type}
- Recipient: {recipient_name}
- Context: {scenario_context}

... rest of prompt ...
"""

async def enrich_prompt(self, base_prompt: BasePrompt, llm_client: LLMClient) -> EnrichedPrompt:
    # Use explicit substitution to avoid .format() issues
    filled_prompt = self.ENRICHMENT_PROMPT.format(
        persona_job_title=base_prompt.persona.job_title,
        company_name=base_prompt.company.name,
        industry=base_prompt.industry,
        task_description=base_prompt.task.task,
        scenario_type=base_prompt.scenario_seed.scenario_type,
        recipient_name=base_prompt.recipient.full,
        scenario_context=base_prompt.scenario_seed.context,
        word_count_tier=base_prompt.word_count_tier,
        urgency=base_prompt.urgency,
        formality=base_prompt.formality
    )
```

---

## Part 4: API Layer Simulation

### 4.1 OpenRouter Client

**Simulation Steps:**
1. Initialize httpx async client
2. Set authorization headers
3. Implement `generate()` method with proper payload
4. Handle response parsing

**What Works Well:**
- Plan uses httpx (modern async HTTP)
- Mentions proper error handling patterns

**Issues Identified:**

1. **OpenRouter API interface not fully specified**: The plan shows conceptual methods but not actual API endpoints or payload formats.

2. **OpenRouter base URL**: `https://openrouter.ai/api/v1/` - this needs verification.

3. **Request format**: OpenRouter uses OpenAI-compatible format but with extra headers. Need:
   ```python
   headers = {
       "Authorization": f"Bearer {api_key}",
       "HTTP-Referer": "https://your-site.com",  # Optional
       "X-Title": "Gemini Writing Eval",  # Optional
   }
   ```

4. **Response streaming not addressed**: For long responses, streaming might be beneficial but isn't mentioned.

5. **Token counting pre-request**: The plan shows `_estimate_max_tokens(prompt)` but doesn't define how to estimate input tokens for cost projection.

**Suggested OpenRouter Client:**
```python
class OpenRouterClient:
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        return GenerateResponse(
            content=data["choices"][0]["message"]["content"],
            usage=Usage(
                prompt_tokens=data["usage"]["prompt_tokens"],
                completion_tokens=data["usage"]["completion_tokens"],
                total_tokens=data["usage"]["total_tokens"],
            ),
            model=data["model"],
        )
```

### 4.2 Rate Limiter Implementation

**Simulation Steps:**
1. Create token bucket per model
2. Track requests per second/minute
3. Block when limit reached
4. Release tokens over time

**What Works Well:**
- Plan mentions rate limiting concept
- Per-model tracking (different models have different limits)

**Issues Identified:**

1. **No implementation provided**: The plan references `RateLimiter` class but doesn't show implementation.

2. **OpenRouter rate limits unknown**: What are actual limits? Per-model? Per-account? Need to query or document.

3. **Rate limit headers not parsed**: OpenRouter returns `X-RateLimit-*` headers that should be used to adapt.

4. **No backpressure mechanism**: If all models are rate-limited, what happens? Need queue or rejection logic.

**Suggested Implementation:**
```python
class TokenBucketRateLimiter:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= tokens


class RateLimiter:
    def __init__(self):
        # Default conservative limits (adjust based on OpenRouter docs)
        self.limiters = defaultdict(
            lambda: TokenBucketRateLimiter(rate=1.0, capacity=10)
        )

    async def acquire(self, model_id: str) -> None:
        await self.limiters[model_id].acquire()
```

### 4.3 Model Verifier

**Simulation Steps:**
1. Query OpenRouter `/api/v1/models` endpoint
2. Parse available models
3. Match expected to available
4. Handle missing models

**What Works Well:**
- Runtime verification of model availability
- Similar model fallback logic
- Clear error for completely missing models

**Issues Identified:**

1. **Expected model IDs are speculative**: The plan lists models like `google/gemini-3.0-pro` but these are predictions for future models. Actual IDs will differ.

2. **Similar model matching is naive**: The `_find_similar` method just checks if parts of the name appear. This could match wrong models (e.g., `gpt-4` matching `gpt-4-turbo` or `gpt-4o`).

3. **No model capability verification**: Just because a model exists doesn't mean it supports the features needed (long context, JSON mode, etc.).

4. **Missing model pricing extraction**: OpenRouter's `/models` endpoint includes pricing which should be extracted for cost estimation.

**Suggested Model Verification:**
```python
async def verify_models(self, client: httpx.AsyncClient, api_key: str) -> ModelRegistry:
    response = await client.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    response.raise_for_status()

    available = {}
    for model in response.json()["data"]:
        available[model["id"]] = ModelInfo(
            id=model["id"],
            name=model.get("name", model["id"]),
            context_length=model.get("context_length", 4096),
            pricing={
                "prompt": model.get("pricing", {}).get("prompt", 0),
                "completion": model.get("pricing", {}).get("completion", 0),
            },
            supports_json_mode="json" in model.get("supported_parameters", []),
        )

    # Match expected to available with validation
    registry = ModelRegistry()
    for key, expected_pattern in self.EXPECTED_MODELS.items():
        matches = [m for m in available.values() if self._matches_pattern(m, expected_pattern)]
        if not matches:
            raise ModelNotFoundError(f"No model matching {expected_pattern}")

        # Pick best match (e.g., latest version)
        best = self._select_best_match(matches)
        registry.register(key, best)

    return registry
```

---

## Part 5: Evaluation Engine Simulation

### 5.1 Response Collection

**Simulation Steps:**
1. Iterate through all prompts
2. For each prompt, collect responses from all models in tier
3. Handle failures with retry/circuit breaker
4. Checkpoint after each successful collection

**What Works Well:**
- Parallel collection from multiple models
- Clear separation of success vs failure tracking
- Checkpoint callback for resumability

**Issues Identified:**

1. **Model tier configuration unclear**: The plan references `tier_config.get_models(tier)` but doesn't show how tiers are configured or what models belong to each.

2. **Response timeout not specified**: Different models have different latencies. Long responses could timeout. Need configurable timeout per model class.

3. **Empty response handling**: What if a model returns empty string? Is that a failure or valid response?

4. **Max tokens estimation**: `_estimate_max_tokens(prompt)` is referenced but not implemented. This affects both cost and response truncation.

5. **Response storage not shown**: Where are responses written? JSON files? Database? Both?

**Critical Issue - Tier Definition Missing:**
```python
# Needs to be specified in config/models.py
PRO_TIER_MODELS = [
    "google/gemini-3.0-pro",
    "openai/gpt-5.2",
    "anthropic/claude-opus-4.5",
    "x-ai/grok-4.1",
    "moonshot/kimi-k2",
]

FLASH_TIER_MODELS = [
    "google/gemini-3.0-flash",
    "openai/gpt-4.1",
    "anthropic/claude-sonnet",
]

# Which models to compare against (Gemini always vs one competitor)
PRO_COMPARISONS = [
    ("google/gemini-3.0-pro", "openai/gpt-5.2"),
    ("google/gemini-3.0-pro", "anthropic/claude-opus-4.5"),
    ("google/gemini-3.0-pro", "x-ai/grok-4.1"),
    ("google/gemini-3.0-pro", "moonshot/kimi-k2"),
]
```

### 5.2 Dual-Persona Judging

**Simulation Steps:**
1. Format comparison prompt with both responses
2. Call judge with Writing Expert persona
3. Call judge with Simulated Recipient persona
4. Return both judgments

**What Works Well:**
- Dual-persona concept is sound
- Clear system prompts for each persona
- Structured JSON output

**Issues Identified:**

1. **Judge context is incomplete**: The plan shows judge prompts but doesn't include all the context PROMPT.md requires:
   - Writer persona details (age, skill level, role, industry, generation)
   - Target recipient/consumer persona
   - Formality level
   - Communication context
   - Additional scenario-specific context

2. **Recipient persona generation is vague**: `_infer_recipient_role(prompt)` - how is this inferred? The prompt has `recipient: PersonName` but role isn't stored.

3. **Response position not tracked in judgment**: The judgment result stores winner as "A" or "B" but doesn't record which model was in which position for this specific judgment.

4. **Temperature 0.3 may still cause inconsistency**: For reproducibility, temperature 0 or seed parameter would be better.

5. **No judge prompt length check**: If both responses are very long, the judge prompt could exceed context limits.

**Enhanced Judge Context:**
```python
COMPARISON_PROMPT_ENHANCED = """
You are comparing two responses to this writing prompt:

CONTEXT:
- Writer: {writer_name}, {writer_role} at {company} ({industry})
- Writer Profile: {experience_level} level, {communication_style} style, {age_group} generation
- Recipient: {recipient_name}, {recipient_role}
- Communication Type: {expected_format}
- Formality Level: {formality}
- Urgency: {urgency}

PROMPT:
{prompt_text}

RESPONSE A:
{response_a}

RESPONSE B:
{response_b}

Evaluate both responses considering:
1. Appropriateness for the specific writer persona
2. Effectiveness for the specific recipient
3. Match to expected formality and tone
4. Task completion and accuracy
5. Authenticity (does it sound AI-generated or natural?)
6. Avoidance of cliches and boilerplate

Provide your judgment as JSON:
{{
    "reasoning": "Brief explanation (2-3 sentences)",
    "winner": "A" or "B" or "TIE",
    "confidence": "high" or "medium" or "low",
    "scores": {{
        "appropriateness": {{"A": 1-5, "B": 1-5}},
        "effectiveness": {{"A": 1-5, "B": 1-5}},
        "tone_match": {{"A": 1-5, "B": 1-5}},
        "authenticity": {{"A": 1-5, "B": 1-5}}
    }},
    "weaknesses_a": ["..."],
    "weaknesses_b": ["..."]
}}
"""
```

### 5.3 Position Bias Handling

**Simulation Steps:**
1. Judge with Model A in position A, Model B in position B
2. Judge with positions swapped
3. Map positional winners back to actual models
4. Track position agreement

**What Works Well:**
- Explicit position shuffling addresses known bias
- Agreement tracking enables bias detection
- Clean mapping logic

**Issues Identified:**

1. **Cost doubles with position shuffling**: Each comparison requires 2 judge calls per persona per judge model. With 3 judges x 2 personas x 2 positions = 12 judge calls per comparison. This significantly increases cost.

2. **Position disagreement handling unclear**: If a judge picks A when Gemini is first but B when Gemini is second, what happens? The `_position_majority` just picks majority, but with only 2 samples, ties are likely.

3. **Best-of-5 not implemented**: PROMPT.md specifies "Best-of-5 judgments per comparison" but the position shuffle only shows 2 judgments per (judge, persona) combination. Where are the 5 votes?

4. **Shuffle determinism not ensured**: The position assignment should be deterministic based on seed for reproducibility.

**Critical Discrepancy - Vote Count:**
The plan says:
- 3 judges x 5 votes each = 15 total votes
- Then majority of 3 judge majorities

But the implementation shows:
- 3 judges x 2 positions x 2 personas = 12 total judgments
- No "5 votes per judge"

**Clarification Needed:**
```python
# Option A: 5 independent votes per (judge, persona), each with position shuffle
# Cost: 3 judges x 2 personas x 5 votes x 2 positions = 60 API calls per comparison

# Option B: 5 votes come from position x persona combinations
# Cost: 3 judges x 2 positions x 2 personas = 12 API calls per comparison

# Option C (likely intended): Multiple temperature samples per position
# Cost: 3 judges x 2 positions x 5 samples = 30 API calls per comparison
```

### 5.4 Vote Aggregation

**Simulation Steps:**
1. For each judge-persona pair, determine majority across positions
2. Collect all judge-persona majorities
3. Take final majority across all judges and personas
4. Calculate agreement metrics

**What Works Well:**
- Clear aggregation hierarchy
- Agreement metrics at multiple levels
- Confidence calculation based on vote distribution

**Issues Identified:**

1. **Fleiss Kappa implementation incomplete**: The `AgreementMetrics.fleiss_kappa` method is shown but never called in the aggregator. Integration is missing.

2. **Agreement metrics naming confusion**: `inter_judge` and `inter_persona` are booleans (all agree / not all agree) but Kappa should be continuous [0, 1].

3. **TIE handling inconsistent**: Some places treat TIE as a third outcome, others exclude it. Need consistent policy.

4. **Position consistency metric undefined**: `_compute_position_consistency` is referenced but not implemented.

**Suggested Position Consistency:**
```python
def _compute_position_consistency(
    self,
    judge_persona_winners: list[tuple[str, str, str]]
) -> float:
    """Calculate how often judges agree regardless of position."""
    # Group by (judge, persona)
    by_jp = defaultdict(list)
    for judge, persona, winner in judge_persona_winners:
        by_jp[(judge, persona)].append(winner)

    consistent = 0
    total = 0
    for (judge, persona), winners in by_jp.items():
        # Compare AB vs BA orderings
        if len(winners) >= 2:
            total += 1
            if winners[0] == winners[1]:
                consistent += 1

    return consistent / total if total > 0 else 1.0
```

### 5.5 Robust JSON Parsing

**Simulation Steps:**
1. Try direct JSON parse
2. Try extracting from code block
3. Try fixing common issues
4. Try regex extraction
5. Return error indicator on failure

**What Works Well:**
- 4-tier fallback strategy
- Handles code blocks
- Handles common JSON errors (trailing commas, single quotes)
- Regex as last resort

**Issues Identified:**

1. **Missing handling for nested JSON**: If the response contains multiple JSON objects, current logic might fail.

2. **No handling for escaped quotes**: If reasoning contains quotes, the regex extraction will fail on `"reasoning": "He said \"hello\""`.

3. **Confidence fallback missing**: If confidence can't be parsed, it defaults to 'unknown' but this isn't a valid enum value in some places.

4. **No retry with guidance**: If parse fails, could retry asking judge to fix their JSON, but this isn't implemented.

**Enhanced Regex Extraction:**
```python
def _regex_extraction(self, text: str) -> dict:
    result = {'_parse_success': False}

    # Winner extraction (most important)
    winner_patterns = [
        r'"winner"\s*:\s*"([ABab]|[Tt][Ii][Ee])"',
        r'\bwinner\b[^:]*:\s*\*?\*?([ABab]|[Tt][Ii][Ee])\b',  # Handles markdown **A**
        r'\b([AB])\s+is\s+(?:the\s+)?(?:clear\s+)?winner\b',
    ]

    for pattern in winner_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            result['winner'] = match.group(1).upper()
            result['_parse_success'] = True
            break

    # If still no winner, look for sentiment
    if 'winner' not in result:
        if re.search(r'\bResponse A\b.*\bbetter\b|\bprefer.*Response A\b', text, re.I):
            result['winner'] = 'A'
            result['_parse_success'] = True
        elif re.search(r'\bResponse B\b.*\bbetter\b|\bprefer.*Response B\b', text, re.I):
            result['winner'] = 'B'
            result['_parse_success'] = True

    return result
```

---

## Part 6: Analysis Engine Simulation

### 6.1 Statistics Calculation

**Simulation Steps:**
1. Load all aggregated results
2. Calculate win rates per model
3. Calculate confidence intervals (Wilson score)
4. Build head-to-head matrix

**What Works Well:**
- Wilson score interval is correct choice for proportions
- Head-to-head matrix provides clear comparison
- Separates ties from wins/losses

**Issues Identified:**

1. **Missing significance testing**: The plan mentions statistical significance but doesn't show implementation. Need binomial test or chi-square.

2. **Multiple comparison correction**: With many model pairs and dimensions, need Bonferroni or FDR correction.

3. **Effect size not calculated**: Win rate alone doesn't indicate magnitude of difference. Should include Cohen's d or similar.

4. **Confidence interval doesn't account for clustering**: Responses from same model may be correlated. Standard CI assumes independence.

**Suggested Significance Testing:**
```python
def test_significance(
    self,
    wins_a: int,
    wins_b: int,
    ties: int,
    alpha: float = 0.05
) -> SignificanceResult:
    """Test if win rate difference is significant."""
    from scipy import stats

    # Exclude ties for clear comparison
    total = wins_a + wins_b
    if total == 0:
        return SignificanceResult(significant=False, p_value=1.0)

    # Binomial test: is wins_a significantly different from 50%?
    p_value = stats.binom_test(wins_a, total, p=0.5, alternative='two-sided')

    # Effect size (Cohen's h for proportions)
    p_a = wins_a / total
    p_null = 0.5
    import math
    cohens_h = 2 * (math.asin(math.sqrt(p_a)) - math.asin(math.sqrt(p_null)))

    return SignificanceResult(
        significant=p_value < alpha,
        p_value=p_value,
        effect_size=cohens_h,
        effect_interpretation=self._interpret_effect_size(cohens_h)
    )
```

### 6.2 Weakness Analysis

**Simulation Steps:**
1. Filter results to Gemini losses
2. Group by dimensions (category, channel, formality, etc.)
3. Calculate loss rates per dimension value
4. Test for significant patterns
5. Extract reasoning themes from judge feedback

**What Works Well:**
- Multi-dimensional analysis
- Statistical significance filtering
- Theme extraction from reasoning
- Sample prompts for context

**Issues Identified:**

1. **Gemini position tracking missing**: The `WeaknessFinder._extract_reasoning_themes` references `loss.gemini_position` but `AggregatedResult` doesn't have this field.

2. **Relative risk calculation assumes independent samples**: But same prompts evaluated across multiple dimensions create dependency.

3. **Theme extraction is naive string matching**: The `Counter(all_weaknesses)` just counts exact strings. "Too long" and "Response was too lengthy" would be separate themes.

4. **Missing confidence intervals on loss rates**: Just showing loss_rate without CI can be misleading.

5. **No multi-variate analysis**: A weakness might only appear when formality=high AND job_zone=5. Current analysis only does univariate.

**Enhanced Theme Extraction:**
```python
async def _extract_reasoning_themes(
    self,
    losses: list[AggregatedResult],
    llm_client: LLMClient
) -> list[ReasoningTheme]:
    """Use LLM to cluster and summarize weakness themes."""
    all_weaknesses = []
    for loss in losses:
        for judgment in loss.raw_judgments:
            gemini_weaknesses = (
                judgment.weaknesses_a if loss.gemini_was_a else judgment.weaknesses_b
            )
            all_weaknesses.extend(gemini_weaknesses)

    if len(all_weaknesses) < 10:
        return [ReasoningTheme(theme=w, count=1, frequency=1/len(all_weaknesses))
                for w in all_weaknesses]

    # Use LLM to cluster similar weaknesses
    cluster_prompt = f"""
Analyze these critique points about an AI model's writing and group them into 5-10 themes:

{json.dumps(all_weaknesses[:200], indent=2)}

Return as JSON:
{{
    "themes": [
        {{"name": "Theme Name", "description": "...", "examples": ["...", "..."], "count": N}},
        ...
    ]
}}
"""

    response = await llm_client.generate(cluster_prompt, model="smart_cheap")
    themes = self._parse_themes(response)
    return themes
```

### 6.3 Bias Detection

**Simulation Steps:**
1. Calculate position A vs B win rates
2. Calculate longer-response win rate
3. Test for judge self-preference
4. Report all detected biases

**What Works Well:**
- Multiple bias types checked
- Statistical testing for each
- Clear recommendations when bias detected

**Issues Identified:**

1. **`binom_test` is deprecated**: scipy.stats.binom_test deprecated in favor of scipy.stats.binomtest (note the slight name change).

2. **Length bias correlation is wrong**: The code computes Pearson correlation between binary outcome and length differences, but the lists aren't aligned correctly (different filtering).

3. **Self-preference detection requires model-to-provider mapping**: `judge_model_mapping` must be provided but source isn't specified.

4. **Missing statistical power check**: With small sample sizes, bias tests may have low power. Should report if sample too small.

**Fixed Length Bias Detection:**
```python
def detect_length_bias(
    self,
    results: list[AggregatedResult],
    responses: dict[str, dict[str, ModelResponse]]
) -> LengthBiasReport:
    """Detect if longer responses tend to win."""
    winner_lengths = []
    loser_lengths = []

    for result in results:
        if result.winner == "TIE":
            continue

        prompt_responses = responses.get(result.prompt_id, {})
        resp_a = prompt_responses.get(result.model_a)
        resp_b = prompt_responses.get(result.model_b)

        if not resp_a or not resp_b:
            continue

        len_a = len(resp_a.response_text or '')
        len_b = len(resp_b.response_text or '')

        if result.winner == result.model_a:
            winner_lengths.append(len_a)
            loser_lengths.append(len_b)
        else:
            winner_lengths.append(len_b)
            loser_lengths.append(len_a)

    if len(winner_lengths) < 30:
        return LengthBiasReport(
            bias_detected=False,
            note="Sample size too small for reliable analysis"
        )

    # Paired t-test: are winners significantly longer?
    from scipy import stats
    t_stat, p_value = stats.ttest_rel(winner_lengths, loser_lengths)

    avg_winner = sum(winner_lengths) / len(winner_lengths)
    avg_loser = sum(loser_lengths) / len(loser_lengths)

    return LengthBiasReport(
        avg_winner_length=avg_winner,
        avg_loser_length=avg_loser,
        length_difference=avg_winner - avg_loser,
        bias_detected=p_value < 0.05 and (avg_winner - avg_loser) > 50,
        p_value=p_value,
        recommendation=(
            f"Winners average {avg_winner - avg_loser:.0f} chars longer"
            if p_value < 0.05 else None
        )
    )
```

---

## Part 7: TUI and Reporting Simulation

### 7.1 Progress Dashboard

**Simulation Steps:**
1. Create textual App with layout
2. Add progress bars and stats panels
3. Implement periodic refresh
4. Handle keyboard input

**What Works Well:**
- Comprehensive layout design
- Reactive state management
- Keyboard shortcuts documented
- Real-time updates

**Issues Identified:**

1. **Textual API may have changed**: The plan shows `update_progress(value, total)` but textual's ProgressBar might use different API.

2. **Missing eval_state reference**: `self.eval_state` is accessed in `refresh_data` but never set.

3. **Thread safety concerns**: If evaluation runs in separate thread, reactive updates may race.

4. **Error state display missing**: How does the TUI show API errors, parse failures, etc.?

5. **Memory leak potential**: Continuous logging without cleanup could grow activity log unbounded.

**Suggested Fixes:**
```python
class EvalTUI(App):
    def __init__(self, eval_state_provider: Callable[[], EvalState]):
        super().__init__()
        self._get_eval_state = eval_state_provider

    async def refresh_data(self) -> None:
        try:
            state = self._get_eval_state()
            if state:
                self.prompts_completed = state.completed_count
                # ... rest of update
        except Exception as e:
            self.log_error(f"Refresh failed: {e}")

    @work
    async def run_evaluation(self, orchestrator: EvalOrchestrator):
        """Run evaluation in background worker."""
        try:
            await orchestrator.run()
        except Exception as e:
            self.notify(f"Evaluation failed: {e}", severity="error")
```

### 7.2 PDF Report Generation

**Simulation Steps:**
1. Load Jinja2 template
2. Render HTML with data
3. Convert HTML to PDF with WeasyPrint
4. Generate charts as base64 images

**What Works Well:**
- Template-based report generation
- Plotly for charts
- Base64 embedding for portability

**Issues Identified:**

1. **Templates not provided**: The plan references `templates/comprehensive_report.html` but doesn't include template content.

2. **WeasyPrint CSS limitations**: WeasyPrint has limited CSS support. Complex layouts may not render correctly.

3. **Chart resolution**: Plotly `to_image` defaults may produce low-resolution charts. Need explicit DPI setting.

4. **Large report memory issues**: With many charts and comparisons, report generation could exhaust memory.

5. **Missing async handling**: `HTML(...).write_pdf()` is blocking. Should run in executor for long reports.

**Suggested Chart Generation:**
```python
def _create_chart(self, fig: go.Figure, width: int = 800, height: int = 400) -> str:
    """Create high-resolution chart as base64."""
    import io
    import base64

    # Use kaleido for static export (more reliable than orca)
    img_bytes = fig.to_image(
        format='png',
        width=width,
        height=height,
        scale=2,  # 2x resolution for crisp printing
    )

    return base64.b64encode(img_bytes).decode('utf-8')

async def generate_report(self, ...) -> Path:
    # Run blocking operations in executor
    import asyncio

    def _render_pdf():
        html_content = template.render(**context)
        HTML(string=html_content, base_url=str(self.template_dir)).write_pdf(output_path)

    await asyncio.get_event_loop().run_in_executor(None, _render_pdf)
    return output_path
```

---

## Part 8: Data Storage and Checkpointing Simulation

### 8.1 SQLite Database

**Simulation Steps:**
1. Create database with WAL mode
2. Create all tables
3. Implement CRUD operations
4. Enable concurrent access

**What Works Well:**
- SQLite is appropriate for single-machine use
- WAL mode enables concurrent reads
- aiosqlite for async access

**Issues Identified:**

1. **Schema not defined**: The plan mentions `results.db` but no table definitions (CREATE TABLE statements).

2. **Migration strategy missing**: How to handle schema changes between versions?

3. **Index definitions missing**: For large datasets, queries will be slow without proper indexes.

4. **Foreign key enforcement**: SQLite doesn't enforce FKs by default. Need `PRAGMA foreign_keys = ON`.

**Suggested Schema:**
```sql
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Prompts
CREATE TABLE prompts (
    id TEXT PRIMARY KEY,
    prompt_text TEXT NOT NULL,
    task_id TEXT NOT NULL,
    occupation_code TEXT,
    occupation_title TEXT,
    industry TEXT,
    formality TEXT,
    urgency TEXT,
    job_zone INTEGER,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prompts_occupation ON prompts(occupation_code);
CREATE INDEX idx_prompts_industry ON prompts(industry);

-- Responses
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    model_id TEXT NOT NULL,
    response_text TEXT,
    error TEXT,
    status TEXT NOT NULL,
    latency_ms REAL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_id)
);

CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model_id);

-- Judgments
CREATE TABLE judgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    persona_type TEXT NOT NULL,
    position_order TEXT NOT NULL,  -- 'AB' or 'BA'
    winner TEXT NOT NULL,
    confidence TEXT,
    reasoning TEXT,
    raw_response TEXT,
    parse_success INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_judgments_prompt ON judgments(prompt_id);
CREATE INDEX idx_judgments_models ON judgments(model_a, model_b);

-- Aggregated Results
CREATE TABLE aggregated_results (
    prompt_id TEXT PRIMARY KEY REFERENCES prompts(id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    winner TEXT NOT NULL,
    votes_a INTEGER,
    votes_b INTEGER,
    votes_tie INTEGER,
    agreement_score REAL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Checkpoints
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase TEXT NOT NULL,
    state JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2 Checkpoint System

**Simulation Steps:**
1. Serialize evaluation state to JSON
2. Write to temp file
3. Atomic rename
4. Also write to database

**What Works Well:**
- Atomic file operations prevent corruption
- Dual storage (file + DB) for redundancy
- Versioned checkpoint format
- Clear state structure

**Issues Identified:**

1. **Checkpoint size could be large**: With thousands of prompts, storing all IDs as lists could create multi-MB checkpoint files. Should use sets or bitmaps.

2. **`aiofiles` import missing**: The plan shows `async with aiofiles.open(...)` but `aiofiles` isn't in dependencies.

3. **Checkpoint frequency not specified**: How often to checkpoint? After every prompt? Every 10? Too frequent = slow, too rare = lost progress.

4. **Checkpoint validation missing**: When loading, should verify checkpoint integrity (version, required fields).

5. **Orphaned temp files**: If crash happens after temp write but before rename, temp file remains. Need cleanup logic.

**Suggested Improvements:**
```python
class CheckpointManager:
    CHECKPOINT_FREQUENCY = 10  # Checkpoint every N prompts

    def __init__(self, run_dir: Path, db: Database):
        self.run_dir = run_dir
        self.db = db
        self.checkpoint_file = run_dir / "checkpoint.json"
        self.temp_file = run_dir / "checkpoint.json.tmp"
        self._pending_count = 0

    async def maybe_checkpoint(self, state: EvalState, force: bool = False) -> None:
        """Checkpoint if enough progress made or forced."""
        self._pending_count += 1
        if force or self._pending_count >= self.CHECKPOINT_FREQUENCY:
            await self.save_checkpoint(state)
            self._pending_count = 0

    async def save_checkpoint(self, state: EvalState) -> None:
        # Use compact representation
        checkpoint_data = {
            "version": 2,
            "timestamp": datetime.utcnow().isoformat(),
            "phase": state.current_phase,
            "completed_count": len(state.completed_prompts),
            "completed_prompt_ids": sorted(state.completed_prompts),  # Sorted for diffability
            "pending_count": len(state.pending_prompts),
            # Don't store pending IDs - can reconstruct from total - completed
        }

        # Atomic write
        async with aiofiles.open(self.temp_file, 'w') as f:
            await f.write(json.dumps(checkpoint_data))

        # Sync to ensure durability
        os.fsync(f.fileno())

        # Atomic rename
        self.temp_file.rename(self.checkpoint_file)

        # Cleanup any old temp files
        for f in self.run_dir.glob("checkpoint.json.tmp*"):
            f.unlink(missing_ok=True)

    async def load_checkpoint(self) -> EvalState | None:
        if not self.checkpoint_file.exists():
            return None

        async with aiofiles.open(self.checkpoint_file) as f:
            data = json.loads(await f.read())

        # Validate
        if data.get("version") not in [1, 2]:
            raise CheckpointVersionError(f"Unknown version: {data.get('version')}")

        return self._checkpoint_to_state(data)
```

---

## Part 9: Cost Estimation and Budget Control

### 9.1 Cost Estimation

**What Works Well:**
- Presets include cost estimates
- Live cost display during evaluation

**Issues Identified:**

1. **Static pricing in presets**: Prices change frequently. Should query OpenRouter for current prices.

2. **Token estimation not implemented**: Need to estimate prompt + response tokens to calculate cost.

3. **Judge call costs underestimated**: With position shuffling and dual personas, judge costs are 4-8x a single call.

4. **Cost tracking during run missing implementation**: The TUI shows "Est. cost so far" but no code tracks actual spend.

**Suggested Cost Estimator:**
```python
class CostEstimator:
    def __init__(self, model_registry: ModelRegistry):
        self.model_registry = model_registry

    def estimate_run_cost(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost before running."""
        # Response generation cost
        response_cost = 0.0
        for tier, models in [("pro", config.pro_models), ("flash", config.flash_models)]:
            for model_id in models:
                pricing = self.model_registry.get_pricing(model_id)
                # Estimate ~500 input tokens, ~1000 output tokens per response
                per_response = (500 * pricing.prompt + 1000 * pricing.completion) / 1_000_000
                response_cost += per_response * config.num_prompts

        # Judge cost
        judge_calls_per_comparison = (
            len(config.judge_models) *  # 3 judges
            2 *  # 2 positions
            2 *  # 2 personas
            config.votes_per_judge  # 5 votes
        )
        # But if votes_per_judge means 5 total not per-position... need clarification

        judge_cost = 0.0
        for judge_model in config.judge_models:
            pricing = self.model_registry.get_pricing(judge_model)
            # Judge prompts are longer: ~2000 input (prompt + 2 responses), ~200 output
            per_call = (2000 * pricing.prompt + 200 * pricing.completion) / 1_000_000
            judge_cost += per_call * config.num_prompts * judge_calls_per_comparison

        # Prompt enrichment cost (Phase 3)
        enrichment_cost = 0.0
        if config.enable_enrichment:
            # Use cheaper model for enrichment
            pricing = self.model_registry.get_pricing("anthropic/claude-3-haiku")
            per_enrichment = (300 * pricing.prompt + 500 * pricing.completion) / 1_000_000
            enrichment_cost = per_enrichment * config.num_prompts

        return CostEstimate(
            response_generation=response_cost,
            judging=judge_cost,
            enrichment=enrichment_cost,
            total=response_cost + judge_cost + enrichment_cost,
            breakdown={
                "response_per_prompt": response_cost / config.num_prompts,
                "judge_per_comparison": judge_cost / config.num_prompts,
            }
        )

    async def track_actual_cost(self, response: GenerateResponse, model_id: str) -> float:
        """Track actual cost from response usage."""
        pricing = self.model_registry.get_pricing(model_id)
        return (
            response.usage.prompt_tokens * pricing.prompt +
            response.usage.completion_tokens * pricing.completion
        ) / 1_000_000
```

---

## Part 10: Critical Missing Pieces Summary

### 10.1 Missing Implementations

| Component | Status | Impact |
|-----------|--------|--------|
| LLMClient interface | Not defined | Blocks all LLM calls |
| Model ID verification | Speculative IDs | May fail at runtime |
| BLS Matrix parser | Not implemented | Falls back to manual mapping |
| companies.json | Not provided | Needs to be created/populated |
| Report templates | Not provided | PDF generation fails |
| Database schema | Not defined | Storage broken |
| Test suite | Not implemented | No validation |

### 10.2 Ambiguous Requirements

1. **Best-of-5 voting**: Does this mean 5 independent judge calls, or 5 samples from temperature variation, or 5 from position/persona combinations?

2. **Position shuffling cost**: Is doubling judge calls acceptable, or should it be configurable?

3. **Tier comparisons**: Is it always Gemini vs 1 competitor, or Gemini vs all competitors simultaneously?

4. **Response constraints**: PROMPT.md says "no constraints" but also mentions length tiers. Reconcile.

### 10.3 Technical Blockers

1. **WeasyPrint system dependencies** - Users need to install system libraries
2. **Model availability** - Future models (Gemini 3.0, GPT-5.2) don't exist yet
3. **Rate limits unknown** - OpenRouter limits not documented in plan
4. **Memory usage** - Large evaluations could exhaust memory

### 10.4 Recommended Implementation Order

1. **Week 1**: Foundation
   - Project structure with all `__init__.py`
   - Pydantic models (schemas)
   - Settings management
   - SQLite schema and migrations

2. **Week 2**: Data Layer
   - O*NET validation and extraction
   - Generate companies.json
   - Name generator

3. **Week 3**: API Layer
   - OpenRouter client
   - Rate limiter
   - Circuit breaker
   - Model verifier (with current model IDs)

4. **Week 4**: Prompt Generation
   - Phase 2 algorithmic combiner (most important)
   - Phase 3 enricher
   - Skip Phase 1 personas initially (use hardcoded diverse set)

5. **Week 5**: Evaluation Core
   - Response collector
   - Basic judge (single persona first)
   - Simple aggregation (majority vote)

6. **Week 6**: Full Judging
   - Dual persona
   - Position shuffling
   - Full aggregation

7. **Week 7**: Analysis
   - Win rates and CIs
   - Basic weakness analysis
   - Bias detection

8. **Week 8**: Output
   - TUI progress (simplified)
   - CSV export
   - Basic PDF report

---

## Conclusion

The master plan is comprehensive and well-thought-out but has several implementation gaps that need to be addressed before coding begins:

1. **External dependencies need verification**: OpenRouter model IDs, BLS matrix format, actual API endpoints
2. **Data assets need creation**: companies.json, report templates
3. **Interfaces need definition**: LLMClient, Database methods
4. **Ambiguities need resolution**: voting semantics, cost implications of design choices
5. **Testing strategy needed**: The plan has no test coverage specification

With these issues addressed, the plan provides a solid foundation for building a robust writing evaluation framework. The key is to start with a minimal viable implementation (simpler judging, fewer dimensions) and incrementally add complexity once the core pipeline works end-to-end.
