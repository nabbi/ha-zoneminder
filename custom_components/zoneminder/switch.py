"""Support for ZoneMinder switches."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from requests.exceptions import RequestException

from zoneminder.exceptions import ZoneminderError
from zoneminder.monitor import Monitor, MonitorState

from .const import DEFAULT_COMMAND_OFF, DEFAULT_COMMAND_ON, DOMAIN
from .coordinator import ZmDataUpdateCoordinator
from .models import ZmEntryData

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

    on_state = MonitorState(entry.options.get(CONF_COMMAND_ON, DEFAULT_COMMAND_ON))
    off_state = MonitorState(entry.options.get(CONF_COMMAND_OFF, DEFAULT_COMMAND_OFF))

    switches: list[ZMSwitchMonitors] = []
    for monitor in entry_data.monitors:
        switches.append(
            ZMSwitchMonitors(
                entry_data.coordinator, monitor, on_state, off_state, entry_data.host_name
            )
        )
    async_add_entities(switches)


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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return bool(md.function == self._on_state)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.hass.async_add_executor_job(self._set_function, self._on_state)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.hass.async_add_executor_job(self._set_function, self._off_state)
        await self.coordinator.async_request_refresh()

    def _set_function(self, state: MonitorState) -> None:
        """Set monitor function (runs in executor)."""
        try:
            self._monitor.function = state
        except (ZoneminderError, RequestException, KeyError) as err:
            _LOGGER.error(
                "Error setting monitor %s function to %s: %s",
                self._monitor.name,
                state,
                err,
            )
