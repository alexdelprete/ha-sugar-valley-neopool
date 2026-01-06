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
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant, callback

from .const import CMD_HYDROLYSIS, CMD_PH_MAX, CMD_PH_MIN, CMD_REDOX
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
        json_path="NeoPool.pH.Min",
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
        json_path="NeoPool.pH.Max",
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
        json_path="NeoPool.Redox.Setpoint",
        command=CMD_REDOX,
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
        json_path="NeoPool.Hydrolysis.Percent.Setpoint",
        command=CMD_HYDROLYSIS,
        command_template="{value} %",  # NeoPool expects "50 %" format
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool numbers based on a config entry."""
    _LOGGER.debug("Setting up NeoPool numbers")

    numbers = [NeoPoolNumber(entry, description) for description in NUMBER_DESCRIPTIONS]

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
        super().__init__(config_entry, description.key, "number")
        self.entity_description = description
        self._attr_native_value: float | None = None

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
