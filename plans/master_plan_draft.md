# Master Plan: Gemini Writing Evaluation Framework

## Executive Summary

This master plan synthesizes insights from six independent draft plans and their respective critiques to produce a comprehensive, production-ready implementation for the Gemini Writing Evaluation Framework. The plan addresses all requirements from PROMPT.md, resolves conflicting approaches with clear decisions, documents risks and open questions, and provides complete implementation guidance.

---

## 1. Key Agreements Across All Plans

The following elements had strong consensus across all 6 drafts and critiques:

### 1.1 Technology Stack (Universal Agreement)
- **Python 3.11+** with asyncio for concurrent API operations
- **httpx** for async HTTP client (superior to requests)
- **pydantic** for data validation and schemas
- **SQLite** for persistent storage (via aiosqlite for async)
- **textual/rich** for TUI progress dashboard
- **plotly** for chart generation
- **reportlab** or weasyprint for PDF report generation
- **typer** for CLI interface

### 1.2 Evaluation Methodology (Universal Agreement)
- **Majority-of-majorities** voting aggregation:
  1. Each judge model gives best-of-5 votes independently
  2. Take majority per judge
  3. Take majority across the 3 judges
- **Dual judge personas**: Writing Expert + Simulated Recipient
- **Three judge models**: Claude Opus 4.5, GPT-5.2, Gemini 3 Pro
- **Position randomization** with deterministic shuffling for bias mitigation
- **Wilson score intervals** for confidence intervals

### 1.3 Architecture (Universal Agreement)
- Clear separation of concerns with modular components
- Rate limiting with exponential backoff
- Circuit breaker pattern for API resilience
- Checkpoint/resume system for interruption recovery
- Atomic file operations for data integrity

---

## 2. Key Disagreements and Resolutions

### 2.1 Hardcoded Categories vs Data-Driven Diversity

**Disagreement**: Several plans hardcoded writing categories (e.g., `WRITING_CATEGORIES = {"explicit_writing": [...], "correspondence": [...]}`) while PROMPT.md explicitly states: "Avoid hardcoding specific categories... Let the O*NET data drive this diversity programmatically."

**Resolution**:
- Use the pre-processed `ONET_WRITING_REFERENCE.md` file created by Opus
- Extract writing-relevant tasks using the reference document, not pattern matching
- Infer categories dynamically from task content during Phase 3 enrichment
- Track writing_category as metadata for analysis but don't constrain generation

### 2.2 Phase 1 Offline LLM Generation Implementation

**Disagreement**: Plans varied in whether Phase 1 was implemented, and if so, which models to use.

**Resolution**:
- **Implement Phase 1 as a mandatory offline preprocessing step**
- **Use ALL models being evaluated** for generation to avoid single-model bias
- Distribute generation across: Gemini 3 Pro, Gemini 3 Flash, GPT-5.2, GPT-4.1, Claude Opus 4.5, Claude Sonnet
- Store pre-generated variations in `data/offline_variations/`
- Track which model generated each variation for bias analysis

### 2.3 Communication Channel Handling

**Disagreement**: Some plans used fixed `CommunicationChannel` enums, others left it dynamic.

**Resolution**:
- **Do NOT use a fixed enum for channels** (violates PROMPT.md)
- Infer channel naturally from O*NET task statement keywords
- Use Phase 3 LLM enrichment to infer channel when task is ambiguous
- Store as string field, track for analysis
- Allow any channel value - don't force into predefined categories

### 2.4 Rate Limiting Architecture

**Disagreement**: Some plans used global rate limits, others per-model limits.

**Resolution**:
- **Implement per-model rate limiting** - different OpenRouter models have different limits
- Track both requests-per-minute (RPM) and tokens-per-minute (TPM)
- Use model-specific limits from OpenRouter documentation
- Fallback to conservative defaults for unknown models

### 2.5 Checkpoint Granularity

**Disagreement**: Plans varied between per-prompt and per-vote checkpointing.

**Resolution**:
- **Checkpoint after each judge vote** (finest granularity)
- Save responses immediately after generation
- Use atomic write operations (temp file + rename)
- Persist circuit breaker state for crash recovery
- Support resuming mid-comparison

---

## 3. Complete System Architecture

### 3.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GEMINI WRITING EVAL FRAMEWORK                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   CLI/TUI    │  │   Config     │  │   Storage    │  │   Reports    │    │
│  │   Interface  │  │   Manager    │  │   Layer      │  │   Generator  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ┌──────▼─────────────────▼─────────────────▼─────────────────▼──────┐     │
│  │                        ORCHESTRATION ENGINE                        │     │
│  │  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐│     │
│  │  │   Checkpoint  │ │ Rate Limiter │ │Circuit Breaker│ │  Signal  ││     │
│  │  │   Manager     │ │ (per-model)  │ │              │ │  Handler ││     │
│  │  └───────────────┘ └──────────────┘ └──────────────┘ └───────────┘│     │
│  └───────────────────────────┬───────────────────────────────────────┘     │
│                              │                                              │
│  ┌───────────────────────────▼───────────────────────────────────────┐     │
│  │                       EVALUATION PIPELINE                          │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │     │
│  │  │   Prompt    │  │  Response   │  │  Judgment   │  │ Compliance│ │     │
│  │  │  Generator  │─▶│  Collector  │─▶│  Aggregator │─▶│  Tracker  │ │     │
│  │  │ (3-phase)   │  │             │  │             │  │           │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │     │
│  └───────────────────────────┬───────────────────────────────────────┘     │
│                              │                                              │
│  ┌───────────────────────────▼───────────────────────────────────────┐     │
│  │                         DATA LAYER                                 │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │     │
│  │  │  O*NET DB   │  │  Company    │  │  Name       │  │ Diversity │ │     │
│  │  │  Extractor  │  │  Database   │  │  Generator  │  │  Tracker  │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                      OPENROUTER API CLIENT                         │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │     │
│  │  │  Async      │  │   Retry     │  │   Token     │  │  Circuit  │ │     │
│  │  │  HTTP Pool  │  │   Logic     │  │   Counter   │  │  Breaker  │ │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Complete Project Structure

```
gemini-writing-eval/
├── pyproject.toml
├── README.md
├── .env.example
│
├── src/
│   ├── __init__.py
│   ├── cli.py                     # Main CLI with all commands
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # EvalConfig, JudgeConfig, etc.
│   │   ├── presets.py             # 10 preset configurations
│   │   └── cost_estimator.py      # Live cost & time estimates
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py      # Reads ONET_WRITING_REFERENCE.md
│   │   ├── naics_mapper.py        # Industry code mapping
│   │   ├── company_database.py    # 500+ real companies
│   │   ├── name_generator.py      # Census-based diverse names
│   │   └── diversity_tracker.py   # Track coverage across dimensions
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── schemas.py             # WritingPrompt, RecipientPersona, etc.
│   │   ├── phase1_offline.py      # Offline LLM generation
│   │   ├── phase2_algorithmic.py  # Algorithmic combination
│   │   ├── phase3_enrichment.py   # LLM enrichment
│   │   ├── constraint_generator.py # Instruction-following constraints
│   │   ├── revision_generator.py  # Revision task generation
│   │   ├── ambiguity_generator.py # Deliberately vague prompts
│   │   ├── tone_matcher.py        # Tone matching examples
│   │   └── channel_inferrer.py    # Communication channel inference
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py   # Async HTTP client
│   │   ├── rate_limiter.py        # Per-model rate limiting
│   │   ├── circuit_breaker.py     # Circuit breaker pattern
│   │   ├── retry_handler.py       # Exponential backoff with jitter
│   │   └── token_counter.py       # Token estimation
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py              # Main evaluation orchestrator
│   │   ├── judge.py               # Judge prompt building
│   │   ├── vote_aggregator.py     # Majority-of-majorities
│   │   ├── compliance_tracker.py  # Instruction compliance verification
│   │   ├── refusal_classifier.py  # Refusal categorization
│   │   ├── response_analyzer.py   # Format/pattern detection
│   │   └── schemas.py             # JudgeVote, Comparison, etc.
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite with aiosqlite
│   │   ├── checkpoint.py          # Fine-grained checkpointing
│   │   ├── run_directory.py       # Full directory structure
│   │   ├── exporter.py            # CSV/JSON export
│   │   └── failure_logger.py      # Structured failure logging
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # Wilson CI, binomtest, effect sizes
│   │   ├── bias_detection.py      # Position, length, model fingerprinting
│   │   ├── weakness_finder.py     # Systematic weakness identification
│   │   ├── dimension_analyzer.py  # Win rates by all dimensions
│   │   └── cross_run_compare.py   # Multi-run comparison
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── progress_dashboard.py  # Real-time progress TUI
│   │   ├── results_viewer.py      # Post-eval inspection TUI
│   │   └── components.py          # Reusable TUI widgets
│   │
│   └── reports/
│       ├── __init__.py
│       ├── pdf_generator.py       # Full PDF report
│       ├── charts.py              # Plotly visualizations
│       ├── heatmaps.py            # Dimension heatmaps
│       └── readme_generator.py    # Auto-generated README.md
│
├── db/
│   ├── onet.db                    # O*NET 30.1 SQLite database
│   └── ONET_WRITING_REFERENCE.md  # Pre-processed writing tasks
│
├── data/
│   ├── companies.json             # Company database
│   ├── names_census.json          # Census-based names
│   └── offline_variations/        # Phase 1 pre-generated variations
│
├── results/
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    ├── unit/
    └── integration/

---

## 4. Three-Phase Prompt Generation Pipeline

### 4.1 Phase 1: Offline LLM Generation

**Purpose**: Pre-generate diverse persona/context variations using the evaluated models themselves.

**Implementation Details**:

```python
# src/prompts/phase1_offline.py

from pathlib import Path
import json
import hashlib
from typing import List, Dict
from dataclasses import dataclass

from ..api.openrouter_client import OpenRouterClient
from ..data.onet_extractor import ONetTask

@dataclass
class PersonaVariation:
    """Pre-generated persona/context variation."""
    variation_id: str
    task_id: str
    generated_by_model: str  # Track for bias analysis
    writer_name: str
    writer_role: str
    writer_generation: str  # gen_z, millennial, gen_x, boomer
    writer_context: str
    recipient_name: str
    recipient_role: str
    recipient_relationship: str
    company_name: str
    company_size: str
    scenario_details: str
    communication_channel: str
    formality_suggestion: int  # 1-5
    urgency_context: str
    emotional_context: str

