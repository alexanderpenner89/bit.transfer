"""ResearchAggregator — Top-level orchestrator of the research pipeline.

Pure async Python (no LLM). Coordinates all 4 agents in sequence:
  1. ExplorerAgent      — parallel semantic search
  2. TopicEvaluatorAgent × N — parallel topic relevance evaluation
  3. PrecisionSearchAgent × M — parallel precision search per relevant topic
  4. openalex_get_related_works — citation network expansion on top papers
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

_T = TypeVar("_T")

from config import get_langfuse

from agents.evaluator import TopicEvaluatorAgent
from agents.explorer import ExplorerAgent
from agents.precision_search import PrecisionSearchAgent
from schemas.gewerksprofil import GewerksProfilModel
from schemas.research_pipeline import ResearchResult, WorkResult
from schemas.search_strategy import SearchStrategyModel
from tools.openalex_tools import openalex_get_related_works

_TOP_N_FOR_EXPANSION = 10


class ResearchAggregator:
    """Orchestrates the full 4-stage research pipeline."""

    def __init__(
        self,
        model=None,
        on_progress: Callable[[str], None] | None = None,
        max_topics: int | None = None,
        max_queries: int | None = None,
        skip_expansion: bool = False,
    ) -> None:
        from config import settings
        self._explorer = ExplorerAgent()
        self._evaluator = TopicEvaluatorAgent(model=model)
        self._precision = PrecisionSearchAgent()
        self._log = on_progress or (lambda _: None)
        self._llm_sem = asyncio.Semaphore(settings.llm_concurrency)
        self._max_topics = max_topics
        self._max_queries = max_queries
        self._skip_expansion = skip_expansion

    async def _llm(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Run a coroutine with the LLM concurrency semaphore."""
        async with self._llm_sem:
            return await coro

    async def run(
        self,
        strategy: SearchStrategyModel,
        profil: GewerksProfilModel,
    ) -> ResearchResult:
        """Execute the full research pipeline for the given strategy and profile."""

        with get_langfuse().start_as_current_observation(
            name="aggregator.run",
            as_type="agent",
            input={"gewerk_id": strategy.gewerk_id, "gewerk_name": profil.gewerk_name},
        ) as span:
            # Stage 1: Parallel semantic search
            semantic_query_count = min(len(strategy.semantic_queries_en), self._max_queries) if self._max_queries else len(strategy.semantic_queries_en)
            self._log(f"  [dim]→ Semantische Suche: {semantic_query_count} Queries parallel...[/dim]")
            exploration = await self._explorer.run(strategy, max_queries=self._max_queries)
            self._log(f"  [green]✓[/green] {len(exploration.works)} Works gefunden, {len(exploration.topic_candidates)} Topics entdeckt")

            # Stage 2: Parallel topic evaluation
            topic_candidates = exploration.topic_candidates
            if self._max_topics:
                topic_candidates = topic_candidates[: self._max_topics]
            n = len(topic_candidates)
            self._log(f"  [dim]→ Topic-Evaluierung: {n} Topics parallel (LLM)...[/dim]")
            with get_langfuse().start_as_current_observation(
                name="evaluator.batch",
                as_type="span",
                input={"topic_count": n},
            ) as eval_span:
                evaluations = await asyncio.gather(
                    *[
                        self._llm(self._evaluator.evaluate(candidate, profil))
                        for candidate in topic_candidates
                    ],
                    return_exceptions=True,
                )
                eval_errors = sum(1 for ev in evaluations if isinstance(ev, Exception))
                relevant_topics = [
                    ev
                    for ev in evaluations
                    if not isinstance(ev, Exception) and ev.is_relevant
                ]
                eval_span.update(
                    output={"relevant": len(relevant_topics), "errors": eval_errors},
                    **({"level": "WARNING", "status_message": f"{eval_errors} evaluation(s) failed"} if eval_errors else {"level": "DEFAULT"}),
                )
            self._log(f"  [green]✓[/green] {len(relevant_topics)}/{n} Topics relevant")

            # Stage 3: Parallel precision search per relevant topic
            all_boolean_queries = (
                strategy.boolean_queries_de + strategy.boolean_queries_en
            )
            if self._max_queries:
                all_boolean_queries = all_boolean_queries[: self._max_queries]
            self._log(f"  [dim]→ Präzisionssuche: {len(relevant_topics)} Topics × {len(all_boolean_queries)} Queries parallel (OpenAlex)...[/dim]")
            with get_langfuse().start_as_current_observation(
                name="precision_search.batch",
                as_type="span",
                input={"topic_count": len(relevant_topics), "query_count": len(all_boolean_queries)},
            ) as ps_span:
                precision_results = await asyncio.gather(
                    *[
                        self._llm(self._precision.run(topic, all_boolean_queries))
                        for topic in relevant_topics
                    ],
                    return_exceptions=True,
                )
                precision_errors = sum(1 for r in precision_results if isinstance(r, Exception))

                seen: set[str] = set()
                precision_works: list[WorkResult] = []
                for result in precision_results:
                    if isinstance(result, Exception):
                        continue
                    for work in result:
                        if work.work_id not in seen:
                            seen.add(work.work_id)
                            precision_works.append(work)

                precision_works.sort(key=lambda w: w.citation_count, reverse=True)
                ps_span.update(
                    output={"works_found": len(precision_works), "errors": precision_errors},
                    **({"level": "WARNING", "status_message": f"{precision_errors} search(es) failed"} if precision_errors else {"level": "DEFAULT"}),
                )
            self._log(f"  [green]✓[/green] {len(precision_works)} Precision Works (dedupliziert, nach Citations sortiert)")

            # Stage 4: Citation network expansion on top-N precision works
            top_ids = [w.work_id for w in precision_works[:_TOP_N_FOR_EXPANSION]]
            expanded_works: list[WorkResult] = []
            expansion_failed = False
            if top_ids and not self._skip_expansion:
                self._log(f"  [dim]→ Zitiernetzwerk: Top-{len(top_ids)} Works expandieren (OpenAlex)...[/dim]")
                try:
                    expanded_works = await openalex_get_related_works(
                        top_ids, mode="cited_by"
                    )
                    self._log(f"  [green]✓[/green] {len(expanded_works)} Expanded Works")
                except Exception:
                    expanded_works = []
                    expansion_failed = True
                    self._log("  [yellow]⚠[/yellow] Zitiernetzwerk-Expansion fehlgeschlagen (wird übersprungen)")
            elif self._skip_expansion:
                self._log("  [dim]→ Zitiernetzwerk-Expansion übersprungen (--lite)[/dim]")

            # Determine overall log level
            warnings = []
            if not relevant_topics:
                warnings.append("no relevant topics found")
            if eval_errors:
                warnings.append(f"{eval_errors} evaluation(s) failed")
            if precision_errors:
                warnings.append(f"{precision_errors} precision search(es) failed")
            if expansion_failed:
                warnings.append("citation expansion failed")

            if warnings:
                level, status_message = "WARNING", "; ".join(warnings)
            else:
                level, status_message = "DEFAULT", None

            span.update(
                output={
                    "total_works": len(precision_works) + len(expanded_works),
                    "relevant_topics": len(relevant_topics),
                    "eval_errors": eval_errors,
                    "precision_errors": precision_errors,
                },
                level=level,
                **({"status_message": status_message} if status_message else {}),
            )

            return ResearchResult(
                gewerk_id=strategy.gewerk_id,
                exploration_works=exploration.works,
                precision_works=precision_works,
                expanded_works=expanded_works,
                relevant_topics=relevant_topics,
            )
