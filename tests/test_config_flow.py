"""Tests for the Sugar Valley NeoPool config flow."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_RECOVERY_SCRIPT,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SAMPLE_NEOPOOL_PAYLOAD, create_mqtt_message


@pytest.fixture(name="neopool_setup", autouse=True)
def neopool_setup_fixture():
    """Mock neopool entry setup to avoid loading the full integration."""
    with patch(
        "custom_components.sugar_valley_neopool.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_form_user_starts_yaml_migration(hass: HomeAssistant) -> None:
    """Test the user config flow starts with yaml_migration step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "yaml_migration"


async def test_mqtt_discovery(hass: HomeAssistant) -> None:
    """Test MQTT discovery with valid NeoPool payload."""
    message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_confirm"

    # Confirm discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: "NeoPool SmartPool",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NeoPool SmartPool"
    # Data now includes nodeid from MQTT discovery
    assert result["data"][CONF_DEVICE_NAME] == "NeoPool SmartPool"
    assert result["data"][CONF_DISCOVERY_PREFIX] == "SmartPool"
    assert CONF_NODEID in result["data"]


async def test_mqtt_discovery_invalid_topic(hass: HomeAssistant) -> None:
    """Test MQTT discovery with invalid topic format."""
    message = create_mqtt_message("invalid/topic/format", SAMPLE_NEOPOOL_PAYLOAD)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_discovery_not_neopool(hass: HomeAssistant) -> None:
    """Test MQTT discovery with non-NeoPool payload."""
    non_neopool_payload: dict[str, Any] = {
        "Sensor": {"Temperature": 25.0},
        "Wifi": {"RSSI": -50},
    }
    message = create_mqtt_message("tele/OtherDevice/SENSOR", non_neopool_payload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_neopool_device"


async def test_mqtt_discovery_invalid_json(hass: HomeAssistant) -> None:
    """Test MQTT discovery with invalid JSON payload."""
    message = MagicMock()
    message.topic = "tele/SmartPool/SENSOR"
    message.payload = "not valid json"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_mqtt_discovery_duplicate(hass: HomeAssistant) -> None:
    """Test MQTT discovery with already configured device."""
    # First discovery
    message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_NAME: "NeoPool SmartPool"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second discovery with same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_mqtt_confirm_default_name(hass: HomeAssistant) -> None:
    """Test MQTT confirmation uses default device name."""
    message = create_mqtt_message("tele/TestPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=message,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_confirm"

    # Confirm without changing name (use default)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},  # Empty to use default
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NeoPool TestPool"  # Default name
    assert result["data"][CONF_DISCOVERY_PREFIX] == "TestPool"


async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test options flow initialization."""
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

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_reconfigure_flow_init(hass: HomeAssistant) -> None:
    """Test reconfigure flow initialization."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_flow_invalid_topic(hass: HomeAssistant) -> None:
    """Test reconfigure flow with invalid topic."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.mqtt.valid_subscribe_topic",
        side_effect=Exception("Invalid topic"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_DEVICE_NAME: "Updated Pool",
                CONF_DISCOVERY_PREFIX: "invalid#topic",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DISCOVERY_PREFIX: "invalid_topic"}


# =============================================================================
# Config Flow Version Test
# =============================================================================


async def test_config_flow_version() -> None:
    """Test that config flow version is correct."""
    assert NeoPoolConfigFlow.VERSION == 1


# =============================================================================
# Direct Unit Tests (No Integration Loading Required)
# =============================================================================
# These tests instantiate the config flow class directly and mock the hass object,
# avoiding HA's integration loading mechanism that fails in CI environments.


class TestAsyncStepUserDirect:
    """Direct tests for async_step_user without full integration loading."""

    async def test_async_step_user_redirects_to_yaml_migration(self, mock_hass: MagicMock) -> None:
        """Test user step redirects to yaml_migration step."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        result = await flow.async_step_user(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_migration"

    async def test_async_step_yaml_migration_shows_form(self, mock_hass: MagicMock) -> None:
        """Test yaml_migration step shows form."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        result = await flow.async_step_yaml_migration(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "yaml_migration"


class TestAsyncStepMqttDirect:
    """Direct tests for async_step_mqtt without full integration loading."""

    async def test_async_step_mqtt_valid_payload(self, mock_hass: MagicMock) -> None:
        """Test MQTT discovery with valid NeoPool payload."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        message = create_mqtt_message("tele/SmartPool/SENSOR", SAMPLE_NEOPOOL_PAYLOAD)

        result = await flow.async_step_mqtt(message)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mqtt_confirm"

    async def test_async_step_mqtt_invalid_topic(self, mock_hass: MagicMock) -> None:
        """Test MQTT discovery aborts with invalid topic format."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}

        message = create_mqtt_message("invalid/topic", SAMPLE_NEOPOOL_PAYLOAD)

        result = await flow.async_step_mqtt(message)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_discovery_info"

    async def test_async_step_mqtt_not_neopool(self, mock_hass: MagicMock) -> None:
        """Test MQTT discovery aborts when payload is not NeoPool."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}

        non_neopool_payload: dict[str, Any] = {
            "Sensor": {"Temperature": 25.0},
        }
        message = create_mqtt_message("tele/Device/SENSOR", non_neopool_payload)

        result = await flow.async_step_mqtt(message)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_neopool_device"

    async def test_async_step_mqtt_invalid_json(self, mock_hass: MagicMock) -> None:
        """Test MQTT discovery aborts when JSON is invalid."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}

        message = MagicMock()
        message.topic = "tele/SmartPool/SENSOR"
        message.payload = "not valid json"

        result = await flow.async_step_mqtt(message)

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "invalid_discovery_info"


class TestAsyncStepMqttConfirmDirect:
    """Direct tests for async_step_mqtt_confirm without full integration loading."""

    async def test_async_step_mqtt_confirm_shows_form(self, mock_hass: MagicMock) -> None:
        """Test MQTT confirm step shows form."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}
        flow._discovery_prefix = "SmartPool"
        flow._nodeid = "ABC123"

        result = await flow.async_step_mqtt_confirm(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mqtt_confirm"

    async def test_async_step_mqtt_confirm_creates_entry(self, mock_hass: MagicMock) -> None:
        """Test MQTT confirm creates entry."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_MQTT}
        flow._discovery_prefix = "SmartPool"
        flow._nodeid = "ABC123"
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_mqtt_confirm({CONF_DEVICE_NAME: "My NeoPool"})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "My NeoPool"
        assert result["data"][CONF_DISCOVERY_PREFIX] == "SmartPool"
        assert result["data"][CONF_NODEID] == "ABC123"


class TestAsyncStepReconfigureDirect:
    """Direct tests for async_step_reconfigure without full integration loading."""

    def _create_mock_reconfigure_entry(self) -> MagicMock:
        """Create a mock config entry for reconfigure tests."""
        entry = MagicMock()
        entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        entry.options = {}
        entry.unique_id = "ABC123"
        return entry

    async def test_async_step_reconfigure_shows_form(self, mock_hass: MagicMock) -> None:
        """Test initial reconfigure form is shown."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_reconfigure_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        result = await flow.async_step_reconfigure(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["errors"] == {}

    async def test_async_step_reconfigure_success(self, mock_hass: MagicMock) -> None:
        """Test successful reconfiguration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_RECONFIGURE}

        mock_entry = self._create_mock_reconfigure_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_mismatch = MagicMock()
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
        )
        # Mock the MQTT validation to avoid actual MQTT operations
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )

        await flow.async_step_reconfigure(
            {
                CONF_DEVICE_NAME: "New Pool Name",
                CONF_DISCOVERY_PREFIX: "NewTopic",
            }
        )

        flow.async_update_reload_and_abort.assert_called_once()


class TestOptionsFlowDirect:
    """Direct tests for NeoPoolOptionsFlow without full integration loading."""

    def _create_mock_config_entry(self) -> MagicMock:
        """Create a mock config entry for options flow tests."""
        entry = MagicMock()
        entry.data = {
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        }
        entry.options = {
            CONF_ENABLE_REPAIR_NOTIFICATION: DEFAULT_ENABLE_REPAIR_NOTIFICATION,
            CONF_FAILURES_THRESHOLD: DEFAULT_FAILURES_THRESHOLD,
            CONF_OFFLINE_TIMEOUT: DEFAULT_OFFLINE_TIMEOUT,
            CONF_RECOVERY_SCRIPT: DEFAULT_RECOVERY_SCRIPT,
        }
        entry.entry_id = "test_entry_id"
        return entry

    async def test_options_flow_shows_form(self) -> None:
        """Test initial options form is shown."""
        mock_entry = self._create_mock_config_entry()

        flow = NeoPoolOptionsFlow()
        with patch.object(
            type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
        ):
            result = await flow.async_step_init(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_saves_options(self) -> None:
        """Test options are saved correctly."""
        mock_entry = self._create_mock_config_entry()

        flow = NeoPoolOptionsFlow()
        with patch.object(
            type(flow), "config_entry", new_callable=PropertyMock, return_value=mock_entry
        ):
            result = await flow.async_step_init(
                {
                    CONF_ENABLE_REPAIR_NOTIFICATION: True,
                    CONF_FAILURES_THRESHOLD: 10,
                    CONF_OFFLINE_TIMEOUT: 300,
                    CONF_RECOVERY_SCRIPT: "script.pool_recovery",
                }
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_ENABLE_REPAIR_NOTIFICATION: True,
            CONF_FAILURES_THRESHOLD: 10,
            CONF_OFFLINE_TIMEOUT: 300,
            CONF_RECOVERY_SCRIPT: "script.pool_recovery",
        }


# =============================================================================
# Private Method Tests (MQTT Interactions)
# =============================================================================


class TestAutoDetectTopic:
    """Tests for _auto_detect_topic private method."""

    async def test_auto_detect_topic_success(self, mock_hass: MagicMock) -> None:
        """Test successful auto-detection of NeoPool topic."""
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
            # Start detection in background
            detect_task = asyncio.create_task(flow._auto_detect_topic(timeout_seconds=5))

            # Wait for subscription to be set up
            await asyncio.sleep(0.1)

            # Simulate NeoPool message
            mock_msg = MagicMock()
            mock_msg.topic = "tele/SmartPool/SENSOR"
            mock_msg.payload = '{"NeoPool": {"Temperature": 28.5}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await detect_task

        assert result == "SmartPool"

    async def test_auto_detect_topic_timeout(self, mock_hass: MagicMock) -> None:
        """Test auto-detection times out when no message received."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ):
            result = await flow._auto_detect_topic(timeout_seconds=0.1)

        assert result is None

    async def test_auto_detect_topic_ignores_non_neopool(self, mock_hass: MagicMock) -> None:
        """Test auto-detection ignores non-NeoPool messages."""
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
            detect_task = asyncio.create_task(flow._auto_detect_topic(timeout_seconds=0.5))

            await asyncio.sleep(0.1)

            # Send non-NeoPool message
            mock_msg = MagicMock()
            mock_msg.topic = "tele/OtherDevice/SENSOR"
            mock_msg.payload = '{"Sensor": {"Temperature": 25.0}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await detect_task

        assert result is None

    async def test_auto_detect_topic_handles_invalid_json(self, mock_hass: MagicMock) -> None:
        """Test auto-detection handles invalid JSON gracefully."""
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
            detect_task = asyncio.create_task(flow._auto_detect_topic(timeout_seconds=0.5))

            await asyncio.sleep(0.1)

            # Send invalid JSON
            mock_msg = MagicMock()
            mock_msg.topic = "tele/SmartPool/SENSOR"
            mock_msg.payload = "not valid json"
            if captured_callback:
                captured_callback(mock_msg)

            result = await detect_task

        assert result is None


class TestValidateYamlTopic:
    """Tests for _validate_yaml_topic private method."""

    async def test_validate_yaml_topic_success(self, mock_hass: MagicMock) -> None:
        """Test successful validation of YAML topic."""
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

            # Simulate valid NeoPool message with NodeID
            mock_msg = MagicMock()
            mock_msg.payload = (
                '{"NeoPool": {"Powerunit": {"NodeID": "ABC123"}, "Temperature": 28.5}}'
            )
            if captured_callback:
                captured_callback(mock_msg)

            result = await validate_task

        assert result["valid"] is True
        assert result["nodeid"] == "ABC123"
        assert "payload" in result

    async def test_validate_yaml_topic_timeout(self, mock_hass: MagicMock) -> None:
        """Test validation times out when no message received."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ):
            result = await flow._validate_yaml_topic("SmartPool", timeout_seconds=0.1)

        assert result["valid"] is False

    async def test_validate_yaml_topic_non_neopool(self, mock_hass: MagicMock) -> None:
        """Test validation fails for non-NeoPool payload."""
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
                flow._validate_yaml_topic("SmartPool", timeout_seconds=0.5)
            )

            await asyncio.sleep(0.1)

            # Send non-NeoPool message
            mock_msg = MagicMock()
            mock_msg.payload = '{"Sensor": {"Temperature": 25.0}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await validate_task

        assert result["valid"] is False

    async def test_validate_yaml_topic_invalid_json(self, mock_hass: MagicMock) -> None:
        """Test validation handles invalid JSON."""
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
                flow._validate_yaml_topic("SmartPool", timeout_seconds=0.5)
            )

            await asyncio.sleep(0.1)

            mock_msg = MagicMock()
            mock_msg.payload = "invalid json"
            if captured_callback:
                captured_callback(mock_msg)

            result = await validate_task

        assert result["valid"] is False


class TestAutoConfigureNodeid:
    """Tests for _auto_configure_nodeid private method."""

    async def test_auto_configure_nodeid_success(self, mock_hass: MagicMock) -> None:
        """Test successful NodeID auto-configuration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Mock _wait_for_nodeid to return valid NodeID
        flow._wait_for_nodeid = AsyncMock(return_value="ABC123")

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            result = await flow._auto_configure_nodeid("SmartPool")

        assert result["success"] is True
        assert result["nodeid"] == "ABC123"
        mock_publish.assert_called_once_with(
            mock_hass,
            "cmnd/SmartPool/SetOption157",
            "1",
            qos=1,
            retain=False,
        )

    async def test_auto_configure_nodeid_failure(self, mock_hass: MagicMock) -> None:
        """Test NodeID auto-configuration failure."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Mock _wait_for_nodeid to return None (failure)
        flow._wait_for_nodeid = AsyncMock(return_value=None)

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ):
            result = await flow._auto_configure_nodeid("SmartPool")

        assert result["success"] is False
        assert "error" in result

    async def test_auto_configure_nodeid_hidden_response(self, mock_hass: MagicMock) -> None:
        """Test NodeID auto-configuration when still hidden after command."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Mock _wait_for_nodeid to return "hidden"
        flow._wait_for_nodeid = AsyncMock(return_value="hidden")

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ):
            result = await flow._auto_configure_nodeid("SmartPool")

        assert result["success"] is False


class TestWaitForNodeid:
    """Tests for _wait_for_nodeid private method."""

    async def test_wait_for_nodeid_success(self, mock_hass: MagicMock) -> None:
        """Test successful waiting for NodeID."""
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

            # Simulate message with valid NodeID
            mock_msg = MagicMock()
            mock_msg.payload = '{"NeoPool": {"Powerunit": {"NodeID": "XYZ789"}}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await wait_task

        assert result == "XYZ789"

    async def test_wait_for_nodeid_timeout(self, mock_hass: MagicMock) -> None:
        """Test waiting for NodeID times out."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ):
            result = await flow._wait_for_nodeid("SmartPool", timeout_seconds=0.1)

        assert result is None

    async def test_wait_for_nodeid_ignores_hidden(self, mock_hass: MagicMock) -> None:
        """Test waiting ignores hidden NodeID values."""
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
            wait_task = asyncio.create_task(flow._wait_for_nodeid("SmartPool", timeout_seconds=0.5))

            await asyncio.sleep(0.1)

            # Send message with hidden NodeID
            mock_msg = MagicMock()
            mock_msg.payload = '{"NeoPool": {"Powerunit": {"NodeID": "hidden"}}}'
            if captured_callback:
                captured_callback(mock_msg)

            result = await wait_task

        assert result is None


class TestYamlMigrationFlow:
    """Tests for YAML migration flow steps."""

    async def test_yaml_migration_not_selected(self, mock_hass: MagicMock) -> None:
        """Test when user doesn't select YAML migration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        # Mock discover_device step
        flow.async_step_discover_device = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "discover_device"}
        )

        result = await flow.async_step_yaml_migration({"migrate_yaml": False})

        assert result["step_id"] == "discover_device"
        flow.async_step_discover_device.assert_called_once()

    async def test_yaml_migration_selected(self, mock_hass: MagicMock) -> None:
        """Test when user selects YAML migration."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        # Mock yaml_detect step
        flow.async_step_yaml_detect = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_detect"}
        )

        await flow.async_step_yaml_migration({"migrate_yaml": True})

        assert flow._migrate_yaml is True
        flow.async_step_yaml_detect.assert_called_once()

    async def test_yaml_detect_auto_detection_success(self, mock_hass: MagicMock) -> None:
        """Test YAML detect with successful auto-detection."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        # Mock methods
        flow._auto_detect_topic = AsyncMock(return_value="SmartPool")
        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )
        flow._check_orphaned_entities = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        await flow.async_step_yaml_detect()

        assert flow._yaml_topic == "SmartPool"
        assert flow._nodeid == "ABC123"
        flow._check_orphaned_entities.assert_called_once()

    async def test_yaml_detect_auto_detection_fails(self, mock_hass: MagicMock) -> None:
        """Test YAML detect falls back to manual when auto-detection fails."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._auto_detect_topic = AsyncMock(return_value=None)
        flow.async_step_yaml_topic = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_topic"}
        )

        await flow.async_step_yaml_detect()

        flow.async_step_yaml_topic.assert_called_once()

    async def test_yaml_topic_validation_success(self, mock_hass: MagicMock) -> None:
        """Test YAML topic step with successful validation."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(
            return_value={"valid": True, "nodeid": "ABC123", "payload": {}}
        )
        flow._check_orphaned_entities = AsyncMock(
            return_value={"type": FlowResultType.FORM, "step_id": "yaml_confirm"}
        )

        await flow.async_step_yaml_topic({"yaml_topic": "TestPool"})

        assert flow._yaml_topic == "TestPool"
        assert flow._nodeid == "ABC123"

    async def test_yaml_topic_validation_failure(self, mock_hass: MagicMock) -> None:
        """Test YAML topic step with validation failure."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}

        flow._validate_yaml_topic = AsyncMock(return_value={"valid": False})

        result = await flow.async_step_yaml_topic({"yaml_topic": "BadTopic"})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    async def test_yaml_confirm_without_checkbox(self, mock_hass: MagicMock) -> None:
        """Test YAML confirm requires checkbox."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow._migrating_entities = []

        result = await flow.async_step_yaml_confirm({"confirm_migration": False})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "confirmation_required"

    async def test_yaml_confirm_creates_entry(self, mock_hass: MagicMock) -> None:
        """Test YAML confirm creates entry when checkbox checked."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": config_entries.SOURCE_USER}
        flow._yaml_topic = "SmartPool"
        flow._nodeid = "ABC123"
        flow._unique_id_prefix = "neopool_mqtt_"
        flow._migrating_entities = []
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_yaml_confirm({"confirm_migration": True})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["nodeid"] == "ABC123"
        assert result["data"]["migrate_yaml"] is True


class TestFindOrphanedEntities:
    """Tests for _find_orphaned_entities and related methods."""

    def test_find_orphaned_entities_with_matches(self, mock_hass: MagicMock) -> None:
        """Test finding orphaned entities with matching prefix."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        # Create mock entities
        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_water_temperature"
        entity1.config_entry_id = None
        entity1.entity_id = "sensor.neopool_water_temperature"

        entity2 = MagicMock()
        entity2.unique_id = "neopool_mqtt_ph_data"
        entity2.config_entry_id = None
        entity2.entity_id = "sensor.neopool_ph"

        entity3 = MagicMock()
        entity3.unique_id = "other_entity"
        entity3.config_entry_id = None
        entity3.entity_id = "sensor.other"

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = [entity1, entity2, entity3]

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = flow._find_orphaned_entities("neopool_mqtt_")

        assert len(result) == 2
        assert entity1 in result
        assert entity2 in result

    def test_find_orphaned_entities_excludes_configured(self, mock_hass: MagicMock) -> None:
        """Test that entities with config_entry_id are excluded."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        entity1 = MagicMock()
        entity1.unique_id = "neopool_mqtt_temp"
        entity1.config_entry_id = "existing_entry"  # Already configured

        mock_registry = MagicMock()
        mock_registry.entities.values.return_value = [entity1]

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            result = flow._find_orphaned_entities("neopool_mqtt_")

        assert len(result) == 0

    def test_format_entity_list_few_entities(self, mock_hass: MagicMock) -> None:
        """Test formatting entity list with few entities."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        entities = []
        for i in range(3):
            entity = MagicMock()
            entity.entity_id = f"sensor.entity_{i}"
            entities.append(entity)

        result = flow._format_entity_list(entities)

        assert "sensor.entity_0" in result
        assert "sensor.entity_1" in result
        assert "sensor.entity_2" in result
        assert "more" not in result

    def test_format_entity_list_many_entities(self, mock_hass: MagicMock) -> None:
        """Test formatting entity list with many entities."""
        flow = NeoPoolConfigFlow()
        flow.hass = mock_hass

        entities = []
        for i in range(10):
            entity = MagicMock()
            entity.entity_id = f"sensor.entity_{i}"
            entities.append(entity)

        result = flow._format_entity_list(entities)

        # Should show first 5
        assert "sensor.entity_0" in result
        assert "sensor.entity_4" in result
        # Should not show beyond 5
        assert "sensor.entity_5" not in result
        # Should show "and X more"
        assert "5 more" in result


class TestGetTopicsFromConfig:
    """Tests for get_topics_from_config function."""

    def test_get_topics_from_config(self, hass: HomeAssistant) -> None:
        """Test getting configured topics."""
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "Pool1"},
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "Pool2"},
        )
        entry2.add_to_hass(hass)

        topics = get_topics_from_config(hass)

        assert "Pool1" in topics
        assert "Pool2" in topics
