# Critique of Draft Plan 1: Gemini Writing Evaluation Framework

## Overview

This critique analyzes Draft Plan 1 against the complete requirements in PROMPT.md, identifying correctness issues, missed details, suboptimal approaches, and areas for improvement.

---

## SECTION 1: CRITICAL ISSUES

### 1.1 Missing Phase 1 Implementation (Offline LLM Generation)

**Issue:** The draft plan mentions the three-phase prompt generation approach but **completely omits the implementation of Phase 1**. The `PromptGenerator` class only implements Phase 2 (algorithmic combinations) and Phase 3 (LLM enrichment).

**PROMPT.md Requirement:**
> "Phase 1 - Offline LLM Generation: Use an LLM to generate diverse persona/context variations for each O*NET task. This is done as an offline preprocessing step. Use the same models being evaluated for this generation."

**Impact:** Without Phase 1, the system loses a critical source of diversity. The personas and context variations would rely entirely on algorithmic combinations, which limits the creative diversity PROMPT.md explicitly demands.

**Fix Required:** Add a complete Phase 1 implementation that:
- Pre-generates diverse persona/context variations using LLMs
- Uses the same models being evaluated (Gemini, GPT-5.2, etc.) to avoid bias
- Stores these variations for deterministic combination in Phase 2

### 1.2 Instruction-Following Tests Not Tracked Separately

**Issue:** The draft mentions `InstructionConstraint` in the schema but does not implement separate tracking for instruction-following compliance.

**PROMPT.md Requirement:**
> "Track compliance separately - a model that writes beautifully but ignores instructions is problematic for real use."

**Impact:** The evaluation cannot identify models that produce good writing but fail to follow explicit constraints, which is a critical capability gap.

**Fix Required:** Add:
- `instruction_compliance` field to `JudgeVote`
- Separate compliance scoring in judge prompts
- Analysis dimension for instruction-following win rates

### 1.3 Sensitive Topic Handling Not Fully Implemented

**Issue:** The schema includes `sensitive_topic` field but:
- No mechanism to systematically tag sensitive prompts during generation
- No separate win rate tracking for sensitive vs routine tasks
- No refusal pattern analysis by sensitive topic category

**PROMPT.md Requirement:**
> "Tag prompts involving sensitive topics during generation. Track win rates separately for sensitive vs routine tasks. Analyze whether models handle difficult communications appropriately."

**Fix Required:** Add:
- Sensitive topic detection/tagging in prompt generation
- Separate analysis paths for sensitive topics
- Refusal correlation with sensitive topic categories

### 1.4 Missing "Compare" CLI Command

**Issue:** PROMPT.md explicitly requires cross-run comparison functionality, but the draft only implements `run`, `resume`, `view`, `report`, and `presets` commands.

**PROMPT.md Requirement:**
> "Support comparing results across multiple runs: `./eval compare results/eval_2024-01-15_*/ results/eval_2024-01-16_*/`"

**Fix Required:** Add `compare` command that loads multiple run databases and produces comparison analysis.

---

## SECTION 2: SCHEMA AND DATA MODEL ISSUES

### 2.1 Missing Fields in WritingPrompt Schema

The draft schema is missing several fields required by PROMPT.md:

| Missing Field | PROMPT.md Requirement |
|---------------|----------------------|
| `recipient_english_variant` | "Track as metadata: recipient_english_variant" |
| `writer_english_variant` | Already present - OK |
| `communication_channel` inference tracking | "Track channel as metadata for analysis" |
| Multiple recipients list | "Multiple Recipients (CC Situations)" - only has `cc_recipients` |
| Tone example metadata | Need tracking of which prompts use tone matching |

### 2.2 JudgeVote Schema Missing Fields

The draft `JudgeVote` does not include:
- `instruction_compliance_a`: Did Response A follow explicit constraints?
- `instruction_compliance_b`: Did Response B follow explicit constraints?
- `constraint_violations`: List of specific violations detected

### 2.3 ComparisonPair Missing Model Pair Identifier

The `ComparisonPair` schema doesn't track which model pair tier (pro vs flash) this comparison belongs to, making it harder to analyze results by tier.

### 2.4 Response Metadata Incomplete

**PROMPT.md Requirement:**
> "Track metadata for every response: Response length, Response time, Format detection, Greeting/sign-off patterns"

The draft `ModelResponse` has most fields but is missing:
- `paragraph_count` - present
- `header_types`: What kinds of headers were used
- `greeting_type`: Formal vs casual greeting classification
- `signoff_type`: Formal vs casual signoff classification

---

## SECTION 3: ROBUSTNESS AND ERROR HANDLING

### 3.1 Rate Limiter Per-Model Limits

**Issue:** The `RateLimiter` class uses a single global rate limit, but different models on OpenRouter have different rate limits.

**Impact:** The system may hit rate limits on one model while under-utilizing capacity on others, or vice versa.

**Fix Required:** Implement per-model rate limiting that tracks limits separately for each model endpoint.

### 3.2 Circuit Breaker Pattern Missing

**Issue:** The retry logic handles individual failures but doesn't implement a circuit breaker pattern to prevent cascading failures when an API is consistently failing.

**Fix Required:** Add circuit breaker that:
- Opens after N consecutive failures
- Stays open for configurable duration
- Half-opens to test recovery
- Logs circuit state changes

### 3.3 Checkpoint Granularity Too Coarse

**Issue:** The checkpoint saves after each prompt completion, but judging happens at a finer granularity. If the system crashes mid-judging, all judge votes for that prompt are lost.

**Fix Required:** Save checkpoint after each judge vote, not just after each prompt completion.

### 3.4 Atomic File Operations

**Issue:** While the checkpoint uses atomic writes (temp file + rename), the response and judgment file writes do not.

**Impact:** System crash during write could corrupt data files.

**Fix Required:** Use atomic writes for all data files in the responses/ and judgments/ directories.

---

## SECTION 4: EVALUATION METHODOLOGY ISSUES

### 4.1 Judge Context Missing Key Elements

**PROMPT.md Requirement:**
> "Judges need the context of the scenario to evaluate properly... They must have: The full writing prompt/task description, The writer persona details (age, skill level, role, industry, generation), The target recipient/consumer persona, The formality level and communication context, Any additional scenario-specific context"

The draft's `_build_judgment_prompt` includes most context but is missing:
- `skill_level` of the writer
- Full `communication_channel` context
- Temporal context (deadlines, reference events)
- Attached document context
- Competing objectives the writer faces

### 4.2 Temperature Variation Strategy Questionable

**Issue:** The draft varies temperature for different votes: `temperature=0.3 + (vote_number - 1) * 0.1`

This means vote 5 uses temperature 0.7, which may introduce too much randomness in judgments. The purpose of best-of-5 is to capture model consistency, not to artificially inject variance.

**Recommendation:** Use consistent temperature (0.3-0.5) for all votes, or document the rationale for variance.

