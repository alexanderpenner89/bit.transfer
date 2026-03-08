"""PerspectiveSearchAgent — Stage B of the publication pipeline.

Pure async orchestrator (no LLM). Finds related works via OpenAlex
to provide supporting/contrasting perspectives for article generation.

Minimal-context principle: receives only work_id, title, referenced_work_ids.
"""
from __future__ import annotations

from pydantic import BaseModel

from config import get_langfuse
from schemas.publication_pipeline import PerspectiveResult, WorkSummary
from schemas.research_pipeline import WorkResult
from tools.openalex_tools import openalex_get_related_works, openalex_semantic_search

_MAX_RELATED = 8


class PerspectiveInput(BaseModel):
    work_id: str
    title: str
    referenced_work_ids: list[str]


def _to_work_summary(work: WorkResult) -> WorkSummary:
    return WorkSummary(
        work_id=work.work_id,
        title=work.title,
        abstract=work.abstract,
        doi=work.doi,
        publication_year=work.publication_year,
    )


class PerspectiveSearchAgent:
    """Stage B: Finds related works for perspective enrichment (no LLM)."""

    async def run(self, inp: PerspectiveInput) -> PerspectiveResult:
        """Find related works via references and semantic search."""
        with get_langfuse().start_as_current_observation(
            name="perspective_search.run",
            as_type="tool",
            input={"work_id": inp.work_id},
        ) as obs:
            seen: set[str] = {inp.work_id}
            related: list[WorkSummary] = []

            # Step 1: References (what does this paper cite?)
            ref_ids = inp.referenced_work_ids[:5]
            if ref_ids:
                try:
                    ref_works = await openalex_get_related_works(ref_ids, mode="references")
                    for w in ref_works:
                        if w.work_id not in seen:
                            seen.add(w.work_id)
                            related.append(_to_work_summary(w))
                except Exception:
                    pass

            # Step 2: Semantic search for thematically similar works
            try:
                semantic_works = await openalex_semantic_search(inp.title, max_results=10)
                for w in semantic_works:
                    if w.work_id not in seen and len(related) < _MAX_RELATED:
                        seen.add(w.work_id)
                        related.append(_to_work_summary(w))
            except Exception:
                pass

            # Limit to max results
            related = related[:_MAX_RELATED]

            obs.update(output={"related_count": len(related)})
            return PerspectiveResult(
                main_work_id=inp.work_id,
                related_works=related,
            )
