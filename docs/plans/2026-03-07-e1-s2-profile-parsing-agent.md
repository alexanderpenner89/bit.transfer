# E1-S2: Profile Parsing Agent — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a deterministic `ProfileParsingAgent` that reads JSON profiles from file or string and validates them against `GewerksProfilModel`, rejecting invalid input with precise field-level errors.

**Architecture:** `ProfileParsingAgent` wraps Pydantic v2's `model_validate_json()` — no LLM, no custom error logic. Pydantic's `ValidationError` propagates directly with field name, type, and value. Three real sample profiles (Elektrotechniker, Tischler, Maurer) sourced from berufe.net live in `backend/data/profiles/`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, uv

---

### Task 0: Git Branch anlegen

**Step 1: Branch erstellen**

```bash
git checkout -b feature/e1-s2-profile-parsing-agent
```

Expected: Switched to a new branch 'feature/e1-s2-profile-parsing-agent'

---

### Task 1: Verzeichnisstruktur anlegen

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/data/profiles/.gitkeep`
- Create: `backend/tests/__init__.py`

**Step 1: Verzeichnisse anlegen**

```bash
mkdir -p backend/agents backend/data/profiles backend/tests
touch backend/agents/__init__.py backend/tests/__init__.py backend/data/profiles/.gitkeep
```

**Step 2: Commit**

```bash
git add backend/agents/__init__.py backend/tests/__init__.py backend/data/profiles/.gitkeep
git commit -m "chore: add agents, data/profiles, tests directory structure"
```

---

### Task 2: Drei Gewerks-Profile von berufe.net recherchieren und als JSON speichern

Profile werden unter `backend/data/profiles/` gespeichert. Jede Datei muss gegen `GewerksProfilModel` valide sein.

**Files:**
- Create: `backend/data/profiles/elektrotechniker.json`
- Create: `backend/data/profiles/tischler.json`
- Create: `backend/data/profiles/maurer.json`

**Step 1: berufe.net recherchieren**

Besuche folgende URLs und extrahiere Inhalte:
- https://www.berufe.net/berufe/elektrotechniker/
- https://www.berufe.net/berufe/tischler/
- https://www.berufe.net/berufe/maurer/

**Step 2: elektrotechniker.json anlegen**

Datei `backend/data/profiles/elektrotechniker.json`:

```json
{
  "gewerk_id": "A_09_ELEKTROTECHNIKER",
  "gewerk_name": "Elektroniker für Energie- und Gebäudetechnik",
  "hwo_anlage": "A",
  "kernkompetenzen": [
    "Installation elektrischer Anlagen",
    "Gebäudeautomation",
    "Sicherheitstechnik",
    "Energieoptimierung"
  ],
  "taetigkeitsfelder": {
    "Installation": ["Elektroinstallation", "Netzwerktechnik", "Beleuchtungsanlagen"],
    "Wartung": ["Prüfung elektrischer Anlagen", "Fehlerdiagnose", "Instandhaltung"],
    "Planung": ["Schaltplanerstellung", "Materialauswahl", "Kostenvoranschlag"]
  },
  "techniken_manuell": [
    "Kabel verlegen",
    "Klemmen verbinden",
    "Leitungen konfektionieren",
    "Schalter und Steckdosen montieren"
  ],
  "techniken_maschinell": [
    "Bohren und Stemmen",
    "Kabelfräsen",
    "Messgeräte einsetzen",
    "Prüfgeräte bedienen"
  ],
  "techniken_oberflaeche": [
    "Abdichten von Kabeldurchführungen",
    "Brandschutzverguss",
    "Kabelkanalverkleidung"
  ],
  "werkstoffe": [
    "Kupferkabel",
    "Kunststoffrohr",
    "Schaltschrankmaterial",
    "LED-Leuchtmittel",
    "Sicherungsautomaten"
  ],
  "software_tools": [
    "EPLAN",
    "AutoCAD Electrical",
    "KNX-Programmiersoftware",
    "Fluke-Messgeräte-Software"
  ],
  "arbeitsbedingungen": [
    "Arbeit auf Leitern und Gerüsten",
    "Enge Schächte und Zwischendecken",
    "Wechselnde Baustellen",
    "Spannungsführende Umgebung"
  ]
}
```

**Step 3: tischler.json anlegen**

Datei `backend/data/profiles/tischler.json`:

```json
{
  "gewerk_id": "A_13_TISCHLER",
  "gewerk_name": "Tischler",
  "hwo_anlage": "A",
  "kernkompetenzen": [
    "Holzbearbeitung und -verarbeitung",
    "Möbel- und Innenausbau",
    "Fensterbau und Türenmontage",
    "Oberflächenbehandlung"
  ],
  "taetigkeitsfelder": {
    "Herstellung": ["Möbelfertigung", "Treppenbau", "Fensterbau", "Türenbau"],
    "Montage": ["Innenausbau", "Küchenmontage", "Ladeneinrichtung"],
    "Restaurierung": ["Antike Möbel", "Historische Fenster", "Denkmalpflege"]
  },
  "techniken_manuell": [
    "Hobeln",
    "Stemmen",
    "Verzapfen",
    "Dübeln",
    "Schleifen von Hand"
  ],
  "techniken_maschinell": [
    "CNC-Bearbeitung",
    "Formatkreissägen",
    "Abrichthobeln",
    "Fräsen",
    "Schleifen mit Bandschleifer"
  ],
  "techniken_oberflaeche": [
    "Lasieren",
    "Beizen",
    "Lackieren",
    "Ölen und Wachsen",
    "Furnier aufleimen"
  ],
  "werkstoffe": [
    "Massivholz",
    "MDF",
    "Spanplatte",
    "Sperrholz",
    "Furnier",
    "Holzwerkstoffe"
  ],
  "software_tools": [
    "AutoCAD",
    "Imos",
    "Cabinet Vision",
    "TimberStruct",
    "Woodwork for Inventor"
  ],
  "arbeitsbedingungen": [
    "Werkstattarbeit",
    "Montagearbeit auf Baustellen",
    "Staub- und Lärmbelastung",
    "Stehende Tätigkeit"
  ]
}
```

**Step 4: maurer.json anlegen**

Datei `backend/data/profiles/maurer.json`:

```json
{
  "gewerk_id": "A_01_MAURER",
  "gewerk_name": "Maurer und Betonbauer",
  "hwo_anlage": "A",
  "kernkompetenzen": [
    "Mauerwerksbau",
    "Betonbau und Stahlbetonbau",
    "Fassadenbau",
    "Putz- und Estricharbeiten"
  ],
  "taetigkeitsfelder": {
    "Herstellung": ["Mauern", "Betonieren", "Schalungsbau", "Fundamentbau"],
    "Instandhaltung": ["Sanierung", "Reparatur von Mauerwerk", "Abdichtungsarbeiten"],
    "Ausbau": ["Trennwände", "Schornsteinbau", "Kellerausbau"]
  },
  "techniken_manuell": [
    "Mauern mit Kelle",
    "Bewehrung biegen und verlegen",
    "Putzen von Hand",
    "Verfugen"
  ],
  "techniken_maschinell": [
    "Betonmischen",
    "Vibratoren bedienen",
    "Trennschleifer",
    "Bohrmaschinen und Stemmhammer"
  ],
  "techniken_oberflaeche": [
    "Verputzen",
    "Spachteln",
    "Glätten",
    "Abdichten mit Bitumenbahnen"
  ],
  "werkstoffe": [
    "Beton",
    "Mörtel",
    "Ziegel",
    "Kalksandstein",
    "Naturstein",
    "Stahlbewehrung"
  ],
  "software_tools": [
    "AutoCAD",
    "Revit",
    "BIM 360",
    "Allplan"
  ],
  "arbeitsbedingungen": [
    "Schwere körperliche Arbeit",
    "Freiluftarbeit bei jedem Wetter",
    "Staubbelastung",
    "Arbeit auf Gerüsten und in der Höhe"
  ]
}
```

**Step 5: Commit**

```bash
git add backend/data/profiles/
git commit -m "feat(data): add sample profiles for Elektrotechniker, Tischler, Maurer"
```

---

### Task 3: ProfileParsingAgent implementieren (TDD)

**Files:**
- Create: `backend/tests/test_profile_parser.py`
- Create: `backend/agents/profile_parser.py`

**Step 1: Failing tests schreiben**

Datei `backend/tests/test_profile_parser.py`:

```python
import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.profile_parser import ProfileParsingAgent
from schemas.gewerksprofil import GewerksProfilModel

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"


