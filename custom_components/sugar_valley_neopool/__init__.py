"""The NeoPool MQTT integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    CMD_NPREAD,
    CMD_TIME,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_ENABLE_REPAIR_NOTIFICATION,
    CONF_FAILURES_THRESHOLD,
    CONF_NODEID,
    CONF_NODEID_HASHED,
    CONF_NODEID_MASKED,
    CONF_NODEID_REAL,
    CONF_OFFLINE_TIMEOUT,
    CONF_RECOVERY_SCRIPT,
    CONFIG_REGISTERS,
    CONNECTION_ERROR_RATE_WINDOW_SECONDS,
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_RECOVERY_SCRIPT,
    DOMAIN,
    JSON_PATH_POWERUNIT_VERSION,
    JSON_PATH_TIME,
    JSON_PATH_TYPE,
    MANUFACTURER,
    MODEL,
    PLATFORMS,
    TIME_SYNC_COOLDOWN_SECONDS,
    TIME_SYNC_DRIFT_THRESHOLD_SECONDS,
    YAML_ENTITIES_TO_DELETE,
    YAML_TO_INTEGRATION_KEY_MAP,
)
from .helpers import (
    ConnectionRateTracker,
    async_set_setoption157,
    classify_nodeid,
    extract_entity_key_from_masked_unique_id,
    get_nested_value,
    is_masked_unique_id,
    normalize_nodeid,
    validate_nodeid,
)
from .services import async_setup_services, async_unload_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Config entry version for migrations
CONFIG_ENTRY_VERSION = 2


def connection_rate_signal(entry: ConfigEntry) -> str:
    """Return the dispatcher signal name for connection-rate updates.

    Used by the rate sensor and the problem binary_sensor to react when
    the integration's central SENSOR watch updates the shared
    ConnectionRateTracker.
    """
    return f"{DOMAIN}_connection_rate_updated_{entry.entry_id}"


def config_register_signal(entry: ConfigEntry) -> str:
    """Return the dispatcher signal name for config-register cache updates.

    Fired by the stat/RESULT watch whenever a Group 2 config register value is
    read or confirmed; consumed by the register-backed switch/number entities.
    """
    return f"{DOMAIN}_config_register_updated_{entry.entry_id}"


@dataclass
class NeoPoolData:
    """Runtime data for the NeoPool integration."""

    device_name: str
    mqtt_topic: str
    nodeid: str
    sensor_data: dict[str, Any] = field(default_factory=dict)
    available: bool = False
    device_id: str | None = None  # For device triggers
    entity_id_mapping: dict[str, str] = field(default_factory=dict)  # For YAML migration
    # Device metadata from MQTT (updated dynamically)
    manufacturer: str | None = None  # From NeoPool.Type
    fw_version: str | None = None  # From NeoPool.Powerunit.Version
    tasmota_version: str | None = None  # From StatusFWR.Version
    available_relays: set[str] = field(default_factory=set)  # Relay keys present in SENSOR
    # Module keys reported as installed (value == 1) in NeoPool.Modules; used to
    # auto-disable sensor/number entities for modules the controller doesn't have.
    available_modules: set[str] = field(default_factory=set)
    # Hydrolysis.Unit ("%" or "g/h"); used to auto-disable g/h-labeled entities
    # when the controller is in % mode. None means we haven't seen it yet.
    hydrolysis_unit: str | None = None
    device_ip: str | None = None  # From Status 5 network info
    # Sliding-window tracker for the Modbus connection error rate.
    # Populated lazily on first SENSOR message by _setup_dynamic_disable_watch
    # so the rate sensor / problem binary sensor can read .rate.
    connection_rate_tracker: ConnectionRateTracker | None = None
    # Auto time-sync: live state of the HA-side switch (restored via
    # RestoreEntity, not stored in options to avoid reload-on-toggle) and the
    # timestamp of the last NPTime resync (cooldown guard). Read by the SENSOR
    # watch in _setup_dynamic_disable_watch.
    auto_time_sync: bool = False
    last_time_sync_ts: float | None = None
    # Cache of Group 2 config registers (address -> raw value). These are not in
    # the SENSOR payload; populated by a startup NPRead and kept current by the
    # write-ACK. The stat/RESULT watch updates this and fans out via
    # config_register_signal.
    register_state: dict[int, int] = field(default_factory=dict)


type NeoPoolConfigEntry = ConfigEntry[NeoPoolData]


async def async_setup_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Set up NeoPool MQTT from a config entry."""
    _LOGGER.debug("Setting up NeoPool MQTT integration")

    # Wait for MQTT to be available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available")

    _LOGGER.debug("MQTT client is available")

    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    mqtt_topic = entry.data.get(CONF_DISCOVERY_PREFIX, "")
    nodeid = entry.data.get(CONF_NODEID, "")

    # Get entity_id_mapping from config entry data (set by config_flow migration)
    entity_id_mapping = entry.data.get("entity_id_mapping", {})

    # Initialize runtime data
    entry.runtime_data = NeoPoolData(
        device_name=device_name,
        mqtt_topic=mqtt_topic,
        nodeid=nodeid,
        entity_id_mapping=entity_id_mapping,
        connection_rate_tracker=ConnectionRateTracker(
            window_seconds=CONNECTION_ERROR_RATE_WINDOW_SECONDS,
        ),
    )

    # Auto-acquire dual NodeIDs if not yet stored (upgrade from older version)
    # Must run BEFORE device registration to avoid creating a duplicate device
    if not entry.data.get(CONF_NODEID_HASHED):
        _LOGGER.info(
            "Dual NodeID not yet acquired — triggering auto-acquisition for %s",
            mqtt_topic,
        )
        await _auto_acquire_dual_nodeids(hass, entry)
        # Re-read nodeid since it may have changed to hashed canonical
        nodeid = entry.data.get(CONF_NODEID, "")
        entry.runtime_data.nodeid = nodeid

    # Migrate entities and device from old NodeID format to canonical (runs every startup)
    # Handles: real→hashed, masked→hashed, and cleanup of duplicates
    _migrate_to_canonical_nodeid(hass, entry)

    # Register device in device registry and store device_id for triggers
    await async_register_device(hass, entry)

    # Fetch device metadata (manufacturer, firmware version) from MQTT
    # This updates the device registry with actual device info
    await async_fetch_device_metadata(hass, entry)

    # Run sanity check for masked unique_ids and migrate if needed
    # This must happen before platform setup to fix NodeID before entities are created
    migration_success = await async_migrate_masked_unique_ids(hass, entry)
    if not migration_success:
        _LOGGER.warning(
            "Masked unique_id migration failed - entities may have incorrect unique_ids. "
            "Check that SetOption157 is enabled on the Tasmota device."
        )

    # Clean up removed entities (runs for all users, not just YAML migration)
    _cleanup_removed_entities(hass, entry)

    # Disable relay entities that aren't assigned on the controller
    _disable_unavailable_relay_entities(hass, entry)

    # Disable sensor/number entities for modules the controller doesn't have
    _disable_unavailable_module_entities(hass, entry)

    # Disable g/h-labeled entities when the controller is in % display mode
    _disable_unavailable_mode_entities(hass, entry)

    # Subscribe to stat/RESULT and request the Group 2 config registers (not in
    # SENSOR) so the register-backed entities have state on first render.
    # Subscribe before reading so the responses are captured.
    await _setup_result_watch(hass, entry)
    await _read_config_registers(hass, entry)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Platform setup complete for %d platforms", len(PLATFORMS))

    # Register integration services (Group 4a timer scheduling). Idempotent, so
    # registering once per entry setup is safe with multiple devices.
    async_setup_services(hass)

    # Apply entity_id_mapping to preserve original YAML entity IDs
    if entity_id_mapping:
        # Log what entities exist for this integration before renaming
        entity_registry = er.async_get(hass)
        integration_entities = [
            e for e in entity_registry.entities.values() if e.platform == DOMAIN
        ]
        _LOGGER.debug(
            "Found %d entities for platform '%s' before applying mapping",
            len(integration_entities),
            DOMAIN,
        )
        for e in integration_entities[:10]:  # Log first 10
            _LOGGER.debug("  - %s (unique_id=%s)", e.entity_id, e.unique_id)
        if len(integration_entities) > 10:
            _LOGGER.debug("  ... and %d more", len(integration_entities) - 10)

        await _apply_entity_id_mapping(hass, entry, entity_id_mapping)

        # Clean up orphaned YAML entities that can't be migrated (e.g., binary sensors
        # replaced by switches). This runs only when entity_id_mapping exists (YAML migration).
        await _cleanup_orphaned_yaml_entities(hass, entry)

    # Subscribe to SENSOR telemetry to dynamically react to module/relay/mode
    # changes (e.g. user installs a module, flips display unit). On change,
    # idempotently flips entity disabled_by flags and schedules a reload if any
    # entity needs to be (re-)materialized.
    await _setup_dynamic_disable_watch(hass, entry)

    # Note: No manual update listener needed - OptionsFlowWithReload handles reload automatically

    _LOGGER.info("NeoPool MQTT integration setup complete for %s", device_name)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading NeoPool MQTT integration")

    # Unload platforms - only cleanup runtime_data if successful
    # ref.: https://developers.home-assistant.io/blog/2025/02/19/new-config-entry-states/
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.info("NeoPool MQTT integration unloaded successfully")
        # Remove integration services once the last entry is gone. async_entries
        # still includes this entry during unload, so <=1 means it's the only one.
        if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
            async_unload_services(hass)
    else:
        _LOGGER.debug("Platform unload failed, skipping cleanup")

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new format.

    This function handles migration of config entries when the schema version changes.
    """
    # Handle downgrade scenario (per HA best practice)
    if config_entry.version > CONFIG_ENTRY_VERSION:
        _LOGGER.error(
            "Cannot downgrade from version %s to %s",
            config_entry.version,
            CONFIG_ENTRY_VERSION,
        )
        return True

    _LOGGER.info(
        "Migrating config entry from version %s to %s",
        config_entry.version,
        CONFIG_ENTRY_VERSION,
    )

    if config_entry.version == 1:
        # Version 1 -> 2: Add options for repair notifications and offline timeout
        new_options = {**config_entry.options}

        # Add new options with defaults if not present
        if CONF_ENABLE_REPAIR_NOTIFICATION not in new_options:
            new_options[CONF_ENABLE_REPAIR_NOTIFICATION] = DEFAULT_ENABLE_REPAIR_NOTIFICATION
        if CONF_FAILURES_THRESHOLD not in new_options:
            new_options[CONF_FAILURES_THRESHOLD] = DEFAULT_FAILURES_THRESHOLD
        if CONF_RECOVERY_SCRIPT not in new_options:
            new_options[CONF_RECOVERY_SCRIPT] = DEFAULT_RECOVERY_SCRIPT
        if CONF_OFFLINE_TIMEOUT not in new_options:
            new_options[CONF_OFFLINE_TIMEOUT] = DEFAULT_OFFLINE_TIMEOUT

        hass.config_entries.async_update_entry(
            config_entry,
            options=new_options,
            version=2,
        )
        _LOGGER.info("Migration to version 2 complete")

    return True


async def _apply_entity_id_mapping(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    entity_id_mapping: dict[str, str],
) -> None:
    """Apply entity_id_mapping to preserve original YAML entity IDs.

    After entities are created with has_entity_name=True, their entity_ids
    are auto-generated based on device_name + translation_key. This function
    updates the entity registry to use the original YAML entity_ids instead,
    preserving dashboards, automations, and history references.

    The mapping supports two formats for backwards compatibility:
    - New format: entity_key -> full entity_id (e.g., "sensor.neopool_mqtt_ph_data")
    - Old format: entity_key -> object_id only (e.g., "neopool_mqtt_ph_data")

    Args:
        hass: Home Assistant instance
        entry: Config entry
        entity_id_mapping: Dict mapping entity_key -> original entity_id or object_id
    """
    entity_registry = er.async_get(hass)
    nodeid = entry.runtime_data.nodeid
    updated_count = 0

    _LOGGER.debug(
        "Applying entity_id_mapping with %d entries, nodeid=%s",
        len(entity_id_mapping),
        nodeid,
    )

    # Entity domains to search - integration creates entities across these platforms
    all_domains = ["sensor", "binary_sensor", "switch", "select", "number", "button"]

    # Build set of entity keys that should be deleted (not mapped)
    # These are YAML entities replaced by different entity types in the integration
    keys_to_skip = {entity_key for _, entity_key in YAML_ENTITIES_TO_DELETE}

    for yaml_entity_key, target_value in entity_id_mapping.items():
        # Skip entities that are marked for deletion (replaced by different entity types)
        if yaml_entity_key in keys_to_skip:
            continue
        # Determine if target_value is full entity_id or just object_id
        # Full entity_id format: "domain.object_id" (contains a dot)
        if "." in target_value:
            # New format: full entity_id with domain
            target_domain, target_object_id = target_value.split(".", 1)
            target_entity_id = target_value
            # Search in specific domain first, then others as fallback
            domains_to_search = [target_domain] + [d for d in all_domains if d != target_domain]
        else:
            # Old format: just object_id (backwards compatibility)
            target_object_id = target_value
            target_entity_id = None  # Will be determined after finding entity
            domains_to_search = all_domains

        _LOGGER.debug(
            "Processing mapping: yaml_key=%s -> target=%s",
            yaml_entity_key,
            target_value,
        )

        # Translate YAML entity key to integration entity key
        # YAML package uses different naming (e.g., "filtration_switch" vs "filtration")
        integration_key = YAML_TO_INTEGRATION_KEY_MAP.get(yaml_entity_key, yaml_entity_key)

        # Find the entity by its unique_id (NodeID-based pattern)
        unique_id = f"neopool_mqtt_{nodeid}_{integration_key}"

        # Search for entity in domains (prioritizing target domain if known)
        current_entity_id = None
        for domain in domains_to_search:
            entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
            if entity_id:
                current_entity_id = entity_id
                break

        if current_entity_id is None:
            _LOGGER.debug(
                "Entity with unique_id %s not found (yaml_key=%s, integration_key=%s)",
                unique_id,
                yaml_entity_key,
                integration_key,
            )
            continue

        # For old format, build target_entity_id from found entity's domain
        if target_entity_id is None:
            current_domain = current_entity_id.split(".", 1)[0]
            target_entity_id = f"{current_domain}.{target_object_id}"
        else:
            current_domain = current_entity_id.split(".", 1)[0]

        # Check if domains match - HA doesn't allow cross-domain entity renames
        target_domain_check = target_entity_id.split(".", 1)[0]
        if current_domain != target_domain_check:
            _LOGGER.debug(
                "Skipping cross-domain mapping: %s -> %s (domains don't match: %s != %s)",
                current_entity_id,
                target_entity_id,
                current_domain,
                target_domain_check,
            )
            continue

        # Skip if already correct
        if current_entity_id == target_entity_id:
            _LOGGER.debug("Entity %s already has correct entity_id", current_entity_id)
            continue

        # Check if target entity_id is available
        existing_entity = entity_registry.async_get(target_entity_id)
        if existing_entity is not None:
            _LOGGER.warning(
                "Cannot rename %s to %s - target already exists "
                "(platform=%s, unique_id=%s, config_entry=%s)",
                current_entity_id,
                target_entity_id,
                existing_entity.platform,
                existing_entity.unique_id,
                existing_entity.config_entry_id,
            )
            continue

        # Update entity_id in registry
        entity_registry.async_update_entity(
            current_entity_id,
            new_entity_id=target_entity_id,
        )
        updated_count += 1
        _LOGGER.info(
            "Renamed entity %s -> %s to preserve YAML entity_id",
            current_entity_id,
            target_entity_id,
        )

    if updated_count > 0:
        _LOGGER.info(
            "Applied entity_id_mapping: %d entities renamed to preserve YAML IDs",
            updated_count,
        )


async def _cleanup_orphaned_yaml_entities(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
) -> None:
    """Delete orphaned YAML entities that have no equivalent in the integration.

    Some YAML package entities (e.g., relay state binary sensors) were replaced
    by different entity types in the integration (e.g., switches). Since Home
    Assistant doesn't allow cross-domain entity renames, these orphaned entities
    are deleted during migration to keep the entity registry clean.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    entity_registry = er.async_get(hass)
    nodeid = entry.runtime_data.nodeid
    deleted_count = 0

    _LOGGER.debug("Checking for orphaned YAML entities to clean up")

    for domain, entity_key in YAML_ENTITIES_TO_DELETE:
        # Build the unique_id pattern for YAML entities
        # YAML entities use: neopool_mqtt_{entity_key} (without NodeID)
        yaml_unique_id = f"neopool_mqtt_{entity_key}"

        # Find entity by unique_id in the specified domain
        # Check both with and without NodeID in unique_id (different YAML versions)
        unique_ids_to_check = [
            yaml_unique_id,  # Old YAML format: neopool_mqtt_{entity_key}
            f"neopool_mqtt_{nodeid}_{entity_key}",  # If somehow migrated with NodeID
        ]

        for unique_id in unique_ids_to_check:
            entity_id = entity_registry.async_get_entity_id(domain, "mqtt", unique_id)
            if entity_id:
                entity_entry = entity_registry.async_get(entity_id)
                # Only delete if it's an orphaned MQTT entity (no config_entry or orphaned)
                if entity_entry and (
                    entity_entry.config_entry_id is None or entity_entry.platform == "mqtt"
                ):
                    entity_registry.async_remove(entity_id)
                    deleted_count += 1
                    _LOGGER.info(
                        "Deleted orphaned YAML entity %s (unique_id=%s) - "
                        "replaced by integration switch entity",
                        entity_id,
                        unique_id,
                    )

    if deleted_count > 0:
        _LOGGER.info(
            "Cleaned up %d orphaned YAML entities that were replaced by integration entities",
            deleted_count,
        )
    else:
        _LOGGER.debug("No orphaned YAML entities found to clean up")


