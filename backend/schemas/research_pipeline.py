from __future__ import annotations

from pydantic import BaseModel


class TopicRef(BaseModel):
    topic_id: str
    display_name: str
    score: float


class WorkResult(BaseModel):
    work_id: str
    title: str
    abstract: str | None
    publication_year: int | None
    citation_count: int
    doi: str | None
    topics: list[TopicRef]
    referenced_work_ids: list[str]


class TopicCandidate(BaseModel):
    topic_id: str
    display_name: str
    frequency: int


class TopicEvaluation(BaseModel):
    topic_id: str
    display_name: str
    is_relevant: bool
    reasoning: str
    confidence: float


class ExplorationResult(BaseModel):
    gewerk_id: str
    works: list[WorkResult]
    topic_candidates: list[TopicCandidate]


class ResearchResult(BaseModel):
    gewerk_id: str
    exploration_works: list[WorkResult]
    precision_works: list[WorkResult]
    expanded_works: list[WorkResult]
    relevant_topics: list[TopicEvaluation]
