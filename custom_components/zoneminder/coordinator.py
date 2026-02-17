"""DataUpdateCoordinator for ZoneMinder."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from requests.exceptions import RequestException

from zoneminder.exceptions import ZoneminderError
from zoneminder.monitor import Monitor, MonitorState, TimePeriod
from zoneminder.zm import ZoneMinder

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


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
        client: ZoneMinder,
        monitors: list[Monitor],
        host_name: str,
        config_entry: ConfigEntry | None = None,
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
        self._event_queries: set[tuple[TimePeriod, bool]] = set()

    def register_event_queries(self, queries: set[tuple[TimePeriod, bool]]) -> None:
        """Register (TimePeriod, include_archived) pairs to fetch during refresh."""
        self._event_queries |= queries

    async def _async_update_data(self) -> ZmData:
        """Fetch data from ZoneMinder in one batched executor call."""
        data: ZmData = await self.hass.async_add_executor_job(self._fetch_all_data)
        return data

    def _fetch_all_data(self) -> ZmData:
        """Fetch all data synchronously (runs in executor thread)."""
        try:
            data = ZmData()

            self.zm_client.update_all_monitors(self.zm_monitors)

            # Pre-fetch event counts (1 API call per time period, not per monitor)
            event_counts: dict[tuple[TimePeriod, bool], dict | None] = {}
            for time_period, include_archived in self._event_queries:
                event_counts[(time_period, include_archived)] = self.zm_client.get_event_counts(
                    time_period, include_archived
                )

            for monitor in self.zm_monitors:
                monitor_data = ZmMonitorData(
                    function=monitor.function,
                    is_recording=bool(monitor.is_recording),
                    is_available=monitor.is_available,
                    capturing=monitor.capturing,
                    analysing=monitor.analysing,
                    recording=monitor.recording,
                )
                for time_period, include_archived in self._event_queries:
                    counts = event_counts.get((time_period, include_archived))
                    if counts is not None:
                        monitor_data.events[(time_period, include_archived)] = counts.get(
                            str(monitor.id), 0
                        )
                    else:
                        monitor_data.events[(time_period, include_archived)] = None
                data.monitors[monitor.id] = monitor_data

            run_state_objs = self.zm_client.get_run_states()
            data.available_run_states = sorted(rs.name for rs in run_state_objs)
            data.run_state = next((rs.name for rs in run_state_objs if rs.active), None)
            data.server_available = self.zm_client.is_available

            return data
        except (ZoneminderError, RequestException, KeyError) as err:
            raise UpdateFailed(f"Error fetching ZoneMinder data: {err}") from err
