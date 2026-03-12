"""DossierAgent — Stage D of the publication pipeline.

LLM-based (pydantic-ai). Generates the final dossier with executive summary
and key findings from all enriched articles.

Minimal-context principle: receives only article summaries (not full articles).
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai import Agent

from config import compile_prompt_user_msg, fetch_prompt, get_langfuse, get_prompt_system_msg, settings
from schemas.publication_pipeline import DossierModel, EnrichedArticle


class ArticleSummary(BaseModel):
    """Minimal article representation for dossier generation."""
    title: str
    intro: str
    key_learnings: list[str]


@dataclass
class DossierDeps:
    gewerk_id: str
    gewerk_name: str
    research_questions: list[str]
    article_summaries: list[ArticleSummary]


class _DossierOutput(BaseModel):
    """LLM output for dossier — articles are provided separately."""
    executive_summary: str
    key_findings: list[str]


class DossierAgent:
    """Stage D: LLM-based dossier generation from all enriched articles."""

    def __init__(self, model=None) -> None:
        if model is None:
            model = settings.build_model()

        self.agent: Agent[DossierDeps, _DossierOutput] = Agent(
            model=model,
            output_type=_DossierOutput,
            deps_type=DossierDeps,
            defer_model_check=True,
        )
        self._langfuse_prompt = fetch_prompt("dossier")
        self._register_prompts()

    async def generate(
        self,
        deps: DossierDeps,
        articles: list[EnrichedArticle],
        generated_at: str,
    ) -> DossierModel:
        """Generate the final dossier from article summaries."""
        article_count = len(deps.article_summaries)
        with get_langfuse().start_as_current_observation(
            name="dossier.generate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={
                "gewerk_name": deps.gewerk_name,
                "article_count": article_count,
            },
        ) as obs:
            user_prompt = self._build_user_prompt(deps)
            result = await self.agent.run(user_prompt, deps=deps)
            output = result.output
            usage = result.usage()

            obs.update(
                output={"findings_count": len(output.key_findings)},
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
                level="DEFAULT",
            )
            return DossierModel(
                gewerk_id=deps.gewerk_id,
                gewerk_name=deps.gewerk_name,
                research_questions=deps.research_questions,
                generated_at=generated_at,
                executive_summary=output.executive_summary,
                articles=articles,
                key_findings=output.key_findings,
            )

    def _build_user_prompt(self, deps: DossierDeps) -> str:
        questions = "\n".join(f"  - {q}" for q in deps.research_questions)
        articles_text = ""
        for i, art in enumerate(deps.article_summaries, 1):
            learnings = "\n".join(f"    · {l}" for l in art.key_learnings[:3])
            articles_text += (
                f"\n**Artikel {i}: {art.title}**\n"
                f"  {art.intro}\n"
                f"  Key Learnings:\n{learnings}\n"
            )
        fallback = f"""Erstelle ein Executive Summary und übergreifende Schlüsselerkenntnisse für das folgende Forschungsdossier.

**Gewerk:** {deps.gewerk_name}

**Forschungsfragen:**
{questions}

**Ausgewertete Artikel ({len(deps.article_summaries)}):**
{articles_text}

**Aufgabe:**
1. **executive_summary**: Übergreifende Zusammenfassung aller Erkenntnisse (3–5 Sätze). Was sind die wichtigsten Trends und Erkenntnisse für das Gewerk?
2. **key_findings**: 5–8 übergreifende Schlüsselerkenntnisse als prägnante Stichpunkte. Was sind die wichtigsten, gewerksübergreifenden Learnings?

Achte auf Kohärenz und Praxisrelevanz."""
        return compile_prompt_user_msg(
            self._langfuse_prompt,
            fallback,
            gewerk_name=deps.gewerk_name,
            research_questions=questions,
            article_count=str(len(deps.article_summaries)),
            articles=articles_text,
        )

    def _register_prompts(self) -> None:
        @self.agent.system_prompt
        def system_prompt() -> str:
            return get_prompt_system_msg(
                self._langfuse_prompt,
                (
                    "Du bist ein erfahrener Experte für Handwerk und Technologietransfer.\n"
                    "Deine Aufgabe ist es, aus mehreren Fachartikeln ein kohärentes Dossier "
                    "für ein Handwerksgewerk zu erstellen.\n\n"
                    "Das Executive Summary soll:\n"
                    "- Alle wichtigen Erkenntnisse übergreifend zusammenfassen\n"
                    "- Den roten Faden zwischen den verschiedenen Publikationen herstellen\n"
                    "- Konkrete Handlungsempfehlungen für das Gewerk geben\n\n"
                    "Die Key Findings sollen:\n"
                    "- Die wichtigsten, gewerksübergreifenden Erkenntnisse benennen\n"
                    "- Keine Duplikate aus einzelnen Artikeln, sondern übergreifende Schlüsse\n"
                    "- Prägnant und handlungsorientiert formuliert sein"
                ),
            )