@pytest.fixture
def agent():
    return ProfileParsingAgent()


@pytest.fixture
def valid_maurer_json():
    return (PROFILES_DIR / "maurer.json").read_text(encoding="utf-8")


class TestParseString:
    def test_valid_profile_returns_model(self, agent, valid_maurer_json):
        result = agent.parse_string(valid_maurer_json)
        assert isinstance(result, GewerksProfilModel)
        assert result.gewerk_id == "A_01_MAURER"

    def test_missing_required_field_raises_validation_error(self, agent):
        invalid = json.dumps({"gewerk_id": "X_01_TEST"})
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_string(invalid)
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert "gewerk_name" in error_fields

    def test_wrong_hwo_anlage_value_raises_validation_error(self, agent, valid_maurer_json):
        data = json.loads(valid_maurer_json)
        data["hwo_anlage"] = "C"
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_string(json.dumps(data))
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert "hwo_anlage" in error_fields

    def test_empty_list_field_raises_validation_error(self, agent, valid_maurer_json):
        data = json.loads(valid_maurer_json)
        data["kernkompetenzen"] = []
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_string(json.dumps(data))
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert "kernkompetenzen" in error_fields

    def test_invalid_json_raises_validation_error(self, agent):
        with pytest.raises(ValidationError):
            agent.parse_string("{not valid json}")


