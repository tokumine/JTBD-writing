# Simulation Report 6: Master Plan Implementation Dry Run

## Executive Summary

This document presents a detailed simulation of implementing the master plan for the Gemini Writing Evaluation Framework. I walked through each component as if building it, documenting what works well, identifying gaps, noting edge cases, and flagging inconsistencies with PROMPT.md requirements.

**Overall Assessment**: The master plan is comprehensive and well-structured, but has several implementation gaps and potential issues that need addressing before production use. The core architecture is sound, but some critical details are missing or underspecified.

---

## 1. O*NET Data Integration Simulation

### 1.1 Attempting to Load ONET_WRITING_REFERENCE.md

**Simulation Steps**:
1. Navigate to `db/ONET_WRITING_REFERENCE.md`
2. Parse the pre-processed writing tasks
3. Extract task IDs and writing contexts

**What Works Well**:
- The plan correctly relies on the pre-processed reference file rather than raw O*NET queries
- Avoiding hardcoded categories aligns with PROMPT.md requirements

**Issues Identified**:

**CRITICAL GAP**: The master plan references `db/ONET_WRITING_REFERENCE.md` but never specifies:
- The exact format of this file (JSON? Markdown tables? YAML?)
- The expected fields and their names
- How to handle parsing errors

**Proposed Fix**: The plan should include a schema definition for ONET_WRITING_REFERENCE.md:
```python
@dataclass
class ONetWritingTask:
    task_id: str
    onetsoc_code: str  # e.g., "11-1011.00"
    occupation_title: str
    task_statement: str
    job_zone: int
    writing_relevance_score: float  # How relevant to writing (0-1)
    writing_context: str  # Why this task involves writing
```

**Edge Case**: What happens if ONET_WRITING_REFERENCE.md doesn't exist? The plan should fall back to direct O*NET database queries.

### 1.2 O*NET Database Access

**Simulation Steps**:
1. Connect to `db/onet.db` SQLite database
2. Query occupation and task tables
3. Map to prompt schema

**Issues Identified**:

**GAP**: The `ONetExtractor` class in the plan reads from `ONET_WRITING_REFERENCE.md` but the database schema queries assume direct SQLite access. These two approaches conflict.

**GAP**: The plan mentions O*NET 30.1 but doesn't verify the actual table structure. Different O*NET versions have different schemas.

**Verification Needed**: The plan should include validation:
```python
async def verify_onet_schema(self):
    """Verify O*NET database has expected tables."""
    required_tables = ['occupation_data', 'task_statements', 'job_zones']
    # Check each table exists
```

---

## 2. Three-Phase Prompt Generation Simulation

### 2.1 Phase 1: Offline LLM Generation

**Simulation Steps**:
1. Load all writing-relevant O*NET tasks
2. For each task, call each evaluated model to generate 5 persona variations
3. Cache results in `data/offline_variations/`

**What Works Well**:
- Using ALL evaluated models for generation avoids single-model bias
- Caching prevents redundant API calls
- Tracking `generated_by_model` enables bias analysis

**Issues Identified**:

**CRITICAL COST CONCERN**:
- If there are ~20,000 writing tasks and we use 6 models generating 5 variations each:
- 20,000 tasks × 6 models × 1 API call = 120,000 API calls just for Phase 1
- At ~$0.02 per call average, this is ~$2,400 before any evaluation starts

**PROMPT.md INCONSISTENCY**: PROMPT.md says "Use an LLM to generate diverse persona/context variations for each O*NET task. This is done as an offline preprocessing step." It doesn't specify using ALL evaluated models - this is an interpretation.

**Edge Cases**:
- What if one model refuses to generate for a task? Plan handles with try/except but should track refusal patterns
- What if JSON parsing fails? Plan has basic handling but no retry with different prompt

**Missing Implementation**:
```python
# Plan doesn't show how to handle model-specific generation limits
GENERATION_BATCH_SIZE = 50  # Models may have limits on concurrent requests
GENERATION_RATE_LIMIT = 60  # RPM limit for generation phase
```

### 2.2 Phase 2: Algorithmic Combination

**Simulation Steps**:
1. Load pre-generated variations from cache
2. Sample tasks with stratification
3. Combine with company/name data
4. Build WritingPrompt objects

**What Works Well**:
- Deterministic seeded random for reproducibility
- Stratification by job zone and SOC group ensures diversity
- Falls back to algorithmic generation if no cached variations

**Issues Identified**:

**GAP**: The `CompanyDatabase` and `NameGenerator` classes are referenced but not fully specified. The plan mentions:
- "500+ real companies" but doesn't provide the data source
- "Census-based diverse names" but doesn't specify the Census dataset

**PROMPT.md REQUIREMENT**: "Use real company names using your built in knowledge" - but the plan relies on a static `companies.json` file. How is this file populated?

**Missing Data Files**:
```
data/
├── companies.json    # Not specified how to create
├── names_census.json # Not specified source
```

**Stratification Edge Case**: If job zone 5 has very few tasks and num_prompts is high, stratification will undersample other zones:
```python
# Current implementation
per_zone = num_prompts // 5  # Could be 100 per zone
# But zone 5 might only have 50 tasks
```

