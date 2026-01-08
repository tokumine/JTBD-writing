# Gemini Writing Evaluation Framework - Implementation Plan (Draft 3)

## Executive Summary

This plan details a comprehensive implementation for evaluating Gemini 3.0 Pro and Flash against competing frontier LLMs on realistic professional writing tasks. The system leverages the O*NET 30.1 database (18,796 task statements across 923 occupations) to generate diverse, real-world writing evaluation prompts.

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
                                    +---------------------------+
                                    |     User Interface        |
                                    |  (Rich TUI + CLI Args)    |
                                    +-------------+-------------+
                                                  |
                                    +-------------v-------------+
                                    |    Orchestration Engine   |
                                    |  - Config Management      |
                                    |  - Preset Selection       |
                                    |  - Cost Estimation        |
                                    |  - Run Coordination       |
                                    +-------------+-------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                             |                             |
        +-----------v-----------+   +------------v------------+   +------------v------------+
        |   Prompt Generation   |   |   Response Generation   |   |     Judging System      |
        |   Pipeline            |   |   Engine                |   |                         |
        |  - O*NET Extraction   |   |  - OpenRouter Client    |   |  - Multi-Judge Ensemble |
        |  - Context Enrichment |   |  - Response Collection  |   |  - Best-of-N Voting     |
        |  - LLM Enhancement    |   |  - Timeout/Retry        |   |  - Dual Persona Eval    |
        +-----------+-----------+   +------------+------------+   +------------+------------+
                    |                             |                             |
                    +-----------------------------+-----------------------------+
                                                  |
                                    +-------------v-------------+
                                    |    Data Storage Layer     |
                                    |  - SQLite Results DB      |
                                    |  - JSON Checkpoints       |
                                    |  - Structured File System |
                                    +-------------+-------------+
                                                  |
                                    +-------------v-------------+
                                    |   Analysis & Reporting    |
                                    |  - Win Rate Calculation   |
                                    |  - Statistical Tests      |
                                    |  - PDF Report Generation  |
                                    +---------------------------+
```

### 1.2 Core Python Module Structure

```
gemini_writing_eval/
├── __init__.py
├── cli.py                      # Click-based CLI interface
├── config/
│   ├── __init__.py
│   ├── presets.py              # 10 preset configurations
│   ├── models.py               # Model definitions and tiers
│   └── settings.py             # Pydantic settings management
├── data/
│   ├── __init__.py
│   ├── onet_extractor.py       # O*NET database access
│   ├── naics_mapper.py         # Industry code mapping
│   ├── company_sampler.py      # Real company sampling
│   └── name_generator.py       # Realistic name generation
├── prompts/
│   ├── __init__.py
│   ├── generator.py            # Main prompt generation orchestrator
│   ├── enrichment.py           # LLM enrichment phase
│   ├── personas.py             # Writer/recipient persona logic
│   └── schemas.py              # Pydantic schemas for prompts
├── api/
│   ├── __init__.py
│   ├── openrouter.py           # OpenRouter API client
│   ├── rate_limiter.py         # Token bucket rate limiting
│   └── retry.py                # Exponential backoff retry logic
├── evaluation/
│   ├── __init__.py
│   ├── runner.py               # Main evaluation loop
│   ├── judging.py              # Multi-judge ensemble logic
│   ├── rubric.py               # Evaluation criteria
│   └── aggregation.py          # Vote aggregation
├── storage/
│   ├── __init__.py
│   ├── checkpoint.py           # Checkpoint management
│   ├── database.py             # SQLite operations
│   └── filesystem.py           # Directory structure management
├── analysis/
│   ├── __init__.py
│   ├── statistics.py           # Win rates, confidence intervals
│   ├── bias_detection.py       # Systematic bias analysis
│   └── weakness_finder.py      # Gemini weakness identification
├── reporting/
│   ├── __init__.py
│   ├── pdf_generator.py        # PDF report with plotly
│   ├── charts.py               # Visualization generation
│   └── templates/              # Report templates
├── tui/
│   ├── __init__.py
│   ├── app.py                  # Main Textual application
│   ├── screens/                # TUI screens
│   │   ├── progress.py         # Live progress dashboard
│   │   ├── viewer.py           # Results viewer
│   │   └── config.py           # Configuration screen
│   └── widgets/                # Custom widgets
└── utils/
    ├── __init__.py
    ├── logging.py              # Structured logging
    └── costs.py                # Cost estimation utilities
```

### 1.3 Key Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27"                 # Async HTTP client
pydantic = "^2.5"               # Data validation
pydantic-settings = "^2.1"      # Configuration management
sqlalchemy = "^2.0"             # Database ORM
rich = "^13.7"                  # Terminal formatting
textual = "^0.52"               # TUI framework
plotly = "^5.18"                # Visualizations
kaleido = "0.2.1"               # Plotly static export
scipy = "^1.12"                 # Statistical tests
pandas = "^2.2"                 # Data analysis
click = "^8.1"                  # CLI framework
tenacity = "^8.2"               # Retry logic
anyio = "^4.2"                  # Async utilities
structlog = "^24.1"             # Structured logging
weasyprint = "^61"              # PDF generation
jinja2 = "^3.1"                 # Report templates
```

---

## 2. Data Pipeline: O*NET to Prompts

### 2.1 O*NET Database Access Layer

The `onet_extractor.py` module provides structured access to the SQLite database:

```python
@dataclass
class ONetTask:
    task_id: str
    onetsoc_code: str
    occupation_title: str
    occupation_description: str
    task_statement: str
    task_type: str  # Core, Supplemental, or None
    job_zone: int   # 1-5
    soc_major_code: str  # e.g., "11" for Management
    soc_major_name: str  # e.g., "Management"
    writing_skill_importance: float  # 1-5 scale
    email_frequency: float  # 1-5 scale
    written_correspondence_frequency: float  # 1-5 scale
    inferred_writing_category: str  # From 10 categories in ONET_WRITING_REFERENCE.md

class ONetExtractor:
    def __init__(self, db_path: str = "db/onet.db"):
        self.engine = create_engine(f"sqlite:///{db_path}")

    def extract_writing_tasks(self,
                               min_job_zone: int = 1,
                               max_job_zone: int = 5,
                               soc_major_codes: list[str] | None = None,
                               writing_categories: list[str] | None = None,
                               limit: int | None = None) -> list[ONetTask]:
        """Extract writing-relevant tasks with full context."""

    def get_occupation_metadata(self, onetsoc_code: str) -> dict:
        """Get full occupation context for enrichment."""

    def get_writing_category_distribution(self) -> dict[str, int]:
        """Get count of tasks per inferred writing category."""
```

### 2.2 Writing Category Classification

Implement SQL-based classification matching the 10 categories from `ONET_WRITING_REFERENCE.md`:

```python
WRITING_CATEGORY_PATTERNS = {
    "explicit_writing": [
        "%write%", "%draft%", "%document%", "%prepare report%",
        "%prepare%proposal%", "%compose%"
    ],
    "professional_correspondence": [
        "%correspond%", "%email%", "%letter%", "%memo%",
        "%notify%customer%", "%inform%customer%"
    ],
    "reports_analysis": [
        "%report%", "%present%finding%", "%present%result%",
        "%summarize%", "%prepare%presentation%"
    ],
    "persuasion_negotiation": [
        "%negotiat%", "%propos%", "%persuad%", "%recommend%",
        "%advise%client%", "%advise%customer%"
    ],
    "policy_procedure": [
        "%develop%polic%", "%implement%polic%", "%write%procedure%",
        "%prepare%guideline%", "%establish%standard%"
    ],
    "customer_communication": [
        "%customer%question%", "%client%question%", "%answer%question%",
        "%resolve%complaint%", "%explain%to%customer%", "%respond%to%customer%"
    ],
    "instructional_training": [
        "%train%staff%", "%train%employee%", "%instruct%",
        "%develop%curriculum%", "%prepare%manual%", "%prepare%training%"
    ],
    "internal_coordination": [
        "%confer with%", "%coordinate with%", "%collaborate with%",
        "%meet with%", "%communicate with%management%", "%communicate with%staff%"
    ],
    "contracts_legal": [
        "%prepare%contract%", "%draft%contract%", "%write%agreement%",
        "%prepare%permit%", "%prepare%compliance%"
    ],
    "feedback_evaluation": [
        "%evaluate%performance%", "%provide%feedback%",
        "%review%and%recommend%", "%assess%and%report%"
    ]
}

def classify_task(task_statement: str) -> str:
    """Classify task into writing category based on keyword patterns."""
    task_lower = task_statement.lower()
    matches = []
    for category, patterns in WRITING_CATEGORY_PATTERNS.items():
        for pattern in patterns:
            sql_pattern = pattern.replace("%", "")
            if sql_pattern in task_lower:
                matches.append(category)
                break
    return matches[0] if matches else "general"
```

