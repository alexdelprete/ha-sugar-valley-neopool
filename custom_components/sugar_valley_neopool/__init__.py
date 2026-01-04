"""The NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Migrate YAML package entities to new unique_id format.

    Old format: {prefix}{key}
    New format: neopool_mqtt_{nodeid}_{key}

    This preserves historical data by updating entity unique_ids in the registry.
    Returns a summary dict with migration results.
    """
    summary: dict[str, Any] = {
        "steps": [],
        "entities_found": 0,
        "entities_migrated": 0,
        "errors": [],
    }

    # Only run if YAML migration was requested
    if not entry.data.get(CONF_MIGRATE_YAML, False):
        _LOGGER.debug("Not a YAML migration, skipping entity migration")
        return summary

    # Get the prefix (default or custom from config flow)
    prefix = entry.data.get(CONF_UNIQUE_ID_PREFIX, DEFAULT_UNIQUE_ID_PREFIX)

    entity_registry = er.async_get(hass)

    # Find all orphaned entities with the prefix
    yaml_entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.unique_id.startswith(prefix) and entity.config_entry_id is None
    ]

    summary["entities_found"] = len(yaml_entities)
    summary["steps"].append(
        {
            "name": "Find orphaned entities",
            "status": "success" if yaml_entities else "skipped",
            "detail": f"Found {len(yaml_entities)} entities with prefix '{prefix}'",
        }
    )

    if not yaml_entities:
        _LOGGER.debug("No YAML entities found to migrate with prefix '%s'", prefix)
        return summary

    _LOGGER.info(
        "Found %d YAML package entities to migrate to NodeID-based unique_ids",
        len(yaml_entities),
    )

    # Migrate each entity
    for entity in yaml_entities:
        old_unique_id = entity.unique_id

        try:
            # Extract entity key from old unique_id
            entity_key = old_unique_id.replace(prefix, "", 1)

            # New format: neopool_mqtt_{nodeid}_{key}
            new_unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"

            # Update entity unique_id and associate with this config entry
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=new_unique_id,
                config_entry_id=entry.entry_id,
            )

            summary["entities_migrated"] += 1
            _LOGGER.info(
                "Migrated entity %s: %s -> %s",
                entity.entity_id,
                old_unique_id,
                new_unique_id,
            )
        except Exception as e:  # noqa: BLE001
            error_msg = f"{entity.entity_id}: {e}"
            summary["errors"].append(error_msg)
            _LOGGER.error("Failed to migrate entity %s: %s", entity.entity_id, e)

    # Add migration step result
    if summary["errors"]:
        status = "partial"
    else:
        status = "success"

    summary["steps"].append(
        {
            "name": "Migrate entities",
            "status": status,
            "detail": f"Migrated {summary['entities_migrated']}/{summary['entities_found']}",
        }
    )

    # Show persistent notification with summary
    await _show_migration_summary(hass, summary)

    return summary


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
