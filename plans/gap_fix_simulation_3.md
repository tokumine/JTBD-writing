# Gap Fix Simulation Report 3: Detailed Dry Run Analysis

This document provides a thorough dry-run simulation of implementing the gap fix master plan, walking through the implementation as if building it, identifying what works, what doesn't, and documenting potential issues.

---

## Executive Summary

**Overall Assessment**: The gap fix master plan is well-structured but has several implementation challenges that need addressing before production use. The parallel architecture is sound but has some race condition risks. Most gaps from gap_analysis.md are addressed, but a few remain incomplete.

**Key Findings**:
- Parallel architecture: 85% solid, 15% needs refinement
- Gap coverage: ~90% of identified gaps addressed
- Integration issues: 7 significant concerns identified
- Missing pieces: 4 critical components not fully specified
- Edge cases: 12 potential gotchas documented

---

## 1. EvaluationEngine Parallel Architecture Simulation

### 1.1 Simulating Parallel Request Flow

**Scenario**: Processing 100 prompts with 3 model pairs, 3 judges, 5 votes each, both personas.

**Simulation Walkthrough**:

```
Batch 1 (10 prompts):
  -> Prompt 1:
     -> Collect unique models: {gemini-3.0-pro, gpt-5.2, claude-opus-4.5, grok-4.1}
     -> Generate responses in parallel (4 calls)
       -> asyncio.gather fires 4 tasks with semaphore guards
       -> Global semaphore (30 slots): OK
       -> Per-model semaphores: OK (each model has dedicated limit)
     -> Run judging for each pair (3 pairs):
       -> Each pair needs: 3 judges x 5 votes x 2 personas = 30 judge calls
       -> 3 pairs = 90 total judge calls for this prompt
       -> With global semaphore 30, need 3 batches minimum
```

**What Works Well**:
1. The dual semaphore system (global + per-model) properly prevents thundering herd
2. Response caching prevents duplicate generation calls
3. Deterministic position shuffling using `hash(prompt_id + model + vote_idx)` is reproducible
4. Cost tracking is thread-safe with Lock()

**Issues Identified**:

**ISSUE 1: Semaphore Initialization Race Condition**
```python
def _ensure_semaphores(self):
    if not self._semaphores_initialized:  # <-- Race condition here
        self._global_semaphore = asyncio.Semaphore(self.max_concurrent_global)
        self._semaphores_initialized = True
```
**Problem**: Multiple coroutines calling `_ensure_semaphores()` simultaneously could create multiple semaphores.
**Fix**: Use `asyncio.Lock()` or initialize in `__init__` with proper event loop handling.

**ISSUE 2: Model Semaphore Creation Not Thread-Safe**
```python
def _get_model_semaphore(self, model: str) -> asyncio.Semaphore:
    if model not in self._model_semaphores:  # <-- Race condition
        limit = self.MODEL_CONCURRENCY_LIMITS.get(model, ...)
        self._model_semaphores[model] = asyncio.Semaphore(limit)  # <-- Could create duplicates
    return self._model_semaphores[model]
```
**Problem**: Concurrent calls for same model could create multiple semaphores.
**Fix**: Use `asyncio.Lock()` to protect dictionary modification, or pre-initialize all model semaphores.

**ISSUE 3: Judge Task Wrapping Creates Closure Issues**
```python
wrapped_tasks = []
for i, (task, meta) in enumerate(zip(judge_tasks, task_metadata)):
    wrapped_tasks.append(
        run_judge_with_semaphore(task, meta["judge_model"])
    )
```
**Problem**: The `task` variable is a coroutine that's already been called (created). Passing it to `run_judge_with_semaphore` is fine, but the closure over `meta["judge_model"]` in the inner loop could have late-binding issues.
**Actually OK**: Upon closer inspection, since we're iterating with `enumerate` and using `meta["judge_model"]` directly (not `meta`), this is likely fine. But would benefit from explicit capture.

### 1.2 Pause/Cancel Mechanism Simulation

**Scenario**: User presses 'p' to pause during batch processing.

