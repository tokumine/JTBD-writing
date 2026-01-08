# Gemini Writing Evaluation Framework - Improved Implementation Plan

## Critical Evaluation of Draft Plan 3

This document provides a significantly improved implementation plan based on critical analysis of Draft Plan 3. The following issues were identified and addressed:

### Issues Identified in Draft Plan 3

1. **Incomplete NAICS Mapping Strategy**: The draft mentions needing external BLS data but provides no concrete implementation for obtaining or embedding this data. The system would fail at runtime without this critical mapping.

2. **Missing OpenRouter Model Name Verification**: The draft uses model names like `google/gemini-3-pro` without verifying these are the actual OpenRouter model identifiers. Model names on OpenRouter often differ from marketing names.

3. **Inadequate Dual-Persona Judging Implementation**: The draft shows judge personas but doesn't properly implement simultaneous dual-persona evaluation per the PROMPT.md requirement that each comparison should be judged by BOTH personas.

4. **Missing Majority-of-Majorities Implementation Details**: While mentioned, the aggregation logic for majority-of-majorities (across 3 judges x 5 votes x 2 personas) is underspecified.

5. **Company Database Too Small**: The draft shows only a few example companies. A production system needs hundreds of companies across all NAICS sectors and size categories.

6. **Name Generator Lacks Email Domain Handling**: The draft shows email usernames but not how company-specific email domains are generated.

7. **Weak Sensitive Topic Detection**: The failure handler mentions safety refusals but lacks proactive sensitive topic classification during prompt generation.

8. **No Concurrent Request Limit Management**: The rate limiter handles tokens/requests per minute but doesn't manage maximum concurrent connections, which OpenRouter may limit.

9. **Missing Prompt Validation**: No validation that generated prompts meet the diversity and quality requirements before evaluation begins.

10. **Incomplete TUI Error States**: The TUI shows happy-path progress but lacks proper error state handling and recovery UI.

11. **SQLite Concurrency Issues**: The draft uses SQLite but doesn't address write contention with async workers.

12. **Missing Cost Accumulator with Hard Stop**: No mechanism to halt evaluation if costs exceed a user-defined budget.

13. **Weak Temporal Context Generation**: The draft mentions temporal context but lacks systematic date/deadline generation that's consistent with the evaluation date.

14. **No Model Version Tracking**: The draft doesn't capture exact model versions from API responses for reproducibility.

15. **Missing Warm-up/Calibration Phase**: No mechanism to verify API connectivity and calibrate token estimates before committing to a full run.

---

## 1. System Architecture (Improved)

### 1.1 High-Level Architecture

```
                                    +---------------------------+
                                    |     User Interface        |
                                    |  (Rich TUI + CLI Args)    |
                                    +-------------+-------------+
                                                  |
                                    +-------------v-------------+
                                    |    Orchestration Engine   |
                                    |  - Config Management      |
                                    |  - Preset Selection       |
                                    |  - Cost Estimation        |
                                    |  - Budget Enforcement     |  <-- NEW
                                    |  - Warm-up Phase          |  <-- NEW
                                    +-------------+-------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                             |                             |
        +-----------v-----------+   +------------v------------+   +------------v------------+
        |   Prompt Generation   |   |   Response Generation   |   |     Judging System      |
        |   Pipeline            |   |   Engine                |   |                         |
        |  - O*NET Extraction   |   |  - OpenRouter Client    |   |  - Multi-Judge Ensemble |
        |  - Context Enrichment |   |  - Connection Pool Mgmt |   |  - Dual-Persona Per     |
        |  - LLM Enhancement    |   |  - Retry with Circuit   |   |    Comparison           |
        |  - Prompt Validation  |   |    Breaker              |   |  - Majority of          |
        +-----------+-----------+   +------------+------------+   |    Majorities           |
                    |                             |               +------------+------------+
                    +-----------------------------+-----------------------------+
                                                  |
                                    +-------------v-------------+
                                    |    Data Storage Layer     |
                                    |  - SQLite with WAL Mode   |  <-- IMPROVED
                                    |  - Write Coalescing       |  <-- NEW
                                    |  - JSON Checkpoints       |
                                    +-------------+-------------+
                                                  |
                                    +-------------v-------------+
                                    |   Analysis & Reporting    |
                                    |  - Win Rate Calculation   |
                                    |  - Statistical Tests      |
                                    |  - PDF Report Generation  |
                                    +---------------------------+
```

### 1.2 Improved Module Structure

```
gemini_writing_eval/
├── __init__.py
├── cli.py                          # Click-based CLI interface
├── config/
│   ├── __init__.py
│   ├── presets.py                  # 10 preset configurations
│   ├── models.py                   # Model definitions with VERIFIED OpenRouter IDs
│   ├── settings.py                 # Pydantic settings management
│   └── budget.py                   # NEW: Budget limits and cost tracking
├── data/
│   ├── __init__.py
│   ├── onet_extractor.py           # O*NET database access
│   ├── naics_mapper.py             # Industry code mapping with EMBEDDED BLS data
│   ├── company_database.py         # NEW: Comprehensive company database
│   ├── name_generator.py           # Realistic name generation with email domains
│   └── sensitive_topics.py         # NEW: Sensitive topic classification
├── prompts/
│   ├── __init__.py
│   ├── generator.py                # Main prompt generation orchestrator
│   ├── enrichment.py               # LLM enrichment phase
│   ├── personas.py                 # Writer/recipient persona logic
│   ├── temporal.py                 # NEW: Temporal context generation
│   ├── validation.py               # NEW: Prompt validation before evaluation
│   └── schemas.py                  # Pydantic schemas for prompts
├── api/
│   ├── __init__.py
│   ├── openrouter.py               # OpenRouter API client
│   ├── connection_pool.py          # NEW: Connection pool management
│   ├── rate_limiter.py             # Token bucket rate limiting
│   ├── circuit_breaker.py          # NEW: Circuit breaker for failure handling
│   └── retry.py                    # Exponential backoff retry logic
├── evaluation/
│   ├── __init__.py
│   ├── runner.py                   # Main evaluation loop
│   ├── warmup.py                   # NEW: Warm-up/calibration phase
│   ├── judging.py                  # Multi-judge ensemble logic
│   ├── dual_persona.py             # NEW: Dual persona handling
│   ├── rubric.py                   # Evaluation criteria
│   └── aggregation.py              # Majority-of-majorities aggregation
├── storage/
│   ├── __init__.py
│   ├── checkpoint.py               # Checkpoint management
│   ├── database.py                 # SQLite operations with WAL
│   ├── write_coalescer.py          # NEW: Batch writes for performance
│   └── filesystem.py               # Directory structure management
├── analysis/
│   ├── __init__.py
│   ├── statistics.py               # Win rates, confidence intervals
│   ├── bias_detection.py           # Systematic bias analysis
│   └── weakness_finder.py          # Gemini weakness identification
├── reporting/
│   ├── __init__.py
│   ├── pdf_generator.py            # PDF report with plotly
│   ├── charts.py                   # Visualization generation
│   └── templates/                  # Report templates
├── tui/
│   ├── __init__.py
│   ├── app.py                      # Main Textual application
│   ├── screens/
│   │   ├── progress.py             # Live progress dashboard
│   │   ├── viewer.py               # Results viewer
│   │   ├── config.py               # Configuration screen
│   │   └── error_recovery.py       # NEW: Error state handling
│   └── widgets/
└── utils/
    ├── __init__.py
    ├── logging.py                  # Structured logging
    ├── costs.py                    # Cost estimation utilities
    └── model_versions.py           # NEW: Model version tracking
```

### 1.3 Verified Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27"                     # Async HTTP client
pydantic = "^2.5"                   # Data validation
pydantic-settings = "^2.1"          # Configuration management
sqlalchemy = "^2.0"                 # Database ORM
aiosqlite = "^0.19"                 # Async SQLite driver (NEW)
rich = "^13.7"                      # Terminal formatting
textual = "^0.52"                   # TUI framework
plotly = "^5.18"                    # Visualizations
kaleido = "0.2.1"                   # Plotly static export
scipy = "^1.12"                     # Statistical tests
pandas = "^2.2"                     # Data analysis
click = "^8.1"                      # CLI framework
tenacity = "^8.2"                   # Retry logic
anyio = "^4.2"                      # Async utilities
structlog = "^24.1"                 # Structured logging
weasyprint = "^61"                  # PDF generation
jinja2 = "^3.1"                     # Report templates
numpy = "^1.26"                     # Numerical operations
scikit-learn = "^1.4"               # For Cohen's Kappa calculation
```

---

## 2. OpenRouter Model Configuration (CRITICAL FIX)

### 2.1 Verified Model Identifiers

**IMPORTANT**: Model identifiers must be verified against the actual OpenRouter API. The following are based on OpenRouter's typical naming conventions but MUST be verified before implementation:

```python
# config/models.py

from dataclasses import dataclass
from enum import Enum

class ModelTier(Enum):
    PRO = "pro"
    FLASH = "flash"

@dataclass
class ModelConfig:
    """Configuration for a model with verified OpenRouter ID."""
    display_name: str
    openrouter_id: str  # MUST match OpenRouter exactly
    tier: ModelTier
    # Pricing per 1M tokens (to be verified from OpenRouter API)
    input_price_per_million: float
    output_price_per_million: float
    # Rate limits (requests per minute, tokens per minute)
    rpm_limit: int
    tpm_limit: int
    # Whether this model can be used as a judge
    can_judge: bool = True

