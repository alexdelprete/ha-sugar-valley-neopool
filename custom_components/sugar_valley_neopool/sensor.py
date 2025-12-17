"""Sensor platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory

from .const import (
    FILTRATION_MODE_MAP,
    FILTRATION_SPEED_MAP,
    HYDROLYSIS_STATE_MAP,
    PH_PUMP_MAP,
    PH_STATE_MAP,
)
from .entity import NeoPoolMQTTEntity
from .helpers import (
    get_nested_value,
    parse_json_payload,
    parse_runtime_duration,
    safe_float,
    safe_int,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.components import mqtt
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolSensorEntityDescription(SensorEntityDescription):
    """Describes a NeoPool sensor entity."""

    json_path: str
    value_fn: Callable[[Any], Any] | None = None


SENSOR_DESCRIPTIONS: tuple[NeoPoolSensorEntityDescription, ...] = (
    # System info
    NeoPoolSensorEntityDescription(
        key="system_model",
        translation_key="system_model",
        name="System Model",
        icon="mdi:information-outline",
        json_path="NeoPool.Type",
    ),
    # Temperature
    NeoPoolSensorEntityDescription(
        key="water_temperature",
        translation_key="water_temperature",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Temperature",
        value_fn=safe_float,
    ),
    # pH sensors
    NeoPoolSensorEntityDescription(
        key="ph_data",
        translation_key="ph_data",
        name="pH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.pH.Data",
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="ph_state",
        translation_key="ph_state",
        name="pH State",
        icon="mdi:ph",
        json_path="NeoPool.pH.State",
        value_fn=lambda x: PH_STATE_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    NeoPoolSensorEntityDescription(
        key="ph_pump",
        translation_key="ph_pump",
        name="pH Pump",
        icon="mdi:ph",
        json_path="NeoPool.pH.Pump",
        value_fn=lambda x: PH_PUMP_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    # Redox (ORP) sensors
    NeoPoolSensorEntityDescription(
        key="redox_data",
        translation_key="redox_data",
        name="Redox (ORP)",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Redox.Data",
        value_fn=safe_float,
    ),
    # Hydrolysis sensors
    NeoPoolSensorEntityDescription(
        key="hydrolysis_percent",
        translation_key="hydrolysis_percent",
        name="Hydrolysis",
        icon="mdi:water-opacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Hydrolysis.Percent.Data",
        value_fn=lambda x: round(safe_float(x, 0), 0),
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_data",
        translation_key="hydrolysis_data",
        name="Hydrolysis (g/h)",
        icon="mdi:water-opacity",
        native_unit_of_measurement="g/h",
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Hydrolysis.Data",
        value_fn=lambda x: round(safe_float(x, 0), 1),
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_state",
        translation_key="hydrolysis_state",
        name="Hydrolysis State",
        icon="mdi:water-opacity",
        json_path="NeoPool.Hydrolysis.State",
        value_fn=lambda x: HYDROLYSIS_STATE_MAP.get(str(x).upper(), f"Unknown ({x})"),
    ),
    # Hydrolysis Runtime
    NeoPoolSensorEntityDescription(
        key="hydrolysis_runtime_total",
        translation_key="hydrolysis_runtime_total",
        name="Hydrolysis Runtime Total",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path="NeoPool.Hydrolysis.Runtime.Total",
        value_fn=parse_runtime_duration,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_runtime_part",
        translation_key="hydrolysis_runtime_part",
        name="Hydrolysis Runtime Part",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Hydrolysis.Runtime.Part",
        value_fn=parse_runtime_duration,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_polarity_changes",
        translation_key="hydrolysis_polarity_changes",
        name="Hydrolysis Polarity Changes",
        icon="mdi:swap-horizontal",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path="NeoPool.Hydrolysis.Runtime.Changes",
        value_fn=safe_int,
    ),
    # Filtration sensors
    NeoPoolSensorEntityDescription(
        key="filtration_mode",
        translation_key="filtration_mode",
        name="Filtration Mode",
        icon="mdi:pump",
        json_path="NeoPool.Filtration.Mode",
        value_fn=lambda x: FILTRATION_MODE_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    NeoPoolSensorEntityDescription(
        key="filtration_speed",
        translation_key="filtration_speed",
        name="Filtration Speed",
        icon="mdi:speedometer",
        json_path="NeoPool.Filtration.Speed",
        value_fn=lambda x: FILTRATION_SPEED_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    # Powerunit sensors
    NeoPoolSensorEntityDescription(
        key="powerunit_version",
        translation_key="powerunit_version",
        name="Powerunit Version",
        icon="mdi:information-outline",
        json_path="NeoPool.Powerunit.Version",
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_5v",
        translation_key="powerunit_5v",
        name="Powerunit 5V",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Powerunit.5V",
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_12v",
        translation_key="powerunit_12v",
        name="Powerunit 12V",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Powerunit.12V",
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_24v",
        translation_key="powerunit_24v",
        name="Powerunit 24-30V",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Powerunit.24-30V",
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_4ma",
        translation_key="powerunit_4ma",
        name="Powerunit 4-20mA",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path="NeoPool.Powerunit.4-20mA",
        value_fn=safe_float,
    ),
    # Connection diagnostics
    NeoPoolSensorEntityDescription(
        key="connection_requests",
        translation_key="connection_requests",
        name="Connection Requests",
        icon="mdi:source-branch-check",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path="NeoPool.Connection.MBRequests",
        value_fn=safe_int,
        entity_registry_enabled_default=False,
    ),
    NeoPoolSensorEntityDescription(
        key="connection_responses",
        translation_key="connection_responses",
        name="Connection Responses",
        icon="mdi:source-branch-check",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path="NeoPool.Connection.MBNoError",
        value_fn=safe_int,
        entity_registry_enabled_default=False,
    ),
    NeoPoolSensorEntityDescription(
        key="connection_no_response",
        translation_key="connection_no_response",
        name="Connection No Response",
        icon="mdi:source-branch-check",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path="NeoPool.Connection.MBNoResponse",
        value_fn=safe_int,
        entity_registry_enabled_default=False,
    ),
    # Diagnostic sensors
    NeoPoolSensorEntityDescription(
        key="powerunit_nodeid",
        translation_key="powerunit_nodeid",
        name="Powerunit NodeID",
        icon="mdi:identifier",
        json_path="NeoPool.Powerunit.NodeID",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool sensors based on a config entry."""
    _LOGGER.debug("Setting up NeoPool sensors")

    sensors = [NeoPoolSensor(entry, description) for description in SENSOR_DESCRIPTIONS]

    async_add_entities(sensors)
    _LOGGER.info("Added %d NeoPool sensors", len(sensors))


class NeoPoolSensor(NeoPoolMQTTEntity, SensorEntity):
    """Representation of a NeoPool sensor."""

    entity_description: NeoPoolSensorEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        self._attr_native_value = None

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

            # Extract value using JSON path
            raw_value = get_nested_value(payload, self.entity_description.json_path)
            if raw_value is None:
                return

            # Apply transformation function if defined
            if self.entity_description.value_fn is not None:
                self._attr_native_value = self.entity_description.value_fn(raw_value)
            else:
                self._attr_native_value = raw_value

            self._attr_available = True
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)
        _LOGGER.debug(
            "Sensor %s subscribed to %s, path: %s",
            self.entity_description.key,
            sensor_topic,
            self.entity_description.json_path,
        )
