# Gemini Writing Evaluation Framework: Master Implementation Plan

## Executive Summary

This document outlines a comprehensive framework for evaluating Gemini 3.0 Pro and 3.0 Flash against competing frontier models (GPT-5.2, Claude Opus 4.5, Grok-3, Kimi K2, etc.) across realistic writing tasks derived from the entire US economy. The framework leverages O*NET occupational data to ensure comprehensive coverage, implements rigorous pairwise comparisons with position-bias mitigation, and employs dual-persona judging (expert writer + target recipient) with best-of-5 aggregation.

---

## 1. O*NET Data Pipeline

### 1.1 Data Download Strategy

O*NET provides detailed occupational information including work activities, tasks, and skill requirements. We'll download the latest O*NET database (version 29.0+) which contains ~1,000 occupations with detailed task descriptions.

```bash
#!/bin/bash
# scripts/download_onet.sh

ONET_VERSION="29_0"
BASE_URL="https://www.onetcenter.org/dl_files/database"

mkdir -p data/onet_raw
cd data/onet_raw

# Download core files
wget "${BASE_URL}/db_${ONET_VERSION}_excel.zip" -O onet_db.zip
unzip onet_db.zip

# Key files for writing tasks:
# - Task Statements.xlsx - All task statements per occupation
# - Work Activities.xlsx - Generalized work activities (includes writing)
# - Skills.xlsx - Required skills including writing skill level
# - Occupation Data.xlsx - O*NET-SOC codes and titles
```

### 1.2 Writing Task Extraction

We identify writing-intensive occupations using multiple signals:

```python
# scripts/extract_writing_tasks.py

import pandas as pd
from pathlib import Path

class ONetWritingExtractor:
    """Extract writing-related tasks and occupations from O*NET."""

    WRITING_KEYWORDS = [
        'write', 'writing', 'draft', 'compose', 'document', 'report',
        'memo', 'email', 'correspondence', 'letter', 'proposal',
        'communicate in writing', 'prepare written', 'create written',
        'technical writing', 'author', 'edit', 'review written'
    ]

    # O*NET Work Activity IDs related to writing
    WRITING_ACTIVITY_IDS = [
        '4.A.4.a.3',  # Documenting/Recording Information
        '4.A.4.b.2',  # Communicating with Persons Outside Organization (written)
        '4.A.4.b.1',  # Communicating with Supervisors, Peers, or Subordinates
    ]

    # Minimum writing skill importance score (scale 1-5)
    MIN_WRITING_IMPORTANCE = 3.0

    def __init__(self, onet_path: Path):
        self.onet_path = onet_path
        self.occupations = pd.read_excel(onet_path / "Occupation Data.xlsx")
        self.tasks = pd.read_excel(onet_path / "Task Statements.xlsx")
        self.skills = pd.read_excel(onet_path / "Skills.xlsx")
        self.work_activities = pd.read_excel(onet_path / "Work Activities.xlsx")

    def get_writing_intensive_occupations(self) -> pd.DataFrame:
        """Filter occupations with significant writing requirements."""
        # Filter by writing skill importance
        writing_skills = self.skills[
            (self.skills['Element Name'] == 'Writing') &
            (self.skills['Scale ID'] == 'IM') &  # Importance scale
            (self.skills['Data Value'] >= self.MIN_WRITING_IMPORTANCE)
        ]

        return self.occupations[
            self.occupations['O*NET-SOC Code'].isin(writing_skills['O*NET-SOC Code'])
        ]

    def extract_writing_tasks(self, occupation_code: str) -> list[dict]:
        """Extract specific writing tasks for an occupation."""
        occ_tasks = self.tasks[self.tasks['O*NET-SOC Code'] == occupation_code]

        writing_tasks = []
        for _, task in occ_tasks.iterrows():
            task_text = task['Task'].lower()
            if any(kw in task_text for kw in self.WRITING_KEYWORDS):
                writing_tasks.append({
                    'occupation_code': occupation_code,
                    'task_id': task['Task ID'],
                    'task_description': task['Task'],
                    'task_type': task.get('Task Type', 'core')
                })

        return writing_tasks

    def build_writing_task_corpus(self) -> pd.DataFrame:
        """Build complete corpus of writing tasks across all occupations."""
        writing_occs = self.get_writing_intensive_occupations()

        all_tasks = []
        for _, occ in writing_occs.iterrows():
            tasks = self.extract_writing_tasks(occ['O*NET-SOC Code'])
            for task in tasks:
                task['occupation_title'] = occ['Title']
                all_tasks.append(task)

        return pd.DataFrame(all_tasks)
```

### 1.3 Occupation Taxonomy

We categorize occupations into major categories for balanced sampling:

| Category Code | Category Name | Example Occupations |
|---------------|---------------|---------------------|
| 11 | Management | CEOs, HR Managers, Marketing Managers |
| 13 | Business/Financial | Accountants, Financial Analysts, Compliance Officers |
| 15 | Computer/Mathematical | Software Developers, Data Scientists |
| 17 | Architecture/Engineering | Engineers, Architects, Surveyors |
| 19 | Life/Physical/Social Science | Researchers, Economists, Psychologists |
| 21 | Community/Social Service | Social Workers, Counselors |
| 23 | Legal | Lawyers, Paralegals, Judges |
| 25 | Education/Training | Teachers, Professors, Instructional Designers |
| 27 | Arts/Media | Writers, Editors, Public Relations |
| 29 | Healthcare Practitioners | Physicians, Nurses, Pharmacists |
| 33 | Protective Service | Police, Firefighters, Security |
| 41 | Sales | Sales Representatives, Real Estate Agents |
| 43 | Office/Administrative | Administrative Assistants, Secretaries |

---

## 2. Eval Prompt Generation

### 2.1 Prompt Structure

Each evaluation prompt consists of:

1. **Role/Context**: Who the writer is (occupation, industry, company type)
2. **Task Description**: What needs to be written
3. **Audience**: Who will read the output
4. **Constraints**: Length, format, tone requirements
5. **Supporting Context** (optional): Additional information needed

### 2.2 Industry Diversification

For each occupation, we generate prompts across diverse industry contexts:

```python
# scripts/industry_diversifier.py

INDUSTRY_TEMPLATES = {
    "11-1011.00": {  # Chief Executives
        "industries": [
            {"name": "Tech Startup", "context": "Series B funded AI startup, 50 employees"},
            {"name": "Fortune 500", "context": "Fortune 100 consumer goods company, 50,000 employees"},
            {"name": "Nonprofit", "context": "Environmental conservation nonprofit, $10M budget"},
            {"name": "Healthcare", "context": "Regional hospital network, 5,000 employees"},
            {"name": "Manufacturing", "context": "Mid-size auto parts manufacturer, family-owned"},
            {"name": "Retail", "context": "National grocery chain, union workforce"},
        ]
    },
    "15-1252.00": {  # Software Developers
        "industries": [
            {"name": "Fintech", "context": "Payment processing startup, regulated environment"},
            {"name": "Gaming", "context": "Mobile game studio, creative culture"},
            {"name": "Enterprise", "context": "Enterprise SaaS company, Fortune 500 clients"},
            {"name": "Healthcare", "context": "HIPAA-compliant health records system"},
            {"name": "Defense", "context": "Government contractor, security clearances"},
        ]
    },
    # ... additional occupations
}
```

### 2.3 Writing Task Categories

We classify writing tasks into categories to ensure coverage:

