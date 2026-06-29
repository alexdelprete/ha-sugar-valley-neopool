"""Select platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import config_register_signal
from .const import (
    AUX1_FUNCTION_CODE,
    AUX2_FUNCTION_CODE,
    AUX3_FUNCTION_CODE,
    AUX4_FUNCTION_CODE,
    AUX_MODE_MAP,
    BOOST_MODE_MAP,
    CMD_BOOST,
    CMD_FILTRATION_MODE,
    CMD_FILTRATION_SPEED,
    CMD_NPWRITE,
    CONF_PUMP_TYPE,
    DEFAULT_PUMP_TYPE,
    FILTRATION_MODE_MAP,
    FILTRATION_SPEED_MAP,
    FILTRATION_TIMER_SPEED_MAP,
    FILTRATION_TIMER_SPEED_MASK,
    JSON_PATH_FILTRATION_MODE,
    JSON_PATH_FILTRATION_SPEED,
    JSON_PATH_HYDROLYSIS_BOOST,
    JSON_PATH_RELAY_AUX,
    PUMP_TYPE_STANDARD,
    PUMP_TYPE_VARIABLE,
    REG_AUX1_FUNCTION,
    REG_AUX1_MODE,
    REG_AUX2_FUNCTION,
    REG_AUX2_MODE,
    REG_AUX3_FUNCTION,
    REG_AUX3_MODE,
    REG_AUX4_FUNCTION,
    REG_AUX4_MODE,
    REG_FILTRATION_CONF,
    SHIFT_FILTRATION_TIMER1_SPEED,
    SHIFT_FILTRATION_TIMER2_SPEED,
    SHIFT_FILTRATION_TIMER3_SPEED,
)
from .entity import NeoPoolMQTTEntity
from .helpers import get_nested_value, lookup_by_value, parse_json_payload, safe_int

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components import mqtt
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolSelectEntityDescription(SelectEntityDescription):
    """Describes a NeoPool select entity."""

    json_path: str
    command: str
    options_map: dict[int, str]
    value_fn: Callable[[Any], str | None] | None = None


def create_value_fn(options_map: dict[int, str]) -> Callable[[Any], str | None]:
    """Create a value function that maps int to string option."""

    def value_fn(x: Any) -> str | None:
        int_val = safe_int(x)
        if int_val is not None:
            return options_map.get(int_val)
        return None

    return value_fn


SELECT_DESCRIPTIONS: tuple[NeoPoolSelectEntityDescription, ...] = (
    NeoPoolSelectEntityDescription(
        key="filtration_mode",
        translation_key="filtration_mode",
        name="Filtration Mode",
        json_path=JSON_PATH_FILTRATION_MODE,
        command=CMD_FILTRATION_MODE,
        options_map=FILTRATION_MODE_MAP,
        options=list(FILTRATION_MODE_MAP.values()),
    ),
    NeoPoolSelectEntityDescription(
        key="filtration_speed",
        translation_key="filtration_speed",
        name="Filtration Speed",
        json_path=JSON_PATH_FILTRATION_SPEED,
        command=CMD_FILTRATION_SPEED,
        options_map=FILTRATION_SPEED_MAP,
        options=list(FILTRATION_SPEED_MAP.values()),
    ),
    NeoPoolSelectEntityDescription(
        key="boost_mode",
        translation_key="boost_mode",
        name="Boost Mode",
        json_path=JSON_PATH_HYDROLYSIS_BOOST,
        command=CMD_BOOST,
        options_map=BOOST_MODE_MAP,
        options=list(BOOST_MODE_MAP.values()),
    ),
)


@dataclass(frozen=True, kw_only=True)
class NeoPoolAuxModeSelectEntityDescription(SelectEntityDescription):
    """Describes a register-backed AUX relay mode select (auto/on/off)."""

    register: int  # mode/enable word (timer-block +0)
    function_register: int  # function word (timer-block +11)
    function_code: int  # MBV_PAR_CTIMER_FCT_RELAY bit that binds the timer
    aux_index: int  # 0-based index into NeoPool.Relay.Aux for availability gating


AUX_MODE_SELECT_DESCRIPTIONS: tuple[NeoPoolAuxModeSelectEntityDescription, ...] = (
    NeoPoolAuxModeSelectEntityDescription(
        key="aux1_mode",
        translation_key="aux1_mode",
        name="AUX1 Mode",
        register=REG_AUX1_MODE,
        function_register=REG_AUX1_FUNCTION,
        function_code=AUX1_FUNCTION_CODE,
        aux_index=0,
    ),
    NeoPoolAuxModeSelectEntityDescription(
        key="aux2_mode",
        translation_key="aux2_mode",
        name="AUX2 Mode",
        register=REG_AUX2_MODE,
        function_register=REG_AUX2_FUNCTION,
        function_code=AUX2_FUNCTION_CODE,
        aux_index=1,
    ),
    NeoPoolAuxModeSelectEntityDescription(
        key="aux3_mode",
        translation_key="aux3_mode",
        name="AUX3 Mode",
        register=REG_AUX3_MODE,
        function_register=REG_AUX3_FUNCTION,
        function_code=AUX3_FUNCTION_CODE,
        aux_index=2,
    ),
    NeoPoolAuxModeSelectEntityDescription(
        key="aux4_mode",
        translation_key="aux4_mode",
        name="AUX4 Mode",
        register=REG_AUX4_MODE,
        function_register=REG_AUX4_FUNCTION,
        function_code=AUX4_FUNCTION_CODE,
        aux_index=3,
    ),
)


@dataclass(frozen=True, kw_only=True)
class NeoPoolTimerSpeedSelectEntityDescription(SelectEntityDescription):
    """Describes a per-timer filtration-speed select (variable-speed pumps)."""

    bit_shift: int  # position of the 3-bit speed field in REG_FILTRATION_CONF


TIMER_SPEED_SELECT_DESCRIPTIONS: tuple[NeoPoolTimerSpeedSelectEntityDescription, ...] = (
    NeoPoolTimerSpeedSelectEntityDescription(
        key="filtration_timer1_speed",
        translation_key="filtration_timer1_speed",
        name="Filtration Timer 1 Speed",
        bit_shift=SHIFT_FILTRATION_TIMER1_SPEED,
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolTimerSpeedSelectEntityDescription(
        key="filtration_timer2_speed",
        translation_key="filtration_timer2_speed",
        name="Filtration Timer 2 Speed",
        bit_shift=SHIFT_FILTRATION_TIMER2_SPEED,
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolTimerSpeedSelectEntityDescription(
        key="filtration_timer3_speed",
        translation_key="filtration_timer3_speed",
        name="Filtration Timer 3 Speed",
        bit_shift=SHIFT_FILTRATION_TIMER3_SPEED,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool selects based on a config entry."""
    _LOGGER.debug("Setting up NeoPool selects")

    selects: list[SelectEntity] = [
        NeoPoolSelect(entry, description) for description in SELECT_DESCRIPTIONS
    ]
    selects.extend(
        NeoPoolAuxModeSelect(entry, description) for description in AUX_MODE_SELECT_DESCRIPTIONS
    )
    selects.extend(
        NeoPoolTimerSpeedSelect(entry, description)
        for description in TIMER_SPEED_SELECT_DESCRIPTIONS
    )

    async_add_entities(selects)
    _LOGGER.info("Added %d NeoPool selects", len(selects))


