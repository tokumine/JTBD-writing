# O*NET Task AI Acceleration Analysis Results
## Economic Impact of RAG vs Agentic AI on US Knowledge Work (2025-2027)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Tasks Analyzed** | 18,796 |
| **Tasks Acceleratable by AI** | 15,409 (82.0%) |
| **Wage-Weighted Impact** | **$6.09 Trillion** |
| **GDP Impact (1.75x)** | **$10.65 Trillion** |

### Impact by AI Tier

| AI Tier | Tasks | Wage Impact | GDP Impact |
|---------|-------|-------------|------------|
| **Agentic AI (Tier 2)** | 9,167 (48.8%) | $4.80T | $8.41T |
| **RAG Chatbot (Tier 1)** | 3,829 (20.4%) | $0.85T | $1.49T |
| **Physical + Knowledge** | 2,316 (12.3%) | $0.42T | $0.73T |

---

## Table 1: RAG Chatbot (Tier 1) Acceleratable Tasks

**Total: 3,829 tasks | $853.5B wage impact | $1.49T GDP impact**

RAG chatbots can accelerate tasks involving:
- Information retrieval and research
- Document summarization and synthesis
- Q&A over source documents
- Comparison and verification
- Translation
- Simple writing from templates

### Top 20 Highest-Impact RAG Tasks

| Rank | Task | Occupation | Accel % | Annual Impact |
|------|------|------------|---------|---------------|
| 1 | Direct and coordinate business activities | General and Operations Managers | 30% | $6.51B |
| 2 | Direct administrative activities for products/services | General and Operations Managers | 30% | $6.51B |
| 3 | Perform sales floor work, greeting customers | General and Operations Managers | 30% | $6.51B |
| 4 | Develop product-marketing strategies | General and Operations Managers | 30% | $6.51B |
| 5 | Direct non-merchandising departments | General and Operations Managers | 30% | $6.51B |
| 6 | Train users on new equipment | Software Developers | 30% | $3.89B |
| 7 | Teach mental health classes | Psychiatric Nurses | 30% | $3.84B |
| 8 | Refer patients to specialists | Psychiatric Nurses | 30% | $3.84B |
| 9 | Consult with psychiatrists on complex cases | Psychiatric Nurses | 30% | $3.84B |
| 10 | Participate in professional development | Psychiatric Nurses | 30% | $3.84B |

**Full task list: `/tmp/table1_rag_tasks.csv` (3,829 rows)**

---

## Table 2: Agentic AI (Tier 2) Acceleratable Tasks

**Total: 9,167 tasks | $4.80T wage impact | $8.41T GDP impact**

Agentic AI with code execution can accelerate tasks involving:
- Spreadsheet/calculation work (pandas, openpyxl)
- Database queries (SQL, sqlite3)
- Report generation (python-docx, reportlab)
- Presentation creation (python-pptx)
- Data visualization (matplotlib, plotly)
- Statistical analysis (scipy, statsmodels)
- Web automation (selenium, playwright)
- Image generation and analysis
- Extended multi-step reasoning

### Top 20 Highest-Impact Agentic Tasks

| Rank | Task | Occupation | Software Replaced | Accel % | Annual Impact |
|------|------|------------|-------------------|---------|---------------|
| 1 | Recommend locations for new facilities | General/Ops Managers | Python automation | 80% | $17.37B |
| 2 | Review financial statements, activity reports | General/Ops Managers | Excel, Word | 80% | $17.37B |
| 3 | Direct financial or budget activities | General/Ops Managers | Python automation | 80% | $17.37B |
| 4 | Plan store layouts or design displays | General/Ops Managers | Design | 60% | $13.03B |
| 5 | Implement environmental management programs | General/Ops Managers | Python automation | 60% | $13.03B |
| 6 | Set prices based on demand forecasts | General/Ops Managers | Python automation | 60% | $13.03B |
| 7 | Manage movement of goods in/out of facilities | General/Ops Managers | Python automation | 60% | $13.03B |
| 8 | Monitor suppliers for efficiency | General/Ops Managers | Python automation | 60% | $13.03B |
| 9 | Establish departmental policies and procedures | General/Ops Managers | Python automation | 60% | $13.03B |
| 10 | Perform personnel functions (selection, training) | General/Ops Managers | Python automation | 60% | $13.03B |
| 11 | Prepare reports on project specifications | Software Developers | Word, Email | 80% | $10.36B |
| 12 | Design and modify software systems | Software Developers | Design | 80% | $10.36B |
| 13 | Consult with customers on technical issues | Software Developers | Design | 80% | $10.36B |
| 14 | Confer with project managers on capabilities | Software Developers | Excel | 80% | $10.36B |
| 15 | Supervise programmers and technicians | Software Developers | Design | 80% | $10.36B |

