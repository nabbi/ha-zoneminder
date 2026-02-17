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

from custom_components.zoneminder.const import DOMAIN

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


# --- Per-monitor Capturing/Analysing/Recording Select Entities (ZM 1.37+) ---


async def test_capturing_select_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test capturing select entity is created on ZM 1.38."""
    monitors = [create_mock_monitor(name="Cam", capturing="Always")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("select.cam_capturing")
    assert state is not None


async def test_analysing_select_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test analysing select entity is created on ZM 1.38."""
    monitors = [create_mock_monitor(name="Cam", analysing="Always")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("select.cam_analysing")
    assert state is not None


async def test_recording_select_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test recording select entity is created on ZM 1.38."""
    monitors = [create_mock_monitor(name="Cam", recording="OnMotion")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("select.cam_recording")
    assert state is not None


async def test_monitor_selects_not_created_on_old_zm(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test per-monitor select entities are NOT created on ZM < 1.37."""
    monitors = [create_mock_monitor(name="Cam", capturing=None, analysing=None, recording=None)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    assert hass.states.get("select.cam_capturing") is None
    assert hass.states.get("select.cam_analysing") is None
    assert hass.states.get("select.cam_recording") is None
    # Run state select should still exist
    assert hass.states.get("select.run_state_select") is not None


async def test_capturing_select_current_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test capturing select shows the current value."""
    monitors = [create_mock_monitor(name="Cam", capturing="Ondemand")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("select.cam_capturing")
    assert state is not None
    assert state.state == "Ondemand"


async def test_analysing_select_current_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test analysing select shows the current value."""
    monitors = [create_mock_monitor(name="Cam", analysing="None")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("select.cam_analysing")
    assert state is not None
    assert state.state == "None"


async def test_recording_select_current_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test recording select shows the current value."""
    monitors = [create_mock_monitor(name="Cam", recording="Always")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("select.cam_recording")
    assert state is not None
    assert state.state == "Always"


async def test_capturing_select_options(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test capturing select has correct options."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("select.cam_capturing")
    assert state is not None
    assert state.attributes.get("options") == ["None", "Ondemand", "Always"]


async def test_analysing_select_options(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test analysing select has correct options."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("select.cam_analysing")
    assert state is not None
    assert state.attributes.get("options") == ["None", "Always"]


async def test_recording_select_options(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test recording select has correct options."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("select.cam_recording")
    assert state is not None
    assert state.attributes.get("options") == ["None", "OnMotion", "Always"]


async def test_capturing_select_option_calls_setter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting a capturing option writes to the monitor."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.cam_capturing", "option": "Ondemand"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert monitors[0].capturing == "Ondemand"


async def test_analysing_select_option_calls_setter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting an analysing option writes to the monitor."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.cam_analysing", "option": "None"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert monitors[0].analysing == "None"


async def test_recording_select_option_calls_setter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting a recording option writes to the monitor."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.cam_recording", "option": "OnMotion"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert monitors[0].recording == "OnMotion"


async def test_monitor_selects_device_info(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test per-monitor select entities have correct device info."""
    monitors = [create_mock_monitor(name="Cam", monitor_id=7)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    entity = hass.data["entity_components"]["select"].get_entity("select.cam_capturing")
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert (DOMAIN, "zm.example.com_7") in info["identifiers"]


async def test_multiple_monitors_create_selects(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test multiple monitors each get their own select entities."""
    monitors = [
        create_mock_monitor(monitor_id=1, name="Front Door"),
        create_mock_monitor(monitor_id=2, name="Back Yard"),
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    # Each monitor should have 3 selects + 1 run state = 7 total
    states = hass.states.async_all("select")
    assert len(states) == 7

    assert hass.states.get("select.front_door_capturing") is not None
    assert hass.states.get("select.back_yard_recording") is not None
