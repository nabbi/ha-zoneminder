"""Support for ZoneMinder camera streaming."""

from __future__ import annotations

import logging

from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from zoneminder.monitor import Monitor

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZoneMinder cameras."""
    filter_urllib3_logging()
    cameras = []
    zm_monitors = hass.data.get(f"{DOMAIN}_monitors", {})
    for host_name, zm_client in hass.data[DOMAIN].items():
        for monitor in zm_monitors.get(host_name, []):
            _LOGGER.debug("Initializing camera %s", monitor.id)
            cameras.append(ZoneMinderCamera(monitor, zm_client.verify_ssl, host_name))
    add_entities(cameras)


class ZoneMinderCamera(MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    _attr_should_poll = True  # Cameras default to False

    def __init__(self, monitor: Monitor, verify_ssl: bool, host_name: str) -> None:
        """Initialize as a subclass of MjpegCamera."""
        super().__init__(
            name=monitor.name,
            mjpeg_url=monitor.mjpeg_image_url,
            still_image_url=monitor.still_image_url,
            verify_ssl=verify_ssl,
        )
        self._attr_is_recording = False
        self._attr_available = False
        self._attr_unique_id = f"{host_name}_{monitor.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )
        self._monitor = monitor

    def update(self) -> None:
        """Update our recording state from the ZM API."""
        _LOGGER.debug("Updating camera state for monitor %i", self._monitor.id)
        self._attr_is_recording = self._monitor.is_recording
        self._attr_available = self._monitor.is_available
