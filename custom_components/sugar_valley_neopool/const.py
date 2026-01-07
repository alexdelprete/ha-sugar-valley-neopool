"""Constants for the NeoPool MQTT integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

# Integration identity
DOMAIN: Final = "sugar_valley_neopool"
NAME: Final = "Sugar Valley NeoPool"
VERSION: Final = "0.2.10"
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
CONF_REGENERATE_ENTITY_IDS: Final = "regenerate_entity_ids"

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

# Options flow validation bounds
MIN_FAILURES_THRESHOLD: Final = 1
MAX_FAILURES_THRESHOLD: Final = 10
MIN_OFFLINE_TIMEOUT: Final = 60  # 1 minute
MAX_OFFLINE_TIMEOUT: Final = 3600  # 1 hour

# MQTT Topics - Tasmota NeoPool patterns
TOPIC_SENSOR: Final = "tele/{device}/SENSOR"
TOPIC_LWT: Final = "tele/{device}/LWT"
TOPIC_COMMAND: Final = "cmnd/{device}/{command}"
TOPIC_RESULT: Final = "stat/{device}/RESULT"

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

# Relay names (indices 0-6 for main relays)
RELAY_NAMES: Final[list[str]] = [
    "pH",
    "Filtration",
    "Light",
    "AUX1",
    "AUX2",
    "AUX3",
    "AUX4",
]

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
CMD_ESCAPE: Final = "NPEscape"

# JSON paths for sensor data extraction
JSON_PATH_TYPE: Final = "NeoPool.Type"
JSON_PATH_TEMPERATURE: Final = "NeoPool.Temperature"
JSON_PATH_PH_DATA: Final = "NeoPool.pH.Data"
JSON_PATH_PH_STATE: Final = "NeoPool.pH.State"
JSON_PATH_PH_PUMP: Final = "NeoPool.pH.Pump"
JSON_PATH_PH_MIN: Final = "NeoPool.pH.Min"
JSON_PATH_PH_MAX: Final = "NeoPool.pH.Max"
JSON_PATH_PH_FL1: Final = "NeoPool.pH.FL1"
JSON_PATH_PH_TANK: Final = "NeoPool.pH.Tank"
JSON_PATH_REDOX_DATA: Final = "NeoPool.Redox.Data"
JSON_PATH_REDOX_SETPOINT: Final = "NeoPool.Redox.Setpoint"
JSON_PATH_HYDROLYSIS_DATA: Final = "NeoPool.Hydrolysis.Data"
JSON_PATH_HYDROLYSIS_PERCENT: Final = "NeoPool.Hydrolysis.Percent.Data"
JSON_PATH_HYDROLYSIS_SETPOINT: Final = "NeoPool.Hydrolysis.Percent.Setpoint"
JSON_PATH_HYDROLYSIS_STATE: Final = "NeoPool.Hydrolysis.State"
JSON_PATH_HYDROLYSIS_FL1: Final = "NeoPool.Hydrolysis.FL1"
JSON_PATH_HYDROLYSIS_COVER: Final = "NeoPool.Hydrolysis.Cover"
JSON_PATH_HYDROLYSIS_BOOST: Final = "NeoPool.Hydrolysis.Boost"
JSON_PATH_HYDROLYSIS_LOW: Final = "NeoPool.Hydrolysis.Low"
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
JSON_PATH_MODULES_PH: Final = "NeoPool.Modules.pH"
JSON_PATH_MODULES_REDOX: Final = "NeoPool.Modules.Redox"
JSON_PATH_MODULES_HYDROLYSIS: Final = "NeoPool.Modules.Hydrolysis"
JSON_PATH_MODULES_CHLORINE: Final = "NeoPool.Modules.Chlorine"
JSON_PATH_MODULES_CONDUCTIVITY: Final = "NeoPool.Modules.Conductivity"
JSON_PATH_MODULES_IONIZATION: Final = "NeoPool.Modules.Ionization"
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
    "aux1_switch": "aux1",
    "aux2_switch": "aux2",
    "aux3_switch": "aux3",
    "aux4_switch": "aux4",
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
    # Binary sensors -> Switches mapping (YAML relay state binary sensors map to integration switches)
    "relay_aux1_state": "aux1",
    "relay_aux2_state": "aux2",
    "relay_aux3_state": "aux3",
    "relay_aux4_state": "aux4",
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
