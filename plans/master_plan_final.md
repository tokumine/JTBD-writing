# Final Master Plan: Gemini Writing Evaluation Framework

## Executive Summary

This final master plan synthesizes insights from 6 independent draft plans, their critiques, and 6 detailed implementation simulations to produce a comprehensive, production-ready specification for the Gemini Writing Evaluation Framework. All identified gaps, gotchas, and edge cases have been addressed. This plan contains 100% of the specification from PROMPT.md and is ready for implementation.

---

## 1. Technology Stack (Universal Agreement)

- **Python 3.11+** with asyncio for concurrent API operations
- **httpx** for async HTTP client (superior to requests)
- **pydantic v2** for data validation and schemas
- **SQLite** for persistent storage (via aiosqlite for async)
- **textual/rich** for TUI progress dashboard and results viewer
- **plotly** for chart generation
- **reportlab** for PDF report generation (chosen over weasyprint for fewer system dependencies)
- **typer** for CLI interface
- **scipy** for statistical analysis (binomtest, chi2, etc.)

---

## 2. Project Structure (Complete)

```
gemini-writing-eval/
├── pyproject.toml                 # Project configuration with dependencies
├── README.md
├── .env.example                   # OPENROUTER_API_KEY=your_key_here
├── .gitignore                     # Exclude results/, .env, __pycache__/, etc.
│
├── src/
│   ├── __init__.py
│   ├── cli.py                     # Main CLI with all commands
│   ├── exceptions.py              # Custom exception classes
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # EvalConfig, JudgeConfig, etc.
│   │   ├── presets.py             # 10 preset configurations (COMPLETE)
│   │   └── cost_estimator.py      # Live cost & time estimates (COMPLETE)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── onet_extractor.py      # Reads ONET_WRITING_REFERENCE.md (COMPLETE)
│   │   ├── naics_mapper.py        # Industry code mapping (COMPLETE)
│   │   ├── company_database.py    # 500+ real companies (COMPLETE)
│   │   ├── name_generator.py      # Census-based diverse names (COMPLETE)
│   │   └── diversity_tracker.py   # Track coverage across dimensions
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── schemas.py             # WritingPrompt, RecipientPersona, etc.
│   │   ├── phase1_offline.py      # Offline LLM generation
│   │   ├── phase2_algorithmic.py  # Algorithmic combination
│   │   ├── phase3_enrichment.py   # LLM enrichment
│   │   ├── constraint_generator.py # Instruction-following constraints
│   │   ├── revision_generator.py  # Revision task generation
│   │   ├── ambiguity_generator.py # Deliberately vague prompts
│   │   ├── cc_generator.py        # CC/multiple recipient scenarios
│   │   └── prompt_builder.py      # Final prompt text assembly
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── openrouter_client.py   # Async HTTP client (COMPLETE)
│   │   ├── rate_limiter.py        # Per-model rate limiting (COMPLETE)
│   │   ├── circuit_breaker.py     # Circuit breaker pattern (COMPLETE)
│   │   └── token_counter.py       # Token estimation (COMPLETE)
│   │
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── engine.py              # Main evaluation orchestrator
│   │   ├── judge_prompt_builder.py # Judge prompt building (COMPLETE)
│   │   ├── judge_parser.py        # Parse judge responses (COMPLETE)
│   │   ├── vote_aggregator.py     # Majority-of-majorities (COMPLETE)
│   │   ├── compliance_tracker.py  # Instruction compliance (COMPLETE)
│   │   ├── refusal_classifier.py  # Refusal categorization (COMPLETE)
│   │   ├── response_analyzer.py   # Format/pattern detection (COMPLETE)
│   │   └── schemas.py             # JudgeVote, Comparison, etc.
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite with aiosqlite
│   │   ├── checkpoint.py          # Fine-grained checkpointing
│   │   ├── run_directory.py       # Full directory structure
│   │   └── failure_logger.py      # Structured failure logging
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── statistics.py          # Wilson CI, binomtest, effect sizes
│   │   ├── bias_detection.py      # Position, length, format, fingerprinting
│   │   ├── weakness_finder.py     # Systematic weakness identification (COMPLETE)
│   │   └── cross_run_compare.py   # Multi-run comparison
│   │
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── progress_dashboard.py  # Real-time progress TUI (COMPLETE)
│   │   ├── results_viewer.py      # Post-eval inspection TUI (COMPLETE)
│   │   └── components.py          # Reusable TUI widgets
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py       # Full PDF report (COMPLETE)
│   │   ├── charts.py              # Plotly visualizations (COMPLETE)
│   │   ├── heatmaps.py            # Dimension heatmaps (COMPLETE)
│   │   └── readme_generator.py    # Auto-generated README.md (COMPLETE)
│   │
│   └── validation/
│       ├── __init__.py
│       └── onet_schema.py         # O*NET data validation
│
├── db/
│   ├── onet.db                    # O*NET 30.1 SQLite database
│   └── ONET_WRITING_REFERENCE.md  # Pre-processed writing tasks
│
├── data/
│   ├── companies.json             # Company database (500+ companies)
│   ├── names_census.json          # Census-based names
│   ├── naics_crosswalk.json       # SOC to NAICS mapping
│   └── offline_variations/        # Phase 1 pre-generated variations
│
├── results/
│   └── .gitkeep
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    ├── unit/
    └── integration/
```

---

## 3. ONET_WRITING_REFERENCE.md Schema (CRITICAL - Previously Missing)

The simulations identified this as a critical gap. The reference file must have this schema:

```json
{
  "version": "30.1",
  "generated_date": "2026-01-06",
  "tasks": [
    {
      "task_id": "11-1011.00-T1",
      "onetsoc_code": "11-1011.00",
      "occupation_title": "Chief Executives",
      "task_statement": "Draft correspondence for executive review",
      "job_zone": 5,
      "writing_relevance_score": 0.95,
      "writing_context": "Executive-level formal correspondence requiring strategic communication",
      "inferred_channel": "email"
    }
  ]
}
```

**Parser Implementation:**

```python
# src/data/onet_extractor.py

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
import json
import aiosqlite

@dataclass
class ONetTask:
    """O*NET task with writing relevance."""
    task_id: str
    onetsoc_code: str
    occupation_title: str
    task_statement: str
    job_zone: int
    writing_relevance_score: float
    writing_context: str
    inferred_channel: Optional[str] = None

class ONetExtractor:
    """Extract writing-relevant tasks from O*NET."""

    def __init__(self, onet_db_path: Path, reference_path: Path):
        self.db_path = onet_db_path
        self.reference_path = reference_path
        self._reference_data: Optional[Dict] = None

    async def load_reference(self) -> None:
        """Load and parse ONET_WRITING_REFERENCE.md."""
        if not self.reference_path.exists():
            raise FileNotFoundError(
                f"ONET_WRITING_REFERENCE.md not found at {self.reference_path}. "
                "This file must be created by pre-processing O*NET data."
            )

        content = self.reference_path.read_text()

        # Handle both JSON and markdown formats
        if content.strip().startswith('{'):
            self._reference_data = json.loads(content)
        else:
            # Parse markdown format - extract JSON block
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                self._reference_data = json.loads(json_match.group(1))
            else:
                raise ValueError(
                    "ONET_WRITING_REFERENCE.md must contain JSON data "
                    "(either raw JSON or in a ```json block)"
                )

    async def get_writing_tasks(
        self,
        min_relevance_score: float = 0.5,
        job_zones: Optional[List[int]] = None,
        occupation_codes: Optional[List[str]] = None
    ) -> List[ONetTask]:
        """Get all writing-relevant tasks with optional filters."""
        if self._reference_data is None:
            await self.load_reference()

        tasks = []
        for task_data in self._reference_data["tasks"]:
            # Apply relevance filter
            if task_data["writing_relevance_score"] < min_relevance_score:
                continue

            # Apply job zone filter
            if job_zones and task_data["job_zone"] not in job_zones:
                continue

            # Apply occupation filter (supports wildcards like "11-*")
            if occupation_codes:
                matches = False
                for code in occupation_codes:
                    if code.endswith("*"):
                        if task_data["onetsoc_code"].startswith(code[:-1]):
                            matches = True
                            break
                    elif task_data["onetsoc_code"] == code:
                        matches = True
                        break
                if not matches:
                    continue

            tasks.append(ONetTask(
                task_id=task_data["task_id"],
                onetsoc_code=task_data["onetsoc_code"],
                occupation_title=task_data["occupation_title"],
                task_statement=task_data["task_statement"],
                job_zone=task_data["job_zone"],
                writing_relevance_score=task_data["writing_relevance_score"],
                writing_context=task_data["writing_context"],
                inferred_channel=task_data.get("inferred_channel")
            ))

        return tasks

    async def verify_onet_schema(self) -> bool:
        """Verify O*NET database has expected tables."""
        required_tables = ['task_statements', 'occupation_data', 'job_zones']

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}

        missing = set(required_tables) - tables
        if missing:
            raise ValueError(f"O*NET database missing tables: {missing}")

        return True
```

---

## 4. OpenRouter API Client (Complete Implementation)

The simulations identified the missing API client as critical. Here is the complete implementation:

```python
# src/api/openrouter_client.py

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import httpx

from .rate_limiter import RateLimiter
from .circuit_breaker import CircuitBreaker
from ..exceptions import APIError, RateLimitError, CircuitOpenError

@dataclass
class CompletionResponse:
    """Response from OpenRouter API."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost: float
    finish_reason: str
    raw_response: Dict[str, Any] = field(repr=False)

class OpenRouterClient:
    """Async client for OpenRouter API with rate limiting and circuit breaker."""

    BASE_URL = "https://openrouter.ai/api/v1"

    # Model-specific rate limits (requests per minute, tokens per minute)
    # These are conservative estimates - actual limits may be higher
    MODEL_RATE_LIMITS = {
        "google/gemini-3.0-pro": {"rpm": 60, "tpm": 100000},
        "google/gemini-3.0-flash": {"rpm": 100, "tpm": 200000},
        "openai/gpt-5.2": {"rpm": 50, "tpm": 80000},
        "openai/gpt-4.1": {"rpm": 80, "tpm": 150000},
        "anthropic/claude-opus-4.5": {"rpm": 40, "tpm": 60000},
        "anthropic/claude-sonnet-4": {"rpm": 60, "tpm": 100000},
    }

    DEFAULT_RATE_LIMIT = {"rpm": 30, "tpm": 50000}

    def __init__(
        self,
        api_key: str,
        timeout: float = 120.0,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0
    ):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://gemini-writing-eval.example.com",
                "X-Title": "Gemini Writing Evaluation Framework"
            },
            timeout=timeout
        )

        # Per-model rate limiters
        self.rate_limiters: Dict[str, RateLimiter] = {}

        # Per-model circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.circuit_threshold = circuit_breaker_threshold
        self.circuit_timeout = circuit_breaker_timeout

    def _get_rate_limiter(self, model: str) -> RateLimiter:
        """Get or create rate limiter for model."""
        if model not in self.rate_limiters:
            # Find matching rate limit config
            limits = self.DEFAULT_RATE_LIMIT
            for pattern, config in self.MODEL_RATE_LIMITS.items():
                if model.startswith(pattern) or pattern in model:
                    limits = config
                    break

            self.rate_limiters[model] = RateLimiter(
                requests_per_minute=limits["rpm"],
                tokens_per_minute=limits["tpm"]
            )
        return self.rate_limiters[model]

    def _get_circuit_breaker(self, model: str) -> CircuitBreaker:
        """Get or create circuit breaker for model."""
        if model not in self.circuit_breakers:
            self.circuit_breakers[model] = CircuitBreaker(
                failure_threshold=self.circuit_threshold,
                recovery_timeout=self.circuit_timeout
            )
        return self.circuit_breakers[model]

    async def complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResponse:
        """Make a completion request with rate limiting and circuit breaker."""

        # Check circuit breaker
        circuit = self._get_circuit_breaker(model)
        if not circuit.allow_request():
            raise CircuitOpenError(f"Circuit breaker open for model {model}")

        # Estimate tokens for rate limiting
        estimated_tokens = self._estimate_tokens(messages)

        # Acquire rate limit
        rate_limiter = self._get_rate_limiter(model)
        await rate_limiter.acquire(estimated_tokens)

        # Prepare request
        request_body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            request_body["max_tokens"] = max_tokens

        # Execute with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.perf_counter()

                response = await self.client.post(
                    "/chat/completions",
                    json=request_body
                )

                latency_ms = (time.perf_counter() - start_time) * 1000

                # Handle rate limit response
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                    continue

                # Handle other errors
                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    raise APIError(
                        f"OpenRouter API error: {response.status_code}",
                        status_code=response.status_code,
                        response=error_data
                    )

                data = response.json()

                # Mark circuit breaker success
                circuit.record_success()

                # Parse response
                choice = data["choices"][0]
                usage = data.get("usage", {})

                return CompletionResponse(
                    content=choice["message"]["content"],
                    model=data["model"],
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    latency_ms=latency_ms,
                    cost=self._calculate_cost(model, usage),
                    finish_reason=choice.get("finish_reason", "unknown"),
                    raw_response=data
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                circuit.record_failure()

                # Exponential backoff with jitter
                delay = min(2 ** attempt + (asyncio.get_event_loop().time() % 1), 60)
                await asyncio.sleep(delay)

        raise APIError(f"Failed after {self.max_retries} retries: {last_error}")

    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Rough token estimation (4 chars per token average)."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4 + 50  # Add overhead for message structure

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate cost based on model pricing."""
        # Pricing per 1M tokens (as of Jan 2026 - verify actual prices)
        PRICING = {
            "google/gemini-3.0-pro": {"input": 1.25, "output": 5.00},
            "google/gemini-3.0-flash": {"input": 0.075, "output": 0.30},
            "openai/gpt-5.2": {"input": 15.00, "output": 60.00},
            "openai/gpt-4.1": {"input": 1.50, "output": 6.00},
            "anthropic/claude-opus-4.5": {"input": 15.00, "output": 75.00},
            "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
        }

        # Find matching pricing
        pricing = {"input": 10.0, "output": 30.0}  # Default
        for pattern, config in PRICING.items():
            if model.startswith(pattern) or pattern in model:
                pricing = config
                break

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return (input_tokens * pricing["input"] / 1_000_000 +
                output_tokens * pricing["output"] / 1_000_000)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def get_circuit_breaker_states(self) -> Dict[str, Dict]:
        """Get circuit breaker states for checkpointing."""
        return {
            model: cb.get_state()
            for model, cb in self.circuit_breakers.items()
        }

    def restore_circuit_breaker_states(self, states: Dict[str, Dict]):
        """Restore circuit breaker states from checkpoint."""
        for model, state in states.items():
            if model not in self.circuit_breakers:
                self.circuit_breakers[model] = CircuitBreaker(
                    failure_threshold=self.circuit_threshold,
                    recovery_timeout=self.circuit_timeout
                )
            self.circuit_breakers[model].restore_state(state)
