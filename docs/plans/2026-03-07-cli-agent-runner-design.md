# CLI Agent Runner - Design Document

**Date:** 2026-03-07
**Status:** Approved
**Branch:** `feature/cli-agent-runner`

## Zusammenfassung

Ein CLI-Tool zum Starten des vollständigen Agenten-Workflows mit Live-Output und Streaming-Unterstützung.

## Anforderungen

1. **Gesamter Agent-Workflow**: Startet ProfileParsingAgent → OrchestratorAgent
2. **Einfaches Interface**: `python -m backend.cli [--output FILE] [--verbose] <profile.json>`
3. **Menschenlesbares Output**: Schöne Formatierung mit Tabellen und Panels
4. **Streaming-Output**: Token-für-Token-Anzeige während LLM-Generierung
5. **Optionale Dateiausgabe**: `--output FILE` speichert Ergebnis als JSON
6. **Fehlerbehandlung**: Exit-Codes + Traceback nur bei `--verbose`

## Architektur-Entscheidungen

### Gewählter Ansatz: Typer + Rich

| Aspekt | Entscheidung | Begründung |
|--------|-------------|------------|
| CLI-Framework | **Typer** | Type-Hint-basiert, passt zu pydantic, automatische Hilfe/Validierung |
| Output-Formatting | **Rich** | Exzellente Streaming-Visualisierung, Tabellen, Panels |
| Async-Handling | **anyio** | Typer's async-Support über anyio |

**Abgelehnte Alternativen:**
- Argparse: Zu viel Boilerplate, schlechte DX
- Click: Gut aber Typer moderner mit Type-Hints
- Standard-Library logging: Rich bietet bessere UX

## Komponenten

### 1. `backend/cli.py`
Haupt-CLI-Modul. Definiert:
- Entry-Point mit Typer
- Argumente: `profile_path` (JSON-Datei)
- Optionen: `--output`, `--verbose`
- Async-Runner für den Agent-Workflow

### 2. `backend/streaming.py`
Streaming-Output-Handler:
- Callback für pydantic-ai Token-Streaming
- Live-Formatierung mit Rich Console
- Progress-Indikatoren während LLM-Calls

### 3. `pyproject.toml`
Neue Dependencies:
```toml
dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
]
```

### 4. `backend/__main__.py`
Ermöglicht: `python -m backend`

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI Input                                                      │
│  python -m backend.cli maurer.json --output result.json         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│  ProfileParsingAgent.parse_file()                                │
│  → GewerksProfilModel                                             │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│  OrchestratorAgent.generate()                                    │
│  → Streaming-Output während LLM-Generierung                       │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│  Rich-Formatted Output                                            │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Forschungsfragen (3)                                       │  │
│  │  ┌─────────────────────────────────────────────────────┐    │  │
│  │  │ 1. Wie beeinflusst BIM den Mauerwerksbau?          │ ★ │  │
│  │  └─────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Keyword-Queries (DE)                                         │  │
│  │  ("Mauerwerk" AND "BIM") OR ("Digitalisierung" AND "Bau")  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│  Optional: JSON-Output zu --output FILE                           │
└───────────────────────────────────────────────────────────────────┘
```

## Fehlerbehandlung

| Szenario | Verhalten | Exit-Code |
|----------|-----------|-----------|
| Datei nicht gefunden | Fehlermeldung + Exit | 1 |
| Invalides JSON | Validierungsfehler + Exit | 1 |
| API-Fehler (LLM) | Fehlermeldung + Traceback (mit --verbose) | 2 |
| Erfolg | Output + Exit | 0 |

## Abhängigkeiten

Neue Dependencies:
- `typer>=0.15.0` - CLI-Framework
- `rich>=13.9.0` - Terminal-Formatting

Bestehende Dependencies (keine Änderung):
- `pydantic-ai>=0.0.36`
- `pydantic>=2.0.0`

## Tests

Teststrategie:
1. **Unit Tests**: CLI-Argument-Parsing (mit Typer's CliRunner)
2. **Integration Tests**: End-to-End mit Mocked LLM
3. **Snapshot Tests**: Output-Formatierung

## Nicht im Scope (YAGNI)

- Interaktive Prompts (noch nicht benötigt)
- Mehrere Agenten gleichzeitig
- Configuration-Files
- Logging zu Datei (nur stdout)

## Implementierung

Siehe zugehöriger Implementierungsplan: `2026-03-07-cli-agent-runner-impl.md`
