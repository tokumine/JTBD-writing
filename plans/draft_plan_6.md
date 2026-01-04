# Gemini Writing Evaluation Framework: Master Implementation Plan

## Executive Summary

This document provides a comprehensive implementation plan for evaluating Gemini 3.0 Pro and 3.0 Flash against competing frontier models (GPT-5.2, Claude Opus, X/Grok, Kimi, etc.) on realistic writing tasks derived from the complete spectrum of US economy occupations. The framework uses O*NET occupational data, pairwise comparisons with dual-judge personas, and rigorous statistical methodology to identify Gemini's specific strengths and weaknesses.

---

## 1. O*NET Data Pipeline

### 1.1 Data Acquisition

O*NET (Occupational Information Network) provides the most comprehensive database of US occupations and their associated tasks. We'll download the complete database programmatically.

**Download Script (`scripts/download_onet.py`):**

```python
#!/usr/bin/env python3
"""
O*NET Database Downloader
Downloads and extracts the latest O*NET database files.
"""

import requests
import zipfile
import os
from pathlib import Path

ONET_BASE_URL = "https://www.onetcenter.org/dl_files/database"
ONET_VERSION = "29_1"  # Update to latest version
OUTPUT_DIR = Path("data/onet_raw")

FILES_TO_DOWNLOAD = [
    f"db_{ONET_VERSION}_text.zip",  # Main database tables
]

def download_onet():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename in FILES_TO_DOWNLOAD:
        url = f"{ONET_BASE_URL}/{filename}"
        output_path = OUTPUT_DIR / filename

        print(f"Downloading {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract ZIP
        print(f"Extracting {filename}...")
        with zipfile.ZipFile(output_path, 'r') as zip_ref:
            zip_ref.extractall(OUTPUT_DIR / "extracted")

    print("O*NET download complete!")

if __name__ == "__main__":
    download_onet()
```

### 1.2 Key O*NET Tables for Writing Tasks

The following tables are essential for identifying writing-related occupations and tasks:

| Table | Purpose |
|-------|---------|
| `Occupation Data.txt` | All ~1,000 occupations with codes and titles |
| `Task Statements.txt` | Specific tasks performed in each occupation |
| `Work Activities.txt` | Generalized work activities (includes "Communicating" categories) |
| `Skills.txt` | Skills required (includes "Writing" skill ratings) |
| `Knowledge.txt` | Knowledge areas (English Language, Communications) |
| `Task Ratings.txt` | Importance/frequency ratings for tasks |

### 1.3 Writing Task Extraction Pipeline

**Extraction Script (`scripts/extract_writing_tasks.py`):**

```python
#!/usr/bin/env python3
"""
Extracts writing-intensive occupations and tasks from O*NET data.
"""

import pandas as pd
import sqlite3
from pathlib import Path

ONET_DIR = Path("data/onet_raw/extracted")
DB_PATH = Path("data/eval.db")

# Keywords indicating writing tasks
WRITING_KEYWORDS = [
    'write', 'draft', 'compose', 'author', 'document', 'prepare report',
    'correspondence', 'memo', 'email', 'proposal', 'brief', 'summary',
    'record', 'communicate in writing', 'written communication',
    'technical writing', 'creative writing', 'editing', 'proofread',
    'grant application', 'business plan', 'press release', 'newsletter',
    'policy document', 'procedure', 'manual', 'specification'
]

def load_onet_table(name: str) -> pd.DataFrame:
    """Load an O*NET table from text file."""
    path = ONET_DIR / f"{name}.txt"
    return pd.read_csv(path, sep='\t', encoding='utf-8')

def extract_writing_occupations():
    """Identify occupations with significant writing requirements."""

    # Load skills data and filter for Writing skill
    skills = load_onet_table("Skills")
    writing_skills = skills[
        (skills['Element Name'] == 'Writing') &
        (skills['Data Value'] >= 3.5)  # Importance >= 3.5 out of 5
    ]['O*NET-SOC Code'].unique()

    # Load work activities and filter for written communication
    activities = load_onet_table("Work Activities")
    writing_activities = activities[
        activities['Element Name'].str.contains('Written|Documenting', case=False, na=False)
    ]['O*NET-SOC Code'].unique()

    # Combine occupation codes
    writing_occ_codes = set(writing_skills) | set(writing_activities)

    # Load occupation data
    occupations = load_onet_table("Occupation Data")
    writing_occupations = occupations[
        occupations['O*NET-SOC Code'].isin(writing_occ_codes)
    ]

    return writing_occupations

def extract_writing_tasks():
    """Extract specific writing-related tasks from task statements."""

    tasks = load_onet_table("Task Statements")

    # Filter tasks containing writing keywords
    pattern = '|'.join(WRITING_KEYWORDS)
    writing_tasks = tasks[
        tasks['Task'].str.contains(pattern, case=False, na=False)
    ]

    # Join with task ratings to get importance scores
    ratings = load_onet_table("Task Ratings")
    importance_ratings = ratings[ratings['Scale ID'] == 'IM']  # Importance scale

    writing_tasks = writing_tasks.merge(
        importance_ratings[['O*NET-SOC Code', 'Task ID', 'Data Value']],
        on=['O*NET-SOC Code', 'Task ID'],
        how='left'
    )
    writing_tasks.rename(columns={'Data Value': 'Importance'}, inplace=True)

    return writing_tasks

def save_to_database(occupations: pd.DataFrame, tasks: pd.DataFrame):
    """Save extracted data to SQLite database."""

    conn = sqlite3.connect(DB_PATH)

    occupations.to_sql('onet_occupations', conn, if_exists='replace', index=False)
    tasks.to_sql('onet_writing_tasks', conn, if_exists='replace', index=False)

    conn.close()
    print(f"Saved {len(occupations)} occupations and {len(tasks)} writing tasks to {DB_PATH}")

if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    occupations = extract_writing_occupations()
    tasks = extract_writing_tasks()
    save_to_database(occupations, tasks)
```

### 1.4 Expected Output

After running the extraction pipeline, we expect:
- **~400-600 occupations** with significant writing requirements
- **~2,000-4,000 specific writing tasks** across these occupations
- Coverage of all major occupational categories (Management, Healthcare, Legal, Technical, Creative, etc.)

---

## 2. Eval Prompt Generation

### 2.1 Task-to-Prompt Transformation Methodology

Each O*NET writing task must be transformed into a realistic, evaluable prompt. The transformation follows a structured pipeline:

```
O*NET Task -> Industry Contextualization -> Prompt Template Selection -> Final Prompt
```

### 2.2 Industry Diversification

For each occupation, we generate prompts across multiple industry contexts to ensure diversity:

**Industry Context Generator (`scripts/generate_industry_contexts.py`):**

```python
INDUSTRY_CONTEXTS = {
    "Chief Executives": [
        {"industry": "technology_startup", "company": "AI productivity tool startup", "size": "50 employees"},
        {"industry": "manufacturing", "company": "automotive parts manufacturer", "size": "2,000 employees"},
        {"industry": "nonprofit", "company": "environmental conservation nonprofit", "size": "30 employees"},
        {"industry": "healthcare", "company": "regional hospital network", "size": "5,000 employees"},
        {"industry": "retail", "company": "organic grocery chain", "size": "500 employees"},
    ],
    "Software Developers": [
        {"industry": "fintech", "company": "payment processing platform"},
        {"industry": "healthcare", "company": "electronic health records system"},
        {"industry": "gaming", "company": "mobile game studio"},
        {"industry": "enterprise", "company": "CRM software vendor"},
        {"industry": "government", "company": "federal agency contractor"},
    ],
    # ... similar mappings for all occupations
}

def generate_industry_variants(occupation: str, task: str, n_variants: int = 5) -> list:
    """Generate industry-specific variants of a writing task."""

    contexts = INDUSTRY_CONTEXTS.get(occupation, generate_default_contexts(occupation))

    variants = []
    for ctx in contexts[:n_variants]:
        variants.append({
            "occupation": occupation,
            "task": task,
            "industry": ctx["industry"],
            "company_context": ctx.get("company", ""),
            "additional_context": ctx.get("size", "")
        })

    return variants
```

### 2.3 Prompt Template Library