```

```python
# src/api/rate_limiter.py

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

@dataclass
class RateLimiter:
    """Token bucket rate limiter with RPM and TPM limits."""

    requests_per_minute: int
    tokens_per_minute: int

    _request_times: deque = field(default_factory=deque)
    _token_times: deque = field(default_factory=deque)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self, estimated_tokens: int = 0) -> None:
        """Wait until rate limits allow a request."""
        async with self._lock:
            now = time.time()

            # Clean old entries
            cutoff = now - 60
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()
            while self._token_times and self._token_times[0][0] < cutoff:
                self._token_times.popleft()

            # Check RPM limit
            while len(self._request_times) >= self.requests_per_minute:
                wait_time = self._request_times[0] + 60 - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                now = time.time()
                while self._request_times and self._request_times[0] < now - 60:
                    self._request_times.popleft()

            # Check TPM limit
            current_tokens = sum(t[1] for t in self._token_times)
            while current_tokens + estimated_tokens > self.tokens_per_minute:
                if self._token_times:
                    wait_time = self._token_times[0][0] + 60 - now
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    now = time.time()
                    while self._token_times and self._token_times[0][0] < now - 60:
                        self._token_times.popleft()
                    current_tokens = sum(t[1] for t in self._token_times)
                else:
                    break

            # Record this request
            self._request_times.append(now)
            if estimated_tokens > 0:
                self._token_times.append((now, estimated_tokens))
```

```python
# src/api/circuit_breaker.py

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreaker:
    """Circuit breaker pattern for API resilience."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0

    _state: CircuitState = field(default=CircuitState.CLOSED)
    _failure_count: int = 0
    _last_failure_time: float = 0
    _success_count: int = 0

    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        now = time.time()

        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if now - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                return True
            return False

        # HALF_OPEN - allow limited requests
        return True

    def record_success(self):
        """Record a successful request."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= 3:  # 3 successes to close
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed request."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN

    def get_state(self) -> Dict:
        """Get state for checkpointing."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "success_count": self._success_count
        }

    def restore_state(self, state: Dict):
        """Restore state from checkpoint."""
        self._state = CircuitState(state["state"])
        self._failure_count = state["failure_count"]
        self._last_failure_time = state["last_failure_time"]
        self._success_count = state.get("success_count", 0)
```

---

## 5. Complete Preset Configurations (All 10 Presets)

```python
# src/config/presets.py

from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class JudgeConfig:
    """Configuration for judge models."""
    models: List[str]
    votes_per_judge: int
    use_both_personas: bool

@dataclass
class EvalConfig:
    """Complete evaluation configuration."""
    preset_level: int
    run_name: str
    num_prompts: int
    model_pairs: List[Tuple[str, str]]
    judge_config: JudgeConfig
    random_seed: int = None  # Auto-generated if None
    stratify_by_job_zone: bool = True
    stratify_by_soc_group: bool = True
    phase3_enrich_ratio: float = 0.3
    constraint_probability: float = 0.15
    revision_probability: float = 0.10
    ambiguity_probability: float = 0.05

# Model pairs for Pro-tier
PRO_PAIRS = [
    ("google/gemini-3.0-pro", "openai/gpt-5.2"),
    ("google/gemini-3.0-pro", "anthropic/claude-opus-4.5"),
    ("google/gemini-3.0-pro", "x-ai/grok-4.1"),
    ("google/gemini-3.0-pro", "moonshot/kimi-k2"),
]

# Model pairs for Flash-tier
FLASH_PAIRS = [
    ("google/gemini-3.0-flash", "openai/gpt-4.1"),
    ("google/gemini-3.0-flash", "anthropic/claude-sonnet-4"),
]

# All judge models
ALL_JUDGES = [
    "anthropic/claude-opus-4.5",
    "openai/gpt-5.2",
    "google/gemini-3.0-pro"
]

PRESETS = {
    1: EvalConfig(
        preset_level=1,
        run_name="Sanity Check",
        num_prompts=5,
        model_pairs=[PRO_PAIRS[0]],
        judge_config=JudgeConfig(
            models=[ALL_JUDGES[0]],
            votes_per_judge=1,
            use_both_personas=False
        )
    ),
    2: EvalConfig(
        preset_level=2,
        run_name="Smoke Test",
        num_prompts=20,
        model_pairs=[PRO_PAIRS[0]],
        judge_config=JudgeConfig(
            models=[ALL_JUDGES[0]],
            votes_per_judge=3,
            use_both_personas=False
        )
    ),
    3: EvalConfig(
        preset_level=3,
        run_name="Dev Iteration",
        num_prompts=50,
        model_pairs=[PRO_PAIRS[0], PRO_PAIRS[1]],
        judge_config=JudgeConfig(
            models=ALL_JUDGES[:2],
            votes_per_judge=3,
            use_both_personas=False
        )
    ),
    4: EvalConfig(
        preset_level=4,
        run_name="Quick Sample",
        num_prompts=100,
        model_pairs=[PRO_PAIRS[0], PRO_PAIRS[1]],
        judge_config=JudgeConfig(
            models=ALL_JUDGES[:2],
            votes_per_judge=5,
            use_both_personas=True
        )
    ),
    5: EvalConfig(
        preset_level=5,
        run_name="Light Eval",
        num_prompts=200,
        model_pairs=PRO_PAIRS[:3],
        judge_config=JudgeConfig(
            models=ALL_JUDGES,
            votes_per_judge=3,
            use_both_personas=True
        )
    ),
    6: EvalConfig(
        preset_level=6,
        run_name="Standard Eval",
        num_prompts=500,
        model_pairs=PRO_PAIRS,
        judge_config=JudgeConfig(
            models=ALL_JUDGES,
            votes_per_judge=5,
            use_both_personas=True
        )
    ),
    7: EvalConfig(
        preset_level=7,
        run_name="Thorough Eval",
        num_prompts=1000,
        model_pairs=PRO_PAIRS,
        judge_config=JudgeConfig(
            models=ALL_JUDGES,
            votes_per_judge=5,
            use_both_personas=True
        )
    ),
    8: EvalConfig(
        preset_level=8,
        run_name="Comprehensive",
        num_prompts=2000,
        model_pairs=PRO_PAIRS + FLASH_PAIRS,
        judge_config=JudgeConfig(
            models=ALL_JUDGES,
            votes_per_judge=5,
            use_both_personas=True
        )
    ),
    9: EvalConfig(
        preset_level=9,
        run_name="Deep Dive",
        num_prompts=5000,
        model_pairs=PRO_PAIRS + FLASH_PAIRS,
        judge_config=JudgeConfig(
            models=ALL_JUDGES,
            votes_per_judge=5,
            use_both_personas=True
        )
    ),
    10: EvalConfig(
        preset_level=10,
        run_name="Full Kaboodle",
        num_prompts=10000,
        model_pairs=PRO_PAIRS + FLASH_PAIRS,
        judge_config=JudgeConfig(
            models=ALL_JUDGES,
            votes_per_judge=5,
            use_both_personas=True
        )
    ),
}
```

---

## 6. Cost Estimator (Complete Implementation)

```python
# src/config/cost_estimator.py

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .settings import EvalConfig

# OpenRouter pricing per 1M tokens (verify actual prices at runtime)
MODEL_PRICING = {
    "google/gemini-3.0-pro": {"input": 1.25, "output": 5.00},
    "google/gemini-3.0-flash": {"input": 0.075, "output": 0.30},
    "openai/gpt-5.2": {"input": 15.00, "output": 60.00},
    "openai/gpt-4.1": {"input": 1.50, "output": 6.00},
    "anthropic/claude-opus-4.5": {"input": 15.00, "output": 75.00},
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "x-ai/grok-4.1": {"input": 10.00, "output": 40.00},
    "moonshot/kimi-k2": {"input": 8.00, "output": 32.00},
}

@dataclass
class CostEstimate:
    """Detailed cost and time estimate."""
    response_generation_cost: float
    judging_cost: float
    total_cost: float
    total_api_calls: int
    estimated_hours_min: float
    estimated_hours_max: float
    breakdown: Dict[str, float]

def estimate_cost(config: "EvalConfig") -> CostEstimate:
    """Estimate total cost and time for evaluation run."""

    # Average token estimates
    AVG_INPUT_TOKENS = 600   # Prompt + context
    AVG_OUTPUT_TOKENS = 400  # Model response
    AVG_JUDGE_INPUT_TOKENS = 1800  # Full context + both responses
    AVG_JUDGE_OUTPUT_TOKENS = 150   # Structured judgment

    breakdown = {}

    # Response generation cost
    response_cost = 0.0
    response_calls = 0

    for gemini, competitor in config.model_pairs:
        calls = config.num_prompts * 2  # Both models
        response_calls += calls

        # Gemini cost
        gp = MODEL_PRICING.get(gemini, {"input": 5.0, "output": 20.0})
        gemini_cost = config.num_prompts * (
            gp["input"] * AVG_INPUT_TOKENS / 1_000_000 +
            gp["output"] * AVG_OUTPUT_TOKENS / 1_000_000
        )

        # Competitor cost
        cp = MODEL_PRICING.get(competitor, {"input": 10.0, "output": 40.0})
        comp_cost = config.num_prompts * (
            cp["input"] * AVG_INPUT_TOKENS / 1_000_000 +
            cp["output"] * AVG_OUTPUT_TOKENS / 1_000_000
        )

        breakdown[f"responses_{gemini}"] = gemini_cost
        breakdown[f"responses_{competitor}"] = comp_cost
        response_cost += gemini_cost + comp_cost

    # Judging cost
    persona_multiplier = 2 if config.judge_config.use_both_personas else 1
    judge_calls = (
        config.num_prompts *
        len(config.model_pairs) *
        len(config.judge_config.models) *
        config.judge_config.votes_per_judge *
        persona_multiplier
    )

    judging_cost = 0.0
    for judge in config.judge_config.models:
        jp = MODEL_PRICING.get(judge, {"input": 10.0, "output": 40.0})
        calls_per_judge = judge_calls // len(config.judge_config.models)
        cost = calls_per_judge * (
            jp["input"] * AVG_JUDGE_INPUT_TOKENS / 1_000_000 +
            jp["output"] * AVG_JUDGE_OUTPUT_TOKENS / 1_000_000
        )
        breakdown[f"judging_{judge}"] = cost
        judging_cost += cost

    # Time estimate (conservative with rate limits)
    total_calls = response_calls + judge_calls
    # Assume 20-40 calls/minute with rate limiting
    hours_min = total_calls / 40 / 60
    hours_max = total_calls / 20 / 60

    return CostEstimate(
        response_generation_cost=response_cost,
        judging_cost=judging_cost,
        total_cost=response_cost + judging_cost,
        total_api_calls=total_calls,
        estimated_hours_min=hours_min,
        estimated_hours_max=hours_max,
        breakdown=breakdown
    )

def format_cost_estimate(estimate: CostEstimate, config: "EvalConfig") -> str:
    """Format cost estimate for display."""
    return f"""
