"""Tests for ZoneMinder sensor entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_MONITORED_CONDITIONS, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from zoneminder.monitor import Monitor, MonitorState, TimePeriod

from custom_components.zoneminder.const import CONF_INCLUDE_ARCHIVED

from .conftest import create_mock_monitor, setup_entry


def _entry_with_sensor_options(
    mock_config_entry: MockConfigEntry,
    include_archived: bool = False,
    monitored_conditions: list[str] | None = None,
) -> MockConfigEntry:
    """Return a copy of the mock entry with custom sensor options."""
    options = dict(mock_config_entry.options)
    options[CONF_INCLUDE_ARCHIVED] = include_archived
    if monitored_conditions is not None:
        options[CONF_MONITORED_CONDITIONS] = monitored_conditions
    # Update options in place since MockConfigEntry supports it
    hass_entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data=mock_config_entry.data,
        options=options,
        unique_id=mock_config_entry.unique_id,
        source=mock_config_entry.source,
    )
    return hass_entry


# --- Monitor Status Sensor ---


async def test_monitor_status_sensor_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test monitor status sensor is created."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    state = hass.states.get("sensor.front_door_status")
    assert state is not None


async def test_monitor_status_sensor_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test monitor status sensor shows MonitorState value."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.RECORD)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.front_door_status")
    assert state is not None
    assert state.state == "Record"


@pytest.mark.parametrize(
    ("monitor_state", "expected_value"),
    [
        (MonitorState.NONE, "None"),
        (MonitorState.MONITOR, "Monitor"),
        (MonitorState.MODECT, "Modect"),
        (MonitorState.RECORD, "Record"),
        (MonitorState.MOCORD, "Mocord"),
        (MonitorState.NODECT, "Nodect"),
    ],
)
async def test_monitor_status_sensor_all_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    monitor_state: MonitorState,
    expected_value: str,
) -> None:
    """Test monitor status sensor with all MonitorState values."""
    monitors = [create_mock_monitor(name="Cam", function=monitor_state)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == expected_value


async def test_monitor_status_sensor_unavailable_monitor_still_shows_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test status sensor stays available even when monitor daemon is stopped.

    A monitor set to Function=None stops the ZM daemon, making
    is_available=False. The status sensor should still report the function
    state ("None") rather than going unavailable, since the API data is
    still valid.
    """
    monitors = [
        create_mock_monitor(name="Front Door", is_available=False, function=MonitorState.NONE)
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.front_door_status")
    assert state is not None
    assert state.state == "None"


async def test_monitor_status_sensor_null_function(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test monitor status sensor when function is falsy."""
    monitors = [create_mock_monitor(name="Front Door", function=None, is_available=True)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    state = hass.states.get("sensor.front_door_status")
    assert state is not None


# --- Status Sensor with ZM 1.37+ individual fields ---


async def test_status_sensor_derives_classic_name_from_new_fields(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test status sensor derives classic name when new fields map to a MonitorState."""
    monitors = [
        create_mock_monitor(
            name="Cam",
            function=MonitorState.MODECT,
            capturing="Always",
            analysing="Always",
            recording="OnMotion",
        )
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == "Modect"


async def test_status_sensor_shows_composed_state_for_unmapped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test status sensor shows composed string for unmapped field combinations."""
    monitors = [
        create_mock_monitor(
            name="Cam",
            function=MonitorState.MONITOR,  # stale Function column
            capturing="Always",
            analysing="Always",
            recording="None",
        )
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == "Always/Always/None"


async def test_status_sensor_ondemand_capturing_shows_composed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test Ondemand capturing (no classic equivalent) shows composed string."""
    monitors = [
        create_mock_monitor(
            name="Cam",
            function=MonitorState.MONITOR,
            capturing="Ondemand",
            analysing="None",
            recording="None",
        )
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == "Ondemand/None/None"


async def test_status_sensor_falls_back_without_new_fields(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test status sensor falls back to md.function when new fields are absent."""
    monitors = [
        create_mock_monitor(
            name="Cam",
            function=MonitorState.RECORD,
            capturing=None,
            analysing=None,
            recording=None,
        )
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.36.33")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == "Record"


@pytest.mark.parametrize(
    ("capturing", "analysing", "recording", "expected"),
    [
        ("None", "None", "None", "None"),
        ("Always", "None", "None", "Monitor"),
        ("Always", "Always", "OnMotion", "Modect"),
        ("Always", "None", "Always", "Record"),
        ("Always", "Always", "Always", "Mocord"),
        ("Always", "None", "OnMotion", "Nodect"),
    ],
)
async def test_status_sensor_all_classic_states_via_new_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    capturing: str,
    analysing: str,
    recording: str,
    expected: str,
) -> None:
    """Test status sensor derives all classic MonitorState values from new fields."""
    monitors = [
        create_mock_monitor(
            name="Cam",
            function=MonitorState.NONE,  # irrelevant, new fields take priority
            capturing=capturing,
            analysing=analysing,
            recording=recording,
        )
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors, zm_version="1.38.0")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == expected


# --- Event Sensors ---


@pytest.mark.parametrize(
    ("condition", "expected_name_suffix", "expected_value"),
    [
        ("all", "Events", "100"),
        ("hour", "Events Last Hour", "5"),
        ("day", "Events Last Day", "20"),
        ("week", "Events Last Week", "50"),
        ("month", "Events Last Month", "80"),
    ],
)
async def test_event_sensor_for_each_time_period(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    condition: str,
    expected_name_suffix: str,
    expected_value: str,
) -> None:
    """Test event sensors for all 5 time periods."""
    monitors = [create_mock_monitor(name="Front Door")]
    entry = _entry_with_sensor_options(mock_config_entry, monitored_conditions=[condition])
    await setup_entry(hass, entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = f"sensor.front_door_{expected_name_suffix.lower().replace(' ', '_')}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_value


async def test_event_sensor_unit_of_measurement(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test event sensors have 'Events' unit of measurement."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.front_door_events")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == "Events"


async def test_event_sensor_name_format(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test event sensor name format is '{monitor_name} {time_period_title}'."""
    monitors = [create_mock_monitor(name="Back Yard")]
    entry = _entry_with_sensor_options(mock_config_entry, monitored_conditions=["hour"])
    await setup_entry(hass, entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.back_yard_events_last_hour")
    assert state is not None
    assert state.name == "Back Yard Events Last Hour"


async def test_event_sensor_none_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test event sensor handles None event count."""
    monitors = [
        create_mock_monitor(
            name="Front Door",
            events=dict.fromkeys(TimePeriod),
        )
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    state = hass.states.get("sensor.front_door_events")
    assert state is not None


# --- Run State Sensor ---


async def test_run_state_sensor_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state sensor is created."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    state = hass.states.get("sensor.run_state")
    assert state is not None


async def test_run_state_sensor_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state sensor shows state name."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors, active_state="Home")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.run_state")
    assert state is not None
    assert state.state == "Home"


async def test_run_state_device_info_includes_zm_version(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state sensor device info includes ZoneMinder version as sw_version."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    entity = hass.data["entity_components"]["sensor"].get_entity("sensor.run_state")
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert info["sw_version"] == "1.38.0"


async def test_run_state_sensor_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test run state sensor when server unavailable."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(
        hass, mock_config_entry, monitors=monitors, is_available=False, active_state=None
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.run_state")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


# --- Platform behavior ---


async def test_no_monitors_creates_run_state_only(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test empty monitors creates only run state sensor."""
    await setup_entry(hass, mock_config_entry, monitors=[])

    # Run state sensor still exists
    states = hass.states.async_all("sensor")
    assert len(states) == 1
    assert hass.states.get("sensor.run_state") is not None


async def test_subset_condition_filtering(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only selected monitored_conditions get event sensors."""
    monitors = [create_mock_monitor(name="Cam")]
    entry = _entry_with_sensor_options(mock_config_entry, monitored_conditions=["hour", "day"])
    await setup_entry(hass, entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Should have: 1 status + 2 event + 1 run state = 4 sensors
    states = hass.states.async_all("sensor")
    assert len(states) == 4

    # These should exist
    assert hass.states.get("sensor.cam_events_last_hour") is not None
    assert hass.states.get("sensor.cam_events_last_day") is not None

    # These should NOT exist
    assert hass.states.get("sensor.cam_events") is None
    assert hass.states.get("sensor.cam_events_last_week") is None
    assert hass.states.get("sensor.cam_events_last_month") is None


async def test_default_conditions_only_all(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test default monitored_conditions is only 'all'."""
    monitors = [create_mock_monitor(name="Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    # Should have: 1 status + 1 event (all) + 1 run state = 3 sensors
    states = hass.states.async_all("sensor")
    assert len(states) == 3


async def test_include_archived_flag(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test include_archived flag is passed correctly to get_event_counts."""
    monitors = [create_mock_monitor(name="Cam")]
    entry = _entry_with_sensor_options(
        mock_config_entry, include_archived=True, monitored_conditions=["all"]
    )
    client = await setup_entry(hass, entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify get_event_counts was called with include_archived=True
    client.get_event_counts.assert_any_call(TimePeriod.ALL, True)


async def test_sensor_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensor entities should have unique_id for UI customization."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    entry = entity_registry.async_get("sensor.front_door_status")
    assert entry is not None
    assert entry.unique_id is not None


async def test_function_property_no_side_effects(hass: HomeAssistant) -> None:
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
