"""The NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import mqtt, persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_ENABLE_REPAIR_NOTIFICATION,
    CONF_FAILURES_THRESHOLD,
    CONF_MIGRATE_YAML,
    CONF_NODEID,
    CONF_OFFLINE_TIMEOUT,
    CONF_RECOVERY_SCRIPT,
    CONF_UNIQUE_ID_PREFIX,
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_RECOVERY_SCRIPT,
    DEFAULT_UNIQUE_ID_PREFIX,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
    VERSION,
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

    # Initialize runtime data
    entry.runtime_data = NeoPoolData(
        device_name=device_name,
        mqtt_topic=mqtt_topic,
        nodeid=nodeid,
    )

    # Migrate YAML entities if this is first setup
    await async_migrate_yaml_entities(hass, entry, nodeid)

    # Register device in device registry and store device_id for triggers
    await async_register_device(hass, entry)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Verify migration if applicable
    if entry.runtime_data.entity_id_mapping:
        verification = await async_verify_migration(hass, entry.runtime_data.entity_id_mapping)
        _LOGGER.info(
            "Migration verification: %d verified, %d no history, %d failed",
            verification["verified"],
            verification["no_history"],
            len(verification["failed"]),
        )

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


async def async_migrate_yaml_entities(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    nodeid: str,
) -> dict[str, Any]:
    """Migrate YAML entities by deleting old MQTT entities.

    The integration creates new entities with matching entity_ids
    (from registry), preserving historical data.

    Key insight: We find entities by unique_id prefix, but get the actual
    entity_id from the registry (handles user customization).

    Returns a summary dict with migration results.
    """
    summary: dict[str, Any] = {
        "steps": [],
        "entities_found": 0,
        "entities_migrated": 0,
        "errors": [],
    }

    # Skip if not a YAML migration
    if not entry.data.get(CONF_MIGRATE_YAML, False):
        _LOGGER.debug("Not a YAML migration, skipping")
        return summary

    prefix = entry.data.get(CONF_UNIQUE_ID_PREFIX, DEFAULT_UNIQUE_ID_PREFIX)
    entity_registry = er.async_get(hass)

    # Find MQTT platform entities by unique_id prefix
    mqtt_entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.unique_id.startswith(prefix) and entity.platform == "mqtt"
    ]

    summary["entities_found"] = len(mqtt_entities)
    summary["steps"].append(
        {
            "name": "Find MQTT entities",
            "status": "success" if mqtt_entities else "skipped",
            "detail": f"Found {len(mqtt_entities)} MQTT entities with prefix '{prefix}'",
        }
    )

    if not mqtt_entities:
        _LOGGER.debug("No MQTT entities found to migrate")
        return summary

    _LOGGER.info("Found %d MQTT entities to migrate", len(mqtt_entities))

    # Build mapping and delete old entities
    entity_id_mapping: dict[str, str] = {}

    for entity in mqtt_entities:
        try:
            # Extract entity_key (part after prefix in unique_id)
            entity_key = entity.unique_id.replace(prefix, "", 1)

            # Get ACTUAL entity_id from registry (handles user customization!)
            # e.g., "sensor.my_pool_water_temperature" -> "my_pool_water_temperature"
            actual_entity_id = entity.entity_id
            object_id = actual_entity_id.split(".", 1)[1]

            # Check for collision: is this object_id used by another entity?
            collision_found = False
            for other in entity_registry.entities.values():
                if other.entity_id != actual_entity_id:
                    if other.entity_id.endswith(f".{object_id}"):
                        summary["errors"].append(
                            f"{actual_entity_id}: object_id collision with {other.entity_id}"
                        )
                        collision_found = True
                        break

            if collision_found:
                continue

            # Map: entity_key -> actual object_id
            entity_id_mapping[entity_key] = object_id

            # DELETE the old MQTT entity
            entity_registry.async_remove(entity.entity_id)
            summary["entities_migrated"] += 1

            _LOGGER.info(
                "Deleted MQTT entity %s (key: %s, will recreate with same entity_id)",
                actual_entity_id,
                entity_key,
            )
        except Exception as e:  # noqa: BLE001
            summary["errors"].append(f"{entity.entity_id}: {e}")
            _LOGGER.error("Failed to delete entity %s: %s", entity.entity_id, e)

    # Store mapping in runtime_data for entity creation
    entry.runtime_data.entity_id_mapping = entity_id_mapping

    summary["steps"].append(
        {
            "name": "Delete and map entities",
            "status": "success" if not summary["errors"] else "partial",
            "detail": f"Deleted {summary['entities_migrated']}/{summary['entities_found']}",
        }
    )

    # Show notification
    await _show_migration_summary(hass, summary)

    return summary


async def async_verify_migration(
    hass: HomeAssistant,
    entity_id_mapping: dict[str, str],
) -> dict[str, Any]:
    """Verify migration preserved historical data.

    Uses recorder history API to check if entities have state history
    from before the migration (older than 1 hour).
    Works for ALL entity types.
    """
    # Import here to avoid circular imports and optional dependency
    try:
        from homeassistant.components.recorder.history import (  # noqa: PLC0415
            get_last_state_changes,
        )
    except ImportError:
        _LOGGER.warning("Recorder not available, skipping migration verification")
        return {"verified": 0, "no_history": 0, "failed": ["Recorder not available"]}

    results: dict[str, Any] = {
        "verified": 0,
        "no_history": 0,
        "failed": [],
    }

    domains = ["sensor", "binary_sensor", "switch", "select", "number", "button"]
    now = datetime.now(tz=UTC)

    for object_id in entity_id_mapping.values():
        found = False
        for domain in domains:
            entity_id = f"{domain}.{object_id}"

            try:
                # Get last state change for this entity_id (blocking call)
                history = await hass.async_add_executor_job(
                    get_last_state_changes,
                    hass,
                    1,  # number_of_states - just need 1 to confirm
                    entity_id,
                )

                if history.get(entity_id):
                    states = history[entity_id]
                    if states:
                        last_state = states[0]
                        # If last_changed is older than 1 hour, history was preserved
                        last_changed = last_state.last_changed
                        if last_changed.tzinfo is None:
                            last_changed = last_changed.replace(tzinfo=UTC)
                        if last_changed < now - timedelta(hours=1):
                            results["verified"] += 1
                            _LOGGER.debug(
                                "Migration verified for %s: history from %s",
                                entity_id,
                                last_state.last_changed,
                            )
                            found = True
                            break  # Found in this domain, move to next entity

            except Exception as e:  # noqa: BLE001
                results["failed"].append(f"{entity_id}: {e}")
                _LOGGER.warning("Failed to verify %s: %s", entity_id, e)

        if not found:
            results["no_history"] += 1

    return results


async def _show_migration_summary(hass: HomeAssistant, summary: dict[str, Any]) -> None:
    """Show migration summary as persistent notification."""
    lines = ["## NeoPool YAML Migration Complete\n"]

    # Steps summary
    lines.append("### Steps:")
    for step in summary["steps"]:
        if step["status"] == "success":
            icon = "✓"
        elif step["status"] == "partial":
            icon = "⚠️"
        else:
            icon = "○"
        lines.append(f"- {icon} **{step['name']}**: {step['detail']}")

    # Entity counts
    lines.append("\n### Results:")
    lines.append(f"- Entities found: **{summary['entities_found']}**")
    lines.append(f"- Entities migrated: **{summary['entities_migrated']}**")

    # Errors if any
    if summary["errors"]:
        lines.append(f"\n### Errors ({len(summary['errors'])}):")
        lines.extend(f"- {error}" for error in summary["errors"][:5])
        if len(summary["errors"]) > 5:
            lines.append(f"- ...and {len(summary['errors']) - 5} more")

    persistent_notification.async_create(
        hass,
        message="\n".join(lines),
        title="NeoPool Migration",
        notification_id="neopool_migration_summary",
    )


async def async_register_device(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Register the NeoPool device in the device registry."""
    device_registry = dr.async_get(hass)

    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    nodeid = entry.data.get(CONF_NODEID, "")

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, nodeid)},
        manufacturer=MANUFACTURER,
        name=device_name,
        model="NeoPool Controller",
        sw_version=VERSION,
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
    """Get device info for NeoPool entities."""
    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    nodeid = entry.data.get(CONF_NODEID, "")

    return dr.DeviceInfo(
        identifiers={(DOMAIN, nodeid)},
        manufacturer=MANUFACTURER,
        name=device_name,
        model="NeoPool Controller",
        sw_version=VERSION,
        configuration_url="https://tasmota.github.io/docs/NeoPool/",
    )
