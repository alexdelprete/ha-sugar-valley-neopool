"""Constants for the NeoPool MQTT integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

# Integration identity
DOMAIN: Final = "sugar_valley_neopool"
NAME: Final = "Sugar Valley NeoPool"
VERSION: Final = "1.1.4"
MANUFACTURER: Final = "Sugar Valley"
MODEL: Final = "NeoPool Controller"
ATTRIBUTION: Final = "by @alexdelprete"
ISSUE_URL: Final = "https://github.com/alexdelprete/ha-sugar-valley-neopool/issues"

# Platforms supported
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.LIGHT,
]

# Configuration keys (data - changed via reconfigure)
CONF_DISCOVERY_PREFIX: Final = "discovery_prefix"
CONF_DEVICE_NAME: Final = "device_name"
CONF_NODEID: Final = "nodeid"
CONF_MIGRATE_YAML: Final = "migrate_yaml"
CONF_UNIQUE_ID_PREFIX: Final = "unique_id_prefix"
CONF_CONFIRM_MIGRATION: Final = "confirm_migration"

# Configuration keys (options - changed via options flow)
CONF_ENABLE_REPAIR_NOTIFICATION: Final = "enable_repair_notification"
CONF_FAILURES_THRESHOLD: Final = "failures_threshold"
CONF_RECOVERY_SCRIPT: Final = "recovery_script"
CONF_OFFLINE_TIMEOUT: Final = "offline_timeout"
CONF_CONNECTION_ERROR_RATE_THRESHOLD: Final = "connection_error_rate_threshold"
CONF_REGENERATE_ENTITY_IDS: Final = "regenerate_entity_ids"
CONF_NODEID_HASHED: Final = "nodeid_hashed"
CONF_NODEID_REAL: Final = "nodeid_real"
CONF_NODEID_MASKED: Final = "nodeid_masked"
# Pump-type override for the per-timer filtration-speed selects (Group 5).
# "auto" trusts the controller's self-report (Filtration.Speed present in SENSOR
# = variable-speed pump); "variable"/"standard" force it on/off.
CONF_PUMP_TYPE: Final = "pump_type"
PUMP_TYPE_AUTO: Final = "auto"
PUMP_TYPE_VARIABLE: Final = "variable"
PUMP_TYPE_STANDARD: Final = "standard"
PUMP_TYPE_OPTIONS: Final[tuple[str, ...]] = (
    PUMP_TYPE_AUTO,
    PUMP_TYPE_VARIABLE,
    PUMP_TYPE_STANDARD,
)
DEFAULT_PUMP_TYPE: Final = PUMP_TYPE_AUTO

# Device metadata keys (stored in runtime_data, updated from MQTT)
CONF_MANUFACTURER: Final = "manufacturer"
CONF_FW_VERSION: Final = "fw_version"

# Default values
DEFAULT_DEVICE_NAME: Final = "NeoPool"
DEFAULT_DISCOVERY_PREFIX: Final = "tele/"
DEFAULT_UNIQUE_ID_PREFIX: Final = "neopool_mqtt_"
DEFAULT_MQTT_TOPIC: Final = "SmartPool"

# Options flow defaults
DEFAULT_ENABLE_REPAIR_NOTIFICATION: Final = True
DEFAULT_FAILURES_THRESHOLD: Final = 3
DEFAULT_RECOVERY_SCRIPT: Final = ""
DEFAULT_OFFLINE_TIMEOUT: Final = 300  # 5 minutes in seconds
DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD: Final = 5.0  # percent

# Options flow validation bounds
MIN_FAILURES_THRESHOLD: Final = 1
MAX_FAILURES_THRESHOLD: Final = 10
MIN_OFFLINE_TIMEOUT: Final = 60  # 1 minute
MAX_OFFLINE_TIMEOUT: Final = 3600  # 1 hour
MIN_CONNECTION_ERROR_RATE_THRESHOLD: Final = 0.1
MAX_CONNECTION_ERROR_RATE_THRESHOLD: Final = 100.0

# Connection-rate sliding-window size (seconds). Not exposed in the UI —
# 10 minutes is a sensible default that smooths over individual poll noise
# while remaining responsive to actual connection issues.
CONNECTION_ERROR_RATE_WINDOW_SECONDS: Final = 600.0

# Auto time-sync: default state, how far the controller clock may drift from
# Home Assistant before the watch pushes an NPTime resync, and a cooldown so a
# single drift doesn't trigger repeated resyncs before the corrected time is
# echoed back in the next SENSOR message. Only acts when the auto-sync switch
# is on. 60 s drift keeps schedules accurate without resyncing on minor jitter.
DEFAULT_AUTO_TIME_SYNC: Final = False
TIME_SYNC_DRIFT_THRESHOLD_SECONDS: Final = 60
TIME_SYNC_COOLDOWN_SECONDS: Final = 300

# MQTT Topics - Tasmota NeoPool patterns
TOPIC_SENSOR: Final = "tele/{device}/SENSOR"
TOPIC_LWT: Final = "tele/{device}/LWT"
TOPIC_COMMAND: Final = "cmnd/{device}/{command}"
TOPIC_RESULT: Final = "stat/{device}/RESULT"
TOPIC_SO: Final = "stat/{device}/SO"  # Response topic for SetOption queries

# Availability payloads
PAYLOAD_ONLINE: Final = "Online"
PAYLOAD_OFFLINE: Final = "Offline"

# Device types (for grouping entities)
DEVICE_POOL: Final = "pool"
DEVICE_CONTROLLER: Final = "controller"

# pH States mapping
PH_STATE_MAP: Final[dict[int, str]] = {
    0: "No Alarm",
    1: "pH too high",
    2: "pH too low",
    3: "Pump exceeded working time",
    4: "pH high",
    5: "pH low",
    6: "Tank level low",
}

# pH Pump States
PH_PUMP_MAP: Final[dict[int, str]] = {
    0: "Control Off",
    1: "Active",
    2: "Not Active",
}

# Filtration Mode mapping
FILTRATION_MODE_MAP: Final[dict[int, str]] = {
    0: "Manual",
    1: "Auto",
    2: "Heating",
    3: "Smart",
    4: "Intelligent",
    13: "Backwash",
}

# Filtration Speed mapping
FILTRATION_SPEED_MAP: Final[dict[int, str]] = {
    1: "Slow",
    2: "Medium",
    3: "Fast",
}

# Hydrolysis State mapping
HYDROLYSIS_STATE_MAP: Final[dict[str, str]] = {
    "OFF": "Cell Inactive",
    "FLOW": "Flow Alarm",
    "POL1": "Pol1 active",
    "POL2": "Pol2 active",
}

# Boost Mode mapping
BOOST_MODE_MAP: Final[dict[int, str]] = {
    0: "Off",
    1: "On",
    2: "On (Redox)",
}

# NeoPool commands (via MQTT cmnd topic)
CMD_FILTRATION: Final = "NPFiltration"
CMD_FILTRATION_MODE: Final = "NPFiltrationmode"
CMD_FILTRATION_SPEED: Final = "NPFiltrationSpeed"
CMD_LIGHT: Final = "NPLight"
CMD_AUX1: Final = "NPAux1"
CMD_AUX2: Final = "NPAux2"
CMD_AUX3: Final = "NPAux3"
CMD_AUX4: Final = "NPAux4"
CMD_BOOST: Final = "NPBoost"
CMD_PH_MIN: Final = "NPpHMin"
CMD_PH_MAX: Final = "NPpHMax"
CMD_REDOX: Final = "NPRedox"
CMD_HYDROLYSIS: Final = "NPHydrolysis"
CMD_IONIZATION: Final = "NPIonization"
CMD_CHLORINE: Final = "NPChlorine"
CMD_TIME: Final = "NPTime"
CMD_ESCAPE: Final = "NPEscape"

# Generic register access commands (built-in Tasmota NeoPool driver commands).
# Used for registers/actions that have no dedicated NPxxx command.
CMD_NPREAD: Final = "NPRead"
CMD_NPWRITE: Final = "NPWrite"
CMD_NPWRITEL: Final = "NPWriteL"  # write 32-bit value(s) across register pairs
CMD_NPSAVE: Final = "NPSave"
# NPExec (MBF_RESTART_MODULES) commits register changes by restarting the
# controller modules. Used after timer-block / relay-mode writes (Group 4) so
# the change takes effect immediately. Built-in driver command (no Berry).
CMD_NPEXEC: Final = "NPExec"

# Tasmota SetOption157 command (used only during setup for NodeID acquisition)
CMD_SETOPTION157: Final = "SetOption157"

# Modbus register addresses for actions/settings without a dedicated NPxxx
# command. Read via NPRead, written via NPWrite. See
# docs/MODBUS_PARITY_FEATURE_PLAN.md for the full map.
# MBF_RESET_USER_COUNTERS (0x02F2): writing any value resets the hydrolysis
# cell partial/user runtime counters in one atomic controller operation.
REG_RESET_USER_COUNTERS: Final = 0x02F2

# Group 2 config registers (not present in the SENSOR payload). State is read
# on demand with NPRead and kept current by the write-ACK; values are cached in
# runtime_data.register_state. Encodings per the Sugar Valley MODBUS register
# description.
REG_HEATING_TEMP: Final = 0x0416  # heating target temperature setpoint
REG_CLIMA_ONOFF: Final = 0x0417  # climate/thermal control on/off (0/1)
REG_SMART_ANTI_FREEZE: Final = 0x041A  # smart antifreeze enable (0/1)
REG_INTELLIGENT_FILT_MIN_TIME: Final = 0x041D  # intelligent mode min minutes
REG_UV_MODE: Final = 0x0427  # UV lamp mode on/off (0/1)
REG_RELAY_ACTIVATION_DELAY: Final = 0x0433  # pH pump activation delay (seconds)

# Group 3 bit-packed hydrolysis cover registers (bit layout confirmed against
# the Sugar Valley MODBUS register description). Both the cover-reduction and
# temperature-shutdown features share these two registers, so writes must be
# read-modify-write to avoid clobbering the sibling field. Keep the cover-%
# decoding in lock-step with the companion YAML package repo (CLAUDE.md).
REG_HIDRO_COVER_ENABLE: Final = 0x042C  # bit0 cover-reduction, bit1 temp-shutdown
REG_HIDRO_COVER_REDUCTION: Final = 0x042D  # bits0-7 cover %, bits8-15 shutdown °C
MASK_HIDRO_COVER_ENABLE: Final = 0x0001  # MBMSK_HIDRO_COVER_ENABLE
MASK_HIDRO_TEMP_SHUTDOWN_ENABLE: Final = 0x0002  # MBMSK_HIDRO_TEMPERATURE_SHUTDOWN_ENABLE
SHIFT_HIDRO_COVER_REDUCTION: Final = 0  # bits 0-7
SHIFT_HIDRO_SHUTDOWN_TEMP: Final = 8  # bits 8-15

# Group 4b — register-based AUX relay control (replaces the Berry-only NPAux
# commands). Each AUX relay has a 15-register timer block; the enable/mode word
# at block-base +0 (MBV_TIMER_OFFMB_TIMER_ENABLE) selects the working mode, and
# the function word at block-base +11 (MBV_TIMER_OFFMB_TIMER_FUNCTION) binds the
# timer to its physical relay. Addresses verified against @curzon01's
# xsns_83_neopool.ino (primary) and svasek's python-neopool-modbus registers.py
# (secondary cross-check) — they agree. AUX uses the "INT1" block. Driven with
# built-in NPWrite + NPExec (no Berry, and no NPSave per toggle so a manual
# override does not wear the EEPROM and reverts on power-cycle). Physical on/off
# echoes back in SENSOR NeoPool.Relay.Aux[n].
#
# ON-DEVICE FINDING (2026-06-28): writing the mode word alone does NOT switch the
# relay — the function word must also be set to bind the timer to the relay.
# Verified on the owner's controller: all 4 AUX had mode=3 (ALWAYS_ON) but
# function=0 and every relay stayed off; writing AUX4's function code (0x4000) +
# NPExec turned the relay on, and clearing it turned it back off. So every mode
# write must also (re)assert the function code.
REG_AUX1_MODE: Final = 0x04AC  # MBF_PAR_TIMER_BLOCK_AUX1_INT1 +0
REG_AUX2_MODE: Final = 0x04BB  # MBF_PAR_TIMER_BLOCK_AUX2_INT1 +0
REG_AUX3_MODE: Final = 0x04CA  # MBF_PAR_TIMER_BLOCK_AUX3_INT1 +0
REG_AUX4_MODE: Final = 0x04D9  # MBF_PAR_TIMER_BLOCK_AUX4_INT1 +0

# Function word (timer-block +11) and the per-AUX function code that binds the
# timer to its physical relay (MBV_PAR_CTIMER_FCT_RELAY* bit). Without this the
# mode word is inert (see on-device finding above).
REG_AUX1_FUNCTION: Final = 0x04B7  # MBF_PAR_TIMER_BLOCK_AUX1_INT1 +11
REG_AUX2_FUNCTION: Final = 0x04C6  # MBF_PAR_TIMER_BLOCK_AUX2_INT1 +11
REG_AUX3_FUNCTION: Final = 0x04D5  # MBF_PAR_TIMER_BLOCK_AUX3_INT1 +11
REG_AUX4_FUNCTION: Final = 0x04E4  # MBF_PAR_TIMER_BLOCK_AUX4_INT1 +11
AUX1_FUNCTION_CODE: Final = 0x0800  # MBV_PAR_CTIMER_FCT_RELAY (AUX1)
AUX2_FUNCTION_CODE: Final = 0x1000  # AUX2
AUX3_FUNCTION_CODE: Final = 0x2000  # AUX3
AUX4_FUNCTION_CODE: Final = 0x4000  # AUX4

# Timer enable/mode values (MBV_PAR_CTIMER_*). The user-facing AUX subset is
# auto/on/off; disabled(0) and linked(2) are intentionally not exposed.
AUX_MODE_AUTO: Final = 1  # MBV_PAR_CTIMER_ENABLED (timer/schedule controlled)
AUX_MODE_ON: Final = 3  # MBV_PAR_CTIMER_ALWAYS_ON
AUX_MODE_OFF: Final = 4  # MBV_PAR_CTIMER_ALWAYS_OFF
AUX_MODE_MAP: Final[dict[int, str]] = {
    AUX_MODE_AUTO: "auto",
    AUX_MODE_ON: "on",
    AUX_MODE_OFF: "off",
}

# Group 5 — per-timer filtration speed (variable-speed pumps). MBF_PAR_FILTRATION_CONF
# (0x050F) is bit-packed (verified vs @curzon01's xsns_83_neopool.ino; svasek
# cross-check agrees). Not in SENSOR → read on demand via NPRead, written
# read-modify-write via NPWrite. Bit layout:
#   bits 0-3  pump type  (MBMSK_PAR_FILTRATION_CONF_TYPE 0x000F; 0 = standard /
#             single-speed, non-zero = variable speed)
#   bits 4-6  default/manual speed (MBMSK_PAR_FILTRATION_CONF_DEF_SPEED 0x0070)
#   bits 7-9  filtration timer 1 speed (shift 7)
#   bits 10-12 filtration timer 2 speed (shift 10)
#   bits 13-15 filtration timer 3 speed (shift 13)
# ON-DEVICE FINDING (2026-06-29): the speed bit-fields use 0/1/2 = Slow/Medium/
# Fast, i.e. one LESS than the SENSOR `NeoPool.Filtration.Speed` / NPFiltrationspeed
# encoding (1/2/3). Verified on the owner's VS pump: reg 0x050F = 0x0002 (type=2,
# all speeds=0) while SENSOR speed read "Slow" (1). So register_value = sensor - 1.
REG_FILTRATION_CONF: Final = 0x050F  # MBF_PAR_FILTRATION_CONF (bit-packed)
MASK_FILTRATION_PUMP_TYPE: Final = 0x000F  # 0 = standard, non-zero = variable speed
FILTRATION_TIMER_SPEED_MASK: Final = 0x0007  # 3-bit speed field (pre-shift)
SHIFT_FILTRATION_TIMER1_SPEED: Final = 7
SHIFT_FILTRATION_TIMER2_SPEED: Final = 10
SHIFT_FILTRATION_TIMER3_SPEED: Final = 13
# Register (0/1/2) → user-facing speed label, matching FILTRATION_SPEED_MAP labels
# but offset by one (SENSOR/command use 1/2/3).
FILTRATION_TIMER_SPEED_MAP: Final[dict[int, str]] = {
    0: "Slow",
    1: "Medium",
    2: "Fast",
}

# Group 4a — controller timer scheduling. The 12 configurable timers live in a
# block of 15-register structures at MBF_PAR_TIMER_BLOCK_BASE (0x0434); each is
# pre-assigned to a function (filtration 1-3, light, aux1-4, ...). Base
# addresses verified vs @curzon01's xsns_83_neopool.ino (primary) and svasek's
# registers.py (secondary). AUX uses the INT1 block (same as Group 4b). These
# registers are NOT in the SENSOR payload; the set_timer service writes them
# on demand via NPWrite/NPWriteL + NPExec + NPSave.
TIMER_BLOCKS: Final[dict[str, int]] = {
    "filtration1": 0x0434,
    "filtration2": 0x0443,
    "filtration3": 0x0452,
    "light": 0x0470,
    "aux1": 0x04AC,
    "aux2": 0x04BB,
    "aux3": 0x04CA,
    "aux4": 0x04D9,
}

# Per-timer 15-register layout offsets (MBV_TIMER_OFFMB_*). Multi-word values
# are 32-bit Low/High pairs written with NPWriteL.
TIMER_OFFSET_ENABLE: Final = 0  # 16-bit enable/mode (MBV_PAR_CTIMER_*)
TIMER_OFFSET_ON: Final = 1  # 32-bit ON time (seconds since midnight)
TIMER_OFFSET_OFF: Final = 3  # 32-bit OFF time (seconds since midnight)
TIMER_OFFSET_PERIOD: Final = 5  # 32-bit repeat period (e.g. 86400 = daily)
TIMER_OFFSET_INTERVAL: Final = 7  # 32-bit run duration (seconds)
TIMER_OFFSET_FUNCTION: Final = 11  # 16-bit function word (relay binding)

# Function word (MBV_TIMER_OFFMB_TIMER_FUNCTION) value per timer — written to
# bind the timer to its relay before the block takes effect. A timer with a
# schedule written but function word=0 is inert (verified on-device 2026-06-28:
# AUX4 and the filtration block were both unbound; the light block was already
# bound with FCT_LIGHTING=0x0002 and toggling its mode drove the pool light).
# Filtration/light use the MBV_PAR_CTIMER_FCT_* function bits; AUX uses the
# MBV_PAR_CTIMER_FCT_RELAY* relay bits. Writing these is idempotent where the
# controller already bound the timer, and required where it did not.
FCT_FILTRATION: Final = 0x0001  # MBV_PAR_CTIMER_FCT_FILTRATION
FCT_LIGHTING: Final = 0x0002  # MBV_PAR_CTIMER_FCT_LIGHTING
TIMER_FUNCTION_CODES: Final[dict[str, int]] = {
    "filtration1": FCT_FILTRATION,
    "filtration2": FCT_FILTRATION,
    "filtration3": FCT_FILTRATION,
    "light": FCT_LIGHTING,
    "aux1": AUX1_FUNCTION_CODE,
    "aux2": AUX2_FUNCTION_CODE,
    "aux3": AUX3_FUNCTION_CODE,
    "aux4": AUX4_FUNCTION_CODE,
}

# Timer working modes (MBV_PAR_CTIMER_*) accepted by the set_timer service.
TIMER_MODE_MAP: Final[dict[str, int]] = {
    "disabled": 0,
    "auto": 1,
    "on": 3,
    "off": 4,
}
SECONDS_PER_DAY: Final = 86400

# Registers read once at startup (and refreshed by write-ACK) to populate the
# config entities. Read individually for robust NPRead response parsing.
CONFIG_REGISTERS: Final[tuple[int, ...]] = (
    REG_HEATING_TEMP,
    REG_CLIMA_ONOFF,
    REG_SMART_ANTI_FREEZE,
    REG_INTELLIGENT_FILT_MIN_TIME,
    REG_UV_MODE,
    REG_RELAY_ACTIVATION_DELAY,
    REG_HIDRO_COVER_ENABLE,
    REG_HIDRO_COVER_REDUCTION,
    REG_AUX1_MODE,
    REG_AUX2_MODE,
    REG_AUX3_MODE,
    REG_AUX4_MODE,
    REG_AUX1_FUNCTION,
    REG_AUX2_FUNCTION,
    REG_AUX3_FUNCTION,
    REG_AUX4_FUNCTION,
    REG_FILTRATION_CONF,
)

# Group 2 number entity bounds (raw register units).
# heating-temp scaling confirmed x1 (raw degC) from the driver's own NPRead
# example (0x0416 -> 28). pH-delay confirmed raw seconds (+10s system offset)
# with NO firmware max — on-device probing of 0x0433 accepted up to 0xFFFF
# unclamped — so the max below is a deliberate UX cap, not a device limit.
HEATING_TEMP_MIN: Final = 15
HEATING_TEMP_MAX: Final = 40
HEATING_TEMP_STEP: Final = 1
INTELLIGENT_MIN_TIME_MIN: Final = 120  # 2 hours
INTELLIGENT_MIN_TIME_MAX: Final = 1440  # 24 hours
INTELLIGENT_MIN_TIME_STEP: Final = 10
PH_ACTIVATION_DELAY_MIN: Final = 0
PH_ACTIVATION_DELAY_MAX: Final = 300  # UX cap (5 min); device accepts more
PH_ACTIVATION_DELAY_STEP: Final = 5

# Group 3 number bounds (raw byte fields of 0x042D, units percent and °C).
# On-device probing (2026-06-28) confirmed the controller does NOT clamp either
# byte of 0x042D (writing 0x00FF / 0xFF00 stored unchanged), nor the enable bits
# of 0x042C — NeoPool NPWrite never validates at the register level. So these are
# UX caps the entity enforces, not device limits. Observed factory default:
# cover reduction 20 %, shutdown temp 0. Cover reduction is a true 0-100 %;
# the shutdown-temp range is a sensible UX choice.
HIDRO_COVER_REDUCTION_MIN: Final = 0
HIDRO_COVER_REDUCTION_MAX: Final = 100
HIDRO_COVER_REDUCTION_STEP: Final = 5
HIDRO_SHUTDOWN_TEMP_MIN: Final = 5
HIDRO_SHUTDOWN_TEMP_MAX: Final = 30
HIDRO_SHUTDOWN_TEMP_STEP: Final = 1

# JSON paths for sensor data extraction
JSON_PATH_TYPE: Final = "NeoPool.Type"
JSON_PATH_TEMPERATURE: Final = "NeoPool.Temperature"
JSON_PATH_TIME: Final = "NeoPool.Time"
JSON_PATH_PH_DATA: Final = "NeoPool.pH.Data"
JSON_PATH_PH_STATE: Final = "NeoPool.pH.State"
JSON_PATH_PH_PUMP: Final = "NeoPool.pH.Pump"
JSON_PATH_PH_MIN: Final = "NeoPool.pH.Min"
JSON_PATH_PH_MAX: Final = "NeoPool.pH.Max"
JSON_PATH_PH_FL1: Final = "NeoPool.pH.FL1"
JSON_PATH_PH_TANK: Final = "NeoPool.pH.Tank"
JSON_PATH_REDOX_DATA: Final = "NeoPool.Redox.Data"
JSON_PATH_REDOX_SETPOINT: Final = "NeoPool.Redox.Setpoint"
JSON_PATH_REDOX_TANK: Final = "NeoPool.Redox.Tank"
JSON_PATH_HYDROLYSIS_DATA: Final = "NeoPool.Hydrolysis.Data"
JSON_PATH_HYDROLYSIS_PERCENT: Final = "NeoPool.Hydrolysis.Percent.Data"
JSON_PATH_HYDROLYSIS_SETPOINT: Final = "NeoPool.Hydrolysis.Percent.Setpoint"
JSON_PATH_HYDROLYSIS_SETPOINT_GH: Final = "NeoPool.Hydrolysis.Setpoint"
JSON_PATH_HYDROLYSIS_MAX: Final = "NeoPool.Hydrolysis.Max"
JSON_PATH_HYDROLYSIS_UNIT: Final = "NeoPool.Hydrolysis.Unit"
JSON_PATH_HYDROLYSIS_STATE: Final = "NeoPool.Hydrolysis.State"
JSON_PATH_HYDROLYSIS_FL1: Final = "NeoPool.Hydrolysis.FL1"
JSON_PATH_HYDROLYSIS_COVER: Final = "NeoPool.Hydrolysis.Cover"
JSON_PATH_HYDROLYSIS_BOOST: Final = "NeoPool.Hydrolysis.Boost"
JSON_PATH_HYDROLYSIS_LOW: Final = "NeoPool.Hydrolysis.Low"
JSON_PATH_HYDROLYSIS_REDOX: Final = "NeoPool.Hydrolysis.Redox"
JSON_PATH_HYDROLYSIS_RUNTIME_TOTAL: Final = "NeoPool.Hydrolysis.Runtime.Total"
JSON_PATH_HYDROLYSIS_RUNTIME_PART: Final = "NeoPool.Hydrolysis.Runtime.Part"
JSON_PATH_HYDROLYSIS_RUNTIME_POL1: Final = "NeoPool.Hydrolysis.Runtime.Pol1"
JSON_PATH_HYDROLYSIS_RUNTIME_POL2: Final = "NeoPool.Hydrolysis.Runtime.Pol2"
JSON_PATH_HYDROLYSIS_RUNTIME_CHANGES: Final = "NeoPool.Hydrolysis.Runtime.Changes"
JSON_PATH_FILTRATION_STATE: Final = "NeoPool.Filtration.State"
JSON_PATH_FILTRATION_SPEED: Final = "NeoPool.Filtration.Speed"
JSON_PATH_FILTRATION_MODE: Final = "NeoPool.Filtration.Mode"
JSON_PATH_LIGHT: Final = "NeoPool.Light"
JSON_PATH_RELAY_STATE: Final = "NeoPool.Relay.State"
JSON_PATH_RELAY_AUX: Final = "NeoPool.Relay.Aux"
JSON_PATH_RELAY_ACID: Final = "NeoPool.Relay.Acid"
JSON_PATH_RELAY_BASE: Final = "NeoPool.Relay.Base"
JSON_PATH_RELAY_REDOX: Final = "NeoPool.Relay.Redox"
JSON_PATH_RELAY_CHLORINE: Final = "NeoPool.Relay.Chlorine"
JSON_PATH_RELAY_CONDUCTIVITY: Final = "NeoPool.Relay.Conductivity"
JSON_PATH_RELAY_HEATING: Final = "NeoPool.Relay.Heating"
JSON_PATH_RELAY_UV: Final = "NeoPool.Relay.UV"
JSON_PATH_RELAY_VALVE: Final = "NeoPool.Relay.Valve"
JSON_PATH_MODULES_PH: Final = "NeoPool.Modules.pH"
JSON_PATH_MODULES_REDOX: Final = "NeoPool.Modules.Redox"
JSON_PATH_MODULES_HYDROLYSIS: Final = "NeoPool.Modules.Hydrolysis"
JSON_PATH_MODULES_CHLORINE: Final = "NeoPool.Modules.Chlorine"
JSON_PATH_MODULES_CONDUCTIVITY: Final = "NeoPool.Modules.Conductivity"
JSON_PATH_MODULES_IONIZATION: Final = "NeoPool.Modules.Ionization"
JSON_PATH_CONDUCTIVITY_DATA: Final = "NeoPool.Conductivity"
JSON_PATH_CHLORINE_DATA: Final = "NeoPool.Chlorine.Data"
JSON_PATH_CHLORINE_SETPOINT: Final = "NeoPool.Chlorine.Setpoint"
JSON_PATH_IONIZATION_DATA: Final = "NeoPool.Ionization.Data"
JSON_PATH_IONIZATION_SETPOINT: Final = "NeoPool.Ionization.Setpoint"
JSON_PATH_IONIZATION_MAX: Final = "NeoPool.Ionization.Max"
JSON_PATH_POWERUNIT_VERSION: Final = "NeoPool.Powerunit.Version"
JSON_PATH_POWERUNIT_NODEID: Final = "NeoPool.Powerunit.NodeID"
JSON_PATH_POWERUNIT_5V: Final = "NeoPool.Powerunit.5V"
JSON_PATH_POWERUNIT_12V: Final = "NeoPool.Powerunit.12V"
JSON_PATH_POWERUNIT_24V: Final = "NeoPool.Powerunit.24-30V"
JSON_PATH_POWERUNIT_4MA: Final = "NeoPool.Powerunit.4-20mA"
JSON_PATH_CONNECTION_REQUESTS: Final = "NeoPool.Connection.MBRequests"
JSON_PATH_CONNECTION_NOERROR: Final = "NeoPool.Connection.MBNoError"
JSON_PATH_CONNECTION_NORESPONSE: Final = "NeoPool.Connection.MBNoResponse"
JSON_PATH_CONNECTION_OUTOFRANGE: Final = "NeoPool.Connection.DataOutOfRange"

# YAML to Integration entity key translation map
# Maps YAML package entity keys (from unique_id) to integration entity keys
# Used during migration to find the correct integration entity
# Keys are extracted from YAML unique_id by stripping "neopool_mqtt_" prefix
YAML_TO_INTEGRATION_KEY_MAP: Final[dict[str, str]] = {
    # Switches - YAML uses "_switch" suffix
    "filtration_switch": "filtration",
    "light_switch": "light",
    # NOTE: aux1-4 are NOT mapped here. AUX control moved from the switch
    # platform to per-AUX "<n>_mode" select entities (auto/on/off, register
    # driven, no Berry) plus read-only "aux<n>" binary sensors. HA can't rename
    # a YAML switch across domains into a select/binary_sensor, so the old
    # switch.*_aux* entities are dropped by _cleanup_removed_entities and the new
    # entities get their auto-generated IDs (same approach as the light move).
    # Button - YAML uses "_state" suffix
    "clear_error_state": "clear_error",
    # Sensors - hydrolysis naming differences
    # IMPORTANT: YAML has TWO hydrolysis sensors:
    #   - hydrolysis_data (%) -> maps to integration's hydrolysis_percent
    #   - hydrolysis_data_gh (g/h) -> maps to integration's hydrolysis_data
    "hydrolysis_data": "hydrolysis_percent",  # YAML % sensor -> integration percent sensor
    "hydrolysis_data_gh": "hydrolysis_data",  # YAML g/h sensor -> integration g/h sensor
    "hydrolysis_data_g_h": "hydrolysis_data",  # Alternative naming for g/h
    "hydrolysis_runtime_pol_changes": "hydrolysis_polarity_changes",  # YAML uses pol_changes
    "hydrolysis_runtime_polarity_changes": "hydrolysis_polarity_changes",  # Alternative
    # Binary sensors - hydrolysis water flow (YAML: hydrolysis_ctrl_fl1_water_flow)
    "hydrolysis_ctrl_fl1_water_flow": "hydrolysis_water_flow",
    "hydrolysis_ctrl_fl1": "hydrolysis_fl1",
    # Binary sensors - pH FL1 naming (YAML: ph_ctrl_fl1, Integration: ph_fl1)
    "ph_ctrl_fl1": "ph_fl1",
    # NOTE: YAML relay_aux*_state binary sensors CANNOT be mapped to integration switch entities
    # because Home Assistant doesn't allow cross-domain entity renames. These entities are
    # cleaned up during migration (deleted from entity registry) since the integration uses
    # switches for AUX relay control instead of separate binary sensors.
    # Binary sensors - modules naming (YAML: modules_*, Integration: modules_*)
    "modules_ph": "modules_ph",
    "modules_redox": "modules_redox",
    "modules_hydrolysis": "modules_hydrolysis",
    "modules_chlorine": "modules_chlorine",
    "modules_conductivity": "modules_conductivity",
    "modules_ionization": "modules_ionization",
    # Alternative module naming (YAML: *_module)
    "ph_module": "modules_ph",
    "redox_module": "modules_redox",
    "hydrolysis_module": "modules_hydrolysis",
    "chlorine_module": "modules_chlorine",
    "conductivity_module": "modules_conductivity",
    "ionization_module": "modules_ionization",
    # Selects - boost mode (YAML: hydrolysis_boost_mode, Integration: boost_mode)
    "hydrolysis_boost_mode": "boost_mode",
    # Sensors - connection naming (YAML: conndiag_*, Integration: connection_*)
    "conndiag_system_requests": "connection_requests",
    "conndiag_system_responses": "connection_responses",
    "conndiag_missed_system_responses": "connection_no_response",
    "conndiag_outofrange_system_responses": "connection_out_of_range",
    # Alternative connection naming
    "connection_system_requests": "connection_requests",
    "connection_system_responses": "connection_responses",
    "connection_missed_system_responses": "connection_no_response",
    "connection_out_of_range_system_responses": "connection_out_of_range",
}

# YAML entities to delete during migration
# These are YAML package entities that have no equivalent in the integration
# (e.g., binary sensors replaced by switches) or were removed.
# Format: (domain, entity_key) tuples
YAML_ENTITIES_TO_DELETE: Final[list[tuple[str, str]]] = [
    # Relay AUX state binary sensors - replaced by switch entities (aux1-aux4)
    # The integration uses switches which have both state AND control
    ("binary_sensor", "relay_aux1_state"),
    ("binary_sensor", "relay_aux2_state"),
    ("binary_sensor", "relay_aux3_state"),
    ("binary_sensor", "relay_aux4_state"),
    # Relay.State[n] binary sensors - removed (assumed fixed relay-to-function mapping)
    # Physical relay states should not be labeled with function names
    ("binary_sensor", "relay_ph_state"),
    ("binary_sensor", "relay_filtration_state"),
    ("binary_sensor", "relay_light_state"),
]
