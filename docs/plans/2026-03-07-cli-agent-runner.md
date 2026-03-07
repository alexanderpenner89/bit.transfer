# CLI Agent Runner - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ein CLI-Tool zum Starten des vollständigen Agenten-Workflows mit Live-Streaming-Output

**Architecture:** Typer für CLI + Rich für Terminal-Formatting, Integration mit bestehendem pydantic-ai Agent

**Tech Stack:** Python 3.12, Typer, Rich, pydantic-ai, pytest

---

### Task 1: Dependencies hinzufügen

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Typer und Rich zu dependencies hinzufügen**

```toml
[project]
dependencies = [
    "anthropic>=0.84.0",
    "pydantic>=2.0.0",
    "pydantic-ai>=0.0.36",
    "pydantic-settings>=2.13.1",
    "typer>=0.15.0",
    "rich>=13.9.0",
]
```

**Step 2: Console-Script Entry-Point hinzufügen**

```toml
[project.scripts]
gewerk-research = "backend.cli:app"
```

**Step 3: Dependencies installieren**

```bash
cd /home/alex/dev/work/bit.transfer/backend && uv pip install -e ".[dev]"
```

**Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "deps: add typer and rich for CLI"
```

---

### Task 2: Basis CLI-Modul erstellen

**Files:**
- Create: `backend/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Failing Test für CLI-Entry-Point schreiben**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from backend.cli import app

runner = CliRunner()


def test_cli_without_args_shows_help():
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "Usage:" in result.output
```

**Step 2: Test laufen lassen - muss fehlschlagen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py -v
```
Expected: FAIL - "module not found" oder "cannot import name app"

**Step 3: Basis CLI-Modul implementieren**

```python
# backend/cli.py
"""CLI für den Gewerk-Research Agent.

Usage:
    python -m backend.cli [--output FILE] [--verbose] <profile.json>
"""
import typer
from rich.console import Console

app = typer.Typer(help="Gewerk-Research CLI - Generiert Forschungsstrategien für Handwerksgewerke")
console = Console()


@app.command()
def generate(
    profile_path: str = typer.Argument(..., help="Pfad zur Profil-JSON-Datei"),
    output: str | None = typer.Option(None, "--output", "-o", help="Ausgabedatei (optional)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaillierte Fehlermeldungen"),
) -> None:
    """Generiert eine Forschungsstrategie aus einem Gewerks-Profil."""
    console.print(f"[blue]Lade Profil:[/blue] {profile_path}")
    console.print(f"[green]Output:[/green] {output or 'stdout'}")
    console.print(f"[yellow]Verbose:[/yellow] {verbose}")


if __name__ == "__main__":
    app()
```

**Step 4: Test laufen lassen - muss passen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py -v
```
Expected: PASS

**Step 5: Manuelle CLI-Test**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m backend.cli --help
```
Expected: Hilfe-Text wird angezeigt

**Step 6: Commit**

```bash
git add backend/cli.py tests/test_cli.py
git commit -m "feat: add basic CLI structure with typer"
```

---

### Task 3: Profile-Parsing Integration

**Files:**
- Modify: `backend/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Test für Profile-Parsing schreiben**

```python
# tests/test_cli.py (append)
from unittest.mock import patch, MagicMock


def test_generate_with_valid_profile():
    mock_profil = MagicMock()
    mock_profil.gewerk_id = "TEST_01"
    mock_profil.gewerk_name = "Test Gewerk"

    with patch("backend.cli.ProfileParsingAgent") as mock_parser:
        mock_parser.return_value.parse_file.return_value = mock_profil

        result = runner.invoke(app, ["test_profile.json"])

    assert result.exit_code == 0
    assert "TEST_01" in result.output or "Lade Profil" in result.output
```

**Step 2: Test laufen lassen - muss fehlschlagen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py::test_generate_with_valid_profile -v
```
Expected: FAIL

**Step 3: Profile-Parsing zu CLI hinzufügen**

