"""Tests for v0.2.18 new functionality in __init__.py.

Covers:
- _migrate_to_canonical_nodeid (device + entity migration)
- _disable_unavailable_relay_entities (smart relay enable/disable)
- async_fetch_device_metadata (Status 2/5 callbacks, SENSOR relay detection)
- _update_device_registry_metadata (sw_version, config_url)
- _auto_acquire_dual_nodeids (full dual NodeID acquisition)
- _wait_for_any_nodeid (telemetry wait)
- _cleanup_removed_entities (entity rename path)
- get_device_info (device_ip config_url)
- async_migrate_masked_unique_ids (stored real NodeID, ValueError, entity_key failure)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import (
    NeoPoolData,
    _auto_acquire_dual_nodeids,
    _cleanup_removed_entities,
    _disable_unavailable_mode_entities,
    _disable_unavailable_module_entities,
    _disable_unavailable_relay_config_entities,
    _disable_unavailable_relay_entities,
    _migrate_to_canonical_nodeid,
    _parse_register_int,
    _read_config_registers,
    _refresh_entity_disable_state,
    _setup_dynamic_disable_watch,
    _setup_result_watch,
    _update_device_registry_metadata,
    _wait_for_any_nodeid,
    async_fetch_device_metadata,
    async_migrate_masked_unique_ids,
    config_register_signal,
    connection_rate_signal,
    get_device_info,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    CONF_NODEID_HASHED,
    CONF_NODEID_REAL,
    CONFIG_REGISTERS,
    DOMAIN,
    REG_UV_MODE,
    TIMER_ENTITY_REGISTERS,
)
from custom_components.sugar_valley_neopool.helpers import ConnectionRateTracker
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


# ---------------------------------------------------------------------------
# _migrate_to_canonical_nodeid
# ---------------------------------------------------------------------------
class TestMigrateToCanonicalNodeid:
    """Tests for _migrate_to_canonical_nodeid."""

    def test_no_canonical_skips(self, hass: HomeAssistant) -> None:
        """Test skips when no canonical NodeID."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "", CONF_NODEID_REAL: "", CONF_NODEID_HASHED: ""},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="")

        # Should not raise
        _migrate_to_canonical_nodeid(hass, entry)

    def test_no_old_nodeids_skips(self, hass: HomeAssistant) -> None:
        """Test skips when canonical equals real (nothing to migrate)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "AA55HASHED",
                CONF_NODEID_REAL: "AA55HASHED",  # same as canonical
                CONF_NODEID_HASHED: "AA55HASHED",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="AA55HASHED")

        _migrate_to_canonical_nodeid(hass, entry)

    def test_device_migration_old_only(self, hass: HomeAssistant) -> None:
        """Test device identifier update when only old device exists."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "AA55HASHED",
                CONF_NODEID_REAL: "REAL123",
                CONF_NODEID_HASHED: "AA55HASHED",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="AA55HASHED")

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "REAL123")},
            manufacturer="Sugar Valley",
            name="Pool",
        )

        _migrate_to_canonical_nodeid(hass, entry)

        # Device should now have canonical identifier
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "AA55HASHED"), entry.entry_id
        )
        assert device is not None
        # Old identifier should be gone
        old_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "REAL123"), entry.entry_id
        )
        assert old_device is None

    def test_device_migration_both_exist_removes_duplicate(self, hass: HomeAssistant) -> None:
        """Test duplicate device removal when both old and canonical exist."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "AA55HASHED",
                CONF_NODEID_REAL: "REAL123",
                CONF_NODEID_HASHED: "AA55HASHED",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="AA55HASHED")

        device_registry = dr.async_get(hass)
        # Old device (original, has history)
        old_dev = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "REAL123")},
            manufacturer="Sugar Valley",
            name="Pool",
        )
        # Canonical device (new duplicate, empty)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "AA55HASHED")},
            manufacturer="Sugar Valley",
            name="Pool",
        )

        _migrate_to_canonical_nodeid(hass, entry)

        # Canonical device should exist (migrated from old)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "AA55HASHED"), entry.entry_id
        )
        assert device is not None
        # The old device was kept (migrated), its id should match the original
        assert device.id == old_dev.id

    def test_entity_unique_id_migration(self, hass: HomeAssistant) -> None:
        """Test entity unique_id migration from old to canonical NodeID."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "AA55HASHED",
                CONF_NODEID_REAL: "REAL123",
                CONF_NODEID_HASHED: "AA55HASHED",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="AA55HASHED")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_REAL123_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph",
        )

        _migrate_to_canonical_nodeid(hass, entry)

        # Entity should have new unique_id
        entity = entity_registry.async_get("sensor.neopool_ph")
        assert entity is not None
        assert entity.unique_id == "neopool_mqtt_AA55HASHED_ph_data"

    def test_entity_duplicate_removal(self, hass: HomeAssistant) -> None:
        """Test duplicate entity is removed when canonical already exists."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "AA55HASHED",
                CONF_NODEID_REAL: "REAL123",
                CONF_NODEID_HASHED: "AA55HASHED",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="AA55HASHED")

        entity_registry = er.async_get(hass)
        # Old entity (with real NodeID)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_REAL123_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph_old",
        )
        # Canonical entity already exists
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_AA55HASHED_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph_new",
        )

        _migrate_to_canonical_nodeid(hass, entry)

        # Old entity should be removed
        old_entity = entity_registry.async_get("sensor.neopool_ph_old")
        assert old_entity is None
        # Canonical entity should remain
        new_entity = entity_registry.async_get("sensor.neopool_ph_new")
        assert new_entity is not None

    def test_no_entities_need_migration(self, hass: HomeAssistant) -> None:
        """Test when entities already use canonical NodeID."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "AA55HASHED",
                CONF_NODEID_REAL: "REAL123",
                CONF_NODEID_HASHED: "AA55HASHED",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="AA55HASHED")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_AA55HASHED_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph",
        )

        # Should not raise or modify anything
        _migrate_to_canonical_nodeid(hass, entry)

        entity = entity_registry.async_get("sensor.neopool_ph")
        assert entity is not None
        assert entity.unique_id == "neopool_mqtt_AA55HASHED_ph_data"


