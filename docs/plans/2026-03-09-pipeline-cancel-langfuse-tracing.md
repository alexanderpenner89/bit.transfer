# Pipeline Cancel + Langfuse Tracing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add cancel button for running pipelines and fix Langfuse tracing so all agent observations within one pipeline run appear as a single nested trace instead of separate root traces.

**Architecture:** Store asyncio Task handles per run_id; cancel endpoint cancels the task and marks running stages as "cancelled". Wrap pipeline entry points in a root `start_as_current_observation` span so all nested agent spans are children of one trace. UI gets a cancel button that appears during active runs.

**Tech Stack:** FastAPI (asyncio), Langfuse Python SDK (OTel-based spans), vanilla JS SSE

---

### Task 1: Add cancel helper to run_store.py

**Files:**
- Modify: `backend/devtools/run_store.py`

**Step 1: Add `cancel_running_stages` function**

Append to the end of `run_store.py`:

```python
async def cancel_running_stages(run_id: str) -> list[str]:
    """Mark all 'running' stages as 'cancelled'. Returns list of cancelled stage names."""
    async with _lock:
        data = _load_raw()
        if run_id not in data["runs"]:
            return []
        cancelled = []
        for stage, info in data["runs"][run_id]["stages"].items():
            if info["status"] == "running":
                info["status"] = "cancelled"
                info["completed_at"] = None
                info["error"] = "Cancelled by user"
                cancelled.append(stage)
        if cancelled:
            _save_raw(data)
        return cancelled
```

**Step 2: Commit**

```bash
git add backend/devtools/run_store.py
git commit -m "feat: add cancel_running_stages to run_store"
```

---

### Task 2: Add task registry + cancel endpoint to server.py

**Files:**
- Modify: `backend/devtools/server.py`

**Step 1: Add `_run_tasks` dict after `_run_queues` (line ~44)**

```python
# Per-run active asyncio tasks (for cancellation)
_run_tasks: dict[str, asyncio.Task] = {}
```

**Step 2: Add helper to register and clean up tasks (after `_push` function)**

```python
def _register_task(run_id: str, coro) -> asyncio.Task:
    """Create and register an asyncio Task for a pipeline run."""
    task = asyncio.create_task(coro)
    _run_tasks[run_id] = task
    task.add_done_callback(lambda _: _run_tasks.pop(run_id, None))
    return task
```

**Step 3: Replace `background_tasks.add_task` in all three pipeline endpoints**

Change `run_research_pipeline`:
```python
@app.post("/api/runs/{run_id}/pipeline/research")
async def run_research_pipeline(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _register_task(run_id, _run_pipeline_stages(run_id, RESEARCH_STAGES))
    return {"accepted": True}
```

Change `run_publication_pipeline`:
```python
@app.post("/api/runs/{run_id}/pipeline/publication")
async def run_publication_pipeline(run_id: str):
    run = await run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    _register_task(run_id, _run_full_publication_pipeline(run_id))
    return {"accepted": True}
```

Change `run_full_pipeline` (move `_run_all` out as a module-level function named `_run_all_stages`):
```python
async def _run_all_stages(run_id: str) -> None:
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
```

Also remove `BackgroundTasks` from the `run_stage` endpoint:
```python
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
```

