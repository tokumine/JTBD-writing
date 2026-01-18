# Gap Analysis: PROMPT.md vs master_plan_final.md

This document provides a comprehensive gap analysis comparing every requirement in PROMPT.md against the master_plan_final.md implementation plan.

---

## 1. DATA SOURCE: O*NET

### O*NET Database (30.1)
- **Requirement**: Use the latest (30.1) O*NET database from US Department of Labor
- **Status**: ✅ COVERED
- **Evidence**: Section 3 specifies version "30.1" in the ONET_WRITING_REFERENCE.md schema

### Task-Level Granularity (~20,000+ tasks across ~1,000 occupations)
- **Requirement**: Use individual task statements, the most granular level
- **Status**: ✅ COVERED
- **Evidence**: Section 3 shows task_id, task_statement, and occupation-level data structure

### ONET_WRITING_REFERENCE.md Access
- **Requirement**: Use the pre-processed guide at db/ONET_WRITING_REFERENCE.md
- **Status**: ✅ COVERED
- **Evidence**: Section 3 includes complete ONetExtractor implementation that reads this file

---

## 2. MODELS TO EVALUATE

### Pro-Tier Comparisons
| Model | Status | Notes |
|-------|--------|-------|
| Gemini 3.0 Pro | ✅ COVERED | google/gemini-3.0-pro in PRO_PAIRS |
| GPT-5.2 Thinking | ✅ COVERED | openai/gpt-5.2 in PRO_PAIRS |
| Claude Opus 4.5 | ✅ COVERED | anthropic/claude-opus-4.5 in PRO_PAIRS |
| Grok-4.1 Thinking | ✅ COVERED | x-ai/grok-4.1 in PRO_PAIRS |
| Kimi K2 Thinking | ✅ COVERED | moonshot/kimi-k2 in PRO_PAIRS |

### Flash-Tier Comparisons
| Model | Status | Notes |
|-------|--------|-------|
| Gemini 3.0 Flash | ✅ COVERED | google/gemini-3.0-flash in FLASH_PAIRS |
| GPT-4.1 | ✅ COVERED | openai/gpt-4.1 in FLASH_PAIRS |
| Claude Sonnet | ✅ COVERED | anthropic/claude-sonnet-4 in FLASH_PAIRS |
| Other flash-tier models | ⚠️ PARTIAL | Only GPT-4.1 and Sonnet specified, "other flash-tier" not enumerated |

### Comparison Structure
- **Pairwise comparisons**: ✅ COVERED - Always Gemini vs one competitor
- **Class-matched**: ✅ COVERED - PRO_PAIRS and FLASH_PAIRS separated
- **OpenRouter API**: ✅ COVERED - Full OpenRouterClient implementation in Section 4

---

## 3. PROMPT GENERATION

### Core Requirements
- **Realistic writing tasks across every job in US economy**: ✅ COVERED - O*NET task extraction
- **NAICS-based industry diversity**: ✅ COVERED - naics_mapper.py and company_database.py

### Diversity Requirements (CRITICAL)

| Dimension | Status | Evidence |
|-----------|--------|----------|
| User personas | ✅ COVERED | WriterPersona schema with full details |
| Ages/skill levels | ✅ COVERED | age (18-80), generation, skill_level fields |
| Formality/casualness | ✅ COVERED | formality_level (1-5) |
| End users/recipients | ✅ COVERED | RecipientPersona with relationship types |
| Urgency levels | ✅ COVERED | urgency_level (1-5) |
| Relationship context | ✅ COVERED | RecipientPersona.relationship + prior_contact |
| Audience size | ✅ COVERED | audience_size enum (one_on_one to public) |
| Emotional context | ✅ COVERED | EmotionalContext enum |
| Message position | ✅ COVERED | MessagePosition enum |

### Avoiding Hardcoded Categories
- **Requirement**: Let O*NET data drive diversity programmatically
- **Status**: ✅ COVERED
- **Evidence**: Section 19.2 explicitly states channels, categories are NOT hardcoded

### Industry Diversity: NAICS-Based Sampling
- **Status**: ✅ COVERED
- **Evidence**: naics_mapper.py, company_database.py with SOC-to-NAICS mapping

