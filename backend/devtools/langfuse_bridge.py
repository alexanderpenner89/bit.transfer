"""Langfuse bridge — query past successful observations for stage pre-fill.

All Langfuse SDK calls are wrapped in asyncio.to_thread() since the SDK is sync.
Filters for level == "DEFAULT" (successful observations only).
"""
from __future__ import annotations

import asyncio
from typing import Any


# Observation names as used in the codebase
STAGE_OBSERVATION_NAMES: dict[str, str] = {
    "strategy": "orchestrator.generate",
    "explorer": "explorer.run",
    "evaluator": "evaluator.evaluate",
    "precision": "precision_search.run",
    "expansion": "openalex_get_related_works",
    "pub_eval": "publication_evaluator.evaluate",
    "perspective": "perspective_search.run",
    "article": "article_generator.generate",
    "dossier": "dossier.generate",
}


def _fetch_observations_sync(name: str, limit: int) -> list[dict[str, Any]]:
    from config import get_langfuse
    client = get_langfuse()

    try:
        result = client.fetch_observations(name=name, limit=limit, level="DEFAULT")
        observations = []
        for obs in result.data:
            gewerk_id = None
            if isinstance(obs.input, dict):
                gewerk_id = obs.input.get("gewerk_id") or obs.input.get("gewerk")
            observations.append({
                "observation_id": obs.id,
                "trace_id": obs.trace_id,
                "name": obs.name,
                "created_at": obs.start_time.isoformat() if obs.start_time else None,
                "input": obs.input,
                "output": obs.output,
                "gewerk_id": gewerk_id,
            })
        return observations
    except Exception:
        return []


def _fetch_observation_sync(obs_id: str) -> dict[str, Any] | None:
    from config import get_langfuse
    client = get_langfuse()

    try:
        obs = client.fetch_observation(obs_id)
        gewerk_id = None
        if isinstance(obs.data.input, dict):
            gewerk_id = obs.data.input.get("gewerk_id") or obs.data.input.get("gewerk")
        return {
            "observation_id": obs.data.id,
            "trace_id": obs.data.trace_id,
            "name": obs.data.name,
            "created_at": obs.data.start_time.isoformat() if obs.data.start_time else None,
            "input": obs.data.input,
            "output": obs.data.output,
            "gewerk_id": gewerk_id,
        }
    except Exception:
        return None


async def list_observations(name: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return last N successful observations with the given name."""
    return await asyncio.to_thread(_fetch_observations_sync, name, limit)


async def get_observation(obs_id: str) -> dict[str, Any] | None:
    """Return a single observation by ID."""
    return await asyncio.to_thread(_fetch_observation_sync, obs_id)
