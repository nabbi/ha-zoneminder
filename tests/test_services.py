"""Tests for ZoneMinder service calls."""

from __future__ import annotations

import pytest
import voluptuous as vol
from aiozoneminder import ZMApiError, ZMConnectionError
from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zoneminder.const import DOMAIN

from .conftest import MOCK_HOST, MOCK_HOST_2, setup_entry


async def test_set_run_state_service_registered(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test set_run_state service is registered after setup."""
    await setup_entry(hass, mock_config_entry)
    assert hass.services.has_service(DOMAIN, "set_run_state")


async def test_set_run_state_valid_call(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test valid set_run_state call sets state on correct ZM client."""
    client = await setup_entry(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST, ATTR_NAME: "Away"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.set_run_state.assert_awaited_once()
    assert client.set_run_state.await_args.args[0].name == "Away"


async def test_set_run_state_multi_server_targets_correct_server(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
) -> None:
    """Test set_run_state targets specific server by id."""
    client1 = await setup_entry(hass, mock_config_entry)
    client2 = await setup_entry(hass, mock_config_entry_2)

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST_2, ATTR_NAME: "Home"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Only the second server should have been called
    client2.set_run_state.assert_awaited_once()
    assert client2.set_run_state.await_args.args[0].name == "Home"
    client1.set_run_state.assert_not_awaited()


async def test_set_run_state_missing_fields_rejected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test service call with missing required fields is rejected."""
    await setup_entry(hass, mock_config_entry)

    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {ATTR_ID: MOCK_HOST},  # Missing ATTR_NAME
            blocking=True,
        )


async def test_set_run_state_invalid_host_graceful(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Invalid host should log error and return without exception."""
    await setup_entry(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: "invalid.host", ATTR_NAME: "Away"},
        blocking=True,
    )

    assert "Invalid ZoneMinder host provided" in caplog.text


async def test_set_active_state_api_error_logged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ZMApiError from set_run_state should be caught and logged."""
    client = await setup_entry(hass, mock_config_entry)
    client.set_run_state.side_effect = ZMApiError("API error")

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST, ATTR_NAME: "Away"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Error setting ZoneMinder run state" in caplog.text


async def test_set_active_state_request_timeout_logged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A timeout from set_run_state should be caught and logged."""
    client = await setup_entry(hass, mock_config_entry)
    client.set_run_state.side_effect = ZMConnectionError("timed out")

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST, ATTR_NAME: "Away"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert "Error setting ZoneMinder run state" in caplog.text
