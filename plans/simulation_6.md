# Implementation Simulation Report 6: Comprehensive Dry Run

## Executive Summary

This document simulates implementing the entire master plan from start to finish, documenting every issue, blocker, missing piece, and potential gotcha encountered during the dry run. The simulation identifies **47 distinct issues** across 12 categories, ranging from critical blockers to minor improvements.

---

## Part 1: Project Setup and Dependencies Simulation

### 1.1 pyproject.toml Setup

**Simulating**: Creating the project structure and installing dependencies.

**Issue #1 - weasyprint System Dependencies (BLOCKER)**
- weasyprint requires system-level libraries (cairo, pango, gdk-pixbuf)
- On macOS: `brew install cairo pango gdk-pixbuf libffi`
- On Linux: `apt-get install libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0`
- The plan does NOT mention these system dependencies
- **Mitigation**: Add installation instructions or consider reportlab as fallback

**Issue #2 - kaleido Version Compatibility**
- kaleido 0.2 has known issues on Apple Silicon
- May need `kaleido==0.1.0.post1` or arm64-specific handling
- **Mitigation**: Document platform-specific requirements

**Issue #3 - Python 3.11+ Requirement**
- Some users may be on 3.10; should document rationale
- asyncio improvements in 3.11 justify requirement
- **Mitigation**: Acceptable, just document clearly

### 1.2 Directory Structure Creation

**Simulating**: Creating all directories as specified.

**What Works Well**:
- Clean separation of concerns
- Logical module organization
- Clear data flow from src/ to results/

**Issue #4 - Missing directories in plan**
- No `migrations/` directory for schema evolution
- No `fixtures/` for test data
- No `.github/` for CI workflows
- **Mitigation**: Add these to structure

---

## Part 2: O*NET Database Validation Simulation

### 2.1 Schema Validation

**Simulating**: Connecting to db/onet.db and validating schema.

**What Works Well**:
- ONET_WRITING_REFERENCE.md provides excellent schema documentation
- SQL queries are verified against actual O*NET structure
- Job zones, task statements, occupation_data tables confirmed

**Issue #5 - Table Name Discrepancy**
- Plan assumes `task_statements` table
- ONET_WRITING_REFERENCE.md confirms this exists
- However, actual O*NET column names may use different casing
- `task_id` vs `Task_ID` - need case-insensitive matching
- **Mitigation**: Use `PRAGMA table_info()` for exact column names

**Issue #6 - Missing Scale Reference Table**
- The plan references scale_id values 'IM', 'CX', 'LV'
- Need to verify `scales_reference` table exists
- Scale interpretations (1-5 vs 0-7) need documentation
- **Mitigation**: Add scale lookup table validation

**Issue #7 - Element ID Verification**
- Element IDs like '2.A.1.c' for Writing Skill need verification
- ONET_WRITING_REFERENCE.md confirms these exist
- But content_model_reference table structure needs validation
- **Mitigation**: Add comprehensive element ID checks during warmup

### 2.2 Writing Task Extraction

**Simulating**: Running the extraction query from ONetExtractor.

```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%write%' OR t.task LIKE '%draft%'...
```

**What Works Well**:
- Query structure is sound
- Regex patterns for writing relevance are comprehensive
- Combining keyword matching with O*NET skill scores is robust

**Issue #8 - NULL Handling in JOINs**
- LEFT JOINs with job_zones, skills, work_context may return NULLs
- Plan uses COALESCE but doesn't handle missing occupations
- Some occupations may lack job_zone data
- **Mitigation**: Add explicit NULL filtering or default value strategy

**Issue #9 - Writing Relevance Threshold**
- min_relevance=0.5 is arbitrary
- Need calibration run to determine optimal threshold
- Could miss relevant tasks or include too many irrelevant ones
- **Mitigation**: Add threshold tuning as configuration option

**Issue #10 - Inferred Category Overlap**
- `_infer_category()` has overlapping patterns
- A task with "correspond with customer" matches both 'correspondence' AND 'customer_communication'
- Priority ordering helps but may misclassify
- **Mitigation**: Use multi-label classification instead of single category

---

