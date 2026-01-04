"""Tests for NeoPool switch platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import CMD_AUX1, CMD_FILTRATION, CMD_LIGHT
from custom_components.sugar_valley_neopool.switch import (
    SWITCH_DESCRIPTIONS,
    NeoPoolSwitch,
    NeoPoolSwitchEntityDescription,
    async_setup_entry,
)


class TestSwitchDescriptions:
    """Tests for switch entity descriptions."""

    def test_switch_descriptions_exist(self) -> None:
        """Test that switch descriptions are defined."""
        assert len(SWITCH_DESCRIPTIONS) > 0

    def test_filtration_switch_description(self) -> None:
        """Test filtration switch description."""
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "filtration")

        assert desc.json_path == "NeoPool.Filtration.State"
        assert desc.command == CMD_FILTRATION
        assert desc.payload_on == "1"
        assert desc.payload_off == "0"

    def test_light_switch_description(self) -> None:
        """Test light switch description."""
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "light")

        assert desc.json_path == "NeoPool.Light"
        assert desc.command == CMD_LIGHT

    def test_aux_switches_exist(self) -> None:
        """Test aux switch descriptions exist."""
        aux_keys = ["aux1", "aux2", "aux3", "aux4"]
        for key in aux_keys:
            desc = next((d for d in SWITCH_DESCRIPTIONS if d.key == key), None)
            assert desc is not None, f"Missing switch: {key}"
            assert "Aux" in desc.json_path

    def test_all_descriptions_have_command(self) -> None:
        """Test all descriptions have command field."""
        for desc in SWITCH_DESCRIPTIONS:
            assert desc.command is not None
            assert desc.json_path is not None


class TestNeoPoolSwitch:
    """Tests for NeoPoolSwitch entity."""

    def test_switch_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test switch initialization."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
            command="NPTest",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)

        assert switch.entity_description == desc
        assert switch._attr_is_on is None
        assert switch._attr_unique_id == "neopool_mqtt_ABC123_test_switch"

    @pytest.mark.asyncio
    async def test_switch_turn_on(self, mock_config_entry: MagicMock, mock_hass: MagicMock) -> None:
        """Test switch turn on command."""
        desc = NeoPoolSwitchEntityDescription(
            key="filtration",
            name="Filtration",
            json_path="NeoPool.Filtration.State",
            command=CMD_FILTRATION,
            payload_on="1",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await switch.async_turn_on()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_FILTRATION}",
                "1",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_switch_turn_off(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch turn off command."""
        desc = NeoPoolSwitchEntityDescription(
            key="filtration",
            name="Filtration",
            json_path="NeoPool.Filtration.State",
            command=CMD_FILTRATION,
            payload_off="0",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await switch.async_turn_off()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_FILTRATION}",
                "0",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_switch_state_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test switch state updates from MQTT message."""
        desc = NeoPoolSwitchEntityDescription(
            key="filtration",
            name="Filtration",
            json_path="NeoPool.Filtration.State",
            command=CMD_FILTRATION,
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.filtration"
        switch.async_write_ha_state = MagicMock()

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
            await switch.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Filtration.State = 1 in sample payload
        assert switch._attr_is_on is True
        assert switch._attr_available is True

    @pytest.mark.asyncio
    async def test_switch_aux_array_access(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch handles array access for aux relays."""
        desc = NeoPoolSwitchEntityDescription(
            key="aux1",
            name="AUX1",
            json_path="NeoPool.Relay.Aux.0",
            command=CMD_AUX1,
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.aux1"
        switch.async_write_ha_state = MagicMock()

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
            await switch.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Relay": {"Aux": [1, 0, 0, 0]}}})
        sensor_callback(mock_msg)

        # Aux[0] = 1
        assert switch._attr_is_on is True

    @pytest.mark.asyncio
    async def test_switch_light_state(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test light switch state from MQTT."""
        desc = NeoPoolSwitchEntityDescription(
            key="light",
            name="Light",
            json_path="NeoPool.Light",
            command=CMD_LIGHT,
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.light"
        switch.async_write_ha_state = MagicMock()

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
            await switch.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Light": 0}})
        sensor_callback(mock_msg)

        assert switch._attr_is_on is False

    @pytest.mark.asyncio
    async def test_switch_handles_missing_path(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch handles missing JSON path gracefully."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.NonExistent.State",
            command="NPTest",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.test"
        switch.async_write_ha_state = MagicMock()

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
            await switch.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Other": "data"}})
        sensor_callback(mock_msg)

        assert switch._attr_is_on is None
        switch.async_write_ha_state.assert_not_called()


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_switches(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all switch entities."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        assert len(added_entities) == len(SWITCH_DESCRIPTIONS)
        assert all(isinstance(e, NeoPoolSwitch) for e in added_entities)
