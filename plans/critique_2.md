# Critique of Draft Plan 2: Gemini Writing Evaluation Framework

## Executive Summary

Draft Plan 2 presents a comprehensive and well-structured implementation plan for the Gemini Writing Evaluation Framework. The plan demonstrates strong architectural thinking with detailed code examples, clear module organization, and attention to the core requirements in PROMPT.md. However, there are several areas requiring improvement, including missing specifications, technical inaccuracies, and gaps in robustness handling.

---

## Detailed Critique

### 1. Strengths of the Draft Plan

#### 1.1 Excellent Architecture
- Clean separation of concerns with well-defined modules (API, config, data, eval, storage, TUI, analysis, reports)
- Comprehensive Pydantic schemas covering all major data models
- Proper use of async/await patterns for API interactions
- Good use of modern Python tooling (httpx, pydantic, rich, textual)

#### 1.2 Strong O*NET Integration
- Detailed SQL queries for extracting writing-relevant tasks
- Good categorization of writing types (explicit_writing, correspondence, reports_presentations, etc.)
- SOC major group mapping is complete and accurate

#### 1.3 Good Checkpoint System
- Atomic writes with temp file and rename pattern
- State serialization with proper set/list conversion for JSON
- Progress tracking at multiple granularities (prompts, comparisons)

#### 1.4 Comprehensive Statistical Analysis
- Wilson score confidence intervals (correct choice for proportions)
- Position bias detection
- Length bias correlation analysis
- Cohen's Kappa for inter-judge agreement
- Effect size calculation using Cohen's h

---

### 2. Critical Issues and Missing Requirements

#### 2.1 Missing Dual Judge Personas Implementation
**PROMPT.md Requirement:** "Responses should be judged by both: 1) Simulated Writing Expert 2) Simulated Target Recipient"

**Issue:** While the plan mentions dual personas and includes them in schemas, the actual evaluation loop in `EvaluationEngine.evaluate_prompt()` iterates over `judge_config.personas` but doesn't properly separate the voting logic. The votes from both personas for the same judge model get mixed together in the majority calculation. The aggregation should first compute majority per persona per judge, then aggregate.

**Severity:** High

#### 2.2 Incomplete Majority-of-Majorities Implementation
**PROMPT.md Requirement:** "Each judge model gives best-of-5 votes independently. Then take the majority across the 3 judges."

**Issue:** The current `_aggregate_votes` implementation groups by judge model but doesn't properly handle the per-persona voting. It should be:
1. Claude Writing Expert: 5 votes → majority
2. Claude Target Recipient: 5 votes → majority
3. GPT Writing Expert: 5 votes → majority
... and so on

The current implementation would incorrectly mix persona votes.

**Severity:** High

#### 2.3 Missing Response Constraints: Natural (No Constraints)
**PROMPT.md Requirement:** "Let models decide appropriate length and format for each task. Do not enforce word counts or format requirements."

**Issue:** The plan doesn't explicitly ensure that model prompts avoid enforcing constraints. The `_build_model_prompt` method should explicitly avoid adding length/format requirements unless they come from explicit `InstructionConstraint` entries meant to test instruction following.

**Severity:** Medium

#### 2.4 Missing Tone Matching from Examples
**PROMPT.md Requirement:** "Some prompts should include prior writing samples to match: 'Here's how Sarah typically writes to clients: [example]. Draft a similar message for...'"

**Issue:** The `WritingPrompt` schema has `tone_example: Optional[str]` but the prompt generation never populates this field. There's no logic to generate tone examples or integrate them into the Phase 3 LLM enrichment.

**Severity:** Medium

#### 2.5 Missing Revision & Editing Tasks
**PROMPT.md Requirement:** "Include prompts where the model must improve existing text: 'Revise this draft to be more concise: [draft]'"

**Issue:** There's no mechanism to generate editing/revision tasks. This is a distinct task type that should be tracked separately in analysis.

**Severity:** Medium

#### 2.6 Missing Ambiguity Handling Tracking
**PROMPT.md Requirement:** "Include some deliberately vague prompts to test how models handle uncertainty... Track model behavior: Does it make reasonable assumptions? Does it ask for clarification?"

**Issue:** While the schema has fields for attachments and context, there's no mechanism to generate deliberately ambiguous prompts or track how models respond to ambiguity.

**Severity:** Medium

#### 2.7 Incomplete Communication Channel Handling
**PROMPT.md Requirement:** "Let O*NET task statements imply the medium naturally... Track channel as metadata for analysis"

**Issue:** The `_infer_channel` method is too simplistic and only checks for basic keywords. The Phase 3 LLM enrichment should be explicitly tasked with inferring the appropriate channel when ambiguous.

**Severity:** Low

---

### 3. Technical Errors and Bugs

#### 3.1 Incorrect scipy Function Usage
```python
p_value = stats.binom_test(wins, n, 0.5, alternative='two-sided')
```
**Issue:** `scipy.stats.binom_test` is deprecated since SciPy 1.10. Should use `scipy.stats.binomtest().pvalue` instead.

#### 3.2 Incorrect Cohen's Kappa Call
```python
kappa = stats.cohens_kappa(ratings1, ratings2)
```
**Issue:** There's no `cohens_kappa` function in scipy.stats. The correct approach is to use `sklearn.metrics.cohen_kappa_score` or implement manually.

#### 3.3 Missing Import in Evaluation Engine
```python
from .judge_prompts import build_judge_prompt
```
**Issue:** The file path should be `from ..eval.judge_prompts import build_judge_prompt` if called from within eval package, or the import structure is inconsistent.

#### 3.4 Database Column Count Mismatch
The `insert_vote` method has 25 placeholder `?` marks but the `JudgeVote` schema may have different field counts. The SQL needs to be verified against the actual schema.

#### 3.5 Missing Error Handling in Response Generation
```python
except Exception as e:
    logger.error(f"Failed to generate response for {model_id}: {e}")
    return ModelResponse(...)
```
**Issue:** Catching bare `Exception` is too broad. Should catch specific exceptions (httpx exceptions, API errors) and re-raise unexpected ones.

---

### 4. Missing PROMPT.md Requirements

#### 4.1 Multiple Recipients (CC Situations)
**PROMPT.md Requirement:** "Include scenarios with multiple audiences simultaneously: Email to client, CC'd to your boss"

**Status:** Not implemented. Schema doesn't support multiple recipients.

#### 4.2 Instruction-Following Tests with Specific Constraints
**PROMPT.md Requirement:** "Include some prompts with explicit constraints to test instruction-following: Length constraints, Format requirements, Tone directives, Exclusions"

**Status:** Schema has `InstructionConstraint` but no generation logic populates it.

#### 4.3 Cross-Run Comparison Implementation
**PROMPT.md Requirement:** "Support comparing results across multiple runs"

**Status:** CLI has stub but no implementation.

#### 4.4 Fine-Grained Eval Viewer TUI
**PROMPT.md Requirement:** "Build a full interactive terminal UI using the rich/textual library with: Filtering by occupation, industry, winner, etc."

**Status:** Only the progress dashboard is implemented. The results viewer TUI is a stub.

#### 4.5 Heatmaps by Dimension/Occupation
**PROMPT.md Requirement:** "Heatmaps by dimension/occupation"

**Status:** `_generate_heatmap` method exists but has `pass` implementation.

#### 4.6 Results Directory Structure
**PROMPT.md Requirement:** Detailed directory structure with prompts_by_occupation, prompts_by_industry, by_prompt, by_model organization.

**Status:** The plan only creates a flat structure. Missing the organized subdirectories specified in PROMPT.md.

#### 4.7 Config Summary Text File
**PROMPT.md Requirement:** "config_summary.txt - Human-readable config summary"

**Status:** Not implemented.

#### 4.8 Random Seed File
**PROMPT.md Requirement:** "random_seed.txt - Seed for reproducibility"

**Status:** Not explicitly saved as separate file.

#### 4.9 README Auto-Generation
**PROMPT.md Requirement:** "README.md - Auto-generated run description"

**Status:** Not implemented.

---

### 5. Robustness and Error Handling Gaps

#### 5.1 Circuit Breaker Recovery
The circuit breaker opens after 5 failures but the recovery logic doesn't verify the API is actually working before closing. Should include a health check.

#### 5.2 No Graceful Shutdown Handler
**PROMPT.md Requirement:** "Graceful shutdown: Ctrl+C saves state and can resume"

**Status:** No signal handler for SIGINT/SIGTERM to ensure checkpoint is saved on interrupt.

#### 5.3 Missing Failure Logging
**PROMPT.md Requirement:** "Failure logging: Track all failures with full context for debugging"

**Status:** Errors are logged but there's no dedicated `failures.log` file being written as specified in the directory structure.

#### 5.4 No Transaction Handling for Database Writes
Multiple related inserts (response_a, response_b, comparison, votes) should be wrapped in a transaction to ensure atomicity.

---

### 6. Design and Architecture Issues