# These IDs need verification against OpenRouter's actual catalog
# Run: curl https://openrouter.ai/api/v1/models -H "Authorization: Bearer $API_KEY"
MODELS = {
    # Pro tier - Gemini
    "gemini-3-pro": ModelConfig(
        display_name="Gemini 3.0 Pro",
        openrouter_id="google/gemini-2.0-flash-thinking-exp",  # VERIFY THIS
        tier=ModelTier.PRO,
        input_price_per_million=2.50,
        output_price_per_million=10.00,
        rpm_limit=60,
        tpm_limit=100000,
    ),
    # Pro tier - Competitors
    "gpt-5.2-thinking": ModelConfig(
        display_name="GPT-5.2 Thinking",
        openrouter_id="openai/o1-preview",  # VERIFY - may need update for 5.2
        tier=ModelTier.PRO,
        input_price_per_million=15.00,
        output_price_per_million=60.00,
        rpm_limit=20,
        tpm_limit=150000,
    ),
    "claude-opus-4.5": ModelConfig(
        display_name="Claude Opus 4.5",
        openrouter_id="anthropic/claude-3.5-sonnet",  # VERIFY - update for 4.5
        tier=ModelTier.PRO,
        input_price_per_million=15.00,
        output_price_per_million=75.00,
        rpm_limit=50,
        tpm_limit=100000,
    ),
    "grok-4.1-thinking": ModelConfig(
        display_name="Grok 4.1 Thinking",
        openrouter_id="x-ai/grok-2",  # VERIFY
        tier=ModelTier.PRO,
        input_price_per_million=5.00,
        output_price_per_million=15.00,
        rpm_limit=60,
        tpm_limit=100000,
    ),
    "kimi-k2-thinking": ModelConfig(
        display_name="Kimi K2 Thinking",
        openrouter_id="moonshot/moonshot-v1-8k",  # VERIFY
        tier=ModelTier.PRO,
        input_price_per_million=2.00,
        output_price_per_million=8.00,
        rpm_limit=60,
        tpm_limit=100000,
    ),
    # Flash tier
    "gemini-3-flash": ModelConfig(
        display_name="Gemini 3.0 Flash",
        openrouter_id="google/gemini-2.0-flash-exp",  # VERIFY
        tier=ModelTier.FLASH,
        input_price_per_million=0.10,
        output_price_per_million=0.40,
        rpm_limit=100,
        tpm_limit=200000,
    ),
    "gpt-4.1": ModelConfig(
        display_name="GPT-4.1",
        openrouter_id="openai/gpt-4-turbo",  # VERIFY
        tier=ModelTier.FLASH,
        input_price_per_million=10.00,
        output_price_per_million=30.00,
        rpm_limit=60,
        tpm_limit=150000,
    ),
    "claude-sonnet": ModelConfig(
        display_name="Claude Sonnet",
        openrouter_id="anthropic/claude-3.5-sonnet",  # VERIFY
        tier=ModelTier.FLASH,
        input_price_per_million=3.00,
        output_price_per_million=15.00,
        rpm_limit=60,
        tpm_limit=100000,
    ),
}

async def verify_model_availability(api_client, model_ids: list[str]) -> dict[str, bool]:
    """Verify which models are available on OpenRouter."""
    response = await api_client.get("/models")
    available = {m["id"] for m in response["data"]}
    return {mid: mid in available for mid in model_ids}
```

### 2.2 Model Verification at Startup

```python
# evaluation/warmup.py

class WarmupPhase:
    """Pre-evaluation verification and calibration."""

    async def run(self, config: EvalConfig, api_client: APIClient) -> WarmupResult:
        """
        Run all pre-flight checks before evaluation begins.

        1. Verify API connectivity
        2. Verify all models are available
        3. Run calibration prompts to estimate token usage
        4. Verify sufficient API credits
        5. Test judge models
        """
        results = WarmupResult()

        # 1. Verify API connectivity
        try:
            await api_client.health_check()
            results.api_connected = True
        except Exception as e:
            results.api_connected = False
            results.errors.append(f"API connection failed: {e}")
            return results

        # 2. Verify model availability
        all_model_ids = self._collect_all_model_ids(config)
        availability = await verify_model_availability(api_client, all_model_ids)

        unavailable = [mid for mid, avail in availability.items() if not avail]
        if unavailable:
            results.errors.append(f"Models not available: {unavailable}")
            return results
        results.models_verified = True

        # 3. Run calibration prompts
        calibration = await self._run_calibration(config, api_client)
        results.token_estimates = calibration

        # 4. Estimate costs and check budget
        estimated_cost = self._estimate_total_cost(config, calibration)
        if config.budget_limit and estimated_cost > config.budget_limit:
            results.warnings.append(
                f"Estimated cost ${estimated_cost:.2f} exceeds budget ${config.budget_limit:.2f}"
            )
        results.estimated_cost = estimated_cost

        # 5. Test judge models with sample comparison
        judge_test = await self._test_judges(config, api_client)
        results.judges_verified = judge_test.success

        return results

    async def _run_calibration(self, config, api_client) -> TokenEstimates:
        """Run sample prompts to calibrate token estimates."""
        # Generate 3 sample prompts of varying complexity
        # Run through 1 model to measure actual token usage
        # Return calibrated estimates
        pass
```

---

## 3. NAICS Industry Mapping (CRITICAL FIX)

### 3.1 Embedded BLS Occupation-Industry Matrix

The draft plan correctly identified that O*NET lacks NAICS codes but failed to provide a concrete solution. Here's the implementation:

```python
# data/naics_mapper.py

"""
NAICS industry mapping using embedded BLS Occupation-Industry Matrix data.

The BLS publishes occupation-industry employment data annually. This module
embeds a compressed version for the most common occupation-industry combinations.
"""

import json
from dataclasses import dataclass
from pathlib import Path

@dataclass
class IndustryMapping:
    naics_code: str
    naics_name: str
    employment_share: float  # % of occupation employed in this industry

# NAICS 2-digit sectors
NAICS_SECTORS = {
    "11": "Agriculture, Forestry, Fishing and Hunting",
    "21": "Mining, Quarrying, and Oil and Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",  # 31-33 collapsed
    "42": "Wholesale Trade",
    "44": "Retail Trade",  # 44-45 collapsed
    "48": "Transportation and Warehousing",  # 48-49 collapsed
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
    "92": "Public Administration",
}

class NAICSMapper:
    """
    Map SOC occupation codes to NAICS industry codes.

    Uses embedded BLS Occupation-Industry Matrix data. The matrix shows
    employment distribution of each occupation across industries.
    """

    def __init__(self):
        # Load embedded occupation-industry matrix
        # This would be a JSON file bundled with the package
        matrix_path = Path(__file__).parent / "bls_occupation_industry_matrix.json"
        if matrix_path.exists():
            with open(matrix_path) as f:
                self._matrix = json.load(f)
        else:
            # Fallback to broad SOC-major-group to NAICS mapping
            self._matrix = self._generate_fallback_matrix()

    def _generate_fallback_matrix(self) -> dict:
        """
        Generate a fallback mapping based on SOC major groups.

        This is a simplified mapping when full BLS data isn't available.
        Each SOC major group maps to its most common industries.
        """
        return {
            # Management Occupations (11-*)
            "11": [
                IndustryMapping("54", "Professional Services", 0.25),
                IndustryMapping("52", "Finance and Insurance", 0.15),
                IndustryMapping("62", "Health Care", 0.12),
                IndustryMapping("31", "Manufacturing", 0.10),
                IndustryMapping("44", "Retail Trade", 0.08),
                IndustryMapping("23", "Construction", 0.08),
                IndustryMapping("51", "Information", 0.07),
                IndustryMapping("72", "Accommodation and Food Services", 0.05),
                IndustryMapping("56", "Administrative Services", 0.05),
                IndustryMapping("92", "Public Administration", 0.05),
            ],
            # Business and Financial Operations (13-*)
            "13": [
                IndustryMapping("54", "Professional Services", 0.30),
                IndustryMapping("52", "Finance and Insurance", 0.25),
                IndustryMapping("55", "Management of Companies", 0.10),
                IndustryMapping("92", "Public Administration", 0.08),
                IndustryMapping("62", "Health Care", 0.07),
                IndustryMapping("31", "Manufacturing", 0.07),
                IndustryMapping("51", "Information", 0.06),
                IndustryMapping("56", "Administrative Services", 0.07),
            ],
            # Computer and Mathematical (15-*)
            "15": [
                IndustryMapping("54", "Professional Services", 0.35),
                IndustryMapping("51", "Information", 0.25),
                IndustryMapping("52", "Finance and Insurance", 0.12),
                IndustryMapping("31", "Manufacturing", 0.08),
                IndustryMapping("55", "Management of Companies", 0.07),
                IndustryMapping("92", "Public Administration", 0.05),
                IndustryMapping("62", "Health Care", 0.04),
                IndustryMapping("61", "Educational Services", 0.04),
            ],
            # ... Continue for all 22 SOC major groups
        }

    def get_industries_for_occupation(self, soc_code: str) -> list[IndustryMapping]:
        """
        Get list of industries where this occupation commonly works.

        Returns industries sorted by employment share (descending).
        """
        # Try exact SOC code first
        if soc_code in self._matrix:
            return self._matrix[soc_code]

        # Fall back to SOC major group (first 2 digits)
        soc_major = soc_code[:2]
        if soc_major in self._matrix:
            return self._matrix[soc_major]

        # Default: all industries with equal weight
        return [
            IndustryMapping(code, name, 1.0 / len(NAICS_SECTORS))
            for code, name in NAICS_SECTORS.items()
        ]

    def sample_industry(self, soc_code: str, rng) -> IndustryMapping:
        """
        Sample an industry for this occupation weighted by employment share.

        Uses the provided random number generator for reproducibility.
        """
        industries = self.get_industries_for_occupation(soc_code)
        weights = [ind.employment_share for ind in industries]

        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]

        # Sample
        idx = rng.choice(len(industries), p=weights)
        return industries[idx]

    def sample_diverse_industries(self,
                                   soc_code: str,
                                   num_samples: int,
                                   rng) -> list[IndustryMapping]:
        """
        Sample multiple diverse industries, ensuring no duplicates.
        """
        industries = self.get_industries_for_occupation(soc_code)

        if num_samples >= len(industries):
            return industries.copy()

        # Sample without replacement, weighted
        weights = [ind.employment_share for ind in industries]
        total = sum(weights)
        weights = [w / total for w in weights]

        indices = rng.choice(
            len(industries),
            size=num_samples,
            replace=False,
            p=weights
        )
        return [industries[i] for i in indices]
