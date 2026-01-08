"""Application settings using Pydantic Settings."""
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="EVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required
    openrouter_api_key: str = Field(
        ...,
        alias="OPENROUTER_API_KEY",
        description="OpenRouter API key for model access",
    )

    # Paths
    onet_db_path: Path = Field(
        default=Path("db/onet.db"),
        description="Path to O*NET SQLite database",
    )
    results_dir: Path = Field(
        default=Path("results"),
        description="Directory for evaluation results",
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for static data files",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    # API settings
    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent API requests",
    )
    request_timeout: float = Field(
        default=120.0,
        ge=10.0,
        description="API request timeout in seconds",
    )

    # Budget control
    budget_limit: float = Field(
        default=1000.0,
        ge=0.0,
        description="Maximum budget in USD",
    )
    budget_warning_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Warn when this fraction of budget is used",
    )

    # Rate limiting
    rate_limit_requests_per_minute: int = Field(
        default=60,
        ge=1,
        description="Maximum requests per minute",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed requests",
    )
    retry_base_delay: float = Field(
        default=1.0,
        ge=0.1,
        description="Base delay for exponential backoff",
    )

    @field_validator("onet_db_path", "results_dir", "data_dir", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        return Path(v)

    @property
    def companies_file(self) -> Path:
        """Path to companies.json."""
        return self.data_dir / "companies.json"

    @property
    def names_file(self) -> Path:
        """Path to names.json."""
        return self.data_dir / "names.json"

    @property
    def naics_crosswalk_file(self) -> Path:
        """Path to NAICS crosswalk file."""
        return self.data_dir / "naics_soc_crosswalk.json"


def get_settings() -> Settings:
    """Get application settings (singleton pattern)."""
    return Settings()  # type: ignore[call-arg]
