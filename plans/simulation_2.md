# Simulation Report 2: Dry Run Implementation of Master Plan

## Executive Summary

This simulation report walks through implementing the entire master plan as if building it component by component, documenting what works well, what doesn't work or is unclear, identifying missing pieces and gaps, noting gotchas and edge cases, and flagging inconsistencies with PROMPT.md requirements.

---

## 1. Foundation Layer Simulation

### 1.1 O*NET Database Integration

**Simulating**: Reading from `db/onet.db` and using `ONET_WRITING_REFERENCE.md`

**What Works Well**:
- The plan correctly identifies using the pre-processed ONET_WRITING_REFERENCE.md instead of raw pattern matching
- SQLite with aiosqlite provides true async database access
- Task-level granularity (~20,000+ tasks) provides excellent coverage

**Issues Discovered**:

1. **Missing ONET_WRITING_REFERENCE.md Parser**: The master plan references this file but provides NO implementation for parsing it. The `ONetExtractor` class is mentioned but not defined. We need:
   - Parser for the reference document format
   - Mapping from reference to actual task_statements table
   - Validation that referenced task_ids exist in onet.db

2. **Unknown File Format**: PROMPT.md says "OPUS has pre-processed all the tasks" but doesn't specify the format. The plan assumes it contains task IDs and writing contexts but provides no validation.

3. **Missing Table Schema**: The plan shows `task_statements` table but O*NET 30.1 uses different table names. The actual tables are likely:
   - `task_statements` -> correct
   - `occupation_data` or `occupation` for occupation info
   - `job_zone_reference` for job zone data

**Gotcha**: If ONET_WRITING_REFERENCE.md uses a JSON format vs markdown format, the parser will be completely different.

### 1.2 Database Schema Implementation

**Simulating**: Creating results.db with the provided schema

**What Works Well**:
- Schema covers all required fields from PROMPT.md
- Proper foreign key relationships
- Good indexing strategy for common queries
- Tracks all metadata (greeting_type, signoff_type, has_bullets, etc.)

**Issues Discovered**:

1. **Missing Recipient Table**: The schema stores writer info but recipients are only referenced via `recipient_english_variant` in prompts table. Should have:
   ```sql
   CREATE TABLE recipients (
       recipient_id TEXT PRIMARY KEY,
       prompt_id TEXT NOT NULL,
       name TEXT NOT NULL,
       job_title TEXT NOT NULL,
       relationship TEXT NOT NULL,
       english_variant TEXT,
       is_primary INTEGER DEFAULT 1,
       FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
   );
   ```

2. **Missing Attachment Storage**: Schema has no table for attachments, yet prompts can have multiple attachments per PROMPT.md. Need:
   ```sql
   CREATE TABLE attachments (
       attachment_id TEXT PRIMARY KEY,
       prompt_id TEXT NOT NULL,
       type TEXT NOT NULL,
       description TEXT NOT NULL,
       content TEXT NOT NULL,
       FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
   );
   ```

3. **Missing Constraints Storage**: The `has_constraints` flag exists but constraint details aren't stored. Need:
   ```sql
   CREATE TABLE prompt_constraints (
       constraint_id TEXT PRIMARY KEY,
       prompt_id TEXT NOT NULL,
       constraint_type TEXT NOT NULL,
       description TEXT NOT NULL,
       specific_requirement TEXT NOT NULL,
       FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
   );
   ```

4. **Refusal Tracking Incomplete**: Schema tracks `failure_category` but doesn't distinguish between the 5 refusal types from PROMPT.md (safety, capability, misunderstanding, incomplete, off-topic).

### 1.3 OpenRouter API Client

**Simulating**: Building the async HTTP client with rate limiting

**What Works Well**:
- httpx for async HTTP is correct choice
- Circuit breaker pattern is appropriate
- Per-model rate limiting is essential

**Issues Discovered**:

1. **Missing Token Counter Implementation**: The plan mentions `token_counter.py` but provides no implementation. For cost estimation, we need:
   - Tokenizer selection per model (tiktoken for OpenAI, different for others)
   - Or use OpenRouter's returned token counts post-hoc
   - Pre-estimation for cost display requires tokenizer

2. **Rate Limit Values Unknown**: The plan says "Use model-specific limits from OpenRouter documentation" but doesn't provide actual values. OpenRouter rate limits are:
   - Often request-based, not token-based
   - Vary by tier (free vs paid)
   - May change without notice

