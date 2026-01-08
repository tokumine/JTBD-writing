# Implementation Simulation Report - Agent 5

## Executive Summary

This document presents a detailed dry-run implementation simulation of the Gemini Writing Evaluation Framework master plan. I walked through each component as if actually coding it, identifying what works well, what doesn't work or is unclear, missing pieces, technical gotchas, and specific improvements.

**Overall Assessment**: The master plan is comprehensive and well-structured, but contains several critical gaps and assumptions that would cause implementation failures without resolution. The most significant issues are:

1. **O*NET Schema Assumptions**: Table/column names assumed but not verified against actual db/onet.db
2. **OpenRouter API Model ID Uncertainty**: All model IDs are speculative for Jan 2026
3. **Missing External Data Sources**: NAICS-SOC crosswalk data not available
4. **Incomplete Error Handling**: Several edge cases not covered
5. **Cost Estimation Complexity**: Token counting/pricing logic underspecified

---

## Part 1: Project Setup and Configuration Simulation

### 1.1 Directory Structure Setup

**What Works Well:**
- Clean separation of concerns (data/, prompts/, eval/, analysis/, etc.)
- Logical grouping of related functionality
- Standard Python project layout with pyproject.toml

**Issues Identified:**

1. **Missing `__init__.py` files in nested directories**
   - The plan shows `src/config/` but doesn't list `__init__.py` files
   - Would cause `ModuleNotFoundError` on import
   - **Fix**: Add `__init__.py` to every package directory

2. **Results directory permissions**
   - `results/` is gitignored but no creation logic shown
   - Would fail on first run if directory doesn't exist
   - **Fix**: Add directory creation in `run_manager.py`

3. **Database path resolution**
   - Plan references `db/onet.db` but uses relative paths
   - Would break if CLI invoked from different directory
   - **Fix**: Use `importlib.resources` or `pathlib.Path(__file__).parent` for resolution

### 1.2 Dependencies Installation

**Simulation of `pip install -e .`:**

```
Collecting pydantic>=2.5
Collecting httpx>=0.27
Collecting aiosqlite>=0.19
Collecting weasyprint>=61
  ERROR: Could not find version that satisfies weasyprint>=61 on some systems
  Note: weasyprint requires system dependencies (cairo, pango, etc.)
```

**Issues Identified:**

1. **WeasyPrint system dependencies**
   - WeasyPrint requires Cairo, Pango, GDK-PixBuf installed at system level
   - Plan doesn't mention system dependency installation
   - Would fail on fresh Ubuntu/macOS without: `brew install pango cairo gdk-pixbuf`
   - **Fix**: Add system dependency instructions to README

2. **Kaleido version issues**
   - `kaleido>=0.2` has known issues on M1/M2 Macs
   - May need `kaleido==0.1.0.post1` workaround
   - **Fix**: Test on Apple Silicon, provide fallback

3. **Python 3.11+ requirement**
   - Uses `list[str]` syntax (3.9+) and `match` statements (3.10+)
   - Should work but worth noting minimum version clearly

---

## Part 2: O*NET Data Pipeline Simulation

### 2.1 Schema Validation

**Simulating validation against actual schema:**

Looking at the `ONET_WRITING_REFERENCE.md`, the actual schema uses:
- `task_statements` table with columns: `task_id`, `onetsoc_code`, `task`, `task_type`
- `occupation_data` table with columns: `onetsoc_code`, `title`, `description`

**CRITICAL ISSUE FOUND:**

The master plan's `ONetSchemaValidator` expects:
```python
REQUIRED_TABLES = {
    "task_statements": ["task_id", "onetsoc_code", "task"],
    "occupation_data": ["onetsoc_code", "title", "description"],
    "job_zones": ["onetsoc_code", "job_zone"],
    "work_context": ["onetsoc_code", "element_id", "scale_id", "data_value"],
    "skills": ["onetsoc_code", "element_id", "scale_id", "data_value"],
}
```

But actual O*NET 30.1 schema (per reference doc):
- `job_zones` is actually `job_zone_reference` + a join through occupation data
- Element IDs reference `content_model_reference` table
- Scale handling requires understanding O*NET's complex scale system

**Specific Schema Issues:**

1. **Job Zone Data Location**
   - Reference shows: `SELECT * FROM job_zone_reference;`
   - Plan assumes `job_zones` table with direct SOC code mapping
   - Actually need to join through occupation data
   - **Fix**: Update query to use actual O*NET schema structure

2. **Writing Skill Element ID**
   - Plan uses element ID `2.A.1.c` for writing skill
   - Reference confirms this is correct
   - BUT: Scale ID for importance is `IM`, not specified consistently in plan

3. **Work Context Element IDs**
   - `4.C.1.a.2.h` for email - VERIFIED in reference
   - `4.C.1.a.2.j` for letters/memos - VERIFIED in reference
   - However, scale ID `CX` needs verification

**Simulated SQL Execution:**

