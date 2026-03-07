# Provider-Configurable LLM Setup – Design

**Goal:** Replace the hardcoded `"anthropic:claude-3-5-sonnet-20241022"` default in `OrchestratorAgent` with a `PROVIDER`-based env configuration supporting Anthropic, OpenAI, Gemini, Ollama (local + cloud), and OpenRouter.

---

## Architecture

```
backend/.env          ← gitignored, local values
backend/.env.example  ← committed, documents all options
backend/config.py     ← Settings(BaseSettings), build_model()
backend/agents/orchestrator.py  ← reads settings.build_model() as default
```

`Settings` is a `pydantic-settings` `BaseSettings` subclass. It reads from `.env` automatically, validates required keys at startup, and exposes `build_model()` which returns the correct pydantic-ai model object for the active provider.

---

## Environment Variables

```bash
# Active provider
PROVIDER=ollama  # anthropic | openai | gemini | ollama | openrouter

# --- Anthropic ---
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022   # default

# --- OpenAI ---
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o                          # default

# --- Gemini (Google) ---
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.5-pro                  # default

# --- Ollama (local OR cloud) ---
OLLAMA_BASE_URL=http://localhost:11434/v1    # override to https://ollama.com/v1 for cloud
OLLAMA_API_KEY=                              # empty for local, required for cloud
OLLAMA_MODEL=llama3.2                        # default

# --- OpenRouter ---
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet # default
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1  # default
```

---

## Settings Class

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    provider: Literal["anthropic", "openai", "gemini", "ollama", "openrouter"] = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    google_api_key: str | None = None
    gemini_model: str = "gemini-2.5-pro"

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str | None = None   # optional; required for cloud
    ollama_model: str = "llama3.2"

    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
```

### Validation

`@model_validator(mode="after")` raises `ValueError` at startup if:
- `PROVIDER=anthropic` and `ANTHROPIC_API_KEY` is missing
- `PROVIDER=openai` and `OPENAI_API_KEY` is missing
- `PROVIDER=gemini` and `GOOGLE_API_KEY` is missing
- `PROVIDER=openrouter` and `OPENROUTER_API_KEY` is missing
- `PROVIDER=ollama` → no key required (key is optional for cloud upgrade)

### `build_model()` return values

| Provider | Returns |
|----------|---------|
| `anthropic` | `"anthropic:{anthropic_model}"` (string) |
| `openai` | `"openai:{openai_model}"` (string) |
| `gemini` | `"google-gla:{gemini_model}"` (string) |
| `ollama` | `OpenAIModel(ollama_model, base_url=ollama_base_url, api_key=ollama_api_key)` |
| `openrouter` | `OpenAIModel(openrouter_model, base_url=openrouter_base_url, api_key=openrouter_api_key)` |

Ollama and OpenRouter both use `pydantic_ai.models.openai.OpenAIModel` with a custom base URL (OpenAI-compatible API).

---

## OrchestratorAgent Change

Minimal diff — only the default argument:

```python
def __init__(self, model=None) -> None:
    if model is None:
        from config import settings
        model = settings.build_model()
    ...
```

Explicit `model=` overrides (used in all existing tests with `model="test"`) continue to work unchanged.

---

## Files

| Action | File |
|--------|------|
| Create | `backend/config.py` |
| Create | `backend/.env.example` |
| Create | `backend/.env` (gitignored) |
| Modify | `backend/agents/orchestrator.py` |
| Modify | `backend/pyproject.toml` (add `pydantic-settings`) |
| Check | `.gitignore` — ensure `backend/.env` is ignored |
| Create | `backend/tests/test_config.py` |

---

## Tests

All tests construct `Settings(...)` directly with explicit kwargs — no `.env` file needed.

- `PROVIDER=ollama` → no key required, `build_model()` returns `OpenAIModel` pointing to localhost
- `PROVIDER=anthropic` + key → `build_model()` returns `"anthropic:claude-3-5-sonnet-20241022"`
- `PROVIDER=anthropic` + no key → `ValidationError` on construction
- `PROVIDER=gemini` + key → `build_model()` returns `"google-gla:gemini-2.5-pro"`
- `PROVIDER=openrouter` + key → `build_model()` returns `OpenAIModel` with OpenRouter base URL
- Custom model override: `ANTHROPIC_MODEL=claude-3-opus-20240229` reflected in `build_model()`
- Ollama cloud: `OLLAMA_BASE_URL=https://ollama.com/v1` + key → `OpenAIModel` with cloud URL
- All 48 existing tests continue to pass (no change to test infrastructure)
