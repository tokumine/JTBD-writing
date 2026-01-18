# Simulation Report 1: Master Plan Implementation Dry Run

## Overview

This document simulates implementing the entire master plan as a detailed dry run. I walk through each component as if building it, documenting what works well, what does not work or is unclear, missing pieces, gotchas, edge cases, and inconsistencies with PROMPT.md requirements.

---

## 1. Foundation Layer Simulation

### 1.1 O*NET Data Extraction

**Simulating**: Reading from `db/onet.db` and `db/ONET_WRITING_REFERENCE.md`

**What Works Well**:
- The plan correctly identifies that O*NET 30.1 is the data source
- Using pre-processed `ONET_WRITING_REFERENCE.md` aligns with PROMPT.md's guidance
- Task-level granularity (~20,000+ tasks) provides excellent diversity

**Issues Found**:
1. **Missing ONetExtractor Implementation**: The plan mentions `ONetExtractor` and `ONET_WRITING_REFERENCE.md` integration but never shows the actual SQL queries or parsing logic. How exactly do we extract writing-relevant tasks?

2. **ONET_WRITING_REFERENCE.md Format Unknown**: The plan assumes this file exists and contains useful data but doesn't verify its structure. Critical question: What columns/fields does this reference contain?

3. **Task-to-Writing Relevance Mapping**: PROMPT.md says Opus "pre-processed all the tasks where effective writing might be needed." But the plan doesn't show how to query this or what the filtering criteria were.

4. **Job Zone Access**: The plan uses `task.job_zone` but O*NET stores job zones at the occupation level, not task level. Need to join `task_statements` with `job_zones` table.

**Simulation Steps**:
```
1. Open db/onet.db connection
2. Read ONET_WRITING_REFERENCE.md
3. Parse reference to get task_ids flagged as writing-relevant
4. Query task_statements table for those task_ids
5. Join with occupation_data for job_zone
6. Return List[ONetTask]
```

**Gotcha**: The plan shows `ONetTask.job_zone` as a direct field, but this requires a JOIN that isn't shown anywhere.

### 1.2 Database Schema Implementation

**Simulating**: Creating the SQLite database with aiosqlite

**What Works Well**:
- Schema is comprehensive with all necessary tables
- Proper foreign key relationships defined
- Useful indexes for common query patterns
- Uses aiosqlite for true async operations

**Issues Found**:
1. **No Migration Strategy**: If schema needs changes during development, how do we handle existing data?

2. **Missing Tables**:
   - No `runs` table to track multiple evaluation runs
   - No `models` table to store model metadata/pricing
   - No `occupations` table for O*NET occupation metadata

3. **sensitive_topics Storage**: Stored as comma-separated string `",".join(t.value for t in prompt.sensitive_topics)` - should use a proper junction table for relational queries

4. **communication_channel Index Missing**: This is a key analysis dimension but has no index

5. **Constraint Compliance Not Linked**: `compliance_checks` table exists but there's no mechanism to link specific constraints from the prompt schema to compliance results

**Edge Case**: What if the same prompt_id is generated twice (hash collision in `hashlib.md5`)? The 16-character hex ID has collision probability. Should use UUID4 instead.

### 1.3 OpenRouter API Client

**Simulating**: Building the async HTTP client with httpx

**What Works Well**:
- Plan specifies httpx for async HTTP (correct modern choice)
- Per-model rate limiting architecture
- Circuit breaker pattern for resilience
- Exponential backoff with jitter

**Issues Found**:
1. **Missing OpenRouter Client Code**: The plan references `OpenRouterClient` extensively but never provides its implementation. Critical missing piece.

2. **Rate Limiter Implementation Missing**: Plan mentions per-model rate limiting but doesn't show the implementation. Need semaphores or token bucket algorithm.

3. **Model ID Verification**: The plan uses model IDs like `google/gemini-3.0-pro-preview` but doesn't verify these are valid OpenRouter model strings. OpenRouter model IDs may differ.