| Category | Description | Examples |
|----------|-------------|----------|
| **Persuasive** | Convince reader to take action | Sales proposals, funding requests |
| **Informational** | Convey information clearly | Status reports, documentation |
| **Instructional** | Teach or guide | Procedures, tutorials, training |
| **Correspondence** | Professional communication | Emails, letters, memos |
| **Creative** | Engaging, narrative content | Marketing copy, speeches |
| **Technical** | Precise, specialized content | Specifications, legal documents |
| **Analytical** | Data-driven insights | Research reports, analyses |

### 2.4 Prompt Template System

```python
# lib/prompt_templates.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class WritingPrompt:
    """Structured writing prompt for evaluation."""

    prompt_id: str
    occupation_code: str
    occupation_title: str
    industry: str
    industry_context: str
    task_category: str
    writing_type: str

    # Core prompt components
    role_description: str
    task_instruction: str
    audience_description: str

    # Optional components
    additional_context: Optional[str] = None
    constraints: Optional[dict] = None
    reference_materials: Optional[str] = None

    def to_simple_prompt(self) -> str:
        """Generate simple prompt without additional context."""
        return f"""You are a {self.role_description}.

Task: {self.task_instruction}

Audience: {self.audience_description}
"""

    def to_full_prompt(self) -> str:
        """Generate complete prompt with all context."""
        prompt = self.to_simple_prompt()

        if self.additional_context:
            prompt += f"\nContext:\n{self.additional_context}\n"

        if self.constraints:
            constraints_text = "\n".join(f"- {k}: {v}" for k, v in self.constraints.items())
            prompt += f"\nRequirements:\n{constraints_text}\n"

        if self.reference_materials:
            prompt += f"\nReference Materials:\n{self.reference_materials}\n"

        return prompt


# Example prompt generation
PROMPT_TEMPLATES = {
    "ceo_board_update": WritingPrompt(
        prompt_id="ceo_board_001",
        occupation_code="11-1011.00",
        occupation_title="Chief Executive",
        industry="Tech Startup",
        industry_context="Series B AI startup, 50 employees",
        task_category="informational",
        writing_type="report",
        role_description="CEO of a Series B funded AI startup with 50 employees",
        task_instruction="Write a quarterly board update email covering company performance, key metrics, challenges faced, and strategic priorities for next quarter.",
        audience_description="Board of directors including 3 VCs, 2 independent directors, and the founder",
        additional_context="""
Q3 Performance Data:
- Revenue: $2.1M (up 40% QoQ)
- ARR: $8.4M
- Customers: 47 enterprise accounts
- Burn rate: $800K/month
- Runway: 18 months
- Team: Grew from 42 to 50 employees
- Key wins: Landed Fortune 500 pilot with Acme Corp
- Challenges: Senior engineer departure, delayed product launch by 3 weeks
""",
        constraints={
            "length": "500-800 words",
            "tone": "Professional but confident",
            "format": "Email with clear sections"
        }
    ),

    "nurse_handoff": WritingPrompt(
        prompt_id="nurse_handoff_001",
        occupation_code="29-1141.00",
        occupation_title="Registered Nurse",
        industry="Hospital",
        industry_context="Urban teaching hospital, ICU",
        task_category="informational",
        writing_type="clinical_note",
        role_description="ICU nurse at an urban teaching hospital completing a 12-hour shift",
        task_instruction="Write a shift handoff note for the incoming nurse covering patient status, treatments administered, concerns, and pending tasks.",
        audience_description="Incoming night shift ICU nurse who has not seen this patient before",
        additional_context="""
Patient: 67-year-old male, Day 3 post-CABG
- Vitals: BP 128/76, HR 82, Temp 37.2C, SpO2 96% on 2L NC
- Drains: Chest tubes to suction, 50mL serosanguinous output last 4 hours
- Meds: Metoprolol 25mg BID, Aspirin 81mg, Heparin drip at 800 units/hr
- Labs pending: Evening CBC, BMP at 1800
- Concerns: Intermittent confusion this afternoon, possible sundowning
- Family: Wife visited 1400-1700, updated on condition
- Plan: PT eval tomorrow AM, possible step-down if stable overnight
""",
        constraints={
            "format": "SBAR format preferred",
            "length": "200-400 words",
            "tone": "Clinical, precise"
        }
    )
}
```

---

## 3. Context Generation

### 3.1 Context Categories

Different writing tasks require different types of supporting context:

| Context Type | Description | Generation Method |
|--------------|-------------|-------------------|
| **Numerical Data** | Metrics, statistics, financial data | Synthetic generation with realistic distributions |
| **Background Info** | Company history, project details | LLM generation with validation |
| **Reference Docs** | Policies, prior communications | Template-based generation |
| **Stakeholder Info** | People involved, relationships | Structured persona generation |
| **Timeline/Events** | Chronology of relevant events | Procedural generation |

### 3.2 Synthetic Context Generator

```python
# lib/context_generator.py

import random
from typing import Any

class ContextGenerator:
    """Generate realistic synthetic context for writing prompts."""

    def generate_company_metrics(self, company_type: str, quarter: int) -> dict:
        """Generate realistic company performance metrics."""

        base_metrics = {
            "startup": {
                "revenue_range": (500000, 5000000),
                "growth_rate": (0.2, 0.6),
                "employee_range": (20, 200),
                "customer_range": (10, 500)
            },
            "enterprise": {
                "revenue_range": (100000000, 10000000000),
                "growth_rate": (0.02, 0.15),
                "employee_range": (5000, 100000),
                "customer_range": (1000, 1000000)
            },
            "nonprofit": {
                "budget_range": (1000000, 100000000),
                "growth_rate": (-0.05, 0.20),
                "employee_range": (10, 500),
                "donor_range": (100, 50000)
            }
        }

        params = base_metrics.get(company_type, base_metrics["startup"])

        return {
            "revenue": random.randint(*params["revenue_range"]),
            "growth_rate": round(random.uniform(*params["growth_rate"]), 2),
            "employees": random.randint(*params["employee_range"]),
            "customers": random.randint(*params["customer_range"]),
            "quarter": quarter
        }

    def generate_patient_data(self, condition_type: str) -> dict:
        """Generate synthetic patient data for healthcare prompts."""

        conditions = {
            "post_surgical": {
                "vitals": {
                    "bp_systolic": (110, 140),
                    "bp_diastolic": (60, 90),
                    "heart_rate": (60, 100),
                    "temp_celsius": (36.5, 37.8),
                    "spo2": (94, 99)
                },
                "common_concerns": [
                    "Pain management", "Wound healing", "Mobility",
                    "DVT risk", "Infection signs", "Fluid balance"
                ]
            },
            # Additional condition templates...
        }

        params = conditions.get(condition_type, conditions["post_surgical"])
        vitals = params["vitals"]

        return {
            "bp": f"{random.randint(*vitals['bp_systolic'])}/{random.randint(*vitals['bp_diastolic'])}",
            "hr": random.randint(*vitals["heart_rate"]),
            "temp": round(random.uniform(*vitals["temp_celsius"]), 1),
            "spo2": random.randint(*vitals["spo2"]),
            "concerns": random.sample(params["common_concerns"], k=2)
        }

    def generate_project_context(self, project_type: str) -> str:
        """Generate project background context using templates."""

        templates = {
            "software": """
Project: {project_name}
Timeline: Started {start_date}, Target completion {end_date}
Team: {team_size} engineers, {pm_count} PM, {designer_count} designers
Tech Stack: {tech_stack}
Current Status: {status}
Key Milestones:
{milestones}
Blockers:
{blockers}
""",
            "construction": """
Project: {project_name}
Location: {location}
Budget: ${budget:,}
Timeline: {start_date} - {end_date}
Current Phase: {phase}
Contractor: {contractor}
Permits: {permit_status}
Safety Record: {safety_record}
"""
        }

        # Fill templates with generated values
        # ... implementation details
        pass
```

