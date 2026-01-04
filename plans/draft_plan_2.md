# Gemini Writing Evaluation Framework: Comprehensive Implementation Plan

## Executive Summary

This document outlines a rigorous evaluation framework for comparing Gemini 3.0 Pro and Flash against competing frontier models (GPT-5.2, Claude Opus 4.5, Grok-3, Kimi-2, DeepSeek-V3) on realistic writing tasks derived from the O*NET occupational database. The framework employs pairwise comparisons with dual-persona judging, position shuffling, and best-of-5 aggregation to produce statistically robust results.

---

## 1. O*NET Data Pipeline

### 1.1 Data Source Overview

O*NET (Occupational Information Network) is the primary source for US occupational data, maintained by the US Department of Labor. The database contains detailed information about 1,000+ occupations including tasks, skills, and work activities.

**Key O*NET Files for Writing Tasks:**
- `Task Statements.txt` - Individual tasks per occupation
- `Work Activities.txt` - Generalized work activities (includes "Communicating" activities)
- `Skills.txt` - Skills data including "Writing" skill importance ratings
- `Occupation Data.txt` - Master occupation list with O*NET-SOC codes

### 1.2 Download Script

```python
#!/usr/bin/env python3
"""
onet_downloader.py - Downloads and extracts O*NET database files
"""

import os
import requests
import zipfile
from pathlib import Path

ONET_VERSION = "29_1"  # Update to latest version
ONET_BASE_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION}_text.zip"
DATA_DIR = Path("data/onet")

def download_onet():
    """Download O*NET database ZIP file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / f"onet_{ONET_VERSION}.zip"

    if not zip_path.exists():
        print(f"Downloading O*NET {ONET_VERSION}...")
        response = requests.get(ONET_BASE_URL, stream=True)
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

def load_onet_tables(extract_dir):
    """Load relevant O*NET tables into pandas DataFrames."""
    import pandas as pd

    tables = {}
    files = [
        "Task Statements.txt",
        "Work Activities.txt",
        "Skills.txt",
        "Occupation Data.txt",
        "Content Model Reference.txt"
    ]

    for filename in files:
        filepath = extract_dir / filename
        if filepath.exists():
            tables[filename.replace(".txt", "")] = pd.read_csv(
                filepath, sep='\t', encoding='utf-8'
            )

    return tables

if __name__ == "__main__":
    extract_dir = download_onet()
    tables = load_onet_tables(extract_dir)
    print(f"Loaded {len(tables)} tables")
```

### 1.3 Writing Task Extraction

```python
#!/usr/bin/env python3
"""
extract_writing_tasks.py - Identifies occupations with significant writing requirements
"""

import pandas as pd
from pathlib import Path

# Writing-related keywords for task identification
WRITING_KEYWORDS = [
    'write', 'writing', 'draft', 'compose', 'document', 'report',
    'email', 'memo', 'letter', 'proposal', 'communicate in writing',
    'correspondence', 'manuscript', 'article', 'brief', 'statement',
    'presentation', 'script', 'content', 'copy', 'edit', 'proofread',
    'newsletter', 'blog', 'post', 'summary', 'narrative', 'description'
]

def identify_writing_occupations(tables):
    """
    Identify occupations with significant writing requirements.
    Returns occupations where Writing skill importance >= 3.0 (scale 1-5)
    """
    skills_df = tables["Skills"]

    # Filter for Writing skill (Element ID: 2.A.1.a)
    writing_skills = skills_df[
        (skills_df['Element ID'] == '2.A.1.a') &
        (skills_df['Scale ID'] == 'IM') &  # Importance scale
        (skills_df['Data Value'] >= 3.0)
    ]

    return writing_skills['O*NET-SOC Code'].unique()

def extract_writing_tasks(tables, occupation_codes):
    """
    Extract specific writing-related tasks for identified occupations.
    """
    tasks_df = tables["Task Statements"]

    # Filter to relevant occupations
    occ_tasks = tasks_df[tasks_df['O*NET-SOC Code'].isin(occupation_codes)]

    # Identify writing-related tasks via keyword matching
    def is_writing_task(task_text):
        task_lower = task_text.lower()
        return any(kw in task_lower for kw in WRITING_KEYWORDS)

    writing_tasks = occ_tasks[
        occ_tasks['Task'].apply(is_writing_task)
    ].copy()

    return writing_tasks

def enrich_with_occupation_info(writing_tasks, tables):
    """Add occupation titles and industry information."""
    occ_df = tables["Occupation Data"]

    enriched = writing_tasks.merge(
        occ_df[['O*NET-SOC Code', 'Title', 'Description']],
        on='O*NET-SOC Code',
        how='left'
    )

    return enriched
```

### 1.4 Expected Output Structure

The extraction pipeline produces a structured dataset with:
- ~400-600 occupations with significant writing requirements
- 2,000-5,000 specific writing-related tasks
- Coverage across all 23 major occupation groups (SOC codes 11-53)

---

## 2. Eval Prompt Generation

### 2.1 Prompt Generation Methodology

Each writing task from O*NET is transformed into a concrete eval prompt with:

1. **Job Context**: Specific occupation and industry variant
2. **Task Description**: The actual writing deliverable needed
3. **Audience**: Who will receive/read the writing
4. **Constraints**: Length, tone, format requirements

### 2.2 Industry Diversification

For each occupation, generate 3-5 industry variants:

```python
INDUSTRY_VARIANTS = {
    "11-1011.00": {  # Chief Executives
        "base_title": "Chief Executive Officer",
        "variants": [
            {"industry": "Technology Startup", "context": "50-person Series B software company"},
            {"industry": "Non-profit", "context": "Regional food bank with 200 volunteers"},
            {"industry": "Agriculture", "context": "Family-owned fruit distribution company"},
            {"industry": "Healthcare", "context": "Regional hospital network"},
            {"industry": "Retail", "context": "Specialty retail chain with 30 locations"}
        ]
    },
    "15-1252.00": {  # Software Developers
        "base_title": "Software Developer",
        "variants": [
            {"industry": "Fintech", "context": "Payment processing platform"},
            {"industry": "Healthcare", "context": "Electronic health records company"},
            {"industry": "Gaming", "context": "Mobile game studio"},
            {"industry": "Enterprise", "context": "B2B SaaS company"},
            {"industry": "Automotive", "context": "Self-driving vehicle company"}
        ]
    }
    # ... expanded for all occupations
}
```

### 2.3 Prompt Template System

```python
PROMPT_TEMPLATES = {
    "simple": {
        "template": """You are a {job_title} at a {industry_context}.

Write a {document_type} to {recipient_description}.

Topic: {task_topic}

Requirements:
- Appropriate professional tone
- Clear and concise
- {length_guidance}""",
        "requires_context": False
    },

    "with_context": {
        "template": """You are a {job_title} at a {industry_context}.

BACKGROUND INFORMATION:
{background_context}

TASK:
Write a {document_type} to {recipient_description}.

Topic: {task_topic}

Requirements:
- Incorporate the relevant background information
- Appropriate professional tone
- {length_guidance}""",
        "requires_context": True
    }
}

def generate_eval_prompt(task_row, industry_variant, template_type="simple", context=None):
    """Generate a complete evaluation prompt from task data."""

    template = PROMPT_TEMPLATES[template_type]["template"]

    prompt = template.format(
        job_title=task_row['Title'],
        industry_context=industry_variant['context'],
        document_type=infer_document_type(task_row['Task']),
        recipient_description=infer_recipient(task_row['Task']),
        task_topic=extract_topic(task_row['Task']),
        length_guidance=determine_length_guidance(task_row['Task']),
        background_context=context or ""
    )

    return prompt
```

