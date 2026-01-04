# Gemini Writing Evaluation Framework: Master Implementation Plan

## Executive Summary

This document outlines a comprehensive framework for evaluating writing capabilities across frontier LLMs (Gemini 3.0 Pro, Gemini 3.0 Flash, GPT-5.2, Claude Opus, Grok, Kimi, etc.) using realistic writing tasks derived from the US economy's occupational landscape. The evaluation employs rigorous methodology including pairwise comparisons, dual-persona judging, position shuffling, and best-of-5 aggregation to produce statistically robust results.

---

## 1. O*NET Data Pipeline

### 1.1 Overview

The O*NET (Occupational Information Network) database provides comprehensive occupational data for over 1,000 occupations in the US economy. We will extract writing-related tasks, work activities, and context to generate realistic evaluation prompts.

### 1.2 Data Download Script

```python
#!/usr/bin/env python3
"""
onet_downloader.py - Downloads and extracts O*NET database files
"""

import os
import requests
import zipfile
from pathlib import Path

ONET_VERSION = "29_1"  # Update as needed
BASE_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION}_text.zip"
DATA_DIR = Path("data/onet")

def download_onet():
    """Download the latest O*NET database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / f"onet_{ONET_VERSION}.zip"

    if not zip_path.exists():
        print(f"Downloading O*NET {ONET_VERSION}...")
        response = requests.get(BASE_URL, stream=True)
        response.raise_for_status()

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    # Extract
    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(DATA_DIR)

    print(f"O*NET data extracted to {DATA_DIR}")

if __name__ == "__main__":
    download_onet()
```

### 1.3 Key O*NET Files to Parse

| File | Purpose |
|------|---------|
| `Occupation Data.txt` | Master list of all occupations with titles |
| `Task Statements.txt` | Specific tasks performed in each occupation |
| `Work Activities.txt` | Generalized work activities (includes writing indicators) |
| `Skills.txt` | Required skills including "Writing" skill ratings |
| `Knowledge.txt` | Domain knowledge requirements |
| `Work Context.txt` | Working conditions and communication requirements |

### 1.4 Writing Task Extraction Logic

```python
#!/usr/bin/env python3
"""
extract_writing_tasks.py - Identifies writing-related occupations and tasks
"""

import pandas as pd
from pathlib import Path
import re

class OnetWritingExtractor:
    WRITING_KEYWORDS = [
        r'\bwrit(e|ing|ten)\b', r'\bdraft(ing)?\b', r'\bcompos(e|ing)\b',
        r'\bdocument(ation|ing)?\b', r'\breport(s|ing)?\b', r'\bcorrespond(ence)?\b',
        r'\bemail\b', r'\bmemo(s)?\b', r'\bletter(s)?\b', r'\bproposal(s)?\b',
        r'\bpresentation(s)?\b', r'\bcommunicat(e|ion|ing)\b', r'\brecord(s|ing)?\b',
        r'\bprepare.*statement', r'\bcreate.*content', r'\bauthor(ing)?\b'
    ]

    def __init__(self, onet_dir: Path):
        self.onet_dir = onet_dir
        self.occupations = None
        self.tasks = None
        self.skills = None

    def load_data(self):
        """Load relevant O*NET tables."""
        self.occupations = pd.read_csv(
            self.onet_dir / "Occupation Data.txt",
            sep='\t', encoding='utf-8'
        )
        self.tasks = pd.read_csv(
            self.onet_dir / "Task Statements.txt",
            sep='\t', encoding='utf-8'
        )
        self.skills = pd.read_csv(
            self.onet_dir / "Skills.txt",
            sep='\t', encoding='utf-8'
        )
        self.work_activities = pd.read_csv(
            self.onet_dir / "Work Activities.txt",
            sep='\t', encoding='utf-8'
        )

    def identify_writing_intensive_occupations(self) -> pd.DataFrame:
        """
        Identify occupations with significant writing requirements.
        Uses skill ratings and work activity scores.
        """
        # Filter for "Writing" skill (Element ID: 2.A.1.a)
        writing_skill = self.skills[
            self.skills['Element ID'] == '2.A.1.a'
        ].copy()

        # Filter for "Documenting/Recording Information" activity
        doc_activity = self.work_activities[
            self.work_activities['Element ID'] == '4.A.3.b.1'
        ].copy()

        # Merge and rank
        occ_writing = writing_skill.merge(
            self.occupations[['O*NET-SOC Code', 'Title']],
            on='O*NET-SOC Code'
        )

        # Filter occupations with writing skill importance >= 3.0 (scale 1-5)
        high_writing = occ_writing[
            occ_writing['Data Value'] >= 3.0
        ].sort_values('Data Value', ascending=False)

        return high_writing

    def extract_writing_tasks(self, occupation_code: str) -> list:
        """Extract writing-related tasks for a specific occupation."""
        occ_tasks = self.tasks[
            self.tasks['O*NET-SOC Code'] == occupation_code
        ]

        writing_tasks = []
        pattern = '|'.join(self.WRITING_KEYWORDS)

        for _, row in occ_tasks.iterrows():
            task_text = row['Task']
            if re.search(pattern, task_text, re.IGNORECASE):
                writing_tasks.append({
                    'task_id': row['Task ID'],
                    'task': task_text,
                    'occupation_code': occupation_code
                })

        return writing_tasks

    def build_writing_task_corpus(self) -> pd.DataFrame:
        """Build complete corpus of writing tasks across all occupations."""
        high_writing_occs = self.identify_writing_intensive_occupations()

        all_tasks = []
        for _, row in high_writing_occs.iterrows():
            occ_code = row['O*NET-SOC Code']
            occ_title = row['Title']
            tasks = self.extract_writing_tasks(occ_code)

            for task in tasks:
                task['occupation_title'] = occ_title
                task['writing_skill_level'] = row['Data Value']
                all_tasks.append(task)

        return pd.DataFrame(all_tasks)
```

### 1.5 Expected Coverage

Based on O*NET analysis, we expect to cover:
- **~450 occupations** with significant writing requirements (skill level >= 3.0)
- **~2,500 distinct writing tasks** across these occupations
- **23 major occupation groups** including:
  - Management (11-XXXX)
  - Business/Financial (13-XXXX)
  - Healthcare (29-XXXX)
  - Legal (23-XXXX)
  - Education (25-XXXX)
  - Arts/Media (27-XXXX)

---

## 2. Eval Prompt Generation

### 2.1 Prompt Generation Architecture

We generate prompts by combining:
1. **O*NET Task Statement** - The base writing task
2. **Industry Context** - Specific industry/company type
3. **Scenario Details** - Realistic situational context
4. **Complexity Modifier** - Simple vs. context-rich variants

