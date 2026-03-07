# E2 – Intelligente Themenidentifikation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement EPIC 2 – aus einem validierten GewerksProfilModel werden automatisch Forschungsfragen, Keyword-Queries und bilinguale Suchstrategien generiert (E2-S1 regelbasiert, E2-S2+S3 LLM-gestützt via pydantic-ai).

**Architecture:** Drei aufeinander aufbauende Komponenten: (1) `KeywordExtractor` – deterministisch, extrahiert Boolean-Queries direkt aus Profilfeldern ohne LLM. (2) `OrchestratorAgent` – pydantic-ai Agent mit Chain-of-Thought, generiert Forschungsfragen und bilinguale Query-Expansion. (3) `SearchStrategyModel` – typsicheres Pydantic-Ausgabemodell, das beide Ergebnisse vereint.

**Tech Stack:** Python 3.12+, pydantic-ai>=0.0.36 (latest), pydantic v2, anthropic claude-3-5-sonnet, pytest, uv

---

## Codebase Context

```
backend/
├── agents/
│   └── profile_parser.py       # E1: ProfileParsingAgent – Vorlage für Agent-Stil
├── schemas/
│   └── gewerksprofil.py        # GewerksProfilModel – Input für E2
├── data/profiles/
│   ├── maurer.json             # Testdaten
│   ├── tischler.json
│   └── elektrotechniker.json
├── tests/
│   └── test_profile_parser.py  # Vorlage für Teststruktur
└── pyproject.toml              # Dependencies
```

**Wichtig:** Kein `src/`-Layout. `pythonpath = ["."]` in pyproject.toml. Import-Style: `from schemas.gewerksprofil import GewerksProfilModel`.

---

## Task 1: Branch anlegen + pydantic-ai installieren

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock` (automatisch via uv)

**Step 1: Feature-Branch erstellen**

```bash
cd /home/alex/dev/work/bit.transfer
git checkout -b feature/e2-intelligente-themenidentifikation
```

Expected: `Switched to a new branch 'feature/e2-intelligente-themenidentifikation'`

**Step 2: pydantic-ai + anthropic installieren**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv add pydantic-ai anthropic
```

Expected: Adds `pydantic-ai` und `anthropic` zu `pyproject.toml` und `uv.lock`.

**Step 3: Installation verifizieren**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run python -c "import pydantic_ai; print(pydantic_ai.__version__)"
```

Expected: Gibt eine Versionsnummer aus (z.B. `0.0.36` oder neuer).

**Step 4: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add pydantic-ai and anthropic dependencies for E2"
```

---

## Task 2: SearchStrategyModel definieren (Pydantic-Datenmodell)

**Files:**
- Create: `backend/schemas/search_strategy.py`
- Modify: `backend/schemas/__init__.py`
- Test: `backend/tests/test_search_strategy_model.py`

**Step 1: Failing test schreiben**

```python
# backend/tests/test_search_strategy_model.py
import pytest
from pydantic import ValidationError

from schemas.search_strategy import ForschungsFrage, SearchStrategyModel


class TestForschungsFrageModel:
    def test_valid_frage_creates_model(self):
        frage = ForschungsFrage(
            frage="Welche ergonomischen Risiken bestehen beim Mauern?",
            bezug_profilfelder=["arbeitsbedingungen", "techniken_manuell"],
            prioritaet=1,
        )
        assert frage.frage == "Welche ergonomischen Risiken bestehen beim Mauern?"
        assert "arbeitsbedingungen" in frage.bezug_profilfelder

    def test_prioritaet_must_be_1_to_3(self):
        with pytest.raises(ValidationError):
            ForschungsFrage(
                frage="Test",
                bezug_profilfelder=["kernkompetenzen"],
                prioritaet=0,
            )

    def test_bezug_profilfelder_min_one(self):
        with pytest.raises(ValidationError):
            ForschungsFrage(
                frage="Test",
                bezug_profilfelder=[],
                prioritaet=1,
            )


class TestSearchStrategyModel:
    def test_valid_model_creates_correctly(self):
        strategy = SearchStrategyModel(
            gewerk_id="A_01_MAURER",
            forschungsfragen=[
                ForschungsFrage(
                    frage="Welche Materialien optimieren Mauerwerk?",
                    bezug_profilfelder=["werkstoffe"],
                    prioritaet=1,
                )
            ],
            keyword_queries_de=["Mauerwerk AND Ziegel", "Beton AND Bewehrung"],
            keyword_queries_en=["masonry AND brick", "concrete AND reinforcement"],
            semantic_queries_en=["load-bearing masonry construction techniques"],
            hyde_abstracts=[],
            concept_filter_ids=None,
            max_results_per_query=50,
        )
        assert strategy.gewerk_id == "A_01_MAURER"
        assert len(strategy.forschungsfragen) == 1
        assert len(strategy.keyword_queries_de) >= 1

    def test_forschungsfragen_min_3_required(self):
        """SearchStrategyModel braucht mindestens 3 Forschungsfragen für LLM-Output."""
        with pytest.raises(ValidationError):
            SearchStrategyModel(
                gewerk_id="TEST",
                forschungsfragen=[
                    ForschungsFrage(frage="F1", bezug_profilfelder=["x"], prioritaet=1),
                    ForschungsFrage(frage="F2", bezug_profilfelder=["y"], prioritaet=2),
                ],
                keyword_queries_de=["a"],
                keyword_queries_en=["b"],
                semantic_queries_en=["c"],
                hyde_abstracts=[],
                concept_filter_ids=None,
                max_results_per_query=50,
            )

    def test_max_results_default_is_50(self):
        strategy = SearchStrategyModel(
            gewerk_id="TEST",
            forschungsfragen=[
                ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["x"], prioritaet=1)
                for i in range(3)
            ],
            keyword_queries_de=["a"],
            keyword_queries_en=["b"],
            semantic_queries_en=["c"],
            hyde_abstracts=[],
            concept_filter_ids=None,
        )
        assert strategy.max_results_per_query == 50

    def test_keyword_queries_de_min_one(self):
        with pytest.raises(ValidationError):
            SearchStrategyModel(
                gewerk_id="TEST",
                forschungsfragen=[
                    ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["x"], prioritaet=1)
                    for i in range(3)
                ],
                keyword_queries_de=[],
                keyword_queries_en=["b"],
                semantic_queries_en=["c"],
                hyde_abstracts=[],
                concept_filter_ids=None,
            )
```

**Step 2: Test ausführen (muss FAIL)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_search_strategy_model.py -v
```

Expected: `ImportError: No module named 'schemas.search_strategy'`

**Step 3: Implementierung schreiben**

```python
# backend/schemas/search_strategy.py
from typing import Annotated

from pydantic import BaseModel, Field


class ForschungsFrage(BaseModel):
    """Eine spezifische Forschungsfrage mit Bezug zum Gewerks-Profil."""

    frage: str = Field(..., description="Die Forschungsfrage als vollständiger Satz")
    bezug_profilfelder: list[str] = Field(
        ...,
        min_length=1,
        description="Profilfelder (z.B. 'kernkompetenzen', 'werkstoffe') zu denen diese Frage gehört",
    )
    prioritaet: Annotated[int, Field(ge=1, le=3)] = Field(
        ...,
        description="Priorität 1 (hoch) bis 3 (niedrig)",
    )


class SearchStrategyModel(BaseModel):
    """Typsicheres Ausgabemodell des Orchestrator-Agents.

    Enthält alle Forschungsfragen und Suchstrategien für eine föderierte
    Literaturrecherche zu einem spezifischen Gewerk.
    """

    gewerk_id: str = Field(..., description="Referenz zum Quell-Profil")
    forschungsfragen: list[ForschungsFrage] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="3–10 spezifische Forschungsfragen",
    )
    keyword_queries_de: list[str] = Field(
        ...,
        min_length=1,
        description="Deutsche Keyword-Queries mit Bool-Operatoren (AND/OR)",
    )
    keyword_queries_en: list[str] = Field(
        ...,
        min_length=1,
        description="Englische Keyword-Queries mit Bool-Operatoren",
    )
    semantic_queries_en: list[str] = Field(
        ...,
        min_length=1,
        description="Englische Absatz-Descriptions für Semantic Search",
    )
    hyde_abstracts: list[str] = Field(
        default_factory=list,
        description="Hypothetische Abstracts für HyDE-Retrieval (optional)",
    )
    concept_filter_ids: list[str] | None = Field(
        default=None,
        description="OpenAlex Concept-IDs zur Eingrenzung (optional)",
    )
    max_results_per_query: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Zielanzahl Ergebnisse pro Query",
    )
