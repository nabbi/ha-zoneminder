"""DataUpdateCoordinator for ZoneMinder."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from aiozoneminder import Monitor, RunState, ZMApiError, ZMError, ZoneMinderClient
from aiozoneminder.const import SERVER_ACTIONS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_INCLUDE_ARCHIVED, DEFAULT_INCLUDE_ARCHIVED, DEFAULT_MONITORED_CONDITIONS
from .monitor_state import MonitorState, TimePeriod, derive_function

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# Alarm states zm-py's is_recording counted as recording (state >= ALARM).
_RECORDING_ALARM_STATES = ("alarm", "alert")


@dataclass
class ZmMonitorData:
    """Refreshed data for a single ZoneMinder monitor."""

    function: MonitorState | None
    is_recording: bool
    is_available: bool
    capturing: str | None = None
    analysing: str | None = None
    recording: str | None = None
    events: dict[tuple[TimePeriod, bool], int | None] = field(default_factory=dict)


@dataclass
class ZmData:
    """Data returned by the ZoneMinder coordinator."""

    monitors: dict[int, ZmMonitorData] = field(default_factory=dict)
    run_state: str | None = None
    available_run_states: list[str] = field(default_factory=list)
    server_available: bool = False


class ZmDataUpdateCoordinator(DataUpdateCoordinator[ZmData]):
    """Shared coordinator for all ZoneMinder entities on one server."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZoneMinderClient,
        monitors: list[Monitor],
        host_name: str,
        config_entry: ConfigEntry | None = None,
        *,
        server_device_id: str,
        zm_version: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"ZoneMinder ({host_name})",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.zm_client = client
        self.zm_monitors = monitors
        self.zm_version = zm_version
        # Registry id of the server's device, which monitor devices hang off.
        self.server_device_id = server_device_id
        self._event_queries: set[tuple[TimePeriod, bool]] = set()

    def register_event_queries_from_options(self, options: Mapping[str, Any]) -> None:
        """Register the event queries the sensor options call for."""
        include_archived = options.get(CONF_INCLUDE_ARCHIVED, DEFAULT_INCLUDE_ARCHIVED)
        conditions = options.get(CONF_MONITORED_CONDITIONS, DEFAULT_MONITORED_CONDITIONS)
        self.register_event_queries(
            {(TimePeriod.get_time_period(key), include_archived) for key in conditions}
        )

    def register_event_queries(self, queries: set[tuple[TimePeriod, bool]]) -> None:
        """Register (TimePeriod, include_archived) pairs to fetch during refresh."""
        self._event_queries |= queries

    async def async_set_run_state(self, name: str) -> None:
        """Switch ZoneMinder to a run state, or start, stop or restart it."""
        if name in SERVER_ACTIONS:
            await self.zm_client.server_control(name)
        else:
            # Only the name is sent (states/change/<name>).
            await self.zm_client.set_run_state(
                RunState(id=0, name=name, definition="", active=False)
            )

    async def _async_is_recording(self, monitor_id: int) -> bool:
        """Return True when the monitor is in alarm, as zm-py's is_recording did."""
        try:
            state = await self.zm_client.get_alarm_state(monitor_id)
        except ZMApiError as err:
            _LOGGER.debug("No alarm state for monitor %s: %s", monitor_id, err)
            return False
        return state in _RECORDING_ALARM_STATES

    async def _async_update_data(self) -> ZmData:
        """Fetch data from ZoneMinder."""
        client = self.zm_client
        try:
            data = ZmData()

            # One request: the monitor list carries statuses and event summaries.
            monitors = {monitor.id: monitor for monitor in await client.get_monitors()}
            statuses = await client.get_monitor_statuses()

            for monitor in self.zm_monitors:
                current = monitors.get(monitor.id, monitor)
                status = statuses.get(monitor.id)
                monitor_data = ZmMonitorData(
                    function=derive_function(
                        current.capturing, current.analysing, current.recording
                    ),
                    is_recording=await self._async_is_recording(monitor.id),
                    is_available=status is not None and status.connected,
                    capturing=current.capturing,
                    analysing=current.analysing,
                    recording=current.recording,
                )
                for time_period, include_archived in self._event_queries:
                    summary = await client.get_event_summary(
                        monitor.id, include_archived=include_archived
                    )
                    monitor_data.events[(time_period, include_archived)] = (
                        getattr(summary, time_period.summary_field) if summary is not None else None
                    )
                data.monitors[monitor.id] = monitor_data

            try:
                run_state_objs = await client.get_run_states()
            except ZMApiError as err:
                # A user without System view; zm-py returned no run states.
                _LOGGER.debug("Run states unavailable: %s", err)
                run_state_objs = []
            data.available_run_states = sorted(rs.name for rs in run_state_objs)
            data.run_state = next((rs.name for rs in run_state_objs if rs.active), None)
            data.server_available = (await client.get_server_info()).running is True

            return data
        except ZMError as err:
            raise UpdateFailed(f"Error fetching ZoneMinder data: {err}") from err