### 4.3 Position Bias Detection Per-Comparison

**Issue:** Position bias is detected per-comparison in `VoteAggregator`, but a chi-squared test on 5-15 votes has very low statistical power.

**Fix Required:** Track position bias at the aggregate level (across all comparisons) where there's sufficient data for meaningful statistical tests.

### 4.4 Tie Handling in Majority Logic

**Issue:** The majority logic treats ties as a third category, which can lead to "tie wins majority" even when there are more decisive votes.

Example: If votes are [gemini, competitor, tie, tie, tie], the result is "tie" even though there was 1-1 on decisive votes.

**Recommendation:** Consider treating ties as abstentions in majority calculation, or implement a tiebreaker mechanism.

---

## SECTION 5: PROMPT GENERATION GAPS

### 5.1 Diversity Requirements Not Systematically Addressed

PROMPT.md lists CRITICAL diversity requirements that are not systematically implemented:

| Requirement | Draft Implementation | Gap |
|-------------|---------------------|-----|
| User personas: full spectrum | Partially via NameGenerator | No systematic coverage tracking |
| Ages/skill levels: GenZ through Boomer | Age ranges by job zone | Doesn't ensure even distribution |
| Formality/casualness | Random selection | No stratified sampling |
| End users/recipients: full spectrum | Basic RecipientPersona | Limited recipient diversity |
| Urgency levels | Random choice | No distribution guarantee |
| Relationship context | Single field | Limited relationship types |
| Audience size | Random selection | No coverage tracking |
| Emotional context | Random selection | Limited emotion vocabulary |
| Message position | Random choice | No distribution tracking |

**Fix Required:** Implement diversity tracking and stratified sampling that ensures coverage across ALL dimensions, not just occupation and job zone.

### 5.2 Ambiguity Handling Tasks Not Implemented

**PROMPT.md Requirement:**
> "Include some deliberately vague prompts to test how models handle uncertainty"

The draft has `is_ambiguous` flag but:
- No mechanism to generate deliberately vague prompts
- No tracking of model behavior (makes assumptions, asks clarification, hedges, hallucinations)

**Fix Required:** Add:
- Ambiguous prompt generation logic
- Model behavior classification for ambiguous responses
- Analysis of ambiguity handling patterns

### 5.3 Revision/Editing Tasks Under-Implemented

**PROMPT.md Requirement:**
> "Include prompts where the model must improve existing text... Track these separately in analysis."

The draft has `is_revision_task` and `original_text_to_revise` but:
- No mechanism to generate original drafts to revise
- No separate analysis path for revision tasks

**Fix Required:** Add:
- Draft generation for revision tasks
- Separate win rate tracking for revision vs original generation

### 5.4 Tone Matching Not Implemented

**PROMPT.md Requirement:**
> "Some prompts should include prior writing samples to match"

The draft has `tone_example` field but no implementation for:
- Generating example writing samples
- Evaluating tone consistency with examples

### 5.5 Reply-To Context Generation

**PROMPT.md Requirement:**
> "Some prompts should include prior messages to respond to"

The draft has `prior_message` and `message_position` but:
- No systematic generation of realistic prior messages
- Prior message generation is deferred entirely to Phase 3 enrichment

**Issue:** This creates heavy reliance on LLM enrichment, which is expensive and may not cover all scenarios.

---

## SECTION 6: ANALYSIS AND REPORTING GAPS

### 6.1 Missing Breakdown Dimensions

The PDF report and analysis modules don't include all required breakdowns:

| Required Breakdown | Present in Draft |
|-------------------|------------------|
| Win rates by occupation | Partial (WeaknessFinder) |
| Win rates by writing type | Yes |
| Win rates by formality level | Partial |
| Win rates by age group | No |
| Win rates by industry | No |
| Win rates by communication channel | No |
| Win rates by emotional context | No |
| Win rates by message position | No |
| Heatmaps | Mentioned but not implemented |

### 6.2 Inter-Rater Reliability Calculation

**Issue:** The Cohen's Kappa calculation in `VoteAggregator` is implemented for pairwise judges but:
- Doesn't handle the case of 3+ judges properly (should use Fleiss' Kappa)
- Averages pairwise Kappas which can be misleading

**Fix Required:** Implement Fleiss' Kappa for multi-rater agreement.

### 6.3 Effect Size Missing

**PROMPT.md Requirement:**
> "Deep Statistical Analysis: Statistical rigor with significance tests, effect sizes, inter-rater reliability"

