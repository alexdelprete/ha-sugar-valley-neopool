"""Tests for Sugar Valley NeoPool device triggers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.sugar_valley_neopool.const import DOMAIN
from custom_components.sugar_valley_neopool.device_trigger import (
    TRIGGER_SCHEMA,
    TRIGGER_TYPES,
    async_attach_trigger,
    async_get_triggers,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


@pytest.fixture
def mock_device_registry(hass: HomeAssistant) -> dr.DeviceRegistry:
    """Create mock device registry with a NeoPool device."""
    return dr.async_get(hass)


class TestTriggerTypes:
    """Tests for trigger type constants."""

    def test_trigger_types_defined(self) -> None:
        """Test trigger types are defined."""
        assert "device_offline" in TRIGGER_TYPES
        assert "device_online" in TRIGGER_TYPES
        assert "device_recovered" in TRIGGER_TYPES

    def test_trigger_types_count(self) -> None:
        """Test expected number of trigger types."""
        assert len(TRIGGER_TYPES) == 3


class TestAsyncGetTriggers:
    """Tests for async_get_triggers function."""

    @pytest.mark.asyncio
    async def test_get_triggers_for_neopool_device(self, hass: HomeAssistant) -> None:
        """Test getting triggers for a NeoPool device."""
        # Create a config entry first
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"device_name": "Test Pool", "discovery_prefix": "SmartPool"},
        )
        entry.add_to_hass(hass)

        # Create a device in the registry
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            name="Test Pool",
        )

        triggers = await async_get_triggers(hass, device.id)

        assert len(triggers) == 3
        for trigger in triggers:
            assert trigger[CONF_PLATFORM] == "device"
            assert trigger[CONF_DOMAIN] == DOMAIN
            assert trigger[CONF_DEVICE_ID] == device.id
            assert trigger[CONF_TYPE] in TRIGGER_TYPES

    @pytest.mark.asyncio
    async def test_get_triggers_for_non_neopool_device(self, hass: HomeAssistant) -> None:
        """Test getting triggers for a non-NeoPool device returns empty."""
        # Create a device from a different domain
        entry = MockConfigEntry(
            domain="other_domain",
            data={},
        )
        entry.add_to_hass(hass)

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("other_domain", "OTHER123")},
            name="Other Device",
        )

        triggers = await async_get_triggers(hass, device.id)

        assert triggers == []

    @pytest.mark.asyncio
    async def test_get_triggers_for_nonexistent_device(self, hass: HomeAssistant) -> None:
        """Test getting triggers for non-existent device returns empty."""
        triggers = await async_get_triggers(hass, "nonexistent_device_id")

        assert triggers == []

    @pytest.mark.asyncio
    async def test_get_triggers_contains_all_types(self, hass: HomeAssistant) -> None:
        """Test all trigger types are returned."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"device_name": "Test Pool"},
        )
        entry.add_to_hass(hass)

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            name="Test Pool",
        )

        triggers = await async_get_triggers(hass, device.id)
        trigger_types = {t[CONF_TYPE] for t in triggers}

        assert trigger_types == TRIGGER_TYPES


class TestAsyncAttachTrigger:
    """Tests for async_attach_trigger function."""

    @pytest.mark.asyncio
    async def test_attach_trigger(self, hass: HomeAssistant) -> None:
        """Test attaching a trigger."""
        config = {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: "test_device_id",
            CONF_TYPE: "device_offline",
        }
        action = MagicMock()
        trigger_info = {"trigger_id": "test_trigger"}

        with patch.object(
            event_trigger, "async_attach_trigger", return_value=MagicMock()
        ) as mock_attach:
            await async_attach_trigger(hass, config, action, trigger_info)

            mock_attach.assert_called_once()
            call_args = mock_attach.call_args
            assert call_args[0][0] == hass
            assert call_args[0][2] == action
            assert call_args[0][3] == trigger_info

    @pytest.mark.asyncio
    async def test_attach_trigger_event_config(self, hass: HomeAssistant) -> None:
        """Test the event config passed to event_trigger."""
        device_id = "my_device_id"
        trigger_type = "device_recovered"
        config = {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }

        captured_event_config = None

        def capture_schema(config_dict):
            nonlocal captured_event_config
            captured_event_config = config_dict
            return config_dict

        with (
            patch(
                "custom_components.sugar_valley_neopool.device_trigger.event_trigger.TRIGGER_SCHEMA",
                side_effect=capture_schema,
            ),
            patch(
                "custom_components.sugar_valley_neopool.device_trigger.event_trigger.async_attach_trigger",
                return_value=MagicMock(),
            ),
        ):
            await async_attach_trigger(hass, config, MagicMock(), {"trigger_id": "test"})

        # Verify the event config structure
        assert captured_event_config is not None
        assert captured_event_config["platform"] == "event"
        assert captured_event_config["event_type"] == f"{DOMAIN}_event"
        assert captured_event_config["event_data"][CONF_DEVICE_ID] == device_id
        assert captured_event_config["event_data"][CONF_TYPE] == trigger_type


class TestTriggerSchema:
    """Tests for trigger schema validation."""

    def test_valid_trigger_config(self) -> None:
        """Test valid trigger configuration passes schema."""
        config = {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: "test_device",
            CONF_TYPE: "device_offline",
        }
        validated = TRIGGER_SCHEMA(config)
        assert validated[CONF_TYPE] == "device_offline"

    def test_invalid_trigger_type(self) -> None:
        """Test invalid trigger type fails schema."""
        config = {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: "test_device",
            CONF_TYPE: "invalid_type",
        }
        with pytest.raises(vol.Invalid):
            TRIGGER_SCHEMA(config)
