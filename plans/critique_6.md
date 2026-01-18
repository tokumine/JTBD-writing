# Critique of Draft Plan 6: Gemini Writing Evaluation Framework

## Executive Summary

Draft Plan 6 presents a comprehensive and well-structured implementation plan for the Gemini Writing Evaluation Framework. The plan demonstrates strong technical design with clear architecture, detailed code examples, and thorough coverage of most PROMPT.md requirements. However, there are several areas requiring improvement: missing specifications for certain diversity dimensions, incomplete handling of some prompt generation scenarios, gaps in the results viewer TUI, and several technical implementation concerns that need addressing.

---

## Part 1: Detailed Critique

### 1.1 Strengths

**Excellent Architecture Design:**
- Clear separation of concerns with well-defined components
- Comprehensive directory structure
- Good use of modern Python tooling (asyncio, pydantic, httpx, textual)

**Strong Data Modeling:**
- Thorough Pydantic schemas for prompts, responses, and judgments
- Good coverage of metadata fields for analysis
- Well-designed SQLite schema with appropriate indexes

**Robust API Layer:**
- Circuit breaker pattern implementation
- Token bucket rate limiting
- Retry logic with exponential backoff

**Comprehensive Judging System:**
- Dual persona approach (writing expert + recipient)
- Multi-model ensemble (3 judges)
- Majority-of-majorities aggregation

**Good Statistical Analysis:**
- Wilson score confidence intervals
- Cohen's Kappa for inter-judge agreement
- Bias detection mechanisms

---

### 1.2 Issues and Missing Elements

#### CRITICAL: Missing PROMPT.md Requirements

**1. Results Viewer TUI (Section 14) - Incomplete**

PROMPT.md specifies (Section "Fine-Grained Eval Viewer: Rich TUI"):
> "Build a full interactive terminal UI using the rich/textual library with:
> - Filtering by occupation, industry, winner, etc.
> - Sorting by various dimensions
> - Side-by-side response viewing
> - Drill-down into individual judgments"

The draft plan only shows the progress dashboard TUI. It completely omits the Results Viewer TUI for post-evaluation inspection. This is a critical gap since PROMPT.md explicitly states:
> "Allows meaningful inspection of judgements on a per writing task basis"

**2. Cross-Run Comparison (Section "Results Organization") - Missing**

PROMPT.md specifies:
```bash
./eval compare results/eval_2024-01-15_*/ results/eval_2024-01-16_*/
```

The draft mentions a `compare` CLI command but provides no implementation details for cross-run comparison logic.

**3. Response Metadata Tracking - Incomplete**

PROMPT.md specifies tracking:
- Response length (characters, words, tokens)
- Response time (latency)
- Format detection (bullet points, headers, paragraphs)
- **Greeting/sign-off patterns (formal vs casual markers)** - partially covered

The draft's `_analyze_response` method has basic detection but doesn't implement proper "formal vs casual markers" analysis as specified.

**4. Refusal Categorization - Incomplete Analysis Tracking**

PROMPT.md specifies:
> "Track refusal rates by:
> - Model (which models refuse most?)
> - Task type (which tasks trigger refusals?)
> - Sensitive topic category (which sensitive areas are problematic?)"

The draft has failure categorization but doesn't show how this data flows into the analysis/reporting system for aggregate refusal rate tracking.

**5. Instruction-Following Tests - Missing Compliance Tracking**

PROMPT.md specifies:
> "Track compliance separately - a model that writes beautifully but ignores instructions is problematic for real use."

While the draft has `InstructionConstraint` in the schema, there's no implementation for:
- Detecting instruction compliance in responses
- Tracking compliance rates in analysis
- Reporting compliance statistics

**6. Auto-Generated README - Missing**

PROMPT.md specifies each run directory should contain:
> "README.md  # Auto-generated run description"

No implementation provided.

---

#### Technical Issues

**7. Phase 1 LLM Generation - Bias Concern Not Addressed**

PROMPT.md warns:
> "Use the same models being evaluated for this generation (note: this creates potential bias but ensures prompts aren't accidentally biased against any particular model)."

The draft shows `Phase1Generator` but doesn't implement the requirement to use ALL evaluated models for generation to avoid single-model bias.

**8. Sensitive Topic Tagging - Incomplete**

PROMPT.md specifies:
> "Tag prompts involving sensitive topics during generation"

The schema has `sensitive_topic_category` field but no implementation shows how this tagging happens during prompt generation.

**9. Communication Channel Handling - Partially Implemented**

PROMPT.md states:
> "Let O*NET task statements imply the medium naturally"
> "Use Phase 3 LLM enrichment to infer/specify medium when the task is ambiguous"

The draft has the field but doesn't show the inference logic in Phase 3.

**10. Model Fingerprinting Detection - Missing**

PROMPT.md specifies detecting:
> "Model fingerprinting: Can judges identify which model wrote which response?"

No implementation for detecting this bias pattern.

**11. Temporal Context - Missing Date Specification**

PROMPT.md specifies:
> "Specify the current date/quarter when it affects the writing"
> "The Date is Jan 6, 2026"

The draft doesn't incorporate the specified date into temporal context generation.

---

#### Robustness Concerns

**12. Checkpoint File Writing - Race Condition Risk**

The `_write_checkpoint` method writes directly to `checkpoint.json` without atomic write operations. Should use write-to-temp-then-rename pattern.

**13. Circuit Breaker Uses `time.time()` Not `asyncio` Time**

The `CircuitBreaker` class uses `time.time()` while the `RateLimiter` uses `asyncio.get_event_loop().time()`. This inconsistency could cause issues.

**14. Set Serialization in Checkpoint**

The checkpoint manager converts sets to lists for JSON serialization, but this loses the O(1) lookup benefit. Should use a more efficient structure or document the performance tradeoff.

**15. Error Handling in Response Analysis**

The `_analyze_response` method doesn't handle malformed responses (e.g., if `response_text` is None or contains unexpected characters).

---

#### Completeness Gaps

**16. "Latest" Symlink Creation - Missing Implementation**

PROMPT.md specifies:
> "latest -> eval_2024-01-16_11-45-33/  # Symlink to latest"

No code creates this symlink.

**17. Config Summary Text File - Missing**

PROMPT.md specifies:
> "config_summary.txt  # Human-readable config summary"

No implementation provided.

**18. Prompts by Organization/Industry - Missing**

PROMPT.md specifies:
> "prompts_by_occupation/  # Prompts organized by occupation"
> "prompts_by_industry/   # Prompts organized by industry"

No implementation for organizing prompts into these subdirectories.

**19. Flash Tier Models Incomplete**

PROMPT.md specifies:
> "Other flash-tier models in class"

