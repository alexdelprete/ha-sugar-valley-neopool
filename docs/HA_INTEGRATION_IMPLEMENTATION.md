# Home Assistant NeoPool MQTT Integration - Implementation Guide

## Overview

This guide provides technical details for implementing a Home Assistant custom integration for
Tasmota NeoPool pool controllers via MQTT.

______________________________________________________________________

## Architecture

### Integration Type: MQTT-based Custom Integration

**Components:**

- `__init__.py` - Integration setup and MQTT subscription
- `config_flow.py` - Configuration UI
- `const.py` - Constants and mappings
- `sensor.py` - Sensor entities (read-only values)
- `number.py` - Number entities (adjustable setpoints)
- `select.py` - Select entities (mode selection)
- `switch.py` - Switch entities (binary controls)
- `binary_sensor.py` - Binary sensor entities (status indicators)

______________________________________________________________________

## Entity Mapping Strategy

### Dynamic Entity Creation

Entities should be created based on the `Module` object in telemetry:

```python
def should_create_ph_entities(module_data):
    """Only create pH entities if pH module is installed"""
    return module_data.get("pH") == 1

def should_create_redox_entities(module_data):
    """Only create redox entities if redox module is installed"""
    return module_data.get("Redox") == 1

def should_create_hydrolysis_entities(module_data):
    """Only create hydrolysis entities if hydrolysis module is installed"""
    return module_data.get("Hydrolysis") == 1

def should_create_chlorine_entities(module_data):
    """Only create chlorine entities if chlorine module is installed"""
    return module_data.get("Chlorine") == 1
```

______________________________________________________________________

## Sensor Entities (sensor.py)

### Temperature Sensor

```python
{
    "name": "Temperature",
    "unique_id": "neopool_{device_id}_temperature",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Temperature }}",
    "unit_of_measurement": "°C",
    "device_class": "temperature",
    "state_class": "measurement",
    "icon": "mdi:thermometer"
}
```

### pH Sensor (if Module.pH == 1)

```python
{
    "name": "pH",
    "unique_id": "neopool_{device_id}_ph",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.pH.Data }}",
    "unit_of_measurement": "pH",
    "icon": "mdi:ph",
    "state_class": "measurement"
}
```

### pH State Sensor

```python
{
    "name": "pH State",
    "unique_id": "neopool_{device_id}_ph_state",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": """
        {% set states = {
            0: 'OK',
            1: 'pH Too High',
            2: 'pH Too Low',
            3: 'Pump Timeout',
            4: 'pH High Warning',
            5: 'pH Low Warning',
            6: 'Tank Empty'
        } %}
        {{ states[value_json.NeoPool.pH.State | int] | default('Unknown') }}
    """,
    "icon": "mdi:alert-circle"
}
```

### Redox Sensor (if Module.Redox == 1)

```python
{
    "name": "Redox",
    "unique_id": "neopool_{device_id}_redox",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Redox.Data }}",
    "unit_of_measurement": "mV",
    "icon": "mdi:lightning-bolt",
    "state_class": "measurement"
}
```

### Chlorine Sensor (if Module.Chlorine == 1)

```python
{
    "name": "Chlorine",
    "unique_id": "neopool_{device_id}_chlorine",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Chlorine.Data }}",
    "unit_of_measurement": "ppm",
    "icon": "mdi:water-plus",
    "state_class": "measurement"
}
```

### Hydrolysis Production Sensor (if Module.Hydrolysis == 1)

```python
{
    "name": "Hydrolysis Production",
    "unique_id": "neopool_{device_id}_hydrolysis",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Data }}",
    "unit_of_measurement": "{{ value_json.NeoPool.Hydrolysis.Unit }}",
    "icon": "mdi:waves",
    "state_class": "measurement"
}
```

### Hydrolysis State Sensor

```python
{
    "name": "Hydrolysis State",
    "unique_id": "neopool_{device_id}_hydrolysis_state",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.State }}",
    "icon": "mdi:state-machine"
}
```

### Hydrolysis Runtime Sensors

