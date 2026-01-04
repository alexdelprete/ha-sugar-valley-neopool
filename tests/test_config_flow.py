"""Tests for the Sugar Valley NeoPool config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool.config_flow import NeoPoolConfigFlow, NeoPoolOptionsFlow
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
    assert result["errors"] == {}


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


async def test_options_flow_update(hass: HomeAssistant) -> None:
    """Test options flow updates options."""
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

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENABLE_REPAIR_NOTIFICATION: True,
            CONF_FAILURES_THRESHOLD: 5,
            CONF_OFFLINE_TIMEOUT: 120,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ENABLE_REPAIR_NOTIFICATION] is True
    assert entry.options[CONF_FAILURES_THRESHOLD] == 5
    assert entry.options[CONF_OFFLINE_TIMEOUT] == 120


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