### 2.4 Document Type Inference

```python
DOCUMENT_TYPE_PATTERNS = {
    r'report': 'detailed report',
    r'email|memo': 'professional email',
    r'proposal': 'business proposal',
    r'letter': 'formal letter',
    r'presentation': 'presentation script/outline',
    r'policy|procedure': 'policy document',
    r'summary|brief': 'executive summary',
    r'article|blog': 'article',
    r'review|evaluation': 'performance review',
    r'instruction|guide': 'instructional guide'
}

def infer_document_type(task_text):
    """Infer the type of document from task description."""
    task_lower = task_text.lower()

    for pattern, doc_type in DOCUMENT_TYPE_PATTERNS.items():
        if re.search(pattern, task_lower):
            return doc_type

    return 'professional written communication'
```

---

## 3. Context Generation

### 3.1 Context Requirements Analysis

Approximately 40% of eval prompts require additional context to be realistic. Context types include:

| Context Type | Example | Generation Method |
|-------------|---------|-------------------|
| Data/Metrics | Quarterly sales figures | Synthetic generation |
| Prior Communication | Email thread to respond to | LLM generation |
| Policy/Procedure | Existing company policy to update | Template + variation |
| Technical Specs | Product requirements | Domain templates |
| Meeting Notes | Discussion to summarize | LLM generation |

### 3.2 Synthetic Context Generator

```python
import json
import random

class ContextGenerator:
    """Generates realistic context for writing tasks."""

    def __init__(self, llm_client):
        self.llm = llm_client
        self.templates = self._load_templates()

    def generate_context(self, task_type, industry, job_title):
        """Generate appropriate context based on task requirements."""

        if task_type == "data_report":
            return self._generate_metrics_context(industry)
        elif task_type == "email_response":
            return self._generate_email_thread(industry, job_title)
        elif task_type == "meeting_summary":
            return self._generate_meeting_notes(industry)
        elif task_type == "policy_update":
            return self._generate_existing_policy(industry)
        else:
            return self._generate_generic_context(task_type, industry)

    def _generate_metrics_context(self, industry):
        """Generate realistic business metrics."""
        template = """
QUARTERLY PERFORMANCE DATA - Q3 2025

Revenue: ${revenue:,}
Previous Quarter: ${prev_revenue:,}
Year-over-Year Change: {yoy_change}%

Key Metrics:
- Customer Acquisition: {new_customers:,} new customers
- Customer Retention Rate: {retention}%
- Average Order Value: ${aov:.2f}
- Net Promoter Score: {nps}

Regional Breakdown:
- Northeast: {ne_pct}% of revenue
- Southeast: {se_pct}% of revenue
- Midwest: {mw_pct}% of revenue
- West: {w_pct}% of revenue

Notable Events:
{notable_events}
"""
        # Generate realistic random values
        revenue = random.randint(5_000_000, 500_000_000)
        prev_revenue = int(revenue * random.uniform(0.85, 1.15))

        return template.format(
            revenue=revenue,
            prev_revenue=prev_revenue,
            yoy_change=round(random.uniform(-15, 30), 1),
            new_customers=random.randint(1000, 50000),
            retention=round(random.uniform(75, 95), 1),
            aov=random.uniform(50, 500),
            nps=random.randint(20, 80),
            ne_pct=random.randint(15, 35),
            se_pct=random.randint(15, 35),
            mw_pct=random.randint(15, 35),
            w_pct=random.randint(15, 35),
            notable_events=self._generate_notable_events(industry)
        )

    def _generate_email_thread(self, industry, job_title):
        """Use LLM to generate realistic email thread for response."""
        prompt = f"""Generate a realistic 2-3 email thread in the {industry} industry
        that a {job_title} would need to respond to. Include:
        - A request or question that needs a substantive response
        - Some context about an ongoing project or issue
        - Professional but not overly formal tone

        Format as:
        FROM: [name and title]
        TO: [recipient]
        SUBJECT: [subject line]
        DATE: [date]

        [email body]

        ---
        [next email in thread]
        """

        response = self.llm.generate(prompt, max_tokens=800)
        return response
```

### 3.3 Context Validation

All generated context undergoes validation:

```python
def validate_context(context, task_type):
    """Ensure generated context is appropriate and coherent."""

    checks = {
        "minimum_length": len(context) >= 200,
        "no_placeholder_text": "[" not in context or "]" not in context,
        "no_lorem_ipsum": "lorem" not in context.lower(),
        "has_specifics": bool(re.search(r'\d+', context)),  # Contains numbers
        "professional_tone": not any(w in context.lower() for w in ['lol', 'gonna', 'wanna'])
    }

    return all(checks.values()), checks
```

---

## 4. Model Integration

### 4.1 OpenRouter API Configuration

```python
import os
import httpx
from typing import Optional
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential

@dataclass
class ModelConfig:
    """Configuration for a model accessible via OpenRouter."""
    model_id: str
    display_name: str
    provider: str
    max_tokens: int = 4096
    temperature: float = 0.7

# Model registry
MODELS = {
    "gemini-3.0-pro": ModelConfig(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro",
        provider="Google"
    ),
    "gemini-3.0-flash": ModelConfig(
        model_id="google/gemini-3.0-flash",
        display_name="Gemini 3.0 Flash",
        provider="Google"
    ),
    "gpt-5.2": ModelConfig(
        model_id="openai/gpt-5.2",
        display_name="GPT-5.2",
        provider="OpenAI"
    ),
    "claude-opus": ModelConfig(
        model_id="anthropic/claude-opus-4-5",
        display_name="Claude Opus 4.5",
        provider="Anthropic"
    ),
    "grok-3": ModelConfig(
        model_id="x-ai/grok-3",
        display_name="Grok-3",
        provider="xAI"
    ),
    "kimi-2": ModelConfig(
        model_id="moonshot/kimi-2",
        display_name="Kimi-2",
        provider="Moonshot"
    ),
    "deepseek-v3": ModelConfig(
        model_id="deepseek/deepseek-v3",
        display_name="DeepSeek-V3",
        provider="DeepSeek"
    )
}

class OpenRouterClient:
    """Client for OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required")

        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://writing-eval.example.com",
                "X-Title": "Writing Evaluation Framework"
            },
            timeout=120.0
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
    def generate(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> dict:
        """Generate a completion from specified model."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.post(
            "/chat/completions",
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        )
        response.raise_for_status()

        result = response.json()
        return {
            "content": result["choices"][0]["message"]["content"],
            "model": result["model"],
            "usage": result.get("usage", {}),
            "latency_ms": response.elapsed.total_seconds() * 1000
        }

    def batch_generate(self, requests: list) -> list:
        """Generate completions for multiple requests in parallel."""
        import asyncio
        import httpx as async_httpx

        async def _async_generate(request):
            async with async_httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=self.client.headers,
                timeout=120.0
            ) as client:
                response = await client.post(
                    "/chat/completions",
                    json=request
                )
                return response.json()

        async def _batch():
            tasks = [_async_generate(req) for req in requests]
            return await asyncio.gather(*tasks, return_exceptions=True)

        return asyncio.run(_batch())
```