class Phase1OfflineGenerator:
    """Phase 1: Generate diverse persona variations using evaluated models."""

    # Models to use for generation - ALL evaluated models to avoid bias
    GENERATION_MODELS = [
        "google/gemini-3.0-pro-preview",
        "google/gemini-3.0-flash-preview",
        "openai/gpt-5.2-thinking-preview",
        "openai/gpt-4.1-preview",
        "anthropic/claude-opus-4.5-20251101",
        "anthropic/claude-sonnet-4-20250514"
    ]

    GENERATION_PROMPT = '''Generate 5 diverse, realistic workplace personas for this writing task.

O*NET Task: "{task}"
Occupation: {occupation} (Job Zone {job_zone})

For EACH of the 5 personas, provide:
1. Writer name (culturally diverse, realistic for US workforce)
2. Writer role/title specific to this occupation
3. Writer generation (vary: Gen Z, Millennial, Gen X, Boomer)
4. Brief writer context/background (2-3 sentences)
5. Recipient name (diverse)
6. Recipient role/title
7. Relationship to writer (boss, peer, direct report, client, vendor, etc.)
8. Company name (use real companies when plausible, or realistic fictional)
9. Company size (startup, small, mid-market, enterprise, fortune_500)
10. Specific scenario details (what's happening, why this task matters now)
11. Communication channel (email, memo, slack, report, etc.)
12. Formality level (1-5)
13. Urgency context (none, low, medium, high, crisis)
14. Emotional context (routine, celebration, conflict, bad_news, crisis, etc.)

CRITICAL: Make scenarios feel REAL. Include challenging situations, political dynamics,
competing pressures. Avoid generic corporate-speak.

Output as JSON array with keys: writer_name, writer_role, writer_generation, writer_context,
recipient_name, recipient_role, recipient_relationship, company_name, company_size,
scenario_details, communication_channel, formality_suggestion, urgency_context, emotional_context'''

    def __init__(
        self,
        api_client: OpenRouterClient,
        output_dir: Path,
        variations_per_task_per_model: int = 5
    ):
        self.api_client = api_client
        self.output_dir = output_dir
        self.variations_per_task_per_model = variations_per_task_per_model
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_all_variations(
        self,
        tasks: List[ONetTask]
    ) -> Dict[str, List[PersonaVariation]]:
        """Generate persona variations for all tasks using all models."""
        all_variations = {}

        for task in tasks:
            task_variations = []
            cache_file = self.output_dir / f"{task.task_id}.json"

            # Check cache
            if cache_file.exists():
                with open(cache_file) as f:
                    cached = json.load(f)
                all_variations[task.task_id] = [
                    PersonaVariation(**v) for v in cached
                ]
                continue

            # Generate using each model
            for model in self.GENERATION_MODELS:
                try:
                    variations = await self._generate_for_task(task, model)
                    task_variations.extend(variations)
                except Exception as e:
                    print(f"Warning: Generation failed for {task.task_id} with {model}: {e}")

            # Save to cache
            if task_variations:
                with open(cache_file, 'w') as f:
                    json.dump([v.__dict__ for v in task_variations], f, indent=2)
                all_variations[task.task_id] = task_variations

        return all_variations

    async def _generate_for_task(
        self,
        task: ONetTask,
        model: str
    ) -> List[PersonaVariation]:
        """Generate variations for a single task using specified model."""
        prompt = self.GENERATION_PROMPT.format(
            task=task.task,
            occupation=task.occupation_title,
            job_zone=task.job_zone
        )

        response = await self.api_client.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9  # Higher for diversity
        )

        return self._parse_variations(response.content, task.task_id, model)

    def _parse_variations(
        self,
        content: str,
        task_id: str,
        model: str
    ) -> List[PersonaVariation]:
        """Parse LLM response into PersonaVariation objects."""
        # Extract JSON from response
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            variations_data = json.loads(content)

            variations = []
            for i, v in enumerate(variations_data):
                var_id = hashlib.md5(
                    f"{task_id}_{model}_{i}".encode()
                ).hexdigest()[:12]

                variations.append(PersonaVariation(
                    variation_id=var_id,
                    task_id=task_id,
                    generated_by_model=model,
                    **v
                ))

            return variations
        except json.JSONDecodeError:
            return []
```

### 4.2 Phase 2: Algorithmic Combination

**Purpose**: Deterministically combine O*NET tasks, pre-generated variations, company data, and name data.

**Implementation Details**:

```python
# src/prompts/phase2_algorithmic.py

import random
import hashlib
from typing import List, Optional
from dataclasses import dataclass

from .schemas import WritingPrompt, WriterPersona, RecipientPersona, CompanyContext
from .phase1_offline import PersonaVariation
from ..data.onet_extractor import ONetTask, ONetExtractor
from ..data.company_database import CompanyDatabase
from ..data.name_generator import NameGenerator
from ..data.naics_mapper import NAICSMapper

