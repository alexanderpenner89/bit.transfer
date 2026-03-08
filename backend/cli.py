"""CLI für den Gewerk-Research Agent.

Usage:
    python cli.py [--output FILE] [--verbose] [--show-queries] <profile.json>
"""
import asyncio
import uuid

import typer
from langfuse import observe, propagate_attributes
from rich.console import Console
from rich.panel import Panel

from agents import OrchestratorAgent, ProfileParsingAgent, ResearchQuestionAgent
from agents.aggregator import ResearchAggregator
from agents.publication_pipeline import PublicationPipeline
from config import settings
from tools.seen_works import SeenWorksRegistry
from schemas.publication_pipeline import DossierModel, GewerksContext, ResearchQuestionsModel
from schemas.research_pipeline import ResearchResult
from schemas.search_strategy import SearchStrategyModel

# Initialize Langfuse if enabled
if settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key:
    from langfuse import Langfuse
    langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_base_url,
    )
else:
    langfuse = None

app = typer.Typer(help="Gewerk-Research CLI - Generiert Forschungsstrategien für Handwerksgewerke")
console = Console()


def _handle_error(error: Exception, verbose: bool) -> None:
    """Zeigt Fehler schön formatiert an."""
    if verbose:
        console.print_exception()
    else:
        console.print(f"[red]Fehler:[/red] {error}")
    raise typer.Exit(code=1)


def _display_queries(queries: list[str], title: str, show_all: bool = False) -> None:
    """Zeigt Queries an, optional alle oder gekürzt."""
    console.print(f"\n[bold]{title}:[/bold] {len(queries)}")

    display_count = len(queries) if show_all else min(5, len(queries))
    for i, q in enumerate(queries[:display_count], 1):
        console.print(f"  {i}. {q}")

    if not show_all and len(queries) > display_count:
        console.print(f"  ... und {len(queries) - display_count} weitere (verwende --show-queries für alle)")


def _display_strategy(strategy: SearchStrategyModel, show_queries: bool = False) -> None:
    """Zeigt die generierte Strategie schön formatiert an."""
    _display_queries(strategy.semantic_queries_en, "Semantic Queries (EN)", show_queries)
    _display_queries(strategy.boolean_queries_de, "Boolean Queries (DE)", show_queries)
    _display_queries(strategy.boolean_queries_en, "Boolean Queries (EN)", show_queries)


def _make_session_id(gewerk_id: str) -> str:
    return f"{gewerk_id}-{uuid.uuid4().hex[:8]}"


@observe(name="pipeline.generate")
async def _generate_strategy(profil, session_id: str) -> SearchStrategyModel:
    """Führt den OrchestratorAgent aus mit Langfuse Session-Tracing."""
    with propagate_attributes(session_id=session_id, user_id=profil.gewerk_id):
        orchestrator = OrchestratorAgent()
        return await orchestrator.generate(profil)


@observe(name="pipeline.research")
async def _run_research(
    profil,
    session_id: str,
    on_progress,
    max_topics: int | None = None,
    max_queries: int | None = None,
    skip_expansion: bool = False,
) -> tuple[SearchStrategyModel, ResearchResult]:
    """Führt die vollständige Research-Pipeline aus mit Langfuse Session-Tracing."""
    with propagate_attributes(session_id=session_id, user_id=profil.gewerk_id):
        strategy = await _generate_strategy(profil, session_id=session_id)
        aggregator = ResearchAggregator(
            on_progress=on_progress,
            max_topics=max_topics,
            max_queries=max_queries,
            skip_expansion=skip_expansion,
        )
        result = await aggregator.run(strategy, profil)
    return strategy, result


@app.command()
def generate(
    profile_path: str = typer.Argument(..., help="Pfad zur Profil-JSON-Datei"),
    output: str | None = typer.Option(None, "--output", "-o", help="Ausgabedatei (optional)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaillierte Fehlermeldungen"),
    show_queries: bool = typer.Option(False, "--show-queries", "-q", help="Zeige alle Queries (nicht nur die ersten 5)"),
) -> None:
    """Generiert eine Forschungsstrategie aus einem Gewerks-Profil."""
    try:
        # Profil laden
        console.print(f"[dim]Lade Profil aus:[/dim] {profile_path}")
        parser = ProfileParsingAgent()
        profil = parser.parse_file(profile_path)

        console.print(Panel.fit(
            f"[bold]{profil.gewerk_name}[/bold]\n"
            f"ID: {profil.gewerk_id}\n"
            f"HWO-Anlage: {profil.hwo_anlage}",
            title="Gewerks-Profil",
            border_style="blue"
        ))

        session_id = _make_session_id(profil.gewerk_id)
        console.print(f"[dim]Session ID: {session_id}[/dim]")

        # Strategie generieren
        console.print("\n[yellow]Generiere Forschungsstrategie...[/yellow]")
        strategy = asyncio.run(_generate_strategy(profil, session_id=session_id))

        # Anzeigen
        console.print("\n[bold green]✓ Strategie generiert![/bold green]\n")
        _display_strategy(strategy, show_queries)

        # Optional: Speichern
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(strategy.model_dump_json(indent=2))
            console.print(f"\n[green]Gespeichert nach:[/green] {output}")

    except FileNotFoundError:
        _handle_error(f"Profil-Datei nicht gefunden: {profile_path}", verbose)
    except Exception as e:
        _handle_error(e, verbose)


