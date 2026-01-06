# Gemini Writing Evaluation Framework - Draft Plan 1

## Executive Summary

This plan details a comprehensive evaluation framework to compare Gemini 3.0 Pro and Flash against competing frontier models on realistic professional writing tasks. The evaluation leverages O*NET occupational data for ~20,000+ writing tasks, uses OpenRouter API for unified model access, employs triple-judge ensemble methodology with best-of-5 voting, and delivers results through an interactive TUI and comprehensive PDF report.

## 1. Architecture Overview

### 1.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     GEMINI WRITING EVAL                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │  Data Pipeline   │───▶│  Prompt Engine   │             │
│  │  (O*NET + NAICS) │    │  (Generation)    │             │
│  └──────────────────┘    └──────────────────┘             │
│           │                       │                         │
│           ▼                       ▼                         │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │  SQLite Storage  │◀──▶│  Eval Executor   │             │
│  │  (Results DB)    │    │  (OpenRouter)    │             │
│  └──────────────────┘    └──────────────────┘             │
│           │                       │                         │
│           ▼                       ▼                         │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │  Judge System    │───▶│  Analysis Engine │             │
│  │  (Multi-Judge)   │    │  (Stats + Viz)   │             │
│  └──────────────────┘    └──────────────────┘             │
│           │                       │                         │
│           └───────────┬───────────┘                         │
│                       ▼                                     │
│              ┌──────────────────┐                          │
│              │   TUI Viewer +   │                          │
│              │   PDF Reporter   │                          │
│              └──────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

- **Language**: Python 3.11+
- **Async HTTP**: httpx with asyncio for concurrent API calls
- **Data Validation**: pydantic v2 for type-safe data models
- **Database**: SQLite with aiosqlite for async operations
- **CLI/TUI**: rich + textual for interactive terminal UI
- **Visualization**: plotly for interactive charts, matplotlib for PDF report charts
- **PDF Generation**: reportlab or weasyprint for final analyst report
- **API Gateway**: OpenRouter unified API for all LLM models
- **Configuration**: TOML/YAML for configs, python-dotenv for secrets
- **Testing**: pytest with pytest-asyncio

### 1.3 Project Structure

```
gemini-writing-eval/
├── README.md
├── pyproject.toml                 # Poetry/uv project config
├── .env.example                   # Environment variables template
├── config/
│   ├── models.yaml                # Model configurations
│   ├── judge_prompts.yaml         # Judge system prompts
│   └── eval_config.yaml           # Evaluation parameters
├── src/
│   ├── data/
│   │   ├── onet_downloader.py     # O*NET data fetching
│   │   ├── naics_mapper.py        # NAICS industry mapping
│   │   └── task_extractor.py      # Extract writing tasks
│   ├── prompts/
│   │   ├── generator.py           # LLM-based prompt generation
│   │   ├── combinator.py          # Algorithmic combinations
│   │   ├── enricher.py            # Context enrichment
│   │   └── templates.py           # Prompt templates
│   ├── evaluation/
│   │   ├── executor.py            # Run evaluations
│   │   ├── models.py              # OpenRouter API clients
│   │   └── checkpoint.py          # Pause/resume support
│   ├── judging/
│   │   ├── judge_engine.py        # Multi-judge orchestration
│   │   ├── personas.py            # Expert vs Recipient judges
│   │   ├── voting.py              # Best-of-5 + aggregation
│   │   └── rubric.py              # Evaluation criteria
│   ├── storage/
│   │   ├── schema.py              # SQLite schema
│   │   ├── database.py            # Database operations
│   │   └── exports.py             # CSV export functionality
│   ├── analysis/
│   │   ├── statistics.py          # Win rates, confidence intervals
│   │   ├── visualizations.py      # Charts and heatmaps
│   │   └── weaknesses.py          # Identify specific failure modes
│   ├── ui/
│   │   ├── tui_app.py             # Textual TUI application
│   │   ├── components/            # TUI widgets
│   │   └── filters.py             # Filtering logic
│   ├── reporting/
│   │   ├── pdf_generator.py       # Final PDF report
│   │   ├── dashboard.py           # Comprehensive metrics
│   │   └── executive_summary.py   # High-level findings
│   └── utils/
│       ├── logging.py             # Structured logging
│       └── randomness.py          # Deterministic shuffling
├── scripts/
│   ├── download_onet.sh           # O*NET data download
│   ├── setup_db.py                # Initialize database
│   └── run_eval.py                # Main evaluation CLI
└── tests/
    ├── test_prompts.py
    ├── test_judging.py
    └── test_integration.py
```

## 2. Data Pipeline: O*NET + NAICS

### 2.1 O*NET Data Acquisition

**Objective**: Download and parse the latest O*NET database to extract ~20,000+ individual task statements across ~1,000 occupations.

**Implementation**:

```python
# src/data/onet_downloader.py

import httpx
import zipfile
from pathlib import Path
import pandas as pd

class ONetDownloader:
    """Download and extract O*NET database."""

    BASE_URL = "https://www.onetcenter.org/dl_files/database/db_28_0_text/"
    VERSION = "28.0"  # Update as needed

    async def download_database(self, output_dir: Path) -> None:
        """Download latest O*NET database ZIP."""
        url = f"{self.BASE_URL}db_{self.VERSION}_text.zip"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()

            zip_path = output_dir / "onet_db.zip"
            zip_path.write_bytes(response.content)

            # Extract
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(output_dir)

    def load_tasks(self, data_dir: Path) -> pd.DataFrame:
        """Load Task Statements table."""
        # Task statements are in 'Task Statements.txt'
        tasks_df = pd.read_csv(
            data_dir / "Task Statements.txt",
            sep="\t",
            encoding="utf-8"
        )
        return tasks_df

    def load_occupations(self, data_dir: Path) -> pd.DataFrame:
        """Load Occupation Data table."""
        occ_df = pd.read_csv(
            data_dir / "Occupation Data.txt",
            sep="\t",
            encoding="utf-8"
        )
        return occ_df
```

