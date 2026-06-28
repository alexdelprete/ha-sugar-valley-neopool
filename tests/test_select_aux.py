"""Tests for the register-backed AUX mode select (Group 4b)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_NPEXEC,
    CMD_NPSAVE,
    CMD_NPWRITE,
    REG_AUX1_MODE,
)
from custom_components.sugar_valley_neopool.select import (
    AUX_MODE_SELECT_DESCRIPTIONS,
    NeoPoolAuxModeSelect,
)


class TestAuxModeSelectDescriptions:
    """Tests for the AUX mode select descriptions."""

    def test_four_aux_mode_selects(self) -> None:
        """There is one mode select per AUX relay."""
        keys = [d.key for d in AUX_MODE_SELECT_DESCRIPTIONS]
        assert keys == ["aux1_mode", "aux2_mode", "aux3_mode", "aux4_mode"]

    def test_registers_and_indices_match(self) -> None:
        """aux1 maps to REG_AUX1_MODE and array index 0."""
        desc = AUX_MODE_SELECT_DESCRIPTIONS[0]
        assert desc.register == REG_AUX1_MODE
        assert desc.aux_index == 0


class TestNeoPoolAuxModeSelect:
    """Tests for the AUX mode select entity."""

    def _make(self, entry: MagicMock) -> tuple[NeoPoolAuxModeSelect, Any]:
        desc = AUX_MODE_SELECT_DESCRIPTIONS[0]  # aux1_mode
        return NeoPoolAuxModeSelect(entry, desc), desc

    def test_options_are_auto_on_off(self, mock_config_entry: MagicMock) -> None:
        """The select exposes exactly auto/on/off."""
        sel, _desc = self._make(mock_config_entry)
        assert sel.options == ["auto", "on", "off"]

    def test_current_option_requires_binding(self, mock_config_entry: MagicMock) -> None:
        """A mode value is only meaningful once the timer is bound to its relay."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        # Mode set but function word still 0 (unbound) -> option is unknown.
        rs[desc.register] = 3
        assert sel.current_option is None
        # Bind the timer (function word == aux code); now the mode maps.
        rs[desc.function_register] = desc.function_code
        assert sel.current_option == "on"

    def test_current_option_from_register(self, mock_config_entry: MagicMock) -> None:
        """current_option maps the cached mode value when bound; None otherwise."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[desc.function_register] = desc.function_code  # bound
        assert sel.current_option is None  # mode not cached yet
        rs[desc.register] = 1
        assert sel.current_option == "auto"
        rs[desc.register] = 3
        assert sel.current_option == "on"
        rs[desc.register] = 4
        assert sel.current_option == "off"
        rs[desc.register] = 2  # linked: not exposed -> None
        assert sel.current_option is None

    def test_available_requires_gating_and_value(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + AUX present in SENSOR + a cached mode."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        sel._attr_available = True  # LWT online
        sel._gating_ok = False
        assert sel.available is False
        sel._gating_ok = True
        assert sel.available is False  # value not cached yet
        rs[desc.register] = 1
        assert sel.available is True

    @pytest.mark.asyncio
    async def test_select_option_binds_then_writes_mode(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Selecting a mode writes the function code + mode + NPExec (no NPSave).

        The function-code write binds the timer to the relay (without it the
        mode is inert, per the on-device finding), then the mode is applied with
        NPExec; both are cached optimistically.
        """
        sel, desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()

        with patch.object(sel, "_publish_command", new_callable=AsyncMock) as pub:
            await sel.async_select_option("on")

        published = [c.args for c in pub.await_args_list]
        # function word bound, mode applied, committed, never persisted
        assert (
            CMD_NPWRITE,
            f"0x{desc.function_register:04X} {desc.function_code}",
        ) in published
        assert (CMD_NPWRITE, f"0x{desc.register:04X} 3") in published
        assert (CMD_NPEXEC, "") in published
        assert all(cmd != CMD_NPSAVE for cmd, _ in published)
        assert rs[desc.function_register] == desc.function_code
        assert rs[desc.register] == 3

    @pytest.mark.asyncio
    async def test_select_invalid_option_is_noop(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """An option outside auto/on/off does not write anything."""
        sel, _desc = self._make(mock_config_entry)
        sel.hass = mock_hass
        sel.async_write_ha_state = MagicMock()

        with patch.object(sel, "_publish_command", new_callable=AsyncMock) as pub:
            await sel.async_select_option("bogus")

        pub.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_gating_tracked_from_sensor(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """The SENSOR watch flips _gating_ok on AUX array presence/length."""
        sel, _desc = self._make(mock_config_entry)  # aux1 -> index 0
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
        msg.payload = json.dumps({"NeoPool": {"Relay": {"Aux": [0, 0, 0, 0]}}})
        sensor_cb(msg)
        assert sel._gating_ok is True

        msg.payload = json.dumps({"NeoPool": {"Relay": {"Aux": []}}})
        sensor_cb(msg)
        assert sel._gating_ok is False

        msg.payload = json.dumps({"NeoPool": {"Other": 1}})
        sensor_cb(msg)
        assert sel._gating_ok is False

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
