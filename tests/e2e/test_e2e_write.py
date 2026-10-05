"""Live tests that change the server: monitor settings, force alarm and PTZ.

Enabled with ZM_E2E_WRITE=1. Every test restores what it changed, so they
are safe on a shared simulator, but each one is visible to anything else
watching the server (events are recorded and cameras move).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zoneminder.monitor import Monitor, MonitorState, _is_zm_137_or_later
from zoneminder.zm import ZoneMinder

from custom_components.zoneminder.const import DOMAIN

from .conftest import ZmE2EConfig, coordinator_of, entity_id

pytestmark = pytest.mark.zm_e2e_write

FetchMonitor = Callable[[int], Awaitable[Monitor]]


async def _wait_for_state(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    ent_id: str,
    expected: str,
    timeout: float = 20,
) -> None:
    """Refresh the coordinator until the entity shows the expected state."""
    deadline = time.monotonic() + timeout
    while True:
        await coordinator_of(hass, entry).async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get(ent_id)
        if state is not None and state.state == expected:
            return
        if time.monotonic() > deadline:
            pytest.fail(f"{ent_id} is {state.state if state else None!r}, expected {expected!r}")
        await asyncio.sleep(1)


async def _select(hass: HomeAssistant, ent_id: str, option: str) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: ent_id, "option": option},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.fixture
def require_zm_137(zm_api: ZoneMinder) -> None:
    """Skip unless the server has the 1.37+ Capturing/Analysing/Recording fields."""
    if not _is_zm_137_or_later(zm_api.zm_version):
        pytest.skip(f"ZoneMinder {zm_api.zm_version} is older than 1.37")


@pytest.mark.usefixtures("require_zm_137")
async def test_recording_select_round_trip(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    target_monitor: Monitor,
    fresh_monitor: FetchMonitor,
    run_api: Callable[..., Awaitable[Any]],
    setup_live: MockConfigEntry,
) -> None:
    """Changing Recording in HA writes it to ZoneMinder, and changing it back restores it."""
    ent_id = entity_id(hass, "select", f"{zm_config.host}_{target_monitor.id}_recording")
    original = (await fresh_monitor(target_monitor.id)).recording
    assert original is not None
    new_value = "Always" if original != "Always" else "OnMotion"

    try:
        await _select(hass, ent_id, new_value)
        assert (await fresh_monitor(target_monitor.id)).recording == new_value
        await _wait_for_state(hass, setup_live, ent_id, new_value)

        await _select(hass, ent_id, original)
        assert (await fresh_monitor(target_monitor.id)).recording == original
        await _wait_for_state(hass, setup_live, ent_id, original)
    finally:
        monitor = await fresh_monitor(target_monitor.id)
        if monitor.recording != original:

            def _restore() -> None:
                monitor.recording = original

            await run_api(_restore)


async def test_function_select_round_trip(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    target_monitor: Monitor,
    fresh_monitor: FetchMonitor,
    run_api: Callable[..., Awaitable[Any]],
    setup_live: MockConfigEntry,
) -> None:
    """Picking a function in HA changes it on the server (via the 1.37 fields when present)."""
    ent_id = entity_id(hass, "select", f"{zm_config.host}_{target_monitor.id}_function")
    state = hass.states.get(ent_id)
    assert state is not None
    if state.state not in {s.value for s in MonitorState}:
        pytest.skip(f"{target_monitor.name} has a custom function ({state.state})")
    original = MonitorState(state.state)
    new_value = MonitorState.MOCORD if original != MonitorState.MOCORD else MonitorState.MODECT

    try:
        await _select(hass, ent_id, new_value.value)
        assert (await fresh_monitor(target_monitor.id)).function == new_value
        await _wait_for_state(hass, setup_live, ent_id, new_value.value)

        await _select(hass, ent_id, original.value)
        assert (await fresh_monitor(target_monitor.id)).function == original
        await _wait_for_state(hass, setup_live, ent_id, original.value)
    finally:
        monitor = await fresh_monitor(target_monitor.id)
        if monitor.function != original:

            def _restore() -> None:
                monitor.function = original

            await run_api(_restore)


async def test_force_alarm_switch(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    target_monitor: Monitor,
    run_api: Callable[..., Awaitable[Any]],
    setup_live: MockConfigEntry,
) -> None:
    """The force alarm switch puts the monitor into alarm and takes it out again."""
    ent_id = entity_id(hass, "switch", f"{zm_config.host}_{target_monitor.id}_force_alarm")

    try:
        await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: ent_id}, blocking=True)
        await _wait_for_state(hass, setup_live, ent_id, STATE_ON)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: ent_id}, blocking=True
        )
        await _wait_for_state(hass, setup_live, ent_id, STATE_OFF, timeout=30)
    finally:
        await run_api(target_monitor.set_force_alarm_state, False)


async def test_ptz_move_and_home(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    ptz_monitor: Monitor,
    setup_live: MockConfigEntry,
) -> None:
    """The ptz and ptz_preset services drive a real PTZ camera through ZoneMinder."""
    ent_id = entity_id(hass, "camera", f"{zm_config.host}_{ptz_monitor.id}")

    for direction in ("right", "left"):
        await hass.services.async_call(
            DOMAIN, "ptz", {ATTR_ENTITY_ID: ent_id, "direction": direction}, blocking=True
        )
    await hass.services.async_call(
        DOMAIN, "ptz_preset", {ATTR_ENTITY_ID: ent_id, "preset": 0}, blocking=True
    )
