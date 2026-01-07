"""Extended tests for Sugar Valley NeoPool integration initialization - edge cases."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    CONFIG_ENTRY_VERSION,
    NeoPoolData,
    async_migrate_entry,
    async_register_device,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


class TestAsyncSetupEntryExtended:
    """Extended tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_registers_device(self, hass: HomeAssistant) -> None:
        """Test setup entry registers device."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "MyPool",
                CONF_NODEID: "XYZ789",
            },
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mqtt.async_wait_for_mqtt_client",
                return_value=True,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True),
            patch("custom_components.sugar_valley_neopool.async_register_device") as mock_register,
        ):
            await async_setup_entry(hass, entry)

        mock_register.assert_called_once_with(hass, entry)

    @pytest.mark.asyncio
    async def test_setup_entry_mqtt_timeout(self, hass: HomeAssistant) -> None:
        """Test setup entry raises when MQTT times out."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
            },
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mqtt.async_wait_for_mqtt_client",
                return_value=False,
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_setup_entry_with_entity_id_mapping(self, hass: HomeAssistant) -> None:
        """Test setup with entity_id_mapping applies mapping."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
                "entity_id_mapping": {"water_temp": "sensor.neopool_water_temp"},
            },
            options={},
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mqtt.async_wait_for_mqtt_client",
                return_value=True,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True),
            patch(
                "custom_components.sugar_valley_neopool._apply_entity_id_mapping"
            ) as mock_apply_mapping,
        ):
            await async_setup_entry(hass, entry)

        # Entity ID mapping should be applied
        mock_apply_mapping.assert_called_once()


class TestAsyncUnloadEntryExtended:
    """Extended tests for async_unload_entry function."""

    @pytest.mark.asyncio
    async def test_unload_clears_runtime_data(self, hass: HomeAssistant) -> None:
        """Test unload clears runtime data properly."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
            sensor_data={"temp": 28.5},
        )

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            result = await async_unload_entry(hass, entry)

        assert result is True


class TestAsyncMigrateEntryExtended:
    """Extended tests for async_migrate_entry function."""

    @pytest.mark.asyncio
    async def test_migrate_already_current_version(self, hass: HomeAssistant) -> None:
        """Test migration when already at current version."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=CONFIG_ENTRY_VERSION,
            data={CONF_DEVICE_NAME: "Pool"},
            options={"some_option": "value"},
        )
        entry.add_to_hass(hass)

        result = await async_migrate_entry(hass, entry)

        # Should return True and not modify anything
        assert result is True
        assert entry.version == CONFIG_ENTRY_VERSION

    @pytest.mark.asyncio
    async def test_migrate_preserves_data(self, hass: HomeAssistant) -> None:
        """Test migration preserves entry data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=1,
            data={
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "CustomTopic",
                CONF_NODEID: "CUSTOM123",
            },
            options={},
        )
        entry.add_to_hass(hass)

        await async_migrate_entry(hass, entry)

        # Data should be preserved
        assert entry.data[CONF_DEVICE_NAME] == "My Pool"
        assert entry.data[CONF_DISCOVERY_PREFIX] == "CustomTopic"
        assert entry.data[CONF_NODEID] == "CUSTOM123"


class TestAsyncRegisterDeviceExtended:
    """Extended tests for async_register_device."""

    @pytest.mark.asyncio
    async def test_register_device_stores_device_id(self, hass: HomeAssistant) -> None:
        """Test that device registration stores device_id in runtime_data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "MyPool",
                CONF_NODEID: "XYZ789",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="My Pool",
            mqtt_topic="MyPool",
            nodeid="XYZ789",
        )

        await async_register_device(hass, entry)

        # Device ID should be stored in runtime_data
        assert entry.runtime_data.device_id is not None


class TestNeoPoolDataExtended:
    """Extended tests for NeoPoolData dataclass."""

    def test_neopool_data_with_all_fields(self) -> None:
        """Test NeoPoolData with all fields populated."""
        data = NeoPoolData(
            device_name="Full Pool",
            mqtt_topic="FullTopic",
            nodeid="FULL123",
            sensor_data={"temp": 30.0, "ph": 7.2},
            available=True,
            device_id="device_123",
        )

        assert data.device_name == "Full Pool"
        assert data.mqtt_topic == "FullTopic"
        assert data.nodeid == "FULL123"
        assert data.sensor_data == {"temp": 30.0, "ph": 7.2}
        assert data.available is True
        assert data.device_id == "device_123"

    def test_neopool_data_mutable_sensor_data(self) -> None:
        """Test NeoPoolData sensor_data is mutable."""
        data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="Topic",
            nodeid="123",
        )

        # Should be able to modify sensor_data
        data.sensor_data["new_key"] = "new_value"
        assert data.sensor_data["new_key"] == "new_value"

    def test_neopool_data_availability_toggle(self) -> None:
        """Test NeoPoolData availability can be toggled."""
        data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="Topic",
            nodeid="123",
            available=False,
        )

        assert data.available is False

        # Should be able to update availability
        data.available = True
        assert data.available is True

    def test_neopool_data_entity_id_mapping(self) -> None:
        """Test NeoPoolData entity_id_mapping field."""
        data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="Topic",
            nodeid="123",
            entity_id_mapping={"water_temp": "neopool_water_temp"},
        )

        assert data.entity_id_mapping == {"water_temp": "neopool_water_temp"}

    def test_neopool_data_entity_id_mapping_default_empty(self) -> None:
        """Test NeoPoolData entity_id_mapping defaults to empty dict."""
        data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="Topic",
            nodeid="123",
        )

        assert data.entity_id_mapping == {}
