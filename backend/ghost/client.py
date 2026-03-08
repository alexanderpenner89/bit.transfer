from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt

from .schemas import EmailPostInput, PostInput, PostResponse


class GhostAdminClient:
    """Async client for the Ghost Admin API v5 using JWT authentication.

    Ghost Admin API Key format: ``<key_id>:<hex_secret>``
    The ``key_id`` goes in the JWT ``kid`` header; ``hex_secret`` is decoded
    with ``bytes.fromhex()`` and used as the HMAC-SHA256 signing key.
    """

    def __init__(self, api_key: str, ghost_url: str) -> None:
        if not api_key:
            raise ValueError(
                "GHOST_ADMIN_API_KEY is required. "
                "Create a custom integration in Ghost → Settings → Integrations."
            )
        parts = api_key.split(":")
        if len(parts) != 2:
            raise ValueError("GHOST_ADMIN_API_KEY must be in format <id>:<hex-secret>")
        self._key_id, self._secret_hex = parts
        self._base_url = ghost_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    # ── HTTP client lifecycle ─────────────────────────────────────────────────

    async def __aenter__(self) -> "GhostAdminClient":
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with GhostAdminClient(...)' context manager")
        return self._client

    # ── JWT ───────────────────────────────────────────────────────────────────

    def _make_token(self) -> str:
        """Generate a short-lived Ghost Admin JWT (valid 5 minutes)."""
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 300,
            "aud": "/admin/",
        }
        key_bytes = bytes.fromhex(self._secret_hex)
        token: str = jwt.encode(
            payload,
            key_bytes,
            algorithm="HS256",
            headers={"kid": self._key_id},
        )
        return token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Ghost {self._make_token()}"}

    # ── Posts ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _wrap_html_card(html: str) -> str:
        """Wrap HTML in Ghost's kg-html-card markers so custom classes are preserved.

        Ghost's Lexical converter strips unknown div/aside elements. Wrapping the
        entire body in an HTML card tells Ghost to store it verbatim.
        """
        return f"<!--kg-card-begin: html-->\n{html}\n<!--kg-card-end: html-->"

    async def create_post(
        self,
        title: str,
        html: str,
        tags: list[str],
        status: str = "published",
        excerpt: str | None = None,
        author_id: str | None = None,
    ) -> PostResponse:
        """Create and optionally publish a new Ghost post."""
        import logging
        import re
        _log = logging.getLogger(__name__)
        # Wrap in Ghost HTML card so custom CSS classes are not stripped by Lexical
        html = self._wrap_html_card(html)
        # Ghost requires plain text in custom_excerpt (no HTML) and max 300 chars
        if excerpt:
            excerpt = re.sub(r"<[^>]+>", "", excerpt).strip()
            if len(excerpt) > 300:
                excerpt = excerpt[:297] + "..."
        post = PostInput.from_dict(
            title=title, html=html, tags=tags, status=status, excerpt=excerpt, author_id=author_id
        )
        payload: dict[str, Any] = {"posts": [post.model_dump(exclude_none=True)]}

        resp = await self._http().post(
            f"{self._base_url}/ghost/api/admin/posts/",
            json=payload,
            headers=self._auth_headers(),
            params={"source": "html"},
        )
        if not resp.is_success:
            _log.error("Ghost API error %s: %s", resp.status_code, resp.text[:2000])
        resp.raise_for_status()
        return PostResponse.from_api(resp.json()["posts"][0])

    async def create_email_post(
        self,
        title: str,
        html: str,
        newsletter_id: str | None = None,
    ) -> PostResponse:
        """Create an email-only newsletter post and send it."""
        post = EmailPostInput.for_newsletter(title=title, html=html, newsletter_id=newsletter_id)
        data = post.model_dump(exclude_none=True)
        payload: dict[str, Any] = {"posts": [data]}

        resp = await self._http().post(
            f"{self._base_url}/ghost/api/admin/posts/",
            json=payload,
            headers=self._auth_headers(),
            params={"source": "html"},
        )
        resp.raise_for_status()
        return PostResponse.from_api(resp.json()["posts"][0])

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_recent_posts(self, days: int = 7) -> list[dict[str, Any]]:
        """Return all published posts from the last *days* days."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        resp = await self._http().get(
            f"{self._base_url}/ghost/api/admin/posts/",
            headers=self._auth_headers(),
            params={
                "limit": "all",
                "filter": f"status:published+published_at:>{since}",
                "include": "tags",
            },
        )
        resp.raise_for_status()
        posts = resp.json().get("posts", [])
        # Filter out newsletter posts (posts with #newsletter internal tag)
        filtered = []
        for post in posts:
            tags = post.get("tags", [])
            is_newsletter = any(
                t.get("name", "").startswith("#") and "newsletter" in t.get("name", "").lower()
                for t in tags if isinstance(t, dict)
            )
            if not is_newsletter:
                filtered.append(post)
        return filtered

    async def get_newsletters(self) -> list[dict[str, Any]]:
        """Return all newsletters (useful for finding newsletter IDs)."""
        resp = await self._http().get(
            f"{self._base_url}/ghost/api/admin/newsletters/",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("newsletters", [])