# ---------------------------------------------------------------------------
# _disable_unavailable_relay_entities
# ---------------------------------------------------------------------------
class TestDisableUnavailableRelayEntities:
    """Tests for _disable_unavailable_relay_entities."""

    def test_no_relay_data_skips(self, hass: HomeAssistant) -> None:
        """Test skips when no relay data available."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_relays=set(),
            available=False,
        )

        # Should not raise
        _disable_unavailable_relay_entities(hass, entry)

    def test_disables_absent_relay(self, hass: HomeAssistant) -> None:
        """Test disables relay entity not present in SENSOR."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_relays={"Acid"},  # Only Acid is present
            available=True,
        )

        entity_registry = er.async_get(hass)
        # Create Base relay entity (not in available_relays)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_relay_base_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_base",
        )
        # Create Acid relay entity (IS in available_relays)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_relay_acid_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_acid",
        )

        _disable_unavailable_relay_entities(hass, entry)

        # Base should be disabled
        base = entity_registry.async_get("binary_sensor.neopool_relay_base")
        assert base is not None
        assert base.disabled_by == er.RegistryEntryDisabler.INTEGRATION

        # Acid should remain enabled
        acid = entity_registry.async_get("binary_sensor.neopool_relay_acid")
        assert acid is not None
        assert acid.disabled_by is None

    def test_reenables_previously_disabled_relay(self, hass: HomeAssistant) -> None:
        """Test re-enables relay entity that was disabled by integration but is now present."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_relays={"Heating"},  # Heating is now present
            available=True,
        )

        entity_registry = er.async_get(hass)
        entity_entry = entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_relay_heating_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_heating",
        )
        # Simulate previously disabled by integration
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )

        _disable_unavailable_relay_entities(hass, entry)

        # Should be re-enabled
        heating = entity_registry.async_get("binary_sensor.neopool_relay_heating")
        assert heating is not None
        assert heating.disabled_by is None

    def test_does_not_reenable_user_disabled(self, hass: HomeAssistant) -> None:
        """Test does NOT re-enable relay disabled by user."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_relays={"UV"},
            available=True,
        )

        entity_registry = er.async_get(hass)
        entity_entry = entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_relay_uv_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_uv",
        )
        # User disabled
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

        _disable_unavailable_relay_entities(hass, entry)

        # Should remain user-disabled
        uv = entity_registry.async_get("binary_sensor.neopool_relay_uv")
        assert uv is not None
        assert uv.disabled_by == er.RegistryEntryDisabler.USER


# ---------------------------------------------------------------------------
# _disable_unavailable_relay_config_entities
# ---------------------------------------------------------------------------
class TestDisableUnavailableRelayConfigEntities:
    """Tests for _disable_unavailable_relay_config_entities."""

    def _entry(self, hass: HomeAssistant, relays: set[str], available: bool = True):
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_relays=relays,
            available=available,
        )
        return entry

    def test_no_relay_data_skips(self, hass: HomeAssistant) -> None:
        """No relay data and device unavailable → returns without changes."""
        entry = self._entry(hass, set(), available=False)
        _disable_unavailable_relay_config_entities(hass, entry)  # must not raise

    def test_disables_config_entities_for_absent_relay(self, hass: HomeAssistant) -> None:
        """climate_mode is disabled when the Heating relay is absent; uv_mode stays enabled."""
        entry = self._entry(hass, {"UV"})  # UV present, Heating absent
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            "switch",
            DOMAIN,
            "neopool_mqtt_ABC123_climate_mode",
            config_entry=entry,
            suggested_object_id="neopool_climate_mode",
        )
        entity_registry.async_get_or_create(
            "switch",
            DOMAIN,
            "neopool_mqtt_ABC123_uv_mode",
            config_entry=entry,
            suggested_object_id="neopool_uv_mode",
        )

        _disable_unavailable_relay_config_entities(hass, entry)

        climate = entity_registry.async_get("switch.neopool_climate_mode")
        assert climate.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        uv = entity_registry.async_get("switch.neopool_uv_mode")
        assert uv.disabled_by is None

    def test_reenables_previously_disabled(self, hass: HomeAssistant) -> None:
        """A config entity the integration disabled is re-enabled when its relay reappears."""
        entry = self._entry(hass, {"Heating"})  # Heating now present
        entity_registry = er.async_get(hass)
        e = entity_registry.async_get_or_create(
            "number",
            DOMAIN,
            "neopool_mqtt_ABC123_heating_temp",
            config_entry=entry,
            suggested_object_id="neopool_heating_temp",
        )
        entity_registry.async_update_entity(
            e.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
        )

        _disable_unavailable_relay_config_entities(hass, entry)

        assert entity_registry.async_get(e.entity_id).disabled_by is None

    def test_does_not_touch_user_disabled(self, hass: HomeAssistant) -> None:
        """A user-disabled config entity is left alone even when its relay is present."""
        entry = self._entry(hass, {"UV"})
        entity_registry = er.async_get(hass)
        e = entity_registry.async_get_or_create(
            "switch",
            DOMAIN,
            "neopool_mqtt_ABC123_uv_mode",
            config_entry=entry,
            suggested_object_id="neopool_uv_mode",
        )
        entity_registry.async_update_entity(e.entity_id, disabled_by=er.RegistryEntryDisabler.USER)

        _disable_unavailable_relay_config_entities(hass, entry)

        assert entity_registry.async_get(e.entity_id).disabled_by == er.RegistryEntryDisabler.USER