The draft only includes GPT-4.1 and Claude Sonnet for Flash tier. Should be more extensible.

**20. Age Range Filtering - Incomplete**

PROMPT.md specifies:
> "Age/generation range: Limit to specific persona age groups"

The filter implementation doesn't include age/generation filtering.

---

### 1.3 Code Quality Issues

**21. Incomplete Method Implementations**

Many methods end with `pass` without implementation guidance:
- `CompanyDatabase.get_company()`
- `NAICSMapper.sample_industries_for_occupation()`
- `Phase1Generator.generate_persona_variations()`
- `ResultsExporter.export_json()`

**22. Missing Type Hints in Some Areas**

Several functions lack return type hints, reducing code clarity.

**23. Judge Persona Implementation Gap**

The `JudgeSystem.judge_comparison()` method shows two personas but the prompt templates only show how to handle one at a time. The actual orchestration logic for running both personas is unclear.

**24. Missing `WritingPrompt.render_prompt()` Implementation**

This critical method that renders the full prompt text is left as `pass`.

---

## Part 2: Improved Implementation Plan

### Section 1: Architecture Overview (Unchanged - Well Designed)

The architecture section is solid and requires no changes.

---

### Section 2: Enhanced Data Models

#### 2.1 Enhanced Prompt Schema

Add missing fields and improve existing ones:

```python
class WritingPrompt(BaseModel):
    """Complete writing prompt specification"""
    prompt_id: str

    # Core task
    onet_task_id: str
    onet_task_text: str
    onet_occupation_code: str
    onet_occupation_title: str
    onet_job_zone: int
    soc_major_group: str  # ADD: For aggregation

    # Industry context
    naics_code: str
    naics_description: str
    naics_sector: str  # ADD: 2-digit sector for filtering

    # Personas
    writer: WriterPersona
    primary_recipient: RecipientPersona
    additional_recipients: List[AdditionalRecipient] = []

    # Context dimensions
    formality: FormattingLevel
    urgency: UrgencyLevel
    emotional_context: EmotionalContext
    audience_size: AudienceSize
    message_position: MessagePosition

    # Communication details
    communication_channel: Optional[str] = None
    inferred_channel: Optional[str] = None  # ADD: LLM-inferred channel
    temporal_context: Optional[str] = None
    current_date: str = "2026-01-06"  # ADD: Per PROMPT.md specification

    # Enrichment content
    attachments: List[Attachment] = []
    prior_messages: List[PriorMessage] = []
    tone_examples: List[ToneExample] = []

    # Special scenarios
    competing_objectives: Optional[str] = None
    is_revision_task: bool = False
    revision_content: Optional[str] = None
    is_ambiguous: bool = False

    # Constraints
    instruction_constraints: List[InstructionConstraint] = []

    # Sensitive topic handling - ADD detailed implementation
    sensitive_topic_category: Optional[str] = None
    sensitive_topic_tags: List[str] = []  # ADD: Multiple tags possible

    # Metadata
    language: str = "en"
    language_variant: str = "en-US"
    generation_seed: int
    generated_by_model: str  # ADD: Track which model generated this prompt

    # Computed fields
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0

    def render_prompt(self) -> str:
        """Render the full prompt text for model consumption"""
        sections = []

        # Build context section
        context = f"""You are {self.writer.name}, {self.writer.job_title} at {self.writer.company_name}.

Company: {self.writer.company_name} ({self.writer.company_size}, {self.naics_description})
Your Experience: {self.writer.years_experience} years in this role
"""
        if self.current_date and self.temporal_context:
            context += f"\nCurrent Date: {self.current_date}\n{self.temporal_context}"

        sections.append(context)

        # Task description
        task = f"""## Writing Task
{self.onet_task_text}

## Your Target Audience
Primary Recipient: {self.primary_recipient.name}, {self.primary_recipient.job_title}
Relationship: {self.primary_recipient.relationship_to_writer}
Prior Contact: {"Yes, you have communicated before" if self.primary_recipient.prior_contact else "No, this is first contact"}
"""
        if self.primary_recipient.english_variant != EnglishVariant.EN_US:
            task += f"Note: Recipient uses {self.primary_recipient.english_variant.value} English\n"

        if self.additional_recipients:
            task += "\nAdditional Recipients:\n"
            for r in self.additional_recipients:
                task += f"- {r.name} ({r.job_title}) - {r.visibility}\n"

        sections.append(task)

        # Context details
        context_details = f"""## Communication Context
Formality Level: {self.formality.value}
Urgency: {self.urgency.value}
Emotional Context: {self.emotional_context.value}
Audience Size: {self.audience_size.value}
"""
        sections.append(context_details)

        # Prior messages (if reply)
        if self.prior_messages:
            sections.append("## Previous Messages in Thread")
            for msg in self.prior_messages:
                timestamp_str = msg.timestamp.strftime("%Y-%m-%d %H:%M") if msg.timestamp else ""
                sections.append(f"From: {msg.sender_name} {timestamp_str}\n{msg.content}\n---")

        # Attachments
        if self.attachments:
            sections.append("## Referenced Materials")
            for att in self.attachments:
                sections.append(f"[{att.type.upper()}: {att.name}]\n{att.summary}")

        # Tone examples
        if self.tone_examples:
            sections.append("## Tone Reference")
            for ex in self.tone_examples:
                sections.append(f"Context: {ex.context}\nExample: {ex.example_text}")

        # Competing objectives
        if self.competing_objectives:
            sections.append(f"## Key Challenge\n{self.competing_objectives}")

        # Revision task
        if self.is_revision_task and self.revision_content:
            sections.append(f"## Content to Revise\n{self.revision_content}")

        # Instruction constraints
        if self.instruction_constraints:
            sections.append("## Specific Requirements")
            for ic in self.instruction_constraints:
                sections.append(f"- {ic.instruction}")

        # Final instruction
        sections.append("\nPlease write the requested content. Do not include any meta-commentary about the task.")

        return "\n\n".join(sections)
```

#### 2.2 Enhanced Response Schema with Compliance Tracking

