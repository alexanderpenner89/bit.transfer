"""TopicEvaluatorAgent — Stage 2 of the research pipeline.

Pure LLM reasoning agent (no tools). Evaluates whether an OpenAlex topic is
relevant for a given craft trade profile (GewerksProfilModel).
"""
from __future__ import annotations

from dataclasses import dataclass

from config import fetch_prompt, get_langfuse, settings
from pydantic_ai import Agent, RunContext

from schemas.gewerksprofil import GewerksProfilModel
from schemas.research_pipeline import TopicCandidate, TopicEvaluation


@dataclass
class EvaluatorDeps:
    candidate: TopicCandidate
    profil: GewerksProfilModel


class TopicEvaluatorAgent:
    """Stage 2: LLM-based relevance judgment for a single topic candidate."""

    def __init__(self, model=None) -> None:
        if model is None:
            from config import settings
            model = settings.build_model()

        self.agent: Agent[EvaluatorDeps, TopicEvaluation] = Agent(
            model=model,
            output_type=TopicEvaluation,
            deps_type=EvaluatorDeps,
            defer_model_check=True,
        )
        self._langfuse_prompt = fetch_prompt("topic-evaluator")
        self._register_prompts()

    async def evaluate(
        self,
        candidate: TopicCandidate,
        profil: GewerksProfilModel,
    ) -> TopicEvaluation:
        """Evaluate whether a topic is relevant for the given craft trade profile."""
        with get_langfuse().start_as_current_observation(
            name="evaluator.evaluate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={
                "topic_id": candidate.topic_id,
                "topic_name": candidate.display_name,
                "gewerk": profil.gewerk_name,
            },
        ) as agent:
            deps = EvaluatorDeps(candidate=candidate, profil=profil)
            user_prompt = self._build_user_prompt(candidate, profil)
            result = await self.agent.run(user_prompt, deps=deps)
            output = result.output
            usage = result.usage()

            if output.confidence < 0.4:
                level, status_message = "WARNING", f"Low confidence: {output.confidence:.2f}"
            else:
                level, status_message = "DEFAULT", None

            agent.update(
                output={
                    "is_relevant": output.is_relevant,
                    "confidence": output.confidence,
                    "reasoning": output.reasoning,
                },
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
                level=level,
                **({"status_message": status_message} if status_message else {}),
            )
            return output

    def _build_user_prompt(
        self, candidate: TopicCandidate, profil: GewerksProfilModel
    ) -> str:
        kernkompetenzen = ", ".join(profil.kernkompetenzen[:6])
        werkstoffe = ", ".join(profil.werkstoffe[:5])
        techniken = ", ".join(
            (profil.techniken_manuell + profil.techniken_maschinell)[:6]
        )

        if self._langfuse_prompt:
            try:
                msgs = self._langfuse_prompt.compile(
                    topic_id=candidate.topic_id,
                    topic_display_name=candidate.display_name,
                    topic_frequency=str(candidate.frequency),
                    gewerk_name=profil.gewerk_name,
                    gewerk_id=profil.gewerk_id,
                    kernkompetenzen=kernkompetenzen,
                    werkstoffe=werkstoffe,
                    techniken=techniken,
                )
                user_msg = next((m["content"] for m in msgs if m["role"] == "user"), None)
                if user_msg:
                    return user_msg
            except Exception:
                pass

        return f"""Evaluate whether the following OpenAlex topic is relevant for this craft trade.

**Topic to evaluate:**
- ID: {candidate.topic_id}
- Name: {candidate.display_name}
- Frequency in search results: {candidate.frequency}

**Craft trade profile:**
- Trade: {profil.gewerk_name} (ID: {profil.gewerk_id})
- Core competencies: {kernkompetenzen}
- Materials: {werkstoffe}
- Techniques: {techniken}

Is this topic relevant for finding scientific literature useful to this trade?
Respond with a TopicEvaluation including your reasoning and confidence (0.0–1.0)."""

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
                "You are an expert in academic literature and German craft trades (Handwerk).\n"
                "Your task is to evaluate whether an OpenAlex research topic is relevant for a given trade.\n\n"
                "A topic is relevant if scientific literature in that area would provide practical value "
                "for the trade's work — covering materials, techniques, safety, digitalization, or "
                "regulatory compliance.\n\n"
                "Be precise: a topic about general physics is NOT relevant for a mason just because "
                "masonry involves physics. The topic must have direct applied relevance.\n\n"
                "Set is_relevant=True only if you are reasonably confident the topic yields useful literature."
            )