### 2.3 NAICS Industry Mapping

Since O*NET lacks direct NAICS codes, implement external mapping:

```python
class NAICSMapper:
    """Map occupations to NAICS industry codes using BLS crosswalk."""

    # NAICS 2-digit sector codes
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
        "81": "Other Services (except Public Administration)",
        "92": "Public Administration"
    }

    def __init__(self):
        # Load BLS occupation-industry matrix (embedded as static data)
        self.occupation_industry_matrix = self._load_bls_matrix()

    def get_industries_for_occupation(self, soc_code: str) -> list[str]:
        """Return list of NAICS codes where this occupation is common."""

    def sample_industry(self, soc_code: str, seed: int) -> str:
        """Deterministically sample an industry for this occupation."""
```

### 2.4 Company Sampling System

Generate realistic company context using embedded knowledge:

```python
@dataclass
class Company:
    name: str
    naics_code: str
    industry_name: str
    size_category: str  # "Fortune 500", "Mid-market", "Small Business", "Startup"
    employee_count_range: str  # e.g., "10,000-50,000"
    founded_year: int | None
    public_private: str  # "Public", "Private"
    hq_location: str  # City, State or Country

class CompanySampler:
    """Sample real companies with industry and size diversity."""

    # Embedded company database by NAICS sector and size
    COMPANIES = {
        "54": {  # Professional Services
            "Fortune 500": [
                Company("Deloitte", "54", "Professional Services", "Fortune 500",
                        "300,000-400,000", 1845, "Private", "New York, NY"),
                Company("Accenture", "54", "Professional Services", "Fortune 500",
                        "700,000-750,000", 1989, "Public", "Dublin, Ireland"),
                # ...
            ],
            "Mid-market": [
                Company("West Monroe Partners", "54", "Professional Services", "Mid-market",
                        "2,000-3,000", 2002, "Private", "Chicago, IL"),
                # ...
            ],
            "Small Business": [
                Company("Regional accounting firm with 25 employees", "54",
                        "Professional Services", "Small Business", "20-30", None,
                        "Private", "Suburban office"),
            ],
            "Startup": [
                Company("3-person consulting practice", "54", "Professional Services",
                        "Startup", "1-5", None, "Private", "Remote-first"),
            ]
        },
        # ... 20 NAICS sectors with 4 size categories each
    }

    def sample_company(self, naics_code: str,
                       size_category: str | None = None,
                       seed: int = None) -> Company:
        """Sample a company with optional size preference."""
```

### 2.5 Realistic Name Generation

```python
@dataclass
class PersonaName:
    first_name: str
    last_name: str
    full_name: str
    formal_name: str  # "Dr. Williams" or "Mr. Chen"
    email_username: str  # "sarah.chen"
    generation_hint: str  # "GenZ", "Millennial", "GenX", "Boomer"

class NameGenerator:
    """Generate diverse, realistic names for personas."""

    # Name pools with demographic tagging
    FIRST_NAMES = {
        "GenZ": ["Jayden", "Olivia", "Aiden", "Isabella", "Kai", "Luna", ...],
        "Millennial": ["Jessica", "Michael", "Ashley", "Christopher", "Amanda", ...],
        "GenX": ["Jennifer", "David", "Michelle", "Brian", "Heather", ...],
        "Boomer": ["Patricia", "Robert", "Linda", "William", "Barbara", ...],
    }

    # Diverse last names reflecting US demographics
    LAST_NAMES = [
        # Hispanic origin
        "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        # Asian origin
        "Chen", "Kim", "Nguyen", "Patel", "Singh", "Lee", "Wong", "Park",
        # European origin
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
        "Wilson", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
        # Other
        "Ali", "Khan", "Mohamed", "O'Brien", "O'Connor", "Murphy",
    ]

    def generate(self, generation: str, gender_hint: str = None,
                 seed: int = None) -> PersonaName:
        """Generate a realistic name with demographic consistency."""
```

---

## 3. Prompt Generation Methodology

### 3.1 Core Prompt Schema

```python
class WritingPrompt(BaseModel):
    """Complete schema for a writing evaluation prompt."""

    # Identification
    prompt_id: str  # UUID
    source_task_id: str  # O*NET task ID
    random_seed: int  # For reproducibility

    # O*NET Source Data
    onetsoc_code: str
    occupation_title: str
    occupation_description: str
    task_statement: str  # Original O*NET task
    job_zone: int
    soc_major_code: str
    soc_major_name: str
    inferred_writing_category: str

    # Industry Context
    naics_code: str
    naics_sector_name: str
    company: CompanyContext

    # Writer Persona
    writer: WriterPersona

    # Recipient/Audience Persona(s)
    recipients: list[RecipientPersona]
    audience_size: str  # "one-on-one", "small_group", "department", "company-wide", "public"

    # Communication Context
    channel: str  # Inferred: "email", "memo", "report", "proposal", "slack", etc.
    formality_level: int  # 1-5 scale
    urgency_level: str  # "routine", "important", "urgent", "critical"
    emotional_context: str  # "routine", "crisis", "celebration", "conflict", "bad_news"
    message_position: str  # "initial", "reply", "follow_up"
    relationship_context: str  # "first_contact", "ongoing", "established"

    # Regional/Language
    language: str = "en"
    language_variant: str = "en-US"
    recipient_english_variant: str  # "en-US", "en-GB", "en-AU", "non-native"
    writer_english_variant: str

    # Additional Context Elements
    temporal_context: TemporalContext | None  # Date, deadlines, recent events
    attachments: list[Attachment] | None  # Mock referenced content
    prior_messages: list[PriorMessage] | None  # For reply-to scenarios
    tone_examples: list[ToneExample] | None  # For tone-matching tasks
    existing_draft: str | None  # For revision tasks

    # Task Variations
    has_competing_objectives: bool
    competing_objectives: list[str] | None
    has_explicit_constraints: bool
    explicit_constraints: list[str] | None  # "under 100 words", etc.
    is_deliberately_vague: bool
    is_revision_task: bool
    is_sensitive_topic: bool
    sensitive_topic_category: str | None

    # The Final Prompt
    generated_prompt_text: str  # Full prompt to send to models

    # Metadata for Analysis
    generation_timestamp: datetime
    phase_1_model: str | None  # Which model did offline generation
    phase_3_model: str | None  # Which model did enrichment
```

### 3.2 Three-Phase Generation Pipeline

#### Phase 1: Offline LLM Generation (Persona Variations)

```python
class Phase1Generator:
    """Generate diverse persona/context variations for O*NET tasks."""

    async def generate_personas_for_task(self,
                                          task: ONetTask,
                                          num_variations: int = 5,
                                          model: str = "gemini-3-pro") -> list[PersonaVariation]:
        """
        Use LLM to generate realistic persona variations for a task.

        Prompt template:
        ```
        Given this occupational task from the US Department of Labor:

        Occupation: {occupation_title}
        Task: {task_statement}
        Skill Level (Job Zone 1-5): {job_zone}

        Generate {num_variations} diverse, realistic scenarios where someone
        would perform this writing task. For each scenario, provide:

        1. Writer persona (age range, experience level, generation)
        2. Company context (type, size, industry specifics)
        3. Recipient(s) and their relationship to writer
        4. Communication urgency and emotional context
        5. Any specific constraints or competing objectives

        Ensure maximum diversity across scenarios - vary ages from 22 to 65+,
        company sizes from startups to Fortune 500, urgency from routine to critical,
        and emotional context from celebratory to difficult conversations.

        Output as JSON array.
        ```
        """
```

#### Phase 2: Algorithmic Combinations

```python
class Phase2Combiner:
    """Programmatically combine O*NET tasks with context dimensions."""

    def __init__(self,
                 onet_extractor: ONetExtractor,
                 naics_mapper: NAICSMapper,
                 company_sampler: CompanySampler,
                 name_generator: NameGenerator):
        self.onet = onet_extractor
        self.naics = naics_mapper
        self.companies = company_sampler
        self.names = name_generator

    def generate_combinations(self,
                               tasks: list[ONetTask],
                               num_prompts: int,
                               config: SamplingConfig,
                               seed: int) -> list[PartialPrompt]:
        """
        Generate deterministic combinations ensuring diversity.

        Stratification dimensions:
        - Job zone (5 levels)
        - SOC major group (22 groups)
        - NAICS sector (20 sectors)
        - Writing category (10 categories)
        - Formality level (5 levels)
        - Age/generation (4 groups)
        - Company size (4 categories)
        """
        rng = np.random.default_rng(seed)

        # Calculate quotas per stratum
        quotas = self._calculate_quotas(tasks, num_prompts, config)

        prompts = []
        for task in self._stratified_sample(tasks, quotas, rng):
            partial = PartialPrompt(
                source_task=task,
                naics_code=self.naics.sample_industry(task.soc_major_code, rng),
                company=self.companies.sample_company(...),
                formality=self._sample_formality(task.job_zone, rng),
                writer_generation=self._sample_generation(rng),
                # ... other dimensions
            )
            prompts.append(partial)

        return prompts
```

