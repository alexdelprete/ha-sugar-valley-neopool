"""Number platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import config_register_signal
from .const import (
    CMD_CHLORINE,
    CMD_HYDROLYSIS,
    CMD_IONIZATION,
    CMD_PH_MAX,
    CMD_PH_MIN,
    CMD_REDOX,
    HEATING_TEMP_MAX,
    HEATING_TEMP_MIN,
    HEATING_TEMP_STEP,
    HIDRO_COVER_REDUCTION_MAX,
    HIDRO_COVER_REDUCTION_MIN,
    HIDRO_COVER_REDUCTION_STEP,
    HIDRO_SHUTDOWN_TEMP_MAX,
    HIDRO_SHUTDOWN_TEMP_MIN,
    HIDRO_SHUTDOWN_TEMP_STEP,
    INTELLIGENT_MIN_TIME_MAX,
    INTELLIGENT_MIN_TIME_MIN,
    INTELLIGENT_MIN_TIME_STEP,
    JSON_PATH_CHLORINE_SETPOINT,
    JSON_PATH_HYDROLYSIS_DATA,
    JSON_PATH_HYDROLYSIS_SETPOINT,
    JSON_PATH_IONIZATION_MAX,
    JSON_PATH_IONIZATION_SETPOINT,
    JSON_PATH_PH_DATA,
    JSON_PATH_PH_MAX,
    JSON_PATH_PH_MIN,
    JSON_PATH_REDOX_SETPOINT,
    JSON_PATH_RELAY_HEATING,
    JSON_PATH_TEMPERATURE,
    PH_ACTIVATION_DELAY_MAX,
    PH_ACTIVATION_DELAY_MIN,
    PH_ACTIVATION_DELAY_STEP,
    REG_HEATING_TEMP,
    REG_HIDRO_COVER_REDUCTION,
    REG_INTELLIGENT_FILT_MIN_TIME,
    REG_RELAY_ACTIVATION_DELAY,
    SHIFT_HIDRO_COVER_REDUCTION,
    SHIFT_HIDRO_SHUTDOWN_TEMP,
)
from .entity import NeoPoolMQTTEntity
from .helpers import get_nested_value, parse_json_payload, safe_float

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components import mqtt
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolNumberEntityDescription(NumberEntityDescription):
    """Describes a NeoPool number entity."""

    json_path: str
    command: str
    command_template: str | None = None
    value_fn: Callable[[Any], float | None] = safe_float
    max_json_path: str | None = None


NUMBER_DESCRIPTIONS: tuple[NeoPoolNumberEntityDescription, ...] = (
    NeoPoolNumberEntityDescription(
        key="ph_min",
        translation_key="ph_min",
        name="pH Min",
        device_class=NumberDeviceClass.PH,
        native_min_value=0.0,
        native_max_value=14.0,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        json_path=JSON_PATH_PH_MIN,
        command=CMD_PH_MIN,
    ),
    NeoPoolNumberEntityDescription(
        key="ph_max",
        translation_key="ph_max",
        name="pH Max",
        device_class=NumberDeviceClass.PH,
        native_min_value=0.0,
        native_max_value=14.0,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        json_path=JSON_PATH_PH_MAX,
        command=CMD_PH_MAX,
    ),
    NeoPoolNumberEntityDescription(
        key="redox_setpoint",
        translation_key="redox_setpoint",
        name="Redox Setpoint",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        mode=NumberMode.SLIDER,
        json_path=JSON_PATH_REDOX_SETPOINT,
        command=CMD_REDOX,
    ),
    # Chlorine setpoint — disabled by default; re-enabled when Modules.Chlorine == 1
    NeoPoolNumberEntityDescription(
        key="chlorine_setpoint",
        translation_key="chlorine_setpoint",
        name="Chlorine Setpoint",
        native_unit_of_measurement="ppm",
        native_min_value=0,
        native_max_value=10,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        json_path=JSON_PATH_CHLORINE_SETPOINT,
        command=CMD_CHLORINE,
        entity_registry_enabled_default=False,
    ),
    NeoPoolNumberEntityDescription(
        key="hydrolysis_setpoint",
        translation_key="hydrolysis_setpoint",
        name="Hydrolysis Setpoint",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        json_path=JSON_PATH_HYDROLYSIS_SETPOINT,
        command=CMD_HYDROLYSIS,
        command_template="{value} %",  # NeoPool expects "50 %" format
    ),
    # Ionization setpoint — disabled by default; re-enabled when Modules.Ionization == 1
    NeoPoolNumberEntityDescription(
        key="ionization_setpoint",
        translation_key="ionization_setpoint",
        name="Ionization Setpoint",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        json_path=JSON_PATH_IONIZATION_SETPOINT,
        command=CMD_IONIZATION,
        max_json_path=JSON_PATH_IONIZATION_MAX,
        entity_registry_enabled_default=False,
    ),
)


@dataclass(frozen=True, kw_only=True)
class NeoPoolRegisterNumberEntityDescription(NumberEntityDescription):
    """Describes a NeoPool config-register number (state read via NPRead)."""

    register: int
    # SENSOR JSON paths that must all be present for availability.
    gating_paths: tuple[str, ...]


REGISTER_NUMBER_DESCRIPTIONS: tuple[NeoPoolRegisterNumberEntityDescription, ...] = (
    NeoPoolRegisterNumberEntityDescription(
        key="heating_temp",
        translation_key="heating_temp",
        name="Heating Temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=HEATING_TEMP_MIN,
        native_max_value=HEATING_TEMP_MAX,
        native_step=HEATING_TEMP_STEP,
        mode=NumberMode.SLIDER,
        register=REG_HEATING_TEMP,
        gating_paths=(JSON_PATH_RELAY_HEATING, JSON_PATH_TEMPERATURE),
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolRegisterNumberEntityDescription(
        key="intelligent_min_time",
        translation_key="intelligent_min_time",
        name="Intelligent Min Filtration Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=INTELLIGENT_MIN_TIME_MIN,
        native_max_value=INTELLIGENT_MIN_TIME_MAX,
        native_step=INTELLIGENT_MIN_TIME_STEP,
        mode=NumberMode.BOX,
        register=REG_INTELLIGENT_FILT_MIN_TIME,
        gating_paths=(JSON_PATH_RELAY_HEATING, JSON_PATH_TEMPERATURE),
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolRegisterNumberEntityDescription(
        key="ph_activation_delay",
        translation_key="ph_activation_delay",
        name="pH Pump Activation Delay",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=PH_ACTIVATION_DELAY_MIN,
        native_max_value=PH_ACTIVATION_DELAY_MAX,
        native_step=PH_ACTIVATION_DELAY_STEP,
        mode=NumberMode.BOX,
        register=REG_RELAY_ACTIVATION_DELAY,
        gating_paths=(JSON_PATH_PH_DATA,),
        entity_category=EntityCategory.CONFIG,
    ),
)


@dataclass(frozen=True, kw_only=True)
class NeoPoolRegisterByteNumberEntityDescription(NeoPoolRegisterNumberEntityDescription):
    """A config-register number stored in one byte of a shared register."""

    byte_shift: int  # 0 for the low byte, 8 for the high byte


REGISTER_BYTE_NUMBER_DESCRIPTIONS: tuple[NeoPoolRegisterByteNumberEntityDescription, ...] = (
    NeoPoolRegisterByteNumberEntityDescription(
        key="hydro_cover_reduction_pct",
        translation_key="hydro_cover_reduction_pct",
        name="Hydrolysis Cover Reduction",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=HIDRO_COVER_REDUCTION_MIN,
        native_max_value=HIDRO_COVER_REDUCTION_MAX,
        native_step=HIDRO_COVER_REDUCTION_STEP,
        mode=NumberMode.SLIDER,
        register=REG_HIDRO_COVER_REDUCTION,
        byte_shift=SHIFT_HIDRO_COVER_REDUCTION,
        gating_paths=(JSON_PATH_HYDROLYSIS_DATA,),
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolRegisterByteNumberEntityDescription(
        key="hydro_shutdown_temp",
        translation_key="hydro_shutdown_temp",
        name="Hydrolysis Shutdown Temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=HIDRO_SHUTDOWN_TEMP_MIN,
        native_max_value=HIDRO_SHUTDOWN_TEMP_MAX,
        native_step=HIDRO_SHUTDOWN_TEMP_STEP,
        mode=NumberMode.BOX,
        register=REG_HIDRO_COVER_REDUCTION,
        byte_shift=SHIFT_HIDRO_SHUTDOWN_TEMP,
        gating_paths=(JSON_PATH_HYDROLYSIS_DATA, JSON_PATH_TEMPERATURE),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool numbers based on a config entry."""
    _LOGGER.debug("Setting up NeoPool numbers")

    numbers: list[NumberEntity] = [
        NeoPoolNumber(entry, description) for description in NUMBER_DESCRIPTIONS
    ]
    numbers.extend(
        NeoPoolRegisterNumber(entry, description) for description in REGISTER_NUMBER_DESCRIPTIONS
    )
    numbers.extend(
        NeoPoolRegisterByteNumber(entry, description)
        for description in REGISTER_BYTE_NUMBER_DESCRIPTIONS
    )

    async_add_entities(numbers)
    _LOGGER.info("Added %d NeoPool numbers", len(numbers))


