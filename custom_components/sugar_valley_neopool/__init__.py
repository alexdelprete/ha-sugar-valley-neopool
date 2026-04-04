"""The NeoPool MQTT integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
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
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_RECOVERY_SCRIPT,
    DOMAIN,
    JSON_PATH_POWERUNIT_VERSION,
    JSON_PATH_TYPE,
    MANUFACTURER,
    MODEL,
    PLATFORMS,
    YAML_ENTITIES_TO_DELETE,
    YAML_TO_INTEGRATION_KEY_MAP,
)
from .helpers import (
    async_set_setoption157,
    classify_nodeid,
    extract_entity_key_from_masked_unique_id,
    get_nested_value,
    is_masked_unique_id,
    normalize_nodeid,
    validate_nodeid,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Config entry version for migrations
CONFIG_ENTRY_VERSION = 2


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
    )

    # Register device in device registry and store device_id for triggers
    await async_register_device(hass, entry)

    # Fetch device metadata (manufacturer, firmware version) from MQTT
    # This updates the device registry with actual device info
    await async_fetch_device_metadata(hass, entry)

    # Auto-acquire dual NodeIDs if not yet stored (upgrade from older version)
    if not entry.data.get(CONF_NODEID_HASHED):
        _LOGGER.info(
            "Dual NodeID not yet acquired — triggering auto-acquisition for %s",
            mqtt_topic,
        )
        await _auto_acquire_dual_nodeids(hass, entry)

    # Run sanity check for masked unique_ids and migrate if needed
    # This must happen before platform setup to fix NodeID before entities are created
    migration_success = await async_migrate_masked_unique_ids(hass, entry)
    if not migration_success:
        _LOGGER.warning(
            "Masked unique_id migration failed - entities may have incorrect unique_ids. "
            "Check that SetOption157 is enabled on the Tasmota device."
        )
        # Don't fail setup - let integration continue with potentially masked IDs
        # User can fix via Options flow

    # Clean up removed entities (runs for all users, not just YAML migration)
    _cleanup_removed_entities(hass, entry)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Platform setup complete for %d platforms", len(PLATFORMS))

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
        return False

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


async def async_register_device(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Register the NeoPool device in the device registry.

    Initial registration uses default manufacturer. Device metadata (actual manufacturer
    from NeoPool.Type and firmware from NeoPool.Powerunit.Version) is fetched separately
    via async_fetch_device_metadata() and updates the registry dynamically.
    """
    device_registry = dr.async_get(hass)

    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    nodeid = entry.data.get(CONF_NODEID, "")

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, nodeid)},
        manufacturer=MANUFACTURER,
        name=device_name,
        model=MODEL,
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
    return False


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
        if entry.runtime_data.fw_version:
            sw_version = f"{entry.runtime_data.fw_version} (Powerunit)"

    return dr.DeviceInfo(
        identifiers={(DOMAIN, nodeid)},
        manufacturer=manufacturer,
        name=device_name,
        model=MODEL,
        sw_version=sw_version,
        configuration_url="https://tasmota.github.io/docs/NeoPool/",
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
        return False

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


async def async_fetch_device_metadata(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    wait_timeout: float = 10.0,
) -> None:
    """Fetch device metadata (manufacturer, firmware version) from MQTT telemetry.

    Triggers TelePeriod command to get immediate telemetry response,
    then extracts Type (manufacturer) and Powerunit.Version (firmware).
    Updates runtime_data and device registry with the fetched values.

    Args:
        hass: Home Assistant instance
        entry: Config entry with runtime_data
        wait_timeout: Maximum time to wait for telemetry (seconds)
    """
    mqtt_topic = entry.runtime_data.mqtt_topic
    manufacturer: str | None = None
    fw_version: str | None = None
    event = asyncio.Event()

    @callback
    def message_received(msg: mqtt.ReceiveMessage) -> None:
        """Handle telemetry message and extract device metadata."""
        nonlocal manufacturer, fw_version
        try:
            if isinstance(msg.payload, (bytes, bytearray)):
                payload_str = msg.payload.decode("utf-8")
            else:
                payload_str = msg.payload

            payload = json.loads(payload_str)

            # Extract manufacturer from NeoPool.Type
            device_type = get_nested_value(payload, JSON_PATH_TYPE)
            if device_type:
                manufacturer = str(device_type)
                _LOGGER.debug("Extracted manufacturer from telemetry: %s", manufacturer)

            # Extract firmware version from NeoPool.Powerunit.Version
            version = get_nested_value(payload, JSON_PATH_POWERUNIT_VERSION)
            if version:
                fw_version = str(version)
                _LOGGER.debug("Extracted firmware version from telemetry: %s", fw_version)

            # Signal completion if we got at least one value
            if manufacturer or fw_version:
                event.set()

        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse telemetry payload for metadata: %s", err)

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
            _LOGGER.debug(
                "Timeout waiting for device metadata from %s after %.1f seconds",
                mqtt_topic,
                wait_timeout,
            )
    finally:
        unsubscribe()

    # Update runtime_data with fetched metadata
    if manufacturer:
        entry.runtime_data.manufacturer = manufacturer
    if fw_version:
        entry.runtime_data.fw_version = fw_version

    # Update device registry if we got any metadata
    if manufacturer or fw_version:
        await _update_device_registry_metadata(hass, entry)
        _LOGGER.info(
            "Device metadata updated - Manufacturer: %s, Firmware: %s",
            manufacturer or "unknown",
            fw_version or "unknown",
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

    # Build sw_version string: "Vx.y.z (Powerunit)" if we have firmware version
    sw_version: str | None = None
    if entry.runtime_data.fw_version:
        sw_version = f"{entry.runtime_data.fw_version} (Powerunit)"

    # Update device with new metadata
    device_registry.async_update_device(
        device.id,
        manufacturer=entry.runtime_data.manufacturer or MANUFACTURER,
        sw_version=sw_version,
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
    old_nodeid = entry.data.get(CONF_NODEID, "")
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

    # Step 6: Migrate device registry identifier if canonical changed
    if old_nodeid and old_nodeid != canonical:
        device_registry = dr.async_get(hass)
        old_device = device_registry.async_get_device(identifiers={(DOMAIN, old_nodeid)})
        if old_device:
            device_registry.async_update_device(
                old_device.id,
                new_identifiers={(DOMAIN, canonical)},
            )
            _LOGGER.info(
                "Migrated device identifier: %s -> %s",
                old_nodeid,
                canonical,
            )

    # Step 7: Migrate entity unique_ids from old NodeID to canonical
    if old_nodeid and old_nodeid != canonical:
        entity_registry = er.async_get(hass)
        migrated = 0
        for entity in entity_registry.entities.values():
            if entity.config_entry_id != entry.entry_id:
                continue
            if not entity.unique_id or old_nodeid not in entity.unique_id:
                continue
            new_unique_id = entity.unique_id.replace(old_nodeid, canonical)
            existing = entity_registry.async_get_entity_id(entity.domain, DOMAIN, new_unique_id)
            if existing and existing != entity.entity_id:
                _LOGGER.warning(
                    "Cannot migrate %s: unique_id %s already exists",
                    entity.entity_id,
                    new_unique_id,
                )
                continue
            entity_registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
            migrated += 1
        if migrated:
            _LOGGER.info(
                "Migrated %d entity unique_ids: %s -> %s",
                migrated,
                old_nodeid,
                canonical,
            )


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
        except (json.JSONDecodeError, UnicodeDecodeError):
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
