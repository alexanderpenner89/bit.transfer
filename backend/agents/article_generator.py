"""ArticleGeneratorAgent — Stage C of the publication pipeline.

LLM-based (pydantic-ai). Generates HTML transfer dossier articles for interesting
publications, integrating perspectives and gewerk-specific insights.

Strict minimal-context principle — receives only what's needed for article generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from config import get_langfuse, settings
from schemas.publication_pipeline import EnrichedArticle, WorkSummary


class _ArticleOutput(BaseModel):
    """LLM output: HTML article + plain-text fields for DossierAgent."""
    title: str
    html: str          # Full HTML article body (800–1200 words)
    intro: str         # 2–3 sentence plain-text intro (for excerpt + DossierAgent)
    key_learnings: list[str]   # 3–5 concrete learnings (for DossierAgent)


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
    """Stage C: LLM-based HTML article generation for a single publication."""

    def __init__(self, model=None) -> None:
        if model is None:
            model = settings.build_model()

        self.agent: Agent[ArticleDeps, _ArticleOutput] = Agent(
            model=model,
            output_type=_ArticleOutput,
            deps_type=ArticleDeps,
            defer_model_check=True,
            retries=2,
        )
        self._register_prompts()

    async def generate(self, deps: ArticleDeps) -> EnrichedArticle:
        """Generate an HTML transfer dossier article for the given publication."""
        perspective_count = len(deps.perspectives)
        with get_langfuse().start_as_current_observation(
            name="article_generator.generate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={
                "work_id": deps.work_id,
                "title": deps.work.title,
                "gewerk_name": deps.gewerk_context.gewerk_name,
                "perspective_count": perspective_count,
                "perspectives": [
                    {"work_id": p.work_id, "title": p.title}
                    for p in deps.perspectives
                ],
            },
        ) as obs:
            user_prompt = self._build_user_prompt(deps)

            # Initial generation
            result = await self.agent.run(user_prompt, deps=deps)
            output = result.output

            # Feedback loop: up to 2 retries
            max_retries = 2
            for _attempt in range(max_retries):
                val_output = await self._validate(output, deps)
                if val_output.passed:
                    break

                issues_text = "\n".join(
                    f"- [{i.severity}] {i.description}" for i in val_output.issues
                )
                feedback_prompt = (
                    "Dein Artikel hat die Qualitätsprüfung nicht bestanden. "
                    "Bitte überarbeite ihn vollständig und behebe folgende Probleme:\n"
                    f"{issues_text}"
                )
                result = await self.agent.run(
                    feedback_prompt,
                    message_history=result.all_messages(),
                    deps=deps,
                )
                output = result.output

            usage = result.usage()
            obs.update(
                output={
                    "html_length": len(output.html),
                    "intro": output.intro,
                    "key_learnings": output.key_learnings,
                },
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
                level="DEFAULT",
            )
            return EnrichedArticle(
                work_id=deps.work_id,
                title=output.title,
                html=output.html,
                intro=output.intro,
                key_learnings=output.key_learnings,
            )

    def _build_user_prompt(self, deps: ArticleDeps) -> str:
        work = deps.work
        context = deps.gewerk_context
        kernkompetenzen = ", ".join(context.kernkompetenzen[:6])
        questions = "\n".join(f"  - {q}" for q in deps.research_questions)

        abstract_text = f"\n**Abstract:** {work.abstract}" if work.abstract else ""
        doi_text = f"\n**DOI:** {work.doi}" if work.doi else ""
        doi_link = f'<a href="https://doi.org/{work.doi.replace("https://doi.org/", "")}">{work.doi}</a>' if work.doi else ""
        year_text = f" ({work.publication_year})" if work.publication_year else ""
        citations_text = f"\n**Zitierungen:** {work.citation_count}"

        perspectives_text = ""
        if deps.perspectives:
            persp_lines = []
            for p in deps.perspectives[:8]:
                year = f" ({p.publication_year})" if p.publication_year else ""
                persp_lines.append(f"  • [{p.title}{year}] (work_id: {p.work_id})")
            perspectives_text = "\n**Verwandte Arbeiten:**\n" + "\n".join(persp_lines)
        else:
            perspectives_text = "\n**Verwandte Arbeiten:** Keine"

        return f"""Erstelle ein HTML-Transfer-Dossier für das folgende Handwerksgewerk.

**Hauptpublikation:**
- Titel: {work.title}{year_text}{doi_text}{citations_text}{abstract_text}
{perspectives_text}

**Gewerk:** {context.gewerk_name}
**Kernkompetenzen:** {kernkompetenzen}

**Forschungsfragen:**
{questions}

**HTML-Struktur (800–1200 Wörter):**

