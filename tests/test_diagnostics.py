"""Tests for Sugar Valley NeoPool diagnostics module."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import NeoPoolData
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    DOMAIN,
    VERSION,
)
from custom_components.sugar_valley_neopool.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_runtime_data() -> NeoPoolData:
    """Create mock runtime data."""
    return NeoPoolData(
        device_name="Test Pool",
        mqtt_topic="SmartPool",
        nodeid="ABC123",
        sensor_data={"temperature": 28.5, "ph": 7.2},
        available=True,
    )


class TestDiagnostics:
    """Tests for diagnostics functionality."""

    @pytest.mark.asyncio
    async def test_async_get_config_entry_diagnostics(
        self, hass: HomeAssistant, mock_runtime_data: NeoPoolData
    ) -> None:
        """Test diagnostics returns expected structure."""
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
        entry.runtime_data = mock_runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        # Check structure
        assert "config" in result
        assert "device" in result
        assert "sensors" in result

    @pytest.mark.asyncio
    async def test_diagnostics_config_section(
        self, hass: HomeAssistant, mock_runtime_data: NeoPoolData
    ) -> None:
        """Test diagnostics config section content."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
            },
            options={"some_option": "value"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = mock_runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        config = result["config"]
        assert config["entry_id"] == entry.entry_id
        assert config["version"] == entry.version
        assert config["domain"] == DOMAIN
        assert config["integration_version"] == VERSION
        assert config["options"] == {"some_option": "value"}

    @pytest.mark.asyncio
    async def test_diagnostics_device_section(
        self, hass: HomeAssistant, mock_runtime_data: NeoPoolData
    ) -> None:
        """Test diagnostics device section content."""
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
        entry.runtime_data = mock_runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        device = result["device"]
        assert device["name"] == "Test Pool"
        assert device["available"] is True
        # Sensitive data should be redacted
        assert device["mqtt_topic"] == "**REDACTED**"
        assert device["nodeid"] == "**REDACTED**"

    @pytest.mark.asyncio
    async def test_diagnostics_redacts_sensitive_data(
        self, hass: HomeAssistant, mock_runtime_data: NeoPoolData
    ) -> None:
        """Test diagnostics redacts sensitive data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "SENSITIVE_NODEID",
            },
            options={},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = mock_runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        config_data = result["config"]["data"]
        # NodeID and discovery_prefix should be redacted
        assert config_data.get(CONF_NODEID) == "**REDACTED**"
        assert config_data.get(CONF_DISCOVERY_PREFIX) == "**REDACTED**"
        # Device name should NOT be redacted
        assert config_data.get(CONF_DEVICE_NAME) == "Test Pool"

    @pytest.mark.asyncio
    async def test_diagnostics_includes_sensor_data(self, hass: HomeAssistant) -> None:
        """Test diagnostics includes sensor data."""
        runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
            sensor_data={
                "temperature": 28.5,
                "ph": 7.2,
                "redox": 750,
            },
            available=True,
        )

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
        entry.runtime_data = runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        sensors = result["sensors"]
        assert sensors["temperature"] == 28.5
        assert sensors["ph"] == 7.2
        assert sensors["redox"] == 750

    @pytest.mark.asyncio
    async def test_diagnostics_redacts_nodeid_in_sensors(self, hass: HomeAssistant) -> None:
        """Test diagnostics redacts NodeID in sensor data."""
        runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
            sensor_data={
                "temperature": 28.5,
                "NodeID": "SENSITIVE123",
                "nodeid": "SENSITIVE456",
            },
            available=True,
        )

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
        entry.runtime_data = runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        sensors = result["sensors"]
        assert sensors["temperature"] == 28.5
        assert sensors.get("NodeID") == "**REDACTED**"
        assert sensors.get("nodeid") == "**REDACTED**"

    @pytest.mark.asyncio
    async def test_diagnostics_empty_sensor_data(self, hass: HomeAssistant) -> None:
        """Test diagnostics with empty sensor data."""
        runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
            sensor_data={},
            available=False,
        )

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
        entry.runtime_data = runtime_data

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["sensors"] == {}
        assert result["device"]["available"] is False