#### Phase 3: LLM Enrichment

```python
class Phase3Enricher:
    """Add rich context to prompts requiring additional detail."""

    async def enrich_prompt(self,
                            partial: PartialPrompt,
                            model: str = "gemini-3-pro") -> WritingPrompt:
        """
        Enrich partial prompts with realistic details.

        Enrichment tasks:
        - Generate specific names for writer and recipients
        - Add temporal context where relevant
        - Create mock attachments for tasks referencing documents
        - Generate prior message content for reply scenarios
        - Add competing objectives where realistic
        - Create tone examples for matching tasks
        """

        enrichment_prompt = self._build_enrichment_prompt(partial)
        response = await self.api.complete(model, enrichment_prompt)
        enriched = self._parse_enrichment(response)

        return self._assemble_final_prompt(partial, enriched)

    def _build_enrichment_prompt(self, partial: PartialPrompt) -> str:
        """
        Build the enrichment prompt based on what the task needs.

        For reply scenarios: "Generate a realistic prior message that this
        reply would be responding to..."

        For document references: "Generate a brief summary of the Q3 report
        that would be attached..."

        For competing objectives: "Identify any natural tensions in this
        writing task..."
        """
```

### 3.3 Final Prompt Assembly

```python
class PromptAssembler:
    """Assemble all components into the final prompt text."""

    def assemble(self, prompt: WritingPrompt) -> str:
        """
        Create the final prompt text that will be sent to models.

        Structure varies based on complexity:

        Simple prompt:
        ```
        You are {writer.name}, a {writer.title} at {company.name}.

        Write an email to {recipient.name} ({recipient.title}) to
        {task_description}.
        ```

        Complex prompt with context:
        ```
        Context:
        You are {writer.name}, a {writer.age}-year-old {writer.title} at
        {company.name}, a {company.size_description} in {company.industry}.
        It's {temporal.current_date}, and {temporal.context}.

        Previous message from {sender}:
        ---
        {prior_message}
        ---

        Attached: {attachment.description}
        Key figures: {attachment.summary}

        Task:
        Write a reply to {recipient.name} that {task_objective}.

        Consider:
        - {competing_objective_1}
        - {competing_objective_2}
        ```
        """
```

---

## 4. Evaluation Flow and Judging System

### 4.1 Response Generation Engine

```python
class ResponseGenerator:
    """Generate responses from all models being evaluated."""

    def __init__(self, api_client: OpenRouterClient, config: EvalConfig):
        self.api = api_client
        self.config = config

    async def generate_responses(self,
                                  prompt: WritingPrompt,
                                  model_pair: ModelPair) -> tuple[Response, Response]:
        """
        Generate responses from both models in a pair.

        Returns responses with full metadata:
        - response_text
        - latency_ms
        - token_counts (input, output)
        - finish_reason
        - model_version
        - timestamp
        """

        # Run both models in parallel
        gemini_task = self.api.complete(
            model=model_pair.gemini_model,
            prompt=prompt.generated_prompt_text,
            temperature=0.7,  # Allow some creativity
        )
        competitor_task = self.api.complete(
            model=model_pair.competitor_model,
            prompt=prompt.generated_prompt_text,
            temperature=0.7,
        )

        gemini_resp, competitor_resp = await asyncio.gather(
            gemini_task, competitor_task,
            return_exceptions=True
        )

        return self._process_responses(gemini_resp, competitor_resp)
```

### 4.2 Multi-Judge Ensemble System

```python
class JudgingEnsemble:
    """Coordinate multi-model, multi-persona judging."""

    JUDGE_MODELS = [
        "anthropic/claude-opus-4.5",
        "openai/gpt-5.2",
        "google/gemini-3-pro"
    ]

    JUDGE_PERSONAS = {
        "writing_expert": """
            You are an expert writing professional with 20+ years of experience
            evaluating business and professional communication. Assess the writing
            based on craft quality: clarity, structure, tone appropriateness,
            conciseness, professionalism, and effectiveness of language.

            Consider whether the writing:
            - Uses appropriate vocabulary for the context
            - Has logical flow and structure
            - Maintains consistent and appropriate tone
            - Is the right length (not too verbose, not too sparse)
            - Avoids AI-sounding cliches and boilerplate
            - Reads as authentic human communication
        """,

        "target_recipient": """
            You are the intended recipient of this communication. Based on the
            scenario described, evaluate which response you would prefer to receive.

            Consider:
            - Does it address your needs/questions effectively?
            - Is the tone appropriate for your relationship with the sender?
            - Would you be able to act on this communication?
            - Does it feel genuine and personal, or generic?
            - Does it respect your time with appropriate length?
        """
    }

    async def judge_comparison(self,
                                prompt: WritingPrompt,
                                response_a: Response,
                                response_b: Response,
                                config: JudgeConfig) -> JudgmentResult:
        """
        Run full judging pipeline for a single comparison.

        Steps:
        1. For each judge model
        2. For each judge persona
        3. Run N votes (default 5)
        4. Aggregate per-judge majority
        5. Aggregate cross-judge majority
        """

        all_judgments = []

        for judge_model in self.JUDGE_MODELS[:config.num_judges]:
            for persona_name, persona_prompt in self._get_personas(config):
                votes = await self._run_votes(
                    judge_model=judge_model,
                    persona=persona_prompt,
                    prompt=prompt,
                    response_a=response_a,
                    response_b=response_b,
                    num_votes=config.votes_per_judge
                )
                all_judgments.append(JudgeVotes(
                    judge_model=judge_model,
                    persona=persona_name,
                    votes=votes,
                    majority=self._compute_majority(votes)
                ))

        return self._aggregate_judgments(all_judgments)
```

### 4.3 Position Bias Mitigation

```python
class PositionBiasHandler:
    """Handle response ordering to eliminate position bias."""

    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def get_presentation_order(self,
                                prompt_id: str,
                                judge_model: str,
                                vote_number: int) -> tuple[str, str]:
        """
        Deterministically decide which response is A vs B.

        Uses hash of (prompt_id, judge_model, vote_number) to ensure:
        - Different votes may see different orderings
        - Ordering is reproducible from seed
        - Each model appears in each position roughly equally
        """
        hash_input = f"{prompt_id}:{judge_model}:{vote_number}:{self.seed}"
        order_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # First bit determines order
        gemini_first = int(order_hash[0], 16) % 2 == 0
        return ("gemini", "competitor") if gemini_first else ("competitor", "gemini")

    def build_judge_prompt(self,
                           prompt: WritingPrompt,
                           response_a: Response,
                           response_b: Response,
                           persona_prompt: str,
                           order: tuple[str, str]) -> str:
        """Build the full judge prompt with proper ordering."""

        return f"""
{persona_prompt}

## Writing Task Context

{self._format_task_context(prompt)}

## Response A

{response_a.text if order[0] == "gemini" else response_b.text}

## Response B

{response_b.text if order[0] == "gemini" else response_a.text}

## Evaluation Criteria

{EVALUATION_RUBRIC}

## Your Judgment

Based on your expertise and the specific context of this writing task,
which response is better? Consider all criteria but focus especially on
authenticity and appropriateness for this specific scenario.

Respond with ONLY one of:
- "A" if Response A is clearly better
- "B" if Response B is clearly better
- "TIE" if they are roughly equivalent

Your judgment:
"""
```

### 4.4 Evaluation Rubric

```python
EVALUATION_RUBRIC = """
Evaluate each response on these criteria:

1. **Task Completion**: Does the response fully address what was asked?

2. **Tone Appropriateness**: Is the tone right for the relationship,
   formality level, and context described?

3. **Clarity & Structure**: Is the writing clear, well-organized, and
   easy to follow?

4. **Length Appropriateness**: Is it the right length for this task?
   (Not padding, not missing key information)

5. **Authenticity**: Does it read like genuine human writing, or does
   it feel AI-generated? Look for:
   - Overuse of "I hope this email finds you well"
   - Excessive bullet points where prose is more natural
   - Generic phrases like "Please don't hesitate to reach out"
   - Overly formal when casual is appropriate (or vice versa)
   - Lack of personality or voice

6. **Effectiveness**: Would this communication achieve its purpose
   with the intended recipient?

7. **Instruction Following**: If specific constraints were given
   (length, format, tone directives), were they followed?

Consider the full context: who is writing, to whom, for what purpose,
in what organizational/emotional context. The best response is one that
a skilled human professional in this exact situation would produce.
"""
```

