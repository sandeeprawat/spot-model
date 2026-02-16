"""Capability tracker — monitors tool usage and identifies gaps."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from spot_agent.logging import get_logger

log = get_logger(__name__)


class CapabilityTracker:
    """Tracks tool usage, success rates, and identifies capability gaps."""

    def __init__(self) -> None:
        self._tool_usage: dict[str, dict[str, int]] = defaultdict(
            lambda: {"calls": 0, "successes": 0, "failures": 0}
        )
        self._failed_requests: list[dict[str, Any]] = []
        self._capability_gaps: list[dict[str, Any]] = []

    def record_tool_call(self, tool_name: str, success: bool, error: str | None = None) -> None:
        """Record a tool invocation outcome."""
        stats = self._tool_usage[tool_name]
        stats["calls"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
            if error:
                self._failed_requests.append({
                    "tool": tool_name,
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    def record_capability_gap(self, task_description: str, missing_capability: str) -> None:
        """Record when the agent couldn't complete a task due to missing capability."""
        self._capability_gaps.append({
            "task": task_description,
            "missing": missing_capability,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        log.info("capability_gap_recorded", missing=missing_capability)

    def get_tool_stats(self) -> dict[str, dict[str, Any]]:
        """Get usage statistics for all tools."""
        stats = {}
        for name, data in self._tool_usage.items():
            total = data["calls"]
            success_rate = data["successes"] / total if total > 0 else 0.0
            stats[name] = {
                **data,
                "success_rate": round(success_rate, 3),
            }
        return stats

    def get_underperforming_tools(self, threshold: float = 0.5) -> list[str]:
        """Get tools with success rate below threshold."""
        return [
            name
            for name, stats in self.get_tool_stats().items()
            if stats["success_rate"] < threshold and stats["calls"] >= 3
        ]

    def get_capability_gaps(self) -> list[dict[str, Any]]:
        """Get recorded capability gaps."""
        return self._capability_gaps

    def get_recent_failures(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent failure records."""
        return self._failed_requests[-limit:]

    def to_dict(self) -> dict[str, Any]:
        """Serialize tracker state."""
        return {
            "tool_usage": dict(self._tool_usage),
            "failed_requests": self._failed_requests,
            "capability_gaps": self._capability_gaps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityTracker:
        """Restore from serialized state."""
        tracker = cls()
        for name, stats in data.get("tool_usage", {}).items():
            tracker._tool_usage[name] = stats
        tracker._failed_requests = data.get("failed_requests", [])
        tracker._capability_gaps = data.get("capability_gaps", [])
        return tracker
