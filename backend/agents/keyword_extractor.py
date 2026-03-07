from schemas.gewerksprofil import GewerksProfilModel


class KeywordExtractor:
    """Deterministischer Keyword-Extraktor für Gewerks-Profile.

    Generiert Boolean-Keyword-Queries direkt aus den Profilfeldern.
    Kein LLM, kein API-Call. Vollständig reproduzierbar.

    E2-S1: MVP-Implementierung (Meilenstein M1).
    """

    def extract_keyword_queries(self, profil: GewerksProfilModel) -> list[str]:
        """Extrahiert mindestens 5 Boolean-Queries aus dem Profil."""
        queries: list[str] = []
        queries.extend(self._queries_from_kernkompetenzen(profil))
        queries.extend(self._queries_from_techniken(profil))
        queries.extend(self._queries_from_werkstoffe(profil))
        queries.extend(self._queries_combined(profil))
        return queries

    def extract_queries_by_field(self, profil: GewerksProfilModel) -> dict[str, list[str]]:
        """Gibt Queries gruppiert nach Profilfeld zurück."""
        return {
            "kernkompetenzen": self._queries_from_kernkompetenzen(profil),
            "techniken_manuell": self._queries_from_techniken_manuell(profil),
            "techniken_maschinell": self._queries_from_techniken_maschinell(profil),
            "werkstoffe": self._queries_from_werkstoffe(profil),
        }

    def _queries_from_kernkompetenzen(self, profil: GewerksProfilModel) -> list[str]:
        kompetenzen = profil.kernkompetenzen
        if not kompetenzen:
            return []
        or_query = " OR ".join(f'"{k}"' for k in kompetenzen[:6])
        queries = [or_query]
        if len(kompetenzen) >= 2:
            queries.append(f'"{profil.gewerk_name}" AND "{kompetenzen[0]}"')
        return queries

    def _queries_from_techniken(self, profil: GewerksProfilModel) -> list[str]:
        queries = []
        queries.extend(self._queries_from_techniken_manuell(profil))
        queries.extend(self._queries_from_techniken_maschinell(profil))
        return queries

    def _queries_from_techniken_manuell(self, profil: GewerksProfilModel) -> list[str]:
        techniken = profil.techniken_manuell
        if not techniken:
            return []
        or_query = " OR ".join(f'"{t}"' for t in techniken[:5])
        return [f"({or_query}) AND Handwerk"]

    def _queries_from_techniken_maschinell(self, profil: GewerksProfilModel) -> list[str]:
        techniken = profil.techniken_maschinell
        if not techniken:
            return []
        or_query = " OR ".join(f'"{t}"' for t in techniken[:4])
        return [f"({or_query}) AND Maschine"]

    def _queries_from_werkstoffe(self, profil: GewerksProfilModel) -> list[str]:
        werkstoffe = profil.werkstoffe
        if not werkstoffe:
            return []
        or_query = " OR ".join(f'"{w}"' for w in werkstoffe[:5])
        return [f"({or_query}) AND Verarbeitung"]

    def _queries_combined(self, profil: GewerksProfilModel) -> list[str]:
        """Cross-Feld-Queries: Werkstoff AND Technik."""
        if not profil.werkstoffe or not profil.techniken_manuell:
            return []
        return [
            f'"{profil.werkstoffe[0]}" AND "{profil.techniken_manuell[0]}"',
            f'"{profil.gewerk_name}" AND Forschung',
        ]
