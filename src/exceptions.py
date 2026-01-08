"""Custom exceptions for the Gemini Writing Evaluation Framework."""


class GeminiEvalError(Exception):
    """Base exception for all framework errors."""
    pass


class ConfigurationError(GeminiEvalError):
    """Raised when configuration is invalid or missing."""
    pass


class DataNotFoundError(GeminiEvalError):
    """Raised when required data files or database are missing."""
    pass


class APIError(GeminiEvalError):
    """Raised for OpenRouter API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ModelNotFoundError(GeminiEvalError):
    """Raised when a required model is not available on OpenRouter."""

    def __init__(self, message: str, missing_models: list[str] | None = None):
        super().__init__(message)
        self.missing_models = missing_models or []


class ValidationError(GeminiEvalError):
    """Raised when schema or data validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class CheckpointError(GeminiEvalError):
    """Raised when checkpoint save/load fails."""
    pass


class BudgetExceededError(GeminiEvalError):
    """Raised when cost limit is reached."""

    def __init__(self, message: str, current_cost: float, limit: float):
        super().__init__(message)
        self.current_cost = current_cost
        self.limit = limit


class RateLimitError(APIError):
    """Raised when API rate limit is hit."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class CircuitOpenError(GeminiEvalError):
    """Raised when circuit breaker is open."""

    def __init__(self, service_id: str, retry_after: float | None = None):
        super().__init__(f"Circuit breaker open for {service_id}")
        self.service_id = service_id
        self.retry_after = retry_after


class ParseError(GeminiEvalError):
    """Raised when parsing LLM output fails."""

    def __init__(self, message: str, raw_output: str | None = None):
        super().__init__(message)
        self.raw_output = raw_output
