"""Tests for the per-timer mode select (filtration 1-3 + light, #1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_NPEXEC,
    CMD_NPSAVE,
    CMD_NPWRITE,
    FCT_FILTRATION,
    FCT_LIGHTING,
    TIMER_BLOCKS,
    TIMER_OFFSET_ENABLE,
    TIMER_OFFSET_FUNCTION,
)
from custom_components.sugar_valley_neopool.select import (
    TIMER_MODE_SELECT_DESCRIPTIONS,
    NeoPoolTimerModeSelect,
)


class TestTimerModeSelectDescriptions:
    """Tests for the timer mode select descriptions."""

    def test_keys_and_scope(self) -> None:
        """Filtration 1-3 + light, in that order; AUX excluded."""
        keys = [d.key for d in TIMER_MODE_SELECT_DESCRIPTIONS]
        assert keys == [
            "filtration_timer1_mode",
            "filtration_timer2_mode",
            "filtration_timer3_mode",
            "light_timer_mode",
        ]

    def test_registers_derived_from_blocks(self) -> None:
        """Mode/function registers and codes come from the timer-block map."""
        filt1 = TIMER_MODE_SELECT_DESCRIPTIONS[0]
        assert filt1.mode_register == TIMER_BLOCKS["filtration1"] + TIMER_OFFSET_ENABLE
        assert filt1.function_register == TIMER_BLOCKS["filtration1"] + TIMER_OFFSET_FUNCTION
        assert filt1.function_code == FCT_FILTRATION
        light = TIMER_MODE_SELECT_DESCRIPTIONS[3]
        assert light.mode_register == TIMER_BLOCKS["light"] + TIMER_OFFSET_ENABLE
        assert light.function_code == FCT_LIGHTING


class TestNeoPoolTimerModeSelect:
    """Tests for the timer mode select entity."""

    def _make(self, entry: MagicMock, idx: int = 0) -> tuple[NeoPoolTimerModeSelect, Any]:
        desc = TIMER_MODE_SELECT_DESCRIPTIONS[idx]
        return NeoPoolTimerModeSelect(entry, desc), desc

    def test_options_include_disabled(self, mock_config_entry: MagicMock) -> None:
        """The select exposes the full disabled/auto/on/off subset."""
        sel, _desc = self._make(mock_config_entry)
        assert sel.options == ["disabled", "auto", "on", "off"]

    def test_current_option_from_register(self, mock_config_entry: MagicMock) -> None:
        """current_option maps the cached mode value (no bind gate)."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        assert sel.current_option is None  # nothing cached
        rs[desc.mode_register] = 0
        assert sel.current_option == "disabled"
        rs[desc.mode_register] = 1
        assert sel.current_option == "auto"
        rs[desc.mode_register] = 3
        assert sel.current_option == "on"
        rs[desc.mode_register] = 4
        assert sel.current_option == "off"
        rs[desc.mode_register] = 2  # linked: not exposed -> None
        assert sel.current_option is None

    def test_available_requires_online_and_value(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + a cached mode register."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        sel._attr_available = True  # LWT online
        assert sel.available is False  # not cached
        rs[desc.mode_register] = 1
        assert sel.available is True

    @pytest.mark.asyncio
    async def test_select_option_binds_writes_and_persists(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Selecting a mode binds the timer, writes the mode, commits and persists."""
        sel, desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()

        with patch.object(sel, "_publish_command", new_callable=AsyncMock) as pub:
            await sel.async_select_option("auto")

        published = [c.args for c in pub.await_args_list]
        assert (
            CMD_NPWRITE,
            f"0x{desc.function_register:04X} {desc.function_code}",
        ) in published
        assert (CMD_NPWRITE, f"0x{desc.mode_register:04X} 1") in published
        assert (CMD_NPEXEC, "") in published
        # A schedule should survive reboot -> NPSave is issued.
        assert (CMD_NPSAVE, "") in published
        assert rs[desc.function_register] == desc.function_code
        assert rs[desc.mode_register] == 1

    @pytest.mark.asyncio
    async def test_select_invalid_option_is_noop(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """An option outside the map writes nothing."""
        sel, _desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()

        with patch.object(sel, "_publish_command", new_callable=AsyncMock) as pub:
            await sel.async_select_option("bogus")

        pub.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_register_update_writes_state(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """The config-register dispatcher callback re-renders the entity."""
        sel, _desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()
        sel._handle_register_update()
        sel.async_write_ha_state.assert_called_once()