### 4.5 Failure Handling

```python
class FailureHandler:
    """Handle model failures and determine auto-losses."""

    FAILURE_CATEGORIES = {
        "safety_refusal": "Model refused citing safety/policy",
        "capability_limitation": "Model stated inability to complete",
        "misunderstanding": "Model interpreted task incorrectly",
        "incomplete_response": "Model started but didn't finish",
        "off_topic": "Model responded but not to the task",
        "timeout": "Model didn't respond in time",
        "api_error": "API returned an error",
        "empty_response": "Model returned empty/whitespace only",
    }

    def categorize_failure(self,
                           response: Response | Exception,
                           prompt: WritingPrompt) -> FailureResult:
        """
        Categorize why a response failed and record for analysis.

        Returns:
        - failure_category
        - is_auto_loss (always True for failures)
        - analysis_notes
        """

        if isinstance(response, TimeoutError):
            return FailureResult("timeout", True, "Request timed out")

        if isinstance(response, APIError):
            return FailureResult("api_error", True, str(response))

        text = response.text.strip() if response else ""

        if not text:
            return FailureResult("empty_response", True, "Empty response")

        # Detect safety refusals
        safety_phrases = [
            "I cannot", "I'm not able to", "I won't", "against my guidelines",
            "I don't feel comfortable", "potentially harmful"
        ]
        if any(phrase.lower() in text.lower() for phrase in safety_phrases):
            return FailureResult("safety_refusal", True, text[:200])

        # ... additional categorization logic
```

---

## 5. Results Storage and Analysis

### 5.1 SQLite Database Schema

```sql
-- Core tables
CREATE TABLE eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    config_json TEXT,
    preset_name TEXT,
    random_seed INTEGER,
    status TEXT  -- 'running', 'completed', 'interrupted'
);

CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES eval_runs(run_id),
    source_task_id TEXT,
    onetsoc_code TEXT,
    occupation_title TEXT,
    job_zone INTEGER,
    soc_major_code TEXT,
    naics_code TEXT,
    writing_category TEXT,
    formality_level INTEGER,
    writer_generation TEXT,
    company_size TEXT,
    urgency_level TEXT,
    emotional_context TEXT,
    is_sensitive_topic BOOLEAN,
    sensitive_topic_category TEXT,
    is_revision_task BOOLEAN,
    has_competing_objectives BOOLEAN,
    prompt_text TEXT,
    created_at TIMESTAMP
);

CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    model_name TEXT,
    model_tier TEXT,  -- 'pro' or 'flash'
    response_text TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    finish_reason TEXT,
    is_failure BOOLEAN,
    failure_category TEXT,
    word_count INTEGER,
    char_count INTEGER,
    created_at TIMESTAMP
);

CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    gemini_response_id TEXT REFERENCES responses(response_id),
    competitor_response_id TEXT REFERENCES responses(response_id),
    competitor_model TEXT,
    final_winner TEXT,  -- 'gemini', 'competitor', 'tie'
    gemini_auto_loss BOOLEAN,
    competitor_auto_loss BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    judge_model TEXT,
    judge_persona TEXT,
    vote_number INTEGER,
    presentation_order TEXT,  -- 'gemini_first' or 'competitor_first'
    raw_judgment TEXT,  -- 'A' or 'B' or 'TIE'
    winner TEXT,  -- normalized to 'gemini', 'competitor', 'tie'
    judge_response_text TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMP
);

CREATE TABLE judge_aggregations (
    aggregation_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    judge_model TEXT,
    judge_persona TEXT,
    votes_gemini INTEGER,
    votes_competitor INTEGER,
    votes_tie INTEGER,
    majority_winner TEXT,
    created_at TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_prompts_run ON prompts(run_id);
CREATE INDEX idx_prompts_occupation ON prompts(onetsoc_code);
CREATE INDEX idx_prompts_category ON prompts(writing_category);
CREATE INDEX idx_responses_model ON responses(model_name);
CREATE INDEX idx_comparisons_winner ON comparisons(final_winner);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
```

### 5.2 Statistical Analysis Module

```python
class StatisticalAnalyzer:
    """Compute win rates, confidence intervals, and significance tests."""

    def compute_win_rate(self,
                         comparisons: list[Comparison],
                         model_pair: str) -> WinRateResult:
        """
        Compute win rate with confidence interval.

        Uses Wilson score interval for binomial proportion.
        """
        wins = sum(1 for c in comparisons if c.winner == "gemini")
        losses = sum(1 for c in comparisons if c.winner == "competitor")
        ties = sum(1 for c in comparisons if c.winner == "tie")
        total = len(comparisons)

        # Win rate (excluding ties)
        contested = wins + losses
        if contested == 0:
            return WinRateResult(
                win_rate=0.5,
                confidence_interval=(0.0, 1.0),
                n_wins=0, n_losses=0, n_ties=ties,
                statistical_power=0.0
            )

        win_rate = wins / contested
        ci_low, ci_high = self._wilson_score_interval(wins, contested, 0.95)

        return WinRateResult(
            win_rate=win_rate,
            confidence_interval=(ci_low, ci_high),
            n_wins=wins,
            n_losses=losses,
            n_ties=ties,
            statistical_power=self._compute_power(contested, win_rate)
        )

    def _wilson_score_interval(self,
                                successes: int,
                                n: int,
                                confidence: float) -> tuple[float, float]:
        """Wilson score interval for binomial proportion."""
        from scipy import stats

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = successes / n

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denominator
        spread = z * np.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denominator

        return (center - spread, center + spread)

    def compute_inter_judge_agreement(self,
                                       judgments: list[Judgment]) -> float:
        """
        Compute Cohen's Kappa for inter-judge agreement.

        Compares judgments across judge models for same comparisons.
        """
        from sklearn.metrics import cohen_kappa_score

        # Group judgments by comparison
        by_comparison = defaultdict(list)
        for j in judgments:
            by_comparison[j.comparison_id].append(j)

        # Build rating matrices for each pair of judges
        judge_pairs = list(combinations(self.judge_models, 2))
        kappas = []

        for judge_a, judge_b in judge_pairs:
            ratings_a = []
            ratings_b = []
            for comp_id, judges in by_comparison.items():
                a_judgment = next((j for j in judges if j.judge_model == judge_a), None)
                b_judgment = next((j for j in judges if j.judge_model == judge_b), None)
                if a_judgment and b_judgment:
                    ratings_a.append(a_judgment.majority_winner)
                    ratings_b.append(b_judgment.majority_winner)

            if len(ratings_a) > 10:  # Minimum for meaningful kappa
                kappas.append(cohen_kappa_score(ratings_a, ratings_b))

        return np.mean(kappas) if kappas else 0.0
```

### 5.3 Bias Detection System

```python
class BiasDetector:
    """Detect systematic biases in models and judges."""

    def detect_position_bias(self, judgments: list[Judgment]) -> PositionBiasResult:
        """
        Check if judges systematically prefer Response A over B.

        Uses chi-square test for independence.
        """
        a_wins_when_gemini_first = sum(
            1 for j in judgments
            if j.presentation_order == "gemini_first" and j.raw_judgment == "A"
        )
        b_wins_when_gemini_first = sum(
            1 for j in judgments
            if j.presentation_order == "gemini_first" and j.raw_judgment == "B"
        )
        a_wins_when_competitor_first = sum(
            1 for j in judgments
            if j.presentation_order == "competitor_first" and j.raw_judgment == "A"
        )
        b_wins_when_competitor_first = sum(
            1 for j in judgments
            if j.presentation_order == "competitor_first" and j.raw_judgment == "B"
        )

        # Chi-square test
        contingency_table = [
            [a_wins_when_gemini_first, b_wins_when_gemini_first],
            [a_wins_when_competitor_first, b_wins_when_competitor_first]
        ]
        chi2, p_value, _, _ = stats.chi2_contingency(contingency_table)

        return PositionBiasResult(
            a_preference_rate=...,
            chi_square=chi2,
            p_value=p_value,
            is_significant=p_value < 0.05
        )

    def detect_length_bias(self,
                           responses: list[Response],
                           judgments: list[Judgment]) -> LengthBiasResult:
        """Check if judges prefer longer or shorter responses."""

        winner_lengths = []
        loser_lengths = []

        for j in judgments:
            winner_resp = ... # Get winning response
            loser_resp = ... # Get losing response
            winner_lengths.append(winner_resp.word_count)
            loser_lengths.append(loser_resp.word_count)

        # Mann-Whitney U test
        statistic, p_value = stats.mannwhitneyu(winner_lengths, loser_lengths)

        return LengthBiasResult(
            avg_winner_length=np.mean(winner_lengths),
            avg_loser_length=np.mean(loser_lengths),
            u_statistic=statistic,
            p_value=p_value,
            is_significant=p_value < 0.05
        )

    def detect_model_length_bias(self, responses: list[Response]) -> dict:
        """Check if certain models consistently write longer/shorter."""

        by_model = defaultdict(list)
        for r in responses:
            by_model[r.model_name].append(r.word_count)

        return {
            model: {
                "mean": np.mean(lengths),
                "std": np.std(lengths),
                "median": np.median(lengths)
            }
            for model, lengths in by_model.items()
        }
```

