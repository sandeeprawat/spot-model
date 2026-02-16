"""Tests for SPOT VM lifecycle components."""

from __future__ import annotations

import asyncio

import pytest

from spot_agent.vm.eviction import EvictionMonitor


@pytest.mark.asyncio
async def test_eviction_monitor_check_no_azure():
    """Test eviction check when not running on Azure (should return False)."""
    evicted = False

    async def on_eviction():
        nonlocal evicted
        evicted = True

    monitor = EvictionMonitor(on_eviction=on_eviction, poll_interval=1.0)
    result = await monitor.check_for_eviction()
    assert result is False
    assert not evicted


@pytest.mark.asyncio
async def test_eviction_monitor_stop():
    """Test stopping the eviction monitor."""
    async def on_eviction():
        pass

    monitor = EvictionMonitor(on_eviction=on_eviction, poll_interval=0.1)
    
    # Start in background
    task = asyncio.create_task(monitor.run())
    await asyncio.sleep(0.3)
    
    assert monitor.is_running
    monitor.stop()
    await asyncio.sleep(0.2)
    assert not monitor.is_running
    
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
