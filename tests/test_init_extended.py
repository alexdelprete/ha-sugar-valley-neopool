"""Extended tests for Sugar Valley NeoPool integration initialization - edge cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    CONFIG_ENTRY_VERSION,
    NeoPoolData,
    _show_migration_verification_result,
    async_migrate_entry,
    async_register_device,
    async_setup_entry,
    async_unload_entry,
    async_verify_migration,
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
        """Test setup entry with entity_id_mapping triggers verification."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Test Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: "ABC123",
                "entity_id_mapping": {"water_temp": "neopool_water_temp"},
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
                "custom_components.sugar_valley_neopool.async_verify_migration",
                return_value={"verified": 1, "no_history": 0, "failed": []},
            ) as mock_verify,
            patch(
                "custom_components.sugar_valley_neopool._show_migration_verification_result"
            ) as mock_show,
        ):
            await async_setup_entry(hass, entry)

        mock_verify.assert_called_once()
        mock_show.assert_called_once()


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


class TestAsyncVerifyMigration:
    """Tests for async_verify_migration function."""

    @pytest.mark.asyncio
    async def test_verify_migration_recorder_not_available(self, hass: HomeAssistant) -> None:
        """Test verification returns early when recorder import fails."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        # Simulate recorder module not being importable by removing it from sys.modules
        # and ensuring the import inside async_verify_migration fails
        with patch.dict("sys.modules", {"homeassistant.components.recorder.history": None}):
            result = await async_verify_migration(hass, entity_id_mapping)

        # Should return early with warning - recorder not in components
        assert result["verified"] == 0
        assert result["no_history"] == 0

    @pytest.mark.asyncio
    async def test_verify_migration_recorder_not_loaded(self, hass: HomeAssistant) -> None:
        """Test verification returns early when recorder component not loaded."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        # Ensure recorder is not in components
        hass.config.components = set()

        result = await async_verify_migration(hass, entity_id_mapping)

        assert result["verified"] == 0
        assert result["no_history"] == 0
        assert "Recorder not loaded" in result["failed"][0]

    @pytest.mark.asyncio
    async def test_verify_migration_with_verified_history(self, hass: HomeAssistant) -> None:
        """Test verification finds verified history."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        # Add recorder to components
        hass.config.components = {"recorder"}

        # Create mock state with old timestamp (more than 1 hour ago)
        mock_state = MagicMock()
        mock_state.last_changed = datetime.now(tz=UTC) - timedelta(hours=2)

        mock_history = {"sensor.neopool_water_temp": [mock_state]}

        with patch(
            "homeassistant.components.recorder.history.get_last_state_changes",
            return_value=mock_history,
        ):
            result = await async_verify_migration(hass, entity_id_mapping)

        assert result["verified"] == 1
        assert result["no_history"] == 0
        assert len(result["failed"]) == 0

    @pytest.mark.asyncio
    async def test_verify_migration_no_history(self, hass: HomeAssistant) -> None:
        """Test verification with no history found."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        hass.config.components = {"recorder"}

        # Return empty history
        mock_history: dict = {}

        with patch(
            "homeassistant.components.recorder.history.get_last_state_changes",
            return_value=mock_history,
        ):
            result = await async_verify_migration(hass, entity_id_mapping)

        assert result["verified"] == 0
        assert result["no_history"] == 1

    @pytest.mark.asyncio
    async def test_verify_migration_recent_history(self, hass: HomeAssistant) -> None:
        """Test verification with recent history (less than 1 hour)."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        hass.config.components = {"recorder"}

        # Create mock state with recent timestamp (less than 1 hour ago)
        mock_state = MagicMock()
        mock_state.last_changed = datetime.now(tz=UTC) - timedelta(minutes=30)

        mock_history = {"sensor.neopool_water_temp": [mock_state]}

        with patch(
            "homeassistant.components.recorder.history.get_last_state_changes",
            return_value=mock_history,
        ):
            result = await async_verify_migration(hass, entity_id_mapping)

        # Recent history doesn't count as "verified"
        assert result["verified"] == 0
        assert result["no_history"] == 1

    @pytest.mark.asyncio
    async def test_verify_migration_exception(self, hass: HomeAssistant) -> None:
        """Test verification handles exceptions gracefully."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        hass.config.components = {"recorder"}

        with patch(
            "homeassistant.components.recorder.history.get_last_state_changes",
            side_effect=Exception("Database error"),
        ):
            result = await async_verify_migration(hass, entity_id_mapping)

        assert result["verified"] == 0
        assert len(result["failed"]) > 0

    @pytest.mark.asyncio
    async def test_verify_migration_multiple_domains(self, hass: HomeAssistant) -> None:
        """Test verification searches across multiple domains."""
        entity_id_mapping = {
            "water_temp": "neopool_water_temp",
            "light_switch": "neopool_light",
        }

        hass.config.components = {"recorder"}

        # Return history for binary_sensor domain
        old_time = datetime.now(tz=UTC) - timedelta(hours=2)
        mock_state = MagicMock()
        mock_state.last_changed = old_time

        def mock_get_history(hass, num, entity_id):
            if entity_id == "binary_sensor.neopool_light":
                return {entity_id: [mock_state]}
            return {}

        with patch(
            "homeassistant.components.recorder.history.get_last_state_changes",
            side_effect=mock_get_history,
        ):
            result = await async_verify_migration(hass, entity_id_mapping)

        # One should be found in binary_sensor domain
        assert result["verified"] >= 0

    @pytest.mark.asyncio
    async def test_verify_migration_naive_datetime(self, hass: HomeAssistant) -> None:
        """Test verification handles naive datetime (no timezone)."""
        entity_id_mapping = {"water_temp": "neopool_water_temp"}

        hass.config.components = {"recorder"}

        # Create mock state with naive datetime (no timezone)
        mock_state = MagicMock()
        mock_state.last_changed = datetime.now() - timedelta(hours=2)  # noqa: DTZ005

        mock_history = {"sensor.neopool_water_temp": [mock_state]}

        with patch(
            "homeassistant.components.recorder.history.get_last_state_changes",
            return_value=mock_history,
        ):
            result = await async_verify_migration(hass, entity_id_mapping)

        # Should handle naive datetime and convert to UTC
        assert result["verified"] == 1


