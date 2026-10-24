"""Tests for ZoneMinder config flow."""

from __future__ import annotations

from unittest.mock import patch

from aiozoneminder import ZMAuthenticationError, ZMConnectionError
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

from custom_components.zoneminder.const import (
    API_AUTO,
    API_V2,
    API_V3,
    CONF_API_BACKEND,
    CONF_API_V3_URL,
    CONF_API_VERSION,
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
        "custom_components.zoneminder.config_flow.create_zm_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"] == {**USER_INPUT, CONF_API_VERSION: API_AUTO, CONF_API_BACKEND: API_V2}
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
    client.authenticate.side_effect = ZMConnectionError("Connection refused")
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
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
        "custom_components.zoneminder.config_flow.create_zm_client",
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
    client.authenticate.side_effect = ZMAuthenticationError("Invalid credentials")
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
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
    client.authenticate.side_effect = RuntimeError("Something unexpected")
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
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
        "custom_components.zoneminder.config_flow.create_zm_client",
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
        "custom_components.zoneminder.config_flow.create_zm_client",
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
    assert result["data"] == {**import_data, CONF_API_VERSION: API_V2, CONF_API_BACKEND: API_V2}


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
    client.authenticate.side_effect = ZMConnectionError("Connection refused")
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
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


# --- Reconfigure flow ---


async def test_reconfigure_flow_success(hass: HomeAssistant, mock_config_entry) -> None:
    """Test reconfigure flow updates credentials and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {
        **USER_INPUT,
        CONF_USERNAME: "new_admin",
        CONF_PASSWORD: "new_secret",
    }

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new_admin"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_secret"


async def test_reconfigure_flow_invalid_auth(hass: HomeAssistant, mock_config_entry) -> None:
    """Test reconfigure flow shows error on invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    client = create_mock_zm_client()
    client.authenticate.side_effect = ZMAuthenticationError("Invalid credentials")
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_cannot_connect(hass: HomeAssistant, mock_config_entry) -> None:
    """Test reconfigure flow shows error on connection failure."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    client = create_mock_zm_client()
    client.authenticate.side_effect = ZMConnectionError("Connection refused")
    with patch(
        "custom_components.zoneminder.config_flow.create_zm_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


# --- Options flow ---


async def test_options_flow_defaults(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow shows current defaults."""
    mock_config_entry.add_to_hass(hass)

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.create_zm_client",
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
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.zoneminder.create_zm_client",
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
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.zoneminder.create_zm_client",
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


