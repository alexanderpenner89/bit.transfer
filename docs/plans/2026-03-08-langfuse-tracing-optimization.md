# Langfuse Tracing Optimization Plan

## Problem Analysis

Current tracing shows flat observations without hierarchical parent-child relationships:
- Tool calls appear disconnected from the agents that invoke them
- Parallel executions lack grouping context
- Agent nesting is not visible in the Langfuse UI

## Solution: Explicit Nested Context Managers

Replace `@observe` decorators with explicit `start_as_current_observation()` context managers to establish proper parent-child hierarchies.

## Implementation Steps

### Step 1: Update Tool Functions to Accept Parent Context
**File:** `backend/tools/openalex_tools.py`

Modify all three tool functions to accept an optional `parent_observation` parameter and use context managers instead of decorators:

```python
from langfuse import Langfuse

langfuse = Langfuse()

async def openalex_semantic_search(
    query: str,
    max_results: int = 25,
    parent_observation=None,
) -> list[WorkResult]:
    """Search OpenAlex for works matching a natural-language query."""
    ctx = langfuse.start_as_current_observation(
        name="openalex.semantic_search",
        as_type="tool",
        input={"query": query, "max_results": max_results},
        parent=parent_observation,
    ) if parent_observation else langfuse.start_as_current_observation(
        name="openalex.semantic_search",
        as_type="tool",
        input={"query": query, "max_results": max_results},
    )

    with ctx as tool:
        def _search() -> list[dict]:
            return Works().search(query).get(per_page=max_results)

        raw = await asyncio.to_thread(_search)

        if not raw:
            tool.update(level="ERROR", output={"error": "No results"})
            raise ValueError(f"Semantic search for '{query}' returned 0 results.")

        results = [_parse_work(w) for w in raw]
        tool.update(output={"result_count": len(results)})
        return results
```

Repeat for `openalex_precision_search` and `openalex_get_related_works`.

---

### Step 2: Update ExplorerAgent with Nested Tool Context
**File:** `backend/agents/explorer.py`

Replace decorator with explicit span and pass parent context to tool calls:

```python
from langfuse import Langfuse

langfuse = Langfuse()

class ExplorerAgent:
    """Stage 1: Parallel semantic search → deduplicated works + topic candidates."""

    async def run(
        self,
        strategy: SearchStrategyModel,
        parent_observation=None,
    ) -> ExplorationResult:
        """Run all semantic queries in parallel and aggregate results."""
        queries = strategy.semantic_queries_en

        ctx = langfuse.start_as_current_observation(
            name="explorer.run",
            as_type="agent",
            input={"gewerk_id": strategy.gewerk_id, "query_count": len(queries)},
            parent=parent_observation,
        ) if parent_observation else langfuse.start_as_current_observation(
            name="explorer.run",
            as_type="agent",
            input={"gewerk_id": strategy.gewerk_id, "query_count": len(queries)},
        )

        with ctx as span:
            # Pass the span as parent to tool calls
            results = await asyncio.gather(
                *[openalex_semantic_search(q, parent_observation=span) for q in queries],
                return_exceptions=True,
            )

            # ... existing processing logic ...

            span.update(output={
                "works_found": len(works),
                "topics_discovered": len(topic_candidates),
            })

            return ExplorationResult(
                gewerk_id=strategy.gewerk_id,
                works=works,
                topic_candidates=topic_candidates,
            )
```

---

### Step 3: Update Evaluator with Nested Structure
**File:** `backend/agents/evaluator.py`

```python
@observe(name="evaluator.evaluate", as_type="agent")
async def evaluate(
    self,
    candidate: TopicCandidate,
    profil: GewerksProfilModel,
    parent_observation=None,
) -> TopicEvaluation:
    """Evaluate whether a topic is relevant for the given craft trade profile."""
    # Use explicit context manager if parent provided
    if parent_observation:
        with langfuse.start_as_current_observation(
            name="evaluator.evaluate",
            as_type="agent",
            input={"topic_id": candidate.topic_id, "topic_name": candidate.display_name},
            parent=parent_observation,
        ) as agent:
            result = await self._execute_evaluation(candidate, profil)
            agent.update(output={"is_relevant": result.is_relevant, "confidence": result.confidence})
            return result
    else:
        # Fallback to decorated method
        return await self._execute_evaluation(candidate, profil)
```

---

### Step 4: Update PrecisionSearchAgent with Agent→Tool Parent Link
**File:** `backend/agents/precision_search.py`