╭─────────────────────────────────────────────────────────────╮
│                    EVAL RUN ESTIMATE                        │
├─────────────────────────────────────────────────────────────┤
│ Preset:               {config.preset_level} ({config.run_name})
│ Prompts:              {config.num_prompts:,}
│ Model pairs:          {len(config.model_pairs)}
│ Total comparisons:    {config.num_prompts * len(config.model_pairs):,}
│                                                             │
│ Judge config:         {len(config.judge_config.models)} judges × {config.judge_config.votes_per_judge} votes × {'2 personas' if config.judge_config.use_both_personas else '1 persona'}
│ Total judge calls:    {estimate.total_api_calls - config.num_prompts * len(config.model_pairs) * 2:,}
│                                                             │
│ ESTIMATED COST                                              │
│   Response generation:  ${estimate.response_generation_cost:,.2f}
│   Judging:              ${estimate.judging_cost:,.2f}
│   Total:                ${estimate.total_cost:,.2f}
│                                                             │
│ ESTIMATED TIME                                              │
│   Range:                {estimate.estimated_hours_min:.1f} - {estimate.estimated_hours_max:.1f} hours
╰─────────────────────────────────────────────────────────────╯
"""
```

---

## 7. Complete Prompt Schema

```python
# src/prompts/schemas.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

class EnglishVariant(str, Enum):
    EN_US = "en-US"
    EN_GB = "en-GB"
    EN_AU = "en-AU"
    NON_NATIVE = "non-native"

class MessagePosition(str, Enum):
    INITIAL = "initial_outreach"
    REPLY = "reply_in_thread"
    FOLLOWUP = "follow_up"

class EmotionalContext(str, Enum):
    ROUTINE = "routine"
    CRISIS = "crisis"
    CELEBRATION = "celebration"
    CONFLICT = "conflict"
    BAD_NEWS = "bad_news"

class SensitiveTopic(str, Enum):
    HR_ISSUES = "hr_issues"
    LEGAL = "legal_matters"
    BAD_NEWS = "bad_news_delivery"
    CONFIDENTIAL = "confidential_information"
    CONFLICT = "conflict_situations"

class WriterPersona(BaseModel):
    """Complete writer persona specification."""
    name: str
    email: Optional[str] = None
    age: int = Field(ge=18, le=80)
    generation: Literal["gen_z", "millennial", "gen_x", "boomer"]
    job_title: str
    skill_level: Literal["entry", "mid", "senior", "executive"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    years_experience: Optional[int] = None

class RecipientPersona(BaseModel):
    """Complete recipient persona specification."""
    name: str
    email: Optional[str] = None
    job_title: str
    relationship: Literal["new_contact", "acquaintance", "colleague",
                          "manager", "direct_report", "client", "vendor",
                          "peer", "external_partner", "board_member"]
    english_variant: EnglishVariant = EnglishVariant.EN_US
    is_technical: bool = False
    is_primary: bool = True
    prior_contact: bool = True

class CompanyContext(BaseModel):
    """Company information for grounding."""
    name: str
    size: Literal["startup", "small", "mid_market", "enterprise", "fortune_500"]
    industry_naics: str
    industry_name: str
    is_public: bool = False
    hq_location: Optional[str] = None
    employee_count: Optional[int] = None
    founding_year: Optional[int] = None

    @field_validator('industry_naics')
    @classmethod
    def validate_naics(cls, v):
        if v and len(v) not in [2, 3, 4, 5, 6]:
            if v != "000000":  # Allow placeholder
                raise ValueError("NAICS code must be 2-6 digits")
        return v

class Attachment(BaseModel):
    """Mock attachment or reference content."""
    type: str  # report, email, meeting_notes, resume, etc.
    description: str
    content: str

class ToneExample(BaseModel):
    """Prior writing sample for tone matching."""
    example_text: str
    context: str
    match_instruction: str

class CCContext(BaseModel):
    """Context for CC/forwarding scenarios."""
    cc_recipients: List[str] = []
    will_be_forwarded_to: Optional[str] = None
    mixed_audience_note: Optional[str] = None

class ConstraintSpec(BaseModel):
    """Explicit instruction-following constraint."""
    type: Literal["length", "format", "tone", "exclusion", "inclusion"]
    description: str
    specific_requirement: str
    measurable: bool = True

class RevisionTask(BaseModel):
    """Details for revision/editing tasks."""
    original_draft: str
    revision_type: Literal["concise", "professional", "soften", "expand", "clarify"]
    instruction: str

class WritingPrompt(BaseModel):
    """Complete writing prompt with all dimensions per PROMPT.md."""

    # Identifiers
    prompt_id: str
    onet_task_id: str
    onet_task: str

    # Occupation context
    occupation_code: str
    occupation_title: str
    job_zone: int = Field(ge=1, le=5)
    soc_major_group: str

    # Industry context
    naics_code: str
    naics_sector: str
    company: CompanyContext

    # Personas
    writer: WriterPersona
    recipients: List[RecipientPersona]
    audience_size: Literal["one_on_one", "small_group", "department",
                           "company_wide", "public"]

    # CC/Multiple audience context
    cc_context: Optional[CCContext] = None

    # Communication context
    formality_level: int = Field(ge=1, le=5)
    urgency_level: int = Field(ge=1, le=5)
    message_position: MessagePosition
    emotional_context: EmotionalContext
    communication_channel: Optional[str] = None  # NOT an enum - dynamic

    # Content context
    prior_context: Optional[str] = None
    attachments: List[Attachment] = []
    competing_objectives: Optional[str] = None
    temporal_context: Optional[str] = None

    # Tone matching
    tone_example: Optional[ToneExample] = None

    # Revision tasks
    is_revision_task: bool = False
    revision_task: Optional[RevisionTask] = None

    # Instruction-following constraints
    constraints: List[ConstraintSpec] = []
    has_constraints: bool = False

    # Ambiguity testing
    is_ambiguous: bool = False
    ambiguity_type: Optional[Literal["underspecified_recipient",
                                      "missing_context", "unclear_ask"]] = None

    # Sensitive topics
    sensitive_topics: List[SensitiveTopic] = []

    # Language
    language: str = "en"
    language_variant: str = "en-US"
    recipient_english_variant: Optional[str] = None

    # Metadata
    generated_by_model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # The actual prompt text (built in Phase 3)
    full_prompt: str = ""
```

---

## 8. Judge System (Complete with Parser)

### 8.1 Judge Prompt Builder

```python
# src/eval/judge_prompt_builder.py

from typing import Tuple
from ..prompts.schemas import WritingPrompt

class JudgePromptBuilder:
    """Build judge prompts with full scenario context per PROMPT.md."""

    WRITING_EXPERT_SYSTEM = """You are a seasoned writing consultant who has coached executives
at Fortune 500 companies. Your expertise is in professional communication that achieves
business objectives while maintaining appropriate relationships and tone.

You will evaluate two responses to the same writing task. Consider:
1. Quality of writing - grammar, style, clarity
2. Appropriate length - is it the RIGHT length for this specific task?
3. Tone appropriateness - does it match the relationship and context?
4. Effectiveness - will it achieve the communication objective?
5. Task completion - does it fully address what was asked?
6. Authenticity/"Human-like" quality - does it feel like real human writing?
7. Cliche/boilerplate avoidance - does it avoid obvious AI patterns like "I hope this email finds you well", "Please don't hesitate to reach out", excessive bullet points?
8. Instruction compliance - if constraints were specified, are they followed?

CRITICAL: Position labels (Response A/B) do NOT indicate quality. Evaluate purely on merit."""

    RECIPIENT_SYSTEM = """You are {recipient_name}, {recipient_title}.
Your relationship with the sender: {relationship}
Your technical level: {technical_level}
Your English variant preference: {english_variant}

You will evaluate two responses to a message you would receive.
As the actual recipient, consider:
- Would this message achieve its intended purpose?
- Is the tone appropriate for your relationship with the sender?
- Is it clear what action, if any, you should take?
- Would you feel respected and properly informed?
- Does it feel authentic and human, or does it seem AI-generated?
- Is the length appropriate - not too long, not too short?

CRITICAL: Position labels (Response A/B) do NOT indicate quality. Evaluate purely on merit."""

    def build_judge_prompt(
        self,
        prompt: WritingPrompt,
        response_a: str,
        response_b: str,
        persona: str  # "expert" or "recipient"
    ) -> Tuple[str, str]:
        """Build complete judge prompt with full context."""

        # System prompt based on persona
        if persona == "expert":
            system = self.WRITING_EXPERT_SYSTEM
        else:
            system = self.RECIPIENT_SYSTEM.format(
                recipient_name=prompt.recipients[0].name,
                recipient_title=prompt.recipients[0].job_title,
                relationship=prompt.recipients[0].relationship,
                technical_level="technical" if prompt.recipients[0].is_technical else "non-technical",
                english_variant=prompt.recipients[0].english_variant.value
            )

        # Build user prompt with FULL scenario context
        user_sections = []

        # Task context
        user_sections.append(f"""## Writing Task
{prompt.onet_task}

## Writer Context
Name: {prompt.writer.name}
Role: {prompt.writer.job_title} at {prompt.company.name}
Company: {prompt.company.name} ({prompt.company.size.replace('_', ' ')}, {prompt.company.industry_name})
Generation: {prompt.writer.generation}
Skill Level: {prompt.writer.skill_level}

## Recipient Context
Name: {prompt.recipients[0].name}
Role: {prompt.recipients[0].job_title}
Relationship to Writer: {prompt.recipients[0].relationship}
English Variant: {prompt.recipients[0].english_variant.value}""")

        # CC context if present
        if prompt.cc_context and prompt.cc_context.cc_recipients:
            user_sections.append(f"""
## Additional Audience
CC'd: {', '.join(prompt.cc_context.cc_recipients)}
{prompt.cc_context.mixed_audience_note or ''}""")

        if prompt.cc_context and prompt.cc_context.will_be_forwarded_to:
            user_sections.append(f"Note: This will be forwarded to: {prompt.cc_context.will_be_forwarded_to}")

        # Communication context
        user_sections.append(f"""
## Communication Requirements
Formality Level: {prompt.formality_level}/5 (1=very casual, 5=very formal)
Urgency: {prompt.urgency_level}/5
Emotional Context: {prompt.emotional_context.value}
Channel: {prompt.communication_channel or 'email'}
Message Position: {prompt.message_position.value}""")

        # Temporal context if present
        if prompt.temporal_context:
            user_sections.append(f"\n## Temporal Context\n{prompt.temporal_context}")

        # Prior message if reply
        if prompt.prior_context:
            user_sections.append(f"""
## Prior Message (being responded to)
{prompt.prior_context}""")

        # Attachments summary
        if prompt.attachments:
            user_sections.append("\n## Referenced Materials")
            for att in prompt.attachments:
                user_sections.append(f"[{att.type.upper()}]: {att.description}\n{att.content[:500]}...")

        # Tone example if present
        if prompt.tone_example:
            user_sections.append(f"""
## Tone Reference (writer should match this style)
{prompt.tone_example.context}:
"{prompt.tone_example.example_text[:300]}..."

{prompt.tone_example.match_instruction}""")

        # Competing objectives if present
        if prompt.competing_objectives:
            user_sections.append(f"""
## Key Challenge
{prompt.competing_objectives}""")

        # Instruction constraints - CRITICAL for compliance checking
        if prompt.constraints:
            user_sections.append("\n## EXPLICIT CONSTRAINTS (MUST be followed)")
            for c in prompt.constraints:
                user_sections.append(f"- {c.description}")
            user_sections.append("\nEvaluate whether each response follows these constraints.")

        # Sensitive topics
        if prompt.sensitive_topics:
            topics = [t.value.replace('_', ' ') for t in prompt.sensitive_topics]
            user_sections.append(f"\n## Sensitive Topic Warning\nThis involves: {', '.join(topics)}")

        # The responses to evaluate
        user_sections.append(f"""
---

## Response A
{response_a}

---

## Response B
{response_b}

---

## Your Evaluation

Compare these responses considering ALL context above. Provide:

1. WINNER: "A", "B", or "TIE"
2. CONFIDENCE: 1-5 (5 = very confident)
3. QUALITY_A: 1-10 overall quality score
4. QUALITY_B: 1-10 overall quality score
5. CONSTRAINT_COMPLIANCE_A: YES/NO/NA (did A follow explicit constraints?)
6. CONSTRAINT_COMPLIANCE_B: YES/NO/NA (did B follow explicit constraints?)
7. REASONING: 2-3 sentences explaining your decision

