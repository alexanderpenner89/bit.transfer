"""CLI für den Gewerk-Research Agent.

Usage:
    python cli.py [--output FILE] [--verbose] [--show-queries] [--trace] <profile.json>
"""
import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents import OrchestratorAgent, ProfileParsingAgent
from config import settings
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
    # Forschungsfragen
    questions_table = Table(title="Forschungsfragen", show_header=True)
    questions_table.add_column("#", style="dim", width=3)
    questions_table.add_column("Frage", style="green")
    questions_table.add_column("Prio", style="cyan", width=4)

    for i, q in enumerate(strategy.forschungsfragen, 1):
        star = "★" if q.prioritaet == 1 else ""
        questions_table.add_row(str(i), q.frage, f"{q.prioritaet}{star}")

    console.print(questions_table)

    # Keyword Queries
    _display_queries(strategy.keyword_queries_de, "Deutsche Queries", show_queries)
    _display_queries(strategy.keyword_queries_en, "Englische Queries", show_queries)
    _display_queries(strategy.semantic_queries_en, "Semantic Queries (EN)", show_queries)


async def _generate_strategy(profil, use_trace: bool = False) -> tuple[SearchStrategyModel, str | None]:
    """Führt den OrchestratorAgent aus, optional mit Langfuse Tracing."""
    orchestrator = OrchestratorAgent()
    if use_trace and langfuse:
        with langfuse.start_as_current_span(name="cli.generate") as span:
            span.update(input=profil.model_dump())
            trace_id = langfuse.get_current_trace_id()
            result = await orchestrator.generate(profil)
            span.update(output=result.model_dump())
            return result, trace_id
    return await orchestrator.generate(profil), None


@app.command()
def generate(
    profile_path: str = typer.Argument(..., help="Pfad zur Profil-JSON-Datei"),
    output: str | None = typer.Option(None, "--output", "-o", help="Ausgabedatei (optional)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaillierte Fehlermeldungen"),
    show_queries: bool = typer.Option(False, "--show-queries", "-q", help="Zeige alle Queries (nicht nur die ersten 5)"),
    trace: bool = typer.Option(False, "--trace", "-t", help="Aktiviere Langfuse Tracing für diesen Aufruf"),
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

        # Strategie generieren
        console.print("\n[yellow]Generiere Forschungsstrategie...[/yellow]")
        strategy, trace_id = asyncio.run(_generate_strategy(profil, use_trace=trace))
        if trace_id:
            console.print(f"[dim]Trace ID: {trace_id}[/dim]")

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


if __name__ == "__main__":
    app()
