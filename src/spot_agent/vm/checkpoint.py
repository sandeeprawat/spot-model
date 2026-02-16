"""Checkpoint management — serialize/deserialize agent state to Azure Blob Storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from azure.storage.blob.aio import BlobServiceClient

from spot_agent.config import AzureConfig
from spot_agent.logging import get_logger

log = get_logger(__name__)

CHECKPOINT_BLOB_NAME = "checkpoint/latest.json"


class CheckpointManager:
    """Manages agent state checkpoints in Azure Blob Storage."""

    def __init__(self, config: AzureConfig) -> None:
        self.config = config
        self._credential: Any = None
        self._blob_client: BlobServiceClient | None = None

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

    async def save_checkpoint(self, state: dict[str, Any]) -> None:
        """Save agent state to Azure Blob Storage."""
        client = await self._get_blob_client()
        container = client.get_container_client(self.config.storage_container)

        # Ensure container exists
        try:
            await container.create_container()
        except Exception:
            pass  # Container already exists

        checkpoint_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state,
        }

        blob = container.get_blob_client(CHECKPOINT_BLOB_NAME)
        await blob.upload_blob(
            json.dumps(checkpoint_data, default=str),
            overwrite=True,
        )
        log.info("checkpoint_saved", timestamp=checkpoint_data["timestamp"])

    async def load_checkpoint(self) -> dict[str, Any] | None:
        """Load the latest checkpoint from Azure Blob Storage."""
        try:
            client = await self._get_blob_client()
            container = client.get_container_client(self.config.storage_container)
            blob = container.get_blob_client(CHECKPOINT_BLOB_NAME)

            download = await blob.download_blob()
            content = await download.readall()
            checkpoint_data = json.loads(content)

            log.info(
                "checkpoint_loaded",
                timestamp=checkpoint_data.get("timestamp"),
            )
            return checkpoint_data.get("state")
        except Exception as exc:
            log.info("no_checkpoint_found", reason=str(exc))
            return None

    async def delete_checkpoint(self) -> None:
        """Delete the current checkpoint."""
        try:
            client = await self._get_blob_client()
            container = client.get_container_client(self.config.storage_container)
            blob = container.get_blob_client(CHECKPOINT_BLOB_NAME)
            await blob.delete_blob()
            log.info("checkpoint_deleted")
        except Exception:
            pass

    async def close(self) -> None:
        """Clean up resources."""
        if self._blob_client:
            await self._blob_client.close()
        if self._credential:
            await self._credential.close()
