"""Tests for ResearchAggregator — unit tests mocked, integration test marked."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agents.aggregator import ResearchAggregator
from schemas.gewerksprofil import GewerksProfilModel
from schemas.research_pipeline import (
    ExplorationResult,
    ResearchResult,
    TopicCandidate,
    TopicEvaluation,
    TopicRef,
    WorkResult,
)
from schemas.search_strategy import SearchStrategyModel


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def strategy() -> SearchStrategyModel:
    return SearchStrategyModel(
        gewerk_id="A_01_MAURER",
        semantic_queries_en=["Load-bearing masonry and thermal performance."],
        boolean_queries_de=[
            '("Mauerwerk" OR "Ziegel") AND "Tragfähigkeit"',
            '("Mörtel" OR "Dünnbettmörtel") AND Verarbeitung',
        ],
        boolean_queries_en=[
            '("masonry" OR "brickwork") AND "structural performance"',
            '("mortar" OR "adhesive mortar") AND application',
        ],
    )


@pytest.fixture
def profil() -> GewerksProfilModel:
    return GewerksProfilModel(
        gewerk_id="A_01_MAURER",
        gewerk_name="Maurer und Betonbauer",
        hwo_anlage="A",
        kernkompetenzen=["Mauerwerksbau", "Betonbau"],
        taetigkeitsfelder={"Herstellung": ["Mauern"]},
        techniken_manuell=["Stemmen"],
        techniken_maschinell=["Bohren"],
        techniken_oberflaeche=["Verputzen"],
        werkstoffe=["Ziegel", "Beton"],
        software_tools=["AutoCAD"],
        arbeitsbedingungen=["Freiluftarbeit"],
    )


WORK_A = WorkResult(
    work_id="W001",
    title="Masonry thermal bridges",
    abstract=None,
    publication_year=2020,
    citation_count=42,
    doi=None,
    topics=[TopicRef(topic_id="T100", display_name="Masonry Construction", score=0.9)],
    referenced_work_ids=[],
)

WORK_B = WorkResult(
    work_id="W002",
    title="Mortar joint optimization",
    abstract=None,
    publication_year=2021,
    citation_count=10,
    doi=None,
    topics=[TopicRef(topic_id="T100", display_name="Masonry Construction", score=0.8)],
    referenced_work_ids=[],
)

EXPLORATION = ExplorationResult(
    gewerk_id="A_01_MAURER",
    works=[WORK_A, WORK_B],
    topic_candidates=[
        TopicCandidate(topic_id="T100", display_name="Masonry Construction", frequency=2),
    ],
)

RELEVANT_TOPIC = TopicEvaluation(
    topic_id="T100",
    display_name="Masonry Construction",
    is_relevant=True,
    reasoning="Directly relevant to masonry trade.",
    confidence=0.95,
)

IRRELEVANT_TOPIC = TopicEvaluation(
    topic_id="T999",
    display_name="Quantum Physics",
    is_relevant=False,
    reasoning="Not relevant.",
    confidence=0.99,
)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestResearchAggregatorRun:
    def test_returns_research_result(self, strategy, profil):
        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=EXPLORATION)),
            patch.object(agg._evaluator, "evaluate", new=AsyncMock(return_value=RELEVANT_TOPIC)),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[WORK_A])),
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert isinstance(result, ResearchResult)

    def test_sets_correct_gewerk_id(self, strategy, profil):
        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=EXPLORATION)),
            patch.object(agg._evaluator, "evaluate", new=AsyncMock(return_value=RELEVANT_TOPIC)),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[WORK_A])),
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert result.gewerk_id == "A_01_MAURER"

    def test_filters_irrelevant_topics(self, strategy, profil):
        exploration_with_two = ExplorationResult(
            gewerk_id="A_01_MAURER",
            works=[WORK_A],
            topic_candidates=[
                TopicCandidate(topic_id="T100", display_name="Masonry Construction", frequency=2),
                TopicCandidate(topic_id="T999", display_name="Quantum Physics", frequency=1),
            ],
        )
        call_count = 0

        async def mock_evaluate(candidate, profil):
            nonlocal call_count
            call_count += 1
            return RELEVANT_TOPIC if candidate.topic_id == "T100" else IRRELEVANT_TOPIC

        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=exploration_with_two)),
            patch.object(agg._evaluator, "evaluate", side_effect=mock_evaluate),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[WORK_A])),
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert len(result.relevant_topics) == 1
        assert result.relevant_topics[0].topic_id == "T100"

    def test_precision_works_deduplicated(self, strategy, profil):
        # Two relevant topics both return the same work
        two_topics_exploration = ExplorationResult(
            gewerk_id="A_01_MAURER",
            works=[WORK_A],
            topic_candidates=[
                TopicCandidate(topic_id="T100", display_name="Masonry", frequency=2),
                TopicCandidate(topic_id="T101", display_name="Concrete", frequency=1),
            ],
        )

        async def mock_evaluate(candidate, profil):
            return TopicEvaluation(
                topic_id=candidate.topic_id,
                display_name=candidate.display_name,
                is_relevant=True,
                reasoning="Relevant.",
                confidence=0.9,
            )

        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=two_topics_exploration)),
            patch.object(agg._evaluator, "evaluate", side_effect=mock_evaluate),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[WORK_A])),
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert len(result.precision_works) == 1

    def test_precision_works_sorted_by_citation_count(self, strategy, profil):
        low = WorkResult(
            work_id="W_LOW", title="Low cited", abstract=None,
            publication_year=2020, citation_count=1, doi=None, topics=[], referenced_work_ids=[]
        )
        high = WorkResult(
            work_id="W_HIGH", title="High cited", abstract=None,
            publication_year=2020, citation_count=100, doi=None, topics=[], referenced_work_ids=[]
        )
        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=EXPLORATION)),
            patch.object(agg._evaluator, "evaluate", new=AsyncMock(return_value=RELEVANT_TOPIC)),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[low, high])),
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert result.precision_works[0].citation_count >= result.precision_works[1].citation_count

    def test_no_relevant_topics_skips_precision(self, strategy, profil):
        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=EXPLORATION)),
            patch.object(agg._evaluator, "evaluate", new=AsyncMock(return_value=IRRELEVANT_TOPIC)),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[])) as mock_precision,
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        mock_precision.assert_not_called()
        assert result.precision_works == []

    def test_expansion_error_handled_gracefully(self, strategy, profil):
        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=EXPLORATION)),
            patch.object(agg._evaluator, "evaluate", new=AsyncMock(return_value=RELEVANT_TOPIC)),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[WORK_A])),
            patch(
                "agents.aggregator.openalex_get_related_works",
                new=AsyncMock(side_effect=Exception("Network error")),
            ),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert result.expanded_works == []

    def test_exploration_works_included_in_result(self, strategy, profil):
        agg = ResearchAggregator()
        with (
            patch.object(agg._explorer, "run", new=AsyncMock(return_value=EXPLORATION)),
            patch.object(agg._evaluator, "evaluate", new=AsyncMock(return_value=RELEVANT_TOPIC)),
            patch.object(agg._precision, "run", new=AsyncMock(return_value=[])),
            patch("agents.aggregator.openalex_get_related_works", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(agg.run(strategy, profil))

        assert len(result.exploration_works) == 2


# ---------------------------------------------------------------------------
# Integration test (requires internet + real OpenAlex API)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestResearchAggregatorIntegration:
    def test_full_pipeline_smoke(self):
        """Smoke test: runs the full pipeline against the live OpenAlex API."""
        from agents.aggregator import ResearchAggregator

        strategy = SearchStrategyModel(
            gewerk_id="A_01_MAURER",
            semantic_queries_en=[
                "Load-bearing masonry construction structural performance brick mortar."
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
        profil = GewerksProfilModel(
            gewerk_id="A_01_MAURER",
            gewerk_name="Maurer und Betonbauer",
            hwo_anlage="A",
            kernkompetenzen=["Mauerwerksbau", "Betonbau"],
            taetigkeitsfelder={"Herstellung": ["Mauern"]},
            techniken_manuell=["Stemmen"],
            techniken_maschinell=["Bohren"],
            techniken_oberflaeche=["Verputzen"],
            werkstoffe=["Ziegel", "Beton"],
            software_tools=["AutoCAD"],
            arbeitsbedingungen=["Freiluftarbeit"],
        )

        agg = ResearchAggregator(on_progress=lambda msg: print(msg, flush=True))
        result = asyncio.run(agg.run(strategy, profil))

        assert isinstance(result, ResearchResult)
        assert result.gewerk_id == "A_01_MAURER"
        assert len(result.exploration_works) > 0
        print(f"\nExploration works: {len(result.exploration_works)}")
        print(f"Relevant topics: {len(result.relevant_topics)}")
        print(f"Precision works: {len(result.precision_works)}")
        print(f"Expanded works: {len(result.expanded_works)}")
