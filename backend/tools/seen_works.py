"""SeenWorksRegistry — Tracks processed OpenAlex Work-IDs across pipeline runs.

Prevents re-processing already-evaluated publications in daily incremental runs.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path


class SeenWorksRegistry:
    """Persistent registry of processed Work-IDs for a given Gewerk."""

    def __init__(self, gewerk_id: str, data_dir: str = "data/seen_works") -> None:
        self._path = Path(data_dir) / f"{gewerk_id}.json"

    def load(self) -> set[str]:
        """Load known Work-IDs. Returns empty set if no registry file exists."""
        if not self._path.exists():
            return set()
        with self._path.open(encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("work_ids", []))

    def save(self, work_ids: set[str]) -> None:
        """Merge new Work-IDs into the registry (additive, never overwrites existing)."""
        existing = self.load()
        merged = existing | work_ids
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "work_ids": sorted(merged),
                    "last_updated": datetime.date.today().isoformat(),
                },
                f,
                indent=2,
            )
