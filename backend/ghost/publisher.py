"""Convert DossierModel articles to Ghost posts."""
from __future__ import annotations

import logging
from datetime import date

from schemas.publication_pipeline import DossierModel, EnrichedArticle
from .client import GhostAdminClient
from .schemas import PostResponse

logger = logging.getLogger(__name__)


def _article_to_html(article: EnrichedArticle, gewerk_name: str) -> str:
    """Convert an EnrichedArticle to Ghost-compatible HTML."""
    core = "".join(f"<li>{m}</li>" for m in article.core_messages)
    learnings = "".join(f"<li>{l}</li>" for l in article.key_learnings)
    sources = "".join(
        f'<li><span class="citation-type citation-{s.citation_type}">{s.citation_type.title()}</span> '
        f'{s.title} ({s.publication_year or "n.d."})'
        + (f' — <a href="https://doi.org/{s.doi}">{s.doi}</a>' if s.doi else "")
        + "</li>"
        for s in article.sources
    )

    return f"""
<article class="enriched-article">
  <p class="article-intro">{article.intro}</p>

  <section class="core-messages">
    <h2>Kernaussagen</h2>
    <ul>{core}</ul>
  </section>

  <section class="key-learnings">
    <h2>Erkenntnisse für die Praxis</h2>
    <ul>{learnings}</ul>
  </section>

  <section class="gewerk-insights">
    <h2>Relevanz für {gewerk_name}</h2>
    <p>{article.gewerk_insights}</p>
  </section>

  <section class="perspectives">
    <h2>Perspektiven & Kontroversen</h2>
    <p>{article.perspectives}</p>
  </section>

  <section class="conclusion">
    <h2>Fazit</h2>
    <p>{article.conclusion}</p>
  </section>

  <section class="sources">
    <h2>Quellen</h2>
    <ul>{sources}</ul>
  </section>
</article>
"""


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
        html = _article_to_html(article, dossier.gewerk_name)
        excerpt = article.intro[:297] + "..." if len(article.intro) > 300 else article.intro

        try:
            response = await ghost_client.create_post(
                title=article.title,
                html=html,
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