## Part 3: OpenRouter API Integration Simulation

### 3.1 Model ID Verification

**Simulating**: Calling OpenRouter /api/v1/models endpoint.

**Issue #11 - Speculative Model IDs (CRITICAL)**
- Model IDs like "google/gemini-3.0-pro" are speculative
- These models may not exist yet (Jan 2026 timeframe)
- OpenRouter model ID format varies by provider
- **Mitigation**: Plan correctly identifies this as needing runtime verification

**Issue #12 - Model Fallback Logic**
- `_find_similar()` method is too simplistic
- Matching "gemini" and "3" could return wrong model generation
- May match "gemini-2.0" instead of waiting for "3.0"
- **Mitigation**: Use explicit version comparison, not substring matching

**Issue #13 - API Version Changes**
- OpenRouter API may change response format
- Need versioned API calls or graceful degradation
- **Mitigation**: Add API version checking in warmup

### 3.2 Rate Limiting Implementation

**Simulating**: Token bucket rate limiter for OpenRouter.

**What Works Well**:
- Token bucket is appropriate algorithm
- Per-model rate limits allow fine-grained control

**Issue #14 - Unknown Rate Limits**
- OpenRouter rate limits not documented in plan
- Different models have different limits
- Need to discover limits dynamically or hardcode conservatively
- **Mitigation**: Start conservative (10 req/min), increase based on 429 responses

**Issue #15 - Concurrent Request Handling**
- asyncio.Semaphore limits concurrency
- But doesn't handle burst patterns
- OpenRouter may rate limit bursts even under average rate
- **Mitigation**: Add request spacing (minimum delay between requests)

### 3.3 Circuit Breaker Testing

**Simulating**: Testing circuit breaker state transitions.

**What Works Well**:
- Three-state model (CLOSED, OPEN, HALF_OPEN) is standard
- Recovery timeout prevents thundering herd
- Half-open probe requests allow gradual recovery

**Issue #16 - Service ID Granularity**
- Circuit breaker uses service_id (model name)
- But failures may be OpenRouter-wide, not model-specific
- A global circuit breaker may be needed in addition
- **Mitigation**: Add hierarchical circuit breakers (global + per-model)

---

## Part 4: Prompt Generation Pipeline Simulation

### 4.1 Phase 1: Persona Generation

**Simulating**: LLM-based persona generation with caching.

**What Works Well**:
- Caching prevents repeated LLM calls
- JSON-based storage is portable
- Diversity requirements are explicit in prompt

**Issue #17 - LLM Output Parsing**
- Persona generation expects JSON array response
- LLMs may return markdown-wrapped JSON
- Or return incomplete JSON if output truncates
- **Mitigation**: Use same robust JSON parsing as judge output

**Issue #18 - Persona Diversity Verification**
- No automated check that generated personas meet diversity requirements
- Could end up with homogeneous persona set
- **Mitigation**: Add diversity validation after generation

**Issue #19 - Offline Generation Cost**
- "Use same models being evaluated" for persona generation
- This could be expensive if generating 1000+ personas
- No cost estimate for offline phase
- **Mitigation**: Add Phase 1 cost to budget calculations

### 4.2 Phase 2: Algorithmic Combination

**Simulating**: Stratified sampling across 8 dimensions.

**What Works Well**:
- Multi-dimensional stratification ensures diversity
- Deterministic seeding enables reproduction
- Two-pass sampling fills remaining quota

**Issue #20 - Combinatorial Explosion**
- 8 stratification dimensions with multiple values each
- If each has 5 values: 5^8 = 390,625 strata
- Many strata will have zero examples
- **Mitigation**: Use partial stratification or hierarchical sampling

**Issue #21 - Stratum Key Collision**
- `tuple(combo.get(d, "unknown") for d in dimensions)` creates strata keys
- "unknown" value creates catch-all stratum that may be overweighted
- Multiple dimensions with missing data cluster together
- **Mitigation**: Track and report "unknown" dimension rates

**Issue #22 - Company Size Inference**
- `_infer_company_size(combo['persona'])` not implemented
- Need logic to match persona seniority to company size
- Executive at startup vs junior at Fortune 500 needs different handling
- **Mitigation**: Add explicit company size inference rules

