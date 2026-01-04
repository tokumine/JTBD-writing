# Gemini Writing Evaluation Framework: Master Implementation Plan

## Executive Summary

This document outlines a comprehensive framework for evaluating Gemini 3.0 Pro and Flash against frontier models (GPT-5.2, Claude Opus, X/Grok, Kimi, etc.) on realistic writing tasks derived from the US economy. The evaluation uses O*NET occupational data to ensure coverage across all job types with writing requirements, employs dual-judge personas (expert writer + target recipient), and aggregates results via pairwise comparisons with position-bias mitigation.

---

## 1. O*NET Data Pipeline

### 1.1 Overview

O*NET (Occupational Information Network) is the primary US Department of Labor database containing detailed occupational information. We will extract tasks, work activities, and skills related to writing across all occupations.

### 1.2 Download Script

```python
#!/usr/bin/env python3
"""
onet_downloader.py - Download and extract O*NET database files
"""

import os
import requests
import zipfile
from pathlib import Path

ONET_BASE_URL = "https://www.onetcenter.org/dl_files/database"
ONET_VERSION = "29_1"  # Update to latest version
OUTPUT_DIR = Path("data/onet_raw")

FILES_TO_DOWNLOAD = [
    f"db_{ONET_VERSION}_excel.zip",  # Main database in Excel format
    f"db_{ONET_VERSION}_text.zip",   # Text/CSV format (preferred)
]

def download_onet_data():
    """Download O*NET database files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename in FILES_TO_DOWNLOAD:
        url = f"{ONET_BASE_URL}/{filename}"
        output_path = OUTPUT_DIR / filename

        print(f"Downloading {filename}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract ZIP
        print(f"Extracting {filename}...")
        with zipfile.ZipFile(output_path, 'r') as zip_ref:
            zip_ref.extractall(OUTPUT_DIR / filename.replace('.zip', ''))

    print("O*NET download complete!")

if __name__ == "__main__":
    download_onet_data()
```

### 1.3 Key O*NET Tables for Writing Tasks

| Table Name | Purpose | Key Fields |
|------------|---------|------------|
| `Occupation Data.txt` | All occupations | O*NET-SOC Code, Title, Description |
| `Task Statements.txt` | Specific work tasks | Task ID, Task, Task Type |
| `Tasks to DWAs.txt` | Links tasks to work activities | Task ID, DWA ID |
| `Work Activities.txt` | Detailed work activities | DWA ID, DWA Title, Description |
| `Skills.txt` | Required skills | Element ID, Element Name, Scale ID, Data Value |

### 1.4 Writing Task Extraction Logic

```python
#!/usr/bin/env python3
"""
onet_parser.py - Extract writing-related tasks from O*NET
"""

import pandas as pd
import sqlite3
from pathlib import Path

# Keywords indicating writing-related tasks
WRITING_KEYWORDS = [
    'write', 'writing', 'written', 'draft', 'compose', 'document',
    'report', 'memo', 'email', 'correspondence', 'communicate',
    'prepare', 'create', 'develop', 'author', 'edit', 'proofread',
    'proposal', 'letter', 'brief', 'summary', 'transcript',
    'presentation', 'newsletter', 'publication', 'blog', 'content',
    'copy', 'script', 'narrative', 'description', 'specification'
]

# Work Activity IDs related to writing (from O*NET taxonomy)
WRITING_ACTIVITY_IDS = [
    '4.A.4.a.1',  # Writing - Communicating in writing
    '4.A.4.a.2',  # Documenting/Recording Information
    '4.A.2.b.2',  # Processing Information
]

class ONETParser:
    def __init__(self, onet_dir: Path, db_path: Path):
        self.onet_dir = onet_dir
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    def load_occupations(self) -> pd.DataFrame:
        """Load occupation data."""
        return pd.read_csv(
            self.onet_dir / "Occupation Data.txt",
            sep='\t',
            encoding='utf-8'
        )

    def load_tasks(self) -> pd.DataFrame:
        """Load task statements."""
        return pd.read_csv(
            self.onet_dir / "Task Statements.txt",
            sep='\t',
            encoding='utf-8'
        )

    def load_work_activities(self) -> pd.DataFrame:
        """Load detailed work activities."""
        return pd.read_csv(
            self.onet_dir / "Work Activities.txt",
            sep='\t',
            encoding='utf-8'
        )

    def extract_writing_tasks(self) -> pd.DataFrame:
        """
        Extract tasks related to writing using keyword matching
        and work activity linkages.
        """
        tasks = self.load_tasks()

        # Keyword-based filtering
        pattern = '|'.join(WRITING_KEYWORDS)
        writing_tasks = tasks[
            tasks['Task'].str.lower().str.contains(pattern, na=False)
        ].copy()

        # Add occupation info
        occupations = self.load_occupations()
        writing_tasks = writing_tasks.merge(
            occupations[['O*NET-SOC Code', 'Title', 'Description']],
            on='O*NET-SOC Code',
            how='left'
        )

        return writing_tasks

    def categorize_writing_types(self, tasks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Categorize writing tasks into types for balanced sampling.
        """
        def categorize(task_text: str) -> str:
            task_lower = task_text.lower()
            if any(w in task_lower for w in ['email', 'correspondence', 'memo']):
                return 'correspondence'
            elif any(w in task_lower for w in ['report', 'summary', 'analysis']):
                return 'reports'
            elif any(w in task_lower for w in ['proposal', 'grant', 'bid']):
                return 'proposals'
            elif any(w in task_lower for w in ['document', 'record', 'log']):
                return 'documentation'
            elif any(w in task_lower for w in ['presentation', 'speech', 'script']):
                return 'presentations'
            elif any(w in task_lower for w in ['policy', 'procedure', 'manual']):
                return 'policy_docs'
            elif any(w in task_lower for w in ['creative', 'story', 'content', 'blog']):
                return 'creative_content'
            else:
                return 'general'

        tasks_df['writing_category'] = tasks_df['Task'].apply(categorize)
        return tasks_df

    def save_to_database(self, writing_tasks: pd.DataFrame):
        """Save extracted tasks to SQLite database."""
        writing_tasks.to_sql(
            'onet_writing_tasks',
            self.conn,
            if_exists='replace',
            index=False
        )
        self.conn.commit()
        print(f"Saved {len(writing_tasks)} writing tasks to database")
```

### 1.5 Industry Diversification Logic

To ensure diverse industry coverage within each occupation (e.g., CEO of fruit company vs. CEO of startup):

```python
# Industry context generators by occupation category
INDUSTRY_CONTEXTS = {
    'executive': [
        {'industry': 'agriculture', 'company': 'FreshHarvest Farms', 'context': 'organic fruit production'},
        {'industry': 'technology', 'company': 'NexGen AI', 'context': 'B2B SaaS startup'},
        {'industry': 'nonprofit', 'company': 'Hope Foundation', 'context': 'homeless services charity'},
        {'industry': 'manufacturing', 'company': 'SteelWorks Inc', 'context': 'industrial equipment'},
        {'industry': 'healthcare', 'company': 'MedCare Systems', 'context': 'hospital network'},
        {'industry': 'finance', 'company': 'Apex Capital', 'context': 'investment management'},
        {'industry': 'retail', 'company': 'QuickMart', 'context': 'regional grocery chain'},
        {'industry': 'education', 'company': 'Brightpath Academy', 'context': 'K-12 private school'},
    ],
    'healthcare': [
        {'industry': 'hospital', 'context': 'urban trauma center'},
        {'industry': 'clinic', 'context': 'rural family practice'},
        {'industry': 'research', 'context': 'academic medical center'},
        {'industry': 'pharma', 'context': 'pharmaceutical company'},
    ],
    # ... additional categories
}

def generate_industry_variants(occupation: str, base_task: str, n_variants: int = 3) -> list:
    """
    Generate industry-specific variants of a writing task.
    """
    category = classify_occupation_category(occupation)
    contexts = INDUSTRY_CONTEXTS.get(category, INDUSTRY_CONTEXTS['general'])

    variants = []
    for ctx in random.sample(contexts, min(n_variants, len(contexts))):
        variant = {
            'base_task': base_task,
            'occupation': occupation,
            'industry': ctx['industry'],
            'company_name': ctx.get('company', 'Acme Corp'),
            'industry_context': ctx['context'],
        }
        variants.append(variant)

    return variants
```

