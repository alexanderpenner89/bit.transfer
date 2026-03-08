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


class EnrichedArticle(BaseModel):
    work_id: str
    title: str
    html: str                   # Full HTML article (800–1200 words)
    intro: str                  # Brief plain-text intro (for DossierAgent + CLI + excerpt)
    key_learnings: list[str]    # Kept for DossierAgent meta-synthesis


class DossierModel(BaseModel):
    gewerk_id: str
    gewerk_name: str
    research_questions: list[str]
    generated_at: str              # ISO 8601
    executive_summary: str
    articles: list[EnrichedArticle]
    key_findings: list[str]