# ---------------------------------------------------------------------------
# _disable_unavailable_module_entities
# ---------------------------------------------------------------------------
class TestDisableUnavailableModuleEntities:
    """Tests for _disable_unavailable_module_entities."""

    def test_no_module_data_skips(self, hass: HomeAssistant) -> None:
        """No module data and device unavailable → function returns without changes."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules=set(),
            available=False,
        )
        _disable_unavailable_module_entities(hass, entry)  # must not raise

    def test_disables_absent_module_entities(self, hass: HomeAssistant) -> None:
        """Entities for modules not in available_modules get disabled by INTEGRATION."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            # Only Hydrolysis is installed; Chlorine / Ionization / Conductivity absent.
            available_modules={"Hydrolysis"},
            available=True,
        )
        entity_registry = er.async_get(hass)
        for domain, key in [
            ("sensor", "chlorine_data"),
            ("number", "chlorine_setpoint"),
            ("sensor", "ionization_data"),
            ("number", "ionization_setpoint"),
            ("sensor", "conductivity_data"),
        ]:
            entity_registry.async_get_or_create(
                domain=domain,
                platform=DOMAIN,
                unique_id=f"neopool_mqtt_ABC123_{key}",
                config_entry=entry,
                suggested_object_id=f"neopool_{key}",
            )

        _disable_unavailable_module_entities(hass, entry)

        # All five should now be disabled by INTEGRATION
        for entity_id in [
            "sensor.neopool_chlorine_data",
            "number.neopool_chlorine_setpoint",
            "sensor.neopool_ionization_data",
            "number.neopool_ionization_setpoint",
            "sensor.neopool_conductivity_data",
        ]:
            e = entity_registry.async_get(entity_id)
            assert e is not None, entity_id
            assert e.disabled_by == er.RegistryEntryDisabler.INTEGRATION, entity_id

    def test_leaves_present_module_entities_enabled(self, hass: HomeAssistant) -> None:
        """Entities whose module IS present stay enabled."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules={"Chlorine"},
            available=True,
        )
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_chlorine_data",
            config_entry=entry,
            suggested_object_id="neopool_chlorine_data",
        )

        _disable_unavailable_module_entities(hass, entry)

        e = entity_registry.async_get("sensor.neopool_chlorine_data")
        assert e is not None
        assert e.disabled_by is None

    def test_reenables_previously_disabled_module_entity(self, hass: HomeAssistant) -> None:
        """An INTEGRATION-disabled entity gets re-enabled when its module reappears."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules={"Ionization"},
            available=True,
        )
        entity_registry = er.async_get(hass)
        created = entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_ionization_data",
            config_entry=entry,
            suggested_object_id="neopool_ionization_data",
        )
        entity_registry.async_update_entity(
            created.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )

        _disable_unavailable_module_entities(hass, entry)

        e = entity_registry.async_get("sensor.neopool_ionization_data")
        assert e is not None
        assert e.disabled_by is None

    def test_does_not_reenable_user_disabled(self, hass: HomeAssistant) -> None:
        """User-disabled entities are left alone even when their module is present."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules={"Chlorine"},
            available=True,
        )
        entity_registry = er.async_get(hass)
        created = entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_chlorine_data",
            config_entry=entry,
            suggested_object_id="neopool_chlorine_data",
        )
        entity_registry.async_update_entity(
            created.entity_id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

        _disable_unavailable_module_entities(hass, entry)

        e = entity_registry.async_get("sensor.neopool_chlorine_data")
        assert e is not None
        assert e.disabled_by == er.RegistryEntryDisabler.USER


# ---------------------------------------------------------------------------
# _disable_unavailable_mode_entities
# ---------------------------------------------------------------------------
class TestDisableUnavailableModeEntities:
    """Tests for _disable_unavailable_mode_entities (hydrolysis g/h entities)."""

    def test_no_unit_data_skips(self, hass: HomeAssistant) -> None:
        """No unit data and device unavailable → returns without changes."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            hydrolysis_unit=None,
            available=False,
        )
        _disable_unavailable_mode_entities(hass, entry)  # must not raise

    def test_unknown_unit_skips(self, hass: HomeAssistant) -> None:
        """Unrecognized unit string → don't touch anything (safe default)."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            hydrolysis_unit="weird",
            available=True,
        )
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_data",
            config_entry=entry,
            suggested_object_id="neopool_hydrolysis_data",
        )
        _disable_unavailable_mode_entities(hass, entry)
        e = entity_registry.async_get("sensor.neopool_hydrolysis_data")
        assert e is not None
        assert e.disabled_by is None  # untouched

    def test_disables_gh_entities_in_percent_mode(self, hass: HomeAssistant) -> None:
        """In % mode, the 3 g/h-labeled sensors get disabled by INTEGRATION."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            hydrolysis_unit="%",
            available=True,
        )
        entity_registry = er.async_get(hass)
        for key in ["hydrolysis_data", "hydrolysis_setpoint_gh", "hydrolysis_max"]:
            entity_registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=f"neopool_mqtt_ABC123_{key}",
                config_entry=entry,
                suggested_object_id=f"neopool_{key}",
            )

        _disable_unavailable_mode_entities(hass, entry)

        for key in ["hydrolysis_data", "hydrolysis_setpoint_gh", "hydrolysis_max"]:
            e = entity_registry.async_get(f"sensor.neopool_{key}")
            assert e is not None, key
            assert e.disabled_by == er.RegistryEntryDisabler.INTEGRATION, key

    def test_reenables_gh_entities_in_gh_mode(self, hass: HomeAssistant) -> None:
        """Flipping back to g/h re-enables previously INTEGRATION-disabled g/h sensors."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            hydrolysis_unit="g/h",
            available=True,
        )
        entity_registry = er.async_get(hass)
        created = entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_data",
            config_entry=entry,
            suggested_object_id="neopool_hydrolysis_data",
        )
        entity_registry.async_update_entity(
            created.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )
        _disable_unavailable_mode_entities(hass, entry)
        e = entity_registry.async_get("sensor.neopool_hydrolysis_data")
        assert e is not None
        assert e.disabled_by is None

    def test_does_not_reenable_user_disabled(self, hass: HomeAssistant) -> None:
        """User-disabled g/h entities stay disabled even when controller is in g/h mode."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            hydrolysis_unit="g/h",
            available=True,
        )
        entity_registry = er.async_get(hass)
        created = entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_max",
            config_entry=entry,
            suggested_object_id="neopool_hydrolysis_max",
        )
        entity_registry.async_update_entity(
            created.entity_id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
        _disable_unavailable_mode_entities(hass, entry)
        e = entity_registry.async_get("sensor.neopool_hydrolysis_max")
        assert e is not None
        assert e.disabled_by == er.RegistryEntryDisabler.USER


# ---------------------------------------------------------------------------
# _refresh_entity_disable_state
# ---------------------------------------------------------------------------
class TestRefreshEntityDisableState:
    """Tests for _refresh_entity_disable_state (orchestrator + reload trigger)."""

    def test_no_changes_no_reload(self, hass: HomeAssistant) -> None:
        """Steady-state: nothing transitions to enabled, no reload scheduled."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules={"Hydrolysis"},
            available_relays={"Acid"},
            hydrolysis_unit="g/h",
            available=True,
        )
        # Pre-create one of each managed entity in the "correct" state
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_relay_acid_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_acid",
        )

        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
            _refresh_entity_disable_state(hass, entry)

        mock_reload.assert_not_called()

    def test_disable_only_no_reload(self, hass: HomeAssistant) -> None:
        """Disable-direction transitions don't trigger a reload."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules=set(),  # Chlorine module not installed
            available_relays={"Acid"},
            hydrolysis_unit="g/h",
            available=True,
        )
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_chlorine_data",
            config_entry=entry,
            suggested_object_id="neopool_chlorine_data",
        )  # currently enabled

        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
            _refresh_entity_disable_state(hass, entry)

        # Entity got disabled, but no reload needed
        e = entity_registry.async_get("sensor.neopool_chlorine_data")
        assert e is not None
        assert e.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        mock_reload.assert_not_called()

    def test_enable_triggers_reload(self, hass: HomeAssistant) -> None:
        """INTEGRATION→None transition triggers a config-entry reload."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="T",
            nodeid="ABC123",
            available_modules={"Chlorine"},  # module now present
            available_relays={"Acid"},
            hydrolysis_unit="g/h",
            available=True,
        )
        entity_registry = er.async_get(hass)
        created = entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_chlorine_data",
            config_entry=entry,
            suggested_object_id="neopool_chlorine_data",
        )
        entity_registry.async_update_entity(
            created.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )

        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
            _refresh_entity_disable_state(hass, entry)

        # Entity re-enabled, reload scheduled
        e = entity_registry.async_get("sensor.neopool_chlorine_data")
        assert e is not None
        assert e.disabled_by is None
        # async_reload was scheduled via async_create_task — give the loop a tick
        # The mock should have been called once with entry.entry_id
        assert mock_reload.call_count >= 1
        mock_reload.assert_any_call(entry.entry_id)


# ---------------------------------------------------------------------------
# async_fetch_device_metadata
# ---------------------------------------------------------------------------
class TestAsyncFetchDeviceMetadata:
    """Tests for async_fetch_device_metadata."""

    @pytest.mark.asyncio
    async def test_full_metadata_fetch(self, hass: HomeAssistant) -> None:
        """Test fetching all metadata: SENSOR, Status 2, Status 5."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_NODEID: "ABC123",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid="ABC123"
        )

        # Register device so _update_device_registry_metadata can find it
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            manufacturer="Sugar Valley",
            name="Pool",
        )

        callbacks: dict[str, object] = {}

        async def mock_subscribe(hass, topic, callback, **kwargs):
            callbacks[topic] = callback
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
        ):
            task = asyncio.create_task(async_fetch_device_metadata(hass, entry, wait_timeout=5.0))
            await asyncio.sleep(0.1)

            # Simulate Status 2 response
            status2_topic = "stat/SmartPool/STATUS2"
            if status2_topic in callbacks:
                msg = MagicMock()
                msg.payload = json.dumps({"StatusFWR": {"Version": "14.4.1(release-tasmota)"}})
                msg.topic = status2_topic
                callbacks[status2_topic](msg)

            await asyncio.sleep(0.1)

            # Simulate Status 5 response
            status5_topic = "stat/SmartPool/STATUS5"
            if status5_topic in callbacks:
                msg = MagicMock()
                msg.payload = json.dumps({"StatusNET": {"IPAddress": "192.168.1.50"}})
                msg.topic = status5_topic
                callbacks[status5_topic](msg)

            await asyncio.sleep(0.1)

            # Simulate SENSOR response
            sensor_topic = "tele/SmartPool/SENSOR"
            if sensor_topic in callbacks:
                msg = MagicMock()
                msg.payload = json.dumps(
                    {
                        "NeoPool": {
                            "Type": "Bayrol",
                            "Powerunit": {"Version": "V6.0.0"},
                            "Relay": {
                                "State": [1, 0, 0],
                                "Acid": 1,
                                "Redox": 0,
                            },
                        }
                    }
                )
                msg.topic = sensor_topic
                callbacks[sensor_topic](msg)

            await task

        assert entry.runtime_data.manufacturer == "Bayrol"
        assert entry.runtime_data.fw_version == "V6.0.0"
        assert entry.runtime_data.tasmota_version == "14.4.1"
        assert entry.runtime_data.device_ip == "192.168.1.50"
        assert entry.runtime_data.available_relays == {"Acid", "Redox"}

        # Check device registry was updated
        device = device_registry.async_get_device_by_identifier((DOMAIN, "ABC123"), entry.entry_id)
        assert device is not None
        assert device.sw_version == "Tasmota 14.4.1 / Powerunit V6.0.0"
        assert device.configuration_url == "http://192.168.1.50"

    @pytest.mark.asyncio
    async def test_status2_json_error_handled(self, hass: HomeAssistant) -> None:
        """Test Status 2 JSON decode error is handled gracefully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid="ABC123"
        )

        callbacks: dict[str, object] = {}

        async def mock_subscribe(hass, topic, callback, **kwargs):
            callbacks[topic] = callback
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
        ):
            task = asyncio.create_task(async_fetch_device_metadata(hass, entry, wait_timeout=0.5))
            await asyncio.sleep(0.1)

            # Send invalid JSON on Status 2
            status2_topic = "stat/SmartPool/STATUS2"
            if status2_topic in callbacks:
                msg = MagicMock()
                msg.payload = "not valid json"
                msg.topic = status2_topic
                callbacks[status2_topic](msg)

            # Send invalid JSON on Status 5
            status5_topic = "stat/SmartPool/STATUS5"
            if status5_topic in callbacks:
                msg = MagicMock()
                msg.payload = b"also invalid"
                msg.topic = status5_topic
                callbacks[status5_topic](msg)

            # Send invalid JSON on SENSOR
            sensor_topic = "tele/SmartPool/SENSOR"
            if sensor_topic in callbacks:
                msg = MagicMock()
                msg.payload = "bad json"
                msg.topic = sensor_topic
                callbacks[sensor_topic](msg)

            await task

        # Nothing should be set
        assert entry.runtime_data.manufacturer is None
        assert entry.runtime_data.tasmota_version is None
        assert entry.runtime_data.device_ip is None

    @pytest.mark.asyncio
    async def test_sensor_timeout_handled(self, hass: HomeAssistant) -> None:
        """Test SENSOR timeout is handled gracefully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid="ABC123"
        )

        async def mock_subscribe(hass, topic, callback, **kwargs):
            return MagicMock()

        with (
            patch(
                "homeassistant.components.mqtt.async_subscribe",
                side_effect=mock_subscribe,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
        ):
            # Very short timeout — nothing will respond
            await async_fetch_device_metadata(hass, entry, wait_timeout=0.2)

        # Should not crash, just no data
        assert entry.runtime_data.manufacturer is None


# ---------------------------------------------------------------------------
# _update_device_registry_metadata
# ---------------------------------------------------------------------------
class TestUpdateDeviceRegistryMetadata:
    """Tests for _update_device_registry_metadata."""

    @pytest.mark.asyncio
    async def test_device_not_found(self, hass: HomeAssistant) -> None:
        """Test graceful handling when device not in registry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "MISSING"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="T",
            nodeid="MISSING",
            manufacturer="Bayrol",
        )

        # Should not raise
        await _update_device_registry_metadata(hass, entry)

    @pytest.mark.asyncio
    async def test_sw_version_building(self, hass: HomeAssistant) -> None:
        """Test sw_version built from tasmota + powerunit versions."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="T",
            nodeid="ABC123",
            tasmota_version="14.4.1",
            fw_version="V6.0.0",
            device_ip="10.0.0.1",
        )

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            name="Pool",
        )

        await _update_device_registry_metadata(hass, entry)

        device = device_registry.async_get_device_by_identifier((DOMAIN, "ABC123"), entry.entry_id)
        assert device.sw_version == "Tasmota 14.4.1 / Powerunit V6.0.0"
        assert device.configuration_url == "http://10.0.0.1"

    @pytest.mark.asyncio
    async def test_sw_version_tasmota_only(self, hass: HomeAssistant) -> None:
        """Test sw_version with only tasmota version."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="T",
            nodeid="ABC123",
            tasmota_version="14.4.1",
        )

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            name="Pool",
        )

        await _update_device_registry_metadata(hass, entry)

        device = device_registry.async_get_device_by_identifier((DOMAIN, "ABC123"), entry.entry_id)
        assert device.sw_version == "Tasmota 14.4.1"

    @pytest.mark.asyncio
    async def test_fallback_config_url(self, hass: HomeAssistant) -> None:
        """Test config_url falls back to Tasmota docs when no IP."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="T",
            nodeid="ABC123",
            manufacturer="Bayrol",
            # No device_ip
        )

        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "ABC123")},
            name="Pool",
        )

        await _update_device_registry_metadata(hass, entry)

        device = device_registry.async_get_device_by_identifier((DOMAIN, "ABC123"), entry.entry_id)
        assert device.configuration_url == "https://tasmota.github.io/docs/NeoPool/"


