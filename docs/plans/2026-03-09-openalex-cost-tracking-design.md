# OpenAlex Cost Tracking Design

**Date:** 2026-03-09

## Overview

Track monetary costs of OpenAlex API calls per pipeline run and report them to Langfuse — both as per-call metadata and as a per-run total summary.

## OpenAlex Pricing Reference

| Endpoint Type        | Cost per 1,000 calls |
|----------------------|----------------------|
| Get singleton        | Free                 |
| List + Filter        | $0.10                |
| Search (boolean)     | $1.00                |
| Semantic search      | $1.00                |

Free daily budget: $1.00 per API key.

## Tool-to-Cost Mapping

| Tool Function                                   | Endpoint Type  | HTTP Calls              | Cost per invocation              |
|-------------------------------------------------|----------------|-------------------------|----------------------------------|
| `openalex_semantic_search`                      | Semantic search| 1                       | $0.001                           |
| `openalex_precision_search`                     | Search         | `len(queries)`          | `len(queries) × $0.001`          |
| `openalex_fetch_works`                          | List + Filter  | 1                       | $0.0001                          |
| `openalex_get_related_works` cited_by           | List + Filter  | `len(work_ids)`         | `len(work_ids) × $0.0001`        |
| `openalex_get_related_works` references         | List + Filter  | `len(work_ids) + 1`     | `(len(work_ids) + 1) × $0.0001`  |

## Architecture

### New file: `tools/openalex_costs.py`

- Cost constants (`COST_SEMANTIC_SEARCH`, `COST_SEARCH`, `COST_LIST_FILTER`)
- `OpenAlexCostTracker` class:
  - Holds accumulated `total_cost_usd` and `total_calls`
  - Per-tool-type breakdown dict: `{"semantic_search": 0.003, "search": 0.005, ...}`
  - `add(tool_name, calls, cost_usd)` method
  - `summary_dict()` → dict for Langfuse metadata output
- `ContextVar[OpenAlexCostTracker | None]` for async-safe context propagation
- `get_tracker() -> OpenAlexCostTracker | None`
- `reset_tracker() -> OpenAlexCostTracker` (creates fresh instance, sets ContextVar)

### Changes: `tools/openalex_tools.py`

Each tool function after its HTTP call(s):
1. Calculates its cost: `cost = calls × COST_PER_CALL`
2. Updates its Langfuse span: `tool.update(metadata={"openalex_cost_usd": cost, "openalex_calls": calls})`
3. Accumulates to tracker: `if t := get_tracker(): t.add(tool_name, calls, cost)`

### Pipeline entry points (CLI / `__main__.py`)

At the start of each full pipeline run:
```python
tracker = reset_tracker()
```

At the end (in the top-level Langfuse span update):
```python
if tracker := get_tracker():
    span.update(metadata={"openalex_cost_summary": tracker.summary_dict()})
```

This emits a `openalex_cost_summary` object on the root span, e.g.:
```json
{
  "total_cost_usd": 0.0085,
  "total_calls": 14,
  "breakdown": {
    "semantic_search": 0.005,
    "search": 0.003,
    "list_filter": 0.0005
  }
}
```

## Data Flow

```
CLI run starts
  → reset_tracker() creates fresh OpenAlexCostTracker in ContextVar

  → ExplorerAgent: openalex_semantic_search × N queries
      each call → cost calculated → Langfuse span metadata + tracker.add()

  → PrecisionSearchAgent: openalex_precision_search × M boolean_queries
      each call → cost per query × query_count → Langfuse span metadata + tracker.add()

  → PerspectiveSearchAgent: openalex_get_related_works / openalex_fetch_works
      each call → cost calculated → Langfuse span metadata + tracker.add()

CLI run ends
  → tracker.summary_dict() → written to root Langfuse span metadata
```

## Langfuse Visibility

- **Per tool call:** `metadata.openalex_cost_usd` and `metadata.openalex_calls` on each tool span
- **Per run total:** `metadata.openalex_cost_summary` on the root pipeline span

## Out of Scope

- No persistence to database or file — Langfuse is the single source of truth
- No budget alerting — just tracking/reporting
- Singleton calls (free) are not tracked (no cost impact)
