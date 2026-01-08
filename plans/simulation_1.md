# Implementation Simulation Report

## Overview

This document simulates implementing the Master Plan for the Gemini Writing Evaluation Framework, walking through each component as if actually coding it. The goal is to identify what works well, what doesn't, missing pieces, gotchas, and technical blockers.

---

## Part 1: Project Setup and Foundation

### 1.1 Simulating pyproject.toml Setup

**What Works Well:**
- The dependency list is comprehensive and modern (pydantic 2.x, httpx, asyncio-native libraries)
- Python 3.11+ requirement is appropriate for modern async patterns
- The dev dependencies include proper testing tools

**Issues Identified:**

1. **aiofiles Missing**: The plan uses `aiofiles.open()` in the CheckpointManager but aiofiles is not in the dependencies list. Need to add:
   ```toml
   "aiofiles>=23.2",
   ```

2. **Version Pinning Risk**: Many dependencies use `>=` without upper bounds. For a production eval framework, consider pinning more strictly to avoid breaking changes:
   ```toml
   # Risk: plotly 6.x may have breaking changes
   "plotly>=5.18,<6.0",
   ```

3. **Missing Type Stubs**: For full mypy support, add:
   ```toml
   "types-aiofiles",
   "pandas-stubs",
   ```

4. **WeasyPrint System Dependencies**: WeasyPrint requires system libraries (cairo, pango, etc.) that aren't documented. Need installation docs for macOS/Linux.

### 1.2 Simulating Directory Structure Creation

**What Works Well:**
- Clear separation of concerns (data, prompts, eval, analysis, etc.)
- Sensible module organization

**Issues Identified:**

1. **Missing `__init__.py` files**: The plan shows directory structure but doesn't mention all the `__init__.py` files needed. Need to ensure proper package structure.

2. **Missing templates directory contents**: The `src/reports/templates/` directory is listed but no template files are specified. Need:
   - `comprehensive_report.html`
   - `executive_summary.html`
   - Base CSS files

3. **Missing data files**: The plan assumes these exist:
   - `data/companies.json` - not provided, needs to be created
   - `data/names.json` - not provided, needs to be created
   - `data/naics_soc_crosswalk.json` - not provided, external data needed

---

## Part 2: O*NET Database Integration

### 2.1 Simulating Schema Validation

**Walking through the validation code:**

```python
# Attempting to validate schema
REQUIRED_TABLES = {
    "task_statements": ["task_id", "onetsoc_code", "task"],
    "occupation_data": ["onetsoc_code", "title", "description"],
    ...
}
```

**Issues Identified:**

1. **Table Name Mismatch**: According to ONET_WRITING_REFERENCE.md, the actual table names and columns need verification. Simulating a query against the actual database:

   The reference document shows `task_statements` with columns including `task_type`, but the validator doesn't check for this. Missing column in validation:
   ```python
   "task_statements": ["task_id", "onetsoc_code", "task", "task_type"],  # ADD task_type
   ```

2. **Element ID Verification Problem**: The plan validates element IDs like `2.A.1.c` for Writing Skill. However, per ONET_WRITING_REFERENCE.md:
   - Writing skill uses element_id `2.A.1.c` - CORRECT
   - But the query joins with `content_model_reference` to get element_name = 'Writing'

   The validator should check BOTH the element_id exists AND has the expected element_name.

3. **Missing Scale Validation**: The plan assumes scales like 'IM' and 'CX' exist but doesn't validate them. Need to add:
   ```python
   REQUIRED_SCALES = ["IM", "LV", "CX"]  # Importance, Level, Context
   ```

4. **Job Zone Reference Table**: The plan references `job_zones` table but ONET_WRITING_REFERENCE.md shows there's also a `job_zone_reference` table with zone definitions. Need to validate both.

### 2.2 Simulating Task Extraction

**Walking through ONetExtractor.extract_writing_tasks():**

```python
query = """
SELECT
    t.task_id,
    t.onetsoc_code,
    o.title as occupation_title,
    ...
    COALESCE(ws.data_value, 2.5) as writing_skill,
    ...
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
LEFT JOIN skills ws ON t.onetsoc_code = ws.onetsoc_code
    AND ws.element_id = '2.A.1.c' AND ws.scale_id = 'IM'
...
"""
```

**Issues Identified:**

1. **Query Will Fail**: The `occupation_data` table may have different column names. Per ONET_WRITING_REFERENCE.md, need to verify the exact column name for description (`description` vs `desc` vs `occupation_description`).

2. **Missing Task Type Filter**: The extraction doesn't filter by `task_type`. Per ONET_WRITING_REFERENCE.md, task_type can be 'Core', 'Supplemental', or NULL. Core tasks are more universally performed - should this be a filter option?
   ```python
   # Should add optional filter
   if core_tasks_only:
       query += " WHERE t.task_type = 'Core'"
   ```

3. **Performance Issue with COALESCE**: Using COALESCE with default 2.5 for missing writing skills is problematic:
   - Many occupations may legitimately have no writing skill score
   - Default of 2.5 (middle of 1-5 scale) artificially inflates relevance
   - Better approach: use NULL and handle in Python with explicit logic

4. **SQL Injection Risk (Minor)**: While the current implementation uses parameterized queries for user inputs, the job_zones and soc_codes filters are built dynamically. Verify they're properly escaped:
   ```python
   # Current approach is safe if using parameterized queries
   # But plan doesn't show the parameterization clearly
   ```

5. **Missing Emerging Tasks**: ONET_WRITING_REFERENCE.md mentions 328 emerging tasks in `emerging_tasks` table that may reflect modern communication needs (email, social media). The extraction query doesn't include these. Should add:
   ```python
   UNION ALL
   SELECT e.*, 'emerging' as source FROM emerging_tasks e ...
   ```

### 2.3 Simulating Writing Relevance Computation

**Walking through _compute_writing_relevance():**

```python
WRITING_INDICATORS = [
    (r'\bwrite\b', 1.0),
    (r'\bdraft\b', 1.0),
    ...
    (r'\bcommunicat', 0.6),
    (r'\bpresent\b', 0.5),
]
```

**Issues Identified:**

1. **False Positives with 'present'**: The pattern `\bpresent\b` with weight 0.5 will match:
   - "Present findings to management" (relevant)
   - "Present employees with awards" (not writing-relevant)
   - "At present, the system..." (not relevant)

   Need more specific patterns or context-aware matching.

