# Implementation Simulation Report - Simulation 2

## Executive Summary

This document presents a detailed dry-run simulation of implementing the Gemini Writing Evaluation Framework as specified in the master plan. The simulation walks through each component as if coding it, identifying issues, gaps, and improvements needed before actual implementation begins.

---

## Phase 1: Project Setup and Foundation

### 1.1 Directory Structure Creation

**Simulation Steps:**
```bash
mkdir -p gemini-writing-eval/src/{config,validation,data,prompts,eval,api,storage,analysis,reports,tui}
mkdir -p gemini-writing-eval/{db,data,results,tests}
touch gemini-writing-eval/pyproject.toml
```

**Issues Identified:**

1. **Missing `__init__.py` files**: The plan shows directory structure but implementation would need `__init__.py` in every package directory for proper imports.

2. **Results directory gitignore**: The `results/` directory should be gitignored but the plan doesn't include a `.gitignore` template.

3. **Log directory missing**: No `logs/` directory at project root for application logs separate from run-specific logs.

**Gotcha:** Python 3.11+ requirement may cause issues on some systems. Should document `pyenv` or `conda` setup instructions.

---

### 1.2 Dependency Installation

**Simulation:**
```bash
pip install -e ".[dev]"
```

**Issues Identified:**

1. **WeasyPrint system dependencies**: WeasyPrint requires system-level dependencies (Cairo, Pango, GDK-PixBuf) that aren't mentioned. On macOS:
   ```bash
   brew install cairo pango gdk-pixbuf libffi
   ```
   On Ubuntu:
   ```bash
   apt-get install libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0
   ```
   **This is a significant blocker for first-time users.**

2. **Kaleido architecture issues**: Kaleido has known issues on Apple Silicon. May need:
   ```bash
   pip install kaleido==0.1.0.post1
   ```

3. **aiofiles missing from dependencies**: The checkpoint code uses `aiofiles` but it's not in `pyproject.toml`.

4. **Missing dependencies detected:**
   - `aiofiles` - for async file operations
   - `ujson` or `orjson` - for faster JSON parsing (mentioned as performance concern)
   - `click` - typer dependency but should be explicit

**Recommendation:** Add a `requirements-system.txt` documenting system-level dependencies with installation commands for different OSes.

---

### 1.3 Pydantic Schema Implementation

**Simulation of ONetTask model:**

```python
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
```

**Issues Identified:**

1. **Missing field validators**: No validation that `job_zone` is 1-5, `writing_relevance_score` is 0-1.

2. **Missing task_type field**: ONET_REFERENCE.md mentions `task_type` can be 'Core', 'Supplemental', or NULL but the schema doesn't include it.

3. **SOC code validation**: `soc_major_group` should be validated as 2-digit string.

4. **Missing occupation_description**: Useful for context enrichment but not in schema.

**Improved schema:**
```python
class ONetTask(BaseModel):
    task_id: str
    onetsoc_code: str = Field(..., pattern=r"^\d{2}-\d{4}\.\d{2}$")
    task: str
    task_type: Literal["Core", "Supplemental", None] = None
    occupation_title: str
    occupation_description: str | None = None
    job_zone: int = Field(..., ge=1, le=5)
    soc_major_group: str = Field(..., pattern=r"^\d{2}$")
    writing_relevance_score: float = Field(..., ge=0.0, le=1.0)
    inferred_category: str
    inferred_channel: str
```

---

## Phase 2: O*NET Data Pipeline

### 2.1 Schema Validation

**Simulation of running schema validator:**

```python
validator = ONetSchemaValidator()
result = await validator.validate(Path("db/onet.db"))
```

**Issues Identified:**

1. **Table names don't match**: The plan assumes `task_statements` and `occupation_data` tables. Need to verify actual O*NET 30.1 table names. From ONET_REFERENCE.md, the tables appear to be:
   - `task_statements` - confirmed
   - `occupation_data` - confirmed
   - `job_zones` - confirmed
   - `work_context` - confirmed
   - `skills` - confirmed

2. **Missing element verification**: The plan checks for element IDs like `2.A.1.c` (Writing Skill) but doesn't verify the `content_model_reference` table exists to look up element names.

