# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Objective

CREATE A MASTER PLAN FOR THE FOLLOWING WRITING EVAL FOR GEMINI

Use OpenRouter API and the latest O*NET database to produce a high quality effective writing eval that compares (SxS) Gemini 3.0 pro and 3.0 flash with the latest competing models (gpt5.2, Claude Opus, X, Kimi etc) in their class.

The eval itself should be made up of highly realistic writing tasks that are required across every single job in the US economy (proxy: ONET) and an evenly distributed range of industries for diversity within a single job type (eg CEO of fruit company, CEO of startup, CEO of charity).

The SxS itself should compare a range of salient criteria for high quality writing and be judged for quality of example, appropriate length and tone, effectiveness and other qualities by both a simulated writing expert and a simulated target recipient or reader of the writing for whatever task is at hand. Some writing prompts will require additional context, others will be simple prompts. Generate or provide download scripts for any eval context needed.

The goal is to produce a repeatable eval that has aggregate win rates per model pair (Gemini vs X) for every real world effective writing task and that allows meaningful inspection of judgements on a per writing task basis.

The big challenge is creating the right eval prompts for this task and then creating the robust, reliable, eval framework and judgement methodology to make such an eval highly trustworthy for researchers working on a frontier lab, in addition to a fine grained eval viewer and also aggregate statistics and visualisations/plots. The eval and AI judges must be correct and robust (always pairwise, best of 5, shuffle ordering, robust eval rubric etc). Assume a terminal environment, use SQLite if needed, allow exports to CSV. Generate a final lead evaluation analyst report as a PDF that digs into the data behind the aggregate win/loss rates and identifies specific areas of weakness in Gemini effective writing vs its peers.

The user will provide an OpenRouter key.

## Planning Methodology

This project uses a multi-stage planning process with parallel Opus 4.5 sub-agents to maximize intelligence and explore the solution space comprehensively.

**Key Principles:**
- All work happens in sub-agents, not the orchestrator
- Sub-agents write to files in `plans/` directory
- Orchestrator passes file references, never loads agent outputs directly
- Parallelism is used to generate multiple versions of the same work (scaling intelligence), NOT divide-and-conquer
- Each parallel sub-agent group receives identical prompts
- Git push after each stage

**Planning Stages:**

1. **Initial Parallel Drafting** - 6 sub-agents draft detailed plans to solve the entire objective with concrete implementation details

2. **Parallel Critique & Rewrite** - 6 sub-agents (1 per plan) check for correctness, robustness, errors, missed details, or poor decisions

3. **Master Plan Synthesis** - 1 Opus sub-agent synthesizes a highly detailed master plan considering areas of agreement, disagreement, risks, and open questions from the critiqued plans

4. **Parallel Implementation Simulation** - 6 sub-agents perform dry-run simulations of the master plan, revealing implementation issues and gotchas. Each writes a detailed report on what works, what doesn't, things missing, etc.

5. **Final Master Plan Improvement** - 1 Opus sub-agent uses all simulation reports to produce the final master plan

6. **Delivery** - Orchestrator reads and shares final master plan with user

## Directory Structure

```
plans/                    # All planning artifacts
  draft_plan_N.md        # Stage 1: Initial parallel drafts
  critique_N.md          # Stage 2: Critiques and rewrites
  master_plan_draft.md   # Stage 3: Synthesized master plan
  simulation_N.md        # Stage 4: Implementation simulation reports
  master_plan_final.md   # Stage 5: Final improved master plan
```