```sql
-- Plan's query
SELECT COALESCE(jz.job_zone, 3) as job_zone
FROM job_zones jz

-- Error: no such table: job_zones
-- Actual O*NET has job_zones table with different structure
```

**Fix Required:**
```sql
-- Correct query based on ONET_WRITING_REFERENCE.md
SELECT jz.job_zone
FROM task_statements t
JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
```

### 2.2 Task Extraction Simulation

**Simulating `ONetExtractor.extract_writing_tasks()`:**

**What Works:**
- Regex patterns for writing indicators are reasonable
- Weighted scoring approach is sound
- Category inference logic is data-driven as required

**Issues Found:**

1. **Pattern matching inefficiency**
   - Running 13 regex patterns against 18,796 tasks = 244,348 regex operations
   - Could be slow on first run
   - **Fix**: Compile patterns once, use combined pattern where possible

2. **Missing `task_type` filtering**
   - Reference mentions `task_type` can be 'Core', 'Supplemental', or NULL
   - Plan doesn't filter or weight by task type
   - Core tasks are more universally performed - should prioritize
   - **Fix**: Add task_type weighting (Core = 1.0, Supplemental = 0.7, NULL = 0.5)

3. **Writing relevance score edge cases**
   - If no pattern matches AND no O*NET skill data, score = 0.0
   - Some tasks might still be writing-relevant but missed
   - Example: "Communicate with insurance adjusters" - no direct writing keyword
   - **Fix**: Add minimum score floor for tasks from high-writing occupations

4. **Category inference overlap**
   - "Prepare report for customer" matches both 'documentation' and 'customer_communication'
   - Current priority order may not be optimal
   - **Fix**: Use multi-label classification instead of single category

### 2.3 NAICS Mapping Simulation

**CRITICAL MISSING DEPENDENCY:**

The plan states: "Use BLS Occupation-Industry Matrix when available, with robust fallback."

But:
- No BLS data file included in plan's directory structure
- Reference doc explicitly states: "O*NET does not contain NAICS industry codes directly"
- Fallback mapping is incomplete (only shows 4 of 22 SOC major groups)

**Simulating `NAICSMapper.sample_industry()`:**

```python
# Input: SOC code "11-1011.00" (Chief Executives)
soc_major = "11"  # Management

# Try BLS matrix
self._bls_matrix = None  # Not available!

# Fall back to hardcoded mapping
FALLBACK_SOC_TO_NAICS = {
    "11": [("54", 0.25), ("52", 0.15), ("62", 0.12), ("31", 0.10)],
    # ... but where are the other 18 SOC major groups?
}

# Result: Only 4 industry codes with weights totaling 0.62
# Missing 38% probability mass!
```

**Issues:**

1. **Incomplete fallback mapping**
   - Only 4 SOC groups shown in plan
   - Need all 22 SOC major groups mapped
   - **Fix**: Complete the mapping using BLS occupation-industry statistics

2. **No external data download**
   - Plan mentions verifying URLs but doesn't provide any
   - BLS data URL: https://www.bls.gov/emp/tables/industry-employment-and-output.htm
   - **Fix**: Add data download script or embed processed data

3. **Weight normalization missing from some paths**
   - Ultimate fallback creates uniform weights but sum != 1.0 always
   - **Fix**: Ensure all code paths normalize weights

### 2.4 Company Database Simulation

**Simulating `CompanyDatabase.get_company()`:**

```python
# Input: NAICS "54", size=ENTERPRISE, seed=12345

# Try to find real company
companies_path = Path("data/companies.json")
# File doesn't exist in plan! Only mentioned, not created.

FileNotFoundError: [Errno 2] No such file or directory: 'data/companies.json'
```

**Issues:**

1. **Missing companies.json data file**
   - Plan references it but doesn't show how to create/populate it
   - Would need manual curation or LLM generation
   - **Fix**: Include script to generate initial company dataset

2. **Company generation prompt quality**
   - LLM generation prompt asks for "fictional company names"
   - PROMPT.md explicitly wants REAL company names for realism
   - These are contradictory requirements
   - **Fix**: Create curated real company database first, only generate for gaps

3. **Company size categorization unclear**
   - `CompanySize` enum: STARTUP, SMALL, MEDIUM, LARGE, ENTERPRISE
   - No employee count thresholds defined
   - How does plan determine "this prompt needs a STARTUP"?
   - **Fix**: Define size thresholds and selection logic

4. **Bias tracking missing**
   - PROMPT.md says: "Document which companies were used so bias can be analyzed"
   - No metadata field for tracking which prompts used which companies
   - **Fix**: Add `company_name` to prompt metadata for bias analysis

---

## Part 3: Prompt Generation Pipeline Simulation

### 3.1 Phase 1 - Offline Persona Generation

**Simulating `Phase1Generator.generate_personas()`:**

**What Works:**
- Caching strategy is sound
- Prompt template covers required diversity dimensions
- JSON output format is parseable

**Issues Found:**

