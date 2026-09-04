"""Tests for the register-backed AUX mode select (Group 4b)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    AUX_MODE_PUSH_GRACE_SECONDS,
    AUX_OPERATING_MODE_COUNTDOWN,
    AUX_OPERATING_MODE_MANUAL,
    AUX_OPERATING_MODE_TIMER,
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


class TestNeoPoolAuxModeSelectPush:
    """Push-native option from NeoPool.Relay.AuxMode (Tasmota 15.6.0.1+, PR #24998)."""

    def _make(self, entry: MagicMock) -> tuple[NeoPoolAuxModeSelect, Any]:
        desc = AUX_MODE_SELECT_DESCRIPTIONS[1]  # aux2_mode -> index 1
        return NeoPoolAuxModeSelect(entry, desc), desc

    async def _wire(self, sel: NeoPoolAuxModeSelect, hass: MagicMock):
        sel.hass = hass
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
        return sensor_cb

    @staticmethod
    def _msg(aux: list[int] | None, modes: list[int] | None) -> MagicMock:
        relay: dict[str, Any] = {}
        if aux is not None:
            relay["Aux"] = aux
        if modes is not None:
            relay["AuxMode"] = modes
        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Relay": relay}})
        return msg

    @pytest.mark.asyncio
    async def test_pushed_mode_derives_option(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Timer -> auto; Manual + physical on/off -> on/off; Countdown/unknown -> None."""
        sel, _desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        cb = await self._wire(sel, mock_hass)

        cb(self._msg([0, 0, 0, 0], [0, AUX_OPERATING_MODE_TIMER, 0, 0]))
        assert sel.current_option == "auto"
        cb(self._msg([0, 1, 0, 0], [0, AUX_OPERATING_MODE_MANUAL, 0, 0]))
        assert sel.current_option == "on"
        cb(self._msg([0, 0, 0, 0], [0, AUX_OPERATING_MODE_MANUAL, 0, 0]))
        assert sel.current_option == "off"
        cb(self._msg([0, 1, 0, 0], [0, AUX_OPERATING_MODE_COUNTDOWN, 0, 0]))
        assert sel.current_option is None
        cb(self._msg([0, 1, 0, 0], [0, -1, 0, 0]))
        assert sel.current_option is None

    @pytest.mark.asyncio
    async def test_push_available_without_register_cache(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """With AuxMode pushed the select is available even before any NPRead."""
        sel, _desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        cb = await self._wire(sel, mock_hass)
        sel._attr_available = True  # LWT online

        cb(self._msg([0, 0, 0, 0], None))  # old firmware: no AuxMode
        assert sel.available is False
        cb(self._msg([0, 0, 0, 0], [1, 1, 1, 1]))
        assert sel.available is True

    @pytest.mark.asyncio
    async def test_push_wins_over_register_cache(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """A pushed mode overrides a (possibly stale) cached register value."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[desc.function_register] = desc.function_code
        rs[desc.register] = 3  # cache says ALWAYS_ON
        cb = await self._wire(sel, mock_hass)
        assert sel.current_option == "on"  # fallback path

        cb(self._msg([0, 0, 0, 0], [0, AUX_OPERATING_MODE_TIMER, 0, 0]))
        assert sel.current_option == "auto"  # push path

    @pytest.mark.asyncio
    async def test_message_without_auxmode_keeps_fallback(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Firmware without AuxMode leaves the register-cache path untouched."""
        sel, desc = self._make(mock_config_entry)
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[desc.function_register] = desc.function_code
        rs[desc.register] = 4
        cb = await self._wire(sel, mock_hass)

        cb(self._msg([0, 1, 0, 0], None))
        assert sel._pushed_mode is None
        assert sel._pushed_state == 1
        assert sel.current_option == "off"
        # A short AuxMode array (index missing) is treated as absent too.
        cb(self._msg([0, 1, 0, 0], [0]))
        assert sel._pushed_mode is None
        assert sel.current_option == "off"

    @pytest.mark.asyncio
    async def test_select_option_ignores_push_during_grace(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """After our own write, stale pushed AuxMode is ignored until the grace elapses."""
        sel, _desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        cb = await self._wire(sel, mock_hass)

        cb(self._msg([0, 0, 0, 0], [0, AUX_OPERATING_MODE_TIMER, 0, 0]))
        assert sel.current_option == "auto"

        t0 = 1_000_000.0
        with (
            patch.object(sel, "_publish_command", new_callable=AsyncMock),
            patch("custom_components.sugar_valley_neopool.select.dt_util.utcnow") as utcnow,
        ):
            utcnow.return_value.timestamp.return_value = t0
            await sel.async_select_option("on")
            # Optimistic cache value shown; pushed mode dropped.
            assert sel._pushed_mode is None
            assert sel.current_option == "on"

            # Driver echo within the window still carries the stale Timer mode
            # (its 30 s register cache): ignored, physical state still tracked.
            utcnow.return_value.timestamp.return_value = t0 + 2
            cb(self._msg([0, 1, 0, 0], [0, AUX_OPERATING_MODE_TIMER, 0, 0]))
            assert sel._pushed_mode is None
            assert sel._pushed_state == 1
            assert sel.current_option == "on"

            # First message after the window is fresh and trusted again.
            utcnow.return_value.timestamp.return_value = t0 + AUX_MODE_PUSH_GRACE_SECONDS + 1
            cb(self._msg([0, 1, 0, 0], [0, AUX_OPERATING_MODE_MANUAL, 0, 0]))
            assert sel._pushed_mode == AUX_OPERATING_MODE_MANUAL
            assert sel.current_option == "on"
