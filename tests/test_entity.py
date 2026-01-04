"""Tests for NeoPool base entity classes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.entity import NeoPoolEntity, NeoPoolMQTTEntity


class TestNeoPoolEntity:
    """Tests for NeoPoolEntity base class."""

    def test_entity_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test entity initialization."""
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity._config_entry == mock_config_entry
        assert entity._entity_key == "test_key"
        assert entity._attr_unique_id == "neopool_mqtt_ABC123_test_key"
        assert entity._attr_has_entity_name is True
        assert entity._attr_available is False

    def test_entity_unique_id_pattern(self, mock_config_entry: MagicMock) -> None:
        """Test unique ID follows NodeID pattern."""
        entity = NeoPoolEntity(mock_config_entry, "water_temperature")

        # NodeID-based pattern: neopool_mqtt_{nodeid}_{entity_key}
        assert entity._attr_unique_id == "neopool_mqtt_ABC123_water_temperature"

    def test_entity_device_info(self, mock_config_entry: MagicMock) -> None:
        """Test device info is set from config entry."""
        with patch(
            "custom_components.sugar_valley_neopool.entity.get_device_info"
        ) as mock_get_device_info:
            mock_get_device_info.return_value = {
                "identifiers": {("sugar_valley_neopool", "ABC123")},
                "name": "Test NeoPool",
            }
            entity = NeoPoolEntity(mock_config_entry, "test_key")

            mock_get_device_info.assert_called_once_with(mock_config_entry)
            assert entity._attr_device_info is not None

    def test_mqtt_topic_property(self, mock_config_entry: MagicMock) -> None:
        """Test mqtt_topic property returns discovery_prefix."""
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity.mqtt_topic == "SmartPool"

    def test_mqtt_topic_empty_when_missing(self, mock_config_entry: MagicMock) -> None:
        """Test mqtt_topic returns empty string when discovery_prefix missing."""
        mock_config_entry.data = {}
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity.mqtt_topic == ""


class TestNeoPoolMQTTEntity:
    """Tests for NeoPoolMQTTEntity base class."""

    def test_mqtt_entity_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test MQTT entity initialization."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")

        assert entity._unsubscribe_callbacks == []
        assert entity._attr_available is False

    @pytest.mark.asyncio
    async def test_async_added_to_hass_subscribes_to_lwt(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that entity subscribes to LWT topic when added."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"

        mock_unsubscribe = MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=mock_unsubscribe,
        ) as mock_subscribe:
            await entity.async_added_to_hass()

            # Should subscribe to LWT topic
            mock_subscribe.assert_called_once()
            call_args = mock_subscribe.call_args
            assert call_args[0][1] == "tele/SmartPool/LWT"
            assert call_args[1]["qos"] == 1

            # Should store unsubscribe callback
            assert mock_unsubscribe in entity._unsubscribe_callbacks

    @pytest.mark.asyncio
    async def test_availability_message_online(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test availability set to True on Online message."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"
        entity.async_write_ha_state = MagicMock()

        captured_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await entity.async_added_to_hass()

        # Simulate Online message
        mock_msg = MagicMock()
        mock_msg.payload = "Online"
        captured_callback(mock_msg)

        assert entity._attr_available is True
        entity.async_write_ha_state.assert_called()

    @pytest.mark.asyncio
    async def test_availability_message_offline(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test availability set to False on Offline message."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"
        entity.async_write_ha_state = MagicMock()

        captured_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal captured_callback
            captured_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await entity.async_added_to_hass()

        # Simulate Offline message
        mock_msg = MagicMock()
        mock_msg.payload = "Offline"
        captured_callback(mock_msg)

        assert entity._attr_available is False

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_unsubscribes(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that entity unsubscribes when removed."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"

        mock_unsubscribe1 = MagicMock()
        mock_unsubscribe2 = MagicMock()
        entity._unsubscribe_callbacks = [mock_unsubscribe1, mock_unsubscribe2]

        await entity.async_will_remove_from_hass()

        mock_unsubscribe1.assert_called_once()
        mock_unsubscribe2.assert_called_once()
        assert entity._unsubscribe_callbacks == []

    @pytest.mark.asyncio
    async def test_subscribe_topic(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test _subscribe_topic helper method."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"

        mock_callback = MagicMock()
        mock_unsubscribe = MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=mock_unsubscribe,
        ) as mock_subscribe:
            await entity._subscribe_topic("test/topic", mock_callback, qos=0)

            mock_subscribe.assert_called_once_with(mock_hass, "test/topic", mock_callback, qos=0)
            assert mock_unsubscribe in entity._unsubscribe_callbacks

    @pytest.mark.asyncio
    async def test_publish_command(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test _publish_command helper method."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await entity._publish_command("NPFiltration", "1", qos=1, retain=True)

            mock_publish.assert_called_once_with(
                mock_hass,
                "cmnd/SmartPool/NPFiltration",
                "1",
                qos=1,
                retain=True,
            )

    @pytest.mark.asyncio
    async def test_publish_command_default_params(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test _publish_command with default parameters."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await entity._publish_command("NPLight", "0")

            mock_publish.assert_called_once_with(
                mock_hass,
                "cmnd/SmartPool/NPLight",
                "0",
                qos=0,
                retain=False,
            )
