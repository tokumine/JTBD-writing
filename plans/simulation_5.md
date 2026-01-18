# Simulation Report 5: Implementation Dry Run of Master Plan

## Executive Summary

This document simulates implementing the entire Gemini Writing Evaluation Framework master plan step-by-step, documenting what works well, what doesn't work, missing pieces, gotchas, edge cases, and inconsistencies with PROMPT.md requirements.

---

## Phase 1: Foundation Components

### 1.1 O*NET Extractor Implementation

**Simulating Implementation:**

The plan references `ONET_WRITING_REFERENCE.md` as a pre-processed file created by Opus, but provides no specification for its format.

**What Works Well:**
- The decision to use ONET_WRITING_REFERENCE.md instead of hardcoded categories aligns with PROMPT.md
- Using the reference document prevents pattern-matching false positives

**Issues Identified:**

1. **CRITICAL GAP: ONET_WRITING_REFERENCE.md Format Undefined**
   - The plan assumes this file exists but never specifies its schema
   - No sample structure provided
   - Implementation would stall without knowing: Is it JSON? YAML? Markdown with task IDs?
   - The `ONetExtractor` class has no implementation showing how to parse this file

2. **Missing: How to Connect Reference to onet.db**
   - The reference file presumably maps to task IDs in the SQLite database
   - No query logic shown for joining reference data with full task details
   - Question: Does the reference contain task IDs, O*NET-SOC codes, or task text?

3. **Edge Case: Tasks Not in Reference**
   - What happens if onet.db contains tasks not in the reference?
   - No fallback mechanism defined

**Suggested Fix:**
```python
# Need explicit schema definition
@dataclass
class ONetWritingReference:
    task_id: str
    onet_soc_code: str
    task_statement: str
    writing_relevance_score: float  # 0-1
    writing_category: Optional[str]  # Inferred, not hardcoded
    context_notes: Optional[str]
```

### 1.2 Database Schema (aiosqlite)

**Simulating Implementation:**

Walking through the schema creation and data flow.

**What Works Well:**
- Comprehensive schema covering prompts, responses, comparisons, votes, compliance checks
- Appropriate indices for common query patterns
- aiosqlite for true async support

**Issues Identified:**

1. **Missing: Connection Pool Management**
   - Single `_connection` member won't handle concurrent access well
   - Multiple coroutines writing simultaneously could cause issues
   - Need connection pooling or explicit locking

2. **Missing: Transaction Management**
   - `save_prompt` commits after each insert
   - For bulk operations (loading 1000 prompts), this is extremely slow
   - Need batch insert support with single transaction

3. **Missing: Migration Strategy**
   - No versioning for schema changes
   - If schema evolves mid-project, existing results become incompatible
   - Need schema version tracking

4. **Edge Case: Unicode in Task Statements**
   - O*NET tasks may contain special characters
   - No explicit encoding handling shown

5. **Inconsistency: compliance_checks Table**
   - Schema includes `compliance_checks` table
   - But the corresponding `ComplianceTracker` module referenced in architecture (Section 3.2) is not implemented in the plan
   - No code showing how compliance checks are actually performed

**Suggested Fix:**
```python
async def save_prompts_batch(self, prompts: List[WritingPrompt]) -> None:
    """Batch save with single transaction."""
    async with self._connection.execute("BEGIN"):
        for prompt in prompts:
            await self._save_prompt_no_commit(prompt)
    await self._connection.commit()
```

### 1.3 OpenRouter Client Implementation

**Simulating Implementation:**

The plan shows architecture diagrams but no actual OpenRouterClient implementation code.

**CRITICAL GAP: No OpenRouter Client Code**

The plan references:
- `openrouter_client.py` - Not implemented
- `rate_limiter.py` - Not implemented
- `circuit_breaker.py` - Not implemented
- `retry_handler.py` - Not implemented
- `token_counter.py` - Not implemented

Only high-level descriptions exist. This is a fundamental gap since all API interactions depend on this client.

**Issues That Would Arise:**

1. **OpenRouter API Specifics Missing:**
   - Base URL format
   - Authentication header format
   - Response schema parsing
   - Error response handling

2. **Rate Limit Detection:**
   - How to detect rate limit responses (HTTP 429?)
   - How to parse retry-after headers
   - Per-model vs global limits

3. **Model ID Verification:**
   - The plan uses model IDs like `google/gemini-3.0-pro-preview`
   - These need verification against actual OpenRouter model IDs
   - January 2026 model names may differ from assumptions