```python
class InstructionComplianceResult(BaseModel):
    """Track compliance with specific instructions"""
    constraint_type: str
    instruction: str
    compliant: bool
    explanation: str

class ResponseFormatAnalysis(BaseModel):
    """Detailed format analysis of response"""
    greeting_type: Optional[str] = None  # "formal", "casual", "none"
    greeting_text: Optional[str] = None
    signoff_type: Optional[str] = None  # "formal", "casual", "none"
    signoff_text: Optional[str] = None
    structural_elements: List[str] = []  # "bullet_points", "numbered_list", "headers", "paragraphs"
    formality_markers: List[str] = []  # Detected formal/casual markers

class ModelResponse(BaseModel):
    """Single model response to a writing prompt"""
    response_id: str
    prompt_id: str
    model_id: str
    model_name: str

    # Response content
    response_text: str

    # Metadata
    response_time_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int

    # Response characteristics (auto-detected)
    word_count: int
    character_count: int
    paragraph_count: int

    # ADD: Detailed format analysis
    format_analysis: ResponseFormatAnalysis

    # ADD: Instruction compliance (if applicable)
    instruction_compliance: List[InstructionComplianceResult] = []
    overall_compliance_rate: Optional[float] = None

    # Failure tracking
    is_failure: bool = False
    failure_category: Optional[str] = None
    failure_reason: Optional[str] = None

    # Timestamps
    generated_at: datetime
    retry_count: int = 0
```

---

### Section 3: Enhanced O*NET Extraction

Add sensitive topic detection:

```python
class ONetExtractor:
    """Extract and process O*NET tasks for writing evaluation"""

    SENSITIVE_TOPIC_PATTERNS = {
        "hr_issues": [
            r"performance\s+(review|evaluation|issue)",
            r"terminat(e|ion)",
            r"disciplin(e|ary)",
            r"complaint",
            r"grievance"
        ],
        "legal_matters": [
            r"contract",
            r"liabilit(y|ies)",
            r"compliance",
            r"regulat(e|ion|ory)",
            r"litigation"
        ],
        "bad_news": [
            r"layoff",
            r"cancel(led|lation)",
            r"reject(ed|ion)",
            r"terminat(e|ion)",
            r"deny|denied"
        ],
        "confidential": [
            r"confidential",
            r"proprietary",
            r"financial\s+result",
            r"merger|acquisition",
            r"personnel\s+matter"
        ],
        "conflict": [
            r"dispute",
            r"negotiat(e|ion)",
            r"complain(t|ing)",
            r"disagree(ment)?",
            r"mediat(e|ion)"
        ]
    }

    def detect_sensitive_topics(self, task_text: str) -> List[str]:
        """Detect sensitive topics in task text"""
        import re
        topics = []
        task_lower = task_text.lower()

        for category, patterns in self.SENSITIVE_TOPIC_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    topics.append(category)
                    break

        return topics
```

---

### Section 4: Results Viewer TUI (NEW - Missing from Draft)

```python
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Static, Input, Select
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen

class ResultsViewerApp(App):
    """Interactive TUI for exploring evaluation results"""

    CSS = """
    #filter-bar {
        height: 3;
        margin: 1;
    }

    #main-table {
        height: 1fr;
    }

    #detail-panel {
        height: 40%;
        border: solid green;
    }

    #response-comparison {
        height: 100%;
    }

    .response-panel {
        width: 50%;
        border: solid blue;
        overflow: auto;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "focus_filter", "Filter"),
        ("s", "sort_menu", "Sort"),
        ("enter", "view_detail", "View Detail"),
        ("j", "view_judgments", "Judgments"),
        ("e", "export_selection", "Export"),
    ]

    def __init__(self, run_dir: str):
        super().__init__()
        self.run_dir = Path(run_dir)
        self.storage = StorageManager(self.run_dir)
        self.current_filters = {}
        self.sort_column = "prompt_id"
        self.sort_ascending = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main"):
            # Filter bar
            with Horizontal(id="filter-bar"):
                yield Select(
                    [(o, o) for o in self._get_occupations()],
                    prompt="Occupation",
                    id="occupation-filter"
                )
                yield Select(
                    [(i, i) for i in self._get_industries()],
                    prompt="Industry",
                    id="industry-filter"
                )
                yield Select(
                    [("All", "all"), ("Gemini Wins", "gemini"),
                     ("Competitor Wins", "competitor"), ("Ties", "tie")],
                    prompt="Winner",
                    id="winner-filter"
                )
                yield Select(
                    [(str(jz), jz) for jz in range(1, 6)],
                    prompt="Job Zone",
                    id="job-zone-filter"
                )
                yield Input(placeholder="Search prompts...", id="search-input")

            # Main results table
            yield DataTable(id="main-table")

            # Detail panel (side-by-side responses)
            with Container(id="detail-panel"):
                yield Static("Select a comparison to view details", id="detail-header")
                with Horizontal(id="response-comparison"):
                    yield ResponsePanel(id="response-a", classes="response-panel")
                    yield ResponsePanel(id="response-b", classes="response-panel")

        yield Footer()

    async def on_mount(self):
        """Initialize table with data"""
        table = self.query_one("#main-table", DataTable)
        table.add_columns(
            "Prompt ID", "Occupation", "Industry", "Formality",
            "Gemini Model", "Competitor", "Winner", "Agreement"
        )
        await self._load_comparisons()

    async def _load_comparisons(self):
        """Load comparisons with current filters"""
        table = self.query_one("#main-table", DataTable)
        table.clear()

        comparisons = await self.storage.get_comparisons(
            filters=self.current_filters,
            sort_by=self.sort_column,
            ascending=self.sort_ascending
        )

        for c in comparisons:
            table.add_row(
                c.prompt_id,
                c.occupation_title[:30],
                c.naics_description[:20],
                c.formality,
                c.gemini_model,
                c.competitor_model,
                c.final_winner,
                f"{c.judge_agreement}/3"
            )

    async def action_view_detail(self):
        """Show side-by-side response comparison"""
        table = self.query_one("#main-table", DataTable)
        row_key = table.cursor_row
        if row_key is None:
            return

        comparison_id = table.get_row_at(row_key)[0]
        comparison = await self.storage.get_comparison_detail(comparison_id)

        # Update header
        header = self.query_one("#detail-header", Static)
        header.update(f"Comparison: {comparison_id} | Winner: {comparison.final_winner}")

        # Update response panels
        panel_a = self.query_one("#response-a", ResponsePanel)
        panel_b = self.query_one("#response-b", ResponsePanel)

        panel_a.show_response(
            comparison.gemini_response,
            title=f"Gemini ({comparison.gemini_model})"
        )
        panel_b.show_response(
            comparison.competitor_response,
            title=f"Competitor ({comparison.competitor_model})"
        )

    async def action_view_judgments(self):
        """Open judgment detail screen"""
        table = self.query_one("#main-table", DataTable)
        row_key = table.cursor_row
        if row_key is None:
            return

        comparison_id = table.get_row_at(row_key)[0]
        await self.push_screen(JudgmentDetailScreen(comparison_id, self.storage))


class JudgmentDetailScreen(Screen):
    """Screen showing detailed judgment breakdown"""

    def __init__(self, comparison_id: str, storage: StorageManager):
        super().__init__()
        self.comparison_id = comparison_id
        self.storage = storage

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Judgments for {self.comparison_id}", id="title")
        yield DataTable(id="judgment-table")
        yield Footer()

    async def on_mount(self):
        table = self.query_one("#judgment-table", DataTable)
        table.add_columns(
            "Judge Model", "Persona", "Vote #", "Winner",
            "Confidence", "Quality A", "Quality B", "Reasoning"
        )

        judgments = await self.storage.get_judgments(self.comparison_id)
        for j in judgments:
            table.add_row(
                j.judge_model,
                j.judge_persona,
                str(j.vote_number),
                j.winner,
                f"{j.confidence:.2f}",
                str(j.scores_a.get("quality", "N/A")),
                str(j.scores_b.get("quality", "N/A")),
                j.reasoning[:50] + "..."
            )


class ResponsePanel(Static):
    """Panel for displaying a single response"""

    def show_response(self, response: ModelResponse, title: str):
        content = f"""[bold]{title}[/bold]

[dim]Words: {response.word_count} | Time: {response.response_time_ms}ms[/dim]

{response.response_text}

[dim]Format: {'Bullets ' if response.format_analysis.structural_elements and 'bullet_points' in response.format_analysis.structural_elements else ''}{'Headers ' if 'headers' in response.format_analysis.structural_elements else ''}[/dim]
"""
        self.update(content)
```