#### 6.1 Phase 1 vs Phase 2 Generation Confusion
The plan conflates Phase 1 (Offline LLM Generation) and Phase 2 (Algorithmic Combinations). The `generate_prompt_phase1` method is actually doing Phase 2 work. Phase 1 should be a separate preprocessing step that generates diverse variations using LLM.

#### 6.2 Company Database is Too Limited
The hardcoded company database has only ~20 companies. For 10,000+ prompts, this will cause significant repetition. Need either:
- Much larger embedded database
- LLM-generated companies during Phase 1
- Integration with external company data source

#### 6.3 Missing Sensitive Topic Generation
While detection is implemented, there's no mechanism to intentionally generate prompts covering sensitive topics to ensure balanced coverage.

#### 6.4 TUI Dashboard Not Properly Integrated
The `EvalDashboard.run()` is called but the actual evaluation loop `evaluation_loop()` is defined but never awaited or run alongside the dashboard.

---

## Improved Plan

The following sections present an improved version of the draft plan addressing all identified issues.

---

# Improved Implementation Plan: Gemini Writing Evaluation Framework

## 1. System Architecture Overview (Improved)

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GEMINI WRITING EVAL FRAMEWORK                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   CLI/CONFIG    │───▶│  ORCHESTRATOR   │───▶│   TUI DISPLAY   │          │
│  │    MANAGER      │    │     ENGINE      │    │    (Rich)       │          │
│  └─────────────────┘    └────────┬────────┘    └─────────────────┘          │
│                                  │                                           │
│         ┌────────────────────────┼────────────────────────────┐             │
│         ▼                        ▼                            ▼             │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐          │
│  │   PROMPT     │    │    EVALUATION     │    │    ANALYSIS &    │          │
│  │  GENERATION  │    │      ENGINE       │    │    REPORTING     │          │
│  │   PIPELINE   │    │                   │    │                  │          │
│  └──────┬───────┘    └────────┬──────────┘    └────────┬─────────┘          │
│         │                     │                        │                     │
│         ▼                     ▼                        ▼                     │
│  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐          │
│  │   O*NET DB   │    │   OPENROUTER      │    │    RESULTS DB    │          │
│  │  + NAICS +   │    │   API CLIENT      │    │    (SQLite)      │          │
│  │  COMPANIES   │    │   + FAILOVER      │    │                  │          │
│  └──────────────┘    └───────────────────┘    └──────────────────┘          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    SIGNAL HANDLER / GRACEFUL SHUTDOWN                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Components (Enhanced)

| Component | Responsibility | Key Dependencies |
|-----------|---------------|------------------|
| CLI/Config Manager | User configuration, presets, dry-run estimates | Click/Typer, Pydantic |
| Orchestrator Engine | Workflow coordination, checkpointing, resumption, **signal handling** | asyncio, State Machine |
| Prompt Generation Pipeline | O*NET extraction, **three-phase generation**, diversity sampling | SQLite, HTTPX |
| Evaluation Engine | Model invocation, judging, **per-persona voting**, vote aggregation | OpenRouter API |
| TUI Display | Real-time progress visualization, **results viewer** | Rich/Textual |
| Analysis & Reporting | Statistics, weakness detection, **heatmaps**, PDF generation | Pandas, Plotly, ReportLab |
| Results DB | Persistent storage, querying, exports, **transactional writes** | SQLite |
| Signal Handler | **Graceful shutdown on Ctrl+C/SIGTERM** | signal module |

### 1.3 Technology Stack (Corrected)

```python
# Core Framework
python = ">=3.11"
asyncio        # Async I/O for concurrent API calls
httpx          # Modern async HTTP client
pydantic       # Data validation and settings

# Data & Storage
sqlite3        # Results database (built-in)
pandas         # Data analysis
numpy          # Numerical operations
scipy          # Statistical testing (use binomtest, not binom_test)

# UI & Visualization
rich           # Terminal formatting and progress
textual        # Full TUI application
plotly         # Interactive charts (use kaleido for image export)
reportlab      # PDF generation

# ML/Statistics
scikit-learn   # For cohen_kappa_score

# CLI
typer          # CLI framework with type hints

# Testing
pytest         # Test framework
pytest-asyncio # Async test support
pytest-cov     # Coverage reporting
```

---

## 2. Data Models and Schemas (Corrected and Enhanced)

### 2.1 Enhanced Prompt Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime
from enum import Enum

# Additional task type for revision/editing
class TaskType(str, Enum):
    """Type of writing task"""
    GENERATION = "generation"      # Write from scratch
    REVISION = "revision"          # Improve existing text
    REPLY = "reply"                # Respond to message
    EDITING = "editing"            # Edit for specific quality

class AmbiguityLevel(str, Enum):
    """Intentional ambiguity level for testing"""
    CLEAR = "clear"
    SLIGHTLY_AMBIGUOUS = "slightly_ambiguous"
    DELIBERATELY_VAGUE = "deliberately_vague"

class RecipientPersona(BaseModel):
    """Complete recipient/reader specification - supports multiple recipients"""
    primary_recipient: 'SingleRecipient'
    cc_recipients: List['SingleRecipient'] = []  # For CC situations
    audience_notes: Optional[str] = None  # e.g., "Will be forwarded to executives"

