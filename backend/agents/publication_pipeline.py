"""PublicationPipeline — Async orchestrator for the publication pipeline.

No LLM. Coordinates:
  A: PublicationEvaluatorAgent × N (parallel, LLM)
  B: PerspectiveSearchAgent × K (parallel, no LLM)
  C: ArticleGeneratorAgent × K (parallel, LLM)
  D: DossierAgent (LLM)
"""
from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from config import get_langfuse, settings
from schemas.publication_pipeline import (
    DossierModel,
    EnrichedArticle,
    GewerksContext,
    ResearchQuestionsModel,
)
from schemas.research_pipeline import ResearchResult, WorkResult

from agents.article_generator import ArticleDeps, ArticleGewerksContext, ArticleWorkInput, ArticleGeneratorAgent
from agents.dossier import ArticleSummary, DossierAgent, DossierDeps
from agents.perspective_search import PerspectiveInput, PerspectiveSearchAgent
from agents.publication_evaluator import EvalContext, PublicationEvaluatorAgent, WorkEvalInput

_T = TypeVar("_T")


class PublicationPipeline:
    """Orchestrates the full publication pipeline for a research result."""

    def __init__(
        self,
        model=None,
        on_progress: Callable[[str], None] | None = None,
        max_works: int | None = None,
        skip_work_ids: set[str] = frozenset(),
    ) -> None:
        self._evaluator = PublicationEvaluatorAgent(model=model)
        self._perspective = PerspectiveSearchAgent()
        self._article_gen = ArticleGeneratorAgent(model=model)
        self._dossier = DossierAgent(model=model)
        self._log = on_progress or (lambda _: None)
        self._llm_sem = asyncio.Semaphore(settings.llm_concurrency)
        self._max_works = max_works
        self._skip_work_ids = skip_work_ids

    async def _llm(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Run a coroutine with the LLM concurrency semaphore."""
        async with self._llm_sem:
            return await coro

    async def run(
        self,
        research_result: ResearchResult,
        research_questions: ResearchQuestionsModel,
        gewerk_context: GewerksContext,
    ) -> DossierModel:
        """Execute the full publication pipeline."""
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        all_works = research_result.precision_works + research_result.expanded_works
        publication_count = len(all_works)

        with get_langfuse().start_as_current_observation(
            name="publication_pipeline.run",
            as_type="agent",
            input={
                "gewerk_id": gewerk_context.gewerk_id,
                "publication_count": publication_count,
            },
        ) as span:
            # Skip if no publications found
            if publication_count == 0:
                self._log("  [yellow]⚠[/yellow] Keine Publikationen gefunden — leeres Dossier wird erstellt")
                empty_dossier = DossierModel(
                    gewerk_id=gewerk_context.gewerk_id,
                    gewerk_name=gewerk_context.gewerk_name,
                    research_questions=research_questions.research_questions,
                    generated_at=generated_at,
                    executive_summary="Keine wissenschaftlichen Publikationen gefunden.",
                    articles=[],
                    key_findings=[],
                )
                span.update(output={"articles": 0, "skipped": True})
                return empty_dossier

            # Deduplicate works (precision + expanded)
            seen: set[str] = set()
            unique_works: list[WorkResult] = []
            for w in all_works:
                if w.work_id not in seen:
                    seen.add(w.work_id)
                    unique_works.append(w)

            if self._skip_work_ids:
                before = len(unique_works)
                unique_works = [w for w in unique_works if w.work_id not in self._skip_work_ids]
                self._log(f"  [dim]→ {len(unique_works)} neue Works (nach Duplikat-Filter, {before - len(unique_works)} übersprungen)[/dim]")

            if self._max_works:
                unique_works = unique_works[: self._max_works]

            self._log(f"  [dim]→ {len(unique_works)} einzigartige Publikationen zur Bewertung[/dim]")

            eval_context = EvalContext(
                gewerk_name=gewerk_context.gewerk_name,
                kernkompetenzen=gewerk_context.kernkompetenzen,
                research_questions=research_questions.research_questions,
            )

            # Stage A: Parallel publication evaluation
            with get_langfuse().start_as_current_observation(
                name="publication_evaluator.batch",
                as_type="span",
                input={"publication_count": len(unique_works)},
            ) as eval_span:
                eval_results = await asyncio.gather(
                    *[
                        self._llm(self._evaluator.evaluate(
                            work=WorkEvalInput(
                                work_id=w.work_id,
                                title=w.title,
                                abstract=w.abstract,
                                publication_year=w.publication_year,
                            ),
                            context=eval_context,
                        ))
                        for w in unique_works
                    ],
                    return_exceptions=True,
                )
                eval_errors = sum(1 for r in eval_results if isinstance(r, Exception))
                interesting_evals = [
                    r for r in eval_results
                    if not isinstance(r, Exception) and r.is_interesting
                ]
                eval_span.update(
                    output={
                        "interesting": len(interesting_evals),
                        "errors": eval_errors,
                        "interesting_titles": [r.title for r in interesting_evals],
                    },
                    **({"level": "WARNING", "status_message": f"{eval_errors} evaluation(s) failed"} if eval_errors else {"level": "DEFAULT"}),
                )

            self._log(f"  [green]✓[/green] {len(interesting_evals)}/{len(unique_works)} Publikationen interessant")

            if not interesting_evals:
                self._log("  [yellow]⚠[/yellow] Keine interessanten Publikationen — leeres Dossier")
                empty_dossier = DossierModel(
                    gewerk_id=gewerk_context.gewerk_id,
                    gewerk_name=gewerk_context.gewerk_name,
                    research_questions=research_questions.research_questions,
                    generated_at=generated_at,
                    executive_summary="Keine für das Gewerk relevanten Publikationen gefunden.",
                    articles=[],
                    key_findings=[],
                )
                span.update(output={"articles": 0, "interesting": 0})
                return empty_dossier

            # Build work_id → WorkResult lookup
            work_lookup: dict[str, WorkResult] = {w.work_id: w for w in unique_works}

            # Stage B: Parallel perspective search (no LLM)
            self._log(f"  [dim]→ Perspektivensuche: {len(interesting_evals)} Publikationen parallel (OpenAlex)...[/dim]")
            with get_langfuse().start_as_current_observation(
                name="perspective_search.batch",
                as_type="span",
                input={"publication_count": len(interesting_evals)},
            ) as persp_span:
                perspective_results = await asyncio.gather(
                    *[
                        self._perspective.run(PerspectiveInput(
                            work_id=ev.work_id,
                            title=ev.title,
                            referenced_work_ids=work_lookup[ev.work_id].referenced_work_ids
                            if ev.work_id in work_lookup else [],
                        ))
                        for ev in interesting_evals
                    ],
                    return_exceptions=True,
                )
                persp_errors = sum(1 for r in perspective_results if isinstance(r, Exception))
                valid_perspectives = [
                    r for r in perspective_results if not isinstance(r, Exception)
                ]
                persp_span.update(
                    output={"success": len(valid_perspectives), "errors": persp_errors},
                    **({"level": "WARNING", "status_message": f"{persp_errors} perspective search(es) failed"} if persp_errors else {"level": "DEFAULT"}),
                )

            self._log(f"  [green]✓[/green] Perspektiven gesammelt")

            # Build work_id → PerspectiveResult lookup
            perspective_lookup = {r.main_work_id: r for r in valid_perspectives}

            # Stage C: Parallel article generation (LLM)
            self._log(f"  [dim]→ Artikelgenerierung: {len(interesting_evals)} Artikel parallel (LLM)...[/dim]")
            gewerk_ctx = ArticleGewerksContext(
                gewerk_name=gewerk_context.gewerk_name,
                kernkompetenzen=gewerk_context.kernkompetenzen,
            )
            with get_langfuse().start_as_current_observation(
                name="article_generator.batch",
                as_type="span",
                input={"article_count": len(interesting_evals)},
            ) as art_span:
                article_results = await asyncio.gather(
                    *[
                        self._llm(self._article_gen.generate(ArticleDeps(
                            work_id=ev.work_id,
                            work=ArticleWorkInput(
                                title=ev.title,
                                abstract=work_lookup[ev.work_id].abstract if ev.work_id in work_lookup else None,
                                doi=work_lookup[ev.work_id].doi if ev.work_id in work_lookup else None,
                                publication_year=work_lookup[ev.work_id].publication_year if ev.work_id in work_lookup else None,
                                citation_count=work_lookup[ev.work_id].citation_count if ev.work_id in work_lookup else 0,
                            ),
                            perspectives=perspective_lookup[ev.work_id].related_works
                            if ev.work_id in perspective_lookup else [],
                            gewerk_context=gewerk_ctx,
                            research_questions=research_questions.research_questions,
                        )))
                        for ev in interesting_evals
                    ],
                    return_exceptions=True,
                )
                art_errors = sum(1 for r in article_results if isinstance(r, Exception))
                articles: list[EnrichedArticle] = [
                    r for r in article_results if not isinstance(r, Exception)
                ]
                art_span.update(
                    output={"generated": len(articles), "errors": art_errors},
                    **({"level": "WARNING", "status_message": f"{art_errors} article(s) failed"} if art_errors else {"level": "DEFAULT"}),
                )

            self._log(f"  [green]✓[/green] {len(articles)} Artikel generiert")

            # Stage D: Dossier generation (LLM)
            self._log("  [dim]→ Dossier-Generierung (LLM)...[/dim]")
            article_summaries = [
                ArticleSummary(
                    title=art.title,
                    intro=art.intro,
                    key_learnings=art.key_learnings,
                )
                for art in articles
            ]
            dossier_deps = DossierDeps(
                gewerk_id=gewerk_context.gewerk_id,
                gewerk_name=gewerk_context.gewerk_name,
                research_questions=research_questions.research_questions,
                article_summaries=article_summaries,
            )
            dossier = await self._llm(
                self._dossier.generate(dossier_deps, articles, generated_at)
            )
            self._log(f"  [green]✓[/green] Dossier erstellt mit {len(dossier.key_findings)} Key Findings")

            span.update(output={
                "articles": len(articles),
                "key_findings": len(dossier.key_findings),
                "article_titles": [a.title for a in articles],
            })
            return dossier