---

## 5. Judging Framework

### 5.1 Dual-Persona Judge Design

Each comparison is evaluated by two distinct judge personas:

#### Expert Writer Persona

```python
EXPERT_WRITER_SYSTEM_PROMPT = """You are an expert writing evaluator with 20+ years of experience
in professional communications across industries. You have worked as:
- Corporate communications director
- Technical writing lead
- Journalism editor
- Academic writing instructor

Your evaluation focuses on craft and technique:
- Clarity of expression and logical flow
- Precision of language and word choice
- Appropriate structure and organization
- Grammar, syntax, and mechanics
- Effective use of evidence and examples
- Engagement and readability

You evaluate writing objectively based on professional standards,
not personal preference. You provide specific, actionable feedback."""

EXPERT_WRITER_EVAL_PROMPT = """Compare these two pieces of writing for the following task:

TASK: {task_description}

RESPONSE A:
{response_a}

---

RESPONSE B:
{response_b}

---

Evaluate both responses on these criteria (1-5 scale each):

1. CLARITY: Is the message clear and easy to understand?
2. ORGANIZATION: Is the structure logical and effective?
3. LANGUAGE: Is word choice precise and appropriate?
4. MECHANICS: Are grammar, spelling, and punctuation correct?
5. EFFECTIVENESS: Does the writing achieve its purpose?

For each criterion, provide:
- Score for Response A (1-5)
- Score for Response B (1-5)
- Brief justification

Then provide your OVERALL VERDICT:
- WINNER: A, B, or TIE
- CONFIDENCE: HIGH, MEDIUM, or LOW
- KEY DIFFERENTIATOR: The most important factor in your decision

Respond in JSON format:
{{
  "criteria": {{
    "clarity": {{"a": X, "b": Y, "justification": "..."}},
    "organization": {{"a": X, "b": Y, "justification": "..."}},
    "language": {{"a": X, "b": Y, "justification": "..."}},
    "mechanics": {{"a": X, "b": Y, "justification": "..."}},
    "effectiveness": {{"a": X, "b": Y, "justification": "..."}}
  }},
  "verdict": {{
    "winner": "A|B|TIE",
    "confidence": "HIGH|MEDIUM|LOW",
    "key_differentiator": "..."
  }}
}}"""
```

#### Target Recipient Persona

```python
def generate_recipient_system_prompt(recipient_info):
    """Generate persona prompt for the intended recipient of the writing."""

    return f"""You are evaluating writing as its intended recipient. Your profile:

ROLE: {recipient_info['role']}
CONTEXT: {recipient_info['context']}
EXPECTATIONS: {recipient_info['expectations']}
PRIORITIES: {recipient_info['priorities']}

Evaluate the writing from YOUR perspective as the recipient:
- Does it address your needs and questions?
- Is the tone appropriate for your relationship with the writer?
- Is the level of detail right for your expertise?
- Would you feel informed/persuaded/motivated as intended?
- Is the length appropriate for your time constraints?

You care about practical utility, not writing perfection."""

RECIPIENT_PERSONAS = {
    "executive": {
        "role": "Senior Executive (C-Suite)",
        "context": "Extremely busy, reads hundreds of messages daily",
        "expectations": "Concise, action-oriented, bottom-line upfront",
        "priorities": "Time efficiency, clear recommendations, risk awareness"
    },
    "technical_peer": {
        "role": "Technical Team Member",
        "context": "Works closely with the writer on technical projects",
        "expectations": "Accurate technical details, clear specifications",
        "priorities": "Precision, completeness, actionable next steps"
    },
    "customer": {
        "role": "Customer/Client",
        "context": "Paying customer with a question or concern",
        "expectations": "Helpful, professional, solution-oriented",
        "priorities": "Feeling heard, getting resolution, maintaining trust"
    },
    "board_member": {
        "role": "Board of Directors Member",
        "context": "Quarterly review of company performance",
        "expectations": "Strategic perspective, honest assessment",
        "priorities": "Fiduciary responsibility, governance, long-term value"
    },
    "general_public": {
        "role": "General Public Reader",
        "context": "Reading company blog/announcement",
        "expectations": "Accessible, engaging, informative",
        "priorities": "Understanding without jargon, relevance, trust"
    }
}
```

### 5.2 Position Shuffling

```python
import random
from dataclasses import dataclass
from typing import Tuple

@dataclass
class ComparisonPair:
    """A pair of responses for comparison."""
    task_id: str
    model_a: str
    model_b: str
    response_a: str
    response_b: str

def shuffle_for_judgment(pair: ComparisonPair, seed: int) -> Tuple[dict, dict]:
    """
    Shuffle response order to eliminate position bias.
    Returns (presentation_order, true_mapping).
    """
    random.seed(seed)

    if random.random() < 0.5:
        # Keep original order
        presentation = {
            "response_a": pair.response_a,
            "response_b": pair.response_b
        }
        mapping = {"A": pair.model_a, "B": pair.model_b}
    else:
        # Swap order
        presentation = {
            "response_a": pair.response_b,
            "response_b": pair.response_a
        }
        mapping = {"A": pair.model_b, "B": pair.model_a}

    return presentation, mapping

class PositionBalancer:
    """Ensures balanced position assignment across all comparisons."""

    def __init__(self):
        self.position_counts = {}  # model -> {"first": N, "second": N}

    def get_next_order(self, model_a: str, model_b: str) -> Tuple[str, str]:
        """Determine order to balance position exposure."""

        key = tuple(sorted([model_a, model_b]))
        if key not in self.position_counts:
            self.position_counts[key] = {model_a: 0, model_b: 0}

        counts = self.position_counts[key]

        # Put the model with fewer first-position appearances first
        if counts.get(model_a, 0) <= counts.get(model_b, 0):
            first, second = model_a, model_b
        else:
            first, second = model_b, model_a

        # Update counts
        counts[first] = counts.get(first, 0) + 1

        return first, second
```

### 5.3 Best of 5 Aggregation

```python
from collections import Counter
from typing import List
from dataclasses import dataclass

@dataclass
class JudgmentResult:
    """Result from a single judge evaluation."""
    winner: str  # "A", "B", or "TIE"
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    criteria_scores: dict
    judge_type: str  # "expert" or "recipient"

@dataclass
class AggregatedResult:
    """Aggregated result from multiple judgments."""
    final_winner: str
    win_count: dict
    confidence_level: str
    individual_judgments: List[JudgmentResult]

def aggregate_judgments(judgments: List[JudgmentResult]) -> AggregatedResult:
    """
    Aggregate 5 judgments using majority vote with confidence weighting.
    """
    if len(judgments) != 5:
        raise ValueError("Exactly 5 judgments required for best-of-5")

    # Weight votes by confidence
    confidence_weights = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}

    weighted_scores = {"A": 0.0, "B": 0.0, "TIE": 0.0}
    raw_counts = Counter()

    for j in judgments:
        weight = confidence_weights[j.confidence]
        weighted_scores[j.winner] += weight
        raw_counts[j.winner] += 1

    # Determine winner
    if weighted_scores["A"] > weighted_scores["B"] + 0.5:
        final_winner = "A"
    elif weighted_scores["B"] > weighted_scores["A"] + 0.5:
        final_winner = "B"
    else:
        final_winner = "TIE"

    # Determine aggregated confidence
    max_count = max(raw_counts.values())
    if max_count >= 4:
        agg_confidence = "HIGH"
    elif max_count >= 3:
        agg_confidence = "MEDIUM"
    else:
        agg_confidence = "LOW"

    return AggregatedResult(
        final_winner=final_winner,
        win_count=dict(raw_counts),
        confidence_level=agg_confidence,
        individual_judgments=judgments
    )
```