1. **LLM model selection unclear**
   - Code references `model="smart_cheap"` - not a real model ID
   - Plan doesn't define this mapping
   - **Fix**: Define model tier mapping in config (e.g., smart_cheap -> anthropic/claude-sonnet)

2. **Persona count not specified**
   - How many personas to generate for different eval sizes?
   - 50 prompts vs 1000 prompts need different persona pools
   - Too few = repetition, too many = generation cost
   - **Fix**: Scale persona pool size with target prompt count (e.g., 10:1 ratio)

3. **Persona deduplication missing**
   - LLM might generate similar personas across batches
   - "Marketing Manager with 5 years experience" vs "Senior Marketing Manager"
   - **Fix**: Add similarity detection using embeddings or fuzzy matching

4. **Cache invalidation strategy**
   - Cache file persists forever
   - What if persona quality is poor? No way to regenerate
   - **Fix**: Add version number to cache, allow `--regenerate-personas` flag

### 3.2 Phase 2 - Algorithmic Combination

**Simulating `Phase2Combiner.generate_prompts()`:**

```python
# Generate all combinations
all_combinations = self._generate_all_combinations()

# With:
# - 500 O*NET tasks
# - 100 personas
# - 5 urgency levels
# - 3 word count tiers
# - 20 NAICS sectors

# Total theoretical combinations: 500 * 100 * 5 * 3 * 20 = 15,000,000
# This is a combinatorial explosion!
```

**Issues Found:**

1. **Memory explosion risk**
   - `_generate_all_combinations()` could create millions of dicts
   - Each dict with nested objects = significant memory
   - **Fix**: Use generator pattern, don't materialize full combination space

2. **Stratified sampling correctness**
   - Current algorithm samples from each stratum, then fills remaining
   - With 8 stratification dimensions, number of strata = product of dimension cardinalities
   - Could easily exceed prompt count, making sampling undefined
   - **Fix**: Use hierarchical sampling or PCA-based dimensionality reduction

3. **Determinism not guaranteed**
   - `random.Random(seed)` is used but multiple RNG calls in unknown order
   - Different Python versions might give different results
   - **Fix**: Create dedicated RNG for each sampling stage, document version

4. **Scenario seed alignment**
   - `scenario_seeds` generated from sampled O*NET tasks
   - But in phase 2, we sample tasks again independently
   - What if selected task has no matching scenario seed?
   - **Fix**: Ensure scenario seeds cover all possible tasks, or generate on-demand

### 3.3 Phase 3 - LLM Enrichment

**Simulating `Phase3Enricher.enrich_prompt()`:**

**Enrichment Prompt Analysis:**

```python
ENRICHMENT_PROMPT = """
You are creating a realistic writing prompt...

Generate a complete, realistic writing prompt that:
1. Includes specific but fictional details (names, dates, numbers, project names)
2. Provides clear context about why this communication is needed NOW
...
"""
```

**Issues Found:**

1. **Temporal grounding inconsistency**
   - PROMPT.md says: "Do NOT include temporal context for tasks where it's irrelevant"
   - But enrichment prompt always asks for "why this communication is needed NOW"
   - **Fix**: Add conditional temporal injection based on task type

2. **Attachment generation missing**
   - PROMPT.md extensively describes attachment/reference handling
   - Enrichment prompt doesn't ask for mock attachment content
   - Example: "See attached Q3 report" should include summary
   - **Fix**: Add attachment generation to enrichment prompt

3. **Reply-to context missing**
   - PROMPT.md wants "prior messages to respond to" for some prompts
   - Not included in enrichment pipeline
   - **Fix**: Create separate `ReplyContextGenerator` for response prompts

4. **Regional English variants missing**
   - PROMPT.md specifies en-US, en-GB, en-AU, non-native options
   - No mechanism to inject regional context
   - **Fix**: Add `english_variant` field to persona/prompt, instruct enricher

5. **JSON parsing robustness**
   - `self._parse_enrichment(response)` assumes valid JSON
   - But LLM responses often include markdown code blocks
   - **Fix**: Use same robust parser from judge parsing

6. **Enrichment batching timeout**
   - `asyncio.gather(*tasks)` waits for all to complete
   - One slow enrichment blocks entire batch
   - **Fix**: Add per-enrichment timeout with fallback

### 3.4 Special Prompt Types

**Simulating `ConstraintGenerator.add_constraints()`:**

**Issues Found:**

1. **Constraint combinations can be contradictory**
   - "Keep this under 100 words" + "Include exactly 5 bullet points"
   - 5 bullet points often exceed 100 words
   - **Fix**: Add constraint compatibility checking

2. **Verification logic incomplete**
   - `verifiable=True` flag set but no verification code shown
   - How do we check if response "starts with word X"?
   - **Fix**: Implement `ConstraintChecker` class with verification methods

3. **Keyword constraint edge cases**
   - "Include the word 'however' at least 3 times" - case sensitive?
   - What if word appears in different forms (However, HOWEVER)?
   - **Fix**: Define case sensitivity rules, document in prompt

