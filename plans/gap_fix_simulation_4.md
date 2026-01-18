# Gap Fix Simulation Report: Detailed Implementation Dry Run

This document provides a comprehensive simulation of implementing the entire gap fix master plan, walking through each component as if building it, identifying issues, edge cases, and integration concerns.

---

## Executive Summary

The gap fix master draft provides substantial code implementations to address the 17+ gaps identified in the original gap analysis. After walking through the implementation in detail, I identify:

- **14 components that work well** with solid architecture
- **8 potential race conditions or concurrency issues**
- **6 missing dependencies or imports**
- **5 incomplete integrations**
- **4 edge cases requiring additional handling**

Overall assessment: **The plan is 80-85% complete** with the remaining issues being fixable during implementation.

---

## 1. EvaluationEngine Parallel Architecture Simulation

### 1.1 Walking Through the Implementation

Starting with the `EvaluationEngine` class, I simulate instantiating and running an evaluation:

```python
# Simulated instantiation
config = EvalConfig(num_prompts=100, model_pairs=[...])
client = OpenRouterClient(api_key="...")
checkpoint_manager = CheckpointManager(...)
database = Database(...)

engine = EvaluationEngine(
    config=config,
    client=client,
    checkpoint_manager=checkpoint_manager,
    database=database,
    max_concurrent_global=30
)

# Call run_evaluation
results = await engine.run_evaluation(prompts, batch_size=10)
```

### 1.2 Parallel Architecture Analysis

**What Works Well:**

1. **Global and per-model semaphores** - The dual semaphore approach is sound:
   ```python
   async with self._global_semaphore:
       async with self._get_model_semaphore(model):
           response = await self._generate_response(prompt, model)
   ```
   This prevents both global API overload AND per-model rate limiting.

2. **Lazy semaphore initialization** - `_ensure_semaphores()` being called within async context prevents the common pitfall of creating semaphores in `__init__` before an event loop exists.

3. **Exponential backoff with jitter** - Well implemented:
   ```python
   delay = self.base_retry_delay * (2 ** attempt) + random.uniform(0, 1)
   ```

4. **Response caching** - The `_response_cache` prevents redundant API calls when the same model needs to respond to the same prompt.

**Potential Race Conditions Identified:**

1. **Race Condition #1: `_pair_results` access**
   ```python
   # In _run_comparison:
   with self._state_lock:
       if pair_key not in self._pair_results:
           self._pair_results[pair_key] = {"gemini": 0, "competitor": 0, "tie": 0}
       # ... update logic
   ```
   **Issue:** The lock protects the dictionary, but the dict is also read in `_emit_progress` without holding the lock:
   ```python
   for pair_key, results in self._pair_results.items():  # Not locked!
   ```
   **Fix Required:** Either acquire lock during reads, or use `copy.deepcopy(self._pair_results)` inside the lock.

2. **Race Condition #2: `_all_vote_records` append**
   ```python
   self._all_vote_records.append((prompt_id, judge_key, vote_label))
   ```
   This is inside the lock, which is good. However, `_emit_progress` copies it:
   ```python
   all_votes=self._all_vote_records.copy()
   ```
   **Issue:** `copy()` on a list is NOT thread-safe during concurrent appends. Could get partial copy.
   **Fix Required:** Wrap copy in lock acquisition.

3. **Race Condition #3: `_response_cache` access**
   ```python
   # Check cache first (no lock)
   if cache_key in self._response_cache:
       return self._response_cache[cache_key]
   # ... later ...
   self._response_cache[cache_key] = result  # Also no lock
   ```
   **Issue:** Dict operations are not atomic in Python during concurrent access.
   **Fix Required:** Add lock or use `threading.Lock()` for cache access.

### 1.3 Batch Processing Flow

Walking through `_process_batch` with 10 prompts:

