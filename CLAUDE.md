# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Gemini Writing Evaluation Framework - comparing Gemini 3.0 Pro/Flash against competing frontier LLMs on realistic professional writing tasks.

**All planning requirements and methodology are in PROMPT.md** - read that file first.

## Directory Structure

PROMPT.md                 # Complete requirements and planning methodology
plans/                    # All planning artifacts (outputs from each stage)

Artifacts Generated
       │ 1     │ plans/draft_plan_1-6.md    │ 6 independent initial drafts    │
       │ 2     │ plans/critique_1-6.md      │ 6 critiqued & improved versions │
       │ 3     │ plans/master_plan_draft.md │ Synthesized master plan         │
       │ 4     │ plans/simulation_1-6.md    │ 6 implementation dry-runs       │
       │ 5     │ plans/master_plan_final.md │ Final deliverable               │

Final Master Plan Highlights
The final plan (plans/master_plan_final.md) is comprehensive (~32k tokens) and incorporates learnings from all 6 simulations. Key improvements over the draft:
       Critical Fixes Applied:
     - Resolved 15+ blocking issues that would cause runtime failures
     - Corrected cost estimates (were underestimated by 5-10x)
     - Added all missing data file specifications
     - Fixed memory-exploding algorithms with lazy generation patterns
     - Clarified voting methodology (majority-of-majorities)
     - Added comprehensive exception handling

       Structure Includes:
     1. Pre-implementation requirements - System dependencies, required data files, environment config
     2. Complete Pydantic schemas - All data models for tasks, personas, prompts, judgments
     3. Fixed O*NET pipeline - Schema validation, memory-efficient task extraction, NAICS mapping
     4. Prompt generation - 3-phase approach with attachment/reply support
     5. Evaluation engine - Corrected cost estimation, voting methodology, dual-persona judges
     6. API layer - Model verification, rate limiting, circuit breakers
     7. Storage & analysis - Checkpoint system, statistical tests, weakness analysis
     8. TUI implementation - Progress dashboard, results browser
     9. PDF report generation - Templates and chart building

       Preset Configurations (corrected costs):
       │ smoke    │ 10      │ ~$5    │ 6 min   │
       │ dev      │ 30      │ ~$25   │ 18 min  │
       │ standard │ 200     │ ~$800  │ 4 hrs   │
       │ full     │ 1000    │ ~$8000 │ 24 hrs  │

       View the full plan: plans/master_plan_final.md

implement plans/master_plan_final.md, drawing on PROMPT.md as the context, and the intermediate planning outputs listed above as needed if you want to see what went into the master plan. 

First create and persist a large TODO list to plans/, then execute the TODO list.  
implement using TDD methodology (1. Write failing tests, 2. Implement feature, 3. Run tests, 4. If any fail, debug and fix, 5. Refactor if needed, 6. Repeat until all green).  
Create a README.md.  
In addition to tests being green and at >90% coverage, use the CLI tool itself as you build it through self play / to test it works until it is finished. 
Output COMPLETE when all phases done.