2. **Missing Important Patterns**: Per ONET_WRITING_REFERENCE.md categories, missing:
   ```python
   (r'\bnotify\b', 0.8),      # From Correspondence category
   (r'\binform\b', 0.7),      # From Correspondence category
   (r'\bpersuade\b', 0.8),    # From Persuasion category
   (r'\bcontract\b', 0.7),    # From Contracts category
   ```

3. **Regex Compilation Not Cached**: Each task will recompile all regex patterns. For 18,796 tasks, this is wasteful:
   ```python
   # Should pre-compile in __init__
   self._compiled_patterns = [(re.compile(p), w) for p, w in self.WRITING_INDICATORS]
   ```

4. **O*NET Score Normalization Issue**: The relevance combination logic has a bug:
   ```python
   onet_score = (
       row.get('writing_skill', 2.5) * 0.4 +
       row.get('email_freq', 2.5) * 0.3 +
       row.get('letter_freq', 2.5) * 0.3
   ) / 5.0  # Normalize to 0-1
   ```

   The ONET_WRITING_REFERENCE.md states scores are 1-5, so:
   - Max weighted sum = 5.0 * 0.4 + 5.0 * 0.3 + 5.0 * 0.3 = 5.0
   - Dividing by 5.0 gives max of 1.0 - CORRECT
   - But min would be (1*0.4 + 1*0.3 + 1*0.3) / 5 = 0.2, not 0

   Should normalize properly:
   ```python
   onet_score = (weighted_sum - 1.0) / 4.0  # Map 1-5 to 0-1
   ```

---

## Part 3: NAICS Industry Mapping

### 3.1 Simulating NAICSMapper

**Issues Identified:**

1. **Missing BLS Matrix Data**: The plan assumes `bls_matrix_path` might be provided but doesn't specify:
   - Where to get this data
   - What format it should be in
   - Whether the URL/source is still valid

   **BLOCKER**: Without external BLS data, falls back to hardcoded mappings that may not reflect actual occupation-industry distributions.

2. **Incomplete Fallback Mapping**: The FALLBACK_SOC_TO_NAICS only shows partial mapping:
   ```python
   FALLBACK_SOC_TO_NAICS = {
       "11": [...],  # Management
       "13": [...],  # Business/Financial
       "15": [...],  # Computer/Math
       "17": [...],  # Engineering
       # ... missing SOC codes 19-55!
   }
   ```

   Need mappings for all 22 SOC major groups listed in ONET_WRITING_REFERENCE.md.

3. **NAICS Sector Codes Incomplete**: The NAICS_SECTORS dict only has 20 entries but the official NAICS has more (e.g., missing 32-33 for Manufacturing breakdown, 44-45 split for Retail).

4. **Reproducibility Issue with sample_industry()**: The function uses `random.Random(seed)` but creates a new instance each call. For deterministic behavior across runs, should use a seeded instance consistently:
   ```python
   # Current: Creates new Random each call
   rng = random.Random(seed)

   # Better: Pass RNG instance or use module-level seeded generator
   ```

---

## Part 4: Company Database

### 4.1 Simulating CompanyDatabase

**Walking through get_company():**

```python
def get_company(
    self,
    naics_code: str,
    company_size: CompanySize,
    seed: int,
    use_real: bool = True,
    llm_client: LLMClient | None = None
) -> Company:
```

**Issues Identified:**

1. **CRITICAL: companies.json Doesn't Exist**: The plan references `data/companies.json` but this file needs to be created. Need:
   - Curated list of real companies by NAICS code
   - Company metadata (size, industry, HQ location)
   - Minimum ~500-1000 companies for diversity

   **Suggested approach:**
   - Use Fortune 500 list (publicly available)
   - Use Inc 5000 for smaller companies
   - Use Crunchbase data for startups (requires API)
   - Manual curation is time-intensive

2. **Async/Sync Mismatch**: The method is defined as sync (`def get_company`) but calls `await self._generate_companies()`:
   ```python
   # BUG: Can't await in sync function
   self._generated_cache[cache_key] = await self._generate_companies(...)
   ```

   Need to make the method async:
   ```python
   async def get_company(self, ...) -> Company:
   ```

3. **LLM Generation Caching Issue**: Companies are cached in memory (`self._generated_cache`) but not persisted. If process restarts mid-evaluation, regeneration uses different companies, breaking reproducibility:
   ```python
   # Should persist cache to disk
   async def _generate_companies(self, ...):
       cache_file = self.cache_dir / f"generated_{naics_code}_{size.value}.json"
       if cache_file.exists():
           return self._load_from_file(cache_file)
       # ... generate and save ...
   ```

4. **NAICS Code Matching Too Strict**: The current matching only checks first 2 digits:
   ```python
   if c['naics'].startswith(naics_code[:2])
   ```

   This means a request for NAICS 541511 (Custom Software) will match any company in sector 54 (Professional Services), including law firms (5411). Should have tiered matching:
   ```python
   # Try exact match first, then progressively broader
   for prefix_len in [6, 4, 2]:
       candidates = [c for c in self._companies
                     if c['naics'].startswith(naics_code[:prefix_len])]
       if candidates:
           break
   ```

### 4.2 Simulating Name Generation

**Walking through NameGenerator:**

**Issues Identified:**

1. **Demographic Distribution Outdated**: The DEMOGRAPHIC_WEIGHTS use Census data but:
   ```python
   DEMOGRAPHIC_WEIGHTS = {
       "white": 0.61,
       "hispanic": 0.19,
       "black": 0.13,
       "asian": 0.06,
       "other": 0.01,
   }
   ```

   - These don't sum to 1.0 (0.61+0.19+0.13+0.06+0.01 = 1.0) - OK
   - But workforce demographics differ from general population
   - Should ideally use BLS workforce demographics by occupation type

2. **Name Pool Size Too Small**: The NAME_POOLS shown have only 6-7 names per category. For 10,000+ prompts, this creates:
   - High repetition rate
   - Obvious patterns in generated prompts
   - Need at least 100+ names per demographic/gender combination

3. **Missing Age/Generation Context**: The plan requires age diversity (GenZ to Boomer) but NameGenerator doesn't support this:
   ```python
   # Missing: Names appropriate for different generations
   # "Ethel" and "Gladys" more common for Boomers
   # "Jayden" and "Aiden" more common for GenZ
   ```

