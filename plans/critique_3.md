# Critique of Draft Plan 3: Gemini Writing Evaluation Framework

## Overview

Draft Plan 3 presents a comprehensive and well-structured implementation plan for the Gemini Writing Evaluation Framework. The plan demonstrates strong technical understanding and covers most major components specified in PROMPT.md. However, there are several areas requiring correction, improvement, and additional specification to ensure full compliance with requirements.

---

## Part 1: Detailed Critique

### 1.1 Strengths of the Draft Plan

1. **Excellent Architecture Design**: The layered architecture (UI, Orchestration, Execution, Persistence, Analysis) is clean and appropriate for the complexity of the system.

2. **Strong Data Models**: The Pydantic schemas for WritingPrompt, ModelResponse, JudgmentVote, and ComparisonResult are comprehensive and include most required metadata fields.

3. **Robust API Integration**: The OpenRouter client architecture with RateLimiter, RetryHandler, and CircuitBreaker demonstrates solid understanding of production API integration requirements.

4. **Good TUI Implementation**: The Textual-based progress dashboard design matches the detailed requirements from PROMPT.md well.

5. **Comprehensive Testing Strategy**: The testing approach covers unit and integration tests with appropriate fixtures.

### 1.2 Critical Issues and Missing Components

#### 1.2.1 Prompt Generation Issues

**Problem 1: Writing Categories are Hardcoded**

PROMPT.md explicitly states: "IMPORTANT: Avoid hardcoding specific categories and types of effective writing where possible. Let the O*NET data drive this diversity programmatically."

The draft plan hardcodes WRITING_CATEGORIES in ONetLoader:
```python
WRITING_CATEGORIES = {
    "explicit_writing": [...],
    "correspondence": [...],
    ...
}
```

**Impact**: This violates a critical directive and may miss writing tasks that don't fit predefined patterns.

**Problem 2: Missing Phase 1 - Offline LLM Generation**

The three-phase prompt generation approach is mentioned but Phase 1 (Offline LLM Generation for persona/context templates) is not actually implemented. The plan jumps from O*NET extraction directly to algorithmic combination.

**Problem 3: Communication Channel Handling**

PROMPT.md states: "Do NOT force tasks into predefined channel categories - let realistic variety emerge." However, the plan defines a CommunicationChannel enum with fixed options, which contradicts this requirement.

#### 1.2.2 Evaluation Methodology Issues

**Problem 4: Incomplete Judge Persona Implementation**

The dual judge persona system (Writing Expert vs Simulated Recipient) is described, but the recipient persona generation doesn't fully capture the depth required. PROMPT.md specifies the recipient persona should judge from the perspective of "whoever the writing is intended for in that specific task."

The `build_recipient_persona` method is too generic and doesn't adequately adapt to the specific context (e.g., different for a CEO recipient vs. junior employee recipient).

**Problem 5: Missing Instruction-Following Verification**

PROMPT.md requires: "Include some prompts with explicit constraints to test instruction-following" and "Track compliance separately."

The plan includes InstructionConstraint in the schema but doesn't implement the verification logic to actually check if constraints were followed.

**Problem 6: Ambiguity Handling Tracking Incomplete**

PROMPT.md specifies tracking specific behaviors for ambiguous prompts:
- Does it make reasonable assumptions?
- Does it ask for clarification?
- Does it hedge appropriately?
- Does it hallucinate specific details?

The plan marks prompts as deliberately_ambiguous but doesn't implement tracking for these specific behavioral patterns.

#### 1.2.3 Configuration and Cost Estimation Issues

**Problem 7: Flash-Tier Model Comparisons Missing**

The plan focuses heavily on Pro-tier comparisons but underspecifies the Flash-tier evaluation:
- Gemini 3.0 Flash vs GPT-4.1
- Gemini 3.0 Flash vs Claude Sonnet
- "Other flash-tier models in class"

The preset configurations only show Pro-tier model pairs.

**Problem 8: Time Estimates Not Calculated**

The cost estimation is implemented, but time estimation (which PROMPT.md requires in the estimate display) is mentioned but not actually calculated based on rate limits and parallelization.

#### 1.2.4 Analysis and Reporting Issues

**Problem 9: Win Rate Breakdown Missing Dimensions**

PROMPT.md requires win rates broken down by multiple dimensions beyond what's implemented:
- By age/generation of writer persona
- By communication channel
- By audience size
- By emotional context
- By message position (initial/reply/follow-up)

**Problem 10: Effect Size Calculation Missing**

