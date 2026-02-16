"""Tests for built-in tools."""

from __future__ import annotations

import os
import tempfile

import pytest

from spot_agent.tools.base import BaseTool
from spot_agent.tools.builtin.code_executor import CodeExecutorTool
from spot_agent.tools.builtin.file_ops import FileOpsTool
from spot_agent.tools.builtin.shell import ShellTool
from spot_agent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_code_executor_python():
    tool = CodeExecutorTool()
    result = await tool.execute(code="print('hello world')")
    assert result["exit_code"] == 0
    assert "hello world" in result["stdout"]


@pytest.mark.asyncio
async def test_code_executor_python_error():
    tool = CodeExecutorTool()
    result = await tool.execute(code="raise ValueError('test error')")
    assert result["exit_code"] != 0
    assert "test error" in result["stderr"]


@pytest.mark.asyncio
async def test_file_ops_write_and_read():
    tool = FileOpsTool()
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test.txt")
        
        # Write
        write_result = await tool.execute(operation="write", path=filepath, content="Hello, World!")
        assert write_result["written"] == 13
        
        # Read
        read_result = await tool.execute(operation="read", path=filepath)
        assert read_result["content"] == "Hello, World!"


@pytest.mark.asyncio
async def test_file_ops_list_directory():
    tool = FileOpsTool()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files
        for name in ["a.txt", "b.txt"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("test")
        
        result = await tool.execute(operation="list", path=tmpdir)
        assert result["count"] == 2


@pytest.mark.asyncio
async def test_file_ops_read_nonexistent():
    tool = FileOpsTool()
    result = await tool.execute(operation="read", path="/nonexistent/file.txt")
    assert "error" in result


@pytest.mark.asyncio
async def test_shell_tool():
    tool = ShellTool()
    result = await tool.execute(command="python -c \"print('shell test')\"")
    assert result["exit_code"] == 0
    assert "shell test" in result["stdout"]


def test_tool_registry():
    registry = ToolRegistry()
    
    class DummyTool(BaseTool):
        @property
        def name(self): return "dummy"
        @property
        def description(self): return "A dummy tool"
        async def execute(self, **kwargs): return "ok"
    
    tool = DummyTool()
    registry.register(tool)
    
    assert registry.get_tool("dummy") is not None
    assert "dummy" in registry.get_tool_names()
    assert len(registry.list_tools()) == 1
    
    registry.unregister("dummy")
    assert registry.get_tool("dummy") is None


def test_register_builtin_tools():
    registry = ToolRegistry()
    registry.register_builtin_tools()
    
    assert registry.get_tool("execute_code") is not None
    assert registry.get_tool("file_ops") is not None
    assert registry.get_tool("shell") is not None
    assert registry.get_tool("web_search") is not None
    assert len(registry.list_tools()) == 4


def test_tool_openai_format():
    tool = CodeExecutorTool()
    openai_def = tool.to_openai_tool()
    
    assert openai_def["type"] == "function"
    assert openai_def["function"]["name"] == "execute_code"
    assert "parameters" in openai_def["function"]