### 5.4 Complete Judging Pipeline

```python
class JudgingPipeline:
    """Orchestrates the complete judging process."""

    def __init__(self, llm_client: OpenRouterClient, judge_model: str = "anthropic/claude-opus-4-5"):
        self.llm = llm_client
        self.judge_model = judge_model
        self.balancer = PositionBalancer()

    def judge_comparison(
        self,
        pair: ComparisonPair,
        task_description: str,
        recipient_info: dict
    ) -> dict:
        """
        Execute full best-of-5 judging for a comparison pair.
        Returns detailed results including individual judgments.
        """

        judgments = []

        # Run 5 judgment rounds with different seeds
        for round_num in range(5):
            seed = hash(f"{pair.task_id}_{round_num}")
            presentation, mapping = shuffle_for_judgment(pair, seed)

            # Alternate between judge personas
            if round_num % 2 == 0:
                judge_result = self._run_expert_judgment(
                    presentation, task_description
                )
                judge_result.judge_type = "expert"
            else:
                judge_result = self._run_recipient_judgment(
                    presentation, task_description, recipient_info
                )
                judge_result.judge_type = "recipient"

            # Map back to true model identities
            true_winner = mapping.get(judge_result.winner, "TIE")
            judge_result.true_winner = true_winner
            judge_result.position_mapping = mapping

            judgments.append(judge_result)

        # Aggregate results
        aggregated = aggregate_judgments(judgments)

        return {
            "task_id": pair.task_id,
            "model_a": pair.model_a,
            "model_b": pair.model_b,
            "aggregated_result": aggregated,
            "individual_judgments": judgments
        }
```

---

## 6. Database Schema

### 6.1 SQLite Schema Definition

```sql
-- Core tables for the writing evaluation framework

-- Occupations from O*NET
CREATE TABLE occupations (
    onet_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    writing_importance REAL,  -- 1-5 scale
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Writing tasks extracted from O*NET
CREATE TABLE writing_tasks (
    task_id TEXT PRIMARY KEY,
    onet_code TEXT NOT NULL REFERENCES occupations(onet_code),
    task_text TEXT NOT NULL,
    document_type TEXT,
    recipient_type TEXT,
    complexity_level TEXT CHECK(complexity_level IN ('simple', 'moderate', 'complex')),
    requires_context BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Industry variants for task diversification
CREATE TABLE industry_variants (
    variant_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES writing_tasks(task_id),
    industry TEXT NOT NULL,
    context_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated evaluation prompts
CREATE TABLE eval_prompts (
    prompt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES writing_tasks(task_id),
    variant_id TEXT REFERENCES industry_variants(variant_id),
    prompt_text TEXT NOT NULL,
    additional_context TEXT,  -- JSON blob if context provided
    prompt_type TEXT CHECK(prompt_type IN ('simple', 'with_context')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model responses
CREATE TABLE model_responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES eval_prompts(prompt_id),
    model_id TEXT NOT NULL,
    response_text TEXT NOT NULL,
    latency_ms INTEGER,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, model_id)
);

-- Pairwise comparisons
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES eval_prompts(prompt_id),
    model_a TEXT NOT NULL,
    model_b TEXT NOT NULL,
    response_a_id TEXT NOT NULL REFERENCES model_responses(response_id),
    response_b_id TEXT NOT NULL REFERENCES model_responses(response_id),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'judging', 'complete', 'error')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual judgments
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),
    round_number INTEGER NOT NULL CHECK(round_number BETWEEN 1 AND 5),
    judge_type TEXT NOT NULL CHECK(judge_type IN ('expert', 'recipient')),
    position_order TEXT NOT NULL,  -- JSON: which model was shown as A vs B
    winner TEXT NOT NULL CHECK(winner IN ('A', 'B', 'TIE')),
    true_winner_model TEXT NOT NULL,  -- Actual model that won
    confidence TEXT NOT NULL CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    criteria_scores TEXT NOT NULL,  -- JSON blob with detailed scores
    raw_response TEXT,  -- Full judge response for debugging
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated comparison results
CREATE TABLE comparison_results (
    result_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL UNIQUE REFERENCES comparisons(comparison_id),
    final_winner TEXT NOT NULL CHECK(final_winner IN ('model_a', 'model_b', 'tie')),
    final_winner_model TEXT NOT NULL,
    win_count_a INTEGER NOT NULL,
    win_count_b INTEGER NOT NULL,
    win_count_tie INTEGER NOT NULL,
    aggregated_confidence TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_responses_model ON model_responses(model_id);
CREATE INDEX idx_comparisons_models ON comparisons(model_a, model_b);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
CREATE INDEX idx_results_winner ON comparison_results(final_winner_model);

-- Views for analysis
CREATE VIEW model_pair_stats AS
SELECT
    model_a,
    model_b,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN final_winner_model = model_a THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN final_winner_model = model_b THEN 1 ELSE 0 END) as model_b_wins,
    SUM(CASE WHEN final_winner = 'tie' THEN 1 ELSE 0 END) as ties,
    ROUND(100.0 * SUM(CASE WHEN final_winner_model = model_a THEN 1 ELSE 0 END) / COUNT(*), 1) as model_a_win_rate
FROM comparison_results cr
JOIN comparisons c ON cr.comparison_id = c.comparison_id
GROUP BY model_a, model_b;

CREATE VIEW gemini_performance AS
SELECT
    CASE
        WHEN model_a LIKE '%gemini%' THEN model_a
        ELSE model_b
    END as gemini_model,
    CASE
        WHEN model_a LIKE '%gemini%' THEN model_b
        ELSE model_a
    END as competitor,
    COUNT(*) as comparisons,
    SUM(CASE
        WHEN (model_a LIKE '%gemini%' AND final_winner_model = model_a) OR
             (model_b LIKE '%gemini%' AND final_winner_model = model_b)
        THEN 1 ELSE 0 END
    ) as gemini_wins,
    ROUND(100.0 * SUM(CASE
        WHEN (model_a LIKE '%gemini%' AND final_winner_model = model_a) OR
             (model_b LIKE '%gemini%' AND final_winner_model = model_b)
        THEN 1 ELSE 0 END
    ) / COUNT(*), 1) as gemini_win_rate
FROM comparison_results cr
JOIN comparisons c ON cr.comparison_id = c.comparison_id
WHERE model_a LIKE '%gemini%' OR model_b LIKE '%gemini%'
GROUP BY gemini_model, competitor;
```

### 6.2 Database Manager

