"""Accurate cost estimation for evaluation runs."""
from dataclasses import dataclass, field


@dataclass
class CostEstimate:
    """Detailed cost breakdown for an evaluation run."""

    response_generation_cost: float
    judging_cost: float
    enrichment_cost: float
    total_cost: float
    breakdown: dict[str, int | float] = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable cost summary."""
        return (
            f"Cost Estimate:\n"
            f"  Response generation: ${self.response_generation_cost:.2f}\n"
            f"  Judging:             ${self.judging_cost:.2f}\n"
            f"  Enrichment:          ${self.enrichment_cost:.2f}\n"
            f"  ─────────────────────────────\n"
            f"  Total:               ${self.total_cost:.2f}"
        )


class CostEstimator:
    """
    Accurate cost estimation incorporating ALL judging factors.

    Critical factors:
    - Position shuffling DOUBLES judge calls
    - Best-of-N voting MULTIPLIES judge calls
    - Two personas DOUBLE judge calls
    - Three judges TRIPLE judge calls
    """

    # Approximate pricing per 1K tokens (as of Jan 2026)
    MODEL_PRICING: dict[str, dict[str, float]] = {
        # Pro tier
        "google/gemini-3.0-pro": {"input": 0.005, "output": 0.015},
        "openai/gpt-5.2": {"input": 0.01, "output": 0.03},
        "anthropic/claude-opus-4.5": {"input": 0.015, "output": 0.075},
        "x-ai/grok-4.1": {"input": 0.008, "output": 0.024},
        "moonshot/kimi-k2": {"input": 0.006, "output": 0.018},
        # Flash tier
        "google/gemini-3.0-flash": {"input": 0.0005, "output": 0.0015},
        "openai/gpt-4.1": {"input": 0.003, "output": 0.006},
        "anthropic/claude-sonnet": {"input": 0.003, "output": 0.015},
    }

    # Default token estimates
    DEFAULT_TOKEN_ESTIMATES: dict[str, int] = {
        "prompt_input": 500,
        "response_output": 300,
        "judge_input": 1200,  # Prompt + 2 responses + system prompt
        "judge_output": 250,
        "enrichment_input": 400,
        "enrichment_output": 600,
    }

    def estimate_full_eval(
        self,
        prompt_count: int,
        model_count: int,
        judge_count: int,
        persona_count: int,
        votes_per_judge: int,
        position_shuffle: bool,
        token_estimates: dict[str, int] | None = None,
    ) -> CostEstimate:
        """
        Calculate total estimated cost.

        Args:
            prompt_count: Number of prompts to evaluate
            model_count: Number of models being evaluated
            judge_count: Number of judge models
            persona_count: Number of judge personas (usually 2)
            votes_per_judge: Best-of-N voting count
            position_shuffle: Whether to test both orderings
            token_estimates: Override default token estimates

        Returns:
            CostEstimate with detailed breakdown
        """
        tokens = token_estimates or self.DEFAULT_TOKEN_ESTIMATES

        # Response generation
        response_calls = prompt_count * model_count
        response_cost = self._estimate_response_cost(response_calls, tokens)

        # Judging calculation
        # Each pair of models creates one comparison per prompt
        comparisons_per_prompt = model_count * (model_count - 1) // 2
        total_comparisons = prompt_count * comparisons_per_prompt

        position_multiplier = 2 if position_shuffle else 1
        judge_calls_per_comparison = (
            judge_count * persona_count * votes_per_judge * position_multiplier
        )
        total_judge_calls = total_comparisons * judge_calls_per_comparison

        judging_cost = self._estimate_judge_cost(total_judge_calls, tokens)

        # Enrichment (one call per prompt)
        enrichment_cost = self._estimate_enrichment_cost(prompt_count, tokens)

        total = response_cost + judging_cost + enrichment_cost

        return CostEstimate(
            response_generation_cost=response_cost,
            judging_cost=judging_cost,
            enrichment_cost=enrichment_cost,
            total_cost=total,
            breakdown={
                "response_calls": response_calls,
                "total_comparisons": total_comparisons,
                "judge_calls_per_comparison": judge_calls_per_comparison,
                "total_judge_calls": total_judge_calls,
                "enrichment_calls": prompt_count,
            },
        )

    def estimate_from_preset(self, preset_name: str) -> CostEstimate:
        """Estimate cost for a named preset."""
        from src.config.presets import get_preset

        preset = get_preset(preset_name)  # type: ignore[arg-type]
        return self.estimate_full_eval(
            prompt_count=preset.prompt_count,
            model_count=len(preset.models),
            judge_count=len(preset.judge_models),
            persona_count=len(preset.judge_personas),
            votes_per_judge=preset.votes_per_judge,
            position_shuffle=preset.position_shuffle,
        )

    def _estimate_response_cost(self, call_count: int, tokens: dict[str, int]) -> float:
        """Estimate response generation cost."""
        avg_price = self._average_price(list(self.MODEL_PRICING.keys())[:5])
        input_cost = call_count * tokens["prompt_input"] / 1000 * avg_price["input"]
        output_cost = call_count * tokens["response_output"] / 1000 * avg_price["output"]
        return input_cost + output_cost

    def _estimate_judge_cost(self, call_count: int, tokens: dict[str, int]) -> float:
        """Estimate judging cost using pro-tier models."""
        avg_price = self._average_price([
            "anthropic/claude-opus-4.5",
            "openai/gpt-5.2",
            "google/gemini-3.0-pro",
        ])
        input_cost = call_count * tokens["judge_input"] / 1000 * avg_price["input"]
        output_cost = call_count * tokens["judge_output"] / 1000 * avg_price["output"]
        return input_cost + output_cost

    def _estimate_enrichment_cost(self, call_count: int, tokens: dict[str, int]) -> float:
        """Estimate enrichment cost using cheaper model."""
        price = self.MODEL_PRICING.get(
            "anthropic/claude-sonnet",
            {"input": 0.003, "output": 0.015},
        )
        input_cost = call_count * tokens["enrichment_input"] / 1000 * price["input"]
        output_cost = call_count * tokens["enrichment_output"] / 1000 * price["output"]
        return input_cost + output_cost

    def _average_price(self, model_ids: list[str]) -> dict[str, float]:
        """Get average pricing across models."""
        input_prices = [
            self.MODEL_PRICING.get(m, {"input": 0.01})["input"] for m in model_ids
        ]
        output_prices = [
            self.MODEL_PRICING.get(m, {"output": 0.03})["output"] for m in model_ids
        ]
        return {
            "input": sum(input_prices) / len(input_prices),
            "output": sum(output_prices) / len(output_prices),
        }
