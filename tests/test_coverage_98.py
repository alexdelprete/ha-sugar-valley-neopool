"""Comprehensive tests to achieve 98%+ coverage.

This file targets specific uncovered code paths across all files:
- __init__.py: lines 138, 140, 257, 395-402, 410, 550, 607-611, 644-645, 703-774, 791-810, 903-963
- helpers.py: lines 148, 264-267, 311, 362-402
- config_flow.py: lines 665, 673, 692, 730, 1005
- select.py: line 133
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    _cleanup_orphaned_yaml_entities,
    _update_device_registry_metadata,
    async_fetch_device_metadata,
    async_remove_config_entry_device,
    async_setup_entry,
    get_device_info,
)
from custom_components.sugar_valley_neopool.config_flow import NeoPoolConfigFlow
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    CONF_NODEID_HASHED,
    DOMAIN,
)
from custom_components.sugar_valley_neopool.helpers import (
    classify_nodeid,
    extract_entity_key_from_masked_unique_id,
    is_nodeid_hashed,
    is_nodeid_masked,
    validate_nodeid,
)
from custom_components.sugar_valley_neopool.select import (
    NeoPoolSelect,
    NeoPoolSelectEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

# =============================================================================
# __init__.py Coverage Tests
# =============================================================================


class TestCleanupOrphanedYamlEntities:
    """Tests for _cleanup_orphaned_yaml_entities function - lines 395-402, 410."""

    @pytest.mark.asyncio
    async def test_cleanup_finds_orphaned_mqtt_entities(self, hass: HomeAssistant) -> None:
        """Test cleanup finds and deletes orphaned MQTT entities."""
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

        entity_registry = er.async_get(hass)

        # Create orphaned MQTT entity (binary_sensor relay state - replaced by switch)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform="mqtt",  # MQTT platform, not our integration
            unique_id="neopool_mqtt_relay_aux1_state",
            config_entry=None,  # Orphaned - no config entry
            suggested_object_id="neopool_relay_aux1",
        )

        await _cleanup_orphaned_yaml_entities(hass, entry)

        # Entity should be removed
        entity = entity_registry.async_get("binary_sensor.neopool_relay_aux1")
        assert entity is None

    @pytest.mark.asyncio
    async def test_cleanup_with_nodeid_in_unique_id(self, hass: HomeAssistant) -> None:
        """Test cleanup handles entities with NodeID in unique_id."""
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

        entity_registry = er.async_get(hass)

        # Create orphaned MQTT entity with NodeID format
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform="mqtt",
            unique_id="neopool_mqtt_ABC123_relay_aux2_state",
            config_entry=None,
            suggested_object_id="neopool_relay_aux2",
        )

        await _cleanup_orphaned_yaml_entities(hass, entry)

        # Entity should be removed
        entity = entity_registry.async_get("binary_sensor.neopool_relay_aux2")
        assert entity is None

    @pytest.mark.asyncio
    async def test_cleanup_no_orphans_found(self, hass: HomeAssistant) -> None:
        """Test cleanup handles case with no orphaned entities."""
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

        # No orphaned entities created
        await _cleanup_orphaned_yaml_entities(hass, entry)
        # Should complete without error


class TestAsyncFetchDeviceMetadata:
    """Tests for async_fetch_device_metadata - lines 607-611, 644-645."""

    @pytest.mark.asyncio
    async def test_fetch_metadata_extracts_manufacturer(self, hass: HomeAssistant) -> None:
        """Test metadata extraction gets manufacturer from Type."""
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

        # Register device first
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            manufacturer="Sugar Valley",
            name="Test Pool",
        )

        sensor_callback = None
        status_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal sensor_callback, status_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            elif "STATUS" in topic:
                status_callback = callback
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=mock_subscribe),
            patch("homeassistant.components.mqtt.async_publish", new_callable=AsyncMock),
        ):
            task = asyncio.create_task(async_fetch_device_metadata(hass, entry, wait_timeout=5.0))
            await asyncio.sleep(0.1)

            # Simulate SENSOR telemetry with metadata
            if sensor_callback:
                mock_msg = MagicMock()
                mock_msg.payload = json.dumps(
                    {
                        "NeoPool": {
                            "Type": "Hayward AquaRite",
                            "Powerunit": {"Version": "V3.2.1"},
                        }
                    }
                )
                sensor_callback(mock_msg)

            # Simulate Status 2 (firmware) and Status 5 (network) responses
            if status_callback:
                mock_status2 = MagicMock()
                mock_status2.payload = json.dumps(
                    {"StatusFWR": {"Version": "15.3.0(release-tasmota)"}}
                )
                status_callback(mock_status2)

                mock_status5 = MagicMock()
                mock_status5.payload = json.dumps({"StatusNET": {"IPAddress": "192.168.1.100"}})
                status_callback(mock_status5)

            await task

        assert entry.runtime_data.manufacturer == "Hayward AquaRite"
        assert entry.runtime_data.fw_version == "V3.2.1"

    @pytest.mark.asyncio
    async def test_fetch_metadata_timeout(self, hass: HomeAssistant) -> None:
        """Test metadata fetch handles timeout gracefully."""
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

        async def mock_subscribe(hass, topic, callback, **kwargs):
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=mock_subscribe),
            patch("homeassistant.components.mqtt.async_publish", new_callable=AsyncMock),
        ):
            await async_fetch_device_metadata(hass, entry, wait_timeout=0.1)

        # Should complete without error, metadata remains None
        assert entry.runtime_data.manufacturer is None

    @pytest.mark.asyncio
    async def test_fetch_metadata_invalid_json(self, hass: HomeAssistant) -> None:
        """Test metadata fetch handles invalid JSON."""
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

        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=mock_subscribe),
            patch("homeassistant.components.mqtt.async_publish", new_callable=AsyncMock),
        ):
            task = asyncio.create_task(async_fetch_device_metadata(hass, entry, wait_timeout=0.5))
            await asyncio.sleep(0.1)

            # Send invalid JSON
            if received_callback:
                mock_msg = MagicMock()
                mock_msg.payload = "not valid json"
                received_callback(mock_msg)

            await task

        # Should complete without error
        assert entry.runtime_data.manufacturer is None

    @pytest.mark.asyncio
    async def test_fetch_metadata_bytes_payload(self, hass: HomeAssistant) -> None:
        """Test metadata fetch handles bytes payload."""
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

        # Register device
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            manufacturer="Sugar Valley",
            name="Test Pool",
        )

        sensor_callback = None
        status_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal sensor_callback, status_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            elif "STATUS" in topic:
                status_callback = callback
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=mock_subscribe),
            patch("homeassistant.components.mqtt.async_publish", new_callable=AsyncMock),
        ):
            task = asyncio.create_task(async_fetch_device_metadata(hass, entry, wait_timeout=5.0))
            await asyncio.sleep(0.1)

            # Send bytes payload for SENSOR
            if sensor_callback:
                mock_msg = MagicMock()
                mock_msg.payload = (
                    b'{"NeoPool": {"Type": "Zodiac", "Powerunit": {"Version": "1.0"}}}'
                )
                sensor_callback(mock_msg)

            # Send Status responses to satisfy gather
            if status_callback:
                mock_status2 = MagicMock()
                mock_status2.payload = json.dumps({"StatusFWR": {"Version": "15.0.0"}})
                status_callback(mock_status2)

                mock_status5 = MagicMock()
                mock_status5.payload = json.dumps({"StatusNET": {"IPAddress": "10.0.0.1"}})
                status_callback(mock_status5)

            await task

        assert entry.runtime_data.manufacturer == "Zodiac"


class TestUpdateDeviceRegistryMetadata:
    """Tests for _update_device_registry_metadata - lines 703-774."""

    @pytest.mark.asyncio
    async def test_update_metadata_device_not_found(self, hass: HomeAssistant) -> None:
        """Test update handles missing device gracefully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "NONEXISTENT",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="NONEXISTENT",
            manufacturer="Test Manufacturer",
        )

        # Don't create device - let it be missing
        await _update_device_registry_metadata(hass, entry)
        # Should complete without error

    @pytest.mark.asyncio
    async def test_update_metadata_with_firmware(self, hass: HomeAssistant) -> None:
        """Test update sets firmware version."""
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
            manufacturer="Hayward",
            fw_version="V2.5.0",
        )

        # Create device
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            manufacturer="Sugar Valley",
            name="Test Pool",
        )

        await _update_device_registry_metadata(hass, entry)

        device = device_registry.async_get_device_by_identifier((DOMAIN, "ABC123"), entry.entry_id)
        assert device is not None
        assert device.manufacturer == "Hayward"
        assert device.sw_version == "Powerunit V2.5.0"


