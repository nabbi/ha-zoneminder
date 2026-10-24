"""Tests for ZmDataUpdateCoordinator error handling."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import call

from aiozoneminder import ZMApiError, ZMAuthenticationError, ZMConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.zoneminder.const import DOMAIN
from custom_components.zoneminder.monitor_state import MonitorState, TimePeriod

from .conftest import create_mock_monitor, setup_entry


async def _setup_and_get_coordinator(hass: HomeAssistant, entry: MockConfigEntry, monitors: list):
    """Set up ZM entry and return the coordinator + client."""
    client = await setup_entry(hass, entry, monitors=monitors)
    entry_data = hass.data[DOMAIN][entry.entry_id]
    return entry_data.coordinator, client


async def test_update_failed_on_zoneminder_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """ZMApiError during update should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_monitors.side_effect = ZMApiError("api/monitors.json returned 500")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_run_states_refused_reads_as_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A refused run state list (no System view) is no run states, as zm-py returned."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_run_states.side_effect = ZMApiError("api/states.json was refused")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data.available_run_states == []
    assert coordinator.data.run_state is None


async def test_alarm_state_error_reads_as_not_recording(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A failed alarm status read is not recording, as zm-py's is_recording returned."""
    monitors = [create_mock_monitor(is_recording=True)]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_alarm_state.side_effect = ZMApiError("alarm status returned 500")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data.monitors[1].is_recording is False


async def test_update_failed_on_key_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A response aiozoneminder can't use should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_monitors.side_effect = ZMApiError(
        "api/monitors.json returned a page that is not JSON"
    )
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_failed_on_request_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A timeout during update should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_run_states.side_effect = ZMConnectionError("connection timed out")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_recovers_after_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Coordinator should recover on next successful poll after a failure."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    # First poll fails
    client.get_monitors.side_effect = ZMConnectionError("temporary failure")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # Next poll succeeds
    client.get_monitors.side_effect = lambda: []
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True


async def test_bulk_update_monitors_called(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Each refresh lists the monitors once, for every monitor's state."""
    monitors = [create_mock_monitor(monitor_id=1), create_mock_monitor(monitor_id=2, name="Yard")]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    # Reset call counts from initial setup refresh
    client.get_monitors.reset_mock()

    await coordinator.async_refresh()

    client.get_monitors.assert_awaited_once_with()
    assert set(coordinator.data.monitors) == {1, 2}


async def test_coordinator_populates_new_monitor_fields(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Coordinator should populate capturing/analysing/recording from monitors."""
    monitors = [
        create_mock_monitor(
            monitor_id=1,
            capturing="Always",
            analysing="None",
            recording="OnMotion",
        )
    ]
    coordinator, _ = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    await coordinator.async_refresh()

    md = coordinator.data.monitors[1]
    assert md.capturing == "Always"
    assert md.analysing == "None"
    assert md.recording == "OnMotion"


async def test_coordinator_fields_from_function_on_old_zm(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """On pre-1.37 ZM aiozoneminder expands Function into the three fields."""
    monitors = [
        create_mock_monitor(
            monitor_id=1,
            function=MonitorState.MODECT,
            capturing=None,
            analysing=None,
            recording=None,
        )
    ]
    coordinator, _ = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    await coordinator.async_refresh()

    md = coordinator.data.monitors[1]
    assert (md.capturing, md.analysing, md.recording) == ("Always", "Always", "OnMotion")
    assert md.function is MonitorState.MODECT


async def test_event_counts_prefetched_once_per_period(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Event counts come per monitor from the monitor list aiozoneminder already has."""
    monitors = [
        create_mock_monitor(monitor_id=1),
        create_mock_monitor(monitor_id=2, name="Yard"),
        create_mock_monitor(monitor_id=3, name="Garage"),
    ]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    # Register event queries (normally done by sensor platform setup)
    coordinator.register_event_queries(
        {
            (TimePeriod.ALL, False),
            (TimePeriod.HOUR, False),
        }
    )

    client.get_event_summary.reset_mock()
    client.get_monitors.reset_mock()
    await coordinator.async_refresh()

    # One summary per monitor and query, served from the one monitor list.
    assert client.get_monitors.await_count == 1
    assert client.get_event_summary.await_count == 6
    client.get_event_summary.assert_has_awaits(
        [call(m, include_archived=False) for m in (1, 2, 3)], any_order=True
    )
    assert coordinator.data.monitors[2].events[(TimePeriod.HOUR, False)] == 5


async def test_refused_login_starts_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A login refused during a refresh starts reauth and stops polling."""
    client = await setup_entry(hass, mock_config_entry, monitors=[create_mock_monitor()])
    client.get_monitors.side_effect = ZMAuthenticationError("Invalid username or password")
    calls = client.get_monitors.call_count

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
    assert client.get_monitors.call_count == calls + 1

    # No more polling, so no more failed logins, until the user answers.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
    await hass.async_block_till_done()
    assert client.get_monitors.call_count == calls + 1