class NeoPoolNumber(NeoPoolMQTTEntity, NumberEntity):
    """Representation of a NeoPool number."""

    entity_description: NeoPoolNumberEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        self._attr_native_value: float | None = None
        self._dynamic_max_received: bool = not bool(description.max_json_path)

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

            # Update dynamic max value from payload if configured
            if self.entity_description.max_json_path:
                raw_max = get_nested_value(payload, self.entity_description.max_json_path)
                max_value = safe_float(raw_max) if raw_max is not None else None
                if max_value is not None:
                    self._attr_native_max_value = max_value
                    self._dynamic_max_received = True
                elif not self._dynamic_max_received:
                    # Max not yet received, entity stays unavailable
                    self._attr_available = False
                    self.async_write_ha_state()
                    return

            raw_value = get_nested_value(payload, self.entity_description.json_path)
            if raw_value is None:
                self._attr_native_value = None
                self._attr_available = False
                self.async_write_ha_state()
                return

            self._attr_native_value = self.entity_description.value_fn(raw_value)
            self._attr_available = True
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        # Format the command payload
        if self.entity_description.command_template:
            payload = self.entity_description.command_template.format(value=int(value))
        # Check if the value should be int or float
        elif self.entity_description.native_step and self.entity_description.native_step >= 1:
            payload = str(int(value))
        else:
            payload = str(value)

        await self._publish_command(
            self.entity_description.command,
            payload,
        )
        _LOGGER.debug(
            "Set %s to %s",
            self.entity_description.key,
            payload,
        )


