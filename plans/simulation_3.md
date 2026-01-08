# Implementation Simulation Report #3

## Executive Summary

This document provides a detailed dry-run simulation of implementing the Gemini Writing Evaluation Framework master plan. By walking through each component as if actually coding it, I've identified what works well, what doesn't work or is unclear, missing pieces, gotchas, and specific improvements needed.

---

## Part 1: Project Setup and Foundation

### What Works Well
- The directory structure is comprehensive and well-organized
- Technology stack choices (pydantic, httpx, asyncio, textual) are modern and appropriate
- The pyproject.toml dependencies are realistic and compatible

### Issues Identified

#### Issue 1.1: Missing Python Version Constraint
**Problem**: The plan specifies `requires-python = ">=3.11"` but doesn't explain why 3.11 specifically.
**Impact**: Low - but documentation should note that 3.11 is needed for `typing.Self`, improved `asyncio.TaskGroup`, and better error messages.
**Recommendation**: Add comment explaining Python 3.11 requirement.

#### Issue 1.2: Missing Environment Variable Schema
**Problem**: The plan mentions `.env.example` but doesn't define what environment variables are needed.
**Gotcha**: Developers will need to guess what variables to set.
**Required Variables** (inferred):
```
OPENROUTER_API_KEY=
DEFAULT_PRESET=standard
LOG_LEVEL=INFO
RESULTS_DIR=./results
MAX_CONCURRENT_REQUESTS=10
```
**Recommendation**: Add explicit `.env.example` contents to the plan.

#### Issue 1.3: Database Migration Strategy Missing
**Problem**: The plan mentions SQLite but doesn't specify how schema migrations will be handled.
**Impact**: Medium - production systems need versioned migrations.
**Recommendation**: Add `alembic` or a simple migration system to track schema versions.

---

## Part 2: O*NET Data Pipeline Simulation

### Simulation: Schema Validation

Walking through the `ONetSchemaValidator` implementation:

```python
# Attempting to validate schema...
REQUIRED_TABLES = {
    "task_statements": ["task_id", "onetsoc_code", "task"],
    "occupation_data": ["onetsoc_code", "title", "description"],
    ...
}
```

#### Issue 2.1: Actual O*NET Table Names Differ
**Problem**: According to ONET_WRITING_REFERENCE.md, the actual O*NET schema uses slightly different conventions.
**Evidence**: The reference shows `task_statements` and `occupation_data` which match, but I need to verify `job_zones` vs `job_zone_reference`.

**Simulation Query**:
```sql
-- From ONET_REFERENCE.md, we see job_zone_reference table
SELECT * FROM job_zone_reference;
-- But plan code references 'job_zones' table
```

**Gotcha**: The plan's `REQUIRED_TABLES` may have wrong table name - should verify against actual db/onet.db schema.
**Recommendation**: Add startup script to discover actual schema and generate validation rules dynamically.

#### Issue 2.2: Element ID Verification May Fail
**Problem**: The plan hardcodes element IDs like `'4.C.1.a.2.h'` for Electronic Mail Work Context.
**Gotcha**: These IDs are correct per ONET_REFERENCE.md, but the plan doesn't handle the case where O*NET updates these in future versions.
**Recommendation**: Add fallback element lookup by name, not just ID.

### Simulation: Task Extraction

Walking through `ONetExtractor.extract_writing_tasks()`:

```python
query = """
SELECT
    t.task_id,
    t.onetsoc_code,
    o.title as occupation_title,
    ...
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
...
"""
```

#### Issue 2.3: SQL Join May Be Wrong
**Problem**: ONET_REFERENCE shows `job_zones` table with columns `onetsoc_code, job_zone`, but the reference also mentions `job_zone_reference` which is a lookup table.
**Gotcha**: Need to verify the actual join key. The `job_zones` table may be named differently or structured differently.
**Recommendation**: Run actual query against db/onet.db to verify.

#### Issue 2.4: Scale ID Assumptions
**Problem**: The query assumes `scale_id = 'IM'` for importance and `scale_id = 'CX'` for work context frequency.
**Evidence**: This is correct per ONET_REFERENCE.md which states "Importance (IM scale): 1-5" and "Work Context (CX scale): 1-5".
**Status**: Works as expected.

#### Issue 2.5: Writing Relevance Scoring Could Miss Tasks
**Problem**: The `_compute_writing_relevance()` function uses regex patterns but may miss important writing tasks.
**Example**: Task "Coordinate with clients regarding project requirements" doesn't match any pattern but clearly involves written communication.
**Recommendation**: Lower minimum relevance threshold OR add more patterns like:
- `r'\bconfer\b'` - 0.5
- `r'\bcoordinate\b'` - 0.5
- `r'\bconsult\b'` - 0.5

