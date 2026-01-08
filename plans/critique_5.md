# Gemini Writing Evaluation Framework - Improved Implementation Plan

## Document Info
- **Plan Version**: Critique 5 (Improved from Draft 5)
- **Date**: January 8, 2026
- **Scope**: Complete system architecture and implementation details with critical improvements

---

## Critical Issues Identified in Draft 5

Before presenting the improved plan, here are the key issues identified in the original draft:

### 1. **Technical Feasibility Issues**
- **Missing O*NET schema validation**: The SQL queries reference tables and columns without verifying they exist in the actual db/onet.db
- **Incorrect model IDs**: OpenRouter model IDs are speculative (e.g., "google/gemini-3-pro" may not be accurate)
- **Company database hardcoded**: The CompanySampler relies on a static hardcoded database rather than dynamic generation
- **LLM enrichment model references outdated**: Uses "claude-3-opus", "gpt-4-turbo" which don't match the models being evaluated

### 2. **Robustness Gaps**
- **Judge JSON parsing has no error handling**: If judge returns malformed JSON, the whole comparison fails
- **No handling of partial judge responses**: What if judge gives scores but invalid verdict?
- **Checkpoint manager uses sync file I/O in async context**: Could cause blocking
- **Missing validation for response pair shuffling**: No verification that shuffling is actually applied correctly

### 3. **Missed Requirements from PROMPT.md**
- **Dual judge personas not properly integrated**: Each comparison should use BOTH personas, but aggregation logic only considers one
- **No tone matching implementation**: PROMPT.md requires "tone matching from examples" scenarios
- **Multiple recipients (CC situations)** not fully implemented in prompt assembly
- **Regional English variants** tracking incomplete
- **Communication channel** should be inferred, not hardcoded
- **Revision/editing tasks** generation strategy missing

### 4. **Poor Design Decisions**
- **Stratified sampling too rigid**: Round-robin approach may not achieve good coverage with small sample sizes
- **Position bias detection uses wrong null hypothesis**: Assumes equal distribution of A/B/TIE which isn't realistic
- **Cost estimates use fixed token counts**: Actual variance is significant and should use distributions
- **Single-threaded checkpoint writes**: Could lose data under high load

### 5. **Missing Implementation Details**
- **No database migration strategy**: How to upgrade schema between versions
- **No API key validation**: Should verify OpenRouter key before starting
- **No prompt deduplication**: Could generate near-duplicate prompts
- **No sensitive topic tagging implementation**: Just schema, no logic
- **Missing instruction constraint generation**: Mentioned but not implemented

---

## 1. Executive Summary

This improved plan addresses the critical gaps identified above while preserving the strong architectural foundation of Draft 5. Key improvements include:

1. **Verified O*NET Integration**: SQL queries validated against actual schema from db/ONET_REFERENCE.md
2. **Robust Judge Integration**: Proper dual-persona evaluation with fallback parsing
3. **Dynamic Company Generation**: LLM-assisted company selection instead of static database
4. **Complete Prompt Diversity**: Full implementation of all PROMPT.md requirements
5. **Production-Grade Error Handling**: Comprehensive failure recovery throughout

---

## 2. System Architecture Overview

### 2.1 High-Level Component Diagram

```
+-----------------------------------------------------------------------------+
|                        GEMINI WRITING EVAL FRAMEWORK                         |
+-----------------------------------------------------------------------------+
|                                                                              |
|  +-------------+    +-------------+    +-------------+    +-------------+   |
|  |   CONFIG    |--->|   PROMPT    |--->|  RESPONSE   |--->|   JUDGE     |   |
|  |   MODULE    |    |  GENERATOR  |    |  COLLECTOR  |    |   MODULE    |   |
|  +------+------+    +------+------+    +------+------+    +------+------+   |
|         |                 |                  |                  |           |
|         v                 v                  v                  v           |
|  +---------------------------------------------------------------------+    |
|  |                         DATA LAYER (SQLite)                          |    |
|  |  +----------+  +----------+  +----------+  +----------+              |    |
|  |  | O*NET DB |  | Prompts  |  |Responses |  |Judgments |              |    |
|  |  | (source) |  | (frozen) |  |(per model)|  |(per eval) |              |    |
|  |  +----------+  +----------+  +----------+  +----------+              |    |
|  +---------------------------------------------------------------------+    |
|         |                                                                    |
|         v                                                                    |
|  +-------------+    +-------------+    +-------------+                      |
|  |  ANALYSIS   |--->|   REPORT    |--->|    TUI      |                      |
|  |   ENGINE    |    |  GENERATOR  |    |   VIEWER    |                      |
|  +-------------+    +-------------+    +-------------+                      |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### 2.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async support, rich ecosystem |
| Async HTTP | httpx | Modern, async-native HTTP client |
| Data Validation | Pydantic v2 | Type-safe schemas, JSON serialization |
| Database | SQLite + aiosqlite | Simple, portable, async-compatible |
| TUI Framework | textual | Rich terminal UI with modern widgets |
| Visualization | plotly | Interactive charts, PDF export |
| PDF Generation | weasyprint + jinja2 | Better CSS support than reportlab |
| CLI Framework | typer | Modern CLI with automatic help |
| Config Management | pydantic-settings | Environment + file config |
| Testing | pytest + pytest-asyncio | Async-aware testing |

### 2.3 Directory Structure

```
gemini-writing-eval/
+-- pyproject.toml                 # Project dependencies and metadata
+-- README.md                      # Setup and usage instructions
|
+-- src/
|   +-- __init__.py
|   |
|   +-- core/                      # Core domain models and interfaces
|   |   +-- __init__.py
|   |   +-- models.py              # Pydantic models for all entities
|   |   +-- interfaces.py          # Abstract base classes
|   |   +-- enums.py               # Enumerations (JudgeVerdict, etc.)
|   |   +-- exceptions.py          # Custom exception hierarchy
|   |
|   +-- config/                    # Configuration management
|   |   +-- __init__.py
|   |   +-- settings.py            # Global settings and presets
|   |   +-- presets.py             # 10 eval preset definitions
|   |   +-- cost_estimator.py      # Token/cost estimation
|   |   +-- model_registry.py      # OpenRouter model ID mapping
|   |
|   +-- data/                      # Data layer
|   |   +-- __init__.py
|   |   +-- onet_extractor.py      # O*NET database queries
|   |   +-- onet_schema.py         # Schema validation for O*NET
|   |   +-- naics_mapper.py        # Industry code mapping
|   |   +-- company_generator.py   # LLM-assisted company generation
|   |   +-- name_generator.py      # Realistic name generation
|   |   +-- results_db.py          # Results SQLite operations
|   |   +-- migrations.py          # Database schema migrations
|   |
|   +-- prompts/                   # Prompt generation pipeline
|   |   +-- __init__.py
|   |   +-- task_selector.py       # O*NET task sampling
|   |   +-- persona_generator.py   # Writer/recipient personas
|   |   +-- context_builder.py     # Context enrichment
|   |   +-- scenario_generator.py  # Special scenario types
|   |   +-- prompt_assembler.py    # Final prompt construction
|   |   +-- constraint_generator.py # Instruction constraints
|   |   +-- enrichment_llm.py      # LLM-based enrichment (Phase 3)
|   |   +-- deduplicator.py        # Prompt similarity detection
|   |
|   +-- eval/                      # Evaluation execution
|   |   +-- __init__.py
|   |   +-- orchestrator.py        # Main eval loop coordinator
|   |   +-- response_collector.py  # Model response gathering
|   |   +-- judge_module.py        # Judging logic
|   |   +-- judge_parser.py        # Robust JSON parsing for judgments
|   |   +-- vote_aggregator.py     # Majority-of-majorities
|   |   +-- checkpoint_manager.py  # Resume/checkpoint handling
|   |   +-- auto_loss_detector.py  # Refusal/failure detection
|   |
|   +-- api/                       # External API integrations
|   |   +-- __init__.py
|   |   +-- openrouter_client.py   # OpenRouter API wrapper
|   |   +-- rate_limiter.py        # Rate limiting with backoff
|   |   +-- retry_handler.py       # Retry logic with jitter
|   |   +-- api_validator.py       # API key validation
|   |
|   +-- analysis/                  # Post-eval analysis
|   |   +-- __init__.py
|   |   +-- win_rate_calculator.py # Win rate computation
|   |   +-- confidence_intervals.py # CI calculations
|   |   +-- bias_detector.py       # Systematic bias detection
|   |   +-- weakness_analyzer.py   # Weakness identification
|   |   +-- statistical_tests.py   # Significance testing
|   |   +-- refusal_analyzer.py    # Refusal pattern analysis
|   |
|   +-- reports/                   # Report generation
|   |   +-- __init__.py
|   |   +-- pdf_generator.py       # PDF report assembly
|   |   +-- chart_builder.py       # Visualization creation
|   |   +-- executive_summary.py   # Summary generation
|   |   +-- templates/             # Jinja2 templates for reports
|   |
|   +-- tui/                       # Terminal UI
|   |   +-- __init__.py
|   |   +-- app.py                 # Main textual app
|   |   +-- progress_screen.py     # Live progress dashboard
|   |   +-- results_browser.py     # Results exploration
|   |   +-- comparison_viewer.py   # Side-by-side response view
|   |
|   +-- cli/                       # Command-line interface
|       +-- __init__.py
|       +-- main.py                # Entry point
|       +-- run_cmd.py             # Run evaluation command
|       +-- view_cmd.py            # View results command
|       +-- compare_cmd.py         # Cross-run comparison
|       +-- validate_cmd.py        # Validate configuration
|
+-- db/
|   +-- onet.db                    # O*NET 30.1 database (provided)
|   +-- ONET_REFERENCE.md          # Schema documentation
|
+-- results/                       # Evaluation outputs (gitignored)
|   +-- eval_YYYY-MM-DD_HH-MM-SS/
|       +-- ...                    # Run-specific files
|
+-- tests/
    +-- __init__.py
    +-- conftest.py                # Pytest fixtures
    +-- test_onet_extraction.py
    +-- test_prompt_generation.py
    +-- test_judging.py
    +-- test_analysis.py
    +-- test_checkpoint.py
    +-- integration/
    |   +-- test_full_eval.py
    +-- fixtures/
        +-- sample_prompts.json
        +-- sample_responses.json