**Suggested Implementation Skeleton:**
```python
class OpenRouterClient:
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"}
        )
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    async def complete(
        self,
        model: str,
        messages: List[Dict],
        temperature: float = 0.7,
        **kwargs
    ) -> CompletionResponse:
        # Implementation needed
        pass
```

---

## Phase 2: Prompt Generation Pipeline

### 2.1 Phase 1 Offline Generator

**Simulating Implementation:**

The code for `Phase1OfflineGenerator` is relatively complete. Walking through execution:

**What Works Well:**
- Uses ALL evaluated models for generation (avoiding single-model bias)
- Caches results to disk for efficiency
- Tracks which model generated each variation
- High temperature (0.9) for diversity

**Issues Identified:**

1. **Missing: Error Recovery for Partial Generation**
   - If generation fails for one model mid-run, the task_variations list has incomplete data
   - Cache file still written with partial results
   - No retry mechanism for failed models

2. **JSON Parsing Fragility:**
   - `_parse_variations` assumes JSON array format
   - If model outputs markdown formatting differently, parsing fails
   - No schema validation after parsing

3. **Memory Concerns:**
   - `generate_all_variations` loads all tasks into memory
   - For 20,000+ O*NET tasks, this could be problematic
   - Should use async generators and streaming

4. **Rate Limit Coordination:**
   - No rate limiting visible in the generation loop
   - Calling 6 different models in sequence without coordination
   - Would hit rate limits immediately for large task sets

5. **CRITICAL: Cost Implications Not Addressed**
   - Phase 1 generates 5 variations per task per model
   - 6 models x 5 variations x 20,000 tasks = 600,000 API calls
   - This is extremely expensive and not mentioned in cost estimates
   - PROMPT.md presets don't account for Phase 1 costs

**Suggested Fix:**
```python
async def generate_all_variations(
    self,
    tasks: AsyncIterator[ONetTask]  # Stream instead of list
) -> AsyncIterator[Tuple[str, List[PersonaVariation]]]:
    semaphore = asyncio.Semaphore(10)  # Limit concurrency

    async def process_task(task):
        async with semaphore:
            # ... generation logic with rate limiting
            pass
```

### 2.2 Phase 2 Algorithmic Combiner

**Simulating Implementation:**

The `Phase2AlgorithmicCombiner` code is reasonably complete.

**What Works Well:**
- Deterministic random seed for reproducibility
- Stratification by job zone and SOC group
- Integration with company database and name generator

**Issues Identified:**

1. **Missing: CompanyDatabase Implementation**
   - `self.companies.get_by_name()` and `sample_for_occupation()` referenced but not implemented
   - No code for loading companies.json
   - No logic for mapping occupations to appropriate companies

2. **Missing: NAICSMapper Implementation**
   - `self.naics.get_for_occupation()` referenced but not implemented
   - How does occupation map to NAICS codes?
   - This mapping is non-trivial

3. **Bug: Stratification Order**
   - `_stratify_by_job_zone` called first, reduces list
   - Then `_stratify_by_soc_group` called on already-reduced list
   - Second stratification won't have full data to work with
   - Should stratify on full list with combined criteria

4. **Missing: NameGenerator Implementation**
   - Referenced in architecture but no code provided
   - Census-based name generation mentioned but not implemented
   - Demographic diversity logic missing

5. **Edge Case: Empty Variation List**
   - If `variations.get(task.task_id, [])` returns empty
   - Falls back to `_build_algorithmic` but this method is not implemented
   - Would crash at runtime

**Code Gap Example:**
```python
# Referenced but not implemented:
def _build_algorithmic(self, task: ONetTask, index: int) -> WritingPrompt:
    """Fallback: generate algorithmically."""
    # NO IMPLEMENTATION PROVIDED
    pass
```

### 2.3 Phase 3 LLM Enrichment

**Simulating Implementation:**

The `Phase3Enricher` is the most detailed generator code.

**What Works Well:**
- Selective enrichment (30% of prompts)
- Multiple enrichment types (prior messages, attachments, competing objectives, tone examples)
- Model rotation to avoid single-model bias
- Temporal context with realistic dates

**Issues Identified:**

1. **Bug: Index Tracking in Enrichment**
   ```python
   for j, result in enumerate(results):
       original_idx = list(indices_to_enrich)[batch_start + j]
   ```
   - This assumes indices_to_enrich maintains order
   - Python set doesn't guarantee order
   - Would assign enrichments to wrong prompts