3. **Scale ID confusion**: The plan uses `scale_id = 'IM'` for importance and `scale_id = 'CX'` for context, but doesn't verify these scale codes exist in the database.

**Recommended pre-flight query:**
```sql
SELECT DISTINCT scale_id FROM skills;
SELECT DISTINCT scale_id FROM work_context;
```

4. **Database path hardcoded**: The plan references `db/onet.db` but should be configurable via environment variable or CLI argument.

---

### 2.2 Task Extraction

**Simulation of extraction query:**

```sql
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
-- ... rest of joins
```

**Issues Identified:**

1. **Ambiguous column name**: If `occupation_data` has a `description` column, it may conflict. Should use table prefix: `o.description`.

2. **Missing task_type**: The query doesn't select `task_type` which is useful for filtering Core vs Supplemental tasks.

3. **COALESCE default values questionable**: Using 2.5 as default for missing skill scores assumes middle-of-scale, but this may not be appropriate. Tasks with missing writing skill data might be entirely non-writing tasks.

4. **Memory concerns**: Loading all 18,796 tasks into memory at once. Should use cursor iteration or batching for large datasets:
```python
async for row in cursor:
    # process row
```

5. **Index performance**: No mention of database indexes. For repeated queries, should verify indexes exist on:
   - `task_statements.onetsoc_code`
   - `skills.onetsoc_code, skills.element_id, skills.scale_id`
   - `work_context.onetsoc_code, work_context.element_id, work_context.scale_id`

---

### 2.3 Writing Relevance Scoring

**Simulation of `_compute_writing_relevance`:**

```python
def _compute_writing_relevance(self, row: dict) -> float:
    task_lower = row['task'].lower()
    max_pattern_score = 0.0

    for pattern, weight in self.WRITING_INDICATORS:
        if re.search(pattern, task_lower):
            max_pattern_score = max(max_pattern_score, weight)

    onet_score = (
        row.get('writing_skill', 2.5) * 0.4 +
        row.get('email_freq', 2.5) * 0.3 +
        row.get('letter_freq', 2.5) * 0.3
    ) / 5.0

    return max(max_pattern_score, onet_score)
```

**Issues Identified:**

1. **Pattern matching is naive**: Using `max()` of pattern scores means a task matching "write" (1.0) and "communicate" (0.6) only gets 1.0, losing the signal that it matches multiple indicators.

2. **Scale normalization error**: O*NET skills are on 1-5 scale, but dividing by 5.0 gives a max of 1.0 only if all values are 5.0. A score of (5*0.4 + 5*0.3 + 5*0.3)/5.0 = 1.0, but (3*0.4 + 3*0.3 + 3*0.3)/5.0 = 0.6. This seems intentional but should be documented.

3. **No caching of regex compilation**: `re.search(pattern, ...)` recompiles regex each time. Should pre-compile:
```python
WRITING_INDICATORS = [
    (re.compile(r'\bwrite\b'), 1.0),
    ...
]
```

4. **Missing edge case handling**: What if `row['task']` is None or empty string?

---

### 2.4 NAICS Industry Mapping

**Simulation:**

The plan mentions using BLS Occupation-Industry Matrix but doesn't provide:
1. URL to download the data
2. File format specification
3. Parsing code

**Critical Issue:** The `NAICSMapper` constructor takes `bls_matrix_path` but:
- No code to download/update the BLS data
- No schema for what the BLS matrix file looks like
- No fallback data file provided

From ONET_REFERENCE.md:
> "IMPORTANT: O*NET does not contain NAICS industry codes directly."

**Required Implementation:**
1. Add BLS data download script
2. Define BLS matrix parsing format
3. Include pre-processed crosswalk in `data/naics_soc_crosswalk.json`

**Gotcha:** BLS data format changes periodically. Should version the crosswalk data.

---

## Phase 3: Prompt Generation Pipeline

### 3.1 Phase 1 - Persona Generation

**Simulation of LLM call:**

```python
response = await llm_client.generate(
    self.PERSONA_GENERATION_PROMPT.format(count=count),
    model="smart_cheap"
)
```

**Issues Identified:**

1. **"smart_cheap" is undefined**: The plan uses semantic model names like "smart_cheap" but doesn't define the mapping to actual OpenRouter model IDs.

