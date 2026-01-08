"""Extended tests for Sugar Valley NeoPool config flow - edge cases."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from custom_components.sugar_valley_neopool.config_flow import (
    NEOPOOL_SIGNATURES,
    NeoPoolConfigFlow,
    NeoPoolOptionsFlow,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    CONF_REGENERATE_ENTITY_IDS,
)
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SAMPLE_NEOPOOL_PAYLOAD_HIDDEN_NODEID, create_mqtt_message


class TestMqttDiscoveryExtended:
    """Extended tests for MQTT discovery."""

    async def test_mqtt_discovery_hidden_nodeid_triggers_auto_config(
        self, mock_hass: MagicMock
    ) -> None:
        """Test MQTT discovery with hidden NodeID triggers auto-configuration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        # Mock auto_configure_nodeid
        flow._auto_configure_nodeid = AsyncMock(
            return_value={"success": True, "nodeid": "CONFIGURED123"}
        )

        message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD_HIDDEN_NODEID)

        result = await flow.async_step_mqtt(message)

        # Should proceed to mqtt_confirm with configured NodeID
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mqtt_confirm"
        assert flow._nodeid == "CONFIGURED123"

    async def test_mqtt_discovery_auto_config_failure(self, mock_hass: MagicMock) -> None:
        """Test MQTT discovery when auto-configuration fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}

        # Mock auto_configure_nodeid to fail
        flow._auto_configure_nodeid = AsyncMock(
            return_value={"success": False, "error": "Configuration failed"}
        )

        message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD_HIDDEN_NODEID)

        result = await flow.async_step_mqtt(message)

        # Should abort with nodeid_configuration_failed
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "nodeid_configuration_failed"


class TestYamlMigrationExtended:
    """Extended tests for YAML migration flow."""

    async def test_yaml_topic_hidden_nodeid_triggers_auto_config(
        self, mock_hass: MagicMock
    ) -> None:
        """Test YAML topic step with hidden NodeID triggers auto-config."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        # First validation returns hidden NodeID
        flow._validate_yaml_topic = AsyncMock(
            return_value={
                "valid": True,
                "nodeid": "hidden",
                "payload": SAMPLE_NEOPOOL_PAYLOAD_HIDDEN_NODEID,
            }
        )

        # Auto-configure succeeds
        flow._auto_configure_nodeid = AsyncMock(
            return_value={"success": True, "nodeid": "NEWID123"}
        )

        flow._check_migratable_entities = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        await flow.async_step_yaml_topic({"yaml_topic": "SmartPool"})

        # Should have called auto-configure
        flow._auto_configure_nodeid.assert_called_once_with("SmartPool")
        assert flow._nodeid == "NEWID123"

    async def test_yaml_topic_auto_config_failure(self, mock_hass: MagicMock) -> None:
        """Test YAML topic step when auto-configuration fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )

        flow._auto_configure_nodeid = AsyncMock(return_value={"success": False, "error": "Failed"})

        result = await flow.async_step_yaml_topic({"yaml_topic": "SmartPool"})

        # When auto-config fails, the flow aborts
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "nodeid_configuration_failed"

    async def test_yaml_detect_hidden_nodeid_auto_config(self, mock_hass: MagicMock) -> None:
        """Test YAML detect with hidden NodeID triggers auto-config."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._auto_detect_topic = AsyncMock(return_value="SmartPool")
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        flow._auto_configure_nodeid = AsyncMock(
            return_value={"success": True, "nodeid": "AUTOCONFIG123"}
        )
        flow._check_migratable_entities = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        await flow.async_step_yaml_detect()

        assert flow._nodeid == "AUTOCONFIG123"

    async def test_yaml_detect_auto_config_failure_fallback_to_topic(
        self, mock_hass: MagicMock
    ) -> None:
        """Test YAML detect falls back to yaml_topic when auto-config fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._auto_detect_topic = AsyncMock(return_value="SmartPool")
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        flow._auto_configure_nodeid = AsyncMock(return_value={"success": False, "error": "Failed"})
        flow.async_step_yaml_topic = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_topic"}
        )

        result = await flow.async_step_yaml_detect()

        # Should fall back to yaml_topic step
        assert result["step_id"] == "yaml_topic"

    async def test_yaml_detect_validation_fails(self, mock_hass: MagicMock) -> None:
        """Test YAML detect when validation fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._auto_detect_topic = AsyncMock(return_value="SmartPool")
        flow._validate_yaml_topic = AsyncMock(return_value={"valid": False})
        flow.async_step_yaml_topic = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_topic"}
        )

        result = await flow.async_step_yaml_detect()

        # Should fall back to yaml_topic step
        assert result["step_id"] == "yaml_topic"