```python
# Total Runtime
{
    "name": "Hydrolysis Runtime Total",
    "unique_id": "neopool_{device_id}_hydrolysis_runtime_total",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Runtime.Total }}",
    "icon": "mdi:timer"
}

# Polarity 1 Runtime
{
    "name": "Hydrolysis Runtime Pol1",
    "unique_id": "neopool_{device_id}_hydrolysis_runtime_pol1",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Runtime.Pol1 }}",
    "icon": "mdi:timer"
}

# Polarity 2 Runtime
{
    "name": "Hydrolysis Runtime Pol2",
    "unique_id": "neopool_{device_id}_hydrolysis_runtime_pol2",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Runtime.Pol2 }}",
    "icon": "mdi:timer"
}

# Polarity Changes Counter
{
    "name": "Hydrolysis Polarity Changes",
    "unique_id": "neopool_{device_id}_hydrolysis_changes",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Runtime.Changes }}",
    "icon": "mdi:counter",
    "state_class": "total_increasing"
}
```

### Filtration Speed Sensor

```python
{
    "name": "Filtration Speed",
    "unique_id": "neopool_{device_id}_filtration_speed",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": """
        {% set speeds = {1: 'Low', 2: 'Medium', 3: 'High'} %}
        {{ speeds[value_json.NeoPool.Filtration.Speed | int] |
           default('Unknown') }}
    """,
    "icon": "mdi:speedometer"
}
```

### Filtration Mode Sensor

```python
{
    "name": "Filtration Mode",
    "unique_id": "neopool_{device_id}_filtration_mode",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": """
        {% set modes = {
            0: 'Manual',
            1: 'Auto',
            2: 'Heating',
            3: 'Smart',
            4: 'Intelligent',
            13: 'Backwash'
        } %}
        {{ modes[value_json.NeoPool.Filtration.Mode | int] | default('Unknown') }}
    """,
    "icon": "mdi:engine"
}
```

### Power Supply Sensors

```python
# 5V Rail
{
    "name": "Power 5V",
    "unique_id": "neopool_{device_id}_power_5v",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Powerunit['5V'] }}",
    "unit_of_measurement": "V",
    "device_class": "voltage",
    "entity_category": "diagnostic"
}

# 12V Rail
{
    "name": "Power 12V",
    "unique_id": "neopool_{device_id}_power_12v",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Powerunit['12V'] }}",
    "unit_of_measurement": "V",
    "device_class": "voltage",
    "entity_category": "diagnostic"
}

# 24-30V Rail
{
    "name": "Power 24-30V",
    "unique_id": "neopool_{device_id}_power_24_30v",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Powerunit['24-30V'] }}",
    "unit_of_measurement": "V",
    "device_class": "voltage",
    "entity_category": "diagnostic"
}
```

### Connection Statistics (ESP32 only, if NPSetOption1 enabled)

```python
# Total Requests
{
    "name": "Modbus Requests",
    "unique_id": "neopool_{device_id}_mb_requests",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Connection.MBRequests }}",
    "icon": "mdi:counter",
    "entity_category": "diagnostic",
    "state_class": "total_increasing"
}

# Successful Requests
{
    "name": "Modbus Successful",
    "unique_id": "neopool_{device_id}_mb_success",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Connection.MBNoError }}",
    "icon": "mdi:check-circle",
    "entity_category": "diagnostic",
    "state_class": "total_increasing"
}

# CRC Errors
{
    "name": "Modbus CRC Errors",
    "unique_id": "neopool_{device_id}_mb_crc_err",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Connection.MBCRCErr }}",
    "icon": "mdi:alert-circle",
    "entity_category": "diagnostic",
    "state_class": "total_increasing"
}

# Timeout Errors
{
    "name": "Modbus Timeouts",
    "unique_id": "neopool_{device_id}_mb_timeout",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Connection.MBNoResponse }}",
    "icon": "mdi:alert-circle",
    "entity_category": "diagnostic",
    "state_class": "total_increasing"
}
```

______________________________________________________________________

## Binary Sensor Entities (binary_sensor.py)

