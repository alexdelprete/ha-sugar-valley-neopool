"""Tests for NeoPool number platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_HYDROLYSIS,
    CMD_PH_MAX,
    CMD_PH_MIN,
    CMD_REDOX,
)
from custom_components.sugar_valley_neopool.number import (
    NUMBER_DESCRIPTIONS,
    NeoPoolNumber,
    NeoPoolNumberEntityDescription,
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
        number.async_write_ha_state.assert_not_called()


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

        assert len(added_entities) == len(NUMBER_DESCRIPTIONS)
        assert all(isinstance(e, NeoPoolNumber) for e in added_entities)
