"""Support for ZoneMinder camera streaming."""

from __future__ import annotations

import logging

from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from zoneminder.monitor import Monitor

from .const import DOMAIN
from .coordinator import ZmDataUpdateCoordinator
from .models import ZmEntryData

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up ZoneMinder camera platform (deprecated YAML)."""
    _LOGGER.warning(
        "Configuration of the ZoneMinder camera platform via YAML is deprecated "
        "and will be removed in a future release. Your existing configuration has "
        "been imported. Please remove 'camera' entries for 'zoneminder' from your "
        "configuration.yaml and restart Home Assistant"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZoneMinder cameras."""
    filter_urllib3_logging()
    entry_data: ZmEntryData = hass.data[DOMAIN][entry.entry_id]
    cameras = []
    for monitor in entry_data.monitors:
        _LOGGER.debug("Initializing camera %s", monitor.id)
        cameras.append(
            ZoneMinderCamera(
                entry_data.coordinator,
                monitor,
                entry_data.client.verify_ssl,
                entry_data.host_name,
            )
        )
    async_add_entities(cameras)


class ZoneMinderCamera(CoordinatorEntity[ZmDataUpdateCoordinator], MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    def __init__(
        self,
        coordinator: ZmDataUpdateCoordinator,
        monitor: Monitor,
        verify_ssl: bool,
        host_name: str,
    ) -> None:
        """Initialize as a subclass of CoordinatorEntity and MjpegCamera."""
        CoordinatorEntity.__init__(self, coordinator)
        MjpegCamera.__init__(
            self,
            name=monitor.name,
            mjpeg_url=monitor.mjpeg_image_url,
            still_image_url=monitor.still_image_url,
            verify_ssl=verify_ssl,
        )
        self._monitor = monitor
        self._attr_unique_id = f"{host_name}_{monitor.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def is_recording(self) -> bool:
        """Return True if the camera is recording."""
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return bool(md.is_recording)
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return bool(md.is_available)
        return False
