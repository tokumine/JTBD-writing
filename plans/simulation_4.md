# Simulation Report 4: Implementation Dry Run of Master Plan

## Executive Summary

This simulation walks through implementing the complete Master Plan Draft for the Gemini Writing Evaluation Framework. I methodically trace through each component as if actually building it, documenting what works well, what is unclear or problematic, missing pieces, potential edge cases, and inconsistencies with PROMPT.md requirements.

---

## 1. Project Structure and Setup Simulation

### 1.1 Directory Structure Creation

**What Works Well:**
- The project structure at `gemini-writing-eval/` is comprehensive and well-organized
- Clear separation into `src/`, `data/`, `results/`, `tests/`, and `db/` directories
- Modular organization within `src/` (api, config, data, eval, prompts, storage, tui, analysis, reports)

**Issues Identified:**

1. **Missing `validation/` directory**: The master plan mentions an `onet_schema.py` file in the project structure but there's no `validation/` subdirectory shown. Should be added:
   ```
   src/validation/
       __init__.py
       onet_schema.py
   ```

2. **Conflict between `db/` and `data/`**:
   - `db/onet.db` and `db/ONET_WRITING_REFERENCE.md` are shown
   - But `data/companies.json`, `data/names_census.json`, `data/offline_variations/` are separate
   - This split is potentially confusing - consider consolidating

3. **pyproject.toml not specified**: The plan shows `pyproject.toml` exists but doesn't provide its contents. Need to specify:
   - Python version requirement (3.11+)
   - Dependencies: httpx, pydantic, aiosqlite, textual, rich, plotly, reportlab/weasyprint, typer, scipy, numpy
   - Entry points for CLI

### 1.2 Environment Setup

**Missing Components:**
- `.env.example` mentioned but not defined - needs to specify:
  ```
  OPENROUTER_API_KEY=your_key_here
  ```
- No `.gitignore` specified (should exclude `results/`, `.env`, `__pycache__/`, etc.)

---

## 2. Data Layer Simulation

### 2.1 O*NET Extractor Implementation

**Walking Through Implementation:**

The plan references `ONET_WRITING_REFERENCE.md` as a pre-processed file created by Opus. However:

**Critical Gap #1**: The format of `ONET_WRITING_REFERENCE.md` is completely unspecified.

Questions that must be answered:
- Is it structured Markdown with parseable sections?
- Is it JSON embedded in Markdown?
- Does it contain task IDs that map to the SQLite database?
- What fields does it have for each task?

**Assumed Format (needs verification):**
```json
{
  "tasks": [
    {
      "task_id": "12345",
      "onetsoc_code": "11-1011.00",
      "occupation_title": "Chief Executives",
      "task_statement": "Draft correspondence for executive review",
      "job_zone": 5,
      "writing_context": "formal correspondence"
    }
  ]
}
```

**Implementation Issue:**
```python
# src/data/onet_extractor.py - The plan doesn't show this file's implementation
# Need to handle both SQLite queries AND ONET_WRITING_REFERENCE.md parsing
```

**Missing Implementation:**
- How to extract writing-relevant tasks from `ONET_WRITING_REFERENCE.md`
- Fallback logic if reference file is missing
- Validation of task data against the SQLite schema

### 2.2 Company Database Implementation

**Walking Through:**
```python
# src/data/company_database.py
# Plan mentions 500+ real companies but doesn't provide the data
```

**Issues:**
1. **No `data/companies.json` provided**: This is a dependency. Need to create/source:
   - Fortune 500 companies
   - Mid-market companies
   - Small businesses
   - Startups
   - Each with: name, size, industry, NAICS code, is_public, employee_count

2. **NAICS mapping incomplete**: The `naics_mapper.py` needs the actual NAICS code database. While O*NET contains some industry info, the mapping isn't automatic.

3. **Company selection bias**: Real companies may have uneven training data representation across models. This is acknowledged but no specific mitigation is implemented.

### 2.3 Name Generator Implementation

**Walking Through:**
```python
# src/data/name_generator.py
# Plan mentions Census-based diverse names but doesn't provide implementation
```

