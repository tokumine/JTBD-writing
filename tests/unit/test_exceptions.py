"""Tests for exception classes."""
import pytest

from src.exceptions import (
    APIError,
    BudgetExceededError,
    CheckpointError,
    CircuitOpenError,
    ConfigurationError,
    DataNotFoundError,
    GeminiEvalError,
    ModelNotFoundError,
    ParseError,
    RateLimitError,
    ValidationError,
)


class TestGeminiEvalError:
    """Tests for base exception."""

    def test_base_exception(self) -> None:
        """Test base exception can be raised."""
        with pytest.raises(GeminiEvalError) as exc_info:
            raise GeminiEvalError("Test error")
        assert str(exc_info.value) == "Test error"

    def test_inheritance(self) -> None:
        """Test all exceptions inherit from base."""
        assert issubclass(ConfigurationError, GeminiEvalError)
        assert issubclass(DataNotFoundError, GeminiEvalError)
        assert issubclass(APIError, GeminiEvalError)
        assert issubclass(ModelNotFoundError, GeminiEvalError)
        assert issubclass(ValidationError, GeminiEvalError)
        assert issubclass(CheckpointError, GeminiEvalError)
        assert issubclass(BudgetExceededError, GeminiEvalError)


class TestAPIError:
    """Tests for APIError."""

    def test_basic_error(self) -> None:
        """Test basic API error."""
        err = APIError("API failed")
        assert str(err) == "API failed"
        assert err.status_code is None
        assert err.response_body is None

    def test_with_status_code(self) -> None:
        """Test API error with status code."""
        err = APIError("Not found", status_code=404, response_body='{"error": "Not found"}')
        assert err.status_code == 404
        assert err.response_body == '{"error": "Not found"}'


class TestModelNotFoundError:
    """Tests for ModelNotFoundError."""

    def test_with_missing_models(self) -> None:
        """Test error with missing models list."""
        err = ModelNotFoundError(
            "Models unavailable",
            missing_models=["gpt-5", "claude-4"],
        )
        assert err.missing_models == ["gpt-5", "claude-4"]

    def test_without_missing_models(self) -> None:
        """Test error without missing models."""
        err = ModelNotFoundError("Models unavailable")
        assert err.missing_models == []


class TestValidationError:
    """Tests for ValidationError."""

    def test_with_errors_list(self) -> None:
        """Test error with validation errors list."""
        err = ValidationError(
            "Validation failed",
            errors=["Field 'name' is required", "Field 'age' must be positive"],
        )
        assert len(err.errors) == 2
        assert "Field 'name' is required" in err.errors


class TestBudgetExceededError:
    """Tests for BudgetExceededError."""

    def test_budget_error(self) -> None:
        """Test budget exceeded error."""
        err = BudgetExceededError("Budget exceeded", current_cost=150.0, limit=100.0)
        assert err.current_cost == 150.0
        assert err.limit == 100.0


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_with_retry_after(self) -> None:
        """Test rate limit with retry delay."""
        err = RateLimitError("Rate limited", retry_after=60.0)
        assert err.status_code == 429
        assert err.retry_after == 60.0


class TestCircuitOpenError:
    """Tests for CircuitOpenError."""

    def test_circuit_open(self) -> None:
        """Test circuit open error."""
        err = CircuitOpenError("openai", retry_after=30.0)
        assert err.service_id == "openai"
        assert err.retry_after == 30.0
        assert "openai" in str(err)


class TestParseError:
    """Tests for ParseError."""

    def test_with_raw_output(self) -> None:
        """Test parse error with raw output."""
        err = ParseError("Failed to parse JSON", raw_output='{"invalid json')
        assert err.raw_output == '{"invalid json'