```

**Step 4: `__init__.py` updaten**

```python
# backend/schemas/__init__.py  – bestehende Imports BEHALTEN, nur ergänzen:
from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import ForschungsFrage, SearchStrategyModel

__all__ = ["GewerksProfilModel", "ForschungsFrage", "SearchStrategyModel"]
```

**Step 5: Tests laufen lassen (müssen PASS)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_search_strategy_model.py -v
```

Expected: `5 passed`

**Step 6: Alle Tests laufen lassen (darf nichts brechen)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v
```

Expected: Alle Tests grün.

**Step 7: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/schemas/search_strategy.py backend/schemas/__init__.py backend/tests/test_search_strategy_model.py
git commit -m "feat: add SearchStrategyModel and ForschungsFrage Pydantic models (E2)"
```

---

## Task 3: E2-S1 – KeywordExtractor (deterministisch, kein LLM)

**Files:**
- Create: `backend/agents/keyword_extractor.py`
- Test: `backend/tests/test_keyword_extractor.py`

**Zweck:** Extrahiert direkt aus den Profilfeldern Boolean-Queries. Kein LLM, kein API-Call. Dient als MVP-Fallback und als Input für den Orchestrator.

**Step 1: Failing test schreiben**

```python
# backend/tests/test_keyword_extractor.py
import json
from pathlib import Path

import pytest

from agents.keyword_extractor import KeywordExtractor
from schemas.gewerksprofil import GewerksProfilModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


@pytest.fixture
def maurer_profil() -> GewerksProfilModel:
    text = (PROFILES_DIR / "maurer.json").read_text(encoding="utf-8")
    return GewerksProfilModel.model_validate_json(text)


@pytest.fixture
def extractor() -> KeywordExtractor:
    return KeywordExtractor()


class TestExtractKeywords:
    def test_returns_at_least_5_queries(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        assert len(queries) >= 5

    def test_all_queries_are_strings(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        assert all(isinstance(q, str) for q in queries)

    def test_queries_contain_boolean_operators(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        has_operator = any("AND" in q or "OR" in q for q in queries)
        assert has_operator, "Mindestens eine Query muss AND oder OR enthalten"

    def test_queries_contain_profile_terms(self, extractor, maurer_profil):
        queries = extractor.extract_keyword_queries(maurer_profil)
        all_terms = " ".join(queries).lower()
        # Mindestens ein Begriff aus kernkompetenzen muss vorkommen
        kernkompetenzen_terms = [k.lower() for k in maurer_profil.kernkompetenzen]
        found = any(term in all_terms for term in kernkompetenzen_terms)
        assert found, "Queries müssen Begriffe aus kernkompetenzen enthalten"

    def test_no_llm_dependency(self, extractor, maurer_profil):
        """KeywordExtractor darf keine LLM-Aufrufe machen – rein deterministisch."""
        # Wenn er LLM nutzen würde, würde ein ANTHROPIC_API_KEY fehlen → ImportError/Exception
        # Hier reicht es zu prüfen, dass die Klasse kein pydantic_ai.Agent-Attribut hat
        assert not hasattr(extractor, "agent"), "KeywordExtractor darf keinen pydantic-ai Agent haben"

    def test_tischler_profil_also_works(self, extractor):
        text = (PROFILES_DIR / "tischler.json").read_text(encoding="utf-8")
        profil = GewerksProfilModel.model_validate_json(text)
        queries = extractor.extract_keyword_queries(profil)
        assert len(queries) >= 5

    def test_elektrotechniker_profil_also_works(self, extractor):
        text = (PROFILES_DIR / "elektrotechniker.json").read_text(encoding="utf-8")
        profil = GewerksProfilModel.model_validate_json(text)
        queries = extractor.extract_keyword_queries(profil)
        assert len(queries) >= 5


class TestQueryGrouping:
    def test_generates_queries_per_profilfeld(self, extractor, maurer_profil):
        """Jedes Kernfeld (kernkompetenzen, techniken, werkstoffe) trägt Queries bei."""
        queries_by_field = extractor.extract_queries_by_field(maurer_profil)
        assert "kernkompetenzen" in queries_by_field
        assert "werkstoffe" in queries_by_field
        assert len(queries_by_field["kernkompetenzen"]) >= 1

    def test_combines_related_terms_with_or(self, extractor, maurer_profil):
        """Synonyme/verwandte Begriffe werden mit OR verbunden."""
        queries_by_field = extractor.extract_queries_by_field(maurer_profil)
        all_queries = " ".join(str(v) for v in queries_by_field.values())
        assert "OR" in all_queries
```

**Step 2: Test ausführen (muss FAIL)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_keyword_extractor.py -v
```

Expected: `ImportError: No module named 'agents.keyword_extractor'`

**Step 3: Implementierung schreiben**

```python
# backend/agents/keyword_extractor.py
from schemas.gewerksprofil import GewerksProfilModel


class KeywordExtractor:
    """Deterministischer Keyword-Extraktor für Gewerks-Profile.

    Generiert Boolean-Keyword-Queries direkt aus den Profilfeldern.
    Kein LLM, kein API-Call. Vollständig reproduzierbar.

    E2-S1: MVP-Implementierung (Meilenstein M1).
    """

    def extract_keyword_queries(self, profil: GewerksProfilModel) -> list[str]:
        """Extrahiert mindestens 5 Boolean-Queries aus dem Profil.

        Strategie:
        - Pro Kernkompetenz: eine OR-verknüpfte Query
        - Pro Technikgruppe: AND-verknüpfte Kombination
        - Pro Werkstoff: kombiniert mit Gewerk-Name
        """
        queries: list[str] = []
        queries.extend(self._queries_from_kernkompetenzen(profil))
        queries.extend(self._queries_from_techniken(profil))
        queries.extend(self._queries_from_werkstoffe(profil))
        queries.extend(self._queries_combined(profil))
        return queries

    def extract_queries_by_field(self, profil: GewerksProfilModel) -> dict[str, list[str]]:
        """Gibt Queries gruppiert nach Profilfeld zurück.

        Wird vom OrchestratorAgent genutzt, um Queries dem Kontext zuzuordnen.
        """
        return {
            "kernkompetenzen": self._queries_from_kernkompetenzen(profil),
            "techniken_manuell": self._queries_from_techniken_manuell(profil),
            "techniken_maschinell": self._queries_from_techniken_maschinell(profil),
            "werkstoffe": self._queries_from_werkstoffe(profil),
        }

    # --- Private Hilfsmethoden ---

    def _queries_from_kernkompetenzen(self, profil: GewerksProfilModel) -> list[str]:
        kompetenzen = profil.kernkompetenzen
        if not kompetenzen:
            return []
        # Alle Kernkompetenzen als eine große OR-Query
        or_query = " OR ".join(f'"{k}"' for k in kompetenzen[:6])
        queries = [or_query]
        # Zusätzlich: Gewerk-Name AND erste Kompetenz
        if len(kompetenzen) >= 2:
            queries.append(f'"{profil.gewerk_name}" AND "{kompetenzen[0]}"')
        return queries

    def _queries_from_techniken(self, profil: GewerksProfilModel) -> list[str]:
        queries = []
        queries.extend(self._queries_from_techniken_manuell(profil))
        queries.extend(self._queries_from_techniken_maschinell(profil))
        return queries

    def _queries_from_techniken_manuell(self, profil: GewerksProfilModel) -> list[str]:
        techniken = profil.techniken_manuell
        if not techniken:
            return []
        or_query = " OR ".join(f'"{t}"' for t in techniken[:5])
        return [f"({or_query}) AND Handwerk"]

    def _queries_from_techniken_maschinell(self, profil: GewerksProfilModel) -> list[str]:
        techniken = profil.techniken_maschinell
        if not techniken:
            return []
        or_query = " OR ".join(f'"{t}"' for t in techniken[:4])
        return [f"({or_query}) AND Maschine"]

    def _queries_from_werkstoffe(self, profil: GewerksProfilModel) -> list[str]:
        werkstoffe = profil.werkstoffe
        if not werkstoffe:
            return []
        or_query = " OR ".join(f'"{w}"' for w in werkstoffe[:5])
        return [f"({or_query}) AND Verarbeitung"]

    def _queries_combined(self, profil: GewerksProfilModel) -> list[str]:
        """Cross-Feld-Queries: Werkstoff AND Technik."""
        if not profil.werkstoffe or not profil.techniken_manuell:
            return []
        return [
            f'"{profil.werkstoffe[0]}" AND "{profil.techniken_manuell[0]}"',
            f'"{profil.gewerk_name}" AND Forschung',
        ]
```

**Step 4: Tests laufen lassen**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_keyword_extractor.py -v
```

Expected: `9 passed`

**Step 5: Alle Tests**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v
```

Expected: Alle grün.

**Step 6: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/agents/keyword_extractor.py backend/tests/test_keyword_extractor.py
git commit -m "feat: add KeywordExtractor for rule-based query generation (E2-S1)"
```

---

## Task 4: E2-S2 + E2-S3 – OrchestratorAgent (LLM + bilinguale Query-Expansion)

**Files:**
- Create: `backend/agents/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`

**Wichtige Hinweise zu pydantic-ai:**
- Import: `from pydantic_ai import Agent`
- `Agent(model='claude-3-5-sonnet-20241022', output_type=SearchStrategyModel, deps_type=GewerksProfilModel)`
- `result = await agent.run(user_prompt, deps=profil)` → `result.output` ist das `SearchStrategyModel`
- System-Prompt mit `@agent.system_prompt` decorator, erhält `RunContext[GewerksProfilModel]`
- API-Key kommt aus Env-Variable `ANTHROPIC_API_KEY`
- Für Tests: `TestModel` aus `pydantic_ai.models.test` nutzen (kein echter API-Call!)

**Step 1: Failing test schreiben**

```python
# backend/tests/test_orchestrator.py
"""Tests für den OrchestratorAgent (E2-S2 + E2-S3).

Nutzt pydantic_ai.models.test.TestModel für deterministische Tests ohne API-Call.
TestModel gibt immer ein valides SearchStrategyModel zurück – wir testen Struktur und Logik.
"""
import asyncio
from pathlib import Path

import pytest

from agents.orchestrator import OrchestratorAgent
from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import SearchStrategyModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


@pytest.fixture
def maurer_profil() -> GewerksProfilModel:
    text = (PROFILES_DIR / "maurer.json").read_text(encoding="utf-8")
    return GewerksProfilModel.model_validate_json(text)


@pytest.fixture
def tischler_profil() -> GewerksProfilModel:
    text = (PROFILES_DIR / "tischler.json").read_text(encoding="utf-8")
    return GewerksProfilModel.model_validate_json(text)


class TestOrchestratorInit:
    def test_creates_with_default_model(self):
        agent = OrchestratorAgent()
        assert agent is not None

    def test_creates_with_custom_model(self):
        agent = OrchestratorAgent(model="openai:gpt-4o")
        assert agent is not None

    def test_has_pydantic_ai_agent(self):
        from pydantic_ai import Agent
        orchestrator = OrchestratorAgent()
        assert isinstance(orchestrator.agent, Agent)


class TestGenerateStrategy:
    """Tests mit TestModel – kein echter LLM-Call."""

    def test_returns_search_strategy_model(self, maurer_profil):
        """OrchestratorAgent.generate() gibt ein SearchStrategyModel zurück."""
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(maurer_profil))
        assert isinstance(result, SearchStrategyModel)

    def test_gewerk_id_matches_input(self, maurer_profil):
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(maurer_profil))
        assert result.gewerk_id == maurer_profil.gewerk_id

    def test_has_at_least_3_forschungsfragen(self, maurer_profil):
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(maurer_profil))
        assert len(result.forschungsfragen) >= 3

    def test_has_german_and_english_queries(self, maurer_profil):
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(maurer_profil))
        assert len(result.keyword_queries_de) >= 1, "Muss deutsche Queries haben"
        assert len(result.keyword_queries_en) >= 1, "Muss englische Queries haben"

    def test_has_semantic_queries(self, maurer_profil):
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(maurer_profil))
        assert len(result.semantic_queries_en) >= 1

    def test_tischler_also_works(self, tischler_profil):
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(tischler_profil))
        assert isinstance(result, SearchStrategyModel)
        assert result.gewerk_id == tischler_profil.gewerk_id

    def test_keyword_extractor_queries_are_included(self, maurer_profil):
        """OrchestratorAgent soll vorhandene KeywordExtractor-Queries als Basis nutzen."""
        agent = OrchestratorAgent(model="test")
        result = asyncio.run(agent.generate(maurer_profil))
        # Deutsche Queries müssen mindestens die deterministischen enthalten
        assert len(result.keyword_queries_de) >= 5


class TestSystemPrompt:
    def test_system_prompt_contains_profil_fields(self, maurer_profil):
        """Der System-Prompt muss das Profil referenzieren, damit der LLM Kontext hat."""
        orchestrator = OrchestratorAgent(model="test")
        prompt = orchestrator._build_user_prompt(maurer_profil)
        assert "A_01_MAURER" in prompt or "Maurer" in prompt
        assert maurer_profil.kernkompetenzen[0] in prompt
```