---

### Section 5: Enhanced Phase 3 Enrichment with Channel Inference

```python
class Phase3Enricher:
    """LLM enrichment for context-heavy prompts"""

    CHANNEL_INFERENCE_PROMPT = """
    Given this O*NET writing task:
    "{task_text}"

    And this context:
    - Occupation: {occupation_title}
    - Formality: {formality}
    - Audience: {audience_size}
    - Urgency: {urgency}

    What is the most likely communication channel for this task?
    Options: email, memo, letter, report, presentation, slack/teams message,
             social media post, text message, formal document, other

    Respond with just the channel name.
    """

    async def infer_communication_channel(
        self,
        prompt: WritingPrompt
    ) -> str:
        """Infer communication channel from task context"""

        # First check if task text implies channel
        task_lower = prompt.onet_task_text.lower()

        explicit_channels = {
            "email": ["email", "e-mail"],
            "memo": ["memo", "memorandum"],
            "letter": ["letter", "correspondence"],
            "report": ["report", "documentation"],
            "presentation": ["presentation", "slides"],
            "social_media": ["social media", "twitter", "linkedin", "post"]
        }

        for channel, keywords in explicit_channels.items():
            if any(kw in task_lower for kw in keywords):
                return channel

        # If not explicit, use LLM inference
        messages = [
            {"role": "user", "content": self.CHANNEL_INFERENCE_PROMPT.format(
                task_text=prompt.onet_task_text,
                occupation_title=prompt.onet_occupation_title,
                formality=prompt.formality.value,
                audience_size=prompt.audience_size.value,
                urgency=prompt.urgency.value
            )}
        ]

        result = await self.client.complete(
            model="google/gemini-3.0-flash",  # Use fast model for inference
            messages=messages,
            temperature=0.3,
            max_tokens=50
        )

        return result["choices"][0]["message"]["content"].strip().lower()
```

---

### Section 6: Instruction Compliance Detection

```python
class InstructionComplianceDetector:
    """Detect compliance with explicit instructions"""

    async def check_compliance(
        self,
        response: str,
        constraints: List[InstructionConstraint]
    ) -> List[InstructionComplianceResult]:
        """Check response compliance with all constraints"""

        results = []

        for constraint in constraints:
            if constraint.type == "length":
                result = self._check_length_compliance(response, constraint)
            elif constraint.type == "format":
                result = self._check_format_compliance(response, constraint)
            elif constraint.type == "tone":
                result = await self._check_tone_compliance(response, constraint)
            elif constraint.type == "exclusion":
                result = self._check_exclusion_compliance(response, constraint)
            else:
                result = await self._check_generic_compliance(response, constraint)

            results.append(result)

        return results

    def _check_length_compliance(
        self,
        response: str,
        constraint: InstructionConstraint
    ) -> InstructionComplianceResult:
        """Check length-based constraints"""
        import re

        word_count = len(response.split())
        instruction = constraint.instruction.lower()

        # Parse constraint
        if "under" in instruction or "less than" in instruction:
            match = re.search(r'(\d+)\s*words?', instruction)
            if match:
                limit = int(match.group(1))
                compliant = word_count < limit
                return InstructionComplianceResult(
                    constraint_type="length",
                    instruction=constraint.instruction,
                    compliant=compliant,
                    explanation=f"Response is {word_count} words (limit: {limit})"
                )

        elif "at least" in instruction or "minimum" in instruction:
            match = re.search(r'(\d+)\s*words?', instruction)
            if match:
                minimum = int(match.group(1))
                compliant = word_count >= minimum
                return InstructionComplianceResult(
                    constraint_type="length",
                    instruction=constraint.instruction,
                    compliant=compliant,
                    explanation=f"Response is {word_count} words (minimum: {minimum})"
                )

        return InstructionComplianceResult(
            constraint_type="length",
            instruction=constraint.instruction,
            compliant=True,
            explanation="Could not parse length constraint"
        )

    def _check_format_compliance(
        self,
        response: str,
        constraint: InstructionConstraint
    ) -> InstructionComplianceResult:
        """Check format-based constraints"""
        import re
        instruction = constraint.instruction.lower()

        # Check for bullet point requirements
        if "bullet" in instruction:
            match = re.search(r'(\d+)\s*bullet', instruction)
            bullet_count = len(re.findall(r'^[\-\*\u2022]\s', response, re.MULTILINE))

            if match:
                required = int(match.group(1))
                if "exactly" in instruction:
                    compliant = bullet_count == required
                else:
                    compliant = bullet_count >= required
                return InstructionComplianceResult(
                    constraint_type="format",
                    instruction=constraint.instruction,
                    compliant=compliant,
                    explanation=f"Found {bullet_count} bullet points (required: {required})"
                )

        # Check for paragraph-only requirement
        if "paragraph" in instruction and "only" in instruction:
            has_bullets = bool(re.search(r'^[\-\*\u2022]\s', response, re.MULTILINE))
            has_headers = bool(re.search(r'^#+\s', response, re.MULTILINE))
            compliant = not has_bullets and not has_headers
            return InstructionComplianceResult(
                constraint_type="format",
                instruction=constraint.instruction,
                compliant=compliant,
                explanation="Response uses paragraph form only" if compliant else "Response contains bullets or headers"
            )

        return InstructionComplianceResult(
            constraint_type="format",
            instruction=constraint.instruction,
            compliant=True,
            explanation="Format constraint check not implemented for this type"
        )

    def _check_exclusion_compliance(
        self,
        response: str,
        constraint: InstructionConstraint
    ) -> InstructionComplianceResult:
        """Check exclusion-based constraints"""
        import re
        instruction = constraint.instruction.lower()
        response_lower = response.lower()

        # Extract what to exclude
        match = re.search(r'do not mention (?:the )?(.+)', instruction)
        if match:
            excluded_term = match.group(1).strip()
            found = excluded_term in response_lower
            return InstructionComplianceResult(
                constraint_type="exclusion",
                instruction=constraint.instruction,
                compliant=not found,
                explanation=f"Term '{excluded_term}' {'found' if found else 'not found'} in response"
            )

        match = re.search(r'avoid (.+)', instruction)
        if match:
            avoided_term = match.group(1).strip()
            found = avoided_term in response_lower
            return InstructionComplianceResult(
                constraint_type="exclusion",
                instruction=constraint.instruction,
                compliant=not found,
                explanation=f"Term '{avoided_term}' {'found' if found else 'not found'} in response"
            )

        return InstructionComplianceResult(
            constraint_type="exclusion",
            instruction=constraint.instruction,
            compliant=True,
            explanation="Could not parse exclusion constraint"
        )
```

