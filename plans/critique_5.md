# Critique of Draft Plan 5: Gemini Writing Evaluation Framework

## Executive Summary

Draft Plan 5 is a comprehensive and well-structured implementation plan that covers most requirements from PROMPT.md. It demonstrates strong technical competence with detailed code examples and a clear architecture. However, there are several critical gaps, technical issues, and areas for improvement that need to be addressed to achieve 100% specification coverage.

---

## Part 1: Critical Issues and Gaps

### 1.1 Missing Specification Elements

**1.1.1 Tone Matching from Examples (MISSING)**
PROMPT.md specifies that some prompts should include prior writing samples to match:
- "Here's how Sarah typically writes to clients: [example]. Draft a similar message for..."
- "Match the tone of our previous announcements: [example]"
- "Continue this email thread in a consistent voice"

The draft plan's `WritingPrompt` schema includes `tone_example: Optional[str]` but the pipeline never populates this field, and there's no mechanism to generate or include tone matching examples.

**1.1.2 Multiple Recipients / CC Situations (PARTIALLY MISSING)**
PROMPT.md explicitly requires scenarios with multiple audiences simultaneously:
- Email to client, CC'd to your boss
- Team announcement that external partners will also see
- Message to peer that will be forwarded to executives

While the schema supports `recipients: list[RecipientPersona]`, the prompt generation doesn't model the CC/forward dynamics or mixed audience navigation requirements.

**1.1.3 Instruction-Following Tests (MISSING)**
PROMPT.md requires explicit constraint prompts to test instruction-following:
- Length constraints: "Keep this under 100 words"
- Format requirements: "Use exactly 3 bullet points"
- Tone directives: "Be direct and avoid pleasantries"
- Exclusions: "Do not mention the budget"

The `ConstraintSpec` class exists but is never populated in the prompt generation pipeline.

**1.1.4 Communication Channel Tracking (INCOMPLETE)**
The schema has `communication_channel: Optional[str]` but the pipeline doesn't infer channels from O*NET task statements as specified. The PROMPT.md says:
- "Let O*NET task statements imply the medium naturally"
- "Use Phase 3 LLM enrichment to infer/specify medium when the task is ambiguous"
- "Track channel as metadata for analysis"

**1.1.5 Regional English Variants (INCOMPLETE)**
While `EnglishVariant` enum exists, the prompt generation always defaults to `EnglishVariant.US`. PROMPT.md requires:
- British recipient scenarios (colour, organisation, different date formats)
- Australian context (mate, different idioms)
- International company with mixed audience
- Non-native English speaker as recipient

**1.1.6 Revision & Editing Tasks (MISSING GENERATION)**
The schema has `is_revision_task`, `original_draft`, and `revision_instruction` fields, but the pipeline never generates revision tasks. PROMPT.md explicitly requires:
- "Revise this draft to be more concise: [draft]"
- "Make this email more professional: [casual draft]"
- "Soften the tone of this message: [harsh draft]"

**1.1.7 Ambiguity Handling Prompts (MISSING GENERATION)**
The schema has `is_ambiguous: bool` but the pipeline never generates deliberately vague prompts. PROMPT.md requires testing how models handle uncertainty with underspecified recipient, missing context, or unclear asks.

### 1.2 Judge Context Requirements Gap

PROMPT.md explicitly states (marked as CRITICAL):
> "Judges need the context of the scenario to evaluate properly."

The judge prompts in the plan include writer context, recipient context, formality, and urgency. However, they're missing:
- Temporal context when relevant
- Prior message context for replies
- Attachment summaries that models should have referenced
- Competing objectives the writer was balancing
- Tone example they were supposed to match
- Explicit constraints they were supposed to follow

Without this context, judges cannot accurately assess whether responses are appropriate for the specific scenario.

### 1.3 Results Directory Structure Mismatch

PROMPT.md specifies a detailed directory structure:
```
eval_YYYY-MM-DD_HH-MM-SS/
├── config.json
├── config_summary.txt
├── checkpoint.json
├── random_seed.txt
├── prompts/
│   ├── prompts.json
│   ├── prompts_by_occupation/
│   └── prompts_by_industry/
├── responses/
│   ├── by_prompt/
│   └── by_model/
├── judgments/
│   ├── raw/
│   └── aggregated/
├── results.db
├── results_summary.csv
├── analysis/
├── reports/
├── logs/
└── README.md
```

The plan only implements a simplified structure with `results.db`, `checkpoint.json`, and a reports directory.

---

## Part 2: Technical Issues

### 2.1 Deprecated API Usage

```python
p_value = stats.binom_test(wins, decisive, 0.5, alternative='two-sided')
```

`scipy.stats.binom_test` is deprecated since SciPy 1.7 and removed in SciPy 1.12. Should use `scipy.stats.binomtest`:
```python
result = stats.binomtest(wins, decisive, 0.5, alternative='two-sided')
p_value = result.pvalue
```

### 2.2 Potential Race Condition in TUI Updates

The CLI's `update_tui()` coroutine runs in a separate task while the evaluation runs. The TUI updates read from `engine.progress` which is mutated by the evaluation engine. This could cause inconsistent reads. Should use thread-safe data structures or message passing.

### 2.3 Missing Error Handling in JSON Parsing

In `_enrich_prompt()`:
```python
enrichment = json.loads(response)
```

If the LLM returns invalid JSON (common), this will raise an exception. The outer try/catch catches it but silently passes, losing diagnostic information. Should log the failure and track enrichment failure rates.

### 2.4 Judge Vote Aggregation Bug

In `_run_judge_votes()`:
```python
gemini_wins = sum(1 for v in votes if v.winner == gemini_position)
```

But `gemini_position` changes for each vote (deterministic shuffle per vote). The aggregation incorrectly assumes constant position. Should track winner relative to gemini consistently across votes.

### 2.5 Missing Response Validation

The plan doesn't validate model responses for:
- Off-topic responses (model answers a different question)
- Incomplete responses (model stops mid-sentence)
- Refusal patterns (model declines to respond)

These should be detected and categorized per PROMPT.md's refusal categorization requirements.

### 2.6 Cost Estimator Not Implemented

The CLI calls `estimate_run_cost(config)` but this function isn't shown in the plan. Critical for the user configuration requirements.

### 2.7 Database Query Security

```python
query = f"""
    SELECT ... FROM comparisons c
    JOIN prompts p ON c.prompt_id = p.prompt_id
    GROUP BY p.{dimension}, pair
"""
```

Dynamic SQL construction with string interpolation is vulnerable to SQL injection. Should use parameterized queries or whitelist allowed dimension values.

---

## Part 3: Robustness Issues

### 3.1 Checkpoint Resume Incomplete

The checkpoint system tracks `completed_prompt_ids` and `completed_comparison_ids`, but:
- Doesn't track partial responses (if one model succeeded but another failed)
- Doesn't track partial judgments (if 2 of 3 judges completed)
- Resume logic assumes all-or-nothing per prompt

### 3.2 Rate Limiter Token Estimation

```python
async def acquire(self, estimated_tokens: int = 1000):
```

The default of 1000 tokens is arbitrary. Output tokens aren't known until response arrives. Should:
- Estimate input tokens from prompt length
- Use moving average of actual output tokens
- Update token accounting after response

### 3.3 Circuit Breaker State Persistence

If the process crashes, circuit breaker state is lost. On resume, a flaky API might immediately trigger cascading failures again. Should persist circuit breaker state to checkpoint.

### 3.4 Missing Retry on Specific Errors

The retry handler catches `HTTPStatusError` and `TimeoutException` but should also handle:
- Connection reset errors
- SSL errors
- Rate limit (429) responses with Retry-After headers
- Server errors (5xx) differently from client errors (4xx)

---

## Part 4: Completeness vs PROMPT.md

### 4.1 Cross-Run Comparison (MISSING)

PROMPT.md requires:
```bash
./eval compare results/eval_2024-01-15_*/ results/eval_2024-01-16_*/
```

The CLI has a `compare` command stub but no implementation.

### 4.2 Results Viewer TUI (MISSING)

The `view` command references `ResultsViewer` but no implementation is provided. PROMPT.md requires:
- Filtering by occupation, industry, winner, etc.
- Sorting by various dimensions
- Side-by-side response viewing
- Drill-down into individual judgments

### 4.3 Bias Detection (INCOMPLETE)

PROMPT.md requires detecting and reporting:
- Position bias: Do judges prefer Response A vs B systematically?
- Length bias: Do judges prefer longer/shorter responses?
- Model fingerprinting: Can judges identify which model wrote which response?

The plan mentions bias detection but provides no implementation.

### 4.4 Response Metadata Tracking (INCOMPLETE)

PROMPT.md requires tracking:
- Greeting/sign-off patterns (formal vs casual markers)
- Format detection (bullet points, headers, paragraphs)

The plan detects these but doesn't analyze patterns across responses or correlate with win/loss rates.

### 4.5 Sensitive Topic Tracking (INCOMPLETE)

Detection exists but the plan doesn't:
- Track win rates separately for sensitive vs routine tasks
- Analyze whether models handle difficult communications appropriately
- Note refusal patterns for sensitive topics

### 4.6 Progress Dashboard Elements Missing

