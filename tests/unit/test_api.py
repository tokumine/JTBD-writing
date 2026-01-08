"""Tests for API layer modules."""
import asyncio
from datetime import datetime, timedelta

import pytest

from src.api.circuit_breaker import CircuitBreaker, CircuitState
from src.api.rate_limiter import MultiServiceRateLimiter, TokenBucketRateLimiter
from src.api.token_counter import TokenCounter


class TestTokenBucketRateLimiter:
    """Tests for rate limiter."""

    @pytest.mark.asyncio
    async def test_acquire_available_tokens(self) -> None:
        """Test acquiring when tokens are available."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60)

        wait_time = await limiter.acquire(1.0)
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_try_acquire_success(self) -> None:
        """Test try_acquire when tokens available."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60)

        success = await limiter.try_acquire(1.0)
        assert success is True

    @pytest.mark.asyncio
    async def test_try_acquire_failure(self) -> None:
        """Test try_acquire when no tokens available."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=1)

        # Take the only token
        await limiter.acquire(1.0)

        # Should fail immediately
        success = await limiter.try_acquire(1.0)
        assert success is False

    @pytest.mark.asyncio
    async def test_refill(self) -> None:
        """Test token refill over time."""
        limiter = TokenBucketRateLimiter(requests_per_minute=6000, burst_size=10)

        # Take all tokens
        for _ in range(10):
            await limiter.acquire(1.0)

        # Wait for refill (100 tokens/sec)
        await asyncio.sleep(0.1)

        # Should have refilled some tokens
        success = await limiter.try_acquire(5.0)
        assert success is True

    def test_get_status(self) -> None:
        """Test getting limiter status."""
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=10)
        status = limiter.get_status()

        assert status.max_tokens == 10.0
        assert status.refill_rate == 1.0  # 60 per minute = 1 per second


class TestMultiServiceRateLimiter:
    """Tests for multi-service rate limiter."""

    @pytest.mark.asyncio
    async def test_separate_services(self) -> None:
        """Test that services have separate limiters."""
        limiter = MultiServiceRateLimiter(default_rpm=60)

        # Acquire from different services
        wait1 = await limiter.acquire("service_a")
        wait2 = await limiter.acquire("service_b")

        assert wait1 == 0.0
        assert wait2 == 0.0

    def test_get_all_statuses(self) -> None:
        """Test getting all service statuses."""
        limiter = MultiServiceRateLimiter(default_rpm=60)
        limiter.get_limiter("service_a")
        limiter.get_limiter("service_b")

        statuses = limiter.get_all_statuses()
        assert "service_a" in statuses
        assert "service_b" in statuses


class TestCircuitBreaker:
    """Tests for circuit breaker."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self) -> None:
        """Test circuit starts closed."""
        breaker = CircuitBreaker()
        status = breaker.get_status("test_service")

        assert status.state == CircuitState.CLOSED
        assert status.failure_count == 0

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self) -> None:
        """Test requests allowed when closed."""
        breaker = CircuitBreaker()

        can_execute = await breaker.can_execute("test_service")
        assert can_execute is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self) -> None:
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Record failures
        for _ in range(3):
            await breaker.record_failure("test_service")

        status = breaker.get_status("test_service")
        assert status.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rejects_when_open(self) -> None:
        """Test requests rejected when open."""
        breaker = CircuitBreaker(failure_threshold=1)

        await breaker.record_failure("test_service")

        can_execute = await breaker.can_execute("test_service")
        assert can_execute is False

    @pytest.mark.asyncio
    async def test_success_resets_count(self) -> None:
        """Test success resets failure count."""
        breaker = CircuitBreaker(failure_threshold=3)

        await breaker.record_failure("test_service")
        await breaker.record_failure("test_service")
        await breaker.record_success("test_service")

        status = breaker.get_status("test_service")
        assert status.failure_count == 0
        assert status.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_transition(self) -> None:
        """Test transition to half-open after timeout."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,  # 100ms
        )

        await breaker.record_failure("test_service")
        await asyncio.sleep(0.15)  # Wait for recovery

        can_execute = await breaker.can_execute("test_service")
        assert can_execute is True

        status = breaker.get_status("test_service")
        assert status.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self) -> None:
        """Test half-open closes after successful requests."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_requests=2,
        )

        await breaker.record_failure("test_service")
        await asyncio.sleep(0.02)

        # Trigger transition to half-open
        await breaker.can_execute("test_service")

        # Record successes
        await breaker.record_success("test_service")
        await breaker.record_success("test_service")

        status = breaker.get_status("test_service")
        assert status.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_opens_on_failure(self) -> None:
        """Test half-open returns to open on failure."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
        )

        await breaker.record_failure("test_service")
        await asyncio.sleep(0.02)

        # Trigger transition to half-open
        await breaker.can_execute("test_service")

        # Record another failure
        await breaker.record_failure("test_service")

        status = breaker.get_status("test_service")
        assert status.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_manual_reset(self) -> None:
        """Test manually resetting a circuit."""
        breaker = CircuitBreaker(failure_threshold=1)

        await breaker.record_failure("test_service")
        assert breaker.get_status("test_service").state == CircuitState.OPEN

        await breaker.reset("test_service")
        assert breaker.get_status("test_service").state == CircuitState.CLOSED

    def test_get_all_statuses(self) -> None:
        """Test getting all service statuses."""
        breaker = CircuitBreaker()
        breaker.get_status("service_a")
        breaker.get_status("service_b")

        # Just getting status shouldn't create entries
        statuses = breaker.get_all_statuses()
        assert len(statuses) == 0  # No failures recorded yet


class TestTokenCounter:
    """Tests for token counting."""

    def test_count_tokens_openai(self) -> None:
        """Test counting tokens for OpenAI model."""
        counter = TokenCounter()
        count = counter.count_tokens(
            "Hello, world! This is a test.",
            "openai/gpt-4",
        )

        assert count > 0
        assert count < 100  # Should be around 8-10 tokens

    def test_count_tokens_unknown_provider(self) -> None:
        """Test fallback for unknown provider."""
        counter = TokenCounter()
        text = "Hello, world!"
        count = counter.count_tokens(text, "unknown/model")

        # Fallback uses character count / 4
        expected = max(1, len(text) // 4)
        assert count == expected

    def test_estimate_response_tokens(self) -> None:
        """Test response token estimation."""
        counter = TokenCounter()

        # Short email
        short = counter.estimate_response_tokens("email", "short")
        # Long report
        long = counter.estimate_response_tokens("report", "long")

        assert short < long
        assert short == 100  # 200 * 0.5
        assert long == 1000  # 500 * 2.0

    def test_estimate_cost(self) -> None:
        """Test cost estimation."""
        counter = TokenCounter()
        cost = counter.estimate_cost(
            input_tokens=1000,
            output_tokens=500,
            model_id="anthropic/claude-opus-4.5",
        )

        # 1K input @ $0.015/1K + 0.5K output @ $0.075/1K
        expected = 0.015 + 0.0375
        assert abs(cost - expected) < 0.001

    def test_estimate_cost_unknown_model(self) -> None:
        """Test cost estimation with unknown model."""
        counter = TokenCounter()
        cost = counter.estimate_cost(
            input_tokens=1000,
            output_tokens=1000,
            model_id="unknown/model",
        )

        # Should use conservative default
        assert cost > 0