### 3.3 LLM-Assisted Context Generation

For complex contexts, we use a smaller model to generate realistic details:

```python
# lib/context_llm.py

import openai

CONTEXT_GENERATION_PROMPT = """You are generating realistic context for a writing evaluation task.

Occupation: {occupation}
Industry: {industry}
Writing Task: {task}

Generate detailed, realistic supporting context that a person in this role would have access to when completing this writing task. Include:
- Specific names (people, companies, products)
- Realistic numbers and dates
- Plausible scenarios and relationships
- Industry-appropriate terminology

Output JSON with the following structure:
{{
    "stakeholders": [list of people involved with names and roles],
    "key_facts": [list of relevant facts and figures],
    "timeline": [list of relevant events with dates],
    "constraints": [any limitations or requirements],
    "background": "brief narrative background"
}}
"""

class LLMContextGenerator:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

    def generate_context(self, occupation: str, industry: str, task: str) -> dict:
        """Generate context using a fast, cheap model."""

        response = self.client.chat.completions.create(
            model="google/gemini-2.0-flash-001",  # Fast, cheap for context gen
            messages=[{
                "role": "user",
                "content": CONTEXT_GENERATION_PROMPT.format(
                    occupation=occupation,
                    industry=industry,
                    task=task
                )
            }],
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)
```

---

## 4. Model Integration

### 4.1 OpenRouter Configuration

```python
# lib/model_client.py

from dataclasses import dataclass
from typing import Optional
import httpx
import asyncio

@dataclass
class ModelConfig:
    """Configuration for a model accessible via OpenRouter."""
    model_id: str
    display_name: str
    provider: str
    max_tokens: int = 4096
    temperature: float = 0.7

# Models to evaluate
EVAL_MODELS = {
    "gemini-3-pro": ModelConfig(
        model_id="google/gemini-3.0-pro",
        display_name="Gemini 3.0 Pro",
        provider="Google"
    ),
    "gemini-3-flash": ModelConfig(
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
        model_id="anthropic/claude-opus-4-5-20251101",
        display_name="Claude Opus 4.5",
        provider="Anthropic"
    ),
    "grok-3": ModelConfig(
        model_id="x-ai/grok-3",
        display_name="Grok 3",
        provider="xAI"
    ),
    "kimi-k2": ModelConfig(
        model_id="moonshot/kimi-k2",
        display_name="Kimi K2",
        provider="Moonshot"
    ),
}

# Judge model (separate from eval targets)
JUDGE_MODEL = ModelConfig(
    model_id="anthropic/claude-opus-4-5-20251101",
    display_name="Claude Opus 4.5 (Judge)",
    provider="Anthropic",
    temperature=0.3  # Lower temperature for more consistent judging
)


class OpenRouterClient:
    """Async client for OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://gemini-writing-eval.internal",
                "X-Title": "Gemini Writing Evaluation"
            },
            timeout=120.0
        )

    async def generate(
        self,
        model: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate a completion from a model."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.post(
            "/chat/completions",
            json={
                "model": model.model_id,
                "messages": messages,
                "max_tokens": model.max_tokens,
                "temperature": model.temperature
            }
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def generate_pair(
        self,
        model_a: ModelConfig,
        model_b: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> tuple[str, str]:
        """Generate completions from two models in parallel."""

        results = await asyncio.gather(
            self.generate(model_a, prompt, system_prompt),
            self.generate(model_b, prompt, system_prompt)
        )
        return results[0], results[1]
```

---

## 5. Judging Framework

### 5.1 Evaluation Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Clarity** | 20% | Ideas are expressed clearly and unambiguously |
| **Tone Appropriateness** | 15% | Tone matches context, audience, and purpose |
| **Effectiveness** | 20% | Writing achieves its stated purpose |
| **Structure** | 15% | Logical organization, good flow |
| **Completeness** | 15% | All required elements addressed |
| **Conciseness** | 10% | Appropriate length, no unnecessary content |
| **Professionalism** | 5% | Grammar, spelling, formatting |

### 5.2 Expert Writer Persona

```python
EXPERT_WRITER_SYSTEM_PROMPT = """You are an expert writing evaluator with 20+ years of experience across professional, technical, and creative writing. You have:

- Taught writing at top universities
- Edited for major publications
- Consulted Fortune 500 companies on communications
- Deep expertise in business, technical, and persuasive writing

Your evaluation philosophy:
- Great writing serves its purpose for its audience
- Clarity and effectiveness trump stylistic flourishes
- Context determines what "good" means
- Small errors matter less than overall impact

You evaluate writing rigorously but fairly, acknowledging strengths before noting weaknesses."""

EXPERT_WRITER_EVAL_PROMPT = """Evaluate these two writing samples for the following task:

TASK CONTEXT:
{task_context}

INTENDED AUDIENCE:
{audience}

RESPONSE A:
{response_a}

---

RESPONSE B:
{response_b}

---

Evaluate both responses on these criteria (1-10 scale each):

1. CLARITY: How clearly are ideas expressed?
2. TONE: How appropriate is the tone for this context/audience?
3. EFFECTIVENESS: How well does it achieve the writing's purpose?
4. STRUCTURE: How well organized is the content?
5. COMPLETENESS: Are all necessary elements addressed?
6. CONCISENESS: Is the length appropriate? No unnecessary content?
7. PROFESSIONALISM: Grammar, spelling, formatting quality?

For each criterion, provide:
- Score for Response A (1-10)
- Score for Response B (1-10)
- Brief justification

Then provide your OVERALL VERDICT:
- "A" if Response A is clearly better
- "B" if Response B is clearly better
- "TIE" if they are roughly equivalent

Output your evaluation as JSON:
{{
    "criteria": {{
        "clarity": {{"a": X, "b": Y, "reasoning": "..."}},
        "tone": {{"a": X, "b": Y, "reasoning": "..."}},
        "effectiveness": {{"a": X, "b": Y, "reasoning": "..."}},
        "structure": {{"a": X, "b": Y, "reasoning": "..."}},
        "completeness": {{"a": X, "b": Y, "reasoning": "..."}},
        "conciseness": {{"a": X, "b": Y, "reasoning": "..."}},
        "professionalism": {{"a": X, "b": Y, "reasoning": "..."}}
    }},
    "overall_reasoning": "...",
    "verdict": "A" | "B" | "TIE"
}}
"""
```

### 5.3 Target Recipient Persona

```python
def generate_recipient_persona(occupation: str, audience_description: str) -> str:
    """Generate a recipient persona prompt based on the writing task."""

    return f"""You are the intended recipient of a piece of professional writing. Specifically, you are:

{audience_description}

You are evaluating this writing from your perspective as the reader. Consider:
- Would this writing be useful to you?
- Does it address your needs and concerns?
- Is the tone appropriate for your relationship with the writer?
- Would you feel confident acting on this information?
- Does it respect your time and expertise level?

You are not a writing expert - you are a practical reader who cares about whether the writing serves your needs."""

RECIPIENT_EVAL_PROMPT = """You received two versions of the same document. Evaluate which one better serves your needs.

YOUR ROLE: {recipient_description}

WHAT YOU NEEDED: {task_purpose}

VERSION A:
{response_a}

---

VERSION B:
{response_b}

---

As the intended reader, evaluate:

1. USEFULNESS: How useful is this for your needs? (1-10)
2. CLARITY: How easy was it to understand? (1-10)
3. TRUST: How much do you trust this communication? (1-10)
4. ACTIONABILITY: Can you act on this information? (1-10)
5. APPROPRIATENESS: Is the tone/approach right for you? (1-10)

Then give your PREFERENCE:
- "A" if you prefer Version A
- "B" if you prefer Version B
- "TIE" if no strong preference

Output as JSON:
{{
    "usefulness": {{"a": X, "b": Y, "reasoning": "..."}},
    "clarity": {{"a": X, "b": Y, "reasoning": "..."}},
    "trust": {{"a": X, "b": Y, "reasoning": "..."}},
    "actionability": {{"a": X, "b": Y, "reasoning": "..."}},
    "appropriateness": {{"a": X, "b": Y, "reasoning": "..."}},
    "overall_reasoning": "...",
    "verdict": "A" | "B" | "TIE"
}}
"""
```

