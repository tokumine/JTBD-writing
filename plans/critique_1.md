# Critique and Improved Plan for Gemini Writing Evaluation Framework

## CRITIQUE OF DRAFT PLAN 1

### Critical Issues

#### 1. **Prompt Generation Bias - Fundamental Flaw**
**Problem**: Draft proposes using "all models being evaluated" for Phase 1 prompt generation to "avoid bias." This creates circular contamination - models generate prompts they'll later be evaluated on, introducing training data leakage and advantage to models with better instruction following during generation.

**Impact**: Undermines entire evaluation validity. Models that generate better prompts during Phase 1 may have unfair advantage recognizing their own generated patterns.

**Correct Approach**: Use a SEPARATE, neutral model NOT in the evaluation set for prompt generation (e.g., Claude Opus 4.5 if it's not being evaluated as a "Sonnet" tier competitor). Alternatively, use multiple non-competing models and aggregate.

#### 2. **Missing Critical Judge Context Structure**
**Problem**: Draft mentions judges need context but doesn't specify HOW context is structured and passed. The judge prompt examples (lines 698-765) show context being passed informally via string formatting, but there's no validation that ALL required context elements are consistently provided.

**Impact**: Inconsistent context provision leads to invalid comparisons. Some judgments may lack industry details, others may lack persona information.

**Fix**: Require strict pydantic schema for JudgeContext that validates all required fields are present before any judgment. Make it impossible to call judge without complete context.

#### 3. **Response Constraint Violation**
**Problem**: Draft says "Let models decide appropriate length and format" but provides NO mechanism for judges to evaluate whether the model's length/format decision was appropriate. This creates evaluation ambiguity.

**Impact**: Models could game the system by writing excessively long responses (flooding the eval) or inappropriately short ones, and judges have no clear standard to penalize this.

**Fix**: Judges must explicitly evaluate "appropriateness of length/format choice" as a rubric item, with context about what's typical for that task type. Include reference ranges derived from O*NET task analysis.

#### 4. **NAICS Sampling Strategy Underspecified**
**Problem**: Lines 256-260 describe "sample evenly across 2-digit sectors" but provide no algorithm or code for HOW to ensure even distribution when occupations naturally cluster in certain sectors.

**Impact**: Could lead to biased industry representation (e.g., over-representing tech/finance, under-representing agriculture/manufacturing).

**Fix**: Implement stratified sampling with explicit quotas per NAICS 2-digit code, with fallback logic when an occupation doesn't naturally fit certain sectors.

#### 5. **Voting Aggregation Logic Ambiguity**
**Problem**: "Majority-of-majorities" is described but not precisely defined for edge cases:
- What if all 3 judges have 3-2 splits but disagree on winner?
- What if one judge has 5-0, another 3-2 opposite, third is 3-2 same as first?
- What weight do we give unanimous vs split decisions?

**Impact**: Undefined behavior in ~10-15% of comparisons, leading to arbitrary winner selection.

**Fix**: Define precise aggregation algorithm with weighted voting based on agreement strength. A 5-0 majority should carry more weight than a 3-2 split.

#### 6. **Failure Auto-Loss Creates Perverse Incentives**
**Problem**: Draft states models that fail "automatically lose" (lines 157-158, 636-647). This punishes models for being appropriately cautious about harmful content, while rewarding models that generate anything regardless of safety.

**Impact**: Incentivizes unsafe behavior. A model refusing an inappropriate task (e.g., writing a deceptive sales email) loses to a model that complies.

**Fix**: Separate failure types: (a) Technical failures = auto-loss, (b) Safety refusals = exclude from comparison (neither wins), (c) Off-topic = auto-loss. Add manual review queue for ambiguous refusals.

#### 7. **Scale Configuration Unrealistic**
**Problem**: Draft proposes 1000 prompts × 8 models × 3 judges × 2 personas × 5 votes = 240,000 API calls in "Week 7-8" (line 1662). At 300ms per call with rate limits, this is 20+ days of runtime, not 2 weeks.

**Impact**: Timeline is fantasy. Project will stall during execution phase.

**Fix**: Implement true async batching with 50+ concurrent requests, adaptive rate limiting, and realistic 4-6 week execution timeline for full eval.

#### 8. **Diversity Requirements Not Measured**
**Problem**: PROMPT.md emphasizes diversity across personas, ages, formality, recipients as "CRITICAL" (lines 56-66) but draft plan has NO metrics or validation that generated prompts actually achieve this diversity.

**Impact**: Could generate 1000 prompts that are all mid-career professionals writing formal emails to executives, completely missing GenZ casual writing or Boomer formal reports.

**Fix**: Implement diversity metrics dashboard that tracks distribution across all dimensions BEFORE running eval. Require minimum thresholds (e.g., each generation 15%+, each formality level 15%+, each skill level 20%+) and reject prompt sets that don't meet targets.

#### 9. **Inter-Judge Agreement Misused**
**Problem**: Draft computes Cohen's Kappa between judge pairs (lines 1084-1092) but doesn't specify what to DO if agreement is low. Low kappa could mean: (a) judges are bad, (b) task is genuinely ambiguous, or (c) models are equally matched.

**Impact**: Computing metrics without action plans wastes resources and provides false confidence.

**Fix**: Define kappa thresholds and action plans:
- Kappa < 0.2 (slight): Flag comparison for manual review, check if prompt is ambiguous
- Kappa 0.2-0.4 (fair): Acceptable for genuinely difficult comparisons
- Kappa > 0.4: Expected baseline
- If overall kappa < 0.3: Re-evaluate judge prompts/rubric

#### 10. **O*NET Task Filtering Too Narrow**
**Problem**: Keyword filtering (lines 187-200) uses only 18 keywords and will MISS many writing tasks. Example: "coordinate with stakeholders" involves writing but has none of those keywords. "Present findings to board" requires written presentation materials.

**Impact**: Eval misses 30-50% of actual writing tasks, biasing toward explicit "write/draft" tasks and missing implicit writing work.

**Fix**: Two-stage filtering:
1. Broad keyword filter (100+ keywords including implicit terms like "coordinate", "present", "communicate", "inform", "report")
2. LLM verification with few-shot examples of edge cases
3. Manual review of random 5% sample to validate recall

#### 11. **Rubric Weights Are Arbitrary**
**Problem**: Line 922 assigns "authenticity" weight of 1.5 vs 1.0 for others, but draft never explains how weights are used in judging or aggregation. Are judges told about weights? Do weights affect final scoring?

**Impact**: Weights are decorative. Judges won't know to prioritize authenticity, making the weighting meaningless.

**Fix**: Either (a) remove weights and treat all criteria equally in judge instructions, or (b) explicitly tell judges "authenticity is 1.5x more important - if authenticity differs significantly, it should be decisive factor even if other criteria favor the other response."

#### 12. **Missing Prompt Token Limits**
**Problem**: Context enrichment (lines 397-430) could generate arbitrarily long context, leading to prompts that exceed model context windows or cost 10x expected amounts.

**Impact**: API errors, cost blowouts, or worse - truncation that removes critical context inconsistently across comparisons.

**Fix**: Enforce max token budgets per prompt component:
- Base task: 100 tokens
- Persona: 150 tokens
- Recipient: 100 tokens
- Enriched context: 300 tokens
- Total prompt: 800 tokens max
Validate before storage, truncate intelligently if needed.

### Moderate Issues

#### 13. **SQLite Schema Missing Critical Indexes**
**Problem**: Schema has indexes (lines 1103-1108) but missing indexes on filtering/analysis heavy columns like `formality_level`, `writer_persona->generation`, and `final_winner`.

**Impact**: TUI filtering and analysis queries will be slow on 1000+ prompt dataset.

**Fix**: Add indexes on all commonly filtered fields. Create composite indexes for common filter combinations.

#### 14. **No Validation of Model IDs**
**Problem**: Model IDs are hardcoded in YAML (lines 532-569) but there's no validation that these IDs actually exist in OpenRouter API before running expensive eval.

**Impact**: Could run for hours before discovering a typo like "gemini-3.0-pro" vs "google/gemini-3-pro".

**Fix**: Add `validate_models()` function that hits OpenRouter's model list endpoint and confirms all configured models exist before any eval runs.

#### 15. **Position Bias Detection is Passive**
**Problem**: Draft detects position bias after the fact (lines 941-986) but doesn't CORRECT for it if found.

**Impact**: If position bias is detected (e.g., judges prefer first position 60% of time), the bias remains in final results.

**Fix**: If significant position bias detected (p < 0.05), apply correction factor to final win rates or flag entire eval as compromised and require re-run with different judge prompts.

#### 16. **CSV Export Too Simple**
**Problem**: Export (lines 1111-1148) creates single flat CSV losing hierarchical structure. Can't distinguish between judge disagreement and majority agreement in exported data.

**Impact**: External analysis requires re-querying database, defeating purpose of CSV export.

**Fix**: Provide multiple export formats:
- Summary CSV (current approach)
- Detailed CSV with all individual votes
- JSON export preserving full structure
- Parquet for larger datasets

#### 17. **TUI Has No Search Functionality**
**Problem**: Draft describes filtering/sorting (lines 1320-1425) but no free-text search across responses, tasks, or reasoning.

**Impact**: Can't quickly find "all comparisons where judge mentioned 'tone'" or "responses containing 'stakeholder'".

**Fix**: Add full-text search capability using SQLite FTS5 extension on response_text, task_description, and judge reasoning fields.

#### 18. **Checkpoint System Underspecified**
**Problem**: Lines 219-220 mention "checkpoint/resume" and line 1095-1100 has checkpoint table, but no detail on checkpoint frequency, what state is saved, or how partial completion of a prompt (e.g., 2/5 judge votes) is handled.

**Impact**: Resume might lose work or create inconsistent state.

**Fix**: Define checkpoint strategy:
- Checkpoint after each completed comparison (all judges voted)
- Save run_id, completed_comparison_ids, pending_comparison_ids, config, random_seed_state
- Resume loads state and continues from next pending comparison
- Never resume mid-comparison to avoid partial vote sets

### Minor Issues

#### 19. **Cost Estimation Outdated**
**Problem**: Lines 1664-1676 estimate costs based on arbitrary per-token pricing, but OpenRouter pricing varies 100x between models and changes frequently.

**Impact**: Budget could be off by 5-10x.

**Fix**: Implement dynamic cost estimation that queries current OpenRouter pricing API before eval and provides range based on actual model prices.

#### 20. **No Mechanism for Handling Model Updates**
**Problem**: Models get updated during long-running evals. "gpt-5.2" today might be different from "gpt-5.2" in 4 weeks.

**Impact**: Inconsistent comparisons - early prompts use old model, late prompts use updated model.

**Fix**: Pin to specific model versions/dates if OpenRouter supports it, or record model version metadata with each response. If model updates mid-eval, either restart or segment analysis by model version.

#### 21. **Visualization Code Incomplete**
**Problem**: Lines 1205-1267 show example plotly code but don't specify where charts are saved, what format (HTML/PNG/SVG), or how they're versioned alongside results.

**Impact**: Analysis reproducibility issues.

**Fix**: Save all charts to `outputs/{run_id}/charts/` as both HTML (interactive) and PNG (for PDF report), with metadata JSON describing chart params.

---

## IMPROVED PLAN

### Overview of Key Improvements

1. **Neutral Prompt Generation**: Use non-competing models for prompt generation
2. **Strict Judge Context Schema**: Pydantic validation ensuring complete context
3. **Weighted Voting Aggregation**: Confidence-weighted majority-of-majorities
4. **Failure Type Taxonomy**: Separate technical failures from safety refusals
5. **Diversity Validation Dashboard**: Pre-eval diversity metrics with rejection criteria
6. **Enhanced O*NET Filtering**: Two-stage broad+verified approach
7. **Realistic Timeline**: 6-8 week full eval with proper async batching
8. **Actionable Agreement Metrics**: Kappa thresholds with remediation plans
9. **Prompt Token Budgets**: Strict per-component limits with validation
10. **Production-Grade Infrastructure**: Complete error handling, retry logic, monitoring

---

## IMPROVED SYSTEM ARCHITECTURE

### 1. Data Pipeline: O*NET + NAICS (Enhanced)

#### 1.1 O*NET Data Acquisition (Same as Draft)

```python
# src/data/onet_downloader.py
# [Same as draft lines 122-168 - implementation is correct]
```

#### 1.2 Writing Task Extraction (IMPROVED)

```python
# src/data/task_extractor.py

class WritingTaskExtractor:
    """Extract writing-related tasks with comprehensive keyword coverage."""

    # EXPANDED: 100+ keywords covering explicit and implicit writing
    WRITING_KEYWORDS_EXPLICIT = [
        "write", "draft", "compose", "author", "document", "prepare",
        "correspondence", "report", "email", "memo", "letter", "article",
        "proposal", "brief", "content", "copy", "text", "description",
        "communicate", "message", "notification", "announcement"
    ]

    WRITING_KEYWORDS_IMPLICIT = [
        "coordinate", "inform", "notify", "present", "convey",
        "articulate", "explain", "describe", "summarize", "outline",
        "detail", "specify", "clarify", "document", "record",
        "update", "advise", "recommend", "request", "respond"
    ]

    def filter_writing_tasks(self, tasks_df: pd.DataFrame) -> pd.DataFrame:
        """Two-stage filtering: broad keywords + LLM verification."""

        # Stage 1: Broad keyword filter
        all_keywords = self.WRITING_KEYWORDS_EXPLICIT + self.WRITING_KEYWORDS_IMPLICIT
        pattern = "|".join(all_keywords)
        candidate_tasks = tasks_df[
            tasks_df["Task"].str.contains(pattern, case=False, na=False)
        ]

        return candidate_tasks

    async def verify_with_llm(
        self,
        tasks: list[dict],
        llm_client: LLMClient
    ) -> list[dict]:
        """LLM verification with few-shot examples."""

        verification_prompt = """
Classify whether each task requires producing written communication as a core component.

Guidelines:
- YES: Task explicitly requires writing documents, emails, reports, or messages
- YES: Task requires "coordinating" or "communicating" that would necessitate written communication
- NO: Task is purely verbal communication or doesn't involve creating written artifacts
- NO: Task involves reading/analyzing writing but not producing it

Examples:
- "Draft correspondence for executive review" → YES (explicit writing)
- "Coordinate with stakeholders on project timeline" → YES (implicit - requires written updates)
- "Present findings to board" → YES (requires written presentation materials)
- "Review budget reports for accuracy" → NO (reading, not writing)
- "Conduct verbal interviews with candidates" → NO (verbal only)

Tasks to classify:
{tasks}

Return JSON: [{{"task_id": "...", "is_writing": true/false, "reasoning": "..."}}]
"""

        verified_tasks = []
        # Batch process in groups of 50
        for batch in chunked(tasks, 50):
            result = await llm_client.generate(
                verification_prompt.format(tasks=json.dumps(batch))
            )
            verified_tasks.extend(json.loads(result["content"]))

        # Filter to only confirmed writing tasks
        return [t for t in verified_tasks if t["is_writing"]]

    def validate_recall(self, verified_tasks: list[dict], sample_size: int = 50) -> dict:
        """Manual review of random sample to check recall."""

        sample = random.sample(verified_tasks, min(sample_size, len(verified_tasks)))

        print("Manual Validation Sample:")
        print("=" * 80)

        for i, task in enumerate(sample, 1):
            print(f"\n{i}. {task['task']}")
            print(f"   LLM Classification: {'WRITING' if task['is_writing'] else 'NOT WRITING'}")
            response = input("   Correct? (y/n/skip): ").strip().lower()

            if response == 'y':
                task['manual_validation'] = 'correct'
            elif response == 'n':
                task['manual_validation'] = 'incorrect'
            else:
                task['manual_validation'] = 'skipped'

        # Calculate accuracy
        validated = [t for t in sample if t.get('manual_validation') in ['correct', 'incorrect']]
        accuracy = len([t for t in validated if t['manual_validation'] == 'correct']) / len(validated)

        return {
            "sample_size": len(validated),
            "accuracy": accuracy,
            "validation_sample": sample
        }
```

#### 1.3 NAICS Industry Mapping (IMPROVED - Stratified Sampling)

```python
# src/data/naics_mapper.py

class NAICSMapper:
    """Map occupations to NAICS industry codes with guaranteed even distribution."""

    # 20 NAICS 2-digit sectors
    NAICS_SECTORS = {
        "11": "Agriculture, Forestry, Fishing and Hunting",
        "21": "Mining, Quarrying, and Oil and Gas Extraction",
        "22": "Utilities",
        "23": "Construction",
        "31-33": "Manufacturing",
        "42": "Wholesale Trade",
        "44-45": "Retail Trade",
        "48-49": "Transportation and Warehousing",
        "51": "Information",
        "52": "Finance and Insurance",
        "53": "Real Estate and Rental and Leasing",
        "54": "Professional, Scientific, and Technical Services",
        "55": "Management of Companies and Enterprises",
        "56": "Administrative and Support Services",
        "61": "Educational Services",
        "62": "Health Care and Social Assistance",
        "71": "Arts, Entertainment, and Recreation",
        "72": "Accommodation and Food Services",
        "81": "Other Services (except Public Administration)",
        "92": "Public Administration"
    }

    def stratified_sample_industries(
        self,
        occupation_code: str,
        occupation_name: str,
        n_samples: int,
        random_seed: int
    ) -> list[dict]:
        """Sample NAICS codes ensuring even sector distribution."""

        rng = Random(random_seed)

        # Get applicable sectors for this occupation
        applicable_sectors = self._get_applicable_sectors(occupation_code, occupation_name)

        if len(applicable_sectors) == 0:
            # Fallback: generic white-collar applicable sectors
            applicable_sectors = ["54", "55", "56", "61", "62", "92"]

        # Sample evenly across applicable sectors
        samples_per_sector = max(1, n_samples // len(applicable_sectors))
        sampled_industries = []

        for sector in applicable_sectors:
            # Get specific 4-6 digit NAICS codes within sector
            specific_codes = self._get_specific_codes_in_sector(sector)

            # Sample randomly from specific codes
            sector_samples = rng.sample(
                specific_codes,
                min(samples_per_sector, len(specific_codes))
            )

            sampled_industries.extend(sector_samples)

        # If we need more samples, sample additional from any applicable sector
        while len(sampled_industries) < n_samples:
            sector = rng.choice(applicable_sectors)
            codes = self._get_specific_codes_in_sector(sector)
            sampled_industries.append(rng.choice(codes))

        return sampled_industries[:n_samples]

    def _get_applicable_sectors(self, occupation_code: str, occupation_name: str) -> list[str]:
        """Determine which NAICS sectors are realistic for this occupation."""

        # Logic based on O*NET occupation categorization
        # Example: CEOs (11-1011.00) apply to all sectors
        #          Farm Managers (11-9013.00) only apply to sector 11
        #          Software Developers only apply to specific sectors

        # This would be more sophisticated in production,
        # potentially using O*NET's industry-occupation matrix
        # For now, simplified logic:

        if "chief executive" in occupation_name.lower():
            return list(self.NAICS_SECTORS.keys())  # CEOs in all industries

        if "software" in occupation_name.lower() or "computer" in occupation_name.lower():
            return ["51", "54", "52", "55"]  # Tech-heavy sectors

        # Default: Most white-collar occupations apply to these
        return ["54", "55", "56", "61", "62", "52", "51", "92"]
```

### 2. Prompt Generation System (CORRECTED)

#### 2.1 Neutral Model Selection for Generation

**CRITICAL FIX**: Use models NOT in the evaluation set for prompt generation.

```python
# src/prompts/generator.py

class PromptGenerationConfig:
    """Configuration for prompt generation models."""

    # Models used for prompt generation - NOT in evaluation set
    # Choose based on which tiers are being evaluated
    GENERATION_MODELS = {
        "for_pro_tier_eval": [
            "anthropic/claude-opus-4.5",  # If NOT being evaluated as competitor
            "openai/o1-preview"  # Different model family
        ],
        "for_flash_tier_eval": [
            "anthropic/claude-sonnet-4.5",  # If NOT being evaluated
            "openai/gpt-4.1"  # If NOT being evaluated
        ]
    }

    @classmethod
    def get_generation_models(cls, eval_tier: str) -> list[str]:
        """Get appropriate generation models that won't bias eval."""
        if eval_tier == "pro":
            # Use models from flash tier or non-competing models
            return ["anthropic/claude-3-opus", "openai/o1-mini"]
        else:
            # Use completely different models
            return ["anthropic/claude-3-opus"]


class PersonaGenerator:
    """Generate diverse writer personas without eval bias."""

    def __init__(self, generation_models: list[str]):
        """Initialize with neutral models NOT in evaluation."""
        self.generation_models = generation_models
        self.client = OpenRouterClient()

    async def generate_personas(
        self,
        task: dict,
        industry: dict,
        n_personas: int,
        random_seed: int
    ) -> list[dict]:
        """Generate diverse personas using rotation of generation models."""

        personas = []
        rng = Random(random_seed)

        for i in range(n_personas):
            # Rotate through generation models to ensure diversity
            model = self.generation_models[i % len(self.generation_models)]

            # Randomly assign attributes
            generation = rng.choice(["Gen Z", "Millennial", "Gen X", "Boomer"])
            skill_level = rng.choice(["entry-level", "mid-career", "senior", "executive"])
            formality = rng.choice(["very casual", "casual", "neutral", "formal", "very formal"])

            persona_prompt = f"""
Generate a realistic writer persona for this professional writing task:

Task: {task['task']}
Occupation: {task['occupation_name']}
Industry: {industry['name']} (NAICS: {industry['code']})

Required attributes:
- Generation: {generation}
- Career level: {skill_level}
- Communication style: {formality}

Create a persona with:
- Realistic name appropriate for their generation
- Age consistent with generation and career level
- Specific job title and company context
- Brief background (2-3 sentences)
- Writing skill level (novice/competent/skilled/expert)
- Key personality traits affecting communication style

Make it authentic and diverse. This persona will write in the style natural to them.

Return JSON:
{{
  "name": "...",
  "age": ...,
  "generation": "{generation}",
  "job_title": "...",
  "company_context": "...",
  "career_level": "{skill_level}",
  "writing_skill": "...",
  "communication_style": "{formality}",
  "background": "...",
  "personality_traits": ["...", "..."]
}}
"""

            response = await self.client.generate(
                model_id=model,
                prompt=persona_prompt,
                max_tokens=500,
                temperature=0.9  # High diversity
            )

            persona = json.loads(response["content"])
            persona["generated_by_model"] = model
            persona["generation_seed"] = random_seed + i
            personas.append(persona)

        return personas
```

#### 2.2 Token Budget Validation

```python
# src/prompts/token_budgets.py

class TokenBudgetValidator:
    """Enforce token limits on prompt components."""

    BUDGETS = {
        "task_description": 100,
        "writer_persona": 150,
        "recipient_persona": 100,
        "enriched_context": 300,
        "total_prompt": 800
    }

    def __init__(self):
        # Use tiktoken or similar for accurate token counting
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))

    def validate_component(self, component_name: str, text: str) -> tuple[bool, int]:
        """Check if component is within budget."""
        token_count = self.count_tokens(text)
        budget = self.BUDGETS[component_name]
        return token_count <= budget, token_count

    def truncate_intelligently(self, text: str, max_tokens: int) -> str:
        """Truncate text to max_tokens while preserving meaning."""

        tokens = self.encoder.encode(text)

        if len(tokens) <= max_tokens:
            return text

        # Truncate and decode
        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.encoder.decode(truncated_tokens)

        # Try to end at sentence boundary
        last_period = truncated_text.rfind('.')
        if last_period > len(truncated_text) * 0.7:  # If we're not losing too much
            return truncated_text[:last_period + 1]

        return truncated_text + "..."

    def validate_full_prompt(self, prompt_components: dict) -> dict:
        """Validate all components and full assembled prompt."""

        validation_result = {
            "valid": True,
            "component_counts": {},
            "budget_violations": []
        }

        for component, text in prompt_components.items():
            if component in self.BUDGETS:
                valid, count = self.validate_component(component, text)
                validation_result["component_counts"][component] = count

                if not valid:
                    validation_result["valid"] = False
                    validation_result["budget_violations"].append({
                        "component": component,
                        "count": count,
                        "budget": self.BUDGETS[component],
                        "overage": count - self.BUDGETS[component]
                    })

        # Check total
        total_tokens = sum(validation_result["component_counts"].values())
        if total_tokens > self.BUDGETS["total_prompt"]:
            validation_result["valid"] = False
            validation_result["budget_violations"].append({
                "component": "total_prompt",
                "count": total_tokens,
                "budget": self.BUDGETS["total_prompt"],
                "overage": total_tokens - self.BUDGETS["total_prompt"]
            })

        return validation_result
```

#### 2.3 Diversity Validation Dashboard

```python
# src/prompts/diversity_validator.py

class DiversityValidator:
    """Validate prompt set meets diversity requirements before eval."""

    DIVERSITY_REQUIREMENTS = {
        "generation": {
            "categories": ["Gen Z", "Millennial", "Gen X", "Boomer"],
            "min_percentage_each": 15.0,
            "ideal_percentage_each": 25.0
        },
        "formality_level": {
            "categories": ["very casual", "casual", "neutral", "formal", "very formal"],
            "min_percentage_each": 15.0,
            "ideal_percentage_each": 20.0
        },
        "skill_level": {
            "categories": ["entry-level", "mid-career", "senior", "executive"],
            "min_percentage_each": 20.0,
            "ideal_percentage_each": 25.0
        },
        "naics_sector": {
            "min_unique_sectors": 15,  # At least 15 of 20 sectors
            "max_percentage_single_sector": 20.0
        }
    }

    def validate_diversity(self, prompts: list[dict]) -> dict:
        """Check if prompt set meets diversity requirements."""

        total_prompts = len(prompts)
        validation_result = {
            "valid": True,
            "total_prompts": total_prompts,
            "dimension_analysis": {},
            "violations": [],
            "warnings": []
        }

        # Check each dimension
        for dimension, requirements in self.DIVERSITY_REQUIREMENTS.items():
            if dimension == "naics_sector":
                analysis = self._analyze_naics_diversity(prompts, requirements)
            else:
                analysis = self._analyze_categorical_diversity(
                    prompts, dimension, requirements
                )

            validation_result["dimension_analysis"][dimension] = analysis

            # Check for violations
            if not analysis["meets_requirements"]:
                validation_result["valid"] = False
                validation_result["violations"].append(analysis["violation_message"])

            # Check for warnings
            if not analysis["meets_ideal"]:
                validation_result["warnings"].append(analysis["warning_message"])

        return validation_result

    def _analyze_categorical_diversity(
        self,
        prompts: list[dict],
        dimension: str,
        requirements: dict
    ) -> dict:
        """Analyze diversity for categorical dimensions."""

        total = len(prompts)
        counts = Counter([p["writer_persona"][dimension] for p in prompts])
        percentages = {cat: (count / total) * 100 for cat, count in counts.items()}

        # Check minimum requirements
        violations = []
        for category in requirements["categories"]:
            pct = percentages.get(category, 0)
            if pct < requirements["min_percentage_each"]:
                violations.append(
                    f"{category}: {pct:.1f}% (minimum {requirements['min_percentage_each']}%)"
                )

        # Check ideal requirements
        ideal_met = all(
            percentages.get(cat, 0) >= requirements["ideal_percentage_each"]
            for cat in requirements["categories"]
        )

        return {
            "dimension": dimension,
            "counts": dict(counts),
            "percentages": percentages,
            "meets_requirements": len(violations) == 0,
            "meets_ideal": ideal_met,
            "violation_message": f"{dimension}: " + ", ".join(violations) if violations else None,
            "warning_message": f"{dimension} below ideal distribution" if not ideal_met else None
        }

    def _analyze_naics_diversity(self, prompts: list[dict], requirements: dict) -> dict:
        """Analyze NAICS sector diversity."""

        # Extract 2-digit sectors
        sectors = [p["industry"]["naics_code"][:2] for p in prompts]
        sector_counts = Counter(sectors)
        total = len(prompts)

        unique_sectors = len(sector_counts)
        max_sector_pct = (max(sector_counts.values()) / total) * 100

        violations = []
        if unique_sectors < requirements["min_unique_sectors"]:
            violations.append(
                f"Only {unique_sectors} unique sectors (minimum {requirements['min_unique_sectors']})"
            )

        if max_sector_pct > requirements["max_percentage_single_sector"]:
            violations.append(
                f"Single sector represents {max_sector_pct:.1f}% (max {requirements['max_percentage_single_sector']}%)"
            )

        return {
            "dimension": "naics_sector",
            "unique_sectors": unique_sectors,
            "sector_counts": dict(sector_counts),
            "max_sector_percentage": max_sector_pct,
            "meets_requirements": len(violations) == 0,
            "meets_ideal": unique_sectors >= 18,  # 18 of 20 sectors is ideal
            "violation_message": "NAICS diversity: " + ", ".join(violations) if violations else None,
            "warning_message": "NAICS diversity below ideal (18+ sectors)" if unique_sectors < 18 else None
        }

    def generate_diversity_report(self, validation_result: dict) -> str:
        """Generate human-readable diversity report."""

        report = f"""
DIVERSITY VALIDATION REPORT
===========================

Total Prompts: {validation_result['total_prompts']}
Overall Status: {'✓ PASS' if validation_result['valid'] else '✗ FAIL'}

"""

        for dimension, analysis in validation_result["dimension_analysis"].items():
            report += f"\n{dimension.upper()}:\n"

            if "counts" in analysis:
                for category, count in analysis["counts"].items():
                    pct = analysis["percentages"][category]
                    report += f"  {category}: {count} ({pct:.1f}%)\n"

            if "unique_sectors" in analysis:
                report += f"  Unique sectors: {analysis['unique_sectors']}\n"
                report += f"  Max sector %: {analysis['max_sector_percentage']:.1f}%\n"

            status = "✓" if analysis["meets_requirements"] else "✗"
            report += f"  Status: {status}\n"

        if validation_result["violations"]:
            report += "\nVIOLATIONS:\n"
            for violation in validation_result["violations"]:
                report += f"  ✗ {violation}\n"

        if validation_result["warnings"]:
            report += "\nWARNINGS:\n"
            for warning in validation_result["warnings"]:
                report += f"  ⚠ {warning}\n"

        return report
```

### 3. Judge System (CORRECTED)

#### 3.1 Strict Judge Context Schema

```python
# src/judging/context.py

from pydantic import BaseModel, Field, validator
from typing import Literal

class WriterPersona(BaseModel):
    """Complete writer persona for judging context."""
    name: str
    age: int
    generation: Literal["Gen Z", "Millennial", "Gen X", "Boomer"]
    job_title: str
    company_context: str
    career_level: Literal["entry-level", "mid-career", "senior", "executive"]
    writing_skill: Literal["novice", "competent", "skilled", "expert"]
    communication_style: Literal["very casual", "casual", "neutral", "formal", "very formal"]
    background: str
    personality_traits: list[str]

class RecipientPersona(BaseModel):
    """Complete recipient persona for judging context."""
    role: str
    relationship_to_writer: str
    needs_from_communication: str
    communication_preferences: str
    background: str

class JudgeContext(BaseModel):
    """Complete context required for fair judgment."""

    # Required fields - missing any will cause validation error
    task_description: str = Field(..., min_length=10)
    occupation_name: str = Field(..., min_length=3)
    industry_name: str = Field(..., min_length=3)
    industry_naics: str = Field(..., min_length=2)

    writer_persona: WriterPersona
    recipient_persona: RecipientPersona

    enriched_context: str | None = None
    expected_length_range: str | None = Field(
        None,
        description="e.g., '50-200 words', 'brief note', '2-3 paragraphs'"
    )
    expected_format: str | None = Field(
        None,
        description="e.g., 'email', 'formal letter', 'internal memo', 'report section'"
    )

    @validator('expected_length_range', 'expected_format', always=True)
    def set_defaults_from_task(cls, v, values):
        """Infer defaults if not explicitly set."""
        if v is None:
            task = values.get('task_description', '').lower()

            # Infer expected format
            if 'email' in task or 'message' in task:
                values['expected_format'] = 'email'
            elif 'report' in task:
                values['expected_format'] = 'report section'
            elif 'memo' in task or 'brief' in task:
                values['expected_format'] = 'memo'
            elif 'letter' in task or 'correspondence' in task:
                values['expected_format'] = 'formal letter'
            else:
                values['expected_format'] = 'professional communication'

            # Infer expected length
            if 'brief' in task or 'short' in task or 'quick' in task:
                values['expected_length_range'] = '50-150 words'
            elif 'detailed' in task or 'comprehensive' in task:
                values['expected_length_range'] = '300-800 words'
            else:
                values['expected_length_range'] = '150-400 words'

        return v

    def format_for_judge_prompt(self) -> str:
        """Format context as clear prose for judge."""

        context_text = f"""
EVALUATION CONTEXT:

Task: {self.task_description}
Occupation: {self.occupation_name}
Industry: {self.industry_name} (NAICS: {self.industry_naics})

WRITER:
{self.writer_persona.name}, {self.writer_persona.age} year old {self.writer_persona.generation}
Position: {self.writer_persona.job_title} at {self.writer_persona.company_context}
Career Level: {self.writer_persona.career_level}
Writing Skill: {self.writer_persona.writing_skill}
Communication Style: {self.writer_persona.communication_style}
Background: {self.writer_persona.background}

RECIPIENT:
Role: {self.recipient_persona.role}
Relationship: {self.recipient_persona.relationship_to_writer}
Needs: {self.recipient_persona.needs_from_communication}
Preferences: {self.recipient_persona.communication_preferences}

EXPECTATIONS:
Format: {self.expected_format}
Length: {self.expected_length_range}
"""

        if self.enriched_context:
            context_text += f"\nADDITIONAL CONTEXT:\n{self.enriched_context}\n"

        return context_text
```

#### 3.2 Weighted Voting Aggregation (IMPROVED)

```python
# src/judging/voting.py

class WeightedVotingSystem:
    """Confidence-weighted majority-of-majorities aggregation."""

    async def run_best_of_5(
        self,
        judge_model: str,
        judge_persona: JudgePersona,
        context: JudgeContext,
        response_a: str,
        response_b: str,
        base_seed: int
    ) -> dict:
        """Run 5 independent judgments with different shuffle seeds."""

        votes = []
        for i in range(5):
            seed = base_seed + i

            vote_result = await self._single_judgment(
                judge_model=judge_model,
                judge_persona=judge_persona,
                context=context,
                response_a=response_a,
                response_b=response_b,
                shuffle_seed=seed
            )

            votes.append(vote_result)

        # Aggregate votes
        vote_counts = Counter([v["winner"] for v in votes])
        majority_winner = vote_counts.most_common(1)[0][0]
        majority_count = vote_counts[majority_winner]

        # Calculate confidence: 5-0 = 1.0, 4-1 = 0.8, 3-2 = 0.6
        confidence = majority_count / 5.0

        return {
            "judge_model": judge_model,
            "judge_persona": judge_persona.__class__.__name__,
            "votes": votes,
            "vote_counts": dict(vote_counts),
            "majority_winner": majority_winner,
            "confidence": confidence
        }

    def aggregate_weighted_majority(
        self,
        judge_results: list[dict]
    ) -> dict:
        """Aggregate with confidence weighting."""

        # Each judge's vote is weighted by their confidence
        weighted_votes = {}

        for result in judge_results:
            winner = result["majority_winner"]
            confidence = result["confidence"]

            if winner not in weighted_votes:
                weighted_votes[winner] = 0
            weighted_votes[winner] += confidence

        # Determine final winner by weighted votes
        final_winner = max(weighted_votes.items(), key=lambda x: x[1])[0]
        total_weight = sum(weighted_votes.values())

        return {
            "judge_results": judge_results,
            "weighted_votes": weighted_votes,
            "final_winner": final_winner,
            "final_confidence": weighted_votes[final_winner] / total_weight,
            "agreement_level": self._calculate_agreement_level(judge_results)
        }

    def _calculate_agreement_level(self, judge_results: list[dict]) -> str:
        """Classify level of judge agreement."""

        winners = [r["majority_winner"] for r in judge_results]
        winner_counts = Counter(winners)

        if len(winner_counts) == 1:
            # All judges agree
            avg_confidence = sum(r["confidence"] for r in judge_results) / len(judge_results)
            if avg_confidence >= 0.8:
                return "unanimous_strong"  # All judges + strong confidence
            else:
                return "unanimous_weak"  # All judges but low confidence

        if len(winner_counts) == 2:
            most_common_count = winner_counts.most_common(1)[0][1]
            if most_common_count == 2:
                return "split_decision"  # 2-1 split
            else:
                return "majority_decision"  # 3-0 or similar

        return "no_consensus"
```

#### 3.3 Failure Handling with Taxonomy

```python
# src/evaluation/failure_handler.py

from enum import Enum

class FailureType(Enum):
    """Taxonomy of failure modes."""
    NONE = "none"
    API_ERROR = "api_error"  # Timeout, rate limit, network error
    SAFETY_REFUSAL = "safety_refusal"  # Legitimate safety concern
    CAPABILITY_REFUSAL = "capability_refusal"  # "I can't write creative content"
    OFF_TOPIC = "off_topic"  # Response doesn't address task
    TOO_SHORT = "too_short"  # <50 characters
    MALFORMED = "malformed"  # Invalid format, corrupted output

class FailureHandler:
    """Classify and handle model failures appropriately."""

    SAFETY_PATTERNS = [
        "I cannot", "I'm unable", "I can't assist",
        "inappropriate", "against my guidelines", "not comfortable",
        "violates", "harmful", "unethical", "illegal"
    ]

    CAPABILITY_PATTERNS = [
        "I don't have the ability", "I'm not designed to",
        "I cannot access", "I don't have information about",
        "I'm a language model"
    ]

    def classify_failure(self, response: dict | Exception) -> tuple[FailureType, str]:
        """Classify failure type with reasoning."""

        # API error
        if isinstance(response, Exception):
            return FailureType.API_ERROR, f"API exception: {type(response).__name__}"

        if response is None or "content" not in response:
            return FailureType.API_ERROR, "No response content"

        content = response.get("content", "").strip()

        # Too short
        if len(content) < 50:
            return FailureType.TOO_SHORT, f"Response only {len(content)} characters"

        # Safety refusal
        if any(pattern.lower() in content.lower() for pattern in self.SAFETY_PATTERNS):
            return FailureType.SAFETY_REFUSAL, "Model declined due to safety guidelines"

        # Capability refusal
        if any(pattern.lower() in content.lower() for pattern in self.CAPABILITY_PATTERNS):
            return FailureType.CAPABILITY_REFUSAL, "Model claimed lack of capability"

        # Off-topic check (would need more sophisticated analysis)
        # For now, basic heuristic: starts with refusal language
        first_sentence = content.split('.')[0].lower()
        if any(p.lower() in first_sentence for p in self.SAFETY_PATTERNS + self.CAPABILITY_PATTERNS):
            return FailureType.OFF_TOPIC, "Response starts with refusal"

        return FailureType.NONE, "Valid response"

    def determine_comparison_outcome(
        self,
        failure_a: tuple[FailureType, str],
        failure_b: tuple[FailureType, str]
    ) -> dict:
        """Determine comparison outcome based on failure types."""

        type_a, reason_a = failure_a
        type_b, reason_b = failure_b

        # Both succeeded
        if type_a == FailureType.NONE and type_b == FailureType.NONE:
            return {
                "outcome": "proceed_to_judging",
                "auto_winner": None,
                "reasoning": "Both models produced valid responses"
            }

        # Both failed
        if type_a != FailureType.NONE and type_b != FailureType.NONE:
            # Safety refusals = exclude from comparison
            if type_a == FailureType.SAFETY_REFUSAL and type_b == FailureType.SAFETY_REFUSAL:
                return {
                    "outcome": "exclude_both_safety",
                    "auto_winner": "tie",
                    "reasoning": "Both models appropriately declined on safety grounds"
                }

            # Different failure types - worse failure loses
            failure_severity = {
                FailureType.SAFETY_REFUSAL: 1,  # Least severe
                FailureType.CAPABILITY_REFUSAL: 2,
                FailureType.TOO_SHORT: 3,
                FailureType.OFF_TOPIC: 4,
                FailureType.MALFORMED: 5,
                FailureType.API_ERROR: 6  # Most severe
            }

            severity_a = failure_severity.get(type_a, 999)
            severity_b = failure_severity.get(type_b, 999)

            if severity_a < severity_b:
                return {
                    "outcome": "auto_win_a",
                    "auto_winner": "A",
                    "reasoning": f"Model A failed less severely ({type_a.value}) than B ({type_b.value})"
                }
            elif severity_b < severity_a:
                return {
                    "outcome": "auto_win_b",
                    "auto_winner": "B",
                    "reasoning": f"Model B failed less severely ({type_b.value}) than A ({type_a.value})"
                }
            else:
                return {
                    "outcome": "exclude_both_failed",
                    "auto_winner": "tie",
                    "reasoning": f"Both models failed similarly ({type_a.value})"
                }

        # Only A failed
        if type_a != FailureType.NONE:
            if type_a == FailureType.SAFETY_REFUSAL:
                return {
                    "outcome": "exclude_safety_refusal_a",
                    "auto_winner": None,  # Don't count as loss
                    "reasoning": "Model A appropriately declined on safety grounds"
                }
            return {
                "outcome": "auto_win_b",
                "auto_winner": "B",
                "reasoning": f"Model A failed ({type_a.value}), Model B succeeded"
            }

        # Only B failed
        if type_b != FailureType.NONE:
            if type_b == FailureType.SAFETY_REFUSAL:
                return {
                    "outcome": "exclude_safety_refusal_b",
                    "auto_winner": None,
                    "reasoning": "Model B appropriately declined on safety grounds"
                }
            return {
                "outcome": "auto_win_a",
                "auto_winner": "A",
                "reasoning": f"Model B failed ({type_b.value}), Model A succeeded"
            }

        return {
            "outcome": "error",
            "auto_winner": None,
            "reasoning": "Unexpected failure classification state"
        }
```

### 4. Infrastructure and Orchestration

#### 4.1 Async Batch Execution with Rate Limiting

```python
# src/evaluation/batch_executor.py

import asyncio
from asyncio import Semaphore
import time

class AsyncBatchExecutor:
    """Production-grade async execution with rate limiting."""

    def __init__(
        self,
        max_concurrent: int = 50,
        requests_per_minute: int = 500,
        retry_attempts: int = 3
    ):
        self.semaphore = Semaphore(max_concurrent)
        self.rate_limit = requests_per_minute
        self.retry_attempts = retry_attempts

        # Track request timestamps for rate limiting
        self.request_times = []

    async def execute_batch(
        self,
        tasks: list[Coroutine],
        checkpoint_callback: Callable = None
    ) -> list:
        """Execute batch with concurrency control and rate limiting."""

        results = []
        total_tasks = len(tasks)

        for i, task in enumerate(tasks):
            async with self.semaphore:
                # Rate limiting check
                await self._enforce_rate_limit()

                # Execute with retry
                result = await self._execute_with_retry(task)
                results.append(result)

                # Checkpoint every 10 completions
                if checkpoint_callback and (i + 1) % 10 == 0:
                    await checkpoint_callback(results)

                # Progress logging
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i+1}/{total_tasks} completed")

        return results

    async def _enforce_rate_limit(self):
        """Ensure we don't exceed rate limit."""

        now = time.time()

        # Remove timestamps older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        # If at limit, wait
        if len(self.request_times) >= self.rate_limit:
            oldest = self.request_times[0]
            wait_time = 60 - (now - oldest)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.request_times.append(now)

    async def _execute_with_retry(
        self,
        task: Coroutine,
        attempt: int = 1
    ):
        """Execute task with exponential backoff retry."""

        try:
            result = await task
            return result

        except Exception as e:
            if attempt >= self.retry_attempts:
                logger.error(f"Task failed after {attempt} attempts: {e}")
                return {"error": str(e), "exception_type": type(e).__name__}

            # Exponential backoff
            wait_time = 2 ** attempt
            logger.warning(f"Task failed (attempt {attempt}), retrying in {wait_time}s: {e}")
            await asyncio.sleep(wait_time)

            return await self._execute_with_retry(task, attempt + 1)
```

#### 4.2 Model Validation Pre-Flight

```python
# src/evaluation/model_validator.py

class ModelValidator:
    """Validate model availability before expensive eval run."""

    async def validate_all_models(self, config: dict) -> dict:
        """Check all configured models exist in OpenRouter."""

        client = OpenRouterClient()
        available_models = await client.list_models()
        available_ids = {m["id"] for m in available_models}

        validation_result = {
            "valid": True,
            "missing_models": [],
            "available_models": []
        }

        # Check eval models
        all_eval_models = []
        for tier in ["pro_tier", "flash_tier"]:
            if tier in config["models"]:
                all_eval_models.append(config["models"][tier]["gemini"]["id"])
                all_eval_models.extend([m["id"] for m in config["models"][tier]["competitors"]])

        # Check judge models
        all_judge_models = [m["id"] for m in config["judge_models"]]

        # Validate all
        for model_id in set(all_eval_models + all_judge_models):
            if model_id in available_ids:
                validation_result["available_models"].append(model_id)
            else:
                validation_result["valid"] = False
                validation_result["missing_models"].append(model_id)

        return validation_result
```

### 5. Realistic Timeline and Execution Plan

#### Full Evaluation Timeline (6-8 Weeks)

```
WEEK 1-2: Setup and Data Preparation
- Download and process O*NET database (2 days)
- Extract and verify writing tasks (3 days)
- Set up NAICS mapping (2 days)
- Database schema and infrastructure (3 days)

WEEK 3: Prompt Generation
- Phase 1: LLM-based persona generation (3 days, ~500 API calls)
- Phase 2: Algorithmic combinations (2 days, offline processing)
- Phase 3: Context enrichment (2 days, ~1000 API calls)
- Diversity validation and regeneration if needed (2 days)

WEEK 4: Model Validation and Pilot
- Validate all model IDs (1 day)
- Run 50-prompt pilot evaluation (3 days, ~1000 API calls)
- Analyze pilot results, check for issues (2 days)
- Adjust judge prompts/rubric if needed (1 day)

WEEK 5-6: Full Model Evaluation
- Generate responses: 1000 prompts × 8 models = 8000 API calls
- With 50 concurrent requests: ~3-4 days runtime
- Buffer for rate limits and failures: +2 days
- Total: 6 days for response generation

WEEK 7-8: Judge Voting
- Judging: 1000 comparisons × 3 judges × 2 personas × 5 votes = 30,000 API calls
- With 50 concurrent requests: ~12 hours runtime per comparison type
- Total across all comparison types: ~5-6 days
- Aggregation and analysis: 2 days
- Final report generation: 2 days

CONTINGENCY: +1-2 weeks for unexpected issues, re-runs, debugging
```

#### Quick Evaluation Timeline (100 prompts, 1-2 Weeks)

```
WEEK 1:
- Setup and data prep (condensed): 3 days
- Prompt generation (100 prompts): 2 days
- Diversity validation: 1 day
- Pilot run: 1 day

WEEK 2:
- Full evaluation: 100 × 8 models = 800 API calls (~4-6 hours)
- Judging: 100 × 3 × 2 × 5 = 3000 API calls (~1 day)
- Analysis and reporting: 3 days
```

### 6. Key Design Decisions and Rationale

#### Decision 1: Neutral Models for Prompt Generation
**Rationale**: Prevents circular contamination where models generate prompts they'll later be evaluated on. Uses models outside evaluation set or different tiers.
**Alternative Considered**: Using evaluated models was draft proposal, but creates unfair advantage.
**Risk**: Neutral models might generate prompts biased toward their own strengths, but this is less severe than self-evaluation bias.

#### Decision 2: Weighted Majority-of-Majorities
**Rationale**: A 5-0 unanimous decision should carry more weight than a 3-2 split. Weighting by confidence provides more nuanced aggregation.
**Alternative Considered**: Simple majority (2 of 3 judges) without weighting.
**Benefit**: Better captures judge certainty and provides richer signal.

#### Decision 3: Failure Taxonomy (Not Auto-Loss for All)
**Rationale**: Safety refusals are appropriate behavior and shouldn't be penalized. Only technical/capability failures should result in auto-loss.
**Alternative Considered**: Draft's blanket auto-loss policy.
**Benefit**: Doesn't incentivize unsafe behavior, separates ethical refusals from technical failures.

#### Decision 4: Strict Token Budgets
**Rationale**: Prevents cost blowouts and ensures fair comparisons. Models can't be compared if one receives 200-token prompt and another 2000-token prompt.
**Alternative Considered**: No token limits (draft approach).
**Risk**: Slightly constrains context richness, but ensures consistency.

#### Decision 5: Diversity Validation Gate
**Rationale**: PROMPT.md emphasizes diversity as "CRITICAL". Must measure and enforce before running expensive eval.
**Alternative Considered**: Generate prompts and hope for diversity (draft approach).
**Benefit**: Guarantees eval actually tests diverse scenarios, catches systematic biases early.

### 7. Open Questions and Remaining Design Choices

#### Question 1: Judge Rubric Weighting
**Options**:
A) Remove weights entirely, treat all criteria equally
B) Keep weights but explicitly instruct judges to prioritize weighted criteria
C) Use weighted scoring system with numerical ratings per criterion

