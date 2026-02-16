"""Tests for ZoneMinder camera entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.camera import CameraState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.zoneminder.camera import setup_platform
from custom_components.zoneminder.const import DOMAIN
from custom_components.zoneminder.coordinator import ZmDataUpdateCoordinator

from .conftest import MOCK_HOST, create_mock_monitor, create_mock_zm_client


async def _setup_zm_with_cameras(
    hass: HomeAssistant, config: dict, monitors: list, verify_ssl: bool = True
) -> MagicMock:
    """Set up ZM component with camera platform and given monitors."""
    client = create_mock_zm_client(monitors=monitors, verify_ssl=verify_ssl)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Camera uses setup_platform (sync), add camera platform explicitly
        assert await async_setup_component(
            hass,
            "camera",
            {"camera": [{"platform": DOMAIN}]},
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        # Trigger first poll to update entity state
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    return client


async def test_one_camera_per_monitor(
    hass: HomeAssistant, single_server_config, two_monitors
) -> None:
    """Test one camera entity is created per monitor."""
    await _setup_zm_with_cameras(hass, single_server_config, two_monitors)

    states = hass.states.async_all("camera")
    assert len(states) == 2


async def test_camera_entity_name(hass: HomeAssistant, single_server_config) -> None:
    """Test camera entity name matches monitor name."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    state = hass.states.get("camera.front_door")
    assert state is not None
    assert state.name == "Front Door"


async def test_camera_recording_state(hass: HomeAssistant, single_server_config) -> None:
    """Test camera recording state reflects monitor is_recording."""
    monitors = [create_mock_monitor(name="Recording Cam", is_recording=True, is_available=True)]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    state = hass.states.get("camera.recording_cam")
    assert state is not None
    assert state.state == CameraState.RECORDING


async def test_camera_idle_state(hass: HomeAssistant, single_server_config) -> None:
    """Test camera idle state when not recording."""
    monitors = [create_mock_monitor(name="Idle Cam", is_recording=False, is_available=True)]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    state = hass.states.get("camera.idle_cam")
    assert state is not None
    assert state.state == CameraState.IDLE


async def test_camera_unavailable_state(hass: HomeAssistant, single_server_config) -> None:
    """Test camera unavailable state tracking."""
    monitors = [create_mock_monitor(name="Offline Cam", is_available=False)]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    state = hass.states.get("camera.offline_cam")
    assert state is not None
    assert state.state == "unavailable"