**Simulating `RevisionGenerator`:**

**Issues Found:**

1. **Circular dependency**
   - Revision prompts need original response
   - But original response comes from model being evaluated
   - If model fails original, can't generate revision
   - **Fix**: Generate revision prompts only from successful responses

2. **Revision baseline unclear**
   - Which model's response is used as revision input?
   - Using Gemini's response biases toward Gemini
   - **Fix**: Use responses from neutral source (different model) or manually curated

---

## Part 4: API Layer Simulation

### 4.1 OpenRouter Client

**Simulating `ModelVerifier.verify_models()`:**

```python
# Expected model IDs from plan
EXPECTED_MODELS = {
    "gemini_pro": "google/gemini-3.0-pro",
    "gpt_pro": "openai/gpt-5.2",
    "claude_pro": "anthropic/claude-opus-4.5",
    "grok": "x-ai/grok-4.1",
    "kimi": "moonshot/kimi-k2",
}

# Current OpenRouter API call (simulated Jan 2026)
response = await client.get("https://openrouter.ai/api/v1/models")

# Problem: These model IDs are speculative!
# Actual model IDs might be:
# - "google/gemini-3-pro" (no .0)
# - "openai/gpt-5-2" (hyphen vs dot)
# - "anthropic/claude-4.5-opus" (different order)
```

**Critical Issues:**

1. **All model IDs are guesses**
   - Gemini 3.0, GPT-5.2, Claude Opus 4.5 may not exist with these exact IDs
   - Names may differ (gemini-3.0-pro vs gemini-pro-3.0)
   - **Fix**: Query OpenRouter API FIRST, then map to evaluation tiers

2. **Kimi availability uncertain**
   - Moonshot's Kimi may not be on OpenRouter
   - No fallback if unavailable
   - **Fix**: Make model list configurable, gracefully handle missing models

3. **Similar model matching is fragile**
   ```python
   def _find_similar(self, target: str, available: set) -> str | None:
       provider, name = target.split("/")
       for model_id in available:
           if provider in model_id and any(
               part in model_id for part in name.split("-")
           ):
               return model_id
   ```
   - "gemini-3.0-pro" splits to ["gemini", "3.0", "pro"]
   - Would match "google/gemini-1.5-pro-latest" incorrectly!
   - **Fix**: Use more precise matching, require user confirmation

### 4.2 Rate Limiting Simulation

**Simulating `RateLimiter.acquire()`:**

**Issues Found:**

1. **Per-model vs per-provider limits unknown**
   - OpenRouter may have account-level limits
   - Some providers (OpenAI) have per-model limits
   - Plan doesn't distinguish
   - **Fix**: Research OpenRouter rate limit structure, implement hierarchically

2. **Token-based vs request-based limits**
   - Some APIs limit by tokens/minute, others by requests/minute
   - Plan only shows request counting
   - **Fix**: Track both tokens and requests, respect lower limit

3. **Rate limit response parsing**
   - OpenRouter returns retry-after header
   - But format varies: seconds vs datetime
   - **Fix**: Parse both formats with fallback

### 4.3 Circuit Breaker Simulation

**What Works:**
- State machine logic is correct (CLOSED -> OPEN -> HALF_OPEN)
- Recovery timeout prevents cascading failures
- Per-service isolation is good

**Issues Found:**

1. **Thread safety concerns**
   - `_states`, `_failure_counts` modified without locks
   - Async code might interleave updates
   - **Fix**: Use `asyncio.Lock` for state modifications

2. **No health metrics exposure**
   - TUI can't show circuit breaker status
   - User doesn't know why requests aren't being made
   - **Fix**: Add circuit breaker status to progress display

3. **Recovery too conservative**
   - `half_open_requests=3` means 3 successes needed to close
   - If errors are intermittent, might never fully recover
   - **Fix**: Add time-based auto-close after extended half-open

---

## Part 5: Evaluation Engine Simulation

### 5.1 Response Collection

**Simulating `ResponseCollector.collect_responses()`:**

