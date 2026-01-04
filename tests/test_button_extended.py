"""Extended tests for NeoPool button platform - edge cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.button import (
    BUTTON_DESCRIPTIONS,
    NeoPoolButton,
    NeoPoolButtonEntityDescription,
)


class TestButtonDescriptionsExtended:
    """Extended tests for button descriptions."""

    def test_clear_error_has_empty_payload(self) -> None:
        """Test clear error button has empty payload."""
        desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == "clear_error")
        assert desc.payload == ""

    def test_all_buttons_have_icon(self) -> None:
        """Test all buttons have an icon."""
        for desc in BUTTON_DESCRIPTIONS:
            assert desc.icon is not None


class TestNeoPoolButtonExtended:
    """Extended tests for NeoPoolButton entity."""

    @pytest.mark.asyncio
    async def test_button_lwt_availability(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test button availability follows LWT."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
        )

        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = mock_hass
        button.entity_id = "button.test"
        button.async_write_ha_state = MagicMock()

        lwt_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal lwt_callback
            if "LWT" in topic:
                lwt_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await button.async_added_to_hass()

        # Button starts available (buttons are always available by default)
        assert button._attr_available is True

        # LWT Online keeps it available
        mock_lwt = MagicMock()
        mock_lwt.payload = "Online"
        lwt_callback(mock_lwt)
        assert button._attr_available is True

        # LWT Offline should make it unavailable
        mock_lwt.payload = "Offline"
        lwt_callback(mock_lwt)
        assert button._attr_available is False

    @pytest.mark.asyncio
    async def test_button_press_default_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test button press with default (None) payload."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
            # payload defaults to ""
        )

        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await button.async_press()

            mock_publish.assert_called_once()
            # Default payload should be empty string
            assert mock_publish.call_args[0][2] == ""

    @pytest.mark.asyncio
    async def test_button_press_non_empty_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test button press with non-empty payload."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
            payload="1",
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
                "1",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_button_unsubscribes_on_remove(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test button unsubscribes when removed."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
        )

        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = mock_hass
        button.entity_id = "button.test"

        mock_unsubscribe = MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=mock_unsubscribe,
        ):
            await button.async_added_to_hass()

        assert mock_unsubscribe in button._unsubscribe_callbacks

        await button.async_will_remove_from_hass()

        mock_unsubscribe.assert_called_once()
        assert button._unsubscribe_callbacks == []

    def test_button_unique_id(self, mock_config_entry: MagicMock) -> None:
        """Test button unique ID format."""
        desc = NeoPoolButtonEntityDescription(
            key="clear_error",
            name="Clear Error",
            command="NPEscape",
        )

        button = NeoPoolButton(mock_config_entry, desc)

        assert button._attr_unique_id == "neopool_mqtt_ABC123_clear_error"

    def test_button_device_info(self, mock_config_entry: MagicMock) -> None:
        """Test button has device info."""
        desc = NeoPoolButtonEntityDescription(
            key="test_button",
            name="Test Button",
            command="NPTest",
        )

        with patch(
            "custom_components.sugar_valley_neopool.entity.get_device_info",
            return_value={"identifiers": {("sugar_valley_neopool", "ABC123")}},
        ):
            button = NeoPoolButton(mock_config_entry, desc)

        assert button._attr_device_info is not None
