# E1-S2: Profile Parsing Agent — Design

**Story:** Als System möchte ich JSON-Dateien einlesen und gegen das Schema validieren, damit fehlerhafte Profile sofort mit präzisen Fehlermeldungen abgelehnt werden.

**Priorität:** P0 / M1 / 2 SP

---

## Architektur

Klasse `ProfileParsingAgent` in `backend/agents/profile_parser.py`.

Pydantic v2 `model_validate_json()` übernimmt Parsing und Validierung in einem Schritt — kein LLM, rein deterministisch, ~1ms pro Profil.

## Struktur

```
backend/
  agents/
    __init__.py
    profile_parser.py
  data/
    profiles/
      elektrotechniker.json
      tischler.json
      maurer.json
  tests/
    test_profile_parser.py
```

## API

```python
class ProfileParsingAgent:
    def parse_file(self, path: str | Path) -> GewerksProfilModel
    def parse_string(self, json_str: str) -> GewerksProfilModel
```

- `parse_file` liest Datei via `Path.read_text()`, delegiert an `parse_string`
- `parse_string` ruft `GewerksProfilModel.model_validate_json()` auf
- `ValidationError` von Pydantic propagiert direkt — enthält Feld, Wert, erwarteten Typ
- `FileNotFoundError` / `JSONDecodeError` propagieren ebenfalls unverändert

## Fehlerverhalten

Pydantic v2 `ValidationError` gibt bei Fehlern exakt an:
- Feldname (`.loc`)
- Fehlermeldung (`.msg`)
- Eingabewert (`.input`)
- Fehlertyp (`.type`)

Kein Wrapping oder eigene Exceptions nötig.

## Performance

Pydantic v2 nutzt Rust-basiertes `pydantic-core` — Validierung ist <1ms pro Profil, weit unter der 100ms-Grenze.

## Tests

- Valides Profil via Datei laden
- Valides Profil via String laden
- Invalides JSON (fehlendes Pflichtfeld) → `ValidationError` mit korrektem Feld
- Falscher Typ → `ValidationError` mit korrektem Feld
- Nicht-existierende Datei → `FileNotFoundError`
- Performance: 100 Durchläufe < 100ms gesamt
