"""Persistent JSON store for DevTools run records.

Atomic writes (tmp → os.replace) protected by asyncio.Lock.
Stores to data/dev_runs/runs.json inside the app directory.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

STAGES = [
    "strategy",
    "explorer",
    "evaluator",
    "precision",
    "expansion",
    "pub_eval",
    "perspective",
    "article",
    "dossier",
]

_STORE_PATH = Path("/app/data/dev_runs/runs.json")
_lock = asyncio.Lock()


def _default_stage() -> dict[str, Any]:
    return {
        "status": "not_run",
        "started_at": None,
        "completed_at": None,
        "output": None,
        "error": None,
    }


def _default_stages() -> dict[str, Any]:
    return {stage: _default_stage() for stage in STAGES}


def _load_raw() -> dict[str, Any]:
    if _STORE_PATH.exists():
        try:
            return json.loads(_STORE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"runs": {}}


def _save_raw(data: dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    os.replace(tmp, _STORE_PATH)


async def create_run(run_id: str, gewerk_id: str, gewerk_name: str, created_at: str) -> dict[str, Any]:
    async with _lock:
        data = _load_raw()
        run = {
            "run_id": run_id,
            "gewerk_id": gewerk_id,
            "gewerk_name": gewerk_name,
            "created_at": created_at,
            "stages": _default_stages(),
        }
        data["runs"][run_id] = run
        _save_raw(data)
        return run


async def get_run(run_id: str) -> dict[str, Any] | None:
    async with _lock:
        data = _load_raw()
        return data["runs"].get(run_id)


async def list_runs() -> list[dict[str, Any]]:
    async with _lock:
        data = _load_raw()
        runs = list(data["runs"].values())
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return runs


async def delete_run(run_id: str) -> bool:
    async with _lock:
        data = _load_raw()
        if run_id not in data["runs"]:
            return False
        del data["runs"][run_id]
        _save_raw(data)
        return True


async def update_stage(run_id: str, stage: str, updates: dict[str, Any]) -> None:
    async with _lock:
        data = _load_raw()
        if run_id not in data["runs"]:
            return
        data["runs"][run_id]["stages"][stage].update(updates)
        _save_raw(data)


async def cancel_running_stages(run_id: str) -> list[str]:
    """Mark all 'running' stages as 'cancelled'. Returns list of cancelled stage names."""
    async with _lock:
        data = _load_raw()
        if run_id not in data["runs"]:
            return []
        cancelled = []
        for stage, info in data["runs"][run_id]["stages"].items():
            if info["status"] == "running":
                info["status"] = "cancelled"
                info["completed_at"] = None
                info["error"] = "Cancelled by user"
                cancelled.append(stage)
        if cancelled:
            _save_raw(data)
        return cancelled
