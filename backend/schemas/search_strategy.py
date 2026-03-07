from pydantic import BaseModel, Field


class ForschungsFrage(BaseModel):
    """Eine spezifische Forschungsfrage mit Bezug zum Gewerks-Profil."""

    model_config = {"str_strip_whitespace": True, "validate_assignment": True}

    frage: str = Field(..., description="Die Forschungsfrage als vollständiger Satz")
    bezug_profilfelder: list[str] = Field(
        ...,
        min_length=1,
        description="Profilfelder zu denen diese Frage gehört",
    )
    prioritaet: int = Field(
        ...,
        ge=1,
        le=3,
        description="Priorität 1 (hoch) bis 3 (niedrig)",
    )


class SearchStrategyModel(BaseModel):
    """Typsicheres Ausgabemodell des Orchestrator-Agents."""

    model_config = {"str_strip_whitespace": True, "validate_assignment": True}

    gewerk_id: str = Field(..., description="Referenz zum Quell-Profil")
    forschungsfragen: list[ForschungsFrage] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="3–10 spezifische Forschungsfragen",
    )
    keyword_queries_de: list[str] = Field(
        ...,
        min_length=1,
        description="Deutsche Keyword-Queries mit Bool-Operatoren (AND/OR)",
    )
    keyword_queries_en: list[str] = Field(
        ...,
        min_length=1,
        description="Englische Keyword-Queries mit Bool-Operatoren",
    )
    semantic_queries_en: list[str] = Field(
        ...,
        min_length=1,
        description="Englische Absatz-Descriptions für Semantic Search",
    )
    hyde_abstracts: list[str] = Field(
        default_factory=list,
        description="Hypothetische Abstracts für HyDE-Retrieval (optional)",
    )
    concept_filter_ids: list[str] | None = Field(
        default=None,
        description="OpenAlex Concept-IDs zur Eingrenzung (optional)",
    )
    max_results_per_query: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Zielanzahl Ergebnisse pro Query",
    )
