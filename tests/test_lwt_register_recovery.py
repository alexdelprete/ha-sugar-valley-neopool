"""Tests for the LWT register recovery path.

Register-backed entities (timer selects/times, AUX mode selects, UV/climate/
antifreeze switches, heating/pH-delay/cover numbers) get their state from the
paced NPRead sweep, which originally ran only in async_setup_entry. NPReads
issued while the device is offline are silently dropped, so a sweep that raced
an LWT blip left those entities unavailable until a config-entry reload.

Covered here:
- the LWT recovery watch (subscription, Offline -> Online transition detection,
  no trigger on the retained/initial Online, no trigger on duplicate Online)
- sweep debouncing (at most one in-flight sweep; a new blip restarts it)
- entities restoring instantly from the runtime_data.register_state cache on
  reconnect (only unavailable before the first-ever successful read)
"""

from __future__ import annotations

import asyncio
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    _async_start_register_sweep,
    _setup_register_recovery_watch,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_NODEID,
    DOMAIN,
    TIMER_BLOCKS,
    TIMER_OFFSET_ON,
)
from custom_components.sugar_valley_neopool.time import TIMER_TIME_DESCRIPTIONS, NeoPoolTimerTime
from homeassistant.core import HomeAssistant

_F1_ON = TIMER_BLOCKS["filtration1"] + TIMER_OFFSET_ON

_READ_CONFIG_REGISTERS = "custom_components.sugar_valley_neopool._read_config_registers"


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a config entry with real runtime data, added to hass."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
    entry.add_to_hass(hass)
    entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="MyPool", nodeid="ABC123")
    return entry


async def _setup_watch(hass: HomeAssistant, entry: MockConfigEntry):
    """Set up the recovery watch with a captured LWT callback."""
    captured = {}

    async def capture_subscribe(_hass, topic, cb, **_kwargs):
        captured["topic"] = topic
        captured["cb"] = cb
        return MagicMock()

    with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
        await _setup_register_recovery_watch(hass, entry)
    return captured


def _lwt(payload: str) -> MagicMock:
    """Build an LWT ReceiveMessage stand-in."""
    msg = MagicMock()
    msg.payload = payload
    return msg


class TestRegisterRecoveryWatch:
    """Tests for _setup_register_recovery_watch's LWT transition handling."""

    @pytest.mark.asyncio
    async def test_watch_subscribes_to_lwt_topic(self, hass: HomeAssistant) -> None:
        """The watch subscribes to tele/{topic}/LWT."""
        entry = _make_entry(hass)
        captured = await _setup_watch(hass, entry)
        assert captured["topic"] == "tele/MyPool/LWT"

    @pytest.mark.asyncio
    async def test_initial_online_does_not_trigger_sweep(self, hass: HomeAssistant) -> None:
        """The retained Online replayed at subscribe time is not a regain.

        The startup sweep covers the initial read; only a genuine
        Offline -> Online transition may trigger a recovery sweep.
        """
        entry = _make_entry(hass)
        captured = await _setup_watch(hass, entry)

        with patch(_READ_CONFIG_REGISTERS, new_callable=AsyncMock) as mock_read:
            captured["cb"](_lwt("Online"))
            captured["cb"](_lwt("Online"))  # duplicate Online, still no transition
            await hass.async_block_till_done()

        mock_read.assert_not_awaited()
        assert entry.runtime_data.register_sweep_task is None

    @pytest.mark.asyncio
    async def test_offline_to_online_triggers_one_sweep(self, hass: HomeAssistant) -> None:
        """An Offline -> Online transition re-runs the paced register sweep.

        The recovery path reuses _read_config_registers itself, so the
        reconnect reads are paced by NPREAD_BURST_INTERVAL exactly like the
        startup sweep (the controller drops fast bursts).
        """
        entry = _make_entry(hass)
        captured = await _setup_watch(hass, entry)

        with patch(_READ_CONFIG_REGISTERS, new_callable=AsyncMock) as mock_read:
            captured["cb"](_lwt("Offline"))
            captured["cb"](_lwt("Online"))
            await hass.async_block_till_done()

        mock_read.assert_awaited_once_with(hass, entry)
        assert entry.runtime_data.register_sweep_task is not None
        assert entry.runtime_data.register_sweep_task.done()

    @pytest.mark.asyncio
    async def test_online_after_completed_sweep_needs_new_offline(
        self, hass: HomeAssistant
    ) -> None:
        """After a recovery sweep, another Online alone does not re-trigger."""
        entry = _make_entry(hass)
        captured = await _setup_watch(hass, entry)

        with patch(_READ_CONFIG_REGISTERS, new_callable=AsyncMock) as mock_read:
            captured["cb"](_lwt("Offline"))
            captured["cb"](_lwt("Online"))
            await hass.async_block_till_done()
            captured["cb"](_lwt("Online"))  # no new Offline in between
            await hass.async_block_till_done()
            assert mock_read.await_count == 1

            # A second full blip triggers a second sweep.
            captured["cb"](_lwt("Offline"))
            captured["cb"](_lwt("Online"))
            await hass.async_block_till_done()
            assert mock_read.await_count == 2

    @pytest.mark.asyncio
    async def test_flapping_link_restarts_single_sweep(self, hass: HomeAssistant) -> None:
        """A blip during an in-flight sweep restarts it; sweeps never pile up."""
        entry = _make_entry(hass)
        captured = await _setup_watch(hass, entry)

        release = asyncio.Event()
        started: list[int] = []

        async def slow_sweep(_hass, _entry) -> None:
            started.append(1)
            await release.wait()

        with patch(_READ_CONFIG_REGISTERS, side_effect=slow_sweep):
            captured["cb"](_lwt("Offline"))
            captured["cb"](_lwt("Online"))
            task1 = entry.runtime_data.register_sweep_task
            assert task1 is not None and not task1.done()

            # Second blip while the first sweep is still pacing: the stale
            # sweep is cancelled and a fresh, complete one starts.
            captured["cb"](_lwt("Offline"))
            captured["cb"](_lwt("Online"))
            task2 = entry.runtime_data.register_sweep_task
            assert task2 is not task1

            await asyncio.wait([task1])
            assert task1.cancelled()
            assert not task2.done()
            assert len(started) == 2  # started twice, but never two alive

            release.set()
            await task2
        await hass.async_block_till_done()