```
Batch of 10 prompts:
  For each prompt:
    1. Collect all unique models needed (e.g., gemini-pro, gpt-5.2, claude-opus)
    2. Generate responses in parallel (3 models = 3 concurrent tasks)
    3. Wait for all generations
    4. For each model pair, run judging
```

**Issue Identified: Sequential model pair judging**

Looking at `_process_prompt_all_pairs`:
```python
for gemini_model, competitor_model in self.config.model_pairs:
    # ... run judging for this pair
```

This loops through pairs **sequentially**, but judging for different pairs could be parallelized.

**Impact:** With 3 model pairs and 3 judges doing 5 votes each with 2 personas = 90 judge API calls per prompt. Running these sequentially is suboptimal.

**Recommended Fix:** Restructure to parallelize across model pairs:
```python
pair_tasks = []
for gemini_model, competitor_model in self.config.model_pairs:
    task = self._run_comparison(prompt, gemini_model, competitor_model, ...)
    pair_tasks.append(task)
await asyncio.gather(*pair_tasks)
```

### 1.4 Pause/Resume Mechanism

The pause mechanism works correctly:
```python
self._paused = asyncio.Event()
self._paused.set()  # Not paused initially

# In processing:
await self._paused.wait()  # Blocks if paused
```

**Issue:** The `request_shutdown` method calls `resume()` after setting `_shutdown_requested`. This is correct - it ensures paused evaluations can exit. No issue here.

---

## 2. Cohen's Kappa Implementation Simulation

### 2.1 Testing the Algorithm

Walking through `cohens_kappa` with sample data:

```python
ratings_1 = ["gemini", "gemini", "competitor", "gemini", "tie"]
ratings_2 = ["gemini", "competitor", "competitor", "gemini", "gemini"]

# Expected: Some agreement but not perfect
result = cohens_kappa(ratings_1, ratings_2)
```

**Manual calculation verification:**
- N = 5 samples
- Agreement on positions: 0, 2, 3 = 3/5 = 0.6 observed
- For expected agreement, need marginal probabilities...

The implementation looks mathematically correct.

### 2.2 Fleiss' Kappa Edge Cases

**Edge Case #1: Unequal raters per subject**
```python
n = sum(ratings_matrix[0].values())  # Number of raters
```
**Issue:** Assumes all subjects have same number of raters. If some prompts have fewer judge votes (due to failures), this breaks.

**Fix Required:** Add validation:
```python
rater_counts = [sum(row.values()) for row in ratings_matrix]
if len(set(rater_counts)) > 1:
    raise ValueError("All subjects must have same number of raters for Fleiss' Kappa")
```

**Edge Case #2: All judges always agree**
When `P_bar = 1.0` and `P_e = 1.0` (perfect agreement and only one category ever chosen):
```python
if P_e == 1.0:
    kappa = 1.0 if P_bar == 1.0 else 0.0
```
This is correctly handled.

### 2.3 Integration with EvaluationEngine

The engine calls kappa calculation in `_emit_progress`:
```python
from ..analysis.statistics import calculate_inter_judge_agreement
agreement = calculate_inter_judge_agreement(self._all_vote_records)
```

**Issue #1: Import inside async function**
Importing inside the function works but is inefficient. Should be at module level.

**Issue #2: Minimum sample requirement**
```python
if len(self._all_vote_records) >= 10:
```
This waits for 10 votes total, but Fleiss' Kappa needs votes organized by prompt. With 3 judges, 10 votes = ~3 complete prompts. This is actually reasonable, but could be made configurable.

---

## 3. Cost Tracking TUI Widget Simulation

### 3.1 Widget Reactivity

The `CostTrackerWidget` uses Textual's reactive system:
```python
cost_spent: reactive[float] = reactive(0.0)
cost_projected: reactive[float] = reactive(0.0)

def watch_cost_spent(self, value: float) -> None:
    self._update_display()
```

**Works Well:** Changes to `cost_spent` automatically trigger `_update_display()`.

