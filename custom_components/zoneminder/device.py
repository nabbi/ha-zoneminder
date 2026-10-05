"""Device registry info for ZoneMinder servers and monitors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from zoneminder.monitor import Monitor

from .const import DOMAIN

# HA 2026.8 added DeviceInfo's via_device_id (parent registry id); 2026.9 deprecated
# via_device (parent identifier), which is removed in 2027.8. Older releases only
# know via_device.
HAS_VIA_DEVICE_ID = "via_device_id" in (DeviceInfo.__required_keys__ | DeviceInfo.__optional_keys__)


def server_device_info(host_name: str, zm_version: str | None) -> DeviceInfo:
    """Return the device info for a ZoneMinder server."""
    return DeviceInfo(
        identifiers={(DOMAIN, host_name)},
        name=host_name,
        manufacturer="ZoneMinder",
        sw_version=zm_version,
    )


def monitor_device_info(host_name: str, monitor: Monitor, server_device_id: str) -> DeviceInfo:
    """Return the device info for a monitor, linked to its server's device."""
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{host_name}_{monitor.id}")},
        name=monitor.name,
        manufacturer="ZoneMinder",
    )
    if HAS_VIA_DEVICE_ID:
        info["via_device_id"] = server_device_id
    else:
        info["via_device"] = (DOMAIN, host_name)  # type: ignore[typeddict-unknown-key]
    return info
