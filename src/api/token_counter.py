"""Token counting utilities."""
import tiktoken


class TokenCounter:
    """Accurate token counting using tiktoken."""

    # Model family to tokenizer mapping
    TOKENIZERS: dict[str, str | None] = {
        "openai": "cl100k_base",  # GPT-4 and later
        "anthropic": "cl100k_base",  # Claude uses similar
        "google": None,  # No public tokenizer, estimate
        "x-ai": "cl100k_base",  # Grok likely similar
        "moonshot": None,  # No public tokenizer
    }

    def __init__(self) -> None:
        """Initialize token counter."""
        self._tokenizers: dict[str, tiktoken.Encoding] = {}

    def count_tokens(self, text: str, model_id: str) -> int:
        """
        Count tokens for text given model.

        Args:
            text: Text to count tokens for
            model_id: OpenRouter model ID

        Returns:
            Token count
        """
        provider = model_id.split("/")[0] if "/" in model_id else "unknown"
        tokenizer_name = self.TOKENIZERS.get(provider)

        if tokenizer_name:
            try:
                tokenizer = self._get_tokenizer(tokenizer_name)
                return len(tokenizer.encode(text))
            except Exception:
                pass

        # Fallback: estimate based on character count
        # Average is ~4 characters per token for English
        return max(1, len(text) // 4)

    def estimate_response_tokens(
        self,
        task_type: str,
        word_count_tier: str,
    ) -> int:
        """
        Estimate expected response token count.

        Args:
            task_type: Type of task (email, memo, report, etc.)
            word_count_tier: Expected length tier (short, medium, long)

        Returns:
            Estimated token count
        """
        # Base estimates by task type
        base_estimates = {
            "email": 200,
            "memo": 300,
            "report": 500,
            "letter": 250,
            "other": 300,
        }

        # Adjust by word count tier
        tier_multipliers = {
            "short": 0.5,
            "medium": 1.0,
            "long": 2.0,
        }

        base = base_estimates.get(task_type, 300)
        multiplier = tier_multipliers.get(word_count_tier, 1.0)

        return int(base * multiplier)

    def _get_tokenizer(self, name: str) -> tiktoken.Encoding:
        """Get or create tokenizer."""
        if name not in self._tokenizers:
            self._tokenizers[name] = tiktoken.get_encoding(name)
        return self._tokenizers[name]

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str,
        pricing: dict[str, dict[str, float]] | None = None,
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_id: Model ID
            pricing: Optional pricing dict {model_id: {"input": x, "output": y}}

        Returns:
            Estimated cost in USD
        """
        # Default pricing per 1K tokens
        default_pricing = {
            "anthropic/claude-opus-4.5": {"input": 0.015, "output": 0.075},
            "openai/gpt-5.2": {"input": 0.01, "output": 0.03},
            "google/gemini-3.0-pro": {"input": 0.005, "output": 0.015},
        }

        if pricing and model_id in pricing:
            model_pricing = pricing[model_id]
        elif model_id in default_pricing:
            model_pricing = default_pricing[model_id]
        else:
            # Conservative default
            model_pricing = {"input": 0.01, "output": 0.03}

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]

        return input_cost + output_cost