### Company Grounding: Real Companies
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Real, named companies | ✅ COVERED | company_database.py with 500+ companies |
| Company size range (Fortune 500 to startups) | ✅ COVERED | size field with full range |
| Well-known and lesser-known companies | ✅ COVERED | "Inc. 5000" and Fortune 500 sources |
| Company metadata (size, age, public/private, HQ) | ✅ COVERED | Company dataclass has all fields |
| Bias documentation | ✅ COVERED | Stored in prompts for analysis |

### Realistic Names for People
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Realistic names for writers/recipients | ✅ COVERED | NameGenerator class |
| Demographic diversity | ✅ COVERED | Census-based data, ethnic names |
| Match names to persona plausibly | ✅ COVERED | generation parameter support |
| Realistic email addresses | ✅ COVERED | WriterPersona.email, RecipientPersona.email |
| Vary name formality | ⚠️ PARTIAL | Not explicitly shown (Dr. Williams vs Mike) |

**Gap**: Name formality variation (Dr., Mr., informal first name) not explicitly implemented.

### Temporal Context
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Current date/quarter when relevant | ✅ COVERED | temporal_context field |
| Deadlines when urgency matters | ✅ COVERED | temporal_context usage |
| Reference recent events when realistic | ✅ COVERED | temporal_context |
| NOT include when irrelevant | ✅ COVERED | Optional field |

### Attachment & Reference Handling
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Mock attachments/references | ✅ COVERED | Attachment model with type, description, content |
| Q3 report summaries | ✅ COVERED | Attachment.content |
| Prior email content | ✅ COVERED | prior_context + Attachment |
| Meeting notes | ✅ COVERED | Attachment.type |
| Resume summaries | ✅ COVERED | Attachment.type |

### Competing Objectives
- **Requirement**: Include prompts with tension between competing goals
- **Status**: ✅ COVERED
- **Evidence**: competing_objectives field in WritingPrompt schema

### Regional English Variants
| Requirement | Status | Evidence |
|-------------|--------|----------|
| British recipient | ✅ COVERED | EnglishVariant.EN_GB |
| Australian context | ✅ COVERED | EnglishVariant.EN_AU |
| Non-native English speaker | ✅ COVERED | EnglishVariant.NON_NATIVE |
| recipient_english_variant metadata | ✅ COVERED | recipient_english_variant field |
| writer_english_variant metadata | ✅ COVERED | writer.english_variant |

### Reply-To Context
- **Requirement**: Prior messages to respond to
- **Status**: ✅ COVERED
- **Evidence**: prior_context field, MessagePosition.REPLY

### Multiple Recipients (CC Situations)
- **Requirement**: Multiple audiences simultaneously
- **Status**: ✅ COVERED
- **Evidence**: CCContext model with cc_recipients, will_be_forwarded_to, mixed_audience_note

### Tone Matching from Examples
- **Requirement**: Prior writing samples to match
- **Status**: ✅ COVERED
- **Evidence**: ToneExample model with example_text, context, match_instruction

### Revision & Editing Tasks
- **Requirement**: Model must improve existing text
- **Status**: ✅ COVERED
- **Evidence**: RevisionTask model, is_revision_task flag, revision_generator.py

### Ambiguity Handling
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Deliberately vague prompts | ✅ COVERED | is_ambiguous, ambiguity_type fields |
| Underspecified recipient | ✅ COVERED | ambiguity_type includes this |
| Missing context | ✅ COVERED | ambiguity_type includes this |
| Unclear ask | ✅ COVERED | ambiguity_type includes this |
| Track model behavior | ⚠️ PARTIAL | Field exists but behavior tracking not explicit |

**Gap**: How the system tracks whether models "ask for clarification", "hedge appropriately", or "hallucinate details" is not explicitly defined.

### Communication Channel
- **Requirement**: Let medium emerge naturally, track as metadata, do NOT force categories
- **Status**: ✅ COVERED
- **Evidence**: communication_channel as Optional[str], Section 19.1 confirms NOT enum

