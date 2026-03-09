"""Convert DossierModel articles to Ghost posts."""
from __future__ import annotations

import logging

from schemas.publication_pipeline import DossierModel
from .client import GhostAdminClient
from .schemas import PostResponse

logger = logging.getLogger(__name__)


async def publish_dossier(
    dossier: DossierModel,
    ghost_client: GhostAdminClient,
    author_id: str | None = None,
    status: str = "published",
) -> list[PostResponse]:
    """Publish each EnrichedArticle in the dossier as a Ghost post.

    Returns list of PostResponse for each published article.
    """
    results: list[PostResponse] = []
    tags = [dossier.gewerk_name, "Forschung", "bit-transfer"]

    for article in dossier.articles:
        # Excerpt from plain-text intro (max 300 chars)
        excerpt = article.intro[:300].rstrip()
        if len(article.intro) > 300:
            excerpt += "…"

        try:
            response = await ghost_client.create_post(
                title=article.title,
                html=article.html,          # Use LLM-generated HTML directly
                tags=tags,
                status=status,
                excerpt=excerpt,
                author_id=author_id,
            )
            results.append(response)
            logger.info("Published: %s → %s", article.title, response.url)
        except Exception as exc:
            logger.error("Failed to publish '%s': %s", article.title, exc)

    return results