Format your response EXACTLY as:
WINNER: [A/B/TIE]
CONFIDENCE: [1-5]
QUALITY_A: [1-10]
QUALITY_B: [1-10]
CONSTRAINT_COMPLIANCE_A: [YES/NO/NA]
CONSTRAINT_COMPLIANCE_B: [YES/NO/NA]
REASONING: [Your explanation]""")

        return system, "\n\n".join(user_sections)
```

### 8.2 Judge Response Parser (Complete - Previously Missing)

```python
# src/eval/judge_parser.py

import re
from typing import Optional
from dataclasses import dataclass

@dataclass
class ParsedJudgment:
    """Parsed judgment from judge model."""
    winner: str  # "A", "B", or "TIE"
    confidence: int
    quality_a: int
    quality_b: int
    constraint_compliance_a: Optional[str]  # "YES", "NO", "NA"
    constraint_compliance_b: Optional[str]
    reasoning: str
    raw_response: str
    parse_success: bool

class JudgeParser:
    """Parse judge model responses with robust fallbacks."""

    def parse(self, response_text: str) -> ParsedJudgment:
        """Parse judge response into structured format."""
        raw = response_text.strip()

        # Try structured parsing first
        result = self._parse_structured(raw)
        if result.parse_success:
            return result

        # Fallback: try to extract key fields with regex
        result = self._parse_fallback(raw)
        return result

    def _parse_structured(self, text: str) -> ParsedJudgment:
        """Parse expected structured format."""
        patterns = {
            'winner': r'WINNER:\s*([ABab]|TIE|tie)',
            'confidence': r'CONFIDENCE:\s*([1-5])',
            'quality_a': r'QUALITY_A:\s*(\d+)',
            'quality_b': r'QUALITY_B:\s*(\d+)',
            'compliance_a': r'CONSTRAINT_COMPLIANCE_A:\s*(YES|NO|NA|yes|no|na)',
            'compliance_b': r'CONSTRAINT_COMPLIANCE_B:\s*(YES|NO|NA|yes|no|na)',
            'reasoning': r'REASONING:\s*(.+?)(?:\n|$)',
        }

        extracted = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted[key] = match.group(1).strip()

        # Check required fields
        if 'winner' not in extracted:
            return ParsedJudgment(
                winner="TIE",
                confidence=1,
                quality_a=5,
                quality_b=5,
                constraint_compliance_a=None,
                constraint_compliance_b=None,
                reasoning="Parse failed - defaulting to tie",
                raw_response=text,
                parse_success=False
            )

        return ParsedJudgment(
            winner=extracted['winner'].upper(),
            confidence=int(extracted.get('confidence', 3)),
            quality_a=min(10, max(1, int(extracted.get('quality_a', 5)))),
            quality_b=min(10, max(1, int(extracted.get('quality_b', 5)))),
            constraint_compliance_a=extracted.get('compliance_a', '').upper() or None,
            constraint_compliance_b=extracted.get('compliance_b', '').upper() or None,
            reasoning=extracted.get('reasoning', 'No reasoning provided'),
            raw_response=text,
            parse_success=True
        )

    def _parse_fallback(self, text: str) -> ParsedJudgment:
        """Fallback parsing for non-standard responses."""
        text_lower = text.lower()

        # Try to determine winner from natural language
        winner = "TIE"
        if any(phrase in text_lower for phrase in [
            "response a is better", "a is the winner", "prefer a",
            "a wins", "choose a", "a is superior"
        ]):
            winner = "A"
        elif any(phrase in text_lower for phrase in [
            "response b is better", "b is the winner", "prefer b",
            "b wins", "choose b", "b is superior"
        ]):
            winner = "B"
        elif any(phrase in text_lower for phrase in [
            "tie", "equally", "both are", "neither is clearly"
        ]):
            winner = "TIE"

        # Try to extract a quality assessment
        quality_match = re.search(r'(\d+)\s*/\s*10', text)
        quality = int(quality_match.group(1)) if quality_match else 5

        return ParsedJudgment(
            winner=winner,
            confidence=2,  # Lower confidence for fallback parsing
            quality_a=quality,
            quality_b=quality,
            constraint_compliance_a=None,
            constraint_compliance_b=None,
            reasoning=text[:500] if len(text) > 500 else text,
            raw_response=text,
            parse_success=False
        )
```

---

## 9. Vote Aggregator (Fixed Per Simulations)

The simulations identified issues with judge persona aggregation. Here is the corrected implementation:

```python
# src/eval/vote_aggregator.py

import hashlib
import random
from typing import List, Literal, Dict
from dataclasses import dataclass

@dataclass
class JudgeVote:
    """Single vote from a judge."""
    judge_model: str
    judge_persona: str  # "expert" or "recipient"
    vote_index: int  # Which of the 5 votes
    winner: Literal["gemini", "competitor", "tie"]
    confidence: int
    quality_gemini: int
    quality_competitor: int
    reasoning: str
    gemini_was_position: Literal["A", "B"]
    constraint_compliance_gemini: str = None
    constraint_compliance_competitor: str = None

@dataclass
class AggregatedResult:
    """Aggregated result for a comparison."""
    prompt_id: str
    gemini_model: str
    competitor_model: str
    final_winner: Literal["gemini", "competitor", "tie"]
    gemini_wins: int
    competitor_wins: int
    ties: int
    judge_agreement: float  # 0.0 to 1.0
    per_judge_results: Dict[str, str]  # judge_model -> winner
    all_votes: List[JudgeVote]

class VoteAggregator:
    """Implement majority-of-majorities aggregation per PROMPT.md.

    IMPORTANT CLARIFICATION (from simulations):
    PROMPT.md says "majority of the 3 judges" - this means we aggregate
    across the 3 judge MODELS, not 6 (3 judges x 2 personas).

    For each judge model, we combine votes from both personas, then take
    the majority across the 3 judge models.
    """

    def __init__(self, votes_per_judge: int = 5):
        self.votes_per_judge = votes_per_judge

    def get_position_for_vote(
        self,
        prompt_id: str,
        gemini_model: str,
        competitor_model: str,
        judge_model: str,
        judge_persona: str,
        vote_index: int
    ) -> Literal["A", "B"]:
        """Deterministic but varied position assignment."""
        seed_string = f"{prompt_id}_{gemini_model}_{competitor_model}_{judge_model}_{judge_persona}_{vote_index}"
        seed = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        return "A" if rng.random() < 0.5 else "B"

    def parse_winner_to_normalized(
        self,
        raw_winner: str,
        gemini_position: Literal["A", "B"]
    ) -> Literal["gemini", "competitor", "tie"]:
        """Convert position-based winner to model-based winner."""
        raw = raw_winner.upper().strip()
        if raw == "TIE":
            return "tie"
        elif raw == gemini_position:
            return "gemini"
        else:
            return "competitor"

    def aggregate_for_judge_model(
        self,
        votes: List[JudgeVote]
    ) -> Literal["gemini", "competitor", "tie"]:
        """Get majority winner for a single judge MODEL (both personas combined).

        Per PROMPT.md: "Each judge model gives best-of-5 votes independently"
        With 2 personas and 5 votes each, we have 10 votes per judge model.
        Take the majority across all 10.
        """
        gemini_count = sum(1 for v in votes if v.winner == "gemini")
        competitor_count = sum(1 for v in votes if v.winner == "competitor")

        total_decisive = gemini_count + competitor_count
        majority_threshold = total_decisive / 2 if total_decisive > 0 else 0

        if gemini_count > majority_threshold:
            return "gemini"
        elif competitor_count > majority_threshold:
            return "competitor"
        else:
            return "tie"

    def aggregate_all(
        self,
        prompt_id: str,
        gemini_model: str,
        competitor_model: str,
        all_votes: List[JudgeVote]
    ) -> AggregatedResult:
        """Apply majority-of-majorities aggregation.

        Step 1: Group votes by judge MODEL (not persona)
        Step 2: Get majority winner per judge model
        Step 3: Take majority across the 3 judge models
        """

        # Group by judge model ONLY (combine personas)
        judge_model_groups: Dict[str, List[JudgeVote]] = {}
        for vote in all_votes:
            if vote.judge_model not in judge_model_groups:
                judge_model_groups[vote.judge_model] = []
            judge_model_groups[vote.judge_model].append(vote)

        # Get majority per judge model
        per_judge_results = {}
        judge_majorities = []
        for judge_model, votes in judge_model_groups.items():
            majority = self.aggregate_for_judge_model(votes)
            per_judge_results[judge_model] = majority
            judge_majorities.append(majority)

        # Aggregate across judges (majority of 3)
        gemini_judges = sum(1 for m in judge_majorities if m == "gemini")
        competitor_judges = sum(1 for m in judge_majorities if m == "competitor")
        num_judges = len(judge_majorities)

        if gemini_judges > num_judges / 2:
            final = "gemini"
        elif competitor_judges > num_judges / 2:
            final = "competitor"
        else:
            final = "tie"

        # Calculate agreement (what fraction of judges agreed with final?)
        if final != "tie":
            agreement = max(gemini_judges, competitor_judges) / num_judges
        else:
            agreement = 0.0

        return AggregatedResult(
            prompt_id=prompt_id,
            gemini_model=gemini_model,
            competitor_model=competitor_model,
            final_winner=final,
            gemini_wins=sum(1 for v in all_votes if v.winner == "gemini"),
            competitor_wins=sum(1 for v in all_votes if v.winner == "competitor"),
            ties=sum(1 for v in all_votes if v.winner == "tie"),
            judge_agreement=agreement,
            per_judge_results=per_judge_results,
            all_votes=all_votes
        )
```

---

## 10. Compliance Tracker (Complete - Previously Missing)

The simulations identified this as a critical gap for instruction-following evaluation.

```python
# src/eval/compliance_tracker.py

import re
from dataclasses import dataclass
from typing import List, Optional
from ..prompts.schemas import ConstraintSpec, WritingPrompt

@dataclass
class ComplianceResult:
    """Result of constraint compliance check."""
    constraint: ConstraintSpec
    is_compliant: bool
    actual_value: Optional[str] = None  # e.g., "127 words" for length check
    details: str = ""

class ComplianceTracker:
    """Verify response compliance with explicit constraints."""

    def check_all_constraints(
        self,
        response: str,
        prompt: WritingPrompt
    ) -> List[ComplianceResult]:
        """Check all constraints for a prompt."""
        results = []
        for constraint in prompt.constraints:
            result = self.check_constraint(response, constraint)
            results.append(result)
        return results

    def check_constraint(
        self,
        response: str,
        constraint: ConstraintSpec
    ) -> ComplianceResult:
        """Check a single constraint."""
        if constraint.type == "length":
            return self._check_length(response, constraint)
        elif constraint.type == "format":
            return self._check_format(response, constraint)
        elif constraint.type == "tone":
            return self._check_tone(response, constraint)
        elif constraint.type == "exclusion":
            return self._check_exclusion(response, constraint)
        elif constraint.type == "inclusion":
            return self._check_inclusion(response, constraint)
        else:
            return ComplianceResult(
                constraint=constraint,
                is_compliant=True,
                details="Unknown constraint type - skipped"
            )

    def _check_length(
        self,
        response: str,
        constraint: ConstraintSpec
    ) -> ComplianceResult:
        """Check length constraints."""
        req = constraint.specific_requirement

        if req.startswith("max_words:"):
            max_words = int(req.split(":")[1])
            actual_words = len(response.split())
            is_compliant = actual_words <= max_words
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                actual_value=f"{actual_words} words",
                details=f"Required max {max_words}, got {actual_words}"
            )

        elif req.startswith("min_words:"):
            min_words = int(req.split(":")[1])
            actual_words = len(response.split())
            is_compliant = actual_words >= min_words
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                actual_value=f"{actual_words} words",
                details=f"Required min {min_words}, got {actual_words}"
            )

        elif req.startswith("exact_sentences:"):
            n = int(req.split(":")[1])
            # Simple sentence count (not perfect but reasonable)
            sentences = re.split(r'[.!?]+', response.strip())
            sentences = [s for s in sentences if s.strip()]
            is_compliant = len(sentences) == n
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                actual_value=f"{len(sentences)} sentences",
                details=f"Required exactly {n}, got {len(sentences)}"
            )

        elif req.startswith("max_paragraphs:"):
            max_para = int(req.split(":")[1])
            paragraphs = [p for p in response.split('\n\n') if p.strip()]
            is_compliant = len(paragraphs) <= max_para
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                actual_value=f"{len(paragraphs)} paragraphs",
                details=f"Required max {max_para}, got {len(paragraphs)}"
            )

        return ComplianceResult(
            constraint=constraint,
            is_compliant=True,
            details="Unknown length requirement - skipped"
        )

    def _check_format(
        self,
        response: str,
        constraint: ConstraintSpec
    ) -> ComplianceResult:
        """Check format constraints."""
        req = constraint.specific_requirement

        if req == "no_bullets":
            has_bullets = bool(re.search(r'^[\s]*[-*•]\s+', response, re.MULTILINE))
            return ComplianceResult(
                constraint=constraint,
                is_compliant=not has_bullets,
                details="Contains bullet points" if has_bullets else "No bullet points found"
            )

        elif req.startswith("exact_bullets:"):
            n = int(req.split(":")[1])
            bullets = re.findall(r'^[\s]*[-*•]\s+', response, re.MULTILINE)
            is_compliant = len(bullets) == n
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                actual_value=f"{len(bullets)} bullets",
                details=f"Required exactly {n}, got {len(bullets)}"
            )

        elif req == "has_subject":
            # Look for "Subject:" or similar at start
            has_subject = bool(re.search(r'^(Subject|Re|Subj)[:\s]', response, re.MULTILINE | re.IGNORECASE))
            return ComplianceResult(
                constraint=constraint,
                is_compliant=has_subject,
                details="Subject line found" if has_subject else "No subject line detected"
            )

        elif req == "has_headings":
            # Look for markdown headings or ALL CAPS lines
            has_headings = bool(re.search(r'^(#{1,6}\s+|[A-Z][A-Z\s]{2,}:?\s*$)', response, re.MULTILINE))
            return ComplianceResult(
                constraint=constraint,
                is_compliant=has_headings,
                details="Headings found" if has_headings else "No headings detected"
            )

        return ComplianceResult(
            constraint=constraint,
            is_compliant=True,
            details="Unknown format requirement - skipped"
        )

    def _check_tone(
        self,
        response: str,
        constraint: ConstraintSpec
    ) -> ComplianceResult:
        """Check tone constraints (heuristic-based)."""
        req = constraint.specific_requirement
        text_lower = response.lower()

        if req == "no_pleasantries":
            pleasantries = [
                "hope this finds you",
                "hope you're doing well",
                "hope all is well",
                "i hope you're having",
                "thank you for your time",
                "please don't hesitate"
            ]
            found = [p for p in pleasantries if p in text_lower]
            is_compliant = len(found) == 0
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                details=f"Found pleasantries: {found}" if found else "No pleasantries found"
            )

        elif req == "formal_only":
            casual_markers = [
                "hey ", "hi!", "thanks!", "gonna", "wanna", "gotta",
                "awesome", "cool!", "sup", "btw", "fyi"
            ]
            found = [m for m in casual_markers if m in text_lower]
            is_compliant = len(found) == 0
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                details=f"Found casual language: {found}" if found else "No casual language detected"
            )

        return ComplianceResult(
            constraint=constraint,
            is_compliant=True,
            details="Tone check heuristic - manual review recommended"
        )

    def _check_exclusion(
        self,
        response: str,
        constraint: ConstraintSpec
    ) -> ComplianceResult:
        """Check exclusion constraints."""
        req = constraint.specific_requirement
        text_lower = response.lower()

        if req.startswith("word:"):
            word = req.split(":")[1].lower()
            found = word in text_lower
            return ComplianceResult(
                constraint=constraint,
                is_compliant=not found,
                details=f"Word '{word}' {'found' if found else 'not found'}"
            )

        elif req.startswith("topic:"):
            topic = req.split(":")[1].lower()
            # Simple keyword matching
            topic_keywords = {
                "budget": ["budget", "cost", "expense", "financial", "funding", "money"],
                "dates": ["monday", "tuesday", "wednesday", "thursday", "friday",
                         "january", "february", "march", "april", "may", "june",
                         "july", "august", "september", "october", "november", "december",
                         r"\d{1,2}/\d{1,2}", r"\d{4}"]
            }
            keywords = topic_keywords.get(topic, [topic])
            found = []
            for kw in keywords:
                if re.search(kw, text_lower):
                    found.append(kw)
            is_compliant = len(found) == 0
            return ComplianceResult(
                constraint=constraint,
                is_compliant=is_compliant,
                details=f"Topic '{topic}' {'referenced via: ' + str(found) if found else 'not referenced'}"
            )

        return ComplianceResult(
            constraint=constraint,
            is_compliant=True,
            details="Unknown exclusion requirement - skipped"
        )

    def _check_inclusion(
        self,
        response: str,
        constraint: ConstraintSpec
    ) -> ComplianceResult:
        """Check inclusion constraints."""
        req = constraint.specific_requirement
        text_lower = response.lower()

        if req.startswith("word:"):
            word = req.split(":")[1].lower()
            found = word in text_lower
            return ComplianceResult(
                constraint=constraint,
                is_compliant=found,
                details=f"Required word '{word}' {'found' if found else 'not found'}"
            )

        return ComplianceResult(
            constraint=constraint,
            is_compliant=True,
            details="Unknown inclusion requirement - skipped"
        )
```

---

## 11. Response Analyzer (Format Detection - Previously Missing)

```python
# src/eval/response_analyzer.py

import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ResponseMetrics:
    """Metrics extracted from a model response."""
    word_count: int
    sentence_count: int
    paragraph_count: int
    has_bullets: bool
    bullet_count: int
    has_headers: bool
    header_count: int
    greeting_type: Optional[str]  # formal, semiformal, casual, none
    signoff_type: Optional[str]   # formal, semiformal, casual, none
    has_subject_line: bool
    ai_cliche_count: int
    questions_count: int
    exclamation_count: int

class ResponseAnalyzer:
    """Analyze response format and patterns."""

    # Common AI cliches to detect
    AI_CLICHES = [
        "i hope this email finds you well",
        "i hope this message finds you",
        "please don't hesitate to reach out",
        "please feel free to reach out",
        "looking forward to hearing from you",
        "best regards",
        "kind regards",
        "warm regards",
        "i wanted to reach out",
        "i'm reaching out to",
        "i hope you're doing well",
        "thank you for your time and consideration",
        "please let me know if you have any questions"
    ]

    GREETING_PATTERNS = {
        'formal': [r'^Dear\s+', r'^To whom it may concern'],
        'semiformal': [r'^Hi\s+', r'^Hello\s+', r'^Good\s+(morning|afternoon|evening)'],
        'casual': [r'^Hey\s+', r'^Hey!', r'^Yo\s+', r'^What\'s up']
    }

    SIGNOFF_PATTERNS = {
        'formal': [r'Sincerely,?\s*$', r'Respectfully,?\s*$', r'Best regards,?\s*$'],
        'semiformal': [r'Best,?\s*$', r'Thanks,?\s*$', r'Thank you,?\s*$', r'Regards,?\s*$'],
        'casual': [r'Cheers,?\s*$', r'Later,?\s*$', r'Talk soon,?\s*$', r'TTYL']
    }

    def analyze(self, response: str) -> ResponseMetrics:
        """Analyze a response and extract metrics."""

        # Basic counts
        words = response.split()
        sentences = [s for s in re.split(r'[.!?]+', response) if s.strip()]
        paragraphs = [p for p in response.split('\n\n') if p.strip()]

        # Bullet detection
        bullets = re.findall(r'^[\s]*[-*•]\s+', response, re.MULTILINE)

        # Header detection (markdown or all caps)
        headers = re.findall(r'^(#{1,6}\s+.+|[A-Z][A-Z\s]{2,}:?\s*)$', response, re.MULTILINE)

        # Greeting detection
        greeting_type = None
        first_line = response.split('\n')[0] if response else ""
        for gtype, patterns in self.GREETING_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, first_line, re.IGNORECASE):
                    greeting_type = gtype
                    break
            if greeting_type:
                break

        # Signoff detection
        signoff_type = None
        last_lines = '\n'.join(response.split('\n')[-3:])
        for stype, patterns in self.SIGNOFF_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, last_lines, re.IGNORECASE | re.MULTILINE):
                    signoff_type = stype
                    break
            if signoff_type:
                break

        # Subject line detection
        has_subject = bool(re.search(r'^(Subject|Re|Subj)[:\s]', response, re.MULTILINE | re.IGNORECASE))

        # AI cliche detection
        response_lower = response.lower()
        ai_cliches = sum(1 for cliche in self.AI_CLICHES if cliche in response_lower)

        # Question and exclamation counts
        questions = len(re.findall(r'\?', response))
        exclamations = len(re.findall(r'!', response))

        return ResponseMetrics(
            word_count=len(words),
            sentence_count=len(sentences),
            paragraph_count=len(paragraphs),
            has_bullets=len(bullets) > 0,
            bullet_count=len(bullets),
            has_headers=len(headers) > 0,
            header_count=len(headers),
            greeting_type=greeting_type,
            signoff_type=signoff_type,
            has_subject_line=has_subject,
            ai_cliche_count=ai_cliches,
            questions_count=questions,
            exclamation_count=exclamations
        )
```

---

## 12. Weakness Finder (Complete - CRITICAL PROMPT.md Requirement)

```python
# src/analysis/weakness_finder.py

from dataclasses import dataclass
from typing import List, Dict, Optional, TYPE_CHECKING
from scipy import stats

if TYPE_CHECKING:
    from ..storage.database import ResultsDatabase

@dataclass
class Weakness:
    """Identified weakness in Gemini performance."""
    dimension: str  # occupation, formality, job_zone, emotion, etc.
    dimension_value: str  # The specific value (e.g., "11-1011" for occupation)
    dimension_label: str  # Human readable (e.g., "Chief Executives")
    win_rate: float
    loss_rate: float
    sample_size: int
    p_value: float  # Statistical significance
    effect_size: float  # Cohen's h
    example_prompt_ids: List[str]  # Sample prompts showing this weakness
    competitor_model: str  # Which competitor Gemini loses to

@dataclass
class WeaknessReport:
    """Complete weakness analysis report."""
    total_comparisons: int
    overall_win_rate: float
    significant_weaknesses: List[Weakness]
    potential_weaknesses: List[Weakness]  # p < 0.1 but >= 0.05
    strengths: List[Weakness]  # Areas where Gemini excels

class WeaknessFinder:
    """Identify systematic weaknesses in Gemini performance per PROMPT.md."""

    def __init__(self, min_sample_size: int = 10, significance_level: float = 0.05):
        self.min_sample_size = min_sample_size
        self.significance_level = significance_level

    async def find_weaknesses(
        self,
        db: "ResultsDatabase",
        gemini_model: str
    ) -> WeaknessReport:
        """Find all systematic weaknesses for a Gemini model."""

        # Dimensions to analyze
        dimensions = [
            ("occupation_code", "occupation_title"),
            ("job_zone", None),
            ("soc_major_group", None),
            ("naics_sector", None),
            ("formality_level", None),
            ("urgency_level", None),
            ("emotional_context", None),
            ("writer_generation", None),
            ("writer_skill_level", None),
            ("audience_size", None),
            ("communication_channel", None),
            ("has_constraints", None),
            ("is_revision_task", None),
            ("is_ambiguous", None),
        ]

        all_weaknesses = []
        all_strengths = []

        for dim_column, label_column in dimensions:
            results = await db.get_win_rates_by_dimension(
                gemini_model=gemini_model,
                dimension=dim_column,
                label_column=label_column
            )

            for r in results:
                if r["total"] < self.min_sample_size:
                    continue

                win_rate = r["wins"] / r["total"]
                loss_rate = r["losses"] / r["total"]

                # Test if significantly different from 50%
                result = stats.binomtest(r["wins"], r["total"], 0.5)
                p_value = result.pvalue

                # Cohen's h effect size
                effect_size = self._cohens_h(win_rate, 0.5)

                weakness = Weakness(
                    dimension=dim_column,
                    dimension_value=str(r["dimension_value"]),
                    dimension_label=r.get("dimension_label", str(r["dimension_value"])),
                    win_rate=win_rate,
                    loss_rate=loss_rate,
                    sample_size=r["total"],
                    p_value=p_value,
                    effect_size=effect_size,
                    example_prompt_ids=r.get("example_prompts", [])[:5],
                    competitor_model=r.get("competitor_model", "various")
                )

                if win_rate < 0.5 and p_value < self.significance_level:
                    all_weaknesses.append(weakness)
                elif win_rate > 0.5 and p_value < self.significance_level:
                    all_strengths.append(weakness)

        # Sort by effect size (most significant weaknesses first)
        all_weaknesses.sort(key=lambda w: w.effect_size, reverse=True)
        all_strengths.sort(key=lambda w: w.effect_size, reverse=True)

        # Separate significant from potential weaknesses
        significant = [w for w in all_weaknesses if w.p_value < 0.05]
        potential = [w for w in all_weaknesses if 0.05 <= w.p_value < 0.1]

        # Get overall stats
        overall = await db.get_overall_win_rate(gemini_model)

        return WeaknessReport(
            total_comparisons=overall["total"],
            overall_win_rate=overall["win_rate"],
            significant_weaknesses=significant,
            potential_weaknesses=potential,
            strengths=all_strengths[:10]  # Top 10 strengths
        )

    def _cohens_h(self, p1: float, p2: float) -> float:
        """Calculate Cohen's h effect size for two proportions."""
        import math
        phi1 = 2 * math.asin(math.sqrt(p1))
        phi2 = 2 * math.asin(math.sqrt(p2))
        return abs(phi1 - phi2)

    def format_weakness_report(self, report: WeaknessReport) -> str:
        """Format weakness report for display."""
        lines = []
        lines.append("=" * 60)
        lines.append("GEMINI WEAKNESS ANALYSIS")
        lines.append("=" * 60)
        lines.append(f"Total comparisons: {report.total_comparisons:,}")
        lines.append(f"Overall win rate: {report.overall_win_rate:.1%}")
        lines.append("")

        if report.significant_weaknesses:
            lines.append("SIGNIFICANT WEAKNESSES (p < 0.05)")
            lines.append("-" * 40)
            for w in report.significant_weaknesses[:15]:
                lines.append(
                    f"  {w.dimension}: {w.dimension_label}"
                )
                lines.append(
                    f"    Win rate: {w.win_rate:.1%} (n={w.sample_size}, p={w.p_value:.3f})"
                )
                lines.append("")
        else:
            lines.append("No significant weaknesses identified.")
            lines.append("")

        if report.strengths:
            lines.append("NOTABLE STRENGTHS (p < 0.05)")
            lines.append("-" * 40)
            for s in report.strengths[:10]:
                lines.append(
                    f"  {s.dimension}: {s.dimension_label}"
                )
                lines.append(
                    f"    Win rate: {s.win_rate:.1%} (n={s.sample_size})"
                )
                lines.append("")

        return "\n".join(lines)