### 2.2 Industry Diversification Matrix

```python
INDUSTRY_CONTEXTS = {
    "11-1011.00": {  # Chief Executives
        "industries": [
            {"type": "tech_startup", "desc": "Series B AI startup with 85 employees"},
            {"type": "fortune_500", "desc": "Fortune 500 consumer packaged goods company"},
            {"type": "nonprofit", "desc": "National environmental conservation nonprofit"},
            {"type": "healthcare", "desc": "Regional hospital network with 12 facilities"},
            {"type": "manufacturing", "desc": "Family-owned precision manufacturing firm"},
        ]
    },
    "23-1011.00": {  # Lawyers
        "industries": [
            {"type": "biglaw", "desc": "AmLaw 50 corporate law firm"},
            {"type": "public_defender", "desc": "County public defender's office"},
            {"type": "in_house", "desc": "In-house counsel at fintech company"},
            {"type": "solo", "desc": "Solo practitioner family law attorney"},
            {"type": "government", "desc": "Assistant US Attorney"},
        ]
    },
    # ... expanded for all occupation codes
}
```

### 2.3 Prompt Template Structure

```python
PROMPT_TEMPLATES = {
    "simple": {
        "template": """You are a {occupation_title} at a {industry_context}.

Task: {task_statement}

Write the appropriate document/communication to complete this task.""",
        "requires_context": False
    },

    "context_rich": {
        "template": """You are a {occupation_title} at a {industry_context}.

Background Context:
{generated_context}

Current Situation:
{scenario_details}

Task: {task_statement}

Requirements:
- Appropriate tone for the audience
- Professional formatting
- Address all key stakeholders mentioned
- Length appropriate to the communication type

Write the appropriate document/communication to complete this task.""",
        "requires_context": True
    }
}
```

### 2.4 Prompt Generation Pipeline

```python
class PromptGenerator:
    def __init__(self, writing_corpus: pd.DataFrame):
        self.corpus = writing_corpus
        self.context_generator = ContextGenerator()

    def generate_prompt(self, task_row: dict, complexity: str = "simple") -> dict:
        """Generate a complete evaluation prompt."""

        occupation_code = task_row['occupation_code']

        # Select random industry for this occupation
        industry = random.choice(
            INDUSTRY_CONTEXTS.get(occupation_code, DEFAULT_INDUSTRIES)['industries']
        )

        prompt_data = {
            "prompt_id": f"{occupation_code}_{task_row['task_id']}_{complexity}",
            "occupation_code": occupation_code,
            "occupation_title": task_row['occupation_title'],
            "base_task": task_row['task'],
            "industry_type": industry['type'],
            "industry_desc": industry['desc'],
            "complexity": complexity,
        }

        if complexity == "context_rich":
            # Generate synthetic context
            context = self.context_generator.generate(
                occupation=task_row['occupation_title'],
                industry=industry['desc'],
                task=task_row['task']
            )
            prompt_data['context'] = context
            prompt_data['scenario'] = self.context_generator.generate_scenario(
                occupation=task_row['occupation_title'],
                task=task_row['task']
            )

        # Render final prompt
        template = PROMPT_TEMPLATES[complexity]['template']
        prompt_data['rendered_prompt'] = template.format(**prompt_data)

        return prompt_data

    def generate_eval_set(self, n_prompts: int = 1000) -> list:
        """Generate balanced evaluation prompt set."""
        prompts = []

        # Stratified sampling across occupation groups
        for occ_group in self.corpus['occupation_code'].str[:2].unique():
            group_tasks = self.corpus[
                self.corpus['occupation_code'].str.startswith(occ_group)
            ]

            # Sample proportionally
            n_sample = max(5, int(len(group_tasks) / len(self.corpus) * n_prompts))
            sampled = group_tasks.sample(min(n_sample, len(group_tasks)))

            for _, task in sampled.iterrows():
                # 50% simple, 50% context-rich
                complexity = random.choice(["simple", "context_rich"])
                prompts.append(self.generate_prompt(task.to_dict(), complexity))

        return prompts
```

---

## 3. Context Generation

### 3.1 Context Generation Strategy

For context-rich prompts, we need realistic background information. We use a hybrid approach:

1. **Template-based context** - Pre-written scenario templates per occupation
2. **LLM-generated context** - Use a capable model to generate realistic details
3. **Synthetic data generation** - Fake names, companies, dates, figures

### 3.2 Context Generator Implementation

```python
import openai
from faker import Faker

class ContextGenerator:
    def __init__(self):
        self.faker = Faker()
        self.context_model = "gpt-4o-mini"  # Cost-effective for context generation

    def generate(self, occupation: str, industry: str, task: str) -> str:
        """Generate realistic background context for a writing task."""

        prompt = f"""Generate realistic background context for the following scenario.

Occupation: {occupation}
Industry/Organization: {industry}
Writing Task: {task}

Generate 3-4 paragraphs of context including:
- Relevant organizational details
- Key stakeholders involved (use realistic but fictional names)
- Recent events or decisions that make this writing task necessary
- Any constraints or considerations the writer should keep in mind

Keep the context specific and realistic. Include concrete details like dates,
figures, and names where appropriate."""

        response = openai.chat.completions.create(
            model=self.context_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=500
        )

        return response.choices[0].message.content

    def generate_scenario(self, occupation: str, task: str) -> str:
        """Generate specific scenario details."""

        scenarios = {
            "urgent": f"This is time-sensitive and needs to be completed by end of day.",
            "stakeholder": f"Multiple senior stakeholders will review this document.",
            "external": f"This will be shared with external parties and represents the organization.",
            "sensitive": f"This involves confidential information that requires careful handling.",
            "routine": f"This is a routine communication but should maintain professional standards."
        }

        return random.choice(list(scenarios.values()))

    def generate_fake_entities(self) -> dict:
        """Generate realistic fake names, companies, etc."""
        return {
            "person_name": self.faker.name(),
            "company_name": self.faker.company(),
            "address": self.faker.address(),
            "date": self.faker.date_between(start_date='-30d', end_date='+30d'),
            "dollar_amount": f"${self.faker.random_int(1000, 1000000):,}",
            "email": self.faker.company_email(),
        }
```

### 3.3 Context Quality Assurance

```python
def validate_context(context: str) -> bool:
    """Validate generated context meets quality standards."""
    checks = [
        len(context) >= 200,  # Minimum length
        len(context) <= 2000,  # Maximum length
        not any(pii in context.lower() for pii in REAL_PII_PATTERNS),
        context.count('\n') >= 2,  # Multiple paragraphs
    ]
    return all(checks)
```