### 4.3 Phase 3: LLM Enrichment

**Simulating**: Context enrichment via LLM calls.

**What Works Well**:
- Prompt template is comprehensive
- Explicit "no placeholders" instruction
- Temperature 0.7 balances creativity and consistency

**Issue #23 - Enrichment Bottleneck**
- Each prompt requires LLM enrichment call
- 1000 prompts = 1000 API calls just for enrichment
- At 2 seconds per call = 33+ minutes just for enrichment
- **Mitigation**: Batch enrichment (multiple prompts per LLM call)

**Issue #24 - Enrichment Quality Variance**
- LLM-generated context quality varies
- Some prompts may have unrealistic details
- No validation of enriched content quality
- **Mitigation**: Add post-enrichment validation rules

**Issue #25 - Context Leakage Risk**
- Enrichment uses same models being evaluated
- Model A's enriched prompts may favor Model A
- This is acknowledged in PROMPT.md but mitigation unclear
- **Mitigation**: Use mix of models for enrichment, track by model

### 4.4 Special Prompt Types

**Simulating**: Constraint, revision, and ambiguous prompt generation.

**Issue #26 - Constraint Verification Logic**
- `ConstraintGenerator` creates verifiable constraints
- But `ConstraintChecker` implementation not shown
- Word counting, bullet point counting need implementation
- **Mitigation**: Add constraint checker implementation

**Issue #27 - Revision Task Dependency**
- Revision prompts require prior responses
- Creates sequential dependency in otherwise parallel flow
- Need to decide: pre-generate revision prompts or generate mid-eval?
- **Mitigation**: Separate revision evaluation as post-processing phase

---

## Part 5: Evaluation Engine Simulation

### 5.1 Response Collection

**Simulating**: Parallel response collection from all models.

**What Works Well**:
- asyncio.gather for parallel execution
- Per-model error handling prevents cascade failures
- Latency and token tracking for analysis

**Issue #28 - Token Limit Estimation**
- `_estimate_max_tokens(prompt)` not implemented
- Writing responses can vary from 50 to 2000+ tokens
- Setting too low truncates, too high wastes budget
- **Mitigation**: Use adaptive max_tokens based on task type

**Issue #29 - Response Timeout Handling**
- No timeout specified in response collection
- Long-thinking models could block indefinitely
- Need per-model timeout configuration
- **Mitigation**: Add configurable timeout (60-180 seconds typical)

**Issue #30 - Empty Response Detection**
- Some models return empty or near-empty responses
- Need to distinguish: empty, refusal, error, timeout
- Auto-loss criteria need clear definition
- **Mitigation**: Add response classification before judging

### 5.2 Dual-Persona Judging

**Simulating**: Running both writing expert and recipient persona judgments.

**What Works Well**:
- Two complementary perspectives
- System prompts are well-crafted
- JSON output format enables structured analysis

**Issue #31 - Context Window Limits**
- Judge prompt includes: system prompt + task prompt + response A + response B
- Long writing responses could exceed context limits
- Gemini 3.0 Pro may have different limits than GPT-5.2
- **Mitigation**: Add response truncation with notification

**Issue #32 - Recipient Role Inference**
- `_infer_recipient_role(prompt)` not implemented
- Need to extract recipient role from enriched prompt
- May not always be explicit in prompt text
- **Mitigation**: Store recipient role in prompt metadata

**Issue #33 - Judge Prompt Inconsistency Risk**
- Small wording differences in judge prompts affect results
- Version controlling judge prompts critical
- **Mitigation**: Hash judge prompts and log with results

### 5.3 Position Bias Handling

**Simulating**: Running comparisons with shuffled positions.

**What Works Well**:
- Both orderings tested per judge-persona combination
- Position mapping logic is correct
- Consistency checking across positions

**Issue #34 - Doubling API Costs**
- Each comparison requires 2 judgments (AB and BA orderings)
- With 3 judges x 2 personas x 2 orderings = 12 judge calls per prompt pair
- Cost estimation may undercount by 2x
- **Mitigation**: Review cost calculations for position shuffling