**Missing:**
1. **No `data/names_census.json` provided**: Need actual Census name data with:
   - First names with demographic distribution
   - Last names with ethnic/cultural origin markers
   - Frequency weights for realistic sampling

2. **Age-to-generation mapping is simplistic**:
   ```python
   def _generation_to_age(self, generation: str) -> int:
       # Plan doesn't show implementation details
       # Gen Z: 1997-2012 (ages 14-29 in 2026)
       # Millennial: 1981-1996 (ages 30-45 in 2026)
       # Gen X: 1965-1980 (ages 46-61 in 2026)
       # Boomer: 1946-1964 (ages 62-80 in 2026)
   ```

---

## 3. Phase 1: Offline LLM Generation Simulation

### 3.1 Walking Through Phase1OfflineGenerator

**What Works Well:**
- Uses ALL evaluated models to avoid single-model bias
- Caches results to `data/offline_variations/`
- Structured output with PersonaVariation dataclass

**Issues Identified:**

1. **Model ID Inconsistency**: The plan uses these model IDs:
   ```python
   GENERATION_MODELS = [
       "google/gemini-3.0-pro-preview",
       "google/gemini-3.0-flash-preview",
       "openai/gpt-5.2-thinking-preview",
       "openai/gpt-4.1-preview",
       "anthropic/claude-opus-4.5-20251101",
       "anthropic/claude-sonnet-4-20250514"
   ]
   ```

   **Problem**: These model IDs may not match actual OpenRouter model identifiers. Need to verify against OpenRouter API.

2. **JSON Parsing Fragility**:
   ```python
   def _parse_variations(self, content: str, task_id: str, model: str):
       # Extract JSON from response
       if '```json' in content:
           content = content.split('```json')[1].split('```')[0]
   ```

   **Issues:**
   - What if model returns malformed JSON?
   - What if model doesn't use code fences?
   - What if some fields are missing?
   - No schema validation of parsed output

3. **Cost Explosion Risk**: For 20,000 O*NET tasks × 6 models × 5 variations = 600,000 LLM calls just for Phase 1.

   **Missing**:
   - Progress tracking for Phase 1
   - Resumability of Phase 1 generation
   - Cost estimation before Phase 1

4. **Empty Cache File Handling**: If `_generate_for_task` fails for all models, an empty cache file might be written, causing issues on subsequent runs.

### 3.2 Cost Calculation for Phase 1

**Rough Estimate:**
- 20,000 tasks × 6 models = 120,000 API calls
- Average ~500 input tokens + ~1000 output tokens per call
- At roughly $0.01-0.03 per call average across models
- **Phase 1 alone: $1,200 - $3,600**

This is NOT included in the preset cost estimates!

---

## 4. Phase 2: Algorithmic Combination Simulation

### 4.1 Walking Through Phase2AlgorithmicCombiner

**What Works Well:**
- Deterministic with random seed
- Stratification by job zone and SOC group
- Uses pre-generated variations when available

**Issues Identified:**

1. **Stratification Conflict**: Two stratification methods are applied sequentially:
   ```python
   if stratify_by_job_zone:
       tasks = self._stratify_by_job_zone(tasks, num_prompts)
   if stratify_by_soc_group:
       tasks = self._stratify_by_soc_group(tasks, num_prompts)
   ```

   **Problem**: The second stratification destroys the first. If 100 prompts stratified by job zone (20 per zone), then re-stratified by SOC group, you don't get 20 per zone anymore.

2. **Missing NAICS Stratification**: PROMPT.md requires industry diversity via NAICS, but there's no `stratify_by_naics` method.

3. **`_build_from_variation` incomplete**:
   ```python
   def _build_from_variation(self, task, variation, index) -> WritingPrompt:
       # ...
       return WritingPrompt(
           # ...
           full_prompt=""  # Empty! Phase 3 must fill this
       )
   ```

   What happens if Phase 3 is skipped or fails? Prompts with empty `full_prompt` would be invalid.

4. **`_build_algorithmic` not implemented**: The fallback for tasks without variations is mentioned but not shown:
   ```python
   else:
       # Fallback: generate algorithmically
       prompt = self._build_algorithmic(task, i)
   ```

---

## 5. Phase 3: LLM Enrichment Simulation

### 5.1 Walking Through Phase3Enricher

**What Works Well:**
- 30% enrichment ratio is reasonable
- Multiple enrichment types (prior message, attachments, competing objectives, tone examples, temporal context)
- Parallel batch processing

**Issues Identified:**

1. **Race Condition in indices_to_enrich**:
   ```python
   indices_to_enrich = set(random.sample(range(len(prompts)), num_to_enrich))
   ```
   Uses `random.sample` without seeding - not deterministic/reproducible!

2. **Enrichment Model Rotation is Stateful**:
   ```python
   def _get_next_model(self) -> str:
       model = self.ENRICHMENT_MODELS[self.model_index % len(self.ENRICHMENT_MODELS)]
       self.model_index += 1
       return model
   ```
   This state is lost between runs. If resumed, rotation restarts.

3. **Temporal Context Date Hardcoded**:
   ```python
   base_date = datetime(2026, 1, 6)  # Per PROMPT.md
   ```
   Good that it follows PROMPT.md, but should be configurable or read from config.

4. **`_enrich_single_prompt` doesn't handle all enrichment types**:
   - Missing: Reply-To context for ALL reply scenarios
   - Missing: Regional English variants (en-GB, en-AU, non-native)
   - Missing: Multiple recipients (CC situations) - delegated to separate generator but not integrated

5. **Error Swallowing**:
   ```python
   for result in results:
       if isinstance(result, dict):  # Silently ignores exceptions
   ```
   Failed enrichments are silently ignored. Should at least log.

### 5.2 _build_prompt_text Issues

```python
def _build_prompt_text(self, prompt: WritingPrompt) -> str:
    # ...
    sections.append("\nPlease write the requested content. Do not include meta-commentary about the task.")