2. **Missing: Error Handling in Enrichments**
   - `asyncio.gather(*enrichments, return_exceptions=True)` catches exceptions
   - But only checks `if isinstance(result, dict)`
   - Doesn't log which enrichments failed or why

3. **Temporal Context Hardcoded Date:**
   ```python
   base_date = datetime(2026, 1, 6)  # Per PROMPT.md
   ```
   - Should be configurable, not hardcoded
   - Makes the code not reusable for future runs

4. **Missing: Full Prompt Text Builder**
   - `_build_prompt_text` exists but is incomplete
   - Doesn't handle all schema fields (e.g., revision_task, ambiguity)
   - No handling for regional English variants

5. **Prompt Schema Mismatch:**
   - `prompt.message_position.value` assumes MessagePosition is always set
   - But in Phase 2, `_infer_message_position` is called but not implemented
   - Would throw AttributeError on None

---

## Phase 3: Evaluation Pipeline

### 3.1 Judge Prompt Builder

**Simulating Implementation:**

Walking through the `JudgePromptBuilder` class.

**What Works Well:**
- Dual persona system (Writing Expert + Recipient)
- Full scenario context provided to judges per PROMPT.md
- Structured output format for parsing
- Position bias warning in prompts

**Issues Identified:**

1. **CRITICAL: Recipient Persona Gaps**
   - `RECIPIENT_SYSTEM` references `{recipient_name}`, `{recipient_title}`, `{relationship}`
   - But also needs: generation, english_variant, technical level
   - Judge can't properly simulate recipient without full context

2. **Missing: Constraint Compliance Prompting**
   - Judge prompt includes constraints but doesn't explicitly ask:
     "Did the response comply with each constraint?"
   - PROMPT.md requires tracking instruction compliance separately

3. **Output Parsing Not Implemented:**
   - `JudgePromptBuilder` returns (system, user) tuple
   - No code showing how to parse judge responses
   - The `WINNER: [A/B/TIE]` format parsing is not implemented

4. **Edge Case: Long Responses**
   - If responses are very long (500+ words each)
   - Combined with full context, judge prompt could exceed model limits
   - No truncation strategy defined

5. **Missing: Refusal Detection Prompting**
   - PROMPT.md requires categorizing WHY models refuse
   - Judge prompt doesn't ask judges to identify refusals
   - No mechanism to detect "off-topic" or "incomplete" responses

**Suggested Addition:**
```python
EVALUATION_ADDITIONS = """
6. RESPONSE_A_REFUSAL: If Response A refused or failed, categorize:
   - "none" (valid response)
   - "safety_refusal"
   - "capability_limitation"
   - "misunderstanding"
   - "incomplete"
   - "off_topic"
7. RESPONSE_B_REFUSAL: Same categories for Response B
8. CONSTRAINT_COMPLIANCE_A: Did A follow all explicit constraints? YES/NO
9. CONSTRAINT_COMPLIANCE_B: Did B follow all explicit constraints? YES/NO
"""
```

### 3.2 Vote Aggregator

**Simulating Implementation:**

The `VoteAggregator` is one of the more complete implementations.

**What Works Well:**
- Deterministic position randomization using hash
- Winner normalization relative to Gemini (not position)
- Majority-of-majorities aggregation
- Judge agreement calculation

**Issues Identified:**

1. **Bug: Tie Handling in Majority**
   ```python
   if gemini_count >= 3:
       return "gemini"
   elif competitor_count >= 3:
       return "competitor"
   else:
       # If no clear majority, compare totals
   ```
   - With best-of-5, if votes are [gemini, tie, tie, tie, tie]
   - gemini_count=1, competitor_count=0, tie_count=4
   - No model reaches 3, falls through to comparison
   - Returns "gemini" but this is only 1 actual vote
   - Should probably return "tie" for low conviction

2. **Missing: Confidence Weighting**
   - JudgeVote includes `confidence: int`
   - But aggregation ignores confidence scores
   - High-confidence votes treated same as low-confidence

3. **Edge Case: Judge Subset**
   - If only 2 judges configured (not 3)
   - Majority-of-3 logic breaks
   - Code assumes 3 judges but config allows different numbers