**Issue #35 - Inconsistent Position Handling**
- If judge gives A in AB order and A in BA order (different winners)
- Current logic flags inconsistency but still aggregates
- Should inconsistent judgments be weighted differently?
- **Mitigation**: Add configurable handling for position-inconsistent judges

### 5.4 Vote Aggregation

**Simulating**: Majority-of-majorities computation.

**What Works Well**:
- Two-level aggregation (position, then judge-persona)
- Tie handling is explicit
- Agreement metrics calculated inline

**Issue #36 - Tie Breaking**
- Plan shows `_simple_majority()` returning "TIE" on exact split
- With even number of judge-persona combinations, ties are common
- Need clearer tie-breaking strategy or explicit tie reporting
- **Mitigation**: Consider odd number of judges or weighted tie-breaking

**Issue #37 - Agreement Metric Edge Cases**
- Fleiss' Kappa with 3 categories and unbalanced data
- May produce misleading values with low sample sizes
- Cohen's Kappa for 2 raters needs matched pair handling
- **Mitigation**: Add sample size thresholds for agreement reporting

---

## Part 6: Analysis and Reporting Simulation

### 6.1 Statistical Analysis

**Simulating**: Win rate calculation and confidence intervals.

**What Works Well**:
- Wilson score interval is correct choice for proportions
- scipy.stats integration for significance tests
- Head-to-head matrix structure is clear

**Issue #38 - Multiple Comparison Correction**
- Testing many hypotheses (by occupation, industry, etc.)
- p < 0.05 will produce false positives
- Need Bonferroni or FDR correction
- **Mitigation**: Add multiple comparison correction to significance tests

**Issue #39 - Small Sample Warning**
- Some dimension slices may have few samples
- Confidence intervals become meaningless with n < 30
- Need minimum sample size warnings
- **Mitigation**: Add sample size thresholds and warnings

### 6.2 Weakness Finding

**Simulating**: Identifying patterns in Gemini losses.

**What Works Well**:
- Multi-dimensional loss analysis
- Relative risk calculation
- Reasoning theme extraction from judge comments

**Issue #40 - Gemini Position Detection**
- `loss.gemini_position` attribute used but not set
- Need to track which position Gemini was in for each comparison
- **Mitigation**: Add gemini_position to AggregatedResult

**Issue #41 - Theme Extraction Quality**
- Themes extracted from judge weaknesses as raw strings
- Same weakness phrased differently won't cluster
- "Too verbose" vs "Response too long" vs "Overly wordy"
- **Mitigation**: Use embedding similarity or LLM-based theme clustering

### 6.3 PDF Report Generation

**Simulating**: Generating the final PDF report.

**Issue #42 - Template Not Provided**
- `{report_type}_report.html` template referenced but not defined
- Need Jinja2 templates for executive, comprehensive reports
- CSS styling for PDF not specified
- **Mitigation**: Create template files in src/reports/templates/

**Issue #43 - Chart Image Quality**
- Plotly to_image() at 800x400 may be low resolution for PDF
- kaleido rendering quality varies by platform
- **Mitigation**: Use higher resolution (1600x800) and scale down in PDF

---

## Part 7: TUI Implementation Simulation

### 7.1 Progress Dashboard

**Simulating**: Running the textual-based TUI during evaluation.

**What Works Well**:
- Reactive state updates
- Clear visual hierarchy
- Keyboard controls for interaction

**Issue #44 - State Synchronization**
- TUI polls eval_state every 1 second
- Eval state updates from async tasks
- Potential race conditions on state reads
- **Mitigation**: Use thread-safe state container or message passing

**Issue #45 - Terminal Size Handling**
- Complex dashboard layout may break on small terminals
- No minimum size checking
- **Mitigation**: Add responsive layout with graceful degradation

### 7.2 Results Browser

**Simulating**: Browsing and filtering results post-evaluation.

**Issue #46 - Large Dataset Performance**
- 10,000+ results in DataTable may be slow
- Full response text storage increases memory
- **Mitigation**: Add pagination and lazy loading

---

## Part 8: Checkpoint and Recovery Simulation

