"""Tests for the NeoPool set_timer service (Group 4a)."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.sugar_valley_neopool.const import DOMAIN
from custom_components.sugar_valley_neopool.services import (
    SERVICE_SET_TIMER,
    SET_TIMER_SCHEMA,
    _async_set_timer,
    _resolve_entry,
    _seconds_since_midnight,
    async_setup_services,
    async_unload_services,
)
from homeassistant.exceptions import ServiceValidationError


def test_seconds_since_midnight() -> None:
    """Time-of-day converts to seconds since midnight."""
    assert _seconds_since_midnight(dt_time(0, 0, 0)) == 0
    assert _seconds_since_midnight(dt_time(10, 0, 0)) == 36000
    assert _seconds_since_midnight(dt_time(15, 30, 15)) == 55815


def test_set_timer_schema_defaults() -> None:
    """The schema fills period/mode defaults and accepts time strings."""
    data = SET_TIMER_SCHEMA(
        {
            "device_id": "dev1",
            "timer": "filtration1",
            "start": "10:00:00",
            "stop": "15:00:00",
        }
    )
    assert data["period"] == 86400
    assert data["mode"] == "auto"
    assert data["start"] == dt_time(10, 0, 0)


def test_set_timer_schema_rejects_unknown_timer() -> None:
    """An unknown timer name fails validation."""
    with pytest.raises(vol.Invalid):
        SET_TIMER_SCHEMA(
            {
                "device_id": "dev1",
                "timer": "nope",
                "start": "10:00:00",
                "stop": "15:00:00",
            }
        )


def _make_call(hass: MagicMock, **overrides: object) -> MagicMock:
    call = MagicMock()
    call.hass = hass
    call.data = {
        "device_id": "dev1",
        "timer": "filtration1",
        "start": dt_time(10, 0, 0),
        "stop": dt_time(15, 0, 0),
        "period": 86400,
        "mode": "auto",
        **overrides,
    }
    return call


def _patch_registry(found: bool) -> AbstractContextManager[MagicMock]:
    """Patch services.dr.async_get to resolve (or not) a device."""
    registry = MagicMock()
    if found:
        device = MagicMock()
        device.config_entries = {"eid"}
        registry.async_get.return_value = device
    else:
        registry.async_get.return_value = None
    return patch(
        "custom_components.sugar_valley_neopool.services.dr.async_get",
        return_value=registry,
    )


def _publish_patch() -> AbstractContextManager[AsyncMock]:
    return patch(
        "custom_components.sugar_valley_neopool.services.mqtt.async_publish",
        new_callable=AsyncMock,
    )


class TestResolveEntry:
    """Tests for _resolve_entry."""

    def test_resolves_matching_domain_entry(self, mock_config_entry: MagicMock) -> None:
        """A device with our config entry resolves to that entry."""
        hass = MagicMock()
        mock_config_entry.domain = DOMAIN
        hass.config_entries.async_get_entry.return_value = mock_config_entry
        with _patch_registry(found=True):
            assert _resolve_entry(hass, "dev1") is mock_config_entry

    def test_unknown_device_returns_none(self) -> None:
        """A device_id the registry doesn't know returns None."""
        hass = MagicMock()
        with _patch_registry(found=False):
            assert _resolve_entry(hass, "dev1") is None