```

---

## 4. Comprehensive Company Database (CRITICAL FIX)

### 4.1 Company Database Structure

The draft plan showed only a few example companies. A production system needs comprehensive coverage:

```python
# data/company_database.py

"""
Comprehensive database of real companies for realistic prompt grounding.

Organized by NAICS sector and company size. Each entry includes metadata
for realistic scenario generation.
"""

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

class CompanySize(Enum):
    FORTUNE_500 = "fortune_500"
    LARGE = "large"              # 1000-10000 employees
    MIDMARKET = "midmarket"      # 100-1000 employees
    SMALL_BUSINESS = "small"     # 10-100 employees
    STARTUP = "startup"          # <10 employees

@dataclass
class Company:
    name: str
    naics_code: str
    size: CompanySize
    employee_range: str
    founded_year: int | None
    is_public: bool
    hq_city: str
    hq_country: str
    industry_description: str
    # For generating realistic email domains
    email_domain: str | None

class CompanyDatabase:
    """
    Database of real companies organized by industry and size.

    Provides approximately 500+ companies across:
    - 20 NAICS sectors
    - 5 size categories
    - Geographic diversity (US-focused with international)
    """

    def __init__(self):
        self._companies = self._load_companies()

    def _load_companies(self) -> dict[str, dict[str, list[Company]]]:
        """
        Load companies from embedded data.

        Structure: {naics_code: {size: [companies]}}
        """
        # This would be loaded from a JSON file in production
        # Here we show the structure with representative examples

        return {
            # Professional, Scientific, and Technical Services (54)
            "54": {
                CompanySize.FORTUNE_500: [
                    Company("Deloitte", "54", CompanySize.FORTUNE_500,
                            "300,000-400,000", 1845, False, "New York", "USA",
                            "Professional services and consulting", "deloitte.com"),
                    Company("Accenture", "54", CompanySize.FORTUNE_500,
                            "700,000+", 1989, True, "Dublin", "Ireland",
                            "Consulting and professional services", "accenture.com"),
                    Company("McKinsey & Company", "54", CompanySize.FORTUNE_500,
                            "30,000-45,000", 1926, False, "New York", "USA",
                            "Management consulting", "mckinsey.com"),
                    Company("Boston Consulting Group", "54", CompanySize.FORTUNE_500,
                            "25,000-30,000", 1963, False, "Boston", "USA",
                            "Management consulting", "bcg.com"),
                    Company("KPMG", "54", CompanySize.FORTUNE_500,
                            "200,000-250,000", 1987, False, "Amstelveen", "Netherlands",
                            "Audit, tax, and advisory services", "kpmg.com"),
                    Company("PwC", "54", CompanySize.FORTUNE_500,
                            "280,000-330,000", 1998, False, "London", "UK",
                            "Professional services", "pwc.com"),
                    Company("Ernst & Young", "54", CompanySize.FORTUNE_500,
                            "300,000-365,000", 1989, False, "London", "UK",
                            "Professional services", "ey.com"),
                ],
                CompanySize.LARGE: [
                    Company("Booz Allen Hamilton", "54", CompanySize.LARGE,
                            "25,000-30,000", 1914, True, "McLean", "USA",
                            "Government consulting", "bah.com"),
                    Company("Bain & Company", "54", CompanySize.LARGE,
                            "12,000-15,000", 1973, False, "Boston", "USA",
                            "Management consulting", "bain.com"),
                    Company("Oliver Wyman", "54", CompanySize.LARGE,
                            "5,000-7,000", 1984, False, "New York", "USA",
                            "Management consulting", "oliverwyman.com"),
                ],
                CompanySize.MIDMARKET: [
                    Company("West Monroe Partners", "54", CompanySize.MIDMARKET,
                            "2,000-3,000", 2002, False, "Chicago", "USA",
                            "Business and technology consulting", "westmonroe.com"),
                    Company("FTI Consulting", "54", CompanySize.MIDMARKET,
                            "6,000-8,000", 1982, True, "Washington DC", "USA",
                            "Business advisory", "fticonsulting.com"),
                    Company("ZS Associates", "54", CompanySize.MIDMARKET,
                            "10,000-12,000", 1983, False, "Evanston", "USA",
                            "Sales and marketing consulting", "zs.com"),
                ],
                CompanySize.SMALL_BUSINESS: [
                    Company("Apex Business Solutions", "54", CompanySize.SMALL_BUSINESS,
                            "25-50", 2015, False, "Austin", "USA",
                            "Regional business consulting", None),
                    Company("Strategic Growth Partners", "54", CompanySize.SMALL_BUSINESS,
                            "15-25", 2018, False, "Denver", "USA",
                            "Growth strategy consulting", None),
                ],
                CompanySize.STARTUP: [
                    Company("Innova Strategy Group", "54", CompanySize.STARTUP,
                            "3-8", 2022, False, "San Francisco", "USA",
                            "Early-stage startup consulting", None),
                ],
            },

            # Finance and Insurance (52)
            "52": {
                CompanySize.FORTUNE_500: [
                    Company("JPMorgan Chase", "52", CompanySize.FORTUNE_500,
                            "250,000-290,000", 1799, True, "New York", "USA",
                            "Investment banking and financial services", "jpmorganchase.com"),
                    Company("Bank of America", "52", CompanySize.FORTUNE_500,
                            "200,000-220,000", 1998, True, "Charlotte", "USA",
                            "Banking and financial services", "bankofamerica.com"),
                    Company("Goldman Sachs", "52", CompanySize.FORTUNE_500,
                            "40,000-50,000", 1869, True, "New York", "USA",
                            "Investment banking", "goldmansachs.com"),
                    Company("Morgan Stanley", "52", CompanySize.FORTUNE_500,
                            "70,000-85,000", 1935, True, "New York", "USA",
                            "Financial services", "morganstanley.com"),
                    Company("Citigroup", "52", CompanySize.FORTUNE_500,
                            "200,000-240,000", 1998, True, "New York", "USA",
                            "Financial services", "citigroup.com"),
                    Company("Wells Fargo", "52", CompanySize.FORTUNE_500,
                            "230,000-260,000", 1852, True, "San Francisco", "USA",
                            "Banking", "wellsfargo.com"),
                    Company("State Farm", "52", CompanySize.FORTUNE_500,
                            "55,000-65,000", 1922, False, "Bloomington", "USA",
                            "Insurance", "statefarm.com"),
                    Company("Berkshire Hathaway", "52", CompanySize.FORTUNE_500,
                            "350,000-400,000", 1839, True, "Omaha", "USA",
                            "Diversified insurance and investments", "berkshirehathaway.com"),
                ],
                CompanySize.LARGE: [
                    Company("Charles Schwab", "52", CompanySize.LARGE,
                            "30,000-35,000", 1971, True, "Westlake", "USA",
                            "Brokerage and banking", "schwab.com"),
                    Company("Capital One", "52", CompanySize.LARGE,
                            "50,000-55,000", 1994, True, "McLean", "USA",
                            "Banking and credit cards", "capitalone.com"),
                ],
                CompanySize.MIDMARKET: [
                    Company("First Republic Bank", "52", CompanySize.MIDMARKET,
                            "5,000-7,000", 1985, True, "San Francisco", "USA",
                            "Private banking", "firstrepublic.com"),
                    Company("Signature Bank", "52", CompanySize.MIDMARKET,
                            "2,000-3,000", 2001, True, "New York", "USA",
                            "Commercial banking", None),
                ],
                CompanySize.SMALL_BUSINESS: [
                    Company("Valley Community Bank", "52", CompanySize.SMALL_BUSINESS,
                            "50-100", 1985, False, "Sacramento", "USA",
                            "Community banking", None),
                ],
                CompanySize.STARTUP: [
                    Company("FinFlow Technologies", "52", CompanySize.STARTUP,
                            "5-15", 2021, False, "New York", "USA",
                            "Fintech startup", None),
                ],
            },

            # Health Care and Social Assistance (62)
            "62": {
                CompanySize.FORTUNE_500: [
                    Company("UnitedHealth Group", "62", CompanySize.FORTUNE_500,
                            "350,000-400,000", 1977, True, "Minnetonka", "USA",
                            "Health insurance and services", "uhc.com"),
                    Company("CVS Health", "62", CompanySize.FORTUNE_500,
                            "300,000-350,000", 1963, True, "Woonsocket", "USA",
                            "Health care and pharmacy", "cvshealth.com"),
                    Company("Kaiser Permanente", "62", CompanySize.FORTUNE_500,
                            "200,000-220,000", 1945, False, "Oakland", "USA",
                            "Integrated managed care", "kaiserpermanente.org"),
                    Company("HCA Healthcare", "62", CompanySize.FORTUNE_500,
                            "250,000-280,000", 1968, True, "Nashville", "USA",
                            "Hospital operator", "hcahealthcare.com"),
                    Company("Anthem", "62", CompanySize.FORTUNE_500,
                            "90,000-100,000", 2014, True, "Indianapolis", "USA",
                            "Health insurance", "anthem.com"),
                ],
                CompanySize.LARGE: [
                    Company("Ascension Health", "62", CompanySize.LARGE,
                            "150,000-160,000", 1999, False, "St. Louis", "USA",
                            "Catholic health system", "ascension.org"),
                    Company("Mayo Clinic", "62", CompanySize.LARGE,
                            "70,000-80,000", 1864, False, "Rochester", "USA",
                            "Academic medical center", "mayoclinic.org"),
                ],
                CompanySize.MIDMARKET: [
                    Company("Regional Medical Center", "62", CompanySize.MIDMARKET,
                            "2,000-5,000", 1965, False, "Various", "USA",
                            "Regional hospital system", None),
                ],
                CompanySize.SMALL_BUSINESS: [
                    Company("Valley Family Medicine", "62", CompanySize.SMALL_BUSINESS,
                            "15-30", 2005, False, "Phoenix", "USA",
                            "Family medical practice", None),
                ],
                CompanySize.STARTUP: [
                    Company("TeleHealth Connect", "62", CompanySize.STARTUP,
                            "5-12", 2020, False, "Austin", "USA",
                            "Telemedicine startup", None),
                ],
            },

            # Information Technology (51)
            "51": {
                CompanySize.FORTUNE_500: [
                    Company("Apple", "51", CompanySize.FORTUNE_500,
                            "150,000-165,000", 1976, True, "Cupertino", "USA",
                            "Technology", "apple.com"),
                    Company("Microsoft", "51", CompanySize.FORTUNE_500,
                            "180,000-220,000", 1975, True, "Redmond", "USA",
                            "Software and cloud services", "microsoft.com"),
                    Company("Google", "51", CompanySize.FORTUNE_500,
                            "180,000-190,000", 1998, True, "Mountain View", "USA",
                            "Internet services and advertising", "google.com"),
                    Company("Meta", "51", CompanySize.FORTUNE_500,
                            "60,000-85,000", 2004, True, "Menlo Park", "USA",
                            "Social media and technology", "meta.com"),
                    Company("Amazon", "51", CompanySize.FORTUNE_500,
                            "1,500,000+", 1994, True, "Seattle", "USA",
                            "E-commerce and cloud services", "amazon.com"),
                    Company("Netflix", "51", CompanySize.FORTUNE_500,
                            "12,000-15,000", 1997, True, "Los Gatos", "USA",
                            "Streaming entertainment", "netflix.com"),
                    Company("Salesforce", "51", CompanySize.FORTUNE_500,
                            "70,000-80,000", 1999, True, "San Francisco", "USA",
                            "Cloud software", "salesforce.com"),
                    Company("Adobe", "51", CompanySize.FORTUNE_500,
                            "25,000-30,000", 1982, True, "San Jose", "USA",
                            "Creative and document software", "adobe.com"),
                ],
                CompanySize.LARGE: [
                    Company("Spotify", "51", CompanySize.LARGE,
                            "8,000-10,000", 2006, True, "Stockholm", "Sweden",
                            "Music streaming", "spotify.com"),
                    Company("Twilio", "51", CompanySize.LARGE,
                            "7,000-9,000", 2008, True, "San Francisco", "USA",
                            "Cloud communications", "twilio.com"),
                    Company("Atlassian", "51", CompanySize.LARGE,
                            "8,000-10,000", 2002, True, "Sydney", "Australia",
                            "Collaboration software", "atlassian.com"),
                ],
                CompanySize.MIDMARKET: [
                    Company("Notion", "51", CompanySize.MIDMARKET,
                            "400-600", 2016, False, "San Francisco", "USA",
                            "Productivity software", "notion.so"),
                    Company("Figma", "51", CompanySize.MIDMARKET,
                            "800-1,200", 2012, False, "San Francisco", "USA",
                            "Design software", "figma.com"),
                ],
                CompanySize.SMALL_BUSINESS: [
                    Company("LocalTech Solutions", "51", CompanySize.SMALL_BUSINESS,
                            "20-40", 2018, False, "Denver", "USA",
                            "IT services", None),
                ],
                CompanySize.STARTUP: [
                    Company("AI Innovations Lab", "51", CompanySize.STARTUP,
                            "4-10", 2023, False, "San Francisco", "USA",
                            "AI startup", None),
                ],
            },

            # Continue for all 20 NAICS sectors...
            # Manufacturing (31), Retail Trade (44), Construction (23),
            # Education (61), Transportation (48), etc.
        }

    def get_company(self,
                    naics_code: str,
                    size: CompanySize | None = None,
                    rng=None) -> Company:
        """
        Get a company for the given industry, optionally filtered by size.

        If rng is provided, randomly sample. Otherwise return first match.
        """
        # Map to 2-digit NAICS
        naics_2digit = naics_code[:2]

        if naics_2digit not in self._companies:
            # Fallback to generic company
            return self._generate_generic_company(naics_code, size)

        industry_companies = self._companies[naics_2digit]

        if size:
            if size in industry_companies:
                companies = industry_companies[size]
            else:
                # Fallback to any size in this industry
                companies = [c for sizes in industry_companies.values() for c in sizes]
        else:
            companies = [c for sizes in industry_companies.values() for c in sizes]

        if not companies:
            return self._generate_generic_company(naics_code, size)

        if rng:
            return rng.choice(companies)
        return companies[0]

    def _generate_generic_company(self, naics_code: str, size: CompanySize | None) -> Company:
        """Generate a generic company description when no specific company available."""
        naics_name = NAICS_SECTORS.get(naics_code[:2], "General Business")
        size = size or CompanySize.MIDMARKET

        size_desc = {
            CompanySize.FORTUNE_500: "Fortune 500",
            CompanySize.LARGE: "Large",
            CompanySize.MIDMARKET: "Mid-sized",
            CompanySize.SMALL_BUSINESS: "Small",
            CompanySize.STARTUP: "Early-stage startup",
        }

        return Company(
            name=f"{size_desc[size]} {naics_name} company",
            naics_code=naics_code,
            size=size,
            employee_range=self._get_employee_range(size),
            founded_year=None,
            is_public=size in [CompanySize.FORTUNE_500, CompanySize.LARGE],
            hq_city="United States",
            hq_country="USA",
            industry_description=naics_name,
            email_domain=None
        )

    def _get_employee_range(self, size: CompanySize) -> str:
        return {
            CompanySize.FORTUNE_500: "10,000+",
            CompanySize.LARGE: "1,000-10,000",
            CompanySize.MIDMARKET: "100-1,000",
            CompanySize.SMALL_BUSINESS: "10-100",
            CompanySize.STARTUP: "1-10",
        }[size]
