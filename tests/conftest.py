"""Shared fixtures for ZoneMinder integration tests."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

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
from zoneminder.monitor import MonitorState, TimePeriod

from custom_components.zoneminder.const import DOMAIN

CONF_PATH_ZMS = "path_zms"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for all tests."""


MOCK_HOST = "zm.example.com"
MOCK_HOST_2 = "zm2.example.com"


@pytest.fixture
def single_server_config() -> dict:
    """Return minimal single ZM server YAML config."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            }
        ]
    }


@pytest.fixture
def multi_server_config() -> dict:
    """Return two ZM servers with different settings."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            },
            {
                CONF_HOST: MOCK_HOST_2,
                CONF_USERNAME: "user2",
                CONF_PASSWORD: "pass2",
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
                CONF_PATH: "/zoneminder/",
                CONF_PATH_ZMS: "/zoneminder/cgi-bin/nph-zms",
            },
        ]
    }


@pytest.fixture
def no_auth_config() -> dict:
    """Return server config without username/password."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
            }
        ]
    }


@pytest.fixture
def ssl_config() -> dict:
    """Return server config with SSL enabled, verify_ssl disabled."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            }
        ]
    }


def create_mock_monitor(
    monitor_id: int = 1,
    name: str = "Front Door",
    function: MonitorState = MonitorState.MODECT,
    is_recording: bool = False,
    is_available: bool = True,
    mjpeg_image_url: str = "http://zm.example.com/mjpeg/1",
    still_image_url: str = "http://zm.example.com/still/1",
    events: dict[TimePeriod, int | None] | None = None,
) -> MagicMock:
    """Create a mock Monitor instance with configurable properties."""
    monitor = MagicMock()
    monitor.id = monitor_id
    monitor.name = name

    # function is both a property and a settable attribute in zm-py
    monitor.function = function

    monitor.is_recording = is_recording
    monitor.is_available = is_available
    monitor.mjpeg_image_url = mjpeg_image_url
    monitor.still_image_url = still_image_url

    if events is None:
        events = {
            TimePeriod.ALL: 100,
            TimePeriod.HOUR: 5,
            TimePeriod.DAY: 20,
            TimePeriod.WEEK: 50,
            TimePeriod.MONTH: 80,
        }

    def mock_get_events(time_period, include_archived=False):
        return events.get(time_period, 0)

    monitor.get_events = MagicMock(side_effect=mock_get_events)

    return monitor


@pytest.fixture
def mock_monitor():
    """Return a function to create mock Monitor instances."""
    return create_mock_monitor


@pytest.fixture
def two_monitors():
    """Pre-built list of 2 monitors."""
    return [
        create_mock_monitor(
            monitor_id=1,
            name="Front Door",
            function=MonitorState.MODECT,
            is_recording=True,
            is_available=True,
        ),
        create_mock_monitor(
            monitor_id=2,
            name="Back Yard",
            function=MonitorState.MONITOR,
            is_recording=False,
            is_available=True,
        ),
    ]


def create_mock_zm_client(
    is_available: bool = True,
    verify_ssl: bool = True,
    monitors: list | None = None,
    login_success: bool = True,
    active_state: str | None = "Running",
    zm_version: str | None = "1.38.0",
) -> MagicMock:
    """Create a mock ZoneMinder client."""
    client = MagicMock()
    client.login.return_value = login_success
    client.get_monitors.return_value = monitors or []

    # is_available, verify_ssl, and zm_version are properties in zm-py
    type(client).is_available = PropertyMock(return_value=is_available)
    type(client).verify_ssl = PropertyMock(return_value=verify_ssl)
    type(client).zm_version = PropertyMock(return_value=zm_version)

    client.get_active_state.return_value = active_state
    client.set_active_state.return_value = True
    client.update_all_monitors.return_value = None

    # Build get_event_counts mock from monitors' event data.
    # The coordinator pre-fetches event counts per time period; the mock
    # delegates to each monitor's get_events() to build the result dict.
    _monitors = monitors or []

    def _mock_get_event_counts(time_period, include_archived=False):
        result = {}
        for mon in _monitors:
            val = mon.get_events(time_period, include_archived)
            if val is None:
                return None
            result[str(mon.id)] = val
        return result

    client.get_event_counts = MagicMock(side_effect=_mock_get_event_counts)

    return client


@pytest.fixture
def mock_zm_client():
    """Return a factory for creating mock ZM clients."""
    return create_mock_zm_client


@pytest.fixture
async def setup_zm(hass: HomeAssistant, single_server_config, two_monitors) -> MagicMock:
    """Set up the ZoneMinder component with mocked client and monitors.

    Returns the mock ZM client for further assertions.
    """
    client = create_mock_zm_client(monitors=two_monitors)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done()

    return client


@pytest.fixture
def sensor_platform_config(single_server_config) -> dict:
    """Return sensor platform YAML with all monitored_conditions."""
    config = dict(single_server_config)
    config["sensor"] = [
        {
            "platform": DOMAIN,
            "include_archived": True,
            "monitored_conditions": ["all", "hour", "day", "week", "month"],
        }
    ]
    return config


@pytest.fixture
def switch_platform_config(single_server_config) -> dict:
    """Return switch platform YAML with command_on=Modect, command_off=Monitor."""
    config = dict(single_server_config)
    config["switch"] = [
        {
            "platform": DOMAIN,
            "command_on": "Modect",
            "command_off": "Monitor",
        }
    ]
    return config
