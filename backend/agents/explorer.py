"""ExplorerAgent — Stage 1 of the research pipeline.

Pure async Python orchestrator (no LLM). Executes semantic queries in parallel,
deduplicates works, and counts topic frequencies to build TopicCandidate list.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter

from config import get_langfuse
from schemas.research_pipeline import ExplorationResult, TopicCandidate, WorkResult
from schemas.search_strategy import SearchStrategyModel
from tools.openalex_tools import openalex_semantic_search


class ExplorerAgent:
    """Stage 1: Parallel semantic search → deduplicated works + topic candidates."""

    async def run(
        self,
        strategy: SearchStrategyModel,
        max_queries: int | None = None,
    ) -> ExplorationResult:
        """Run all semantic queries in parallel and aggregate results."""
        queries = strategy.semantic_queries_en
        if max_queries:
            queries = queries[:max_queries]

        with get_langfuse().start_as_current_observation(
            name="explorer.run",
            as_type="agent",
            input={"gewerk_id": strategy.gewerk_id, "query_count": len(queries)},
        ) as span:
            results = await asyncio.gather(
                *[openalex_semantic_search(q) for q in queries],
                return_exceptions=True,
            )

            failed = [r for r in results if isinstance(r, Exception)]
            for query, result in zip(queries, results):
                if isinstance(result, Exception):
                    logging.warning("Semantic search failed for query %r: %s", query[:80], result)

            seen: dict[str, WorkResult] = {}
            for result in results:
                if isinstance(result, Exception):
                    continue
                for work in result:
                    if work.work_id not in seen:
                        seen[work.work_id] = work

            works = list(seen.values())

            topic_counter: Counter[str] = Counter()
            topic_names: dict[str, str] = {}
            for work in works:
                for t in work.topics:
                    topic_counter[t.topic_id] += 1
                    topic_names[t.topic_id] = t.display_name

            topic_candidates = [
                TopicCandidate(
                    topic_id=tid,
                    display_name=topic_names[tid],
                    frequency=freq,
                )
                for tid, freq in topic_counter.most_common()
            ]

            # Determine log level based on failure rate
            if len(failed) == len(queries):
                level, status_message = "ERROR", "All semantic queries failed"
            elif failed:
                level = "WARNING"
                status_message = f"{len(failed)}/{len(queries)} queries failed"
            elif not works:
                level, status_message = "WARNING", "No works found across all queries"
            else:
                level, status_message = "DEFAULT", None

            span.update(
                output={
                    "works_found": len(works),
                    "topics_discovered": len(topic_candidates),
                    "queries_failed": len(failed),
                },
                level=level,
                **({"status_message": status_message} if status_message else {}),
            )

            return ExplorationResult(
                gewerk_id=strategy.gewerk_id,
                works=works,
                topic_candidates=topic_candidates,
            )
