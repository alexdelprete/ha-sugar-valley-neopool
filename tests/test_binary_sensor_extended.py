"""Extended tests for NeoPool binary sensor platform - edge cases."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    NeoPoolBinarySensor,
    NeoPoolBinarySensorEntityDescription,
)


class TestBinarySensorDescriptionsExtended:
    """Extended tests for binary sensor descriptions."""

    def test_all_descriptions_have_invert_field(self) -> None:
        """Test all descriptions have invert field (default or explicit)."""
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            # invert defaults to False in the dataclass
            assert hasattr(desc, "invert")

    def test_inverted_sensors_count(self) -> None:
        """Test correct number of inverted sensors."""
        inverted = [d for d in BINARY_SENSOR_DESCRIPTIONS if d.invert]
        # Should have some inverted sensors (FL1, Tank level, etc.)
        assert len(inverted) >= 2

    def test_module_descriptions_exist(self) -> None:
        """Test module binary sensor descriptions exist."""
        module_descs = [d for d in BINARY_SENSOR_DESCRIPTIONS if "modules" in d.key.lower()]
        # Should have module presence sensors (pH, Redox, Hydrolysis, Chlorine)
        assert len(module_descs) >= 4


class TestNeoPoolBinarySensorExtended:
    """Extended tests for NeoPoolBinarySensor entity."""

    @pytest.mark.asyncio
    async def test_binary_sensor_with_value_fn(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor with custom value function."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Test.Value",
            value_fn=lambda x: x > 50,  # True if value > 50
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        # Value > 50 should be True
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Value": 75}}})
        sensor_callback(mock_msg)
        assert sensor._attr_is_on is True

        # Value <= 50 should be False
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Value": 30}}})
        sensor_callback(mock_msg)
        assert sensor._attr_is_on is False

    @pytest.mark.asyncio
    async def test_binary_sensor_invert_with_string_values(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor invert with string bit values."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Test.State",
            invert=True,
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        # String "0" inverted should be True
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": "0"}}})
        sensor_callback(mock_msg)
        assert sensor._attr_is_on is True

        # String "1" inverted should be False
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": "1"}}})
        sensor_callback(mock_msg)
        assert sensor._attr_is_on is False

    @pytest.mark.asyncio
    async def test_binary_sensor_no_invert(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor without invert."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Modules.pH",
            invert=False,
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        # Value 1 should be True (not inverted)
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Modules": {"pH": 1}}})
        sensor_callback(mock_msg)
        assert sensor._attr_is_on is True

        # Value 0 should be False (not inverted)
        mock_msg.payload = json.dumps({"NeoPool": {"Modules": {"pH": 0}}})
        sensor_callback(mock_msg)
        assert sensor._attr_is_on is False

    @pytest.mark.asyncio
    async def test_binary_sensor_deep_array_access(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor with array access in nested path."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="relay_aux3",
            name="Relay Aux 3",
            json_path="NeoPool.Relay.Aux.2",  # Third element
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.relay_aux3"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Relay": {"Aux": [0, 0, 1, 0]}}})
        sensor_callback(mock_msg)

        assert sensor._attr_is_on is True

    @pytest.mark.asyncio
    async def test_binary_sensor_availability_follows_lwt(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor availability follows LWT."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Test.State",
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        lwt_callback = None
        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal lwt_callback, sensor_callback
            if "LWT" in topic:
                lwt_callback = callback
            elif "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        # Initially unavailable
        assert sensor._attr_available is False

        # LWT Online makes available
        mock_lwt = MagicMock()
        mock_lwt.payload = "Online"
        lwt_callback(mock_lwt)
        assert sensor._attr_available is True

        # Receive sensor data
        mock_sensor = MagicMock()
        mock_sensor.payload = json.dumps({"NeoPool": {"Test": {"State": 1}}})
        sensor_callback(mock_sensor)
        assert sensor._attr_is_on is True
        assert sensor._attr_available is True

        # LWT Offline makes unavailable
        mock_lwt.payload = "Offline"
        lwt_callback(mock_lwt)
        assert sensor._attr_available is False

    @pytest.mark.asyncio
    async def test_binary_sensor_value_fn_none_result(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor when value_fn returns None."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Test.State",
            value_fn=lambda x: None,  # Always returns None
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": 1}}})
        sensor_callback(mock_msg)

        # Should not update state when value_fn returns None
        assert sensor._attr_is_on is None

    @pytest.mark.asyncio
    async def test_binary_sensor_boolean_true_value(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor with actual boolean true value."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Test.Active",
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        # JSON true value
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Active": True}}})
        sensor_callback(mock_msg)

        # Boolean True should be converted to True
        assert sensor._attr_is_on is True

    @pytest.mark.asyncio
    async def test_binary_sensor_null_value(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor with null JSON value."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary",
            name="Test Binary",
            json_path="NeoPool.Test.State",
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test"
        sensor.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await sensor.async_added_to_hass()

        # null value in JSON
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": None}}})
        sensor_callback(mock_msg)

        # null should result in None
        assert sensor._attr_is_on is None
