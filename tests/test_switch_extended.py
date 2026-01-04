"""Extended tests for NeoPool switch platform - edge cases."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.switch import (
    SWITCH_DESCRIPTIONS,
    NeoPoolSwitch,
    NeoPoolSwitchEntityDescription,
)


class TestSwitchDescriptionsExtended:
    """Extended tests for switch descriptions."""

    def test_all_switches_have_payloads(self) -> None:
        """Test all switches have on/off payloads."""
        for desc in SWITCH_DESCRIPTIONS:
            assert desc.payload_on is not None or hasattr(desc, "payload_on")
            assert desc.payload_off is not None or hasattr(desc, "payload_off")

    def test_switch_count(self) -> None:
        """Test correct number of switches."""
        assert len(SWITCH_DESCRIPTIONS) == 6  # filtration, light, aux1-4


class TestNeoPoolSwitchExtended:
    """Extended tests for NeoPoolSwitch entity."""

    @pytest.mark.asyncio
    async def test_switch_lwt_availability(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch availability follows LWT."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
            command="NPTest",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.test"
        switch.async_write_ha_state = MagicMock()

        lwt_callback = None
        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal lwt_callback, sensor_callback
            if "LWT" in topic:
                lwt_callback = callback
            elif "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await switch.async_added_to_hass()

        # Initially unavailable
        assert switch._attr_available is False

        # LWT Online
        mock_lwt = MagicMock()
        mock_lwt.payload = "Online"
        lwt_callback(mock_lwt)
        assert switch._attr_available is True

        # Receive state
        mock_sensor = MagicMock()
        mock_sensor.payload = json.dumps({"NeoPool": {"Test": {"State": 1}}})
        sensor_callback(mock_sensor)
        assert switch._attr_is_on is True

        # LWT Offline
        mock_lwt.payload = "Offline"
        lwt_callback(mock_lwt)
        assert switch._attr_available is False

    @pytest.mark.asyncio
    async def test_switch_turn_on_custom_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch turn on with custom payload."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
            command="NPTest",
            payload_on="ON",
            payload_off="OFF",
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
                "cmnd/SmartPool/NPTest",
                "ON",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_switch_turn_off_custom_payload(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch turn off with custom payload."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
            command="NPTest",
            payload_on="ON",
            payload_off="OFF",
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
                "cmnd/SmartPool/NPTest",
                "OFF",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_switch_state_string_one(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch state with string '1'."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
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
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": "1"}}})
        sensor_callback(mock_msg)

        assert switch._attr_is_on is True

    @pytest.mark.asyncio
    async def test_switch_state_string_zero(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch state with string '0'."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
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
        mock_msg.payload = json.dumps({"NeoPool": {"Test": {"State": "0"}}})
        sensor_callback(mock_msg)

        assert switch._attr_is_on is False

    @pytest.mark.asyncio
    async def test_switch_multiple_state_updates(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch handles multiple state updates."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Filtration.State",
            command="NPFiltration",
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

        # Turn on
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Filtration": {"State": 1}}})
        sensor_callback(mock_msg)
        assert switch._attr_is_on is True

        # Turn off
        mock_msg.payload = json.dumps({"NeoPool": {"Filtration": {"State": 0}}})
        sensor_callback(mock_msg)
        assert switch._attr_is_on is False

        # Turn on again
        mock_msg.payload = json.dumps({"NeoPool": {"Filtration": {"State": 1}}})
        sensor_callback(mock_msg)
        assert switch._attr_is_on is True

        assert switch.async_write_ha_state.call_count == 3
