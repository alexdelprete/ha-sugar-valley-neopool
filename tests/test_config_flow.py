"""Tests for the Sugar Valley NeoPool config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_ENABLE_REPAIR_NOTIFICATION,
    CONF_FAILURES_THRESHOLD,
    CONF_NODEID,
    CONF_OFFLINE_TIMEOUT,
    CONF_RECOVERY_SCRIPT,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SAMPLE_NEOPOOL_PAYLOAD, create_mqtt_message


async def test_form_user(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test the user config flow with valid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "My Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Pool"
    assert result["data"] == {
        CONF_DEVICE_NAME: "My Pool",
        CONF_DISCOVERY_PREFIX: "SmartPool",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_invalid_topic(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test the user config flow with invalid MQTT topic."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test with invalid characters in topic
    with patch(
        "homeassistant.components.mqtt.valid_subscribe_topic",
        side_effect=Exception("Invalid topic"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "invalid/topic#",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_topic"}


async def test_form_user_duplicate(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test the user config flow with duplicate entry."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "My Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Try to create duplicate entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "Another Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",  # Same topic
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_mqtt_discovery(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test MQTT discovery with valid NeoPool payload."""
    message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_confirm"

    # Confirm discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "NeoPool SmartPool",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NeoPool SmartPool"
    assert result["data"] == {
        CONF_DEVICE_NAME: "NeoPool SmartPool",
        CONF_DISCOVERY_PREFIX: "SmartPool",
    }


async def test_mqtt_discovery_invalid_topic(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test MQTT discovery with invalid topic format."""
    message = create_mqtt_message("invalid/topic/format", SAMPLE_NEOPOOL_PAYLOAD)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_discovery_not_neopool(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test MQTT discovery with non-NeoPool payload."""
    non_neopool_payload: dict[str, Any] = {
        "Sensor": {"Temperature": 25.0},
        "Wifi": {"RSSI": -50},
    }
    message = create_mqtt_message("tele/OtherDevice/SENSOR", non_neopool_payload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_neopool_device"


async def test_mqtt_discovery_invalid_json(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test MQTT discovery with invalid JSON payload."""
    message = MagicMock()
    message.topic = "tele/SmartPool/SENSOR"
    message.payload = "not valid json"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_discovery_duplicate(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test MQTT discovery with already configured device."""
    # First discovery
    message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "NeoPool SmartPool"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second discovery with same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_mqtt_confirm_default_name(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test MQTT confirmation uses default device name."""
    message = create_mqtt_message("tele/TestPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_confirm"

    # Confirm without changing name (use default)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},  # Empty to use default
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NeoPool TestPool"  # Default name
    assert result["data"][CONF_DISCOVERY_PREFIX] == "TestPool"


# Options Flow Tests


async def test_options_flow_init(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test options flow initialization."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_update(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test options flow updates options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENABLE_REPAIR_NOTIFICATION: True,
            CONF_FAILURES_THRESHOLD: 5,
            CONF_OFFLINE_TIMEOUT: 120,
            CONF_RECOVERY_SCRIPT: "",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ENABLE_REPAIR_NOTIFICATION] is True
    assert entry.options[CONF_FAILURES_THRESHOLD] == 5
    assert entry.options[CONF_OFFLINE_TIMEOUT] == 120


async def test_options_flow_preserves_existing(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test options flow shows existing values as defaults."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
        options={
            CONF_ENABLE_REPAIR_NOTIFICATION: False,
            CONF_FAILURES_THRESHOLD: 10,
            CONF_OFFLINE_TIMEOUT: 300,
            CONF_RECOVERY_SCRIPT: "script.pool_recovery",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    # Form should be shown with current options as defaults


async def test_options_flow_defaults(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test options flow uses default values when no options set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Should show form with default values
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


# Reconfigure Flow Tests


async def test_reconfigure_flow_init(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test reconfigure flow initialization."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_flow_invalid_topic(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test reconfigure flow with invalid topic."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.mqtt.valid_subscribe_topic",
        side_effect=Exception("Invalid topic"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_DEVICE_NAME: "Updated Pool",
                CONF_DISCOVERY_PREFIX: "invalid#topic",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DISCOVERY_PREFIX: "invalid_topic"}