class TestGetDeviceInfo:
    """Tests for get_device_info function."""

    def test_device_info_with_runtime_metadata(self) -> None:
        """Test device info uses runtime metadata when available."""
        entry = MagicMock()
        entry.data = {
            CONF_DEVICE_NAME: "My Pool",
            CONF_NODEID: "ABC123",
        }
        entry.runtime_data = NeoPoolData(
            device_name="My Pool",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
            manufacturer="Hayward",
            fw_version="V2.0.0",
        )

        info = get_device_info(entry)

        assert info["manufacturer"] == "Hayward"
        assert info["sw_version"] == "Powerunit V2.0.0"

    def test_device_info_without_runtime_data(self) -> None:
        """Test device info uses defaults without runtime_data."""
        entry = MagicMock()
        entry.data = {
            CONF_DEVICE_NAME: "My Pool",
            CONF_NODEID: "ABC123",
        }
        entry.runtime_data = None

        info = get_device_info(entry)

        assert info["manufacturer"] == "Sugar Valley"
        assert info["sw_version"] is None


class TestAsyncRemoveConfigEntryDevice:
    """Tests for async_remove_config_entry_device."""

    @pytest.mark.asyncio
    async def test_remove_device_returns_true(self, hass: HomeAssistant) -> None:
        """Test remove device returns True to allow removal."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DEVICE_NAME: "Test"},
        )
        entry.add_to_hass(hass)

        device_entry = MagicMock()

        result = await async_remove_config_entry_device(hass, entry, device_entry)

        assert result is True


class TestSetupEntryLogging:
    """Tests for async_setup_entry logging paths - lines 138, 140, 257."""

    @pytest.mark.asyncio
    async def test_setup_logs_entity_mapping_details(self, hass: HomeAssistant) -> None:
        """Test setup logs entity mapping details when mapping exists."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
                CONF_NODEID_HASHED: "AA55HASHED",
                "entity_id_mapping": {
                    "ph_data": "sensor.neopool_ph",
                    "water_temperature": "sensor.neopool_temp",
                },
            },
        )
        entry.add_to_hass(hass)

        # Create some entities that would be found
        entity_registry = er.async_get(hass)
        for i in range(15):  # More than 10 to test "and X more" logging
            entity_registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=f"neopool_mqtt_ABC123_test_{i}",
                config_entry=entry,
                suggested_object_id=f"test_{i}",
            )

        with (
            patch("homeassistant.components.mqtt.async_wait_for_mqtt_client", return_value=True),
            patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True),
            patch(
                "custom_components.sugar_valley_neopool.async_fetch_device_metadata",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._setup_dynamic_disable_watch",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._setup_result_watch",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._setup_register_recovery_watch",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._read_config_registers",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._migrate_to_canonical_nodeid",
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_migrate_masked_unique_ids",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.sugar_valley_neopool._apply_entity_id_mapping",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._cleanup_orphaned_yaml_entities",
                new_callable=AsyncMock,
            ),
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True


