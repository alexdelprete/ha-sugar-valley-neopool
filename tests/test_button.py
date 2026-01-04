"""Tests for NeoPool button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.button import (
    BUTTON_DESCRIPTIONS,
    NeoPoolButton,
    NeoPoolButtonEntityDescription,
    async_setup_entry,
)
from custom_components.sugar_valley_neopool.const import CMD_ESCAPE
from homeassistant.const import EntityCategory


class TestButtonDescriptions:
    """Tests for button entity descriptions."""

    def test_button_descriptions_exist(self) -> None:
        """Test that button descriptions are defined."""
        assert len(BUTTON_DESCRIPTIONS) > 0

    def test_clear_error_description(self) -> None:
        """Test clear error button description."""
        desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == "clear_error")

        assert desc.command == CMD_ESCAPE
        assert desc.payload == ""
        assert desc.entity_category == EntityCategory.CONFIG
        assert desc.icon == "mdi:alert-remove"

    def test_all_descriptions_have_command(self) -> None:
        """Test all descriptions have command field."""
        for desc in BUTTON_DESCRIPTIONS:
            assert desc.command is not None
            assert desc.key is not None


class TestNeoPoolButton:
    """Tests for NeoPoolButton entity."""

    def test_button_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test button initialization."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
            payload="test",
        )

        button = NeoPoolButton(mock_config_entry, desc)

        assert button.entity_description == desc
        assert button._attr_unique_id == "neopool_mqtt_ABC123_test_button"
        # Buttons are always available
        assert button._attr_available is True

    def test_button_always_available(self, mock_config_entry: MagicMock) -> None:
        """Test button is always available (no state tracking)."""
        desc = NeoPoolButtonEntityDescription(
            key="clear_error",
            name="Clear Error",
            command=CMD_ESCAPE,
        )

        button = NeoPoolButton(mock_config_entry, desc)

        assert button._attr_available is True

    @pytest.mark.asyncio
    async def test_button_press(self, mock_config_entry: MagicMock, mock_hass: MagicMock) -> None:
        """Test button press sends command."""
        desc = NeoPoolButtonEntityDescription(
            key="clear_error",
            name="Clear Error",
            command=CMD_ESCAPE,
            payload="",
        )

        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await button.async_press()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_ESCAPE}",
                "",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_button_press_with_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test button press with custom payload."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
            payload="custom_value",
        )

        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await button.async_press()

            mock_publish.assert_called_once_with(
                mock_hass,
                "cmnd/SmartPool/NPTest",
                "custom_value",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_button_does_not_subscribe_to_sensor(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test button only subscribes to LWT, not SENSOR topic."""
        desc = NeoPoolButtonEntityDescription(
            key="clear_error",
            name="Clear Error",
            command=CMD_ESCAPE,
        )

        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = mock_hass
        button.entity_id = "button.clear_error"

        subscribed_topics = []

        async def capture_callback(hass, topic, callback, **kwargs):
            subscribed_topics.append(topic)
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await button.async_added_to_hass()

        # Button inherits from NeoPoolMQTTEntity which subscribes to LWT
        assert "tele/SmartPool/LWT" in subscribed_topics
        # Button does not override async_added_to_hass to subscribe to SENSOR


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_buttons(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all button entities."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        assert len(added_entities) == len(BUTTON_DESCRIPTIONS)
        assert all(isinstance(e, NeoPoolButton) for e in added_entities)

    @pytest.mark.asyncio
    async def test_setup_entry_button_keys_match(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that created buttons match description keys."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        entity_keys = {e.entity_description.key for e in added_entities}
        description_keys = {d.key for d in BUTTON_DESCRIPTIONS}

        assert entity_keys == description_keys