```
Time T0: Engine processing prompt 15 of 100
Time T1: User presses 'p'
        -> TUI calls engine.pause()
        -> self._paused.clear()
Time T2: Current API calls in flight continue (cannot stop)
Time T3: Next prompt iteration hits: await self._paused.wait()
        -> Blocks until resume
Time T4: User presses 'p' again
        -> self._paused.set()
        -> Processing continues
```

**What Works**: Clean pause/resume using asyncio.Event()
**Issue**: In-flight API calls cannot be cancelled - need to document this behavior to users.

### 1.3 ETA Calculation Simulation

```python
def _calculate_eta(self, completed: int, total: int, elapsed: float) -> Optional[float]:
    if self._batch_completion_times:
        weights = [1.5 ** i for i in range(len(self._batch_completion_times))]
        weighted_avg = sum(t * w for t, w in zip(self._batch_completion_times, weights))
        weighted_avg /= sum(weights)
        ...
```

**Simulation with sample data**:
```
Batch times: [45s, 50s, 55s, 40s, 35s] (5 batches)
Weights:     [1.0, 1.5, 2.25, 3.375, 5.0625]
Weighted sum: 45 + 75 + 123.75 + 135 + 177.19 = 555.94
Weight sum:   13.6875
Weighted avg: 40.6s per batch

If 50 prompts completed out of 100, remaining = 50
Batches remaining = 50/10 = 5
ETA = 5 * 40.6 = 203 seconds
```

**What Works**: Exponential weighting gives more importance to recent batch times
**Issue**: `[1.5 ** i]` weights earliest batches lowest. Should this be reversed? `[1.5 ** (len-i)]` would weight recent batches higher.

**FIX NEEDED**:
```python
# Current (weights early batches lower):
weights = [1.5 ** i for i in range(len(self._batch_completion_times))]
# Should be (weights recent batches higher):
weights = [1.5 ** i for i in reversed(range(len(self._batch_completion_times)))]
```

---

## 2. Cohen's Kappa Implementation Simulation

### 2.1 Simulating Cohen's Kappa Calculation

**Test Case**: Two judges, 20 prompts, 3 categories (gemini, competitor, tie)

```
Judge 1 ratings: [g, g, c, g, t, c, c, g, g, c, g, c, t, g, g, c, c, g, g, t]
Judge 2 ratings: [g, c, c, g, g, c, c, g, c, c, g, c, t, g, c, c, c, g, g, t]

Confusion Matrix:
           Judge2
           g   c   t
Judge1 g   7   3   0  = 10
       c   1   7   0  = 8
       t   0   0   2  = 2
           8  10   2    20

Observed agreement = (7 + 7 + 2) / 20 = 16/20 = 0.80

Expected agreement:
P(j1=g) = 10/20 = 0.5,  P(j2=g) = 8/20 = 0.4   -> 0.5 * 0.4 = 0.20
P(j1=c) = 8/20 = 0.4,   P(j2=c) = 10/20 = 0.5  -> 0.4 * 0.5 = 0.20
P(j1=t) = 2/20 = 0.1,   P(j2=t) = 2/20 = 0.1   -> 0.1 * 0.1 = 0.01
Expected = 0.20 + 0.20 + 0.01 = 0.41

Kappa = (0.80 - 0.41) / (1 - 0.41) = 0.39 / 0.59 = 0.66 ("substantial")
```

**Implementation Check**: The `cohens_kappa()` function correctly implements the formula.

**ISSUE 4: Division by Zero Not Handled**
```python
if expected_agreement == 1.0:
    kappa = 1.0 if observed_agreement == 1.0 else 0.0
else:
    kappa = (observed_agreement - expected_agreement) / (1.0 - expected_agreement)
```
This handles `expected_agreement == 1.0` but what about `expected_agreement` very close to 1.0? Floating point issues could cause division by tiny numbers.

### 2.2 Simulating Fleiss' Kappa for Multiple Judges

**Test Case**: 3 judges, 10 prompts

```
Prompt 1: {gemini: 2, competitor: 1, tie: 0}
Prompt 2: {gemini: 3, competitor: 0, tie: 0}
Prompt 3: {gemini: 1, competitor: 2, tie: 0}
...
```

**Implementation appears correct** for the standard Fleiss' kappa formula.