---

## 4. Model Integration

### 4.1 OpenRouter API Integration

```python
import httpx
import asyncio
from typing import Optional
from dataclasses import dataclass

@dataclass
class ModelConfig:
    model_id: str
    display_name: str
    provider: str
    max_tokens: int = 4096
    temperature: float = 0.7

MODELS = {
    "gemini-3-pro": ModelConfig(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro",
        provider="google"
    ),
    "gemini-3-flash": ModelConfig(
        model_id="google/gemini-3.0-flash",
        display_name="Gemini 3.0 Flash",
        provider="google"
    ),
    "gpt-5.2": ModelConfig(
        model_id="openai/gpt-5.2",
        display_name="GPT-5.2",
        provider="openai"
    ),
    "claude-opus": ModelConfig(
        model_id="anthropic/claude-opus-4",
        display_name="Claude Opus 4",
        provider="anthropic"
    ),
    "grok-3": ModelConfig(
        model_id="x-ai/grok-3",
        display_name="Grok 3",
        provider="xai"
    ),
    "kimi-k2": ModelConfig(
        model_id="moonshot/kimi-k2",
        display_name="Kimi K2",
        provider="moonshot"
    ),
}

class OpenRouterClient:
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://writing-eval.internal",
                "X-Title": "Writing Evaluation Framework"
            },
            timeout=120.0
        )

    async def generate(
        self,
        model_key: str,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> dict:
        """Generate completion from specified model."""

        config = MODELS[model_key]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.post(
            "/chat/completions",
            json={
                "model": config.model_id,
                "messages": messages,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
            }
        )
        response.raise_for_status()

        result = response.json()

        return {
            "model": model_key,
            "content": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
            "latency_ms": response.elapsed.total_seconds() * 1000
        }

    async def generate_pair(
        self,
        model_a: str,
        model_b: str,
        prompt: str
    ) -> tuple:
        """Generate responses from two models concurrently."""

        results = await asyncio.gather(
            self.generate(model_a, prompt),
            self.generate(model_b, prompt)
        )

        return results[0], results[1]
```