class TestSetTimerService:
    """Tests for the _async_set_timer handler."""

    @pytest.mark.asyncio
    async def test_writes_timer_block(self, mock_config_entry: MagicMock) -> None:
        """The handler writes mode + ON/OFF/INTERVAL/PERIOD + EXEC + SAVE."""
        hass = MagicMock()
        mock_config_entry.domain = DOMAIN
        mock_config_entry.runtime_data.mqtt_topic = "SmartPool"
        hass.config_entries.async_get_entry.return_value = mock_config_entry
        call = _make_call(hass)

        with _patch_registry(found=True), _publish_patch() as pub:
            await _async_set_timer(call)

        sent = [(c.args[1], c.args[2]) for c in pub.await_args_list]
        base = 0x0434  # filtration1
        assert ("cmnd/SmartPool/NPWrite", f"0x{base:04X} 1") in sent
        assert ("cmnd/SmartPool/NPWriteL", f"0x{base + 1:04X} 36000") in sent
        assert ("cmnd/SmartPool/NPWriteL", f"0x{base + 3:04X} 54000") in sent
        assert ("cmnd/SmartPool/NPWriteL", f"0x{base + 7:04X} 18000") in sent
        assert ("cmnd/SmartPool/NPWriteL", f"0x{base + 5:04X} 86400") in sent
        assert ("cmnd/SmartPool/NPExec", "") in sent
        assert ("cmnd/SmartPool/NPSave", "") in sent
        # filtration is controller-bound: no function-word write at base+11
        assert all(addr != f"0x{base + 11:04X} 1" for _, addr in sent)

    @pytest.mark.asyncio
    async def test_aux_timer_writes_function_word(self, mock_config_entry: MagicMock) -> None:
        """An AUX timer is bound by writing its function code at block +11.

        Without this the block is inert (verified on-device); filtration/light
        timers are controller-bound and omit it.
        """
        hass = MagicMock()
        mock_config_entry.domain = DOMAIN
        mock_config_entry.runtime_data.mqtt_topic = "SmartPool"
        hass.config_entries.async_get_entry.return_value = mock_config_entry
        call = _make_call(hass, timer="aux4")

        with _patch_registry(found=True), _publish_patch() as pub:
            await _async_set_timer(call)

        sent = [(c.args[1], c.args[2]) for c in pub.await_args_list]
        base = 0x04D9  # aux4
        # function word (base+11 = 0x04E4) bound to AUX4 code 0x4000 = 16384
        assert ("cmnd/SmartPool/NPWrite", f"0x{base + 11:04X} 16384") in sent
        assert ("cmnd/SmartPool/NPWrite", f"0x{base:04X} 1") in sent
        assert ("cmnd/SmartPool/NPExec", "") in sent

    @pytest.mark.asyncio
    async def test_interval_wraps_over_midnight(self, mock_config_entry: MagicMock) -> None:
        """A stop earlier than start wraps the interval across midnight."""
        hass = MagicMock()
        mock_config_entry.domain = DOMAIN
        mock_config_entry.runtime_data.mqtt_topic = "SmartPool"
        hass.config_entries.async_get_entry.return_value = mock_config_entry
        call = _make_call(hass, start=dt_time(23, 0, 0), stop=dt_time(1, 0, 0))

        with _patch_registry(found=True), _publish_patch() as pub:
            await _async_set_timer(call)

        sent = [(c.args[1], c.args[2]) for c in pub.await_args_list]
        # 23:00 -> 01:00 = 2h = 7200s interval
        assert ("cmnd/SmartPool/NPWriteL", f"0x{0x0434 + 7:04X} 7200") in sent

    @pytest.mark.asyncio
    async def test_unknown_device_raises(self) -> None:
        """An unresolvable device raises ServiceValidationError, no publish."""
        hass = MagicMock()
        call = _make_call(hass)

        with (
            _patch_registry(found=False),
            _publish_patch() as pub,
            pytest.raises(ServiceValidationError),
        ):
            await _async_set_timer(call)

        pub.assert_not_awaited()


class TestServiceRegistration:
    """Tests for service (de)registration."""

    def test_setup_registers_once(self) -> None:
        """async_setup_services registers only when not already present."""
        hass = MagicMock()
        hass.services.has_service.return_value = False
        async_setup_services(hass)
        hass.services.async_register.assert_called_once()
        assert hass.services.async_register.call_args.args[0] == DOMAIN
        assert hass.services.async_register.call_args.args[1] == SERVICE_SET_TIMER

    def test_setup_idempotent(self) -> None:
        """A second setup with the service present does not re-register."""
        hass = MagicMock()
        hass.services.has_service.return_value = True
        async_setup_services(hass)
        hass.services.async_register.assert_not_called()

    def test_unload_removes_service(self) -> None:
        """async_unload_services removes the service."""
        hass = MagicMock()
        async_unload_services(hass)
        hass.services.async_remove.assert_called_once_with(DOMAIN, SERVICE_SET_TIMER)