# ---------------------------------------------------------------------------
# _auto_acquire_dual_nodeids
# ---------------------------------------------------------------------------
class TestAutoAcquireDualNodeids:
    """Tests for _auto_acquire_dual_nodeids."""

    @pytest.mark.asyncio
    async def test_no_mqtt_topic_skips(self, hass: HomeAssistant) -> None:
        """Test skips when no MQTT topic."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: ""},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="", nodeid="")

        await _auto_acquire_dual_nodeids(hass, entry)
        # Should not crash

    @pytest.mark.asyncio
    async def test_first_nodeid_timeout(self, hass: HomeAssistant) -> None:
        """Test skips when first NodeID read times out."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="SmartPool", nodeid="")

        with (
            patch(
                "custom_components.sugar_valley_neopool._wait_for_any_nodeid",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
        ):
            await _auto_acquire_dual_nodeids(hass, entry)
            # Should log warning and return

    @pytest.mark.asyncio
    async def test_invalid_first_nodeid(self, hass: HomeAssistant) -> None:
        """Test skips when first NodeID is invalid."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="SmartPool", nodeid="")

        with (
            patch(
                "custom_components.sugar_valley_neopool._wait_for_any_nodeid",
                new_callable=AsyncMock,
                return_value="hidden",  # Invalid
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
        ):
            await _auto_acquire_dual_nodeids(hass, entry)

    @pytest.mark.asyncio
    async def test_full_dual_acquisition_hashed_first(self, hass: HomeAssistant) -> None:
        """Test full dual acquisition starting with hashed NodeID."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool", CONF_NODEID: "OLD"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="SmartPool", nodeid="OLD")

        call_count = 0

        async def mock_wait_for_any(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "AA55 1234 5678 9ABC DEF0 1234"  # Hashed
            return "0026 0051 5443 5016 2036 3435"  # Real

        with (
            patch(
                "custom_components.sugar_valley_neopool._wait_for_any_nodeid",
                side_effect=mock_wait_for_any,
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await _auto_acquire_dual_nodeids(hass, entry)

        # Config entry should be updated with dual NodeIDs
        assert entry.data.get(CONF_NODEID_HASHED) is not None
        assert entry.data.get(CONF_NODEID_REAL) is not None
        # Canonical should be hashed
        assert entry.data[CONF_NODEID] == entry.data[CONF_NODEID_HASHED]
        assert entry.runtime_data.nodeid == entry.data[CONF_NODEID]

    @pytest.mark.asyncio
    async def test_dual_acquisition_real_first(self, hass: HomeAssistant) -> None:
        """Test dual acquisition starting with real NodeID."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool", CONF_NODEID: "OLD"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="SmartPool", nodeid="OLD")

        call_count = 0

        async def mock_wait_for_any(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "0026 0051 5443 5016 2036 3435"  # Real
            return "AA55 ABCD 1234 5678 90EF 0000"  # Hashed

        with (
            patch(
                "custom_components.sugar_valley_neopool._wait_for_any_nodeid",
                side_effect=mock_wait_for_any,
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await _auto_acquire_dual_nodeids(hass, entry)

        assert entry.data.get(CONF_NODEID_REAL) is not None
        assert entry.data.get(CONF_NODEID_HASHED) is not None

    @pytest.mark.asyncio
    async def test_dual_acquisition_no_real_nodeid(self, hass: HomeAssistant) -> None:
        """Test dual acquisition when second NodeID is not a real one."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_DISCOVERY_PREFIX: "SmartPool", CONF_NODEID: "OLD"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="SmartPool", nodeid="OLD")

        call_count = 0

        async def mock_wait_for_any(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "AA55 1234 5678 9ABC DEF0 1234"  # Hashed
            return None  # Second one failed

        with (
            patch(
                "custom_components.sugar_valley_neopool._wait_for_any_nodeid",
                side_effect=mock_wait_for_any,
            ),
            patch(
                "custom_components.sugar_valley_neopool.async_set_setoption157",
                new_callable=AsyncMock,
            ),
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await _auto_acquire_dual_nodeids(hass, entry)

        # Without a real NodeID, config entry should NOT be updated
        assert CONF_NODEID_REAL not in entry.data or entry.data.get(CONF_NODEID_REAL) is None


# ---------------------------------------------------------------------------
# _wait_for_any_nodeid
# ---------------------------------------------------------------------------
class TestWaitForAnyNodeid:
    """Tests for _wait_for_any_nodeid."""

    @pytest.mark.asyncio
    async def test_receives_valid_nodeid(self, hass: HomeAssistant) -> None:
        """Test receiving a valid NodeID."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            task = asyncio.create_task(_wait_for_any_nodeid(hass, "SmartPool", wait_timeout=5.0))
            await asyncio.sleep(0.1)

            if received_callback:
                msg = MagicMock()
                msg.payload = json.dumps({"NeoPool": {"Powerunit": {"NodeID": "AA55 1234 5678"}}})
                received_callback(msg)

            result = await task

        assert result == "AA55 1234 5678"

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, hass: HomeAssistant) -> None:
        """Test timeout returns None."""

        async def mock_subscribe(hass, topic, callback, **kwargs):
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            result = await _wait_for_any_nodeid(hass, "SmartPool", wait_timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_bytes_payload(self, hass: HomeAssistant) -> None:
        """Test bytes payload is decoded."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            task = asyncio.create_task(_wait_for_any_nodeid(hass, "SmartPool", wait_timeout=5.0))
            await asyncio.sleep(0.1)

            if received_callback:
                msg = MagicMock()
                msg.payload = b'{"NeoPool": {"Powerunit": {"NodeID": "BYTES123"}}}'
                received_callback(msg)

            result = await task

        assert result == "BYTES123"

    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self, hass: HomeAssistant) -> None:
        """Test invalid JSON is ignored."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            task = asyncio.create_task(_wait_for_any_nodeid(hass, "SmartPool", wait_timeout=0.5))
            await asyncio.sleep(0.1)

            if received_callback:
                msg = MagicMock()
                msg.payload = "not json"
                received_callback(msg)

            result = await task

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_nodeid_ignored(self, hass: HomeAssistant) -> None:
        """Test empty NodeID is ignored."""
        received_callback = None

        async def mock_subscribe(hass, topic, callback, **kwargs):
            nonlocal received_callback
            received_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ):
            task = asyncio.create_task(_wait_for_any_nodeid(hass, "SmartPool", wait_timeout=0.5))
            await asyncio.sleep(0.1)

            if received_callback:
                msg = MagicMock()
                msg.payload = json.dumps({"NeoPool": {"Powerunit": {"NodeID": "   "}}})
                received_callback(msg)

            result = await task

        assert result is None


# ---------------------------------------------------------------------------
# _cleanup_removed_entities (rename path)
# ---------------------------------------------------------------------------
class TestCleanupRemovedEntitiesRename:
    """Tests for the entity rename path in _cleanup_removed_entities."""

    def test_renames_powerunit_nodeid_to_system_id(self, hass: HomeAssistant) -> None:
        """Test renames powerunit_nodeid entity to system_id."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_powerunit_nodeid",
            config_entry=entry,
            suggested_object_id="neopool_powerunit_nodeid",
        )

        _cleanup_removed_entities(hass, entry)

        # Old unique_id should be gone, new should exist
        old_entity = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "neopool_mqtt_ABC123_powerunit_nodeid"
        )
        assert old_entity is None

        new_entity = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "neopool_mqtt_ABC123_system_id"
        )
        assert new_entity is not None

    def test_removes_deprecated_entities(self, hass: HomeAssistant) -> None:
        """Test removes deprecated relay entities."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        # Create deprecated entity
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_relay_ph_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_ph",
        )

        _cleanup_removed_entities(hass, entry)

        # Should be removed
        entity = entity_registry.async_get("binary_sensor.neopool_relay_ph")
        assert entity is None

    def test_removes_legacy_format_entities(self, hass: HomeAssistant) -> None:
        """Test removes deprecated entities in legacy format (no NodeID)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        # Create legacy format deprecated entity
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_relay_filtration_state",
            config_entry=entry,
            suggested_object_id="neopool_relay_filtration",
        )

        _cleanup_removed_entities(hass, entry)

        entity = entity_registry.async_get("binary_sensor.neopool_relay_filtration")
        assert entity is None

    def test_realigns_fl1_entity_ids_on_fresh_install(self, hass: HomeAssistant) -> None:
        """Old fresh installs get the new flow-alarm entity_ids (refs #23)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_fl1",
            config_entry=entry,
            suggested_object_id="neopool_hydrolysis_fl1",
        )
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_ph_fl1",
            config_entry=entry,
            suggested_object_id="neopool_ph_fl1",
        )

        _cleanup_removed_entities(hass, entry)

        assert (
            entity_registry.async_get_entity_id(
                "binary_sensor", DOMAIN, "neopool_mqtt_ABC123_hydrolysis_fl1"
            )
            == "binary_sensor.neopool_hydrolysis_flow_alarm"
        )
        assert (
            entity_registry.async_get_entity_id(
                "binary_sensor", DOMAIN, "neopool_mqtt_ABC123_ph_fl1"
            )
            == "binary_sensor.neopool_ph_flow_alarm"
        )

    def test_fl1_realignment_skips_migrated_installs(self, hass: HomeAssistant) -> None:
        """Migrated installs keep YAML-pinned entity_ids (refs #23)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_NODEID: "ABC123",
                "entity_id_mapping": {
                    "hydrolysis_ctrl_fl1": "binary_sensor.neopool_mqtt_hydrolysis_fl1"
                },
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_fl1",
            config_entry=entry,
            suggested_object_id="neopool_mqtt_hydrolysis_fl1",
        )

        _cleanup_removed_entities(hass, entry)

        assert (
            entity_registry.async_get_entity_id(
                "binary_sensor", DOMAIN, "neopool_mqtt_ABC123_hydrolysis_fl1"
            )
            == "binary_sensor.neopool_mqtt_hydrolysis_fl1"
        )

    def test_fl1_realignment_skips_custom_entity_ids(self, hass: HomeAssistant) -> None:
        """User-customized entity_ids are left alone (refs #23)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_fl1",
            config_entry=entry,
            suggested_object_id="my_custom_flow_sensor",
        )

        _cleanup_removed_entities(hass, entry)

        assert (
            entity_registry.async_get_entity_id(
                "binary_sensor", DOMAIN, "neopool_mqtt_ABC123_hydrolysis_fl1"
            )
            == "binary_sensor.my_custom_flow_sensor"
        )

    def test_fl1_realignment_skips_on_target_collision(self, hass: HomeAssistant) -> None:
        """Realignment is skipped when the target entity_id is taken (refs #23)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_NODEID: "ABC123"},
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="T", nodeid="ABC123")

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform=DOMAIN,
            unique_id="neopool_mqtt_ABC123_hydrolysis_fl1",
            config_entry=entry,
            suggested_object_id="neopool_hydrolysis_fl1",
        )
        # Occupy the target entity_id with an unrelated entity
        entity_registry.async_get_or_create(
            domain="binary_sensor",
            platform="mqtt",
            unique_id="some_other_entity",
            suggested_object_id="neopool_hydrolysis_flow_alarm",
        )

        _cleanup_removed_entities(hass, entry)

        assert (
            entity_registry.async_get_entity_id(
                "binary_sensor", DOMAIN, "neopool_mqtt_ABC123_hydrolysis_fl1"
            )
            == "binary_sensor.neopool_hydrolysis_fl1"
        )


