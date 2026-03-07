"""Integrations-Smoke-Test: ProfileParser → KeywordExtractor → OrchestratorAgent.

Tests the full E2 pipeline without real LLM calls.
Uses unittest.mock to mock agent.run — same pattern as test_orchestrator.py.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.keyword_extractor import KeywordExtractor
from agents.orchestrator import OrchestratorAgent
from agents.profile_parser import ProfileParsingAgent
from schemas.search_strategy import ForschungsFrage, SearchStrategyModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


def _make_strategy_for_gewerk(gewerk_id: str) -> SearchStrategyModel:
    """Creates a valid SearchStrategyModel for a given gewerk_id."""
    return SearchStrategyModel(
        gewerk_id=gewerk_id,
        forschungsfragen=[
            ForschungsFrage(frage=f"Forschungsfrage {i}", bezug_profilfelder=["kernkompetenzen"], prioritaet=1)
            for i in range(3)
        ],
        keyword_queries_de=["Query DE 1", "Query DE 2"],
        keyword_queries_en=["Query EN 1", "Query EN 2"],
        semantic_queries_en=["semantic description for this trade"],
        hyde_abstracts=[],
        concept_filter_ids=None,
        max_results_per_query=50,
    )


def _make_mock_result(strategy: SearchStrategyModel) -> MagicMock:
    mock = MagicMock()
    mock.output = strategy
    return mock


@pytest.fixture
def parser() -> ProfileParsingAgent:
    return ProfileParsingAgent()


@pytest.fixture
def orchestrator() -> OrchestratorAgent:
    return OrchestratorAgent()


class TestE2Pipeline:
    def test_full_pipeline_maurer(self, parser, orchestrator):
        """E1 → E2: Profile Parser → Orchestrator → SearchStrategyModel."""
        profil = parser.parse_file(PROFILES_DIR / "maurer.json")
        strategy = _make_strategy_for_gewerk(profil.gewerk_id)
        mock_result = _make_mock_result(strategy)

        with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
            result = asyncio.run(orchestrator.generate(profil))

        assert isinstance(result, SearchStrategyModel)
        assert result.gewerk_id == "A_01_MAURER"
        assert len(result.forschungsfragen) >= 3
        # KeywordExtractor queries merged in → should have > 2 DE queries
        assert len(result.keyword_queries_de) >= 5

    def test_full_pipeline_all_three_profiles(self, parser, orchestrator):
        """All three pilot profiles run through the full E2 pipeline."""
        profiles = [
            ("maurer.json", "A_01_MAURER"),
            ("tischler.json", "A_13_TISCHLER"),
            ("elektrotechniker.json", "A_09_ELEKTROTECHNIKER"),
        ]

        for filename, expected_id in profiles:
            profil = parser.parse_file(PROFILES_DIR / filename)
            strategy = _make_strategy_for_gewerk(profil.gewerk_id)
            mock_result = _make_mock_result(strategy)

            with patch.object(orchestrator.agent, "run", new=AsyncMock(return_value=mock_result)):
                result = asyncio.run(orchestrator.generate(profil))

            assert isinstance(result, SearchStrategyModel)
            assert result.gewerk_id == expected_id

    def test_keyword_extractor_standalone_pipeline(self):
        """E2-S1: ProfileParser → KeywordExtractor works without any LLM."""
        parser = ProfileParsingAgent()
        extractor = KeywordExtractor()

        profil = parser.parse_file(PROFILES_DIR / "maurer.json")
        queries = extractor.extract_keyword_queries(profil)

        assert len(queries) >= 5
        assert all(isinstance(q, str) for q in queries)

    def test_agents_importable_from_package(self):
        """All agent classes are importable from the agents package."""
        from agents import KeywordExtractor, OrchestratorAgent, ProfileParsingAgent
        assert KeywordExtractor is not None
        assert OrchestratorAgent is not None
        assert ProfileParsingAgent is not None
