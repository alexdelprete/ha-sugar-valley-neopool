"""Extended tests for Sugar Valley NeoPool config flow - edge cases."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.sugar_valley_neopool.config_flow import NeoPoolConfigFlow
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
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

        flow._check_orphaned_entities = AsyncMock(
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
        flow._check_orphaned_entities = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        await flow.async_step_yaml_detect()

        assert flow._nodeid == "AUTOCONFIG123"


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
        entry.unique_id = "ABC123"
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

        # Mock async_update_reload_and_abort
        flow.async_update_reload_and_abort = AsyncMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        # Should successfully reconfigure
        flow.async_update_reload_and_abort.assert_called_once()


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


class TestCheckOrphanedEntities:
    """Tests for _check_orphaned_entities method."""

    async def test_check_with_no_orphans_goes_to_prefix(self, mock_hass: MagicMock) -> None:
        """Test check orphaned entities with no orphans asks for custom prefix."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._find_orphaned_entities = MagicMock(return_value=[])
        flow.async_step_yaml_prefix = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_prefix"}
        )

        result = await flow._check_orphaned_entities()

        # When no orphans found with default prefix, asks user for custom prefix
        assert result["step_id"] == "yaml_prefix"

    async def test_check_with_orphans_found(self, mock_hass: MagicMock) -> None:
        """Test check orphaned entities with orphans found."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow.context = {"source": config_entries.SOURCE_USER}

        # Create mock orphaned entities
        entity1 = MagicMock()
        entity1.entity_id = "sensor.neopool_temp"
        entity1.unique_id = "neopool_mqtt_temp"

        flow._find_orphaned_entities = MagicMock(return_value=[entity1])
        flow.async_step_yaml_confirm = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        result = await flow._check_orphaned_entities()

        # Should set _migrating_entities and go to confirm
        assert len(flow._migrating_entities) == 1
        assert result["step_id"] == "yaml_confirm"


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