**Key Tables**:
- `Task Statements.txt`: Individual task statements per occupation
- `Occupation Data.txt`: Occupation names, codes, descriptions
- `Task Categories.txt`: Optional categorization metadata

### 2.2 Writing Task Extraction

**Objective**: Filter O*NET tasks to identify only those involving writing/communication.

**Strategy**: Use keyword matching + LLM verification to ensure tasks are writing-related.

```python
# src/data/task_extractor.py

class WritingTaskExtractor:
    """Extract writing-related tasks from O*NET data."""

    WRITING_KEYWORDS = [
        "write", "draft", "compose", "document", "prepare",
        "correspondence", "report", "email", "memo", "letter",
        "communication", "message", "proposal", "brief",
        "article", "content", "copy", "text", "description"
    ]

    def filter_writing_tasks(self, tasks_df: pd.DataFrame) -> pd.DataFrame:
        """Filter tasks containing writing keywords."""
        pattern = "|".join(self.WRITING_KEYWORDS)
        writing_tasks = tasks_df[
            tasks_df["Task"].str.contains(pattern, case=False, na=False)
        ]
        return writing_tasks

    async def verify_with_llm(
        self,
        tasks: list[str],
        llm_client: LLMClient
    ) -> list[bool]:
        """Use LLM to verify tasks are actually writing-related."""
        prompt = """
        Classify whether each task involves professional writing or written communication.
        Return only "yes" or "no" for each task.

        Tasks:
        {tasks}
        """
        # Batch verification logic
        ...
```

**Expected Output**: ~5,000-10,000 writing-related tasks across diverse occupations.

### 2.3 NAICS Industry Mapping

**Objective**: Map each occupation to multiple NAICS industry codes for systematic industry diversity.

**NAICS Structure**: 2-6 digit hierarchical codes (e.g., 72 = Accommodation and Food Services, 7224 = Drinking Places)

```python
# src/data/naics_mapper.py

class NAICSMapper:
    """Map occupations to NAICS industry codes."""

    def load_naics_codes(self) -> dict:
        """Load official NAICS 2022 codes from Census Bureau."""
        # Download from: https://www.census.gov/naics/
        # Parse NAICS structure
        return {
            "11": "Agriculture, Forestry, Fishing and Hunting",
            "21": "Mining, Quarrying, and Oil and Gas Extraction",
            "22": "Utilities",
            "23": "Construction",
            # ... all 20 2-digit sectors
        }

    def sample_industries_for_occupation(
        self,
        occupation_code: str,
        n_samples: int = 5
    ) -> list[dict]:
        """Sample diverse NAICS codes for an occupation."""
        # Strategy: Sample evenly across 2-digit sectors
        # Then drill down to 4-6 digit codes for specificity
        ...
```

**Sampling Strategy**:
- For each occupation, sample 5-10 NAICS codes
- Ensure even distribution across major sectors (20 2-digit NAICS codes)
- Use stratified sampling to avoid over-representation of any sector

## 3. Prompt Generation System

### 3.1 Three-Phase Generation Approach

**Phase 1: Offline LLM Generation** (Preprocessing)
- Generate diverse persona/context variations for each O*NET task
- Use all models being evaluated to avoid bias
- Store in database for reuse

**Phase 2: Algorithmic Combinations**
- Programmatically combine tasks with randomized dimensions
- Deterministic and reproducible
- Fast and scalable

**Phase 3: LLM Enrichment**
- Add realistic details to complex prompts
- Inject industry-specific context
- Ensure authenticity

### 3.2 Persona Generation (Phase 1)

```python
# src/prompts/generator.py

class PersonaGenerator:
    """Generate diverse writer personas for tasks."""

    GENERATIONS = ["Gen Z", "Millennial", "Gen X", "Boomer"]
    SKILL_LEVELS = ["entry-level", "mid-career", "senior", "executive"]

    async def generate_personas(
        self,
        task: str,
        occupation: str,
        industry_naics: str,
        llm_clients: list[LLMClient]
    ) -> list[dict]:
        """Generate persona variations using multiple LLMs."""

        prompt_template = """
        Generate a realistic writer persona for this task:

        Task: {task}
        Occupation: {occupation}
        Industry: {industry}

        Create a persona with:
        - Name and age
        - Experience level
        - Writing skill level
        - Communication style (formal to casual)
        - Key background details

        Make it realistic and diverse.
        """

        # Call each LLM to generate personas
        personas = []
        for llm in llm_clients:
            persona = await llm.generate(prompt_template.format(...))
            personas.append(persona)

        return personas
```

### 3.3 Recipient/Consumer Generation

```python
class RecipientGenerator:
    """Generate target recipient personas for each writing task."""

    async def generate_recipient(
        self,
        task: str,
        writer_persona: dict,
        context: dict
    ) -> dict:
        """Generate the intended recipient/consumer of the writing."""

        prompt = """
        Given this writing task and writer:

        Task: {task}
        Writer: {writer_persona}
        Context: {context}

        Who is the intended recipient/consumer of this writing?
        Provide:
        - Role/position
        - Relationship to writer
        - What they need from this communication
        - Their likely communication preferences
        """
        # Generate recipient persona
        ...
```

### 3.4 Algorithmic Combination (Phase 2)

