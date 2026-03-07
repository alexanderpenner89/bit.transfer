"""CLI für den Gewerk-Research Agent.

Usage:
    python cli.py [--output FILE] [--verbose] <profile.json>
"""
import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents import OrchestratorAgent, ProfileParsingAgent
from schemas.search_strategy import SearchStrategyModel

app = typer.Typer(help="Gewerk-Research CLI - Generiert Forschungsstrategien für Handwerksgewerke")
console = Console()


def _handle_error(error: Exception, verbose: bool) -> None:
    """Zeigt Fehler schön formatiert an."""
    if verbose:
        console.print_exception()
    else:
        console.print(f"[red]Fehler:[/red] {error}")
    raise typer.Exit(code=1)


def _display_strategy(strategy: SearchStrategyModel) -> None:
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
    console.print(f"\n[bold]Deutsche Queries:[/bold] {len(strategy.keyword_queries_de)}")
    for q in strategy.keyword_queries_de[:3]:
        console.print(f"  • {q}")
    if len(strategy.keyword_queries_de) > 3:
        console.print(f"  ... und {len(strategy.keyword_queries_de) - 3} weitere")

    console.print(f"\n[bold]Englische Queries:[/bold] {len(strategy.keyword_queries_en)}")


async def _generate_strategy(profil) -> SearchStrategyModel:
    """Führt den OrchestratorAgent aus."""
    orchestrator = OrchestratorAgent()
    return await orchestrator.generate(profil)


@app.command()
def generate(
    profile_path: str = typer.Argument(..., help="Pfad zur Profil-JSON-Datei"),
    output: str | None = typer.Option(None, "--output", "-o", help="Ausgabedatei (optional)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaillierte Fehlermeldungen"),
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
        strategy = asyncio.run(_generate_strategy(profil))

        # Anzeigen
        console.print("\n[bold green]✓ Strategie generiert![/bold green]\n")
        _display_strategy(strategy)

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