4. **Missing: Raw Vote Storage**
   - Aggregation converts position-based winner to model-based
   - But raw position (A/B) vote should also be stored for bias analysis
   - The schema includes it but aggregation doesn't populate it

5. **Statistical Gap:**
   - `judge_agreement` is simple percentage
   - PROMPT.md specifies "Cohen's Kappa or similar"
   - Agreement metric in aggregator is not Cohen's Kappa

### 3.3 Response Metadata Tracking

**What PROMPT.md Requires:**
- Response length (characters, words, tokens)
- Response time (latency)
- Format detection (bullets, headers, paragraphs)
- Greeting/sign-off patterns

**What's Implemented:**
- Database schema has fields for these
- But no `ResponseAnalyzer` class code provided

**Missing Implementation:**
```python
# Referenced in architecture but not implemented:
# src/eval/response_analyzer.py

class ResponseAnalyzer:
    """Detect format patterns in responses."""

    def analyze(self, response_text: str) -> ResponseMetadata:
        # NO CODE PROVIDED
        pass
```

**Issues:**
- Format detection requires regex patterns for bullets, headers
- Greeting detection needs common phrase matching
- None of this is implemented

---

## Phase 4: Analysis Components

### 4.1 Statistical Analysis

**Simulating Implementation:**

The `StatisticalAnalyzer` class is well-implemented.

**What Works Well:**
- Uses `scipy.stats.binomtest` (not deprecated `binom_test`)
- Wilson score intervals properly implemented
- Cohen's Kappa for inter-rater reliability
- Cohen's h for effect size

**Issues Identified:**

1. **Bug: Tie Exclusion in Statistical Tests**
   ```python
   decisive = wins + losses  # Exclude ties for statistical tests
   # ...
   p_value = self.binomial_test(wins, decisive) if decisive > 0 else 1.0
   ```
   - This excludes ties from significance testing
   - But `win_rate = wins / total` includes ties
   - Inconsistent denominators could be confusing
   - Document this clearly in reports

2. **Missing: Multiple Comparison Correction**
   - Running tests for each dimension (job zone, NAICS, formality, etc.)
   - Creates multiple hypothesis testing problem
   - No Bonferroni or FDR correction implemented
   - Could report spurious "significant" results

3. **Cohen's Kappa Implementation Gap:**
   - `cohens_kappa` takes two lists of ratings
   - But evaluation has 3 judges x 2 personas = 6 raters
   - Need pairwise kappa calculations or Fleiss' kappa for multiple raters
   - Current implementation only handles 2 raters

4. **Missing: Bootstrap Confidence Intervals**
   - Wilson score intervals assume normal approximation
   - For small samples, bootstrap CIs would be more robust
   - Not implemented

5. **Missing: Power Analysis**
   - PROMPT.md mentions "statistical power" for sample sizes
   - No pre-hoc power analysis to determine needed N
   - Would help users choose appropriate preset levels

### 4.2 Bias Detection

**Simulating Implementation:**

The `BiasDetector` class covers most required bias types.

**What Works Well:**
- Position bias detection with binomial test
- Length bias detection
- Model fingerprinting analysis
- Formality drift detection

**Issues Identified:**

1. **Missing: Model Format Bias**
   - PROMPT.md: "Does Model X consistently over-write or under-write?"
   - This isn't captured in current bias detection
   - Need per-model length distribution analysis

2. **Data Requirements Not Met:**
   - `detect_formality_drift` expects `response["detected_formality"]`
   - But no formality detection is implemented
   - Would crash with KeyError

3. **Fingerprinting Detection Flaw:**
   - Current implementation checks if Gemini win rate differs by position
   - This conflates position bias with fingerprinting
   - True fingerprinting would be: judge consistently picks specific model regardless of position
   - Need separate analysis

4. **Missing: Per-Judge Bias Analysis**
   - Current analysis aggregates across judges
   - Should also report per-judge biases
   - One biased judge could skew results

5. **Statistical Test Selection:**
   - Chi-square test for fingerprinting assumes sufficient cell counts
   - Small samples might violate assumptions
   - Fisher's exact test would be more appropriate for small N

### 4.3 Weakness Finder

**CRITICAL GAP: Not Implemented**

The plan references `weakness_finder.py` in the architecture but provides no implementation.

PROMPT.md explicitly requires:
> "Identifies specific areas of weakness in Gemini effective writing vs its peers"

