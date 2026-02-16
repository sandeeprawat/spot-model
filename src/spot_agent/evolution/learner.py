"""Learning engine — uses LLM to analyze failures and generate new tools."""

from __future__ import annotations

from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI

from spot_agent.config import LLMConfig
from spot_agent.evolution.engine import SelfEvolutionEngine
from spot_agent.evolution.tracker import CapabilityTracker
from spot_agent.logging import get_logger

log = get_logger(__name__)

TOOL_GENERATION_PROMPT = """You are a Python developer creating a new tool plugin for an AI agent.

The agent needs a tool with these requirements:
{requirements}

Create a Python class that extends BaseTool with the following structure:

```python
from __future__ import annotations
from typing import Any
from spot_agent.tools.base import BaseTool

class {class_name}(BaseTool):
    @property
    def name(self) -> str:
        return "{tool_name}"

    @property
    def description(self) -> str:
        return "{description}"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {{
            "type": "object",
            "properties": {{
                # Define parameters here
            }},
            "required": []
        }}

    async def execute(self, **kwargs: Any) -> Any:
        # Implement the tool logic here
        pass
```

Return ONLY the Python code, no markdown fences or explanations.
The code must be self-contained and importable."""


class LearningEngine:
    """Analyzes agent performance and generates new tools to fill capability gaps."""

    def __init__(
        self,
        llm_config: LLMConfig,
        evolution_engine: SelfEvolutionEngine,
        tracker: CapabilityTracker,
    ) -> None:
        self.llm_config = llm_config
        self.evolution = evolution_engine
        self.tracker = tracker

        if getattr(llm_config, "provider", "openai") == "azure_openai":
            self._llm: AsyncOpenAI | AsyncAzureOpenAI = AsyncAzureOpenAI(
                api_key=llm_config.api_key,
                azure_endpoint=llm_config.api_base or "",
                api_version="2024-02-01",
            )
        else:
            client_kwargs: dict[str, Any] = {"api_key": llm_config.api_key}
            if llm_config.api_base:
                client_kwargs["base_url"] = llm_config.api_base
            self._llm = AsyncOpenAI(**client_kwargs)

    async def analyze_and_evolve(self) -> list[dict[str, Any]]:
        """Analyze capability gaps and attempt to create new tools."""
        results = []

        gaps = self.tracker.get_capability_gaps()
        if not gaps:
            log.info("no_capability_gaps")
            return results

        # Group similar gaps
        unique_gaps = {g["missing"] for g in gaps}

        for gap in unique_gaps:
            try:
                result = await self._create_tool_for_gap(gap)
                results.append(result)
            except Exception as exc:
                log.error("tool_creation_failed", gap=gap, error=str(exc))
                results.append({"gap": gap, "success": False, "error": str(exc)})

        return results

    async def _create_tool_for_gap(self, capability_description: str) -> dict[str, Any]:
        """Use LLM to generate a tool that fills a capability gap."""
        # Generate a tool name from the description
        tool_name = capability_description.lower().replace(" ", "_")[:30]
        class_name = "".join(w.capitalize() for w in capability_description.split()[:4]) + "Tool"

        prompt = TOOL_GENERATION_PROMPT.format(
            requirements=capability_description,
            class_name=class_name,
            tool_name=tool_name,
            description=capability_description,
        )

        response = await self._llm.chat.completions.create(
            model=self.llm_config.model,
            messages=[
                {"role": "system", "content": "You are an expert Python developer. Generate clean, working code."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.2,
        )

        code = response.choices[0].message.content or ""

        # Clean up code (remove markdown fences if present)
        if "```python" in code:
            code = code.split("```python", 1)[1].rsplit("```", 1)[0]
        elif "```" in code:
            code = code.split("```", 1)[1].rsplit("```", 1)[0]
        code = code.strip()

        result = await self.evolution.create_tool(
            tool_name=tool_name,
            tool_description=capability_description,
            tool_code=code,
        )

        log.info("tool_generated", tool_name=tool_name, success=result.get("success"))
        return {"gap": capability_description, **result}

    async def suggest_improvements(self) -> list[dict[str, str]]:
        """Analyze underperforming tools and suggest improvements."""
        underperforming = self.tracker.get_underperforming_tools()
        if not underperforming:
            return []

        suggestions = []
        stats = self.tracker.get_tool_stats()
        failures = self.tracker.get_recent_failures()

        for tool_name in underperforming:
            tool_stats = stats[tool_name]
            tool_failures = [f for f in failures if f["tool"] == tool_name]
            error_summary = "; ".join(f["error"] for f in tool_failures[:3])

            suggestions.append({
                "tool": tool_name,
                "success_rate": str(tool_stats["success_rate"]),
                "common_errors": error_summary,
                "suggestion": f"Tool '{tool_name}' has {tool_stats['success_rate']:.0%} success rate. Consider reviewing error patterns: {error_summary}",
            })

        return suggestions