4. **Email Generation Not Implemented**: PROMPT.md requires realistic email addresses:
   > Include realistic email addresses where appropriate (sarah.chen@acme.com)

   The NameGenerator returns PersonName but doesn't include email. Need:
   ```python
   class PersonName(BaseModel):
       first: str
       last: str
       full: str
       email: str  # ADD THIS
       demographic: str
       gender: str
   ```

   And generation logic:
   ```python
   def _generate_email(self, first: str, last: str, company: str) -> str:
       formats = [
           f"{first.lower()}.{last.lower()}@{company}.com",
           f"{first[0].lower()}{last.lower()}@{company}.com",
           f"{first.lower()}_{last.lower()}@{company}.com",
       ]
       return random.choice(formats)
   ```

---

## Part 5: Prompt Generation Pipeline

### 5.1 Simulating Phase 1 (Offline Persona Generation)

**Walking through Phase1Generator:**

**Issues Identified:**

1. **model="smart_cheap" Undefined**: The code uses:
   ```python
   response = await llm_client.generate(
       self.PERSONA_GENERATION_PROMPT.format(count=count),
       model="smart_cheap"
   )
   ```

   But "smart_cheap" is not defined in the model registry. Need to map this to actual model:
   ```python
   MODEL_ALIASES = {
       "smart_cheap": "anthropic/claude-sonnet",  # or similar
       "cheap_fast": "openai/gpt-4.1-mini",
   }
   ```

2. **Token Limit Risk**: Generating 100+ personas in a single prompt risks hitting token limits:
   ```python
   PERSONA_GENERATION_PROMPT = """
   Generate {count} diverse professional personas...
   """
   ```

   If count=100 and each persona is ~200 tokens, output would be 20,000 tokens. Need batching:
   ```python
   async def generate_personas(self, count: int, ...) -> list[Persona]:
       batch_size = 20
       all_personas = []
       for i in range(0, count, batch_size):
           batch = await self._generate_batch(min(batch_size, count - i), ...)
           all_personas.extend(batch)
       return all_personas
   ```

3. **Persona ID Generation Missing**: The Persona model requires an `id` field but generation doesn't create one:
   ```python
   # Need to add ID generation
   personas = [
       Persona(id=f"persona_{i:04d}", **p)
       for i, p in enumerate(self._parse_personas(response))
   ]
   ```

4. **Cache Invalidation**: If requirements change (e.g., add new persona fields), cached personas become stale. Need cache versioning:
   ```python
   cache_path = data_dir / f"personas_v{PERSONA_SCHEMA_VERSION}.json"
   ```

### 5.2 Simulating Phase 2 (Algorithmic Combination)

**Walking through Phase2Combiner:**

**Issues Identified:**

1. **Combinatorial Explosion**: The code generates all combinations then samples:
   ```python
   all_combinations = self._generate_all_combinations()
   ```

   With:
   - ~5000 O*NET tasks (after filtering)
   - ~100 personas
   - ~50 scenario seeds
   - ~20 NAICS sectors
   - ~3 word count tiers
   - ~3 urgency levels

   Total combinations = 5000 * 100 * 50 * 20 * 3 * 3 = 4.5 billion

   **CRITICAL BLOCKER**: Can't enumerate all combinations. Need lazy generation:
   ```python
   def _generate_combinations_lazily(self, count: int, seed: int):
       """Generate combinations on-demand without full enumeration."""
       rng = random.Random(seed)
       seen = set()
       while len(seen) < count:
           combo = (
               rng.choice(self.tasks),
               rng.choice(self.personas),
               rng.choice(self.scenario_seeds),
               # ... etc
           )
           combo_hash = hash(combo)
           if combo_hash not in seen:
               seen.add(combo_hash)
               yield combo
   ```

2. **Stratification Across 8 Dimensions Impractical**: The plan lists 8 stratification dimensions:
   ```python
   STRATIFICATION_DIMENSIONS = [
       "job_zone",           # 5 values
       "writing_category",   # ~10 values
       "channel",            # ~6 values
       "formality",          # ~4 values
       "word_count_tier",    # 3 values
       "urgency",            # 3 values
       "soc_major_group",    # 22 values
       "naics_sector",       # ~20 values
   ]
   ```

   Total strata = 5 * 10 * 6 * 4 * 3 * 3 * 22 * 20 = 9.5 million strata

   For 500 prompts, most strata will have 0 samples. Need to:
   - Reduce dimensions (pick top 3-4 most important)
   - Use hierarchical stratification instead of full cross-product
   - Or use weighted random sampling with diversity bonus

3. **_combination_to_prompt Missing Required Fields**: The BasePrompt model requires a `scenario_seed` but the combination dictionary may not always have one:
   ```python
   return BasePrompt(
       id=f"prompt_{seed:08x}",
       task=combo['task'],
       persona=combo['persona'],
       scenario_seed=combo['scenario_seed'],  # KeyError if missing
       ...
   )
   ```

4. **Company Size Inference Undefined**: The code calls:
   ```python
   self._infer_company_size(combo['persona'])
   ```

   But this method is not defined. Need to implement:
   ```python
   def _infer_company_size(self, persona: Persona) -> CompanySize:
       """Infer likely company size from persona."""
       if persona.experience_level == "executive":
           return random.choice([CompanySize.MEDIUM, CompanySize.LARGE, CompanySize.ENTERPRISE])
       elif persona.experience_level == "junior":
           return random.choice([CompanySize.STARTUP, CompanySize.SMALL, CompanySize.MEDIUM])
       # ... etc
   ```

### 5.3 Simulating Phase 3 (LLM Enrichment)

**Walking through Phase3Enricher:**

**Issues Identified:**

1. **Prompt Template Has Unsafe String Formatting**:
   ```python
   filled_prompt = self.ENRICHMENT_PROMPT.format(
       persona=base_prompt.persona,
       company=base_prompt.company,
       ...
   )
   ```

   If any field contains `{` or `}`, this will fail. Use safer formatting:
   ```python
   from string import Template
   template = Template(self.ENRICHMENT_PROMPT)
   filled_prompt = template.safe_substitute(...)
   ```

2. **JSON Parsing Without Validation**: The enrichment expects JSON output:
   ```python
   enrichment = self._parse_enrichment(response)
   ```

   But `_parse_enrichment` isn't shown, and LLM outputs are unreliable. Need robust parsing like the JudgeParser but it's not reused here.

