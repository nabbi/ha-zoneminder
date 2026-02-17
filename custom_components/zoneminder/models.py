"""Runtime data models for ZoneMinder integration."""

from __future__ import annotations

from dataclasses import dataclass

from zoneminder.monitor import Monitor
from zoneminder.zm import ZoneMinder

from .coordinator import ZmDataUpdateCoordinator


@dataclass
class ZmEntryData:
    """Runtime data stored in hass.data for a single config entry."""

    client: ZoneMinder
    coordinator: ZmDataUpdateCoordinator
    monitors: list[Monitor]
    host_name: str
