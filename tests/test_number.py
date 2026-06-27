"""Tests for NeoPool number platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_CHLORINE,
    CMD_HYDROLYSIS,
    CMD_IONIZATION,
    CMD_PH_MAX,
    CMD_PH_MIN,
    CMD_REDOX,
    JSON_PATH_CHLORINE_SETPOINT,
    JSON_PATH_IONIZATION_MAX,
    JSON_PATH_IONIZATION_SETPOINT,
    REG_HIDRO_COVER_REDUCTION,
    SHIFT_HIDRO_SHUTDOWN_TEMP,
)
from custom_components.sugar_valley_neopool.number import (
    NUMBER_DESCRIPTIONS,
    REGISTER_BYTE_NUMBER_DESCRIPTIONS,
    REGISTER_NUMBER_DESCRIPTIONS,
    NeoPoolNumber,
    NeoPoolNumberEntityDescription,
    NeoPoolRegisterByteNumber,
    NeoPoolRegisterNumber,
    async_setup_entry,
)
from homeassistant.components.number import NumberDeviceClass, NumberMode


class TestNumberDescriptions:
    """Tests for number entity descriptions."""

    def test_number_descriptions_exist(self) -> None:
        """Test that number descriptions are defined."""
        assert len(NUMBER_DESCRIPTIONS) > 0

    def test_ph_min_description(self) -> None:
        """Test pH min number description."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "ph_min")

        assert desc.device_class == NumberDeviceClass.PH
        assert desc.native_min_value == 0.0
        assert desc.native_max_value == 14.0
        assert desc.native_step == 0.1
        assert desc.mode == NumberMode.SLIDER
        assert desc.json_path == "NeoPool.pH.Min"
        assert desc.command == CMD_PH_MIN

    def test_ph_max_description(self) -> None:
        """Test pH max number description."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "ph_max")

        assert desc.device_class == NumberDeviceClass.PH
        assert desc.json_path == "NeoPool.pH.Max"
        assert desc.command == CMD_PH_MAX

    def test_redox_setpoint_description(self) -> None:
        """Test redox setpoint number description."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "redox_setpoint")

        assert desc.native_min_value == 0
        assert desc.native_max_value == 1000
        assert desc.native_step == 1
        assert desc.json_path == "NeoPool.Redox.Setpoint"
        assert desc.command == CMD_REDOX

    def test_hydrolysis_setpoint_description(self) -> None:
        """Test hydrolysis setpoint number description."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "hydrolysis_setpoint")

        assert desc.native_min_value == 0
        assert desc.native_max_value == 100
        assert desc.json_path == "NeoPool.Hydrolysis.Percent.Setpoint"
        assert desc.command == CMD_HYDROLYSIS
        assert desc.command_template == "{value} %"

    def test_chlorine_setpoint_description(self) -> None:
        """Test chlorine setpoint number description."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "chlorine_setpoint")

        assert desc.native_unit_of_measurement == "ppm"
        assert desc.native_min_value == 0
        assert desc.native_max_value == 10
        assert desc.native_step == 0.1
        assert desc.mode == NumberMode.SLIDER
        assert desc.json_path == JSON_PATH_CHLORINE_SETPOINT
        assert desc.command == CMD_CHLORINE
        assert desc.max_json_path is None

    def test_ionization_setpoint_description(self) -> None:
        """Test ionization setpoint number description."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "ionization_setpoint")
        assert desc.native_min_value == 0
        assert desc.native_step == 0.1
        assert desc.json_path == JSON_PATH_IONIZATION_SETPOINT
        assert desc.command == CMD_IONIZATION
        assert desc.command_template is None
        assert desc.max_json_path == JSON_PATH_IONIZATION_MAX

    def test_all_descriptions_have_command(self) -> None:
        """Test all descriptions have command field."""
        for desc in NUMBER_DESCRIPTIONS:
            assert desc.command is not None
            assert desc.json_path is not None


class TestNeoPoolNumber:
    """Tests for NeoPoolNumber entity."""

    def test_number_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test number initialization."""
        desc = NeoPoolNumberEntityDescription(
            key="test_number",
            name="Test Number",
            json_path="NeoPool.Test.Value",
            command="NPTestValue",
        )

        number = NeoPoolNumber(mock_config_entry, desc)

        assert number.entity_description == desc
        assert number._attr_native_value is None
        assert number._attr_unique_id == "neopool_mqtt_ABC123_test_number"

    @pytest.mark.asyncio
    async def test_number_set_value_simple(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test setting number value without template."""
        desc = NeoPoolNumberEntityDescription(
            key="ph_min",
            name="pH Min",
            json_path="NeoPool.pH.Min",
            command=CMD_PH_MIN,
            native_step=0.1,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await number.async_set_native_value(7.2)

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_PH_MIN}",
                "7.2",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_number_set_value_integer(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test setting number value with integer step."""
        desc = NeoPoolNumberEntityDescription(
            key="redox_setpoint",
            name="Redox Setpoint",
            json_path="NeoPool.Redox.Setpoint",
            command=CMD_REDOX,
            native_step=1,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await number.async_set_native_value(750.0)

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_REDOX}",
                "750",  # Integer format
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_number_set_value_with_template(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test setting number value with command template."""
        desc = NeoPoolNumberEntityDescription(
            key="hydrolysis_setpoint",
            name="Hydrolysis Setpoint",
            json_path="NeoPool.Hydrolysis.Percent.Setpoint",
            command=CMD_HYDROLYSIS,
            command_template="{value} %",
            native_step=1,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await number.async_set_native_value(60.0)

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_HYDROLYSIS}",
                "60 %",  # Template format
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_number_state_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test number state updates from MQTT message."""
        desc = NeoPoolNumberEntityDescription(
            key="ph_min",
            name="pH Min",
            json_path="NeoPool.pH.Min",
            command=CMD_PH_MIN,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.ph_min"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # pH.Min = 7.0 in sample payload
        assert number._attr_native_value == 7.0
        assert number._attr_available is True

    @pytest.mark.asyncio
    async def test_number_redox_setpoint_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test redox setpoint updates from MQTT."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "redox_setpoint")

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.redox_setpoint"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Redox.Setpoint = 700 in sample payload
        assert number._attr_native_value == 700.0

    @pytest.mark.asyncio
    async def test_number_hydrolysis_setpoint_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test hydrolysis setpoint updates from MQTT."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "hydrolysis_setpoint")

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.hydrolysis_setpoint"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Hydrolysis.Percent.Setpoint = 60 in sample payload
        assert number._attr_native_value == 60.0

    @pytest.mark.asyncio
    async def test_number_chlorine_setpoint_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test chlorine setpoint updates from MQTT."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "chlorine_setpoint")

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.chlorine_setpoint"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Chlorine.Setpoint = 1.5 in sample payload
        assert number._attr_native_value == 1.5
        assert number._attr_available is True

    @pytest.mark.asyncio
    async def test_number_ionization_setpoint_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test ionization setpoint updates from MQTT with dynamic max."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "ionization_setpoint")

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.ionization_setpoint"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Ionization.Setpoint = 3, Max = 10 in sample payload
        assert number._attr_native_value == 3.0
        assert number._attr_native_max_value == 10.0
        assert number._attr_available is True

    @pytest.mark.asyncio
    async def test_number_ionization_unavailable_without_max(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
    ) -> None:
        """Test ionization setpoint stays unavailable when max is missing."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "ionization_setpoint")

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.ionization_setpoint"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        # Send payload without Ionization.Max
        payload_no_max = {
            "NeoPool": {
                "Ionization": {
                    "Data": 5,
                    "Setpoint": 3,
                },
            },
        }
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(payload_no_max)
        sensor_callback(mock_msg)

        assert number._attr_available is False

    @pytest.mark.asyncio
    async def test_number_handles_missing_path(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number handles missing JSON path gracefully."""
        desc = NeoPoolNumberEntityDescription(
            key="test_number",
            name="Test Number",
            json_path="NeoPool.NonExistent.Value",
            command="NPTest",
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.test"
        number.async_write_ha_state = MagicMock()

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
            await number.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Other": "data"}})
        sensor_callback(mock_msg)

        assert number._attr_native_value is None
        assert number._attr_available is False
        number.async_write_ha_state.assert_called()


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_numbers(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all number entities."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Command numbers + register numbers + byte-packed register numbers.
        assert len(added_entities) == (
            len(NUMBER_DESCRIPTIONS)
            + len(REGISTER_NUMBER_DESCRIPTIONS)
            + len(REGISTER_BYTE_NUMBER_DESCRIPTIONS)
        )
        assert sum(isinstance(e, NeoPoolNumber) for e in added_entities) == len(NUMBER_DESCRIPTIONS)
        assert sum(isinstance(e, NeoPoolRegisterByteNumber) for e in added_entities) == len(
            REGISTER_BYTE_NUMBER_DESCRIPTIONS
        )


class TestNeoPoolRegisterNumber:
    """Tests for register-backed config numbers (heating/intelligent/pH delay)."""

    def _make(self, entry: MagicMock) -> tuple[NeoPoolRegisterNumber, Any]:
        desc = REGISTER_NUMBER_DESCRIPTIONS[0]  # heating_temp
        return NeoPoolRegisterNumber(entry, desc), desc

    def test_native_value_from_register_state(self, mock_config_entry: MagicMock) -> None:
        """native_value reflects the cached register value (None when unknown)."""
        num, desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        assert num.native_value is None
        mock_config_entry.runtime_data.register_state[desc.register] = 28
        assert num.native_value == 28

    def test_available_requires_gating_and_value(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + gating keys present + a cached value."""
        num, desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        num._attr_available = True
        num._gating_ok = False
        assert num.available is False
        num._gating_ok = True
        assert num.available is False
        mock_config_entry.runtime_data.register_state[desc.register] = 28
        assert num.available is True

    @pytest.mark.asyncio
    async def test_set_value_writes_register(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Setting a value writes the integer register and updates the cache."""
        num, desc = self._make(mock_config_entry)
        num.hass = mock_hass
        num.async_write_ha_state = MagicMock()
        mock_config_entry.runtime_data.register_state.clear()

        with patch.object(num, "_write_register", new_callable=AsyncMock) as mock_w:
            await num.async_set_native_value(30.0)
            mock_w.assert_awaited_once_with(desc.register, 30)
            assert mock_config_entry.runtime_data.register_state[desc.register] == 30


class TestNeoPoolRegisterByteNumber:
    """Tests for byte-packed config numbers (cover-% / shutdown-temp of 0x042D)."""

    def _make(self, entry: MagicMock, key: str) -> NeoPoolRegisterByteNumber:
        desc = next(d for d in REGISTER_BYTE_NUMBER_DESCRIPTIONS if d.key == key)
        return NeoPoolRegisterByteNumber(entry, desc)

    def test_native_value_extracts_byte(self, mock_config_entry: MagicMock) -> None:
        """Each number reads only its own byte of the shared register."""
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        # high byte (shutdown temp) = 12, low byte (cover %) = 40 -> 0x0C28
        rs[REG_HIDRO_COVER_REDUCTION] = (12 << SHIFT_HIDRO_SHUTDOWN_TEMP) | 40

        pct = self._make(mock_config_entry, "hydro_cover_reduction_pct")
        temp = self._make(mock_config_entry, "hydro_shutdown_temp")
        assert pct.native_value == 40
        assert temp.native_value == 12

    @pytest.mark.asyncio
    async def test_set_value_preserves_sibling_byte(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Writing one byte must not clobber the sibling byte of the register."""
        temp = self._make(mock_config_entry, "hydro_shutdown_temp")
        temp.hass = mock_hass
        temp.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[REG_HIDRO_COVER_REDUCTION] = (12 << SHIFT_HIDRO_SHUTDOWN_TEMP) | 40  # temp 12, % 40

        with patch.object(temp, "_write_register", new_callable=AsyncMock) as mock_w:
            await temp.async_set_native_value(15.0)
            expected = (15 << SHIFT_HIDRO_SHUTDOWN_TEMP) | 40  # temp 15, % preserved
            mock_w.assert_awaited_once_with(REG_HIDRO_COVER_REDUCTION, expected)
            assert rs[REG_HIDRO_COVER_REDUCTION] == expected

    @pytest.mark.asyncio
    async def test_no_write_when_value_uncached(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Without a cached register value, a blind RMW write is skipped."""
        pct = self._make(mock_config_entry, "hydro_cover_reduction_pct")
        pct.hass = mock_hass
        pct.async_write_ha_state = MagicMock()
        mock_config_entry.runtime_data.register_state.clear()

        with patch.object(pct, "_write_register", new_callable=AsyncMock) as mock_w:
            await pct.async_set_native_value(50.0)
            mock_w.assert_not_awaited()


class TestNeoPoolRegisterNumberGating:
    """Covers the register-number SENSOR gating + dispatcher subscription."""

    @pytest.mark.asyncio
    async def test_gating_tracked_and_handle_update(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """async_added_to_hass wires gating (heating+temperature) and the signal."""
        desc = next(d for d in REGISTER_NUMBER_DESCRIPTIONS if d.key == "heating_temp")
        num = NeoPoolRegisterNumber(mock_config_entry, desc)
        num.hass = mock_hass
        num.async_write_ha_state = MagicMock()

        sensor_cb = None

        async def capture(hass, topic, cb, **kwargs):
            nonlocal sensor_cb
            if "SENSOR" in topic:
                sensor_cb = cb
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
            patch(
                "custom_components.sugar_valley_neopool.number.async_dispatcher_connect",
                return_value=MagicMock(),
            ),
        ):
            await num.async_added_to_hass()

        # Both gating paths present -> available gate satisfied.
        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Relay": {"Heating": 1}, "Temperature": 25.0}})
        sensor_cb(msg)
        assert num._gating_ok is True

        # Missing heating relay -> gate fails.
        msg.payload = json.dumps({"NeoPool": {"Temperature": 25.0}})
        sensor_cb(msg)
        assert num._gating_ok is False

        # The dispatcher-driven refresh writes state.
        num.async_write_ha_state.reset_mock()
        num._handle_register_update()
        num.async_write_ha_state.assert_called_once()
