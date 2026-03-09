"""DevTools FastAPI server.

Routes:
  GET  /                              → serve index.html
  GET  /api/fixtures                  → list profile fixtures
  GET  /api/fixtures/{filename}       → return raw profile JSON
  GET  /api/runs                      → list all runs
  GET  /api/runs/{run_id}             → single run
  DELETE /api/runs/{run_id}           → delete run
  POST /api/runs                      → create run
  POST /api/runs/{run_id}/pipeline/research     → run strategy→explorer→evaluator→precision→expansion
  POST /api/runs/{run_id}/pipeline/publication  → run pub_eval→perspective→article→dossier
  POST /api/runs/{run_id}/pipeline/full         → run all 9 stages
  POST /api/runs/{run_id}/stages/{stage}        → run single stage
  GET  /api/runs/{run_id}/stream      → SSE progress stream
  GET  /api/langfuse/observations     → list past successful observations
  GET  /api/langfuse/observations/{obs_id} → single observation
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from devtools import run_store
from devtools import langfuse_bridge

app = FastAPI(title="bit.transfer DevTools")

_STATIC_DIR = Path(__file__).parent / "static"
_PROFILES_DIR = Path("/app/data/profiles")

# Per-run SSE queues
_run_queues: dict[str, asyncio.Queue] = {}

# Per-run active asyncio tasks (for cancellation)
_run_tasks: dict[str, asyncio.Task] = {}

STAGE_DEPENDENCIES: dict[str, list[str]] = {
    "strategy": [],
    "explorer": ["strategy"],
    "evaluator": ["explorer"],
    "precision": ["evaluator"],
    "expansion": ["precision"],
    "pub_eval": ["expansion"],
    "perspective": ["pub_eval"],
    "article": ["perspective"],
    "dossier": ["article"],
}

RESEARCH_STAGES = ["strategy", "explorer", "evaluator", "precision", "expansion"]
PUBLICATION_STAGES = ["pub_eval", "perspective", "article", "dossier"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_rich(msg: str) -> str:
    """Strip Rich markup tags like [green], [/dim], etc."""
    return re.sub(r"\[/?[^\]]+\]", "", msg)


def _make_run_id(gewerk_id: str) -> str:
    short = gewerk_id.lower().replace("_", "-")
    suffix = uuid.uuid4().hex[:8]
    return f"{short}-{suffix}"


def _get_queue(run_id: str) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def _push(run_id: str, event: str, data: Any) -> None:
    q = _get_queue(run_id)
    await q.put({"event": event, "data": data})


def _register_task(run_id: str, coro) -> asyncio.Task:
    """Create and register an asyncio Task for a pipeline run."""
    task = asyncio.create_task(coro)
    _run_tasks[run_id] = task
    task.add_done_callback(lambda _: _run_tasks.pop(run_id, None))
    return task


def _check_deps(run: dict[str, Any], stage: str) -> None:
    """Raise 422 if stage dependencies are not completed."""
    for dep in STAGE_DEPENDENCIES[stage]:
        dep_status = run["stages"][dep]["status"]
        if dep_status != "completed":
            raise HTTPException(
                status_code=422,
                detail=f"Stage '{dep}' must be completed before '{stage}' (current: {dep_status})",
            )


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Stage runner ─────────────────────────────────────────────────────────────

async def _run_stage(run_id: str, stage: str, stage_input: dict[str, Any]) -> None:
    """Execute a single stage and update the run store + SSE queue."""
    await run_store.update_stage(run_id, stage, {
        "status": "running",
        "started_at": _now(),
        "output": None,
        "error": None,
    })
    await _push(run_id, "stage_started", {"stage": stage})

    def on_progress(msg: str) -> None:
        asyncio.get_event_loop().call_soon_threadsafe(
            lambda: asyncio.create_task(_push(run_id, "progress", {"stage": stage, "message": _strip_rich(msg)}))
        )

    try:
        output = await _execute_stage(stage, stage_input, on_progress)
        await run_store.update_stage(run_id, stage, {
            "status": "completed",
            "completed_at": _now(),
            "output": output,
        })
        await _push(run_id, "stage_completed", {"stage": stage, "output": output})
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        await run_store.update_stage(run_id, stage, {
            "status": "failed",
            "completed_at": _now(),
            "error": error_msg,
        })
        await _push(run_id, "stage_failed", {"stage": stage, "error": error_msg})


async def _execute_stage(stage: str, stage_input: dict[str, Any], on_progress) -> Any:
    """Dispatch to the correct agent and return serializable output."""
    from config import settings

    if stage == "strategy":
        from agents.orchestrator import OrchestratorAgent
        from schemas.gewerksprofil import GewerksProfilModel
        profil = GewerksProfilModel.model_validate(stage_input["profil"])
        agent = OrchestratorAgent()
        strategy = await agent.generate(profil)
        return strategy.model_dump()

    elif stage == "explorer":
        from agents.explorer import ExplorerAgent
        from schemas.search_strategy import SearchStrategyModel
        strategy = SearchStrategyModel.model_validate(stage_input["strategy"])
        agent = ExplorerAgent()
        result = await agent.run(strategy)
        return result.model_dump()

    elif stage == "evaluator":
        from agents.evaluator import TopicEvaluatorAgent
        from schemas.research_pipeline import TopicCandidate
        from schemas.gewerksprofil import GewerksProfilModel
        candidates = [TopicCandidate.model_validate(c) for c in stage_input["candidates"]]
        profil = GewerksProfilModel.model_validate(stage_input["profil"])
        agent = TopicEvaluatorAgent()
        sem = asyncio.Semaphore(settings.llm_concurrency)

        async def _eval_one(candidate: TopicCandidate):
            async with sem:
                return await agent.evaluate(candidate, profil)

        results = await asyncio.gather(*[_eval_one(c) for c in candidates], return_exceptions=True)
        return [r.model_dump() for r in results if not isinstance(r, Exception)]

    elif stage == "precision":
        from agents.precision_search import PrecisionSearchAgent
        from schemas.research_pipeline import TopicEvaluation
        topics = [TopicEvaluation.model_validate(t) for t in stage_input["topics"]]
        queries = stage_input["queries"]
        agent = PrecisionSearchAgent()
        results = await asyncio.gather(*[agent.run(topic, queries) for topic in topics], return_exceptions=True)
        seen: set[str] = set()
        all_works = []
        for result in results:
            if isinstance(result, Exception):
                continue
            for work in result:
                if work.work_id not in seen:
                    seen.add(work.work_id)
                    all_works.append(work)
        all_works.sort(key=lambda w: w.citation_count or 0, reverse=True)
        return [w.model_dump() for w in all_works]

    elif stage == "expansion":
        from tools.openalex_tools import openalex_get_related_works
        work_ids = stage_input["work_ids"]
        works = await openalex_get_related_works(work_ids, mode="cited_by")
        return [w.model_dump() for w in works]

    elif stage == "pub_eval":
        from agents.publication_evaluator import PublicationEvaluatorAgent, WorkEvalInput, EvalContext
        work = WorkEvalInput.model_validate(stage_input["work"])
        context = EvalContext.model_validate(stage_input["context"])
        agent = PublicationEvaluatorAgent()
        result = await agent.evaluate(work=work, context=context)
        return result.model_dump()

    elif stage == "perspective":
        from agents.perspective_search import PerspectiveSearchAgent, PerspectiveInput
        inp = PerspectiveInput.model_validate(stage_input)
        agent = PerspectiveSearchAgent()
        result = await agent.run(inp)
        return result.model_dump()

    elif stage == "article":
        from agents.article_generator import ArticleGeneratorAgent, ArticleDeps, ArticleWorkInput, ArticleGewerksContext
        deps = ArticleDeps(
            work_id=stage_input["work_id"],
            work=ArticleWorkInput.model_validate(stage_input["work"]),
            perspectives=stage_input.get("perspectives", []),
            gewerk_context=ArticleGewerksContext.model_validate(stage_input["gewerk_context"]),
            research_questions=stage_input.get("research_questions", []),
        )
        agent = ArticleGeneratorAgent()
        result = await agent.generate(deps)
        return result.model_dump()

    elif stage == "dossier":
        from agents.dossier import DossierAgent, DossierDeps, ArticleSummary
        from schemas.publication_pipeline import EnrichedArticle, DossierModel
        articles = [EnrichedArticle.model_validate(a) for a in stage_input["articles"]]
        article_summaries = [
            ArticleSummary(title=a.title, intro=a.intro, key_learnings=a.key_learnings)
            for a in articles
        ]
        deps = DossierDeps(
            gewerk_id=stage_input["gewerk_id"],
            gewerk_name=stage_input["gewerk_name"],
            research_questions=stage_input.get("research_questions", []),
            article_summaries=article_summaries,
        )
        agent = DossierAgent()
        result = await agent.generate(deps, articles, _now())
        return result.model_dump()

    raise ValueError(f"Unknown stage: {stage}")


async def _run_pipeline_stages(run_id: str, stages: list[str], *, final_event: bool = True) -> None:
    """Run a sequence of stages, loading inputs from prior stage outputs."""
    from langfuse import propagate_attributes
    from config import get_langfuse

    run = await run_store.get_run(run_id)
    if not run:
        return

    # Build a mutable context from previously completed stages
    ctx: dict[str, Any] = {}
    for s in run_store.STAGES:
        if run["stages"][s]["status"] == "completed" and run["stages"][s]["output"]:
            ctx[s] = run["stages"][s]["output"]

    span_name = "research-pipeline" if set(stages) <= {"strategy","explorer","evaluator","precision","expansion"} else "pipeline-stages"

    try:
        with propagate_attributes(session_id=run_id, user_id=run["gewerk_id"]):
            with get_langfuse().start_as_current_observation(
                name=span_name,
                as_type="span",
                input={"run_id": run_id, "gewerk_id": run["gewerk_id"], "stages": stages},
            ):
                for stage in stages:
                    stage_input = _build_stage_input_from_ctx(stage, run, ctx)
                    if stage_input is None:
                        await _push(run_id, "stage_failed", {
                            "stage": stage,
                            "error": "Cannot build input — missing upstream outputs",
                        })
                        await run_store.update_stage(run_id, stage, {
                            "status": "failed",
                            "completed_at": _now(),
                            "error": "Missing upstream outputs",
                        })
                        break
                    await _run_stage(run_id, stage, stage_input)
                    # Refresh run and update ctx after stage completes
                    run = await run_store.get_run(run_id)
                    if run["stages"][stage]["status"] != "completed":
                        break
                    if run["stages"][stage]["output"]:
                        ctx[stage] = run["stages"][stage]["output"]
    except asyncio.CancelledError:
        raise

    if final_event:
        await _push(run_id, "run_completed", {"run_id": run_id})


async def _run_full_publication_pipeline(run_id: str) -> None:
    """Run all publication stages using PublicationPipeline (processes ALL works in parallel)."""
    from langfuse import propagate_attributes
    from config import get_langfuse

    run = await run_store.get_run(run_id)
    if not run:
        return

    # Build context from completed stages
    ctx: dict[str, Any] = {}
    for s in run_store.STAGES:
        if run["stages"][s]["status"] == "completed" and run["stages"][s]["output"]:
            ctx[s] = run["stages"][s]["output"]

    gewerk_id = run["gewerk_id"]
    gewerk_name = run["gewerk_name"]
    profil = _load_profile_by_gewerk_id(gewerk_id)
    kernkompetenzen = profil.get("kernkompetenzen", []) if profil else []

    precision_out = ctx.get("precision", [])
    expansion_out = ctx.get("expansion", [])

    if not precision_out and not expansion_out:
        error = "No works from research pipeline — run research stages first"
        for stage in PUBLICATION_STAGES:
            await run_store.update_stage(run_id, stage, {
                "status": "failed",
                "completed_at": _now(),
                "error": error,
            })
            await _push(run_id, "stage_failed", {"stage": stage, "error": error})
        await _push(run_id, "run_completed", {"run_id": run_id})
        return

    # Mark all publication stages as running
    for stage in PUBLICATION_STAGES:
        await run_store.update_stage(run_id, stage, {
            "status": "running",
            "started_at": _now(),
            "output": None,
            "error": None,
        })
        await _push(run_id, "stage_started", {"stage": stage})

    try:
        from agents.publication_pipeline import PublicationPipeline
        from schemas.research_pipeline import ResearchResult, WorkResult
        from schemas.publication_pipeline import GewerksContext, ResearchQuestionsModel

        precision_works = [
            WorkResult.model_validate(w)
            for w in (precision_out if isinstance(precision_out, list) else [])
        ]
        expanded_works = [
            WorkResult.model_validate(w)
            for w in (expansion_out if isinstance(expansion_out, list) else [])
        ]
        research_result = ResearchResult(
            gewerk_id=gewerk_id,
            exploration_works=[],
            precision_works=precision_works,
            expanded_works=expanded_works,
            relevant_topics=[],
        )
        research_questions = ResearchQuestionsModel(
            gewerk_id=gewerk_id,
            research_questions=[],
            research_focus="",
        )
        gewerk_context = GewerksContext(
            gewerk_id=gewerk_id,
            gewerk_name=gewerk_name,
            kernkompetenzen=kernkompetenzen,
        )

        def on_progress(msg: str) -> None:
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda: asyncio.create_task(
                    _push(run_id, "progress", {"stage": "pub_eval", "message": _strip_rich(msg)})
                )
            )

        with propagate_attributes(session_id=run_id, user_id=gewerk_id):
            with get_langfuse().start_as_current_observation(
                name="publication-pipeline",
                as_type="span",
                input={
                    "run_id": run_id,
                    "gewerk_id": gewerk_id,
                    "precision_works": len(precision_works),
                    "expanded_works": len(expanded_works),
                },
            ):
                pipeline = PublicationPipeline(on_progress=on_progress)
                dossier = await pipeline.run(research_result, research_questions, gewerk_context)

        dossier_dict = dossier.model_dump()

        for stage in PUBLICATION_STAGES:
            output = dossier_dict if stage == "dossier" else None
            await run_store.update_stage(run_id, stage, {
                "status": "completed",
                "completed_at": _now(),
                "output": output,
            })
            await _push(run_id, "stage_completed", {"stage": stage, "output": output})

        # Publish to Ghost if configured
        from config import settings as _settings
        if _settings.ghost_enabled:
            from ghost.client import GhostAdminClient
            from ghost.publisher import publish_dossier
            await _push(run_id, "progress", {"stage": "dossier", "message": f"Publishing {len(dossier.articles)} articles to Ghost..."})
            async with GhostAdminClient(
                api_key=_settings.ghost_admin_api_key,
                ghost_url=_settings.ghost_url,
            ) as ghost_client:
                posts = await publish_dossier(dossier, ghost_client, author_id=_settings.ghost_ai_author_id)
            for post in posts:
                await _push(run_id, "progress", {"stage": "dossier", "message": f"Published: {post.title} → {post.url}"})

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        for stage in PUBLICATION_STAGES:
            await run_store.update_stage(run_id, stage, {
                "status": "failed",
                "completed_at": _now(),
                "error": error_msg,
            })
            await _push(run_id, "stage_failed", {"stage": stage, "error": error_msg})

    await _push(run_id, "run_completed", {"run_id": run_id})


def _build_stage_input_from_ctx(
    stage: str, run: dict[str, Any], ctx: dict[str, Any]
) -> dict[str, Any] | None:
    """Build stage input dict from accumulated pipeline context."""
    gewerk_id = run["gewerk_id"]
    gewerk_name = run["gewerk_name"]

    try:
        if stage == "strategy":
            # Need profil from fixtures — load it
            profil = _load_profile_by_gewerk_id(gewerk_id)
            if profil is None:
                return None
            return {"profil": profil}

        elif stage == "explorer":
            return {"strategy": ctx["strategy"]}

        elif stage == "evaluator":
            exploration = ctx.get("explorer", {})
            candidates = exploration.get("topic_candidates", [])
            if not candidates:
                return None
            profil = _load_profile_by_gewerk_id(gewerk_id)
            return {"candidates": candidates, "profil": profil}

        elif stage == "precision":
            evaluator_out = ctx.get("evaluator", [])
            strategy = ctx.get("strategy", {})
            boolean_queries = (
                strategy.get("boolean_queries_de", []) +
                strategy.get("boolean_queries_en", [])
            )
            # evaluator now returns a list of TopicEvaluation dicts
            if not isinstance(evaluator_out, list):
                return None
            relevant_topics = [t for t in evaluator_out if t.get("is_relevant")]
            if not relevant_topics:
                return None
            return {"topics": relevant_topics, "queries": boolean_queries}

        elif stage == "expansion":
            precision_out = ctx.get("precision", [])
            if not isinstance(precision_out, list):
                return None
            top_ids = [w["work_id"] for w in precision_out[:10]]
            return {"work_ids": top_ids}

        elif stage == "pub_eval":
            # Run first work from precision
            precision_out = ctx.get("precision", [])
            expansion_out = ctx.get("expansion", [])
            all_works = (precision_out if isinstance(precision_out, list) else []) + \
                        (expansion_out if isinstance(expansion_out, list) else [])
            if not all_works:
                return None
            w = all_works[0]
            profil = _load_profile_by_gewerk_id(gewerk_id)
            kernkompetenzen = profil.get("kernkompetenzen", []) if profil else []
            return {
                "work": {
                    "work_id": w["work_id"],
                    "title": w["title"],
                    "abstract": w.get("abstract"),
                    "publication_year": w.get("publication_year"),
                },
                "context": {
                    "gewerk_name": gewerk_name,
                    "kernkompetenzen": kernkompetenzen,
                    "research_questions": [],
                },
            }

        elif stage == "perspective":
            pub_eval_out = ctx.get("pub_eval", {})
            if not pub_eval_out or "work_id" not in pub_eval_out:
                return None
            # Find referenced_work_ids from precision/expansion
            work_id = pub_eval_out["work_id"]
            precision_out = ctx.get("precision", [])
            expansion_out = ctx.get("expansion", [])
            all_works = (precision_out if isinstance(precision_out, list) else []) + \
                        (expansion_out if isinstance(expansion_out, list) else [])
            work_data = next((w for w in all_works if w["work_id"] == work_id), {})
            return {
                "work_id": work_id,
                "title": pub_eval_out.get("title", ""),
                "referenced_work_ids": work_data.get("referenced_work_ids", []),
            }

        elif stage == "article":
            pub_eval_out = ctx.get("pub_eval", {})
            perspective_out = ctx.get("perspective", {})
            if not pub_eval_out or "work_id" not in pub_eval_out:
                return None
            work_id = pub_eval_out["work_id"]
            precision_out = ctx.get("precision", [])
            expansion_out = ctx.get("expansion", [])
            all_works = (precision_out if isinstance(precision_out, list) else []) + \
                        (expansion_out if isinstance(expansion_out, list) else [])
            work_data = next((w for w in all_works if w["work_id"] == work_id), {})
            profil = _load_profile_by_gewerk_id(gewerk_id)
            kernkompetenzen = profil.get("kernkompetenzen", []) if profil else []
            return {
                "work_id": work_id,
                "work": {
                    "title": pub_eval_out.get("title", work_data.get("title", "")),
                    "abstract": work_data.get("abstract"),
                    "doi": work_data.get("doi"),
                    "publication_year": work_data.get("publication_year"),
                    "citation_count": work_data.get("citation_count", 0),
                },
                "perspectives": perspective_out.get("related_works", []) if perspective_out else [],
                "gewerk_context": {
                    "gewerk_name": gewerk_name,
                    "kernkompetenzen": kernkompetenzen,
                },
                "research_questions": [],
            }

        elif stage == "dossier":
            article_out = ctx.get("article")
            if not article_out:
                return None
            articles = [article_out] if isinstance(article_out, dict) else article_out
            return {
                "articles": articles,
                "gewerk_id": gewerk_id,
                "gewerk_name": gewerk_name,
                "research_questions": [],
            }

    except Exception:
        return None

    return None


def _load_profile_by_gewerk_id(gewerk_id: str) -> dict[str, Any] | None:
    """Load a profile JSON by gewerk_id, scanning profiles directory."""
    if not _PROFILES_DIR.exists():
        return None
    for f in _PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("gewerk_id") == gewerk_id:
                return data
        except Exception:
            continue
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(_STATIC_DIR / "index.html")


# Fixtures

@app.get("/api/fixtures")
async def list_fixtures():
    if not _PROFILES_DIR.exists():
        return {"fixtures": []}
    files = sorted(_PROFILES_DIR.glob("*.json"))
    return {"fixtures": [f.name for f in files]}


@app.get("/api/fixtures/{filename}")
async def get_fixture(filename: str):
    path = _PROFILES_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Fixture not found")
    return JSONResponse(json.loads(path.read_text()))


# Runs

@app.get("/api/runs")
async def list_runs():
    runs = await run_store.list_runs()
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    deleted = await run_store.delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"deleted": True}


class CreateRunRequest(BaseModel):
    gewerk_id: str


@app.post("/api/runs", status_code=201)
async def create_run(body: CreateRunRequest):
    # Load gewerk_name from profile
    profil = _load_profile_by_gewerk_id(body.gewerk_id)
    gewerk_name = profil.get("gewerk_name", body.gewerk_id) if profil else body.gewerk_id
    run_id = _make_run_id(body.gewerk_id)
    created_at = _now()
    await run_store.create_run(run_id, body.gewerk_id, gewerk_name, created_at)
    return {"run_id": run_id}


# Pipeline endpoints

@app.post("/api/runs/{run_id}/pipeline/research")
async def run_research_pipeline(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _register_task(run_id, _run_pipeline_stages(run_id, RESEARCH_STAGES))
    return {"accepted": True}


@app.post("/api/runs/{run_id}/pipeline/publication")
async def run_publication_pipeline(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _register_task(run_id, _run_full_publication_pipeline(run_id))
    return {"accepted": True}


async def _run_all_stages(run_id: str) -> None:
    from langfuse import propagate_attributes
    from config import get_langfuse

    run = await run_store.get_run(run_id)
    if not run:
        return

    with propagate_attributes(session_id=run_id, user_id=run["gewerk_id"]):
        with get_langfuse().start_as_current_observation(
            name="full-pipeline",
            as_type="span",
            input={"run_id": run_id, "gewerk_id": run["gewerk_id"]},
        ):
            await _run_pipeline_stages(run_id, RESEARCH_STAGES, final_event=False)
            run_after = await run_store.get_run(run_id)
            if run_after and run_after["stages"]["expansion"]["status"] == "completed":
                await _run_full_publication_pipeline(run_id)
            else:
                await _push(run_id, "run_completed", {"run_id": run_id})


@app.post("/api/runs/{run_id}/pipeline/full")
async def run_full_pipeline(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _register_task(run_id, _run_all_stages(run_id))
    return {"accepted": True}


# Individual stage endpoints

class StageRequest(BaseModel):
    model_config = {"extra": "allow"}


@app.post("/api/runs/{run_id}/stages/{stage}")
async def run_stage(run_id: str, stage: str, body: StageRequest):
    if stage not in STAGE_DEPENDENCIES:
        raise HTTPException(status_code=404, detail=f"Unknown stage: {stage}")
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _check_deps(run, stage)
    stage_input = body.model_dump()
    _register_task(run_id, _run_stage(run_id, stage, stage_input))
    return {"accepted": True}


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Cancel running task if any
    task = _run_tasks.get(run_id)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    # Mark remaining running stages as cancelled
    cancelled = await run_store.cancel_running_stages(run_id)
    await _push(run_id, "run_cancelled", {"run_id": run_id, "stages": cancelled})
    return {"cancelled": True, "stages": cancelled}


# SSE stream

@app.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    queue = _get_queue(run_id)

    async def generator():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield {"event": item["event"], "data": json.dumps(item["data"])}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(generator())


# Langfuse observations

@app.get("/api/langfuse/observations")
async def list_observations(name: str, limit: int = 10):
    observations = await langfuse_bridge.list_observations(name=name, limit=limit)
    return {"observations": observations}


@app.get("/api/langfuse/observations/{obs_id}")
async def get_observation(obs_id: str):
    obs = await langfuse_bridge.get_observation(obs_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    return obs
