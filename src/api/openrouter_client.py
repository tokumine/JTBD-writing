"""OpenRouter API client for model access."""
import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.exceptions import APIError, RateLimitError


@dataclass
class ModelResponse:
    """Response from a model generation request."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    finish_reason: str
    raw_response: dict[str, Any] | None = None


class OpenRouterClient:
    """Async client for OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenRouterClient":
        """Enter async context."""
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client exists."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/gemini-writing-eval",
                    "X-Title": "Gemini Writing Eval",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """
        Generate a response from a model.

        Args:
            model_id: OpenRouter model ID (e.g., "anthropic/claude-opus-4.5")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt

        Returns:
            ModelResponse with generated content
        """
        client = await self._ensure_client()

        # Build request payload
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            # Prepend system message
            payload["messages"] = [
                {"role": "system", "content": system_prompt},
                *messages,
            ]

        start_time = time.perf_counter()

        try:
            response = await self._make_request_with_retry(client, payload)
            latency_ms = (time.perf_counter() - start_time) * 1000

            return self._parse_response(response, latency_ms)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = float(e.response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    f"Rate limit exceeded for {model_id}",
                    retry_after=retry_after,
                )
            raise APIError(
                f"API error: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
            )
        except httpx.TimeoutException:
            raise APIError(f"Request timeout after {self.timeout}s for {model_id}")
        except Exception as e:
            raise APIError(f"Request failed: {e}")

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True,
    )
    async def _make_request_with_retry(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Make request with retry on rate limit."""
        response = await client.post(
            f"{self.BASE_URL}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(
        self,
        response_data: dict[str, Any],
        latency_ms: float,
    ) -> ModelResponse:
        """Parse API response into ModelResponse."""
        choice = response_data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = response_data.get("usage", {})

        return ModelResponse(
            content=message.get("content", ""),
            model=response_data.get("model", "unknown"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "unknown"),
            raw_response=response_data,
        )

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        client = await self._ensure_client()

        try:
            response = await client.get(f"{self.BASE_URL}/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            raise APIError(f"Failed to list models: {e}")

    async def verify_model(self, model_id: str) -> bool:
        """Verify a model is available."""
        models = await self.list_models()
        model_ids = {m.get("id") for m in models}
        return model_id in model_ids