### 4.2 Rate Limiting and Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class RateLimitedClient(OpenRouterClient):
    def __init__(self, api_key: str, requests_per_minute: int = 60):
        super().__init__(api_key)
        self.semaphore = asyncio.Semaphore(requests_per_minute // 2)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    async def generate(self, model_key: str, prompt: str, **kwargs):
        async with self.semaphore:
            return await super().generate(model_key, prompt, **kwargs)
```

---

## 5. Judging Framework

### 5.1 Dual-Persona Judging System

Each comparison receives judgments from two distinct perspectives:

#### Expert Writer Persona

```python
EXPERT_WRITER_PROMPT = """You are an expert writing evaluator with 20+ years of experience
assessing professional writing across industries. You have expertise in:
- Business communication and corporate writing
- Technical documentation
- Legal and regulatory writing
- Marketing and persuasive writing
- Academic and research writing

Your evaluation focuses on craft: clarity, structure, style, grammar, and effectiveness
of the writing independent of domain-specific accuracy.

Evaluate the two responses below for the given writing task. Consider:

1. **Clarity** (1-5): Is the writing clear and easy to understand?
2. **Structure** (1-5): Is the document well-organized with logical flow?
3. **Tone** (1-5): Is the tone appropriate for the context and audience?
4. **Conciseness** (1-5): Is the writing appropriately concise without being incomplete?
5. **Professionalism** (1-5): Does the writing meet professional standards?
6. **Task Completion** (1-5): Does the writing fully address the task requirements?

After scoring each criterion, provide an overall preference:
- "A" if Response A is clearly better
- "B" if Response B is clearly better
- "TIE" if they are roughly equivalent

Respond in JSON format:
{
  "scores_a": {"clarity": N, "structure": N, "tone": N, "conciseness": N, "professionalism": N, "task_completion": N},
  "scores_b": {"clarity": N, "structure": N, "tone": N, "conciseness": N, "professionalism": N, "task_completion": N},
  "reasoning": "Brief explanation of your judgment",
  "preference": "A" | "B" | "TIE"
}"""
```

#### Target Recipient Persona (Dynamic)

```python
def generate_recipient_prompt(occupation: str, task: str, industry: str) -> str:
    """Generate task-specific recipient persona prompt."""

    return f"""You are evaluating writing from the perspective of the intended recipient.

Context:
- The writer is a {occupation} working in {industry}
- The writing task was: {task}

As the target recipient of this communication, evaluate which response would be more
effective from YOUR perspective. Consider:

1. **Relevance** (1-5): Does this address what you need to know?
2. **Actionability** (1-5): Can you act on this information?
3. **Credibility** (1-5): Does the writer come across as credible and competent?
4. **Engagement** (1-5): Is this communication engaging and worth your time?
5. **Appropriateness** (1-5): Is this the right format/length/tone for the situation?

After scoring each criterion, provide an overall preference:
- "A" if Response A better serves your needs as the recipient
- "B" if Response B better serves your needs as the recipient
- "TIE" if they are roughly equivalent

Respond in JSON format:
{{
  "scores_a": {{"relevance": N, "actionability": N, "credibility": N, "engagement": N, "appropriateness": N}},
  "scores_b": {{"relevance": N, "actionability": N, "credibility": N, "engagement": N, "appropriateness": N}},
  "reasoning": "Brief explanation from your perspective as recipient",
  "preference": "A" | "B" | "TIE"
}}"""
```

### 5.2 Position Shuffling

```python
import random
import hashlib

class PositionShuffler:
    """Handles randomized position assignment for pairwise comparisons."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def shuffle_pair(
        self,
        response_a: dict,
        response_b: dict,
        prompt_id: str,
        judge_run: int
    ) -> tuple:
        """
        Deterministically shuffle response positions.
        Returns (first_response, second_response, position_map)
        """
        # Create deterministic shuffle based on prompt_id and run number
        shuffle_key = f"{prompt_id}_{judge_run}"
        hash_val = int(hashlib.sha256(shuffle_key.encode()).hexdigest(), 16)

        if hash_val % 2 == 0:
            return response_a, response_b, {"A": "first", "B": "second"}
        else:
            return response_b, response_a, {"A": "second", "B": "first"}

    def unmap_preference(self, preference: str, position_map: dict) -> str:
        """Convert positional preference back to original model labels."""
        if preference == "TIE":
            return "TIE"

        # If A was shown first and judge preferred first, real preference is A
        if position_map["A"] == "first":
            return preference  # A->A, B->B
        else:
            return "B" if preference == "A" else "A"  # Swap
```

### 5.3 Best of 5 Aggregation

```python
from collections import Counter
from typing import List

class JudgmentAggregator:
    """Aggregates multiple judgments using best-of-5 methodology."""

    @staticmethod
    def aggregate_preferences(preferences: List[str]) -> dict:
        """
        Aggregate 5 preferences into final judgment.
        Returns winner and confidence metrics.
        """
        assert len(preferences) == 5, "Requires exactly 5 judgments"

        counts = Counter(preferences)

        # Determine winner
        if counts.get("A", 0) >= 3:
            winner = "A"
        elif counts.get("B", 0) >= 3:
            winner = "B"
        else:
            winner = "TIE"

        # Calculate agreement metrics
        max_count = max(counts.values())
        agreement_ratio = max_count / 5

        return {
            "winner": winner,
            "vote_counts": dict(counts),
            "agreement_ratio": agreement_ratio,
            "unanimous": max_count == 5,
            "majority_margin": max_count - sorted(counts.values())[-2] if len(counts) > 1 else 5
        }

    @staticmethod
    def aggregate_scores(all_scores: List[dict]) -> dict:
        """Aggregate numerical scores across judgments."""
        aggregated = {}

        # Get all score keys from first judgment
        score_keys = all_scores[0].keys()

        for key in score_keys:
            values = [s[key] for s in all_scores]
            aggregated[key] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "std": (sum((x - sum(values)/len(values))**2 for x in values) / len(values)) ** 0.5
            }

        return aggregated
```

### 5.4 Judge Execution Pipeline

```python
class JudgingPipeline:
    def __init__(self, client: OpenRouterClient, judge_model: str = "claude-opus"):
        self.client = client
        self.judge_model = judge_model
        self.shuffler = PositionShuffler()
        self.aggregator = JudgmentAggregator()

    async def judge_comparison(
        self,
        prompt_data: dict,
        response_a: dict,
        response_b: dict,
        n_runs: int = 5
    ) -> dict:
        """Execute full judging pipeline for one comparison."""

        expert_judgments = []
        recipient_judgments = []

        for run in range(n_runs):
            # Shuffle positions
            first, second, pos_map = self.shuffler.shuffle_pair(
                response_a, response_b,
                prompt_data['prompt_id'], run
            )

            # Format comparison for judge
            comparison_text = f"""
## Writing Task
{prompt_data['rendered_prompt']}

## Response A (shown first)
{first['content']}

## Response B (shown second)
{second['content']}
"""

            # Get expert judgment
            expert_result = await self.client.generate(
                self.judge_model,
                comparison_text,
                system_prompt=EXPERT_WRITER_PROMPT
            )
            expert_parsed = self._parse_judgment(expert_result['content'])
            expert_parsed['original_preference'] = self.shuffler.unmap_preference(
                expert_parsed['preference'], pos_map
            )
            expert_judgments.append(expert_parsed)

            # Get recipient judgment
            recipient_prompt = generate_recipient_prompt(
                prompt_data['occupation_title'],
                prompt_data['base_task'],
                prompt_data['industry_desc']
            )
            recipient_result = await self.client.generate(
                self.judge_model,
                comparison_text,
                system_prompt=recipient_prompt
            )
            recipient_parsed = self._parse_judgment(recipient_result['content'])
            recipient_parsed['original_preference'] = self.shuffler.unmap_preference(
                recipient_parsed['preference'], pos_map
            )
            recipient_judgments.append(recipient_parsed)

        # Aggregate results
        return {
            "prompt_id": prompt_data['prompt_id'],
            "model_a": response_a['model'],
            "model_b": response_b['model'],
            "expert_aggregate": self.aggregator.aggregate_preferences(
                [j['original_preference'] for j in expert_judgments]
            ),
            "recipient_aggregate": self.aggregator.aggregate_preferences(
                [j['original_preference'] for j in recipient_judgments]
            ),
            "expert_judgments": expert_judgments,
            "recipient_judgments": recipient_judgments,
        }

    def _parse_judgment(self, response: str) -> dict:
        """Parse JSON judgment from model response."""
        import json
        import re

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(f"Could not parse judgment: {response[:200]}")
```

---

## 6. Database Schema

### 6.1 SQLite Schema Definition

```sql
-- Core tables for the evaluation framework

-- Occupations from O*NET
CREATE TABLE occupations (
    occupation_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    writing_skill_level REAL,
    occupation_group TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Writing tasks extracted from O*NET
CREATE TABLE writing_tasks (
    task_id TEXT PRIMARY KEY,
    occupation_code TEXT REFERENCES occupations(occupation_code),
    task_statement TEXT NOT NULL,
    keywords_matched TEXT,  -- JSON array of matched writing keywords
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated evaluation prompts
CREATE TABLE eval_prompts (
    prompt_id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES writing_tasks(task_id),
    occupation_code TEXT REFERENCES occupations(occupation_code),
    industry_type TEXT NOT NULL,
    industry_description TEXT NOT NULL,
    complexity TEXT CHECK(complexity IN ('simple', 'context_rich')),
    rendered_prompt TEXT NOT NULL,
    context_data TEXT,  -- JSON with generated context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model responses
CREATE TABLE model_responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES eval_prompts(prompt_id),
    model_key TEXT NOT NULL,
    response_content TEXT NOT NULL,
    tokens_used INTEGER,
    latency_ms REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pairwise comparisons
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES eval_prompts(prompt_id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    response_a_id TEXT REFERENCES model_responses(response_id),
    response_b_id TEXT REFERENCES model_responses(response_id),
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual judgments (5 per comparison per persona)
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    judge_persona TEXT CHECK(judge_persona IN ('expert', 'recipient')),
    run_number INTEGER,
    position_shown TEXT,  -- JSON mapping of which response shown first
    raw_preference TEXT,  -- A, B, or TIE as judge stated
    corrected_preference TEXT,  -- Preference after unshuffling
    scores_a TEXT,  -- JSON of dimension scores
    scores_b TEXT,  -- JSON of dimension scores
    reasoning TEXT,
    judge_model TEXT,
    latency_ms REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated results per comparison
CREATE TABLE comparison_results (
    result_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    expert_winner TEXT,
    expert_vote_counts TEXT,  -- JSON
    expert_agreement_ratio REAL,
    recipient_winner TEXT,
    recipient_vote_counts TEXT,  -- JSON
    recipient_agreement_ratio REAL,
    combined_winner TEXT,  -- Consensus of both judges
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregate statistics per model pair
CREATE TABLE model_pair_stats (
    stat_id TEXT PRIMARY KEY,
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    total_comparisons INTEGER,
    model_a_wins INTEGER,
    model_b_wins INTEGER,
    ties INTEGER,
    model_a_win_rate REAL,
    by_complexity TEXT,  -- JSON breakdown
    by_occupation_group TEXT,  -- JSON breakdown
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
CREATE INDEX idx_comparisons_models ON comparisons(model_a, model_b);
CREATE INDEX idx_responses_prompt ON model_responses(prompt_id);
CREATE INDEX idx_prompts_occupation ON eval_prompts(occupation_code);
```

### 6.2 Database Manager Class

```python
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

class EvalDatabase:
    def __init__(self, db_path: str = "data/eval.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)  # The SQL above

    def insert_prompt(self, prompt_data: dict):
        """Insert a new evaluation prompt."""
        with self.connection() as conn:
            conn.execute("""
                INSERT INTO eval_prompts
                (prompt_id, task_id, occupation_code, industry_type,
                 industry_description, complexity, rendered_prompt, context_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt_data['prompt_id'],
                prompt_data.get('task_id'),
                prompt_data['occupation_code'],
                prompt_data['industry_type'],
                prompt_data['industry_desc'],
                prompt_data['complexity'],
                prompt_data['rendered_prompt'],
                json.dumps(prompt_data.get('context', {}))
            ))

    def insert_response(self, response_data: dict) -> str:
        """Insert a model response."""
        import uuid
        response_id = str(uuid.uuid4())

        with self.connection() as conn:
            conn.execute("""
                INSERT INTO model_responses
                (response_id, prompt_id, model_key, response_content,
                 tokens_used, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                response_id,
                response_data['prompt_id'],
                response_data['model'],
                response_data['content'],
                response_data.get('usage', {}).get('total_tokens'),
                response_data.get('latency_ms')
            ))

        return response_id

    def get_model_pair_stats(self, model_a: str, model_b: str) -> dict:
        """Get aggregate statistics for a model pair."""
        with self.connection() as conn:
            row = conn.execute("""
                SELECT * FROM model_pair_stats
                WHERE (model_a = ? AND model_b = ?)
                   OR (model_a = ? AND model_b = ?)
            """, (model_a, model_b, model_b, model_a)).fetchone()

            if row:
                return dict(row)
            return None

    def export_to_csv(self, table: str, output_path: str):
        """Export a table to CSV."""
        import csv

        with self.connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
```

---

## 7. Execution Pipeline

### 7.1 End-to-End Pipeline Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  O*NET Download │ --> │ Task Extraction  │ --> │ Prompt Gen      │
│  & Parse        │     │ & Filtering      │     │ (Simple+Complex)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          v
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Aggregate Stats │ <-- │ Judge Responses  │ <-- │ Generate Model  │
│ & Reporting     │     │ (5x2 per pair)   │     │ Responses       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### 7.2 Main Execution Script

```python
#!/usr/bin/env python3
"""
run_eval.py - Main evaluation execution script
"""

import asyncio
import argparse
from pathlib import Path

from onet_downloader import download_onet
from extract_writing_tasks import OnetWritingExtractor
from prompt_generator import PromptGenerator
from openrouter_client import RateLimitedClient
from judging_pipeline import JudgingPipeline
from database import EvalDatabase
from analysis import ResultsAnalyzer

async def main(args):
    # Initialize components
    db = EvalDatabase(args.db_path)
    client = RateLimitedClient(args.api_key)
    judge_pipeline = JudgingPipeline(client, args.judge_model)

    # Step 1: Download O*NET if needed
    if not Path("data/onet").exists():
        print("Downloading O*NET database...")
        download_onet()

    # Step 2: Extract writing tasks
    print("Extracting writing tasks...")
    extractor = OnetWritingExtractor(Path("data/onet"))
    extractor.load_data()
    writing_corpus = extractor.build_writing_task_corpus()

    # Step 3: Generate prompts
    print(f"Generating {args.n_prompts} evaluation prompts...")
    prompt_gen = PromptGenerator(writing_corpus)
    prompts = prompt_gen.generate_eval_set(n_prompts=args.n_prompts)

    for prompt in prompts:
        db.insert_prompt(prompt)

    # Step 4: Generate model responses
    print("Generating model responses...")
    model_pairs = [
        ("gemini-3-pro", "gpt-5.2"),
        ("gemini-3-pro", "claude-opus"),
        ("gemini-3-pro", "grok-3"),
        ("gemini-3-flash", "gpt-5.2"),
        ("gemini-3-flash", "claude-opus"),
        # Add more pairs as needed
    ]

    for prompt in prompts:
        for model in set(m for pair in model_pairs for m in pair):
            response = await client.generate(model, prompt['rendered_prompt'])
            response['prompt_id'] = prompt['prompt_id']
            db.insert_response(response)

    # Step 5: Run pairwise judgments
    print("Running pairwise evaluations...")
    for prompt in prompts:
        for model_a, model_b in model_pairs:
            # Get responses
            resp_a = db.get_response(prompt['prompt_id'], model_a)
            resp_b = db.get_response(prompt['prompt_id'], model_b)

            # Judge comparison
            result = await judge_pipeline.judge_comparison(
                prompt, resp_a, resp_b, n_runs=5
            )

            db.insert_comparison_result(result)

    # Step 6: Aggregate and analyze
    print("Aggregating results...")
    analyzer = ResultsAnalyzer(db)
    analyzer.compute_aggregate_stats()
    analyzer.generate_report(args.output_dir)

    print(f"Evaluation complete. Results in {args.output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--db-path", default="data/eval.db")
    parser.add_argument("--n-prompts", type=int, default=1000)
    parser.add_argument("--judge-model", default="claude-opus")
    parser.add_argument("--output-dir", default="results")

    args = parser.parse_args()
    asyncio.run(main(args))
```

### 7.3 Checkpoint and Resume Support

```python
class EvalRunner:
    """Supports checkpointing for long-running evaluations."""

    def __init__(self, db: EvalDatabase):
        self.db = db

    def get_pending_prompts(self) -> list:
        """Get prompts that haven't been fully evaluated."""
        with self.db.connection() as conn:
            rows = conn.execute("""
                SELECT p.* FROM eval_prompts p
                LEFT JOIN comparisons c ON p.prompt_id = c.prompt_id
                WHERE c.status IS NULL OR c.status = 'pending'
            """).fetchall()
        return [dict(r) for r in rows]

    def mark_complete(self, prompt_id: str):
        """Mark a prompt as fully evaluated."""
        with self.db.connection() as conn:
            conn.execute("""
                UPDATE comparisons SET status = 'complete'
                WHERE prompt_id = ?
            """, (prompt_id,))
```

---

## 8. Analysis & Reporting

### 8.1 Statistical Analysis

```python
import pandas as pd
import numpy as np
from scipy import stats

class ResultsAnalyzer:
    def __init__(self, db: EvalDatabase):
        self.db = db

    def compute_win_rates(self, model_a: str, model_b: str) -> dict:
        """Compute win rates with confidence intervals."""

        with self.db.connection() as conn:
            rows = conn.execute("""
                SELECT cr.expert_winner, cr.recipient_winner
                FROM comparison_results cr
                JOIN comparisons c ON cr.comparison_id = c.comparison_id
                WHERE c.model_a = ? AND c.model_b = ?
            """, (model_a, model_b)).fetchall()

        results = pd.DataFrame(rows, columns=['expert_winner', 'recipient_winner'])

        # Calculate win rates
        n = len(results)
        a_wins = (results == 'A').sum()
        b_wins = (results == 'B').sum()
        ties = (results == 'TIE').sum()

        # Wilson score interval for confidence
        def wilson_ci(wins, total, confidence=0.95):
            if total == 0:
                return 0, 0, 0
            p = wins / total
            z = stats.norm.ppf(1 - (1 - confidence) / 2)
            denominator = 1 + z**2 / total
            center = (p + z**2 / (2 * total)) / denominator
            margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
            return center, center - margin, center + margin

        return {
            "model_a": model_a,
            "model_b": model_b,
            "total": n,
            "expert": {
                "a_wins": int(a_wins['expert_winner']),
                "b_wins": int(b_wins['expert_winner']),
                "ties": int(ties['expert_winner']),
                "a_win_rate": wilson_ci(a_wins['expert_winner'], n),
            },
            "recipient": {
                "a_wins": int(a_wins['recipient_winner']),
                "b_wins": int(b_wins['recipient_winner']),
                "ties": int(ties['recipient_winner']),
                "a_win_rate": wilson_ci(a_wins['recipient_winner'], n),
            }
        }

    def breakdown_by_dimension(self, model_a: str, model_b: str) -> pd.DataFrame:
        """Get performance breakdown by evaluation dimension."""

        with self.db.connection() as conn:
            rows = conn.execute("""
                SELECT j.scores_a, j.scores_b, j.judge_persona
                FROM judgments j
                JOIN comparisons c ON j.comparison_id = c.comparison_id
                WHERE c.model_a = ? AND c.model_b = ?
            """, (model_a, model_b)).fetchall()

        # Parse and aggregate scores
        dimensions = ['clarity', 'structure', 'tone', 'conciseness',
                      'professionalism', 'task_completion']

        results = {dim: {'a_mean': [], 'b_mean': []} for dim in dimensions}

        for row in rows:
            scores_a = json.loads(row['scores_a'])
            scores_b = json.loads(row['scores_b'])
            for dim in dimensions:
                if dim in scores_a:
                    results[dim]['a_mean'].append(scores_a[dim])
                    results[dim]['b_mean'].append(scores_b[dim])

        # Calculate means
        breakdown = pd.DataFrame([
            {
                'dimension': dim,
                f'{model_a}_mean': np.mean(results[dim]['a_mean']),
                f'{model_b}_mean': np.mean(results[dim]['b_mean']),
                'delta': np.mean(results[dim]['a_mean']) - np.mean(results[dim]['b_mean'])
            }
            for dim in dimensions
        ])

        return breakdown
```

### 8.2 Visualization Generation

```python
import matplotlib.pyplot as plt
import seaborn as sns

class Visualizer:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use('seaborn-v0_8-whitegrid')

    def plot_win_rate_comparison(self, stats: list, filename: str = "win_rates.png"):
        """Generate win rate comparison chart."""

        fig, ax = plt.subplots(figsize=(12, 6))

        models = [s['model_b'] for s in stats]
        gemini_wins = [s['expert']['a_win_rate'][0] * 100 for s in stats]
        competitor_wins = [(s['expert']['b_wins'] / s['total']) * 100 for s in stats]
        ties = [(s['expert']['ties'] / s['total']) * 100 for s in stats]

        x = np.arange(len(models))
        width = 0.25

        ax.bar(x - width, gemini_wins, width, label='Gemini Wins', color='#4285F4')
        ax.bar(x, competitor_wins, width, label='Competitor Wins', color='#EA4335')
        ax.bar(x + width, ties, width, label='Ties', color='#9E9E9E')

        ax.set_ylabel('Percentage')
        ax.set_title('Gemini Win Rates vs Competitors (Expert Judge)')
        ax.set_xticks(x)
        ax.set_xticklabels(models)
        ax.legend()

        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=150)
        plt.close()

    def plot_dimension_heatmap(self, breakdown_df: pd.DataFrame, filename: str = "dimensions.png"):
        """Generate dimension comparison heatmap."""

        fig, ax = plt.subplots(figsize=(10, 8))

        # Pivot for heatmap
        heatmap_data = breakdown_df.set_index('dimension')['delta']

        sns.heatmap(
            heatmap_data.values.reshape(-1, 1),
            annot=True,
            cmap='RdYlGn',
            center=0,
            yticklabels=breakdown_df['dimension'],
            xticklabels=['Delta (Gemini - Competitor)'],
            ax=ax
        )

        ax.set_title('Score Differences by Dimension')
        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=150)
        plt.close()

    def plot_occupation_breakdown(self, data: pd.DataFrame, filename: str = "by_occupation.png"):
        """Plot win rates by occupation group."""

        fig, ax = plt.subplots(figsize=(14, 8))

        data_sorted = data.sort_values('win_rate', ascending=True)

        colors = ['#4285F4' if wr >= 50 else '#EA4335' for wr in data_sorted['win_rate']]

        ax.barh(data_sorted['occupation_group'], data_sorted['win_rate'], color=colors)
        ax.axvline(x=50, color='black', linestyle='--', alpha=0.5)
        ax.set_xlabel('Gemini Win Rate (%)')
        ax.set_title('Win Rate by Occupation Group')

        plt.tight_layout()
        plt.savefig(self.output_dir / filename, dpi=150)
        plt.close()