### 5.4 Position Shuffling & Best-of-5 Aggregation

```python
# lib/judging.py

import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal

@dataclass
class JudgmentResult:
    """Result of a single judgment."""
    judge_type: Literal["expert", "recipient"]
    position_order: Literal["AB", "BA"]  # Which model was shown first
    raw_verdict: Literal["A", "B", "TIE"]
    normalized_verdict: Literal["model_a", "model_b", "tie"]  # Accounts for position
    criteria_scores: dict
    reasoning: str

@dataclass
class AggregatedResult:
    """Aggregated result from best-of-5 judging."""
    model_a_wins: int
    model_b_wins: int
    ties: int
    final_verdict: Literal["model_a", "model_b", "tie"]
    confidence: float  # 0-1, based on agreement
    individual_judgments: list[JudgmentResult]


class JudgingPipeline:
    """Orchestrates the judging process with position shuffling."""

    def __init__(self, client: OpenRouterClient, judge_model: ModelConfig):
        self.client = client
        self.judge_model = judge_model

    async def run_single_judgment(
        self,
        judge_type: Literal["expert", "recipient"],
        response_a: str,
        response_b: str,
        task_context: str,
        audience: str,
        shuffle: bool = True
    ) -> JudgmentResult:
        """Run a single judgment with optional position shuffling."""

        # Determine position order
        if shuffle and random.random() < 0.5:
            position_order = "BA"
            shown_first, shown_second = response_b, response_a
        else:
            position_order = "AB"
            shown_first, shown_second = response_a, response_b

        # Select appropriate prompt
        if judge_type == "expert":
            system_prompt = EXPERT_WRITER_SYSTEM_PROMPT
            eval_prompt = EXPERT_WRITER_EVAL_PROMPT.format(
                task_context=task_context,
                audience=audience,
                response_a=shown_first,
                response_b=shown_second
            )
        else:
            system_prompt = generate_recipient_persona(task_context, audience)
            eval_prompt = RECIPIENT_EVAL_PROMPT.format(
                recipient_description=audience,
                task_purpose=task_context,
                response_a=shown_first,
                response_b=shown_second
            )

        # Get judgment
        raw_response = await self.client.generate(
            self.judge_model,
            eval_prompt,
            system_prompt
        )

        # Parse response
        judgment_data = json.loads(raw_response)
        raw_verdict = judgment_data["verdict"]

        # Normalize verdict to account for position shuffling
        if position_order == "BA":
            # Swap A/B since we showed them reversed
            if raw_verdict == "A":
                normalized_verdict = "model_b"
            elif raw_verdict == "B":
                normalized_verdict = "model_a"
            else:
                normalized_verdict = "tie"
        else:
            if raw_verdict == "A":
                normalized_verdict = "model_a"
            elif raw_verdict == "B":
                normalized_verdict = "model_b"
            else:
                normalized_verdict = "tie"

        return JudgmentResult(
            judge_type=judge_type,
            position_order=position_order,
            raw_verdict=raw_verdict,
            normalized_verdict=normalized_verdict,
            criteria_scores=judgment_data.get("criteria", {}),
            reasoning=judgment_data.get("overall_reasoning", "")
        )

    async def run_best_of_5(
        self,
        response_a: str,
        response_b: str,
        task_context: str,
        audience: str
    ) -> AggregatedResult:
        """Run 5 judgments (mixed expert/recipient) and aggregate."""

        # 3 expert judgments, 2 recipient judgments
        judge_types = ["expert", "expert", "expert", "recipient", "recipient"]
        random.shuffle(judge_types)

        judgments = []
        for judge_type in judge_types:
            judgment = await self.run_single_judgment(
                judge_type=judge_type,
                response_a=response_a,
                response_b=response_b,
                task_context=task_context,
                audience=audience,
                shuffle=True
            )
            judgments.append(judgment)

        # Count verdicts
        verdicts = [j.normalized_verdict for j in judgments]
        counts = Counter(verdicts)

        model_a_wins = counts.get("model_a", 0)
        model_b_wins = counts.get("model_b", 0)
        ties = counts.get("tie", 0)

        # Determine final verdict (majority wins, ties count as 0.5 each)
        a_score = model_a_wins + (ties * 0.5)
        b_score = model_b_wins + (ties * 0.5)

        if a_score > b_score:
            final_verdict = "model_a"
        elif b_score > a_score:
            final_verdict = "model_b"
        else:
            final_verdict = "tie"

        # Confidence based on agreement (5/5 = 1.0, 3/5 = 0.6, etc.)
        max_agreement = max(model_a_wins, model_b_wins, ties)
        confidence = max_agreement / 5.0

        return AggregatedResult(
            model_a_wins=model_a_wins,
            model_b_wins=model_b_wins,
            ties=ties,
            final_verdict=final_verdict,
            confidence=confidence,
            individual_judgments=judgments
        )
```

---

## 6. Database Schema

### 6.1 SQLite Schema