```python
# src/prompts/combinator.py

class PromptCombinator:
    """Algorithmically combine elements into full prompts."""

    def combine_elements(
        self,
        onet_task: dict,
        persona: dict,
        industry: dict,
        formality_level: str,
        random_seed: int
    ) -> dict:
        """Deterministically combine elements."""

        rng = Random(random_seed)  # Deterministic

        # Select formality level
        formality = rng.choice(["very casual", "casual", "neutral", "formal", "very formal"])

        # Build prompt
        prompt = {
            "task_id": onet_task["id"],
            "occupation": onet_task["occupation"],
            "task_description": onet_task["task"],
            "writer_persona": persona,
            "industry": industry,
            "formality": formality,
            "recipient": ...,  # Generated separately
            "random_seed": random_seed
        }

        return prompt
```

### 3.5 Context Enrichment (Phase 3)

```python
# src/prompts/enricher.py

class PromptEnricher:
    """Add realistic details to complex prompts."""

    async def enrich_prompt(
        self,
        base_prompt: dict,
        llm_client: LLMClient
    ) -> dict:
        """Add industry-specific context and realistic details."""

        enrichment_prompt = """
        Enhance this writing task with realistic details:

        Task: {task}
        Writer: {persona}
        Industry: {industry}
        Recipient: {recipient}

        Add:
        - Specific context/situation
        - Relevant constraints or requirements
        - Background information
        - Any industry-specific details

        Keep it concise but realistic.
        """

        enriched = await llm_client.generate(enrichment_prompt.format(...))
        return {**base_prompt, "enriched_context": enriched}
```

### 3.6 Final Prompt Assembly

```python
class PromptAssembler:
    """Assemble final evaluation prompts."""

    def assemble_eval_prompt(self, enriched_prompt: dict) -> str:
        """Create the final prompt sent to models."""

        template = """
You are {persona_name}, a {persona_level} {occupation} at {company} in the {industry} industry.

Task: {task_description}

Context: {enriched_context}

Recipient: {recipient_description}

Communication Style: {formality}

Please complete this writing task. Use your judgment about appropriate length and format.
"""

        return template.format(**enriched_prompt)
```

### 3.7 Scale Configuration

```python
# config/eval_config.yaml

prompt_generation:
  full_eval:
    num_prompts: 1000
    estimated_cost: 2000  # USD

  quick_sample:
    num_prompts: 100
    sample_method: "stratified"  # Even distribution

  micro_targeted:
    enabled: true
    filters:
      - occupation_codes: ["11-1011.00"]  # CEOs
      - task_keywords: ["executive", "strategic"]
      - industries: ["tech", "finance"]

diversity_targets:
  generations: ["Gen Z", "Millennial", "Gen X", "Boomer"]
  formality_levels: ["very casual", "casual", "neutral", "formal", "very formal"]
  skill_levels: ["entry", "mid", "senior", "executive"]
  industry_sectors: 20  # All NAICS 2-digit sectors
```

## 4. Model Evaluation System

### 4.1 OpenRouter Integration

```python
# src/evaluation/models.py

class OpenRouterClient:
    """Unified API client for all LLM models."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=300.0  # 5 min timeout
        )

    async def generate(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> dict:
        """Generate completion from any model."""

        response = await self.client.post(
            f"{self.BASE_URL}/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        )
        response.raise_for_status()
        return response.json()
```

### 4.2 Model Configuration

```yaml
# config/models.yaml

models:
  pro_tier:
    gemini:
      id: "google/gemini-3.0-pro"
      tier: "pro"
      params:
        temperature: 1.0
        max_tokens: 8192

    competitors:
      - id: "openai/gpt-5.2-thinking"
        tier: "pro"
      - id: "anthropic/claude-opus-4.5"
        tier: "pro"
      - id: "x-ai/grok-4.1-thinking"
        tier: "pro"
      - id: "moonshot/kimi-k2-thinking"
        tier: "pro"

  flash_tier:
    gemini:
      id: "google/gemini-3.0-flash"
      tier: "flash"

    competitors:
      - id: "openai/gpt-4.1"
        tier: "flash"
      - id: "anthropic/claude-sonnet-4.5"
        tier: "flash"

judge_models:
  - id: "anthropic/claude-opus-4.5"
    name: "claude"
  - id: "openai/gpt-5.2"
    name: "gpt"
  - id: "google/gemini-3.0-pro"
    name: "gemini"
```

### 4.3 Evaluation Executor

```python
# src/evaluation/executor.py

class EvaluationExecutor:
    """Execute pairwise model comparisons."""

    async def run_comparison(
        self,
        prompt: dict,
        model_a: str,
        model_b: str
    ) -> dict:
        """Run pairwise comparison."""

        # Generate responses from both models
        tasks = [
            self.client.generate(model_a, prompt["assembled_prompt"]),
            self.client.generate(model_b, prompt["assembled_prompt"])
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle failures
        result = {
            "prompt_id": prompt["id"],
            "model_a": model_a,
            "model_b": model_b,
            "response_a": responses[0] if not isinstance(responses[0], Exception) else None,
            "response_b": responses[1] if not isinstance(responses[1], Exception) else None,
            "failure_a": isinstance(responses[0], Exception),
            "failure_b": isinstance(responses[1], Exception)
        }

        return result
```

### 4.4 Failure Handling

