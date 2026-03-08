"""Provider-configurable LLM settings.

Reads from backend/.env (gitignored). Set PROVIDER to switch between providers.

Usage:
    from config import settings
    model = settings.build_model()

For tests: construct Settings(...) directly with kwargs — no .env file needed.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIChatModel

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: Literal["anthropic", "openai", "gemini", "ollama", "openrouter"] = "ollama"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Gemini (Google)
    google_api_key: str | None = None
    gemini_model: str = "gemini-2.5-pro"

    # Ollama — local or cloud (same provider, different base URL + optional key)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str | None = None  # optional; required only for Ollama Cloud
    ollama_model: str = "llama3.2"

    # OpenRouter
    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Ghost CMS
    ghost_admin_api_key: str | None = None
    ghost_url: str = "http://localhost:2368"
    ghost_ai_author_id: str | None = None

    @property
    def ghost_enabled(self) -> bool:
        return bool(self.ghost_admin_api_key)

    # OpenAlex
    openalex_api_key: str | None = None
    openalex_max_results: int = 25
    # Precision search date filter — filters by publication_date (free tier compatible).
    # Format: YYYY-MM-DD. Defaults to 30 days ago (rolling window). Set to None to disable.
    openalex_precision_search_date: str | None = str(datetime.date.today() - datetime.timedelta(days=30))

    # Concurrency
    llm_concurrency: int = 3  # max parallel LLM calls (Ollama Cloud limit: 3)
    openalex_concurrency: int = 1  # max parallel OpenAlex API requests (free tier: 1 = sequential to avoid 429)

    # Langfuse Tracing
    langfuse_secret_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True

    @model_validator(mode="after")
    def validate_provider_keys(self) -> "Settings":
        required = {
            "anthropic": (self.anthropic_api_key, "ANTHROPIC_API_KEY"),
            "openai": (self.openai_api_key, "OPENAI_API_KEY"),
            "gemini": (self.google_api_key, "GOOGLE_API_KEY"),
            "openrouter": (self.openrouter_api_key, "OPENROUTER_API_KEY"),
        }
        if self.provider in required:
            value, name = required[self.provider]
            if not value:
                raise ValueError(f"{name} is required when PROVIDER={self.provider}")
        return self

    def langfuse_model_name(self) -> str:
        """Returns the bare model name for Langfuse cost tracking."""
        match self.provider:
            case "anthropic":
                return self.anthropic_model
            case "openai":
                return self.openai_model
            case "gemini":
                return self.gemini_model
            case "ollama":
                return self.ollama_model
            case "openrouter":
                return self.openrouter_model
            case _:
                return "unknown"

    def build_model(self) -> str | OpenAIChatModel:
        """Returns pydantic-ai compatible model string or OpenAIChatModel object."""
        match self.provider:
            case "anthropic":
                return f"anthropic:{self.anthropic_model}"
            case "openai":
                return f"openai:{self.openai_model}"
            case "gemini":
                return f"google-gla:{self.gemini_model}"
            case "ollama":
                from pydantic_ai.models.openai import OpenAIChatModel
                from pydantic_ai.providers.openai import OpenAIProvider
                return OpenAIChatModel(
                    self.ollama_model,
                    provider=OpenAIProvider(
                        base_url=self.ollama_base_url,
                        api_key=self.ollama_api_key or "ollama",
                    ),
                )
            case "openrouter":
                from pydantic_ai.models.openai import OpenAIChatModel
                from pydantic_ai.providers.openai import OpenAIProvider
                return OpenAIChatModel(
                    self.openrouter_model,
                    provider=OpenAIProvider(
                        base_url=self.openrouter_base_url,
                        api_key=self.openrouter_api_key,
                    ),
                )
            case _:
                raise NotImplementedError(
                    f"build_model() not implemented for provider {self.provider!r}"
                )


# Module-level singleton — reads from .env on import.
# In tests, construct Settings(...) directly instead.
settings = Settings()


def get_langfuse():
    """Return a Langfuse client configured from settings, or a disabled stub."""
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key or "",
        secret_key=settings.langfuse_secret_key or "",
        host=settings.langfuse_base_url,
        tracing_enabled=bool(settings.langfuse_enabled and settings.langfuse_public_key),
    )
