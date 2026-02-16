"""Azure SPOT VM lifecycle management."""

from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from azure.mgmt.compute.aio import ComputeManagementClient
    from azure.mgmt.compute.models import VirtualMachine

from spot_agent.config import AzureConfig
from spot_agent.logging import get_logger
from spot_agent.vm.checkpoint import CheckpointManager
from spot_agent.vm.eviction import EvictionMonitor

log = get_logger(__name__)


class SpotVMManager:
    """Manages Azure SPOT VM lifecycle — creation, monitoring, eviction handling, and restart."""

    def __init__(self, config: AzureConfig, checkpoint_mgr: CheckpointManager) -> None:
        self.config = config
        self.checkpoint_mgr = checkpoint_mgr
        self._credential: Any = None
        self._compute_client: ComputeManagementClient | None = None
        self._eviction_monitor: EvictionMonitor | None = None
        self._vm_name: str | None = None

    async def _get_compute_client(self) -> ComputeManagementClient:
        if self._compute_client is None:
            from azure.identity.aio import DefaultAzureCredential
            from azure.mgmt.compute.aio import ComputeManagementClient as _Client

            if self._credential is None:
                self._credential = DefaultAzureCredential()
            self._compute_client = _Client(
                credential=self._credential,
                subscription_id=self.config.subscription_id,
            )
        return self._compute_client

    async def create_spot_vm(self, vm_name: str, nic_id: str) -> VirtualMachine:
        """Create a new Azure SPOT VM."""
        from azure.mgmt.compute.models import (
            BillingProfile, DiskCreateOptionTypes, HardwareProfile, ImageReference,
            LinuxConfiguration, ManagedDiskParameters, NetworkInterfaceReference,
            NetworkProfile, OSDisk, OSProfile, SshConfiguration, StorageAccountTypes,
            StorageProfile, VirtualMachine as VMModel, VirtualMachinePriorityTypes,
            VirtualMachineEvictionPolicyTypes,
        )

        self._vm_name = vm_name
        client = await self._get_compute_client()

        vm_params = VMModel(
            location=self.config.location,
            hardware_profile=HardwareProfile(vm_size=self.config.vm_size),
            storage_profile=StorageProfile(
                image_reference=ImageReference(
                    publisher="Canonical",
                    offer="0001-com-ubuntu-server-jammy",
                    sku="22_04-lts-gen2",
                    version="latest",
                ),
                os_disk=OSDisk(
                    create_option=DiskCreateOptionTypes.FROM_IMAGE,
                    managed_disk=ManagedDiskParameters(
                        storage_account_type=StorageAccountTypes.STANDARD_LRS
                    ),
                ),
            ),
            os_profile=OSProfile(
                computer_name=vm_name,
                admin_username="spotagent",
                linux_configuration=LinuxConfiguration(
                    disable_password_authentication=True,
                    ssh=SshConfiguration(public_keys=[]),
                ),
            ),
            network_profile=NetworkProfile(
                network_interfaces=[
                    NetworkInterfaceReference(id=nic_id, primary=True)
                ]
            ),
            priority=VirtualMachinePriorityTypes.SPOT,
            eviction_policy=VirtualMachineEvictionPolicyTypes.DEALLOCATE,
            billing_profile=BillingProfile(max_price=self.config.max_spot_price),
        )

        log.info("creating_spot_vm", vm_name=vm_name, size=self.config.vm_size)
        poller = await client.virtual_machines.begin_create_or_update(
            self.config.resource_group, vm_name, vm_params
        )
        vm = await poller.result()
        log.info("spot_vm_created", vm_name=vm_name, vm_id=vm.id)
        return vm

    async def start_vm(self, vm_name: str) -> None:
        """Start a deallocated SPOT VM."""
        client = await self._get_compute_client()
        log.info("starting_vm", vm_name=vm_name)
        poller = await client.virtual_machines.begin_start(
            self.config.resource_group, vm_name
        )
        await poller.result()
        log.info("vm_started", vm_name=vm_name)

    async def deallocate_vm(self, vm_name: str) -> None:
        """Deallocate a SPOT VM."""
        client = await self._get_compute_client()
        log.info("deallocating_vm", vm_name=vm_name)
        poller = await client.virtual_machines.begin_deallocate(
            self.config.resource_group, vm_name
        )
        await poller.result()
        log.info("vm_deallocated", vm_name=vm_name)

    async def get_vm_status(self, vm_name: str) -> str:
        """Get the current power state of the VM."""
        client = await self._get_compute_client()
        instance_view = await client.virtual_machines.instance_view(
            self.config.resource_group, vm_name
        )
        for status in instance_view.statuses:
            if status.code and status.code.startswith("PowerState/"):
                return status.code.split("/", 1)[1]
        return "unknown"

    async def handle_eviction(self, state: dict[str, Any]) -> None:
        """Handle SPOT VM eviction — checkpoint state and prepare for restart."""
        log.warning("eviction_detected", vm_name=self._vm_name)
        await self.checkpoint_mgr.save_checkpoint(state)
        log.info("checkpoint_saved", vm_name=self._vm_name)

    async def restart_after_eviction(self, vm_name: str) -> dict[str, Any] | None:
        """Restart after eviction and restore checkpoint."""
        log.info("restarting_after_eviction", vm_name=vm_name)
        try:
            await self.start_vm(vm_name)
        except Exception:
            log.warning("start_failed_recreating", vm_name=vm_name)
        return await self.checkpoint_mgr.load_checkpoint()

    async def start_eviction_monitor(
        self, on_eviction: Any, poll_interval: float = 5.0
    ) -> EvictionMonitor:
        """Start monitoring for SPOT VM eviction events."""
        self._eviction_monitor = EvictionMonitor(
            on_eviction=on_eviction, poll_interval=poll_interval
        )
        asyncio.create_task(self._eviction_monitor.run())
        return self._eviction_monitor

    async def close(self) -> None:
        """Clean up resources."""
        if self._eviction_monitor:
            self._eviction_monitor.stop()
        if self._compute_client:
            await self._compute_client.close()
        if self._credential:
            await self._credential.close()