PROMPT.md requires "effect sizes" in statistical analysis, but the StatisticalAnalyzer only computes win rates, confidence intervals, and kappa. Effect size measures (like Cohen's d or odds ratios) are not implemented.

**Problem 11: Response Format Bias Detection Incomplete**

The bias detection for "Format bias: Does one model overuse certain structures?" is mentioned but not fully implemented with statistical tests.

### 1.3 Technical Errors and Bugs

**Bug 1: Incorrect Vote Aggregation for Personas**

The vote aggregation groups by judge_model but doesn't account for the dual personas correctly. With 3 judges x 2 personas x 5 votes = 30 votes per comparison, the aggregation logic needs to handle persona-level aggregation before judge-level.

**Bug 2: Position Bias Analysis Missing Gemini Context**

The position bias analysis looks at A vs B preference but should specifically track whether Gemini being in position A vs B affects outcomes, not just raw A/B preference.

**Bug 3: Database Schema Missing Key Fields**

The prompts table is missing fields for:
- `audience_size`
- `emotional_context`
- `message_position`
- `temporal_context`
- `language` and `language_variant`

These are in the Pydantic model but not the SQL schema.

**Bug 4: Checkpoint Query Logic Issue**

The `get_incomplete_prompts` method for generation phase checks for existence of both responses, but doesn't handle the case where one model responded and the other didn't (partial completion).

### 1.4 Missing Components from PROMPT.md

1. **Regional English Variants Analysis**: No analysis implementation for how models adapt to en-GB, en-AU, or non-native recipient contexts.

2. **Refusal Categorization Tracking**: The RefusalCategory system isn't fully integrated into analysis and reporting.

3. **Tone Matching Evaluation**: When tone_example is provided, there's no mechanism to evaluate whether the model matched the established tone.

4. **Multiple Recipients (CC) Analysis**: No specific analysis for how models handle multi-audience communication.

5. **Cross-Run Comparison Command**: The `compare` CLI command is stubbed but not implemented.

6. **Auto-Generated README**: Each run directory should have an auto-generated README.md (mentioned in PROMPT.md results structure) but not implemented.

7. **CSV Export Functionality**: Mentioned in PROMPT.md but not fully implemented in the results manager.

---

## Part 2: Improved Implementation Plan

### 2.1 Revised Prompt Generation Pipeline

Replace the hardcoded writing categories with a data-driven approach:

```python
class ONetTaskExtractor:
    """Extract writing-relevant tasks from O*NET using the preprocessed reference"""

    def __init__(self, db_path: Path, reference_path: Path):
        self.db_path = db_path
        self.reference = self._load_reference(reference_path)

    def _load_reference(self, path: Path) -> WritingReference:
        """Load the ONET_WRITING_REFERENCE.md preprocessed by Opus"""
        # Parse the reference document for task mappings
        pass

    async def extract_all_writing_tasks(self) -> list[ONetWritingTask]:
        """Extract tasks based on the Opus-preprocessed reference, not hardcoded categories"""
        async with aiosqlite.connect(self.db_path) as db:
            # Use reference-guided extraction, not pattern matching
            tasks = []
            for task_id in self.reference.writing_task_ids:
                task = await self._fetch_task_with_context(db, task_id)
                tasks.append(task)
            return tasks

    async def _fetch_task_with_context(
        self, db: aiosqlite.Connection, task_id: str
    ) -> ONetWritingTask:
        """Fetch task with full occupation context"""
        query = """
            SELECT
                t.task_id,
                t.task,
                t.task_type,
                o.onetsoc_code,
                o.title as occupation_title,
                o.description as occupation_description,
                jz.job_zone
            FROM task_statements t
            JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
            JOIN job_zones jz ON o.onetsoc_code = jz.onetsoc_code
            WHERE t.task_id = ?
        """
        # Return enriched task object
        pass
```

### 2.2 Full Three-Phase Generation Implementation

```python
class PromptGenerationPipeline:
    """Complete three-phase prompt generation as specified in PROMPT.md"""

    def __init__(
        self,
        onet_extractor: ONetTaskExtractor,
        api_client: OpenRouterClient,
        config: PromptGenerationConfig
    ):
        self.extractor = onet_extractor
        self.api_client = api_client
        self.config = config

    async def generate_prompts(self, n_prompts: int, seed: int) -> list[WritingPrompt]:
        """Execute all three phases of prompt generation"""

        # Phase 1: Offline LLM Generation (pre-generate templates)
        templates = await self._phase1_generate_templates(seed)

        # Phase 2: Algorithmic Combinations
        base_prompts = await self._phase2_algorithmic_combination(
            n_prompts, templates, seed
        )

        # Phase 3: LLM Enrichment for complex prompts
        final_prompts = await self._phase3_llm_enrichment(base_prompts)

        return final_prompts

    async def _phase1_generate_templates(self, seed: int) -> PromptTemplates:
        """Phase 1: Use evaluated models to generate diverse templates"""

        # Use the same models being evaluated (as per PROMPT.md)
        generation_models = [
            "google/gemini-3-pro",
            "google/gemini-3-flash",
            "openai/gpt-5.2-thinking",
            "anthropic/claude-opus-4.5"
        ]

        templates = PromptTemplates()

        # Generate persona variations
        for model in generation_models:
            persona_batch = await self._generate_personas_with_model(model, seed)
            templates.personas.extend(persona_batch)

        # Generate context variations
        for model in generation_models:
            context_batch = await self._generate_contexts_with_model(model, seed)
            templates.contexts.extend(context_batch)

        # Track which model generated which templates (for bias analysis)
        templates.generation_log = self._log_generation_sources()

        return templates

    async def _phase2_algorithmic_combination(
        self,
        n_prompts: int,
        templates: PromptTemplates,
        seed: int
    ) -> list[WritingPrompt]:
        """Phase 2: Deterministic algorithmic combination"""

        rng = random.Random(seed)
        tasks = await self.extractor.extract_all_writing_tasks()

        prompts = []
        sampler = StratifiedSampler(
            tasks=tasks,
            templates=templates,
            config=self.config.sampling,
            rng=rng
        )

        for i in range(n_prompts):
            # Sample task, ensuring diversity
            task = sampler.sample_task()

            # Sample industry using NAICS
            industry = sampler.sample_industry(task.soc_code)

            # Get real company for industry
            company = self.company_db.get_company(
                naics_code=industry,
                seed=rng.randint(0, 2**32)
            )

            # Sample persona dimensions (from Phase 1 templates)
            writer = sampler.sample_writer_persona(task, company)
            recipients = sampler.sample_recipients(task, company)

            # Sample communication dimensions
            # Let channel emerge from task naturally, don't force categories
            channel = self._infer_channel_from_task(task.task_statement)

            formality = sampler.sample_formality(task, company)
            urgency = sampler.sample_urgency(task)
            # ... other dimensions

            prompt = WritingPrompt(
                prompt_id=f"p_{seed}_{i:05d}",
                onet_task_id=task.task_id,
                onet_soc_code=task.soc_code,
                task_statement=task.task_statement,
                # ... all fields
                generation_phase=2,
                random_seed=seed
            )
            prompts.append(prompt)

        return prompts

    def _infer_channel_from_task(self, task_statement: str) -> str:
        """Infer channel naturally from task statement, not force into categories"""
        # Return the natural communication medium implied by the task
        # e.g., "Draft email" -> "email", "Prepare memo" -> "memo"
        # If unclear, return "unspecified" and let Phase 3 determine
        task_lower = task_statement.lower()

        if "email" in task_lower:
            return "email"
        elif "memo" in task_lower or "memorandum" in task_lower:
            return "memo"
        elif "report" in task_lower:
            return "report"
        elif "letter" in task_lower:
            return "letter"
        elif "present" in task_lower:
            return "presentation"
        elif "post" in task_lower or "social" in task_lower:
            return "social_media"
        else:
            return "unspecified"  # Let LLM enrichment determine
```

### 2.3 Corrected Vote Aggregation with Persona Handling

```python
class VoteAggregator:
    """Aggregate votes using majority-of-majorities with proper persona handling"""

    def aggregate(
        self,
        votes: list[JudgmentVote],
        model_pair: ModelPair
    ) -> ComparisonResult:
        """
        Aggregation logic:
        1. For each judge model, aggregate across both personas
        2. Get majority within each judge (across personas and votes)
        3. Take majority of the 3 judge majorities
        """

        # Group by judge model
        by_judge: dict[str, list[JudgmentVote]] = defaultdict(list)
        for vote in votes:
            by_judge[vote.judge_model].append(vote)

        judge_majorities: dict[str, str] = {}
        judge_breakdowns: dict[str, JudgeBreakdown] = {}

        for judge_model, judge_votes in by_judge.items():
            # Count wins across all personas and votes for this judge
            gemini_wins = sum(1 for v in judge_votes if v.winner_model == model_pair.gemini)
            competitor_wins = sum(1 for v in judge_votes if v.winner_model == model_pair.competitor)
            ties = sum(1 for v in judge_votes if v.winner == "tie")

            total_votes = len(judge_votes)

            # Determine this judge's majority verdict
            if gemini_wins > competitor_wins and gemini_wins > ties:
                judge_majorities[judge_model] = "gemini"
            elif competitor_wins > gemini_wins and competitor_wins > ties:
                judge_majorities[judge_model] = "competitor"
            else:
                judge_majorities[judge_model] = "tie"

            # Store breakdown for analysis
            judge_breakdowns[judge_model] = JudgeBreakdown(
                gemini_votes=gemini_wins,
                competitor_votes=competitor_wins,
                tie_votes=ties,
                total_votes=total_votes,
                majority=judge_majorities[judge_model],
                # Persona-level breakdown
                by_persona={
                    persona: self._aggregate_persona_votes(
                        [v for v in judge_votes if v.judge_persona == persona],
                        model_pair
                    )
                    for persona in ["writing_expert", "recipient"]
                }
            )

        # Majority of majorities
        final_counts = Counter(judge_majorities.values())

        if final_counts["gemini"] > final_counts["competitor"]:
            final_winner = "gemini"
        elif final_counts["competitor"] > final_counts["gemini"]:
            final_winner = "competitor"
        else:
            final_winner = "tie"

        return ComparisonResult(
            # ... standard fields
            final_winner=final_winner,
            judge_agreement_count=max(final_counts.values()),
            judge_breakdowns=judge_breakdowns,  # New: detailed breakdown
            # ...
        )

    def _aggregate_persona_votes(
        self,
        votes: list[JudgmentVote],
        model_pair: ModelPair
    ) -> PersonaBreakdown:
        """Get breakdown for a specific persona"""
        return PersonaBreakdown(
            gemini_votes=sum(1 for v in votes if v.winner_model == model_pair.gemini),
            competitor_votes=sum(1 for v in votes if v.winner_model == model_pair.competitor),
            tie_votes=sum(1 for v in votes if v.winner == "tie")
        )
```

### 2.4 Complete Flash-Tier Configuration

```python
# Add Flash-tier model pairs to all presets
FLASH_MODEL_PAIRS = [
    ModelPair("google/gemini-3-flash", "openai/gpt-4.1"),
    ModelPair("google/gemini-3-flash", "anthropic/claude-sonnet"),
]

PRO_MODEL_PAIRS = [
    ModelPair("google/gemini-3-pro", "openai/gpt-5.2-thinking"),
    ModelPair("google/gemini-3-pro", "anthropic/claude-opus-4.5"),
    ModelPair("google/gemini-3-pro", "x-ai/grok-4.1-thinking"),
    ModelPair("google/gemini-3-pro", "moonshot/kimi-k2-thinking"),
]

ALL_MODEL_PAIRS = PRO_MODEL_PAIRS + FLASH_MODEL_PAIRS

# Updated preset 6 (Standard Eval) as example
PRESETS[6] = EvalConfig(
    name="Standard Eval",
    num_prompts=500,
    model_pairs=ALL_MODEL_PAIRS,  # Include both tiers
    model_tier_filter=None,  # Run both tiers
    judge_models=[
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2",
        "google/gemini-3-pro"
    ],
    votes_per_judge=5,
    judge_personas=["writing_expert", "recipient"],
    estimated_cost=500,
    estimated_time_minutes=180,
    description="Standard evaluation run with all model tiers"
)

# Add tier filtering option
@app.command()
def run(
    # ... existing options
    tier: str = typer.Option(None, "--tier", help="Model tier: 'pro', 'flash', or 'all'"),
):
    if tier == "pro":
        config.model_pairs = [p for p in config.model_pairs if "pro" in p.gemini]
    elif tier == "flash":
        config.model_pairs = [p for p in config.model_pairs if "flash" in p.gemini]
```

### 2.5 Instruction-Following Verification System

```python
class InstructionComplianceChecker:
    """Verify whether responses comply with explicit constraints"""

    def __init__(self):
        self.checkers = {
            "length": self._check_length_constraint,
            "format": self._check_format_constraint,
            "tone": self._check_tone_constraint,
            "exclusion": self._check_exclusion_constraint,
            "inclusion": self._check_inclusion_constraint,
        }

    def check_compliance(
        self,
        response: ModelResponse,
        constraints: list[InstructionConstraint]
    ) -> dict[str, ConstraintResult]:
        """Check all constraints and return compliance results"""
        results = {}

        for constraint in constraints:
            if constraint.verifiable:
                checker = self.checkers.get(constraint.type)
                if checker:
                    results[constraint.constraint] = checker(
                        response.response_text, constraint
                    )
                else:
                    results[constraint.constraint] = ConstraintResult(
                        compliant=None,
                        reason="No verifier for this constraint type"
                    )

        return results

    def _check_length_constraint(
        self,
        text: str,
        constraint: InstructionConstraint
    ) -> ConstraintResult:
        """Check word/character count constraints"""
        word_count = len(text.split())

        # Parse constraint like "under 100 words" or "at least 500 words"
        import re
        match = re.search(r'(under|at least|exactly|between)\s+(\d+)(?:\s+(?:and|to)\s+(\d+))?\s+words?', constraint.constraint.lower())

        if not match:
            return ConstraintResult(compliant=None, reason="Could not parse length constraint")

        constraint_type = match.group(1)
        limit1 = int(match.group(2))
        limit2 = int(match.group(3)) if match.group(3) else None

        if constraint_type == "under":
            compliant = word_count < limit1
        elif constraint_type == "at least":
            compliant = word_count >= limit1
        elif constraint_type == "exactly":
            compliant = word_count == limit1
        elif constraint_type == "between" and limit2:
            compliant = limit1 <= word_count <= limit2
        else:
            compliant = None

        return ConstraintResult(
            compliant=compliant,
            actual_value=word_count,
            expected=constraint.constraint
        )

    def _check_format_constraint(
        self,
        text: str,
        constraint: InstructionConstraint
    ) -> ConstraintResult:
        """Check format constraints (bullets, paragraphs, headers)"""
        constraint_lower = constraint.constraint.lower()

        if "bullet" in constraint_lower:
            # Count bullet points
            bullet_count = text.count("- ") + text.count("• ") + text.count("* ")
            match = re.search(r'(\d+)\s+bullet', constraint_lower)
            if match:
                expected = int(match.group(1))
                return ConstraintResult(
                    compliant=(bullet_count == expected),
                    actual_value=bullet_count,
                    expected=f"{expected} bullets"
                )

        if "paragraph form only" in constraint_lower:
            has_bullets = any(marker in text for marker in ["- ", "• ", "* "])
            has_numbered = bool(re.search(r'^\d+\.\s', text, re.MULTILINE))
            return ConstraintResult(
                compliant=not (has_bullets or has_numbered),
                reason="Must be paragraph form without lists"
            )

        return ConstraintResult(compliant=None, reason="Unrecognized format constraint")

    def _check_exclusion_constraint(
        self,
        text: str,
        constraint: InstructionConstraint
    ) -> ConstraintResult:
        """Check exclusion constraints (do not mention X)"""
        # Parse "do not mention the budget" style constraints
        match = re.search(r'(?:do not|don\'t|avoid)\s+mention(?:ing)?\s+(?:the\s+)?(.+)', constraint.constraint.lower())

        if match:
            excluded_term = match.group(1).strip()
            contains_term = excluded_term.lower() in text.lower()
            return ConstraintResult(
                compliant=not contains_term,
                reason=f"Text {'contains' if contains_term else 'does not contain'} '{excluded_term}'"
            )

        return ConstraintResult(compliant=None, reason="Could not parse exclusion constraint")

    def _check_tone_constraint(
        self,
        text: str,
        constraint: InstructionConstraint
    ) -> ConstraintResult:
        """Tone constraints require LLM verification - mark for judge evaluation"""
        return ConstraintResult(
            compliant=None,
            reason="Tone compliance requires judge evaluation",
            requires_judge_verification=True
        )

    def _check_inclusion_constraint(
        self,
        text: str,
        constraint: InstructionConstraint
    ) -> ConstraintResult:
        """Check inclusion constraints (must include X)"""
        match = re.search(r'(?:must|should)\s+(?:include|mention)\s+(.+)', constraint.constraint.lower())

        if match:
            required_term = match.group(1).strip()
            contains_term = required_term.lower() in text.lower()
            return ConstraintResult(
                compliant=contains_term,
                reason=f"Text {'contains' if contains_term else 'does not contain'} '{required_term}'"
            )

        return ConstraintResult(compliant=None, reason="Could not parse inclusion constraint")
```

### 2.6 Ambiguity Handling Behavior Tracking

```python
class AmbiguityBehaviorAnalyzer:
    """Analyze how models handle deliberately ambiguous prompts"""

    BEHAVIOR_PATTERNS = {
        "asks_clarification": [
            r"(?:what|which|could you|can you)\s+(?:specific|clarify|tell me more)",
            r"(?:to clarify|for clarification)",
            r"(?:i\'m not sure|unclear|need more information)",
            r"(?:do you mean|are you referring to)",
        ],
        "makes_assumptions": [
            r"(?:i\'ll assume|assuming that|i\'m assuming)",
            r"(?:based on|given that|since you mentioned)",
            r"(?:i\'ll proceed with|let me interpret this as)",
        ],
        "hedges_appropriately": [
            r"(?:if applicable|if relevant|depending on)",
            r"(?:you may want to|consider|might need to)",
            r"(?:please adjust|feel free to modify)",
        ],
        "hallucinated_specifics": [
            # Detect when model invents specific details not in prompt
            # This requires comparison with prompt content
        ]
    }

    async def analyze_response(
        self,
        prompt: WritingPrompt,
        response: ModelResponse
    ) -> AmbiguityBehavior:
        """Analyze how the model handled an ambiguous prompt"""

        if not prompt.deliberate_ambiguity:
            return None

        behaviors = {}

        # Pattern-based detection
        for behavior, patterns in self.BEHAVIOR_PATTERNS.items():
            if behavior == "hallucinated_specifics":
                behaviors[behavior] = await self._detect_hallucination(prompt, response)
            else:
                behaviors[behavior] = self._detect_pattern(response.response_text, patterns)

        return AmbiguityBehavior(
            prompt_id=prompt.prompt_id,
            ambiguity_type=prompt.ambiguity_type,
            asks_clarification=behaviors.get("asks_clarification", False),
            makes_assumptions=behaviors.get("makes_assumptions", False),
            hedges_appropriately=behaviors.get("hedges_appropriately", False),
            hallucinated_specifics=behaviors.get("hallucinated_specifics", False),
            raw_patterns=behaviors
        )

    def _detect_pattern(self, text: str, patterns: list[str]) -> bool:
        """Check if any pattern matches in the text"""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in patterns)

    async def _detect_hallucination(
        self,
        prompt: WritingPrompt,
        response: ModelResponse
    ) -> bool:
        """Detect if model hallucinated specific details not in prompt"""
        # Extract specific details from response (names, numbers, dates)
        response_specifics = self._extract_specifics(response.response_text)
        prompt_content = prompt.enriched_prompt

        # If ambiguity type is "underspecified" and response contains
        # specific details not present in prompt, likely hallucination
        if prompt.ambiguity_type == "underspecified":
            for specific in response_specifics:
                if specific not in prompt_content:
                    return True

        return False

    def _extract_specifics(self, text: str) -> list[str]:
        """Extract specific details like names, dates, numbers"""
        specifics = []

        # Extract dates
        dates = re.findall(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:,? \d{4})?\b', text)
        specifics.extend(dates)

        # Extract dollar amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        specifics.extend(amounts)

        # Extract percentages
        percentages = re.findall(r'\d+(?:\.\d+)?%', text)
        specifics.extend(percentages)

        return specifics
```

### 2.7 Corrected Database Schema

```sql
-- Complete schema including all required fields from PROMPT.md

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),

    -- O*NET context
    onet_task_id TEXT NOT NULL,
    onet_soc_code TEXT NOT NULL,
    occupation_title TEXT NOT NULL,
    occupation_description TEXT,
    job_zone INTEGER NOT NULL,
    soc_major_group TEXT NOT NULL,

    -- Task content
    task_statement TEXT NOT NULL,
    enriched_prompt TEXT NOT NULL,

    -- Company context (JSON)
    company_json JSON NOT NULL,

    -- Personas (JSON)
    writer_json JSON NOT NULL,
    recipients_json JSON NOT NULL,
    cc_recipients_json JSON,

    -- Communication context (all fields from schema)
    channel TEXT NOT NULL,
    formality_level INTEGER NOT NULL,
    urgency_level INTEGER NOT NULL,
    relationship_context TEXT NOT NULL,
    audience_size TEXT NOT NULL,
    emotional_context TEXT,
    message_position TEXT NOT NULL,

    -- Additional context
    temporal_context TEXT,
    attachments_json JSON,
    prior_message TEXT,
    tone_example TEXT,
    competing_objectives_json JSON,

    -- Task types
    is_revision_task BOOLEAN DEFAULT FALSE,
    original_text TEXT,
    revision_instruction TEXT,

    -- Ambiguity
    deliberate_ambiguity BOOLEAN DEFAULT FALSE,
    ambiguity_type TEXT,

    -- Constraints
    explicit_constraints_json JSON,

    -- Categorization
    writing_category TEXT NOT NULL,
    sensitive_category TEXT,

    -- Language (for future extension)
    language TEXT DEFAULT 'en',
    language_variant TEXT DEFAULT 'en-US',

    -- Regional variants for analysis
    writer_english_variant TEXT DEFAULT 'en-US',
    recipient_english_variant TEXT DEFAULT 'en-US',

    -- Generation metadata
    generation_phase INTEGER NOT NULL,
    generation_model TEXT,
    generation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    random_seed INTEGER NOT NULL,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Response table with all tracking fields
CREATE TABLE IF NOT EXISTS responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model_id TEXT NOT NULL,

    -- Response content
    response_text TEXT NOT NULL,

    -- Length metrics
    response_length_chars INTEGER NOT NULL,
    response_length_words INTEGER NOT NULL,
    response_length_tokens INTEGER NOT NULL,

    -- Timing
    response_time_ms INTEGER NOT NULL,

    -- Status and failures
    status TEXT NOT NULL,  -- success, refused, error, timeout, incomplete, off_topic
    refusal_category TEXT,  -- safety, capability, misunderstanding, incomplete, off_topic
    error_message TEXT,

    -- Format detection
    uses_bullet_points BOOLEAN,
    uses_headers BOOLEAN,
    uses_numbered_list BOOLEAN,
    greeting_type TEXT,
    signoff_type TEXT,
    format_metadata_json JSON,

    -- Constraint compliance (if applicable)
    constraint_compliance_json JSON,

    -- Ambiguity behavior (if applicable)
    ambiguity_behavior_json JSON,

    -- API metadata
    openrouter_request_id TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_id)
);

-- Additional indexes for analysis queries
CREATE INDEX idx_prompts_audience_size ON prompts(audience_size);
CREATE INDEX idx_prompts_emotional_context ON prompts(emotional_context);
CREATE INDEX idx_prompts_message_position ON prompts(message_position);
CREATE INDEX idx_prompts_writer_variant ON prompts(writer_english_variant);
CREATE INDEX idx_prompts_recipient_variant ON prompts(recipient_english_variant);
CREATE INDEX idx_responses_status ON responses(status);
CREATE INDEX idx_responses_refusal_category ON responses(refusal_category);
```

### 2.8 Complete Statistical Analysis with Effect Sizes

```python
class StatisticalAnalyzer:
    """Comprehensive statistical analysis including effect sizes"""

    async def compute_win_rates_with_effect_sizes(
        self,
        model_pair: Optional[ModelPair] = None
    ) -> dict[str, WinRateResult]:
        """Compute win rates with confidence intervals AND effect sizes"""

        comparisons = await self._fetch_comparisons(model_pair)

        by_pair = self._group_by_pair(comparisons)

        results = {}
        for pair_key, pair_comparisons in by_pair.items():
            n = len(pair_comparisons)
            gemini_wins = sum(1 for c in pair_comparisons if c['final_winner'] == 'gemini')
            competitor_wins = sum(1 for c in pair_comparisons if c['final_winner'] == 'competitor')
            ties = sum(1 for c in pair_comparisons if c['final_winner'] == 'tie')

            win_rate = gemini_wins / n if n > 0 else 0

            # Wilson score confidence interval
            ci_lower, ci_upper = self._wilson_ci(gemini_wins, n)

            # Effect size: Odds Ratio
            odds_ratio = self._compute_odds_ratio(gemini_wins, competitor_wins)

            # Effect size: Cohen's h (for proportions)
            cohens_h = self._compute_cohens_h(win_rate)

            # Statistical significance test (binomial test)
            p_value = self._binomial_test(gemini_wins, n)

            results[pair_key] = WinRateResult(
                pair_key=pair_key,
                total_comparisons=n,
                gemini_wins=gemini_wins,
                competitor_wins=competitor_wins,
                ties=ties,
                win_rate=win_rate,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                # Effect sizes
                odds_ratio=odds_ratio,
                odds_ratio_ci=self._odds_ratio_ci(gemini_wins, competitor_wins),
                cohens_h=cohens_h,
                # Significance
                p_value=p_value,
                significant_at_05=p_value < 0.05,
                significant_at_01=p_value < 0.01
            )

        return results

    def _compute_odds_ratio(self, wins_a: int, wins_b: int) -> float:
        """Compute odds ratio: (wins_a / wins_b)"""
        # Add 0.5 to avoid division by zero (Haldane-Anscombe correction)
        return (wins_a + 0.5) / (wins_b + 0.5)

    def _compute_cohens_h(self, proportion: float, baseline: float = 0.5) -> float:
        """Cohen's h effect size for comparing proportions"""
        import math
        phi1 = 2 * math.asin(math.sqrt(proportion))
        phi2 = 2 * math.asin(math.sqrt(baseline))
        return phi1 - phi2

    def _binomial_test(self, successes: int, n: int, p: float = 0.5) -> float:
        """Two-sided binomial test against null hypothesis of 50% win rate"""
        from scipy.stats import binomtest
        result = binomtest(successes, n, p, alternative='two-sided')
        return result.pvalue

    def _odds_ratio_ci(
        self,
        wins_a: int,
        wins_b: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Confidence interval for odds ratio using log transform"""
        import math
        from scipy.stats import norm

        # Haldane-Anscombe correction
        a = wins_a + 0.5
        b = wins_b + 0.5

        log_or = math.log(a / b)
        se_log_or = math.sqrt(1/a + 1/b)

        z = norm.ppf(1 - (1 - confidence) / 2)

        ci_lower = math.exp(log_or - z * se_log_or)
        ci_upper = math.exp(log_or + z * se_log_or)

        return (ci_lower, ci_upper)

    async def compute_win_rates_by_all_dimensions(self) -> DimensionalAnalysis:
        """Compute win rates broken down by ALL required dimensions"""

        dimensions = {
            "occupation": "onet_soc_code",
            "soc_major_group": "soc_major_group",
            "industry": "company_json->>'industry_naics'",
            "job_zone": "job_zone",
            "formality_level": "formality_level",
            "writing_category": "writing_category",
            "sensitive_category": "sensitive_category",
            "channel": "channel",
            "audience_size": "audience_size",
            "emotional_context": "emotional_context",
            "message_position": "message_position",
            "urgency_level": "urgency_level",
            "relationship_context": "relationship_context",
            "writer_generation": "writer_json->>'generation'",
            "writer_age_range": "writer_json->>'age_range'",
            "recipient_english_variant": "recipient_english_variant",
            "is_revision_task": "is_revision_task",
            "deliberate_ambiguity": "deliberate_ambiguity",
        }

        results = {}
        for dim_name, db_field in dimensions.items():
            results[dim_name] = await self._win_rates_by_dimension(db_field)

        return DimensionalAnalysis(
            dimensions=results,
            timestamp=datetime.utcnow()
        )

    async def _win_rates_by_dimension(self, dimension_field: str) -> dict[str, WinRateResult]:
        """Compute win rates grouped by a specific dimension"""

        query = f"""
            SELECT
                {dimension_field} as dimension_value,
                SUM(CASE WHEN c.final_winner = 'gemini' THEN 1 ELSE 0 END) as gemini_wins,
                SUM(CASE WHEN c.final_winner = 'competitor' THEN 1 ELSE 0 END) as competitor_wins,
                SUM(CASE WHEN c.final_winner = 'tie' THEN 1 ELSE 0 END) as ties,
                COUNT(*) as total
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            GROUP BY {dimension_field}
            HAVING total >= 5  -- Minimum sample size
        """

        rows = await self.storage.fetch_all(query)

        results = {}
        for row in rows:
            dim_value = row['dimension_value'] or "unspecified"
            n = row['total']
            gemini_wins = row['gemini_wins']

            win_rate = gemini_wins / n if n > 0 else 0
            ci_lower, ci_upper = self._wilson_ci(gemini_wins, n)

            results[dim_value] = WinRateResult(
                total_comparisons=n,
                gemini_wins=gemini_wins,
                competitor_wins=row['competitor_wins'],
                ties=row['ties'],
                win_rate=win_rate,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                odds_ratio=self._compute_odds_ratio(gemini_wins, row['competitor_wins']),
                cohens_h=self._compute_cohens_h(win_rate)
            )

        return results
```

### 2.9 Time Estimation Implementation

```python
class TimeEstimator:
    """Estimate evaluation run time based on rate limits and parallelization"""

    # API rate limits (requests per minute) - conservative estimates
    RATE_LIMITS = {
        "openai": 60,
        "anthropic": 50,
        "google": 60,
        "x-ai": 30,
        "moonshot": 30
    }

    # Average response times (seconds)
    AVG_RESPONSE_TIMES = {
        "openai/gpt-5.2-thinking": 5.0,
        "openai/gpt-4.1": 2.0,
        "anthropic/claude-opus-4.5": 4.0,
        "anthropic/claude-sonnet": 2.0,
        "google/gemini-3-pro": 3.0,
        "google/gemini-3-flash": 1.5,
        "x-ai/grok-4.1-thinking": 4.0,
        "moonshot/kimi-k2-thinking": 4.0
    }

    def estimate_time(self, config: EvalConfig) -> TimeEstimate:
        """Estimate total time for evaluation run"""

        # Phase 1: Response generation time
        generation_time = self._estimate_generation_time(config)

        # Phase 2: Judging time
        judging_time = self._estimate_judging_time(config)

        # Total with overhead
        total_sequential = generation_time + judging_time
        total_parallel = self._estimate_parallel_time(config)

        return TimeEstimate(
            generation_time_minutes=generation_time / 60,
            judging_time_minutes=judging_time / 60,
            total_sequential_minutes=total_sequential / 60,
            total_parallel_minutes=total_parallel / 60,
            bottleneck=self._identify_bottleneck(config),
            rate_limit_warnings=self._check_rate_limit_warnings(config)
        )

    def _estimate_generation_time(self, config: EvalConfig) -> float:
        """Estimate time for response generation phase"""
        total_seconds = 0

        for model_pair in config.model_pairs:
            # Time for Gemini responses
            gemini_provider = self._get_provider(model_pair.gemini)
            gemini_rate = self.RATE_LIMITS[gemini_provider]
            gemini_response_time = self.AVG_RESPONSE_TIMES.get(model_pair.gemini, 3.0)

            # Time for competitor responses
            competitor_provider = self._get_provider(model_pair.competitor)
            competitor_rate = self.RATE_LIMITS[competitor_provider]
            competitor_response_time = self.AVG_RESPONSE_TIMES.get(model_pair.competitor, 3.0)

            # Sequential time (rate-limited)
            time_per_prompt = max(
                60 / gemini_rate,  # Rate limit delay
                gemini_response_time
            ) + max(
                60 / competitor_rate,
                competitor_response_time
            )

            total_seconds += time_per_prompt * config.num_prompts

        return total_seconds

    def _estimate_judging_time(self, config: EvalConfig) -> float:
        """Estimate time for judging phase"""
        total_seconds = 0

        # Total judge calls per comparison
        calls_per_comparison = (
            len(config.judge_models) *
            config.votes_per_judge *
            len(config.judge_personas)
        )

        total_comparisons = config.num_prompts * len(config.model_pairs)
        total_judge_calls = total_comparisons * calls_per_comparison

        # Estimate based on slowest judge rate
        slowest_rate = min(
            self.RATE_LIMITS[self._get_provider(j)]
            for j in config.judge_models
        )

        # Time = calls / rate (calls per minute)
        total_seconds = (total_judge_calls / slowest_rate) * 60

        return total_seconds

    def _estimate_parallel_time(self, config: EvalConfig) -> float:
        """Estimate time with maximum parallelization"""
        # With parallelization, we're limited by:
        # 1. Per-provider rate limits (can parallelize across providers)
        # 2. Per-call response time

        generation_parallel = self._parallel_generation_time(config)
        judging_parallel = self._parallel_judging_time(config)

        return generation_parallel + judging_parallel

    def _parallel_generation_time(self, config: EvalConfig) -> float:
        """Generation time with parallel execution across providers"""
        # Group model pairs by provider
        by_provider = defaultdict(list)
        for pair in config.model_pairs:
            by_provider[self._get_provider(pair.gemini)].append(pair)
            by_provider[self._get_provider(pair.competitor)].append(pair)

        # Find bottleneck provider
        max_time = 0
        for provider, pairs in by_provider.items():
            provider_calls = len(pairs) * config.num_prompts
            provider_rate = self.RATE_LIMITS[provider]
            provider_time = (provider_calls / provider_rate) * 60
            max_time = max(max_time, provider_time)

        return max_time

    def _get_provider(self, model: str) -> str:
        """Extract provider from model ID"""
        return model.split("/")[0]

    def _identify_bottleneck(self, config: EvalConfig) -> str:
        """Identify what's limiting the evaluation speed"""
        # Check if any provider is significantly slower
        provider_loads = defaultdict(int)
        for pair in config.model_pairs:
            provider_loads[self._get_provider(pair.gemini)] += config.num_prompts
            provider_loads[self._get_provider(pair.competitor)] += config.num_prompts

        # Add judge calls
        total_judge_calls = (
            config.num_prompts *
            len(config.model_pairs) *
            len(config.judge_models) *
            config.votes_per_judge *
            len(config.judge_personas)
        )

        for judge in config.judge_models:
            provider = self._get_provider(judge)
            provider_loads[provider] += total_judge_calls // len(config.judge_models)

        # Find highest load relative to rate limit
        bottleneck = max(
            provider_loads.keys(),
            key=lambda p: provider_loads[p] / self.RATE_LIMITS[p]
        )

        return f"{bottleneck} ({provider_loads[bottleneck]} calls, {self.RATE_LIMITS[bottleneck]} RPM limit)"
```

### 2.10 Position Bias Analysis with Gemini Context

```python
class PositionBiasAnalyzer:
    """Analyze position bias with Gemini-specific context"""

    async def analyze_position_bias(self, storage: StorageManager) -> PositionBiasResult:
        """Comprehensive position bias analysis"""

        judgments = await storage.fetch_all("""
            SELECT
                winner,
                position_a_was_gemini,
                winner_model,
                judge_model
            FROM judgments
        """)

        # Overall A vs B preference
        a_wins = sum(1 for j in judgments if j['winner'] == 'A')
        b_wins = sum(1 for j in judgments if j['winner'] == 'B')
        ties = sum(1 for j in judgments if j['winner'] == 'tie')
        total = len(judgments)

        # Gemini win rate when in position A vs position B
        gemini_wins_as_a = sum(
            1 for j in judgments
            if j['position_a_was_gemini'] and j['winner'] == 'A'
        )
        gemini_total_as_a = sum(
            1 for j in judgments if j['position_a_was_gemini']
        )

        gemini_wins_as_b = sum(
            1 for j in judgments
            if not j['position_a_was_gemini'] and j['winner'] == 'B'
        )
        gemini_total_as_b = sum(
            1 for j in judgments if not j['position_a_was_gemini']
        )

        gemini_win_rate_as_a = gemini_wins_as_a / gemini_total_as_a if gemini_total_as_a > 0 else 0
        gemini_win_rate_as_b = gemini_wins_as_b / gemini_total_as_b if gemini_total_as_b > 0 else 0

        # Chi-squared test for position bias
        from scipy.stats import chisquare, chi2_contingency

        # Test 1: Overall A vs B preference
        expected = (a_wins + b_wins) / 2
        chi2_overall, p_overall = chisquare([a_wins, b_wins], [expected, expected])

        # Test 2: Gemini win rate by position (2x2 contingency)
        contingency_table = [
            [gemini_wins_as_a, gemini_total_as_a - gemini_wins_as_a],
            [gemini_wins_as_b, gemini_total_as_b - gemini_wins_as_b]
        ]
        chi2_gemini, p_gemini, dof, expected_freq = chi2_contingency(contingency_table)

        # Per-judge analysis
        by_judge = defaultdict(lambda: {"a_wins": 0, "b_wins": 0, "total": 0})
        for j in judgments:
            judge = j['judge_model']
            by_judge[judge]["total"] += 1
            if j['winner'] == 'A':
                by_judge[judge]["a_wins"] += 1
            elif j['winner'] == 'B':
                by_judge[judge]["b_wins"] += 1

        judge_biases = {}
        for judge, counts in by_judge.items():
            a_rate = counts["a_wins"] / counts["total"] if counts["total"] > 0 else 0
            judge_biases[judge] = {
                "a_win_rate": a_rate,
                "b_win_rate": counts["b_wins"] / counts["total"] if counts["total"] > 0 else 0,
                "preference": "A" if a_rate > 0.55 else ("B" if a_rate < 0.45 else "neutral")
            }

        return PositionBiasResult(
            # Overall position bias
            overall_a_win_rate=a_wins / (a_wins + b_wins) if (a_wins + b_wins) > 0 else 0,
            overall_b_win_rate=b_wins / (a_wins + b_wins) if (a_wins + b_wins) > 0 else 0,
            overall_chi_squared=chi2_overall,
            overall_p_value=p_overall,
            overall_significant=p_overall < 0.05,

            # Gemini-specific position bias
            gemini_win_rate_as_a=gemini_win_rate_as_a,
            gemini_win_rate_as_b=gemini_win_rate_as_b,
            gemini_position_chi_squared=chi2_gemini,
            gemini_position_p_value=p_gemini,
            gemini_position_significant=p_gemini < 0.05,

            # Per-judge breakdown
            per_judge_bias=judge_biases,

            # Summary
            position_bias_detected=(p_overall < 0.05 or p_gemini < 0.05),
            recommendation=self._generate_recommendation(
                p_overall, p_gemini, gemini_win_rate_as_a, gemini_win_rate_as_b
            )
        )

    def _generate_recommendation(
        self,
        p_overall: float,
        p_gemini: float,
        win_rate_a: float,
        win_rate_b: float
    ) -> str:
        """Generate recommendation based on bias analysis"""
        if p_overall < 0.05:
            if win_rate_a > win_rate_b:
                return "Significant position bias detected favoring position A. Consider weighting results."
            else:
                return "Significant position bias detected favoring position B. Consider weighting results."

        if p_gemini < 0.05:
            diff = abs(win_rate_a - win_rate_b)
            if diff > 0.1:
                return f"Gemini's win rate varies by position ({win_rate_a:.1%} as A, {win_rate_b:.1%} as B). Results may need adjustment."

        return "No significant position bias detected."
```

### 2.11 Missing Components: Regional Variants and Multi-Recipient Analysis

```python
class RegionalVariantAnalyzer:
    """Analyze model performance on regional English variants"""

    async def analyze_regional_performance(
        self,
        storage: StorageManager
    ) -> RegionalAnalysisResult:
        """Analyze how models adapt to regional English contexts"""

        # Win rates by recipient English variant
        variants = ["en-US", "en-GB", "en-AU", "non-native"]

        results_by_variant = {}
        for variant in variants:
            comparisons = await storage.fetch_all("""
                SELECT c.final_winner, c.gemini_model, c.competitor_model
                FROM comparisons c
                JOIN prompts p ON c.prompt_id = p.prompt_id
                WHERE p.recipient_english_variant = ?
            """, (variant,))

            if len(comparisons) >= 10:
                gemini_wins = sum(1 for c in comparisons if c['final_winner'] == 'gemini')
                win_rate = gemini_wins / len(comparisons)
                ci_lower, ci_upper = self._wilson_ci(gemini_wins, len(comparisons))

                results_by_variant[variant] = RegionalWinRate(
                    variant=variant,
                    total=len(comparisons),
                    gemini_wins=gemini_wins,
                    win_rate=win_rate,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper
                )

        # Cross-regional comparison
        if len(results_by_variant) >= 2:
            chi2, p_value = self._compare_variants(results_by_variant)
        else:
            chi2, p_value = None, None

        return RegionalAnalysisResult(
            by_variant=results_by_variant,
            chi_squared=chi2,
            p_value=p_value,
            significant_difference=p_value < 0.05 if p_value else False,
            best_variant=max(results_by_variant.keys(), key=lambda v: results_by_variant[v].win_rate) if results_by_variant else None,
            worst_variant=min(results_by_variant.keys(), key=lambda v: results_by_variant[v].win_rate) if results_by_variant else None
        )


class MultiRecipientAnalyzer:
    """Analyze performance on multi-recipient (CC) scenarios"""

    async def analyze_cc_scenarios(
        self,
        storage: StorageManager
    ) -> CCAnalysisResult:
        """Analyze how models handle multiple-audience scenarios"""

        # Prompts with CC recipients
        cc_comparisons = await storage.fetch_all("""
            SELECT c.*, p.cc_recipients_json
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            WHERE p.cc_recipients_json IS NOT NULL
            AND json_array_length(p.cc_recipients_json) > 0
        """)

        # Prompts without CC recipients
        single_comparisons = await storage.fetch_all("""
            SELECT c.*
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            WHERE p.cc_recipients_json IS NULL
            OR json_array_length(p.cc_recipients_json) = 0
        """)

        # Compare win rates
        cc_gemini_wins = sum(1 for c in cc_comparisons if c['final_winner'] == 'gemini')
        single_gemini_wins = sum(1 for c in single_comparisons if c['final_winner'] == 'gemini')

        cc_win_rate = cc_gemini_wins / len(cc_comparisons) if cc_comparisons else 0
        single_win_rate = single_gemini_wins / len(single_comparisons) if single_comparisons else 0

        # Statistical comparison
        from scipy.stats import chi2_contingency
        contingency = [
            [cc_gemini_wins, len(cc_comparisons) - cc_gemini_wins],
            [single_gemini_wins, len(single_comparisons) - single_gemini_wins]
        ]
        chi2, p_value, _, _ = chi2_contingency(contingency) if cc_comparisons and single_comparisons else (None, None, None, None)

        return CCAnalysisResult(
            cc_total=len(cc_comparisons),
            cc_win_rate=cc_win_rate,
            single_total=len(single_comparisons),
            single_win_rate=single_win_rate,
            difference=cc_win_rate - single_win_rate,
            chi_squared=chi2,
            p_value=p_value,
            significant=p_value < 0.05 if p_value else False,
            interpretation=self._interpret_results(cc_win_rate, single_win_rate, p_value)
        )

    def _interpret_results(
        self,
        cc_rate: float,
        single_rate: float,
        p_value: float
    ) -> str:
        """Interpret CC analysis results"""
        if p_value is None:
            return "Insufficient data for analysis"

        diff = cc_rate - single_rate

        if p_value >= 0.05:
            return "No significant difference between CC and single-recipient scenarios"

        if diff > 0:
            return f"Gemini performs better in CC scenarios (+{diff:.1%})"
        else:
            return f"Gemini performs worse in CC scenarios ({diff:.1%})"
```

### 2.12 Auto-Generated README and CSV Export

```python
class ResultsManager:
    """Manages results directory with auto-generated documentation"""

    def create_run_directory(self, config: EvalConfig) -> Path:
        """Create a new timestamped run directory with auto-generated README"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = self.base_dir / f"eval_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories...
        # (same as original)

        # Auto-generate README
        readme_content = self._generate_readme(config, timestamp)
        (run_dir / "README.md").write_text(readme_content)

        return run_dir

    def _generate_readme(self, config: EvalConfig, timestamp: str) -> str:
        """Generate README for the run directory"""
        return f"""# Evaluation Run: {timestamp}

## Configuration

- **Preset**: {config.name}
- **Prompts**: {config.num_prompts}
- **Random Seed**: {config.random_seed}

### Model Pairs

| Gemini Model | Competitor |
|--------------|------------|
{self._format_model_pairs_table(config.model_pairs)}

### Judge Configuration

- **Judge Models**: {', '.join(config.judge_models)}
- **Votes per Judge**: {config.votes_per_judge}
- **Judge Personas**: {', '.join(config.judge_personas)}

## Directory Structure

```
{self._format_directory_structure()}
```

## Files

- `config.json`: Full configuration (machine-readable)
- `config_summary.txt`: Human-readable configuration
- `results.db`: SQLite database with all results
- `results_summary.csv`: Quick CSV export of key metrics
- `reports/report.pdf`: Final PDF report (after completion)

## Resume

To resume an interrupted run:

```bash
./eval resume {timestamp}
```

---

*Generated automatically by Gemini Writing Evaluation Framework*
"""

    def export_to_csv(self, run_dir: Path) -> Path:
        """Export results to CSV for easy analysis"""
        storage = StorageManager(run_dir / "results.db")

        # Export main comparison results
        comparisons_path = run_dir / "results_summary.csv"
        comparisons = asyncio.run(storage.fetch_all("""
            SELECT
                c.comparison_id,
                c.prompt_id,
                p.occupation_title,
                p.job_zone,
                p.writing_category,
                p.formality_level,
                p.channel,
                p.audience_size,
                c.gemini_model,
                c.competitor_model,
                c.final_winner,
                c.judge_agreement_count,
                c.gemini_auto_loss,
                c.competitor_auto_loss
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
        """))

        import csv
        with open(comparisons_path, 'w', newline='') as f:
            if comparisons:
                writer = csv.DictWriter(f, fieldnames=comparisons[0].keys())
                writer.writeheader()
                writer.writerows(comparisons)

        # Export detailed win rates
        win_rates_path = run_dir / "win_rates_by_dimension.csv"
        # (similar export for dimensional analysis)

        return comparisons_path
```

---

## Part 3: Summary of Required Changes

### Critical Fixes (Must Address)

1. **Remove hardcoded writing categories** - Use O*NET reference data instead
2. **Implement Phase 1 of prompt generation** - Offline LLM template generation
3. **Fix channel handling** - Don't force into predefined categories
4. **Add Flash-tier model pairs** to all preset configurations
5. **Fix vote aggregation** - Properly handle persona-level aggregation
6. **Complete database schema** - Add missing fields for all dimensions
7. **Implement effect size calculations** - Cohen's h and odds ratios
8. **Add time estimation** - Calculate based on rate limits

### Important Additions (Should Address)

1. **Instruction compliance checker** - Verify constraint following
2. **Ambiguity behavior tracking** - Track model handling patterns
3. **Position bias analysis with Gemini context** - Not just A/B preference
4. **Regional variant analysis** - en-GB, en-AU, non-native performance
5. **Multi-recipient (CC) analysis** - Performance on multi-audience scenarios
6. **Auto-generated README** - For each run directory
7. **CSV export functionality** - For easy external analysis

### Recommended Improvements

1. **More detailed recipient persona generation** - Context-specific evaluation
2. **Cross-run comparison implementation** - Complete the stubbed command
3. **Format bias detection with statistical tests**
4. **Tone matching evaluation mechanism**

---

*End of Critique for Draft Plan 3*