**What's Needed:**
```python
class WeaknessFinder:
    """Identify systematic Gemini weaknesses."""

    def find_weaknesses(
        self,
        comparisons: List[Comparison],
        prompts: List[WritingPrompt]
    ) -> List[Weakness]:
        # Group by dimension
        # Find dimensions where Gemini win rate < threshold
        # Analyze patterns in losses
        # Identify task types with consistent losses
        pass

    def analyze_loss_patterns(
        self,
        gemini_losses: List[Comparison]
    ) -> LossPatternAnalysis:
        # What characterizes prompts where Gemini loses?
        # Length? Formality? Task type? Emotional context?
        pass
```

**This is a core deliverable and must be implemented.**

---

## Phase 5: User Interface

### 5.1 Progress Dashboard TUI

**Simulating Implementation:**

The `ProgressDashboard` uses Textual framework.

**What Works Well:**
- Rich visual layout matching PROMPT.md specification
- Real-time reactive updates
- Keyboard bindings for interaction
- ETA calculation

**Issues Identified:**

1. **Missing: Integration with EvaluationEngine**
   - Dashboard has `update_progress(data: Dict)` method
   - But no code showing how engine sends updates
   - Need pub/sub or callback mechanism

2. **Missing: Current Batch Details**
   - PROMPT.md requires showing current prompt details
   - Progress dashboard has placeholder but no implementation

3. **Missing: Per-Model-Pair Progress Bars**
   - PROMPT.md shows individual progress per comparison pair
   - Only one main progress bar implemented
   - Need DataTable rows with per-pair progress

4. **Missing: Error Summary Panel**
   - PROMPT.md requires "Errors & Warnings" section
   - Only `errors_count` reactive tracked
   - No detailed error display

5. **Screen Switching Not Implemented:**
   - `action_detail` and `action_statistics` log messages but don't push screens
   - Need separate Screen classes for detail views

6. **Performance Concern:**
   - Updating TUI on every vote could be expensive
   - Should batch updates or use refresh intervals

### 5.2 Results Viewer TUI

**Simulating Implementation:**

The `ResultsViewerApp` is skeletal.

**What Works Well:**
- Filter bar with occupation, winner, job zone selectors
- Main data table layout
- Side-by-side response comparison concept

**Issues Identified:**

1. **CRITICAL: Mostly Stub Code**
   ```python
   async def _load_comparisons(self):
       """Load comparisons from database."""
       # Would load from results.db
       pass
   ```
   - Most methods are empty stubs
   - Not a working implementation

2. **Missing: Judgment Drill-Down**
   - PROMPT.md requires "Drill-down into individual judgments"
   - `action_view_judgments` is a stub
   - No JudgmentDetailScreen implemented

3. **Missing: Response Diff View**
   - For revision tasks, showing original vs revised would help
   - Not implemented

4. **Missing: Export from Viewer**
   - `action_export` not implemented
   - Should export filtered results

5. **Search Functionality:**
   - Search input present but no search logic
   - Need full-text search across prompts

### 5.3 CLI Interface

**Simulating Implementation:**

The CLI is reasonably complete.

**What Works Well:**
- Typer for modern CLI experience
- Preset system with overrides
- Cost estimation before running
- Resume support
- Multiple commands (run, view, compare, export)

**Issues Identified:**

1. **Missing: Dry-Run Mode**
   - PROMPT.md shows `--dry-run` flag
   - Not implemented in CLI code

2. **Missing: Filter Options**
   - PROMPT.md: `--occupations "11-*,13-*" --industries "54,62"`
   - These filters not implemented in run command

3. **Missing: Judge Configuration Options**
   - Can't override judge models or votes from CLI
   - Only preset and num_prompts overridable

4. **Error Handling:**
   - No try/except around `asyncio.run(run_eval())`
   - Unhandled exceptions would crash ungracefully

5. **API Key Handling:**
   - No mention of how API key is passed
   - Should support environment variable or flag

**Suggested Additions:**
```python
@app.command()
def run(
    # ... existing options ...
    occupations: Optional[str] = typer.Option(None, "--occupations", help="SOC codes to include"),
    industries: Optional[str] = typer.Option(None, "--industries", help="NAICS codes to include"),
    judges: Optional[str] = typer.Option(None, "--judges", help="Judge models"),
    votes: int = typer.Option(5, "--votes", help="Votes per judge"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate only"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="OPENROUTER_API_KEY"),
):
```

---

## Phase 6: Reporting

### 6.1 PDF Report Generator

