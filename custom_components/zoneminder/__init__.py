"""Support for ZoneMinder."""

import logging

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9 validates with voluptuous
    import voluptuous as vol  # type: ignore[no-redef]
from aiozoneminder import ZMAuthenticationError, ZMError
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .client import create_zm_client
from .const import (
    CONF_PATH_ZMS,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ZmDataUpdateCoordinator
from .device import server_device_info
from .models import ZmEntryData
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

HOST_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [HOST_CONFIG_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ZoneMinder component from YAML (import only)."""
    if DOMAIN not in config:
        # YAML configuration has been removed - clear any stale import repairs
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.source == SOURCE_IMPORT:
                ir.async_delete_issue(hass, DOMAIN, f"yaml_import_{entry.data[CONF_HOST]}")
        return True

    for conf in config[DOMAIN]:
        host_name = conf[CONF_HOST]
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_import_{host_name}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="yaml_import",
            translation_placeholders={"host": host_name},
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=conf,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZoneMinder from a config entry."""
    conf = entry.data
    host_name = conf[CONF_HOST]

    zm_client = create_zm_client(hass, conf, entry.options)

    try:
        await zm_client.authenticate()
        zm_version = await zm_client.get_version()
    except ZMAuthenticationError as ex:
        # Not a retry: each one would be another failed login. Ask for the password.
        await zm_client.close()
        raise ConfigEntryAuthFailed(f"ZoneMinder at {host_name} refused the login: {ex}") from ex
    except ZMError as ex:
        await zm_client.close()
        raise ConfigEntryNotReady(f"Cannot connect to ZoneMinder at {host_name}: {ex}") from ex

    try:
        monitors = await zm_client.get_monitors()
    except ZMError as ex:
        _LOGGER.error("Error fetching monitors from %s: %s", host_name, ex)
        monitors = []

    # Registered before the platforms, so monitor devices can reference it by id.
    server_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **server_device_info(host_name, zm_version),
    )

    coordinator = ZmDataUpdateCoordinator(
        hass,
        zm_client,
        monitors,
        host_name,
        config_entry=entry,
        server_device_id=server_device.id,
        zm_version=zm_version,
    )
    # Before the first refresh, so event sensors have counts as soon as they are added.
    coordinator.register_event_queries_from_options(entry.options)
    await coordinator.async_config_entry_first_refresh()

    entry_data = ZmEntryData(
        client=zm_client,
        coordinator=coordinator,
        monitors=monitors,
        host_name=host_name,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry_data

    host_map: dict[str, str] = hass.data.setdefault(f"{DOMAIN}_host_map", {})
    host_map[host_name] = entry.entry_id

    async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ZoneMinder config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data: ZmEntryData = hass.data[DOMAIN].pop(entry.entry_id)
        await entry_data.client.close()

        host_map: dict[str, str] = hass.data.get(f"{DOMAIN}_host_map", {})
        host_map.pop(entry_data.host_name, None)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            hass.data.pop(f"{DOMAIN}_host_map", None)

    return unload_ok