Different writing tasks require different prompt structures:

**Template Categories:**

```python
PROMPT_TEMPLATES = {
    "email_communication": """
You are a {occupation} at {company_context} ({industry} industry).

Task: {task_description}

Write a professional email to {recipient} regarding {topic}.

Additional context:
{additional_context}

Requirements:
- Appropriate tone for the recipient and situation
- Clear and actionable message
- Professional formatting
""",

    "report_writing": """
You are a {occupation} working in the {industry} sector.

Task: {task_description}

Write a {report_type} report addressing the following:
{report_requirements}

The report should be suitable for {audience}.

Background information:
{background_context}
""",

    "proposal_drafting": """
You are a {occupation} at {company_context}.

Task: {task_description}

Draft a proposal for {proposal_subject}.

Key points to address:
{key_points}

The proposal will be reviewed by {decision_makers}.
""",

    "documentation": """
You are a {occupation} responsible for {responsibility_area}.

Task: {task_description}

Create documentation for {documentation_subject}.

Target audience: {target_audience}
Technical level: {technical_level}

Include:
{required_sections}
""",

    "creative_brief": """
You are a {occupation} in the {industry} industry.

Task: {task_description}

Write {deliverable_type} for {purpose}.

Brand voice: {brand_voice}
Target audience: {target_audience}
Key messages: {key_messages}
"""
}
```

### 2.4 Prompt Complexity Tiers

Prompts are categorized by complexity to ensure a balanced evaluation:

| Tier | Description | Context Required | Example |
|------|-------------|------------------|---------|
| **Simple** | Straightforward writing task | Minimal | "Write a thank-you email to a client" |
| **Standard** | Task with moderate context | Some background | "Write a project status update for stakeholders, given the project timeline and current blockers" |
| **Complex** | Multi-faceted task with rich context | Substantial | "Draft a board presentation on Q3 performance with attached financial data and strategic recommendations" |

**Distribution Target:** 30% Simple, 50% Standard, 20% Complex

---

## 3. Context Generation

### 3.1 Synthetic Context Generation

For prompts requiring additional context, we use a combination of:

1. **Templated synthetic data** (names, dates, figures)
2. **LLM-generated realistic scenarios**
3. **Curated real-world examples** (anonymized)

**Context Generator (`scripts/generate_context.py`):**

```python
import random
from faker import Faker

fake = Faker()

class ContextGenerator:
    """Generates realistic context for writing prompts."""

    def generate_company_context(self, industry: str) -> dict:
        """Generate fictional but realistic company details."""
        return {
            "company_name": fake.company(),
            "founding_year": random.randint(1980, 2020),
            "employee_count": random.choice([50, 200, 500, 2000, 10000]),
            "revenue_range": random.choice(["$1-10M", "$10-50M", "$50-200M", "$200M-1B", "$1B+"]),
            "headquarters": fake.city(),
            "industry": industry
        }

    def generate_project_context(self) -> dict:
        """Generate project details for status reports."""
        return {
            "project_name": f"{fake.word().capitalize()} {random.choice(['Initiative', 'Project', 'Program'])}",
            "start_date": fake.date_between(start_date='-6m', end_date='-1m'),
            "target_completion": fake.date_between(start_date='+1m', end_date='+6m'),
            "budget": f"${random.randint(50, 500) * 1000:,}",
            "team_size": random.randint(3, 20),
            "status": random.choice(["On Track", "At Risk", "Behind Schedule"]),
            "blockers": self._generate_blockers(),
            "milestones": self._generate_milestones()
        }

    def generate_financial_context(self) -> dict:
        """Generate financial data for reports."""
        base_revenue = random.randint(1, 100) * 1000000
        return {
            "revenue_q1": base_revenue * random.uniform(0.9, 1.1),
            "revenue_q2": base_revenue * random.uniform(0.95, 1.15),
            "revenue_q3": base_revenue * random.uniform(0.85, 1.2),
            "yoy_growth": f"{random.uniform(-5, 25):.1f}%",
            "gross_margin": f"{random.uniform(30, 70):.1f}%",
            "operating_expenses": base_revenue * random.uniform(0.6, 0.9),
            "headcount_change": random.randint(-20, 50)
        }

    def generate_recipient_context(self, role: str) -> dict:
        """Generate recipient details for communication tasks."""
        return {
            "name": fake.name(),
            "title": role,
            "relationship": random.choice(["new contact", "long-term partner", "internal colleague"]),
            "communication_style": random.choice(["formal", "professional", "casual-professional"]),
            "key_concerns": self._generate_concerns(role)
        }

    def _generate_blockers(self) -> list:
        blockers = [
            "Waiting on vendor API documentation",
            "Key team member on medical leave",
            "Budget approval pending",
            "Third-party integration delays",
            "Scope changes from stakeholders",
            "Technical debt requiring refactoring",
            "Resource constraints",
            "Regulatory compliance review"
        ]
        return random.sample(blockers, random.randint(0, 3))

    def _generate_milestones(self) -> list:
        milestones = [
            {"name": "Requirements Complete", "status": "Done"},
            {"name": "Design Review", "status": "Done"},
            {"name": "Development Phase 1", "status": random.choice(["Done", "In Progress"])},
            {"name": "Development Phase 2", "status": random.choice(["In Progress", "Not Started"])},
            {"name": "QA Testing", "status": "Not Started"},
            {"name": "UAT", "status": "Not Started"},
            {"name": "Production Deployment", "status": "Not Started"}
        ]
        return milestones

    def _generate_concerns(self, role: str) -> list:
        concern_map = {
            "CEO": ["strategic alignment", "ROI", "competitive positioning"],
            "CFO": ["budget impact", "cost efficiency", "financial risk"],
            "CTO": ["technical feasibility", "scalability", "security"],
            "Manager": ["timeline", "resource allocation", "team impact"],
            "Client": ["value delivery", "timeline", "communication"],
        }
        return concern_map.get(role, ["quality", "timeline", "communication"])
```

### 3.2 Context Data Files

For complex scenarios, we provide pre-generated context files:

**Directory Structure:**
```
data/
  contexts/
    financial_reports/
      q3_2024_sample.json
      budget_variance.json
    project_data/
      software_project.json
      construction_project.json
    customer_scenarios/
      complaint_resolution.json
      partnership_proposal.json
    legal_documents/
      contract_summary.json
      compliance_brief.json
```

---

## 4. Model Integration

### 4.1 OpenRouter API Configuration

**OpenRouter Client (`src/model_client.py`):**

```python
import os
import asyncio
import aiohttp
from dataclasses import dataclass
from typing import Optional
import backoff

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

@dataclass
class ModelConfig:
    """Configuration for a model accessible via OpenRouter."""
    model_id: str
    display_name: str
    max_tokens: int = 4096
    temperature: float = 0.7

# Model registry with OpenRouter model IDs
MODELS = {
    "gemini-3-pro": ModelConfig(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro"
    ),
    "gemini-3-flash": ModelConfig(
        model_id="google/gemini-3.0-flash",
        display_name="Gemini 3.0 Flash"
    ),
    "gpt-5.2": ModelConfig(
        model_id="openai/gpt-5.2",
        display_name="GPT-5.2"
    ),
    "claude-opus": ModelConfig(
        model_id="anthropic/claude-opus-4",
        display_name="Claude Opus 4"
    ),
    "grok-3": ModelConfig(
        model_id="x-ai/grok-3",
        display_name="Grok 3"
    ),
    "kimi-k2": ModelConfig(
        model_id="moonshot/kimi-k2",
        display_name="Kimi K2"
    ),
    "deepseek-v3": ModelConfig(
        model_id="deepseek/deepseek-v3",
        display_name="DeepSeek V3"
    ),
}

class OpenRouterClient:
    """Async client for OpenRouter API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable required")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gemini-writing-eval.internal",
            "X-Title": "Gemini Writing Evaluation"
        }

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3
    )
    async def generate(
        self,
        model_key: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> dict:
        """Generate a completion from the specified model."""

        config = MODELS[model_key]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": config.model_id,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": temperature or config.temperature
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_API_URL,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                response.raise_for_status()
                result = await response.json()

                return {
                    "model": model_key,
                    "content": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {}),
                    "finish_reason": result["choices"][0].get("finish_reason")
                }

    async def generate_batch(
        self,
        model_key: str,
        prompts: list[str],
        system_prompt: Optional[str] = None,
        concurrency: int = 5
    ) -> list[dict]:
        """Generate completions for multiple prompts with concurrency control."""

        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_generate(prompt):
            async with semaphore:
                return await self.generate(model_key, prompt, system_prompt)

        tasks = [bounded_generate(p) for p in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### 4.2 Response Collection

**Batch Generation Script (`scripts/collect_responses.py`):**

```python
async def collect_model_responses(eval_prompts: list[dict], models: list[str]) -> list[dict]:
    """Collect responses from all models for all prompts."""

    client = OpenRouterClient()
    results = []

    for prompt_data in eval_prompts:
        prompt_id = prompt_data["prompt_id"]
        prompt_text = prompt_data["full_prompt"]

        for model in models:
            try:
                response = await client.generate(model, prompt_text)
                results.append({
                    "prompt_id": prompt_id,
                    "model": model,
                    "response": response["content"],
                    "usage": response["usage"],
                    "collected_at": datetime.utcnow().isoformat()
                })
            except Exception as e:
                results.append({
                    "prompt_id": prompt_id,
                    "model": model,
                    "response": None,
                    "error": str(e),
                    "collected_at": datetime.utcnow().isoformat()
                })

    return results