### pH Flow Sensor

```python
{
    "name": "pH Flow",
    "unique_id": "neopool_{device_id}_ph_flow",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.pH.FL1 }}",
    "payload_on": 1,
    "payload_off": 0,
    "device_class": "running",
    "icon": "mdi:water-pump"
}
```

### pH Tank Level

```python
{
    "name": "pH Tank",
    "unique_id": "neopool_{device_id}_ph_tank",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.pH.Tank }}",
    "payload_on": 1,
    "payload_off": 0,
    "device_class": "problem",
    "icon": "mdi:cup"
}
```

### Hydrolysis Cover

```python
{
    "name": "Pool Cover",
    "unique_id": "neopool_{device_id}_pool_cover",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Cover }}",
    "payload_on": 1,
    "payload_off": 0,
    "device_class": "opening",
    "icon": "mdi:pool"
}
```

### Filtration State

```python
{
    "name": "Filtration Running",
    "unique_id": "neopool_{device_id}_filtration_state",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Filtration.State }}",
    "payload_on": 1,
    "payload_off": 0,
    "device_class": "running",
    "icon": "mdi:pump"
}
```

### Module Detection (Diagnostic)

```python
# pH Module Installed
{
    "name": "pH Module Installed",
    "unique_id": "neopool_{device_id}_module_ph",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Module.pH }}",
    "payload_on": 1,
    "payload_off": 0,
    "entity_category": "diagnostic",
    "icon": "mdi:chip"
}

# Redox Module Installed
{
    "name": "Redox Module Installed",
    "unique_id": "neopool_{device_id}_module_redox",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Module.Redox }}",
    "payload_on": 1,
    "payload_off": 0,
    "entity_category": "diagnostic",
    "icon": "mdi:chip"
}

# Hydrolysis Module Installed
{
    "name": "Hydrolysis Module Installed",
    "unique_id": "neopool_{device_id}_module_hydrolysis",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Module.Hydrolysis }}",
    "payload_on": 1,
    "payload_off": 0,
    "entity_category": "diagnostic",
    "icon": "mdi:chip"
}

# Chlorine Module Installed
{
    "name": "Chlorine Module Installed",
    "unique_id": "neopool_{device_id}_module_chlorine",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Module.Chlorine }}",
    "payload_on": 1,
    "payload_off": 0,
    "entity_category": "diagnostic",
    "icon": "mdi:chip"
}
```

______________________________________________________________________

## Number Entities (number.py)

### pH Minimum

```python
{
    "name": "pH Min",
    "unique_id": "neopool_{device_id}_ph_min",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.pH.Min }}",
    "command_topic": "cmnd/{topic}/NPpHMin",
    "min": 0,
    "max": 14,
    "step": 0.1,
    "mode": "slider",
    "icon": "mdi:ph"
}
```

### pH Maximum

```python
{
    "name": "pH Max",
    "unique_id": "neopool_{device_id}_ph_max",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.pH.Max }}",
    "command_topic": "cmnd/{topic}/NPpHMax",
    "min": 0,
    "max": 14,
    "step": 0.1,
    "mode": "slider",
    "icon": "mdi:ph"
}
```

### Redox Setpoint

```python
{
    "name": "Redox Setpoint",
    "unique_id": "neopool_{device_id}_redox_setpoint",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Redox.Setpoint }}",
    "command_topic": "cmnd/{topic}/NPRedox",
    "min": 0,
    "max": 1000,
    "step": 10,
    "mode": "box",
    "unit_of_measurement": "mV",
    "icon": "mdi:lightning-bolt"
}
```

### Chlorine Setpoint

```python
{
    "name": "Chlorine Setpoint",
    "unique_id": "neopool_{device_id}_chlorine_setpoint",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Chlorine.Setpoint }}",
    "command_topic": "cmnd/{topic}/NPChlorine",
    "min": 0,
    "max": 10,
    "step": 0.1,
    "mode": "slider",
    "unit_of_measurement": "ppm",
    "icon": "mdi:water-plus"
}
```