2. **JSON parsing from LLM**: The code assumes LLM returns valid JSON. Needs robust parsing with fallback:
```python
def _parse_personas(self, response: str) -> list[Persona]:
    # Try direct JSON parse
    # Try extracting from code block
    # Try line-by-line extraction
    # Raise with helpful error
```

3. **Token limit concerns**: Generating 100+ personas in one call may exceed context limits. Should batch:
```python
async def generate_personas(self, count: int, ...):
    batch_size = 20  # Safe batch size
    all_personas = []
    for i in range(0, count, batch_size):
        batch = await self._generate_persona_batch(batch_size, ...)
        all_personas.extend(batch)
    return all_personas
```

4. **Persona diversity not validated**: No check that generated personas actually span desired diversity dimensions.

5. **Cache invalidation**: If persona requirements change, cached personas become stale. Need versioned cache keys.

---

### 3.2 Phase 2 - Algorithmic Combination

**Simulation of stratified sampling:**

```python
def _stratified_sample(
    self,
    combinations: list[dict],
    count: int,
    rng: random.Random,
    dimensions: list[str]
) -> list[dict]:
    strata = defaultdict(list)
    for combo in combinations:
        key = tuple(combo.get(d, "unknown") for d in dimensions)
        strata[key].append(combo)
```

**Issues Identified:**

1. **Combinatorial explosion**: With 8 dimensions, even 3 values per dimension = 3^8 = 6,561 strata. Many will be empty or have very few items.

2. **Empty strata handling**: Code handles empty strata by filling from largest, but this skews distribution.

3. **Dimension priority**: All dimensions treated equally, but some (job_zone, soc_major_group) should have higher priority for even distribution.

**Improved approach:**
```python
def _hierarchical_stratified_sample(
    self,
    combinations: list[dict],
    count: int,
    rng: random.Random,
    primary_dimensions: list[str],  # Must be evenly distributed
    secondary_dimensions: list[str]  # Best effort
) -> list[dict]:
    # First stratify on primary dimensions
    # Then within each stratum, diversify on secondary
```

4. **Missing generation of all combinations**: `_generate_all_combinations()` is referenced but not implemented. This would be a cartesian product of tasks x personas x scenario_seeds - potentially huge.

**Memory concern:** 18,796 tasks x 100 personas x 100 scenarios = 188 billion combinations. Cannot materialize in memory.

**Solution:** Generate combinations on-demand with sampling:
```python
def _sample_combination(self, rng: random.Random) -> dict:
    task = rng.choice(self.tasks)
    persona = rng.choice(self.personas)
    scenario = rng.choice(self.scenario_seeds)
    return {"task": task, "persona": persona, "scenario_seed": scenario, ...}
```

---

### 3.3 Phase 3 - LLM Enrichment

**Simulation of enrichment:**

```python
filled_prompt = self.ENRICHMENT_PROMPT.format(
    persona=base_prompt.persona,
    company=base_prompt.company,
    ...
)
```

**Issues Identified:**

1. **Object formatting**: `.format()` with Pydantic objects will use `__str__` representation, not structured data. Need:
```python
filled_prompt = self.ENRICHMENT_PROMPT.format(
    persona_job_title=base_prompt.persona.job_title,
    persona_style=base_prompt.persona.communication_style,
    company_name=base_prompt.company.name,
    ...
)
```

2. **Context length**: The enrichment prompt with all fields could be 2000+ tokens. Plus LLM response. May hit context limits on cheaper models.

3. **Enrichment quality validation**: No check that enriched prompts meet quality criteria:
   - Has realistic specifics (not "[PLACEHOLDER]")
   - Has appropriate length
   - Matches persona formality

4. **Rate limiting for batch enrichment**: `enrich_batch` uses semaphore but no rate limiting for API calls per second:
```python
async def enrich_with_semaphore(prompt: BasePrompt) -> EnrichedPrompt:
    async with semaphore:
        await self.rate_limiter.acquire()  # Missing!
        enriched = await self.enrich_prompt(prompt, llm_client)
```