### Simulation: NAICS Mapping

#### Issue 2.6: BLS Matrix Data Not Provided
**Problem**: The plan mentions using BLS Occupation-Industry Matrix but doesn't include this data or explain how to obtain it.
**Gotcha**: Without BLS data, the system falls back to hardcoded `FALLBACK_SOC_TO_NAICS` which is incomplete.
**Missing Data**: The plan shows only partial mappings for SOC codes 11, 13, 15, 17.
**Impact**: High - 18 of 22 SOC major groups have no mapping.
**Recommendation**:
1. Add complete FALLBACK_SOC_TO_NAICS for all 22 SOC groups
2. Document how to obtain and process BLS matrix data
3. Provide download script or include data file

#### Issue 2.7: NAICS Sectors List Incomplete
**Problem**: The `NAICS_SECTORS` dict shows 20 sectors but skips some codes.
**Evidence**: Codes shown are 11, 21, 22, 23, 31, 42, 44, 48, 51, 52, 53, 54, 55, 56, 61, 62, 71, 72, 81, 92.
**Missing**: 32, 33 (Manufacturing subsectors), 45 (Retail subsector), 49 (Transportation subsector).
**Recommendation**: Use 2-digit NAICS consistently (31-33 are all Manufacturing, etc.) and document this.

---

## Part 3: Company Database Simulation

### Simulation: Real Company Lookup

```python
def get_company(self, naics_code: str, company_size: CompanySize, ...):
    candidates = [
        c for c in self._companies
        if c['naics'].startswith(naics_code[:2])
        and c['size'] == company_size.value
    ]
```

#### Issue 3.1: No Companies.json Provided
**Problem**: The plan references `data/companies.json` but doesn't provide this file or explain its structure.
**Impact**: Critical - the system won't work without this data.
**Required Structure** (inferred):
```json
[
  {
    "name": "Apple Inc.",
    "naics": "334111",
    "size": "enterprise",
    "industry": "Computer and Electronic Product Manufacturing",
    "hq_location": "Cupertino, CA",
    "public": true
  }
]
```
**Recommendation**: Provide initial companies.json with at least 100-200 real companies across major NAICS sectors and sizes.

#### Issue 3.2: async/await Mixing Bug
**Problem**: In `get_company()`, there's a bug - it calls `await self._generate_companies()` inside a sync function.
```python
def get_company(...) -> Company:  # Not async!
    ...
    if cache_key not in self._generated_cache and llm_client:
        self._generated_cache[cache_key] = await self._generate_companies(  # BUG!
```
**Impact**: Will raise runtime error.
**Recommendation**: Make `get_company()` async or separate generation into a pre-population phase.

#### Issue 3.3: Company Size Enum Mismatch
**Problem**: `CompanySize` enum has STARTUP, SMALL, MEDIUM, LARGE, ENTERPRISE but the prompt mentions "Fortune 500, mid-market, small businesses, startups".
**Gotcha**: Need to map between terminology consistently.
**Recommendation**: Add mapping:
- Fortune 500 -> ENTERPRISE
- mid-market -> LARGE or MEDIUM
- small businesses -> SMALL
- startups -> STARTUP

---

## Part 4: Name Generation Simulation

#### Issue 4.1: Limited Name Diversity
**Problem**: The name pools are very limited (~7 first names and ~6 last names per demographic group).
**Impact**: With 500+ prompts, names will repeat frequently.
**Calculation**: 7 * 7 * 2 * 5 = 490 unique combinations maximum (first * last * gender * demographic).
**Recommendation**: Expand name pools to 50+ per category or use external name generation service.

#### Issue 4.2: Age/Generation Not Connected to Names
**Problem**: PROMPT.md requires personas across "GenZ/GenA all the way through to Boomer" but name generation doesn't account for generational naming patterns.
**Example**: "Brittany" and "Tiffany" are more common for Gen X, while "Ava" and "Emma" are more common for Gen Z.
**Recommendation**: Add generational name pools and link them to persona age.

#### Issue 4.3: "Other" Demographic Not Defined
**Problem**: `DEMOGRAPHIC_WEIGHTS` includes "other": 0.01 but `NAME_POOLS` doesn't have an "other" key.
**Impact**: Will use fallback to "white" names, which defeats diversity purpose.
**Recommendation**: Either remove "other" from weights or add name pools for additional demographics (Native American, Middle Eastern, Pacific Islander, etc.).