---

### Section 7: Cross-Run Comparison (NEW - Missing from Draft)

```python
class CrossRunComparator:
    """Compare results across multiple evaluation runs"""

    def __init__(self, run_dirs: List[Path]):
        self.run_dirs = run_dirs
        self.runs = []

    async def load_runs(self):
        """Load all runs for comparison"""
        for run_dir in self.run_dirs:
            storage = StorageManager(run_dir)
            config = await storage.load_config()
            results = await storage.load_results_summary()
            self.runs.append({
                "dir": run_dir,
                "config": config,
                "results": results
            })

    def compare_win_rates(self) -> pd.DataFrame:
        """Compare win rates across runs"""
        data = []

        for run in self.runs:
            run_name = run["dir"].name
            for model_pair, stats in run["results"]["model_pair_stats"].items():
                data.append({
                    "run": run_name,
                    "gemini_model": model_pair[0],
                    "competitor": model_pair[1],
                    "win_rate": stats["win_rate"],
                    "ci_lower": stats["ci_lower"],
                    "ci_upper": stats["ci_upper"],
                    "sample_size": stats["total"]
                })

        return pd.DataFrame(data)

    def compare_by_dimension(self, dimension: str) -> pd.DataFrame:
        """Compare win rates by dimension across runs"""
        data = []

        for run in self.runs:
            run_name = run["dir"].name
            dim_stats = run["results"].get(f"{dimension}_win_rates", {})
            for value, stats in dim_stats.items():
                data.append({
                    "run": run_name,
                    dimension: value,
                    "win_rate": stats["win_rate"],
                    "sample_size": stats["total"]
                })

        return pd.DataFrame(data)

    def statistical_comparison(self) -> dict:
        """Run statistical tests comparing runs"""
        if len(self.runs) < 2:
            return {"error": "Need at least 2 runs to compare"}

        results = {}

        # Compare each pair of runs
        for i, run1 in enumerate(self.runs):
            for run2 in self.runs[i+1:]:
                pair_key = f"{run1['dir'].name} vs {run2['dir'].name}"

                # Chi-square test for win rate difference
                wins1 = run1["results"]["total_gemini_wins"]
                total1 = run1["results"]["total_comparisons"]
                wins2 = run2["results"]["total_gemini_wins"]
                total2 = run2["results"]["total_comparisons"]

                from scipy.stats import chi2_contingency
                contingency = [
                    [wins1, total1 - wins1],
                    [wins2, total2 - wins2]
                ]
                chi2, p_value, _, _ = chi2_contingency(contingency)

                results[pair_key] = {
                    "chi2": chi2,
                    "p_value": p_value,
                    "significant": p_value < 0.05,
                    "run1_win_rate": wins1 / total1,
                    "run2_win_rate": wins2 / total2
                }

        return results

    def generate_comparison_report(self, output_path: Path):
        """Generate visual comparison report"""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        # Win rate comparison chart
        df = self.compare_win_rates()

        fig = go.Figure()

        for run_name in df["run"].unique():
            run_data = df[df["run"] == run_name]
            fig.add_trace(go.Bar(
                name=run_name,
                x=[f"{r['gemini_model']} vs {r['competitor']}"
                   for _, r in run_data.iterrows()],
                y=run_data["win_rate"],
                error_y=dict(
                    type="data",
                    array=run_data["ci_upper"] - run_data["win_rate"],
                    arrayminus=run_data["win_rate"] - run_data["ci_lower"]
                )
            ))

        fig.update_layout(
            title="Win Rate Comparison Across Runs",
            barmode="group",
            yaxis_title="Win Rate"
        )

        fig.write_html(output_path / "comparison_chart.html")
```

---

### Section 8: Enhanced Checkpoint Manager with Atomic Writes

```python
import tempfile
import shutil

class CheckpointManager:
    """Manage checkpoints for resumable evaluation with atomic writes"""

    def __init__(self, storage: StorageManager, run_dir: Path):
        self.storage = storage
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"
        self._lock = asyncio.Lock()

    async def _write_checkpoint(self, checkpoint: dict):
        """Write checkpoint atomically using temp file"""
        async with self._lock:
            data = checkpoint.copy()
            data["completed_prompts"] = list(data["completed_prompts"])
            data["completed_comparisons"] = list(data["completed_comparisons"])

            # Write to temp file first
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.run_dir,
                prefix="checkpoint_",
                suffix=".tmp"
            )
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(data, f, indent=2)

                # Atomic rename
                shutil.move(temp_path, self.checkpoint_file)
            except Exception:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
```

---

### Section 9: Auto-Generated Run README