class TestParseFile:
    def test_loads_maurer_profile(self, agent):
        path = PROFILES_DIR / "maurer.json"
        result = agent.parse_file(path)
        assert result.gewerk_id == "A_01_MAURER"

    def test_loads_tischler_profile(self, agent):
        path = PROFILES_DIR / "tischler.json"
        result = agent.parse_file(path)
        assert result.gewerk_id == "A_13_TISCHLER"

    def test_loads_elektrotechniker_profile(self, agent):
        path = PROFILES_DIR / "elektrotechniker.json"
        result = agent.parse_file(path)
        assert result.gewerk_id == "A_09_ELEKTROTECHNIKER"

    def test_nonexistent_file_raises_file_not_found(self, agent):
        with pytest.raises(FileNotFoundError):
            agent.parse_file("/nonexistent/path/profile.json")

    def test_accepts_string_path(self, agent):
        path = str(PROFILES_DIR / "maurer.json")
        result = agent.parse_file(path)
        assert isinstance(result, GewerksProfilModel)


class TestPerformance:
    def test_100_parses_under_100ms(self, agent, valid_maurer_json):
        start = time.perf_counter()
        for _ in range(100):
            agent.parse_string(valid_maurer_json)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"100 parses took {elapsed_ms:.1f}ms, expected <100ms"
```

**Step 2: Tests ausführen — müssen SCHEITERN**

```bash
cd backend && uv run pytest tests/test_profile_parser.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'agents.profile_parser'`

**Step 3: ProfileParsingAgent implementieren**

Datei `backend/agents/profile_parser.py`:

```python
from pathlib import Path

from schemas.gewerksprofil import GewerksProfilModel


class ProfileParsingAgent:
    """Deterministischer Agent zum Einlesen und Validieren von Gewerks-Profilen.

    Kein LLM. Reine Pydantic-Validierung.
    ValidationError propagiert direkt mit exaktem Feld und erwartetem Typ.
    """

    def parse_file(self, path: str | Path) -> GewerksProfilModel:
        """Liest eine JSON-Datei vom Dateisystem und validiert sie.

        Args:
            path: Dateipfad als str oder Path.

        Returns:
            Validiertes GewerksProfilModel.

        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
            ValidationError: Wenn das JSON nicht dem Schema entspricht.
        """
        file_path = Path(path)
        json_str = file_path.read_text(encoding="utf-8")
        return self.parse_string(json_str)

    def parse_string(self, json_str: str) -> GewerksProfilModel:
        """Parst und validiert ein JSON-Profil aus einem String.

        Args:
            json_str: JSON-String mit Profildaten.

        Returns:
            Validiertes GewerksProfilModel.

        Raises:
            ValidationError: Wenn das JSON nicht dem Schema entspricht,
                             mit exaktem Feld und erwartetem Typ.
        """
        return GewerksProfilModel.model_validate_json(json_str)
```

**Step 4: Tests ausführen — müssen BESTEHEN**

```bash
cd backend && uv run pytest tests/test_profile_parser.py -v
```

Expected: Alle Tests grün (PASSED)

**Step 5: Commit**

```bash
git add backend/agents/profile_parser.py backend/tests/test_profile_parser.py
git commit -m "feat(agents): implement ProfileParsingAgent with Pydantic validation (E1-S2)"
```

---

### Task 4: Design-Dokument committen

**Step 1: Commit**

```bash
git add docs/
git commit -m "docs: add E1-S2 design and implementation plan"
```

---

### Task 5: Verifikation

**Step 1: Alle Tests ausführen**

```bash
cd backend && uv run pytest tests/ -v --tb=short
```

Expected: Alle Tests PASSED

**Step 2: Schnellcheck Performance-Test**

```bash
cd backend && uv run pytest tests/test_profile_parser.py::TestPerformance -v -s
```

Expected: PASSED mit Timing weit unter 100ms

**Step 3: Branch-Status prüfen**

```bash
git log --oneline feature/e1-s2-profile-parsing-agent
```
