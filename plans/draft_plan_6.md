# Gemini Writing Evaluation Framework - Implementation Plan (Draft 6)

## Executive Summary

This document presents a comprehensive implementation plan for the Gemini Writing Evaluation Framework - a robust, scalable system for comparing Gemini 3.0 Pro/Flash against competing frontier LLMs on realistic professional writing tasks derived from the O*NET database.

---

## Part 1: System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GEMINI WRITING EVAL FRAMEWORK                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   O*NET DB   │───▶│    Prompt    │───▶│   Response   │───▶│  Judging  │ │
│  │   Pipeline   │    │  Generator   │    │  Collector   │    │   Engine  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                   │                   │                   │       │
│         ▼                   ▼                   ▼                   ▼       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         SQLite Results Store                          │  │
│  │   (prompts, responses, judgments, metadata, checkpoints, failures)    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Analysis   │───▶│    Report    │───▶│     TUI      │                  │
│  │    Engine    │    │  Generator   │    │   Viewer     │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Components

| Component | Responsibility | Key Technologies |
|-----------|---------------|------------------|
| **O*NET Pipeline** | Extract, transform, enrich task data | SQLite, Pydantic |
| **Prompt Generator** | Create diverse, realistic writing prompts | LLM APIs, NAICS mapping |
| **Response Collector** | Gather model outputs with retry logic | httpx, asyncio |
| **Judging Engine** | Multi-judge ensemble evaluation | Best-of-5, majority voting |
| **Results Store** | Persist all artifacts with checkpointing | SQLite, JSON |
| **Analysis Engine** | Statistical analysis, bias detection | scipy, pandas |
| **Report Generator** | PDF reports with visualizations | plotly, weasyprint |
| **TUI Viewer** | Interactive results exploration | textual/rich |

### 1.3 Directory Structure

```
gemini-writing-eval/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── models.py                 # Pydantic models for all data structures
│   ├── cli.py                    # CLI entry point
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py     # O*NET database access
│   │   ├── task_classifier.py    # Writing task categorization
│   │   ├── naics_mapper.py       # Industry mapping
│   │   └── company_sampler.py    # Real company selection
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py          # Main prompt generation orchestrator
│   │   ├── persona_builder.py    # Writer/recipient persona creation
│   │   ├── context_enricher.py   # LLM-based context enrichment
│   │   ├── diversity_sampler.py  # Multi-dimensional sampling
│   │   └── templates.py          # Prompt templates and schemas
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── runner.py             # Main evaluation orchestrator
│   │   ├── api_client.py         # OpenRouter API wrapper
│   │   ├── response_collector.py # Model response collection
│   │   ├── judge.py              # Judging logic
│   │   └── aggregator.py         # Vote aggregation
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLite operations
│   │   ├── checkpoint.py         # Checkpoint/resume logic
│   │   └── exporter.py           # CSV/JSON export
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py         # Win rates, confidence intervals
│   │   ├── bias_detector.py      # Systematic bias analysis
│   │   ├── weakness_finder.py    # Gemini weakness identification
│   │   └── visualizations.py     # Charts and graphs
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py      # PDF report creation
│   │   └── templates/            # Report templates
│   │
│   └── tui/
│       ├── __init__.py
│       ├── app.py                # Main TUI application
│       ├── screens/              # TUI screens
│       └── widgets/              # Custom widgets
│
├── db/
│   └── onet.db                   # O*NET 30.1 database
│
├── results/                      # Eval run directories
│   └── eval_YYYY-MM-DD_HH-MM-SS/
│
├── tests/
├── pyproject.toml
└── README.md
```

---

## Part 2: Data Pipeline - O*NET to Prompts

### 2.1 O*NET Data Extraction

#### 2.1.1 Task Extraction Strategy

The O*NET database contains 18,796 task statements across 923 occupations. We extract writing-relevant tasks using a multi-layer approach:

**Layer 1: Explicit Writing Keywords**
```python
EXPLICIT_WRITING_PATTERNS = [
    r'\bwrite\b', r'\bdraft\b', r'\bcompose\b', r'\bauthor\b',
    r'\bdocument\b', r'\bprepare\s+report', r'\bprepare\s+proposal',
    r'\bcorrespond', r'\bemail\b', r'\bletter\b', r'\bmemo\b'
]
```

**Layer 2: Implicit Writing Tasks**
```python
IMPLICIT_WRITING_PATTERNS = [
    r'\bnotify\b', r'\binform\b', r'\bcommunicate\b',
    r'\bpresent\s+finding', r'\bsummariz', r'\brecommend\b',
    r'\bpropos', r'\bnegotiat', r'\badvise\b'
]
```

**Layer 3: Communication Context Scoring**
```sql
-- High email frequency (element_id = '4.C.1.a.2.h')
-- High written correspondence frequency (element_id = '4.C.1.a.2.j')
-- High written expression ability (element_id = '1.A.1.a.4')
```

#### 2.1.2 Task Extraction SQL

```python
class ONetExtractor:
    """Extract writing-relevant tasks from O*NET database."""

    WRITING_TASK_QUERY = """
    SELECT
        t.task_id,
        t.onetsoc_code,
        o.title as occupation_title,
        o.description as occupation_description,
        t.task,
        t.task_type,
        jz.job_zone,
        COALESCE(email_wc.data_value, 0) as email_frequency,
        COALESCE(letter_wc.data_value, 0) as letter_frequency,
        COALESCE(writing_skill.data_value, 0) as writing_skill_importance
    FROM task_statements t
    JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
    LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
    LEFT JOIN work_context email_wc ON t.onetsoc_code = email_wc.onetsoc_code
        AND email_wc.element_id = '4.C.1.a.2.h' AND email_wc.scale_id = 'CX'
    LEFT JOIN work_context letter_wc ON t.onetsoc_code = letter_wc.onetsoc_code
        AND letter_wc.element_id = '4.C.1.a.2.j' AND letter_wc.scale_id = 'CX'
    LEFT JOIN skills writing_skill ON t.onetsoc_code = writing_skill.onetsoc_code
        AND writing_skill.element_id = '2.A.1.c' AND writing_skill.scale_id = 'IM'
    WHERE {writing_filter}
    ORDER BY writing_skill_importance DESC, email_frequency DESC
    """
```

### 2.2 Writing Task Classification

Rather than hardcoding categories, we use a dynamic classification system that emerges from the task content:

```python
@dataclass
class WritingTaskClassification:
    """Dynamic classification derived from task content."""

    # Primary classification (inferred from keywords)
    primary_type: str  # e.g., "documentation", "correspondence", "report"

    # Communication attributes (inferred from context)
    formality_signal: float  # 0.0-1.0 based on occupation/task signals
    urgency_signal: float    # 0.0-1.0 based on task verbs
    audience_size_signal: str  # "individual", "group", "public"

    # Inferred medium
    likely_medium: str  # "email", "memo", "report", "letter", "presentation"

    # Confidence scores
    classification_confidence: float

class TaskClassifier:
    """Classify tasks based on content analysis."""

    def classify(self, task: str, occupation: str, job_zone: int) -> WritingTaskClassification:
        # Use regex patterns to identify primary type
        primary_type = self._detect_primary_type(task)

        # Use job zone and occupation to infer formality
        formality_signal = self._infer_formality(job_zone, occupation, task)

        # Use verb analysis to infer urgency
        urgency_signal = self._analyze_urgency_verbs(task)

        # Detect likely audience size
        audience_size_signal = self._detect_audience(task)

        # Infer communication medium
        likely_medium = self._infer_medium(task, primary_type)

        return WritingTaskClassification(...)
```

### 2.3 NAICS Industry Mapping

Since O*NET doesn't contain NAICS codes directly, we implement a mapping strategy:

```python
class NAICSMapper:
    """Map occupations to industries using SOC-NAICS crosswalk."""

    # SOC Major Group to likely NAICS sectors mapping
    SOC_TO_NAICS_WEIGHTS = {
        "11": {  # Management
            "52": 0.15,  # Finance
            "54": 0.20,  # Professional Services
            "62": 0.10,  # Healthcare
            "31-33": 0.15,  # Manufacturing
            "44-45": 0.10,  # Retail
            "other": 0.30
        },
        "13": {  # Business/Financial
            "52": 0.40,  # Finance
            "54": 0.30,  # Professional Services
            "other": 0.30
        },
        # ... additional mappings for all 22 SOC groups
    }

    # Major NAICS sectors for sampling
    NAICS_SECTORS = {
        "11": "Agriculture, Forestry, Fishing and Hunting",
        "21": "Mining, Quarrying, and Oil and Gas Extraction",
        "22": "Utilities",
        "23": "Construction",
        "31-33": "Manufacturing",
        "42": "Wholesale Trade",
        "44-45": "Retail Trade",
        "48-49": "Transportation and Warehousing",
        "51": "Information",
        "52": "Finance and Insurance",
        "53": "Real Estate and Rental and Leasing",
        "54": "Professional, Scientific, and Technical Services",
        "55": "Management of Companies and Enterprises",
        "56": "Administrative and Support Services",
        "61": "Educational Services",
        "62": "Health Care and Social Assistance",
        "71": "Arts, Entertainment, and Recreation",
        "72": "Accommodation and Food Services",
        "81": "Other Services",
        "92": "Public Administration"
    }

    def sample_industry(self, soc_code: str, seed: int) -> tuple[str, str]:
        """Sample a NAICS industry appropriate for the occupation."""
        soc_major = soc_code[:2]
        weights = self.SOC_TO_NAICS_WEIGHTS.get(soc_major, {"other": 1.0})

        rng = random.Random(seed)
        naics = rng.choices(
            list(weights.keys()),
            weights=list(weights.values())
        )[0]

        return naics, self.NAICS_SECTORS.get(naics, "General Business")
```

### 2.4 Real Company Sampling

```python
class CompanySampler:
    """Sample real companies for grounding prompts in reality."""

    # Company database organized by NAICS and size tier
    COMPANIES_BY_NAICS_AND_SIZE = {
        "52": {  # Finance
            "fortune500": ["JPMorgan Chase", "Bank of America", "Wells Fargo", "Citigroup"],
            "midmarket": ["First Republic Bank", "Synchrony Financial", "Ally Financial"],
            "small": ["Local Credit Union (~50 employees)", "Regional Bank (~200 employees)"],
            "startup": ["Fintech startup (~15 employees)", "Payment processor (~30 employees)"]
        },
        "54": {  # Professional Services
            "fortune500": ["Deloitte", "PwC", "McKinsey", "Accenture"],
            "midmarket": ["Grant Thornton", "RSM", "Kroll"],
            "small": ["Regional consulting firm (~75 employees)"],
            "startup": ["Boutique advisory (~8 employees)"]
        },
        # ... extensive mapping for all NAICS sectors
    }

    SIZE_TIERS = ["fortune500", "midmarket", "small", "startup"]
    SIZE_WEIGHTS = [0.25, 0.30, 0.30, 0.15]  # Weighted toward diversity

    def sample_company(
        self,
        naics: str,
        preferred_size: str | None = None,
        seed: int = None
    ) -> CompanyContext:
        """Sample a real company with full metadata."""
        rng = random.Random(seed)

        # Get companies for this industry
        industry_companies = self.COMPANIES_BY_NAICS_AND_SIZE.get(naics, {})

        # Select size tier
        if preferred_size:
            size_tier = preferred_size
        else:
            size_tier = rng.choices(self.SIZE_TIERS, weights=self.SIZE_WEIGHTS)[0]

        # Select company
        company_pool = industry_companies.get(size_tier, ["Generic company"])
        company_name = rng.choice(company_pool)

        return CompanyContext(
            name=company_name,
            naics_code=naics,
            size_tier=size_tier,
            is_public=size_tier in ["fortune500", "midmarket"],
            employee_count_estimate=self._estimate_employees(size_tier),
            hq_location=self._sample_location(rng)
        )
```

---

## Part 3: Prompt Generation Methodology

