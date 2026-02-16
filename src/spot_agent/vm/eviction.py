"""SPOT VM eviction detection via Azure Instance Metadata Service."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from spot_agent.logging import get_logger

log = get_logger(__name__)

IMDS_SCHEDULED_EVENTS_URL = (
    "http://169.254.169.254/metadata/scheduledevents?api-version=2020-07-01"
)
IMDS_HEADERS = {"Metadata": "true"}


class EvictionMonitor:
    """Monitors Azure IMDS Scheduled Events for SPOT VM eviction notices."""

    def __init__(
        self,
        on_eviction: Callable[[], Awaitable[None]],
        poll_interval: float = 5.0,
    ) -> None:
        self._on_eviction = on_eviction
        self._poll_interval = poll_interval
        self._running = False
        self._eviction_detected = False

    async def check_for_eviction(self) -> bool:
        """Poll IMDS for scheduled eviction events."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(IMDS_SCHEDULED_EVENTS_URL, headers=IMDS_HEADERS)
                resp.raise_for_status()
                data = resp.json()

            for event in data.get("Events", []):
                if event.get("EventType") == "Preempt":
                    log.warning(
                        "eviction_event_detected",
                        event_id=event.get("EventId"),
                        not_before=event.get("NotBefore"),
                    )
                    return True
        except httpx.HTTPError:
            # Not running on Azure VM or IMDS unavailable — ignore
            pass
        except Exception as exc:
            log.debug("imds_poll_error", error=str(exc))
        return False

    async def run(self) -> None:
        """Continuously poll for eviction events."""
        self._running = True
        log.info("eviction_monitor_started", poll_interval=self._poll_interval)

        while self._running:
            if await self.check_for_eviction() and not self._eviction_detected:
                self._eviction_detected = True
                log.warning("triggering_eviction_handler")
                await self._on_eviction()
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """Stop the eviction monitor."""
        self._running = False
        log.info("eviction_monitor_stopped")

    @property
    def is_running(self) -> bool:
        return self._running
