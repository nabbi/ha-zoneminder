"""Fixtures for live end-to-end tests against a running ZoneMinder server.

These tests set the integration up in a test Home Assistant against a real
ZoneMinder (e.g. a zm-holodeck stack) and compare what HA shows with what an
independent zm-py client reads from the same server.

Configuration comes from the environment or from ``.env.zm_e2e`` in the
project root (same variable names as zm-py's live suite):

    ZM_HOST            ZoneMinder base URL, e.g. http://127.0.0.1:8480 (required)
    ZM_USER            username (default: admin)
    ZM_PASSWORD        password (default: admin)
    ZM_SERVER_PATH     server path (default: /zm/)
    ZM_ZMS_PATH        ZMS CGI path (default: /zm/cgi-bin/nph-zms)
    ZM_VERIFY_SSL      verify TLS certificates (default: false)
    ZM_E2E_WRITE       "1" enables tests that change monitors, force alarms and move PTZ
    ZM_E2E_RUN_STATE   "1" enables run state switching (restarts the ZoneMinder daemons)
    ZM_E2E_MONITOR     id or name of the monitor the write tests change
    ZM_E2E_PTZ_MONITOR id or name of the monitor the PTZ tests move

Without ZM_HOST every test here is skipped, so ``pytest tests`` stays offline.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlsplit

import pytest
import pytest_socket
import zoneminder
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
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
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zoneminder.monitor import Monitor
from zoneminder.zm import ZoneMinder

from custom_components.zoneminder.const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    DEFAULT_COMMAND_OFF,
    DEFAULT_COMMAND_ON,
    DOMAIN,
)
from custom_components.zoneminder.coordinator import ZmDataUpdateCoordinator
from custom_components.zoneminder.models import ZmEntryData

_T = TypeVar("_T")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env.zm_e2e"


def _load_env_file() -> dict[str, str]:
    """Parse KEY=VALUE lines from .env.zm_e2e, ignoring blanks and comments."""
    if not _ENV_FILE.is_file():
        return {}
    values: dict[str, str] = {}
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        if key:
            values[key.strip()] = val.strip()
    return values


_FILE_VALUES = _load_env_file()


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, _FILE_VALUES.get(name, default))


def _flag(name: str) -> bool:
    return _get(name).lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class ZmE2EConfig:
    """Connection settings for the live ZoneMinder server."""

    url: str
    host: str
    ssl: bool
    username: str
    password: str
    path: str
    path_zms: str
    verify_ssl: bool

    @property
    def hostname(self) -> str:
        """Host without the port."""
        return urlsplit(self.url).hostname or ""

    @property
    def entry_data(self) -> dict[str, Any]:
        """Config entry data, as the user step would store it."""
        return {
            CONF_HOST: self.host,
            CONF_USERNAME: self.username,
            CONF_PASSWORD: self.password,
            CONF_SSL: self.ssl,
            CONF_PATH: self.path,
            CONF_PATH_ZMS: self.path_zms,
            CONF_VERIFY_SSL: self.verify_ssl,
        }


def _load_config() -> ZmE2EConfig | None:
    url = _get("ZM_HOST")
    if not url:
        return None
    if "://" not in url:
        url = f"http://{url}"
    parts = urlsplit(url)
    return ZmE2EConfig(
        url=f"{parts.scheme}://{parts.netloc}",
        # The integration stores host[:port] and derives the scheme from CONF_SSL.
        host=parts.netloc,
        ssl=parts.scheme == "https",
        username=_get("ZM_USER", "admin"),
        password=_get("ZM_PASSWORD", "admin"),
        path=_get("ZM_SERVER_PATH", "/zm/"),
        path_zms=_get("ZM_ZMS_PATH", "/zm/cgi-bin/nph-zms"),
        verify_ssl=_flag("ZM_VERIFY_SSL"),
    )


ZM_CONFIG = _load_config()
WRITE_ENABLED = _flag("ZM_E2E_WRITE")
RUN_STATE_ENABLED = _flag("ZM_E2E_RUN_STATE")

# ---------------------------------------------------------------------------
# Collection: skip tiers that are not enabled
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live tests when no server is configured or their tier is off."""
    skip_no_server = pytest.mark.skip(reason="ZM_HOST not set (no .env.zm_e2e)")
    skip_no_write = pytest.mark.skip(reason="ZM_E2E_WRITE != 1 (write tests disabled)")
    skip_no_run_state = pytest.mark.skip(
        reason="ZM_E2E_RUN_STATE != 1 (run state switching disabled)"
    )
    for item in items:
        markers = {m.name for m in item.iter_markers()}
        if not markers & {"zm_e2e", "zm_e2e_write", "zm_e2e_run_state"}:
            continue
        if ZM_CONFIG is None:
            item.add_marker(skip_no_server)
        elif "zm_e2e_run_state" in markers and not RUN_STATE_ENABLED:
            item.add_marker(skip_no_run_state)
        elif "zm_e2e_write" in markers and not WRITE_ENABLED:
            item.add_marker(skip_no_write)


