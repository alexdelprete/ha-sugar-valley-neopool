"""Tests for Sugar Valley NeoPool integration initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    CONFIG_ENTRY_VERSION,
    NeoPoolData,
    async_migrate_entry,
    async_migrate_yaml_entities,
    async_register_device,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
    get_device_info,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_ENABLE_REPAIR_NOTIFICATION,
    CONF_FAILURES_THRESHOLD,
    CONF_MIGRATE_YAML,
    CONF_NODEID,
    CONF_OFFLINE_TIMEOUT,
    CONF_RECOVERY_SCRIPT,
    CONF_UNIQUE_ID_PREFIX,
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_RECOVERY_SCRIPT,
    DEFAULT_UNIQUE_ID_PREFIX,
    DOMAIN,
    VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_success(self, hass: HomeAssistant) -> None:
        """Test successful setup entry."""
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
                return_value=True,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True),
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        assert entry.runtime_data.device_name == "Test Pool"
        assert entry.runtime_data.mqtt_topic == "SmartPool"
        assert entry.runtime_data.nodeid == "ABC123"

    @pytest.mark.asyncio
    async def test_setup_entry_mqtt_not_available(self, hass: HomeAssistant) -> None:
        """Test setup fails when MQTT is not available."""
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
    async def test_setup_entry_uses_default_name(self, hass: HomeAssistant) -> None:
        """Test setup uses default name when not provided."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
            },
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mqtt.async_wait_for_mqtt_client",
                return_value=True,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True),
        ):
            await async_setup_entry(hass, entry)

        assert entry.runtime_data.device_name == DEFAULT_DEVICE_NAME


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry function."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, hass: HomeAssistant) -> None:
        """Test successful unload entry."""
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
        )

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            result = await async_unload_entry(hass, entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_unload_entry_failure(self, hass: HomeAssistant) -> None:
        """Test unload entry returns False on failure."""
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
        )

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
            result = await async_unload_entry(hass, entry)

        assert result is False


class TestAsyncMigrateEntry:
    """Tests for async_migrate_entry function."""

    @pytest.mark.asyncio
    async def test_migrate_from_v1_to_v2(self, hass: HomeAssistant) -> None:
        """Test migration from version 1 to 2."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=1,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
            },
            options={},
        )
        entry.add_to_hass(hass)

        result = await async_migrate_entry(hass, entry)

        assert result is True
        assert entry.version == CONFIG_ENTRY_VERSION
        assert CONF_ENABLE_REPAIR_NOTIFICATION in entry.options
        assert CONF_FAILURES_THRESHOLD in entry.options
        assert CONF_RECOVERY_SCRIPT in entry.options
        assert CONF_OFFLINE_TIMEOUT in entry.options

    @pytest.mark.asyncio
    async def test_migrate_preserves_existing_options(self, hass: HomeAssistant) -> None:
        """Test migration preserves existing options."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=1,
            data={CONF_DEVICE_NAME: "Pool"},
            options={"existing_option": "value"},
        )
        entry.add_to_hass(hass)

        await async_migrate_entry(hass, entry)

        assert entry.options["existing_option"] == "value"

    @pytest.mark.asyncio
    async def test_migrate_sets_defaults(self, hass: HomeAssistant) -> None:
        """Test migration sets default values."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=1,
            data={CONF_DEVICE_NAME: "Pool"},
            options={},
        )
        entry.add_to_hass(hass)

        await async_migrate_entry(hass, entry)

        assert entry.options[CONF_ENABLE_REPAIR_NOTIFICATION] == DEFAULT_ENABLE_REPAIR_NOTIFICATION
        assert entry.options[CONF_FAILURES_THRESHOLD] == DEFAULT_FAILURES_THRESHOLD
        assert entry.options[CONF_RECOVERY_SCRIPT] == DEFAULT_RECOVERY_SCRIPT
        assert entry.options[CONF_OFFLINE_TIMEOUT] == DEFAULT_OFFLINE_TIMEOUT

    @pytest.mark.asyncio
    async def test_no_downgrade(self, hass: HomeAssistant) -> None:
        """Test migration fails for future version."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=CONFIG_ENTRY_VERSION + 1,
            data={CONF_DEVICE_NAME: "Pool"},
        )
        entry.add_to_hass(hass)

        result = await async_migrate_entry(hass, entry)

        assert result is False


