"""Select platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback

from .const import (
    BOOST_MODE_MAP,
    CMD_BOOST,
    CMD_FILTRATION_MODE,
    CMD_FILTRATION_SPEED,
    FILTRATION_MODE_MAP,
    FILTRATION_SPEED_MAP,
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
        json_path="NeoPool.Filtration.Mode",
        command=CMD_FILTRATION_MODE,
        options_map=FILTRATION_MODE_MAP,
        options=list(FILTRATION_MODE_MAP.values()),
    ),
    NeoPoolSelectEntityDescription(
        key="filtration_speed",
        translation_key="filtration_speed",
        name="Filtration Speed",
        json_path="NeoPool.Filtration.Speed",
        command=CMD_FILTRATION_SPEED,
        options_map=FILTRATION_SPEED_MAP,
        options=list(FILTRATION_SPEED_MAP.values()),
    ),
    NeoPoolSelectEntityDescription(
        key="boost_mode",
        translation_key="boost_mode",
        name="Boost Mode",
        json_path="NeoPool.Hydrolysis.Boost",
        command=CMD_BOOST,
        options_map=BOOST_MODE_MAP,
        options=list(BOOST_MODE_MAP.values()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool selects based on a config entry."""
    _LOGGER.debug("Setting up NeoPool selects")

    selects = [NeoPoolSelect(entry, description) for description in SELECT_DESCRIPTIONS]

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
        super().__init__(config_entry, description.key, "select")
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
