"""PrecisionSearchAgent — Stage 3a of the research pipeline.

Direct async orchestrator (no LLM). Executes all boolean queries against a
specific topic in parallel, deduplicates, and returns sorted WorkResults.

The LLM was removed: it added no intelligence (just called the tool and
returned results), while introducing GLM-incompatible tool-response messages.
"""
from __future__ import annotations

from config import get_langfuse, settings
from schemas.research_pipeline import TopicEvaluation, WorkResult
from tools.openalex_tools import openalex_precision_search


class PrecisionSearchAgent:
    """Stage 3a: Direct precision search for a single relevant topic (no LLM)."""

    async def run(
        self,
        topic: TopicEvaluation,
        boolean_queries: list[str],
    ) -> list[WorkResult]:
        """Run precision search directly against OpenAlex — no LLM roundtrip."""
        with get_langfuse().start_as_current_observation(
            name="precision_search.run",
            as_type="span",
            input={
                "topic_id": topic.topic_id,
                "topic_name": topic.display_name,
                "query_count": len(boolean_queries),
                "queries": boolean_queries,
                "from_publication_date": settings.openalex_precision_search_date,
            },
        ) as obs:
            try:
                works = await openalex_precision_search(
                    topic_id=topic.topic_id,
                    topic_name=topic.display_name,
                    boolean_queries=boolean_queries,
                    publication_date=settings.openalex_precision_search_date,
                )
                obs.update(
                    output={
                        "works_found": len(works),
                        "top_works": [
                            {"work_id": w.work_id, "title": w.title, "citations": w.citation_count}
                            for w in works[:5]
                        ],
                    },
                    level="WARNING" if not works else "DEFAULT",
                    **({"status_message": "No works found"} if not works else {}),
                )
                return works
            except Exception as e:
                obs.update(
                    level="ERROR",
                    status_message=f"{type(e).__name__}: {e}",
                )
                return []
