"""Tests for the AUX operating-mode sensors (NeoPool.Relay.AuxMode, Tasmota 15.6.0.1+)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    AUX_OPERATING_MODE_MAP,
    JSON_PATH_RELAY_AUX_MODE,
)
from custom_components.sugar_valley_neopool.sensor import (
    SENSOR_DESCRIPTIONS,
    NeoPoolSensor,
    _aux_operating_mode_fn,
)
from homeassistant.components.sensor import SensorDeviceClass

AUX_MODE_KEYS = [f"aux{n}_operating_mode" for n in range(1, 5)]


class TestAuxOperatingModeDescriptions:
    """The four enum sensors and their wiring."""

    def test_four_enum_sensors(self) -> None:
        """One ENUM sensor per AUX, gated on the AuxMode array path."""
        descs = [d for d in SENSOR_DESCRIPTIONS if d.key in AUX_MODE_KEYS]
        assert [d.key for d in descs] == AUX_MODE_KEYS
        for desc in descs:
            assert desc.device_class == SensorDeviceClass.ENUM
            assert desc.options == ["manual", "timer", "countdown"]
            assert desc.json_path == JSON_PATH_RELAY_AUX_MODE
            assert desc.payload_fn is not None

    def test_operating_mode_map_matches_driver(self) -> None:
        """Values follow arendst/Tasmota PR #24998: 0 Manual, 1 Timer, 2 Countdown."""
        assert AUX_OPERATING_MODE_MAP == {0: "manual", 1: "timer", 2: "countdown"}

    def test_each_sensor_reads_its_own_index(self) -> None:
        """aux<n> reads AuxMode[n-1]."""
        payload = {"NeoPool": {"Relay": {"AuxMode": [0, 1, 2, -1]}}}
        descs = {d.key: d for d in SENSOR_DESCRIPTIONS if d.key in AUX_MODE_KEYS}
        assert descs["aux1_operating_mode"].payload_fn(payload) == "manual"
        assert descs["aux2_operating_mode"].payload_fn(payload) == "timer"
        assert descs["aux3_operating_mode"].payload_fn(payload) == "countdown"
        assert descs["aux4_operating_mode"].payload_fn(payload) is None


class TestAuxOperatingModeFn:
    """payload_fn edge cases."""

    def test_missing_array(self) -> None:
        """No AuxMode key (older Tasmota) -> None."""
        assert _aux_operating_mode_fn(0)({"NeoPool": {"Relay": {"Aux": [0, 0, 0, 0]}}}) is None

    def test_not_a_list(self) -> None:
        """A scalar where the array is expected -> None."""
        assert _aux_operating_mode_fn(0)({"NeoPool": {"Relay": {"AuxMode": 1}}}) is None

    def test_short_array(self) -> None:
        """Index beyond the array -> None."""
        assert _aux_operating_mode_fn(3)({"NeoPool": {"Relay": {"AuxMode": [0, 1]}}}) is None

    def test_non_numeric_value(self) -> None:
        """Garbage element -> None."""
        assert _aux_operating_mode_fn(0)({"NeoPool": {"Relay": {"AuxMode": ["x"]}}}) is None

    def test_string_digits_accepted(self) -> None:
        """Numeric strings map like ints."""
        assert _aux_operating_mode_fn(0)({"NeoPool": {"Relay": {"AuxMode": ["2"]}}}) == "countdown"


class TestAuxOperatingModeSensor:
    """End-to-end through the SENSOR callback."""

    @pytest.mark.asyncio
    async def test_sensor_tracks_mode_and_availability(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock, sample_payload: dict[str, Any]
    ) -> None:
        """Mode follows the pushed array; absent array or unknown value -> unavailable."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "aux2_operating_mode")
        sensor = NeoPoolSensor(mock_config_entry, desc)
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.neopool_aux2_operating_mode"
        sensor.async_write_ha_state = MagicMock()

        sensor_cb = None

        async def capture(hass, topic, cb, **kwargs):
            nonlocal sensor_cb
            if "SENSOR" in topic:
                sensor_cb = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture):
            await sensor.async_added_to_hass()

        msg = MagicMock()

        # Older firmware: no AuxMode array at all -> unavailable.
        msg.payload = json.dumps(sample_payload)
        sensor_cb(msg)
        assert sensor._attr_available is False
        assert sensor._attr_native_value is None

        payload = json.loads(json.dumps(sample_payload))
        payload["NeoPool"]["Relay"]["AuxMode"] = [0, 1, 2, 0]
        msg.payload = json.dumps(payload)
        sensor_cb(msg)
        assert sensor._attr_available is True
        assert sensor._attr_native_value == "timer"

        payload["NeoPool"]["Relay"]["AuxMode"] = [0, -1, 2, 0]
        msg.payload = json.dumps(payload)
        sensor_cb(msg)
        assert sensor._attr_available is False
        assert sensor._attr_native_value is None