**Step 2: Tests ausführen (muss FAIL)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_orchestrator.py -v
```

Expected: `ImportError: No module named 'agents.orchestrator'`

**Step 3: OrchestratorAgent implementieren**

```python
# backend/agents/orchestrator.py
"""OrchestratorAgent – E2-S2 + E2-S3.

Generiert Forschungsfragen und bilinguale Suchstrategien via Chain-of-Thought.
Nutzt pydantic-ai für typsichere LLM-Outputs.

Abhängigkeiten:
- ANTHROPIC_API_KEY in Env-Variable (für echte Calls)
- Für Tests: model="test" (kein API-Call)
"""
from pydantic_ai import Agent, RunContext

from agents.keyword_extractor import KeywordExtractor
from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import ForschungsFrage, SearchStrategyModel


class OrchestratorAgent:
    """Management-Agent der E2-Pipeline.

    Generiert aus einem validierten GewerksProfilModel:
    - 3–10 spezifische Forschungsfragen (Chain-of-Thought)
    - Bilinguale Keyword-Queries (DE + EN)
    - Semantic Search Queries (EN)
    - Optionale HyDE-Abstracts

    E2-S2 + E2-S3: LLM-basiert, nutzt pydantic-ai Agent.
    """

    def __init__(self, model: str = "anthropic:claude-3-5-sonnet-20241022") -> None:
        self._keyword_extractor = KeywordExtractor()
        self.agent: Agent[GewerksProfilModel, SearchStrategyModel] = Agent(
            model=model,
            output_type=SearchStrategyModel,
            deps_type=GewerksProfilModel,
            system_prompt=self._static_system_prompt(),
        )
        self._register_dynamic_system_prompt()

    async def generate(self, profil: GewerksProfilModel) -> SearchStrategyModel:
        """Generiert eine vollständige Suchstrategie für das gegebene Profil.

        Args:
            profil: Validiertes GewerksProfilModel (Output von ProfileParsingAgent).

        Returns:
            SearchStrategyModel mit Forschungsfragen und bilingualen Queries.
        """
        user_prompt = self._build_user_prompt(profil)
        result = await self.agent.run(user_prompt, deps=profil)
        strategy = result.output

        # Stelle sicher, dass gewerk_id korrekt gesetzt ist (LLM könnte es falsch setzen)
        strategy = SearchStrategyModel(
            **{
                **strategy.model_dump(),
                "gewerk_id": profil.gewerk_id,
                "keyword_queries_de": self._merge_de_queries(profil, strategy.keyword_queries_de),
            }
        )
        return strategy

    def _build_user_prompt(self, profil: GewerksProfilModel) -> str:
        """Baut den User-Prompt mit vollem Profil-Kontext für Chain-of-Thought."""
        kernkompetenzen = ", ".join(profil.kernkompetenzen[:8])
        techniken = ", ".join(profil.techniken_manuell[:5] + profil.techniken_maschinell[:5])
        werkstoffe = ", ".join(profil.werkstoffe[:6])
        software = ", ".join(profil.software_tools[:4])

        return f"""Analysiere das folgende Handwerksgewerk und generiere eine wissenschaftliche Recherchestrategie.

**Gewerk:** {profil.gewerk_name} (ID: {profil.gewerk_id}, HWO-Anlage: {profil.hwo_anlage})

**Kernkompetenzen:** {kernkompetenzen}

**Techniken:** {techniken}

**Werkstoffe:** {werkstoffe}

**Software/Digitale Werkzeuge:** {software}

**Aufgabe (Chain-of-Thought):**
1. Überlege: Welche wissenschaftlichen Forschungsfelder sind für dieses Gewerk relevant?
2. Leite 3–10 spezifische Forschungsfragen ab, jede mit Bezug zu mindestens einem Profilfeld.
3. Generiere je 5–10 deutsche Keyword-Queries mit Boolean-Operatoren (AND, OR).
4. Übersetze und erweitere die Queries ins Englische (mindestens 2 EN-Varianten pro DE-Query).
5. Formuliere 2–3 englische Absatz-Descriptions für Semantic Search.

Antworte NUR mit dem strukturierten SearchStrategyModel-Output."""

    def _static_system_prompt(self) -> str:
        return """Du bist ein wissenschaftlicher Recherche-Spezialist für das deutsche Handwerk.
Deine Aufgabe: Aus einem Gewerks-Profil der Handwerksordnung (HWO) erstellst du
präzise Forschungsfragen und bilinguale Suchstrategien für akademische Datenbanken.

Prinzipien:
- Spezifität vor Allgemeinheit: Lieber enge, präzise Queries als breite
- Bilingualität: Jede deutsche Query hat mindestens 2 englische Varianten
- Feldabdeckung: Mindestens 80% der Profilfelder sind in Forschungsfragen abgedeckt
- Boolean-Syntax: AND für Eingrenzung, OR für Synonyme/Varianten"""

    def _register_dynamic_system_prompt(self) -> None:
        """Registriert einen dynamischen System-Prompt, der Profil-Daten einbettet."""

        @self.agent.system_prompt
        async def add_profil_context(ctx: RunContext[GewerksProfilModel]) -> str:
            profil = ctx.deps
            taetigkeiten = []
            for bereich, liste in profil.taetigkeitsfelder.items():
                taetigkeiten.extend([f"{bereich}: {t}" for t in liste[:3]])
            taetigkeiten_str = "; ".join(taetigkeiten[:6])
            return f"\nAktuelles Profil-Kontext:\nGewerk-ID: {profil.gewerk_id}\nTätigkeiten: {taetigkeiten_str}"

    def _merge_de_queries(
        self, profil: GewerksProfilModel, llm_queries: list[str]
    ) -> list[str]:
        """Merged deterministisch generierte Queries mit LLM-Queries (Duplikate entfernen)."""
        deterministic = self._keyword_extractor.extract_keyword_queries(profil)
        all_queries = list(deterministic)
        for q in llm_queries:
            if q not in all_queries:
                all_queries.append(q)
        return all_queries