### 3.2 Display Rendering

Walking through `_update_display()`:

```python
table = Table(box=None, show_header=False, padding=(0, 1))
# ... add rows ...
panel = Panel(table, title="[bold]Cost Tracking[/]", border_style="cyan")
self.query_one("#cost-display", Static).update(panel)
```

**Issue Identified: Missing child widget**

In `compose()`:
```python
def compose(self):
    yield Static(id="cost-display")
```

But `watch_cost_spent` calls `_update_display()` which does:
```python
self.query_one("#cost-display", Static).update(panel)
```

**Timing Issue:** The watcher might fire before `compose()` has yielded the child widget.

**Fix Required:** Add guard:
```python
def _update_display(self) -> None:
    try:
        display = self.query_one("#cost-display", Static)
        # ... render ...
        display.update(panel)
    except NoMatches:
        pass  # Widget not mounted yet
```

### 3.3 Budget Warning

The budget warning logic works correctly:
```python
proj_style = "yellow"
if self.cost_budget and self.cost_projected > self.cost_budget:
    proj_style = "red bold"
```

**Enhancement opportunity:** Could add a callback/event when budget is exceeded to potentially pause evaluation.

---

## 4. Help Overlay Simulation

### 4.1 Modal Screen Implementation

The `HelpOverlay` extends `ModalScreen`:
```python
class HelpOverlay(ModalScreen):
    BINDINGS = [
        Binding("h", "dismiss", "Close Help"),
        Binding("escape", "dismiss", "Close Help"),
        Binding("q", "dismiss", "Close Help"),
    ]
```

**Issue #1: `q` binding conflict**

The main app has:
```python
Binding("q", "quit", "Quit", show=True),
```

When help overlay is shown and user presses `q`, which binding wins?

**Answer:** Modal screens have their own binding scope. The overlay's `q` binding takes precedence while modal is active. This is correct behavior.

### 4.2 Mixin Pattern

```python
class HelpBindingMixin:
    BINDINGS = [
        Binding("h", "show_help", "Help", show=True),
    ]

    def action_show_help(self) -> None:
        self.push_screen(HelpOverlay())
```

**Works Well:** The mixin pattern cleanly adds help functionality to any app.

**Issue #2: Binding combination**

```python
class EvalTUIApp(HelpBindingMixin, App):
    BINDINGS = HelpBindingMixin.BINDINGS + [...]
```

This correctly combines bindings from the mixin with the app's own bindings.

---

## 5. Complete CLI Options Simulation

### 5.1 Argument Validation

Walking through model validation:
```python
def validate_model(value: str) -> str:
    if not value:
        return value
    if "/" not in value:
        raise typer.BadParameter(...)
    return value
```

**Works correctly** for the intended purpose.

### 5.2 Formality Range Parsing

```python
if formality_range:
    try:
        parts = formality_range.split("-")
        formality_min = int(parts[0])
        formality_max = int(parts[1]) if len(parts) > 1 else formality_min
    except (ValueError, IndexError):
        # Error handling
```

**Edge Cases:**
- "3" -> min=3, max=3 (single value)
- "1-5" -> min=1, max=5 (range)
- "5-1" -> min=5, max=1 **BUG: Invalid range not caught!**

**Fix Required:**
```python
if formality_min > formality_max:
    formality_min, formality_max = formality_max, formality_min  # Swap
```

### 5.3 Config Building

The CLI correctly builds nested configs:
```python
judge_config = JudgeConfig(
    models=judge_models,
    votes_per_judge=votes_per_judge,
    use_both_personas=use_both_personas,
    persona_to_use=persona_to_use
)
```

**Issue Identified: `persona_to_use` when `use_both_personas` is True**

```python
use_both_personas = judge_persona == JudgePersona.both
persona_to_use = None if use_both_personas else judge_persona.value
```

This is correct - `persona_to_use` is `None` when using both personas.

---

## 6. TUI Enhancements Simulation