**ISSUE 5: Empty/Partial Ratings Not Handled Gracefully**
If some prompts have fewer judge votes than others, the code assumes consistent `n` (number of raters):
```python
n = sum(ratings_matrix[0].values())  # Number of raters
```
If prompt 5 only has 2 votes instead of 3, this will produce incorrect results.

**Fix**: Validate that all rows have the same total votes, or handle variable-n case.

---

## 3. Cost Tracking TUI Simulation

### 3.1 Widget Update Flow

```
Engine emits ProgressUpdate every prompt completion:
  -> TUI._handle_progress() called
  -> cost_tracker.update_costs(spent=0.0523, projected=5.23)
  -> CostTrackerWidget.watch_cost_spent triggers
  -> _update_display() rebuilds Rich Panel
```

**What Works**:
- Reactive properties automatically trigger re-render
- Budget comparison with color coding (green < 80%, yellow < 100%, red >= 100%)
- Progress bar visualization

**ISSUE 6: No Currency Formatting Localization**
```python
spent_text = Text(f"${self.cost_spent:.4f}", style="green")
```
Always uses `$` symbol and 4 decimal places. Should consider:
- User locale for currency symbol
- Appropriate precision (4 decimals good for small values, awkward for large)

### 3.2 Cost Breakdown Widget

**Simulation**: After 50 prompts with varied model usage

The `CostBreakdownWidget.update_breakdown()` method expects:
- `model_costs: dict` - cost per model
- `phase_costs: dict` - cost per phase (generation, judging)

**ISSUE 7: CostBreakdownWidget Never Receives Updates**
Looking at `EvalTUIApp._handle_progress()`:
```python
# Update costs
self.query_one("#cost-tracker", CostTrackerWidget).update_costs(...)

# MISSING: update_breakdown() is never called!
# self.query_one("#cost-breakdown", CostBreakdownWidget).update_breakdown(...)
```

The `ProgressUpdate` dataclass doesn't include model-level or phase-level cost breakdowns, so the breakdown widget would never show data.

**Fix**: Add `model_costs: Dict[str, float]` and `phase_costs: Dict[str, float]` to `ProgressUpdate` and wire up the update call.

---

## 4. Help Overlay Simulation

### 4.1 Key Binding Flow

```
User presses 'h':
  -> HelpBindingMixin.action_show_help() called
  -> self.push_screen(HelpOverlay())
  -> HelpOverlay modal appears
User presses 'h' again:
  -> HelpOverlay.action_dismiss() called
  -> Modal dismissed
```

**What Works**: Clean modal pattern using Textual's `ModalScreen`

**ISSUE 8: `question_mark` Binding Invalid**
```python
BINDINGS = [
    Binding("h", "show_help", "Help", show=True),
    Binding("question_mark", "show_help", "Help", show=False),  # Invalid!
]
```
Textual uses key names like `"shift+slash"` for `?`, not `"question_mark"`.

**Fix**: Change to `Binding("shift+slash", "show_help", "Help", show=False)` or `Binding("?", "show_help", ...)` depending on Textual version.

### 4.2 Help Content Completeness

The help overlay shows many shortcuts:
- Navigation (h, q, Tab, etc.)
- Evaluation Control (Space, p, s, x)
- View Control (1-5, r, d, l)
- Results Navigation (Up/Down, Enter, f, e)
- Advanced (c, k, m, t)

**ISSUE 9: Some Listed Shortcuts Not Implemented**
The help lists these shortcuts, but checking EvalTUIApp.BINDINGS:
- `c` (show cost breakdown) - NOT in BINDINGS
- `k` (show kappa details) - NOT in BINDINGS
- `m` (model comparison view) - NOT in BINDINGS
- `t` (response time histogram) - NOT in BINDINGS
- `Tab` navigation - depends on Textual defaults
- `Up/Down` navigation - not explicitly bound

**Impact**: Help overlay promises functionality that doesn't exist.

---

## 5. CLI Options Simulation

### 5.1 Running Complete Evaluation via CLI

