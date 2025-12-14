"""Common fixtures for Sugar Valley NeoPool tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


def create_mqtt_message(topic: str, payload: dict[str, Any] | str) -> MagicMock:
    """Create a mock MQTT message."""
    message = MagicMock()
    message.topic = topic
    message.payload = json.dumps(payload) if isinstance(payload, dict) else payload
    return message


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
        },
        "Redox": {
            "Data": 750,
            "Setpoint": 700,
        },
        "Hydrolysis": {
            "Data": 50,
            "Percent": {"Data": 50, "Setpoint": 60},
            "State": "POL1",
        },
        "Filtration": {
            "State": 1,
            "Speed": 2,
            "Mode": 1,
        },
        "Modules": {
            "pH": 1,
            "Redox": 1,
            "Hydrolysis": 1,
        },
    }
}
