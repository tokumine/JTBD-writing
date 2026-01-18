# Critique of Draft Plan 4: Gemini Writing Evaluation Framework

## Executive Summary

Draft Plan 4 provides a comprehensive and well-structured implementation plan for the Gemini Writing Evaluation Framework. It demonstrates strong technical architecture, thoughtful design decisions, and extensive code examples. However, there are several critical gaps, technical inaccuracies, and areas requiring improvement when compared against the PROMPT.md specification.

**Overall Assessment: 7.5/10** - Solid foundation with good architecture but missing critical features and contains implementation flaws.

---

## Part 1: Critical Issues and Gaps

### 1.1 MISSING: Reference to ONET_WRITING_REFERENCE.md

**PROMPT.md Requirement:**
> "OPUS has pre-processed all the tasks where effective writing might be needed and written a guide in db/ONET_WRITING_REFERENCE.md"

**Issue:** The draft plan hardcodes writing categories in `ONetExtractor.WRITING_CATEGORIES` instead of reading from the pre-processed reference document. This ignores the work already done to identify writing-relevant tasks and violates the principle of letting O*NET data drive diversity.

**Fix Required:** The implementation should read from `db/ONET_WRITING_REFERENCE.md` rather than defining its own categorization.

### 1.2 MISSING: LLM Enrichment Phase 3 Implementation

**PROMPT.md Requirement:**
> "Phase 3 - LLM Enrichment: Further enrich with LLM where context-heavy prompts require additional detail or realism."

**Issue:** The `_enrich_prompts` method is a placeholder that returns prompts unchanged:
```python
def _enrich_prompts(self, prompts: List[WritingPrompt]) -> List[WritingPrompt]:
    """Phase 3: LLM enrichment for complex prompts."""
    return prompts  # Placeholder
```

This critical feature is completely unimplemented.

**Fix Required:** Full implementation of LLM enrichment including:
- Attachment generation (mock Q3 reports, meeting notes, resumes, etc.)
- Prior message generation for reply-to contexts
- Tone example generation for tone-matching scenarios
- Temporal context additions (dates, deadlines, recent events)
- Competing objectives elaboration

### 1.3 MISSING: Phase 1 Offline LLM Generation

**PROMPT.md Requirement:**
> "Phase 1 - Offline LLM Generation: Use an LLM to generate diverse persona/context variations for each O*NET task. This is done as an offline preprocessing step."

**Issue:** Phase 1 is mentioned but not implemented. The plan jumps directly to algorithmic combinations without the offline LLM pre-generation step that should create diverse persona variations before runtime.

**Fix Required:** Implement the offline LLM generation step including:
- Persona variation generation
- Context variation generation
- Storage of pre-generated variations for runtime use
- Using evaluated models for generation (as specified)

### 1.4 MISSING: Instruction-Following Tests

**PROMPT.md Requirement:**
> "Include some prompts with explicit constraints to test instruction-following:
> - Length constraints: 'Keep this under 100 words'
> - Format requirements: 'Use exactly 3 bullet points'
> - Tone directives: 'Be direct and avoid pleasantries'
> - Exclusions: 'Do not mention the budget'"

**Issue:** While `InstructionConstraint` is defined in the schema, there's no implementation that:
- Generates prompts with these constraints
- Verifies compliance after response generation
- Tracks instruction-following separately in analysis

**Fix Required:**
- Add constraint generation logic in prompt generator
- Implement compliance checking module
- Track instruction-following metrics separately from quality judgments

### 1.5 INCOMPLETE: Refusal Categorization

**PROMPT.md Requirement:**
> "Categorize WHY models refuse for deeper analysis:
> - Safety refusal: Model cites safety/policy concerns
> - Capability limitation: Model says it can't do the task
> - Misunderstanding: Model interprets task incorrectly
> - Incomplete response: Model starts but doesn't finish
> - Off-topic: Model responds but not to the actual task"

**Issue:** The plan mentions auto-loss for failures but doesn't implement categorization of refusal types. Only generic error logging exists.

**Fix Required:**
- Implement refusal detection logic
- Add categorization of refusal types
- Track refusal rates by model and task type
- Include refusal analysis in reporting

### 1.6 MISSING: Response Metadata Tracking

**PROMPT.md Requirement:**
> "Track metadata for every response:
> - Response length (characters, words, tokens)
> - Response time (latency)
> - Format detection (bullet points, headers, paragraphs)
> - Greeting/sign-off patterns"

**Issue:** Only basic metrics (tokens, latency) are tracked. Critical analysis features are missing:
- Format detection (bullet points, headers, numbered lists)
- Greeting pattern detection ("I hope this email finds you well", etc.)
- Sign-off pattern detection
- Word/character counts separate from tokens

**Fix Required:** Add comprehensive response analysis module with:
```python
class ResponseAnalyzer:
    def analyze(self, response: str) -> ResponseMetadata:
        return ResponseMetadata(
            char_count=len(response),
            word_count=len(response.split()),
            has_bullet_points=self._detect_bullets(response),
            has_headers=self._detect_headers(response),
            has_numbered_list=self._detect_numbered(response),
            greeting_type=self._detect_greeting(response),
            signoff_type=self._detect_signoff(response),
            cliche_patterns=self._detect_cliches(response)
        )
```

### 1.7 INCOMPLETE: Systematic Bias Detection

**PROMPT.md Requirement:**
> "Report all detected biases with statistical significance:
> - Formality drift: Does one model skew formal/casual regardless of prompt?
> - Model fingerprinting: Can judges identify which model wrote which response?"

**Issue:** Bias detection implementation covers position and length bias, but misses:
- Formality drift detection
- Model fingerprinting detection
- Format bias (does one model overuse bullet points?)

**Fix Required:** Extend `BiasDetector` class with these additional bias types.

### 1.8 INCOMPLETE: Results Directory Structure

**PROMPT.md Requirement:** Detailed results directory structure with specific subdirectories and files.

**Issue:** The plan doesn't fully implement the required structure. Missing:
- `prompts/prompts_by_occupation/`
- `prompts/prompts_by_industry/`
- `responses/by_prompt/`
- `responses/by_model/`
- `judgments/raw/`
- `judgments/aggregated/`
- `analysis/weakness_analysis.json`
- `reports/executive_summary.md`
- `reports/charts/`
- `logs/run.log`
- `logs/timing.log`
- `README.md` (auto-generated)

**Fix Required:** Implement full directory structure with all required organization.

### 1.9 MISSING: Cross-Run Comparison Implementation

**PROMPT.md Requirement:**
> "Support comparing results across multiple runs"

**Issue:** The CLI has a `compare` command but it's not implemented:
```python
def compare(results_dirs):
    console.print(f"Comparing {len(results_dirs)} runs...")
    # Implementation for cross-run comparison
```

**Fix Required:** Full implementation of cross-run comparison with statistical analysis.

### 1.10 MISSING: Weakness Analysis Implementation

**PROMPT.md Requirement:**
> "Identifies specific areas of weakness in Gemini effective writing vs its peers"

**Issue:**
- `weakness_finder.py` is listed in project structure but not implemented
- `_create_weakness_analysis` in PDF generator is empty
- No systematic weakness identification logic

**Fix Required:** Implement comprehensive weakness analysis:
- By occupation type
- By writing task category
- By formality level
- By demographic segment
- By communication channel
- Statistical significance of weaknesses

---

## Part 2: Technical Issues and Bugs

### 2.1 Bug: Duplicate Response Token Saving

**Issue in database.py:**
```python
cursor.execute("""
    INSERT INTO responses (prompt_id, model, response_text, input_tokens,
                          output_tokens, latency_ms, cost, finish_reason)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    outcome.prompt_id,
    outcome.gemini_model,
    outcome.gemini_response,
    outcome.metadata.get('gemini_tokens', 0),
    outcome.metadata.get('gemini_tokens', 0),  # BUG: Same value for input and output!
    ...
))
```

Both `input_tokens` and `output_tokens` are set to `gemini_tokens`. This is incorrect.

**Fix:** Track input and output tokens separately in metadata.

### 2.2 Bug: Incorrect Cost Splitting

