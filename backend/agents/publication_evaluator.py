"""PublicationEvaluatorAgent — Stage A of the publication pipeline.

LLM-based (pydantic-ai). Evaluates whether a publication is interesting and
relevant for a craft trade, and extracts key insights.

Strict minimal-context principle: receives only what's needed for evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai import Agent

from config import fetch_prompt, get_langfuse, settings
from schemas.publication_pipeline import PublicationEvaluation


class WorkEvalInput(BaseModel):
    """Minimal work representation for evaluation (no doi, no topics)."""
    work_id: str
    title: str
    abstract: str | None
    publication_year: int | None


class EvalContext(BaseModel):
    """Gewerk context for evaluation."""
    gewerk_name: str
    kernkompetenzen: list[str]
    research_questions: list[str]


@dataclass
class EvalDeps:
    work: WorkEvalInput
    context: EvalContext


class PublicationEvaluatorAgent:
    """Stage A: LLM-based relevance evaluation for a single publication."""

    def __init__(self, model=None) -> None:
        if model is None:
            model = settings.build_model()

        self.agent: Agent[EvalDeps, PublicationEvaluation] = Agent(
            model=model,
            output_type=PublicationEvaluation,
            deps_type=EvalDeps,
            defer_model_check=True,
        )
        self._langfuse_prompt = fetch_prompt("publication-evaluator")
        self._register_prompts()

    async def evaluate(
        self,
        work: WorkEvalInput,
        context: EvalContext,
    ) -> PublicationEvaluation:
        """Evaluate whether a publication is interesting for the craft trade."""
        with get_langfuse().start_as_current_observation(
            name="publication_evaluator.evaluate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={
                "work_id": work.work_id,
                "title": work.title,
                "gewerk_name": context.gewerk_name,
            },
        ) as obs:
            deps = EvalDeps(work=work, context=context)
            user_prompt = self._build_user_prompt(work, context)
            result = await self.agent.run(user_prompt, deps=deps)
            output = result.output
            usage = result.usage()

            obs.update(
                output={
                    "is_interesting": output.is_interesting,
                    "relevance_score": output.relevance_score,
                    "reasoning": output.reasoning,
                    "key_insights": output.key_insights,
                },
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
                level="DEFAULT",
            )
            # Ensure work_id and title are set correctly
            return PublicationEvaluation(
                work_id=work.work_id,
                title=work.title,
                is_interesting=output.is_interesting,
                relevance_score=output.relevance_score,
                reasoning=output.reasoning,
                key_insights=output.key_insights,
            )

    def _build_user_prompt(self, work: WorkEvalInput, context: EvalContext) -> str:
        abstract_text = work.abstract or "(nicht verfügbar)"
        kernkompetenzen = ", ".join(context.kernkompetenzen[:6])
        questions = "\n".join(f"  - {q}" for q in context.research_questions)
        year_text = f" ({work.publication_year})" if work.publication_year else ""

        if self._langfuse_prompt:
            try:
                msgs = self._langfuse_prompt.compile(
                    work_title=work.title,
                    work_year=year_text,
                    work_abstract=abstract_text,
                    gewerk_name=context.gewerk_name,
                    kernkompetenzen=kernkompetenzen,
                    research_questions=questions,
                )
                user_msg = next((m["content"] for m in msgs if m["role"] == "user"), None)
                if user_msg:
                    return user_msg
            except Exception:
                pass

        return f"""Bewerte, ob die folgende wissenschaftliche Publikation für das Gewerk relevant und interessant ist.

**Publikation:**
- Titel: {work.title}{year_text}
**Abstract:** {abstract_text}

**Gewerk:** {context.gewerk_name}
**Kernkompetenzen:** {kernkompetenzen}

**Forschungsfragen des Gewerks:**
{questions}

**Aufgabe:**
1. Ist diese Publikation interessant und relevant für das Gewerk? (is_interesting: true/false)
2. Bewerte die Relevanz auf einer Skala von 0.0 bis 1.0 (relevance_score)
3. Begründe deine Entscheidung kurz (reasoning)
4. Extrahiere 2–5 Key Insights als Stichworte (key_insights) — nur wenn is_interesting=true

Setze is_interesting=true nur wenn die Publikation direkt anwendbares Wissen für das Gewerk liefert."""

    def _register_prompts(self) -> None:
        @self.agent.system_prompt
        def system_prompt() -> str:
            if self._langfuse_prompt:
                try:
                    sys_content = next(
                        (m["content"] for m in self._langfuse_prompt.prompt if m["role"] == "system"),
                        None,
                    )
                    if sys_content:
                        return sys_content
                except Exception:
                    pass
            return (
                "Du bist ein Experte für Handwerksberufe und wissenschaftliche Literaturauswertung.\n"
                "Deine Aufgabe ist es, wissenschaftliche Publikationen auf ihre Relevanz "
                "für ein spezifisches Handwerksgewerk zu bewerten.\n\n"
                "Eine Publikation ist interessant wenn sie:\n"
                "- Direkt anwendbares Wissen für das Gewerk liefert\n"
                "- Neue Technologien oder Materialien für das Gewerk beschreibt\n"
                "- Arbeitssicherheit oder Gesundheitsschutz im Gewerk adressiert\n"
                "- Praxisrelevante Erkenntnisse enthält\n\n"
                "Sei präzise: Allgemeine Physik ist NICHT relevant für einen Maurer, "
                "nur weil Maurerei Physik beinhaltet. Es muss direkten Anwendungsbezug geben.\n\n"
                "Wenn kein Abstract vorhanden → bewerte konservativ anhand des Titels."
            )
