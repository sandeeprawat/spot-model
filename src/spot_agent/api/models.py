"""API request/response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriorityEnum(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskRequest(BaseModel):
    """Request to submit a new task."""
    description: str = Field(description="Task description / instructions for the agent")
    priority: TaskPriorityEnum = Field(default=TaskPriorityEnum.NORMAL, description="Task priority")
    parent_id: str | None = Field(default=None, description="Parent task ID for follow-up conversations")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TaskResponse(BaseModel):
    """Response for a single task."""
    id: str
    description: str
    status: TaskStatusEnum
    priority: str
    result: Any = None
    error: str | None = None
    parent_id: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retries: int = 0


class TaskListResponse(BaseModel):
    """Response for listing tasks."""
    tasks: list[TaskResponse]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    agent_name: str = ""
    uptime_seconds: float = 0.0
    tasks_completed: int = 0
    tasks_pending: int = 0
    tools_available: int = 0


class CheckpointResponse(BaseModel):
    """Response for checkpoint operation."""
    success: bool
    message: str


class EvolutionStatusResponse(BaseModel):
    """Response for evolution status."""
    plugins_loaded: int = 0
    capability_gaps: int = 0
    tool_stats: dict[str, Any] = Field(default_factory=dict)