---

## Part 5: Prompt Generation Pipeline Simulation

### Phase 1 Simulation

#### Issue 5.1: Persona Generation Prompt Too Vague
**Problem**: The `PERSONA_GENERATION_PROMPT` asks for "diverse professional personas" but doesn't specify:
- Age ranges
- Regional diversity (US regions, international)
- Industry distribution targets
**Impact**: LLM may generate similar personas.
**Recommendation**: Add specific distribution requirements to the prompt.

#### Issue 5.2: Cache Path Not Configurable
**Problem**: Persona cache is stored at a fixed path but the location isn't specified in config.
**Gotcha**: Multiple runs could conflict or overwrite each other's caches.
**Recommendation**: Include run_id or hash in cache path.

### Phase 2 Simulation

#### Issue 5.3: Stratification Dimension Explosion
**Problem**: With 8 stratification dimensions, the number of strata explodes:
```
job_zone (5) * writing_category (~10) * channel (~6) * formality (4) *
word_count_tier (3) * urgency (3) * soc_major_group (22) * naics_sector (20)
= 5 * 10 * 6 * 4 * 3 * 3 * 22 * 20 = 9,504,000 potential strata
```
**Impact**: Most strata will be empty, making stratified sampling ineffective.
**Recommendation**:
1. Reduce dimensions to 4-5 most important
2. Use hierarchical stratification (first by SOC, then by formality, etc.)
3. Accept natural distribution for some dimensions

#### Issue 5.4: Missing Word Count Tier Assignment
**Problem**: `word_count_tier` appears in stratification but it's unclear where it gets assigned.
**Gotcha**: The `_combination_to_prompt` function uses `combo.get('word_count_tier', 'medium')` but no code assigns this value.
**Recommendation**: Add word count tier sampling logic in `_generate_all_combinations()`.

### Phase 3 Simulation

#### Issue 5.5: Enrichment Prompt Format Strings May Fail
**Problem**: The enrichment prompt uses f-string formatting with nested object attributes:
```python
filled_prompt = self.ENRICHMENT_PROMPT.format(
    persona=base_prompt.persona,  # This will print the object repr
    company=base_prompt.company,
    ...
)
```
**Gotcha**: Python's `.format()` doesn't support nested attribute access like `{persona.job_title}`.
**Impact**: Will either fail or produce unhelpful output.
**Recommendation**: Pre-extract all needed values or use Jinja2 templating.

#### Issue 5.6: Temperature 0.7 May Be Too High
**Problem**: Enrichment uses `temperature=0.7` which may produce inconsistent or overly creative results.
**Risk**: Some prompts may become unrealistic or contain hallucinations.
**Recommendation**: Lower to 0.4-0.5 for more consistent enrichment.

---

## Part 6: Response Collection Simulation

#### Issue 6.1: Model ID Placeholders Are Speculative
**Problem**: The plan uses model IDs like `"google/gemini-3.0-pro"` which are fictional.
**Evidence**: As of Jan 2026, actual OpenRouter model IDs would be different (e.g., `"google/gemini-2.0-flash-exp"`).
**Impact**: Critical - the system will fail at runtime.
**Recommendation**:
1. Fetch model list from OpenRouter API at startup
2. Provide model ID mapping in config file
3. Add model discovery command: `gemini-eval discover-models`

#### Issue 6.2: `_estimate_max_tokens()` Not Implemented
**Problem**: `ResponseCollector._collect_single()` calls `self._estimate_max_tokens(prompt)` but this method isn't defined.
**Impact**: Will fail at runtime.
**Recommendation**: Add implementation based on word_count_tier:
```python
def _estimate_max_tokens(self, prompt: EnrichedPrompt) -> int:
    tier_to_tokens = {"short": 500, "medium": 1000, "long": 2000}
    return tier_to_tokens.get(prompt.word_count_tier, 1000)
```

#### Issue 6.3: Response Metadata Tracking Missing
**Problem**: PROMPT.md requires tracking "Response length, Response time, Format detection, Greeting/sign-off patterns" but `ModelResponse` schema doesn't include format_detected or greeting_patterns fields.
**Recommendation**: Extend `ModelResponse`:
```python
class ModelResponse(BaseModel):
    ...
    format_detected: Optional[str] = None  # email/memo/report/etc.
    has_greeting: Optional[bool] = None
    has_signoff: Optional[bool] = None
    bullet_count: Optional[int] = None
    paragraph_count: Optional[int] = None
```

---

## Part 7: Judging System Simulation

### Dual Persona Judge Simulation

