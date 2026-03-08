"""Tests für den OrchestratorAgent (optimierte Query-Generierung).

Uses mock or TestModel for deterministic tests without real API calls.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.orchestrator import OrchestratorAgent
from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import SearchStrategyModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"

VALID_STRATEGY = SearchStrategyModel(
    gewerk_id="A_01_MAURER",
    semantic_queries_en=[
        "Load-bearing masonry construction encompasses the structural performance of brick "
        "and limestone assemblies.",
        "Mortar joint optimization and thermal bridge mitigation in residential buildings.",
        "Brick masonry structural integrity durability and quality assessment.",
    ],
    boolean_queries_de=[
        '("Mauerwerk" OR "Ziegel" OR "Kalksandstein") AND "Tragfähigkeit"',
        '("Mörtel" OR "Dünnbettmörtel") AND Verarbeitung',
    ],
    boolean_queries_en=[
        '("masonry" OR "brickwork") AND "structural performance"',
        '("mortar" OR "adhesive mortar") AND application',
    ],
)


@pytest.fixture
def maurer_profil() -> GewerksProfilModel:
    text = (PROFILES_DIR / "maurer.json").read_text(encoding="utf-8")
    return GewerksProfilModel.model_validate_json(text)


@pytest.fixture
def tischler_profil() -> GewerksProfilModel:
    text = (PROFILES_DIR / "tischler.json").read_text(encoding="utf-8")
    return GewerksProfilModel.model_validate_json(text)


def _make_mock_result(strategy: SearchStrategyModel):
    mock_result = MagicMock()
    mock_result.output = strategy
    mock_result.data = strategy
    return mock_result


class TestOrchestratorInit:
    def test_creates_with_default_model(self):
        agent = OrchestratorAgent()
        assert agent is not None

    def test_creates_with_custom_model_string(self):
        agent = OrchestratorAgent(model="openai:gpt-4o")
        assert agent is not None

    def test_has_pydantic_ai_agent_attribute(self):
        from pydantic_ai import Agent
        orchestrator = OrchestratorAgent()
        assert hasattr(orchestrator, "agent")
        assert isinstance(orchestrator.agent, Agent)


class TestGenerateStrategy:
    """Tests using mocked agent.run to avoid real API calls."""

    def test_generate_returns_search_strategy_model(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = _make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert isinstance(result, SearchStrategyModel)

    def test_generate_sets_correct_gewerk_id(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = _make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert result.gewerk_id == maurer_profil.gewerk_id

    def test_generate_produces_semantic_queries_en(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = _make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert 3 <= len(result.semantic_queries_en) <= 10

    def test_generate_produces_boolean_queries_de(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = _make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert 2 <= len(result.boolean_queries_de) <= 3

    def test_generate_produces_boolean_queries_en(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = _make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert 2 <= len(result.boolean_queries_en) <= 3

    def test_generate_boolean_queries_contain_operators(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = _make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        all_queries = result.boolean_queries_de + result.boolean_queries_en
        assert any("AND" in q or "OR" in q for q in all_queries)

    def test_tischler_also_works(self, tischler_profil):
        orchestrator = OrchestratorAgent()
        tischler_strategy = SearchStrategyModel(
            gewerk_id="A_13_TISCHLER",
            semantic_queries_en=[
                "Woodworking and joinery techniques encompass furniture manufacturing.",
                "Timber processing and wood material properties for structural applications.",
                "Surface finishing and coating techniques for wood products.",
            ],
            boolean_queries_de=[
                '("Holz" OR "Massivholz" OR "Furnier") AND Verarbeitung',
                '("Tischler" OR "Schreiner") AND Handwerk',
            ],
            boolean_queries_en=[
                '("wood" OR "timber") AND "manufacturing"',
                '("joinery" OR "carpentry") AND techniques',
            ],
        )
        mock_result = _make_mock_result(tischler_strategy)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(tischler_profil))
        assert isinstance(result, SearchStrategyModel)
        assert result.gewerk_id == tischler_profil.gewerk_id


class TestSystemPrompt:
    def test_system_prompt_contains_openalex_rules(self):
        orchestrator = OrchestratorAgent()
        # Check that the registered system prompt contains OpenAlex info
        # The static prompt is embedded in the agent via _register_system_prompts
        # We verify the orchestrator's agent has system prompts registered
        assert orchestrator.agent is not None
        # Check the source of system prompts includes "OpenAlex"
        import inspect
        source = inspect.getsource(orchestrator._register_system_prompts)
        assert "OpenAlex" in source

    def test_no_keyword_extractor_dependency(self):
        orchestrator = OrchestratorAgent()
        assert not hasattr(orchestrator, "_keyword_extractor")

    def test_user_prompt_contains_gewerk_info(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        prompt = orchestrator._build_user_prompt(maurer_profil)
        assert "Maurer" in prompt or "A_01_MAURER" in prompt

    def test_user_prompt_contains_kernkompetenzen(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        prompt = orchestrator._build_user_prompt(maurer_profil)
        assert maurer_profil.kernkompetenzen[0] in prompt

    def test_user_prompt_contains_recipe_instructions(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        prompt = orchestrator._build_user_prompt(maurer_profil)
        assert "Schritt 2" in prompt
        assert "Schritt 3" in prompt
        assert "Schritt 4" in prompt
        assert "Selbstprüfung" in prompt
        assert "Synonym-Cluster" in prompt
        assert "Wildcard" in prompt
        assert "Proximity" in prompt
        assert "Wenn eine Prüfung fehlschlägt" in prompt