```sql
-- schema.sql

-- Core tables
CREATE TABLE occupations (
    occupation_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category_code TEXT NOT NULL,
    category_name TEXT NOT NULL,
    writing_importance REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE writing_tasks (
    task_id TEXT PRIMARY KEY,
    occupation_code TEXT NOT NULL,
    task_description TEXT NOT NULL,
    task_category TEXT NOT NULL,  -- persuasive, informational, etc.
    writing_type TEXT NOT NULL,   -- email, report, memo, etc.
    FOREIGN KEY (occupation_code) REFERENCES occupations(occupation_code)
);

CREATE TABLE prompts (
    prompt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    industry TEXT NOT NULL,
    industry_context TEXT,
    prompt_type TEXT NOT NULL,  -- 'simple' or 'full'
    role_description TEXT NOT NULL,
    task_instruction TEXT NOT NULL,
    audience_description TEXT NOT NULL,
    additional_context TEXT,
    constraints_json TEXT,
    full_prompt_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES writing_tasks(task_id)
);

-- Model responses
CREATE TABLE model_responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_display_name TEXT NOT NULL,
    response_text TEXT NOT NULL,
    generation_time_ms INTEGER,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
);

-- Comparisons (pairs of responses to be judged)
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    model_a_id TEXT NOT NULL,
    model_b_id TEXT NOT NULL,
    response_a_id TEXT NOT NULL,
    response_b_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, in_progress, complete
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id),
    FOREIGN KEY (response_a_id) REFERENCES model_responses(response_id),
    FOREIGN KEY (response_b_id) REFERENCES model_responses(response_id)
);

-- Individual judgments
CREATE TABLE judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL,
    judge_type TEXT NOT NULL,  -- 'expert' or 'recipient'
    judge_model_id TEXT NOT NULL,
    position_order TEXT NOT NULL,  -- 'AB' or 'BA'
    raw_verdict TEXT NOT NULL,  -- 'A', 'B', or 'TIE'
    normalized_verdict TEXT NOT NULL,  -- 'model_a', 'model_b', or 'tie'
    criteria_scores_json TEXT,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
);

-- Aggregated results
CREATE TABLE aggregated_results (
    result_id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL UNIQUE,
    model_a_wins INTEGER NOT NULL,
    model_b_wins INTEGER NOT NULL,
    ties INTEGER NOT NULL,
    final_verdict TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comparison_id) REFERENCES comparisons(comparison_id)
);

-- Indexes for common queries
CREATE INDEX idx_prompts_task ON prompts(task_id);
CREATE INDEX idx_prompts_industry ON prompts(industry);
CREATE INDEX idx_responses_prompt ON model_responses(prompt_id);
CREATE INDEX idx_responses_model ON model_responses(model_id);
CREATE INDEX idx_comparisons_models ON comparisons(model_a_id, model_b_id);
CREATE INDEX idx_comparisons_status ON comparisons(status);
CREATE INDEX idx_judgments_comparison ON judgments(comparison_id);
CREATE INDEX idx_aggregated_comparison ON aggregated_results(comparison_id);

-- Views for analysis
CREATE VIEW v_model_pair_results AS
SELECT
    c.model_a_id,
    c.model_b_id,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN ar.final_verdict = 'model_a' THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN ar.final_verdict = 'model_b' THEN 1 ELSE 0 END) as model_b_wins,
    SUM(CASE WHEN ar.final_verdict = 'tie' THEN 1 ELSE 0 END) as ties,
    AVG(ar.confidence) as avg_confidence
FROM comparisons c
JOIN aggregated_results ar ON c.comparison_id = ar.comparison_id
GROUP BY c.model_a_id, c.model_b_id;

CREATE VIEW v_results_by_category AS
SELECT
    wt.task_category,
    c.model_a_id,
    c.model_b_id,
    COUNT(*) as total,
    SUM(CASE WHEN ar.final_verdict = 'model_a' THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN ar.final_verdict = 'model_b' THEN 1 ELSE 0 END) as model_b_wins
FROM comparisons c
JOIN aggregated_results ar ON c.comparison_id = ar.comparison_id
JOIN prompts p ON c.prompt_id = p.prompt_id
JOIN writing_tasks wt ON p.task_id = wt.task_id
GROUP BY wt.task_category, c.model_a_id, c.model_b_id;

CREATE VIEW v_results_by_industry AS
SELECT
    p.industry,
    c.model_a_id,
    c.model_b_id,
    COUNT(*) as total,
    SUM(CASE WHEN ar.final_verdict = 'model_a' THEN 1 ELSE 0 END) as model_a_wins,
    SUM(CASE WHEN ar.final_verdict = 'model_b' THEN 1 ELSE 0 END) as model_b_wins
FROM comparisons c
JOIN aggregated_results ar ON c.comparison_id = ar.comparison_id
JOIN prompts p ON c.prompt_id = p.prompt_id
GROUP BY p.industry, c.model_a_id, c.model_b_id;
```

### 6.2 Database Access Layer

```python
# lib/database.py

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator
import uuid

class EvalDatabase:
    """Database access layer for the evaluation framework."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database with schema."""
        with self._get_connection() as conn:
            schema_path = Path(__file__).parent.parent / "schema.sql"
            with open(schema_path) as f:
                conn.executescript(f.read())

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def insert_prompt(self, prompt: WritingPrompt) -> str:
        """Insert a writing prompt and return its ID."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO prompts (
                    prompt_id, task_id, industry, industry_context,
                    prompt_type, role_description, task_instruction,
                    audience_description, additional_context,
                    constraints_json, full_prompt_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt.prompt_id,
                prompt.task_id,
                prompt.industry,
                prompt.industry_context,
                "full" if prompt.additional_context else "simple",
                prompt.role_description,
                prompt.task_instruction,
                prompt.audience_description,
                prompt.additional_context,
                json.dumps(prompt.constraints) if prompt.constraints else None,
                prompt.to_full_prompt()
            ))
        return prompt.prompt_id

    def insert_response(
        self,
        prompt_id: str,
        model_id: str,
        model_display_name: str,
        response_text: str,
        generation_time_ms: int,
        token_count: int
    ) -> str:
        """Insert a model response."""
        response_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO model_responses (
                    response_id, prompt_id, model_id, model_display_name,
                    response_text, generation_time_ms, token_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                response_id, prompt_id, model_id, model_display_name,
                response_text, generation_time_ms, token_count
            ))
        return response_id

    def insert_comparison(
        self,
        prompt_id: str,
        model_a_id: str,
        model_b_id: str,
        response_a_id: str,
        response_b_id: str
    ) -> str:
        """Create a comparison record."""
        comparison_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO comparisons (
                    comparison_id, prompt_id, model_a_id, model_b_id,
                    response_a_id, response_b_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (
                comparison_id, prompt_id, model_a_id, model_b_id,
                response_a_id, response_b_id
            ))
        return comparison_id

    def insert_judgment(self, comparison_id: str, result: JudgmentResult) -> str:
        """Insert a single judgment."""
        judgment_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO judgments (
                    judgment_id, comparison_id, judge_type, judge_model_id,
                    position_order, raw_verdict, normalized_verdict,
                    criteria_scores_json, reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                judgment_id, comparison_id, result.judge_type,
                JUDGE_MODEL.model_id, result.position_order,
                result.raw_verdict, result.normalized_verdict,
                json.dumps(result.criteria_scores), result.reasoning
            ))
        return judgment_id

    def insert_aggregated_result(
        self,
        comparison_id: str,
        result: AggregatedResult
    ) -> str:
        """Insert aggregated judgment result."""
        result_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO aggregated_results (
                    result_id, comparison_id, model_a_wins, model_b_wins,
                    ties, final_verdict, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, comparison_id, result.model_a_wins,
                result.model_b_wins, result.ties,
                result.final_verdict, result.confidence
            ))

            # Update comparison status
            conn.execute("""
                UPDATE comparisons SET status = 'complete'
                WHERE comparison_id = ?
            """, (comparison_id,))

        return result_id

    def export_to_csv(self, output_dir: Path):
        """Export all tables to CSV files."""
        import csv

        output_dir.mkdir(parents=True, exist_ok=True)

        tables = [
            'occupations', 'writing_tasks', 'prompts',
            'model_responses', 'comparisons', 'judgments',
            'aggregated_results'
        ]

        with self._get_connection() as conn:
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

### 7.1 Pipeline Overview

```
┌─────────────────┐
│  O*NET Data     │
│  Download       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Extract        │
│  Writing Tasks  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │
│  Prompts        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │
│  Responses      │──────┐
│  (All Models)   │      │
└────────┬────────┘      │
         │               │ Parallel
         ▼               │
┌─────────────────┐      │
│  Create         │◄─────┘
│  Comparisons    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Run Judging    │
│  (Best of 5)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Aggregate &    │
│  Analyze        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │
│  Report         │
└─────────────────┘
```

### 7.2 Main Orchestrator

```python
# scripts/run_eval.py

import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

from lib.database import EvalDatabase
from lib.model_client import OpenRouterClient, EVAL_MODELS, JUDGE_MODEL
from lib.judging import JudgingPipeline
from lib.prompt_templates import WritingPrompt

