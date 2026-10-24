"""Shared fixtures for ZoneMinder integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiozoneminder import (
    EventSummary,
    Monitor,
    MonitorStatus,
    RunState,
    ServerInfo,
    ZMAuthenticationError,
    function_fields,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zoneminder.const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    DEFAULT_COMMAND_OFF,
    DEFAULT_COMMAND_ON,
    DEFAULT_INCLUDE_ARCHIVED,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from custom_components.zoneminder.monitor_state import MonitorState, TimePeriod, derive_function


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for all tests."""


MOCK_HOST = "zm.example.com"
MOCK_HOST_2 = "zm2.example.com"

MOCK_ENTRY_DATA = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_SSL: DEFAULT_SSL,
    CONF_PATH: DEFAULT_PATH,
    CONF_PATH_ZMS: DEFAULT_PATH_ZMS,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}

MOCK_ENTRY_OPTIONS = {
    CONF_INCLUDE_ARCHIVED: DEFAULT_INCLUDE_ARCHIVED,
    CONF_MONITORED_CONDITIONS: DEFAULT_MONITORED_CONDITIONS,
    "command_on": DEFAULT_COMMAND_ON,
    "command_off": DEFAULT_COMMAND_OFF,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for ZoneMinder."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_HOST,
        data=MOCK_ENTRY_DATA,
        options=MOCK_ENTRY_OPTIONS,
        unique_id=MOCK_HOST,
        source=SOURCE_USER,
    )