```

---

## 3. Core Data Models (Pydantic Schemas)

### 3.1 Prompt Models - Improved

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, Annotated
from datetime import datetime
from enum import Enum
import re

class FormalityLevel(str, Enum):
    """Corrected typo from FormailtyLevel"""
    VERY_CASUAL = "very_casual"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"
    VERY_FORMAL = "very_formal"

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    INITIAL = "initial"
    REPLY = "reply"
    FOLLOW_UP = "follow_up"

class AudienceSize(str, Enum):
    ONE_ON_ONE = "one_on_one"
    SMALL_GROUP = "small_group"
    DEPARTMENT = "department"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"
    NEGOTIATION = "negotiation"  # Added for completeness

class SensitiveTopic(str, Enum):
    """Explicit sensitive topic categorization"""
    HR_ISSUES = "hr_issues"
    LEGAL_MATTERS = "legal_matters"
    BAD_NEWS_DELIVERY = "bad_news_delivery"
    CONFIDENTIAL_INFO = "confidential_info"
    CONFLICT_SITUATION = "conflict_situation"
    PERFORMANCE_ISSUES = "performance_issues"
    TERMINATION = "termination"
    NONE = "none"

class PromptType(str, Enum):
    """Categorize prompt complexity and type"""
    SIMPLE = "simple"
    CONTEXT_RICH = "context_rich"
    REPLY_TO = "reply_to"
    REVISION = "revision"
    TONE_MATCHING = "tone_matching"
    AMBIGUOUS = "ambiguous"
    MULTI_RECIPIENT = "multi_recipient"
    INSTRUCTION_CONSTRAINED = "instruction_constrained"

class WriterPersona(BaseModel):
    """Full specification of the person writing"""
    name: str = Field(..., min_length=1)
    email: Optional[str] = None
    job_title: str
    department: Optional[str] = None
    age_range: str  # e.g., "25-35", "55-65"
    generation: str  # e.g., "GenZ", "Millennial", "GenX", "Boomer"
    skill_level: Literal["junior", "mid", "senior", "executive"]
    years_experience: int = Field(..., ge=0, le=50)
    english_variant: EnglishVariant = EnglishVariant.EN_US
    communication_style_notes: Optional[str] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('Invalid email format')
        return v

class RecipientPersona(BaseModel):
    """Full specification of the target reader"""
    name: str = Field(..., min_length=1)
    email: Optional[str] = None
    job_title: str
    company: Optional[str] = None
    relationship_to_writer: str  # e.g., "direct report", "client", "vendor"
    familiarity: Literal["first_contact", "acquaintance", "established", "close"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    technical_level: Literal["non_technical", "somewhat_technical", "technical", "expert"]
    is_primary: bool = True  # False for CC recipients

class CompanyContext(BaseModel):
    """Real company grounding - improved with validation"""
    name: str = Field(..., min_length=1)
    industry: str
    naics_code: str = Field(..., pattern=r'^\d{2}(-\d{2})?$')
    size_category: Literal["startup", "small", "medium", "large", "enterprise"]
    employee_count_range: str  # e.g., "10-50", "10000+"
    public_private: Literal["public", "private", "nonprofit", "government"]
    hq_location: str
    founded_year: Optional[int] = Field(None, ge=1800, le=2026)

    @property
    def approximate_employees(self) -> int:
        """Parse employee range to approximate number for cost estimation"""
        parts = self.employee_count_range.replace('+', '').split('-')
        if len(parts) == 2:
            return (int(parts[0]) + int(parts[1])) // 2
        return int(parts[0])

class AttachmentReference(BaseModel):
    """Mock attachment or reference content"""
    attachment_type: Literal[
        "report", "email_thread", "meeting_notes", "resume",
        "spreadsheet", "presentation", "contract", "proposal"
    ]
    description: str
    content_summary: str = Field(..., min_length=10)

class ToneExample(BaseModel):
    """Example writing to match tone from"""
    source_description: str  # "Sarah's typical client email"
    example_text: str
    key_characteristics: list[str]  # What to preserve

class InstructionConstraint(BaseModel):
    """Explicit instruction to test compliance"""
    constraint_type: Literal[
        "length_max", "length_min", "format_bullets",
        "format_paragraphs", "tone_directive", "exclusion", "inclusion"
    ]
    constraint_text: str  # The actual instruction
    verification_hint: str  # How to verify compliance

class WritingPrompt(BaseModel):
    """Complete prompt specification - improved with validation"""
    prompt_id: str = Field(..., pattern=r'^prompt_\d{8}_\d{6}_[a-f0-9]{8}$')

    # O*NET source
    onet_task_id: str
    onet_task_statement: str
    onet_occupation_code: str = Field(..., pattern=r'^\d{2}-\d{4}\.\d{2}$')
    onet_occupation_title: str
    onet_job_zone: int = Field(..., ge=1, le=5)
    soc_major_group: str

    # Company context
    company: CompanyContext

    # People - improved to handle multiple recipients properly
    writer: WriterPersona
    primary_recipient: RecipientPersona
    cc_recipients: list[RecipientPersona] = Field(default_factory=list)

    @property
    def all_recipients(self) -> list[RecipientPersona]:
        return [self.primary_recipient] + self.cc_recipients

    # Communication context
    formality_level: FormalityLevel
    message_position: MessagePosition
    audience_size: AudienceSize
    emotional_context: EmotionalContext
    urgency: Literal["low", "medium", "high", "critical"]

    # Content requirements
    communication_channel: Optional[str] = None  # Inferred from task
    competing_objectives: list[str] = Field(default_factory=list, max_length=3)
    explicit_constraints: list[InstructionConstraint] = Field(default_factory=list)

    # Attachments/context
    attachments: list[AttachmentReference] = Field(default_factory=list)
    prior_messages: list[str] = Field(default_factory=list)
    tone_example: Optional[ToneExample] = None

    # Temporal
    temporal_context: Optional[str] = None

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    sensitive_topics: list[SensitiveTopic] = Field(default_factory=lambda: [SensitiveTopic.NONE])
    prompt_type: PromptType = PromptType.SIMPLE
    inferred_writing_category: str

    # Flags for analysis
    is_revision_task: bool = False
    is_ambiguous_task: bool = False
    has_instruction_constraints: bool = False
    has_tone_matching: bool = False
    has_multiple_recipients: bool = False

    # The actual prompt text sent to models
    assembled_prompt: str

    # Generation metadata
    generation_seed: int
    generation_timestamp: datetime
    enrichment_model: Optional[str] = None  # Track which model enriched

    @model_validator(mode='after')
    def validate_flags(self):
        """Ensure flags match actual content"""
        self.has_instruction_constraints = len(self.explicit_constraints) > 0
        self.has_tone_matching = self.tone_example is not None
        self.has_multiple_recipients = len(self.cc_recipients) > 0
        self.is_revision_task = self.prompt_type == PromptType.REVISION
        self.is_ambiguous_task = self.prompt_type == PromptType.AMBIGUOUS
        return self
```

### 3.2 Response Models - Improved

```python
class ResponseStatus(str, Enum):
    """Explicit response status tracking"""
    SUCCESS = "success"
    REFUSAL = "refusal"
    ERROR = "error"
    TIMEOUT = "timeout"
    INCOMPLETE = "incomplete"
    OFF_TOPIC = "off_topic"

class RefusalCategory(str, Enum):
    """Detailed refusal categorization per PROMPT.md"""
    SAFETY = "safety"
    CAPABILITY = "capability"
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE = "incomplete"
    OFF_TOPIC = "off_topic"
    API_ERROR = "api_error"
    NONE = "none"

class ResponseFormatAnalysis(BaseModel):
    """Detailed format analysis for bias detection"""
    word_count: int
    character_count: int
    sentence_count: int
    paragraph_count: int
    has_bullet_points: bool
    bullet_count: int = 0
    has_headers: bool
    header_count: int = 0
    has_greeting: bool
    greeting_type: Optional[str] = None  # "formal", "casual", "none"
    has_signoff: bool
    signoff_type: Optional[str] = None  # "formal", "casual", "none"
    has_emoji: bool = False
    estimated_reading_time_seconds: int = 0

class ModelResponse(BaseModel):
    """A single model's response to a prompt - improved"""
    response_id: str
    prompt_id: str
    model_id: str  # OpenRouter model identifier
    model_display_name: str

    # Response content
    response_text: str

    # Status tracking
    status: ResponseStatus = ResponseStatus.SUCCESS
    refusal_category: RefusalCategory = RefusalCategory.NONE
    error_message: Optional[str] = None

    # Performance metadata
    response_time_ms: int = Field(..., ge=-1)  # -1 for errors
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)

    # Format analysis
    format_analysis: ResponseFormatAnalysis

    # Raw API response (for debugging)
    raw_api_response: dict

    timestamp: datetime

    @property
    def is_valid_response(self) -> bool:
        """Check if response can be judged"""
        return self.status == ResponseStatus.SUCCESS

    @property
    def triggers_auto_loss(self) -> bool:
        """Check if response should auto-lose"""
        return self.status in (
            ResponseStatus.REFUSAL,
            ResponseStatus.ERROR,
            ResponseStatus.TIMEOUT,
            ResponseStatus.OFF_TOPIC
        )

class ResponsePair(BaseModel):
    """A pair of responses for side-by-side comparison - improved"""
    pair_id: str
    prompt_id: str
    response_a: ModelResponse
    response_b: ModelResponse

    # Ordering (for position bias mitigation)
    gemini_position: Literal["A", "B"]
    shuffle_seed: int

    # Pre-computed for convenience
    gemini_response_id: str
    opponent_response_id: str

    @model_validator(mode='after')
    def validate_positions(self):
        """Verify shuffle was applied correctly"""
        if self.gemini_position == "A":
            assert "gemini" in self.response_a.model_id.lower()
        else:
            assert "gemini" in self.response_b.model_id.lower()
        return self

    @property
    def has_auto_loss(self) -> tuple[bool, bool]:
        """Return (gemini_auto_loss, opponent_auto_loss)"""
        if self.gemini_position == "A":
            return (
                self.response_a.triggers_auto_loss,
                self.response_b.triggers_auto_loss
            )
        return (
            self.response_b.triggers_auto_loss,
            self.response_a.triggers_auto_loss
        )
```

### 3.3 Judgment Models - Improved with Dual Persona Support

