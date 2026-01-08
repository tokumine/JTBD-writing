# O*NET Database Reference for Writing Evaluation Framework

This document provides a comprehensive reference for accessing the O*NET 30.1 database (`db/onet.db`) to support the Gemini Writing Evaluation Framework defined in PROMPT.md.

---

## Database Overview

| Metric | Value |
|--------|-------|
| Total Task Statements | 18,796 |
| Unique Occupations | 1,016 (923 with tasks) |
| Emerging Tasks | 328 |
| Detailed Work Activities (DWAs) | 2,087 |

---

## INFERRED WRITING NEEDS BY CATEGORY

Based on comprehensive analysis of all 18,796 task statements, effective writing is needed across these categories:

### 1. EXPLICIT WRITING & DOCUMENTATION TASKS (~2,500+ tasks)

**Direct writing keywords**: write, draft, prepare, document, compose, author, create

Sample task patterns:
- "Write project proposals, grant applications, or other documents..."
- "Prepare reports concerning activities, expenses, budgets..."
- "Draft speeches for company executives..."
- "Document testing procedures, methodologies, or criteria..."
- "Write press releases, prepare information for media kits..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%write%'
   OR t.task LIKE '%draft%'
   OR t.task LIKE '%document%'
   OR t.task LIKE '%prepare report%'
   OR t.task LIKE '%prepare%proposal%'
   OR t.task LIKE '%compose%';
```

### 2. PROFESSIONAL CORRESPONDENCE (~1,500+ tasks)

**Keywords**: correspond, email, letter, memo, communicate, notify, inform, contact

Sample patterns:
- "Correspond with customers to answer questions or resolve complaints"
- "Contact organizations to explain services and facilities offered"
- "Notify credit departments when customers fail to respond..."
- "Inform customers of estimated delivery schedules..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%correspond%'
   OR t.task LIKE '%email%'
   OR t.task LIKE '%letter%'
   OR t.task LIKE '%memo%'
   OR t.task LIKE '%notify%customer%'
   OR t.task LIKE '%inform%customer%';
```

### 3. REPORTS & ANALYSIS COMMUNICATION (~3,000+ tasks)

**Keywords**: report, present, summarize, analyze, review, evaluate

Sample patterns:
- "Prepare and maintain production reports or personnel records"
- "Present purchase offers to sellers for consideration"
- "Review financial statements, sales or activity reports..."
- "Produce reports regarding nonconformance of products..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%report%'
   OR t.task LIKE '%present%finding%'
   OR t.task LIKE '%present%result%'
   OR t.task LIKE '%summarize%'
   OR t.task LIKE '%prepare%presentation%';
```

### 4. PERSUASION & NEGOTIATION (~1,200+ tasks)

**Keywords**: negotiate, propose, persuade, recommend, advise, convince, pitch, sell

Sample patterns:
- "Negotiate prices and terms with suppliers..."
- "Prepare proposals, quotes, contracts, or presentations..."
- "Persuade customers to purchase products..."
- "Recommend modifications to products..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%negotiat%'
   OR t.task LIKE '%propos%'
   OR t.task LIKE '%persuad%'
   OR t.task LIKE '%recommend%'
   OR t.task LIKE '%advise%client%'
   OR t.task LIKE '%advise%customer%';
```

### 5. POLICY & PROCEDURE COMMUNICATION (~800+ tasks)

**Keywords**: policy, procedure, guideline, regulation, standard, protocol, rule

Sample patterns:
- "Develop policies for food service or nutritional programs..."
- "Create or implement security standards, policies, and procedures"
- "Interpret and explain policies, rules, regulations..."
- "Establish or implement departmental policies, goals, objectives..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%develop%polic%'
   OR t.task LIKE '%implement%polic%'
   OR t.task LIKE '%write%procedure%'
   OR t.task LIKE '%prepare%guideline%'
   OR t.task LIKE '%establish%standard%';
```

### 6. CUSTOMER/CLIENT COMMUNICATION (~2,000+ tasks)

**Keywords**: customer, client, patient, explain, answer, respond, resolve, complaint

Sample patterns:
- "Resolve customer complaints regarding sales and service"
- "Answer customers' questions about products, prices, availability..."
- "Explain products or services and prices..."
- "Consult with clients after sales to resolve problems..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%customer%question%'
   OR t.task LIKE '%client%question%'
   OR t.task LIKE '%answer%question%'
   OR t.task LIKE '%resolve%complaint%'
   OR t.task LIKE '%explain%to%customer%'
   OR t.task LIKE '%respond%to%customer%';
```

