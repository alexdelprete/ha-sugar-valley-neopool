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
    BOOST_MODE_MAP,
    FILTRATION_MODE_MAP,
    FILTRATION_SPEED_MAP,
    HYDROLYSIS_STATE_MAP,
    JSON_PATH_CHLORINE_DATA,
    JSON_PATH_CONDUCTIVITY_DATA,
    JSON_PATH_CONNECTION_NOERROR,
    JSON_PATH_CONNECTION_NORESPONSE,
    JSON_PATH_CONNECTION_OUTOFRANGE,
    JSON_PATH_CONNECTION_REQUESTS,
    JSON_PATH_FILTRATION_MODE,
    JSON_PATH_FILTRATION_SPEED,
    JSON_PATH_HYDROLYSIS_BOOST,
    JSON_PATH_HYDROLYSIS_DATA,
    JSON_PATH_HYDROLYSIS_MAX,
    JSON_PATH_HYDROLYSIS_PERCENT,
    JSON_PATH_HYDROLYSIS_RUNTIME_CHANGES,
    JSON_PATH_HYDROLYSIS_RUNTIME_PART,
    JSON_PATH_HYDROLYSIS_RUNTIME_POL1,
    JSON_PATH_HYDROLYSIS_RUNTIME_POL2,
    JSON_PATH_HYDROLYSIS_RUNTIME_TOTAL,
    JSON_PATH_HYDROLYSIS_SETPOINT_GH,
    JSON_PATH_HYDROLYSIS_STATE,
    JSON_PATH_HYDROLYSIS_UNIT,
    JSON_PATH_IONIZATION_DATA,
    JSON_PATH_PH_DATA,
    JSON_PATH_PH_PUMP,
    JSON_PATH_PH_STATE,
    JSON_PATH_POWERUNIT_4MA,
    JSON_PATH_POWERUNIT_5V,
    JSON_PATH_POWERUNIT_12V,
    JSON_PATH_POWERUNIT_24V,
    JSON_PATH_POWERUNIT_NODEID,
    JSON_PATH_POWERUNIT_VERSION,
    JSON_PATH_REDOX_DATA,
    JSON_PATH_TEMPERATURE,
    JSON_PATH_TIME,
    JSON_PATH_TYPE,
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
    # When set, called with the full SENSOR payload to compute the value.
    # Returning None marks the sensor unavailable. Takes precedence over value_fn.
    # json_path is still used for the initial availability gate.
    payload_fn: Callable[[dict[str, Any]], Any] | None = None


def _hydrolysis_percent_fn(payload: dict[str, Any]) -> float | None:
    """Compute hydrolysis production percent.

    Tasmota emits Hydrolysis.Data in the controller's configured unit (% or g/h),
    and a Percent.Data sub-object only from firmware >= Nov 2023 (PR #19924) using
    integer math that truncates small values. Compute directly from Data/Unit/Max
    so this works on older firmware too.
    """
    data = safe_float(get_nested_value(payload, JSON_PATH_HYDROLYSIS_DATA), None)
    if data is None:
        return None
    unit = get_nested_value(payload, JSON_PATH_HYDROLYSIS_UNIT)
    if unit == "%":
        return round(data, 0)
    max_val = safe_float(get_nested_value(payload, JSON_PATH_HYDROLYSIS_MAX), None)
    if max_val and max_val > 0:
        return round(data * 100.0 / max_val, 0)
    fallback = safe_float(get_nested_value(payload, JSON_PATH_HYDROLYSIS_PERCENT), None)
    return None if fallback is None else round(fallback, 0)


def _hydrolysis_gh_only_fn(json_path: str) -> Callable[[dict[str, Any]], float | None]:
    """Return a payload_fn that reads `json_path` as g/h, or None when unit is %.

    Hydrolysis.Data/Setpoint/Max are emitted in the controller's configured unit.
    When the user has selected % display mode there is no way to recover g/h from
    the telemetry (Max becomes 100%), so the g/h-labeled sensors go unavailable.
    """

    def _fn(payload: dict[str, Any]) -> float | None:
        if get_nested_value(payload, JSON_PATH_HYDROLYSIS_UNIT) != "g/h":
            return None
        value = get_nested_value(payload, json_path)
        return None if value is None else round(safe_float(value, 0), 1)

    return _fn


