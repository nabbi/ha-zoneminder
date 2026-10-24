"""Live tests: the config flow's API choice (auto, v2, v3) against a real ZoneMinder.

The v3 tests need zm-api (API v3) on the server and skip without it.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from zoneminder.monitor import Monitor

from custom_components.zoneminder.const import (
    API_AUTO,
    API_V2,
    API_V3,
    CONF_API_BACKEND,
    CONF_API_V3_URL,
    CONF_API_VERSION,
    DOMAIN,
)

from .conftest import ZmE2EConfig, coordinator_of, entity_id

pytestmark = pytest.mark.zm_e2e


async def _user_flow(hass: HomeAssistant, data: dict[str, Any]) -> Any:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    await hass.async_block_till_done()
    return result


async def test_auto_picks_v2(hass: HomeAssistant, zm_config: ZmE2EConfig) -> None:
    """With API v2 answering, auto stores v2 and the entry loads."""
    result = await _user_flow(hass, {**zm_config.entry_data, CONF_API_VERSION: API_AUTO})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_VERSION] == API_AUTO
    assert result["data"][CONF_API_BACKEND] == API_V2
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED


async def test_auto_wrong_password(hass: HomeAssistant, zm_config: ZmE2EConfig) -> None:
    """A wrong password under auto is invalid_auth, not cannot_connect."""
    result = await _user_flow(
        hass,
        {**zm_config.entry_data, CONF_API_VERSION: API_AUTO, CONF_PASSWORD: "not-the-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_v3_found_and_loads(
    hass: HomeAssistant, zm_config: ZmE2EConfig, zm_monitors: list[Monitor]
) -> None:
    """API v3 picked: zm-api is found under the web path or root, and the entry runs on it.

    Unique IDs are the same as on API v2, so switching API keeps the entities.
    """
    result = await _user_flow(hass, {**zm_config.entry_data, CONF_API_VERSION: API_V3})
    if result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}:
        pytest.skip("no zm-api (API v3) on this server")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_BACKEND] == API_V3
    assert result["data"][CONF_API_V3_URL].startswith(zm_config.url)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED

    coordinator = coordinator_of(hass, entry)
    assert coordinator.last_update_success
    assert set(coordinator.data.monitors) == {m.id for m in zm_monitors}
    for monitor in zm_monitors:
        assert hass.states.get(entity_id(hass, "camera", f"{zm_config.host}_{monitor.id}"))


async def test_v3_wrong_password(hass: HomeAssistant, zm_config: ZmE2EConfig) -> None:
    """API v3 picked and the password wrong: invalid_auth."""
    result = await _user_flow(
        hass,
        {**zm_config.entry_data, CONF_API_VERSION: API_V3, CONF_PASSWORD: "not-the-password"},
    )
    if result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}:
        pytest.skip("no zm-api (API v3) on this server")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