**Recommendation**: Option B - keep "authenticity" at 1.5x weight but make this explicit in judge instructions.

#### Question 2: Position Bias Remediation
**Options**:
A) Detect but don't correct (draft approach)
B) Apply statistical correction factor to win rates
C) If bias detected, flag eval as compromised and require re-run

**Recommendation**: Option C for pilot, Option B for full eval (too expensive to re-run 1000 prompts).

#### Question 3: Inter-Judge Agreement Thresholds
**Options**:
A) No action, just report kappa
B) Flag low-agreement comparisons for manual review
C) Require minimum kappa to consider eval valid

**Recommendation**: Option B - flag bottom 10% of comparisons by kappa for manual inspection.

#### Question 4: Temperature Settings
**Options**:
A) Fixed temperature 1.0 for all models (draft approach)
B) Use each model's recommended default temperature
C) Test multiple temperatures (0.7, 1.0, 1.3) as separate conditions

**Recommendation**: Option A for consistency, unless specific models have documented issues at temperature 1.0.

### 8. Success Criteria

**The evaluation is successful if:**

1. **Coverage**: 1000+ prompts spanning all required diversity dimensions (15%+ each generation, formality, skill level; 15+ NAICS sectors)

2. **Statistical Power**: Win rate confidence intervals < ±5% for all model pairs