```python
class FailureHandler:
    """Handle model failures and refusals."""

    def check_failure(self, response: dict) -> tuple[bool, str]:
        """Determine if response is a failure."""

        if response is None:
            return True, "api_error"

        content = response.get("content", "")

        # Detect refusals
        refusal_patterns = [
            "I cannot", "I'm unable", "I can't assist",
            "inappropriate", "against my guidelines"
        ]
        if any(p in content.lower() for p in refusal_patterns):
            return True, "refusal"

        # Detect off-topic
        if len(content.strip()) < 50:
            return True, "too_short"

        return False, "success"

    def apply_auto_loss(self, result: dict) -> dict:
        """Apply auto-loss for failures."""

        if result["failure_a"] and not result["failure_b"]:
            result["auto_winner"] = "model_b"
        elif result["failure_b"] and not result["failure_a"]:
            result["auto_winner"] = "model_a"
        elif result["failure_a"] and result["failure_b"]:
            result["auto_winner"] = "tie"  # Both failed

        return result
```

## 5. Judge System Architecture

### 5.1 Dual Judge Personas

**Implementation of two distinct judge types:**

```python
# src/judging/personas.py

class JudgePersona(ABC):
    """Base class for judge personas."""

    @abstractmethod
    async def evaluate(
        self,
        prompt_context: dict,
        response_a: str,
        response_b: str
    ) -> dict:
        """Evaluate two responses."""
        pass

class WritingExpertJudge(JudgePersona):
    """Simulated writing professional evaluating craft quality."""

    SYSTEM_PROMPT = """
You are an expert writing professional with 20+ years of experience across diverse industries and communication contexts.

Evaluate the quality of writing based on:
- Craft quality (grammar, style, word choice)
- Clarity and coherence
- Structure and organization
- Appropriate length for the task
- Tone appropriateness
- Professional polish
- Authenticity (does it sound like real human writing vs AI-generated?)

Given the specific context of the task, which response demonstrates superior writing quality?
"""

    async def evaluate(
        self,
        prompt_context: dict,
        response_a: str,
        response_b: str
    ) -> dict:
        """Evaluate from writing expert perspective."""

        evaluation_prompt = f"""
Context:
Task: {prompt_context['task_description']}
Writer Persona: {prompt_context['writer_persona']}
Industry: {prompt_context['industry']}
Recipient: {prompt_context['recipient']}
Formality Level: {prompt_context['formality']}

Response A:
{response_a}

Response B:
{response_b}

Which response demonstrates better writing quality? Respond with:
- "A" if Response A is better
- "B" if Response B is better
- "Tie" if they are roughly equal

Provide brief reasoning (2-3 sentences).
"""

        # LLM call logic
        ...

class TargetRecipientJudge(JudgePersona):
    """Simulated target recipient evaluating effectiveness."""

    SYSTEM_PROMPT = """
You are simulating the intended recipient/consumer of this writing.

Evaluate the effectiveness from the recipient's perspective:
- Does it meet my needs?
- Is it appropriate for our relationship/context?
- Is the tone right for this situation?
- Is it actionable/useful?
- Does it feel authentic vs formulaic/AI-generated?
- Would I trust this communication?

Which response would be more effective if you received it?
"""

    async def evaluate(
        self,
        prompt_context: dict,
        response_a: str,
        response_b: str
    ) -> dict:
        """Evaluate from recipient perspective."""

        evaluation_prompt = f"""
You are: {prompt_context['recipient']['description']}
Relationship to writer: {prompt_context['recipient']['relationship']}

You received this communication from {prompt_context['writer_persona']['name']} regarding:
{prompt_context['task_description']}

Response A:
{response_a}

Response B:
{response_b}

As the recipient, which response would be more effective and appropriate for you?

Respond with "A", "B", or "Tie" and brief reasoning.
"""

        # LLM call logic
        ...
```

### 5.2 Multi-Judge Ensemble

```python
# src/judging/judge_engine.py

class JudgeEnsemble:
    """Ensemble of multiple judge models."""

    def __init__(self, judge_models: list[str]):
        """
        Args:
            judge_models: List of model IDs (Claude Opus, GPT-5.2, Gemini Pro)
        """
        self.judge_models = judge_models
        self.client = OpenRouterClient(api_key=os.getenv("OPENROUTER_API_KEY"))

    async def judge_comparison(
        self,
        prompt_context: dict,
        response_a: str,
        response_b: str,
        judge_persona: JudgePersona,
        shuffle_seed: int
    ) -> dict:
        """Run judgment across all judge models."""

        # Deterministic shuffling to eliminate position bias
        rng = Random(shuffle_seed)
        order = ["A", "B"] if rng.random() > 0.5 else ["B", "A"]

        # Present in shuffled order
        first_response = response_a if order[0] == "A" else response_b
        second_response = response_b if order[0] == "A" else response_a

        # Collect judgments from all three judge models
        judgments = []
        for judge_model in self.judge_models:
            judgment = await self._run_single_judgment(
                judge_model=judge_model,
                judge_persona=judge_persona,
                prompt_context=prompt_context,
                first_response=first_response,
                second_response=second_response,
                original_order=order
            )
            judgments.append(judgment)

        return {
            "judge_persona": judge_persona.__class__.__name__,
            "shuffle_seed": shuffle_seed,
            "shuffle_order": order,
            "judgments": judgments
        }
```

### 5.3 Best-of-5 Voting Logic