3. **Circuit Breaker State Not Serializable**: The plan mentions persisting circuit breaker state but the implementation uses a simple Dict that may not capture:
   - Timestamp of last failure
   - Half-open state
   - Reset timeout

4. **Missing Retry Handler**: Referenced in project structure (`retry_handler.py`) but not implemented. Need exponential backoff with jitter:
   ```python
   delay = min(base_delay * (2 ** attempt) + jitter, max_delay)
   ```

---

## 2. Prompt Generation Pipeline Simulation

### 2.1 Phase 1: Offline LLM Generation

**Simulating**: Pre-generating persona variations

**What Works Well**:
- Using ALL evaluated models for generation avoids single-model bias
- Temperature 0.9 ensures diversity
- Caching per task_id is efficient
- Tracking `generated_by_model` enables bias analysis

**Issues Discovered**:

1. **JSON Parsing Fragility**: The `_parse_variations` method assumes LLM outputs clean JSON. In practice:
   - Models may include explanatory text before/after JSON
   - Models may use different quote styles
   - Models may escape characters differently
   - Need robust extraction with regex fallback

2. **Missing Variation Validation**: No validation that generated personas are:
   - Demographically diverse
   - Plausible for the occupation
   - Not duplicate/similar to each other

3. **Cost of Phase 1**: Generating 5 variations per task per model:
   - 20,000 tasks * 6 models * ~$0.01 per call = ~$1,200 just for Phase 1
   - This should be a one-time preprocessing cost, but plan doesn't clarify this

4. **Missing Progress Tracking for Phase 1**: No TUI or progress display for offline generation, which could take hours.

5. **Variation ID Collision Risk**: Using MD5 hash of `task_id_model_i` is fine but should use full hash or UUID to avoid collisions.

### 2.2 Phase 2: Algorithmic Combination

**Simulating**: Combining O*NET tasks with pre-generated variations

**What Works Well**:
- Deterministic sampling with seeded RNG
- Stratification by job zone and SOC group ensures diversity
- Company database lookup with fallback

**Issues Discovered**:

1. **Missing Company Database Implementation**: Referenced but not provided. Need:
   - `data/companies.json` with 500+ companies
   - Mapping from NAICS to companies
   - Company size distribution data

2. **NAICS Mapper Not Implemented**: `naics_mapper.py` referenced but not coded. Need:
   - O*NET occupation to NAICS mapping (crosswalk file)
   - NAICS code to description lookup
   - Sector derivation logic

3. **Name Generator Missing**: `name_generator.py` referenced but not implemented. Need:
   - Census-based name distribution
   - Demographic diversity tracking
   - Name-to-generation plausibility

4. **Diversity Tracker Missing**: `diversity_tracker.py` is critical but not implemented. Per PROMPT.md, need to track coverage across:
   - User personas
   - Ages/skill levels
   - Formality/casualness
   - End users/recipients
   - Urgency levels
   - Relationship context
   - Audience size
   - Emotional context
   - Message position

5. **Edge Case - No Variations**: The fallback `_build_algorithmic` is mentioned but not implemented. What happens when:
   - A task has zero variations (all model calls failed)?
   - A variation is malformed?

### 2.3 Phase 3: LLM Enrichment

**Simulating**: Adding context-heavy enrichments

**What Works Well**:
- Enrichment ratio of 30% is reasonable
- Parallel batch processing (batch_size=10)
- Multiple enrichment types (prior_message, attachment, competing_objectives, tone_example, temporal)

**Issues Discovered**:

1. **Random State Not Preserved**: The enricher uses `random.random()` without seeding, making enrichment decisions non-reproducible. Should use the global random_seed.

2. **Missing Enrichment for All Required Types**:
   - **Regional English Variants**: PROMPT.md requires en-GB, en-AU, non-native prompts. Not implemented in Phase 3.
   - **Reply-to Context for All Message Positions**: Only applies to 'reply_in_thread' and 'follow_up', but some 'initial_outreach' might need prior context (e.g., "following our meeting").
   - **Multiple Recipients (CC)**: Handled separately, but Phase 3 should integrate with CC generator.

3. **Prompt Text Building Issues**: The `_build_prompt_text` method:
   - Uses hardcoded section headers that may leak meta-information to models
   - Doesn't handle revision tasks specially (should show original draft prominently)
   - Doesn't handle ambiguous prompts (should NOT add clarifying context)