3. **Context Details Schema Undefined**: The enrichment prompt requests:
   ```python
   "context_details": {{
       "project_name": "...",
       "deadline": "...",
       "specific_numbers": [...],
       "stakeholders": [...]
   }}
   ```

   But not all prompts need all fields. Should make schema flexible:
   ```python
   context_details: dict[str, Any] = Field(default_factory=dict)
   ```

4. **Temperature 0.7 May Cause Inconsistency**: Higher temperature increases variety but also increases risk of:
   - Off-topic responses
   - Inconsistent formats
   - Hallucinated constraints

   Consider temperature 0.3-0.5 for structured output tasks.

5. **Rate Limiting for Batch Enrichment**: The `enrich_batch` method has concurrency control:
   ```python
   semaphore = asyncio.Semaphore(concurrency)
   ```

   But doesn't integrate with the global rate limiter. If enriching 1000 prompts with concurrency=5, could overwhelm API:
   ```python
   async def enrich_with_semaphore(prompt: BasePrompt) -> EnrichedPrompt:
       async with semaphore:
           await self.rate_limiter.acquire()  # ADD THIS
           enriched = await self.enrich_prompt(prompt, llm_client)
   ```

---

## Part 6: OpenRouter API Integration

### 6.1 Simulating Model Verification

**Walking through ModelVerifier:**

**Issues Identified:**

1. **Model IDs Are Speculative**: The EXPECTED_MODELS dictionary uses IDs like:
   ```python
   "gemini_pro": "google/gemini-3.0-pro",
   "gpt_pro": "openai/gpt-5.2",
   ```

   These model IDs don't exist yet (as of the knowledge cutoff). The actual OpenRouter model IDs will likely differ. Need:
   - Runtime verification as the plan suggests
   - But also a fallback strategy when expected models don't exist

2. **_find_similar() Is Fragile**: The similar model finder:
   ```python
   def _find_similar(self, target: str, available: set) -> str | None:
       provider, name = target.split("/")
       for model_id in available:
           if provider in model_id and any(
               part in model_id for part in name.split("-")
           ):
               return model_id
   ```

   Problems:
   - `target.split("/")` fails if no "/" in ID
   - Matching "3.0" in "gemini-3.0-pro" could match "gemini-3.0-flash"
   - No version preference (might match older version)

   Better approach:
   ```python
   def _find_similar(self, target: str, available: set) -> str | None:
       if "/" not in target:
           return None
       provider, name = target.split("/", 1)  # maxsplit=1
       candidates = [m for m in available if m.startswith(provider + "/")]

       # Sort by version similarity and pick best
       return self._best_match(name, candidates) if candidates else None
   ```

3. **API Key Validation Timing**: The verification happens only at startup. If API key expires mid-run (e.g., rate limits, billing), no recovery:
   ```python
   # Should add periodic health checks
   async def _periodic_health_check(self):
       while True:
           await asyncio.sleep(300)  # Every 5 minutes
           try:
               await self.api_client.health_check()
           except AuthError:
               self._pause_evaluation("API key invalid")
   ```

### 6.2 Simulating Response Collection

**Walking through ResponseCollector:**

**Issues Identified:**

1. **Missing max_tokens Estimation**: The `_estimate_max_tokens()` method is called but not defined:
   ```python
   max_tokens=self._estimate_max_tokens(prompt),
   ```

   Need to implement based on word_count_tier:
   ```python
   def _estimate_max_tokens(self, prompt: EnrichedPrompt) -> int:
       TIER_TOKENS = {
           "short": 500,
           "medium": 1500,
           "long": 4000,
       }
       base = TIER_TOKENS.get(prompt.word_count_tier, 1500)
       return int(base * 1.5)  # Buffer for variability
   ```

2. **Response Schema Mismatch**: The code expects:
   ```python
   response_text=response.content,
   token_count=response.usage.total_tokens,
   ```

   But OpenRouter's response format may differ. Need to verify and handle:
   ```python
   # OpenRouter format might be:
   response_text=response["choices"][0]["message"]["content"],
   token_count=response.get("usage", {}).get("total_tokens", 0),
   ```

3. **No Timeout Configuration**: The response collection has no explicit timeout. Long-running generations could block:
   ```python
   response = await self.api_client.generate(
       prompt=prompt.prompt_text,
       model=model_id,
       # ADD: timeout=60.0
   )
   ```

4. **Circuit Breaker per-model but Rate Limiter shared?**: The circuit breaker is per-service:
   ```python
   if not self.circuit_breaker.allow_request(model_id):
   ```

   But rate_limiter.acquire() signature suggests per-model:
   ```python
   await self.rate_limiter.acquire(model_id)
   ```

   Need to ensure rate limits are per-provider, not per-model (OpenRouter has provider-level limits).

### 6.3 Simulating OpenRouter Client

**Issues Identified:**

1. **Client Not Shown**: The plan references `OpenRouterClient` but doesn't show implementation. Key requirements:
   - Proper authentication headers
   - Error classification (transient vs permanent)
   - Response streaming support (for progress indication)
   - Cost tracking per request

2. **OpenRouter-Specific Headers Missing**: OpenRouter requires specific headers:
   ```python
   headers = {
       "Authorization": f"Bearer {api_key}",
       "HTTP-Referer": "https://your-app.com",  # Required
       "X-Title": "Gemini Writing Eval",  # Optional but recommended
   }
   ```

3. **Missing Request ID Tracking**: For debugging failed requests:
   ```python
   # Should log request IDs
   request_id = response.headers.get("x-request-id")
   logger.debug(f"Request {request_id}: {model_id} completed in {latency_ms}ms")
   ```

---

## Part 7: Judging System

### 7.1 Simulating Dual-Persona Judge

**Walking through DualPersonaJudge:**

**Issues Identified:**

1. **Recipient Role Inference Undefined**:
   ```python
   recipient_role=self._infer_recipient_role(prompt),
   ```

   Method not shown. Need to implement:
   ```python
   def _infer_recipient_role(self, prompt: EnrichedPrompt) -> str:
       """Infer recipient's role from prompt context."""
       # Could be from scenario_seed.audience
       # Or inferred from task type
       if "customer" in prompt.task.task.lower():
           return "customer"
       elif "manager" in prompt.task.task.lower():
           return "manager"
       # ... etc
       return "colleague"  # default
   ```