---

## 2. Eval Prompt Generation

### 2.1 Prompt Template Structure

Each writing prompt consists of:

1. **Role Context**: Who the writer is
2. **Task Description**: What they need to write
3. **Audience**: Who will read it
4. **Constraints**: Length, tone, format requirements
5. **Supporting Context** (optional): Additional information needed

### 2.2 Prompt Templates by Writing Category

```python
PROMPT_TEMPLATES = {
    'correspondence': {
        'simple': """
You are a {occupation} at {company_name}, a company in the {industry} industry.

Task: {task_description}

Write a professional email addressing this task. The email should be clear,
appropriately toned for the recipient, and achieve the stated objective.
""",
        'with_context': """
You are a {occupation} at {company_name}, a company in the {industry} industry.

Background Context:
{additional_context}

Task: {task_description}

Recipient: {recipient_description}

Write a professional email addressing this task. Consider the background
context and tailor your message appropriately for the recipient.
"""
    },

    'reports': {
        'simple': """
You are a {occupation} at {company_name} ({industry}).

Task: {task_description}

Write a professional report or summary addressing this task. Structure your
writing clearly with appropriate sections if needed.
""",
        'with_context': """
You are a {occupation} at {company_name} ({industry}).

Background Information:
{additional_context}

Data/Metrics to Include:
{data_context}

Task: {task_description}

Audience: {audience_description}

Write a professional report addressing this task. Use the provided information
and structure your writing appropriately for the intended audience.
"""
    },

    'proposals': {
        'simple': """
You are a {occupation} at {company_name}, operating in the {industry} sector.

Task: {task_description}

Write a compelling proposal that clearly articulates the value proposition
and addresses likely concerns of the decision-maker.
""",
        'with_context': """
You are a {occupation} at {company_name}, operating in the {industry} sector.

Your Organization's Background:
{org_context}

Opportunity Details:
{opportunity_context}

Budget Constraints: {budget_info}

Task: {task_description}

Target Decision-Maker: {decision_maker}

Write a compelling proposal tailored to this specific opportunity and
decision-maker.
"""
    },

    'documentation': {
        'simple': """
You are a {occupation} at {company_name} ({industry}).

Task: {task_description}

Create clear, accurate documentation that would be useful for its intended purpose.
""",
        'with_context': """
You are a {occupation} at {company_name} ({industry}).

System/Process to Document:
{system_context}

Target Users: {user_context}

Existing Documentation Style: {style_guide}

Task: {task_description}

Create documentation that is consistent with the organization's style and
appropriate for the target users.
"""
    }
}
```

### 2.3 Prompt Generation Pipeline

```python
class PromptGenerator:
    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn
        self.context_generator = ContextGenerator()

    def generate_eval_prompt(
        self,
        onet_task: dict,
        industry_context: dict,
        include_context: bool = False
    ) -> dict:
        """
        Generate a complete evaluation prompt from O*NET task data.
        """
        writing_category = onet_task['writing_category']
        template_type = 'with_context' if include_context else 'simple'
        template = PROMPT_TEMPLATES[writing_category][template_type]

        # Base substitutions
        substitutions = {
            'occupation': onet_task['Title'],
            'company_name': industry_context['company_name'],
            'industry': industry_context['industry'],
            'task_description': self._humanize_task(onet_task['Task']),
        }

        # Generate additional context if needed
        if include_context:
            context_data = self.context_generator.generate(
                occupation=onet_task['Title'],
                task=onet_task['Task'],
                industry=industry_context['industry'],
                category=writing_category
            )
            substitutions.update(context_data)

        prompt = template.format(**substitutions)

        return {
            'prompt_id': self._generate_id(),
            'prompt_text': prompt.strip(),
            'onet_task_id': onet_task['Task ID'],
            'occupation_code': onet_task['O*NET-SOC Code'],
            'occupation_title': onet_task['Title'],
            'writing_category': writing_category,
            'industry': industry_context['industry'],
            'has_context': include_context,
            'metadata': {
                'company_name': industry_context['company_name'],
                'industry_context': industry_context.get('context', ''),
            }
        }

    def _humanize_task(self, task_text: str) -> str:
        """
        Convert O*NET task statement to natural instruction.
        """
        # Remove common O*NET phrasing patterns
        task = task_text.strip()
        task = re.sub(r'^(Write|Prepare|Draft|Compose|Create)\s+', '', task, flags=re.I)
        return f"Write {task[0].lower()}{task[1:]}"

    def generate_batch(
        self,
        n_prompts: int,
        context_ratio: float = 0.4
    ) -> list:
        """
        Generate a balanced batch of evaluation prompts.
        """
        # Load writing tasks from database
        tasks_df = pd.read_sql(
            "SELECT * FROM onet_writing_tasks",
            self.conn
        )

        prompts = []
        n_with_context = int(n_prompts * context_ratio)

        # Stratified sampling by writing category and occupation level
        for _, task_row in tasks_df.sample(n_prompts).iterrows():
            task = task_row.to_dict()
            industry_variants = generate_industry_variants(
                task['Title'],
                task['Task'],
                n_variants=1
            )

            include_context = len(prompts) < n_with_context

            prompt = self.generate_eval_prompt(
                onet_task=task,
                industry_context=industry_variants[0],
                include_context=include_context
            )
            prompts.append(prompt)

        return prompts
```

---

## 3. Context Generation

### 3.1 Context Generation Strategies

For prompts requiring additional context, we use multiple strategies:

1. **Template-based generation**: Pre-defined context templates with variable substitution
2. **LLM-assisted generation**: Use a capable model to generate realistic context
3. **Real-world data integration**: Incorporate anonymized real-world examples

### 3.2 Context Generator Implementation