5. **Error handling in gather**: Using `return_exceptions=True` but then filtering without logging individual failures:
```python
for r in results:
    if isinstance(r, Exception):
        logger.error(f"Enrichment failed: {r}")  # Loses prompt context
```
Should log which prompt failed.

---

## Phase 4: API Layer

### 4.1 OpenRouter Client

**Simulation of model verification:**

```python
response = await client.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {api_key}"}
)
```

**Issues Identified:**

1. **API endpoint verification needed**: The OpenRouter models endpoint should be verified. Current endpoint appears correct but may change.

2. **Model ID format uncertainty**: The plan uses IDs like "google/gemini-3.0-pro" but actual OpenRouter IDs may differ:
   - Actual format might be: "google/gemini-1.5-pro-latest"
   - Need to verify current model names via API

3. **Missing authentication test**: Should verify API key has sufficient credits before starting evaluation.

4. **Pricing data**: OpenRouter returns pricing in the models endpoint. Should capture for cost estimation:
```python
available = {
    m["id"]: {
        "pricing": m.get("pricing", {}),
        "context_length": m.get("context_length", 0)
    }
    for m in response.json()["data"]
}
```

---

### 4.2 Rate Limiter

**Issue:** No rate limiter implementation provided in the plan.

**Required implementation:**
```python
class TokenBucketRateLimiter:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
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
```

**Per-model rate limits needed:** Different models may have different rate limits.

---

### 4.3 Response Collection

**Simulation:**

```python
async def _collect_single(self, prompt, model_id, checkpoint_callback):
    if not self.circuit_breaker.allow_request(model_id):
        raise CircuitBreakerOpen(f"Circuit open for {model_id}")

    await self.rate_limiter.acquire(model_id)

    start = time.perf_counter()
    response = await self.api_client.generate(
        prompt=prompt.prompt_text,
        model=model_id,
        max_tokens=self._estimate_max_tokens(prompt),
        temperature=0.7
    )
```

**Issues Identified:**

1. **`_estimate_max_tokens` not implemented**: Need heuristic based on prompt type:
```python
def _estimate_max_tokens(self, prompt: EnrichedPrompt) -> int:
    base = 500
    if prompt.word_count_tier == "short":
        return 300
    elif prompt.word_count_tier == "long":
        return 1500
    return base
```

2. **Timeout handling missing**: No timeout on API call. Could hang forever:
```python
response = await asyncio.wait_for(
    self.api_client.generate(...),
    timeout=120.0  # 2 minute timeout
)
```

3. **Response validation missing**: Need to check response isn't empty, truncated, or obviously malformed.

4. **Token count access**: `response.usage.total_tokens` assumes OpenRouter response format. May vary by model.

---

## Phase 5: Evaluation Engine

### 5.1 Dual-Persona Judging

**Simulation of judge call:**

```python
comparison_prompt = self.COMPARISON_PROMPT.format(
    prompt_text=prompt.prompt_text,
    response_a=response_a,
    response_b=response_b
)
```

**Issues Identified:**

1. **Missing judge context**: PROMPT.md specifies judges need full context:
   - Writer persona details
   - Target recipient persona
   - Formality level
   - Communication context

   The current `COMPARISON_PROMPT` only includes `prompt_text`, losing this context.

2. **Prompt length explosion**: With two full responses embedded, prompt could be 8000+ tokens. Some judge models may truncate.

3. **Response sanitization**: What if response_a or response_b contains the string "RESPONSE B:" ? Could confuse the judge. Need delimiters:
```python
response_a_safe = response_a.replace("RESPONSE", "RESP0NSE")  # Or use XML tags
```

4. **Missing evaluation criteria**: PROMPT.md lists specific criteria:
   - Authenticity / "Human-like" quality
   - Cliche/boilerplate avoidance
   - Length appropriateness

   These aren't in the judge prompt.

**Improved prompt:**
```
You are comparing two responses. Consider:
1. Quality of writing (clarity, organization, grammar)
2. Appropriate tone for the context: {formality}
3. Effectiveness for the recipient: {recipient_role}
4. Authenticity - does it sound human or AI-generated?
5. Appropriate length for a {expected_format}
6. Avoidance of cliches ("I hope this email finds you well", etc.)

WRITER CONTEXT:
{persona_details}

RECIPIENT CONTEXT:
{recipient_details}
...
```

