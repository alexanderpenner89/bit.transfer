from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MobiledocCard(BaseModel):
    version: str = "0.3.1"
    markups: list = Field(default_factory=list)
    atoms: list = Field(default_factory=list)
    cards: list = Field(default_factory=list)
    sections: list = Field(default_factory=list)


class PostTag(BaseModel):
    name: str


class PostAuthor(BaseModel):
    id: str


class PostInput(BaseModel):
    title: str
    html: str
    status: str = "published"  # draft | published | scheduled
    tags: list[PostTag] = Field(default_factory=list)
    authors: list[PostAuthor] | None = None
    custom_excerpt: str | None = None
    feature_image: str | None = None

    @classmethod
    def from_dict(
        cls,
        title: str,
        html: str,
        tags: list[str],
        status: str = "published",
        excerpt: str | None = None,
        author_id: str | None = None,
    ) -> "PostInput":
        return cls(
            title=title,
            html=html,
            status=status,
            tags=[PostTag(name=t) for t in tags],
            authors=[PostAuthor(id=author_id)] if author_id else None,
            custom_excerpt=excerpt,
        )


class EmailPostInput(PostInput):
    """Newsletter post: published to /newsletter/ and sent by email to all members."""

    email_segment: str = "all"  # "all" | "free" | "paid" | "none"
    newsletter: dict[str, str] | None = None  # {"id": "<newsletter_id>"}

    @classmethod
    def for_newsletter(
        cls,
        title: str,
        html: str,
        newsletter_id: str | None = None,
    ) -> "EmailPostInput":
        obj = cls(
            title=title,
            html=html,
            status="published",
            email_segment="all",
            tags=[PostTag(name="#newsletter")],
        )
        if newsletter_id:
            obj.newsletter = {"id": newsletter_id}
        return obj


class PostResponse(BaseModel):
    id: str
    title: str
    url: str
    status: str
    published_at: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PostResponse":
        return cls(
            id=data["id"],
            title=data["title"],
            url=data.get("url", ""),
            status=data.get("status", ""),
            published_at=data.get("published_at"),
        )