```python
class ContextGenerator:
    """
    Generates realistic additional context for writing prompts.
    """

    # Context templates by category
    CONTEXT_TEMPLATES = {
        'correspondence': {
            'recipient_description': [
                "Senior VP of Operations who prefers concise communication",
                "External client who is unfamiliar with technical jargon",
                "Board member who needs high-level strategic overview",
                "Direct report who needs actionable guidance",
            ],
            'additional_context': [
                "Recent quarterly results showed a 15% increase in revenue but customer satisfaction scores dropped by 8 points.",
                "The company recently underwent a merger and teams are still integrating processes.",
                "Budget constraints require a 20% reduction in operational costs this quarter.",
            ]
        },
        'reports': {
            'data_context': [
                "Q3 Revenue: $4.2M (up 12% YoY), Operating Margin: 18%, Customer Churn: 5.2%",
                "Project completed 2 weeks ahead of schedule, under budget by $45K, with 3 scope changes approved",
                "Survey results: 847 respondents, 72% satisfaction rate, top concerns: wait times (34%), communication (28%)",
            ],
            'audience_description': [
                "C-suite executives who need strategic insights in 5 minutes or less",
                "Technical team leads who need detailed methodology and data",
                "External stakeholders who need compliance-focused documentation",
            ]
        },
        'proposals': {
            'org_context': [
                "10-year-old company with strong track record, recently expanded to 3 new markets",
                "Startup with innovative technology, limited operational history but strong team credentials",
                "Nonprofit with 25-year history, extensive community relationships, seeking to scale impact",
            ],
            'opportunity_context': [
                "RFP for $2M contract, 3-year term, with potential for renewal. 4 other vendors competing.",
                "Grant opportunity for $500K to pilot new program. Foundation has funded similar initiatives.",
                "Partnership proposal to Fortune 500 company seeking innovation partners.",
            ],
            'budget_info': [
                "$150K implementation budget with flexibility for phased approach",
                "Fixed budget of $75K, must demonstrate clear ROI within 12 months",
                "Budget TBD based on proposal scope, decision-makers value innovation over cost",
            ]
        }
    }

    def generate(
        self,
        occupation: str,
        task: str,
        industry: str,
        category: str
    ) -> dict:
        """
        Generate context appropriate for the writing task.
        """
        templates = self.CONTEXT_TEMPLATES.get(category, {})
        context = {}

        for field, options in templates.items():
            # Select contextually appropriate option
            context[field] = self._select_context(
                options, occupation, industry
            )

        # Generate any missing required fields using LLM
        context = self._fill_missing_context(context, occupation, task, industry)

        return context

    def _select_context(
        self,
        options: list,
        occupation: str,
        industry: str
    ) -> str:
        """Select most appropriate context from options."""
        # Simple random selection; could be enhanced with semantic matching
        return random.choice(options)

    def _fill_missing_context(
        self,
        context: dict,
        occupation: str,
        task: str,
        industry: str
    ) -> dict:
        """
        Use LLM to generate any missing context fields.
        """
        # Implementation uses OpenRouter API to generate context
        # This is a fallback for complex scenarios
        return context
```

### 3.3 Context Validation

```python
def validate_context(prompt: dict) -> bool:
    """
    Validate that generated context is realistic and appropriate.
    """
    checks = [
        # Length checks
        len(prompt['prompt_text']) >= 100,
        len(prompt['prompt_text']) <= 3000,

        # Required fields present
        prompt.get('occupation_title') is not None,
        prompt.get('industry') is not None,

        # No placeholder text remaining
        '{' not in prompt['prompt_text'],
        '}' not in prompt['prompt_text'],
    ]

    return all(checks)
```

---

## 4. Model Integration (OpenRouter API)

### 4.1 Supported Models Configuration

```python
EVAL_MODELS = {
    'gemini-3.0-pro': {
        'openrouter_id': 'google/gemini-3.0-pro',
        'display_name': 'Gemini 3.0 Pro',
        'provider': 'Google',
        'is_target': True,  # Primary model being evaluated
    },
    'gemini-3.0-flash': {
        'openrouter_id': 'google/gemini-3.0-flash',
        'display_name': 'Gemini 3.0 Flash',
        'provider': 'Google',
        'is_target': True,
    },
    'gpt-5.2': {
        'openrouter_id': 'openai/gpt-5.2',
        'display_name': 'GPT-5.2',
        'provider': 'OpenAI',
        'is_target': False,
    },
    'claude-opus': {
        'openrouter_id': 'anthropic/claude-opus-4',
        'display_name': 'Claude Opus 4',
        'provider': 'Anthropic',
        'is_target': False,
    },
    'grok-3': {
        'openrouter_id': 'x-ai/grok-3',
        'display_name': 'Grok 3',
        'provider': 'xAI',
        'is_target': False,
    },
    'kimi-k2': {
        'openrouter_id': 'moonshot/kimi-k2',
        'display_name': 'Kimi K2',
        'provider': 'Moonshot',
        'is_target': False,
    },
}

# Judge model (should be highly capable)
JUDGE_MODEL = 'anthropic/claude-opus-4'
```

### 4.2 OpenRouter Client Implementation

```python
import httpx
import asyncio
from typing import Optional
import os

class OpenRouterClient:
    """
    Async client for OpenRouter API with retry logic and rate limiting.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OpenRouter API key required")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'HTTP-Referer': 'https://writing-eval.example.com',
                'X-Title': 'Writing Evaluation Framework',
            },
            timeout=120.0
        )

        # Rate limiting
        self.semaphore = asyncio.Semaphore(10)  # Max concurrent requests
        self.request_delay = 0.1  # Seconds between requests

    async def complete(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> dict:
        """
        Generate completion from specified model.
        """
        async with self.semaphore:
            await asyncio.sleep(self.request_delay)

            payload = {
                'model': model_id,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens,
                'temperature': temperature,
                **kwargs
            }

            for attempt in range(3):  # Retry logic
                try:
                    response = await self.client.post(
                        '/chat/completions',
                        json=payload
                    )
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:  # Rate limited
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise

            raise Exception(f"Failed after 3 attempts for model {model_id}")

    async def generate_writing(
        self,
        model_key: str,
        prompt: str
    ) -> dict:
        """
        Generate writing sample from a model.
        """
        model_config = EVAL_MODELS[model_key]

        result = await self.complete(
            model_id=model_config['openrouter_id'],
            prompt=prompt,
            temperature=0.7,
            max_tokens=2048,
        )

        return {
            'model_key': model_key,
            'model_id': model_config['openrouter_id'],
            'response_text': result['choices'][0]['message']['content'],
            'usage': result.get('usage', {}),
            'finish_reason': result['choices'][0].get('finish_reason'),
        }

    async def close(self):
        await self.client.aclose()
```

### 4.3 Batch Generation Pipeline

```python
async def generate_all_responses(
    client: OpenRouterClient,
    prompt: dict,
    models: list[str]
) -> dict:
    """
    Generate responses from all models for a single prompt.
    """
    tasks = [
        client.generate_writing(model_key, prompt['prompt_text'])
        for model_key in models
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = {}
    for model_key, result in zip(models, results):
        if isinstance(result, Exception):
            responses[model_key] = {'error': str(result)}
        else:
            responses[model_key] = result

    return {
        'prompt_id': prompt['prompt_id'],
        'responses': responses,
    }
```

---

## 5. Judging Framework

### 5.1 Evaluation Criteria

```python
EVALUATION_CRITERIA = {
    'clarity': {
        'weight': 0.20,
        'description': 'How clear and easy to understand is the writing?',
        'scale': '1-5 where 1=confusing/unclear, 5=crystal clear',
    },
    'tone_appropriateness': {
        'weight': 0.15,
        'description': 'Is the tone appropriate for the context, audience, and purpose?',
        'scale': '1-5 where 1=completely wrong tone, 5=perfect tone',
    },
    'task_completion': {
        'weight': 0.25,
        'description': 'Does the writing fully accomplish the stated task?',
        'scale': '1-5 where 1=fails to address task, 5=comprehensively addresses task',
    },
    'effectiveness': {
        'weight': 0.20,
        'description': 'Would this writing achieve its intended purpose with the target audience?',
        'scale': '1-5 where 1=would fail, 5=highly effective',
    },
    'length_appropriateness': {
        'weight': 0.10,
        'description': 'Is the length appropriate? Not too verbose or too brief?',
        'scale': '1-5 where 1=significantly too long/short, 5=ideal length',
    },
    'professionalism': {
        'weight': 0.10,
        'description': 'Grammar, spelling, formatting, and professional polish',
        'scale': '1-5 where 1=many errors, 5=polished and professional',
    },
}
```

### 5.2 Judge Persona Prompts

