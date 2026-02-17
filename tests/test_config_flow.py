"""Tests for ZoneMinder config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import ConnectionError as RequestsConnectionError
from zoneminder.exceptions import LoginError

from custom_components.zoneminder.const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
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

from .conftest import MOCK_HOST, create_mock_zm_client

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_SSL: DEFAULT_SSL,
    CONF_PATH: DEFAULT_PATH,
    CONF_PATH_ZMS: DEFAULT_PATH_ZMS,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user config flow with successful connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == USER_INPUT
    assert result["options"][CONF_INCLUDE_ARCHIVED] == DEFAULT_INCLUDE_ARCHIVED
    assert result["options"][CONF_MONITORED_CONDITIONS] == DEFAULT_MONITORED_CONDITIONS
    assert result["options"]["command_on"] == DEFAULT_COMMAND_ON
    assert result["options"]["command_off"] == DEFAULT_COMMAND_OFF


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user config flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client = create_mock_zm_client()
    client.login.side_effect = RequestsConnectionError("Connection refused")
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test user config flow with login failure (returns False)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client = create_mock_zm_client(login_success=False)
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_login_error_exception(hass: HomeAssistant) -> None:
    """Test user config flow with LoginError exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client = create_mock_zm_client()
    client.login.side_effect = LoginError("Invalid credentials")
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test user config flow with unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client = create_mock_zm_client()
    client.login.side_effect = RuntimeError("Something unexpected")
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_duplicate_host(hass: HomeAssistant) -> None:
    """Test user config flow aborts on duplicate host."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_HOST,
        data=USER_INPUT,
        unique_id=MOCK_HOST,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- Import flow ---


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test import flow creates entry from YAML data."""
    import_data = {
        CONF_HOST: MOCK_HOST,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
        CONF_SSL: DEFAULT_SSL,
        CONF_PATH: DEFAULT_PATH,
        CONF_PATH_ZMS: DEFAULT_PATH_ZMS,
        CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    }

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=import_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == import_data


async def test_import_flow_already_imported(hass: HomeAssistant) -> None:
    """Test import flow aborts when host already configured."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_HOST,
        data=USER_INPUT,
        unique_id=MOCK_HOST,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_connection_error(hass: HomeAssistant) -> None:
    """Test import flow aborts on connection error."""
    client = create_mock_zm_client()
    client.login.side_effect = RequestsConnectionError("Connection refused")
    with patch(
        "custom_components.zoneminder.config_flow.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


# --- Options flow ---


async def test_options_flow_defaults(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow shows current defaults."""
    mock_config_entry.add_to_hass(hass)

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_update(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow updates values (ZM 1.38+ hides command_on/off)."""
    mock_config_entry.add_to_hass(hass)

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_ARCHIVED: True,
                CONF_MONITORED_CONDITIONS: ["all", "hour"],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INCLUDE_ARCHIVED] is True
    assert result["data"][CONF_MONITORED_CONDITIONS] == ["all", "hour"]


async def test_options_flow_shows_command_on_pre137(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow shows command_on/off fields on pre-1.37 ZM."""
    mock_config_entry.add_to_hass(hass)

    client = create_mock_zm_client(zm_version="1.36.33")
    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.zoneminder.ZoneMinder",
        return_value=client,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_ARCHIVED: True,
                CONF_MONITORED_CONDITIONS: ["all", "hour"],
                "command_on": "Record",
                "command_off": "None",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["command_on"] == "Record"
    assert result["data"]["command_off"] == "None"
