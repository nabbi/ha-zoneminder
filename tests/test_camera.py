"""Tests for ZoneMinder camera entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
import voluptuous as vol
from homeassistant.components.camera import CameraState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from zoneminder.exceptions import MonitorControlTypeError

from custom_components.zoneminder.const import DOMAIN

from .conftest import (
    MOCK_HOST,
    create_mock_monitor,
    setup_entry,
)


async def test_one_camera_per_monitor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, two_monitors
) -> None:
    """Test one camera entity is created per monitor."""
    await setup_entry(hass, mock_config_entry, monitors=two_monitors)

    states = hass.states.async_all("camera")
    assert len(states) == 2


async def test_camera_entity_name(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test camera entity name matches monitor name."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    state = hass.states.get("camera.front_door")
    assert state is not None
    assert state.name == "Front Door"


async def test_camera_recording_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test camera recording state reflects monitor is_recording."""
    monitors = [create_mock_monitor(name="Recording Cam", is_recording=True, is_available=True)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    # Trigger poll
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.recording_cam")
    assert state is not None
    assert state.state == CameraState.RECORDING


async def test_camera_idle_state(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test camera idle state when not recording."""
    monitors = [create_mock_monitor(name="Idle Cam", is_recording=False, is_available=True)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.idle_cam")
    assert state is not None
    assert state.state == CameraState.IDLE


async def test_camera_unavailable_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test camera unavailable state tracking."""
    monitors = [create_mock_monitor(name="Offline Cam", is_available=False)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.offline_cam")
    assert state is not None
    assert state.state == "unavailable"


async def test_no_monitors_no_cameras(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test no cameras when no monitors returned."""
    await setup_entry(hass, mock_config_entry, monitors=[])

    states = hass.states.async_all("camera")
    assert len(states) == 0


async def test_multi_server_camera_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
) -> None:
    """Test cameras created from multiple ZM servers."""
    monitors1 = [create_mock_monitor(monitor_id=1, name="Front Door")]
    monitors2 = [create_mock_monitor(monitor_id=2, name="Back Yard")]

    await setup_entry(hass, mock_config_entry, monitors=monitors1)
    await setup_entry(hass, mock_config_entry_2, monitors=monitors2)

    states = hass.states.async_all("camera")
    assert len(states) == 2


async def test_camera_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Camera entities should have unique_id for UI customization."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    entry = entity_registry.async_get("camera.front_door")
    assert entry is not None
    assert entry.unique_id is not None


async def test_camera_device_info(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Camera entities should provide device_info to group under a device."""
    monitors = [create_mock_monitor(name="Front Door")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    entity = hass.data["entity_components"]["camera"].get_entity("camera.front_door")
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert (DOMAIN, f"{MOCK_HOST}_1") in info["identifiers"]
    assert info["name"] == "Front Door"
    assert info["manufacturer"] == "ZoneMinder"
    assert info["via_device"] == (DOMAIN, MOCK_HOST)


async def test_empty_server_creates_no_cameras(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A server with zero monitors should set up successfully with no cameras."""
    await setup_entry(hass, mock_config_entry, monitors=[])

    states = hass.states.async_all("camera")
    assert len(states) == 0


async def test_get_monitors_called_once(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """get_monitors should be called once per entry setup."""
    monitors = [create_mock_monitor(name="Front Door")]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)

    # get_monitors is called once during async_setup_entry
    assert client.get_monitors.call_count == 1


async def test_coordinator_shared_updates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Entities should share a coordinator instead of polling independently."""
    monitors = [create_mock_monitor(name="Coord Cam")]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    entity = hass.data["entity_components"]["camera"].get_entity("camera.coord_cam")
    assert entity is not None
    assert entity.should_poll is False
    assert hasattr(entity, "coordinator")


# --- PTZ tests ---


async def test_ptz_supported_features_set_on_controllable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Controllable cameras should have SUPPORT_PTZ in supported_features."""
    monitors = [
        create_mock_monitor(name="PTZ Cam", controllable=True),
        create_mock_monitor(monitor_id=2, name="Fixed Cam", controllable=False),
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    ptz_state = hass.states.get("camera.ptz_cam")
    assert ptz_state is not None
    assert ptz_state.attributes.get("supported_features", 0) & 4

    fixed_state = hass.states.get("camera.fixed_cam")
    assert fixed_state is not None
    assert not (fixed_state.attributes.get("supported_features", 0) & 4)


async def test_ptz_moves_controllable_camera(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """PTZ service call should invoke move_monitor on a controllable camera."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)

    await hass.services.async_call(
        DOMAIN,
        "ptz",
        {"direction": "right"},
        target={"entity_id": "camera.ptz_cam"},
        blocking=True,
    )

    client.move_monitor.assert_called_once_with(monitors[0], "right")


async def test_ptz_raises_on_non_controllable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """PTZ service should raise ServiceNotSupported on non-controllable camera."""
    monitors = [create_mock_monitor(name="Fixed Cam", controllable=False)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "ptz",
            {"direction": "up"},
            target={"entity_id": "camera.fixed_cam"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "direction",
    ["right", "left", "up", "down", "up_left", "up_right", "down_left", "down_right"],
)
async def test_ptz_all_directions(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, direction: str
) -> None:
    """All 8 PTZ directions should be accepted."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)

    await hass.services.async_call(
        DOMAIN,
        "ptz",
        {"direction": direction},
        target={"entity_id": "camera.ptz_cam"},
        blocking=True,
    )

    client.move_monitor.assert_called_once_with(monitors[0], direction)


async def test_ptz_invalid_direction_rejected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Invalid direction should be rejected by schema validation."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "ptz",
            {"direction": "diagonal"},
            target={"entity_id": "camera.ptz_cam"},
            blocking=True,
        )


async def test_ptz_api_error_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """zm-py exception should be wrapped in HomeAssistantError."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)
    client.move_monitor = MagicMock(side_effect=MonitorControlTypeError())

    with pytest.raises(HomeAssistantError, match="Failed to move camera"):
        await hass.services.async_call(
            DOMAIN,
            "ptz",
            {"direction": "left"},
            target={"entity_id": "camera.ptz_cam"},
            blocking=True,
        )


async def test_ptz_returns_false_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """move_monitor returning False should raise HomeAssistantError."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)
    client.move_monitor = MagicMock(return_value=False)

    with pytest.raises(HomeAssistantError, match="Failed to move camera"):
        await hass.services.async_call(
            DOMAIN,
            "ptz",
            {"direction": "down"},
            target={"entity_id": "camera.ptz_cam"},
            blocking=True,
        )


# --- PTZ preset tests ---


async def test_ptz_preset_calls_goto_preset(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """PTZ preset service with preset > 0 should call goto_preset."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)

    await hass.services.async_call(
        DOMAIN,
        "ptz_preset",
        {"preset": 3},
        target={"entity_id": "camera.ptz_cam"},
        blocking=True,
    )

    client.goto_preset.assert_called_once_with(monitors[0], 3)


async def test_ptz_preset_zero_calls_goto_home(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """PTZ preset service with preset=0 should call goto_home."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)

    await hass.services.async_call(
        DOMAIN,
        "ptz_preset",
        {"preset": 0},
        target={"entity_id": "camera.ptz_cam"},
        blocking=True,
    )

    client.goto_home.assert_called_once_with(monitors[0])


async def test_ptz_preset_raises_on_non_controllable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """PTZ preset service should raise on non-controllable camera."""
    monitors = [create_mock_monitor(name="Fixed Cam", controllable=False)]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "ptz_preset",
            {"preset": 1},
            target={"entity_id": "camera.fixed_cam"},
            blocking=True,
        )


async def test_ptz_preset_api_error_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """zm-py exception should be wrapped in HomeAssistantError."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)
    client.goto_preset = MagicMock(side_effect=MonitorControlTypeError())

    with pytest.raises(HomeAssistantError, match="Failed to move camera"):
        await hass.services.async_call(
            DOMAIN,
            "ptz_preset",
            {"preset": 5},
            target={"entity_id": "camera.ptz_cam"},
            blocking=True,
        )


async def test_ptz_preset_returns_false_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """goto_preset returning False should raise HomeAssistantError."""
    monitors = [create_mock_monitor(name="PTZ Cam", controllable=True)]
    client = await setup_entry(hass, mock_config_entry, monitors=monitors)
    client.goto_preset = MagicMock(return_value=False)

    with pytest.raises(HomeAssistantError, match="Failed to move camera"):
        await hass.services.async_call(
            DOMAIN,
            "ptz_preset",
            {"preset": 2},
            target={"entity_id": "camera.ptz_cam"},
            blocking=True,
        )