### 7. INSTRUCTIONAL & TRAINING CONTENT (~1,000+ tasks)

**Keywords**: train, instruct, teach, educate, develop curriculum, prepare materials

Sample patterns:
- "Train and supervise other translators or interpreters"
- "Instruct staff in quality control and analytical procedures"
- "Develop curriculum and prepare manuals, visual aids..."
- "Provide training and supervision in therapy techniques..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%train%staff%'
   OR t.task LIKE '%train%employee%'
   OR t.task LIKE '%instruct%'
   OR t.task LIKE '%develop%curriculum%'
   OR t.task LIKE '%prepare%manual%'
   OR t.task LIKE '%prepare%training%';
```

### 8. INTERNAL COORDINATION (~2,500+ tasks)

**Keywords**: coordinate, confer, collaborate, meet, discuss, communicate with

Sample patterns:
- "Confer with department heads to plan advertising services..."
- "Coordinate with the media to disseminate advertising"
- "Collaborate with other health care professionals..."
- "Meet with department heads to discuss issues..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%confer with%'
   OR t.task LIKE '%coordinate with%'
   OR t.task LIKE '%collaborate with%'
   OR t.task LIKE '%meet with%'
   OR t.task LIKE '%communicate with%management%'
   OR t.task LIKE '%communicate with%staff%';
```

### 9. CONTRACTS & LEGAL DOCUMENTS (~600+ tasks)

**Keywords**: contract, agreement, legal, license, permit, compliance

Sample patterns:
- "Prepare and negotiate advertising and sales contracts"
- "Draw up contracts for advertising work..."
- "Prepare rental or lease agreements..."
- "Prepare documentation for contracts, transactions, or regulatory compliance"

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%prepare%contract%'
   OR t.task LIKE '%draft%contract%'
   OR t.task LIKE '%write%agreement%'
   OR t.task LIKE '%prepare%permit%'
   OR t.task LIKE '%prepare%compliance%';
```

### 10. FEEDBACK & EVALUATION COMMUNICATION (~1,500+ tasks)

**Keywords**: evaluate, assess, review, feedback, critique, appraise, performance

Sample patterns:
- "Evaluate employees' job performance and conformance to regulations..."
- "Provide feedback and interpretation to production management..."
- "Review and approve quality plans submitted by contractors"
- "Analyze and evaluate security operations..."

**SQL to extract:**
```sql
SELECT t.task_id, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%evaluate%performance%'
   OR t.task LIKE '%provide%feedback%'
   OR t.task LIKE '%review%and%recommend%'
   OR t.task LIKE '%assess%and%report%';