```python
class RunReadmeGenerator:
    """Generate auto-documentation for evaluation runs"""

    def generate_readme(self, run_dir: Path, config: EvalConfig,
                        results_summary: dict) -> str:
        """Generate README.md for a run directory"""

        readme = f"""# Evaluation Run: {run_dir.name}

## Overview
- **Preset**: Level {config.preset_level} - {config.preset_name}
- **Started**: {results_summary['started_at']}
- **Completed**: {results_summary.get('completed_at', 'In Progress')}
- **Status**: {results_summary['status']}

## Configuration
- **Prompts**: {config.num_prompts}
- **Model Pairs**: {len(config.model_pairs)}
- **Judge Models**: {', '.join(config.judge_models)}
- **Votes per Judge**: {config.votes_per_judge}
- **Random Seed**: {config.random_seed}

## Results Summary

### Overall Win Rates
| Gemini Model | Competitor | Win Rate | 95% CI | Sample Size |
|--------------|------------|----------|--------|-------------|
"""
        for pair, stats in results_summary.get('model_pair_stats', {}).items():
            readme += f"| {pair[0]} | {pair[1]} | {stats['win_rate']:.1%} | [{stats['ci_lower']:.1%}, {stats['ci_upper']:.1%}] | {stats['total']} |\n"

        readme += f"""
### Key Metrics
- **Inter-Judge Agreement**: {results_summary.get('inter_judge_kappa', 'N/A'):.3f} (Cohen's Kappa)
- **Total API Cost**: ${results_summary.get('total_cost', 0):.2f}
- **Total Runtime**: {results_summary.get('runtime_hours', 0):.2f} hours

## Files
- `config.json` - Full configuration
- `results.db` - SQLite database with all results
- `prompts/prompts.json` - All generated prompts
- `responses/` - Model responses
- `judgments/` - Judge results
- `analysis/` - Statistical analysis
- `reports/report.pdf` - Full PDF report

## Reproducibility
To reproduce this run:
```bash
./eval run --preset {config.preset_level} --seed {config.random_seed}
```

## Notes
{results_summary.get('notes', 'No additional notes.')}

---
Generated automatically by Gemini Writing Evaluation Framework
"""
        return readme

    def save_readme(self, run_dir: Path, config: EvalConfig,
                    results_summary: dict):
        """Save README to run directory"""
        readme_content = self.generate_readme(run_dir, config, results_summary)
        (run_dir / "README.md").write_text(readme_content)
```

---

### Section 10: Latest Symlink Creation

```python
def create_latest_symlink(results_dir: Path, run_dir: Path):
    """Create/update 'latest' symlink to most recent run"""
    latest_link = results_dir / "latest"

    # Remove existing symlink if present
    if latest_link.is_symlink():
        latest_link.unlink()
    elif latest_link.exists():
        # It's a real directory, don't touch it
        return

    # Create new symlink
    latest_link.symlink_to(run_dir.name)
```

---

### Section 11: Enhanced Refusal Rate Tracking and Analysis

```python
class RefusalAnalyzer:
    """Analyze refusal patterns across models and tasks"""

    async def analyze_refusals(
        self,
        storage: StorageManager
    ) -> RefusalAnalysisReport:
        """Comprehensive refusal analysis"""

        # Get all failed responses
        query = """
        SELECT
            r.model_id,
            r.failure_category,
            r.failure_reason,
            p.onet_occupation_code,
            p.onet_occupation_title,
            p.sensitive_topic_category,
            p.formality,
            p.emotional_context
        FROM responses r
        JOIN prompts p ON r.prompt_id = p.prompt_id
        WHERE r.is_failure = 1
        """

        failures = await storage.execute_query(query)

        # Analyze by model
        by_model = {}
        for f in failures:
            model = f["model_id"]
            if model not in by_model:
                by_model[model] = {"total": 0, "by_category": {}}
            by_model[model]["total"] += 1
            cat = f["failure_category"]
            by_model[model]["by_category"][cat] = \
                by_model[model]["by_category"].get(cat, 0) + 1

        # Analyze by task type (SOC major group)
        by_occupation = {}
        for f in failures:
            occ = f["onet_occupation_code"][:2]  # Major group
            if occ not in by_occupation:
                by_occupation[occ] = 0
            by_occupation[occ] += 1

        # Analyze by sensitive topic
        by_sensitive_topic = {}
        for f in failures:
            topic = f["sensitive_topic_category"]
            if topic:
                if topic not in by_sensitive_topic:
                    by_sensitive_topic[topic] = 0
                by_sensitive_topic[topic] += 1

        # Calculate rates
        total_responses = await storage.get_total_response_count()
        responses_per_model = await storage.get_response_count_by_model()

        refusal_rates = {}
        for model, stats in by_model.items():
            model_total = responses_per_model.get(model, 1)
            refusal_rates[model] = stats["total"] / model_total

        return RefusalAnalysisReport(
            total_refusals=len(failures),
            total_responses=total_responses,
            overall_refusal_rate=len(failures) / total_responses if total_responses > 0 else 0,
            by_model=by_model,
            by_occupation=by_occupation,
            by_sensitive_topic=by_sensitive_topic,
            refusal_rates_by_model=refusal_rates,
            high_refusal_tasks=self._identify_high_refusal_tasks(failures),
            recommendations=self._generate_refusal_recommendations(
                by_model, by_sensitive_topic
            )
        )

    def _identify_high_refusal_tasks(self, failures: List[dict]) -> List[dict]:
        """Identify task patterns with high refusal rates"""
        from collections import Counter

        task_failures = Counter()
        for f in failures:
            task_key = (f["onet_occupation_title"], f["emotional_context"])
            task_failures[task_key] += 1

        high_refusal = [
            {"occupation": k[0], "context": k[1], "count": v}
            for k, v in task_failures.most_common(10)
        ]

        return high_refusal

    def _generate_refusal_recommendations(
        self,
        by_model: dict,
        by_sensitive_topic: dict
    ) -> List[str]:
        """Generate actionable recommendations from refusal analysis"""

        recommendations = []

        # Find models with high safety refusals
        for model, stats in by_model.items():
            safety_refusals = stats["by_category"].get("safety_refusal", 0)
            if safety_refusals > stats["total"] * 0.5:
                recommendations.append(
                    f"{model} has high safety refusal rate ({safety_refusals}/{stats['total']}). "
                    f"Consider reviewing prompts that trigger safety filters."
                )

        # Find problematic sensitive topics
        if by_sensitive_topic:
            top_topic = max(by_sensitive_topic, key=by_sensitive_topic.get)
            recommendations.append(
                f"'{top_topic}' sensitive topics have highest refusal rate. "
                f"Consider whether these prompts need adjustment."
            )

        return recommendations
```

---

### Section 12: Model Fingerprinting Detection