### Language Support
| Requirement | Status | Evidence |
|-------------|--------|----------|
| v1 English-only | ✅ COVERED | language = "en" default |
| ISO 639-1 language field | ✅ COVERED | language field in schema |
| language_variant field | ✅ COVERED | language_variant = "en-US" |

### Prompt Complexity
- **Requirement**: Handle both simple and context-rich prompts
- **Status**: ✅ COVERED
- **Evidence**: Optional fields, Phase 3 enrichment for complex prompts

### Three-Phase Generation Methodology
| Phase | Status | Evidence |
|-------|--------|----------|
| Phase 1 - Offline LLM Generation | ✅ COVERED | phase1_offline.py |
| Phase 2 - Algorithmic Combinations | ✅ COVERED | phase2_algorithmic.py |
| Phase 3 - LLM Enrichment | ✅ COVERED | phase3_enrichment.py |
| Use same models being evaluated | ⚠️ PARTIAL | Mentioned but not explicitly implemented |

**Gap**: The requirement to "use the same models being evaluated" for Phase 1 generation is mentioned in PROMPT.md but implementation details are not specified.

### Response Constraints: Natural
- **Requirement**: No word counts or format requirements enforced
- **Status**: ✅ COVERED
- **Evidence**: No default constraints, constraints are optional

---

## 4. USER CONFIGURATION & COST CONTROL

### Configurable Parameters

#### Model Configuration
| Parameter | Status | Evidence |
|-----------|--------|----------|
| Models to evaluate | ✅ COVERED | --models CLI option |
| Model pairs | ✅ COVERED | EvalConfig.model_pairs |
| Model tiers | ⚠️ PARTIAL | PRO_PAIRS/FLASH_PAIRS exist but no --tier flag |

**Gap**: No explicit --pro-tier or --flash-tier CLI option.

#### Judge Configuration
| Parameter | Status | Evidence |
|-----------|--------|----------|
| Judge models (1, 2, or all 3) | ✅ COVERED | JudgeConfig.models, --judges CLI |
| Votes per judge (1, 3, or 5) | ✅ COVERED | JudgeConfig.votes_per_judge, --votes CLI |
| Judge personas (both, expert only, recipient only) | ⚠️ PARTIAL | use_both_personas exists but no CLI flag |

**Gap**: No CLI option to select expert-only or recipient-only persona.

#### Prompt/Task Configuration
| Parameter | Status | Evidence |
|-----------|--------|----------|
| Number of prompts | ✅ COVERED | --prompts CLI |
| Occupations filter | ✅ COVERED | --occupations CLI |
| Industries filter | ✅ COVERED | --industries CLI |
| Job zones filter | ⚠️ PARTIAL | Not in CLI, only in ONetExtractor |
| Formality range | ⚠️ PARTIAL | EvalConfig but no CLI |
| Age/generation range | ❌ MISSING | Not in CLI or config |

**Gaps**:
- No --job-zones CLI option
- No --formality-range CLI option
- No --age-range or --generation CLI option

#### Sampling Configuration
| Parameter | Status | Evidence |
|-----------|--------|----------|
| Random seed | ✅ COVERED | --seed CLI |
| Stratification | ✅ COVERED | stratify_by_job_zone, stratify_by_soc_group |
| Occupation limit | ❌ MISSING | Not shown |
| Industry limit | ❌ MISSING | Not shown |

**Gaps**:
- No --occupation-limit or --max-per-occupation CLI option
- No --industry-limit or --max-per-industry CLI option

### Live Cost & Time Estimates
- **Requirement**: Display detailed estimate before run
- **Status**: ✅ COVERED
- **Evidence**: format_cost_estimate function with exact layout from PROMPT.md