# ---------------------------------------------------------------------------
# get_device_info (device_ip config_url path)
# ---------------------------------------------------------------------------
class TestGetDeviceInfoConfigUrl:
    """Tests for get_device_info with device_ip."""

    def test_config_url_with_device_ip(self) -> None:
        """Test config_url uses device IP when available."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_NODEID: "ABC123",
            },
        )
        entry.runtime_data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="T",
            nodeid="ABC123",
            device_ip="192.168.1.50",
        )

        device_info = get_device_info(entry)

        assert device_info["configuration_url"] == "http://192.168.1.50"

    def test_config_url_without_device_ip(self) -> None:
        """Test config_url falls back to Tasmota docs."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_NODEID: "ABC123",
            },
        )
        entry.runtime_data = NeoPoolData(
            device_name="Pool",
            mqtt_topic="T",
            nodeid="ABC123",
        )

        device_info = get_device_info(entry)

        assert device_info["configuration_url"] == "https://tasmota.github.io/docs/NeoPool/"


# ---------------------------------------------------------------------------
# async_migrate_masked_unique_ids (stored real NodeID, ValueError, entity_key)
# ---------------------------------------------------------------------------
class TestMigrateMaskedAdditional:
    """Additional tests for async_migrate_masked_unique_ids."""

    @pytest.mark.asyncio
    async def test_stored_real_nodeid_used(self, hass: HomeAssistant) -> None:
        """Test uses stored CONF_NODEID_REAL when available."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
                CONF_NODEID_REAL: "STORED_REAL_123",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid=masked_nodeid
        )

        # Create entity with masked unique_id
        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"neopool_mqtt_{masked_nodeid}_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph",
        )

        # Should NOT call _wait_for_real_nodeid since stored value exists
        result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True
        entity = entity_registry.async_get("sensor.neopool_ph")
        assert entity is not None
        assert "STORED_REAL_123" in entity.unique_id

    @pytest.mark.asyncio
    async def test_entity_key_extraction_failure(self, hass: HomeAssistant) -> None:
        """Test handles entity_key extraction failure gracefully."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
                CONF_NODEID_REAL: "REAL123",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid=masked_nodeid
        )

        entity_registry = er.async_get(hass)
        # Create entity whose unique_id will fail entity_key extraction
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"neopool_mqtt_{masked_nodeid}",  # No entity key suffix
            config_entry=entry,
            suggested_object_id="neopool_broken",
        )

        with patch(
            "custom_components.sugar_valley_neopool.extract_entity_key_from_masked_unique_id",
            return_value=None,
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_value_error_during_migration(self, hass: HomeAssistant) -> None:
        """Test handles ValueError during entity update."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
                CONF_NODEID_REAL: "REAL123",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid=masked_nodeid
        )

        entity_registry = er.async_get(hass)
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"neopool_mqtt_{masked_nodeid}_ph_data",
            config_entry=entry,
            suggested_object_id="neopool_ph",
        )

        with patch.object(
            entity_registry,
            "async_update_entity",
            side_effect=ValueError("test error"),
        ):
            result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_many_masked_entities_logging(self, hass: HomeAssistant) -> None:
        """Test logging when more than 5 masked entities exist."""
        masked_nodeid = "XXXX XXXX XXXX XXXX XXXX 3435"
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_DEVICE_NAME: "Pool",
                CONF_DISCOVERY_PREFIX: "SmartPool",
                CONF_NODEID: masked_nodeid,
                CONF_NODEID_REAL: "REAL123",
            },
        )
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="Pool", mqtt_topic="SmartPool", nodeid=masked_nodeid
        )

        entity_registry = er.async_get(hass)
        # Create 7 entities with masked unique_ids
        for i in range(7):
            entity_registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=f"neopool_mqtt_{masked_nodeid}_sensor_{i}",
                config_entry=entry,
                suggested_object_id=f"neopool_sensor_{i}",
            )

        result = await async_migrate_masked_unique_ids(hass, entry)

        assert result is True


# ---------------------------------------------------------------------------
# _setup_dynamic_disable_watch (continuous SENSOR watch + rate tracker feed)
# ---------------------------------------------------------------------------
class TestSetupDynamicDisableWatch:
    """Tests for _setup_dynamic_disable_watch and its on_sensor callback."""

    @pytest.mark.asyncio
    async def test_watch_subscribes_to_sensor_topic(self, hass: HomeAssistant) -> None:
        """Setup subscribes to tele/{topic}/SENSOR and stores the unsub via entry."""

        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="MyPool",
            nodeid="ABC123",
            connection_rate_tracker=ConnectionRateTracker(60.0),
        )

        captured_topic: str | None = None

        async def fake_subscribe(_hass, topic, _cb, **_kwargs):
            nonlocal captured_topic
            captured_topic = topic
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=fake_subscribe,
        ):
            await _setup_dynamic_disable_watch(hass, entry)

        assert captured_topic == "tele/MyPool/SENSOR"

    @pytest.mark.asyncio
    async def test_on_sensor_feeds_tracker_and_dispatches(self, hass: HomeAssistant) -> None:
        """A SENSOR message with Connection.* counters updates the tracker."""

        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="MyPool",
            nodeid="ABC123",
            connection_rate_tracker=ConnectionRateTracker(60.0),
        )

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        dispatched: list[str] = []

        def capture_signal(_hass, signal, *_args):
            dispatched.append(signal)

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_dynamic_disable_watch(hass, entry)

        # Invoke the captured callback with a representative payload
        msg = MagicMock()
        msg.payload = json.dumps(
            {
                "NeoPool": {
                    "Connection": {
                        "MBRequests": 1000,
                        "MBNoResponse": 5,
                        "DataOutOfRange": 0,
                    }
                }
            }
        )

        with patch(
            "custom_components.sugar_valley_neopool.async_dispatcher_send",
            side_effect=capture_signal,
        ):
            captured_cb(msg)

        assert entry.runtime_data.connection_rate_tracker.samples_count == 1
        assert dispatched == [connection_rate_signal(entry)]

    async def _run_time_sync(
        self, hass: HomeAssistant, *, auto: bool, last_ts: float | None
    ) -> MagicMock:
        """Drive on_sensor with a far-drifted controller time; return publish mock."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="MyPool",
            nodeid="ABC123",
            auto_time_sync=auto,
            last_time_sync_ts=last_ts,
            connection_rate_tracker=ConnectionRateTracker(60.0),
        )

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_dynamic_disable_watch(hass, entry)

        msg = MagicMock()
        # A controller clock far in the past -> drift well over the threshold.
        msg.payload = json.dumps({"NeoPool": {"Time": "2000-01-01T00:00:00"}})

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            captured_cb(msg)
        return mock_publish

    @pytest.mark.asyncio
    async def test_auto_time_sync_resyncs_on_drift(self, hass: HomeAssistant) -> None:
        """When enabled and drifted past the threshold, an NPTime resync is sent."""
        mock_publish = await self._run_time_sync(hass, auto=True, last_ts=None)
        mock_publish.assert_called_once_with(
            hass,
            "cmnd/MyPool/NPTime",
            "0",
            qos=1,
            retain=False,
        )

    @pytest.mark.asyncio
    async def test_auto_time_sync_disabled_no_resync(self, hass: HomeAssistant) -> None:
        """When the switch is off, no resync is sent even if drifted."""
        mock_publish = await self._run_time_sync(hass, auto=False, last_ts=None)
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_time_sync_respects_cooldown(self, hass: HomeAssistant) -> None:
        """A recent resync (future-dated ts) is within cooldown -> skipped."""
        # last_ts far in the future makes (now - last) negative, i.e. < cooldown.
        mock_publish = await self._run_time_sync(hass, auto=True, last_ts=9999999999.0)
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_sensor_detects_module_change_and_refreshes(self, hass: HomeAssistant) -> None:
        """Module set change triggers _refresh_entity_disable_state."""

        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="MyPool",
            nodeid="ABC123",
            available=True,
            available_modules=set(),  # nothing initially
            connection_rate_tracker=ConnectionRateTracker(60.0),
        )

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_dynamic_disable_watch(hass, entry)

        # Mock the refresh so we can assert it was called
        refresh_calls: list[str] = []
        with patch(
            "custom_components.sugar_valley_neopool._refresh_entity_disable_state",
            side_effect=lambda *_args: refresh_calls.append("called"),
        ):
            msg = MagicMock()
            msg.payload = json.dumps({"NeoPool": {"Modules": {"Chlorine": 1, "Ionization": 0}}})
            captured_cb(msg)

        assert refresh_calls == ["called"]
        assert entry.runtime_data.available_modules == {"Chlorine"}

    @pytest.mark.asyncio
    async def test_on_sensor_no_change_no_refresh(self, hass: HomeAssistant) -> None:
        """Identical signals to last seen → no refresh call (cheap no-op)."""

        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="MyPool",
            nodeid="ABC123",
            available=True,
            available_modules={"Chlorine"},  # already what payload will report
            available_relays={"Acid"},
            hydrolysis_unit="g/h",
            connection_rate_tracker=ConnectionRateTracker(60.0),
        )

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_dynamic_disable_watch(hass, entry)

        refresh_calls: list[str] = []
        with patch(
            "custom_components.sugar_valley_neopool._refresh_entity_disable_state",
            side_effect=lambda *_args: refresh_calls.append("called"),
        ):
            msg = MagicMock()
            msg.payload = json.dumps(
                {
                    "NeoPool": {
                        "Modules": {"Chlorine": 1},
                        "Relay": {"Acid": 0},
                        "Hydrolysis": {"Unit": "g/h"},
                    }
                }
            )
            captured_cb(msg)

        assert refresh_calls == []  # no change → no refresh

    @pytest.mark.asyncio
    async def test_on_sensor_invalid_json_silent(self, hass: HomeAssistant) -> None:
        """Invalid JSON payload is swallowed without raising."""

        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(
            device_name="P",
            mqtt_topic="MyPool",
            nodeid="ABC123",
            connection_rate_tracker=ConnectionRateTracker(60.0),
        )

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_dynamic_disable_watch(hass, entry)

        msg = MagicMock()
        msg.payload = "not valid json {{{"
        captured_cb(msg)  # must not raise

        assert entry.runtime_data.connection_rate_tracker.samples_count == 0


