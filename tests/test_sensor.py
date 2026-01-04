"""Tests for NeoPool sensor platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.sensor import (
    SENSOR_DESCRIPTIONS,
    NeoPoolSensor,
    NeoPoolSensorEntityDescription,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature


class TestSensorDescriptions:
    """Tests for sensor entity descriptions."""

    def test_sensor_descriptions_exist(self) -> None:
        """Test that sensor descriptions are defined."""
        assert len(SENSOR_DESCRIPTIONS) > 0

    def test_water_temperature_description(self) -> None:
        """Test water temperature sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "water_temperature")

        assert desc.device_class == SensorDeviceClass.TEMPERATURE
        assert desc.native_unit_of_measurement == UnitOfTemperature.CELSIUS
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.json_path == "NeoPool.Temperature"
        assert desc.value_fn is not None

    def test_ph_data_description(self) -> None:
        """Test pH sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ph_data")

        assert desc.device_class == SensorDeviceClass.PH
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.json_path == "NeoPool.pH.Data"

    def test_redox_data_description(self) -> None:
        """Test redox sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "redox_data")

        assert desc.device_class == SensorDeviceClass.VOLTAGE
        assert desc.json_path == "NeoPool.Redox.Data"

    def test_hydrolysis_runtime_description(self) -> None:
        """Test hydrolysis runtime sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_runtime_total")

        assert desc.device_class == SensorDeviceClass.DURATION
        assert desc.state_class == SensorStateClass.TOTAL_INCREASING
        assert desc.json_path == "NeoPool.Hydrolysis.Runtime.Total"

    def test_all_descriptions_have_required_fields(self) -> None:
        """Test all descriptions have required fields."""
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.key is not None
            assert desc.json_path is not None
            assert desc.name is not None or desc.translation_key is not None


class TestNeoPoolSensor:
    """Tests for NeoPoolSensor entity."""

    def test_sensor_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test sensor initialization."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Test.Value",
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)

        assert sensor.entity_description == desc
        assert sensor._attr_native_value is None
        assert sensor._attr_unique_id == "neopool_mqtt_ABC123_test_sensor"

    @pytest.mark.asyncio
    async def test_sensor_subscribes_to_topic(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test sensor subscribes to MQTT topic."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Temperature",
        )

        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.test_sensor"

        subscribed_topics = []

        async def mock_subscribe(hass, topic, callback, **kwargs):
            subscribed_topics.append(topic)
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            await sensor.async_added_to_hass()

        # Should subscribe to LWT and SENSOR topics
        assert "tele/SmartPool/LWT" in subscribed_topics
        assert "tele/SmartPool/SENSOR" in subscribed_topics

    @pytest.mark.asyncio
    async def test_sensor_processes_mqtt_message(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test sensor processes MQTT message correctly."""
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

        # Simulate MQTT message
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        assert sensor._attr_native_value == 28.5
        assert sensor._attr_available is True
        sensor.async_write_ha_state.assert_called()

    @pytest.mark.asyncio
    async def test_sensor_handles_invalid_json(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test sensor handles invalid JSON gracefully."""
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

        # Simulate invalid MQTT message
        mock_msg = MagicMock()
        mock_msg.payload = "not valid json"
        sensor_callback(mock_msg)

        # Value should remain None
        assert sensor._attr_native_value is None
        # async_write_ha_state should not be called for invalid JSON
        sensor.async_write_ha_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_sensor_handles_missing_path(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test sensor handles missing JSON path gracefully."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.NonExistent.Path",
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

        # Simulate MQTT message without the expected path
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Other": "data"}})
        sensor_callback(mock_msg)

        # Value should remain None
        assert sensor._attr_native_value is None
        sensor.async_write_ha_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_sensor_applies_value_function(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test sensor applies value transformation function."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.pH.State",
            value_fn=lambda x: f"State {x}",
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
        mock_msg.payload = json.dumps({"NeoPool": {"pH": {"State": 0}}})
        sensor_callback(mock_msg)

        assert sensor._attr_native_value == "State 0"

    @pytest.mark.asyncio
    async def test_sensor_without_value_function(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test sensor without value function uses raw value."""
        desc = NeoPoolSensorEntityDescription(
            key="test_sensor",
            name="Test Sensor",
            json_path="NeoPool.Type",
            value_fn=None,
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
        mock_msg.payload = json.dumps({"NeoPool": {"Type": "Sugar Valley"}})
        sensor_callback(mock_msg)

        assert sensor._attr_native_value == "Sugar Valley"


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_sensors(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all sensor entities."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        assert len(added_entities) == len(SENSOR_DESCRIPTIONS)
        assert all(isinstance(e, NeoPoolSensor) for e in added_entities)

    @pytest.mark.asyncio
    async def test_setup_entry_sensor_keys_match(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that created sensors match description keys."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        entity_keys = {e.entity_description.key for e in added_entities}
        description_keys = {d.key for d in SENSOR_DESCRIPTIONS}

        assert entity_keys == description_keys