```

### 8.3 PDF Report Generation

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

class ReportGenerator:
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.doc = SimpleDocTemplate(output_path, pagesize=letter)
        self.styles = getSampleStyleSheet()
        self.elements = []

    def add_title(self, text: str):
        self.elements.append(Paragraph(text, self.styles['Title']))
        self.elements.append(Spacer(1, 0.5*inch))

    def add_section(self, title: str, content: str):
        self.elements.append(Paragraph(title, self.styles['Heading1']))
        self.elements.append(Paragraph(content, self.styles['Normal']))
        self.elements.append(Spacer(1, 0.25*inch))

    def add_image(self, path: str, width: float = 6*inch):
        img = Image(path, width=width)
        self.elements.append(img)
        self.elements.append(Spacer(1, 0.25*inch))

    def add_table(self, data: list, col_widths: list = None):
        table = Table(data, colWidths=col_widths)
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.25*inch))

    def add_weakness_analysis(self, weaknesses: list):
        """Add detailed weakness analysis section."""
        self.elements.append(Paragraph("Identified Gemini Weaknesses", self.styles['Heading1']))

        for i, weakness in enumerate(weaknesses, 1):
            self.elements.append(Paragraph(
                f"<b>{i}. {weakness['dimension']}</b>",
                self.styles['Heading2']
            ))
            self.elements.append(Paragraph(
                f"<b>Severity:</b> {weakness['severity']}/5",
                self.styles['Normal']
            ))
            self.elements.append(Paragraph(
                f"<b>Description:</b> {weakness['description']}",
                self.styles['Normal']
            ))
            self.elements.append(Paragraph(
                f"<b>Affected Tasks:</b> {', '.join(weakness['affected_tasks'])}",
                self.styles['Normal']
            ))
            self.elements.append(Paragraph(
                f"<b>Recommendation:</b> {weakness['recommendation']}",
                self.styles['Normal']
            ))
            self.elements.append(Spacer(1, 0.15*inch))

    def generate(self):
        self.doc.build(self.elements)


def generate_final_report(analyzer: ResultsAnalyzer, viz: Visualizer, output_dir: Path):
    """Generate complete PDF report."""

    report = ReportGenerator(str(output_dir / "gemini_writing_eval_report.pdf"))

    report.add_title("Gemini Writing Capabilities Evaluation Report")

    report.add_section(
        "Executive Summary",
        """This report presents the results of a comprehensive evaluation comparing
        Gemini 3.0 Pro and Flash models against frontier competitors (GPT-5.2, Claude Opus,
        Grok, Kimi) on realistic writing tasks derived from the US economy's occupational
        landscape. The evaluation employed pairwise comparisons with dual-persona judging
        and best-of-5 aggregation for robust results."""
    )

    # Add methodology section
    report.add_section(
        "Methodology",
        """- 1,000+ writing prompts across 450 occupations
        - Tasks extracted from O*NET database
        - Dual-judge system: Expert Writer + Task Recipient personas
        - 5 independent judgments per comparison with position shuffling
        - Majority vote aggregation"""
    )

    # Add visualizations
    report.add_image(str(output_dir / "win_rates.png"))
    report.add_image(str(output_dir / "dimensions.png"))
    report.add_image(str(output_dir / "by_occupation.png"))

    # Identify and add weaknesses
    weaknesses = analyzer.identify_weaknesses("gemini-3-pro")
    report.add_weakness_analysis(weaknesses)

    report.generate()
```

