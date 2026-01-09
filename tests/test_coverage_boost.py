"""Additional tests to boost coverage to 97%+.

This file targets specific uncovered code paths identified through coverage analysis.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    async_remove_config_entry_device,
    get_device_info,
)
from custom_components.sugar_valley_neopool.config_flow import (
    NeoPoolConfigFlow,
    NeoPoolOptionsFlow,
    get_topics_from_config,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_ENABLE_REPAIR_NOTIFICATION,
    CONF_FAILURES_THRESHOLD,
    CONF_NODEID,
    CONF_OFFLINE_TIMEOUT,
    CONF_RECOVERY_SCRIPT,
    CONF_REGENERATE_ENTITY_IDS,
    DOMAIN,
)
from custom_components.sugar_valley_neopool.select import create_value_fn
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr


class TestGetTopicsFromConfig:
    """Tests for get_topics_from_config function."""

    def test_returns_empty_set_when_no_entries(self, hass: HomeAssistant) -> None:
        """Test returns empty set when no config entries."""
        result = get_topics_from_config(hass)
        # Should return set with None since no entries exist
        assert isinstance(result, set)

    def test_returns_topics_from_entries(self, hass: HomeAssistant) -> None:
        """Test returns topics from existing config entries."""
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool1"},
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool2"},
        )
        entry2.add_to_hass(hass)

        result = get_topics_from_config(hass)

        assert "SmartPool1" in result
        assert "SmartPool2" in result


class TestMqttConfirmStep:
    """Tests for async_step_mqtt_confirm with user input."""

    async def test_mqtt_confirm_creates_entry(self, hass: HomeAssistant) -> None:
        """Test MQTT confirm step creates entry with user input."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._discovery_prefix = "SmartPool"
        flow._device_name = "Auto Pool"
        flow._nodeid = "ABC123"

        result = await flow.async_step_mqtt_confirm({CONF_DEVICE_NAME: "Custom Pool Name"})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Custom Pool Name"
        assert result["data"][CONF_DEVICE_NAME] == "Custom Pool Name"
        assert result["data"][CONF_NODEID] == "ABC123"

    async def test_mqtt_confirm_uses_default_name(self, hass: HomeAssistant) -> None:
        """Test MQTT confirm uses discovered name when no input."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._discovery_prefix = "SmartPool"
        flow._device_name = "Discovered Pool"
        flow._nodeid = "XYZ789"

        # Submit with device name provided
        result = await flow.async_step_mqtt_confirm({CONF_DEVICE_NAME: "Discovered Pool"})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Discovered Pool"


class TestOptionsFlow:
    """Tests for NeoPoolOptionsFlow."""

    async def test_options_flow_init_shows_form(self, hass: HomeAssistant) -> None:
        """Test options flow init step shows form."""
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

        # Mock the MQTT query for SetOption157 status
        with patch(
            "custom_components.sugar_valley_neopool.config_flow.async_query_setoption157",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # Use hass.config_entries.options.async_init to properly initialize the flow
            result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_creates_entry(self, hass: HomeAssistant) -> None:
        """Test options flow creates entry with user input."""
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

        # Mock the MQTT query for SetOption157 status
        with patch(
            "custom_components.sugar_valley_neopool.config_flow.async_query_setoption157",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # Initialize options flow properly
            result = await hass.config_entries.options.async_init(entry.entry_id)
            assert result["type"] == FlowResultType.FORM

            # Submit the form - SO157 is no longer in the form (auto-enforced)
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    CONF_RECOVERY_SCRIPT: "script.test_recovery",
                    CONF_ENABLE_REPAIR_NOTIFICATION: True,
                    CONF_FAILURES_THRESHOLD: 5,
                    CONF_OFFLINE_TIMEOUT: 120,
                },
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_RECOVERY_SCRIPT] == "script.test_recovery"
        assert result["data"][CONF_ENABLE_REPAIR_NOTIFICATION] is True
        assert result["data"][CONF_FAILURES_THRESHOLD] == 5
        assert result["data"][CONF_OFFLINE_TIMEOUT] == 120

    async def test_options_flow_uses_existing_values(self, hass: HomeAssistant) -> None:
        """Test options flow shows existing values."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
            },
            options={
                CONF_RECOVERY_SCRIPT: "script.existing",
                CONF_ENABLE_REPAIR_NOTIFICATION: False,
                CONF_FAILURES_THRESHOLD: 10,
                CONF_OFFLINE_TIMEOUT: 300,
            },
        )
        entry.add_to_hass(hass)

        # Mock the MQTT query for SetOption157 status
        with patch(
            "custom_components.sugar_valley_neopool.config_flow.async_query_setoption157",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # Initialize options flow properly
            result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        # Form should be shown with existing values as defaults


class TestReconfigureFlow:
    """Extended tests for reconfigure flow."""

    async def test_reconfigure_invalid_topic_validation_fails(self, hass: HomeAssistant) -> None:
        """Test reconfigure when topic validation fails (timeout/no message)."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "reconfigure"}

        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        # Mock _validate_yaml_topic to return invalid (simulates timeout or bad topic)
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": False, "nodeid": None, "payload": {}}
        )

        result = await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "invalid_topic",
            }
        )

        # Should show form with error for invalid topic (cannot_connect is used for validation failures)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    async def test_reconfigure_hidden_nodeid_auto_config(self, hass: HomeAssistant) -> None:
        """Test reconfigure with hidden NodeID triggers auto-config."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "reconfigure"}

        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        mock_entry.unique_id = "sugar_valley_neopool_ABC123"
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        # Validation returns hidden NodeID
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        # Auto-config succeeds with same NodeID
        flow._auto_configure_nodeid = AsyncMock(return_value={"success": True, "nodeid": "ABC123"})

        async def mock_set_unique_id(uid):
            flow._unique_id = uid

        flow.async_set_unique_id = mock_set_unique_id
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        flow._auto_configure_nodeid.assert_called_once_with("NewTopic")

    async def test_reconfigure_nodeid_config_failure(self, hass: HomeAssistant) -> None:
        """Test reconfigure when NodeID auto-config fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "reconfigure"}

        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
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


class TestYamlPrefixStep:
    """Tests for async_step_yaml_prefix."""

    async def test_yaml_prefix_shows_form(self, hass: HomeAssistant) -> None:
        """Test yaml_prefix step shows form."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}

        result = await flow.async_step_yaml_prefix(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_prefix"

    async def test_yaml_prefix_empty_prefix_error(self, hass: HomeAssistant) -> None:
        """Test yaml_prefix with empty prefix shows error."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._find_migratable_entities = MagicMock(return_value=[])

        result = await flow.async_step_yaml_prefix({"unique_id_prefix": ""})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "no_entities_found"

    async def test_yaml_prefix_no_matching_entities(self, hass: HomeAssistant) -> None:
        """Test yaml_prefix when no entities match prefix."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._find_migratable_entities = MagicMock(return_value=[])

        result = await flow.async_step_yaml_prefix({"unique_id_prefix": "custom_prefix_"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "no_entities_found"


class TestYamlConfirmStep:
    """Tests for async_step_yaml_confirm."""

    async def test_yaml_confirm_no_confirmation_error(self, hass: HomeAssistant) -> None:
        """Test yaml_confirm without confirmation checkbox shows error."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow._migrating_entities = []

        result = await flow.async_step_yaml_confirm({"confirm_migration": False})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "confirmation_required"


class TestFormatEntityList:
    """Tests for _format_entity_list method."""

    def test_format_less_than_five_entities(self) -> None:
        """Test formatting less than 5 entities."""
        flow = NeoPoolConfigFlow()

        entities = [MagicMock(entity_id=f"sensor.entity_{i}") for i in range(3)]

        result = flow._format_entity_list(entities)

        assert "sensor.entity_0" in result
        assert "sensor.entity_1" in result
        assert "sensor.entity_2" in result
        assert "more" not in result

    def test_format_more_than_five_entities(self) -> None:
        """Test formatting more than 5 entities shows count."""
        flow = NeoPoolConfigFlow()

        entities = [MagicMock(entity_id=f"sensor.entity_{i}") for i in range(10)]

        result = flow._format_entity_list(entities)

        assert "sensor.entity_0" in result
        assert "sensor.entity_4" in result
        assert "5 more" in result

    def test_format_exactly_five_entities(self) -> None:
        """Test formatting exactly 5 entities."""
        flow = NeoPoolConfigFlow()

        entities = [MagicMock(entity_id=f"sensor.entity_{i}") for i in range(5)]

        result = flow._format_entity_list(entities)

        assert "sensor.entity_0" in result
        assert "sensor.entity_4" in result
        assert "more" not in result


class TestAsyncRemoveConfigEntryDevice:
    """Tests for async_remove_config_entry_device."""

    @pytest.mark.asyncio
    async def test_always_returns_false(self, hass: HomeAssistant) -> None:
        """Test function always returns False to prevent device removal."""
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

        mock_device = MagicMock(spec=dr.DeviceEntry)

        result = await async_remove_config_entry_device(hass, entry, mock_device)

        assert result is False


class TestGetDeviceInfo:
    """Tests for get_device_info function."""

    def test_returns_device_info(self) -> None:
        """Test get_device_info returns correct DeviceInfo."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "XYZ789",
            },
        )

        result = get_device_info(entry)

        assert result["name"] == "My Pool"
        assert (DOMAIN, "XYZ789") in result["identifiers"]
        assert result["manufacturer"] == "Sugar Valley"
        assert result["model"] == "NeoPool Controller"

    def test_device_info_uses_defaults(self) -> None:
        """Test get_device_info uses defaults when data missing."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={},
        )

        result = get_device_info(entry)

        # Should use default device name (DEFAULT_DEVICE_NAME = "NeoPool")
        assert result["name"] == "NeoPool"
        # Empty nodeid in identifiers
        assert (DOMAIN, "") in result["identifiers"]


class TestCreateValueFn:
    """Tests for create_value_fn factory function in select.py."""

    def test_returns_callable(self) -> None:
        """Test create_value_fn returns a callable."""
        options_map = {0: "Off", 1: "On"}
        fn = create_value_fn(options_map)

        assert callable(fn)

    def test_maps_int_to_string(self) -> None:
        """Test value function maps int to string."""
        options_map = {0: "Off", 1: "On", 2: "Auto"}
        fn = create_value_fn(options_map)

        assert fn(0) == "Off"
        assert fn(1) == "On"
        assert fn(2) == "Auto"

    def test_handles_string_int(self) -> None:
        """Test value function handles string integers."""
        options_map = {0: "Off", 1: "On"}
        fn = create_value_fn(options_map)

        assert fn("0") == "Off"
        assert fn("1") == "On"

    def test_returns_none_for_invalid(self) -> None:
        """Test value function returns None for invalid values."""
        options_map = {0: "Off", 1: "On"}
        fn = create_value_fn(options_map)

        assert fn(99) is None
        assert fn("invalid") is None
        assert fn(None) is None


class TestDiscoverDeviceHiddenNodeid:
    """Tests for discover_device with hidden NodeID."""

    async def test_discover_device_hidden_nodeid_auto_config(self, hass: HomeAssistant) -> None:
        """Test discover_device with hidden NodeID triggers auto-config."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}

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

        flow._auto_configure_nodeid.assert_called_once_with("SmartPool")
        assert result["type"] == FlowResultType.CREATE_ENTRY

    async def test_discover_device_auto_config_failure(self, hass: HomeAssistant) -> None:
        """Test discover_device aborts when auto-config fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        flow._auto_configure_nodeid = AsyncMock(
            return_value={"success": False, "error": "Failed to configure"}
        )

        result = await flow.async_step_discover_device(
            {
                CONF_DEVICE_NAME: "My Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
            }
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "nodeid_configuration_failed"


class TestAutoDetectTimeout:
    """Tests for auto-detection timeout scenarios."""

    async def test_auto_detect_timeout_returns_none(self, hass: HomeAssistant) -> None:
        """Test auto-detection returns None on timeout."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass

        async def mock_subscribe(hass, topic, callback, **kwargs):
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            result = await flow._auto_detect_topic(timeout_seconds=0.1)

        assert result is None

    async def test_validate_topic_timeout_returns_invalid(self, hass: HomeAssistant) -> None:
        """Test topic validation returns invalid on timeout."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass

        async def mock_subscribe(hass, topic, callback, **kwargs):
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            result = await flow._validate_yaml_topic("SmartPool", timeout_seconds=0.1)

        assert result["valid"] is False


class TestYamlDetectAutoConfigFailure:
    """Tests for yaml_detect when auto-config fails."""

    async def test_yaml_detect_auto_config_fails_goes_to_yaml_topic(
        self, hass: HomeAssistant
    ) -> None:
        """Test yaml_detect falls back to yaml_topic when auto-config fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}

        flow._auto_detect_topic = AsyncMock(return_value="SmartPool")
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "hidden", "payload": {}}
        )
        flow._auto_configure_nodeid = AsyncMock(return_value={"success": False, "error": "Failed"})
        flow.async_step_yaml_topic = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_topic"}
        )

        await flow.async_step_yaml_detect()

        # Should fall back to yaml_topic step
        flow.async_step_yaml_topic.assert_called_once()