**Full task list: `/tmp/table2_agent_tasks.csv` (9,167 rows)**

---

## Table 3: Software Replacement Summary

Agentic AI can replace commercial software via Python code execution:

| Software Category | Unique Tools | Occupations Using | AI Replacement Potential | Wage Impact |
|-------------------|--------------|-------------------|--------------------------|-------------|
| Other Software | 6,732 | 909 | 30% | $6,085B |
| **Spreadsheets (Excel/Sheets)** | 63 | 864 | **70%** | $5,808B |
| **Statistical/Analytics** | 979 | 758 | **70%** | $5,709B |
| **Word Processing** | 77 | 804 | **70%** | $5,699B |
| Email/Communication | 15 | 721 | 50% | $5,340B |
| **Databases** | 261 | 545 | **70%** | $5,196B |
| **Presentations** | 13 | 633 | **70%** | $4,990B |
| ERP/Business Systems | 177 | 406 | 50% | $4,427B |
| **Project Management** | 38 | 226 | **70%** | $3,506B |
| **Visualization** | 101 | 219 | **70%** | $2,950B |
| CAD/Engineering | 112 | 252 | 30% | $2,199B |
| Graphics/Design | 123 | 231 | 50% | $2,099B |
| Web/Browser | 80 | 131 | 50% | $1,961B |
| CRM | 14 | 95 | 50% | $1,686B |

### Key Software → Python Library Mappings

| Commercial Software | Python Replacement | Acceleration |
|--------------------|-------------------|--------------|
| Microsoft Excel | pandas, openpyxl, xlsxwriter | 70% |
| Microsoft Word | python-docx | 70% |
| Microsoft PowerPoint | python-pptx | 70% |
| Microsoft Access | sqlite3, sqlalchemy | 70% |
| Tableau/Power BI | matplotlib, plotly, seaborn | 70% |
| SAS/SPSS/Stata | scipy, statsmodels | 70% |
| MATLAB | numpy, scipy | 70% |
| Microsoft Project | pandas, scheduling algorithms | 70% |
| Adobe Acrobat | PyPDF, pdf2image | 70% |
| Microsoft Visio | graphviz, diagrams | 70% |

---

## Table 4: SOC Major Group Summary

Economic impact by occupation group:

| SOC | Group Name | Total Tasks | RAG Tasks | Agent Tasks | Employment | Wage Impact ($B) |
|-----|------------|-------------|-----------|-------------|------------|------------------|
| 11 | Management | 1,214 | 247 | 815 | 10.9M | $1,225.10 |
| 29 | Healthcare Practitioners | 1,721 | 466 | 949 | 9.2M | $1,016.45 |
| 13 | Business and Financial | 994 | 212 | 663 | 9.8M | $758.90 |
| 15 | Computer and Mathematical | 770 | 95 | 565 | 5.2M | $616.63 |
| 43 | Office and Administrative | 971 | 220 | 568 | 17.8M | $436.93 |
| 17 | Architecture and Engineering | 1,245 | 138 | 831 | 2.6M | $348.53 |
| 41 | Sales and Related | 425 | 143 | 204 | 13.3M | $270.72 |
| 25 | Educational Instruction | 1,636 | 511 | 908 | 6.9M | $203.33 |
| 53 | Transportation | 917 | 176 | 344 | 13.0M | $176.93 |
| 35 | Food Preparation | 319 | 98 | 77 | 13.5M | $169.82 |
| 47 | Construction | 1,141 | 120 | 168 | 6.3M | $126.00 |
| 51 | Production | 2,117 | 271 | 616 | 6.6M | $107.33 |
| 33 | Protective Service | 522 | 140 | 230 | 3.6M | $105.47 |
| 49 | Installation, Maintenance | 1,008 | 93 | 201 | 6.0M | $98.90 |
| 27 | Arts, Design, Media | 806 | 162 | 503 | 2.0M | $89.08 |
| 19 | Science | 1,227 | 287 | 787 | 1.4M | $86.02 |
| 31 | Healthcare Support | 343 | 78 | 152 | 3.5M | $61.99 |
| 23 | Legal | 123 | 37 | 65 | 1.2M | $61.98 |
| 21 | Community and Social | 292 | 78 | 183 | 1.9M | $54.06 |
| 39 | Personal Care | 617 | 180 | 230 | 3.0M | $44.48 |
| 37 | Building and Grounds | 168 | 31 | 42 | 4.5M | $23.12 |
| 45 | Farming, Fishing | 220 | 46 | 66 | 0.4M | $5.65 |

