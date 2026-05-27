"""Tests for NeoPool sensor platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    JSON_PATH_CHLORINE_DATA,
    JSON_PATH_CONDUCTIVITY_DATA,
    JSON_PATH_HYDROLYSIS_DATA,
    JSON_PATH_HYDROLYSIS_MAX,
    JSON_PATH_HYDROLYSIS_SETPOINT_GH,
    JSON_PATH_HYDROLYSIS_UNIT,
    JSON_PATH_IONIZATION_DATA,
    JSON_PATH_TIME,
)
from custom_components.sugar_valley_neopool.helpers import ConnectionRateTracker
from custom_components.sugar_valley_neopool.sensor import (
    SENSOR_DESCRIPTIONS,
    NeoPoolConnectionRateSensor,
    NeoPoolCumulativeSensor,
    NeoPoolCumulativeSensorEntityDescription,
    NeoPoolSensor,
    NeoPoolSensorEntityDescription,
    _hydrolysis_gh_only_fn,
    _hydrolysis_percent_fn,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature


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

    def test_ionization_data_description(self) -> None:
        """Test ionization sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "ionization_data")
        assert desc.native_unit_of_measurement == PERCENTAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.json_path == JSON_PATH_IONIZATION_DATA
        assert desc.value_fn is not None

    def test_conductivity_data_description(self) -> None:
        """Test conductivity sensor description.

        Firmware emits NeoPool.Conductivity as a flat scalar (not an object).
        See docs/TASMOTA_NEOPOOL_DRIVER_REFERENCE.md, "Conductivity deep dive".
        """
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "conductivity_data")
        assert desc.native_unit_of_measurement == PERCENTAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.json_path == JSON_PATH_CONDUCTIVITY_DATA
        assert desc.json_path == "NeoPool.Conductivity"
        assert desc.value_fn is not None
        # No device_class — HA's SensorDeviceClass.CONDUCTIVITY expects µS/cm
        assert desc.device_class is None

    def test_chlorine_data_description(self) -> None:
        """Test chlorine sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "chlorine_data")
        assert desc.native_unit_of_measurement == "ppm"
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.json_path == JSON_PATH_CHLORINE_DATA
        assert desc.value_fn is not None

    def test_hydrolysis_max_description(self) -> None:
        """Test hydrolysis_max sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_max")
        assert desc.native_unit_of_measurement == "g/h"
        # No state_class - this is a device capability constant, not a measurement
        assert desc.state_class is None
        assert desc.json_path == JSON_PATH_HYDROLYSIS_MAX
        # g/h sensors use payload_fn to go unavailable when controller is in % mode
        assert desc.payload_fn is not None

    def test_hydrolysis_unit_description(self) -> None:
        """Test hydrolysis_unit sensor description (string sensor)."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_unit")
        assert desc.json_path == JSON_PATH_HYDROLYSIS_UNIT
        assert desc.device_class is None
        assert desc.native_unit_of_measurement is None

    def test_hydrolysis_setpoint_gh_description(self) -> None:
        """Test hydrolysis_setpoint_gh sensor (read-only g/h companion)."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_setpoint_gh")
        assert desc.native_unit_of_measurement == "g/h"
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.json_path == JSON_PATH_HYDROLYSIS_SETPOINT_GH
        assert desc.payload_fn is not None

    def test_hydrolysis_percent_description(self) -> None:
        """Test hydrolysis_percent sensor description.

        The percent sensor computes from Data/Unit/Max via payload_fn instead
        of reading Hydrolysis.Percent.Data directly, so it works on Tasmota
        firmware that pre-dates the Percent sub-object (pre-Nov 2023) and
        also when the controller is in % mode.
        """
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_percent")
        assert desc.native_unit_of_measurement == PERCENTAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.payload_fn is not None

    def test_hydrolysis_data_description(self) -> None:
        """Test hydrolysis_data (g/h) sensor description."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_data")
        assert desc.native_unit_of_measurement == "g/h"
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.payload_fn is not None

    def test_controller_time_description(self) -> None:
        """Test controller_time sensor description.

        Firmware emits ISO string without timezone, so no TIMESTAMP device_class.
        """
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "controller_time")
        assert desc.json_path == JSON_PATH_TIME
        assert desc.device_class is None  # No TZ in firmware string

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
        assert sensor._attr_available is False
        sensor.async_write_ha_state.assert_called()

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


class TestHydrolysisPayloadFns:
    """Tests for the hydrolysis payload_fn helpers."""

    @staticmethod
    def _payload(hydrolysis: dict[str, Any]) -> dict[str, Any]:
        """Build a minimal payload with just the Hydrolysis block populated."""
        return {"NeoPool": {"Hydrolysis": hydrolysis}}

    def test_percent_uses_data_when_unit_is_percent(self) -> None:
        """In % mode, Data is already the percentage — use it directly.

        Reproduces the user-reported bug: controller in % mode published
        Hydrolysis.Data = 50 (percent), but the integration was reading
        Percent.Data which the firmware emits as 0 due to integer truncation
        (or doesn't emit at all on older builds), so the % sensor stayed at 0.
        """
        payload = self._payload({"Data": 50, "Unit": "%", "Max": 100})
        assert _hydrolysis_percent_fn(payload) == 50

    def test_percent_computes_from_data_and_max_in_gh_mode(self) -> None:
        """In g/h mode, compute percent from Data and Max in floating point."""
        payload = self._payload({"Data": 25, "Unit": "g/h", "Max": 100})
        assert _hydrolysis_percent_fn(payload) == 25

    def test_percent_avoids_firmware_integer_truncation(self) -> None:
        """Tasmota's `data * 100 / max` truncates to 0 for small data values.

        Example: data=0.5, max=100 → Tasmota emits Percent.Data=0. Our
        float-based computation correctly yields 1 (rounded from 0.5).
        """
        payload = self._payload({"Data": 0.5, "Unit": "g/h", "Max": 100, "Percent": {"Data": 0}})
        assert _hydrolysis_percent_fn(payload) == round(0.5)

    def test_percent_fallback_to_percent_data(self) -> None:
        """Fall back to Hydrolysis.Percent.Data when Max is missing/zero."""
        payload = self._payload({"Data": 5, "Unit": "g/h", "Max": 0, "Percent": {"Data": 42}})
        assert _hydrolysis_percent_fn(payload) == 42

    def test_percent_returns_none_when_data_missing(self) -> None:
        """If Hydrolysis.Data is missing, return None (sensor unavailable)."""
        payload = self._payload({"Unit": "g/h", "Max": 100})
        assert _hydrolysis_percent_fn(payload) is None

    def test_percent_returns_none_when_nothing_recoverable(self) -> None:
        """g/h mode, Max=0, no Percent.Data → cannot compute, unavailable."""
        payload = self._payload({"Data": 5, "Unit": "g/h", "Max": 0})
        assert _hydrolysis_percent_fn(payload) is None

    def test_gh_only_returns_value_in_gh_mode(self) -> None:
        """g/h-only sensors return the raw value when controller is in g/h."""
        fn = _hydrolysis_gh_only_fn(JSON_PATH_HYDROLYSIS_DATA)
        payload = self._payload({"Data": 25.5, "Unit": "g/h", "Max": 100})
        assert fn(payload) == 25.5

    def test_gh_only_returns_none_in_percent_mode(self) -> None:
        """g/h-labeled sensors must NOT show a percentage with a g/h unit.

        Why: when the controller is in % mode the JSON fields are in percent,
        not g/h, and there is no way to recover the absolute g/h value from
        the telemetry (Max becomes 100%). Showing the raw value with a "g/h"
        label would be misleading.
        """
        fn = _hydrolysis_gh_only_fn(JSON_PATH_HYDROLYSIS_DATA)
        payload = self._payload({"Data": 50, "Unit": "%", "Max": 100})
        assert fn(payload) is None

    def test_gh_only_returns_none_when_path_missing(self) -> None:
        """If the requested field is missing, return None."""
        fn = _hydrolysis_gh_only_fn(JSON_PATH_HYDROLYSIS_MAX)
        payload = self._payload({"Data": 25, "Unit": "g/h"})
        assert fn(payload) is None


class TestSensorPayloadFnIntegration:
    """Tests for NeoPoolSensor end-to-end with payload_fn."""

    @pytest.mark.asyncio
    async def test_percent_sensor_works_in_percent_mode(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """End-to-end: % sensor reports value when controller is in % mode."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_percent")
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.hydrolysis"
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

        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Hydrolysis": {"Data": 50, "Unit": "%", "Max": 100}}})
        sensor_callback(msg)

        assert sensor._attr_native_value == 50
        assert sensor._attr_available is True

    @pytest.mark.asyncio
    async def test_gh_sensor_unavailable_in_percent_mode(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """End-to-end: g/h sensor goes unavailable when controller is in % mode."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "hydrolysis_data")
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.hydrolysis_gh"
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

        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Hydrolysis": {"Data": 50, "Unit": "%", "Max": 100}}})
        sensor_callback(msg)

        assert sensor._attr_native_value is None
        assert sensor._attr_available is False


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_sensors(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all sensor entities.

        Setup creates one entity per SENSOR_DESCRIPTIONS plus the standalone
        NeoPoolConnectionRateSensor (which has no description because it
        reads from the shared ConnectionRateTracker, not from a JSON path).
        """
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # +1 for the standalone NeoPoolConnectionRateSensor
        assert len(added_entities) == len(SENSOR_DESCRIPTIONS) + 1

        assert all(
            isinstance(e, (NeoPoolSensor, NeoPoolConnectionRateSensor)) for e in added_entities
        )

    @pytest.mark.asyncio
    async def test_setup_entry_sensor_keys_match(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Created sensors include every SENSOR_DESCRIPTIONS key (plus the rate sensor)."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        description_keys = {d.key for d in SENSOR_DESCRIPTIONS}
        description_keys.add("connection_error_rate")  # standalone, no description
        entity_keys = {
            e.entity_description.key
            if hasattr(e, "entity_description") and e.entity_description is not None
            else e._entity_key
            for e in added_entities
        }
        assert entity_keys == description_keys


class TestThrottleAndCumulative:
    """Tests for min_update_interval throttling and NeoPoolCumulativeSensor."""

    @pytest.mark.asyncio
    async def test_throttle_first_write_passes_through(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """The first SENSOR message after subscription writes immediately."""
        desc = NeoPoolSensorEntityDescription(
            key="throttled",
            name="Throttled",
            json_path="NeoPool.Temperature",
            min_update_interval=300.0,
        )
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.throttled"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture):
            await sensor.async_added_to_hass()

        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Temperature": 25.5}})
        cb(msg)

        assert sensor._attr_native_value == 25.5
        sensor.async_write_ha_state.assert_called()

    @pytest.mark.asyncio
    async def test_throttle_silences_within_window(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Updates within the throttle window track in memory but don't write."""
        desc = NeoPoolSensorEntityDescription(
            key="throttled",
            name="Throttled",
            json_path="NeoPool.Temperature",
            min_update_interval=300.0,
        )
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.throttled"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture):
            await sensor.async_added_to_hass()

        # First message writes
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Temperature": 25.5}})))
        assert sensor.async_write_ha_state.call_count == 1
        # Second message immediately after — value tracks but no write
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Temperature": 26.0}})))
        assert sensor._attr_native_value == 26.0
        assert sensor.async_write_ha_state.call_count == 1  # still 1

    @pytest.mark.asyncio
    async def test_throttle_writes_after_window_elapses(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """After the throttle window elapses, the next message writes."""
        desc = NeoPoolSensorEntityDescription(
            key="throttled",
            name="Throttled",
            json_path="NeoPool.Temperature",
            min_update_interval=300.0,
        )
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.throttled"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture):
            await sensor.async_added_to_hass()

        cb(MagicMock(payload=json.dumps({"NeoPool": {"Temperature": 25.5}})))
        # Rewind the throttle bookkeeping past the window
        sensor._last_write_ts -= 301
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Temperature": 26.0}})))

        assert sensor.async_write_ha_state.call_count == 2

    @pytest.mark.asyncio
    async def test_unavailable_resets_throttle(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Going unavailable resets throttle so the next available update writes."""
        desc = NeoPoolSensorEntityDescription(
            key="throttled",
            name="Throttled",
            json_path="NeoPool.Temperature",
            min_update_interval=300.0,
        )
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.throttled"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture):
            await sensor.async_added_to_hass()

        cb(MagicMock(payload=json.dumps({"NeoPool": {"Temperature": 25.5}})))
        # Payload now without Temperature → unavailable, throttle resets
        cb(MagicMock(payload=json.dumps({"NeoPool": {}})))
        assert sensor._last_write_ts is None
        # Next available update writes immediately even within nominal window
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Temperature": 27.0}})))
        # Calls: write (25.5) + write (unavailable) + write (27.0)
        assert sensor.async_write_ha_state.call_count == 3

    @pytest.mark.asyncio
    async def test_cumulative_first_sample_baseline(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """First raw sample establishes baseline without inflating cumulative."""
        desc = NeoPoolCumulativeSensorEntityDescription(
            key="cum",
            name="Cumulative",
            json_path="NeoPool.Connection.MBRequests",
            min_update_interval=0.0,  # no throttle for test simplicity
        )
        sensor = NeoPoolCumulativeSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.cum"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        # No prior state to restore
        with (
            patch.object(NeoPoolCumulativeSensor, "async_get_last_state", return_value=None),
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
        ):
            await sensor.async_added_to_hass()

        # First sample of a huge Tasmota counter — must NOT fold into cumulative
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 1_300_000}}})))
        assert sensor._attr_native_value == 0.0
        assert sensor._last_raw == 1_300_000

    @pytest.mark.asyncio
    async def test_cumulative_accumulates_delta(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Subsequent samples add (new - last_raw) to the cumulative."""
        desc = NeoPoolCumulativeSensorEntityDescription(
            key="cum",
            name="Cumulative",
            json_path="NeoPool.Connection.MBRequests",
            min_update_interval=0.0,
        )
        sensor = NeoPoolCumulativeSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.cum"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        with (
            patch.object(NeoPoolCumulativeSensor, "async_get_last_state", return_value=None),
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
        ):
            await sensor.async_added_to_hass()

        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 1000}}})))
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 1050}}})))
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 1080}}})))
        # 0 + (1050-1000) + (1080-1050) = 80
        assert sensor._attr_native_value == 80.0

    @pytest.mark.asyncio
    async def test_cumulative_handles_tasmota_reboot(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """When the raw counter drops, treat new value as delta from 0 (reboot)."""
        desc = NeoPoolCumulativeSensorEntityDescription(
            key="cum",
            name="Cumulative",
            json_path="NeoPool.Connection.MBRequests",
            min_update_interval=0.0,
        )
        sensor = NeoPoolCumulativeSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.cum"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        with (
            patch.object(NeoPoolCumulativeSensor, "async_get_last_state", return_value=None),
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
        ):
            await sensor.async_added_to_hass()

        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 1_000_000}}})))
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 1_000_500}}})))
        # Tasmota reboot — counter drops back to 0 and starts climbing
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 200}}})))
        # 0 + 500 + 200 = 700 (the 200 is treated as the new delta from 0)
        assert sensor._attr_native_value == 700.0
        assert sensor._last_raw == 200

    @pytest.mark.asyncio
    async def test_cumulative_restores_prior_state(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Cumulative is restored from prior HA session via RestoreEntity."""
        desc = NeoPoolCumulativeSensorEntityDescription(
            key="cum",
            name="Cumulative",
            json_path="NeoPool.Connection.MBRequests",
            min_update_interval=0.0,
        )
        sensor = NeoPoolCumulativeSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.cum"
        sensor.async_write_ha_state = MagicMock()

        cb = None

        async def capture(hass, topic, callback, **kwargs):
            nonlocal cb
            if "SENSOR" in topic:
                cb = callback
            return MagicMock()

        # Pretend HA last recorded 42,000 for this entity
        prior_state = MagicMock()
        prior_state.state = "42000"
        with (
            patch.object(NeoPoolCumulativeSensor, "async_get_last_state", return_value=prior_state),
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
        ):
            await sensor.async_added_to_hass()

        # Native value restored before any SENSOR arrives
        assert sensor._cumulative == 42000.0
        assert sensor._attr_native_value == 42000.0

        # First sample establishes baseline; doesn't change cumulative
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 500}}})))
        assert sensor._attr_native_value == 42000.0
        # Next sample adds the delta
        cb(MagicMock(payload=json.dumps({"NeoPool": {"Connection": {"MBRequests": 600}}})))
        assert sensor._attr_native_value == 42100.0

    def test_connection_entities_are_cumulative(self) -> None:
        """The 4 connection diagnostic entities must use the cumulative class."""
        for key in (
            "connection_requests",
            "connection_responses",
            "connection_no_response",
            "connection_out_of_range",
        ):
            desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
            assert isinstance(desc, NeoPoolCumulativeSensorEntityDescription), key
            assert desc.min_update_interval == 3600.0, key

    def test_controller_time_throttled_and_enabled(self) -> None:
        """controller_time should be throttled to 5 min and enabled by default."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "controller_time")
        assert desc.min_update_interval == 300.0
        # entity_registry_enabled_default defaults to True when not overridden
        assert desc.entity_registry_enabled_default is True


class TestConnectionRateSensor:
    """Tests for NeoPoolConnectionRateSensor (reads from runtime_data tracker)."""

    @pytest.mark.asyncio
    async def test_rate_sensor_reads_tracker_on_dispatch(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Dispatcher signal triggers reading the tracker's current rate."""

        tracker = ConnectionRateTracker(window_seconds=60.0)
        tracker.update(timestamp=1000.0, requests=100, errors=1)
        tracker.update(timestamp=1010.0, requests=200, errors=3)
        # (3-1)/(200-100) * 100 = 2%
        mock_config_entry.runtime_data.connection_rate_tracker = tracker

        sensor = NeoPoolConnectionRateSensor(mock_config_entry)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.neopool_connection_error_rate"
        sensor.async_write_ha_state = MagicMock()

        # Pretend the dispatcher fired
        sensor._handle_rate_update()
        assert sensor._attr_native_value == 2.0
        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_sensor_none_when_tracker_has_no_data(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Insufficient samples → tracker returns None → entity value is None."""

        mock_config_entry.runtime_data.connection_rate_tracker = ConnectionRateTracker(60.0)
        sensor = NeoPoolConnectionRateSensor(mock_config_entry)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.neopool_connection_error_rate"
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_rate_update()
        assert sensor._attr_native_value is None