```python
# backend/cli.py (replace content)
"""CLI für den Gewerk-Research Agent.

Usage:
    python -m backend.cli [--output FILE] [--verbose] <profile.json>
"""
import typer
from rich.console import Console
from rich.panel import Panel

from agents import ProfileParsingAgent
from config import settings

app = typer.Typer(help="Gewerk-Research CLI - Generiert Forschungsstrategien für Handwerksgewerke")
console = Console()


def _handle_error(error: Exception, verbose: bool) -> None:
    """Zeigt Fehler schön formatiert an."""
    if verbose:
        console.print_exception()
    else:
        console.print(f"[red]Fehler:[/red] {error}")
    raise typer.Exit(code=1)


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

        # TODO: Orchestrator-Agent aufrufen
        console.print("[yellow]TODO: Orchestrator-Agent Integration[/yellow]")

    except FileNotFoundError as e:
        _handle_error(f"Profil-Datei nicht gefunden: {profile_path}", verbose)
    except Exception as e:
        _handle_error(e, verbose)


if __name__ == "__main__":
    app()
```

**Step 4: Test laufen lassen - muss passen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py -v
```
Expected: PASS

**Step 5: Manuelle Test mit echter Datei**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m backend.cli data/profiles/maurer.json
```
Expected: Profil-Informationen werden angezeigt

**Step 6: Commit**

```bash
git add backend/cli.py tests/test_cli.py
git commit -m "feat: add profile parsing to CLI"
```

---

### Task 4: OrchestratorAgent Integration

**Files:**
- Modify: `backend/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Test für Orchestrator Integration**

```python
# tests/test_cli.py (append)
import asyncio


def test_generate_calls_orchestrator():
    mock_profil = MagicMock()
    mock_profil.gewerk_id = "A_01_MAURER"
    mock_profil.gewerk_name = "Maurer"
    mock_profil.hwo_anlage = "A"

    mock_strategy = MagicMock()
    mock_strategy.model_dump_json.return_value = '{"gewerk_id": "A_01_MAURER"}'

    with patch("backend.cli.ProfileParsingAgent") as mock_parser, \
         patch("backend.cli.OrchestratorAgent") as mock_orch:
        mock_parser.return_value.parse_file.return_value = mock_profil
        mock_orch_instance = MagicMock()
        mock_orch_instance.generate = MagicMock(return_value=asyncio.Future())
        mock_orch_instance.generate.return_value.set_result(mock_strategy)
        mock_orch.return_value = mock_orch_instance

        result = runner.invoke(app, ["maurer.json"])

    assert result.exit_code == 0
    mock_orch_instance.generate.assert_called_once()
```

**Step 2: Test laufen lassen - muss fehlschlagen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py::test_generate_calls_orchestrator -v
```
Expected: FAIL

**Step 3: OrchestratorAgent Integration hinzufügen**

```python
# backend/cli.py (replace content)
"""CLI für den Gewerk-Research Agent.

Usage:
    python -m backend.cli [--output FILE] [--verbose] <profile.json>
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
```

**Step 4: Test laufen lassen - muss passen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cli.py tests/test_cli.py
git commit -m "feat: integrate OrchestratorAgent into CLI"
```

---

### Task 5: Streaming-Output Implementierung

**Files:**
- Create: `backend/streaming.py`
- Modify: `backend/cli.py`

**Step 1: Streaming-Handler erstellen**

```python
# backend/streaming.py
"""Streaming-Output Handler für LLM-Generierung."""
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner


class StreamingHandler:
    """Handhabt Streaming-Output von pydantic-ai Agenten."""

    def __init__(self, console: Console):
        self.console = console
        self._buffer = ""
        self._live: Live | None = None

    def on_token(self, token: str) -> None:
        """Wird bei jedem neuen Token aufgerufen."""
        self._buffer += token
        if self._live:
            self._live.update(Panel(
                self._buffer[-500:] + "▌",  # Letzte 500 Zeichen + Cursor
                title="LLM generiert...",
                border_style="yellow"
            ))

    def start(self) -> None:
        """Startet die Live-Anzeige."""
        self._live = Live(
            Panel("Warte auf LLM-Antwort...", title="Generierung", border_style="yellow"),
            console=self.console,
            refresh_per_second=10
        )
        self._live.start()

    def stop(self) -> None:
        """Stoppt die Live-Anzeige."""
        if self._live:
            self._live.stop()
            self._live = None

    def get_full_output(self) -> str:
        """Gibt den gesammelten Output zurück."""
        return self._buffer