---

## Table 5: Aggregate Economic Impact Summary

| Category | Task Count | % of Tasks | Wage Impact ($B) | GDP Impact ($B) |
|----------|------------|------------|------------------|-----------------|
| **Agentic AI (Tier 2)** | 9,167 | 48.8% | $4,803.85 | $8,406.74 |
| **RAG Only (Tier 1)** | 3,829 | 20.4% | $853.53 | $1,493.68 |
| **Physical + Knowledge** | 2,316 | 12.3% | $415.01 | $726.27 |
| Human Critical Judgment | 97 | 0.5% | $15.03 | $26.30 |
| Physical Only (Not Acceleratable) | 1,445 | 7.7% | $0.00 | $0.00 |
| Unclassified (Not Acceleratable) | 1,942 | 10.3% | $0.00 | $0.00 |
| **TOTAL ACCELERATABLE** | **15,409** | **82.0%** | **$6,087.42** | **$10,652.99** |

---

## Methodology Notes

### Acceleration Percentages
- **80%**: Excellent agentic match + software boost (AI can fully execute)
- **70%**: Excellent agentic match (direct capability match)
- **60%**: Good agentic match + software boost
- **50%**: Good agentic/RAG match (human review needed)
- **40%**: RAG good match
- **30%**: Partial match (some components acceleratable)
- **15%**: Human critical judgment (minimal acceleration)
- **0%**: Physical only, not acceleratable

### Economic Impact Formula
```
Task_Impact = Employment × Hourly_Wage × 2,080 hours × Task_Share × Acceleration%
GDP_Impact = Wage_Impact × 1.75 (multiplier)
```

### Data Sources
- **O*NET 30.1**: 18,796 task statements, 1,016 occupations
- **BLS OES May 2024**: Employment and wages for 1,396 SOC codes
- **O*NET technology_skills**: 8,785 software tools across 923 occupations

---

## Key Findings

1. **Agentic AI dominates**: Tier 2 (agentic) AI accounts for 79% of total economic acceleration potential ($4.8T of $6.1T wage impact)

2. **Software replacement is key**: Occupations using spreadsheets, databases, and analytics tools see the highest acceleration (70% potential)

3. **Management and healthcare lead**: SOC groups 11 (Management) and 29 (Healthcare Practitioners) account for 37% of total impact

4. **82% of tasks are acceleratable**: Only 18% of O*NET tasks are purely physical or require critical human judgment

5. **Code execution enables higher acceleration**: Agentic AI's ability to write and execute Python code to replace commercial software drives the 5.6x impact multiplier over RAG (4.8T vs 0.85T)

---

## Output Files

| File | Description | Rows |
|------|-------------|------|
| `/tmp/table1_rag_tasks.csv` | All RAG-acceleratable tasks with impact | 3,829 |
| `/tmp/table2_agent_tasks.csv` | All Agentic-acceleratable tasks with software | 9,167 |
| `/tmp/table3_software_replacement.csv` | Software category summary | 14 |
| `/tmp/table4_soc_summary.csv` | SOC major group breakdown | 22 |
| `/tmp/table5_aggregate_impact.csv` | Aggregate summary | 7 |
| `/tmp/tasks_with_impact.csv` | Complete dataset with all calculations | 18,796 |

---

*Analysis completed: January 2025*
*Data sources: O*NET 30.1, BLS OES May 2024*