```python
class JudgeVerdict(str, Enum):
    RESPONSE_A_WINS = "A"
    RESPONSE_B_WINS = "B"
    TIE = "TIE"

class JudgePersona(str, Enum):
    WRITING_EXPERT = "writing_expert"
    TARGET_RECIPIENT = "target_recipient"

class CriteriaScores(BaseModel):
    """Scores for evaluation criteria (1-5 scale)"""
    quality: int = Field(..., ge=1, le=5)
    tone_appropriateness: int = Field(..., ge=1, le=5)
    length_appropriateness: int = Field(..., ge=1, le=5)
    effectiveness: int = Field(..., ge=1, le=5)
    authenticity: int = Field(..., ge=1, le=5)  # Human-like quality
    cliche_avoidance: int = Field(..., ge=1, le=5)
    instruction_compliance: Optional[int] = Field(None, ge=1, le=5)

    @property
    def total_score(self) -> float:
        """Weighted total score"""
        scores = [
            self.quality,
            self.tone_appropriateness,
            self.length_appropriateness,
            self.effectiveness,
            self.authenticity * 1.2,  # Weight authenticity higher
            self.cliche_avoidance * 1.2  # Weight cliche avoidance higher
        ]
        if self.instruction_compliance:
            scores.append(self.instruction_compliance * 1.5)  # Weight compliance highest
        return sum(scores) / len(scores)

class SingleJudgment(BaseModel):
    """One judge's single vote - improved with better parsing"""
    judgment_id: str
    pair_id: str
    judge_model_id: str
    judge_persona: JudgePersona
    vote_index: int = Field(..., ge=0, le=4)

    verdict: JudgeVerdict
    reasoning: str = Field(..., min_length=10)

    # Structured scores
    scores_a: CriteriaScores
    scores_b: CriteriaScores

    # Parsing metadata
    raw_response: str
    parse_success: bool = True
    parse_warnings: list[str] = Field(default_factory=list)

    # Performance
    response_time_ms: int
    timestamp: datetime

class PersonaJudgmentSet(BaseModel):
    """All judgments from one judge model for one persona"""
    judge_model_id: str
    judge_persona: JudgePersona
    pair_id: str

    individual_judgments: list[SingleJudgment]
    majority_verdict: JudgeVerdict

    vote_counts: dict[JudgeVerdict, int]
    average_scores_a: CriteriaScores
    average_scores_b: CriteriaScores

class JudgeModelResult(BaseModel):
    """Combined result from one judge model across BOTH personas"""
    judge_model_id: str
    pair_id: str

    # Results per persona
    writing_expert_result: PersonaJudgmentSet
    target_recipient_result: PersonaJudgmentSet

    # Combined verdict (majority across both personas)
    combined_verdict: JudgeVerdict

    # Agreement between personas
    personas_agree: bool

class ComparisonResult(BaseModel):
    """Final result for one prompt comparison - improved"""
    comparison_id: str
    pair_id: str
    prompt_id: str

    # Models being compared
    gemini_model_id: str
    opponent_model_id: str

    # Per-judge-model results (includes both personas per judge)
    judge_results: list[JudgeModelResult]

    # Final aggregation
    final_verdict: JudgeVerdict
    gemini_verdict: Literal["WIN", "LOSS", "TIE"]

    # Vote breakdown
    judges_for_gemini: int
    judges_for_opponent: int
    judges_tie: int

    # Quality metrics
    unanimous: bool
    inter_persona_agreement_rate: float  # How often personas agreed

    # Auto-loss tracking
    gemini_auto_loss: bool = False
    opponent_auto_loss: bool = False
    auto_loss_reason: Optional[str] = None

    # Metadata
    total_judge_calls: int
    total_judge_time_ms: int
    timestamp: datetime
```

---

## 4. Data Pipeline: O*NET to Prompts - Improved

### 4.1 Phase 1: Task Extraction with Schema Validation

**Critical Fix**: The draft assumed table/column names. We must validate against actual schema.

```python
class ONetSchemaValidator:
    """Validates O*NET database schema before queries"""

    REQUIRED_TABLES = [
        'task_statements',
        'occupation_data',
        'job_zones',
        'skills',
        'work_context'
    ]

    REQUIRED_COLUMNS = {
        'task_statements': ['task_id', 'task', 'task_type', 'onetsoc_code'],
        'occupation_data': ['onetsoc_code', 'title', 'description'],
        'job_zones': ['onetsoc_code', 'job_zone'],
        'skills': ['onetsoc_code', 'element_id', 'scale_id', 'data_value'],
        'work_context': ['onetsoc_code', 'element_id', 'scale_id', 'data_value']
    }

    async def validate(self, db_path: str) -> tuple[bool, list[str]]:
        """Validate schema, return (success, list of issues)"""
        issues = []

        async with aiosqlite.connect(db_path) as db:
            # Check tables exist
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            existing_tables = {row[0] for row in await cursor.fetchall()}

            for table in self.REQUIRED_TABLES:
                if table not in existing_tables:
                    issues.append(f"Missing table: {table}")
                    continue

                # Check columns
                cursor = await db.execute(f"PRAGMA table_info({table})")
                existing_cols = {row[1] for row in await cursor.fetchall()}

                for col in self.REQUIRED_COLUMNS.get(table, []):
                    if col not in existing_cols:
                        issues.append(f"Missing column: {table}.{col}")

        return (len(issues) == 0, issues)


class ONetTaskExtractor:
    """Extracts writing-relevant tasks from O*NET with proper error handling"""

    # Element IDs based on O*NET documentation
    WRITING_SKILL_ELEMENT = '2.A.1.c'  # Written Expression
    EMAIL_CONTEXT_ELEMENT = '4.C.1.a.2.h'  # Electronic Mail
    CORRESPONDENCE_ELEMENT = '4.C.1.a.2.j'  # Letters and Memos

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._validated = False

    async def validate_schema(self) -> None:
        """Validate schema before first use"""
        validator = ONetSchemaValidator()
        success, issues = await validator.validate(self.db_path)
        if not success:
            raise SchemaValidationError(
                f"O*NET database schema validation failed:\n" +
                "\n".join(issues)
            )
        self._validated = True

    async def extract_writing_tasks(
        self,
        min_writing_score: float = 0.0,
        limit: Optional[int] = None
    ) -> list[dict]:
        """Extract tasks with writing relevance signals"""

        if not self._validated:
            await self.validate_schema()

        # Use parameterized queries for safety
        query = """
        WITH writing_skills AS (
            SELECT onetsoc_code, data_value as writing_skill
            FROM skills
            WHERE element_id = ? AND scale_id = 'IM'
        ),
        email_freq AS (
            SELECT onetsoc_code, data_value as email_frequency
            FROM work_context
            WHERE element_id = ? AND scale_id = 'CX'
        ),
        correspondence_freq AS (
            SELECT onetsoc_code, data_value as correspondence_frequency
            FROM work_context
            WHERE element_id = ? AND scale_id = 'CX'
        )
        SELECT DISTINCT
            t.task_id,
            t.task,
            t.task_type,
            t.onetsoc_code,
            o.title as occupation_title,
            o.description as occupation_description,
            COALESCE(jz.job_zone, 3) as job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major,
            COALESCE(ws.writing_skill, 2.5) as writing_skill,
            COALESCE(ef.email_frequency, 2.5) as email_frequency,
            COALESCE(cf.correspondence_frequency, 2.5) as correspondence_frequency
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        LEFT JOIN writing_skills ws ON t.onetsoc_code = ws.onetsoc_code
        LEFT JOIN email_freq ef ON t.onetsoc_code = ef.onetsoc_code
        LEFT JOIN correspondence_freq cf ON t.onetsoc_code = cf.onetsoc_code
        WHERE (
            t.task LIKE '%write%' ESCAPE '\\' OR
            t.task LIKE '%draft%' ESCAPE '\\' OR
            t.task LIKE '%document%' ESCAPE '\\' OR
            t.task LIKE '%correspond%' ESCAPE '\\' OR
            t.task LIKE '%email%' ESCAPE '\\' OR
            t.task LIKE '%memo%' ESCAPE '\\' OR
            t.task LIKE '%report%' ESCAPE '\\' OR
            t.task LIKE '%communicate%' ESCAPE '\\' OR
            t.task LIKE '%letter%' ESCAPE '\\' OR
            t.task LIKE '%present%' ESCAPE '\\' OR
            COALESCE(ws.writing_skill, 0) >= 3.5 OR
            COALESCE(ef.email_frequency, 0) >= 3.5 OR
            COALESCE(cf.correspondence_frequency, 0) >= 3.5
        )
        """

        params = [
            self.WRITING_SKILL_ELEMENT,
            self.EMAIL_CONTEXT_ELEMENT,
            self.CORRESPONDENCE_ELEMENT
        ]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        tasks = []
        for row in rows:
            # Calculate composite writing relevance score
            score = self._calculate_writing_score(dict(row))
            if score >= min_writing_score:
                task = dict(row)
                task['writing_relevance_score'] = score
                task['inferred_category'] = self._classify_category(task['task'])
                tasks.append(task)

        return tasks

    def _calculate_writing_score(self, task: dict) -> float:
        """Calculate composite writing relevance score"""
        score = 0.0
        task_lower = task['task'].lower()

        # Explicit writing keywords
        if any(kw in task_lower for kw in ['write', 'draft', 'author', 'compose']):
            score += 3.0

        # Communication keywords
        if any(kw in task_lower for kw in ['correspond', 'email', 'memo', 'letter']):
            score += 2.5

        # Reporting keywords
        if any(kw in task_lower for kw in ['report', 'document', 'summarize']):
            score += 2.0

        # O*NET skill/context scores
        score += float(task.get('writing_skill', 2.5)) * 0.5
        score += float(task.get('email_frequency', 2.5)) * 0.3
        score += float(task.get('correspondence_frequency', 2.5)) * 0.3

        return score

    def _classify_category(self, task_text: str) -> str:
        """Classify task into writing category"""
        task_lower = task_text.lower()

        # Order matters - more specific patterns first
        patterns = [
            ('contracts_legal', r'\b(contract|agreement|legal|license|compliance)\b'),
            ('policy_procedure', r'\b(polic|procedure|guideline|standard|regulation)\b'),
            ('training_instruction', r'\b(train|instruct|teach|curriculum|manual)\b'),
            ('persuasion_negotiation', r'\b(negotiat|propos|persuad|recommend|pitch)\b'),
            ('feedback_evaluation', r'\b(evaluat|feedback|review|assess|apprais)\b'),
            ('customer_communication', r'\b(customer|client|patient|consumer)\b'),
            ('reports_presentations', r'\b(report|present|summar|brief)\b'),
            ('correspondence', r'\b(correspond|email|letter|memo|message)\b'),
            ('internal_coordination', r'\b(confer|coordinate|collaborat|meet)\b'),
            ('explicit_writing', r'\b(write|draft|document|compose|author)\b'),
        ]

        for category, pattern in patterns:
            if re.search(pattern, task_lower):
                return category

        return "general"
```

### 4.2 Phase 2: LLM-Assisted Company Generation

**Critical Improvement**: Instead of a hardcoded company database, use LLM to generate realistic companies dynamically.