class TestReconfigureFlowExtended:
    """Extended tests for reconfigure flow."""

    def _create_mock_entry(self) -> MagicMock:
        """Create mock config entry."""
        entry = MagicMock()
        entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        entry.options = {}
        entry.unique_id = "sugar_valley_neopool_ABC123"
        entry.entry_id = "test_entry_id"
        return entry

    async def test_reconfigure_topic_validation_failure(self, mock_hass: MagicMock) -> None:
        """Test reconfigure with topic validation failure."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        flow._validate_yaml_topic = AsyncMock(return_value={"valid": False})

        result = await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    async def test_reconfigure_same_nodeid_success(self, mock_hass: MagicMock) -> None:
        """Test reconfigure with same NodeID succeeds."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        # Validation returns same NodeID
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )

        # Mock async_set_unique_id to set the unique_id
        async def mock_set_unique_id(unique_id):
            flow._unique_id = unique_id

        flow.async_set_unique_id = mock_set_unique_id

        # Mock _abort_if_unique_id_mismatch - this checks if entry unique_id matches
        flow._abort_if_unique_id_mismatch = MagicMock()

        # Mock async_update_reload_and_abort
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        result = await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        # Should successfully reconfigure
        flow.async_update_reload_and_abort.assert_called_once()
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

    async def test_reconfigure_hidden_nodeid_auto_config(self, mock_hass: MagicMock) -> None:
        """Test reconfigure with hidden NodeID triggers auto-config."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        # Validation returns hidden NodeID
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )

        # Auto-configure succeeds with same NodeID
        flow._auto_configure_nodeid = AsyncMock(return_value={"success": True, "nodeid": "ABC123"})

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        result = await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        flow._auto_configure_nodeid.assert_called_once()
        assert result["type"] == FlowResultType.ABORT

    async def test_reconfigure_auto_config_failure(self, mock_hass: MagicMock) -> None:
        """Test reconfigure when auto-config fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )

        flow._auto_configure_nodeid = AsyncMock(return_value={"success": False, "error": "Failed"})

        result = await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "nodeid_configuration_failed"

    async def test_reconfigure_with_regenerate_entity_ids(self, mock_hass: MagicMock) -> None:
        """Test reconfigure with entity ID regeneration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow._regenerate_entity_ids = AsyncMock(return_value=3)
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        result = await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Device Name",  # Different name
                CONF_DISCOVERY_PREFIX: "NewTopic",
                CONF_REGENERATE_ENTITY_IDS: True,
            }
        )

        # Should call regenerate since name changed
        flow._regenerate_entity_ids.assert_called_once()
        assert result["type"] == FlowResultType.ABORT


class TestRegenerateEntityIds:
    """Tests for _regenerate_entity_ids method."""

    async def test_regenerate_entity_ids(self, mock_hass: MagicMock) -> None:
        """Test entity ID regeneration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"

        # Create mock entity entries
        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_ABC123_water_temperature"
        entity1.entity_id = "sensor.old_pool_water_temperature"

        entity2 = MagicMock()
        entity2.unique_id = "neopool_mqtt_ABC123_ph_data"
        entity2.entity_id = "sensor.old_pool_ph_data"

        mock_registry = MagicMock()
        mock_registry.async_get.return_value = None  # No collision

        with (
            patch(
                "homeassistant.helpers.entity_registry.async_get",
                return_value=mock_registry,
            ),
            patch(
                "homeassistant.helpers.entity_registry.async_entries_for_config_entry",
                return_value=[entity1, entity2],
            ),
        ):
            count = await flow._regenerate_entity_ids(mock_entry, "new_pool")

        # Should regenerate both entities
        assert count == 2
        assert mock_registry.async_update_entity.call_count == 2

    async def test_regenerate_entity_ids_collision(self, mock_hass: MagicMock) -> None:
        """Test entity ID regeneration with collision."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"

        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_ABC123_water_temperature"
        entity1.entity_id = "sensor.old_pool_water_temperature"

        mock_registry = MagicMock()
        # Collision exists
        mock_registry.async_get.return_value = MagicMock()

        with (
            patch(
                "homeassistant.helpers.entity_registry.async_get",
                return_value=mock_registry,
            ),
            patch(
                "homeassistant.helpers.entity_registry.async_entries_for_config_entry",
                return_value=[entity1],
            ),
        ):
            count = await flow._regenerate_entity_ids(mock_entry, "new_pool")

        # Should not regenerate due to collision
        assert count == 0

    async def test_regenerate_entity_ids_same_id(self, mock_hass: MagicMock) -> None:
        """Test entity ID regeneration when ID is already correct."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"

        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_ABC123_water_temperature"
        entity1.entity_id = "sensor.new_pool_water_temperature"  # Already correct

        mock_registry = MagicMock()

        with (
            patch(
                "homeassistant.helpers.entity_registry.async_get",
                return_value=mock_registry,
            ),
            patch(
                "homeassistant.helpers.entity_registry.async_entries_for_config_entry",
                return_value=[entity1],
            ),
        ):
            count = await flow._regenerate_entity_ids(mock_entry, "new_pool")

        # Should not regenerate since ID is already correct
        assert count == 0


