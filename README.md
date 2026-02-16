# SPOT Agent

Autonomous AI Agent running on Azure SPOT VMs for cost-efficient 24/7 operation.

## Features

- **Autonomous Execution**: ReAct-style agent loop that runs tasks independently
- **Azure SPOT VM**: Up to 90% cost savings with automatic eviction handling
- **Tool System**: Extensible tools + MCP server integration
- **Self-Evolution**: Agent can write and register new tools dynamically
- **24/7 Operation**: Automatic checkpoint/resume across SPOT VM evictions

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your Azure and LLM credentials

# Run locally
spot-agent start

# Submit a task
spot-agent task submit "Write a Python function to sort a list"

# Check task status
spot-agent task status <task-id>
```

## Architecture

The agent consists of:
- **Agent Core**: ReAct loop with LLM-powered reasoning
- **SPOT VM Manager**: Azure SPOT VM lifecycle with eviction handling
- **Tool System**: Pluggable tools + MCP client for external tool servers
- **Self-Evolution**: Dynamic plugin creation and capability growth
- **Task API**: FastAPI server + CLI for task submission and monitoring

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/
```
