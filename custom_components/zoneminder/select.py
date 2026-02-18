"""Support for ZoneMinder select entities."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from requests.exceptions import RequestException

from zoneminder.exceptions import ZoneminderError
from zoneminder.monitor import Monitor, MonitorState, _derive_function, _is_zm_137_or_later

from .const import DOMAIN
from .coordinator import ZmData, ZmDataUpdateCoordinator
from .models import ZmEntryData

_LOGGER = logging.getLogger(__name__)

FUNCTION_OPTIONS = [s.value for s in MonitorState]
CAPTURING_OPTIONS = ["None", "Ondemand", "Always"]
ANALYSING_OPTIONS = ["None", "Always"]
RECORDING_OPTIONS = ["None", "OnMotion", "Always"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZoneMinder select platform."""
    entry_data: ZmEntryData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data.coordinator
    host_name = entry_data.host_name

    entities: list[SelectEntity] = [ZMSelectRunState(coordinator, host_name)]

    for monitor in entry_data.monitors:
        entities.append(ZMSelectFunction(coordinator, monitor, host_name))

    if _is_zm_137_or_later(coordinator.zm_client.zm_version):
        for monitor in entry_data.monitors:
            entities.append(ZMSelectCapturing(coordinator, monitor, host_name))
            entities.append(ZMSelectAnalysing(coordinator, monitor, host_name))
            entities.append(ZMSelectRecording(coordinator, monitor, host_name))

    async_add_entities(entities)


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
        data: ZmData | None = self.coordinator.data
        if data is not None:
            return data.available_run_states
        return []

    @property
    def current_option(self) -> str | None:
        """Return the current run state."""
        data: ZmData | None = self.coordinator.data
        if data is not None:
            return data.run_state
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the ZoneMinder run state."""
        await self.hass.async_add_executor_job(self.coordinator.zm_client.set_active_state, option)
        await self.coordinator.async_request_refresh()


class ZMSelectFunction(CoordinatorEntity[ZmDataUpdateCoordinator], SelectEntity):
    """Select entity for changing a monitor's function (None/Monitor/Modect/etc).

    On ZM 1.37+, when the individual Capturing/Analysing/Recording fields
    don't map to a classic MonitorState, ``current_option`` returns "Custom"
    and ``options`` temporarily includes it so HA's ``@final state`` property
    passes validation.  "Custom" is a display-only label — the dropdown still
    lets the user pick any classic function to switch back to.
    """

    def __init__(
        self, coordinator: ZmDataUpdateCoordinator, monitor: Monitor, host_name: str
    ) -> None:
        """Initialize function select."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._attr_name = f"{monitor.name} Function"
        self._attr_unique_id = f"{host_name}_{monitor.id}_function"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def options(self) -> list[str]:
        """Return selectable options, including 'Custom' when active."""
        if self.current_option == "Custom":
            return [*FUNCTION_OPTIONS, "Custom"]
        return FUNCTION_OPTIONS

    @property
    def current_option(self) -> str | None:
        """Return the current function name.

        On ZM 1.37+, derives the classic function from individual fields.
        Returns "Custom" for non-classic combinations.
        """
        data: ZmData | None = self.coordinator.data
        if data is not None and (md := data.monitors.get(self._monitor.id)):
            if md.capturing is not None and md.analysing is not None and md.recording is not None:
                derived = _derive_function(md.capturing, md.analysing, md.recording)
                if derived is not None:
                    return str(derived.value)
                return "Custom"
            if md.function is not None:
                return str(md.function.value)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the monitor function."""
        if option == "Custom":
            return
        await self.hass.async_add_executor_job(self._set_function, option)
        await self.coordinator.async_request_refresh()

    def _set_function(self, value: str) -> None:
        """Set monitor function (runs in executor)."""
        try:
            self._monitor.function = MonitorState(value)
        except (ZoneminderError, RequestException, KeyError) as err:
            _LOGGER.error(
                "Error setting monitor %s Function to %s: %s",
                self._monitor.name,
                value,
                err,
            )


class ZMSelectCapturing(CoordinatorEntity[ZmDataUpdateCoordinator], SelectEntity):
    """Select entity for the ZM 1.37+ Capturing field on a monitor."""

    _attr_options = CAPTURING_OPTIONS

    def __init__(
        self, coordinator: ZmDataUpdateCoordinator, monitor: Monitor, host_name: str
    ) -> None:
        """Initialize capturing select."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._attr_name = f"{monitor.name} Capturing"
        self._attr_unique_id = f"{host_name}_{monitor.id}_capturing"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def current_option(self) -> str | None:
        """Return the current Capturing value."""
        data: ZmData | None = self.coordinator.data
        if data is not None and (md := data.monitors.get(self._monitor.id)):
            return md.capturing
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the Capturing field."""
        await self.hass.async_add_executor_job(self._set_capturing, option)
        await self.coordinator.async_request_refresh()

    def _set_capturing(self, value: str) -> None:
        """Set monitor capturing (runs in executor)."""
        try:
            self._monitor.capturing = value
        except (ZoneminderError, RequestException, KeyError) as err:
            _LOGGER.error(
                "Error setting monitor %s Capturing to %s: %s",
                self._monitor.name,
                value,
                err,
            )


class ZMSelectAnalysing(CoordinatorEntity[ZmDataUpdateCoordinator], SelectEntity):
    """Select entity for the ZM 1.37+ Analysing field on a monitor."""

    _attr_options = ANALYSING_OPTIONS

    def __init__(
        self, coordinator: ZmDataUpdateCoordinator, monitor: Monitor, host_name: str
    ) -> None:
        """Initialize analysing select."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._attr_name = f"{monitor.name} Analysing"
        self._attr_unique_id = f"{host_name}_{monitor.id}_analysing"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def current_option(self) -> str | None:
        """Return the current Analysing value."""
        data: ZmData | None = self.coordinator.data
        if data is not None and (md := data.monitors.get(self._monitor.id)):
            return md.analysing
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the Analysing field."""
        await self.hass.async_add_executor_job(self._set_analysing, option)
        await self.coordinator.async_request_refresh()

    def _set_analysing(self, value: str) -> None:
        """Set monitor analysing (runs in executor)."""
        try:
            self._monitor.analysing = value
        except (ZoneminderError, RequestException, KeyError) as err:
            _LOGGER.error(
                "Error setting monitor %s Analysing to %s: %s",
                self._monitor.name,
                value,
                err,
            )


class ZMSelectRecording(CoordinatorEntity[ZmDataUpdateCoordinator], SelectEntity):
    """Select entity for the ZM 1.37+ Recording field on a monitor."""

    _attr_options = RECORDING_OPTIONS

    def __init__(
        self, coordinator: ZmDataUpdateCoordinator, monitor: Monitor, host_name: str
    ) -> None:
        """Initialize recording select."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._attr_name = f"{monitor.name} Recording"
        self._attr_unique_id = f"{host_name}_{monitor.id}_recording"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def current_option(self) -> str | None:
        """Return the current Recording value."""
        data: ZmData | None = self.coordinator.data
        if data is not None and (md := data.monitors.get(self._monitor.id)):
            return md.recording
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the Recording field."""
        await self.hass.async_add_executor_job(self._set_recording, option)
        await self.coordinator.async_request_refresh()

    def _set_recording(self, value: str) -> None:
        """Set monitor recording (runs in executor)."""
        try:
            self._monitor.recording = value
        except (ZoneminderError, RequestException, KeyError) as err:
            _LOGGER.error(
                "Error setting monitor %s Recording to %s: %s",
                self._monitor.name,
                value,
                err,
            )
