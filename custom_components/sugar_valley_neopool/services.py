"""Services for the NeoPool MQTT integration.

Group 4a — controller timer scheduling. The ``set_timer`` service writes one of
the controller's 12 built-in timers (filtration 1-3, light, aux1-4) so the
schedule runs on the device itself, independent of Home Assistant. The timer
registers are not in the SENSOR payload, so they are written on demand with the
built-in ``NPWrite`` / ``NPWriteL`` commands, committed with ``NPExec`` and
persisted with ``NPSave``. No Berry extension is required.
"""

from __future__ import annotations

from datetime import time as dt_time
import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CMD_NPEXEC,
    CMD_NPSAVE,
    CMD_NPWRITE,
    CMD_NPWRITEL,
    DOMAIN,
    SECONDS_PER_DAY,
    TIMER_BLOCKS,
    TIMER_MODE_MAP,
    TIMER_OFFSET_ENABLE,
    TIMER_OFFSET_INTERVAL,
    TIMER_OFFSET_OFF,
    TIMER_OFFSET_ON,
    TIMER_OFFSET_PERIOD,
)

if TYPE_CHECKING:
    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TIMER = "set_timer"

ATTR_DEVICE_ID = "device_id"
ATTR_TIMER = "timer"
ATTR_START = "start"
ATTR_STOP = "stop"
ATTR_PERIOD = "period"
ATTR_MODE = "mode"

SET_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_TIMER): vol.In(list(TIMER_BLOCKS)),
        vol.Required(ATTR_START): cv.time,
        vol.Required(ATTR_STOP): cv.time,
        vol.Optional(ATTR_PERIOD, default=SECONDS_PER_DAY): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=7 * SECONDS_PER_DAY)
        ),
        vol.Optional(ATTR_MODE, default="auto"): vol.In(list(TIMER_MODE_MAP)),
    }
)


def _seconds_since_midnight(value: dt_time) -> int:
    """Return seconds since midnight for a time value."""
    return value.hour * 3600 + value.minute * 60 + value.second


def _resolve_entry(hass: HomeAssistant, device_id: str) -> NeoPoolConfigEntry | None:
    """Resolve a target device_id to this integration's config entry."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            return entry
    return None


async def _async_set_timer(call: ServiceCall) -> None:
    """Write one controller timer block from the service call."""
    hass = call.hass
    entry = _resolve_entry(hass, call.data[ATTR_DEVICE_ID])
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="set_timer_unknown_device",
            translation_placeholders={"device_id": call.data[ATTR_DEVICE_ID]},
        )

    mqtt_topic = entry.runtime_data.mqtt_topic
    base = TIMER_BLOCKS[call.data[ATTR_TIMER]]
    start = _seconds_since_midnight(call.data[ATTR_START])
    stop = _seconds_since_midnight(call.data[ATTR_STOP])
    interval = (stop - start) % SECONDS_PER_DAY
    period = call.data[ATTR_PERIOD]
    mode = TIMER_MODE_MAP[call.data[ATTR_MODE]]

    async def _pub(command: str, payload: str) -> None:
        await mqtt.async_publish(hass, f"cmnd/{mqtt_topic}/{command}", payload, qos=1, retain=False)

    # 16-bit enable/mode, then the 32-bit ON/OFF/INTERVAL/PERIOD pairs, then
    # commit (NPExec) and persist (NPSave — a schedule should survive reboot).
    await _pub(CMD_NPWRITE, f"0x{base + TIMER_OFFSET_ENABLE:04X} {mode}")
    await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_ON:04X} {start}")
    await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_OFF:04X} {stop}")
    await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_INTERVAL:04X} {interval}")
    await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_PERIOD:04X} {period}")
    await _pub(CMD_NPEXEC, "")
    await _pub(CMD_NPSAVE, "")

    _LOGGER.debug(
        "set_timer %s on %s: start=%ds stop=%ds interval=%ds period=%ds mode=%d",
        call.data[ATTR_TIMER],
        mqtt_topic,
        start,
        stop,
        interval,
        period,
        mode,
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent across multiple entries)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_TIMER):
        return
    hass.services.async_register(
        DOMAIN, SERVICE_SET_TIMER, _async_set_timer, schema=SET_TIMER_SCHEMA
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove integration services when the last entry unloads."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_TIMER)
