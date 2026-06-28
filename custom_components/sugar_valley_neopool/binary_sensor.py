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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from . import connection_rate_signal
from .const import (
    CONF_CONNECTION_ERROR_RATE_THRESHOLD,
    DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD,
    JSON_PATH_HYDROLYSIS_COVER,
    JSON_PATH_HYDROLYSIS_FL1,
    JSON_PATH_HYDROLYSIS_LOW,
    JSON_PATH_HYDROLYSIS_REDOX,
    JSON_PATH_MODULES_CHLORINE,
    JSON_PATH_MODULES_CONDUCTIVITY,
    JSON_PATH_MODULES_HYDROLYSIS,
    JSON_PATH_MODULES_IONIZATION,
    JSON_PATH_MODULES_PH,
    JSON_PATH_MODULES_REDOX,
    JSON_PATH_PH_FL1,
    JSON_PATH_PH_TANK,
    JSON_PATH_REDOX_TANK,
    JSON_PATH_RELAY_ACID,
    JSON_PATH_RELAY_AUX,
    JSON_PATH_RELAY_BASE,
    JSON_PATH_RELAY_CHLORINE,
    JSON_PATH_RELAY_CONDUCTIVITY,
    JSON_PATH_RELAY_HEATING,
    JSON_PATH_RELAY_REDOX,
    JSON_PATH_RELAY_UV,
    JSON_PATH_RELAY_VALVE,
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
        json_path=JSON_PATH_MODULES_PH,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_redox",
        translation_key="modules_redox",
        name="Redox Module",
        json_path=JSON_PATH_MODULES_REDOX,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_hydrolysis",
        translation_key="modules_hydrolysis",
        name="Hydrolysis Module",
        json_path=JSON_PATH_MODULES_HYDROLYSIS,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_chlorine",
        translation_key="modules_chlorine",
        name="Chlorine Module",
        json_path=JSON_PATH_MODULES_CHLORINE,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_conductivity",
        translation_key="modules_conductivity",
        name="Conductivity Module",
        json_path=JSON_PATH_MODULES_CONDUCTIVITY,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="modules_ionization",
        translation_key="modules_ionization",
        name="Ionization Module",
        json_path=JSON_PATH_MODULES_IONIZATION,
    ),
    # Named relay state sensors (functional state regardless of physical relay assignment)
    # Disabled by default — only appear when the function is assigned to a relay
    NeoPoolBinarySensorEntityDescription(
        key="relay_acid_state",
        translation_key="relay_acid_state",
        name="Relay Acid State",
        json_path=JSON_PATH_RELAY_ACID,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_base_state",
        translation_key="relay_base_state",
        name="Relay Base State",
        json_path=JSON_PATH_RELAY_BASE,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_redox_state",
        translation_key="relay_redox_state",
        name="Relay Redox State",
        json_path=JSON_PATH_RELAY_REDOX,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_chlorine_state",
        translation_key="relay_chlorine_state",
        name="Relay Chlorine State",
        json_path=JSON_PATH_RELAY_CHLORINE,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_conductivity_state",
        translation_key="relay_conductivity_state",
        name="Relay Conductivity State",
        json_path=JSON_PATH_RELAY_CONDUCTIVITY,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_heating_state",
        translation_key="relay_heating_state",
        name="Relay Heating State",
        json_path=JSON_PATH_RELAY_HEATING,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_uv_state",
        translation_key="relay_uv_state",
        name="Relay UV State",
        json_path=JSON_PATH_RELAY_UV,
        entity_registry_enabled_default=False,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="relay_valve_state",
        translation_key="relay_valve_state",
        name="Relay Valve State",
        json_path=JSON_PATH_RELAY_VALVE,
        entity_registry_enabled_default=False,
    ),
    # AUX relay physical-output state (read-only). The on/off control lives in
    # the "aux<n>_mode" select entities; these expose the live relay state,
    # which is the only way to see whether an AUX in "auto" mode is currently
    # energized. Array access into NeoPool.Relay.Aux is handled in the message
    # callback below.
    NeoPoolBinarySensorEntityDescription(
        key="aux1",
        translation_key="aux1",
        name="AUX1",
        json_path=f"{JSON_PATH_RELAY_AUX}.0",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="aux2",
        translation_key="aux2",
        name="AUX2",
        json_path=f"{JSON_PATH_RELAY_AUX}.1",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="aux3",
        translation_key="aux3",
        name="AUX3",
        json_path=f"{JSON_PATH_RELAY_AUX}.2",
    ),
    NeoPoolBinarySensorEntityDescription(
        key="aux4",
        translation_key="aux4",
        name="AUX4",
        json_path=f"{JSON_PATH_RELAY_AUX}.3",
    ),
    # Flow and tank level sensors
    NeoPoolBinarySensorEntityDescription(
        key="ph_fl1",
        translation_key="ph_fl1",
        name="pH FL1",
        json_path=JSON_PATH_PH_FL1,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_fl1",
        translation_key="hydrolysis_fl1",
        name="Hydrolysis FL1",
        json_path=JSON_PATH_HYDROLYSIS_FL1,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_water_flow",
        translation_key="hydrolysis_water_flow",
        name="Water Flow",
        device_class=BinarySensorDeviceClass.RUNNING,
        json_path=JSON_PATH_HYDROLYSIS_FL1,
        invert=True,  # FL1=0 means flow is OK, FL1=1 means no flow
    ),
    NeoPoolBinarySensorEntityDescription(
        key="ph_tank_level",
        translation_key="ph_tank_level",
        name="pH Tank Level Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        json_path=JSON_PATH_PH_TANK,
        invert=True,  # Tank=0 means low, Tank=1 means OK
    ),
    NeoPoolBinarySensorEntityDescription(
        key="redox_tank_level",
        translation_key="redox_tank_level",
        name="Redox Tank Level Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        json_path=JSON_PATH_REDOX_TANK,
        invert=True,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_cover",
        translation_key="hydrolysis_cover",
        name="Hydrolysis Cover",
        json_path=JSON_PATH_HYDROLYSIS_COVER,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_low_production",
        translation_key="hydrolysis_low_production",
        name="Hydrolysis Low Production",
        device_class=BinarySensorDeviceClass.PROBLEM,
        json_path=JSON_PATH_HYDROLYSIS_LOW,
    ),
    NeoPoolBinarySensorEntityDescription(
        key="hydrolysis_redox_controlled",
        translation_key="hydrolysis_redox_controlled",
        name="Hydrolysis Redox Controlled",
        json_path=JSON_PATH_HYDROLYSIS_REDOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool binary sensors based on a config entry."""
    _LOGGER.debug("Setting up NeoPool binary sensors")

    sensors: list[BinarySensorEntity] = [
        NeoPoolBinarySensor(entry, description) for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    # Connection-problem binary sensor — driven by the shared rate tracker,
    # configurable threshold via options flow.
    sensors.append(NeoPoolConnectionProblemBinarySensor(entry))

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

            # Handle array access in JSON path (e.g., "NeoPool.Relay.State.0"
            # or "NeoPool.Relay.Aux.0").
            json_path = self.entity_description.json_path
            if (".State." in json_path or ".Aux." in json_path) and json_path[-1].isdigit():
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
                self._attr_is_on = None
                self._attr_available = False
                self.async_write_ha_state()
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


class NeoPoolConnectionProblemBinarySensor(NeoPoolEntity, BinarySensorEntity):
    """Binary sensor that turns ON when the rolling error rate exceeds the threshold.

    Reads from the shared `ConnectionRateTracker` in `runtime_data` via the
    rate-updated dispatcher signal — same source the rate sensor uses, so
    both stay consistent.

    Threshold is read from the options entry (`CONF_CONNECTION_ERROR_RATE_THRESHOLD`,
    defaulting to `DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD`). Options changes
    auto-reload the integration via `OptionsFlowWithReload`, so the threshold
    is picked up on next setup.
    """

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connection_problem"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, config_entry: NeoPoolConfigEntry) -> None:
        """Initialize the problem binary sensor."""
        super().__init__(config_entry, "connection_problem")
        self._attr_name = "Connection Problem"
        self._attr_is_on: bool | None = None
        self._attr_available = True
        self._threshold: float = float(
            config_entry.options.get(
                CONF_CONNECTION_ERROR_RATE_THRESHOLD,
                DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD,
            )
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to the rate-updated dispatcher signal."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                connection_rate_signal(self._config_entry),
                self._handle_rate_update,
            )
        )

    @callback
    def _handle_rate_update(self) -> None:
        """Pull the latest rate from the shared tracker and update is_on."""
        tracker = self._config_entry.runtime_data.connection_rate_tracker
        if tracker is None:
            return
        rate = tracker.rate
        if rate is None:
            # Insufficient samples / reboot detected — leave previous state
            # unchanged. The next valid rate will flip the state correctly.
            return
        self._attr_is_on = rate > self._threshold
        self.async_write_ha_state()
