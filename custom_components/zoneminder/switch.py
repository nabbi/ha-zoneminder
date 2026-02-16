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

from zoneminder.monitor import Monitor, MonitorState

from .const import DOMAIN

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
    for host_name, _zm_client in hass.data[DOMAIN].items():
        monitors = zm_monitors.get(host_name, [])
        switches.extend(
            ZMSwitchMonitors(monitor, on_state, off_state, host_name) for monitor in monitors
        )
    add_entities(switches)


class ZMSwitchMonitors(SwitchEntity):
    """Representation of a ZoneMinder switch."""

    icon = "mdi:record-rec"

    def __init__(self, monitor: Monitor, on_state: str, off_state: str, host_name: str) -> None:
        """Initialize the switch."""
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._state: bool | None = None
        self._attr_name = f"{monitor.name} State"
        self._attr_unique_id = f"{host_name}_{monitor.id}_switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    def update(self) -> None:
        """Update the switch value."""
        self._state = self._monitor.function == self._on_state

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._monitor.function = self._on_state

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._monitor.function = self._off_state