```python
import sqlite3
import json
import uuid
from pathlib import Path
from contextlib import contextmanager

class EvalDatabase:
    """Database manager for the evaluation framework."""

    def __init__(self, db_path: str = "data/eval.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        schema_path = Path("schema.sql")
        if schema_path.exists():
            with self.connection() as conn:
                conn.executescript(schema_path.read_text())

    def insert_comparison_result(self, result: dict):
        """Insert a complete comparison result with all judgments."""
        with self.connection() as conn:
            # Insert comparison record
            conn.execute("""
                INSERT INTO comparisons (comparison_id, prompt_id, model_a, model_b,
                                        response_a_id, response_b_id, status)
                VALUES (?, ?, ?, ?, ?, ?, 'complete')
            """, (
                result['comparison_id'],
                result['prompt_id'],
                result['model_a'],
                result['model_b'],
                result['response_a_id'],
                result['response_b_id']
            ))

            # Insert individual judgments
            for i, judgment in enumerate(result['judgments']):
                conn.execute("""
                    INSERT INTO judgments (judgment_id, comparison_id, round_number,
                                          judge_type, position_order, winner,
                                          true_winner_model, confidence, criteria_scores)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    result['comparison_id'],
                    i + 1,
                    judgment['judge_type'],
                    json.dumps(judgment['position_mapping']),
                    judgment['winner'],
                    judgment['true_winner'],
                    judgment['confidence'],
                    json.dumps(judgment['criteria_scores'])
                ))

            # Insert aggregated result
            agg = result['aggregated']
            conn.execute("""
                INSERT INTO comparison_results (result_id, comparison_id, final_winner,
                                               final_winner_model, win_count_a, win_count_b,
                                               win_count_tie, aggregated_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                result['comparison_id'],
                agg['final_winner'],
                agg['final_winner_model'],
                agg['win_counts'].get('A', 0),
                agg['win_counts'].get('B', 0),
                agg['win_counts'].get('TIE', 0),
                agg['confidence']
            ))

    def export_to_csv(self, output_dir: str = "exports"):
        """Export all tables to CSV files."""
        import csv

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        tables = [
            'occupations', 'writing_tasks', 'eval_prompts',
            'model_responses', 'comparisons', 'judgments',
            'comparison_results'
        ]

        with self.connection() as conn:
            for table in tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()

                if rows:
                    csv_path = output_path / f"{table}.csv"
                    with open(csv_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([desc[0] for desc in cursor.description])
                        writer.writerows(rows)

                    print(f"Exported {len(rows)} rows to {csv_path}")
```

---

## 7. Execution Pipeline

### 7.1 Pipeline Orchestrator

```python
import asyncio
from typing import List, Optional
from dataclasses import dataclass
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EvalConfig:
    """Configuration for evaluation run."""
    models: List[str]
    gemini_models: List[str]  # Models to compare against all others
    prompts_per_task: int = 3
    max_parallel_requests: int = 10
    judge_model: str = "anthropic/claude-opus-4-5"

class EvalPipeline:
    """Main orchestrator for the evaluation pipeline."""

    def __init__(self, config: EvalConfig, db: EvalDatabase, llm: OpenRouterClient):
        self.config = config
        self.db = db
        self.llm = llm
        self.judging = JudgingPipeline(llm, config.judge_model)

    async def run_full_evaluation(self):
        """Execute complete evaluation pipeline."""

        logger.info("Starting evaluation pipeline")

        # Phase 1: Load O*NET data and generate prompts
        logger.info("Phase 1: Loading O*NET data")
        await self._load_onet_data()

        # Phase 2: Generate all model responses
        logger.info("Phase 2: Generating model responses")
        await self._generate_all_responses()

        # Phase 3: Create comparison pairs
        logger.info("Phase 3: Creating comparison pairs")
        comparisons = self._create_comparison_pairs()

        # Phase 4: Run judgments
        logger.info(f"Phase 4: Running judgments for {len(comparisons)} comparisons")
        await self._run_all_judgments(comparisons)

        # Phase 5: Generate reports
        logger.info("Phase 5: Generating reports")
        self._generate_reports()

        logger.info("Evaluation complete!")

    async def _generate_all_responses(self):
        """Generate responses from all models for all prompts."""

        with self.db.connection() as conn:
            prompts = conn.execute(
                "SELECT prompt_id, prompt_text FROM eval_prompts WHERE prompt_id NOT IN (SELECT DISTINCT prompt_id FROM model_responses)"
            ).fetchall()

        semaphore = asyncio.Semaphore(self.config.max_parallel_requests)

        async def generate_with_limit(model_id, prompt):
            async with semaphore:
                return await self._generate_single_response(model_id, prompt)

        tasks = []
        for prompt in prompts:
            for model_id in self.config.models:
                tasks.append(generate_with_limit(model_id, prompt))

        results = []
        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Generating responses"):
            result = await coro
            results.append(result)

            # Save to database periodically
            if len(results) % 100 == 0:
                self._save_responses(results[-100:])

        # Save remaining
        self._save_responses(results[-(len(results) % 100):])

    def _create_comparison_pairs(self) -> List[dict]:
        """Create all pairwise comparisons (Gemini vs each competitor)."""

        comparisons = []

        with self.db.connection() as conn:
            prompts = conn.execute("SELECT prompt_id FROM eval_prompts").fetchall()

            for prompt in prompts:
                prompt_id = prompt['prompt_id']

                # Get all responses for this prompt
                responses = conn.execute(
                    "SELECT response_id, model_id FROM model_responses WHERE prompt_id = ?",
                    (prompt_id,)
                ).fetchall()

                response_map = {r['model_id']: r['response_id'] for r in responses}

                # Create Gemini vs competitor pairs
                for gemini_model in self.config.gemini_models:
                    if gemini_model not in response_map:
                        continue

                    for other_model in self.config.models:
                        if other_model == gemini_model or other_model not in response_map:
                            continue

                        comparisons.append({
                            'prompt_id': prompt_id,
                            'model_a': gemini_model,
                            'model_b': other_model,
                            'response_a_id': response_map[gemini_model],
                            'response_b_id': response_map[other_model]
                        })

        return comparisons

    async def _run_all_judgments(self, comparisons: List[dict]):
        """Run best-of-5 judgments for all comparison pairs."""

        for comparison in tqdm(comparisons, desc="Running judgments"):
            try:
                result = await self._judge_single_comparison(comparison)
                self.db.insert_comparison_result(result)
            except Exception as e:
                logger.error(f"Error judging comparison {comparison['prompt_id']}: {e}")
                continue
```

### 7.2 Command-Line Interface