# ---------------------------------------------------------------------------
# Sockets: the HA test plugin blocks all network access in every test
# ---------------------------------------------------------------------------

# Captured at import, before the HA test plugin patches it for each test.
_REAL_GETADDRINFO = socket.getaddrinfo
_ZM_ADDRS: list[str] = (
    sorted({str(info[4][0]) for info in _REAL_GETADDRINFO(ZM_CONFIG.hostname, None)})
    if ZM_CONFIG is not None
    else []
)


def _open_zm_sockets() -> None:
    """Allow connections to the ZoneMinder server, and nowhere else.

    pytest-homeassistant-custom-component disables sockets and DNS before each
    test. Live tests need the configured server (by name, if it has one).
    """
    assert ZM_CONFIG is not None
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.1", "::1", *_ZM_ADDRS], allow_unix_socket=True)

    patched_getaddrinfo = socket.getaddrinfo
    hostname = ZM_CONFIG.hostname

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host == hostname:
            return _REAL_GETADDRINFO(host, *args, **kwargs)
        return patched_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo


@pytest.fixture(autouse=True)
def _zm_sockets(zm_config: ZmE2EConfig) -> None:
    """Open the ZoneMinder server to each live test."""
    _open_zm_sockets()


# ---------------------------------------------------------------------------
# Session fixtures: ground truth from an independent zm-py client
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def zm_config() -> ZmE2EConfig:
    """Return the connection settings for the live server."""
    if ZM_CONFIG is None:
        pytest.skip("ZM_HOST not set")
    # Session fixtures that log in are built before the per-test autouse fixture.
    _open_zm_sockets()
    return ZM_CONFIG


def _new_client(cfg: ZmE2EConfig) -> ZoneMinder:
    return ZoneMinder(
        cfg.url,
        cfg.username,
        cfg.password,
        cfg.path,
        cfg.path_zms,
        cfg.verify_ssl,
    )


@pytest.fixture(scope="session")
def zm_api(zm_config: ZmE2EConfig) -> ZoneMinder:
    """Logged-in zm-py client used to check what the server really holds.

    It is separate from the client the integration creates, so a test sees
    the server's state, not the integration's cached objects.
    """
    client = _new_client(zm_config)
    assert client.login(), f"Cannot log in to ZoneMinder at {zm_config.url}"
    _SUMMARY["ZoneMinder"] = f"{zm_config.url} (version {client.zm_version})"
    return client


@pytest.fixture(scope="session")
def zm_monitors(zm_api: ZoneMinder) -> list[Monitor]:
    """Return the monitors on the server, as zm-py lists them."""
    monitors = zm_api.get_monitors()
    if not monitors:
        pytest.skip("ZoneMinder has no monitors")
    return monitors


def _pick(monitors: list[Monitor], selector: str) -> Monitor:
    for monitor in monitors:
        if selector in (str(monitor.id), monitor.name):
            return monitor
    pytest.fail(f"No monitor with id or name {selector!r}")


@pytest.fixture(scope="session")
def target_monitor(zm_monitors: list[Monitor]) -> Monitor:
    """Monitor the write tests change (ZM_E2E_MONITOR, else first capturing one)."""
    if selector := _get("ZM_E2E_MONITOR"):
        monitor = _pick(zm_monitors, selector)
    else:
        monitor = next((m for m in zm_monitors if m.is_available), None)
        if monitor is None:
            pytest.skip("No monitor is capturing")
    _SUMMARY["Write target"] = f"monitor {monitor.id} ({monitor.name})"
    return monitor


@pytest.fixture(scope="session")
def ptz_monitor(zm_monitors: list[Monitor]) -> Monitor:
    """Monitor the PTZ tests move (ZM_E2E_PTZ_MONITOR, else a working PTZ camera).

    Reolink is avoided by default: its control module needs JSON.pm, which
    stock ZoneMinder packages lack.
    """
    if selector := _get("ZM_E2E_PTZ_MONITOR"):
        monitor = _pick(zm_monitors, selector)
    else:
        candidates = [
            m
            for m in zm_monitors
            if m.controllable and m.is_available and "reolink" not in m.name.lower()
        ]
        candidates.sort(key=lambda m: "hikvision" not in m.name.lower())
        if not candidates:
            pytest.skip("No controllable monitor")
        monitor = candidates[0]
    if not monitor.controllable:
        pytest.skip(f"Monitor {monitor.name} is not controllable")
    _SUMMARY["PTZ target"] = f"monitor {monitor.id} ({monitor.name})"
    return monitor


