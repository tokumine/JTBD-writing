# PROMPT.md

This is the master prompt for the Gemini Writing Evaluation Framework project. The Date is Jan 6, 2026. 

---

## OBJECTIVE

Create a master plan for a high quality effective writing evaluation that compares (SxS) Gemini 3.0 Pro and 3.0 Flash with the latest competing models (GPT-5.2, Claude Opus, X, Kimi etc) in their class.

Use OpenRouter API and the latest O*NET database to produce this evaluation.

---

## DATA SOURCE: O*NET

Use the latest (30.1) O*NET database (US Department of Labor occupational data) to extract writing tasks across ALL jobs in the US economy. the ONET DB is available in db/onet.db as a sqlite3 database that you can access. OPUS has pre-processed all the tasks where effective writing might be needed and written a guide in db/ONET_WRITING_REFERENCE.md

### Granularity: Task-Level (Deepest)

Use **individual task statements** from O*NET (e.g., "Draft correspondence for executive review"). This is the most granular level, providing ~20,000+ individual tasks across ~1,000 occupations.

---

## MODELS TO EVALUATE

### Pro-Tier Comparisons (Gemini 3.0 Pro vs)
- GPT-5.2 Thinking
- Claude Opus 4.5
- Grok-4.1 Thinking
- Kimi K2 Thinking

### Flash-Tier Comparisons (Gemini 3.0 Flash vs)
- GPT-4.1
- Claude Sonnet
- Other flash-tier models in class

### Comparison Structure
- Always pairwise: Gemini vs one competitor at a time
- Class-matched: Compare Pro vs Pro-tier (GPT-5.2, Opus), Flash vs Flash-tier (GPT-4.1, Sonnet) separately
- Use OpenRouter API as unified interface to all models

---

## PROMPT GENERATION (CRITICAL - THE BIG CHALLENGE)

The big challenge is creating the right eval prompts for this task.

### Core Requirements

The eval itself should be made up of **highly realistic writing tasks that are required across every single job in the US economy** (proxy: O*NET) and an **evenly distributed range of industries for diversity within a single job type** (e.g., CEO of Coca Cola, CEO of 5 person Startup, CEO of charity).

### Diversity Requirements (CRITICAL)

The writing prompts must be as **DIVERSE** as possible and as **GENERATIVE** as possible, covering as wide a range as possible of:

- **User personas**: The full spectrum of who might be writing
- **Ages/skill levels**: From GenZ/GenA all the way through to Boomer
- **Formality/casualness**: From highly casual to extremely formal
- **End users/recipients**: The full spectrum of who might receive the writing
- **Urgency levels**: From routine/low-priority to time-sensitive/critical
- **Relationship context**: First contact vs ongoing relationship with recipient
- **Audience size**: One-on-one vs small group vs department-wide vs company-wide vs public
- **Emotional context**: Routine, crisis, celebration, conflict resolution, bad news delivery
- **Message position**: Initial outreach vs reply in thread vs follow-up

**The tasks in the economy can be highly diverse.**

**IMPORTANT: Avoid hardcoding specific categories and types of effective writing where possible.** Let the O*NET data drive this diversity programmatically rather than pre-defining categories.

### Industry Diversity: NAICS-Based Sampling

Use official **NAICS industry codes** for systematic industry coverage within each occupation. This ensures even distribution across sectors and reproducible industry assignment.

### Company Grounding: Real Companies (CRITICAL FOR REALISM)

**Try to use real, named companies instead of generic descriptions.** This grounds prompts in reality and enables more authentic evaluation. For smaller companies specify size so it's clearer what stage and level of bureaucracy and maturity they are at.

Instead of:
> "CEO of a fruit company"

Use:
> "CEO of Dole Food Company" or "CEO of Chiquita Brands"

**Implementation:**
- Use a real company names using your built in knowledge
- Sample across company sizes: Fortune 500, mid-market, small businesses, startups
- Include both well-known and lesser-known companies for diversity
- Store company metadata: size, age, public/private, HQ location

**Bias considerations:**
- Models may have uneven training data about different companies
- Document which companies were used so bias can be analyzed

### Realistic Names for People

**Use realistic names for writers and recipients** rather than generic titles:

Instead of:
> "Write to the VP of Marketing"

Use:
> "Write to Sarah Chen, VP of Marketing"

**Implementation:**
- Use names with demographic diversity (age, ethnicity, gender)
- Match names to persona characteristics plausibly
- Include realistic email addresses where appropriate (sarah.chen@acme.com)
- Vary name formality (Dr. Williams vs Mike vs Michael T. Williams)

### Temporal Context

**Include temporal grounding** where relevant to the task:

- Specify the current date/quarter when it affects the writing ("It's Q4 2024...")
- Include deadlines when urgency matters ("The board meeting is Friday...")
- Reference recent events for context when realistic ("Following last week's announcement...")

