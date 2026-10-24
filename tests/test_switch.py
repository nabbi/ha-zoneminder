"""Tests for ZoneMinder switch entities."""

from __future__ import annotations

from datetime import timedelta

import pytest
from aiozoneminder import ZMApiError, ZMConnectionError
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.zoneminder.monitor_state import MonitorState

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


async def test_turn_on_api_error_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """ZMApiError during turn_on is raised as an error HA shows."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MONITOR)]

    def raise_on_set(self, value):
        raise ZMApiError("API error")

    monitors[0].configure_mock(**{"function": MonitorState.MONITOR})
    type(monitors[0]).function = property(lambda self: MonitorState.MONITOR, raise_on_set)

    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    with pytest.raises(HomeAssistantError, match="Error setting monitor"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.front_door_state"},
            blocking=True,
        )
    await hass.async_block_till_done()


async def test_turn_off_request_timeout_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """requests.Timeout during turn_off is raised as an error HA shows."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]

    def raise_on_set(self, value):
        raise ZMConnectionError("connection timed out")

    type(monitors[0]).function = property(lambda self: MonitorState.MODECT, raise_on_set)

    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    with pytest.raises(HomeAssistantError, match="Error setting monitor"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.front_door_state"},
            blocking=True,
        )
    await hass.async_block_till_done()


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
    """Test turn_on forces an alarm."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.trigger_alarm.assert_awaited_once_with(1, "Home Assistant")
    client.cancel_alarm.assert_not_awaited()


async def test_force_alarm_turn_off_calls_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn_off cancels the forced alarm."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.cancel_alarm.assert_awaited_once_with(1)
    client.trigger_alarm.assert_not_awaited()


async def test_force_alarm_api_error_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """ZMApiError during force alarm is raised as an error HA shows."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")
    client.trigger_alarm.side_effect = ZMApiError("zmu exit 255")

    with pytest.raises(HomeAssistantError, match="Error setting force alarm"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
            blocking=True,
        )
    await hass.async_block_till_done()


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


async def test_force_alarm_request_timeout_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A timeout during force alarm is raised as an error HA shows."""
    monitors = [create_mock_monitor(name="Front Door", is_recording=False)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")
    client.trigger_alarm.side_effect = ZMConnectionError("connection timed out")

    with pytest.raises(HomeAssistantError, match="Error setting force alarm"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.front_door_force_alarm"},
            blocking=True,
        )
    await hass.async_block_till_done()