### Hydrolysis Setpoint

```python
{
    "name": "Hydrolysis Setpoint",
    "unique_id": "neopool_{device_id}_hydrolysis_setpoint",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Hydrolysis.Setpoint }}",
    "command_topic": "cmnd/{topic}/NPHydrolysis",
    "min": 0,
    "max": 100,  # Or device-specific max for g/h mode
    "step": 5,
    "mode": "slider",
    "unit_of_measurement": "{{ value_json.NeoPool.Hydrolysis.Unit }}",
    "icon": "mdi:waves"
}
```

### Ionization Setpoint (if Module.Ionization == 1)

```python
{
    "name": "Ionization Setpoint",
    "unique_id": "neopool_{device_id}_ionization_setpoint",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ value_json.NeoPool.Ionization.Setpoint }}",
    "command_topic": "cmnd/{topic}/NPIonization",
    "min": 0,
    "max": "{{ value_json.NeoPool.Ionization.Max }}",
    "step": 1,
    "mode": "slider",
    "icon": "mdi:current-dc"
}
```

______________________________________________________________________

## Select Entities (select.py)

### Filtration Mode

```python
{
    "name": "Filtration Mode",
    "unique_id": "neopool_{device_id}_filtration_mode_select",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": """
        {% set modes = {
            0: 'Manual',
            1: 'Auto',
            2: 'Heating',
            3: 'Smart',
            4: 'Intelligent',
            13: 'Backwash'
        } %}
        {{ modes[value_json.NeoPool.Filtration.Mode | int] | default('Manual') }}
    """,
    "command_topic": "cmnd/{topic}/NPFiltrationmode",
    "command_template": """
        {% set modes = {
            'Manual': 0,
            'Auto': 1,
            'Heating': 2,
            'Smart': 3,
            'Intelligent': 4,
            'Backwash': 13
        } %}
        {{ modes[value] }}
    """,
    "options": ["Manual", "Auto", "Heating", "Smart", "Intelligent", "Backwash"],
    "icon": "mdi:engine"
}
```

### Filtration Speed

```python
{
    "name": "Filtration Speed",
    "unique_id": "neopool_{device_id}_filtration_speed_select",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": """
        {% set speeds = {1: 'Low', 2: 'Medium', 3: 'High'} %}
        {{ speeds[value_json.NeoPool.Filtration.Speed | int] | default('Low') }}
    """,
    "command_topic": "cmnd/{topic}/NPFiltrationspeed",
    "command_template": """
        {% set speeds = {'Low': 1, 'Medium': 2, 'High': 3} %}
        {{ speeds[value] }}
    """,
    "options": ["Low", "Medium", "High"],
    "icon": "mdi:speedometer"
}
```

### Hydrolysis Boost Mode

```python
{
    "name": "Hydrolysis Boost",
    "unique_id": "neopool_{device_id}_boost_select",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": """
        {% set modes = {0: 'Off', 1: 'On', 2: 'Redox'} %}
        {{ modes[value_json.NeoPool.Hydrolysis.Boost | int] | default('Off') }}
    """,
    "command_topic": "cmnd/{topic}/NPBoost",
    "command_template": """
        {% set modes = {'Off': 0, 'On': 1, 'Redox': 2} %}
        {{ modes[value] }}
    """,
    "options": ["Off", "On", "Redox"],
    "icon": "mdi:turbo"
}
```

______________________________________________________________________

## Switch Entities (switch.py)

### Filtration Switch

```python
{
    "name": "Filtration",
    "unique_id": "neopool_{device_id}_filtration_switch",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template":
        "{{ 'ON' if value_json.NeoPool.Filtration.State == 1 else 'OFF' }}",
    "command_topic": "cmnd/{topic}/NPFiltration",
    "payload_on": "1",
    "payload_off": "0",
    "icon": "mdi:pump"
}
```

### Light Switch

```python
{
    "name": "Light",
    "unique_id": "neopool_{device_id}_light_switch",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ 'ON' if value_json.NeoPool.Light == 1 else 'OFF' }}",
    "command_topic": "cmnd/{topic}/NPLight",
    "payload_on": "1",
    "payload_off": "0",
    "icon": "mdi:lightbulb"
}
```