# =============================================================================
# helpers.py Coverage Tests
# =============================================================================


class TestExtractEntityKeyEdgeCases:
    """Tests for extract_entity_key_from_masked_unique_id edge cases - lines 264-267."""

    def test_extract_key_with_only_hex_end(self) -> None:
        """Test extraction when NodeID ends with hex digits."""
        # This tests the branch where we check for 4-char hex at the end
        unique_id = "neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_sensor"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        assert result == "sensor"

    def test_extract_key_multiple_underscores(self) -> None:
        """Test extraction with multiple underscores in entity key."""
        unique_id = "neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_hydrolysis_percent_setpoint"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        assert result == "hydrolysis_percent_setpoint"

    def test_extract_key_no_xxxx_pattern(self) -> None:
        """Test extraction with no XXXX pattern but spaces."""
        # Spaces alone don't indicate masked, only XXXX XXXX does
        unique_id = "neopool_mqtt_0026 0051 5443 5016 2036 3435_ph_data"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        # Should still extract the key
        assert result is not None


class TestIsNodeidMaskedEdgeCases:
    """Tests for is_nodeid_masked edge cases - line 148."""

    def test_nodeid_with_single_xxxx(self) -> None:
        """Test single XXXX is not considered masked."""
        # Only "XXXX XXXX" pattern indicates masking
        result = is_nodeid_masked("XXXX 0051 5443 5016 2036 3435")
        # Single XXXX at start should be masked
        assert result is False  # No "xxxx xxxx" pattern

    def test_nodeid_none_is_masked(self) -> None:
        """Test None NodeID is considered masked."""
        result = is_nodeid_masked(None)
        assert result is True

    def test_nodeid_empty_is_masked(self) -> None:
        """Test empty string is considered masked."""
        result = is_nodeid_masked("")
        assert result is True


class TestIsNodeidHashed:
    """Tests for is_nodeid_hashed function."""

    def test_hashed_nodeid_with_aa55_prefix(self) -> None:
        """Test NodeID with AA55 prefix is detected as hashed."""
        result = is_nodeid_hashed("AA55 1234 5678 9ABC DEF0 1234")
        assert result is True

    def test_hashed_nodeid_lowercase(self) -> None:
        """Test lowercase aa55 prefix is detected as hashed."""
        result = is_nodeid_hashed("aa55 1234 5678")
        assert result is True

    def test_hashed_nodeid_no_spaces(self) -> None:
        """Test AA55 prefix without spaces is detected as hashed."""
        result = is_nodeid_hashed("AA551234567890AB")
        assert result is True

    def test_real_nodeid_not_hashed(self) -> None:
        """Test real NodeID is not detected as hashed."""
        result = is_nodeid_hashed("4C7525BFB344")
        assert result is False

    def test_none_not_hashed(self) -> None:
        """Test None is not hashed."""
        result = is_nodeid_hashed(None)
        assert result is False

    def test_empty_not_hashed(self) -> None:
        """Test empty string is not hashed."""
        result = is_nodeid_hashed("")
        assert result is False

    def test_masked_not_hashed(self) -> None:
        """Test masked NodeID is not hashed."""
        result = is_nodeid_hashed("XXXX XXXX XXXX XXXX XXXX 3435")
        assert result is False


