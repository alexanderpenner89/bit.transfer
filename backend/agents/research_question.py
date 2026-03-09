"""ResearchQuestionAgent — Generates research questions for a craft trade.

LLM-based (pydantic-ai). Input: GewerksContext (minimal).
Output: ResearchQuestionsModel with 3–5 research questions.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from config import fetch_prompt, get_langfuse, settings
from schemas.publication_pipeline import GewerksContext, ResearchQuestionsModel


@dataclass
class ResearchQuestionDeps:
    context: GewerksContext


class ResearchQuestionAgent:
    """Generates 3–5 current, practice-relevant research questions for a craft trade."""

    def __init__(self, model=None) -> None:
        if model is None:
            model = settings.build_model()

        self.agent: Agent[ResearchQuestionDeps, ResearchQuestionsModel] = Agent(
            model=model,
            output_type=ResearchQuestionsModel,
            deps_type=ResearchQuestionDeps,
            defer_model_check=True,
        )
        self._langfuse_prompt = fetch_prompt("research-question")
        self._register_prompts()

    async def generate(self, context: GewerksContext) -> ResearchQuestionsModel:
        """Generate research questions for the given craft trade context."""
        user_prompt = self._build_user_prompt(context) # bzw. profil
        with get_langfuse().start_as_current_observation(
            name="research_question.generate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={
                "gewerk_name": context.gewerk_name,
                "prompt": user_prompt,
            },
        ) as obs:
            deps = ResearchQuestionDeps(context=context)
            result = await self.agent.run(user_prompt, deps=deps)
            output = result.output
            usage = result.usage()

            obs.update(
                output={"question_count": len(output.research_questions)},
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
                level="DEFAULT",
            )
            # Ensure gewerk_id is set correctly
            return ResearchQuestionsModel(
                gewerk_id=context.gewerk_id,
                research_questions=output.research_questions,
                research_focus=output.research_focus,
            )

    def _build_user_prompt(self, context: GewerksContext) -> str:
        kernkompetenzen = ", ".join(context.kernkompetenzen[:6])

        if self._langfuse_prompt:
            try:
                msgs = self._langfuse_prompt.compile(
                    gewerk_name=context.gewerk_name,
                    gewerk_id=context.gewerk_id,
                    kernkompetenzen=kernkompetenzen,
                )
                user_msg = next((m["content"] for m in msgs if m["role"] == "user"), None)
                if user_msg:
                    return user_msg
            except Exception:
                pass

        return f"""Generiere 3–5 aktuelle, praxisrelevante Forschungsfragen für das folgende Handwerksgewerk.

**Gewerk:** {context.gewerk_name} (ID: {context.gewerk_id})
**Kernkompetenzen:** {kernkompetenzen}

**Anforderungen an die Forschungsfragen:**
- Fokus auf aktuelle Trends und Innovationen im Gewerk
- Neue Technologien und Materialien
- Arbeitssicherheit und Gesundheitsschutz
- Digitalisierung und neue Arbeitsmethoden
- Nachhaltigkeit und Umweltaspekte

Jede Frage soll:
1. Konkret und praxisorientiert sein
2. Mit wissenschaftlicher Literatur beantwortbar sein
3. Einen direkten Nutzen für das Gewerk haben

Gib außerdem einen kurzen research_focus (Ein-Satz-Zusammenfassung) an."""

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
                "Du bist ein Experte für Handwerksberufe und wissenschaftliche Forschung.\n"
                "Deine Aufgabe ist es, relevante Forschungsfragen für ein Handwerksgewerk zu generieren.\n\n"
                "Die Forschungsfragen sollen:\n"
                "- In wissenschaftlicher Literatur beantwortbar sein\n"
                "- Praktischen Mehrwert für das Gewerk haben\n"
                "- Aktuelle Herausforderungen und Chancen adressieren\n"
                "- Präzise und gut abgegrenzt sein\n\n"
                "Setze gewerk_id aus dem Kontext. Generiere exakt 3–5 Forschungsfragen."
            )
