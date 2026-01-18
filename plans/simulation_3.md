# Simulation Report 3: Master Plan Implementation Dry Run

## Executive Summary

This document simulates implementing the master plan from `plans/master_plan_draft.md` for the Gemini Writing Evaluation Framework. I walked through each component as if building it, documenting what works well, what doesn't work or is unclear, identifying missing pieces, noting gotchas and edge cases, and flagging inconsistencies with PROMPT.md requirements.

**Overall Assessment**: The master plan is comprehensive and well-structured, but several critical gaps and implementation challenges need resolution before production use.

---

## 1. Phase 1 - Foundation Implementation Simulation

### 1.1 O*NET Extractor Simulation

**Walking through the implementation:**

When implementing `src/data/onet_extractor.py`, I would need to:

1. Connect to `db/onet.db` (SQLite database)
2. Read `db/ONET_WRITING_REFERENCE.md` for pre-processed writing tasks
3. Extract task statements with writing relevance

**What Works Well:**
- The plan correctly identifies using the pre-processed reference document rather than hardcoding categories
- SQLite approach is appropriate for the data size
- aiosqlite for async operations is a good choice

**Issues Identified:**

1. **CRITICAL: ONET_WRITING_REFERENCE.md Format Unknown**
   - The plan states "Use the pre-processed ONET_WRITING_REFERENCE.md file created by Opus" but doesn't define:
     - What fields/columns are in this reference?
     - Is it JSON, CSV, or markdown format?
     - What "writing relevance" criteria were used?
   - The code assumes it can map task_ids but the format is undefined

2. **Missing O*NET Schema Knowledge**
   - Plan references `task_statements` table but O*NET 30.1 has multiple tables:
     - `task_statements`
     - `task_ratings`
     - `occupation_data`
     - `job_zones`
   - Need JOIN logic to get occupation titles and job zones

3. **Gotcha: Task ID Format**
   - O*NET task IDs are NOT simple strings like "T1"
   - Real format is like "11-1011.00-T1" (occupation code + task number)
   - The test fixture uses wrong format

**Simulated Fix Required:**
```python
# Need to define ONET_WRITING_REFERENCE.md format explicitly
# Suggest JSON Lines format:
# {"task_id": "11-1011.00-T1", "onetsoc_code": "11-1011.00", "task": "...", "writing_relevance_score": 0.85}
```

### 1.2 WritingPrompt Schema Simulation

**What Works Well:**
- Comprehensive schema covering all PROMPT.md dimensions
- Uses pydantic for validation
- Includes all required metadata fields
- Correctly uses string for `communication_channel` instead of enum

**Issues Identified:**