---

### 5.2 Position Bias Handling

**Simulation:**

```python
# Order 1: A first, B second
expert_ab, recipient_ab = await judge.judge_comparison(
    prompt, responses[model_a], responses[model_b], judge_model, api_client
)

# Order 2: B first, A second
expert_ba, recipient_ba = await judge.judge_comparison(
    prompt, responses[model_b], responses[model_a], judge_model, api_client
)
```

**Issues Identified:**

1. **Double API cost**: Every comparison now requires 4 judge calls (2 personas x 2 orderings) instead of 2. With best-of-5, that's 20 calls per comparison per judge model.

   With 3 judge models: 60 judge calls per prompt comparison.
   With 500 prompts and 4 model pairs: 120,000 judge calls.

   **This significantly increases cost estimates.**

2. **Statistical power vs cost tradeoff**: The plan should offer configurable position shuffling:
   - `shuffle_mode="none"` - no shuffling (2 calls)
   - `shuffle_mode="single"` - one random ordering (2 calls)
   - `shuffle_mode="both"` - both orderings (4 calls)

3. **Missing deterministic shuffle**: For reproducibility, shuffle should use seeded RNG:
```python
def _deterministic_order(self, prompt_id: str, model_a: str, model_b: str, seed: int) -> tuple[str, str]:
    rng = random.Random(f"{seed}_{prompt_id}_{model_a}_{model_b}")
    models = [model_a, model_b]
    rng.shuffle(models)
    return tuple(models)
```

---

### 5.3 Vote Aggregation

**Simulation:**

```python
def aggregate_comparison(self, shuffled_judgments, model_a, model_b):
    judge_persona_winners = []

    for sj in shuffled_judgments:
        expert_winners = [sj.judgments['expert_ab'], sj.judgments['expert_ba']]
        expert_winner = self._position_majority(expert_winners, model_a, model_b)
```

**Issues Identified:**

1. **Majority of 2 gives TIE frequently**: With only 2 position orderings, disagreement always yields TIE. Should track as "inconsistent" rather than "TIE".

2. **Best-of-5 not implemented**: The plan mentions "best-of-5 judgments" but the code only shows 2 judgments per persona (one per position). Where are the 5 votes?

   **Missing implementation:**
   ```python
   async def judge_with_multiple_votes(
       self, prompt, responses, judge_model, api_client, num_votes: int = 5
   ):
       votes = []
       for i in range(num_votes):
           result = await judge.judge_comparison(
               prompt, responses[model_a], responses[model_b],
               judge_model, api_client,
               temperature=0.5  # Allow variation
           )
           votes.append(result)
       return self._majority_vote(votes)
   ```

3. **TIE handling ambiguity**: A position majority of [A, B] gives TIE. But a position majority of [A, TIE] should give A. Current code doesn't handle this.

---

### 5.4 JSON Parsing Robustness

**Simulation of `_regex_extraction`:**

```python
winner_match = re.search(r'"?winner"?\s*:\s*"?([ABab]|TIE|tie)"?', text, re.I)
```

**Issues Identified:**

1. **Doesn't handle model names in winner field**: Judge might return `"winner": "gemini-pro"` instead of `"winner": "A"`. Need to map.

2. **Case sensitivity**: Pattern allows 'a', 'b', 'TIE', 'tie' but not 'Tie'. Should add.

3. **Missing whitespace handling**: `"winner" : "A"` with extra spaces before colon won't match.

4. **JSON5 not supported**: LLMs sometimes output JSON5 (trailing commas, single quotes). The regex fixes some but not all.

**Improved regex:**
```python
winner_match = re.search(
    r'"?winner"?\s*:\s*["\'']?([ABab]|tie|Tie|TIE|model_?[ab]|response_?[ab])["\'']?',
    text,
    re.I
)
```

---

## Phase 6: Analysis and Reporting

### 6.1 Statistics Engine

**Simulation of Wilson score interval:**

```python
def _wilson_score_interval(self, successes, total, confidence=0.95):
    from scipy import stats
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / total

    denominator = 1 + z**2 / total
    center = (p_hat + z**2 / (2 * total)) / denominator
    margin = (z / denominator) * math.sqrt(...)
```