### 3.1 Three-Phase Generation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROMPT GENERATION PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Phase 1: Offline LLM Generation                                         │
│  ─────────────────────────────────                                       │
│  • Generate persona variations for each O*NET task                       │
│  • Create context templates with demographic diversity                   │
│  • Use same models being evaluated (noted bias consideration)            │
│  • Store in prompt_templates.db                                          │
│                                                                          │
│  Phase 2: Algorithmic Combination                                        │
│  ───────────────────────────────                                         │
│  • Combine O*NET tasks with randomized dimensions                        │
│  • Apply NAICS industry sampling                                         │
│  • Enforce stratification constraints                                    │
│  • Deterministic seeding for reproducibility                             │
│                                                                          │
│  Phase 3: LLM Enrichment                                                 │
│  ─────────────────────────                                               │
│  • Add context-rich details for complex prompts                          │
│  • Generate attachments, prior messages, examples                        │
│  • Apply temporal grounding where appropriate                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Persona Generation System

```python
@dataclass
class WriterPersona:
    """Complete writer persona for prompt context."""

    # Identity
    name: str                          # e.g., "Sarah Chen"
    email: str                         # e.g., "sarah.chen@acme.com"

    # Demographics
    age: int                           # 22-67 range
    generation: str                    # "GenZ", "Millennial", "GenX", "Boomer"

    # Professional context
    job_title: str                     # From O*NET occupation
    seniority_level: str               # "entry", "mid", "senior", "executive"
    years_experience: int

    # Company context
    company: CompanyContext
    department: str | None

    # Communication style signals
    formality_preference: float        # 0.0 (very casual) to 1.0 (very formal)
    verbosity_preference: float        # 0.0 (terse) to 1.0 (detailed)

    # Regional context
    english_variant: str               # "en-US", "en-GB", "en-AU", "non-native"
    location: str

@dataclass
class RecipientPersona:
    """Complete recipient persona for evaluating appropriateness."""

    name: str
    email: str | None

    job_title: str
    relationship_to_writer: str        # "superior", "peer", "subordinate", "external"
    relationship_duration: str         # "first_contact", "new", "established", "long_term"

    seniority_level: str
    english_variant: str

    # For judging context
    expectations_notes: str | None     # What recipient would expect

class PersonaBuilder:
    """Build diverse, realistic personas."""

    # Name pools with demographic diversity
    FIRST_NAMES_BY_DEMO = {
        "GenZ_diverse": ["Aiden", "Zara", "Kai", "Luna", "Jayden", "Aria"],
        "Millennial_diverse": ["Sarah", "Michael", "Jennifer", "David", "Wei", "Priya"],
        "GenX_diverse": ["Karen", "Brian", "Lisa", "Mark", "Kenji", "Maria"],
        "Boomer_diverse": ["Robert", "Linda", "William", "Patricia", "James", "Barbara"]
    }

    LAST_NAMES_DIVERSE = [
        "Chen", "Williams", "Garcia", "Patel", "Kim", "O'Brien", "Müller",
        "Santos", "Nakamura", "Johnson", "Okonkwo", "Petrov", "Ali"
    ]

    def build_writer_persona(
        self,
        occupation: str,
        job_zone: int,
        company: CompanyContext,
        diversity_constraints: dict,
        seed: int
    ) -> WriterPersona:
        """Build a complete writer persona with enforced diversity."""
        rng = random.Random(seed)

        # Sample age based on constraints or naturally
        if "age_range" in diversity_constraints:
            age = rng.randint(*diversity_constraints["age_range"])
        else:
            age = self._sample_age_for_occupation(job_zone, rng)

        generation = self._age_to_generation(age)

        # Sample name matching demographics
        name = self._sample_name(generation, rng)

        # Infer seniority from job zone and age
        seniority = self._infer_seniority(job_zone, age, occupation)

        # Calculate formality preference (influenced by generation and seniority)
        formality = self._calculate_formality_preference(
            generation, seniority, company.size_tier
        )

        return WriterPersona(
            name=name,
            email=self._generate_email(name, company),
            age=age,
            generation=generation,
            job_title=occupation,
            seniority_level=seniority,
            years_experience=self._calculate_experience(age, seniority),
            company=company,
            formality_preference=formality,
            verbosity_preference=rng.uniform(0.3, 0.7),
            english_variant=self._sample_english_variant(rng),
            location=company.hq_location
        )
```

### 3.3 Diversity Sampling Engine

```python
class DiversitySampler:
    """Ensure even distribution across all required dimensions."""

    DIVERSITY_DIMENSIONS = {
        "job_zone": [1, 2, 3, 4, 5],
        "soc_major": list(range(11, 56, 2)),  # 22 major groups
        "generation": ["GenZ", "Millennial", "GenX", "Boomer"],
        "formality": ["very_casual", "casual", "neutral", "formal", "very_formal"],
        "urgency": ["routine", "standard", "elevated", "urgent", "critical"],
        "audience_size": ["individual", "small_group", "department", "company", "public"],
        "relationship": ["first_contact", "new", "established", "long_term"],
        "emotional_context": ["routine", "celebration", "crisis", "conflict", "bad_news"],
        "message_position": ["initial", "reply", "follow_up", "thread_continuation"],
        "english_variant": ["en-US", "en-GB", "en-AU", "non-native"]
    }

    def __init__(self, target_count: int, seed: int):
        self.target_count = target_count
        self.seed = seed
        self.quotas = self._calculate_quotas()
        self.filled = {dim: {val: 0 for val in vals}
                       for dim, vals in self.DIVERSITY_DIMENSIONS.items()}

    def _calculate_quotas(self) -> dict:
        """Calculate per-dimension quotas for even distribution."""
        quotas = {}
        for dim, values in self.DIVERSITY_DIMENSIONS.items():
            quota_per_value = self.target_count // len(values)
            quotas[dim] = {val: quota_per_value for val in values}
        return quotas

    def sample_next(self, available_tasks: list) -> tuple[dict, dict]:
        """Sample next prompt configuration ensuring diversity."""
        # Find dimensions most under-quota
        priority_dims = self._get_priority_dimensions()

        # Filter available tasks to those that can fill priority dimensions
        filtered_tasks = self._filter_by_priority(available_tasks, priority_dims)

        # Sample from filtered set
        task = random.choice(filtered_tasks)

        # Generate diversity attributes
        attributes = self._sample_attributes(priority_dims)

        # Update filled counts
        self._update_filled(attributes)

        return task, attributes

    def get_distribution_report(self) -> dict:
        """Report on achieved distribution across dimensions."""
        report = {}
        for dim, filled_vals in self.filled.items():
            total = sum(filled_vals.values())
            report[dim] = {
                val: {"count": count, "pct": count/total if total > 0 else 0}
                for val, count in filled_vals.items()
            }
        return report
```

### 3.4 Context Enrichment

```python
class ContextEnricher:
    """LLM-based enrichment for context-heavy prompts."""

    async def enrich_prompt(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona,
        enrichment_type: str
    ) -> dict:
        """Add rich context based on enrichment type needed."""

        enrichment_handlers = {
            "attachment": self._generate_attachment_context,
            "prior_message": self._generate_prior_message,
            "meeting_notes": self._generate_meeting_notes,
            "example_to_match": self._generate_style_example,
            "revision_draft": self._generate_draft_to_revise,
            "ambiguous": self._generate_ambiguous_context,
            "competing_objectives": self._generate_competing_objectives,
            "temporal": self._generate_temporal_context
        }

        handler = enrichment_handlers.get(enrichment_type)
        if handler:
            return await handler(base_task, writer, recipient)
        return {}

    async def _generate_attachment_context(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona
    ) -> dict:
        """Generate mock attachment content for the prompt."""

        prompt = f"""Generate realistic attachment context for this writing task.

Task: {base_task}
Writer: {writer.job_title} at {writer.company.name}
Recipient: {recipient.job_title}

Generate a brief summary of what the "attached" document contains.
Include 3-5 specific details (numbers, names, dates) that should be referenced.
Format as if describing an attachment in an email context.

Keep it concise but specific enough to be useful context."""

        response = await self.llm_client.generate(prompt)
        return {"attachment_context": response}

    async def _generate_prior_message(
        self,
        base_task: str,
        writer: WriterPersona,
        recipient: RecipientPersona
    ) -> dict:
        """Generate a prior message that needs a response."""

        prompt = f"""Generate a realistic prior message that requires a response.

Task context: {base_task}
Original sender: {recipient.name}, {recipient.job_title}
Recipient (now writing reply): {writer.name}, {writer.job_title}
Relationship: {recipient.relationship_to_writer}

Generate an email/message that {recipient.name} sent which requires a thoughtful reply.
The tone should match the relationship and professional context.
Include specific details that the reply should address.

Format as a complete message with greeting and signature."""

        response = await self.llm_client.generate(prompt)
        return {"prior_message": response}
```

### 3.5 Complete Prompt Schema

```python
@dataclass
class EvalPrompt:
    """Complete prompt for evaluation."""

    # Identification
    prompt_id: str
    created_at: datetime
    random_seed: int

    # Source data
    onet_task_id: str
    onet_task_text: str
    occupation_code: str
    occupation_title: str
    job_zone: int

    # Classification
    writing_category: str
    likely_medium: str

    # Personas
    writer: WriterPersona
    recipient: RecipientPersona
    cc_recipients: list[RecipientPersona] | None

    # Industry context
    naics_code: str
    naics_sector: str
    company: CompanyContext

    # Diversity dimensions (for analysis)
    formality_level: str
    urgency_level: str
    audience_size: str
    relationship_context: str
    emotional_context: str
    message_position: str

    # Enrichment content
    attachment_context: str | None
    prior_message: str | None
    example_to_match: str | None
    draft_to_revise: str | None
    competing_objectives: list[str] | None
    temporal_context: str | None

    # Constraints (for instruction-following tests)
    length_constraint: str | None
    format_constraint: str | None
    tone_directive: str | None
    exclusions: list[str] | None

    # Language settings
    language: str = "en"
    language_variant: str = "en-US"

    # Sensitive topic flags
    is_sensitive: bool = False
    sensitive_categories: list[str] | None = None

    def render_prompt(self) -> str:
        """Render the complete prompt text for model consumption."""
        parts = []

        # Context header
        parts.append(f"You are {self.writer.name}, {self.writer.job_title} at {self.company.name}.")
        parts.append(f"Your writing style tends to be {self._describe_style()}.")

        # Temporal context if present
        if self.temporal_context:
            parts.append(self.temporal_context)

        # Prior message if present
        if self.prior_message:
            parts.append(f"\n--- Previous message ---\n{self.prior_message}\n---\n")

        # Attachment context if present
        if self.attachment_context:
            parts.append(f"\nAttached: {self.attachment_context}\n")

        # Main task
        parts.append(f"\nTask: {self.onet_task_text}")

        # Recipient info
        recipient_desc = f"Write to {self.recipient.name}, {self.recipient.job_title}"
        if self.recipient.email:
            recipient_desc += f" ({self.recipient.email})"
        parts.append(recipient_desc)

        # CC recipients
        if self.cc_recipients:
            cc_list = ", ".join([f"{r.name} ({r.job_title})" for r in self.cc_recipients])
            parts.append(f"CC: {cc_list}")

        # Competing objectives
        if self.competing_objectives:
            parts.append(f"\nNote: {' and '.join(self.competing_objectives)}")

        # Constraints
        if self.length_constraint:
            parts.append(f"\nLength: {self.length_constraint}")
        if self.format_constraint:
            parts.append(f"Format: {self.format_constraint}")
        if self.tone_directive:
            parts.append(f"Tone: {self.tone_directive}")
        if self.exclusions:
            parts.append(f"Do not mention: {', '.join(self.exclusions)}")

        # Example to match
        if self.example_to_match:
            parts.append(f"\n--- Match this style ---\n{self.example_to_match}\n---")

        # Draft to revise
        if self.draft_to_revise:
            parts.append(f"\n--- Revise this draft ---\n{self.draft_to_revise}\n---")

        return "\n".join(parts)
```

---

## Part 4: Evaluation Flow and Judging System

### 4.1 Evaluation Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVALUATION PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  For each prompt:                                                            │
│  ┌──────────────┐                                                           │
│  │   Prompt     │                                                           │
│  │  (frozen)    │                                                           │
│  └──────┬───────┘                                                           │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │               RESPONSE COLLECTION (parallel)                          │   │
│  │  ┌─────────────────┐    ┌─────────────────┐                          │   │
│  │  │   Gemini 3.0    │    │   Competitor    │                          │   │
│  │  │   Pro/Flash     │    │   (GPT/Claude)  │                          │   │
│  │  └────────┬────────┘    └────────┬────────┘                          │   │
│  │           │                      │                                    │   │
│  │           ▼                      ▼                                    │   │
│  │  ┌─────────────────┐    ┌─────────────────┐                          │   │
│  │  │   Response A    │    │   Response B    │                          │   │
│  │  │   + metadata    │    │   + metadata    │                          │   │
│  │  └─────────────────┘    └─────────────────┘                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    POSITION SHUFFLING                                 │   │
│  │  • Deterministic shuffle based on prompt_id + seed                    │   │
│  │  • 50% show Gemini as "Response A", 50% as "Response B"              │   │
│  │  • Tracked for position bias analysis                                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    JUDGING ENSEMBLE                                   │   │
│  │                                                                       │   │
│  │  For each judge model (Claude Opus, GPT-5.2, Gemini Pro):            │   │
│  │    For each persona (Writing Expert, Recipient):                      │   │
│  │      For each vote (1 to 5):                                          │   │
│  │        → Generate judgment with reasoning                             │   │
│  │                                                                       │   │
│  │  Total: 3 judges × 2 personas × 5 votes = 30 judgments per prompt    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    VOTE AGGREGATION                                   │   │
│  │                                                                       │   │
│  │  Step 1: Per-judge majority (5 votes → 1 winner per judge/persona)   │   │
│  │  Step 2: Cross-judge majority (3 judges → final winner per persona)  │   │
│  │  Step 3: Combine personas (optional: weighted or consensus)          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Response Collection

```python
class ResponseCollector:
    """Collect model responses with retry logic and metadata tracking."""

    def __init__(self, api_client: OpenRouterClient, config: EvalConfig):
        self.api_client = api_client
        self.config = config
        self.retry_policy = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=0.1
        )

    async def collect_response(
        self,
        prompt: EvalPrompt,
        model_id: str
    ) -> ModelResponse:
        """Collect a single model response with full metadata."""

        start_time = time.monotonic()
        rendered_prompt = prompt.render_prompt()

        try:
            response = await self.retry_policy.execute(
                self.api_client.generate,
                model=model_id,
                prompt=rendered_prompt,
                timeout=self.config.response_timeout
            )

            return ModelResponse(
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                response_text=response.text,
                response_time_ms=int((time.monotonic() - start_time) * 1000),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                status="success",
                metadata=self._extract_metadata(response.text)
            )

        except RefusalError as e:
            return ModelResponse(
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                response_text=str(e),
                status="refusal",
                refusal_category=self._categorize_refusal(str(e)),
                metadata={}
            )

        except Exception as e:
            return ModelResponse(
                prompt_id=prompt.prompt_id,
                model_id=model_id,
                response_text="",
                status="error",
                error_message=str(e),
                metadata={}
            )

    def _extract_metadata(self, response_text: str) -> dict:
        """Extract response metadata for analysis."""
        return {
            "char_count": len(response_text),
            "word_count": len(response_text.split()),
            "line_count": response_text.count('\n') + 1,
            "has_bullet_points": bool(re.search(r'^\s*[-•*]\s', response_text, re.M)),
            "has_numbered_list": bool(re.search(r'^\s*\d+[.)]\s', response_text, re.M)),
            "has_greeting": self._detect_greeting(response_text),
            "has_signoff": self._detect_signoff(response_text),
            "formality_markers": self._count_formality_markers(response_text)
        }

    def _categorize_refusal(self, refusal_text: str) -> str:
        """Categorize the type of refusal."""
        refusal_patterns = {
            "safety": ["safety", "policy", "harmful", "inappropriate", "cannot assist"],
            "capability": ["cannot", "unable", "don't have", "beyond my"],
            "incomplete": ["let me", "would need", "could you provide"],
            "misunderstanding": ["clarify", "not sure what", "do you mean"]
        }

        text_lower = refusal_text.lower()
        for category, patterns in refusal_patterns.items():
            if any(p in text_lower for p in patterns):
                return category
        return "unknown"

    async def collect_pair(
        self,
        prompt: EvalPrompt,
        gemini_model: str,
        competitor_model: str
    ) -> tuple[ModelResponse, ModelResponse]:
        """Collect responses from both models in parallel."""
        gemini_task = self.collect_response(prompt, gemini_model)
        competitor_task = self.collect_response(prompt, competitor_model)

        return await asyncio.gather(gemini_task, competitor_task)
```

### 4.3 Position Shuffling for Bias Mitigation

```python
class PositionShuffler:
    """Deterministic position shuffling to eliminate position bias."""

    def __init__(self, global_seed: int):
        self.global_seed = global_seed

    def shuffle_for_comparison(
        self,
        prompt_id: str,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> tuple[ModelResponse, ModelResponse, bool]:
        """
        Shuffle responses to position A/B.

        Returns:
            (response_a, response_b, gemini_is_a)
        """
        # Deterministic shuffle based on prompt_id
        shuffle_seed = hash(f"{self.global_seed}:{prompt_id}") % (2**32)
        gemini_is_a = shuffle_seed % 2 == 0

        if gemini_is_a:
            return gemini_response, competitor_response, True
        else:
            return competitor_response, gemini_response, False

    def verify_balance(self, comparisons: list) -> dict:
        """Verify position assignments are balanced."""
        gemini_a_count = sum(1 for c in comparisons if c.gemini_is_a)
        gemini_b_count = len(comparisons) - gemini_a_count

        return {
            "gemini_position_a": gemini_a_count,
            "gemini_position_b": gemini_b_count,
            "balance_ratio": gemini_a_count / len(comparisons) if comparisons else 0.5,
            "is_balanced": abs(gemini_a_count - gemini_b_count) <= len(comparisons) * 0.1
        }
```

### 4.4 Judge Personas

```python
WRITING_EXPERT_PERSONA = """You are an expert writing evaluator with 20+ years of experience
in professional communication. You have worked as an editor at major publications,
taught business writing at top universities, and consulted for Fortune 500 companies
on their communication strategies.

You evaluate writing based on:
- Clarity and precision of language
- Appropriate structure and organization
- Tone matching the context and audience
- Conciseness without sacrificing completeness
- Professional quality and polish
- Authentic voice (not generic or AI-sounding)
- Avoidance of clichés and boilerplate phrases

You are particularly attuned to:
- Whether the length is appropriate for the task (not over-written or under-written)
- Whether the writing sounds natural or artificially constructed
- Whether formatting choices (bullets, headers, etc.) are appropriate or excessive
"""

RECIPIENT_PERSONA_TEMPLATE = """You are {recipient_name}, {recipient_title}.

You are evaluating two responses to a message/document you need to receive.
Your relationship to the writer: {relationship}
Your expectations: {expectations}

You evaluate based on:
- Does this response give me what I actually need?
- Is the tone appropriate for our relationship?
- Would I find this helpful, clear, and actionable?
- Does this seem like something my colleague would actually write?
- Is this the right level of detail for my needs?
- Would I have to ask follow-up questions, or is this complete?

You are NOT looking for perfect prose - you want effective, realistic communication.
"""

class JudgePersonaBuilder:
    """Build judge personas for each evaluation."""

    def build_writing_expert(self) -> str:
        return WRITING_EXPERT_PERSONA

    def build_recipient_persona(
        self,
        recipient: RecipientPersona,
        context: EvalPrompt
    ) -> str:
        expectations = self._infer_expectations(recipient, context)

        return RECIPIENT_PERSONA_TEMPLATE.format(
            recipient_name=recipient.name,
            recipient_title=recipient.job_title,
            relationship=recipient.relationship_to_writer,
            expectations=expectations
        )

    def _infer_expectations(
        self,
        recipient: RecipientPersona,
        context: EvalPrompt
    ) -> str:
        """Infer what the recipient would expect from this communication."""
        expectations = []

        if context.urgency_level in ["urgent", "critical"]:
            expectations.append("I need this quickly and clearly - no fluff")

        if recipient.seniority_level == "executive":
            expectations.append("I want the bottom line first, then details if needed")

        if context.formality_level in ["very_formal", "formal"]:
            expectations.append("I expect professional, polished communication")

        if recipient.relationship_to_writer == "first_contact":
            expectations.append("I don't know this person - they need to establish context")

        return "; ".join(expectations) if expectations else "Standard professional communication"
```

### 4.5 Judgment Generation

```python
@dataclass
class JudgmentRequest:
    """Request for a single judgment."""
    prompt: EvalPrompt
    response_a: ModelResponse
    response_b: ModelResponse
    judge_persona: str
    persona_type: str  # "expert" or "recipient"

@dataclass
class Judgment:
    """Single judgment result."""
    prompt_id: str
    judge_model: str
    persona_type: str
    vote_number: int

    winner: str  # "A", "B", or "tie"
    confidence: float  # 0.0-1.0
    reasoning: str

    # Detailed scores
    clarity_a: int
    clarity_b: int
    tone_a: int
    tone_b: int
    effectiveness_a: int
    effectiveness_b: int
    authenticity_a: int
    authenticity_b: int
    length_appropriateness_a: int
    length_appropriateness_b: int

    # Position tracking
    gemini_is_a: bool
    gemini_won: bool | None  # Computed after unblinding

JUDGMENT_PROMPT_TEMPLATE = """
{persona}

---

## Evaluation Task

You are evaluating two responses to the following writing task.

### Context
{context}

### The Task
{task}

---

### Response A
{response_a}

---

### Response B
{response_b}

---

## Your Evaluation

Evaluate both responses on the following criteria (1-5 scale):

1. **Clarity**: How clear and easy to understand is the writing?
2. **Tone Appropriateness**: Does the tone match the context and audience?
3. **Effectiveness**: Does the response accomplish the intended goal?
4. **Authenticity**: Does it sound natural/human, not AI-generated?
5. **Length Appropriateness**: Is it the right length for this task?

Then provide your overall judgment:
- Which response is better overall?
- How confident are you? (low/medium/high)
- Brief reasoning (2-3 sentences)

Format your response as JSON:
```json
{{
  "scores": {{
    "response_a": {{"clarity": X, "tone": X, "effectiveness": X, "authenticity": X, "length": X}},
    "response_b": {{"clarity": X, "tone": X, "effectiveness": X, "authenticity": X, "length": X}}
  }},
  "winner": "A" | "B" | "tie",
  "confidence": "low" | "medium" | "high",
  "reasoning": "..."
}}
```
"""

class JudgingEngine:
    """Execute judgments across multiple judges and personas."""

    JUDGE_MODELS = [
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2",
        "google/gemini-3-pro"
    ]

    def __init__(
        self,
        api_client: OpenRouterClient,
        config: EvalConfig,
        persona_builder: JudgePersonaBuilder
    ):
        self.api_client = api_client
        self.config = config
        self.persona_builder = persona_builder

    async def judge_comparison(
        self,
        prompt: EvalPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        gemini_is_a: bool
    ) -> ComparisonResult:
        """Run full judging ensemble for one comparison."""

        all_judgments = []

        # For each judge model
        for judge_model in self.JUDGE_MODELS[:self.config.num_judges]:
            # For each persona
            for persona_type in ["expert", "recipient"]:
                if persona_type == "expert":
                    persona = self.persona_builder.build_writing_expert()
                else:
                    persona = self.persona_builder.build_recipient_persona(
                        prompt.recipient, prompt
                    )

                # Collect N votes
                for vote_num in range(self.config.votes_per_judge):
                    judgment = await self._get_single_judgment(
                        prompt=prompt,
                        response_a=response_a,
                        response_b=response_b,
                        judge_model=judge_model,
                        persona=persona,
                        persona_type=persona_type,
                        vote_number=vote_num,
                        gemini_is_a=gemini_is_a
                    )
                    all_judgments.append(judgment)

        # Aggregate results
        return self._aggregate_judgments(all_judgments, gemini_is_a)

    async def _get_single_judgment(
        self,
        prompt: EvalPrompt,
        response_a: ModelResponse,
        response_b: ModelResponse,
        judge_model: str,
        persona: str,
        persona_type: str,
        vote_number: int,
        gemini_is_a: bool
    ) -> Judgment:
        """Get a single judgment from one judge."""

        judge_prompt = JUDGMENT_PROMPT_TEMPLATE.format(
            persona=persona,
            context=self._format_context(prompt),
            task=prompt.onet_task_text,
            response_a=response_a.response_text,
            response_b=response_b.response_text
        )

        response = await self.api_client.generate(
            model=judge_model,
            prompt=judge_prompt,
            temperature=0.7  # Some variation for different votes
        )

        parsed = self._parse_judgment_response(response.text)

        # Determine if Gemini won (unblinding)
        if parsed["winner"] == "tie":
            gemini_won = None
        elif parsed["winner"] == "A":
            gemini_won = gemini_is_a
        else:
            gemini_won = not gemini_is_a

        return Judgment(
            prompt_id=prompt.prompt_id,
            judge_model=judge_model,
            persona_type=persona_type,
            vote_number=vote_number,
            winner=parsed["winner"],
            confidence=self._confidence_to_float(parsed["confidence"]),
            reasoning=parsed["reasoning"],
            clarity_a=parsed["scores"]["response_a"]["clarity"],
            clarity_b=parsed["scores"]["response_b"]["clarity"],
            tone_a=parsed["scores"]["response_a"]["tone"],
            tone_b=parsed["scores"]["response_b"]["tone"],
            effectiveness_a=parsed["scores"]["response_a"]["effectiveness"],
            effectiveness_b=parsed["scores"]["response_b"]["effectiveness"],
            authenticity_a=parsed["scores"]["response_a"]["authenticity"],
            authenticity_b=parsed["scores"]["response_b"]["authenticity"],
            length_appropriateness_a=parsed["scores"]["response_a"]["length"],
            length_appropriateness_b=parsed["scores"]["response_b"]["length"],
            gemini_is_a=gemini_is_a,
            gemini_won=gemini_won
        )
```