4. **Cost Not Tracked**: Enrichment calls are not counted in cost estimation.

---

## 3. Evaluation Engine Simulation

### 3.1 Response Generation

**Simulating**: Collecting responses from all model pairs

**What Works Well**:
- Response metadata tracking (word_count, char_count, has_bullets, etc.)
- Failure categorization
- Immediate response saving

**Issues Discovered**:

1. **Missing Response Analyzer**: The plan lists `response_analyzer.py` but doesn't implement:
   - Format detection (bullets, headers, paragraphs)
   - Greeting/sign-off pattern detection
   - Detected formality level (for bias detection)

2. **Refusal Classification Not Implemented**: PROMPT.md requires categorizing WHY models refuse:
   - Safety refusal
   - Capability limitation
   - Misunderstanding
   - Incomplete response
   - Off-topic

   The plan mentions `refusal_classifier.py` but provides no implementation.

3. **Auto-Loss Logic Missing**: PROMPT.md says "If a model refuses... it automatically loses that comparison." The evaluation engine doesn't show this logic.

4. **Missing Instruction Compliance Checking**: While `compliance_tracker.py` is mentioned and a `compliance_checks` table exists, no implementation shows how to verify:
   - "Keep this under 100 words" -> count words
   - "Use exactly 3 bullet points" -> parse and count bullets
   - "Do not mention the budget" -> search for budget-related terms

### 3.2 Judge System

**Simulating**: Building judge prompts and collecting votes

**What Works Well**:
- Full scenario context provided to judges
- Both personas (Writing Expert + Recipient) implemented
- Position randomization with deterministic hashing
- Winner normalization to "gemini"/"competitor"/"tie"

**Issues Discovered**:

1. **Judge Output Parsing Fragility**: The expected format:
   ```
   WINNER: [A/B/TIE]
   CONFIDENCE: [1-5]
   QUALITY_A: [1-10]
   QUALITY_B: [1-10]
   REASONING: [explanation]
   ```

   But models may:
   - Use different formats
   - Add additional text
   - Use lowercase
   - Put reasoning first
   - Include line breaks in reasoning

   Need robust parser with fallbacks.

2. **Missing Judge Response Validation**: No validation that:
   - WINNER is exactly A, B, or TIE
   - CONFIDENCE is 1-5
   - QUALITY scores are 1-10
   - All fields are present

3. **Tie Handling in Aggregation**: The `aggregate_for_judge` method handles ties but the logic is confusing:
   ```python
   if gemini_count >= 3:
       return "gemini"
   elif competitor_count >= 3:
       return "competitor"
   else:
       # Compare totals
   ```

   This means 2 gemini + 2 competitor + 1 tie returns based on comparison, which is correct, but 2 gemini + 1 competitor + 2 ties would incorrectly favor gemini.

4. **Missing Judge Persona in Vote ID**: The `get_position_for_vote` uses judge_model but should include persona for complete uniqueness.

5. **Evaluation Criteria Not Structured**: PROMPT.md lists specific criteria:
   - Quality of writing
   - Appropriate length
   - Tone appropriateness
   - Effectiveness
   - Clarity
   - Task completion
   - Authenticity / "Human-like" quality
   - Cliche/boilerplate avoidance
   - Length appropriateness

   But the judge prompt asks for general evaluation, not scores per criterion. For meaningful weakness analysis, we need per-criterion scores.

### 3.3 Vote Aggregation

**Simulating**: Majority-of-majorities aggregation

**What Works Well**:
- Correct implementation of two-level majority voting
- Per-judge grouping before cross-judge aggregation
- Agreement calculation

**Issues Discovered**:

1. **Persona Aggregation Unclear**: The plan groups by `(judge_model, judge_persona)` meaning each combination gets 5 votes. With 3 judges x 2 personas = 6 groups. But the "majority of 3 judges" comment suggests combining personas per judge. Clarification needed:
   - Option A: 6 independent voters (3 judges x 2 personas), majority of 6
   - Option B: Combine personas per judge first, then majority of 3 judges

   PROMPT.md says "majority across the 3 judges" suggesting Option B, but the code implements Option A.

2. **Tie Breaking Inconsistency**: If judge majorities are [gemini, competitor, tie], the final result should be tie (no majority). But the code:
   ```python
   if gemini_judges > len(judge_majorities) / 2:
       final = "gemini"
   ```
   This means with 6 groups, you need >3 (i.e., 4+) to win. With 3 groups, you need >1.5 (i.e., 2+). This is correct.