def _display_research_result(result: ResearchResult) -> None:
    """Zeigt das Forschungsergebnis zusammenfassend an."""
    console.print(f"\n[bold]Exploration works:[/bold] {len(result.exploration_works)}")
    console.print(f"[bold]Relevant topics:[/bold] {len(result.relevant_topics)}")
    for t in result.relevant_topics:
        mark = "[green]✓[/green]" if t.is_relevant else "[red]✗[/red]"
        console.print(f"  {mark} {t.display_name} (confidence: {t.confidence:.0%})")

    console.print(f"\n[bold]Precision works:[/bold] {len(result.precision_works)}")
    for w in result.precision_works[:5]:
        console.print(f"  • {w.title[:80]} ({w.publication_year}, {w.citation_count} citations)")
    if len(result.precision_works) > 5:
        console.print(f"  ... and {len(result.precision_works) - 5} more")

    console.print(f"\n[bold]Expanded works (citations):[/bold] {len(result.expanded_works)}")


@app.command()
def research(
    profile_path: str = typer.Argument(..., help="Pfad zur Profil-JSON-Datei"),
    output: str | None = typer.Option(None, "--output", "-o", help="Ausgabedatei für ResearchResult (JSON)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaillierte Fehlermeldungen"),
) -> None:
    """Führt die vollständige Research-Pipeline aus: Profil → Strategie → Literaturrecherche."""
    try:
        console.print(f"[dim]Lade Profil aus:[/dim] {profile_path}")
        parser = ProfileParsingAgent()
        profil = parser.parse_file(profile_path)

        console.print(Panel.fit(
            f"[bold]{profil.gewerk_name}[/bold]\n"
            f"ID: {profil.gewerk_id}\n"
            f"HWO-Anlage: {profil.hwo_anlage}",
            title="Gewerks-Profil",
            border_style="blue"
        ))

        session_id = _make_session_id(profil.gewerk_id)
        console.print(f"[dim]Session ID: {session_id}[/dim]")

        async def _run() -> tuple[SearchStrategyModel, ResearchResult]:
            console.print("\n[yellow]Schritt 1/2: Generiere Suchstrategie (LLM)...[/yellow]")
            console.print("\n[yellow]Schritt 2/2: Research-Pipeline...[/yellow]")
            return await _run_research(profil, session_id=session_id, on_progress=console.print)

        strategy, result = asyncio.run(_run())

        console.print("[green]✓[/green] Suchstrategie generiert")
        _display_strategy(strategy)
        console.print("\n[bold green]✓ Research abgeschlossen![/bold green]")
        _display_research_result(result)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))
            console.print(f"\n[green]Gespeichert nach:[/green] {output}")

    except FileNotFoundError:
        _handle_error(f"Profil-Datei nicht gefunden: {profile_path}", verbose)
    except Exception as e:
        _handle_error(e, verbose)


def _display_dossier(dossier: DossierModel) -> None:
    """Zeigt das Dossier zusammenfassend an."""
    console.print(Panel.fit(
        f"[bold]{dossier.gewerk_name}[/bold]\n"
        f"Generiert: {dossier.generated_at}\n"
        f"Artikel: {len(dossier.articles)} | Key Findings: {len(dossier.key_findings)}",
        title="Dossier",
        border_style="green"
    ))

    console.print("\n[bold]Executive Summary:[/bold]")
    console.print(dossier.executive_summary)

    console.print(f"\n[bold]Key Findings ({len(dossier.key_findings)}):[/bold]")
    for i, finding in enumerate(dossier.key_findings, 1):
        console.print(f"  {i}. {finding}")

    console.print(f"\n[bold]Artikel ({len(dossier.articles)}):[/bold]")
    for art in dossier.articles:
        console.print(f"  • [bold]{art.title[:80]}[/bold]")
        console.print(f"    {art.intro[:120]}...")
        console.print(f"    Quellen: {len(art.sources)}")