class TestAsyncRegisterDevice:
    """Tests for async_register_device function."""

    @pytest.mark.asyncio
    async def test_register_device(self, hass: HomeAssistant) -> None:
        """Test device registration."""
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
        )

        await async_register_device(hass, entry)

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123")})

        assert device is not None
        assert device.name == "Test Pool"

    @pytest.mark.asyncio
    async def test_register_device_stores_device_id(self, hass: HomeAssistant) -> None:
        """Test device registration stores device_id in runtime_data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "PoolTopic",
                CONF_NODEID: "XYZ789",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="My Pool",
            mqtt_topic="PoolTopic",
            nodeid="XYZ789",
        )

        await async_register_device(hass, entry)

        assert entry.runtime_data.device_id is not None


class TestAsyncRemoveConfigEntryDevice:
    """Tests for async_remove_config_entry_device function."""

    @pytest.mark.asyncio
    async def test_remove_device_returns_false(self, hass: HomeAssistant) -> None:
        """Test remove device always returns False."""
        entry = MockConfigEntry(domain=DOMAIN, data={})
        device = MagicMock()
        device.identifiers = {(DOMAIN, "ABC123")}

        result = await async_remove_config_entry_device(hass, entry, device)

        assert result is False


class TestGetDeviceInfo:
    """Tests for get_device_info function."""

    def test_get_device_info(self) -> None:
        """Test getting device info."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
            },
        )

        device_info = get_device_info(entry)

        assert device_info["identifiers"] == {(DOMAIN, "ABC123")}
        assert device_info["name"] == "Test Pool"
        assert device_info["sw_version"] == VERSION

    def test_get_device_info_default_name(self) -> None:
        """Test device info uses default name."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "ABC123",
            },
        )

        device_info = get_device_info(entry)

        assert device_info["name"] == DEFAULT_DEVICE_NAME


class TestNeoPoolData:
    """Tests for NeoPoolData dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="Topic",
            nodeid="123",
        )

        assert data.device_name == "Pool"
        assert data.mqtt_topic == "Topic"
        assert data.nodeid == "123"
        assert data.sensor_data == {}
        assert data.available is False
        assert data.device_id is None

    def test_with_sensor_data(self) -> None:
        """Test with sensor data."""
        data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="Topic",
            nodeid="123",
            sensor_data={"temp": 28.5},
            available=True,
        )

        assert data.sensor_data == {"temp": 28.5}
        assert data.available is True


class TestConfigEntryVersion:
    """Tests for config entry version constant."""

    def test_config_entry_version(self) -> None:
        """Test CONFIG_ENTRY_VERSION is defined."""
        assert CONFIG_ENTRY_VERSION == 2


class TestAsyncMigrateYamlEntities:
    """Tests for async_migrate_yaml_entities function."""

    @pytest.mark.asyncio
    async def test_skip_when_not_yaml_migration(self, hass: HomeAssistant) -> None:
        """Test migration is skipped when not a YAML migration."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                # No CONF_MIGRATE_YAML key
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert result["entities_found"] == 0
        assert result["entities_migrated"] == 0

    @pytest.mark.asyncio
    async def test_skip_when_migrate_yaml_false(self, hass: HomeAssistant) -> None:
        """Test migration is skipped when migrate_yaml is False."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: False,
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert result["entities_found"] == 0

    @pytest.mark.asyncio
    async def test_migrate_entities_success(self, hass: HomeAssistant) -> None:
        """Test successful entity migration."""
        # Create orphaned entities in registry
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_water_temperature",
            suggested_object_id="neopool_water_temperature",
        )
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_ph_data",
            suggested_object_id="neopool_ph",
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "XYZ789",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: DEFAULT_UNIQUE_ID_PREFIX,
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "XYZ789")

        assert result["entities_found"] == 2
        assert result["entities_migrated"] == 2
        assert len(result["errors"]) == 0

        # Verify entities were updated
        updated_entity = entity_registry.async_get("sensor.neopool_water_temperature")
        assert updated_entity.unique_id == "neopool_mqtt_XYZ789_water_temperature"
        assert updated_entity.config_entry_id == entry.entry_id

    @pytest.mark.asyncio
    async def test_migrate_with_custom_prefix(self, hass: HomeAssistant) -> None:
        """Test migration with custom unique_id prefix."""
        # Create orphaned entity with custom prefix
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="custom_prefix_temperature",
            suggested_object_id="custom_temp",
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_NODEID: "ABC123",
                CONF_MIGRATE_YAML: True,
                CONF_UNIQUE_ID_PREFIX: "custom_prefix_",
            },
        )
        entry.add_to_hass(hass)

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        assert result["entities_found"] == 1
        assert result["entities_migrated"] == 1

        # Verify entity was updated with correct new unique_id
        updated_entity = entity_registry.async_get("sensor.custom_temp")
        assert updated_entity.unique_id == "neopool_mqtt_ABC123_temperature"

    @pytest.mark.asyncio
    async def test_no_orphaned_entities_found(self, hass: HomeAssistant) -> None:
        """Test when no orphaned entities are found."""
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

        assert result["entities_found"] == 0
        assert result["entities_migrated"] == 0
        assert len(result["steps"]) >= 1

    @pytest.mark.asyncio
    async def test_excludes_already_configured_entities(self, hass: HomeAssistant) -> None:
        """Test that entities with config_entry_id are excluded."""
        # Create another config entry
        other_entry = MockConfigEntry(
            domain="other_domain",
            data={},
        )
        other_entry.add_to_hass(hass)

        # Create entity already associated with a config entry
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_configured_sensor",
            suggested_object_id="configured_sensor",
            config_entry=other_entry,
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

        # Should not find the already-configured entity
        assert result["entities_found"] == 0

    @pytest.mark.asyncio
    async def test_migration_summary_steps(self, hass: HomeAssistant) -> None:
        """Test that migration summary includes proper steps."""
        # Create orphaned entity
        entity_registry = er.async_get(hass)
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

        result = await async_migrate_yaml_entities(hass, entry, "ABC123")

        # Verify steps are recorded
        assert len(result["steps"]) >= 2
        step_names = [step["name"] for step in result["steps"]]
        assert "Find orphaned entities" in step_names
        assert "Migrate entities" in step_names

    @pytest.mark.asyncio
    async def test_shows_persistent_notification(self, hass: HomeAssistant) -> None:
        """Test that migration shows persistent notification."""
        # Create orphaned entity
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_notif_test",
            suggested_object_id="notif_test",
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

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await async_migrate_yaml_entities(hass, entry, "ABC123")

            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert "NeoPool" in call_args[1]["title"]
            assert call_args[1]["notification_id"] == "neopool_migration_summary"