```python
class CompanyGenerator:
    """LLM-assisted company generation for realistic grounding"""

    COMPANY_GENERATION_PROMPT = """
Generate a realistic company for the following context. The company should be a REAL company
that actually exists, appropriate for this industry and size category.

Industry (NAICS): {naics_code} - {naics_name}
Size Category: {size_category}
Occupation Context: {occupation_title}

Return a JSON object with these exact fields:
{{
    "name": "Real company name",
    "industry": "Industry description",
    "size_category": "{size_category}",
    "employee_count_range": "e.g., 1000-5000",
    "public_private": "public|private|nonprofit|government",
    "hq_location": "City, State/Country",
    "founded_year": YYYY,
    "brief_description": "One sentence about the company"
}}

Requirements:
- Use a REAL company name that exists
- Match the size category accurately
- Ensure the company operates in or is relevant to the given industry
- For startups, use real startups (founded 2015 or later)
- Provide accurate founding year

Return ONLY the JSON, no other text.
"""

    def __init__(self, client: OpenRouterClient, cache_path: Optional[str] = None):
        self.client = client
        self.cache: dict[str, CompanyContext] = {}
        self.cache_path = cache_path
        if cache_path and Path(cache_path).exists():
            self._load_cache()

    async def generate_company(
        self,
        naics_code: str,
        naics_name: str,
        size_category: str,
        occupation_title: str,
        seed: int
    ) -> CompanyContext:
        """Generate a realistic company for the given context"""

        # Check cache first
        cache_key = f"{naics_code}_{size_category}_{seed % 100}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = self.COMPANY_GENERATION_PROMPT.format(
            naics_code=naics_code,
            naics_name=naics_name,
            size_category=size_category,
            occupation_title=occupation_title
        )

        # Rotate through models to avoid bias
        models = [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "google/gemini-1.5-flash"
        ]
        model = models[seed % len(models)]

        try:
            response = await self.client.complete(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )

            # Parse with error handling
            company_data = self._parse_company_json(response.content)
            company = CompanyContext(
                name=company_data["name"],
                industry=company_data["industry"],
                naics_code=naics_code,
                size_category=company_data["size_category"],
                employee_count_range=company_data["employee_count_range"],
                public_private=company_data["public_private"],
                hq_location=company_data["hq_location"],
                founded_year=company_data.get("founded_year")
            )

            # Cache result
            self.cache[cache_key] = company
            self._save_cache()

            return company

        except Exception as e:
            logger.warning(f"Company generation failed: {e}, using fallback")
            return self._fallback_company(naics_code, size_category)

    def _parse_company_json(self, text: str) -> dict:
        """Robust JSON parsing from LLM response"""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find JSON object anywhere in text
        brace_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group())

        raise ValueError(f"Could not parse company JSON from: {text[:200]}")

    def _fallback_company(self, naics_code: str, size_category: str) -> CompanyContext:
        """Fallback company when generation fails"""
        fallbacks = {
            "enterprise": ("Acme Corporation", "10000+", "public", "New York, NY"),
            "large": ("TechCorp Inc", "1000-5000", "private", "San Francisco, CA"),
            "medium": ("Midsize Solutions", "200-500", "private", "Austin, TX"),
            "small": ("Small Business Co", "20-50", "private", "Denver, CO"),
            "startup": ("NewVenture Labs", "5-20", "private", "San Francisco, CA"),
        }
        name, employees, pub_priv, hq = fallbacks.get(
            size_category,
            fallbacks["medium"]
        )
        return CompanyContext(
            name=name,
            industry="Professional Services",
            naics_code=naics_code,
            size_category=size_category,
            employee_count_range=employees,
            public_private=pub_priv,
            hq_location=hq,
            founded_year=2000
        )

    def _load_cache(self):
        """Load company cache from disk"""
        with open(self.cache_path) as f:
            data = json.load(f)
            self.cache = {k: CompanyContext(**v) for k, v in data.items()}

    def _save_cache(self):
        """Save company cache to disk"""
        if self.cache_path:
            with open(self.cache_path, 'w') as f:
                json.dump({k: v.model_dump() for k, v in self.cache.items()}, f)
```

### 4.3 Phase 2: Improved Stratified Sampling

**Critical Fix**: Better sampling strategy that works for small sample sizes.

```python
class ImprovedStratifiedSampler:
    """Stratified sampling that works across all sample sizes"""

    def __init__(self, tasks: list[dict], config: SamplingConfig):
        self.tasks = tasks
        self.config = config
        self.rng = random.Random(config.random_seed)

    def sample(self, n: int) -> list[dict]:
        """Sample n tasks with proper stratification"""

        # Build indices by dimension
        indices = {
            'job_zone': defaultdict(list),
            'soc_major': defaultdict(list),
            'category': defaultdict(list),
        }

        for i, task in enumerate(self.tasks):
            indices['job_zone'][task['job_zone']].append(i)
            indices['soc_major'][task['soc_major']].append(i)
            indices['category'][task['inferred_category']].append(i)

        # Calculate target distribution
        if n >= 100:
            # For larger samples, aim for even distribution
            return self._stratified_sample(indices, n)
        else:
            # For smaller samples, prioritize diversity over evenness
            return self._diversity_sample(indices, n)

    def _stratified_sample(self, indices: dict, n: int) -> list[dict]:
        """Even distribution across dimensions for larger samples"""
        selected_indices = set()

        # Determine how many from each dimension
        dimensions = ['job_zone', 'soc_major', 'category']
        per_round = max(1, n // (len(dimensions) * 5))

        while len(selected_indices) < n:
            for dim in dimensions:
                if len(selected_indices) >= n:
                    break

                # Get buckets sorted by how underrepresented they are
                buckets = sorted(
                    indices[dim].items(),
                    key=lambda x: len([i for i in x[1] if i not in selected_indices]),
                    reverse=True
                )

                for bucket_key, bucket_indices in buckets:
                    if len(selected_indices) >= n:
                        break

                    available = [i for i in bucket_indices if i not in selected_indices]
                    if available:
                        to_select = min(per_round, len(available), n - len(selected_indices))
                        selected_indices.update(self.rng.sample(available, to_select))

        return [self.tasks[i] for i in selected_indices]

    def _diversity_sample(self, indices: dict, n: int) -> list[dict]:
        """Maximize diversity for smaller samples"""
        selected_indices = set()
        dimension_coverage = {dim: set() for dim in indices}

        while len(selected_indices) < n:
            # Find dimension with least coverage
            min_coverage_dim = min(
                dimension_coverage.keys(),
                key=lambda d: len(dimension_coverage[d]) / max(len(indices[d]), 1)
            )

            # Find uncovered bucket in that dimension
            uncovered = [
                k for k in indices[min_coverage_dim]
                if k not in dimension_coverage[min_coverage_dim]
            ]

            if uncovered:
                bucket = self.rng.choice(uncovered)
            else:
                # All buckets covered, pick any with available tasks
                available_buckets = [
                    k for k, v in indices[min_coverage_dim].items()
                    if any(i not in selected_indices for i in v)
                ]
                if not available_buckets:
                    # Move to next dimension
                    del dimension_coverage[min_coverage_dim]
                    if not dimension_coverage:
                        break
                    continue
                bucket = self.rng.choice(available_buckets)

            # Select one task from this bucket
            available = [i for i in indices[min_coverage_dim][bucket]
                        if i not in selected_indices]
            if available:
                selected = self.rng.choice(available)
                selected_indices.add(selected)
                task = self.tasks[selected]

                # Update coverage
                for dim in dimension_coverage:
                    if dim == 'job_zone':
                        dimension_coverage[dim].add(task['job_zone'])
                    elif dim == 'soc_major':
                        dimension_coverage[dim].add(task['soc_major'])
                    elif dim == 'category':
                        dimension_coverage[dim].add(task['inferred_category'])

        return [self.tasks[i] for i in selected_indices]
```

### 4.4 Phase 3: Special Scenario Generation

**Missing from Draft**: Implementation for revision tasks, tone matching, ambiguous prompts, etc.

```python
class ScenarioGenerator:
    """Generates special scenario types per PROMPT.md requirements"""

    def __init__(self, client: OpenRouterClient):
        self.client = client

    async def generate_revision_scenario(
        self,
        task: dict,
        seed: int
    ) -> tuple[str, str]:
        """Generate a draft text that needs revision"""
        prompt = f"""
Generate a realistic but FLAWED draft for this writing task that needs revision:
Task: {task['task']}
Occupation: {task['occupation_title']}

Create a draft with ONE of these issues (pick one):
1. Too verbose - needs to be more concise
2. Too casual for the context - needs to be more professional
3. Too harsh - needs softer tone
4. Too vague - needs more specific details
5. Poor structure - needs reorganization

Return JSON:
{{
    "draft": "The flawed draft text...",
    "revision_instruction": "What specific change is needed",
    "flaw_type": "verbose|casual|harsh|vague|structure"
}}
"""
        response = await self._call_llm(prompt, seed)
        data = json.loads(response)
        return data['draft'], data['revision_instruction']

    async def generate_tone_example(
        self,
        task: dict,
        writer: WriterPersona,
        seed: int
    ) -> ToneExample:
        """Generate an example to match tone from"""
        prompt = f"""
Generate an example of how {writer.name} typically writes, to serve as a tone reference.

Context:
- Writer: {writer.name}, {writer.job_title}
- Age/Generation: {writer.age_range} ({writer.generation})
- Task type: {task['task']}

Create a SHORT example (2-3 sentences) showing their typical communication style.
Then identify 3 key characteristics to preserve.

Return JSON:
{{
    "example_text": "Sample writing showing their style...",
    "characteristics": ["characteristic 1", "characteristic 2", "characteristic 3"],
    "source_description": "Where this example is from (e.g., 'previous client email')"
}}
"""
        response = await self._call_llm(prompt, seed)
        data = json.loads(response)
        return ToneExample(
            source_description=data['source_description'],
            example_text=data['example_text'],
            key_characteristics=data['characteristics']
        )

    async def generate_reply_context(
        self,
        task: dict,
        recipient: RecipientPersona,
        seed: int
    ) -> list[str]:
        """Generate prior messages to reply to"""
        prompt = f"""
Generate 1-2 prior messages that set up a reply scenario for this task.

Task: {task['task']}
From: {recipient.name}, {recipient.job_title}
Relationship: {recipient.relationship_to_writer}

The prior message(s) should create one of these situations:
1. Angry/frustrated message needing diplomatic response
2. Vague request needing clarification
3. Technical question needing helpful answer
4. Rejection that needs counter-proposal
5. Request that needs follow-up

Return JSON:
{{
    "messages": ["First message...", "Optional second message..."],
    "situation_type": "angry|vague|technical|rejection|followup"
}}
"""
        response = await self._call_llm(prompt, seed)
        data = json.loads(response)
        return data['messages']

    async def generate_ambiguous_prompt(
        self,
        task: dict,
        seed: int
    ) -> str:
        """Generate deliberately vague prompt to test model handling"""
        ambiguity_types = [
            "underspecified recipient",
            "missing context",
            "unclear ask"
        ]
        ambiguity = ambiguity_types[seed % len(ambiguity_types)]

        prompt = f"""
Rewrite this task to be deliberately vague with "{ambiguity}":

Original task: {task['task']}

Make it ambiguous but still recognizable as a writing task.
The model should either make reasonable assumptions or ask for clarification.

Return just the ambiguous task description, nothing else.
"""
        return await self._call_llm(prompt, seed)

    def generate_instruction_constraints(
        self,
        seed: int
    ) -> list[InstructionConstraint]:
        """Generate explicit instruction constraints to test compliance"""
        rng = random.Random(seed)

        all_constraints = [
            InstructionConstraint(
                constraint_type="length_max",
                constraint_text="Keep this under 100 words",
                verification_hint="word_count <= 100"
            ),
            InstructionConstraint(
                constraint_type="length_min",
                constraint_text="This should be comprehensive, at least 500 words",
                verification_hint="word_count >= 500"
            ),
            InstructionConstraint(
                constraint_type="format_bullets",
                constraint_text="Use exactly 3 bullet points",
                verification_hint="bullet_count == 3"
            ),
            InstructionConstraint(
                constraint_type="format_paragraphs",
                constraint_text="Write in paragraph form only, no bullet points",
                verification_hint="bullet_count == 0"
            ),
            InstructionConstraint(
                constraint_type="tone_directive",
                constraint_text="Be direct and avoid pleasantries",
                verification_hint="no_greeting and no_signoff"
            ),
            InstructionConstraint(
                constraint_type="exclusion",
                constraint_text="Do not mention the budget",
                verification_hint="'budget' not in text.lower()"
            ),
            InstructionConstraint(
                constraint_type="inclusion",
                constraint_text="Make sure to include a clear call to action",
                verification_hint="has_call_to_action"
            ),
        ]

        # Select 1-2 constraints that don't conflict
        selected = [rng.choice(all_constraints)]
        if rng.random() < 0.3:  # 30% chance of second constraint
            compatible = [c for c in all_constraints
                         if c.constraint_type != selected[0].constraint_type]
            if compatible:
                selected.append(rng.choice(compatible))

        return selected

    async def _call_llm(self, prompt: str, seed: int) -> str:
        """Helper to call LLM with model rotation"""
        models = ["anthropic/claude-3.5-sonnet", "openai/gpt-4o"]
        model = models[seed % len(models)]
        response = await self.client.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.content
```

