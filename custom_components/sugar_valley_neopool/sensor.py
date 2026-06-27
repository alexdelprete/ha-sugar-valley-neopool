"""Sensor platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder import (
    get_instance as recorder_get_instance,
    history as recorder_history,
)
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import connection_rate_signal
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
from .entity import NeoPoolEntity, NeoPoolMQTTEntity
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
    # Minimum seconds between recorder-visible state writes. 0 = write on every
    # SENSOR message (default). >0 = in-memory value still tracks each message
    # but async_write_ha_state() is throttled so the recorder only sees one row
    # per `min_update_interval`. First write after entity becomes available
    # always goes through immediately so users don't wait for it.
    min_update_interval: float = 0.0


@dataclass(frozen=True, kw_only=True)
class NeoPoolCumulativeSensorEntityDescription(NeoPoolSensorEntityDescription):
    """Describes a cumulative-counter sensor.

    Reads a Tasmota-RAM counter from SENSOR telemetry (which resets on
    Tasmota reboot), computes the lifetime cumulative by tracking deltas
    in memory across resets. State persists across HA restarts via
    RestoreEntity. Writes are throttled per `min_update_interval`
    (typically 3600 — once per hour, which matches HA's statistics
    aggregation granularity).
    """


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
        # Throttled to once per 5 minutes: the value changes on every
        # SENSOR telemetry tick (time always advances). Throttling caps
        # the recorder rate at ~288 rows/day regardless of TelePeriod,
        # while keeping the entity useful as a sanity-check for the
        # controller's clock and for verifying the Sync Controller Time
        # button worked.
        min_update_interval=300.0,
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
    # Chlorine sensor — disabled by default; re-enabled by
    # _disable_unavailable_module_entities when Modules.Chlorine == 1
    NeoPoolSensorEntityDescription(
        key="chlorine_data",
        translation_key="chlorine_data",
        name="Chlorine",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_CHLORINE_DATA,
        value_fn=safe_float,
        entity_registry_enabled_default=False,
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
    # Disabled by default; re-enabled when Modules.Conductivity == 1
    NeoPoolSensorEntityDescription(
        key="conductivity_data",
        translation_key="conductivity_data",
        name="Conductivity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_CONDUCTIVITY_DATA,
        value_fn=safe_int,
        entity_registry_enabled_default=False,
    ),
    # Ionization sensor — disabled by default; re-enabled when Modules.Ionization == 1
    NeoPoolSensorEntityDescription(
        key="ionization_data",
        translation_key="ionization_data",
        name="Ionization",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        json_path=JSON_PATH_IONIZATION_DATA,
        value_fn=safe_float,
        entity_registry_enabled_default=False,
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
    # Connection diagnostics — lifetime cumulative counters.
    # The underlying Tasmota counters reset on every Tasmota reboot, so each
    # of these entities tracks the cumulative across resets in memory (with
    # state restored via RestoreEntity on HA restart). Writes are throttled
    # to once per hour, which matches HA's statistics aggregation granularity
    # and keeps recorder spam minimal.
    NeoPoolCumulativeSensorEntityDescription(
        key="connection_requests",
        translation_key="connection_requests",
        name="Connection Requests",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_REQUESTS,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_update_interval=3600.0,
    ),
    NeoPoolCumulativeSensorEntityDescription(
        key="connection_responses",
        translation_key="connection_responses",
        name="Connection Responses",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_NOERROR,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_update_interval=3600.0,
    ),
    NeoPoolCumulativeSensorEntityDescription(
        key="connection_no_response",
        translation_key="connection_no_response",
        name="Connection No Response",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_NORESPONSE,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_update_interval=3600.0,
    ),
    NeoPoolCumulativeSensorEntityDescription(
        key="connection_out_of_range",
        translation_key="connection_out_of_range",
        name="Connection Out of Range",
        state_class=SensorStateClass.TOTAL_INCREASING,
        json_path=JSON_PATH_CONNECTION_OUTOFRANGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_update_interval=3600.0,
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

    sensors: list[SensorEntity] = []
    for description in SENSOR_DESCRIPTIONS:
        if isinstance(description, NeoPoolCumulativeSensorEntityDescription):
            sensors.append(NeoPoolCumulativeSensor(entry, description))
        else:
            sensors.append(NeoPoolSensor(entry, description))

    # Connection error-rate sensor — sliding window, no JSON path of its own.
    # Reads from the shared ConnectionRateTracker in runtime_data.
    sensors.append(NeoPoolConnectionRateSensor(entry))

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
        # Throttle bookkeeping: timestamp of the last async_write_ha_state()
        # call. None means "no write yet" — first write goes through
        # immediately so users see data without waiting for the throttle
        # window to elapse.
        self._last_write_ts: float | None = None

    def _should_write_now(self) -> bool:
        """Return True if we should call async_write_ha_state() now.

        Honours `min_update_interval` on the entity description. First write
        always passes through; subsequent writes are throttled.
        """
        interval = self.entity_description.min_update_interval
        if interval <= 0 or self._last_write_ts is None:
            return True
        now = dt_util.utcnow().timestamp()
        return (now - self._last_write_ts) >= interval

    def _record_write(self) -> None:
        """Mark a write as having just happened (for throttle bookkeeping)."""
        self._last_write_ts = dt_util.utcnow().timestamp()

    def _compute_value(self, payload: dict[str, Any], raw_value: Any) -> Any:
        """Compute the entity's native value from the payload.

        Override in subclasses to add custom logic (e.g. cumulative deltas).
        Returning None signals "unavailable".
        """
        if self.entity_description.payload_fn is not None:
            return self.entity_description.payload_fn(payload)
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(raw_value)
        return raw_value

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
                # Becoming-unavailable resets the throttle so the next available
                # update goes through immediately rather than being silenced.
                self._last_write_ts = None
                return

            new_value = self._compute_value(payload, raw_value)
            if new_value is None:
                # payload_fn / cumulative logic signalled "unavailable"
                self._attr_native_value = None
                self._attr_available = False
                self.async_write_ha_state()
                self._last_write_ts = None
                return

            self._attr_native_value = new_value
            self._attr_available = True
            if self._should_write_now():
                self.async_write_ha_state()
                self._record_write()

        await self._subscribe_topic(sensor_topic, message_received)
        _LOGGER.debug(
            "Sensor %s subscribed to %s, path: %s",
            self.entity_description.key,
            sensor_topic,
            self.entity_description.json_path,
        )


class NeoPoolCumulativeSensor(NeoPoolSensor, RestoreEntity):
    """Sensor that accumulates lifetime deltas from a Tasmota-RAM counter.

    Tasmota's connection counters (MBRequests, MBNoError, MBNoResponse,
    DataOutOfRange) reset to 0 every Tasmota reboot. This class computes
    the lifetime cumulative across resets by tracking the raw counter
    in memory: each delta (new - last) gets added to the cumulative,
    and a negative delta is treated as a Tasmota-reboot signal (the
    new value itself is the delta from 0).

    The cumulative survives HA restarts via RestoreEntity. State writes
    are throttled per `min_update_interval` so the recorder sees only
    one row per throttle window — typically once per hour, which matches
    HA's statistics aggregation granularity.
    """

    entity_description: NeoPoolCumulativeSensorEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolCumulativeSensorEntityDescription,
    ) -> None:
        """Initialize the cumulative sensor."""
        super().__init__(config_entry, description)
        self._cumulative: float = 0.0
        # The last raw (volatile) counter value seen from SENSOR. We start
        # with None so the first message just establishes the baseline
        # without folding the full Tasmota-side counter into our cumulative.
        self._last_raw: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore cumulative from prior HA session, then subscribe to SENSOR.

        Two-tier restore: first try RestoreEntity (works whenever the entity
        was previously a RestoreEntity at shutdown — i.e. all post-v1.1.0
        restarts). If that returns nothing usable, fall back to querying
        the recorder for the most recent state of this entity_id. The
        fallback catches the v1.0.x → v1.1.0 upgrade where the prior
        instance was NOT a RestoreEntity, so the restore-state cache
        doesn't have anything to give us.
        """
        # Tier 1: RestoreEntity (the fast path, also the common path)
        last_state = await self.async_get_last_state()
        restored_value = self._extract_float_state(last_state)

        # Tier 2: recorder fallback for pre-RestoreEntity prior instances
        if restored_value is None:
            restored_value = await self._restore_from_recorder()

        if restored_value is not None:
            self._cumulative = restored_value
            _LOGGER.debug("Cumulative entity %s restored to %s", self.entity_id, restored_value)
        self._attr_native_value = self._cumulative
        await super().async_added_to_hass()

    @staticmethod
    def _extract_float_state(state: Any) -> float | None:
        """Return state.state as float, or None if missing / non-numeric."""
        if state is None or state.state in (None, "", "unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except TypeError, ValueError:
            return None

    async def _restore_from_recorder(self) -> float | None:
        """Query the recorder for the most recent state of this entity_id.

        Used when RestoreEntity returns nothing — typically because the
        previous instance was a different class without the RestoreEntity
        mixin (e.g. v1.0.x → v1.1.0 upgrade where the entity used to be
        a plain NeoPoolSensor). Returns None if the recorder integration
        isn't loaded, the entity has no history, or the recorded state
        isn't numeric.
        """
        if "recorder" not in self.hass.config.components:
            return None

        try:
            states = await recorder_get_instance(self.hass).async_add_executor_job(
                recorder_history.get_last_state_changes,
                self.hass,
                1,
                self.entity_id,
            )
        except Exception as err:  # noqa: BLE001 — defensive, recorder API may raise
            _LOGGER.debug("Recorder fallback for %s failed: %s", self.entity_id, err)
            return None

        if not states or self.entity_id not in states:
            return None
        entity_states = states[self.entity_id]
        if not entity_states:
            return None
        value = self._extract_float_state(entity_states[-1])
        if value is not None:
            _LOGGER.warning(
                "Restored cumulative for %s from recorder (RestoreEntity had "
                "nothing — likely a v1.0.x → v1.1.0 upgrade): %s",
                self.entity_id,
                value,
            )
        return value

    def _compute_value(self, payload: dict[str, Any], raw_value: Any) -> Any:
        """Update the cumulative with the delta vs last raw value."""
        current = safe_float(raw_value, None)
        if current is None:
            return None

        if self._last_raw is None:
            # First sample after install or HA restart — establish baseline
            # without folding the full Tasmota-side counter into the
            # cumulative. The cumulative stays at whatever RestoreEntity
            # restored (or 0).
            self._last_raw = current
            return self._cumulative

        if current < self._last_raw:
            # Negative delta → Tasmota rebooted. The current value is itself
            # the delta from 0 (counts accumulated since the reboot).
            delta = current
        else:
            delta = current - self._last_raw
        self._last_raw = current
        self._cumulative += delta
        return self._cumulative


class NeoPoolConnectionRateSensor(NeoPoolEntity, SensorEntity):
    """Sliding-window error-rate sensor for the Modbus connection.

    Reads from the shared `ConnectionRateTracker` in `runtime_data` which
    the integration's central SENSOR watch feeds on every telemetry tick.
    Reacts via a dispatcher signal, so we don't open a second MQTT
    subscription just to compute the rate.
    """

    _attr_should_poll = False
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connection_error_rate"
    _attr_icon = "mdi:percent"
    _attr_suggested_display_precision = 2

    def __init__(self, config_entry: NeoPoolConfigEntry) -> None:
        """Initialize the rate sensor."""
        super().__init__(config_entry, "connection_error_rate")
        self._attr_name = "Connection Error Rate"
        self._attr_native_value: float | None = None
        # Always available — the rate is undefined (None) until the window
        # has accumulated >=2 samples, but the entity itself is live.
        self._attr_available = True

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
        """Pull the latest rate from the shared tracker and write state."""
        tracker = self._config_entry.runtime_data.connection_rate_tracker
        if tracker is None:
            return
        self._attr_native_value = tracker.rate
        self.async_write_ha_state()