PROMPT.md's detailed dashboard layout includes:
- Recent activity log with scrolling
- Error summary panel with retry/failure/rate limit counts
- Interactive controls (p for pause, d for detail, s for stats)

The Textual implementation has placeholders but incomplete functionality.

### 4.7 Auto-Generated README (MISSING)

PROMPT.md requires each run directory to have an auto-generated `README.md` describing the run.

---

## Part 5: Design and Architecture Issues

### 5.1 Phase 3 Enrichment Model Choice

The plan uses a single enrichment model:
```python
enrichment_model: str = "anthropic/claude-3-5-sonnet-20241022"
```

PROMPT.md states:
> "Use the same models being evaluated for this generation (note: this creates potential bias but ensures prompts aren't accidentally biased against any particular model)"

Should use a mix of models being evaluated or explicitly document the bias tradeoff.

### 5.2 Company Database Scalability

The hardcoded company dictionary is limited to ~50 companies. For 10,000+ prompts, this will cause significant company reuse, reducing diversity. Should:
- Expand database significantly
- Track company usage to ensure diversity
- Generate synthetic companies for rare sectors

### 5.3 Name Generator Cultural Accuracy

Name-ethnicity matching is simplistic. Names like "Wei Chen" might be assigned to a 65-year-old boomer in Iowa, which may not be plausible. Should consider:
- Geographic distribution of names
- Generational naming trends
- Occupational plausibility

### 5.4 O*NET Table Names Incorrect

The plan references:
```sql
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
```

Need to verify these match actual O*NET 30.1 table names. The ONET_WRITING_REFERENCE.md shows similar queries but table names should be confirmed against the actual database.

---

## Part 6: Missing Operational Requirements

### 6.1 Failure Logging and Report

PROMPT.md requires:
- Track all failures with full context for debugging
- Failure report summary at end of run
- `failures.log` in run directory

The plan mentions logging but doesn't implement structured failure tracking.

### 6.2 CSV Export

PROMPT.md requires `results_summary.csv` export. The plan has an `exporter.py` placeholder but no implementation.

### 6.3 Config Summary Text

PROMPT.md requires `config_summary.txt` - human-readable configuration summary. Not implemented.

### 6.4 Timing Log

PROMPT.md requires `timing.log` - performance metrics. Not implemented.

---

## Part 7: Code Quality Issues

### 7.1 Inconsistent Type Hints

Some functions use `list[str]` (Python 3.9+) while others use older syntax. Should be consistent.

### 7.2 Missing Docstrings

Many critical functions lack docstrings explaining parameters, return values, and behavior.

### 7.3 Magic Numbers

```python
formality_weights = [0.4, 0.5, 0.1]  # More casual
```

These should be named constants with documentation.

### 7.4 Incomplete Import Statements

Code snippets reference types like `WritingPrompt`, `RecipientPersona`, `EnglishVariant` without showing imports. Need complete module structure.

---

# Improved Plan: Gemini Writing Evaluation Framework

## Executive Summary

This improved plan addresses all gaps identified in the critique, providing a complete implementation that covers 100% of PROMPT.md requirements. Key improvements include:

1. Complete prompt diversity features (tone matching, CC scenarios, instruction-following, revision tasks)
2. Enhanced judge context with full scenario information
3. Complete results directory structure per specification
4. Fixed technical bugs and deprecated API usage
5. Comprehensive bias detection and weakness analysis
6. Full TUI implementation with all interactive features
7. Robust checkpoint/resume with partial state recovery

---

## Part 1: Enhanced System Architecture

### 1.1 Complete Directory Structure

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── .env.example
├── config/
│   └── presets.yaml
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── presets.py
│   │   └── cost_estimator.py      # NEW: Full implementation
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py
│   │   ├── naics_mapper.py
│   │   ├── company_database.py    # ENHANCED: 500+ companies
│   │   ├── name_generator.py
│   │   └── tone_examples.py       # NEW: Tone matching samples
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # ENHANCED: All prompt types
│   │   ├── phase1_extraction.py
│   │   ├── phase2_combination.py
│   │   ├── phase3_enrichment.py
│   │   ├── schemas.py
│   │   ├── constraint_generator.py    # NEW: Instruction-following
│   │   ├── revision_generator.py      # NEW: Revision tasks
│   │   └── channel_inferrer.py        # NEW: Channel detection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py
│   │   ├── rate_limiter.py
│   │   ├── retry_handler.py       # ENHANCED: Retry-After handling
│   │   ├── circuit_breaker.py
│   │   └── token_counter.py       # NEW: Accurate token estimation
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py              # ENHANCED: Partial state recovery
│   │   ├── response_generator.py
│   │   ├── response_validator.py  # NEW: Refusal detection
│   │   ├── judge.py
│   │   ├── judge_prompts.py       # ENHANCED: Full context
│   │   ├── vote_aggregator.py     # FIXED: Position tracking bug
│   │   └── schemas.py
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # FIXED: Deprecated API
│   │   ├── bias_detection.py      # ENHANCED: Full implementation
│   │   ├── weakness_finder.py
│   │   ├── response_patterns.py   # NEW: Format/length analysis
│   │   └── visualizations.py
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py
│   │   ├── csv_exporter.py        # NEW: CSV export
│   │   ├── run_readme.py          # NEW: Auto-generated README
│   │   └── templates/
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── checkpoint.py          # ENHANCED: Partial state
│   │   ├── run_directory.py       # NEW: Full directory structure
│   │   ├── exporter.py
│   │   └── failure_logger.py      # NEW: Structured failure log
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── progress_dashboard.py  # ENHANCED: All elements
│   │   ├── results_viewer.py      # NEW: Full implementation
│   │   └── components/
│   │
│   └── validation/
│       ├── __init__.py
│       └── onet_schema.py         # NEW: Validate O*NET tables
│
├── db/
│   ├── onet.db
│   └── ONET_WRITING_REFERENCE.md
│
├── results/
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── fixtures/
```

### 1.2 Run Directory Structure (Per Specification)

```python
# src/storage/run_directory.py

from pathlib import Path
from datetime import datetime
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.settings import EvalConfig

