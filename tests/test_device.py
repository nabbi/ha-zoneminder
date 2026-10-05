"""Tests for ZoneMinder device registry entries."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zoneminder.const import DOMAIN
from custom_components.zoneminder.device import monitor_device_info

from .conftest import MOCK_HOST, create_mock_monitor, setup_entry


def _devices_by_identifier(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    return {
        identifier: device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        for identifier in device.identifiers
    }


async def test_monitor_devices_linked_to_server_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Each monitor device hangs off the server device."""
    monitors = [
        create_mock_monitor(monitor_id=1, name="Front Door"),
        create_mock_monitor(monitor_id=2, name="Back Yard"),
    ]
    await setup_entry(hass, mock_config_entry, monitors=monitors)

    devices = _devices_by_identifier(hass, mock_config_entry)
    server = devices[(DOMAIN, MOCK_HOST)]
    assert server.manufacturer == "ZoneMinder"
    assert server.sw_version == "1.38.0"
    for monitor_id in (1, 2):
        assert devices[(DOMAIN, f"{MOCK_HOST}_{monitor_id}")].via_device_id == server.id


async def test_no_deprecated_via_device_usage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Setup does not use the deprecated via_device key (removed in HA 2027.8)."""
    await setup_entry(hass, mock_config_entry, monitors=[create_mock_monitor(name="Front Door")])

    assert "via_device" not in caplog.text


def test_monitor_device_info_uses_via_device_id() -> None:
    """On HA versions with via_device_id, the parent is referenced by device id."""
    monitor = create_mock_monitor(monitor_id=3, name="Garage")

    with patch("custom_components.zoneminder.device.HAS_VIA_DEVICE_ID", True):
        info = monitor_device_info(MOCK_HOST, monitor, "server-device-id")

    assert info["identifiers"] == {(DOMAIN, f"{MOCK_HOST}_3")}
    assert info["name"] == "Garage"
    assert info["via_device_id"] == "server-device-id"
    assert "via_device" not in info


def test_monitor_device_info_falls_back_to_via_device() -> None:
    """On HA versions without via_device_id, the parent is referenced by identifier."""
    monitor = create_mock_monitor(monitor_id=3, name="Garage")

    with patch("custom_components.zoneminder.device.HAS_VIA_DEVICE_ID", False):
        info = monitor_device_info(MOCK_HOST, monitor, "server-device-id")

    assert info["via_device"] == (DOMAIN, MOCK_HOST)  # type: ignore[typeddict-item]
    assert "via_device_id" not in info