### Relay Switches (7 relays)

```python
# Relay 1
{
    "name": "Relay 1",
    "unique_id": "neopool_{device_id}_relay_1",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template":
        "{{ 'ON' if value_json.NeoPool.Relay.State[0] == 1 else 'OFF' }}",
    "command_topic": "cmnd/{topic}/NPWrite",
    "payload_on": "0x0408 1",  # Example register address
    "payload_off": "0x0408 0",
    "icon": "mdi:electric-switch"
}

# ... Similar for Relay 2-7
```

### Named Relay Switches

```python
# Heating Relay
{
    "name": "Heating",
    "unique_id": "neopool_{device_id}_relay_heating",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template":
        "{{ 'ON' if value_json.NeoPool.Relay.Heating == 1 else 'OFF' }}",
    "icon": "mdi:radiator"
}

# UV Lamp Relay
{
    "name": "UV Lamp",
    "unique_id": "neopool_{device_id}_relay_uv",
    "state_topic": "tele/{topic}/SENSOR",
    "value_template": "{{ 'ON' if value_json.NeoPool.Relay.UV == 1 else 'OFF' }}",
    "icon": "mdi:lightbulb-fluorescent-tube"
}
```

______________________________________________________________________

## Constants (const.py)

```python
"""Constants for NeoPool MQTT integration."""

DOMAIN = "neopool_mqtt"

# Configuration
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_DEVICE_NAME = "device_name"

# MQTT Topics
TOPIC_SENSOR = "tele/{topic}/SENSOR"
TOPIC_RESULT = "stat/{topic}/RESULT"
TOPIC_COMMAND = "cmnd/{topic}/{command}"

# Commands
CMD_FILTRATION = "NPFiltration"
CMD_FILTRATION_MODE = "NPFiltrationmode"
CMD_FILTRATION_SPEED = "NPFiltrationspeed"
CMD_LIGHT = "NPLight"
CMD_BOOST = "NPBoost"
CMD_PH_MIN = "NPpHMin"
CMD_PH_MAX = "NPpHMax"
CMD_REDOX = "NPRedox"
CMD_CHLORINE = "NPChlorine"
CMD_HYDROLYSIS = "NPHydrolysis"
CMD_IONIZATION = "NPIonization"
CMD_TIME_SYNC = "NPTime"

# State Mappings
PH_STATES = {
    0: "OK",
    1: "pH Too High",
    2: "pH Too Low",
    3: "Pump Timeout",
    4: "pH High Warning",
    5: "pH Low Warning",
    6: "Tank Empty",
}

PH_PUMP_STATES = {
    0: "Inactive",
    1: "Dosing",
    2: "Stopped",
}

FILTRATION_MODES = {
    0: "Manual",
    1: "Auto",
    2: "Heating",
    3: "Smart",
    4: "Intelligent",
    13: "Backwash",
}

FILTRATION_MODES_REVERSE = {v: k for k, v in FILTRATION_MODES.items()}

FILTRATION_SPEEDS = {
    1: "Low",
    2: "Medium",
    3: "High",
}

FILTRATION_SPEEDS_REVERSE = {v: k for k, v in FILTRATION_SPEEDS.items()}

HYDROLYSIS_STATES = {
    "OFF": "Off",
    "FLOW": "Flow Alarm",
    "POL1": "Running (Polarity 1)",
    "POL2": "Running (Polarity 2)",
}

BOOST_MODES = {
    0: "Off",
    1: "On",
    2: "Redox",
}

BOOST_MODES_REVERSE = {v: k for k, v in BOOST_MODES.items()}

# Device Classes
DEVICE_CLASS_TEMPERATURE = "temperature"
DEVICE_CLASS_VOLTAGE = "voltage"
DEVICE_CLASS_RUNNING = "running"
DEVICE_CLASS_PROBLEM = "problem"
DEVICE_CLASS_OPENING = "opening"

# Icons
ICON_PH = "mdi:ph"
ICON_REDOX = "mdi:lightning-bolt"
ICON_CHLORINE = "mdi:water-plus"
ICON_TEMPERATURE = "mdi:thermometer"
ICON_PUMP = "mdi:pump"
ICON_LIGHT = "mdi:lightbulb"
ICON_WAVES = "mdi:waves"
ICON_SPEEDOMETER = "mdi:speedometer"
ICON_ENGINE = "mdi:engine"
ICON_TURBO = "mdi:turbo"
ICON_TIMER = "mdi:timer"
ICON_COUNTER = "mdi:counter"
ICON_CHIP = "mdi:chip"
ICON_POOL = "mdi:pool"

# Entity Categories
ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"
ENTITY_CATEGORY_CONFIG = "config"
```

