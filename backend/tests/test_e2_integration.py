"""Integrations-Smoke-Test: ProfileParser → OrchestratorAgent.

Tests the full E2 pipeline without real LLM calls.
Uses unittest.mock to mock agent.run — same pattern as test_orchestrator.py.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.orchestrator import OrchestratorAgent
from agents.profile_parser import ProfileParsingAgent
from schemas.search_strategy import SearchStrategyModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


def _make_strategy_for_gewerk(gewerk_id: str) -> SearchStrategyModel:
    """Creates a valid SearchStrategyModel for a given gewerk_id."""
    return SearchStrategyModel(
        gewerk_id=gewerk_id,
        semantic_queries_en=[
            "Research in this craft domain addresses material properties and structural "
            "performance in construction and manufacturing applications."
        ],
        boolean_queries_de=[
            '("Handwerk" OR "Gewerk") AND Technik',
            '("Werkstoff" OR "Material") AND Verarbeitung',
        ],
        boolean_queries_en=[
            '("craft" OR "trade") AND techniques',
            '("material" OR "substrate") AND processing',
        ],
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
        assert len(result.semantic_queries_en) >= 1
        assert len(result.boolean_queries_de) >= 2
        assert len(result.boolean_queries_en) >= 2

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

    def test_agents_importable_from_package(self):
        """All agent classes are importable from the agents package."""
        from agents import OrchestratorAgent, ProfileParsingAgent
        assert OrchestratorAgent is not None
        assert ProfileParsingAgent is not None
