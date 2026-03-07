"""OrchestratorAgent – E2-S2 + E2-S3.

Generates research questions and bilingual search strategies via Chain-of-Thought.
Uses pydantic-ai for type-safe LLM outputs.

Dependencies:
- Set PROVIDER and corresponding API key in backend/.env (see .env.example)
- For tests: pass model="test" or mock agent.run — no API call needed
"""
from langfuse import observe
from pydantic_ai import Agent, RunContext

from agents.keyword_extractor import KeywordExtractor
from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import SearchStrategyModel


class OrchestratorAgent:
    """Management-Agent der E2-Pipeline.

    Generates from a validated GewerksProfilModel:
    - 3–10 specific research questions (Chain-of-Thought)
    - Bilingual keyword queries (DE + EN)
    - Semantic search queries (EN)
    - Optional HyDE abstracts

    E2-S2 + E2-S3: LLM-based, uses pydantic-ai Agent.
    """

    def __init__(self, model=None) -> None:
        if model is None:
            from config import settings
            model = settings.build_model()
        self._keyword_extractor = KeywordExtractor()
        self.agent: Agent[GewerksProfilModel, SearchStrategyModel] = Agent(
            model=model,
            output_type=SearchStrategyModel,
            deps_type=GewerksProfilModel,
            defer_model_check=True,
        )
        self._register_system_prompts()

    @observe(name="orchestrator.generate", as_type="agent")
    @observe(name="orchestrator.generate", as_type="agent")
    async def generate(self, profil: GewerksProfilModel) -> SearchStrategyModel:
        """Generates a complete search strategy for the given profile."""
        user_prompt = self._build_user_prompt(profil)
        result = await self.agent.run(user_prompt, deps=profil)
        strategy = result.output

        # Ensure gewerk_id is correct and merge deterministic queries
        return SearchStrategyModel(
            **{
                **strategy.model_dump(),
                "gewerk_id": profil.gewerk_id,
                "keyword_queries_de": self._merge_de_queries(profil, strategy.keyword_queries_de),
            }
        )

    def _build_user_prompt(self, profil: GewerksProfilModel) -> str:
        """Builds user prompt with full profile context for Chain-of-Thought."""
        kernkompetenzen = ", ".join(profil.kernkompetenzen[:8])
        techniken = ", ".join(profil.techniken_manuell[:5] + profil.techniken_maschinell[:5])
        werkstoffe = ", ".join(profil.werkstoffe[:6])
        software = ", ".join(profil.software_tools[:4])

        return f"""Analysiere das folgende Handwerksgewerk und generiere eine wissenschaftliche Recherchestrategie.

**Gewerk:** {profil.gewerk_name} (ID: {profil.gewerk_id}, HWO-Anlage: {profil.hwo_anlage})

**Kernkompetenzen:** {kernkompetenzen}

**Techniken:** {techniken}

**Werkstoffe:** {werkstoffe}

**Software/Digitale Werkzeuge:** {software}

**Aufgabe (Chain-of-Thought):**
1. Überlege: Welche wissenschaftlichen Forschungsfelder sind für dieses Gewerk relevant?
2. Leite 3–10 spezifische Forschungsfragen ab, jede mit Bezug zu mindestens einem Profilfeld.
3. Generiere je 5–10 deutsche Keyword-Queries mit Boolean-Operatoren (AND, OR).
4. Übersetze und erweitere die Queries ins Englische (mindestens 2 EN-Varianten pro DE-Query).
5. Formuliere 2–3 englische Absatz-Descriptions für Semantic Search.

Antworte NUR mit dem strukturierten SearchStrategyModel-Output."""

    def _register_system_prompts(self) -> None:
        """Registers static and dynamic system prompts."""

        @self.agent.system_prompt
        def static_prompt() -> str:
            return """Du bist ein wissenschaftlicher Recherche-Spezialist für das deutsche Handwerk.
Deine Aufgabe: Aus einem Gewerks-Profil der Handwerksordnung (HWO) erstellst du
präzise Forschungsfragen und bilinguale Suchstrategien für akademische Datenbanken.

Prinzipien:
- Spezifität vor Allgemeinheit: Lieber enge, präzise Queries als breite
- Bilingualität: Jede deutsche Query hat mindestens 2 englische Varianten
- Feldabdeckung: Mindestens 80% der Profilfelder sind in Forschungsfragen abgedeckt
- Boolean-Syntax: AND für Eingrenzung, OR für Synonyme/Varianten"""

        @self.agent.system_prompt
        async def dynamic_prompt(ctx: RunContext[GewerksProfilModel]) -> str:
            profil = ctx.deps
            taetigkeiten = []
            for bereich, liste in profil.taetigkeitsfelder.items():
                taetigkeiten.extend([f"{bereich}: {t}" for t in liste[:3]])
            taetigkeiten_str = "; ".join(taetigkeiten[:6])
            return f"\nAktuelles Profil-Kontext:\nGewerk-ID: {profil.gewerk_id}\nTätigkeiten: {taetigkeiten_str}"

    def _merge_de_queries(
        self, profil: GewerksProfilModel, llm_queries: list[str]
    ) -> list[str]:
        """Merges deterministic KeywordExtractor queries with LLM queries."""
        deterministic = self._keyword_extractor.extract_keyword_queries(profil)
        all_queries = list(deterministic)
        for q in llm_queries:
            if q not in all_queries:
                all_queries.append(q)
        return all_queries
