"""Tests for NeoPool select platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    BOOST_MODE_MAP,
    CMD_BOOST,
    CMD_FILTRATION_MODE,
    CMD_FILTRATION_SPEED,
    FILTRATION_MODE_MAP,
    FILTRATION_SPEED_MAP,
)
from custom_components.sugar_valley_neopool.select import (
    SELECT_DESCRIPTIONS,
    NeoPoolSelect,
    NeoPoolSelectEntityDescription,
    async_setup_entry,
    create_value_fn,
)


class TestCreateValueFn:
    """Tests for create_value_fn helper."""

    def test_create_value_fn_valid_mapping(self) -> None:
        """Test value function with valid mapping."""
        options_map = {0: "Off", 1: "On", 2: "Auto"}
        value_fn = create_value_fn(options_map)

        assert value_fn(0) == "Off"
        assert value_fn(1) == "On"
        assert value_fn(2) == "Auto"

    def test_create_value_fn_string_input(self) -> None:
        """Test value function with string input."""
        options_map = {0: "Off", 1: "On"}
        value_fn = create_value_fn(options_map)

        assert value_fn("1") == "On"
        assert value_fn("0") == "Off"

    def test_create_value_fn_invalid_value(self) -> None:
        """Test value function with invalid value."""
        options_map = {0: "Off", 1: "On"}
        value_fn = create_value_fn(options_map)

        assert value_fn(99) is None
        assert value_fn("invalid") is None

    def test_create_value_fn_none_input(self) -> None:
        """Test value function with None input."""
        options_map = {0: "Off", 1: "On"}
        value_fn = create_value_fn(options_map)

        assert value_fn(None) is None


class TestSelectDescriptions:
    """Tests for select entity descriptions."""

    def test_select_descriptions_exist(self) -> None:
        """Test that select descriptions are defined."""
        assert len(SELECT_DESCRIPTIONS) > 0

    def test_filtration_mode_description(self) -> None:
        """Test filtration mode select description."""
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "filtration_mode")

        assert desc.json_path == "NeoPool.Filtration.Mode"
        assert desc.command == CMD_FILTRATION_MODE
        assert desc.options_map == FILTRATION_MODE_MAP
        assert desc.options == list(FILTRATION_MODE_MAP.values())

    def test_filtration_speed_description(self) -> None:
        """Test filtration speed select description."""
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "filtration_speed")

        assert desc.json_path == "NeoPool.Filtration.Speed"
        assert desc.command == CMD_FILTRATION_SPEED
        assert desc.options_map == FILTRATION_SPEED_MAP

    def test_boost_mode_description(self) -> None:
        """Test boost mode select description."""
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "boost_mode")

        assert desc.json_path == "NeoPool.Hydrolysis.Boost"
        assert desc.command == CMD_BOOST
        assert desc.options_map == BOOST_MODE_MAP

    def test_all_descriptions_have_options(self) -> None:
        """Test all descriptions have options list."""
        for desc in SELECT_DESCRIPTIONS:
            assert desc.options is not None
            assert len(desc.options) > 0
            assert desc.options_map is not None


class TestNeoPoolSelect:
    """Tests for NeoPoolSelect entity."""

    def test_select_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test select initialization."""
        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test.Mode",
            command="NPTestMode",
            options_map={0: "Off", 1: "On"},
            options=["Off", "On"],
        )

        select = NeoPoolSelect(mock_config_entry, desc)

        assert select.entity_description == desc
        assert select._attr_current_option is None
        assert select._attr_options == ["Off", "On"]
        assert select._attr_unique_id == "neopool_mqtt_ABC123_test_select"

    @pytest.mark.asyncio
    async def test_select_option_command(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select option sends correct command."""
        desc = NeoPoolSelectEntityDescription(
            key="filtration_mode",
            name="Filtration Mode",
            json_path="NeoPool.Filtration.Mode",
            command=CMD_FILTRATION_MODE,
            options_map=FILTRATION_MODE_MAP,
            options=list(FILTRATION_MODE_MAP.values()),
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await select.async_select_option("Auto")

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_FILTRATION_MODE}",
                "1",  # Auto = 1 in FILTRATION_MODE_MAP
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_select_option_invalid(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select option with invalid option does not send command."""
        desc = NeoPoolSelectEntityDescription(
            key="filtration_mode",
            name="Filtration Mode",
            json_path="NeoPool.Filtration.Mode",
            command=CMD_FILTRATION_MODE,
            options_map=FILTRATION_MODE_MAP,
            options=list(FILTRATION_MODE_MAP.values()),
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await select.async_select_option("InvalidOption")

            mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_select_state_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test select state updates from MQTT message."""
        desc = NeoPoolSelectEntityDescription(
            key="filtration_mode",
            name="Filtration Mode",
            json_path="NeoPool.Filtration.Mode",
            command=CMD_FILTRATION_MODE,
            options_map=FILTRATION_MODE_MAP,
            options=list(FILTRATION_MODE_MAP.values()),
        )

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass
        select.entity_id = "select.filtration_mode"
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
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Filtration.Mode = 1 in sample payload = "Auto"
        assert select._attr_current_option == "Auto"
        assert select._attr_available is True

    @pytest.mark.asyncio
    async def test_select_with_custom_value_fn(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select with custom value function."""
        custom_map = {0: "Off", 1: "On"}

        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test.State",
            command="NPTest",
            options_map=custom_map,
            options=["Off", "On"],
            value_fn=lambda x: "Custom" if x == 99 else custom_map.get(int(x)),
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
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": 99}}})
        sensor_callback(mock_msg)

        assert select._attr_current_option == "Custom"

    @pytest.mark.asyncio
    async def test_select_boost_mode(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test boost mode select."""
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "boost_mode")

        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = mock_hass

        with patch(
            "custom_components.sugar_valley_neopool.entity.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            # Select "On" option (value 1) - BOOST_MODE_MAP has {0: "Off", 1: "On", 2: "On (Redox)"}
            await select.async_select_option("On")

            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert CMD_BOOST in call_args[0][1]

    @pytest.mark.asyncio
    async def test_select_handles_none_option(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test select handles None option gracefully."""
        desc = NeoPoolSelectEntityDescription(
            key="test_select",
            name="Test Select",
            json_path="NeoPool.Test.Mode",
            command="NPTest",
            options_map={0: "Off", 1: "On"},
            options=["Off", "On"],
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

        # Send value that doesn't map to any option
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"Mode": 99}}})
        sensor_callback(mock_msg)

        # Should not update state for unmapped value
        assert select._attr_current_option is None


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_selects(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all select entities."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        assert len(added_entities) == len(SELECT_DESCRIPTIONS)
        assert all(isinstance(e, NeoPoolSelect) for e in added_entities)