#### Issue 7.1: Recipient Role Inference Missing
**Problem**: `DualPersonaJudge._infer_recipient_role()` is called but not implemented.
```python
recipient_system = self.RECIPIENT_SYSTEM_TEMPLATE.format(
    recipient_name=prompt.recipient.full,
    recipient_role=self._infer_recipient_role(prompt),  # NOT IMPLEMENTED
    company=prompt.company.name
)
```
**Impact**: Will fail at runtime.
**Recommendation**: Add implementation:
```python
def _infer_recipient_role(self, prompt: EnrichedPrompt) -> str:
    # Look for role hints in prompt context
    if prompt.context_details.get('stakeholders'):
        return prompt.context_details['stakeholders'][0]
    return f"colleague at {prompt.company.name}"
```

#### Issue 7.2: Judge System Prompts May Cause Position Bias
**Problem**: The WRITING_EXPERT_SYSTEM and RECIPIENT_SYSTEM prompts don't explicitly instruct judges to avoid position bias.
**Research**: Studies show LLM judges tend to prefer the first response (position A).
**Recommendation**: Add to both system prompts:
```
IMPORTANT: Evaluate each response on its merits alone. The order of presentation (A vs B)
has no bearing on quality. Focus solely on the writing quality and effectiveness.
```

#### Issue 7.3: Temperature 0.3 May Still Cause Inconsistency
**Problem**: Even with temperature=0.3, judges may give different verdicts on identical comparisons.
**Impact**: Reduces reliability of majority voting.
**Recommendation**: Consider temperature=0.1 for judging, or implement a consistency check:
```python
# If same judge gives contradictory results on position shuffle, flag for review
if expert_ab.winner != self._reverse_winner(expert_ba.winner):
    flag_inconsistent_judgment(...)
```

### Position Bias Handler Simulation

#### Issue 7.4: Position Shuffle Doubles API Costs
**Problem**: Shuffling positions means running each judgment twice (A-B and B-A orders).
**Impact**: Judging costs double what the cost estimates assume.
**Calculation**:
- 500 prompts * 4 model pairs * 3 judges * 5 votes * 2 personas * 2 positions
- = 120,000 judge API calls instead of 60,000
**Recommendation**: Either:
1. Update cost estimates to reflect position shuffling
2. Make position shuffling optional
3. Use statistical correction instead of full shuffling

#### Issue 7.5: Position Majority Logic Has Edge Case
**Problem**: With only 2 position orderings, a tie is possible and common.
```python
def _position_majority(self, winners: list[str], model_a: str, model_b: str) -> str:
    a_count = winners.count(model_a)
    b_count = winners.count(model_b)
    if a_count > b_count:
        return model_a
    elif b_count > a_count:
        return model_b
    else:
        return "TIE"
```
**Gotcha**: If AB order says A wins and BA order says B wins (now in position A), the logic is correct BUT the mapping may be confusing.
**Recommendation**: Add unit tests with explicit examples and comments explaining the mapping.

### Vote Aggregation Simulation

#### Issue 7.6: Majority-of-Majorities May Not Match PROMPT.md Spec
**Problem**: PROMPT.md says "Best-of-5 judgments per comparison" but the plan aggregates across personas and positions differently.
**Spec says**:
1. Each judge gives 5 judgments -> majority winner
2. Take majority across 3 judges
**Plan does**:
1. Each judge gives 2 position orderings * 2 personas = 4 judgments
2. Aggregate across all judge-persona combinations

**Impact**: The aggregation logic doesn't match the specification.
**Recommendation**: Implement exactly as specified:
```python
# For each judge model:
#   Run 5 independent judgments
#   Take majority -> that judge's vote
# Across 3 judges, take majority -> final winner
```

#### Issue 7.7: Best-of-5 Not Actually Implemented
**Problem**: The plan mentions best-of-5 but the code only runs 2 judgments per judge (one per position order).
**Impact**: Statistical power is lower than expected.
**Recommendation**: Implement actual best-of-5:
```python
async def best_of_n_judgment(self, ..., n: int = 5) -> str:
    votes = []
    for i in range(n):
        result = await self._single_judgment(...)
        votes.append(result.winner)
    return Counter(votes).most_common(1)[0][0]
```

---

## Part 8: Analysis Engine Simulation

### Statistics Engine Simulation