```

**Step 4: Tests laufen lassen**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_orchestrator.py -v
```

Expected: `9 passed` (TestModel simuliert valide SearchStrategyModel-Outputs)

> **Hinweis:** Falls `TestModel` kein valides `SearchStrategyModel` generiert (min_length Constraints), kann es nötig sein, die pydantic-ai TestModel-Dokumentation zu prüfen. In neueren pydantic-ai Versionen können Constraints an `TestModel` übergeben werden.

**Step 5: Alle Tests laufen lassen**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v
```

Expected: Alle grün.

**Step 6: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/agents/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: add OrchestratorAgent with CoT and bilingual query expansion (E2-S2, E2-S3)"
```

---

## Task 5: Agents `__init__.py` updaten + Smoke-Test

**Files:**
- Modify: `backend/agents/__init__.py`
- Modify: `backend/tests/test_orchestrator.py` (ggf. Smoke-Test ergänzen)

**Step 1: `__init__.py` updaten**

```python
# backend/agents/__init__.py
from agents.keyword_extractor import KeywordExtractor
from agents.orchestrator import OrchestratorAgent
from agents.profile_parser import ProfileParsingAgent

__all__ = ["KeywordExtractor", "OrchestratorAgent", "ProfileParsingAgent"]
```

**Step 2: Integration-Smoke-Test schreiben**

