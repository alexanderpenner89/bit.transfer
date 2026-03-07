"""Provider-configurable LLM settings.

Reads from backend/.env (gitignored). Set PROVIDER to switch between providers.

Usage:
    from config import settings
    model = settings.build_model()

For tests: construct Settings(...) directly with kwargs — no .env file needed.
"""
from typing import Any, Literal

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

    def build_model(self) -> Any:
        """Returns pydantic-ai compatible model string or OpenAIModel object."""
        match self.provider:
            case "anthropic":
                return f"anthropic:{self.anthropic_model}"
            case "openai":
                return f"openai:{self.openai_model}"
            case "gemini":
                return f"google-gla:{self.gemini_model}"
            case "ollama":
                from pydantic_ai.models.openai import OpenAIModel
                from pydantic_ai.providers.openai import OpenAIProvider
                return OpenAIModel(
                    self.ollama_model,
                    provider=OpenAIProvider(
                        base_url=self.ollama_base_url,
                        api_key=self.ollama_api_key or "ollama",
                    ),
                )
            case "openrouter":
                from pydantic_ai.models.openai import OpenAIModel
                from pydantic_ai.providers.openai import OpenAIProvider
                return OpenAIModel(
                    self.openrouter_model,
                    provider=OpenAIProvider(
                        base_url=self.openrouter_base_url,
                        api_key=self.openrouter_api_key,
                    ),
                )


# Module-level singleton — reads from .env on import.
# In tests, construct Settings(...) directly instead.
settings = Settings()
