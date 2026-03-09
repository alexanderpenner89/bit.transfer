"""OpenAlex cost tracking utilities.

Pricing reference (per 1,000 calls):
  Semantic search:  $1.00  → $0.001 per call
  Search (boolean): $1.00  → $0.001 per call
  List + Filter:    $0.10  → $0.0001 per call
  Singleton:        Free
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

COST_SEMANTIC_SEARCH: float = 0.001
COST_SEARCH: float = 0.001
COST_LIST_FILTER: float = 0.0001


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
