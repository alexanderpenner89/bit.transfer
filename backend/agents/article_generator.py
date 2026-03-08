"""ArticleGeneratorAgent — Stage C of the publication pipeline.

LLM-based (pydantic-ai). Generates enriched articles for interesting publications,
integrating perspectives and gewerk-specific insights.

Strict minimal-context principle — receives only what's needed for article generation.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai import Agent

from config import get_langfuse, settings
from schemas.publication_pipeline import ArticleSource, EnrichedArticle, WorkSummary


class ArticleWorkInput(BaseModel):
    """Minimal work info for article generation (no work_id, no raw topics)."""
    title: str
    abstract: str | None
    doi: str | None
    publication_year: int | None
    citation_count: int


class ArticleGewerksContext(BaseModel):
    """Minimal gewerk context for article generation."""
    gewerk_name: str
    kernkompetenzen: list[str]


@dataclass
class ArticleDeps:
    work_id: str  # kept for output construction only, not passed to LLM
    work: ArticleWorkInput
    perspectives: list[WorkSummary]
    gewerk_context: ArticleGewerksContext
    research_questions: list[str]


class ArticleGeneratorAgent:
    """Stage C: LLM-based article generation for a single publication."""

    def __init__(self, model=None) -> None:
        if model is None:
            model = settings.build_model()

        self.agent: Agent[ArticleDeps, EnrichedArticle] = Agent(
            model=model,
            output_type=EnrichedArticle,
            deps_type=ArticleDeps,
            defer_model_check=True,
        )
        self._register_prompts()

    async def generate(self, deps: ArticleDeps) -> EnrichedArticle:
        """Generate an enriched article for the given publication."""
        perspective_count = len(deps.perspectives)
        with get_langfuse().start_as_current_observation(
            name="article_generator.generate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={
                "work_id": deps.work_id,
                "gewerk_name": deps.gewerk_context.gewerk_name,
                "perspective_count": perspective_count,
            },
        ) as obs:
            user_prompt = self._build_user_prompt(deps)
            result = await self.agent.run(user_prompt, deps=deps)
            output = result.output
            usage = result.usage()

            obs.update(
                output={"source_count": len(output.sources)},
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
                level="DEFAULT",
            )
            # Ensure work_id and title are set correctly
            return EnrichedArticle(
                work_id=deps.work_id,
                title=deps.work.title,
                intro=output.intro,
                core_messages=output.core_messages,
                key_learnings=output.key_learnings,
                gewerk_insights=output.gewerk_insights,
                perspectives=output.perspectives,
                conclusion=output.conclusion,
                sources=output.sources,
            )

    def _build_user_prompt(self, deps: ArticleDeps) -> str:
        work = deps.work
        context = deps.gewerk_context
        kernkompetenzen = ", ".join(context.kernkompetenzen[:6])
        questions = "\n".join(f"  - {q}" for q in deps.research_questions)

        abstract_text = f"\n**Abstract:** {work.abstract}" if work.abstract else ""
        doi_text = f"\n**DOI:** {work.doi}" if work.doi else ""
        year_text = f" ({work.publication_year})" if work.publication_year else ""
        citations_text = f"\n**Zitierungen:** {work.citation_count}"

        perspectives_text = ""
        if deps.perspectives:
            persp_lines = []
            for p in deps.perspectives[:8]:
                abstract_short = f" — {p.abstract[:300]}..." if p.abstract else ""
                year = f" ({p.publication_year})" if p.publication_year else ""
                persp_lines.append(f"  • {p.title}{year}{abstract_short}")
            perspectives_text = "\n**Verwandte Arbeiten (Perspektiven):**\n" + "\n".join(persp_lines)
        else:
            perspectives_text = "\n**Verwandte Arbeiten:** Keine vorhanden"

        return f"""Erstelle einen fundierten Fachartikel für das folgende Handwerksgewerk basierend auf einer wissenschaftlichen Publikation.

**Hauptpublikation:**
- Titel: {work.title}{year_text}{doi_text}{citations_text}{abstract_text}
{perspectives_text}

**Gewerk:** {context.gewerk_name}
**Kernkompetenzen:** {kernkompetenzen}

**Forschungsfragen:**
{questions}

**Anforderungen an den Artikel:**
1. **intro**: Kurze Einleitung (2–3 Sätze) — Was ist die Publikation, warum ist sie relevant?
2. **core_messages**: 3–5 Kernbotschaften der Publikation als prägnante Stichpunkte
3. **key_learnings**: 3–5 konkrete Erkenntnisse, die direkt anwendbar sind
4. **gewerk_insights**: Was kann das Gewerk konkret mitnehmen? (1–2 Absätze)
5. **perspectives**: Unterstützende und kritische Perspektiven aus den verwandten Arbeiten einarbeiten (1–2 Absätze)
6. **conclusion**: Zusammenfassung und Ausblick (2–3 Sätze)
7. **sources**: Quellenverweise für ALLE Aussagen (Hauptpublikation als "primary", verwandte als "supporting" oder "contrasting")

**Stil:** Sachlich, zugänglich, praxisorientiert. Keine akademischen Floskeln."""

    def _register_prompts(self) -> None:
        @self.agent.system_prompt
        def system_prompt() -> str:
            return (
                "Du bist ein erfahrener Fachjournalist für Handwerk und Bautechnik.\n"
                "Du erstellst fundierte, praxisorientierte Fachartikel für Handwerksgewerke "
                "auf Basis wissenschaftlicher Publikationen.\n\n"
                "Dein Ziel:\n"
                "- Wissenschaftliche Erkenntnisse für Praktiker zugänglich machen\n"
                "- Konkrete Anwendungshinweise geben\n"
                "- Verschiedene Perspektiven (unterstützend und kritisch) einarbeiten\n"
                "- Alle Quellen korrekt zitieren\n\n"
                "Stil: Sachlich, präzise, ohne Fachjargon wo möglich. "
                "Schreibe für erfahrene Handwerker, nicht für Akademiker.\n\n"
                "Setze work_id und title korrekt aus dem Kontext.\n"
                "citation_type: 'primary' für die Hauptpublikation, "
                "'supporting' für unterstützende, 'contrasting' für kritische Perspektiven."
            )