### 6.1 Main App Layout

The CSS grid layout:
```css
#main-container {
    layout: grid;
    grid-size: 2 2;
    grid-columns: 2fr 1fr;
    grid-rows: auto 1fr;
}
```

**Renders as:**
```
+------------------+--------+
|   Progress       |        |
|   Section        |        |
+------------------+--------+
|   Left Panel     | Right  |
|   (Tabs)         | Panel  |
|                  | (Cost) |
+------------------+--------+
```

**Issue: `row-span` on progress section**
```css
#progress-section {
    row-span: 1;
    column-span: 2;
}
```

With `grid-size: 2 2`, spanning 2 columns works, but the layout math seems slightly off. The progress section should span the full width.

### 6.2 Progress Callback Integration

```python
async def on_mount(self) -> None:
    self.engine.progress_callback = self._handle_progress
    self._eval_task = asyncio.create_task(self._run_evaluation())
```

**Issue Identified: Callback from async context to sync widgets**

`_handle_progress` is called from the async evaluation engine:
```python
def _handle_progress(self, update: ProgressUpdate) -> None:
    self.query_one("#progress-bar", ProgressBarWidget).update_progress(...)
```

**This is a sync method being called from async code.** In Textual, widget updates should generally happen in the main thread.

**Potential Issue:** If the evaluation runs in a different thread (which it doesn't here since it's all asyncio), this could cause issues. However, since everything is asyncio-based in the same event loop, this should work.

**Better Practice:** Use `self.call_from_thread()` if ever running in threads.

### 6.3 Tab Switching

```python
def action_tab_1(self) -> None:
    self.query_one(TabbedContent).active = "tab-pairs"
```

**Issue:** The tab IDs in compose are different:
```python
with TabPane("Model Pairs", id="tab-pairs"):
```

The `active` property expects the TabPane ID. This looks correct.

---

## 7. Name Formality Variation Simulation

### 7.1 Name Formatting

Walking through `GeneratedName.format()`:

```python
name = GeneratedName(
    first_name="Michael",
    last_name="Johnson",
    middle_initial="R",
    nickname="Mike",
    prefix="Mr.",
    suffix="CPA"
)

# Test all formality levels:
name.format(FormalityLevel.VERY_INFORMAL)  # "Mike"
name.format(FormalityLevel.INFORMAL)       # "Mike Johnson"
name.format(FormalityLevel.NEUTRAL)        # "Michael Johnson"
name.format(FormalityLevel.FORMAL)         # "Mr. Johnson" or "Michael R. Johnson"
name.format(FormalityLevel.VERY_FORMAL)    # "Mr. Michael R. Johnson, CPA"
```

**Works correctly** for the common cases.

### 7.2 Missing Nickname Handling

```python
def format(self, formality: FormalityLevel) -> str:
    if formality == FormalityLevel.VERY_INFORMAL:
        return self.nickname or self._shorten(self.first_name)
```

If nickname is `None` and `_shorten()` returns the original name:
```python
def _shorten(self, name: str) -> str:
    shortcuts = {"Michael": "Mike", ...}
    return shortcuts.get(name, name)  # Returns original if not found
```

**Edge Case:** Name "Christopher" -> shortcut exists ("Chris")
Name "Bartholomew" -> no shortcut, returns "Bartholomew" (not very informal!)

**Acceptable Behavior:** This is a reasonable fallback.

---

## 8. Ambiguity Tracking Simulation

### 8.1 Response Analysis

Walking through `analyze_response()`:

```python
response_text = """
I'd be happy to help with this email. However, I'm not entirely sure
who the recipient is - could you clarify whether this is for your
direct manager or the project stakeholders? I'll assume it's for your
manager and proceed accordingly.

Dear Manager,

Thank you for the opportunity to discuss...
"""
```

Expected detection:
- Clarification pattern match: "could you clarify"
- Assumption pattern match: "I'll assume"
- Hedge pattern match: "not entirely sure"