```

---

## 13. Checkpoint and Resume System (Complete)

```python
# src/storage/checkpoint.py

import json
import os
import signal
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from datetime import datetime

@dataclass
class ComparisonState:
    """State of a single comparison."""
    prompt_id: str
    gemini_model: str
    competitor_model: str
    gemini_response: Optional[str] = None
    competitor_response: Optional[str] = None
    gemini_response_time: Optional[datetime] = None
    competitor_response_time: Optional[datetime] = None
    completed_votes: List[Dict] = field(default_factory=list)
    is_complete: bool = False

@dataclass
class CheckpointState:
    """Complete checkpoint state."""
    run_id: str
    config_hash: str  # To detect config changes
    started_at: str
    last_updated: str
    total_prompts: int
    completed_comparisons: Set[str] = field(default_factory=set)
    in_progress_comparisons: Dict[str, ComparisonState] = field(default_factory=dict)
    circuit_breaker_states: Dict[str, Dict] = field(default_factory=dict)
    current_phase: str = "response_generation"  # or "judging" or "analysis"

class CheckpointManager:
    """Manage checkpoint state for resumability."""

    def __init__(self, checkpoint_path: Path, config_hash: str):
        self.checkpoint_path = checkpoint_path
        self.config_hash = config_hash
        self.state: Optional[CheckpointState] = None
        self._dirty = False
        self._save_lock = asyncio.Lock()

    async def initialize(self, run_id: str, total_prompts: int) -> CheckpointState:
        """Initialize new checkpoint or load existing."""
        if self.checkpoint_path.exists():
            return await self.load()

        self.state = CheckpointState(
            run_id=run_id,
            config_hash=self.config_hash,
            started_at=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
            total_prompts=total_prompts
        )
        await self.save()
        return self.state

    async def load(self) -> CheckpointState:
        """Load checkpoint from disk."""
        with open(self.checkpoint_path) as f:
            data = json.load(f)

        # Verify config hasn't changed
        if data.get("config_hash") != self.config_hash:
            raise ValueError(
                "Checkpoint config hash mismatch. The evaluation configuration "
                "has changed since the last run. Start a new run or use the "
                "original configuration."
            )

        # Reconstruct state
        self.state = CheckpointState(
            run_id=data["run_id"],
            config_hash=data["config_hash"],
            started_at=data["started_at"],
            last_updated=data["last_updated"],
            total_prompts=data["total_prompts"],
            completed_comparisons=set(data.get("completed_comparisons", [])),
            in_progress_comparisons={
                k: ComparisonState(**v)
                for k, v in data.get("in_progress_comparisons", {}).items()
            },
            circuit_breaker_states=data.get("circuit_breaker_states", {}),
            current_phase=data.get("current_phase", "response_generation")
        )
        return self.state

    async def save(self) -> None:
        """Atomically save checkpoint to disk."""
        async with self._save_lock:
            if self.state is None:
                return

            self.state.last_updated = datetime.utcnow().isoformat()

            # Prepare data
            data = {
                "run_id": self.state.run_id,
                "config_hash": self.state.config_hash,
                "started_at": self.state.started_at,
                "last_updated": self.state.last_updated,
                "total_prompts": self.state.total_prompts,
                "completed_comparisons": list(self.state.completed_comparisons),
                "in_progress_comparisons": {
                    k: asdict(v) for k, v in self.state.in_progress_comparisons.items()
                },
                "circuit_breaker_states": self.state.circuit_breaker_states,
                "current_phase": self.state.current_phase
            }

            # Atomic write: write to temp file, then rename
            temp_path = self.checkpoint_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            # Atomic rename
            os.replace(temp_path, self.checkpoint_path)
            self._dirty = False

    def is_comparison_complete(self, comparison_id: str) -> bool:
        """Check if a comparison is already complete."""
        return comparison_id in self.state.completed_comparisons

    def get_partial_state(self, comparison_id: str) -> Optional[ComparisonState]:
        """Get partial state for resuming mid-comparison."""
        return self.state.in_progress_comparisons.get(comparison_id)

    async def record_response(
        self,
        comparison_id: str,
        prompt_id: str,
        gemini_model: str,
        competitor_model: str,
        model_type: str,  # "gemini" or "competitor"
        response: str
    ) -> None:
        """Record a response and save checkpoint."""
        if comparison_id not in self.state.in_progress_comparisons:
            self.state.in_progress_comparisons[comparison_id] = ComparisonState(
                prompt_id=prompt_id,
                gemini_model=gemini_model,
                competitor_model=competitor_model
            )

        state = self.state.in_progress_comparisons[comparison_id]
        if model_type == "gemini":
            state.gemini_response = response
            state.gemini_response_time = datetime.utcnow()
        else:
            state.competitor_response = response
            state.competitor_response_time = datetime.utcnow()

        await self.save()

    async def record_vote(
        self,
        comparison_id: str,
        vote_data: Dict
    ) -> None:
        """Record a judge vote and save checkpoint."""
        if comparison_id in self.state.in_progress_comparisons:
            state = self.state.in_progress_comparisons[comparison_id]
            state.completed_votes.append(vote_data)
            await self.save()

    async def mark_comparison_complete(self, comparison_id: str) -> None:
        """Mark a comparison as complete."""
        self.state.completed_comparisons.add(comparison_id)
        if comparison_id in self.state.in_progress_comparisons:
            del self.state.in_progress_comparisons[comparison_id]
        await self.save()

    def update_circuit_breaker_states(self, states: Dict[str, Dict]) -> None:
        """Update circuit breaker states (saved on next save())."""
        self.state.circuit_breaker_states = states
        self._dirty = True

    def get_progress(self) -> Dict:
        """Get current progress statistics."""
        completed = len(self.state.completed_comparisons)
        in_progress = len(self.state.in_progress_comparisons)
        return {
            "completed": completed,
            "in_progress": in_progress,
            "total": self.state.total_prompts,
            "percent": (completed / self.state.total_prompts * 100) if self.state.total_prompts > 0 else 0
        }

