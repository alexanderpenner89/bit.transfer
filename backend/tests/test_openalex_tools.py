"""Tests for openalex_tools — all mocked, no real API calls."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.research_pipeline import WorkResult, TopicRef
from tools.openalex_tools import (
    openalex_semantic_search,
    openalex_precision_search,
    openalex_get_related_works,
    _parse_work,
)
from tools.openalex_costs import reset_tracker, get_tracker
from tools.openalex_tools import openalex_fetch_works


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RAW_WORK = {
    "id": "https://openalex.org/W2741809807",
    "display_name": "Thermal bridges in masonry construction",
    "abstract": "This paper investigates thermal bridge effects.",
    "publication_year": 2021,
    "cited_by_count": 42,
    "doi": "https://doi.org/10.1000/test",
    "topics": [
        {
            "id": "https://openalex.org/T10116",
            "display_name": "Thermal Bridge Mitigation",
            "score": 0.95,
        }
    ],
    "referenced_works": [
        "https://openalex.org/W111",
        "https://openalex.org/W222",
    ],
}

SAMPLE_WORK_RESULT = WorkResult(
    work_id="W2741809807",
    title="Thermal bridges in masonry construction",
    abstract="This paper investigates thermal bridge effects.",
    publication_year=2021,
    citation_count=42,
    doi="https://doi.org/10.1000/test",
    topics=[TopicRef(topic_id="T10116", display_name="Thermal Bridge Mitigation", score=0.95)],
    referenced_work_ids=["W111", "W222"],
)


# ---------------------------------------------------------------------------
# _parse_work
# ---------------------------------------------------------------------------

class TestParseWork:
    def test_parses_work_id(self):
        result = _parse_work(SAMPLE_RAW_WORK)
        assert result.work_id == "W2741809807"

    def test_parses_title(self):
        result = _parse_work(SAMPLE_RAW_WORK)
        assert result.title == "Thermal bridges in masonry construction"

    def test_parses_citation_count(self):
        result = _parse_work(SAMPLE_RAW_WORK)
        assert result.citation_count == 42

    def test_parses_topics_with_short_ids(self):
        result = _parse_work(SAMPLE_RAW_WORK)
        assert len(result.topics) == 1
        assert result.topics[0].topic_id == "T10116"
        assert result.topics[0].display_name == "Thermal Bridge Mitigation"

    def test_parses_referenced_work_ids(self):
        result = _parse_work(SAMPLE_RAW_WORK)
        assert result.referenced_work_ids == ["W111", "W222"]

    def test_handles_missing_abstract(self):
        raw = {**SAMPLE_RAW_WORK, "abstract": None}
        result = _parse_work(raw)
        assert result.abstract is None

    def test_handles_missing_doi(self):
        raw = {**SAMPLE_RAW_WORK, "doi": None}
        result = _parse_work(raw)
        assert result.doi is None

    def test_handles_empty_topics(self):
        raw = {**SAMPLE_RAW_WORK, "topics": []}
        result = _parse_work(raw)
        assert result.topics == []


# ---------------------------------------------------------------------------
# openalex_semantic_search
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    def test_returns_list_of_work_results(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value.search.return_value = mock_chain

            result = asyncio.run(openalex_semantic_search("thermal bridge masonry"))

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], WorkResult)

    def test_raises_value_error_on_empty_results(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.get.return_value = []
            MockWorks.return_value.search.return_value = mock_chain

            with pytest.raises(ValueError, match="returned 0 results"):
                asyncio.run(openalex_semantic_search("xyzzy nonexistent"))

    def test_error_message_mentions_query(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.get.return_value = []
            MockWorks.return_value.search.return_value = mock_chain

            with pytest.raises(ValueError, match="my special query"):
                asyncio.run(openalex_semantic_search("my special query"))

    def test_respects_max_results_param(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value.search.return_value = mock_chain

            asyncio.run(openalex_semantic_search("masonry", max_results=10))

        mock_chain.get.assert_called_once_with(per_page=10)


# ---------------------------------------------------------------------------
# openalex_precision_search
# ---------------------------------------------------------------------------

class TestPrecisionSearch:
    def test_returns_list_of_work_results(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.search_filter.return_value = mock_chain
            mock_chain.sort.return_value = mock_chain
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain

            result = asyncio.run(
                openalex_precision_search(
                    topic_id="T10116",
                    topic_name="Thermal Bridge Mitigation",
                    boolean_queries=['("masonry" OR "brickwork") AND "thermal"'],
                )
            )

        assert isinstance(result, list)
        assert all(isinstance(w, WorkResult) for w in result)

    def test_deduplicates_across_queries(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.search_filter.return_value = mock_chain
            mock_chain.sort.return_value = mock_chain
            # Both queries return the same work
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain

            result = asyncio.run(
                openalex_precision_search(
                    topic_id="T10116",
                    topic_name="Test",
                    boolean_queries=["query1", "query2"],
                )
            )

        # Should be deduplicated to 1
        assert len(result) == 1

    def test_sorted_by_citation_count_desc(self):
        low_cited = {**SAMPLE_RAW_WORK, "id": "https://openalex.org/W001", "cited_by_count": 5}
        high_cited = {**SAMPLE_RAW_WORK, "id": "https://openalex.org/W002", "cited_by_count": 100}

        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.search_filter.return_value = mock_chain
            mock_chain.sort.return_value = mock_chain
            mock_chain.get.return_value = [low_cited, high_cited]
            MockWorks.return_value = mock_chain

            result = asyncio.run(
                openalex_precision_search("T10116", "Test", ["q1"])
            )

        assert result[0].citation_count >= result[1].citation_count


# ---------------------------------------------------------------------------
# openalex_get_related_works
# ---------------------------------------------------------------------------

class TestGetRelatedWorks:
    def test_cited_by_mode_returns_works(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain

            result = asyncio.run(
                openalex_get_related_works(["W123"], mode="cited_by")
            )

        assert isinstance(result, list)
        assert all(isinstance(w, WorkResult) for w in result)

    def test_deduplicates_across_work_ids(self):
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            # Both source work IDs return the same citing paper
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain

            result = asyncio.run(
                openalex_get_related_works(["W001", "W002"], mode="cited_by")
            )

        assert len(result) == 1

    def test_empty_work_ids_returns_empty(self):
        result = asyncio.run(openalex_get_related_works([], mode="cited_by"))
        assert result == []


# ---------------------------------------------------------------------------
# TestCostTracking
# ---------------------------------------------------------------------------

class TestCostTracking:
    """Verify each tool adds to the OpenAlexCostTracker when one is active."""

    def test_semantic_search_tracks_cost(self):
        tracker = reset_tracker()
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value.search.return_value = mock_chain
            asyncio.run(openalex_semantic_search("thermal bridge"))
        assert tracker.total_calls == 1
        assert tracker.total_cost_usd > 0
        assert "semantic_search" in tracker.breakdown

    def test_precision_search_tracks_cost_per_query(self):
        tracker = reset_tracker()
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.search_filter.return_value = mock_chain
            mock_chain.sort.return_value = mock_chain
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain
            asyncio.run(openalex_precision_search("T10116", "Test", ["q1", "q2"]))
        assert tracker.total_calls == 2  # 2 boolean queries = 2 calls
        assert "search" in tracker.breakdown

    def test_fetch_works_tracks_cost(self):
        tracker = reset_tracker()
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain
            asyncio.run(openalex_fetch_works(["W123"]))
        assert tracker.total_calls == 1
        assert tracker.total_cost_usd > 0
        assert "list_filter" in tracker.breakdown

    def test_get_related_works_cited_by_tracks_cost_per_work(self):
        tracker = reset_tracker()
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.filter.return_value = mock_chain
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value = mock_chain
            asyncio.run(openalex_get_related_works(["W001", "W002"], mode="cited_by"))
        assert tracker.total_calls == 2  # 2 work_ids = 2 filter calls
        assert "list_filter" in tracker.breakdown

    def test_no_tracker_does_not_crash(self):
        """Tools must not crash when no tracker is active."""
        from tools.openalex_costs import _tracker
        _tracker.set(None)
        with patch("tools.openalex_tools.Works") as MockWorks:
            mock_chain = MagicMock()
            mock_chain.get.return_value = [SAMPLE_RAW_WORK]
            MockWorks.return_value.search.return_value = mock_chain
            asyncio.run(openalex_semantic_search("thermal bridge"))
