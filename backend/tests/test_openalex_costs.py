"""Tests for OpenAlexCostTracker."""
import pytest
from tools.openalex_costs import (
    COST_SEMANTIC_SEARCH,
    COST_SEARCH,
    COST_LIST_FILTER,
    OpenAlexCostTracker,
    get_tracker,
    reset_tracker,
)


class TestCostConstants:
    def test_semantic_search_cost(self):
        assert COST_SEMANTIC_SEARCH == pytest.approx(0.001)

    def test_search_cost(self):
        assert COST_SEARCH == pytest.approx(0.001)

    def test_list_filter_cost(self):
        assert COST_LIST_FILTER == pytest.approx(0.0001)


class TestOpenAlexCostTracker:
    def test_starts_at_zero(self):
        tracker = OpenAlexCostTracker()
        assert tracker.total_cost_usd == 0.0
        assert tracker.total_calls == 0
        assert tracker.breakdown == {}

    def test_add_accumulates_cost(self):
        tracker = OpenAlexCostTracker()
        tracker.add("semantic_search", 1, 0.001)
        assert tracker.total_cost_usd == pytest.approx(0.001)
        assert tracker.total_calls == 1

    def test_add_multiple_calls_same_tool(self):
        tracker = OpenAlexCostTracker()
        tracker.add("semantic_search", 1, 0.001)
        tracker.add("semantic_search", 1, 0.001)
        assert tracker.total_cost_usd == pytest.approx(0.002)
        assert tracker.total_calls == 2
        assert tracker.breakdown["semantic_search"] == pytest.approx(0.002)

    def test_add_different_tools(self):
        tracker = OpenAlexCostTracker()
        tracker.add("semantic_search", 1, 0.001)
        tracker.add("list_filter", 3, 0.0003)
        assert tracker.total_cost_usd == pytest.approx(0.0013)
        assert tracker.total_calls == 4
        assert "semantic_search" in tracker.breakdown
        assert "list_filter" in tracker.breakdown

    def test_summary_dict_structure(self):
        tracker = OpenAlexCostTracker()
        tracker.add("semantic_search", 5, 0.005)
        tracker.add("list_filter", 10, 0.001)
        summary = tracker.summary_dict()
        assert summary["total_cost_usd"] == pytest.approx(0.006)
        assert summary["total_calls"] == 15
        assert "breakdown" in summary
        assert summary["breakdown"]["semantic_search"] == pytest.approx(0.005)


class TestContextVar:
    def test_get_tracker_returns_none_by_default(self):
        from tools.openalex_costs import _tracker
        _tracker.set(None)
        assert get_tracker() is None

    def test_reset_tracker_returns_fresh_tracker(self):
        tracker = reset_tracker()
        assert isinstance(tracker, OpenAlexCostTracker)
        assert tracker.total_cost_usd == 0.0

    def test_get_tracker_returns_reset_tracker(self):
        tracker = reset_tracker()
        assert get_tracker() is tracker

    def test_reset_clears_previous_state(self):
        t1 = reset_tracker()
        t1.add("semantic_search", 1, 0.001)
        t2 = reset_tracker()
        assert t2.total_cost_usd == 0.0
        assert get_tracker() is t2