```

---

## KEY DATABASE TABLES

### Primary Tables for Prompt Generation

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `task_statements` | 18,796 individual writing tasks | task_id, onetsoc_code, task, task_type |
| `occupation_data` | 1,016 occupation definitions | onetsoc_code, title, description |
| `job_zones` | Skill level classification (1-5) | onetsoc_code, job_zone |
| `emerging_tasks` | 328 new/updated tasks | onetsoc_code, task, task_type |

### Contextual Tables for Enrichment

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `work_context` | Communication frequency data | onetsoc_code, element_id, data_value |
| `skills` | Skill importance ratings | onetsoc_code, element_id, data_value |
| `abilities` | Ability importance ratings | onetsoc_code, element_id, data_value |
| `work_styles` | Work style characteristics | onetsoc_code, element_id, data_value |
| `dwa_reference` | Detailed work activities | dwa_id, dwa_title |
| `content_model_reference` | Element definitions | element_id, element_name, description |

---

## JOB ZONES (Skill Levels)

```sql
SELECT * FROM job_zone_reference;
```

| Zone | Name | Occupations |
|------|------|-------------|
| 1 | Little or No Preparation Needed | 33 |
| 2 | Some Preparation Needed | 298 |
| 3 | Medium Preparation Needed | 213 |
| 4 | Considerable Preparation Needed | 225 |
| 5 | Extensive Preparation Needed | 154 |

**Usage**: Job zone affects formality level, vocabulary complexity, and writing sophistication expected.

---

## SOC MAJOR OCCUPATION GROUPS (22 groups)

```sql
SELECT DISTINCT SUBSTR(onetsoc_code, 1, 2) as soc_major,
  CASE SUBSTR(onetsoc_code, 1, 2)
    WHEN '11' THEN 'Management'
    WHEN '13' THEN 'Business and Financial Operations'
    WHEN '15' THEN 'Computer and Mathematical'
    WHEN '17' THEN 'Architecture and Engineering'
    WHEN '19' THEN 'Life, Physical, and Social Science'
    WHEN '21' THEN 'Community and Social Service'
    WHEN '23' THEN 'Legal'
    WHEN '25' THEN 'Educational Instruction and Library'
    WHEN '27' THEN 'Arts, Design, Entertainment, Sports, Media'
    WHEN '29' THEN 'Healthcare Practitioners and Technical'
    WHEN '31' THEN 'Healthcare Support'
    WHEN '33' THEN 'Protective Service'
    WHEN '35' THEN 'Food Preparation and Serving'
    WHEN '37' THEN 'Building and Grounds Cleaning'
    WHEN '39' THEN 'Personal Care and Service'
    WHEN '41' THEN 'Sales and Related'
    WHEN '43' THEN 'Office and Administrative Support'
    WHEN '45' THEN 'Farming, Fishing, and Forestry'
    WHEN '47' THEN 'Construction and Extraction'
    WHEN '49' THEN 'Installation, Maintenance, Repair'
    WHEN '51' THEN 'Production'
    WHEN '53' THEN 'Transportation and Material Moving'
    WHEN '55' THEN 'Military Specific'
  END as occupation_group
FROM occupation_data;
```

| Code | Group | Count |
|------|-------|-------|
| 11 | Management | 59 |
| 13 | Business and Financial Operations | 50 |
| 15 | Computer and Mathematical | 38 |
| 17 | Architecture and Engineering | 59 |
| 19 | Life, Physical, and Social Science | 66 |
| 21 | Community and Social Service | 18 |
| 23 | Legal | 8 |
| 25 | Educational Instruction and Library | 68 |
| 27 | Arts, Design, Entertainment, Sports, Media | 45 |
| 29 | Healthcare Practitioners and Technical | 96 |
| 31 | Healthcare Support | 20 |
| 33 | Protective Service | 28 |
| 35 | Food Preparation and Serving | 18 |
| 37 | Building and Grounds Cleaning | 10 |
| 39 | Personal Care and Service | 34 |
| 41 | Sales and Related | 23 |
| 43 | Office and Administrative Support | 55 |
| 45 | Farming, Fishing, and Forestry | 14 |
| 47 | Construction and Extraction | 65 |
| 49 | Installation, Maintenance, Repair | 52 |
| 51 | Production | 114 |
| 53 | Transportation and Material Moving | 57 |
| 55 | Military Specific | 19 |

---

## WRITING-RELATED WORK CONTEXT ELEMENTS

Use these to identify occupations with high writing requirements:

### Communication Frequency Elements

| Element ID | Name | Description |
|------------|------|-------------|
| 4.C.1.a.2.h | E-Mail | How frequently job requires email |
| 4.C.1.a.2.j | Written Letters and Memos | Frequency of written correspondence |
| 4.C.1.a.2.c | Public Speaking | Frequency of presentations |
| 4.C.1.a.2.l | Face-to-Face Discussions | Frequency of verbal communication |
| 4.C.1.a.4 | Contact With Others | Amount of interpersonal contact |

**SQL to get high email frequency occupations:**
```sql
SELECT o.onetsoc_code, o.title, wc.data_value as email_freq
FROM occupation_data o
JOIN work_context wc ON o.onetsoc_code = wc.onetsoc_code
WHERE wc.element_id = '4.C.1.a.2.h' AND wc.scale_id = 'CX'
ORDER BY wc.data_value DESC
LIMIT 50;
```

**SQL to get high written correspondence frequency:**
```sql
SELECT o.onetsoc_code, o.title, wc.data_value as letter_freq
FROM occupation_data o
JOIN work_context wc ON o.onetsoc_code = wc.onetsoc_code
WHERE wc.element_id = '4.C.1.a.2.j' AND wc.scale_id = 'CX'
ORDER BY wc.data_value DESC
LIMIT 50;
```

---

## WRITING-RELATED ABILITIES & SKILLS

### Key Ability Elements

| Element ID | Name | Description |
|------------|------|-------------|
| 1.A.1.a.2 | Written Comprehension | Ability to read and understand written information |
| 1.A.1.a.4 | Written Expression | Ability to communicate in writing |
| 1.A.1.a.3 | Oral Expression | Ability to communicate verbally |
| 1.A.1.b.1 | Fluency of Ideas | Ability to generate ideas |

**SQL to get occupations by written expression importance:**
```sql
SELECT o.onetsoc_code, o.title, a.data_value as writing_ability
FROM occupation_data o
JOIN abilities a ON o.onetsoc_code = a.onetsoc_code
WHERE a.element_id = '1.A.1.a.4' AND a.scale_id = 'IM'
ORDER BY a.data_value DESC
LIMIT 50;
```

### Key Skill Elements

| Element ID | Name |
|------------|------|
| 2.A.1.c | Writing |
| 2.A.1.a | Reading Comprehension |
| 2.A.1.b | Active Listening |
| 2.B.1.a | Critical Thinking |

**SQL to get occupations by writing skill importance:**
```sql
SELECT o.onetsoc_code, o.title, sk.data_value as writing_skill
FROM occupation_data o
JOIN skills sk ON o.onetsoc_code = sk.onetsoc_code
JOIN content_model_reference cm ON sk.element_id = cm.element_id
WHERE cm.element_name = 'Writing' AND sk.scale_id = 'IM'
ORDER BY sk.data_value DESC
LIMIT 50;
```

---

## TOP OCCUPATIONS FOR WRITING EVALUATION

### By Writing Skill Importance (Scale: 1-5)

| Rank | Occupation | Score |
|------|------------|-------|
| 1 | Technical Writers | 4.88 |
| 2 | Writers and Authors | 4.75 |
| 3 | Poets, Lyricists and Creative Writers | 4.75 |
| 4 | Editors | 4.62 |
| 5 | Anthropology Teachers, Postsecondary | 4.62 |
| 6 | Education Administrators, K-12 | 4.50 |
| 7 | Neuropsychologists | 4.38 |
| 8 | Regulatory Affairs Managers | 4.25 |
| 9 | Lawyers | 4.25 |
| 10 | Survey Researchers | 4.25 |

### By Written Correspondence Frequency (Scale: 1-5, 5=daily)

| Rank | Occupation | Score |
|------|------------|-------|
| 1 | Claims Adjusters, Examiners, and Investigators | 4.93 |
| 2 | Ophthalmologists | 4.81 |
| 3 | Oral and Maxillofacial Surgeons | 4.67 |
| 4 | Genetic Counselors | 4.64 |
| 5 | Property, Real Estate, and Community Association Managers | 4.55 |
| 6 | Allergists and Immunologists | 4.55 |
| 7 | Loan Interviewers and Clerks | 4.53 |
| 8 | Human Resources Specialists | 4.52 |
| 9 | Paralegals and Legal Assistants | 4.52 |
| 10 | Administrative Law Judges | 4.51 |

---

## SAMPLE QUERIES FOR PROMPT GENERATION

### Get all tasks for a specific occupation
```sql
SELECT task_id, task, task_type
FROM task_statements
WHERE onetsoc_code = '11-1011.00'  -- Chief Executives
ORDER BY task_type, task_id;
```

### Get occupations with most writing-heavy tasks
```sql
SELECT o.title, COUNT(*) as writing_task_count
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
WHERE t.task LIKE '%write%'
   OR t.task LIKE '%draft%'
   OR t.task LIKE '%document%'
   OR t.task LIKE '%correspond%'
   OR t.task LIKE '%report%'
   OR t.task LIKE '%prepare%'
GROUP BY t.onetsoc_code
ORDER BY writing_task_count DESC
LIMIT 30;
```

### Get tasks by job zone for formality stratification
```sql
SELECT jz.job_zone, o.title, t.task
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
WHERE t.task LIKE '%write%' OR t.task LIKE '%prepare%report%'
ORDER BY jz.job_zone, o.title;
```

### Combine task with occupation context
```sql
SELECT
  o.onetsoc_code,
  o.title as occupation,
  o.description as occupation_desc,
  jz.job_zone,
  t.task,
  t.task_type
FROM task_statements t
JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
WHERE t.task LIKE '%correspond%'
ORDER BY jz.job_zone DESC;
```

---

## NAICS INDUSTRY CODES (External Data Needed)

**IMPORTANT**: O*NET does not contain NAICS industry codes directly.

For industry diversity as required by PROMPT.md, you'll need external data sources:
- BLS Occupation-Industry Matrix (maps occupations to industries)
- Census Bureau NAICS reference
- Commercial databases (SEC filings, Crunchbase)

A typical mapping approach:
1. Extract occupation codes from O*NET
2. Map to NAICS codes using BLS crosswalk
3. Sample across NAICS sectors for diversity

---

## PROMPT GENERATION WORKFLOW

### Phase 1: Task Extraction
1. Extract all task_statements
2. Filter to writing-relevant tasks using inferred categories above
3. Join with occupation_data for context
4. Join with job_zones for skill level

### Phase 2: Context Enrichment
1. Add work_context scores for communication frequency
2. Add skills/abilities scores for writing importance
3. Classify tasks by inferred writing category

### Phase 3: Diversity Sampling
1. Sample evenly across job zones (1-5)
2. Sample evenly across SOC major groups (22 groups)
3. Apply NAICS sampling using external crosswalk
4. Ensure representation of all 10 inferred writing categories

### Phase 4: LLM Enrichment (per PROMPT.md)
1. Add persona details (age, skill level, generation)
2. Add recipient context
3. Add temporal grounding where appropriate
4. Add competing objectives where realistic
5. Add attachments/context where referenced

---

## QUICK REFERENCE: Count by Inferred Category

```sql
-- Approximate counts for writing category distribution
SELECT
  'Explicit Writing' as category,
  COUNT(*) as count
FROM task_statements
WHERE task LIKE '%write%' OR task LIKE '%draft%'
UNION ALL
SELECT 'Correspondence', COUNT(*) FROM task_statements
WHERE task LIKE '%correspond%' OR task LIKE '%email%' OR task LIKE '%letter%'
UNION ALL
SELECT 'Reports/Presentations', COUNT(*) FROM task_statements
WHERE task LIKE '%report%' OR task LIKE '%present%'
UNION ALL
SELECT 'Proposals/Negotiation', COUNT(*) FROM task_statements
WHERE task LIKE '%propos%' OR task LIKE '%negotiat%'
UNION ALL
SELECT 'Policy/Procedure', COUNT(*) FROM task_statements
WHERE task LIKE '%polic%' OR task LIKE '%procedure%'
UNION ALL
SELECT 'Customer Communication', COUNT(*) FROM task_statements
WHERE task LIKE '%customer%' OR task LIKE '%client%'
UNION ALL
SELECT 'Training/Instruction', COUNT(*) FROM task_statements
WHERE task LIKE '%train%' OR task LIKE '%instruct%'
UNION ALL
SELECT 'Internal Coordination', COUNT(*) FROM task_statements
WHERE task LIKE '%confer%' OR task LIKE '%coordinate%'
UNION ALL
SELECT 'Contracts/Legal', COUNT(*) FROM task_statements
WHERE task LIKE '%contract%' OR task LIKE '%agreement%'
UNION ALL
SELECT 'Feedback/Evaluation', COUNT(*) FROM task_statements
WHERE task LIKE '%evaluat%' AND task LIKE '%report%';
```

---

## NOTES FOR IMPLEMENTATION

1. **Task Type**: `task_type` can be 'Core', 'Supplemental', or NULL. Core tasks are more universally performed.

2. **Scale Interpretation**:
   - Work Context (CX scale): 1-5, where 5 = "Every day"
   - Importance (IM scale): 1-5, where 5 = "Extremely important"
   - Level (LV scale): 0-7, measures complexity

3. **Emerging Tasks**: The `emerging_tasks` table contains 328 newer tasks that may reflect modern communication needs (e.g., email, social media).

4. **DWA Linkage**: Use `tasks_to_dwas` to link specific tasks to broader Detailed Work Activities for categorization.
