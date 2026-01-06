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
    CONF_NODEID,
    CONF_OFFLINE_TIMEOUT,
    CONF_RECOVERY_SCRIPT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_RECOVERY_SCRIPT,
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

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Apply entity_id_mapping to preserve original YAML entity IDs
    if entity_id_mapping:
        await _apply_entity_id_mapping(hass, entry, entity_id_mapping)

    # Verify migration and show results if applicable
    if entry.runtime_data.entity_id_mapping:
        verification = await async_verify_migration(hass, entry.runtime_data.entity_id_mapping)
        _LOGGER.info(
            "Migration verification: %d verified, %d no history, %d failed",
            verification["verified"],
            verification["no_history"],
            len(verification["failed"]),
        )
        # Show persistent notification with final migration assessment
        await _show_migration_verification_result(hass, verification, device_name)

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

    Args:
        hass: Home Assistant instance
        entry: Config entry
        entity_id_mapping: Dict mapping entity_key -> original object_id
    """
    entity_registry = er.async_get(hass)
    nodeid = entry.runtime_data.nodeid
    updated_count = 0

    # Entity domains to search - integration creates entities across these platforms
    domains = ["sensor", "binary_sensor", "switch", "select", "number", "button"]

    for entity_key, target_object_id in entity_id_mapping.items():
        # Find the entity by its unique_id (NodeID-based pattern)
        unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"

        # Search across all possible domains since entity_key doesn't indicate domain
        current_entity_id = None
        for domain in domains:
            entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
            if entity_id:
                current_entity_id = entity_id
                break

        if current_entity_id is None:
            _LOGGER.debug("Entity with unique_id %s not found in registry, skipping", unique_id)
            continue

        # Determine domain from current entity_id
        domain = current_entity_id.split(".", 1)[0]
        target_entity_id = f"{domain}.{target_object_id}"

        # Skip if already correct
        if current_entity_id == target_entity_id:
            _LOGGER.debug("Entity %s already has correct entity_id", current_entity_id)
            continue

        # Check if target entity_id is available
        if entity_registry.async_get(target_entity_id) is not None:
            _LOGGER.warning(
                "Cannot rename %s to %s - target already exists",
                current_entity_id,
                target_entity_id,
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

    # Check if recorder component is loaded
    if "recorder" not in hass.config.components:
        _LOGGER.warning("Recorder component not loaded, skipping migration verification")
        return {"verified": 0, "no_history": 0, "failed": ["Recorder not loaded"]}

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


async def _show_migration_verification_result(
    hass: HomeAssistant,
    verification: dict[str, Any],
    device_name: str,
) -> None:
    """Show migration verification result as persistent notification."""
    verified = verification["verified"]
    no_history = verification["no_history"]
    failed = verification["failed"]
    total = verified + no_history

    # Determine overall status
    if verified > 0 and not failed:
        status_icon = "✅"
        status_text = "Migration Successful"
    elif verified > 0 and (no_history > 0 or failed):
        status_icon = "⚠️"
        status_text = "Migration Partially Successful"
    elif no_history > 0 and not failed:
        status_icon = "ℹ️"
        status_text = "Migration Complete (No History to Verify)"
    else:
        status_icon = "❌"
        status_text = "Migration Verification Failed"

    lines = [
        f"## {status_icon} {status_text}",
        "",
        f"**Device**: {device_name}",
        "",
        "### Verification Results:",
        f"- **History preserved**: {verified} entities",
        f"- **No previous history**: {no_history} entities",
        f"- **Verification errors**: {len(failed)}",
        "",
    ]

    if verified > 0:
        lines.append(
            "✓ Historical data from your YAML entities has been preserved. "
            "Your graphs and statistics should show continuous data."
        )
        lines.append("")

    if no_history > 0:
        lines.append(
            f"ℹ️ {no_history} entities had no historical data older than 1 hour to verify. "
            "This is normal for newly created entities or entities that rarely change state."
        )
        lines.append("")

    if failed:
        lines.append("### Errors:")
        lines.extend(f"- {error}" for error in failed[:5])
        if len(failed) > 5:
            lines.append(f"- ...and {len(failed) - 5} more")
        lines.append("")

    if total > 0:
        success_rate = (verified / total) * 100 if total > 0 else 0
        lines.append(f"**Overall**: {verified}/{total} entities verified ({success_rate:.0f}%)")

    persistent_notification.async_create(
        hass,
        message="\n".join(lines),
        title="NeoPool YAML Migration Verification",
        notification_id=f"neopool_migration_verification_{device_name}",
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