```

---

## 5. Judging Framework

### 5.1 Dual Judge Persona System

Each comparison is evaluated by two distinct judge personas:

#### Judge 1: Writing Expert Persona

```python
WRITING_EXPERT_SYSTEM_PROMPT = """You are a senior writing expert with 20+ years of experience in professional communication, technical writing, and editorial work. You have worked as an editor at major publications and as a writing consultant for Fortune 500 companies.

Your expertise includes:
- Clarity and readability assessment
- Structural organization and flow
- Grammar, syntax, and mechanics
- Tone and register appropriateness
- Persuasiveness and rhetorical effectiveness
- Conciseness and information density

You evaluate writing based on craft, not personal preference. You recognize that excellent writing serves its purpose effectively while maintaining high standards of clarity and professionalism.

IMPORTANT: You must evaluate the writing samples fairly without any bias based on their presentation order. Focus solely on the quality of the writing itself."""
```

#### Judge 2: Target Recipient Persona

The recipient persona is dynamically generated based on the task:

```python
def generate_recipient_persona(task_context: dict) -> str:
    """Generate a recipient persona prompt based on task context."""

    base_template = """You are simulating the perspective of a {recipient_role} who is the intended recipient of the writing being evaluated.

Your background:
- Role: {recipient_role}
- Industry: {industry}
- Key responsibilities: {responsibilities}
- Communication preferences: {preferences}

When evaluating writing, consider:
- Would this writing achieve its intended purpose with you as the recipient?
- Is the tone appropriate for your role and relationship with the writer?
- Is the information presented in a way that's useful and actionable for you?
- Does it respect your time by being appropriately concise?
- Would you take the desired action after reading this?

IMPORTANT: Evaluate based on effectiveness for the recipient, not general writing quality. A technically imperfect piece that achieves its goal is better than a polished piece that fails to connect."""

    return base_template.format(**task_context)

# Example recipient contexts
RECIPIENT_CONTEXTS = {
    "board_presentation": {
        "recipient_role": "Board Member",
        "industry": "varies by context",
        "responsibilities": "fiduciary oversight, strategic guidance, executive evaluation",
        "preferences": "concise executive summaries, data-driven insights, clear recommendations"
    },
    "client_email": {
        "recipient_role": "Client/Customer",
        "industry": "varies by context",
        "responsibilities": "business decision-making, vendor management",
        "preferences": "professional but personable, clear next steps, timely responses"
    },
    "technical_documentation": {
        "recipient_role": "Software Developer",
        "industry": "technology",
        "responsibilities": "implementation, maintenance, troubleshooting",
        "preferences": "precise technical details, code examples, searchable structure"
    }
}
```

### 5.2 Evaluation Rubric

**Comprehensive Writing Evaluation Rubric:**

```python
EVALUATION_RUBRIC = """
## Writing Evaluation Rubric

Evaluate each response on the following criteria. For each criterion, consider which response is better (A, B, or Tie).

### 1. CLARITY (Weight: 25%)
- Is the main message immediately apparent?
- Are ideas expressed precisely without ambiguity?
- Is the language accessible to the target audience?
- Are complex concepts explained effectively?

### 2. STRUCTURE & ORGANIZATION (Weight: 20%)
- Is there a logical flow from beginning to end?
- Are paragraphs well-organized with clear transitions?
- Is information presented in an order that aids comprehension?
- Are headings/sections used appropriately (if applicable)?

### 3. TONE & REGISTER (Weight: 20%)
- Is the tone appropriate for the audience and context?
- Does it strike the right balance of formality?
- Is the voice consistent throughout?
- Does it reflect appropriate empathy/authority as needed?

### 4. EFFECTIVENESS & PURPOSE (Weight: 20%)
- Does the writing achieve its stated purpose?
- Would the recipient take the intended action?
- Is it persuasive where persuasion is needed?
- Does it provide value to the reader?

### 5. CONCISENESS & COMPLETENESS (Weight: 15%)
- Is the length appropriate for the task?
- Is every sentence purposeful?
- Is necessary information included without excess?
- Are there unnecessary repetitions or digressions?

## Response Format

Provide your evaluation in the following JSON format:
{
  "criterion_scores": {
    "clarity": {"winner": "A|B|Tie", "reasoning": "..."},
    "structure": {"winner": "A|B|Tie", "reasoning": "..."},
    "tone": {"winner": "A|B|Tie", "reasoning": "..."},
    "effectiveness": {"winner": "A|B|Tie", "reasoning": "..."},
    "conciseness": {"winner": "A|B|Tie", "reasoning": "..."}
  },
  "overall_winner": "A|B|Tie",
  "overall_reasoning": "Brief summary of why the overall winner was chosen",
  "confidence": "high|medium|low"
}
"""
```

### 5.3 Position Shuffling Implementation

To eliminate position bias, we shuffle which response appears as A vs B:

```python
import random
import hashlib

def create_shuffled_comparison(
    prompt_id: str,
    response_a: dict,
    response_b: dict,
    judgment_index: int  # 0-4 for best of 5
) -> dict:
    """Create a comparison with deterministic position shuffling."""

    # Create deterministic seed from prompt_id and judgment_index
    seed_string = f"{prompt_id}_{judgment_index}"
    seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Shuffle positions
    if rng.random() < 0.5:
        position_a, position_b = "A", "B"
        displayed_a, displayed_b = response_a, response_b
    else:
        position_a, position_b = "B", "A"
        displayed_a, displayed_b = response_b, response_a

    return {
        "prompt_id": prompt_id,
        "judgment_index": judgment_index,
        "displayed_response_a": displayed_a["content"],
        "displayed_response_b": displayed_b["content"],
        "actual_model_in_position_a": displayed_a["model"],
        "actual_model_in_position_b": displayed_b["model"],
        "original_position_mapping": {
            response_a["model"]: position_a,
            response_b["model"]: position_b
        }
    }
```

### 5.4 Best of 5 Judgment Aggregation

```python
from collections import Counter
from typing import Literal

def aggregate_judgments(
    judgments: list[dict],
    model_a: str,
    model_b: str
) -> dict:
    """Aggregate 5 judgments into a final verdict using majority vote."""

    # Map displayed winners back to actual models
    model_wins = Counter()

    for j in judgments:
        displayed_winner = j["overall_winner"]
        position_mapping = j["position_mapping"]

        if displayed_winner == "Tie":
            model_wins["Tie"] += 1
        elif displayed_winner == "A":
            actual_winner = position_mapping["A"]
            model_wins[actual_winner] += 1
        else:  # "B"
            actual_winner = position_mapping["B"]
            model_wins[actual_winner] += 1

    # Determine majority winner
    total_judgments = len(judgments)

    if model_wins[model_a] > total_judgments / 2:
        final_winner = model_a
    elif model_wins[model_b] > total_judgments / 2:
        final_winner = model_b
    else:
        final_winner = "Tie"

    return {
        "model_a": model_a,
        "model_b": model_b,
        "model_a_wins": model_wins[model_a],
        "model_b_wins": model_wins[model_b],
        "ties": model_wins["Tie"],
        "final_winner": final_winner,
        "agreement_rate": max(model_wins.values()) / total_judgments,
        "judgments": judgments
    }