**CRITICAL GAP: Not Implemented**

The plan references `pdf_generator.py` but provides no code.

PROMPT.md requires:
> "Generate a final lead evaluation analyst report as a PDF that digs into the data behind the aggregate win/loss rates and identifies specific areas of weakness in Gemini effective writing vs its peers."

Required sections:
1. Comprehensive Dashboard
2. Deep Statistical Analysis
3. Executive Summary

**What's Needed:**

```python
class PDFReportGenerator:
    """Generate comprehensive PDF report."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    def generate(self) -> Path:
        # Load all analysis results
        # Generate charts using plotly
        # Build PDF with reportlab/weasyprint
        # Include:
        #   - Executive summary
        #   - Win rates by dimension
        #   - Statistical tests results
        #   - Bias analysis
        #   - Weakness analysis
        #   - Heatmaps
        pass
```

This is a major deliverable with no implementation.

### 6.2 Charts and Visualizations

**Referenced but Not Implemented:**
- `charts.py` - Not provided
- `heatmaps.py` - Not provided

**What's Needed:**
- Win rate bar charts by model pair
- Heatmaps by occupation x formality
- Confidence interval plots
- Judge agreement visualizations

### 6.3 Auto-Generated README

**Referenced but Not Implemented:**
- `readme_generator.py` - Not provided

PROMPT.md requires each run directory to have:
> "README.md - Auto-generated run description"

---

## Checkpoint and Resumability

### 6.4 Checkpoint Manager Analysis

**Simulating Checkpoint/Resume Scenarios:**

**Scenario 1: Graceful Ctrl+C**
- Signal handler saves checkpoint
- But no signal handler code provided
- PROMPT.md requires this functionality

**Scenario 2: Crash Mid-Vote**
- CheckpointManager saves after each vote
- Resume should skip completed votes
- `is_vote_complete()` method exists
- But how is vote_id constructed? Not specified.

**Scenario 3: Resume with Config Changes**
- User resumes with different config (e.g., more prompts)
- No validation that resumed run matches original config
- Could lead to inconsistent results

**Issues Identified:**

1. **Missing: Signal Handlers**
   ```python
   # Not implemented
   import signal

   def handle_interrupt(signum, frame):
       # Save checkpoint
       # Graceful shutdown
       pass

   signal.signal(signal.SIGINT, handle_interrupt)
   ```

2. **Missing: Vote ID Generation**
   - `is_vote_complete(vote_id)` requires vote_id
   - How is vote_id constructed?
   - Should be: `{prompt_id}_{gemini_model}_{competitor_model}_{judge_model}_{persona}_{vote_index}`

3. **Checkpoint File Corruption:**
   - If crash during atomic write (after unlink, before move)
   - Could lose checkpoint entirely
   - Should keep backup of previous checkpoint

4. **Missing: Checkpoint Validation**
   - On resume, should validate checkpoint matches config
   - Prevent resuming wrong run

---

## Specific Prompt Feature Validation

### 7.1 PROMPT.md Feature Checklist

Walking through each PROMPT.md requirement to verify coverage:

| PROMPT.md Requirement | Implemented | Notes |
|----------------------|-------------|-------|
| O*NET task-level granularity | Partial | No extraction code |
| NAICS industry sampling | Partial | NAICSMapper referenced, not implemented |
| Real company names | Partial | CompanyDatabase referenced, not implemented |
| Realistic person names | Partial | NameGenerator referenced, not implemented |
| Age/generation diversity | Yes | In WriterPersona schema |
| Formality range (1-5) | Yes | In schema and generators |
| Urgency levels | Yes | In schema |
| Relationship context | Yes | In RecipientPersona |
| Audience size | Yes | In schema |
| Emotional context | Yes | Enum defined |
| Message position | Yes | Enum defined |
| Regional English variants | Yes | In schema, partial implementation |
| Temporal context | Yes | In Phase 3 enrichment |
| Attachments/references | Yes | Attachment schema, enrichment code |
| Competing objectives | Yes | In enrichment |
| Reply-to context | Yes | Prior message generation |
| Multiple recipients (CC) | Yes | CCContext schema, generator |
| Tone matching examples | Yes | ToneExample schema, generator |
| Revision tasks | Yes | RevisionTask schema, generator |
| Ambiguous prompts | Yes | AmbiguityGenerator |
| Instruction constraints | Yes | ConstraintSpec schema, generator |
| Communication channel | Yes | Dynamic string, not enum |
| Language field (future) | Yes | In schema |