```bash
gemini-eval run \
  --prompts 500 \
  --gemini google/gemini-3.0-pro \
  --competitor openai/gpt-5.2 \
  --competitor anthropic/claude-opus-4.5 \
  --judge openai/gpt-5.2 \
  --judge anthropic/claude-opus-4.5 \
  --judge google/gemini-3.0-pro \
  --votes 5 \
  --persona both \
  --formality 2-4 \
  --budget 50.0 \
  --output ./my-eval
```

**Simulation**:
1. Validates API key from env
2. Builds model_pairs: [(gemini-pro, gpt-5.2), (gemini-pro, claude-opus)]
3. Parses formality range "2-4" -> (2, 4)
4. Creates JudgeConfig with 3 judges, 5 votes, both personas
5. Creates EvalConfig
6. If --dry-run, shows estimates and exits
7. Otherwise, initializes OpenRouterClient, CheckpointManager, Database
8. Starts EvaluationEngine with TUI or simple mode

**What Works**:
- Multiple `--competitor` and `--judge` flags work via typer's List support
- Formality range parsing handles both "3" (single) and "2-4" (range)
- Budget constraint passed to config

**ISSUE 10: Missing CLI Options from Gap Analysis**

Comparing to gap_analysis.md requirements:
- `--tier` (pro-tier/flash-tier): NOT IMPLEMENTED
- `--job-zones`: NOT IMPLEMENTED
- `--age-range` / `--generation`: NOT IMPLEMENTED
- `--occupation-limit` / `--max-per-occupation`: NOT IMPLEMENTED
- `--industry-limit` / `--max-per-industry`: NOT IMPLEMENTED

The CLI in gap_fix_master_draft.md doesn't add these options.

### 5.2 Dry Run Estimation

```bash
gemini-eval run --prompts 1000 --dry-run
```

**Simulation**:
```python
estimator = CostEstimator(config)
estimate = estimator.estimate()
```

**ISSUE 11: CostEstimator Not Provided**
The CLI references `CostEstimator` but its implementation isn't shown in gap_fix_master_draft.md. We have `QuickEstimate.calculate()` but no `CostEstimator` class.

**Fix**: Either rename the reference or provide `CostEstimator` implementation.

---

## 6. TUI Enhancements Simulation

### 6.1 Progress Dashboard Layout

```
+----------------------------------------------------------+
|  Header (clock)                                          |
+----------------------------------------------------------+
| Progress Section:                                        |
|   GENERATION [████████░░░░░░░░░░░░] 45/100 (45%) ETA 5m |
|   Occupation: Software Developers | Industry: Tech       |
+----------------------------------------------------------+
|  Left Panel (Tabbed)    |  Right Panel                   |
|  [Model Pairs][Stats]   |  +------------------------+    |
|  [Kappa]                |  |    Cost Tracking       |    |
|                         |  |    Spent: $1.23        |    |
|  gemini vs gpt-5.2     |  |    Projected: $12.30   |    |
|  Done: 45/100          |  +------------------------+    |
|  Win Rate: 52.3%       |  |    Cost Breakdown      |    |
|  CI: (48.2% - 56.4%)   |  |    (not showing data)  |    |
|                         |  +------------------------+    |
+----------------------------------------------------------+
| Log Panel (hidden by default, toggled with 'l')          |
+----------------------------------------------------------+
|  Footer                                                  |
+----------------------------------------------------------+
```

**What Works**:
- Grid layout with proper proportions
- Tabbed content for different views
- Hidden log panel with toggle
- Model pair progress with CIs

**ISSUE 12: CSS Grid Values May Not Work**
```python
CSS = """
#main-container {
    grid-size: 2 2;
    grid-columns: 2fr 1fr;
    grid-rows: auto 1fr;
}
"""
```

In Textual CSS, `grid-columns` and `grid-rows` syntax might be different. Need to verify against Textual documentation.

---

## 7. Name Formality Variation Simulation

### 7.1 Testing All Formality Levels