**Do NOT** include temporal context for tasks where it's irrelevant - let it emerge naturally from task requirements.

### Attachment & Reference Handling

Many real tasks reference external content. **Include mock attachments/references** where realistic:

- "See attached Q3 report" → provide summary of key figures
- "Per the email below" → include prior message content
- "Based on the meeting notes" → provide bullet points of what was discussed
- "Review the attached resume" → include candidate summary

This tests whether models appropriately reference and incorporate external context rather than ignoring it or hallucinating details.

### Competing Objectives

Real writing often involves **tension between competing goals**. Include prompts with inherent trade-offs:

- "Be brief but comprehensive"
- "Be direct but diplomatic"
- "Convey urgency without causing panic"
- "Give honest feedback while maintaining the relationship"
- "Explain technical details to a non-technical audience"

Track how models navigate these tensions - do they acknowledge the trade-off? Lean one way? Find creative balance?

### Regional English Variants

While US-centric, **include scenarios with international context**:

- British recipient (colour, organisation, different date formats)
- Australian context (mate, different idioms)
- International company with mixed audience
- Non-native English speaker as recipient (simpler vocabulary may be appropriate)

**Track as metadata:**
- `recipient_english_variant`: "en-US", "en-GB", "en-AU", "non-native"
- `writer_english_variant`: same options

Analyze whether models adapt appropriately to regional expectations.

### Reply-To Context

Some prompts should include **prior messages to respond to**:

- Angry customer email → write response
- Vague request from boss → write clarifying reply
- Technical question from colleague → write helpful answer
- Rejection to negotiate → write counter-proposal

This tests contextual understanding and appropriate response matching.

### Multiple Recipients (CC Situations)

Include scenarios with **multiple audiences simultaneously**:

- Email to client, CC'd to your boss
- Team announcement that external partners will also see
- Message to peer that will be forwarded to executives

Tests ability to navigate tone for mixed audiences.

### Tone Matching from Examples

Some prompts should include **prior writing samples to match**:

- "Here's how Sarah typically writes to clients: [example]. Draft a similar message for..."
- "Match the tone of our previous announcements: [example]"
- "Continue this email thread in a consistent voice"

Tests whether models can adapt to established communication patterns rather than defaulting to generic style.

### Revision & Editing Tasks

Include prompts where **the model must improve existing text**:

- "Revise this draft to be more concise: [draft]"
- "Make this email more professional: [casual draft]"
- "Soften the tone of this message: [harsh draft]"
- "Add more detail to this summary: [sparse draft]"

Tests editing ability, not just generation from scratch. Track these separately in analysis.

### Ambiguity Handling

Include some **deliberately vague prompts** to test how models handle uncertainty:

- Underspecified recipient: "Write to the team about the project"
- Missing context: "Follow up on our conversation"
- Unclear ask: "Put together something for the client"

**Track model behavior:**
- Does it make reasonable assumptions?
- Does it ask for clarification (in the response)?
- Does it hedge appropriately?
- Does it hallucinate specific details?

### Communication Channel

The **communication medium** affects expected tone, length, and format. Rather than hardcoding channels:

- Let O*NET task statements imply the medium naturally (e.g., "Draft email...", "Prepare memo...", "Write report...", "Social post on Twitter/X")
- Use Phase 3 LLM enrichment to infer/specify medium when the task is ambiguous
- Track channel as metadata for analysis (enables filtering results by medium)
- **Do NOT force tasks into predefined channel categories** - let realistic variety emerge

### Language Support

**v1: English-only** - Matches O*NET's US focus and simplifies judging.

**Future extensibility:** Include a `language` field in the prompt schema:
```json
{
  "prompt_id": "...",
  "language": "en",  // ISO 639-1 code
  "language_variant": "en-US",  // Optional regional variant
  ...
}
```

This allows future multilingual evaluation tracks without schema changes.

### Prompt Complexity

Some writing prompts will require additional context, others will be simple prompts. The system must handle both:
- **Simple prompts**: Straightforward writing tasks that need minimal context
- **Context-rich prompts**: Complex scenarios requiring detailed background information, recipient details, constraints, etc.

### Generation Methodology (Three-Phase Approach)

