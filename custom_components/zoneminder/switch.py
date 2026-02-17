"""Support for ZoneMinder switches."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
)
from homeassistant.components.switch import (
    SwitchEntity,
)
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from requests.exceptions import RequestException

from zoneminder.exceptions import ZoneminderError
from zoneminder.monitor import Monitor, MonitorState

from .const import DOMAIN
from .coordinator import ZmDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_ON): cv.string,
        vol.Required(CONF_COMMAND_OFF): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZoneMinder switch platform."""
    on_state = MonitorState(config.get(CONF_COMMAND_ON))
    off_state = MonitorState(config.get(CONF_COMMAND_OFF))

    switches: list[ZMSwitchMonitors] = []
    zm_monitors = hass.data.get(f"{DOMAIN}_monitors", {})
    coordinators = hass.data.get(f"{DOMAIN}_coordinators", {})
    for host_name, _zm_client in hass.data[DOMAIN].items():
        coordinator = coordinators[host_name]
        monitors = zm_monitors.get(host_name, [])
        switches.extend(
            ZMSwitchMonitors(coordinator, monitor, on_state, off_state, host_name)
            for monitor in monitors
        )
    add_entities(switches)


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