```python
async def run(
    self,
    topic: TopicEvaluation,
    boolean_queries: list[str],
    parent_observation=None,
) -> list[WorkResult]:
    """Run precision search for a single relevant topic."""
    ctx = langfuse.start_as_current_observation(
        name="precision_search.run",
        as_type="agent",
        input={"topic_id": topic.topic_id, "topic_name": topic.display_name},
        parent=parent_observation,
    ) if parent_observation else langfuse.start_as_current_observation(
        name="precision_search.run",
        as_type="agent",
        input={"topic_id": topic.topic_id, "topic_name": topic.display_name},
    )

    with ctx as agent:
        deps = PrecisionSearchDeps(topic=topic, boolean_queries=boolean_queries)
        user_prompt = self._build_user_prompt(topic, boolean_queries)

        # Store parent for tool registration
        self._current_parent = agent
        result = await self.agent.run(user_prompt, deps=deps)

        agent.update(output={"works_found": len(result.output)})
        return result.output
```

Update tool registration to use the stored parent:

```python
def _register_tools(self) -> None:
    @self.agent.tool_plain
    async def openalex_precision_search_tool(
        topic_id: str,
        topic_name: str,
        boolean_queries: list[str],
        max_results: int = 50,
    ) -> list[WorkResult]:
        """Search OpenAlex for highly relevant works within a specific topic."""
        return await openalex_precision_search(
            topic_id=topic_id,
            topic_name=topic_name,
            boolean_queries=boolean_queries,
            max_results=max_results,
            parent_observation=getattr(self, '_current_parent', None),
        )
```

---

### Step 5: Restructure Aggregator as Root Trace Coordinator
**File:** `backend/agents/aggregator.py`

```python
from langfuse import Langfuse

langfuse = Langfuse()

class ResearchAggregator:
    """Orchestrates the full 4-stage research pipeline."""

    async def run(
        self,
        strategy: SearchStrategyModel,
        profil: GewerksProfilModel,
    ) -> ResearchResult:
        """Execute the full research pipeline for the given strategy and profile."""

        with langfuse.start_as_current_span(
            name="aggregator.run",
            as_type="span",
            input={"gewerk_id": strategy.gewerk_id, "gewerk_name": profil.gewerk_name},
        ) as span:

            # Stage 1: Explorer (nested under span)
            self._log(f"  [dim]→ Semantische Suche: {len(strategy.semantic_queries_en)} Queries...")
            exploration = await self._explorer.run(strategy, parent_observation=span)
            self._log(f"  [green]✓[/green] {len(exploration.works)} Works gefunden")

            # Stage 2: Evaluator (multiple parallel, nested under span)
            evaluations = await asyncio.gather(
                *[
                    self._evaluator.evaluate(candidate, profil, parent_observation=span)
                    for candidate in exploration.topic_candidates
                ],
                return_exceptions=True,
            )

            # Stage 3: Precision Search (nested under span)
            precision_results = await asyncio.gather(
                *[
                    self._precision.run(topic, all_boolean_queries, parent_observation=span)
                    for topic in relevant_topics
                ],
                return_exceptions=True,
            )

            # Stage 4: Citation expansion
            if top_ids:
                expanded_works = await openalex_get_related_works(
                    top_ids,
                    mode="cited_by",
                    parent_observation=span,
                )

            span.update(output={
                "total_works": len(precision_works) + len(expanded_works),
                "relevant_topics": len(relevant_topics),
            })

            return ResearchResult(...)
```

---

### Step 6: Update Orchestrator Entry Point
**File:** `backend/agents/orchestrator.py`

Keep `@observe` decorator as the entry point creates its own trace context:

```python
@observe(name="orchestrator.generate", as_type="agent")
async def generate(self, profil: GewerksProfilModel) -> SearchStrategyModel:
    """Generates a complete search strategy for the given profile."""
    # This creates a separate trace for strategy generation
    # Pipeline execution would be a child of this or a separate trace
    ...
```

---

## Expected Result in Langfuse UI

```
aggregator.run (SPAN)
├── explorer.run (AGENT)
│   ├── openalex.semantic_search (TOOL)
│   ├── openalex.semantic_search (TOOL)
│   ├── openalex.semantic_search (TOOL)
│   └── ... (parallel tools)
├── evaluator.evaluate (AGENT)
├── evaluator.evaluate (AGENT)
├── evaluator.evaluate (AGENT)
├── precision_search.run (AGENT)
│   └── openalex.precision_search (TOOL)
├── precision_search.run (AGENT)
│   └── openalex.precision_search (TOOL)
└── openalex.get_related_works (TOOL)
```

## Verification Checklist

After implementation:
- [ ] Traces show hierarchical tree structure in Langfuse UI
- [ ] Tool calls are children of the agent that invoked them
- [ ] Parallel executions are grouped under their parent span
- [ ] Latency is aggregated correctly per hierarchy level
- [ ] Clicking an agent shows its child tool calls
- [ ] Full names are visible (not truncated)

## Files to Modify

1. `backend/tools/openalex_tools.py` - 3 functions
2. `backend/agents/explorer.py` - run method
3. `backend/agents/evaluator.py` - evaluate method
4. `backend/agents/precision_search.py` - run method + tool registration
5. `backend/agents/aggregator.py` - run method