class NeoPoolRegisterNumber(NeoPoolMQTTEntity, NumberEntity):
    """A number backed by a config register read via NPRead / written via NPWrite.

    State lives in runtime_data.register_state (populated by the startup NPRead
    and kept current by the write-ACK). Availability self-gates on the presence
    of the configured SENSOR keys.
    """

    entity_description: NeoPoolRegisterNumberEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolRegisterNumberEntityDescription,
    ) -> None:
        """Initialize the register-backed number."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
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
            self._gating_ok = all(
                get_nested_value(payload, path) is not None
                for path in self.entity_description.gating_paths
            )
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    @callback
    def _handle_register_update(self) -> None:
        """React to a config-register cache update."""
        self.async_write_ha_state()

    @property
    def _register_value(self) -> int | None:
        """Return the cached raw register value, if known."""
        return self._config_entry.runtime_data.register_state.get(self.entity_description.register)

    @property
    def native_value(self) -> float | None:
        """Return the cached register value."""
        return self._register_value

    @property
    def available(self) -> bool:
        """Available when online, gating keys present, and a value is cached."""
        return super().available and self._gating_ok and self._register_value is not None

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the register (raw integer)."""
        int_value = int(value)
        await self._write_register(self.entity_description.register, int_value)
        self._config_entry.runtime_data.register_state[self.entity_description.register] = int_value
        self.async_write_ha_state()
        _LOGGER.debug("Set %s to %s", self.entity_description.key, int_value)


class NeoPoolRegisterByteNumber(NeoPoolRegisterNumber):
    """A number stored in one byte (low or high) of a shared config register.

    Reuses the register-number subscription/gating/availability logic but reads
    and writes a single byte via read-modify-write so the sibling byte in the
    same register (e.g. the cover-% vs shutdown-temp fields of 0x042D) is
    preserved.
    """

    entity_description: NeoPoolRegisterByteNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the byte field of the cached register value."""
        value = self._register_value
        if value is None:
            return None
        return (value >> self.entity_description.byte_shift) & 0xFF

    async def async_set_native_value(self, value: float) -> None:
        """Read-modify-write the byte field; no-op if the value isn't cached."""
        current = self._register_value
        if current is None:
            # Entity is unavailable without a cached value; guard against
            # clobbering the sibling byte on a blind write.
            return
        shift = self.entity_description.byte_shift
        new_value = (current & ~(0xFF << shift)) | ((int(value) & 0xFF) << shift)
        await self._write_register(self.entity_description.register, new_value)
        self._config_entry.runtime_data.register_state[self.entity_description.register] = new_value
        self.async_write_ha_state()
        _LOGGER.debug("Set %s to %s", self.entity_description.key, int(value))
