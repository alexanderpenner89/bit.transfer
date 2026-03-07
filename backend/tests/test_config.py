"""Tests for Settings — construct directly with kwargs, no .env file needed."""
import pytest
from pydantic import ValidationError
from pydantic_ai.models.openai import OpenAIChatModel

from config import Settings


class TestProviderValidation:
    def test_ollama_requires_no_api_key(self):
        s = Settings(provider="ollama")
        assert s.provider == "ollama"

    def test_anthropic_requires_api_key(self):
        with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
            Settings(provider="anthropic", anthropic_api_key=None)

    def test_anthropic_with_key_is_valid(self):
        s = Settings(provider="anthropic", anthropic_api_key="sk-ant-test")
        assert s.provider == "anthropic"

    def test_openai_requires_api_key(self):
        with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
            Settings(provider="openai", openai_api_key=None)

    def test_openai_with_key_is_valid(self):
        s = Settings(provider="openai", openai_api_key="sk-test")
        assert s.provider == "openai"

    def test_gemini_requires_api_key(self):
        with pytest.raises(ValidationError, match="GOOGLE_API_KEY"):
            Settings(provider="gemini", google_api_key=None)

    def test_gemini_with_key_is_valid(self):
        s = Settings(provider="gemini", google_api_key="AIza-test")
        assert s.provider == "gemini"

    def test_openrouter_requires_api_key(self):
        with pytest.raises(ValidationError, match="OPENROUTER_API_KEY"):
            Settings(provider="openrouter", openrouter_api_key=None)

    def test_openrouter_with_key_is_valid(self):
        s = Settings(provider="openrouter", openrouter_api_key="sk-or-test")
        assert s.provider == "openrouter"

    def test_invalid_provider_raises(self):
        with pytest.raises(ValidationError):
            Settings(provider="invalid_provider")


class TestDefaults:
    def test_default_provider_is_ollama(self):
        s = Settings()
        assert s.provider == "ollama"

    def test_anthropic_default_model(self):
        s = Settings(provider="anthropic", anthropic_api_key="sk-ant-test")
        assert s.anthropic_model == "claude-3-5-sonnet-20241022"

    def test_openai_default_model(self):
        s = Settings(provider="openai", openai_api_key="sk-test")
        assert s.openai_model == "gpt-4o"

    def test_gemini_default_model(self):
        s = Settings(provider="gemini", google_api_key="AIza-test")
        assert s.gemini_model == "gemini-2.5-pro"

    def test_ollama_default_model(self):
        s = Settings(provider="ollama")
        assert s.ollama_model == "llama3.2"

    def test_ollama_default_base_url(self):
        s = Settings(provider="ollama")
        assert s.ollama_base_url == "http://localhost:11434/v1"

    def test_openrouter_default_model(self):
        s = Settings(provider="openrouter", openrouter_api_key="sk-or-test")
        assert s.openrouter_model == "anthropic/claude-3.5-sonnet"

    def test_custom_model_override(self):
        s = Settings(provider="anthropic", anthropic_api_key="sk-ant-test",
                     anthropic_model="claude-3-opus-20240229")
        assert s.anthropic_model == "claude-3-opus-20240229"


class TestBuildModel:
    def test_anthropic_returns_string(self):
        s = Settings(provider="anthropic", anthropic_api_key="sk-ant-test")
        assert s.build_model() == "anthropic:claude-3-5-sonnet-20241022"

    def test_anthropic_custom_model_in_string(self):
        s = Settings(provider="anthropic", anthropic_api_key="sk-ant-test",
                     anthropic_model="claude-3-opus-20240229")
        assert s.build_model() == "anthropic:claude-3-opus-20240229"

    def test_openai_returns_string(self):
        s = Settings(provider="openai", openai_api_key="sk-test")
        assert s.build_model() == "openai:gpt-4o"

    def test_gemini_returns_string(self):
        s = Settings(provider="gemini", google_api_key="AIza-test")
        assert s.build_model() == "google-gla:gemini-2.5-pro"

    def test_ollama_local_returns_openai_model(self):
        s = Settings(provider="ollama")
        model = s.build_model()
        assert isinstance(model, OpenAIChatModel)

    def test_ollama_cloud_uses_cloud_url(self):
        s = Settings(
            provider="ollama",
            ollama_base_url="https://ollama.com/v1",
            ollama_api_key="cloud-key",
        )
        model = s.build_model()
        assert isinstance(model, OpenAIChatModel)

    def test_openrouter_returns_openai_model(self):
        s = Settings(provider="openrouter", openrouter_api_key="sk-or-test")
        model = s.build_model()
        assert isinstance(model, OpenAIChatModel)
