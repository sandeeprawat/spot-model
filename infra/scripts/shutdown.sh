#!/bin/bash
# Graceful shutdown script — checkpoint agent state before eviction
set -euo pipefail

LOG_FILE="/var/log/spot-agent-shutdown.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== SPOT Agent Shutdown $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

AGENT_DIR="/opt/spot-agent"

# Signal the agent to checkpoint
echo "Triggering agent checkpoint..."
curl -s -X POST http://localhost:8000/checkpoint || true

# Wait briefly for checkpoint to complete (we have ~30s)
sleep 10

# Stop the agent container gracefully
echo "Stopping agent container..."
cd "$AGENT_DIR"
docker-compose down --timeout 15 || true

echo "=== SPOT Agent Shutdown Complete ==="