async def test_no_monitors_raises_platform_not_ready(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test PlatformNotReady raised when no monitors returned."""
    client = create_mock_zm_client(monitors=[])

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done()
        await async_setup_component(
            hass,
            "camera",
            {"camera": [{"platform": DOMAIN}]},
        )
        await hass.async_block_till_done()

    # No camera entities should exist
    states = hass.states.async_all("camera")
    assert len(states) == 0


async def test_multi_server_camera_creation(hass: HomeAssistant, multi_server_config) -> None:
    """Test cameras created from multiple ZM servers."""
    monitors1 = [create_mock_monitor(monitor_id=1, name="Front Door")]
    monitors2 = [create_mock_monitor(monitor_id=2, name="Back Yard")]

    clients = iter(
        [
            create_mock_zm_client(monitors=monitors1),
            create_mock_zm_client(monitors=monitors2),
        ]
    )

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        side_effect=lambda *args, **kwargs: next(clients),
    ):
        assert await async_setup_component(hass, DOMAIN, multi_server_config)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert await async_setup_component(
            hass,
            "camera",
            {"camera": [{"platform": DOMAIN}]},
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    states = hass.states.async_all("camera")
    assert len(states) == 2


def test_filter_urllib3_logging_called(hass: HomeAssistant) -> None:
    """Test filter_urllib3_logging() is called in setup_platform."""
    monitors = [create_mock_monitor()]
    client = create_mock_zm_client(monitors=monitors)
    coordinator = ZmDataUpdateCoordinator(hass, client, monitors, MOCK_HOST)
    hass.data[DOMAIN] = {MOCK_HOST: client}
    hass.data[f"{DOMAIN}_monitors"] = {MOCK_HOST: monitors}
    hass.data[f"{DOMAIN}_coordinators"] = {MOCK_HOST: coordinator}

    with patch("custom_components.zoneminder.camera.filter_urllib3_logging") as mock_filter:
        setup_platform(hass, {}, MagicMock())

    mock_filter.assert_called_once()


async def test_camera_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, single_server_config
) -> None:
    """Camera entities should have unique_id for UI customization.

    No entity in the integration sets unique_id. This means entities cannot
    be customized via the HA UI and are fragile to name changes.
    """
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    entry = entity_registry.async_get("camera.front_door")
    assert entry is not None
    assert entry.unique_id is not None


async def test_camera_device_info(hass: HomeAssistant, single_server_config) -> None:
    """Camera entities should provide device_info to group under a device.

    Each monitor entity provides device_info so that camera, sensors, and switch
    for the same monitor are grouped on a single device page in the HA UI.
    Note: device registry integration requires config entries (future migration).
    """
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    entity = hass.data["entity_components"]["camera"].get_entity("camera.front_door")
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert (DOMAIN, f"{MOCK_HOST}_1") in info["identifiers"]
    assert info["name"] == "Front Door"
    assert info["manufacturer"] == "ZoneMinder"
    assert info["via_device"] == (DOMAIN, MOCK_HOST)


async def test_empty_server_does_not_raise_platform_not_ready(
    hass: HomeAssistant, single_server_config
) -> None:
    """A server with zero monitors should set up successfully, not retry forever.

    All platforms raise PlatformNotReady when get_monitors() returns empty,
    but an empty list is a legitimate permanent state (server has no monitors).
    """
    client = create_mock_zm_client(monitors=[])

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done()
        assert await async_setup_component(
            hass,
            "camera",
            {"camera": [{"platform": DOMAIN}]},
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Desired: platform loads successfully with 0 entities (not PlatformNotReady)
    # We verify by checking the platform didn't schedule a retry
    states = hass.states.async_all("camera")
    assert len(states) == 0
    # The key assertion: get_monitors was called only once (no retry loop)
    assert client.get_monitors.call_count == 1


@pytest.mark.xfail(reason="BUG-08: PTZ control not exposed despite zm-py support")
async def test_camera_supports_ptz(hass: HomeAssistant, single_server_config) -> None:
    """Camera should expose PTZ control when monitor is controllable.

    zm-py provides complete PTZ support via Monitor.ptz_control_command()
    and Monitor.controllable, but HA exposes none of it.
    """
    monitors = [create_mock_monitor(name="PTZ Cam")]
    monitors[0].controllable = True
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    state = hass.states.get("camera.ptz_cam")
    assert state is not None
    # Check for any PTZ-related supported feature or service
    supported = state.attributes.get("supported_features", 0)
    # Any PTZ feature bit should be set (the exact flag depends on HA version)
    assert supported > 0


async def test_get_monitors_called_once(hass: HomeAssistant, single_server_config) -> None:
    """get_monitors should be called once and shared across platforms.

    Each platform (camera, sensor, switch) independently calls get_monitors(),
    fetching monitors.json 3 times and creating separate Monitor object trees.
    """
    monitors = [create_mock_monitor(name="Front Door")]
    client = create_mock_zm_client(monitors=monitors)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Set up all three platforms
        assert await async_setup_component(hass, "camera", {"camera": [{"platform": DOMAIN}]})
        assert await async_setup_component(hass, "sensor", {"sensor": [{"platform": DOMAIN}]})
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": [
                    {
                        "platform": DOMAIN,
                        "command_on": "Modect",
                        "command_off": "Monitor",
                    }
                ]
            },
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    # Desired: monitors fetched once and shared across all platforms
    assert client.get_monitors.call_count == 1


async def test_coordinator_shared_updates(hass: HomeAssistant, single_server_config) -> None:
    """Entities should share a coordinator instead of polling independently.

    Camera entities set should_poll=False and get data from a shared
    ZmDataUpdateCoordinator instead of polling the ZM API independently.
    """
    monitors = [create_mock_monitor(name="Coord Cam")]
    await _setup_zm_with_cameras(hass, single_server_config, monitors)

    entity = hass.data["entity_components"]["camera"].get_entity("camera.coord_cam")
    assert entity is not None
    assert entity.should_poll is False
    assert hasattr(entity, "coordinator")