### 4.6 Vote Aggregation

```python
class VoteAggregator:
    """Aggregate votes using majority-of-majorities logic."""

    def aggregate(
        self,
        judgments: list[Judgment],
        gemini_is_a: bool
    ) -> ComparisonResult:
        """
        Aggregate all judgments for a single comparison.

        Logic:
        1. For each (judge_model, persona_type), get majority of N votes
        2. For each persona_type, get majority across judges
        3. Combine both personas for final result
        """

        # Group by judge and persona
        by_judge_persona = defaultdict(list)
        for j in judgments:
            key = (j.judge_model, j.persona_type)
            by_judge_persona[key].append(j)

        # Step 1: Per-judge majority
        judge_persona_winners = {}
        for (judge, persona), votes in by_judge_persona.items():
            gemini_votes = sum(1 for v in votes if v.gemini_won is True)
            opponent_votes = sum(1 for v in votes if v.gemini_won is False)
            tie_votes = sum(1 for v in votes if v.gemini_won is None)

            if gemini_votes > opponent_votes:
                judge_persona_winners[(judge, persona)] = "gemini"
            elif opponent_votes > gemini_votes:
                judge_persona_winners[(judge, persona)] = "opponent"
            else:
                judge_persona_winners[(judge, persona)] = "tie"

        # Step 2: Cross-judge majority per persona
        persona_results = {}
        for persona_type in ["expert", "recipient"]:
            persona_votes = [
                winner for (judge, persona), winner in judge_persona_winners.items()
                if persona == persona_type
            ]

            gemini_count = persona_votes.count("gemini")
            opponent_count = persona_votes.count("opponent")

            if gemini_count > opponent_count:
                persona_results[persona_type] = "gemini"
            elif opponent_count > gemini_count:
                persona_results[persona_type] = "opponent"
            else:
                persona_results[persona_type] = "tie"

        # Step 3: Final combination
        expert_result = persona_results.get("expert", "tie")
        recipient_result = persona_results.get("recipient", "tie")

        if expert_result == recipient_result:
            final_winner = expert_result
        elif expert_result == "tie":
            final_winner = recipient_result
        elif recipient_result == "tie":
            final_winner = expert_result
        else:
            final_winner = "split"  # Expert and recipient disagree

        # Calculate agreement metrics
        agreement = self._calculate_agreement(judgments)

        return ComparisonResult(
            prompt_id=judgments[0].prompt_id,
            gemini_is_a=gemini_is_a,
            expert_winner=expert_result,
            recipient_winner=recipient_result,
            final_winner=final_winner,
            total_judgments=len(judgments),
            gemini_vote_count=sum(1 for j in judgments if j.gemini_won is True),
            opponent_vote_count=sum(1 for j in judgments if j.gemini_won is False),
            tie_count=sum(1 for j in judgments if j.gemini_won is None),
            inter_judge_agreement=agreement["cohens_kappa"],
            all_judgments=judgments
        )

    def _calculate_agreement(self, judgments: list[Judgment]) -> dict:
        """Calculate inter-rater reliability metrics."""
        # Cohen's Kappa calculation for multi-rater agreement
        # Simplified: pairwise agreement rate

        judge_models = list(set(j.judge_model for j in judgments))
        if len(judge_models) < 2:
            return {"cohens_kappa": 1.0, "pairwise_agreement": 1.0}

        agreements = 0
        comparisons = 0

        for i, j1 in enumerate(judge_models):
            for j2 in judge_models[i+1:]:
                j1_votes = [j for j in judgments if j.judge_model == j1]
                j2_votes = [j for j in judgments if j.judge_model == j2]

                for v1, v2 in zip(j1_votes, j2_votes):
                    if v1.gemini_won == v2.gemini_won:
                        agreements += 1
                    comparisons += 1

        pairwise = agreements / comparisons if comparisons > 0 else 1.0

        # Approximate Cohen's Kappa
        # κ = (p_o - p_e) / (1 - p_e)
        p_o = pairwise
        p_e = 0.33  # Expected agreement by chance (3 outcomes)
        kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0

        return {
            "cohens_kappa": max(0, min(1, kappa)),
            "pairwise_agreement": pairwise
        }
```

### 4.7 Failure Handling: Auto-Loss Logic

```python
class AutoLossHandler:
    """Handle failures and refusals with auto-loss logic."""

    def evaluate_for_auto_loss(
        self,
        gemini_response: ModelResponse,
        competitor_response: ModelResponse
    ) -> tuple[str | None, str | None]:
        """
        Check if either response should auto-lose.

        Returns:
            (auto_winner, reason) or (None, None) if normal judging should proceed
        """

        gemini_failed = self._is_failure(gemini_response)
        competitor_failed = self._is_failure(competitor_response)

        if gemini_failed and competitor_failed:
            return "tie", "both_failed"
        elif gemini_failed:
            return "opponent", f"gemini_{gemini_response.status}"
        elif competitor_failed:
            return "gemini", f"opponent_{competitor_response.status}"
        else:
            return None, None

    def _is_failure(self, response: ModelResponse) -> bool:
        """Determine if a response constitutes a failure."""
        if response.status in ["refusal", "error"]:
            return True

        # Check for off-topic or incomplete responses
        if response.status == "success":
            if len(response.response_text.strip()) < 20:
                return True
            if self._is_off_topic(response.response_text):
                return True

        return False

    def _is_off_topic(self, text: str) -> bool:
        """Detect if response is off-topic."""
        off_topic_patterns = [
            r"I cannot help with",
            r"I'm not able to",
            r"As an AI",
            r"I don't have access to",
        ]
        return any(re.search(p, text, re.I) for p in off_topic_patterns)
```

---

## Part 5: Results Storage and Analysis

### 5.1 SQLite Database Schema

```sql
-- Core tables for eval storage

-- Eval runs (top-level container)
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_json TEXT NOT NULL,
    preset_name TEXT,
    random_seed INTEGER NOT NULL,
    status TEXT DEFAULT 'running',  -- running, completed, interrupted
    total_prompts INTEGER,
    completed_prompts INTEGER DEFAULT 0,
    estimated_cost_usd REAL,
    actual_cost_usd REAL
);

-- Generated prompts
CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- O*NET source
    onet_task_id TEXT,
    onet_task_text TEXT NOT NULL,
    occupation_code TEXT,
    occupation_title TEXT,
    job_zone INTEGER,

    -- Classification
    writing_category TEXT,
    likely_medium TEXT,

    -- Personas (JSON)
    writer_persona_json TEXT,
    recipient_persona_json TEXT,
    cc_recipients_json TEXT,

    -- Industry context
    naics_code TEXT,
    naics_sector TEXT,
    company_json TEXT,

    -- Diversity dimensions
    formality_level TEXT,
    urgency_level TEXT,
    audience_size TEXT,
    relationship_context TEXT,
    emotional_context TEXT,
    message_position TEXT,

    -- Enrichment content
    attachment_context TEXT,
    prior_message TEXT,
    example_to_match TEXT,
    draft_to_revise TEXT,
    competing_objectives_json TEXT,
    temporal_context TEXT,

    -- Constraints
    length_constraint TEXT,
    format_constraint TEXT,
    tone_directive TEXT,
    exclusions_json TEXT,

    -- Language
    language TEXT DEFAULT 'en',
    language_variant TEXT DEFAULT 'en-US',

    -- Sensitive topic flags
    is_sensitive BOOLEAN DEFAULT FALSE,
    sensitive_categories_json TEXT,

    -- Rendered prompt
    rendered_prompt TEXT NOT NULL
);

-- Model responses
CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    response_text TEXT,
    response_time_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,

    status TEXT NOT NULL,  -- success, refusal, error
    refusal_category TEXT,
    error_message TEXT,

    -- Metadata
    char_count INTEGER,
    word_count INTEGER,
    line_count INTEGER,
    has_bullet_points BOOLEAN,
    has_numbered_list BOOLEAN,
    has_greeting BOOLEAN,
    has_signoff BOOLEAN,
    formality_markers_json TEXT
);

-- Comparisons (pairwise)
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    gemini_response_id TEXT REFERENCES responses(response_id),
    competitor_response_id TEXT REFERENCES responses(response_id),

    gemini_is_position_a BOOLEAN NOT NULL,

    -- Auto-loss handling
    auto_loss_winner TEXT,  -- NULL if judged normally
    auto_loss_reason TEXT,

    -- Aggregated results
    expert_winner TEXT,     -- gemini, opponent, tie
    recipient_winner TEXT,  -- gemini, opponent, tie
    final_winner TEXT NOT NULL,  -- gemini, opponent, tie, split

    total_judgments INTEGER,
    gemini_vote_count INTEGER,
    opponent_vote_count INTEGER,
    tie_count INTEGER,
    inter_judge_agreement REAL
);

-- Individual judgments
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    judge_model TEXT NOT NULL,
    persona_type TEXT NOT NULL,  -- expert, recipient
    vote_number INTEGER NOT NULL,

    winner TEXT NOT NULL,  -- A, B, tie
    confidence REAL,
    reasoning TEXT,

    -- Detailed scores
    clarity_a INTEGER,
    clarity_b INTEGER,
    tone_a INTEGER,
    tone_b INTEGER,
    effectiveness_a INTEGER,
    effectiveness_b INTEGER,
    authenticity_a INTEGER,
    authenticity_b INTEGER,
    length_appropriateness_a INTEGER,
    length_appropriateness_b INTEGER,

    -- Position tracking
    gemini_is_a BOOLEAN NOT NULL,
    gemini_won BOOLEAN  -- NULL for ties
);

-- Checkpoints for resume capability
CREATE TABLE checkpoints (
    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    phase TEXT NOT NULL,  -- prompt_generation, response_collection, judging
    last_completed_prompt_id TEXT,
    state_json TEXT
);

-- Failure log
CREATE TABLE failures (
    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES eval_runs(run_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    phase TEXT NOT NULL,
    prompt_id TEXT,
    model_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT,
    retry_count INTEGER,
    recovered BOOLEAN DEFAULT FALSE
);

-- Indexes for common queries
CREATE INDEX idx_prompts_run_id ON prompts(run_id);
CREATE INDEX idx_responses_prompt_id ON responses(prompt_id);
CREATE INDEX idx_comparisons_run_id ON comparisons(run_id);
CREATE INDEX idx_comparisons_prompt_id ON comparisons(prompt_id);
CREATE INDEX idx_judgments_comparison_id ON judgments(comparison_id);
CREATE INDEX idx_prompts_occupation ON prompts(occupation_code);
CREATE INDEX idx_prompts_naics ON prompts(naics_code);
CREATE INDEX idx_comparisons_winner ON comparisons(final_winner);
```