#### Expert Writer Persona

```python
EXPERT_WRITER_PERSONA = """
You are a senior professional writing consultant with 20+ years of experience
evaluating business writing across industries. You have:
- Trained executives at Fortune 500 companies
- Published guides on effective business communication
- Served as editor for major business publications
- Expertise in correspondence, reports, proposals, and documentation

Your evaluation approach:
- You value clarity above all else
- You recognize that effective writing adapts to audience and context
- You appreciate conciseness but not at the expense of completeness
- You understand that different genres have different conventions
- You evaluate based on whether the writing would achieve its purpose

You are evaluating two pieces of writing (Response A and Response B) for the
same task. You must determine which is better overall, considering all aspects
of effective professional writing.
"""

EXPERT_WRITER_JUDGMENT_PROMPT = """
{persona}

## Original Writing Task
{original_prompt}

## Response A
{response_a}

## Response B
{response_b}

## Evaluation Instructions

Evaluate both responses on each criterion below, then provide your overall judgment.

### Criteria
{criteria_descriptions}

### Your Evaluation

For each criterion, briefly note which response is stronger and why.

Then provide your FINAL VERDICT in exactly this format:
VERDICT: [A is better | B is better | Tie]

Followed by a 2-3 sentence explanation of your overall judgment.
"""
```

#### Target Recipient Persona

```python
TARGET_RECIPIENT_PERSONA_TEMPLATE = """
You are the intended recipient of this writing. Specifically, you are:
{recipient_description}

Your perspective:
- You will read this writing as part of your daily work
- You have limited time and many competing priorities
- You need the writing to help you {recipient_goal}
- You {domain_expertise_level} with the subject matter

Evaluate the writing from your perspective as the actual recipient. Consider:
- Would you find this useful?
- Would you trust the sender based on this writing?
- Would you take the intended action?
- Does it respect your time and intelligence?
"""

def generate_recipient_persona(prompt: dict) -> str:
    """
    Generate a recipient persona based on the writing task context.
    """
    occupation = prompt['occupation_title']
    category = prompt['writing_category']
    industry = prompt['industry']

    # Map writing categories to typical recipients
    recipient_mappings = {
        'correspondence': {
            'recipient_description': f"a busy professional in the {industry} industry",
            'recipient_goal': "understand the situation and know what action to take",
            'domain_expertise_level': "are familiar",
        },
        'reports': {
            'recipient_description': "a senior decision-maker who needs to understand key findings quickly",
            'recipient_goal': "make an informed decision based on this information",
            'domain_expertise_level': "have strategic understanding but may not know technical details",
        },
        'proposals': {
            'recipient_description': "a decision-maker evaluating multiple competing proposals",
            'recipient_goal': "determine if this proposal meets your needs and is worth the investment",
            'domain_expertise_level': "understand the business need but are evaluating solutions",
        },
    }

    mapping = recipient_mappings.get(category, recipient_mappings['correspondence'])

    return TARGET_RECIPIENT_PERSONA_TEMPLATE.format(**mapping)
```

### 5.3 Position Shuffling Implementation

```python
import random
from hashlib import sha256

def create_shuffled_comparison(
    response_a: dict,
    response_b: dict,
    comparison_id: str,
    seed: Optional[int] = None
) -> dict:
    """
    Create a comparison with randomly shuffled positions.
    Returns mapping to recover original positions.
    """
    if seed is None:
        # Deterministic shuffle based on comparison_id
        seed = int(sha256(comparison_id.encode()).hexdigest()[:8], 16)

    random.seed(seed)
    shuffle = random.choice([True, False])

    if shuffle:
        presented_a = response_b
        presented_b = response_a
        position_mapping = {'A': 'B', 'B': 'A'}
    else:
        presented_a = response_a
        presented_b = response_b
        position_mapping = {'A': 'A', 'B': 'B'}

    return {
        'comparison_id': comparison_id,
        'presented_a': presented_a,
        'presented_b': presented_b,
        'position_mapping': position_mapping,
        'was_shuffled': shuffle,
    }

def decode_verdict(verdict: str, position_mapping: dict) -> str:
    """
    Convert verdict back to original model positions.
    """
    verdict = verdict.strip().upper()

    if 'A IS BETTER' in verdict or verdict == 'A':
        original = position_mapping['A']
        return f"{original} is better"
    elif 'B IS BETTER' in verdict or verdict == 'B':
        original = position_mapping['B']
        return f"{original} is better"
    else:
        return 'Tie'
```

### 5.4 Best-of-5 Aggregation

```python
from collections import Counter
from typing import List

def aggregate_judgments(
    judgments: List[dict],
    require_majority: bool = True
) -> dict:
    """
    Aggregate 5 independent judgments into final verdict.
    """
    assert len(judgments) == 5, "Requires exactly 5 judgments"

    # Decode all verdicts to original positions
    decoded_verdicts = []
    for j in judgments:
        decoded = decode_verdict(j['verdict'], j['position_mapping'])
        decoded_verdicts.append(decoded)

    # Count verdicts
    verdict_counts = Counter(decoded_verdicts)

    # Determine winner
    most_common = verdict_counts.most_common()
    winner = most_common[0][0]
    winner_count = most_common[0][1]

    # Calculate confidence
    if winner_count >= 4:
        confidence = 'high'
    elif winner_count >= 3:
        confidence = 'medium'
    else:
        confidence = 'low'
        if require_majority and winner_count < 3:
            winner = 'Tie (no majority)'

    return {
        'final_verdict': winner,
        'verdict_counts': dict(verdict_counts),
        'confidence': confidence,
        'individual_judgments': decoded_verdicts,
        'agreement_rate': winner_count / 5,
    }

async def run_best_of_5_evaluation(
    client: OpenRouterClient,
    prompt: dict,
    response_a: dict,
    response_b: dict,
    judge_personas: List[str]
) -> dict:
    """
    Run 5 independent judgments with shuffled positions.
    """
    judgments = []

    for i in range(5):
        # Alternate between expert and recipient personas
        persona = judge_personas[i % len(judge_personas)]

        # Create shuffled comparison
        comparison = create_shuffled_comparison(
            response_a, response_b,
            comparison_id=f"{prompt['prompt_id']}_{i}"
        )

        # Format judgment prompt
        judgment_prompt = format_judgment_prompt(
            persona=persona,
            original_prompt=prompt['prompt_text'],
            response_a=comparison['presented_a']['response_text'],
            response_b=comparison['presented_b']['response_text'],
        )

        # Get judgment from judge model
        result = await client.complete(
            model_id=JUDGE_MODEL,
            prompt=judgment_prompt,
            temperature=0.3,  # Lower temperature for more consistent judgments
        )

        verdict = extract_verdict(result['choices'][0]['message']['content'])

        judgments.append({
            'judgment_index': i,
            'persona_type': 'expert' if i % 2 == 0 else 'recipient',
            'verdict': verdict,
            'position_mapping': comparison['position_mapping'],
            'raw_response': result['choices'][0]['message']['content'],
        })

    return aggregate_judgments(judgments)
```

---

## 6. Database Schema

### 6.1 SQLite Schema Definition