### 2.3 Phase 3: LLM Enrichment

**Simulation Steps**:
1. Select 30% of prompts for enrichment
2. For each, generate prior messages, attachments, competing objectives, etc.
3. Build final prompt text

**What Works Well**:
- Using multiple enrichment types adds diversity
- Temporal grounding uses the correct date (Jan 6, 2026 per PROMPT.md)
- Probability-based selection for different enrichment types

**Issues Identified**:

**CRITICAL BUG**: The `_add_temporal_context` method is defined as `async` but doesn't await anything:
```python
async def _add_temporal_context(self, prompt: WritingPrompt) -> dict:
    # No await statements - this could just be sync
```

**Edge Case**: The enrichment ratio of 0.3 is hardcoded. Should be configurable in EvalConfig.

**Missing from Plan**: How to handle enrichment failures gracefully:
```python
# What if LLM returns invalid format?
# What if network times out during enrichment?
# Should partially enriched prompts be used?
```

---

## 3. Prompt Schema Simulation

### 3.1 WritingPrompt Completeness Check

**Verification Against PROMPT.md Requirements**:

| PROMPT.md Requirement | Schema Field | Status |
|----------------------|--------------|--------|
| User personas | `writer: WriterPersona` | ✅ Present |
| Ages/skill levels | `writer.age`, `writer.skill_level` | ✅ Present |
| Formality/casualness | `formality_level` | ✅ Present |
| End users/recipients | `recipients` | ✅ Present |
| Urgency levels | `urgency_level` | ✅ Present |
| Relationship context | `recipients[0].relationship` | ✅ Present |
| Audience size | `audience_size` | ✅ Present |
| Emotional context | `emotional_context` | ✅ Present |
| Message position | `message_position` | ✅ Present |
| Temporal context | `temporal_context` | ✅ Present |
| Attachments | `attachments` | ✅ Present |
| Competing objectives | `competing_objectives` | ✅ Present |
| Regional English | `english_variant`, `recipient_english_variant` | ✅ Present |
| Reply-to context | `prior_context` | ✅ Present |
| CC situations | `cc_context` | ✅ Present |
| Tone matching | `tone_example` | ✅ Present |
| Revision tasks | `revision_task`, `is_revision_task` | ✅ Present |
| Ambiguity handling | `is_ambiguous`, `ambiguity_type` | ✅ Present |
| Constraints | `constraints` | ✅ Present |
| Sensitive topics | `sensitive_topics` | ✅ Present |
| Language support | `language`, `language_variant` | ✅ Present |

**All PROMPT.md diversity dimensions are covered in the schema.**

**Issues Identified**:

**Type Inconsistency**:
- `formality_level` is `int` (1-5) but some code references string values
- `urgency_level` is `int` but some places use string like "high", "low"

**Missing Validation**:
```python
# Schema should validate these are consistent
@validator('formality_level')
def validate_formality(cls, v):
    if not 1 <= v <= 5:
        raise ValueError("formality_level must be 1-5")
    return v
```

---

## 4. API Client and Rate Limiting Simulation

### 4.1 OpenRouter Client

**Simulation Steps**:
1. Initialize async HTTP client
2. Make API calls with retry logic
3. Handle rate limits and errors

**What Works Well**:
- Uses httpx for async HTTP (correct library choice)
- Per-model rate limiting accounts for different OpenRouter limits
- Circuit breaker pattern prevents cascade failures

**Issues Identified**:

**CRITICAL GAP**: The OpenRouter client code is referenced but never fully implemented:
```python
# src/api/openrouter_client.py
# Plan shows usage but not the actual client implementation:
response = await self.api_client.complete(
    model=model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.9
)
```

**Missing Implementation Details**:
- OpenRouter API endpoint URL
- Authentication header format
- Request/response type definitions
- Streaming support
- Token counting before requests

**PROMPT.md REQUIREMENT**: "Use OpenRouter API as unified interface to all models" - Plan correctly uses OpenRouter but doesn't specify:
- How to handle OpenRouter-specific error codes
- How to parse OpenRouter's cost reporting
- How to get current pricing for cost estimates

### 4.2 Rate Limiter

**Issues Identified**:

**GAP**: Rate limiter mentioned but no implementation shown. Need:
```python
class RateLimiter:
    def __init__(self, rpm: int, tpm: int):
        self.rpm = rpm
        self.tpm = tpm
        self.request_times = []
        self.token_times = []

    async def acquire(self, estimated_tokens: int):
        # Wait if we'd exceed limits
        pass
```

**Model-Specific Limits Not Documented**: The plan says "model-specific limits from OpenRouter documentation" but doesn't list what those limits are.

### 4.3 Circuit Breaker

**What Works Well**:
- Circuit breaker state is persisted in checkpoints for crash recovery
- Standard half-open state for testing recovery

**Issues Identified**:

**GAP**: Circuit breaker implementation not shown in plan. Key missing pieces:
- State transitions (closed -> open -> half-open -> closed)
- Failure threshold configuration
- Recovery timeout
- Per-model circuit breaker instances

---

## 5. Evaluation Engine Simulation

### 5.1 Response Generation

