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
    _disable_unavailable_relay_entities,
    _migrate_to_canonical_nodeid,
    _refresh_entity_disable_state,
    _update_device_registry_metadata,
    _wait_for_any_nodeid,
    async_fetch_device_metadata,
    async_migrate_masked_unique_ids,
    get_device_info,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    CONF_NODEID_HASHED,
    CONF_NODEID_REAL,
    DOMAIN,
)
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
        device = device_registry.async_get_device(identifiers={(DOMAIN, "AA55HASHED")})
        assert device is not None
        # Old identifier should be gone
        old_device = device_registry.async_get_device(identifiers={(DOMAIN, "REAL123")})
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
        device = device_registry.async_get_device(identifiers={(DOMAIN, "AA55HASHED")})
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
        device = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123")})
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

        device = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123")})
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

        device = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123")})
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

        device = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123")})
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