SENSOR_DESCRIPTIONS: tuple[NeoPoolSensorEntityDescription, ...] = (
    # System info
    NeoPoolSensorEntityDescription(
        key="system_model",
        translation_key="system_model",
        name="System Model",
        json_path=JSON_PATH_TYPE,
    ),
    NeoPoolSensorEntityDescription(
        key="controller_time",
        translation_key="controller_time",
        name="Controller Time",
        json_path=JSON_PATH_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Raw string from firmware GetDT() (e.g. "2026-05-26T14:30:00"); no
        # device_class=TIMESTAMP because the firmware string has no timezone
        # info, which would make HA reject it.
    ),
    # Temperature
    NeoPoolSensorEntityDescription(
        key="water_temperature",
        translation_key="water_temperature",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_TEMPERATURE,
        value_fn=safe_float,
    ),
    # pH sensors
    NeoPoolSensorEntityDescription(
        key="ph_data",
        translation_key="ph_data",
        name="pH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_PH_DATA,
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="ph_state",
        translation_key="ph_state",
        name="pH State",
        json_path=JSON_PATH_PH_STATE,
        value_fn=lambda x: PH_STATE_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    NeoPoolSensorEntityDescription(
        key="ph_pump",
        translation_key="ph_pump",
        name="pH Pump",
        json_path=JSON_PATH_PH_PUMP,
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
        json_path=JSON_PATH_REDOX_DATA,
        value_fn=safe_float,
    ),
    # Chlorine sensor
    NeoPoolSensorEntityDescription(
        key="chlorine_data",
        translation_key="chlorine_data",
        name="Chlorine",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_CHLORINE_DATA,
        value_fn=safe_float,
    ),
    # Hydrolysis sensors
    NeoPoolSensorEntityDescription(
        key="hydrolysis_percent",
        translation_key="hydrolysis_percent",
        name="Hydrolysis",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        # Availability is gated by Hydrolysis.Data (always present when the
        # module is active); payload_fn computes the actual percent from
        # Data/Unit/Max so it works regardless of the controller's display unit.
        json_path=JSON_PATH_HYDROLYSIS_DATA,
        payload_fn=_hydrolysis_percent_fn,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_data",
        translation_key="hydrolysis_data",
        name="Hydrolysis (g/h)",
        native_unit_of_measurement="g/h",
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_HYDROLYSIS_DATA,
        payload_fn=_hydrolysis_gh_only_fn(JSON_PATH_HYDROLYSIS_DATA),
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_setpoint_gh",
        translation_key="hydrolysis_setpoint_gh",
        name="Hydrolysis Setpoint (g/h)",
        native_unit_of_measurement="g/h",
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_HYDROLYSIS_SETPOINT_GH,
        payload_fn=_hydrolysis_gh_only_fn(JSON_PATH_HYDROLYSIS_SETPOINT_GH),
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_max",
        translation_key="hydrolysis_max",
        name="Hydrolysis Max",
        native_unit_of_measurement="g/h",
        json_path=JSON_PATH_HYDROLYSIS_MAX,
        payload_fn=_hydrolysis_gh_only_fn(JSON_PATH_HYDROLYSIS_MAX),
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_unit",
        translation_key="hydrolysis_unit",
        name="Hydrolysis Unit",
        json_path=JSON_PATH_HYDROLYSIS_UNIT,
        value_fn=lambda x: str(x) if x is not None else None,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_state",
        translation_key="hydrolysis_state",
        name="Hydrolysis State",
        json_path=JSON_PATH_HYDROLYSIS_STATE,
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
        json_path=JSON_PATH_HYDROLYSIS_RUNTIME_TOTAL,
        value_fn=parse_runtime_duration,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_runtime_part",
        translation_key="hydrolysis_runtime_part",
        name="Hydrolysis Runtime Part",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_HYDROLYSIS_RUNTIME_PART,
        value_fn=parse_runtime_duration,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_runtime_pol1",
        translation_key="hydrolysis_runtime_pol1",
        name="Hydrolysis Runtime Pol1",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_HYDROLYSIS_RUNTIME_POL1,
        value_fn=parse_runtime_duration,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_runtime_pol2",
        translation_key="hydrolysis_runtime_pol2",
        name="Hydrolysis Runtime Pol2",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_HYDROLYSIS_RUNTIME_POL2,
        value_fn=parse_runtime_duration,
    ),
    NeoPoolSensorEntityDescription(
        key="hydrolysis_polarity_changes",
        translation_key="hydrolysis_polarity_changes",
        name="Hydrolysis Polarity Changes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_HYDROLYSIS_RUNTIME_CHANGES,
        value_fn=safe_int,
    ),
    # Conductivity sensor (firmware emits flat scalar at NeoPool.Conductivity, %)
    NeoPoolSensorEntityDescription(
        key="conductivity_data",
        translation_key="conductivity_data",
        name="Conductivity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_CONDUCTIVITY_DATA,
        value_fn=safe_int,
    ),
    # Ionization sensor
    NeoPoolSensorEntityDescription(
        key="ionization_data",
        translation_key="ionization_data",
        name="Ionization",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_IONIZATION_DATA,
        value_fn=safe_float,
    ),
    # Filtration sensors
    NeoPoolSensorEntityDescription(
        key="filtration_mode",
        translation_key="filtration_mode",
        name="Filtration Mode",
        json_path=JSON_PATH_FILTRATION_MODE,
        value_fn=lambda x: FILTRATION_MODE_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    NeoPoolSensorEntityDescription(
        key="filtration_speed",
        translation_key="filtration_speed",
        name="Filtration Speed",
        json_path=JSON_PATH_FILTRATION_SPEED,
        value_fn=lambda x: FILTRATION_SPEED_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    NeoPoolSensorEntityDescription(
        key="boost_mode",
        translation_key="boost_mode",
        name="Boost Mode",
        json_path=JSON_PATH_HYDROLYSIS_BOOST,
        value_fn=lambda x: BOOST_MODE_MAP.get(safe_int(x, -1), f"Unknown ({x})"),
    ),
    # Powerunit sensors
    NeoPoolSensorEntityDescription(
        key="powerunit_version",
        translation_key="powerunit_version",
        name="Powerunit Version",
        json_path=JSON_PATH_POWERUNIT_VERSION,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_5v",
        translation_key="powerunit_5v",
        name="Powerunit 5V",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_POWERUNIT_5V,
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_12v",
        translation_key="powerunit_12v",
        name="Powerunit 12V",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_POWERUNIT_12V,
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_24v",
        translation_key="powerunit_24v",
        name="Powerunit 24-30V",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_POWERUNIT_24V,
        value_fn=safe_float,
    ),
    NeoPoolSensorEntityDescription(
        key="powerunit_4ma",
        translation_key="powerunit_4ma",
        name="Powerunit 4-20mA",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_POWERUNIT_4MA,
        value_fn=safe_float,
    ),
    # Connection diagnostics
    NeoPoolSensorEntityDescription(
        key="connection_requests",
        translation_key="connection_requests",
        name="Connection Requests",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_REQUESTS,
        value_fn=safe_int,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NeoPoolSensorEntityDescription(
        key="connection_responses",
        translation_key="connection_responses",
        name="Connection Responses",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_NOERROR,
        value_fn=safe_int,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NeoPoolSensorEntityDescription(
        key="connection_no_response",
        translation_key="connection_no_response",
        name="Connection No Response",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_NORESPONSE,
        value_fn=safe_int,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NeoPoolSensorEntityDescription(
        key="connection_out_of_range",
        translation_key="connection_out_of_range",
        name="Connection Out of Range",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_OUTOFRANGE,
        value_fn=safe_int,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Diagnostic sensors
    NeoPoolSensorEntityDescription(
        key="system_id",
        translation_key="system_id",
        name="System ID",
        json_path=JSON_PATH_POWERUNIT_NODEID,
        entity_category=EntityCategory.DIAGNOSTIC,
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

            # Extract value using JSON path (availability gate)
            raw_value = get_nested_value(payload, self.entity_description.json_path)
            if raw_value is None:
                self._attr_native_value = None
                self._attr_available = False
                self.async_write_ha_state()
                return

            # payload_fn takes precedence: it sees the full payload and may
            # return None to signal "unavailable" even when json_path resolved.
            if self.entity_description.payload_fn is not None:
                new_value = self.entity_description.payload_fn(payload)
                if new_value is None:
                    self._attr_native_value = None
                    self._attr_available = False
                    self.async_write_ha_state()
                    return
                self._attr_native_value = new_value
            elif self.entity_description.value_fn is not None:
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