class NeoPoolSelect(NeoPoolMQTTEntity, SelectEntity):
    """Representation of a NeoPool select."""

    entity_description: NeoPoolSelectEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        self._attr_current_option: str | None = None
        self._attr_options = description.options or []

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topic when entity is added."""
        await super().async_added_to_hass()

        mqtt_topic = self.mqtt_topic
        sensor_topic = f"tele/{mqtt_topic}/SENSOR"

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle new MQTT message."""
            payload = parse_json_payload(msg.payload)
            if payload is None:
                return

            raw_value = get_nested_value(payload, self.entity_description.json_path)
            if raw_value is None:
                self._attr_current_option = None
                self._attr_available = False
                self.async_write_ha_state()
                return

            # Convert raw value to option string
            if self.entity_description.value_fn is not None:
                option = self.entity_description.value_fn(raw_value)
            else:
                int_val = safe_int(raw_value)
                if int_val is not None:
                    option = self.entity_description.options_map.get(int_val)
                else:
                    option = None

            if option is not None:
                self._attr_current_option = option
                self._attr_available = True
                self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Reverse lookup: find the int value for this option
        int_value = lookup_by_value(self.entity_description.options_map, option)

        if int_value is None:
            _LOGGER.warning("Invalid option %s for %s", option, self.entity_description.key)
            return

        await self._publish_command(
            self.entity_description.command,
            str(int_value),
        )
        _LOGGER.debug(
            "Selected option %s (%d) for %s",
            option,
            int_value,
            self.entity_description.key,
        )