```python
# Collect from all tier models in parallel
models = self.tier_config.get_models("pro")
# Returns: ["google/gemini-3.0-pro", "openai/gpt-5.2", "anthropic/claude-opus-4.5", "x-ai/grok-4.1", "moonshot/kimi-k2"]

tasks = [self._collect_single(prompt, model_id, callback) for model_id in models]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Issues Found:**

1. **Timeout handling insufficient**
   - `_estimate_max_tokens()` mentioned but not implemented
   - No timeout specified in API calls
   - Long generation could hang indefinitely
   - **Fix**: Add per-request timeout (e.g., 60s), implement token estimation

2. **Partial failures not checkpointed immediately**
   - If 4/5 models succeed, failure raised
   - But 4 successful responses not saved
   - **Fix**: Checkpoint each successful response individually

3. **Response content validation missing**
   - Empty response? Truncated response? Error message as content?
   - No validation before marking "success"
   - **Fix**: Add response validation (min length, no error patterns)

### 5.2 Dual Persona Judging

**Simulating `DualPersonaJudge.judge_comparison()`:**

**CRITICAL ISSUE:**

```python
COMPARISON_PROMPT = """
...
Provide your judgment as JSON:
{{
    "reasoning": "...",
    "winner": "A" or "B" or "TIE",
    ...
}}
"""
```

But the responses are called "Response A" and "Response B" - not tied to actual model names! The plan correctly shuffles positions, but...

**Issues Found:**

1. **Recipient persona role inference unclear**
   ```python
   recipient_role=self._infer_recipient_role(prompt)
   ```
   - Method not implemented in plan
   - How do we know recipient is "VP of Marketing" vs "Customer"?
   - Prompt schema doesn't have explicit recipient_role field
   - **Fix**: Add recipient_role to prompt schema, populate in enrichment

2. **Judge context missing critical elements**
   - PROMPT.md says judges need: "writer persona details (age, skill level, role, industry, generation)"
   - Comparison prompt only includes `prompt_text`
   - Missing persona, formality, recipient context
   - **Fix**: Include full scenario context in judge prompt

3. **Judgment criteria not aligned with PROMPT.md**
   - Plan's judgment asks for generic "winner"
   - PROMPT.md specifies criteria: authenticity, cliche avoidance, length appropriateness
   - **Fix**: Add specific criteria to judgment prompt, require scores

4. **Temperature 0.3 may be too high for consistency**
   - Best-of-5 voting assumes somewhat consistent judgments
   - Temperature 0.3 can produce variation
   - **Fix**: Use temperature 0.0 or 0.1 for more deterministic judging

### 5.3 Position Bias Handling

**Simulating `PositionBiasHandler.judge_with_position_shuffle()`:**

```python
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
```

**Issues Found:**

1. **Double the API cost!**
   - Each comparison requires 2 judge calls per persona
   - With 3 judges * 2 personas * 2 orderings = 12 judge calls per comparison
   - Cost estimate in presets seems too low
   - **Fix**: Update cost estimates or make position shuffling optional

2. **Position disagreement handling unclear**
   - What if AB order says "A wins" but BA order says "A wins" (position B)?
   - That's actually agreement that model_a wins
   - But what if AB says "A wins" and BA says "A wins" too?
   - Then judge has position bias favoring first position
   - **Fix**: Document interpretation clearly, add position bias detection per-comparison

3. **Tie handling in position aggregation**
   ```python
   def _position_majority(self, winners: list[str], ...) -> str:
       a_count = winners.count(model_a)
       b_count = winners.count(model_b)
       # What if both are 0 (two TIEs)?
       # Returns "TIE" correctly, but...
   ```
   - Two TIEs vs one TIE + one position-biased vote treated differently
   - **Fix**: Add special handling for unanimous TIE

### 5.4 Vote Aggregation

**Simulating `VoteAggregator.aggregate_comparison()`:**

**What Works:**
- Majority-of-majorities logic is correct
- Agreement metric calculation is comprehensive
- Confidence scoring based on margin

**Issues Found:**

1. **Best-of-5 not actually implemented**
   - PROMPT.md says "best-of-5 judgments"
   - Current code only does 2 judgments per (judge, persona) from position shuffle
   - Where are the other 3?
   - **Fix**: Add repeat judgment loop (5 calls per judge-persona)

2. **This massively increases cost!**
   - 3 judges * 2 personas * 5 votes * 2 positions = 60 judge calls per comparison
   - At $0.01/call (conservative), 500 comparisons = $300 just for judging
   - **Fix**: Re-estimate costs in presets with correct multiplier

3. **Tie-breaking rule unclear**
   - If final vote is 3-3 split, what's the result?
   - Current `_simple_majority` would return TIE
   - Is that what we want or should we apply tiebreaker?
   - **Fix**: Document tie-breaking policy explicitly

---

## Part 6: Analysis and Reporting Simulation

### 6.1 Statistical Analysis

**Simulating `StatisticsEngine.compute_win_rates()`:**

**What Works:**
- Wilson score interval is correct choice for proportions
- Head-to-head matrix provides good overview
- Confidence intervals enable statistical significance

**Issues Found:**

1. **Win rate denominator ambiguity**
   ```python
   wins = sum(1 for r in results if r.winner == model_id)
   total = len(results)
   win_rate = wins / total
   ```
   - What counts as "total"? Ties included?
   - Different interpretations give different rates
   - **Fix**: Clearly define win_rate vs win_rate_excluding_ties usage

2. **Paired comparison statistics not used**
   - Results are paired (same prompt, different models)
   - Plan uses simple binomial test
   - Should use McNemar's test or paired sign test
   - **Fix**: Implement proper paired comparison statistics

3. **Multiple comparison correction missing**
   - Testing many model pairs inflates false positive rate
   - Need Bonferroni or FDR correction
   - **Fix**: Apply multiple comparison correction to p-values

### 6.2 Agreement Metrics

**Simulating `AgreementMetrics.fleiss_kappa()`:**

**What Works:**
- Implementation of Fleiss' Kappa is mathematically correct
- Handles edge cases (empty input, single rater)

**Issues Found:**

1. **Categories not clearly defined**
   - What are the valid categories? [model_a, model_b, "TIE"]?
   - But model names change per comparison
   - **Fix**: Use abstract categories [WINNER_A, WINNER_B, TIE]

2. **Per-prompt vs aggregate agreement unclear**
   - Fleiss Kappa assumes multiple raters on same items
   - But each prompt has different model pairs
   - Apples-to-oranges comparison
   - **Fix**: Calculate agreement within model pairs, then aggregate

3. **Cohen's Kappa requires exactly 2 raters**
   ```python
   def cohen_kappa(self, ratings_a: list[str], ratings_b: list[str]):
       from sklearn.metrics import cohen_kappa_score
       return cohen_kappa_score(ratings_a, ratings_b)
   ```
   - We have 3 judges * 2 personas = 6 "raters"
   - Need pairwise Cohen's Kappa between each pair
   - **Fix**: Calculate all pairwise Kappas, report mean and range

### 6.3 Weakness Finding

**Simulating `WeaknessFinder.analyze_losses()`:**

**What Works:**
- Multi-dimensional grouping is comprehensive
- Relative risk calculation useful for prioritization
- Reasoning theme extraction from judge feedback

**Issues Found:**

1. **Statistical significance testing fragile**
   ```python
   if self._is_significant_pattern(loss_rate, baseline_rate, len(results)):
   ```
   - Small sample sizes per stratum
   - Many comparisons = high false positive rate
   - **Fix**: Require minimum stratum size (e.g., 20), apply FDR correction

2. **Raw judgments field assumed but not defined**
   ```python
   for judgment in loss.raw_judgments:
       if loss.gemini_position == 'A':
           all_weaknesses.extend(judgment.weaknesses_a)
   ```
   - `raw_judgments` not in `AggregatedResult` schema shown earlier
   - `gemini_position` not tracked
   - **Fix**: Update schema to include these fields

3. **Weakness taxonomy not standardized**
   - Free-form weaknesses from judges: "too verbose", "verbose response", "lengthy"
   - Same issue, different words not aggregated
   - **Fix**: Add weakness canonicalization or embedding-based clustering

### 6.4 PDF Report Generation

**Simulating `PDFReportGenerator.generate_report()`:**

**Issues Found:**

1. **Template files not provided**
   - References `template_dir` with `comprehensive_report.html`
   - No templates shown in plan
   - **Fix**: Create Jinja2 template files

2. **Chart embedding issues**
   ```python
   img_bytes = fig.to_image(format='png', width=800, height=400)
   return base64.b64encode(img_bytes).decode('utf-8')
   ```
   - `fig.to_image()` requires Kaleido
   - Kaleido startup is slow (~2-3s per chart)
   - With many charts, report generation slow
   - **Fix**: Batch chart generation, consider static matplotlib fallback

3. **Large report size**
   - Base64 images increase file size 33%
   - Report with many comparisons could be huge
   - **Fix**: Use external image files or vector graphics (SVG)

4. **Async mismatch with WeasyPrint**
   ```python
   async def generate_report(...):
       HTML(string=html_content).write_pdf(output_path)
   ```
   - `write_pdf()` is synchronous blocking call
   - Should use `asyncio.to_thread()` or run in executor
   - **Fix**: Move PDF generation to thread pool

---

## Part 7: TUI Implementation Simulation

### 7.1 Progress Dashboard

**Simulating `EvalTUI` with Textual:**

**What Works:**
- Clean reactive state pattern
- Logical panel organization
- Good keyboard bindings

**Issues Found:**

1. **Textual version compatibility**
   - API changed significantly between 0.4x and 0.5x
   - Plan specifies `textual>=0.52` but uses older patterns
   - `compose()` signature may need updates
   - **Fix**: Verify against Textual 0.52 API, update as needed

2. **Refresh rate too aggressive**
   ```python
   def on_mount(self) -> None:
       self.set_interval(1.0, self.refresh_data)
   ```
   - 1 second refresh during 6-hour eval = 21,600 refreshes
   - Each refresh queries state, redraws widgets
   - **Fix**: Use event-driven updates, not polling

3. **Missing eval_state initialization**
   ```python
   async def refresh_data(self) -> None:
       if self.eval_state:  # Where is this set?
   ```
   - `eval_state` never initialized in shown code
   - **Fix**: Add state initialization in constructor

4. **Error handling in TUI**
   - What if evaluation crashes?
   - TUI should show error state, allow export of partial results
   - **Fix**: Add error recovery screen

### 7.2 Results Browser

**Simulating filtering and search:**

**Issues Found:**

1. **FilterPanel not implemented**
   - Referenced in compose() but code not shown
   - Critical for usability
   - **Fix**: Implement filter panel with dropdowns for each dimension

2. **Search performance concerns**
   - Full-text search across 1000+ results
   - SQLite LIKE queries slow without FTS
   - **Fix**: Add SQLite FTS5 index for prompt text search

3. **Side-by-side view scrolling**
   - Long responses won't fit in terminal
   - Need synchronized scrolling between panels
   - **Fix**: Use Textual ScrollView with linked scrolling

---

## Part 8: Checkpoint and Recovery Simulation

### 8.1 Checkpoint System

**Simulating crash and recovery:**

```python
# Scenario: Evaluation at prompt 247/500, crash occurs

