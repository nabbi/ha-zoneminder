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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from zoneminder.monitor import Monitor, TimePeriod

from .const import DOMAIN
from .coordinator import ZmDataUpdateCoordinator

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
    coordinators = hass.data.get(f"{DOMAIN}_coordinators", {})
    for host_name, _zm_client in hass.data[DOMAIN].items():
        coordinator = coordinators[host_name]
        monitors = zm_monitors.get(host_name, [])
        if not monitors:
            continue

        for monitor in monitors:
            sensors.append(ZMSensorMonitors(coordinator, monitor, host_name))

            sensors.extend(
                [
                    ZMSensorEvents(coordinator, monitor, include_archived, description, host_name)
                    for description in SENSOR_TYPES
                    if description.key in monitored_conditions
                ]
            )

        sensors.append(ZMSensorRunState(coordinator, host_name))
    add_entities(sensors)


class ZMSensorMonitors(CoordinatorEntity[ZmDataUpdateCoordinator], SensorEntity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(
        self, coordinator: ZmDataUpdateCoordinator, monitor: Monitor, host_name: str
    ) -> None:
        """Initialize monitor sensor."""
        super().__init__(coordinator)
        self._monitor = monitor
        self._attr_name = f"{monitor.name} Status"
        self._attr_unique_id = f"{host_name}_{monitor.id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return md.is_available
        return False

    @property
    def native_value(self) -> str | None:
        """Return the monitor function state."""
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            if md.function is not None:
                return str(md.function.value)
        return None


class ZMSensorEvents(CoordinatorEntity[ZmDataUpdateCoordinator], SensorEntity):
    """Get the number of events for each monitor."""

    _attr_native_unit_of_measurement = "Events"

    def __init__(
        self,
        coordinator: ZmDataUpdateCoordinator,
        monitor: Monitor,
        include_archived: bool,
        description: SensorEntityDescription,
        host_name: str,
    ) -> None:
        """Initialize event sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._monitor = monitor
        self._include_archived = include_archived
        self.time_period = TimePeriod.get_time_period(description.key)
        self._attr_name = f"{monitor.name} {self.time_period.title}"
        self._attr_unique_id = f"{host_name}_{monitor.id}_events_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
            name=monitor.name,
            manufacturer="ZoneMinder",
            via_device=(DOMAIN, host_name),
        )

    @property
    def native_value(self) -> int | None:
        """Return the event count."""
        if (data := self.coordinator.data) and (md := data.monitors.get(self._monitor.id)):
            return md.events.get((self.time_period, self._include_archived))
        return None


class ZMSensorRunState(CoordinatorEntity[ZmDataUpdateCoordinator], SensorEntity):
    """Get the ZoneMinder run state."""

    _attr_name = "Run State"

    def __init__(self, coordinator: ZmDataUpdateCoordinator, host_name: str) -> None:
        """Initialize run state sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{host_name}_run_state"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host_name)},
            name=host_name,
            manufacturer="ZoneMinder",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if data := self.coordinator.data:
            return data.server_available
        return False

    @property
    def native_value(self) -> str | None:
        """Return the run state."""
        if data := self.coordinator.data:
            return data.run_state
        return None
