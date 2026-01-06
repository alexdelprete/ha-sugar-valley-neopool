"""Binary sensor platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback

from .entity import NeoPoolMQTTEntity
from .helpers import bit_to_bool, get_nested_value, parse_json_payload

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components import mqtt
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a NeoPool binary sensor entity."""

    json_path: str
    value_fn: Callable[[Any], bool | None] = bit_to_bool
    invert: bool = False


BINARY_SENSOR_DESCRIPTIONS: tuple[NeoPoolBinarySensorEntityDescription, ...] = (
    # Module presence sensors
    NeoPoolBinarySensorEntityDescription(
        key="modules_ph",
        translation_key="modules_ph",
        name="pH Module",
        icon="mdi:ph",
        json_path="NeoPool.Modules.pH",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_redox",
        translation_key="modules_redox",
        name="Redox Module",
        icon="mdi:flash",
        json_path="NeoPool.Modules.Redox",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_hydrolysis",
        translation_key="modules_hydrolysis",
        name="Hydrolysis Module",
        icon="mdi:water-opacity",
        json_path="NeoPool.Modules.Hydrolysis",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_chlorine",
        translation_key="modules_chlorine",
        name="Chlorine Module",
        icon="mdi:beaker",
        json_path="NeoPool.Modules.Chlorine",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_conductivity",
        translation_key="modules_conductivity",
        name="Conductivity Module",
        json_path="NeoPool.Modules.Conductivity",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_ionization",
        translation_key="modules_ionization",
        name="Ionization Module",
        icon="mdi:atom",
        json_path="NeoPool.Modules.Ionization",
    ),
    # Relay state sensors
    NeoPoolBinarySensorEntityDescription(
        key="relay_ph_state",
        translation_key="relay_ph_state",
        name="Relay pH State",
        icon="mdi:electric-switch",
        json_path="NeoPool.Relay.State.0",
        value_fn=lambda x: bit_to_bool(x)
        if isinstance(x, (str, int))
        else (bit_to_bool(x[0]) if isinstance(x, list) and len(x) > 0 else None),
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_filtration_state",
        translation_key="relay_filtration_state",
        name="Relay Filtration State",
        device_class=BinarySensorDeviceClass.RUNNING,
        json_path="NeoPool.Relay.State.1",
        value_fn=lambda x: bit_to_bool(x)
        if isinstance(x, (str, int))
        else (bit_to_bool(x[1]) if isinstance(x, list) and len(x) > 1 else None),
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_light_state",
        translation_key="relay_light_state",
        name="Relay Light State",
        device_class=BinarySensorDeviceClass.LIGHT,
        json_path="NeoPool.Relay.State.2",
        value_fn=lambda x: bit_to_bool(x)
        if isinstance(x, (str, int))
        else (bit_to_bool(x[2]) if isinstance(x, list) and len(x) > 2 else None),
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_acid_state",
        translation_key="relay_acid_state",
        name="Relay Acid State",
        icon="mdi:flask",
        json_path="NeoPool.Relay.Acid",
    ),
    # Flow and tank level sensors
    NeoPoolBinarySensorEntityDescription(
        key="ph_fl1",
        translation_key="ph_fl1",
        name="pH FL1",
        icon="mdi:waves-arrow-right",
        json_path="NeoPool.pH.FL1",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_fl1",
        translation_key="hydrolysis_fl1",
        name="Hydrolysis FL1",
        icon="mdi:waves-arrow-right",
        json_path="NeoPool.Hydrolysis.FL1",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_water_flow",
        translation_key="hydrolysis_water_flow",
        name="Water Flow",
        device_class=BinarySensorDeviceClass.RUNNING,
        json_path="NeoPool.Hydrolysis.FL1",
        invert=True,  # FL1=0 means flow is OK, FL1=1 means no flow
    ),
    NeoPoolBinarySensorEntityDescription(
        key="ph_tank_level",
        translation_key="ph_tank_level",
        name="pH Tank Level Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        json_path="NeoPool.pH.Tank",
        invert=True,  # Tank=0 means low, Tank=1 means OK
    ),
    NeoPoolBinarySensorEntityDescription(
        key="redox_tank_level",
        translation_key="redox_tank_level",
        name="Redox Tank Level Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        json_path="NeoPool.Redox.Tank",
        invert=True,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_cover",
        translation_key="hydrolysis_cover",
        name="Hydrolysis Cover",
        icon="mdi:pool",
        json_path="NeoPool.Hydrolysis.Cover",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_low_production",
        translation_key="hydrolysis_low_production",
        name="Hydrolysis Low Production",
        device_class=BinarySensorDeviceClass.PROBLEM,
        json_path="NeoPool.Hydrolysis.Low",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool binary sensors based on a config entry."""
    _LOGGER.debug("Setting up NeoPool binary sensors")

    sensors = [
        NeoPoolBinarySensor(entry, description) for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(sensors)
    _LOGGER.info("Added %d NeoPool binary sensors", len(sensors))


class NeoPoolBinarySensor(NeoPoolMQTTEntity, BinarySensorEntity):
    """Representation of a NeoPool binary sensor."""

    entity_description: NeoPoolBinarySensorEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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

            # Handle array access in JSON path (e.g., "NeoPool.Relay.State.0")
            json_path = self.entity_description.json_path
            if ".State." in json_path and json_path[-1].isdigit():
                # Extract array path and index
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

            # Apply transformation function
            is_on = self.entity_description.value_fn(raw_value)

            # Apply inversion if needed
            if is_on is not None and self.entity_description.invert:
                is_on = not is_on

            self._attr_is_on = is_on
            self._attr_available = True
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)
        _LOGGER.debug(
            "Binary sensor %s subscribed to %s, path: %s",
            self.entity_description.key,
            sensor_topic,
            self.entity_description.json_path,
        )