---

## 9. Quality Assurance

### 9.1 Position Bias Detection

```python
def detect_position_bias(db: EvalDatabase) -> dict:
    """Analyze for position bias in judgments."""

    with db.connection() as conn:
        rows = conn.execute("""
            SELECT position_shown, raw_preference, corrected_preference
            FROM judgments
        """).fetchall()

    df = pd.DataFrame(rows, columns=['position_shown', 'raw_preference', 'corrected_preference'])

    # Calculate first-position win rate
    first_position_wins = (df['raw_preference'] == 'A').sum()
    second_position_wins = (df['raw_preference'] == 'B').sum()
    total = first_position_wins + second_position_wins

    first_rate = first_position_wins / total if total > 0 else 0.5

    # Chi-square test for bias
    chi2, p_value = stats.chisquare([first_position_wins, second_position_wins])

    return {
        "first_position_win_rate": first_rate,
        "chi_square": chi2,
        "p_value": p_value,
        "bias_detected": p_value < 0.05 and abs(first_rate - 0.5) > 0.05
    }
```

### 9.2 Inter-Judge Agreement

```python
def calculate_inter_judge_agreement(db: EvalDatabase) -> dict:
    """Calculate agreement between expert and recipient judges."""

    with db.connection() as conn:
        rows = conn.execute("""
            SELECT cr.expert_winner, cr.recipient_winner
            FROM comparison_results cr
        """).fetchall()

    df = pd.DataFrame(rows, columns=['expert', 'recipient'])

    # Simple agreement
    agreement = (df['expert'] == df['recipient']).mean()

    # Cohen's Kappa
    from sklearn.metrics import cohen_kappa_score
    kappa = cohen_kappa_score(df['expert'], df['recipient'])

    return {
        "simple_agreement": agreement,
        "cohens_kappa": kappa,
        "interpretation": "substantial" if kappa > 0.6 else "moderate" if kappa > 0.4 else "fair"
    }
```