@observe(name="pipeline.publish")
async def _run_publish(
    profil,
    session_id: str,
    on_progress,
    lite: bool = False,
    seen_work_ids: set[str] = frozenset(),
) -> tuple[DossierModel, ResearchResult]:
    """Führt die vollständige Publish-Pipeline aus mit Langfuse Session-Tracing."""
    with propagate_attributes(session_id=session_id, user_id=profil.gewerk_id):
        gewerk_context = GewerksContext(
            gewerk_id=profil.gewerk_id,
            gewerk_name=profil.gewerk_name,
            kernkompetenzen=profil.kernkompetenzen,
        )

        # Parallel: Research questions + Research pipeline
        on_progress("[dim]→ Starte Forschungsfragen-Generierung und Research parallel...[/dim]")
        research_question_agent = ResearchQuestionAgent()
        research_questions_task = asyncio.create_task(
            research_question_agent.generate(gewerk_context)
        )
        research_task = asyncio.create_task(
            _run_research(
                profil,
                session_id=session_id,
                on_progress=on_progress,
                max_topics=2 if lite else None,
                max_queries=3 if lite else None,
                skip_expansion=lite,
            )
        )
        research_questions, (_, research_result) = await asyncio.gather(
            research_questions_task, research_task
        )

        on_progress(f"[green]✓[/green] {len(research_questions.research_questions)} Forschungsfragen generiert")

        # Publication pipeline
        pipeline = PublicationPipeline(
            on_progress=on_progress,
            max_works=5 if lite else None,
            skip_work_ids=seen_work_ids,
        )
        dossier = await pipeline.run(research_result, research_questions, gewerk_context)
        return dossier, research_result


@app.command()
def publish(
    profile_path: str = typer.Argument(..., help="Pfad zur Profil-JSON-Datei"),
    output: str | None = typer.Option(None, "--output", "-o", help="Ausgabedatei für Dossier (JSON)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaillierte Fehlermeldungen"),
    lite: bool = typer.Option(False, "--lite", "-l", help="Reduzierter Lauf: max. 2 Topics, 3 Queries, 5 Works, keine Expansion"),
    incremental: bool = typer.Option(False, "--incremental", "-i", help="Überspringe bereits verarbeitete Works (Registry in data/seen_works/)"),
) -> None:
    """Vollständige Pipeline: Profil → Research → Publikationsbewertung → Dossier."""
    try:
        console.print(f"[dim]Lade Profil aus:[/dim] {profile_path}")
        parser = ProfileParsingAgent()
        profil = parser.parse_file(profile_path)

        console.print(Panel.fit(
            f"[bold]{profil.gewerk_name}[/bold]\n"
            f"ID: {profil.gewerk_id}\n"
            f"HWO-Anlage: {profil.hwo_anlage}",
            title="Gewerks-Profil",
            border_style="blue"
        ))

        session_id = _make_session_id(profil.gewerk_id)
        console.print(f"[dim]Session ID: {session_id}[/dim]")

        seen_work_ids: set[str] = frozenset()
        if incremental:
            registry = SeenWorksRegistry(profil.gewerk_id)
            seen_work_ids = registry.load()
            console.print(f"[dim]Incremental-Modus: {len(seen_work_ids)} bekannte Works geladen[/dim]")

        if lite:
            console.print("\n[yellow]Starte Publish-Pipeline (Lite-Modus: max. 2 Topics, 3 Queries, 5 Works)...[/yellow]")
        else:
            console.print("\n[yellow]Starte Publish-Pipeline...[/yellow]")
        dossier, research_result = asyncio.run(_run_publish(
            profil,
            session_id=session_id,
            on_progress=console.print,
            lite=lite,
            seen_work_ids=seen_work_ids,
        ))

        console.print("\n[bold green]✓ Dossier erstellt![/bold green]")
        _display_dossier(dossier)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(dossier.model_dump_json(indent=2))
            console.print(f"\n[green]Gespeichert nach:[/green] {output}")

        if incremental:
            registry = SeenWorksRegistry(profil.gewerk_id)
            new_ids = {w.work_id for w in research_result.precision_works + research_result.expanded_works}
            registry.save(new_ids)
            console.print(f"[dim]Registry aktualisiert: {len(new_ids)} neue Work-IDs gespeichert[/dim]")

    except FileNotFoundError:
        _handle_error(f"Profil-Datei nicht gefunden: {profile_path}", verbose)
    except Exception as e:
        _handle_error(e, verbose)


if __name__ == "__main__":
    app()
