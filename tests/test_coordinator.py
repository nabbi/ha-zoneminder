"""Tests for ZmDataUpdateCoordinator error handling."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from requests.exceptions import Timeout
from zoneminder.exceptions import ZoneminderError

from custom_components.zoneminder.const import DOMAIN

from .conftest import MOCK_HOST, create_mock_monitor, create_mock_zm_client


async def _setup_and_get_coordinator(hass: HomeAssistant, config: dict, monitors: list):
    """Set up ZM and return the coordinator for MOCK_HOST."""
    client = create_mock_zm_client(monitors=monitors)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    return hass.data[f"{DOMAIN}_coordinators"][MOCK_HOST], client


async def test_update_failed_on_zoneminder_error(hass: HomeAssistant, single_server_config) -> None:
    """ZoneminderError during update should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, single_server_config, monitors)

    client.get_active_state.side_effect = ZoneminderError("API down")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_failed_on_key_error(hass: HomeAssistant, single_server_config) -> None:
    """KeyError from malformed API response should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, single_server_config, monitors)

    client.update_all_monitors.side_effect = KeyError("missing key")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_failed_on_request_timeout(hass: HomeAssistant, single_server_config) -> None:
    """requests.Timeout during update should raise UpdateFailed."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, single_server_config, monitors)

    client.get_active_state.side_effect = Timeout("connection timed out")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_recovers_after_failure(
    hass: HomeAssistant, single_server_config
) -> None:
    """Coordinator should recover on next successful poll after a failure."""
    monitors = [create_mock_monitor()]
    coordinator, client = await _setup_and_get_coordinator(hass, single_server_config, monitors)

    # First poll fails
    client.get_active_state.side_effect = ZoneminderError("temporary failure")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # Next poll succeeds
    client.get_active_state.side_effect = None
    client.get_active_state.return_value = "Running"
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True


async def test_bulk_update_monitors_called(hass: HomeAssistant, single_server_config) -> None:
    """Coordinator should call update_all_monitors() with the monitors list.

    Replaces M individual update_monitor() calls with 1 bulk API call.
    """
    monitors = [create_mock_monitor(monitor_id=1), create_mock_monitor(monitor_id=2, name="Yard")]
    coordinator, client = await _setup_and_get_coordinator(hass, single_server_config, monitors)

    # Reset call counts from initial setup refresh
    client.update_all_monitors.reset_mock()

    await coordinator.async_refresh()

    client.update_all_monitors.assert_called_once_with(monitors)