### 5.4 Weakness Identification

```python
class WeaknessAnalyzer:
    """Identify specific areas where Gemini underperforms."""

    def analyze_weaknesses(self,
                           db: Database,
                           significance_threshold: float = 0.05) -> WeaknessReport:
        """
        Find dimensions where Gemini has statistically significant lower win rates.

        Dimensions analyzed:
        - By occupation (SOC major group)
        - By writing category
        - By formality level
        - By job zone (skill level)
        - By urgency level
        - By emotional context
        - By task type (revision vs new)
        - By sensitive topic category
        - By company size
        - By writer generation
        """

        weaknesses = []

        # Analyze each dimension
        for dimension in self.ANALYSIS_DIMENSIONS:
            dimension_results = self._analyze_dimension(db, dimension)

            for category, result in dimension_results.items():
                if result.win_rate < 0.45 and result.is_significant:
                    weaknesses.append(Weakness(
                        dimension=dimension,
                        category=category,
                        win_rate=result.win_rate,
                        confidence_interval=result.ci,
                        sample_size=result.n,
                        p_value=result.p_value,
                        example_losses=self._get_example_losses(db, dimension, category)
                    ))

        # Rank by severity (lowest win rate * sample size weight)
        weaknesses.sort(key=lambda w: w.win_rate * np.log(w.sample_size + 1))

        return WeaknessReport(
            total_prompts=db.count_prompts(),
            overall_win_rate=db.compute_overall_win_rate(),
            weaknesses=weaknesses,
            strongest_areas=self._find_strengths(db)
        )
```

---

## 6. TUI Implementation

### 6.1 Textual Application Structure

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, DataTable, ProgressBar
from textual.screen import Screen

class GeminiEvalApp(App):
    """Main TUI application for Gemini Writing Evaluation."""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("q", "quit_safely", "Quit"),
        ("p", "pause", "Pause"),
        ("d", "toggle_detail", "Detail"),
        ("s", "show_stats", "Statistics"),
        ("h", "show_help", "Help"),
    ]

    def __init__(self, eval_runner: EvalRunner):
        super().__init__()
        self.runner = eval_runner
        self.is_paused = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield ProgressDashboard()
        yield Footer()

    async def on_mount(self):
        """Start the evaluation loop when app mounts."""
        self.run_worker(self._run_evaluation())

    async def _run_evaluation(self):
        """Main evaluation loop with progress updates."""
        async for progress in self.runner.run():
            self.query_one(ProgressDashboard).update(progress)

class ProgressDashboard(Container):
    """Main progress dashboard widget."""

    def compose(self) -> ComposeResult:
        yield OverallProgress()
        yield ModelPairProgress()
        yield CurrentBatchPanel()
        yield LiveStatistics()
        yield ActivityLog()
        yield ErrorSummary()
```

### 6.2 Progress Dashboard Components

```python
class OverallProgress(Static):
    """Overall evaluation progress display."""

    def update(self, progress: EvalProgress):
        total = progress.total_prompts
        completed = progress.completed_prompts
        pct = (completed / total) * 100 if total > 0 else 0

        elapsed = progress.elapsed_time
        eta = progress.estimated_remaining

        phase_indicators = {
            "generation": "✓" if progress.generation_complete else ("◐" if progress.in_generation else "○"),
            "judging": "✓" if progress.judging_complete else ("◐" if progress.in_judging else "○"),
            "analysis": "✓" if progress.analysis_complete else "○"
        }

        bar = self._render_progress_bar(pct, 50)

        self.update(f"""
┌─ OVERALL PROGRESS ─────────────────────────────────────────────────────────┐
│ {bar}  {completed}/{total} prompts ({pct:.1f}%)         │
│                                                                            │
│ Phase: {progress.current_phase}  [Generation {phase_indicators['generation']}] [Judging {phase_indicators['judging']}] [Analysis {phase_indicators['analysis']}]                   │
│ Elapsed: {elapsed}  |  ETA: {eta}                                         │
└────────────────────────────────────────────────────────────────────────────┘
""")

class ModelPairProgress(Container):
    """Progress for each model pair being evaluated."""

    def compose(self) -> ComposeResult:
        for pair in self.model_pairs:
            yield ModelPairRow(pair)

    def update(self, progress: EvalProgress):
        for pair_name, pair_progress in progress.model_pairs.items():
            row = self.query_one(f"#pair-{pair_name}")
            row.update(pair_progress)

class CurrentBatchPanel(Container):
    """Shows details of the current prompt being evaluated."""

    def update(self, progress: EvalProgress):
        current = progress.current_prompt
        if not current:
            return

        response_status = self._format_response_status(progress.response_status)
        judging_status = self._format_judging_status(progress.judging_status)

        self.update(f"""
┌─ CURRENT BATCH ────────────────────────────────────────────────────────────┐
│ Prompt #{current.number}: "{current.task_summary[:60]}..."                 │
│ Occupation: {current.occupation} ({current.onetsoc_code})                  │
│ Industry: {current.industry} (NAICS {current.naics_code})                  │
│                                                                            │
│ ┌─ Responses ───────────┐  ┌─ Judging ─────────────────────────────────┐  │
{response_status}
{judging_status}
│ └───────────────────────┘  └───────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
""")

class LiveStatistics(Container):
    """Real-time statistics panel."""

    def update(self, progress: EvalProgress):
        stats = progress.live_stats

        win_rates = "\n".join([
            f"│ vs {opponent}: {rate:.1f}% ± {ci:.1f}%"
            for opponent, rate, ci in stats.win_rates
        ])

        self.update(f"""
┌─ LIVE STATISTICS ──────────────────────────────────────────────────────────┐
│ Win Rates (Running)           │ Performance                                │
│ ─────────────────────────     │ ──────────────────────────────────         │
{win_rates}
│                               │ Avg response time:  {stats.avg_response_time:.1f}s                   │
│ Judge Agreement: {stats.kappa:.2f} κ       │ Avg judge time:     {stats.avg_judge_time:.1f}s                   │
│                               │ API calls/min:      {stats.api_calls_per_min}                     │
│                               │ Est. cost so far:   ${stats.cost_so_far:.2f}                │
└────────────────────────────────────────────────────────────────────────────┘
""")

