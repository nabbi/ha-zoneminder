"""Support for ZoneMinder run state select."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZmDataUpdateCoordinator
from .models import ZmEntryData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZoneMinder select platform."""
    entry_data: ZmEntryData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZMSelectRunState(entry_data.coordinator, entry_data.host_name)])


class ZMSelectRunState(CoordinatorEntity[ZmDataUpdateCoordinator], SelectEntity):
    """Select entity for changing the ZoneMinder run state."""

    _attr_name = "Run State Select"

    def __init__(self, coordinator: ZmDataUpdateCoordinator, host_name: str) -> None:
        """Initialize run state select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{host_name}_run_state_select"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host_name)},
            name=host_name,
            manufacturer="ZoneMinder",
            sw_version=coordinator.zm_client.zm_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if data := self.coordinator.data:
            return bool(data.server_available)
        return False

    @property
    def options(self) -> list[str]:
        """Return the list of available run states."""
        if data := self.coordinator.data:
            return data.available_run_states
        return []

    @property
    def current_option(self) -> str | None:
        """Return the current run state."""
        if data := self.coordinator.data:
            return data.run_state
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the ZoneMinder run state."""
        await self.hass.async_add_executor_job(self.coordinator.zm_client.set_active_state, option)
        await self.coordinator.async_request_refresh()
