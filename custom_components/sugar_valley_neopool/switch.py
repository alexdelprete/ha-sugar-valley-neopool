"""Switch platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import config_register_signal
from .const import (
    CMD_FILTRATION,
    JSON_PATH_FILTRATION_STATE,
    JSON_PATH_HYDROLYSIS_DATA,
    JSON_PATH_RELAY_HEATING,
    JSON_PATH_RELAY_UV,
    JSON_PATH_TEMPERATURE,
    MASK_HIDRO_COVER_ENABLE,
    MASK_HIDRO_TEMP_SHUTDOWN_ENABLE,
    REG_CLIMA_ONOFF,
    REG_HIDRO_COVER_ENABLE,
    REG_SMART_ANTI_FREEZE,
    REG_UV_MODE,
)
from .entity import NeoPoolEntity, NeoPoolMQTTEntity
from .helpers import bit_to_bool, get_nested_value, parse_json_payload

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components import mqtt
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolSwitchEntityDescription(SwitchEntityDescription):
    """Describes a NeoPool switch entity."""

    json_path: str
    command: str
    payload_on: str = "1"
    payload_off: str = "0"
    value_fn: Callable[[Any], bool | None] = bit_to_bool


SWITCH_DESCRIPTIONS: tuple[NeoPoolSwitchEntityDescription, ...] = (
    NeoPoolSwitchEntityDescription(
        key="filtration",
        translation_key="filtration",
        name="Filtration",
        json_path=JSON_PATH_FILTRATION_STATE,
        command=CMD_FILTRATION,
    ),
    # NOTE: AUX1-4 were here as switches publishing the Berry-only NPAux<n>
    # command. They moved to register-driven "aux<n>_mode" select entities
    # (auto/on/off) plus read-only "aux<n>" binary sensors, removing the Berry
    # extension requirement. See select.py / binary_sensor.py.
)


@dataclass(frozen=True, kw_only=True)
class NeoPoolRegisterSwitchEntityDescription(SwitchEntityDescription):
    """Describes a NeoPool config-register switch (state read via NPRead)."""

    register: int
    # SENSOR JSON paths that must all be present for the entity to be available
    # (mirrors how the relay binary sensors self-gate on key presence).
    gating_paths: tuple[str, ...]


REGISTER_SWITCH_DESCRIPTIONS: tuple[NeoPoolRegisterSwitchEntityDescription, ...] = (
    NeoPoolRegisterSwitchEntityDescription(
        key="uv_mode",
        translation_key="uv_mode",
        name="UV Mode",
        register=REG_UV_MODE,
        gating_paths=(JSON_PATH_RELAY_UV,),
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolRegisterSwitchEntityDescription(
        key="climate_mode",
        translation_key="climate_mode",
        name="Climate Mode",
        register=REG_CLIMA_ONOFF,
        gating_paths=(JSON_PATH_RELAY_HEATING, JSON_PATH_TEMPERATURE),
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolRegisterSwitchEntityDescription(
        key="smart_antifreeze",
        translation_key="smart_antifreeze",
        name="Smart Antifreeze",
        register=REG_SMART_ANTI_FREEZE,
        gating_paths=(JSON_PATH_TEMPERATURE,),
        entity_category=EntityCategory.CONFIG,
    ),
)


@dataclass(frozen=True, kw_only=True)
class NeoPoolRegisterBitSwitchEntityDescription(NeoPoolRegisterSwitchEntityDescription):
    """A config-register switch that toggles a single bit (read-modify-write)."""

    bit_mask: int


REGISTER_BIT_SWITCH_DESCRIPTIONS: tuple[NeoPoolRegisterBitSwitchEntityDescription, ...] = (
    NeoPoolRegisterBitSwitchEntityDescription(
        key="hydro_cover_reduction",
        translation_key="hydro_cover_reduction",
        name="Hydrolysis Cover Reduction",
        register=REG_HIDRO_COVER_ENABLE,
        bit_mask=MASK_HIDRO_COVER_ENABLE,
        gating_paths=(JSON_PATH_HYDROLYSIS_DATA,),
        entity_category=EntityCategory.CONFIG,
    ),
    NeoPoolRegisterBitSwitchEntityDescription(
        key="hydro_temp_shutdown",
        translation_key="hydro_temp_shutdown",
        name="Hydrolysis Temperature Shutdown",
        register=REG_HIDRO_COVER_ENABLE,
        bit_mask=MASK_HIDRO_TEMP_SHUTDOWN_ENABLE,
        gating_paths=(JSON_PATH_HYDROLYSIS_DATA, JSON_PATH_TEMPERATURE),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool switches based on a config entry."""
    _LOGGER.debug("Setting up NeoPool switches")

    switches: list[SwitchEntity] = [
        NeoPoolSwitch(entry, description) for description in SWITCH_DESCRIPTIONS
    ]
    switches.append(NeoPoolAutoTimeSyncSwitch(entry))
    switches.extend(
        NeoPoolRegisterSwitch(entry, description) for description in REGISTER_SWITCH_DESCRIPTIONS
    )
    switches.extend(
        NeoPoolRegisterBitSwitch(entry, description)
        for description in REGISTER_BIT_SWITCH_DESCRIPTIONS
    )

    async_add_entities(switches)
    _LOGGER.info("Added %d NeoPool switches", len(switches))