class TestResultWatch:
    """Tests for the stat/RESULT config-register read layer."""

    def test_parse_register_int(self) -> None:
        """Int parsing accepts hex strings, decimal strings, and ints."""
        assert _parse_register_int("0x0417") == 0x0417
        assert _parse_register_int("1047") == 1047
        assert _parse_register_int(0x0417) == 0x0417
        assert _parse_register_int("nonsense") is None
        assert _parse_register_int(None) is None
        assert _parse_register_int(True) is None  # bools are not register values

    @pytest.mark.asyncio
    async def test_result_watch_caches_npread(self, hass: HomeAssistant) -> None:
        """An NPRead RESULT updates register_state and dispatches the signal."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="MyPool", nodeid="ABC123")

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        dispatched: list[str] = []

        def capture_signal(_hass, signal, *_args):
            dispatched.append(signal)

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_result_watch(hass, entry)

        # Real Tasmota format: single-register NPRead returns a scalar Data and a
        # decimal Address (1063 == 0x0427 == REG_UV_MODE).
        msg = MagicMock()
        msg.payload = json.dumps({"NPRead": {"Address": REG_UV_MODE, "Data": 1}})
        with patch(
            "custom_components.sugar_valley_neopool.async_dispatcher_send",
            side_effect=capture_signal,
        ):
            captured_cb(msg)

        assert entry.runtime_data.register_state[REG_UV_MODE] == 1
        assert dispatched == [config_register_signal(entry)]

        # NPReadL-style list Data is also accepted (first element used), and the
        # Address may arrive as a hex string rather than a decimal int.
        msg.payload = json.dumps({"NPRead": {"Address": f"0x{REG_UV_MODE:04X}", "Data": [0]}})
        with patch(
            "custom_components.sugar_valley_neopool.async_dispatcher_send",
            side_effect=capture_signal,
        ):
            captured_cb(msg)

        assert entry.runtime_data.register_state[REG_UV_MODE] == 0

        # Devices with NPResult 1 return BOTH Address and Data as hex strings
        # (confirmed on real hardware). _parse_register_int decodes them.
        msg.payload = json.dumps({"NPRead": {"Address": "0x0427", "Data": "0x0002"}})
        with patch(
            "custom_components.sugar_valley_neopool.async_dispatcher_send",
            side_effect=capture_signal,
        ):
            captured_cb(msg)

        assert entry.runtime_data.register_state[REG_UV_MODE] == 2

    @pytest.mark.asyncio
    async def test_result_watch_ignores_non_npread(self, hass: HomeAssistant) -> None:
        """A non-NPRead RESULT (e.g. a command echo) is ignored."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="MyPool", nodeid="ABC123")

        captured_cb = None

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            nonlocal captured_cb
            captured_cb = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_result_watch(hass, entry)

        msg = MagicMock()
        msg.payload = json.dumps({"NPBoost": "OFF"})
        captured_cb(msg)  # must not raise
        assert entry.runtime_data.register_state == {}

    @pytest.mark.asyncio
    async def test_read_config_registers_publishes_each(self, hass: HomeAssistant) -> None:
        """Startup read fires one NPRead per configured register."""
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="MyPool", nodeid="ABC123")

        with (
            patch(
                "homeassistant.components.mqtt.async_publish",
                new_callable=AsyncMock,
            ) as mock_publish,
            # The reads are paced with asyncio.sleep; patch it so the test does
            # not actually wait NPREAD_BURST_INTERVAL between each publish.
            patch(
                "custom_components.sugar_valley_neopool.asyncio.sleep",
                new_callable=AsyncMock,
            ) as mock_sleep,
        ):
            await _read_config_registers(hass, entry)

        expected = len(CONFIG_REGISTERS) + len(TIMER_ENTITY_REGISTERS)
        assert mock_publish.await_count == expected
        # Each read is paced (the controller drops a fast burst).
        assert mock_sleep.await_count == expected
        topics = {call.args[1] for call in mock_publish.await_args_list}
        assert all(t == "cmnd/MyPool/NPRead" for t in topics)