```python
# src/judging/voting.py

class VotingSystem:
    """Best-of-5 voting with majority-of-majorities aggregation."""

    async def run_best_of_5(
        self,
        judge_model: str,
        judge_persona: JudgePersona,
        prompt_context: dict,
        response_a: str,
        response_b: str,
        base_seed: int
    ) -> dict:
        """Run 5 independent judgments and take majority."""

        votes = []
        for i in range(5):
            # Each judgment uses different random seed for shuffling
            seed = base_seed + i

            vote = await self.judge_engine.judge_comparison(
                prompt_context=prompt_context,
                response_a=response_a,
                response_b=response_b,
                judge_persona=judge_persona,
                shuffle_seed=seed
            )

            votes.append(vote["winner"])  # "A", "B", or "Tie"

        # Count votes
        vote_counts = Counter(votes)
        majority_winner = vote_counts.most_common(1)[0][0]

        return {
            "judge_model": judge_model,
            "judge_persona": judge_persona.__class__.__name__,
            "votes": votes,
            "vote_counts": dict(vote_counts),
            "majority_winner": majority_winner
        }

    def aggregate_majority_of_majorities(
        self,
        judge_results: list[dict]
    ) -> str:
        """Aggregate across three judge models' majority winners."""

        # Extract majority winner from each judge model
        majority_winners = [r["majority_winner"] for r in judge_results]

        # Count which winner appears most
        winner_counts = Counter(majority_winners)
        final_winner = winner_counts.most_common(1)[0][0]

        return final_winner
```

### 5.4 Comprehensive Evaluation Rubric

```python
# src/judging/rubric.py

class EvaluationRubric:
    """Comprehensive rubric for writing evaluation."""

    CRITERIA = {
        "writing_quality": {
            "description": "Grammar, syntax, word choice, style",
            "weight": 1.0
        },
        "appropriate_length": {
            "description": "Is the response the right length for the task?",
            "weight": 1.0
        },
        "tone_appropriateness": {
            "description": "Does the tone match the context and formality level?",
            "weight": 1.0
        },
        "clarity": {
            "description": "Is the message clear and easy to understand?",
            "weight": 1.0
        },
        "task_completion": {
            "description": "Does it fully address the requested task?",
            "weight": 1.0
        },
        "effectiveness": {
            "description": "Would this achieve the intended purpose?",
            "weight": 1.0
        },
        "authenticity": {
            "description": "Does it sound like genuine human writing vs AI-generated?",
            "weight": 1.5  # Higher weight per requirements
        },
        "structure": {
            "description": "Logical organization and flow",
            "weight": 1.0
        }
    }

    def format_rubric_for_prompt(self) -> str:
        """Format rubric for inclusion in judge prompts."""

        rubric_text = "Evaluation Criteria:\n"
        for criterion, details in self.CRITERIA.items():
            rubric_text += f"- {criterion}: {details['description']}\n"

        return rubric_text
```

### 5.5 Position Bias Detection

```python
# src/judging/bias_detection.py

class PositionBiasDetector:
    """Detect and measure position bias in judgments."""

    def analyze_position_bias(self, judgments_df: pd.DataFrame) -> dict:
        """Analyze if judges prefer first/second position."""

        # For each judgment, check if winner was in first or second position
        position_analysis = {
            "first_position_wins": 0,
            "second_position_wins": 0,
            "ties": 0
        }

        for _, judgment in judgments_df.iterrows():
            if judgment["winner"] == judgment["shuffle_order"][0]:
                position_analysis["first_position_wins"] += 1
            elif judgment["winner"] == judgment["shuffle_order"][1]:
                position_analysis["second_position_wins"] += 1
            else:
                position_analysis["ties"] += 1

        # Statistical test for bias
        from scipy.stats import binomial_test

        total_wins = (
            position_analysis["first_position_wins"] +
            position_analysis["second_position_wins"]
        )

        p_value = binomial_test(
            position_analysis["first_position_wins"],
            n=total_wins,
            p=0.5,
            alternative="two-sided"
        )

        return {
            **position_analysis,
            "bias_p_value": p_value,
            "significant_bias": p_value < 0.05
        }
```

## 6. Data Storage and Results Management

### 6.1 SQLite Schema Design

```sql
-- src/storage/schema.sql

-- Prompts table
CREATE TABLE prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onet_task_id TEXT NOT NULL,
    occupation_code TEXT NOT NULL,
    occupation_name TEXT NOT NULL,
    task_description TEXT NOT NULL,
    industry_naics TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    writer_persona JSON NOT NULL,
    recipient_persona JSON NOT NULL,
    formality_level TEXT NOT NULL,
    enriched_context TEXT,
    assembled_prompt TEXT NOT NULL,
    generation_seed INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model responses table
CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    model_tier TEXT NOT NULL,  -- 'pro' or 'flash'
    response_text TEXT,
    failure BOOLEAN DEFAULT FALSE,
    failure_type TEXT,  -- 'api_error', 'refusal', 'too_short', etc.
    latency_ms INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- Comparisons table
CREATE TABLE comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    model_a_id TEXT NOT NULL,
    model_b_id TEXT NOT NULL,
    response_a_id INTEGER NOT NULL,
    response_b_id INTEGER NOT NULL,
    comparison_type TEXT NOT NULL,  -- 'gemini_pro_vs_X', 'gemini_flash_vs_X'
    auto_winner TEXT,  -- Set if one model failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id),
    FOREIGN KEY (response_a_id) REFERENCES responses(id),
    FOREIGN KEY (response_b_id) REFERENCES responses(id)
);

-- Judgments table (stores all individual votes)
CREATE TABLE judgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    judge_model TEXT NOT NULL,  -- 'claude-opus-4.5', 'gpt-5.2', 'gemini-3-pro'
    judge_persona TEXT NOT NULL,  -- 'WritingExpert' or 'TargetRecipient'
    vote_round INTEGER NOT NULL,  -- 1-5 for best-of-5
    shuffle_seed INTEGER NOT NULL,
    shuffle_order TEXT NOT NULL,  -- JSON: ["A", "B"] or ["B", "A"]
    winner TEXT NOT NULL,  -- 'A', 'B', or 'Tie'
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(id)
);

-- Aggregated results table
CREATE TABLE aggregated_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    judge_persona TEXT NOT NULL,

    -- Best-of-5 results per judge model
    claude_votes JSON NOT NULL,
    claude_majority TEXT NOT NULL,
    gpt_votes JSON NOT NULL,
    gpt_majority TEXT NOT NULL,
    gemini_votes JSON NOT NULL,
    gemini_majority TEXT NOT NULL,

    -- Final majority-of-majorities
    final_winner TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(id)
);

-- Inter-judge agreement metrics
CREATE TABLE agreement_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER NOT NULL,
    judge_persona TEXT NOT NULL,
    kappa_claude_gpt FLOAT,
    kappa_claude_gemini FLOAT,
    kappa_gpt_gemini FLOAT,
    full_agreement BOOLEAN,
    partial_agreement BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(id)
);

-- Checkpoints table for pause/resume
CREATE TABLE checkpoints (
    run_id TEXT PRIMARY KEY,
    completed_prompts JSON NOT NULL,
    config JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_prompts_occupation ON prompts(occupation_code);
CREATE INDEX idx_prompts_industry ON prompts(industry_naics);
CREATE INDEX idx_responses_model ON responses(model_id);
CREATE INDEX idx_comparisons_type ON comparisons(comparison_type);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
```

