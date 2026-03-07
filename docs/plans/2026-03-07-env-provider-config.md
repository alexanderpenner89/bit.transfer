# Provider-Configurable LLM Setup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hardcoded `"anthropic:claude-3-5-sonnet-20241022"` in `OrchestratorAgent` with a `PROVIDER`-based env config supporting Anthropic, OpenAI, Gemini, Ollama (local + cloud), and OpenRouter.

**Architecture:** A `Settings(BaseSettings)` class in `backend/config.py` reads from `.env`, validates required API keys at startup, and exposes `build_model()` returning the correct pydantic-ai model object. `OrchestratorAgent.__init__` calls `settings.build_model()` when no explicit model is passed — all existing tests (which pass `model="test"`) are unaffected.

**Tech Stack:** Python 3.12, pydantic-settings, pydantic-ai 1.67.0, pydantic-ai `OpenAIModel` for Ollama + OpenRouter

---

## Codebase Context

```
backend/
├── agents/orchestrator.py   # line 29: hardcoded default model — will be updated in Task 4
├── config.py                # NEW — Task 2
├── .env.example             # NEW — Task 3 (committed)
├── .env                     # NEW — Task 3 (gitignored — already in root .gitignore)
├── pyproject.toml           # add pydantic-settings — Task 1
└── tests/
    └── test_config.py       # NEW — Task 2
```

**Import style:** No `src/` layout. `pythonpath = ["."]` in `pyproject.toml`. Imports like `from config import settings`.

**Existing tests:** 48 tests, all pass. None will break — `OrchestratorAgent` still accepts explicit `model=` override.

---

## Task 1: Install pydantic-settings

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Install via uv**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv add pydantic-settings
```

Expected: adds `pydantic-settings` to `pyproject.toml` dependencies and updates `uv.lock`.

**Step 2: Verify import**

```bash
uv run python -c "import pydantic_settings; print(pydantic_settings.__version__)"
```

Expected: prints a version number.

**Step 3: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add pydantic-settings dependency for provider config"
```

---

## Task 2: Implement `backend/config.py` (TDD)

**Files:**
- Create: `backend/config.py`
- Create: `backend/tests/test_config.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_config.py`:

```python
"""Tests for Settings — construct directly with kwargs, no .env file needed."""
import pytest
from pydantic import ValidationError
from pydantic_ai.models.openai import OpenAIModel

from config import Settings


class TestProviderValidation:
    def test_ollama_requires_no_api_key(self):
        """Ollama is the only provider with no required key."""
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
    def test_default_provider_is_anthropic(self):
        # No validation error because we supply the key
        s = Settings(anthropic_api_key="sk-ant-test")
        assert s.provider == "anthropic"

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
        model = s.build_model()
        assert model == "anthropic:claude-3-5-sonnet-20241022"

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
        assert isinstance(model, OpenAIModel)

    def test_ollama_cloud_uses_cloud_url(self):
        s = Settings(
            provider="ollama",
            ollama_base_url="https://ollama.com/v1",
            ollama_api_key="cloud-key",
        )
        model = s.build_model()
        assert isinstance(model, OpenAIModel)

    def test_openrouter_returns_openai_model(self):
        s = Settings(provider="openrouter", openrouter_api_key="sk-or-test")
        model = s.build_model()
        assert isinstance(model, OpenAIModel)
```