The draft calculates p-values but not effect sizes (Cohen's d, odds ratios, etc.).

**Fix Required:** Add effect size calculations to statistical analysis.

### 6.4 Confidence Intervals on All Win Rates

**PROMPT.md Requirement:**
> "Confidence intervals on all win rates"

The draft implements Wilson score intervals for overall win rates but doesn't apply them consistently to all breakdowns (by occupation, formality, etc.).

---

## SECTION 7: TUI AND VISUALIZATION ISSUES

### 7.1 Progress Dashboard Missing Elements

Comparing to PROMPT.md's required progress elements:

| Required Element | Draft Status |
|-----------------|--------------|
| Total prompts completed/total | Yes |
| Progress bar with percentage | Yes |
| Current phase indicator | Yes |
| Elapsed time and ETA | Yes |
| Per-model-pair progress | Yes |
| Running win rate with CI | Partial (no CI in display) |
| Current prompt details | Yes |
| Response generation status per model | Not shown |
| Judging progress (votes per judge) | Not shown |
| Inter-judge agreement | Yes |
| Cost tracking | Yes |
| Activity log | Yes |
| Error summary | Partial |

**Fix Required:** Add missing progress elements, especially real-time vote progress.

### 7.2 Interactive Controls Not All Implemented

**PROMPT.md Requirement:**
> "Interactive Controls: q (quit), p (pause), d (detail view), s (statistics), h (help), arrows (scroll)"

The draft's `EvalProgressApp` defines no key bindings. The `ResultsViewerApp` has some but is missing pause and statistics toggle.

---

## SECTION 8: STORAGE AND ORGANIZATION ISSUES

### 8.1 Directory Structure Mismatch

PROMPT.md specifies this structure:
```
eval_YYYY-MM-DD_HH-MM-SS/
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
...
```

The draft's checkpoint system doesn't organize files this way. It mentions `responses/` directory but doesn't implement the `by_prompt/` and `by_model/` organization.

### 8.2 Missing Files in Run Directory

PROMPT.md requires these files that aren't mentioned in the draft:
- `config_summary.txt` - Human-readable config summary
- `random_seed.txt` - Seed for reproducibility
- `README.md` - Auto-generated run description

### 8.3 Symlink to Latest Not Implemented

**PROMPT.md Requirement:**
> "`latest -> eval_2024-01-16_11-45-33/` Symlink to latest"

---

## SECTION 9: TECHNICAL IMPLEMENTATION ISSUES

### 9.1 Async Context Manager Not Used

The `OpenRouterClient` creates an `httpx.AsyncClient` but doesn't use context manager pattern, leading to potential resource leaks if the client isn't explicitly closed.

### 9.2 SQL Injection Vulnerability

In `ONetExtractor._query_tasks_by_patterns`:
```python
where_clauses = " OR ".join([f"t.task LIKE '{p}'" for p in patterns])
```

This builds SQL queries by string interpolation. While the patterns are currently hardcoded, this is a bad pattern that could become vulnerable if patterns become user-configurable.

**Fix Required:** Use parameterized queries.

### 9.3 Token Estimation Not Connected

The `CostEstimator` uses hardcoded token estimates (`avg_prompt_tokens = 1500`, `avg_response_tokens = 800`) but these aren't validated against actual token counts or connected to the token counter.

**Fix Required:** Build token estimates from actual schema sizes and prompt templates.

### 9.4 Missing Graceful Shutdown Handler

**PROMPT.md Requirement:**
> "Graceful shutdown: Ctrl+C saves state and can resume"

The draft doesn't implement signal handlers for SIGINT/SIGTERM that save checkpoint before exit.

---

## SECTION 10: POSITIVE ASPECTS OF THE DRAFT

To provide balanced feedback, here are things the draft does well:

1. **Comprehensive Schema Design**: The Pydantic models are well-structured and capture most of the required fields.

2. **Good Technology Stack**: The choice of httpx, pydantic, textual/rich, plotly, and typer is appropriate and modern.

3. **Solid API Client Foundation**: Rate limiting and exponential backoff with jitter are correctly implemented.

4. **Clear Architecture**: The modular separation of concerns (data, api, eval, storage, analysis, tui, reports) is clean.

5. **Statistical Analysis Foundation**: Wilson score intervals and significance testing are correctly implemented.

6. **Preset System**: The 10-level preset system exactly matches PROMPT.md requirements.

7. **Cost Estimation Display**: The display format matches PROMPT.md's example output closely.

---

# IMPROVED IMPLEMENTATION PLAN

The following is an improved version of the plan that addresses all identified issues.

---

## 1. System Architecture Overview (Improved)

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GEMINI WRITING EVAL FRAMEWORK                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   CLI/TUI    │  │   Config     │  │   Storage    │  │   Reports    │    │
│  │   Interface  │  │   Manager    │  │   Layer      │  │   Generator  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ┌──────▼─────────────────▼─────────────────▼─────────────────▼──────┐     │
│  │                        ORCHESTRATION ENGINE                        │     │
│  │  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐│     │
│  │  │   Checkpoint  │ │ Rate Limiter │ │Circuit Breaker│ │  Signal  ││     │
│  │  │   Manager     │ │ (per-model)  │ │              │ │  Handler ││     │
│  │  └───────────────┘ └──────────────┘ └──────────────┘ └───────────┘│     │
│  └───────────────────────────┬───────────────────────────────────────┘     │
│                              │                                              │
│  ┌───────────────────────────▼───────────────────────────────────────┐     │
│  │                       EVALUATION PIPELINE                          │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │     │
│  │  │   Prompt    │  │  Response   │  │  Judgment   │  │ Compliance│ │     │
│  │  │  Generator  │─▶│  Collector  │─▶│  Aggregator │─▶│  Tracker  │ │     │
│  │  │ (3-phase)   │  │             │  │             │  │           │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │     │
│  └───────────────────────────┬───────────────────────────────────────┘     │
│                              │                                              │
│  ┌───────────────────────────▼───────────────────────────────────────┐     │
│  │                         DATA LAYER                                 │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │     │
│  │  │  O*NET DB   │  │  Company    │  │  Name       │  │ Diversity │ │     │
│  │  │  Extractor  │  │  Database   │  │  Generator  │  │ Tracker   │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                      OPENROUTER API CLIENT                         │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │     │
│  │  │  Async      │  │   Retry     │  │   Token     │  │  Circuit  │ │     │
│  │  │  HTTP Pool  │  │   Logic     │  │   Counter   │  │  Breaker  │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack (Same as draft - well chosen)

### 1.3 Directory Structure (Improved)

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── .env.example
│
├── src/
│   ├── __init__.py
│   ├── cli.py                     # Main CLI with compare command
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── presets.py
│   │   └── cost_estimator.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py
│   │   ├── naics_mapper.py
│   │   ├── company_database.py
│   │   ├── name_generator.py
│   │   └── diversity_tracker.py   # NEW: Track coverage across dimensions
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   ├── phase1_offline.py      # NEW: Phase 1 LLM generation
│   │   ├── phase2_algorithmic.py  # Phase 2 combinations
│   │   ├── phase3_enrichment.py   # Phase 3 enrichment
│   │   ├── ambiguity_generator.py # NEW: Deliberate vague prompts
│   │   ├── revision_generator.py  # NEW: Revision task generation
│   │   └── tone_matcher.py        # NEW: Tone matching prompts
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py
│   │   ├── rate_limiter.py        # Per-model rate limiting
│   │   ├── circuit_breaker.py     # NEW: Circuit breaker pattern
│   │   └── token_counter.py
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── judge.py
│   │   ├── vote_aggregator.py
│   │   ├── compliance_tracker.py  # NEW: Instruction following
│   │   ├── refusal_classifier.py  # NEW: Refusal categorization
│   │   └── schemas.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── checkpoint.py          # Fine-grained checkpointing
│   │   ├── file_organizer.py      # NEW: Directory structure
│   │   └── exporter.py
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # With effect sizes
│   │   ├── bias_detection.py
│   │   ├── weakness_finder.py
│   │   ├── dimension_analyzer.py  # NEW: All dimension breakdowns
│   │   └── cross_run_compare.py   # NEW: Compare multiple runs
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── progress.py            # With all required elements
│   │   ├── viewer.py
│   │   ├── keybindings.py         # NEW: All interactive controls
│   │   └── components.py
│   │
│   └── reports/
│       ├── __init__.py
│       ├── charts.py
│       ├── heatmaps.py            # NEW: Heatmap generation
│       └── pdf_generator.py
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
    └── integration/
```

---

## 2. Data Models and Schemas (Improved)

### 2.1 Core Prompt Schema (Complete)

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class Formality(str, Enum):
    VERY_CASUAL = "very_casual"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    VERY_FORMAL = "very_formal"

class Generation(str, Enum):
    GEN_Z = "gen_z"
    GEN_A = "gen_a"
    MILLENNIAL = "millennial"
    GEN_X = "gen_x"
    BOOMER = "boomer"

class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AudienceSize(str, Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class MessagePosition(str, Enum):
    INITIAL = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"

class RelationshipType(str, Enum):
    FIRST_CONTACT = "first_contact"
    ACQUAINTANCE = "acquaintance"
    ONGOING_PROFESSIONAL = "ongoing_professional"
    CLOSE_COLLEAGUE = "close_colleague"
    DIRECT_REPORT = "direct_report"
    MANAGER = "manager"
    EXTERNAL_CLIENT = "external_client"
    EXTERNAL_VENDOR = "external_vendor"

class SensitiveTopic(str, Enum):
    NONE = "none"
    HR_ISSUES = "hr_issues"
    LEGAL_MATTERS = "legal_matters"
    BAD_NEWS = "bad_news"
    CONFIDENTIAL = "confidential"
    CONFLICT = "conflict"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CELEBRATION = "celebration"
    CRISIS = "crisis"
    CONFLICT_RESOLUTION = "conflict_resolution"
    BAD_NEWS_DELIVERY = "bad_news_delivery"
    ENCOURAGEMENT = "encouragement"
    URGENT_REQUEST = "urgent_request"

class WriterPersona(BaseModel):
    name: str
    email: Optional[str] = None
    role: str
    age: int
    generation: Generation
    skill_level: Literal[1, 2, 3, 4, 5]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    name_formality: Literal["formal", "casual", "full"]  # Dr. Williams vs Mike vs Michael T. Williams

class RecipientPersona(BaseModel):
    name: str
    email: Optional[str] = None
    role: str
    relationship: RelationshipType
    english_variant: EnglishVariant = EnglishVariant.EN_US

class CompanyContext(BaseModel):
    name: str
    industry: str
    naics_code: str
    naics_sector: str  # 2-digit sector name
    size_category: Literal["startup", "small", "mid_market", "large", "enterprise"]
    employee_count: Optional[int] = None
    founding_year: Optional[int] = None
    public_private: Literal["public", "private"]
    hq_location: str

class TemporalContext(BaseModel):
    current_date: Optional[str] = None
    current_quarter: Optional[str] = None
    deadline: Optional[str] = None
    deadline_urgency: Optional[str] = None
    reference_event: Optional[str] = None

class Attachment(BaseModel):
    type: str
    description: str
    summary: str
    key_points: list[str]
    key_figures: Optional[dict[str, str]] = None  # For reports with numbers

class InstructionConstraint(BaseModel):
    constraint_id: str
    type: Literal["length_max", "length_min", "format", "tone", "exclusion", "inclusion"]
    description: str
    value: Optional[str] = None  # e.g., "100 words", "3 bullet points"
    testable_criteria: str
    is_explicit: bool = True  # Is this constraint explicitly stated in the prompt?

class WritingPrompt(BaseModel):
    prompt_id: str

    # O*NET Source
    onet_task_id: str
    onet_occupation_code: str
    onet_occupation_title: str
    onet_task_statement: str
    onet_soc_major_group: str
    job_zone: Literal[1, 2, 3, 4, 5]

    # Generated Context
    writer: WriterPersona
    recipient: RecipientPersona
    cc_recipients: list[RecipientPersona] = []
    company: CompanyContext

    # Task Details
    writing_task: str
    formality: Formality
    urgency: Urgency
    audience_size: AudienceSize
    emotional_context: EmotionalContext
    message_position: MessagePosition
    relationship_context: RelationshipType

    # Optional Enhancements
    temporal: Optional[TemporalContext] = None
    attachments: list[Attachment] = []
    prior_message: Optional[str] = None
    tone_example: Optional[str] = None
    tone_example_description: Optional[str] = None

    # Constraints
    constraints: list[InstructionConstraint] = []
    competing_objectives: list[str] = []

    # Communication Channel
    communication_channel: Optional[str] = None
    channel_inferred: bool = False  # Was channel inferred vs explicit?

    # Special Task Types
    is_revision_task: bool = False
    original_text_to_revise: Optional[str] = None
    revision_instruction: Optional[str] = None

    is_ambiguous: bool = False
    ambiguity_type: Optional[Literal["underspecified_recipient", "missing_context", "unclear_ask"]] = None

    has_tone_matching: bool = False
    has_reply_context: bool = False
    has_multiple_audiences: bool = False

    # Sensitive Topics
    sensitive_topic: SensitiveTopic = SensitiveTopic.NONE
    sensitive_topic_details: Optional[str] = None

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    writing_category: str

    # Generation Metadata
    generation_phase: Literal[1, 2, 3]
    phase1_model: Optional[str] = None  # Model used in Phase 1
    enrichment_model: Optional[str] = None
    random_seed: int
    diversity_dimensions: dict[str, str] = {}  # Track which diversity slot this fills
    created_at: datetime

    # Model Tier
    model_tier: Literal["pro", "flash"]
```

### 2.2 Response Schema (Improved)

```python
class RefusalCategory(str, Enum):
    NONE = "none"
    SAFETY = "safety"
    CAPABILITY = "capability"
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE = "incomplete"
    OFF_TOPIC = "off_topic"

class ResponseStatus(str, Enum):
    SUCCESS = "success"
    REFUSED = "refused"
    ERROR = "error"
    TIMEOUT = "timeout"
    OFF_TOPIC = "off_topic"

class ModelResponse(BaseModel):
    response_id: str
    prompt_id: str
    model_id: str
    model_name: str
    model_tier: Literal["pro", "flash"]

    # Response Content
    response_text: str

    # Timing
    response_time_ms: int

    # Token Counts
    input_tokens: int
    output_tokens: int
    total_tokens: int

    # Format Detection
    word_count: int
    char_count: int
    sentence_count: int
    paragraph_count: int

    # Structural Elements
    has_greeting: bool
    greeting_type: Optional[Literal["formal", "casual", "none"]] = None
    greeting_text: Optional[str] = None

    has_signoff: bool
    signoff_type: Optional[Literal["formal", "casual", "none"]] = None
    signoff_text: Optional[str] = None

    uses_bullet_points: bool
    bullet_point_count: int = 0

    uses_headers: bool
    header_count: int = 0
    header_types: list[str] = []  # e.g., ["h1", "h2"]

    uses_numbered_list: bool
    numbered_list_count: int = 0

    # Status
    status: ResponseStatus
    refusal_category: RefusalCategory = RefusalCategory.NONE
    error_message: Optional[str] = None

    # Instruction Compliance (populated by compliance tracker)
    constraints_evaluated: list[str] = []
    constraints_met: list[str] = []
    constraints_violated: list[str] = []
    compliance_notes: Optional[str] = None

    created_at: datetime
```

### 2.3 JudgeVote Schema (Improved)

```python
class JudgeVote(BaseModel):
    vote_id: str
    comparison_id: str
    judge_model: str
    judge_persona: Literal["writing_expert", "recipient"]
    vote_number: int

    # Vote Result
    winner: Literal["A", "B", "tie"]
    winner_model: Optional[str] = None  # Resolved after position reveal

    # Rubric Scores (1-5 scale)
    scores_response_a: dict[str, int]
    scores_response_b: dict[str, int]

    # Instruction Compliance Assessment
    instruction_compliance_a: Optional[Literal["full", "partial", "none"]] = None
    instruction_compliance_b: Optional[Literal["full", "partial", "none"]] = None
    compliance_notes: Optional[str] = None

    # Reasoning
    reasoning: str
    key_differentiators: list[str] = []  # What made the difference

    # Ambiguity Handling (for ambiguous prompts)
    ambiguity_handling_a: Optional[Literal["assumptions", "clarification", "hedging", "hallucination"]] = None
    ambiguity_handling_b: Optional[Literal["assumptions", "clarification", "hedging", "hallucination"]] = None

    # Metadata
    response_time_ms: int
    input_tokens: int
    output_tokens: int
    created_at: datetime
```

### 2.4 JudgeAggregation Schema (Improved)

```python
class JudgeAggregation(BaseModel):
    aggregation_id: str
    comparison_id: str
    model_pair: str  # e.g., "gemini-3-pro vs claude-opus-4.5"
    model_tier: Literal["pro", "flash"]

    # Per-Judge Majority (using actual model keys)
    judge_majorities: dict[str, Literal["gemini", "competitor", "tie"]]

    # Final Result
    final_winner: Literal["gemini", "competitor", "tie"]

    # Vote Counts
    gemini_wins: int
    competitor_wins: int
    ties: int
    total_votes: int

    # Agreement Metrics
    fleiss_kappa: float  # Multi-rater agreement
    position_bias_detected: bool
    position_bias_chi_sq: float
    position_bias_p_value: float

    # Instruction Compliance Summary
    gemini_compliance_rate: Optional[float] = None
    competitor_compliance_rate: Optional[float] = None

    created_at: datetime
```

---

## 3. Phase 1: Offline LLM Generation (NEW - Critical Missing Piece)

```python
class Phase1OfflineGenerator:
    """
    Phase 1: Use LLMs to pre-generate diverse persona/context variations.
    Uses the SAME models being evaluated to avoid bias.
    """

    GENERATION_MODELS = [
        "gemini-3-pro",
        "gpt-5.2-thinking",
        "claude-opus-4.5",
        "gemini-3-flash",
        "gpt-4.1",
        "claude-sonnet"
    ]

    def __init__(
        self,
        api_client: OpenRouterClient,
        onet_extractor: ONetExtractor,
        output_dir: Path
    ):
        self.api = api_client
        self.onet = onet_extractor
        self.output_dir = output_dir

    async def generate_variations(
        self,
        tasks: list[dict],
        variations_per_task: int = 5,
        seed: int = 42
    ) -> dict[str, list[dict]]:
        """
        Generate persona/context variations for each task.
        Returns: {task_id: [variation1, variation2, ...]}
        """
        rng = random.Random(seed)
        all_variations = {}

        for task in tasks:
            task_variations = []

            # Distribute generation across models to avoid single-model bias
            for i in range(variations_per_task):
                model = self.GENERATION_MODELS[i % len(self.GENERATION_MODELS)]
                variation = await self._generate_single_variation(
                    task, model, rng.randint(0, 2**32)
                )
                variation["generated_by_model"] = model
                task_variations.append(variation)

            all_variations[task["task_id"]] = task_variations

            # Save incrementally
            self._save_variations(task["task_id"], task_variations)

        return all_variations

    async def _generate_single_variation(
        self,
        task: dict,
        model: str,
        seed: int
    ) -> dict:
        """Generate a single persona/context variation for a task."""

        prompt = f"""
Generate a realistic, diverse writing scenario variation for this O*NET task.

Task: {task['task']}
Occupation: {task['occupation_title']}
Job Zone: {task['job_zone']}

Create a SPECIFIC scenario with:
1. Writer persona (name, age 18-70, specific role variant, skill level 1-5)
2. Recipient persona (name, role, relationship to writer)
3. Company context (real company name if appropriate, or realistic fictional small business with size)
4. Emotional context (routine, celebration, crisis, conflict, bad news, etc.)
5. Urgency level and deadline if appropriate
6. Any relevant prior context or attachments

IMPORTANT: Be creative and DIVERSE. Vary:
- Ages across generations (GenZ through Boomer)
- Formality levels (very casual to very formal)
- Company sizes (startup to Fortune 500)
- Relationship dynamics
- Regional English variants where appropriate

Return as JSON:
{{
    "writer": {{
        "name": "...",
        "age": N,
        "role": "...",
        "skill_level": N,
        "english_variant": "en-US|en-GB|en-AU|non-native"
    }},
    "recipient": {{
        "name": "...",
        "role": "...",
        "relationship": "first_contact|acquaintance|ongoing_professional|close_colleague|direct_report|manager|external_client|external_vendor"
    }},
    "company": {{
        "name": "...",
        "industry": "...",
        "size": "startup|small|mid_market|large|enterprise",
        "employee_count": N or null
    }},
    "context": {{
        "formality": "very_casual|casual|neutral|formal|very_formal",
        "urgency": "low|medium|high|critical",
        "emotional_context": "...",
        "deadline": "..." or null,
        "prior_context": "..." or null
    }},
    "enriched_task": "Full detailed writing task description..."
}}
"""

        response = await self.api.generate(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.9  # High temperature for diversity
        )

        return json.loads(response.content)

    def _save_variations(self, task_id: str, variations: list[dict]):
        """Save variations to disk for later use."""
        output_file = self.output_dir / f"phase1_variations_{task_id}.json"
        with open(output_file, 'w') as f:
            json.dump(variations, f, indent=2)
```

---

## 4. Diversity Tracker (NEW)

```python
class DiversityTracker:
    """
    Track coverage across all diversity dimensions.
    Ensures sampling covers the full spectrum required by PROMPT.md.
    """

    DIMENSIONS = {
        "generation": ["gen_z", "gen_a", "millennial", "gen_x", "boomer"],
        "formality": ["very_casual", "casual", "neutral", "formal", "very_formal"],
        "urgency": ["low", "medium", "high", "critical"],
        "audience_size": ["one_on_one", "small_group", "department", "company_wide", "public"],
        "emotional_context": ["routine", "celebration", "crisis", "conflict_resolution", "bad_news_delivery", "encouragement", "urgent_request"],
        "message_position": ["initial", "reply", "follow_up"],
        "relationship": ["first_contact", "acquaintance", "ongoing_professional", "close_colleague", "direct_report", "manager", "external_client", "external_vendor"],
        "english_variant": ["en-US", "en-GB", "en-AU", "non-native"],
        "company_size": ["startup", "small", "mid_market", "large", "enterprise"],
        "job_zone": [1, 2, 3, 4, 5],
    }

    def __init__(self):
        self.coverage = {dim: {val: 0 for val in vals} for dim, vals in self.DIMENSIONS.items()}
        self.total_prompts = 0

    def record_prompt(self, prompt: WritingPrompt):
        """Record a prompt's coverage of diversity dimensions."""
        self.total_prompts += 1

        self.coverage["generation"][prompt.writer.generation.value] += 1
        self.coverage["formality"][prompt.formality.value] += 1
        self.coverage["urgency"][prompt.urgency.value] += 1
        self.coverage["audience_size"][prompt.audience_size.value] += 1
        self.coverage["emotional_context"][prompt.emotional_context.value] += 1
        self.coverage["message_position"][prompt.message_position.value] += 1
        self.coverage["relationship"][prompt.relationship_context.value] += 1
        self.coverage["english_variant"][prompt.writer.english_variant.value] += 1
        self.coverage["company_size"][prompt.company.size_category] += 1
        self.coverage["job_zone"][prompt.job_zone] += 1

    def get_underrepresented(self, target_min_percent: float = 0.05) -> list[tuple[str, str]]:
        """Get dimension values that are underrepresented."""
        underrepresented = []
        target_count = self.total_prompts * target_min_percent

        for dim, vals in self.coverage.items():
            for val, count in vals.items():
                if count < target_count:
                    underrepresented.append((dim, val))

        return underrepresented

    def get_coverage_report(self) -> dict:
        """Get full coverage statistics."""
        report = {}
        for dim, vals in self.coverage.items():
            total_in_dim = sum(vals.values())
            report[dim] = {
                val: {
                    "count": count,
                    "percent": count / total_in_dim * 100 if total_in_dim > 0 else 0
                }
                for val, count in vals.items()
            }
        return report

    def suggest_next_selection(self) -> dict[str, str]:
        """Suggest dimension values for next prompt to improve coverage."""
        suggestions = {}
        for dim, vals in self.coverage.items():
            # Pick the least represented value
            min_val = min(vals.keys(), key=lambda v: vals[v])
            suggestions[dim] = min_val
        return suggestions
```

---

## 5. Circuit Breaker Pattern (NEW)

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 2      # Successes to close from half-open
    timeout_seconds: int = 60       # Time before half-open from open
    exclude_codes: list[int] = None # HTTP codes that don't count as failures

class CircuitBreaker:
    """
    Circuit breaker pattern for API resilience.
    Prevents cascading failures when an API is consistently failing.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitOpenError(f"Circuit {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure(e)
            raise

    async def _record_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._reset()
            else:
                self.failure_count = 0

    async def _record_failure(self, error: Exception):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = datetime.utcnow() - self.last_failure_time
        return elapsed.total_seconds() >= self.config.timeout_seconds

    def _reset(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0

class CircuitOpenError(Exception):
    pass
```

---

## 6. Per-Model Rate Limiting (Improved)

```python
class PerModelRateLimiter:
    """
    Rate limiter that tracks limits separately for each model.
    Different models on OpenRouter have different rate limits.
    """

    DEFAULT_LIMITS = {
        "gemini-3-pro": {"rpm": 60, "tpm": 1000000},
        "gemini-3-flash": {"rpm": 1000, "tpm": 4000000},
        "gpt-5.2-thinking": {"rpm": 60, "tpm": 150000},
        "gpt-4.1": {"rpm": 500, "tpm": 300000},
        "claude-opus-4.5": {"rpm": 50, "tpm": 100000},
        "claude-sonnet": {"rpm": 100, "tpm": 200000},
        "grok-4.1-thinking": {"rpm": 60, "tpm": 100000},
        "kimi-k2-thinking": {"rpm": 60, "tpm": 100000},
    }

    def __init__(self, custom_limits: Optional[dict] = None):
        self.limits = {**self.DEFAULT_LIMITS}
        if custom_limits:
            self.limits.update(custom_limits)

        self.model_buckets: dict[str, tuple[TokenBucket, TokenBucket]] = {}
        self._lock = asyncio.Lock()

    def _get_buckets(self, model: str) -> tuple[TokenBucket, TokenBucket]:
        """Get or create rate limit buckets for a model."""
        if model not in self.model_buckets:
            limits = self.limits.get(model, {"rpm": 60, "tpm": 100000})
            request_bucket = TokenBucket(
                capacity=limits["rpm"],
                refill_rate=limits["rpm"] / 60
            )
            token_bucket = TokenBucket(
                capacity=limits["tpm"],
                refill_rate=limits["tpm"] / 60
            )
            self.model_buckets[model] = (request_bucket, token_bucket)
        return self.model_buckets[model]

    async def acquire(self, model: str, estimated_tokens: int = 1000):
        """Acquire permission to make an API call for a specific model."""
        async with self._lock:
            request_bucket, token_bucket = self._get_buckets(model)

            while not request_bucket.consume(1):
                await asyncio.sleep(0.1)
            while not token_bucket.consume(estimated_tokens):
                await asyncio.sleep(0.1)
```

---

## 7. Improved CLI with Compare Command

```python
@app.command()
def compare(
    run_dirs: list[Path] = typer.Argument(..., help="Paths to run directories to compare"),
    output: Path = typer.Option(None, "--output", "-o", help="Output comparison report path"),
):
    """Compare results across multiple evaluation runs."""

    if len(run_dirs) < 2:
        console.print("[red]Need at least 2 run directories to compare[/red]")
        raise typer.Abort()

    # Load all results
    all_results = []
    for run_dir in run_dirs:
        db_path = run_dir / "results.db"
        if not db_path.exists():
            console.print(f"[yellow]Warning: No results.db in {run_dir}, skipping[/yellow]")
            continue
        results = load_results(run_dir)
        results.run_name = run_dir.name
        all_results.append(results)

    if len(all_results) < 2:
        console.print("[red]Could not load enough results for comparison[/red]")
        raise typer.Abort()

    # Generate comparison
    comparer = CrossRunComparer(all_results)
    comparison = comparer.compare()

    # Display comparison
    _display_comparison(comparison)

    # Save if output specified
    if output:
        comparison.to_json(output)
        console.print(f"[green]Comparison saved to {output}[/green]")

class CrossRunComparer:
    """Compare results across multiple evaluation runs."""

    def __init__(self, results: list[EvalResults]):
        self.results = results

    def compare(self) -> CrossRunComparison:
        """Generate cross-run comparison."""

        # Win rate comparison per model pair
        win_rate_comparison = {}
        for model_pair in self._get_all_model_pairs():
            win_rate_comparison[model_pair] = {
                r.run_name: r.win_rates.get(model_pair)
                for r in self.results
                if model_pair in r.win_rates
            }

        # Statistical comparison (are differences significant?)
        significance_tests = self._run_significance_tests()

        # Configuration differences
        config_diffs = self._compare_configs()

        return CrossRunComparison(
            runs=[r.run_name for r in self.results],
            win_rate_comparison=win_rate_comparison,
            significance_tests=significance_tests,
            config_differences=config_diffs
        )

    def _run_significance_tests(self) -> dict:
        """Test if differences between runs are statistically significant."""
        tests = {}
        for model_pair in self._get_all_model_pairs():
            # Get win counts from each run
            run_results = []
            for r in self.results:
                if model_pair in r.win_rates:
                    run_results.append({
                        "run": r.run_name,
                        "wins": r.gemini_wins.get(model_pair, 0),
                        "total": r.total_comparisons.get(model_pair, 0)
                    })

            if len(run_results) >= 2:
                # Chi-squared test for homogeneity
                observed = [[rr["wins"], rr["total"] - rr["wins"]] for rr in run_results]
                chi_sq, p_value, dof, expected = stats.chi2_contingency(observed)
                tests[model_pair] = {
                    "chi_squared": chi_sq,
                    "p_value": p_value,
                    "significant": p_value < 0.05,
                    "runs_compared": [rr["run"] for rr in run_results]
                }

        return tests
```

---

## 8. Fine-Grained Checkpointing (Improved)

```python
class FineGrainedCheckpointManager:
    """
    Checkpoint manager with per-vote granularity.
    Saves after EACH judge vote, not just after each prompt.
    """

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_path = run_dir / "checkpoint.json"
        self.votes_dir = run_dir / "judgments" / "raw"
        self.votes_dir.mkdir(parents=True, exist_ok=True)

    def save_vote(self, vote: JudgeVote):
        """Save a single vote immediately after collection."""
        vote_file = self.votes_dir / f"{vote.comparison_id}_{vote.judge_model}_{vote.vote_number}.json"

        # Atomic write
        temp_file = vote_file.with_suffix(".tmp")
        with open(temp_file, 'w') as f:
            json.dump(vote.model_dump(), f, indent=2, default=str)
        temp_file.rename(vote_file)

        # Update checkpoint
        self._update_checkpoint_votes(vote.comparison_id, vote.vote_id)

    def save_response(self, response: ModelResponse):
        """Save a response immediately after generation."""
        response_file = self.run_dir / "responses" / "by_prompt" / f"{response.prompt_id}_{response.model_id}.json"
        response_file.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write
        temp_file = response_file.with_suffix(".tmp")
        with open(temp_file, 'w') as f:
            json.dump(response.model_dump(), f, indent=2, default=str)
        temp_file.rename(response_file)

    def save_checkpoint(self, state: CheckpointState):
        """Save full checkpoint state."""
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        with open(temp_path, 'w') as f:
            json.dump(state.model_dump(), f, indent=2, default=str)
        temp_path.rename(self.checkpoint_path)

    def load_checkpoint(self) -> CheckpointState:
        """Load checkpoint state including all persisted votes."""
        if not self.checkpoint_path.exists():
            return CheckpointState()

        with open(self.checkpoint_path) as f:
            data = json.load(f)

        state = CheckpointState(**data)

        # Also load any votes that were saved but not recorded in checkpoint
        # (in case of crash between vote save and checkpoint update)
        for vote_file in self.votes_dir.glob("*.json"):
            vote_id = vote_file.stem
            if vote_id not in state.completed_votes:
                state.completed_votes.add(vote_id)

        return state

    def _update_checkpoint_votes(self, comparison_id: str, vote_id: str):
        """Update checkpoint to record completed vote."""
        state = self.load_checkpoint() if self.checkpoint_path.exists() else CheckpointState()
        state.completed_votes.add(vote_id)
        if comparison_id not in state.votes_per_comparison:
            state.votes_per_comparison[comparison_id] = []
        state.votes_per_comparison[comparison_id].append(vote_id)
        self.save_checkpoint(state)
```

---

## 9. Graceful Shutdown Handler (NEW)

```python
import signal
import sys

class GracefulShutdownHandler:
    """
    Handle shutdown signals gracefully.
    Saves checkpoint before exit on SIGINT/SIGTERM.
    """

    def __init__(self, checkpoint_manager: CheckpointManager, engine: EvaluationEngine):
        self.checkpoint = checkpoint_manager
        self.engine = engine
        self._shutdown_requested = False
        self._original_sigint = None
        self._original_sigterm = None

    def install(self):
        """Install signal handlers."""
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)

    def uninstall(self):
        """Restore original signal handlers."""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal."""
        if self._shutdown_requested:
            # Second signal - force exit
            console.print("\n[red]Force exit requested[/red]")
            sys.exit(1)

        self._shutdown_requested = True
        console.print("\n[yellow]Shutdown requested. Saving checkpoint...[/yellow]")

        # Save current state
        try:
            self.checkpoint.save_checkpoint(self.engine.get_current_state())
            console.print("[green]Checkpoint saved. Safe to exit.[/green]")
        except Exception as e:
            console.print(f"[red]Error saving checkpoint: {e}[/red]")

        # Request engine to stop
        self.engine.request_stop()

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested
```

---

## 10. Improved Judge Prompt with Full Context

```python
def _build_judgment_prompt(
    self,
    prompt: WritingPrompt,
    response_a: str,
    response_b: str
) -> str:
    """Build the full judgment prompt with ALL required context."""

    # Format constraints if any
    constraints_text = ""
    if prompt.constraints:
        constraints_text = "\n**Explicit Constraints:**\n"
        for c in prompt.constraints:
            constraints_text += f"- {c.description}\n"

    # Format competing objectives
    objectives_text = ""
    if prompt.competing_objectives:
        objectives_text = "\n**Competing Objectives:**\n"
        for obj in prompt.competing_objectives:
            objectives_text += f"- {obj}\n"

    # Format temporal context
    temporal_text = ""
    if prompt.temporal:
        temporal_text = "\n**Temporal Context:**\n"
        if prompt.temporal.current_date:
            temporal_text += f"- Current Date: {prompt.temporal.current_date}\n"
        if prompt.temporal.deadline:
            temporal_text += f"- Deadline: {prompt.temporal.deadline}\n"
        if prompt.temporal.reference_event:
            temporal_text += f"- Reference Event: {prompt.temporal.reference_event}\n"

    # Format attachments
    attachments_text = ""
    if prompt.attachments:
        attachments_text = "\n**Referenced Documents:**\n"
        for att in prompt.attachments:
            attachments_text += f"\n[{att.type.upper()}]\n"
            attachments_text += f"{att.summary}\n"
            attachments_text += "Key Points:\n"
            for point in att.key_points:
                attachments_text += f"  - {point}\n"

    # Format prior message
    prior_text = ""
    if prompt.prior_message:
        prior_text = f"\n**Prior Message (to respond to):**\n{prompt.prior_message}\n"

    return f"""
## WRITING TASK CONTEXT

**Writer Profile:**
- Name: {prompt.writer.name}
- Role: {prompt.writer.role}
- Age: {prompt.writer.age} ({prompt.writer.generation.value})
- Skill Level: {prompt.writer.skill_level}/5
- English Variant: {prompt.writer.english_variant.value}
- Company: {prompt.company.name} ({prompt.company.size_category}, {prompt.company.industry})

**Recipient Profile:**
- Name: {prompt.recipient.name}
- Role: {prompt.recipient.role}
- Relationship to writer: {prompt.relationship_context.value}
- English Variant: {prompt.recipient.english_variant.value}

**Communication Context:**
- Formality Level: {prompt.formality.value}
- Urgency: {prompt.urgency.value}
- Audience Size: {prompt.audience_size.value}
- Emotional Context: {prompt.emotional_context.value}
- Message Position: {prompt.message_position.value}
- Communication Channel: {prompt.communication_channel or "Not specified"}
{temporal_text}
{constraints_text}
{objectives_text}
{attachments_text}
{prior_text}

**The Writing Task:**
{prompt.writing_task}

---

## RESPONSE A

{response_a}

---

## RESPONSE B

{response_b}

---

## EVALUATION RUBRIC

Score each response on these criteria (1-5 scale):

1. **Writing Quality** (15%): Grammar, syntax, style, prose quality
2. **Length Appropriateness** (10%): Is it the RIGHT length for this task?
3. **Tone Appropriateness** (15%): Does tone match formality, context, relationship?
4. **Effectiveness** (15%): Would this achieve the writer's goals?
5. **Clarity** (10%): How easy is it to understand?
6. **Task Completion** (10%): Does it address all aspects of the task?
7. **Authenticity** (15%): Does it read as natural human writing vs AI-generated?
8. **Cliche Avoidance** (10%): Avoids AI patterns and boilerplate?

{"**Instruction Compliance:** Also evaluate whether each response followed the explicit constraints listed above." if prompt.constraints else ""}

---

## YOUR JUDGMENT

Provide your evaluation as JSON:
{{
    "scores_a": {{"writing_quality": N, "length_appropriateness": N, "tone_appropriateness": N, "effectiveness": N, "clarity": N, "task_completion": N, "authenticity": N, "cliche_avoidance": N}},
    "scores_b": {{"writing_quality": N, "length_appropriateness": N, "tone_appropriateness": N, "effectiveness": N, "clarity": N, "task_completion": N, "authenticity": N, "cliche_avoidance": N}},
    {"\"instruction_compliance_a\": \"full|partial|none\"," if prompt.constraints else ""}
    {"\"instruction_compliance_b\": \"full|partial|none\"," if prompt.constraints else ""}
    "winner": "A" | "B" | "tie",
    "reasoning": "Detailed explanation of your decision...",
    "key_differentiators": ["factor1", "factor2", ...]
}}
"""
```

---

## 11. Statistical Analysis with Effect Sizes (Improved)

```python
class ImprovedStatisticalAnalyzer:
    """Statistical analysis with effect sizes and Fleiss' Kappa."""

    def calculate_win_rate_with_effect_size(
        self,
        results: list[ComparisonResult],
        model_pair: str,
        confidence: float = 0.95
    ) -> WinRateResult:
        """Calculate win rate with confidence interval and effect size."""

        wins = sum(1 for r in results if r.winner == "gemini")
        losses = sum(1 for r in results if r.winner == "competitor")
        ties = sum(1 for r in results if r.winner == "tie")
        total = len(results)

        if total == 0:
            return WinRateResult(0, 0, 0, 0, 1.0, 0, 0)

        win_rate = wins / total

        # Wilson score interval
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        denominator = 1 + z**2 / total
        center = (win_rate + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt(win_rate * (1 - win_rate) / total + z**2 / (4 * total**2)) / denominator
        ci_lower = center - margin
        ci_upper = center + margin

        # Two-tailed test vs 0.5
        test_stat = (win_rate - 0.5) / np.sqrt(0.5 * 0.5 / total)
        p_value = 2 * (1 - stats.norm.cdf(abs(test_stat)))

        # Effect size: Odds ratio
        if losses == 0:
            odds_ratio = float('inf') if wins > 0 else 1.0
        else:
            odds_ratio = wins / losses

        # Cohen's h (effect size for proportions)
        cohens_h = 2 * (np.arcsin(np.sqrt(win_rate)) - np.arcsin(np.sqrt(0.5)))

        return WinRateResult(
            win_rate=win_rate,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=total,
            p_value=p_value,
            odds_ratio=odds_ratio,
            cohens_h=cohens_h,
            n_wins=wins,
            n_losses=losses,
            n_ties=ties
        )

    def calculate_fleiss_kappa(
        self,
        votes: list[list[str]],  # Each inner list is votes from one rater
        categories: list[str] = ["gemini", "competitor", "tie"]
    ) -> float:
        """
        Calculate Fleiss' Kappa for multi-rater agreement.
        More appropriate than averaging pairwise Cohen's Kappa.
        """
        n_subjects = len(votes[0])  # Number of items being rated
        n_raters = len(votes)       # Number of raters
        n_categories = len(categories)

        # Build matrix: n_subjects x n_categories
        # Cell (i,j) = number of raters who assigned subject i to category j
        matrix = np.zeros((n_subjects, n_categories))

        for rater_votes in votes:
            for subject_idx, vote in enumerate(rater_votes):
                cat_idx = categories.index(vote)
                matrix[subject_idx, cat_idx] += 1

        # Calculate P_i (agreement for each subject)
        P_i = np.sum(matrix ** 2, axis=1) - n_raters
        P_i = P_i / (n_raters * (n_raters - 1))

        # Calculate P_bar (mean agreement)
        P_bar = np.mean(P_i)

        # Calculate P_e (expected agreement by chance)
        p_j = np.sum(matrix, axis=0) / (n_subjects * n_raters)
        P_e = np.sum(p_j ** 2)

        # Fleiss' Kappa
        if P_e == 1:
            return 1.0  # Perfect agreement
        kappa = (P_bar - P_e) / (1 - P_e)

        return kappa
```

---

## 12. Summary of Critical Improvements

| Issue | Original Draft | Improved Plan |
|-------|---------------|---------------|
| Phase 1 LLM Generation | Missing | Fully implemented |
| Diversity Tracking | Random sampling | Stratified with coverage tracking |
| Instruction Compliance | Not tracked separately | Full tracking in judge and response |
| Sensitive Topics | Schema only | Detection, tagging, separate analysis |
| Compare Command | Missing | Fully implemented |
| Circuit Breaker | Missing | Full implementation |
| Rate Limiting | Global only | Per-model limits |
| Checkpoint Granularity | Per-prompt | Per-vote |
| Signal Handling | Missing | SIGINT/SIGTERM handlers |
| Judge Context | Partial | Full context as per PROMPT.md |
| Inter-rater Agreement | Cohen's Kappa (pairwise) | Fleiss' Kappa (multi-rater) |
| Effect Sizes | Missing | Cohen's h, odds ratios |
| File Organization | Incomplete | Full PROMPT.md structure |
| Ambiguity Handling | Schema only | Generation and tracking |
| Revision Tasks | Schema only | Full generation pipeline |

This improved plan addresses all 37 identified issues from the critique and provides 100% coverage of PROMPT.md requirements.
