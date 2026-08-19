"""Tests for the per-timer start/stop time entities (#1)."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_NPEXEC,
    CMD_NPSAVE,
    CMD_NPWRITE,
    CMD_NPWRITEL,
    FCT_FILTRATION,
    TIMER_BLOCKS,
    TIMER_OFFSET_FUNCTION,
    TIMER_OFFSET_INTERVAL,
    TIMER_OFFSET_OFF,
    TIMER_OFFSET_ON,
)
from custom_components.sugar_valley_neopool.time import (
    TIMER_TIME_DESCRIPTIONS,
    NeoPoolTimerTime,
    _seconds_to_time,
    _time_to_seconds,
)

_F1 = TIMER_BLOCKS["filtration1"]
_F1_ON = _F1 + TIMER_OFFSET_ON
_F1_OFF = _F1 + TIMER_OFFSET_OFF
_F1_INT = _F1 + TIMER_OFFSET_INTERVAL
_F1_FUNC = _F1 + TIMER_OFFSET_FUNCTION


class TestTimeHelpers:
    """Tests for the seconds<->time conversion helpers."""

    def test_round_trip(self) -> None:
        """A time survives conversion to seconds and back."""
        assert _time_to_seconds(dt_time(7, 30, 15)) == 27015
        assert _seconds_to_time(27015) == dt_time(7, 30, 15)

    def test_full_day_wraps_to_midnight(self) -> None:
        """86400s (a whole day) wraps to 00:00:00, not an invalid 24:00."""
        assert _seconds_to_time(86400) == dt_time(0, 0, 0)


class TestTimerTimeDescriptions:
    """Tests for the timer time descriptions."""

    def test_two_entities_per_timer(self) -> None:
        """Four timers, each with a start and a stop entity (8 total)."""
        keys = [d.key for d in TIMER_TIME_DESCRIPTIONS]
        assert keys == [
            "filtration_timer1_start",
            "filtration_timer1_stop",
            "filtration_timer2_start",
            "filtration_timer2_stop",
            "filtration_timer3_start",
            "filtration_timer3_stop",
            "light_timer_start",
            "light_timer_stop",
        ]

    def test_start_and_stop_registers(self) -> None:
        """Start reads the ON pair, stop the OFF pair, each with the other as counterpart."""
        start = TIMER_TIME_DESCRIPTIONS[0]
        stop = TIMER_TIME_DESCRIPTIONS[1]
        assert start.is_start is True
        assert start.time_register == _F1_ON
        assert start.counterpart_register == _F1_OFF
        assert stop.is_start is False
        assert stop.time_register == _F1_OFF
        assert stop.counterpart_register == _F1_ON
        assert start.function_code == FCT_FILTRATION


class TestNeoPoolTimerTime:
    """Tests for the timer time entity."""

    def _make(self, entry: MagicMock, idx: int = 0) -> tuple[NeoPoolTimerTime, Any]:
        desc = TIMER_TIME_DESCRIPTIONS[idx]
        return NeoPoolTimerTime(entry, desc), desc

    def test_native_value_from_low_word(self, mock_config_entry: MagicMock) -> None:
        """A time under 18:12h fits in the low word alone."""
        ent, _desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        assert ent.native_value is None  # nothing cached
        rs[_F1_ON] = 25200  # 07:00:00
        assert ent.native_value == dt_time(7, 0, 0)

    def test_native_value_uses_high_word(self, mock_config_entry: MagicMock) -> None:
        """Times past 18:12:16 need the high word (19:00:00 = 68400s)."""
        ent, _desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[_F1_ON] = 68400 & 0xFFFF
        rs[_F1_ON + 1] = (68400 >> 16) & 0xFFFF
        assert ent.native_value == dt_time(19, 0, 0)

    def test_available_requires_online_and_value(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + this time's register cached."""
        ent, _desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        ent._attr_available = True  # LWT online
        assert ent.available is False
        rs[_F1_ON] = 25200
        assert ent.available is True

    @pytest.mark.asyncio
    async def test_set_start_recomputes_interval(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Setting start binds, writes ON, and recomputes interval from cached stop."""
        ent, _desc = self._make(mock_config_entry, idx=0)  # filtration1 start
        ent.hass = mock_hass
        ent.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[_F1_OFF] = 54000  # stop cached at 15:00:00

        with patch.object(ent, "_publish_command", new_callable=AsyncMock) as pub:
            await ent.async_set_value(dt_time(8, 0, 0))  # 28800s

        published = [c.args for c in pub.await_args_list]
        assert (CMD_NPWRITE, f"0x{_F1_FUNC:04X} {FCT_FILTRATION}") in published
        assert (CMD_NPWRITEL, f"0x{_F1_ON:04X} 28800") in published
        # interval = (54000 - 28800) % 86400 = 25200
        assert (CMD_NPWRITEL, f"0x{_F1_INT:04X} 25200") in published
        assert (CMD_NPEXEC, "") in published
        assert (CMD_NPSAVE, "") in published
        assert rs[_F1_ON] == 28800
        assert rs[_F1_INT] == 25200

    @pytest.mark.asyncio
    async def test_set_stop_recomputes_interval(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Setting stop computes interval as (stop - cached start)."""
        ent, _desc = self._make(mock_config_entry, idx=1)  # filtration1 stop
        ent.hass = mock_hass
        ent.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[_F1_ON] = 28800  # start cached at 08:00:00

        with patch.object(ent, "_publish_command", new_callable=AsyncMock) as pub:
            await ent.async_set_value(dt_time(16, 0, 0))  # 57600s

        published = [c.args for c in pub.await_args_list]
        assert (CMD_NPWRITEL, f"0x{_F1_OFF:04X} 57600") in published
        assert (CMD_NPWRITEL, f"0x{_F1_INT:04X} 28800") in published  # 57600-28800

    @pytest.mark.asyncio
    async def test_set_without_counterpart_skips_interval(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """With the counterpart unknown, the time is still written but interval is not."""
        ent, _desc = self._make(mock_config_entry, idx=0)
        ent.hass = mock_hass
        ent.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()  # no counterpart cached

        with patch.object(ent, "_publish_command", new_callable=AsyncMock) as pub:
            await ent.async_set_value(dt_time(8, 0, 0))

        published = [c.args for c in pub.await_args_list]
        assert (CMD_NPWRITEL, f"0x{_F1_ON:04X} 28800") in published
        assert all(cmd != CMD_NPWRITEL or f"0x{_F1_INT:04X}" not in arg for cmd, arg in published)
        assert (CMD_NPEXEC, "") in published
        assert rs[_F1_ON] == 28800
        assert _F1_INT not in rs

    @pytest.mark.asyncio
    async def test_register_update_writes_state(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """The config-register dispatcher callback re-renders the entity."""
        ent, _desc = self._make(mock_config_entry)
        ent.hass = mock_hass
        ent.async_write_ha_state = MagicMock()
        ent._handle_register_update()
        ent.async_write_ha_state.assert_called_once()