class ActivityLog(Container):
    """Scrolling log of recent activity."""

    def __init__(self):
        super().__init__()
        self.log_entries = deque(maxlen=100)

    def add_entry(self, entry: LogEntry):
        self.log_entries.append(entry)
        self._refresh_display()

    def _refresh_display(self):
        # Show last 5 entries
        recent = list(self.log_entries)[-5:]
        formatted = "\n".join(self._format_entry(e) for e in recent)
        self.update(f"""
┌─ RECENT ACTIVITY ──────────────────────────────────────────────────────────┐
{formatted}
└────────────────────────────────────────────────────────────────────────────┘
""")
```

### 6.3 Results Viewer Screen

```python
class ResultsViewerScreen(Screen):
    """Interactive viewer for exploring evaluation results."""

    BINDINGS = [
        ("f", "filter", "Filter"),
        ("s", "sort", "Sort"),
        ("enter", "view_detail", "View Detail"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield FilterBar()
        yield ResultsTable()
        yield DetailPanel()
        yield Footer()

    def on_filter_changed(self, event: FilterChanged):
        """Apply new filters to results."""
        filters = event.filters
        results = self.db.query_comparisons(
            occupation_filter=filters.occupation,
            industry_filter=filters.industry,
            winner_filter=filters.winner,
            writing_category=filters.category,
            formality_range=filters.formality,
        )
        self.query_one(ResultsTable).update(results)

class ResultsTable(DataTable):
    """Table showing comparison results."""

    COLUMNS = [
        "Prompt", "Occupation", "Category", "Gemini", "Competitor",
        "Winner", "Judge Agreement"
    ]

    def on_row_selected(self, event: DataTable.RowSelected):
        """Show detail panel when row is selected."""
        comparison_id = event.row_key
        self.post_message(ShowComparisonDetail(comparison_id))

class ComparisonDetailPanel(Container):
    """Side-by-side view of responses and judgments."""

    def show_comparison(self, comparison: Comparison):
        prompt_panel = self._render_prompt(comparison.prompt)
        gemini_panel = self._render_response(comparison.gemini_response, "Gemini")
        competitor_panel = self._render_response(comparison.competitor_response,
                                                  comparison.competitor_model)
        judgment_panel = self._render_judgments(comparison.judgments)

        self.update(f"""
╭─ PROMPT ─────────────────────────────────────────────────────────────────╮
{prompt_panel}
╰──────────────────────────────────────────────────────────────────────────╯

╭─ GEMINI RESPONSE ───────────────────╮  ╭─ {comparison.competitor_model} ────────────────╮
{gemini_panel}                            {competitor_panel}
╰─────────────────────────────────────╯  ╰─────────────────────────────────────╯

╭─ JUDGMENTS ──────────────────────────────────────────────────────────────╮
{judgment_panel}
╰──────────────────────────────────────────────────────────────────────────╯
""")
```

---

## 7. Robustness Requirements Implementation

### 7.1 Checkpoint System

```python
@dataclass
class Checkpoint:
    """Checkpoint state for resumability."""
    run_id: str
    config: EvalConfig
    random_seed: int

    # Progress tracking
    total_prompts: int
    completed_prompt_ids: set[str]
    in_progress_prompt_id: str | None

    # Phase tracking
    generation_complete: bool
    prompts_generated: list[str]  # IDs of generated prompts

    responses_complete: dict[str, set[str]]  # prompt_id -> set of model names

    judgments_complete: dict[str, set[str]]  # comparison_id -> set of judge keys

    # Timing
    started_at: datetime
    last_checkpoint_at: datetime

    def save(self, path: Path):
        """Save checkpoint to JSON file."""
        with open(path, "w") as f:
            json.dump(asdict(self), f, default=str, indent=2)

    @classmethod
    def load(cls, path: Path) -> "Checkpoint":
        """Load checkpoint from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

class CheckpointManager:
    """Manage checkpoint saving and loading."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoint_path = run_dir / "checkpoint.json"
        self.checkpoint: Checkpoint | None = None
        self._save_interval = 10  # Save every N completions
        self._completions_since_save = 0

    def initialize(self, config: EvalConfig, seed: int) -> Checkpoint:
        """Create new checkpoint for fresh run."""
        self.checkpoint = Checkpoint(
            run_id=self.run_dir.name,
            config=config,
            random_seed=seed,
            total_prompts=0,
            completed_prompt_ids=set(),
            in_progress_prompt_id=None,
            generation_complete=False,
            prompts_generated=[],
            responses_complete={},
            judgments_complete={},
            started_at=datetime.now(),
            last_checkpoint_at=datetime.now(),
        )
        self.save()
        return self.checkpoint

    def resume(self) -> Checkpoint:
        """Resume from existing checkpoint."""
        self.checkpoint = Checkpoint.load(self.checkpoint_path)
        return self.checkpoint

    def mark_prompt_complete(self, prompt_id: str):
        """Mark a prompt as fully evaluated."""
        self.checkpoint.completed_prompt_ids.add(prompt_id)
        self.checkpoint.in_progress_prompt_id = None
        self._completions_since_save += 1

        if self._completions_since_save >= self._save_interval:
            self.save()
            self._completions_since_save = 0

    def save(self):
        """Save current checkpoint state."""
        self.checkpoint.last_checkpoint_at = datetime.now()
        self.checkpoint.save(self.checkpoint_path)
```

### 7.2 Retry and Rate Limiting

```python
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1

class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self,
                 requests_per_minute: int = 60,
                 tokens_per_minute: int = 100000):
        self.request_bucket = TokenBucket(requests_per_minute, 60)
        self.token_bucket = TokenBucket(tokens_per_minute, 60)

    async def acquire(self, estimated_tokens: int = 1000):
        """Wait until rate limit allows the request."""
        await self.request_bucket.acquire(1)
        await self.token_bucket.acquire(estimated_tokens)

class APIClient:
    """OpenRouter API client with retry and rate limiting."""

    def __init__(self,
                 api_key: str,
                 rate_limiter: RateLimiter,
                 retry_config: RetryConfig):
        self.client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(120.0)
        )
        self.rate_limiter = rate_limiter
        self.retry_config = retry_config

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        wait=wait_exponential_jitter(initial=1, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def complete(self,
                       model: str,
                       prompt: str,
                       temperature: float = 0.7) -> CompletionResponse:
        """Make a completion request with retry logic."""

        # Estimate tokens for rate limiting
        estimated_tokens = len(prompt) // 4 + 500
        await self.rate_limiter.acquire(estimated_tokens)

        response = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
        )

        if response.status_code == 429:  # Rate limited
            retry_after = int(response.headers.get("retry-after", 60))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            raise httpx.HTTPStatusError("Rate limited", request=response.request,
                                         response=response)

        response.raise_for_status()
        return self._parse_response(response.json())
```

### 7.3 Graceful Shutdown

```python
class GracefulShutdown:
    """Handle graceful shutdown on interruption."""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint = checkpoint_manager
        self.shutdown_requested = False
        self._setup_handlers()

    def _setup_handlers(self):
        """Register signal handlers."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal."""
        if self.shutdown_requested:
            # Second signal - force quit
            logger.error("Force quit requested")
            sys.exit(1)

        logger.info("Shutdown requested, completing current task...")
        self.shutdown_requested = True

    async def should_continue(self) -> bool:
        """Check if evaluation should continue."""
        if self.shutdown_requested:
            logger.info("Saving checkpoint and shutting down...")
            self.checkpoint.save()
            return False
        return True
```

---

## 8. Cost Estimation System

### 8.1 Pricing Data

```python
# OpenRouter pricing as of Jan 2026 (per 1M tokens)
MODEL_PRICING = {
    # Pro tier
    "google/gemini-3-pro": {"input": 2.50, "output": 10.00},
    "openai/gpt-5.2": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4.5": {"input": 15.00, "output": 75.00},
    "xai/grok-4.1": {"input": 5.00, "output": 25.00},
    "moonshot/kimi-k2": {"input": 2.00, "output": 8.00},

    # Flash tier
    "google/gemini-3-flash": {"input": 0.10, "output": 0.40},
    "openai/gpt-4.1": {"input": 0.50, "output": 2.00},
    "anthropic/claude-sonnet": {"input": 3.00, "output": 15.00},
}

class CostEstimator:
    """Estimate costs before and during evaluation runs."""

    # Average token counts from analysis
    AVG_PROMPT_TOKENS = 800
    AVG_RESPONSE_TOKENS = 400
    AVG_JUDGE_PROMPT_TOKENS = 2000  # Includes both responses
    AVG_JUDGE_RESPONSE_TOKENS = 50

    def estimate_run_cost(self, config: EvalConfig) -> CostEstimate:
        """Estimate total cost for an evaluation run."""

        # Response generation costs
        response_costs = {}
        for pair in config.model_pairs:
            gemini_cost = self._estimate_model_cost(
                pair.gemini_model,
                self.AVG_PROMPT_TOKENS,
                self.AVG_RESPONSE_TOKENS,
                config.num_prompts
            )
            competitor_cost = self._estimate_model_cost(
                pair.competitor_model,
                self.AVG_PROMPT_TOKENS,
                self.AVG_RESPONSE_TOKENS,
                config.num_prompts
            )
            response_costs[pair.name] = gemini_cost + competitor_cost

        # Judging costs
        num_judge_calls = (
            config.num_prompts *
            len(config.model_pairs) *
            config.num_judges *
            config.votes_per_judge *
            len(config.judge_personas)
        )

        judge_costs = {}
        for judge_model in config.judge_models:
            judge_costs[judge_model] = self._estimate_model_cost(
                judge_model,
                self.AVG_JUDGE_PROMPT_TOKENS,
                self.AVG_JUDGE_RESPONSE_TOKENS,
                num_judge_calls // len(config.judge_models)
            )

        total_low = sum(response_costs.values()) + sum(judge_costs.values())
        total_high = total_low * 1.25  # 25% buffer

        return CostEstimate(
            response_generation=sum(response_costs.values()),
            judging=sum(judge_costs.values()),
            total_low=total_low,
            total_high=total_high,
            num_api_calls=...,
            breakdown_by_model={**response_costs, **judge_costs}
        )

    def _estimate_model_cost(self,
                              model: str,
                              input_tokens: int,
                              output_tokens: int,
                              num_calls: int) -> float:
        """Estimate cost for a specific model."""
        pricing = MODEL_PRICING.get(model, {"input": 5.0, "output": 15.0})
        input_cost = (input_tokens * num_calls / 1_000_000) * pricing["input"]
        output_cost = (output_tokens * num_calls / 1_000_000) * pricing["output"]
        return input_cost + output_cost
