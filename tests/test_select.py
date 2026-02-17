"""Tests for ZoneMinder select entity."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from requests.exceptions import Timeout
from zoneminder.exceptions import ZoneminderError

from .conftest import create_mock_monitor, setup_entry


async def test_run_state_select_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state select entity is created."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    state = hass.states.get("select.run_state_select")
    assert state is not None


async def test_run_state_select_current_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state select shows active run state name."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, active_state="Home")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("select.run_state_select")
    assert state is not None
    assert state.state == "Home"


async def test_run_state_select_options(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state select options list matches available run states."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(
        hass,
        mock_config_entry,
        monitors=monitors,
        run_state_names=["Away", "Home", "Running"],
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("select.run_state_select")
    assert state is not None
    assert state.attributes.get("options") == ["Away", "Home", "Running"]


async def test_run_state_select_option_calls_set_active_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting an option calls set_active_state on the ZM client."""
    monitors = [create_mock_monitor(name="Cam")]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.run_state_select", "option": "Away"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.set_active_state.assert_called_once_with("Away")


async def test_run_state_select_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state select when server is unavailable."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(
        hass, mock_config_entry, monitors=monitors, is_available=False, active_state=None
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("select.run_state_select")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_run_state_select_device_info_includes_zm_version(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state select device info includes ZoneMinder version as sw_version."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    entity = hass.data["entity_components"]["select"].get_entity("select.run_state_select")
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert info["sw_version"] == "1.38.0"


async def test_run_state_select_error_zoneminder(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test ZoneminderError from set_active_state propagates."""
    monitors = [create_mock_monitor(name="Cam")]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)
    client.set_active_state.side_effect = ZoneminderError("API error")

    with pytest.raises(ZoneminderError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.run_state_select", "option": "Away"},
            blocking=True,
        )


async def test_run_state_select_error_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test requests.Timeout from set_active_state propagates."""
    monitors = [create_mock_monitor(name="Cam")]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)
    client.set_active_state.side_effect = Timeout("timed out")

    with pytest.raises(Timeout):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.run_state_select", "option": "Away"},
            blocking=True,
        )


async def test_run_state_select_no_monitors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test select entity is created even with no monitors."""
    await setup_entry(hass, mock_config_entry, monitors=[])

    state = hass.states.get("select.run_state_select")
    assert state is not None
