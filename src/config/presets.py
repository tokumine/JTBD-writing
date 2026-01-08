"""Evaluation preset configurations."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EvalPreset:
    """Configuration preset for evaluation runs."""

    name: str
    prompt_count: int
    models: tuple[str, ...]
    judge_models: tuple[str, ...]
    judge_personas: tuple[str, ...]
    votes_per_judge: int
    position_shuffle: bool
    estimated_cost_usd: float
    estimated_runtime_hours: float
    description: str


# Model logical names mapping to provider/model patterns
MODEL_ALIASES = {
    # Pro tier
    "gemini_pro": "google/gemini-3-pro-preview",
    "gpt_pro": "openai/gpt-5.2",
    "claude_pro": "anthropic/claude-opus-4.5",
    "grok": "x-ai/grok-4.1",
    "kimi": "moonshot/kimi-k2",
    # Flash tier
    "gemini_flash": "google/gemini-3-flash-preview",
    "gpt_flash": "openai/gpt-5.1",
    "claude_flash": "anthropic/claude-haiku-4.5",
    # Judges
    "judge_claude": "anthropic/claude-opus-4.5",
    "judge_gpt": "openai/gpt-5.2",
    "judge_gemini": "google/gemini-3-pro-preview",
}

# Preset configurations with corrected cost estimates
PRESETS: dict[str, EvalPreset] = {
    "smoke": EvalPreset(
        name="smoke",
        prompt_count=10,
        models=("gemini_pro", "gpt_pro"),
        judge_models=("judge_claude",),
        judge_personas=("writing_expert",),
        votes_per_judge=1,
        position_shuffle=False,
        estimated_cost_usd=5.0,
        estimated_runtime_hours=0.1,
        description="Quick sanity check - verify pipeline works",
    ),
    "dev": EvalPreset(
        name="dev",
        prompt_count=30,
        models=("gemini_pro", "gpt_pro", "claude_pro"),
        judge_models=("judge_claude",),
        judge_personas=("writing_expert", "recipient"),
        votes_per_judge=1,
        position_shuffle=False,
        estimated_cost_usd=25.0,
        estimated_runtime_hours=0.3,
        description="Development iteration - test prompt quality",
    ),
    "quick": EvalPreset(
        name="quick",
        prompt_count=100,
        models=("gemini_pro", "gpt_pro", "claude_pro"),
        judge_models=("judge_claude", "judge_gpt"),
        judge_personas=("writing_expert", "recipient"),
        votes_per_judge=1,
        position_shuffle=True,
        estimated_cost_usd=150.0,
        estimated_runtime_hours=1.5,
        description="Quick evaluation with position bias handling",
    ),
    "standard": EvalPreset(
        name="standard",
        prompt_count=200,
        models=("gemini_pro", "gpt_pro", "claude_pro", "grok"),
        judge_models=("judge_claude", "judge_gpt", "judge_gemini"),
        judge_personas=("writing_expert", "recipient"),
        votes_per_judge=3,
        position_shuffle=True,
        estimated_cost_usd=800.0,
        estimated_runtime_hours=4.0,
        description="Standard evaluation with statistical power",
    ),
    "comprehensive": EvalPreset(
        name="comprehensive",
        prompt_count=500,
        models=("gemini_pro", "gpt_pro", "claude_pro", "grok", "kimi"),
        judge_models=("judge_claude", "judge_gpt", "judge_gemini"),
        judge_personas=("writing_expert", "recipient"),
        votes_per_judge=3,
        position_shuffle=True,
        estimated_cost_usd=2500.0,
        estimated_runtime_hours=10.0,
        description="Comprehensive evaluation for publication",
    ),
    "full": EvalPreset(
        name="full",
        prompt_count=1000,
        models=("gemini_pro", "gpt_pro", "claude_pro", "grok", "kimi"),
        judge_models=("judge_claude", "judge_gpt", "judge_gemini"),
        judge_personas=("writing_expert", "recipient"),
        votes_per_judge=5,
        position_shuffle=True,
        estimated_cost_usd=8000.0,
        estimated_runtime_hours=24.0,
        description="Full rigorous evaluation",
    ),
}


PresetName = Literal["smoke", "dev", "quick", "standard", "comprehensive", "full"]


def get_preset(name: PresetName) -> EvalPreset:
    """Get a preset by name."""
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(PRESETS.keys())}")
    return PRESETS[name]


def list_presets() -> list[EvalPreset]:
    """List all available presets."""
    return list(PRESETS.values())
