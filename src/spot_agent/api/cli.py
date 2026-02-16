"""CLI interface for the SPOT Agent."""

from __future__ import annotations

import json
import sys

import click
import httpx


DEFAULT_BASE_URL = "http://localhost:8000"


@click.group()
@click.option("--base-url", default=DEFAULT_BASE_URL, help="Agent API base URL")
@click.pass_context
def main(ctx: click.Context, base_url: str) -> None:
    """SPOT Agent — Autonomous AI Agent on Azure SPOT VMs."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url


@main.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Start the agent server."""
    import uvicorn
    click.echo("Starting SPOT Agent server...")
    uvicorn.run(
        "spot_agent.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


@main.group()
@click.pass_context
def task(ctx: click.Context) -> None:
    """Task management commands."""
    pass


@task.command("submit")
@click.argument("description")
@click.option("--priority", type=click.Choice(["low", "normal", "high", "critical"]), default="normal")
@click.pass_context
def task_submit(ctx: click.Context, description: str, priority: str) -> None:
    """Submit a new task to the agent."""
    base_url = ctx.obj["base_url"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{base_url}/tasks",
                json={"description": description, "priority": priority},
            )
            resp.raise_for_status()
            data = resp.json()
            click.echo(f"Task submitted: {data['id']}")
            click.echo(f"  Status: {data['status']}")
            click.echo(f"  Priority: {data['priority']}")
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to agent. Is it running?", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@task.command("status")
@click.argument("task_id")
@click.pass_context
def task_status(ctx: click.Context, task_id: str) -> None:
    """Check the status of a task."""
    base_url = ctx.obj["base_url"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}/tasks/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            click.echo(f"Task: {data['id']}")
            click.echo(f"  Description: {data['description']}")
            click.echo(f"  Status: {data['status']}")
            click.echo(f"  Priority: {data['priority']}")
            if data.get("result"):
                click.echo(f"  Result: {data['result']}")
            if data.get("error"):
                click.echo(f"  Error: {data['error']}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            click.echo(f"Task '{task_id}' not found", err=True)
        else:
            click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to agent. Is it running?", err=True)
        sys.exit(1)


@task.command("list")
@click.pass_context
def task_list(ctx: click.Context) -> None:
    """List all tasks."""
    base_url = ctx.obj["base_url"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}/tasks")
            resp.raise_for_status()
            data = resp.json()

            if not data["tasks"]:
                click.echo("No tasks found.")
                return

            click.echo(f"{'ID':<10} {'Status':<14} {'Priority':<10} Description")
            click.echo("-" * 70)
            for t in data["tasks"]:
                desc = t["description"][:40]
                click.echo(f"{t['id']:<10} {t['status']:<14} {t['priority']:<10} {desc}")
            click.echo(f"\nTotal: {data['total']} tasks")
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to agent. Is it running?", err=True)
        sys.exit(1)


@main.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check agent health."""
    base_url = ctx.obj["base_url"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}/health")
            resp.raise_for_status()
            data = resp.json()
            click.echo(f"Status: {data['status']}")
            click.echo(f"Agent: {data['agent_name']}")
            click.echo(f"Uptime: {data['uptime_seconds']}s")
            click.echo(f"Tasks completed: {data['tasks_completed']}")
            click.echo(f"Tasks pending: {data['tasks_pending']}")
            click.echo(f"Tools available: {data['tools_available']}")
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to agent. Is it running?", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