2. **System Prompt Not Used in generate()**: The dual persona uses:
   ```python
   response = await api_client.generate(
       prompt=comparison_prompt,
       model=judge_model,
       system=system_prompt,  # Is this supported?
   )
   ```

   But the OpenRouterClient.generate() interface isn't shown. Need to verify system prompts are passed correctly.

3. **Judge Prompt Too Long**: The COMPARISON_PROMPT includes full responses:
   ```python
   RESPONSE A:
   {response_a}

   RESPONSE B:
   {response_b}
   ```

   For long responses (4000+ tokens each), this could hit context limits. Need:
   - Token counting before submission
   - Truncation strategy for very long responses
   - Or use models with longer context

4. **Hardcoded "2-3 sentences" for Reasoning**: The prompt requests brief reasoning, but this may be insufficient for understanding complex decisions:
   ```python
   "reasoning": "Brief explanation of your evaluation (2-3 sentences)",
   ```

   Consider making this configurable:
   ```python
   REASONING_STYLES = {
       "brief": "2-3 sentences",
       "detailed": "Explain your reasoning thoroughly (1-2 paragraphs)",
   }
   ```

### 7.2 Simulating Position Bias Handling

**Walking through PositionBiasHandler:**

**Issues Identified:**

1. **Doubles API Cost**: Every comparison requires 2 orderings:
   ```python
   # Order 1: A first, B second
   expert_ab, recipient_ab = await judge.judge_comparison(...)

   # Order 2: B first, A second
   expert_ba, recipient_ba = await judge.judge_comparison(...)
   ```

   With 3 judges, 2 personas, 2 orderings = 12 API calls per comparison.
   For 500 prompts = 6000 judge calls minimum.

   This may be necessary for robustness but doubles the already-high judging cost.

2. **Contradictory Results Not Handled**: If a judge says A>B in order1 but also A>B in order2 (after swap), that's position bias. But the aggregation just takes majority without flagging:
   ```python
   expert_winner = self._position_majority(expert_winners, model_a, model_b)
   ```

   Should flag and potentially exclude contradictory judgments:
   ```python
   def _check_consistency(self, winner_ab: str, winner_ba: str,
                          model_a: str, model_b: str) -> bool:
       """Check if judgments are consistent across positions."""
       # If judge says A wins in both orderings, that's suspicious
       if winner_ab == model_a and winner_ba == model_a:
           return False  # Position A always wins - bias
       return True
   ```

3. **_map_winner Return Type Inconsistency**: Returns model_id string or "TIE":
   ```python
   def _map_winner(self, judgment, pos_a_model, pos_b_model) -> str:
       if judgment.winner == "A":
           return pos_a_model
       elif judgment.winner == "B":
           return pos_b_model
       else:
           return "TIE"
   ```

   But what if judgment.winner is "PARSE_ERROR"? Should handle:
   ```python
   elif judgment.winner in ["TIE", "PARSE_ERROR"]:
       return judgment.winner  # Preserve error state
   ```

### 7.3 Simulating Vote Aggregation

**Walking through VoteAggregator:**

**Issues Identified:**

1. **Best-of-5 Not Implemented**: The plan says "best-of-5 judgments per comparison" but the actual aggregation only has 2 votes per judge-persona (one per position ordering):
   ```python
   expert_winners = [
       sj.judgments['expert_ab'],
       sj.judgments['expert_ba']
   ]
   expert_winner = self._position_majority(expert_winners, model_a, model_b)
   ```

   To implement best-of-5, need to run 5 rounds per ordering:
   ```python
   for round_num in range(5):
       expert_ab[round_num], recipient_ab[round_num] = await judge.judge_comparison(...)
   ```

   This further increases API costs: 3 judges * 2 personas * 2 orderings * 5 rounds = 60 calls per comparison!

2. **_simple_majority Not Shown**: The method is called but not defined:
   ```python
   final_winner = self._simple_majority(all_winners, model_a, model_b)
   ```

   Need to implement:
   ```python
   def _simple_majority(self, winners: list[str], model_a: str, model_b: str) -> str:
       counts = Counter(winners)
       if counts[model_a] > counts[model_b]:
           return model_a
       elif counts[model_b] > counts[model_a]:
           return model_b
       else:
           return "TIE"
   ```

3. **_compute_position_consistency Not Shown**: Referenced but not defined. Need implementation:
   ```python
   def _compute_position_consistency(self, judge_persona_winners) -> float:
       """Compute how often judgments agree across position shuffles."""
       consistent = 0
       total = 0
       # Group by judge-persona, check if AB and BA agree
       # ...
       return consistent / total if total > 0 else 1.0
   ```

4. **AggregatedResult Missing prompt_id**: The aggregate function returns AggregatedResult but doesn't include the prompt_id. Need to pass it:
   ```python
   return AggregatedResult(
       prompt_id=prompt_id,  # ADD THIS
       winner=final_winner,
       ...
   )
   ```

### 7.4 Simulating JSON Parsing

**Walking through JudgeParser:**

**What Works Well:**
- 4-tier fallback strategy is robust
- Handles common JSON issues (trailing commas, single quotes)

**Issues Identified:**

1. **Regex for Winner Too Permissive**:
   ```python
   winner_match = re.search(r'"?winner"?\s*:\s*"?([ABab]|TIE|tie)"?', text, re.I)
   ```

   This could match text like "the winner of the A/B test was..." Need more specific pattern:
   ```python
   winner_match = re.search(r'"winner"\s*:\s*"?(A|B|TIE)"?', text, re.I)
   ```

2. **No Validation of Parsed Results**: After parsing, values aren't validated:
   ```python
   return JudgmentResult(
       winner=parsed.get('winner', 'PARSE_ERROR'),
       ...
   )
   ```

   Should validate:
   ```python
   winner = parsed.get('winner', 'PARSE_ERROR')
   if winner not in ['A', 'B', 'TIE', 'PARSE_ERROR']:
       winner = 'PARSE_ERROR'
   ```

3. **Nested JSON Not Handled**: The `_find_json_structure` balances braces but doesn't handle nested objects like `strengths_a: [...]`:
   ```python
   # This JSON would fail:
   {
     "winner": "A",
     "strengths_a": ["good length", "clear"]
   }
   ```

   The brace balancing would stop at first `}`. Need proper JSON extraction:
   ```python
   import json
   decoder = json.JSONDecoder()
   obj, end = decoder.raw_decode(text[start:])
   ```