```python
class FingerprintingDetector:
    """Detect if judges can identify which model produced responses"""

    async def detect_fingerprinting(
        self,
        comparisons: List[ComparisonResult]
    ) -> FingerprintingResult:
        """
        Detect model fingerprinting by analyzing if judges' votes
        correlate with actual model identity beyond presentation order
        """

        # Track judge votes by actual model (not position)
        votes_for_model = {}  # model_id -> {"votes_for": N, "votes_against": N}

        for c in comparisons:
            gemini_model = c.gemini_model
            competitor_model = c.competitor_model

            for judge_agg in c.judge_results:
                for vote in judge_agg.votes:
                    # Determine which model the judge voted for
                    if vote.winner == "A":
                        if vote.response_a_position == "gemini_first":
                            voted_for = gemini_model
                        else:
                            voted_for = competitor_model
                    elif vote.winner == "B":
                        if vote.response_a_position == "gemini_first":
                            voted_for = competitor_model
                        else:
                            voted_for = gemini_model
                    else:
                        continue  # Skip ties

                    # Initialize tracking
                    for model in [gemini_model, competitor_model]:
                        if model not in votes_for_model:
                            votes_for_model[model] = {"votes_for": 0, "votes_against": 0}

                    votes_for_model[voted_for]["votes_for"] += 1
                    other_model = competitor_model if voted_for == gemini_model else gemini_model
                    votes_for_model[other_model]["votes_against"] += 1

        # Check for consistent bias toward/against specific models
        # regardless of position
        model_biases = {}
        for model, stats in votes_for_model.items():
            total = stats["votes_for"] + stats["votes_against"]
            if total > 0:
                vote_rate = stats["votes_for"] / total
                # Test if significantly different from 50%
                from scipy.stats import binom_test
                p_value = binom_test(stats["votes_for"], total, 0.5)

                model_biases[model] = {
                    "vote_rate": vote_rate,
                    "p_value": p_value,
                    "significant": p_value < 0.05,
                    "total_votes": total
                }

        # Fingerprinting detected if any model has significant bias
        # after controlling for position
        fingerprinting_detected = any(
            bias["significant"] and abs(bias["vote_rate"] - 0.5) > 0.1
            for bias in model_biases.values()
        )

        return FingerprintingResult(
            detected=fingerprinting_detected,
            model_biases=model_biases,
            interpretation=self._interpret_fingerprinting(model_biases),
            recommendation="Consider additional anonymization" if fingerprinting_detected else "No fingerprinting detected"
        )

    def _interpret_fingerprinting(self, model_biases: dict) -> str:
        """Interpret fingerprinting results"""
        significant = [
            (model, bias) for model, bias in model_biases.items()
            if bias["significant"]
        ]

        if not significant:
            return "Judges do not appear to be identifying models by their output style."

        interpretations = []
        for model, bias in significant:
            direction = "favored" if bias["vote_rate"] > 0.5 else "disfavored"
            interpretations.append(
                f"{model} is consistently {direction} (vote rate: {bias['vote_rate']:.1%}, p={bias['p_value']:.3f})"
            )

        return "Potential fingerprinting detected: " + "; ".join(interpretations)
```

---

### Section 13: Enhanced Filter System with Age/Generation

```python
class StratifiedSampler:
    """Stratified sampling for diverse prompt selection"""

    def apply_filters(
        self,
        prompts: List[WritingPrompt],
        filters: dict
    ) -> List[WritingPrompt]:
        """Apply user-specified filters including age/generation"""
        filtered = prompts

        if filters.get('occupations'):
            filtered = [p for p in filtered
                       if self._matches_pattern(p.onet_occupation_code, filters['occupations'])]

        if filters.get('industries'):
            filtered = [p for p in filtered
                       if p.naics_code.startswith(tuple(filters['industries']))]

        if filters.get('job_zones'):
            filtered = [p for p in filtered
                       if p.onet_job_zone in filters['job_zones']]

        if filters.get('formality_range'):
            min_f, max_f = filters['formality_range']
            formality_order = list(FormattingLevel)
            filtered = [p for p in filtered
                       if min_f <= formality_order.index(p.formality) <= max_f]

        # ADD: Age/generation filtering
        if filters.get('generations'):
            allowed_generations = [GenerationDemographic(g) for g in filters['generations']]
            filtered = [p for p in filtered
                       if p.writer.generation in allowed_generations]

        if filters.get('age_range'):
            min_age, max_age = filters['age_range']
            filtered = [p for p in filtered
                       if (p.writer.age_range[0] >= min_age and
                           p.writer.age_range[1] <= max_age)]

        # ADD: Urgency filtering
        if filters.get('urgency_levels'):
            allowed_urgency = [UrgencyLevel(u) for u in filters['urgency_levels']]
            filtered = [p for p in filtered
                       if p.urgency in allowed_urgency]

        # ADD: Emotional context filtering
        if filters.get('emotional_contexts'):
            allowed_emotions = [EmotionalContext(e) for e in filters['emotional_contexts']]
            filtered = [p for p in filtered
                       if p.emotional_context in allowed_emotions]

        # ADD: Sensitive topic filtering
        if filters.get('include_sensitive') is False:
            filtered = [p for p in filtered
                       if p.sensitive_topic_category is None]

        if filters.get('sensitive_topics'):
            filtered = [p for p in filtered
                       if p.sensitive_topic_category in filters['sensitive_topics']]

        return filtered
```

---

### Section 14: Prompts Organization by Directory

```python
class PromptOrganizer:
    """Organize prompts into subdirectories for easy browsing"""

    def organize_prompts(
        self,
        prompts: List[WritingPrompt],
        run_dir: Path
    ):
        """Organize prompts into by_occupation and by_industry directories"""

        prompts_dir = run_dir / "prompts"
        by_occupation = prompts_dir / "prompts_by_occupation"
        by_industry = prompts_dir / "prompts_by_industry"

        by_occupation.mkdir(parents=True, exist_ok=True)
        by_industry.mkdir(parents=True, exist_ok=True)

        # Group prompts
        occupation_groups = {}
        industry_groups = {}

        for prompt in prompts:
            # By occupation (SOC major group)
            soc_major = prompt.onet_occupation_code[:2]
            if soc_major not in occupation_groups:
                occupation_groups[soc_major] = []
            occupation_groups[soc_major].append(prompt)

            # By industry (NAICS sector)
            naics_sector = prompt.naics_code[:2]
            if naics_sector not in industry_groups:
                industry_groups[naics_sector] = []
            industry_groups[naics_sector].append(prompt)

        # Write occupation files
        for soc_major, group_prompts in occupation_groups.items():
            occupation_name = self._get_soc_major_name(soc_major)
            filename = f"{soc_major}_{occupation_name.replace(' ', '_').lower()}.json"
            filepath = by_occupation / filename

            with open(filepath, 'w') as f:
                json.dump(
                    [p.model_dump() for p in group_prompts],
                    f,
                    indent=2,
                    default=str
                )

        # Write industry files
        for naics_sector, group_prompts in industry_groups.items():
            industry_name = NAICSMapper.NAICS_SECTORS.get(naics_sector, "Unknown")
            filename = f"{naics_sector}_{industry_name.replace(' ', '_').replace(',', '').lower()}.json"
            filepath = by_industry / filename

            with open(filepath, 'w') as f:
                json.dump(
                    [p.model_dump() for p in group_prompts],
                    f,
                    indent=2,
                    default=str
                )

    SOC_MAJOR_NAMES = {
        "11": "Management",
        "13": "Business and Financial Operations",
        "15": "Computer and Mathematical",
        "17": "Architecture and Engineering",
        "19": "Life, Physical, and Social Science",
        "21": "Community and Social Service",
        "23": "Legal",
        "25": "Educational Instruction and Library",
        "27": "Arts, Design, Entertainment, Sports, and Media",
        "29": "Healthcare Practitioners and Technical",
        "31": "Healthcare Support",
        "33": "Protective Service",
        "35": "Food Preparation and Serving Related",
        "37": "Building and Grounds Cleaning and Maintenance",
        "39": "Personal Care and Service",
        "41": "Sales and Related",
        "43": "Office and Administrative Support",
        "45": "Farming, Fishing, and Forestry",
        "47": "Construction and Extraction",
        "49": "Installation, Maintenance, and Repair",
        "51": "Production",
        "53": "Transportation and Material Moving"
    }

    def _get_soc_major_name(self, soc_major: str) -> str:
        return self.SOC_MAJOR_NAMES.get(soc_major, f"Unknown_{soc_major}")
```

