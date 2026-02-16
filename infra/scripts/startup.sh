#!/bin/bash
# Cloud-init startup script for SPOT Agent VM
set -euo pipefail

LOG_FILE="/var/log/spot-agent-startup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== SPOT Agent Startup $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Setup agent directory
AGENT_DIR="/opt/spot-agent"
mkdir -p "$AGENT_DIR/plugins" "$AGENT_DIR/data"

# Pull latest agent image and start
cd "$AGENT_DIR"

# Start the eviction monitor as a systemd service
cat > /etc/systemd/system/spot-agent-eviction.service <<EOF
[Unit]
Description=SPOT Agent Eviction Monitor
After=docker.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 -c "
import urllib.request, json, time, subprocess, sys
IMDS_URL = 'http://169.254.169.254/metadata/scheduledevents?api-version=2020-07-01'
while True:
    try:
        req = urllib.request.Request(IMDS_URL, headers={'Metadata': 'true'})
        resp = urllib.request.urlopen(req, timeout=2)
        data = json.loads(resp.read())
        for event in data.get('Events', []):
            if event.get('EventType') == 'Preempt':
                print(f'EVICTION DETECTED: {event}', flush=True)
                subprocess.run(['/opt/spot-agent/shutdown.sh'], check=False)
                sys.exit(0)
    except Exception:
        pass
    time.sleep(5)
"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable spot-agent-eviction
systemctl start spot-agent-eviction

echo "=== SPOT Agent Startup Complete ==="