```python
# backend/tests/test_e2_integration.py
"""Integrations-Smoke-Test: ProfileParser → OrchestratorAgent.

Testet die vollständige E2-Pipeline ohne echte LLM-Calls.
"""
import asyncio
from pathlib import Path

from agents.orchestrator import OrchestratorAgent
from agents.profile_parser import ProfileParsingAgent
from schemas.search_strategy import SearchStrategyModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


class TestE2Pipeline:
    def test_full_pipeline_maurer(self):
        """E1 → E2: Profile Parser → Orchestrator → SearchStrategyModel."""
        parser = ProfileParsingAgent()
        orchestrator = OrchestratorAgent(model="test")

        profil = parser.parse_file(PROFILES_DIR / "maurer.json")
        strategy = asyncio.run(orchestrator.generate(profil))

        assert isinstance(strategy, SearchStrategyModel)
        assert strategy.gewerk_id == "A_01_MAURER"
        assert len(strategy.forschungsfragen) >= 3
        assert len(strategy.keyword_queries_de) >= 5
        assert len(strategy.keyword_queries_en) >= 1

    def test_full_pipeline_all_three_profiles(self):
        """Alle drei Pilot-Profile laufen durch die Pipeline."""
        parser = ProfileParsingAgent()
        orchestrator = OrchestratorAgent(model="test")

        for filename in ["maurer.json", "tischler.json", "elektrotechniker.json"]:
            profil = parser.parse_file(PROFILES_DIR / filename)
            strategy = asyncio.run(orchestrator.generate(profil))
            assert isinstance(strategy, SearchStrategyModel)
            assert strategy.gewerk_id == profil.gewerk_id
```

**Step 3: Tests laufen lassen**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest tests/test_e2_integration.py -v
```

Expected: `2 passed`

**Step 4: Alle Tests (final)**

```bash
cd /home/alex/dev/work/bit.transfer/backend
uv run pytest -v --tb=short
```

Expected: Alle Tests grün, keine Fehler.

**Step 5: Commit**

```bash
cd /home/alex/dev/work/bit.transfer
git add backend/agents/__init__.py backend/tests/test_e2_integration.py
git commit -m "feat: add E2 integration test and update agents __init__ (E2 complete)"
```

---

## Task 6: PR erstellen

**Step 1: Push Branch**

```bash
cd /home/alex/dev/work/bit.transfer
git push -u origin feature/e2-intelligente-themenidentifikation
```

**Step 2: PR erstellen**

```bash
gh pr create \
  --title "feat: E2 – Intelligente Themenidentifikation" \
  --body "$(cat <<'EOF'
## Summary

- **E2-S1:** `KeywordExtractor` – deterministisch, extrahiert Boolean-Queries aus Profilfeldern (kein LLM)
- **E2-S2:** `OrchestratorAgent` – pydantic-ai Agent mit Chain-of-Thought, generiert 3–10 Forschungsfragen
- **E2-S3:** Bilinguale Query-Expansion (DE+EN) integriert im OrchestratorAgent
- `SearchStrategyModel` + `ForschungsFrage` Pydantic-Modelle als typsichere Pipeline-Schnittstelle

## Test plan

- [ ] `uv run pytest -v` – alle Tests grün
- [ ] `uv run pytest tests/test_search_strategy_model.py` – Modell-Constraints
- [ ] `uv run pytest tests/test_keyword_extractor.py` – deterministische Queries
- [ ] `uv run pytest tests/test_orchestrator.py` – Agent mit TestModel
- [ ] `uv run pytest tests/test_e2_integration.py` – E1→E2 Integrations-Smoke-Test

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Troubleshooting

### pydantic-ai TestModel gibt keine validen Outputs (min_length Constraint)

pydantic-ai's `TestModel` generiert Text-Platzhalter. Wenn `min_length=3` bei `forschungsfragen` fehlschlägt:

```python
# Option A: In Tests result.output mocken
from unittest.mock import AsyncMock, patch

# Option B: TestModel mit custom_output_text parametrisieren (falls pydantic-ai unterstützt)
# Prüfe: https://ai.pydantic.dev/testing/

# Option C: Minimale gültige SearchStrategyModel-Instanz zurückgeben via result_type override
```

### ANTHROPIC_API_KEY fehlt bei echten Calls

Für manuelle Tests mit echtem LLM:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
cd /home/alex/dev/work/bit.transfer/backend
uv run python -c "
import asyncio
from agents.profile_parser import ProfileParsingAgent
from agents.orchestrator import OrchestratorAgent

parser = ProfileParsingAgent()
profil = parser.parse_file('data/profiles/maurer.json')
orchestrator = OrchestratorAgent()  # nutzt echtes Claude-Modell
strategy = asyncio.run(orchestrator.generate(profil))
print(strategy.model_dump_json(indent=2))
"
```