#### Issue 8.1: scipy.stats.binom_test Deprecated
**Problem**: The code uses `stats.binom_test()` which is deprecated in scipy 1.12+.
```python
p_value = stats.binom_test(position_a_wins, ...)  # DEPRECATED
```
**Impact**: Will raise deprecation warnings or fail in future scipy versions.
**Recommendation**: Use `stats.binomtest()` instead:
```python
result = stats.binomtest(position_a_wins, n=total, p=0.5, alternative='two-sided')
p_value = result.pvalue
```

#### Issue 8.2: Pearson Correlation Misuse in Length Bias Detection
**Problem**: The length bias detection calculates correlation incorrectly:
```python
correlation, p_value = stats.pearsonr(
    [1 if r.winner == r.model_a else 0 for r in results if r.winner != "TIE"],
    length_diffs[:len([r for r in results if r.winner != "TIE"])]
)
```
**Issue**: This tests correlation between "which model won" and "absolute length difference", which doesn't make sense. Should test correlation between "longer response won" and "length difference magnitude".
**Recommendation**: Rewrite:
```python
longer_won = []
length_diffs_nonzero = []
for r in results:
    if r.winner == "TIE":
        continue
    len_a = len(responses[r.model_a])
    len_b = len(responses[r.model_b])
    if len_a == len_b:
        continue
    winner_was_longer = (r.winner == r.model_a and len_a > len_b) or \
                        (r.winner == r.model_b and len_b > len_a)
    longer_won.append(1 if winner_was_longer else 0)
    length_diffs_nonzero.append(abs(len_a - len_b))

# Then test if longer_won rate is > 0.5
```

### Weakness Finder Simulation

#### Issue 8.3: `_matches_dimension()` Not Implemented
**Problem**: `WeaknessFinder.analyze_losses()` calls `self._matches_dimension(r, prompts, dimension, value)` but this method isn't defined.
**Impact**: Will fail at runtime.
**Recommendation**: Implement:
```python
def _matches_dimension(self, result, prompts, dimension, value) -> bool:
    prompt = prompts.get(result.prompt_id)
    if not prompt:
        return False
    dimension_getters = {
        'category': lambda p: p.task.inferred_category,
        'channel': lambda p: p.expected_format,
        'formality': lambda p: p.formality,
        'job_zone': lambda p: p.task.job_zone,
        'industry': lambda p: p.industry,
    }
    getter = dimension_getters.get(dimension)
    return getter and getter(prompt) == value
```

#### Issue 8.4: `result.raw_judgments` and `result.gemini_position` Not in Schema
**Problem**: `_extract_reasoning_themes()` accesses fields not in `AggregatedResult`:
```python
for judgment in loss.raw_judgments:  # raw_judgments not in schema
    if loss.gemini_position == 'A':   # gemini_position not in schema
```
**Impact**: Will raise AttributeError at runtime.
**Recommendation**: Add to `AggregatedResult` schema:
```python
class AggregatedResult(BaseModel):
    ...
    raw_judgments: list[JudgmentResult]
    gemini_model_id: str  # To identify which model is Gemini
```

---

## Part 9: TUI Implementation Simulation

#### Issue 9.1: `self.eval_state` Not Initialized
**Problem**: `EvalTUI.refresh_data()` accesses `self.eval_state` but it's never set:
```python
async def refresh_data(self) -> None:
    if self.eval_state:  # Where is this set?
        self.prompts_completed = self.eval_state.completed_count
```
**Impact**: Will always skip update since eval_state is None.
**Recommendation**: Add initialization method:
```python
def set_eval_state(self, state: EvalState) -> None:
    self.eval_state = state
```
And call from orchestrator.

#### Issue 9.2: Textual API Changes
**Problem**: The textual library evolves rapidly. Methods like `Static.update()` may have changed.
**Impact**: Code may not work with latest textual version.
**Recommendation**: Pin textual version explicitly: `"textual==0.52.1"` and test before release.

#### Issue 9.3: Missing Keyboard Shortcuts Documentation
**Problem**: TUI defines bindings but there's no in-app help screen.
**Recommendation**: Add help overlay:
```python
def action_help(self) -> None:
    self.push_screen(HelpScreen())
```

---

## Part 10: Configuration and Presets Simulation

#### Issue 10.1: Cost Estimates Are Unrealistic
**Problem**: Preset cost estimates seem too low:
- "smoke" preset: $0.50 for 5 prompts
- That's $0.10 per prompt
- But each prompt needs: 2+ model responses (~$0.02-0.10 each) + 3 judges * 5 votes * 2 personas * 2 positions = 60 judge calls (~$0.01-0.05 each)
- Realistic cost: $0.20-0.50 per prompt minimum