class TestClassifyNodeid:
    """Tests for classify_nodeid function."""

    def test_classify_real_nodeid(self) -> None:
        """Test real NodeID is classified as 'real'."""
        result = classify_nodeid("4C7525BFB344")
        assert result == "real"

    def test_classify_hashed_nodeid(self) -> None:
        """Test hashed NodeID with AA55 prefix is classified as 'hashed'."""
        result = classify_nodeid("AA55 1234 5678 9ABC DEF0 1234")
        assert result == "hashed"

    def test_classify_masked_nodeid(self) -> None:
        """Test masked NodeID with XXXX pattern is classified as 'masked'."""
        result = classify_nodeid("XXXX XXXX XXXX XXXX XXXX 3435")
        assert result == "masked"

    def test_classify_none_is_invalid(self) -> None:
        """Test None is classified as 'invalid'."""
        result = classify_nodeid(None)
        assert result == "invalid"

    def test_classify_empty_is_invalid(self) -> None:
        """Test empty string is classified as 'invalid'."""
        result = classify_nodeid("")
        assert result == "invalid"

    def test_classify_hidden_is_invalid(self) -> None:
        """Test 'hidden' is classified as 'invalid'."""
        result = classify_nodeid("hidden")
        assert result == "invalid"

    def test_classify_hidden_by_default_is_invalid(self) -> None:
        """Test 'hidden_by_default' is classified as 'invalid'."""
        result = classify_nodeid("hidden_by_default")
        assert result == "invalid"


class TestValidateNodeidAcceptsHashed:
    """Tests for validate_nodeid accepting hashed NodeIDs."""

    def test_hashed_nodeid_is_valid(self) -> None:
        """Test hashed NodeID (AA55 prefix) is accepted as valid."""
        result = validate_nodeid("AA55 1234 5678 9ABC DEF0 1234")
        assert result is True

    def test_masked_nodeid_is_invalid(self) -> None:
        """Test masked NodeID (XXXX pattern) is rejected."""
        result = validate_nodeid("XXXX XXXX XXXX XXXX XXXX 3435")
        assert result is False


# =============================================================================
# select.py Coverage Tests
# =============================================================================


class TestSelectInvalidOptionReturn:
    """Tests for select.py line 133 - return after invalid option warning."""

    @pytest.mark.asyncio
    async def test_select_invalid_option_returns_early(self) -> None:
        """Test async_select_option returns early for invalid option."""
        mock_entry = MagicMock()
        mock_entry.runtime_data = NeoPoolData(
            device_name="Test",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
        )

        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test",
            command="NPTest",
            options_map={0: "Off", 1: "On"},
            options=["Off", "On"],
        )

        select = NeoPoolSelect(mock_entry, desc)

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            # Call with invalid option
            await select.async_select_option("InvalidOption")

            # Should NOT have published anything
            mock_publish.assert_not_called()


# =============================================================================
# config_flow.py Coverage Tests
# =============================================================================


class TestConfigFlowExtractDeviceName:
    """Tests for config_flow.py _extract_device_name_from_migration - lines 665, 673, 692."""

    def test_extract_device_name_empty_mapping(self) -> None:
        """Test extraction with empty mapping returns default."""
        flow = NeoPoolConfigFlow()
        flow._migration_result = {"entity_id_mapping": {}}

        result = flow._extract_device_name_from_migration()

        assert result == "NeoPool"

    def test_extract_device_name_no_result(self) -> None:
        """Test extraction with no migration result returns default."""
        flow = NeoPoolConfigFlow()
        flow._migration_result = None

        result = flow._extract_device_name_from_migration()

        assert result == "NeoPool"

    def test_extract_device_name_custom_prefix(self) -> None:
        """Test extraction with custom prefix."""
        flow = NeoPoolConfigFlow()
        flow._migration_result = {"entity_id_mapping": {"ph_data": "sensor.my_pool_ph_data"}}

        result = flow._extract_device_name_from_migration()

        assert result == "My Pool"

    def test_extract_device_name_old_format(self) -> None:
        """Test extraction with old format (object_id only)."""
        flow = NeoPoolConfigFlow()
        flow._migration_result = {"entity_id_mapping": {"ph_data": "custom_pool_ph_data"}}
        result = flow._extract_device_name_from_migration()

        assert result == "Custom Pool"