class TestAutoDetectTopicExtended:
    """Extended tests for _auto_detect_topic."""

    async def test_auto_detect_bytes_payload(self, mock_hass: MagicMock) -> None:
        """Test auto-detection with bytes payload."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        captured_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            detect_task = asyncio.create_task(flow._auto_detect_topic(timeout_seconds=5))

            await asyncio.sleep(0.1)

            # Send bytes payload
            mock_msg = MagicMock()
            mock_msg.topic = "tele/SmartPool/SENSOR"
            mock_msg.payload = b'{"NeoPool": {"Temperature": 28.5}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await detect_task

        assert result == "SmartPool"

    async def test_auto_detect_multiple_topics_first_wins(self, mock_hass: MagicMock) -> None:
        """Test auto-detection returns first valid topic."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        captured_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            detect_task = asyncio.create_task(flow._auto_detect_topic(timeout_seconds=5))

            await asyncio.sleep(0.1)

            # First NeoPool message
            mock_msg = MagicMock()
            mock_msg.topic = "tele/FirstPool/SENSOR"
            mock_msg.payload = '{"NeoPool": {"Temperature": 25.0}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await detect_task

        # Should return first discovered topic
        assert result == "FirstPool"


class TestValidateYamlTopicExtended:
    """Extended tests for _validate_yaml_topic."""

    async def test_validate_bytes_payload(self, mock_hass: MagicMock) -> None:
        """Test validation with bytes payload."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        captured_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            validate_task = asyncio.create_task(
                flow._validate_yaml_topic("SmartPool", timeout_seconds=5)
            )

            await asyncio.sleep(0.1)

            mock_msg = MagicMock()
            mock_msg.payload = b'{"NeoPool": {"Powerunit": {"NodeID": "ABC123"}}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await validate_task

        assert result["valid"] is True
        assert result["nodeid"] == "ABC123"

    async def test_validate_missing_nodeid(self, mock_hass: MagicMock) -> None:
        """Test validation when NodeID is missing."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        captured_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            validate_task = asyncio.create_task(
                flow._validate_yaml_topic("SmartPool", timeout_seconds=5)
            )

            await asyncio.sleep(0.1)

            # NeoPool payload without NodeID
            mock_msg = MagicMock()
            mock_msg.payload = '{"NeoPool": {"Temperature": 28.5}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await validate_task

        # Should still be valid but with None nodeid
        assert result["valid"] is True
        assert result["nodeid"] is None