4. **Authentication Not Shown**: How is the API key passed? Headers? Environment variable loading?

5. **Response Parsing Not Defined**: OpenRouter has a specific response format. Need to parse `choices[0].message.content`, handle `finish_reason`, extract token counts.

**Critical Missing Code**:
```python
# This is NOT in the plan but is essential:
class OpenRouterClient:
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    async def complete(self, model: str, messages: list, **kwargs):
        # Missing implementation
        pass
```

### 1.4 Configuration and Presets

**Simulating**: Loading preset configurations

**What Works Well**:
- 10 presets from Sanity Check to Full Kaboodle (matches PROMPT.md table)
- EvalConfig pydantic model is comprehensive
- Cost estimator mentioned

**Issues Found**:
1. **PRESETS Dictionary Not Defined**: Plan shows `config = PRESETS[preset]` but never defines the actual PRESETS dictionary mapping integers to EvalConfig objects.

2. **Cost Estimator Logic Missing**: `estimate_cost()` function is called but implementation not provided. How do we estimate:
   - Input tokens per prompt (varies by prompt complexity)
   - Output tokens per response (varies by model behavior)
   - Per-model pricing (needs OpenRouter pricing data)

3. **Model Pairs Hardcoded**: The default model pairs in EvalConfig may not match available OpenRouter models. Need runtime validation.

4. **API Key Handling**: `openrouter_api_key: Optional[str] = None` but no mechanism to load from environment or .env file shown.

---

## 2. Prompt Generation Pipeline Simulation

### 2.1 Phase 1: Offline LLM Generation

**Simulating**: Pre-generating persona variations using all evaluated models

**What Works Well**:
- Uses ALL evaluated models to avoid single-model bias (matches PROMPT.md)
- Caches results to JSON files per task
- Comprehensive PersonaVariation dataclass
- Generation prompt captures key diversity dimensions

**Issues Found**:
1. **Scale Problem**: With ~20,000+ tasks and 6 models generating 5 variations each = 600,000+ API calls for Phase 1 alone. At ~$0.01/call = $6,000 just for preprocessing. This is never mentioned in cost estimates.

2. **No Incremental Generation**: If Phase 1 fails partway through, we restart from the beginning for each task without per-variation checkpointing.

