"""Live tests that switch ZoneMinder run states.

Enabled with ZM_E2E_RUN_STATE=1. Each switch restarts the ZoneMinder daemons
(not the containers), so monitors drop out for a few seconds. The original
state is restored, and the test waits for the monitors to come back.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zoneminder.zm import ZoneMinder

from custom_components.zoneminder.const import DOMAIN

from .conftest import ZmE2EConfig, coordinator_of, entity_id

pytestmark = pytest.mark.zm_e2e_run_state


async def _active_state(run_api: Callable[..., Awaitable[Any]], zm_api: ZoneMinder) -> str | None:
    states = await run_api(zm_api.get_run_states)
    return next((rs.name for rs in states if rs.active), None)


async def _wait_until_active(
    run_api: Callable[..., Awaitable[Any]], zm_api: ZoneMinder, name: str, timeout: float = 60
) -> None:
    deadline = time.monotonic() + timeout
    while (active := await _active_state(run_api, zm_api)) != name:
        if time.monotonic() > deadline:
            pytest.fail(f"Run state is {active!r}, expected {name!r}")
        await asyncio.sleep(1)


async def _wait_for_monitors(
    run_api: Callable[..., Awaitable[Any]], zm_api: ZoneMinder, expected: set[int]
) -> None:
    """Wait until every monitor that was capturing before is capturing again."""
    deadline = time.monotonic() + 90
    while True:
        monitors = await run_api(zm_api.get_monitors)
        if {m.id for m in monitors if m.is_available} >= expected:
            return
        if time.monotonic() > deadline:
            pytest.fail("Monitors did not come back after the run state change")
        await asyncio.sleep(2)


async def test_run_state_select_and_service(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_api: ZoneMinder,
    run_api: Callable[..., Awaitable[Any]],
    setup_live: MockConfigEntry,
) -> None:
    """Switch to another state with the select, then back with set_run_state."""
    states = sorted(rs.name for rs in await run_api(zm_api.get_run_states))
    original = await _active_state(run_api, zm_api)
    others = [name for name in states if name != original]
    if original is None or not others:
        pytest.skip(f"Need an active run state and another to switch to (have {states})")
    other = others[0]
    capturing = {m.id for m in await run_api(zm_api.get_monitors) if m.is_available}
    select_id = entity_id(hass, "select", f"{zm_config.host}_run_state_select")
    sensor_id = entity_id(hass, "sensor", f"{zm_config.host}_run_state")

    try:
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: select_id, "option": other},
            blocking=True,
        )
        await _wait_until_active(run_api, zm_api, other)
        await coordinator_of(hass, setup_live).async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(select_id).state == other
        assert hass.states.get(sensor_id).state == other

        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {ATTR_ID: zm_config.host, ATTR_NAME: original},
            blocking=True,
        )
        await _wait_until_active(run_api, zm_api, original)
        await coordinator_of(hass, setup_live).async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(sensor_id).state == original
    finally:
        if await _active_state(run_api, zm_api) != original:
            await run_api(zm_api.set_active_state, original)
            await _wait_until_active(run_api, zm_api, original)
        await _wait_for_monitors(run_api, zm_api, capturing)