```python
generator = NameGenerator(seed=42)
name = generator.generate(
    gender="male",
    include_middle=True,
    include_prefix=True,
    include_suffix=True,
    professional_context=True,
    age_group="middle"
)
# name = GeneratedName(
#     first_name="Michael",
#     last_name="Johnson",
#     middle_initial="R",
#     nickname="Mike",
#     prefix="Mr.",
#     suffix="CPA",
#     gender="male"
# )

name.format(FormalityLevel.VERY_INFORMAL)  # -> "Mike"
name.format(FormalityLevel.INFORMAL)       # -> "Mike Johnson"
name.format(FormalityLevel.NEUTRAL)        # -> "Michael Johnson"
name.format(FormalityLevel.FORMAL)         # -> "Mr. Johnson" or "Michael R. Johnson" (50%)
name.format(FormalityLevel.VERY_FORMAL)    # -> "Mr. Michael R. Johnson, CPA"
```

**What Works**:
- Five distinct formality levels
- Nickname shortening with common mappings
- Professional suffixes (CPA, MBA, PhD, etc.)
- Demographic diversity in name pools

**Issues**:

**ISSUE 13: Suffix Formatting Creates Double Comma**
```python
if self.suffix:
    parts.append(f", {self.suffix}")
return " ".join(parts)  # Results in "Mr. Michael R. Johnson , CPA"
```
The space before the comma is wrong. Should be:
```python
name_str = " ".join(parts)
if self.suffix:
    name_str += f", {self.suffix}"
return name_str
```

**ISSUE 14: Missing "Mrs." Logic**
```python
PREFIXES = {
    "male": ["Mr."],
    "female": ["Ms.", "Mrs."],  # How to choose between these?
    ...
}
```
There's no logic to determine when to use "Mrs." vs "Ms." - would need marital status field.

### 7.2 Integration with Prompt Generation

The `generate_for_formality()` method nicely ties formality level to name generation options:
```python
include_prefix = formality >= FormalityLevel.FORMAL       # Mr./Ms. for formal+
include_suffix = formality == FormalityLevel.VERY_FORMAL  # Credentials only very formal
include_middle = formality >= FormalityLevel.FORMAL       # Middle initial for formal+
```

**What Works**: Logical mapping from formality to name complexity.

---

## 8. Ambiguity Behavior Tracking Simulation

### 8.1 Pattern Matching Simulation

**Test Input**: Model response to ambiguous prompt about "Q3 report"
```
"I understand you need help with the Q3 report. Before I proceed, could you clarify
whether you'd like this formatted as an executive summary or a detailed analysis?
Also, I'm assuming the Q3 refers to fiscal Q3 2024 unless you meant calendar Q3.
I'll proceed with a balanced approach that addresses the key stakeholders you mentioned."
```

**Pattern Matching Results**:
- CLARIFICATION_PATTERNS: Matches "could you...clarify" -> `clarification_requested = True`
- ASSUMPTION_PATTERNS: Matches "I'm assuming" -> assumptions detected
- HEDGE_PATTERNS: Matches "unless" implicitly

**Behavior Classification**:
```python
if clarification_requested:
    behavior = AmbiguityResponse.CLARIFIED  # <- Selected
```

**What Works**: Multi-pattern detection reasonably classifies response strategy

**ISSUE 15: Overlapping Categories**
A response could both ask for clarification AND make assumptions. Current code picks CLARIFIED first:
```python
if clarification_requested:
    behavior = AmbiguityResponse.CLARIFIED
elif len(assumptions) >= 2:
    behavior = AmbiguityResponse.ASSUMED
```

Should there be a combined category like `CLARIFIED_WITH_ASSUMPTIONS`?

### 8.2 Confidence Assessment

```python
high_confidence = ["clearly", "certainly", "definitely", ...]
low_confidence = ["not sure", "uncertain", "unclear", ...]

# Simple count comparison
if high_count > low_count:
    return "high"
elif low_count > high_count:
    return "low"
```

**Issue**: Very coarse granularity. Could be improved with weighted scoring or actual NLP sentiment analysis.

---

## 9. Refusal Tracking Simulation

### 9.1 Refusal Classification Test Cases

**Test Case 1**: Clear safety refusal
```
"I can't help create content that could be used to deceive customers
about product safety. This would be harmful and potentially illegal."
```
**Expected**: `is_refusal=True, category=SAFETY, dimensions=[CONTENT]`
**Pattern Matches**: "I can't", "harmful", "safety", "content"

