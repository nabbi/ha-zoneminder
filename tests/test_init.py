"""Tests for ZoneMinder __init__.py setup flow internals."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout
from zoneminder.exceptions import LoginError, ZoneminderError

from custom_components.zoneminder.const import DOMAIN

from .conftest import MOCK_HOST, MOCK_HOST_2, create_mock_zm_client, setup_entry


async def test_entry_setup_stores_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, two_monitors
) -> None:
    """Test config entry setup stores ZmEntryData in hass.data."""
    await setup_entry(hass, mock_config_entry, monitors=two_monitors)

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert entry_data.host_name == MOCK_HOST
    assert entry_data.client is not None
    assert entry_data.coordinator is not None
    assert len(entry_data.monitors) == 2


async def test_entry_setup_creates_host_map(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry setup populates host_map for service lookups."""
    await setup_entry(hass, mock_config_entry)

    host_map = hass.data[f"{DOMAIN}_host_map"]
    assert host_map[MOCK_HOST] == mock_config_entry.entry_id


async def test_entry_setup_login_called(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test login() is called during entry setup."""
    client = await setup_entry(hass, mock_config_entry)
    client.login.assert_called_once()


async def test_entry_setup_login_failure_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry raises ConfigEntryNotReady on login failure."""
    client = create_mock_zm_client(login_success=False)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entry_setup_connection_error_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry raises ConfigEntryNotReady on connection error."""
    client = create_mock_zm_client()
    client.login.side_effect = RequestsConnectionError("Connection refused")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entry_setup_login_error_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry raises ConfigEntryNotReady on LoginError."""
    client = create_mock_zm_client()
    client.login.side_effect = LoginError("Invalid credentials")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_entry_setup_timeout_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry raises ConfigEntryNotReady on timeout."""
    client = create_mock_zm_client()
    client.login.side_effect = Timeout("connection timed out")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_monitors_error_defaults_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test get_monitors error defaults to empty list."""
    client = create_mock_zm_client()
    client.get_monitors.side_effect = ZoneminderError("API error")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert "Error fetching monitors" in caplog.text
    entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert entry_data.monitors == []


async def test_entry_unload(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test entry unload cleans up hass.data."""
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entry data should be cleaned up
    assert DOMAIN not in hass.data or mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_multi_entry_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
) -> None:
    """Test multiple config entries set up correctly."""
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, mock_config_entry_2)

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry_2.entry_id in hass.data[DOMAIN]

    host_map = hass.data[f"{DOMAIN}_host_map"]
    assert MOCK_HOST in host_map
    assert MOCK_HOST_2 in host_map


async def test_services_registered(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test services are registered during entry setup."""
    await setup_entry(hass, mock_config_entry)
    assert hass.services.has_service(DOMAIN, "set_run_state")


async def test_yaml_import_fires_flow(hass: HomeAssistant, single_server_config) -> None:
    """Test YAML config fires import flow."""
    client = create_mock_zm_client()
    with (
        patch(
            "custom_components.zoneminder.config_flow.ZoneMinder",
            return_value=client,
        ),
        patch(
            "custom_components.zoneminder.ZoneMinder",
            return_value=client,
        ),
    ):
        from homeassistant.setup import async_setup_component

        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done()

    # An entry should have been created via import
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == MOCK_HOST
