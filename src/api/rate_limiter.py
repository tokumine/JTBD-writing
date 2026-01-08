"""Token bucket rate limiter for API requests."""
import asyncio
import time
from dataclasses import dataclass


@dataclass
class RateLimiterStatus:
    """Current status of the rate limiter."""

    available_tokens: float
    max_tokens: float
    refill_rate: float  # tokens per second
    last_refill: float


class TokenBucketRateLimiter:
    """Token bucket rate limiter with async support."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int | None = None,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum sustained request rate
            burst_size: Maximum burst size (defaults to requests_per_minute)
        """
        self.max_tokens = float(burst_size or requests_per_minute)
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self._tokens = self.max_tokens
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            # Calculate wait time
            deficit = tokens - self._tokens
            wait_time = deficit / self.refill_rate

            # Wait and then take tokens
            await asyncio.sleep(wait_time)
            self._refill()
            self._tokens -= tokens

            return wait_time

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.max_tokens,
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_refill = now

    def get_status(self) -> RateLimiterStatus:
        """Get current status."""
        return RateLimiterStatus(
            available_tokens=self._tokens,
            max_tokens=self.max_tokens,
            refill_rate=self.refill_rate,
            last_refill=self._last_refill,
        )


class MultiServiceRateLimiter:
    """Rate limiter for multiple services."""

    def __init__(self, default_rpm: int = 60):
        """Initialize with default rate limit."""
        self.default_rpm = default_rpm
        self._limiters: dict[str, TokenBucketRateLimiter] = {}

    def get_limiter(self, service_id: str) -> TokenBucketRateLimiter:
        """Get or create limiter for a service."""
        if service_id not in self._limiters:
            self._limiters[service_id] = TokenBucketRateLimiter(
                requests_per_minute=self.default_rpm
            )
        return self._limiters[service_id]

    async def acquire(self, service_id: str, tokens: float = 1.0) -> float:
        """Acquire tokens for a service."""
        limiter = self.get_limiter(service_id)
        return await limiter.acquire(tokens)

    def get_all_statuses(self) -> dict[str, RateLimiterStatus]:
        """Get status for all services."""
        return {sid: lim.get_status() for sid, lim in self._limiters.items()}