```

---

## 5. Dual-Persona Judging Implementation (CRITICAL FIX)

The PROMPT.md requires that each comparison be judged by BOTH the writing expert AND the simulated recipient. The draft plan showed these as options but didn't implement proper simultaneous dual-persona evaluation:

```python
# evaluation/dual_persona.py

"""
Dual-persona judging implementation.

Per PROMPT.md requirements, each comparison must be evaluated by BOTH:
1. A simulated writing expert (judging craft quality)
2. A simulated target recipient (judging effectiveness for them)

The final judgment aggregates across both personas.
"""

from dataclasses import dataclass
from enum import Enum

class JudgePersona(Enum):
    WRITING_EXPERT = "writing_expert"
    TARGET_RECIPIENT = "target_recipient"

@dataclass
class PersonaPrompt:
    persona: JudgePersona
    system_prompt: str
    context_instructions: str

PERSONA_PROMPTS = {
    JudgePersona.WRITING_EXPERT: PersonaPrompt(
        persona=JudgePersona.WRITING_EXPERT,
        system_prompt="""You are an expert writing professional with 20+ years of experience
evaluating business and professional communication. You have worked as an editor,
communications director, and writing coach for Fortune 500 executives.

Your expertise allows you to assess writing craft with nuance: not just whether
something is "correct" but whether it achieves its communicative purpose elegantly.""",

        context_instructions="""Assess the writing based on craft quality:

1. **Clarity & Structure**: Is the writing clear, well-organized, and easy to follow?
   Does it have a logical flow? Are transitions smooth?

2. **Tone Calibration**: Is the tone precisely calibrated for this specific context?
   Consider the relationship, formality level, and emotional situation.

3. **Concision**: Is every word earning its place? No padding, no unnecessary
   pleasantries, but also not missing key information?

4. **Voice & Authenticity**: Does this read like genuine human writing?
   Or does it have telltale AI patterns like:
   - "I hope this email finds you well"
   - "Please don't hesitate to reach out"
   - "I'm happy to help with that"
   - Excessive bullet points where prose is natural
   - Overly formal hedging language

5. **Professional Polish**: Would a skilled professional in this role produce
   writing of this quality? Does it meet the standards for this context?

6. **Instruction Following**: If specific constraints were given (length, format,
   tone directives), were they followed precisely?"""
    ),

    JudgePersona.TARGET_RECIPIENT: PersonaPrompt(
        persona=JudgePersona.TARGET_RECIPIENT,
        system_prompt="""You are the intended recipient of this communication.
You will be given context about who you are, your relationship to the sender,
and the situation. Evaluate the message from your perspective as the receiver.

Consider: Would this message achieve its purpose with you? Would you respond
positively? Does it respect your time and address your needs?""",

        context_instructions="""Based on your role as the recipient, evaluate:

1. **Effectiveness**: Does this message accomplish what it needs to?
   Would you understand what's being asked/communicated?

2. **Actionability**: Can you act on this? Is it clear what (if anything)
   you need to do next?

3. **Appropriateness**: Given your relationship with the sender and the
   context, is the tone appropriate? Too formal? Too casual?

4. **Respect for Your Time**: Is the length appropriate? Does it get to
   the point without being curt?

5. **Authenticity**: Does this feel like a real message from a real person?
   Or does it feel generated/template-like?

6. **Recipient-Specific Fit**: Does it acknowledge your specific situation,
   needs, or concerns? Or is it generic?"""
    )
}