1. **Phase 1 - Offline LLM Generation**: Use an LLM to generate diverse persona/context variations for each O*NET task. This is done as an offline preprocessing step. **Use the same models being evaluated** for this generation (note: this creates potential bias but ensures prompts aren't accidentally biased against any particular model).

2. **Phase 2 - Algorithmic Combinations**: Programmatically combine O*NET tasks with randomized persona/industry/formality dimensions using NAICS codes. This ensures deterministic reproducibility.

3. **Phase 3 - LLM Enrichment**: Further enrich with LLM where context-heavy prompts require additional detail or realism.

### Response Constraints: Natural (No Constraints)

Let models decide appropriate length and format for each task. Do not enforce word counts or format requirements. This is more realistic and allows models to demonstrate judgment about appropriate response length/format.

---

## USER CONFIGURATION & COST CONTROL

The evaluation system must provide **fine-grained user control** over all variables that impact cost and runtime, with **live cost and time estimates** before execution.

### Configurable Parameters

Users must be able to configure ALL of the following:

#### Model Configuration
- **Models to evaluate**: Select which models to include (can run subset of default list)
- **Model pairs**: Choose specific pairwise comparisons to run
- **Model tiers**: Run only Pro-tier, only Flash-tier, or both

#### Judge Configuration
- **Judge models**: Select which judge models to use (1, 2, or all 3)
- **Votes per judge**: Adjust best-of-N (default 5, can reduce to 3 or 1)
- **Judge personas**: Use both personas, writing expert only, or recipient only

#### Prompt/Task Configuration
- **Number of prompts**: Total prompts to evaluate (10 to 10,000+)
- **Occupations**: Filter to specific O*NET occupation codes or categories
- **Industries**: Filter to specific NAICS codes or sectors
- **Job zones**: Filter by O*NET job zone (skill level 1-5)
- **Formality range**: Limit to specific formality levels
- **Age/generation range**: Limit to specific persona age groups

#### Sampling Configuration
- **Random seed**: For reproducible sampling
- **Stratification**: Ensure even distribution across dimensions or allow natural distribution
- **Occupation limit**: Max prompts per occupation
- **Industry limit**: Max prompts per industry

### Live Cost & Time Estimates

Before any eval run begins, the system MUST display:

```
╭─────────────────────────────────────────────────────────────╮
│                    EVAL RUN ESTIMATE                        │
├─────────────────────────────────────────────────────────────┤
│ Prompts:              500                                   │
│ Model pairs:          4 (Gemini Pro vs GPT-5.2, Opus, ...)  │
│ Total comparisons:    2,000                                 │
│                                                             │
│ Judge config:         3 judges × 5 votes × 2 personas       │
│ Total judge calls:    60,000                                │
│                                                             │
│ ESTIMATED COST                                              │
│   Response generation:  $180 - $220                         │
│   Judging:              $450 - $550                         │
│   Total:                $630 - $770                         │
│                                                             │
│ ESTIMATED TIME                                              │
│   With rate limits:     4-6 hours                           │
│   Parallelized:         1-2 hours                           │
╰─────────────────────────────────────────────────────────────╯

Proceed? [y/N]
```

Cost estimates should use current OpenRouter pricing and account for:
- Input/output token counts (estimated from task complexity)
- Per-model pricing differences
- Judge model pricing

### Prepackaged Eval Presets

Provide **10 preset configurations** for common use cases, from minimal to comprehensive:

| Level | Name | Prompts | Models | Judges | Est. Cost | Est. Time | Use Case |
|-------|------|---------|--------|--------|-----------|-----------|----------|
| **1** | Sanity Check | 5 | 1 pair | 1×1 vote | ~$1 | ~2 min | Does the system work? |
| **2** | Smoke Test | 20 | 1 pair | 1×3 votes | ~$5 | ~5 min | Quick functionality test |
| **3** | Dev Iteration | 50 | 2 pairs | 2×3 votes | ~$25 | ~15 min | Development/debugging |
| **4** | Quick Sample | 100 | 2 pairs | 2×5 votes | ~$75 | ~30 min | Fast directional signal |
| **5** | Light Eval | 200 | 3 pairs | 3×3 votes | ~$150 | ~1 hr | Light but meaningful eval |
| **6** | Standard Eval | 500 | 4 pairs | 3×5 votes | ~$500 | ~3 hrs | Standard evaluation run |
| **7** | Thorough Eval | 1,000 | 4 pairs | 3×5 votes | ~$1,000 | ~6 hrs | Thorough with good power |
| **8** | Comprehensive | 2,000 | All pairs | 3×5 votes | ~$2,500 | ~12 hrs | High statistical power |
| **9** | Deep Dive | 5,000 | All pairs | 3×5 votes | ~$6,000 | ~24 hrs | Publication-grade |
| **10** | Full Kaboodle | 10,000+ | All pairs | 3×5 votes | ~$12,000+ | ~48 hrs | Maximum coverage |

Users can start with a preset and customize from there.

### Configuration Interface

```bash
# Use preset
./eval --preset 3

# Customize preset
./eval --preset 6 --models "gemini-pro,gpt-5.2" --prompts 300

# Full custom
./eval --prompts 500 --occupations "11-*,13-*" --industries "54,62" \
       --judges "claude-opus,gpt-5.2" --votes 3

# Show estimate without running
./eval --preset 7 --dry-run
```

---

## LIVE PROGRESS VISUALIZATION

During evaluation runs, display a **highly detailed real-time progress visualization** using rich/textual TUI:

### Progress Dashboard Layout

```
╭────────────────────────────────────────────────────────────────────────────╮
│  GEMINI WRITING EVAL - Running [Preset 6: Standard Eval]                   │
│  Started: 2024-01-15 14:30:00 | Elapsed: 1h 23m 45s | ETA: 1h 36m 15s      │
╰────────────────────────────────────────────────────────────────────────────╯

┌─ OVERALL PROGRESS ─────────────────────────────────────────────────────────┐
│ ████████████████████░░░░░░░░░░░░░░░░░░░░  247/500 prompts (49.4%)         │
│                                                                            │
│ Phase: JUDGING  [Generation ✓] [Judging ◐] [Analysis ○]                   │
└────────────────────────────────────────────────────────────────────────────┘

┌─ MODEL PAIRS ──────────────────────────────────────────────────────────────┐
│ Gemini Pro vs GPT-5.2      ████████████████████░░░░  125/125 ✓  [51% win] │
│ Gemini Pro vs Claude Opus  ████████████░░░░░░░░░░░░   78/125    [48% win] │
│ Gemini Pro vs Grok-4.1     ████████░░░░░░░░░░░░░░░░   44/125    [53% win] │
│ Gemini Pro vs Kimi K2      ░░░░░░░░░░░░░░░░░░░░░░░░    0/125    [--]      │
└────────────────────────────────────────────────────────────────────────────┘

┌─ CURRENT BATCH ────────────────────────────────────────────────────────────┐
│ Prompt #248: "Draft quarterly performance review for junior analyst"       │
│ Occupation: Human Resources Manager (11-3121)                              │
│ Industry: Professional Services (NAICS 54)                                 │
│                                                                            │
│ ┌─ Responses ───────────┐  ┌─ Judging ─────────────────────────────────┐  │
│ │ Gemini Pro    ✓ 2.3s  │  │ Claude Opus:  ●●●●○  (4/5) Gemini wins   │  │
│ │ Claude Opus   ✓ 3.1s  │  │ GPT-5.2:      ●●●○○  (3/5) Gemini wins   │  │
│ │                       │  │ Gemini Judge: ●●○○○  (2/5) waiting...    │  │
│ └───────────────────────┘  └───────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘

┌─ LIVE STATISTICS ──────────────────────────────────────────────────────────┐
│ Win Rates (Running)           │ Performance                                │
│ ─────────────────────────     │ ──────────────────────────────────         │
│ vs GPT-5.2:    51.2% ± 4.3%   │ Avg response time:  2.8s                   │
│ vs Opus:       48.1% ± 5.1%   │ Avg judge time:     1.2s                   │
│ vs Grok:       52.7% ± 7.2%   │ API calls/min:      45                     │
│                               │ Est. cost so far:   $234.50                │
│ Judge Agreement: 0.73 κ       │ Est. total cost:    $475.00                │
└────────────────────────────────────────────────────────────────────────────┘

┌─ RECENT ACTIVITY ──────────────────────────────────────────────────────────┐
│ 14:53:42  ✓  Prompt #247 complete: Gemini wins (3-0 judges)                │
│ 14:53:38  ✓  Prompt #246 complete: Tie (inconclusive)                      │
│ 14:53:31  ⚠  Prompt #245 GPT-5.2 timeout, retrying (1/3)...               │
│ 14:53:28  ✓  Prompt #245 retry successful                                  │
│ 14:53:22  ✓  Prompt #244 complete: Opponent wins (2-1 judges)              │
└────────────────────────────────────────────────────────────────────────────┘

┌─ ERRORS & WARNINGS ────────────────────────────────────────────────────────┐
│ ⚠ 3 retries (all recovered)  │  ✗ 0 failures  │  ⏱ 2 rate limit pauses   │
└────────────────────────────────────────────────────────────────────────────┘

[Press 'q' to quit safely | 'p' to pause | 'd' for detailed view | 'h' for help]
```

### Required Progress Elements

1. **Overall Progress**
   - Total prompts completed / total
   - Progress bar with percentage
   - Current phase indicator (Generation → Judging → Analysis)
   - Elapsed time and ETA

2. **Per-Model-Pair Progress**
   - Individual progress bars for each comparison
   - Running win rate with confidence interval
   - Completion status

3. **Current Batch Details**
   - Current prompt being evaluated
   - Occupation and industry context
   - Response generation status per model
   - Judging progress (votes completed per judge)

4. **Live Statistics**
   - Running win rates with confidence intervals
   - Inter-judge agreement (Cohen's Kappa)
   - Performance metrics (response times, API throughput)
   - Cost tracking (spent so far, projected total)

5. **Activity Log**
   - Scrolling log of recent completions
   - Highlights wins, losses, ties
   - Shows retries and recoveries

6. **Error Summary**
   - Count of retries, failures, rate limits
   - Quick health indicator

### Interactive Controls

- **q**: Graceful quit (saves checkpoint)
- **p**: Pause evaluation
- **d**: Toggle detailed view (show full prompts/responses)
- **s**: Show full statistics panel
- **h**: Help overlay
- **↑↓**: Scroll activity log

---

## RESUMABILITY & ROBUSTNESS

### Interruption Handling

The evaluation MUST be **fully resumable** if interrupted for any reason:

- **Graceful shutdown**: Ctrl+C saves state and can resume
- **Crash recovery**: Can resume from last checkpoint after unexpected termination
- **Partial results**: All completed comparisons are preserved

### API Failure Robustness

The system MUST handle API failures gracefully:

- **Automatic retries**: Exponential backoff with jitter (3 retries default)
- **Rate limit handling**: Automatic slowdown when hitting rate limits
- **Timeout handling**: Configurable timeouts with retry
- **Partial failure**: Continue evaluation even if some calls fail
- **Failure logging**: Track all failures with full context for debugging
- **Failure report**: Summary of failures at end of run

### Checkpoint System

```
results/
└── eval_2024-01-15_14-30-00/
    ├── config.json              # Full configuration for this run
    ├── checkpoint.json          # Current progress state
    ├── prompts.json             # All prompts for this run (frozen)
    ├── responses/               # Model responses (written as completed)
    │   ├── prompt_001_gemini-pro.json
    │   ├── prompt_001_gpt-5.2.json
    │   └── ...
    ├── judgments/               # Judge results (written as completed)
    │   ├── prompt_001_comparison.json
    │   └── ...
    ├── results.db               # SQLite with all results
    └── failures.log             # Log of any failures
```

Resume command:
```bash
./eval --resume results/eval_2024-01-15_14-30-00/
```

---

## RESULTS ORGANIZATION

### Timestamped Run Directories

Each evaluation run creates a **separate timestamped directory**:

```
results/
├── eval_2024-01-15_14-30-00/    # First run
├── eval_2024-01-16_09-15-22/    # Second run
├── eval_2024-01-16_11-45-33/    # Third run (maybe different config)
└── latest -> eval_2024-01-16_11-45-33/  # Symlink to latest
```

### Run Directory Contents

Each run directory is **self-contained** with everything needed to understand and reproduce:

```
eval_YYYY-MM-DD_HH-MM-SS/
├── config.json                  # Complete configuration
├── config_summary.txt           # Human-readable config summary
├── checkpoint.json              # Resume state
├── random_seed.txt              # Seed for reproducibility
│
├── prompts/
│   ├── prompts.json             # All generated prompts
│   ├── prompts_by_occupation/   # Prompts organized by occupation
│   └── prompts_by_industry/     # Prompts organized by industry
│
├── responses/
│   ├── by_prompt/               # Responses organized by prompt ID
│   └── by_model/                # Responses organized by model
│
├── judgments/
│   ├── raw/                     # Raw judgment responses
│   └── aggregated/              # Aggregated results per comparison
│
├── results.db                   # SQLite database with all data
├── results_summary.csv          # Quick CSV export of key metrics
│
├── analysis/
│   ├── win_rates.json           # Computed win rates
│   ├── confidence_intervals.json
│   ├── statistical_tests.json
│   └── weakness_analysis.json
│
├── reports/
│   ├── report.pdf               # Final PDF report
│   ├── executive_summary.md
│   └── charts/                  # Generated visualizations
│
├── logs/
│   ├── run.log                  # Full execution log
│   ├── failures.log             # API failures
│   └── timing.log               # Performance metrics
│
└── README.md                    # Auto-generated run description
```

### Cross-Run Comparison

Support comparing results across multiple runs:

```bash
./eval compare results/eval_2024-01-15_*/ results/eval_2024-01-16_*/
```

---

## EVALUATION METHODOLOGY

### Side-by-Side (SxS) Comparison Structure

The SxS itself should compare a range of salient criteria for high quality writing.

- Always pairwise comparisons (Gemini vs X)
- Best-of-5 judgments per comparison
- Shuffle response ordering to eliminate position bias (deterministic, reproducible shuffling)

### Dual Judge Personas

Responses should be judged by **both**:

1. **Simulated Writing Expert**: Judges quality of craft, appropriate length and tone, clarity, structure, professionalism, and other qualities from the perspective of a writing professional

2. **Simulated Target Recipient/Reader**: Judges effectiveness, relevance, actionability, appropriateness from the perspective of whoever the writing is intended for in that specific task

### Multiple Judge Models (Ensemble)

Use three different LLMs as judges to cross-validate and increase robustness:
- Claude Opus 4.5
- GPT-5.2
- Gemini 3 Pro

### Voting Logic: Majority of Majorities

Each judge model gives **best-of-5** votes independently. Then take the **majority across the 3 judges**. This is the most robust aggregation method:
1. Claude Opus 4.5 gives 5 judgments → majority winner
2. GPT-5.2 gives 5 judgments → majority winner
3. Gemini 3 Pro gives 5 judgments → majority winner
4. Final winner = majority of the 3 judge winners

### Evaluation Criteria

Robust evaluation rubric covering:
- Quality of writing
- Appropriate length
- Tone appropriateness
- Effectiveness
- Clarity
- Task completion
- **Authenticity / "Human-like" quality**: Does the writing seem "AI generated" or does it read as realistic, natural writing that the target writer persona would actually produce? Would the target consumer/recipient perceive it as authentic human communication vs the target writer and consumer?
- **Cliché/boilerplate avoidance**: Does the response avoid obvious AI patterns? ("I hope this email finds you well", "Please don't hesitate to reach out", "I'm happy to help", excessive bullet points)
- **Length appropriateness**: Is the response the RIGHT length for this specific task, not just "good writing"?
- Other salient criteria for high quality effective writing

### Instruction-Following Tests

**Include some prompts with explicit constraints** to test instruction-following:

- Length constraints: "Keep this under 100 words" or "This should be comprehensive, at least 500 words"
- Format requirements: "Use exactly 3 bullet points" or "Write in paragraph form only"
- Tone directives: "Be direct and avoid pleasantries" or "Use a warm, encouraging tone"
- Exclusions: "Do not mention the budget" or "Avoid technical jargon"

Track compliance separately - a model that writes beautifully but ignores instructions is problematic for real use.

### Judge Context Requirements (CRITICAL)

**Judges need the context of the scenario to evaluate properly.** They must have all the information they need about the specific setup of each evaluation.

For each comparison, judges must receive:
- The full writing prompt/task description
- The writer persona details (age, skill level, role, industry, generation)
- The target recipient/consumer persona
- The formality level and communication context
- Any additional scenario-specific context that was provided to the models

This ensures judges can accurately assess whether the writing is appropriate, authentic, and effective **for the specific scenario** - not just generically "good writing."

### Sensitive Topic Handling

Real workplace writing often involves sensitive situations. **Track and analyze these separately:**

**Categories to flag:**
- HR issues (performance problems, terminations, complaints)
- Legal matters (contracts, liability, compliance)
- Bad news delivery (layoffs, project cancellations, rejections)
- Confidential information (financial results, M&A, personnel)
- Conflict situations (disputes, negotiations, complaints)

**Implementation:**
- Tag prompts involving sensitive topics during generation
- Track win rates separately for sensitive vs routine tasks
- Analyze whether models handle difficult communications appropriately
- Note: Some models may refuse sensitive tasks - track this pattern

### Handling Failures: Auto-Loss

If a model refuses to respond, goes off-topic, or produces an error, it **automatically loses that comparison**. This incentivizes models that can handle the full range of realistic writing tasks.

### Refusal Categorization

Beyond auto-loss, **categorize WHY models refuse** for deeper analysis. eg:

- **Safety refusal**: Model cites safety/policy concerns
- **Capability limitation**: Model says it can't do the task
- **Misunderstanding**: Model interprets task incorrectly
- **Incomplete response**: Model starts but doesn't finish
- **Off-topic**: Model responds but not to the actual task

Track refusal rates by:
- Model (which models refuse most?)
- Task type (which tasks trigger refusals?)
- Sensitive topic category (which sensitive areas are problematic?)

This data helps identify both model limitations and potentially problematic prompt patterns.

### Response Metadata Tracking

Track metadata for every response to enable deeper analysis:
- **Response length** (characters, words, tokens)
- **Response time** (latency)
- **Format detection** (used bullet points, headers, paragraphs, etc.)
- **Greeting/sign-off patterns** (formal vs casual markers)

This enables analysis of systematic patterns:
- Does Model X consistently over-write or under-write?
- Does Model Y default to bullet points regardless of context?
- Are there length biases correlated with win/loss rates?

### Systematic Bias Detection

The analysis phase MUST detect and report on systematic biases:

**Model biases:**
- Length bias: Does one model consistently write longer/shorter?
- Format bias: Does one model overuse certain structures?
- Formality drift: Does one model skew formal/casual regardless of prompt?

**Judge biases:**
- Position bias: Do judges prefer Response A vs B systematically?
- Length bias: Do judges prefer longer/shorter responses?
- Model fingerprinting: Can judges identify which model wrote which response?

**Report all detected biases** with statistical significance in the final analysis.

---

## GOAL

The goal is to produce a **repeatable eval** that:

1. Has **aggregate win rates per model pair (Gemini vs X)** for every real world effective writing task
2. Allows **meaningful inspection of judgements on a per writing task basis**
3. Is **highly trustworthy for researchers working on a frontier lab**
4. Identifies **specific areas of weakness** in Gemini effective writing vs its peers

### Focus Areas for Weakness Identification
- **All dimensions equally**: Comprehensive weakness analysis across all evaluation criteria
- **Task-specific competence**: Which specific job types or writing tasks does Gemini struggle with?

---

## INFRASTRUCTURE REQUIREMENTS

### Environment
- Assume a terminal environment
- Use SQLite for all results storage
- Allow exports to CSV
- **Python + modern tooling**: Use asyncio, httpx, pydantic, rich, plotly, and other modern libraries for better developer experience

### Fine-Grained Eval Viewer: Rich TUI

Build a **full interactive terminal UI** using the rich/textual library with:
- Filtering by occupation, industry, winner, etc.
- Sorting by various dimensions
- Side-by-side response viewing
- Drill-down into individual judgments

This allows meaningful inspection of judgements on a per writing task basis.

### Aggregate Statistics & Visualizations

- Win rates per model pair for every real-world writing task
- Charts and graphs for analysis
- Heatmaps by dimension/occupation
- Confidence intervals on all win rates

### Reproducibility: Focus on Statistical Power

Prioritize running **more evaluations with variation** to capture true model capabilities rather than strict deterministic reproduction. Save all random seeds and configs so runs CAN be reproduced when needed, but the primary goal is statistical power.

### Final PDF Analyst Report

Generate a final lead evaluation analyst report as a PDF that digs into the data behind the aggregate win/loss rates and identifies specific areas of weakness in Gemini effective writing vs its peers.

The report should include **all three**:

1. **Comprehensive Dashboard**: Win rates by occupation, by writing type, by formality level, by age group, heatmaps, confidence intervals - everything

2. **Deep Statistical Analysis**: Statistical rigor with significance tests, effect sizes, inter-rater reliability, detailed breakdowns

3. **Executive Summary**: High-level findings, top weaknesses, actionable recommendations, key charts

### Checkpoint/Resume

See **RESUMABILITY & ROBUSTNESS** section above for detailed checkpoint/resume requirements.

### Baselines

No human-written baselines needed. This is a **pure model-vs-model comparison**.

---

## ROBUSTNESS REQUIREMENTS

The eval and AI judges must be correct and robust. Creating the robust, reliable eval framework and judgement methodology is critical to make such an eval highly trustworthy for researchers working on a frontier lab.

Required robustness measures:
- Always pairwise comparisons
- Best-of-5 judgments with majority-of-majorities aggregation
- Shuffle ordering (deterministic for reproducibility)
- Robust eval rubric
- Position bias detection and mitigation
- Inter-judge agreement metrics (Cohen's Kappa or similar)
- Statistical significance testing
- Win rates with confidence intervals

---

## USER-PROVIDED INPUTS

The user will provide an OpenRouter API key.

---

## PLANNING METHODOLOGY

> ⚠️ **CRITICAL WARNING** ⚠️
>
> **SUB-AGENTS MUST NEVER RETURN CONTENT TO THE ORCHESTRATOR.**
>
> - Sub-agents write ALL work to files
> - Sub-agents return ONLY: `Done. Output: [filepath]`
> - Orchestrator NEVER reads output files (except Stage 6)
> - Violation of this will blow up the orchestrator's context
>
> **SUB-AGENTS MUST WRITE IN CHUNKS OF ~4000 TOKENS MAX.**
>
> - Use Write tool, then Edit tool to append
> - NEVER write >4000 tokens between tool calls
> - Hitting output token limit = lost work

---

### ROLE IDENTIFICATION (READ THIS FIRST)

**How to know if you are the ORCHESTRATOR vs a SUB-AGENT:**

- **You are the ORCHESTRATOR if:** You were invoked directly by the user (e.g., user said "execute CLAUDE.md" or similar). You have access to the Task tool to spawn sub-agents.

- **You are a SUB-AGENT if:** Your prompt includes specific instructions like "Write to plans/draft_plan_1.md" or references a specific stage task. You were spawned by another agent. Your job is to do the work and write to files.

---

### IF YOU ARE THE ORCHESTRATOR

Your job is to:
1. Launch sub-agents for each stage using the Task tool
2. Wait for them to complete (they write to files)
3. Pass file paths to the next stage's sub-agents
4. **NEVER read sub-agent output files yourself - you don't need to see them**
5. **NEVER consume sub-agent return messages beyond confirming completion**

**Your context is precious and limited.** Sub-agents have their own 200k token contexts. You only need ~1k tokens per stage to orchestrate. If your context grows beyond ~20k tokens during execution, something is wrong.

**When launching sub-agents, include these instructions in EVERY prompt:**
```
CRITICAL SUB-AGENT INSTRUCTIONS:
- You are a SUB-AGENT, not the orchestrator
- Write ALL output to the specified file using Write/Edit tools
- Write in chunks of ~4000 tokens maximum, saving after each chunk
- Your final response must be ONLY: "Done. Output: [filepath]"
- Do NOT return any content, summaries, or explanations
- The orchestrator cannot see your work - it only sees your final message
```

---

### IF YOU ARE A SUB-AGENT

Your job is to:
1. Do the work described in your prompt
2. Write ALL output to the specified file(s)
3. Write in chunks (~4000 tokens max), saving after each chunk
4. Return ONLY: `Done. Output: [filepath]` when complete
5. **NEVER return content, summaries, or explanations to the orchestrator**

---

### Why This Approach

It's very important that Claude Code is **token efficient and maximally intelligent** during its planning. To achieve this, we lean on Claude Code's ability to spawn **Opus 4.5 sub-agents that have totally separate context windows** and the ability to write to files.

### Core Principles

1. **All work other than orchestration will happen in sub-agents**, which use the filesystem and storage to persist and pass plans, reports, and other state between agents at each stage.

2. **CRITICAL: Sub-agents return ONLY file paths, never content.** When a sub-agent completes, its final message must be exactly: `Done. Output: plans/[filename].md` - nothing else. No summaries, no explanations, no content excerpts.

3. **Orchestrator never reads sub-agent output files.** The orchestrator passes file paths to the next stage. It does NOT use the Read tool on output files. Sub-agents in later stages read the files they need.

4. **Persisted files are stored in `plans/`**. The user will handle git commits manually.

5. **Parallelism generates multiple versions of identical work**, allowing exploration of the solution space. Each prompt to a parallel sub-agent group should be identical.

6. **The orchestrator trusts the process.** It doesn't need to see outputs - only confirm files exist and pass paths forward.

7. **MANDATORY: Chunked writing every ~4000 tokens.** Sub-agents MUST:
   - Write first ~4000 tokens using Write tool
   - STOP writing in your response after the tool call
   - After Write completes, continue with next chunk using Edit (append)
   - Repeat until complete
   - **NEVER exceed ~4000 tokens between file writes**
   - Pattern example:
     ```
     [Write tool: first 4000 tokens to file]
     [Edit tool: append next 4000 tokens]
     [Edit tool: append next 4000 tokens]
     [Final message: "Done. Output: plans/file.md"]
     ```
     
8. **VERIFY URLS**: If the eval requires download of any information or files from the internet, discover and verify they exist using search and browse tools rather than guessing or remembering the URL from parametric knowledge. 

### Stage 1: Initial Parallel Drafting

Launch 6 parallel OPUS sub-agents with identical prompts. Each sub-agent:
- Reads PROMPT.md for full context
- Creates a detailed implementation plan (use a general purpose agent configured in the same way as a plan agent)
- Writes to assigned file: `plans/draft_plan_N.md` (where N is 1-6)
- Returns ONLY: `Done. Output: plans/draft_plan_N.md`

**Orchestrator action:** Launch 6 Task agents in parallel.

### Stage 2: Parallel Critique & Rewrite

Launch 6 parallel OPUS sub-agents. Each sub-agent:
- Reads PROMPT.md AND their assigned draft (`plans/draft_plan_N.md`)
- Critiques for correctness, robustness, errors, missed details, poor decisions, completeness vs PROMPT.md
- Writes detailed critique and improved version to: `plans/critique_N.md`
- Returns ONLY: `Done. Output: plans/critique_N.md`
- The plan must contain 100% of the specification in PROMPT.md

**Orchestrator action:** Launch 6 Task agents in parallel.

### Stage 3: Master Plan Synthesis

Launch 1 OPUS sub-agent:
- Reads PROMPT.md AND all 6 draft plans AND their respective critique files
- Synthesizes a master plan considering draft plans, agreements, disagreements, risks, open questions
- The plan must contain 100% of the specification in PROMPT.md
- Writes to: `plans/master_plan_draft.md`
- Returns ONLY: `Done. Output: plans/master_plan_draft.md`

**Orchestrator action:** Launch 1 Task agent.

### Stage 4: Parallel Implementation Simulation

Launch 6 parallel OPUS sub-agents with identical prompts. Each sub-agent:
- Reads PROMPT.md AND `plans/master_plan_draft.md`
- Simulates implementing the entire master plan in detail (dry run)
- Documents what works, what doesn't, missing pieces, gotchas
- Writes to: `plans/simulation_N.md`
- Returns ONLY: `Done. Output: plans/simulation_N.md`

**Orchestrator action:** Launch 6 Task agents in parallel.

### Stage 5: Final Master Plan Improvement

Launch 1 OPUS sub-agent:
- Reads PROMPT.md, `plans/master_plan_draft.md`, AND all 6 simulation files
- Produces the final improved and COMPLETE master plan, ensuring that the plan contains 100% of the specification in PROMPT.md
- Writes to: `plans/master_plan_final.md`
- Returns ONLY: `Done. Output: plans/master_plan_final.md`

**Orchestrator action:** Launch 1 Task agent.

### Stage 6: Delivery

The orchestrator reads `plans/master_plan_final.md` and shares it with the user.
This is the ONLY time the orchestrator reads an output file.