class EvalPipeline:
    """Main evaluation pipeline orchestrator."""

    def __init__(
        self,
        db: EvalDatabase,
        client: OpenRouterClient,
        target_model: str = "gemini-3-pro"
    ):
        self.db = db
        self.client = client
        self.target_model = target_model
        self.judging = JudgingPipeline(client, JUDGE_MODEL)

    async def run_full_eval(
        self,
        prompts: list[WritingPrompt],
        comparison_models: list[str] = None
    ):
        """Run complete evaluation pipeline."""

        if comparison_models is None:
            comparison_models = [m for m in EVAL_MODELS.keys() if m != self.target_model]

        print(f"Starting evaluation with {len(prompts)} prompts")
        print(f"Target model: {self.target_model}")
        print(f"Comparison models: {comparison_models}")

        # Step 1: Generate responses from all models
        print("\n=== Generating Model Responses ===")
        await self._generate_all_responses(prompts)

        # Step 2: Create comparisons (target vs each competitor)
        print("\n=== Creating Comparisons ===")
        comparisons = self._create_comparisons(prompts, comparison_models)

        # Step 3: Run judging
        print("\n=== Running Judgments ===")
        await self._run_all_judgments(comparisons)

        print("\n=== Evaluation Complete ===")

    async def _generate_all_responses(self, prompts: list[WritingPrompt]):
        """Generate responses from all models for all prompts."""

        for prompt in tqdm(prompts, desc="Prompts"):
            tasks = []
            for model_id, model_config in EVAL_MODELS.items():
                tasks.append(self._generate_single_response(prompt, model_config))

            # Run all model generations in parallel
            await asyncio.gather(*tasks)

    async def _generate_single_response(
        self,
        prompt: WritingPrompt,
        model_config
    ):
        """Generate and store a single model response."""
        import time

        start_time = time.time()
        response_text = await self.client.generate(
            model_config,
            prompt.to_full_prompt()
        )
        generation_time = int((time.time() - start_time) * 1000)

        self.db.insert_response(
            prompt_id=prompt.prompt_id,
            model_id=model_config.model_id,
            model_display_name=model_config.display_name,
            response_text=response_text,
            generation_time_ms=generation_time,
            token_count=len(response_text.split())  # Approximate
        )

    def _create_comparisons(
        self,
        prompts: list[WritingPrompt],
        comparison_models: list[str]
    ) -> list[dict]:
        """Create comparison records for target vs each competitor."""

        comparisons = []

        with self.db._get_connection() as conn:
            for prompt in prompts:
                # Get target model response
                target_response = conn.execute("""
                    SELECT response_id FROM model_responses
                    WHERE prompt_id = ? AND model_id = ?
                """, (prompt.prompt_id, EVAL_MODELS[self.target_model].model_id)).fetchone()

                for comp_model in comparison_models:
                    # Get competitor response
                    comp_response = conn.execute("""
                        SELECT response_id FROM model_responses
                        WHERE prompt_id = ? AND model_id = ?
                    """, (prompt.prompt_id, EVAL_MODELS[comp_model].model_id)).fetchone()

                    if target_response and comp_response:
                        comparison_id = self.db.insert_comparison(
                            prompt_id=prompt.prompt_id,
                            model_a_id=EVAL_MODELS[self.target_model].model_id,
                            model_b_id=EVAL_MODELS[comp_model].model_id,
                            response_a_id=target_response['response_id'],
                            response_b_id=comp_response['response_id']
                        )
                        comparisons.append({
                            'comparison_id': comparison_id,
                            'prompt': prompt
                        })

        return comparisons

    async def _run_all_judgments(self, comparisons: list[dict]):
        """Run best-of-5 judging for all comparisons."""

        for comp in tqdm(comparisons, desc="Judging"):
            comparison_id = comp['comparison_id']
            prompt = comp['prompt']

            # Get responses
            with self.db._get_connection() as conn:
                comparison = conn.execute("""
                    SELECT c.*, ra.response_text as response_a_text,
                           rb.response_text as response_b_text
                    FROM comparisons c
                    JOIN model_responses ra ON c.response_a_id = ra.response_id
                    JOIN model_responses rb ON c.response_b_id = rb.response_id
                    WHERE c.comparison_id = ?
                """, (comparison_id,)).fetchone()

            # Run best-of-5 judging
            result = await self.judging.run_best_of_5(
                response_a=comparison['response_a_text'],
                response_b=comparison['response_b_text'],
                task_context=prompt.task_instruction,
                audience=prompt.audience_description
            )

            # Store individual judgments
            for judgment in result.individual_judgments:
                self.db.insert_judgment(comparison_id, judgment)

            # Store aggregated result
            self.db.insert_aggregated_result(comparison_id, result)


async def main():
    parser = argparse.ArgumentParser(description="Run writing evaluation")
    parser.add_argument("--db", default="data/eval.db", help="Database path")
    parser.add_argument("--target", default="gemini-3-pro", help="Target model")
    parser.add_argument("--sample", type=int, help="Sample N prompts (for testing)")
    args = parser.parse_args()

    # Initialize
    db = EvalDatabase(Path(args.db))
    client = OpenRouterClient(os.environ["OPENROUTER_API_KEY"])

    # Load prompts (from generated corpus)
    prompts = load_prompts_from_db(db)

    if args.sample:
        prompts = random.sample(prompts, min(args.sample, len(prompts)))

    # Run evaluation
    pipeline = EvalPipeline(db, client, args.target)
    await pipeline.run_full_eval(prompts)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Analysis & Reporting

### 8.1 Statistical Analysis

```python
# lib/analysis.py

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path

class EvalAnalyzer:
    """Analyze evaluation results."""

    def __init__(self, db: EvalDatabase):
        self.db = db

    def get_overall_win_rates(self) -> pd.DataFrame:
        """Calculate overall win rates for all model pairs."""

        with self.db._get_connection() as conn:
            df = pd.read_sql_query("""
                SELECT * FROM v_model_pair_results
            """, conn)

        df['model_a_win_rate'] = df['model_a_wins'] / df['total_comparisons']
        df['model_b_win_rate'] = df['model_b_wins'] / df['total_comparisons']
        df['tie_rate'] = df['ties'] / df['total_comparisons']

        return df

    def get_win_rates_by_category(self) -> pd.DataFrame:
        """Win rates broken down by writing task category."""

        with self.db._get_connection() as conn:
            df = pd.read_sql_query("""
                SELECT * FROM v_results_by_category
            """, conn)

        df['model_a_win_rate'] = df['model_a_wins'] / df['total']
        df['model_b_win_rate'] = df['model_b_wins'] / df['total']

        return df

    def get_win_rates_by_industry(self) -> pd.DataFrame:
        """Win rates broken down by industry."""

        with self.db._get_connection() as conn:
            df = pd.read_sql_query("""
                SELECT * FROM v_results_by_industry
            """, conn)

        df['model_a_win_rate'] = df['model_a_wins'] / df['total']
        df['model_b_win_rate'] = df['model_b_wins'] / df['total']

        return df

    def calculate_confidence_intervals(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """Calculate Wilson score confidence interval."""

        if total == 0:
            return (0.0, 0.0)

        z = stats.norm.ppf((1 + confidence) / 2)
        p = wins / total

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

        return (max(0, center - margin), min(1, center + margin))

    def identify_weaknesses(
        self,
        target_model: str,
        threshold: float = 0.4
    ) -> dict:
        """Identify areas where target model underperforms."""

        weaknesses = {
            'by_category': [],
            'by_industry': [],
            'by_task_type': []
        }

        # Check by category
        category_df = self.get_win_rates_by_category()
        for _, row in category_df.iterrows():
            if row['model_a_id'] == target_model and row['model_a_win_rate'] < threshold:
                weaknesses['by_category'].append({
                    'category': row['task_category'],
                    'competitor': row['model_b_id'],
                    'win_rate': row['model_a_win_rate'],
                    'sample_size': row['total']
                })

        # Check by industry
        industry_df = self.get_win_rates_by_industry()
        for _, row in industry_df.iterrows():
            if row['model_a_id'] == target_model and row['model_a_win_rate'] < threshold:
                weaknesses['by_industry'].append({
                    'industry': row['industry'],
                    'competitor': row['model_b_id'],
                    'win_rate': row['model_a_win_rate'],
                    'sample_size': row['total']
                })

        return weaknesses
```