**Issues Identified:**

1. **Import inside function**: `from scipy import stats` inside function is slow when called repeatedly. Move to module level.

2. **Division by zero**: If `total == 0`, returns `(0.0, 0.0)` but `p_hat = successes / total` will raise before that check.

3. **Missing sample size warning**: With small samples (< 30), Wilson interval may be unreliable. Should warn user.

---

### 6.2 Weakness Finding

**Simulation:**

```python
def analyze_losses(self, results, prompts, gemini_model_id):
    losses = [
        r for r in results
        if r.winner != gemini_model_id and r.winner != "TIE"
        and gemini_model_id in {r.model_a, r.model_b}
    ]
```

**Issues Identified:**

1. **Multiple Gemini models**: In Pro vs Flash tiers, there are multiple Gemini model IDs. Should accept list:
```python
def analyze_losses(self, results, prompts, gemini_model_ids: list[str]):
```

2. **Statistical significance testing incomplete**: The `_is_significant_pattern` function isn't implemented.

3. **Reasoning theme extraction incomplete**: `_extract_reasoning_themes` accesses `loss.raw_judgments` and `loss.gemini_position` which aren't in the `AggregatedResult` schema.

**Missing fields in AggregatedResult:**
```python
class AggregatedResult(BaseModel):
    ...
    raw_judgments: list[JudgmentResult]  # Missing
    gemini_position: str  # Missing ('A' or 'B')
```

---

### 6.3 PDF Report Generation

**Simulation:**

```python
from weasyprint import HTML
HTML(string=html_content).write_pdf(output_path)
```

**Issues Identified:**

1. **Template not provided**: `{report_type}_report.html` templates not included in plan.

2. **Chart embedding**: `_create_win_rate_chart` returns base64 PNG but template must properly embed:
```html
<img src="data:image/png;base64,{{ win_rate_chart }}">
```

3. **CSS for PDF**: WeasyPrint has limited CSS support. Need to test complex layouts.

4. **Memory for large reports**: Generating many charts at once could exhaust memory. Should stream or generate on demand.

5. **Jinja2 security**: `autoescape=True` is good but template should also validate input data.

---

## Phase 7: TUI Implementation

### 7.1 Textual App Structure

**Simulation:**

```python
class EvalTUI(App):
    prompts_completed = reactive(0)
    ...

    async def refresh_data(self) -> None:
        if self.eval_state:
            self.prompts_completed = self.eval_state.completed_count
```

**Issues Identified:**

1. **`self.eval_state` not defined**: The reactive data comes from somewhere but initialization not shown.

2. **Thread safety**: If evaluation runs in separate thread/process, need proper synchronization:
```python
# Option 1: Shared memory
eval_state = multiprocessing.Manager().dict()

# Option 2: File-based
self.eval_state = await self._load_checkpoint()
```

3. **Missing ResultsTable implementation**: Referenced but not provided.

4. **Screen navigation**: `self.push_screen(ComparisonDetailScreen(result))` but no back navigation shown.

5. **Error display**: No UI for showing/recovering from errors during evaluation.

---

## Phase 8: Checkpoint and Recovery

### 8.1 Checkpoint System

**Simulation:**

```python
async def save_checkpoint(self, state: EvalState) -> None:
    # ... build checkpoint_data ...

    async with aiofiles.open(self.temp_file, 'w') as f:
        await f.write(json.dumps(checkpoint_data, indent=2))

    self.temp_file.rename(self.checkpoint_file)
```

**Issues Identified:**

1. **aiofiles not in dependencies**: As noted earlier.

2. **Rename not atomic on Windows**: `Path.rename()` may not be atomic on Windows. Should use:
```python
import os
os.replace(str(self.temp_file), str(self.checkpoint_file))
```

3. **Large checkpoint files**: With 1000+ prompts, checkpoint could be large. Consider compression:
```python
import gzip
async with aiofiles.open(self.temp_file, 'wb') as f:
    await f.write(gzip.compress(json.dumps(checkpoint_data).encode()))
```

4. **Checkpoint frequency**: No guidance on when to checkpoint. Should checkpoint after each prompt completion, not just periodically.