### 9.3 Response Quality Validation

```python
def validate_response_quality(response: str, task: str) -> dict:
    """Validate that a model response meets minimum quality standards."""

    issues = []

    # Length check
    word_count = len(response.split())
    if word_count < 50:
        issues.append("Response too short")
    if word_count > 2000:
        issues.append("Response excessively long")

    # Empty/error check
    if not response.strip():
        issues.append("Empty response")
    if "I cannot" in response or "I'm unable" in response:
        issues.append("Refusal detected")

    # Formatting check
    if response.count('\n') == 0 and word_count > 100:
        issues.append("No paragraph breaks in long response")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "word_count": word_count
    }
```

### 9.4 Reproducibility Measures

```python
class ReproducibilityTracker:
    """Track all parameters for reproducibility."""

    def __init__(self):
        self.config = {}

    def record_config(self, **kwargs):
        self.config.update(kwargs)
        self.config['timestamp'] = datetime.now().isoformat()
        self.config['git_commit'] = self._get_git_commit()

    def _get_git_commit(self) -> str:
        import subprocess
        try:
            return subprocess.check_output(
                ['git', 'rev-parse', 'HEAD']
            ).decode().strip()
        except:
            return "unknown"

    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.config, f, indent=2)
```

---

## 10. Fine-Grained Eval Viewer

### 10.1 Terminal-Based Viewer

