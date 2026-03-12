"""
Beispiel: Nutzung des GewerksProfilModel für Agents

Dieses Beispiel zeigt, wie Agents typ-sicher mit validierten
Gewerks-Profilen arbeiten können.
"""

from schemas import GewerksProfilModel


def create_maurer_profil() -> GewerksProfilModel:
    """Erstellt ein validiertes Maurer-Profil."""
    return GewerksProfilModel(
        gewerk_id="A_01_MAURER",
        gewerk_name="Maurer und Betonbauer",
        hwo_anlage="A",
        kernkompetenzen=[
            "Mauerwerksbau",
            "Betonbau",
            "Fassadenbau",
            "Trockenbau",
        ],
        taetigkeitsfelder={
            "Herstellung": [
                "Mauern",
                "Betonieren",
                "Verputzen",
            ],
            "Instandhaltung": [
                "Reparatur",
                "Sanierung",
                "Restaurierung",
            ],
        },
        techniken_manuell=[
            "Stemmen",
            "Verzapfen",
            "Glattschlagen",
            "Kellen",
        ],
        techniken_maschinell=[
            "Betonmischer",
            "Mauersäge",
            "Rüttler",
        ],
        techniken_oberflaeche=[
            "Glasieren",
            "Spachteln",
        ],
        werkstoffe=[
            "Beton",
            "Mauerziegel",
            "Naturstein",
            "Mörtel",
        ],
        software_tools=[
            "AutoCAD",
            "BIM",
            "Allplan",
        ],
        arbeitsbedingungen=[
            "Schwere körperliche Arbeit",
            "Freiluftarbeit",
            "Höhenarbeit",
            "Staubbelastung",
        ],
    )


def agent_analyze_profil(profil: GewerksProfilModel) -> dict:
    """
    Beispiel-Agent-Funktion: Analysiert ein Gewerks-Profil.

    Durch Pydantic ist das Profil garantiert validiert und typsicher.
    """
    analysis = {
        "gewerk": profil.gewerk_name,
        "hwo_stufe": profil.hwo_anlage,
        "komplexitaet": len(profil.kernkompetenzen) * len(profil.taetigkeitsfelder),
        "digitalisierungsgrad": len(profil.software_tools),
        "koerperliche_belastung": "Schwere körperliche Arbeit" in profil.arbeitsbedingungen,
    }
    return analysis


def agent_validate_input(data: dict) -> GewerksProfilModel:
    """
    Beispiel-Agent-Funktion: Validiert Rohdaten und gibt
    ein typ-sicheres Objekt zurück.

    Args:
        data: Rohdaten (z.B. aus API-Response oder LLM-Output)

    Returns:
        Validiertes GewerksProfilModel

    Raises:
        ValidationError: Bei ungültigen Daten
    """
    return GewerksProfilModel.model_validate(data)


if __name__ == "__main__":
    # Beispielausführung
    profil = create_maurer_profil()
    print(f"Profil erstellt: {profil.gewerk_name}")
    print(f"HWO-Anlage: {profil.hwo_anlage}")

    analysis = agent_analyze_profil(profil)
    print(f"\nAnalyse: {analysis}")

    # Validierung von Rohdaten
    rohdaten = {
        "gewerk_id": "A_02_ZIMMERER",
        "gewerk_name": "Zimmerer",
        "hwo_anlage": "A",
        "kernkompetenzen": ["Holzbau", "Dachbau"],
        "techniken_manuell": ["Sägen", "Hobeln", "Stemmen"],
        "techniken_maschinell": ["Kreissäge", "Oberfräse"],
        "techniken_oberflaeche": ["Lasieren", "Ölen"],
        "werkstoffe": ["Vollholz", "Brettschichtholz", "OSB"],
        "software_tools": ["TimberStruct", "AutoCAD"],
        "arbeitsbedingungen": ["Freiluftarbeit", "Höhenarbeit"],
    }

    validiertes_profil = agent_validate_input(rohdaten)
    print(f"\nValidiertes Profil: {validiertes_profil.gewerk_name}")