---

## 5. Evaluation Flow and Judging System - Improved

### 5.1 Robust Judge Parser

**Critical Addition**: The draft had no error handling for judge JSON parsing.

```python
class JudgeResponseParser:
    """Robust parser for judge responses with fallback strategies"""

    def parse(
        self,
        raw_response: str,
        has_instruction_constraints: bool = False
    ) -> tuple[dict, list[str]]:
        """
        Parse judge response with multiple fallback strategies.
        Returns (parsed_data, warnings)
        """
        warnings = []

        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(raw_response)
            return self._validate_and_normalize(data, has_instruction_constraints), warnings
        except json.JSONDecodeError:
            warnings.append("Direct JSON parse failed")

        # Strategy 2: Extract from code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return self._validate_and_normalize(data, has_instruction_constraints), warnings
            except json.JSONDecodeError:
                warnings.append("Code block JSON parse failed")

        # Strategy 3: Find JSON object in text
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_response, re.DOTALL)
        if brace_match:
            try:
                data = json.loads(brace_match.group())
                return self._validate_and_normalize(data, has_instruction_constraints), warnings
            except json.JSONDecodeError:
                warnings.append("Extracted JSON parse failed")

        # Strategy 4: Regex extraction of individual fields
        warnings.append("Falling back to regex extraction")
        data = self._extract_via_regex(raw_response)
        return self._validate_and_normalize(data, has_instruction_constraints), warnings

    def _extract_via_regex(self, text: str) -> dict:
        """Extract judgment fields via regex patterns"""
        data = {}

        # Extract verdict
        verdict_match = re.search(
            r'"?verdict"?\s*[:=]\s*"?(A|B|TIE)"?',
            text, re.IGNORECASE
        )
        if verdict_match:
            data['verdict'] = verdict_match.group(1).upper()
        else:
            # Look for explicit statements
            if re.search(r'response\s*A\s*(is\s+)?better|choose\s*A|winner.*A', text, re.I):
                data['verdict'] = 'A'
            elif re.search(r'response\s*B\s*(is\s+)?better|choose\s*B|winner.*B', text, re.I):
                data['verdict'] = 'B'
            else:
                data['verdict'] = 'TIE'

        # Extract reasoning
        reasoning_match = re.search(
            r'"?reasoning"?\s*[:=]\s*"([^"]+)"',
            text
        )
        data['reasoning'] = reasoning_match.group(1) if reasoning_match else text[:500]

        # Extract scores with fallback to neutral
        score_patterns = [
            ('quality', r'quality[_\s]*(a|b)\s*[:=]\s*(\d)'),
            ('tone', r'tone[_\s]*(a|b)\s*[:=]\s*(\d)'),
            ('length', r'length[_\s]*(a|b)\s*[:=]\s*(\d)'),
            ('effectiveness', r'effectiveness[_\s]*(a|b)\s*[:=]\s*(\d)'),
            ('authenticity', r'authenticity[_\s]*(a|b)\s*[:=]\s*(\d)'),
            ('cliche', r'cliche[_\s]*(a|b)\s*[:=]\s*(\d)'),
        ]

        for field, pattern in score_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for side, score in matches:
                key = f"{field}_{side.lower()}"
                data[key] = int(score)

        return data

    def _validate_and_normalize(
        self,
        data: dict,
        has_instruction_constraints: bool
    ) -> dict:
        """Ensure all required fields exist with valid values"""
        normalized = {}

        # Verdict (required)
        verdict = data.get('verdict', 'TIE').upper()
        if verdict not in ('A', 'B', 'TIE'):
            verdict = 'TIE'
        normalized['verdict'] = verdict

        # Reasoning (required)
        normalized['reasoning'] = data.get('reasoning', 'No reasoning provided')

        # Scores for A and B
        score_fields = [
            'quality', 'tone', 'length', 'effectiveness',
            'authenticity', 'cliche'
        ]

        for field in score_fields:
            for side in ['a', 'b']:
                key = f"{field}_{side}"
                value = data.get(key, data.get(f"{field}_score_{side}", 3))
                normalized[key] = max(1, min(5, int(value) if value else 3))

        # Instruction compliance (optional)
        if has_instruction_constraints:
            for side in ['a', 'b']:
                key = f"compliance_{side}"
                value = data.get(key, data.get(f"instruction_compliance_{side}", 3))
                normalized[key] = max(1, min(5, int(value) if value else 3))

        return normalized
```

### 5.2 Improved Judge Module with Dual Personas

**Critical Fix**: Properly integrate both personas per PROMPT.md requirements.

