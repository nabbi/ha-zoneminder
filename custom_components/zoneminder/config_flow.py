"""Config flow for ZoneMinder integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
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
from requests.exceptions import RequestException

from zoneminder.exceptions import LoginError, ZoneminderError
from zoneminder.monitor import _is_zm_137_or_later
from zoneminder.zm import ZoneMinder

from .const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    CONF_STREAM_MAXFPS,
    CONF_STREAM_SCALE,
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
    }
)

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

            error = await self._async_validate_connection(user_input)
            if error is None:
                return self.async_create_entry(
                    title=host,
                    data=user_input,
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

        error = await self._async_validate_connection(import_data)
        if error is not None:
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=host,
            data=import_data,
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
            error = await self._async_validate_connection(user_input)
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data=user_input,
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
    ) -> str | None:
        """Validate the user input allows us to connect. Returns error key or None."""
        protocol = "https" if data.get(CONF_SSL, DEFAULT_SSL) else "http"
        server_origin = f"{protocol}://{data[CONF_HOST]}"

        zm_client = ZoneMinder(
            server_origin,
            data.get(CONF_USERNAME),
            data.get(CONF_PASSWORD),
            data.get(CONF_PATH, DEFAULT_PATH),
            data.get(CONF_PATH_ZMS, DEFAULT_PATH_ZMS),
            data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )

        try:
            result = await self.hass.async_add_executor_job(zm_client.login)
        except LoginError as ex:
            _LOGGER.error("ZoneMinder login error: %s", ex)
            return "invalid_auth"
        except (RequestException, ZoneminderError) as ex:
            _LOGGER.error("ZoneMinder connection error: %s", ex)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error connecting to ZoneMinder")
            return "unknown"

        if not result:
            return "invalid_auth"
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
        if not _is_zm_137_or_later(zm_version):
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
            version: str | None = entry_data.coordinator.zm_client.zm_version
            return version
        return None