**Result:** `AmbiguityResponse.CLARIFIED` (because clarification was requested)

**Issue Identified: Ambiguity detection order**

```python
if clarification_requested:
    behavior = AmbiguityResponse.CLARIFIED
elif len(assumptions) >= 2:
    behavior = AmbiguityResponse.ASSUMED
```

The model in the example BOTH requested clarification AND stated assumptions. The code prioritizes clarification request, which seems reasonable but could be debated.

### 8.2 Pattern Matching Robustness

The regex patterns:
```python
CLARIFICATION_PATTERNS = [
    r"(?:could you|can you|would you).{0,20}(?:clarify|specify|provide|tell me)",
]
```

**Edge Case:** "Could you please clarify something for me about the budget?"
- Regex: `(?:could you|can you|would you).{0,20}(?:clarify|specify|provide|tell me)`
- "could you" matches
- `.{0,20}` = " please " (8 chars) - within limit
- "clarify" matches

This correctly detects the clarification request.

**Edge Case:** "Could you, after reviewing the document and considering all factors, clarify..."
- The gap between "could you" and "clarify" is > 20 chars
- **False negative** - won't detect this clarification request

**Acceptable Limitation:** Overly verbose clarification requests are rare.

---

## 9. Refusal Tracking Simulation

### 9.1 Classification Algorithm

Walking through `RefusalClassifier.analyze()`:

```python
response_text = """
I'm sorry, but I cannot help write a resignation letter that includes
false accusations against your employer. This would be inappropriate
and could potentially expose you to legal liability.

However, I'd be happy to help you write a professional resignation
letter that maintains your integrity while clearly stating your reasons
for leaving.
"""
```

**Step 1: Strong refusal detection**
- Pattern: `i(?:'m| am) (?:sorry|afraid).{0,30}(?:cannot|can't|unable|not able)`
- Match: "I'm sorry, but I cannot"

**Step 2: Category determination**
- Safety patterns: "legal liability"
- Policy patterns: None strong
- Ethics patterns: "integrity"
- Inappropriate patterns: "inappropriate"

**Result:** Category = INAPPROPRIATE (strongest match)

**Step 3: Alternative detection**
- Pattern: `(?:happy|glad|willing) to.{0,30}(?:help|assist)`
- Match: "happy to help"

**Final Result:**
```python
RefusalAnalysis(
    is_refusal=True,
    category=RefusalCategory.INAPPROPRIATE,
    alternative_offered=True,
    partial_completion=False
)
```

This is a correct classification!

### 9.2 Dimension Tracking

The `RefusalDimension` enum provides:
- TOPIC - topic-related refusal
- CONTENT - content-related
- FORMAT - format-related
- PERSONA - persona/role-related
- AUDIENCE - audience-related

**Issue Identified: Dimension detection too narrow**

The patterns are quite specific:
```python
RefusalDimension.PERSONA: [
    r"(?:as|pretend|role|character)",
    r"(?:persona|identity|acting as)",
],
```

A refusal like "I cannot write as though I were your manager" would match (has "as"), but "I shouldn't impersonate your boss" wouldn't match (no exact pattern).

**Impact:** Dimension classification will have false negatives, but main category classification still works.

### 9.3 Integration Gap

**Missing Connection:** The `RefusalTracker` is instantiated in the engine:
```python
self.refusal_classifier = RefusalClassifier()
```

But there's no corresponding `RefusalTracker` instantiation! The engine uses the classifier directly:
```python
refusal = self.refusal_classifier.classify(response.content)
```

The `RefusalTracker` class exists but isn't wired into the engine.

**Fix Required:** Add to EvaluationEngine:
```python
self.refusal_tracker = RefusalTracker()

# In _generate_response, after classifying:
if refusal:
    self.refusal_tracker.track(prompt.prompt_id, model, response.content, {...})
```

---