---

## Part 8: Analysis and Statistics

### 8.1 Simulating Statistics Engine

**Walking through StatisticsEngine:**

**What Works Well:**
- Wilson score interval is the correct choice for proportions
- Head-to-head matrix is useful for visualization

**Issues Identified:**

1. **scipy Import at Call Time**: The Wilson score imports scipy inside the method:
   ```python
   def _wilson_score_interval(self, ...):
       from scipy import stats
   ```

   This adds latency on every call. Import at module level instead.

2. **win_rate_excluding_ties Calculation Edge Case**:
   ```python
   win_rate_excluding_ties=wins / (wins + losses) if (wins + losses) > 0 else 0.0,
   ```

   If all results are ties, this returns 0.0. Should return None or 0.5:
   ```python
   win_rate_excluding_ties=wins / (wins + losses) if (wins + losses) > 0 else None,
   ```

3. **Head-to-Head Matrix Doesn't Handle Missing Pairs**: If not all model pairs were evaluated:
   ```python
   relevant = [r for r in results if {r.model_a, r.model_b} == {model_a, model_b}]
   if not relevant:
       matrix.loc[model_a, model_b] = 0.5  # Default, but is this right?
   ```

   Should mark as NaN instead:
   ```python
   matrix.loc[model_a, model_b] = float('nan')  # Or use pd.NA
   ```

### 8.2 Simulating Agreement Metrics

**Walking through AgreementMetrics:**

**Issues Identified:**

1. **Fleiss Kappa Implementation Looks Correct** but should be tested:
   - Edge case: all raters agree -> kappa = 1.0
   - Edge case: all raters disagree randomly -> kappa close to 0
   - Edge case: systematic disagreement -> kappa can be negative

2. **Cohen's Kappa Dependency**:
   ```python
   from sklearn.metrics import cohen_kappa_score
   return cohen_kappa_score(ratings_a, ratings_b)
   ```

   This works but sklearn is a heavy dependency just for one function. Could implement manually to reduce dependencies.

3. **Categories Parameter Hardcoded?**: The Fleiss kappa takes categories:
   ```python
   def fleiss_kappa(self, ratings, categories):
   ```

   But the caller needs to know what categories to pass. Should have defaults:
   ```python
   def fleiss_kappa(self, ratings, categories=None):
       if categories is None:
           categories = list(set(r for item in ratings for r in item))
   ```

### 8.3 Simulating Weakness Finding

**Walking through WeaknessFinder:**

**Issues Identified:**

1. **_group_by_dimension Not Shown**: Method called but not defined:
   ```python
   by_category = self._group_by_dimension(losses, prompts, 'inferred_category')
   ```

   Need implementation:
   ```python
   def _group_by_dimension(self, results, prompts, dimension):
       grouped = defaultdict(list)
       for r in results:
           prompt = prompts.get(r.prompt_id)
           if prompt:
               value = getattr(prompt, dimension, getattr(prompt.task, dimension, 'unknown'))
               grouped[value].append(r)
       return grouped
   ```

2. **Chi-squared Test Missing**:
   ```python
   if self._is_significant_pattern(loss_rate, baseline_rate, len(results)):
   ```

   Method not shown. Need:
   ```python
   def _is_significant_pattern(self, rate, baseline, n, alpha=0.05):
       from scipy.stats import chi2_contingency
       observed = [[int(rate * n), int((1-rate) * n)],
                   [int(baseline * n), int((1-baseline) * n)]]
       chi2, p_value, _, _ = chi2_contingency(observed)
       return p_value < alpha
   ```

3. **relative_risk Calculation Wrong**:
   ```python
   relative_risk=loss_rate / baseline_rate if baseline_rate > 0 else 0,
   ```

   Relative risk should compare conditional probabilities, not rates. If loss_rate for a category is 0.2 and baseline is 0.1, RR = 2.0 (correctly computed). But the "loss_rate" in the loop is wrong:
   ```python
   loss_rate = len(loss_results) / len(results)  # This is wrong
   ```

   Should be:
   ```python
   category_total = sum(1 for r in results if self._matches_dimension(r, prompts, dimension, value))
   loss_rate = len(loss_results) / category_total if category_total > 0 else 0
   ```

4. **gemini_position Not in AggregatedResult**: The reasoning extraction assumes:
   ```python
   if loss.gemini_position == 'A':
   ```

   But AggregatedResult doesn't have this field. Need to add it or compute from model_a/model_b.

5. **raw_judgments Not in AggregatedResult**: Similarly:
   ```python
   for judgment in loss.raw_judgments:
   ```

   But AggregatedResult only has `judge_persona_votes`, not raw judgments. Need to either:
   - Add raw_judgments to AggregatedResult
   - Or query judgments from database

---

## Part 9: TUI and Progress Visualization

### 9.1 Simulating Progress Dashboard

**Walking through EvalTUI:**

**What Works Well:**
- Textual app structure is clean
- Reactive state management is appropriate
- Keyboard bindings are sensible

**Issues Identified:**

1. **eval_state Not Initialized**: The refresh_data method references:
   ```python
   if self.eval_state:
       self.prompts_completed = self.eval_state.completed_count
   ```

   But `self.eval_state` is never set. Need:
   ```python
   def __init__(self, eval_state: EvalState):
       super().__init__()
       self.eval_state = eval_state
   ```

2. **Progress Panel update_progress Wrong Method**:
   ```python
   self.query_one("#main-progress").update(progress=progress)
   ```

   Textual's ProgressBar uses `update()` with different signature. Should be:
   ```python
   progress_bar = self.query_one("#main-progress", ProgressBar)
   progress_bar.progress = progress
   ```

3. **Missing Error Handling for Query**: If UI elements don't exist:
   ```python
   self.query_one("#progress-panel").update_progress(...)  # Throws if not found
   ```

   Should use try/except or check existence:
   ```python
   panel = self.query_one("#progress-panel", ProgressPanel)
   if panel:
       panel.update_progress(...)
   ```

4. **Cost Tracking UI Not Connected**: The plan requires live cost tracking but ProgressPanel doesn't include it. Need to add:
   ```python
   yield Static("Cost: $0.00 / $500.00", id="cost-label")
   ```

