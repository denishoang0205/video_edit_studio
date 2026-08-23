from typing import Any
from src.crewai_core.domain.interfaces.tool import ITool, ToolResult


class MockWebSearchTool(ITool):
    """Simulated Web Search Tool for Agent Information Retrieval."""

    name: str = "web_search"
    description: str = "Searches the web for up-to-date facts, documentation, and technical knowledge."
    parameters_schema: dict = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."}
        },
        "required": ["query"]
    }

    async def run(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        if not query.strip():
            return ToolResult(success=False, output="", error="Query parameter cannot be empty.")

        simulated_results = (
            f"Search Results for '{query}':\n"
            f"1. [Documentation]: Best practices and clean architectural design patterns.\n"
            f"2. [Industry Report]: Multi-Agent Orchestration increases autonomous workflow throughput by 4x.\n"
            f"3. [Benchmark]: Asynchronous queueing (Redis/Celery) prevents bottlenecks in LLM workloads."
        )
        return ToolResult(success=True, output=simulated_results)