### 8.2 Visualization

```python
# lib/visualization.py

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path

class EvalVisualizer:
    """Generate visualizations for evaluation results."""

    def __init__(self, analyzer: EvalAnalyzer, output_dir: Path):
        self.analyzer = analyzer
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set style
        plt.style.use('seaborn-v0_8-whitegrid')
        sns.set_palette("husl")

    def plot_overall_win_rates(self, target_model: str) -> Path:
        """Bar chart of win rates vs each competitor."""

        df = self.analyzer.get_overall_win_rates()
        df = df[df['model_a_id'] == target_model]

        fig, ax = plt.subplots(figsize=(12, 6))

        x = range(len(df))
        width = 0.25

        bars1 = ax.bar([i - width for i in x], df['model_a_win_rate'],
                       width, label=f'{target_model} Wins', color='#2ecc71')
        bars2 = ax.bar(x, df['tie_rate'],
                       width, label='Ties', color='#95a5a6')
        bars3 = ax.bar([i + width for i in x], df['model_b_win_rate'],
                       width, label='Competitor Wins', color='#e74c3c')

        ax.set_xlabel('Competitor Model')
        ax.set_ylabel('Rate')
        ax.set_title(f'{target_model} vs Competitors - Overall Win Rates')
        ax.set_xticks(x)
        ax.set_xticklabels(df['model_b_id'], rotation=45, ha='right')
        ax.legend()
        ax.set_ylim(0, 1)

        plt.tight_layout()
        output_path = self.output_dir / 'overall_win_rates.png'
        plt.savefig(output_path, dpi=150)
        plt.close()

        return output_path

    def plot_heatmap_by_category(self, target_model: str) -> Path:
        """Heatmap of win rates by category and competitor."""

        df = self.analyzer.get_win_rates_by_category()
        df = df[df['model_a_id'] == target_model]

        pivot = df.pivot(index='task_category', columns='model_b_id', values='model_a_win_rate')

        fig, ax = plt.subplots(figsize=(14, 8))

        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn',
                    center=0.5, vmin=0, vmax=1, ax=ax)

        ax.set_title(f'{target_model} Win Rate by Category and Competitor')
        ax.set_xlabel('Competitor')
        ax.set_ylabel('Writing Category')

        plt.tight_layout()
        output_path = self.output_dir / 'category_heatmap.png'
        plt.savefig(output_path, dpi=150)
        plt.close()

        return output_path

    def plot_confidence_intervals(self, target_model: str) -> Path:
        """Plot win rates with confidence intervals."""

        df = self.analyzer.get_overall_win_rates()
        df = df[df['model_a_id'] == target_model]

        fig, ax = plt.subplots(figsize=(12, 6))

        for idx, (_, row) in enumerate(df.iterrows()):
            ci_low, ci_high = self.analyzer.calculate_confidence_intervals(
                int(row['model_a_wins']),
                int(row['total_comparisons'])
            )

            ax.errorbar(idx, row['model_a_win_rate'],
                       yerr=[[row['model_a_win_rate'] - ci_low],
                             [ci_high - row['model_a_win_rate']]],
                       fmt='o', capsize=5, capthick=2, markersize=10)

        ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        ax.set_xlabel('Competitor')
        ax.set_ylabel('Win Rate')
        ax.set_title(f'{target_model} Win Rates with 95% Confidence Intervals')
        ax.set_xticks(range(len(df)))
        ax.set_xticklabels(df['model_b_id'], rotation=45, ha='right')
        ax.set_ylim(0, 1)

        plt.tight_layout()
        output_path = self.output_dir / 'confidence_intervals.png'
        plt.savefig(output_path, dpi=150)
        plt.close()

        return output_path
```

### 8.3 PDF Report Generation

```python
# lib/report.py

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from pathlib import Path
from datetime import datetime

class ReportGenerator:
    """Generate PDF evaluation report."""

    def __init__(self, analyzer: EvalAnalyzer, visualizer: EvalVisualizer):
        self.analyzer = analyzer
        self.visualizer = visualizer
        self.styles = getSampleStyleSheet()

        # Custom styles
        self.styles.add(ParagraphStyle(
            name='Heading1Custom',
            parent=self.styles['Heading1'],
            spaceAfter=20
        ))

    def generate_report(
        self,
        target_model: str,
        output_path: Path
    ):
        """Generate complete PDF report."""

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Title
        story.append(Paragraph(
            f"Writing Evaluation Report: {target_model}",
            self.styles['Title']
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.5*inch))

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['Heading1Custom']))
        summary = self._generate_executive_summary(target_model)
        story.append(Paragraph(summary, self.styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # Overall Results
        story.append(Paragraph("Overall Results", self.styles['Heading1Custom']))

        # Win rates chart
        chart_path = self.visualizer.plot_overall_win_rates(target_model)
        story.append(Image(str(chart_path), width=6*inch, height=3*inch))
        story.append(Spacer(1, 0.2*inch))

        # Results table
        results_table = self._create_results_table(target_model)
        story.append(results_table)
        story.append(Spacer(1, 0.3*inch))

        # Category Analysis
        story.append(Paragraph("Performance by Writing Category", self.styles['Heading1Custom']))
        heatmap_path = self.visualizer.plot_heatmap_by_category(target_model)
        story.append(Image(str(heatmap_path), width=6*inch, height=4*inch))
        story.append(Spacer(1, 0.3*inch))

        # Identified Weaknesses
        story.append(Paragraph("Identified Weaknesses", self.styles['Heading1Custom']))
        weaknesses = self.analyzer.identify_weaknesses(target_model)
        weakness_text = self._format_weaknesses(weaknesses)
        story.append(Paragraph(weakness_text, self.styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # Recommendations
        story.append(Paragraph("Recommendations", self.styles['Heading1Custom']))
        recommendations = self._generate_recommendations(weaknesses)
        story.append(Paragraph(recommendations, self.styles['Normal']))

        # Build PDF
        doc.build(story)

        return output_path

    def _generate_executive_summary(self, target_model: str) -> str:
        """Generate executive summary text."""

        df = self.analyzer.get_overall_win_rates()
        df = df[df['model_a_id'] == target_model]

        avg_win_rate = df['model_a_win_rate'].mean()
        best_competitor = df.loc[df['model_a_win_rate'].idxmax()]['model_b_id']
        worst_competitor = df.loc[df['model_a_win_rate'].idxmin()]['model_b_id']

        return f"""
        This evaluation compared {target_model} against {len(df)} competitor models
        across diverse writing tasks sourced from O*NET occupational data.

        Key Findings:
        - Average win rate: {avg_win_rate:.1%}
        - Strongest performance against: {best_competitor}
        - Most challenging competitor: {worst_competitor}
        - Total comparisons evaluated: {df['total_comparisons'].sum():,}
        """

    def _create_results_table(self, target_model: str) -> Table:
        """Create results summary table."""

        df = self.analyzer.get_overall_win_rates()
        df = df[df['model_a_id'] == target_model]

        data = [['Competitor', 'Win Rate', 'Tie Rate', 'Loss Rate', 'N']]

        for _, row in df.iterrows():
            data.append([
                row['model_b_id'],
                f"{row['model_a_win_rate']:.1%}",
                f"{row['tie_rate']:.1%}",
                f"{row['model_b_win_rate']:.1%}",
                str(int(row['total_comparisons']))
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        return table
```

---

## 9. Quality Assurance

### 9.1 Position Bias Validation

