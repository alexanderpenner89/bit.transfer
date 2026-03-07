from pathlib import Path

from schemas.gewerksprofil import GewerksProfilModel


class ProfileParsingAgent:
    """Deterministischer Agent zum Einlesen und Validieren von Gewerks-Profilen.

    Kein LLM. Reine Pydantic-Validierung.
    ValidationError propagiert direkt mit exaktem Feld und erwartetem Typ.
    """

    def parse_file(self, path: str | Path) -> GewerksProfilModel:
        """Liest eine JSON-Datei vom Dateisystem und validiert sie.

        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
            ValidationError: Wenn das JSON nicht dem Schema entspricht.
        """
        file_path = Path(path)
        json_str = file_path.read_text(encoding="utf-8")
        return self.parse_string(json_str)

    def parse_string(self, json_str: str) -> GewerksProfilModel:
        """Parst und validiert ein JSON-Profil aus einem String.

        Raises:
            ValidationError: Wenn das JSON nicht dem Schema entspricht,
                             mit exaktem Feld und erwartetem Typ.
        """
        return GewerksProfilModel.model_validate_json(json_str)