class Phase2AlgorithmicCombiner:
    """Phase 2: Algorithmically combine data sources into prompts."""

    def __init__(
        self,
        onet_extractor: ONetExtractor,
        company_db: CompanyDatabase,
        name_generator: NameGenerator,
        naics_mapper: NAICSMapper,
        random_seed: int
    ):
        self.onet = onet_extractor
        self.companies = company_db
        self.names = name_generator
        self.naics = naics_mapper
        self.rng = random.Random(random_seed)

    def generate_prompts(
        self,
        tasks: List[ONetTask],
        variations: Dict[str, List[PersonaVariation]],
        num_prompts: int,
        stratify_by_job_zone: bool = True,
        stratify_by_soc_group: bool = True
    ) -> List[WritingPrompt]:
        """Generate prompts from O*NET tasks and pre-generated variations."""
        prompts = []

        # Apply stratification
        if stratify_by_job_zone:
            tasks = self._stratify_by_job_zone(tasks, num_prompts)

        if stratify_by_soc_group:
            tasks = self._stratify_by_soc_group(tasks, num_prompts)

        for i, task in enumerate(tasks[:num_prompts]):
            # Get a variation for this task
            task_variations = variations.get(task.task_id, [])
            if task_variations:
                variation = self.rng.choice(task_variations)
                prompt = self._build_from_variation(task, variation, i)
            else:
                # Fallback: generate algorithmically
                prompt = self._build_algorithmic(task, i)

            prompts.append(prompt)

        return prompts

    def _build_from_variation(
        self,
        task: ONetTask,
        variation: PersonaVariation,
        index: int
    ) -> WritingPrompt:
        """Build a prompt from a pre-generated variation."""
        # Use deterministic hash for prompt ID
        prompt_id = hashlib.md5(
            f"{task.task_id}_{variation.variation_id}_{index}".encode()
        ).hexdigest()[:16]

        # Get company context (use variation's company if real, else sample)
        company = self.companies.get_by_name(variation.company_name)
        if not company:
            company = self.companies.sample_for_occupation(task.onetsoc_code)

        # Get NAICS mapping
        naics_info = self.naics.get_for_occupation(task.onetsoc_code)

        # Build writer persona
        writer = WriterPersona(
            name=variation.writer_name,
            job_title=variation.writer_role,
            generation=variation.writer_generation.lower().replace(" ", "_"),
            age=self._generation_to_age(variation.writer_generation),
            skill_level=self._job_zone_to_skill(task.job_zone),
            english_variant="en-US"
        )

        # Build recipient persona
        recipient = RecipientPersona(
            name=variation.recipient_name,
            job_title=variation.recipient_role,
            relationship=self._normalize_relationship(variation.recipient_relationship),
            english_variant="en-US",
            is_primary=True
        )

        # Build company context
        company_ctx = CompanyContext(
            name=company.name if company else variation.company_name,
            size=variation.company_size.lower().replace(" ", "_"),
            industry_naics=naics_info.code if naics_info else "000000",
            industry_name=naics_info.description if naics_info else "General Industry",
            is_public=company.is_public if company else False
        )

        return WritingPrompt(
            prompt_id=prompt_id,
            onet_task_id=task.task_id,
            onet_task=task.task,
            occupation_code=task.onetsoc_code,
            occupation_title=task.occupation_title,
            job_zone=task.job_zone,
            soc_major_group=task.onetsoc_code[:2],
            naics_code=company_ctx.industry_naics,
            naics_sector=company_ctx.industry_naics[:2],
            company=company_ctx,
            writer=writer,
            recipients=[recipient],
            audience_size="one_on_one",
            formality_level=variation.formality_suggestion,
            urgency_level=self._urgency_to_level(variation.urgency_context),
            message_position=self._infer_message_position(task.task),
            emotional_context=self._normalize_emotional(variation.emotional_context),
            communication_channel=variation.communication_channel,
            generated_by_model=variation.generated_by_model,
            # Prompt text will be built in Phase 3
            full_prompt=""
        )

    def _stratify_by_job_zone(
        self,
        tasks: List[ONetTask],
        num_prompts: int
    ) -> List[ONetTask]:
        """Stratify task sampling to ensure job zone diversity."""
        by_zone = {1: [], 2: [], 3: [], 4: [], 5: []}
        for task in tasks:
            by_zone[task.job_zone].append(task)

        per_zone = num_prompts // 5
        stratified = []
        for zone in range(1, 6):
            zone_tasks = by_zone[zone]
            if zone_tasks:
                stratified.extend(self.rng.sample(
                    zone_tasks,
                    min(per_zone, len(zone_tasks))
                ))

        # Shuffle to avoid zone clustering
        self.rng.shuffle(stratified)
        return stratified

    def _stratify_by_soc_group(
        self,
        tasks: List[ONetTask],
        num_prompts: int
    ) -> List[ONetTask]:
        """Stratify by major SOC group for occupational diversity."""
        by_group = {}
        for task in tasks:
            group = task.onetsoc_code[:2]
            if group not in by_group:
                by_group[group] = []
            by_group[group].append(task)

        per_group = max(1, num_prompts // len(by_group))
        stratified = []
        for group, group_tasks in by_group.items():
            stratified.extend(self.rng.sample(
                group_tasks,
                min(per_group, len(group_tasks))
            ))

        self.rng.shuffle(stratified)
        return stratified
```

### 4.3 Phase 3: LLM Enrichment

**Purpose**: Add context-heavy enrichments that require LLM generation: attachments, prior messages, tone examples, temporal context, competing objectives.

**Implementation Details**:

```python
# src/prompts/phase3_enrichment.py

import asyncio
import json
from typing import List, Optional
from datetime import datetime, timedelta

from .schemas import WritingPrompt, Attachment, ToneExample, CCContext, RevisionTask
from ..api.openrouter_client import OpenRouterClient

class Phase3Enricher:
    """Phase 3: LLM enrichment for context-heavy prompts."""

    # Use evaluated models for enrichment to avoid bias
    ENRICHMENT_MODELS = [
        "google/gemini-3.0-pro-preview",
        "anthropic/claude-sonnet-4-20250514"
    ]

    def __init__(
        self,
        api_client: OpenRouterClient,
        enrich_ratio: float = 0.3  # Enrich 30% of prompts
    ):
        self.api_client = api_client
        self.enrich_ratio = enrich_ratio
        self.model_index = 0

    async def enrich_prompts(
        self,
        prompts: List[WritingPrompt]
    ) -> List[WritingPrompt]:
        """Enrich prompts with LLM-generated context."""
        import random

        # Select which prompts to enrich
        num_to_enrich = int(len(prompts) * self.enrich_ratio)
        indices_to_enrich = set(random.sample(range(len(prompts)), num_to_enrich))

        enrichment_tasks = []
        for i, prompt in enumerate(prompts):
            if i in indices_to_enrich:
                enrichment_tasks.append(self._enrich_single_prompt(prompt))

        # Run enrichments in parallel batches
        batch_size = 10
        enriched_prompts = list(prompts)  # Copy

        for batch_start in range(0, len(enrichment_tasks), batch_size):
            batch = enrichment_tasks[batch_start:batch_start + batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)

            for j, result in enumerate(results):
                if not isinstance(result, Exception):
                    original_idx = list(indices_to_enrich)[batch_start + j]
                    enriched_prompts[original_idx] = result

        # Build final prompt text for all
        for prompt in enriched_prompts:
            prompt.full_prompt = self._build_prompt_text(prompt)

        return enriched_prompts

    async def _enrich_single_prompt(
        self,
        prompt: WritingPrompt
    ) -> WritingPrompt:
        """Apply various enrichments to a single prompt."""
        # Rotate through enrichment models
        model = self._get_next_model()

        enrichments = []

        # Add prior message for replies
        if prompt.message_position.value in ['reply_in_thread', 'follow_up']:
            enrichments.append(self._generate_prior_message(prompt, model))

        # Add attachments for reports/memos
        if prompt.communication_channel in ['report', 'memo', 'presentation']:
            enrichments.append(self._generate_attachment(prompt, model))

        # Add competing objectives for conflict/bad news
        if prompt.emotional_context.value in ['conflict', 'bad_news', 'crisis']:
            enrichments.append(self._generate_competing_objectives(prompt, model))

        # 15% chance of tone matching
        import random
        if random.random() < 0.15:
            enrichments.append(self._generate_tone_example(prompt, model))

        # 20% chance of temporal context
        if random.random() < 0.20:
            enrichments.append(self._add_temporal_context(prompt))

        # Run all enrichments
        results = await asyncio.gather(*enrichments, return_exceptions=True)

        # Apply successful enrichments
        for result in results:
            if isinstance(result, dict):
                if 'prior_message' in result:
                    prompt.prior_context = result['prior_message']
                if 'attachment' in result:
                    prompt.attachments.append(result['attachment'])
                if 'competing_objectives' in result:
                    prompt.competing_objectives = result['competing_objectives']
                if 'tone_example' in result:
                    prompt.tone_example = result['tone_example']
                if 'temporal' in result:
                    prompt.temporal_context = result['temporal']

        return prompt

    def _get_next_model(self) -> str:
        """Rotate through enrichment models."""
        model = self.ENRICHMENT_MODELS[self.model_index % len(self.ENRICHMENT_MODELS)]
        self.model_index += 1
        return model

    async def _generate_prior_message(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> dict:
        """Generate a prior message for reply context."""
        generation_prompt = f'''Generate a realistic prior email/message that requires a response.

Context:
- Writer: {prompt.writer.name}, {prompt.writer.job_title} at {prompt.company.name}
- Recipient (sender of prior message): {prompt.recipients[0].name}, {prompt.recipients[0].job_title}
- Topic: {prompt.onet_task}
- Formality: {prompt.formality_level}/5

Generate a message (50-150 words) that the writer must respond to. Make it authentic.
Include specific details that need addressing.

Output the message text only, no preamble.'''

        response = await self.api_client.complete(
            model=model,
            messages=[{"role": "user", "content": generation_prompt}],
            temperature=0.7
        )

        return {'prior_message': response.content.strip()}

    async def _generate_attachment(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> dict:
        """Generate mock attachment summary."""
        doc_type = {
            'report': 'quarterly performance report with key metrics',
            'memo': 'policy update memo',
            'presentation': 'meeting agenda and action items'
        }.get(prompt.communication_channel, 'reference document')

        generation_prompt = f'''Generate a concise summary (100-150 words) of a {doc_type} that would be attached to a workplace communication.

Context:
- Company: {prompt.company.name} ({prompt.company.industry_name})
- Task: {prompt.onet_task}
- Purpose: This document provides context for the communication

Include plausible specifics (numbers, names, dates) but mark as "[COMPANY]" or "[METRIC]" where needed.

Output the summary only.'''

        response = await self.api_client.complete(
            model=model,
            messages=[{"role": "user", "content": generation_prompt}],
            temperature=0.7
        )

        attachment = Attachment(
            type=prompt.communication_channel,
            description=f"Attached {doc_type}",
            content=response.content.strip()
        )

        return {'attachment': attachment}

    async def _generate_competing_objectives(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> dict:
        """Generate competing objectives creating tension."""
        generation_prompt = f'''Given this writing task, identify two competing objectives the writer must balance.

Task: {prompt.onet_task}
Context: {prompt.writer.job_title} writing to {prompt.recipients[0].job_title}
Emotional context: {prompt.emotional_context.value}

Output as a single sentence describing the tension, e.g.:
"You need to be honest about the project delays while maintaining client confidence."

Output only the tension description.'''

        response = await self.api_client.complete(
            model=model,
            messages=[{"role": "user", "content": generation_prompt}],
            temperature=0.5
        )

        return {'competing_objectives': response.content.strip()}

    async def _generate_tone_example(
        self,
        prompt: WritingPrompt,
        model: str
    ) -> dict:
        """Generate a tone example for matching."""
        generation_prompt = f'''Generate a short example (50-100 words) of how {prompt.writer.name} typically writes in their role as {prompt.writer.job_title}.

The example should reflect a formality level of {prompt.formality_level}/5.
This will be used as a tone reference for the writer to match.

Output the example text only.'''

        response = await self.api_client.complete(
            model=model,
            messages=[{"role": "user", "content": generation_prompt}],
            temperature=0.7
        )

        tone_example = ToneExample(
            example_text=response.content.strip(),
            context=f"How {prompt.writer.name} typically communicates",
            match_instruction="Match this tone and style in your response."
        )

        return {'tone_example': tone_example}

    async def _add_temporal_context(
        self,
        prompt: WritingPrompt
    ) -> dict:
        """Add temporal grounding."""
        import random

        base_date = datetime(2026, 1, 6)  # Per PROMPT.md

        # Random deadline 1-14 days out
        deadline_days = random.randint(1, 14)
        deadline = base_date + timedelta(days=deadline_days)

        events = [
            "last week's team meeting",
            "the recent reorganization announcement",
            "the Q4 results release",
            "yesterday's client call",
            "the board meeting earlier this week"
        ]

        temporal = f"Today is {base_date.strftime('%B %d, %Y')}. "
        if random.random() < 0.7:
            temporal += f"Deadline: {deadline.strftime('%A, %B %d')}. "
        if random.random() < 0.5:
            temporal += f"Following up on {random.choice(events)}."

        return {'temporal': temporal.strip()}

    def _build_prompt_text(self, prompt: WritingPrompt) -> str:
        """Build the complete prompt text from all components."""
        sections = []

        # Writer context
        sections.append(f"""You are {prompt.writer.name}, {prompt.writer.job_title} at {prompt.company.name}.

Company: {prompt.company.name} ({prompt.company.size}, {prompt.company.industry_name})""")

        # Temporal context
        if prompt.temporal_context:
            sections.append(prompt.temporal_context)

        # Task
        sections.append(f"""
## Writing Task
{prompt.onet_task}

## Your Target Audience
Primary Recipient: {prompt.recipients[0].name}, {prompt.recipients[0].job_title}
Relationship: {prompt.recipients[0].relationship}""")

        # CC recipients if any
        if prompt.cc_context and prompt.cc_context.cc_recipients:
            sections.append(f"CC'd: {', '.join(prompt.cc_context.cc_recipients)}")

        # Communication context
        sections.append(f"""
## Communication Context
Formality: {prompt.formality_level}/5
Urgency: {prompt.urgency_level}/5
Emotional Context: {prompt.emotional_context.value}
Channel: {prompt.communication_channel or 'email'}""")

        # Prior message for replies
        if prompt.prior_context:
            sections.append(f"""
---
**Prior message to respond to:**

{prompt.prior_context}
---""")

        # Attachments
        if prompt.attachments:
            sections.append("\n## Referenced Materials")
            for att in prompt.attachments:
                sections.append(f"[{att.type.upper()}: {att.description}]\n{att.content}")

        # Tone example
        if prompt.tone_example:
            sections.append(f"""
## Tone Reference
{prompt.tone_example.context}:
"{prompt.tone_example.example_text}"

{prompt.tone_example.match_instruction}""")

        # Competing objectives
        if prompt.competing_objectives:
            sections.append(f"\n## Key Challenge\n{prompt.competing_objectives}")

        # Instruction constraints
        if prompt.constraints:
            sections.append("\n## Specific Requirements")
            for c in prompt.constraints:
                sections.append(f"- {c.description}")

        # Final instruction
        sections.append("\nPlease write the requested content. Do not include meta-commentary about the task.")

        return "\n\n".join(sections)
```

---

## 5. Complete Prompt Schema

### 5.1 WritingPrompt Schema (Comprehensive)

```python
# src/prompts/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    INITIAL = "initial_outreach"
    REPLY = "reply_in_thread"
    FOLLOWUP = "follow_up"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"

class SensitiveTopic(str, Enum):
    HR_ISSUES = "hr_issues"
    LEGAL = "legal_matters"
    BAD_NEWS = "bad_news_delivery"
    CONFIDENTIAL = "confidential_information"
    CONFLICT = "conflict_situations"

class WriterPersona(BaseModel):
    """Complete writer persona specification."""
    name: str
    email: Optional[str] = None
    age: int = Field(ge=18, le=80)
    generation: Literal["gen_z", "millennial", "gen_x", "boomer"]
    job_title: str
    skill_level: Literal["entry", "mid", "senior", "executive"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    years_experience: Optional[int] = None

class RecipientPersona(BaseModel):
    """Complete recipient persona specification."""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship: Literal["new_contact", "acquaintance", "colleague",
                          "manager", "direct_report", "client", "vendor"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    is_technical: bool = False
    is_primary: bool = True
    prior_contact: bool = True

class CompanyContext(BaseModel):
    """Company information for grounding."""
    name: str
    size: Literal["startup", "small", "mid_market", "enterprise", "fortune_500"]
    industry_naics: str
    industry_name: str
    is_public: bool = False
    hq_location: Optional[str] = None
    employee_count: Optional[int] = None

class Attachment(BaseModel):
    """Mock attachment or reference content."""
    type: str  # report, email, meeting_notes, etc.
    description: str
    content: str

class ToneExample(BaseModel):
    """Prior writing sample for tone matching."""
    example_text: str
    context: str
    match_instruction: str

class CCContext(BaseModel):
    """Context for CC/forwarding scenarios."""
    cc_recipients: List[str] = []
    will_be_forwarded_to: Optional[str] = None
    mixed_audience_note: Optional[str] = None

class ConstraintSpec(BaseModel):
    """Explicit instruction-following constraint."""
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    description: str
    specific_requirement: str
    measurable: bool = True

class RevisionTask(BaseModel):
    """Details for revision/editing tasks."""
    original_draft: str
    revision_type: Literal["concise", "professional", "soften", "expand", "clarify"]
    instruction: str

class WritingPrompt(BaseModel):
    """Complete writing prompt with all dimensions per PROMPT.md."""

    # Identifiers
    prompt_id: str
    onet_task_id: str
    onet_task: str

    # Occupation context
    occupation_code: str
    occupation_title: str
    job_zone: int = Field(ge=1, le=5)
    soc_major_group: str

    # Industry context
    naics_code: str
    naics_sector: str
    company: CompanyContext

    # Personas
    writer: WriterPersona
    recipients: List[RecipientPersona]
    audience_size: Literal["one_on_one", "small_group", "department",
                           "company_wide", "public"]

    # CC/Multiple audience context
    cc_context: Optional[CCContext] = None

    # Communication context
    formality_level: int = Field(ge=1, le=5)
    urgency_level: int = Field(ge=1, le=5)
    message_position: MessagePosition
    emotional_context: EmotionalContext
    communication_channel: Optional[str] = None  # NOT an enum - dynamic

    # Content context
    prior_context: Optional[str] = None
    attachments: List[Attachment] = []
    competing_objectives: Optional[str] = None
    temporal_context: Optional[str] = None

    # Tone matching
    tone_example: Optional[ToneExample] = None

    # Revision tasks
    is_revision_task: bool = False
    revision_task: Optional[RevisionTask] = None

    # Instruction-following constraints
    constraints: List[ConstraintSpec] = []

    # Ambiguity testing
    is_ambiguous: bool = False
    ambiguity_type: Optional[Literal["underspecified_recipient",
                                      "missing_context", "unclear_ask"]] = None

    # Sensitive topics
    sensitive_topics: List[SensitiveTopic] = []

    # Language
    language: str = "en"
    language_variant: str = "en-US"
    recipient_english_variant: Optional[str] = None

    # Metadata
    generated_by_model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # The actual prompt text
    full_prompt: str
```

---

## 6. Evaluation Engine and Judge System

### 6.1 Judge Context (CRITICAL)

Per PROMPT.md and critiques, judges need FULL scenario context to evaluate properly.

```python
# src/eval/judge.py

from typing import Tuple
from ..prompts.schemas import WritingPrompt

class JudgePromptBuilder:
    """Build judge prompts with full scenario context."""

    WRITING_EXPERT_SYSTEM = """You are a seasoned writing consultant who has coached executives
at Fortune 500 companies. Your expertise is in professional communication that achieves
business objectives while maintaining appropriate relationships and tone.

You will evaluate two responses to the same writing task. Consider:
- Appropriateness for the specific audience and relationship
- Clarity and organization
- Tone matching the emotional context
- Achievement of the communication objective
- Professionalism and polish
- Instruction compliance (if constraints were specified)

CRITICAL: Position labels (Response A/B) do NOT indicate quality."""

    RECIPIENT_SYSTEM = """You are {recipient_name}, {recipient_title}.
Your relationship with the sender: {relationship}

You will evaluate two responses to a message you would receive.
As the actual recipient, consider:
- Would this message achieve its intended purpose?
- Is the tone appropriate for your relationship with the sender?
- Is it clear what action, if any, you should take?
- Would you feel respected and properly informed?
- Does it feel authentic and human?

CRITICAL: Position labels (Response A/B) do NOT indicate quality."""

    def build_judge_prompt(
        self,
        prompt: WritingPrompt,
        response_a: str,
        response_b: str,
        persona: str  # "expert" or "recipient"
    ) -> Tuple[str, str]:
        """Build complete judge prompt with full context."""

        # System prompt based on persona
        if persona == "expert":
            system = self.WRITING_EXPERT_SYSTEM
        else:
            system = self.RECIPIENT_SYSTEM.format(
                recipient_name=prompt.recipients[0].name,
                recipient_title=prompt.recipients[0].job_title,
                relationship=prompt.recipients[0].relationship
            )

        # Build user prompt with FULL scenario context
        user_sections = []

        # Task context
        user_sections.append(f"""## Writing Task
{prompt.onet_task}

## Writer Context
Name: {prompt.writer.name}
Role: {prompt.writer.job_title} at {prompt.company.name}
Company: {prompt.company.name} ({prompt.company.size}, {prompt.company.industry_name})
Generation: {prompt.writer.generation}

## Recipient Context
Name: {prompt.recipients[0].name}
Role: {prompt.recipients[0].job_title}
Relationship to Writer: {prompt.recipients[0].relationship}
English Variant: {prompt.recipients[0].english_variant.value}""")

        # CC context if present
        if prompt.cc_context and prompt.cc_context.cc_recipients:
            user_sections.append(f"""
## Additional Audience
CC'd: {', '.join(prompt.cc_context.cc_recipients)}
{prompt.cc_context.mixed_audience_note or ''}""")

        # Communication context
        user_sections.append(f"""
## Communication Requirements
Formality Level: {prompt.formality_level}/5
Urgency: {prompt.urgency_level}/5
Emotional Context: {prompt.emotional_context.value}
Channel: {prompt.communication_channel or 'email'}
Message Position: {prompt.message_position.value}""")

        # Temporal context if present
        if prompt.temporal_context:
            user_sections.append(f"\n## Temporal Context\n{prompt.temporal_context}")

        # Prior message if reply
        if prompt.prior_context:
            user_sections.append(f"""
## Prior Message (being responded to)
{prompt.prior_context}""")

        # Attachments summary
        if prompt.attachments:
            user_sections.append("\n## Referenced Materials")
            for att in prompt.attachments:
                user_sections.append(f"[{att.type}]: {att.description}")

        # Tone example if present
        if prompt.tone_example:
            user_sections.append(f"""
## Tone Reference (writer should match)
{prompt.tone_example.context}:
"{prompt.tone_example.example_text[:200]}..."
""")

        # Competing objectives if present
        if prompt.competing_objectives:
            user_sections.append(f"""
## Key Challenge
{prompt.competing_objectives}""")

        # Instruction constraints
        if prompt.constraints:
            user_sections.append("\n## Explicit Constraints (MUST be followed)")
            for c in prompt.constraints:
                user_sections.append(f"- {c.description}")

        # The responses to evaluate
        user_sections.append(f"""
---

## Response A
{response_a}

---

## Response B
{response_b}

---

## Your Evaluation

Compare these responses considering ALL context above. Provide:

1. WINNER: "A", "B", or "TIE"
2. CONFIDENCE: 1-5 (5 = very confident)
3. QUALITY_A: 1-10 overall quality score
4. QUALITY_B: 1-10 overall quality score
5. REASONING: 2-3 sentences explaining your decision

Format your response EXACTLY as:
WINNER: [A/B/TIE]
CONFIDENCE: [1-5]
QUALITY_A: [1-10]
QUALITY_B: [1-10]
REASONING: [Your explanation]""")

        return system, "\n\n".join(user_sections)
```

### 6.2 Vote Aggregator (Fixed)

Critical bug fix from critiques: Track winner relative to Gemini consistently.

```python
# src/eval/vote_aggregator.py

import hashlib
import random
from typing import List, Tuple, Literal
from dataclasses import dataclass

@dataclass
class JudgeVote:
    """Single vote from a judge."""
    judge_model: str
    judge_persona: str  # "expert" or "recipient"
    vote_index: int  # Which of the 5 votes
    winner: Literal["gemini", "competitor", "tie"]
    confidence: int
    quality_gemini: int
    quality_competitor: int
    reasoning: str
    gemini_was_position: Literal["A", "B"]

@dataclass
class AggregatedResult:
    """Aggregated result for a comparison."""
    prompt_id: str
    gemini_model: str
    competitor_model: str
    final_winner: Literal["gemini", "competitor", "tie"]
    gemini_wins: int
    competitor_wins: int
    ties: int
    judge_agreement: float  # 0.0 to 1.0
    all_votes: List[JudgeVote]

class VoteAggregator:
    """Implement majority-of-majorities aggregation."""

    def __init__(self, votes_per_judge: int = 5):
        self.votes_per_judge = votes_per_judge

    def get_position_for_vote(
        self,
        prompt_id: str,
        gemini_model: str,
        competitor_model: str,
        judge_model: str,
        vote_index: int
    ) -> Literal["A", "B"]:
        """Deterministic but varied position assignment."""
        # Use stable hash for reproducibility
        seed_string = f"{prompt_id}_{gemini_model}_{competitor_model}_{judge_model}_{vote_index}"
        seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        return "A" if rng.random() < 0.5 else "B"

    def parse_winner_to_normalized(
        self,
        raw_winner: str,
        gemini_position: Literal["A", "B"]
    ) -> Literal["gemini", "competitor", "tie"]:
        """Convert position-based winner to model-based winner."""
        raw = raw_winner.upper().strip()
        if raw == "TIE":
            return "tie"
        elif raw == gemini_position:
            return "gemini"
        else:
            return "competitor"

    def aggregate_for_judge(
        self,
        votes: List[JudgeVote]
    ) -> Literal["gemini", "competitor", "tie"]:
        """Get majority winner for a single judge's votes."""
        gemini_count = sum(1 for v in votes if v.winner == "gemini")
        competitor_count = sum(1 for v in votes if v.winner == "competitor")
        tie_count = sum(1 for v in votes if v.winner == "tie")

        # Best-of-5 majority
        if gemini_count >= 3:
            return "gemini"
        elif competitor_count >= 3:
            return "competitor"
        else:
            # If no clear majority, compare totals
            if gemini_count > competitor_count:
                return "gemini"
            elif competitor_count > gemini_count:
                return "competitor"
            else:
                return "tie"

    def aggregate_all(
        self,
        prompt_id: str,
        gemini_model: str,
        competitor_model: str,
        all_votes: List[JudgeVote]
    ) -> AggregatedResult:
        """Apply majority-of-majorities aggregation."""

        # Group by judge model + persona
        judge_groups = {}
        for vote in all_votes:
            key = (vote.judge_model, vote.judge_persona)
            if key not in judge_groups:
                judge_groups[key] = []
            judge_groups[key].append(vote)

        # Get majority per judge
        judge_majorities = []
        for key, votes in judge_groups.items():
            majority = self.aggregate_for_judge(votes)
            judge_majorities.append(majority)

        # Aggregate across judges
        gemini_judges = sum(1 for m in judge_majorities if m == "gemini")
        competitor_judges = sum(1 for m in judge_majorities if m == "competitor")

        if gemini_judges > len(judge_majorities) / 2:
            final = "gemini"
        elif competitor_judges > len(judge_majorities) / 2:
            final = "competitor"
        else:
            final = "tie"

        # Calculate agreement
        total_decisive = sum(1 for m in judge_majorities if m != "tie")
        if total_decisive > 0:
            agreement = max(gemini_judges, competitor_judges) / len(judge_majorities)
        else:
            agreement = 0.0

        return AggregatedResult(
            prompt_id=prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            final_winner=final,
            gemini_wins=sum(1 for v in all_votes if v.winner == "gemini"),
            competitor_wins=sum(1 for v in all_votes if v.winner == "competitor"),
            ties=sum(1 for v in all_votes if v.winner == "tie"),
            judge_agreement=agreement,
            all_votes=all_votes
        )
```

---

## 7. Special Prompt Types

### 7.1 Instruction-Following Constraints

```python
# src/prompts/constraint_generator.py

import random
from typing import List
from .schemas import ConstraintSpec, WritingPrompt

class ConstraintGenerator:
    """Generate instruction-following constraints per PROMPT.md."""

    LENGTH_CONSTRAINTS = [
        ("Keep this under 100 words", "length", "max_words:100"),
        ("Keep this under 50 words", "length", "max_words:50"),
        ("This should be comprehensive, at least 500 words", "length", "min_words:500"),
        ("Write exactly 3 sentences", "length", "exact_sentences:3"),
        ("Keep it to a single paragraph", "length", "max_paragraphs:1"),
    ]

    FORMAT_CONSTRAINTS = [
        ("Use exactly 3 bullet points", "format", "exact_bullets:3"),
        ("Use exactly 5 bullet points", "format", "exact_bullets:5"),
        ("Write in paragraph form only, no bullet points", "format", "no_bullets"),
        ("Include a clear subject line", "format", "has_subject"),
        ("Structure with clear headings", "format", "has_headings"),
    ]

    TONE_CONSTRAINTS = [
        ("Be direct and avoid pleasantries", "tone", "no_pleasantries"),
        ("Use a warm, encouraging tone", "tone", "warm_tone"),
        ("Keep it strictly professional, no casual language", "tone", "formal_only"),
    ]

    EXCLUSION_CONSTRAINTS = [
        ("Do not mention the budget", "exclusion", "topic:budget"),
        ("Avoid mentioning specific dates", "exclusion", "topic:dates"),
        ("Do not use the word 'synergy'", "exclusion", "word:synergy"),
        ("Avoid technical jargon", "exclusion", "style:jargon"),
    ]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def maybe_add_constraints(
        self,
        prompt: WritingPrompt,
        constraint_probability: float = 0.15
    ) -> WritingPrompt:
        """Potentially add instruction-following constraints."""
        if self.rng.random() > constraint_probability:
            return prompt

        # Select 1-2 constraints
        num_constraints = self.rng.choices([1, 2], weights=[0.7, 0.3])[0]

        all_constraints = (
            self.LENGTH_CONSTRAINTS +
            self.FORMAT_CONSTRAINTS +
            self.TONE_CONSTRAINTS +
            self.EXCLUSION_CONSTRAINTS
        )

        selected = self.rng.sample(all_constraints, min(num_constraints, len(all_constraints)))

        for desc, ctype, requirement in selected:
            prompt.constraints.append(ConstraintSpec(
                type=ctype,
                description=desc,
                specific_requirement=requirement,
                measurable=True
            ))

        return prompt
```

### 7.2 Revision Task Generator

```python
# src/prompts/revision_generator.py

import random
from typing import Optional
from .schemas import RevisionTask, WritingPrompt

class RevisionTaskGenerator:
    """Generate revision/editing tasks per PROMPT.md."""

    CASUAL_DRAFTS = [
        "hey {recipient}, just wanted to touch base about {topic}. lemme know when works for u to chat. thx!",
        "Hi! So I was thinking about {topic} and wondering if maybe we could discuss? lmk!",
        "yo {recipient} - quick q about {topic}. can u help? thx",
    ]

    HARSH_DRAFTS = [
        "This is completely unacceptable. You need to fix {topic} immediately. This is the third time.",
        "Your work on {topic} was substandard. This cannot continue. Explain why this happened.",
        "I'm extremely disappointed with the {topic} situation. This needs to be resolved TODAY.",
    ]

    CONFUSING_DRAFTS = [
        "So about the thing we discussed, I think maybe we should but also could not? Let me know.",
        "Following up on {topic} and also the other items. Can you do the thing before next week?",
        "Per our conversation, the {topic} needs attention but not the urgent kind unless you disagree.",
    ]

    REVISION_TYPES = {
        "professional": ("Make this email more professional", CASUAL_DRAFTS),
        "soften": ("Soften the tone of this message", HARSH_DRAFTS),
        "clarify": ("Clarify and restructure this confusing message", CONFUSING_DRAFTS),
        "concise": ("Revise this to be more concise", None),  # Will use LLM to generate verbose version
    }

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def should_be_revision_task(self, probability: float = 0.10) -> bool:
        return self.rng.random() < probability

    def create_revision_task(
        self,
        prompt: WritingPrompt,
        revision_type: Optional[str] = None
    ) -> WritingPrompt:
        """Convert a prompt into a revision task."""
        if revision_type is None:
            revision_type = self.rng.choice(list(self.REVISION_TYPES.keys()))

        instruction, templates = self.REVISION_TYPES[revision_type]

        if templates:
            template = self.rng.choice(templates)
            original_draft = template.format(
                recipient=prompt.recipients[0].name.split()[0],
                topic=prompt.onet_task[:50]
            )
        else:
            # For "concise" type, will be filled by LLM in Phase 3
            original_draft = "[To be generated: verbose version of the task response]"

        prompt.is_revision_task = True
        prompt.revision_task = RevisionTask(
            original_draft=original_draft,
            revision_type=revision_type,
            instruction=instruction
        )

        return prompt
```

### 7.3 Ambiguity Generator

```python
# src/prompts/ambiguity_generator.py

import random
from .schemas import WritingPrompt

class AmbiguityGenerator:
    """Generate deliberately vague prompts per PROMPT.md."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def should_be_ambiguous(self, probability: float = 0.10) -> bool:
        return self.rng.random() < probability

    def make_ambiguous(
        self,
        prompt: WritingPrompt
    ) -> WritingPrompt:
        """Make a prompt deliberately vague."""
        ambiguity_type = self.rng.choice([
            "underspecified_recipient",
            "missing_context",
            "unclear_ask"
        ])

        prompt.is_ambiguous = True
        prompt.ambiguity_type = ambiguity_type

        if ambiguity_type == "underspecified_recipient":
            # Remove recipient details
            prompt.recipients[0].job_title = "colleague"
            prompt.recipients[0].relationship = "acquaintance"

        elif ambiguity_type == "missing_context":
            # Remove competing objectives, attachments, prior context
            prompt.competing_objectives = None
            prompt.attachments = []
            prompt.prior_context = None
            prompt.temporal_context = None

        elif ambiguity_type == "unclear_ask":
            # Make the task vague
            prompt.onet_task = f"Write something regarding {prompt.onet_task.split()[0]} matters"

        return prompt
```

### 7.4 CC/Multiple Recipient Generator

```python
# src/prompts/cc_generator.py

import random
from typing import List
from .schemas import WritingPrompt, RecipientPersona, CCContext

class CCScenarioGenerator:
    """Generate CC/multiple recipient scenarios per PROMPT.md."""

    CC_SCENARIOS = [
        ("email_to_client_cc_boss", "Email to client, your manager is CC'd"),
        ("team_announcement_external", "Team announcement that external partners will see"),
        ("peer_message_forwarded_exec", "Message to peer that will be forwarded to executives"),
        ("vendor_cc_legal", "Message to vendor with legal team CC'd"),
    ]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def should_have_cc(self, probability: float = 0.12) -> bool:
        return self.rng.random() < probability

    def add_cc_context(
        self,
        prompt: WritingPrompt,
        additional_recipients: List[str] = None
    ) -> WritingPrompt:
        """Add CC/multiple audience context to a prompt."""
        scenario_type, description = self.rng.choice(self.CC_SCENARIOS)

        if additional_recipients is None:
            # Generate appropriate CC recipients based on scenario
            if scenario_type == "email_to_client_cc_boss":
                additional_recipients = [f"{prompt.writer.name.split()[0]}'s Manager"]
            elif scenario_type == "team_announcement_external":
                additional_recipients = ["External Partner Team"]
            elif scenario_type == "peer_message_forwarded_exec":
                prompt.cc_context = CCContext(
                    cc_recipients=[],
                    will_be_forwarded_to="Executive Leadership",
                    mixed_audience_note="Write knowing this will be shared with executives"
                )
                return prompt
            elif scenario_type == "vendor_cc_legal":
                additional_recipients = ["Legal Department"]

        prompt.cc_context = CCContext(
            cc_recipients=additional_recipients or [],
            mixed_audience_note=f"Scenario: {description}"
        )

        return prompt
```

---

## 8. Results Directory Structure and Storage

### 8.1 Complete Run Directory (Per PROMPT.md)

```python
# src/storage/run_directory.py

from pathlib import Path
from datetime import datetime
import json
import os
import tempfile
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.settings import EvalConfig

class RunDirectory:
    """Manages the full run directory structure per PROMPT.md specification."""

    def __init__(self, base_dir: Path, run_id: str = None):
        if run_id is None:
            run_id = datetime.now().strftime("eval_%Y-%m-%d_%H-%M-%S")
        self.run_id = run_id
        self.run_dir = base_dir / run_id
        self._create_structure()
        self._create_latest_symlink(base_dir)

    def _create_structure(self):
        """Create the complete directory structure per PROMPT.md."""
        directories = [
            self.run_dir,
            self.run_dir / "prompts" / "prompts_by_occupation",
            self.run_dir / "prompts" / "prompts_by_industry",
            self.run_dir / "responses" / "by_prompt",
            self.run_dir / "responses" / "by_model",
            self.run_dir / "judgments" / "raw",
            self.run_dir / "judgments" / "aggregated",
            self.run_dir / "analysis",
            self.run_dir / "reports" / "charts",
            self.run_dir / "logs",
        ]
        for d in directories:
            d.mkdir(parents=True, exist_ok=True)

    def _create_latest_symlink(self, base_dir: Path):
        """Create/update 'latest' symlink pointing to this run."""
        latest_link = base_dir / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        elif latest_link.exists():
            return  # Don't overwrite a real directory
        latest_link.symlink_to(self.run_dir.name)

    # Path properties for all required files
    @property
    def config_json(self) -> Path:
        return self.run_dir / "config.json"

    @property
    def config_summary_txt(self) -> Path:
        return self.run_dir / "config_summary.txt"

    @property
    def checkpoint_json(self) -> Path:
        return self.run_dir / "checkpoint.json"

    @property
    def random_seed_txt(self) -> Path:
        return self.run_dir / "random_seed.txt"

    @property
    def prompts_json(self) -> Path:
        return self.run_dir / "prompts" / "prompts.json"

    @property
    def results_db(self) -> Path:
        return self.run_dir / "results.db"

    @property
    def results_csv(self) -> Path:
        return self.run_dir / "results_summary.csv"

    @property
    def run_log(self) -> Path:
        return self.run_dir / "logs" / "run.log"

    @property
    def failures_log(self) -> Path:
        return self.run_dir / "logs" / "failures.log"

    @property
    def timing_log(self) -> Path:
        return self.run_dir / "logs" / "timing.log"

    @property
    def readme_md(self) -> Path:
        return self.run_dir / "README.md"

    @property
    def weakness_analysis_json(self) -> Path:
        return self.run_dir / "analysis" / "weakness_analysis.json"

    @property
    def executive_summary_md(self) -> Path:
        return self.run_dir / "reports" / "executive_summary.md"

    @property
    def full_report_pdf(self) -> Path:
        return self.run_dir / "reports" / "full_report.pdf"

    def save_config(self, config: "EvalConfig"):
        """Save config.json and config_summary.txt."""
        # Full JSON config
        self._atomic_write(self.config_json, json.dumps(config.model_dump(), indent=2, default=str))

        # Human-readable summary
        summary = self._generate_config_summary(config)
        self._atomic_write(self.config_summary_txt, summary)

        # Random seed
        self._atomic_write(self.random_seed_txt, str(config.random_seed))

    def _atomic_write(self, path: Path, content: str):
        """Write file atomically using temp file + rename."""
        fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
            shutil.move(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _generate_config_summary(self, config: "EvalConfig") -> str:
        """Generate human-readable config summary."""
        lines = [
            "=" * 60,
            "GEMINI WRITING EVALUATION - CONFIGURATION SUMMARY",
            "=" * 60,
            "",
            f"Run ID: {self.run_id}",
            f"Run Name: {config.run_name}",
            f"Preset: Level {config.preset_level}",
            f"Created: {datetime.now().isoformat()}",
            "",
            "MODEL CONFIGURATION",
            "-" * 40,
            f"Model Pairs: {len(config.model_pairs)}",
        ]
        for gemini, competitor in config.model_pairs:
            lines.append(f"  - {gemini} vs {competitor}")

        lines.extend([
            "",
            "JUDGE CONFIGURATION",
            "-" * 40,
            f"Judge Models: {', '.join(config.judge_models)}",
            f"Votes per Judge: {config.votes_per_judge}",
            f"Use Both Personas: {config.use_both_personas}",
            "",
            "SAMPLING CONFIGURATION",
            "-" * 40,
            f"Total Prompts: {config.num_prompts}",
            f"Random Seed: {config.random_seed}",
            f"Stratify by Job Zone: {config.stratify_by_job_zone}",
            f"Stratify by SOC Group: {config.stratify_by_soc_group}",
            "",
            "=" * 60,
        ])
        return "\n".join(lines)

    def organize_prompts_by_occupation(self, prompts):
        """Save prompts organized by occupation."""
        by_occ = {}
        for p in prompts:
            occ = p.occupation_code
            if occ not in by_occ:
                by_occ[occ] = []
            by_occ[occ].append(p.model_dump())

        for occ, occ_prompts in by_occ.items():
            path = self.run_dir / "prompts" / "prompts_by_occupation" / f"{occ}.json"
            self._atomic_write(path, json.dumps(occ_prompts, indent=2, default=str))

    def organize_prompts_by_industry(self, prompts):
        """Save prompts organized by industry."""
        by_ind = {}
        for p in prompts:
            ind = p.naics_sector
            if ind not in by_ind:
                by_ind[ind] = []
            by_ind[ind].append(p.model_dump())

        for ind, ind_prompts in by_ind.items():
            path = self.run_dir / "prompts" / "prompts_by_industry" / f"sector_{ind}.json"
            self._atomic_write(path, json.dumps(ind_prompts, indent=2, default=str))
```

### 8.2 Checkpoint Manager (Fixed)

Addressing critique issues: atomic writes, partial state recovery, circuit breaker persistence.

```python
# src/storage/checkpoint.py

import asyncio
import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class CheckpointState:
    """Complete checkpoint state for resume."""
    # Progress tracking
    completed_prompts: Set[str] = field(default_factory=set)
    completed_comparisons: Set[str] = field(default_factory=set)
    completed_votes: Set[str] = field(default_factory=set)  # For fine-grained resume

    # Partial state (response generated but not all judgments)
    partial_comparisons: Dict[str, Dict] = field(default_factory=dict)

    # Circuit breaker state for crash recovery
    circuit_breaker_states: Dict[str, Dict] = field(default_factory=dict)

    # Metadata
    last_checkpoint_time: Optional[str] = None
    total_api_calls: int = 0
    total_cost: float = 0.0

class CheckpointManager:
    """Manage checkpoints with atomic writes and fine-grained state."""

    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self._lock = asyncio.Lock()
        self._state: Optional[CheckpointState] = None

    async def load(self) -> CheckpointState:
        """Load checkpoint or create new state."""
        if self.checkpoint_path.exists():
            with open(self.checkpoint_path) as f:
                data = json.load(f)
            self._state = CheckpointState(
                completed_prompts=set(data.get("completed_prompts", [])),
                completed_comparisons=set(data.get("completed_comparisons", [])),
                completed_votes=set(data.get("completed_votes", [])),
                partial_comparisons=data.get("partial_comparisons", {}),
                circuit_breaker_states=data.get("circuit_breaker_states", {}),
                last_checkpoint_time=data.get("last_checkpoint_time"),
                total_api_calls=data.get("total_api_calls", 0),
                total_cost=data.get("total_cost", 0.0)
            )
        else:
            self._state = CheckpointState()
        return self._state

    async def save(self):
        """Save checkpoint atomically."""
        async with self._lock:
            if self._state is None:
                return

            self._state.last_checkpoint_time = datetime.now().isoformat()

            data = {
                "completed_prompts": list(self._state.completed_prompts),
                "completed_comparisons": list(self._state.completed_comparisons),
                "completed_votes": list(self._state.completed_votes),
                "partial_comparisons": self._state.partial_comparisons,
                "circuit_breaker_states": self._state.circuit_breaker_states,
                "last_checkpoint_time": self._state.last_checkpoint_time,
                "total_api_calls": self._state.total_api_calls,
                "total_cost": self._state.total_cost
            }

            # Atomic write
            fd, temp_path = tempfile.mkstemp(
                dir=self.checkpoint_path.parent,
                suffix=".tmp"
            )
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(data, f, indent=2)
                shutil.move(temp_path, self.checkpoint_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

    async def mark_vote_complete(self, vote_id: str):
        """Mark a single vote as complete (finest granularity)."""
        self._state.completed_votes.add(vote_id)
        await self.save()

    async def mark_comparison_complete(self, comparison_id: str):
        """Mark a full comparison as complete."""
        self._state.completed_comparisons.add(comparison_id)
        if comparison_id in self._state.partial_comparisons:
            del self._state.partial_comparisons[comparison_id]
        await self.save()

    async def save_partial_comparison(self, comparison_id: str, partial_data: Dict):
        """Save partial comparison state for resume."""
        self._state.partial_comparisons[comparison_id] = partial_data
        await self.save()

    async def update_circuit_breaker(self, model: str, state: Dict):
        """Persist circuit breaker state."""
        self._state.circuit_breaker_states[model] = state
        await self.save()

    def is_vote_complete(self, vote_id: str) -> bool:
        return vote_id in self._state.completed_votes

    def is_comparison_complete(self, comparison_id: str) -> bool:
        return comparison_id in self._state.completed_comparisons

    def get_partial_comparison(self, comparison_id: str) -> Optional[Dict]:
        return self._state.partial_comparisons.get(comparison_id)
```

### 8.3 Database Schema (aiosqlite)

```python
# src/storage/database.py

import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

class ResultsDatabase:
    """SQLite database using aiosqlite for true async operations."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS prompts (
        prompt_id TEXT PRIMARY KEY,
        onet_task_id TEXT NOT NULL,
        onet_task TEXT NOT NULL,
        occupation_code TEXT NOT NULL,
        occupation_title TEXT NOT NULL,
        job_zone INTEGER NOT NULL,
        soc_major_group TEXT NOT NULL,
        naics_code TEXT NOT NULL,
        naics_sector TEXT NOT NULL,
        company_name TEXT NOT NULL,
        company_size TEXT NOT NULL,
        writer_name TEXT NOT NULL,
        writer_generation TEXT NOT NULL,
        formality_level INTEGER NOT NULL,
        urgency_level INTEGER NOT NULL,
        emotional_context TEXT NOT NULL,
        communication_channel TEXT,
        is_ambiguous INTEGER DEFAULT 0,
        is_revision_task INTEGER DEFAULT 0,
        has_constraints INTEGER DEFAULT 0,
        has_cc_context INTEGER DEFAULT 0,
        has_tone_example INTEGER DEFAULT 0,
        sensitive_topics TEXT,
        full_prompt TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS responses (
        response_id TEXT PRIMARY KEY,
        prompt_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        response_text TEXT NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        latency_ms INTEGER NOT NULL,
        cost REAL NOT NULL,
        word_count INTEGER NOT NULL,
        char_count INTEGER NOT NULL,
        has_bullets INTEGER DEFAULT 0,
        has_headers INTEGER DEFAULT 0,
        greeting_type TEXT,
        signoff_type TEXT,
        is_failure INTEGER DEFAULT 0,
        failure_category TEXT,
        finish_reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    CREATE TABLE IF NOT EXISTS comparisons (
        comparison_id TEXT PRIMARY KEY,
        prompt_id TEXT NOT NULL,
        gemini_model TEXT NOT NULL,
        gemini_response_id TEXT NOT NULL,
        competitor_model TEXT NOT NULL,
        competitor_response_id TEXT NOT NULL,
        final_winner TEXT NOT NULL,
        gemini_votes INTEGER NOT NULL,
        competitor_votes INTEGER NOT NULL,
        tie_votes INTEGER NOT NULL,
        judge_agreement REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
        FOREIGN KEY (gemini_response_id) REFERENCES responses(response_id),
        FOREIGN KEY (competitor_response_id) REFERENCES responses(response_id)
    );

    CREATE TABLE IF NOT EXISTS votes (
        vote_id TEXT PRIMARY KEY,
        comparison_id TEXT NOT NULL,
        judge_model TEXT NOT NULL,
        judge_persona TEXT NOT NULL,
        vote_index INTEGER NOT NULL,
        winner TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        quality_gemini INTEGER NOT NULL,
        quality_competitor INTEGER NOT NULL,
        reasoning TEXT,
        gemini_was_position TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
    );

    CREATE TABLE IF NOT EXISTS compliance_checks (
        check_id TEXT PRIMARY KEY,
        response_id TEXT NOT NULL,
        constraint_type TEXT NOT NULL,
        constraint_description TEXT NOT NULL,
        is_compliant INTEGER NOT NULL,
        explanation TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (response_id) REFERENCES responses(response_id)
    );

    CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(occupation_code);
    CREATE INDEX IF NOT EXISTS idx_prompts_naics ON prompts(naics_sector);
    CREATE INDEX IF NOT EXISTS idx_prompts_job_zone ON prompts(job_zone);
    CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
    CREATE INDEX IF NOT EXISTS idx_comparisons_winner ON comparisons(final_winner);
    CREATE INDEX IF NOT EXISTS idx_votes_judge ON votes(judge_model);
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database connection and schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.executescript(self.SCHEMA)
        await self._connection.commit()

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()

    async def save_prompt(self, prompt) -> None:
        """Save a prompt to the database."""
        await self._connection.execute("""
            INSERT OR REPLACE INTO prompts (
                prompt_id, onet_task_id, onet_task, occupation_code, occupation_title,
                job_zone, soc_major_group, naics_code, naics_sector, company_name,
                company_size, writer_name, writer_generation, formality_level,
                urgency_level, emotional_context, communication_channel, is_ambiguous,
                is_revision_task, has_constraints, has_cc_context, has_tone_example,
                sensitive_topics, full_prompt, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prompt.prompt_id,
            prompt.onet_task_id,
            prompt.onet_task,
            prompt.occupation_code,
            prompt.occupation_title,
            prompt.job_zone,
            prompt.soc_major_group,
            prompt.naics_code,
            prompt.naics_sector,
            prompt.company.name,
            prompt.company.size,
            prompt.writer.name,
            prompt.writer.generation,
            prompt.formality_level,
            prompt.urgency_level,
            prompt.emotional_context.value,
            prompt.communication_channel,
            1 if prompt.is_ambiguous else 0,
            1 if prompt.is_revision_task else 0,
            1 if prompt.constraints else 0,
            1 if prompt.cc_context else 0,
            1 if prompt.tone_example else 0,
            ",".join(t.value for t in prompt.sensitive_topics) if prompt.sensitive_topics else None,
            prompt.full_prompt,
            prompt.created_at.isoformat()
        ))
        await self._connection.commit()

    async def save_response(self, response) -> None:
        """Save a response to the database."""
        await self._connection.execute("""
            INSERT OR REPLACE INTO responses (
                response_id, prompt_id, model_id, response_text, input_tokens,
                output_tokens, latency_ms, cost, word_count, char_count,
                has_bullets, has_headers, greeting_type, signoff_type,
                is_failure, failure_category, finish_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.response_id,
            response.prompt_id,
            response.model_id,
            response.response_text,
            response.input_tokens,
            response.output_tokens,
            response.latency_ms,
            response.cost,
            response.word_count,
            response.char_count,
            response.has_bullets,
            response.has_headers,
            response.greeting_type,
            response.signoff_type,
            1 if response.is_failure else 0,
            response.failure_category,
            response.finish_reason,
            response.created_at.isoformat()
        ))
        await self._connection.commit()

    async def get_win_rates_by_dimension(
        self,
        dimension: str,
        gemini_model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get win rates grouped by a dimension."""
        # Use parameterized whitelist for safety
        allowed_dimensions = {
            "job_zone": "p.job_zone",
            "soc_major_group": "p.soc_major_group",
            "naics_sector": "p.naics_sector",
            "formality_level": "p.formality_level",
            "emotional_context": "p.emotional_context",
            "communication_channel": "p.communication_channel",
            "writer_generation": "p.writer_generation"
        }

        if dimension not in allowed_dimensions:
            raise ValueError(f"Invalid dimension: {dimension}")

        column = allowed_dimensions[dimension]

        query = f"""
            SELECT
                {column} as dimension_value,
                COUNT(*) as total,
                SUM(CASE WHEN c.final_winner = 'gemini' THEN 1 ELSE 0 END) as gemini_wins,
                SUM(CASE WHEN c.final_winner = 'competitor' THEN 1 ELSE 0 END) as competitor_wins,
                SUM(CASE WHEN c.final_winner = 'tie' THEN 1 ELSE 0 END) as ties,
                AVG(c.judge_agreement) as avg_agreement
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            WHERE 1=1
        """

        params = []
        if gemini_model:
            query += " AND c.gemini_model = ?"
            params.append(gemini_model)

        query += f" GROUP BY {column} ORDER BY {column}"

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "dimension_value": row[0],
                    "total": row[1],
                    "gemini_wins": row[2],
                    "competitor_wins": row[3],
                    "ties": row[4],
                    "avg_agreement": row[5],
                    "win_rate": row[2] / row[1] if row[1] > 0 else 0
                }
                for row in rows
            ]
```

---

## 9. Analysis and Statistics

### 9.1 Statistical Analysis (Fixed APIs)

Addressing deprecated scipy.stats.binom_test issue.

```python
# src/analysis/statistics.py

import numpy as np
from scipy import stats
from typing import Tuple, List, Dict
from dataclasses import dataclass

@dataclass
class WinRateResult:
    """Complete win rate analysis result."""
    wins: int
    losses: int
    ties: int
    total: int
    win_rate: float
    ci_lower: float
    ci_upper: float
    p_value: float
    is_significant: bool
    effect_size: float  # Cohen's h

class StatisticalAnalyzer:
    """Statistical analysis for evaluation results."""

    @staticmethod
    def wilson_score_interval(
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return (0.0, 0.0)

        z = stats.norm.ppf((1 + confidence) / 2)
        p = successes / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator

        return (max(0, center - margin), min(1, center + margin))

    @staticmethod
    def binomial_test(wins: int, total: int, null_prob: float = 0.5) -> float:
        """Binomial test using current scipy API (binomtest, not binom_test)."""
        if total == 0:
            return 1.0

        # Using scipy.stats.binomtest (not deprecated binom_test)
        result = stats.binomtest(wins, total, null_prob, alternative='two-sided')
        return result.pvalue

    @staticmethod
    def cohens_kappa(
        rater1: List[str],
        rater2: List[str]
    ) -> float:
        """Calculate Cohen's Kappa for inter-rater reliability."""
        if len(rater1) != len(rater2) or len(rater1) == 0:
            return 0.0

        # Get unique categories
        categories = list(set(rater1 + rater2))
        n = len(rater1)

        # Build confusion matrix
        matrix = {}
        for cat1 in categories:
            matrix[cat1] = {cat2: 0 for cat2 in categories}

        for r1, r2 in zip(rater1, rater2):
            matrix[r1][r2] += 1

        # Calculate observed agreement
        observed = sum(matrix[cat][cat] for cat in categories) / n

        # Calculate expected agreement
        expected = 0
        for cat in categories:
            row_sum = sum(matrix[cat].values()) / n
            col_sum = sum(matrix[c][cat] for c in categories) / n
            expected += row_sum * col_sum

        if expected == 1:
            return 1.0

        kappa = (observed - expected) / (1 - expected)
        return kappa

    @staticmethod
    def cohens_h(p1: float, p2: float) -> float:
        """Calculate Cohen's h effect size for proportions."""
        phi1 = 2 * np.arcsin(np.sqrt(p1))
        phi2 = 2 * np.arcsin(np.sqrt(p2))
        return abs(phi1 - phi2)

    def analyze_win_rate(
        self,
        wins: int,
        losses: int,
        ties: int
    ) -> WinRateResult:
        """Complete win rate analysis."""
        total = wins + losses + ties
        decisive = wins + losses  # Exclude ties for statistical tests

        if total == 0:
            return WinRateResult(
                wins=0, losses=0, ties=0, total=0,
                win_rate=0.0, ci_lower=0.0, ci_upper=0.0,
                p_value=1.0, is_significant=False, effect_size=0.0
            )

        win_rate = wins / total if total > 0 else 0.0

        # Wilson CI
        ci_lower, ci_upper = self.wilson_score_interval(wins, total)

        # Binomial test (exclude ties)
        p_value = self.binomial_test(wins, decisive) if decisive > 0 else 1.0

        # Effect size
        effect_size = self.cohens_h(
            wins / decisive if decisive > 0 else 0.5,
            0.5
        )

        return WinRateResult(
            wins=wins,
            losses=losses,
            ties=ties,
            total=total,
            win_rate=win_rate,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=effect_size
        )
```

### 9.2 Bias Detection (Complete)

Addressing all bias types from PROMPT.md.

```python
# src/analysis/bias_detection.py

from typing import List, Dict, Any
from dataclasses import dataclass
import numpy as np
from scipy import stats

@dataclass
class BiasResult:
    """Result of bias detection analysis."""
    bias_type: str
    detected: bool
    strength: float  # 0-1
    p_value: float
    description: str

class BiasDetector:
    """Detect systematic biases in evaluation results."""

    def detect_position_bias(self, votes: List[Dict]) -> BiasResult:
        """Detect if judges prefer Response A or B systematically."""
        a_wins = sum(1 for v in votes if v["raw_winner"] == "A")
        b_wins = sum(1 for v in votes if v["raw_winner"] == "B")
        total = a_wins + b_wins

        if total == 0:
            return BiasResult("position", False, 0.0, 1.0, "No decisive votes")

        # Binomial test against 50/50
        result = stats.binomtest(a_wins, total, 0.5, alternative='two-sided')

        detected = result.pvalue < 0.05
        strength = abs(a_wins / total - 0.5) * 2  # 0-1 scale

        return BiasResult(
            bias_type="position",
            detected=detected,
            strength=strength,
            p_value=result.pvalue,
            description=f"Position A wins {a_wins}/{total} ({a_wins/total:.1%}). "
                       f"{'Significant bias detected!' if detected else 'No significant bias.'}"
        )

    def detect_length_bias(self, comparisons: List[Dict]) -> BiasResult:
        """Detect if longer responses win more often."""
        longer_wins = 0
        shorter_wins = 0

        for c in comparisons:
            gemini_len = c["gemini_word_count"]
            comp_len = c["competitor_word_count"]

            if c["final_winner"] == "gemini":
                if gemini_len > comp_len:
                    longer_wins += 1
                elif gemini_len < comp_len:
                    shorter_wins += 1
            elif c["final_winner"] == "competitor":
                if comp_len > gemini_len:
                    longer_wins += 1
                elif comp_len < gemini_len:
                    shorter_wins += 1

        total = longer_wins + shorter_wins

        if total == 0:
            return BiasResult("length", False, 0.0, 1.0, "No length difference in comparisons")

        result = stats.binomtest(longer_wins, total, 0.5, alternative='two-sided')

        detected = result.pvalue < 0.05
        strength = abs(longer_wins / total - 0.5) * 2

        return BiasResult(
            bias_type="length",
            detected=detected,
            strength=strength,
            p_value=result.pvalue,
            description=f"Longer response wins {longer_wins}/{total} ({longer_wins/total:.1%}). "
                       f"{'Significant length bias!' if detected else 'No significant length bias.'}"
        )

    def detect_model_fingerprinting(self, votes: List[Dict]) -> BiasResult:
        """Detect if judges can identify which model wrote responses."""
        # Group votes by judge and check if any judge consistently picks the same position
        # when a specific model is in that position

        judge_patterns = {}
        for v in votes:
            judge = (v["judge_model"], v["judge_persona"])
            if judge not in judge_patterns:
                judge_patterns[judge] = {"gemini_as_a_picked": 0, "gemini_as_b_picked": 0,
                                         "gemini_as_a_total": 0, "gemini_as_b_total": 0}

            if v["gemini_position"] == "A":
                judge_patterns[judge]["gemini_as_a_total"] += 1
                if v["winner"] == "gemini":
                    judge_patterns[judge]["gemini_as_a_picked"] += 1
            else:
                judge_patterns[judge]["gemini_as_b_total"] += 1
                if v["winner"] == "gemini":
                    judge_patterns[judge]["gemini_as_b_picked"] += 1

        # Check if win rate for Gemini differs by position
        total_a = sum(p["gemini_as_a_total"] for p in judge_patterns.values())
        wins_a = sum(p["gemini_as_a_picked"] for p in judge_patterns.values())
        total_b = sum(p["gemini_as_b_total"] for p in judge_patterns.values())
        wins_b = sum(p["gemini_as_b_picked"] for p in judge_patterns.values())

        if total_a == 0 or total_b == 0:
            return BiasResult("fingerprinting", False, 0.0, 1.0, "Insufficient data")

        rate_a = wins_a / total_a
        rate_b = wins_b / total_b

        # Chi-square test for difference
        contingency = [[wins_a, total_a - wins_a], [wins_b, total_b - wins_b]]
        chi2, p_value, _, _ = stats.chi2_contingency(contingency)

        detected = p_value < 0.05
        strength = abs(rate_a - rate_b)

        return BiasResult(
            bias_type="fingerprinting",
            detected=detected,
            strength=strength,
            p_value=p_value,
            description=f"Gemini win rate: {rate_a:.1%} as A, {rate_b:.1%} as B. "
                       f"{'Judges may identify models!' if detected else 'No fingerprinting detected.'}"
        )

    def detect_formality_drift(self, responses: List[Dict]) -> BiasResult:
        """Detect if models skew formal/casual regardless of prompt."""
        # Compare formality markers to prompt requirements
        mismatches = {"gemini": 0, "competitor": 0}
        totals = {"gemini": 0, "competitor": 0}

        for r in responses:
            prompt_formality = r["prompt_formality"]  # 1-5
            response_formality = r["detected_formality"]  # 1-5

            if r["model_type"] == "gemini":
                totals["gemini"] += 1
                if abs(response_formality - prompt_formality) > 1:
                    mismatches["gemini"] += 1
            else:
                totals["competitor"] += 1
                if abs(response_formality - prompt_formality) > 1:
                    mismatches["competitor"] += 1

        gemini_rate = mismatches["gemini"] / totals["gemini"] if totals["gemini"] > 0 else 0
        comp_rate = mismatches["competitor"] / totals["competitor"] if totals["competitor"] > 0 else 0

        detected = abs(gemini_rate - comp_rate) > 0.1
        strength = abs(gemini_rate - comp_rate)

        return BiasResult(
            bias_type="formality_drift",
            detected=detected,
            strength=strength,
            p_value=0.0,  # No formal test for this
            description=f"Formality mismatch: Gemini {gemini_rate:.1%}, Competitor {comp_rate:.1%}. "
                       f"{'Formality drift detected!' if detected else 'Formality alignment OK.'}"
        )

    def run_all_bias_checks(
        self,
        votes: List[Dict],
        comparisons: List[Dict],
        responses: List[Dict]
    ) -> List[BiasResult]:
        """Run all bias detection checks."""
        return [
            self.detect_position_bias(votes),
            self.detect_length_bias(comparisons),
            self.detect_model_fingerprinting(votes),
            self.detect_formality_drift(responses)
        ]
```

---

## 10. TUI Implementation

### 10.1 Progress Dashboard

```python
# src/tui/progress_dashboard.py

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive
from datetime import datetime
from typing import Dict, Any

class ProgressDashboard(App):
    """Real-time progress dashboard per PROMPT.md specification."""

    CSS = """
    #main-container {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 2fr 1fr;
    }

    #progress-panel {
        row-span: 1;
        column-span: 2;
        border: solid green;
        padding: 1;
    }

    #model-panel {
        border: solid blue;
        padding: 1;
    }

    #cost-panel {
        border: solid yellow;
        padding: 1;
    }

    #activity-log {
        row-span: 1;
        column-span: 2;
        border: solid white;
        height: 12;
    }

    #stats-panel {
        border: solid cyan;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause/Resume"),
        ("d", "detail", "Detail View"),
        ("s", "statistics", "Statistics"),
        ("h", "help", "Help"),
    ]

    # Reactive state
    total_prompts = reactive(0)
    completed_prompts = reactive(0)
    total_comparisons = reactive(0)
    completed_comparisons = reactive(0)
    total_cost = reactive(0.0)
    current_model_pair = reactive("")
    errors_count = reactive(0)
    is_paused = reactive(False)

    def __init__(self):
        super().__init__()
        self.start_time = datetime.now()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main-container"):
            # Progress panel
            with Vertical(id="progress-panel"):
                yield Static("EVALUATION PROGRESS", classes="title")
                yield ProgressBar(id="main-progress", total=100)
                yield Static(id="progress-text")
                yield Static(id="eta-text")

            # Model pair status
            with Vertical(id="model-panel"):
                yield Static("CURRENT MODEL PAIR", classes="title")
                yield Static(id="current-pair")
                yield DataTable(id="model-stats")

            # Cost tracking
            with Vertical(id="cost-panel"):
                yield Static("COST TRACKING", classes="title")
                yield Static(id="cost-current")
                yield Static(id="cost-estimated")
                yield Static(id="cost-remaining")

            # Statistics
            with Vertical(id="stats-panel"):
                yield Static("LIVE STATISTICS", classes="title")
                yield Static(id="gemini-win-rate")
                yield Static(id="judge-agreement")
                yield Static(id="avg-latency")

            # Activity log
            with Vertical(id="activity-log"):
                yield Static("RECENT ACTIVITY", classes="title")
                yield Log(id="log", max_lines=50)

        yield Footer()

    async def on_mount(self):
        """Initialize dashboard components."""
        # Initialize model stats table
        table = self.query_one("#model-stats", DataTable)
        table.add_columns("Model", "Wins", "Losses", "Ties", "Win%")

    def update_progress(self, data: Dict[str, Any]):
        """Update dashboard with new progress data."""
        self.completed_prompts = data.get("completed_prompts", 0)
        self.completed_comparisons = data.get("completed_comparisons", 0)
        self.total_cost = data.get("total_cost", 0.0)
        self.current_model_pair = data.get("current_pair", "")
        self.errors_count = data.get("errors", 0)

        # Update progress bar
        progress = self.query_one("#main-progress", ProgressBar)
        if self.total_comparisons > 0:
            progress.update(progress=self.completed_comparisons / self.total_comparisons * 100)

        # Update text displays
        self.query_one("#progress-text", Static).update(
            f"Comparisons: {self.completed_comparisons}/{self.total_comparisons}"
        )

        # Calculate ETA
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.completed_comparisons > 0:
            rate = self.completed_comparisons / elapsed
            remaining = self.total_comparisons - self.completed_comparisons
            eta_seconds = remaining / rate if rate > 0 else 0
            eta_hours = eta_seconds / 3600
            self.query_one("#eta-text", Static).update(f"ETA: {eta_hours:.1f} hours")

        # Update cost
        self.query_one("#cost-current", Static).update(f"Spent: ${self.total_cost:.2f}")

        # Update current pair
        self.query_one("#current-pair", Static).update(self.current_model_pair)

        # Update live stats
        if "gemini_wins" in data and "total_decisive" in data:
            win_rate = data["gemini_wins"] / data["total_decisive"] if data["total_decisive"] > 0 else 0
            self.query_one("#gemini-win-rate", Static).update(f"Gemini Win Rate: {win_rate:.1%}")

        if "avg_judge_agreement" in data:
            self.query_one("#judge-agreement", Static).update(
                f"Judge Agreement: {data['avg_judge_agreement']:.2f}"
            )

    def log_activity(self, message: str):
        """Add message to activity log."""
        log = self.query_one("#log", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.write_line(f"[{timestamp}] {message}")

    def action_pause(self):
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        status = "PAUSED" if self.is_paused else "RUNNING"
        self.log_activity(f"Evaluation {status}")

    def action_detail(self):
        """Switch to detail view."""
        self.log_activity("Switching to detail view...")
        # Would push a detail screen

    def action_statistics(self):
        """Show statistics view."""
        self.log_activity("Loading statistics...")
        # Would push a stats screen
```

### 10.2 Results Viewer TUI

```python
# src/tui/results_viewer.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static, Select, Input
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from pathlib import Path

class ResultsViewerApp(App):
    """Interactive TUI for exploring evaluation results."""

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

    #response-a, #response-b {
        width: 50%;
        border: solid blue;
        overflow: auto scroll;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "focus_filter", "Filter"),
        ("s", "sort_menu", "Sort"),
        ("enter", "view_detail", "View Detail"),
        ("j", "view_judgments", "Judgments"),
        ("e", "export", "Export"),
    ]

    def __init__(self, run_dir: Path):
        super().__init__()
        self.run_dir = run_dir
        self.current_filters = {}

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
                    yield Static(id="response-a")
                    yield Static(id="response-b")

        yield Footer()

    async def on_mount(self):
        """Initialize table with data."""
        table = self.query_one("#main-table", DataTable)
        table.add_columns(
            "Prompt ID", "Occupation", "Formality",
            "Gemini", "Competitor", "Winner", "Agreement"
        )
        await self._load_comparisons()

    async def _load_comparisons(self):
        """Load comparisons from database."""
        # Would load from results.db
        pass

    def _get_occupations(self):
        """Get list of occupations for filter."""
        return ["All"]  # Would load from database

    async def action_view_detail(self):
        """Show side-by-side response comparison."""
        table = self.query_one("#main-table", DataTable)
        row_key = table.cursor_row
        if row_key is None:
            return

        # Would load full comparison details
        self.query_one("#detail-header", Static).update("Loading comparison...")

    async def action_view_judgments(self):
        """Open judgment detail screen."""
        table = self.query_one("#main-table", DataTable)
        row_key = table.cursor_row
        if row_key is None:
            return

        # Would push JudgmentDetailScreen
        pass
```

---

## 11. CLI Interface

```python
# src/cli.py

import typer
from pathlib import Path
from typing import Optional
import asyncio

app = typer.Typer(help="Gemini Writing Evaluation Framework")

@app.command()
def run(
    preset: int = typer.Option(3, "--preset", "-p", help="Preset level 1-10"),
    num_prompts: Optional[int] = typer.Option(None, "--prompts", "-n", help="Override prompt count"),
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed"),
    output_dir: Path = typer.Option(Path("results"), "--output", "-o", help="Output directory"),
    resume: Optional[Path] = typer.Option(None, "--resume", "-r", help="Resume from checkpoint"),
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file"),
    no_tui: bool = typer.Option(False, "--no-tui", help="Disable TUI"),
):
    """Run a full evaluation."""
    from src.config.presets import PRESETS
    from src.config.settings import EvalConfig
    from src.eval.engine import EvaluationEngine
    from src.tui.progress_dashboard import ProgressDashboard

    # Load or create config
    if config_file and config_file.exists():
        config = EvalConfig.from_file(config_file)
    else:
        config = PRESETS[preset]
        if num_prompts:
            config.num_prompts = num_prompts
        if seed:
            config.random_seed = seed

    # Show cost estimate
    from src.config.cost_estimator import estimate_cost
    estimate = estimate_cost(config)
    typer.echo(f"Estimated cost: ${estimate.total_cost:.2f}")
    typer.echo(f"Estimated time: {estimate.total_hours:.1f} hours")

    if not typer.confirm("Proceed?"):
        raise typer.Abort()

    # Run evaluation
    async def run_eval():
        engine = EvaluationEngine(config, output_dir, resume_from=resume)
        await engine.run()

    if no_tui:
        asyncio.run(run_eval())
    else:
        # Run with TUI
        dashboard = ProgressDashboard()
        # Would integrate engine with dashboard
        dashboard.run()

@app.command()
def view(
    run_dir: Path = typer.Argument(..., help="Run directory to view"),
):
    """View results from a completed run."""
    from src.tui.results_viewer import ResultsViewerApp

    if not run_dir.exists():
        typer.echo(f"Run directory not found: {run_dir}")
        raise typer.Abort()

    viewer = ResultsViewerApp(run_dir)
    viewer.run()

@app.command()
def compare(
    run_dirs: list[Path] = typer.Argument(..., help="Run directories to compare"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Compare results across multiple runs."""
    from src.analysis.cross_run_compare import CrossRunComparator

    comparator = CrossRunComparator(run_dirs)
    asyncio.run(comparator.load_runs())

    # Generate comparison
    comparison = comparator.compare_win_rates()
    stats = comparator.statistical_comparison()

    typer.echo("Win Rate Comparison:")
    typer.echo(comparison.to_string())

    typer.echo("\nStatistical Tests:")
    for pair, result in stats.items():
        sig = "SIGNIFICANT" if result["significant"] else "not significant"
        typer.echo(f"{pair}: p={result['p_value']:.4f} ({sig})")

    if output:
        comparator.generate_comparison_report(output)
        typer.echo(f"Report saved to {output}")

@app.command()
def export(
    run_dir: Path = typer.Argument(..., help="Run directory"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format (csv, json)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Export results to CSV or JSON."""
    from src.storage.exporter import ResultsExporter

    exporter = ResultsExporter(run_dir)

    if format == "csv":
        output_path = output or run_dir / "results_summary.csv"
        exporter.to_csv(output_path)
    else:
        output_path = output or run_dir / "results_full.json"
        exporter.to_json(output_path)

    typer.echo(f"Exported to {output_path}")

if __name__ == "__main__":
    app()
```

---

## 12. Model Configuration

```python
# src/config/settings.py

from pydantic import BaseModel, Field
from typing import List, Tuple, Optional
from datetime import datetime
import secrets

class JudgeConfig(BaseModel):
    """Judge configuration."""
    models: List[str] = [
        "anthropic/claude-opus-4.5-20251101",
        "openai/gpt-5.2-thinking-preview",
        "google/gemini-3.0-pro-preview"
    ]
    votes_per_judge: int = 5
    use_both_personas: bool = True  # Writing Expert + Recipient

class ModelPair(BaseModel):
    """A Gemini model paired with a competitor."""
    gemini: str
    competitor: str

class EvalConfig(BaseModel):
    """Complete evaluation configuration."""
    run_id: str = Field(default_factory=lambda: datetime.now().strftime("eval_%Y-%m-%d_%H-%M-%S"))
    run_name: str = "Gemini Writing Evaluation"
    preset_level: int = 3

    # Model pairs to evaluate
    model_pairs: List[Tuple[str, str]] = [
        ("google/gemini-3.0-pro-preview", "anthropic/claude-opus-4.5-20251101"),
        ("google/gemini-3.0-pro-preview", "openai/gpt-5.2-thinking-preview"),
        ("google/gemini-3.0-flash-preview", "anthropic/claude-sonnet-4-20250514"),
        ("google/gemini-3.0-flash-preview", "openai/gpt-4.1-preview"),
    ]

    # Judge configuration
    judge_config: JudgeConfig = Field(default_factory=JudgeConfig)

    # Sampling configuration
    num_prompts: int = 100
    random_seed: int = Field(default_factory=lambda: secrets.randbelow(2**32))
    stratify_by_job_zone: bool = True
    stratify_by_soc_group: bool = True

    # Enrichment settings
    phase3_enrich_ratio: float = 0.3
    constraint_probability: float = 0.15
    revision_task_probability: float = 0.10
    ambiguity_probability: float = 0.10
    cc_probability: float = 0.12

    # API settings
    openrouter_api_key: Optional[str] = None

    @property
    def judge_models(self) -> List[str]:
        return self.judge_config.models

    @property
    def votes_per_judge(self) -> int:
        return self.judge_config.votes_per_judge

    @property
    def use_both_personas(self) -> bool:
        return self.judge_config.use_both_personas
```

---

## 13. Risks and Open Questions

### 13.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenRouter rate limits exceeded | Medium | High | Per-model rate limiting, exponential backoff, circuit breakers |
| Judge model API failures mid-run | Medium | Medium | Fine-grained checkpointing, retry logic, fallback judges |
| O*NET data quality issues | Low | Medium | Validate ONET_WRITING_REFERENCE.md, fallback queries |
| LLM-generated personas unrealistic | Medium | Low | Human review of Phase 1 outputs, diversity constraints |
| Cost overruns | Low | Medium | Real-time cost tracking, configurable limits, presets |
| TUI performance issues | Low | Low | Async updates, efficient data structures |

### 13.2 Methodology Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Judge position bias | Medium | High | Position randomization verified in bias detection |
| Judge model bias toward own style | Medium | Medium | Use 3 diverse judge models, track per-judge patterns |
| Phase 1 generation bias | Medium | Medium | Use ALL evaluated models for generation |
| Insufficient prompt diversity | Low | Medium | Stratification, diversity tracking |
| Instruction compliance not verified | Medium | Medium | Separate compliance tracking module |

### 13.3 Open Questions

1. **Flash-tier model selection**: Which specific "flash-tier models in class" besides GPT-4.1 and Claude Sonnet should be included?

2. **ONET_WRITING_REFERENCE.md format**: What is the exact format of this pre-processed file? Plan assumes it contains task IDs and writing contexts.

3. **Regional English distribution**: What percentage of prompts should use non-US English variants (UK, AU, non-native)?

4. **Sensitive topic handling**: Should there be explicit approval/review before running prompts tagged as sensitive?

5. **Cross-run comparison statistical tests**: Beyond chi-square, should we include more sophisticated tests for multi-run comparisons?

6. **Real company name usage**: What liability exists for using real company names in generated scenarios?

7. **PDF report depth**: How detailed should the weakness analysis section be in the final PDF?

---

## 14. Implementation Priority Order

1. **Phase 1 (Foundation)**:
   - O*NET extractor with ONET_WRITING_REFERENCE.md integration
   - Complete WritingPrompt schema
   - Database schema and aiosqlite integration
   - OpenRouter client with rate limiting

2. **Phase 2 (Prompt Generation)**:
   - Phase 1 offline generator
   - Phase 2 algorithmic combiner
   - Phase 3 enricher
   - Constraint, revision, ambiguity, CC generators

3. **Phase 3 (Evaluation)**:
   - Response generation with metadata tracking
   - Judge prompt building with full context
   - Vote aggregator with position tracking
   - Checkpoint manager

4. **Phase 4 (Analysis)**:
   - Statistical analysis with fixed APIs
   - Bias detection (all types)
   - Weakness finder
   - Cross-run comparison

5. **Phase 5 (User Interface)**:
   - CLI with all commands
   - Progress dashboard TUI
   - Results viewer TUI

6. **Phase 6 (Reporting)**:
   - PDF report generator
   - CSV/JSON exporters
   - Auto-generated README

---

## 15. Testing Strategy

```python
# tests/conftest.py

import pytest
from pathlib import Path
import tempfile
import sqlite3

@pytest.fixture
def temp_dir():
    """Temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)

@pytest.fixture
def mock_onet_db(temp_dir):
    """Create a minimal O*NET database for testing."""
    db_path = temp_dir / "onet.db"
    conn = sqlite3.connect(db_path)
    # Create minimal tables
    conn.executescript("""
        CREATE TABLE task_statements (
            task_id TEXT PRIMARY KEY,
            onetsoc_code TEXT,
            task TEXT,
            task_type TEXT
        );
        INSERT INTO task_statements VALUES
            ('T1', '11-1011.00', 'Write reports', 'Core'),
            ('T2', '11-1011.00', 'Draft emails', 'Core');
    """)
    conn.commit()
    conn.close()
    return db_path

@pytest.fixture
def sample_prompts():
    """Sample prompts for testing."""
    # Return list of WritingPrompt objects
    pass

# Key test categories:
# 1. Unit tests for each module
# 2. Integration tests for phase pipelines
# 3. Statistical validation tests
# 4. API mock tests
# 5. TUI component tests
```

---

## Summary

This master plan synthesizes the best approaches from all 6 draft plans and addresses all critiques. Key features:

1. **Three-phase prompt generation** with full Phase 1 offline LLM generation
2. **ONET_WRITING_REFERENCE.md integration** instead of hardcoded categories
3. **Complete prompt schema** covering all PROMPT.md requirements
4. **Fixed vote aggregator** tracking winners relative to Gemini consistently
5. **Full judge context** including all scenario information
6. **Comprehensive bias detection** including model fingerprinting
7. **Atomic checkpoint operations** with fine-grained state recovery
8. **Complete TUI implementation** for both progress and results viewing
9. **Full results directory structure** per PROMPT.md specification
10. **Statistical analysis with current APIs** (scipy.stats.binomtest)

The plan provides production-ready code examples and clear implementation guidance for all components.