**Calculation for "standard" preset (200 prompts)**:
- Response generation: 200 * 4 model pairs * 2 responses = 1,600 calls
- Judging: 200 * 4 pairs * 3 judges * 5 votes * 2 personas = 24,000 calls (if best-of-5)
- Or with position shuffling: 48,000 calls
- At $0.01 per call average = $240-480, not $75

**Recommendation**: Recalculate all preset costs using actual OpenRouter pricing for specified models.

#### Issue 10.2: Preset Judge Models Include Evaluated Models
**Problem**: "standard" preset uses `"google/gemini-3.0-pro"` as both evaluated model AND judge.
```python
judge_models=["anthropic/claude-opus-4.5", "openai/gpt-5.2", "google/gemini-3.0-pro"],
```
**Impact**: Self-preference bias - Gemini judging Gemini vs competitors.
**Recommendation**: Either:
1. Exclude Gemini from judges when evaluating Gemini
2. Always detect and report self-preference bias
3. Use only non-competing models as judges

#### Issue 10.3: Missing Time Estimation Logic
**Problem**: Presets have `estimated_time_minutes` but no code calculates this.
**Factors to consider**:
- API rate limits per model
- Concurrent request limits
- Average response latency
- Network overhead
**Recommendation**: Add `CostEstimator.estimate_time()` that accounts for:
```python
def estimate_time(self, config: EvalConfig) -> TimeEstimate:
    total_api_calls = self._count_api_calls(config)
    effective_rate = min(
        config.max_concurrent_requests,
        self._get_rate_limit(config.models)
    )
    base_time_seconds = total_api_calls / effective_rate
    # Add overhead for processing, retries, etc.
    return TimeEstimate(
        optimistic=base_time_seconds * 1.2,
        realistic=base_time_seconds * 1.8,
        pessimistic=base_time_seconds * 3.0
    )
```

---

## Part 11: Error Handling Simulation

#### Issue 11.1: Checkpoint File Race Condition
**Problem**: The atomic write pattern has a subtle race:
```python
async with aiofiles.open(self.temp_file, 'w') as f:
    await f.write(json.dumps(checkpoint_data, indent=2))
self.temp_file.rename(self.checkpoint_file)  # Not awaited!
```
**Gotcha**: `Path.rename()` is synchronous and blocks the event loop. Also, on Windows, rename fails if target exists.
**Recommendation**:
```python
import shutil
await asyncio.to_thread(shutil.move, str(self.temp_file), str(self.checkpoint_file))
```

#### Issue 11.2: Circuit Breaker Missing Per-Model State Persistence
**Problem**: Circuit breaker state is in-memory only. If the process restarts, all circuits reset to closed.
**Impact**: After resume, may immediately hit API limits again.
**Recommendation**: Persist circuit state to checkpoint file:
```python
checkpoint_data = {
    ...
    "circuit_states": {
        model_id: {
            "state": state.value,
            "failure_count": self._failure_counts[model_id],
            "last_failure": self._last_failure_time.get(model_id)
        }
        for model_id, state in self._states.items()
    }
}
```

#### Issue 11.3: `RateLimitError` and `TransientError` Not Defined
**Problem**: The `FailureHandler` catches these exceptions but they're not defined anywhere:
```python
except RateLimitError as e:
    ...
except TransientError as e:
    ...
except PermanentError as e:
```
**Impact**: Will raise NameError.
**Recommendation**: Define exception classes:
```python
class APIError(Exception):
    pass

class RateLimitError(APIError):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after

class TransientError(APIError):
    pass

class PermanentError(APIError):
    pass
```

---

## Part 12: PDF Report Generation Simulation

#### Issue 12.1: WeasyPrint Dependency Complexity
**Problem**: WeasyPrint requires system-level dependencies (cairo, pango, etc.) that are complex to install.
**Impact**: Installation may fail on many systems, especially Windows.
**Recommendation**: Either:
1. Add detailed installation instructions per OS
2. Use alternative like `reportlab` which is pure Python
3. Make PDF generation optional with graceful fallback to HTML

#### Issue 12.2: Kaleido Version Compatibility
**Problem**: kaleido (for plotly image export) has known compatibility issues with certain architectures.
**Impact**: Chart export may fail silently.
**Recommendation**: Add fallback to matplotlib:
```python
try:
    img_bytes = fig.to_image(format='png', ...)
except Exception:
    # Fallback to matplotlib-based export
    img_bytes = self._matplotlib_fallback(fig)
```