3. **Quality Score Aggregation Missing**: Judge quality scores (1-10) are stored but never aggregated. For analysis, we need:
   - Average quality score per model per comparison
   - Quality differential (how much better was the winner?)

---

## 4. Checkpoint and Resumability Simulation

### 4.1 Checkpoint Manager

**Simulating**: Fine-grained checkpointing with atomic writes

**What Works Well**:
- Vote-level granularity for resume
- Atomic write with temp file + rename
- Circuit breaker state persistence
- Partial comparison tracking

**Issues Discovered**:

1. **High Checkpoint Frequency**: Saving after EVERY vote could cause:
   - I/O bottleneck (60,000 judge calls = 60,000 file writes)
   - Performance degradation

   Should batch checkpoints (e.g., every 10 votes or every comparison).

2. **Lock Contention**: Using a single `asyncio.Lock()` for all checkpoint operations could serialize parallel API calls. Consider per-comparison locks or lock-free approaches.

3. **Missing Crash Detection**: No mechanism to detect incomplete/corrupted checkpoint files. Should:
   - Include checksum/version in checkpoint
   - Create backup before overwriting
   - Validate on load

4. **Circuit Breaker State Format**: The `circuit_breaker_states` dict stores arbitrary state but doesn't specify:
   - What fields are required?
   - How to restore a circuit breaker from this state?

### 4.2 Run Directory Structure

**Simulating**: Creating the full directory structure per PROMPT.md

**What Works Well**:
- Matches PROMPT.md specification exactly
- Separate directories for prompts, responses, judgments, analysis, reports, logs
- Symlink to latest run
- Atomic file writes

**Issues Discovered**:

1. **Symlink on Windows**: The `symlink_to` call will fail on Windows without admin privileges. Need:
   ```python
   if platform.system() != 'Windows':
       latest_link.symlink_to(self.run_dir.name)
   ```

2. **Missing Cross-Platform Path Handling**: Some paths may have issues on Windows (max path length, special characters).

3. **Organization Functions Use model_dump**: The `organize_prompts_by_occupation` uses Pydantic's `model_dump()` which may not handle all custom types (enums, datetime) correctly without custom serializers.

---

## 5. Analysis and Statistics Simulation

### 5.1 Statistical Analysis

**Simulating**: Win rate analysis with confidence intervals

**What Works Well**:
- Wilson score interval (correct for proportions)
- Using `scipy.stats.binomtest` (not deprecated `binom_test`)
- Cohen's Kappa for inter-rater reliability
- Cohen's h for effect size

**Issues Discovered**:

1. **Exclusion of Ties in Binomial Test**: The code excludes ties (`decisive = wins + losses`) but this may understate uncertainty. Alternative: treat ties as 0.5 wins each.

2. **Missing Multiple Comparison Correction**: When testing many dimensions (job zone, occupation, industry, formality, etc.), need Bonferroni or FDR correction to avoid false positives.

3. **Cohen's Kappa Implementation Issues**: The implementation assumes two raters, but we have 3 judge models x 2 personas = 6 raters. Need:
   - Fleiss' Kappa for multi-rater reliability
   - Or pairwise Kappa calculations with averaging

4. **Missing Bootstrap Confidence Intervals**: For small sample sizes, Wilson CI may be insufficient. Bootstrap CIs would be more robust.

### 5.2 Bias Detection

**Simulating**: Detecting systematic biases

**What Works Well**:
- Position bias detection
- Length bias detection
- Model fingerprinting detection
- Formality drift detection

**Issues Discovered**:

1. **Missing Format Bias Detection**: PROMPT.md mentions "Does Model Y default to bullet points regardless of context?" but no detection for:
   - Bullet point overuse
   - Header overuse
   - Paragraph vs list preference

2. **Formality Detection Not Implemented**: The `detect_formality_drift` assumes `detected_formality` field exists on responses, but no implementation to detect formality level from response text.

3. **Missing Model-Specific Bias Tracking**: Should detect patterns like:
   - "Gemini consistently writes longer responses"
   - "GPT-5.2 overuses bullet points"
   - "Claude always includes pleasantries"

4. **Statistical Power for Bias Tests**: With small samples, bias tests may lack power. Should report:
   - Sample size
   - Power analysis
   - Minimum detectable effect size