class NeoPoolSwitch(NeoPoolMQTTEntity, SwitchEntity):
    """Representation of a NeoPool switch."""

    entity_description: NeoPoolSwitchEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        self._attr_is_on: bool | None = None

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
                self._attr_is_on = None
                self._attr_available = False
                self.async_write_ha_state()
                return

            self._attr_is_on = self.entity_description.value_fn(raw_value)
            self._attr_available = True
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._publish_command(
            self.entity_description.command,
            self.entity_description.payload_on,
        )
        _LOGGER.debug("Turned on switch %s", self.entity_description.key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._publish_command(
            self.entity_description.command,
            self.entity_description.payload_off,
        )
        _LOGGER.debug("Turned off switch %s", self.entity_description.key)


class NeoPoolAutoTimeSyncSwitch(NeoPoolEntity, SwitchEntity, RestoreEntity):
    """HA-side toggle that keeps the controller clock synced to Home Assistant.

    This is not a device command: it only flips a flag the central SENSOR
    watch reads. When on, the watch resyncs the controller via NPTime whenever
    its clock drifts beyond the threshold. State is restored across restarts
    via RestoreEntity (deliberately kept out of entry.options to avoid
    reloading the integration on every toggle).
    """

    _attr_translation_key = "auto_time_sync"
    _attr_name = "Auto Time Sync"
    _attr_icon = "mdi:clock-sync-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, config_entry: NeoPoolConfigEntry) -> None:
        """Initialize the auto time-sync switch."""
        super().__init__(config_entry, "auto_time_sync")
        # Pure HA-side setting: always operable, no device availability gating.
        self._attr_available = True
        self._attr_is_on = config_entry.runtime_data.auto_time_sync

    async def async_added_to_hass(self) -> None:
        """Restore the last known on/off state across restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            is_on = last_state.state == STATE_ON
            self._attr_is_on = is_on
            self._config_entry.runtime_data.auto_time_sync = is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto time-sync."""
        self._attr_is_on = True
        self._config_entry.runtime_data.auto_time_sync = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto time-sync."""
        self._attr_is_on = False
        self._config_entry.runtime_data.auto_time_sync = False
        self.async_write_ha_state()


class NeoPoolRegisterSwitch(NeoPoolMQTTEntity, SwitchEntity):
    """A switch backed by a config register read via NPRead / written via NPWrite.

    State lives in runtime_data.register_state (populated by the startup NPRead
    and kept current by the write-ACK). Availability self-gates on the presence
    of the configured SENSOR keys, like the relay binary sensors.
    """

    entity_description: NeoPoolRegisterSwitchEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolRegisterSwitchEntityDescription,
    ) -> None:
        """Initialize the register-backed switch."""
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
    def is_on(self) -> bool | None:
        """Return True if the register value is 1."""
        value = self._register_value
        return None if value is None else value == 1

    @property
    def available(self) -> bool:
        """Available when online, gating keys present, and a value is cached."""
        return super().available and self._gating_ok and self._register_value is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (write 1)."""
        await self._write_register(self.entity_description.register, 1)
        self._config_entry.runtime_data.register_state[self.entity_description.register] = 1
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (write 0)."""
        await self._write_register(self.entity_description.register, 0)
        self._config_entry.runtime_data.register_state[self.entity_description.register] = 0
        self.async_write_ha_state()


class NeoPoolRegisterBitSwitch(NeoPoolRegisterSwitch):
    """A switch toggling a single bit of a shared config register.

    Reuses the register-switch subscription/gating/availability logic but reads
    and writes a single bit via read-modify-write so the sibling field in the
    same register (e.g. the temperature-shutdown bit) is preserved.
    """

    entity_description: NeoPoolRegisterBitSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if the entity's bit is set."""
        value = self._register_value
        return None if value is None else bool(value & self.entity_description.bit_mask)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the entity's bit (preserving the rest of the register)."""
        await self._set_bit(state=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the entity's bit (preserving the rest of the register)."""
        await self._set_bit(state=False)

    async def _set_bit(self, *, state: bool) -> None:
        """Read-modify-write the single bit; no-op if the value isn't cached."""
        current = self._register_value
        if current is None:
            # Entity is unavailable without a cached value; guard against
            # clobbering the sibling field on a blind write.
            return
        mask = self.entity_description.bit_mask
        new_value = current | mask if state else current & ~mask
        await self._write_register(self.entity_description.register, new_value)
        self._config_entry.runtime_data.register_state[self.entity_description.register] = new_value
        self.async_write_ha_state()