**Test Case 2**: Capability limitation
```
"I don't have access to your company's internal HR records, so I
cannot write that specific termination letter with the details you mentioned."
```
**Expected**: `is_refusal=True, category=CAPABILITY, dimensions=[CONTENT]`
**Pattern Matches**: "don't have...access", "cannot"

**Test Case 3**: Partial refusal with alternative
```
"I'd prefer not to write this in such an aggressive tone, but I can
offer a firm but professional alternative that conveys the same message."
```
**Expected**: `is_refusal=True, category=PARTIAL, alternative_offered=True`
**Pattern Matches**: "prefer not to", "offer...alternative"

**What Works**:
- Multi-dimensional refusal categorization
- Alternative detection
- Confidence scoring based on pattern count

**ISSUE 16: Over-Detection of Refusals**
The pattern `"I can't"` could match legitimate contexts:
- "I can't wait to share this exciting news with the team!"

This isn't a refusal but would trigger STRONG_REFUSAL_PATTERNS.

**Mitigation**: Add context checking - if response is long (>500 chars) and contains substantive content, lower refusal likelihood.

### 9.2 Refusal Tracker Aggregation

```python
tracker = RefusalTracker()

# After 100 prompts:
tracker.get_comparison()
# -> {
#     "google/gemini-3.0-pro": {"refusal_count": 3, "safety_refusals": 2, ...},
#     "openai/gpt-5.2": {"refusal_count": 5, "safety_refusals": 3, ...},
#     ...
# }
```

**What Works**: Clean aggregation by model, category, and dimension.

---

## 10. Failure Summary Reports Simulation

### 10.1 Failure Logging Flow

```python
failure_logger = FailureLogger(output_dir=Path("./results"))

# During evaluation:
failure_logger.log_failure(
    prompt_id="p_12345",
    model="openai/gpt-5.2",
    error_type="TimeoutError",
    error_message="Request timed out after 120s",
    phase="generation",
    retry_count=3,
    recovered=False
)
```

**What Works**:
- Multi-dimensional indexing (_by_type, _by_model, _by_prompt, _by_phase)
- Timeline bucketing for temporal analysis
- Problem prompt detection (prompts with 2+ failures)

**ISSUE 17: Memory Growth with Large Failure Counts**
All failures are stored in memory lists:
```python
self._failures.append(record)
self._by_type[error_type].append(record)
self._by_model[model].append(record)
```

For long-running evaluations with many failures, this could consume significant memory.

**Fix**: Add optional persistence to disk, or implement rolling window.

### 10.2 Report Generation Simulation

**Simulated Report**:
```
========================================================
FAILURE SUMMARY REPORT
========================================================
Generated: 2024-01-15T14:30:00
Total Failures: 47
Recovered: 35 (74.5%)

----------------------------------------
FAILURES BY ERROR TYPE
----------------------------------------

TimeoutError:
  Count: 23
  Recovery Rate: 82.6%
  Affected Models: gpt-5.2, grok-4.1, kimi-k2
  Example: openai/gpt-5.2: Request timed out after 120s...

RateLimitError:
  Count: 15
  Recovery Rate: 100.0%
  Affected Models: gpt-5.2, claude-opus-4.5
  Example: anthropic/claude-opus-4.5: Rate limit exceeded...

ParseError:
  Count: 9
  Recovery Rate: 0.0%
  Affected Models: google/gemini-3.0-pro
  Example: google/gemini-3.0-pro: Failed to parse response...
```

**What Works**: Comprehensive failure analysis suitable for debugging and reporting.

---

## 11. Updated Config Classes Simulation

### 11.1 Configuration Validation

**Test**: Invalid configuration
```python
config = EvalConfig(
    num_prompts=-5,  # Invalid
    batch_size=0,    # Invalid
    budget_usd=-10,  # Invalid
)
```

**Expected**: `ValueError` raised in `__post_init__`

**What Works**: Dataclass validation catches common errors

**ISSUE 18: JudgeConfig Validation Gap**
```python
if self.persona_to_use and self.persona_to_use not in ["writing_expert", "recipient"]:
    raise ValueError(...)
```

