"""Tests for the Sugar Valley NeoPool config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
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