```

### 8.2 Time Estimation

```python
class TimeEstimator:
    """Estimate run time based on API latencies."""

    # Average latencies in seconds (from benchmarks)
    AVG_RESPONSE_LATENCY = {
        "google/gemini-3-pro": 3.0,
        "openai/gpt-5.2": 4.0,
        "anthropic/claude-opus-4.5": 5.0,
        "xai/grok-4.1": 4.5,
        "moonshot/kimi-k2": 3.5,
        "google/gemini-3-flash": 1.0,
        "openai/gpt-4.1": 1.5,
        "anthropic/claude-sonnet": 2.0,
    }

    AVG_JUDGE_LATENCY = 1.5  # Judges are faster (shorter output)

    def estimate_run_time(self,
                           config: EvalConfig,
                           parallelism: int = 10) -> TimeEstimate:
        """
        Estimate total run time.

        Accounts for:
        - Parallelism (concurrent API calls)
        - Rate limits
        - Overhead between calls
        """

        # Response generation time
        total_response_calls = config.num_prompts * len(config.model_pairs) * 2
        avg_response_latency = np.mean([
            self.AVG_RESPONSE_LATENCY.get(m, 3.0)
            for pair in config.model_pairs
            for m in [pair.gemini_model, pair.competitor_model]
        ])
        response_time_sequential = total_response_calls * avg_response_latency
        response_time_parallel = response_time_sequential / parallelism

        # Judging time
        total_judge_calls = (
            config.num_prompts *
            len(config.model_pairs) *
            config.num_judges *
            config.votes_per_judge *
            len(config.judge_personas)
        )
        judge_time_sequential = total_judge_calls * self.AVG_JUDGE_LATENCY
        judge_time_parallel = judge_time_sequential / parallelism

        # Rate limit constraints
        rate_limited_time = self._apply_rate_limits(
            total_response_calls + total_judge_calls,
            response_time_parallel + judge_time_parallel
        )

        return TimeEstimate(
            response_generation_time=timedelta(seconds=response_time_parallel),
            judging_time=timedelta(seconds=judge_time_parallel),
            total_with_rate_limits=timedelta(seconds=rate_limited_time),
            parallelism_used=parallelism,
        )
```

---

## 9. Reporting and Visualization

### 9.1 PDF Report Generation

```python
class PDFReportGenerator:
    """Generate comprehensive PDF evaluation report."""

    def generate(self,
                 db: Database,
                 run_id: str,
                 output_path: Path) -> Path:
        """
        Generate full PDF report with three sections:
        1. Executive Summary
        2. Comprehensive Dashboard
        3. Deep Statistical Analysis
        """

        # Gather all data
        analysis = self.analyzer.full_analysis(db, run_id)

        # Generate all charts
        charts = self._generate_charts(analysis)

        # Render HTML template
        html = self.template.render(
            run_info=analysis.run_info,
            executive_summary=self._generate_executive_summary(analysis),
            dashboard=self._generate_dashboard_section(analysis, charts),
            statistical_analysis=self._generate_stats_section(analysis),
            weakness_analysis=analysis.weaknesses,
            methodology=self._methodology_section(),
        )

        # Convert to PDF
        pdf_path = output_path / "report.pdf"
        weasyprint.HTML(string=html).write_pdf(pdf_path)

        return pdf_path

    def _generate_charts(self, analysis: FullAnalysis) -> dict[str, str]:
        """Generate all visualization charts."""
        charts = {}

        # Win rate by model pair
        charts["win_rates_bar"] = self._win_rates_bar_chart(analysis.win_rates)

        # Win rate by occupation heatmap
        charts["occupation_heatmap"] = self._occupation_heatmap(
            analysis.win_rates_by_occupation
        )

        # Win rate by writing category
        charts["category_radar"] = self._category_radar_chart(
            analysis.win_rates_by_category
        )

        # Confidence intervals forest plot
        charts["confidence_intervals"] = self._forest_plot(
            analysis.all_confidence_intervals
        )

        # Judge agreement matrix
        charts["judge_agreement"] = self._agreement_heatmap(
            analysis.judge_agreement_matrix
        )

        # Response length distributions
        charts["length_dist"] = self._length_distribution_plot(
            analysis.response_lengths
        )

        return charts
```

### 9.2 Chart Generation

```python
class ChartGenerator:
    """Generate plotly visualizations."""

    def win_rates_bar_chart(self,
                            win_rates: dict[str, WinRateResult]) -> str:
        """Generate bar chart of win rates by model pair."""

        models = list(win_rates.keys())
        rates = [wr.win_rate * 100 for wr in win_rates.values()]
        ci_low = [wr.confidence_interval[0] * 100 for wr in win_rates.values()]
        ci_high = [wr.confidence_interval[1] * 100 for wr in win_rates.values()]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=models,
            y=rates,
            error_y=dict(
                type='data',
                symmetric=False,
                array=[h - r for h, r in zip(ci_high, rates)],
                arrayminus=[r - l for r, l in zip(rates, ci_low)]
            ),
            marker_color=['green' if r > 50 else 'red' for r in rates]
        ))

        fig.add_hline(y=50, line_dash="dash", line_color="gray",
                      annotation_text="50% (no difference)")

        fig.update_layout(
            title="Gemini Win Rates vs Competitors",
            xaxis_title="Competitor Model",
            yaxis_title="Gemini Win Rate (%)",
            yaxis_range=[0, 100]
        )

        return self._fig_to_base64(fig)

    def occupation_heatmap(self,
                           win_rates: dict[str, dict[str, float]]) -> str:
        """Generate heatmap of win rates by occupation group."""

        occupations = sorted(set(
            occ for model_rates in win_rates.values()
            for occ in model_rates.keys()
        ))
        models = list(win_rates.keys())

        z = [[win_rates[model].get(occ, 0.5) * 100 for occ in occupations]
             for model in models]

        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=occupations,
            y=models,
            colorscale='RdYlGn',
            zmid=50,
            text=[[f"{v:.1f}%" for v in row] for row in z],
            texttemplate="%{text}",
            colorbar_title="Win Rate"
        ))

        fig.update_layout(
            title="Win Rates by Occupation Group",
            xaxis_title="Occupation Group (SOC Major)",
            yaxis_title="Competitor Model"
        )

        return self._fig_to_base64(fig)
```

---

## 10. CLI Interface

### 10.1 Command Structure

```python
@click.group()
@click.option('--config', type=click.Path(), help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """Gemini Writing Evaluation Framework CLI."""
    ctx.ensure_object(dict)
    if config:
        ctx.obj['config'] = load_config(config)

@cli.command()
@click.option('--preset', type=int, help='Preset level 1-10')
@click.option('--prompts', type=int, help='Number of prompts')
@click.option('--models', multiple=True, help='Models to evaluate')
@click.option('--judges', multiple=True, help='Judge models')
@click.option('--votes', type=int, default=5, help='Votes per judge')
@click.option('--occupations', help='Filter by SOC codes (comma-separated)')
@click.option('--industries', help='Filter by NAICS codes')
@click.option('--seed', type=int, help='Random seed for reproducibility')
@click.option('--dry-run', is_flag=True, help='Show estimate without running')
@click.pass_context
def run(ctx, preset, prompts, models, judges, votes, occupations,
        industries, seed, dry_run):
    """Run an evaluation."""

    config = build_config(ctx.obj.get('config'), preset, prompts, models,
                          judges, votes, occupations, industries, seed)

    # Show cost estimate
    estimator = CostEstimator()
    estimate = estimator.estimate_run_cost(config)
    display_estimate(estimate)

    if dry_run:
        return

    if not click.confirm('Proceed with evaluation?'):
        return

    # Run evaluation with TUI
    runner = EvalRunner(config)
    app = GeminiEvalApp(runner)
    app.run()

@cli.command()
@click.argument('run_path', type=click.Path(exists=True))
def resume(run_path):
    """Resume an interrupted evaluation."""
    checkpoint = CheckpointManager(Path(run_path)).resume()
    config = checkpoint.config

    runner = EvalRunner(config, checkpoint=checkpoint)
    app = GeminiEvalApp(runner)
    app.run()

@cli.command()
@click.argument('run_paths', nargs=-1, type=click.Path(exists=True))
def compare(run_paths):
    """Compare results across multiple runs."""
    results = [load_results(Path(p)) for p in run_paths]
    comparison = cross_run_comparison(results)
    display_comparison(comparison)

@cli.command()
@click.argument('run_path', type=click.Path(exists=True))
def view(run_path):
    """Open interactive results viewer."""
    db = Database(Path(run_path) / "results.db")
    viewer = ResultsViewerApp(db)
    viewer.run()

@cli.command()
@click.argument('run_path', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['pdf', 'csv', 'json']), default='pdf')
def export(run_path, format):
    """Export results in various formats."""
    db = Database(Path(run_path) / "results.db")

    if format == 'pdf':
        generator = PDFReportGenerator()
        output = generator.generate(db, run_path, Path(run_path) / "reports")
    elif format == 'csv':
        output = export_csv(db, Path(run_path) / "exports")
    elif format == 'json':
        output = export_json(db, Path(run_path) / "exports")

    click.echo(f"Exported to: {output}")