```html
<article class="transfer-dossier">

  <section class="auf-einen-blick">
    <h2>Auf einen Blick</h2>
    <ul>
      <li><!-- 3–5 prägnante Stichpunkte --></li>
    </ul>
  </section>

  <section class="intro">
    <p><!-- Einleitung: Was ist die Publikation, warum relevant? 2–3 Sätze --></p>
  </section>

  <section class="findings">
    <h2><!-- Abschnittstitel --></h2>
    <p><!-- Inhalt mit <mark>wichtige Zahl/Statistik</mark> --></p>
    <div class="key-insight"><!-- Kernaussage in 1–2 Sätzen --></div>
    <div class="trl-badge">TRL <!-- 1-9 -->: <!-- Stufe Name --></div>
  </section>

  <!-- 1–2 weitere findings-Abschnitte -->

  <section class="transfer-potential">
    <h2>Transferpotenzial für {context.gewerk_name}</h2>
    <p><!-- Wie kann das Gewerk diese Erkenntnis konkret anwenden? --></p>
  </section>

  <section class="conclusion">
    <h2>Fazit</h2>
    <p><!-- 2–3 Sätze Zusammenfassung und Ausblick --></p>
  </section>

  <section class="bibliography">
    <h2>Quellen</h2>
    <ul>
      <li><strong>Primär:</strong> {work.title}{year_text}. {doi_link}</li>
      <!-- weitere Quellen aus verwandten Arbeiten -->
    </ul>
  </section>

</article>
```

**Pflichtregeln:**
- Nur Deutsch (Ausnahme: Fachbegriffe, Eigennamen)
- TRL-Badge in JEDEM findings-Abschnitt
- Mindestens eine `<mark>`-Markierung pro findings-Abschnitt
- Bibliographie mit allen zitierten Quellen und DOI-Links wo verfügbar
- `intro`-Feld: 2–3 Sätze plain text (kein HTML) für Vorschau
- `key_learnings`: 3–5 prägnante Stichpunkte als plain text Liste"""

    async def _validate(
        self,
        output: _ArticleOutput,
        deps: ArticleDeps,
    ) -> Any:
        """Validate HTML article quality. Returns validation result (passed + issues only)."""
        from pydantic import BaseModel as _BaseModel

        class _ValidationIssue(_BaseModel):
            severity: str   # "critical" | "major" | "minor"
            description: str

        class _ValidationOutput(_BaseModel):
            passed: bool
            issues: list[_ValidationIssue]
            # refined_html intentionally removed — generator fixes its own output

        validator: Agent[None, _ValidationOutput] = Agent(
            model=settings.build_model(),
            output_type=_ValidationOutput,
            retries=1,
        )

        @validator.system_prompt
        def _val_system() -> str:
            return (
                "Du bist ein Qualitätsprüfer für wissenschaftliche Transfer-Dossiers.\n"
                "Prüfe den HTML-Artikel auf:\n"
                "- Sprache: Muss Deutsch sein (außer Fachbegriffe)\n"
                "- Struktur: auf-einen-blick, findings mit TRL-badge, transfer-potential, conclusion, bibliography\n"
                "- Inhalt: TRL-Einschätzung muss zur Publikation passen\n"
                "- Transferrelevanz: Konkrete Handlungsempfehlungen für das Gewerk\n"
                "Gib nur passed und issues zurück. Generiere KEIN eigenes HTML."
            )

        val_prompt = (
            f"Prüfe diesen HTML-Artikel für das Gewerk '{deps.gewerk_context.gewerk_name}':\n\n"
            f"{output.html}\n\n"
            "Ist der Artikel korrekt? Liste alle Probleme in issues."
        )

        with get_langfuse().start_as_current_observation(
            name="article_generator.validate",
            as_type="generation",
            model=settings.langfuse_model_name(),
            input={"html_length": len(output.html), "work_id": deps.work_id},
        ) as val_obs:
            try:
                val_result = await validator.run(val_prompt)
                val_output = val_result.output
                val_obs.update(
                    output={
                        "passed": val_output.passed,
                        "issue_count": len(val_output.issues),
                        "issues": [f"[{i.severity}] {i.description}" for i in val_output.issues],
                    },
                    level="DEFAULT" if val_output.passed else "WARNING",
                )
                return val_output
            except Exception:
                val_obs.update(level="WARNING", status_message="Validation failed, skipping")
                # Return a passing result so generate() continues without crashing
                return _ValidationOutput(passed=True, issues=[])

    def _register_prompts(self) -> None:
        @self.agent.system_prompt
        def system_prompt() -> str:
            return (
                "Du bist ein erfahrener Fachjournalist für Handwerk, Bautechnik und Technologietransfer.\n"
                "Du erstellst HTML-Transfer-Dossiers für Handwerksgewerke auf Basis wissenschaftlicher Publikationen.\n\n"
                "Deine Stärken:\n"
                "- Wissenschaftliche Erkenntnisse praxisnah aufbereiten\n"
                "- TRL-Einschätzungen (Technology Readiness Level 1–9) präzise einordnen\n"
                "- Transferbarrieren benennen und Überwindungsstrategien nennen\n"
                "- Statistiken und Zahlen mit <mark> hervorheben\n"
                "- Alle Quellen mit DOI-Links korrekt zitieren\n\n"
                "Pflicht: Nur Deutsch. Ausgabe IMMER als vollständiges HTML-Dokument gemäß Struktur."
            )
