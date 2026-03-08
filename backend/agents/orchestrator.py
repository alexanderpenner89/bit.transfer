"""OrchestratorAgent – E2-S2 + E2-S3.

Generates bilingual OpenAlex search strategies via Chain-of-Thought.
Uses pydantic-ai for type-safe LLM outputs and pydantic-ai-skills for
on-demand OpenAlex syntax rules.

Dependencies:
- Set PROVIDER and corresponding API key in backend/.env (see .env.example)
- For tests: pass model="test" or mock agent.run — no API call needed
"""
from pathlib import Path

from langfuse import observe
from pydantic_ai import Agent, RunContext
from pydantic_ai_skills import SkillsToolset

from schemas.gewerksprofil import GewerksProfilModel
from schemas.search_strategy import SearchStrategyModel

_SKILLS_DIR = Path(__file__).parent / "skills"


class OrchestratorAgent:
    """Management-Agent der E2-Pipeline.

    Generates from a validated GewerksProfilModel:
    - 1–2 semantic English paragraphs for vector search
    - 2–3 German Boolean queries (OpenAlex syntax)
    - 2–3 English Boolean queries (OpenAlex syntax)

    E2-S2 + E2-S3: LLM-based, uses pydantic-ai Agent with pydantic-ai-skills.
    """

    def __init__(self, model=None) -> None:
        if model is None:
            from config import settings
            model = settings.build_model()
        self.agent: Agent[GewerksProfilModel, SearchStrategyModel] = Agent(
            model=model,
            output_type=SearchStrategyModel,
            deps_type=GewerksProfilModel,
            defer_model_check=True,
        )
        self._register_system_prompts()

    @observe(name="orchestrator.generate", as_type="agent")
    async def generate(self, profil: GewerksProfilModel) -> SearchStrategyModel:
        """Generates a complete search strategy for the given profile."""
        user_prompt = self._build_user_prompt(profil)
        skills = SkillsToolset(directories=[str(_SKILLS_DIR)])
        result = await self.agent.run(user_prompt, deps=profil, toolsets=[skills])
        strategy = result.output

        # Ensure gewerk_id matches the input profile
        return SearchStrategyModel(
            **{
                **strategy.model_dump(),
                "gewerk_id": profil.gewerk_id,
            }
        )

    def _build_user_prompt(self, profil: GewerksProfilModel) -> str:
        """Builds user prompt with full profile context for Chain-of-Thought."""
        kernkompetenzen = ", ".join(profil.kernkompetenzen[:8])
        techniken = ", ".join(profil.techniken_manuell[:5] + profil.techniken_maschinell[:5])
        werkstoffe = ", ".join(profil.werkstoffe[:6])
        software = ", ".join(profil.software_tools[:4])

        return f"""Analysiere das folgende Handwerksgewerk und generiere eine präzise OpenAlex-Suchstrategie.

**Gewerk:** {profil.gewerk_name} (ID: {profil.gewerk_id}, HWO-Anlage: {profil.hwo_anlage})

**Kernkompetenzen:** {kernkompetenzen}

**Techniken:** {techniken}

**Werkstoffe:** {werkstoffe}

**Software/Digitale Werkzeuge:** {software}

**Aufgabe (Chain-of-Thought):**
1. Formuliere 1–2 englische Absatz-Descriptions für Semantic Search (50–100 Wörter, kein Boolean).
2. Generiere 2–3 breite deutsche Boolean-Queries in OpenAlex-Syntax (UPPERCASE AND/OR, Klammern).
3. Generiere 2–3 breite englische Boolean-Queries in OpenAlex-Syntax (UPPERCASE AND/OR, Klammern).

Lade den Skill 'openalex-query-generation' für detaillierte Syntaxregeln und Beispiele.
Antworte NUR mit dem strukturierten SearchStrategyModel-Output."""

    def _register_system_prompts(self) -> None:
        """Registers static and dynamic system prompts."""

        @self.agent.system_prompt
        def openalex_expert_prompt() -> str:
            return """Du bist ein Principal Data Engineer, spezialisiert auf die OpenAlex API.
Deine Aufgabe ist es, aus Handwerks-Gewerkebeschreibungen (HWO) hochpräzise Suchstrategien für wissenschaftliche Literatur zu generieren.

REGEL 1: Die semantische Suche (Semantic Queries)
- Generiere 1-2 zusammenhängende, fließende englische Absätze.
- Nutze akademisches Vokabular (z.B. "thermal bridge mitigation" statt "preventing cold spots").
- Nutze hier KEINE Boolean-Operatoren. Schreibe natürliche Sätze.

REGEL 2: Die Keyword-Suche (Boolean Queries)
Du musst die strikte OpenAlex-Syntax befolgen:
- UPPERCASE: Operatoren müssen zwingend als AND, OR, NOT geschrieben werden.
- KLAMMERN: Gruppiere Synonyme IMMER mit OR in Klammern, z.B. ("Mauerwerk" OR "Ziegel" OR "Kalksandstein").
- VERMEIDE LANGE AND-KETTEN: Verbinde maximal zwei bis drei Konzepte mit AND, sonst wird die Treffermenge null.
- PHRASEN: Nutze doppelte Anführungszeichen für exakte Begriffe, z.B. "Stahlbeton".
- PROXIMITY (Näherungssuche): Nutze die Tilde (~), um Wörter zu finden, die nahe beieinander stehen, z.B. "Dünnbettmörtel Verarbeitung"~3.
- WILDCARDS: Nutze das Sternchen (*) für Wortstämme, aber es MÜSSEN mindestens 3 Buchstaben davor stehen, z.B. Mauer*.

Lade bei Beginn den Skill 'openalex-query-generation' für detaillierte Beispiele."""

        @self.agent.system_prompt
        async def dynamic_prompt(ctx: RunContext[GewerksProfilModel]) -> str:
            profil = ctx.deps
            taetigkeiten = []
            for bereich, liste in profil.taetigkeitsfelder.items():
                taetigkeiten.extend([f"{bereich}: {t}" for t in liste[:3]])
            taetigkeiten_str = "; ".join(taetigkeiten[:6])
            return f"\nAktuelles Profil-Kontext:\nGewerk-ID: {profil.gewerk_id}\nTätigkeiten: {taetigkeiten_str}"