async def test_options_flow_stream_scale_maxfps(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow accepts stream_scale and stream_maxfps."""
    mock_config_entry.add_to_hass(hass)

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_ARCHIVED: False,
                CONF_MONITORED_CONDITIONS: ["all"],
                CONF_STREAM_SCALE: 50,
                CONF_STREAM_MAXFPS: 5.0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STREAM_SCALE] == 50
    assert result["data"][CONF_STREAM_MAXFPS] == 5.0


async def test_options_flow_stream_params_unset(hass: HomeAssistant, mock_config_entry) -> None:
    """Test options flow works when stream params are not provided (server default)."""
    mock_config_entry.add_to_hass(hass)

    client = create_mock_zm_client()
    with patch(
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "custom_components.zoneminder.create_zm_client",
        return_value=client,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_ARCHIVED: False,
                CONF_MONITORED_CONDITIONS: ["all"],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_STREAM_SCALE not in result["data"]
    assert CONF_STREAM_MAXFPS not in result["data"]


# --- API choice: auto, v2, v3 ---


def _factory(answers: dict[tuple[str, str | None], BaseException | None]):
    """Return a create_zm_client stand-in and the (backend, v3_url) calls it saw.

    ``answers`` maps (backend, v3_url) to the error authenticate() raises, or
    None when that API answers; anything not listed can't be reached.
    """
    calls: list[tuple[str, str | None]] = []

    def create(hass, data, options=None, *, backend=None, v3_url=None):
        calls.append((backend, v3_url))
        client = create_mock_zm_client()
        error = answers.get((backend, v3_url), ZMConnectionError("unreachable"))
        if error is not None:
            client.authenticate.side_effect = error
        return client

    return create, calls


async def _user_flow(hass: HomeAssistant, user_input: dict, answers: dict):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    create, calls = _factory(answers)
    with patch("custom_components.zoneminder.config_flow.create_zm_client", side_effect=create):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
        await hass.async_block_till_done()
    return result, calls


WEB = "http://zm.example.com/zm"
ROOT = "http://zm.example.com"


async def test_auto_prefers_v2(hass: HomeAssistant) -> None:
    """Auto keeps API v2 when it answers and doesn't look for zm-api."""
    result, calls = await _user_flow(
        hass,
        {**USER_INPUT, CONF_API_VERSION: API_AUTO},
        {(API_V2, None): None, (API_V3, WEB): None},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_BACKEND] == API_V2
    assert CONF_API_V3_URL not in result["data"]
    assert calls == [(API_V2, None)]


async def test_auto_falls_back_to_v3_under_web_path(hass: HomeAssistant) -> None:
    """With API v2 off, auto finds zm-api under the web path and stores where."""
    result, calls = await _user_flow(
        hass, {**USER_INPUT, CONF_API_VERSION: API_AUTO}, {(API_V3, WEB): None}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_VERSION] == API_AUTO
    assert result["data"][CONF_API_BACKEND] == API_V3
    assert result["data"][CONF_API_V3_URL] == WEB
    assert calls == [(API_V2, None), (API_V3, WEB)]


async def test_auto_skips_server_root(hass: HomeAssistant) -> None:
    """Auto doesn't look at the server root: a wrong path fails instead of landing on v3."""
    result, calls = await _user_flow(
        hass, {**USER_INPUT, CONF_API_VERSION: API_AUTO}, {(API_V3, ROOT): None}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert calls == [(API_V2, None), (API_V3, WEB)]


async def test_v3_finds_server_root(hass: HomeAssistant) -> None:
    """API v3 picked: zm-api proxied at /api/v3 rather than /zm/api/v3 is found."""
    result, calls = await _user_flow(
        hass, {**USER_INPUT, CONF_API_VERSION: API_V3}, {(API_V3, ROOT): None}
    )
    assert result["data"][CONF_API_BACKEND] == API_V3
    assert result["data"][CONF_API_V3_URL] == ROOT
    assert calls == [(API_V3, WEB), (API_V3, ROOT)]


async def test_auto_given_v3_url(hass: HomeAssistant) -> None:
    """Auto with a zm-api URL tries API v2, then that URL only."""
    result, calls = await _user_flow(
        hass,
        {**USER_INPUT, CONF_API_VERSION: API_AUTO, CONF_API_V3_URL: "http://zm.example.com:8080"},
        {(API_V3, "http://zm.example.com:8080"): None},
    )
    assert result["data"][CONF_API_BACKEND] == API_V3
    assert calls == [(API_V2, None), (API_V3, "http://zm.example.com:8080")]


async def test_auto_wrong_password_stops(hass: HomeAssistant) -> None:
    """A refused login on API v2 isn't retried on v3: both check the same users."""
    result, calls = await _user_flow(
        hass,
        {**USER_INPUT, CONF_API_VERSION: API_AUTO},
        {(API_V2, None): ZMAuthenticationError("no"), (API_V3, WEB): None},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert calls == [(API_V2, None)]


async def test_auto_nothing_answers(hass: HomeAssistant) -> None:
    """No API anywhere: cannot_connect, after every address was tried."""
    result, calls = await _user_flow(hass, {**USER_INPUT, CONF_API_VERSION: API_AUTO}, {})
    assert result["errors"] == {"base": "cannot_connect"}
    assert calls == [(API_V2, None), (API_V3, WEB)]


async def test_auto_unexpected_error_reported(hass: HomeAssistant) -> None:
    """An unexpected error on one API is reported over another's cannot_connect."""
    result, _ = await _user_flow(
        hass, {**USER_INPUT, CONF_API_VERSION: API_AUTO}, {(API_V2, None): RuntimeError("boom")}
    )
    assert result["errors"] == {"base": "unknown"}


async def test_v2_only_never_tries_v3(hass: HomeAssistant) -> None:
    """API v2 picked: a v2 failure is the answer, zm-api isn't asked."""
    result, calls = await _user_flow(
        hass, {**USER_INPUT, CONF_API_VERSION: API_V2}, {(API_V3, WEB): None}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert calls == [(API_V2, None)]


async def test_v3_given_url_only(hass: HomeAssistant) -> None:
    """API v3 at its own address: only that address is tried, trailing slash dropped."""
    result, calls = await _user_flow(
        hass,
        {**USER_INPUT, CONF_API_VERSION: API_V3, CONF_API_V3_URL: "http://zm.example.com:8080/"},
        {(API_V3, "http://zm.example.com:8080"): None, (API_V2, None): None},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_BACKEND] == API_V3
    assert result["data"][CONF_API_V3_URL] == "http://zm.example.com:8080"
    assert calls == [(API_V3, "http://zm.example.com:8080")]


async def test_v3_wrong_password(hass: HomeAssistant) -> None:
    """API v3 picked and the login refused: invalid_auth, no further address."""
    result, calls = await _user_flow(
        hass,
        {**USER_INPUT, CONF_API_VERSION: API_V3},
        {(API_V3, WEB): ZMAuthenticationError("no"), (API_V3, ROOT): None},
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert calls == [(API_V3, WEB)]


async def test_reconfigure_switches_api(hass: HomeAssistant, mock_config_entry) -> None:
    """Reconfigure runs the detection again and stores the API it found."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    create, _ = _factory({(API_V3, WEB): None})
    with (
        patch("custom_components.zoneminder.config_flow.create_zm_client", side_effect=create),
        patch("custom_components.zoneminder.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, CONF_API_VERSION: API_V3}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_BACKEND] == API_V3
    assert mock_config_entry.data[CONF_API_V3_URL] == WEB