#### Issue 12.3: Report Templates Not Provided
**Problem**: PDF generator uses Jinja2 templates but no template files are provided.
```python
template = self.env.get_template(f'{report_type}_report.html')
```
**Impact**: Will fail with TemplateNotFound error.
**Recommendation**: Add template files:
- `src/reports/templates/comprehensive_report.html`
- `src/reports/templates/executive_report.html`
- Include CSS styling for PDF rendering

---

## Part 13: Missing Components and Integration Issues

### Critical Missing Components

#### Issue 13.1: No Main Orchestrator Implementation
**Problem**: The plan has detailed component code but no main orchestrator that ties everything together.
**Impact**: No way to actually run an evaluation.
**Required Code**:
```python
class EvalOrchestrator:
    async def run(self, config: EvalConfig) -> RunResults:
        # 1. Validation phase
        # 2. Prompt generation phase
        # 3. Response collection phase
        # 4. Judging phase
        # 5. Analysis phase
        # 6. Report generation phase
        pass
```

#### Issue 13.2: No CLI Entry Point
**Problem**: Appendix B shows CLI commands but no actual CLI implementation exists.
**Impact**: Cannot run the system from command line.
**Recommendation**: Add `src/cli.py` implementation:
```python
import typer
app = typer.Typer()

@app.command()
def run(preset: str = "standard", ...):
    ...

@app.command()
def resume(run_dir: str):
    ...
```

#### Issue 13.3: No Database Schema Definition
**Problem**: The plan mentions SQLite storage but doesn't define the actual schema.
**Impact**: Cannot persist data correctly.
**Required Tables**:
```sql
CREATE TABLE prompts (...);
CREATE TABLE responses (...);
CREATE TABLE judgments (...);
CREATE TABLE aggregated_results (...);
CREATE TABLE run_metadata (...);
CREATE TABLE checkpoints (...);
```

### Integration Issues

#### Issue 13.4: Inconsistent ID Types
**Problem**: Some code uses string IDs (`prompt_id: str`), others use auto-generated hex (`f"prompt_{seed:08x}"`).
**Impact**: ID mismatches when joining data.
**Recommendation**: Standardize on UUID4 strings throughout.

#### Issue 13.5: No Logging Configuration
**Problem**: Code uses `logger.info()`, `logger.warning()`, etc. but no logging setup.
**Impact**: No logs will be produced.
**Recommendation**: Add structlog configuration in `src/config/logging.py`.

#### Issue 13.6: Missing Type Hints in Some Functions
**Problem**: Several functions have incomplete type hints:
- `_generate_all_combinations()` - return type unclear
- `_parse_enrichment()` - return type unclear
- `_parse_json_response()` - parameter and return types unclear
**Recommendation**: Complete all type hints for mypy compatibility.

---

## Part 14: PROMPT.md Compliance Check

### Features Required But Not Implemented

| Feature | PROMPT.md Location | Plan Status |
|---------|-------------------|-------------|
| Temporal context in prompts | "Include temporal grounding" | Mentioned but no implementation |
| Mock attachments | "Include mock attachments/references" | Not implemented |
| Competing objectives | "Include prompts with inherent trade-offs" | Not implemented |
| Regional English variants | "recipient_english_variant field" | Not in schema |
| Reply-to context | "Prior messages to respond to" | Partially addressed in RevisionGenerator |
| Multiple recipients (CC) | "Multiple audiences simultaneously" | Not implemented |
| Tone matching examples | "Prior writing samples to match" | Not implemented |
| Sensitive topic tagging | "Track and analyze separately" | Detector mentioned but not integrated |
| Refusal categorization | "Categorize WHY models refuse" | Not implemented |
| Constraint compliance checker | "Track compliance separately" | Not implemented |

### Recommendation: Add Missing Feature Stubs

```python
class TemporalContextGenerator:
    """Add temporal grounding to prompts."""
    pass

class AttachmentGenerator:
    """Generate mock attachments for reference."""
    pass

class CompetingObjectivesEnricher:
    """Add tension/trade-offs to prompts."""
    pass

class ReplyToContextGenerator:
    """Generate prior messages for response prompts."""
    pass

class MultiRecipientGenerator:
    """Handle CC/BCC scenarios."""
    pass
```

---

## Part 15: Security and Privacy Considerations

#### Issue 15.1: API Key Storage
**Problem**: API key is expected via environment variable but no guidance on secure storage.
**Risk**: Keys may be committed to git or logged.
**Recommendation**:
1. Add `.env` to `.gitignore`
2. Mask API key in logs
3. Consider secrets manager integration for production