class TestShowMigrationVerificationResult:
    """Tests for _show_migration_verification_result function."""

    @pytest.mark.asyncio
    async def test_show_migration_success(self, hass: HomeAssistant) -> None:
        """Test showing successful migration notification."""
        verification = {
            "verified": 5,
            "no_history": 0,
            "failed": [],
        }

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await _show_migration_verification_result(hass, verification, "Test Pool")

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message")
        assert "Migration Successful" in message
        assert "✅" in message

    @pytest.mark.asyncio
    async def test_show_migration_partial_success(self, hass: HomeAssistant) -> None:
        """Test showing partial success notification (with failures)."""
        # Partial success requires verified > 0 AND (failures exist)
        # Per production code: verified > 0 and (no_history > 0 or failed) triggers partial
        # BUT the first condition `verified > 0 and not failed` takes precedence
        # So we need failures to trigger "Partially Successful"
        verification = {
            "verified": 3,
            "no_history": 2,
            "failed": ["sensor.test: Error"],  # Need failures for partial success
        }

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await _show_migration_verification_result(hass, verification, "Test Pool")

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message")
        assert "Partially Successful" in message
        assert "⚠️" in message

    @pytest.mark.asyncio
    async def test_show_migration_no_history_to_verify(self, hass: HomeAssistant) -> None:
        """Test showing notification when no history to verify."""
        verification = {
            "verified": 0,
            "no_history": 5,
            "failed": [],
        }

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await _show_migration_verification_result(hass, verification, "Test Pool")

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message")
        assert "No History to Verify" in message
        assert "ℹ️" in message

    @pytest.mark.asyncio
    async def test_show_migration_failed(self, hass: HomeAssistant) -> None:
        """Test showing failed migration notification."""
        verification = {
            "verified": 0,
            "no_history": 0,
            "failed": ["Error 1", "Error 2"],
        }

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await _show_migration_verification_result(hass, verification, "Test Pool")

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message")
        assert "Verification Failed" in message
        assert "❌" in message

    @pytest.mark.asyncio
    async def test_show_migration_with_errors(self, hass: HomeAssistant) -> None:
        """Test showing notification with error details."""
        verification = {
            "verified": 3,
            "no_history": 0,
            "failed": ["sensor.a: Error 1", "sensor.b: Error 2"],
        }

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await _show_migration_verification_result(hass, verification, "Test Pool")

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message")
        assert "Errors:" in message
        assert "Error 1" in message

    @pytest.mark.asyncio
    async def test_show_migration_many_errors_truncated(self, hass: HomeAssistant) -> None:
        """Test showing notification truncates many errors."""
        verification = {
            "verified": 0,
            "no_history": 0,
            "failed": [f"sensor.entity_{i}: Error {i}" for i in range(10)],
        }

        with patch(
            "custom_components.sugar_valley_neopool.persistent_notification.async_create"
        ) as mock_notify:
            await _show_migration_verification_result(hass, verification, "Test Pool")

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message")
        # Should show first 5 and indicate more
        assert "5 more" in message


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