1. **Missing Fields from PROMPT.md:**
   - `recipient_english_variant` on recipients list - only tracked at top level
   - `writer_english_variant` should be on WriterPersona (it's there but uses enum)
   - No `audience_size` tracking at the recipient level for CC scenarios

2. **Enum Constraints May Be Too Restrictive:**
   - `generation: Literal["gen_z", "millennial", "gen_x", "boomer"]` - what about "silent generation" or future categories?
   - `relationship: Literal[...]` - what about "external partner", "board member", "regulator"?

3. **Edge Case: Multiple Primary Recipients**
   - Schema has `is_primary: bool` but doesn't handle when you need to write to multiple people equally (team update)

4. **PROMPT.md Requirement Not Met:**
   - PROMPT.md: "Include realistic email addresses where appropriate (sarah.chen@acme.com)"
   - Schema has `email: Optional[str]` but no logic to generate domain-appropriate emails

### 1.3 Database Schema Simulation

**What Works Well:**
- Tables cover all core entities (prompts, responses, comparisons, votes)
- Proper foreign key relationships
- Indexes on key query columns
- compliance_checks table for instruction-following

**Issues Identified:**

1. **Missing Tables:**
   - No `models` table to track model metadata (pricing, rate limits)
   - No `failures` table - plan mentions `failures.log` but structured storage better
   - No `sensitive_topics` junction table (currently comma-separated string)
   - No `attachments` table (can't query by attachment type)

2. **Schema Normalization Issues:**
   - `sensitive_topics TEXT` as comma-separated violates 1NF
   - Company data duplicated in prompts table instead of normalized

3. **Missing Columns:**
   - `prompts.generated_by_model` - needed for bias analysis
   - `responses.retry_count` - needed for reliability analysis
   - `comparisons.gemini_was_position_a_count` - for position bias analysis

4. **Index Gaps:**
   - No index on `responses.prompt_id` - will slow joins
   - No index on `votes.comparison_id` - same issue
   - No composite index for `(gemini_model, competitor_model)` on comparisons

### 1.4 OpenRouter Client Simulation

**Walking through implementation:**

When implementing the API client, I would:
1. Create async HTTP client with httpx
2. Implement per-model rate limiting
3. Add circuit breaker pattern
4. Handle retries with exponential backoff

**What Works Well:**
- httpx choice is correct for async
- Per-model rate limiting is the right approach
- Circuit breaker pattern addresses API failure robustness

**Issues Identified:**

1. **CRITICAL: OpenRouter Model IDs Not Verified**
   - Plan uses model IDs like `google/gemini-3.0-pro-preview`, `openai/gpt-5.2-thinking-preview`
   - These are ASSUMED model IDs - need to verify against OpenRouter API
   - PROMPT.md says: "VERIFY URLS: discover and verify they exist using search and browse tools"
   - The plan does NOT verify these model IDs exist on OpenRouter

2. **Missing: Token Counting Implementation**
   - Plan mentions `token_counter.py` but no implementation details
   - Different models use different tokenizers (tiktoken for OpenAI, gemini tokenizer for Google)
   - Without accurate token counting, cost estimates will be wrong

3. **Rate Limit Configuration Unknown:**
   - Plan says "Use model-specific limits from OpenRouter documentation"
   - But doesn't provide actual values or show how to fetch them
   - OpenRouter rate limits vary by tier/plan

4. **Circuit Breaker State Serialization:**
   - Plan shows `circuit_breaker_states: Dict[str, Dict]` but doesn't define the Dict structure
   - What fields? `failure_count`, `last_failure_time`, `state` (open/closed/half-open)?

---

## 2. Phase 2 - Prompt Generation Pipeline Simulation

### 2.1 Phase 1 Offline Generator Simulation

**Walking through implementation:**

I would need to:
1. Connect to OpenRouter for each evaluated model
2. Generate 5 persona variations per task per model
3. Cache results to `data/offline_variations/`
4. Parse JSON responses from LLMs

**What Works Well:**
- Using all evaluated models for generation avoids single-model bias
- Caching prevents redundant API calls
- PersonaVariation dataclass captures needed fields

**Issues Identified:**

1. **CRITICAL: Cost of Phase 1 Generation Not Estimated**
   - If O*NET has ~20,000 writing tasks
   - 6 models * 5 variations * 20,000 tasks = 600,000 API calls JUST for Phase 1
   - At ~$0.01/call average = $6,000+ for Phase 1 alone
   - This is NOT included in the preset cost estimates!

2. **JSON Parsing Robustness:**
   - Code does `json.loads(content)` but LLMs often:
     - Add explanatory text before/after JSON
     - Use markdown code fences inconsistently
     - Return malformed JSON
   - Need more robust extraction with regex fallbacks

3. **Generation Model Rotation:**
   - Code generates from ALL models for EVERY task
   - Better approach: Round-robin assignment to distribute load
   - Current approach: 6x the API calls needed

4. **Missing: Deduplication**
   - Same persona might be generated by multiple models
   - No deduplication logic for similar variations
   - Could end up with "Sarah Chen, VP Marketing" from 3 different models

5. **Error Handling Gap:**
   - `except Exception as e: print(...)` swallows errors
   - If a model is down, we just skip without tracking
   - Need structured error logging

### 2.2 Phase 2 Algorithmic Combiner Simulation

**What Works Well:**
- Stratification by job zone and SOC group ensures diversity
- Deterministic RNG from seed enables reproducibility
- Fallback to algorithmic generation if no variations exist

**Issues Identified:**

1. **CRITICAL: Company Database Missing**
   - Plan references `CompanyDatabase` with 500+ companies
   - No implementation or data file provided
   - `company_database.py` just mentioned in project structure
   - Where does `data/companies.json` come from?

2. **NAICS Mapper Implementation Missing:**
   - `NAICSMapper` class referenced but not implemented
   - How does occupation code map to NAICS codes?
   - O*NET doesn't directly link to NAICS

3. **Name Generator Implementation Missing:**
   - References Census-based names at `data/names_census.json`
   - No implementation details
   - Census data needs preprocessing for demographic distribution

4. **Stratification Logic Bug:**
   - `_stratify_by_job_zone` returns `min(per_zone, len(zone_tasks))` per zone
   - If zone 5 has only 10 tasks but per_zone is 100, you get 10
   - Then `tasks[:num_prompts]` might cut off unevenly
   - Need to track actual counts returned

5. **Generation-to-Age Mapping:**
   - `_generation_to_age` helper referenced but not implemented
   - Gen Z: 18-28, Millennial: 29-44, Gen X: 45-60, Boomer: 61-78?
   - These ranges shift each year - need to calculate from birthyear ranges

### 2.3 Phase 3 Enrichment Simulation

**What Works Well:**
- Selective enrichment (30%) reduces API costs
- Multiple enrichment types aligned with PROMPT.md
- Temporal context uses correct date (Jan 6, 2026)

**Issues Identified:**

1. **Enrichment Ratio Conflicts:**
   - Config says `phase3_enrich_ratio: float = 0.3`
   - But individual enrichments have their own probabilities:
     - Tone matching: 15%
     - Temporal: 20%
   - These stack, so some prompts get multiple enrichments while 70% get none
   - Need clearer distribution strategy

2. **Async Iteration Bug:**
   - `indices_to_enrich = set(random.sample(...))` creates a set
   - `list(indices_to_enrich)[batch_start + j]` - set iteration order is NOT guaranteed
   - Will cause incorrect index mapping after batching

3. **Attachment Content Too Generic:**
   - Generated attachment summaries use placeholders like "[COMPANY]" and "[METRIC]"
   - These need to be filled in or the model responses will be confused
   - Need post-processing to fill placeholders

4. **Missing: Reply-To Context Distribution**
   - PROMPT.md lists specific reply scenarios:
     - "Angry customer email"
     - "Vague request from boss"
     - "Technical question from colleague"
     - "Rejection to negotiate"
   - Current implementation just generates generic "prior message"
   - Need scenario-specific generation prompts

5. **_build_prompt_text Missing Handling:**
   - Revision tasks need different prompt structure
   - Code builds standard prompt even for revision tasks
   - Need conditional structure for `is_revision_task`

---

## 3. Evaluation Engine Simulation

### 3.1 Response Generation Flow

**Walking through implementation:**

For each prompt + model pair:
1. Send prompt to model via OpenRouter
2. Track response metadata (tokens, latency, cost)
3. Detect format patterns (bullets, headers)
4. Classify any failures/refusals
5. Save to database and checkpoint

**Issues Identified:**

1. **Missing: Response Analyzer Implementation**
   - Plan mentions `response_analyzer.py` for format detection
   - No implementation provided
   - How to detect:
     - `has_bullets` - regex for `^[\-\*\•]`?
     - `has_headers` - regex for `^#{1,6}` or `^[A-Z][^.!?]*:$`?
     - `greeting_type` - classify "Hi", "Dear", "Hey", etc.?
     - `signoff_type` - classify "Best", "Thanks", "Cheers", etc.?

2. **Missing: Refusal Classifier Implementation**
   - PROMPT.md requires categorizing WHY models refuse:
     - Safety refusal
     - Capability limitation
     - Misunderstanding
     - Incomplete response
     - Off-topic
   - No classification logic provided
   - Need keyword matching or LLM-based classification

3. **Formality Detection Missing:**
   - Bias detection references `detected_formality` (1-5)
   - No implementation for detecting formality from response text
   - Need NLP analysis or heuristics

4. **Auto-Loss Logic Not Implemented:**
   - PROMPT.md: "If a model refuses to respond... it automatically loses"
   - No code showing how to detect refusal and mark as auto-loss
   - Need to integrate refusal detection with vote aggregation

### 3.2 Judge System Simulation

**What Works Well:**
- Full scenario context provided to judges
- Both personas (Expert + Recipient) implemented
- Position randomization with deterministic hash

**Issues Identified:**

1. **CRITICAL: Judge Response Parsing Fragile**
   - Expects EXACT format:
     ```
     WINNER: [A/B/TIE]
     CONFIDENCE: [1-5]
     ...
     ```
   - LLMs often:
     - Add preamble ("I've carefully evaluated...")
     - Use different formatting ("Winner: A" vs "WINNER: A")
     - Provide reasoning inline
   - Need robust regex parsing with fallbacks

2. **Judge Persona Context Incomplete:**
   - Recipient persona template uses `{recipient_name}` etc.
   - But doesn't include:
     - Recipient's technical level
     - Recipient's time constraints
     - Cultural context

3. **Missing: Judge Instruction Compliance Check**
   - PROMPT.md: "Include some prompts with explicit constraints"
   - Judges should specifically verify constraint compliance
   - Current judge prompt mentions it but doesn't emphasize

4. **Missing: Sensitive Topic Context for Judges**
   - If prompt is tagged with sensitive topics
   - Judges should know to evaluate appropriateness carefully
   - Current judge prompt doesn't receive `sensitive_topics` field

### 3.3 Vote Aggregation Simulation

**What Works Well:**
- Majority-of-majorities logic correctly implemented
- Winner normalized to "gemini"/"competitor"/"tie"
- Position tracking for bias analysis

**Issues Identified:**

1. **Edge Case: All Ties**
   - If all 5 votes from a judge are ties
   - `aggregate_for_judge` returns "tie"
   - But majority-of-majorities needs handling when judges split
   - If Judge1=tie, Judge2=gemini, Judge3=competitor -> what's the final?

2. **Handling Incomplete Votes:**
   - What if API fails during judging and only 3/5 votes collected?
   - Code doesn't handle partial judge data
   - Should use available votes or mark as incomplete?

3. **Missing: Confidence Weighting Option**
   - Votes have `confidence: int` (1-5)
   - Plan doesn't use this for aggregation
   - High-confidence votes might deserve more weight

4. **Judge Agreement Calculation:**
   - `agreement = max(gemini_judges, competitor_judges) / len(judge_majorities)`
   - This is NOT Cohen's Kappa
   - Plan mentions Kappa in statistics but uses simple agreement here
   - Inconsistent metrics

---

## 4. Checkpoint and Resume Simulation

### 4.1 Checkpoint State Management

**What Works Well:**
- Fine-grained checkpointing (per-vote)
- Atomic writes with temp file + rename
- Circuit breaker state persistence

**Issues Identified:**

1. **Race Condition Risk:**
   - `asyncio.Lock()` protects save
   - But `completed_votes.add(vote_id)` before `await self.save()`
   - If crash between add and save, state inconsistent
   - Need to save THEN add to in-memory set

2. **Checkpoint File Growth:**
   - All completed vote IDs stored as list
   - 10,000 prompts * 4 pairs * 3 judges * 2 personas * 5 votes = 1.2M vote IDs
   - checkpoint.json could grow to 50MB+
   - Consider using SQLite for checkpoint state too

3. **Resume Logic Gap:**
   - `get_partial_comparison` returns data but
   - No code shows how to USE partial data to resume mid-comparison
   - Need to restore generated responses, skip completed votes

4. **Missing: Checkpoint Versioning**
   - What if checkpoint schema changes between versions?
   - No version field in checkpoint.json
   - Old checkpoints might fail to load

### 4.2 Run Directory Structure

**What Works Well:**
- Complete directory structure per PROMPT.md spec
- Atomic writes for all file operations
- Symlink to latest run

**Issues Identified:**

1. **symlink_to Uses Relative Path:**
   - `latest_link.symlink_to(self.run_dir.name)` creates relative symlink
   - Works if you're in `results/` but breaks if accessed from elsewhere
   - Should use absolute path

2. **Missing: Directory Locking**
   - What if two processes try to write to same run directory?
   - No file locking mechanism
   - Could corrupt results

3. **organize_prompts_by_* Memory Issue:**
   - Loads all prompts into memory to group
   - For 10,000+ prompts, this is fine
   - But unnecessary memory allocation

---

## 5. Analysis and Statistics Simulation

### 5.1 Statistical Analysis

**What Works Well:**
- Correctly uses `scipy.stats.binomtest` (not deprecated `binom_test`)
- Wilson score intervals for confidence intervals
- Cohen's Kappa implementation for inter-rater reliability

**Issues Identified:**

1. **Effect Size Interpretation Missing:**
   - Calculates Cohen's h but doesn't interpret it
   - Small: 0.2, Medium: 0.5, Large: 0.8
   - Should include in WinRateResult or analysis output

2. **Multiple Comparisons Problem:**
   - If testing 4 model pairs * 5 job zones * 10 industries
   - That's 200 hypothesis tests
   - Need Bonferroni correction or FDR control
   - Plan doesn't address this

3. **Sample Size for Significance:**
   - With 100 prompts, statistical power may be low
   - Need power analysis to determine minimum sample size
   - Preset 4 (100 prompts) may be too small for reliable conclusions

4. **Ties Excluded from Binomial Test:**
   - `decisive = wins + losses` excludes ties
   - But ties carry information - similar quality
   - Should consider different statistical approach

### 5.2 Bias Detection

**What Works Well:**
- Covers all bias types from PROMPT.md:
  - Position bias
  - Length bias
  - Model fingerprinting
  - Formality drift

**Issues Identified:**

1. **detect_length_bias Data Requirements:**
   - Expects `gemini_word_count` and `competitor_word_count` in comparisons
   - These fields not in database schema
   - Need JOIN with responses table or add to schema

2. **detect_formality_drift Data Requirements:**
   - Expects `prompt_formality` and `detected_formality` in responses
   - `detected_formality` not in response schema
   - Need response analyzer to compute this

3. **detect_model_fingerprinting Logic Issue:**
   - Compares Gemini win rate when in position A vs B
   - But this tests POSITION bias, not fingerprinting
   - True fingerprinting would be: Do judges favor responses with certain stylistic markers?
   - Need different analysis approach

4. **Missing Bias Types:**
   - **Format bias**: Do judges prefer bullet points?
   - **Length preference by judge**: Individual judge length preferences
   - **Self-preference**: Does Gemini judge favor Gemini responses?

### 5.3 Weakness Analysis

**Issues Identified:**

1. **weakness_finder.py Not Implemented:**
   - Plan mentions it in project structure
   - Section 13.2 mentions "Weakness Identification" as goal
   - No implementation provided
   - Need to define what constitutes a "weakness":
     - Win rate < 40% in a dimension?
     - Statistically significant underperformance?

2. **PROMPT.md Requirement:**
   - "Identifies specific areas of weakness in Gemini effective writing vs its peers"
   - Need dimension analysis across:
     - Task types (correspondence, reports, memos)
     - Formality levels
     - Emotional contexts
     - Industry sectors
     - Job zones

3. **Missing: Weakness Severity Classification:**
   - Not all weaknesses are equal
   - Need to weight by:
     - Frequency (how often does this task type appear?)
     - Magnitude (how big is the win rate difference?)
     - Confidence (statistical significance)

---

## 6. TUI Implementation Simulation

### 6.1 Progress Dashboard

**What Works Well:**
- Uses textual for TUI (modern, async-friendly)
- Includes all required PROMPT.md elements:
  - Overall progress
  - Per-model-pair progress
  - Cost tracking
  - Activity log
- Interactive controls for pause/quit

**Issues Identified:**

1. **Dashboard-Engine Integration Missing:**
   - `ProgressDashboard` class defined
   - `EvaluationEngine` mentioned but not implemented
   - No code showing how engine sends updates to dashboard
   - Need message passing or shared state

2. **Reactive State Updates:**
   - Uses textual's `reactive` for state
   - But `update_progress` directly updates UI
   - Reactivity not being used correctly

3. **Model Stats Table Not Populated:**
   - `on_mount` creates columns but no row updates
   - Need `update_model_stats` method

4. **Missing: Error Panel Updates:**
   - Dashboard shows "Errors & Warnings" panel
   - But no code to update error counts
   - Need error tracking integration

5. **ETA Calculation Issue:**
   - Uses simple linear extrapolation
   - Doesn't account for:
     - Rate limit delays
     - Varying prompt complexity
     - Model response time differences

### 6.2 Results Viewer

**Issues Identified:**

1. **Stub Implementation:**
   - `_load_comparisons` and `_get_occupations` are stubs
   - No actual database loading code
   - Need full implementation

2. **Filter Integration Missing:**
   - Filter widgets defined but no `on_change` handlers
   - `current_filters` dict unused
   - Need filter->query->table update flow

3. **Detail View Implementation:**
   - `action_view_detail` gets row but doesn't load data
   - Need to query database for full comparison
   - Show both responses side-by-side

4. **Missing: Export from Viewer:**
   - `action_export` binding defined but no handler
   - Should export current filtered view

---

## 7. CLI Interface Simulation

**What Works Well:**
- Uses typer for CLI (modern, type-annotated)
- All required commands: run, view, compare, export
- Dry-run cost estimation

**Issues Identified:**

1. **CRITICAL: Preset Loading Bug:**
   - `config = PRESETS[preset]` - PRESETS is a dict
   - If preset is int 3, this fails (expects key)
   - Need `PRESETS[f"preset_{preset}"]` or list indexing

2. **Resume Logic Incomplete:**
   - `resume: Optional[Path]` passed to `EvaluationEngine`
   - But `EvaluationEngine` constructor not shown
   - Need to implement resume loading

3. **TUI vs No-TUI Integration:**
   - `no_tui` flag handled but
   - TUI case just creates dashboard without engine integration
   - Need proper async coordination

4. **Compare Command Type Hint:**
   - `run_dirs: list[Path]` - Python 3.9+ syntax
   - Plan says Python 3.11+ so OK
   - But `typer.Argument(...)` with list needs special handling

5. **Missing: Config Validation:**
   - Custom config could have invalid model IDs
   - No validation before starting expensive eval
   - Need `config.validate()` step

---

## 8. Configuration and Presets Simulation

### 8.1 Preset Configurations

**PROMPT.md Requirement (Table):**

| Level | Name | Prompts | Models | Judges | Est. Cost |
|-------|------|---------|--------|--------|-----------|
| 1 | Sanity Check | 5 | 1 pair | 1x1 vote | ~$1 |
| ... | ... | ... | ... | ... | ... |

**Issues Identified:**

1. **CRITICAL: Presets Not Implemented:**
   - `src/config/presets.py` mentioned in structure
   - No actual preset definitions provided
   - Need 10 preset configurations with correct parameters

2. **Cost Estimates Not Validated:**
   - Table shows ~$500 for Standard Eval (500 prompts)
   - But this excludes:
     - Phase 1 offline generation (one-time but huge)
     - Phase 3 enrichment API calls
     - Retries on failures
   - Real costs could be 2-3x higher

3. **Time Estimates Missing Basis:**
   - "~3 hrs" for Standard Eval
   - But depends on:
     - Rate limits (varies by OpenRouter tier)
     - Parallelization level
     - Model response times
   - Need parametric model for estimation

### 8.2 Model Configuration

**Issues Identified:**

1. **Model ID Verification Needed:**
   - Plan assumes these OpenRouter model IDs:
     ```
     google/gemini-3.0-pro-preview
     google/gemini-3.0-flash-preview
     openai/gpt-5.2-thinking-preview
     openai/gpt-4.1-preview
     anthropic/claude-opus-4.5-20251101
     anthropic/claude-sonnet-4-20250514
     ```
   - Date is Jan 6, 2026 - these are FUTURE model versions
   - Need to verify actual OpenRouter model IDs at runtime
   - Should have fallback/alias mechanism

2. **Flash-Tier Models Incomplete:**
   - PROMPT.md: "Other flash-tier models in class"
   - Only GPT-4.1 and Claude Sonnet included
   - Missing potential options:
     - Gemini Flash Thinking?
     - Llama-based flash models?
     - Other frontier flash models?

3. **Judge Model Constraints:**
   - Judges include Gemini 3 Pro
   - But Gemini is being EVALUATED
   - Potential conflict of interest?
   - PROMPT.md explicitly lists this, so intentional for robustness
   - But should track "self-judging" in bias analysis

---

## 9. Report Generation Simulation

### 9.1 PDF Report

**PROMPT.md Requirements:**
1. Comprehensive Dashboard
2. Deep Statistical Analysis
3. Executive Summary

**Issues Identified:**

1. **PDF Generator Not Implemented:**
   - `src/reports/pdf_generator.py` in structure
   - No implementation provided
   - Need to choose: reportlab vs weasyprint
   - weasyprint requires wkhtmltopdf system dependency

2. **Chart Generation Incomplete:**
   - `charts.py` and `heatmaps.py` mentioned
   - No implementation
   - Need:
     - Win rate bar charts by dimension
     - Heatmaps (occupation x formality)
     - Confidence interval plots
     - Time series of running win rate

3. **Executive Summary Content:**
   - What key metrics to highlight?
   - How to identify "top weaknesses"?
   - Actionable recommendations - who generates these?

4. **Missing: Auto-Generated README:**
   - `readme_generator.py` mentioned
   - No implementation
   - Should include:
     - Run configuration summary
     - How to resume if incomplete
     - How to regenerate report

---

## 10. Special Prompt Types Simulation

### 10.1 Constraint Generator

**What Works Well:**
- Good variety of constraint types
- Measurable constraints (word counts, bullet counts)
- Probability-based application

**Issues Identified:**

1. **Constraint Verification Not Automated:**
   - `ConstraintSpec.measurable = True` but
   - No code to actually measure compliance
   - Need `compliance_tracker.py` implementation
   - How to count words/bullets/sentences programmatically?

2. **Conflicting Constraints Possible:**
   - Could randomly select both:
     - "Keep this under 100 words"
     - "This should be comprehensive, at least 500 words"
   - Need mutual exclusion rules

3. **Tone Constraints Hard to Verify:**
   - "Be direct and avoid pleasantries"
   - How to automatically verify?
   - Need NLP or LLM-based verification

### 10.2 Revision Tasks

**Issues Identified:**

1. **"concise" Revision Type Incomplete:**
   - `templates = None` for this type
   - Comment says "Will use LLM to generate verbose version"
   - But no implementation of this LLM call
   - Need Phase 3 integration

2. **Draft Quality Inconsistent:**
   - CASUAL_DRAFTS use "lemme", "thx"
   - But same casual level regardless of formality setting
   - Need formality-matched drafts

3. **Revision Task Prompt Format:**
   - `_build_prompt_text` doesn't handle revision tasks specially
   - Need different prompt structure:
     ```
     Original message:
     [draft]

     Please revise this to: [instruction]
     ```

### 10.3 CC/Multiple Recipients

**Issues Identified:**

1. **CC Scenario Selection Random:**
   - `self.rng.choice(self.CC_SCENARIOS)`
   - But scenarios should match prompt context
   - "vendor_cc_legal" doesn't make sense for all occupations

2. **Mixed Audience Handling:**
   - `mixed_audience_note` tells model about audience mix
   - But doesn't affect judge evaluation criteria
   - Judges should know to evaluate for mixed audience

---

## 11. PROMPT.md Compliance Check

### Requirements Verified as Covered:
- [x] O*NET task-level granularity
- [x] NAICS-based industry sampling
- [x] Real company names (mentioned, not implemented)
- [x] Realistic names for people
- [x] Temporal context
- [x] Attachment handling
- [x] Competing objectives
- [x] Regional English variants (field exists)
- [x] Reply-to context
- [x] Multiple recipients/CC
- [x] Tone matching
- [x] Revision tasks
- [x] Ambiguity handling
- [x] Instruction-following tests
- [x] Dual judge personas
- [x] Multiple judge models
- [x] Majority-of-majorities voting
- [x] Position bias mitigation
- [x] Checkpoint/resume
- [x] Live progress TUI
- [x] Results viewer TUI
- [x] PDF report

### Requirements NOT Fully Addressed:

1. **"Let O*NET data drive diversity programmatically"**
   - Plan uses ONET_WRITING_REFERENCE.md but format undefined
   - Still some hardcoded categories in code examples

2. **"Store company metadata: size, age, public/private, HQ location"**
   - CompanyContext has size, is_public
   - Missing: age (founding year), HQ location

3. **"Model Tiers: Flash vs Flash-tier"**
   - Flash-tier comparison incomplete
   - Only 2 flash-tier models listed

4. **"10 preset configurations"**
   - Mentioned in table but not implemented

5. **"Cross-Run Comparison"**
   - `cross_run_compare.py` mentioned
   - No implementation provided

6. **"Include temporal grounding where relevant... Do NOT include temporal context for tasks where it's irrelevant"**
   - Current implementation adds temporal randomly (20%)
   - Should be task-relevance-based

---

## 12. Summary of Critical Issues

### Must Fix Before Implementation:

1. **ONET_WRITING_REFERENCE.md format undefined** - Cannot implement O*NET extractor
2. **OpenRouter model IDs unverified** - Evaluation may fail at runtime
3. **Phase 1 generation cost not estimated** - Budget could be 2-3x higher
4. **Company and name databases missing** - Cannot generate realistic prompts
5. **Presets not implemented** - CLI will crash
6. **Dashboard-engine integration missing** - TUI won't update
7. **Response analyzer not implemented** - Cannot detect patterns/refusals
8. **Compliance verification not implemented** - Cannot track instruction-following

### Should Fix for Robustness:

1. **JSON parsing fragility** - LLM responses vary in format
2. **Judge response parsing fragility** - Same issue
3. **Checkpoint file growth** - May hit filesystem limits
4. **Multiple comparisons problem** - Statistical validity at risk
5. **Bias detection data requirements** - Missing fields in schema
6. **Weakness analysis undefined** - Core goal not implemented

### Nice to Have:

1. **Confidence weighting in vote aggregation**
2. **Power analysis for sample size**
3. **More comprehensive bias detection**
4. **Constraint conflict prevention**
5. **Context-appropriate CC scenarios**

---

## 13. Recommendations for Master Plan Improvement

1. **Define ONET_WRITING_REFERENCE.md Format**
   - Add schema definition
   - Show example entries
   - Explain how it was generated

2. **Verify OpenRouter Model IDs**
   - Add verification step in implementation
   - Include fallback model IDs
   - Document how to update for new models

3. **Implement All Missing Components**
   - Company database with real data
   - Name generator with Census data
   - All 10 presets
   - Weakness finder
   - Compliance tracker
   - Response analyzer

4. **Add Cost Model for Phase 1**
   - Document one-time offline generation cost
   - Option to skip if offline_variations exists
   - Incremental generation for new tasks only

5. **Fix Data Dependencies**
   - Add missing fields to database schema
   - Ensure all analysis components have required data

6. **Add Integration Documentation**
   - How engine connects to TUI
   - How phases coordinate
   - How resume actually works

7. **Address Statistical Issues**
   - Add power analysis
   - Implement FDR correction
   - Define "weakness" criteria mathematically