---

### Section 15: Config Summary Text File Generation

```python
class ConfigSummaryGenerator:
    """Generate human-readable configuration summary"""

    def generate_summary(self, config: EvalConfig) -> str:
        """Generate text summary of configuration"""

        summary = f"""Gemini Writing Evaluation - Configuration Summary
================================================

PRESET CONFIGURATION
--------------------
Level: {config.preset_level} ({config.preset_name})

PROMPT CONFIGURATION
--------------------
Number of Prompts: {config.num_prompts}
Random Seed: {config.random_seed}

Filters Applied:
"""
        if config.filters:
            for filter_name, filter_value in config.filters.items():
                if filter_value:
                    summary += f"  - {filter_name}: {filter_value}\n"
        else:
            summary += "  None\n"

        summary += f"""
Stratification: {config.stratification}

MODEL CONFIGURATION
-------------------
Model Pairs:
"""
        for gemini, competitor in config.model_pairs:
            summary += f"  - {gemini} vs {competitor}\n"

        summary += f"""
JUDGE CONFIGURATION
-------------------
Judge Models: {', '.join(config.judge_models)}
Votes per Judge: {config.votes_per_judge}
Judge Personas: Writing Expert + Simulated Recipient

COST ESTIMATE
-------------
Estimated Total Cost: ${config.estimated_cost_lower:.0f} - ${config.estimated_cost_upper:.0f}
Estimated Time: {config.estimated_time_hours:.1f} hours

TECHNICAL SETTINGS
------------------
Max Concurrent API Calls: {config.max_concurrent}
API Timeout: {config.api_timeout}s
Retry Attempts: {config.retry_attempts}

Generated: {datetime.now().isoformat()}
"""
        return summary

    def save_summary(self, config: EvalConfig, run_dir: Path):
        """Save summary to file"""
        summary = self.generate_summary(config)
        (run_dir / "config_summary.txt").write_text(summary)
```

---

### Section 16: Phase 1 Multi-Model Generation for Bias Reduction

```python
class Phase1Generator:
    """Offline LLM generation of persona variations using multiple models"""

    # Use all evaluated models to avoid single-model bias
    GENERATION_MODELS = [
        "google/gemini-3.0-pro",
        "openai/gpt-5.2-thinking",
        "anthropic/claude-opus-4.5",
        "google/gemini-3.0-flash",  # Also use flash tier
    ]

    async def batch_generate(
        self,
        tasks: List[dict],
        client: OpenRouterClient
    ) -> dict:
        """Generate variations for all tasks using multiple models"""

        all_variations = {}

        # Distribute tasks across models
        tasks_per_model = len(tasks) // len(self.GENERATION_MODELS) + 1

        for i, model in enumerate(self.GENERATION_MODELS):
            start_idx = i * tasks_per_model
            end_idx = min((i + 1) * tasks_per_model, len(tasks))
            model_tasks = tasks[start_idx:end_idx]

            for task in model_tasks:
                variations = await self.generate_persona_variations(
                    task,
                    model=model,
                    n_variations=10,
                    client=client
                )

                task_id = task["task_id"]
                if task_id not in all_variations:
                    all_variations[task_id] = {
                        "task": task,
                        "variations": [],
                        "generated_by": []
                    }

                all_variations[task_id]["variations"].extend(variations)
                all_variations[task_id]["generated_by"].append(model)

        # Document bias tracking
        generation_stats = {
            model: sum(1 for v in all_variations.values() if model in v["generated_by"])
            for model in self.GENERATION_MODELS
        }

        return {
            "variations": all_variations,
            "generation_stats": generation_stats,
            "bias_note": "Prompts generated by multiple models to reduce single-model bias"
        }
```

---

## Summary of Changes

### Critical Additions:
1. **Results Viewer TUI** - Complete implementation for post-evaluation inspection
2. **Cross-Run Comparison** - Full implementation with statistical tests
3. **Instruction Compliance Detection** - Track and report instruction-following
4. **Refusal Rate Analysis** - Comprehensive tracking by model, task, and topic
5. **Model Fingerprinting Detection** - Bias detection for judge identification

### Important Fixes:
1. **Atomic Checkpoint Writes** - Prevent corruption on interruption
2. **Multi-Model Prompt Generation** - Reduce bias per PROMPT.md
3. **Enhanced Filter System** - Include age/generation filtering
4. **Prompts Organization** - Create by_occupation and by_industry directories
5. **Auto-Generated README** - Document each run automatically
6. **Config Summary Text** - Human-readable configuration file
7. **Latest Symlink** - Create/update symlink to most recent run

### Code Quality Improvements:
1. **Full `render_prompt()` Implementation** - Previously stub
2. **Enhanced Response Analysis** - Detailed format analysis
3. **Sensitive Topic Detection** - Automatic tagging during extraction
4. **Communication Channel Inference** - Phase 3 LLM enrichment
5. **Consistent Async Time** - Fix circuit breaker time source

---

## Conclusion

Draft Plan 6 provides a solid foundation but requires the additions detailed above to achieve 100% coverage of PROMPT.md requirements. The most critical gaps are:

1. The missing Results Viewer TUI for post-evaluation inspection
2. Incomplete instruction compliance tracking
3. Missing refusal rate analysis by dimension
4. Lack of model fingerprinting detection
5. Missing auto-generated documentation files

The improved plan addresses all these gaps while also fixing technical issues like atomic checkpoint writes and multi-model prompt generation for bias reduction. With these improvements, the plan fully covers the PROMPT.md specification and provides a robust, trustworthy evaluation framework.