```python
class ImprovedJudgeModule:
    """Judging with proper dual-persona evaluation"""

    JUDGE_PROMPT_TEMPLATE = """
You are evaluating two writing responses for the same task.

## YOUR ROLE: {persona_description}

## TASK CONTEXT

**Original Writing Task:**
{task_statement}

**Writer Persona:**
- Name: {writer_name}, {writer_title} at {company_name}
- Age/Generation: {writer_age} ({writer_generation})
- Skill Level: {writer_skill_level}
- Years Experience: {writer_years}

**Primary Recipient:**
- Name: {recipient_name}, {recipient_title}
- Relationship: {recipient_relationship}
- Familiarity: {recipient_familiarity}
{cc_recipients_section}

**Communication Context:**
- Formality: {formality}
- Urgency: {urgency}
- Message Type: {message_position}
- Emotional Context: {emotional_context}
{channel_section}

{attachments_section}
{prior_messages_section}
{constraints_section}

---

## RESPONSE A

{response_a}

---

## RESPONSE B

{response_b}

---

## EVALUATION INSTRUCTIONS

{persona_specific_instructions}

Rate each response on these criteria (1-5 scale, where 5 is best):

1. **Quality of Writing** - Grammar, clarity, structure, flow
2. **Tone Appropriateness** - Does it match the required formality and context?
3. **Length Appropriateness** - Is it the RIGHT length for this specific task?
4. **Effectiveness** - Does it achieve the communication goal?
5. **Authenticity** - Does it read like realistic human writing from this persona, not AI-generated?
6. **Cliche Avoidance** - Does it avoid generic AI patterns ("I hope this email finds you well", "Please don't hesitate to reach out")?
{compliance_instruction}

Return your evaluation as JSON:
{{
    "reasoning": "Your detailed reasoning (2-3 sentences explaining your choice)...",
    "quality_a": 1-5, "quality_b": 1-5,
    "tone_a": 1-5, "tone_b": 1-5,
    "length_a": 1-5, "length_b": 1-5,
    "effectiveness_a": 1-5, "effectiveness_b": 1-5,
    "authenticity_a": 1-5, "authenticity_b": 1-5,
    "cliche_a": 1-5, "cliche_b": 1-5,
    {compliance_json}
    "verdict": "A" | "B" | "TIE"
}}
"""

    PERSONA_CONFIGS = {
        JudgePersona.WRITING_EXPERT: {
            "description": "a **Professional Writing Expert** evaluating craft quality",
            "instructions": """
As a Writing Expert, focus on:
- Technical excellence: Is the writing mechanically sound?
- Appropriate register: Does formality match context?
- Structure and organization: Is information presented logically?
- Concision: Right length without padding or missing key points?
- Professional standards: Would this pass review in a professional setting?
- Voice: Does it sound like the stated persona would actually write this?
"""
        },
        JudgePersona.TARGET_RECIPIENT: {
            "description": f"the **Target Recipient** of this communication",
            "instructions": """
As the Target Recipient, consider:
- Clarity: Do you understand the message immediately?
- Tone: Does it feel appropriate for your relationship with the writer?
- Actionability: Can you take action based on this message?
- Authenticity: Does it feel like genuine human communication?
- Respect: Do you feel considered and respected as the audience?
- Appropriateness: Is this what you'd expect from this sender?
"""
        }
    }

    def __init__(
        self,
        client: OpenRouterClient,
        parser: JudgeResponseParser,
        judge_models: list[str],
        votes_per_judge: int = 5
    ):
        self.client = client
        self.parser = parser
        self.judge_models = judge_models
        self.votes_per_judge = votes_per_judge

    async def judge_comparison(
        self,
        prompt: WritingPrompt,
        pair: ResponsePair
    ) -> list[JudgeModelResult]:
        """
        Run full judging for one comparison.
        Each judge model evaluates with BOTH personas.
        """
        results = []

        for judge_model in self.judge_models:
            # Get results for both personas
            expert_judgments = await self._judge_with_persona(
                prompt, pair, judge_model, JudgePersona.WRITING_EXPERT
            )
            recipient_judgments = await self._judge_with_persona(
                prompt, pair, judge_model, JudgePersona.TARGET_RECIPIENT
            )

            # Aggregate per persona
            expert_result = self._aggregate_persona_judgments(expert_judgments)
            recipient_result = self._aggregate_persona_judgments(recipient_judgments)

            # Combine across personas
            combined_verdict = self._combine_persona_verdicts(
                expert_result.majority_verdict,
                recipient_result.majority_verdict
            )

            results.append(JudgeModelResult(
                judge_model_id=judge_model,
                pair_id=pair.pair_id,
                writing_expert_result=expert_result,
                target_recipient_result=recipient_result,
                combined_verdict=combined_verdict,
                personas_agree=(
                    expert_result.majority_verdict == recipient_result.majority_verdict
                )
            ))

        return results

    async def _judge_with_persona(
        self,
        prompt: WritingPrompt,
        pair: ResponsePair,
        judge_model: str,
        persona: JudgePersona
    ) -> list[SingleJudgment]:
        """Execute votes for one judge-persona combination"""
        judgments = []

        judge_prompt = self._build_judge_prompt(prompt, pair, persona)

        for vote_idx in range(self.votes_per_judge):
            try:
                response = await self.client.complete(
                    model=judge_model,
                    messages=[{"role": "user", "content": judge_prompt}],
                    temperature=0.3 + (vote_idx * 0.1),  # Slight variation
                    max_tokens=1000
                )

                parsed, warnings = self.parser.parse(
                    response.content,
                    prompt.has_instruction_constraints
                )

                judgment = self._create_judgment(
                    pair, judge_model, persona, vote_idx,
                    parsed, response.content, warnings,
                    int(response.response_time * 1000)
                )
                judgments.append(judgment)

            except Exception as e:
                logger.error(f"Judge call failed: {e}")
                # Create neutral judgment on failure
                judgments.append(self._create_fallback_judgment(
                    pair, judge_model, persona, vote_idx, str(e)
                ))

        return judgments

    def _build_judge_prompt(
        self,
        prompt: WritingPrompt,
        pair: ResponsePair,
        persona: JudgePersona
    ) -> str:
        """Build complete judge prompt with all context"""
        config = self.PERSONA_CONFIGS[persona]

        # Build optional sections
        cc_section = ""
        if prompt.cc_recipients:
            cc_section = "**CC Recipients:**\n"
            for r in prompt.cc_recipients:
                cc_section += f"- {r.name}, {r.job_title}\n"

        attachments_section = ""
        if prompt.attachments:
            attachments_section = "**Referenced Materials:**\n"
            for att in prompt.attachments:
                attachments_section += f"[{att.attachment_type.upper()}] {att.description}\n"
                attachments_section += f"{att.content_summary}\n\n"

        prior_section = ""
        if prompt.prior_messages:
            prior_section = "**Prior Message(s) in Thread:**\n"
            for msg in prompt.prior_messages:
                prior_section += f"---\n{msg}\n---\n"

        constraints_section = ""
        if prompt.explicit_constraints:
            constraints_section = "**Explicit Instructions Given:**\n"
            for c in prompt.explicit_constraints:
                constraints_section += f"- {c.constraint_text}\n"

        compliance_instruction = ""
        compliance_json = ""
        if prompt.has_instruction_constraints:
            compliance_instruction = "7. **Instruction Compliance** - Did it follow the explicit instructions given?"
            compliance_json = '"compliance_a": 1-5, "compliance_b": 1-5,'

        return self.JUDGE_PROMPT_TEMPLATE.format(
            persona_description=config["description"],
            task_statement=prompt.onet_task_statement,
            writer_name=prompt.writer.name,
            writer_title=prompt.writer.job_title,
            company_name=prompt.company.name,
            writer_age=prompt.writer.age_range,
            writer_generation=prompt.writer.generation,
            writer_skill_level=prompt.writer.skill_level,
            writer_years=prompt.writer.years_experience,
            recipient_name=prompt.primary_recipient.name,
            recipient_title=prompt.primary_recipient.job_title,
            recipient_relationship=prompt.primary_recipient.relationship_to_writer,
            recipient_familiarity=prompt.primary_recipient.familiarity,
            cc_recipients_section=cc_section,
            formality=prompt.formality_level.value,
            urgency=prompt.urgency,
            message_position=prompt.message_position.value,
            emotional_context=prompt.emotional_context.value,
            channel_section=f"- Channel: {prompt.communication_channel}" if prompt.communication_channel else "",
            attachments_section=attachments_section,
            prior_messages_section=prior_section,
            constraints_section=constraints_section,
            persona_specific_instructions=config["instructions"],
            response_a=pair.response_a.response_text[:8000],  # Truncate very long responses
            response_b=pair.response_b.response_text[:8000],
            compliance_instruction=compliance_instruction,
            compliance_json=compliance_json
        )

    def _aggregate_persona_judgments(
        self,
        judgments: list[SingleJudgment]
    ) -> PersonaJudgmentSet:
        """Aggregate votes from one persona"""
        vote_counts = {v: 0 for v in JudgeVerdict}
        for j in judgments:
            vote_counts[j.verdict] += 1

        # Majority verdict
        if vote_counts[JudgeVerdict.RESPONSE_A_WINS] >= 3:
            majority = JudgeVerdict.RESPONSE_A_WINS
        elif vote_counts[JudgeVerdict.RESPONSE_B_WINS] >= 3:
            majority = JudgeVerdict.RESPONSE_B_WINS
        else:
            majority = JudgeVerdict.TIE

        return PersonaJudgmentSet(
            judge_model_id=judgments[0].judge_model_id,
            judge_persona=judgments[0].judge_persona,
            pair_id=judgments[0].pair_id,
            individual_judgments=judgments,
            majority_verdict=majority,
            vote_counts=vote_counts,
            average_scores_a=self._average_scores([j.scores_a for j in judgments]),
            average_scores_b=self._average_scores([j.scores_b for j in judgments])
        )

    def _combine_persona_verdicts(
        self,
        expert_verdict: JudgeVerdict,
        recipient_verdict: JudgeVerdict
    ) -> JudgeVerdict:
        """Combine verdicts from both personas"""
        if expert_verdict == recipient_verdict:
            return expert_verdict
        # If they disagree, call it a tie
        return JudgeVerdict.TIE

    def _average_scores(self, scores_list: list[CriteriaScores]) -> CriteriaScores:
        """Average scores across multiple judgments"""
        n = len(scores_list)
        return CriteriaScores(
            quality=round(sum(s.quality for s in scores_list) / n),
            tone_appropriateness=round(sum(s.tone_appropriateness for s in scores_list) / n),
            length_appropriateness=round(sum(s.length_appropriateness for s in scores_list) / n),
            effectiveness=round(sum(s.effectiveness for s in scores_list) / n),
            authenticity=round(sum(s.authenticity for s in scores_list) / n),
            cliche_avoidance=round(sum(s.cliche_avoidance for s in scores_list) / n),
            instruction_compliance=(
                round(sum(s.instruction_compliance for s in scores_list if s.instruction_compliance) / n)
                if any(s.instruction_compliance for s in scores_list) else None
            )
        )
```

### 5.3 Improved Vote Aggregation

```python
class ImprovedVoteAggregator:
    """Majority-of-majorities with proper persona handling"""

    def aggregate_final_result(
        self,
        prompt: WritingPrompt,
        pair: ResponsePair,
        judge_results: list[JudgeModelResult]
    ) -> ComparisonResult:
        """Aggregate all judge results into final comparison result"""

        # Handle auto-loss cases first
        gemini_auto_loss, opponent_auto_loss = pair.has_auto_loss

        if gemini_auto_loss and not opponent_auto_loss:
            return self._create_auto_loss_result(
                prompt, pair, judge_results,
                gemini_loses=True,
                reason=f"Gemini: {pair.response_a.refusal_category.value if pair.gemini_position == 'A' else pair.response_b.refusal_category.value}"
            )
        if opponent_auto_loss and not gemini_auto_loss:
            return self._create_auto_loss_result(
                prompt, pair, judge_results,
                gemini_loses=False,
                reason=f"Opponent: {pair.response_b.refusal_category.value if pair.gemini_position == 'A' else pair.response_a.refusal_category.value}"
            )
        if gemini_auto_loss and opponent_auto_loss:
            return self._create_auto_loss_result(
                prompt, pair, judge_results,
                gemini_loses=None,  # Tie
                reason="Both models failed"
            )

        # Normal aggregation: majority of judge combined verdicts
        judges_for_a = sum(
            1 for r in judge_results
            if r.combined_verdict == JudgeVerdict.RESPONSE_A_WINS
        )
        judges_for_b = sum(
            1 for r in judge_results
            if r.combined_verdict == JudgeVerdict.RESPONSE_B_WINS
        )
        judges_tie = sum(
            1 for r in judge_results
            if r.combined_verdict == JudgeVerdict.TIE
        )

        # Final verdict
        if judges_for_a >= 2:
            final_verdict = JudgeVerdict.RESPONSE_A_WINS
        elif judges_for_b >= 2:
            final_verdict = JudgeVerdict.RESPONSE_B_WINS
        else:
            final_verdict = JudgeVerdict.TIE

        # Convert to Gemini perspective
        if pair.gemini_position == "A":
            gemini_verdict = "WIN" if final_verdict == JudgeVerdict.RESPONSE_A_WINS else \
                            "LOSS" if final_verdict == JudgeVerdict.RESPONSE_B_WINS else "TIE"
            judges_for_gemini = judges_for_a
            judges_for_opponent = judges_for_b
        else:
            gemini_verdict = "WIN" if final_verdict == JudgeVerdict.RESPONSE_B_WINS else \
                            "LOSS" if final_verdict == JudgeVerdict.RESPONSE_A_WINS else "TIE"
            judges_for_gemini = judges_for_b
            judges_for_opponent = judges_for_a

        # Calculate inter-persona agreement
        agreement_count = sum(1 for r in judge_results if r.personas_agree)
        inter_persona_agreement = agreement_count / len(judge_results)

        # Calculate total judge calls and time
        total_calls = sum(
            len(r.writing_expert_result.individual_judgments) +
            len(r.target_recipient_result.individual_judgments)
            for r in judge_results
        )
        total_time = sum(
            sum(j.response_time_ms for j in r.writing_expert_result.individual_judgments) +
            sum(j.response_time_ms for j in r.target_recipient_result.individual_judgments)
            for r in judge_results
        )

        return ComparisonResult(
            comparison_id=f"cmp_{pair.pair_id}_{int(time.time())}",
            pair_id=pair.pair_id,
            prompt_id=prompt.prompt_id,
            gemini_model_id=pair.response_a.model_id if pair.gemini_position == "A" else pair.response_b.model_id,
            opponent_model_id=pair.response_b.model_id if pair.gemini_position == "A" else pair.response_a.model_id,
            judge_results=judge_results,
            final_verdict=final_verdict,
            gemini_verdict=gemini_verdict,
            judges_for_gemini=judges_for_gemini,
            judges_for_opponent=judges_for_opponent,
            judges_tie=judges_tie,
            unanimous=(judges_for_a == 3 or judges_for_b == 3 or judges_tie == 3),
            inter_persona_agreement_rate=inter_persona_agreement,
            total_judge_calls=total_calls,
            total_judge_time_ms=total_time,
            timestamp=datetime.now()
        )
```

---

## 6. Model Registry and API Validation

**Critical Addition**: Verify model IDs before running and validate API key.

