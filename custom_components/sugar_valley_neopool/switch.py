"""Switch platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback

from .const import CMD_AUX1, CMD_AUX2, CMD_AUX3, CMD_AUX4, CMD_FILTRATION, CMD_LIGHT
from .entity import NeoPoolMQTTEntity
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
        json_path="NeoPool.Filtration.State",
        command=CMD_FILTRATION,
    ),
    NeoPoolSwitchEntityDescription(
        key="light",
        translation_key="light",
        name="Light",
        json_path="NeoPool.Light",
        command=CMD_LIGHT,
    ),
    NeoPoolSwitchEntityDescription(
        key="aux1",
        translation_key="aux1",
        name="AUX1",
        json_path="NeoPool.Relay.Aux.0",
        command=CMD_AUX1,
    ),
    NeoPoolSwitchEntityDescription(
        key="aux2",
        translation_key="aux2",
        name="AUX2",
        json_path="NeoPool.Relay.Aux.1",
        command=CMD_AUX2,
    ),
    NeoPoolSwitchEntityDescription(
        key="aux3",
        translation_key="aux3",
        name="AUX3",
        json_path="NeoPool.Relay.Aux.2",
        command=CMD_AUX3,
    ),
    NeoPoolSwitchEntityDescription(
        key="aux4",
        translation_key="aux4",
        name="AUX4",
        json_path="NeoPool.Relay.Aux.3",
        command=CMD_AUX4,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool switches based on a config entry."""
    _LOGGER.debug("Setting up NeoPool switches")

    switches = [NeoPoolSwitch(entry, description) for description in SWITCH_DESCRIPTIONS]

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
        super().__init__(config_entry, description.key, "switch")
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

            # Handle array access in JSON path
            json_path = self.entity_description.json_path
            if ".Aux." in json_path and json_path[-1].isdigit():
                base_path = json_path.rsplit(".", 1)[0]
                index = int(json_path.rsplit(".", 1)[1])
                array_value = get_nested_value(payload, base_path)
                if isinstance(array_value, list) and len(array_value) > index:
                    raw_value = array_value[index]
                else:
                    return
            else:
                raw_value = get_nested_value(payload, json_path)

            if raw_value is None:
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
