"""Common fixtures for Sugar Valley NeoPool tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool import NeoPoolData
from custom_components.sugar_valley_neopool.const import DOMAIN


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.sugar_valley_neopool.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_mqtt_subscribe() -> Generator[AsyncMock]:
    """Mock MQTT subscribe."""
    with patch(
        "homeassistant.components.mqtt.async_subscribe",
        return_value=MagicMock(),
    ) as mock_subscribe:
        yield mock_subscribe


@pytest.fixture
def mock_mqtt_publish() -> Generator[AsyncMock]:
    """Mock MQTT publish."""
    with patch(
        "homeassistant.components.mqtt.async_publish",
        return_value=None,
    ) as mock_publish:
        yield mock_publish


def create_mqtt_message(topic: str, payload: dict[str, Any] | str) -> MagicMock:
    """Create a mock MQTT message."""
    message = MagicMock()
    message.topic = topic
    message.payload = json.dumps(payload) if isinstance(payload, dict) else payload
    return message


# Sample NeoPool MQTT payloads
SAMPLE_NEOPOOL_PAYLOAD: dict[str, Any] = {
    "NeoPool": {
        "Type": "Sugar Valley",
        "Temperature": 28.5,
        "pH": {
            "Data": 7.2,
            "State": 0,
            "Pump": 1,
            "Min": 7.0,
            "Max": 7.4,
            "FL1": 0,
            "Tank": 1,
        },
        "Redox": {
            "Data": 750,
            "Setpoint": 700,
            "Tank": 1,
        },
        "Hydrolysis": {
            "Data": 50,
            "Percent": {"Data": 50, "Setpoint": 60},
            "State": "POL1",
            "FL1": 0,
            "Cover": 0,
            "Low": 0,
            "Boost": 0,
            "Runtime": {
                "Total": "123T04:30:00",
                "Part": "10T02:15:00",
                "Changes": 456,
            },
        },
        "Filtration": {
            "State": 1,
            "Speed": 2,
            "Mode": 1,
        },
        "Light": 1,
        "Relay": {
            "State": [1, 1, 0, 0, 0, 0, 0],
            "Aux": [0, 1, 0, 1],
            "Acid": 0,
        },
        "Modules": {
            "pH": 1,
            "Redox": 1,
            "Hydrolysis": 1,
            "Chlorine": 0,
            "Conductivity": 0,
            "Ionization": 0,
        },
        "Powerunit": {
            "Version": "1.2.3",
            "NodeID": "ABC123",
            "5V": 5.1,
            "12V": 12.2,
            "24-30V": 24.5,
            "4-20mA": 10.5,
        },
        "Connection": {
            "MBRequests": 1000,
            "MBNoError": 990,
            "MBNoResponse": 10,
        },
    }
}

SAMPLE_NEOPOOL_PAYLOAD_MINIMAL: dict[str, Any] = {
    "NeoPool": {
        "Type": "Sugar Valley",
        "Temperature": 25.0,
        "Powerunit": {
            "NodeID": "DEF456",
        },
    }
}

SAMPLE_NEOPOOL_PAYLOAD_HIDDEN_NODEID: dict[str, Any] = {
    "NeoPool": {
        "Type": "Sugar Valley",
        "Temperature": 25.0,
        "Powerunit": {
            "NodeID": "hidden",
        },
    }
}


@pytest.fixture
def sample_payload() -> dict[str, Any]:
    """Return sample NeoPool payload."""
    return SAMPLE_NEOPOOL_PAYLOAD.copy()


@pytest.fixture
def sample_payload_minimal() -> dict[str, Any]:
    """Return minimal NeoPool payload."""
    return SAMPLE_NEOPOOL_PAYLOAD_MINIMAL.copy()


@pytest.fixture
def mock_neopool_data() -> NeoPoolData:
    """Create mock NeoPoolData."""
    return NeoPoolData(
        device_name="Test NeoPool",
        mqtt_topic="SmartPool",
        nodeid="ABC123",
        available=True,
        sensor_data=SAMPLE_NEOPOOL_PAYLOAD,
        device_id="test_device_id",
    )


@pytest.fixture
def mock_config_entry(mock_neopool_data: NeoPoolData) -> MagicMock:
    """Create mock config entry with runtime_data."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Test NeoPool"
    entry.version = 2
    entry.data = {
        "discovery_prefix": "SmartPool",
        "name": "Test NeoPool",
        "nodeid": "ABC123",
    }
    entry.options = {
        "enable_recovery_script": False,
        "enable_repair_notifications": True,
    }
    entry.runtime_data = mock_neopool_data
    return entry


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.states = MagicMock()
    hass.bus = MagicMock()
    return hass


@pytest.fixture
def mock_device_registry() -> Generator[MagicMock]:
    """Mock device registry."""
    with patch(
        "homeassistant.helpers.device_registry.async_get",
    ) as mock_registry:
        registry = MagicMock()
        mock_registry.return_value = registry
        yield registry


@pytest.fixture
def mock_entity_registry() -> Generator[MagicMock]:
    """Mock entity registry."""
    with patch(
        "homeassistant.helpers.entity_registry.async_get",
    ) as mock_registry:
        registry = MagicMock()
        registry.entities = MagicMock()
        registry.entities.values.return_value = []
        mock_registry.return_value = registry
        yield registry


@pytest.fixture
def mock_issue_registry() -> Generator[MagicMock]:
    """Mock issue registry."""
    with patch(
        "homeassistant.helpers.issue_registry.async_get",
    ) as mock_registry:
        registry = MagicMock()
        mock_registry.return_value = registry
        yield registry
