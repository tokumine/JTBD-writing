# O*NET Task AI Acceleration Analysis Methodology

## Overview

This document describes the methodology used to analyze the economic acceleration potential of AI technologies on US knowledge work, using O*NET task data and BLS employment/wage statistics.

---

## 1. Data Sources

### 1.1 O*NET 30.1 Database
- **task_statements**: 18,796 individual work tasks across all occupations
- **occupation_data**: 1,016 occupation definitions with SOC codes
- **technology_skills**: 8,785 software tools used across 923 occupations
- **job_zones**: 5-level skill classification (1=minimal to 5=extensive preparation)

### 1.2 BLS Occupational Employment and Wage Statistics (OES) May 2024
- **National-level data**: Employment counts and wages for 1,396 SOC codes
- **Key fields**: TOT_EMP (total employment), H_MEDIAN (median hourly wage), A_MEDIAN (median annual wage)

---

## 2. AI Capability Tier Definitions

### 2.1 Tier 1: RAG Chatbot (NotebookLM-style)
Source-grounded retrieval AI with the following capabilities:

| Capability | Description | Detection Keywords |
|------------|-------------|-------------------|
| Information Retrieval | Find facts in provided documents | research, gather information, collect data, compile, search records |
| Summarization | Condense lengthy documents | summarize, synthesize, condense, extract key |
| Q&A | Answer questions from source material | answer questions, explain, clarify, interpret |
| Comparison | Compare information across sources | compare, contrast, verify, reconcile |
| Translation | Translate between languages | translate, interpret language, bilingual |

**Key Limitations**: Cannot execute code, access external tools, generate images, or perform multi-step autonomous reasoning.

### 2.2 Tier 2: Agentic AI (Claude Code-style)
Full computer use with code execution and multimodal capabilities:

| Capability | Description | Detection Keywords | Software Replaced |
|------------|-------------|-------------------|-------------------|
| Computation | Mathematical and statistical calculations | calculate, compute, statistical, spreadsheet | Excel, SAS, SPSS |
| Code Execution | Write and run scripts/automation | automate, program, database, algorithm | Custom software |
| Visual Creation | Generate diagrams, charts, presentations | diagram, chart, design, presentation | PowerPoint, Visio |
| Visual Understanding | Analyze images and documents | review images, visual inspection | Manual processes |
| Web Research | Real-time search and data gathering | web, online, internet, portal | Manual research |
| Browser Automation | Form filling, portal interaction | submit online, electronic filing | Manual data entry |
| Calendar/Scheduling | Meeting coordination | schedule, appointment, calendar | Manual coordination |
| Document Generation | Create reports and documents | prepare report, draft proposal | Word processing |
| Data Analysis | Pattern recognition and trends | analyze data, trend analysis | Analytics tools |
| Extended Reasoning | Complex multi-step analysis | develop strategy, forecast, optimize | Consulting |

---

## 3. Task Classification Algorithm

### 3.1 Keyword-Based Classification
Each of the 18,796 tasks is classified by matching task text against capability keywords:

```python
def classify_task(task_text):
    task_lower = task_text.lower()

    # RAG capabilities
    rag_retrieval = any(x in task_lower for x in
        ['research', 'gather information', 'collect data', 'compile'])

    rag_summarize = any(x in task_lower for x in
        ['summarize', 'synthesize', 'condense'])

    # Agentic capabilities
    agent_compute = any(x in task_lower for x in
        ['calculate', 'compute', 'statistical', 'spreadsheet'])

    agent_code = any(x in task_lower for x in
        ['automate', 'program', 'database', 'algorithm'])

    # ... additional capability detection

    # Physical task detection (reduces acceleration)
    physical_primary = any(x in task_lower for x in
        ['operate machine', 'assemble', 'install', 'repair', 'lift'])

    return classification_flags
```

### 3.2 Expanded Knowledge Work Patterns
Beyond direct AI capability matches, tasks are classified by general knowledge work patterns:

| Pattern | Detection Keywords | AI Benefit |
|---------|-------------------|------------|
| Analysis/Evaluation | analyze, evaluate, assess, examine, review | Tier 2 |
| Planning/Development | plan, develop, create, design, establish | Tier 2 |
| Coordination/Management | coordinate, manage, supervise, direct | Tier 2 |
| Review/Monitoring | monitor, track, observe, ensure compliance | Tier 1/2 |
| Training/Education | train, teach, instruct, mentor | Tier 1 |
| Customer Communication | customer, client, stakeholder interaction | Tier 1 |
| Record Keeping | record, document, file, maintain records | Tier 2 |
| Decision Making | decide, select, recommend, approve | Tier 2 |

### 3.3 Tier Assignment Logic

```python
def assign_tier(classification_flags):
    rag_score = sum([rag_retrieval, rag_summarize, rag_qa, rag_compare])
    agent_score = sum([agent_compute, agent_code, agent_visual, ...])
    knowledge_score = sum([analysis, planning, coordination, ...])

    # Physical tasks get reduced or zero acceleration
    if physical_primary and not (agent_score or rag_score or knowledge_score):
        return 'Physical_Only', 0.0

    if physical_primary:
        return 'Physical+Knowledge', 0.30

    # Human critical judgment
    if human_critical:
        return 'Human_Critical', 0.15

    # Agentic tier assignment
    if agent_score >= 2:
        return 'Tier2_Excellent', 0.70
    elif agent_score == 1 or knowledge_score >= 2:
        return 'Tier2_Good', 0.50
    elif writing_complex:
        return 'Tier2_Writing', 0.70

    # RAG tier assignment
    if rag_score >= 2:
        return 'Tier1_Excellent', 0.50
    elif rag_score == 1:
        return 'Tier1_Partial', 0.30
    elif knowledge_score >= 1:
        return 'Tier1_Knowledge', 0.30

    return 'Unclassified', 0.0
```

---

## 4. Software Replacement Mapping

### 4.1 Technology Skills Analysis
The O*NET `technology_skills` table contains 8,785 software tools across 923 occupations. Each tool is classified by AI replacement potential:

| Software Category | AI Replacement Method | Potential |
|-------------------|----------------------|-----------|
| Spreadsheets (Excel) | pandas, openpyxl | 70% |
| Word Processing | python-docx | 70% |
| Presentations | python-pptx | 70% |
| Databases (SQL) | sqlite3, sqlalchemy | 70% |
| Statistical (SAS/SPSS) | scipy, statsmodels | 70% |
| Visualization (Tableau) | matplotlib, plotly | 70% |
| Email/Communication | smtplib, APIs | 50% |
| ERP/Business Systems | API integration | 50% |
| CAD/Engineering | Partial support | 30% |
| Graphics/Design | PIL, AI image gen | 50% |

### 4.2 Software Boost Calculation
Occupations using high-replacement-potential software receive an acceleration boost:

```python
software_boost = min(software_count / 100, 0.10)  # Cap at 10%
final_acceleration = base_acceleration + software_boost  # Cap at 80%
```

---

## 5. Economic Impact Calculation

### 5.1 Data Preparation

**SOC Code Mapping**: O*NET codes (e.g., "11-1011.00") are mapped to BLS codes (e.g., "11-1011") by truncating to 7 characters.

**Task Share**: Each task's share of occupation labor value:
```
task_share = 1 / (number of tasks for that occupation)
```

### 5.2 Wage-Weighted Impact Formula

```
Task_Annual_Labor_Value = Employment × Hourly_Wage × 2,080 hours × Task_Share

Task_Acceleration_Value = Task_Annual_Labor_Value × Acceleration_Percentage
```

Where:
- **Employment**: BLS TOT_EMP for matching SOC code
- **Hourly_Wage**: BLS H_MEDIAN (or A_MEDIAN / 2,080 if hourly unavailable)
- **2,080**: Standard annual work hours (52 weeks × 40 hours)
- **Acceleration_Percentage**: 0% to 80% based on tier classification

### 5.3 GDP Impact Multiplier

```
GDP_Impact = Wage_Impact × 1.75
```