```python
class ModelRegistry:
    """Registry of OpenRouter model IDs with validation"""

    # Model ID mapping - these should be verified against OpenRouter's actual IDs
    # Updated January 2026
    MODELS = {
        # Gemini models
        "gemini_3_pro": {
            "openrouter_id": "google/gemini-2.0-flash-001",  # Placeholder - verify actual ID
            "display_name": "Gemini 3.0 Pro",
            "tier": "pro",
            "pricing": {"input": 7.0, "output": 21.0}  # per 1M tokens
        },
        "gemini_3_flash": {
            "openrouter_id": "google/gemini-2.0-flash-001",  # Placeholder - verify actual ID
            "display_name": "Gemini 3.0 Flash",
            "tier": "flash",
            "pricing": {"input": 0.35, "output": 1.05}
        },

        # Pro-tier competitors
        "gpt_5_2_thinking": {
            "openrouter_id": "openai/gpt-4-turbo",  # Placeholder - update when available
            "display_name": "GPT-5.2 Thinking",
            "tier": "pro",
            "pricing": {"input": 15.0, "output": 60.0}
        },
        "claude_opus_4_5": {
            "openrouter_id": "anthropic/claude-3-opus-20240229",  # Update to 4.5 when available
            "display_name": "Claude Opus 4.5",
            "tier": "pro",
            "pricing": {"input": 15.0, "output": 75.0}
        },
        "grok_4_1_thinking": {
            "openrouter_id": "x-ai/grok-beta",  # Placeholder
            "display_name": "Grok 4.1 Thinking",
            "tier": "pro",
            "pricing": {"input": 5.0, "output": 15.0}
        },
        "kimi_k2_thinking": {
            "openrouter_id": "moonshot/moonshot-v1-128k",  # Placeholder
            "display_name": "Kimi K2 Thinking",
            "tier": "pro",
            "pricing": {"input": 5.0, "output": 15.0}
        },

        # Flash-tier competitors
        "gpt_4_1": {
            "openrouter_id": "openai/gpt-4-turbo-preview",  # Placeholder
            "display_name": "GPT-4.1",
            "tier": "flash",
            "pricing": {"input": 2.0, "output": 8.0}
        },
        "claude_sonnet": {
            "openrouter_id": "anthropic/claude-3-sonnet-20240229",
            "display_name": "Claude Sonnet",
            "tier": "flash",
            "pricing": {"input": 3.0, "output": 15.0}
        },

        # Judge models
        "judge_opus": {
            "openrouter_id": "anthropic/claude-3-opus-20240229",
            "display_name": "Claude Opus (Judge)",
            "tier": "judge",
            "pricing": {"input": 15.0, "output": 75.0}
        },
        "judge_gpt": {
            "openrouter_id": "openai/gpt-4-turbo",
            "display_name": "GPT-4 Turbo (Judge)",
            "tier": "judge",
            "pricing": {"input": 10.0, "output": 30.0}
        },
        "judge_gemini": {
            "openrouter_id": "google/gemini-1.5-pro",
            "display_name": "Gemini 1.5 Pro (Judge)",
            "tier": "judge",
            "pricing": {"input": 3.5, "output": 10.5}
        }
    }

    @classmethod
    def get_openrouter_id(cls, model_key: str) -> str:
        """Get OpenRouter model ID for a model key"""
        if model_key not in cls.MODELS:
            raise ValueError(f"Unknown model key: {model_key}")
        return cls.MODELS[model_key]["openrouter_id"]

    @classmethod
    def get_pricing(cls, model_key: str) -> dict:
        """Get pricing for a model"""
        return cls.MODELS[model_key]["pricing"]

    @classmethod
    async def validate_models(cls, client: OpenRouterClient, model_keys: list[str]) -> dict[str, bool]:
        """Validate that models are available on OpenRouter"""
        results = {}

        # Get list of available models
        try:
            response = await client.client.get(f"{client.base_url}/models")
            available = {m["id"] for m in response.json()["data"]}
        except Exception as e:
            logger.error(f"Failed to fetch model list: {e}")
            return {k: False for k in model_keys}

        for key in model_keys:
            openrouter_id = cls.MODELS.get(key, {}).get("openrouter_id")
            results[key] = openrouter_id in available

        return results


class APIValidator:
    """Validates OpenRouter API configuration before running"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"

    async def validate(self) -> tuple[bool, list[str]]:
        """
        Validate API key and configuration.
        Returns (success, list of issues)
        """
        issues = []

        # Check API key format
        if not self.api_key or len(self.api_key) < 20:
            issues.append("API key appears invalid (too short)")
            return False, issues

        # Test API key with a simple request
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/auth/key",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0
                )

                if response.status_code == 401:
                    issues.append("API key is invalid or expired")
                    return False, issues

                if response.status_code != 200:
                    issues.append(f"API returned unexpected status: {response.status_code}")

                # Check credit balance if available
                data = response.json()
                if "data" in data and "limit_remaining" in data["data"]:
                    remaining = data["data"]["limit_remaining"]
                    if remaining is not None and remaining < 10:
                        issues.append(f"Low API credit balance: ${remaining}")

            except httpx.TimeoutException:
                issues.append("API request timed out - check network connection")
                return False, issues
            except Exception as e:
                issues.append(f"API validation failed: {str(e)}")
                return False, issues

        return len(issues) == 0, issues
```

---

## 7. Improved Checkpoint Manager

**Critical Fix**: Use async file I/O and atomic writes.

```python
import aiofiles
import tempfile
import shutil

class ImprovedCheckpointManager:
    """Async checkpoint manager with atomic writes"""

    def __init__(self, run_dir: Path, db_path: str):
        self.run_dir = Path(run_dir)
        self.db_path = db_path
        self.checkpoint_path = self.run_dir / "checkpoint.json"
        self._lock = asyncio.Lock()

    async def save_checkpoint(self, state: EvalState) -> None:
        """Save checkpoint atomically using async I/O"""
        async with self._lock:
            checkpoint = {
                "run_id": state.run_id,
                "timestamp": datetime.now().isoformat(),
                "phase": state.current_phase,
                "completed_prompts": list(state.completed_prompt_ids),
                "completed_pairs": [
                    {"prompt_id": p[0], "model_pair": p[1]}
                    for p in state.completed_pairs
                ],
                "current_prompt_index": state.current_prompt_index,
                "stats": {
                    "total_prompts": state.total_prompts,
                    "total_pairs_completed": len(state.completed_pairs),
                    "elapsed_seconds": state.elapsed_seconds,
                    "cost_so_far": state.cost_so_far
                }
            }

            # Write to temp file first (atomic)
            temp_path = self.checkpoint_path.with_suffix('.tmp')
            async with aiofiles.open(temp_path, 'w') as f:
                await f.write(json.dumps(checkpoint, indent=2))

            # Atomic rename
            shutil.move(str(temp_path), str(self.checkpoint_path))

    async def load_checkpoint(self) -> Optional[EvalState]:
        """Load checkpoint if it exists"""
        if not self.checkpoint_path.exists():
            return None

        async with aiofiles.open(self.checkpoint_path) as f:
            content = await f.read()
            checkpoint = json.loads(content)

        return EvalState(
            run_id=checkpoint["run_id"],
            current_phase=checkpoint["phase"],
            completed_prompt_ids=set(checkpoint["completed_prompts"]),
            completed_pairs={
                (p["prompt_id"], p["model_pair"])
                for p in checkpoint["completed_pairs"]
            },
            current_prompt_index=checkpoint["current_prompt_index"],
            total_prompts=checkpoint["stats"]["total_prompts"],
            elapsed_seconds=checkpoint["stats"]["elapsed_seconds"],
            cost_so_far=checkpoint["stats"]["cost_so_far"]
        )

    async def is_completed(self, prompt_id: str, model_pair: str) -> bool:
        """Check if a comparison is already completed (from DB)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 1 FROM comparison_results
                WHERE prompt_id = ?
                  AND (gemini_model_id || '_vs_' || opponent_model_id = ?
                       OR opponent_model_id || '_vs_' || gemini_model_id = ?)
                LIMIT 1
            """, (prompt_id, model_pair, model_pair))
            return await cursor.fetchone() is not None

    async def save_result_atomic(self, result: ComparisonResult) -> None:
        """Save comparison result with transaction"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                # Save comparison result
                await db.execute("""
                    INSERT OR REPLACE INTO comparison_results
                    (comparison_id, pair_id, prompt_id, gemini_model_id,
                     opponent_model_id, final_verdict, gemini_verdict,
                     judges_for_gemini, judges_for_opponent, judges_tie,
                     unanimous, inter_persona_agreement, gemini_auto_loss,
                     opponent_auto_loss, auto_loss_reason, total_judge_calls,
                     total_judge_time_ms, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.comparison_id, result.pair_id, result.prompt_id,
                    result.gemini_model_id, result.opponent_model_id,
                    result.final_verdict.value, result.gemini_verdict,
                    result.judges_for_gemini, result.judges_for_opponent,
                    result.judges_tie, result.unanimous,
                    result.inter_persona_agreement_rate,
                    result.gemini_auto_loss, result.opponent_auto_loss,
                    result.auto_loss_reason, result.total_judge_calls,
                    result.total_judge_time_ms, result.timestamp.isoformat()
                ))

                # Save individual judgments
                for judge_result in result.judge_results:
                    for persona_result in [
                        judge_result.writing_expert_result,
                        judge_result.target_recipient_result
                    ]:
                        for judgment in persona_result.individual_judgments:
                            await db.execute("""
                                INSERT OR REPLACE INTO judgments
                                (judgment_id, pair_id, judge_model_id, judge_persona,
                                 vote_index, verdict, reasoning, quality_score_a,
                                 quality_score_b, tone_a, tone_b, length_a, length_b,
                                 effectiveness_a, effectiveness_b, authenticity_a,
                                 authenticity_b, cliche_a, cliche_b, compliance_a,
                                 compliance_b, response_time_ms, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                judgment.judgment_id, judgment.pair_id,
                                judgment.judge_model_id, judgment.judge_persona.value,
                                judgment.vote_index, judgment.verdict.value,
                                judgment.reasoning,
                                judgment.scores_a.quality, judgment.scores_b.quality,
                                judgment.scores_a.tone_appropriateness,
                                judgment.scores_b.tone_appropriateness,
                                judgment.scores_a.length_appropriateness,
                                judgment.scores_b.length_appropriateness,
                                judgment.scores_a.effectiveness,
                                judgment.scores_b.effectiveness,
                                judgment.scores_a.authenticity,
                                judgment.scores_b.authenticity,
                                judgment.scores_a.cliche_avoidance,
                                judgment.scores_b.cliche_avoidance,
                                judgment.scores_a.instruction_compliance,
                                judgment.scores_b.instruction_compliance,
                                judgment.response_time_ms,
                                judgment.timestamp.isoformat()
                            ))

                await db.execute("COMMIT")

            except Exception as e:
                await db.execute("ROLLBACK")
                raise
```

---

## 8. Improved Cost Estimation

