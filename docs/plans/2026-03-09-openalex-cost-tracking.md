# OpenAlex Cost Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Track monetary costs of OpenAlex API calls per pipeline run and report them to Langfuse — per-call metadata on each tool span and a cost summary on the aggregator root span.

**Architecture:** A new `tools/openalex_costs.py` holds cost constants and an `OpenAlexCostTracker` dataclass stored in a `ContextVar`. Each tool function in `openalex_tools.py` calculates its cost, adds it to the tracker, and passes it as `metadata` to the existing `tool.update()` call. `aggregator.run()` initialises a fresh tracker at the start and appends `summary_dict()` to its root Langfuse span at the end.

**Tech Stack:** Python 3.12, `contextvars.ContextVar`, `dataclasses`, `pytest`, existing Langfuse integration via `get_langfuse().start_as_current_observation`

---

### Task 1: Create `tools/openalex_costs.py`

**Files:**
- Create: `backend/tools/openalex_costs.py`
- Test: `backend/tests/test_openalex_costs.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_openalex_costs.py`:

```python
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
        # Each test gets its own async context so reset first
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
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_openalex_costs.py -v
```

Expected: `ImportError: cannot import name 'OpenAlexCostTracker' from 'tools.openalex_costs'`

**Step 3: Implement `tools/openalex_costs.py`**

```python
"""OpenAlex cost tracking utilities.

Pricing reference (per 1,000 calls):
  Semantic search:  $1.00  → $0.001 per call
  Search (boolean): $1.00  → $0.001 per call
  List + Filter:    $0.10  → $0.0001 per call
  Singleton:        Free

Usage:
    tracker = reset_tracker()        # start of a pipeline run
    # ... tool calls auto-accumulate via get_tracker() ...
    summary = tracker.summary_dict() # at end of run
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

COST_SEMANTIC_SEARCH: float = 0.001   # $1 per 1,000 calls
COST_SEARCH: float = 0.001            # $1 per 1,000 calls
COST_LIST_FILTER: float = 0.0001      # $0.10 per 1,000 calls


@dataclass
class OpenAlexCostTracker:
    total_cost_usd: float = 0.0
    total_calls: int = 0
    breakdown: dict[str, float] = field(default_factory=dict)

    def add(self, tool_name: str, calls: int, cost_usd: float) -> None:
        self.total_calls += calls
        self.total_cost_usd += cost_usd
        self.breakdown[tool_name] = self.breakdown.get(tool_name, 0.0) + cost_usd

    def summary_dict(self) -> dict:
        return {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_calls": self.total_calls,
            "breakdown": {k: round(v, 6) for k, v in self.breakdown.items()},
        }


_tracker: ContextVar[OpenAlexCostTracker | None] = ContextVar(
    "openalex_cost_tracker", default=None
)


def get_tracker() -> OpenAlexCostTracker | None:
    return _tracker.get()


def reset_tracker() -> OpenAlexCostTracker:
    tracker = OpenAlexCostTracker()
    _tracker.set(tracker)
    return tracker
```

**Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_openalex_costs.py -v
```

Expected: all tests PASS

**Step 5: Commit**

```bash
git add backend/tools/openalex_costs.py backend/tests/test_openalex_costs.py
git commit -m "feat: add OpenAlexCostTracker with ContextVar-based accumulation"
```

---

### Task 2: Wire cost tracking into `openalex_tools.py`

**Files:**
- Modify: `backend/tools/openalex_tools.py`
- Modify: `backend/tests/test_openalex_tools.py` (add cost tracking tests)

**Step 1: Write failing tests**

Add this class to `backend/tests/test_openalex_tools.py`:

```python
# At top with other imports:
from tools.openalex_costs import reset_tracker, get_tracker
from tools.openalex_tools import openalex_fetch_works


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
            # Should not raise
            asyncio.run(openalex_semantic_search("thermal bridge"))
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_openalex_tools.py::TestCostTracking -v
```

Expected: FAIL — `AssertionError: assert 0 == 1` (no tracking wired yet)

**Step 3: Update `tools/openalex_tools.py`**

Add imports at the top (after existing imports):

```python
from tools.openalex_costs import (
    COST_LIST_FILTER,
    COST_SEARCH,
    COST_SEMANTIC_SEARCH,
    get_tracker,
)
```

**`openalex_semantic_search`** — replace the two `tool.update()` calls:

Find the error path update:
```python
        if not raw:
            tool.update(
                level="ERROR",
                output={"error": f"No results for query: {query[:50]}..."},
            )
```
Replace with:
```python
        if not raw:
            tool.update(
                level="ERROR",
                output={"error": f"No results for query: {query[:50]}..."},
                metadata={"openalex_cost_usd": COST_SEMANTIC_SEARCH, "openalex_calls": 1},
            )
            if t := get_tracker():
                t.add("semantic_search", 1, COST_SEMANTIC_SEARCH)
```

Find the success path update:
```python
        results = [_parse_work(w) for w in raw]
        tool.update(output={
            "result_count": len(results),
            "top_results": [{"work_id": r.work_id, "title": r.title} for r in results[:5]],
        })
        return results
```
Replace with:
```python
        results = [_parse_work(w) for w in raw]
        tool.update(output={
            "result_count": len(results),
            "top_results": [{"work_id": r.work_id, "title": r.title} for r in results[:5]],
        }, metadata={"openalex_cost_usd": COST_SEMANTIC_SEARCH, "openalex_calls": 1})
        if t := get_tracker():
            t.add("semantic_search", 1, COST_SEMANTIC_SEARCH)
        return results