---

## 6. TUI Implementation Simulation

### 6.1 Progress Dashboard

**Simulating**: Real-time progress visualization

**What Works Well**:
- Comprehensive layout matching PROMPT.md specification
- Reactive state updates
- Keyboard bindings for control
- Activity log with timestamps

**Issues Discovered**:

1. **Integration with Engine Missing**: The dashboard exists but there's no code showing how the EvaluationEngine sends updates to the dashboard. Need:
   - Event emitter/callback pattern
   - Shared state with locks
   - Or message queue

2. **Cost Tracking Requires Token Counts**: The dashboard shows cost but can only calculate after receiving API responses. Pre-call cost estimation needs token counting.

3. **Missing Error Panel Details**: The "ERRORS & WARNINGS" panel shows counts but not details. Should be expandable to show recent errors.

4. **Model Stats Table Not Updated**: The `on_mount` initializes the table but there's no method to update it with per-model win rates.

5. **ETA Calculation Issues**: The ETA uses simple linear extrapolation but doesn't account for:
   - Variable response times per model
   - Rate limit pauses
   - Retry overhead

### 6.2 Results Viewer

**Simulating**: Post-evaluation result exploration

**What Works Well**:
- Filter bar with multiple dimensions
- Side-by-side response comparison
- Drill-down capability

**Issues Discovered**:

1. **Placeholder Implementations**: Most methods are stubs (`pass` or `return ["All"]`). Full implementation needed for:
   - `_load_comparisons` - database query
   - `_get_occupations` - database query
   - `action_view_detail` - response loading
   - `action_view_judgments` - vote loading

2. **Missing Judgment Detail Screen**: Referenced but not implemented. Need screen showing:
   - All 5 votes per judge
   - Position for each vote
   - Reasoning from each vote

3. **Search Functionality Not Implemented**: Search input exists but no handler.

---

## 7. CLI Interface Simulation

### 7.1 CLI Commands

**Simulating**: Running evaluation from command line

**What Works Well**:
- Good command structure (run, view, compare, export)
- Preset system with customization
- Dry-run cost estimation
- Resume support

**Issues Discovered**:

1. **Missing `generate` Command**: For Phase 1 offline generation, need:
   ```bash
   ./eval generate --output data/offline_variations/
   ```

2. **Missing `validate` Command**: To check setup before running:
   ```bash
   ./eval validate --config config.json
   ```
   Should verify:
   - API key validity
   - O*NET database accessibility
   - ONET_WRITING_REFERENCE.md exists
   - OpenRouter model availability

3. **Config File Format Not Specified**: `--config` option exists but no documentation of config file format.

4. **Preset Loading Error**: Code assumes `PRESETS` is indexed by int, but should be dict with preset levels as keys.

5. **Missing API Key Handling**: No `--api-key` option or environment variable documentation.

---

## 8. Reporting Simulation

### 8.1 PDF Report Generation

**Simulating**: Creating the final analyst report

**What Works Well**:
- Listed in project structure
- Three-part structure specified (Dashboard, Statistical Analysis, Executive Summary)

**Issues Discovered**:

1. **No Implementation Provided**: `pdf_generator.py` is mentioned but not implemented at all. This is a major gap.

2. **Library Choice Unclear**: Plan mentions "reportlab or weasyprint" but doesn't decide. These have very different APIs:
   - ReportLab: Low-level, precise control, steeper learning curve
   - WeasyPrint: HTML/CSS based, easier but less control

3. **Chart Integration Missing**: How do Plotly charts get embedded in PDF? Need:
   - Export charts as PNG/SVG
   - Include in PDF layout
   - Handle chart sizing/positioning

4. **Missing Weakness Analysis Section**: PROMPT.md emphasizes "identifies specific areas of weakness in Gemini effective writing" but no implementation for:
   - Identifying dimensions where Gemini underperforms
   - Ranking weaknesses by severity
   - Providing example comparisons for each weakness

---

## 9. Consistency Check with PROMPT.md

### 9.1 Requirements Fully Covered

