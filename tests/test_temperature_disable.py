"""Tests for the temperature-measurement auto-disable rule.

The Tasmota driver publishes NeoPool.Temperature only when the controller's
temperature measurement is enabled (MBF_PAR_TEMPERATURE_ACTIVE; the probe is
optional hardware). Entities whose only dependency is that measurement
(water_temperature, smart_antifreeze) are disabled instead of sitting
unavailable forever, and re-enabled once Temperature appears.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    _MODULE_ENTITY_MAP,
    _RELAY_CONFIG_ENTITY_MAP,
    _TEMPERATURE_ENTITIES,
    NeoPoolData,
    _disable_unavailable_temperature_entities,
    _refresh_entity_disable_state,
    _setup_dynamic_disable_watch,
)
from custom_components.sugar_valley_neopool.const import CONF_NODEID, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

DOMAIN_PKG = "custom_components.sugar_valley_neopool"


def _entry(hass: HomeAssistant, temperature_present: bool | None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
    entry.add_to_hass(hass)
    entry.runtime_data = NeoPoolData(
        device_name="P",
        mqtt_topic="MyPool",
        nodeid="ABC123",
        temperature_present=temperature_present,
    )
    return entry


def _register(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    """Create the two temperature-only registry entries; return key -> entity_id."""
    entity_registry = er.async_get(hass)
    ids = {}
    for domain, key in _TEMPERATURE_ENTITIES:
        ent = entity_registry.async_get_or_create(
            domain,
            DOMAIN,
            f"neopool_mqtt_ABC123_{key}",
            config_entry=entry,
            suggested_object_id=f"neopool_{key}",
        )
        ids[key] = ent.entity_id
    return ids


class TestTemperatureEntityMap:
    """The map only holds entities whose sole dependency is the temperature."""

    def test_contents(self) -> None:
        """Water temperature and smart antifreeze, nothing else."""
        assert _TEMPERATURE_ENTITIES == [
            ("sensor", "water_temperature"),
            ("switch", "smart_antifreeze"),
        ]

    def test_no_overlap_with_other_maps(self) -> None:
        """An entity in two maps would flip-flop (disable, then re-enable + reload)."""
        others = {e for entries in _MODULE_ENTITY_MAP.values() for e in entries}
        others |= {e for entries in _RELAY_CONFIG_ENTITY_MAP.values() for e in entries}
        assert not others & set(_TEMPERATURE_ENTITIES)


class TestDisableUnavailableTemperatureEntities:
    """Tests for _disable_unavailable_temperature_entities."""

    def test_unknown_is_a_no_op(self, hass: HomeAssistant) -> None:
        """Before any NeoPool payload, nothing is touched."""
        entry = _entry(hass, None)
        ids = _register(hass, entry)
        _disable_unavailable_temperature_entities(hass, entry)
        registry = er.async_get(hass)
        assert all(registry.async_get(eid).disabled_by is None for eid in ids.values())

    def test_disables_without_probe(self, hass: HomeAssistant) -> None:
        """No Temperature in telemetry disables both entities."""
        entry = _entry(hass, False)
        ids = _register(hass, entry)
        _disable_unavailable_temperature_entities(hass, entry)
        registry = er.async_get(hass)
        for eid in ids.values():
            assert registry.async_get(eid).disabled_by == er.RegistryEntryDisabler.INTEGRATION

    def test_reenables_when_probe_appears(self, hass: HomeAssistant) -> None:
        """Entities the integration disabled come back once Temperature appears."""
        entry = _entry(hass, True)
        ids = _register(hass, entry)
        registry = er.async_get(hass)
        for eid in ids.values():
            registry.async_update_entity(eid, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        _disable_unavailable_temperature_entities(hass, entry)
        assert all(registry.async_get(eid).disabled_by is None for eid in ids.values())

    def test_leaves_user_disabled_alone(self, hass: HomeAssistant) -> None:
        """A user-disabled entity stays disabled even with a probe present."""
        entry = _entry(hass, True)
        ids = _register(hass, entry)
        registry = er.async_get(hass)
        registry.async_update_entity(
            ids["smart_antifreeze"], disabled_by=er.RegistryEntryDisabler.USER
        )
        _disable_unavailable_temperature_entities(hass, entry)
        assert (
            registry.async_get(ids["smart_antifreeze"]).disabled_by == er.RegistryEntryDisabler.USER
        )

    def test_refresh_schedules_reload_on_reenable(self, hass: HomeAssistant) -> None:
        """The orchestrator manages these keys and reloads after a re-enable."""
        entry = _entry(hass, True)
        ids = _register(hass, entry)
        registry = er.async_get(hass)
        registry.async_update_entity(
            ids["water_temperature"], disabled_by=er.RegistryEntryDisabler.INTEGRATION
        )
        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
            _refresh_entity_disable_state(hass, entry)
        assert registry.async_get(ids["water_temperature"]).disabled_by is None
        mock_reload.assert_called_once_with(entry.entry_id)


class TestDynamicWatchTracksTemperature:
    """The SENSOR watch records whether Temperature is in the NeoPool payload."""

    @pytest.mark.asyncio
    async def test_tracks_presence(self, hass: HomeAssistant) -> None:
        """Present -> True, absent -> False, no NeoPool object -> unchanged."""
        entry = _entry(hass, None)
        captured = {}

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            captured["cb"] = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_dynamic_disable_watch(hass, entry)

        def send(payload: dict) -> None:
            msg = MagicMock()
            msg.payload = json.dumps(payload)
            captured["cb"](msg)

        with patch(f"{DOMAIN_PKG}._refresh_entity_disable_state") as mock_refresh:
            send({"NeoPool": {"Temperature": 26.5}})
            assert entry.runtime_data.temperature_present is True
            send({"NeoPool": {"pH": {"Data": 7.2}}})
            assert entry.runtime_data.temperature_present is False
            send({"Time": "2026-10-03T22:00:00"})  # driver error path: no NeoPool
            assert entry.runtime_data.temperature_present is False
            send({"NeoPool": {"pH": {"Data": 7.2}}})  # unchanged -> no refresh

        assert mock_refresh.call_count == 2