class SingleRecipient(BaseModel):
    """Single recipient specification"""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship: Literal["superior", "peer", "subordinate", "external", "public"]
    familiarity: Literal["first_contact", "acquaintance", "established", "close"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    technical_level: Literal["non_technical", "somewhat_technical", "technical", "expert"]

class WritingPrompt(BaseModel):
    """Complete writing prompt specification - ENHANCED"""
    prompt_id: str

    # O*NET source
    onet_task_id: str
    onet_task_text: str
    occupation_code: str
    occupation_title: str
    job_zone: JobZone
    soc_major_group: str

    # Enriched prompt
    prompt_text: str

    # Task type - NEW
    task_type: TaskType = TaskType.GENERATION

    # For revision/editing tasks - NEW
    original_draft: Optional[str] = None
    revision_instruction: Optional[str] = None

    # Context dimensions
    writer: WriterPersona
    recipients: RecipientPersona  # Changed to support multiple
    company: CompanyContext

    # Communication context
    formality_level: int = Field(ge=1, le=5)
    urgency_level: int = Field(ge=1, le=5)
    audience_size: Literal["one_on_one", "small_group", "department", "company_wide", "public"]
    message_position: MessagePosition
    emotional_context: EmotionalContext

    # Optional enrichments
    temporal_context: Optional[str] = None
    attachments: list[AttachmentReference] = []
    reply_context: Optional[str] = None
    tone_example: Optional[str] = None  # Sample writing to match
    competing_objectives: Optional[str] = None
    constraints: list[InstructionConstraint] = []

    # Ambiguity tracking - NEW
    ambiguity_level: AmbiguityLevel = AmbiguityLevel.CLEAR
    deliberately_missing: List[str] = []  # What info is intentionally omitted

    # Metadata
    inferred_channel: Optional[str] = None
    writing_category: str
    sensitive_topic: Optional[str] = None
    language: str = "en"
    language_variant: str = "en-US"

    # Generation metadata
    generation_phase: Literal["phase1_llm", "phase2_algorithmic", "phase3_enriched"]
    random_seed: int
    created_at: datetime
```

### 2.2 Enhanced Judge Vote Schema with Per-Persona Tracking

```python
class JudgeVote(BaseModel):
    """Single vote from a judge - per persona"""
    vote_id: str
    comparison_id: str
    judge_model: str
    judge_persona: Literal["writing_expert", "target_recipient"]
    vote_number: int  # 1-5 for best-of-5

    # Verdict
    winner: Literal["model_a", "model_b", "tie"]
    confidence: int = Field(ge=1, le=5)

    # Reasoning
    reasoning: str

    # Criteria scores (1-5 scale)
    quality_score_a: int = Field(ge=1, le=5)
    quality_score_b: int = Field(ge=1, le=5)
    length_appropriateness_a: int = Field(ge=1, le=5)
    length_appropriateness_b: int = Field(ge=1, le=5)
    tone_appropriateness_a: int = Field(ge=1, le=5)
    tone_appropriateness_b: int = Field(ge=1, le=5)
    effectiveness_a: int = Field(ge=1, le=5)
    effectiveness_b: int = Field(ge=1, le=5)
    clarity_a: int = Field(ge=1, le=5)
    clarity_b: int = Field(ge=1, le=5)
    task_completion_a: int = Field(ge=1, le=5)
    task_completion_b: int = Field(ge=1, le=5)
    authenticity_a: int = Field(ge=1, le=5)
    authenticity_b: int = Field(ge=1, le=5)
    cliche_avoidance_a: int = Field(ge=1, le=5)
    cliche_avoidance_b: int = Field(ge=1, le=5)

    # Instruction following (if applicable)
    instruction_compliance_a: Optional[int] = Field(default=None, ge=1, le=5)
    instruction_compliance_b: Optional[int] = Field(default=None, ge=1, le=5)

    # Position tracking for bias detection
    model_a_position: Literal["first", "second"]

    created_at: datetime

class PerJudgePersonaVerdict(BaseModel):
    """Aggregated verdict per judge per persona"""
    judge_model: str
    persona: Literal["writing_expert", "target_recipient"]
    votes: List[JudgeVote]
    majority_winner: Literal["model_a", "model_b", "tie"]
    vote_count_a: int
    vote_count_b: int
    vote_count_tie: int

class Comparison(BaseModel):
    """Complete comparison between two models - CORRECTED aggregation"""
    comparison_id: str
    prompt_id: str

    # Models
    model_a_id: str
    model_b_id: str
    model_a_name: str
    model_b_name: str

    # Responses
    response_a_id: str
    response_b_id: str

    # All individual votes
    votes: list[JudgeVote]

    # Per-judge per-persona verdicts - NEW
    judge_persona_verdicts: List[PerJudgePersonaVerdict]

    # Aggregated results per judge model (majority of both personas)
    claude_verdict: Optional[Literal["model_a", "model_b", "tie"]] = None
    gpt_verdict: Optional[Literal["model_a", "model_b", "tie"]] = None
    gemini_verdict: Optional[Literal["model_a", "model_b", "tie"]] = None

    # Final aggregated result (majority of judge verdicts)
    final_winner: Optional[Literal["model_a", "model_b", "tie"]] = None
    gemini_won: Optional[bool] = None

    # Metadata
    presentation_order_seed: int
    created_at: datetime
```

---

## 3. Three-Phase Prompt Generation (Corrected)

### 3.1 Phase 1: Offline LLM Generation (Properly Separated)

Phase 1 should be a **preprocessing step** that generates diverse variations BEFORE the main evaluation run.

```python
# src/prompts/phase1_generator.py

import asyncio
import json
from pathlib import Path
from typing import List, Dict
import random

class Phase1Generator:
    """
    Phase 1: Offline LLM generation of diverse prompt variations.
    This runs BEFORE the main evaluation as a preprocessing step.
    Uses the SAME models being evaluated to avoid bias.
    """

    def __init__(self, openrouter_client, output_dir: Path):
        self.client = openrouter_client
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_persona_variations(self,
                                          onet_task: str,
                                          occupation: str,
                                          num_variations: int = 5) -> List[Dict]:
        """Generate diverse persona/context variations for a task"""

        prompt = f"""
Generate {num_variations} highly diverse writing scenario variations for this O*NET task.

O*NET Task: "{onet_task}"
Occupation: {occupation}

For each variation, provide completely different:
1. Writer persona (vary age/generation, experience level, personality)
2. Recipient persona (vary relationship, familiarity, technical level)
3. Company context (vary size from startup to enterprise, industry)
4. Emotional context (routine, urgent, celebratory, difficult conversation)
5. Communication channel if not explicit in task

Make variations as DIVERSE as possible:
- One Gen Z junior employee, one Boomer executive
- One first email ever, one established relationship
- One 5-person startup, one Fortune 500
- Include at least one with competing objectives
- Include at least one that would benefit from temporal context

Return as JSON array with fields:
- writer: {{name, generation, years_exp, skill_level, personality_notes}}
- recipient: {{name, title, relationship, familiarity, tech_level}}
- company: {{name, size, industry, public_private}}
- emotional_context: string
- urgency: 1-5
- formality: 1-5
- special_elements: [list of any special requirements like "include attachment reference", "CC situation", "tone example needed"]
"""

        # Use multiple models to avoid model-specific bias
        models = [
            "google/gemini-3.0-pro",
            "anthropic/claude-sonnet-4",
            "openai/gpt-4.1"
        ]

        all_variations = []
        for model in models:
            try:
                response = await self.client.complete(
                    model=model,
                    prompt=prompt,
                    max_tokens=2000,
                    temperature=0.9  # High temperature for diversity
                )
                variations = json.loads(response.text)
                all_variations.extend(variations)
            except Exception as e:
                print(f"Warning: Failed to get variations from {model}: {e}")

        return all_variations

    async def generate_revision_drafts(self,
                                       onet_task: str,
                                       num_drafts: int = 3) -> List[Dict]:
        """Generate drafts that need revision for editing tasks"""

        prompt = f"""
Generate {num_drafts} different FLAWED writing drafts that need revision.

Based on this O*NET task: "{onet_task}"

For each draft, create a realistic but flawed piece of writing with ONE clear issue:
1. Draft that is too long and needs to be more concise
2. Draft that is too informal and needs to be more professional
3. Draft that is too harsh and needs to be softened
4. Draft that lacks detail and needs more substance
5. Draft that has poor structure and needs reorganization

Return as JSON array:
[
  {{
    "draft_text": "The actual flawed draft...",
    "issue_type": "too_long|too_informal|too_harsh|lacks_detail|poor_structure",
    "revision_instruction": "Make this more concise" or similar
  }}
]
"""

        response = await self.client.complete(
            model="anthropic/claude-sonnet-4",
            prompt=prompt,
            max_tokens=3000,
            temperature=0.8
        )

        return json.loads(response.text)

    async def generate_tone_examples(self,
                                     company_type: str,
                                     num_examples: int = 3) -> List[str]:
        """Generate sample writing to use as tone examples"""

        prompt = f"""
Generate {num_examples} short sample emails showing different writing tones for a {company_type}.

These will be used as "match this tone" examples.

Include variety:
1. Very formal, corporate tone
2. Casual, friendly startup tone
3. Direct, no-nonsense tone

Return as JSON array of strings, each ~100-150 words.
"""

        response = await self.client.complete(
            model="google/gemini-3.0-pro",
            prompt=prompt,
            max_tokens=1500,
            temperature=0.7
        )

        return json.loads(response.text)

    async def generate_ambiguous_prompts(self,
                                         onet_task: str,
                                         num_prompts: int = 3) -> List[Dict]:
        """Generate deliberately vague prompts to test ambiguity handling"""

        prompt = f"""
Based on this O*NET task: "{onet_task}"

Generate {num_prompts} deliberately VAGUE writing prompts that test how models handle ambiguity.

Types of ambiguity to create:
1. Underspecified recipient: "Write to the team about the project"
2. Missing context: "Follow up on our conversation"
3. Unclear ask: "Put together something for the client"

For each, note what information is deliberately omitted.

Return as JSON:
[
  {{
    "prompt_text": "The vague prompt...",
    "ambiguity_type": "underspecified_recipient|missing_context|unclear_ask",
    "deliberately_omitted": ["recipient name", "which project", etc]
  }}
]
"""

        response = await self.client.complete(
            model="openai/gpt-4.1",
            prompt=prompt,
            max_tokens=1000,
            temperature=0.8
        )

        return json.loads(response.text)

    async def run_phase1_preprocessing(self,
                                       tasks: List[Dict],
                                       output_file: str = "phase1_variations.json"):
        """Run full Phase 1 preprocessing"""

        all_variations = {}

        for task in tasks:
            task_id = task['task_id']

            # Generate persona variations
            personas = await self.generate_persona_variations(
                task['task_text'],
                task['occupation']
            )

            # For some tasks, generate revision drafts
            revision_drafts = []
            if random.random() < 0.15:  # 15% of tasks get revision versions
                revision_drafts = await self.generate_revision_drafts(
                    task['task_text']
                )

            # For some tasks, generate ambiguous versions
            ambiguous = []
            if random.random() < 0.10:  # 10% get ambiguous versions
                ambiguous = await self.generate_ambiguous_prompts(
                    task['task_text']
                )

            all_variations[task_id] = {
                'persona_variations': personas,
                'revision_drafts': revision_drafts,
                'ambiguous_versions': ambiguous
            }

        # Save to file
        output_path = self.output_dir / output_file
        with open(output_path, 'w') as f:
            json.dump(all_variations, f, indent=2)

        return output_path
```

### 3.2 Phase 2: Algorithmic Combinations (Improved)

```python
# src/prompts/phase2_combiner.py

import random
import hashlib
from typing import List, Optional, Dict
from datetime import datetime

class Phase2Combiner:
    """
    Phase 2: Deterministic algorithmic combination of dimensions.
    Combines O*NET tasks with Phase 1 variations using deterministic sampling.
    """

    def __init__(self,
                 onet_extractor,
                 naics_mapper,
                 company_database,
                 name_generator,
                 phase1_variations: Dict):
        self.onet = onet_extractor
        self.naics = naics_mapper
        self.companies = company_database
        self.names = name_generator
        self.phase1_data = phase1_variations

    def _generate_seed(self, task_id: str, dimension: str, base_seed: int) -> int:
        """Generate deterministic seed for a specific dimension"""
        combined = f"{task_id}:{dimension}:{base_seed}"
        return int(hashlib.md5(combined.encode()).hexdigest()[:8], 16)

    def combine_prompt(self,
                       task: 'ONetTask',
                       base_seed: int,
                       variation_index: int = 0) -> WritingPrompt:
        """
        Create a fully-specified prompt by combining task with Phase 1 variations
        and deterministic sampling.
        """
        rng = random.Random(base_seed)

        # Get Phase 1 variations for this task (if available)
        task_variations = self.phase1_data.get(task.task_id, {})
        persona_vars = task_variations.get('persona_variations', [])

        # Select a persona variation or generate algorithmically
        if persona_vars and variation_index < len(persona_vars):
            variation = persona_vars[variation_index]
            writer = self._build_writer_from_variation(variation['writer'], task, rng)
            recipient = self._build_recipient_from_variation(variation['recipient'], rng)
            company = self._build_company_from_variation(variation['company'], rng)
            emotional_context = EmotionalContext(variation['emotional_context'])
            urgency = variation['urgency']
            formality = variation['formality']
        else:
            # Fall back to algorithmic generation
            writer = self._generate_algorithmic_writer(task, rng)
            recipient = self._generate_algorithmic_recipient(task, rng)
            company = self._generate_algorithmic_company(task, rng)
            emotional_context = rng.choice(list(EmotionalContext))
            urgency = self._infer_urgency(task.task, rng)
            formality = self._infer_formality(task.job_zone, emotional_context, rng)

        # Determine task type
        task_type = TaskType.GENERATION
        original_draft = None
        revision_instruction = None

        # Check for revision tasks
        revision_drafts = task_variations.get('revision_drafts', [])
        if revision_drafts and rng.random() < 0.15:
            task_type = TaskType.REVISION
            draft = rng.choice(revision_drafts)
            original_draft = draft['draft_text']
            revision_instruction = draft['revision_instruction']

        # Check for reply context
        if task.task.lower().find('respond') >= 0 or task.task.lower().find('reply') >= 0:
            task_type = TaskType.REPLY

        # Check for ambiguous versions
        ambiguity_level = AmbiguityLevel.CLEAR
        deliberately_missing = []
        ambiguous_versions = task_variations.get('ambiguous_versions', [])
        if ambiguous_versions and rng.random() < 0.10:
            amb = rng.choice(ambiguous_versions)
            ambiguity_level = AmbiguityLevel.DELIBERATELY_VAGUE
            deliberately_missing = amb['deliberately_omitted']

        # Build prompt ID
        prompt_id = f"p_{task.task_id}_{base_seed}_{variation_index}"

        return WritingPrompt(
            prompt_id=prompt_id,
            onet_task_id=task.task_id,
            onet_task_text=task.task,
            occupation_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            job_zone=JobZone(task.job_zone),
            soc_major_group=task.soc_major_group,
            prompt_text=task.task,  # Will be enriched in Phase 3
            task_type=task_type,
            original_draft=original_draft,
            revision_instruction=revision_instruction,
            writer=writer,
            recipients=recipient,
            company=company,
            formality_level=formality,
            urgency_level=urgency,
            audience_size=self._infer_audience_size(task.task, rng),
            message_position=rng.choice(list(MessagePosition)),
            emotional_context=emotional_context,
            ambiguity_level=ambiguity_level,
            deliberately_missing=deliberately_missing,
            inferred_channel=self._infer_channel(task.task),
            writing_category=self._categorize_task(task.task),
            sensitive_topic=self._detect_sensitive_topic(task.task),
            generation_phase='phase2_algorithmic',
            random_seed=base_seed,
            created_at=datetime.utcnow()
        )
```

### 3.3 Phase 3: LLM Enrichment (Enhanced)

```python
# src/prompts/phase3_enricher.py

class Phase3Enricher:
    """
    Phase 3: LLM enrichment for context-heavy prompts.
    Adds realistic details, temporal context, attachments, etc.
    """

    def __init__(self, openrouter_client):
        self.client = openrouter_client

    async def enrich_prompt(self, prompt: WritingPrompt) -> WritingPrompt:
        """Enrich a prompt with LLM-generated realistic details"""

        # Determine what enrichments are needed
        needs_temporal = prompt.urgency_level >= 4
        needs_attachment = self._task_implies_attachment(prompt.onet_task_text)
        needs_tone_example = prompt.message_position == MessagePosition.FOLLOW_UP
        needs_reply_context = prompt.task_type == TaskType.REPLY
        needs_competing_objectives = self._has_inherent_tension(prompt.onet_task_text)
        needs_cc_context = len(prompt.recipients.cc_recipients) > 0

        if not any([needs_temporal, needs_attachment, needs_tone_example,
                    needs_reply_context, needs_competing_objectives, needs_cc_context]):
            return prompt

        enrichment_prompt = self._build_enrichment_prompt(
            prompt,
            needs_temporal,
            needs_attachment,
            needs_tone_example,
            needs_reply_context,
            needs_competing_objectives,
            needs_cc_context
        )

        try:
            response = await self.client.complete(
                model="anthropic/claude-sonnet-4",  # Fast, good quality
                prompt=enrichment_prompt,
                max_tokens=2000,
                temperature=0.7
            )

            enriched = self._parse_enrichment_response(response.text, prompt)
            enriched.generation_phase = 'phase3_enriched'
            return enriched

        except Exception as e:
            # Fall back to non-enriched prompt
            return prompt

    def _build_enrichment_prompt(self, prompt: WritingPrompt,
                                  needs_temporal: bool,
                                  needs_attachment: bool,
                                  needs_tone_example: bool,
                                  needs_reply_context: bool,
                                  needs_competing_objectives: bool,
                                  needs_cc_context: bool) -> str:
        """Build the enrichment prompt with specific requirements"""

        sections = []

        base = f"""
You are enriching a writing task prompt to make it more realistic.

Original Task: {prompt.onet_task_text}
Writer: {prompt.writer.name}, {prompt.writer.job_title} at {prompt.company.name}
Recipient: {prompt.recipients.primary_recipient.name}, {prompt.recipients.primary_recipient.job_title}
Urgency: {prompt.urgency_level}/5
Formality: {prompt.formality_level}/5
"""
        sections.append(base)

        if needs_temporal:
            sections.append("""
TEMPORAL CONTEXT NEEDED:
Add realistic temporal grounding, e.g., "The board meeting is this Friday..." or "Q4 results are due next week..."
""")

        if needs_attachment:
            sections.append("""
ATTACHMENT REFERENCE NEEDED:
Add a mock attachment with key details the writer would reference, e.g.,
"Attached Q3 report shows revenue up 15% but margins compressed by 2 points..."
""")

        if needs_tone_example:
            sections.append("""
TONE EXAMPLE NEEDED:
Provide a brief sample of how this writer typically communicates (2-3 sentences)
that the model should match.
""")

        if needs_reply_context:
            sections.append("""
REPLY CONTEXT NEEDED:
Provide the prior message the writer is responding to. Make it realistic -
it could be a question, request, complaint, or update.
""")

        if needs_competing_objectives:
            sections.append("""
COMPETING OBJECTIVES:
This task has inherent tension. Explicitly state the competing goals, e.g.,
"Be direct but diplomatic" or "Convey urgency without causing panic"
""")

        if needs_cc_context:
            cc_names = [r.name for r in prompt.recipients.cc_recipients]
            sections.append(f"""
CC SITUATION:
This message is CC'd to: {', '.join(cc_names)}
Explain the context - why are they CC'd? What should the writer be aware of?
""")

        sections.append("""
Return a JSON object with the enriched fields:
{
  "enriched_prompt_text": "The full enriched prompt...",
  "temporal_context": "optional string",
  "attachments": [{"type": "report", "description": "Q3 Report", "content_summary": "..."}],
  "tone_example": "optional sample writing",
  "reply_context": "optional prior message",
  "competing_objectives": "optional tension description"
}
""")

        return '\n'.join(sections)
```

---

## 4. Evaluation Engine (Corrected Vote Aggregation)

### 4.1 Corrected Majority-of-Majorities Implementation

```python
# src/eval/vote_aggregator.py

from collections import Counter
from typing import List, Dict, Tuple, Literal
from ..schemas import JudgeVote, PerJudgePersonaVerdict, Comparison

class VoteAggregator:
    """
    Implements the correct majority-of-majorities voting logic:
    1. Each judge model + persona combination gives 5 votes
    2. Compute majority per judge+persona
    3. For each judge, combine persona verdicts (2 verdicts -> judge verdict)
    4. Compute final majority across 3 judges
    """

    def aggregate_votes(self,
                        votes: List[JudgeVote],
                        gemini_model_id: str) -> Tuple[List[PerJudgePersonaVerdict],
                                                        Dict[str, str],
                                                        str,
                                                        bool]:
        """
        Aggregate all votes into final verdict.

        Returns:
            - List of per-judge-persona verdicts
            - Dict of per-judge verdicts
            - Final winner
            - Whether Gemini won
        """

        # Step 1: Group votes by judge model + persona
        grouped = {}  # (judge_model, persona) -> list of votes
        for vote in votes:
            key = (vote.judge_model, vote.judge_persona)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(vote)

        # Step 2: Compute majority per judge+persona
        judge_persona_verdicts = []
        for (judge_model, persona), judge_votes in grouped.items():
            winners = [v.winner for v in judge_votes]
            counter = Counter(winners)

            # Get majority winner
            if counter.most_common(1):
                majority = counter.most_common(1)[0][0]
            else:
                majority = 'tie'

            verdict = PerJudgePersonaVerdict(
                judge_model=judge_model,
                persona=persona,
                votes=judge_votes,
                majority_winner=majority,
                vote_count_a=counter.get('model_a', 0),
                vote_count_b=counter.get('model_b', 0),
                vote_count_tie=counter.get('tie', 0)
            )
            judge_persona_verdicts.append(verdict)

        # Step 3: Compute per-judge verdict (from both personas)
        judge_verdicts = {}  # judge_model -> verdict
        judges = set(v.judge_model for v in judge_persona_verdicts)

        for judge in judges:
            # Get both persona verdicts for this judge
            persona_verdicts = [v for v in judge_persona_verdicts
                               if v.judge_model == judge]

            # Majority of persona verdicts (with 2 personas, need agreement or tie)
            persona_winners = [v.majority_winner for v in persona_verdicts]
            counter = Counter(persona_winners)

            if len(persona_verdicts) == 2:
                # Both personas agree
                if persona_verdicts[0].majority_winner == persona_verdicts[1].majority_winner:
                    judge_verdicts[judge] = persona_verdicts[0].majority_winner
                else:
                    # Personas disagree - this is a tie for this judge
                    judge_verdicts[judge] = 'tie'
            else:
                # Single persona or >2 personas
                judge_verdicts[judge] = counter.most_common(1)[0][0]

        # Step 4: Compute final verdict (majority of judges)
        final_counter = Counter(judge_verdicts.values())

        # Handle the three-judge case
        if len(judge_verdicts) == 3:
            # Need at least 2 judges to agree
            most_common = final_counter.most_common(1)[0]
            if most_common[1] >= 2:
                final_winner = most_common[0]
            else:
                # All three disagree (A, B, tie) - result is tie
                final_winner = 'tie'
        else:
            final_winner = final_counter.most_common(1)[0][0]

        # Determine if Gemini won
        # Gemini is always model_a in our comparisons
        gemini_won = True if final_winner == 'model_a' else \
                     False if final_winner == 'model_b' else None

        return judge_persona_verdicts, judge_verdicts, final_winner, gemini_won
```

### 4.2 Evaluation Engine with Proper Integration

```python
# src/eval/engine.py

import asyncio
import signal
from datetime import datetime
from typing import Optional
import logging

from ..api.openrouter_client import OpenRouterClient, APIError
from ..schemas import WritingPrompt, ModelResponse, JudgeVote, Comparison
from ..storage.checkpoint import CheckpointManager
from ..storage.database import ResultsDatabase
from .vote_aggregator import VoteAggregator
from .judge_prompts import build_judge_prompt

logger = logging.getLogger(__name__)

class EvaluationEngine:
    """
    Core evaluation engine with proper graceful shutdown and error handling.
    """

    def __init__(self,
                 config: 'EvalConfig',
                 openrouter: OpenRouterClient,
                 checkpoint_mgr: CheckpointManager,
                 database: ResultsDatabase,
                 failure_logger: 'FailureLogger'):
        self.config = config
        self.openrouter = openrouter
        self.checkpoint = checkpoint_mgr
        self.db = database
        self.failures = failure_logger
        self.aggregator = VoteAggregator()

        # Graceful shutdown handling
        self._shutdown_requested = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown"""
        def handle_shutdown(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

    def _build_model_prompt(self, prompt: WritingPrompt) -> str:
        """
        Build the full prompt to send to the model.
        IMPORTANT: Do NOT add length/format constraints unless explicitly specified.
        """
        primary = prompt.recipients.primary_recipient

        parts = [
            f"You are {prompt.writer.name}, a {prompt.writer.job_title} at {prompt.company.name}.",
            f"You have {prompt.writer.years_experience} years of experience.",
            "",
            "TASK:",
            prompt.prompt_text,
        ]

        # Handle revision tasks
        if prompt.task_type == TaskType.REVISION and prompt.original_draft:
            parts.append("")
            parts.append("ORIGINAL DRAFT TO REVISE:")
            parts.append(prompt.original_draft)
            parts.append("")
            parts.append(f"REVISION INSTRUCTION: {prompt.revision_instruction}")

        # Basic recipient info
        parts.append("")
        parts.append(f"Write to: {primary.name} ({primary.job_title})")
        parts.append(f"Your relationship: {primary.relationship}, familiarity: {primary.familiarity}")

        # CC recipients if any
        if prompt.recipients.cc_recipients:
            cc_names = [f"{r.name} ({r.job_title})" for r in prompt.recipients.cc_recipients]
            parts.append(f"CC: {', '.join(cc_names)}")
            if prompt.recipients.audience_notes:
                parts.append(f"Note: {prompt.recipients.audience_notes}")

        # Context (but NOT constraints unless explicit)
        parts.append(f"Formality level: {prompt.formality_level}/5")
        parts.append(f"Urgency: {prompt.urgency_level}/5")

        if prompt.temporal_context:
            parts.append(f"\nTiming: {prompt.temporal_context}")

        if prompt.attachments:
            parts.append("\nReferences/Attachments:")
            for att in prompt.attachments:
                parts.append(f"- {att.type}: {att.content_summary}")

        if prompt.reply_context:
            parts.append(f"\nPrior message to reply to:\n{prompt.reply_context}")

        if prompt.tone_example:
            parts.append(f"\nMatch this writing style:\n{prompt.tone_example}")

        if prompt.competing_objectives:
            parts.append(f"\nNote: {prompt.competing_objectives}")

        # ONLY add explicit constraints if testing instruction-following
        if prompt.constraints:
            parts.append("\n** IMPORTANT CONSTRAINTS (you must follow these) **:")
            for c in prompt.constraints:
                parts.append(f"- {c.description}")

        parts.append("\nWrite your response:")

        return "\n".join(parts)

    async def generate_response(self,
                                prompt: WritingPrompt,
                                model_id: str) -> ModelResponse:
        """Generate a response from a model with proper error handling"""
        model = self.config.get_model(model_id)
        full_prompt = self._build_model_prompt(prompt)

        try:
            response = await self.openrouter.complete(
                model=model.openrouter_id,
                prompt=full_prompt,
                max_tokens=model.max_output,
                temperature=0.7
            )

            # Analyze response metadata
            analysis = self._analyze_response(response.text, prompt)

            return ModelResponse(
                response_id=f"r_{prompt.prompt_id}_{model_id}_{int(datetime.utcnow().timestamp())}",
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                model_name=model.name,
                response_text=response.text,
                response_time_ms=response.latency_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                finish_reason=response.finish_reason,
                **analysis,
                created_at=datetime.utcnow()
            )

        except APIError as e:
            # Log specific API error
            self.failures.log_api_error(prompt.prompt_id, model_id, e)
            return self._create_failure_response(prompt, model_id, model.name, str(e))

        except Exception as e:
            # Log unexpected error
            self.failures.log_unexpected_error(prompt.prompt_id, model_id, e)
            raise  # Re-raise unexpected errors

    async def evaluate_prompt(self,
                              prompt: WritingPrompt,
                              model_pair: tuple[str, str]) -> Optional[Comparison]:
        """
        Run full evaluation for a single prompt and model pair.
        Returns None if shutdown was requested.
        """
        if self._shutdown_requested:
            return None

        gemini_id, competitor_id = model_pair

        # Generate responses in parallel
        gemini_response, competitor_response = await asyncio.gather(
            self.generate_response(prompt, gemini_id),
            self.generate_response(prompt, competitor_id)
        )

        # Check for shutdown between phases
        if self._shutdown_requested:
            # Save what we have
            self.db.insert_response(gemini_response)
            self.db.insert_response(competitor_response)
            return None

        # Handle failures (auto-loss)
        if gemini_response.is_refusal and not competitor_response.is_refusal:
            return self._create_auto_loss_comparison(
                prompt, gemini_response, competitor_response, loser='gemini'
            )
        elif competitor_response.is_refusal and not gemini_response.is_refusal:
            return self._create_auto_loss_comparison(
                prompt, gemini_response, competitor_response, loser='competitor'
            )
        elif gemini_response.is_refusal and competitor_response.is_refusal:
            return self._create_auto_loss_comparison(
                prompt, gemini_response, competitor_response, loser='both'
            )

        # Run judge voting with all combinations
        presentation_seed = hash(f"{prompt.prompt_id}:{gemini_id}:{competitor_id}")
        votes = []

        for judge_config in self.config.judges:
            if self._shutdown_requested:
                break

            for persona in judge_config.personas:
                for vote_num in range(judge_config.votes_per_comparison):
                    if self._shutdown_requested:
                        break

                    vote = await self.run_judge_vote(
                        prompt=prompt,
                        response_a=gemini_response,
                        response_b=competitor_response,
                        judge_model_id=judge_config.model.id,
                        judge_persona=persona,
                        vote_number=vote_num,
                        presentation_seed=presentation_seed
                    )
                    votes.append(vote)

        # Aggregate with correct logic
        judge_persona_verdicts, judge_verdicts, final_winner, gemini_won = \
            self.aggregator.aggregate_votes(votes, gemini_id)

        comparison = Comparison(
            comparison_id=f"c_{prompt.prompt_id}_{gemini_id}_{competitor_id}",
            prompt_id=prompt.prompt_id,
            model_a_id=gemini_id,
            model_b_id=competitor_id,
            model_a_name=gemini_response.model_name,
            model_b_name=competitor_response.model_name,
            response_a_id=gemini_response.response_id,
            response_b_id=competitor_response.response_id,
            votes=votes,
            judge_persona_verdicts=judge_persona_verdicts,
            claude_verdict=judge_verdicts.get('claude-opus-4.5'),
            gpt_verdict=judge_verdicts.get('gpt-5.2-thinking'),
            gemini_verdict=judge_verdicts.get('gemini-3-pro'),
            final_winner=final_winner,
            gemini_won=gemini_won,
            presentation_order_seed=presentation_seed,
            created_at=datetime.utcnow()
        )

        return comparison
```

---

## 5. Storage Layer Improvements

### 5.1 Transactional Database Writes

```python
# src/storage/database.py

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ResultsDatabase:
    """SQLite database with transactional writes for atomicity"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    @contextmanager
    def transaction(self):
        """Context manager for transactional writes"""
        try:
            yield
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Transaction rolled back due to: {e}")
            raise

    def insert_comparison_with_responses(self,
                                         response_a: 'ModelResponse',
                                         response_b: 'ModelResponse',
                                         comparison: 'Comparison',
                                         votes: list['JudgeVote']):
        """Insert all related entities in a single transaction"""
        with self.transaction():
            self._insert_response(response_a)
            self._insert_response(response_b)
            self._insert_comparison(comparison)
            for vote in votes:
                self._insert_vote(vote)

    def _insert_response(self, response: 'ModelResponse'):
        """Internal insert without commit"""
        self.conn.execute("""
            INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.response_id,
            response.prompt_id,
            response.model_id,
            response.model_name,
            response.response_text,
            response.response_time_ms,
            response.input_tokens,
            response.output_tokens,
            response.finish_reason,
            response.word_count,
            response.character_count,
            json.dumps(response.detected_format),
            response.greeting_pattern,
            response.signoff_pattern,
            int(response.is_refusal),
            response.refusal_category,
            int(response.is_off_topic),
            response.created_at.isoformat()
        ))
```

### 5.2 Failure Logger

```python
# src/storage/failure_logger.py

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

class FailureLogger:
    """Structured failure logging as required by PROMPT.md"""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = None

    def open(self):
        self._file = open(self.log_path, 'a')

    def close(self):
        if self._file:
            self._file.close()

    def _write_entry(self, entry: dict):
        entry['timestamp'] = datetime.utcnow().isoformat()
        self._file.write(json.dumps(entry) + '\n')
        self._file.flush()

    def log_api_error(self, prompt_id: str, model_id: str, error: Exception):
        self._write_entry({
            'type': 'api_error',
            'prompt_id': prompt_id,
            'model_id': model_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
        })

    def log_unexpected_error(self, prompt_id: str, model_id: str, error: Exception):
        import traceback
        self._write_entry({
            'type': 'unexpected_error',
            'prompt_id': prompt_id,
            'model_id': model_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        })

    def log_refusal(self, prompt_id: str, model_id: str, category: str, response_text: str):
        self._write_entry({
            'type': 'refusal',
            'prompt_id': prompt_id,
            'model_id': model_id,
            'refusal_category': category,
            'response_preview': response_text[:500]
        })

    def log_rate_limit(self, model_id: str, wait_seconds: float):
        self._write_entry({
            'type': 'rate_limit',
            'model_id': model_id,
            'wait_seconds': wait_seconds
        })

    def get_failure_summary(self) -> dict:
        """Generate failure summary for end-of-run report"""
        failures = []
        with open(self.log_path, 'r') as f:
            for line in f:
                failures.append(json.loads(line))

        summary = {
            'total_failures': len(failures),
            'by_type': {},
            'by_model': {},
            'refusal_categories': {}
        }

        for f in failures:
            # Count by type
            t = f['type']
            summary['by_type'][t] = summary['by_type'].get(t, 0) + 1

            # Count by model
            if 'model_id' in f:
                m = f['model_id']
                summary['by_model'][m] = summary['by_model'].get(m, 0) + 1

            # Count refusal categories
            if f['type'] == 'refusal':
                cat = f['refusal_category']
                summary['refusal_categories'][cat] = summary['refusal_categories'].get(cat, 0) + 1

        return summary
```

---

## 6. Run Directory Structure (Complete Implementation)

```python
# src/storage/run_directory.py

from pathlib import Path
from datetime import datetime
import json
import shutil

class RunDirectoryManager:
    """Manage the complete run directory structure per PROMPT.md"""

    def __init__(self, base_dir: Path, run_id: str):
        self.base_dir = base_dir
        self.run_id = run_id
        self.run_dir = base_dir / run_id

    def initialize(self):
        """Create the full directory structure"""
        dirs = [
            self.run_dir,
            self.run_dir / "prompts",
            self.run_dir / "prompts" / "by_occupation",
            self.run_dir / "prompts" / "by_industry",
            self.run_dir / "responses",
            self.run_dir / "responses" / "by_prompt",
            self.run_dir / "responses" / "by_model",
            self.run_dir / "judgments",
            self.run_dir / "judgments" / "raw",
            self.run_dir / "judgments" / "aggregated",
            self.run_dir / "analysis",
            self.run_dir / "reports",
            self.run_dir / "reports" / "charts",
            self.run_dir / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Update latest symlink
        latest_link = self.base_dir / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(self.run_dir.name)

    def save_config(self, config: 'EvalConfig'):
        """Save full configuration"""
        # config.json
        with open(self.run_dir / "config.json", 'w') as f:
            json.dump(config.model_dump(), f, indent=2, default=str)

        # config_summary.txt (human-readable)
        summary = self._generate_config_summary(config)
        with open(self.run_dir / "config_summary.txt", 'w') as f:
            f.write(summary)

        # random_seed.txt
        with open(self.run_dir / "random_seed.txt", 'w') as f:
            f.write(str(config.random_seed))

    def _generate_config_summary(self, config: 'EvalConfig') -> str:
        lines = [
            "=" * 60,
            "GEMINI WRITING EVALUATION - RUN CONFIGURATION",
            "=" * 60,
            "",
            f"Run ID: {config.run_id}",
            f"Preset: {config.preset_name or 'Custom'}",
            f"Created: {datetime.now().isoformat()}",
            "",
            "--- PROMPTS ---",
            f"Number of prompts: {config.num_prompts}",
            f"Random seed: {config.random_seed}",
            "",
            "--- MODELS ---",
            f"Model pairs: {len(config.model_pairs)}",
        ]
        for g, c in config.model_pairs:
            lines.append(f"  - {g} vs {c}")
        lines.extend([
            "",
            "--- JUDGES ---",
            f"Number of judges: {len(config.judges)}",
            f"Votes per comparison: {config.judges[0].votes_per_comparison if config.judges else 'N/A'}",
            f"Personas: writing_expert, target_recipient",
            "",
            "--- FILTERS ---",
            f"Occupations: {config.occupation_filter or 'All'}",
            f"Industries: {config.industry_filter or 'All'}",
            f"Job zones: {config.job_zone_filter or 'All'}",
            "",
            "=" * 60,
        ])
        return '\n'.join(lines)

    def generate_readme(self, config: 'EvalConfig', results_summary: dict):
        """Generate auto README.md"""
        readme = f"""# Evaluation Run: {config.run_id}

## Overview

- **Preset**: {config.preset_name or 'Custom'}
- **Started**: {datetime.now().isoformat()}
- **Prompts**: {config.num_prompts}
- **Model Pairs**: {len(config.model_pairs)}

## Configuration

See `config.json` for full configuration and `config_summary.txt` for human-readable summary.

## Results

| Model Pair | Gemini Win Rate | N |
|------------|-----------------|---|
"""
        for pair, data in results_summary.get('win_rates', {}).items():
            readme += f"| Gemini vs {pair[1]} | {data['win_rate']:.1%} | {data['n']} |\n"

        readme += """
## Files

- `results.db` - SQLite database with all results
- `prompts/` - Generated prompts organized by occupation and industry
- `responses/` - Model responses organized by prompt and model
- `judgments/` - Judge votes and aggregated verdicts
- `analysis/` - Statistical analysis outputs
- `reports/` - PDF report and charts
- `logs/` - Execution logs and failure tracking

## Reproducibility

This run can be reproduced using:
```bash
./eval --seed {seed} --config config.json
```
""".format(seed=config.random_seed)

        with open(self.run_dir / "README.md", 'w') as f:
            f.write(readme)

    def save_prompts_organized(self, prompts: list['WritingPrompt']):
        """Save prompts organized by occupation and industry"""
        from collections import defaultdict

        # By occupation
        by_occ = defaultdict(list)
        for p in prompts:
            by_occ[p.occupation_code].append(p.model_dump())

        for occ, occ_prompts in by_occ.items():
            path = self.run_dir / "prompts" / "by_occupation" / f"{occ}.json"
            with open(path, 'w') as f:
                json.dump(occ_prompts, f, indent=2, default=str)

        # By industry
        by_ind = defaultdict(list)
        for p in prompts:
            by_ind[p.company.industry_naics].append(p.model_dump())

        for ind, ind_prompts in by_ind.items():
            path = self.run_dir / "prompts" / "by_industry" / f"naics_{ind}.json"
            with open(path, 'w') as f:
                json.dump(ind_prompts, f, indent=2, default=str)

        # All prompts
        with open(self.run_dir / "prompts" / "prompts.json", 'w') as f:
            json.dump([p.model_dump() for p in prompts], f, indent=2, default=str)
```

---

## 7. Statistical Analysis Corrections

```python
# src/analysis/statistics.py

import numpy as np
from scipy import stats
from sklearn.metrics import cohen_kappa_score  # Correct import
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class WinRateResult:
    """Win rate with confidence interval"""
    win_rate: float
    ci_low: float
    ci_high: float
    n_samples: int
    p_value: float

@dataclass
class BiasAnalysis:
    """Analysis of systematic biases"""
    position_bias: float
    position_bias_p: float
    length_correlation: float
    length_correlation_p: float
    format_bias: Dict[str, float]  # NEW: Format preference analysis
    judge_agreement_kappa: float

class StatisticalAnalyzer:
    """Statistical analysis with corrected scipy usage"""

    def __init__(self, db: 'ResultsDatabase'):
        self.db = db

    def compute_win_rate(self, model_pair: Tuple[str, str],
                         confidence: float = 0.95) -> WinRateResult:
        """Compute win rate with Wilson score confidence interval"""
        data = self.db.get_win_rates(model_pair)
        if model_pair not in data:
            return None

        stats_data = data[model_pair]
        n = stats_data['total']
        wins = stats_data['gemini_wins']

        if n == 0:
            return WinRateResult(0, 0, 1, 0, 1.0)

        p = wins / n

        # Wilson score interval (correct for proportions)
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        spread = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator

        ci_low = max(0, center - spread)
        ci_high = min(1, center + spread)

        # CORRECTED: Use binomtest instead of deprecated binom_test
        result = stats.binomtest(wins, n, 0.5, alternative='two-sided')
        p_value = result.pvalue

        return WinRateResult(
            win_rate=p,
            ci_low=ci_low,
            ci_high=ci_high,
            n_samples=n,
            p_value=p_value
        )

    def compute_judge_agreement(self) -> float:
        """Compute Cohen's Kappa using sklearn"""
        cursor = self.db.conn.execute("""
            SELECT comparison_id, judge_model, winner
            FROM judge_votes
            WHERE winner != 'tie'
        """)

        from collections import defaultdict
        comparisons = defaultdict(dict)

        for row in cursor:
            # Use first vote per judge per comparison for Kappa
            key = (row['comparison_id'], row['judge_model'])
            if key not in comparisons:
                comparisons[row['comparison_id']][row['judge_model']] = row['winner']

        judges = list(set(j for c in comparisons.values() for j in c.keys()))
        if len(judges) < 2:
            return 1.0

        kappas = []
        for i, j1 in enumerate(judges):
            for j2 in judges[i+1:]:
                ratings1 = []
                ratings2 = []
                for comp_votes in comparisons.values():
                    if j1 in comp_votes and j2 in comp_votes:
                        ratings1.append(comp_votes[j1])
                        ratings2.append(comp_votes[j2])

                if len(ratings1) >= 10:
                    # CORRECTED: Use sklearn's cohen_kappa_score
                    kappa = cohen_kappa_score(ratings1, ratings2)
                    kappas.append(kappa)

        return np.mean(kappas) if kappas else 0

    def analyze_format_bias(self) -> Dict[str, float]:
        """Analyze if judges prefer certain formats - NEW"""
        cursor = self.db.conn.execute("""
            SELECT
                jv.winner,
                ra.detected_format as format_a,
                rb.detected_format as format_b
            FROM judge_votes jv
            JOIN comparisons c ON jv.comparison_id = c.comparison_id
            JOIN responses ra ON c.response_a_id = ra.response_id
            JOIN responses rb ON c.response_b_id = rb.response_id
            WHERE jv.winner != 'tie'
        """)

        format_wins = defaultdict(lambda: {'wins': 0, 'total': 0})

        for row in cursor:
            format_a = json.loads(row['format_a'])
            format_b = json.loads(row['format_b'])

            for fmt in format_a:
                format_wins[fmt]['total'] += 1
                if row['winner'] == 'model_a':
                    format_wins[fmt]['wins'] += 1

            for fmt in format_b:
                format_wins[fmt]['total'] += 1
                if row['winner'] == 'model_b':
                    format_wins[fmt]['wins'] += 1

        # Calculate win rates per format
        bias = {}
        for fmt, data in format_wins.items():
            if data['total'] >= 20:
                rate = data['wins'] / data['total']
                # Test against 50%
                result = stats.binomtest(data['wins'], data['total'], 0.5)
                bias[fmt] = {
                    'win_rate': rate,
                    'n': data['total'],
                    'p_value': result.pvalue,
                    'significant': result.pvalue < 0.05
                }

        return bias

    def analyze_response_patterns(self) -> Dict:
        """Analyze systematic response patterns per PROMPT.md - NEW"""
        cursor = self.db.conn.execute("""
            SELECT
                model_id,
                AVG(word_count) as avg_length,
                STDEV(word_count) as std_length,
                AVG(response_time_ms) as avg_latency,
                detected_format
            FROM responses
            GROUP BY model_id
        """)

        patterns = {}
        for row in cursor:
            patterns[row['model_id']] = {
                'avg_length': row['avg_length'],
                'std_length': row['std_length'],
                'avg_latency': row['avg_latency'],
                'format_distribution': self._get_format_distribution(row['model_id'])
            }

        return patterns

    def _get_format_distribution(self, model_id: str) -> Dict[str, float]:
        """Get format usage distribution for a model"""
        cursor = self.db.conn.execute("""
            SELECT detected_format, COUNT(*) as count
            FROM responses
            WHERE model_id = ?
        """, (model_id,))

        total = 0
        format_counts = defaultdict(int)

        for row in cursor:
            formats = json.loads(row['detected_format'])
            total += 1
            for fmt in formats:
                format_counts[fmt] += 1

        return {fmt: count/total for fmt, count in format_counts.items()} if total > 0 else {}
```

---

## 8. Enhanced PDF Report Generator

```python
# src/reports/pdf_generator.py (additions for missing sections)

def _generate_heatmap(self):
    """Generate win rate heatmap by dimension - IMPLEMENTED"""
    cursor = self.db.conn.execute("""
        SELECT
            p.soc_major_group,
            p.job_zone,
            c.model_b_id as competitor,
            AVG(CASE WHEN c.gemini_won = 1 THEN 1.0 ELSE 0.0 END) as win_rate,
            COUNT(*) as n
        FROM comparisons c
        JOIN prompts p ON c.prompt_id = p.prompt_id
        WHERE c.gemini_won IS NOT NULL
        GROUP BY p.soc_major_group, p.job_zone, c.model_b_id
        HAVING n >= 5
    """)

    data = list(cursor)

    if not data:
        return

    # Create pivot table for heatmap
    import pandas as pd

    df = pd.DataFrame(data, columns=['soc_group', 'job_zone', 'competitor', 'win_rate', 'n'])

    for competitor in df['competitor'].unique():
        comp_df = df[df['competitor'] == competitor]
        pivot = comp_df.pivot(index='soc_group', columns='job_zone', values='win_rate')

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f'Zone {z}' for z in pivot.columns],
            y=pivot.index,
            colorscale='RdYlGn',
            zmid=0.5,
            text=[[f'{v:.0%}' if not np.isnan(v) else '' for v in row] for row in pivot.values],
            texttemplate='%{text}',
            textfont={"size": 10},
            hovertemplate='SOC: %{y}<br>Job Zone: %{x}<br>Win Rate: %{z:.1%}<extra></extra>'
        ))

        fig.update_layout(
            title=f'Gemini Win Rates vs {competitor} by SOC Group and Job Zone',
            xaxis_title='Job Zone',
            yaxis_title='SOC Major Group'
        )

        fig.write_image(str(self.charts_dir / f"heatmap_{competitor.replace('/', '_')}.png"))
