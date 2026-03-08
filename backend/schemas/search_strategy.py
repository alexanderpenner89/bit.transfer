from pydantic import BaseModel, Field


class SearchStrategyModel(BaseModel):
    """Typsicheres Ausgabemodell des Orchestrator-Agents."""

    model_config = {"str_strip_whitespace": True, "validate_assignment": True}

    gewerk_id: str = Field(..., description="Referenz zum Quell-Profil")
    semantic_queries_en: list[str] = Field(
        ..., min_length=3, max_length=10,
        description="5–10 kurze englische Phrasen (je 5–15 Wörter), keyword-fokussiert, keine Boolean-Operatoren, kein Fließtext"
    )
    boolean_queries_de: list[str] = Field(
        ..., min_length=2, max_length=3,
        description="2–3 breite deutsche Keyword-Abfragen mit OR und AND (OpenAlex-Syntax)"
    )
    boolean_queries_en: list[str] = Field(
        ..., min_length=2, max_length=3,
        description="2–3 breite englische Keyword-Abfragen mit OR und AND (OpenAlex-Syntax)"
    )