```sql
-- Core tables for the evaluation framework

-- Prompts table: stores all generated evaluation prompts
CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    prompt_text TEXT NOT NULL,
    onet_task_id TEXT,
    occupation_code TEXT,
    occupation_title TEXT,
    writing_category TEXT,
    industry TEXT,
    has_context BOOLEAN,
    metadata_json TEXT,  -- JSON string for flexible metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prompts_category ON prompts(writing_category);
CREATE INDEX idx_prompts_occupation ON prompts(occupation_code);
CREATE INDEX idx_prompts_industry ON prompts(industry);

-- Model responses table: stores generated writing samples
CREATE TABLE responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    model_key TEXT NOT NULL,
    model_id TEXT NOT NULL,
    response_text TEXT NOT NULL,
    token_count INTEGER,
    generation_time_ms INTEGER,
    finish_reason TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);

CREATE INDEX idx_responses_prompt ON responses(prompt_id);
CREATE INDEX idx_responses_model ON responses(model_key);

-- Comparisons table: stores pairwise comparison metadata
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    model_a_key TEXT NOT NULL,
    model_b_key TEXT NOT NULL,
    response_a_id TEXT NOT NULL,
    response_b_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, error
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
    FOREIGN KEY (response_a_id) REFERENCES responses(response_id),
    FOREIGN KEY (response_b_id) REFERENCES responses(response_id)
);

CREATE INDEX idx_comparisons_models ON comparisons(model_a_key, model_b_key);
CREATE INDEX idx_comparisons_status ON comparisons(status);

-- Individual judgments table: stores each of the 5 judgments per comparison
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL,
    judgment_index INTEGER NOT NULL,  -- 0-4 for best of 5
    persona_type TEXT NOT NULL,  -- 'expert' or 'recipient'
    persona_prompt TEXT,
    presented_order TEXT,  -- 'AB' or 'BA' indicating which was shown first
    position_mapping_json TEXT,  -- JSON mapping presented to original positions
    raw_verdict TEXT,  -- Raw verdict text from judge
    decoded_verdict TEXT,  -- Verdict mapped to original positions
    judgment_reasoning TEXT,  -- Full reasoning from judge
    criteria_scores_json TEXT,  -- JSON with per-criterion evaluations
    judge_model_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
);

CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);

-- Aggregated results table: stores final best-of-5 results
CREATE TABLE comparison_results (
    result_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL UNIQUE,
    final_verdict TEXT NOT NULL,  -- 'model_a', 'model_b', or 'tie'
    winner_model_key TEXT,
    verdict_counts_json TEXT,  -- JSON with vote counts
    confidence TEXT,  -- 'high', 'medium', 'low'
    agreement_rate REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
);

CREATE INDEX idx_results_winner ON comparison_results(winner_model_key);

-- Aggregate statistics view
CREATE VIEW model_pair_stats AS
SELECT
    c.model_a_key,
    c.model_b_key,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN cr.winner_model_key = c.model_a_key THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN cr.winner_model_key = c.model_b_key THEN 1 ELSE 0 END) as model_b_wins,
    SUM(CASE WHEN cr.final_verdict = 'tie' THEN 1 ELSE 0 END) as ties,
    AVG(cr.agreement_rate) as avg_agreement_rate
FROM comparisons c
JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
GROUP BY c.model_a_key, c.model_b_key;

-- Per-category statistics view
CREATE VIEW category_stats AS
SELECT
    p.writing_category,
    c.model_a_key,
    c.model_b_key,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN cr.winner_model_key = c.model_a_key THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN cr.winner_model_key = c.model_b_key THEN 1 ELSE 0 END) as model_b_wins
FROM comparisons c
JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
JOIN prompts p ON c.prompt_id = p.prompt_id
GROUP BY p.writing_category, c.model_a_key, c.model_b_key;
```

### 6.2 Database Manager Implementation

```python
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database with schema."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)  # The SQL above

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_prompt(self, prompt: dict):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO prompts
                (prompt_id, prompt_text, onet_task_id, occupation_code,
                 occupation_title, writing_category, industry, has_context, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt['prompt_id'],
                prompt['prompt_text'],
                prompt.get('onet_task_id'),
                prompt.get('occupation_code'),
                prompt.get('occupation_title'),
                prompt.get('writing_category'),
                prompt.get('industry'),
                prompt.get('has_context', False),
                json.dumps(prompt.get('metadata', {}))
            ))

    def save_response(self, prompt_id: str, response: dict):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO responses
                (response_id, prompt_id, model_key, model_id, response_text,
                 token_count, finish_reason, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                response.get('response_id', f"{prompt_id}_{response['model_key']}"),
                prompt_id,
                response['model_key'],
                response['model_id'],
                response.get('response_text', ''),
                response.get('usage', {}).get('completion_tokens'),
                response.get('finish_reason'),
                response.get('error'),
            ))

    def save_comparison_result(self, comparison_id: str, result: dict):
        with self.get_connection() as conn:
            # Save individual judgments
            for j in result.get('judgments', []):
                conn.execute("""
                    INSERT INTO judgments
                    (judgment_id, comparison_id, judgment_index, persona_type,
                     position_mapping_json, raw_verdict, decoded_verdict, judgment_reasoning)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{comparison_id}_j{j['judgment_index']}",
                    comparison_id,
                    j['judgment_index'],
                    j['persona_type'],
                    json.dumps(j['position_mapping']),
                    j['verdict'],
                    j.get('decoded_verdict'),
                    j.get('raw_response'),
                ))

            # Save aggregated result
            conn.execute("""
                INSERT INTO comparison_results
                (result_id, comparison_id, final_verdict, winner_model_key,
                 verdict_counts_json, confidence, agreement_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"{comparison_id}_result",
                comparison_id,
                result['final_verdict'],
                result.get('winner_model_key'),
                json.dumps(result['verdict_counts']),
                result['confidence'],
                result['agreement_rate'],
            ))

    def get_model_pair_stats(self) -> list:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM model_pair_stats")
            return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(self, output_dir: Path):
        """Export all tables to CSV files."""
        import csv

        output_dir.mkdir(parents=True, exist_ok=True)

        tables = ['prompts', 'responses', 'comparisons', 'judgments', 'comparison_results']

        with self.get_connection() as conn:
            for table in tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()

                if rows:
                    with open(output_dir / f"{table}.csv", 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([d[0] for d in cursor.description])
                        writer.writerows(rows)
```

---

## 7. Execution Pipeline

### 7.1 Main Orchestrator

