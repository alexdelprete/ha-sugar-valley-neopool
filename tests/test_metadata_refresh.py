"""Tests for device-metadata reliability and the disabled-entity write guard.

Covered here:
- the metadata fetch waits for its Status reply subscriptions to be active at
  the broker before publishing (HA queues new subscriptions behind a cooldown,
  and Tasmota's non-retained reply would otherwise be lost)
- each Status command has its own reply budget, so an unanswered Status 2 no
  longer starves Status 5
- the LWT watch keeps runtime_data.available current and retries the
  metadata fetch in the background when it is incomplete or after a reconnect
- NeoPoolEntity._async_write_state skips writes once the entity is disabled
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    _async_start_metadata_refresh,
    _async_wait_subscribed,
    _metadata_complete,
    _setup_register_recovery_watch,
    async_fetch_device_metadata,
)
from custom_components.sugar_valley_neopool.const import CONF_NODEID, DOMAIN
from custom_components.sugar_valley_neopool.entity import NeoPoolEntity
from homeassistant.core import HomeAssistant

_PKG = "custom_components.sugar_valley_neopool"


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a config entry with real runtime data, added to hass."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
    entry.add_to_hass(hass)
    entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="MyPool", nodeid="ABC123")
    return entry


def _complete(entry: MockConfigEntry) -> None:
    """Mark all device metadata as known."""
    entry.runtime_data.tasmota_version = "15.6.0"
    entry.runtime_data.fw_version = "V5.0"
    entry.runtime_data.device_ip = "192.168.1.50"


def _msg(payload: str) -> MagicMock:
    """Build a ReceiveMessage stand-in."""
    msg = MagicMock()
    msg.payload = payload
    return msg


class TestMetadataComplete:
    """Tests for _metadata_complete."""

    def test_incomplete_until_all_three_known(self, hass: HomeAssistant) -> None:
        """Firmware, Powerunit version and IP must all be present."""
        entry = _make_entry(hass)
        assert _metadata_complete(entry) is False
        entry.runtime_data.fw_version = "V5.0"
        entry.runtime_data.device_ip = "192.168.1.50"
        assert _metadata_complete(entry) is False  # Tasmota version still missing
        entry.runtime_data.tasmota_version = "15.6.0"
        assert _metadata_complete(entry) is True


class TestWaitSubscribed:
    """Tests for _async_wait_subscribed."""

    @pytest.mark.asyncio
    async def test_returns_true_once_all_topics_active(self, hass: HomeAssistant) -> None:
        """It waits for every topic and cleans up the status listeners."""
        callbacks: dict[str, object] = {}
        unsubs: list[MagicMock] = []

        def capture(_hass, topic, _qos, on_done):
            callbacks[topic] = on_done
            unsub = MagicMock()
            unsubs.append(unsub)
            return unsub

        with patch("homeassistant.components.mqtt.async_on_subscribe_done", side_effect=capture):
            task = asyncio.create_task(_async_wait_subscribed(hass, ["a", "b"], 1, 2.0))
            await asyncio.sleep(0)
            callbacks["a"]()
            await asyncio.sleep(0)
            assert not task.done()  # "b" still pending
            callbacks["b"]()
            assert await task is True

        assert all(u.called for u in unsubs)

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self, hass: HomeAssistant) -> None:
        """A subscription that never completes times out and still cleans up."""
        unsub = MagicMock()
        with patch(
            "homeassistant.components.mqtt.async_on_subscribe_done",
            return_value=unsub,
        ):
            assert await _async_wait_subscribed(hass, ["a"], 1, 0.05) is False
        unsub.assert_called_once()


class TestFetchSubscriptionOrdering:
    """The Status commands go out only after their reply topics are active."""

    @pytest.mark.asyncio
    async def test_publish_waits_for_reply_subscriptions(self, hass: HomeAssistant) -> None:
        """Nothing is published until both Status reply subscriptions complete."""
        entry = _make_entry(hass)
        done_cbs: dict[str, object] = {}

        def capture(_hass, topic, _qos, on_done):
            done_cbs[topic] = on_done
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "homeassistant.components.mqtt.async_publish", new_callable=AsyncMock
            ) as mock_pub,
            patch("homeassistant.components.mqtt.async_on_subscribe_done", side_effect=capture),
            patch(f"{_PKG}.METADATA_STATUS_REPLY_TIMEOUT", 0.05),
        ):
            task = asyncio.create_task(async_fetch_device_metadata(hass, entry, wait_timeout=1.0))
            await asyncio.sleep(0.05)
            assert set(done_cbs) == {"stat/MyPool/STATUS2", "stat/MyPool/STATUS5"}
            mock_pub.assert_not_awaited()  # still waiting for the broker

            for cb in done_cbs.values():
                cb()
            await task

        payloads = [c.args[2] for c in mock_pub.await_args_list]
        assert payloads[0] == "2"

    @pytest.mark.asyncio
    async def test_unanswered_status2_does_not_starve_status5(self, hass: HomeAssistant) -> None:
        """Status 5 is still sent, and answered, when Status 2 gets no reply."""
        entry = _make_entry(hass)
        callbacks: dict[str, object] = {}

        async def mock_subscribe(_hass, topic, cb, **_kwargs):
            callbacks[topic] = cb
            return MagicMock()

        async def answer_status5(_hass, topic, payload, **_kwargs):
            if payload == "5":
                callbacks["stat/MyPool/STATUS5"](
                    _msg(json.dumps({"StatusNET": {"IPAddress": "192.168.1.50"}}))
                )

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=mock_subscribe),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
                side_effect=answer_status5,
            ) as mock_pub,
            patch(f"{_PKG}.METADATA_STATUS_REPLY_TIMEOUT", 0.05),
        ):
            await async_fetch_device_metadata(hass, entry, wait_timeout=0.5)

        assert [c.args[2] for c in mock_pub.await_args_list] == ["2", "5"]
        assert entry.runtime_data.device_ip == "192.168.1.50"
        assert entry.runtime_data.tasmota_version is None


class TestStartMetadataRefresh:
    """Tests for the _async_start_metadata_refresh single-flight helper."""

    @pytest.mark.asyncio
    async def test_creates_task_and_skips_while_in_flight(self, hass: HomeAssistant) -> None:
        """A second request while a fetch is running is skipped, not queued."""
        entry = _make_entry(hass)
        release = asyncio.Event()
        calls: list[int] = []

        async def slow_fetch(_hass, _entry) -> None:
            calls.append(1)
            await release.wait()

        with patch(f"{_PKG}.async_fetch_device_metadata", side_effect=slow_fetch):
            _async_start_metadata_refresh(hass, entry, reason="incomplete")
            task1 = entry.runtime_data.metadata_task
            await asyncio.sleep(0)
            _async_start_metadata_refresh(hass, entry, reason="lwt_recovery")
            assert entry.runtime_data.metadata_task is task1
            release.set()
            await task1

            # Once finished, a new request starts a fresh fetch.
            _async_start_metadata_refresh(hass, entry, reason="lwt_recovery")
            assert entry.runtime_data.metadata_task is not task1
            await entry.runtime_data.metadata_task

        assert len(calls) == 2


class TestLwtAvailabilityAndMetadata:
    """The LWT watch tracks availability and retries the metadata fetch."""

    async def _watch(self, hass: HomeAssistant, entry: MockConfigEntry):
        captured = {}

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            captured["cb"] = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_register_recovery_watch(hass, entry)
        return captured["cb"]

    @pytest.mark.asyncio
    async def test_tracks_availability(self, hass: HomeAssistant) -> None:
        """runtime_data.available follows the LWT payload."""
        entry = _make_entry(hass)
        _complete(entry)
        cb = await self._watch(hass, entry)
        with (
            patch(f"{_PKG}._read_config_registers", new_callable=AsyncMock),
            patch(f"{_PKG}.async_fetch_device_metadata", new_callable=AsyncMock),
        ):
            assert entry.runtime_data.available is False
            cb(_msg("Online"))
            assert entry.runtime_data.available is True
            cb(_msg("Offline"))
            assert entry.runtime_data.available is False
            cb(_msg("garbage"))  # unknown payloads leave it unchanged
            assert entry.runtime_data.available is False
            await hass.async_block_till_done()

    @pytest.mark.asyncio
    async def test_initial_online_retries_incomplete_metadata(self, hass: HomeAssistant) -> None:
        """The retained Online replay retries a fetch that got no firmware/IP."""
        entry = _make_entry(hass)
        cb = await self._watch(hass, entry)
        with patch(f"{_PKG}.async_fetch_device_metadata", new_callable=AsyncMock) as mock_fetch:
            cb(_msg("Online"))
            await hass.async_block_till_done()
        mock_fetch.assert_awaited_once_with(hass, entry)

    @pytest.mark.asyncio
    async def test_initial_online_skips_complete_metadata(self, hass: HomeAssistant) -> None:
        """No refetch when everything is already known and nothing reconnected."""
        entry = _make_entry(hass)
        _complete(entry)
        cb = await self._watch(hass, entry)
        with patch(f"{_PKG}.async_fetch_device_metadata", new_callable=AsyncMock) as mock_fetch:
            cb(_msg("Online"))
            await hass.async_block_till_done()
        mock_fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reconnect_refreshes_metadata(self, hass: HomeAssistant) -> None:
        """Offline -> Online refreshes metadata even when it was complete."""
        entry = _make_entry(hass)
        _complete(entry)
        cb = await self._watch(hass, entry)
        with (
            patch(f"{_PKG}._read_config_registers", new_callable=AsyncMock),
            patch(f"{_PKG}.async_fetch_device_metadata", new_callable=AsyncMock) as mock_fetch,
        ):
            cb(_msg("Offline"))
            await hass.async_block_till_done()
            mock_fetch.assert_not_awaited()  # going offline never fetches
            cb(_msg("Online"))
            await hass.async_block_till_done()
        mock_fetch.assert_awaited_once_with(hass, entry)


class TestWriteStateGuard:
    """NeoPoolEntity._async_write_state skips writes for disabled entities."""

    def test_writes_when_enabled(self, mock_config_entry: MagicMock) -> None:
        """An enabled (or unregistered) entity writes normally."""
        ent = NeoPoolEntity(mock_config_entry, "key")
        ent.async_write_ha_state = MagicMock()
        ent._async_write_state()
        ent.async_write_ha_state.assert_called_once()

    def test_skips_when_disabled(self, mock_config_entry: MagicMock) -> None:
        """A write racing the dynamic disable is dropped instead of warning."""
        ent = NeoPoolEntity(mock_config_entry, "key")
        ent.async_write_ha_state = MagicMock()
        ent.registry_entry = MagicMock(disabled=True)
        ent._async_write_state()
        ent.async_write_ha_state.assert_not_called()
