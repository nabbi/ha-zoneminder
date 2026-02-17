"""Tests for ZoneMinder binary sensor entity states (public API)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import PropertyMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from .conftest import MOCK_HOST, MOCK_HOST_2, setup_entry

# The entity_id uses the hostname with dots replaced by underscores
ENTITY_ID = f"binary_sensor.{MOCK_HOST.replace('.', '_')}"
ENTITY_ID_2 = f"binary_sensor.{MOCK_HOST_2.replace('.', '_')}"


async def test_binary_sensor_created_per_server(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test one binary sensor entity is created per ZM server."""
    await setup_entry(hass, mock_config_entry, is_available=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None


async def test_binary_sensor_name_from_hostname(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor entity name matches hostname."""
    await setup_entry(hass, mock_config_entry, is_available=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == MOCK_HOST


async def test_binary_sensor_device_class_connectivity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor has connectivity device class."""
    await setup_entry(hass, mock_config_entry, is_available=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY


async def test_binary_sensor_state_on_when_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor state is ON when server is available."""
    await setup_entry(hass, mock_config_entry, is_available=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_state_off_when_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor state is OFF when server is unavailable."""
    await setup_entry(hass, mock_config_entry, is_available=False)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_multi_server_creates_multiple_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
) -> None:
    """Test multi-server config creates multiple binary sensor entities."""
    await setup_entry(hass, mock_config_entry, is_available=True)
    await setup_entry(hass, mock_config_entry_2, is_available=True)

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.states.get(ENTITY_ID_2) is not None


async def test_binary_sensor_state_updates_on_poll(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test binary sensor state updates when polled."""
    client = await setup_entry(hass, mock_config_entry, is_available=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Change availability and trigger another update
    type(client).is_available = PropertyMock(return_value=False)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120), fire_all=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_device_info_includes_zm_version(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test server device info includes ZoneMinder version as sw_version."""
    await setup_entry(hass, mock_config_entry, is_available=True, zm_version="1.36.33")

    entity = hass.data["entity_components"]["binary_sensor"].get_entity(ENTITY_ID)
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert info["sw_version"] == "1.36.33"


async def test_device_info_zm_version_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test server device info handles None zm_version (legacy auth without version)."""
    await setup_entry(hass, mock_config_entry, is_available=True, zm_version=None)

    entity = hass.data["entity_components"]["binary_sensor"].get_entity(ENTITY_ID)
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert info["sw_version"] is None


async def test_unique_id_set(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Binary sensor should have unique_id for UI customization."""
    await setup_entry(hass, mock_config_entry, is_available=True)

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id is not None