```

**Step 2: Streaming zu CLI hinzufügen**

```python
# backend/cli.py - Änderungen in _generate_strategy()
from streaming import StreamingHandler

async def _generate_strategy(profil) -> SearchStrategyModel:
    """Führt den OrchestratorAgent aus mit Streaming."""
    handler = StreamingHandler(console)
    orchestrator = OrchestratorAgent()

    handler.start()
    try:
        # TODO: Wenn pydantic-ai Streaming unterstützt, hier registrieren
        # orchestrator.agent.on_token = handler.on_token
        strategy = await orchestrator.generate(profil)
    finally:
        handler.stop()

    return strategy
```

**Step 3: Commit**

```bash
git add backend/streaming.py backend/cli.py
git commit -m "feat: add streaming output handler for LLM generation"
```

---

### Task 6: Error Handling & Exit Codes verbessern

**Files:**
- Modify: `backend/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Test für Fehlerbehandlung**

```python
# tests/test_cli.py (append)
def test_file_not_found_error():
    result = runner.invoke(app, ["nonexistent.json"])
    assert result.exit_code == 1
    assert "nicht gefunden" in result.output or "not found" in result.output.lower()


def test_verbose_shows_traceback():
    result = runner.invoke(app, ["nonexistent.json", "--verbose"])
    assert result.exit_code == 1
    # Bei verbose sollte Traceback enthalten sein
    assert "Traceback" in result.output or "FileNotFoundError" in result.output
```

**Step 2: Tests laufen lassen - beide sollten passen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli.py -v
```
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add error handling tests for CLI"
```

---

### Task 7: __main__.py für Modul-Ausführung

**Files:**
- Create: `backend/__main__.py`

**Step 1: __main__.py erstellen**

```python
# backend/__main__.py
"""Ermöglicht: python -m backend"""
from backend.cli import app

if __name__ == "__main__":
    app()
```