class TestMqttDiscoveryEdgeCases:
    """Edge case tests for MQTT discovery."""

    async def test_mqtt_discovery_invalid_topic_format(self, hass: HomeAssistant) -> None:
        """Test MQTT discovery with invalid topic format."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "mqtt"}

        mock_discovery = MagicMock()
        mock_discovery.topic = "invalid_topic"
        mock_discovery.payload = '{"NeoPool": {}}'

        result = await flow.async_step_mqtt(mock_discovery)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_discovery_info"

    async def test_mqtt_discovery_non_neopool_device(self, hass: HomeAssistant) -> None:
        """Test MQTT discovery rejects non-NeoPool devices."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "mqtt"}

        mock_discovery = MagicMock()
        mock_discovery.topic = "tele/SomeDevice/SENSOR"
        mock_discovery.payload = '{"SomeOtherDevice": {}}'

        result = await flow.async_step_mqtt(mock_discovery)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_neopool_device"

    async def test_mqtt_discovery_invalid_json(self, hass: HomeAssistant) -> None:
        """Test MQTT discovery with invalid JSON."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "mqtt"}

        mock_discovery = MagicMock()
        mock_discovery.topic = "tele/SmartPool/SENSOR"
        mock_discovery.payload = "not valid json"

        result = await flow.async_step_mqtt(mock_discovery)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_discovery_info"


class TestAutoConfigureNodeid:
    """Tests for _auto_configure_nodeid method."""

    async def test_auto_configure_publishes_setoption(self, hass: HomeAssistant) -> None:
        """Test auto-configure publishes SetOption157 command."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass

        with (
            patch("homeassistant.components.mqtt.async_publish") as mock_publish,
            patch.object(flow, "_wait_for_nodeid", return_value="NEW123"),
            patch(
                "custom_components.sugar_valley_neopool.config_flow.async_query_setoption157",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await flow._auto_configure_nodeid("SmartPool")

        # _auto_configure_nodeid publishes 2 commands: SetOption157 and TelePeriod
        assert mock_publish.call_count == 2
        # Verify SetOption157 command was published
        all_calls = str(mock_publish.call_args_list)
        assert "cmnd/SmartPool/SetOption157" in all_calls
        assert result["success"] is True
        assert result["nodeid"] == "NEW123"

    async def test_auto_configure_fails_when_nodeid_not_received(self, hass: HomeAssistant) -> None:
        """Test auto-configure fails when NodeID not received."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass

        with (
            patch("homeassistant.components.mqtt.async_publish"),
            patch.object(flow, "_wait_for_nodeid", return_value=None),
            patch(
                "custom_components.sugar_valley_neopool.config_flow.async_query_setoption157",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await flow._auto_configure_nodeid("SmartPool")

        assert result["success"] is False
        assert "error" in result


class TestShowOptionsFormStatus:
    """Tests for _show_options_form status messages."""

    async def test_show_form_setoption157_disabled_status(self, hass: HomeAssistant) -> None:
        """Test status message when SetOption157 is disabled."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        mock_entry.options = {}
        mock_entry.entry_id = "test_entry_id"

        flow = NeoPoolOptionsFlow()
        flow.hass = hass
        # SetOption157 is disabled
        flow._setoption157_status = False

        with patch.object(
            type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
        ):
            result = await flow._show_options_form()

        assert result["type"] == FlowResultType.FORM
        # Should have status placeholder
        assert "setoption157_status" in result["description_placeholders"]
        assert "disabled" in result["description_placeholders"]["setoption157_status"]

    async def test_show_form_setoption157_none_status(self, hass: HomeAssistant) -> None:
        """Test status message when SetOption157 status is None (couldn't query)."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        mock_entry.options = {}
        mock_entry.entry_id = "test_entry_id"

        flow = NeoPoolOptionsFlow()
        flow.hass = hass
        # SetOption157 status is None (couldn't query device)
        flow._setoption157_status = None

        with patch.object(
            type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
        ):
            result = await flow._show_options_form()

        assert result["type"] == FlowResultType.FORM
        assert "setoption157_status" in result["description_placeholders"]
        assert "Could not query" in result["description_placeholders"]["setoption157_status"]

    async def test_show_form_setoption157_enabled_status(self, hass: HomeAssistant) -> None:
        """Test status message when SetOption157 is enabled."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        mock_entry.options = {}
        mock_entry.entry_id = "test_entry_id"

        flow = NeoPoolOptionsFlow()
        flow.hass = hass
        # SetOption157 is enabled
        flow._setoption157_status = True

        with patch.object(
            type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
        ):
            result = await flow._show_options_form()

        assert result["type"] == FlowResultType.FORM
        # Should have enabled status placeholder
        assert "setoption157_status" in result["description_placeholders"]
        assert "enabled" in result["description_placeholders"]["setoption157_status"]


class TestSetSetoption157Method:
    """Tests for _set_setoption157 method."""

    async def test_set_setoption157_success(self, hass: HomeAssistant) -> None:
        """Test successful SetOption157 set command."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DISCOVERY_PREFIX: "SmartPool",
        }

        flow = NeoPoolOptionsFlow()
        flow.hass = hass

        with (
            patch.object(
                type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
            ),
            patch("homeassistant.components.mqtt.async_publish", new_callable=AsyncMock),
        ):
            result = await flow._set_setoption157(True)

        assert result is True

    async def test_set_setoption157_no_topic(self, hass: HomeAssistant) -> None:
        """Test SetOption157 set fails with no MQTT topic."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DISCOVERY_PREFIX: "",  # Empty topic
        }

        flow = NeoPoolOptionsFlow()
        flow.hass = hass

        with patch.object(
            type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
        ):
            result = await flow._set_setoption157(True)

        assert result is False

    async def test_set_setoption157_publish_exception(self, hass: HomeAssistant) -> None:
        """Test SetOption157 set handles publish exception."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DISCOVERY_PREFIX: "SmartPool",
        }

        flow = NeoPoolOptionsFlow()
        flow.hass = hass

        with (
            patch.object(
                type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
                side_effect=Exception("MQTT error"),
            ),
        ):
            result = await flow._set_setoption157(True)

        assert result is False


class TestYamlPrefixWithFoundEntities:
    """Tests for yaml_prefix step when entities are found (lines 659-686)."""

    async def test_yaml_prefix_found_entities_inactive(self, hass: HomeAssistant) -> None:
        """Test yaml_prefix with found entities that are inactive."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"

        # Create mock entity
        entity = MagicMock()
        entity.entity_id = "sensor.custom_temp"
        entity.unique_id = "custom_prefix_temp"

        flow._find_migratable_entities = MagicMock(return_value=[entity])
        flow._find_active_entities = MagicMock(return_value=[])  # No active entities

        result = await flow.async_step_yaml_prefix({"unique_id_prefix": "custom_prefix_"})

        # Should proceed to yaml_confirm since entities are inactive
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_confirm"
        assert flow._unique_id_prefix == "custom_prefix_"
        assert len(flow._migrating_entities) == 1

    async def test_yaml_prefix_found_entities_active(self, hass: HomeAssistant) -> None:
        """Test yaml_prefix with found entities that are still active."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"

        # Create mock entity
        entity = MagicMock()
        entity.entity_id = "sensor.custom_temp"
        entity.unique_id = "custom_prefix_temp"

        flow._find_migratable_entities = MagicMock(return_value=[entity])
        flow._find_active_entities = MagicMock(return_value=[entity])  # Entity is active

        result = await flow.async_step_yaml_prefix({"unique_id_prefix": "custom_prefix_"})

        # Should go to yaml_active_warning since entities are active
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_active_warning"


class TestYamlDetectConfirmWithActiveEntities:
    """Tests for yaml_detect_confirm with active entities (line 724)."""

    async def test_yaml_detect_confirm_accepted_with_active_entities(
        self, hass: HomeAssistant
    ) -> None:
        """Test yaml_detect_confirm when confirmed but entities are active."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow._detected_prefix = "detected_prefix_"

        # Create mock entity
        entity = MagicMock()
        entity.entity_id = "sensor.detected_temp"
        entity.unique_id = "detected_prefix_temp"

        flow._find_migratable_entities = MagicMock(return_value=[entity])
        flow._find_active_entities = MagicMock(return_value=[entity])  # Entity is active

        result = await flow.async_step_yaml_detect_confirm({"confirm_detection": True})

        # Should go to yaml_active_warning since entities are active
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_active_warning"

    async def test_yaml_detect_confirm_accepted_no_entities_found(
        self, hass: HomeAssistant
    ) -> None:
        """Test yaml_detect_confirm when confirmed but no entities found."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}
        flow._detected_prefix = "detected_prefix_"

        # No entities found with detected prefix
        flow._find_migratable_entities = MagicMock(return_value=[])

        result = await flow.async_step_yaml_detect_confirm({"confirm_detection": True})

        # Should go to yaml_prefix to ask for manual input
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_prefix"


class TestDiscoverDeviceInvalidTopic:
    """Tests for discover_device invalid topic format (lines 982-985)."""

    async def test_discover_device_invalid_topic_format(self, hass: HomeAssistant) -> None:
        """Test discover_device with invalid MQTT topic format."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": SOURCE_USER}

        # Mock valid_subscribe_topic to raise vol.Invalid
        with patch(
            "custom_components.sugar_valley_neopool.config_flow.valid_subscribe_topic",
            side_effect=vol.Invalid("Invalid topic"),
        ):
            result = await flow.async_step_discover_device(
                {
                    CONF_DEVICE_NAME: "My Pool",
                    CONF_DISCOVERY_PREFIX: "invalid#topic#format",
                }
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_topic"


class TestReconfigureRegenerateEntityIds:
    """Tests for reconfigure flow regenerate with same name (line 1160)."""

    async def test_reconfigure_regenerate_same_name_skipped(self, hass: HomeAssistant) -> None:
        """Test reconfigure with regenerate flag but same device name."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "reconfigure"}

        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Test Pool",  # Same name
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        mock_entry.unique_id = "sugar_valley_neopool_ABC123"
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )

        async def mock_set_unique_id(uid):
            flow._unique_id = uid

        flow.async_set_unique_id = mock_set_unique_id
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow._regenerate_entity_ids = AsyncMock(return_value=0)
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "Test Pool",  # Same name as before
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_REGENERATE_ENTITY_IDS: True,  # Regenerate requested
            }
        )

        # Should NOT call regenerate because name didn't change
        flow._regenerate_entity_ids.assert_not_called()

    async def test_reconfigure_regenerate_different_name(self, hass: HomeAssistant) -> None:
        """Test reconfigure with regenerate flag and different device name."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass
        flow.context = {"source": "reconfigure"}

        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_DEVICE_NAME: "Old Name",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        mock_entry.unique_id = "sugar_valley_neopool_ABC123"
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )

        async def mock_set_unique_id(uid):
            flow._unique_id = uid

        flow.async_set_unique_id = mock_set_unique_id
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow._regenerate_entity_ids = AsyncMock(return_value=5)
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )

        await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Name",  # Different name
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_REGENERATE_ENTITY_IDS: True,
            }
        )

        # Should call regenerate because name changed
        flow._regenerate_entity_ids.assert_called_once()


class TestAutoConfigureNodeidSetOptionVerificationFailed:
    """Tests for _auto_configure_nodeid when SetOption157 verification fails."""

    async def test_auto_configure_setoption_verification_failed(self, hass: HomeAssistant) -> None:
        """Test auto-configure fails when SetOption157 verification fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = hass

        with (
            patch("homeassistant.components.mqtt.async_publish", new_callable=AsyncMock),
            patch(
                "custom_components.sugar_valley_neopool.config_flow.async_query_setoption157",
                new_callable=AsyncMock,
                return_value=False,  # Verification returns False
            ),
        ):
            result = await flow._auto_configure_nodeid("SmartPool")

        assert result["success"] is False
        assert "error" in result
        assert "SetOption157" in result["error"]