Remove `BackgroundTasks` from imports (it's no longer used):
```python
from fastapi import FastAPI, HTTPException
```

**Step 4: Add cancel endpoint (after the run_stage endpoint)**

```python
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
```

**Step 5: Handle CancelledError in `_run_pipeline_stages`**

Wrap the stage loop in `_run_pipeline_stages` to catch cancellation:

```python
async def _run_pipeline_stages(run_id: str, stages: list[str], *, final_event: bool = True) -> None:
    """Run a sequence of stages, loading inputs from prior stage outputs."""
    from langfuse import propagate_attributes

    run = await run_store.get_run(run_id)
    if not run:
        return

    ctx: dict[str, Any] = {}
    for s in run_store.STAGES:
        if run["stages"][s]["status"] == "completed" and run["stages"][s]["output"]:
            ctx[s] = run["stages"][s]["output"]

    try:
        with propagate_attributes(session_id=run_id, user_id=run["gewerk_id"]):
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
                run = await run_store.get_run(run_id)
                if run["stages"][stage]["status"] != "completed":
                    break
                if run["stages"][stage]["output"]:
                    ctx[stage] = run["stages"][stage]["output"]
    except asyncio.CancelledError:
        # Stages will be marked cancelled by the cancel endpoint
        raise

    if final_event:
        await _push(run_id, "run_completed", {"run_id": run_id})
```

Similarly wrap `_run_full_publication_pipeline`'s main `try` block to re-raise `CancelledError` before the except `Exception` handler catches it:

```python
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        ...
```

**Step 6: Commit**

```bash
git add backend/devtools/server.py
git commit -m "feat: add pipeline cancel endpoint with asyncio task registry"
```

---

### Task 3: Fix Langfuse tracing — wrap pipeline runs in root spans

**Files:**
- Modify: `backend/devtools/server.py`

**The problem:** Each agent's `start_as_current_observation` call creates a new root trace because no parent span is active in the background task context. Fix: create a root span at the top of each pipeline entry point.

**Step 1: Wrap `_run_pipeline_stages` with a root span**

Add root span around the entire stage loop (inside the existing `propagate_attributes` block):

```python
async def _run_pipeline_stages(run_id: str, stages: list[str], *, final_event: bool = True) -> None:
    from langfuse import propagate_attributes
    from config import get_langfuse

    run = await run_store.get_run(run_id)
    if not run:
        return

    ctx: dict[str, Any] = {}
    for s in run_store.STAGES:
        if run["stages"][s]["status"] == "completed" and run["stages"][s]["output"]:
            ctx[s] = run["stages"][s]["output"]

    span_name = "research-pipeline" if set(stages) <= set(["strategy","explorer","evaluator","precision","expansion"]) else "pipeline-stages"

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
                    run = await run_store.get_run(run_id)
                    if run["stages"][stage]["status"] != "completed":
                        break
                    if run["stages"][stage]["output"]:
                        ctx[stage] = run["stages"][stage]["output"]
    except asyncio.CancelledError:
        raise

    if final_event:
        await _push(run_id, "run_completed", {"run_id": run_id})
```

**Step 2: Wrap `_run_full_publication_pipeline` with a root span**

Inside the `try` block, before the PublicationPipeline call, add:

```python
        with propagate_attributes(session_id=run_id, user_id=gewerk_id):
            with get_langfuse().start_as_current_observation(
                name="publication-pipeline",
                as_type="span",
                input={"run_id": run_id, "gewerk_id": gewerk_id,
                       "precision_works": len(precision_works),
                       "expanded_works": len(expanded_works)},
            ):
                pipeline = PublicationPipeline(on_progress=on_progress)
                dossier = await pipeline.run(research_result, research_questions, gewerk_context)
```

(Remove the existing `with propagate_attributes(...)` that's already there and fold it into the new block.)

**Step 3: Wrap `_run_all_stages` with an outer root span**

```python
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
```

Note: When `_run_all_stages` calls `_run_pipeline_stages`, the inner `propagate_attributes` and inner `start_as_current_observation` in `_run_pipeline_stages` will create a child span named "research-pipeline" nested under "full-pipeline". This is the correct behavior.

**Step 4: Commit**

```bash
git add backend/devtools/server.py
git commit -m "feat: wrap pipeline runs in root Langfuse spans for proper trace hierarchy"
```

---

### Task 4: Fix evaluator output rendering in UI (evaluator now returns list)

**Files:**
- Modify: `backend/devtools/static/index.html`

**The problem:** `renderOutput` for "evaluator" stage accesses `output.display_name` / `output.is_relevant` etc., but evaluator now returns a list of TopicEvaluation objects.

**Step 1: Update `renderOutput` evaluator case**

Find the evaluator case in `renderOutput` (around line 773):

```javascript
case 'evaluator':
  stats = [
    stat('Topic', output.display_name||output.topic_id||'—'),
    stat('Relevant', output.is_relevant ? '✓ yes' : '✗ no'),
    stat('Confidence', ((output.confidence||0)*100).toFixed(0)+'%'),
  ];
  if (output.reasoning) preview = output.reasoning;
  break;
```

Replace with:

```javascript
case 'evaluator': {
  const evals = Array.isArray(output) ? output : [output];
  const relevant = evals.filter(e => e.is_relevant);
  stats = [
    stat('Evaluated', evals.length),
    stat('Relevant', relevant.length),
    stat('Avg confidence', evals.length
      ? ((evals.reduce((s,e)=>s+(e.confidence||0),0)/evals.length)*100).toFixed(0)+'%'
      : '—'),
  ];
  if (relevant[0]?.display_name) preview = relevant.map(e=>e.display_name).join(', ');
  break;
}
```

**Step 2: Commit**

```bash
git add backend/devtools/static/index.html
git commit -m "fix: update evaluator output rendering for list of evaluations"
```

---

### Task 5: Add cancelled status styling to UI

**Files:**
- Modify: `backend/devtools/static/index.html`

**Step 1: Add CSS for cancelled stage cards**

After the `.sc.failed` rule (around line 115):

```css
.sc.cancelled{border-color:rgba(140,100,0,0.4);border-left:3px solid var(--amber)}
.rdot.cancelled{background:var(--amber)}
```

Add `--amber` to the CSS variables (find the `:root` block at the top):

```css
--amber: #b07d00;
--amber-bg: rgba(176,125,0,0.08);
```

**Step 2: Add cancelled to `statusIcon` function**

Find `statusIcon` function in JS and add:

```javascript
case 'cancelled': return '<span style="color:var(--amber)">⊘</span>';
```

**Step 3: Add cancelled to `badgeStyle` function**

```javascript
case 'cancelled': return 'background:var(--amber-bg);color:var(--amber)';
```

**Step 4: Add cancelled to sidebar dot classes**

Already handled via CSS `.rdot.cancelled`.

**Step 5: Commit**

```bash
git add backend/devtools/static/index.html
git commit -m "feat: add cancelled status styling to pipeline UI"
```

---

### Task 6: Add cancel button to UI + handle SSE event

**Files:**
- Modify: `backend/devtools/static/index.html`

**Step 1: Add helper to detect if any stage is running**

In the JS, add a function to check if the current run has any running stage:

```javascript
function isRunning(run) {
  if (!run) return false;
  return Object.values(run.stages).some(s => s.status === 'running');
}
```

**Step 2: Add cancel button to `renderMain` run header**

Find the run header actions div in `renderMain` (around line 692):

```javascript
<div class="run-hdr-acts">
  <button class="btn btn-ghost" onclick="refreshRun()">↻ Refresh</button>
</div>
```

Replace with:

```javascript
<div class="run-hdr-acts">
  ${isRunning(run) ? `<button class="btn btn-red" onclick="cancelRun()">⬛ Cancel</button>` : ''}
  <button class="btn btn-ghost" onclick="refreshRun()">↻ Refresh</button>
</div>
```

**Step 3: Add `cancelRun` function**

```javascript
async function cancelRun() {
  const runId = state.selectedRunId;
  if (!runId) return;
  try {
    await api(`/api/runs/${runId}/cancel`, {method: 'POST'});
  } catch(e) {
    alert('Cancel failed: ' + e.message);
  }
}
```

**Step 4: Handle `run_cancelled` SSE event**

In the `handle` switch in `startSSE`, add:

```javascript
case 'run_cancelled':
  api(`/api/runs/${runId}`).then(r => { state.run = r; renderMain(); }).catch(()=>{});
  break;
```

Also add `'run_cancelled'` to the `events` array:

```javascript
const events = ['stage_started','progress','stage_completed','stage_failed','run_completed','run_cancelled'];
```

**Step 5: Commit**

```bash
git add backend/devtools/static/index.html
git commit -m "feat: add cancel button and run_cancelled SSE handling to UI"
```

---

### Task 7: Deploy and verify

**Step 1: Push to main to trigger GitHub Actions deployment**

```bash
git push origin main
```

**Step 2: After deployment (~2 min), open http://alexanderpenner.de/devtools/**

**Step 3: Start a full pipeline run and verify:**
- Cancel button appears in run header while pipeline is running
- Clicking cancel marks stages as cancelled (amber color, ⊘ icon)
- SSE stream receives `run_cancelled` event and UI updates

**Step 4: Open Langfuse and verify:**
- Each pipeline run appears as ONE trace (not separate traces per agent call)
- Trace hierarchy: `full-pipeline` → `research-pipeline` → per-stage spans → per-candidate evaluations
- `session_id` groups all traces from the same `run_id`

**Step 5: Commit if any fixes needed, then final push**