@pytest.fixture
def mock_config_entry_2() -> MockConfigEntry:
    """Return a second MockConfigEntry for multi-server tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_HOST_2,
        data={
            CONF_HOST: MOCK_HOST_2,
            CONF_USERNAME: "user2",
            CONF_PASSWORD: "pass2",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
            CONF_PATH: "/zoneminder/",
            CONF_PATH_ZMS: "/zoneminder/cgi-bin/nph-zms",
        },
        options=MOCK_ENTRY_OPTIONS,
        unique_id=MOCK_HOST_2,
        source=SOURCE_USER,
    )


# --- YAML config fixtures (for config validation tests) ---


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
    capturing: str | None = None,
    analysing: str | None = None,
    recording: str | None = None,
    controllable: bool = False,
) -> MagicMock:
    """Create a mock monitor: the server-side state the mock client reports.

    Tests change these attributes and refresh to simulate the server changing.
    ``capturing``/``analysing``/``recording`` left None follow ``function``.
    """
    monitor = MagicMock()
    monitor.id = monitor_id
    monitor.name = name
    monitor.function = function

    monitor.is_recording = is_recording
    monitor.is_available = is_available
    monitor.controllable = controllable
    monitor.mjpeg_image_url = mjpeg_image_url
    monitor.still_image_url = still_image_url

    # ZM 1.37+ individual fields (None = pre-1.37 / field absent)
    monitor.capturing = capturing
    monitor.analysing = analysing
    monitor.recording = recording

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


def monitor_fields(mon: MagicMock) -> tuple[str, str, str]:
    """Return a mock monitor's (capturing, analysing, recording) as the server reports them.

    Fields left None follow the monitor's function.
    """
    from_function = function_fields(mon.function.value if mon.function else "None")
    capturing, analysing, recording = (
        value if value is not None else default
        for value, default in zip(
            (mon.capturing, mon.analysing, mon.recording), from_function, strict=True
        )
    )
    return capturing, analysing, recording


def _write_monitor_state(mon: MagicMock, **fields: str | None) -> None:
    """Apply a set_monitor_state call to a mock monitor, as the server would."""
    current = dict(zip(("capturing", "analysing", "recording"), monitor_fields(mon), strict=True))
    current.update({key: value for key, value in fields.items() if value is not None})
    mon.capturing, mon.analysing, mon.recording = (
        current["capturing"],
        current["analysing"],
        current["recording"],
    )
    if function := derive_function(mon.capturing, mon.analysing, mon.recording):
        mon.function = function


def _as_monitor(mon: MagicMock) -> Monitor:
    """Return the aiozoneminder Monitor the mock client lists for a mock monitor."""
    capturing, analysing, recording = monitor_fields(mon)
    return Monitor(
        id=mon.id,
        name=mon.name,
        type="Ffmpeg",
        width=1920,
        height=1080,
        capturing=capturing,
        analysing=analysing,
        recording=recording,
        controllable=mon.controllable,
    )


def create_mock_zm_client(
    is_available: bool = True,
    verify_ssl: bool = True,
    monitors: list | None = None,
    login_success: bool = True,
    active_state: str | None = "Running",
    run_state_names: list[str] | None = None,
    zm_version: str | None = "1.38.0",
) -> MagicMock:
    """Create a mock aiozoneminder API v2 client.

    Reads come from the mock monitors at call time. ``client.is_available``
    (daemonCheck) and ``client.zm_version`` can be changed by tests too.
    """
    client = MagicMock()
    client.is_available = is_available
    client.zm_version = zm_version
    client.verify_ssl = verify_ssl
    _monitors = monitors or []
    by_id = {mon.id: mon for mon in _monitors}

    if login_success:
        client.authenticate = AsyncMock(return_value=True)
    else:
        client.authenticate = AsyncMock(side_effect=ZMAuthenticationError("Invalid login"))
    client.close = AsyncMock()
    client.get_version = AsyncMock(side_effect=lambda: client.zm_version)
    client.get_server_info = AsyncMock(
        side_effect=lambda: ServerInfo(version=client.zm_version, running=client.is_available)
    )
    client.get_monitors = AsyncMock(side_effect=lambda: [_as_monitor(m) for m in _monitors])
    client.get_monitor_statuses = AsyncMock(
        side_effect=lambda: {
            m.id: MonitorStatus(
                monitor_id=m.id, status="Connected" if m.is_available else "NotRunning"
            )
            for m in _monitors
        }
    )
    client.get_alarm_state = AsyncMock(
        side_effect=lambda monitor_id: "alarm" if by_id[monitor_id].is_recording else "idle"
    )

    def _event_summary(monitor_id: int, *, include_archived: bool = True) -> EventSummary | None:
        mon = by_id[monitor_id]
        counts = {}
        for time_period in TimePeriod:
            value = mon.get_events(time_period, include_archived)
            if value is None:
                return None
            counts[time_period.summary_field] = value
        return EventSummary(monitor_id=monitor_id, **counts)

    client.get_event_summary = AsyncMock(side_effect=_event_summary)

    _run_state_names = run_state_names or ["Away", "Home", "Running"]
    client.get_run_states = AsyncMock(
        return_value=[
            RunState(id=i, name=name, definition="", active=name == active_state)
            for i, name in enumerate(_run_state_names, start=1)
        ]
    )

    client.set_monitor_state = AsyncMock(
        side_effect=lambda monitor_id, **fields: _write_monitor_state(by_id[monitor_id], **fields)
    )
    client.set_run_state = AsyncMock()
    client.server_control = AsyncMock()
    client.trigger_alarm = AsyncMock()
    client.cancel_alarm = AsyncMock()
    client.ptz = AsyncMock()
    client.get_stream_url = MagicMock(
        side_effect=lambda monitor_id, mode="jpeg": by_id[monitor_id].mjpeg_image_url
    )
    client.async_get_snapshot = AsyncMock(return_value=b"\xff\xd8image")

    return client


@pytest.fixture
def mock_zm_client():
    """Return a factory for creating mock ZM clients."""
    return create_mock_zm_client


async def setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    monitors: list | None = None,
    is_available: bool = True,
    active_state: str | None = "Running",
    run_state_names: list[str] | None = None,
    zm_version: str | None = "1.38.0",
    verify_ssl: bool = True,
) -> MagicMock:
    """Set up a ZoneMinder config entry and return the mock client."""
    client = create_mock_zm_client(
        monitors=monitors or [],
        is_available=is_available,
        active_state=active_state,
        run_state_names=run_state_names,
        zm_version=zm_version,
        verify_ssl=verify_ssl,
    )

    entry.add_to_hass(hass)

    with patch(
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
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