### 6.2 CSV Export Functionality

```python
# src/storage/exports.py

class CSVExporter:
    """Export evaluation results to CSV for external analysis."""

    def __init__(self, db: EvalDatabase):
        self.db = db

    async def export_full_results(self, output_path: Path):
        """Export complete results with all metadata."""

        query = """
            SELECT
                p.occupation_name,
                p.occupation_code,
                p.task_description,
                p.industry_name,
                p.formality_level,
                c.model_a_id,
                c.model_b_id,
                c.comparison_type,
                ar.final_winner,
                ar.claude_majority,
                ar.gpt_majority,
                ar.gemini_majority,
                am.kappa_claude_gpt,
                am.full_agreement
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.id
            JOIN aggregated_results ar ON c.id = ar.comparison_id
            LEFT JOIN agreement_metrics am ON c.id = am.comparison_id
        """

        df = await self.db.query_to_dataframe(query)
        df.to_csv(output_path, index=False)
```

## 7. Statistical Analysis and Visualization

### 7.1 Win Rate Calculations

```python
# src/analysis/statistics.py

import pandas as pd
import numpy as np
from scipy import stats

class StatisticalAnalyzer:
    """Comprehensive statistical analysis of evaluation results."""

    def calculate_win_rates(
        self,
        comparisons_df: pd.DataFrame,
        model_a: str,
        model_b: str
    ) -> dict:
        """Calculate win rates with confidence intervals."""

        pair_df = comparisons_df[
            (comparisons_df["model_a_id"] == model_a) &
            (comparisons_df["model_b_id"] == model_b)
        ]

        total = len(pair_df)
        wins_a = len(pair_df[pair_df["final_winner"] == "A"])
        wins_b = len(pair_df[pair_df["final_winner"] == "B"])
        ties = len(pair_df[pair_df["final_winner"] == "Tie"])

        win_rate_a = wins_a / total if total > 0 else 0
        win_rate_b = wins_b / total if total > 0 else 0

        # 95% confidence intervals (Wilson score)
        ci_a = self._wilson_score_interval(wins_a, total)
        ci_b = self._wilson_score_interval(wins_b, total)

        return {
            "model_a": model_a,
            "model_b": model_b,
            "total_comparisons": total,
            "wins_a": wins_a,
            "wins_b": wins_b,
            "ties": ties,
            "win_rate_a": win_rate_a,
            "win_rate_b": win_rate_b,
            "ci_95_a": ci_a,
            "ci_95_b": ci_b
        }
```

### 7.2 Interactive Visualizations

```python
# src/analysis/visualizations.py

import plotly.graph_objects as go
import plotly.express as px

class VisualizationEngine:
    """Generate interactive charts and heatmaps."""

    def create_win_rate_chart(self, win_rates: list[dict]) -> go.Figure:
        """Bar chart with error bars showing confidence intervals."""

        fig = go.Figure()

        for wr in win_rates:
            fig.add_trace(go.Bar(
                name=wr["model_pair"],
                x=[wr["model_a"], wr["model_b"]],
                y=[wr["win_rate_a"], wr["win_rate_b"]],
                error_y=dict(
                    type='data',
                    array=[
                        wr["ci_95_a"][1] - wr["win_rate_a"],
                        wr["ci_95_b"][1] - wr["win_rate_b"]
                    ],
                    arrayminus=[
                        wr["win_rate_a"] - wr["ci_95_a"][0],
                        wr["win_rate_b"] - wr["ci_95_b"][0]
                    ]
                )
            ))

        fig.update_layout(
            title="Model Win Rates by Comparison",
            xaxis_title="Model",
            yaxis_title="Win Rate",
            barmode='group'
        )

        return fig

    def create_occupation_heatmap(
        self,
        results_df: pd.DataFrame
    ) -> go.Figure:
        """Heatmap showing win rates across occupations."""

        pivot = results_df.pivot_table(
            values='win_rate',
            index='occupation_name',
            columns='model_pair',
            aggfunc='mean'
        )

        fig = px.imshow(
            pivot,
            labels=dict(x="Model Pair", y="Occupation", color="Win Rate"),
            title="Win Rates by Occupation",
            color_continuous_scale="RdYlGn"
        )

        return fig
```

### 7.3 Weakness Identification