```

**Missing from PROMPT.md Requirements:**
- No mention of "Natural (No Constraints)" - should NOT enforce length/format
- Should explicitly state: "Choose appropriate length and format for this task"
- Missing instruction about regional English adaptation when `recipient_english_variant` is set

---

## 6. Prompt Schema Simulation

### 6.1 Walking Through WritingPrompt Schema

**What Works Well:**
- Comprehensive coverage of dimensions from PROMPT.md
- Proper use of Pydantic for validation
- Enums for constrained fields
- Optional fields for enrichments

**Issues Identified:**

1. **Enum vs String Inconsistency**:
   ```python
   communication_channel: Optional[str] = None  # NOT an enum - dynamic
   ```
   But `emotional_context`, `message_position` ARE enums. This inconsistency may cause confusion.

2. **Missing Fields from PROMPT.md**:
   - `recipient_english_variant` exists but `writer_english_variant` is on `WriterPersona` - inconsistent nesting
   - No explicit `audience_type` (internal vs external)
   - No `industry_naics` at prompt level (only nested in `CompanyContext`)

3. **Schema Validation Gaps**:
   ```python
   job_zone: int = Field(ge=1, le=5)
   formality_level: int = Field(ge=1, le=5)
   urgency_level: int = Field(ge=1, le=5)
   ```
   Good constraints, but what about `naics_code` format? Should validate it's 6 digits.

4. **RecipientPersona.relationship too limited**:
   ```python
   relationship: Literal["new_contact", "acquaintance", "colleague",
                         "manager", "direct_report", "client", "vendor"]
   ```
   Missing from PROMPT.md: "boss", "peer" (distinct from colleague), external partners

---

## 7. Evaluation Engine Simulation

### 7.1 Judge Prompt Building

**What Works Well:**
- Full scenario context provided to judges
- Clear evaluation criteria
- Position bias warning in prompt
- Dual persona system (expert + recipient)

**Issues Identified:**

1. **Recipient System Prompt Variable Substitution**:
   ```python
   RECIPIENT_SYSTEM = """You are {recipient_name}, {recipient_title}.
   Your relationship with the sender: {relationship}
   ```

   **Problem**: What if recipient has non-native English variant? The judge should adapt expectations accordingly. This isn't mentioned in the system prompt.

2. **Missing Evaluation Criteria from PROMPT.md**:
   The judge prompt mentions:
   - Appropriateness, clarity, organization, tone
   - Achievement of communication objective
   - Professionalism
   - Instruction compliance

   **Missing**:
   - **"Authenticity / Human-like quality"** - CRITICAL per PROMPT.md
   - **"Cliché/boilerplate avoidance"** - explicitly mentioned in PROMPT.md
   - **"Length appropriateness"** - is the response RIGHT length for task?

3. **Output Format Parsing Not Shown**:
   ```
   WINNER: [A/B/TIE]
   CONFIDENCE: [1-5]
   QUALITY_A: [1-10]
   QUALITY_B: [1-10]
   REASONING: [Your explanation]
   ```

   **Missing**: The `judge_parser.py` to parse this format. What if judge doesn't follow format exactly?

### 7.2 Vote Aggregator Simulation

**What Works Well:**
- Deterministic position assignment using hash
- Proper normalization from A/B to gemini/competitor
- Majority-of-majorities aggregation

**Issues Identified:**

1. **Tie Handling in aggregate_for_judge**:
   ```python
   def aggregate_for_judge(self, votes: List[JudgeVote]) -> str:
       if gemini_count >= 3:
           return "gemini"
       elif competitor_count >= 3:
           return "competitor"
       else:
           # If no clear majority, compare totals
   ```

   **Problem**: With 5 votes, if you get 2-2-1 (gemini-competitor-tie), neither reaches 3. The fallback compares 2 vs 2, resulting in tie. This is correct but the threshold logic could be clearer.

2. **Agreement Calculation Questionable**:
   ```python
   agreement = max(gemini_wins, competitor_wins) / len(judge_majorities)
   ```

   This isn't Cohen's Kappa - it's just majority percentage. For 3 judges, if all agree, agreement = 1.0. If 2-1 split, agreement = 0.67. This should be labeled differently (e.g., "majority_strength") to avoid confusion with proper inter-rater reliability.

---

## 8. Storage Layer Simulation

### 8.1 Run Directory Structure

**What Works Well:**
- Self-contained run directories
- Atomic writes with temp file + rename
- 'latest' symlink for convenience
- Comprehensive file organization

**Issues Identified:**

1. **Symlink Race Condition**:
   ```python
   def _create_latest_symlink(self, base_dir: Path):
       if latest_link.is_symlink():
           latest_link.unlink()
       # Race condition here if another process creates link
       latest_link.symlink_to(self.run_dir.name)
   ```

2. **organize_prompts_by_* Functions Not Async**:
   ```python
   def organize_prompts_by_occupation(self, prompts):
       # Synchronous I/O in async context?
   ```
   If called from async evaluation loop, this blocks.

### 8.2 Checkpoint Manager Simulation

**What Works Well:**
- Fine-grained checkpointing (per-vote level)
- Atomic writes
- Circuit breaker state persistence
- Partial comparison recovery

**Issues Identified:**

1. **Lock Contention**:
   ```python
   async def save(self):
       async with self._lock:
   ```
   Every vote completion triggers a save. With 60,000+ votes, this could be a bottleneck.

   **Suggestion**: Batch checkpoint saves (e.g., every 10 votes or every 5 seconds)

2. **Memory Growth**:
   ```python
   completed_votes: Set[str] = field(default_factory=set)
   ```
   For 60,000 votes, storing all vote IDs in memory grows unbounded. Should consider bloom filter or periodic pruning.

3. **Checkpoint File Size**:
   Full checkpoint with 60,000 vote IDs could be several MB. Each save rewrites entire file.

### 8.3 Database Schema Simulation

**What Works Well:**
- Proper foreign keys
- Indices on frequently queried columns
- Covers all required data

**Issues Identified:**

1. **Missing Index on `prompts.emotional_context`**: Frequently filtered but no index.

2. **`sensitive_topics` Stored as Comma-Separated String**:
   ```sql
   sensitive_topics TEXT,
   ```
   This makes querying individual topics difficult. Should be a separate table or JSON field.

3. **No Explicit Transaction Handling in `save_prompt`**:
   ```python
   await self._connection.execute(...)
   await self._connection.commit()
   ```
   If multiple concurrent saves, commits might interleave unexpectedly.

---

## 9. Statistical Analysis Simulation

### 9.1 Walking Through StatisticalAnalyzer

**What Works Well:**
- Uses current scipy API (binomtest, not deprecated binom_test)
- Wilson score intervals for confidence
- Cohen's h effect size
- Cohen's Kappa for inter-rater reliability

**Issues Identified:**

1. **cohens_kappa Implementation Has Edge Case Bug**:
   ```python
   if expected == 1:
       return 1.0
   ```
   If expected == 1 exactly (all in one category), denominator would be 0. But the check prevents division by zero only if expected is exactly 1.0, not close to 1.0.

2. **analyze_win_rate Excludes Ties from Statistical Tests**:
   ```python
   decisive = wins + losses  # Exclude ties for statistical tests
   p_value = self.binomial_test(wins, decisive)
   ```
   This is a methodological choice but should be documented. Alternative: treat ties as 0.5 wins each.

3. **No Multiple Testing Correction**: Running many statistical tests (by job zone, by occupation, by formality, etc.) inflates Type I error rate. Should apply Bonferroni or FDR correction.

### 9.2 Bias Detection Simulation

**What Works Well:**
- Position bias detection
- Length bias detection
- Model fingerprinting detection
- Formality drift detection

**Issues Identified:**

1. **detect_length_bias Requires Word Counts Not in Vote Data**:
   ```python
   gemini_len = c["gemini_word_count"]
   comp_len = c["competitor_word_count"]
   ```
   The comparison dict must include word counts from responses. Need to ensure this data flows through.

2. **detect_model_fingerprinting Chi-Square May Fail**:
   ```python
   chi2, p_value, _, _ = stats.chi2_contingency(contingency)
   ```
   If any cell is 0, chi-square may produce unreliable results. Should check expected frequencies.

3. **detect_formality_drift References Undefined Field**:
   ```python
   response_formality = r["detected_formality"]  # 1-5
   ```
   Where is formality detection implemented? Not in ResponseAnalyzer shown in plan.

---

## 10. TUI Implementation Simulation

### 10.1 Progress Dashboard

**What Works Well:**
- Clean layout with key information
- Interactive controls (pause, quit, detail view)
- Real-time updates via reactive properties
- ETA calculation

**Issues Identified:**

1. **No Integration with EvaluationEngine**:
   ```python
   dashboard = ProgressDashboard()
   # Would integrate engine with dashboard
   dashboard.run()
   ```
   The actual message passing between engine and dashboard isn't implemented.

2. **Model Stats Table Never Populated**:
   ```python
   async def on_mount(self):
       table = self.query_one("#model-stats", DataTable)
       table.add_columns("Model", "Wins", "Losses", "Ties", "Win%")
   ```
   Columns added but no `add_row` calls shown.

3. **Memory Management**: Keeping 50 lines of activity log is good, but if running for 48 hours, may want to persist to file.

### 10.2 Results Viewer TUI

**Issues:**
1. **Incomplete Implementation**: Many methods just have `pass` or comments
2. **No actual database queries shown**
3. **Filter functionality not implemented**

---

## 11. CLI Interface Simulation

**What Works Well:**
- Clean typer-based interface
- Preset support with customization
- Resume capability
- Export functionality

**Issues Identified:**

1. **Missing Commands from PROMPT.md**:
   - `./eval --dry-run` - mentioned in PROMPT.md but not in CLI
   - Cost estimate display format doesn't match the elaborate box shown in PROMPT.md

2. **TUI Integration Incomplete**:
   ```python
   if no_tui:
       asyncio.run(run_eval())
   else:
       dashboard = ProgressDashboard()
       dashboard.run()
   ```
   When using TUI, the actual evaluation doesn't run! Need to integrate both.

3. **No Environment Variable Loading**:
   ```python
   openrouter_api_key: Optional[str] = None
   ```
   Should load from `OPENROUTER_API_KEY` environment variable by default.

---

## 12. Model Configuration Simulation

**Issues Identified:**

1. **Model IDs Not Verified**: Plan uses preview model IDs that may not exist on OpenRouter:
   - `google/gemini-3.0-pro-preview`
   - `openai/gpt-5.2-thinking-preview`
   - These need verification against actual OpenRouter API

2. **Missing Model Tier Classification**: PROMPT.md requires Pro-tier vs Flash-tier separation, but config doesn't enforce this:
   ```python
   model_pairs: List[Tuple[str, str]] = [
       # Mix of pro and flash pairs
   ]
   ```
   Should validate Gemini Pro only pairs with Pro-tier, Flash only with Flash-tier.

3. **Default Random Seed Generation**:
   ```python
   random_seed: int = Field(default_factory=lambda: secrets.randbelow(2**32))
   ```
   Using `secrets` for seed is overkill - `random.randint` would suffice and be more portable.

---

## 13. Special Prompt Types Simulation

### 13.1 Constraint Generator

**Issues:**
1. **constraint_probability Default 0.15**: 15% of prompts get constraints. Is this enough to get statistical power on instruction-following analysis?

2. **Compliance Verification Missing**: Constraints are generated but `compliance_tracker.py` implementation isn't shown. How do we verify a response follows "exactly 3 bullet points"?

### 13.2 Revision Task Generator

**Issues:**
1. **Verbose Draft Generation Incomplete**:
   ```python
   if revision_type == "concise":
       original_draft = "[To be generated: verbose version of the task response]"
   ```
   This placeholder needs Phase 3 to fill, but Phase 3 doesn't show this logic.

### 13.3 Ambiguity Generator

**Issues:**
1. **Over-aggressive Ambiguity**:
   ```python
   elif ambiguity_type == "unclear_ask":
       prompt.onet_task = f"Write something regarding {prompt.onet_task.split()[0]} matters"
   ```
   This destroys the original task context almost entirely. Models will have nothing to work with.

### 13.4 CC Generator

**What Works Well:**
- Multiple CC scenarios
- Will-be-forwarded-to context

**Missing:**
- Integration point in Phase 2/3 pipeline not clear

---

## 14. Consistency Check Against PROMPT.md

### 14.1 Items Fully Covered

- [x] O*NET task-level granularity
- [x] Pairwise SxS comparisons
- [x] Best-of-5 judgments
- [x] Position randomization
- [x] Dual judge personas (Writing Expert + Recipient)
- [x] Three judge models (ensemble)
- [x] Majority-of-majorities aggregation
- [x] Checkpoint/resume system
- [x] Results directory structure
- [x] 10 preset configurations
- [x] Live cost estimation
- [x] Real company names
- [x] Realistic person names
- [x] Temporal context
- [x] Attachments/references
- [x] Competing objectives
- [x] Reply-to context
- [x] CC/multiple recipients
- [x] Tone matching examples
- [x] Revision/editing tasks
- [x] Ambiguity handling
- [x] Instruction-following constraints
- [x] Sensitive topic tracking
- [x] Refusal categorization
- [x] Response metadata tracking
- [x] Wilson confidence intervals
- [x] Inter-judge agreement metrics

### 14.2 Items Partially Covered

- [~] Regional English variants: Schema supports it, but no generation logic
- [~] Communication channel inference: Mentioned but implementation not shown
- [~] Bias detection: Position and length covered, model fingerprinting partial
- [~] PDF report generation: `pdf_generator.py` mentioned but not implemented
- [~] Cross-run comparison: `compare` CLI command exists but logic incomplete
- [~] Formality drift detection: References undefined `detected_formality` field

### 14.3 Items Missing or Incomplete

- [ ] **"Authenticity / Human-like quality" evaluation criteria**: Not in judge prompts
- [ ] **"Cliché/boilerplate avoidance" criteria**: Not in judge prompts
- [ ] **Heatmaps by dimension/occupation**: Mentioned in reports but no implementation
- [ ] **Executive summary generation**: File path defined but no generation logic
- [ ] **Auto-generated README for each run**: Mentioned but not implemented
- [ ] **Failure report at end of run**: failures.log exists but no summary generation
- [ ] **ONET_WRITING_REFERENCE.md parser**: Critical dependency, format undefined
- [ ] **companies.json data file**: Referenced but not provided
- [ ] **names_census.json data file**: Referenced but not provided
- [ ] **Detailed TUI progress dashboard per PROMPT.md spec**: The elaborate ASCII art dashboard shown in PROMPT.md isn't matched by implementation

---

## 15. Gotchas and Edge Cases

### 15.1 API/Network Issues

1. **OpenRouter Rate Limits Vary by Model**: Plan mentions per-model limits but doesn't specify actual values
2. **Timeout Handling**: What's the default timeout? Not specified
3. **Network Partition Recovery**: If connection lost mid-batch, how does circuit breaker recover?

### 15.2 Data Issues

1. **O*NET Task Deduplication**: Some tasks may be near-duplicates across occupations
2. **Company Name Collisions**: "Apple" could be Apple Inc. or a restaurant
3. **Name Generation Bias**: Census data may not reflect current US workforce demographics

### 15.3 Evaluation Issues

1. **Judge Self-Evaluation Bias**: Gemini 3 Pro judges Gemini 3 Pro outputs - conflict of interest?
2. **Prompt Length Variance**: Simple vs context-rich prompts have very different token counts
3. **Model Versioning**: If OpenRouter updates model versions mid-eval, results may be inconsistent

### 15.4 Statistical Issues

1. **Low N in Subgroups**: Stratification may result in few prompts per job zone × industry combination
2. **Correlation Between Tests**: Win rates by job zone aren't independent of win rates by occupation
3. **Survivorship Bias**: If certain prompts always fail on one model, that model gets auto-losses skewing results

---

## 16. Performance Concerns

### 16.1 Memory Usage

- Phase 1 variations: 20,000 tasks × 6 models × 5 variations = 600,000 PersonaVariation objects
- At ~1KB each = ~600MB just for variations
- Checkpoint completed_votes: 60,000+ strings = ~6MB

### 16.2 Disk Usage

- Each response: ~500-2000 tokens = ~2-8KB text
- 500 prompts × 8 models × average 4KB = ~16MB responses
- 60,000 judgments × average 1KB = ~60MB judgments
- Plus database, logs, reports

### 16.3 Time Estimates

- Phase 1 offline: 120,000 API calls at 2 calls/sec = ~17 hours (one-time)
- Preset 6 (500 prompts):
  - 500 × 2 = 1,000 response generations
  - 500 × 4 pairs × 3 judges × 5 votes × 2 personas = 60,000 judge calls
  - At 10 calls/sec = ~100 minutes of API time
  - Plus overhead, closer to 3-6 hours as estimated

---

## 17. Recommendations

### 17.1 Critical Fixes Required

1. **Define ONET_WRITING_REFERENCE.md format** - Cannot proceed without this
2. **Provide companies.json and names_census.json** - Core dependencies
3. **Add authenticity/cliché criteria to judge prompts** - PROMPT.md requirement
4. **Fix stratification conflict** - Currently destroys first stratification
5. **Implement _build_algorithmic fallback** - For prompts without variations
6. **Add Phase 1 cost warning** - Users need to know upfront cost

### 17.2 High Priority Improvements

1. **Add compliance verification** for instruction-following constraints
2. **Implement formality detection** for bias analysis
3. **Complete TUI-engine integration**
4. **Batch checkpoint saves** to reduce I/O overhead
5. **Add multiple testing correction** for statistical analysis
6. **Verify OpenRouter model IDs** against actual API

### 17.3 Nice-to-Have Enhancements

1. **Bloom filter for completed_votes** to reduce memory
2. **Streaming progress updates** instead of polling
3. **Parallel Phase 1 generation** across models
4. **Model version locking** for reproducibility
5. **Web-based results viewer** alternative to TUI

---

## 18. Conclusion

The Master Plan Draft is comprehensive and well-structured, covering the vast majority of PROMPT.md requirements. The architecture is sound, with proper separation of concerns, async operations, and robustness features like checkpointing and circuit breakers.

However, several critical dependencies are undefined (ONET_WRITING_REFERENCE.md format, company/name data files), some PROMPT.md requirements are missing from judge evaluation criteria (authenticity, cliché avoidance), and the TUI implementation is incomplete.

The plan is roughly 85% complete for implementation. The remaining 15% consists of:
- Data file specifications and contents
- Missing judge criteria
- TUI-engine integration
- Compliance verification
- Complete bias detection implementation

With the recommended fixes, this plan can be successfully implemented to produce a production-quality evaluation framework.
