"""Tests for ZmDataUpdateCoordinator error handling."""

from __future__ import annotations

from unittest.mock import call

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import Timeout
from zoneminder.exceptions import ZoneminderError
from zoneminder.monitor import TimePeriod

from custom_components.zoneminder.const import DOMAIN

from .conftest import create_mock_monitor, setup_entry


async def _setup_and_get_coordinator(hass: HomeAssistant, entry: MockConfigEntry, monitors: list):
    """Set up ZM entry and return the coordinator + client."""
    client = await setup_entry(hass, entry, monitors=monitors)
    entry_data = hass.data[DOMAIN][entry.entry_id]
    return entry_data.coordinator, client


async def test_update_failed_on_zoneminder_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """ZoneminderError during update should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_active_state.side_effect = ZoneminderError("API down")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_failed_on_key_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """KeyError from malformed API response should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.update_all_monitors.side_effect = KeyError("missing key")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_failed_on_request_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """requests.Timeout during update should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    client.get_active_state.side_effect = Timeout("connection timed out")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_recovers_after_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Coordinator should recover on next successful poll after a failure."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    # First poll fails
    client.get_active_state.side_effect = ZoneminderError("temporary failure")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # Next poll succeeds
    client.get_active_state.side_effect = None
    client.get_active_state.return_value = "Running"
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True


async def test_bulk_update_monitors_called(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Coordinator should call update_all_monitors() with the monitors list."""
    monitors = [create_mock_monitor(monitor_id=1), create_mock_monitor(monitor_id=2, name="Yard")]
    coordinator, client = await _setup_and_get_coordinator(hass, mock_config_entry, monitors)

    # Reset call counts from initial setup refresh
    client.update_all_monitors.reset_mock()

    await coordinator.async_refresh()

    client.update_all_monitors.assert_called_once_with(monitors)


async def test_event_counts_prefetched_once_per_period(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Event counts should be fetched once per time period, not per monitor."""
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

    client.get_event_counts.reset_mock()
    await coordinator.async_refresh()

    # Should be called exactly once per (TimePeriod, include_archived) pair
    assert client.get_event_counts.call_count == 2
    client.get_event_counts.assert_has_calls(
        [call(TimePeriod.ALL, False), call(TimePeriod.HOUR, False)],
        any_order=True,
    )