```python
#!/usr/bin/env python3
"""
eval_viewer.py - Interactive evaluation results viewer
"""

import sqlite3
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

class EvalViewer:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def list_comparisons(self, model_a: str = None, model_b: str = None, limit: int = 20):
        """List comparisons with filtering."""

        query = """
            SELECT c.comparison_id, c.model_a, c.model_b,
                   p.occupation_code, cr.expert_winner, cr.recipient_winner
            FROM comparisons c
            JOIN eval_prompts p ON c.prompt_id = p.prompt_id
            LEFT JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
            WHERE 1=1
        """
        params = []

        if model_a:
            query += " AND c.model_a = ?"
            params.append(model_a)
        if model_b:
            query += " AND c.model_b = ?"
            params.append(model_b)

        query += f" LIMIT {limit}"

        rows = self.conn.execute(query, params).fetchall()

        table = Table(title="Comparisons")
        table.add_column("ID", style="cyan")
        table.add_column("Model A")
        table.add_column("Model B")
        table.add_column("Occupation")
        table.add_column("Expert Winner", style="green")
        table.add_column("Recipient Winner", style="yellow")

        for row in rows:
            table.add_row(
                row['comparison_id'][:8],
                row['model_a'],
                row['model_b'],
                row['occupation_code'],
                row['expert_winner'] or '-',
                row['recipient_winner'] or '-'
            )

        console.print(table)

    def view_comparison(self, comparison_id: str):
        """View detailed comparison results."""

        # Get comparison data
        comp = self.conn.execute("""
            SELECT c.*, p.rendered_prompt, p.occupation_code
            FROM comparisons c
            JOIN eval_prompts p ON c.prompt_id = p.prompt_id
            WHERE c.comparison_id = ?
        """, (comparison_id,)).fetchone()

        # Get responses
        resp_a = self.conn.execute("""
            SELECT response_content FROM model_responses
            WHERE response_id = ?
        """, (comp['response_a_id'],)).fetchone()

        resp_b = self.conn.execute("""
            SELECT response_content FROM model_responses
            WHERE response_id = ?
        """, (comp['response_b_id'],)).fetchone()

        # Get judgments
        judgments = self.conn.execute("""
            SELECT * FROM judgments
            WHERE comparison_id = ?
            ORDER BY judge_persona, run_number
        """, (comparison_id,)).fetchall()

        # Display
        console.print(Panel(comp['rendered_prompt'], title="Prompt"))
        console.print()

        console.print(Panel(
            resp_a['response_content'][:1000] + "..." if len(resp_a['response_content']) > 1000 else resp_a['response_content'],
            title=f"Response A ({comp['model_a']})"
        ))
        console.print()

        console.print(Panel(
            resp_b['response_content'][:1000] + "..." if len(resp_b['response_content']) > 1000 else resp_b['response_content'],
            title=f"Response B ({comp['model_b']})"
        ))
        console.print()

        # Judgments table
        table = Table(title="Judgments")
        table.add_column("Persona")
        table.add_column("Run")
        table.add_column("Preference")
        table.add_column("Reasoning")

        for j in judgments:
            table.add_row(
                j['judge_persona'],
                str(j['run_number']),
                j['corrected_preference'],
                j['reasoning'][:100] + "..." if j['reasoning'] and len(j['reasoning']) > 100 else j['reasoning']
            )

        console.print(table)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/eval.db")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--model-a")
    list_parser.add_argument("--model-b")
    list_parser.add_argument("--limit", type=int, default=20)

    view_parser = subparsers.add_parser("view")
    view_parser.add_argument("comparison_id")

    args = parser.parse_args()
    viewer = EvalViewer(args.db)

    if args.command == "list":
        viewer.list_comparisons(args.model_a, args.model_b, args.limit)
    elif args.command == "view":
        viewer.view_comparison(args.comparison_id)

if __name__ == "__main__":
    main()
```

---

## 11. Project Structure

```
gemini-writing-eval/
├── data/
│   ├── onet/                  # O*NET database files
│   ├── prompts/               # Generated prompts (cached)
│   └── eval.db                # SQLite database
├── src/
│   ├── __init__.py
│   ├── onet_downloader.py     # O*NET data download
│   ├── extract_writing_tasks.py
│   ├── prompt_generator.py
│   ├── context_generator.py
│   ├── openrouter_client.py
│   ├── judging_pipeline.py
│   ├── database.py
│   ├── analysis.py
│   ├── visualizations.py
│   ├── report_generator.py
│   └── eval_viewer.py
├── configs/
│   ├── models.yaml            # Model configurations
│   ├── industries.yaml        # Industry contexts
│   └── rubrics.yaml           # Evaluation rubrics
├── results/
│   ├── figures/               # Generated visualizations
│   ├── exports/               # CSV exports
│   └── reports/               # PDF reports
├── tests/
│   ├── test_prompt_generation.py
│   ├── test_judging.py
│   └── test_analysis.py
├── run_eval.py                # Main execution script
├── requirements.txt
└── README.md
```

---

## 12. Estimated Resource Requirements

| Resource | Estimate |
|----------|----------|
| O*NET Data | ~500 MB |
| Prompts (1000) | ~5 MB |
| Model Responses | ~50 MB |
| Judge Responses | ~100 MB |
| Total DB Size | ~200 MB |
| API Costs (rough) | $500-2000 depending on models |
| Runtime | 8-24 hours |

---

## 13. Success Criteria

1. **Coverage**: 450+ occupations, 1000+ unique prompts
2. **Robustness**: Position bias < 5%, inter-judge agreement kappa > 0.4
3. **Statistical Significance**: 95% confidence intervals on all win rates
4. **Actionable Insights**: Specific, ranked weaknesses with recommendations
5. **Reproducibility**: Full audit trail, all configs versioned

---

## Appendix A: Complete Rubric Definitions

### Expert Writer Rubric

| Dimension | 1 (Poor) | 3 (Adequate) | 5 (Excellent) |
|-----------|----------|--------------|---------------|
| Clarity | Confusing, ambiguous | Understandable with effort | Crystal clear, no ambiguity |
| Structure | Disorganized, no flow | Basic organization | Logical, compelling flow |
| Tone | Inappropriate for context | Acceptable | Perfectly calibrated |
| Conciseness | Verbose or incomplete | Reasonable length | Optimal density |
| Professionalism | Unprofessional errors | Meets standards | Polished, impressive |
| Task Completion | Misses key requirements | Addresses main points | Exceeds expectations |

### Recipient Rubric

| Dimension | 1 (Poor) | 3 (Adequate) | 5 (Excellent) |
|-----------|----------|--------------|---------------|
| Relevance | Off-topic | Addresses topic | Precisely targeted |
| Actionability | No clear actions | Some guidance | Clear next steps |
| Credibility | Undermines trust | Neutral | Builds confidence |
| Engagement | Tedious to read | Acceptable | Compelling read |
| Appropriateness | Wrong format/length | Acceptable format | Perfect format |

---

This implementation plan provides a comprehensive foundation for building a rigorous, scalable writing evaluation framework. The modular design allows for iterative development and easy extension to additional models, occupations, or evaluation criteria.
