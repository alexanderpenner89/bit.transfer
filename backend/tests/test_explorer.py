"""Tests for ExplorerAgent — all mocked, no real API calls."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agents.explorer import ExplorerAgent
from schemas.research_pipeline import ExplorationResult, TopicCandidate, TopicRef, WorkResult
from schemas.search_strategy import SearchStrategyModel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STRATEGY = SearchStrategyModel(
    gewerk_id="A_01_MAURER",
    semantic_queries_en=[
        "Load-bearing masonry construction and thermal performance.",
        "Mortar joint optimization in residential building envelopes.",
        "Brick masonry structural integrity and durability assessment.",
    ],
    boolean_queries_de=[
        '("Mauerwerk" OR "Ziegel") AND "Tragfähigkeit"',
        '("Mörtel" OR "Dünnbettmörtel") AND Verarbeitung',
    ],
    boolean_queries_en=[
        '("masonry" OR "brickwork") AND "structural performance"',
        '("mortar" OR "adhesive mortar") AND application',
    ],
)

WORK_A = WorkResult(
    work_id="W001",
    title="Masonry thermal bridges",
    abstract=None,
    publication_year=2020,
    citation_count=10,
    doi=None,
    topics=[
        TopicRef(topic_id="T100", display_name="Masonry Construction", score=0.9),
        TopicRef(topic_id="T200", display_name="Thermal Performance", score=0.7),
    ],
    referenced_work_ids=[],
)

WORK_B = WorkResult(
    work_id="W002",
    title="Mortar joint optimization",
    abstract=None,
    publication_year=2021,
    citation_count=5,
    doi=None,
    topics=[
        TopicRef(topic_id="T100", display_name="Masonry Construction", score=0.8),
    ],
    referenced_work_ids=[],
)

WORK_C = WorkResult(
    work_id="W003",
    title="Building envelope study",
    abstract=None,
    publication_year=2019,
    citation_count=20,
    doi=None,
    topics=[
        TopicRef(topic_id="T300", display_name="Building Envelope", score=0.85),
    ],
    referenced_work_ids=[],
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExplorerAgentRun:
    def test_returns_exploration_result(self):
        agent = ExplorerAgent()
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(return_value=[WORK_A]),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        assert isinstance(result, ExplorationResult)

    def test_sets_correct_gewerk_id(self):
        agent = ExplorerAgent()
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(return_value=[WORK_A]),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        assert result.gewerk_id == "A_01_MAURER"

    def test_deduplicates_works_across_queries(self):
        agent = ExplorerAgent()
        # Both queries return the same work
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(return_value=[WORK_A]),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        assert len(result.works) == 1

    def test_merges_distinct_works_across_queries(self):
        agent = ExplorerAgent()
        side_effects = [[WORK_A], [WORK_B]]
        call_count = 0

        async def mock_search(q, **kwargs):
            nonlocal call_count
            val = side_effects[call_count % len(side_effects)]
            call_count += 1
            return val

        with patch("agents.explorer.openalex_semantic_search", side_effect=mock_search):
            result = asyncio.run(agent.run(STRATEGY))

        assert len(result.works) == 2

    def test_builds_topic_candidates(self):
        agent = ExplorerAgent()
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(return_value=[WORK_A, WORK_B, WORK_C]),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        assert len(result.topic_candidates) > 0
        assert all(isinstance(c, TopicCandidate) for c in result.topic_candidates)

    def test_topic_frequency_counts_correctly(self):
        agent = ExplorerAgent()
        # WORK_A and WORK_B both have T100, so frequency should be 2
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(return_value=[WORK_A, WORK_B]),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        t100 = next((c for c in result.topic_candidates if c.topic_id == "T100"), None)
        assert t100 is not None
        assert t100.frequency == 2

    def test_topic_candidates_sorted_by_frequency_desc(self):
        agent = ExplorerAgent()
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(return_value=[WORK_A, WORK_B, WORK_C]),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        freqs = [c.frequency for c in result.topic_candidates]
        assert freqs == sorted(freqs, reverse=True)

    def test_tolerates_query_errors(self):
        agent = ExplorerAgent()
        call_count = 0

        async def mock_search(q, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Query returned 0 results")
            return [WORK_A]

        with patch("agents.explorer.openalex_semantic_search", side_effect=mock_search):
            result = asyncio.run(agent.run(STRATEGY))

        # Only WORK_A from the second successful query
        assert len(result.works) == 1

    def test_all_queries_fail_returns_empty(self):
        agent = ExplorerAgent()
        with patch(
            "agents.explorer.openalex_semantic_search",
            new=AsyncMock(side_effect=ValueError("No results")),
        ):
            result = asyncio.run(agent.run(STRATEGY))

        assert result.works == []
        assert result.topic_candidates == []