The 1.75 multiplier accounts for:
- **Employer costs beyond wages** (benefits, payroll taxes): ~1.3x
- **Productivity spillovers and value-add**: ~1.35x
- **Combined multiplier**: 1.3 × 1.35 ≈ 1.75

---

## 6. Acceleration Percentage Assignment

| Classification | Tier | Base % | With Software Boost |
|----------------|------|--------|---------------------|
| Tier2_Excellent | 2 | 70% | 70-80% |
| Tier2_Good | 2 | 50% | 50-60% |
| Tier2_Knowledge | 2 | 50% | 50-60% |
| Tier2_Writing | 2 | 70% | 70-80% |
| Tier1_Excellent | 1 | 50% | N/A |
| Tier1_Good | 1 | 40% | N/A |
| Tier1_Partial | 1 | 30% | N/A |
| Tier1_Knowledge | 1 | 30% | N/A |
| Physical+Knowledge | - | 30% | N/A |
| Human_Critical | - | 15% | N/A |
| Physical_Only | - | 0% | N/A |
| Unclassified | - | 0% | N/A |

---

## 7. Aggregation Levels

Results are aggregated at multiple levels:

1. **Per-Task**: Individual task acceleration value
2. **Per-Occupation**: Sum of task values for each O*NET occupation
3. **Per-SOC-Major**: Sum by 2-digit SOC code (22 occupation groups)
4. **Per-AI-Tier**: Total by RAG (Tier 1) vs Agentic (Tier 2)
5. **Per-Software-Category**: By software type replaced
6. **National Total**: Sum of all acceleratable value

---

## 8. Validation and Sanity Checks

### 8.1 Reference Benchmarks

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| US Total Employment | ~160M | 154M (BLS) | ✓ |
| US Labor Compensation | ~$12T | - | - |
| US GDP | ~$28T | - | - |
| Maximum Theoretical Impact | <$8T | $6.1T wage | ✓ |

### 8.2 Validation Rules Applied
1. Acceleration percentages capped at 80%
2. Physical-only tasks receive 0% acceleration
3. Human critical judgment tasks capped at 15%
4. Total impact validated against US GDP benchmarks

---

## 9. Limitations and Assumptions

### 9.1 Key Assumptions
- **Timeframe**: 2025-2027 (near-term AI capabilities)
- **Adoption rate**: 100% theoretical maximum (actual adoption will be lower)
- **Hours per year**: 2,080 standard work hours
- **GDP multiplier**: 1.75x (industry standard for labor productivity)

### 9.2 Limitations
1. **Keyword matching**: May miss tasks described with unusual terminology
2. **Task independence**: Assumes tasks can be accelerated independently
3. **Employment data**: Uses national averages; regional variation exists
4. **Software mapping**: Some specialized software may be misclassified
5. **Adoption barriers**: Does not account for regulatory, cultural, or organizational barriers

### 9.3 Conservative vs Aggressive Estimates
This analysis uses **aggressive** acceleration estimates (30-70% range). Conservative estimates would be approximately 50% lower.

---

## 10. Output Files

| File | Description | Records |
|------|-------------|---------|
| `tasks_with_impact.csv` | Complete dataset with all classifications and calculations | 18,796 |
| `table1_rag_tasks.csv` | RAG-acceleratable tasks with impact values | 3,829 |
| `table2_agent_tasks.csv` | Agentic-acceleratable tasks with software mapping | 9,167 |
| `table3_software_replacement.csv` | Software category summary | 14 |
| `table4_soc_summary.csv` | SOC major group breakdown | 22 |
| `table5_aggregate_impact.csv` | Aggregate economic impact | 7 |

---

## 11. Reproducibility

### 11.1 Data Sources
- O*NET 30.1: https://www.onetcenter.org/database.html
- BLS OES May 2024: https://www.bls.gov/oes/

### 11.2 Code
Classification and impact calculation performed using Python with:
- pandas (data manipulation)
- sqlite3 (O*NET database queries)
- openpyxl (BLS Excel file reading)

---

*Methodology version: 1.0*
*Analysis date: January 2025*