### 10 Prepackaged Eval Presets
| Level | Status | Evidence |
|-------|--------|----------|
| 1 - Sanity Check | ✅ COVERED | 5 prompts, 1 pair, 1x1 vote |
| 2 - Smoke Test | ✅ COVERED | 20 prompts, 1 pair, 1x3 votes |
| 3 - Dev Iteration | ✅ COVERED | 50 prompts, 2 pairs, 2x3 votes |
| 4 - Quick Sample | ✅ COVERED | 100 prompts, 2 pairs, 2x5 votes |
| 5 - Light Eval | ✅ COVERED | 200 prompts, 3 pairs, 3x3 votes |
| 6 - Standard Eval | ✅ COVERED | 500 prompts, 4 pairs, 3x5 votes |
| 7 - Thorough Eval | ✅ COVERED | 1000 prompts, 4 pairs, 3x5 votes |
| 8 - Comprehensive | ✅ COVERED | 2000 prompts, All pairs, 3x5 votes |
| 9 - Deep Dive | ✅ COVERED | 5000 prompts, All pairs, 3x5 votes |
| 10 - Full Kaboodle | ✅ COVERED | 10000+ prompts, All pairs, 3x5 votes |

### Configuration Interface
| Example | Status | Evidence |
|---------|--------|----------|
| ./eval --preset 3 | ✅ COVERED | --preset CLI |
| --models filter | ⚠️ PARTIAL | Exists but parsing not shown |
| --prompts override | ✅ COVERED | CLI implementation |
| --occupations filter | ✅ COVERED | CLI exists |
| --industries filter | ✅ COVERED | CLI exists |
| --judges filter | ✅ COVERED | CLI exists |
| --votes override | ✅ COVERED | CLI exists |
| --dry-run | ✅ COVERED | CLI implementation |

---

## 5. LIVE PROGRESS VISUALIZATION

### Progress Dashboard Layout
- **Status**: ✅ COVERED
- **Evidence**: Section 17 ProgressDashboard with all elements

### Required Progress Elements

