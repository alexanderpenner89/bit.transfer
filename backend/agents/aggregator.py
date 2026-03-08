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

    def __init__(self, model=None, on_progress: Callable[[str], None] | None = None) -> None:
        from config import settings
        self._explorer = ExplorerAgent()
        self._evaluator = TopicEvaluatorAgent(model=model)
        self._precision = PrecisionSearchAgent(model=model)
        self._log = on_progress or (lambda _: None)
        self._llm_sem = asyncio.Semaphore(settings.llm_concurrency)

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
            as_type="span",
            input={"gewerk_id": strategy.gewerk_id, "gewerk_name": profil.gewerk_name},
        ) as span:
            # Stage 1: Parallel semantic search
            self._log(f"  [dim]→ Semantische Suche: {len(strategy.semantic_queries_en)} Queries parallel...[/dim]")
            exploration = await self._explorer.run(strategy)
            self._log(f"  [green]✓[/green] {len(exploration.works)} Works gefunden, {len(exploration.topic_candidates)} Topics entdeckt")

            # Stage 2: Parallel topic evaluation
            n = len(exploration.topic_candidates)
            self._log(f"  [dim]→ Topic-Evaluierung: {n} Topics parallel (LLM)...[/dim]")
            evaluations = await asyncio.gather(
                *[
                    self._llm(self._evaluator.evaluate(candidate, profil))
                    for candidate in exploration.topic_candidates
                ],
                return_exceptions=True,
            )
            relevant_topics = [
                ev
                for ev in evaluations
                if not isinstance(ev, Exception) and ev.is_relevant
            ]
            self._log(f"  [green]✓[/green] {len(relevant_topics)}/{n} Topics relevant")

            # Stage 3: Parallel precision search per relevant topic
            all_boolean_queries = (
                strategy.boolean_queries_de + strategy.boolean_queries_en
            )
            self._log(f"  [dim]→ Präzisionssuche: {len(relevant_topics)} Topics × {len(all_boolean_queries)} Queries parallel (OpenAlex)...[/dim]")
            precision_results = await asyncio.gather(
                *[
                    self._llm(self._precision.run(topic, all_boolean_queries))
                    for topic in relevant_topics
                ],
                return_exceptions=True,
            )

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
            self._log(f"  [green]✓[/green] {len(precision_works)} Precision Works (dedupliziert, nach Citations sortiert)")

            # Stage 4: Citation network expansion on top-N precision works
            top_ids = [w.work_id for w in precision_works[:_TOP_N_FOR_EXPANSION]]
            expanded_works: list[WorkResult] = []
            if top_ids:
                self._log(f"  [dim]→ Zitiernetzwerk: Top-{len(top_ids)} Works expandieren (OpenAlex)...[/dim]")
                try:
                    expanded_works = await openalex_get_related_works(
                        top_ids, mode="cited_by"
                    )
                    self._log(f"  [green]✓[/green] {len(expanded_works)} Expanded Works")
                except Exception:
                    expanded_works = []
                    self._log("  [yellow]⚠[/yellow] Zitiernetzwerk-Expansion fehlgeschlagen (wird übersprungen)")

            span.update(
                output={
                    "total_works": len(precision_works) + len(expanded_works),
                    "relevant_topics": len(relevant_topics),
                }
            )

            return ResearchResult(
                gewerk_id=strategy.gewerk_id,
                exploration_works=exploration.works,
                precision_works=precision_works,
                expanded_works=expanded_works,
                relevant_topics=relevant_topics,
            )