### 7.2 Evaluation Methodology Checklist

| PROMPT.md Requirement | Implemented | Notes |
|----------------------|-------------|-------|
| Pairwise comparison | Yes | ModelPair structure |
| Best-of-5 votes | Yes | Configurable |
| 3 judge models | Yes | In config |
| Majority-of-majorities | Yes | VoteAggregator |
| Position randomization | Yes | Deterministic shuffle |
| Dual judge personas | Yes | Expert + Recipient |
| Writing Expert persona | Yes | Prompt defined |
| Recipient persona | Partial | Needs more context |
| Authenticity/human-like | Partial | In criteria, not scored |
| Cliche avoidance | Partial | In criteria, not scored |
| Length appropriateness | Partial | In criteria, not scored |
| Instruction compliance | No | No ComplianceTracker code |
| Sensitive topic handling | Partial | Schema supports, no tracking |
| Refusal categorization | No | Not implemented |
| Auto-loss for failures | Partial | Schema supports, no logic |
| Response metadata | Partial | Schema has fields, no analyzer |
| Position bias detection | Yes | In BiasDetector |
| Length bias detection | Yes | In BiasDetector |
| Judge agreement (Kappa) | Partial | 2-rater only |
| Confidence intervals | Yes | Wilson score |

### 7.3 Configuration Checklist

| PROMPT.md Requirement | Implemented | Notes |
|----------------------|-------------|-------|
| Model selection | Yes | In EvalConfig |
| Judge model selection | Partial | Hardcoded, not CLI configurable |
| Votes per judge | Yes | Configurable |
| Judge personas toggle | Yes | use_both_personas |
| Number of prompts | Yes | Configurable |
| Occupation filters | No | Not in CLI |
| Industry filters | No | Not in CLI |
| Job zone filters | No | Not in CLI |
| Formality range filter | No | Not in CLI |
| Random seed | Yes | Configurable |
| Stratification options | Yes | In config |
| 10 preset levels | Partial | Referenced, not defined |

### 7.4 Output Checklist