```

### 5.5 Complete Judging Pipeline

```python
async def run_judging_pipeline(
    comparison: dict,
    client: OpenRouterClient,
    judge_model: str = "claude-opus"
) -> dict:
    """Run the complete judging pipeline for one comparison."""

    prompt_data = comparison["prompt_data"]
    response_a = comparison["response_a"]
    response_b = comparison["response_b"]

    # Generate judge personas
    expert_system = WRITING_EXPERT_SYSTEM_PROMPT
    recipient_context = get_recipient_context(prompt_data)
    recipient_system = generate_recipient_persona(recipient_context)

    all_judgments = []

    # Best of 5 judgments
    for judge_idx in range(5):
        # Create shuffled comparison
        shuffled = create_shuffled_comparison(
            comparison["comparison_id"],
            response_a,
            response_b,
            judge_idx
        )

        # Alternate between expert and recipient judges
        if judge_idx % 2 == 0:
            system_prompt = expert_system
            judge_type = "expert"
        else:
            system_prompt = recipient_system
            judge_type = "recipient"

        # Construct evaluation prompt
        eval_prompt = f"""
## Writing Task
{prompt_data['full_prompt']}

## Response A
{shuffled['displayed_response_a']}

## Response B
{shuffled['displayed_response_b']}

{EVALUATION_RUBRIC}

Evaluate which response better fulfills the writing task.
"""

        # Get judgment
        result = await client.generate(
            judge_model,
            eval_prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent judging
        )

        judgment = parse_judgment_response(result["content"])
        judgment["judge_type"] = judge_type
        judgment["judge_index"] = judge_idx
        judgment["position_mapping"] = {
            "A": shuffled["actual_model_in_position_a"],
            "B": shuffled["actual_model_in_position_b"]
        }

        all_judgments.append(judgment)

    # Aggregate judgments
    aggregated = aggregate_judgments(
        all_judgments,
        response_a["model"],
        response_b["model"]
    )

    return {
        "comparison_id": comparison["comparison_id"],
        "prompt_id": prompt_data["prompt_id"],
        **aggregated
    }