**Critical Fix**: Use distributions instead of fixed estimates.

```python
class ImprovedCostEstimator:
    """Cost estimation with variance and confidence ranges"""

    # Token statistics from empirical data
    TOKEN_DISTRIBUTIONS = {
        "prompt": {"mean": 1500, "std": 500, "min": 500, "max": 4000},
        "response": {"mean": 800, "std": 400, "min": 100, "max": 3000},
        "judge_prompt": {"mean": 3500, "std": 800, "min": 2000, "max": 6000},
        "judge_response": {"mean": 400, "std": 150, "min": 150, "max": 1000},
    }

    def estimate(
        self,
        config: EvalConfig,
        confidence_level: float = 0.9
    ) -> CostEstimate:
        """Estimate costs with confidence intervals"""

        num_prompts = config.sampling_config.num_prompts
        num_model_pairs = self._count_model_pairs(config)
        num_judges = len(config.judge_config.judge_models)
        votes_per_judge = config.judge_config.votes_per_judge
        num_personas = 2  # Always both personas

        # Calculate expected token counts with variance
        response_calls = num_prompts * num_model_pairs * 2
        judge_calls = num_prompts * num_model_pairs * num_judges * votes_per_judge * num_personas

        # Monte Carlo simulation for cost distribution
        costs = self._simulate_costs(
            response_calls=response_calls,
            judge_calls=judge_calls,
            config=config,
            n_simulations=1000
        )

        # Calculate percentiles
        sorted_costs = sorted(costs)
        low_idx = int((1 - confidence_level) / 2 * len(costs))
        high_idx = int((1 + confidence_level) / 2 * len(costs))

        mean_cost = sum(costs) / len(costs)
        low_cost = sorted_costs[low_idx]
        high_cost = sorted_costs[high_idx]

        # Time estimation
        avg_response_time = 3.0
        avg_judge_time = 1.5
        parallelism = config.max_concurrent_requests

        # Account for rate limits
        rate_limit_factor = self._estimate_rate_limit_factor(
            response_calls + judge_calls,
            parallelism
        )

        sequential_time = (
            response_calls * avg_response_time +
            judge_calls * avg_judge_time
        )
        parallel_time = (sequential_time / parallelism) * rate_limit_factor

        return CostEstimate(
            total_prompts=num_prompts,
            model_pairs=num_model_pairs,
            total_comparisons=num_prompts * num_model_pairs,
            total_response_calls=response_calls,
            total_judge_calls=judge_calls,
            total_cost_mean=mean_cost,
            total_cost_low=low_cost,
            total_cost_high=high_cost,
            confidence_level=confidence_level,
            estimated_time_parallel_hours=parallel_time / 3600,
            estimated_time_sequential_hours=sequential_time / 3600
        )

    def _simulate_costs(
        self,
        response_calls: int,
        judge_calls: int,
        config: EvalConfig,
        n_simulations: int
    ) -> list[float]:
        """Monte Carlo simulation of total costs"""
        rng = random.Random(42)
        costs = []

        for _ in range(n_simulations):
            total = 0.0

            # Response costs
            for _ in range(response_calls):
                input_tokens = max(
                    self.TOKEN_DISTRIBUTIONS["prompt"]["min"],
                    rng.gauss(
                        self.TOKEN_DISTRIBUTIONS["prompt"]["mean"],
                        self.TOKEN_DISTRIBUTIONS["prompt"]["std"]
                    )
                )
                output_tokens = max(
                    self.TOKEN_DISTRIBUTIONS["response"]["min"],
                    rng.gauss(
                        self.TOKEN_DISTRIBUTIONS["response"]["mean"],
                        self.TOKEN_DISTRIBUTIONS["response"]["std"]
                    )
                )

                # Use average pricing across models
                total += (input_tokens * 5.0 + output_tokens * 20.0) / 1_000_000

            # Judge costs
            for _ in range(judge_calls):
                input_tokens = max(
                    self.TOKEN_DISTRIBUTIONS["judge_prompt"]["min"],
                    rng.gauss(
                        self.TOKEN_DISTRIBUTIONS["judge_prompt"]["mean"],
                        self.TOKEN_DISTRIBUTIONS["judge_prompt"]["std"]
                    )
                )
                output_tokens = max(
                    self.TOKEN_DISTRIBUTIONS["judge_response"]["min"],
                    rng.gauss(
                        self.TOKEN_DISTRIBUTIONS["judge_response"]["mean"],
                        self.TOKEN_DISTRIBUTIONS["judge_response"]["std"]
                    )
                )

                total += (input_tokens * 10.0 + output_tokens * 40.0) / 1_000_000

            costs.append(total)

        return costs

    def _estimate_rate_limit_factor(
        self,
        total_calls: int,
        parallelism: int
    ) -> float:
        """Estimate slowdown factor due to rate limits"""
        # Assume ~60 requests per minute limit
        expected_calls_per_minute = parallelism * 20  # 3s avg response time

        if expected_calls_per_minute <= 60:
            return 1.0
        else:
            # Slowdown proportional to how much we exceed the limit
            return expected_calls_per_minute / 60

    def _count_model_pairs(self, config: EvalConfig) -> int:
        """Count total model pairs"""
        count = 0
        if config.run_pro_tier:
            count += len(config.pro_tier_opponents)
        if config.run_flash_tier:
            count += len(config.flash_tier_opponents)
        return count
```

---

## 9. Updated Presets with Correct Judge Call Counts

**Critical Fix**: Account for dual personas in judge call calculations.

```python
# Corrected preset definitions
# Note: With dual personas, each comparison requires:
# judges * personas * votes = 3 * 2 * 5 = 30 judge calls per comparison

EVAL_PRESETS = {
    1: EvalPreset(
        name="Sanity Check",
        description="Does the system work?",
        prompts=5,
        model_pairs=1,
        judges=1,
        votes=1,
        personas=2,
        estimated_cost_range=(2, 5),  # Corrected
        estimated_time_minutes=5
    ),
    2: EvalPreset(
        name="Smoke Test",
        description="Quick functionality test",
        prompts=20,
        model_pairs=1,
        judges=1,
        votes=3,
        personas=2,
        estimated_cost_range=(10, 20),
        estimated_time_minutes=10
    ),
    3: EvalPreset(
        name="Dev Iteration",
        description="Development/debugging",
        prompts=50,
        model_pairs=2,
        judges=2,
        votes=3,
        personas=2,
        estimated_cost_range=(40, 80),
        estimated_time_minutes=30
    ),
    4: EvalPreset(
        name="Quick Sample",
        description="Fast directional signal",
        prompts=100,
        model_pairs=2,
        judges=2,
        votes=5,
        personas=2,
        estimated_cost_range=(100, 200),
        estimated_time_minutes=60
    ),
    5: EvalPreset(
        name="Light Eval",
        description="Light but meaningful eval",
        prompts=200,
        model_pairs=3,
        judges=3,
        votes=3,
        personas=2,
        estimated_cost_range=(200, 400),
        estimated_time_minutes=120
    ),
    6: EvalPreset(
        name="Standard Eval",
        description="Standard evaluation run",
        prompts=500,
        model_pairs=4,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost_range=(700, 1200),
        estimated_time_minutes=240
    ),
    7: EvalPreset(
        name="Thorough Eval",
        description="Thorough with good power",
        prompts=1000,
        model_pairs=4,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost_range=(1500, 2500),
        estimated_time_minutes=480
    ),
    8: EvalPreset(
        name="Comprehensive",
        description="High statistical power",
        prompts=2000,
        model_pairs=6,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost_range=(4000, 6000),
        estimated_time_minutes=900
    ),
    9: EvalPreset(
        name="Deep Dive",
        description="Publication-grade",
        prompts=5000,
        model_pairs=6,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost_range=(10000, 15000),
        estimated_time_minutes=1800
    ),
    10: EvalPreset(
        name="Full Kaboodle",
        description="Maximum coverage",
        prompts=10000,
        model_pairs=6,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost_range=(20000, 30000),
        estimated_time_minutes=3600
    )
}
```

---

## 10. Implementation Timeline - Revised

### Phase 1: Foundation (Week 1)
- Set up project structure with proper packaging
- Implement core data models with validation
- Build O*NET schema validator and extractor
- Create OpenRouter client with API validation
- Write unit tests for core components

### Phase 2: Prompt Pipeline (Week 2)
- Implement LLM-assisted company generation
- Build improved stratified sampling
- Create scenario generators (revision, tone matching, etc.)
- Implement persona generation
- Build prompt assembler with all scenario types
- Write integration tests for prompt pipeline

### Phase 3: Evaluation Core (Week 3)
- Build response collector with format analysis
- Implement robust judge parser
- Create dual-persona judge module
- Build vote aggregator with auto-loss handling
- Implement async checkpoint manager
- Write tests for judging logic

### Phase 4: Analysis & Reporting (Week 4)
- Implement analysis engine with all metrics
- Build statistical tests with proper null hypotheses
- Create weakness analyzer
- Build chart generation with Plotly
- Create PDF report generator
- Write analysis tests

### Phase 5: TUI & CLI (Week 5)
- Build progress dashboard with Textual
- Implement results browser
- Create CLI with Typer
- Add cross-run comparison
- End-to-end integration testing

### Phase 6: Validation & Polish (Week 6)
- Run small-scale evaluations
- Validate statistical methods
- Tune cost estimates against real data
- Performance optimization
- Documentation and examples

---

## 11. Key Improvements Summary

| Area | Draft 5 Issue | Improvement |
|------|--------------|-------------|
| O*NET Schema | Assumed table/column names | Schema validation before queries |
| Company Generation | Hardcoded static database | LLM-assisted dynamic generation |
| Judge Parsing | No error handling | Robust parser with fallbacks |
| Dual Personas | Not properly integrated | Full dual-persona evaluation |
| Sampling | Too rigid for small sizes | Adaptive strategy based on n |
| Checkpointing | Sync file I/O | Async with atomic writes |
| Cost Estimation | Fixed token counts | Monte Carlo with distributions |
| Model IDs | Speculative | Registry with validation |
| API Validation | None | Pre-flight checks |
| Scenario Types | Missing implementations | Full coverage of PROMPT.md requirements |

---

## 12. Success Criteria - Updated

1. **Schema Safety**: All O*NET queries validated against actual schema
2. **Reproducibility**: Given same seed and config, produces identical prompts
3. **Robustness**: Handles all API failure modes, malformed JSON, partial responses
4. **Statistical Validity**: All win rates include proper confidence intervals
5. **Dual Persona Coverage**: Every comparison judged by both personas
6. **Diversity Coverage**: All scenario types from PROMPT.md implemented
7. **Cost Accuracy**: Estimates within 20% of actual costs
8. **Resumability**: Can resume from any failure point
9. **Usability**: Clear CLI, informative TUI, comprehensive reports
10. **Transparency**: Full audit trail of all judgments and reasoning
