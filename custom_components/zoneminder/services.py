"""Support for ZoneMinder."""

import logging

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9 validates with voluptuous
    import voluptuous as vol  # type: ignore[no-redef]
from aiozoneminder import ZMError
from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_RUN_STATE = "set_run_state"
SET_RUN_STATE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ID): cv.string, vol.Required(ATTR_NAME): cv.string}
)


async def _async_set_active_state(call: ServiceCall) -> None:
    """Set the ZoneMinder run state to the given state name."""
    zm_id = call.data[ATTR_ID]
    state_name = call.data[ATTR_NAME]

    host_map: dict[str, str] = call.hass.data.get(f"{DOMAIN}_host_map", {})
    entry_id = host_map.get(zm_id)
    if entry_id is None:
        _LOGGER.error("Invalid ZoneMinder host provided: %s", zm_id)
        return

    from .models import ZmEntryData

    entry_data: ZmEntryData = call.hass.data[DOMAIN][entry_id]
    try:
        await entry_data.coordinator.async_set_run_state(state_name)
    except ZMError as err:
        _LOGGER.error(
            "Error setting ZoneMinder run state on %s to %s: %s",
            zm_id,
            state_name,
            err,
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register ZoneMinder services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_RUN_STATE):
        return
    hass.services.async_register(
        DOMAIN, SERVICE_SET_RUN_STATE, _async_set_active_state, schema=SET_RUN_STATE_SCHEMA
    )