class DualPersonaJudge:
    """
    Implements dual-persona judging for each comparison.

    For each model pair comparison:
    1. Get 5 votes from each judge model as the writing expert
    2. Get 5 votes from each judge model as the target recipient
    3. Aggregate within each persona
    4. Combine across personas for final judgment
    """

    def __init__(self,
                 api_client,
                 judge_models: list[str],
                 votes_per_judge: int = 5):
        self.api = api_client
        self.judge_models = judge_models
        self.votes_per_judge = votes_per_judge

    async def judge_comparison(self,
                                prompt: WritingPrompt,
                                response_a: Response,
                                response_b: Response,
                                gemini_position: str) -> DualPersonaJudgment:
        """
        Run full dual-persona judging for a comparison.

        Returns aggregated judgment across both personas and all judges.
        """

        all_judgments = []

        for judge_model in self.judge_models:
            for persona in [JudgePersona.WRITING_EXPERT, JudgePersona.TARGET_RECIPIENT]:
                persona_prompt = self._build_persona_prompt(
                    prompt, response_a, response_b, persona
                )

                votes = await self._collect_votes(
                    judge_model, persona_prompt, self.votes_per_judge
                )

                # Map votes back to actual models
                mapped_votes = self._map_votes_to_models(votes, gemini_position)

                all_judgments.append(PersonaJudgment(
                    judge_model=judge_model,
                    persona=persona,
                    votes=mapped_votes,
                    majority=self._compute_majority(mapped_votes)
                ))

        return self._aggregate_dual_persona(all_judgments)

    def _build_persona_prompt(self,
                               prompt: WritingPrompt,
                               response_a: Response,
                               response_b: Response,
                               persona: JudgePersona) -> str:
        """Build the full judge prompt with persona-specific instructions."""

        persona_config = PERSONA_PROMPTS[persona]

        # For target recipient, customize based on the actual recipient persona
        if persona == JudgePersona.TARGET_RECIPIENT:
            recipient_context = self._build_recipient_context(prompt)
        else:
            recipient_context = ""

        return f"""{persona_config.system_prompt}

## Writing Task Context

{self._format_task_context(prompt)}

{recipient_context}

## Response A

{response_a.text}

## Response B

{response_b.text}

## Evaluation Criteria

{persona_config.context_instructions}

## Your Judgment

Based on your expertise/perspective and the specific context of this writing task,
which response is better?

Respond with ONLY one of:
- "A" if Response A is clearly better
- "B" if Response B is clearly better
- "TIE" if they are roughly equivalent

Your judgment:"""

    def _build_recipient_context(self, prompt: WritingPrompt) -> str:
        """Build recipient-specific context for the target recipient persona."""

        recipient = prompt.recipients[0] if prompt.recipients else None
        if not recipient:
            return ""

        return f"""## Your Role as Recipient

You are {recipient.name}, {recipient.title} at {prompt.company.name}.
Your relationship with the sender: {prompt.relationship_context}
The emotional context: {prompt.emotional_context}
The urgency level: {prompt.urgency_level}

Consider how you would receive this message given who you are and the situation."""

    def _aggregate_dual_persona(self,
                                 judgments: list[PersonaJudgment]) -> DualPersonaJudgment:
        """
        Aggregate judgments across both personas using majority-of-majorities.

        Structure:
        1. For each judge model, for each persona: compute majority of 5 votes
        2. For each judge model: combine two persona majorities
        3. Across all judges: compute final majority

        Per PROMPT.md: "majority of the 3 judge winners"
        """

        # Group by judge model
        by_judge = defaultdict(list)
        for j in judgments:
            by_judge[j.judge_model].append(j)

        judge_winners = []
        for judge_model, judge_judgments in by_judge.items():
            # Get majority per persona
            expert_judgment = next(
                j for j in judge_judgments if j.persona == JudgePersona.WRITING_EXPERT
            )
            recipient_judgment = next(
                j for j in judge_judgments if j.persona == JudgePersona.TARGET_RECIPIENT
            )

            # If both personas agree, that's the judge's verdict
            if expert_judgment.majority == recipient_judgment.majority:
                judge_winners.append(expert_judgment.majority)
            else:
                # If they disagree, could use various strategies:
                # Option 1: Expert wins
                # Option 2: Count as tie
                # Option 3: Weight by confidence
                # For now: if either says tie, use the other; else tie
                if expert_judgment.majority == "tie":
                    judge_winners.append(recipient_judgment.majority)
                elif recipient_judgment.majority == "tie":
                    judge_winners.append(expert_judgment.majority)
                else:
                    judge_winners.append("tie")

        # Final majority across judges
        final_winner = self._compute_majority(judge_winners)

        return DualPersonaJudgment(
            judgments=judgments,
            judge_winners=judge_winners,
            final_winner=final_winner,
            agreement_rate=self._compute_agreement(judgments)
        )

    def _compute_majority(self, votes: list[str]) -> str:
        """Compute majority vote from a list of 'gemini'/'competitor'/'tie' votes."""
        counts = {"gemini": 0, "competitor": 0, "tie": 0}
        for v in votes:
            counts[v] = counts.get(v, 0) + 1

        if counts["gemini"] > counts["competitor"] + counts["tie"]:
            return "gemini"
        elif counts["competitor"] > counts["gemini"] + counts["tie"]:
            return "competitor"
        else:
            return "tie"
```

---

## 6. SQLite Concurrency Handling (CRITICAL FIX)

The draft plan uses SQLite with async workers but doesn't address write contention:

```python
# storage/database.py

