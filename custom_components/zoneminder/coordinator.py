"""DataUpdateCoordinator for ZoneMinder."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

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
    events: dict[tuple[TimePeriod, bool], int | None] = field(default_factory=dict)


@dataclass
class ZmData:
    """Data returned by the ZoneMinder coordinator."""

    monitors: dict[int, ZmMonitorData] = field(default_factory=dict)
    run_state: str | None = None
    server_available: bool = False


class ZmDataUpdateCoordinator(DataUpdateCoordinator[ZmData]):
    """Shared coordinator for all ZoneMinder entities on one server."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZoneMinder,
        monitors: list[Monitor],
        host_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"ZoneMinder ({host_name})",
            update_interval=SCAN_INTERVAL,
        )
        self.zm_client = client
        self.zm_monitors = monitors

    async def _async_update_data(self) -> ZmData:
        """Fetch data from ZoneMinder in one batched executor call."""
        return await self.hass.async_add_executor_job(self._fetch_all_data)

    def _fetch_all_data(self) -> ZmData:
        """Fetch all data synchronously (runs in executor thread)."""
        try:
            data = ZmData()

            for monitor in self.zm_monitors:
                monitor_data = ZmMonitorData(
                    function=monitor.function,
                    is_recording=monitor.is_recording,
                    is_available=monitor.is_available,
                )
                for time_period in TimePeriod:
                    for include_archived in (False, True):
                        monitor_data.events[(time_period, include_archived)] = monitor.get_events(
                            time_period, include_archived
                        )
                data.monitors[monitor.id] = monitor_data

            data.run_state = self.zm_client.get_active_state()
            data.server_available = self.zm_client.is_available

            return data
        except (ZoneminderError, RequestException, KeyError) as err:
            raise UpdateFailed(f"Error fetching ZoneMinder data: {err}") from err
