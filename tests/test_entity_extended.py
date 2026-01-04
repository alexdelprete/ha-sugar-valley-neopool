"""Extended tests for NeoPool base entity classes - edge cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.entity import NeoPoolEntity, NeoPoolMQTTEntity


class TestNeoPoolEntityExtended:
    """Extended tests for NeoPoolEntity base class."""

    def test_entity_with_special_characters_key(self, mock_config_entry: MagicMock) -> None:
        """Test entity with special characters in key."""
        entity = NeoPoolEntity(mock_config_entry, "ph_data_sensor")

        assert entity._attr_unique_id == "neopool_mqtt_ABC123_ph_data_sensor"

    def test_entity_unique_id_format(self, mock_config_entry: MagicMock) -> None:
        """Test entity unique_id includes nodeid."""
        entity = NeoPoolEntity(mock_config_entry, "test_key")
        # Unique ID should follow pattern: neopool_mqtt_{nodeid}_{entity_key}
        assert "neopool_mqtt_" in entity._attr_unique_id
        assert "_test_key" in entity._attr_unique_id

    def test_mqtt_topic_with_empty_discovery_prefix(self, mock_config_entry: MagicMock) -> None:
        """Test mqtt_topic with empty discovery_prefix."""
        mock_config_entry.data = {"discovery_prefix": ""}
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity.mqtt_topic == ""


class TestNeoPoolMQTTEntityExtended:
    """Extended tests for NeoPoolMQTTEntity base class."""

    @pytest.mark.asyncio
    async def test_availability_message_string_online(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test availability with string payload 'Online'."""
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

        # Simulate string Online message (HA MQTT delivers strings)
        mock_msg = MagicMock()
        mock_msg.payload = "Online"
        captured_callback(mock_msg)

        assert entity._attr_available is True

    @pytest.mark.asyncio
    async def test_availability_message_bytes_offline(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test availability with bytes payload 'Offline'."""
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

        mock_msg = MagicMock()
        mock_msg.payload = b"Offline"
        captured_callback(mock_msg)

        assert entity._attr_available is False

    @pytest.mark.asyncio
    async def test_availability_message_unknown_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test availability with unknown payload sets unavailable."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"
        entity._attr_available = True  # Start available
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

        mock_msg = MagicMock()
        mock_msg.payload = "UnknownStatus"
        captured_callback(mock_msg)

        # Unknown payload != "Online", so available becomes False
        assert entity._attr_available is False

    @pytest.mark.asyncio
    async def test_multiple_subscriptions(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test entity handles multiple subscriptions."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"

        mock_unsubscribe1 = MagicMock()
        mock_unsubscribe2 = MagicMock()

        call_count = 0

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_unsubscribe1 if call_count == 1 else mock_unsubscribe2

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            await entity.async_added_to_hass()
            # Subscribe to additional topic
            await entity._subscribe_topic("tele/SmartPool/SENSOR", MagicMock())

        assert len(entity._unsubscribe_callbacks) == 2
        assert mock_unsubscribe1 in entity._unsubscribe_callbacks
        assert mock_unsubscribe2 in entity._unsubscribe_callbacks

    @pytest.mark.asyncio
    async def test_remove_clears_all_subscriptions(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test removing entity clears all subscriptions."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"

        mock_unsub1 = MagicMock()
        mock_unsub2 = MagicMock()
        mock_unsub3 = MagicMock()
        entity._unsubscribe_callbacks = [mock_unsub1, mock_unsub2, mock_unsub3]

        await entity.async_will_remove_from_hass()

        mock_unsub1.assert_called_once()
        mock_unsub2.assert_called_once()
        mock_unsub3.assert_called_once()
        assert entity._unsubscribe_callbacks == []

    @pytest.mark.asyncio
    async def test_publish_command_with_empty_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test publishing command with empty payload."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await entity._publish_command("NPEscape", "")

            mock_publish.assert_called_once_with(
                mock_hass,
                "cmnd/SmartPool/NPEscape",
                "",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_subscribe_with_custom_qos(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test subscription with custom QoS."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity.entity_id = "sensor.test_entity"

        mock_callback = MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_subscribe:
            await entity._subscribe_topic("test/topic", mock_callback, qos=2)

            mock_subscribe.assert_called_once_with(mock_hass, "test/topic", mock_callback, qos=2)

    @pytest.mark.asyncio
    async def test_availability_transition_online_to_offline(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test availability transition from online to offline."""
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

        # First go online
        mock_msg = MagicMock()
        mock_msg.payload = "Online"
        captured_callback(mock_msg)
        assert entity._attr_available is True

        # Then go offline
        mock_msg.payload = "Offline"
        captured_callback(mock_msg)
        assert entity._attr_available is False

        # Verify state was written for both transitions
        assert entity.async_write_ha_state.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_unsubscribe_list(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test remove with empty unsubscribe list doesn't error."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = mock_hass
        entity._unsubscribe_callbacks = []

        # Should not raise
        await entity.async_will_remove_from_hass()
        assert entity._unsubscribe_callbacks == []