______________________________________________________________________

## Data Processing Functions

### Parse Runtime String

```python
def parse_runtime(runtime_str: str) -> int:
    """
    Parse NeoPool runtime string to total seconds.

    Format: "DDDThh:mm:ss" (e.g., "120T15:30:45")
    Returns: Total seconds as integer
    """
    if not runtime_str or "T" not in runtime_str:
        return 0

    try:
        days_part, time_part = runtime_str.split("T")
        days = int(days_part)

        time_components = time_part.split(":")
        hours = int(time_components[0])
        minutes = int(time_components[1])
        seconds = int(time_components[2])

        total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds
        return total_seconds
    except (ValueError, IndexError):
        return 0


def format_runtime(total_seconds: int) -> str:
    """
    Format seconds to NeoPool runtime string.

    Returns: String in format "DDDThh:mm:ss"
    """
    days = total_seconds // 86400
    remaining = total_seconds % 86400
    hours = remaining // 3600
    remaining = remaining % 3600
    minutes = remaining // 60
    seconds = remaining % 60

    return f"{days}T{hours:02d}:{minutes:02d}:{seconds:02d}"
```

### Validate pH Value

```python
def validate_ph(value: float) -> bool:
    """Validate pH value is within acceptable range."""
    return 0.0 <= value <= 14.0


def validate_redox(value: int) -> bool:
    """Validate redox value is within acceptable range."""
    return 0 <= value <= 1000


def validate_chlorine(value: float) -> bool:
    """Validate chlorine value is within acceptable range."""
    return 0.0 <= value <= 10.0
```

### Module Detection Helper

```python
def get_installed_modules(neopool_data: dict) -> dict:
    """
    Extract installed module information.

    Returns dict with module names as keys and boolean values.
    """
    module_data = neopool_data.get("Module", {})

    return {
        "ph": module_data.get("pH", 0) == 1,
        "redox": module_data.get("Redox", 0) == 1,
        "hydrolysis": module_data.get("Hydrolysis", 0) == 1,
        "chlorine": module_data.get("Chlorine", 0) == 1,
        "conductivity": module_data.get("Conductivity", 0) == 1,
        "ionization": module_data.get("Ionization", 0) == 1,
    }
```

______________________________________________________________________

## Device Information

Every entity should be associated with a device:

```python
DEVICE_INFO = {
    "identifiers": {(DOMAIN, device_id)},
    "name": device_name,
    "manufacturer": "Sugar Valley",
    "model": neopool_data.get("Type", "NeoPool Controller"),
    "sw_version": neopool_data.get("Powerunit", {}).get("Version", "Unknown"),
    "via_device": (DOMAIN, "tasmota_mqtt"),
}
```

______________________________________________________________________

## Error Handling

### MQTT Connection Errors

```python
def handle_mqtt_disconnect():
    """Handle MQTT disconnection."""
    # Set all entities to unavailable
    # Log warning
    # Attempt reconnection


def handle_malformed_payload(payload: str):
    """Handle malformed JSON payload."""
    # Log error with payload details
    # Don't update entity states
    # Increment error counter
```

### Value Validation

```python
def safe_get_nested(data: dict, path: list, default=None):
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to search
        path: List of keys (e.g., ["NeoPool", "pH", "Data"])
        default: Default value if path doesn't exist

    Returns:
        Value at path or default
    """
    current = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
```

