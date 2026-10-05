"""Live tests: config flow, YAML import, options and reload against a real ZoneMinder."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zoneminder.monitor import Monitor, _is_zm_137_or_later
from zoneminder.zm import ZoneMinder

from custom_components.zoneminder.const import CONF_INCLUDE_ARCHIVED, CONF_PATH_ZMS, DOMAIN

from .conftest import ZmE2EConfig, entity_id

pytestmark = pytest.mark.zm_e2e


async def test_user_flow_creates_working_entry(
    hass: HomeAssistant, zm_config: ZmE2EConfig, zm_monitors: list[Monitor]
) -> None:
    """The user step logs in to the real server and the new entry loads."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], zm_config.entry_data)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == zm_config.host
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id(hass, "camera", f"{zm_config.host}_{zm_monitors[0].id}"))


async def test_user_flow_wrong_password(hass: HomeAssistant, zm_config: ZmE2EConfig) -> None:
    """A wrong password is reported as invalid_auth and no entry is created."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**zm_config.entry_data, CONF_PASSWORD: "definitely-not-the-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_user_flow_unreachable(hass: HomeAssistant, zm_config: ZmE2EConfig) -> None:
    """A host where nothing listens is reported as cannot_connect."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**zm_config.entry_data, CONF_HOST: "127.0.0.1:1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_yaml_import(hass: HomeAssistant, zm_config: ZmE2EConfig) -> None:
    """A YAML block is imported into a config entry that loads."""
    yaml_conf = {
        key: value
        for key, value in zm_config.entry_data.items()
        if key in (CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PATH_ZMS)
    }
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: [{**yaml_conf, "ssl": zm_config.ssl}]}
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].unique_id == zm_config.host


async def test_reconfigure_with_valid_credentials(
    hass: HomeAssistant, zm_config: ZmE2EConfig, setup_live: MockConfigEntry
) -> None:
    """Reconfiguring with working credentials validates live and reloads."""
    result = await setup_live.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], zm_config.entry_data)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert setup_live.state is ConfigEntryState.LOADED


async def test_options_flow_matches_server_version(
    hass: HomeAssistant, zm_api: ZoneMinder, setup_live: MockConfigEntry
) -> None:
    """command_on/off are offered only for servers older than ZM 1.37."""
    result = await hass.config_entries.options.async_init(setup_live.entry_id)
    assert result["type"] is FlowResultType.FORM

    keys = {str(key) for key in result["data_schema"].schema}
    legacy = not _is_zm_137_or_later(zm_api.zm_version)
    assert ("command_on" in keys) is legacy
    assert ("command_off" in keys) is legacy


async def test_options_change_reloads_with_new_sensors(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_monitors: list[Monitor],
    setup_live: MockConfigEntry,
) -> None:
    """Adding a monitored condition reloads the entry and adds its sensors."""
    monitor = zm_monitors[0]
    hour_uid = f"{zm_config.host}_{monitor.id}_events_hour"

    result = await hass.config_entries.options.async_init(setup_live.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_INCLUDE_ARCHIVED: False, CONF_MONITORED_CONDITIONS: ["all", "hour"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_live.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id(hass, "sensor", hour_uid))
    assert state is not None
    assert state.state.isdigit()


async def test_devices_registered(
    hass: HomeAssistant,
    zm_config: ZmE2EConfig,
    zm_api: ZoneMinder,
    zm_monitors: list[Monitor],
    setup_live: MockConfigEntry,
) -> None:
    """One server device with the live ZM version, and one device per monitor under it."""
    # Looked up by owning entry: async_get_device is deprecated (and raises) from HA 2026.10.
    devices = {
        identifier: device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), setup_live.entry_id)
        for identifier in device.identifiers
    }
    server = devices.get((DOMAIN, zm_config.host))
    assert server is not None
    assert server.sw_version == zm_api.zm_version

    for monitor in zm_monitors:
        device = devices.get((DOMAIN, f"{zm_config.host}_{monitor.id}"))
        assert device is not None, f"No device for monitor {monitor.name}"
        assert device.name == monitor.name
        assert device.via_device_id == server.id


async def test_unload(hass: HomeAssistant, setup_live: MockConfigEntry) -> None:
    """The entry unloads cleanly and drops its runtime data."""
    assert await hass.config_entries.async_unload(setup_live.entry_id)
    await hass.async_block_till_done()

    assert setup_live.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