```python
# src/analysis/weaknesses.py

class WeaknessAnalyzer:
    """Identify specific areas where Gemini underperforms."""

    def analyze_weaknesses(
        self,
        comparisons_df: pd.DataFrame,
        model_name: str = "gemini-3.0-pro"
    ) -> dict:
        """Find where Gemini loses most often."""

        gemini_comps = comparisons_df[
            comparisons_df["model_a_id"].str.contains("gemini") |
            comparisons_df["model_b_id"].str.contains("gemini")
        ]

        # Determine if Gemini won or lost each comparison
        gemini_comps["gemini_won"] = gemini_comps.apply(
            lambda row: (
                (row["model_a_id"].startswith("gemini") and row["final_winner"] == "A") or
                (row["model_b_id"].startswith("gemini") and row["final_winner"] == "B")
            ),
            axis=1
        )

        # Analyze by dimension
        by_occupation = gemini_comps.groupby("occupation_name")["gemini_won"].agg(["mean", "count"])
        by_formality = gemini_comps.groupby("formality_level")["gemini_won"].agg(["mean", "count"])
        by_industry = gemini_comps.groupby("industry_name")["gemini_won"].agg(["mean", "count"])

        # Find worst performing segments
        weakest_occupations = by_occupation.sort_values("mean").head(10)
        weakest_formality = by_formality.sort_values("mean")
        weakest_industries = by_industry.sort_values("mean").head(10)

        return {
            "weakest_occupations": weakest_occupations.to_dict(),
            "weakest_formality_levels": weakest_formality.to_dict(),
            "weakest_industries": weakest_industries.to_dict()
        }
```

## 8. Interactive TUI Viewer

### 8.1 Textual Application Design

```python
# src/ui/tui_app.py

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Container, Horizontal, Vertical

class EvalViewerApp(App):
    """Interactive TUI for exploring evaluation results."""

    CSS = """
    DataTable {
        height: 60%;
    }
    #detail-pane {
        height: 40%;
        border: solid green;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("s", "sort", "Sort"),
        ("d", "detail", "View Detail")
    ]

    def compose(self) -> ComposeResult:
        """Create UI layout."""
        yield Header()
        yield DataTable(id="results-table")
        yield Container(
            Static(id="detail-pane"),
            id="details"
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load data on startup."""
        table = self.query_one(DataTable)

        # Set up columns
        table.add_columns(
            "Occupation",
            "Task",
            "Industry",
            "Model A",
            "Model B",
            "Winner",
            "Expert Judge",
            "Recipient Judge"
        )

        # Load results from database
        results = await self.load_results()
        for row in results:
            table.add_row(*row)

    async def load_results(self) -> list:
        """Query database for results."""
        # Database query logic
        ...

    def action_filter(self) -> None:
        """Open filter dialog."""
        # Implement filtering UI
        ...

    def action_detail(self) -> None:
        """Show detailed view of selected comparison."""
        table = self.query_one(DataTable)
        row_key = table.cursor_row
        # Show full responses, all judge votes, reasoning, etc.
        ...
```

### 8.2 Filtering and Sorting

```python
# src/ui/filters.py

class FilterEngine:
    """Apply filters to evaluation results."""

    def apply_filters(
        self,
        results_df: pd.DataFrame,
        filters: dict
    ) -> pd.DataFrame:
        """Apply user-specified filters."""

        filtered = results_df.copy()

        if occupation := filters.get("occupation"):
            filtered = filtered[filtered["occupation_code"] == occupation]

        if industry := filters.get("industry"):
            filtered = filtered[filtered["industry_naics"].str.startswith(industry)]

        if winner := filters.get("winner"):
            filtered = filtered[filtered["final_winner"] == winner]

        if formality := filters.get("formality"):
            filtered = filtered[filtered["formality_level"] == formality]

        return filtered
```

## 9. PDF Report Generation

### 9.1 Three-Part Report Structure

```python
# src/reporting/pdf_generator.py

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet

class PDFReportGenerator:
    """Generate comprehensive PDF analyst report."""

    def generate_full_report(
        self,
        results: dict,
        output_path: Path
    ):
        """Create three-part report: Dashboard + Analysis + Executive Summary."""

        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Part 1: Executive Summary
        story.extend(self._create_executive_summary(results, styles))

        # Part 2: Comprehensive Dashboard
        story.extend(self._create_dashboard(results, styles))

        # Part 3: Deep Statistical Analysis
        story.extend(self._create_statistical_analysis(results, styles))

        doc.build(story)

    def _create_executive_summary(
        self,
        results: dict,
        styles
    ) -> list:
        """High-level findings and recommendations."""

        elements = []

        elements.append(Paragraph("Executive Summary", styles['Heading1']))
        elements.append(Spacer(1, 12))

        # Key findings
        elements.append(Paragraph("Key Findings:", styles['Heading2']))

        for finding in results["key_findings"]:
            elements.append(Paragraph(f"• {finding}", styles['Normal']))

        elements.append(Spacer(1, 12))

        # Top weaknesses
        elements.append(Paragraph("Top Weaknesses:", styles['Heading2']))

        for weakness in results["top_weaknesses"]:
            elements.append(Paragraph(
                f"• {weakness['category']}: {weakness['description']}",
                styles['Normal']
            ))

        return elements

    def _create_dashboard(self, results: dict, styles) -> list:
        """Comprehensive metrics and visualizations."""

        elements = []

        elements.append(Paragraph("Comprehensive Dashboard", styles['Heading1']))

        # Overall win rates
        win_rate_table = self._create_win_rate_table(results["win_rates"])
        elements.append(win_rate_table)

        # Charts (saved as images)
        for chart_path in results["chart_paths"]:
            elements.append(Image(str(chart_path), width=500, height=300))

        return elements

    def _create_statistical_analysis(self, results: dict, styles) -> list:
        """Deep statistical rigor section."""

        elements = []

        elements.append(Paragraph("Statistical Analysis", styles['Heading1']))

        # Significance tests
        elements.append(Paragraph("Significance Testing:", styles['Heading2']))

        for test_result in results["significance_tests"]:
            elements.append(Paragraph(
                f"• {test_result['comparison']}: p={test_result['p_value']:.4f}, "
                f"effect size={test_result['effect_size']:.2f} ({test_result['interpretation']})",
                styles['Normal']
            ))

        # Inter-rater reliability
        elements.append(Paragraph("Inter-Judge Reliability:", styles['Heading2']))
        elements.append(Paragraph(
            f"Average Cohen's Kappa: {results['average_kappa']:.3f}",
            styles['Normal']
        ))

        return elements
```

