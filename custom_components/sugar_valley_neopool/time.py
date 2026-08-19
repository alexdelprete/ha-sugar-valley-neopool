"""Time platform for NeoPool MQTT integration.

Per-timer start/stop times (#1) for the scheduled timer blocks (filtration 1-3
and light). Each timer's ON/OFF time is a 32-bit value stored across a register
pair; the blocks are not in the SENSOR payload, so the values are read on startup
via NPRead and kept current by the write-ACK (never polled). Setting a time binds
the timer to its relay (function word), rewrites the ON/OFF register, recomputes
the run interval from the cached counterpart, commits with NPExec and persists
with NPSave. External keypad edits are not pushed, so timers are documented as
integration-managed only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time
import logging
from typing import TYPE_CHECKING

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import config_register_signal
from .const import (
    CMD_NPEXEC,
    CMD_NPSAVE,
    CMD_NPWRITE,
    CMD_NPWRITEL,
    SECONDS_PER_DAY,
    TIMER_BLOCKS,
    TIMER_FUNCTION_CODES,
    TIMER_OFFSET_FUNCTION,
    TIMER_OFFSET_INTERVAL,
    TIMER_OFFSET_OFF,
    TIMER_OFFSET_ON,
)
from .entity import NeoPoolMQTTEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolTimerTimeEntityDescription(TimeEntityDescription):
    """Describes a per-timer start/stop time entity."""

    time_register: int  # low register of this ON/OFF 32-bit pair
    counterpart_register: int  # low register of the other (OFF/ON) pair
    interval_register: int  # timer-block +7, recomputed from the pair on write
    function_register: int  # timer-block +11 (relay/function binding)
    function_code: int  # value that binds the timer to its relay
    is_start: bool  # True = this is the ON time, False = the OFF time


# (entity key prefix, display name prefix, TIMER_BLOCKS key) for each timer that
# gets start/stop time entities. Registers/codes come from const (single source).
_TIMER_TIMES: tuple[tuple[str, str, str], ...] = (
    ("filtration_timer1", "Filtration Timer 1", "filtration1"),
    ("filtration_timer2", "Filtration Timer 2", "filtration2"),
    ("filtration_timer3", "Filtration Timer 3", "filtration3"),
    ("light_timer", "Light Timer", "light"),
)


def _build_descriptions() -> tuple[NeoPoolTimerTimeEntityDescription, ...]:
    """Build a start and a stop time description for every scheduled timer."""
    descriptions: list[NeoPoolTimerTimeEntityDescription] = []
    for key_prefix, name_prefix, tkey in _TIMER_TIMES:
        base = TIMER_BLOCKS[tkey]
        on_reg = base + TIMER_OFFSET_ON
        off_reg = base + TIMER_OFFSET_OFF
        interval_reg = base + TIMER_OFFSET_INTERVAL
        function_reg = base + TIMER_OFFSET_FUNCTION
        function_code = TIMER_FUNCTION_CODES[tkey]
        descriptions.append(
            NeoPoolTimerTimeEntityDescription(
                key=f"{key_prefix}_start",
                translation_key=f"{key_prefix}_start",
                name=f"{name_prefix} Start",
                time_register=on_reg,
                counterpart_register=off_reg,
                interval_register=interval_reg,
                function_register=function_reg,
                function_code=function_code,
                is_start=True,
                entity_category=EntityCategory.CONFIG,
            )
        )
        descriptions.append(
            NeoPoolTimerTimeEntityDescription(
                key=f"{key_prefix}_stop",
                translation_key=f"{key_prefix}_stop",
                name=f"{name_prefix} Stop",
                time_register=off_reg,
                counterpart_register=on_reg,
                interval_register=interval_reg,
                function_register=function_reg,
                function_code=function_code,
                is_start=False,
                entity_category=EntityCategory.CONFIG,
            )
        )
    return tuple(descriptions)


TIMER_TIME_DESCRIPTIONS: tuple[NeoPoolTimerTimeEntityDescription, ...] = _build_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool per-timer time entities."""
    _LOGGER.debug("Setting up NeoPool timer time entities")
    entities = [NeoPoolTimerTime(entry, description) for description in TIMER_TIME_DESCRIPTIONS]
    async_add_entities(entities)
    _LOGGER.info("Added %d NeoPool timer time entities", len(entities))