```

---

## 9. Results Viewer TUI (Implementation)

```python
# src/tui/viewer.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static, Input, Select
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.binding import Binding
from rich.panel import Panel
from rich.syntax import Syntax
import json

class ResultsViewer(App):
    """Interactive TUI for viewing evaluation results - as required by PROMPT.md"""

    CSS = """
    #filters {
        height: 5;
        dock: top;
    }
    #results-table {
        height: 60%;
    }
    #detail-view {
        height: 40%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filters", "Filters"),
        Binding("enter", "select_row", "View Details"),
        Binding("/", "search", "Search"),
        Binding("j", "next", "Next"),
        Binding("k", "prev", "Previous"),
    ]

    def __init__(self, db_path: str, **kwargs):
        super().__init__(**kwargs)
        from ..storage.database import ResultsDatabase
        self.db = ResultsDatabase(db_path)
        self.db.connect()
        self.current_filters = {}
        self.selected_comparison = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # Filters row
        with Horizontal(id="filters"):
            yield Select(
                [("All", None)] + [(occ, occ) for occ in self._get_occupations()],
                prompt="Occupation",
                id="filter-occupation"
            )
            yield Select(
                [("All", None), ("Gemini Wins", "gemini"), ("Opponent Wins", "opponent"), ("Ties", "tie")],
                prompt="Winner",
                id="filter-winner"
            )
            yield Select(
                [("All", None)] + [(str(z), z) for z in range(1, 6)],
                prompt="Job Zone",
                id="filter-zone"
            )
            yield Input(placeholder="Search prompts...", id="search-input")

        # Results table
        yield DataTable(id="results-table")

        # Detail view
        yield ScrollableContainer(
            Static(id="detail-content"),
            id="detail-view"
        )

        yield Footer()

    def on_mount(self):
        """Initialize the table"""
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "ID", "Occupation", "Zone", "Winner", "Gemini Rate", "Votes"
        )
        self._refresh_table()

    def _get_occupations(self) -> list:
        """Get list of occupations for filter"""
        cursor = self.db.conn.execute(
            "SELECT DISTINCT occupation_title FROM prompts ORDER BY occupation_title"
        )
        return [row[0] for row in cursor]

    def _refresh_table(self):
        """Refresh table with current filters"""
        table = self.query_one("#results-table", DataTable)
        table.clear()

        query = """
            SELECT
                c.comparison_id,
                p.occupation_title,
                p.job_zone,
                CASE
                    WHEN c.gemini_won = 1 THEN 'Gemini'
                    WHEN c.gemini_won = 0 THEN 'Opponent'
                    ELSE 'Tie'
                END as winner,
                c.model_b_name,
                (SELECT COUNT(*) FROM judge_votes jv
                 WHERE jv.comparison_id = c.comparison_id) as vote_count
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            WHERE 1=1
        """
        params = []

        # Apply filters
        if self.current_filters.get('occupation'):
            query += " AND p.occupation_title = ?"
            params.append(self.current_filters['occupation'])

        if self.current_filters.get('winner'):
            if self.current_filters['winner'] == 'gemini':
                query += " AND c.gemini_won = 1"
            elif self.current_filters['winner'] == 'opponent':
                query += " AND c.gemini_won = 0"
            elif self.current_filters['winner'] == 'tie':
                query += " AND c.gemini_won IS NULL"

        if self.current_filters.get('zone'):
            query += " AND p.job_zone = ?"
            params.append(self.current_filters['zone'])

        if self.current_filters.get('search'):
            query += " AND p.prompt_text LIKE ?"
            params.append(f"%{self.current_filters['search']}%")

        query += " ORDER BY c.comparison_id LIMIT 500"

        cursor = self.db.conn.execute(query, params)

        for row in cursor:
            table.add_row(
                row['comparison_id'][:20] + '...',
                row['occupation_title'][:30],
                str(row['job_zone']),
                row['winner'],
                row['model_b_name'][:15],
                str(row['vote_count'])
            )

    def action_select_row(self):
        """Show details for selected comparison"""
        table = self.query_one("#results-table", DataTable)
        row = table.cursor_row
        if row is None:
            return

        comparison_id = table.get_cell_at((row, 0))
        # Reconstruct full ID
        cursor = self.db.conn.execute(
            "SELECT comparison_id FROM comparisons WHERE comparison_id LIKE ?",
            (comparison_id.replace('...', '%'),)
        )
        full_id = cursor.fetchone()
        if full_id:
            self._show_comparison_detail(full_id[0])

    def _show_comparison_detail(self, comparison_id: str):
        """Show detailed view of a comparison"""
        # Get comparison data
        cursor = self.db.conn.execute("""
            SELECT
                c.*,
                p.prompt_text,
                p.occupation_title,
                ra.response_text as response_a_text,
                rb.response_text as response_b_text
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            JOIN responses ra ON c.response_a_id = ra.response_id
            JOIN responses rb ON c.response_b_id = rb.response_id
            WHERE c.comparison_id = ?
        """, (comparison_id,))

        row = cursor.fetchone()
        if not row:
            return

        # Get votes
        votes_cursor = self.db.conn.execute("""
            SELECT judge_model, judge_persona, winner, reasoning
            FROM judge_votes
            WHERE comparison_id = ?
            ORDER BY judge_model, judge_persona, vote_number
        """, (comparison_id,))

        votes = list(votes_cursor)

        # Build detail content
        content = f"""
