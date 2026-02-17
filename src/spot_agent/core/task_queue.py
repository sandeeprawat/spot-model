"""Task queue management for the autonomous agent."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Status of a task in the queue."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    """A unit of work for the agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str | None = None
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    result: Any = None
    error: str | None = None
    parent_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retries: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "result": self.result,
            "error": self.error,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Deserialize task from dictionary."""
        return cls(
            id=data["id"],
            title=data.get("title"),
            description=data["description"],
            status=TaskStatus(data["status"]),
            priority=TaskPriority(data["priority"]),
            result=data.get("result"),
            error=data.get("error"),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
        )


class TaskQueue:
    """Priority-based task queue for the agent."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def submit(self, description: str, priority: TaskPriority = TaskPriority.NORMAL, parent_id: str | None = None, title: str | None = None, **metadata: Any) -> Task:
        """Submit a new task to the queue."""
        task = Task(description=description, priority=priority, parent_id=parent_id, title=title, metadata=metadata)
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_conversation_chain(self, task_id: str) -> list[Task]:
        """Get the full conversation chain for a task (oldest first)."""
        chain: list[Task] = []
        current = self._tasks.get(task_id)
        while current:
            chain.append(current)
            current = self._tasks.get(current.parent_id) if current.parent_id else None
        chain.reverse()
        return chain

    def next(self) -> Task | None:
        """Get the next pending task by priority."""
        pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
        if not pending:
            return None
        pending.sort(key=lambda t: (-t.priority.value, t.created_at))
        return pending[0]

    def mark_in_progress(self, task_id: str) -> None:
        """Mark a task as in progress."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now(timezone.utc)

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.retries += 1
            if task.retries < task.max_retries:
                task.status = TaskStatus.PENDING
                task.error = error
            else:
                task.status = TaskStatus.FAILED
                task.error = error
                task.completed_at = datetime.now(timezone.utc)

    def list_all(self) -> list[Task]:
        """List all tasks."""
        return list(self._tasks.values())

    def to_dict(self) -> list[dict[str, Any]]:
        """Serialize all tasks."""
        return [t.to_dict() for t in self._tasks.values()]

    @classmethod
    def from_dict(cls, data: list[dict[str, Any]]) -> TaskQueue:
        """Deserialize task queue."""
        queue = cls()
        for item in data:
            task = Task.from_dict(item)
            queue._tasks[task.id] = task
        return queue
