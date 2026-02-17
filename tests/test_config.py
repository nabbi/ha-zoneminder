"""Tests for ZoneMinder YAML configuration validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.zoneminder.const import DOMAIN

from .conftest import MOCK_HOST, create_mock_zm_client


@pytest.fixture
def mock_zm_patch():
    """Patch ZoneMinder client for config validation tests.

    Patches both config_flow (import validation) and __init__ (entry setup).
    """
    client = create_mock_zm_client()
    with (
        patch(
            "custom_components.zoneminder.config_flow.ZoneMinder",
            return_value=client,
        ) as mock_flow,
        patch(
            "custom_components.zoneminder.ZoneMinder",
            return_value=client,
        ) as mock_init,
    ):
        yield mock_flow, mock_init, client


async def test_valid_minimal_config(hass: HomeAssistant, mock_zm_patch) -> None:
    """Test valid minimal configuration with only required host."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_valid_full_config(hass: HomeAssistant, mock_zm_patch) -> None:
    """Test valid full configuration with all optional fields."""
    config = {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
                CONF_PATH: "/zm/",
                "path_zms": "/zm/cgi-bin/nph-zms",
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
            }
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_valid_multi_server_config(
    hass: HomeAssistant, mock_zm_patch, multi_server_config
) -> None:
    """Test valid multi-server configuration."""
    assert await async_setup_component(hass, DOMAIN, multi_server_config)
    await hass.async_block_till_done()


async def test_valid_ssl_config(hass: HomeAssistant, mock_zm_patch, ssl_config) -> None:
    """Test valid SSL configuration."""
    assert await async_setup_component(hass, DOMAIN, ssl_config)
    await hass.async_block_till_done()


async def test_valid_no_auth_config(hass: HomeAssistant, mock_zm_patch, no_auth_config) -> None:
    """Test valid config without authentication credentials."""
    assert await async_setup_component(hass, DOMAIN, no_auth_config)
    await hass.async_block_till_done()


async def test_invalid_config_missing_host(hass: HomeAssistant) -> None:
    """Test that config without host is rejected."""
    config: dict = {DOMAIN: [{}]}

    result = await async_setup_component(hass, DOMAIN, config)
    # Config validation should reject this - component won't set up
    assert not result or DOMAIN not in hass.data


async def test_invalid_config_bad_ssl_type(hass: HomeAssistant) -> None:
    """Test that non-boolean ssl value is rejected."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST, CONF_SSL: "not_bool"}]}

    result = await async_setup_component(hass, DOMAIN, config)
    assert not result or DOMAIN not in hass.data