```python
#!/usr/bin/env python3
"""
main.py - Main execution pipeline for writing evaluation
"""

import asyncio
import argparse
from pathlib import Path
from datetime import datetime

class EvaluationPipeline:
    def __init__(self, config: dict):
        self.config = config
        self.db = DatabaseManager(Path(config['db_path']))
        self.client = OpenRouterClient()
        self.prompt_generator = PromptGenerator(self.db.conn)

    async def run_full_evaluation(self):
        """Execute complete evaluation pipeline."""
        print("Starting Writing Evaluation Pipeline")
        print("=" * 50)

        # Phase 1: Generate prompts
        print("\n[Phase 1] Generating evaluation prompts...")
        prompts = await self.generate_prompts()
        print(f"Generated {len(prompts)} prompts")

        # Phase 2: Generate model responses
        print("\n[Phase 2] Generating model responses...")
        responses = await self.generate_responses(prompts)
        print(f"Generated responses from {len(self.config['models'])} models")

        # Phase 3: Run pairwise comparisons
        print("\n[Phase 3] Running pairwise comparisons...")
        comparisons = await self.run_comparisons(prompts, responses)
        print(f"Completed {len(comparisons)} comparisons")

        # Phase 4: Generate analysis and report
        print("\n[Phase 4] Generating analysis and report...")
        await self.generate_report()

        print("\n" + "=" * 50)
        print("Evaluation complete!")

    async def generate_prompts(self) -> list:
        """Generate all evaluation prompts."""
        prompts = self.prompt_generator.generate_batch(
            n_prompts=self.config['n_prompts'],
            context_ratio=self.config['context_ratio']
        )

        for prompt in prompts:
            self.db.save_prompt(prompt)

        return prompts

    async def generate_responses(self, prompts: list) -> dict:
        """Generate responses from all models for all prompts."""
        all_responses = {}

        for prompt in prompts:
            prompt_responses = await generate_all_responses(
                self.client,
                prompt,
                self.config['models']
            )

            for model_key, response in prompt_responses['responses'].items():
                self.db.save_response(prompt['prompt_id'], response)

            all_responses[prompt['prompt_id']] = prompt_responses

        return all_responses

    async def run_comparisons(self, prompts: list, responses: dict) -> list:
        """Run all pairwise comparisons."""
        target_models = [m for m, cfg in EVAL_MODELS.items() if cfg['is_target']]
        competitor_models = [m for m, cfg in EVAL_MODELS.items() if not cfg['is_target']]

        comparisons = []

        for prompt in prompts:
            prompt_responses = responses[prompt['prompt_id']]['responses']

            # Compare each target model against each competitor
            for target in target_models:
                for competitor in competitor_models:
                    if target in prompt_responses and competitor in prompt_responses:
                        comparison = await self.run_single_comparison(
                            prompt,
                            prompt_responses[target],
                            prompt_responses[competitor],
                            target,
                            competitor
                        )
                        comparisons.append(comparison)

        return comparisons

    async def run_single_comparison(
        self,
        prompt: dict,
        response_a: dict,
        response_b: dict,
        model_a_key: str,
        model_b_key: str
    ) -> dict:
        """Run best-of-5 comparison between two responses."""
        comparison_id = f"{prompt['prompt_id']}_{model_a_key}_vs_{model_b_key}"

        # Generate recipient persona for this prompt
        recipient_persona = generate_recipient_persona(prompt)
        judge_personas = [EXPERT_WRITER_PERSONA, recipient_persona]

        result = await run_best_of_5_evaluation(
            self.client,
            prompt,
            response_a,
            response_b,
            judge_personas
        )

        # Determine winner model key
        if 'A is better' in result['final_verdict']:
            result['winner_model_key'] = model_a_key
        elif 'B is better' in result['final_verdict']:
            result['winner_model_key'] = model_b_key
        else:
            result['winner_model_key'] = None

        self.db.save_comparison_result(comparison_id, result)

        return {
            'comparison_id': comparison_id,
            'prompt_id': prompt['prompt_id'],
            'model_a': model_a_key,
            'model_b': model_b_key,
            **result
        }


async def main():
    parser = argparse.ArgumentParser(description='Run Writing Evaluation')
    parser.add_argument('--n-prompts', type=int, default=500)
    parser.add_argument('--db-path', default='data/eval.db')
    parser.add_argument('--output-dir', default='output')
    args = parser.parse_args()

    config = {
        'n_prompts': args.n_prompts,
        'db_path': args.db_path,
        'output_dir': args.output_dir,
        'context_ratio': 0.4,
        'models': list(EVAL_MODELS.keys()),
    }

    pipeline = EvaluationPipeline(config)
    await pipeline.run_full_evaluation()


if __name__ == "__main__":
    asyncio.run(main())
```

### 7.2 CLI Commands

```python
# cli.py - Command-line interface for the evaluation framework

import click
import asyncio

@click.group()
def cli():
    """Writing Evaluation Framework CLI"""
    pass

@cli.command()
@click.option('--n-prompts', default=500, help='Number of prompts to generate')
def generate_prompts(n_prompts):
    """Generate evaluation prompts from O*NET data."""
    # Implementation

@cli.command()
@click.option('--prompt-id', help='Specific prompt to evaluate')
def generate_responses(prompt_id):
    """Generate model responses for prompts."""
    # Implementation

@cli.command()
@click.option('--model-pair', help='Specific model pair (e.g., gemini-pro:gpt-5)')
def run_comparisons(model_pair):
    """Run pairwise comparisons."""
    # Implementation

@cli.command()
def export_csv():
    """Export all data to CSV files."""
    # Implementation

@cli.command()
@click.option('--output', default='report.pdf', help='Output PDF path')
def generate_report(output):
    """Generate final PDF report."""
    # Implementation

@cli.command()
@click.option('--comparison-id', required=True)
def inspect(comparison_id):
    """Inspect a specific comparison in detail."""
    # Implementation

if __name__ == '__main__':
    cli()
```

---

## 8. Analysis & Reporting

### 8.1 Statistical Analysis

```python
import pandas as pd
import numpy as np
from scipy import stats

class EvalAnalyzer:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def compute_win_rates(self) -> pd.DataFrame:
        """Compute win rates for all model pairs."""
        stats = self.db.get_model_pair_stats()

        results = []
        for row in stats:
            total = row['total_comparisons']
            results.append({
                'model_a': row['model_a_key'],
                'model_b': row['model_b_key'],
                'model_a_win_rate': row['model_a_wins'] / total,
                'model_b_win_rate': row['model_b_wins'] / total,
                'tie_rate': row['ties'] / total,
                'total_comparisons': total,
                'agreement_rate': row['avg_agreement_rate'],
            })

        return pd.DataFrame(results)

    def compute_confidence_intervals(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple:
        """Compute Wilson score confidence interval for win rate."""
        if total == 0:
            return (0, 0)

        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = wins / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        spread = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator

        return (center - spread, center + spread)

    def identify_weaknesses(self, target_model: str) -> dict:
        """Identify specific weakness patterns for a target model."""
        with self.db.get_connection() as conn:
            # By writing category
            category_query = """
                SELECT
                    p.writing_category,
                    COUNT(*) as total,
                    SUM(CASE WHEN cr.winner_model_key != ? THEN 1 ELSE 0 END) as losses
                FROM comparisons c
                JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
                JOIN prompts p ON c.prompt_id = p.prompt_id
                WHERE c.model_a_key = ? OR c.model_b_key = ?
                GROUP BY p.writing_category
            """
            category_results = conn.execute(
                category_query, (target_model, target_model, target_model)
            ).fetchall()

            # By competitor
            competitor_query = """
                SELECT
                    CASE
                        WHEN c.model_a_key = ? THEN c.model_b_key
                        ELSE c.model_a_key
                    END as competitor,
                    COUNT(*) as total,
                    SUM(CASE WHEN cr.winner_model_key != ? THEN 1 ELSE 0 END) as losses
                FROM comparisons c
                JOIN comparison_results cr ON c.comparison_id = cr.comparison_id
                WHERE c.model_a_key = ? OR c.model_b_key = ?
                GROUP BY competitor
            """
            competitor_results = conn.execute(
                competitor_query, (target_model, target_model, target_model, target_model)
            ).fetchall()

        return {
            'by_category': [dict(r) for r in category_results],
            'by_competitor': [dict(r) for r in competitor_results],
        }
```

### 8.2 Visualization Generation

