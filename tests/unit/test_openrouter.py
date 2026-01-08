"""Tests for OpenRouter API client."""
import pytest
import respx
from httpx import Response

from src.api.openrouter_client import ModelResponse, OpenRouterClient
from src.exceptions import APIError, RateLimitError


class TestOpenRouterClient:
    """Tests for OpenRouter client."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_success(self) -> None:
        """Test successful generation request."""
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "model": "openai/gpt-4",
                    "choices": [
                        {
                            "message": {"content": "Hello, world!"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                },
            )
        )

        async with OpenRouterClient("test-api-key") as client:
            response = await client.generate(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello"}],
            )

        assert isinstance(response, ModelResponse)
        assert response.content == "Hello, world!"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    @respx.mock
    async def test_generate_with_system_prompt(self) -> None:
        """Test generation with system prompt."""
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "model": "openai/gpt-4",
                    "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
                },
            )
        )

        async with OpenRouterClient("test-api-key") as client:
            response = await client.generate(
                model_id="openai/gpt-4",
                messages=[{"role": "user", "content": "Hello"}],
                system_prompt="You are helpful.",
            )

        assert response.content == "Response"

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_error(self) -> None:
        """Test rate limit handling."""
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=Response(
                429,
                headers={"Retry-After": "60"},
                json={"error": "Rate limit exceeded"},
            )
        )

        async with OpenRouterClient("test-api-key", max_retries=1) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.generate(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert exc_info.value.retry_after == 60.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_error(self) -> None:
        """Test API error handling."""
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=Response(
                500,
                json={"error": "Internal server error"},
            )
        )

        async with OpenRouterClient("test-api-key") as client:
            with pytest.raises(APIError) as exc_info:
                await client.generate(
                    model_id="openai/gpt-4",
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_models(self) -> None:
        """Test listing available models."""
        respx.get("https://openrouter.ai/api/v1/models").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": "openai/gpt-4", "name": "GPT-4"},
                        {"id": "anthropic/claude-3", "name": "Claude 3"},
                    ]
                },
            )
        )

        async with OpenRouterClient("test-api-key") as client:
            models = await client.list_models()

        assert len(models) == 2
        assert models[0]["id"] == "openai/gpt-4"

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_model_exists(self) -> None:
        """Test model verification - model exists."""
        respx.get("https://openrouter.ai/api/v1/models").mock(
            return_value=Response(
                200,
                json={"data": [{"id": "openai/gpt-4"}]},
            )
        )

        async with OpenRouterClient("test-api-key") as client:
            exists = await client.verify_model("openai/gpt-4")

        assert exists is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_model_not_exists(self) -> None:
        """Test model verification - model doesn't exist."""
        respx.get("https://openrouter.ai/api/v1/models").mock(
            return_value=Response(
                200,
                json={"data": [{"id": "openai/gpt-4"}]},
            )
        )

        async with OpenRouterClient("test-api-key") as client:
            exists = await client.verify_model("nonexistent/model")

        assert exists is False

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        async with OpenRouterClient("test-api-key") as client:
            assert client._client is not None

        # After exit, client should be closed
        assert client._client is None
