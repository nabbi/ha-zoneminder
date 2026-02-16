"""Support for ZoneMinder sensors."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from zoneminder.monitor import Monitor, TimePeriod
from zoneminder.zm import ZoneMinder

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE_ARCHIVED = "include_archived"

DEFAULT_INCLUDE_ARCHIVED = False

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="all",
        name="Events",
    ),
    SensorEntityDescription(
        key="hour",
        name="Events Last Hour",
    ),
    SensorEntityDescription(
        key="day",
        name="Events Last Day",
    ),
    SensorEntityDescription(
        key="week",
        name="Events Last Week",
    ),
    SensorEntityDescription(
        key="month",
        name="Events Last Month",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_INCLUDE_ARCHIVED, default=DEFAULT_INCLUDE_ARCHIVED): cv.boolean,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["all"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZoneMinder sensor platform."""
    include_archived = config[CONF_INCLUDE_ARCHIVED]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    sensors: list[SensorEntity] = []
    zm_monitors = hass.data.get(f"{DOMAIN}_monitors", {})
    for host_name, zm_client in hass.data[DOMAIN].items():
        monitors = zm_monitors.get(host_name, [])
        if not monitors:
            continue

        for monitor in monitors:
            sensors.append(ZMSensorMonitors(monitor, host_name))

            sensors.extend(
                [
                    ZMSensorEvents(monitor, include_archived, description, host_name)
                    for description in SENSOR_TYPES
                    if description.key in monitored_conditions
                ]
            )

        sensors.append(ZMSensorRunState(zm_client, host_name))
    add_entities(sensors)


class ZMSensorMonitors(SensorEntity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor: Monitor, host_name: str) -> None:
        """Initialize monitor sensor."""
        self._monitor = monitor
        self._attr_available = False
        self._attr_name = f"{self._monitor.name} Status"
        self._attr_unique_id = f"{host_name}_{monitor.id}_status"

    def update(self) -> None:
        """Update the sensor."""
        if not (state := self._monitor.function):
            self._attr_native_value = None
        else:
            self._attr_native_value = state.value
        self._attr_available = self._monitor.is_available


class ZMSensorEvents(SensorEntity):
    """Get the number of events for each monitor."""

    _attr_native_unit_of_measurement = "Events"

    def __init__(
        self,
        monitor: Monitor,
        include_archived: bool,
        description: SensorEntityDescription,
        host_name: str,
    ) -> None:
        """Initialize event sensor."""
        self.entity_description = description

        self._monitor = monitor
        self._include_archived = include_archived
        self.time_period = TimePeriod.get_time_period(description.key)
        self._attr_name = f"{monitor.name} {self.time_period.title}"
        self._attr_unique_id = f"{host_name}_{monitor.id}_events_{description.key}"

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._monitor.get_events(self.time_period, self._include_archived)


class ZMSensorRunState(SensorEntity):
    """Get the ZoneMinder run state."""

    _attr_name = "Run State"

    def __init__(self, client: ZoneMinder, host_name: str) -> None:
        """Initialize run state sensor."""
        self._attr_available = False
        self._client = client
        self._attr_unique_id = f"{host_name}_run_state"

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._client.get_active_state()
        self._attr_available = self._client.is_available