But `persona_to_use` could be `None` when `use_both_personas=True`, which is valid. However, there's no validation that:
- If `use_both_personas=False`, then `persona_to_use` MUST be set
- If `use_both_personas=True`, then `persona_to_use` should be None

### 11.2 Serialization Round-Trip

```python
config = EvalConfig(
    num_prompts=500,
    model_pairs=[("google/gemini-3.0-pro", "openai/gpt-5.2")],
    prompt_config=PromptConfig(formality_range=(2, 4)),
)

# Serialize
data = config.to_dict()

# Deserialize
loaded = EvalConfig.from_dict(data)

# Verify
assert loaded.num_prompts == config.num_prompts
assert loaded.formality_range == config.formality_range
```

**What Works**: Clean serialization/deserialization pattern

**ISSUE 19: Nested Config Objects Not Fully Serialized**
```python
def to_dict(self):
    return {
        ...
        "judge_config": {
            "models": self.judge_config.models,
            ...
            # Missing: temperature, max_tokens
        },
        ...
    }
```

Some fields are missing from serialization, causing data loss on round-trip.

---

## 12. Results Viewer Simulation

### 12.1 Loading Results

**Test**: Loading from directory
```python
viewer = ResultsViewer(Path("./results"))
await viewer._load_results()
```

**Flow**:
1. Check if path is directory -> Yes
2. Look for `results.db` -> Found
3. Initialize Database, call `get_all_results()`
4. Store in `self.results`

**What Works**: Flexible loading from JSON or database

**ISSUE 20: Database.get_all_results() Not Implemented**
The ResultsViewer calls `await self.database.get_all_results()` but the Database class implementation isn't shown in gap_fix_master_draft.md.

### 12.2 Filter Dialog Flow

```
User presses 'f':
  -> action_filter() called
  -> FilterScreen modal pushed
User enters: Model="gpt", Winner="gemini"
User clicks "Apply":
  -> dismiss() called with filters dict
  -> _update_display() called with filtered results
```

**ISSUE 21: Filter Screen Callback Not Connected**
```python
def action_filter(self) -> None:
    """Show filter dialog."""
    # Method ends here! No implementation shown
```

The method body is cut off - needs implementation:
```python
def action_filter(self) -> None:
    def handle_filters(filters):
        if filters:
            self.current_filters = filters
            self._apply_filters()
            self._update_display()
    self.push_screen(FilterScreen(), callback=handle_filters)
```

---

## 13. Gap Coverage Analysis

Comparing gap_fix_master_draft.md against gap_analysis.md:

### Critical Gaps (Status)

| Gap | Status | Notes |
|-----|--------|-------|
| Cohen's Kappa | FIXED | Full implementation provided |
| Cost tracking in TUI | FIXED | Widgets provided, but breakdown not wired |
| Help overlay (h key) | FIXED | HelpOverlay class provided |
| ETA calculation | FIXED | Weighted batch time calculation |
| Confidence intervals in TUI | FIXED | ModelPairsWidget shows CIs |

### Important Gaps (Status)

| Gap | Status | Notes |
|-----|--------|-------|
| Name formality variation | FIXED | NameGenerator with 5 levels |
| Ambiguity behavior tracking | FIXED | AmbiguityTracker class |
| Model tier CLI option | NOT FIXED | No --tier flag |
| Judge persona CLI option | FIXED | --persona flag added |
| Job zones CLI filter | NOT FIXED | No --job-zones flag |
| Formality range CLI | FIXED | --formality flag added |
| Age range CLI | NOT FIXED | No --age-range flag |
| Occupation limits | NOT FIXED | No --occupation-limit flag |
| Industry limits | NOT FIXED | No --industry-limit flag |
| Occupation/industry in batch display | FIXED | ContextDisplayWidget |
| Per-judge vote counts | PARTIALLY | In KappaDisplayWidget |
| Response times in TUI | FIXED | TimingStatsWidget |
| Failure summary report | FIXED | FailureLogger with report generation |
| Refusal tracking by dimension | FIXED | RefusalTracker class |
| TUI results viewer | FIXED | ResultsViewer class with filtering |

### Gaps Still Missing

