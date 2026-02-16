"""Tests for the self-evolution engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from spot_agent.evolution.engine import SelfEvolutionEngine
from spot_agent.evolution.tracker import CapabilityTracker
from spot_agent.tools.registry import ToolRegistry


def test_capability_tracker_record():
    tracker = CapabilityTracker()
    tracker.record_tool_call("shell", success=True)
    tracker.record_tool_call("shell", success=True)
    tracker.record_tool_call("shell", success=False, error="timeout")

    stats = tracker.get_tool_stats()
    assert stats["shell"]["calls"] == 3
    assert stats["shell"]["successes"] == 2
    assert stats["shell"]["failures"] == 1
    assert stats["shell"]["success_rate"] == pytest.approx(0.667, abs=0.01)


def test_underperforming_tools():
    tracker = CapabilityTracker()
    for _ in range(5):
        tracker.record_tool_call("bad_tool", success=False, error="fail")
    tracker.record_tool_call("good_tool", success=True)

    underperforming = tracker.get_underperforming_tools(threshold=0.5)
    assert "bad_tool" in underperforming
    assert "good_tool" not in underperforming


def test_capability_gaps():
    tracker = CapabilityTracker()
    tracker.record_capability_gap("Parse PDF files", "pdf_parser")
    
    gaps = tracker.get_capability_gaps()
    assert len(gaps) == 1
    assert gaps[0]["missing"] == "pdf_parser"


def test_tracker_serialization():
    tracker = CapabilityTracker()
    tracker.record_tool_call("test", success=True)
    tracker.record_capability_gap("test gap", "test_tool")

    data = tracker.to_dict()
    restored = CapabilityTracker.from_dict(data)
    
    assert restored.get_tool_stats()["test"]["calls"] == 1
    assert len(restored.get_capability_gaps()) == 1


@pytest.mark.asyncio
async def test_evolution_engine_create_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry()
        engine = SelfEvolutionEngine(tmpdir, registry)

        tool_code = '''
from __future__ import annotations
from typing import Any
from spot_agent.tools.base import BaseTool

class GreeterTool(BaseTool):
    @property
    def name(self) -> str:
        return "greeter"

    @property
    def description(self) -> str:
        return "Greets a person"

    async def execute(self, name: str = "World", **kwargs: Any) -> str:
        return f"Hello, {name}!"
'''

        result = await engine.create_tool("greeter", "Greets a person", tool_code)
        assert result["success"] is True
        assert registry.get_tool("greeter") is not None

        # Verify the tool works
        tool = registry.get_tool("greeter")
        greeting = await tool.execute(name="Agent")
        assert greeting == "Hello, Agent!"


@pytest.mark.asyncio
async def test_evolution_engine_remove_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry()
        engine = SelfEvolutionEngine(tmpdir, registry)

        tool_code = '''
from __future__ import annotations
from typing import Any
from spot_agent.tools.base import BaseTool

class TempTool(BaseTool):
    @property
    def name(self) -> str:
        return "temp_tool"
    @property
    def description(self) -> str:
        return "Temporary"
    async def execute(self, **kwargs: Any) -> str:
        return "temp"
'''

        await engine.create_tool("temp_tool", "Temporary", tool_code)
        assert registry.get_tool("temp_tool") is not None

        result = await engine.remove_tool("temp_tool")
        assert result["success"] is True
        assert registry.get_tool("temp_tool") is None


def test_load_existing_plugins():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a plugin file
        plugin_path = Path(tmpdir) / "sample_plugin.py"
        plugin_path.write_text('''
from __future__ import annotations
from typing import Any
from spot_agent.tools.base import BaseTool

class SamplePlugin(BaseTool):
    @property
    def name(self) -> str:
        return "sample"
    @property
    def description(self) -> str:
        return "Sample plugin"
    async def execute(self, **kwargs: Any) -> str:
        return "sample"
''', encoding="utf-8")

        registry = ToolRegistry()
        engine = SelfEvolutionEngine(tmpdir, registry)
        loaded = engine.load_existing_plugins()
        
        assert loaded == 1
        assert registry.get_tool("sample") is not None