5. **Thread Safety**: The eval_state is updated by async evaluation tasks while TUI reads it. Need proper synchronization:
   ```python
   import asyncio
   self._state_lock = asyncio.Lock()

   async def refresh_data(self):
       async with self._state_lock:
           # Read state safely
   ```

### 9.2 Simulating Results Browser

**Issues Identified:**

1. **results Not Defined**: The action_view_details method references:
   ```python
   result = self.results[table.cursor_row]
   ```

   But `self.results` is never initialized. Need to pass results data to the app.

2. **ComparisonDetailScreen Not Shown**: Referenced but not implemented:
   ```python
   self.push_screen(ComparisonDetailScreen(result))
   ```

   Need full implementation for detailed view.

3. **SideBySideScreen Assumes response_a/response_b**: The screen references:
   ```python
   Static(self.result.response_a, classes="response-text"),
   Static(self.result.response_b, classes="response-text"),
   ```

   But AggregatedResult doesn't have response_a/response_b fields - just model_a/model_b IDs. Need to fetch responses:
   ```python
   def __init__(self, result: AggregatedResult, responses: dict):
       self.result = result
       self.response_a = responses[result.model_a].response_text
       self.response_b = responses[result.model_b].response_text
   ```

4. **No Scrolling for Long Responses**: Using Static for full responses won't scroll if content exceeds screen. Need ScrollableContainer:
   ```python
   from textual.containers import ScrollableContainer
   yield ScrollableContainer(
       Static(self.response_a, classes="response-text"),
       id="response-a-scroll"
   )
   ```

---

## Part 10: Checkpoint and Resume

### 10.1 Simulating CheckpointManager

**What Works Well:**
- Atomic write pattern (temp file + rename) is correct
- Dual storage (file + DB) provides redundancy

**Issues Identified:**

1. **aiofiles Used but Import Not Shown**: The code uses:
   ```python
   async with aiofiles.open(self.temp_file, 'w') as f:
   ```

   But aiofiles wasn't in the dependencies (identified earlier). Also need import:
   ```python
   import aiofiles
   ```

2. **JSON Serialization for datetime**: Checkpoints include datetime:
   ```python
   "timestamp": datetime.utcnow().isoformat(),
   ```

   Good - isoformat() produces JSON-serializable string.

3. **_checkpoint_to_state Not Shown**: Method called but not defined:
   ```python
   return self._checkpoint_to_state(data)
   ```

   Need implementation to reconstruct EvalState from checkpoint data.

4. **completed_prompts Is a Set**: The checkpoint stores:
   ```python
   "completed_prompt_ids": list(state.completed_prompts),
   ```

   But when loading, need to convert back to set:
   ```python
   completed_prompts=set(data["completed_prompt_ids"])
   ```

5. **No Checkpoint Versioning**: If checkpoint format changes between versions:
   ```python
   checkpoint_data = {
       "version": 1,  # Good - has version
       ...
   }
   ```

   But no migration logic for older versions. Need:
   ```python
   def _checkpoint_to_state(self, data):
       version = data.get("version", 0)
       if version < 1:
           data = self._migrate_v0_to_v1(data)
       # ... etc
   ```

### 10.2 Simulating Failure Handler

**What Works Well:**
- Exponential backoff with different delays for different error types
- Clear distinction between transient and permanent errors

**Issues Identified:**

1. **RateLimitError.retry_after May Not Exist**: The code assumes:
   ```python
   wait_time = e.retry_after or self.RETRY_DELAYS[attempt] * 10
   ```

   But the exception class isn't defined - need to ensure it has retry_after attribute:
   ```python
   class RateLimitError(Exception):
       def __init__(self, message: str, retry_after: float | None = None):
           super().__init__(message)
           self.retry_after = retry_after
   ```

2. **TransientError vs PermanentError Classification**: These exceptions aren't defined. Need to classify API errors:
   ```python
   # 429 -> RateLimitError
   # 500, 502, 503, 504 -> TransientError
   # 400, 401, 403, 404 -> PermanentError
   ```

3. **MaxRetriesExceeded Not Defined**: Need to define:
   ```python
   class MaxRetriesExceeded(Exception):
       pass
   ```

4. **Generic Type T Not Imported**: The method signature uses:
   ```python
   async def with_retry(self, ...) -> T:
   ```

   Need:
   ```python
   from typing import TypeVar
   T = TypeVar('T')
   ```

### 10.3 Simulating Circuit Breaker

**What Works Well:**
- Standard circuit breaker pattern with three states
- Recovery timeout and half-open state are correctly implemented

**Issues Identified:**

1. **CircuitState Enum Not Defined**:
   ```python
   self._states: dict[str, CircuitState] = {}
   if state == CircuitState.CLOSED:
   ```

   Need:
   ```python
   from enum import Enum
   class CircuitState(Enum):
       CLOSED = "closed"
       OPEN = "open"
       HALF_OPEN = "half_open"
   ```

2. **Thread Safety Concerns**: The circuit breaker is accessed from multiple async tasks but has no locking:
   ```python
   self._failure_counts[service_id] += 1  # Race condition
   ```

   For async safety, use asyncio.Lock:
   ```python
   async def record_failure(self, service_id: str) -> None:
       async with self._lock:
           self._failure_counts[service_id] += 1
   ```

3. **No Circuit Breaker State Persistence**: If process restarts, all circuits reset to CLOSED. Could cause immediate failures again:
   ```python
   # Should persist open circuits
   async def save_state(self, path: Path):
       open_circuits = {
           sid: self._last_failure_time[sid]
           for sid, state in self._states.items()
           if state == CircuitState.OPEN
       }
       # ... save to file
   ```

---

## Part 11: PDF Report Generation

### 11.1 Simulating PDFReportGenerator

**Issues Identified:**

1. **Template Files Not Provided**: The plan expects:
   ```python
   template = self.env.get_template(f'{report_type}_report.html')
   ```

   But no templates are shown. Need to create:
   - `templates/comprehensive_report.html`
   - `templates/executive_summary.html`

2. **Chart Generation to Base64 Is Slow**: Every chart converts to PNG then base64:
   ```python
   img_bytes = fig.to_image(format='png', width=800, height=400)
   return base64.b64encode(img_bytes).decode('utf-8')
   ```

   For a report with 10+ charts, this adds significant latency. Consider:
   - Pre-generating charts in parallel
   - Using SVG for smaller file sizes
   - Caching generated charts

