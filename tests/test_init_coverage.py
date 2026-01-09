"""Additional tests for __init__.py to boost coverage to 97%+.

This file targets specific uncovered code paths:
- _apply_entity_id_mapping (lines 218-327)
- async_migrate_masked_unique_ids (lines 440-607)
- _wait_for_real_nodeid (lines 628-677)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    _apply_entity_id_mapping,
    _wait_for_real_nodeid,
    async_migrate_masked_unique_ids,
    async_setup_entry,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


class TestApplyEntityIdMapping:
    """Tests for _apply_entity_id_mapping function."""

    @pytest.mark.asyncio
    async def test_empty_mapping_does_nothing(self, hass: HomeAssistant) -> None:
        """Test empty mapping doesn't modify anything."""
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

        # Should complete without error
        await _apply_entity_id_mapping(hass, entry, {})

    @pytest.mark.asyncio
    async def test_mapping_with_full_entity_id_format(self, hass: HomeAssistant) -> None:
        """Test mapping using full entity_id format (domain.object_id)."""
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

        # Create a mock entity in the registry
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph_data",
        )

        mapping = {"ph_data": "sensor.neopool_mqtt_ph_data"}

        await _apply_entity_id_mapping(hass, entry, mapping)

        # Verify the entity was renamed
        updated_entity = entity_registry.async_get("sensor.neopool_mqtt_ph_data")
        assert updated_entity is not None

    @pytest.mark.asyncio
    async def test_mapping_with_object_id_only_format(self, hass: HomeAssistant) -> None:
        """Test mapping using object_id only format (backwards compatibility)."""
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

        # Create a mock entity
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_water_temperature",
            config_entry=entry,
            suggested_object_id="neopool_water_temp",
        )

        # Old format: just object_id without domain
        mapping = {"water_temperature": "neopool_yaml_temperature"}

        await _apply_entity_id_mapping(hass, entry, mapping)

        # Verify entity was renamed
        updated_entity = entity_registry.async_get("sensor.neopool_yaml_temperature")
        assert updated_entity is not None

    @pytest.mark.asyncio
    async def test_mapping_entity_not_found(self, hass: HomeAssistant) -> None:
        """Test mapping when entity doesn't exist."""
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

        # No entities created - mapping should handle gracefully
        mapping = {"nonexistent_entity": "sensor.should_not_crash"}

        # Should complete without error
        await _apply_entity_id_mapping(hass, entry, mapping)

    @pytest.mark.asyncio
    async def test_mapping_yaml_key_translation(self, hass: HomeAssistant) -> None:
        """Test YAML key to integration key translation."""
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

        # Create entity with integration key
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="switch",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_filtration",
            config_entry=entry,
            suggested_object_id="neopool_filtration",
        )

        # YAML uses "filtration_switch" which maps to "filtration"
        mapping = {"filtration_switch": "switch.neopool_yaml_filtration"}

        await _apply_entity_id_mapping(hass, entry, mapping)

        # Entity should be renamed
        updated_entity = entity_registry.async_get("switch.neopool_yaml_filtration")
        assert updated_entity is not None

    @pytest.mark.asyncio
    async def test_mapping_cross_domain_skipped(self, hass: HomeAssistant) -> None:
        """Test cross-domain mapping is skipped (HA doesn't allow)."""
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

        # Create a sensor entity
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph",
        )

        # Try to rename sensor to switch domain - should be skipped
        mapping = {"ph_data": "switch.neopool_ph_switch"}

        await _apply_entity_id_mapping(hass, entry, mapping)

        # Original entity should still exist unchanged
        original = entity_registry.async_get("sensor.neopool_ph")
        assert original is not None

    @pytest.mark.asyncio
    async def test_mapping_already_correct_entity_id(self, hass: HomeAssistant) -> None:
        """Test mapping skips entity with already correct ID."""
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

        # Create entity with already correct ID
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_temperature",
            config_entry=entry,
            suggested_object_id="neopool_mqtt_temperature",
        )

        # Mapping points to same ID it already has
        mapping = {"temperature": "sensor.neopool_mqtt_temperature"}

        await _apply_entity_id_mapping(hass, entry, mapping)

        # Entity should still exist
        entity = entity_registry.async_get("sensor.neopool_mqtt_temperature")
        assert entity is not None

    @pytest.mark.asyncio
    async def test_mapping_target_already_exists(self, hass: HomeAssistant) -> None:
        """Test mapping when target entity_id already exists."""
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

        # Create source entity
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph_new",
        )

        # Create target entity that already exists
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_other",
            config_entry=entry,
            suggested_object_id="neopool_ph_target",
        )

        # Try to rename to already existing target
        mapping = {"ph_data": "sensor.neopool_ph_target"}

        # Should not crash, just log warning
        await _apply_entity_id_mapping(hass, entry, mapping)

        # Source entity should remain unchanged
        source = entity_registry.async_get("sensor.neopool_ph_new")
        assert source is not None