### 5.2 Checkpoint and Resume System

```python
@dataclass
class CheckpointState:
    """State for checkpoint/resume."""
    run_id: str
    phase: str
    last_completed_prompt_id: str | None
    pending_prompt_ids: list[str]
    pending_comparison_ids: list[str]
    config: EvalConfig
    random_seed: int

class CheckpointManager:
    """Manage checkpoints for resumable evaluation."""

    def __init__(self, db: Database, run_dir: Path):
        self.db = db
        self.run_dir = run_dir
        self.checkpoint_file = run_dir / "checkpoint.json"

    async def save_checkpoint(self, state: CheckpointState) -> None:
        """Save checkpoint to both database and file."""
        # Save to database
        await self.db.execute(
            """INSERT INTO checkpoints (run_id, phase, last_completed_prompt_id, state_json)
               VALUES (?, ?, ?, ?)""",
            (state.run_id, state.phase, state.last_completed_prompt_id,
             json.dumps(asdict(state)))
        )

        # Also save to file for crash recovery
        with open(self.checkpoint_file, 'w') as f:
            json.dump(asdict(state), f, indent=2)

    async def load_checkpoint(self, run_id: str) -> CheckpointState | None:
        """Load most recent checkpoint for a run."""
        # Try file first (in case of DB corruption)
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file) as f:
                    data = json.load(f)
                return CheckpointState(**data)
            except Exception:
                pass

        # Fall back to database
        row = await self.db.fetchone(
            """SELECT state_json FROM checkpoints
               WHERE run_id = ?
               ORDER BY checkpoint_id DESC LIMIT 1""",
            (run_id,)
        )
        if row:
            return CheckpointState(**json.loads(row['state_json']))
        return None

    async def get_incomplete_work(self, run_id: str) -> dict:
        """Get all incomplete work for a run."""
        # Prompts without responses
        prompts_needing_responses = await self.db.fetchall(
            """SELECT p.prompt_id, c.gemini_model, c.competitor_model
               FROM prompts p
               JOIN comparisons c ON p.prompt_id = c.prompt_id
               WHERE p.run_id = ?
               AND (c.gemini_response_id IS NULL OR c.competitor_response_id IS NULL)""",
            (run_id,)
        )

        # Comparisons without judgments
        comparisons_needing_judging = await self.db.fetchall(
            """SELECT c.comparison_id
               FROM comparisons c
               WHERE c.run_id = ?
               AND c.auto_loss_winner IS NULL
               AND c.total_judgments IS NULL""",
            (run_id,)
        )

        return {
            "response_collection": prompts_needing_responses,
            "judging": comparisons_needing_judging
        }

class ResumableEvalRunner:
    """Evaluation runner with full resume capability."""

    def __init__(self, config: EvalConfig, db: Database):
        self.config = config
        self.db = db
        self.checkpoint_mgr = CheckpointManager(db, config.run_dir)

    async def run(self, resume_from: str | None = None) -> None:
        """Run evaluation, optionally resuming from checkpoint."""

        if resume_from:
            state = await self.checkpoint_mgr.load_checkpoint(resume_from)
            if not state:
                raise ValueError(f"No checkpoint found for run {resume_from}")
            self.config = state.config
            incomplete = await self.checkpoint_mgr.get_incomplete_work(resume_from)
        else:
            state = None
            incomplete = None

        # Continue from appropriate phase
        if state is None or state.phase == "prompt_generation":
            await self._run_prompt_generation()
            await self._save_phase_checkpoint("response_collection")

        if state is None or state.phase in ["prompt_generation", "response_collection"]:
            await self._run_response_collection(incomplete)
            await self._save_phase_checkpoint("judging")

        if state is None or state.phase in ["prompt_generation", "response_collection", "judging"]:
            await self._run_judging(incomplete)
            await self._save_phase_checkpoint("analysis")

        await self._run_analysis()
        await self._mark_completed()
```

### 5.3 Statistical Analysis Engine

```python
class StatisticsEngine:
    """Compute win rates, confidence intervals, and statistical tests."""

    def compute_win_rate(
        self,
        comparisons: list[ComparisonResult],
        model: str = "gemini"
    ) -> WinRateResult:
        """Compute win rate with confidence interval."""

        wins = sum(1 for c in comparisons if c.final_winner == model)
        losses = sum(1 for c in comparisons if c.final_winner == "opponent")
        ties = sum(1 for c in comparisons if c.final_winner in ["tie", "split"])
        total = len(comparisons)

        win_rate = wins / total if total > 0 else 0.0

        # Wilson score interval for binomial proportion
        ci_low, ci_high = self._wilson_score_interval(wins, total, confidence=0.95)

        return WinRateResult(
            wins=wins,
            losses=losses,
            ties=ties,
            total=total,
            win_rate=win_rate,
            confidence_interval=(ci_low, ci_high),
            confidence_level=0.95
        )

    def _wilson_score_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return (0.0, 0.0)

        from scipy import stats

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p_hat = successes / total
        n = total

        denominator = 1 + z**2 / n
        center = (p_hat + z**2 / (2 * n)) / denominator
        margin = (z / denominator) * math.sqrt(
            (p_hat * (1 - p_hat) + z**2 / (4 * n)) / n
        )

        return (max(0, center - margin), min(1, center + margin))

    def compute_significance(
        self,
        comparisons: list[ComparisonResult]
    ) -> SignificanceResult:
        """Test whether win rate is significantly different from 50%."""
        from scipy import stats

        wins = sum(1 for c in comparisons if c.final_winner == "gemini")
        losses = sum(1 for c in comparisons if c.final_winner == "opponent")
        total = wins + losses  # Exclude ties for this test

        if total < 10:
            return SignificanceResult(
                test_type="insufficient_data",
                p_value=1.0,
                is_significant=False,
                effect_size=0.0
            )

        # Binomial test: is this significantly different from 50%?
        p_value = stats.binom_test(wins, total, 0.5, alternative='two-sided')

        # Effect size (Cohen's h for proportions)
        p_obs = wins / total
        p_null = 0.5
        effect_size = 2 * (math.asin(math.sqrt(p_obs)) - math.asin(math.sqrt(p_null)))

        return SignificanceResult(
            test_type="binomial",
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=effect_size
        )

    def compute_breakdown_by_dimension(
        self,
        comparisons: list[ComparisonResult],
        prompts: dict[str, EvalPrompt],
        dimension: str
    ) -> dict[str, WinRateResult]:
        """Compute win rates broken down by a dimension."""

        by_dim = defaultdict(list)
        for comp in comparisons:
            prompt = prompts[comp.prompt_id]
            dim_value = getattr(prompt, dimension, "unknown")
            by_dim[dim_value].append(comp)

        return {
            dim_val: self.compute_win_rate(comps)
            for dim_val, comps in by_dim.items()
        }
```

### 5.4 Bias Detection System

```python
class BiasDetector:
    """Detect systematic biases in models and judges."""

    async def detect_all_biases(
        self,
        comparisons: list[ComparisonResult],
        responses: dict[str, ModelResponse],
        judgments: list[Judgment]
    ) -> BiasReport:
        """Run all bias detection analyses."""

        return BiasReport(
            position_bias=self._detect_position_bias(comparisons),
            length_bias=self._detect_length_bias(comparisons, responses),
            judge_model_bias=self._detect_judge_bias(judgments),
            formality_bias=self._detect_formality_bias(comparisons, responses),
            format_bias=self._detect_format_bias(comparisons, responses)
        )

    def _detect_position_bias(
        self,
        comparisons: list[ComparisonResult]
    ) -> PositionBiasResult:
        """Detect if judges prefer position A over B."""

        # For each judgment, check if winner was A or B
        a_wins = 0
        b_wins = 0
        total = 0

        for comp in comparisons:
            for j in comp.all_judgments:
                if j.winner == "A":
                    a_wins += 1
                elif j.winner == "B":
                    b_wins += 1
                total += 1

        a_rate = a_wins / total if total > 0 else 0.5

        # Chi-square test for position bias
        from scipy import stats
        chi2, p_value = stats.chisquare([a_wins, b_wins])

        return PositionBiasResult(
            position_a_win_rate=a_rate,
            position_b_win_rate=1 - a_rate,
            chi_square=chi2,
            p_value=p_value,
            is_significant=p_value < 0.05,
            recommendation="Position bias detected - verify shuffle is working" if p_value < 0.05 else "No significant position bias"
        )

    def _detect_length_bias(
        self,
        comparisons: list[ComparisonResult],
        responses: dict[str, ModelResponse]
    ) -> LengthBiasResult:
        """Detect if longer responses win more often."""

        longer_wins = 0
        shorter_wins = 0

        for comp in comparisons:
            gemini_resp = responses[comp.gemini_response_id]
            competitor_resp = responses[comp.competitor_response_id]

            gemini_len = gemini_resp.metadata.get("word_count", 0)
            competitor_len = competitor_resp.metadata.get("word_count", 0)

            if comp.final_winner == "gemini":
                if gemini_len > competitor_len:
                    longer_wins += 1
                else:
                    shorter_wins += 1
            elif comp.final_winner == "opponent":
                if competitor_len > gemini_len:
                    longer_wins += 1
                else:
                    shorter_wins += 1

        total = longer_wins + shorter_wins
        longer_rate = longer_wins / total if total > 0 else 0.5

        return LengthBiasResult(
            longer_response_win_rate=longer_rate,
            avg_winner_length=self._avg_winner_length(comparisons, responses),
            avg_loser_length=self._avg_loser_length(comparisons, responses),
            correlation=self._length_win_correlation(comparisons, responses),
            recommendation="Length bias detected - consider length normalization" if longer_rate > 0.6 else "No significant length bias"
        )

    def _detect_judge_bias(
        self,
        judgments: list[Judgment]
    ) -> JudgeBiasResult:
        """Detect if specific judges favor specific models."""

        by_judge = defaultdict(lambda: {"gemini": 0, "opponent": 0, "tie": 0})

        for j in judgments:
            if j.gemini_won is True:
                by_judge[j.judge_model]["gemini"] += 1
            elif j.gemini_won is False:
                by_judge[j.judge_model]["opponent"] += 1
            else:
                by_judge[j.judge_model]["tie"] += 1

        judge_rates = {}
        for judge, counts in by_judge.items():
            total = counts["gemini"] + counts["opponent"]
            judge_rates[judge] = counts["gemini"] / total if total > 0 else 0.5

        # Test for significant differences between judges
        from scipy import stats

        if len(judge_rates) >= 2:
            # Cochran's Q test for multiple judges
            rates = list(judge_rates.values())
            variance = np.var(rates)
            is_significant = variance > 0.05  # Simplified threshold
        else:
            is_significant = False

        return JudgeBiasResult(
            per_judge_gemini_rates=judge_rates,
            max_disagreement=max(judge_rates.values()) - min(judge_rates.values()) if judge_rates else 0,
            is_significant=is_significant,
            recommendation="Significant judge disagreement - review judge prompts" if is_significant else "Judges are reasonably aligned"
        )
```

### 5.5 Weakness Analysis

