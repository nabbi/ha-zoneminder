"""Support for ZoneMinder binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZmDataUpdateCoordinator


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZoneMinder binary sensor platform."""
    sensors = []
    coordinators = hass.data.get(f"{DOMAIN}_coordinators", {})
    for host_name in hass.data[DOMAIN]:
        coordinator = coordinators[host_name]
        sensors.append(ZMAvailabilitySensor(coordinator, host_name))
    add_entities(sensors)


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
        )

    @property
    def is_on(self) -> bool:
        """Return True if ZoneMinder server is available."""
        if data := self.coordinator.data:
            return data.server_available
        return False
