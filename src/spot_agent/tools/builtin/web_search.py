"""Web search tool using Bing Search API with DuckDuckGo fallback."""

from __future__ import annotations

import os
from typing import Any

import httpx

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool

log = get_logger(__name__)


class WebSearchTool(BaseTool):
    """Search the web for information. Uses Bing Search API if configured, otherwise DuckDuckGo (free, no key needed)."""

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
        """Execute a web search. Uses Bing if API key is set, otherwise DuckDuckGo."""
        api_key = os.environ.get("BING_SEARCH_API_KEY")
        if api_key:
            return await self._search_bing(query, count, api_key)
        return await self._search_duckduckgo(query, count)

    async def _search_bing(self, query: str, count: int, api_key: str) -> list[dict[str, str]]:
        """Search using Bing Search API."""
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
            log.info("bing_search_completed", query=query, results=len(results))
            return results
        except Exception as exc:
            log.error("bing_search_error", query=query, error=str(exc))
            # Fall back to DuckDuckGo on Bing failure
            log.info("falling_back_to_duckduckgo")
            return await self._search_duckduckgo(query, count)

    async def _search_duckduckgo(self, query: str, count: int) -> list[dict[str, str]]:
        """Search using DuckDuckGo (free, no API key needed)."""
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=count))

            results = []
            for item in raw_results:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                })
            log.info("duckduckgo_search_completed", query=query, results=len(results))
            return results
        except Exception as exc:
            log.error("duckduckgo_search_error", query=query, error=str(exc))
            return [{"error": f"Web search failed: {exc}"}]