```python
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

class EvalVisualizer:
    def __init__(self, analyzer: EvalAnalyzer, output_dir: Path):
        self.analyzer = analyzer
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set style
        sns.set_theme(style="whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)

    def plot_win_rate_heatmap(self) -> Path:
        """Generate heatmap of win rates between all model pairs."""
        win_rates = self.analyzer.compute_win_rates()

        # Pivot to matrix form
        models = sorted(set(win_rates['model_a'].unique()) |
                       set(win_rates['model_b'].unique()))

        matrix = pd.DataFrame(index=models, columns=models, dtype=float)

        for _, row in win_rates.iterrows():
            matrix.loc[row['model_a'], row['model_b']] = row['model_a_win_rate']
            matrix.loc[row['model_b'], row['model_a']] = row['model_b_win_rate']

        # Plot
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(
            matrix.astype(float),
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            center=0.5,
            ax=ax
        )
        ax.set_title('Win Rate Matrix (Row Model vs Column Model)')

        output_path = self.output_dir / 'win_rate_heatmap.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return output_path

    def plot_category_performance(self, model: str) -> Path:
        """Plot performance breakdown by writing category."""
        weaknesses = self.analyzer.identify_weaknesses(model)

        df = pd.DataFrame(weaknesses['by_category'])
        df['win_rate'] = 1 - (df['losses'] / df['total'])

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.barh(df['writing_category'], df['win_rate'])

        # Color bars based on performance
        for bar, rate in zip(bars, df['win_rate']):
            if rate < 0.4:
                bar.set_color('red')
            elif rate < 0.5:
                bar.set_color('orange')
            else:
                bar.set_color('green')

        ax.axvline(x=0.5, color='black', linestyle='--', alpha=0.5)
        ax.set_xlabel('Win Rate')
        ax.set_title(f'{model} Performance by Writing Category')
        ax.set_xlim(0, 1)

        output_path = self.output_dir / f'{model}_category_performance.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return output_path

    def plot_head_to_head(self, model_a: str, model_b: str) -> Path:
        """Plot detailed head-to-head comparison."""
        # Implementation for head-to-head visualization
        pass

    def generate_all_visualizations(self) -> list:
        """Generate all standard visualizations."""
        paths = []

        paths.append(self.plot_win_rate_heatmap())

        for model_key, config in EVAL_MODELS.items():
            if config['is_target']:
                paths.append(self.plot_category_performance(model_key))

        return paths
```

### 8.3 PDF Report Generation

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class ReportGenerator:
    def __init__(self, analyzer: EvalAnalyzer, visualizer: EvalVisualizer):
        self.analyzer = analyzer
        self.visualizer = visualizer
        self.styles = getSampleStyleSheet()

    def generate_pdf_report(self, output_path: Path) -> Path:
        """Generate comprehensive PDF report."""
        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        story = []

        # Title
        story.append(Paragraph(
            "Gemini Writing Evaluation Report",
            self.styles['Title']
        ))
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['Heading1']))
        summary = self._generate_executive_summary()
        story.append(Paragraph(summary, self.styles['Normal']))
        story.append(Spacer(1, 20))

        # Methodology
        story.append(Paragraph("Methodology", self.styles['Heading1']))
        story.append(Paragraph(self._methodology_text(), self.styles['Normal']))
        story.append(Spacer(1, 20))

        # Overall Results
        story.append(Paragraph("Overall Results", self.styles['Heading1']))

        # Win rate heatmap
        heatmap_path = self.visualizer.plot_win_rate_heatmap()
        story.append(Image(str(heatmap_path), width=450, height=350))
        story.append(Spacer(1, 20))

        # Per-model analysis
        for model_key, config in EVAL_MODELS.items():
            if config['is_target']:
                story.append(Paragraph(
                    f"{config['display_name']} Analysis",
                    self.styles['Heading2']
                ))

                analysis = self._generate_model_analysis(model_key)
                story.append(Paragraph(analysis, self.styles['Normal']))

                perf_path = self.visualizer.plot_category_performance(model_key)
                story.append(Image(str(perf_path), width=400, height=300))
                story.append(Spacer(1, 20))

        # Identified Weaknesses
        story.append(Paragraph("Identified Weaknesses", self.styles['Heading1']))
        weaknesses = self._identify_key_weaknesses()
        story.append(Paragraph(weaknesses, self.styles['Normal']))

        # Build PDF
        doc.build(story)
        return output_path

    def _generate_executive_summary(self) -> str:
        """Generate executive summary text."""
        win_rates = self.analyzer.compute_win_rates()

        # Calculate overall standings
        gemini_pro_avg = win_rates[
            win_rates['model_a'] == 'gemini-3.0-pro'
        ]['model_a_win_rate'].mean()

        return f"""
        This report presents the results of a comprehensive writing evaluation
        comparing Gemini 3.0 Pro and Flash against leading frontier models
        across {win_rates['total_comparisons'].sum()} pairwise comparisons.

        Key Finding: Gemini 3.0 Pro achieved an average win rate of
        {gemini_pro_avg:.1%} across all competitor comparisons.
        """

    def _methodology_text(self) -> str:
        return """
        Evaluation Methodology:
        - Tasks derived from O*NET occupational database covering all US job types
        - Pairwise comparisons with position shuffling to eliminate bias
        - Best of 5 judgments using dual personas (expert writer + target recipient)
        - Aggregate win rates computed with confidence intervals
        """

    def _generate_model_analysis(self, model_key: str) -> str:
        weaknesses = self.analyzer.identify_weaknesses(model_key)
        # Generate analysis text
        return f"Analysis for {model_key}..."

    def _identify_key_weaknesses(self) -> str:
        # Identify and describe key weaknesses
        return "Key weaknesses identified..."
```

---

## 9. Quality Assurance

### 9.1 Validation Checks

```python
class QualityAssurance:
    """Quality assurance checks for the evaluation framework."""

    @staticmethod
    def validate_prompt_coverage(db: DatabaseManager) -> dict:
        """Ensure prompts cover required dimensions."""
        with db.get_connection() as conn:
            # Check writing category distribution
            categories = conn.execute("""
                SELECT writing_category, COUNT(*) as count
                FROM prompts
                GROUP BY writing_category
            """).fetchall()

            # Check industry distribution
            industries = conn.execute("""
                SELECT industry, COUNT(*) as count
                FROM prompts
                GROUP BY industry
            """).fetchall()

            # Check occupation coverage
            occupations = conn.execute("""
                SELECT COUNT(DISTINCT occupation_code) as unique_occupations
                FROM prompts
            """).fetchone()

        return {
            'category_distribution': dict(categories),
            'industry_distribution': dict(industries),
            'unique_occupations': occupations['unique_occupations'],
        }

    @staticmethod
    def validate_response_quality(response: dict) -> dict:
        """Validate a model response meets quality standards."""
        text = response.get('response_text', '')

        checks = {
            'non_empty': len(text.strip()) > 0,
            'minimum_length': len(text) >= 50,
            'no_error': response.get('error') is None,
            'completed': response.get('finish_reason') == 'stop',
            'not_truncated': response.get('finish_reason') != 'length',
        }

        return {
            'passed': all(checks.values()),
            'checks': checks,
        }

    @staticmethod
    def validate_judgment_consistency(judgments: list) -> dict:
        """Check for suspicious judgment patterns."""
        verdicts = [j['decoded_verdict'] for j in judgments]

        # Check for position bias
        raw_verdicts = [j['verdict'] for j in judgments]
        a_raw_count = sum(1 for v in raw_verdicts if 'A' in v.upper())

        return {
            'agreement_rate': max(Counter(verdicts).values()) / len(verdicts),
            'potential_position_bias': abs(a_raw_count - 2.5) > 2,
            'all_same': len(set(verdicts)) == 1,
        }

    @staticmethod
    def run_bias_detection(db: DatabaseManager) -> dict:
        """Detect systematic biases in judgments."""
        with db.get_connection() as conn:
            # Check if 'A' position wins more often (before decoding)
            position_bias = conn.execute("""
                SELECT
                    raw_verdict,
                    COUNT(*) as count
                FROM judgments
                GROUP BY raw_verdict
            """).fetchall()

            # Check agreement rates
            agreement = conn.execute("""
                SELECT AVG(agreement_rate) as avg_agreement
                FROM comparison_results
            """).fetchone()

        return {
            'position_verdict_distribution': dict(position_bias),
            'average_agreement_rate': agreement['avg_agreement'],
        }