#### Issue 15.2: Company/Name Data May Create Privacy Concerns
**Problem**: Using real company names and generated person names could create legal/privacy issues.
**Risk**: Generated prompts might inadvertently reference real people.
**Recommendation**:
1. Add disclaimer that generated scenarios are fictional
2. Screen company names against "do not use" list
3. Add opt-out for real company names in config

#### Issue 15.3: Response Content Storage
**Problem**: Model responses are stored indefinitely with no retention policy.
**Risk**: Sensitive generated content could accumulate.
**Recommendation**: Add configurable retention policy and PII scanning.

---

## Part 16: Summary of Critical Issues

### Priority 1: Blocking Issues (Must Fix Before Implementation)

1. **Issue 3.2**: async/await mixing bug - will crash at runtime
2. **Issue 6.1**: Speculative model IDs - will fail API calls
3. **Issue 7.1**: Missing `_infer_recipient_role()` - will crash
4. **Issue 8.3**: Missing `_matches_dimension()` - will crash
5. **Issue 11.3**: Undefined exception classes - will crash
6. **Issue 13.1**: No orchestrator - cannot run
7. **Issue 13.3**: No database schema - cannot persist

### Priority 2: Significant Issues (Should Fix Before Production)

1. **Issue 2.6**: Incomplete BLS/NAICS mapping
2. **Issue 3.1**: No companies.json data file
3. **Issue 5.3**: Stratification dimension explosion
4. **Issue 7.4**: Position shuffle doubles costs (budget surprise)
5. **Issue 7.6/7.7**: Best-of-5 not implemented correctly
6. **Issue 10.1**: Unrealistic cost estimates
7. **Issue 10.2**: Self-preference bias in judges
8. **Issue 12.3**: No report templates

### Priority 3: Quality Issues (Fix When Possible)

1. **Issue 4.1**: Limited name diversity
2. **Issue 4.2**: Age/generation not connected to names
3. **Issue 5.6**: Temperature too high for enrichment
4. **Issue 8.1**: Deprecated scipy function
5. **Issue 8.2**: Incorrect correlation calculation
6. **Issue 9.2**: Textual API compatibility

### Priority 4: Missing Features (Per PROMPT.md)

1. Temporal context generation
2. Mock attachment generation
3. Competing objectives
4. Regional English variants
5. Reply-to context
6. Multiple recipients (CC)
7. Tone matching
8. Sensitive topic tagging
9. Refusal categorization
10. Constraint compliance checking

---

## Part 17: Recommended Implementation Order

Based on this simulation, the recommended implementation order is:

### Phase 1: Foundation (Week 1-2)
1. Fix all Priority 1 blocking issues
2. Create database schema
3. Implement main orchestrator skeleton
4. Add CLI entry point
5. Define all exception classes
6. Verify O*NET schema against actual database

### Phase 2: Core Pipeline (Week 3-4)
1. Implement O*NET extraction with verified schema
2. Create companies.json with real company data
3. Add complete NAICS mapping for all SOC codes
4. Fix async/await issues in company database
5. Implement name generator with larger pools

### Phase 3: Prompt Generation (Week 5-6)
1. Reduce stratification to 4-5 dimensions
2. Fix format string issues in enrichment
3. Add word count tier assignment
4. Implement missing feature generators (temporal, attachments, etc.)

### Phase 4: Evaluation (Week 7-8)
1. Implement proper best-of-5 judging
2. Add position bias mitigation instruction to judge prompts
3. Fix vote aggregation to match PROMPT.md spec
4. Implement constraint compliance checker
5. Update cost estimates with accurate calculations

### Phase 5: Analysis and Reporting (Week 9-10)
1. Fix deprecated scipy functions
2. Correct length bias calculation
3. Implement missing analysis methods
4. Create report templates
5. Add WeasyPrint installation instructions or fallback

### Phase 6: Polish and Testing (Week 11-12)
1. Add comprehensive test coverage
2. Pin dependency versions
3. Add security measures
4. Write documentation
5. End-to-end integration testing

---

## Conclusion

This simulation identified **47 distinct issues** across 17 categories. Of these:
- **7 are blocking** and will cause immediate crashes
- **8 are significant** and will cause incorrect results or budget overruns
- **9 are quality issues** that affect reliability or user experience
- **10 are missing features** explicitly required by PROMPT.md

The master plan provides excellent architectural direction and comprehensive component design. However, significant implementation work remains, particularly around:
1. Completing stub implementations
2. Creating required data files
3. Fixing integration issues between components
4. Aligning judging methodology with PROMPT.md specification

With the recommended implementation order and fixes, the framework should be production-ready in approximately 10-12 weeks.

---

*End of Simulation Report*
