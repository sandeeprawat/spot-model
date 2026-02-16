"""Tests for the task queue."""

from __future__ import annotations

from spot_agent.core.task_queue import Task, TaskPriority, TaskQueue, TaskStatus


def test_submit_task():
    queue = TaskQueue()
    task = queue.submit("Test task")
    assert task.description == "Test task"
    assert task.status == TaskStatus.PENDING
    assert task.priority == TaskPriority.NORMAL


def test_next_returns_highest_priority():
    queue = TaskQueue()
    low = queue.submit("Low priority", TaskPriority.LOW)
    high = queue.submit("High priority", TaskPriority.HIGH)
    normal = queue.submit("Normal priority", TaskPriority.NORMAL)

    next_task = queue.next()
    assert next_task is not None
    assert next_task.id == high.id


def test_mark_completed():
    queue = TaskQueue()
    task = queue.submit("Complete me")
    queue.mark_in_progress(task.id)
    queue.mark_completed(task.id, result="Done!")

    updated = queue.get(task.id)
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.result == "Done!"
    assert updated.completed_at is not None


def test_mark_failed_with_retries():
    queue = TaskQueue()
    task = queue.submit("Fail me")
    task.max_retries = 2

    queue.mark_failed(task.id, "Error 1")
    assert task.status == TaskStatus.PENDING  # retries left
    assert task.retries == 1

    queue.mark_failed(task.id, "Error 2")
    assert task.status == TaskStatus.FAILED  # no retries left
    assert task.retries == 2


def test_next_returns_none_when_empty():
    queue = TaskQueue()
    assert queue.next() is None


def test_serialization_roundtrip():
    queue = TaskQueue()
    queue.submit("Task 1", TaskPriority.HIGH)
    queue.submit("Task 2", TaskPriority.LOW)

    data = queue.to_dict()
    restored = TaskQueue.from_dict(data)
    assert len(restored.list_all()) == 2


def test_list_all():
    queue = TaskQueue()
    queue.submit("A")
    queue.submit("B")
    queue.submit("C")
    assert len(queue.list_all()) == 3
