# Gemini Writing Evaluation Framework: Master Implementation Plan

**Version:** 3.0
**Date:** January 2026
**Purpose:** Compare Gemini 3.0 Pro/Flash against frontier models using realistic writing tasks from across the US economy

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [O*NET Data Pipeline](#2-onet-data-pipeline)
3. [Eval Prompt Generation](#3-eval-prompt-generation)
4. [Context Generation](#4-context-generation)
5. [Model Integration](#5-model-integration)
6. [Judging Framework](#6-judging-framework)
7. [Database Schema](#7-database-schema)
8. [Execution Pipeline](#8-execution-pipeline)
9. [Analysis & Reporting](#9-analysis--reporting)
10. [Quality Assurance](#10-quality-assurance)

---

## 1. Executive Summary

This framework evaluates writing capabilities of leading AI models across **every job type in the US economy** that involves writing tasks. We use O*NET (Occupational Information Network) as our authoritative source for job classifications and task descriptions, then generate realistic writing prompts that span industries, contexts, and complexity levels.

### Models Under Evaluation

| Model | Provider | OpenRouter Model ID |
|-------|----------|---------------------|
| Gemini 3.0 Pro | Google | `google/gemini-3.0-pro` |
| Gemini 3.0 Flash | Google | `google/gemini-3.0-flash` |
| GPT-5.2 | OpenAI | `openai/gpt-5.2` |
| Claude Opus 4.5 | Anthropic | `anthropic/claude-opus-4-5` |
| Grok-3 | xAI | `x-ai/grok-3` |
| Kimi-2 | Moonshot | `moonshot/kimi-2` |
| Llama 4 Maverick | Meta | `meta-llama/llama-4-maverick` |

### Core Methodology

- **Pairwise comparisons**: Always Gemini vs. one competitor
- **Best of 5 judgments**: Robust aggregation
- **Position shuffling**: Eliminate order bias
- **Dual judges**: Expert writer + target recipient persona
- **Comprehensive coverage**: All O*NET occupations with writing requirements

---

## 2. O*NET Data Pipeline

### 2.1 Data Source

O*NET provides comprehensive occupational data including detailed work activities (DWAs), tasks, skills, and abilities for 1,000+ occupations. The database is freely available from https://www.onetcenter.org/database.html.

### 2.2 Download Script

```python
#!/usr/bin/env python3
"""
scripts/download_onet.py - Download and extract O*NET database
"""

import os
import requests
import zipfile
from pathlib import Path

ONET_VERSION = "29_1"  # Update to latest version
ONET_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION}_excel.zip"
DATA_DIR = Path("data/onet")

def download_onet():
    """Download O*NET database if not already present."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / f"onet_{ONET_VERSION}.zip"

    if not zip_path.exists():
        print(f"Downloading O*NET {ONET_VERSION}...")
        response = requests.get(ONET_URL, stream=True)
        response.raise_for_status()

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")

    # Extract
    extract_dir = DATA_DIR / f"db_{ONET_VERSION}"
    if not extract_dir.exists():
        print("Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        print("Extraction complete.")

    return extract_dir

if __name__ == "__main__":
    download_onet()
```

### 2.3 Writing Task Extraction

We identify writing-related tasks using multiple O*NET tables:

```python
#!/usr/bin/env python3
"""
scripts/extract_writing_tasks.py - Extract writing-related occupations and tasks
"""

import pandas as pd
import sqlite3
from pathlib import Path

WRITING_KEYWORDS = [
    'write', 'writing', 'written', 'draft', 'compose', 'document',
    'report', 'correspondence', 'email', 'memo', 'letter', 'proposal',
    'manuscript', 'article', 'content', 'copy', 'script', 'brief',
    'communicate', 'prepare', 'create', 'develop'  # often paired with documents
]

WRITING_SKILLS = [
    '2.A.1.a',  # Written Comprehension
    '2.A.1.b',  # Written Expression
]

def load_onet_data(onet_dir: Path) -> dict:
    """Load relevant O*NET tables into DataFrames."""
    tables = {}

    # Core tables
    files = [
        'Occupation Data.xlsx',
        'Task Statements.xlsx',
        'Tasks to DWAs.xlsx',
        'DWA Reference.xlsx',
        'Abilities.xlsx',
        'Skills.xlsx',
        'Work Activities.xlsx'
    ]

    for fname in files:
        fpath = onet_dir / fname
        if fpath.exists():
            key = fname.replace('.xlsx', '').replace(' ', '_').lower()
            tables[key] = pd.read_excel(fpath)

    return tables

def filter_writing_occupations(tables: dict) -> pd.DataFrame:
    """Identify occupations with significant writing requirements."""

    # Method 1: Filter by Writing skills/abilities scores
    abilities = tables.get('abilities', pd.DataFrame())
    writing_abilities = abilities[
        (abilities['Element ID'].isin(WRITING_SKILLS)) &
        (abilities['Data Value'] >= 3.5)  # Above average importance
    ]['O*NET-SOC Code'].unique()

    # Method 2: Filter by task descriptions containing writing keywords
    tasks = tables.get('task_statements', pd.DataFrame())
    pattern = '|'.join(WRITING_KEYWORDS)
    writing_tasks = tasks[
        tasks['Task'].str.lower().str.contains(pattern, na=False, regex=True)
    ]

    # Combine and get occupation details
    occupations = tables.get('occupation_data', pd.DataFrame())
    writing_occ_codes = set(writing_abilities) | set(writing_tasks['O*NET-SOC Code'].unique())

    result = occupations[occupations['O*NET-SOC Code'].isin(writing_occ_codes)].copy()

    # Add writing tasks as JSON column
    task_map = writing_tasks.groupby('O*NET-SOC Code')['Task'].apply(list).to_dict()
    result['writing_tasks'] = result['O*NET-SOC Code'].map(task_map)

    return result

def save_to_sqlite(df: pd.DataFrame, db_path: str):
    """Save extracted data to SQLite."""
    conn = sqlite3.connect(db_path)
    df.to_sql('writing_occupations', conn, if_exists='replace', index=False)
    conn.close()

if __name__ == "__main__":
    onet_dir = Path("data/onet/db_29_1")
    tables = load_onet_data(onet_dir)
    writing_occs = filter_writing_occupations(tables)
    print(f"Found {len(writing_occs)} occupations with writing requirements")
    save_to_sqlite(writing_occs, "data/eval.db")
```

### 2.4 Expected Output

This pipeline produces a table of ~600-800 occupations with:
- O*NET-SOC Code (e.g., "11-1011.00")
- Title (e.g., "Chief Executives")
- Description
- Writing-specific tasks extracted from task statements

---

## 3. Eval Prompt Generation

### 3.1 Industry Diversification Strategy

For each occupation, we generate multiple industry variants to ensure diversity:

```python
"""
scripts/generate_prompts.py - Generate diverse writing prompts
"""

import json
import random
from dataclasses import dataclass
from typing import List, Optional

# Industry contexts for diversification
INDUSTRY_SECTORS = {
    "technology": ["AI startup", "cybersecurity firm", "cloud computing company", "fintech"],
    "healthcare": ["hospital system", "pharmaceutical company", "biotech startup", "telehealth provider"],
    "finance": ["investment bank", "hedge fund", "credit union", "insurance company"],
    "retail": ["e-commerce platform", "luxury brand", "grocery chain", "department store"],
    "manufacturing": ["automotive", "aerospace", "consumer electronics", "industrial equipment"],
    "nonprofit": ["environmental charity", "education foundation", "healthcare nonprofit", "arts organization"],
    "government": ["federal agency", "state government", "municipal office", "public utility"],
    "education": ["research university", "community college", "K-12 school district", "EdTech company"],
    "media": ["news organization", "streaming service", "advertising agency", "publishing house"],
    "professional_services": ["law firm", "consulting firm", "accounting practice", "architecture studio"]
}

COMPANY_SIZE_CONTEXTS = ["small (50 employees)", "medium (500 employees)", "large (5000+ employees)"]

@dataclass
class WritingPrompt:
    """Represents a generated writing prompt for evaluation."""
    prompt_id: str
    occupation_code: str
    occupation_title: str
    task_description: str
    industry: str
    company_context: str
    writing_type: str  # email, report, proposal, etc.
    complexity: str    # simple, moderate, complex
    prompt_text: str
    context_required: bool
    context_description: Optional[str] = None
    target_recipient: str = ""
    word_count_guidance: str = ""

WRITING_TYPE_TEMPLATES = {
    "email": {
        "simple": "Write a professional email to {recipient} regarding {topic}.",
        "moderate": "Write a detailed email to {recipient} about {topic}. Include {requirements}.",
        "complex": "Write a comprehensive email thread response to {recipient} addressing {topic}. Consider {constraints} and ensure {outcomes}."
    },
    "report": {
        "simple": "Write a brief summary report on {topic}.",
        "moderate": "Write a detailed report on {topic} including {sections}.",
        "complex": "Write a comprehensive analytical report on {topic} with executive summary, methodology, findings, and recommendations."
    },
    "proposal": {
        "simple": "Write a short proposal for {initiative}.",
        "moderate": "Write a detailed proposal for {initiative} including objectives, timeline, and budget.",
        "complex": "Write a comprehensive business proposal for {initiative} with market analysis, implementation plan, risk assessment, and ROI projections."
    },
    "memo": {
        "simple": "Write an internal memo announcing {announcement}.",
        "moderate": "Write a policy memo regarding {policy} with rationale and implementation steps.",
        "complex": "Write an executive memo addressing {issue} with background analysis, stakeholder impacts, and recommended actions."
    },
    "correspondence": {
        "simple": "Write a formal letter to {recipient} about {matter}.",
        "moderate": "Write a detailed letter to {recipient} regarding {matter} with supporting arguments.",
        "complex": "Write a persuasive letter to {recipient} on {matter} addressing potential objections and proposing next steps."
    }
}

def generate_prompts_for_occupation(
    occ_code: str,
    occ_title: str,
    writing_tasks: List[str],
    num_prompts: int = 10
) -> List[WritingPrompt]:
    """Generate diverse writing prompts for an occupation."""

    prompts = []

    # Select random industries and contexts
    for i in range(num_prompts):
        sector = random.choice(list(INDUSTRY_SECTORS.keys()))
        industry = random.choice(INDUSTRY_SECTORS[sector])
        company_size = random.choice(COMPANY_SIZE_CONTEXTS)
        writing_type = random.choice(list(WRITING_TYPE_TEMPLATES.keys()))
        complexity = random.choice(["simple", "moderate", "complex"])

        # Select a writing task if available
        task = random.choice(writing_tasks) if writing_tasks else "general professional communication"

        # Determine if context is required (complex prompts need context)
        context_required = complexity == "complex" or random.random() < 0.3

        # Generate the actual prompt
        prompt_text = generate_specific_prompt(
            occ_title, industry, company_size, writing_type, complexity, task
        )

        target_recipient = infer_recipient(occ_title, writing_type, task)

        prompt = WritingPrompt(
            prompt_id=f"{occ_code}_{i:04d}",
            occupation_code=occ_code,
            occupation_title=occ_title,
            task_description=task,
            industry=industry,
            company_context=f"{industry}, {company_size}",
            writing_type=writing_type,
            complexity=complexity,
            prompt_text=prompt_text,
            context_required=context_required,
            context_description=generate_context_description(context_required, industry, task),
            target_recipient=target_recipient,
            word_count_guidance=get_word_count_guidance(writing_type, complexity)
        )
        prompts.append(prompt)

    return prompts

def generate_specific_prompt(occ_title, industry, company_size, writing_type, complexity, task):
    """Generate specific prompt text based on parameters."""

    # This would use an LLM to generate realistic prompts
    # For the plan, here's the structure:

    base_template = f"""You are a {occ_title} at a {company_size} {industry}.

Your task: {task}

Writing requirement: {WRITING_TYPE_TEMPLATES[writing_type][complexity]}

Additional context will be provided below if applicable.
"""
    return base_template

def get_word_count_guidance(writing_type: str, complexity: str) -> str:
    """Return appropriate word count guidance."""
    guidance = {
        ("email", "simple"): "150-300 words",
        ("email", "moderate"): "300-500 words",
        ("email", "complex"): "500-800 words",
        ("report", "simple"): "300-500 words",
        ("report", "moderate"): "800-1500 words",
        ("report", "complex"): "1500-3000 words",
        ("proposal", "simple"): "400-600 words",
        ("proposal", "moderate"): "1000-2000 words",
        ("proposal", "complex"): "2500-5000 words",
        ("memo", "simple"): "150-300 words",
        ("memo", "moderate"): "400-700 words",
        ("memo", "complex"): "800-1200 words",
        ("correspondence", "simple"): "200-400 words",
        ("correspondence", "moderate"): "400-700 words",
        ("correspondence", "complex"): "700-1200 words",
    }
    return guidance.get((writing_type, complexity), "500-1000 words")
```

### 3.2 Prompt Complexity Distribution

Target distribution across complexity levels:
- **Simple (30%)**: Direct requests with minimal context needed
- **Moderate (45%)**: Requires some domain knowledge and structure
- **Complex (25%)**: Requires significant context, multiple considerations, nuanced tone

---

## 4. Context Generation

### 4.1 Context Types

Different prompts require different context types:

| Context Type | Description | Generation Method |
|--------------|-------------|-------------------|
| Company Background | Company history, mission, values | LLM-generated + templates |
| Recipient Profile | Who receives the writing, their role, preferences | LLM-generated personas |
| Prior Communication | Previous emails/documents in a thread | LLM-generated examples |
| Data/Metrics | Numbers, statistics, performance data | Synthetic data generation |
| Policy/Regulatory | Rules, guidelines, compliance requirements | Domain-specific templates |
| Project Details | Timelines, deliverables, stakeholders | Structured generation |

### 4.2 Context Generation Pipeline

```python
"""
scripts/generate_context.py - Generate contextual information for prompts
"""

import openai
from typing import Dict, Any
import json

CONTEXT_GENERATION_PROMPT = """Generate realistic context for the following writing task.

Occupation: {occupation}
Industry: {industry}
Writing Type: {writing_type}
Task Description: {task}

Generate the following contextual elements in JSON format:
1. company_background: 2-3 sentences about the company
2. recipient_profile: Name, role, relationship to writer, communication preferences
3. relevant_data: Any numbers, metrics, or facts that should be included
4. constraints: Any limitations, deadlines, or requirements
5. tone_guidance: Appropriate tone for this context
6. prior_context: Any relevant background information the writer would know

Output valid JSON only."""

class ContextGenerator:
    def __init__(self, openrouter_api_key: str):
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key
        )

    def generate_context(self, prompt: 'WritingPrompt') -> Dict[str, Any]:
        """Generate context for a writing prompt."""

        if not prompt.context_required:
            return {}

        response = self.client.chat.completions.create(
            model="google/gemini-3.0-flash",  # Use fast model for context generation
            messages=[{
                "role": "user",
                "content": CONTEXT_GENERATION_PROMPT.format(
                    occupation=prompt.occupation_title,
                    industry=prompt.industry,
                    writing_type=prompt.writing_type,
                    task=prompt.task_description
                )
            }],
            temperature=0.7,
            max_tokens=1000
        )

        try:
            context = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # Fallback to structured extraction
            context = self._extract_structured_context(response.choices[0].message.content)

        return context

    def generate_synthetic_data(self, data_type: str, industry: str) -> Dict[str, Any]:
        """Generate synthetic data for prompts requiring metrics/numbers."""

        data_templates = {
            "financial": {
                "revenue": f"${random.randint(10, 500)}M",
                "growth_rate": f"{random.randint(-5, 30)}%",
                "profit_margin": f"{random.randint(5, 25)}%"
            },
            "performance": {
                "completion_rate": f"{random.randint(75, 99)}%",
                "customer_satisfaction": f"{random.randint(70, 95)}/100",
                "response_time": f"{random.randint(1, 48)} hours"
            },
            "project": {
                "budget": f"${random.randint(50, 5000)}K",
                "timeline": f"{random.randint(2, 18)} months",
                "team_size": f"{random.randint(3, 50)} people"
            }
        }

        return data_templates.get(data_type, {})
```

### 4.3 External Data Sources

For certain specialized contexts, we download real data:

```python
# Industry-specific data sources
DATA_SOURCES = {
    "sec_filings": "https://www.sec.gov/cgi-bin/browse-edgar",  # Public company filings
    "bls_statistics": "https://www.bls.gov/data/",  # Labor statistics
    "census_data": "https://data.census.gov/",  # Economic census
    "fdic_data": "https://www.fdic.gov/resources/data-tools/",  # Banking data
}

def download_industry_context(industry: str) -> Dict[str, Any]:
    """Download real-world context data for specific industries."""
    # Implementation for each data source
    pass
```

---

## 5. Model Integration

### 5.1 OpenRouter API Integration

```python
"""
src/models/openrouter_client.py - OpenRouter API client for model access
"""

import openai
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional
import time
import logging

@dataclass
class ModelConfig:
    model_id: str
    display_name: str
    provider: str
    max_tokens: int = 4096
    temperature: float = 0.7

MODELS = {
    "gemini-pro": ModelConfig("google/gemini-3.0-pro", "Gemini 3.0 Pro", "Google"),
    "gemini-flash": ModelConfig("google/gemini-3.0-flash", "Gemini 3.0 Flash", "Google"),
    "gpt-5.2": ModelConfig("openai/gpt-5.2", "GPT-5.2", "OpenAI"),
    "claude-opus": ModelConfig("anthropic/claude-opus-4-5", "Claude Opus 4.5", "Anthropic"),
    "grok-3": ModelConfig("x-ai/grok-3", "Grok-3", "xAI"),
    "kimi-2": ModelConfig("moonshot/kimi-2", "Kimi-2", "Moonshot"),
    "llama-4": ModelConfig("meta-llama/llama-4-maverick", "Llama 4 Maverick", "Meta"),
}

class OpenRouterClient:
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.rate_limiter = asyncio.Semaphore(10)  # Max concurrent requests

    async def generate_writing(
        self,
        model_key: str,
        prompt: str,
        context: Optional[str] = None,
        max_tokens: int = 4096
    ) -> Dict:
        """Generate writing from a model."""

        config = MODELS[model_key]

        full_prompt = prompt
        if context:
            full_prompt = f"{context}\n\n---\n\n{prompt}"

        async with self.rate_limiter:
            start_time = time.time()

            try:
                response = await self.client.chat.completions.create(
                    model=config.model_id,
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=config.temperature,
                    max_tokens=max_tokens,
                    extra_headers={
                        "HTTP-Referer": "https://eval-framework.internal",
                        "X-Title": "Gemini Writing Eval"
                    }
                )

                latency = time.time() - start_time

                return {
                    "model": model_key,
                    "content": response.choices[0].message.content,
                    "finish_reason": response.choices[0].finish_reason,
                    "tokens_used": response.usage.total_tokens if response.usage else None,
                    "latency_seconds": latency,
                    "success": True
                }

            except Exception as e:
                logging.error(f"Error with {model_key}: {e}")
                return {
                    "model": model_key,
                    "content": None,
                    "error": str(e),
                    "success": False
                }

    async def generate_pairwise(
        self,
        gemini_model: str,
        competitor_model: str,
        prompt: str,
        context: Optional[str] = None
    ) -> Dict:
        """Generate writing from both models for comparison."""

        tasks = [
            self.generate_writing(gemini_model, prompt, context),
            self.generate_writing(competitor_model, prompt, context)
        ]

        results = await asyncio.gather(*tasks)

        return {
            "gemini": results[0],
            "competitor": results[1]
        }
```

### 5.2 Rate Limiting and Retry Logic

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class RateLimitedClient(OpenRouterClient):
    def __init__(self, api_key: str, requests_per_minute: int = 60):
        super().__init__(api_key)
        self.rpm = requests_per_minute
        self.request_times = []

    async def _wait_for_rate_limit(self):
        """Implement sliding window rate limiting."""
        now = time.time()
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.rpm:
            wait_time = 60 - (now - self.request_times[0])
            await asyncio.sleep(wait_time)

        self.request_times.append(now)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
    async def generate_writing_with_retry(self, *args, **kwargs):
        await self._wait_for_rate_limit()
        return await self.generate_writing(*args, **kwargs)
```

---

## 6. Judging Framework

### 6.1 Expert Writer Persona

```python
EXPERT_WRITER_PROMPT = """You are an expert writing evaluator with 20+ years of experience in professional communication, technical writing, and business correspondence. You have worked as:
- Senior editor at a major publication
- Corporate communications director at Fortune 500 companies
- Writing instructor at a top business school

You evaluate writing with a critical but fair eye, focusing on:
1. **Clarity**: Is the message immediately understandable? Are ideas logically organized?
2. **Effectiveness**: Does the writing achieve its intended purpose? Is it persuasive/informative as needed?
3. **Professionalism**: Is the tone appropriate? Are there any errors or awkward phrasings?
4. **Structure**: Is the format appropriate? Are paragraphs well-organized?
5. **Conciseness**: Is every word necessary? Is the length appropriate for the task?

You will compare two pieces of writing (A and B) for the same task. You must:
1. Analyze each piece against the criteria above
2. Identify specific strengths and weaknesses with quotes
3. Determine which is better overall, or if they are equal
4. Provide your verdict as: A_WINS, B_WINS, or TIE

Be rigorous and specific in your analysis. Avoid vague statements."""

EXPERT_EVALUATION_TEMPLATE = """## Writing Task
{task_description}

## Context Provided
{context}

## Response A
{response_a}

## Response B
{response_b}

---

Evaluate both responses according to your expertise. Structure your response as:

### Analysis of Response A
[Detailed analysis with specific quotes]

### Analysis of Response B
[Detailed analysis with specific quotes]

### Comparative Assessment
[Direct comparison on each criterion]

### Verdict
[One of: A_WINS, B_WINS, TIE]
Confidence: [HIGH, MEDIUM, LOW]
Reasoning: [One sentence summary]"""
```

### 6.2 Target Recipient Persona

```python
RECIPIENT_PERSONA_TEMPLATE = """You are {recipient_name}, {recipient_role} at {company}.

Background:
- {years_experience} years in your field
- Communication style preference: {communication_style}
- Key priorities: {priorities}
- Pet peeves in written communication: {pet_peeves}

You are evaluating two versions of a {writing_type} that was sent to you. Consider:
1. Does this writing respect your time?
2. Is the information you need clearly presented?
3. Would you feel confident acting on this communication?
4. Does the tone feel appropriate for your relationship with the sender?
5. Would you need to ask follow-up questions?

Compare Response A and Response B from your perspective as the actual recipient."""

def generate_recipient_persona(prompt: 'WritingPrompt') -> str:
    """Generate a realistic recipient persona based on the writing task."""

    # Map writing types to typical recipients
    recipient_templates = {
        "email": {
            "roles": ["manager", "colleague", "client", "vendor", "executive"],
            "styles": ["brief and direct", "detailed and thorough", "formal", "casual professional"],
            "pet_peeves": [
                "burying the main point",
                "unnecessary jargon",
                "overly long emails",
                "missing action items",
                "vague requests"
            ]
        },
        # ... other writing types
    }

    template_data = recipient_templates.get(prompt.writing_type, recipient_templates["email"])

    return RECIPIENT_PERSONA_TEMPLATE.format(
        recipient_name=generate_realistic_name(),
        recipient_role=random.choice(template_data["roles"]),
        company=prompt.industry,
        years_experience=random.randint(5, 25),
        communication_style=random.choice(template_data["styles"]),
        priorities=generate_role_priorities(prompt),
        pet_peeves=random.sample(template_data["pet_peeves"], 2),
        writing_type=prompt.writing_type
    )
```

### 6.3 Evaluation Rubric

```python
EVALUATION_RUBRIC = {
    "clarity": {
        "weight": 0.25,
        "criteria": [
            "Main message is immediately apparent",
            "Ideas flow logically",
            "No ambiguous statements",
            "Technical terms are explained when needed",
            "Reader doesn't need to re-read to understand"
        ],
        "scoring": {
            5: "Exceptionally clear, could be used as an example",
            4: "Clear with minor areas for improvement",
            3: "Adequately clear but some confusion possible",
            2: "Several unclear sections that impede understanding",
            1: "Significantly unclear, major revision needed"
        }
    },
    "tone_appropriateness": {
        "weight": 0.20,
        "criteria": [
            "Matches the professional context",
            "Appropriate formality level",
            "Respectful and considerate",
            "Confident without being arrogant",
            "Matches relationship with recipient"
        ],
        "scoring": {
            5: "Perfect tone for the situation",
            4: "Appropriate with minor adjustments possible",
            3: "Generally appropriate but inconsistent",
            2: "Noticeably inappropriate in places",
            1: "Significantly wrong tone throughout"
        }
    },
    "effectiveness": {
        "weight": 0.25,
        "criteria": [
            "Achieves the stated purpose",
            "Persuasive where needed",
            "Includes necessary information",
            "Calls to action are clear",
            "Anticipates reader questions"
        ],
        "scoring": {
            5: "Highly effective, exceeds expectations",
            4: "Effective with room for optimization",
            3: "Adequate but could be more impactful",
            2: "Partially effective, missing key elements",
            1: "Ineffective, fails to achieve purpose"
        }
    },
    "structure_format": {
        "weight": 0.15,
        "criteria": [
            "Appropriate format for the writing type",
            "Good use of paragraphs/sections",
            "Effective use of headers/bullets if appropriate",
            "Logical information hierarchy",
            "Professional appearance"
        ],
        "scoring": {
            5: "Excellent structure, easy to navigate",
            4: "Good structure with minor issues",
            3: "Adequate structure",
            2: "Poor structure impedes reading",
            1: "No discernible structure"
        }
    },
    "length_conciseness": {
        "weight": 0.15,
        "criteria": [
            "Appropriate length for the task",
            "No unnecessary repetition",
            "Every paragraph adds value",
            "Not padded with filler",
            "Not so brief as to omit important information"
        ],
        "scoring": {
            5: "Perfect length, every word earns its place",
            4: "Good length with minor trimming possible",
            3: "Acceptable but could be tightened",
            2: "Noticeably too long or too short",
            1: "Significantly inappropriate length"
        }
    }
}
```

### 6.4 Position Shuffling Implementation

```python
import random
import hashlib

def shuffle_responses(
    response_a: str,
    response_b: str,
    prompt_id: str,
    judge_run: int
) -> tuple:
    """
    Deterministically shuffle response order to eliminate position bias.
    Uses prompt_id and judge_run for reproducibility.
    """

    # Create deterministic seed from prompt_id and run number
    seed_string = f"{prompt_id}_{judge_run}"
    seed = int(hashlib.sha256(seed_string.encode()).hexdigest()[:8], 16)

    rng = random.Random(seed)

    if rng.random() < 0.5:
        return response_a, response_b, "A_is_gemini"
    else:
        return response_b, response_a, "B_is_gemini"

def aggregate_judgments(judgments: List[Dict]) -> Dict:
    """
    Aggregate 5 judgments into final verdict using majority voting.
    """

    verdicts = [j["verdict"] for j in judgments]

    # Count wins
    gemini_wins = sum(1 for j in judgments if
        (j["verdict"] == "A_WINS" and j["gemini_position"] == "A") or
        (j["verdict"] == "B_WINS" and j["gemini_position"] == "B")
    )
    competitor_wins = sum(1 for j in judgments if
        (j["verdict"] == "A_WINS" and j["gemini_position"] == "B") or
        (j["verdict"] == "B_WINS" and j["gemini_position"] == "A")
    )
    ties = sum(1 for j in judgments if j["verdict"] == "TIE")

    # Majority decision
    if gemini_wins >= 3:
        final_verdict = "GEMINI_WINS"
    elif competitor_wins >= 3:
        final_verdict = "COMPETITOR_WINS"
    else:
        final_verdict = "TIE"

    # Calculate agreement score
    max_agreement = max(gemini_wins, competitor_wins, ties)
    agreement_score = max_agreement / 5.0

    return {
        "final_verdict": final_verdict,
        "gemini_wins": gemini_wins,
        "competitor_wins": competitor_wins,
        "ties": ties,
        "agreement_score": agreement_score,
        "individual_judgments": judgments
    }
```

### 6.5 Best of 5 Judging Pipeline

```python
async def run_best_of_5_judgment(
    client: OpenRouterClient,
    prompt: WritingPrompt,
    gemini_response: str,
    competitor_response: str,
    competitor_name: str,
    judge_model: str = "anthropic/claude-opus-4-5"
) -> Dict:
    """Run 5 independent judgments with position shuffling."""

    judgments = []

    for run in range(5):
        # Shuffle positions
        response_a, response_b, gemini_position = shuffle_responses(
            gemini_response, competitor_response, prompt.prompt_id, run
        )

        # Run expert judge
        expert_result = await run_single_judgment(
            client, judge_model,
            EXPERT_WRITER_PROMPT,
            EXPERT_EVALUATION_TEMPLATE.format(
                task_description=prompt.prompt_text,
                context=prompt.context_description or "None provided",
                response_a=response_a,
                response_b=response_b
            )
        )

        # Run recipient judge
        recipient_persona = generate_recipient_persona(prompt)
        recipient_result = await run_single_judgment(
            client, judge_model,
            recipient_persona,
            EXPERT_EVALUATION_TEMPLATE.format(
                task_description=prompt.prompt_text,
                context=prompt.context_description or "None provided",
                response_a=response_a,
                response_b=response_b
            )
        )

        # Combine judge verdicts (both must agree for strong signal)
        combined_verdict = combine_judge_verdicts(expert_result, recipient_result)

        judgments.append({
            "run": run,
            "gemini_position": gemini_position,
            "expert_verdict": expert_result["verdict"],
            "recipient_verdict": recipient_result["verdict"],
            "combined_verdict": combined_verdict,
            "expert_reasoning": expert_result["reasoning"],
            "recipient_reasoning": recipient_result["reasoning"],
            "verdict": combined_verdict
        })

    return aggregate_judgments(judgments)
```

---

## 7. Database Schema

### 7.1 SQLite Schema Definition

```sql
-- schema.sql - Complete database schema for writing evaluation framework

-- Occupations from O*NET
CREATE TABLE occupations (
    onet_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    writing_importance_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Writing tasks extracted from O*NET
CREATE TABLE writing_tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    onet_code TEXT REFERENCES occupations(onet_code),
    task_description TEXT NOT NULL,
    task_category TEXT,  -- email, report, proposal, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated evaluation prompts
CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    onet_code TEXT REFERENCES occupations(onet_code),
    task_id INTEGER REFERENCES writing_tasks(task_id),
    industry TEXT NOT NULL,
    company_context TEXT,
    writing_type TEXT NOT NULL,
    complexity TEXT CHECK(complexity IN ('simple', 'moderate', 'complex')),
    prompt_text TEXT NOT NULL,
    context_required BOOLEAN DEFAULT FALSE,
    context_json TEXT,  -- JSON blob with generated context
    target_recipient TEXT,
    word_count_guidance TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model responses
CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    model_key TEXT NOT NULL,
    model_display_name TEXT NOT NULL,
    response_text TEXT,
    tokens_used INTEGER,
    latency_seconds REAL,
    finish_reason TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pairwise comparisons
CREATE TABLE comparisons (
    comparison_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    gemini_response_id INTEGER REFERENCES responses(response_id),
    competitor_response_id INTEGER REFERENCES responses(response_id),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Individual judgments (5 per comparison per judge type)
CREATE TABLE judgments (
    judgment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER REFERENCES comparisons(comparison_id),
    run_number INTEGER CHECK(run_number BETWEEN 0 AND 4),
    judge_type TEXT CHECK(judge_type IN ('expert', 'recipient')),
    judge_model TEXT NOT NULL,
    gemini_position TEXT CHECK(gemini_position IN ('A', 'B')),
    verdict TEXT CHECK(verdict IN ('A_WINS', 'B_WINS', 'TIE')),
    confidence TEXT CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    reasoning TEXT,
    full_analysis TEXT,
    rubric_scores_json TEXT,  -- JSON with per-criterion scores
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated comparison results
CREATE TABLE comparison_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER UNIQUE REFERENCES comparisons(comparison_id),
    final_verdict TEXT CHECK(final_verdict IN ('GEMINI_WINS', 'COMPETITOR_WINS', 'TIE')),
    gemini_win_count INTEGER,
    competitor_win_count INTEGER,
    tie_count INTEGER,
    agreement_score REAL,
    expert_agreement_score REAL,
    recipient_agreement_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregate statistics by model pair
CREATE TABLE model_pair_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gemini_model TEXT NOT NULL,
    competitor_model TEXT NOT NULL,
    total_comparisons INTEGER,
    gemini_wins INTEGER,
    competitor_wins INTEGER,
    ties INTEGER,
    gemini_win_rate REAL,
    avg_agreement_score REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gemini_model, competitor_model)
);

-- Indexes for common queries
CREATE INDEX idx_prompts_occupation ON prompts(onet_code);
CREATE INDEX idx_prompts_complexity ON prompts(complexity);
CREATE INDEX idx_prompts_writing_type ON prompts(writing_type);
CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model_key);
CREATE INDEX idx_comparisons_status ON comparisons(status);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
CREATE INDEX idx_comparison_results_verdict ON comparison_results(final_verdict);

-- Views for common analyses
CREATE VIEW v_full_comparison AS
SELECT
    c.comparison_id,
    p.prompt_id,
    p.prompt_text,
    p.industry,
    p.writing_type,
    p.complexity,
    o.title as occupation_title,
    c.gemini_model,
    c.competitor_model,
    gr.response_text as gemini_response,
    cr.response_text as competitor_response,
    r.final_verdict,
    r.agreement_score
FROM comparisons c
JOIN prompts p ON c.prompt_id = p.prompt_id
JOIN occupations o ON p.onet_code = o.onet_code
LEFT JOIN responses gr ON c.gemini_response_id = gr.response_id
LEFT JOIN responses cr ON c.competitor_response_id = cr.response_id
LEFT JOIN comparison_results r ON c.comparison_id = r.comparison_id;

CREATE VIEW v_win_rates_by_category AS
SELECT
    c.gemini_model,
    c.competitor_model,
    p.writing_type,
    p.complexity,
    COUNT(*) as total,
    SUM(CASE WHEN cr.final_verdict = 'GEMINI_WINS' THEN 1 ELSE 0 END) as gemini_wins,
    SUM(CASE WHEN cr.final_verdict = 'COMPETITOR_WINS' THEN 1 ELSE 0 END) as competitor_wins,
    ROUND(100.0 * SUM(CASE WHEN cr.final_verdict = 'GEMINI_WINS' THEN 1 ELSE 0 END) / COUNT(*), 2) as gemini_win_rate
FROM comparisons c
JOIN prompts p ON c.prompt_id = p.prompt_id
JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
GROUP BY c.gemini_model, c.competitor_model, p.writing_type, p.complexity;
```

---

## 8. Execution Pipeline

### 8.1 Pipeline Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  O*NET Download │────▶│ Task Extraction │────▶│ Prompt Generation│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Analysis     │◀────│    Judging      │◀────│ Response Gen    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Report Gen     │
└─────────────────┘
```

### 8.2 Main Execution Script

```python
#!/usr/bin/env python3
"""
run_eval.py - Main execution script for writing evaluation
"""

import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime

from src.data.onet_pipeline import download_onet, extract_writing_tasks
from src.prompts.generator import PromptGenerator
from src.models.openrouter_client import RateLimitedClient
from src.evaluation.judge import JudgeRunner
from src.analysis.aggregator import ResultsAggregator
from src.reports.pdf_generator import ReportGenerator
from src.db.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_full_pipeline(config: dict):
    """Execute the complete evaluation pipeline."""

    db = Database(config["db_path"])
    client = RateLimitedClient(config["openrouter_api_key"])

    # Phase 1: Data preparation
    logger.info("Phase 1: Downloading and processing O*NET data...")
    onet_dir = download_onet()
    occupations = extract_writing_tasks(onet_dir)
    db.insert_occupations(occupations)

    # Phase 2: Prompt generation
    logger.info("Phase 2: Generating evaluation prompts...")
    generator = PromptGenerator(db)
    prompts = generator.generate_all_prompts(
        prompts_per_occupation=config["prompts_per_occupation"],
        complexity_distribution=config["complexity_distribution"]
    )
    db.insert_prompts(prompts)

    # Phase 3: Response generation
    logger.info("Phase 3: Generating model responses...")
    for gemini_model in config["gemini_models"]:
        for competitor_model in config["competitor_models"]:
            logger.info(f"Running {gemini_model} vs {competitor_model}")

            pending_prompts = db.get_pending_prompts(gemini_model, competitor_model)

            for prompt in pending_prompts:
                # Generate responses from both models
                responses = await client.generate_pairwise(
                    gemini_model, competitor_model,
                    prompt.prompt_text, prompt.context_json
                )

                # Store responses
                gemini_resp_id = db.insert_response(prompt.prompt_id, gemini_model, responses["gemini"])
                comp_resp_id = db.insert_response(prompt.prompt_id, competitor_model, responses["competitor"])

                # Create comparison record
                db.create_comparison(prompt.prompt_id, gemini_model, competitor_model,
                                   gemini_resp_id, comp_resp_id)

    # Phase 4: Judging
    logger.info("Phase 4: Running judges...")
    judge = JudgeRunner(client, config["judge_model"])

    pending_comparisons = db.get_pending_comparisons()
    for comparison in pending_comparisons:
        result = await judge.run_best_of_5_judgment(
            comparison.prompt,
            comparison.gemini_response,
            comparison.competitor_response,
            comparison.competitor_model
        )
        db.store_judgment_result(comparison.comparison_id, result)

    # Phase 5: Analysis
    logger.info("Phase 5: Aggregating results...")
    aggregator = ResultsAggregator(db)
    aggregator.compute_all_statistics()

    # Phase 6: Report generation
    logger.info("Phase 6: Generating reports...")
    report_gen = ReportGenerator(db, config["output_dir"])
    report_gen.generate_csv_exports()
    report_gen.generate_visualizations()
    report_gen.generate_pdf_report()

    logger.info("Pipeline complete!")

def main():
    parser = argparse.ArgumentParser(description="Run writing evaluation pipeline")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--phase", type=str, choices=["all", "data", "prompts", "responses", "judge", "analyze", "report"])
    args = parser.parse_args()

    config = load_config(args.config)
    asyncio.run(run_full_pipeline(config))

if __name__ == "__main__":
    main()
```

### 8.3 Configuration File

```yaml
# config.yaml - Pipeline configuration

# API Configuration
openrouter_api_key: "${OPENROUTER_API_KEY}"
rate_limit_rpm: 60

# Database
db_path: "data/eval.db"
output_dir: "output"

# Models to evaluate
gemini_models:
  - "gemini-pro"
  - "gemini-flash"

competitor_models:
  - "gpt-5.2"
  - "claude-opus"
  - "grok-3"
  - "kimi-2"
  - "llama-4"

# Judge configuration
judge_model: "anthropic/claude-opus-4-5"

# Prompt generation
prompts_per_occupation: 10
complexity_distribution:
  simple: 0.30
  moderate: 0.45
  complex: 0.25

# Sampling (for testing)
sample_occupations: null  # Set to number for testing subset
sample_prompts: null
```

---

## 9. Analysis & Reporting

### 9.1 Statistical Analysis

```python
"""
src/analysis/statistics.py - Statistical analysis functions
"""

import numpy as np
from scipy import stats
import pandas as pd
from typing import Dict, List

def compute_win_rate_with_ci(wins: int, total: int, confidence: float = 0.95) -> Dict:
    """Compute win rate with Wilson score confidence interval."""

    if total == 0:
        return {"win_rate": 0, "ci_lower": 0, "ci_upper": 0}

    p = wins / total
    z = stats.norm.ppf((1 + confidence) / 2)

    # Wilson score interval
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    spread = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

    return {
        "win_rate": p,
        "ci_lower": max(0, center - spread),
        "ci_upper": min(1, center + spread),
        "n": total
    }

def compute_pairwise_significance(
    gemini_wins: int,
    competitor_wins: int,
    ties: int
) -> Dict:
    """Test if difference between models is statistically significant."""

    total = gemini_wins + competitor_wins + ties

    # Exclude ties for head-to-head comparison
    decisive = gemini_wins + competitor_wins

    if decisive < 10:
        return {"significant": False, "reason": "insufficient_data", "p_value": None}

    # Binomial test
    p_value = stats.binomtest(gemini_wins, decisive, 0.5).pvalue

    return {
        "significant": p_value < 0.05,
        "p_value": p_value,
        "effect_size": (gemini_wins - competitor_wins) / decisive if decisive > 0 else 0,
        "decisive_comparisons": decisive
    }

def segment_analysis(df: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    """Analyze win rates by segment (e.g., writing_type, complexity)."""

    results = []
    for segment_value in df[segment_col].unique():
        segment_data = df[df[segment_col] == segment_value]

        gemini_wins = (segment_data["final_verdict"] == "GEMINI_WINS").sum()
        competitor_wins = (segment_data["final_verdict"] == "COMPETITOR_WINS").sum()
        ties = (segment_data["final_verdict"] == "TIE").sum()
        total = len(segment_data)

        win_stats = compute_win_rate_with_ci(gemini_wins, total)
        sig_stats = compute_pairwise_significance(gemini_wins, competitor_wins, ties)

        results.append({
            "segment": segment_value,
            "total": total,
            "gemini_wins": gemini_wins,
            "competitor_wins": competitor_wins,
            "ties": ties,
            "gemini_win_rate": win_stats["win_rate"],
            "ci_lower": win_stats["ci_lower"],
            "ci_upper": win_stats["ci_upper"],
            "p_value": sig_stats["p_value"],
            "significant": sig_stats["significant"]
        })

    return pd.DataFrame(results)
```

### 9.2 Visualizations

```python
"""
src/analysis/visualizations.py - Generate analysis visualizations
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path

def plot_win_rate_heatmap(db, output_dir: Path):
    """Generate heatmap of win rates across model pairs."""

    df = pd.read_sql("""
        SELECT gemini_model, competitor_model, gemini_win_rate
        FROM model_pair_stats
    """, db.conn)

    pivot = df.pivot(index="gemini_model", columns="competitor_model", values="gemini_win_rate")

    plt.figure(figsize=(12, 8))
    sns.heatmap(pivot, annot=True, fmt=".1%", cmap="RdYlGn", center=0.5,
                vmin=0.3, vmax=0.7)
    plt.title("Gemini Win Rates vs Competitors")
    plt.tight_layout()
    plt.savefig(output_dir / "win_rate_heatmap.png", dpi=150)
    plt.close()

def plot_win_rates_by_writing_type(db, output_dir: Path):
    """Bar chart of win rates by writing type."""

    df = pd.read_sql("""
        SELECT writing_type, competitor_model, gemini_win_rate, total
        FROM v_win_rates_by_category
        WHERE gemini_model = 'gemini-pro'
    """, db.conn)

    plt.figure(figsize=(14, 8))

    writing_types = df["writing_type"].unique()
    x = np.arange(len(writing_types))
    width = 0.15

    competitors = df["competitor_model"].unique()
    for i, comp in enumerate(competitors):
        comp_data = df[df["competitor_model"] == comp]
        rates = [comp_data[comp_data["writing_type"] == wt]["gemini_win_rate"].values[0]
                 if len(comp_data[comp_data["writing_type"] == wt]) > 0 else 0
                 for wt in writing_types]
        plt.bar(x + i * width, rates, width, label=f"vs {comp}")

    plt.xlabel("Writing Type")
    plt.ylabel("Gemini Win Rate")
    plt.title("Gemini Pro Win Rates by Writing Type and Competitor")
    plt.xticks(x + width * 2, writing_types, rotation=45)
    plt.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_dir / "win_rates_by_writing_type.png", dpi=150)
    plt.close()

def plot_complexity_analysis(db, output_dir: Path):
    """Show how win rates vary by task complexity."""

    df = pd.read_sql("""
        SELECT complexity, competitor_model, gemini_win_rate
        FROM v_win_rates_by_category
        WHERE gemini_model = 'gemini-pro'
    """, db.conn)

    plt.figure(figsize=(10, 6))

    complexity_order = ["simple", "moderate", "complex"]

    for comp in df["competitor_model"].unique():
        comp_data = df[df["competitor_model"] == comp]
        rates = [comp_data[comp_data["complexity"] == c]["gemini_win_rate"].values[0]
                 for c in complexity_order]
        plt.plot(complexity_order, rates, marker='o', label=f"vs {comp}", linewidth=2)

    plt.xlabel("Task Complexity")
    plt.ylabel("Gemini Win Rate")
    plt.title("Gemini Pro Performance by Task Complexity")
    plt.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "complexity_analysis.png", dpi=150)
    plt.close()
```

### 9.3 PDF Report Generation

```python
"""
src/reports/pdf_generator.py - Generate final PDF report
"""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from pathlib import Path
import pandas as pd

class ReportGenerator:
    def __init__(self, db, output_dir: str):
        self.db = db
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pdf_report(self):
        """Generate comprehensive PDF report."""

        doc = SimpleDocTemplate(
            str(self.output_dir / "gemini_writing_eval_report.pdf"),
            pagesize=letter
        )

        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph("Gemini Writing Evaluation Report", styles["Title"]))
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("Executive Summary", styles["Heading1"]))
        story.append(Paragraph(self._generate_executive_summary(), styles["Normal"]))
        story.append(Spacer(1, 20))

        # Overall Results
        story.append(Paragraph("Overall Results", styles["Heading1"]))
        story.append(self._create_overall_results_table())
        story.append(Spacer(1, 20))

        # Add visualizations
        story.append(Paragraph("Win Rate Analysis", styles["Heading1"]))
        story.append(Image(str(self.output_dir / "win_rate_heatmap.png"), width=450, height=300))
        story.append(PageBreak())

        # Detailed Analysis by Writing Type
        story.append(Paragraph("Analysis by Writing Type", styles["Heading1"]))
        story.append(Image(str(self.output_dir / "win_rates_by_writing_type.png"), width=500, height=300))
        story.append(Spacer(1, 20))

        # Complexity Analysis
        story.append(Paragraph("Performance by Task Complexity", styles["Heading1"]))
        story.append(Image(str(self.output_dir / "complexity_analysis.png"), width=450, height=270))
        story.append(PageBreak())

        # Identified Weaknesses
        story.append(Paragraph("Gemini Specific Weaknesses", styles["Heading1"]))
        story.append(Paragraph(self._identify_weaknesses(), styles["Normal"]))
        story.append(Spacer(1, 20))

        # Methodology
        story.append(Paragraph("Methodology", styles["Heading1"]))
        story.append(Paragraph(self._methodology_description(), styles["Normal"]))

        doc.build(story)

    def _identify_weaknesses(self) -> str:
        """Analyze results to identify specific Gemini weaknesses."""

        # Find segments where Gemini significantly underperforms
        df = pd.read_sql("""
            SELECT
                competitor_model,
                writing_type,
                complexity,
                gemini_win_rate,
                total
            FROM v_win_rates_by_category
            WHERE gemini_win_rate < 0.45 AND total >= 20
            ORDER BY gemini_win_rate ASC
        """, self.db.conn)

        weaknesses = []

        for _, row in df.iterrows():
            weaknesses.append(
                f"- vs {row['competitor_model']} on {row['writing_type']} "
                f"({row['complexity']} complexity): {row['gemini_win_rate']:.1%} win rate"
            )

        if not weaknesses:
            return "No significant weaknesses identified where Gemini win rate < 45% with sufficient sample size."

        return "Key areas where Gemini underperforms:\n\n" + "\n".join(weaknesses[:10])

    def generate_csv_exports(self):
        """Export all analysis tables to CSV."""

        exports = [
            ("overall_results.csv", "SELECT * FROM model_pair_stats"),
            ("by_writing_type.csv", "SELECT * FROM v_win_rates_by_category"),
            ("all_comparisons.csv", "SELECT * FROM v_full_comparison"),
            ("all_judgments.csv", "SELECT * FROM judgments"),
        ]

        for filename, query in exports:
            df = pd.read_sql(query, self.db.conn)
            df.to_csv(self.output_dir / filename, index=False)
```

### 9.4 Fine-Grained Eval Viewer

```python
"""
src/viewer/eval_viewer.py - Terminal-based evaluation viewer
"""

import sqlite3
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

class EvalViewer:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.console = Console()

    def view_comparison(self, comparison_id: int):
        """View detailed comparison with all judgments."""

        # Get comparison details
        comp = self.conn.execute("""
            SELECT * FROM v_full_comparison WHERE comparison_id = ?
        """, (comparison_id,)).fetchone()

        if not comp:
            self.console.print(f"[red]Comparison {comparison_id} not found[/red]")
            return

        # Display prompt
        self.console.print(Panel(comp["prompt_text"], title="Prompt", border_style="blue"))

        # Display responses side by side
        table = Table(title="Responses", show_header=True)
        table.add_column("Gemini", width=50)
        table.add_column("Competitor", width=50)
        table.add_row(
            comp["gemini_response"][:500] + "...",
            comp["competitor_response"][:500] + "..."
        )
        self.console.print(table)

        # Display judgments
        judgments = self.conn.execute("""
            SELECT * FROM judgments WHERE comparison_id = ?
            ORDER BY run_number, judge_type
        """, (comparison_id,)).fetchall()

        self.console.print("\n[bold]Judgments:[/bold]")
        for j in judgments:
            verdict_color = "green" if "GEMINI" in j["verdict"] else "red" if "COMPETITOR" in j["verdict"] else "yellow"
            self.console.print(
                f"  Run {j['run_number']} ({j['judge_type']}): "
                f"[{verdict_color}]{j['verdict']}[/{verdict_color}] "
                f"(Gemini was {j['gemini_position']})"
            )

        # Final result
        self.console.print(f"\n[bold]Final Verdict: {comp['final_verdict']}[/bold]")
        self.console.print(f"Agreement Score: {comp['agreement_score']:.2f}")

    def search_comparisons(self, **filters):
        """Search comparisons with filters."""

        query = "SELECT * FROM v_full_comparison WHERE 1=1"
        params = []

        if "occupation" in filters:
            query += " AND occupation_title LIKE ?"
            params.append(f"%{filters['occupation']}%")

        if "writing_type" in filters:
            query += " AND writing_type = ?"
            params.append(filters["writing_type"])

        if "verdict" in filters:
            query += " AND final_verdict = ?"
            params.append(filters["verdict"])

        if "competitor" in filters:
            query += " AND competitor_model = ?"
            params.append(filters["competitor"])

        results = self.conn.execute(query, params).fetchall()

        table = Table(title=f"Found {len(results)} comparisons")
        table.add_column("ID")
        table.add_column("Occupation")
        table.add_column("Type")
        table.add_column("Competitor")
        table.add_column("Verdict")

        for r in results[:50]:
            table.add_row(
                str(r["comparison_id"]),
                r["occupation_title"][:30],
                r["writing_type"],
                r["competitor_model"],
                r["final_verdict"]
            )

        self.console.print(table)
```

---

## 10. Quality Assurance

### 10.1 Data Validation

```python
"""
src/qa/validators.py - Data validation functions
"""

def validate_prompt(prompt: WritingPrompt) -> List[str]:
    """Validate a generated prompt for quality issues."""

    issues = []

    # Check prompt length
    if len(prompt.prompt_text) < 50:
        issues.append("Prompt too short (< 50 chars)")
    if len(prompt.prompt_text) > 5000:
        issues.append("Prompt too long (> 5000 chars)")

    # Check for placeholder text
    placeholders = ["{", "}", "TODO", "PLACEHOLDER", "XXX"]
    for ph in placeholders:
        if ph in prompt.prompt_text:
            issues.append(f"Contains placeholder: {ph}")

    # Check context consistency
    if prompt.context_required and not prompt.context_json:
        issues.append("Context required but not provided")

    return issues

def validate_response(response: Dict) -> List[str]:
    """Validate a model response."""

    issues = []

    if not response.get("success"):
        issues.append(f"Generation failed: {response.get('error')}")
        return issues

    content = response.get("content", "")

    if len(content) < 50:
        issues.append("Response too short")

    # Check for refusals
    refusal_patterns = [
        "I cannot", "I'm not able to", "I apologize, but",
        "As an AI", "I don't have the ability"
    ]
    for pattern in refusal_patterns:
        if pattern.lower() in content.lower():
            issues.append(f"Possible refusal detected: {pattern}")

    return issues

def validate_judgment(judgment: Dict) -> List[str]:
    """Validate a judgment for quality."""

    issues = []

    # Check verdict is valid
    if judgment.get("verdict") not in ["A_WINS", "B_WINS", "TIE"]:
        issues.append(f"Invalid verdict: {judgment.get('verdict')}")

    # Check reasoning is substantive
    reasoning = judgment.get("reasoning", "")
    if len(reasoning) < 100:
        issues.append("Reasoning too brief")

    # Check for analysis of both responses
    analysis = judgment.get("full_analysis", "")
    if "Response A" not in analysis or "Response B" not in analysis:
        issues.append("Analysis doesn't discuss both responses")

    return issues
```

### 10.2 Position Bias Detection

```python
def detect_position_bias(judgments: List[Dict]) -> Dict:
    """Analyze judgments for systematic position bias."""

    a_wins = sum(1 for j in judgments if j["verdict"] == "A_WINS")
    b_wins = sum(1 for j in judgments if j["verdict"] == "B_WINS")
    total = len(judgments)

    # Binomial test for position bias
    if total > 100:
        p_value = stats.binomtest(a_wins, a_wins + b_wins, 0.5).pvalue

        return {
            "a_win_rate": a_wins / total,
            "b_win_rate": b_wins / total,
            "bias_detected": p_value < 0.05,
            "p_value": p_value,
            "recommendation": "Review shuffling implementation" if p_value < 0.05 else "No action needed"
        }

    return {"bias_detected": False, "reason": "Insufficient data"}
```

### 10.3 Judge Consistency Checks

```python
def check_judge_consistency(comparison_id: int, db) -> Dict:
    """Check if expert and recipient judges are reasonably consistent."""

    judgments = db.get_judgments_for_comparison(comparison_id)

    expert_verdicts = [j["verdict"] for j in judgments if j["judge_type"] == "expert"]
    recipient_verdicts = [j["verdict"] for j in judgments if j["judge_type"] == "recipient"]

    # Check agreement
    agreements = sum(1 for e, r in zip(expert_verdicts, recipient_verdicts) if e == r)
    agreement_rate = agreements / len(expert_verdicts) if expert_verdicts else 0

    return {
        "agreement_rate": agreement_rate,
        "concerning": agreement_rate < 0.4,  # Less than 40% agreement is concerning
        "expert_verdicts": expert_verdicts,
        "recipient_verdicts": recipient_verdicts
    }
```

### 10.4 Sample Audit Process

```python
def generate_audit_sample(db, sample_size: int = 100) -> List[int]:
    """Generate random sample of comparisons for human audit."""

    # Stratified sampling across:
    # - Model pairs
    # - Writing types
    # - Verdicts (oversample close calls)

    comparison_ids = db.execute("""
        SELECT comparison_id, agreement_score
        FROM comparison_results
        ORDER BY
            CASE WHEN agreement_score < 0.8 THEN 0 ELSE 1 END,  -- Prioritize close calls
            RANDOM()
        LIMIT ?
    """, (sample_size,)).fetchall()

    return [c[0] for c in comparison_ids]

def format_audit_sheet(db, comparison_ids: List[int], output_path: str):
    """Generate audit sheet for human review."""

    records = []
    for comp_id in comparison_ids:
        comp = db.get_full_comparison(comp_id)
        records.append({
            "comparison_id": comp_id,
            "prompt": comp["prompt_text"],
            "response_a": comp["gemini_response"] if comp["gemini_position"] == "A" else comp["competitor_response"],
            "response_b": comp["competitor_response"] if comp["gemini_position"] == "A" else comp["gemini_response"],
            "system_verdict": comp["final_verdict"],
            "human_verdict": "",  # To be filled
            "notes": ""
        })

    pd.DataFrame(records).to_csv(output_path, index=False)
```

---

## Appendix A: Project Structure

```
JTBD-writing/
├── config.yaml
├── requirements.txt
├── run_eval.py
├── data/
│   ├── onet/                    # Downloaded O*NET data
│   └── eval.db                  # SQLite database
├── src/
│   ├── data/
│   │   ├── onet_pipeline.py
│   │   └── extract_writing_tasks.py
│   ├── prompts/
│   │   ├── generator.py
│   │   └── templates.py
│   ├── context/
│   │   └── generator.py
│   ├── models/
│   │   └── openrouter_client.py
│   ├── evaluation/
│   │   ├── judge.py
│   │   ├── rubrics.py
│   │   └── aggregator.py
│   ├── analysis/
│   │   ├── statistics.py
│   │   └── visualizations.py
│   ├── reports/
│   │   └── pdf_generator.py
│   ├── viewer/
│   │   └── eval_viewer.py
│   ├── db/
│   │   └── database.py
│   └── qa/
│       └── validators.py
├── scripts/
│   ├── download_onet.py
│   ├── setup_db.py
│   └── run_audit.py
├── output/
│   ├── *.csv
│   ├── *.png
│   └── gemini_writing_eval_report.pdf
└── tests/
    └── ...
```

---

## Appendix B: Requirements

```
# requirements.txt
openai>=1.0.0
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
matplotlib>=3.7.0
seaborn>=0.12.0
reportlab>=4.0.0
rich>=13.0.0
pyyaml>=6.0.0
openpyxl>=3.1.0
tenacity>=8.2.0
aiohttp>=3.8.0
pytest>=7.3.0
```

---

## Appendix C: Estimated Scale

| Metric | Estimate |
|--------|----------|
| Writing-related occupations | ~700 |
| Prompts per occupation | 10 |
| Total prompts | ~7,000 |
| Model pairs (2 Gemini x 6 competitors) | 12 |
| Total comparisons | ~84,000 |
| Judgments (5 per comparison x 2 judges) | ~840,000 |
| Estimated API cost | $15,000-25,000 |
| Estimated runtime | 5-7 days |

---

This plan provides a complete, production-ready framework for evaluating Gemini's writing capabilities against frontier competitors across the full breadth of the US economy's writing needs.
