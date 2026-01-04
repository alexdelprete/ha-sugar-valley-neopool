"""Extended tests for NeoPool number platform - edge cases."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.number import (
    NUMBER_DESCRIPTIONS,
    NeoPoolNumber,
    NeoPoolNumberEntityDescription,
)


class TestNumberDescriptionsExtended:
    """Extended tests for number descriptions."""

    def test_all_numbers_have_step(self) -> None:
        """Test all numbers have native_step."""
        for desc in NUMBER_DESCRIPTIONS:
            assert desc.native_step is not None

    def test_ph_numbers_have_correct_range(self) -> None:
        """Test pH numbers have correct min/max range."""
        ph_descs = [d for d in NUMBER_DESCRIPTIONS if "ph_" in d.key]
        for desc in ph_descs:
            assert desc.native_min_value == 0.0
            assert desc.native_max_value == 14.0

    def test_hydrolysis_has_template(self) -> None:
        """Test hydrolysis setpoint has command template."""
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "hydrolysis_setpoint")
        assert desc.command_template == "{value} %"


class TestNeoPoolNumberExtended:
    """Extended tests for NeoPoolNumber entity."""

    @pytest.mark.asyncio
    async def test_number_lwt_availability(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number availability follows LWT."""
        desc = NeoPoolNumberEntityDescription(
            key="test_number",
            name="Test Number",
            json_path="NeoPool.Test.Value",
            command="NPTest",
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass
        number.entity_id = "number.test"
        number.async_write_ha_state = MagicMock()

        lwt_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal lwt_callback
            if "LWT" in topic:
                lwt_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await number.async_added_to_hass()

        # Initially unavailable
        assert number._attr_available is False

        # LWT Online
        mock_lwt = MagicMock()
        mock_lwt.payload = "Online"
        lwt_callback(mock_lwt)
        assert number._attr_available is True

    @pytest.mark.asyncio
    async def test_number_set_value_float_formatting(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number formats float value correctly."""
        desc = NeoPoolNumberEntityDescription(
            key="ph_min",
            name="pH Min",
            json_path="NeoPool.pH.Min",
            command="NPpHMin",
            native_step=0.1,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await number.async_set_native_value(7.25)

            mock_publish.assert_called_once()
            # Should format as float string
            assert mock_publish.call_args[0][2] == "7.25"

    @pytest.mark.asyncio
    async def test_number_set_value_integer_step(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number formats integer when step is 1."""
        desc = NeoPoolNumberEntityDescription(
            key="redox_setpoint",
            name="Redox Setpoint",
            json_path="NeoPool.Redox.Setpoint",
            command="NPRedox",
            native_step=1,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await number.async_set_native_value(750.0)

            mock_publish.assert_called_once()
            # Should format as integer string
            assert mock_publish.call_args[0][2] == "750"

    @pytest.mark.asyncio
    async def test_number_set_value_with_template_formatting(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number applies template correctly."""
        desc = NeoPoolNumberEntityDescription(
            key="hydrolysis_setpoint",
            name="Hydrolysis Setpoint",
            json_path="NeoPool.Hydrolysis.Percent.Setpoint",
            command="NPHydrolysis",
            command_template="{value} %",
            native_step=1,
        )

        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await number.async_set_native_value(75.0)

            mock_publish.assert_called_once()
            # Should apply template
            assert mock_publish.call_args[0][2] == "75 %"

    @pytest.mark.asyncio
    async def test_number_state_from_string(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number handles string value in payload."""
        desc = NeoPoolNumberEntityDescription(
            key="test_number",
            name="Test Number",
            json_path="NeoPool.Test.Value",
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

        # String numeric value
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Value": "42.5"}}})
        sensor_callback(mock_msg)

        assert number._attr_native_value == 42.5

    @pytest.mark.asyncio
    async def test_number_multiple_updates(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number handles multiple value updates."""
        desc = NeoPoolNumberEntityDescription(
            key="test_number",
            name="Test Number",
            json_path="NeoPool.pH.Min",
            command="NPpHMin",
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

        # First value
        mock_msg.payload = json.dumps({"NeoPool": {"pH": {"Min": 7.0}}})
        sensor_callback(mock_msg)
        assert number._attr_native_value == 7.0

        # Second value
        mock_msg.payload = json.dumps({"NeoPool": {"pH": {"Min": 7.2}}})
        sensor_callback(mock_msg)
        assert number._attr_native_value == 7.2

        # Third value
        mock_msg.payload = json.dumps({"NeoPool": {"pH": {"Min": 6.8}}})
        sensor_callback(mock_msg)
        assert number._attr_native_value == 6.8

        assert number.async_write_ha_state.call_count == 3

    @pytest.mark.asyncio
    async def test_number_zero_value(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test number handles zero value correctly."""
        desc = NeoPoolNumberEntityDescription(
            key="test_number",
            name="Test Number",
            json_path="NeoPool.Test.Value",
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
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Value": 0}}})
        sensor_callback(mock_msg)

        # Zero should be valid value, not None
        assert number._attr_native_value == 0.0
        number.async_write_ha_state.assert_called()
