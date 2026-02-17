"""Support for ZoneMinder binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up the ZoneMinder binary sensor platform."""
    entry_data: ZmEntryData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZMAvailabilitySensor(entry_data.coordinator, entry_data.host_name)])


class ZMAvailabilitySensor(CoordinatorEntity[ZmDataUpdateCoordinator], BinarySensorEntity):
    """Representation of the availability of ZoneMinder as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ZmDataUpdateCoordinator, host_name: str) -> None:
        """Initialize availability sensor."""
        super().__init__(coordinator)
        self._attr_name = host_name
        self._attr_unique_id = f"{host_name}_availability"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host_name)},
            name=host_name,
            manufacturer="ZoneMinder",
            sw_version=coordinator.zm_client.zm_version,
        )

    @property
    def is_on(self) -> bool:
        """Return True if ZoneMinder server is available."""
        if data := self.coordinator.data:
            return bool(data.server_available)
        return False
