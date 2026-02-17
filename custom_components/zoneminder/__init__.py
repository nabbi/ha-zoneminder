"""Support for ZoneMinder."""

import logging

import voluptuous as vol
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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from requests.exceptions import RequestException

from zoneminder.exceptions import LoginError, ZoneminderError
from zoneminder.zm import ZoneMinder

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
        return True

    for conf in config[DOMAIN]:
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
    protocol = "https" if conf.get(CONF_SSL, DEFAULT_SSL) else "http"
    server_origin = f"{protocol}://{host_name}"

    zm_client = ZoneMinder(
        server_origin,
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        conf.get(CONF_PATH, DEFAULT_PATH),
        conf.get(CONF_PATH_ZMS, DEFAULT_PATH_ZMS),
        conf.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )

    try:
        result = await hass.async_add_executor_job(zm_client.login)
    except (RequestException, LoginError, ZoneminderError) as ex:
        raise ConfigEntryNotReady(f"Cannot connect to ZoneMinder at {host_name}: {ex}") from ex

    if not result:
        raise ConfigEntryNotReady(f"Login failed for ZoneMinder at {host_name}")

    try:
        monitors = await hass.async_add_executor_job(zm_client.get_monitors)
    except (ZoneminderError, RequestException, KeyError) as ex:
        _LOGGER.error("Error fetching monitors from %s: %s", host_name, ex)
        monitors = []

    coordinator = ZmDataUpdateCoordinator(hass, zm_client, monitors, host_name, config_entry=entry)
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

    if entry.source == SOURCE_IMPORT:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_import_{host_name}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="yaml_import",
            translation_placeholders={"host": host_name},
        )

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ZoneMinder config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data: ZmEntryData = hass.data[DOMAIN].pop(entry.entry_id)

        host_map: dict[str, str] = hass.data.get(f"{DOMAIN}_host_map", {})
        host_map.pop(entry_data.host_name, None)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            hass.data.pop(f"{DOMAIN}_host_map", None)

    return unload_ok