```python
#!/usr/bin/env python3
"""
cli.py - Command-line interface for the writing evaluation framework
"""

import click
import asyncio
from pathlib import Path

@click.group()
@click.option('--db', default='data/eval.db', help='Database path')
@click.pass_context
def cli(ctx, db):
    """Writing Evaluation Framework CLI"""
    ctx.ensure_object(dict)
    ctx.obj['db'] = EvalDatabase(db)

@cli.command()
@click.pass_context
def download_onet(ctx):
    """Download and process O*NET data."""
    click.echo("Downloading O*NET database...")
    extract_dir = download_onet()
    tables = load_onet_tables(extract_dir)

    # Process and store
    writing_occs = identify_writing_occupations(tables)
    click.echo(f"Found {len(writing_occs)} occupations with significant writing requirements")

    tasks = extract_writing_tasks(tables, writing_occs)
    click.echo(f"Extracted {len(tasks)} writing-related tasks")

    # Store in database
    db = ctx.obj['db']
    # ... store logic

@cli.command()
@click.option('--models', '-m', multiple=True, required=True, help='Models to evaluate')
@click.option('--gemini', '-g', multiple=True, required=True, help='Gemini models to compare')
@click.pass_context
def run_eval(ctx, models, gemini):
    """Run the full evaluation pipeline."""
    config = EvalConfig(
        models=list(models),
        gemini_models=list(gemini)
    )

    db = ctx.obj['db']
    llm = OpenRouterClient()
    pipeline = EvalPipeline(config, db, llm)

    asyncio.run(pipeline.run_full_evaluation())

@cli.command()
@click.option('--output', '-o', default='exports', help='Output directory')
@click.pass_context
def export(ctx, output):
    """Export results to CSV files."""
    db = ctx.obj['db']
    db.export_to_csv(output)
    click.echo(f"Exported to {output}/")

@cli.command()
@click.option('--output', '-o', default='reports/eval_report.pdf', help='Output PDF path')
@click.pass_context
def report(ctx, output):
    """Generate PDF evaluation report."""
    db = ctx.obj['db']
    generator = ReportGenerator(db)
    generator.generate_pdf(output)
    click.echo(f"Report generated: {output}")

@cli.command()
@click.option('--comparison-id', '-c', help='Specific comparison to view')
@click.option('--model', '-m', help='Filter by model')
@click.pass_context
def inspect(ctx, comparison_id, model):
    """Inspect individual evaluation results."""
    db = ctx.obj['db']
    viewer = EvalViewer(db)

    if comparison_id:
        viewer.show_comparison(comparison_id)
    elif model:
        viewer.show_model_results(model)
    else:
        viewer.show_summary()

if __name__ == '__main__':
    cli()
```

---

## 8. Analysis & Reporting

### 8.1 Statistical Analysis

```python
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple

class StatisticalAnalyzer:
    """Statistical analysis of evaluation results."""

    def __init__(self, db: EvalDatabase):
        self.db = db

    def compute_win_rates(self) -> Dict[str, Dict[str, float]]:
        """Compute pairwise win rates for all model combinations."""

        with self.db.connection() as conn:
            results = conn.execute("""
                SELECT model_a, model_b, final_winner_model, COUNT(*) as count
                FROM comparison_results cr
                JOIN comparisons c ON cr.comparison_id = c.comparison_id
                GROUP BY model_a, model_b, final_winner_model
            """).fetchall()

        # Aggregate into win rate matrix
        win_rates = {}
        for row in results:
            key = (row['model_a'], row['model_b'])
            if key not in win_rates:
                win_rates[key] = {'a_wins': 0, 'b_wins': 0, 'ties': 0, 'total': 0}

            if row['final_winner_model'] == row['model_a']:
                win_rates[key]['a_wins'] += row['count']
            elif row['final_winner_model'] == row['model_b']:
                win_rates[key]['b_wins'] += row['count']
            else:
                win_rates[key]['ties'] += row['count']

            win_rates[key]['total'] += row['count']

        # Calculate percentages
        for key, data in win_rates.items():
            data['a_win_rate'] = data['a_wins'] / data['total'] * 100
            data['b_win_rate'] = data['b_wins'] / data['total'] * 100
            data['tie_rate'] = data['ties'] / data['total'] * 100

        return win_rates

    def compute_confidence_intervals(self, win_rates: Dict) -> Dict:
        """Compute 95% confidence intervals for win rates."""

        ci_results = {}

        for key, data in win_rates.items():
            n = data['total']
            p = data['a_win_rate'] / 100

            # Wilson score interval
            z = 1.96  # 95% CI
            denominator = 1 + z**2 / n
            center = (p + z**2 / (2*n)) / denominator
            spread = z * np.sqrt((p*(1-p) + z**2/(4*n)) / n) / denominator

            ci_results[key] = {
                'point_estimate': p * 100,
                'ci_lower': max(0, (center - spread) * 100),
                'ci_upper': min(100, (center + spread) * 100)
            }

        return ci_results

    def identify_weaknesses(self, gemini_model: str) -> List[dict]:
        """Identify specific areas where Gemini underperforms."""

        with self.db.connection() as conn:
            # Analyze by task type
            results = conn.execute("""
                SELECT
                    wt.document_type,
                    wt.recipient_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN cr.final_winner_model = ? THEN 1 ELSE 0 END) as gemini_wins
                FROM comparison_results cr
                JOIN comparisons c ON cr.comparison_id = c.comparison_id
                JOIN eval_prompts ep ON c.prompt_id = ep.prompt_id
                JOIN writing_tasks wt ON ep.task_id = wt.task_id
                WHERE c.model_a = ? OR c.model_b = ?
                GROUP BY wt.document_type, wt.recipient_type
                HAVING total >= 10
            """, (gemini_model, gemini_model, gemini_model)).fetchall()

        weaknesses = []
        for row in results:
            win_rate = row['gemini_wins'] / row['total'] * 100
            if win_rate < 45:  # Underperforming threshold
                weaknesses.append({
                    'document_type': row['document_type'],
                    'recipient_type': row['recipient_type'],
                    'win_rate': win_rate,
                    'sample_size': row['total'],
                    'severity': 'high' if win_rate < 35 else 'medium'
                })

        return sorted(weaknesses, key=lambda x: x['win_rate'])
```

### 8.2 Visualization Generation