class TestResultWatchEdges:
    """Edge-case coverage for the stat/RESULT watch."""

    async def _cb(self, hass: HomeAssistant):
        entry = MockConfigEntry(domain=DOMAIN, data={CONF_NODEID: "ABC123"})
        entry.add_to_hass(hass)
        entry.runtime_data = NeoPoolData(device_name="P", mqtt_topic="MyPool", nodeid="ABC123")
        captured = {}

        async def capture_subscribe(_hass, _topic, cb, **_kwargs):
            captured["cb"] = cb
            return MagicMock()

        with patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture_subscribe):
            await _setup_result_watch(hass, entry)
        return entry, captured["cb"]

    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self, hass: HomeAssistant) -> None:
        """Malformed RESULT JSON is ignored without raising."""
        entry, cb = await self._cb(hass)
        msg = MagicMock()
        msg.payload = "not json {{{"
        cb(msg)
        assert entry.runtime_data.register_state == {}

    @pytest.mark.asyncio
    async def test_non_dict_payload_ignored(self, hass: HomeAssistant) -> None:
        """A JSON array/scalar (not an object) is ignored."""
        entry, cb = await self._cb(hass)
        msg = MagicMock()
        msg.payload = json.dumps([1, 2, 3])
        cb(msg)
        assert entry.runtime_data.register_state == {}

    @pytest.mark.asyncio
    async def test_unparseable_address_ignored(self, hass: HomeAssistant) -> None:
        """An NPRead whose Address can't be parsed is dropped."""
        entry, cb = await self._cb(hass)
        msg = MagicMock()
        msg.payload = json.dumps({"NPRead": {"Address": "bogus", "Data": 1}})
        cb(msg)
        assert entry.runtime_data.register_state == {}