"""
SQLite database operations with proper async handling.

Uses WAL mode for better concurrent read performance and
write coalescing to avoid contention from multiple workers.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import aiosqlite
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

class AsyncDatabase:
    """
    Async SQLite database with WAL mode and write coalescing.

    Design decisions:
    1. WAL mode: Allows concurrent reads during writes
    2. Single writer: All writes go through a queue to avoid contention
    3. Batch commits: Coalesce multiple writes into single transactions
    4. Read replicas: Reads can use separate connections
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._write_task: asyncio.Task | None = None
        self._read_connection: aiosqlite.Connection | None = None

    async def initialize(self):
        """Initialize database with schema and WAL mode."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=-64000")  # 64MB cache

            # Create schema
            await self._create_schema(db)
            await db.commit()

        # Start write worker
        self._write_task = asyncio.create_task(self._write_worker())

    async def _create_schema(self, db: aiosqlite.Connection):
        """Create all tables."""
        await db.executescript(SCHEMA_SQL)

    async def _write_worker(self):
        """
        Single writer that processes all write operations.

        Batches writes together for efficiency.
        """
        batch = []
        BATCH_SIZE = 50
        BATCH_TIMEOUT = 0.5  # seconds

        while True:
            try:
                # Wait for first item
                item = await asyncio.wait_for(
                    self._write_queue.get(),
                    timeout=BATCH_TIMEOUT if batch else None
                )
                batch.append(item)

                # Collect more items if available (non-blocking)
                while len(batch) < BATCH_SIZE:
                    try:
                        item = self._write_queue.get_nowait()
                        batch.append(item)
                    except asyncio.QueueEmpty:
                        break

            except asyncio.TimeoutError:
                pass  # Timeout reached, process current batch

            if batch:
                await self._process_batch(batch)
                batch = []

    async def _process_batch(self, batch: list):
        """Process a batch of write operations in a single transaction."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                for operation in batch:
                    if operation["type"] == "execute":
                        await db.execute(operation["sql"], operation["params"])
                    elif operation["type"] == "executemany":
                        await db.executemany(operation["sql"], operation["params"])

                await db.commit()

                # Signal completion to all waiters
                for operation in batch:
                    if operation.get("future"):
                        operation["future"].set_result(True)

            except Exception as e:
                await db.rollback()
                for operation in batch:
                    if operation.get("future"):
                        operation["future"].set_exception(e)

    async def write(self, sql: str, params: tuple = ()) -> None:
        """Queue a write operation."""
        future = asyncio.get_event_loop().create_future()
        await self._write_queue.put({
            "type": "execute",
            "sql": sql,
            "params": params,
            "future": future
        })
        await future

    async def write_many(self, sql: str, params_list: list[tuple]) -> None:
        """Queue a batch write operation."""
        future = asyncio.get_event_loop().create_future()
        await self._write_queue.put({
            "type": "executemany",
            "sql": sql,
            "params": params_list,
            "future": future
        })
        await future

    @asynccontextmanager
    async def read_connection(self):
        """Get a read connection (can be used concurrently)."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def read_one(self, sql: str, params: tuple = ()):
        """Execute a read query and return one row."""
        async with self.read_connection() as conn:
            async with conn.execute(sql, params) as cursor:
                return await cursor.fetchone()

    async def read_all(self, sql: str, params: tuple = ()):
        """Execute a read query and return all rows."""
        async with self.read_connection() as conn:
            async with conn.execute(sql, params) as cursor:
                return await cursor.fetchall()

    async def close(self):
        """Shutdown database cleanly."""
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass

        # Process any remaining writes
        while not self._write_queue.empty():
            batch = []
            while not self._write_queue.empty():
                batch.append(await self._write_queue.get())
            if batch:
                await self._process_batch(batch)


SCHEMA_SQL = """
-- Core tables
CREATE TABLE IF NOT EXISTS eval_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    config_json TEXT,
    preset_name TEXT,
    random_seed INTEGER,
    status TEXT,
    budget_limit REAL,
    cost_spent REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES eval_runs(run_id),
    source_task_id TEXT,
    onetsoc_code TEXT,
    occupation_title TEXT,
    job_zone INTEGER,
    soc_major_code TEXT,
    naics_code TEXT,
    writing_category TEXT,
    formality_level INTEGER,
    writer_generation TEXT,
    company_size TEXT,
    company_name TEXT,
    urgency_level TEXT,
    emotional_context TEXT,
    is_sensitive_topic BOOLEAN,
    sensitive_topic_category TEXT,
    is_revision_task BOOLEAN,
    has_competing_objectives BOOLEAN,
    prompt_text TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS responses (
    response_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    model_name TEXT,
    model_version TEXT,  -- ADDED: exact model version from API
    model_tier TEXT,
    response_text TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    finish_reason TEXT,
    is_failure BOOLEAN,
    failure_category TEXT,
    word_count INTEGER,
    char_count INTEGER,
    cost_usd REAL,  -- ADDED: actual cost for this response
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id TEXT PRIMARY KEY,
    prompt_id TEXT REFERENCES prompts(prompt_id),
    gemini_response_id TEXT REFERENCES responses(response_id),
    competitor_response_id TEXT REFERENCES responses(response_id),
    competitor_model TEXT,
    final_winner TEXT,
    gemini_auto_loss BOOLEAN,
    competitor_auto_loss BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS judgments (
    judgment_id TEXT PRIMARY KEY,
    comparison_id TEXT REFERENCES comparisons(comparison_id),
    judge_model TEXT,
    judge_model_version TEXT,  -- ADDED
    judge_persona TEXT,
    vote_number INTEGER,
    presentation_order TEXT,
    raw_judgment TEXT,
    winner TEXT,
    judge_response_text TEXT,
    latency_ms INTEGER,
    cost_usd REAL,  -- ADDED
    created_at TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prompts_run ON prompts(run_id);
CREATE INDEX IF NOT EXISTS idx_prompts_occupation ON prompts(onetsoc_code);
CREATE INDEX IF NOT EXISTS idx_responses_prompt ON responses(prompt_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_prompt ON comparisons(prompt_id);
CREATE INDEX IF NOT EXISTS idx_judgments_comparison ON judgments(comparison_id);
"""
```

---

## 7. Budget Enforcement and Cost Tracking (NEW)

A critical missing piece in the draft plan. The system must allow users to set hard budget limits:

```python
# config/budget.py

"""
Budget management and cost tracking.

Provides:
1. Pre-run cost estimates
2. Hard budget limits that halt evaluation
3. Real-time cost tracking during runs
"""

from dataclasses import dataclass, field
from datetime import datetime
import asyncio

@dataclass
class BudgetConfig:
    """Budget configuration for an evaluation run."""
    soft_limit_usd: float | None = None  # Warning threshold
    hard_limit_usd: float | None = None  # Halt threshold
    alert_at_percent: float = 80  # Alert when reaching this % of limit

@dataclass
class CostAccumulator:
    """Thread-safe cost accumulator with budget enforcement."""
    budget: BudgetConfig
    total_spent: float = 0.0
    response_generation_cost: float = 0.0
    judging_cost: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _halt_requested: bool = False
    _alert_issued: bool = False

    async def add_cost(self, amount: float, category: str = "general") -> CostStatus:
        """
        Add cost and check against budget limits.

        Returns status indicating if evaluation should continue.
        """
        async with self._lock:
            self.total_spent += amount

            if category == "response":
                self.response_generation_cost += amount
            elif category == "judging":
                self.judging_cost += amount

            # Check hard limit
            if self.budget.hard_limit_usd:
                if self.total_spent >= self.budget.hard_limit_usd:
                    self._halt_requested = True
                    return CostStatus(
                        should_halt=True,
                        reason=f"Hard budget limit ${self.budget.hard_limit_usd:.2f} reached",
                        total_spent=self.total_spent
                    )

            # Check soft limit for alert
            if self.budget.soft_limit_usd and not self._alert_issued:
                alert_threshold = self.budget.soft_limit_usd * (self.budget.alert_at_percent / 100)
                if self.total_spent >= alert_threshold:
                    self._alert_issued = True
                    return CostStatus(
                        should_halt=False,
                        alert=f"Approaching budget limit: ${self.total_spent:.2f} of ${self.budget.soft_limit_usd:.2f}",
                        total_spent=self.total_spent
                    )

            return CostStatus(should_halt=False, total_spent=self.total_spent)

    @property
    def should_halt(self) -> bool:
        return self._halt_requested

    def get_summary(self) -> dict:
        return {
            "total_spent_usd": self.total_spent,
            "response_generation_usd": self.response_generation_cost,
            "judging_usd": self.judging_cost,
            "budget_remaining_usd": (
                self.budget.hard_limit_usd - self.total_spent
                if self.budget.hard_limit_usd else None
            )
        }

@dataclass
class CostStatus:
    should_halt: bool
    total_spent: float
    reason: str | None = None
    alert: str | None = None
```

---

## 8. Sensitive Topic Classification (NEW)

Proactive detection during prompt generation, not just reactive handling of refusals:

```python
# data/sensitive_topics.py

"""
Sensitive topic classification for writing prompts.

Identifies prompts involving sensitive workplace situations that:
1. May trigger model refusals
2. Should be tracked separately in analysis
3. Require careful handling
"""

from enum import Enum
from dataclasses import dataclass
import re

class SensitiveCategory(Enum):
    HR_PERFORMANCE = "hr_performance"        # Performance issues, PIPs
    HR_TERMINATION = "hr_termination"        # Firing, layoffs
    HR_COMPLAINT = "hr_complaint"            # Harassment, discrimination
    LEGAL_CONTRACT = "legal_contract"        # Contract disputes
    LEGAL_LIABILITY = "legal_liability"      # Legal risk, liability
    LEGAL_COMPLIANCE = "legal_compliance"    # Regulatory compliance
    BAD_NEWS = "bad_news"                    # Project cancellation, rejection
    CONFIDENTIAL = "confidential"            # Financial results, M&A
    CONFLICT = "conflict"                    # Disputes, negotiations
    HEALTH_MEDICAL = "health_medical"        # Medical information
    NONE = "none"

@dataclass
class SensitivityAnalysis:
    is_sensitive: bool
    categories: list[SensitiveCategory]
    confidence: float
    reasoning: str

class SensitiveTopicClassifier:
    """
    Classify prompts for sensitive topics.

    Uses pattern matching for efficiency, with optional LLM verification
    for ambiguous cases.
    """

    PATTERNS = {
        SensitiveCategory.HR_PERFORMANCE: [
            r'\bperformance\s+(review|improvement|issue|problem)\b',
            r'\bPIP\b',
            r'\bunderperform',
            r'\b(written|verbal)\s+warning\b',
            r'\bfailing\s+to\s+meet\b',
            r'\bpoor\s+performance\b',
        ],
        SensitiveCategory.HR_TERMINATION: [
            r'\b(terminat|fire|dismiss|let\s+go|layoff|laid\s+off)\b',
            r'\bseverance\b',
            r'\bend\s+(of\s+)?employment\b',
            r'\breduction\s+in\s+force\b',
            r'\bRIF\b',
        ],
        SensitiveCategory.HR_COMPLAINT: [
            r'\b(harass|discriminat|hostile\s+work)\b',
            r'\bEEO\b',
            r'\b(sexual|racial|age)\s+(harass|discriminat)\b',
            r'\bwhistleblow',
            r'\bretaliat',
        ],
        SensitiveCategory.LEGAL_CONTRACT: [
            r'\bbreach\s+of\s+contract\b',
            r'\bcontract\s+dispute\b',
            r'\bnon-?compete\b',
            r'\bNDA\s+violation\b',
        ],
        SensitiveCategory.LEGAL_LIABILITY: [
            r'\bliab(le|ility)\b',
            r'\blitigat',
            r'\blawsuit\b',
            r'\blegal\s+action\b',
            r'\bdefamation\b',
        ],
        SensitiveCategory.LEGAL_COMPLIANCE: [
            r'\b(compliance|regulatory)\s+(violation|issue|breach)\b',
            r'\baudit\s+finding\b',
            r'\bSOX\b',
            r'\bHIPAA\b',
            r'\bGDPR\b',
        ],
        SensitiveCategory.BAD_NEWS: [
            r'\bcancel(led|ing)?\s+(project|contract|deal)\b',
            r'\breject(ed|ing)?\s+(proposal|application|candidate)\b',
            r'\bdeny\s+(request|application)\b',
            r'\bbad\s+news\b',
            r'\bunfortunately\b.*\b(cannot|unable|regret)\b',
        ],
        SensitiveCategory.CONFIDENTIAL: [
            r'\bconfidential\b',
            r'\bM&A\b',
            r'\bmerger\b',
            r'\bacquisition\b',
            r'\bpre-?announcement\b',
            r'\bearnings\b.*\b(unreleased|embargo)\b',
            r'\binsider\b',
        ],
        SensitiveCategory.CONFLICT: [
            r'\bdispute\b',
            r'\bconflict\s+(with|between)\b',
            r'\bgrievance\b',
            r'\bescalat',
            r'\bconfrontation\b',
        ],
        SensitiveCategory.HEALTH_MEDICAL: [
            r'\bmedical\s+(condition|leave|information)\b',
            r'\bFMLA\b',
            r'\bdisability\b',
            r'\bmental\s+health\b',
            r'\bpregnancy\b',
        ],
    }

    def __init__(self):
        # Compile patterns for efficiency
        self._compiled_patterns = {
            category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for category, patterns in self.PATTERNS.items()
        }

    def classify(self, prompt_text: str, task_statement: str = "") -> SensitivityAnalysis:
        """
        Classify a prompt for sensitive topics.

        Checks both the generated prompt and the original task statement.
        """
        full_text = f"{prompt_text} {task_statement}"

        matched_categories = []
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(full_text):
                    matched_categories.append(category)
                    break  # One match per category is enough

        if matched_categories:
            return SensitivityAnalysis(
                is_sensitive=True,
                categories=matched_categories,
                confidence=0.8 if len(matched_categories) > 1 else 0.6,
                reasoning=f"Matched patterns for: {[c.value for c in matched_categories]}"
            )

        return SensitivityAnalysis(
            is_sensitive=False,
            categories=[SensitiveCategory.NONE],
            confidence=0.7,
            reasoning="No sensitive patterns detected"
        )

    async def verify_with_llm(self,
                               prompt_text: str,
                               api_client,
                               preliminary: SensitivityAnalysis) -> SensitivityAnalysis:
        """
        Optional LLM verification for ambiguous cases.

        Only call this for edge cases where pattern matching is uncertain.
        """
        if preliminary.confidence > 0.75:
            return preliminary

        # Use fast model for classification
        response = await api_client.complete(
            model="gemini-3-flash",
            prompt=f"""Classify this writing prompt for sensitive workplace topics.

Prompt:
{prompt_text}

Is this about: HR issues (performance, termination, complaints), legal matters,
bad news delivery, confidential information, workplace conflict, or health/medical?

Reply with a JSON object: {{"is_sensitive": bool, "categories": ["category1", ...], "reasoning": "brief explanation"}}"""
        )

        # Parse response and merge with pattern results
        # ...
        pass
```

---

## 9. Connection Pool and Circuit Breaker (NEW)

Proper management of concurrent API connections:

```python
# api/connection_pool.py

"""
Connection pool management for OpenRouter API.

Manages:
1. Maximum concurrent connections
2. Connection reuse
3. Health monitoring
"""

import asyncio
from dataclasses import dataclass
from collections import deque
import httpx

@dataclass
class ConnectionPoolConfig:
    max_connections: int = 10
    max_connections_per_host: int = 10
    connection_timeout: float = 30.0
    read_timeout: float = 120.0
    keepalive_expiry: float = 30.0

class ConnectionPool:
    """
    Manages a pool of HTTP connections to OpenRouter.

    Uses httpx connection pooling with semaphore-based concurrency control.
    """

    def __init__(self, config: ConnectionPoolConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_connections)
        self._client: httpx.AsyncClient | None = None

    async def initialize(self, api_key: str):
        """Initialize the connection pool."""
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "gemini-writing-eval",
                "X-Title": "Gemini Writing Evaluation Framework",
            },
            timeout=httpx.Timeout(
                connect=self.config.connection_timeout,
                read=self.config.read_timeout,
                write=30.0,
                pool=30.0
            ),
            limits=httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_connections_per_host,
                keepalive_expiry=self.config.keepalive_expiry
            )
        )

    async def request(self, method: str, path: str, **kwargs):
        """Make a request with connection pool management."""
        async with self._semaphore:
            return await self._client.request(method, path, **kwargs)

    async def close(self):
        """Close all connections."""
        if self._client:
            await self._client.aclose()


# api/circuit_breaker.py

"""
Circuit breaker for API failure handling.

Prevents cascading failures by temporarily stopping requests
when error rates are too high.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 3      # Successes to close from half-open
    timeout_seconds: float = 60.0   # Time before trying half-open
    window_seconds: float = 60.0    # Window for counting failures

class CircuitBreaker:
    """
    Circuit breaker implementation for API resilience.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, reject all requests immediately
    - HALF_OPEN: Testing if service recovered, allow limited requests
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._opened_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker.

        Raises CircuitOpenError if circuit is open.
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit {self.name} is open, retry after "
                        f"{self._time_until_retry():.1f}s"
                    )

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = max(0, self._failure_count - 1)

    async def _on_failure(self, error: Exception):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self.state = CircuitState.OPEN
                self._opened_at = datetime.now()
            elif self.state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self._opened_at = datetime.now()

    def _should_attempt_reset(self) -> bool:
        if not self._opened_at:
            return True
        elapsed = (datetime.now() - self._opened_at).total_seconds()
        return elapsed >= self.config.timeout_seconds

    def _time_until_retry(self) -> float:
        if not self._opened_at:
            return 0
        elapsed = (datetime.now() - self._opened_at).total_seconds()
        return max(0, self.config.timeout_seconds - elapsed)

class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
```

---

## 10. Temporal Context Generation (IMPROVED)

Consistent date/deadline generation:

```python
# prompts/temporal.py

"""
Temporal context generation for writing prompts.

Generates realistic dates, deadlines, and time-sensitive context
that is consistent with the evaluation date.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import random

class TemporalRelevance(Enum):
    NONE = "none"                    # No temporal context needed
    DATE_AWARE = "date_aware"        # Just needs current date
    DEADLINE_DRIVEN = "deadline"     # Has specific deadline
    EVENT_REFERENCED = "event"       # References recent/upcoming event
    QUARTERLY = "quarterly"          # Quarter-end related
    ANNUAL = "annual"                # Year-end related

@dataclass
class TemporalContext:
    relevance: TemporalRelevance
    current_date: datetime
    deadline: datetime | None = None
    deadline_description: str | None = None
    recent_event: str | None = None
    upcoming_event: str | None = None
    quarter: str | None = None  # "Q1 2026"
    fiscal_context: str | None = None

class TemporalContextGenerator:
    """
    Generate realistic temporal context for prompts.

    Uses the evaluation date as the reference point to ensure
    all generated dates are plausible.
    """

    def __init__(self, evaluation_date: datetime):
        self.eval_date = evaluation_date

    def generate(self,
                 task_statement: str,
                 urgency_level: str,
                 rng) -> TemporalContext:
        """
        Generate appropriate temporal context based on task and urgency.
        """
        relevance = self._determine_relevance(task_statement, urgency_level)

        if relevance == TemporalRelevance.NONE:
            return TemporalContext(
                relevance=relevance,
                current_date=self.eval_date
            )

        context = TemporalContext(
            relevance=relevance,
            current_date=self.eval_date,
            quarter=self._get_quarter_string()
        )

        if relevance == TemporalRelevance.DEADLINE_DRIVEN:
            context.deadline, context.deadline_description = self._generate_deadline(
                urgency_level, rng
            )

        if relevance == TemporalRelevance.EVENT_REFERENCED:
            context.recent_event, context.upcoming_event = self._generate_events(
                task_statement, rng
            )

        if relevance in [TemporalRelevance.QUARTERLY, TemporalRelevance.ANNUAL]:
            context.fiscal_context = self._generate_fiscal_context(relevance)

        return context

    def _determine_relevance(self, task: str, urgency: str) -> TemporalRelevance:
        """Determine what type of temporal context is appropriate."""
        task_lower = task.lower()

        # Quarterly/annual patterns
        if any(word in task_lower for word in ['quarterly', 'q1', 'q2', 'q3', 'q4']):
            return TemporalRelevance.QUARTERLY
        if any(word in task_lower for word in ['annual', 'year-end', 'fiscal year']):
            return TemporalRelevance.ANNUAL

        # Deadline patterns
        if any(word in task_lower for word in ['deadline', 'due', 'by friday', 'urgent']):
            return TemporalRelevance.DEADLINE_DRIVEN
        if urgency in ['urgent', 'critical']:
            return TemporalRelevance.DEADLINE_DRIVEN

        # Event patterns
        if any(word in task_lower for word in ['meeting', 'conference', 'presentation']):
            return TemporalRelevance.EVENT_REFERENCED
        if 'following' in task_lower or 'after' in task_lower:
            return TemporalRelevance.EVENT_REFERENCED

        # Some tasks just need date awareness
        if any(word in task_lower for word in ['schedule', 'plan', 'upcoming']):
            return TemporalRelevance.DATE_AWARE

        return TemporalRelevance.NONE

    def _generate_deadline(self, urgency: str, rng) -> tuple[datetime, str]:
        """Generate a realistic deadline based on urgency."""
        if urgency == 'critical':
            days = rng.choice([0, 1])  # Today or tomorrow
            descriptions = ["end of day today", "tomorrow morning", "by close of business"]
        elif urgency == 'urgent':
            days = rng.choice([1, 2, 3])
            descriptions = ["by Friday", "this week", "in the next few days"]
        elif urgency == 'important':
            days = rng.choice([5, 7, 10, 14])
            descriptions = ["next week", "by the 15th", "within two weeks"]
        else:
            days = rng.choice([14, 21, 30])
            descriptions = ["by end of month", "in the next few weeks", "by the 1st"]

        deadline = self.eval_date + timedelta(days=days)
        description = rng.choice(descriptions)

        return deadline, description

    def _generate_events(self, task: str, rng) -> tuple[str | None, str | None]:
        """Generate recent and upcoming events for context."""
        recent_events = [
            "last week's team meeting",
            "the quarterly review",
            "yesterday's client call",
            "the recent announcement",
            "our conversation earlier this week",
            "the project kickoff",
        ]

        upcoming_events = [
            "the board meeting on Friday",
            "next week's conference",
            "the upcoming product launch",
            "tomorrow's presentation",
            "the client visit next month",
        ]

        recent = rng.choice(recent_events) if rng.random() > 0.3 else None
        upcoming = rng.choice(upcoming_events) if rng.random() > 0.3 else None

        return recent, upcoming

    def _get_quarter_string(self) -> str:
        """Get current quarter string."""
        quarter = (self.eval_date.month - 1) // 3 + 1
        return f"Q{quarter} {self.eval_date.year}"

    def _generate_fiscal_context(self, relevance: TemporalRelevance) -> str:
        """Generate fiscal/quarterly context."""
        quarter = (self.eval_date.month - 1) // 3 + 1
        year = self.eval_date.year

        if relevance == TemporalRelevance.QUARTERLY:
            return f"We're approaching the end of Q{quarter} {year}"
        else:  # ANNUAL
            return f"As we approach fiscal year-end {year}"

    def format_for_prompt(self, context: TemporalContext) -> str:
        """Format temporal context for inclusion in prompt."""
        if context.relevance == TemporalRelevance.NONE:
            return ""

        parts = []

        # Current date
        date_str = context.current_date.strftime("%A, %B %d, %Y")
        parts.append(f"Today is {date_str}.")

        # Quarter context
        if context.quarter and context.relevance in [
            TemporalRelevance.QUARTERLY, TemporalRelevance.ANNUAL
        ]:
            parts.append(context.fiscal_context)

        # Deadline
        if context.deadline and context.deadline_description:
            parts.append(f"This needs to be completed {context.deadline_description}.")

        # Events
        if context.recent_event:
            parts.append(f"Following {context.recent_event},")
        if context.upcoming_event:
            parts.append(f"In preparation for {context.upcoming_event},")

        return " ".join(parts)
```

---

## 11. Prompt Validation (NEW)

Validate prompts before evaluation begins:

```python
# prompts/validation.py

"""
Prompt validation to ensure quality before evaluation.

Validates:
1. Prompt completeness (all required fields)
2. Diversity requirements met
3. No obvious issues that would cause failures
"""

from dataclasses import dataclass
from collections import Counter

@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    diversity_scores: dict[str, float]

class PromptValidator:
    """
    Validate a set of prompts before evaluation.
    """

    REQUIRED_FIELDS = [
        'prompt_id', 'onetsoc_code', 'occupation_title', 'naics_code',
        'writer', 'recipients', 'generated_prompt_text'
    ]

    DIVERSITY_DIMENSIONS = [
        'job_zone', 'soc_major_code', 'naics_code', 'formality_level',
        'writer_generation', 'company_size', 'urgency_level', 'emotional_context'
    ]

    def validate_prompts(self, prompts: list) -> ValidationResult:
        """Validate a complete set of prompts."""
        errors = []
        warnings = []
        diversity_scores = {}

        # Check completeness
        for i, prompt in enumerate(prompts):
            field_errors = self._check_required_fields(prompt, i)
            errors.extend(field_errors)

        # Check diversity
        diversity_scores = self._compute_diversity_scores(prompts)

        for dimension, score in diversity_scores.items():
            if score < 0.3:
                errors.append(f"Poor diversity on {dimension}: {score:.2f}")
            elif score < 0.5:
                warnings.append(f"Low diversity on {dimension}: {score:.2f}")

        # Check for problematic patterns
        pattern_warnings = self._check_patterns(prompts)
        warnings.extend(pattern_warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            diversity_scores=diversity_scores
        )

    def _check_required_fields(self, prompt, index: int) -> list[str]:
        """Check that all required fields are present."""
        errors = []
        for field in self.REQUIRED_FIELDS:
            if not hasattr(prompt, field) or getattr(prompt, field) is None:
                errors.append(f"Prompt {index}: missing required field '{field}'")
        return errors

    def _compute_diversity_scores(self, prompts: list) -> dict[str, float]:
        """
        Compute diversity scores for each dimension.

        Uses normalized entropy: 1.0 = perfectly uniform, 0.0 = all same value
        """
        import math

        scores = {}

        for dimension in self.DIVERSITY_DIMENSIONS:
            values = [getattr(p, dimension, None) for p in prompts]
            values = [v for v in values if v is not None]

            if not values:
                scores[dimension] = 0.0
                continue

            counter = Counter(values)
            n = len(values)
            k = len(counter)

            if k == 1:
                scores[dimension] = 0.0
            else:
                # Normalized entropy
                entropy = -sum((c/n) * math.log2(c/n) for c in counter.values())
                max_entropy = math.log2(k)
                scores[dimension] = entropy / max_entropy if max_entropy > 0 else 0

        return scores

    def _check_patterns(self, prompts: list) -> list[str]:
        """Check for problematic patterns in prompts."""
        warnings = []

        # Check for duplicate prompts
        prompt_texts = [p.generated_prompt_text for p in prompts]
        if len(prompt_texts) != len(set(prompt_texts)):
            warnings.append("Found duplicate prompt texts")

        # Check for very short prompts
        short_prompts = sum(1 for p in prompts if len(p.generated_prompt_text) < 100)
        if short_prompts > len(prompts) * 0.1:
            warnings.append(f"{short_prompts} prompts are very short (<100 chars)")

        # Check for very long prompts
        long_prompts = sum(1 for p in prompts if len(p.generated_prompt_text) > 5000)
        if long_prompts > len(prompts) * 0.1:
            warnings.append(f"{long_prompts} prompts are very long (>5000 chars)")

        return warnings
```

---

## 12. Implementation Phases (IMPROVED)

### Phase 1: Core Infrastructure (Week 1-2)

**Priority: Get a minimal working evaluation running**

1. **OpenRouter API client** with verified model IDs
   - Connection pool with concurrency limits
   - Retry with exponential backoff
   - Circuit breaker for resilience
   - Model verification at startup

2. **SQLite database** with WAL mode
   - Write coalescing for performance
   - Complete schema with cost tracking

3. **Basic CLI** with preset support
   - Cost estimation before run
   - Dry-run mode

4. **Checkpoint system**
   - Save/resume functionality
   - Graceful shutdown handling

### Phase 2: Prompt Generation (Week 2-3)

1. **O*NET extraction** with writing task classification
2. **NAICS mapping** with embedded BLS data
3. **Company database** with 500+ companies
4. **Name generator** with demographic diversity
5. **Temporal context** generation
6. **Sensitive topic** classification
7. **Prompt validation** before evaluation

### Phase 3: Evaluation Pipeline (Week 3-4)

1. **Response generation** with parallel execution
2. **Dual-persona judging** implementation
3. **Majority-of-majorities** aggregation
4. **Position bias** mitigation
5. **Failure categorization**
6. **Budget enforcement**

### Phase 4: Analysis & Reporting (Week 4-5)

1. **Statistical analysis** with confidence intervals
2. **Bias detection** (position, length, model)
3. **Weakness identification**
4. **PDF report generation**
5. **Chart generation**

### Phase 5: TUI & Polish (Week 5-6)

1. **Progress dashboard** with real-time updates
2. **Results viewer** with filtering
3. **Error state handling**
4. **Cross-run comparison**

---

## 13. Risk Mitigation (IMPROVED)

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenRouter model names change | High | Verify at startup, fail fast with clear error |
| Rate limits vary by model | Medium | Adaptive rate limiting, per-model limits |
| API outages | High | Circuit breaker, automatic retry, checkpoint |
| SQLite write contention | Medium | WAL mode, single writer, batch commits |
| Token estimation inaccuracy | Medium | Calibration phase, conservative estimates |
| Budget overrun | High | Hard limits, real-time cost tracking, alerts |

### Methodological Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Prompt generation bias | High | Use ensemble of models, track which generated |
| Judge model self-bias | High | Weight non-Gemini judges, detect/report bias |
| Sensitive topic refusals | Medium | Proactive classification, separate tracking |
| Uneven diversity | Medium | Validation before run, stratified sampling |

---

## 14. Success Criteria (IMPROVED)

1. **Functional**: Complete end-to-end evaluation with preset 3 (50 prompts) succeeds
2. **Robust**: System recovers from API failures, can resume after interruption
3. **Trustworthy**: Statistical methodology verified, bias detection working
4. **Usable**: Clear TUI, informative progress, actionable reports
5. **Reproducible**: Same seed + config produces identical prompts
6. **Cost-controlled**: Budget limits enforced, costs tracked accurately

---

## 15. Conclusion

This improved plan addresses the critical gaps in Draft Plan 3:

1. **Verified model identifiers** with startup verification
2. **Embedded NAICS mapping** data
3. **Comprehensive company database** structure
4. **Proper dual-persona judging** per PROMPT.md
5. **SQLite concurrency** handling
6. **Budget enforcement** with hard stops
7. **Sensitive topic classification** during generation
8. **Connection pooling** and circuit breakers
9. **Temporal context** generation
10. **Prompt validation** before evaluation

The plan is now more robust, complete, and implementable.
