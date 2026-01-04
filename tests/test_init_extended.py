"""Extended tests for Sugar Valley NeoPool integration initialization - edge cases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    async_migrate_entry,
    async_migrate_yaml_entities,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_MIGRATE_YAML,
    CONF_NODEID,
    CONF_UNIQUE_ID_PREFIX,
    DEFAULT_DEVICE_NAME,
    DEFAULT_UNIQUE_ID_PREFIX,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er


class TestAsyncSetupEntryExtended:
    """Extended tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_calls_migration(self, hass: HomeAssistant) -> None:
        """Test setup entry calls YAML migration when configured."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: DEFAULT_UNIQUE_ID_PREFIX,
            },
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mqtt.async_wait_for_mqtt_client",
                return_value=True,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_migrate_yaml_entities",
                return_value={"entities_migrated": 0},
            ) as mock_migrate,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        mock_migrate.assert_called_once()

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
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=True
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_register_device"
            ) as mock_register,
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

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True


class TestAsyncMigrateEntryExtended:
    """Extended tests for async_migrate_entry function."""

    @pytest.mark.asyncio
    async def test_migrate_already_current_version(self, hass: HomeAssistant) -> None:
        """Test migration when already at current version."""
        from custom_components.sugar_valley_neopool import CONFIG_ENTRY_VERSION

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


class TestAsyncMigrateYamlEntitiesExtended:
    """Extended tests for async_migrate_yaml_entities function."""

    @pytest.mark.asyncio
    async def test_migrate_handles_registry_error(self, hass: HomeAssistant) -> None:
        """Test migration handles entity registry errors gracefully."""
        entity_registry = er.async_get(hass)

        # Create entity that might cause issues
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_test_sensor",
            suggested_object_id="test_sensor",
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: DEFAULT_UNIQUE_ID_PREFIX,
            },
        )
        entry.add_to_hass(hass)

        # Should not raise
        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert "entities_found" in result
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_migrate_different_prefixes(self, hass: HomeAssistant) -> None:
        """Test migration with different unique_id prefixes."""
        entity_registry = er.async_get(hass)

        # Create entities with different prefix
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="custom_pool_temp",
            suggested_object_id="custom_temp",
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: "custom_pool_",
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert result["entities_found"] == 1

    @pytest.mark.asyncio
    async def test_migrate_multiple_entities_same_domain(
        self, hass: HomeAssistant
    ) -> None:
        """Test migration of multiple entities in same domain."""
        entity_registry = er.async_get(hass)

        # Create multiple sensor entities
        for i in range(5):
            entity_registry.async_get_or_create(
                domain="sensor",
                platform="mqtt",
                unique_id=f"neopool_mqtt_sensor_{i}",
                suggested_object_id=f"sensor_{i}",
            )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: DEFAULT_UNIQUE_ID_PREFIX,
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert result["entities_found"] == 5
        assert result["entities_migrated"] == 5

    @pytest.mark.asyncio
    async def test_migrate_mixed_platforms(self, hass: HomeAssistant) -> None:
        """Test migration of entities across different platforms."""
        entity_registry = er.async_get(hass)

        # Create entities in different platforms
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_temperature",
            suggested_object_id="temperature",
        )
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_pump_running",
            suggested_object_id="pump_running",
        )
        entity_registry.async_get_or_create(
            domain="switch",
            platform="mqtt",
            unique_id="neopool_mqtt_filtration",
            suggested_object_id="filtration",
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: DEFAULT_UNIQUE_ID_PREFIX,
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert result["entities_found"] == 3
        assert result["entities_migrated"] == 3


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
