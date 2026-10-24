"""Tests for building the aiozoneminder client from a config entry."""

from __future__ import annotations

from aiozoneminder import ZoneMinderLegacyClient, ZoneMinderV3Client
from homeassistant.const import CONF_PATH, CONF_SSL
from homeassistant.core import HomeAssistant

from custom_components.zoneminder.client import create_zm_client, v3_urls, web_url
from custom_components.zoneminder.const import (
    API_V2,
    API_V3,
    CONF_API_BACKEND,
    CONF_API_V3_URL,
)

from .conftest import MOCK_ENTRY_DATA


async def test_entry_without_api_is_v2(hass: HomeAssistant) -> None:
    """Entries made before the API choice existed stay on API v2, unmigrated."""
    client = create_zm_client(hass, MOCK_ENTRY_DATA)
    assert isinstance(client, ZoneMinderLegacyClient)
    assert client.host == "http://zm.example.com/zm"
    await client.close()


async def test_entry_on_v3_uses_stored_url(hass: HomeAssistant) -> None:
    """The API found at setup and zm-api's address are what later starts use."""
    data = {
        **MOCK_ENTRY_DATA,
        CONF_API_BACKEND: API_V3,
        CONF_API_V3_URL: "http://zm.example.com:8080",
    }
    client = create_zm_client(hass, data)
    assert isinstance(client, ZoneMinderV3Client)
    assert client.host == "http://zm.example.com:8080"
    await client.close()


async def test_backend_argument_wins(hass: HomeAssistant) -> None:
    """The config flow asks for one API at one address, whatever is stored."""
    data = {**MOCK_ENTRY_DATA, CONF_API_BACKEND: API_V3}
    client = create_zm_client(hass, data, backend=API_V2)
    assert isinstance(client, ZoneMinderLegacyClient)
    await client.close()
    client = create_zm_client(hass, MOCK_ENTRY_DATA, backend=API_V3, v3_url="http://x:1")
    assert isinstance(client, ZoneMinderV3Client)
    assert client.host == "http://x:1"
    await client.close()


def test_urls() -> None:
    """Web path and zm-api candidates for the usual path forms."""
    assert web_url(MOCK_ENTRY_DATA) == "http://zm.example.com/zm"
    assert v3_urls(MOCK_ENTRY_DATA) == ["http://zm.example.com/zm", "http://zm.example.com"]
    root = {**MOCK_ENTRY_DATA, CONF_PATH: "/", CONF_SSL: True}
    assert web_url(root) == "https://zm.example.com"
    assert v3_urls(root) == ["https://zm.example.com"]
    given = {**MOCK_ENTRY_DATA, CONF_API_V3_URL: " http://zm.example.com:8080/ "}
    assert v3_urls(given) == ["http://zm.example.com:8080"]
    assert v3_urls({**MOCK_ENTRY_DATA, CONF_API_V3_URL: ""}) == v3_urls(MOCK_ENTRY_DATA)
