"""Runtime data models for ZoneMinder integration."""

from __future__ import annotations

from dataclasses import dataclass

from aiozoneminder import Monitor, ZoneMinderLegacyClient

from .coordinator import ZmDataUpdateCoordinator


@dataclass
class ZmEntryData:
    """Runtime data stored in hass.data for a single config entry."""

    client: ZoneMinderLegacyClient
    coordinator: ZmDataUpdateCoordinator
    monitors: list[Monitor]
    host_name: str