## 10. Orchestration and CLI

### 10.1 Main Evaluation Script

```python
# scripts/run_eval.py

import asyncio
import click
from pathlib import Path

@click.group()
def cli():
    """Gemini Writing Evaluation Framework"""
    pass

@cli.command()
@click.option("--num-prompts", default=1000, help="Number of prompts to generate")
@click.option("--mode", type=click.Choice(["full", "quick", "micro"]), default="full")
async def generate_prompts(num_prompts: int, mode: str):
    """Generate evaluation prompts from O*NET data."""

    # Initialize components
    downloader = ONetDownloader()
    extractor = WritingTaskExtractor()
    generator = PromptGenerator()

    # Download O*NET
    await downloader.download_database(Path("data/onet"))

    # Extract writing tasks
    tasks = extractor.extract_writing_tasks(Path("data/onet"))

    # Generate prompts
    prompts = await generator.generate_prompts(tasks, num_prompts, mode)

    click.echo(f"Generated {len(prompts)} prompts")

@cli.command()
@click.option("--model-pair", required=True, help="e.g., gemini-3.0-pro:gpt-5.2")
@click.option("--resume", default=None, help="Resume from checkpoint run ID")
async def run_evaluation(model_pair: str, resume: str):
    """Execute pairwise model evaluation."""

    model_a, model_b = model_pair.split(":")

    executor = EvaluationExecutor()

    if resume:
        state = await executor.resume_from_checkpoint(resume)
    else:
        state = None

    await executor.run_comparisons(model_a, model_b, state)

@cli.command()
async def run_judging():
    """Execute judge voting on completed comparisons."""

    judge_system = JudgeEnsemble()
    await judge_system.judge_all_comparisons()

@cli.command()
def launch_tui():
    """Launch interactive TUI viewer."""

    app = EvalViewerApp()
    app.run()

@cli.command()
@click.option("--output", default="report.pdf", help="Output PDF path")
def generate_report(output: str):
    """Generate final PDF analyst report."""

    reporter = PDFReportGenerator()
    reporter.generate_full_report(Path(output))

if __name__ == "__main__":
    cli()
```

## 11. Implementation Roadmap

### Phase 1: Data Foundation (Week 1)
- Download and process O*NET database
- Extract writing tasks
- Integrate NAICS codes
- Set up SQLite schema

### Phase 2: Prompt Generation (Week 2)
- Implement three-phase generation pipeline
- Generate persona/recipient variations
- Test prompt diversity and quality
- Create 100-prompt test set

### Phase 3: Evaluation Infrastructure (Week 3)
- OpenRouter integration
- Model response collection
- Failure handling
- Checkpoint system

### Phase 4: Judge System (Week 4)
- Implement dual judge personas
- Build multi-judge ensemble
- Best-of-5 voting logic
- Position bias detection

### Phase 5: Analysis and Reporting (Week 5)
- Statistical analysis engine
- Visualization generation
- Weakness identification
- PDF report creation

### Phase 6: TUI and Polish (Week 6)
- Build interactive TUI
- Filtering and sorting
- CSV export
- End-to-end testing

### Phase 7: Full Evaluation Run (Week 7-8)
- Generate 1000+ prompts
- Run all model comparisons
- Complete judging
- Generate final report

## 12. Cost Estimation

### API Costs (OpenRouter)

**Full Evaluation (1000 prompts):**

- Model responses: 1000 prompts × 8 models × $0.10/response = $800
- Judge votes: 1000 comparisons × 3 judges × 2 personas × 5 votes × $0.05/vote = $1500
- Prompt generation: $200

**Total: ~$2500**

**Quick Sample (100 prompts):** ~$250

## 13. Robustness Measures Summary

1. Pairwise comparisons only
2. Best-of-5 voting per judge model
3. Majority-of-majorities aggregation across 3 judge models
4. Dual judge personas (Expert + Recipient)
5. Deterministic shuffling to eliminate position bias
6. Position bias detection and statistical testing
7. Inter-judge agreement metrics (Cohen's Kappa)
8. Confidence intervals on all win rates
9. Statistical significance testing
10. Auto-loss for model failures

## 14. Open Questions and Risks

### Questions
1. Should we include temperature variation in model comparisons?
2. How to handle edge cases where all models fail?
3. What threshold for "significant" weakness identification?

### Risks
1. **API rate limits**: Implement exponential backoff and retry logic
2. **Cost overruns**: Start with 100-prompt pilot before full run
3. **Judge bias**: Monitor inter-judge agreement; if low, investigate prompts
4. **Prompt quality**: Manual review of sample prompts before full generation
5. **Data quality**: Validate O*NET tasks are truly writing-related

## Conclusion

This plan provides a comprehensive, implementable framework for evaluating Gemini writing capabilities against frontier competitors. The system is designed for statistical robustness, meaningful inspection, and actionable insights into specific weaknesses.

