"""Diagnostics support for Sugar Valley NeoPool.

https://github.com/alexdelprete/ha-sugar-valley-neopool
"""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NeoPoolConfigEntry
from .const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    VERSION,
)

# Keys to redact from diagnostics output
TO_REDACT = {
    CONF_NODEID,
    "nodeid",
    "NodeID",
    "mqtt_topic",
    CONF_DISCOVERY_PREFIX,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: NeoPoolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = config_entry.runtime_data

    # Gather configuration data
    config_data = {
        "entry_id": config_entry.entry_id,
        "version": config_entry.version,
        "domain": DOMAIN,
        "integration_version": VERSION,
        "data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "options": dict(config_entry.options),
    }

    # Gather device info
    device_data = {
        "name": config_entry.data.get(CONF_DEVICE_NAME),
        "mqtt_topic": "**REDACTED**",
        "nodeid": "**REDACTED**",
        "manufacturer": MANUFACTURER,
        "model": MODEL,
        "available": runtime_data.available,
    }

    # Gather sensor data (redact sensitive values)
    sensor_data = {}
    if runtime_data.sensor_data:
        for key, value in runtime_data.sensor_data.items():
            if key in TO_REDACT:
                sensor_data[key] = "**REDACTED**"
            else:
                sensor_data[key] = value

    return {
        "config": config_data,
        "device": device_data,
        "sensors": sensor_data,
    }
