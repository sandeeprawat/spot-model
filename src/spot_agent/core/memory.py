"""Persistent memory for the autonomous agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure.storage.blob.aio import BlobServiceClient

from spot_agent.config import AzureConfig
from spot_agent.logging import get_logger

log = get_logger(__name__)


class AgentMemory:
    """Persistent memory storing conversation history and learned knowledge."""

    def __init__(self, config: AzureConfig | None = None) -> None:
        self.config = config
        self._credential: Any = None
        self._blob_client: BlobServiceClient | None = None
        self._conversation_history: list[dict[str, str]] = []
        self._task_outcomes: list[dict[str, Any]] = []
        self._learned_patterns: dict[str, Any] = {}

    async def _get_blob_client(self) -> BlobServiceClient:
        if self._blob_client is None:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            if self._credential is None:
                self._credential = DefaultAzureCredential()
            account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
            self._blob_client = BlobServiceClient(
                account_url=account_url, credential=self._credential
            )
        return self._blob_client

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self._conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def add_task_outcome(self, task_id: str, description: str, success: bool, result: Any = None, error: str | None = None) -> None:
        """Record a task outcome for learning."""
        self._task_outcomes.append({
            "task_id": task_id,
            "description": description,
            "success": success,
            "result": str(result) if result else None,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_conversation_history(self, limit: int = 50) -> list[dict[str, str]]:
        """Get recent conversation history."""
        return self._conversation_history[-limit:]

    def get_recent_outcomes(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent task outcomes."""
        return self._task_outcomes[-limit:]

    def get_context_for_llm(self, limit: int = 20) -> list[dict[str, str]]:
        """Get formatted context suitable for LLM messages."""
        messages = []
        for msg in self._conversation_history[-limit:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        return messages

    async def save(self) -> None:
        """Persist memory to Azure Blob Storage."""
        client = await self._get_blob_client()
        container = client.get_container_client(self.config.storage_container)
        try:
            await container.create_container()
        except Exception:
            pass

        memory_data = {
            "conversation_history": self._conversation_history,
            "task_outcomes": self._task_outcomes,
            "learned_patterns": self._learned_patterns,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        blob = container.get_blob_client("memory/agent_memory.json")
        await blob.upload_blob(json.dumps(memory_data, default=str), overwrite=True)
        log.info("memory_saved", messages=len(self._conversation_history))

    async def load(self) -> None:
        """Load memory from Azure Blob Storage."""
        try:
            client = await self._get_blob_client()
            container = client.get_container_client(self.config.storage_container)
            blob = container.get_blob_client("memory/agent_memory.json")
            download = await blob.download_blob()
            content = await download.readall()
            data = json.loads(content)

            self._conversation_history = data.get("conversation_history", [])
            self._task_outcomes = data.get("task_outcomes", [])
            self._learned_patterns = data.get("learned_patterns", {})
            log.info("memory_loaded", messages=len(self._conversation_history))
        except Exception:
            log.info("no_existing_memory_found")

    def to_dict(self) -> dict[str, Any]:
        """Serialize memory state."""
        return {
            "conversation_history": self._conversation_history,
            "task_outcomes": self._task_outcomes,
            "learned_patterns": self._learned_patterns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], config: AzureConfig | None = None) -> AgentMemory:
        """Restore memory from dict."""
        memory = cls(config)
        memory._conversation_history = data.get("conversation_history", [])
        memory._task_outcomes = data.get("task_outcomes", [])
        memory._learned_patterns = data.get("learned_patterns", {})
        return memory

    async def close(self) -> None:
        """Clean up resources."""
        if self._blob_client:
            await self._blob_client.close()
        if self._credential:
            await self._credential.close()