```

---

## 6. Database Schema

### 6.1 Complete SQLite Schema

```sql
-- O*NET source data
CREATE TABLE onet_occupations (
    occupation_code TEXT PRIMARY KEY,
    occupation_title TEXT NOT NULL,
    writing_skill_importance REAL,
    writing_activity_importance REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE onet_writing_tasks (
    task_id TEXT PRIMARY KEY,
    occupation_code TEXT REFERENCES onet_occupations(occupation_code),
    task_description TEXT NOT NULL,
    importance_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Evaluation prompts
CREATE TABLE eval_prompts (
    prompt_id TEXT PRIMARY KEY,
    occupation_code TEXT REFERENCES onet_occupations(occupation_code),
    task_id TEXT REFERENCES onet_writing_tasks(task_id),
    industry_context TEXT NOT NULL,
    complexity_tier TEXT CHECK(complexity_tier IN ('simple', 'standard', 'complex')),
    prompt_template TEXT NOT NULL,
    full_prompt TEXT NOT NULL,
    context_data JSON,
    recipient_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prompts_occupation ON eval_prompts(occupation_code);
CREATE INDEX idx_prompts_complexity ON eval_prompts(complexity_tier);

-- Model responses
CREATE TABLE model_responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES eval_prompts(prompt_id),
    model_key TEXT NOT NULL,
    response_content TEXT NOT NULL,
    token_usage JSON,
    generation_time_ms INTEGER,
    error_message TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_responses_prompt ON model_responses(prompt_id);
CREATE INDEX idx_responses_model ON model_responses(model_key);

-- Pairwise comparisons
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES eval_prompts(prompt_id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    response_a_id TEXT REFERENCES model_responses(response_id),
    response_b_id TEXT REFERENCES model_responses(response_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_a, model_b)
);

CREATE INDEX idx_comparisons_models ON comparisons(model_a, model_b);

-- Individual judgments (5 per comparison)
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    judgment_index INTEGER CHECK(judgment_index BETWEEN 0 AND 4),
    judge_type TEXT CHECK(judge_type IN ('expert', 'recipient')),
    judge_model TEXT NOT NULL,
    displayed_position_a_model TEXT NOT NULL,
    displayed_position_b_model TEXT NOT NULL,

    -- Criterion-level scores
    clarity_winner TEXT CHECK(clarity_winner IN ('A', 'B', 'Tie')),
    clarity_reasoning TEXT,
    structure_winner TEXT CHECK(structure_winner IN ('A', 'B', 'Tie')),
    structure_reasoning TEXT,
    tone_winner TEXT CHECK(tone_winner IN ('A', 'B', 'Tie')),
    tone_reasoning TEXT,
    effectiveness_winner TEXT CHECK(effectiveness_winner IN ('A', 'B', 'Tie')),
    effectiveness_reasoning TEXT,
    conciseness_winner TEXT CHECK(conciseness_winner IN ('A', 'B', 'Tie')),
    conciseness_reasoning TEXT,

    -- Overall judgment
    overall_winner TEXT CHECK(overall_winner IN ('A', 'B', 'Tie')),
    overall_reasoning TEXT,
    confidence TEXT CHECK(confidence IN ('high', 'medium', 'low')),

    raw_response TEXT,
    judged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(comparison_id, judgment_index)
);

CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);

-- Aggregated comparison results
CREATE TABLE comparison_results (
    comparison_id TEXT PRIMARY KEY REFERENCES comparisons(comparison_id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    model_a_wins INTEGER NOT NULL,
    model_b_wins INTEGER NOT NULL,
    ties INTEGER NOT NULL,
    final_winner TEXT NOT NULL,
    agreement_rate REAL NOT NULL,

    -- Per-criterion aggregates
    clarity_a_wins INTEGER,
    clarity_b_wins INTEGER,
    structure_a_wins INTEGER,
    structure_b_wins INTEGER,
    tone_a_wins INTEGER,
    tone_b_wins INTEGER,
    effectiveness_a_wins INTEGER,
    effectiveness_b_wins INTEGER,
    conciseness_a_wins INTEGER,
    conciseness_b_wins INTEGER,

    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregate statistics view
CREATE VIEW model_pair_statistics AS
SELECT
    model_a,
    model_b,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN final_winner = model_a THEN 1 ELSE 0 END) as model_a_total_wins,
    SUM(CASE WHEN final_winner = model_b THEN 1 ELSE 0 END) as model_b_total_wins,
    SUM(CASE WHEN final_winner = 'Tie' THEN 1 ELSE 0 END) as total_ties,
    ROUND(AVG(agreement_rate), 3) as avg_agreement_rate,
    ROUND(100.0 * SUM(CASE WHEN final_winner = model_a THEN 1 ELSE 0 END) / COUNT(*), 1) as model_a_win_rate,
    ROUND(100.0 * SUM(CASE WHEN final_winner = model_b THEN 1 ELSE 0 END) / COUNT(*), 1) as model_b_win_rate
FROM comparison_results
GROUP BY model_a, model_b;

-- Per-occupation statistics
CREATE VIEW occupation_statistics AS
SELECT
    o.occupation_title,
    cr.model_a,
    cr.model_b,
    COUNT(*) as comparisons,
    SUM(CASE WHEN cr.final_winner = cr.model_a THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN cr.final_winner = cr.model_b THEN 1 ELSE 0 END) as model_b_wins
FROM comparison_results cr
JOIN comparisons c ON cr.comparison_id = c.comparison_id
JOIN eval_prompts ep ON c.prompt_id = ep.prompt_id
JOIN onet_occupations o ON ep.occupation_code = o.occupation_code
GROUP BY o.occupation_title, cr.model_a, cr.model_b;
```

---

## 7. Execution Pipeline

### 7.1 End-to-End Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXECUTION PIPELINE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ 1. O*NET     │───>│ 2. Prompt    │───>│ 3. Response          │  │
│  │ Data Load    │    │ Generation   │    │ Collection           │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                   │                      │               │
│         v                   v                      v               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ SQLite:      │    │ SQLite:      │    │ SQLite:              │  │
│  │ occupations, │    │ eval_prompts │    │ model_responses      │  │
│  │ tasks        │    │              │    │                      │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                                                    │               │
│                                                    v               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ 6. Analysis  │<───│ 5. Aggregate │<───│ 4. Pairwise          │  │
│  │ & Reporting  │    │ Results      │    │ Judging              │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                   │                      │               │
│         v                   v                      v               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ PDF Report   │    │ SQLite:      │    │ SQLite:              │  │
│  │ CSV Exports  │    │ comparison_  │    │ judgments,           │  │
│  │ Plots        │    │ results      │    │ comparisons          │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Main Orchestrator Script

**`scripts/run_eval.py`:**

```python
#!/usr/bin/env python3
"""
Main orchestrator for the Gemini Writing Evaluation.
"""

import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime

from src.data_pipeline import load_onet_data, generate_prompts
from src.model_client import OpenRouterClient, MODELS
from src.response_collector import collect_all_responses
from src.judging import run_all_judgments
from src.aggregation import compute_aggregates
from src.reporting import generate_reports

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models to evaluate
EVAL_MODELS = [
    "gemini-3-pro",
    "gemini-3-flash",
    "gpt-5.2",
    "claude-opus",
    "grok-3",
    "kimi-k2",
    "deepseek-v3"
]

# Gemini comparison pairs
GEMINI_COMPARISONS = [
    ("gemini-3-pro", "gpt-5.2"),
    ("gemini-3-pro", "claude-opus"),
    ("gemini-3-pro", "grok-3"),
    ("gemini-3-pro", "kimi-k2"),
    ("gemini-3-pro", "deepseek-v3"),
    ("gemini-3-flash", "gpt-5.2"),
    ("gemini-3-flash", "claude-opus"),
    ("gemini-3-flash", "grok-3"),
    ("gemini-3-flash", "kimi-k2"),
    ("gemini-3-flash", "deepseek-v3"),
    ("gemini-3-pro", "gemini-3-flash"),  # Internal comparison
]

async def run_pipeline(
    db_path: Path,
    prompts_per_occupation: int = 10,
    skip_stages: list[str] = None
):
    """Run the complete evaluation pipeline."""

    skip_stages = skip_stages or []

    # Stage 1: Load O*NET data
    if "onet" not in skip_stages:
        logger.info("Stage 1: Loading O*NET data...")
        load_onet_data(db_path)

    # Stage 2: Generate evaluation prompts
    if "prompts" not in skip_stages:
        logger.info("Stage 2: Generating evaluation prompts...")
        generate_prompts(db_path, prompts_per_occupation)

    # Stage 3: Collect model responses
    if "responses" not in skip_stages:
        logger.info("Stage 3: Collecting model responses...")
        client = OpenRouterClient()
        await collect_all_responses(db_path, client, EVAL_MODELS)

    # Stage 4: Run pairwise judgments
    if "judging" not in skip_stages:
        logger.info("Stage 4: Running pairwise judgments...")
        client = OpenRouterClient()
        await run_all_judgments(db_path, client, GEMINI_COMPARISONS)

    # Stage 5: Compute aggregates
    if "aggregate" not in skip_stages:
        logger.info("Stage 5: Computing aggregate statistics...")
        compute_aggregates(db_path)

    # Stage 6: Generate reports
    if "reports" not in skip_stages:
        logger.info("Stage 6: Generating reports...")
        generate_reports(db_path)

    logger.info("Pipeline complete!")

def main():
    parser = argparse.ArgumentParser(description="Run Gemini Writing Evaluation")
    parser.add_argument("--db", type=Path, default=Path("data/eval.db"))
    parser.add_argument("--prompts-per-occupation", type=int, default=10)
    parser.add_argument("--skip", nargs="*", default=[],
                       help="Stages to skip: onet, prompts, responses, judging, aggregate, reports")

    args = parser.parse_args()

    asyncio.run(run_pipeline(
        args.db,
        args.prompts_per_occupation,
        args.skip
    ))

if __name__ == "__main__":
    main()
```

### 7.3 Progress Tracking and Resumability

```python
class PipelineState:
    """Track pipeline progress for resumability."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_state_table()

    def _init_state_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_state (
                stage TEXT PRIMARY KEY,
                status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                progress_pct REAL,
                error_message TEXT
            )
        """)
        self.conn.commit()

    def mark_stage_started(self, stage: str):
        self.conn.execute("""
            INSERT OR REPLACE INTO pipeline_state (stage, status, started_at)
            VALUES (?, 'in_progress', ?)
        """, (stage, datetime.utcnow()))
        self.conn.commit()

    def update_progress(self, stage: str, progress_pct: float):
        self.conn.execute("""
            UPDATE pipeline_state SET progress_pct = ? WHERE stage = ?
        """, (progress_pct, stage))
        self.conn.commit()

    def mark_stage_completed(self, stage: str):
        self.conn.execute("""
            UPDATE pipeline_state
            SET status = 'completed', completed_at = ?
            WHERE stage = ?
        """, (datetime.utcnow(), stage))
        self.conn.commit()

    def get_incomplete_stages(self) -> list[str]:
        cursor = self.conn.execute("""
            SELECT stage FROM pipeline_state
            WHERE status != 'completed'
        """)
        return [row[0] for row in cursor.fetchall()]
```

---

## 8. Analysis & Reporting

### 8.1 Statistical Analysis

**`src/analysis.py`:**

```python
import pandas as pd
import numpy as np
from scipy import stats
import sqlite3

def compute_win_rates(db_path: Path) -> pd.DataFrame:
    """Compute win rates for all model pairs."""

    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        model_a,
        model_b,
        COUNT(*) as n,
        SUM(CASE WHEN final_winner = model_a THEN 1 ELSE 0 END) as a_wins,
        SUM(CASE WHEN final_winner = model_b THEN 1 ELSE 0 END) as b_wins,
        SUM(CASE WHEN final_winner = 'Tie' THEN 1 ELSE 0 END) as ties
    FROM comparison_results
    GROUP BY model_a, model_b
    """

    df = pd.read_sql(query, conn)

    # Compute win rates with confidence intervals
    df['a_win_rate'] = df['a_wins'] / df['n']
    df['b_win_rate'] = df['b_wins'] / df['n']

    # Wilson score confidence intervals
    for idx, row in df.iterrows():
        ci_low, ci_high = wilson_ci(row['a_wins'], row['n'])
        df.at[idx, 'a_ci_low'] = ci_low
        df.at[idx, 'a_ci_high'] = ci_high

    return df

def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple:
    """Compute Wilson score confidence interval."""
    if n == 0:
        return (0, 0)

    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n

    denominator = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denominator
    spread = z * np.sqrt((p*(1-p) + z**2/(4*n)) / n) / denominator

    return (max(0, center - spread), min(1, center + spread))

def compute_per_criterion_analysis(db_path: Path) -> pd.DataFrame:
    """Analyze performance by evaluation criterion."""

    conn = sqlite3.connect(db_path)

    criteria = ['clarity', 'structure', 'tone', 'effectiveness', 'conciseness']
    results = []

    for criterion in criteria:
        query = f"""
        SELECT
            c.model_a,
            c.model_b,
            SUM(CASE WHEN j.{criterion}_winner =
                CASE WHEN j.displayed_position_a_model = c.model_a THEN 'A' ELSE 'B' END
                THEN 1 ELSE 0 END) as a_wins,
            SUM(CASE WHEN j.{criterion}_winner =
                CASE WHEN j.displayed_position_b_model = c.model_b THEN 'B' ELSE 'A' END
                THEN 1 ELSE 0 END) as b_wins,
            COUNT(*) as total
        FROM judgments j
        JOIN comparisons c ON j.comparison_id = c.comparison_id
        GROUP BY c.model_a, c.model_b
        """

        df = pd.read_sql(query, conn)
        df['criterion'] = criterion
        results.append(df)

    return pd.concat(results)

def identify_gemini_weaknesses(db_path: Path) -> dict:
    """Identify specific areas where Gemini underperforms."""

    conn = sqlite3.connect(db_path)

    weaknesses = {
        "gemini-3-pro": {},
        "gemini-3-flash": {}
    }

    for gemini_model in weaknesses.keys():
        # Find task types where Gemini loses most often
        query = """
        SELECT
            ep.complexity_tier,
            o.occupation_title,
            cr.model_b as competitor,
            COUNT(*) as comparisons,
            SUM(CASE WHEN cr.final_winner = cr.model_b THEN 1 ELSE 0 END) as losses,
            ROUND(100.0 * SUM(CASE WHEN cr.final_winner = cr.model_b THEN 1 ELSE 0 END) / COUNT(*), 1) as loss_rate
        FROM comparison_results cr
        JOIN comparisons c ON cr.comparison_id = c.comparison_id
        JOIN eval_prompts ep ON c.prompt_id = ep.prompt_id
        JOIN onet_occupations o ON ep.occupation_code = o.occupation_code
        WHERE cr.model_a = ?
        GROUP BY ep.complexity_tier, o.occupation_title, cr.model_b
        HAVING loss_rate > 50
        ORDER BY loss_rate DESC
        """

        df = pd.read_sql(query, conn, params=[gemini_model])

        weaknesses[gemini_model] = {
            "high_loss_task_types": df.to_dict('records'),
            "worst_competitor": df.groupby('competitor')['losses'].sum().idxmax() if len(df) > 0 else None,
            "worst_complexity": df.groupby('complexity_tier')['losses'].sum().idxmax() if len(df) > 0 else None
        }

    return weaknesses
```

### 8.2 Visualization Generation

**`src/visualizations.py`:**

```python
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path

def plot_win_rate_heatmap(win_rates: pd.DataFrame, output_path: Path):
    """Generate win rate heatmap for all model pairs."""

    # Pivot to matrix format
    models = list(set(win_rates['model_a'].unique()) | set(win_rates['model_b'].unique()))
    matrix = pd.DataFrame(index=models, columns=models, data=0.5)

    for _, row in win_rates.iterrows():
        matrix.loc[row['model_a'], row['model_b']] = row['a_win_rate']
        matrix.loc[row['model_b'], row['model_a']] = row['b_win_rate']

    plt.figure(figsize=(12, 10))
    sns.heatmap(
        matrix.astype(float),
        annot=True,
        fmt='.2f',
        cmap='RdYlGn',
        center=0.5,
        vmin=0,
        vmax=1,
        square=True
    )
    plt.title('Model Win Rates (row vs column)')
    plt.tight_layout()
    plt.savefig(output_path / 'win_rate_heatmap.png', dpi=150)
    plt.close()

def plot_gemini_comparison_bars(win_rates: pd.DataFrame, output_path: Path):
    """Bar chart comparing Gemini vs each competitor."""

    gemini_models = ['gemini-3-pro', 'gemini-3-flash']

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for idx, gemini in enumerate(gemini_models):
        gemini_data = win_rates[win_rates['model_a'] == gemini].copy()
        gemini_data = gemini_data.sort_values('a_win_rate', ascending=True)

        ax = axes[idx]
        colors = ['green' if x > 0.5 else 'red' for x in gemini_data['a_win_rate']]

        bars = ax.barh(gemini_data['model_b'], gemini_data['a_win_rate'], color=colors)
        ax.axvline(x=0.5, color='black', linestyle='--', linewidth=1)
        ax.set_xlim(0, 1)
        ax.set_xlabel('Win Rate')
        ax.set_title(f'{gemini} vs Competitors')

        # Add value labels
        for bar, rate in zip(bars, gemini_data['a_win_rate']):
            ax.text(rate + 0.02, bar.get_y() + bar.get_height()/2,
                   f'{rate:.1%}', va='center')

    plt.tight_layout()
    plt.savefig(output_path / 'gemini_comparison_bars.png', dpi=150)
    plt.close()

def plot_criterion_breakdown(criterion_data: pd.DataFrame, output_path: Path):
    """Radar chart showing performance by criterion."""

    criteria = ['clarity', 'structure', 'tone', 'effectiveness', 'conciseness']

    # Focus on Gemini Pro vs top competitors
    gemini_vs_gpt = criterion_data[
        (criterion_data['model_a'] == 'gemini-3-pro') &
        (criterion_data['model_b'] == 'gpt-5.2')
    ]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    angles = np.linspace(0, 2*np.pi, len(criteria), endpoint=False).tolist()
    angles += angles[:1]  # Complete the circle

    values = [gemini_vs_gpt[gemini_vs_gpt['criterion'] == c]['a_win_rate'].values[0]
              for c in criteria]
    values += values[:1]

    ax.plot(angles, values, 'o-', linewidth=2, label='Gemini Pro')
    ax.fill(angles, values, alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(criteria)
    ax.set_ylim(0, 1)
    ax.axhline(y=0.5, color='red', linestyle='--', alpha=0.5)
    ax.set_title('Gemini Pro vs GPT-5.2 by Criterion')

    plt.tight_layout()
    plt.savefig(output_path / 'criterion_radar.png', dpi=150)
    plt.close()

def plot_occupation_performance(db_path: Path, output_path: Path):
    """Heatmap of Gemini performance by occupation category."""

    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        SUBSTR(o.occupation_code, 1, 2) as occupation_category,
        cr.model_a,
        cr.model_b,
        ROUND(100.0 * SUM(CASE WHEN cr.final_winner = cr.model_a THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
    FROM comparison_results cr
    JOIN comparisons c ON cr.comparison_id = c.comparison_id
    JOIN eval_prompts ep ON c.prompt_id = ep.prompt_id
    JOIN onet_occupations o ON ep.occupation_code = o.occupation_code
    WHERE cr.model_a LIKE 'gemini%'
    GROUP BY occupation_category, cr.model_a, cr.model_b
    """

    df = pd.read_sql(query, conn)

    # Map occupation codes to names
    occ_categories = {
        '11': 'Management',
        '13': 'Business/Financial',
        '15': 'Computer/Math',
        '17': 'Architecture/Engineering',
        '19': 'Life/Physical/Social Science',
        '21': 'Community/Social Service',
        '23': 'Legal',
        '25': 'Education',
        '27': 'Arts/Media',
        '29': 'Healthcare',
        '31': 'Healthcare Support',
        '33': 'Protective Service',
        '35': 'Food Preparation',
        '37': 'Building/Grounds',
        '39': 'Personal Care',
        '41': 'Sales',
        '43': 'Office/Admin',
        '45': 'Farming/Fishing',
        '47': 'Construction',
        '49': 'Installation/Maintenance',
        '51': 'Production',
        '53': 'Transportation'
    }

    df['occupation_name'] = df['occupation_category'].map(occ_categories)

    pivot = df.pivot_table(
        index='occupation_name',
        columns='model_b',
        values='win_rate',
        aggfunc='mean'
    )

    plt.figure(figsize=(14, 10))
    sns.heatmap(pivot, annot=True, fmt='.0f', cmap='RdYlGn', center=50)
    plt.title('Gemini Win Rate by Occupation Category')
    plt.tight_layout()
    plt.savefig(output_path / 'occupation_heatmap.png', dpi=150)
    plt.close()
```

### 8.3 PDF Report Generation

**`src/report_generator.py`:**

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from pathlib import Path

def generate_pdf_report(db_path: Path, output_path: Path):
    """Generate comprehensive PDF report."""

    doc = SimpleDocTemplate(
        str(output_path / "gemini_writing_eval_report.pdf"),
        pagesize=letter
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24)

    elements = []

    # Title
    elements.append(Paragraph("Gemini Writing Evaluation Report", title_style))
    elements.append(Spacer(1, 20))

    # Executive Summary
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    summary = generate_executive_summary(db_path)
    elements.append(Paragraph(summary, styles['Normal']))
    elements.append(Spacer(1, 20))

    # Methodology
    elements.append(Paragraph("Methodology", styles['Heading2']))
    elements.append(Paragraph(METHODOLOGY_TEXT, styles['Normal']))
    elements.append(Spacer(1, 20))

    # Overall Results
    elements.append(Paragraph("Overall Results", styles['Heading2']))
    elements.append(Image(str(output_path / 'win_rate_heatmap.png'), width=450, height=375))
    elements.append(Spacer(1, 10))
    elements.append(Image(str(output_path / 'gemini_comparison_bars.png'), width=500, height=215))
    elements.append(Spacer(1, 20))

    # Criterion Analysis
    elements.append(Paragraph("Performance by Criterion", styles['Heading2']))
    elements.append(Image(str(output_path / 'criterion_radar.png'), width=350, height=350))
    elements.append(Spacer(1, 20))

    # Weakness Analysis
    elements.append(Paragraph("Identified Weaknesses", styles['Heading2']))
    weaknesses = identify_gemini_weaknesses(db_path)
    for model, data in weaknesses.items():
        elements.append(Paragraph(f"<b>{model}</b>", styles['Normal']))
        weakness_text = format_weaknesses(data)
        elements.append(Paragraph(weakness_text, styles['Normal']))
        elements.append(Spacer(1, 10))

    # Recommendations
    elements.append(Paragraph("Recommendations", styles['Heading2']))
    recommendations = generate_recommendations(weaknesses)
    elements.append(Paragraph(recommendations, styles['Normal']))

    doc.build(elements)
    print(f"Report generated: {output_path / 'gemini_writing_eval_report.pdf'}")

METHODOLOGY_TEXT = """
This evaluation compared Gemini 3.0 Pro and Flash against leading frontier models across
realistic writing tasks derived from the O*NET occupational database. Key methodology elements:

<bullet>Pairwise comparisons with position shuffling to eliminate order bias</bullet>
<bullet>Best of 5 judgments per comparison for statistical robustness</bullet>
<bullet>Dual judge personas: writing expert and simulated recipient</bullet>
<bullet>Comprehensive rubric covering clarity, structure, tone, effectiveness, and conciseness</bullet>
<bullet>Tasks spanning all major US occupation categories with writing requirements</bullet>
"""
```

### 8.4 CSV Export

```python
def export_results_to_csv(db_path: Path, output_dir: Path):
    """Export all results to CSV for external analysis."""

    conn = sqlite3.connect(db_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    exports = [
        ("model_pair_win_rates.csv", "SELECT * FROM model_pair_statistics"),
        ("occupation_breakdown.csv", "SELECT * FROM occupation_statistics"),
        ("all_comparisons.csv", """
            SELECT
                c.comparison_id,
                ep.occupation_code,
                ep.industry_context,
                ep.complexity_tier,
                cr.model_a,
                cr.model_b,
                cr.final_winner,
                cr.model_a_wins,
                cr.model_b_wins,
                cr.ties,
                cr.agreement_rate
            FROM comparison_results cr
            JOIN comparisons c ON cr.comparison_id = c.comparison_id
            JOIN eval_prompts ep ON c.prompt_id = ep.prompt_id
        """),
        ("all_judgments.csv", """
            SELECT
                j.*,
                c.model_a,
                c.model_b
            FROM judgments j
            JOIN comparisons c ON j.comparison_id = c.comparison_id
        """),
    ]

    for filename, query in exports:
        df = pd.read_sql(query, conn)
        df.to_csv(output_dir / filename, index=False)
        print(f"Exported: {output_dir / filename}")

    conn.close()
```

---

## 9. Quality Assurance

### 9.1 Data Validation

```python
def validate_pipeline_data(db_path: Path) -> dict:
    """Comprehensive validation of all pipeline data."""

    conn = sqlite3.connect(db_path)
    issues = []

    # Check for missing responses
    missing_responses = pd.read_sql("""
        SELECT ep.prompt_id, m.model_key
        FROM eval_prompts ep
        CROSS JOIN (SELECT DISTINCT model_key FROM model_responses) m
        LEFT JOIN model_responses mr
            ON ep.prompt_id = mr.prompt_id AND m.model_key = mr.model_key
        WHERE mr.response_id IS NULL
    """, conn)

    if len(missing_responses) > 0:
        issues.append(f"Missing {len(missing_responses)} model responses")

    # Check for incomplete judgments
    incomplete_judgments = pd.read_sql("""
        SELECT c.comparison_id, COUNT(j.judgment_id) as judgment_count
        FROM comparisons c
        LEFT JOIN judgments j ON c.comparison_id = j.comparison_id
        GROUP BY c.comparison_id
        HAVING judgment_count < 5
    """, conn)

    if len(incomplete_judgments) > 0:
        issues.append(f"{len(incomplete_judgments)} comparisons have fewer than 5 judgments")

    # Check position shuffling distribution
    position_distribution = pd.read_sql("""
        SELECT
            displayed_position_a_model,
            COUNT(*) as count
        FROM judgments
        GROUP BY displayed_position_a_model
    """, conn)

    # Expect roughly 50-50 distribution
    total = position_distribution['count'].sum()
    for _, row in position_distribution.iterrows():
        ratio = row['count'] / total
        if abs(ratio - 0.5) > 0.05:  # More than 5% deviation
            issues.append(f"Position bias detected: {row['displayed_position_a_model']} appears in position A {ratio:.1%} of the time")

    # Check inter-judge agreement
    agreement_stats = pd.read_sql("""
        SELECT AVG(agreement_rate) as avg_agreement
        FROM comparison_results
    """, conn)

    avg_agreement = agreement_stats['avg_agreement'].values[0]
    if avg_agreement < 0.6:
        issues.append(f"Low inter-judge agreement: {avg_agreement:.1%}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "stats": {
            "total_prompts": pd.read_sql("SELECT COUNT(*) FROM eval_prompts", conn).iloc[0, 0],
            "total_responses": pd.read_sql("SELECT COUNT(*) FROM model_responses", conn).iloc[0, 0],
            "total_comparisons": pd.read_sql("SELECT COUNT(*) FROM comparisons", conn).iloc[0, 0],
            "total_judgments": pd.read_sql("SELECT COUNT(*) FROM judgments", conn).iloc[0, 0],
            "avg_agreement": avg_agreement
        }
    }
```

### 9.2 Judgment Quality Checks

```python
def analyze_judgment_quality(db_path: Path) -> dict:
    """Analyze quality and consistency of judgments."""

    conn = sqlite3.connect(db_path)

    # Check for position bias in judgments
    position_bias = pd.read_sql("""
        SELECT
            overall_winner,
            COUNT(*) as count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct
        FROM judgments
        GROUP BY overall_winner
    """, conn)

    # Check confidence distribution
    confidence_dist = pd.read_sql("""
        SELECT
            confidence,
            COUNT(*) as count
        FROM judgments
        GROUP BY confidence
    """, conn)

    # Check for judges always agreeing (suspicious)
    perfect_agreement = pd.read_sql("""
        SELECT
            comparison_id,
            COUNT(DISTINCT overall_winner) as distinct_winners
        FROM judgments
        GROUP BY comparison_id
        HAVING distinct_winners = 1
    """, conn)

    perfect_agreement_rate = len(perfect_agreement) / pd.read_sql(
        "SELECT COUNT(DISTINCT comparison_id) FROM judgments", conn
    ).iloc[0, 0]

    return {
        "position_bias": position_bias.to_dict('records'),
        "confidence_distribution": confidence_dist.to_dict('records'),
        "perfect_agreement_rate": perfect_agreement_rate,
        "suspicious_if_perfect_rate_above": 0.8  # Flag if >80% perfect agreement
    }
```

### 9.3 Reproducibility

```python
def ensure_reproducibility(db_path: Path):
    """Add reproducibility metadata to database."""

    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    import subprocess
    import sys

    metadata = {
        "python_version": sys.version,
        "git_commit": subprocess.getoutput("git rev-parse HEAD"),
        "git_branch": subprocess.getoutput("git branch --show-current"),
        "onet_version": "29.1",  # Update as needed
        "openrouter_models": str(list(MODELS.keys())),
        "random_seed": "42",  # If using seeded randomness
        "evaluation_date": datetime.utcnow().isoformat()
    }

    for key, value in metadata.items():
        conn.execute("""
            INSERT OR REPLACE INTO eval_metadata (key, value)
            VALUES (?, ?)
        """, (key, value))

    conn.commit()
    conn.close()
```

### 9.4 Fine-Grained Eval Viewer

**`scripts/eval_viewer.py`:**

```python
#!/usr/bin/env python3
"""
Interactive viewer for inspecting individual evaluations.
"""

import sqlite3
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def view_comparison(db_path: Path, comparison_id: str):
    """View detailed information for a specific comparison."""

    conn = sqlite3.connect(db_path)

    # Get comparison details
    comparison = pd.read_sql("""
        SELECT
            c.*,
            ep.full_prompt,
            ep.occupation_code,
            ep.industry_context,
            ep.complexity_tier,
            mr_a.response_content as response_a,
            mr_b.response_content as response_b,
            cr.final_winner,
            cr.model_a_wins,
            cr.model_b_wins,
            cr.ties
        FROM comparisons c
        JOIN eval_prompts ep ON c.prompt_id = ep.prompt_id
        JOIN model_responses mr_a ON c.response_a_id = mr_a.response_id
        JOIN model_responses mr_b ON c.response_b_id = mr_b.response_id
        JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
        WHERE c.comparison_id = ?
    """, conn, params=[comparison_id])

    if len(comparison) == 0:
        console.print(f"[red]Comparison {comparison_id} not found[/red]")
        return

    row = comparison.iloc[0]

    # Display prompt
    console.print(Panel(row['full_prompt'], title="Writing Prompt", border_style="blue"))

    # Display responses side by side
    table = Table(title="Model Responses")
    table.add_column(f"{row['model_a']}", style="cyan", width=50)
    table.add_column(f"{row['model_b']}", style="magenta", width=50)
    table.add_row(row['response_a'][:1000] + "...", row['response_b'][:1000] + "...")
    console.print(table)

    # Display judgments
    judgments = pd.read_sql("""
        SELECT * FROM judgments WHERE comparison_id = ?
        ORDER BY judgment_index
    """, conn, params=[comparison_id])

    console.print(f"\n[bold]Final Result:[/bold] {row['final_winner']}")
    console.print(f"Wins: {row['model_a']}={row['model_a_wins']}, {row['model_b']}={row['model_b_wins']}, Ties={row['ties']}")

    for _, j in judgments.iterrows():
        console.print(f"\n[dim]Judgment {j['judgment_index']+1} ({j['judge_type']}):[/dim]")
        console.print(f"  Winner: {j['overall_winner']} | Confidence: {j['confidence']}")
        console.print(f"  Reasoning: {j['overall_reasoning'][:200]}...")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/eval.db"))
    parser.add_argument("--comparison-id", type=str, help="View specific comparison")
    parser.add_argument("--list", action="store_true", help="List all comparisons")
    parser.add_argument("--filter-model", type=str, help="Filter by model")
    parser.add_argument("--filter-winner", type=str, help="Filter by winner")

    args = parser.parse_args()

    if args.comparison_id:
        view_comparison(args.db, args.comparison_id)
    elif args.list:
        list_comparisons(args.db, args.filter_model, args.filter_winner)

if __name__ == "__main__":
    main()
```

---

## 10. Project Structure

```
gemini-writing-eval/
├── README.md
├── requirements.txt
├── pyproject.toml
├── .env.example                    # OPENROUTER_API_KEY=...
│
├── data/
│   ├── onet_raw/                   # Downloaded O*NET files
│   ├── contexts/                   # Pre-generated context files
│   └── eval.db                     # Main SQLite database
│
├── scripts/
│   ├── download_onet.py            # O*NET data downloader
│   ├── extract_writing_tasks.py    # Extract writing-related data
│   ├── generate_prompts.py         # Prompt generation
│   ├── collect_responses.py        # Model response collection
│   ├── run_judgments.py            # Judging pipeline
│   ├── run_eval.py                 # Main orchestrator
│   └── eval_viewer.py              # Interactive result viewer
│
├── src/
│   ├── __init__.py
│   ├── model_client.py             # OpenRouter API client
│   ├── data_pipeline.py            # O*NET data processing
│   ├── prompt_generator.py         # Prompt creation logic
│   ├── context_generator.py        # Synthetic context generation
│   ├── judging.py                  # Judgment pipeline
│   ├── aggregation.py              # Result aggregation
│   ├── analysis.py                 # Statistical analysis
│   ├── visualizations.py           # Plot generation
│   └── report_generator.py         # PDF report creation
│
├── outputs/
│   ├── plots/                      # Generated visualizations
│   ├── reports/                    # PDF reports
│   └── exports/                    # CSV exports
│
└── tests/
    ├── test_prompt_generation.py
    ├── test_judging.py
    └── test_aggregation.py
```

---

## 11. Execution Timeline

| Phase | Tasks | Duration |
|-------|-------|----------|
| **Setup** | Environment setup, O*NET download, database init | 1 day |
| **Prompt Generation** | Generate ~5,000 diverse prompts | 2 days |
| **Response Collection** | Collect responses from all 7 models | 3-5 days |
| **Judging** | Run ~55,000 pairwise judgments (11 pairs x 5000 prompts) | 5-7 days |
| **Analysis** | Aggregate, visualize, report | 2 days |
| **Total** | | ~2-3 weeks |

---

## 12. Cost Estimation

| Component | Estimated Tokens | Cost Estimate |
|-----------|------------------|---------------|
| Response Generation | 7 models x 5000 prompts x ~1000 tokens = 35M tokens | ~$350-700 |
| Judging | 55,000 comparisons x 5 judgments x ~2000 tokens = 550M tokens | ~$2,000-4,000 |
| **Total** | | **~$2,500-5,000** |

*Costs vary by model pricing on OpenRouter*

---

## 13. Key Success Metrics

1. **Coverage**: Minimum 80% of O*NET occupation categories represented
2. **Statistical Power**: Minimum 100 comparisons per model pair for significance
3. **Inter-Judge Agreement**: Target >70% agreement rate
4. **Position Bias**: <55% either position winning overall
5. **Confidence**: >60% of judgments with "high" confidence

---

## Appendix A: Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENROUTER_API_KEY="your-api-key"

# Initialize database
python scripts/download_onet.py
python scripts/extract_writing_tasks.py

# Run full evaluation
python scripts/run_eval.py
```

**requirements.txt:**
```
aiohttp>=3.9.0
backoff>=2.2.0
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
matplotlib>=3.7.0
seaborn>=0.12.0
reportlab>=4.0.0
rich>=13.0.0
faker>=18.0.0
python-dotenv>=1.0.0
```

---

## Appendix B: Sample Prompts by Occupation

### Chief Executive (11-1011.00)
**Simple:** "Write a brief thank-you email to a longtime business partner after a successful meeting."

**Standard:** "Draft a quarterly update email to all employees about company performance. Q3 revenue was $12.3M (up 15% YoY), new product launch exceeded targets, but supply chain issues caused delivery delays."

**Complex:** "Prepare talking points and a summary memo for the board of directors regarding a potential acquisition of a competitor. Include strategic rationale, financial considerations, integration risks, and recommended next steps."

### Software Developer (15-1252.00)
**Simple:** "Write a commit message for a bug fix that resolved a null pointer exception in the user authentication module."

**Standard:** "Draft a technical design document for implementing a new caching layer. The system currently handles 10,000 requests/minute and needs to scale to 100,000 with sub-50ms latency."

**Complex:** "Write a post-mortem document for a production incident where database failover caused 45 minutes of downtime. Include timeline, root cause analysis, impact assessment, and preventive measures."

### Registered Nurse (29-1141.00)
**Simple:** "Write a shift handoff note for an incoming nurse about a stable post-operative patient."

**Standard:** "Document a patient's change in condition: 72-year-old male with CHF showing increased shortness of breath, elevated BP (165/95), and new-onset ankle edema. Include your assessment and actions taken."

**Complex:** "Draft a care coordination summary for a patient being discharged to home hospice care, including medication reconciliation, family education completed, and follow-up appointments scheduled."

---

*This plan provides a comprehensive framework for evaluating Gemini's writing capabilities against frontier competitors. The methodology prioritizes statistical rigor, diverse task coverage, and actionable insights into specific areas where Gemini may underperform.*