| Element | Status | Evidence |
|---------|--------|----------|
| Overall Progress bar | ✅ COVERED | ProgressBar with percentage |
| Total prompts completed/total | ✅ COVERED | main-progress widget |
| Current phase indicator | ✅ COVERED | phase-label |
| Elapsed time and ETA | ⚠️ PARTIAL | Elapsed shown, ETA not explicitly calculated |
| Per-Model-Pair Progress bars | ✅ COVERED | ModelPairProgress widgets |
| Running win rate with confidence interval | ⚠️ PARTIAL | Win rate shown, CI not shown in TUI |
| Current prompt being evaluated | ✅ COVERED | CurrentBatchStatus |
| Occupation and industry context | ⚠️ PARTIAL | Not shown in CurrentBatchStatus |
| Response generation status per model | ✅ COVERED | response_a_status, response_b_status |
| Judging progress (votes per judge) | ⚠️ PARTIAL | judging_status exists but not per-judge votes |
| Running win rates with CI | ⚠️ PARTIAL | Win rate yes, CI not shown |
| Inter-judge agreement (Cohen's Kappa) | ❌ MISSING | Not in TUI |
| Performance metrics (response times, throughput) | ⚠️ PARTIAL | Not shown in TUI |
| Cost tracking (spent, projected) | ❌ MISSING | Not in TUI |
| Activity log (scrolling) | ✅ COVERED | Log widget |
| Error summary | ✅ COVERED | ErrorSummary widget |

**Gaps**:
- ETA calculation not shown
- Confidence intervals not displayed in TUI
- Occupation/industry context not in current batch display
- Per-judge vote count not displayed
- Cohen's Kappa not in TUI
- Response times/throughput not displayed
- Cost tracking (spent so far, projected) not in TUI

### Interactive Controls
| Control | Status | Evidence |
|---------|--------|----------|
| q - Graceful quit | ✅ COVERED | BINDINGS |
| p - Pause | ✅ COVERED | action_toggle_pause |
| d - Toggle detailed view | ⚠️ PARTIAL | BINDINGS exists, implementation unclear |
| s - Show statistics | ⚠️ PARTIAL | save_checkpoint instead |
| h - Help overlay | ❌ MISSING | Not in BINDINGS |
| Arrow keys - Scroll log | ⚠️ PARTIAL | Log widget default behavior |

**Gaps**:
- h for help not implemented
- s should show statistics panel, not save checkpoint

---

## 6. RESUMABILITY & ROBUSTNESS

### Interruption Handling
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Graceful shutdown (Ctrl+C) | ✅ COVERED | signal.SIGINT handler |
| Crash recovery | ✅ COVERED | load() method |
| Partial results preserved | ✅ COVERED | in_progress_comparisons |

### API Failure Robustness
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Automatic retries with exponential backoff | ✅ COVERED | max_retries, delay calculation |
| Rate limit handling | ✅ COVERED | RateLimiter class |
| Timeout handling | ✅ COVERED | httpx timeout, retry on TimeoutException |
| Partial failure - continue eval | ✅ COVERED | Circuit breaker allows continuation |
| Failure logging | ✅ COVERED | failures.log path |
| Failure report at end | ⚠️ PARTIAL | failures.log exists but summary generation not shown |

### Checkpoint System
| Element | Status | Evidence |
|---------|--------|----------|
| config.json | ✅ COVERED | config_json property |
| checkpoint.json | ✅ COVERED | checkpoint_json property |
| prompts.json | ✅ COVERED | prompts_json property |
| responses/ directory | ✅ COVERED | responses/by_prompt, responses/by_model |
| judgments/ directory | ✅ COVERED | judgments/raw, judgments/aggregated |
| results.db | ✅ COVERED | results_db property |
| failures.log | ✅ COVERED | failures_log property |
| Resume command | ✅ COVERED | --resume CLI option |

---

## 7. RESULTS ORGANIZATION

### Timestamped Run Directories
- **Status**: ✅ COVERED
- **Evidence**: RunDirectory with eval_YYYY-MM-DD_HH-MM-SS format

### Run Directory Contents
| Path | Status | Evidence |
|------|--------|----------|
| config.json | ✅ COVERED | config_json property |
| config_summary.txt | ✅ COVERED | config_summary_txt property |
| checkpoint.json | ✅ COVERED | checkpoint_json property |
| random_seed.txt | ✅ COVERED | random_seed_txt property |
| prompts/prompts.json | ✅ COVERED | prompts_json property |
| prompts/prompts_by_occupation/ | ✅ COVERED | organize_prompts_by_occupation |
| prompts/prompts_by_industry/ | ✅ COVERED | organize_prompts_by_industry |
| responses/by_prompt/ | ✅ COVERED | get_response_path |
| responses/by_model/ | ✅ COVERED | Directory created |
| judgments/raw/ | ✅ COVERED | get_judgment_path |
| judgments/aggregated/ | ✅ COVERED | get_aggregated_judgment_path |
| results.db | ✅ COVERED | results_db property |
| results_summary.csv | ✅ COVERED | results_csv property |
| analysis/*.json | ✅ COVERED | get_analysis_path |
| reports/report.pdf | ✅ COVERED | full_report_pdf property |
| reports/executive_summary.md | ✅ COVERED | executive_summary_md property |
| reports/charts/ | ✅ COVERED | get_chart_path |
| logs/run.log | ✅ COVERED | run_log property |
| logs/failures.log | ✅ COVERED | failures_log property |
| logs/timing.log | ✅ COVERED | timing_log property |
| README.md | ✅ COVERED | readme_md property |
| latest symlink | ✅ COVERED | create_latest_symlink method |

### Cross-Run Comparison
- **Requirement**: Support comparing results across multiple runs
- **Status**: ✅ COVERED
- **Evidence**: compare CLI command, cross_run_compare.py

---

## 8. EVALUATION METHODOLOGY

### Side-by-Side Comparison Structure
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Pairwise comparisons | ✅ COVERED | VoteAggregator design |
| Best-of-5 judgments | ✅ COVERED | votes_per_judge = 5 |
| Shuffle response ordering | ✅ COVERED | get_position_for_vote with deterministic hash |
| Reproducible shuffling | ✅ COVERED | Seed-based hash |

### Dual Judge Personas
| Persona | Status | Evidence |
|---------|--------|----------|
| Simulated Writing Expert | ✅ COVERED | WRITING_EXPERT_SYSTEM prompt |
| Simulated Target Recipient | ✅ COVERED | RECIPIENT_SYSTEM prompt |

### Multiple Judge Models (Ensemble)
| Judge | Status | Evidence |
|-------|--------|----------|
| Claude Opus 4.5 | ✅ COVERED | ALL_JUDGES |
| GPT-5.2 | ✅ COVERED | ALL_JUDGES |
| Gemini 3 Pro | ✅ COVERED | ALL_JUDGES |

### Voting Logic: Majority of Majorities
- **Status**: ✅ COVERED
- **Evidence**: Section 9 VoteAggregator with explicit clarification about judge MODEL vs persona

### Evaluation Criteria
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Quality of writing | ✅ COVERED | In judge prompt |
| Appropriate length | ✅ COVERED | In judge prompt |
| Tone appropriateness | ✅ COVERED | In judge prompt |
| Effectiveness | ✅ COVERED | In judge prompt |
| Clarity | ✅ COVERED | In judge prompt |
| Task completion | ✅ COVERED | In judge prompt |
| Authenticity/"Human-like" quality | ✅ COVERED | In judge prompt |
| Cliche/boilerplate avoidance | ✅ COVERED | In judge prompt with examples |
| Length appropriateness | ✅ COVERED | In judge prompt |

### Instruction-Following Tests
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Length constraints | ✅ COVERED | ConstraintSpec type="length" |
| Format requirements | ✅ COVERED | ConstraintSpec type="format" |
| Tone directives | ✅ COVERED | ConstraintSpec type="tone" |
| Exclusions | ✅ COVERED | ConstraintSpec type="exclusion" |
| Track compliance separately | ✅ COVERED | ComplianceTracker, compliance_tracker.py |

### Judge Context Requirements (CRITICAL)
| Context Element | Status | Evidence |
|-----------------|--------|----------|
| Full writing prompt/task | ✅ COVERED | onet_task in judge prompt |
| Writer persona details | ✅ COVERED | Writer Context section |
| Target recipient persona | ✅ COVERED | Recipient Context section |
| Formality level | ✅ COVERED | Communication Requirements |
| Additional scenario context | ✅ COVERED | All optional fields included |

### Sensitive Topic Handling
| Requirement | Status | Evidence |
|-------------|--------|----------|
| HR issues category | ✅ COVERED | SensitiveTopic.HR_ISSUES |
| Legal matters | ✅ COVERED | SensitiveTopic.LEGAL |
| Bad news delivery | ✅ COVERED | SensitiveTopic.BAD_NEWS |
| Confidential information | ✅ COVERED | SensitiveTopic.CONFIDENTIAL |
| Conflict situations | ✅ COVERED | SensitiveTopic.CONFLICT |
| Tag during generation | ✅ COVERED | sensitive_topics field |
| Track win rates separately | ⚠️ PARTIAL | Field exists but separate analysis not shown |
| Note refusal patterns | ✅ COVERED | refusal_classifier.py |

### Handling Failures: Auto-Loss
- **Status**: ✅ COVERED
- **Evidence**: Section 19.5 explicitly confirms auto-loss on timeout, refusal, empty response

### Refusal Categorization
| Category | Status | Evidence |
|----------|--------|----------|
| Safety refusal | ✅ COVERED | refusal_classifier.py mentioned |
| Capability limitation | ✅ COVERED | refusal_classifier.py mentioned |
| Misunderstanding | ✅ COVERED | refusal_classifier.py mentioned |
| Incomplete response | ✅ COVERED | refusal_classifier.py mentioned |
| Off-topic | ✅ COVERED | refusal_classifier.py mentioned |
| Track by model | ⚠️ PARTIAL | Implementation not shown |
| Track by task type | ⚠️ PARTIAL | Implementation not shown |
| Track by sensitive topic | ⚠️ PARTIAL | Implementation not shown |

**Gap**: Refusal tracking breakdowns (by model, by task type, by sensitive topic) implementation details not shown.

### Response Metadata Tracking
| Metadata | Status | Evidence |
|----------|--------|----------|
| Response length (chars, words, tokens) | ✅ COVERED | ResponseMetrics.word_count |
| Response time (latency) | ✅ COVERED | CompletionResponse.latency_ms |
| Format detection | ✅ COVERED | ResponseMetrics.has_bullets, has_headers |
| Greeting/sign-off patterns | ✅ COVERED | ResponseMetrics.greeting_type, signoff_type |

### Systematic Bias Detection
| Bias Type | Status | Evidence |
|-----------|--------|----------|
| Length bias (model) | ✅ COVERED | detect_length_bias |
| Format bias (model) | ✅ COVERED | detect_format_bias |
| Formality drift (model) | ✅ COVERED | detect_formality_drift |
| Position bias (judge) | ✅ COVERED | detect_position_bias |
| Length bias (judge) | ✅ COVERED | detect_length_bias checks winner correlation |
| Model fingerprinting (judge) | ✅ COVERED | detect_model_fingerprinting |
| Report with statistical significance | ✅ COVERED | BiasResult.p_value, effect_size |

---

## 9. GOAL: Repeatable Eval Requirements

| Goal | Status | Evidence |
|------|--------|----------|
| Aggregate win rates per model pair | ✅ COVERED | WeaknessReport.overall_win_rate |
| Meaningful inspection per task | ✅ COVERED | TUI results_viewer.py |
| Highly trustworthy for frontier lab researchers | ✅ COVERED | Multiple judges, bias detection, statistical tests |
| Identify specific areas of weakness | ✅ COVERED | WeaknessFinder with dimension analysis |

### Focus Areas for Weakness Identification
| Focus | Status | Evidence |
|-------|--------|----------|
| All dimensions equally | ✅ COVERED | WeaknessFinder analyzes all dimensions |
| Task-specific competence | ✅ COVERED | occupation_code, soc_major_group in dimensions |

---

## 10. INFRASTRUCTURE REQUIREMENTS

### Environment
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Terminal environment | ✅ COVERED | CLI-based |
| SQLite for storage | ✅ COVERED | aiosqlite, results.db |
| CSV exports | ✅ COVERED | export command, results_summary.csv |
| Python + modern tooling | ✅ COVERED | asyncio, httpx, pydantic, rich |

### Fine-Grained Eval Viewer: Rich TUI
| Feature | Status | Evidence |
|---------|--------|----------|
| Filtering by occupation | ⚠️ PARTIAL | results_viewer.py exists but filtering not shown |
| Filtering by industry | ⚠️ PARTIAL | Not shown |
| Filtering by winner | ⚠️ PARTIAL | Not shown |
| Sorting by dimensions | ⚠️ PARTIAL | Not shown |
| Side-by-side response viewing | ⚠️ PARTIAL | results_viewer.py exists |
| Drill-down into judgments | ⚠️ PARTIAL | Not shown |

**Gap**: TUI results viewer implementation details (filtering, sorting, drill-down) not shown.

### Aggregate Statistics & Visualizations
| Feature | Status | Evidence |
|---------|--------|----------|
| Win rates per model pair | ✅ COVERED | WeaknessReport |
| Charts and graphs | ✅ COVERED | charts.py, plotly |
| Heatmaps by dimension/occupation | ✅ COVERED | heatmaps.py |
| Confidence intervals on win rates | ✅ COVERED | Wilson CI in statistics.py |

### Reproducibility: Focus on Statistical Power
- **Status**: ✅ COVERED
- **Evidence**: Random seed saved, stratification options

### Final PDF Analyst Report
| Section | Status | Evidence |
|---------|--------|----------|
| Comprehensive Dashboard | ✅ COVERED | pdf_generator.py mentioned |
| Deep Statistical Analysis | ✅ COVERED | statistics.py, bias_detection.py |
| Executive Summary | ✅ COVERED | executive_summary.md |

### Checkpoint/Resume
- **Status**: ✅ COVERED
- **Evidence**: Section 13 CheckpointManager

### Baselines
- **Requirement**: No human-written baselines needed
- **Status**: ✅ COVERED
- **Evidence**: No baseline references in plan

---

## 11. ROBUSTNESS REQUIREMENTS

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Always pairwise comparisons | ✅ COVERED | Design |
| Best-of-5 with majority-of-majorities | ✅ COVERED | VoteAggregator |
| Shuffle ordering (deterministic) | ✅ COVERED | get_position_for_vote |
| Robust eval rubric | ✅ COVERED | Judge prompt |
| Position bias detection and mitigation | ✅ COVERED | detect_position_bias |
| Inter-judge agreement (Cohen's Kappa) | ⚠️ PARTIAL | Mentioned in PROMPT.md dashboard, not in implementation |
| Statistical significance testing | ✅ COVERED | binomtest, chi2_contingency |
| Win rates with confidence intervals | ✅ COVERED | Wilson CI |

**Gap**: Cohen's Kappa implementation not explicitly shown.

---

## 12. USER-PROVIDED INPUTS

- **Requirement**: OpenRouter API key
- **Status**: ✅ COVERED
- **Evidence**: .env.example mentions OPENROUTER_API_KEY

---

## SUMMARY OF GAPS

### ❌ MISSING (Critical)
1. **Inter-judge agreement metric (Cohen's Kappa)** - Referenced in PROMPT.md progress dashboard but not implemented
2. **Cost tracking in TUI** - "Est. cost so far" and "Est. total cost" not in progress dashboard
3. **Help overlay (h key)** - Not in TUI BINDINGS

### ⚠️ PARTIAL (Important)
1. **Name formality variation** - Dr. Williams vs Mike vs Michael T. Williams not explicitly handled
2. **Ambiguity behavior tracking** - How to track if model asks clarification, hedges, or hallucinates
3. **Phase 1 generation using evaluated models** - Requirement exists but implementation not specified
4. **Model tier CLI option** - No --pro-tier or --flash-tier flag
5. **Judge persona CLI option** - No --expert-only or --recipient-only flag
6. **Job zones CLI filter** - ONetExtractor supports but no CLI option
7. **Formality/age range CLI** - No CLI options
8. **Occupation/industry limits** - No max-per-occupation/industry options
9. **ETA calculation** - Not shown in TUI
10. **Confidence intervals in TUI** - Not displayed
11. **Occupation/industry in current batch display** - Not shown
12. **Per-judge vote count in TUI** - Not displayed
13. **Response times/throughput in TUI** - Not displayed
14. **Failure summary report at end of run** - failures.log exists but summary generation not shown
15. **Refusal tracking by dimension** - Fields exist but breakdown analysis not shown
16. **TUI results viewer details** - Filtering, sorting, drill-down implementation not shown
17. **Other flash-tier models** - Only GPT-4.1 and Sonnet specified

### ✅ FULLY COVERED
- O*NET data source and task-level granularity
- All Pro-tier models
- Core Flash-tier models
- All diversity requirements (personas, ages, formality, etc.)
- Company grounding with real companies
- Temporal context
- Attachments and references
- Regional English variants
- CC situations
- Tone matching
- Revision tasks
- Communication channels (not hardcoded)
- Language support with extensibility
- Three-phase generation methodology
- All 10 presets
- Live cost estimates
- Core CLI interface
- Interruption handling and crash recovery
- Checkpoint system
- Results organization structure
- Cross-run comparison
- Dual judge personas
- Judge ensemble
- Majority-of-majorities voting
- All evaluation criteria
- Instruction-following tests
- Judge context requirements
- Sensitive topic handling
- Auto-loss on failure
- Refusal categorization
- Response metadata tracking
- All bias detection types
- Weakness identification
- PDF report generation
- Statistical analysis

---

## RECOMMENDATIONS

### High Priority
1. Implement Cohen's Kappa calculation and display in TUI
2. Add cost tracking (spent/projected) to progress dashboard
3. Add ETA calculation to progress dashboard

### Medium Priority
4. Add --tier, --persona CLI options
5. Add --job-zones, --formality-range, --age-range CLI options
6. Add --occupation-limit, --industry-limit CLI options
7. Implement name formality variation in NameGenerator
8. Document Phase 1 generation model selection strategy

### Lower Priority
9. Add help overlay (h key) to TUI
10. Add occupation/industry context to current batch display
11. Add per-judge vote counts to TUI
12. Add response times/throughput metrics to TUI
13. Implement failure summary report generation
14. Document TUI results viewer filtering/sorting
