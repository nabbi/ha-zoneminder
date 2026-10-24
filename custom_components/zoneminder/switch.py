"""Support for ZoneMinder switches."""

from __future__ import annotations

import logging
from typing import Any

from aiozoneminder import Monitor, ZMError, function_fields
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_COMMAND_OFF, DEFAULT_COMMAND_ON, DOMAIN
from .coordinator import ZmDataUpdateCoordinator
from .device import monitor_device_info
from .models import ZmEntryData
from .monitor_state import MonitorState, is_zm_137_or_later

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up ZoneMinder switch platform (deprecated YAML)."""
    _LOGGER.warning(
        "Configuration of the ZoneMinder switch platform via YAML is deprecated "
        "and will be removed in a future release. Your connection settings have "
        "been imported into a config entry, but platform options "
        "(command_on, command_off) were set to defaults. "
        "Please review the integration options in the UI, then remove 'switch' "
        "platform entries for 'zoneminder' from your configuration.yaml"
    )


CONF_COMMAND_ON = "command_on"
CONF_COMMAND_OFF = "command_off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZoneMinder switch platform."""
    entry_data: ZmEntryData = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    # Force alarm switches are available on ALL ZM versions.
    for monitor in entry_data.monitors:
        entities.append(ZMSwitchForceAlarm(entry_data.coordinator, monitor, entry_data.host_name))

    # On ZM 1.37+, the three select entities (Capturing/Analysing/Recording)
    # replace the legacy Function switch — so skip function switches.
    if not is_zm_137_or_later(entry_data.coordinator.zm_version):
        on_state = MonitorState(entry.options.get(CONF_COMMAND_ON, DEFAULT_COMMAND_ON))
        off_state = MonitorState(entry.options.get(CONF_COMMAND_OFF, DEFAULT_COMMAND_OFF))

        for monitor in entry_data.monitors:
            entities.append(
                ZMSwitchMonitors(
                    entry_data.coordinator, monitor, on_state, off_state, entry_data.host_name
                )
            )

    async_add_entities(entities)


class ZMSwitchMonitors(CoordinatorEntity[ZmDataUpdateCoordinator], SwitchEntity):
    """Representation of a ZoneMinder switch."""

    icon = "mdi:record-rec"

    def __init__(
        self,
        coordinator: ZmDataUpdateCoordinator,
        monitor: Monitor,
        on_state: MonitorState,
        off_state: MonitorState,
        host_name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._attr_name = f"{monitor.name} State"
        self._attr_unique_id = f"{host_name}_{monitor.id}_switch"
        self._attr_device_info = monitor_device_info(
            host_name, monitor, coordinator.server_device_id
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return bool(md.function == self._on_state)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_set_function(self._on_state)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_set_function(self._off_state)
        await self.coordinator.async_request_refresh()

    async def _async_set_function(self, state: MonitorState) -> None:
        """Set monitor function."""
        capturing, analysing, recording = function_fields(state.value)
        try:
            await self.coordinator.zm_client.set_monitor_state(
                self._monitor.id, capturing=capturing, analysing=analysing, recording=recording
            )
        except ZMError as err:
            raise HomeAssistantError(
                f"Error setting monitor {self._monitor.name} function to {state}: {err}"
            ) from err


class ZMSwitchForceAlarm(CoordinatorEntity[ZmDataUpdateCoordinator], SwitchEntity):
    """Switch to force a ZoneMinder monitor into alarm state."""

    _attr_icon = "mdi:alarm-light"

    def __init__(
        self,
        coordinator: ZmDataUpdateCoordinator,
        monitor: Monitor,
        host_name: str,
    ) -> None:
        """Initialize the force alarm switch."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._attr_name = f"{monitor.name} Force Alarm"
        self._attr_unique_id = f"{host_name}_{monitor.id}_force_alarm"
        self._attr_device_info = monitor_device_info(
            host_name, monitor, coordinator.server_device_id
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the monitor is currently in alarm/recording state."""
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return bool(md.is_recording)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Force the monitor into alarm state."""
        await self._async_set_force_alarm(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Cancel forced alarm on the monitor."""
        await self._async_set_force_alarm(False)
        await self.coordinator.async_request_refresh()

    async def _async_set_force_alarm(self, state: bool) -> None:
        """Set force alarm state."""
        client = self.coordinator.zm_client
        try:
            if state:
                # API v2 runs zmu -a, which records "Forced Web" whatever the cause.
                await client.trigger_alarm(self._monitor.id, "Home Assistant")
            else:
                await client.cancel_alarm(self._monitor.id)
        except ZMError as err:
            raise HomeAssistantError(
                f"Error setting force alarm {'on' if state else 'off'} "
                f"for monitor {self._monitor.name}: {err}"
            ) from err