3. **JSON Parsing Fragility**: The `_parse_variations` method has basic JSON extraction:
   ```python
   if '```json' in content:
       content = content.split('```json')[1].split('```')[0]
   ```
   This fails if model outputs JSON without markdown fencing or uses different formatting.

4. **No Validation**: PersonaVariation fields aren't validated. What if LLM outputs:
   - Invalid `writer_generation` like "Young Adult" instead of expected values?
   - Empty strings for required fields?
   - Wrong data types?

5. **Deduplication Not Handled**: If the same model generates similar personas for similar tasks, we may get low actual diversity.

6. **Temperature 0.9 Everywhere**: May produce inconsistent quality. Should validate outputs.

**PROMPT.md Compliance Check**:
- PROMPT.md says "Use the same models being evaluated" for Phase 1 - COMPLIANT
- PROMPT.md mentions tracking "which model generated each variation for bias analysis" - COMPLIANT (stored in `generated_by_model`)

### 2.2 Phase 2: Algorithmic Combination

**Simulating**: Deterministically combining O*NET tasks with variations

**What Works Well**:
- Seeded random for reproducibility
- Stratification by job zone and SOC group
- Uses pre-generated variations from Phase 1
- Fallback to algorithmic generation if no variations

**Issues Found**:
1. **Company Database Missing**: `CompanyDatabase.get_by_name()` and `sample_for_occupation()` are called but the company database isn't provided. Plan mentions "500+ real companies" but no data file shown.

2. **NAICS Mapper Not Defined**: `NAICSMapper.get_for_occupation()` is used but implementation missing. How do we map O*NET SOC codes to NAICS industry codes?

3. **Name Generator Missing**: `NameGenerator` is referenced for "Census-based diverse names" but not implemented. Where is the names data?

4. **Stratification Logic Issue**:
   ```python
   per_zone = num_prompts // 5
   ```
   If `num_prompts = 100`, we get 20 per zone. But what if job zone 1 has only 10 tasks? We'd undersample. Need to handle uneven distribution.

5. **Generation to Age Mapping Missing**:
   ```python
   age=self._generation_to_age(variation.writer_generation)
   ```
   Method `_generation_to_age` is called but never defined. Need to map gen_z/millennial/gen_x/boomer to age ranges.

6. **Relationship Normalization Missing**: `_normalize_relationship()` method called but not defined.

7. **`full_prompt` Left Empty**:
   ```python
   return WritingPrompt(
       ...
       full_prompt=""  # Will be built in Phase 3
   )
   ```
   This means Phase 2 output is incomplete and cannot be used without Phase 3.

**PROMPT.md Compliance Check**:
- PROMPT.md requires NAICS-based industry sampling - PARTIALLY COMPLIANT (mapper mentioned but not implemented)
- PROMPT.md requires "real, named companies" - INCOMPLETE (database mentioned but not provided)

### 2.3 Phase 3: LLM Enrichment

**Simulating**: Adding context-heavy enrichments via LLM

**What Works Well**:
- Enriches only 30% of prompts (configurable)
- Parallel batch processing
- Multiple enrichment types: prior messages, attachments, competing objectives, tone examples, temporal context
- Uses evaluated models to avoid bias

**Issues Found**:
1. **Random State Not Seeded**:
   ```python
   import random
   if random.random() < 0.15:  # 15% chance of tone matching
   ```
   This uses global random state, not the seeded `self.rng`. Breaks reproducibility.

2. **Enrichment Selection Non-Deterministic**: The indices_to_enrich set is created with `random.sample()` using global random, not seeded.

3. **Error Handling Silent**:
   ```python
   results = await asyncio.gather(*enrichments, return_exceptions=True)
   for result in results:
       if isinstance(result, dict):  # Silently ignores exceptions
   ```
   Failed enrichments are silently dropped. Should log these.

4. **Attachment Type Mismatch**:
   ```python
   if prompt.communication_channel in ['report', 'memo', 'presentation']:
   ```
   But `communication_channel` is a dynamic string inferred by LLM, not guaranteed to match these exact values.

5. **`MessagePosition` Enum Access**:
   ```python
   if prompt.message_position.value in ['reply_in_thread', 'follow_up']:
   ```
   Checking `.value` is correct, but the enum values are `INITIAL`, `REPLY`, `FOLLOWUP` (capitalized), not `reply_in_thread`. Schema mismatch.

6. **Temporal Context Hardcoded Date**:
   ```python
   base_date = datetime(2026, 1, 6)  # Per PROMPT.md
   ```
   Good that it matches PROMPT.md's Jan 6, 2026 date. But what about prompts run on different dates?

7. **CC Context Not Generated**: The `_add_cc_context` enrichment isn't called in `_enrich_single_prompt`. CC scenarios won't be added during enrichment.

**PROMPT.md Compliance Check**:
- Prior message context for replies - COMPLIANT
- Mock attachments - COMPLIANT
- Competing objectives - COMPLIANT
- Tone matching examples - COMPLIANT
- Temporal grounding - COMPLIANT
- Multiple recipients/CC - NOT COMPLIANT (not called in enrichment)

### 2.4 Special Prompt Type Generators

**Simulating**: Constraint, revision, ambiguity, CC generators

**What Works Well**:
- Instruction-following constraints cover length, format, tone, exclusions
- Revision tasks have template drafts for different types
- Ambiguity generator handles three types correctly
- CC scenario generator covers key multi-audience situations

**Issues Found**:
1. **Constraint Validation Gap**: Constraints like `"max_words:100"` are stored but no compliance checker is shown that parses and validates these against responses.

2. **Revision Draft Placeholders**:
   ```python
   original_draft = template.format(
       recipient=prompt.recipients[0].name.split()[0],
       topic=prompt.onet_task[:50]
   )
   ```
   If `onet_task` contains format specifiers like `{`, this will crash.

3. **Ambiguity Destroys Context**:
   ```python
   prompt.onet_task = f"Write something regarding {prompt.onet_task.split()[0]} matters"
   ```
   This destroys the original task. Should preserve original in a separate field for analysis.

4. **CC Generator Not Integrated**: The `CCScenarioGenerator` class exists but is never called in the prompt generation pipeline.

5. **Probabilities Not Exclusive**: A prompt could be both ambiguous AND have constraints AND be a revision task simultaneously. Need to define mutual exclusivity rules.

---

## 3. Evaluation Engine Simulation

### 3.1 Judge Prompt Building

**Simulating**: Creating evaluation prompts for dual judge personas

**What Works Well**:
- Full scenario context included (matches PROMPT.md requirement)
- Both Writing Expert and Recipient personas defined
- Clear evaluation criteria with WINNER, CONFIDENCE, QUALITY scores
- Position bias warning included

**Issues Found**:
1. **Rubric Missing Key Criteria**: PROMPT.md specifies:
   - "Authenticity / 'Human-like' quality"
   - "Cliche/boilerplate avoidance"
   - "Length appropriateness"

   These are mentioned in PROMPT.md but not in the judge prompt template.

2. **Response Format Fragility**: Judge output expected as:
   ```
   WINNER: [A/B/TIE]
   CONFIDENCE: [1-5]
   ...
   ```
   But LLMs often add preamble or vary format. Need robust parsing.

3. **Token Length Concern**: The judge prompt includes full scenario context + both responses. For long responses (500+ words each), this could exceed context limits for some judge models.

4. **Instruction Compliance Not Judged**: If the prompt had explicit constraints, judges should evaluate compliance. This isn't in the judge prompt.

5. **Missing Refusal Detection**: If a response is a refusal, the judge prompt doesn't instruct how to handle it. Should the judge score it 0? Mark as auto-loss?

### 3.2 Vote Aggregation

**Simulating**: Majority-of-majorities aggregation

**What Works Well**:
- Position assignment is deterministic via hash
- Winner normalization from position (A/B) to model (gemini/competitor)
- Majority-of-majorities logic correctly implemented
- Agreement calculation included

**Issues Found**:
1. **Judge Grouping By Persona Too**:
   ```python
   key = (vote.judge_model, vote.judge_persona)
   ```
   This means each judge+persona combo is treated as separate "judge." With 3 judges x 2 personas = 6 judge groups, taking majority requires 4/6 agreement. Is this intended? PROMPT.md says "majority across the 3 judges" - not 6.

2. **Tie Breaking Logic Ambiguous**:
   ```python
   if gemini_count > len(judge_majorities) / 2:
       final = "gemini"
   ```
   With 6 judge groups, need 4 to win (majority of 6). But PROMPT.md says "majority of the 3 judge winners" - implying only 3 judges, needing 2/3.

3. **Vote ID Generation Missing**: `vote_id` is used for checkpointing but how it's generated isn't shown.

4. **Quality Scores Not Used**: `quality_gemini` and `quality_competitor` are captured but never used in aggregation. Could be valuable for tie-breaking.

**PROMPT.md Compliance Issue**: The plan aggregates across judge+persona pairs (6 groups), but PROMPT.md describes aggregating across 3 judge models. Need clarification.

### 3.3 Response Metadata Tracking

**Simulating**: Extracting metadata from model responses

**What Works Well**:
- Plan mentions tracking length, time, format detection, greeting/signoff patterns

**Issues Found**:
1. **Format Detection Not Implemented**: No code shown to detect:
   - Bullet points (`has_bullets`)
   - Headers (`has_headers`)
   - Greeting type
   - Signoff type

2. **Formality Detection Missing**: Bias detection mentions `detected_formality` but no classifier exists.

3. **Response Analyzer Referenced But Missing**: `response_analyzer.py` is in project structure but no implementation shown.

---

## 4. Storage and Checkpointing Simulation

### 4.1 Run Directory Structure

**Simulating**: Creating timestamped run directories

**What Works Well**:
- Complete directory structure matches PROMPT.md specification
- Atomic writes via temp file + rename
- Latest symlink for convenience
- Config saved in both JSON and human-readable formats

**Issues Found**:
1. **Symlink Platform Issue**:
   ```python
   latest_link.symlink_to(self.run_dir.name)
   ```
   On Windows, symlinks require admin privileges. Need fallback or warning.

2. **organize_prompts_by_occupation Has Bug**:
   ```python
   for p in prompts:
       occ = p.occupation_code  # This is a string like "11-1011.00"
   ```
   Then saved to file named `{occ}.json`. Filename with dots and hyphens may cause issues on some filesystems.

3. **README Auto-Generation Missing**: `readme_md` path property exists but no implementation to generate README content.

4. **Charts Directory Empty**: `reports/charts/` created but no code shows saving charts there.

### 4.2 Checkpoint System

**Simulating**: Fine-grained checkpointing with crash recovery

**What Works Well**:
- Per-vote granularity (finest level)
- Partial comparison state tracked
- Circuit breaker state persisted
- Async-safe with lock

**Issues Found**:
1. **Checkpoint Save Frequency**: `await self.save()` is called after every vote. With 5 votes x 6 judge groups x many prompts = many file writes. Could be slow.

2. **Race Condition Risk**:
   ```python
   async with self._lock:
       # ... write file
   ```
   If multiple save() calls queue up, they'll serialize correctly, but the intermediate states are lost.

3. **Checkpoint File Corruption**: If crash during atomic write (between temp file write and rename), we lose checkpoint. Should keep backup.

4. **Partial Comparison Loading Not Shown**: `get_partial_comparison()` returns data but how does the engine use it to resume mid-comparison?

---

## 5. Analysis Layer Simulation

### 5.1 Statistical Analysis

**Simulating**: Win rate analysis with confidence intervals

**What Works Well**:
- Wilson score interval (correct for proportions)
- Uses `scipy.stats.binomtest` (not deprecated `binom_test`)
- Cohen's Kappa for inter-rater reliability
- Cohen's h effect size

**Issues Found**:
1. **Ties Handling Inconsistent**:
   ```python
   decisive = wins + losses  # Exclude ties for statistical tests
   ```
   But then:
   ```python
   win_rate = wins / total  # Includes ties in denominator
   ```
   This is inconsistent. Should win rate exclude ties or not?

2. **Cohens Kappa Implementation Assumes Two Raters**: The implementation takes `rater1` and `rater2` lists, but we have 3 (or 6) judges. Need multi-rater agreement metric (Fleiss' Kappa).

3. **Multiple Testing Correction Missing**: Running many statistical tests (per occupation, per industry, per formality, etc.) inflates false positive rate. Need Bonferroni or FDR correction.

### 5.2 Bias Detection

**Simulating**: Detecting systematic biases

**What Works Well**:
- Position bias detection with binomial test
- Length bias detection
- Model fingerprinting detection via chi-square
- Formality drift detection

**Issues Found**:
1. **Vote Data Structure Assumptions**:
   ```python
   for v in votes:
       judge = (v["judge_model"], v["judge_persona"])
   ```
   This assumes votes are dicts with specific keys, but the plan uses `JudgeVote` dataclass elsewhere. Inconsistent.

2. **Formality Drift Requires Detection**:
   ```python
   response_formality = r["detected_formality"]  # 1-5
   ```
   But no formality detector is implemented anywhere.

3. **Length Bias Calculation Issue**:
   ```python
   if c["final_winner"] == "gemini":
       if gemini_len > comp_len:
           longer_wins += 1
   ```
   This counts when winner was longer, but doesn't control for actual quality. Correlation doesn't imply bias.

4. **Model Fingerprinting Test Validity**: The chi-square test checks if Gemini win rate differs by position. But this could also indicate real quality differences, not fingerprinting. Need better test.

---

## 6. TUI Implementation Simulation

### 6.1 Progress Dashboard

**Simulating**: Real-time progress display with Textual

**What Works Well**:
- Layout matches PROMPT.md specification closely
- Reactive state updates
- Key bindings for pause/quit/detail view
- Activity log with timestamps

**Issues Found**:
1. **Integration With Engine Missing**:
   ```python
   if no_tui:
       asyncio.run(run_eval())
   else:
       dashboard = ProgressDashboard()
       # Would integrate engine with dashboard
       dashboard.run()
   ```
   Comment says "would integrate" but no integration code shown. How does engine push updates to dashboard?

2. **Dashboard Blocking**: Textual's `app.run()` is blocking. Running async evaluation alongside requires careful threading/async coordination not shown.

3. **Model Stats Table Not Populated**:
   ```python
   table.add_columns("Model", "Wins", "Losses", "Ties", "Win%")
   ```
   Columns added but no code to add rows with actual data.

4. **ETA Calculation Issue**:
   ```python
   rate = self.completed_comparisons / elapsed
   remaining = self.total_comparisons - self.completed_comparisons
   eta_seconds = remaining / rate
   ```
   If rate varies (e.g., due to rate limits), this linear projection will be inaccurate.

### 6.2 Results Viewer

**Simulating**: Interactive results exploration TUI

**What Works Well**:
- Filter bar with occupation, winner, job zone filters
- Search input
- Side-by-side response comparison panel
- Key bindings for navigation

**Issues Found**:
1. **`_get_occupations` Returns Static**:
   ```python
   def _get_occupations(self):
       return ["All"]  # Would load from database
   ```
   Placeholder implementation.

2. **`_load_comparisons` Not Implemented**:
   ```python
   async def _load_comparisons(self):
       pass
   ```
   Empty implementation.

3. **Judgment Detail Screen Missing**:
   ```python
   async def action_view_judgments(self):
       # Would push JudgmentDetailScreen
       pass
   ```
   Screen doesn't exist.

---

## 7. PDF Report Generation Simulation

**Simulating**: Generating final analyst report

**What Works Well**:
- Plan mentions reportlab/weasyprint options
- Specifies three sections: Dashboard, Statistical Analysis, Executive Summary

**Issues Found**:
1. **No PDF Generator Implementation**: The `pdf_generator.py` file is in the project structure but no code is shown.

2. **Chart Generation Missing**: Charts are mentioned but `charts.py` and `heatmaps.py` have no implementation.

3. **Weakness Analysis Output Missing**: `weakness_analysis.json` path exists but no `WeaknessFinder` implementation shown.

4. **Report Content Spec Vague**: What specific charts? What statistical tables? What format for weakness analysis?

---

## 8. Critical Missing Pieces Summary

### 8.1 Completely Missing Implementations

1. **OpenRouterClient** - Essential for all API calls
2. **Rate limiter** - Per-model rate limiting logic
3. **Company database** (companies.json)
4. **Name generator** (names_census.json)
5. **NAICS mapper**
6. **ONet extractor** SQL queries
7. **Response analyzer** (format detection)
8. **Formality detector**
9. **Compliance checker** (instruction following)
10. **PDF report generator**
11. **Chart generators**
12. **PRESETS dictionary**
13. **Cost estimator logic**
14. **Engine-TUI integration**

### 8.2 Incomplete Implementations

1. **Phase 2 combiner** - Missing helper methods (`_generation_to_age`, etc.)
2. **Phase 3 enricher** - Reproducibility issues with random state
3. **Results viewer TUI** - Mostly placeholder code
4. **Database queries** - `get_win_rates_by_dimension` exists but other queries missing

### 8.3 PROMPT.md Compliance Gaps

| Requirement | Status | Issue |
|-------------|--------|-------|
| CC/Multiple recipients | Partial | Generator exists but not integrated into pipeline |
| Judge rubric criteria | Partial | Missing authenticity, cliche avoidance, length appropriateness |
| Majority-of-majorities | Unclear | Implementation uses 6 groups (judge+persona) vs 3 judges |
| Instruction compliance tracking | Missing | No compliance checker implementation |
| Regional English variants | Partial | Schema supports it but no generation logic |
| Sensitive topic flagging | Partial | Schema has field but no tagging logic in generators |

---

## 9. Recommended Fixes Before Implementation

### 9.1 High Priority

1. **Clarify aggregation**: Does "3 judges" mean 3 judge models (ignoring persona split) or 6 judge groups (3 models x 2 personas)?

2. **Implement OpenRouterClient**: This blocks everything else.

3. **Fix random state seeding**: Phase 3 uses global random breaking reproducibility.

4. **Add compliance checker**: Critical for instruction-following test tracking.

5. **Implement missing data files**: companies.json, names_census.json.

### 9.2 Medium Priority

1. **Add judge rubric criteria**: Authenticity, cliche avoidance.

2. **Integrate CC generator**: Currently orphaned.

3. **Fix MessagePosition enum values**: Schema uses different case than code checks.

4. **Add Fleiss' Kappa**: For multi-rater agreement (more than 2 raters).

5. **Implement TUI-engine integration**: Currently disconnected.

### 9.3 Low Priority

1. **Add symlink fallback for Windows**.

2. **Improve ETA calculation** with rolling average.

3. **Add checkpoint backup** to prevent corruption.

4. **Implement README auto-generation**.

---

## 10. Edge Cases and Gotchas

### 10.1 API Edge Cases

1. **Model unavailable**: OpenRouter might not have all specified models. Need fallback.

2. **Rate limit 429 response**: Need to parse `Retry-After` header.

3. **Context length exceeded**: Long prompts + long responses + judge context could exceed model limits.

4. **Empty response**: Model returns empty string. How to handle?

5. **Streaming responses**: OpenRouter supports streaming. Plan doesn't use it. Consider for progress updates.

### 10.2 Data Edge Cases

1. **O*NET task with special characters**: Unicode, quotes, newlines in task text.

2. **Company name conflicts**: What if two companies have similar names?

3. **Name collisions**: Generated names might collide across prompts.

4. **Hash collisions**: MD5 16-char hex has collision probability at scale.

### 10.3 Evaluation Edge Cases

1. **Both responses are refusals**: Who wins?

2. **Judge refuses to judge**: Safety refusal on sensitive content.

3. **Tie in majority-of-majorities**: What if 1 gemini, 1 competitor, 1 tie across judges?

4. **Judge outputs malformed response**: Parsing fails.

5. **Extreme latency difference**: One model takes 30s, other takes 2s. Does this affect judging?

### 10.4 Statistical Edge Cases

1. **Zero comparisons for a dimension**: Division by zero in win rate calculation.

2. **All ties**: What's the win rate?

3. **Very small sample sizes**: Wilson CI breaks down with n < 5.

---

## 11. Conclusion

The master plan provides a comprehensive architecture and addresses most PROMPT.md requirements. However, significant implementation gaps remain, particularly around:

1. **Core infrastructure** (API client, data files)
2. **Pipeline integration** (generators not connected)
3. **TUI functionality** (placeholder implementations)
4. **Reporting** (no actual report generation)

The plan's code examples are valuable but incomplete. A production implementation would require filling in approximately 40% more code than what's provided. The statistical methodology is sound, though some edge cases need attention.

**Overall Assessment**: Good architectural blueprint, needs significant implementation work. Recommend addressing high-priority gaps before proceeding.