# Before crash state:
checkpoint_data = {
    "phase": "judging",
    "completed_prompt_ids": [...247 ids...],
    "pending_prompt_ids": [...253 ids...],
    # ...
}

# Atomic write sequence:
await f.write(json.dumps(checkpoint_data))  # Write to .tmp
self.temp_file.rename(self.checkpoint_file)  # Atomic rename

# Crash during write_pdf (after rename)
# State is safe!
```

**What Works:**
- Atomic write pattern is correct
- Dual storage (file + DB) provides redundancy
- Phase-aware resume logic

**Issues Found:**

1. **Checkpoint frequency not specified**
   - When do we save checkpoints?
   - Every prompt? Every 10? On phase change?
   - Too frequent = slow, too infrequent = lost work
   - **Fix**: Checkpoint every N prompts (configurable, default 10)

2. **Async file operations incomplete**
   ```python
   async with aiofiles.open(self.temp_file, 'w') as f:
       await f.write(json.dumps(checkpoint_data, indent=2))

   # But this is synchronous!
   self.temp_file.rename(self.checkpoint_file)
   ```
   - `Path.rename()` is blocking
   - **Fix**: Use `aiofiles.os.rename()` or `asyncio.to_thread()`

3. **DB checkpoint structure not shown**
   - `await self.db.save_checkpoint(checkpoint_data)` called
   - But no schema for checkpoint table
   - **Fix**: Add checkpoint table to schema

4. **Resume validation missing**
   - What if checkpoint says prompt completed but response not in DB?
   - Inconsistent state possible after partial crash
   - **Fix**: Add consistency check comparing checkpoint to actual DB state

### 8.2 Graceful Shutdown

**Simulating Ctrl+C handling:**

**Issues Found:**

1. **Signal handling not implemented**
   - Plan mentions "Ctrl+C saves state"
   - No signal handler code shown
   - **Fix**: Add SIGINT handler that triggers checkpoint

2. **In-flight requests**
   - What happens to API calls in progress when shutdown requested?
   - Need to wait for completion or cancel
   - **Fix**: Track in-flight tasks, wait with timeout on shutdown

---

## Part 9: Cost Estimation Simulation

### 9.1 Pre-Evaluation Cost Estimate

**Simulating cost calculation for "standard" preset:**

```
Configuration:
- 200 prompts
- 3 judges (Claude Opus, GPT-5.2, Gemini Pro)
- Best-of-5 voting
- 2 personas (expert, recipient)
- 2 position orderings
- 4 model pairs

