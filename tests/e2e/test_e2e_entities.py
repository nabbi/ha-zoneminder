"""Live tests: entity states match what the ZoneMinder server reports."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from homeassistant.components.camera import async_get_image
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zoneminder.monitor import Monitor, TimePeriod, _derive_function, _is_zm_137_or_later
from zoneminder.zm import ZoneMinder

from custom_components.zoneminder.const import SUPPORT_PTZ
from custom_components.zoneminder.select import SYSTEM_STATES

from .conftest import ZmE2EConfig, coordinator_of, entity_id

pytestmark = pytest.mark.zm_e2e


def _expected_status(monitor: Monitor) -> str:
    """Return what the status sensor should show, derived as the integration does."""
    if monitor.capturing is not None and monitor.analysing is not None:
        if monitor.recording is not None:
            derived = _derive_function(monitor.capturing, monitor.analysing, monitor.recording)
            if derived is not None:
                return str(derived.value)
            return f"{monitor.capturing}/{monitor.analysing}/{monitor.recording}"
    return str(monitor.function.value)


async def test_server_entities(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_api: ZoneMinder,
    run_api: Callable[..., Awaitable[Any]],
    setup_live: MockConfigEntry,
) -> None:
    """Availability, run state sensor and run state select reflect the server."""
    host = zm_config.host
    run_states = await run_api(zm_api.get_run_states)
    active = next((rs.name for rs in run_states if rs.active), None)

    availability = hass.states.get(entity_id(hass, "binary_sensor", f"{host}_availability"))
    assert availability is not None
    assert availability.state == STATE_ON

    run_state = hass.states.get(entity_id(hass, "sensor", f"{host}_run_state"))
    assert run_state is not None
    assert run_state.state == active

    select = hass.states.get(entity_id(hass, "select", f"{host}_run_state_select"))
    assert select is not None
    assert select.state == active
    assert select.attributes["options"] == [
        *sorted(rs.name for rs in run_states),
        *SYSTEM_STATES,
    ]


async def test_monitor_entities_match_server(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_api: ZoneMinder,
    zm_monitors: list[Monitor],
    setup_live: MockConfigEntry,
) -> None:
    """Every monitor gets its entities, with states matching zm-py's view."""
    host = zm_config.host
    zm_137 = _is_zm_137_or_later(zm_api.zm_version)

    for monitor in zm_monitors:
        prefix = f"{host}_{monitor.id}"

        camera = hass.states.get(entity_id(hass, "camera", prefix))
        assert camera is not None
        assert (camera.state != STATE_UNAVAILABLE) is bool(monitor.is_available), monitor.name

        status = hass.states.get(entity_id(hass, "sensor", f"{prefix}_status"))
        assert status is not None
        assert status.state == _expected_status(monitor), monitor.name

        assert hass.states.get(entity_id(hass, "switch", f"{prefix}_force_alarm"))
        assert hass.states.get(entity_id(hass, "select", f"{prefix}_function"))

        if zm_137:
            for field in ("capturing", "analysing", "recording"):
                state = hass.states.get(entity_id(hass, "select", f"{prefix}_{field}"))
                assert state is not None
                assert state.state == getattr(monitor, field), f"{monitor.name} {field}"
        else:
            assert hass.states.get(entity_id(hass, "switch", f"{prefix}_switch"))


async def test_legacy_function_switch_absent_on_zm_137(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_api: ZoneMinder,
    zm_monitors: list[Monitor],
    setup_live: MockConfigEntry,
) -> None:
    """On ZM 1.37+ the Capturing/Analysing/Recording selects replace the function switch."""
    if not _is_zm_137_or_later(zm_api.zm_version):
        pytest.skip(f"ZoneMinder {zm_api.zm_version} is older than 1.37")
    registry_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(er.async_get(hass), setup_live.entry_id)
    }
    for monitor in zm_monitors:
        assert f"{zm_config.host}_{monitor.id}_switch" not in registry_ids


async def test_event_counts_match_server(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_api: ZoneMinder,
    zm_monitors: list[Monitor],
    run_api: Callable[..., Awaitable[Any]],
    setup_live: MockConfigEntry,
) -> None:
    """Event sensors show the server's counts (bracketed, as events may arrive meanwhile)."""
    before = await run_api(zm_api.get_event_counts, TimePeriod.ALL, False) or {}
    await coordinator_of(hass, setup_live).async_refresh()
    await hass.async_block_till_done()
    after = await run_api(zm_api.get_event_counts, TimePeriod.ALL, False) or {}

    for monitor in zm_monitors:
        state = hass.states.get(
            entity_id(hass, "sensor", f"{zm_config.host}_{monitor.id}_events_all")
        )
        assert state is not None
        count = int(state.state)
        key = str(monitor.id)
        assert before.get(key, 0) <= count <= after.get(key, 0), monitor.name


async def test_coordinator_refresh_succeeds(
    hass: HomeAssistant, setup_live: MockConfigEntry
) -> None:
    """A scheduled refresh against the live server succeeds and keeps entities fresh."""
    coordinator = coordinator_of(hass, setup_live)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert coordinator.data.server_available
    assert coordinator.data.run_state is not None


async def test_camera_still_image(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_monitors: list[Monitor],
    setup_live: MockConfigEntry,
) -> None:
    """The camera entity fetches a real JPEG from ZMS."""
    monitor = next((m for m in zm_monitors if m.is_available), None)
    if monitor is None:
        pytest.skip("No monitor is capturing")

    image = await async_get_image(
        hass, entity_id(hass, "camera", f"{zm_config.host}_{monitor.id}"), timeout=20
    )

    assert image.content_type == "image/jpeg"
    assert image.content[:2] == b"\xff\xd8"


async def test_ptz_feature_matches_controllable(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_monitors: list[Monitor],
    setup_live: MockConfigEntry,
) -> None:
    """Only controllable monitors advertise the PTZ feature."""
    for monitor in zm_monitors:
        state = hass.states.get(entity_id(hass, "camera", f"{zm_config.host}_{monitor.id}"))
        assert state is not None
        features = state.attributes.get("supported_features", 0)
        assert bool(features & SUPPORT_PTZ) is bool(monitor.controllable), monitor.name