```

**`openalex_fetch_works`** — replace the `tool.update()` call:

```python
        results = [_parse_work(w) for w in raw]
        tool.update(output={
            "result_count": len(results),
            "titles": [r.title for r in results],
        })
        return results
```
Replace with:
```python
        results = [_parse_work(w) for w in raw]
        tool.update(output={
            "result_count": len(results),
            "titles": [r.title for r in results],
        }, metadata={"openalex_cost_usd": COST_LIST_FILTER, "openalex_calls": 1})
        if t := get_tracker():
            t.add("list_filter", 1, COST_LIST_FILTER)
        return results
```

**`openalex_precision_search`** — add cost calc before the final `tool.update()` call.

Find the final `tool.update()` block (around line 256):
```python
        tool.update(
            output={
                "result_count": len(merged),
                "queries_failed": len(failed_queries),
                "top_results": [
                    {"work_id": w.work_id, "title": w.title, "citations": w.citation_count}
                    for w in merged[:5]
                ],
            },
            level=level,
            **({"status_message": status_message} if status_message else {}),
        )
        return merged
```
Replace with:
```python
        calls = len(boolean_queries)
        cost = calls * COST_SEARCH
        tool.update(
            output={
                "result_count": len(merged),
                "queries_failed": len(failed_queries),
                "top_results": [
                    {"work_id": w.work_id, "title": w.title, "citations": w.citation_count}
                    for w in merged[:5]
                ],
            },
            level=level,
            metadata={"openalex_cost_usd": cost, "openalex_calls": calls},
            **({"status_message": status_message} if status_message else {}),
        )
        if t := get_tracker():
            t.add("search", calls, cost)
        return merged
```

**`openalex_get_related_works`** — add cost calc before each `tool.update()` call.

Find the empty-result branch:
```python
        if not results:
            tool.update(
                output={"result_count": 0},
                level="WARNING",
                status_message="No related works found",
            )
        else:
            tool.update(output={
                "result_count": len(results),
                "titles": [r.title for r in results[:5]],
            })
        return results
```
Replace with:
```python
        if mode == "cited_by":
            calls = len(work_ids)
        else:
            calls = len(work_ids) + (1 if ref_ids else 0)
        cost = calls * COST_LIST_FILTER
        if not results:
            tool.update(
                output={"result_count": 0},
                level="WARNING",
                status_message="No related works found",
                metadata={"openalex_cost_usd": cost, "openalex_calls": calls},
            )
        else:
            tool.update(output={
                "result_count": len(results),
                "titles": [r.title for r in results[:5]],
            }, metadata={"openalex_cost_usd": cost, "openalex_calls": calls})
        if t := get_tracker():
            t.add("list_filter", calls, cost)
        return results
```

Note: `ref_ids` is defined in the `references` branch of the function. For `cited_by` mode it doesn't exist. The cost calculation must be placed after the `if mode == "cited_by": ... else: ...` block where both `results` and `ref_ids` (in references branch) are available. Place it just before the `if not results:` check. For `cited_by` mode, `ref_ids` is not in scope — use `mode == "cited_by"` to branch the calculation as shown above.

**Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_openalex_tools.py -v
```

Expected: all tests PASS (including existing ones)

**Step 5: Commit**

```bash
git add backend/tools/openalex_tools.py backend/tests/test_openalex_tools.py
git commit -m "feat: add per-call cost tracking to OpenAlex tools"
```

---

### Task 3: Init tracker and emit summary in `aggregator.run()`

**Files:**
- Modify: `backend/agents/aggregator.py`

No new tests needed — the unit tests in Task 2 already verify per-call tracking. This wires the summary to the existing root Langfuse span.

**Step 1: Add import**

In `backend/agents/aggregator.py`, add to the imports:

```python
from tools.openalex_costs import reset_tracker
```

**Step 2: Init tracker at the start of `aggregator.run()`**

In `aggregator.run()`, insert after the `with get_langfuse().start_as_current_observation(...) as span:` line:

```python
        cost_tracker = reset_tracker()
```

**Step 3: Add summary to the final `span.update()` call**

Find the existing `span.update(...)` call at the end of `aggregator.run()` (around line 187):

```python
            span.update(
                output={
                    "total_works": len(precision_works) + len(expanded_works),
                    ...
                },
                level=level,
                **({"status_message": status_message} if status_message else {}),
            )
```

Replace with:

```python
            span.update(
                output={
                    "total_works": len(precision_works) + len(expanded_works),
                    "relevant_topics": len(relevant_topics),
                    "relevant_topic_names": [ev.display_name for ev in relevant_topics],
                    "eval_errors": eval_errors,
                    "precision_errors": precision_errors,
                    "top_precision_works": [
                        {"work_id": w.work_id, "title": w.title, "citations": w.citation_count}
                        for w in precision_works[:10]
                    ],
                },
                metadata={"openalex_cost_summary": cost_tracker.summary_dict()},
                level=level,
                **({"status_message": status_message} if status_message else {}),
            )
```

**Step 4: Run existing aggregator tests**

```bash
cd backend && python -m pytest tests/test_aggregator.py -v
```

Expected: all existing tests PASS

**Step 5: Commit**

```bash
git add backend/agents/aggregator.py
git commit -m "feat: emit OpenAlex cost summary on aggregator.run Langfuse span"
```

---

### Task 4: Run full test suite

**Step 1: Run all tests**

```bash
cd backend && python -m pytest -v
```

Expected: all tests PASS, no regressions

**Step 2: Commit if any fixes were needed, otherwise done**

```bash
git log --oneline -5
```

Verify the three feature commits are present.
