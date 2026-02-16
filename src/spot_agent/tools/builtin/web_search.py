"""Web search tool using Bing Search API or fallback."""

from __future__ import annotations

import os
from typing import Any

import httpx

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool

log = get_logger(__name__)


class WebSearchTool(BaseTool):
    """Search the web for information using Bing Search API."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for information. Returns search results with titles, URLs, and snippets."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, count: int = 5, **kwargs: Any) -> list[dict[str, str]]:
        """Execute a web search."""
        api_key = os.environ.get("BING_SEARCH_API_KEY")
        if not api_key:
            log.warning("bing_api_key_not_set")
            return [{"error": "BING_SEARCH_API_KEY not configured. Set the environment variable to enable web search."}]

        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {"q": query, "count": count, "textFormat": "Raw"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                })
            log.info("web_search_completed", query=query, results=len(results))
            return results
        except Exception as exc:
            log.error("web_search_error", query=query, error=str(exc))
            return [{"error": str(exc)}]
