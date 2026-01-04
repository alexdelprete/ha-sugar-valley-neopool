"""Tests for Sugar Valley NeoPool repairs module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.sugar_valley_neopool.const import DOMAIN
from custom_components.sugar_valley_neopool.repairs import (
    ISSUE_DEVICE_OFFLINE,
    create_device_offline_issue,
    create_recovery_notification,
    delete_device_offline_issue,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


class TestCreateDeviceOfflineIssue:
    """Tests for create_device_offline_issue function."""

    def test_creates_issue(self, hass: HomeAssistant) -> None:
        """Test creating a device offline issue."""
        with patch.object(ir, "async_create_issue") as mock_create:
            create_device_offline_issue(
                hass,
                entry_id="test_entry_id",
                device_name="Test Pool",
                mqtt_topic="SmartPool",
                offline_since="2024-01-01 12:00:00",
                offline_duration="5m 30s",
            )

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][0] == hass
            assert call_args[0][1] == DOMAIN
            assert call_args[0][2] == f"{ISSUE_DEVICE_OFFLINE}_test_entry_id"

    def test_issue_parameters(self, hass: HomeAssistant) -> None:
        """Test issue is created with correct parameters."""
        with patch.object(ir, "async_create_issue") as mock_create:
            create_device_offline_issue(
                hass,
                entry_id="entry123",
                device_name="My Pool",
                mqtt_topic="PoolTopic",
                offline_since="2024-01-01 10:00:00",
                offline_duration="10m",
            )

            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["is_fixable"] is False
            assert call_kwargs["is_persistent"] is True
            assert call_kwargs["severity"] == ir.IssueSeverity.ERROR
            assert call_kwargs["translation_key"] == ISSUE_DEVICE_OFFLINE
            assert call_kwargs["translation_placeholders"]["device_name"] == "My Pool"
            assert call_kwargs["translation_placeholders"]["mqtt_topic"] == "PoolTopic"
            assert call_kwargs["translation_placeholders"]["offline_since"] == "2024-01-01 10:00:00"
            assert call_kwargs["translation_placeholders"]["offline_duration"] == "10m"


class TestDeleteDeviceOfflineIssue:
    """Tests for delete_device_offline_issue function."""

    def test_deletes_issue(self, hass: HomeAssistant) -> None:
        """Test deleting a device offline issue."""
        with patch.object(ir, "async_delete_issue") as mock_delete:
            delete_device_offline_issue(hass, entry_id="test_entry_id")

            mock_delete.assert_called_once_with(
                hass, DOMAIN, f"{ISSUE_DEVICE_OFFLINE}_test_entry_id"
            )

    def test_deletes_correct_issue_id(self, hass: HomeAssistant) -> None:
        """Test correct issue ID is deleted."""
        with patch.object(ir, "async_delete_issue") as mock_delete:
            delete_device_offline_issue(hass, entry_id="my_entry")

            call_args = mock_delete.call_args[0]
            assert call_args[0] == hass
            assert call_args[1] == DOMAIN
            assert call_args[2] == f"{ISSUE_DEVICE_OFFLINE}_my_entry"


class TestCreateRecoveryNotification:
    """Tests for create_recovery_notification function."""

    def test_creates_notification(self, hass: HomeAssistant) -> None:
        """Test creating a recovery notification."""
        mock_service_call = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = mock_service_call
        hass.async_create_task = MagicMock()

        create_recovery_notification(
            hass,
            entry_id="test_entry",
            device_name="Test Pool",
            started_at="2024-01-01 10:00:00",
            ended_at="2024-01-01 10:05:30",
            downtime="5m 30s",
        )

        # Verify async_create_task was called
        hass.async_create_task.assert_called_once()

    def test_notification_without_script(self, hass: HomeAssistant) -> None:
        """Test notification without recovery script."""
        hass.services = MagicMock()
        hass.async_create_task = MagicMock()

        create_recovery_notification(
            hass,
            entry_id="test_entry",
            device_name="Pool",
            started_at="2024-01-01 10:00:00",
            ended_at="2024-01-01 10:10:00",
            downtime="10m",
            script_name=None,
            script_executed_at=None,
        )

        hass.async_create_task.assert_called_once()

    def test_notification_with_script(self, hass: HomeAssistant) -> None:
        """Test notification with recovery script."""
        hass.services = MagicMock()
        hass.async_create_task = MagicMock()

        create_recovery_notification(
            hass,
            entry_id="test_entry",
            device_name="Pool",
            started_at="2024-01-01 10:00:00",
            ended_at="2024-01-01 10:10:00",
            downtime="10m",
            script_name="script.neopool_recovery",
            script_executed_at="2024-01-01 10:05:00",
        )

        hass.async_create_task.assert_called_once()


class TestIssueConstants:
    """Tests for issue constants."""

    def test_issue_device_offline_constant(self) -> None:
        """Test ISSUE_DEVICE_OFFLINE constant."""
        assert ISSUE_DEVICE_OFFLINE == "device_offline"