**Simulation Steps**:
1. For each prompt, call each model in the pair
2. Collect responses with metadata
3. Handle failures (timeout, refusal, error)

**What Works Well**:
- Auto-loss for failures aligns with PROMPT.md
- Response metadata tracking (tokens, latency, format detection)
- Refusal categorization for deeper analysis

**Issues Identified**:

**MISSING**: Format detection implementation:
```python
# Plan references but doesn't implement:
has_bullets: bool = ...
has_headers: bool = ...
greeting_type: str = ...
signoff_type: str = ...
```

**Need regex patterns for detection**:
```python
BULLET_PATTERN = r'^[\s]*[-*•]\s+'
HEADER_PATTERN = r'^#{1,6}\s+|^[A-Z][^.]*:$'
GREETING_PATTERNS = {
    'formal': r'^Dear\s+',
    'semiformal': r'^Hi\s+|^Hello\s+',
    'casual': r'^Hey\s+'
}
```

### 5.2 Judge System

**Simulation Steps**:
1. Build judge prompt with full context
2. Call each judge model 5 times
3. Parse responses and aggregate votes

**What Works Well**:
- Full scenario context provided to judges (addressing PROMPT.md requirement)
- Two personas: Writing Expert and Simulated Recipient
- Position randomization with deterministic seeding

**Issues Identified**:

**CRITICAL BUG in VoteAggregator**:
```python
def aggregate_for_judge(self, votes: List[JudgeVote]) -> Literal["gemini", "competitor", "tie"]:
    # ...
    if gemini_count >= 3:
        return "gemini"
    elif competitor_count >= 3:
        return "competitor"
    else:
        # This logic is wrong for best-of-5
        # If votes are [gemini, gemini, tie, tie, tie], gemini_count=2
        # But gemini should win (2 > 0)
```

**Fix needed**:
```python
def aggregate_for_judge(self, votes: List[JudgeVote]) -> Literal["gemini", "competitor", "tie"]:
    gemini_count = sum(1 for v in votes if v.winner == "gemini")
    competitor_count = sum(1 for v in votes if v.winner == "competitor")

    # Need majority of decisive votes
    if gemini_count > competitor_count:
        return "gemini"
    elif competitor_count > gemini_count:
        return "competitor"
    else:
        return "tie"
```

**PROMPT.md Inconsistency**: The plan has judges output QUALITY_A and QUALITY_B (1-10) but these are never used in aggregation. They're stored but not analyzed.

### 5.3 Judge Prompt Parsing

**Simulation Steps**:
1. Receive judge response text
2. Parse structured output (WINNER, CONFIDENCE, etc.)
3. Handle malformed responses

**Issues Identified**:

**CRITICAL GAP**: No parser implementation shown. The plan expects:
```
WINNER: A
CONFIDENCE: 4
QUALITY_A: 8
QUALITY_B: 6
REASONING: Response A was more concise...
```

**Missing parser**:
```python
def parse_judge_response(response_text: str) -> Optional[JudgeVote]:
    """Parse judge output. Returns None if parsing fails."""
    lines = response_text.strip().split('\n')
    result = {}
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            result[key.strip().upper()] = value.strip()

    # Validate required fields
    if 'WINNER' not in result:
        return None

    # ... more validation
```

**Edge Cases Not Handled**:
- Judge says "Response B wins" instead of "WINNER: B"
- Judge includes extra text before/after the structured output
- Judge uses different formatting (markdown, etc.)

---

## 6. Checkpoint and Resumability Simulation

### 6.1 Checkpoint Manager

**Simulation Steps**:
1. Save state after each vote
2. Handle graceful shutdown (Ctrl+C)
3. Resume from checkpoint after crash

**What Works Well**:
- Atomic writes using temp file + rename
- Fine-grained vote-level checkpointing
- Partial comparison state for mid-comparison resume

**Issues Identified**:

**GAP**: Signal handler not implemented:
```python
# Plan mentions "Ctrl+C saves state" but doesn't show implementation
import signal

def setup_signal_handlers(checkpoint_manager: CheckpointManager):
    async def handle_shutdown(signum, frame):
        await checkpoint_manager.save()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
```

**Edge Case**: What if crash happens DURING atomic write?
- Temp file may be left behind
- Need cleanup logic on startup

### 6.2 Resume Logic

**Issues Identified**:

**CRITICAL GAP**: Resume command shown but resume logic not implemented:
```python
# CLI shows:
./eval --resume results/eval_2024-01-15_14-30-00/

# But how does the engine use checkpoint state?
class EvaluationEngine:
    async def run(self):
        # Need to check checkpoint for each operation
        for prompt_id, prompt in prompts.items():
            for pair in model_pairs:
                comparison_id = f"{prompt_id}_{pair}"
                if self.checkpoint.is_comparison_complete(comparison_id):
                    continue  # Skip completed

                partial = self.checkpoint.get_partial_comparison(comparison_id)
                if partial:
                    # Resume from partial state
                    existing_votes = partial.get('votes', [])
                    # ... continue from where we left off
```

---

## 7. Storage and Database Simulation

### 7.1 SQLite Schema

**What Works Well**:
- Comprehensive schema covering all entities
- Appropriate indexes for common queries
- Foreign key relationships for data integrity