```python
# scripts/validate_position_bias.py

def validate_position_bias(db: EvalDatabase) -> dict:
    """Check for position bias in judgments."""

    with db._get_connection() as conn:
        df = pd.read_sql_query("""
            SELECT position_order, raw_verdict, COUNT(*) as count
            FROM judgments
            GROUP BY position_order, raw_verdict
        """, conn)

    # Calculate win rates by position
    ab_results = df[df['position_order'] == 'AB']
    ba_results = df[df['position_order'] == 'BA']

    ab_a_wins = ab_results[ab_results['raw_verdict'] == 'A']['count'].sum()
    ab_total = ab_results['count'].sum()

    ba_a_wins = ba_results[ba_results['raw_verdict'] == 'A']['count'].sum()
    ba_total = ba_results['count'].sum()

    # Position A should win roughly equally often regardless of actual model
    ab_first_win_rate = ab_a_wins / ab_total if ab_total > 0 else 0
    ba_first_win_rate = ba_a_wins / ba_total if ba_total > 0 else 0

    # Chi-square test for independence
    observed = [[ab_a_wins, ab_total - ab_a_wins],
                [ba_a_wins, ba_total - ba_a_wins]]
    chi2, p_value, _, _ = stats.chi2_contingency(observed)

    return {
        'ab_first_position_win_rate': ab_first_win_rate,
        'ba_first_position_win_rate': ba_first_win_rate,
        'position_bias_detected': p_value < 0.05,
        'chi2_statistic': chi2,
        'p_value': p_value
    }
```

### 9.2 Judge Agreement Analysis

```python
def analyze_judge_agreement(db: EvalDatabase) -> dict:
    """Analyze agreement between expert and recipient judges."""

    with db._get_connection() as conn:
        df = pd.read_sql_query("""
            SELECT comparison_id, judge_type, normalized_verdict
            FROM judgments
        """, conn)

    # Pivot to get expert and recipient verdicts side by side
    expert_verdicts = df[df['judge_type'] == 'expert'].groupby('comparison_id')['normalized_verdict'].apply(list)
    recipient_verdicts = df[df['judge_type'] == 'recipient'].groupby('comparison_id')['normalized_verdict'].apply(list)

    # Calculate majority verdict for each judge type
    agreements = 0
    total = 0

    for comp_id in expert_verdicts.index:
        if comp_id in recipient_verdicts.index:
            expert_majority = max(set(expert_verdicts[comp_id]), key=expert_verdicts[comp_id].count)
            recipient_majority = max(set(recipient_verdicts[comp_id]), key=recipient_verdicts[comp_id].count)

            if expert_majority == recipient_majority:
                agreements += 1
            total += 1

    return {
        'expert_recipient_agreement_rate': agreements / total if total > 0 else 0,
        'total_comparisons': total
    }
```

### 9.3 Sample-Level Inspection

```python
# scripts/inspect_eval.py

def inspect_comparison(db: EvalDatabase, comparison_id: str):
    """Display detailed information about a single comparison."""

    with db._get_connection() as conn:
        # Get comparison details
        comp = conn.execute("""
            SELECT c.*, p.full_prompt_text, p.audience_description,
                   ra.response_text as response_a_text,
                   rb.response_text as response_b_text,
                   ar.final_verdict, ar.confidence
            FROM comparisons c
            JOIN prompts p ON c.prompt_id = p.prompt_id
            JOIN model_responses ra ON c.response_a_id = ra.response_id
            JOIN model_responses rb ON c.response_b_id = rb.response_id
            LEFT JOIN aggregated_results ar ON c.comparison_id = ar.comparison_id
            WHERE c.comparison_id = ?
        """, (comparison_id,)).fetchone()

        # Get individual judgments
        judgments = conn.execute("""
            SELECT * FROM judgments
            WHERE comparison_id = ?
            ORDER BY created_at
        """, (comparison_id,)).fetchall()

    print("=" * 80)
    print(f"COMPARISON: {comparison_id}")
    print("=" * 80)
    print(f"\nMODEL A: {comp['model_a_id']}")
    print(f"MODEL B: {comp['model_b_id']}")
    print(f"\nFINAL VERDICT: {comp['final_verdict']} (confidence: {comp['confidence']:.2f})")

    print("\n" + "-" * 40)
    print("PROMPT:")
    print("-" * 40)
    print(comp['full_prompt_text'][:500] + "...")

    print("\n" + "-" * 40)
    print("RESPONSE A:")
    print("-" * 40)
    print(comp['response_a_text'][:500] + "...")

    print("\n" + "-" * 40)
    print("RESPONSE B:")
    print("-" * 40)
    print(comp['response_b_text'][:500] + "...")

    print("\n" + "-" * 40)
    print("INDIVIDUAL JUDGMENTS:")
    print("-" * 40)
    for j in judgments:
        print(f"\n  {j['judge_type'].upper()} (position: {j['position_order']})")
        print(f"  Raw verdict: {j['raw_verdict']} -> Normalized: {j['normalized_verdict']}")
        print(f"  Reasoning: {j['reasoning'][:200]}...")
```

---

## 10. Directory Structure

```
gemini-writing-eval/
├── README.md
├── requirements.txt
├── schema.sql
├── .env.example
│
├── scripts/
│   ├── download_onet.sh
│   ├── extract_writing_tasks.py
│   ├── generate_prompts.py
│   ├── run_eval.py
│   ├── analyze_results.py
│   ├── generate_report.py
│   ├── inspect_eval.py
│   └── validate_position_bias.py
│
├── lib/
│   ├── __init__.py
│   ├── database.py
│   ├── model_client.py
│   ├── prompt_templates.py
│   ├── context_generator.py
│   ├── judging.py
│   ├── analysis.py
│   ├── visualization.py
│   └── report.py
│
├── data/
│   ├── onet_raw/          # Downloaded O*NET files
│   ├── processed/          # Extracted writing tasks
│   ├── prompts/            # Generated prompts (JSON)
│   └── eval.db             # SQLite database
│
├── output/
│   ├── figures/            # Generated visualizations
│   ├── reports/            # PDF reports
│   └── exports/            # CSV exports
│
└── tests/
    ├── test_judging.py
    ├── test_database.py
    └── test_analysis.py
```

---

## 11. Implementation Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| **Setup** | 1 week | Environment setup, O*NET download, database schema |
| **Prompt Generation** | 2 weeks | Extract tasks, generate prompts, diversify industries |
| **Response Generation** | 1 week | Run all models, store responses |
| **Judging** | 2 weeks | Run best-of-5 judging on all comparisons |
| **Analysis** | 1 week | Statistical analysis, visualization, report generation |
| **QA** | 1 week | Validation, bias checks, manual inspection |

**Total: ~8 weeks for full implementation**

---

## 12. Appendix: Key Metrics

### Sample Size Recommendations

| Metric | Minimum | Recommended |
|--------|---------|-------------|
| Total prompts | 500 | 2,000+ |
| Prompts per occupation | 5 | 20+ |
| Industry variants per occupation | 3 | 6+ |
| Judgments per comparison | 5 | 5 (fixed) |
| Comparisons per model pair | 100 | 500+ |

### Expected Costs (OpenRouter Pricing)

| Component | Tokens/Comparison | Cost/1000 Comparisons |
|-----------|-------------------|----------------------|
| Response generation (6 models) | ~6,000 | ~$12 |
| Judging (5 judges) | ~15,000 | ~$75 |
| Context generation | ~2,000 | ~$4 |
| **Total** | ~23,000 | **~$91** |

For 5,000 comparisons: **~$455**

---

This implementation plan provides a comprehensive framework for evaluating Gemini's writing capabilities against competitors. The methodology ensures rigor through position shuffling, dual-persona judging, and best-of-5 aggregation while maintaining practical feasibility through efficient parallel processing and SQLite storage.