**Issue:** Cost is divided by 2 for each response:
```python
outcome.metadata.get('total_cost', 0) / 2
```

This assumes equal cost for both models, which is incorrect given different model pricing.

**Fix:** Track cost per model separately.

### 2.3 Issue: Synchronous Database Operations in Async Context

**Issue:** The database methods are marked as `async` but use synchronous SQLite operations:
```python
async def save_prompt(self, prompt) -> None:
    cursor = self.conn.cursor()
    cursor.execute(...)  # Synchronous!
```

This blocks the event loop.

**Fix:** Use `aiosqlite` for true async database operations:
```python
import aiosqlite

class ResultsDatabase:
    async def save_prompt(self, prompt) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(...)
            await conn.commit()
```

### 2.4 Issue: Rate Limiter Not Per-Model

**Issue:** The rate limiter is global across all models, but different models have different rate limits.

**Fix:** Implement per-model rate limiting:
```python
class PerModelRateLimiter:
    def __init__(self):
        self._request_times: Dict[str, List[datetime]] = {}
        self._limits: Dict[str, int] = {
            'gemini-3-pro': 60,
            'gpt-5.2-thinking': 30,
            # etc.
        }
```

### 2.5 Issue: Thread Safety in TUI

**Issue:** The evaluation runs in a separate thread but updates TUI state without proper synchronization:
```python
eval_thread = threading.Thread(
    target=lambda: asyncio.run(
        engine.run_evaluation(prompts, progress_callback)
    )
)
```

This can cause race conditions when updating reactive state.

**Fix:** Use proper message passing or thread-safe queues between evaluation thread and TUI.

### 2.6 Issue: Company Email Generation Unsafe

**Issue:**
```python
email=f"{writer_name.email_style}@{company.name.lower().replace(' ', '').replace(',', '')}.com"
```

This doesn't handle:
- Special characters (& in "Johnson & Johnson")
- International characters
- Multiple word names with various separators

**Fix:** Implement proper domain sanitization:
```python
def sanitize_domain(name: str) -> str:
    import re
    # Remove special chars, normalize
    clean = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    return clean[:63]  # DNS label limit
```

### 2.7 Issue: Hash for Randomization Not Portable

**Issue:**
```python
rng = random.Random(hash(prompt_id))
```

`hash()` returns different values across Python sessions (unless PYTHONHASHSEED is set).

**Fix:** Use hashlib for deterministic hashing:
```python
import hashlib
seed = int(hashlib.md5(prompt_id.encode()).hexdigest()[:8], 16)
rng = random.Random(seed)
```

### 2.8 Issue: Missing Error Handling in Judgment Parsing

**Issue:** `_parse_judgment` has minimal error handling:
```python
def _parse_judgment(self, response: str) -> tuple:
    lines = response.strip().split('\n')
    winner = 'tie'
    # ...parsing without validation
```

If the model returns malformed output, parsing silently fails and defaults to 'tie'.

**Fix:** Add robust parsing with validation and fallback strategies.

---

## Part 3: Design Issues and Suboptimal Approaches

### 3.1 Company Database Scalability

**Issue:** All companies are hardcoded in Python. This:
- Limits diversity
- Makes updates difficult
- Inflates code size

**Fix:** Store companies in JSON/CSV file or SQLite table.

### 3.2 Name Generator Ethnicity Categories

**Issue:** The name generator uses explicit ethnicity categories which could:
- Be culturally insensitive
- Miss many ethnic groups
- Create stereotypical associations

**Better Approach:** Use a larger, more diverse name pool without explicit ethnic categorization, or use census-based distribution.

### 3.3 Missing Caching for O*NET Queries

**Issue:** Every prompt generation queries the O*NET database repeatedly.

**Fix:** Cache extracted tasks after first query.

### 3.4 No Batching for API Calls

**Issue:** Judgments are collected one at a time in a loop:
```python
for judge_model in judge_models:
    for persona in personas:
        for vote_idx in range(votes_per_judge):
            judgment = await self.judge_manager.get_judgment(...)
```

**Fix:** Use `asyncio.gather` for parallel judgment collection within rate limits.

### 3.5 PDF Generation Library Choice

**Issue:** Uses ReportLab which is complex and produces basic output.

**Better Alternative:** Consider `weasyprint` (already listed in tech stack) which allows HTML/CSS-based PDF generation for better styling.

---

## Part 4: Missing PROMPT.md Features (Additional)

### 4.1 Multiple Recipients (CC Situations)

**PROMPT.md Requirement:**
> "Include scenarios with multiple audiences simultaneously:
> - Email to client, CC'd to your boss
> - Team announcement that external partners will also see"

**Issue:** Schema has `cc_recipients` but no generation logic for CC scenarios.

### 4.2 Revision & Editing Tasks

**PROMPT.md Requirement:**
> "Include prompts where the model must improve existing text:
> - 'Revise this draft to be more concise'
> - 'Make this email more professional'"

**Issue:** Schema has `existing_draft` and `is_revision_task` but no implementation.

### 4.3 Ambiguity Handling Tracking

**PROMPT.md Requirement:**
> "Include deliberately vague prompts and track:
> - Does it make reasonable assumptions?
> - Does it ask for clarification?
> - Does it hedge appropriately?
> - Does it hallucinate specific details?"

**Issue:** Schema has `is_ambiguous` but no tracking of model behavior for ambiguous prompts.

### 4.4 Sensitive Topic Tracking

**PROMPT.md Requirement:** Track and analyze sensitive topics separately.

**Issue:** `is_sensitive` and `sensitive_category` exist but:
- No separate win rate tracking for sensitive tasks
- No analysis of how models handle difficult communications
- No tracking of refusal patterns for sensitive content

### 4.5 Interactive TUI Controls

**PROMPT.md Requirement:**
> "Interactive controls: q (quit), p (pause), d (detail view), s (statistics), h (help), arrow keys (scroll)"

**Issue:** Bindings exist but implementations are stubs:
```python
def action_pause(self) -> None:
    self.log_activity("Evaluation paused...")  # Doesn't actually pause!

def action_detail(self) -> None:
    pass  # Would switch to detail view
```

### 4.6 Live Cost Tracking

**PROMPT.md Requirement:** Real-time cost tracking during evaluation.

**Issue:** Cost tracking exists in estimate but actual spent-so-far tracking during runs is incomplete.

### 4.7 CSV Export

**PROMPT.md Requirement:**
> "Allow exports to CSV"

**Issue:** `exporter.py` is listed in project structure but not implemented.

### 4.8 Judge Agreement Display

