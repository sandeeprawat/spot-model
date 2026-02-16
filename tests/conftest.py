"""Shared test fixtures for SPOT Agent."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_llm_response():
    """Return a factory for mock LLM responses."""
    def _make(content: str = "I'll help with that.", tool_calls: list | None = None):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls or [],
                    }
                }
            ]
        }
    return _make