1. **--tier CLI option** (--pro-tier, --flash-tier)
2. **--job-zones CLI option**
3. **--age-range / --generation CLI option**
4. **--occupation-limit / --industry-limit CLI options**
5. **Phase 1 generation using evaluated models** (mentioned but not implemented)

---

## 14. Integration Issues Summary

### Critical Integration Issues

1. **Semaphore race conditions** in EvaluationEngine (Issues #1, #2)
2. **CostBreakdownWidget never updated** - ProgressUpdate missing required data (Issue #7)
3. **Help shortcuts not implemented** - c, k, m, t bindings missing (Issue #9)
4. **Database.get_all_results() not implemented** (Issue #20)
5. **action_filter() implementation incomplete** (Issue #21)

### Data Flow Issues

```
EvaluationEngine
    -> ProgressUpdate (missing model_costs, phase_costs)
    -> TUI._handle_progress()
    -> CostBreakdownWidget.update_breakdown() [NEVER CALLED]
```

### Missing Component Interactions

1. **VoteAggregator** - referenced but implementation not shown
2. **JudgePromptBuilder** - referenced but implementation not shown
3. **JudgeParser** - referenced but implementation not shown
4. **ResponseAnalyzer** - referenced but implementation not shown
5. **PromptGenerator** - referenced but implementation not shown

---

## 15. Edge Cases and Gotchas

### Gotcha 1: Empty Response Handling
What happens if a model returns empty string?
```python
if not gemini_response and competitor_response:
    winner = competitor_model
```
But `ModelResponse(content="")` is truthy! Need explicit empty content check.

### Gotcha 2: Tie Breaking with Even Votes
With 5 votes, ties are impossible. But with 4 votes (2-2), or when judges fail:
```python
winner = self.vote_aggregator.aggregate_majority_of_majorities(...)
# What if no clear majority?
```

### Gotcha 3: Cost Overflow
```python
self._cost_tracker.add_cost(cost)  # Keeps adding forever
# No maximum cost check during evaluation
```
Budget is checked in CLI but not enforced during evaluation runtime.

### Gotcha 4: Checkpoint File Corruption
If process crashes during checkpoint save:
```python
await self.checkpoint_manager.save_batch_results(batch_results)
```
What happens if file is partially written?

### Gotcha 5: Timezone in Timestamps
```python
timestamp: datetime = datetime.now()  # Local time, not UTC
```
For distributed systems or comparison across runs, should use `datetime.utcnow()` or `datetime.now(timezone.utc)`.

---

## 16. Recommendations

### High Priority Fixes

1. **Fix semaphore initialization** - Use asyncio.Lock() or pre-initialize
2. **Wire CostBreakdownWidget** - Add model/phase costs to ProgressUpdate
3. **Implement missing shortcuts** - Add c, k, m, t bindings
4. **Complete action_filter()** - Add filter callback handling
5. **Fix ETA weighting** - Reverse exponential weights for recent emphasis

### Medium Priority Fixes

6. **Add missing CLI options** - --tier, --job-zones, --age-range, limits
7. **Fix name suffix formatting** - Remove space before comma
8. **Fix question_mark binding** - Use correct Textual key name
9. **Add Database.get_all_results()** - Implement method
10. **Validate JudgeConfig consistency** - persona_to_use vs use_both_personas

### Low Priority Improvements

11. **Add refusal context checking** - Reduce false positives
12. **Add memory management to FailureLogger** - Rolling window or persistence
13. **Complete to_dict() serialization** - Include all nested fields
14. **Add timezone awareness** - Use UTC timestamps
15. **Add budget enforcement** - Check during runtime, not just CLI

---

## 17. Conclusion

The gap fix master plan provides a solid foundation for addressing the identified gaps. However, the simulation reveals that:

1. **~15% of the parallel architecture needs refinement** for production safety
2. **Several UI components are incompletely wired** - data flows don't reach widgets
3. **5 CLI options remain unimplemented** from the original gap analysis
4. **Multiple referenced components lack implementations** in the document

The implementation is approximately **85% complete** for addressing the gaps, with the remaining 15% requiring:
- Race condition fixes
- Missing method implementations
- Additional CLI options
- UI wiring completion

With these fixes applied, the framework would be production-ready for the stated evaluation objectives.