class TestWaitForNodeidExtended:
    """Extended tests for _wait_for_nodeid."""

    async def test_wait_for_nodeid_bytes_payload(self, mock_hass: MagicMock) -> None:
        """Test waiting for NodeID with bytes payload."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        captured_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            wait_task = asyncio.create_task(flow._wait_for_nodeid("SmartPool", timeout_seconds=5))

            await asyncio.sleep(0.1)

            mock_msg = MagicMock()
            mock_msg.payload = b'{"NeoPool": {"Powerunit": {"NodeID": "BYTES123"}}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await wait_task

        assert result == "BYTES123"

    async def test_wait_for_nodeid_ignores_invalid_json(self, mock_hass: MagicMock) -> None:
        """Test waiting ignores invalid JSON and continues waiting."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        captured_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            wait_task = asyncio.create_task(flow._wait_for_nodeid("SmartPool", timeout_seconds=1))

            await asyncio.sleep(0.1)

            # Invalid JSON - should be ignored
            mock_msg = MagicMock()
            mock_msg.payload = "not json"
            if captured_callback:
                captured_callback(mock_msg)

            # Wait should timeout
            result = await wait_task

        assert result is None


class TestCheckMigratableEntities:
    """Tests for _check_migratable_entities method."""

    async def test_check_with_no_migratable_goes_to_prefix(self, mock_hass: MagicMock) -> None:
        """Test check migratable entities with none found asks for custom prefix."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._find_migratable_entities = MagicMock(return_value=[])
        # Mock _auto_detect_neopool_prefix to return no prefix (smart detection fails)
        flow._auto_detect_neopool_prefix = MagicMock(
            return_value={
                "prefix": None,
                "confidence": 0,
                "matched_signatures": [],
                "entity_count": 0,
            }
        )
        flow.async_step_yaml_prefix = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_prefix"}
        )

        result = await flow._check_migratable_entities()

        # When no migratable entities found with default prefix, asks for custom prefix
        assert result["step_id"] == "yaml_prefix"

    async def test_check_with_migratable_found(self, mock_hass: MagicMock) -> None:
        """Test check migratable entities with entities found (no active entities)."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow.context = {"source": config_entries.SOURCE_USER}

        # Create mock migratable entities
        entity1 = MagicMock()
        entity1.entity_id = "sensor.neopool_temp"
        entity1.unique_id = "neopool_mqtt_temp"

        flow._find_migratable_entities = MagicMock(return_value=[entity1])
        # Mock _find_active_entities to return empty list (entities are inactive)
        flow._find_active_entities = MagicMock(return_value=[])
        flow.async_step_yaml_confirm = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        result = await flow._check_migratable_entities()

        # Should set _migrating_entities and go to confirm (since no active entities)
        assert len(flow._migrating_entities) == 1
        assert result["step_id"] == "yaml_confirm"

    async def test_check_with_smart_detection_found(self, mock_hass: MagicMock) -> None:
        """Test check migratable entities uses smart detection when default prefix fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow.context = {"source": config_entries.SOURCE_USER}

        # Default prefix finds nothing
        flow._find_migratable_entities = MagicMock(return_value=[])

        # Smart detection finds a prefix with good confidence
        flow._auto_detect_neopool_prefix = MagicMock(
            return_value={
                "prefix": "custom_prefix_",
                "confidence": 50,
                "matched_signatures": ["hydrolysis_runtime_total", "ph_data"],
                "entity_count": 2,
            }
        )

        flow.async_step_yaml_detect_confirm = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_detect_confirm"}
        )

        result = await flow._check_migratable_entities()

        # Should go to detect confirm step
        assert result["step_id"] == "yaml_detect_confirm"
        assert flow._detected_prefix == "custom_prefix_"
        assert flow._detection_confidence == 50


class TestYamlDetectConfirmStep:
    """Tests for async_step_yaml_detect_confirm."""

    async def test_yaml_detect_confirm_shows_form(self, mock_hass: MagicMock) -> None:
        """Test yaml_detect_confirm step shows form."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}
        flow._detected_prefix = "custom_prefix_"
        flow._detection_confidence = 60
        flow._matched_signatures = ["hydrolysis_runtime_total", "ph_data"]

        result = await flow.async_step_yaml_detect_confirm(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_detect_confirm"
        assert result["description_placeholders"]["prefix"] == "custom_prefix_"
        assert result["description_placeholders"]["confidence"] == "60"

    async def test_yaml_detect_confirm_accepted(self, mock_hass: MagicMock) -> None:
        """Test yaml_detect_confirm when user confirms."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow._detected_prefix = "custom_prefix_"

        # Create mock entity
        entity1 = MagicMock()
        entity1.entity_id = "sensor.custom_temp"
        entity1.unique_id = "custom_prefix_temp"

        flow._find_migratable_entities = MagicMock(return_value=[entity1])
        flow._find_active_entities = MagicMock(return_value=[])
        flow.async_step_yaml_confirm = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        result = await flow.async_step_yaml_detect_confirm({"confirm_detection": True})

        assert result["step_id"] == "yaml_confirm"
        assert flow._unique_id_prefix == "custom_prefix_"

    async def test_yaml_detect_confirm_rejected(self, mock_hass: MagicMock) -> None:
        """Test yaml_detect_confirm when user rejects."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}
        flow._detected_prefix = "custom_prefix_"

        flow.async_step_yaml_prefix = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_prefix"}
        )

        result = await flow.async_step_yaml_detect_confirm({"confirm_detection": False})

        assert result["step_id"] == "yaml_prefix"

    async def test_yaml_detect_confirm_with_many_signatures(self, mock_hass: MagicMock) -> None:
        """Test yaml_detect_confirm shows truncated signature list."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}
        flow._detected_prefix = "custom_prefix_"
        flow._detection_confidence = 80
        # More than 5 signatures
        flow._matched_signatures = [
            "hydrolysis_runtime_total",
            "ph_data",
            "water_temperature",
            "redox_data",
            "filtration",
            "modules_ph",
            "modules_redox",
        ]

        result = await flow.async_step_yaml_detect_confirm(None)

        # Should show "and X more"
        assert "2 more" in result["description_placeholders"]["matched_signatures"]


class TestYamlPrefixStep:
    """Tests for async_step_yaml_prefix."""

    async def test_yaml_prefix_shows_form(self, mock_hass: MagicMock) -> None:
        """Test yaml_prefix step shows form."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        result = await flow.async_step_yaml_prefix(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_prefix"

    async def test_yaml_prefix_empty_prefix(self, mock_hass: MagicMock) -> None:
        """Test yaml_prefix with empty prefix."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        result = await flow.async_step_yaml_prefix({"unique_id_prefix": ""})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "no_entities_found"


class TestDiscoverDeviceFlow:
    """Tests for discover_device flow step."""

    async def test_discover_device_shows_form(self, mock_hass: MagicMock) -> None:
        """Test discover device step shows form."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        result = await flow.async_step_discover_device(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "discover_device"

    async def test_discover_device_validation_success(self, mock_hass: MagicMock) -> None:
        """Test discover device with successful validation."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_discover_device(
            {
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
            }
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "My Pool"
        assert result["data"][CONF_NODEID] == "ABC123"

    async def test_discover_device_validation_failure(self, mock_hass: MagicMock) -> None:
        """Test discover device with validation failure."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(return_value={"valid": False})

        result = await flow.async_step_discover_device(
            {
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "BadTopic",
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    async def test_discover_device_hidden_nodeid(self, mock_hass: MagicMock) -> None:
        """Test discover device with hidden NodeID triggers auto-config."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        flow._auto_configure_nodeid = AsyncMock(
            return_value={"success": True, "nodeid": "CONFIGURED123"}
        )
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_discover_device(
            {
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
            }
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_NODEID] == "CONFIGURED123"

    async def test_discover_device_auto_config_failure(self, mock_hass: MagicMock) -> None:
        """Test discover device when auto-config fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        flow._auto_configure_nodeid = AsyncMock(return_value={"success": False, "error": "Failed"})

        result = await flow.async_step_discover_device(
            {
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
            }
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "nodeid_configuration_failed"


class TestAutoDetectNeopoolPrefix:
    """Tests for _auto_detect_neopool_prefix method."""

    def test_auto_detect_neopool_prefix_found(self, mock_hass: MagicMock) -> None:
        """Test auto-detection finds NeoPool prefix."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Create mock entities with NeoPool signatures
        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_hydrolysis_runtime_total"
        entity1.platform = "mqtt"

        entity2 = MagicMock()
        entity2.unique_id = "neopool_mqtt_ph_data"
        entity2.platform = "mqtt"

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = [entity1, entity2]

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = flow._auto_detect_neopool_prefix()

        assert result["prefix"] == "neopool_mqtt_"
        assert result["confidence"] > 0
        assert len(result["matched_signatures"]) == 2

    def test_auto_detect_neopool_prefix_different_prefixes(self, mock_hass: MagicMock) -> None:
        """Test auto-detection with different prefixes only counts matching ones."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        entity1 = MagicMock()
        entity1.unique_id = "prefix_a_hydrolysis_runtime_total"
        entity1.platform = "mqtt"

        entity2 = MagicMock()
        entity2.unique_id = "prefix_b_ph_data"  # Different prefix
        entity2.platform = "mqtt"

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = [entity1, entity2]

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = flow._auto_detect_neopool_prefix()

        # Should only count entities with first detected prefix
        assert result["prefix"] == "prefix_a_"
        assert len(result["matched_signatures"]) == 1

    def test_auto_detect_neopool_prefix_no_mqtt_entities(self, mock_hass: MagicMock) -> None:
        """Test auto-detection with no MQTT entities."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        entity1 = MagicMock()
        entity1.unique_id = "some_sensor"
        entity1.platform = "other_platform"

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = [entity1]

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = flow._auto_detect_neopool_prefix()

        assert result["prefix"] is None
        assert result["confidence"] == 0

    def test_auto_detect_neopool_prefix_caps_confidence(self, mock_hass: MagicMock) -> None:
        """Test auto-detection caps confidence at 100."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Create many entities with high-weight signatures
        entities = []
        for sig in NEOPOOL_SIGNATURES:
            entity = MagicMock()
            entity.unique_id = f"neopool_mqtt_{sig}"
            entity.platform = "mqtt"
            entities.append(entity)

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = entities

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = flow._auto_detect_neopool_prefix()

        # Confidence should be capped at 100
        assert result["confidence"] <= 100


class TestOptionsFlowExtended:
    """Extended tests for NeoPoolOptionsFlow."""

    def _create_mock_config_entry(self) -> MagicMock:
        """Create a mock config entry for options flow tests."""
        entry = MagicMock()
        entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        entry.options = {}
        entry.entry_id = "test_entry_id"
        return entry

    async def test_options_flow_with_all_options(self) -> None:
        """Test options flow with all options set."""
        mock_entry = self._create_mock_config_entry()
        mock_entry.options = {
            "enable_repair_notification": True,
            "failures_threshold": 5,
            "offline_timeout": 300,
            "recovery_script": "script.pool_recovery",
        }

        flow = NeoPoolOptionsFlow()
        flow.hass = MagicMock()
        with (
            patch.object(
                type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
            ),
            patch.object(flow, "_query_setoption157", new_callable=AsyncMock, return_value=True),
        ):
            result = await flow.async_step_init(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"


class TestPerformMigrationExtended:
    """Extended tests for _perform_migration method."""

    async def test_perform_migration_collision_detected(self, mock_hass: MagicMock) -> None:
        """Test migration detects collision with existing entity."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow._nodeid = "ABC123"
        flow._unique_id_prefix = "neopool_mqtt_"

        # Entity to migrate
        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_water_temp"
        entity1.entity_id = "sensor.neopool_water_temp"

        # Existing entity with same object_id but different entity_id
        existing_entity = MagicMock()
        existing_entity.entity_id = "binary_sensor.neopool_water_temp"

        flow._migrating_entities = [entity1]

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = [entity1, existing_entity]

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = await flow._perform_migration()

        # Should detect collision and fail that entity
        assert result["entities_migrated"] == 0
        assert len(result["entities_failed"]) == 1
        assert "collision" in result["entities_failed"][0]
