FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Create plugins directory
RUN mkdir -p /app/plugins

# Set environment defaults
ENV AGENT_PLUGINS_DIR=/app/plugins
ENV AGENT_LOG_LEVEL=INFO

EXPOSE 8000

CMD ["uvicorn", "spot_agent.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