3. **WeasyPrint Memory Issues**: WeasyPrint can use significant memory for large PDFs. For comprehensive reports with many charts:
   ```python
   HTML(string=html_content).write_pdf(output_path)
   ```

   May fail with OOM. Consider:
   - Splitting into sections
   - Using reportlab as alternative
   - Streaming generation

4. **Missing Sample Selection Logic**:
   ```python
   'sample_wins': self._select_sample_comparisons(run_results, 'wins', 5),
   ```

   Method not shown. Need implementation that selects interesting examples:
   ```python
   def _select_sample_comparisons(self, results, outcome_type, n):
       if outcome_type == 'wins':
           relevant = [r for r in results.aggregated if r.winner == results.config.gemini_model]
       else:
           relevant = [r for r in results.aggregated if r.winner != results.config.gemini_model]

       # Select diverse examples across dimensions
       return self._select_diverse_samples(relevant, n)
   ```

5. **Plotly Kaleido Dependency Issues**: Plotly static image export requires kaleido:
   ```python
   fig.to_image(format='png')  # Requires kaleido
   ```

   Kaleido can have platform-specific installation issues (especially on M1 Macs). Need to:
   - Document installation requirements
   - Add fallback to screenshot-based export

---

## Part 12: Cost Estimation and Presets

### 12.1 Simulating Cost Estimation

**Issues Identified:**

1. **Pricing Data Hardcoded and Will Be Stale**: The plan doesn't show pricing logic but presets have estimated costs:
   ```python
   estimated_cost=200.00,
   ```

   OpenRouter pricing changes frequently. Need dynamic pricing lookup:
   ```python
   async def get_current_pricing(self, model_id: str) -> ModelPricing:
       response = await self.client.get("https://openrouter.ai/api/v1/models")
       model_data = next(m for m in response.json()["data"] if m["id"] == model_id)
       return ModelPricing(
           prompt_per_1k=model_data["pricing"]["prompt"],
           completion_per_1k=model_data["pricing"]["completion"]
       )
   ```

2. **Token Count Estimation Inaccurate**: Cost depends on tokens, but estimation doesn't use tokenizer:
   ```python
   # Naive estimation:
   estimated_tokens = len(prompt.prompt_text) / 4

   # Better: Use tiktoken or similar
   import tiktoken
   enc = tiktoken.encoding_for_model("gpt-4")
   estimated_tokens = len(enc.encode(prompt.prompt_text))
   ```

3. **Judge Cost Not Properly Estimated**: Judging prompts include full responses, so cost depends on response length. Current estimates assume fixed costs but actual costs vary significantly.

### 12.2 Simulating Presets

**Issues Identified:**

1. **Preset Model IDs Don't Exist**:
   ```python
   judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
   ```

   These are future/speculative model IDs. Need to make presets reference configurable model aliases, not hardcoded IDs.

2. **Budget Preset May Exceed Budget**: The "budget" preset estimates $15:
   ```python
   estimated_cost=15.00,
   ```

   But if responses are longer than expected or retries happen, actual cost could be 2-3x. Need budget caps:
   ```python
   max_budget=20.00,  # Hard cap
   budget_warning_threshold=0.8,  # Warn at 80%
   ```

3. **Time Estimates Assume Parallelism**: The estimates like "60 minutes" assume full parallelization:
   ```python
   estimated_time_minutes=60,
   ```

   But with rate limits, actual time could be much longer. Need:
   ```python
   estimated_time_minutes_parallel=60,
   estimated_time_minutes_sequential=240,
   ```

---

## Summary of Critical Issues

### Blockers (Must Fix Before Implementation)

1. **Combinatorial Explosion in Phase2Combiner**: Can't enumerate 4.5 billion combinations
2. **companies.json Doesn't Exist**: No real company data provided
3. **Model IDs Are Speculative**: Future model IDs won't work
4. **aiofiles Not in Dependencies**: CheckpointManager will fail
5. **BLS Matrix Data Source Unknown**: NAICS mapping fallback needed

### High Priority (Significant Impact)

1. **Best-of-5 Not Actually Implemented**: Plan says best-of-5 but code has 2 votes per judge
2. **60 Judge Calls Per Comparison**: Cost prohibitive if actually implementing best-of-5
3. **Many Helper Methods Undefined**: ~15 methods called but not shown
4. **Async/Sync Mismatches**: Multiple methods incorrectly mix async patterns
5. **Stratification Impractical**: 8 dimensions with 9.5M strata

### Medium Priority (Functional Issues)

1. **Schema Validation Incomplete**: Missing columns and element verification
2. **Name Pools Too Small**: High repetition for large evaluations
3. **JSON Parsing Edge Cases**: Nested JSON, permissive regex
4. **Thread/Async Safety**: Multiple race conditions possible
5. **Cost Estimation Stale**: Hardcoded pricing will drift

### Low Priority (Polish/Optimization)

1. **Regex Not Pre-compiled**: Performance impact on large task sets
2. **scipy Import at Call Time**: Minor latency
3. **Template Files Missing**: Need HTML/CSS for reports
4. **Progress UI Not Fully Connected**: Some display issues

---

## Recommended Implementation Order

Based on dependencies and critical path:

1. **Week 1: Fix Blockers**
   - Create companies.json (curate 500+ companies)
   - Implement lazy combination generation
   - Add aiofiles dependency
   - Create model alias system for future model IDs

2. **Week 2: Core Data Pipeline**
   - Verify O*NET schema against actual database
   - Complete NAICS mapping with fallbacks
   - Expand name pools (100+ per category)
   - Add email generation to PersonName

3. **Week 3-4: API Layer**
   - Implement OpenRouterClient fully
   - Add proper error classification
   - Implement rate limiter with per-provider limits
   - Add timeout handling

4. **Week 5-6: Judging System**
   - Decide on actual voting strategy (not 60 calls!)
   - Implement all undefined helper methods
   - Fix JSON parsing edge cases
   - Add proper position bias detection

5. **Week 7-8: Analysis & Reporting**
   - Create HTML templates for PDF
   - Implement chart generation with caching
   - Complete weakness finding logic
   - Add statistical significance tests

6. **Week 9-10: TUI & Integration**
   - Fix TUI component connections
   - Add proper state synchronization
   - Integration testing end-to-end
   - Documentation and user guide