```python
class WeaknessAnalyzer:
    """Identify specific areas where Gemini underperforms."""

    def analyze_weaknesses(
        self,
        comparisons: list[ComparisonResult],
        prompts: dict[str, EvalPrompt],
        stats_engine: StatisticsEngine
    ) -> WeaknessReport:
        """Comprehensive weakness analysis."""

        # Analyze by every dimension
        dimensions = [
            "occupation_code", "job_zone", "writing_category",
            "formality_level", "urgency_level", "audience_size",
            "emotional_context", "message_position", "naics_code",
            "is_sensitive", "likely_medium"
        ]

        dimension_weaknesses = {}
        for dim in dimensions:
            breakdown = stats_engine.compute_breakdown_by_dimension(
                comparisons, prompts, dim
            )
            # Find values where Gemini significantly underperforms
            weak_values = [
                (val, result) for val, result in breakdown.items()
                if result.win_rate < 0.45 and result.total >= 10
            ]
            if weak_values:
                dimension_weaknesses[dim] = sorted(
                    weak_values, key=lambda x: x[1].win_rate
                )

        # Identify specific task patterns
        task_pattern_weaknesses = self._analyze_task_patterns(comparisons, prompts)

        # Identify criterion-specific weaknesses
        criterion_weaknesses = self._analyze_criteria(comparisons)

        return WeaknessReport(
            dimension_weaknesses=dimension_weaknesses,
            task_pattern_weaknesses=task_pattern_weaknesses,
            criterion_weaknesses=criterion_weaknesses,
            top_10_weakest_areas=self._get_top_weaknesses(dimension_weaknesses),
            recommendations=self._generate_recommendations(dimension_weaknesses)
        )

    def _analyze_criteria(
        self,
        comparisons: list[ComparisonResult]
    ) -> dict[str, CriterionWeakness]:
        """Analyze per-criterion scores to find systematic weaknesses."""

        criteria = ["clarity", "tone", "effectiveness", "authenticity", "length_appropriateness"]
        results = {}

        for criterion in criteria:
            gemini_scores = []
            opponent_scores = []

            for comp in comparisons:
                for j in comp.all_judgments:
                    if comp.gemini_is_a:
                        gemini_scores.append(getattr(j, f"{criterion}_a"))
                        opponent_scores.append(getattr(j, f"{criterion}_b"))
                    else:
                        gemini_scores.append(getattr(j, f"{criterion}_b"))
                        opponent_scores.append(getattr(j, f"{criterion}_a"))

            gemini_avg = np.mean(gemini_scores) if gemini_scores else 0
            opponent_avg = np.mean(opponent_scores) if opponent_scores else 0
            diff = gemini_avg - opponent_avg

            results[criterion] = CriterionWeakness(
                criterion=criterion,
                gemini_avg_score=gemini_avg,
                opponent_avg_score=opponent_avg,
                difference=diff,
                is_weakness=diff < -0.3
            )

        return results

    def _generate_recommendations(
        self,
        dimension_weaknesses: dict
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if "job_zone" in dimension_weaknesses:
            weak_zones = [v for v, _ in dimension_weaknesses["job_zone"]]
            recommendations.append(
                f"Gemini underperforms on job zones {weak_zones}. "
                "Consider targeted training on these skill levels."
            )

        if "emotional_context" in dimension_weaknesses:
            weak_contexts = [v for v, _ in dimension_weaknesses["emotional_context"]]
            recommendations.append(
                f"Gemini struggles with emotional contexts: {weak_contexts}. "
                "Review handling of sensitive/difficult communications."
            )

        if "formality_level" in dimension_weaknesses:
            weak_formality = [v for v, _ in dimension_weaknesses["formality_level"]]
            recommendations.append(
                f"Formality calibration issues at levels: {weak_formality}. "
                "May need better formality adaptation training."
            )

        return recommendations
```

---

## Part 6: TUI Implementation

### 6.1 TUI Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TUI APPLICATION STRUCTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐                                                        │
│  │   EvalApp       │  Main Textual Application                              │
│  │   (textual)     │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ├── ProgressScreen      (Live eval progress dashboard)            │
│           ├── ResultsScreen       (Browse completed results)                │
│           ├── ComparisonScreen    (Side-by-side response viewing)           │
│           ├── AnalysisScreen      (Statistics and charts)                   │
│           ├── ConfigScreen        (Configure eval parameters)               │
│           └── HelpScreen          (Documentation and controls)              │
│                                                                              │
│  Shared Widgets:                                                            │
│  ├── ProgressBar, StatsPanel, ActivityLog                                   │
│  ├── ResponseViewer, JudgmentPanel, FilterBar                               │
│  └── HeatmapChart, WinRateChart, ConfidenceIntervalChart                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Progress Screen Implementation

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, DataTable, Log
from textual.reactive import reactive
from textual.message import Message

