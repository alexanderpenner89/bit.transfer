from typing import Literal

from pydantic import BaseModel, Field


class GewerksProfilModel(BaseModel):
    """
    Zentrales Datenmodell für ein Gewerks-Profil (Bauberuf).

    Validiert alle Felder eines Gewerks nach den Standards der Handwerks-Ordnung (HWO).
    Ermöglicht typ-sichere Datenübergabe an Agents.
    """

    gewerk_id: str = Field(
        ...,
        description="Eindeutige ID nach HWO",
        examples=["A_01_MAURER"],
    )

    gewerk_name: str = Field(
        ...,
        description="Offizieller Name des Gewerks",
        examples=["Maurer und Betonbauer"],
    )

    hwo_anlage: Literal["A", "B1", "B2"] = Field(
        ...,
        description="Regulatorische Stufe nach Handwerks-Ordnung Anlage",
        examples=["A"],
    )

    kernkompetenzen: list[str] = Field(
        default_factory=list,
        description="Liste der Kernkompetenzen des Gewerks",
        examples=[["Mauerwerksbau", "Betonbau", "Fassadenbau"]],
    )

    taetigkeitsfelder: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Tätigkeitsfelder unterteilt nach Bereichen",
        examples=[{
            "Herstellung": ["Mauern", "Betonieren"],
            "Instandhaltung": ["Reparatur", "Sanierung"],
        }],
    )

    techniken_manuell: list[str] = Field(
        default_factory=list,
        description="Manuelle Handwerkstechniken",
        examples=[["Stemmen", "Verzapfen", "Glattschlagen"]],
    )

    techniken_maschinell: list[str] = Field(
        default_factory=list,
        description="Maschinelle Bearbeitungstechniken",
        examples=[["CNC-Bearbeitung", "Bohren", "Sägen"]],
    )

    techniken_oberflaeche: list[str] = Field(
        default_factory=list,
        description="Oberflächenbehandlungstechniken",
        examples=[["Lasieren", "Beizen", "Lackieren"]],
    )

    werkstoffe: list[str] = Field(
        default_factory=list,
        description="Verarbeitete Materialien und Werkstoffe",
        examples=[["Massivholz", "Beton", "Naturstein"]],
    )

    software_tools: list[str] = Field(
        default_factory=list,
        description="Verwendete digitale Werkzeuge und Software",
        examples=[["AutoCAD", "BIM", "TimberStruct"]],
    )

    arbeitsbedingungen: list[str] = Field(
        default_factory=list,
        description="Physische und ergonomische Arbeitsbedingungen",
        examples=[["Schwere körperliche Arbeit", "Freiluftarbeit", "Höhenarbeit"]],
    )

    class Config:
        """Pydantic-Konfiguration"""

        populate_by_name = True
        str_strip_whitespace = True
        validate_assignment = True
