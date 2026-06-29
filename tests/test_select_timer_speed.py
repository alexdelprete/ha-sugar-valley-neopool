"""Tests for per-timer filtration-speed selects (Group 5, variable-speed pumps)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CONF_PUMP_TYPE,
    PUMP_TYPE_STANDARD,
    PUMP_TYPE_VARIABLE,
    REG_FILTRATION_CONF,
)
from custom_components.sugar_valley_neopool.select import (
    TIMER_SPEED_SELECT_DESCRIPTIONS,
    NeoPoolTimerSpeedSelect,
)


class TestTimerSpeedDescriptions:
    """Tests for the timer-speed select descriptions."""

    def test_three_timer_speed_selects(self) -> None:
        """One speed select per filtration timer, with stepped bit shifts."""
        keys = [d.key for d in TIMER_SPEED_SELECT_DESCRIPTIONS]
        assert keys == [
            "filtration_timer1_speed",
            "filtration_timer2_speed",
            "filtration_timer3_speed",
        ]
        assert [d.bit_shift for d in TIMER_SPEED_SELECT_DESCRIPTIONS] == [7, 10, 13]


class TestNeoPoolTimerSpeedSelect:
    """Tests for the timer-speed select entity."""

    def _make(self, entry: MagicMock, idx: int = 0) -> tuple[NeoPoolTimerSpeedSelect, Any]:
        desc = TIMER_SPEED_SELECT_DESCRIPTIONS[idx]
        return NeoPoolTimerSpeedSelect(entry, desc), desc

    def test_options_are_speed_labels(self, mock_config_entry: MagicMock) -> None:
        """Options are the register-encoded speed labels."""
        sel, _desc = self._make(mock_config_entry)
        assert sel.options == ["Slow", "Medium", "Fast"]

    def test_vs_enabled_override(self, mock_config_entry: MagicMock) -> None:
        """pump_type override forces VS on/off; auto follows SENSOR detection."""
        sel, _desc = self._make(mock_config_entry)
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        sel._speed_present = False
        assert sel._vs_enabled is True  # forced on
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_STANDARD}
        sel._speed_present = True
        assert sel._vs_enabled is False  # forced off
        mock_config_entry.options = {CONF_PUMP_TYPE: "auto"}
        sel._speed_present = True
        assert sel._vs_enabled is True  # auto -> follows SENSOR
        sel._speed_present = False
        assert sel._vs_enabled is False

    def test_current_option_decodes_field(self, mock_config_entry: MagicMock) -> None:
        """current_option reads this timer's 3-bit field; None when not VS."""
        sel, _desc = self._make(mock_config_entry, idx=0)  # timer1, shift 7
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        assert sel.current_option is None  # nothing cached
        # type=2 (bits0-3), timer1 speed field (bits7-9) = 2 (Fast): 0x0102
        rs[REG_FILTRATION_CONF] = 0x0102
        assert sel.current_option == "Fast"
        rs[REG_FILTRATION_CONF] = 0x0002  # timer1 field = 0 -> Slow
        assert sel.current_option == "Slow"
        # standard pump -> not meaningful
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_STANDARD}
        assert sel.current_option is None

    def test_timer2_field_isolation(self, mock_config_entry: MagicMock) -> None:
        """timer2 reads bits 10-12, independent of timer1/3."""
        sel, _desc = self._make(mock_config_entry, idx=1)  # timer2, shift 10
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        # timer2 field = 1 (Medium) -> 1<<10 = 0x0400
        mock_config_entry.runtime_data.register_state[REG_FILTRATION_CONF] = 0x0400
        assert sel.current_option == "Medium"

    def test_available_requires_vs_and_cache(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + VS enabled + cached register."""
        sel, _desc = self._make(mock_config_entry)
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        sel._attr_available = True  # LWT online
        assert sel.available is False  # register not cached
        rs[REG_FILTRATION_CONF] = 0x0002
        assert sel.available is True
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_STANDARD}
        assert sel.available is False  # forced standard

    @pytest.mark.asyncio
    async def test_select_option_read_modify_write(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Selecting a speed RMWs only this timer's field, preserving the rest."""
        sel, _desc = self._make(mock_config_entry, idx=0)  # timer1, shift 7
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[REG_FILTRATION_CONF] = 0x0002  # type=2, all speeds 0

        with patch.object(sel, "_write_register", new_callable=AsyncMock) as mock_w:
            await sel.async_select_option("Fast")  # field 2 at shift 7 -> 0x0100

        # 0x0002 | (2 << 7) = 0x0102; pump type bits preserved
        mock_w.assert_awaited_once_with(REG_FILTRATION_CONF, 0x0102)
        assert rs[REG_FILTRATION_CONF] == 0x0102
        assert rs[REG_FILTRATION_CONF] & 0x000F == 2  # type preserved

    @pytest.mark.asyncio
    async def test_select_option_no_cache_is_noop(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Without a cached register value, no blind write happens."""
        sel, _desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()
        mock_config_entry.runtime_data.register_state.clear()

        with patch.object(sel, "_write_register", new_callable=AsyncMock) as mock_w:
            await sel.async_select_option("Fast")

        mock_w.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_speed_presence_tracked_from_sensor(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """The SENSOR watch flips _speed_present on Filtration.Speed presence."""
        sel, _desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()

        sensor_cb = None

        async def capture(hass, topic, cb, **kwargs):
            nonlocal sensor_cb
            if "SENSOR" in topic:
                sensor_cb = cb
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
            patch(
                "custom_components.sugar_valley_neopool.select.async_dispatcher_connect",
                return_value=MagicMock(),
            ),
        ):
            await sel.async_added_to_hass()

        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Filtration": {"Speed": 1}}})
        sensor_cb(msg)
        assert sel._speed_present is True

        msg.payload = json.dumps({"NeoPool": {"Filtration": {"State": 1}}})
        sensor_cb(msg)
        assert sel._speed_present is False