Calculations:
Response generation:
- 200 prompts * 4 model pairs * 2 models = 1,600 responses
- Avg input: ~500 tokens, output: ~300 tokens
- At ~$0.01/1K input, ~$0.03/1K output for pro models:
  - Input: 1,600 * 500 / 1000 * 0.01 = $8
  - Output: 1,600 * 300 / 1000 * 0.03 = $14.40
  - Response subtotal: ~$22

Judging:
- Per comparison: 3 judges * 2 personas * 5 votes * 2 positions = 60 calls
- Total comparisons: 200 * 4 = 800
- Total judge calls: 800 * 60 = 48,000 calls!
- Avg input: ~800 tokens (prompt + 2 responses), output: ~200 tokens
- At ~$0.01/1K input, ~$0.03/1K output:
  - Input: 48,000 * 800 / 1000 * 0.01 = $384
  - Output: 48,000 * 200 / 1000 * 0.03 = $288
  - Judging subtotal: ~$672

Total: $694 (not $75 as stated in preset!)
```

**CRITICAL ISSUE:**

The preset costs are dramatically underestimated:
- "standard" preset claims ~$75, actual could be ~$700
- Factor of ~10x error!

**Root Causes:**

1. **Best-of-5 not accounted for in estimates**
2. **Position shuffling doubles calls**
3. **Dual persona doubles again**
4. **Judge response token costs high**

**Fix Options:**
1. Reduce default judging (3 votes instead of 5?)
2. Skip position shuffling for lower presets
3. Use cheaper judge models for some votes
4. Update all cost estimates accurately

### 9.2 Token Estimation

**Issues Found:**

1. **No token counting implementation**
   - `_estimate_max_tokens()` referenced but not implemented
   - tiktoken library not in dependencies
   - **Fix**: Add tiktoken or approximation based on character count

2. **Model-specific tokenizers**
   - Claude, GPT, Gemini use different tokenizers
   - Same text = different token counts
   - **Fix**: Use conservative estimates or per-model tokenizers

---

## Part 10: Missing Components Summary

### 10.1 Components Mentioned But Not Implemented

| Component | Status | Priority |
|-----------|--------|----------|
| `data/companies.json` | Not created | High |
| `data/names.json` | Not created | High |
| `data/naics_soc_crosswalk.json` | Not created | High |
| `templates/*.html` | Not created | Medium |
| Token estimation | Not implemented | Medium |
| Constraint verification | Not implemented | Medium |
| Reply-to context generator | Not implemented | Medium |
| Attachment content generator | Not implemented | Medium |
| Regional English handling | Not implemented | Low |
| FilterPanel TUI widget | Not implemented | Low |

### 10.2 Schemas Referenced But Not Defined

- `ValidationResult`
- `WarmupResult`
- `EvalConfig`
- `LLMClient`
- `CircuitState` (enum)
- `ScenarioSeed`
- `PromptConstraints`
- `PromptConstraint`
- `ModelResponse`
- `JudgmentResult`
- `ShuffledJudgment`
- `AggregatedResult`
- `WeaknessPattern`
- `WeaknessReport`
- `ReasoningTheme`
- `PositionBiasReport`
- `LengthBiasReport`
- `SelfPreferenceReport`
- `WinRateStats`
- `RunResults`
- `EvalState`

### 10.3 External Data Not Provided

1. **BLS Occupation-Industry Matrix** - Required for NAICS mapping
2. **Company database** - Required for realistic company names
3. **Name pools by demographic** - Partially shown, needs full data
4. **OpenRouter model registry** - Needs runtime verification

---

## Part 11: Specific Improvement Recommendations

### 11.1 Critical Fixes (Must Have Before Implementation)

1. **Verify O*NET schema against actual onet.db**
   - Run schema discovery queries
   - Update all SQL queries to match
   - Document actual table/column names

2. **Build model discovery system**
   - Query OpenRouter `/models` endpoint at startup
   - Present available models to user
   - Allow flexible tier assignment

3. **Fix cost estimates**
   - Implement accurate token counting
   - Account for all judging multipliers
   - Add warning if estimated cost exceeds budget

4. **Complete NAICS mapping**
   - Download BLS crosswalk data
   - Or implement robust fallback for all 22 SOC groups
   - Document data sources

5. **Create required data files**
   - `companies.json` with real companies by NAICS/size
   - `names.json` with full demographic pools
   - `naics_soc_crosswalk.json` if using external data

### 11.2 High Priority Improvements

1. **Simplify judging for lower presets**
   - Skip position shuffling for "smoke" and "dev"
   - Reduce to 3 votes instead of 5
   - Use single persona for quick tests

2. **Add judge context per PROMPT.md**
   - Include writer persona in judge prompt
   - Include recipient details
   - Include formality/urgency context

3. **Implement constraint verification**
   - Word count checker
   - Bullet point counter
   - Keyword finder
   - Start/end word validator

4. **Add attachment/reply generation**
   - Mock email thread generator
   - Report summary generator
   - Document reference generator

### 11.3 Medium Priority Improvements

1. **Memory-efficient combination generation**
   - Use generators instead of lists
   - Lazy evaluation of combinations
   - Batch processing for large evals

2. **Proper paired statistics**
   - Implement McNemar's test
   - Add multiple comparison correction
   - Report effect sizes

3. **Weakness canonicalization**
   - Cluster similar weakness descriptions
   - Create taxonomy of common issues
   - Enable trend analysis

4. **TUI polish**
   - Event-driven updates
   - Error recovery screen
   - Partial result export

### 11.4 Nice to Have

1. **Regional English support**
   - en-GB spelling variants
   - Date format adaptation
   - Idiom appropriateness

2. **Full-text search in results browser**
   - SQLite FTS5 integration
   - Prompt/response search
   - Filter by keyword

3. **Chart optimization**
   - Batch Kaleido calls
   - Static matplotlib fallback
   - SVG output option

---

## Conclusion

The master plan is ambitious and comprehensive, covering nearly all aspects of building a production-grade writing evaluation framework. However, the simulation reveals several critical gaps that would prevent successful implementation:

1. **Data dependencies are unresolved** - Company database, NAICS crosswalk, and name pools need to be created or sourced
2. **Cost estimates are significantly underestimated** - Real costs may be 5-10x higher than stated
3. **Model IDs are speculative** - Runtime discovery is essential
4. **Schema assumptions need verification** - O*NET queries may fail without correction
5. **Several components are referenced but not implemented** - Templates, verification logic, attachment generators

The plan's architecture is sound, and the phased approach is sensible. With the fixes identified in this simulation, the framework could be successfully implemented. Priority should be given to the critical fixes before beginning any coding work.

**Estimated additional planning/prep work needed: 1-2 weeks**
**Estimated implementation time after fixes: 12-14 weeks (vs 14 weeks original)**