**Step 2: Testen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m backend --help
```
Expected: Hilfe-Text wird angezeigt

**Step 3: Commit**

```bash
git add backend/__main__.py
git commit -m "feat: add __main__.py for module execution"
```

---

### Task 8: E2E Test mit Mock

**Files:**
- Create: `tests/test_cli_e2e.py`

**Step 1: E2E Test schreiben**

```python
# tests/test_cli_e2e.py
"""End-to-End Tests für CLI mit gemocktem LLM."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from typer.testing import CliRunner
from backend.cli import app

runner = CliRunner()


def test_e2e_full_workflow():
    """Testet den vollständigen Workflow mit gemocktem Orchestrator."""
    # Temporäre Profil-Datei erstellen
    profile_data = {
        "gewerk_id": "TEST_01",
        "gewerk_name": "Test Gewerk",
        "hwo_anlage": "A",
        "kernkompetenzen": ["Testen"],
        "taetigkeitsfelder": {"Herstellung": ["Test machen"]},
        "techniken_manuell": ["Handtest"],
        "techniken_maschinell": ["Maschinentest"],
        "techniken_oberflaeche": ["Oberflächentest"],
        "werkstoffe": ["Testmaterial"],
        "software_tools": ["TestTool"],
        "arbeitsbedingungen": ["Testbedingungen"]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(profile_data, f)
        profile_path = f.name

    try:
        # Mock-Strategie erstellen
        mock_strategy = MagicMock()
        mock_strategy.gewerk_id = "TEST_01"
        mock_strategy.forschungsfragen = []
        mock_strategy.keyword_queries_de = ["Test AND Query"]
        mock_strategy.keyword_queries_en = ["Test AND Query"]
        mock_strategy.semantic_queries_en = ["Test query description"]
        mock_strategy.model_dump_json.return_value = json.dumps({
            "gewerk_id": "TEST_01",
            "forschungsfragen": [],
            "keyword_queries_de": ["Test AND Query"],
            "keyword_queries_en": ["Test AND Query"],
            "semantic_queries_en": ["Test query description"]
        })

        with patch("backend.cli.OrchestratorAgent") as mock_orch_class:
            mock_orch = MagicMock()
            mock_orch.generate = AsyncMock(return_value=mock_strategy)
            mock_orch_class.return_value = mock_orch

            result = runner.invoke(app, [profile_path])

        assert result.exit_code == 0
        assert "Strategie generiert" in result.output

    finally:
        Path(profile_path).unlink()


def test_e2e_with_output_file():
    """Testet das Speichern in eine Datei."""
    profile_data = {
        "gewerk_id": "TEST_02",
        "gewerk_name": "Test Gewerk 2",
        "hwo_anlage": "A",
        "kernkompetenzen": ["Testen"],
        "taetigkeitsfelder": {},
        "techniken_manuell": ["Handtest"],
        "techniken_maschinell": ["Maschinentest"],
        "techniken_oberflaeche": ["Oberflächentest"],
        "werkstoffe": ["Testmaterial"],
        "software_tools": ["TestTool"],
        "arbeitsbedingungen": ["Testbedingungen"]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(profile_data, f)
        profile_path = f.name

    output_path = profile_path.replace(".json", "_output.json")

    try:
        mock_strategy = MagicMock()
        mock_strategy.model_dump_json.return_value = '{"test": true}'

        with patch("backend.cli.OrchestratorAgent") as mock_orch_class:
            mock_orch = MagicMock()
            mock_orch.generate = AsyncMock(return_value=mock_strategy)
            mock_orch_class.return_value = mock_orch

            result = runner.invoke(app, [profile_path, "--output", output_path])

        assert result.exit_code == 0
        assert Path(output_path).exists()
        assert "Gespeichert nach" in result.output

    finally:
        Path(profile_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)
```

**Step 2: Tests laufen lassen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli_e2e.py -v
```
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_cli_e2e.py
git commit -m "test: add E2E tests for CLI with mocked LLM"
```

---

### Task 9: README-Dokumentation aktualisieren

**Files:**
- Modify: `backend/README.md` (oder neu erstellen)

**Step 1: CLI-Usage zu README hinzufügen**

```markdown
## CLI Usage

### Generiere eine Forschungsstrategie

```bash
python -m backend.cli data/profiles/maurer.json
```

### Mit Ausgabedatei

```bash
python -m backend.cli data/profiles/maurer.json --output strategy.json
```

### Mit detaillierten Fehlermeldungen

```bash
python -m backend.cli data/profiles/maurer.json --verbose
```

### Hilfe

```bash
python -m backend.cli --help
```
```

**Step 2: Commit**

```bash
git add backend/README.md
git commit -m "docs: add CLI usage instructions"
```

---

### Task 10: Finale Überprüfung

**Step 1: Alle Tests laufen lassen**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m pytest tests/test_cli*.py -v
```
Expected: Alle Tests PASS

**Step 2: Manuelle CLI-Test mit echter Datei (nur Profil-Parsing)**

```bash
cd /home/alex/dev/work/bit.transfer/backend && python -m backend.cli data/profiles/maurer.json --output /tmp/test_strategy.json
```
Expected: Profil wird angezeigt, Fehler wegen fehlendem LLM-API-Key (oder Erfolg wenn Ollama läuft)

**Step 3: Code-Review mit Simplify**

```bash
skill: simplify
```

**Step 4: Finaler Commit**

```bash
git add .
git commit -m "feat: complete CLI agent runner implementation"
```

---

## Summary

Nach diesem Plan haben wir:

1. ✅ Typer + Rich als Dependencies
2. ✅ Basis CLI-Struktur mit Entry-Point
3. ✅ ProfileParsingAgent Integration
4. ✅ OrchestratorAgent Integration
5. ✅ Streaming-Output Handler
6. ✅ Fehlerbehandlung mit Exit-Codes
7. ✅ `python -m backend` Support
8. ✅ E2E Tests mit Mocks
9. ✅ Dokumentation

**Nutzung:**
```bash
python -m backend.cli data/profiles/maurer.json --output strategy.json
```
