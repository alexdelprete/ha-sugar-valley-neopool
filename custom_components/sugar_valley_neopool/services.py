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
from typing import TYPE_CHECKING, Any

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
    TIMER_FUNCTION_CODES,
    TIMER_MODE_MAP,
    TIMER_OFFSET_ENABLE,
    TIMER_OFFSET_FUNCTION,
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


def _validate_set_timer(data: dict[str, Any]) -> dict[str, Any]:
    """Cross-field rules for granular (partial) timer edits.

    All schedule fields are optional so a call can change just one thing (e.g.
    only the mode), but ``start`` and ``stop`` are coupled (the run interval is
    derived from the pair), and a call must change at least one field.
    """
    if (ATTR_START in data) != (ATTR_STOP in data):
        raise vol.Invalid("'start' and 'stop' must be set together")
    if not any(k in data for k in (ATTR_START, ATTR_PERIOD, ATTR_MODE)):
        raise vol.Invalid("provide at least one of 'start'/'stop', 'period', or 'mode'")
    return data


SET_TIMER_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required(ATTR_TIMER): vol.In(list(TIMER_BLOCKS)),
            # All schedule fields optional → only the ones provided are written
            # (granular edit). No defaults, so an omitted field keeps its current
            # value on the controller (we simply don't write that register).
            vol.Optional(ATTR_START): cv.time,
            vol.Optional(ATTR_STOP): cv.time,
            vol.Optional(ATTR_PERIOD): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=7 * SECONDS_PER_DAY)
            ),
            vol.Optional(ATTR_MODE): vol.In(list(TIMER_MODE_MAP)),
        },
        _validate_set_timer,
    )
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
    timer = call.data[ATTR_TIMER]
    base = TIMER_BLOCKS[timer]
    function_code = TIMER_FUNCTION_CODES.get(timer)

    async def _pub(command: str, payload: str) -> None:
        await mqtt.async_publish(hass, f"cmnd/{mqtt_topic}/{command}", payload, qos=1, retain=False)

    # Granular edit: only registers for the fields actually supplied are written;
    # omitted fields keep their current value on the controller. We never read
    # the block first (our MQTT transport makes a read-modify-write round trip
    # costly/fragile), so a write is fully specified by the call.
    start_t = call.data.get(ATTR_START)
    stop_t = call.data.get(ATTR_STOP)
    period = call.data.get(ATTR_PERIOD)
    mode_name = call.data.get(ATTR_MODE)

    # Always (re)bind the timer to its relay via the function word — without it
    # the block is inert (verified on-device: AUX and filtration timers were
    # unbound). Idempotent where the controller already bound it (e.g. light).
    if function_code is not None:
        await _pub(CMD_NPWRITE, f"0x{base + TIMER_OFFSET_FUNCTION:04X} {function_code}")

    if mode_name is not None:
        mode = TIMER_MODE_MAP[mode_name]
        await _pub(CMD_NPWRITE, f"0x{base + TIMER_OFFSET_ENABLE:04X} {mode}")

    if start_t is not None and stop_t is not None:
        start = _seconds_since_midnight(start_t)
        stop = _seconds_since_midnight(stop_t)
        interval = (stop - start) % SECONDS_PER_DAY
        await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_ON:04X} {start}")
        await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_OFF:04X} {stop}")
        await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_INTERVAL:04X} {interval}")

    if period is not None:
        await _pub(CMD_NPWRITEL, f"0x{base + TIMER_OFFSET_PERIOD:04X} {period}")

    # Commit (NPExec) and persist (NPSave — a schedule should survive reboot).
    await _pub(CMD_NPEXEC, "")
    await _pub(CMD_NPSAVE, "")

    _LOGGER.debug(
        "set_timer %s on %s: fields=%s",
        timer,
        mqtt_topic,
        {
            k: call.data[k]
            for k in (ATTR_START, ATTR_STOP, ATTR_PERIOD, ATTR_MODE)
            if k in call.data
        },
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