**Issues Identified**:

**Type Mismatch**: Schema stores `emotional_context` as TEXT but Python uses Enum:
```sql
emotional_context TEXT NOT NULL,  -- Stores "routine", "crisis", etc.
```
This works but loses type safety on retrieval.

**Missing Columns**:
- `sensitive_topics` should be a separate table for proper normalization
- `constraints` need their own table (one prompt can have multiple)

**Schema Addition Needed**:
```sql
CREATE TABLE IF NOT EXISTS prompt_constraints (
    constraint_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    constraint_type TEXT NOT NULL,
    description TEXT NOT NULL,
    specific_requirement TEXT NOT NULL,
    is_compliant INTEGER,  -- NULL until checked
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);

CREATE TABLE IF NOT EXISTS prompt_sensitive_topics (
    prompt_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    PRIMARY KEY (prompt_id, topic),
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);
```

### 7.2 Run Directory Structure

**Verification Against PROMPT.md**:

| PROMPT.md Requirement | Plan Implementation | Status |
|----------------------|---------------------|--------|
| config.json | ✅ RunDirectory.config_json | Present |
| config_summary.txt | ✅ RunDirectory.config_summary_txt | Present |
| checkpoint.json | ✅ RunDirectory.checkpoint_json | Present |
| random_seed.txt | ✅ RunDirectory.random_seed_txt | Present |
| prompts/prompts.json | ✅ RunDirectory.prompts_json | Present |
| prompts/prompts_by_occupation/ | ✅ organize_prompts_by_occupation() | Present |
| prompts/prompts_by_industry/ | ✅ organize_prompts_by_industry() | Present |
| responses/by_prompt/ | ✅ Directory created | Present |
| responses/by_model/ | ✅ Directory created | Present |
| judgments/raw/ | ✅ Directory created | Present |
| judgments/aggregated/ | ✅ Directory created | Present |
| results.db | ✅ RunDirectory.results_db | Present |
| results_summary.csv | ✅ RunDirectory.results_csv | Present |
| analysis/*.json | ✅ Directory created | Present |
| reports/report.pdf | ✅ RunDirectory.full_report_pdf | Present |
| reports/executive_summary.md | ✅ RunDirectory.executive_summary_md | Present |
| reports/charts/ | ✅ Directory created | Present |
| logs/run.log | ✅ RunDirectory.run_log | Present |
| logs/failures.log | ✅ RunDirectory.failures_log | Present |
| logs/timing.log | ✅ RunDirectory.timing_log | Present |
| README.md | ✅ RunDirectory.readme_md | Present |
| latest symlink | ✅ _create_latest_symlink() | Present |

**All PROMPT.md directory requirements are met.**

---

## 8. Analysis Module Simulation

### 8.1 Statistical Analysis

**What Works Well**:
- Uses scipy.stats.binomtest (not deprecated binom_test)
- Wilson score intervals for confidence intervals
- Cohen's Kappa for inter-rater reliability
- Cohen's h for effect size

**Issues Identified**:

**PROMPT.md Requirement Not Fully Implemented**:
> "Win rates with confidence intervals" - Present
> "Statistical significance testing" - Present
> "Inter-judge agreement metrics (Cohen's Kappa or similar)" - Present
> "Position bias detection and mitigation" - Partially present (detection but not mitigation)

**Mitigation Gap**: The plan detects position bias but doesn't show how to MITIGATE it:
```python
# Mitigation could be:
# 1. Exclude biased judge from analysis
# 2. Apply correction factor
# 3. Re-run with different position assignments
def mitigate_position_bias(comparisons, bias_result):
    if not bias_result.detected:
        return comparisons

    # Option 1: Weight by position
    # If A wins 60% when shown first, apply 0.83 weight to A wins
    correction_factor = 0.5 / (bias_result.a_win_rate)
    # ...
```

### 8.2 Bias Detection

**Verification Against PROMPT.md**:

| Bias Type | Status | Notes |
|-----------|--------|-------|
| Position bias | ✅ Implemented | detect_position_bias() |
| Length bias | ✅ Implemented | detect_length_bias() |
| Model fingerprinting | ✅ Implemented | detect_model_fingerprinting() |
| Formality drift | ✅ Implemented | detect_formality_drift() |
| Format bias | ❌ Missing | "Does one model overuse certain structures?" |

**Missing Format Bias Detection**:
```python
def detect_format_bias(self, responses: List[Dict]) -> BiasResult:
    """Detect if one model overuses bullet points, headers, etc."""
    format_usage = {"gemini": {"bullets": 0, "headers": 0},
                    "competitor": {"bullets": 0, "headers": 0}}

    for r in responses:
        model = "gemini" if r["model_type"] == "gemini" else "competitor"
        if r["has_bullets"]:
            format_usage[model]["bullets"] += 1
        if r["has_headers"]:
            format_usage[model]["headers"] += 1

    # Statistical test for difference...
```

### 8.3 Weakness Finder

**Issues Identified**:

**CRITICAL GAP**: Weakness finder is mentioned in project structure but never implemented:
```
src/analysis/weakness_finder.py     # Systematic weakness identification
```

**PROMPT.md Requirement**:
> "Identifies specific areas of weakness in Gemini effective writing vs its peers"
> "Task-specific competence: Which specific job types or writing tasks does Gemini struggle with?"

**Needed Implementation**:
```python
class WeaknessFinder:
    """Identify systematic weaknesses in Gemini performance."""

    async def find_weaknesses(self, db: ResultsDatabase) -> List[Weakness]:
        weaknesses = []

        # 1. Find occupations where Gemini loses most
        occ_results = await db.get_win_rates_by_dimension("occupation_code")
        for r in occ_results:
            if r["win_rate"] < 0.4 and r["total"] >= 10:
                weaknesses.append(Weakness(
                    dimension="occupation",
                    value=r["dimension_value"],
                    win_rate=r["win_rate"],
                    sample_size=r["total"],
                    significance=self._calculate_significance(r)
                ))

        # 2. Find formality levels where Gemini struggles
        # 3. Find emotional contexts where Gemini struggles
        # 4. Find writing types where Gemini struggles

        return sorted(weaknesses, key=lambda w: w.win_rate)
```

---

## 9. TUI Implementation Simulation

### 9.1 Progress Dashboard

**What Works Well**:
- Uses Textual for modern TUI
- Shows all required progress elements from PROMPT.md
- Interactive controls (q, p, d, s, h)

**Issues Identified**:

**PROMPT.md Layout Comparison**:
The PROMPT.md shows a specific layout with:
- Overall progress with phases
- Per-model-pair progress bars with running win rates
- Current batch details with response/judging status
- Live statistics
- Activity log
- Error summary

**Plan Gaps**:
1. No per-model-pair progress bars (only one main progress bar)
2. No phase indicator (Generation -> Judging -> Analysis)
3. No current batch details showing individual response/judging status
4. Activity log present but doesn't match PROMPT.md format

**Missing TUI Components**:
```python
# Need model pair progress widget
class ModelPairProgress(Static):
    """Progress for a single model pair."""

    def __init__(self, gemini_model: str, competitor_model: str):
        self.gemini = gemini_model
        self.competitor = competitor_model
        self.completed = 0
        self.total = 0
        self.gemini_wins = 0
        self.competitor_wins = 0

    def render(self) -> str:
        bar = "█" * int(20 * self.completed / self.total) + "░" * (20 - int(20 * self.completed / self.total))
        win_pct = self.gemini_wins / (self.gemini_wins + self.competitor_wins) if self.completed > 0 else 0
        return f"{self.gemini} vs {self.competitor} {bar} {self.completed}/{self.total} [{win_pct:.0%} win]"
```

### 9.2 Results Viewer TUI

**What Works Well**:
- Filtering by occupation, winner, job zone
- Search functionality
- Side-by-side response viewing

**Issues Identified**:

**Incomplete Implementation**:
- `_load_comparisons()` method is empty
- `_get_occupations()` returns only ["All"]
- `action_view_detail()` doesn't actually load data
- `action_view_judgments()` doesn't push a screen

These are placeholders that need full implementation.

---

## 10. PDF Report Generation Simulation

### 10.1 Report Requirements from PROMPT.md

| Requirement | Status | Notes |
|-------------|--------|-------|
| Comprehensive Dashboard | ❌ Not implemented | Referenced but no code |
| Deep Statistical Analysis | ❌ Not implemented | Referenced but no code |
| Executive Summary | ✅ File path defined | But content generation missing |
| Win rates by occupation | ❌ Not shown | Query exists but chart missing |
| Win rates by writing type | ❌ Not shown | |
| Win rates by formality level | ❌ Not shown | |
| Win rates by age group | ❌ Not shown | |
| Heatmaps | ❌ Not shown | |
| Confidence intervals | ✅ Statistical analysis | But visualization missing |
| Significance tests | ✅ Statistical analysis | But formatting missing |
| Effect sizes | ✅ Statistical analysis | But formatting missing |
| Inter-rater reliability | ✅ Cohen's Kappa | But visualization missing |

**CRITICAL GAP**: The plan lists these files but never shows implementation:
```
src/reports/
├── pdf_generator.py       # Full PDF report
├── charts.py              # Plotly visualizations
├── heatmaps.py            # Dimension heatmaps
└── readme_generator.py    # Auto-generated README.md
```

**Needed Skeleton**:
```python
# src/reports/pdf_generator.py

from pathlib import Path
from typing import TYPE_CHECKING
import plotly.graph_objects as go
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Image
from reportlab.lib.styles import getSampleStyleSheet

if TYPE_CHECKING:
    from ..storage.database import ResultsDatabase
    from ..analysis.statistics import StatisticalAnalyzer

class PDFReportGenerator:
    """Generate comprehensive PDF report per PROMPT.md."""

    def __init__(self, db: "ResultsDatabase", output_path: Path):
        self.db = db
        self.output_path = output_path
        self.styles = getSampleStyleSheet()

    async def generate(self):
        """Generate complete PDF report."""
        doc = SimpleDocTemplate(str(self.output_path))
        elements = []

        # 1. Executive Summary
        elements.extend(await self._build_executive_summary())

        # 2. Methodology
        elements.extend(await self._build_methodology())

        # 3. Overall Results
        elements.extend(await self._build_overall_results())

        # 4. Breakdown by Dimension
        for dimension in ["occupation", "formality", "job_zone", "emotion"]:
            elements.extend(await self._build_dimension_section(dimension))

        # 5. Weakness Analysis
        elements.extend(await self._build_weakness_analysis())

        # 6. Bias Analysis
        elements.extend(await self._build_bias_analysis())

        # 7. Statistical Appendix
        elements.extend(await self._build_statistical_appendix())

        doc.build(elements)
```

---

## 11. CLI and Configuration Simulation

### 11.1 CLI Commands

**Verification Against PROMPT.md**:

| PROMPT.md CLI Example | Plan Implementation | Status |
|----------------------|---------------------|--------|
| `./eval --preset 3` | ✅ `run --preset` | Present |
| `./eval --preset 6 --models "..." --prompts 300` | ⚠️ Partial | --models not shown |
| `./eval --prompts 500 --occupations "..." --industries "..."` | ❌ Missing | Filters not implemented |
| `./eval --judges "..." --votes 3` | ❌ Missing | Judge override not shown |
| `./eval --preset 7 --dry-run` | ❌ Missing | --dry-run not implemented |
| `./eval --resume results/...` | ✅ `run --resume` | Present |
| `./eval compare results/...` | ✅ `compare` command | Present |

**Missing CLI Options**:
```python
@app.command()
def run(
    # ... existing ...
    models: Optional[str] = typer.Option(None, "--models", "-m",
        help="Comma-separated model pairs, e.g., 'gemini-pro,gpt-5.2'"),
    occupations: Optional[str] = typer.Option(None, "--occupations",
        help="O*NET occupation filter, e.g., '11-*,13-*'"),
    industries: Optional[str] = typer.Option(None, "--industries",
        help="NAICS industry filter, e.g., '54,62'"),
    judges: Optional[str] = typer.Option(None, "--judges",
        help="Judge models to use"),
    votes: Optional[int] = typer.Option(None, "--votes",
        help="Votes per judge"),
    dry_run: bool = typer.Option(False, "--dry-run",
        help="Show estimate without running"),
):
```

### 11.2 Cost Estimator

**Issues Identified**:

**CRITICAL GAP**: Cost estimator is referenced but not implemented:
```python
from src.config.cost_estimator import estimate_cost
estimate = estimate_cost(config)
```

**Need Implementation**:
```python
# src/config/cost_estimator.py

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import EvalConfig

# OpenRouter pricing as of Jan 2026 (needs verification)
MODEL_PRICING = {
    "google/gemini-3.0-pro-preview": {"input": 0.00125, "output": 0.005},
    "google/gemini-3.0-flash-preview": {"input": 0.000075, "output": 0.0003},
    "openai/gpt-5.2-thinking-preview": {"input": 0.015, "output": 0.06},
    "openai/gpt-4.1-preview": {"input": 0.0015, "output": 0.006},
    "anthropic/claude-opus-4.5-20251101": {"input": 0.015, "output": 0.075},
    "anthropic/claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
}

@dataclass
class CostEstimate:
    response_generation_cost: float
    judging_cost: float
    phase1_generation_cost: float  # If needed
    total_cost: float
    total_hours: float

def estimate_cost(config: "EvalConfig") -> CostEstimate:
    """Estimate total cost and time for evaluation run."""
    # Average tokens per prompt/response
    AVG_INPUT_TOKENS = 500
    AVG_OUTPUT_TOKENS = 400
    AVG_JUDGE_INPUT_TOKENS = 1500  # Includes both responses + context
    AVG_JUDGE_OUTPUT_TOKENS = 100

    # Response generation
    response_cost = 0.0
    for gemini, competitor in config.model_pairs:
        calls_per_pair = config.num_prompts * 2  # Both models
        gemini_cost = (
            calls_per_pair *
            (MODEL_PRICING[gemini]["input"] * AVG_INPUT_TOKENS / 1000 +
             MODEL_PRICING[gemini]["output"] * AVG_OUTPUT_TOKENS / 1000)
        )
        competitor_cost = (
            calls_per_pair *
            (MODEL_PRICING[competitor]["input"] * AVG_INPUT_TOKENS / 1000 +
             MODEL_PRICING[competitor]["output"] * AVG_OUTPUT_TOKENS / 1000)
        )
        response_cost += gemini_cost + competitor_cost

    # Judging cost
    judge_calls = (
        config.num_prompts *
        len(config.model_pairs) *
        len(config.judge_models) *
        config.votes_per_judge *
        (2 if config.use_both_personas else 1)
    )
    judging_cost = sum(
        judge_calls / len(config.judge_models) *
        (MODEL_PRICING[j]["input"] * AVG_JUDGE_INPUT_TOKENS / 1000 +
         MODEL_PRICING[j]["output"] * AVG_JUDGE_OUTPUT_TOKENS / 1000)
        for j in config.judge_models
    )

    # Time estimate (rough)
    total_calls = config.num_prompts * len(config.model_pairs) * 2 + judge_calls
    calls_per_minute = 30  # Conservative with rate limits
    total_hours = total_calls / calls_per_minute / 60

    return CostEstimate(
        response_generation_cost=response_cost,
        judging_cost=judging_cost,
        phase1_generation_cost=0.0,  # Assumed pre-run
        total_cost=response_cost + judging_cost,
        total_hours=total_hours
    )
```

### 11.3 Presets

**Verification Against PROMPT.md**:

The plan mentions 10 presets but only shows EvalConfig default values. The full preset table from PROMPT.md should be implemented:

```python
# src/config/presets.py

PRESETS = {
    1: EvalConfig(
        preset_level=1,
        run_name="Sanity Check",
        num_prompts=5,
        model_pairs=[("google/gemini-3.0-pro-preview", "openai/gpt-5.2-thinking-preview")],
        judge_config=JudgeConfig(
            models=["anthropic/claude-opus-4.5-20251101"],
            votes_per_judge=1,
            use_both_personas=False
        )
    ),
    2: EvalConfig(
        preset_level=2,
        run_name="Smoke Test",
        num_prompts=20,
        model_pairs=[("google/gemini-3.0-pro-preview", "openai/gpt-5.2-thinking-preview")],
        judge_config=JudgeConfig(
            models=["anthropic/claude-opus-4.5-20251101"],
            votes_per_judge=3,
            use_both_personas=False
        )
    ),
    # ... presets 3-10 ...
}
```

---

## 12. Special Prompt Types Simulation

### 12.1 Instruction-Following Constraints

**What Works Well**:
- Covers length, format, tone, exclusion constraints
- Probability-based application (15% of prompts)
- Measurable requirements for verification

**Issues Identified**:

**GAP**: Compliance verification is mentioned but not implemented:
```python
# Plan has ComplianceTracker referenced but no implementation
src/eval/compliance_tracker.py  # Missing
```

**Need Implementation**:
```python
class ComplianceTracker:
    """Verify response compliance with constraints."""

    def check_length_constraint(self, response: str, constraint: ConstraintSpec) -> bool:
        """Check if response meets length requirements."""
        if constraint.specific_requirement.startswith("max_words:"):
            max_words = int(constraint.specific_requirement.split(":")[1])
            return len(response.split()) <= max_words
        elif constraint.specific_requirement.startswith("min_words:"):
            min_words = int(constraint.specific_requirement.split(":")[1])
            return len(response.split()) >= min_words
        # ... more checks

    def check_format_constraint(self, response: str, constraint: ConstraintSpec) -> bool:
        """Check format requirements."""
        if constraint.specific_requirement == "no_bullets":
            return not re.search(r'^[\s]*[-*•]\s+', response, re.MULTILINE)
        elif constraint.specific_requirement.startswith("exact_bullets:"):
            n = int(constraint.specific_requirement.split(":")[1])
            bullets = re.findall(r'^[\s]*[-*•]\s+', response, re.MULTILINE)
            return len(bullets) == n
        # ... more checks
```

### 12.2 Revision Tasks

**What Works Well**:
- Multiple revision types (professional, soften, clarify, concise)
- Template-based draft generation

**Issues Identified**:

**Edge Case**: "Concise" revision type says it will be filled by LLM in Phase 3, but Phase 3 enricher doesn't have special handling for revision task drafts.

**Fix Needed in Phase 3**:
```python
async def _enrich_single_prompt(self, prompt: WritingPrompt) -> WritingPrompt:
    # ... existing enrichments ...

    # Handle revision task draft generation
    if prompt.is_revision_task and prompt.revision_task:
        if prompt.revision_task.original_draft.startswith("[To be generated"):
            verbose_draft = await self._generate_verbose_draft(prompt, model)
            prompt.revision_task.original_draft = verbose_draft
```

### 12.3 CC/Multiple Recipients

**What Works Well**:
- Multiple scenario types
- Mixed audience notes

**Issues Identified**:

**PROMPT.md Requirement**: "Email to client, CC'd to your boss" - this is implemented.

**Missing Scenario**: "Message to peer that will be forwarded to executives" - the plan handles this with `will_be_forwarded_to` field but the judge prompt builder doesn't include forward context:
```python
# Need to add to judge prompt:
if prompt.cc_context and prompt.cc_context.will_be_forwarded_to:
    user_sections.append(f"\n## Forward Context\nThis message will be forwarded to: {prompt.cc_context.will_be_forwarded_to}")
```

---

## 13. Edge Cases and Gotchas

### 13.1 API-Related Gotchas

1. **OpenRouter model name changes**: Model IDs may change (e.g., "gpt-5.2-thinking-preview" -> "gpt-5.2"). Need model alias mapping.

2. **Rate limit headers**: OpenRouter returns rate limit info in headers. Plan doesn't show parsing these.

3. **Streaming vs non-streaming**: Some models may only support streaming. Plan assumes non-streaming.

4. **Token counting before request**: To avoid exceeding context limits, need to count tokens BEFORE sending. Plan's TokenCounter is referenced but not shown.

### 13.2 Data-Related Gotchas

1. **O*NET occupation codes format**: Codes are "XX-XXXX.XX" format. Plan sometimes uses "XX-XXXX" (without decimal). Need consistency.

2. **NAICS code length**: NAICS codes are 2-6 digits. Plan uses 6-digit codes but some tasks may only have 2-digit sector codes.

3. **Company name ambiguity**: "Apple" could be Apple Inc. or a fruit company. Need disambiguation in CompanyDatabase.

### 13.3 Evaluation-Related Gotchas

1. **Judge self-evaluation**: When Gemini 3 Pro is being evaluated AND is a judge, it's judging its own output. This creates potential bias despite position shuffling.

2. **Response length correlation with quality**: Longer responses might be judged better regardless of content. Plan detects but doesn't mitigate.

3. **Tie handling in statistics**: Many statistical tests exclude ties. If tie rate is high, effective sample size drops significantly.

### 13.4 Resume-Related Gotchas

1. **Config changes between runs**: If user resumes with different config, results may be inconsistent. Need config hash verification.

2. **Model updates**: If model is updated on OpenRouter between resume, responses may differ from pre-interruption.

3. **Partial comparison state**: If crash happens after some judge votes but before all, need to track which exact votes are complete.

---

## 14. Missing Components Summary

### 14.1 Critical Missing (Must Have)

1. **OpenRouter client implementation** - Core API interface
2. **Cost estimator implementation** - Required for user confirmation
3. **Judge response parser** - Required for vote aggregation
4. **Compliance tracker** - Required for instruction-following analysis
5. **Weakness finder** - Core PROMPT.md requirement
6. **PDF report generator** - Core PROMPT.md requirement

### 14.2 Important Missing (Should Have)

1. **Rate limiter with model-specific limits**
2. **Circuit breaker with state persistence**
3. **Signal handlers for graceful shutdown**
4. **Format detection (bullets, headers, etc.)**
5. **Format bias detection**
6. **TUI per-model-pair progress**
7. **CLI --dry-run option**
8. **CLI occupation/industry filters**

### 14.3 Nice to Have

1. **Model alias mapping**
2. **Streaming response support**
3. **Real-time cost tracking from OpenRouter headers**
4. **Heatmap generation**
5. **Cross-run statistical comparison details**

---

## 15. PROMPT.md Compliance Checklist

### 15.1 Fully Compliant

- [x] Three-phase prompt generation
- [x] O*NET task-level granularity
- [x] NAICS-based industry sampling
- [x] All diversity dimensions in schema
- [x] Majority-of-majorities voting
- [x] Three judge models
- [x] Dual judge personas
- [x] Position randomization
- [x] Wilson score confidence intervals
- [x] Cohen's Kappa for inter-rater reliability
- [x] Full results directory structure
- [x] Checkpoint/resume system
- [x] SQLite storage
- [x] 10 preset configurations (structure, not full implementation)

### 15.2 Partially Compliant

- [ ] Live progress visualization - TUI exists but doesn't match PROMPT.md layout exactly
- [ ] Cost estimation - Referenced but not implemented
- [ ] Bias detection - 4 of 5 types implemented
- [ ] PDF report - Structure defined but not implemented
- [ ] CLI options - Basic commands present, advanced filtering missing

### 15.3 Non-Compliant or Missing

- [ ] Real company database - Referenced but source not specified
- [ ] Census name database - Referenced but source not specified
- [ ] Weakness finder - Not implemented
- [ ] PDF heatmaps - Not implemented
- [ ] --dry-run CLI option - Not implemented

---

## 16. Recommendations

### 16.1 Immediate Priorities

1. **Implement OpenRouter client** with proper error handling, rate limiting, and cost tracking
2. **Implement judge response parser** with robust fallback for malformed outputs
3. **Add weakness finder** - this is a core deliverable per PROMPT.md
4. **Complete cost estimator** - users need this before running expensive evaluations

### 16.2 Architecture Improvements

1. **Add model alias layer** to handle OpenRouter model name changes
2. **Centralize token counting** to prevent context limit issues
3. **Add config validation** to catch incompatible settings before run
4. **Implement position bias mitigation** not just detection

### 16.3 Testing Priorities

1. **Unit tests for vote aggregator** - critical for correctness
2. **Integration tests with mock OpenRouter** - expensive to test against real API
3. **Resume tests** - simulate crashes at various points
4. **Statistical validation tests** - verify CI and p-value calculations

---

## 17. Conclusion

The master plan provides a solid foundation for the Gemini Writing Evaluation Framework. The architecture is well-designed, the schema is comprehensive, and most PROMPT.md requirements are addressed at the structural level.

**Key Strengths**:
- Complete prompt schema covering all diversity dimensions
- Robust three-phase generation pipeline
- Proper statistical methodology
- Good checkpoint/resume design

**Key Weaknesses**:
- Several critical components are referenced but not implemented (OpenRouter client, cost estimator, PDF generator, weakness finder)
- TUI doesn't fully match PROMPT.md specifications
- Some edge cases and gotchas not addressed
- Missing format bias detection

**Overall Assessment**: The plan is approximately 70% complete for implementation. The remaining 30% consists of critical implementation details, edge case handling, and full compliance with PROMPT.md specifications. Before implementation, the gaps identified in this simulation should be addressed to ensure a production-ready system.
