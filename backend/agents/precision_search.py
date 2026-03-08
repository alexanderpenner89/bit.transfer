"""PrecisionSearchAgent — Stage 3a of the research pipeline.

PydanticAI agent that uses the openalex_precision_search tool to find
highly relevant works within a specific evaluated topic.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import get_langfuse
from pydantic_ai import Agent, RunContext

from schemas.research_pipeline import TopicEvaluation, WorkResult
from tools.openalex_tools import openalex_precision_search


@dataclass
class PrecisionSearchDeps:
    topic: TopicEvaluation
    boolean_queries: list[str]


class PrecisionSearchAgent:
    """Stage 3a: LLM-guided precision search within a single relevant topic."""

    def __init__(self, model=None) -> None:
        if model is None:
            from config import settings
            model = settings.build_model()

        self.agent: Agent[PrecisionSearchDeps, list[WorkResult]] = Agent(
            model=model,
            output_type=list[WorkResult],
            deps_type=PrecisionSearchDeps,
            defer_model_check=True,
        )
        self._register_tools()
        self._register_prompts()

    async def run(
        self,
        topic: TopicEvaluation,
        boolean_queries: list[str],
    ) -> list[WorkResult]:
        """Run precision search for a single relevant topic."""
        with get_langfuse().start_as_current_observation(
            name="precision_search.run",
            as_type="agent",
            input={
                "topic_id": topic.topic_id,
                "topic_name": topic.display_name,
                "query_count": len(boolean_queries),
            },
        ) as agent:
            deps = PrecisionSearchDeps(topic=topic, boolean_queries=boolean_queries)
            user_prompt = self._build_user_prompt(topic, boolean_queries)
            result = await self.agent.run(user_prompt, deps=deps)
            usage = result.usage()

            agent.update(
                output={"works_found": len(result.output)},
                usage_details={
                    "input": usage.input_tokens or 0,
                    "output": usage.output_tokens or 0,
                },
            )
            return result.output

    def _build_user_prompt(
        self, topic: TopicEvaluation, boolean_queries: list[str]
    ) -> str:
        queries_formatted = "\n".join(f"  - {q}" for q in boolean_queries)
        return f"""Search for high-quality academic works on the following topic using precision search.

**Topic:**
- ID: {topic.topic_id}
- Name: {topic.display_name}
- Relevance reasoning: {topic.reasoning}

**Boolean queries to use:**
{queries_formatted}

Call openalex_precision_search with the topic_id and the boolean_queries above.
Return the list of WorkResult objects from the search."""

    def _register_tools(self) -> None:
        @self.agent.tool_plain
        async def openalex_precision_search_tool(
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
            """
            return await openalex_precision_search(
                topic_id=topic_id,
                topic_name=topic_name,
                boolean_queries=boolean_queries,
                max_results=max_results,
            )

    def _register_prompts(self) -> None:
        @self.agent.system_prompt
        def system_prompt() -> str:
            return (
                "You are a research librarian specializing in academic literature retrieval.\n"
                "Your task is to find the most relevant scientific papers for a given research topic.\n\n"
                "Use the openalex_precision_search_tool with the provided topic_id and boolean_queries.\n"
                "The boolean queries use OpenAlex syntax: AND/OR/NOT uppercase, phrases in quotes, "
                "wildcards (min 3 chars before *), proximity operator (~N).\n\n"
                "Return all WorkResult objects from the search — do not filter or rank them yourself."
            )