```

### 10.2 Preset Configurations

```python
PRESETS = {
    1: EvalConfig(
        name="Sanity Check",
        num_prompts=5,
        model_pairs=[ModelPair("gemini-3-pro", "gpt-5.2")],
        num_judges=1,
        votes_per_judge=1,
        judge_personas=["writing_expert"],
    ),
    2: EvalConfig(
        name="Smoke Test",
        num_prompts=20,
        model_pairs=[ModelPair("gemini-3-pro", "gpt-5.2")],
        num_judges=1,
        votes_per_judge=3,
        judge_personas=["writing_expert"],
    ),
    3: EvalConfig(
        name="Dev Iteration",
        num_prompts=50,
        model_pairs=[
            ModelPair("gemini-3-pro", "gpt-5.2"),
            ModelPair("gemini-3-pro", "claude-opus-4.5"),
        ],
        num_judges=2,
        votes_per_judge=3,
        judge_personas=["writing_expert", "target_recipient"],
    ),
    # ... presets 4-10
    10: EvalConfig(
        name="Full Kaboodle",
        num_prompts=10000,
        model_pairs=[
            ModelPair("gemini-3-pro", "gpt-5.2"),
            ModelPair("gemini-3-pro", "claude-opus-4.5"),
            ModelPair("gemini-3-pro", "grok-4.1"),
            ModelPair("gemini-3-pro", "kimi-k2"),
            ModelPair("gemini-3-flash", "gpt-4.1"),
            ModelPair("gemini-3-flash", "claude-sonnet"),
        ],
        num_judges=3,
        votes_per_judge=5,
        judge_personas=["writing_expert", "target_recipient"],
    ),
}
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/test_onet_extractor.py
class TestONetExtractor:
    def test_extract_writing_tasks(self, db_path):
        extractor = ONetExtractor(db_path)
        tasks = extractor.extract_writing_tasks(limit=100)

        assert len(tasks) == 100
        assert all(isinstance(t, ONetTask) for t in tasks)
        assert all(t.job_zone in range(1, 6) for t in tasks)

    def test_writing_category_classification(self):
        task = "Write project proposals and grant applications"
        category = classify_task(task)
        assert category == "explicit_writing"

    def test_stratified_sampling(self):
        # Ensure even distribution across dimensions
        ...

# tests/test_judging.py
class TestJudging:
    def test_position_bias_handling(self):
        handler = PositionBiasHandler(seed=42)

        # Same inputs should give same order
        order1 = handler.get_presentation_order("p1", "claude", 1)
        order2 = handler.get_presentation_order("p1", "claude", 1)
        assert order1 == order2

        # Different votes may have different orders
        orders = [handler.get_presentation_order("p1", "claude", i)
                  for i in range(100)]
        assert len(set(orders)) > 1  # Not all same

    def test_majority_aggregation(self):
        votes = ["A", "A", "B", "A", "B"]
        assert compute_majority(votes) == "A"

        votes = ["A", "B", "TIE", "B", "B"]
        assert compute_majority(votes) == "B"

# tests/test_checkpoint.py
class TestCheckpoint:
    def test_save_and_resume(self, tmp_path):
        manager = CheckpointManager(tmp_path)
        checkpoint = manager.initialize(EvalConfig(...), seed=42)

        checkpoint.completed_prompt_ids.add("p1")
        checkpoint.completed_prompt_ids.add("p2")
        manager.save()

        # Simulate restart
        new_manager = CheckpointManager(tmp_path)
        resumed = new_manager.resume()

        assert resumed.completed_prompt_ids == {"p1", "p2"}
        assert resumed.random_seed == 42
```

### 11.2 Integration Tests

```python
# tests/integration/test_full_pipeline.py
@pytest.mark.integration
class TestFullPipeline:
    """End-to-end integration tests with real API calls."""

    @pytest.fixture
    def api_client(self):
        return OpenRouterClient(os.environ["OPENROUTER_API_KEY"])

    async def test_mini_eval_run(self, api_client, tmp_path):
        """Run a minimal evaluation to test full pipeline."""
        config = PRESETS[1]  # Sanity check preset

        runner = EvalRunner(config, output_dir=tmp_path)
        results = await runner.run()

        assert results.total_prompts == 5
        assert len(results.comparisons) == 5
        assert all(c.final_winner in ["gemini", "competitor", "tie"]
                   for c in results.comparisons)

        # Check files created
        assert (tmp_path / "results.db").exists()
        assert (tmp_path / "checkpoint.json").exists()
        assert (tmp_path / "config.json").exists()
```

---

## 12. Deployment and Operations

### 12.1 Environment Configuration

```bash
# .env file
OPENROUTER_API_KEY=sk-or-...
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=120
CHECKPOINT_INTERVAL=10
```

### 12.2 Directory Structure for Runs

```
results/
├── eval_2026-01-08_14-30-00/
│   ├── config.json
│   ├── config_summary.txt
│   ├── checkpoint.json
│   ├── random_seed.txt
│   ├── prompts/
│   │   ├── prompts.json
│   │   ├── prompts_by_occupation/
│   │   └── prompts_by_industry/
│   ├── responses/
│   │   ├── by_prompt/
│   │   └── by_model/
│   ├── judgments/
│   │   ├── raw/
│   │   └── aggregated/
│   ├── results.db
│   ├── results_summary.csv
│   ├── analysis/
│   │   ├── win_rates.json
│   │   ├── confidence_intervals.json
│   │   ├── statistical_tests.json
│   │   └── weakness_analysis.json
│   ├── reports/
│   │   ├── report.pdf
│   │   ├── executive_summary.md
│   │   └── charts/
│   ├── logs/
│   │   ├── run.log
│   │   ├── failures.log
│   │   └── timing.log
│   └── README.md
└── latest -> eval_2026-01-08_14-30-00/
```

---

## 13. Open Questions and Risks

### 13.1 Technical Risks

1. **API Rate Limits**: OpenRouter may have varying rate limits per model. Need adaptive rate limiting that learns from 429 responses.

2. **Model Availability**: Models may be temporarily unavailable. Need fallback handling and partial run completion.

3. **Cost Overruns**: Token usage may exceed estimates. Implement hard budget caps with automatic pause.

4. **Judge Model Bias**: Using Gemini as a judge while evaluating Gemini creates potential bias. Mitigation: heavily weight non-Gemini judges, track and report any Gemini-judge vs other-judge disagreements.

### 13.2 Methodological Considerations

1. **Prompt Generation Bias**: Using the evaluated models to generate prompts may inadvertently favor them. Mitigation: use ensemble of models for generation, track which model generated each prompt.

2. **O*NET Coverage**: Not all O*NET tasks involve written communication. Some tasks may be forced into writing contexts unnaturally. Mitigation: careful filtering, manual review of sample prompts.

3. **Temporal Sensitivity**: Results may vary with model updates. Record exact model versions and timestamps.

### 13.3 Implementation Priorities

**Phase 1 (MVP)**:
- Core data pipeline (O*NET extraction, basic prompts)
- Single-model pair evaluation
- Basic TUI progress display
- SQLite storage
- Checkpoint/resume

**Phase 2**:
- Full prompt enrichment pipeline
- Multi-model pair support
- Complete TUI with viewer
- PDF reporting

**Phase 3**:
- Advanced statistical analysis
- Bias detection
- Weakness identification
- Cross-run comparison

---

## 14. Success Criteria

1. **Correctness**: All prompts are realistic, diverse, and properly grounded in O*NET data.

2. **Robustness**: System handles all failure modes gracefully with full recoverability.

3. **Trustworthiness**: Statistical methodology is sound with proper confidence intervals and significance testing.

4. **Usability**: Clear TUI, informative progress, actionable reports.

5. **Reproducibility**: Any run can be exactly reproduced with the saved seed and config.

6. **Actionability**: Reports clearly identify Gemini's specific weaknesses with examples and statistical backing.