class TestStartRegisterSweep:
    """Tests for the _async_start_register_sweep debounce helper."""

    @pytest.mark.asyncio
    async def test_startup_sweep_creates_task(self, hass: HomeAssistant) -> None:
        """The startup call creates and tracks the background sweep task."""
        entry = _make_entry(hass)
        with patch(_READ_CONFIG_REGISTERS, new_callable=AsyncMock) as mock_read:
            _async_start_register_sweep(hass, entry, reason="startup")
            task = entry.runtime_data.register_sweep_task
            assert task is not None
            await hass.async_block_till_done()

        mock_read.assert_awaited_once_with(hass, entry)
        assert task.done()

    @pytest.mark.asyncio
    async def test_completed_sweep_is_not_cancelled(self, hass: HomeAssistant) -> None:
        """A finished sweep task is left alone; a new one simply starts."""
        entry = _make_entry(hass)
        with patch(_READ_CONFIG_REGISTERS, new_callable=AsyncMock) as mock_read:
            _async_start_register_sweep(hass, entry, reason="startup")
            await hass.async_block_till_done()
            task1 = entry.runtime_data.register_sweep_task

            _async_start_register_sweep(hass, entry, reason="lwt_recovery")
            await hass.async_block_till_done()
            task2 = entry.runtime_data.register_sweep_task

        assert task1.done() and not task1.cancelled()
        assert task2 is not task1
        assert mock_read.await_count == 2


class TestEntityRestoresFromCache:
    """Register-backed entities restore from the cache the moment LWT regains."""

    async def _added(self, ent: NeoPoolTimerTime, mock_hass: MagicMock):
        """Run async_added_to_hass, capturing the LWT callback."""
        ent.hass = mock_hass
        ent.entity_id = "time.test"
        ent.async_write_ha_state = MagicMock()
        captured = {}

        async def capture_subscribe(_hass, topic, cb, **_kwargs):
            if "LWT" in topic:
                captured["lwt"] = cb
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=capture_subscribe,
            ),
            patch(
                "custom_components.sugar_valley_neopool.time.async_dispatcher_connect",
                return_value=MagicMock(),
            ),
        ):
            await ent.async_added_to_hass()
        return captured["lwt"]

    @pytest.mark.asyncio
    async def test_cached_value_survives_lwt_blip(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """After a blip the entity is immediately available with its old value.

        No register re-read is needed for the restore — the recovery sweep only
        refreshes the cached values afterwards.
        """
        ent = NeoPoolTimerTime(mock_config_entry, TIMER_TIME_DESCRIPTIONS[0])
        lwt_cb = await self._added(ent, mock_hass)

        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        rs[_F1_ON] = 25200  # 07:00:00, cached by the startup sweep

        lwt_cb(_lwt("Online"))
        assert ent.available is True
        assert ent.native_value == dt_time(7, 0, 0)

        # Blip: offline makes it unavailable, but the cache is untouched...
        lwt_cb(_lwt("Offline"))
        assert ent.available is False
        assert rs[_F1_ON] == 25200

        # ...so on regain it restores instantly, before any NPRead round-trip.
        lwt_cb(_lwt("Online"))
        assert ent.available is True
        assert ent.native_value == dt_time(7, 0, 0)

    @pytest.mark.asyncio
    async def test_unavailable_only_before_first_read(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """With nothing cached yet, LWT Online alone is not enough."""
        ent = NeoPoolTimerTime(mock_config_entry, TIMER_TIME_DESCRIPTIONS[0])
        lwt_cb = await self._added(ent, mock_hass)

        rs = mock_config_entry.runtime_data.register_state
        rs.clear()

        lwt_cb(_lwt("Online"))
        assert ent.available is False  # first-ever read still pending

        rs[_F1_ON] = 25200  # first successful read lands
        assert ent.available is True