```python
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

class Visualizer:
    """Generate visualizations for evaluation results."""

    def __init__(self, db: EvalDatabase, analyzer: StatisticalAnalyzer):
        self.db = db
        self.analyzer = analyzer

        # Set style
        plt.style.use('seaborn-v0_8-whitegrid')
        sns.set_palette("husl")

    def create_win_rate_heatmap(self, save_path: str = None) -> plt.Figure:
        """Create heatmap of pairwise win rates."""

        win_rates = self.analyzer.compute_win_rates()

        # Convert to matrix format
        models = sorted(set(
            [k[0] for k in win_rates.keys()] +
            [k[1] for k in win_rates.keys()]
        ))

        matrix = pd.DataFrame(index=models, columns=models, dtype=float)

        for (m1, m2), data in win_rates.items():
            matrix.loc[m1, m2] = data['a_win_rate']
            matrix.loc[m2, m1] = data['b_win_rate']

        # Fill diagonal with 50%
        for m in models:
            matrix.loc[m, m] = 50.0

        fig, ax = plt.subplots(figsize=(12, 10))
        sns.heatmap(
            matrix.astype(float),
            annot=True,
            fmt='.1f',
            cmap='RdYlGn',
            center=50,
            vmin=0,
            vmax=100,
            ax=ax
        )

        ax.set_title('Model Win Rates (Row vs Column)', fontsize=14)
        ax.set_xlabel('Opponent Model')
        ax.set_ylabel('Model')

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def create_gemini_comparison_chart(self, gemini_model: str, save_path: str = None) -> plt.Figure:
        """Create bar chart comparing Gemini against all competitors."""

        win_rates = self.analyzer.compute_win_rates()
        ci = self.analyzer.compute_confidence_intervals(win_rates)

        # Filter for Gemini comparisons
        gemini_data = []
        for (m1, m2), data in win_rates.items():
            if m1 == gemini_model:
                gemini_data.append({
                    'competitor': m2,
                    'gemini_win_rate': data['a_win_rate'],
                    'ci_lower': ci[(m1, m2)]['ci_lower'],
                    'ci_upper': ci[(m1, m2)]['ci_upper']
                })
            elif m2 == gemini_model:
                gemini_data.append({
                    'competitor': m1,
                    'gemini_win_rate': data['b_win_rate'],
                    'ci_lower': 100 - ci[(m1, m2)]['ci_upper'],
                    'ci_upper': 100 - ci[(m1, m2)]['ci_lower']
                })

        df = pd.DataFrame(gemini_data)
        df = df.sort_values('gemini_win_rate', ascending=True)

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = ['#e74c3c' if r < 45 else '#2ecc71' if r > 55 else '#f39c12'
                  for r in df['gemini_win_rate']]

        bars = ax.barh(df['competitor'], df['gemini_win_rate'], color=colors)

        # Add error bars
        ax.errorbar(
            df['gemini_win_rate'],
            range(len(df)),
            xerr=[df['gemini_win_rate'] - df['ci_lower'], df['ci_upper'] - df['gemini_win_rate']],
            fmt='none',
            color='black',
            capsize=3
        )

        ax.axvline(x=50, color='gray', linestyle='--', alpha=0.7, label='Parity')
        ax.set_xlabel('Gemini Win Rate (%)')
        ax.set_title(f'{gemini_model} Win Rate vs Competitors')
        ax.set_xlim(0, 100)

        # Add value labels
        for i, (idx, row) in enumerate(df.iterrows()):
            ax.text(row['gemini_win_rate'] + 2, i, f"{row['gemini_win_rate']:.1f}%", va='center')

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig

    def create_weakness_analysis_chart(self, gemini_model: str, save_path: str = None) -> plt.Figure:
        """Visualize Gemini's specific weaknesses by task type."""

        weaknesses = self.analyzer.identify_weaknesses(gemini_model)

        if not weaknesses:
            return None

        df = pd.DataFrame(weaknesses)
        df['label'] = df['document_type'] + '\n(' + df['recipient_type'] + ')'

        fig, ax = plt.subplots(figsize=(12, 6))

        colors = ['#e74c3c' if s == 'high' else '#f39c12' for s in df['severity']]

        bars = ax.bar(range(len(df)), df['win_rate'], color=colors)

        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.7)
        ax.axhline(y=45, color='orange', linestyle=':', alpha=0.7)
        ax.axhline(y=35, color='red', linestyle=':', alpha=0.7)

        ax.set_xticks(range(len(df)))
        ax.set_xticklabels(df['label'], rotation=45, ha='right')
        ax.set_ylabel('Win Rate (%)')
        ax.set_title(f'{gemini_model} Underperformance Areas')
        ax.set_ylim(0, 60)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')

        return fig
```

### 8.3 PDF Report Generator

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from io import BytesIO

class ReportGenerator:
    """Generate comprehensive PDF evaluation report."""

    def __init__(self, db: EvalDatabase):
        self.db = db
        self.analyzer = StatisticalAnalyzer(db)
        self.visualizer = Visualizer(db, self.analyzer)
        self.styles = getSampleStyleSheet()

    def generate_pdf(self, output_path: str):
        """Generate complete evaluation report PDF."""

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Title page
        story.extend(self._create_title_page())
        story.append(PageBreak())

        # Executive summary
        story.extend(self._create_executive_summary())
        story.append(PageBreak())

        # Methodology
        story.extend(self._create_methodology_section())
        story.append(PageBreak())

        # Results overview
        story.extend(self._create_results_overview())
        story.append(PageBreak())

        # Detailed Gemini analysis
        story.extend(self._create_gemini_analysis())
        story.append(PageBreak())

        # Weakness analysis
        story.extend(self._create_weakness_analysis())
        story.append(PageBreak())

        # Appendix: Per-task results
        story.extend(self._create_appendix())

        doc.build(story)

    def _create_executive_summary(self) -> list:
        """Create executive summary section."""

        elements = []
        elements.append(Paragraph("Executive Summary", self.styles['Heading1']))
        elements.append(Spacer(1, 12))

        # Get high-level stats
        win_rates = self.analyzer.compute_win_rates()

        # Calculate overall Gemini performance
        gemini_stats = self._calculate_gemini_overall_stats(win_rates)

        summary_text = f"""
        This report presents the results of a comprehensive writing evaluation comparing
        Gemini 3.0 Pro and Gemini 3.0 Flash against leading frontier models across {gemini_stats['total_comparisons']:,}
        pairwise comparisons derived from {gemini_stats['unique_tasks']:,} unique writing tasks.

        Key Findings:
        - Gemini 3.0 Pro achieved an overall win rate of {gemini_stats['pro_win_rate']:.1f}% against competitors
        - Gemini 3.0 Flash achieved an overall win rate of {gemini_stats['flash_win_rate']:.1f}% against competitors
        - Primary weakness areas: {', '.join(gemini_stats['top_weaknesses'][:3])}
        - Primary strength areas: {', '.join(gemini_stats['top_strengths'][:3])}
        """

        elements.append(Paragraph(summary_text, self.styles['Normal']))

        return elements

    def _create_gemini_analysis(self) -> list:
        """Create detailed Gemini performance analysis."""

        elements = []
        elements.append(Paragraph("Gemini Performance Analysis", self.styles['Heading1']))
        elements.append(Spacer(1, 12))

        # Add comparison charts
        for gemini_model in ['gemini-3.0-pro', 'gemini-3.0-flash']:
            elements.append(Paragraph(f"{gemini_model} vs Competitors", self.styles['Heading2']))

            # Create and embed chart
            fig = self.visualizer.create_gemini_comparison_chart(gemini_model)
            img_buffer = BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)

            elements.append(Image(img_buffer, width=6*inch, height=4*inch))
            elements.append(Spacer(1, 12))

            plt.close(fig)

        return elements

    def _create_weakness_analysis(self) -> list:
        """Create Gemini weakness analysis section."""

        elements = []
        elements.append(Paragraph("Identified Weaknesses", self.styles['Heading1']))
        elements.append(Spacer(1, 12))

        for gemini_model in ['gemini-3.0-pro', 'gemini-3.0-flash']:
            weaknesses = self.analyzer.identify_weaknesses(gemini_model)

            elements.append(Paragraph(f"{gemini_model} Weaknesses", self.styles['Heading2']))

            if weaknesses:
                # Create table
                data = [['Task Type', 'Recipient', 'Win Rate', 'Sample Size', 'Severity']]
                for w in weaknesses[:10]:
                    data.append([
                        w['document_type'],
                        w['recipient_type'],
                        f"{w['win_rate']:.1f}%",
                        str(w['sample_size']),
                        w['severity'].upper()
                    ])

                table = Table(data, colWidths=[1.5*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))

                elements.append(table)
            else:
                elements.append(Paragraph("No significant weaknesses identified.", self.styles['Normal']))

            elements.append(Spacer(1, 20))

        return elements
