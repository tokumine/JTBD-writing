# PROMPT.md

This is the master prompt for the Gemini Writing Evaluation Framework project.

---

## OBJECTIVE

Create a master plan for a high quality effective writing evaluation that compares (SxS) Gemini 3.0 Pro and 3.0 Flash with the latest competing models (GPT-5.2, Claude Opus, X, Kimi etc) in their class.

Use OpenRouter API and the latest O*NET database to produce this evaluation.

---

## DATA SOURCE: O*NET

Use the latest O*NET database (US Department of Labor occupational data) to extract writing tasks across ALL jobs in the US economy.

### Granularity: Task-Level (Deepest)

Use **individual task statements** from O*NET (e.g., "Draft correspondence for executive review"). This is the most granular level, providing ~20,000+ individual tasks across ~1,000 occupations.

Generate or provide download scripts for O*NET data and any other eval context needed.

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

The eval itself should be made up of **highly realistic writing tasks that are required across every single job in the US economy** (proxy: O*NET) and an **evenly distributed range of industries for diversity within a single job type** (e.g., CEO of fruit company, CEO of startup, CEO of charity).

### Diversity Requirements (CRITICAL)

The writing prompts must be as **DIVERSE** as possible and as **GENERATIVE** as possible, covering as wide a range as possible of:

- **User personas**: The full spectrum of who might be writing
- **Ages/skill levels**: From GenZ/GenA all the way through to Boomer
- **Formality/casualness**: From highly casual to extremely formal
- **End users/recipients**: The full spectrum of who might receive the writing

**The tasks in the economy can be highly diverse.**

**IMPORTANT: Avoid hardcoding specific categories and types of effective writing where possible.** Let the O*NET data drive this diversity programmatically rather than pre-defining categories.

### Industry Diversity: NAICS-Based Sampling

Use official **NAICS industry codes** for systematic industry coverage within each occupation. This ensures even distribution across sectors and reproducible industry assignment.

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

### Scale & Flexibility

- **Full evaluation**: 1000+ prompts for comprehensive coverage and high statistical power (~$1000-2000 API cost)
- **Quick sampled runs**: Ability to run faster iterations on random samples
- **Micro-targeted tests**: Support for focused evaluations on specific O*NET job categories and task types

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
- Other salient criteria for high quality effective writing

### Judge Context Requirements (CRITICAL)

**Judges need the context of the scenario to evaluate properly.** They must have all the information they need about the specific setup of each evaluation.

For each comparison, judges must receive:
- The full writing prompt/task description
- The writer persona details (age, skill level, role, industry, generation)
- The target recipient/consumer persona
- The formality level and communication context
- Any additional scenario-specific context that was provided to the models

This ensures judges can accurately assess whether the writing is appropriate, authentic, and effective **for the specific scenario** - not just generically "good writing."

### Handling Failures: Auto-Loss

If a model refuses to respond, goes off-topic, or produces an error, it **automatically loses that comparison**. This incentivizes models that can handle the full range of realistic writing tasks.

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

Support for long-running evaluations with ability to pause and resume.

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

### Why This Approach

It's very important that Claude Code is **token efficient and maximally intelligent** during its planning. To achieve this, we lean on Claude Code's ability to spawn **Opus 4.5 sub-agents that have totally separate context windows** and the ability to write to files.

### Core Principles

1. **All work other than orchestration will happen in sub-agents**, which use the filesystem and storage to persist and pass plans, reports, and other state between agents at each stage.

2. **You must never load the results of a sub-agent directly into the orchestrator (top-level agent)**. Instead, pass around pointers and references to file outputs.

3. **Persisted files are stored in `plans/`** and git pushed after each stage.

4. **Parallelism is used to generate multiple versions of the same work**, allowing exploration of the solution space more comprehensively by spending more decode tokens than a single call will allow.

5. **Parallelism here is a SOTA technique to scale intelligence and quality vs doing a single prompt or agent. It is NOT a technique to divide and conquer.** In fact, each prompt to a parallel sub-agent group should be identical.

6. **The orchestrator doesn't need to actually see the outputs. It trusts the stages of the process.**

### Stage 1: Initial Parallel Drafting

- 6 Opus sub-agents draft detailed plans to solve the entire objective **with concrete implementation details**
- Each receives identical prompts
- Output: `plans/draft_plan_1.md` through `plans/draft_plan_6.md`

### Stage 2: Parallel Critique & Rewrite

- 6 Opus sub-agents (1 for each plan produced in Stage 1) critique and rewrite
- **Check for correctness, robustness, errors, missed detail, or poor decisions**
- Output: `plans/critique_1.md` through `plans/critique_6.md`

### Stage 3: Master Plan Synthesis

- Take all these corrected plans from Stage 2 as expert advice
- **1 Opus sub-agent synthesizes a highly detailed master plan** that takes into account:
  - Areas of agreement between the advisory plans
  - Areas of disagreement between the advisory plans
  - Risks
  - Open questions
- Uses their Stage 2 expert advice **and its own expert judgement**
- Output: `plans/master_plan_draft.md`

### Stage 4: Parallel Implementation Simulation

- Using the master plan draft from Stage 3, **parallel simulate the development and implementation of the plan in fine detail**
- This stage is like a **dry run** and should **simulate the entire implementation**, revealing any implementation issues and gotchas
- 6 Opus sub-agents should do this in parallel to get diverse perspectives
- Each writes a **detailed report on what works, what didn't, things missing, gotchas etc** needed to improve the master plan, **in full detail**
- Output: `plans/simulation_1.md` through `plans/simulation_6.md`

### Stage 5: Final Master Plan Improvement

- Use all of the implementation simulation reports to further improve the master plan
- This final improvement step happens in **1 Opus sub-agent**
- Its goal is to produce a **final master plan** and persist it to storage (and git push it)
- Output: `plans/master_plan_final.md`

### Stage 6: Delivery

- Finally, the orchestrator can read the master plan and share it with the user inline