| Requirement | Status | Notes |
|-------------|--------|-------|
| O*NET task-level granularity | Covered | Using ONET_WRITING_REFERENCE.md |
| Pro-tier and Flash-tier comparisons | Covered | Model pairs defined |
| Best-of-5 majority-of-majorities | Covered | Vote aggregator implements |
| Position bias mitigation | Covered | Deterministic shuffling |
| Dual judge personas | Covered | Expert + Recipient |
| Three judge models | Covered | Claude, GPT, Gemini |
| Wilson score intervals | Covered | StatisticalAnalyzer |
| Cohen's Kappa | Covered | Inter-rater reliability |
| 10 presets | Referenced | But not implemented |
| Live cost estimates | Referenced | But token counting missing |
| TUI progress dashboard | Partially covered | Layout done, integration missing |
| Results TUI viewer | Partially covered | Mostly stubs |
| PDF report | Not covered | No implementation |
| Checkpoint/resume | Covered | Fine-grained |
| Atomic file operations | Covered | Temp + rename |

### 9.2 Requirements Missing or Incomplete

1. **Instruction-Following Compliance Verification**: Schema exists but no actual verification logic.

2. **Sensitive Topic Tagging**: Schema has field but no tagging logic during prompt generation.

3. **Refusal Categorization**: Five categories defined in PROMPT.md but no classifier.

4. **Regional English Variants**: Distribution not specified, no enrichment for en-GB/en-AU.

5. **Real Company Database**: Referenced but not provided (need 500+ companies).

6. **Name Generator with Demographics**: Referenced but not implemented.

7. **Phase 1 Offline Generation as Separate Step**: Not clear if this is a CLI command or automatic.

8. **Cross-Run Comparison**: `cross_run_compare.py` mentioned but not implemented.

9. **Auto-Generated README**: `readme_generator.py` mentioned but not implemented.

10. **Heatmaps**: `heatmaps.py` mentioned but not implemented.

### 9.3 Explicit Contradictions

1. **Judge Grouping**: Plan groups by `(judge_model, judge_persona)` creating 6 groups, but PROMPT.md says "majority of the 3 judges" suggesting 3 groups.

2. **Communication Channel**: Plan correctly notes "NOT an enum" but some code uses conditional checks on specific channel values, which implicitly creates categories.

3. **Enrichment Ratio**: Plan uses 30% but PROMPT.md doesn't specify a ratio. May be too high or too low.

---

## 10. Edge Cases and Gotchas

### 10.1 API-Related Edge Cases

1. **Model Unavailability**: What if a model (e.g., Grok-4.1) becomes unavailable mid-run?
   - Need: Model substitution logic or graceful degradation
   - Current: Would fail with retry exhaustion

2. **Context Length Exceeded**: Long prompts with attachments + prior messages could exceed context limits
   - Need: Prompt truncation strategy
   - Current: Would fail with API error

3. **Different Response Formats**: Models may return different structures
   - Need: Normalize response extraction (some use `message.content`, others `choices[0].message.content`)
   - Current: Assumes unified OpenRouter format

4. **Token Limit Responses**: Some models may truncate responses without clear finish_reason
   - Need: Detection and retry with shorter prompt
   - Current: Would accept incomplete response

### 10.2 Data-Related Edge Cases

1. **O*NET Tasks Without Writing**: Some tasks in the reference might be edge cases
   - Example: "Operate heavy machinery" flagged as writing-related
   - Need: Validation/filtering mechanism

2. **Company-Occupation Mismatch**: Sampling may produce unrealistic combinations
   - Example: "Construction worker at Goldman Sachs"
   - Need: Occupation-appropriate company filtering

3. **Empty Prompt Fields**: Some prompts may have all optional fields empty
   - Need: Ensure base prompt is always meaningful
   - Current: Could generate very sparse prompts

4. **Duplicate Prompts**: With random sampling, near-duplicates are possible
   - Need: Deduplication check
   - Current: No deduplication

### 10.3 Evaluation Edge Cases

1. **All Ties**: If a comparison has 5 ties from all judges, what's the result?
   - Current: Would return "tie"
   - Issue: This may be too common if models are similar

2. **Refusal vs Refusal**: Both models refuse the same prompt
   - Need: Special handling (mutual loss? skip?)
   - Current: Not addressed

3. **Very Short Responses**: One-word or empty responses
   - Need: Minimum length threshold for "valid" response
   - Current: Would accept any response

4. **Identical Responses**: Both models produce exact same text
   - Need: Detection and special handling
   - Current: Would be judged normally (likely ties)

### 10.4 System Edge Cases

1. **Disk Full**: Run directory can't be created or written to
   - Need: Pre-check for disk space
   - Current: Would fail with OS error

