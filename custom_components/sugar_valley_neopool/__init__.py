"""The NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
    VERSION,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class NeoPoolData:
    """Runtime data for the NeoPool integration."""

    device_name: str
    mqtt_topic: str
    nodeid: str
    sensor_data: dict[str, Any] = field(default_factory=dict)
    available: bool = False


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

    # Register device in device registry
    await async_register_device(hass, entry)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("NeoPool MQTT integration setup complete for %s", device_name)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading NeoPool MQTT integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.info("NeoPool MQTT integration unloaded successfully")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.debug("Reloading NeoPool MQTT integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_yaml_entities(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    nodeid: str,
) -> None:
    """Migrate YAML package entities to new unique_id format.

    Old format: neopool_mqtt_{key}
    New format: neopool_mqtt_{nodeid}_{key}

    This preserves historical data by updating entity unique_ids in the registry.
    """
    entity_registry = er.async_get(hass)

    # Get all entities that might be from YAML package
    # YAML entities are not associated with any config entry
    all_entities = list(entity_registry.entities.values())
    yaml_entities = [
        entity
        for entity in all_entities
        if entity.unique_id.startswith("neopool_mqtt_") and entity.config_entry_id is None
    ]

    if not yaml_entities:
        _LOGGER.debug("No YAML entities found to migrate")
        return

    _LOGGER.info(
        "Found %d YAML package entities to migrate to NodeID-based unique_ids",
        len(yaml_entities),
    )

    # Migrate each entity
    for entity in yaml_entities:
        old_unique_id = entity.unique_id

        # Extract entity key from old unique_id
        # Old format: neopool_mqtt_{key}
        if old_unique_id.startswith("neopool_mqtt_"):
            entity_key = old_unique_id.replace("neopool_mqtt_", "", 1)

            # New format: neopool_mqtt_{nodeid}_{key}
            new_unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"

            # Update entity unique_id and associate with this config entry
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=new_unique_id,
                config_entry_id=entry.entry_id,
            )

            _LOGGER.info(
                "Migrated entity %s: %s -> %s",
                entity.entity_id,
                old_unique_id,
                new_unique_id,
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
