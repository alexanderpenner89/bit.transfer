"""OpenAlex tools for the research pipeline.

Three async-wrapped functions covering the three core search workflows.
All pyalex calls are sync and are wrapped in asyncio.to_thread() for non-blocking use.

Naming convention: openalex_* prefix on all public functions.
"""
from __future__ import annotations

import asyncio
from typing import Literal

import pyalex
from pyalex import Works

from config import get_langfuse
from schemas.research_pipeline import TopicRef, WorkResult


def _configure_pyalex() -> None:
    """Set API key from settings if available."""
    try:
        from config import settings
        if settings.openalex_api_key:
            pyalex.config.api_key = settings.openalex_api_key
    except Exception:
        pass


_configure_pyalex()


def _parse_work(work: dict) -> WorkResult:
    """Parse a raw pyalex work dict into a WorkResult."""
    topics = []
    for t in work.get("topics") or []:
        topic_id = t.get("id", "")
        if topic_id:
            # OpenAlex returns full URLs like https://openalex.org/T12345 — extract short ID
            short_id = topic_id.split("/")[-1] if "/" in topic_id else topic_id
            topics.append(TopicRef(
                topic_id=short_id,
                display_name=t.get("display_name", ""),
                score=float(t.get("score", 0.0)),
            ))

    referenced = []
    for ref in work.get("referenced_works") or []:
        if ref:
            short = ref.split("/")[-1] if "/" in ref else ref
            referenced.append(short)

    work_id = work.get("id", "")
    short_work_id = work_id.split("/")[-1] if "/" in work_id else work_id

    abstract = work.get("abstract") or None

    doi = work.get("doi") or None

    return WorkResult(
        work_id=short_work_id,
        title=work.get("display_name") or work.get("title") or "",
        abstract=abstract,
        publication_year=work.get("publication_year"),
        citation_count=work.get("cited_by_count") or 0,
        doi=doi,
        topics=topics,
        referenced_work_ids=referenced,
    )


async def openalex_semantic_search(
    query: str,
    max_results: int = 25,
) -> list[WorkResult]:
    """Search OpenAlex for works matching a natural-language query.

    Use academic vocabulary (e.g. 'thermal bridge mitigation' not 'cold spots').
    No boolean operators — the endpoint runs full-text semantic matching.

    Returns up to max_results works ranked by relevance, each with title, abstract,
    citation_count, topics (with display_name), and referenced_work_ids.

    Raises ValueError with an instructive message if the query yields no results
    (hint: the error message will suggest broadening the query).
    """
    with get_langfuse().start_as_current_observation(
        name="openalex.semantic_search",
        as_type="tool",
        input={"query": query, "max_results": max_results},
    ) as tool:
        def _search() -> list[dict]:
            return Works().search(query).get(per_page=max_results)

        raw = await asyncio.to_thread(_search)

        if not raw:
            tool.update(
                level="ERROR",
                output={"error": f"No results for query: {query[:50]}..."},
            )
            raise ValueError(
                f"Semantic search for '{query}' returned 0 results. "
                "Try shorter or broader academic phrasing."
            )

        results = [_parse_work(w) for w in raw]
        tool.update(output={"result_count": len(results)})
        return results


async def openalex_precision_search(
    topic_id: str,
    topic_name: str,
    boolean_queries: list[str],
    max_results: int = 50,
) -> list[WorkResult]:
    """Search OpenAlex for highly relevant works within a specific topic.

    topic_id: OpenAlex topic ID (e.g. 'T10116') — use the id from TopicEvaluation.
    topic_name: human-readable name — included for LLM context, not used in API call.
    boolean_queries: list of OpenAlex boolean query strings (AND/OR/NOT UPPERCASE,
      synonym groups in parens, wildcards min 3 chars, proximity with ~N).
      Pass the boolean_queries_de and boolean_queries_en from SearchStrategyModel.

    Results are sorted by citation count descending (most-cited first).
    """
    with get_langfuse().start_as_current_observation(
        name="openalex.precision_search",
        as_type="tool",
        input={
            "topic_id": topic_id,
            "topic_name": topic_name,
            "query_count": len(boolean_queries),
        },
    ) as tool:
        def _fetch_one(q: str) -> list[dict]:
            return (
                Works()
                .filter(topics={"id": topic_id})
                .search_filter(default=q)
                .sort(cited_by_count="desc")
                .get(per_page=max_results)
            )

        tasks = [asyncio.to_thread(_fetch_one, q) for q in boolean_queries]
        results_per_query = await asyncio.gather(*tasks)

        seen: set[str] = set()
        merged: list[WorkResult] = []
        for raw_list in results_per_query:
            for w in raw_list:
                wid = w.get("id", "")
                if wid not in seen:
                    seen.add(wid)
                    merged.append(_parse_work(w))

        merged.sort(key=lambda w: w.citation_count, reverse=True)
        tool.update(output={"result_count": len(merged)})
        return merged


async def openalex_get_related_works(
    work_ids: list[str],
    mode: Literal["cited_by", "references"] = "cited_by",
    max_per_work: int = 10,
) -> list[WorkResult]:
    """Expand a set of papers via their citation network.

    mode='cited_by'  → papers that cite these works (incoming citations, broadens scope)
    mode='references' → papers these works cite (outgoing citations, finds foundational literature)

    Use 'cited_by' for recency/impact signals; 'references' for foundational literature.
    Results are deduplicated across all input work_ids.
    """
    with get_langfuse().start_as_current_observation(
        name="openalex.get_related_works",
        as_type="tool",
        input={"work_ids": work_ids, "mode": mode, "max_per_work": max_per_work},
    ) as tool:
        seen: set[str] = set()
        results: list[WorkResult] = []

        if mode == "cited_by":
            def _fetch_cited_by(wid: str) -> list[dict]:
                return Works().filter(cites=wid).get(per_page=max_per_work)

            tasks = [asyncio.to_thread(_fetch_cited_by, wid) for wid in work_ids]
            all_results = await asyncio.gather(*tasks)
            for raw_list in all_results:
                for w in raw_list:
                    wid = w.get("id", "")
                    if wid not in seen:
                        seen.add(wid)
                        results.append(_parse_work(w))

        else:  # references
            def _fetch_work(wid: str) -> dict | None:
                items = Works().filter(openalex=wid).get(per_page=1)
                return items[0] if items else None

            source_tasks = [asyncio.to_thread(_fetch_work, wid) for wid in work_ids]
            source_works = await asyncio.gather(*source_tasks)

            ref_ids: list[str] = []
            for work in source_works:
                if work is None:
                    continue
                for ref in work.get("referenced_works") or []:
                    if ref and ref not in ref_ids:
                        short = ref.split("/")[-1] if "/" in ref else ref
                        ref_ids.append(short)

            ref_ids = ref_ids[: len(work_ids) * max_per_work]

            if ref_ids:
                def _fetch_refs() -> list[dict]:
                    return Works().filter(openalex="|".join(ref_ids)).get(per_page=len(ref_ids))

                raw = await asyncio.to_thread(_fetch_refs)
                for w in raw:
                    wid = w.get("id", "")
                    if wid not in seen:
                        seen.add(wid)
                        results.append(_parse_work(w))

        tool.update(output={"result_count": len(results)})
        return results
