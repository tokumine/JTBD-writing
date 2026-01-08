"""Thread-safe circuit breaker for API resilience."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStatus:
    """Current circuit breaker status."""

    state: CircuitState
    failure_count: int
    last_failure: datetime | None
    next_retry: datetime | None


class CircuitBreaker:
    """Thread-safe circuit breaker with hierarchical support."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before trying recovery
            half_open_requests: Successful requests needed to close
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.half_open_requests = half_open_requests

        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, CircuitState] = {}
        self._failure_counts: dict[str, int] = {}
        self._last_failures: dict[str, datetime] = {}
        self._half_open_successes: dict[str, int] = {}

    async def _get_lock(self, service_id: str) -> asyncio.Lock:
        """Get or create lock for service."""
        if service_id not in self._locks:
            self._locks[service_id] = asyncio.Lock()
        return self._locks[service_id]

    async def can_execute(self, service_id: str) -> bool:
        """Check if request should be allowed."""
        lock = await self._get_lock(service_id)
        async with lock:
            state = self._states.get(service_id, CircuitState.CLOSED)

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                last_failure = self._last_failures.get(service_id)
                if last_failure and datetime.now() - last_failure >= self.recovery_timeout:
                    self._states[service_id] = CircuitState.HALF_OPEN
                    self._half_open_successes[service_id] = 0
                    return True
                return False

            if state == CircuitState.HALF_OPEN:
                return True  # Allow probe requests

            return False

    async def record_success(self, service_id: str) -> None:
        """Record successful request."""
        lock = await self._get_lock(service_id)
        async with lock:
            state = self._states.get(service_id, CircuitState.CLOSED)

            if state == CircuitState.HALF_OPEN:
                self._half_open_successes[service_id] = (
                    self._half_open_successes.get(service_id, 0) + 1
                )

                if self._half_open_successes[service_id] >= self.half_open_requests:
                    self._states[service_id] = CircuitState.CLOSED
                    self._failure_counts[service_id] = 0

            elif state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_counts[service_id] = 0

    async def record_failure(self, service_id: str) -> None:
        """Record failed request."""
        lock = await self._get_lock(service_id)
        async with lock:
            state = self._states.get(service_id, CircuitState.CLOSED)

            if state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._states[service_id] = CircuitState.OPEN
                self._last_failures[service_id] = datetime.now()

            elif state == CircuitState.CLOSED:
                self._failure_counts[service_id] = (
                    self._failure_counts.get(service_id, 0) + 1
                )

                if self._failure_counts[service_id] >= self.failure_threshold:
                    self._states[service_id] = CircuitState.OPEN
                    self._last_failures[service_id] = datetime.now()

    def get_status(self, service_id: str) -> CircuitStatus:
        """Get current status for display."""
        state = self._states.get(service_id, CircuitState.CLOSED)
        failure_count = self._failure_counts.get(service_id, 0)
        last_failure = self._last_failures.get(service_id)

        next_retry = None
        if state == CircuitState.OPEN and last_failure:
            next_retry = last_failure + self.recovery_timeout

        return CircuitStatus(
            state=state,
            failure_count=failure_count,
            last_failure=last_failure,
            next_retry=next_retry,
        )

    def get_all_statuses(self) -> dict[str, CircuitStatus]:
        """Get status for all tracked services."""
        all_services = set(self._states.keys()) | set(self._failure_counts.keys())
        return {s: self.get_status(s) for s in all_services}

    async def reset(self, service_id: str) -> None:
        """Manually reset a circuit."""
        lock = await self._get_lock(service_id)
        async with lock:
            self._states[service_id] = CircuitState.CLOSED
            self._failure_counts[service_id] = 0
            self._half_open_successes[service_id] = 0