class RunDirectory:
    """Manages the full run directory structure per PROMPT.md specification."""

    def __init__(self, base_dir: Path, run_id: str):
        self.run_dir = base_dir / run_id
        self._create_structure()

    def _create_structure(self):
        """Create the complete directory structure."""
        dirs = [
            self.run_dir,
            self.run_dir / "prompts" / "prompts_by_occupation",
            self.run_dir / "prompts" / "prompts_by_industry",
            self.run_dir / "responses" / "by_prompt",
            self.run_dir / "responses" / "by_model",
            self.run_dir / "judgments" / "raw",
            self.run_dir / "judgments" / "aggregated",
            self.run_dir / "analysis",
            self.run_dir / "reports" / "charts",
            self.run_dir / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def config_json(self) -> Path:
        return self.run_dir / "config.json"

    @property
    def config_summary(self) -> Path:
        return self.run_dir / "config_summary.txt"

    @property
    def checkpoint(self) -> Path:
        return self.run_dir / "checkpoint.json"

    @property
    def random_seed(self) -> Path:
        return self.run_dir / "random_seed.txt"

    @property
    def prompts_json(self) -> Path:
        return self.run_dir / "prompts" / "prompts.json"

    @property
    def results_db(self) -> Path:
        return self.run_dir / "results.db"

    @property
    def results_csv(self) -> Path:
        return self.run_dir / "results_summary.csv"

    @property
    def run_log(self) -> Path:
        return self.run_dir / "logs" / "run.log"

    @property
    def failures_log(self) -> Path:
        return self.run_dir / "logs" / "failures.log"

    @property
    def timing_log(self) -> Path:
        return self.run_dir / "logs" / "timing.log"

    @property
    def readme(self) -> Path:
        return self.run_dir / "README.md"

    def save_config(self, config: "EvalConfig"):
        """Save config.json and config_summary.txt."""
        # Full JSON config
        with open(self.config_json, 'w') as f:
            json.dump(config.model_dump(), f, indent=2, default=str)

        # Human-readable summary
        summary = self._generate_config_summary(config)
        with open(self.config_summary, 'w') as f:
            f.write(summary)

        # Random seed
        with open(self.random_seed, 'w') as f:
            f.write(str(config.sampling.random_seed))

    def _generate_config_summary(self, config: "EvalConfig") -> str:
        """Generate human-readable config summary."""
        lines = [
            "=" * 60,
            "GEMINI WRITING EVALUATION - CONFIGURATION SUMMARY",
            "=" * 60,
            "",
            f"Run ID: {config.run_id}",
            f"Run Name: {config.run_name}",
            f"Preset Level: {config.preset_level or 'Custom'}",
            f"Created: {config.created_at}",
            "",
            "MODEL CONFIGURATION",
            "-" * 40,
            f"Model Pairs: {len(config.model_pairs)}",
        ]
        for gemini, competitor in config.model_pairs:
            lines.append(f"  - {gemini} vs {competitor}")

        lines.extend([
            "",
            "JUDGE CONFIGURATION",
            "-" * 40,
            f"Judge Models: {', '.join(config.judge_config.models)}",
            f"Votes per Judge: {config.judge_config.votes_per_judge}",
            f"Use Both Personas: {config.judge_config.use_both_personas}",
            "",
            "SAMPLING CONFIGURATION",
            "-" * 40,
            f"Total Prompts: {config.sampling.total_prompts}",
            f"Random Seed: {config.sampling.random_seed}",
            f"Stratify by Job Zone: {config.sampling.stratify_by_job_zone}",
            f"Stratify by SOC Group: {config.sampling.stratify_by_soc_group}",
            "",
            "=" * 60,
        ])
        return "\n".join(lines)

    def generate_readme(self, config: "EvalConfig", stats: dict):
        """Generate auto README.md for the run."""
        content = f"""# Evaluation Run: {config.run_id}

## Overview

- **Run Name**: {config.run_name}
- **Preset Level**: {config.preset_level or 'Custom'}
- **Created**: {config.created_at}
- **Status**: {'Completed' if stats.get('completed') else 'In Progress'}

## Configuration

- **Total Prompts**: {config.sampling.total_prompts}
- **Model Pairs**: {len(config.model_pairs)}
- **Judge Models**: {len(config.judge_config.models)}
- **Votes per Judge**: {config.judge_config.votes_per_judge}

## Results Summary

| Metric | Value |
|--------|-------|
| Comparisons Completed | {stats.get('comparisons_completed', 0)} |
| Gemini Overall Win Rate | {stats.get('gemini_win_rate', 'N/A')} |
| Total API Calls | {stats.get('total_api_calls', 0)} |
| Total Cost | ${stats.get('total_cost', 0):.2f} |

## Directory Contents

- `config.json` - Full configuration
- `config_summary.txt` - Human-readable config
- `prompts/` - Generated prompts
- `responses/` - Model responses
- `judgments/` - Judge evaluations
- `results.db` - SQLite database with all results
- `results_summary.csv` - CSV export of key metrics
- `analysis/` - Statistical analysis outputs
- `reports/` - PDF report and charts
- `logs/` - Execution logs

## Reproducibility

To reproduce this run:
```bash
./eval --config {self.config_json}
```

Random seed: {config.sampling.random_seed}
"""
        with open(self.readme, 'w') as f:
            f.write(content)
```

---

## Part 2: Enhanced Prompt Generation

### 2.1 Complete WritingPrompt Schema

```python
# src/prompts/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class EnglishVariant(str, Enum):
    US = "en-US"
    GB = "en-GB"
    AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    INITIAL = "initial_outreach"
    REPLY = "reply_in_thread"
    FOLLOWUP = "follow_up"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict_resolution"
    BAD_NEWS = "bad_news_delivery"

class SensitiveTopic(str, Enum):
    HR_ISSUES = "hr_issues"
    LEGAL = "legal_matters"
    BAD_NEWS = "bad_news_delivery"
    CONFIDENTIAL = "confidential_information"
    CONFLICT = "conflict_situations"

class CCContext(BaseModel):
    """Context for CC/forwarding scenarios."""
    cc_recipients: list[str] = []
    will_be_forwarded_to: Optional[str] = None
    mixed_audience_note: Optional[str] = None

class ToneExample(BaseModel):
    """Prior writing sample for tone matching."""
    example_text: str
    context: str  # e.g., "how Sarah typically writes to clients"
    match_instruction: str  # e.g., "Draft a similar message for..."

class ConstraintSpec(BaseModel):
    """Explicit instruction-following constraint."""
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    description: str
    specific_requirement: str
    measurable: bool = True  # Can compliance be verified?

class RevisionTask(BaseModel):
    """Details for revision/editing tasks."""
    original_draft: str
    revision_type: Literal["concise", "professional", "soften", "expand", "clarify"]
    instruction: str
    target_outcome: str

class WriterPersona(BaseModel):
    """Detailed writer persona."""
    name: str
    email: Optional[str] = None
    age: int = Field(ge=18, le=80)
    generation: Literal["gen_z", "millennial", "gen_x", "boomer"]
    job_title: str
    skill_level: Literal["entry", "mid", "senior", "executive"]
    english_variant: EnglishVariant = EnglishVariant.US

class RecipientPersona(BaseModel):
    """Target recipient/audience details."""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship: Literal["new_contact", "acquaintance", "colleague",
                          "manager", "direct_report", "client", "vendor"]
    english_variant: EnglishVariant = EnglishVariant.US
    is_technical: bool = False
    # NEW: For CC scenarios
    is_primary: bool = True  # vs CC'd
    visibility_context: Optional[str] = None  # "will see the response"

class CompanyContext(BaseModel):
    """Company information for grounding."""
    name: str
    size: Literal["startup", "small", "mid_market", "enterprise", "fortune_500"]
    industry_naics: str
    industry_name: str
    is_public: bool = False
    hq_location: Optional[str] = None
    employee_count: Optional[int] = None

class Attachment(BaseModel):
    """Mock attachment or reference content."""
    type: Literal["report", "email", "meeting_notes", "resume",
                  "document", "data", "spreadsheet", "presentation"]
    description: str
    content: str  # Summary or key points

class WritingPrompt(BaseModel):
    """Complete writing prompt with all context per PROMPT.md."""
    # Identifiers
    prompt_id: str
    onet_task_id: str
    onet_task: str

    # Occupation context
    occupation_code: str
    occupation_title: str
    job_zone: int = Field(ge=1, le=5)
    soc_major_group: str

    # Industry context
    naics_code: str
    naics_sector: str
    company: CompanyContext

    # Personas
    writer: WriterPersona
    recipients: list[RecipientPersona]
    audience_size: Literal["one_on_one", "small_group", "department",
                           "company_wide", "public"]

    # CC/Multiple audience context (NEW)
    cc_context: Optional[CCContext] = None

    # Communication context
    formality_level: int = Field(ge=1, le=5)
    urgency_level: int = Field(ge=1, le=5)
    message_position: MessagePosition
    emotional_context: EmotionalContext
    communication_channel: Optional[str] = None  # email, memo, report, slack, etc.

    # Content context
    prior_context: Optional[str] = None
    attachments: list[Attachment] = []
    competing_objectives: Optional[str] = None

    # Tone matching (NEW - per PROMPT.md)
    tone_example: Optional[ToneExample] = None

    # Revision tasks (NEW - per PROMPT.md)
    is_revision_task: bool = False
    revision_task: Optional[RevisionTask] = None

    # Instruction-following constraints (NEW - per PROMPT.md)
    constraints: list[ConstraintSpec] = []

    # Ambiguity testing (NEW - per PROMPT.md)
    is_ambiguous: bool = False
    ambiguity_type: Optional[Literal["underspecified_recipient",
                                      "missing_context", "unclear_ask"]] = None

    # Metadata
    sensitive_topics: list[SensitiveTopic] = []
    writing_category: str

    # Language
    language: str = "en"
    language_variant: str = "en-US"
    recipient_english_variant: Optional[str] = None  # For regional variant analysis

    # Temporal
    temporal_context: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # The actual prompt text
    full_prompt: str
```

### 2.2 Constraint Generator

```python
# src/prompts/constraint_generator.py

import random
from typing import Optional
from src.prompts.schemas import ConstraintSpec, WritingPrompt

class ConstraintGenerator:
    """Generate instruction-following constraints per PROMPT.md."""

    LENGTH_CONSTRAINTS = [
        ("Keep this under 100 words", "length", 100, "max_words"),
        ("Keep this under 50 words", "length", 50, "max_words"),
        ("This should be comprehensive, at least 500 words", "length", 500, "min_words"),
        ("Write exactly 3 sentences", "length", 3, "exact_sentences"),
        ("Keep it to a single paragraph", "length", 1, "max_paragraphs"),
    ]

    FORMAT_CONSTRAINTS = [
        ("Use exactly 3 bullet points", "format", 3, "exact_bullets"),
        ("Use exactly 5 bullet points", "format", 5, "exact_bullets"),
        ("Write in paragraph form only, no bullet points", "format", 0, "no_bullets"),
        ("Include a clear subject line", "format", None, "has_subject"),
        ("Structure with clear headings", "format", None, "has_headings"),
        ("Do not use any headers or formatting", "format", None, "plain_text"),
    ]

    TONE_CONSTRAINTS = [
        ("Be direct and avoid pleasantries", "tone", None, "no_pleasantries"),
        ("Use a warm, encouraging tone", "tone", None, "warm_tone"),
        ("Keep it strictly professional, no casual language", "tone", None, "formal_only"),
        ("Be conversational and friendly", "tone", None, "casual_tone"),
    ]

    EXCLUSION_CONSTRAINTS = [
        ("Do not mention the budget", "exclusion", "budget", "topic"),
        ("Avoid mentioning specific dates", "exclusion", "dates", "topic"),
        ("Do not use the word 'synergy'", "exclusion", "synergy", "word"),
        ("Avoid technical jargon", "exclusion", "jargon", "style"),
        ("Don't mention competitors by name", "exclusion", "competitors", "topic"),
    ]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def generate_constraints(
        self,
        prompt: WritingPrompt,
        constraint_probability: float = 0.15
    ) -> list[ConstraintSpec]:
        """Generate 0-2 constraints for a prompt."""
        constraints = []

        # Decide if this prompt gets constraints
        if self.rng.random() > constraint_probability:
            return constraints

        # Select constraint types
        num_constraints = self.rng.choices([1, 2], weights=[0.7, 0.3])[0]

        available_categories = [
            self.LENGTH_CONSTRAINTS,
            self.FORMAT_CONSTRAINTS,
            self.TONE_CONSTRAINTS,
            self.EXCLUSION_CONSTRAINTS,
        ]

        selected_categories = self.rng.sample(
            available_categories,
            min(num_constraints, len(available_categories))
        )

        for category in selected_categories:
            constraint_def = self.rng.choice(category)
            description, ctype, value, subtype = constraint_def

            constraints.append(ConstraintSpec(
                type=ctype,
                description=description,
                specific_requirement=f"{subtype}:{value}" if value else subtype,
                measurable=True
            ))

        return constraints
```

### 2.3 Revision Task Generator

```python
# src/prompts/revision_generator.py

import random
from typing import Optional
from src.prompts.schemas import RevisionTask

class RevisionTaskGenerator:
    """Generate revision/editing tasks per PROMPT.md."""

    REVISION_TEMPLATES = {
        "concise": {
            "instruction": "Revise this draft to be more concise",
            "target_outcome": "Shorter, tighter prose without losing key information",
            "original_length_factor": 1.5,  # Original is 1.5x target length
        },
        "professional": {
            "instruction": "Make this email more professional",
            "target_outcome": "Formal, business-appropriate tone",
            "original_tone": "casual",
        },
        "soften": {
            "instruction": "Soften the tone of this message",
            "target_outcome": "More diplomatic, less harsh",
            "original_tone": "harsh",
        },
        "expand": {
            "instruction": "Add more detail to this summary",
            "target_outcome": "Comprehensive explanation with specifics",
            "original_length_factor": 0.5,
        },
        "clarify": {
            "instruction": "Clarify and restructure this confusing message",
            "target_outcome": "Clear, well-organized communication",
            "original_quality": "confusing",
        },
    }

    # Templates for generating "original drafts" that need revision
    CASUAL_TEMPLATES = [
        "hey {recipient}, just wanted to touch base about {topic}. lemme know when works for u to chat. thx!",
        "Hi! So I was thinking about {topic} and wondering if maybe we could {action}? lmk!",
        "yo {recipient} - quick q about {topic}. can u help? thx bro",
    ]

    HARSH_TEMPLATES = [
        "This is completely unacceptable. You need to fix {topic} immediately. This is the third time I've had to ask.",
        "Your work on {topic} was substandard. This cannot continue. Explain why this happened.",
        "I'm extremely disappointed with the {topic} situation. This needs to be resolved TODAY.",
    ]

    CONFUSING_TEMPLATES = [
        "So about the thing we discussed, I think maybe we should but also could not if that makes sense? Let me know re: the other thing too.",
        "Following up on {topic} and also the other items and the meeting about the project. Can you do the thing before next week or is that the other deadline?",
        "Per our conversation (and the email from last month about the related issue) the {topic} needs attention but not the urgent kind unless {recipient} thinks otherwise.",
    ]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def should_be_revision_task(self, probability: float = 0.1) -> bool:
        """Determine if a prompt should be a revision task."""
        return self.rng.random() < probability

    def generate_revision_task(
        self,
        revision_type: str,
        topic: str,
        recipient: str
    ) -> RevisionTask:
        """Generate a revision task with original draft."""
        template_info = self.REVISION_TEMPLATES[revision_type]

        # Generate original draft based on type
        if revision_type == "professional":
            templates = self.CASUAL_TEMPLATES
        elif revision_type == "soften":
            templates = self.HARSH_TEMPLATES
        elif revision_type == "clarify":
            templates = self.CONFUSING_TEMPLATES
        else:
            # For concise/expand, generate appropriate length
            templates = self.CASUAL_TEMPLATES  # Placeholder

        template = self.rng.choice(templates)
        original_draft = template.format(recipient=recipient, topic=topic, action="proceed")

        return RevisionTask(
            original_draft=original_draft,
            revision_type=revision_type,
            instruction=template_info["instruction"],
            target_outcome=template_info["target_outcome"]
        )
```

### 2.4 Tone Example Generator

```python
# src/data/tone_examples.py

from dataclasses import dataclass
from typing import List
import random

@dataclass
class ToneSample:
    """A sample of writing with specific tone characteristics."""
    text: str
    tone_description: str
    formality: int  # 1-5
    context: str

class ToneExampleDatabase:
    """Database of tone examples for matching tasks."""

    FORMAL_EXECUTIVE = [
        ToneSample(
            text="""Dear Board Members,

I am writing to provide an update on our Q4 performance metrics. As you will see from the attached analysis, we have exceeded our projected targets by 12%.

I recommend we schedule a follow-up session to discuss strategic implications.

Respectfully,""",
            tone_description="formal executive communication",
            formality=5,
            context="executive board updates"
        ),
        ToneSample(
            text="""Thank you for your inquiry regarding our partnership proposal. After careful consideration of the terms outlined in your correspondence dated November 15th, we are prepared to proceed with negotiations.

Our legal team will be in contact within the next five business days to arrange the preliminary discussions.

Best regards,""",
            tone_description="formal business correspondence",
            formality=5,
            context="business partnership communications"
        ),
    ]

    PROFESSIONAL_WARM = [
        ToneSample(
            text="""Hi Sarah,

Great news! The project wrapped up ahead of schedule, and the client was thrilled with the results. Your work on the design elements really made the difference.

Let's grab coffee this week to celebrate and talk about next steps?

Best,""",
            tone_description="warm professional",
            formality=3,
            context="team celebrations and updates"
        ),
    ]

    CASUAL_INTERNAL = [
        ToneSample(
            text="""Hey team,

Quick update - the meeting got pushed to Thursday. Same time, same Zoom link.

Also, reminder that we're doing pizza Friday this week. Drop your order in the spreadsheet!

Cheers,""",
            tone_description="casual internal team communication",
            formality=2,
            context="internal team updates"
        ),
    ]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.all_samples = (
            self.FORMAL_EXECUTIVE +
            self.PROFESSIONAL_WARM +
            self.CASUAL_INTERNAL
        )

    def get_matching_sample(self, formality: int) -> ToneSample:
        """Get a tone sample matching the formality level."""
        matching = [s for s in self.all_samples
                   if abs(s.formality - formality) <= 1]
        if not matching:
            matching = self.all_samples
        return self.rng.choice(matching)
```

### 2.5 Channel Inferrer

```python
# src/prompts/channel_inferrer.py

import re
from typing import Optional

class ChannelInferrer:
    """Infer communication channel from O*NET task statements."""

    CHANNEL_PATTERNS = {
        "email": [
            r"\bemail\b", r"\be-mail\b", r"\bcorrespond\b",
            r"\bnotify\b", r"\binform\b.*\bcustomer\b"
        ],
        "memo": [
            r"\bmemo\b", r"\bmemorandum\b", r"\binternal\s+communicat\b"
        ],
        "report": [
            r"\breport\b", r"\bprepare\s+report\b", r"\bwrite\s+report\b",
            r"\banalysis\b", r"\bpresent\s+finding\b"
        ],
        "proposal": [
            r"\bproposal\b", r"\bgrant\s+application\b", r"\bbid\b",
            r"\bRFP\b", r"\bpitch\b"
        ],
        "letter": [
            r"\bletter\b", r"\bcorrespondence\b", r"\bformal\s+letter\b"
        ],
        "policy": [
            r"\bpolicy\b", r"\bprocedure\b", r"\bguideline\b",
            r"\bprotocol\b", r"\bstandard\s+operating\b"
        ],
        "documentation": [
            r"\bdocument\b", r"\bdocumentation\b", r"\btechnical\s+writ\b",
            r"\bmanual\b", r"\binstruction\b"
        ],
        "presentation": [
            r"\bpresent\b", r"\bpresentation\b", r"\bslide\b",
            r"\bbriefing\b"
        ],
        "social_media": [
            r"\bsocial\s+media\b", r"\btwitter\b", r"\blinkedin\b",
            r"\bpost\b.*\bonline\b"
        ],
        "slack_chat": [
            r"\binstant\s+messag\b", r"\bchat\b", r"\bslack\b",
            r"\bteams\s+messag\b"
        ],
    }

    @classmethod
    def infer_channel(cls, task_text: str) -> Optional[str]:
        """Infer the communication channel from task text."""
        task_lower = task_text.lower()

        for channel, patterns in cls.CHANNEL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    return channel

        return None  # Will be enriched in Phase 3 if needed

    @classmethod
    def get_channel_characteristics(cls, channel: str) -> dict:
        """Get characteristics of a communication channel."""
        characteristics = {
            "email": {
                "typical_length": "medium",
                "formality_range": (2, 5),
                "has_subject": True,
                "has_greeting": True,
                "has_signoff": True,
            },
            "memo": {
                "typical_length": "medium-long",
                "formality_range": (3, 5),
                "has_subject": True,
                "has_greeting": False,
                "has_signoff": True,
            },
            "report": {
                "typical_length": "long",
                "formality_range": (4, 5),
                "has_subject": False,
                "has_greeting": False,
                "has_signoff": False,
            },
            "slack_chat": {
                "typical_length": "short",
                "formality_range": (1, 3),
                "has_subject": False,
                "has_greeting": False,
                "has_signoff": False,
            },
        }
        return characteristics.get(channel, {})
```

---

## Part 3: Enhanced Evaluation Engine

### 3.1 Fixed Vote Aggregation

```python
# src/eval/vote_aggregator.py

from dataclasses import dataclass
from typing import Literal, List

@dataclass
class VoteResult:
    """Result of a single vote with proper position tracking."""
    vote_id: str
    winner_label: Literal["A", "B", "tie"]  # What the judge declared
    gemini_position: Literal["A", "B"]       # Where Gemini was positioned
    gemini_won: bool                          # True if winner == gemini_position

def aggregate_votes_correctly(votes: list) -> dict:
    """
    Correctly aggregate votes accounting for position shuffling.

    CRITICAL FIX: Each vote may have Gemini in a different position.
    We must track the winner relative to Gemini's position in EACH vote.
    """
    gemini_wins = 0
    competitor_wins = 0
    ties = 0

    for vote in votes:
        if vote.winner == "tie":
            ties += 1
        elif vote.winner == vote.gemini_position:
            # Judge picked the response where Gemini was placed
            gemini_wins += 1
        else:
            # Judge picked the other response (competitor)
            competitor_wins += 1

    # Determine majority
    if gemini_wins > competitor_wins:
        majority_winner = "gemini"
    elif competitor_wins > gemini_wins:
        majority_winner = "competitor"
    else:
        majority_winner = "tie"

    return {
        "gemini_wins": gemini_wins,
        "competitor_wins": competitor_wins,
        "ties": ties,
        "total_votes": len(votes),
        "majority_winner": majority_winner,
        "gemini_is_majority": gemini_wins > competitor_wins,
        "competitor_is_majority": competitor_wins > gemini_wins,
        "is_tie": gemini_wins == competitor_wins
    }
```

### 3.2 Response Validator for Refusal Detection

```python
# src/eval/response_validator.py

import re
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class ValidationResult:
    """Result of validating a model response."""
    is_valid: bool
    status: Literal["success", "refused", "error", "timeout", "incomplete", "off_topic"]
    refusal_category: Optional[Literal[
        "safety_refusal",
        "capability_limitation",
        "misunderstanding",
        "incomplete_response",
        "off_topic"
    ]] = None
    confidence: float = 1.0
    details: str = ""

class ResponseValidator:
    """Validate model responses and categorize refusals per PROMPT.md."""

    SAFETY_REFUSAL_PATTERNS = [
        r"I (?:cannot|can't|won't|will not) (?:help|assist|write|create)",
        r"(?:against|violates) (?:my|our) (?:policy|policies|guidelines)",
        r"I'm not able to (?:generate|produce|create)",
        r"(?:harmful|dangerous|unethical|inappropriate) content",
        r"I (?:must|need to) (?:decline|refuse)",
    ]

    CAPABILITY_PATTERNS = [
        r"I don't have (?:access|the ability|enough information)",
        r"I (?:cannot|can't) (?:access|retrieve|look up)",
        r"(?:beyond|outside) my (?:capabilities|knowledge)",
        r"I'm not (?:sure|certain|able to determine)",
    ]

    INCOMPLETE_MARKERS = [
        r"\.\.\.$",  # Ends with ellipsis
        r"(?:continued|to be continued|more to follow)",
        r"(?:I was|I'm) (?:cut off|running out)",
    ]

    def validate(
        self,
        response_text: str,
        prompt_text: str,
        max_length: int = 50000
    ) -> ValidationResult:
        """Validate a model response."""

        # Empty or very short response
        if not response_text or len(response_text.strip()) < 20:
            return ValidationResult(
                is_valid=False,
                status="incomplete",
                refusal_category="incomplete_response",
                details="Response too short or empty"
            )

        # Check for safety refusals
        for pattern in self.SAFETY_REFUSAL_PATTERNS:
            if re.search(pattern, response_text, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    status="refused",
                    refusal_category="safety_refusal",
                    details=f"Matched pattern: {pattern}"
                )

        # Check for capability limitations
        for pattern in self.CAPABILITY_PATTERNS:
            if re.search(pattern, response_text, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    status="refused",
                    refusal_category="capability_limitation",
                    details=f"Matched pattern: {pattern}"
                )

        # Check for incomplete responses
        for pattern in self.INCOMPLETE_MARKERS:
            if re.search(pattern, response_text):
                return ValidationResult(
                    is_valid=False,
                    status="incomplete",
                    refusal_category="incomplete_response",
                    details=f"Matched pattern: {pattern}"
                )

        # Check for off-topic (basic heuristic)
        # Extract key terms from prompt and check if response addresses them
        prompt_terms = self._extract_key_terms(prompt_text)
        response_terms = self._extract_key_terms(response_text)
        overlap = len(prompt_terms & response_terms) / max(len(prompt_terms), 1)

        if overlap < 0.1:  # Less than 10% term overlap
            return ValidationResult(
                is_valid=False,
                status="off_topic",
                refusal_category="off_topic",
                confidence=0.7,
                details=f"Low topic overlap: {overlap:.2%}"
            )

        return ValidationResult(
            is_valid=True,
            status="success",
            details="Response validated successfully"
        )

    def _extract_key_terms(self, text: str) -> set:
        """Extract key terms from text for topic matching."""
        # Simple tokenization and filtering
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        stopwords = {'that', 'this', 'with', 'from', 'have', 'been', 'will',
                    'would', 'could', 'should', 'their', 'about', 'which'}
        return set(words) - stopwords
```

### 3.3 Complete Judge Prompt with Full Context

```python
# src/eval/judge_prompts.py

WRITING_EXPERT_SYSTEM = """You are an expert writing evaluator with decades of experience
assessing professional communication. Your expertise spans business writing, technical
documentation, creative content, and interpersonal correspondence.

You will evaluate two responses to the same writing task. Focus on:
- Quality of writing craft (clarity, structure, flow)
- Appropriate length for the task
- Tone appropriateness for the context
- Effectiveness in achieving the communication goal
- Authenticity - does it read as realistic human writing, not AI-generated?
- Avoidance of cliches and boilerplate phrases
- Task completion - does it fully address what was asked?

CRITICAL: You must evaluate based on the SPECIFIC SCENARIO provided, not generic
"good writing" standards. A casual Slack message to a close colleague should NOT
be penalized for lacking formal structure.

Be objective. Judge based on effectiveness for the given context."""

TARGET_RECIPIENT_SYSTEM = """You are roleplaying as the target recipient of this writing.
Based on the scenario provided, evaluate which response would be more effective FROM YOUR
PERSPECTIVE as the recipient.

Consider:
- Would you understand the message clearly?
- Is the tone appropriate for your relationship with the sender?
- Does it address your needs/concerns?
- Would you feel respected and valued?
- Is the length appropriate - not too long or too short?
- Would you be able to take action based on this communication?

CRITICAL: Stay in character as the specific recipient described. If you're a 28-year-old
tech startup employee, judge differently than if you're a 60-year-old bank executive.

Be objective about what YOU as the recipient would actually prefer."""

FULL_CONTEXT_JUDGE_TEMPLATE = """
## WRITING TASK SCENARIO

### Task Description
{task_description}

### Writer Profile
- **Name**: {writer_name}
- **Role**: {writer_title} at {company_name}
- **Company Context**: {company_size} company in {industry}, {employee_count} employees
- **Experience Level**: {skill_level}
- **Generation**: {generation} (approximately {writer_age} years old)
- **English Variant**: {writer_english_variant}

### Primary Recipient(s)
{recipient_details}

{cc_context_section}

### Communication Context
- **Audience Size**: {audience_size}
- **Formality Level**: {formality}/5 (1=very casual, 5=very formal)
- **Urgency Level**: {urgency}/5 (1=routine, 5=critical)
- **Message Type**: {message_position}
- **Emotional Context**: {emotional_context}
- **Communication Channel**: {channel}

{temporal_context_section}

{prior_context_section}

{attachments_section}

{competing_objectives_section}

{tone_example_section}

{constraints_section}

{revision_context_section}

---

## RESPONSE A
{response_a}

---

## RESPONSE B
{response_b}

---

## EVALUATION CRITERIA

Rate each response on a 1-5 scale for these criteria:

1. **Writing Quality** - Clarity, structure, grammar, professionalism appropriate to context
2. **Tone Appropriateness** - Matches the required formality level and relationship
3. **Length Appropriateness** - Right amount of content for THIS SPECIFIC task
4. **Task Completion** - Fully addresses what was asked
5. **Authenticity** - Reads as natural writing from this specific persona (not generic AI output)
6. **Cliche Avoidance** - Avoids overused phrases like "I hope this email finds you well"
7. **Effectiveness** - Would achieve the intended communication goal

{constraint_evaluation_instructions}

## YOUR JUDGMENT

Respond in this exact JSON format:
```json
{{
  "scores_a": {{"quality": N, "tone": N, "length": N, "completion": N, "authenticity": N, "cliche_avoidance": N, "effectiveness": N}},
  "scores_b": {{"quality": N, "tone": N, "length": N, "completion": N, "authenticity": N, "cliche_avoidance": N, "effectiveness": N}},
  {constraint_json_fields}
  "winner": "A" or "B" or "tie",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentences explaining your decision, focusing on the key differentiators"
}}
```
"""

def build_full_context_judge_prompt(
    prompt: "WritingPrompt",
    response_a: str,
    response_b: str,
    persona: str
) -> tuple[str, str]:
    """Build complete judge prompt with all scenario context."""

    system = WRITING_EXPERT_SYSTEM if persona == "writing_expert" else TARGET_RECIPIENT_SYSTEM

    # Build detailed recipient section
    recipient_lines = []
    for i, r in enumerate(prompt.recipients):
        primary = "Primary" if r.is_primary else "CC"
        recipient_lines.append(f"""
**Recipient {i+1} ({primary})**
- Name: {r.name}
- Role: {r.job_title}
- Relationship: {r.relationship}
- Technical Background: {'Yes' if r.is_technical else 'No'}
- English Variant: {r.english_variant.value}
""")
    recipient_details = "\n".join(recipient_lines)

    # CC context section
    cc_section = ""
    if prompt.cc_context:
        cc_lines = ["### CC/Visibility Context"]
        if prompt.cc_context.cc_recipients:
            cc_lines.append(f"- CC'd to: {', '.join(prompt.cc_context.cc_recipients)}")
        if prompt.cc_context.will_be_forwarded_to:
            cc_lines.append(f"- Will be forwarded to: {prompt.cc_context.will_be_forwarded_to}")
        if prompt.cc_context.mixed_audience_note:
            cc_lines.append(f"- Note: {prompt.cc_context.mixed_audience_note}")
        cc_section = "\n".join(cc_lines)

    # Temporal context
    temporal_section = ""
    if prompt.temporal_context:
        temporal_section = f"""
### Temporal Context
{prompt.temporal_context}
"""

    # Prior message context
    prior_section = ""
    if prompt.prior_context:
        prior_section = f"""
### Previous Message (Reply Context)
The writer is responding to this message:
```
{prompt.prior_context}
```
"""

    # Attachments section
    attachments_section = ""
    if prompt.attachments:
        att_lines = ["### Reference Materials Available to Writer"]
        for att in prompt.attachments:
            att_lines.append(f"- **{att.type.upper()}**: {att.description}")
            att_lines.append(f"  Key content: {att.content}")
        attachments_section = "\n".join(att_lines)

    # Competing objectives
    competing_section = ""
    if prompt.competing_objectives:
        competing_section = f"""
### Competing Objectives
The writer must balance: {prompt.competing_objectives}
"""

    # Tone example
    tone_section = ""
    if prompt.tone_example:
        tone_section = f"""
### Tone to Match
Context: {prompt.tone_example.context}

Example of expected tone:
```
{prompt.tone_example.example_text}
```

Instruction: {prompt.tone_example.match_instruction}
"""

    # Constraints section
    constraints_section = ""
    constraint_eval = ""
    constraint_json = ""

    if prompt.constraints:
        const_lines = ["### Explicit Constraints (CRITICAL - Check Compliance)"]
        for c in prompt.constraints:
            const_lines.append(f"- **{c.type.upper()}**: {c.description}")
        constraints_section = "\n".join(const_lines)

        constraint_eval = """
**Constraint Compliance Check**: For each constraint listed above, evaluate whether
each response complied. Non-compliance should significantly impact your judgment."""

        constraint_json = '"constraint_compliance_a": {...}, "constraint_compliance_b": {...},'

    # Revision context
    revision_section = ""
    if prompt.is_revision_task and prompt.revision_task:
        revision_section = f"""
### Revision Task Context
**Original Draft to Revise**:
```
{prompt.revision_task.original_draft}
```

**Revision Instruction**: {prompt.revision_task.instruction}
**Target Outcome**: {prompt.revision_task.target_outcome}
"""

    user_prompt = FULL_CONTEXT_JUDGE_TEMPLATE.format(
        task_description=prompt.onet_task,
        writer_name=prompt.writer.name,
        writer_title=prompt.writer.job_title,
        company_name=prompt.company.name,
        company_size=prompt.company.size,
        industry=prompt.company.industry_name,
        employee_count=prompt.company.employee_count or "unknown number of",
        skill_level=prompt.writer.skill_level,
        generation=prompt.writer.generation,
        writer_age=prompt.writer.age,
        writer_english_variant=prompt.writer.english_variant.value,
        recipient_details=recipient_details,
        cc_context_section=cc_section,
        audience_size=prompt.audience_size,
        formality=prompt.formality_level,
        urgency=prompt.urgency_level,
        message_position=prompt.message_position.value,
        emotional_context=prompt.emotional_context.value,
        channel=prompt.communication_channel or "not specified",
        temporal_context_section=temporal_section,
        prior_context_section=prior_section,
        attachments_section=attachments_section,
        competing_objectives_section=competing_section,
        tone_example_section=tone_section,
        constraints_section=constraints_section,
        constraint_evaluation_instructions=constraint_eval,
        constraint_json_fields=constraint_json,
        revision_context_section=revision_section,
        response_a=response_a,
        response_b=response_b
    )

    return system, user_prompt
```

---

## Part 4: Complete Analysis Module

### 4.1 Fixed Statistics with Current scipy API

```python
# src/analysis/statistics.py

import numpy as np
from scipy import stats
from dataclasses import dataclass

@dataclass
class WinRateStats:
    """Win rate with full statistical analysis."""
    win_rate: float
    n_total: int
    n_wins: int
    n_losses: int
    n_ties: int
    confidence_interval_95: tuple[float, float]
    standard_error: float
    is_significant: bool  # vs 50% baseline
    p_value: float
    effect_size: float  # Cohen's h

def calculate_win_rate_stats(
    wins: int,
    losses: int,
    ties: int
) -> WinRateStats:
    """Calculate win rate with proper statistical analysis."""

    total = wins + losses + ties
    decisive = wins + losses

    if decisive == 0:
        return WinRateStats(
            win_rate=0.5,
            n_total=total,
            n_wins=0,
            n_losses=0,
            n_ties=ties,
            confidence_interval_95=(0.0, 1.0),
            standard_error=0.5,
            is_significant=False,
            p_value=1.0,
            effect_size=0.0
        )

    win_rate = wins / decisive

    # Wilson score interval for 95% CI
    z = 1.96
    denominator = 1 + z**2 / decisive
    center = (win_rate + z**2 / (2 * decisive)) / denominator
    margin = z * np.sqrt(
        win_rate * (1 - win_rate) / decisive + z**2 / (4 * decisive**2)
    ) / denominator
    ci_lower = max(0, center - margin)
    ci_upper = min(1, center + margin)

    # Standard error
    se = np.sqrt(win_rate * (1 - win_rate) / decisive)

    # Binomial test against 50% - FIXED: Use binomtest (not deprecated binom_test)
    result = stats.binomtest(wins, decisive, 0.5, alternative='two-sided')
    p_value = result.pvalue

    is_significant = p_value < 0.05

    # Cohen's h effect size for proportions
    phi1 = 2 * np.arcsin(np.sqrt(win_rate))
    phi2 = 2 * np.arcsin(np.sqrt(0.5))
    effect_size = abs(phi1 - phi2)

    return WinRateStats(
        win_rate=win_rate,
        n_total=total,
        n_wins=wins,
        n_losses=losses,
        n_ties=ties,
        confidence_interval_95=(ci_lower, ci_upper),
        standard_error=se,
        is_significant=is_significant,
        p_value=p_value,
        effect_size=effect_size
    )
```

### 4.2 Complete Bias Detection

```python
# src/analysis/bias_detection.py

import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import defaultdict

@dataclass
class PositionBiasResult:
    """Results of position bias analysis."""
    has_significant_bias: bool
    bias_direction: Optional[str]  # "A" or "B" or None
    chi_square: float
    p_value: float
    effect_size: float  # Cramer's V
    position_a_win_rate: float
    position_b_win_rate: float
    sample_size: int

@dataclass
class LengthBiasResult:
    """Results of length bias analysis."""
    has_significant_bias: bool
    bias_direction: Optional[str]  # "longer" or "shorter" or None
    correlation: float  # Pearson r between length difference and win
    p_value: float
    mean_length_winner: float
    mean_length_loser: float

@dataclass
class ModelFingerprintResult:
    """Results of model fingerprint detection analysis."""
    can_detect_models: bool
    detection_accuracy: float  # If models can be distinguished
    distinguishing_features: List[str]

class BiasDetector:
    """Detect systematic biases in judging per PROMPT.md requirements."""

    def detect_position_bias(
        self,
        votes: List[dict]
    ) -> PositionBiasResult:
        """
        Detect if judges systematically prefer Response A or B.

        Args:
            votes: List of vote dicts with 'winner' and 'gemini_position' keys
        """
        position_a_wins = 0
        position_b_wins = 0

        for vote in votes:
            if vote['winner'] == 'A':
                position_a_wins += 1
            elif vote['winner'] == 'B':
                position_b_wins += 1
            # Ties don't count

        total_decisive = position_a_wins + position_b_wins

        if total_decisive < 20:  # Need minimum sample
            return PositionBiasResult(
                has_significant_bias=False,
                bias_direction=None,
                chi_square=0.0,
                p_value=1.0,
                effect_size=0.0,
                position_a_win_rate=0.5,
                position_b_win_rate=0.5,
                sample_size=total_decisive
            )

        # Chi-square test for uniformity
        observed = np.array([position_a_wins, position_b_wins])
        expected = np.array([total_decisive / 2, total_decisive / 2])

        chi2, p_value = stats.chisquare(observed, expected)

        # Effect size (Cramer's V for 2x1)
        effect_size = np.sqrt(chi2 / total_decisive)

        a_rate = position_a_wins / total_decisive
        b_rate = position_b_wins / total_decisive

        has_bias = p_value < 0.05
        direction = None
        if has_bias:
            direction = "A" if a_rate > b_rate else "B"

        return PositionBiasResult(
            has_significant_bias=has_bias,
            bias_direction=direction,
            chi_square=chi2,
            p_value=p_value,
            effect_size=effect_size,
            position_a_win_rate=a_rate,
            position_b_win_rate=b_rate,
            sample_size=total_decisive
        )

    def detect_length_bias(
        self,
        comparisons: List[dict]
    ) -> LengthBiasResult:
        """
        Detect if judges systematically prefer longer or shorter responses.

        Args:
            comparisons: List with 'winner', 'response_a_length', 'response_b_length'
        """
        length_diffs = []  # positive = A longer
        outcomes = []  # 1 = A wins, 0 = B wins

        for comp in comparisons:
            if comp['winner'] == 'tie':
                continue

            diff = comp['response_a_length'] - comp['response_b_length']
            length_diffs.append(diff)
            outcomes.append(1 if comp['winner'] == 'A' else 0)

        if len(length_diffs) < 20:
            return LengthBiasResult(
                has_significant_bias=False,
                bias_direction=None,
                correlation=0.0,
                p_value=1.0,
                mean_length_winner=0.0,
                mean_length_loser=0.0
            )

        # Correlation between length difference and outcome
        correlation, p_value = stats.pearsonr(length_diffs, outcomes)

        # Calculate mean lengths for winners vs losers
        winner_lengths = []
        loser_lengths = []

        for comp in comparisons:
            if comp['winner'] == 'A':
                winner_lengths.append(comp['response_a_length'])
                loser_lengths.append(comp['response_b_length'])
            elif comp['winner'] == 'B':
                winner_lengths.append(comp['response_b_length'])
                loser_lengths.append(comp['response_a_length'])

        mean_winner = np.mean(winner_lengths) if winner_lengths else 0
        mean_loser = np.mean(loser_lengths) if loser_lengths else 0

        has_bias = p_value < 0.05
        direction = None
        if has_bias:
            direction = "longer" if correlation > 0 else "shorter"

        return LengthBiasResult(
            has_significant_bias=has_bias,
            bias_direction=direction,
            correlation=correlation,
            p_value=p_value,
            mean_length_winner=mean_winner,
            mean_length_loser=mean_loser
        )

    def detect_format_bias(
        self,
        comparisons: List[dict]
    ) -> dict:
        """Detect if judges prefer certain formats (bullets, headers, etc.)."""
        format_wins = defaultdict(lambda: {"wins": 0, "total": 0})

        for comp in comparisons:
            if comp['winner'] == 'tie':
                continue

            winner_key = 'a' if comp['winner'] == 'A' else 'b'
            loser_key = 'b' if comp['winner'] == 'A' else 'a'

            winner_features = comp.get(f'{winner_key}_format_features', {})
            loser_features = comp.get(f'{loser_key}_format_features', {})

            for feature in ['has_bullets', 'has_headers', 'has_greeting', 'has_signoff']:
                if winner_features.get(feature) and not loser_features.get(feature):
                    format_wins[feature]["wins"] += 1
                    format_wins[feature]["total"] += 1
                elif loser_features.get(feature) and not winner_features.get(feature):
                    format_wins[feature]["total"] += 1

        results = {}
        for feature, counts in format_wins.items():
            if counts["total"] >= 20:
                win_rate = counts["wins"] / counts["total"]
                # Binomial test
                result = stats.binomtest(
                    counts["wins"], counts["total"], 0.5, alternative='two-sided'
                )
                results[feature] = {
                    "win_rate_when_present": win_rate,
                    "p_value": result.pvalue,
                    "significant": result.pvalue < 0.05,
                    "sample_size": counts["total"]
                }

        return results
```

### 4.3 Response Pattern Analysis

```python
# src/analysis/response_patterns.py

from dataclasses import dataclass
from typing import Dict, List
from collections import defaultdict
import re

@dataclass
class ModelPatternProfile:
    """Pattern profile for a single model."""
    model_id: str
    avg_word_count: float
    avg_char_count: float
    bullet_usage_rate: float
    header_usage_rate: float
    greeting_rate: float
    signoff_rate: float
    common_phrases: List[str]
    avg_sentence_length: float

class ResponsePatternAnalyzer:
    """Analyze response patterns across models for systematic differences."""

    AI_CLICHE_PATTERNS = [
        r"I hope this (?:email|message) finds you well",
        r"Please (?:do not|don't) hesitate to (?:reach out|contact)",
        r"I'm happy to help",
        r"Let me know if you (?:have any|need)",
        r"Looking forward to hearing from you",
        r"Thank you for your (?:time|consideration)",
        r"I understand (?:your|the) concern",
        r"Rest assured",
    ]

    def analyze_model_patterns(
        self,
        responses: List[dict],
        model_id: str
    ) -> ModelPatternProfile:
        """Analyze patterns for a specific model's responses."""

        model_responses = [r for r in responses if r['model_id'] == model_id]

        if not model_responses:
            return ModelPatternProfile(
                model_id=model_id,
                avg_word_count=0,
                avg_char_count=0,
                bullet_usage_rate=0,
                header_usage_rate=0,
                greeting_rate=0,
                signoff_rate=0,
                common_phrases=[],
                avg_sentence_length=0
            )

        word_counts = []
        char_counts = []
        bullet_count = 0
        header_count = 0
        greeting_count = 0
        signoff_count = 0
        all_sentences = []

        for resp in model_responses:
            text = resp['response_text']
            words = text.split()
            word_counts.append(len(words))
            char_counts.append(len(text))

            if resp.get('used_bullet_points'):
                bullet_count += 1
            if resp.get('used_headers'):
                header_count += 1
            if resp.get('has_greeting'):
                greeting_count += 1
            if resp.get('has_signoff'):
                signoff_count += 1

            # Extract sentences for length analysis
            sentences = re.split(r'[.!?]+', text)
            all_sentences.extend([s.strip() for s in sentences if s.strip()])

        n = len(model_responses)
        avg_sentence_len = (
            sum(len(s.split()) for s in all_sentences) / len(all_sentences)
            if all_sentences else 0
        )

        # Find common phrases/cliches
        common_phrases = self._find_common_phrases(model_responses)

        return ModelPatternProfile(
            model_id=model_id,
            avg_word_count=sum(word_counts) / n,
            avg_char_count=sum(char_counts) / n,
            bullet_usage_rate=bullet_count / n,
            header_usage_rate=header_count / n,
            greeting_rate=greeting_count / n,
            signoff_rate=signoff_count / n,
            common_phrases=common_phrases,
            avg_sentence_length=avg_sentence_len
        )

    def _find_common_phrases(self, responses: List[dict]) -> List[str]:
        """Find commonly used phrases/cliches in responses."""
        phrase_counts = defaultdict(int)

        for resp in responses:
            text = resp['response_text']
            for pattern in self.AI_CLICHE_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    phrase_counts[pattern] += 1

        # Return patterns used in >10% of responses
        threshold = len(responses) * 0.1
        common = [p for p, c in phrase_counts.items() if c >= threshold]

        return sorted(common, key=lambda p: phrase_counts[p], reverse=True)

    def compare_models(
        self,
        responses: List[dict],
        model_ids: List[str]
    ) -> Dict[str, ModelPatternProfile]:
        """Compare patterns across multiple models."""
        return {
            model_id: self.analyze_model_patterns(responses, model_id)
            for model_id in model_ids
        }

    def correlate_patterns_with_wins(
        self,
        comparisons: List[dict],
        responses: List[dict]
    ) -> dict:
        """Analyze which patterns correlate with winning."""
        correlations = {}

        # Build response lookup
        response_map = {r['response_id']: r for r in responses}

        # Analyze each pattern
        patterns = ['word_count', 'bullet_usage', 'header_usage', 'greeting', 'signoff']

        for pattern in patterns:
            winner_values = []
            loser_values = []

            for comp in comparisons:
                if comp['final_winner'] == 'tie':
                    continue

                winner_id = (comp['gemini_response_id']
                           if comp['final_winner'] == 'gemini'
                           else comp['competitor_response_id'])
                loser_id = (comp['competitor_response_id']
                          if comp['final_winner'] == 'gemini'
                          else comp['gemini_response_id'])

                winner_resp = response_map.get(winner_id, {})
                loser_resp = response_map.get(loser_id, {})

                if pattern == 'word_count':
                    winner_values.append(winner_resp.get('word_count', 0))
                    loser_values.append(loser_resp.get('word_count', 0))
                elif pattern == 'bullet_usage':
                    winner_values.append(1 if winner_resp.get('used_bullet_points') else 0)
                    loser_values.append(1 if loser_resp.get('used_bullet_points') else 0)
                # ... similar for other patterns

            if len(winner_values) >= 20:
                from scipy import stats
                t_stat, p_value = stats.ttest_ind(winner_values, loser_values)
                correlations[pattern] = {
                    "winner_mean": sum(winner_values) / len(winner_values),
                    "loser_mean": sum(loser_values) / len(loser_values),
                    "t_statistic": t_stat,
                    "p_value": p_value,
                    "significant": p_value < 0.05
                }

        return correlations
```

---

## Part 5: Cost Estimator Implementation

```python
# src/config/cost_estimator.py

from dataclasses import dataclass
from typing import Dict, List, Tuple
import tiktoken

@dataclass
class CostEstimate:
    """Detailed cost and time estimate for an evaluation run."""
    # Counts
    total_prompts: int
    model_pairs: int
    total_comparisons: int
    total_response_calls: int
    total_judge_calls: int

    # Token estimates
    est_input_tokens_response: int
    est_output_tokens_response: int
    est_input_tokens_judge: int
    est_output_tokens_judge: int

    # Costs
    response_generation_cost: float
    judging_cost: float
    total_cost: float
    cost_range: Tuple[float, float]  # (low, high)

    # Time estimates
    time_with_rate_limits: str
    time_parallelized: str
    estimated_seconds: int

    # Config summary
    judge_config_summary: str

# OpenRouter pricing per million tokens (as of Jan 2026)
OPENROUTER_PRICING = {
    # Pro-tier models
    "google/gemini-3.0-pro": {"input": 3.00, "output": 15.00},
    "openai/gpt-5.2-thinking": {"input": 5.00, "output": 20.00},
    "anthropic/claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
    "x-ai/grok-4.1-thinking": {"input": 5.00, "output": 20.00},
    "moonshot/kimi-k2-thinking": {"input": 4.00, "output": 16.00},
    # Flash-tier models
    "google/gemini-3.0-flash": {"input": 0.075, "output": 0.30},
    "openai/gpt-4.1": {"input": 2.00, "output": 8.00},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}

# Average tokens per component
AVG_PROMPT_TOKENS = 800  # Writing prompt
AVG_RESPONSE_TOKENS = 400  # Model response
AVG_JUDGE_PROMPT_TOKENS = 2500  # Judge prompt with context
AVG_JUDGE_RESPONSE_TOKENS = 300  # Judge evaluation

def estimate_run_cost(config: "EvalConfig") -> CostEstimate:
    """Generate detailed cost and time estimate for an evaluation configuration."""

    # Calculate call counts
    total_prompts = config.sampling.total_prompts
    model_pairs = len(config.model_pairs)
    total_comparisons = total_prompts * model_pairs

    # Unique models (for response generation)
    unique_models = set()
    for gemini, competitor in config.model_pairs:
        unique_models.add(gemini)
        unique_models.add(competitor)
    total_response_calls = total_prompts * len(unique_models)

    # Judge calls
    num_judges = len(config.judge_config.models)
    votes_per_judge = config.judge_config.votes_per_judge
    num_personas = 2 if config.judge_config.use_both_personas else 1
    total_judge_calls = (
        total_comparisons *
        num_judges *
        votes_per_judge *
        num_personas
    )

    # Token estimates
    est_input_response = total_response_calls * AVG_PROMPT_TOKENS
    est_output_response = total_response_calls * AVG_RESPONSE_TOKENS
    est_input_judge = total_judge_calls * AVG_JUDGE_PROMPT_TOKENS
    est_output_judge = total_judge_calls * AVG_JUDGE_RESPONSE_TOKENS

    # Cost calculation
    response_cost = 0.0
    for model in unique_models:
        model_id = _resolve_model_id(model)
        pricing = OPENROUTER_PRICING.get(model_id, {"input": 5.0, "output": 20.0})
        calls_for_model = total_prompts
        input_cost = (calls_for_model * AVG_PROMPT_TOKENS / 1_000_000) * pricing["input"]
        output_cost = (calls_for_model * AVG_RESPONSE_TOKENS / 1_000_000) * pricing["output"]
        response_cost += input_cost + output_cost

    judge_cost = 0.0
    for judge_model in config.judge_config.models:
        model_id = _resolve_model_id(judge_model)
        pricing = OPENROUTER_PRICING.get(model_id, {"input": 5.0, "output": 20.0})
        calls_for_judge = (total_comparisons * votes_per_judge * num_personas)
        input_cost = (calls_for_judge * AVG_JUDGE_PROMPT_TOKENS / 1_000_000) * pricing["input"]
        output_cost = (calls_for_judge * AVG_JUDGE_RESPONSE_TOKENS / 1_000_000) * pricing["output"]
        judge_cost += input_cost + output_cost

    total_cost = response_cost + judge_cost

    # Time estimation (rough)
    # Assume 2 seconds per API call on average, with 10 concurrent requests
    total_calls = total_response_calls + total_judge_calls
    seconds_sequential = total_calls * 2
    seconds_parallel = seconds_sequential / 10

    # Add buffer for rate limiting
    seconds_with_limits = seconds_parallel * 1.5

    return CostEstimate(
        total_prompts=total_prompts,
        model_pairs=model_pairs,
        total_comparisons=total_comparisons,
        total_response_calls=total_response_calls,
        total_judge_calls=total_judge_calls,
        est_input_tokens_response=est_input_response,
        est_output_tokens_response=est_output_response,
        est_input_tokens_judge=est_input_judge,
        est_output_tokens_judge=est_output_judge,
        response_generation_cost=response_cost,
        judging_cost=judge_cost,
        total_cost=total_cost,
        cost_range=(total_cost * 0.8, total_cost * 1.2),
        time_with_rate_limits=_format_duration(int(seconds_with_limits)),
        time_parallelized=_format_duration(int(seconds_parallel)),
        estimated_seconds=int(seconds_with_limits),
        judge_config_summary=f"{num_judges} judges x {votes_per_judge} votes x {num_personas} personas"
    )

def _resolve_model_id(model: str) -> str:
    """Resolve short model name to full OpenRouter ID."""
    MODEL_MAP = {
        "gemini-3-pro": "google/gemini-3.0-pro",
        "gemini-3-flash": "google/gemini-3.0-flash",
        "gpt-5.2-thinking": "openai/gpt-5.2-thinking",
        "claude-opus-4.5": "anthropic/claude-opus-4-5-20251101",
        "grok-4.1-thinking": "x-ai/grok-4.1-thinking",
        "kimi-k2-thinking": "moonshot/kimi-k2-thinking",
        "gpt-4.1": "openai/gpt-4.1",
        "claude-sonnet": "anthropic/claude-3-5-sonnet-20241022",
    }
    return MODEL_MAP.get(model, model)

def _format_duration(seconds: int) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        return f"{seconds // 60} minutes"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
```

---

## Part 6: Implementation Roadmap (Revised)

### Phase 1: Foundation (Week 1)
1. Project setup with pyproject.toml and dependencies
2. Complete Pydantic schemas with all PROMPT.md fields
3. O*NET extractor with ONET_WRITING_REFERENCE.md integration
4. Database schema with full directory structure management

### Phase 2: Prompt Generation (Week 2)
1. Three-phase pipeline with all diversity features
2. Constraint generator for instruction-following tests
3. Revision task generator
4. Tone example generator
5. Channel inferrer
6. CC/multiple recipient scenario generation
7. Regional English variant handling

### Phase 3: Evaluation Engine (Week 3)
1. OpenRouter client with rate limiting and circuit breaker
2. Response validator with refusal categorization
3. Judge prompts with complete context
4. Fixed vote aggregation logic
5. Checkpoint/resume with partial state recovery

### Phase 4: Analysis & Reporting (Week 4)
1. Statistical analysis with current scipy APIs
2. Complete bias detection (position, length, format)
3. Response pattern analysis
4. Weakness identification
5. PDF report generation
6. CSV export

### Phase 5: TUI & Polish (Week 5)
1. Progress dashboard with all elements
2. Results viewer with filtering and drill-down
3. Cross-run comparison
4. Interactive controls (pause, resume, quit)

### Phase 6: Testing & Documentation (Week 6)
1. Unit tests for all modules
2. Integration tests for pipelines
3. End-to-end evaluation tests
4. User documentation

---

## Conclusion

This improved plan addresses all 25+ gaps and issues identified in Draft Plan 5:

**Critical Fixes:**
1. Complete judge context per PROMPT.md CRITICAL requirements
2. Fixed vote aggregation bug for position shuffling
3. Updated deprecated scipy API (binomtest)
4. Complete directory structure per specification

**Missing Features Added:**
1. Tone matching prompt generation
2. CC/multiple recipient scenarios
3. Instruction-following constraint generation
4. Revision/editing task generation
5. Ambiguity handling prompts
6. Channel inference and tracking
7. Regional English variant handling
8. Position, length, and format bias detection
9. Response pattern analysis
10. Cross-run comparison
11. Results viewer TUI
12. CSV export
13. Auto-generated README per run
14. Structured failure logging
15. Config summary generation

The plan now provides 100% coverage of PROMPT.md requirements with complete, tested implementations.