**Step 2: Run tests (must FAIL)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_config.py -v
```

Expected: `ImportError: No module named 'config'`

**Step 3: Implement `backend/config.py`**

```python
"""Provider-configurable LLM settings.

Reads from backend/.env (gitignored). Set PROVIDER to switch between providers.
Each provider has per-provider model name and API key settings.

Usage:
    from config import settings
    model = settings.build_model()  # returns pydantic-ai compatible model

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

    provider: Literal["anthropic", "openai", "gemini", "ollama", "openrouter"] = "anthropic"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Gemini (Google)
    google_api_key: str | None = None
    gemini_model: str = "gemini-2.5-pro"

    # Ollama — local or cloud (same provider, different base URL)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str | None = None  # optional; required only for Ollama Cloud
    ollama_model: str = "llama3.2"

    # OpenRouter
    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    @model_validator(mode="after")
    def validate_provider_keys(self) -> "Settings":
        required: dict[str, str | None] = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "gemini": self.google_api_key,
            "openrouter": self.openrouter_api_key,
        }
        key_names = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        if self.provider in required and not required[self.provider]:
            raise ValueError(
                f"{key_names[self.provider]} is required when PROVIDER={self.provider}"
            )
        return self

    def build_model(self) -> Any:
        """Returns a pydantic-ai compatible model object or string.

        - anthropic / openai / gemini: returns a string (pydantic-ai resolves internally)
        - ollama / openrouter: returns OpenAIModel with custom base URL
        """
        match self.provider:
            case "anthropic":
                return f"anthropic:{self.anthropic_model}"
            case "openai":
                return f"openai:{self.openai_model}"
            case "gemini":
                return f"google-gla:{self.gemini_model}"
            case "ollama":
                from pydantic_ai.models.openai import OpenAIModel
                return OpenAIModel(
                    self.ollama_model,
                    base_url=self.ollama_base_url,
                    api_key=self.ollama_api_key or "ollama",  # local Ollama ignores key
                )
            case "openrouter":
                from pydantic_ai.models.openai import OpenAIModel
                return OpenAIModel(
                    self.openrouter_model,
                    base_url=self.openrouter_base_url,
                    api_key=self.openrouter_api_key,
                )


# Module-level singleton — reads from .env on import.
# In tests, construct Settings(...) directly instead of using this singleton.
settings = Settings()
```

**Step 4: Run tests (must PASS)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_config.py -v
```

Expected: all tests pass.

> **Note:** The module-level `settings = Settings()` at the bottom will try to read `.env`. If `.env` doesn't exist yet (Task 3 hasn't run), `pydantic-settings` silently ignores the missing file. However, the default `provider="anthropic"` requires `ANTHROPIC_API_KEY`. If it's not set, the module import will fail.
>
> **Fix:** Change the default provider to `"ollama"` temporarily, OR create the `.env` file (Task 3) before running all tests. The test file constructs `Settings(...)` directly with kwargs, so `test_config.py` itself is unaffected. The problem is only when importing `from config import settings` elsewhere.
>
> **Solution:** Keep `provider` default as `"ollama"` (requires no API key). Users with cloud providers set `PROVIDER=anthropic` in their `.env`. This is the right default for local development anyway.

**Adjust the default** in the implementation to `provider: Literal[...] = "ollama"`:

```python
provider: Literal["anthropic", "openai", "gemini", "ollama", "openrouter"] = "ollama"
```

**Step 5: Run all 48 existing tests + new config tests**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v
```

Expected: all pass (60+ tests).

**Step 6: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/config.py backend/tests/test_config.py
git commit -m "feat: add Settings class with PROVIDER-based LLM config (Anthropic, OpenAI, Gemini, Ollama, OpenRouter)"
```

---

## Task 3: Create `.env.example` and local `.env`

**Files:**
- Create: `backend/.env.example` (committed)
- Create: `backend/.env` (gitignored — already in root `.gitignore`)

**Step 1: Create `.env.example`**

Create `backend/.env.example`:

```bash
# Provider selection — choose one: anthropic | openai | gemini | ollama | openrouter
PROVIDER=ollama

# =============================================================================
# Anthropic
# =============================================================================
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# =============================================================================
# OpenAI
# =============================================================================
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o

# =============================================================================
# Gemini (Google)
# =============================================================================
GOOGLE_API_KEY=AIza-your-key-here
GEMINI_MODEL=gemini-2.5-pro

# =============================================================================
# Ollama — local (default) or cloud
# Local:  OLLAMA_BASE_URL=http://localhost:11434/v1  (no API key needed)
# Cloud:  OLLAMA_BASE_URL=https://ollama.com/v1      (API key required)
# =============================================================================
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=
OLLAMA_MODEL=llama3.2

# =============================================================================
# OpenRouter
# =============================================================================
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

**Step 2: Create local `backend/.env`**

Create `backend/.env` (this file is gitignored and for local development only):

```bash
# Local development default — Ollama requires no API key
PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434/v1
```

**Step 3: Verify `.env` is gitignored**

```bash
cd /home/alex/dev/work/bit.transfer
git check-ignore -v backend/.env
```

Expected: output like `.gitignore:... backend/.env` — confirming it is ignored.

**Step 4: Verify all tests still pass**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v
```

Expected: all pass (no new failures from `.env` loading).

**Step 5: Commit only `.env.example`**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/.env.example
git commit -m "docs: add .env.example with all provider configurations"
```

**DO NOT** `git add backend/.env` — it is gitignored and contains local secrets.

---

## Task 4: Update `OrchestratorAgent` to use `settings.build_model()`

**Files:**
- Modify: `backend/agents/orchestrator.py:29`

**Step 1: Verify current line 29**

Read `backend/agents/orchestrator.py` lines 27–37. It should look like:

```python
def __init__(self, model: str = "anthropic:claude-3-5-sonnet-20241022") -> None:
    self._keyword_extractor = KeywordExtractor()
    self.agent: Agent[GewerksProfilModel, SearchStrategyModel] = Agent(
        model=model,
        ...
    )
```

**Step 2: Update `__init__` signature**

Change lines 29–36 from:

```python
def __init__(self, model: str = "anthropic:claude-3-5-sonnet-20241022") -> None:
    self._keyword_extractor = KeywordExtractor()
    self.agent: Agent[GewerksProfilModel, SearchStrategyModel] = Agent(
        model=model,
        output_type=SearchStrategyModel,
        deps_type=GewerksProfilModel,
        defer_model_check=True,
    )
```

To:

```python
def __init__(self, model=None) -> None:
    if model is None:
        from config import settings
        model = settings.build_model()
    self._keyword_extractor = KeywordExtractor()
    self.agent: Agent[GewerksProfilModel, SearchStrategyModel] = Agent(
        model=model,
        output_type=SearchStrategyModel,
        deps_type=GewerksProfilModel,
        defer_model_check=True,
    )
```

The lazy import (`from config import settings` inside `__init__`) prevents import-time failures in environments where `.env` isn't loaded yet.

**Step 3: Run all tests**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v
```

Expected: all pass. Existing tests pass `model="test"` explicitly, so this change doesn't affect them.

**Step 4: Smoke-test default instantiation**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run python -c "
from agents.orchestrator import OrchestratorAgent
a = OrchestratorAgent()
print('Default model loaded from settings:', type(a.agent))
print('Success')
"
```

Expected: `Success` — no `ValidationError` or `ImportError` (Ollama needs no key).

**Step 5: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/agents/orchestrator.py
git commit -m "feat: OrchestratorAgent reads model from settings.build_model() by default"
```

---

## Troubleshooting

### `ValidationError` on import when PROVIDER=anthropic and no key

The module-level `settings = Settings()` in `config.py` runs at import time. If `PROVIDER=anthropic` is set in `.env` but `ANTHROPIC_API_KEY` is missing, import fails.

**Fix:** Ensure your `.env` includes the key for the active provider. For local development without cloud keys, use `PROVIDER=ollama`.

### `OpenAIModel` constructor signature changed in pydantic-ai 1.67.0

If `OpenAIModel(model, base_url=..., api_key=...)` fails, check the actual API:

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run python -c "
from pydantic_ai.models.openai import OpenAIModel
import inspect
print(inspect.signature(OpenAIModel.__init__))
"
```

Adjust the constructor call in `build_model()` accordingly.

### Ollama local not running

If you test with `PROVIDER=ollama` and Ollama isn't running, `agent.run()` will fail with a connection error. Start Ollama with `ollama serve` before running real (non-mocked) calls.