## Comparison: {comparison_id}

### Prompt
**Occupation:** {row['occupation_title']}

{row['prompt_text']}

---

### Response A ({row['model_a_name']})

{row['response_a_text'][:2000]}{'...' if len(row['response_a_text']) > 2000 else ''}

---

### Response B ({row['model_b_name']})

{row['response_b_text'][:2000]}{'...' if len(row['response_b_text']) > 2000 else ''}

---

### Votes

| Judge | Persona | Winner | Reasoning |
|-------|---------|--------|-----------|
"""
        for v in votes:
            content += f"| {v['judge_model']} | {v['judge_persona']} | {v['winner']} | {v['reasoning'][:50]}... |\n"

        content += f"""
---

### Final Result

**Winner:** {row['final_winner']}
**Gemini Won:** {row['gemini_won']}
"""

        detail = self.query_one("#detail-content", Static)
        detail.update(Panel(content, title="Comparison Details"))

    def on_select_changed(self, event):
        """Handle filter changes"""
        if event.select.id == "filter-occupation":
            self.current_filters['occupation'] = event.value
        elif event.select.id == "filter-winner":
            self.current_filters['winner'] = event.value
        elif event.select.id == "filter-zone":
            self.current_filters['zone'] = event.value
        self._refresh_table()

    def on_input_submitted(self, event):
        """Handle search"""
        if event.input.id == "search-input":
            self.current_filters['search'] = event.value
            self._refresh_table()
```

---

## 10. Implementation Timeline (Revised)

### Phase 1: Foundation (Week 1)
- Set up project structure and dependencies
- Implement O*NET data extractor **with ONET_WRITING_REFERENCE.md integration**
- Create Phase 1 preprocessing for persona variations
- Implement OpenRouter API client with circuit breaker

### Phase 2: Prompt Generation (Week 2)
- Implement Phase 2 algorithmic combiner
- Implement Phase 3 LLM enrichment
- Add revision task generation
- Add ambiguous prompt generation
- Add tone example generation
- Add CC recipient support

### Phase 3: Core Evaluation (Week 3)
- Implement evaluation engine with **correct vote aggregation**
- Build judge prompt construction with full context
- Implement **per-persona voting logic**
- Create SQLite storage layer with **transactional writes**
- Implement checkpoint/resume system with **signal handlers**
- Add **structured failure logging**

### Phase 4: TUI and Analysis (Week 4)
- Build Rich/Textual progress dashboard
- Implement **results viewer TUI**
- Create statistical analysis module with **corrected scipy usage**
- Implement **heatmap generation**
- Add **format bias detection**
- Add **response pattern analysis**

### Phase 5: Reporting and Polish (Week 5)
- Build PDF report generator with all sections
- Implement **run directory structure per PROMPT.md**
- Add **auto-generated README**
- Add CSV exports for all data types
- Comprehensive testing
- Documentation

---

## Summary of Key Corrections

1. **Fixed Vote Aggregation**: Properly separate votes by judge+persona, compute majority per combination, then aggregate
2. **Added Missing Task Types**: Revision, editing, ambiguous prompts
3. **Added Multiple Recipients**: CC support for mixed-audience scenarios
4. **Fixed scipy Usage**: Use `binomtest` instead of deprecated `binom_test`
5. **Fixed Kappa Calculation**: Use `sklearn.metrics.cohen_kappa_score`
6. **Added Signal Handlers**: Graceful shutdown on Ctrl+C
7. **Added Transactional DB Writes**: Atomic inserts for related entities
8. **Added Structured Failure Logging**: Per PROMPT.md requirements
9. **Added Complete Directory Structure**: All subdirectories per specification
10. **Implemented Results Viewer TUI**: Interactive filtering and drill-down
11. **Implemented Heatmap Generation**: Visual analysis by dimension
12. **Added Format Bias Detection**: New analysis for systematic biases
13. **Corrected Three-Phase Generation**: Properly separated phases
14. **Added Tone Matching**: Tone example generation and integration
15. **Added ONET_WRITING_REFERENCE.md Integration**: Use pre-processed reference data
