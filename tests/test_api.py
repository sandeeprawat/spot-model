"""Tests for the API server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the API with lifespan."""
    # Import here to avoid startup issues
    from spot_agent.api.server import app
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_submit_task(client):
    resp = client.post("/tasks", json={
        "description": "Test task",
        "priority": "normal",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Test task"
    assert data["status"] == "pending"
    assert "id" in data


def test_list_tasks(client):
    # Submit a task first
    client.post("/tasks", json={"description": "Listed task"})
    
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_get_task(client):
    # Submit and then retrieve
    submit_resp = client.post("/tasks", json={"description": "Get me"})
    task_id = submit_resp.json()["id"]
    
    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


def test_get_nonexistent_task(client):
    resp = client.get("/tasks/nonexistent")
    assert resp.status_code == 404


def test_evolution_endpoint(client):
    resp = client.get("/evolution")
    assert resp.status_code == 200