class TestAsyncMigrateMaskedUniqueIds:
    """Tests for async_migrate_masked_unique_ids function."""

    @pytest.mark.asyncio
    async def test_no_masked_entities_returns_true(self, hass: HomeAssistant) -> None:
        """Test returns True when no masked entities exist."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",  # Valid NodeID, not masked
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="ABC123",
        )

        result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_masked_nodeid_in_config_triggers_migration(self, hass: HomeAssistant) -> None:
        """Test masked NodeID in config entry triggers migration."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "XXXX XXXX XXXX XXXX XXXX 3435",  # Masked NodeID
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="XXXX XXXX XXXX XXXX XXXX 3435",
        )

        with (
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._wait_for_real_nodeid",
                new_callable=AsyncMock,
                return_value="REALNODEID123",
            ),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True
        # Config entry should be updated with real NodeID
        assert entry.data[CONF_NODEID] == "REALNODEID123"

    @pytest.mark.asyncio
    async def test_masked_entity_unique_ids_migrated(self, hass: HomeAssistant) -> None:
        """Test entities with masked unique_ids are migrated."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid=masked_nodeid,
        )

        # Create entity with masked unique_id
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"neopool_mqtt_{masked_nodeid}_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph",
        )

        with (
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._wait_for_real_nodeid",
                new_callable=AsyncMock,
                return_value="REAL123",
            ),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True

        # Entity should have new unique_id with real NodeID
        updated_entity = entity_registry.async_get("sensor.neopool_ph")
        assert updated_entity is not None
        assert "REAL123" in updated_entity.unique_id
        assert "XXXX" not in updated_entity.unique_id

    @pytest.mark.asyncio
    async def test_setoption157_set_is_called(self, hass: HomeAssistant) -> None:
        """Test SetOption157 set command is sent during migration."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "XXXX XXXX XXXX XXXX XXXX 3435",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="XXXX XXXX XXXX XXXX XXXX 3435",
        )

        with (
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ) as mock_set,
            patch(
                "custom_components.sugar_valley_neopool._wait_for_real_nodeid",
                new_callable=AsyncMock,
                return_value="REALNODEID",
            ),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True
        mock_set.assert_called_once_with(hass, "SmartPool", enable=True)

    @pytest.mark.asyncio
    async def test_wait_for_nodeid_fails_returns_false(self, hass: HomeAssistant) -> None:
        """Test returns False when waiting for NodeID fails."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "XXXX XXXX XXXX XXXX XXXX 3435",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid="XXXX XXXX XXXX XXXX XXXX 3435",
        )

        with (
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._wait_for_real_nodeid",
                new_callable=AsyncMock,
                return_value=None,  # Failed to get NodeID
            ),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is False

    @pytest.mark.asyncio
    async def test_entity_migration_with_existing_unique_id(self, hass: HomeAssistant) -> None:
        """Test entity migration skips when new unique_id already exists."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid=masked_nodeid,
        )

        entity_registry = er.async_get(hass)

        # Create entity with masked unique_id
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"neopool_mqtt_{masked_nodeid}_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph_masked",
        )

        # Create entity with the target unique_id already
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_REAL123_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph_real",
        )

        with (
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._wait_for_real_nodeid",
                new_callable=AsyncMock,
                return_value="REAL123",
            ),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        # Should still return True (migration completed)
        assert result is True

        # Original masked entity should still have old unique_id (couldn't migrate)
        masked_entity = entity_registry.async_get("sensor.neopool_ph_masked")
        assert masked_entity is not None
        assert "XXXX" in masked_entity.unique_id

    @pytest.mark.asyncio
    async def test_device_registry_updated_with_real_nodeid(self, hass: HomeAssistant) -> None:
        """Test device registry identifier is updated with real NodeID."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Test Pool",
            mqtt_topic="SmartPool",
            nodeid=masked_nodeid,
        )

        # Register device with masked NodeID
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, masked_nodeid)},
            manufacturer="Sugar Valley",
            name="Test Pool",
        )

        with (
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.sugar_valley_neopool._wait_for_real_nodeid",
                new_callable=AsyncMock,
                return_value="REALNODEID123",
            ),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True

        # Device should now have real NodeID identifier
        device = device_registry.async_get_device(identifiers={(DOMAIN, "REALNODEID123")})
        assert device is not None


class TestWaitForRealNodeid:
    """Tests for _wait_for_real_nodeid function."""

    @pytest.mark.asyncio
    async def test_receives_valid_nodeid(self, hass: HomeAssistant) -> None:
        """Test receiving valid NodeID from telemetry."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch("homeassistant.components.mqtt.async_publish"),
        ):
            # Start the wait in a task
            task = asyncio.create_task(_wait_for_real_nodeid(hass, "SmartPool", wait_timeout=5.0))

            # Give it time to subscribe
            await asyncio.sleep(0.1)

            # Simulate receiving telemetry with valid NodeID
            if received_callback:
                mock_msg = MagicMock()
                mock_msg.payload = json.dumps(
                    {"NeoPool": {"Powerunit": {"NodeID": "4C7525BFB344"}}}
                )
                received_callback(mock_msg)

            result = await task

        assert result == "4C7525BFB344"

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, hass: HomeAssistant) -> None:
        """Test timeout returns None."""

        async def mock_subscribe(hass, topic, callback, **kwargs):
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch("homeassistant.components.mqtt.async_publish"),
        ):
            result = await _wait_for_real_nodeid(hass, "SmartPool", wait_timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self, hass: HomeAssistant) -> None:
        """Test invalid JSON payload is ignored."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch("homeassistant.components.mqtt.async_publish"),
        ):
            task = asyncio.create_task(_wait_for_real_nodeid(hass, "SmartPool", wait_timeout=0.5))

            await asyncio.sleep(0.1)

            # Send invalid JSON - should be ignored
            if received_callback:
                mock_msg = MagicMock()
                mock_msg.payload = "not valid json"
                received_callback(mock_msg)

            result = await task

        # Should timeout since invalid JSON was ignored
        assert result is None

    @pytest.mark.asyncio
    async def test_bytes_payload_decoded(self, hass: HomeAssistant) -> None:
        """Test bytes payload is decoded correctly."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch("homeassistant.components.mqtt.async_publish"),
        ):
            task = asyncio.create_task(_wait_for_real_nodeid(hass, "SmartPool", wait_timeout=5.0))

            await asyncio.sleep(0.1)

            # Send bytes payload
            if received_callback:
                mock_msg = MagicMock()
                mock_msg.payload = b'{"NeoPool": {"Powerunit": {"NodeID": "BYTESNODEID"}}}'
                received_callback(mock_msg)

            result = await task

        assert result == "BYTESNODEID"

    @pytest.mark.asyncio
    async def test_invalid_nodeid_ignored(self, hass: HomeAssistant) -> None:
        """Test invalid NodeID (hidden) is ignored."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch("homeassistant.components.mqtt.async_publish"),
        ):
            task = asyncio.create_task(_wait_for_real_nodeid(hass, "SmartPool", wait_timeout=0.5))

            await asyncio.sleep(0.1)

            # Send "hidden" NodeID - should be ignored
            if received_callback:
                mock_msg = MagicMock()
                mock_msg.payload = json.dumps({"NeoPool": {"Powerunit": {"NodeID": "hidden"}}})
                received_callback(mock_msg)

            result = await task

        # Should timeout since hidden NodeID was rejected
        assert result is None


class TestSetupEntryWithEntityIdMapping:
    """Tests for async_setup_entry with entity_id_mapping."""

    @pytest.mark.asyncio
    async def test_setup_applies_entity_id_mapping(self, hass: HomeAssistant) -> None:
        """Test setup applies entity_id_mapping from config data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
                "entity_id_mapping": {"ph_data": "sensor.yaml_ph"},
            },
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mqtt.async_wait_for_mqtt_client",
                return_value=True,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups", return_value=True),
            patch(
                "custom_components.sugar_valley_neopool.async_fetch_device_metadata",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_migrate_masked_unique_ids",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.sugar_valley_neopool._apply_entity_id_mapping",
                new_callable=AsyncMock,
            ) as mock_apply,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        # Verify _apply_entity_id_mapping was called with the mapping
        mock_apply.assert_called_once()
        call_args = mock_apply.call_args
        assert call_args[0][2] == {"ph_data": "sensor.yaml_ph"}

    @pytest.mark.asyncio
    async def test_setup_handles_migration_failure(self, hass: HomeAssistant) -> None:
        """Test setup continues even if masked unique_id migration fails."""
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
            patch(
                "custom_components.sugar_valley_neopool.async_fetch_device_metadata",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_migrate_masked_unique_ids",
                new_callable=AsyncMock,
                return_value=False,  # Migration failed
            ),
        ):
            result = await async_setup_entry(hass, entry)

        # Setup should still succeed
        assert result is True