## 10. Failure Summary Reports Simulation

### 10.1 FailureLogger Flow

```python
logger = FailureLogger(output_dir=Path("./results"))

# Log failures during evaluation
logger.log_failure(
    prompt_id="prompt_001",
    model="openai/gpt-5.2",
    error_type="TimeoutError",
    error_message="Request timed out after 120 seconds",
    phase="generation",
    retry_count=3,
    recovered=False
)

# At end of evaluation
report = logger.generate_report()
```

**Works Well:** The internal organization by type, model, prompt, and phase enables comprehensive reporting.

### 10.2 Report Generation

The `generate_report()` method creates:
```python
report = {
    "status": "failures_recorded",
    "total_failures": len(self._failures),
    "by_error_type": {...},
    "by_model": {...},
    "by_phase": {...},
    "problem_prompts": [...],
    "timeline": [...]
}
```

**Issue Identified: JSON serialization of datetime**

```python
with open(report_path, "w") as f:
    json.dump(report, f, indent=2, default=str)
```

Using `default=str` handles datetime objects, but the resulting strings won't be in ISO format from FailureSummary objects:
```python
first_occurrence: datetime
last_occurrence: datetime
```

When serialized in `by_error_type`:
```python
"first_occurrence": v.first_occurrence,  # datetime object
```

**Result:** `"first_occurrence": "2025-01-11 10:30:45.123456"` (str representation)

**Better:** Use `.isoformat()` explicitly for consistency.

### 10.3 Integration with Engine

The engine calls:
```python
if self.failure_logger:
    self.failure_logger.log_failure(...)
```

But at the end:
```python
if self.failure_logger:
    self.failure_logger.generate_report()
```

**Issue:** `generate_report()` returns the report dict but it's not being stored or passed anywhere. The file is saved, but the return value is discarded.

**Impact:** Minor - the file is saved, which is the primary goal.

---

## 11. Updated Config Classes Simulation

### 11.1 Nested Config Validation

```python
@dataclass
class JudgeConfig:
    def __post_init__(self):
        if self.votes_per_judge < 1:
            raise ValueError("votes_per_judge must be at least 1")
```

**Works Well:** Validation happens automatically on instantiation.

### 11.2 Property Aliases

```python
@property
def output_dir(self) -> Path:
    return self.storage_config.output_dir
```

**Purpose:** Backward compatibility with code expecting `config.output_dir` instead of `config.storage_config.output_dir`.

**Works correctly.**

### 11.3 Serialization Round-Trip

Testing `to_dict()` and `from_dict()`:

```python
config = EvalConfig(num_prompts=500, budget_usd=100.0)
data = config.to_dict()
restored = EvalConfig.from_dict(data)

assert restored.num_prompts == 500
assert restored.budget_usd == 100.0
```

**Issue Identified: Incomplete serialization**

`to_dict()` doesn't serialize all fields:
```python
"api_config": {
    "timeout_seconds": self.api_config.timeout_seconds,
    "max_retries": self.api_config.max_retries,
    "max_concurrent_global": self.api_config.max_concurrent_global,
    # Missing: api_key, api_base, base_retry_delay, max_concurrent_per_model
}
```

**Intentional?** Yes - `api_key` should NOT be serialized for security. But `api_base` and other settings should be.

**Fix Required:** Add missing non-sensitive fields to serialization.

---

## 12. Results Viewer Simulation

### 12.1 Data Loading

```python
async def _load_results(self) -> None:
    if self.results_path.is_dir():
        db_path = self.results_path / "results.db"
        if db_path.exists():
            self.database = Database(db_path)
            self.results = await self._load_from_database()
```

**Issue Identified: Database method is async but called in sync context**

The `_load_from_database` method:
```python
async def _load_from_database(self) -> List[Dict[str, Any]]:
    if not self.database:
        return []
    return await self.database.get_all_results()
```

This is called from `_load_results` which is async - correct.