class ProgressScreen(Screen):
    """Real-time progress visualization during evaluation."""

    BINDINGS = [
        ("q", "quit_safely", "Quit (save checkpoint)"),
        ("p", "pause", "Pause"),
        ("d", "toggle_detail", "Toggle detail view"),
        ("s", "show_stats", "Full statistics"),
        ("h", "show_help", "Help"),
    ]

    # Reactive state
    total_prompts = reactive(0)
    completed_prompts = reactive(0)
    current_phase = reactive("initializing")
    elapsed_seconds = reactive(0)
    estimated_cost = reactive(0.0)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main"):
            # Overall progress section
            with Container(id="overall-progress", classes="panel"):
                yield Static("OVERALL PROGRESS", classes="panel-title")
                yield ProgressBar(id="main-progress")
                yield Static(id="progress-text")
                yield Static(id="phase-indicator")

            # Model pairs section
            with Container(id="model-pairs", classes="panel"):
                yield Static("MODEL PAIRS", classes="panel-title")
                yield DataTable(id="pairs-table")

            # Current batch section
            with Horizontal(id="current-batch"):
                with Container(id="current-prompt", classes="panel"):
                    yield Static("CURRENT PROMPT", classes="panel-title")
                    yield Static(id="prompt-details")

                with Container(id="current-judging", classes="panel"):
                    yield Static("JUDGING", classes="panel-title")
                    yield Static(id="judging-status")

            # Statistics section
            with Horizontal(id="stats-row"):
                with Container(id="win-rates", classes="panel"):
                    yield Static("WIN RATES (Running)", classes="panel-title")
                    yield Static(id="win-rate-display")

                with Container(id="performance", classes="panel"):
                    yield Static("PERFORMANCE", classes="panel-title")
                    yield Static(id="performance-display")

            # Activity log
            with Container(id="activity", classes="panel"):
                yield Static("RECENT ACTIVITY", classes="panel-title")
                yield Log(id="activity-log", max_lines=100)

            # Error summary
            with Container(id="errors", classes="panel"):
                yield Static(id="error-summary")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the display on mount."""
        # Set up pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.add_columns("Model Pair", "Progress", "Win Rate")

        # Start update timer
        self.set_interval(0.5, self.update_display)

    async def update_display(self) -> None:
        """Update all display elements with current state."""
        state = await self.app.eval_runner.get_current_state()

        # Update progress bar
        progress = self.query_one("#main-progress", ProgressBar)
        progress.total = state.total_prompts
        progress.progress = state.completed_prompts

        # Update progress text
        pct = (state.completed_prompts / state.total_prompts * 100
               if state.total_prompts > 0 else 0)
        self.query_one("#progress-text").update(
            f"{state.completed_prompts}/{state.total_prompts} prompts ({pct:.1f}%)"
        )

        # Update phase indicator
        phases = ["Generation", "Judging", "Analysis"]
        phase_display = " → ".join([
            f"[{'green' if p == state.current_phase else 'dim'}]{p}[/]"
            for p in phases
        ])
        self.query_one("#phase-indicator").update(phase_display)

        # Update model pairs table
        table = self.query_one("#pairs-table", DataTable)
        table.clear()
        for pair in state.model_pairs:
            table.add_row(
                f"Gemini vs {pair.competitor}",
                f"{pair.completed}/{pair.total}",
                f"{pair.win_rate:.1f}% ± {pair.confidence:.1f}%"
            )

        # Update current prompt
        if state.current_prompt:
            self.query_one("#prompt-details").update(
                f"Prompt #{state.current_prompt.index}: "
                f"\"{state.current_prompt.task[:60]}...\"\n"
                f"Occupation: {state.current_prompt.occupation}\n"
                f"Industry: {state.current_prompt.industry}"
            )

        # Update judging status
        if state.current_judging:
            judging_lines = []
            for judge, status in state.current_judging.items():
                progress_dots = "●" * status.completed + "○" * (5 - status.completed)
                judging_lines.append(
                    f"{judge}: {progress_dots} ({status.completed}/5)"
                )
            self.query_one("#judging-status").update("\n".join(judging_lines))

        # Update win rates
        win_display = []
        for pair, rate in state.running_win_rates.items():
            win_display.append(f"vs {pair}: {rate.rate:.1f}% ± {rate.ci:.1f}%")
        win_display.append(f"\nJudge Agreement: {state.agreement:.2f} κ")
        self.query_one("#win-rate-display").update("\n".join(win_display))

        # Update performance
        self.query_one("#performance-display").update(
            f"Avg response time: {state.avg_response_time:.1f}s\n"
            f"Avg judge time: {state.avg_judge_time:.1f}s\n"
            f"API calls/min: {state.api_calls_per_min}\n"
            f"Est. cost so far: ${state.cost_so_far:.2f}\n"
            f"Est. total cost: ${state.estimated_total_cost:.2f}"
        )

        # Update error summary
        self.query_one("#error-summary").update(
            f"⚠ {state.retry_count} retries "
            f"({state.recovered_count} recovered)  |  "
            f"✗ {state.failure_count} failures  |  "
            f"⏱ {state.rate_limit_pauses} rate limit pauses"
        )

    def action_quit_safely(self) -> None:
        """Quit with checkpoint save."""
        self.app.eval_runner.request_graceful_shutdown()
        self.app.exit()

    def action_pause(self) -> None:
        """Toggle pause state."""
        self.app.eval_runner.toggle_pause()

    def action_toggle_detail(self) -> None:
        """Toggle detailed view of current prompt/responses."""
        self.app.push_screen("detail")

class ProgressApp(App):
    """Main TUI application for progress monitoring."""

    CSS = """
    .panel {
        border: solid green;
        padding: 1;
        margin: 1;
    }
    .panel-title {
        text-style: bold;
        color: cyan;
    }
    #main-progress {
        width: 100%;
    }
    #stats-row {
        height: auto;
    }
    """

    SCREENS = {
        "progress": ProgressScreen,
        "detail": DetailScreen,
        "help": HelpScreen,
    }

    def __init__(self, eval_runner: ResumableEvalRunner):
        super().__init__()
        self.eval_runner = eval_runner

    def on_mount(self) -> None:
        self.push_screen("progress")
```

### 6.3 Results Browser Screen

```python
class ResultsScreen(Screen):
    """Browse and filter evaluation results."""

    BINDINGS = [
        ("f", "filter", "Filter"),
        ("s", "sort", "Sort"),
        ("enter", "view_detail", "View details"),
        ("e", "export", "Export CSV"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="filter-bar"):
            yield Select(
                options=[("All", "all")] + [(o, o) for o in self.occupations],
                id="occupation-filter"
            )
            yield Select(
                options=[("All", "all"), ("Gemini", "gemini"),
                         ("Opponent", "opponent"), ("Tie", "tie")],
                id="winner-filter"
            )
            yield Select(
                options=[("All", "all")] + [(i, i) for i in self.industries],
                id="industry-filter"
            )

        with Container(id="results-list"):
            yield DataTable(id="results-table")

        with Container(id="detail-panel"):
            yield Static(id="selected-detail")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "ID", "Occupation", "Industry", "Winner",
            "Gemini Votes", "Expert", "Recipient", "Agreement"
        )
        self.load_results()

    def load_results(self, filters: dict = None) -> None:
        """Load results with optional filters."""
        results = self.app.db.query_comparisons(filters)
        table = self.query_one("#results-table", DataTable)
        table.clear()

        for r in results:
            table.add_row(
                r.prompt_id[:8],
                r.occupation_title[:30],
                r.naics_sector[:20],
                r.final_winner,
                f"{r.gemini_vote_count}/{r.total_judgments}",
                r.expert_winner,
                r.recipient_winner,
                f"{r.inter_judge_agreement:.2f}"
            )

    def action_view_detail(self) -> None:
        """View detailed comparison for selected row."""
        table = self.query_one("#results-table", DataTable)
        row = table.cursor_row
        if row is not None:
            prompt_id = table.get_row_at(row)[0]
            self.app.push_screen(ComparisonScreen(prompt_id))
```

### 6.4 Side-by-Side Comparison Screen

```python
class ComparisonScreen(Screen):
    """View side-by-side responses and judgments."""

    def __init__(self, prompt_id: str):
        super().__init__()
        self.prompt_id = prompt_id

    def compose(self) -> ComposeResult:
        yield Header()

        # Prompt context
        with Container(id="prompt-context", classes="panel"):
            yield Static("PROMPT CONTEXT", classes="panel-title")
            yield Static(id="prompt-text")

        # Side-by-side responses
        with Horizontal(id="responses"):
            with Container(id="response-a", classes="panel response-panel"):
                yield Static("RESPONSE A (Gemini)", id="response-a-title",
                            classes="panel-title")
                yield Static(id="response-a-text", classes="response-text")
                yield Static(id="response-a-meta", classes="response-meta")

            with Container(id="response-b", classes="panel response-panel"):
                yield Static("RESPONSE B (Opponent)", id="response-b-title",
                            classes="panel-title")
                yield Static(id="response-b-text", classes="response-text")
                yield Static(id="response-b-meta", classes="response-meta")

        # Judgments
        with Container(id="judgments", classes="panel"):
            yield Static("JUDGMENTS", classes="panel-title")
            yield DataTable(id="judgment-table")

        # Aggregated result
        with Container(id="result", classes="panel"):
            yield Static(id="final-result")

        yield Footer()

    def on_mount(self) -> None:
        # Load comparison data
        comparison = self.app.db.get_comparison(self.prompt_id)
        prompt = self.app.db.get_prompt(self.prompt_id)

        # Display prompt
        self.query_one("#prompt-text").update(prompt.rendered_prompt)

        # Display responses
        gemini_resp = self.app.db.get_response(comparison.gemini_response_id)
        opponent_resp = self.app.db.get_response(comparison.competitor_response_id)

        if comparison.gemini_is_position_a:
            resp_a, resp_b = gemini_resp, opponent_resp
            self.query_one("#response-a-title").update("RESPONSE A (Gemini)")
            self.query_one("#response-b-title").update("RESPONSE B (Opponent)")
        else:
            resp_a, resp_b = opponent_resp, gemini_resp
            self.query_one("#response-a-title").update("RESPONSE A (Opponent)")
            self.query_one("#response-b-title").update("RESPONSE B (Gemini)")

        self.query_one("#response-a-text").update(resp_a.response_text)
        self.query_one("#response-b-text").update(resp_b.response_text)

        self.query_one("#response-a-meta").update(
            f"Words: {resp_a.metadata['word_count']} | "
            f"Time: {resp_a.response_time_ms}ms"
        )
        self.query_one("#response-b-meta").update(
            f"Words: {resp_b.metadata['word_count']} | "
            f"Time: {resp_b.response_time_ms}ms"
        )

        # Display judgments table
        table = self.query_one("#judgment-table", DataTable)
        table.add_columns(
            "Judge", "Persona", "Vote", "Winner", "Confidence", "Reasoning"
        )

        judgments = self.app.db.get_judgments(comparison.comparison_id)
        for j in judgments:
            winner_display = "Gemini" if j.gemini_won else ("Opponent" if j.gemini_won is False else "Tie")
            table.add_row(
                j.judge_model.split("/")[-1],
                j.persona_type,
                str(j.vote_number + 1),
                winner_display,
                f"{j.confidence:.0%}",
                j.reasoning[:50] + "..."
            )

        # Final result
        result_text = (
            f"FINAL WINNER: {comparison.final_winner.upper()}\n"
            f"Expert verdict: {comparison.expert_winner} | "
            f"Recipient verdict: {comparison.recipient_winner}\n"
            f"Total votes: Gemini {comparison.gemini_vote_count} - "
            f"Opponent {comparison.opponent_vote_count} "
            f"(Ties: {comparison.tie_count})\n"
            f"Inter-judge agreement: κ = {comparison.inter_judge_agreement:.2f}"
        )
        self.query_one("#final-result").update(result_text)
```

### 6.5 Cost Estimation Display

```python
class CostEstimator:
    """Estimate costs for evaluation runs."""

    # OpenRouter pricing per 1M tokens (approximate, varies by model)
    PRICING = {
        "google/gemini-3-pro": {"input": 1.25, "output": 5.00},
        "google/gemini-3-flash": {"input": 0.075, "output": 0.30},
        "openai/gpt-5.2": {"input": 2.50, "output": 10.00},
        "openai/gpt-4.1": {"input": 0.50, "output": 1.50},
        "anthropic/claude-opus-4.5": {"input": 15.00, "output": 75.00},
        "anthropic/claude-sonnet": {"input": 3.00, "output": 15.00},
        "x/grok-4.1": {"input": 2.00, "output": 8.00},
        "kimi/k2": {"input": 1.00, "output": 4.00},
    }

    # Estimated tokens per request type
    TOKEN_ESTIMATES = {
        "response_generation": {"input": 800, "output": 400},
        "judgment": {"input": 2000, "output": 200},
    }

    def estimate_run(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost and time for an eval run."""

        # Response generation costs
        response_calls = config.num_prompts * len(config.model_pairs) * 2
        response_cost = self._estimate_response_cost(config)

        # Judging costs
        judge_calls = (
            config.num_prompts *
            len(config.model_pairs) *
            config.num_judges *
            config.num_personas *
            config.votes_per_judge
        )
        judge_cost = self._estimate_judge_cost(config)

        total_cost_low = (response_cost * 0.8) + (judge_cost * 0.8)
        total_cost_high = (response_cost * 1.2) + (judge_cost * 1.2)

        # Time estimation
        time_with_limits = self._estimate_time(config, rate_limited=True)
        time_parallelized = self._estimate_time(config, rate_limited=False)

        return CostEstimate(
            response_generation_cost=(response_cost * 0.9, response_cost * 1.1),
            judging_cost=(judge_cost * 0.9, judge_cost * 1.1),
            total_cost=(total_cost_low, total_cost_high),
            response_calls=response_calls,
            judge_calls=judge_calls,
            estimated_time_with_limits=time_with_limits,
            estimated_time_parallelized=time_parallelized
        )

    def display_estimate(self, estimate: CostEstimate, config: EvalConfig) -> str:
        """Format estimate for display."""
        return f"""
╭─────────────────────────────────────────────────────────────╮
│                    EVAL RUN ESTIMATE                        │
├─────────────────────────────────────────────────────────────┤
│ Prompts:              {config.num_prompts:<39}│
│ Model pairs:          {len(config.model_pairs)} ({', '.join(p.competitor[:10] for p in config.model_pairs[:3])}...)│
│ Total comparisons:    {config.num_prompts * len(config.model_pairs):<39}│
│                                                             │
│ Judge config:         {config.num_judges} judges × {config.votes_per_judge} votes × {config.num_personas} personas       │
│ Total judge calls:    {estimate.judge_calls:<39}│
│                                                             │
│ ESTIMATED COST                                              │
│   Response generation:  ${estimate.response_generation_cost[0]:.0f} - ${estimate.response_generation_cost[1]:.0f}                         │
│   Judging:              ${estimate.judging_cost[0]:.0f} - ${estimate.judging_cost[1]:.0f}                         │
│   Total:                ${estimate.total_cost[0]:.0f} - ${estimate.total_cost[1]:.0f}                         │
│                                                             │
│ ESTIMATED TIME                                              │
│   With rate limits:     {estimate.estimated_time_with_limits}                           │
│   Parallelized:         {estimate.estimated_time_parallelized}                           │
╰─────────────────────────────────────────────────────────────╯
"""
```

---

## Part 7: Robustness Requirements

### 7.1 Retry Policy with Exponential Backoff

```python
@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retryable_exceptions: tuple = (
        httpx.TimeoutException,
        httpx.NetworkError,
        RateLimitError,
        ServerError,
    )

    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e

                if attempt == self.max_retries:
                    raise

                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        # Add jitter
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)
```

### 7.2 Rate Limit Handling

```python
class RateLimitHandler:
    """Handle rate limits across multiple models."""

    def __init__(self):
        self.model_limits = defaultdict(lambda: RateLimitState())
        self.global_semaphore = asyncio.Semaphore(50)  # Global concurrency limit

    async def acquire(self, model: str) -> None:
        """Acquire rate limit slot for a model."""
        state = self.model_limits[model]

        # Check if we're in cooldown
        if state.cooldown_until and time.time() < state.cooldown_until:
            wait_time = state.cooldown_until - time.time()
            logger.info(f"Rate limit cooldown for {model}: {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        # Acquire global semaphore
        await self.global_semaphore.acquire()

        # Track request
        state.request_count += 1
        state.last_request = time.time()

    def release(self, model: str) -> None:
        """Release rate limit slot."""
        self.global_semaphore.release()

    def handle_rate_limit(self, model: str, retry_after: float = None) -> None:
        """Handle a rate limit response."""
        state = self.model_limits[model]

        # Default cooldown if not specified
        if retry_after is None:
            retry_after = 60.0

        state.cooldown_until = time.time() + retry_after
        state.rate_limit_hits += 1

        logger.warning(
            f"Rate limit hit for {model}. "
            f"Cooling down for {retry_after}s. "
            f"Total hits: {state.rate_limit_hits}"
        )

@dataclass
class RateLimitState:
    """Track rate limit state for a model."""
    request_count: int = 0
    last_request: float = 0
    cooldown_until: float = 0
    rate_limit_hits: int = 0
```

### 7.3 Graceful Shutdown

```python
class GracefulShutdownHandler:
    """Handle graceful shutdown with checkpoint saving."""

    def __init__(self, eval_runner: ResumableEvalRunner):
        self.eval_runner = eval_runner
        self.shutdown_requested = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        import signal

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signal."""
        if self.shutdown_requested:
            # Second signal - force quit
            logger.warning("Force quit requested. Exiting immediately.")
            sys.exit(1)

        self.shutdown_requested = True
        logger.info("Shutdown requested. Saving checkpoint...")

        # Request graceful shutdown
        asyncio.create_task(self._graceful_shutdown())

    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown."""
        try:
            # Wait for current operations to complete (with timeout)
            await asyncio.wait_for(
                self.eval_runner.finish_current_operations(),
                timeout=30.0
            )

            # Save checkpoint
            await self.eval_runner.save_checkpoint()

            logger.info("Checkpoint saved. Exiting safely.")
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for operations. Forcing checkpoint save.")
            await self.eval_runner.force_save_checkpoint()

        sys.exit(0)
```

### 7.4 Inter-Judge Agreement Validation

```python
class AgreementValidator:
    """Validate inter-judge agreement is within acceptable bounds."""

    def __init__(self, min_kappa: float = 0.4, warn_kappa: float = 0.6):
        self.min_kappa = min_kappa
        self.warn_kappa = warn_kappa
        self.running_agreements = []

    def record_agreement(self, kappa: float, comparison_id: str) -> None:
        """Record agreement for a comparison."""
        self.running_agreements.append((comparison_id, kappa))

        # Check if we're seeing systematic low agreement
        if len(self.running_agreements) >= 50:
            recent = [k for _, k in self.running_agreements[-50:]]
            avg_kappa = sum(recent) / len(recent)

            if avg_kappa < self.min_kappa:
                logger.error(
                    f"Inter-judge agreement critically low: κ={avg_kappa:.2f}. "
                    "Consider reviewing judge prompts or pausing evaluation."
                )
            elif avg_kappa < self.warn_kappa:
                logger.warning(
                    f"Inter-judge agreement below threshold: κ={avg_kappa:.2f}. "
                    "Results may have high variance."
                )

    def get_summary(self) -> dict:
        """Get agreement summary statistics."""
        if not self.running_agreements:
            return {"count": 0}

        kappas = [k for _, k in self.running_agreements]
        return {
            "count": len(kappas),
            "mean": sum(kappas) / len(kappas),
            "min": min(kappas),
            "max": max(kappas),
            "std": np.std(kappas),
            "below_threshold": sum(1 for k in kappas if k < self.min_kappa)
        }
```

---

## Part 8: CLI and Configuration

### 8.1 CLI Interface

```python
import click

@click.group()
def cli():
    """Gemini Writing Evaluation Framework"""
    pass

@cli.command()
@click.option('--preset', type=int, help='Use preset configuration (1-10)')
@click.option('--prompts', type=int, help='Number of prompts')
@click.option('--models', type=str, help='Comma-separated model IDs')
@click.option('--judges', type=int, help='Number of judge models (1-3)')
@click.option('--votes', type=int, help='Votes per judge (1-5)')
@click.option('--occupations', type=str, help='Filter by O*NET occupation codes')
@click.option('--industries', type=str, help='Filter by NAICS codes')
@click.option('--dry-run', is_flag=True, help='Show estimate without running')
@click.option('--seed', type=int, help='Random seed for reproducibility')
def run(preset, prompts, models, judges, votes, occupations, industries, dry_run, seed):
    """Run an evaluation."""

    # Build configuration
    config = build_config(preset, prompts, models, judges, votes,
                         occupations, industries, seed)

    # Show estimate
    estimator = CostEstimator()
    estimate = estimator.estimate_run(config)
    click.echo(estimator.display_estimate(estimate, config))

    if dry_run:
        return

    # Confirm
    if not click.confirm('Proceed?'):
        return

    # Run evaluation with TUI
    runner = ResumableEvalRunner(config)
    app = ProgressApp(runner)
    app.run()

@cli.command()
@click.argument('run_dir')
def resume(run_dir):
    """Resume an interrupted evaluation."""
    config = load_config(run_dir)
    runner = ResumableEvalRunner(config)
    runner.resume_from(run_dir)

    app = ProgressApp(runner)
    app.run()

@cli.command()
@click.argument('run_dir')
def view(run_dir):
    """View results for a completed evaluation."""
    db = Database(Path(run_dir) / "results.db")
    app = ResultsApp(db)
    app.run()

@cli.command()
@click.argument('run_dirs', nargs=-1)
def compare(run_dirs):
    """Compare results across multiple runs."""
    dbs = [Database(Path(d) / "results.db") for d in run_dirs]
    comparison = CrossRunComparison(dbs)
    comparison.display()

@cli.command()
@click.argument('run_dir')
@click.option('--output', '-o', type=str, default='report.pdf')
def report(run_dir, output):
    """Generate PDF report for an evaluation."""
    db = Database(Path(run_dir) / "results.db")
    generator = PDFReportGenerator(db)
    generator.generate(output)
    click.echo(f"Report saved to {output}")
```

### 8.2 Preset Configurations

```python
EVAL_PRESETS = {
    1: EvalPreset(
        name="Sanity Check",
        prompts=5,
        model_pairs=1,
        judges=1,
        votes=1,
        personas=1,
        estimated_cost=1,
        estimated_time="2 min",
        use_case="Does the system work?"
    ),
    2: EvalPreset(
        name="Smoke Test",
        prompts=20,
        model_pairs=1,
        judges=1,
        votes=3,
        personas=2,
        estimated_cost=5,
        estimated_time="5 min",
        use_case="Quick functionality test"
    ),
    3: EvalPreset(
        name="Dev Iteration",
        prompts=50,
        model_pairs=2,
        judges=2,
        votes=3,
        personas=2,
        estimated_cost=25,
        estimated_time="15 min",
        use_case="Development/debugging"
    ),
    4: EvalPreset(
        name="Quick Sample",
        prompts=100,
        model_pairs=2,
        judges=2,
        votes=5,
        personas=2,
        estimated_cost=75,
        estimated_time="30 min",
        use_case="Fast directional signal"
    ),
    5: EvalPreset(
        name="Light Eval",
        prompts=200,
        model_pairs=3,
        judges=3,
        votes=3,
        personas=2,
        estimated_cost=150,
        estimated_time="1 hr",
        use_case="Light but meaningful eval"
    ),
    6: EvalPreset(
        name="Standard Eval",
        prompts=500,
        model_pairs=4,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost=500,
        estimated_time="3 hrs",
        use_case="Standard evaluation run"
    ),
    7: EvalPreset(
        name="Thorough Eval",
        prompts=1000,
        model_pairs=4,
        judges=3,
        votes=5,
        personas=2,
        estimated_cost=1000,
        estimated_time="6 hrs",
        use_case="Thorough with good power"
    ),
    8: EvalPreset(
        name="Comprehensive",
        prompts=2000,
        model_pairs="all",
        judges=3,
        votes=5,
        personas=2,
        estimated_cost=2500,
        estimated_time="12 hrs",
        use_case="High statistical power"
    ),
    9: EvalPreset(
        name="Deep Dive",
        prompts=5000,
        model_pairs="all",
        judges=3,
        votes=5,
        personas=2,
        estimated_cost=6000,
        estimated_time="24 hrs",
        use_case="Publication-grade"
    ),
    10: EvalPreset(
        name="Full Kaboodle",
        prompts=10000,
        model_pairs="all",
        judges=3,
        votes=5,
        personas=2,
        estimated_cost=12000,
        estimated_time="48 hrs",
        use_case="Maximum coverage"
    ),
}
```

---

## Part 9: PDF Report Generation

### 9.1 Report Structure

```python
class PDFReportGenerator:
    """Generate comprehensive PDF evaluation report."""

    def __init__(self, db: Database):
        self.db = db
        self.stats_engine = StatisticsEngine()
        self.bias_detector = BiasDetector()
        self.weakness_analyzer = WeaknessAnalyzer()

    def generate(self, output_path: str) -> None:
        """Generate the complete PDF report."""

        # Load all data
        comparisons = self.db.get_all_comparisons()
        prompts = self.db.get_all_prompts_dict()
        judgments = self.db.get_all_judgments()
        responses = self.db.get_all_responses_dict()

        # Generate report sections
        sections = [
            self._executive_summary(comparisons),
            self._methodology_section(),
            self._overall_results(comparisons),
            self._per_model_pair_results(comparisons),
            self._dimension_breakdowns(comparisons, prompts),
            self._bias_analysis(comparisons, responses, judgments),
            self._weakness_analysis(comparisons, prompts),
            self._statistical_appendix(comparisons),
        ]

        # Render to HTML
        html = self._render_html(sections)

        # Convert to PDF
        from weasyprint import HTML
        HTML(string=html).write_pdf(output_path)

    def _executive_summary(self, comparisons: list) -> ReportSection:
        """Generate executive summary."""

        overall = self.stats_engine.compute_win_rate(comparisons)
        significance = self.stats_engine.compute_significance(comparisons)

        # Key findings
        findings = []
        if overall.win_rate > 0.55:
            findings.append(f"Gemini wins {overall.win_rate:.1%} of comparisons")
        elif overall.win_rate < 0.45:
            findings.append(f"Gemini underperforms with {overall.win_rate:.1%} win rate")
        else:
            findings.append(f"Results are competitive ({overall.win_rate:.1%} win rate)")

        if significance.is_significant:
            findings.append(f"Result is statistically significant (p={significance.p_value:.4f})")

        return ReportSection(
            title="Executive Summary",
            content=self._render_executive_summary(overall, significance, findings)
        )

    def _dimension_breakdowns(
        self,
        comparisons: list,
        prompts: dict
    ) -> ReportSection:
        """Generate breakdown by all dimensions."""

        dimensions = [
            ("Job Zone", "job_zone"),
            ("Occupation Group", "occupation_code"),
            ("Industry", "naics_sector"),
            ("Formality Level", "formality_level"),
            ("Urgency", "urgency_level"),
            ("Audience Size", "audience_size"),
            ("Emotional Context", "emotional_context"),
            ("Writing Category", "writing_category"),
        ]

        breakdowns = []
        for name, field in dimensions:
            breakdown = self.stats_engine.compute_breakdown_by_dimension(
                comparisons, prompts, field
            )
            breakdowns.append((name, breakdown))

        return ReportSection(
            title="Results by Dimension",
            content=self._render_dimension_breakdowns(breakdowns),
            charts=self._generate_heatmaps(breakdowns)
        )

    def _generate_heatmaps(self, breakdowns: list) -> list:
        """Generate heatmap visualizations."""
        import plotly.graph_objects as go

        charts = []
        for name, breakdown in breakdowns:
            # Create heatmap data
            labels = list(breakdown.keys())
            win_rates = [r.win_rate for r in breakdown.values()]
            sample_sizes = [r.total for r in breakdown.values()]

            fig = go.Figure(data=go.Heatmap(
                z=[win_rates],
                x=labels,
                colorscale='RdYlGn',
                zmid=0.5,
                text=[[f"{r:.1%}\n(n={n})" for r, n in zip(win_rates, sample_sizes)]],
                texttemplate="%{text}",
                textfont={"size": 10},
            ))

            fig.update_layout(
                title=f"Win Rate by {name}",
                height=200
            )

            charts.append(fig.to_html(full_html=False))

        return charts
```

---

## Part 10: Implementation Timeline and Dependencies

### 10.1 Dependencies

```toml
[project]
name = "gemini-writing-eval"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # Core
    "pydantic>=2.0",
    "httpx>=0.25",

    # Database
    "aiosqlite>=0.19",

    # CLI & TUI
    "click>=8.1",
    "textual>=0.40",
    "rich>=13.0",

    # Analysis
    "pandas>=2.0",
    "numpy>=1.24",
    "scipy>=1.11",

    # Visualization
    "plotly>=5.18",

    # PDF Generation
    "weasyprint>=60",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.1",
    "mypy>=1.6",
    "ruff>=0.1",
]
```

### 10.2 Implementation Phases

**Phase 1: Core Infrastructure (Week 1)**
- Database schema and models
- Configuration system
- O*NET data extraction
- Basic CLI structure

**Phase 2: Prompt Generation (Week 2)**
- Task classification
- Persona building
- Diversity sampling
- LLM enrichment pipeline

**Phase 3: Evaluation Pipeline (Week 3)**
- OpenRouter API client
- Response collection with retry
- Judging engine
- Vote aggregation

**Phase 4: Storage and Resume (Week 4)**
- Checkpoint system
- Resume capability
- Failure logging
- Export functionality

**Phase 5: Analysis (Week 5)**
- Statistics engine
- Bias detection
- Weakness analysis
- Visualization generation

**Phase 6: TUI and Reports (Week 6)**
- Progress screen
- Results browser
- Comparison viewer
- PDF report generator

**Phase 7: Testing and Polish (Week 7)**
- Integration tests
- Load testing
- Documentation
- Performance optimization

---

## Appendix: Key Design Decisions

### A.1 Why SQLite?
- Single-file portability for each run
- No external dependencies
- Full SQL capability for analysis
- Excellent Python async support via aiosqlite

### A.2 Why Textual for TUI?
- Modern, well-maintained library
- Rich styling and layout
- Good async support
- Cross-platform compatibility

### A.3 Why OpenRouter?
- Unified API for all models
- Consistent pricing visibility
- Reduced implementation complexity
- Good rate limit handling

### A.4 Why Majority-of-Majorities Voting?
- Reduces noise from individual judge variability
- Cross-validates across different judge perspectives
- More robust than simple majority or averaging
- Handles ties gracefully

### A.5 Trade-offs Acknowledged
- **Prompt Generation Bias**: Using evaluated models for prompt generation creates potential bias; documented and tracked
- **Cost vs. Statistical Power**: Presets allow users to choose their trade-off point
- **NAICS Mapping Approximation**: Without official crosswalk, we use SOC-based heuristics
- **English-only v1**: Limits international applicability but simplifies judging