```

### 9.2 Testing Suite

```python
import pytest

class TestEvaluationFramework:
    """Test suite for the evaluation framework."""

    def test_prompt_generation(self):
        """Test prompt generation produces valid prompts."""
        generator = PromptGenerator(mock_db_conn)
        prompts = generator.generate_batch(n_prompts=10)

        assert len(prompts) == 10
        for prompt in prompts:
            assert validate_context(prompt)

    def test_position_shuffling(self):
        """Test that position shuffling is random but deterministic."""
        response_a = {'response_text': 'Response A text'}
        response_b = {'response_text': 'Response B text'}

        # Same comparison_id should give same shuffle
        comp1 = create_shuffled_comparison(response_a, response_b, 'test_id_1')
        comp2 = create_shuffled_comparison(response_a, response_b, 'test_id_1')
        assert comp1['was_shuffled'] == comp2['was_shuffled']

        # Different IDs should (eventually) give different shuffles
        shuffles = set()
        for i in range(100):
            comp = create_shuffled_comparison(response_a, response_b, f'test_{i}')
            shuffles.add(comp['was_shuffled'])
        assert len(shuffles) == 2  # Both True and False should appear

    def test_verdict_aggregation(self):
        """Test best-of-5 aggregation logic."""
        # Clear winner
        judgments = [
            {'verdict': 'A is better', 'position_mapping': {'A': 'A', 'B': 'B'}}
        ] * 4 + [
            {'verdict': 'B is better', 'position_mapping': {'A': 'A', 'B': 'B'}}
        ]
        result = aggregate_judgments(judgments)
        assert result['final_verdict'] == 'A is better'
        assert result['confidence'] == 'high'

        # Split decision
        judgments = [
            {'verdict': 'A is better', 'position_mapping': {'A': 'A', 'B': 'B'}}
        ] * 3 + [
            {'verdict': 'B is better', 'position_mapping': {'A': 'A', 'B': 'B'}}
        ] * 2
        result = aggregate_judgments(judgments)
        assert result['confidence'] == 'medium'

    def test_database_operations(self, tmp_path):
        """Test database CRUD operations."""
        db = DatabaseManager(tmp_path / 'test.db')

        # Test prompt save/retrieve
        prompt = {'prompt_id': 'test_1', 'prompt_text': 'Test prompt'}
        db.save_prompt(prompt)

        with db.get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM prompts WHERE prompt_id = ?",
                ('test_1',)
            ).fetchone()

        assert result is not None
        assert result['prompt_text'] == 'Test prompt'
```

---

## 10. Project Structure

```
writing-eval/
├── src/
│   ├── __init__.py
│   ├── onet/
│   │   ├── __init__.py
│   │   ├── downloader.py      # O*NET data download
│   │   └── parser.py          # O*NET data parsing
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py       # Prompt generation
│   │   ├── templates.py       # Prompt templates
│   │   └── context.py         # Context generation
│   ├── models/
│   │   ├── __init__.py
│   │   ├── client.py          # OpenRouter client
│   │   └── config.py          # Model configurations
│   ├── judging/
│   │   ├── __init__.py
│   │   ├── personas.py        # Judge personas
│   │   ├── rubrics.py         # Evaluation rubrics
│   │   └── aggregation.py     # Best-of-5 aggregation
│   ├── database/
│   │   ├── __init__.py
│   │   ├── manager.py         # Database operations
│   │   └── schema.sql         # Schema definition
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py      # Statistical analysis
│   │   ├── visualization.py   # Plot generation
│   │   └── report.py          # PDF report generation
│   └── qa/
│       ├── __init__.py
│       └── validation.py      # Quality assurance
├── tests/
│   ├── test_prompts.py
│   ├── test_judging.py
│   └── test_database.py
├── data/
│   ├── onet_raw/              # Raw O*NET downloads
│   └── eval.db                # SQLite database
├── output/
│   ├── csv/                   # CSV exports
│   ├── visualizations/        # Generated plots
│   └── reports/               # PDF reports
├── cli.py                     # Command-line interface
├── main.py                    # Main entry point
├── requirements.txt
└── README.md
```

---

## 11. Implementation Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| 1. Setup | 2 days | Project structure, dependencies, O*NET download |
| 2. Data Pipeline | 3 days | O*NET parsing, writing task extraction, industry mapping |
| 3. Prompt Generation | 3 days | Templates, context generation, validation |
| 4. Model Integration | 2 days | OpenRouter client, response generation |
| 5. Judging Framework | 4 days | Personas, rubrics, shuffling, aggregation |
| 6. Database & Storage | 2 days | Schema implementation, CRUD operations |
| 7. Analysis & Reporting | 3 days | Statistics, visualizations, PDF generation |
| 8. QA & Testing | 2 days | Test suite, bias detection, validation |
| 9. Full Run & Debug | 3 days | End-to-end execution, bug fixes |

**Total Estimated Duration: ~24 days**

---

## 12. Requirements

```
# requirements.txt
httpx>=0.24.0
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
matplotlib>=3.7.0
seaborn>=0.12.0
reportlab>=4.0.0
sqlite-utils>=3.30
click>=8.1.0
pytest>=7.3.0
python-dotenv>=1.0.0
```

---

## Appendix A: Sample Evaluation Output

```
================================================================================
WRITING EVALUATION: Gemini 3.0 Pro vs GPT-5.2
================================================================================

Prompt ID: prompt_00142
Occupation: Chief Executive (11-1011.00)
Industry: Technology Startup
Category: Correspondence
Has Context: Yes

Task: Write an email to the board of directors explaining the need for an
additional funding round despite missing Q3 targets.

--------------------------------------------------------------------------------
RESPONSE A (Position: First)
--------------------------------------------------------------------------------
Subject: Strategic Funding Discussion - Q4 Board Meeting

Dear Board Members,

I'm writing to request time on our upcoming board agenda to discuss a
proposed Series C extension...
[truncated for brevity]

--------------------------------------------------------------------------------
RESPONSE B (Position: Second)
--------------------------------------------------------------------------------
Subject: Request for Board Discussion: Funding Strategy Update

Dear Members of the Board,

As we approach our Q4 planning cycle, I want to proactively address our
capital position and propose a path forward...
[truncated for brevity]

--------------------------------------------------------------------------------
JUDGMENTS (Best of 5)
--------------------------------------------------------------------------------
Judge 1 (Expert Writer): A is better
  - Response A more directly addresses the sensitive topic
  - Better balance of accountability and forward-looking optimism

Judge 2 (Target Recipient - Board Member): B is better
  - Response B demonstrates stronger strategic thinking
  - More appropriate level of detail for board communication

Judge 3 (Expert Writer): A is better
  - Clearer structure and more actionable ask

Judge 4 (Target Recipient - Board Member): A is better
  - More concise, respects board members' time

Judge 5 (Expert Writer): A is better

--------------------------------------------------------------------------------
FINAL VERDICT: A is better (4-1)
Confidence: High
Agreement Rate: 80%

Original Positions: A = Gemini 3.0 Pro, B = GPT-5.2
WINNER: Gemini 3.0 Pro
================================================================================
```

---

This implementation plan provides a comprehensive framework for evaluating Gemini's writing capabilities against frontier models. The design emphasizes methodological rigor through position shuffling, dual-judge personas, and best-of-5 aggregation while maintaining practical executability through SQLite storage, OpenRouter integration, and automated reporting.