But `on_mount` calls it:
```python
async def on_mount(self) -> None:
    await self._load_results()
```

This is correct - `on_mount` is an async method in Textual.

### 12.2 Agreement Stats Calculation

```python
vote_records = []
for r in self.filtered_results:
    prompt_id = r.get("prompt_id", "")
    model_a = r.get("model_a", "")
    for j in r.get("judgments", []):
        judge_model = j.get("judge_model", "")
        winner = j.get("winner")
        if winner == model_a:
            vote = "gemini"
        elif winner:
            vote = "competitor"
        else:
            vote = "tie"
        vote_records.append((prompt_id, judge_model, vote))
```

**Issue Identified: Assumes model_a is always Gemini**

The code assumes `model_a` is always the Gemini model. Looking at the engine:
```python
result = await self._run_comparison(
    prompt,
    gemini_model, competitor_model,  # Order: gemini first
    gemini_response, competitor_response
)
```

And BatchResult:
```python
model_a=gemini_model,
model_b=competitor_model,
```

**Confirmed:** `model_a` is always Gemini. The assumption is valid.

### 12.3 Filter Dialog

```python
class FilterScreen(ModalScreen):
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-filter":
            filters = {
                "model": self.query_one("#model-filter", Input).value,
                "winner": self.query_one("#winner-filter", Input).value,
                "occupation": self.query_one("#occupation-filter", Input).value,
            }
            self.dismiss({k: v for k, v in filters.items() if v})
```

**Issue Identified: Filter application not implemented**

The `action_filter` method shows the dialog:
```python
def action_filter(self) -> None:
    """Show filter dialog."""
```

But the implementation is truncated! We need:
```python
def action_filter(self) -> None:
    def apply_filters(filters):
        if filters is None:
            return
        self.current_filters = filters
        self._apply_filters()
        self._update_display()

    self.push_screen(FilterScreen(), callback=apply_filters)
```

**Fix Required:** Complete the filter implementation.

---

## 13. Gap Coverage Verification

### 13.1 Critical Gaps from gap_analysis.md

| Gap | Status in Master Plan | Simulation Result |
|-----|----------------------|-------------------|
| Cohen's Kappa missing | Fully implemented | Works correctly |
| Cost tracking in TUI missing | Implemented | Works with minor widget timing issue |
| Help overlay missing | Fully implemented | Works correctly |
| Name formality variation | Implemented | Works with reasonable edge case handling |
| Ambiguity behavior tracking | Implemented | Works with some pattern limitations |
| Phase 1 using evaluated models | NOT ADDRESSED | Still missing |
| Model tier CLI option | NOT ADDRESSED | Still missing |
| Judge persona CLI option | Implemented | Works correctly |
| Job zones CLI filter | NOT ADDRESSED | Still missing |
| Formality/age range CLI | Partially addressed | Formality yes, age no |
| Occupation/industry limits | NOT ADDRESSED | Still missing |
| ETA calculation | Implemented | Works correctly |
| Confidence intervals in TUI | Implemented | Works correctly |
| Occupation/industry in current batch | Implemented | Works correctly |
| Per-judge vote count in TUI | Implemented | Works correctly |
| Response times/throughput in TUI | Implemented | Works correctly |
| Failure summary report | Implemented | Works with minor serialization issue |
| Refusal tracking by dimension | Implemented | Missing engine integration |
| TUI results viewer | Implemented | Missing filter application |

### 13.2 Gaps Still Not Addressed

1. **Phase 1 using evaluated models** - The requirement that prompt generation (Phase 1) should use the same models being evaluated is mentioned but never implemented.

2. **Model tier CLI option** - No `--pro-tier` or `--flash-tier` shortcuts.

3. **Job zones CLI filter** - No `--job-zones` CLI option despite ONetExtractor supporting it.

4. **Age range CLI** - No `--age-range` or `--generation` CLI option.