# ---------------------------------------------------------------------------
# Per-test helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def run_api(hass: HomeAssistant) -> Callable[..., Awaitable[Any]]:
    """Run a blocking zm-py call in the executor, off the event loop."""

    async def _run(func: Callable[..., _T], *args: Any) -> _T:
        return await hass.async_add_executor_job(func, *args)

    return _run


@pytest.fixture
def fresh_monitor(
    zm_config: ZmE2EConfig, run_api: Callable[..., Awaitable[Any]]
) -> Callable[[int], Awaitable[Monitor]]:
    """Fetch one monitor's current state straight from the server."""

    async def _fetch(monitor_id: int) -> Monitor:
        def _get_monitor() -> Monitor:
            client = _new_client(zm_config)
            client.login()
            return next(m for m in client.get_monitors() if m.id == monitor_id)

        monitor: Monitor = await run_api(_get_monitor)
        return monitor

    return _fetch


def live_entry(cfg: ZmE2EConfig, **options: Any) -> MockConfigEntry:
    """Config entry for the live server, with the user step's default options."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=cfg.host,
        data=cfg.entry_data,
        options={
            CONF_INCLUDE_ARCHIVED: False,
            CONF_MONITORED_CONDITIONS: ["all"],
            "command_on": DEFAULT_COMMAND_ON,
            "command_off": DEFAULT_COMMAND_OFF,
            **options,
        },
        unique_id=cfg.host,
        source=SOURCE_USER,
    )


@pytest.fixture
async def setup_live(
    hass: HomeAssistant, zm_config: ZmE2EConfig
) -> AsyncGenerator[MockConfigEntry]:
    """Set the integration up against the live server and unload it afterwards."""
    entry = live_entry(zm_config)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    yield entry
    if entry.state is ConfigEntryState.LOADED:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


def coordinator_of(hass: HomeAssistant, entry: MockConfigEntry) -> ZmDataUpdateCoordinator:
    """Return the coordinator behind a loaded entry."""
    entry_data: ZmEntryData = hass.data[DOMAIN][entry.entry_id]
    return entry_data.coordinator


def entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Look an entity up by unique ID, failing if the integration did not create it."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert found is not None, f"No {platform} entity with unique_id {unique_id!r}"
    return found


# ---------------------------------------------------------------------------
# Summary: which zm-py and which server the run used
# ---------------------------------------------------------------------------

_SUMMARY: dict[str, str] = {}


def _relative(path: Path) -> str:
    """Show a path relative to the project root (e.g. ../zm-py)."""
    return os.path.relpath(path.resolve(), _PROJECT_ROOT)


def _zm_py_source() -> str:
    """Describe the installed zm-py: version, and checkout + commit if editable."""
    dist = metadata.distribution("zm-py")
    desc = f"zm-py {dist.version}"
    direct_url = dist.read_text("direct_url.json")
    if direct_url:
        info = json.loads(direct_url)
        if info.get("dir_info", {}).get("editable"):
            path = Path(urlsplit(info["url"]).path)
            desc += f", editable from {_relative(path)}"
            try:
                rev = subprocess.run(  # noqa: S603
                    ["git", "-C", str(path), "describe", "--always", "--dirty"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                desc += f" @ {rev}"
            except OSError, subprocess.CalledProcessError:
                pass
        elif "vcs_info" in info:
            desc += f", from {info['url']}@{info['vcs_info'].get('commit_id', '')[:10]}"
        else:
            desc += f", from {info['url']}"
    return f"{desc} ({_relative(Path(zoneminder.__file__).parent)})"


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """Report the zm-py build and server the live tests ran against."""
    if ZM_CONFIG is None:
        return
    tw = terminalreporter
    tw.write_sep("=", "ZoneMinder E2E")
    tw.write_line(f"  zm-py: {_zm_py_source()}")
    for label, value in _SUMMARY.items():
        tw.write_line(f"  {label}: {value}")
    tiers = ["read"]
    if WRITE_ENABLED:
        tiers.append("write")
    if RUN_STATE_ENABLED:
        tiers.append("run-state")
    tw.write_line(f"  Tiers: {', '.join(tiers)}")