2. **Network Interruption**: Long periods without connectivity
   - Need: Reconnection logic, offline mode for viewing results
   - Current: Would fail with timeout

3. **Process Kill vs Ctrl+C**: Hard kill doesn't save checkpoint
   - Need: Signal handler for SIGTERM, periodic auto-checkpoint
   - Current: Only handles graceful quit

4. **Parallel Run Conflicts**: Two runs using same output directory
   - Need: Lock file or unique run ID
   - Current: Would overwrite each other

---

## 11. Performance Concerns

### 11.1 Bottlenecks Identified

1. **Per-Vote Checkpointing**: Writing to disk after every single vote
   - Impact: Could add 50ms+ latency per vote
   - Solution: Batch checkpoints every N operations

2. **JSON Parsing in Phase 1**: Large offline_variations directory with thousands of files
   - Impact: Slow startup time when loading cached variations
   - Solution: Use SQLite or single large JSON file

3. **Database Queries**: No connection pooling for aiosqlite
   - Impact: Connection overhead on every query
   - Solution: Keep connection open throughout run

4. **TUI Updates**: Updating all widgets on every event
   - Impact: UI lag with high event rate
   - Solution: Throttle updates to max 10 per second

### 11.2 Memory Concerns

1. **Loading All Prompts**: With 10,000+ prompts, keeping all in memory
   - Impact: Could use 1GB+ RAM
   - Solution: Stream prompts from database

2. **Vote History**: Storing all votes in memory for aggregation
   - Impact: Memory grows linearly with prompts
   - Solution: Aggregate incrementally, only keep counts

3. **TUI Log**: Activity log with unlimited history
   - Impact: Memory leak over long runs
   - Solution: Already capped at 50 lines, good

---

## 12. Security Considerations

### 12.1 API Key Handling

1. **Key in Config File**: Could be committed to git
   - Need: Environment variable support, .gitignore pattern
   - Current: Optional field in EvalConfig

2. **Key in Logs**: Could be logged on error
   - Need: Sanitize API keys before logging
   - Current: Not addressed

### 12.2 Data Privacy

1. **Real Company Names**: Legal concerns with using real companies in scenarios
   - Need: Disclaimer that scenarios are fictional
   - Current: Uses real companies as PROMPT.md requires

2. **Prompt Storage**: Prompts may contain personal-seeming names/emails
   - Need: Note that names are fictional
   - Current: Not addressed

---

## 13. Summary of Critical Issues

### Must Fix Before Implementation

1. **ONET_WRITING_REFERENCE.md Parser**: No implementation exists
2. **Phase 1 Offline Generator Cost**: ~$1,200 cost not clearly communicated
3. **Judge Grouping Ambiguity**: 3 judges vs 6 (judge x persona)
4. **PDF Report Generator**: Completely missing
5. **Token Counter**: Required for cost estimation but not implemented
6. **Compliance Verifier**: Required for instruction-following tests but not implemented

### Should Fix

1. **Company Database**: Need actual data for 500+ companies
2. **Name Generator**: Need census-based implementation
3. **Results Viewer**: Mostly stubs
4. **Cross-Run Comparison**: Mentioned but not implemented

### Nice to Have

1. **Heatmaps**: Visualization enhancement
2. **Fleiss' Kappa**: Multi-rater reliability
3. **Bootstrap CIs**: Statistical robustness
4. **Windows Symlink Handling**: Cross-platform support

---

## 14. Recommendations

1. **Clarify Judge Aggregation**: Explicitly decide between 3-judge and 6-voter models and update all documentation consistently.

2. **Implement Stub Modules**: Complete all referenced but unimplemented modules before coding begins.

3. **Add Phase 1 CLI Command**: Make offline generation a separate, clearly documented step.

4. **Define ONET_WRITING_REFERENCE.md Format**: Create or document the actual format of this critical input file.

5. **Choose PDF Library**: Make a decision between ReportLab and WeasyPrint and design report templates.

6. **Add Per-Criterion Judging**: Modify judge prompt to collect scores for each evaluation criterion.

7. **Batch Checkpointing**: Change from per-vote to per-comparison checkpointing with vote-level state.

8. **Create Data Files**: Generate companies.json and names_census.json before starting implementation.

9. **Add Validation Command**: Create CLI command to verify all prerequisites before running eval.

10. **Document Config Format**: Provide sample config.json file in repository.