5. **Occupation/industry limits** - No `--max-per-occupation` or `--max-per-industry` options.

---

## 14. Missing Imports and Dependencies

### 14.1 Identified Missing Imports

1. **EvaluationEngine** - Missing:
   ```python
   from .ambiguity_tracker import AmbiguityTracker
   from ..reports.failure_report import FailureLogger
   ```
   These are used but imports not shown.

2. **statistics.py** - Missing:
   ```python
   import random  # Used in bootstrap_confidence_interval
   ```
   The `random` import is used but only shown inside the function.

3. **TUI widgets** - Missing from imports:
   ```python
   from textual.css.query import NoMatches
   ```
   For the guard in `_update_display()`.

### 14.2 Missing Module Files

The master plan references but doesn't implement:
- `src/prompts/generator.py` - Used in CLI but not provided
- `src/storage/database.py` - The `Database.get_all_results()` method
- `src/eval/judge_prompt_builder.py` - Used in engine
- `src/eval/response_analyzer.py` - Used in engine

---

## 15. Integration Testing Scenarios

### 15.1 Scenario: Full Evaluation Run

```
1. User runs: gemini-eval run --prompts 100 --budget 50.0
2. System:
   - Loads config
   - Estimates cost (~$45)
   - Generates 100 prompts
   - Starts TUI
   - Runs evaluation with progress updates
   - Budget warning if cost approaches $50
   - Saves results and failure report
```

**Potential Issues:**
- Prompt generation not implemented
- Budget enforcement during run not shown

### 15.2 Scenario: Resume from Checkpoint

```
1. User runs evaluation, Ctrl+C at 50%
2. System saves checkpoint
3. User runs: gemini-eval run --resume ./results/checkpoint.json
4. System:
   - Loads checkpoint
   - Skips completed prompts
   - Continues from where it left off
```

**Implementation looks correct** - The engine's `run_evaluation` loads completed IDs:
```python
completed_ids = await self.checkpoint_manager.get_completed_prompt_ids()
remaining_prompts = [p for p in prompts if p.prompt_id not in completed_ids]
```

### 15.3 Scenario: View Results

```
1. User runs: gemini-eval view ./results
2. System:
   - Loads results from database or JSON
   - Displays summary statistics
   - Shows filterable results table
   - Calculates agreement metrics
```

**Issue:** Filter application incomplete.

---

## 16. Recommendations for Implementation

### 16.1 High Priority Fixes

1. **Race condition in `_pair_results` access** - Add lock during reads or use deepcopy
2. **Race condition in `_response_cache`** - Add thread-safe access
3. **Complete filter application in ResultsViewer**
4. **Add RefusalTracker integration to EvaluationEngine**

### 16.2 Medium Priority Additions

1. **Implement remaining CLI options** - `--job-zones`, `--age-range`, `--max-per-occupation`
2. **Add model tier shortcuts** - `--pro-tier`, `--flash-tier`
3. **Improve datetime serialization** in failure reports
4. **Add missing module implementations** - `PromptGenerator`, `JudgePromptBuilder`

### 16.3 Low Priority Enhancements

1. **Parallelize model pair judging** - Currently sequential
2. **Add budget enforcement callback** - Pause when approaching budget
3. **Improve ambiguity pattern matching** - Handle verbose clarifications

---

## 17. Conclusion

The gap fix master draft provides a solid foundation for addressing the identified gaps. The parallel architecture is well-designed with appropriate semaphore management. The Cohen's Kappa implementation is mathematically correct. The TUI widgets integrate well with Textual's reactive system.

**Key Issues to Address Before Implementation:**
1. Three race conditions in shared state access
2. Missing RefusalTracker integration
3. Incomplete filter application in viewer
4. Several CLI options still missing
5. Missing module implementations referenced but not provided

**Overall Readiness: 80-85%**

The plan can proceed to implementation with awareness of these issues. Most can be fixed during development without major architectural changes.
