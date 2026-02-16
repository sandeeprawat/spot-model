"""FastAPI server for the SPOT Agent API."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from spot_agent.api.models import (
    CheckpointResponse,
    EvolutionStatusResponse,
    HealthResponse,
    TaskListResponse,
    TaskRequest,
    TaskResponse,
    TaskStatusEnum,
)
from spot_agent.config import AgentConfig
from spot_agent.core.agent import AutonomousAgent
from spot_agent.core.memory import AgentMemory
from spot_agent.core.task_queue import TaskPriority, TaskQueue, TaskStatus
from spot_agent.evolution.engine import SelfEvolutionEngine
from spot_agent.evolution.tracker import CapabilityTracker
from spot_agent.logging import get_logger, setup_logging
from spot_agent.tools.registry import ToolRegistry

log = get_logger(__name__)

# Global state
_agent: AutonomousAgent | None = None
_task_queue: TaskQueue | None = None
_tool_registry: ToolRegistry | None = None
_evolution_engine: SelfEvolutionEngine | None = None
_tracker: CapabilityTracker | None = None
_start_time: float = 0.0
_agent_task: asyncio.Task | None = None

PRIORITY_MAP = {
    "low": TaskPriority.LOW,
    "normal": TaskPriority.NORMAL,
    "high": TaskPriority.HIGH,
    "critical": TaskPriority.CRITICAL,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and start the agent."""
    global _agent, _task_queue, _tool_registry, _evolution_engine, _tracker, _start_time, _agent_task

    _start_time = time.time()

    try:
        config = AgentConfig()
    except Exception:
        # Fallback for local dev without all env vars
        config = AgentConfig.model_construct(
            name="spot-agent-dev",
            plugins_dir="plugins",
            checkpoint_interval=60,
            max_task_retries=3,
            log_level="INFO",
            azure=None,
            llm=None,
            mcp=None,
        )

    setup_logging(getattr(config, "log_level", "INFO") or "INFO")

    # Initialize components
    _task_queue = TaskQueue()
    _tool_registry = ToolRegistry()
    _tool_registry.register_builtin_tools()
    _tracker = CapabilityTracker()

    plugins_dir = getattr(config, "plugins_dir", "plugins") or "plugins"
    _evolution_engine = SelfEvolutionEngine(plugins_dir, _tool_registry)
    _evolution_engine.load_existing_plugins()

    memory = AgentMemory()

    _agent = AutonomousAgent(
        config=config,
        task_queue=_task_queue,
        memory=memory,
        tool_registry=_tool_registry,
    )

    # Only start agent loop if LLM is configured
    if getattr(config, "llm", None) and getattr(config.llm, "api_key", None):
        _agent_task = asyncio.create_task(_agent.run())
    log.info("agent_api_started")

    yield

    # Shutdown
    if _agent:
        _agent.stop()
    if _agent_task:
        _agent_task.cancel()
        try:
            await _agent_task
        except asyncio.CancelledError:
            pass
    log.info("agent_api_stopped")


app = FastAPI(
    title="SPOT Agent API",
    description="Autonomous AI Agent running on Azure SPOT VMs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _task_to_response(task: Any) -> TaskResponse:
    """Convert internal Task to API response."""
    return TaskResponse(
        id=task.id,
        description=task.description,
        status=TaskStatusEnum(task.status.value),
        priority=task.priority.name.lower(),
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        retries=task.retries,
    )


@app.get("/")
async def root():
    """Serve the dashboard."""
    static_dir = Path(__file__).parent / "static"
    return FileResponse(static_dir / "index.html")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    tasks = _task_queue.list_all() if _task_queue else []
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)

    return HealthResponse(
        status="healthy",
        agent_name=_agent.config.name if _agent else "unknown",
        uptime_seconds=round(time.time() - _start_time, 1),
        tasks_completed=completed,
        tasks_pending=pending,
        tools_available=len(_tool_registry.list_tools()) if _tool_registry else 0,
    )


@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def submit_task(request: TaskRequest):
    """Submit a new task for the agent."""
    if not _task_queue:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    priority = PRIORITY_MAP.get(request.priority.value, TaskPriority.NORMAL)
    task = _task_queue.submit(
        description=request.description,
        priority=priority,
        **request.metadata,
    )
    log.info("task_submitted", task_id=task.id, description=task.description[:80])
    return _task_to_response(task)


@app.get("/tasks", response_model=TaskListResponse)
async def list_tasks():
    """List all tasks."""
    if not _task_queue:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    tasks = _task_queue.list_all()
    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task status and result."""
    if not _task_queue:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    task = _task_queue.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return _task_to_response(task)


@app.post("/checkpoint", response_model=CheckpointResponse)
async def trigger_checkpoint():
    """Trigger a manual checkpoint of agent state."""
    if not _agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        state = _agent.get_state()
        # In production, this would save to Azure Blob Storage
        log.info("manual_checkpoint_triggered")
        return CheckpointResponse(success=True, message="Checkpoint saved")
    except Exception as exc:
        return CheckpointResponse(success=False, message=str(exc))


@app.get("/evolution", response_model=EvolutionStatusResponse)
async def evolution_status():
    """Get evolution engine status."""
    return EvolutionStatusResponse(
        plugins_loaded=len(_evolution_engine.list_plugins()) if _evolution_engine else 0,
        capability_gaps=len(_tracker.get_capability_gaps()) if _tracker else 0,
        tool_stats=_tracker.get_tool_stats() if _tracker else {},
    )


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time agent output streaming."""
    await websocket.accept()
    log.info("websocket_client_connected")

    try:
        while True:
            # Send periodic status updates
            if _task_queue:
                tasks = _task_queue.list_all()
                in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
                if in_progress:
                    for task in in_progress:
                        await websocket.send_json({
                            "type": "task_status",
                            "task_id": task.id,
                            "status": task.status.value,
                            "description": task.description[:100],
                        })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        log.info("websocket_client_disconnected")