def setup_signal_handlers(checkpoint_manager: CheckpointManager) -> None:
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()

    def handle_signal(signum, frame):
        print(f"\nReceived signal {signum}. Saving checkpoint...")
        # Schedule the save coroutine
        asyncio.ensure_future(checkpoint_manager.save())
        # Give it a moment to complete
        loop.run_until_complete(asyncio.sleep(1))
        print("Checkpoint saved. Exiting.")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
```

---

## 14. Run Directory Structure (Complete)

```python
# src/storage/run_directory.py

from pathlib import Path
from datetime import datetime
import json
import os

class RunDirectory:
    """Manage the complete run directory structure per PROMPT.md."""

    def __init__(self, base_dir: Path, run_id: str = None):
        if run_id is None:
            run_id = datetime.now().strftime("eval_%Y-%m-%d_%H-%M-%S")

        self.run_id = run_id
        self.root = base_dir / run_id

    def create_structure(self) -> "RunDirectory":
        """Create the full directory structure."""
        dirs = [
            self.root,
            self.root / "prompts" / "prompts_by_occupation",
            self.root / "prompts" / "prompts_by_industry",
            self.root / "responses" / "by_prompt",
            self.root / "responses" / "by_model",
            self.root / "judgments" / "raw",
            self.root / "judgments" / "aggregated",
            self.root / "analysis",
            self.root / "reports" / "charts",
            self.root / "logs"
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        return self

    # File paths
    @property
    def config_json(self) -> Path:
        return self.root / "config.json"

    @property
    def config_summary_txt(self) -> Path:
        return self.root / "config_summary.txt"

    @property
    def checkpoint_json(self) -> Path:
        return self.root / "checkpoint.json"

    @property
    def random_seed_txt(self) -> Path:
        return self.root / "random_seed.txt"

    @property
    def prompts_json(self) -> Path:
        return self.root / "prompts" / "prompts.json"

    @property
    def results_db(self) -> Path:
        return self.root / "results.db"

    @property
    def results_csv(self) -> Path:
        return self.root / "results_summary.csv"

    @property
    def full_report_pdf(self) -> Path:
        return self.root / "reports" / "report.pdf"

    @property
    def executive_summary_md(self) -> Path:
        return self.root / "reports" / "executive_summary.md"

    @property
    def run_log(self) -> Path:
        return self.root / "logs" / "run.log"

    @property
    def failures_log(self) -> Path:
        return self.root / "logs" / "failures.log"

    @property
    def timing_log(self) -> Path:
        return self.root / "logs" / "timing.log"

    @property
    def readme_md(self) -> Path:
        return self.root / "README.md"

    # Methods
    def get_response_path(self, prompt_id: str, model: str) -> Path:
        """Get path for a specific response."""
        safe_model = model.replace("/", "_")
        return self.root / "responses" / "by_prompt" / prompt_id / f"{safe_model}.json"

    def get_judgment_path(self, comparison_id: str) -> Path:
        """Get path for raw judgment data."""
        return self.root / "judgments" / "raw" / f"{comparison_id}.json"

    def get_aggregated_judgment_path(self, comparison_id: str) -> Path:
        """Get path for aggregated judgment."""
        return self.root / "judgments" / "aggregated" / f"{comparison_id}.json"

    def get_analysis_path(self, analysis_name: str) -> Path:
        """Get path for analysis output."""
        return self.root / "analysis" / f"{analysis_name}.json"

    def get_chart_path(self, chart_name: str) -> Path:
        """Get path for chart."""
        return self.root / "reports" / "charts" / f"{chart_name}.png"

    def create_latest_symlink(self, results_base: Path) -> None:
        """Create 'latest' symlink pointing to this run."""
        latest_link = results_base / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        elif latest_link.exists():
            # It's a real directory, don't touch it
            return
        latest_link.symlink_to(self.root.name)

    def organize_prompts_by_occupation(self, prompts: list) -> None:
        """Organize prompts into occupation subdirectories."""
        for prompt in prompts:
            occ_dir = self.root / "prompts" / "prompts_by_occupation" / prompt["occupation_code"]
            occ_dir.mkdir(exist_ok=True)
            with open(occ_dir / f"{prompt['prompt_id']}.json", 'w') as f:
                json.dump(prompt, f, indent=2, default=str)

    def organize_prompts_by_industry(self, prompts: list) -> None:
        """Organize prompts into industry subdirectories."""
        for prompt in prompts:
            ind_dir = self.root / "prompts" / "prompts_by_industry" / prompt["naics_sector"]
            ind_dir.mkdir(exist_ok=True)
            with open(ind_dir / f"{prompt['prompt_id']}.json", 'w') as f:
                json.dump(prompt, f, indent=2, default=str)
```

---

## 15. Bias Detection (Complete with Format Bias)

```python
# src/analysis/bias_detection.py

from dataclasses import dataclass
from typing import List, Dict, TYPE_CHECKING
from scipy import stats
import numpy as np

if TYPE_CHECKING:
    from ..storage.database import ResultsDatabase

@dataclass
class BiasResult:
    """Result of bias detection."""
    bias_type: str
    detected: bool
    p_value: float
    effect_size: float
    details: str
    recommendation: str

class BiasDetector:
    """Detect various biases in evaluation results per PROMPT.md."""

    async def detect_all_biases(
        self,
        db: "ResultsDatabase"
    ) -> List[BiasResult]:
        """Run all bias detection tests."""
        results = []
        results.append(await self.detect_position_bias(db))
        results.append(await self.detect_length_bias(db))
        results.append(await self.detect_format_bias(db))
        results.append(await self.detect_model_fingerprinting(db))
        results.append(await self.detect_formality_drift(db))
        return results

    async def detect_position_bias(
        self,
        db: "ResultsDatabase"
    ) -> BiasResult:
        """Detect if position (A vs B) affects judging."""
        votes = await db.get_all_votes()

        a_wins = sum(1 for v in votes if v["gemini_position"] == "A" and v["winner"] == "gemini")
        b_wins = sum(1 for v in votes if v["gemini_position"] == "B" and v["winner"] == "gemini")
        a_total = sum(1 for v in votes if v["gemini_position"] == "A")
        b_total = sum(1 for v in votes if v["gemini_position"] == "B")

        if a_total == 0 or b_total == 0:
            return BiasResult(
                bias_type="position",
                detected=False,
                p_value=1.0,
                effect_size=0.0,
                details="Insufficient data for position bias test",
                recommendation=""
            )

        a_rate = a_wins / a_total
        b_rate = b_wins / b_total

        # Chi-squared test
        contingency = [[a_wins, a_total - a_wins], [b_wins, b_total - b_wins]]
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)

        # Effect size (Cohen's h)
        import math
        effect_size = abs(2 * math.asin(math.sqrt(a_rate)) - 2 * math.asin(math.sqrt(b_rate)))

        detected = p_value < 0.05 and effect_size > 0.1

        return BiasResult(
            bias_type="position",
            detected=detected,
            p_value=p_value,
            effect_size=effect_size,
            details=f"Win rate when Gemini is A: {a_rate:.1%}, when B: {b_rate:.1%}",
            recommendation="Consider weighting results or excluding biased judges" if detected else ""
        )

    async def detect_length_bias(
        self,
        db: "ResultsDatabase"
    ) -> BiasResult:
        """Detect if longer responses win more often."""
        comparisons = await db.get_comparisons_with_lengths()

        longer_wins = 0
        shorter_wins = 0

        for c in comparisons:
            gemini_len = c["gemini_word_count"]
            comp_len = c["competitor_word_count"]
            winner = c["final_winner"]

            if winner == "tie":
                continue

            if gemini_len > comp_len:
                if winner == "gemini":
                    longer_wins += 1
                else:
                    shorter_wins += 1
            elif comp_len > gemini_len:
                if winner == "competitor":
                    longer_wins += 1
                else:
                    shorter_wins += 1

        total = longer_wins + shorter_wins
        if total < 10:
            return BiasResult(
                bias_type="length",
                detected=False,
                p_value=1.0,
                effect_size=0.0,
                details="Insufficient data for length bias test",
                recommendation=""
            )

        # Binomial test against 50%
        result = stats.binomtest(longer_wins, total, 0.5)

        longer_rate = longer_wins / total
        effect_size = abs(longer_rate - 0.5) * 2  # Simple effect size

        detected = result.pvalue < 0.05 and effect_size > 0.1

        return BiasResult(
            bias_type="length",
            detected=detected,
            p_value=result.pvalue,
            effect_size=effect_size,
            details=f"Longer response wins {longer_rate:.1%} of the time (n={total})",
            recommendation="Judges may favor verbosity - consider length normalization" if detected else ""
        )

    async def detect_format_bias(
        self,
        db: "ResultsDatabase"
    ) -> BiasResult:
        """Detect if one model overuses certain structures (bullets, headers)."""
        responses = await db.get_all_responses_with_metrics()

        gemini_bullets = []
        competitor_bullets = []
        gemini_headers = []
        competitor_headers = []

        for r in responses:
            if r["model_type"] == "gemini":
                gemini_bullets.append(r["bullet_count"])
                gemini_headers.append(r["header_count"])
            else:
                competitor_bullets.append(r["bullet_count"])
                competitor_headers.append(r["header_count"])

        if len(gemini_bullets) < 10 or len(competitor_bullets) < 10:
            return BiasResult(
                bias_type="format",
                detected=False,
                p_value=1.0,
                effect_size=0.0,
                details="Insufficient data for format bias test",
                recommendation=""
            )

        # Mann-Whitney U test for bullets
        stat, p_bullet = stats.mannwhitneyu(gemini_bullets, competitor_bullets, alternative='two-sided')

        # Effect size (Cohen's d approximation)
        mean_diff = abs(np.mean(gemini_bullets) - np.mean(competitor_bullets))
        pooled_std = np.sqrt((np.std(gemini_bullets)**2 + np.std(competitor_bullets)**2) / 2)
        effect_size = mean_diff / pooled_std if pooled_std > 0 else 0

        detected = p_bullet < 0.05 and effect_size > 0.2

        return BiasResult(
            bias_type="format",
            detected=detected,
            p_value=p_bullet,
            effect_size=effect_size,
            details=f"Gemini avg bullets: {np.mean(gemini_bullets):.1f}, Competitor: {np.mean(competitor_bullets):.1f}",
            recommendation="Models show different formatting styles - may affect judging" if detected else ""
        )

    async def detect_model_fingerprinting(
        self,
        db: "ResultsDatabase"
    ) -> BiasResult:
        """Detect if judges can identify which model produced a response."""
        # This is detected by checking if self-judging shows bias
        votes = await db.get_votes_by_judge()

        self_judge_wins = {}  # judge_model -> {gemini_wins, total}

        for judge_model, judge_votes in votes.items():
            # Check if this judge model is also being evaluated
            gemini_wins = 0
            total = 0

            for v in judge_votes:
                # If judge is same family as one of the models
                judge_family = judge_model.split("/")[0]
                gemini_family = v["gemini_model"].split("/")[0]

                if judge_family == gemini_family:
                    total += 1
                    if v["winner"] == "gemini":
                        gemini_wins += 1

            if total >= 10:
                self_judge_wins[judge_model] = {"wins": gemini_wins, "total": total}

        if not self_judge_wins:
            return BiasResult(
                bias_type="model_fingerprinting",
                detected=False,
                p_value=1.0,
                effect_size=0.0,
                details="No self-judging scenarios found",
                recommendation=""
            )

        # Test each self-judge scenario
        max_effect = 0
        min_p = 1.0
        details = []

        for judge, stats_dict in self_judge_wins.items():
            rate = stats_dict["wins"] / stats_dict["total"]
            result = stats.binomtest(stats_dict["wins"], stats_dict["total"], 0.5)
            effect = abs(rate - 0.5) * 2

            if effect > max_effect:
                max_effect = effect
            if result.pvalue < min_p:
                min_p = result.pvalue

            details.append(f"{judge}: {rate:.1%} win rate (n={stats_dict['total']})")

        detected = min_p < 0.05 and max_effect > 0.15

        return BiasResult(
            bias_type="model_fingerprinting",
            detected=detected,
            p_value=min_p,
            effect_size=max_effect,
            details="; ".join(details),
            recommendation="Judges may recognize their own model's outputs" if detected else ""
        )

    async def detect_formality_drift(
        self,
        db: "ResultsDatabase"
    ) -> BiasResult:
        """Detect if models consistently over/under-formalize."""
        responses = await db.get_responses_with_prompts()

        gemini_drift = []  # (requested_formality, detected_formality)
        competitor_drift = []

        for r in responses:
            requested = r["formality_level"]
            # Use greeting/signoff as proxy for formality
            detected = self._estimate_formality(r["greeting_type"], r["signoff_type"])

            drift = detected - requested

            if r["model_type"] == "gemini":
                gemini_drift.append(drift)
            else:
                competitor_drift.append(drift)

        if len(gemini_drift) < 10 or len(competitor_drift) < 10:
            return BiasResult(
                bias_type="formality_drift",
                detected=False,
                p_value=1.0,
                effect_size=0.0,
                details="Insufficient data for formality drift test",
                recommendation=""
            )

        gemini_mean = np.mean(gemini_drift)
        comp_mean = np.mean(competitor_drift)

        stat, p_value = stats.ttest_ind(gemini_drift, competitor_drift)
        effect_size = abs(gemini_mean - comp_mean)

        detected = p_value < 0.05 and effect_size > 0.5

        return BiasResult(
            bias_type="formality_drift",
            detected=detected,
            p_value=p_value,
            effect_size=effect_size,
            details=f"Gemini avg drift: {gemini_mean:+.1f}, Competitor: {comp_mean:+.1f}",
            recommendation="Models interpret formality requirements differently" if detected else ""
        )

    def _estimate_formality(self, greeting: str, signoff: str) -> int:
        """Estimate formality from greeting/signoff types."""
        score = 3  # Default middle

        greeting_scores = {"formal": 5, "semiformal": 3, "casual": 1, None: 3}
        signoff_scores = {"formal": 5, "semiformal": 3, "casual": 1, None: 3}

        return (greeting_scores.get(greeting, 3) + signoff_scores.get(signoff, 3)) / 2