**PROMPT.md Requirement:** Show inter-judge agreement (Cohen's Kappa) in progress dashboard.

**Issue:** Kappa calculation exists in statistics but not wired to TUI display.

---

## Part 5: Strengths of the Draft Plan

Despite the issues identified above, Draft Plan 4 has several notable strengths:

### 5.1 Excellent Architecture
- Clean modular design with clear separation of concerns
- Well-organized project structure
- Appropriate use of Python best practices

### 5.2 Comprehensive Schema Design
- The `WritingPrompt` schema captures most required dimensions
- Good use of enums for type safety
- Extensible design for future features

### 5.3 Strong Evaluation Methodology
- Correct implementation of majority-of-majorities voting
- Proper position randomization for bias mitigation
- Multiple judge models for robustness

### 5.4 Good Technology Choices
- httpx for async HTTP (better than requests)
- Pydantic for validation
- Textual for modern TUI
- SQLite for simple persistence

### 5.5 Statistical Rigor
- Wilson score intervals for confidence
- Binomial tests for significance
- Cohen's Kappa for inter-rater reliability

### 5.6 Cost Awareness
- Cost estimation before runs
- Token tracking
- Pricing model integration

---

# IMPROVED PLAN

## Overview

The following improved plan addresses all critical gaps and issues identified above while preserving the strengths of the original draft.

---

## 1. Project Structure (Updated)

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── .env.example
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── presets.py
│   │   └── cost_estimator.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py        # Reads ONET_WRITING_REFERENCE.md
│   │   ├── naics_mapper.py
│   │   ├── company_database.py      # Loads from JSON
│   │   ├── name_generator.py        # Census-based names
│   │   └── companies.json           # External company data
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── enricher.py              # Phase 3 LLM enrichment (FULL)
│   │   ├── offline_generator.py     # Phase 1 offline LLM generation
│   │   ├── constraint_generator.py  # Instruction-following constraints
│   │   ├── schemas.py
│   │   └── templates.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py
│   │   ├── rate_limiter.py          # Per-model rate limiting
│   │   ├── retry_handler.py
│   │   ├── circuit_breaker.py       # NEW: Circuit breaker pattern
│   │   └── models.py
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── judge.py
│   │   ├── comparator.py
│   │   ├── aggregator.py
│   │   ├── refusal_detector.py      # NEW: Refusal categorization
│   │   ├── response_analyzer.py     # NEW: Format/pattern detection
│   │   ├── compliance_checker.py    # NEW: Instruction compliance
│   │   └── schemas.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py              # Using aiosqlite
│   │   ├── checkpoint.py
│   │   ├── exporter.py              # CSV/JSON export (FULL)
│   │   └── directory_manager.py     # NEW: Full directory structure
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py
│   │   ├── bias_detector.py         # Extended with all bias types
│   │   ├── weakness_finder.py       # FULL implementation
│   │   └── cross_run_comparator.py  # NEW: Cross-run analysis
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── progress.py              # FULL implementation
│   │   ├── viewer.py
│   │   ├── detail_screen.py         # NEW: Detail view screen
│   │   ├── stats_screen.py          # NEW: Statistics screen
│   │   └── widgets.py
│   │
│   └── reports/
│       ├── __init__.py
│       ├── pdf_generator.py         # Using weasyprint
│       ├── charts.py
│       ├── readme_generator.py      # NEW: Auto-generate README.md
│       └── templates/
│           └── report.html          # HTML template for PDF
│
├── db/
│   ├── onet.db
│   └── ONET_WRITING_REFERENCE.md    # Pre-processed writing tasks
│
├── data/
│   ├── companies.json               # Company database
│   ├── names_census.json            # Census-based name data
│   └── offline_variations/          # Phase 1 pre-generated variations
│
├── results/
│   └── .gitkeep
│
└── tests/
    └── ...
```

---

## 2. O*NET Extractor (Using ONET_WRITING_REFERENCE.md)

```python
# src/data/onet_extractor.py
import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class ONetTask:
    task_id: str
    onetsoc_code: str
    occupation_title: str
    occupation_description: str
    task: str
    task_type: str
    job_zone: int
    writing_relevance_score: float
    writing_context: Optional[str]
    email_frequency: Optional[float]
    correspondence_frequency: Optional[float]
    writing_skill_importance: Optional[float]

class ONetExtractor:
    """Extract writing-relevant tasks from O*NET using pre-processed reference."""

    def __init__(self, db_path: str, reference_path: str = "db/ONET_WRITING_REFERENCE.md"):
        self.db_path = db_path
        self.reference_path = Path(reference_path)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # Load pre-processed writing task guidance
        self._writing_guidance = self._load_writing_reference()
        self._task_cache: Optional[List[ONetTask]] = None

    def _load_writing_reference(self) -> Dict:
        """Load the OPUS-generated writing task reference."""
        if not self.reference_path.exists():
            raise FileNotFoundError(
                f"ONET_WRITING_REFERENCE.md not found at {self.reference_path}. "
                "This file should contain pre-processed writing task guidance."
            )

        content = self.reference_path.read_text()
        # Parse the reference document for task IDs, categories, guidance
        return self._parse_reference_document(content)

    def _parse_reference_document(self, content: str) -> Dict:
        """Parse the ONET_WRITING_REFERENCE.md file."""
        # Extract relevant task IDs, writing contexts, and guidance
        # This would parse the markdown structure
        guidance = {
            'relevant_task_ids': [],
            'task_contexts': {},
            'category_mappings': {}
        }

        # Parse sections from the reference document
        # ... implementation based on actual format

        return guidance

    def extract_writing_tasks(self) -> List[ONetTask]:
        """Extract all writing-relevant tasks using pre-processed reference."""
        if self._task_cache is not None:
            return self._task_cache

        tasks = []
        relevant_ids = self._writing_guidance.get('relevant_task_ids', [])

        if relevant_ids:
            # Use pre-identified task IDs from reference
            placeholders = ','.join(['?' for _ in relevant_ids])
            query = f"""
                SELECT DISTINCT
                    t.task_id,
                    t.onetsoc_code,
                    o.title as occupation_title,
                    o.description as occupation_description,
                    t.task,
                    t.task_type,
                    jz.job_zone,
                    wc_email.data_value as email_freq,
                    wc_letter.data_value as letter_freq,
                    sk.data_value as writing_skill
                FROM task_statements t
                JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
                LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
                LEFT JOIN work_context wc_email
                    ON t.onetsoc_code = wc_email.onetsoc_code
                    AND wc_email.element_id = '4.C.1.a.2.h'
                    AND wc_email.scale_id = 'CX'
                LEFT JOIN work_context wc_letter
                    ON t.onetsoc_code = wc_letter.onetsoc_code
                    AND wc_letter.element_id = '4.C.1.a.2.j'
                    AND wc_letter.scale_id = 'CX'
                LEFT JOIN skills sk
                    ON t.onetsoc_code = sk.onetsoc_code
                    AND sk.element_id = '2.A.1.c'
                    AND sk.scale_id = 'IM'
                WHERE t.task_id IN ({placeholders})
            """
            cursor = self.conn.execute(query, relevant_ids)
        else:
            # Fallback: use writing skill importance threshold
            query = """
                SELECT DISTINCT
                    t.task_id,
                    t.onetsoc_code,
                    o.title as occupation_title,
                    o.description as occupation_description,
                    t.task,
                    t.task_type,
                    jz.job_zone,
                    wc_email.data_value as email_freq,
                    wc_letter.data_value as letter_freq,
                    sk.data_value as writing_skill
                FROM task_statements t
                JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
                LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
                LEFT JOIN work_context wc_email
                    ON t.onetsoc_code = wc_email.onetsoc_code
                    AND wc_email.element_id = '4.C.1.a.2.h'
                LEFT JOIN work_context wc_letter
                    ON t.onetsoc_code = wc_letter.onetsoc_code
                    AND wc_letter.element_id = '4.C.1.a.2.j'
                LEFT JOIN skills sk
                    ON t.onetsoc_code = sk.onetsoc_code
                    AND sk.element_id = '2.A.1.c'
                    AND sk.scale_id = 'IM'
                WHERE sk.data_value >= 3.0
                   OR wc_email.data_value >= 3.0
                   OR wc_letter.data_value >= 3.0
            """
            cursor = self.conn.execute(query)

        for row in cursor:
            # Get additional context from reference
            task_context = self._writing_guidance.get('task_contexts', {}).get(
                row['task_id'], {}
            )

            tasks.append(ONetTask(
                task_id=row['task_id'],
                onetsoc_code=row['onetsoc_code'],
                occupation_title=row['occupation_title'],
                occupation_description=row['occupation_description'],
                task=row['task'],
                task_type=row['task_type'] or 'Unknown',
                job_zone=row['job_zone'] or 3,
                writing_relevance_score=task_context.get('relevance_score', 0.5),
                writing_context=task_context.get('context'),
                email_frequency=row['email_freq'],
                correspondence_frequency=row['letter_freq'],
                writing_skill_importance=row['writing_skill']
            ))

        self._task_cache = tasks
        return tasks
```

---

## 3. Phase 1: Offline LLM Generation

```python
# src/prompts/offline_generator.py
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
import hashlib

from ..api.openrouter_client import OpenRouterClient
from ..data.onet_extractor import ONetTask

@dataclass
class PersonaVariation:
    variation_id: str
    task_id: str
    writer_name: str
    writer_role: str
    writer_generation: str
    writer_context: str
    recipient_name: str
    recipient_role: str
    recipient_relationship: str
    company_context: str
    scenario_details: str
    communication_channel: str
    formality_suggestion: str
    urgency_context: str
    emotional_context: str

class OfflineLLMGenerator:
    """Phase 1: Generate diverse persona/context variations offline."""

    GENERATION_PROMPT = '''You are helping create diverse, realistic writing scenarios.

Given this O*NET task: "{task}"
For occupation: {occupation} (Job Zone {job_zone})

Generate 5 diverse persona/context variations for this writing task. Each should feel like a real workplace scenario.

For each variation, provide:
1. Writer name (diverse, realistic)
2. Writer role/title (appropriate for this occupation)
3. Writer generation (Gen Z, Millennial, Gen X, or Boomer - vary these)
4. Writer context (brief background)
5. Recipient name (diverse, realistic)
6. Recipient role
7. Relationship to writer (boss, peer, direct report, client, etc.)
8. Company context (real company name if possible, or realistic fictional company with size)
9. Scenario details (what's the specific situation?)
10. Communication channel (email, memo, report, slack, etc.)
11. Suggested formality level (1-5)
12. Urgency context (if any)
13. Emotional context (routine, crisis, celebration, conflict, bad news, etc.)

Output as JSON array with keys: writer_name, writer_role, writer_generation, writer_context, recipient_name, recipient_role, recipient_relationship, company_context, scenario_details, communication_channel, formality_suggestion, urgency_context, emotional_context

Be creative and diverse - avoid generic scenarios. Include some challenging situations.'''

    def __init__(
        self,
        api_client: OpenRouterClient,
        output_dir: Path,
        models_to_use: List[str]
    ):
        self.api_client = api_client
        self.output_dir = output_dir
        self.models_to_use = models_to_use
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_variations(
        self,
        tasks: List[ONetTask],
        variations_per_task: int = 5
    ) -> Dict[str, List[PersonaVariation]]:
        """Generate persona variations for all tasks."""
        all_variations = {}

        for task in tasks:
            # Check if already generated
            cache_file = self.output_dir / f"{task.task_id}.json"
            if cache_file.exists():
                with open(cache_file) as f:
                    all_variations[task.task_id] = [
                        PersonaVariation(**v) for v in json.load(f)
                    ]
                continue

            # Generate using each model (for balance)
            task_variations = []
            for model in self.models_to_use:
                try:
                    variations = await self._generate_for_task(task, model)
                    task_variations.extend(variations)
                except Exception as e:
                    print(f"Warning: Generation failed for {task.task_id} with {model}: {e}")

            # Save to cache
            if task_variations:
                with open(cache_file, 'w') as f:
                    json.dump([v.__dict__ for v in task_variations], f, indent=2)
                all_variations[task.task_id] = task_variations

        return all_variations

    async def _generate_for_task(
        self,
        task: ONetTask,
        model: str
    ) -> List[PersonaVariation]:
        """Generate variations for a single task using specified model."""
        prompt = self.GENERATION_PROMPT.format(
            task=task.task,
            occupation=task.occupation_title,
            job_zone=task.job_zone
        )

        response = await self.api_client.complete(
            model,
            prompt,
            temperature=0.9  # Higher for diversity
        )

        # Parse JSON response
        try:
            # Extract JSON from response
            content = response.content
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            variations_data = json.loads(content)

            variations = []
            for i, v in enumerate(variations_data):
                var_id = hashlib.md5(
                    f"{task.task_id}_{model}_{i}".encode()
                ).hexdigest()[:12]

                variations.append(PersonaVariation(
                    variation_id=var_id,
                    task_id=task.task_id,
                    **v
                ))

            return variations

        except json.JSONDecodeError:
            print(f"Warning: Could not parse JSON for task {task.task_id}")
            return []
```

---

## 4. Phase 3: LLM Enrichment (Full Implementation)

```python
# src/prompts/enricher.py
import asyncio
from typing import List, Optional
from dataclasses import dataclass
import json

from ..api.openrouter_client import OpenRouterClient
from .schemas import WritingPrompt, Attachment, CompetingObjectives

class PromptEnricher:
    """Phase 3: Enrich prompts with LLM-generated context."""

    ATTACHMENT_PROMPT = '''Generate realistic mock content for a workplace document.

Context: {context}
Document type: {doc_type}
Purpose: {purpose}

Generate a concise but realistic summary/excerpt of this document (100-200 words).
Include specific but plausible details (names, numbers, dates).
Format appropriately for the document type.

Output the document content directly, no preamble.'''

    PRIOR_MESSAGE_PROMPT = '''Generate a realistic prior email/message that requires a response.

Context: {context}
Sender: {sender}
Topic: {topic}
Tone: {tone}

Generate a realistic message (50-150 words) that the recipient must respond to.
Make it feel authentic to workplace communication.
Include specific details that require addressing in the reply.

Output the message directly, no preamble.'''

    COMPETING_OBJECTIVES_PROMPT = '''Given this writing task, identify realistic competing objectives the writer must navigate.

Task: {task}
Context: {context}

Identify TWO competing objectives that create tension in this communication.
Examples: "be brief" vs "be comprehensive", "be direct" vs "be diplomatic"

Output as JSON: {{"objective_a": "...", "objective_b": "...", "tension_context": "..."}}'''

    def __init__(
        self,
        api_client: OpenRouterClient,
        enrichment_model: str = "gemini-3-pro"
    ):
        self.api_client = api_client
        self.enrichment_model = enrichment_model

    async def enrich_prompts(
        self,
        prompts: List[WritingPrompt],
        enrich_ratio: float = 0.3  # Enrich 30% of prompts
    ) -> List[WritingPrompt]:
        """Enrich prompts with additional context."""
        import random

        # Determine which prompts to enrich
        num_to_enrich = int(len(prompts) * enrich_ratio)
        indices_to_enrich = set(random.sample(range(len(prompts)), num_to_enrich))

        enriched = []
        tasks = []

        for i, prompt in enumerate(prompts):
            if i in indices_to_enrich:
                tasks.append(self._enrich_single_prompt(prompt))
            else:
                enriched.append(prompt)

        # Run enrichment in parallel batches
        batch_size = 10
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    print(f"Enrichment failed: {result}")
                else:
                    enriched.append(result)

        return enriched

    async def _enrich_single_prompt(self, prompt: WritingPrompt) -> WritingPrompt:
        """Enrich a single prompt with context."""
        enrichments = []

        # Decide what enrichments to add based on prompt characteristics
        if prompt.message_position.value in ['reply', 'follow_up']:
            enrichments.append(self._add_prior_message(prompt))

        if prompt.communication_channel in ['report', 'memo', 'presentation']:
            enrichments.append(self._add_attachment(prompt))

        if prompt.emotional_context.value in ['conflict', 'bad_news', 'crisis']:
            enrichments.append(self._add_competing_objectives(prompt))

        # 20% chance of adding temporal context
        import random
        if random.random() < 0.2:
            enrichments.append(self._add_temporal_context(prompt))

        # Run all enrichments
        results = await asyncio.gather(*enrichments, return_exceptions=True)

        # Apply successful enrichments
        for result in results:
            if isinstance(result, dict) and not isinstance(result, Exception):
                if 'prior_message' in result:
                    prompt.prior_message = result['prior_message']
                if 'attachments' in result:
                    prompt.attachments = result['attachments']
                if 'competing_objectives' in result:
                    prompt.competing_objectives = result['competing_objectives']
                if 'temporal' in result:
                    prompt.current_date = result['temporal'].get('date')
                    prompt.deadline = result['temporal'].get('deadline')
                    prompt.recent_event = result['temporal'].get('event')

        # Rebuild prompt text with enrichments
        prompt.prompt_text = self._build_enriched_prompt_text(prompt)

        return prompt

    async def _add_prior_message(self, prompt: WritingPrompt) -> dict:
        """Generate a prior message for reply context."""
        context = f"{prompt.occupation_title} at {prompt.company}"
        sender = f"{prompt.recipient.name}, {prompt.recipient.role}"
        topic = prompt.onet_task
        tone = "professional" if prompt.formality_level.value >= 3 else "casual"

        response = await self.api_client.complete(
            self.enrichment_model,
            self.PRIOR_MESSAGE_PROMPT.format(
                context=context,
                sender=sender,
                topic=topic,
                tone=tone
            ),
            temperature=0.7
        )

        return {'prior_message': response.content.strip()}

    async def _add_attachment(self, prompt: WritingPrompt) -> dict:
        """Generate mock attachment content."""
        doc_types = {
            'report': 'quarterly performance report',
            'memo': 'policy update memo',
            'presentation': 'meeting agenda and notes',
            'email': 'previous correspondence'
        }

        doc_type = doc_types.get(prompt.communication_channel, 'supporting document')

        response = await self.api_client.complete(
            self.enrichment_model,
            self.ATTACHMENT_PROMPT.format(
                context=f"{prompt.occupation_title} at {prompt.company}",
                doc_type=doc_type,
                purpose=prompt.onet_task
            ),
            temperature=0.7
        )

        attachment = Attachment(
            type=prompt.communication_channel,
            description=f"Attached {doc_type}",
            content=response.content.strip()
        )

        return {'attachments': [attachment]}

    async def _add_competing_objectives(self, prompt: WritingPrompt) -> dict:
        """Generate competing objectives."""
        response = await self.api_client.complete(
            self.enrichment_model,
            self.COMPETING_OBJECTIVES_PROMPT.format(
                task=prompt.onet_task,
                context=f"{prompt.writer.role} writing to {prompt.recipient.role}"
            ),
            temperature=0.5
        )

        try:
            data = json.loads(response.content)
            objectives = CompetingObjectives(
                objective_a=data['objective_a'],
                objective_b=data['objective_b'],
                context=data.get('tension_context')
            )
            return {'competing_objectives': objectives}
        except:
            return {}

    async def _add_temporal_context(self, prompt: WritingPrompt) -> dict:
        """Add temporal grounding."""
        from datetime import datetime, timedelta
        import random

        base_date = datetime(2026, 1, 6)  # Project date

        # Random deadline in next 1-14 days
        deadline_days = random.randint(1, 14)
        deadline = base_date + timedelta(days=deadline_days)

        # Random recent event
        events = [
            "last week's team meeting",
            "the recent reorganization announcement",
            "the Q4 results release",
            "yesterday's client call",
            "the board meeting earlier this week"
        ]

        return {
            'temporal': {
                'date': base_date.strftime('%B %d, %Y'),
                'deadline': deadline.strftime('%A, %B %d'),
                'event': random.choice(events) if random.random() < 0.5 else None
            }
        }

    def _build_enriched_prompt_text(self, prompt: WritingPrompt) -> str:
        """Build the full prompt text with all enrichments."""
        parts = [
            f"You are {prompt.writer.name}, {prompt.writer.role} at {prompt.company}.",
            ""
        ]

        # Add temporal context
        if prompt.current_date:
            parts.append(f"Today's date: {prompt.current_date}")
        if prompt.deadline:
            parts.append(f"Deadline: {prompt.deadline}")
        if prompt.recent_event:
            parts.append(f"Context: Following {prompt.recent_event}")

        parts.extend([
            "",
            f"**Task**: {prompt.onet_task}",
            "",
            f"**Recipient**: {prompt.recipient.name}, {prompt.recipient.role}"
        ])

        if prompt.recipient.relationship_to_writer:
            parts.append(f"**Relationship**: {prompt.recipient.relationship_to_writer}")

        parts.extend([
            f"**Communication type**: {prompt.communication_channel}",
            f"**Formality level**: {prompt.formality_level.name.replace('_', ' ').title()}"
        ])

        if prompt.urgency_level.value >= 3:
            parts.append(f"**Urgency**: {prompt.urgency_level.name}")

        # Add prior message if present
        if prompt.prior_message:
            parts.extend([
                "",
                "---",
                "**Prior message to respond to:**",
                "",
                prompt.prior_message,
                "---",
                ""
            ])

        # Add attachments if present
        if prompt.attachments:
            for att in prompt.attachments:
                parts.extend([
                    "",
                    f"**Referenced document ({att.description}):**",
                    "",
                    att.content,
                    "---",
                    ""
                ])

        # Add competing objectives if present
        if prompt.competing_objectives:
            parts.extend([
                "",
                f"**Note**: Balance {prompt.competing_objectives.objective_a} "
                f"with {prompt.competing_objectives.objective_b}."
            ])

        parts.extend(["", "Write the communication now."])

        return "\n".join(parts)
```

---

## 5. Response Analyzer (New Component)

```python
# src/eval/response_analyzer.py
import re
from dataclasses import dataclass
from typing import List, Optional, Set
from enum import Enum

class GreetingType(Enum):
    FORMAL_DEAR = "formal_dear"
    CASUAL_HI = "casual_hi"
    NAME_ONLY = "name_only"
    NO_GREETING = "no_greeting"
    CLICHE_HOPE = "cliche_hope_finds_well"

class SignoffType(Enum):
    FORMAL_REGARDS = "formal_regards"
    CASUAL_THANKS = "casual_thanks"
    BEST = "best"
    NONE = "none"
    CLICHE_HESITATE = "cliche_dont_hesitate"

@dataclass
class ResponseMetadata:
    char_count: int
    word_count: int
    sentence_count: int
    paragraph_count: int

    has_bullet_points: bool
    has_numbered_list: bool
    has_headers: bool
    has_bold_text: bool

    greeting_type: Optional[GreetingType]
    signoff_type: Optional[SignoffType]

    cliche_patterns: List[str]
    ai_markers: List[str]

    estimated_reading_time_seconds: int

class ResponseAnalyzer:
    """Analyze response metadata for systematic bias detection."""

    CLICHE_PATTERNS = [
        r"hope this (email |message |)finds you well",
        r"please don'?t hesitate to (reach out|contact)",
        r"I'?m happy to help",
        r"let me know if you have any questions",
        r"I hope this helps",
        r"please feel free to",
        r"at your earliest convenience",
        r"just wanted to (follow up|check in|reach out)",
        r"as per (our|my|your)",
        r"pursuant to",
        r"in regards to",
        r"I wanted to take a moment",
        r"I trust this",
        r"moving forward",
        r"circle back",
        r"touch base",
        r"ping me",
        r"loop (you |me |them )in",
    ]

    AI_MARKER_PATTERNS = [
        r"As an AI",
        r"I don'?t have (personal |)feelings",
        r"I'?m (just |)a (language |AI |)model",
        r"I cannot (actually |truly |)",
        r"[Cc]ertainly[!,]? (I |Here)",
        r"[Aa]bsolutely[!,]? (I |Here|Let)",
        r"^(Sure|Of course|Certainly|Absolutely)[!,]",
        r"I'?d be happy to",
        r"Great question",
    ]

    def __init__(self):
        self.cliche_re = [re.compile(p, re.IGNORECASE) for p in self.CLICHE_PATTERNS]
        self.ai_marker_re = [re.compile(p) for p in self.AI_MARKER_PATTERNS]

    def analyze(self, response: str) -> ResponseMetadata:
        """Perform comprehensive response analysis."""
        # Basic counts
        char_count = len(response)
        words = response.split()
        word_count = len(words)
        sentences = re.split(r'[.!?]+', response)
        sentence_count = len([s for s in sentences if s.strip()])
        paragraphs = response.split('\n\n')
        paragraph_count = len([p for p in paragraphs if p.strip()])

        # Structure detection
        has_bullet_points = bool(re.search(r'^[\s]*[-*•]', response, re.MULTILINE))
        has_numbered_list = bool(re.search(r'^[\s]*\d+[.)]\s', response, re.MULTILINE))
        has_headers = bool(re.search(r'^#{1,6}\s|^[A-Z][^.!?]*:$', response, re.MULTILINE))
        has_bold_text = '**' in response or '__' in response

        # Greeting detection
        greeting_type = self._detect_greeting(response)

        # Signoff detection
        signoff_type = self._detect_signoff(response)

        # Cliche detection
        cliche_patterns = self._detect_cliches(response)

        # AI marker detection
        ai_markers = self._detect_ai_markers(response)

        # Reading time (average 200 wpm)
        reading_time = max(1, word_count // 200 * 60)

        return ResponseMetadata(
            char_count=char_count,
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            has_bullet_points=has_bullet_points,
            has_numbered_list=has_numbered_list,
            has_headers=has_headers,
            has_bold_text=has_bold_text,
            greeting_type=greeting_type,
            signoff_type=signoff_type,
            cliche_patterns=cliche_patterns,
            ai_markers=ai_markers,
            estimated_reading_time_seconds=reading_time
        )

    def _detect_greeting(self, response: str) -> Optional[GreetingType]:
        """Detect the type of greeting used."""
        first_line = response.split('\n')[0].lower().strip()

        if 'hope this' in first_line and 'finds you well' in first_line:
            return GreetingType.CLICHE_HOPE
        elif first_line.startswith('dear '):
            return GreetingType.FORMAL_DEAR
        elif first_line.startswith(('hi ', 'hey ', 'hello ')):
            return GreetingType.CASUAL_HI
        elif re.match(r'^[A-Z][a-z]+,?$', first_line):
            return GreetingType.NAME_ONLY
        else:
            return GreetingType.NO_GREETING

    def _detect_signoff(self, response: str) -> Optional[SignoffType]:
        """Detect the type of sign-off used."""
        lines = response.strip().split('\n')
        last_lines = '\n'.join(lines[-3:]).lower()

        if "don't hesitate" in last_lines or "do not hesitate" in last_lines:
            return SignoffType.CLICHE_HESITATE
        elif any(x in last_lines for x in ['best regards', 'kind regards', 'sincerely', 'regards,']):
            return SignoffType.FORMAL_REGARDS
        elif 'thank' in last_lines:
            return SignoffType.CASUAL_THANKS
        elif 'best,' in last_lines or 'best\n' in last_lines:
            return SignoffType.BEST
        else:
            return SignoffType.NONE

    def _detect_cliches(self, response: str) -> List[str]:
        """Detect cliche patterns in response."""
        found = []
        for pattern in self.cliche_re:
            if pattern.search(response):
                found.append(pattern.pattern)
        return found

    def _detect_ai_markers(self, response: str) -> List[str]:
        """Detect patterns that suggest AI-generated content."""
        found = []
        for pattern in self.ai_marker_re:
            if pattern.search(response):
                found.append(pattern.pattern)
        return found
```

---

## 6. Refusal Detector (New Component)

```python
# src/eval/refusal_detector.py
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
import re

class RefusalType(Enum):
    SAFETY = "safety"           # Model cites safety/policy
    CAPABILITY = "capability"   # Model says it can't do task
    MISUNDERSTANDING = "misunderstanding"  # Model misinterprets
    INCOMPLETE = "incomplete"   # Model starts but doesn't finish
    OFF_TOPIC = "off_topic"     # Model responds to wrong thing
    NONE = "none"               # No refusal detected

@dataclass
class RefusalAnalysis:
    is_refusal: bool
    refusal_type: RefusalType
    confidence: float
    evidence: str
    original_response: str

class RefusalDetector:
    """Detect and categorize model refusals."""

    SAFETY_PATTERNS = [
        r"I (cannot|can't|am unable to|won't) (help with|assist with|provide|generate|write|create)",
        r"(violates|against) (my|our) (policies|guidelines|terms)",
        r"(potentially|could be) (harmful|dangerous|inappropriate)",
        r"I'm not (able|allowed|permitted) to",
        r"(ethical|safety) (concerns|considerations|guidelines)",
        r"goes against my (programming|design|principles)",
    ]

    CAPABILITY_PATTERNS = [
        r"I don't have (access|the ability|information)",
        r"(beyond|outside) my (capabilities|abilities|scope)",
        r"I'm (just|only) a (language model|AI|text-based)",
        r"I cannot (actually|physically|literally)",
        r"I don't have (real-time|current|up-to-date) (access|information)",
    ]

    MISUNDERSTANDING_PATTERNS = [
        r"I (think|believe) you('re| are) asking",
        r"(unclear|not sure) what you mean",
        r"(did you mean|are you asking)",
        r"I'm (confused|not certain) about",
    ]

    def __init__(self):
        self.safety_re = [re.compile(p, re.IGNORECASE) for p in self.SAFETY_PATTERNS]
        self.capability_re = [re.compile(p, re.IGNORECASE) for p in self.CAPABILITY_PATTERNS]
        self.misunderstanding_re = [re.compile(p, re.IGNORECASE) for p in self.MISUNDERSTANDING_PATTERNS]

    def analyze(
        self,
        response: str,
        prompt: str,
        expected_min_length: int = 50
    ) -> RefusalAnalysis:
        """Analyze response for refusal patterns."""

        # Check for empty/very short response
        if len(response.strip()) < expected_min_length:
            return RefusalAnalysis(
                is_refusal=True,
                refusal_type=RefusalType.INCOMPLETE,
                confidence=0.9,
                evidence=f"Response too short ({len(response)} chars)",
                original_response=response
            )

        # Check for safety refusal
        for pattern in self.safety_re:
            match = pattern.search(response)
            if match:
                return RefusalAnalysis(
                    is_refusal=True,
                    refusal_type=RefusalType.SAFETY,
                    confidence=0.95,
                    evidence=match.group(),
                    original_response=response
                )

        # Check for capability refusal
        for pattern in self.capability_re:
            match = pattern.search(response)
            if match:
                return RefusalAnalysis(
                    is_refusal=True,
                    refusal_type=RefusalType.CAPABILITY,
                    confidence=0.85,
                    evidence=match.group(),
                    original_response=response
                )

        # Check for misunderstanding
        for pattern in self.misunderstanding_re:
            match = pattern.search(response)
            if match:
                return RefusalAnalysis(
                    is_refusal=True,
                    refusal_type=RefusalType.MISUNDERSTANDING,
                    confidence=0.7,
                    evidence=match.group(),
                    original_response=response
                )

        # Check for off-topic (basic keyword overlap check)
        if self._is_off_topic(response, prompt):
            return RefusalAnalysis(
                is_refusal=True,
                refusal_type=RefusalType.OFF_TOPIC,
                confidence=0.6,
                evidence="Low keyword overlap with prompt",
                original_response=response
            )

        return RefusalAnalysis(
            is_refusal=False,
            refusal_type=RefusalType.NONE,
            confidence=0.0,
            evidence="",
            original_response=response
        )

    def _is_off_topic(self, response: str, prompt: str) -> bool:
        """Check if response is off-topic using keyword overlap."""
        # Extract significant words from prompt
        prompt_words = set(
            w.lower() for w in re.findall(r'\b\w{4,}\b', prompt)
        )
        response_words = set(
            w.lower() for w in re.findall(r'\b\w{4,}\b', response)
        )

        if not prompt_words:
            return False

        overlap = len(prompt_words & response_words) / len(prompt_words)
        return overlap < 0.1  # Less than 10% overlap suggests off-topic
```

---

## 7. Weakness Finder (Full Implementation)

```python
# src/analysis/weakness_finder.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from collections import defaultdict
import numpy as np
from scipy import stats

@dataclass
class Weakness:
    dimension: str          # e.g., "occupation", "formality", "channel"
    dimension_value: str    # e.g., "Legal", "Very Formal", "email"
    win_rate: float
    confidence_interval: tuple
    n_samples: int
    p_value: float
    severity: str          # "critical", "moderate", "minor"
    description: str
    example_prompt_ids: List[str]

@dataclass
class WeaknessReport:
    model_pair: str
    total_comparisons: int
    overall_win_rate: float
    weaknesses: List[Weakness]
    strongest_areas: List[Weakness]
    recommendations: List[str]

class WeaknessFinder:
    """Identify specific areas of weakness in Gemini vs competitors."""

    DIMENSIONS = [
        'occupation_title',
        'writing_category',
        'communication_channel',
        'formality_level',
        'urgency_level',
        'emotional_context',
        'job_zone',
        'industry_name',
        'is_sensitive',
        'message_position',
        'audience_size'
    ]

    WEAKNESS_THRESHOLD = 0.45  # Win rate below this is concerning
    STRENGTH_THRESHOLD = 0.55  # Win rate above this is a strength
    MIN_SAMPLES = 20           # Minimum samples for significance

    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.z_score = stats.norm.ppf((1 + confidence_level) / 2)

    def find_weaknesses(
        self,
        results: List[Dict[str, Any]],
        model_pair: str
    ) -> WeaknessReport:
        """Find all weaknesses for a model pair."""

        # Filter to relevant model pair
        pair_results = [r for r in results
                       if f"{r['gemini_model']}_vs_{r['opponent_model']}" == model_pair]

        if not pair_results:
            return WeaknessReport(
                model_pair=model_pair,
                total_comparisons=0,
                overall_win_rate=0.5,
                weaknesses=[],
                strongest_areas=[],
                recommendations=[]
            )

        # Overall stats
        total = len(pair_results)
        gemini_wins = sum(1 for r in pair_results if r['result'] == 'gemini_wins')
        overall_win_rate = gemini_wins / total if total > 0 else 0.5

        weaknesses = []
        strengths = []

        # Analyze each dimension
        for dimension in self.DIMENSIONS:
            dim_analysis = self._analyze_dimension(pair_results, dimension)

            for value, analysis in dim_analysis.items():
                if analysis['n'] < self.MIN_SAMPLES:
                    continue

                if analysis['win_rate'] < self.WEAKNESS_THRESHOLD:
                    severity = self._determine_severity(
                        analysis['win_rate'],
                        overall_win_rate
                    )
                    weaknesses.append(Weakness(
                        dimension=dimension,
                        dimension_value=str(value),
                        win_rate=analysis['win_rate'],
                        confidence_interval=(analysis['ci_lower'], analysis['ci_upper']),
                        n_samples=analysis['n'],
                        p_value=analysis['p_value'],
                        severity=severity,
                        description=self._describe_weakness(
                            dimension, value, analysis['win_rate'], overall_win_rate
                        ),
                        example_prompt_ids=analysis['example_losses'][:5]
                    ))

                elif analysis['win_rate'] > self.STRENGTH_THRESHOLD:
                    strengths.append(Weakness(
                        dimension=dimension,
                        dimension_value=str(value),
                        win_rate=analysis['win_rate'],
                        confidence_interval=(analysis['ci_lower'], analysis['ci_upper']),
                        n_samples=analysis['n'],
                        p_value=analysis['p_value'],
                        severity='strength',
                        description=self._describe_strength(
                            dimension, value, analysis['win_rate']
                        ),
                        example_prompt_ids=analysis['example_wins'][:5]
                    ))

        # Sort by severity/win rate
        weaknesses.sort(key=lambda w: w.win_rate)
        strengths.sort(key=lambda w: -w.win_rate)

        # Generate recommendations
        recommendations = self._generate_recommendations(weaknesses, overall_win_rate)

        return WeaknessReport(
            model_pair=model_pair,
            total_comparisons=total,
            overall_win_rate=overall_win_rate,
            weaknesses=weaknesses,
            strongest_areas=strengths[:10],
            recommendations=recommendations
        )

    def _analyze_dimension(
        self,
        results: List[Dict[str, Any]],
        dimension: str
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze win rates for each value in a dimension."""
        by_value = defaultdict(lambda: {
            'gemini_wins': 0, 'opponent_wins': 0, 'ties': 0,
            'example_wins': [], 'example_losses': []
        })

        for r in results:
            value = r.get(dimension, 'unknown')
            if value is None:
                value = 'unknown'

            if r['result'] == 'gemini_wins':
                by_value[value]['gemini_wins'] += 1
                by_value[value]['example_wins'].append(r['prompt_id'])
            elif r['result'] == 'opponent_wins':
                by_value[value]['opponent_wins'] += 1
                by_value[value]['example_losses'].append(r['prompt_id'])
            else:
                by_value[value]['ties'] += 1

        analysis = {}
        for value, counts in by_value.items():
            n = counts['gemini_wins'] + counts['opponent_wins']
            if n == 0:
                continue

            win_rate = counts['gemini_wins'] / n

            # Wilson score interval
            ci_lower, ci_upper = self._wilson_interval(counts['gemini_wins'], n)

            # Binomial test against 50%
            result = stats.binomtest(counts['gemini_wins'], n, 0.5)

            analysis[value] = {
                'win_rate': win_rate,
                'n': n,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'p_value': result.pvalue,
                'example_wins': counts['example_wins'],
                'example_losses': counts['example_losses']
            }

        return analysis

    def _wilson_interval(self, successes: int, n: int) -> tuple:
        """Calculate Wilson score confidence interval."""
        if n == 0:
            return (0.0, 1.0)

        p = successes / n
        denominator = 1 + self.z_score ** 2 / n
        center = (p + self.z_score ** 2 / (2 * n)) / denominator
        spread = self.z_score * np.sqrt(
            (p * (1 - p) + self.z_score ** 2 / (4 * n)) / n
        ) / denominator

        return (max(0, center - spread), min(1, center + spread))

    def _determine_severity(self, win_rate: float, overall: float) -> str:
        """Determine severity of weakness."""
        if win_rate < 0.35:
            return 'critical'
        elif win_rate < 0.40:
            return 'moderate'
        else:
            return 'minor'

    def _describe_weakness(
        self,
        dimension: str,
        value: str,
        win_rate: float,
        overall: float
    ) -> str:
        """Generate human-readable weakness description."""
        dim_names = {
            'occupation_title': 'occupation',
            'writing_category': 'writing type',
            'communication_channel': 'communication channel',
            'formality_level': 'formality level',
            'job_zone': 'skill level',
            'industry_name': 'industry',
            'emotional_context': 'emotional context'
        }
        dim_name = dim_names.get(dimension, dimension.replace('_', ' '))

        delta = (overall - win_rate) * 100
        return (
            f"Gemini underperforms by {delta:.1f}pp on {dim_name}='{value}' "
            f"(win rate: {win_rate*100:.1f}% vs overall {overall*100:.1f}%)"
        )

    def _describe_strength(
        self,
        dimension: str,
        value: str,
        win_rate: float
    ) -> str:
        """Generate human-readable strength description."""
        dim_names = {
            'occupation_title': 'occupation',
            'writing_category': 'writing type',
            'communication_channel': 'channel',
        }
        dim_name = dim_names.get(dimension, dimension.replace('_', ' '))
        return f"Strong performance on {dim_name}='{value}' (win rate: {win_rate*100:.1f}%)"

    def _generate_recommendations(
        self,
        weaknesses: List[Weakness],
        overall: float
    ) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        # Group weaknesses by dimension
        by_dim = defaultdict(list)
        for w in weaknesses:
            by_dim[w.dimension].append(w)

        # Critical weaknesses first
        critical = [w for w in weaknesses if w.severity == 'critical']
        if critical:
            recs.append(
                f"CRITICAL: Address severe underperformance in {len(critical)} areas "
                f"where win rate is below 35%"
            )

        # Dimension-specific recommendations
        for dim, weak_list in by_dim.items():
            if len(weak_list) >= 3:
                values = ', '.join(w.dimension_value for w in weak_list[:3])
                recs.append(
                    f"Systematic weakness in {dim.replace('_', ' ')}: "
                    f"particularly {values}"
                )

        # Overall assessment
        if overall < 0.45:
            recs.append(
                "Overall performance is below par - consider broad model improvements"
            )
        elif overall > 0.55:
            recs.append(
                "Good overall performance - focus on specific weak areas listed above"
            )

        return recs
```

---

## 8. Directory Manager (Full Implementation)

```python
# src/storage/directory_manager.py
from pathlib import Path
from datetime import datetime
import json
import os

class DirectoryManager:
    """Manage the full directory structure for evaluation runs."""

    def __init__(self, base_dir: str = "results"):
        self.base_dir = Path(base_dir)
        self.current_run_dir: Optional[Path] = None

    def create_run_directory(self, preset_name: str = "") -> Path:
        """Create a new timestamped run directory with full structure."""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        run_dir = self.base_dir / f"eval_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create full directory structure
        subdirs = [
            'prompts',
            'prompts/prompts_by_occupation',
            'prompts/prompts_by_industry',
            'responses',
            'responses/by_prompt',
            'responses/by_model',
            'judgments',
            'judgments/raw',
            'judgments/aggregated',
            'analysis',
            'reports',
            'reports/charts',
            'logs'
        ]

        for subdir in subdirs:
            (run_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Create initial files
        (run_dir / 'random_seed.txt').touch()
        (run_dir / 'results_summary.csv').touch()

        # Update symlink to latest
        latest_link = self.base_dir / 'latest'
        if latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(run_dir.name)

        self.current_run_dir = run_dir
        return run_dir

    def save_config(self, config: dict):
        """Save configuration to run directory."""
        if not self.current_run_dir:
            raise ValueError("No run directory created")

        # JSON config
        with open(self.current_run_dir / 'config.json', 'w') as f:
            json.dump(config, f, indent=2, default=str)

        # Human-readable summary
        summary = self._generate_config_summary(config)
        (self.current_run_dir / 'config_summary.txt').write_text(summary)

    def save_random_seed(self, seed: int):
        """Save random seed for reproducibility."""
        if self.current_run_dir:
            (self.current_run_dir / 'random_seed.txt').write_text(str(seed))

    def save_prompt_by_occupation(self, prompt: dict, occupation_code: str):
        """Save prompt organized by occupation."""
        if not self.current_run_dir:
            return

        occ_dir = self.current_run_dir / 'prompts' / 'prompts_by_occupation' / occupation_code[:2]
        occ_dir.mkdir(parents=True, exist_ok=True)

        with open(occ_dir / f"{prompt['prompt_id']}.json", 'w') as f:
            json.dump(prompt, f, indent=2)

    def save_prompt_by_industry(self, prompt: dict, naics_code: str):
        """Save prompt organized by industry."""
        if not self.current_run_dir:
            return

        ind_dir = self.current_run_dir / 'prompts' / 'prompts_by_industry' / naics_code[:2]
        ind_dir.mkdir(parents=True, exist_ok=True)

        with open(ind_dir / f"{prompt['prompt_id']}.json", 'w') as f:
            json.dump(prompt, f, indent=2)

    def save_response_by_prompt(self, prompt_id: str, model: str, response: dict):
        """Save response organized by prompt."""
        if not self.current_run_dir:
            return

        prompt_dir = self.current_run_dir / 'responses' / 'by_prompt' / prompt_id
        prompt_dir.mkdir(parents=True, exist_ok=True)

        with open(prompt_dir / f"{model}.json", 'w') as f:
            json.dump(response, f, indent=2)

    def save_response_by_model(self, prompt_id: str, model: str, response: dict):
        """Save response organized by model."""
        if not self.current_run_dir:
            return

        model_dir = self.current_run_dir / 'responses' / 'by_model' / model
        model_dir.mkdir(parents=True, exist_ok=True)

        with open(model_dir / f"{prompt_id}.json", 'w') as f:
            json.dump(response, f, indent=2)

    def save_raw_judgment(self, judgment: dict):
        """Save raw judgment."""
        if not self.current_run_dir:
            return

        raw_dir = self.current_run_dir / 'judgments' / 'raw'
        filename = f"{judgment['prompt_id']}_{judgment['judge_model']}_{judgment.get('vote_idx', 0)}.json"

        with open(raw_dir / filename, 'w') as f:
            json.dump(judgment, f, indent=2)

    def save_aggregated_judgment(self, prompt_id: str, aggregated: dict):
        """Save aggregated judgment for a comparison."""
        if not self.current_run_dir:
            return

        agg_dir = self.current_run_dir / 'judgments' / 'aggregated'
        with open(agg_dir / f"{prompt_id}.json", 'w') as f:
            json.dump(aggregated, f, indent=2)

    def save_analysis(self, filename: str, data: dict):
        """Save analysis result."""
        if not self.current_run_dir:
            return

        with open(self.current_run_dir / 'analysis' / filename, 'w') as f:
            json.dump(data, f, indent=2)

    def generate_readme(self, config: dict, results_summary: dict):
        """Generate README.md for the run."""
        if not self.current_run_dir:
            return

        readme = f"""# Evaluation Run: {self.current_run_dir.name}

## Configuration
- Preset: {config.get('preset_name', 'Custom')}
- Prompts: {config.get('num_prompts', 'N/A')}
- Model pairs: {len(config.get('model_pairs', []))}
- Random seed: {config.get('random_seed', 'N/A')}

## Results Summary
- Total comparisons: {results_summary.get('total_comparisons', 0)}
- Overall Gemini win rate: {results_summary.get('overall_win_rate', 0.5)*100:.1f}%

## Directory Structure
- `prompts/` - All generated prompts
- `responses/` - Model responses organized by prompt and model
- `judgments/` - Raw and aggregated judge verdicts
- `analysis/` - Statistical analysis results
- `reports/` - Generated reports and charts
- `logs/` - Execution logs

## Files
- `config.json` - Full configuration
- `results.db` - SQLite database with all data
- `checkpoint.json` - Resume state

Generated: {datetime.now().isoformat()}
"""
        (self.current_run_dir / 'README.md').write_text(readme)

    def _generate_config_summary(self, config: dict) -> str:
        """Generate human-readable config summary."""
        lines = [
            "=" * 60,
            "EVALUATION CONFIGURATION SUMMARY",
            "=" * 60,
            "",
            f"Preset: {config.get('preset_name', 'Custom')}",
            f"Number of prompts: {config.get('num_prompts', 'N/A')}",
            f"Random seed: {config.get('random_seed', 'N/A')}",
            "",
            "Models to evaluate:",
        ]

        for pair in config.get('model_pairs', []):
            lines.append(f"  - {pair[0]} vs {pair[1]}")

        lines.extend([
            "",
            "Judge configuration:",
            f"  - Judge models: {', '.join(config.get('judge_models', []))}",
            f"  - Votes per judge: {config.get('votes_per_judge', 5)}",
            f"  - Judge personas: {', '.join(config.get('judge_personas', []))}",
            "",
            "=" * 60
        ])

        return "\n".join(lines)
```

---

## 9. Summary of Improvements

### Critical Fixes
1. **O*NET Reference Integration**: Now reads from ONET_WRITING_REFERENCE.md instead of hardcoding categories
2. **Phase 1 Implementation**: Full offline LLM generation for persona variations
3. **Phase 3 Implementation**: Full LLM enrichment with attachments, prior messages, competing objectives
4. **Response Analyzer**: Complete format/pattern detection with cliche and AI marker analysis
5. **Refusal Detector**: Full categorization of refusal types
6. **Weakness Finder**: Comprehensive weakness analysis across all dimensions
7. **Directory Manager**: Full directory structure as specified in PROMPT.md

### Bug Fixes
1. Fixed duplicate token values in database saves
2. Fixed incorrect cost splitting
3. Added proper async database operations with aiosqlite
4. Fixed non-portable hash for randomization
5. Added per-model rate limiting

### Design Improvements
1. External company database in JSON
2. Census-based name generation
3. Parallel API call batching
4. Circuit breaker pattern for API resilience
5. WeasyPrint for better PDF generation

### Additional Features
1. Cross-run comparison implementation
2. CSV/JSON export functionality
3. Full TUI interactive controls
4. Live cost tracking
5. Auto-generated README.md for each run

---

## 10. Implementation Priority

### Phase 1 (Week 1-2): Foundation + Critical Fixes
1. Set up project structure with all directories
2. Implement O*NET extractor using reference document
3. Build OpenRouter client with per-model rate limiting
4. Implement Phase 1 offline generation
5. Create basic prompt generator

### Phase 2 (Week 2-3): Core Evaluation
1. Implement Phase 3 LLM enrichment
2. Build evaluation engine with refusal detection
3. Implement response analyzer
4. Create judge manager with full context
5. Build vote aggregator

### Phase 3 (Week 3-4): Storage + Analysis
1. Implement full directory manager
2. Build async SQLite database layer
3. Create checkpoint/resume system
4. Implement weakness finder
5. Build bias detector with all types

### Phase 4 (Week 4-5): TUI + Reporting
1. Build progress dashboard TUI
2. Implement results viewer TUI
3. Create PDF report generator
4. Build chart generation
5. Implement CSV export

### Phase 5 (Week 5-6): Polish
1. Cross-run comparison
2. Full test coverage
3. Performance optimization
4. Documentation
5. Error handling refinement