class NeoPoolAuxModeSelect(NeoPoolMQTTEntity, SelectEntity):
    """AUX relay mode select (auto/on/off) backed by a timer-block register.

    Replaces the Berry-only NPAux switches. The mode lives in the relay's
    timer-block enable register (read on startup via NPRead, cached in
    runtime_data.register_state, fanned out via config_register_signal); writes
    go through NPWrite + NPExec (no NPSave, so a manual override is transient and
    does not wear the EEPROM). Availability gates on the AUX entry being present
    in the SENSOR NeoPool.Relay.Aux array, like the relay binary sensors.
    """

    entity_description: NeoPoolAuxModeSelectEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolAuxModeSelectEntityDescription,
    ) -> None:
        """Initialize the AUX mode select."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        self._attr_options = list(AUX_MODE_MAP.values())
        self._gating_ok = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to LWT, the config-register signal, and SENSOR gating."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                config_register_signal(self._config_entry),
                self._handle_register_update,
            )
        )

        sensor_topic = f"tele/{self.mqtt_topic}/SENSOR"

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            payload = parse_json_payload(msg.payload)
            if payload is None:
                return
            aux = get_nested_value(payload, JSON_PATH_RELAY_AUX)
            self._gating_ok = isinstance(aux, list) and len(aux) > self.entity_description.aux_index
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    @callback
    def _handle_register_update(self) -> None:
        """React to a config-register cache update."""
        self.async_write_ha_state()

    @property
    def _register_value(self) -> int | None:
        """Return the cached raw mode register value, if known."""
        return self._config_entry.runtime_data.register_state.get(self.entity_description.register)

    @property
    def _function_value(self) -> int | None:
        """Return the cached function-word value (relay binding), if known."""
        return self._config_entry.runtime_data.register_state.get(
            self.entity_description.function_register
        )

    @property
    def _is_bound(self) -> bool:
        """True if the timer is bound to its relay (function word == aux code).

        On-device finding: the mode word is inert unless the function word holds
        the AUX's relay bit, so an unbound timer's mode does not reflect the
        relay. Report None (unknown) for the option until it is bound.
        """
        return self._function_value == self.entity_description.function_code

    @property
    def current_option(self) -> str | None:
        """Return the current mode option (only meaningful while bound)."""
        value = self._register_value
        if value is None or not self._is_bound:
            return None
        return AUX_MODE_MAP.get(value)

    @property
    def available(self) -> bool:
        """Available when online, AUX present in SENSOR, and a mode is cached."""
        return super().available and self._gating_ok and self._register_value is not None

    async def async_select_option(self, option: str) -> None:
        """Set the AUX mode: bind the timer (function word) then write the mode.

        Writing the mode alone is inert (verified on-device) — the function word
        must carry the AUX relay bit to bind the timer to the relay. We write the
        function code (no commit), then the mode with NPExec to apply both. No
        NPSave: a manual override is transient and reverts on power-cycle.
        """
        mode = lookup_by_value(AUX_MODE_MAP, option)
        if mode is None:
            _LOGGER.warning("Invalid AUX mode %s for %s", option, self.entity_description.key)
            return
        desc = self.entity_description
        # Bind the timer to the relay (function word), then apply mode + commit.
        await self._publish_command(
            CMD_NPWRITE, f"0x{desc.function_register:04X} {desc.function_code}"
        )
        await self._write_register(desc.register, mode, save=False, execute=True)
        rs = self._config_entry.runtime_data.register_state
        rs[desc.function_register] = desc.function_code
        rs[desc.register] = mode
        self.async_write_ha_state()
        _LOGGER.debug(
            "Set AUX mode %s (%d, bound via 0x%04X=0x%04X) for %s",
            option,
            mode,
            desc.function_register,
            desc.function_code,
            desc.key,
        )


class NeoPoolTimerSpeedSelect(NeoPoolMQTTEntity, SelectEntity):
    """Per-timer filtration speed for variable-speed pumps (Group 5).

    The three filtration timers each have a 3-bit speed field packed into
    MBF_PAR_FILTRATION_CONF (0x050F), read on startup via NPRead and kept current
    by the write-ACK. Writes are read-modify-write (preserve the other fields).
    The register encodes 0/1/2 = Slow/Medium/Fast (one less than the SENSOR /
    NPFiltrationspeed 1/2/3 encoding — verified on-device).

    Variable-speed gating: the controller emits NeoPool.Filtration.Speed in
    SENSOR only for speed-capable pumps, so the select self-gates on that key.
    The pump_type option overrides it (variable = force on, standard = force off,
    auto = follow the SENSOR detection).
    """

    entity_description: NeoPoolTimerSpeedSelectEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolTimerSpeedSelectEntityDescription,
    ) -> None:
        """Initialize the timer-speed select."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        self._attr_options = list(FILTRATION_TIMER_SPEED_MAP.values())
        self._speed_present = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to LWT, the config-register signal, and SENSOR gating."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                config_register_signal(self._config_entry),
                self._handle_register_update,
            )
        )

        sensor_topic = f"tele/{self.mqtt_topic}/SENSOR"

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            payload = parse_json_payload(msg.payload)
            if payload is None:
                return
            # Filtration.Speed is emitted only for speed-capable (VS) pumps.
            self._speed_present = get_nested_value(payload, JSON_PATH_FILTRATION_SPEED) is not None
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    @callback
    def _handle_register_update(self) -> None:
        """React to a config-register cache update."""
        self.async_write_ha_state()

    @property
    def _vs_enabled(self) -> bool:
        """Whether per-timer speed applies (override, else SENSOR detection)."""
        override = self._config_entry.options.get(CONF_PUMP_TYPE, DEFAULT_PUMP_TYPE)
        if override == PUMP_TYPE_VARIABLE:
            return True
        if override == PUMP_TYPE_STANDARD:
            return False
        return self._speed_present

    @property
    def _conf_value(self) -> int | None:
        """Return the cached raw MBF_PAR_FILTRATION_CONF value, if known."""
        return self._config_entry.runtime_data.register_state.get(REG_FILTRATION_CONF)

    @property
    def _speed_field(self) -> int | None:
        """Return this timer's 3-bit speed value from the register, if known."""
        value = self._conf_value
        if value is None:
            return None
        return (value >> self.entity_description.bit_shift) & FILTRATION_TIMER_SPEED_MASK

    @property
    def current_option(self) -> str | None:
        """Return the current speed option (only meaningful for VS pumps)."""
        field = self._speed_field
        if field is None or not self._vs_enabled:
            return None
        return FILTRATION_TIMER_SPEED_MAP.get(field)

    @property
    def available(self) -> bool:
        """Available for VS pumps when online and the register is cached."""
        return super().available and self._vs_enabled and self._conf_value is not None

    async def async_select_option(self, option: str) -> None:
        """Set this timer's speed (read-modify-write the 3-bit field, persist)."""
        field = lookup_by_value(FILTRATION_TIMER_SPEED_MAP, option)
        current = self._conf_value
        if field is None or current is None:
            _LOGGER.warning(
                "Cannot set %s to %s (field=%s, cached=%s)",
                self.entity_description.key,
                option,
                field,
                current,
            )
            return
        shift = self.entity_description.bit_shift
        new_value = (current & ~(FILTRATION_TIMER_SPEED_MASK << shift)) | (field << shift)
        await self._write_register(REG_FILTRATION_CONF, new_value)
        self._config_entry.runtime_data.register_state[REG_FILTRATION_CONF] = new_value
        self.async_write_ha_state()
        _LOGGER.debug(
            "Set %s = %s (field %d) -> 0x%04X = 0x%04X",
            self.entity_description.key,
            option,
            field,
            REG_FILTRATION_CONF,
            new_value,
        )