```

---

## 16. CLI Implementation (Complete)

```python
# src/cli.py

import asyncio
import sys
from pathlib import Path
from typing import Optional
import typer

from .config.presets import PRESETS, EvalConfig
from .config.cost_estimator import estimate_cost, format_cost_estimate

app = typer.Typer(help="Gemini Writing Evaluation Framework")

@app.command()
def run(
    preset: int = typer.Option(6, "--preset", "-p", help="Preset level 1-10"),
    prompts: Optional[int] = typer.Option(None, "--prompts", "-n", help="Override number of prompts"),
    models: Optional[str] = typer.Option(None, "--models", "-m", help="Comma-separated model pairs"),
    occupations: Optional[str] = typer.Option(None, "--occupations", help="O*NET occupation filter"),
    industries: Optional[str] = typer.Option(None, "--industries", help="NAICS industry filter"),
    judges: Optional[str] = typer.Option(None, "--judges", help="Judge models to use"),
    votes: Optional[int] = typer.Option(None, "--votes", help="Votes per judge"),
    resume: Optional[Path] = typer.Option(None, "--resume", "-r", help="Resume from checkpoint"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show estimate without running"),
    output_dir: Path = typer.Option(Path("results"), "--output", "-o", help="Output directory"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    no_tui: bool = typer.Option(False, "--no-tui", help="Disable TUI progress display"),
):
    """Run an evaluation with specified configuration."""

    # Build config from preset + overrides
    if preset < 1 or preset > 10:
        typer.echo("Error: Preset must be between 1 and 10", err=True)
        raise typer.Exit(1)

    config = PRESETS[preset]

    # Apply overrides
    if prompts:
        config.num_prompts = prompts
    if votes:
        config.judge_config.votes_per_judge = votes
    if seed:
        config.random_seed = seed

    # Show estimate
    estimate = estimate_cost(config)
    typer.echo(format_cost_estimate(estimate, config))

    if dry_run:
        typer.echo("\n--dry-run specified, not running evaluation.")
        raise typer.Exit(0)

    # Confirm before running
    if estimate.total_cost > 10:
        if not typer.confirm(f"\nEstimated cost is ${estimate.total_cost:.2f}. Continue?"):
            raise typer.Exit(0)

    # Run the evaluation
    from .eval.engine import EvaluationEngine

    engine = EvaluationEngine(config, output_dir, resume_from=resume, enable_tui=not no_tui)
    asyncio.run(engine.run())

@app.command()
def view(
    run_dir: Path = typer.Argument(..., help="Path to results directory"),
):
    """Interactive results viewer."""
    from .tui.results_viewer import ResultsViewerApp

    if not run_dir.exists():
        typer.echo(f"Error: Directory not found: {run_dir}", err=True)
        raise typer.Exit(1)

    app = ResultsViewerApp(run_dir)
    app.run()

@app.command()
def compare(
    run_dirs: list[Path] = typer.Argument(..., help="Paths to results directories to compare"),
):
    """Compare multiple evaluation runs."""
    from .analysis.cross_run_compare import compare_runs

    for d in run_dirs:
        if not d.exists():
            typer.echo(f"Error: Directory not found: {d}", err=True)
            raise typer.Exit(1)

    results = asyncio.run(compare_runs(run_dirs))
    typer.echo(results.format_summary())

@app.command()
def report(
    run_dir: Path = typer.Argument(..., help="Path to results directory"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output PDF path"),
):
    """Generate PDF report from evaluation results."""
    from .reports.pdf_generator import PDFReportGenerator

    if not run_dir.exists():
        typer.echo(f"Error: Directory not found: {run_dir}", err=True)
        raise typer.Exit(1)

    output_path = output or (run_dir / "reports" / "report.pdf")

    generator = PDFReportGenerator(run_dir, output_path)
    asyncio.run(generator.generate())

    typer.echo(f"Report generated: {output_path}")

@app.command()
def export(
    run_dir: Path = typer.Argument(..., help="Path to results directory"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv, json, parquet"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export evaluation results to various formats."""
    from .storage.exporter import ResultsExporter

    if not run_dir.exists():
        typer.echo(f"Error: Directory not found: {run_dir}", err=True)
        raise typer.Exit(1)

    exporter = ResultsExporter(run_dir)

    if format == "csv":
        output_path = output or (run_dir / "results_export.csv")
        asyncio.run(exporter.to_csv(output_path))
    elif format == "json":
        output_path = output or (run_dir / "results_export.json")
        asyncio.run(exporter.to_json(output_path))
    elif format == "parquet":
        output_path = output or (run_dir / "results_export.parquet")
        asyncio.run(exporter.to_parquet(output_path))
    else:
        typer.echo(f"Error: Unknown format: {format}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Exported to: {output_path}")

@app.command()
def weaknesses(
    run_dir: Path = typer.Argument(..., help="Path to results directory"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Specific Gemini model"),
):
    """Analyze and report weaknesses."""
    from .analysis.weakness_finder import WeaknessFinder
    from .storage.database import ResultsDatabase

    if not run_dir.exists():
        typer.echo(f"Error: Directory not found: {run_dir}", err=True)
        raise typer.Exit(1)

    db = ResultsDatabase(run_dir / "results.db")
    finder = WeaknessFinder()

    # Default to first Gemini model if not specified
    if not model:
        model = "google/gemini-3.0-pro"

    report = asyncio.run(finder.find_weaknesses(db, model))
    typer.echo(finder.format_weakness_report(report))

def main():
    app()

if __name__ == "__main__":
    main()
```

---

## 17. TUI Progress Dashboard (Complete per PROMPT.md)

```python
# src/tui/progress_dashboard.py

from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer, ProgressBar, DataTable, Log
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from typing import Dict, List
import asyncio

class ModelPairProgress(Static):
    """Progress widget for a single model pair."""

    completed: reactive[int] = reactive(0)
    total: reactive[int] = reactive(0)
    gemini_wins: reactive[int] = reactive(0)
    competitor_wins: reactive[int] = reactive(0)
    ties: reactive[int] = reactive(0)

    def __init__(self, gemini_model: str, competitor_model: str, **kwargs):
        super().__init__(**kwargs)
        self.gemini_model = gemini_model.split("/")[-1]
        self.competitor_model = competitor_model.split("/")[-1]

    def render(self) -> str:
        if self.total == 0:
            pct = 0
            bar = "░" * 20
        else:
            pct = self.completed / self.total
            filled = int(20 * pct)
            bar = "█" * filled + "░" * (20 - filled)

        decisive = self.gemini_wins + self.competitor_wins
        win_pct = self.gemini_wins / decisive if decisive > 0 else 0.5

        return (
            f"{self.gemini_model:20} vs {self.competitor_model:20} "
            f"|{bar}| {self.completed:4}/{self.total:4} "
            f"[{win_pct:.0%} win]"
        )

class CurrentBatchStatus(Static):
    """Shows current batch processing status."""

    current_prompt: reactive[str] = reactive("")
    current_phase: reactive[str] = reactive("idle")
    response_a_status: reactive[str] = reactive("pending")
    response_b_status: reactive[str] = reactive("pending")
    judging_status: reactive[str] = reactive("pending")

    def render(self) -> str:
        return f"""Current: {self.current_prompt[:40]}...
Phase: {self.current_phase}
  Response A: {self.response_a_status}
  Response B: {self.response_b_status}
  Judging:    {self.judging_status}"""

class LiveStats(Static):
    """Live statistics widget."""

    total_comparisons: reactive[int] = reactive(0)
    gemini_wins: reactive[int] = reactive(0)
    competitor_wins: reactive[int] = reactive(0)
    ties: reactive[int] = reactive(0)
    errors: reactive[int] = reactive(0)
    elapsed_seconds: reactive[int] = reactive(0)

    def render(self) -> str:
        total = self.gemini_wins + self.competitor_wins + self.ties
        win_rate = self.gemini_wins / total if total > 0 else 0

        hours = self.elapsed_seconds // 3600
        minutes = (self.elapsed_seconds % 3600) // 60
        seconds = self.elapsed_seconds % 60

        return f"""Live Statistics
═══════════════
Completed:    {self.total_comparisons:,}
Gemini wins:  {self.gemini_wins:,} ({win_rate:.1%})
Competitor:   {self.competitor_wins:,}
Ties:         {self.ties:,}
Errors:       {self.errors:,}
Elapsed:      {hours:02d}:{minutes:02d}:{seconds:02d}"""

class ErrorSummary(Static):
    """Error summary widget."""

    errors: reactive[list] = reactive([])

    def render(self) -> str:
        if not self.errors:
            return "No errors"

        lines = ["Recent Errors", "═" * 40]
        for err in self.errors[-5:]:
            lines.append(f"  {err['time']}: {err['message'][:50]}")

        return "\n".join(lines)

class ProgressDashboard(App):
    """Real-time progress dashboard per PROMPT.md."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 4;
        grid-rows: auto auto 1fr auto;
    }

    #header-container {
        column-span: 2;
    }

    #overall-progress {
        column-span: 2;
        height: auto;
        padding: 1;
    }

    #model-pairs {
        height: 100%;
        padding: 1;
    }

    #live-stats {
        height: 100%;
        padding: 1;
    }

    #current-batch {
        padding: 1;
    }

    #activity-log {
        height: 100%;
    }

    #error-summary {
        padding: 1;
    }

    .progress-label {
        text-style: bold;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "toggle_pause", "Pause"),
        ("d", "show_details", "Details"),
        ("s", "save_checkpoint", "Save"),
    ]

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.model_pair_widgets: Dict[str, ModelPairProgress] = {}
        self.is_paused = False

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="header-container"):
            yield Static(f"Gemini Writing Evaluation - {self.config.run_name}", classes="progress-label")

        with Container(id="overall-progress"):
            yield Static("Phase: Response Generation", id="phase-label")
            yield ProgressBar(id="main-progress", total=100)

        with Container(id="model-pairs"):
            yield Static("Model Pair Progress", classes="progress-label")
            for gemini, competitor in self.config.model_pairs:
                widget = ModelPairProgress(gemini, competitor)
                widget.total = self.config.num_prompts
                pair_id = f"{gemini}_{competitor}"
                self.model_pair_widgets[pair_id] = widget
                yield widget

        with Container(id="live-stats"):
            yield LiveStats(id="stats")

        with Container(id="current-batch"):
            yield CurrentBatchStatus(id="batch-status")

        with Vertical(id="activity-log"):
            yield Static("Activity Log", classes="progress-label")
            yield Log(id="log")

        with Container(id="error-summary"):
            yield ErrorSummary(id="errors")

        yield Footer()

    def action_toggle_pause(self):
        self.is_paused = not self.is_paused
        status = "PAUSED" if self.is_paused else "Running"
        self.query_one("#phase-label", Static).update(f"Phase: {status}")

    def action_save_checkpoint(self):
        log = self.query_one("#log", Log)
        log.write_line("Manual checkpoint save triggered...")

    # Update methods called by evaluation engine
    def update_progress(self, completed: int, total: int, phase: str):
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(progress=completed / total * 100 if total > 0 else 0)
        self.query_one("#phase-label", Static).update(f"Phase: {phase}")

    def update_model_pair(self, gemini: str, competitor: str, completed: int,
                          gemini_wins: int, competitor_wins: int, ties: int):
        pair_id = f"{gemini}_{competitor}"
        if pair_id in self.model_pair_widgets:
            widget = self.model_pair_widgets[pair_id]
            widget.completed = completed
            widget.gemini_wins = gemini_wins
            widget.competitor_wins = competitor_wins
            widget.ties = ties

    def update_stats(self, stats: Dict):
        stats_widget = self.query_one("#stats", LiveStats)
        stats_widget.total_comparisons = stats.get("total", 0)
        stats_widget.gemini_wins = stats.get("gemini_wins", 0)
        stats_widget.competitor_wins = stats.get("competitor_wins", 0)
        stats_widget.ties = stats.get("ties", 0)
        stats_widget.errors = stats.get("errors", 0)
        stats_widget.elapsed_seconds = stats.get("elapsed_seconds", 0)

    def update_current_batch(self, prompt_id: str, phase: str,
                             response_a: str, response_b: str, judging: str):
        batch = self.query_one("#batch-status", CurrentBatchStatus)
        batch.current_prompt = prompt_id
        batch.current_phase = phase
        batch.response_a_status = response_a
        batch.response_b_status = response_b
        batch.judging_status = judging

    def log_activity(self, message: str):
        log = self.query_one("#log", Log)
        log.write_line(message)

    def add_error(self, error: Dict):
        errors_widget = self.query_one("#errors", ErrorSummary)
        current = list(errors_widget.errors)
        current.append(error)
        errors_widget.errors = current[-10:]  # Keep last 10
```

---

## 18. Company and Name Data Sources

```python
# src/data/company_database.py

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
import random

@dataclass
class Company:
    """Company information."""
    name: str
    size: str  # startup, small, mid_market, enterprise, fortune_500
    industry_naics: str
    industry_name: str
    is_public: bool
    hq_location: Optional[str] = None
    employee_count: Optional[int] = None
    sector: Optional[str] = None

class CompanyDatabase:
    """Database of 500+ real companies per PROMPT.md.

    Data sources:
    - Fortune 500 list (public companies)
    - Inc. 5000 (fast-growing private companies)
    - Built-in LLM knowledge for real company data
    """

    def __init__(self, data_path: Path, seed: int = None):
        self.data_path = data_path
        self.rng = random.Random(seed)
        self._companies: List[Company] = []
        self._by_naics: Dict[str, List[Company]] = {}
        self._by_size: Dict[str, List[Company]] = {}

    def load(self) -> "CompanyDatabase":
        """Load company data from JSON file."""
        with open(self.data_path) as f:
            data = json.load(f)

        for c in data["companies"]:
            company = Company(**c)
            self._companies.append(company)

            # Index by NAICS sector (first 2 digits)
            sector = c["industry_naics"][:2]
            if sector not in self._by_naics:
                self._by_naics[sector] = []
            self._by_naics[sector].append(company)

            # Index by size
            if c["size"] not in self._by_size:
                self._by_size[c["size"]] = []
            self._by_size[c["size"]].append(company)

        return self

    def get_by_name(self, name: str) -> Optional[Company]:
        """Get company by exact name."""
        for c in self._companies:
            if c.name.lower() == name.lower():
                return c
        return None

    def sample_for_occupation(self, onet_code: str) -> Company:
        """Sample a plausible company for an occupation."""
        # Map SOC major group to likely NAICS sectors
        soc_to_naics = {
            "11": ["52", "54", "55"],  # Management -> Finance, Professional, Management
            "13": ["52", "54"],         # Business/Financial -> Finance, Professional
            "15": ["51", "54"],         # Computer/Math -> Information, Professional
            "17": ["23", "54"],         # Architecture/Engineering -> Construction, Professional
            "19": ["54", "62"],         # Life/Physical/Social Science -> Professional, Health
            "21": ["62", "92"],         # Community/Social Service -> Health, Government
            "23": ["54", "92"],         # Legal -> Professional, Government
            "25": ["61"],               # Education -> Educational Services
            "27": ["51", "71"],         # Arts/Media -> Information, Entertainment
            "29": ["62"],               # Healthcare Practitioners -> Health
            "31": ["62"],               # Healthcare Support -> Health
            "33": ["92"],               # Protective Service -> Government
            "35": ["72"],               # Food Prep -> Accommodation/Food
            "37": ["56", "81"],         # Building/Grounds -> Admin Support, Other Services
            "39": ["72", "81"],         # Personal Care -> Accommodation, Other Services
            "41": ["44", "45"],         # Sales -> Retail Trade
            "43": ["52", "54", "55"],   # Office/Admin -> Finance, Professional, Management
            "45": ["11"],               # Farming -> Agriculture
            "47": ["23"],               # Construction -> Construction
            "49": ["23", "31"],         # Installation/Maintenance -> Construction, Manufacturing
            "51": ["31", "32", "33"],   # Production -> Manufacturing
            "53": ["48", "49"],         # Transportation -> Transportation/Warehousing
        }

        soc_major = onet_code[:2]
        likely_sectors = soc_to_naics.get(soc_major, ["54"])  # Default to Professional

        # Try to find a company in these sectors
        for sector in likely_sectors:
            if sector in self._by_naics and self._by_naics[sector]:
                return self.rng.choice(self._by_naics[sector])

        # Fallback to any company
        return self.rng.choice(self._companies)

    def sample_by_size(self, size: str) -> Company:
        """Sample a company of a specific size."""
        if size in self._by_size and self._by_size[size]:
            return self.rng.choice(self._by_size[size])
        return self.rng.choice(self._companies)
```

```python
# src/data/name_generator.py

import json
from pathlib import Path
from typing import Optional, Tuple
import random

class NameGenerator:
    """Generate diverse, realistic names per PROMPT.md.

    Uses Census data for demographic accuracy:
    - First names from SSA baby names + Census ethnic names
    - Last names from Census surname data
    - Tracks diversity to ensure representation
    """

    def __init__(self, data_path: Path, seed: int = None):
        self.data_path = data_path
        self.rng = random.Random(seed)
        self._first_names: dict = {}  # gender -> [names]
        self._last_names: list = []
        self._generated: set = set()  # Track to avoid duplicates

    def load(self) -> "NameGenerator":
        """Load name data from Census JSON."""
        with open(self.data_path) as f:
            data = json.load(f)

        self._first_names = data.get("first_names", {
            "male": ["James", "John", "Robert", "Michael", "David"],
            "female": ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth"],
            "neutral": ["Alex", "Jordan", "Taylor", "Morgan", "Casey"]
        })

        self._last_names = data.get("last_names", [
            "Smith", "Johnson", "Williams", "Brown", "Jones",
            "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin",
            "Lee", "Perez", "Thompson", "White", "Harris",
            "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
            "Chen", "Kim", "Patel", "Nguyen", "Shah"
        ])

        return self

    def generate(
        self,
        gender: Optional[str] = None,
        generation: Optional[str] = None
    ) -> Tuple[str, str]:
        """Generate a unique first + last name combination."""
        # Select gender if not specified
        if gender is None:
            gender = self.rng.choice(["male", "female", "neutral"])

        # Get appropriate first names
        first_pool = self._first_names.get(gender, self._first_names.get("neutral", ["Alex"]))

        # Try to generate unique combination
        for _ in range(100):  # Max attempts
            first = self.rng.choice(first_pool)
            last = self.rng.choice(self._last_names)
            full = f"{first} {last}"

            if full not in self._generated:
                self._generated.add(full)
                return first, last

        # Fallback: add a number suffix
        first = self.rng.choice(first_pool)
        last = self.rng.choice(self._last_names)
        return first, last

    def generate_full_name(self, **kwargs) -> str:
        """Generate a full name as a single string."""
        first, last = self.generate(**kwargs)
        return f"{first} {last}"
```

---

## 19. Key Decisions and Clarifications (From Simulations)

### 19.1 Communication Channels

Per PROMPT.md: "Avoid hardcoding specific categories". Communication channels are:
- Stored as free-form strings (NOT enum)
- Inferred from O*NET task context
- Enriched in Phase 3 if ambiguous
- Tracked for analysis but not constrained

### 19.2 Hardcoded Categories Avoided

The following are explicitly NOT hardcoded:
- Writing categories (let O*NET tasks drive this)
- Communication channels
- Industry sectors (derived from NAICS)
- Occupation types (derived from SOC codes)

### 19.3 Temporal Context

Per PROMPT.md: "Today's date should be January 6, 2026"
- All temporal context uses this date
- Deadlines are relative to this date
- Historical references are plausible for this date

### 19.4 Judge Aggregation Clarification

The majority-of-majorities works as follows:
1. Each judge MODEL (not persona) gets votes from BOTH personas combined
2. Take majority across all votes for that judge model
3. Take majority across the 3 judge models
4. Final winner is majority of judge model majorities

### 19.5 Auto-Loss on Failure

Per PROMPT.md: "Model failures or refusals automatically lose"
- If model times out: auto-loss
- If model refuses: auto-loss
- If model produces empty response: auto-loss
- Track refusal reasons for analysis

---

## 20. Implementation Checklist

### Phase 1: Foundation (Week 1)
- [ ] Project setup with pyproject.toml
- [ ] Core exceptions and base classes
- [ ] OpenRouter client with rate limiting
- [ ] Circuit breaker implementation
- [ ] Configuration and presets
- [ ] Cost estimator

### Phase 2: Data Layer (Week 1-2)
- [ ] O*NET extractor and schema
- [ ] Company database with 500+ companies
- [ ] Name generator with Census data
- [ ] NAICS mapper

### Phase 3: Prompt Generation (Week 2)
- [ ] Phase 1 offline generation
- [ ] Phase 2 algorithmic combination
- [ ] Phase 3 LLM enrichment
- [ ] Constraint generator
- [ ] Revision task generator
- [ ] CC/ambiguity generators

### Phase 4: Evaluation Engine (Week 2-3)
- [ ] Main evaluation orchestrator
- [ ] Judge prompt builder
- [ ] Judge response parser
- [ ] Vote aggregator
- [ ] Compliance tracker
- [ ] Response analyzer

### Phase 5: Storage (Week 3)
- [ ] SQLite database schema
- [ ] Checkpoint manager with signal handlers
- [ ] Run directory structure
- [ ] Failure logger

### Phase 6: Analysis (Week 3-4)
- [ ] Statistical analysis (Wilson CI, binomtest)
- [ ] Bias detection (all 5 types)
- [ ] Weakness finder
- [ ] Cross-run comparison

### Phase 7: TUI and Reports (Week 4)
- [ ] Progress dashboard
- [ ] Results viewer
- [ ] PDF report generator
- [ ] Chart generation
- [ ] Heatmaps

### Phase 8: CLI and Integration (Week 4)
- [ ] All CLI commands
- [ ] End-to-end testing
- [ ] Documentation

---

## 21. Testing Strategy

### Unit Tests
- Vote aggregator (critical for correctness)
- Judge parser (handle all edge cases)
- Compliance tracker (constraint checking)
- Statistical functions (verify math)

### Integration Tests
- Mock OpenRouter responses
- Full pipeline with small preset
- Resume from checkpoint
- Cross-run comparison

### End-to-End Tests
- Preset 1 (5 prompts) - fast sanity check
- Preset 2 (20 prompts) - full flow validation

---

## 22. Conclusion

This final master plan incorporates all learnings from 6 implementation simulations:

1. **Complete API Client**: Full OpenRouter implementation with rate limiting and circuit breaker
2. **Complete Parsers**: Judge response parser with fallback handling
3. **Complete Analysis**: Weakness finder, bias detection (all 5 types), format detection
4. **Complete TUI**: Per-model-pair progress, batch status, error summary
5. **Complete CLI**: All commands including --dry-run, filters, resume
6. **Fixed Vote Aggregation**: Correctly handles judge model vs persona aggregation
7. **Complete Checkpoint System**: Signal handlers, atomic writes, mid-comparison resume
8. **All PROMPT.md Requirements**: 100% coverage verified

The plan is ready for implementation.
