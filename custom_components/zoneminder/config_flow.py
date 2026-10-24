"""Config flow for ZoneMinder integration."""

from __future__ import annotations

import logging
from typing import Any

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9 validates with voluptuous
    import voluptuous as vol  # type: ignore[no-redef]
from aiozoneminder import ZMAuthenticationError, ZMError
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import create_zm_client, v3_urls
from .const import (
    API_AUTO_ORDER,
    API_V2,
    API_V3,
    API_VERSIONS,
    CONF_API_BACKEND,
    CONF_API_V3_URL,
    CONF_API_VERSION,
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    CONF_STREAM_MAXFPS,
    CONF_STREAM_SCALE,
    DEFAULT_API_VERSION,
    DEFAULT_COMMAND_OFF,
    DEFAULT_COMMAND_ON,
    DEFAULT_INCLUDE_ARCHIVED,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .monitor_state import is_zm_137_or_later

_LOGGER = logging.getLogger(__name__)

SENSOR_KEYS = ["all", "hour", "day", "week", "month"]

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Optional(CONF_USERNAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): BooleanSelector(),
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): BooleanSelector(),
        vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): SelectSelector(
            SelectSelectorConfig(
                options=API_VERSIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="api_version",
            )
        ),
        vol.Optional(CONF_API_V3_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
    }
)

# When no API connects, report the most telling failure.
_ERROR_RANK = ["unknown", "cannot_connect"]

CONF_COMMAND_ON = "command_on"
CONF_COMMAND_OFF = "command_off"


class ZoneMinderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZoneMinder."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: Any,
    ) -> ZoneMinderOptionsFlow:
        """Get the options flow for this handler."""
        return ZoneMinderOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            error, data = await self._async_validate_connection(user_input)
            if error is None:
                return self.async_create_entry(
                    title=host,
                    data=data,
                    options={
                        CONF_INCLUDE_ARCHIVED: DEFAULT_INCLUDE_ARCHIVED,
                        CONF_MONITORED_CONDITIONS: DEFAULT_MONITORED_CONDITIONS,
                        CONF_COMMAND_ON: DEFAULT_COMMAND_ON,
                        CONF_COMMAND_OFF: DEFAULT_COMMAND_OFF,
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(
        self,
        import_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        host = import_data[CONF_HOST]
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        # The YAML configuration was zm-py's, which only spoke API v2.
        error, data = await self._async_validate_connection(
            {**import_data, CONF_API_VERSION: import_data.get(CONF_API_VERSION, API_V2)}
        )
        if error is not None:
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=host,
            data=data,
            options={
                CONF_INCLUDE_ARCHIVED: DEFAULT_INCLUDE_ARCHIVED,
                CONF_MONITORED_CONDITIONS: DEFAULT_MONITORED_CONDITIONS,
                CONF_COMMAND_ON: DEFAULT_COMMAND_ON,
                CONF_COMMAND_OFF: DEFAULT_COMMAND_OFF,
            },
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of connection credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, data = await self._async_validate_connection(user_input)
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data=data,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA,
                user_input or self._get_reconfigure_entry().data,
            ),
            errors=errors,
        )

    async def _async_validate_connection(
        self,
        data: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        """Find the API to use and check the login.

        Returns an error key, or None and the entry data with the API found
        (``api_backend``) and, for v3, zm-api's address.
        """
        choice = data.get(CONF_API_VERSION) or DEFAULT_API_VERSION
        backends = [choice] if choice in (API_V2, API_V3) else API_AUTO_ORDER
        errors: list[str] = []
        for backend in backends:
            # Auto looks for zm-api only where the user pointed: a wrong path
            # should fail, not land on v3 at the server root.
            urls = v3_urls(data, root=choice == API_V3) if backend == API_V3 else [None]
            for url in urls:
                error = await self._async_try_backend(data, backend, url)
                if error is None:
                    found = {**data, CONF_API_VERSION: choice, CONF_API_BACKEND: backend}
                    if backend == API_V3 and url is not None:
                        found[CONF_API_V3_URL] = url
                    return None, found
                # Both APIs check ZoneMinder's own users, so a refused login ends
                # the search: trying further would only add failed logins, which
                # fail2ban or a login throttle count.
                if error == "invalid_auth":
                    return error, data
                errors.append(error)
        return min(errors, key=_ERROR_RANK.index), data

    async def _async_try_backend(
        self,
        data: dict[str, Any],
        backend: str,
        v3_url: str | None,
    ) -> str | None:
        """Log in with one API at one address. Returns an error key or None."""
        zm_client = create_zm_client(self.hass, data, backend=backend, v3_url=v3_url)
        where = f"API {backend} at {zm_client.host}"
        try:
            await zm_client.authenticate()
            # The version is what setup reads first, so check it answers too.
            await zm_client.get_version()
        except ZMAuthenticationError as ex:
            _LOGGER.warning("ZoneMinder login error (%s): %s", where, ex)
            return "invalid_auth"
        except ZMError as ex:
            _LOGGER.warning("ZoneMinder connection error (%s): %s", where, ex)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error connecting to ZoneMinder (%s)", where)
            return "unknown"
        finally:
            await zm_client.close()
        _LOGGER.debug("ZoneMinder %s answers", where)
        return None


class ZoneMinderOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle ZoneMinder options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.options

        schema_dict: dict[vol.Optional, Any] = {
            vol.Optional(
                CONF_INCLUDE_ARCHIVED,
                default=options.get(CONF_INCLUDE_ARCHIVED, DEFAULT_INCLUDE_ARCHIVED),
            ): BooleanSelector(),
            vol.Optional(
                CONF_MONITORED_CONDITIONS,
                default=options.get(CONF_MONITORED_CONDITIONS, DEFAULT_MONITORED_CONDITIONS),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SENSOR_KEYS,
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_STREAM_SCALE,
                description={
                    "suggested_value": options.get(CONF_STREAM_SCALE),
                },
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_STREAM_MAXFPS,
                description={
                    "suggested_value": options.get(CONF_STREAM_MAXFPS),
                },
            ): NumberSelector(
                NumberSelectorConfig(min=0.5, max=30.0, step=0.5, mode=NumberSelectorMode.BOX)
            ),
        }

        # command_on/command_off only apply to the legacy switch (pre-1.37 ZM).
        zm_version = self._get_zm_version()
        if not is_zm_137_or_later(zm_version):
            schema_dict[
                vol.Optional(
                    CONF_COMMAND_ON,
                    default=options.get(CONF_COMMAND_ON, DEFAULT_COMMAND_ON),
                )
            ] = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
            schema_dict[
                vol.Optional(
                    CONF_COMMAND_OFF,
                    default=options.get(CONF_COMMAND_OFF, DEFAULT_COMMAND_OFF),
                )
            ] = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )

    def _get_zm_version(self) -> str | None:
        """Get the ZM version from the running integration, if available."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if entry_data is not None:
            version: str | None = entry_data.coordinator.zm_version
            return version
        return None