def _seconds_to_time(seconds: int) -> dt_time:
    """Convert seconds-since-midnight to a time (wrapping a full day to 00:00)."""
    seconds %= SECONDS_PER_DAY
    return dt_time(hour=seconds // 3600, minute=(seconds % 3600) // 60, second=seconds % 60)


def _time_to_seconds(value: dt_time) -> int:
    """Return seconds since midnight for a time value."""
    return value.hour * 3600 + value.minute * 60 + value.second


class NeoPoolTimerTime(NeoPoolMQTTEntity, TimeEntity):
    """A scheduled timer's start or stop time, backed by a 32-bit register pair."""

    entity_description: NeoPoolTimerTimeEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolTimerTimeEntityDescription,
    ) -> None:
        """Initialize the timer time entity."""
        super().__init__(config_entry, description.key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Subscribe to LWT and the config-register signal."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                config_register_signal(self._config_entry),
                self._handle_register_update,
            )
        )

    @callback
    def _handle_register_update(self) -> None:
        """React to a config-register cache update."""
        self.async_write_ha_state()

    def _read_pair(self, low_register: int) -> int | None:
        """Reconstruct a 32-bit value from its low/high register pair.

        NeoPool stores 32-bit values low word first (verified against the driver's
        NPWriteL pairing). Returns None until the low word is cached.
        """
        rs = self._config_entry.runtime_data.register_state
        low = rs.get(low_register)
        if low is None:
            return None
        high = rs.get(low_register + 1, 0)
        return low | (high << 16)

    @property
    def native_value(self) -> dt_time | None:
        """Return this timer's start/stop time from the cached register pair."""
        seconds = self._read_pair(self.entity_description.time_register)
        if seconds is None:
            return None
        return _seconds_to_time(seconds)

    @property
    def available(self) -> bool:
        """Available when online and this time's register is cached."""
        return super().available and self.native_value is not None

    async def async_set_value(self, value: dt_time) -> None:
        """Write this timer's start/stop time, recompute the interval, persist.

        Binds the timer (function word), writes the ON/OFF register as a 32-bit
        value, and recomputes the run interval (stop - start) from the cached
        counterpart so the schedule stays coherent when only one end is edited.
        The interval is only rewritten when the counterpart is known.
        """
        desc = self.entity_description
        own = _time_to_seconds(value)
        counterpart = self._read_pair(desc.counterpart_register)

        # (Re)bind the timer to its relay first — an unbound schedule is inert.
        await self._publish_command(
            CMD_NPWRITE, f"0x{desc.function_register:04X} {desc.function_code}"
        )
        await self._publish_command(CMD_NPWRITEL, f"0x{desc.time_register:04X} {own}")

        interval: int | None = None
        if counterpart is not None:
            start, stop = (own, counterpart) if desc.is_start else (counterpart, own)
            interval = (stop - start) % SECONDS_PER_DAY
            await self._publish_command(CMD_NPWRITEL, f"0x{desc.interval_register:04X} {interval}")

        await self._publish_command(CMD_NPEXEC, "")
        await self._publish_command(CMD_NPSAVE, "")

        # Reflect the write in the register cache so the entity updates without a
        # read-back (write-ACK model). Store 32-bit values low word first.
        rs = self._config_entry.runtime_data.register_state
        rs[desc.function_register] = desc.function_code
        rs[desc.time_register] = own & 0xFFFF
        rs[desc.time_register + 1] = (own >> 16) & 0xFFFF
        if interval is not None:
            rs[desc.interval_register] = interval & 0xFFFF
            rs[desc.interval_register + 1] = (interval >> 16) & 0xFFFF
        self.async_write_ha_state()

        _LOGGER.debug(
            "Set %s = %s (%ds) -> 0x%04X; interval=%s",
            desc.key,
            value.isoformat(),
            own,
            desc.time_register,
            interval,
        )