### 8.1 Checkpoint System

**Simulating**: Saving and loading checkpoint state.

**What Works Well**:
- Atomic write pattern (temp file + rename)
- Dual storage (file + SQLite) for redundancy
- Comprehensive state serialization

**Issue #47 - Checkpoint Size Growth**
- pending/completed lists grow with evaluation size
- 10,000 prompts = large checkpoint files
- JSON serialization may be slow
- **Mitigation**: Use incremental checkpointing or binary format

---

## Part 9: Missing Components Identified

### 9.1 Not Implemented or Underspecified

1. **`_estimate_max_tokens(prompt)`** - Response token estimation
2. **`_infer_company_size(persona)`** - Company size inference from persona
3. **`_infer_recipient_role(prompt)`** - Recipient role extraction
4. **`constraint_checker.py`** - Instruction compliance verification
5. **Report templates** - Jinja2 HTML templates for PDF generation
6. **NAICS-SOC crosswalk data** - External data file not provided
7. **Company database JSON** - data/companies.json not populated
8. **Name pools JSON** - data/names.json not populated
9. **BLS matrix loader** - External data integration

### 9.2 Missing Test Coverage

1. Position bias detection unit tests
2. Agreement metric edge case tests
3. Circuit breaker state transition tests
4. Checkpoint recovery integration tests
5. End-to-end smoke test suite

### 9.3 Missing Documentation

1. System dependency installation guide
2. OpenRouter account setup
3. Cost estimation methodology
4. Extending model support guide
5. Custom preset creation guide

---

## Part 10: Recommendations Summary

### Critical (Must Fix Before Implementation)

| ID | Issue | Recommendation |
|----|-------|----------------|
| 1 | weasyprint system deps | Document or switch to reportlab |
| 11 | Speculative model IDs | Runtime verification (already planned) |
| 20 | Combinatorial explosion | Hierarchical stratification |
| 23 | Enrichment bottleneck | Batch enrichment calls |
| 34 | Position shuffling costs | Update cost calculations |

### High Priority (Fix During Implementation)

| ID | Issue | Recommendation |
|----|-------|----------------|
| 5 | Table name casing | Add case-insensitive schema check |
| 12 | Model fallback logic | Use semantic version comparison |
| 28 | Token limit estimation | Add task-type-based estimation |
| 38 | Multiple comparison correction | Add Bonferroni/FDR correction |
| 42 | Missing templates | Create template files |

### Medium Priority (Nice to Have)

| ID | Issue | Recommendation |
|----|-------|----------------|
| 14 | Unknown rate limits | Add adaptive rate discovery |
| 18 | Persona diversity verification | Add automated diversity check |
| 41 | Theme extraction quality | Add embedding-based clustering |
| 44 | State synchronization | Use message passing |

---

## Part 11: Successful Patterns Worth Preserving

1. **Data-driven design** - Letting O*NET drive diversity rather than hardcoded categories
2. **Multi-layer validation** - Schema validation, model verification, warmup phase
3. **Dual-persona judging** - Expert + recipient perspectives
4. **Majority-of-majorities** - Robust vote aggregation
5. **Position bias mitigation** - Systematic shuffling with consistency tracking
6. **Atomic checkpointing** - Temp file + rename pattern
7. **Circuit breaker pattern** - Prevents cascade failures
8. **Ten preset configurations** - Easy onboarding with customization path

---

## Part 12: Simulation Conclusion

The master plan is **substantially sound** and demonstrates sophisticated design thinking. The three-phase prompt generation pipeline, dual-persona judging, and majority-of-majorities aggregation represent best practices for LLM evaluation.

**Primary risks** center on:
1. External dependencies (model IDs, O*NET schema, system libraries)
2. Cost estimation accuracy (position shuffling doubles judge costs)
3. Scalability (enrichment bottleneck, stratification combinatorics)

**Recommended approach**:
- Start with "smoke" preset to validate all integrations
- Progress through "dev" -> "quick" -> "standard" presets
- Address issues incrementally as they manifest
- Maintain comprehensive logging for debugging

The plan is ready for implementation with the mitigations identified above.
