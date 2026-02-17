"""Tests for ZoneMinder switch entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from requests.exceptions import Timeout
from zoneminder.exceptions import ZoneminderError
from zoneminder.monitor import Monitor, MonitorState

from .conftest import create_mock_monitor, setup_entry


def _entry_with_switch_options(
    mock_config_entry: MockConfigEntry,
    command_on: str = "Modect",
    command_off: str = "Monitor",
) -> MockConfigEntry:
    """Return a copy of the mock entry with custom switch options."""
    options = dict(mock_config_entry.options)
    options["command_on"] = command_on
    options["command_off"] = command_off
    return MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data=mock_config_entry.data,
        options=options,
        unique_id=mock_config_entry.unique_id,
        source=mock_config_entry.source,
    )


async def test_switch_per_monitor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, two_monitors
) -> None:
    """Test one function switch + one force alarm switch per monitor on pre-1.37 ZM."""
    await setup_entry(hass, mock_config_entry, monitors=two_monitors, zm_version="1.36.33")

    states = hass.states.async_all(SWITCH_DOMAIN)
    # 2 function switches + 2 force alarm switches = 4
    assert len(states) == 4


async def test_switch_name_format(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test switch name format is '{name} State'."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.name == "Front Door State"


async def test_switch_on_when_function_matches_command_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch is ON when monitor function matches command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_off_when_function_differs(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch is OFF when monitor function differs from command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_turn_on_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn_on service sets monitor function to command_on."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify monitor function was set to MonitorState("Modect")
    assert monitors[0].function == MonitorState("Modect")


async def test_switch_turn_off_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn_off service sets monitor function to command_off."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert monitors[0].function == MonitorState("Monitor")


async def test_switch_icon(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test switch icon is mdi:record-rec."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    state = hass.states.get("switch.front_door_state")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:record-rec"


async def test_switch_no_monitors(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test no switches when no monitors."""
    await setup_entry(hass, mock_config_entry, monitors=[], zm_version="1.36.33")

    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 0


async def test_switch_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Switch entities should have unique_id for UI customization."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    entry = entity_registry.async_get("switch.front_door_state")
    assert entry is not None
    assert entry.unique_id is not None


async def test_turn_on_api_error_logged(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """ZoneminderError during turn_on should be caught and logged."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]

    def raise_on_set(self, value):
        raise ZoneminderError("API error")

    monitors[0].configure_mock(**{"function": MonitorState.MONITOR})
    type(monitors[0]).function = property(lambda self: MonitorState.MONITOR, raise_on_set)

    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Error setting monitor" in caplog.text


async def test_turn_off_request_timeout_logged(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """requests.Timeout during turn_off should be caught and logged."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]

    def raise_on_set(self, value):
        raise Timeout("connection timed out")

    type(monitors[0]).function = property(lambda self: MonitorState.MODECT, raise_on_set)

    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.front_door_state"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Error setting monitor" in caplog.text


async def test_function_switch_not_created_on_zm_137(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test function switches are NOT created on ZM 1.37+ (select entities replace them)."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    # Only force alarm switch should exist, not function switch
    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 1
    assert states[0].entity_id == "switch.front_door_force_alarm"


# ---------------------------------------------------------------------------
# Force alarm switch tests
# ---------------------------------------------------------------------------


async def test_force_alarm_switch_created_per_monitor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, two_monitors
) -> None:
    """Test one force alarm switch is created per monitor."""
    await setup_entry(hass, mock_config_entry, monitors=two_monitors, zm_version="1.36.33")

    states = hass.states.async_all(SWITCH_DOMAIN)
    force_alarm_states = [s for s in states if "force_alarm" in s.entity_id]
    assert len(force_alarm_states) == 2


async def test_force_alarm_switch_name_format(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test force alarm switch name format is '{name} Force Alarm'."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    state = hass.states.get("switch.front_door_force_alarm")
    assert state is not None
    assert state.name == "Front Door Force Alarm"


async def test_force_alarm_switch_on_when_recording(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test force alarm switch is ON when monitor is recording."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=True)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.front_door_force_alarm")
    assert state is not None
    assert state.state == STATE_ON


async def test_force_alarm_switch_off_when_not_recording(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test force alarm switch is OFF when monitor is not recording."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.front_door_force_alarm")
    assert state is not None
    assert state.state == STATE_OFF


async def test_force_alarm_turn_on_calls_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn_on calls set_force_alarm_state(True)."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()

    monitors[0].set_force_alarm_state.assert_called_once_with(True)


async def test_force_alarm_turn_off_calls_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn_off calls set_force_alarm_state(False)."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=True)]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()

    monitors[0].set_force_alarm_state.assert_called_once_with(False)


async def test_force_alarm_api_error_logged(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """ZoneminderError during force alarm should be caught and logged."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    monitors[0].set_force_alarm_state.side_effect = ZoneminderError("API error")
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Error setting force alarm" in caplog.text


async def test_force_alarm_icon(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test force alarm switch icon is mdi:alarm-light."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    state = hass.states.get("switch.front_door_force_alarm")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:alarm-light"


async def test_force_alarm_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Force alarm switch should have a unique_id."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    entry = entity_registry.async_get("switch.front_door_force_alarm")
    assert entry is not None
    assert entry.unique_id == "zm.example.com_1_force_alarm"


async def test_force_alarm_created_on_zm_137(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test force alarm switches ARE created on ZM 1.37+ (not suppressed like function switch)."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    state = hass.states.get("switch.front_door_force_alarm")
    assert state is not None


async def test_force_alarm_request_timeout_logged(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """requests.Timeout during force alarm should be caught and logged."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    monitors[0].set_force_alarm_state.side_effect = Timeout("connection timed out")
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Error setting force alarm" in caplog.text


async def test_function_read_no_side_effects(hass: HomeAssistant) -> None:
    """Reading monitor.function should not trigger an HTTP request.

    BUG-03 resolved: Monitor.function is now a pure read from _raw_result.
    The coordinator calls update_monitor() explicitly once per poll cycle.
    This test verifies the property getter makes zero API calls.
    """
    stub_client = MagicMock()
    stub_client.verify_ssl = True

    raw_result = {
        "Monitor": {
            "Id": "1",
            "Name": "Test",
            "Function": "Modect",
            "Controllable": "0",
            "StreamReplayBuffer": "0",
            "ServerId": "0",
        },
        "Monitor_Status": {"CaptureFPS": "15.00"},
    }
    stub_client.get_zms_url_for_monitor.return_value = "http://example.com/zms"
    stub_client.get_url_with_auth.return_value = "http://example.com/zms?auth=1"

    monitor = Monitor(stub_client, raw_result)
    stub_client.get_state.reset_mock()

    # Reading function should NOT make an HTTP call (constructor data is cached)
    _ = monitor.function
    assert stub_client.get_state.call_count == 0