```

---

## 9. Quality Assurance

### 9.1 Position Bias Verification

```python
def verify_position_balance(db: EvalDatabase) -> dict:
    """Verify that position assignment was properly balanced."""

    with db.connection() as conn:
        results = conn.execute("""
            SELECT
                j.position_order,
                j.winner,
                COUNT(*) as count
            FROM judgments j
            GROUP BY j.position_order, j.winner
        """).fetchall()

    # Parse and analyze
    position_stats = {'first_position_wins': 0, 'second_position_wins': 0, 'total': 0}

    for row in results:
        position_order = json.loads(row['position_order'])
        if row['winner'] == 'A':
            position_stats['first_position_wins'] += row['count']
        elif row['winner'] == 'B':
            position_stats['second_position_wins'] += row['count']
        position_stats['total'] += row['count']

    # Check for significant bias
    first_rate = position_stats['first_position_wins'] / position_stats['total']

    bias_check = {
        'first_position_rate': first_rate * 100,
        'second_position_rate': (1 - first_rate) * 100,
        'is_balanced': 0.45 <= first_rate <= 0.55,
        'recommendation': 'OK' if 0.45 <= first_rate <= 0.55 else 'INVESTIGATE POSITION BIAS'
    }

    return bias_check
```

### 9.2 Inter-Judge Agreement

```python
def compute_judge_agreement(db: EvalDatabase) -> dict:
    """Compute agreement rates between expert and recipient judges."""

    with db.connection() as conn:
        comparisons = conn.execute("""
            SELECT comparison_id FROM comparisons WHERE status = 'complete'
        """).fetchall()

    agreements = 0
    total = 0

    for comp in comparisons:
        judgments = conn.execute("""
            SELECT judge_type, true_winner_model
            FROM judgments
            WHERE comparison_id = ?
        """, (comp['comparison_id'],)).fetchall()

        expert_votes = [j['true_winner_model'] for j in judgments if j['judge_type'] == 'expert']
        recipient_votes = [j['true_winner_model'] for j in judgments if j['judge_type'] == 'recipient']

        if expert_votes and recipient_votes:
            expert_majority = max(set(expert_votes), key=expert_votes.count)
            recipient_majority = max(set(recipient_votes), key=recipient_votes.count)

            if expert_majority == recipient_majority:
                agreements += 1
            total += 1

    return {
        'agreement_rate': agreements / total * 100 if total > 0 else 0,
        'total_comparisons': total,
        'interpretation': 'Good' if agreements / total > 0.7 else 'Investigate disagreements'
    }
```

### 9.3 Result Validation Suite

```python
class ValidationSuite:
    """Comprehensive validation for evaluation results."""

    def __init__(self, db: EvalDatabase):
        self.db = db

    def run_all_validations(self) -> dict:
        """Run complete validation suite."""

        return {
            'position_balance': verify_position_balance(self.db),
            'judge_agreement': compute_judge_agreement(self.db),
            'sample_sizes': self._check_sample_sizes(),
            'data_completeness': self._check_completeness(),
            'outlier_analysis': self._detect_outliers()
        }

    def _check_sample_sizes(self) -> dict:
        """Verify adequate sample sizes for statistical validity."""

        with self.db.connection() as conn:
            model_pairs = conn.execute("""
                SELECT model_a, model_b, COUNT(*) as n
                FROM comparisons
                WHERE status = 'complete'
                GROUP BY model_a, model_b
            """).fetchall()

        min_required = 100  # Minimum for reliable estimates

        insufficient = []
        for pair in model_pairs:
            if pair['n'] < min_required:
                insufficient.append({
                    'pair': (pair['model_a'], pair['model_b']),
                    'count': pair['n'],
                    'shortfall': min_required - pair['n']
                })

        return {
            'all_sufficient': len(insufficient) == 0,
            'insufficient_pairs': insufficient,
            'minimum_required': min_required
        }

    def _check_completeness(self) -> dict:
        """Check for missing data or incomplete evaluations."""

        with self.db.connection() as conn:
            incomplete = conn.execute("""
                SELECT COUNT(*) as n FROM comparisons WHERE status != 'complete'
            """).fetchone()['n']

            missing_judgments = conn.execute("""
                SELECT c.comparison_id, COUNT(j.judgment_id) as judgment_count
                FROM comparisons c
                LEFT JOIN judgments j ON c.comparison_id = j.comparison_id
                WHERE c.status = 'complete'
                GROUP BY c.comparison_id
                HAVING judgment_count < 5
            """).fetchall()

        return {
            'incomplete_comparisons': incomplete,
            'comparisons_missing_judgments': len(missing_judgments),
            'is_complete': incomplete == 0 and len(missing_judgments) == 0
        }
```

---

## 10. Estimated Timeline and Resources

### 10.1 Implementation Phases

| Phase | Duration | Description |
|-------|----------|-------------|
| 1. Setup | 2 days | Repository structure, dependencies, database schema |
| 2. O*NET Pipeline | 3 days | Download scripts, extraction, task identification |
| 3. Prompt Generation | 4 days | Templates, industry variants, context generation |
| 4. Model Integration | 2 days | OpenRouter client, error handling, rate limiting |
| 5. Judging Framework | 5 days | Personas, rubrics, aggregation logic |
| 6. Execution Pipeline | 3 days | Orchestration, parallelization, progress tracking |
| 7. Analysis & Reporting | 4 days | Statistics, visualizations, PDF generation |
| 8. Testing & QA | 3 days | Validation suite, bias checks, edge cases |

**Total Estimated Duration: 26 working days (5-6 weeks)**

### 10.2 API Cost Estimates

| Component | Estimated Calls | Est. Cost |
|-----------|-----------------|-----------|
| Model Responses (7 models x 3000 prompts) | 21,000 | $2,000-4,000 |
| Judge Evaluations (5 per comparison x 18,000 pairs) | 90,000 | $3,000-5,000 |
| Context Generation | 5,000 | $200-500 |
| **Total** | ~116,000 | **$5,200-9,500** |

---

## 11. File Structure

```
JTBD-writing/
├── README.md
├── requirements.txt
├── setup.py
├── config/
│   ├── models.yaml
│   └── prompts.yaml
├── data/
│   ├── onet/
│   │   └── (downloaded O*NET files)
│   ├── eval.db
│   └── context_templates/
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── onet/
│   │   ├── __init__.py
│   │   ├── downloader.py
│   │   └── extractor.py
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── context.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── openrouter.py
│   ├── judging/
│   │   ├── __init__.py
│   │   ├── personas.py
│   │   ├── rubrics.py
│   │   └── aggregation.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.sql
│   │   └── manager.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── orchestrator.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py
│   │   └── visualizations.py
│   └── reporting/
│       ├── __init__.py
│       └── pdf_generator.py
├── tests/
│   ├── test_onet.py
│   ├── test_prompts.py
│   ├── test_judging.py
│   └── test_pipeline.py
├── exports/
│   └── (CSV exports)
└── reports/
    └── (Generated PDF reports)
```

---

## 12. Summary

This implementation plan provides a comprehensive framework for evaluating Gemini's writing capabilities against frontier competitors. Key design decisions include:

1. **Data-Driven Task Selection**: Using O*NET ensures coverage of realistic writing tasks across the entire US economy
2. **Dual-Persona Judging**: Combining expert craft evaluation with recipient-focused utility assessment
3. **Robust Methodology**: Position shuffling, best-of-5 aggregation, and statistical validation
4. **Actionable Outputs**: Fine-grained inspection, weakness identification, and publication-ready reports

The framework is designed to produce trustworthy, reproducible results that identify specific areas where Gemini models can improve relative to competitors.
