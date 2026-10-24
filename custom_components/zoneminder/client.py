"""Build the aiozoneminder client for a config entry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiozoneminder import ZoneMinderLegacyClient
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_PATH_ZMS,
    CONF_STREAM_MAXFPS,
    CONF_STREAM_SCALE,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
)


def create_zm_client(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    options: Mapping[str, Any] | None = None,
) -> ZoneMinderLegacyClient:
    """Return an API v2 client for the entry's connection settings and stream options."""
    options = options or {}
    protocol = "https" if data.get(CONF_SSL, DEFAULT_SSL) else "http"
    path = data.get(CONF_PATH, DEFAULT_PATH)
    stream_scale = options.get(CONF_STREAM_SCALE)
    stream_maxfps = options.get(CONF_STREAM_MAXFPS)
    return ZoneMinderLegacyClient(
        f"{protocol}://{data[CONF_HOST]}/{path.strip('/')}",
        data.get(CONF_USERNAME) or "",
        data.get(CONF_PASSWORD) or "",
        async_get_clientsession(hass),
        verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        zms_path=data.get(CONF_PATH_ZMS, DEFAULT_PATH_ZMS),
        stream_scale=int(stream_scale) if stream_scale is not None else None,
        # aiozoneminder defaults to 30 fps; zm-py sent no maxfps unless set.
        stream_maxfps=float(stream_maxfps) if stream_maxfps is not None else None,
    )
