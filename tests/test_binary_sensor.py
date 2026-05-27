"""Tests for NeoPool binary sensor platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    NeoPoolBinarySensor,
    NeoPoolBinarySensorEntityDescription,
    NeoPoolConnectionProblemBinarySensor,
    async_setup_entry,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_CONNECTION_ERROR_RATE_THRESHOLD,
    DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD,
)
from custom_components.sugar_valley_neopool.helpers import ConnectionRateTracker, bit_to_bool
from homeassistant.components.binary_sensor import BinarySensorDeviceClass


class TestBinarySensorDescriptions:
    """Tests for binary sensor entity descriptions."""

    def test_binary_sensor_descriptions_exist(self) -> None:
        """Test that binary sensor descriptions are defined."""
        assert len(BINARY_SENSOR_DESCRIPTIONS) > 0

    def test_modules_ph_description(self) -> None:
        """Test pH module binary sensor description."""
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "modules_ph")

        assert desc.json_path == "NeoPool.Modules.pH"
        assert desc.invert is False

    def test_water_flow_description(self) -> None:
        """Test water flow binary sensor with inversion."""
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "hydrolysis_water_flow")

        assert desc.device_class == BinarySensorDeviceClass.RUNNING
        assert desc.json_path == "NeoPool.Hydrolysis.FL1"
        assert desc.invert is True  # FL1=0 means flow OK

    def test_ph_tank_level_description(self) -> None:
        """Test pH tank level binary sensor with inversion."""
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "ph_tank_level")

        assert desc.device_class == BinarySensorDeviceClass.PROBLEM
        assert desc.invert is True  # Tank=0 means low

    def test_named_relay_state_descriptions(self) -> None:
        """Test named relay binary sensor descriptions exist."""
        relay_descs = [d for d in BINARY_SENSOR_DESCRIPTIONS if d.key.startswith("relay_")]

        # Named relay entities (functional state regardless of physical relay assignment)
        assert any(d.key == "relay_acid_state" for d in relay_descs)
        assert any(d.key == "relay_base_state" for d in relay_descs)
        assert any(d.key == "relay_redox_state" for d in relay_descs)

    def test_hydrolysis_redox_controlled_description(self) -> None:
        """Test hydrolysis redox controlled binary sensor description."""
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "hydrolysis_redox_controlled")

        assert desc.json_path == "NeoPool.Hydrolysis.Redox"
        assert desc.invert is False

    def test_all_descriptions_have_json_path(self) -> None:
        """Test all descriptions have json_path field."""
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            assert desc.json_path is not None
            assert desc.key is not None


class TestNeoPoolBinarySensor:
    """Tests for NeoPoolBinarySensor entity."""

    def test_binary_sensor_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test binary sensor initialization."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary_sensor",
            name="Test Binary Sensor",
            json_path="NeoPool.Test.Value",
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)

        assert sensor.entity_description == desc
        assert sensor._attr_is_on is None
        assert sensor._attr_unique_id == "neopool_mqtt_ABC123_test_binary_sensor"

    @pytest.mark.asyncio
    async def test_binary_sensor_processes_true(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor processes true value correctly."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary_sensor",
            name="Test Binary Sensor",
            json_path="NeoPool.Modules.pH",
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
        mock_msg.payload = json.dumps({"NeoPool": {"Modules": {"pH": 1}}})
        sensor_callback(mock_msg)

        assert sensor._attr_is_on is True
        assert sensor._attr_available is True

    @pytest.mark.asyncio
    async def test_binary_sensor_processes_false(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor processes false value correctly."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary_sensor",
            name="Test Binary Sensor",
            json_path="NeoPool.Modules.Chlorine",
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
        mock_msg.payload = json.dumps({"NeoPool": {"Modules": {"Chlorine": 0}}})
        sensor_callback(mock_msg)

        assert sensor._attr_is_on is False

    @pytest.mark.asyncio
    async def test_binary_sensor_invert_true(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor inverts value when invert=True."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary_sensor",
            name="Test Binary Sensor",
            json_path="NeoPool.Hydrolysis.FL1",
            invert=True,  # FL1=0 means OK (True), FL1=1 means alarm (False)
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

        # Value 0 should become True (inverted)
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Hydrolysis": {"FL1": 0}}})
        sensor_callback(mock_msg)

        assert sensor._attr_is_on is True  # Inverted: 0 -> False -> True

    @pytest.mark.asyncio
    async def test_binary_sensor_array_access(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test binary sensor handles array access in JSON path."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_relay_array",
            name="Test Relay Array",
            json_path="NeoPool.Relay.State.1",
            value_fn=lambda x: (
                bit_to_bool(x)
                if isinstance(x, (str, int))
                else (bit_to_bool(x[1]) if isinstance(x, list) and len(x) > 1 else None)
            ),
        )

        sensor = NeoPoolBinarySensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.test_relay_array"
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
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Relay.State[1] = 1 in sample payload
        assert sensor._attr_is_on is True

    @pytest.mark.asyncio
    async def test_binary_sensor_handles_missing_path(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test binary sensor handles missing JSON path gracefully."""
        desc = NeoPoolBinarySensorEntityDescription(
            key="test_binary_sensor",
            name="Test Binary Sensor",
            json_path="NeoPool.NonExistent.Path",
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
        mock_msg.payload = json.dumps({"NeoPool": {"Other": "data"}})
        sensor_callback(mock_msg)

        assert sensor._attr_is_on is None
        assert sensor._attr_available is False
        sensor.async_write_ha_state.assert_called()


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_binary_sensors(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all binary sensor entities.

        Setup creates one entity per BINARY_SENSOR_DESCRIPTIONS plus the
        standalone NeoPoolConnectionProblemBinarySensor (which reads from
        the shared ConnectionRateTracker, no description-driven JSON path).
        """

        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # +1 for the standalone NeoPoolConnectionProblemBinarySensor
        assert len(added_entities) == len(BINARY_SENSOR_DESCRIPTIONS) + 1
        assert all(
            isinstance(e, (NeoPoolBinarySensor, NeoPoolConnectionProblemBinarySensor))
            for e in added_entities
        )


class TestConnectionProblemBinarySensor:
    """Tests for NeoPoolConnectionProblemBinarySensor."""

    @pytest.mark.asyncio
    async def test_problem_on_when_rate_exceeds_threshold(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """is_on becomes True when the tracker's rate > threshold."""

        # Threshold = 5 %; tracker should report 10 %
        mock_config_entry.options = {CONF_CONNECTION_ERROR_RATE_THRESHOLD: 5.0}
        tracker = ConnectionRateTracker(window_seconds=60.0)
        tracker.update(timestamp=1000.0, requests=100, errors=0)
        tracker.update(timestamp=1010.0, requests=200, errors=10)
        mock_config_entry.runtime_data.connection_rate_tracker = tracker

        sensor = NeoPoolConnectionProblemBinarySensor(mock_config_entry)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.neopool_connection_problem"
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_rate_update()
        assert sensor._attr_is_on is True
        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_problem_off_when_rate_below_threshold(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """is_on stays False while rate is at/below threshold."""

        mock_config_entry.options = {CONF_CONNECTION_ERROR_RATE_THRESHOLD: 5.0}
        tracker = ConnectionRateTracker(window_seconds=60.0)
        tracker.update(timestamp=1000.0, requests=100, errors=0)
        tracker.update(timestamp=1010.0, requests=200, errors=2)  # 2 %
        mock_config_entry.runtime_data.connection_rate_tracker = tracker

        sensor = NeoPoolConnectionProblemBinarySensor(mock_config_entry)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.neopool_connection_problem"
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_rate_update()
        assert sensor._attr_is_on is False

    @pytest.mark.asyncio
    async def test_problem_holds_previous_state_on_none_rate(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Tracker rate=None (reboot / insufficient samples) → state unchanged."""

        mock_config_entry.options = {CONF_CONNECTION_ERROR_RATE_THRESHOLD: 5.0}
        # Empty tracker → rate is None
        mock_config_entry.runtime_data.connection_rate_tracker = ConnectionRateTracker(60.0)

        sensor = NeoPoolConnectionProblemBinarySensor(mock_config_entry)
        sensor.hass = mock_hass
        sensor.entity_id = "binary_sensor.neopool_connection_problem"
        sensor._attr_is_on = True  # pretend a previous state
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_rate_update()
        # Previous state preserved, no state write
        assert sensor._attr_is_on is True
        sensor.async_write_ha_state.assert_not_called()

    def test_threshold_read_from_options(self) -> None:
        """Threshold should come from CONF_CONNECTION_ERROR_RATE_THRESHOLD option."""

        entry = MagicMock()
        entry.options = {CONF_CONNECTION_ERROR_RATE_THRESHOLD: 7.5}
        entry.runtime_data.nodeid = "ABC"
        sensor = NeoPoolConnectionProblemBinarySensor(entry)
        assert sensor._threshold == 7.5

        # Fallback to default when option absent
        entry.options = {}
        sensor = NeoPoolConnectionProblemBinarySensor(entry)
        assert sensor._threshold == DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD
