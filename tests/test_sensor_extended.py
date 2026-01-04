"""Extended tests for NeoPool sensor platform - edge cases."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.sensor import (
    SENSOR_DESCRIPTIONS,
    NeoPoolSensor,
    NeoPoolSensorEntityDescription,
)


class TestSensorDescriptionsExtended:
    """Extended tests for sensor entity descriptions."""

    def test_ph_state_sensor_has_value_fn(self) -> None:
        """Test pH state sensor has value function."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ph_state")
        assert desc.value_fn is not None

    def test_hydrolysis_state_sensor(self) -> None:
        """Test hydrolysis state sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_state")
        assert desc.json_path == "NeoPool.Hydrolysis.State"

    def test_filtration_mode_sensor(self) -> None:
        """Test filtration mode sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "filtration_mode")
        assert desc.json_path == "NeoPool.Filtration.Mode"
        assert desc.value_fn is not None

    def test_all_translation_keys_or_names(self) -> None:
        """Test all sensors have translation_key or name."""
        for desc in SENSOR_DESCRIPTIONS:
            has_name = desc.name is not None
            has_translation_key = desc.translation_key is not None
            assert has_name or has_translation_key, (
                f"Sensor {desc.key} missing name/translation_key"
            )


class TestNeoPoolSensorExtended:
    """Extended tests for NeoPoolSensor entity."""

    @pytest.mark.asyncio
    async def test_sensor_lwt_online_then_data(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test sensor receives LWT online then MQTT data."""
        desc = NeoPoolSensorEntityDescription(
            key="water_temperature",
            name="Water Temperature",
            json_path="NeoPool.Temperature",
            value_fn=float,
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.water_temperature"
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

        # Receive LWT Online first
        mock_lwt_msg = MagicMock()
        mock_lwt_msg.payload = "Online"
        lwt_callback(mock_lwt_msg)

        assert sensor._attr_available is True

        # Then receive sensor data
        mock_sensor_msg = MagicMock()
        mock_sensor_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_sensor_msg)

        assert sensor._attr_native_value == 28.5

    @pytest.mark.asyncio
    async def test_sensor_bytes_payload(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor handles bytes payload."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Temperature",
            value_fn=float,
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"
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

        # Send bytes payload
        mock_msg = MagicMock()
        mock_msg.payload = b'{"NeoPool": {"Temperature": 25.5}}'
        sensor_callback(mock_msg)

        assert sensor._attr_native_value == 25.5

    @pytest.mark.asyncio
    async def test_sensor_value_fn_returns_none(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor when value_fn returns None."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Test",
            value_fn=lambda x: None,  # Always returns None
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"
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
        mock_msg.payload = json.dumps({"NeoPool": {"Test": 123}})
        sensor_callback(mock_msg)

        # Value should be None, state should not be written
        assert sensor._attr_native_value is None

    @pytest.mark.asyncio
    async def test_sensor_value_fn_exception(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor when value_fn raises exception."""

        def failing_fn(x):
            raise ValueError("Test error")

        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Test",
            value_fn=failing_fn,
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"
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
        mock_msg.payload = json.dumps({"NeoPool": {"Test": "value"}})

        # Should not raise, but value should not be set
        sensor_callback(mock_msg)
        # Value should remain None
        assert sensor._attr_native_value is None

    @pytest.mark.asyncio
    async def test_sensor_nested_path_extraction(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor extracts deeply nested values."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Hydrolysis.Runtime.Total",
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"
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
        mock_msg.payload = json.dumps(
            {"NeoPool": {"Hydrolysis": {"Runtime": {"Total": "100T05:30:00"}}}}
        )
        sensor_callback(mock_msg)

        assert sensor._attr_native_value == "100T05:30:00"

    @pytest.mark.asyncio
    async def test_sensor_empty_payload(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor handles empty payload."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Temperature",
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"
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
        mock_msg.payload = "{}"
        sensor_callback(mock_msg)

        assert sensor._attr_native_value is None
        sensor.async_write_ha_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_sensor_update_multiple_times(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor updates correctly on multiple messages."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Temperature",
            value_fn=float,
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"
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

        # First update
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Temperature": 25.0}})
        sensor_callback(mock_msg)
        assert sensor._attr_native_value == 25.0

        # Second update
        mock_msg.payload = json.dumps({"NeoPool": {"Temperature": 27.5}})
        sensor_callback(mock_msg)
        assert sensor._attr_native_value == 27.5

        # Third update
        mock_msg.payload = json.dumps({"NeoPool": {"Temperature": 30.0}})
        sensor_callback(mock_msg)
        assert sensor._attr_native_value == 30.0

        assert sensor.async_write_ha_state.call_count == 3