5. **Database checkpoint redundancy**: Code saves to both file and DB but doesn't handle disagreement on recovery.

---

## Phase 9: Cost Estimation

### 9.1 Pre-Evaluation Cost Estimate

**The plan shows cost UI but no implementation for calculating costs.**

**Required implementation:**

```python
class CostEstimator:
    # OpenRouter pricing as of Jan 2026 (verify at runtime)
    PRICING = {
        "anthropic/claude-opus-4.5": {"input": 15.0, "output": 75.0},  # per 1M tokens
        "openai/gpt-5.2": {"input": 10.0, "output": 30.0},
        "google/gemini-3.0-pro": {"input": 7.0, "output": 21.0},
        "anthropic/claude-sonnet": {"input": 3.0, "output": 15.0},
        # ... etc
    }

    def estimate_run_cost(self, config: EvalConfig) -> CostEstimate:
        # Response generation
        avg_prompt_tokens = 500
        avg_response_tokens = 400
        response_cost = 0.0

        for model in config.models:
            pricing = self.PRICING.get(model, {"input": 10, "output": 30})
            model_calls = config.prompts
            response_cost += (
                model_calls * avg_prompt_tokens * pricing["input"] / 1_000_000 +
                model_calls * avg_response_tokens * pricing["output"] / 1_000_000
            )

        # Judging cost
        judge_prompt_tokens = 2000  # prompt + 2 responses
        judge_response_tokens = 200
        judge_cost = 0.0

        num_comparisons = config.prompts * len(config.model_pairs)
        num_judge_calls = num_comparisons * config.judges * config.votes_per_judge * 2  # 2 personas
        if config.shuffle_positions:
            num_judge_calls *= 2

        for judge_model in config.judge_models:
            pricing = self.PRICING.get(judge_model, {"input": 10, "output": 30})
            calls = num_judge_calls / len(config.judge_models)
            judge_cost += (
                calls * judge_prompt_tokens * pricing["input"] / 1_000_000 +
                calls * judge_response_tokens * pricing["output"] / 1_000_000
            )

        return CostEstimate(
            response_generation=response_cost,
            judging=judge_cost,
            total=response_cost + judge_cost,
            confidence="medium"  # actual costs may vary 20%
        )
```

**Issue:** Pricing data becomes stale. Should fetch from OpenRouter API at runtime.

---

## Summary of Critical Issues

### Blockers (Must Fix Before Implementation)

1. **WeasyPrint system dependencies not documented** - Will fail on fresh install
2. **aiofiles missing from dependencies** - Checkpoint code will crash
3. **BLS crosswalk data not provided** - NAICS mapping won't work
4. **Model IDs are speculative** - Need runtime verification
5. **Best-of-5 voting not implemented** - Core evaluation logic missing
6. **Judge context incomplete** - Won't evaluate properly per PROMPT.md requirements

### High Priority Issues

1. Combinatorial explosion in stratified sampling
2. Position shuffling doubles+ judge API costs
3. Memory issues with large task/combination sets
4. Missing rate limiter implementation
5. Template files for PDF reports not provided
6. Cost estimation logic not implemented

### Medium Priority Issues

1. Schema validation incomplete (task_type, validators)
2. Regex for JSON parsing misses edge cases
3. TUI state synchronization unclear
4. Checkpoint frequency not specified
5. Error messages lose context

### Recommendations

1. **Create setup script** that installs system dependencies and validates environment
2. **Implement `--dry-run` mode** that validates everything without making API calls
3. **Add comprehensive logging** with structured JSON format for debugging
4. **Create test fixtures** with sample O*NET data for unit tests
5. **Document all model ID mappings** with version tracking
6. **Add cost ceiling** that aborts evaluation if estimated cost exceeds budget

---

## Files That Need Creation Before Implementation

1. `data/companies.json` - Curated company database
2. `data/names.json` - Name pools by demographic
3. `data/naics_soc_crosswalk.json` - Industry mapping
4. `src/reports/templates/comprehensive_report.html` - Report template
5. `src/reports/templates/executive_summary.html` - Summary template
6. `requirements-system.txt` - System dependency documentation
7. `.gitignore` - Exclude results/, .env, etc.
8. `INSTALL.md` - Installation instructions
