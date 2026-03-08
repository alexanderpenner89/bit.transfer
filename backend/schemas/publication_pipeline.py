"""Schemas for the publication pipeline (research questions → dossier)."""
from __future__ import annotations

from pydantic import BaseModel


class ResearchQuestionsModel(BaseModel):
    gewerk_id: str
    research_questions: list[str]  # 3-5 konkrete Forschungsfragen
    research_focus: str            # Ein-Satz-Zusammenfassung


class GewerksContext(BaseModel):   # Minimaler Kontext für Downstream-Agents
    gewerk_id: str
    gewerk_name: str
    kernkompetenzen: list[str]


class PublicationEvaluation(BaseModel):
    work_id: str
    title: str
    is_interesting: bool
    relevance_score: float         # 0.0–1.0
    reasoning: str
    key_insights: list[str]        # Stichworte für Artikelgenerierung


class WorkSummary(BaseModel):      # Minimale Work-Darstellung für Perspektiven
    work_id: str
    title: str
    abstract: str | None
    doi: str | None
    publication_year: int | None


class PerspectiveResult(BaseModel):
    main_work_id: str
    related_works: list[WorkSummary]  # Ergänzende Perspektiven (5–10)


class ArticleSource(BaseModel):
    work_id: str
    title: str
    doi: str | None
    publication_year: int | None
    citation_type: str             # "primary" | "supporting" | "contrasting"


class EnrichedArticle(BaseModel):
    work_id: str
    title: str
    intro: str
    core_messages: list[str]
    key_learnings: list[str]
    gewerk_insights: str
    perspectives: str              # Unterstützende & gegensätzliche Perspektiven
    conclusion: str
    sources: list[ArticleSource]   # Quellenverweise


class DossierModel(BaseModel):
    gewerk_id: str
    gewerk_name: str
    research_questions: list[str]
    generated_at: str              # ISO 8601
    executive_summary: str
    articles: list[EnrichedArticle]
    key_findings: list[str]