______________________________________________________________________

## Availability Template

All entities should track availability:

```python
{
    "availability": [
        {
            "topic": "tele/{topic}/LWT",
            "payload_available": "Online",
            "payload_not_available": "Offline"
        }
    ]
}
```

______________________________________________________________________

## Testing Checklist

### Unit Tests

- [ ] Parse runtime strings correctly
- [ ] Validate input ranges (pH, redox, chlorine)
- [ ] Handle missing JSON keys gracefully
- [ ] Convert state enums correctly
- [ ] Parse module installation flags

### Integration Tests

- [ ] MQTT subscription successful
- [ ] Entity discovery works
- [ ] State updates from telemetry
- [ ] Command publishing successful
- [ ] Unavailable when device offline
- [ ] Dynamic entity creation based on modules

### Manual Tests

- [ ] Configure via UI
- [ ] All sensors show correct values
- [ ] Number entities accept input
- [ ] Select entities change modes
- [ ] Switches control devices
- [ ] Device info displays correctly
- [ ] Entities unavailable when disconnected

______________________________________________________________________

## Performance Considerations

### Telemetry Processing

- Use `NPTelePeriod 0` for change-based updates
- Reduce MQTT traffic
- Only update changed entities

### Entity Creation

- Create entities only for installed modules
- Use entity categories for diagnostic/config entities
- Lazy load optional features

### State Updates

- Batch process telemetry messages
- Avoid redundant state updates
- Use debouncing for rapid changes

______________________________________________________________________

## Security Considerations

### MQTT Credentials

- Store in Home Assistant secrets
- Use TLS for MQTT if possible
- Validate all incoming data

### Command Validation

- Range check all numeric inputs
- Sanitize command payloads
- Rate limit commands to prevent abuse

______________________________________________________________________

## Future Enhancements

### Planned Features

1. **Services**

   - `neopool_mqtt.sync_time` - Sync device time
   - `neopool_mqtt.clear_errors` - Clear error states
   - `neopool_mqtt.save_config` - Persist settings to EEPROM

1. **Diagnostics**

   - Communication quality metrics
   - Error rate tracking
   - Last update timestamp

1. **Advanced Controls**

   - Timer programming via UI
   - Relay mapping configuration
   - Berry script execution (ESP32)

1. **Automations**

   - Auto time sync
   - pH alarm notifications
   - Temperature-based filtration

______________________________________________________________________

## Example Integration Setup

```python
# __init__.py
async def async_setup_entry(hass, entry):
    """Set up NeoPool MQTT from a config entry."""
    mqtt_topic = entry.data[CONF_MQTT_TOPIC]
    device_name = entry.data[CONF_DEVICE_NAME]

    # Subscribe to sensor topic
    sensor_topic = TOPIC_SENSOR.format(topic=mqtt_topic)

    @callback
    def message_received(msg):
        """Handle new MQTT messages."""
        try:
            payload = json.loads(msg.payload)
            neopool_data = payload.get("NeoPool")

            if not neopool_data:
                return

            # Update coordinator data
            coordinator.async_set_updated_data(neopool_data)

        except json.JSONDecodeError:
            _LOGGER.error("Invalid JSON payload")

    await mqtt.async_subscribe(hass, sensor_topic, message_received)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "binary_sensor", "number", "select", "switch"]
    )

    return True
```

______________________________________________________________________

## Recommended Project Structure

```text
custom_components/neopool_mqtt/
├── __init__.py              # Integration setup
├── config_flow.py           # Configuration UI
├── const.py                 # Constants and mappings
├── coordinator.py           # Data update coordinator
├── sensor.py                # Sensor entities
├── binary_sensor.py         # Binary sensor entities
├── number.py                # Number entities
├── select.py                # Select entities
├── switch.py                # Switch entities
├── services.yaml            # Service definitions
├── strings.json             # UI strings
├── translations/
│   └── en.json              # English translations
└── manifest.json            # Integration metadata
```