@callback
def _migrate_to_canonical_nodeid(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Migrate device and entities to use the canonical NodeID.

    Runs on EVERY startup. Handles all cases:
    - Entities with real NodeID → migrate to hashed (canonical)
    - Entities with masked NodeID → migrate to canonical
    - Device registry with old identifier → update to canonical
    - Duplicate entities from failed migrations → remove duplicates

    This is idempotent — running it when everything is already correct
    produces no changes.
    """
    canonical = entry.data.get(CONF_NODEID, "")
    nodeid_real = entry.data.get(CONF_NODEID_REAL, "")
    nodeid_hashed = entry.data.get(CONF_NODEID_HASHED, "")

    if not canonical:
        _LOGGER.debug("No canonical NodeID, skipping migration")
        return

    # Collect all old NodeID values that should be migrated to canonical
    old_nodeids = set()
    if nodeid_real and nodeid_real != canonical:
        old_nodeids.add(nodeid_real)
    # Also check for the original CONF_NODEID value before it was updated
    # (handles case where config was updated but entities weren't migrated)
    if nodeid_hashed and nodeid_hashed != canonical:
        # If canonical is NOT the hashed one, something is off — skip
        pass

    if not old_nodeids:
        _LOGGER.debug("No old NodeIDs to migrate from, canonical is up to date")
        return

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Step 1: Migrate device registry identifiers
    for old_nodeid in old_nodeids:
        old_device = device_registry.async_get_device(identifiers={(DOMAIN, old_nodeid)})
        canonical_device = device_registry.async_get_device(identifiers={(DOMAIN, canonical)})

        if old_device and canonical_device and old_device.id != canonical_device.id:
            # Both exist — remove the NEW duplicate (empty), keep the
            # ORIGINAL (has history, area, automations), update its identifier
            device_registry.async_remove_device(canonical_device.id)
            device_registry.async_update_device(
                old_device.id,
                new_identifiers={(DOMAIN, canonical)},
            )
            _LOGGER.info(
                "Removed duplicate device, migrated original: %s -> %s",
                old_nodeid,
                canonical,
            )
        elif old_device and not canonical_device:
            # Only old exists — update its identifier
            device_registry.async_update_device(
                old_device.id,
                new_identifiers={(DOMAIN, canonical)},
            )
            _LOGGER.info(
                "Migrated device identifier: %s -> %s",
                old_nodeid,
                canonical,
            )

    # Step 2: Migrate entity unique_ids
    migrated = 0
    removed_duplicates = 0
    for entity in list(entity_registry.entities.values()):
        if entity.config_entry_id != entry.entry_id:
            continue
        if not entity.unique_id:
            continue

        # Check if this entity uses an old NodeID
        matched_old = None
        for old_nodeid in old_nodeids:
            if old_nodeid in entity.unique_id:
                matched_old = old_nodeid
                break

        if not matched_old:
            continue

        new_unique_id = entity.unique_id.replace(matched_old, canonical)

        # Check if an entity with the new unique_id already exists
        existing_entity_id = entity_registry.async_get_entity_id(
            entity.domain, DOMAIN, new_unique_id
        )
        if existing_entity_id and existing_entity_id != entity.entity_id:
            # Duplicate: canonical entity already exists, remove the old one
            entity_registry.async_remove(entity.entity_id)
            removed_duplicates += 1
            _LOGGER.debug(
                "Removed duplicate entity %s (old unique_id=%s, canonical already exists as %s)",
                entity.entity_id,
                entity.unique_id,
                existing_entity_id,
            )
            continue

        # No duplicate — migrate the unique_id
        entity_registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
        migrated += 1

    if migrated or removed_duplicates:
        _LOGGER.info(
            "NodeID migration: %d entities migrated, %d duplicates removed (%s -> %s)",
            migrated,
            removed_duplicates,
            old_nodeids,
            canonical,
        )
    else:
        _LOGGER.debug(
            "No entities needed migration to canonical NodeID %s",
            canonical,
        )


@callback
def _cleanup_removed_entities(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Remove entities that were deleted from the integration.

    Removes registry entries for entities whose descriptions have been removed,
    preventing them from lingering as unavailable.
    """
    # Entities removed in previous versions (Relay.State[n] with assumed function mapping)
    removed_entity_keys = [
        ("binary_sensor", "relay_ph_state"),
        ("binary_sensor", "relay_filtration_state"),
        ("binary_sensor", "relay_light_state"),
        # The pool light moved from the switch platform to a dedicated light
        # entity (light.<name>_light). Drop the old switch so it doesn't linger.
        ("switch", "light"),
        # AUX relays moved from the switch platform (Berry-only NPAux commands)
        # to register-driven "aux<n>_mode" selects + read-only "aux<n>" binary
        # sensors. Drop the old switches so they don't linger as unavailable.
        ("switch", "aux1"),
        ("switch", "aux2"),
        ("switch", "aux3"),
        ("switch", "aux4"),
    ]

    # Entities renamed in this version
    renamed_entity_keys = [
        ("sensor", "powerunit_nodeid", "system_id"),
    ]

    entity_registry = er.async_get(hass)
    nodeid = entry.data.get(CONF_NODEID, "")

    for domain, entity_key in removed_entity_keys:
        # Check both NodeID-based and legacy (no NodeID) unique_id formats
        unique_ids = [f"neopool_mqtt_{nodeid}_{entity_key}"]
        if nodeid:
            unique_ids.append(f"neopool_mqtt_{entity_key}")
        for unique_id in unique_ids:
            entity_entry = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
            if entity_entry:
                entity_registry.async_remove(entity_entry)
                _LOGGER.info(
                    "Removed deprecated entity %s (unique_id=%s)",
                    entity_entry,
                    unique_id,
                )

    for domain, old_key, new_key in renamed_entity_keys:
        old_unique_id = f"neopool_mqtt_{nodeid}_{old_key}"
        new_unique_id = f"neopool_mqtt_{nodeid}_{new_key}"
        entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, old_unique_id)
        if entity_id:
            entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)
            _LOGGER.info(
                "Renamed entity %s: %s -> %s",
                entity_id,
                old_unique_id,
                new_unique_id,
            )


@callback
def _disable_unavailable_relay_entities(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Disable relay entities that aren't assigned on the controller.

    Uses available_relays from SENSOR payload to determine which relays
    are actually present. Only disables relays that are confirmed absent.
    Re-enables relays that are present but were previously disabled by
    the integration.
    """
    available = entry.runtime_data.available_relays
    if not available and not entry.runtime_data.available:
        # No SENSOR data received yet — can't determine relay availability
        _LOGGER.debug("No relay data available, skipping relay entity management")
        return

    entity_registry = er.async_get(hass)
    nodeid = entry.data.get(CONF_NODEID, "")

    # Map entity key → relay name in JSON
    relay_key_map = {
        "relay_acid_state": "Acid",
        "relay_base_state": "Base",
        "relay_redox_state": "Redox",
        "relay_chlorine_state": "Chlorine",
        "relay_conductivity_state": "Conductivity",
        "relay_heating_state": "Heating",
        "relay_uv_state": "UV",
        "relay_valve_state": "Valve",
    }

    for entity_key, relay_name in relay_key_map.items():
        unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"
        entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        if not entity_id:
            continue

        entity_entry = entity_registry.async_get(entity_id)
        if not entity_entry:
            continue

        is_present = relay_name in available

        if not is_present and entity_entry.disabled_by is None:
            # Relay not assigned → disable
            entity_registry.async_update_entity(
                entity_id,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            )
            _LOGGER.warning(
                "Disabled relay entity %s (%s not assigned on controller)",
                entity_id,
                relay_name,
            )
        elif is_present and entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            # Relay IS assigned but was disabled by us → re-enable
            entity_registry.async_update_entity(
                entity_id,
                disabled_by=None,
            )
            _LOGGER.warning(
                "Re-enabled relay entity %s (%s is assigned on controller)",
                entity_id,
                relay_name,
            )


# Map: module name in NeoPool.Modules → (domain, entity_key) entries to manage.
# Only entities that go unavailable when the module is absent belong here.
# Relay state binary sensors (e.g. relay_chlorine_state) are managed separately
# by _disable_unavailable_relay_entities via NeoPool.Relay detection.
_MODULE_ENTITY_MAP: Final[dict[str, list[tuple[str, str]]]] = {
    "Chlorine": [
        ("sensor", "chlorine_data"),
        ("number", "chlorine_setpoint"),
    ],
    "Ionization": [
        ("sensor", "ionization_data"),
        ("number", "ionization_setpoint"),
    ],
    "Conductivity": [
        ("sensor", "conductivity_data"),
    ],
}


@callback
def _disable_unavailable_module_entities(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Disable sensor/number entities for NeoPool modules not installed.

    Uses available_modules from SENSOR payload (NeoPool.Modules) to decide.
    Only acts on entities whose disabled_by is either None or INTEGRATION —
    user-disabled entities (disabled_by=USER) are left alone. Re-enables
    entities that were previously disabled by the integration when the
    module is later detected as present.
    """
    available = entry.runtime_data.available_modules
    if not available and not entry.runtime_data.available:
        # No SENSOR data received yet — can't determine module availability
        _LOGGER.debug("No module data available, skipping module entity management")
        return

    entity_registry = er.async_get(hass)
    nodeid = entry.data.get(CONF_NODEID, "")

    for module_name, entity_descriptors in _MODULE_ENTITY_MAP.items():
        is_present = module_name in available
        for domain, entity_key in entity_descriptors:
            unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"
            entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
            if not entity_id:
                continue

            entity_entry = entity_registry.async_get(entity_id)
            if not entity_entry:
                continue

            if not is_present and entity_entry.disabled_by is None:
                entity_registry.async_update_entity(
                    entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )
                _LOGGER.warning(
                    "Disabled module entity %s (%s module not installed)",
                    entity_id,
                    module_name,
                )
            elif is_present and entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
                entity_registry.async_update_entity(entity_id, disabled_by=None)
                _LOGGER.warning(
                    "Re-enabled module entity %s (%s module is installed)",
                    entity_id,
                    module_name,
                )


# (domain, entity_key) entries that go unavailable when the controller's
# hydrolysis display unit is "%": the JSON values exist but in % mode the
# absolute g/h amount is unrecoverable (Max collapses to 100).
_MODE_DEPENDENT_GH_ENTITIES: Final[list[tuple[str, str]]] = [
    ("sensor", "hydrolysis_data"),  # the g/h sensor
    ("sensor", "hydrolysis_setpoint_gh"),
    ("sensor", "hydrolysis_max"),
]


@callback
def _disable_unavailable_mode_entities(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Disable g/h-labeled entities when the controller is in % display mode.

    Uses hydrolysis_unit from SENSOR payload (NeoPool.Hydrolysis.Unit).
    Only acts on entities whose disabled_by is None or INTEGRATION — user-disabled
    entities are left alone. Re-enables INTEGRATION-disabled entities when the
    unit flips back to "g/h".
    """
    unit = entry.runtime_data.hydrolysis_unit
    if unit is None and not entry.runtime_data.available:
        # No SENSOR data received yet — can't determine display unit
        _LOGGER.debug("No hydrolysis unit available, skipping mode-dependent entity management")
        return

    # Treat unknown unit as "we don't know" → don't disable; only act on confirmed "%"
    if unit not in ("%", "g/h"):
        return

    is_percent_mode = unit == "%"
    entity_registry = er.async_get(hass)
    nodeid = entry.data.get(CONF_NODEID, "")

    for domain, entity_key in _MODE_DEPENDENT_GH_ENTITIES:
        unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"
        entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not entity_id:
            continue

        entity_entry = entity_registry.async_get(entity_id)
        if not entity_entry:
            continue

        if is_percent_mode and entity_entry.disabled_by is None:
            entity_registry.async_update_entity(
                entity_id,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            )
            _LOGGER.warning(
                "Disabled mode entity %s (controller is in %% mode)",
                entity_id,
            )
        elif (
            not is_percent_mode and entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        ):
            entity_registry.async_update_entity(entity_id, disabled_by=None)
            _LOGGER.warning(
                "Re-enabled mode entity %s (controller is in g/h mode)",
                entity_id,
            )


@callback
def _refresh_entity_disable_state(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Re-evaluate all dynamic entity disable rules; trigger reload on enable.

    Runs the three disable management functions (relays, modules, hydrolysis
    unit mode) atomically. If any entity transitions from INTEGRATION-disabled
    to enabled, schedules a config-entry reload so the re-enabled entities
    actually materialize (HA does NOT create entities on registry flag flip
    alone — a reload is required).

    Disable transitions (None → INTEGRATION) don't need a reload; the entity
    just gets hidden from the UI and cleaned up on the next natural reload.
    """
    entity_registry = er.async_get(hass)
    nodeid = entry.data.get(CONF_NODEID, "")

    # Collect entity_ids for everything we manage across the three functions
    managed_keys = set()
    for relay_key in [
        "relay_acid_state",
        "relay_base_state",
        "relay_redox_state",
        "relay_chlorine_state",
        "relay_conductivity_state",
        "relay_heating_state",
        "relay_uv_state",
        "relay_valve_state",
    ]:
        managed_keys.add(("binary_sensor", relay_key))
    for entries in _MODULE_ENTITY_MAP.values():
        managed_keys.update(entries)
    managed_keys.update(_MODE_DEPENDENT_GH_ENTITIES)

    # Snapshot which managed entities are currently INTEGRATION-disabled
    was_disabled = set()
    for domain, key in managed_keys:
        unique_id = f"neopool_mqtt_{nodeid}_{key}"
        eid = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if not eid:
            continue
        e = entity_registry.async_get(eid)
        if e and e.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            was_disabled.add(eid)

    # Run all three management functions (each is idempotent)
    _disable_unavailable_relay_entities(hass, entry)
    _disable_unavailable_module_entities(hass, entry)
    _disable_unavailable_mode_entities(hass, entry)

    # Detect re-enable transitions (INTEGRATION → None)
    reenabled = {
        eid
        for eid in was_disabled
        if (e := entity_registry.async_get(eid)) is not None and e.disabled_by is None
    }
    if reenabled:
        _LOGGER.warning(
            "Re-enabled %d previously-disabled entities, scheduling integration reload: %s",
            len(reenabled),
            sorted(reenabled),
        )
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def _setup_dynamic_disable_watch(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Subscribe to SENSOR telemetry and refresh entity disable state on changes.

    Watches NeoPool.Modules, NeoPool.Hydrolysis.Unit, and NeoPool.Relay across
    incoming telemetry. When any of these signals changes vs the last seen
    value, refreshes runtime_data and runs `_refresh_entity_disable_state` —
    which idempotently flips registry flags and schedules a config-entry
    reload if any entity transitioned from INTEGRATION-disabled to enabled
    (necessary because re-enabled entities don't materialize until reload).

    The subscription persists for the lifetime of the config entry;
    `entry.async_on_unload(unsub)` ensures it's torn down on unload.
    """
    mqtt_topic = entry.runtime_data.mqtt_topic
    sensor_topic = f"tele/{mqtt_topic}/SENSOR"

    relay_names = {"Acid", "Base", "Redox", "Chlorine", "Conductivity", "Heating", "UV", "Valve"}
    rate_signal = connection_rate_signal(entry)

    @callback
    def on_sensor(msg: mqtt.ReceiveMessage) -> None:
        try:
            payload = json.loads(
                msg.payload.decode("utf-8")
                if isinstance(msg.payload, (bytes, bytearray))
                else msg.payload
            )
        except json.JSONDecodeError, UnicodeDecodeError:
            return

        # Feed the connection rate tracker on every message regardless of
        # whether other signals changed — the rate is meant to be current.
        tracker = entry.runtime_data.connection_rate_tracker
        if tracker is not None:
            requests = get_nested_value(payload, "NeoPool.Connection.MBRequests")
            no_response = get_nested_value(payload, "NeoPool.Connection.MBNoResponse")
            out_of_range = get_nested_value(payload, "NeoPool.Connection.DataOutOfRange")
            if requests is not None and no_response is not None:
                try:
                    tracker.update(
                        timestamp=dt_util.utcnow().timestamp(),
                        requests=int(requests),
                        errors=int(no_response) + int(out_of_range or 0),
                    )
                    async_dispatcher_send(hass, rate_signal)
                except (TypeError, ValueError) as err:
                    _LOGGER.debug("Failed to update connection rate tracker: %s", err)

        # Auto time-sync: when the HA-side switch is on, resync the controller
        # clock to Home Assistant if it has drifted beyond the threshold. Runs
        # before the change short-circuit so it acts on every message. The
        # cooldown prevents repeated resyncs before the corrected time echoes
        # back in a later SENSOR message.
        if entry.runtime_data.auto_time_sync:
            controller_time = get_nested_value(payload, JSON_PATH_TIME)
            parsed = (
                dt_util.parse_datetime(controller_time)
                if isinstance(controller_time, str)
                else None
            )
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
                now = dt_util.now()
                drift = abs((parsed - now).total_seconds())
                last = entry.runtime_data.last_time_sync_ts
                now_ts = now.timestamp()
                if drift > TIME_SYNC_DRIFT_THRESHOLD_SECONDS and (
                    last is None or now_ts - last >= TIME_SYNC_COOLDOWN_SECONDS
                ):
                    entry.runtime_data.last_time_sync_ts = now_ts
                    _LOGGER.info(
                        "Controller clock drifted %.0f s; auto-syncing via NPTime",
                        drift,
                    )
                    hass.async_create_task(
                        mqtt.async_publish(
                            hass,
                            f"cmnd/{mqtt_topic}/{CMD_TIME}",
                            "0",
                            qos=1,
                            retain=False,
                        )
                    )

        modules_data = get_nested_value(payload, "NeoPool.Modules")
        new_modules: set[str] = (
            {k for k, v in modules_data.items() if v == 1}
            if isinstance(modules_data, dict)
            else entry.runtime_data.available_modules
        )

        relay_data = get_nested_value(payload, "NeoPool.Relay")
        new_relays: set[str] = (
            {k for k in relay_data if k in relay_names}
            if isinstance(relay_data, dict)
            else entry.runtime_data.available_relays
        )

        unit = get_nested_value(payload, "NeoPool.Hydrolysis.Unit")
        new_unit: str | None = unit if isinstance(unit, str) else entry.runtime_data.hydrolysis_unit

        if (
            new_modules == entry.runtime_data.available_modules
            and new_relays == entry.runtime_data.available_relays
            and new_unit == entry.runtime_data.hydrolysis_unit
        ):
            return  # Nothing relevant changed — skip the refresh

        _LOGGER.debug(
            "Detected change in module/relay/unit signals — modules=%s relays=%s unit=%s",
            new_modules,
            new_relays,
            new_unit,
        )
        entry.runtime_data.available_modules = new_modules
        entry.runtime_data.available_relays = new_relays
        entry.runtime_data.hydrolysis_unit = new_unit
        _refresh_entity_disable_state(hass, entry)

    unsub = await mqtt.async_subscribe(hass, sensor_topic, on_sensor, qos=1)
    entry.async_on_unload(unsub)
    _LOGGER.debug("Dynamic disable watch subscribed to %s", sensor_topic)


def _parse_register_int(value: Any) -> int | None:
    """Parse an int from an NPRead RESULT field (int, hex string, or decimal str).

    Used for both the Address and the Data value: per the Tasmota docs an
    NPRead address comes back as a decimal int (e.g. 1046 == 0x0416) while
    other commands may use hex strings (e.g. "0x040F"); Data for a single
    register is a scalar that can likewise be an int or a hex string.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.lower().startswith("0x") else int(value)
        except ValueError:
            return None
    return None


async def _setup_result_watch(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Subscribe to the command result topic(s) and cache config registers.

    Tasmota answers every command with a JSON object keyed by the command name.
    With the default ``SetOption4 0`` it goes to ``stat/{topic}/RESULT``; with
    ``SetOption4 1`` it goes to ``stat/{topic}/<command>`` (e.g.
    ``stat/{topic}/NPRead``). We therefore subscribe to the single-level
    wildcard ``stat/{topic}/+`` so NPRead replies are captured regardless of the
    SetOption4 setting; non-NPRead messages are ignored by the JSON-key check.
    (Reading SetOption4 to pick a single topic doesn't help: its own reply is
    SO4-routed too, so it has the same multi-topic bootstrap. stat traffic is
    low-volume command responses, not telemetry, so the wildcard is cheap.)

    We store the value in runtime_data.register_state, fanning out via
    config_register_signal so the register-backed entities update. This is
    on-demand request/response, not polling: reads are only issued at startup
    (and writes echo their state).

    Data shapes handled: a single-register NPRead returns a scalar Data
    (``{"NPRead":{"Address":1046,"Data":28}}``); a multi-register read (NPReadL)
    returns a Data list. Address and Data may be decimal ints or hex strings
    (``"0x0002"``) depending on the device's ``NPResult`` setting — both are
    parsed by ``_parse_register_int``.
    """
    mqtt_topic = entry.runtime_data.mqtt_topic
    result_topic = f"stat/{mqtt_topic}/+"
    signal = config_register_signal(entry)

    @callback
    def on_result(msg: mqtt.ReceiveMessage) -> None:
        try:
            payload = json.loads(
                msg.payload.decode("utf-8")
                if isinstance(msg.payload, (bytes, bytearray))
                else msg.payload
            )
        except json.JSONDecodeError, UnicodeDecodeError:
            return
        if not isinstance(payload, dict):
            return

        npread = payload.get("NPRead")
        if not isinstance(npread, dict):
            return
        address = _parse_register_int(npread.get("Address"))
        data = npread.get("Data")
        if isinstance(data, list):
            data = data[0] if data else None
        value = _parse_register_int(data)
        if address is None or value is None:
            return
        entry.runtime_data.register_state[address] = value
        async_dispatcher_send(hass, signal)

    unsub = await mqtt.async_subscribe(hass, result_topic, on_result, qos=1)
    entry.async_on_unload(unsub)
    _LOGGER.debug("Result watch subscribed to %s", result_topic)


async def _read_config_registers(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Issue a one-time NPRead for each Group 2 config register.

    Responses arrive asynchronously on stat/RESULT and populate
    runtime_data.register_state via _setup_result_watch. Reads are sent
    individually for robust response parsing.
    """
    mqtt_topic = entry.runtime_data.mqtt_topic
    for address in CONFIG_REGISTERS:
        await mqtt.async_publish(
            hass,
            f"cmnd/{mqtt_topic}/{CMD_NPREAD}",
            f"0x{address:04X}",
            qos=1,
            retain=False,
        )
    _LOGGER.debug("Requested %d config registers via NPRead", len(CONFIG_REGISTERS))


async def async_register_device(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Register the NeoPool device in the device registry.

    Initial registration uses default manufacturer. Device metadata (actual manufacturer
    from NeoPool.Type and firmware from NeoPool.Powerunit.Version) is fetched separately
    via async_fetch_device_metadata() and updates the registry dynamically.
    """
    device_registry = dr.async_get(hass)

    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    nodeid = entry.data.get(CONF_NODEID, "")

    # Use hashed NodeID as serial_number for privacy
    serial_number = entry.data.get(CONF_NODEID_HASHED)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, nodeid)},
        manufacturer=MANUFACTURER,
        name=device_name,
        model=MODEL,
        serial_number=serial_number,
        configuration_url="https://tasmota.github.io/docs/NeoPool/",
    )

    # Store device_id in runtime_data for device triggers
    device = device_registry.async_get_device(identifiers={(DOMAIN, nodeid)})
    if device:
        entry.runtime_data.device_id = device.id
        _LOGGER.debug(
            "Device ID stored in runtime_data: %s",
            device.id,
        )

    _LOGGER.debug("Registered device: %s (NodeID: %s)", device_name, nodeid)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: NeoPoolConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device.

    Return False to prevent device removal - user should remove integration instead.
    """
    return True


def get_device_info(entry: NeoPoolConfigEntry) -> dr.DeviceInfo:
    """Get device info for NeoPool entities.

    Uses dynamic manufacturer and firmware version from runtime_data if available,
    otherwise falls back to defaults.
    """
    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    nodeid = entry.data.get(CONF_NODEID, "")

    # Use dynamic metadata from runtime_data if available
    manufacturer = MANUFACTURER
    sw_version: str | None = None

    if hasattr(entry, "runtime_data") and entry.runtime_data:
        if entry.runtime_data.manufacturer:
            manufacturer = entry.runtime_data.manufacturer
        # Build sw_version: "Tasmota X.Y.Z / Powerunit VX.Y"
        sw_parts = []
        if entry.runtime_data.tasmota_version:
            sw_parts.append(f"Tasmota {entry.runtime_data.tasmota_version}")
        if entry.runtime_data.fw_version:
            sw_parts.append(f"Powerunit {entry.runtime_data.fw_version}")
        if sw_parts:
            sw_version = " / ".join(sw_parts)

    # Use device IP for configuration URL if available, otherwise Tasmota docs
    config_url = "https://tasmota.github.io/docs/NeoPool/"
    if hasattr(entry, "runtime_data") and entry.runtime_data:
        if entry.runtime_data.device_ip:
            config_url = f"http://{entry.runtime_data.device_ip}"

    return dr.DeviceInfo(
        identifiers={(DOMAIN, nodeid)},
        manufacturer=manufacturer,
        name=device_name,
        model=MODEL,
        sw_version=sw_version,
        configuration_url=config_url,
    )


async def async_migrate_masked_unique_ids(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
) -> bool:
    """Migrate entities with masked unique_ids to use the real NodeID.

    This sanity check runs on every startup to detect and fix entities that were
    created with masked NodeIDs (when Tasmota SetOption157 was disabled).

    The migration process:
    1. Find entities belonging to this config entry with masked unique_ids
    2. Check SetOption157 status - enable it if disabled
    3. Wait for real NodeID from telemetry
    4. Update entity unique_ids with real NodeID
    5. Update config entry data with real NodeID

    Args:
        hass: Home Assistant instance
        entry: Config entry to check/migrate

    Returns:
        True if migration was successful or not needed, False if migration failed.
    """
    entity_registry = er.async_get(hass)
    mqtt_topic = entry.data.get(CONF_DISCOVERY_PREFIX, "")
    current_nodeid = entry.data.get(CONF_NODEID, "")

    _LOGGER.debug(
        "Starting masked unique_id sanity check for entry %s (topic: %s, nodeid: %s)",
        entry.entry_id,
        mqtt_topic,
        current_nodeid,
    )

    # Step 1: Find entities with masked unique_ids for this config entry
    all_entry_entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    ]
    _LOGGER.debug(
        "Found %d total entities for config entry %s",
        len(all_entry_entities),
        entry.entry_id,
    )

    masked_entities = [
        entity
        for entity in all_entry_entities
        if entity.unique_id and is_masked_unique_id(entity.unique_id)
    ]

    if masked_entities:
        _LOGGER.debug(
            "Found %d entities with masked unique_ids:",
            len(masked_entities),
        )
        for entity in masked_entities[:5]:  # Log first 5
            _LOGGER.debug("  - %s (unique_id: %s)", entity.entity_id, entity.unique_id)
        if len(masked_entities) > 5:
            _LOGGER.debug("  ... and %d more", len(masked_entities) - 5)

    if not masked_entities:
        # Also check if stored nodeid is masked
        nodeid_is_masked = is_masked_unique_id(current_nodeid)
        _LOGGER.debug(
            "No masked entity unique_ids found. Config entry NodeID masked: %s (%s)",
            nodeid_is_masked,
            current_nodeid,
        )
        if not nodeid_is_masked:
            _LOGGER.debug("No masked unique_ids found, migration not needed")
            return True
        _LOGGER.info(
            "Config entry NodeID is masked (%s), will attempt to get real NodeID",
            current_nodeid,
        )

    _LOGGER.warning(
        "Found %d entities with masked unique_ids, starting migration",
        len(masked_entities),
    )

    # Step 2: Get the canonical NodeID from config entry
    # With dual recognition, the config entry should already have the real NodeID
    # from setup. If we're migrating from an older version, try to get it from
    # the stored nodeid_real value first.
    stored_real = entry.data.get(CONF_NODEID_REAL)
    if stored_real:
        _LOGGER.info("Using stored real NodeID for migration: %s", stored_real)
        raw_nodeid = stored_real
    else:
        # Fallback: wait for NodeID from telemetry (legacy migration path)
        _LOGGER.debug("Waiting for NodeID from telemetry on %s", mqtt_topic)
        raw_nodeid = await _wait_for_real_nodeid(hass, mqtt_topic)
        _LOGGER.debug("Raw NodeID from telemetry: %s", raw_nodeid)

    if not raw_nodeid:
        _LOGGER.error("Could not get NodeID for migration, migration aborted")
        return True

    # Normalize NodeID (remove spaces, uppercase) for clean unique_ids
    real_nodeid = normalize_nodeid(raw_nodeid)
    _LOGGER.debug(
        "NodeID normalization: '%s' -> '%s'",
        raw_nodeid,
        real_nodeid,
    )
    _LOGGER.info("Got real NodeID: %s", real_nodeid)

    # Step 4: Update entity unique_ids
    _LOGGER.debug("Starting entity unique_id migration for %d entities", len(masked_entities))
    migrated_count = 0
    for entity in masked_entities:
        entity_key = extract_entity_key_from_masked_unique_id(entity.unique_id)
        _LOGGER.debug(
            "Extracting entity_key from '%s' -> '%s'",
            entity.unique_id,
            entity_key,
        )
        if not entity_key:
            _LOGGER.warning(
                "Could not extract entity_key from unique_id: %s",
                entity.unique_id,
            )
            continue

        new_unique_id = f"neopool_mqtt_{real_nodeid}_{entity_key}"
        _LOGGER.debug(
            "Entity %s: old unique_id='%s' -> new unique_id='%s'",
            entity.entity_id,
            entity.unique_id,
            new_unique_id,
        )

        # Check if new unique_id already exists
        existing = entity_registry.async_get_entity_id(entity.domain, DOMAIN, new_unique_id)
        if existing and existing != entity.entity_id:
            _LOGGER.warning(
                "Cannot migrate %s: new unique_id %s already exists for %s",
                entity.entity_id,
                new_unique_id,
                existing,
            )
            continue

        try:
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=new_unique_id,
            )
            migrated_count += 1
            _LOGGER.info(
                "Migrated entity %s: %s -> %s",
                entity.entity_id,
                entity.unique_id,
                new_unique_id,
            )
        except ValueError as err:
            _LOGGER.error(
                "Failed to migrate entity %s: %s",
                entity.entity_id,
                err,
            )

    # Step 5: Update config entry data with real NodeID
    if current_nodeid != real_nodeid:
        new_data = {**entry.data, CONF_NODEID: real_nodeid}
        hass.config_entries.async_update_entry(entry, data=new_data)
        # Also update runtime_data
        entry.runtime_data.nodeid = real_nodeid
        _LOGGER.info(
            "Updated config entry NodeID: %s -> %s",
            current_nodeid,
            real_nodeid,
        )

    # Step 6: Update device registry identifier
    device_registry = dr.async_get(hass)
    old_device = device_registry.async_get_device(identifiers={(DOMAIN, current_nodeid)})
    if old_device and current_nodeid != real_nodeid:
        # Update device identifiers to use real NodeID
        device_registry.async_update_device(
            old_device.id,
            new_identifiers={(DOMAIN, real_nodeid)},
        )
        _LOGGER.info(
            "Updated device identifier: %s -> %s",
            current_nodeid,
            real_nodeid,
        )

    _LOGGER.info(
        "Migration complete: %d/%d entities migrated to use NodeID %s",
        migrated_count,
        len(masked_entities),
        real_nodeid,
    )
    return True


async def _send_and_wait(
    hass: HomeAssistant,
    topic: str,
    payload: str,
    event: asyncio.Event,
    label: str,
    deadline: float,
) -> None:
    """Publish an MQTT command and wait for the response event."""
    remaining = deadline - hass.loop.time()
    if remaining <= 0:
        return
    await mqtt.async_publish(hass, topic, payload, qos=1, retain=False)
    _LOGGER.debug("Sent %s to %s", label, topic)
    try:
        await asyncio.wait_for(event.wait(), timeout=remaining)
    except TimeoutError:
        _LOGGER.debug("Timeout waiting for %s", label)


async def async_fetch_device_metadata(  # noqa: C901
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    wait_timeout: float = 10.0,
) -> None:
    """Fetch device metadata from MQTT.

    Fetches from three sources:
    - SENSOR topic: manufacturer (NeoPool.Type), powerunit firmware (Powerunit.Version)
    - Status 2: Tasmota firmware version (StatusFWR.Version)
    - Status 5: Device IP address (StatusNET.IPAddress)

    Args:
        hass: Home Assistant instance
        entry: Config entry with runtime_data
        wait_timeout: Maximum time to wait for responses (seconds)
    """
    mqtt_topic = entry.runtime_data.mqtt_topic
    manufacturer: str | None = None
    fw_version: str | None = None
    tasmota_version: str | None = None
    device_ip: str | None = None
    available_relays: set[str] = set()
    available_modules: set[str] = set()
    hydrolysis_unit: str | None = None
    sensor_event = asyncio.Event()
    status2_event = asyncio.Event()
    status5_event = asyncio.Event()

    @callback
    def sensor_received(msg: mqtt.ReceiveMessage) -> None:
        """Handle SENSOR telemetry for manufacturer, version, relay, module, and unit detection."""
        nonlocal manufacturer, fw_version, available_relays, available_modules, hydrolysis_unit
        try:
            payload = json.loads(
                msg.payload.decode("utf-8")
                if isinstance(msg.payload, (bytes, bytearray))
                else msg.payload
            )
            device_type = get_nested_value(payload, JSON_PATH_TYPE)
            if device_type:
                manufacturer = str(device_type)
                _LOGGER.debug("Extracted manufacturer: %s", manufacturer)
            version = get_nested_value(payload, JSON_PATH_POWERUNIT_VERSION)
            if version:
                fw_version = str(version)
                _LOGGER.debug("Extracted powerunit version: %s", fw_version)
            # Detect which named relays are present in the payload
            relay_data = get_nested_value(payload, "NeoPool.Relay")
            if isinstance(relay_data, dict):
                relay_names = {
                    "Acid",
                    "Base",
                    "Redox",
                    "Chlorine",
                    "Conductivity",
                    "Heating",
                    "UV",
                    "Valve",
                }
                available_relays = {k for k in relay_data if k in relay_names}
                _LOGGER.debug("Detected available relays: %s", available_relays)
            # Detect which modules are installed (value == 1)
            modules_data = get_nested_value(payload, "NeoPool.Modules")
            if isinstance(modules_data, dict):
                available_modules = {k for k, v in modules_data.items() if v == 1}
                _LOGGER.debug("Detected available modules: %s", available_modules)
            # Capture hydrolysis display unit ("%" or "g/h")
            unit = get_nested_value(payload, "NeoPool.Hydrolysis.Unit")
            if isinstance(unit, str):
                hydrolysis_unit = unit
                _LOGGER.debug("Detected hydrolysis unit: %s", hydrolysis_unit)
            if manufacturer or fw_version:
                sensor_event.set()
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse SENSOR for metadata: %s", err)

    @callback
    def status2_received(msg: mqtt.ReceiveMessage) -> None:
        """Handle Status 2 (firmware) response."""
        nonlocal tasmota_version
        try:
            payload = json.loads(
                msg.payload.decode("utf-8")
                if isinstance(msg.payload, (bytes, bytearray))
                else msg.payload
            )
            status_fwr = payload.get("StatusFWR", {})
            if status_fwr:
                ver = status_fwr.get("Version", "")
                if ver:
                    tasmota_version = ver.split("(")[0].strip()
                    _LOGGER.debug("Extracted Tasmota version: %s", tasmota_version)
                    status2_event.set()
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse Status 2 response: %s", err)

    @callback
    def status5_received(msg: mqtt.ReceiveMessage) -> None:
        """Handle Status 5 (network) response."""
        nonlocal device_ip
        _LOGGER.debug("Received Status 5 response on %s", msg.topic)
        try:
            payload = json.loads(
                msg.payload.decode("utf-8")
                if isinstance(msg.payload, (bytes, bytearray))
                else msg.payload
            )
            status_net = payload.get("StatusNET", {})
            if status_net:
                ip = status_net.get("IPAddress", "")
                if ip:
                    device_ip = str(ip)
                    _LOGGER.debug("Extracted device IP: %s", device_ip)
                    status5_event.set()
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse Status 5 response: %s", err)

    # Subscribe to SENSOR and specific Status response topics
    unsub_sensor = await mqtt.async_subscribe(
        hass, f"tele/{mqtt_topic}/SENSOR", sensor_received, qos=1
    )
    unsub_status2 = await mqtt.async_subscribe(
        hass, f"stat/{mqtt_topic}/STATUS2", status2_received, qos=1
    )
    unsub_status5 = await mqtt.async_subscribe(
        hass, f"stat/{mqtt_topic}/STATUS5", status5_received, qos=1
    )

    try:
        # Send Status commands one at a time, waiting for each response
        # before sending the next. Backlog doesn't work reliably because
        # regular SENSOR telemetry interrupts Tasmota's command queue.
        cmnd_topic = f"cmnd/{mqtt_topic}/Status"
        deadline = hass.loop.time() + wait_timeout

        await _send_and_wait(hass, cmnd_topic, "2", status2_event, "Status 2", deadline)
        await _send_and_wait(hass, cmnd_topic, "5", status5_event, "Status 5", deadline)

        # SENSOR data arrives naturally from the regular telemetry cycle
        remaining = deadline - hass.loop.time()
        if remaining > 0 and not sensor_event.is_set():
            try:
                await asyncio.wait_for(sensor_event.wait(), timeout=remaining)
            except TimeoutError:
                _LOGGER.debug("Timeout waiting for SENSOR from %s", mqtt_topic)
        _LOGGER.debug(
            "Device metadata fetch complete for %s (manufacturer=%s, fw=%s, tasmota=%s, ip=%s)",
            mqtt_topic,
            manufacturer,
            fw_version,
            tasmota_version,
            device_ip,
        )
    finally:
        unsub_sensor()
        unsub_status2()
        unsub_status5()

    # Update runtime_data
    if manufacturer:
        entry.runtime_data.manufacturer = manufacturer
    if fw_version:
        entry.runtime_data.fw_version = fw_version
    if tasmota_version:
        entry.runtime_data.tasmota_version = tasmota_version
    if device_ip:
        entry.runtime_data.device_ip = device_ip

    # Store available relays
    if available_relays:
        entry.runtime_data.available_relays = available_relays

    # Store available modules (used to auto-disable entities for absent modules)
    if available_modules:
        entry.runtime_data.available_modules = available_modules

    # Store hydrolysis unit (used to auto-disable g/h-labeled entities in % mode)
    if hydrolysis_unit:
        entry.runtime_data.hydrolysis_unit = hydrolysis_unit

    # Update device registry if we got any metadata
    if manufacturer or fw_version or tasmota_version or device_ip:
        await _update_device_registry_metadata(hass, entry)
        _LOGGER.info(
            "Device metadata updated - Manufacturer: %s, Powerunit: %s, Tasmota: %s, IP: %s",
            manufacturer or "unknown",
            fw_version or "unknown",
            tasmota_version or "unknown",
            device_ip or "unknown",
        )


async def _update_device_registry_metadata(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
) -> None:
    """Update device registry with metadata from runtime_data.

    Args:
        hass: Home Assistant instance
        entry: Config entry with runtime_data containing metadata
    """
    device_registry = dr.async_get(hass)
    nodeid = entry.runtime_data.nodeid

    device = device_registry.async_get_device(identifiers={(DOMAIN, nodeid)})
    if not device:
        _LOGGER.debug("Device not found in registry for NodeID: %s", nodeid)
        return

    # Build sw_version: "Tasmota X.Y.Z / Powerunit VX.Y"
    sw_parts = []
    if entry.runtime_data.tasmota_version:
        sw_parts.append(f"Tasmota {entry.runtime_data.tasmota_version}")
    if entry.runtime_data.fw_version:
        sw_parts.append(f"Powerunit {entry.runtime_data.fw_version}")
    sw_version = " / ".join(sw_parts) if sw_parts else None

    # Build configuration_url from device IP
    config_url = (
        f"http://{entry.runtime_data.device_ip}"
        if entry.runtime_data.device_ip
        else "https://tasmota.github.io/docs/NeoPool/"
    )

    # Update device with new metadata
    device_registry.async_update_device(
        device.id,
        manufacturer=entry.runtime_data.manufacturer or MANUFACTURER,
        sw_version=sw_version,
        configuration_url=config_url,
    )
    _LOGGER.debug(
        "Updated device registry - manufacturer: %s, sw_version: %s",
        entry.runtime_data.manufacturer or MANUFACTURER,
        sw_version,
    )


async def _auto_acquire_dual_nodeids(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
) -> None:
    """Auto-acquire dual NodeIDs on startup for existing installations.

    Called when config entry is missing nodeid_hashed (upgrade from older version).
    Reads the current NodeID from SENSOR, classifies it, toggles SO157 once
    to get the other format, restores SO157, and updates config entry.
    """
    mqtt_topic = entry.data.get(CONF_DISCOVERY_PREFIX, "")
    if not mqtt_topic:
        _LOGGER.warning("No MQTT topic, cannot acquire dual NodeIDs")
        return

    # Step 1: Read current NodeID from telemetry
    _LOGGER.debug("Step 1: Reading current NodeID from SENSOR on %s", mqtt_topic)
    await mqtt.async_publish(hass, f"cmnd/{mqtt_topic}/TelePeriod", "", qos=1, retain=False)
    first_nodeid = await _wait_for_any_nodeid(hass, mqtt_topic)

    if not first_nodeid:
        _LOGGER.warning("Could not read NodeID from device, dual acquisition skipped")
        return

    first_type = classify_nodeid(first_nodeid)
    _LOGGER.info("Current NodeID: %s (type: %s)", first_nodeid, first_type)

    if first_type == "invalid":
        _LOGGER.warning("Invalid NodeID received: %s, dual acquisition skipped", first_nodeid)
        return

    # Step 2: Toggle SO157 to get the other format
    toggle_to = first_type in ("hashed", "masked")
    _LOGGER.debug(
        "Step 2: Toggling SetOption157 to %s to acquire second NodeID",
        "1" if toggle_to else "0",
    )
    await async_set_setoption157(hass, mqtt_topic, enable=toggle_to)
    await asyncio.sleep(1)
    await mqtt.async_publish(hass, f"cmnd/{mqtt_topic}/TelePeriod", "", qos=1, retain=False)
    second_nodeid = await _wait_for_any_nodeid(hass, mqtt_topic)

    # Step 3: Restore SO157
    _LOGGER.debug("Step 3: Restoring SetOption157 to %s", "0" if toggle_to else "1")
    await async_set_setoption157(hass, mqtt_topic, enable=not toggle_to)

    second_type = classify_nodeid(second_nodeid) if second_nodeid else "invalid"
    _LOGGER.debug("Second NodeID: %s (type: %s)", second_nodeid, second_type)

    # Step 4: Classify and store
    nodeid_hashed = None
    nodeid_real = None
    nodeid_masked = None

    for nodeid, ntype in [(first_nodeid, first_type), (second_nodeid, second_type)]:
        if ntype == "hashed":
            nodeid_hashed = normalize_nodeid(nodeid)
        elif ntype == "real":
            nodeid_real = normalize_nodeid(nodeid)
        elif ntype == "masked":
            nodeid_masked = normalize_nodeid(nodeid)

    if not nodeid_real:
        _LOGGER.warning("Could not acquire real NodeID, dual acquisition incomplete")
        return

    # Canonical: prefer hashed, fall back to real
    canonical = nodeid_hashed or nodeid_real

    _LOGGER.info(
        "Dual NodeID acquisition complete. Canonical: %s, Real: %s, Hashed: %s, Masked: %s",
        canonical,
        nodeid_real,
        nodeid_hashed or "N/A",
        nodeid_masked or "N/A",
    )

    # Step 5: Update config entry with dual NodeIDs
    new_data = {
        **entry.data,
        CONF_NODEID: canonical,
        CONF_NODEID_HASHED: nodeid_hashed,
        CONF_NODEID_REAL: nodeid_real,
        CONF_NODEID_MASKED: nodeid_masked,
    }
    hass.config_entries.async_update_entry(entry, data=new_data)

    # Update runtime data
    entry.runtime_data.nodeid = canonical
    _LOGGER.info("Config entry updated with dual NodeIDs")
    # Note: device and entity migration is handled by _migrate_to_canonical_nodeid()
    # which runs separately in async_setup_entry()


async def _wait_for_any_nodeid(
    hass: HomeAssistant,
    mqtt_topic: str,
    wait_timeout: float = 10.0,
) -> str | None:
    """Wait for any NodeID from telemetry (accepts all formats)."""
    received_nodeid: str | None = None
    event = asyncio.Event()

    @callback
    def message_received(msg: mqtt.ReceiveMessage) -> None:
        nonlocal received_nodeid
        try:
            if isinstance(msg.payload, (bytes, bytearray)):
                payload_str = msg.payload.decode("utf-8")
            else:
                payload_str = msg.payload
            payload = json.loads(payload_str)
            nodeid = get_nested_value(payload, "NeoPool.Powerunit.NodeID")
            if nodeid and str(nodeid).strip():
                received_nodeid = str(nodeid)
                event.set()
        except json.JSONDecodeError, UnicodeDecodeError:
            pass

    sensor_topic = f"tele/{mqtt_topic}/SENSOR"
    unsubscribe = await mqtt.async_subscribe(hass, sensor_topic, message_received, qos=1)

    try:
        await asyncio.wait_for(event.wait(), timeout=wait_timeout)
    except TimeoutError:
        _LOGGER.debug("Timeout waiting for NodeID from %s", mqtt_topic)
    finally:
        unsubscribe()

    return received_nodeid


async def _wait_for_real_nodeid(
    hass: HomeAssistant,
    mqtt_topic: str,
    wait_timeout: float = 10.0,
) -> str | None:
    """Wait for real NodeID from telemetry message.

    Triggers TelePeriod command to get immediate telemetry response,
    then extracts and validates the NodeID.

    Args:
        hass: Home Assistant instance
        mqtt_topic: MQTT topic prefix for the device
        wait_timeout: Maximum time to wait for telemetry (seconds)

    Returns:
        Real NodeID string if found and valid, None otherwise.
    """
    real_nodeid: str | None = None
    event = asyncio.Event()

    @callback
    def message_received(msg: mqtt.ReceiveMessage) -> None:
        """Handle telemetry message and extract NodeID."""
        nonlocal real_nodeid
        try:
            if isinstance(msg.payload, (bytes, bytearray)):
                payload_str = msg.payload.decode("utf-8")
            else:
                payload_str = msg.payload

            payload = json.loads(payload_str)
            nodeid = get_nested_value(payload, "NeoPool.Powerunit.NodeID")

            if nodeid and validate_nodeid(str(nodeid)):
                real_nodeid = str(nodeid)
                _LOGGER.debug("Received real NodeID from telemetry: %s", real_nodeid)
                event.set()
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse telemetry payload: %s", err)

    # Subscribe to sensor topic
    sensor_topic = f"tele/{mqtt_topic}/SENSOR"
    unsubscribe = await mqtt.async_subscribe(hass, sensor_topic, message_received, qos=1)

    try:
        # Trigger immediate telemetry by sending TelePeriod command
        await mqtt.async_publish(
            hass,
            f"cmnd/{mqtt_topic}/TelePeriod",
            "",  # Empty payload queries current period and triggers immediate telemetry
            qos=1,
            retain=False,
        )

        # Wait for telemetry with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=wait_timeout)
        except TimeoutError:
            _LOGGER.warning(
                "Timeout waiting for telemetry from %s after %.1f seconds",
                mqtt_topic,
                wait_timeout,
            )
    finally:
        unsubscribe()

    return real_nodeid
