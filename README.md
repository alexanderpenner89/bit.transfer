# Bit-Transfer

[![Deploy](https://img.shields.io/badge/deploy-DigitalOcean-blue)](https://m.do.co/c)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Private-lightgrey)]()

> Automatisierte KI-Forschung für Handwerksgewerke — von der Profilanalyse bis zur Publikation.

Bit-Transfer ist eine modulare Plattform, die KI-Agenten nutzt, um Gewerksprofile zu analysieren, wissenschaftliche Forschung zu automatisieren und Ergebnisse für Content-Management-Systeme aufzubereiten.

![Architektur](docs/assets/architecture.png)

## Features

- **KI-gestützte Profilanalyse** — Extrahiert automatisch relevante Themen und Forschungsfragen aus Gewerksprofilen
- **Automatische Literaturrecherche** — Durchsucht OpenAlex (30M+ wissenschaftliche Werke) nach relevanten Publikationen
- **Pipeline-Monitoring** — Web-basiertes Dashboard zur Überwachung laufender Forschungsprozesse
- **Ghost CMS Integration** — Direkte Publikation der Ergebnisse
- **Langfuse Observability** — Vollständiges Tracing aller KI-Interaktionen

## Schnellstart

```bash
# Repository klonen
git clone <repo-url> && cd bit-transfer

# Backend einrichten
cd backend
uv sync

# Umgebungsvariablen konfigurieren
cp .env.example .env
# Provider und API-Key in .env konfigurieren (Standard: Ollama, kein Key nötig)

# Demo-Pipeline starten
uv run python cli.py fixtures/electrician-profile.json
```

## Systemarchitektur

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx (80)                           │
│  / → Ghost CMS (2368)                                       │
│  /devtools/ → DevTools API (8000)                         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌──────────┐        ┌──────────┐         ┌──────────┐
   │  Ghost   │        │ DevTools │         │  MySQL   │
   │   CMS    │        │   API    │         │          │
   └──────────┘        └────┬─────┘         └──────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌─────────┐  ┌──────────┐  ┌──────────┐
        │   CLI   │  │ Langfuse │  │ OpenAlex │
        └─────────┘  │  Cloud   │  │    API   │
                     └──────────┘  └──────────┘
```

## Installation

### Voraussetzungen

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — Python Package Manager
- Docker & Docker Compose (optional)

### Lokale Entwicklung

```bash
# Backend
$ cd backend
$ uv sync

# Mit Docker Compose (vollständiger Stack)
$ docker compose --profile ghost up -d
```

## Nutzung

### CLI

```bash
cd backend

# Grundlegende Nutzung
uv run python cli.py fixtures/electrician-profile.json

# Mit Optionen
uv run python cli.py \
  --output result.json \
  --verbose \
  --show-queries \
  fixtures/profile.json
```

### DevTools API

```bash
# Pipeline starten
curl -X POST https://<domain>/devtools/api/pipeline/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic <token>" \
  -d @fixtures/profile.json

# Status abfragen
curl https://<domain>/devtools/api/pipeline/{id}

# Live-Updates via SSE
curl https://<domain>/devtools/api/pipeline/{id}/sse
```

## Ghost CMS Setup

Ghost CMS wird für die Publikation von Forschungsergebnissen verwendet.

### Erstinstallation

```bash
# Mit Docker Compose starten
docker compose --profile ghost up -d

# Warte auf MySQL (erster Start dauert ca. 30s)
docker compose logs -f mysql

# Ghost ist dann verfügbar unter: http://localhost:2368
```

### Initialisierung

1. **Ghost Setup aufrufen**: `http://localhost:2368/ghost`
2. **Admin-Konto erstellen**: Folge dem Setup-Assistenten
3. **Theme aktivieren**:
   - Ghost Admin → Settings → Design → Change theme → Upload theme
   - ZIP der gewünschten Theme-Version unter Releases herunterladen und hochladen

### Themes

Die Ghost-Themes sind in eigenen Repositories gepflegt. Bei jedem Push auf `main` wird automatisch eine neue ZIP als Release-Asset erstellt.

| Theme | Repository | Beschreibung |
|-------|-----------|--------------|
| **bit.craft** | [alexanderpenner89/bit.craft](https://github.com/alexanderpenner89/bit.craft) | Strukturiert, inhaltsdicht, gewerkenah |
| **bit.clarity** | [alexanderpenner89/bit.clarity](https://github.com/alexanderpenner89/bit.clarity) | Apple-inspiriertes Editorial-Design |

### Routing-Konfiguration

Die Routing-Konfiguration wird über `ghost/routes.yaml` gesteuert:

```yaml
# Beispiel: Custom Routes für Gewerk-Seiten
routes:
  /gewerke/: collections.gewerke

collections:
  gewerke:
    permalink: /gewerke/{slug}/
    template: gewerk
```

### Ghost Umgebungsvariablen

| Variable | Beschreibung | Standard |
|----------|--------------|----------|
| `url` | Öffentliche URL | `https://<domain>` |
| `NODE_ENV` | Umgebung | `production` |
| `database__client` | Datenbank-Typ | `mysql` |
| `database__connection__host` | MySQL Host | `mysql` |
| `database__connection__user` | MySQL Benutzer | `root` |
| `database__connection__password` | MySQL Passwort | `ghostpass` |

### Ghost-KI Integration

Um KI-Funktionen in Ghost zu nutzen (z.B. für Artikelvorschläge oder Content-Optimierung):

1. **Custom Integration in Ghost anlegen**:
   - Ghost Admin → Settings → Integrations → Add custom integration
   - Name: "Bit-Transfer KI"
   - API-Key wird automatisch generiert

2. **API-Key konfigurieren**:
   ```bash
   # In .env (Backend)
   GHOST_API_URL=http://localhost:2368
   GHOST_API_KEY=<content-api-key>
   GHOST_ADMIN_API_KEY=<admin-api-key>
   ```

3. **Integration verwenden**:
   ```python
   # Beispiel: Artikel automatisch veröffentlichen
   from tools.ghost_integration import GhostPublisher

   publisher = GhostPublisher()
   publisher.publish_article(
       title="Ergebnisse der Forschung",
       content=research_results,
       tags=["Forschung", "KI"]
   )
   ```

## Deployment

### Produktion (DigitalOcean)

```bash
# Deployment wird automatisch bei Push auf main ausgelöst
git push origin main

# Manuelles Deployment
ssh root@<server-ip>
cd /opt/bit-transfer
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

**Infrastruktur:**
- **Server:** DigitalOcean Droplet (FRA1)
- **Domain:** In `docker-compose.prod.yml` konfigurieren
- **Secrets:** GitHub Actions verwendet `DO_SSH_PRIVATE_KEY`

## Konfiguration

### Umgebungsvariablen

Die vollständige Konfiguration erfolgt über `backend/.env` (aus `.env.example` kopieren).

### LLM-Provider

Über `PROVIDER` wird der aktive Anbieter gewählt. Nur der Key des gewählten Providers ist erforderlich.

| `PROVIDER`-Wert | API-Key Variable | Beschreibung |
|-----------------|------------------|--------------|
| `ollama` *(Standard)* | — (keiner) | Lokales Ollama, kein Key nötig |
| `anthropic` | `ANTHROPIC_API_KEY` | Claude (Anthropic) |
| `openai` | `OPENAI_API_KEY` | GPT-4o (OpenAI) |
| `gemini` | `GOOGLE_API_KEY` | Gemini (Google) |
| `openrouter` | `OPENROUTER_API_KEY` | OpenRouter (Multi-Provider-Proxy) |

### Weitere Variablen

| Variable | Beschreibung | Erforderlich |
|----------|--------------|--------------|
| `MYSQL_ROOT_PASSWORD` | Datenbank-Passwort | ✅ (Prod) |
| `LANGFUSE_PUBLIC_KEY` | Tracing: Public Key | ❌ |
| `LANGFUSE_SECRET_KEY` | Tracing: Secret Key | ❌ |
| `LANGFUSE_BASE_URL` | Tracing: Host URL | ❌ |

## Projektstruktur

```
bit-transfer/
├── backend/              # Python Backend (Pydantic AI, FastAPI)
│   ├── agents/          # KI-Agenten (Orchestrator, Parser, Research)
│   ├── devtools/        # FastAPI Server & Pipeline-Steuerung
│   ├── schemas/         # Pydantic Models
│   ├── tools/           # OpenAlex Integration
│   └── tests/           # Pytest Suite
├── ghost/               # CMS Konfiguration
├── nginx/               # Reverse Proxy Config
└── .github/workflows/    # CI/CD
```

> Ghost-Themes: [bit.craft](https://github.com/alexanderpenner89/bit.craft) · [bit.clarity](https://github.com/alexanderpenner89/bit.clarity)

## API Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/pipeline/run` | POST | Neue Pipeline starten |
| `/api/pipeline/{id}` | GET | Status abfragen |
| `/api/pipeline/{id}/cancel` | POST | Pipeline abbrechen |
| `/api/pipelines` | GET | Alle Pipelines auflisten |
| `/api/pipeline/{id}/sse` | GET | Live-Updates (SSE) |

## Entwicklung

```bash
# Tests ausführen
cd backend
uv run pytest -m "not integration"  # Unit-Tests
uv run pytest                       # Alle Tests

# Code-Qualität
uv run mypy .                       # Typ-Checking
uv run ruff check .                 # Linting
```

## Technologien

- **[Pydantic AI](https://github.com/pydantic/pydantic-ai)** — Agenten-Framework
- **[Anthropic Claude](https://anthropic.com)** — LLM
- **[OpenAlex](https://openalex.org)** — Wissenschaftliche Datenbank
- **[Ghost CMS](https://ghost.org)** — Headless CMS
- **[Langfuse](https://langfuse.com)** — Observability
- **[FastAPI](https://fastapi.tiangolo.com)** — Web-Framework

## Lizenz

Private — Alle Rechte vorbehalten.