| PROMPT.md Requirement | Implemented | Notes |
|----------------------|-------------|-------|
| Timestamped run directories | Yes | RunDirectory class |
| config.json | Yes | Save method |
| config_summary.txt | Yes | Save method |
| checkpoint.json | Yes | CheckpointManager |
| prompts.json | Yes | Path property |
| prompts_by_occupation/ | Yes | Method defined |
| prompts_by_industry/ | Yes | Method defined |
| responses/ by_prompt | Yes | Directory structure |
| responses/ by_model | Yes | Directory structure |
| judgments/raw | Yes | Directory structure |
| judgments/aggregated | Yes | Directory structure |
| results.db | Yes | SQLite database |
| results_summary.csv | Yes | Path property |
| analysis/*.json | Partial | Paths defined, no generators |
| reports/report.pdf | No | Not implemented |
| reports/executive_summary.md | Yes | Path property |
| reports/charts/ | Yes | Directory structure |
| logs/run.log | Yes | Path property |
| logs/failures.log | Yes | Path property |
| logs/timing.log | Yes | Path property |
| README.md per run | No | Not implemented |
| latest symlink | Yes | In RunDirectory |

---

## Critical Gaps Summary

### Must-Fix Before Implementation

1. **ONET_WRITING_REFERENCE.md Schema**
   - No format defined
   - Cannot implement O*NET extractor without this

2. **OpenRouter Client**
   - Core API client not implemented
   - All evaluation depends on this

3. **Phase 1 Cost Not Accounted**
   - Pre-generation costs 600,000+ API calls
   - Not in cost estimates or presets

4. **WeaknessFinder Module**
   - Core deliverable per PROMPT.md
   - No implementation provided

5. **PDF Report Generator**
   - Major deliverable
   - No implementation provided

6. **Compliance Tracker**
   - PROMPT.md requires instruction compliance tracking
   - No implementation provided

7. **Refusal Classifier**
   - PROMPT.md requires categorizing refusals
   - No implementation provided

8. **Response Analyzer**
   - Metadata extraction not implemented
   - Bias detection depends on this

9. **10 Preset Configurations**
   - Referenced but not defined
   - Presets table in PROMPT.md not implemented

10. **Signal Handlers**
    - Graceful shutdown not implemented
    - Checkpointing on interrupt missing

### Should-Fix For Robustness

1. **Database Connection Pooling**
2. **Batch Operations for Bulk Inserts**
3. **Multiple Comparison Correction**
4. **Fleiss Kappa for Multiple Raters**
5. **Bootstrap Confidence Intervals**
6. **Per-Judge Bias Analysis**
7. **Filter Options in CLI**
8. **TUI-Engine Integration**
9. **Search in Results Viewer**
10. **Cross-Run Comparison Statistical Tests**

---

## Gotchas and Edge Cases

### 8.1 Data Edge Cases

1. **Empty O*NET Tasks**
   - Some occupations may have no writing-relevant tasks
   - Need graceful handling

2. **Company Name Collisions**
   - "Apple" could be tech or fruit company
   - Need industry context for disambiguation

3. **International Companies**
   - US-centric but some companies are global
   - Regional variants may conflict

4. **Very Long Task Statements**
   - Some O*NET tasks are multiple sentences
   - May exceed prompt length limits

### 8.2 API Edge Cases

1. **Model Deprecation**
   - Model IDs may change between plan and implementation
   - `gemini-3.0-pro-preview` may not be final name

2. **Rate Limit Variations**
   - OpenRouter rate limits may vary by account tier
   - Hardcoded limits may be wrong

3. **Response Truncation**
   - Long responses may hit output token limits
   - Need detection and handling

4. **Timeout Without Response**
   - API may timeout without error
   - Need to distinguish from actual failures

### 8.3 Evaluation Edge Cases

1. **All Ties**
   - If all comparisons are ties, no winner can be determined
   - Need clear reporting of this case

2. **Judge Refusals**
   - What if a judge model refuses to evaluate?
   - Should fall back to other judges

3. **Self-Evaluation Bias**
   - Gemini 3 Pro as judge evaluating Gemini 3 Pro
   - Need to flag or exclude

4. **Prompt Length Variation**
   - Some prompts much longer than others
   - May affect model performance differently

### 8.4 Statistical Edge Cases

1. **Small Sample Sizes**
   - Some dimensions may have few samples
   - CIs become unreliable

2. **Simpson's Paradox**
   - Aggregate win rate may mask dimension-level patterns
   - Need careful analysis

3. **Non-Independence**
   - Multiple comparisons per prompt
   - Violates independence assumptions

---

## Implementation Recommendations

### Priority 1: Critical Path

1. Define ONET_WRITING_REFERENCE.md schema
2. Implement OpenRouter client with rate limiting
3. Implement O*NET extractor
4. Implement Phase 2 combiner completely
5. Implement evaluation engine main loop

### Priority 2: Core Features

1. Complete judge prompt builder with all context
2. Implement response analyzer for metadata
3. Implement compliance tracker
4. Implement refusal classifier
5. Build working TUI with engine integration

### Priority 3: Analysis and Reporting

1. Implement weakness finder
2. Build PDF report generator
3. Create chart generation utilities
4. Build heatmap visualizations
5. Generate executive summary

### Priority 4: Polish

1. Add signal handlers for graceful shutdown
2. Implement CLI filter options
3. Build results viewer TUI completely
4. Add search functionality
5. Create cross-run comparison tools

---

## Conclusion

The master plan provides a comprehensive architectural vision that aligns well with PROMPT.md requirements at a high level. However, significant implementation gaps exist:

**Strengths:**
- Clear technology stack choices
- Well-designed schemas and data models
- Proper voting aggregation methodology
- Good bias detection framework foundation

**Critical Gaps:**
- Core API client not implemented
- Multiple essential modules are stubs or missing
- Cost estimation for Phase 1 not addressed
- Key deliverables (PDF report, weakness finder) not implemented

**Risk Assessment:**
- HIGH: Implementation would stall on undefined ONET_WRITING_REFERENCE.md format
- HIGH: Phase 1 costs could exceed budget significantly
- MEDIUM: TUI integration requires substantial additional work
- MEDIUM: Statistical analysis needs multiple comparison correction

**Recommendation:**
Before implementation, the plan needs:
1. ONET_WRITING_REFERENCE.md schema specification
2. Complete OpenRouter client implementation
3. Realistic Phase 1 cost modeling
4. WeaknessFinder and PDFReportGenerator implementations
5. All stub methods filled in with working code

The architectural decisions are sound, but the plan is approximately 40-50% complete in terms of implementation-ready specifications.
