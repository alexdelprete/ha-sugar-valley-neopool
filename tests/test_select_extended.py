"""Extended tests for NeoPool select platform - edge cases."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import BOOST_MODE_MAP
from custom_components.sugar_valley_neopool.select import (
    SELECT_DESCRIPTIONS,
    NeoPoolSelect,
    NeoPoolSelectEntityDescription,
    create_value_fn,
)


class TestCreateValueFnExtended:
    """Extended tests for create_value_fn helper."""

    def test_create_value_fn_float_input(self) -> None:
        """Test value function with float input."""
        options_map = {0: "Off", 1: "On"}
        value_fn = create_value_fn(options_map)

        # Float that converts to valid int
        assert value_fn(1.0) == "On"
        assert value_fn(0.0) == "Off"

    def test_create_value_fn_negative(self) -> None:
        """Test value function with negative value."""
        options_map = {-1: "Error", 0: "Off", 1: "On"}
        value_fn = create_value_fn(options_map)

        assert value_fn(-1) == "Error"
        assert value_fn("-1") == "Error"


class TestSelectDescriptionsExtended:
    """Extended tests for select descriptions."""

    def test_all_selects_have_value_fn(self) -> None:
        """Test all selects have value_fn."""
        for desc in SELECT_DESCRIPTIONS:
            assert desc.value_fn is not None

    def test_boost_mode_options(self) -> None:
        """Test boost mode has correct options."""
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "boost_mode")
        assert "Off" in desc.options
        assert "On" in desc.options


class TestNeoPoolSelectExtended:
    """Extended tests for NeoPoolSelect entity."""

    @pytest.mark.asyncio
    async def test_select_lwt_availability(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select availability follows LWT."""
        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test.Mode",
            command="NPTestMode",
            options_map={0: "Off", 1: "On"},
            options=["Off", "On"],
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass
        select.entity_id = "select.test"
        select.async_write_ha_state = MagicMock()

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
            await select.async_added_to_hass()

        # Initially unavailable
        assert select._attr_available is False

        # LWT Online
        mock_lwt = MagicMock()
        mock_lwt.payload = "Online"
        lwt_callback(mock_lwt)
        assert select._attr_available is True

    @pytest.mark.asyncio
    async def test_select_option_reverse_lookup(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select option sends correct command via reverse lookup."""
        desc = NeoPoolSelectEntityDescription(
            key="boost_mode",
            name="Boost Mode",
            json_path="NeoPool.Hydrolysis.Boost",
            command="NPBoost",
            options_map=BOOST_MODE_MAP,
            options=list(BOOST_MODE_MAP.values()),
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            # Select "On" which maps to key 1
            await select.async_select_option("On")

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            # Payload should be "1" (the key for "On")
            assert call_args[0][2] == "1"

    @pytest.mark.asyncio
    async def test_select_state_from_string_value(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select state from string numeric value."""
        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test.Mode",
            command="NPTestMode",
            options_map={0: "Off", 1: "On", 2: "Auto"},
            options=["Off", "On", "Auto"],
            value_fn=create_value_fn({0: "Off", 1: "On", 2: "Auto"}),
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass
        select.entity_id = "select.test"
        select.async_write_ha_state = MagicMock()

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
            await select.async_added_to_hass()

        # String "2" should map to "Auto"
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Mode": "2"}}})
        sensor_callback(mock_msg)

        assert select._attr_current_option == "Auto"

    @pytest.mark.asyncio
    async def test_select_no_command_for_unknown_option(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select doesn't send command for unknown option."""
        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test.Mode",
            command="NPTestMode",
            options_map={0: "Off", 1: "On"},
            options=["Off", "On"],
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await select.async_select_option("NonExistent")

            mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_multiple_state_updates(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select handles multiple state updates."""
        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Filtration.Mode",
            command="NPFiltrationMode",
            options_map={0: "Manual", 1: "Auto", 2: "Heating"},
            options=["Manual", "Auto", "Heating"],
            value_fn=create_value_fn({0: "Manual", 1: "Auto", 2: "Heating"}),
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass
        select.entity_id = "select.test"
        select.async_write_ha_state = MagicMock()

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
            await select.async_added_to_hass()

        mock_msg = MagicMock()

        # Update to Manual
        mock_msg.payload = json.dumps({"NeoPool": {"Filtration": {"Mode": 0}}})
        sensor_callback(mock_msg)
        assert select._attr_current_option == "Manual"

        # Update to Auto
        mock_msg.payload = json.dumps({"NeoPool": {"Filtration": {"Mode": 1}}})
        sensor_callback(mock_msg)
        assert select._attr_current_option == "Auto"

        # Update to Heating
        mock_msg.payload = json.dumps({"NeoPool": {"Filtration": {"Mode": 2}}})
        sensor_callback(mock_msg)
        assert select._attr_current_option == "Heating"

        assert select.async_write_ha_state.call_count == 3