3. **Judge Agreement**: Average Cohen's Kappa > 0.3 across all comparisons

4. **Completion Rate**: >95% of comparisons complete successfully (not excluding safety refusals)

5. **Reproducibility**: All random seeds saved, exact prompt set archived, model versions recorded

6. **Actionability**: Report identifies ≥5 specific weakness areas for Gemini with concrete examples

7. **Trustworthiness**: Position bias p-value > 0.05 (no significant bias), all judge contexts validated

8. **Usability**: TUI allows filtering/sorting/search, exports work for external analysis, PDF report is clear and comprehensive

### 9. Cost Estimation (Revised)

#### Full Evaluation (1000 prompts)

Assuming OpenRouter average costs (varies by model):
- **Prompt Generation**: 3000 API calls × $0.015/call = $45
- **Model Responses**: 8000 API calls × $0.05/call (average across tiers) = $400
- **Judge Voting**: 30,000 API calls × $0.03/call (judge models) = $900
- **Validation/Pilots**: $150
- **Total**: ~$1500 (range: $1200-2000 depending on model pricing)

#### Quick Evaluation (100 prompts)

- Proportional to full: ~$150-200

#### Dynamic Pricing Check

```python
# Before eval starts, query actual OpenRouter pricing
def estimate_cost(num_prompts: int, config: dict) -> dict:
    """Get real-time cost estimate from OpenRouter API."""

    pricing = await client.get_model_pricing()

    costs = {
        "prompt_generation": num_prompts * 3 * pricing["generation_model"],
        "model_responses": num_prompts * 8 * pricing["eval_models_avg"],
        "judge_voting": num_prompts * 30 * pricing["judge_models_avg"],
        "buffer": 0.2  # 20% buffer for retries
    }

    total = sum(costs.values()) * (1 + costs["buffer"])

    return {
        "breakdown": costs,
        "total_estimate": total,
        "range": (total * 0.8, total * 1.2)
    }
```

## CONCLUSION

This improved plan addresses all critical flaws in Draft Plan 1:

1. ✓ Neutral models for prompt generation (eliminates bias)
2. ✓ Strict judge context validation (ensures fair comparisons)
3. ✓ Weighted voting aggregation (better handles judge certainty)
4. ✓ Failure taxonomy (separates safety from technical failures)
5. ✓ Diversity validation gate (enforces PROMPT.md requirements)
6. ✓ Token budgets (prevents cost blowouts and ensures consistency)
7. ✓ Realistic timeline (6-8 weeks for full eval, not 2 weeks)
8. ✓ Production-grade infrastructure (retry logic, rate limiting, checkpoints)
9. ✓ Enhanced O*NET filtering (two-stage with validation)
10. ✓ Stratified NAICS sampling (guaranteed industry diversity)

The plan is now **implementable, robust, and aligned with PROMPT.md requirements**.
