"""Build the aiozoneminder client for a config entry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiozoneminder import ZoneMinderClient, ZoneMinderLegacyClient, ZoneMinderV3Client
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
    API_V2,
    API_V3,
    CONF_API_BACKEND,
    CONF_API_V3_URL,
    CONF_PATH_ZMS,
    CONF_STREAM_MAXFPS,
    CONF_STREAM_SCALE,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
)


def _origin(data: Mapping[str, Any]) -> str:
    protocol = "https" if data.get(CONF_SSL, DEFAULT_SSL) else "http"
    return f"{protocol}://{data[CONF_HOST]}"


def web_url(data: Mapping[str, Any]) -> str:
    """Return ZoneMinder's web path, where API v2 lives (http://host/zm)."""
    path = data.get(CONF_PATH, DEFAULT_PATH).strip("/")
    return f"{_origin(data)}/{path}" if path else _origin(data)


def v3_urls(data: Mapping[str, Any], *, root: bool = True) -> list[str]:
    """Return where to look for zm-api: the URL given, else the web path, then the server root.

    zm-api serves /api/v3 on its own port (8080) or behind the web server's
    proxy, under the web path (/zm/api/v3) or at the root (/api/v3). ``root``
    False leaves the server root out.
    """
    if url := (data.get(CONF_API_V3_URL) or "").strip().rstrip("/"):
        return [url]
    return list(dict.fromkeys([web_url(data), *([_origin(data)] if root else [])]))


def create_zm_client(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    options: Mapping[str, Any] | None = None,
    *,
    backend: str | None = None,
    v3_url: str | None = None,
) -> ZoneMinderClient:
    """Return the client for the entry's API and connection settings.

    ``backend`` defaults to the API found at setup; entries made before the
    API choice existed are API v2. A v3 client goes to ``v3_url``, else the
    stored zm-api address, else the web path.
    """
    options = options or {}
    backend = backend or data.get(CONF_API_BACKEND) or API_V2
    session = async_get_clientsession(hass)
    username = data.get(CONF_USERNAME) or ""
    password = data.get(CONF_PASSWORD) or ""
    verify_ssl = data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    if backend == API_V3:
        return ZoneMinderV3Client(
            v3_url or v3_urls(data)[0],
            username,
            password,
            session,
            verify_ssl=verify_ssl,
        )
    stream_scale = options.get(CONF_STREAM_SCALE)
    stream_maxfps = options.get(CONF_STREAM_MAXFPS)
    return ZoneMinderLegacyClient(
        web_url(data),
        username,
        password,
        session,
        verify_ssl=verify_ssl,
        zms_path=data.get(CONF_PATH_ZMS, DEFAULT_PATH_ZMS),
        stream_scale=int(stream_scale) if stream_scale is not None else None,
        # aiozoneminder defaults to 30 fps; zm-py sent no maxfps unless set.
        stream_maxfps=float(stream_maxfps) if stream_maxfps is not None else None,
    )
