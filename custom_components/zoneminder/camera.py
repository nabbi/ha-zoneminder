"""Support for ZoneMinder camera streaming."""

from __future__ import annotations

import logging

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9 validates with voluptuous
    import voluptuous as vol  # type: ignore[no-redef]
from aiohttp import web
from aiozoneminder import Monitor, ZMError, ZoneMinderLegacyClient
from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DIRECTION,
    ATTR_PRESET,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SERVICE_PTZ,
    SERVICE_PTZ_PRESET,
    SUPPORT_PTZ,
)
from .coordinator import ZmDataUpdateCoordinator
from .device import monitor_device_info
from .models import ZmEntryData

_LOGGER = logging.getLogger(__name__)

PTZ_DIRECTIONS = [
    "right",
    "left",
    "up",
    "down",
    "up_left",
    "up_right",
    "down_left",
    "down_right",
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up ZoneMinder camera platform (deprecated YAML)."""
    _LOGGER.warning(
        "Configuration of the ZoneMinder camera platform via YAML is deprecated "
        "and will be removed in a future release. Your connection settings have "
        "been imported into a config entry. Please remove 'camera' platform "
        "entries for 'zoneminder' from your configuration.yaml"
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
                entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                entry_data.host_name,
            )
        )
    async_add_entities(cameras)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PTZ,
        {vol.Required(ATTR_DIRECTION): vol.In(PTZ_DIRECTIONS)},
        "async_perform_ptz",
        required_features=[SUPPORT_PTZ],
    )
    platform.async_register_entity_service(
        SERVICE_PTZ_PRESET,
        {vol.Required(ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=0, max=99))},
        "async_perform_ptz_preset",
        required_features=[SUPPORT_PTZ],
    )


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
            # Built again for each stream: it carries the API token, which expires.
            mjpeg_url=coordinator.zm_client.get_stream_url(monitor.id),
            still_image_url=None,
            verify_ssl=verify_ssl,
        )
        self._monitor = monitor
        self._attr_unique_id = f"{host_name}_{monitor.id}"
        if monitor.controllable:
            self._attr_supported_features = CameraEntityFeature(SUPPORT_PTZ)
        self._attr_device_info = monitor_device_info(
            host_name, monitor, coordinator.server_device_id
        )

    @property
    def _zm_client(self) -> ZoneMinderLegacyClient:
        return self.coordinator.zm_client

    async def stream_source(self) -> str:
        """Return the MJPEG URL, with a current token."""
        self._mjpeg_url = self._zm_client.get_stream_url(self._monitor.id)
        return await super().stream_source()

    async def handle_async_mjpeg_stream(self, request: web.Request) -> web.StreamResponse | None:
        """Proxy the MJPEG stream, with a current token."""
        self._mjpeg_url = self._zm_client.get_stream_url(self._monitor.id)
        return await super().handle_async_mjpeg_stream(request)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from ZMS."""
        return await self._zm_client.async_get_snapshot(self._monitor.id)

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

    async def async_perform_ptz(self, direction: str) -> None:
        """Move PTZ camera in the specified direction."""
        try:
            # aiozoneminder spells directions up-left where the service takes up_left.
            await self._zm_client.ptz(self._monitor.id, direction.replace("_", "-"))
        except ZMError as err:
            raise HomeAssistantError(f"Failed to move camera {self._monitor.name}: {err}") from err

    async def async_perform_ptz_preset(self, preset: int) -> None:
        """Move PTZ camera to a preset position (0 = home)."""
        try:
            if preset == 0:
                await self._zm_client.ptz(self._monitor.id, "home")
            else:
                await self._zm_client.ptz(self._monitor.id, "preset", preset=preset)
        except ZMError as err:
            raise HomeAssistantError(
                f"Failed to move camera {self._monitor.name} to preset {preset}: {err}"
            ) from err
