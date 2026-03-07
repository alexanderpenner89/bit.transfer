"""Tests für den OrchestratorAgent (E2-S2 + E2-S3).

Uses mock or TestModel for deterministic tests without real API calls.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.orchestrator import OrchestratorAgent
from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import ForschungsFrage, SearchStrategyModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"

VALID_STRATEGY = SearchStrategyModel(
    gewerk_id="A_01_MAURER",
    forschungsfragen=[
        ForschungsFrage(frage=f"Forschungsfrage {i}", bezug_profilfelder=["kernkompetenzen"], prioritaet=1)
        for i in range(3)
    ],
    keyword_queries_de=["Mauerwerk AND Ziegel", "Beton AND Bewehrung", "Mörtel OR Putz", "Fassade AND Dämmung", "Naturstein AND Bearbeitung"],
    keyword_queries_en=["masonry AND brick", "concrete AND reinforcement"],
    semantic_queries_en=["load-bearing masonry construction techniques in building"],
    hyde_abstracts=[],
    concept_filter_ids=None,
    max_results_per_query=50,
)


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

    def _make_mock_result(self, strategy: SearchStrategyModel):
        """Creates a mock result that mimics pydantic-ai AgentRunResult."""
        mock_result = MagicMock()
        mock_result.output = strategy
        # Some pydantic-ai versions use .data instead of .output
        mock_result.data = strategy
        return mock_result

    def test_returns_search_strategy_model(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = self._make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert isinstance(result, SearchStrategyModel)

    def test_gewerk_id_matches_input(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = self._make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert result.gewerk_id == maurer_profil.gewerk_id

    def test_has_at_least_3_forschungsfragen(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = self._make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert len(result.forschungsfragen) >= 3

    def test_has_german_and_english_queries(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = self._make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert len(result.keyword_queries_de) >= 1
        assert len(result.keyword_queries_en) >= 1

    def test_has_semantic_queries(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        mock_result = self._make_mock_result(VALID_STRATEGY)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        assert len(result.semantic_queries_en) >= 1

    def test_deterministic_queries_merged_from_keyword_extractor(self, maurer_profil):
        """OrchestratorAgent merges KeywordExtractor queries into keyword_queries_de."""
        orchestrator = OrchestratorAgent()
        # Return a strategy with only 2 DE queries from "LLM"
        sparse_strategy = SearchStrategyModel(
            gewerk_id="A_01_MAURER",
            forschungsfragen=[
                ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["kernkompetenzen"], prioritaet=1)
                for i in range(3)
            ],
            keyword_queries_de=["LLM Query 1", "LLM Query 2"],
            keyword_queries_en=["en query 1"],
            semantic_queries_en=["semantic query"],
            hyde_abstracts=[],
            concept_filter_ids=None,
        )
        mock_result = self._make_mock_result(sparse_strategy)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(maurer_profil))
        # After merging with KeywordExtractor, should have > 2 DE queries
        assert len(result.keyword_queries_de) > 2

    def test_tischler_also_works(self, tischler_profil):
        orchestrator = OrchestratorAgent()
        tischler_strategy = SearchStrategyModel(
            gewerk_id="A_13_TISCHLER",
            forschungsfragen=[
                ForschungsFrage(frage=f"F{i}", bezug_profilfelder=["kernkompetenzen"], prioritaet=1)
                for i in range(3)
            ],
            keyword_queries_de=["Holz AND Verarbeitung"],
            keyword_queries_en=["wood AND processing"],
            semantic_queries_en=["woodworking techniques and materials"],
            hyde_abstracts=[],
            concept_filter_ids=None,
        )
        mock_result = self._make_mock_result(tischler_strategy)
        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(tischler_profil))
        assert isinstance(result, SearchStrategyModel)
        assert result.gewerk_id == tischler_profil.gewerk_id


class TestSystemPrompt:
    def test_user_prompt_contains_gewerk_info(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        prompt = orchestrator._build_user_prompt(maurer_profil)
        assert "Maurer" in prompt or "A_01_MAURER" in prompt

    def test_user_prompt_contains_kernkompetenzen(self, maurer_profil):
        orchestrator = OrchestratorAgent()
        prompt = orchestrator._build_user_prompt(maurer_profil)
        assert maurer_profil.kernkompetenzen[0] in prompt
