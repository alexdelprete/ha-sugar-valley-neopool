"""Tests for per-timer filtration-speed selects (Group 5, variable-speed pumps)."""

from __future__ import annotations

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

# A realistic MBF_PAR_FILTRATION_CONF base: pump type = 2 (variable speed),
# all speed fields 0 (unset).
_VS_BASE = 0x0002


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
        """Options are the 1/2/3 speed labels (0 = unset is not an option)."""
        sel, _desc = self._make(mock_config_entry)
        assert sel.options == ["Slow", "Medium", "Fast"]

    def test_vs_detection_override_and_pump_type(self, mock_config_entry: MagicMock) -> None:
        """override forces on/off; auto reads the pump-type nibble (bits 0-3)."""
        sel, _desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        # override wins regardless of the register
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        assert sel._vs_enabled is True
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_STANDARD}
        rs[REG_FILTRATION_CONF] = _VS_BASE  # type=2
        assert sel._vs_enabled is False
        # auto: follow the pump-type nibble
        mock_config_entry.options = {CONF_PUMP_TYPE: "auto"}
        assert sel._vs_enabled is True  # type 2 -> variable
        rs[REG_FILTRATION_CONF] = 0x0000  # type 0 -> standard
        assert sel._vs_enabled is False
        rs.clear()
        assert sel._vs_enabled is False  # unknown until read

    def test_current_option_encoding_and_unset(self, mock_config_entry: MagicMock) -> None:
        """1/2/3 map to Slow/Medium/Fast; 0 (unset) and unknown -> None."""
        sel, _desc = self._make(mock_config_entry, idx=0)  # timer1, shift 7
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        assert sel.current_option is None  # nothing cached
        rs[REG_FILTRATION_CONF] = _VS_BASE  # timer1 field = 0 -> unset
        assert sel.current_option is None
        rs[REG_FILTRATION_CONF] = _VS_BASE | (1 << 7)  # Slow
        assert sel.current_option == "Slow"
        rs[REG_FILTRATION_CONF] = _VS_BASE | (3 << 7)  # Fast
        assert sel.current_option == "Fast"

    def test_timer2_field_isolation(self, mock_config_entry: MagicMock) -> None:
        """timer2 reads bits 10-12, independent of timer1/3."""
        sel, _desc = self._make(mock_config_entry, idx=1)  # timer2, shift 10
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        mock_config_entry.runtime_data.register_state[REG_FILTRATION_CONF] = _VS_BASE | (2 << 10)
        assert sel.current_option == "Medium"

    def test_available_requires_vs_and_cache(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + VS enabled + cached register."""
        sel, _desc = self._make(mock_config_entry)
        mock_config_entry.options = {CONF_PUMP_TYPE: PUMP_TYPE_VARIABLE}
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        sel._attr_available = True  # LWT online
        assert sel.available is False  # register not cached
        rs[REG_FILTRATION_CONF] = _VS_BASE
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
        rs[REG_FILTRATION_CONF] = _VS_BASE  # type=2, all speeds unset

        with patch.object(sel, "_write_register", new_callable=AsyncMock) as mock_w:
            await sel.async_select_option("Fast")  # field 3 at shift 7

        expected = _VS_BASE | (3 << 7)  # 0x0182
        mock_w.assert_awaited_once_with(REG_FILTRATION_CONF, expected)
        assert rs[REG_FILTRATION_CONF] == expected
        assert rs[REG_FILTRATION_CONF] & 0x000F == 2  # pump type preserved

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
