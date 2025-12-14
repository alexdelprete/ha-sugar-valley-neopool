# Claude Development Guidelines for Sugar Valley NeoPool Integration

## Mandatory Starting Actions

Before making ANY changes to this repository:

1. **Read this entire document** - Contains critical project-specific information
1. **Review recent git commits**: `git log --oneline -20`
1. **Check current status**: `git status`
1. **Understand the MQTT data flow** before modifying entity definitions

## Project Overview

### What is NeoPool MQTT?

A Home Assistant custom integration for **Sugar Valley NeoPool** pool controllers connected via **Tasmota MQTT**. The integration subscribes to MQTT topics published by Tasmota devices running the NeoPool module and provides bidirectional control.

### Integration Type

- **Type**: Hub (manages a device that provides multiple entities)
- **IoT Class**: Local Push (receives data via MQTT, no polling)
- **Dependencies**: Home Assistant MQTT integration

### Key Technologies

- **Protocol**: MQTT (via Home Assistant's MQTT integration)
- **Device Firmware**: Tasmota with NeoPool module
- **Data Format**: JSON payloads on `tele/{topic}/SENSOR`

## Architecture Overview

### Data Flow

```
NeoPool Controller (RS485/Modbus)
         ↓
Tasmota Device (ESP8266/ESP32)
         ↓
MQTT Broker
         ↓
Home Assistant MQTT Integration
         ↓
NeoPool MQTT Custom Integration
         ↓
Home Assistant Entities
```

### MQTT Topics

| Topic Pattern          | Direction   | Purpose               |
| ---------------------- | ----------- | --------------------- |
| `tele/{device}/SENSOR` | Device → HA | JSON sensor data      |
| `tele/{device}/LWT`    | Device → HA | Online/Offline status |
| `cmnd/{device}/{cmd}`  | HA → Device | Commands              |
| `stat/{device}/RESULT` | Device → HA | Command responses     |

### File Structure

```
custom_components/sugar_valley_neopool/
├── __init__.py          # Integration setup, device registry
├── config_flow.py       # UI configuration + MQTT discovery
├── const.py             # Constants, mappings, JSON paths
├── entity.py            # Base MQTT entity classes
├── helpers.py           # JSON parsing, value transformations
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
├── switch.py            # Switch entities (with commands)
├── select.py            # Select entities (with commands)
├── number.py            # Number entities (with commands)
├── button.py            # Button entities (with commands)
├── manifest.json        # Integration metadata
└── translations/
    └── en.json          # English translations
```

## Coding Standards

### Data Storage Pattern

**DO use `runtime_data`** (modern pattern):

```python
entry.runtime_data = NeoPoolData(device_name=name, mqtt_topic=topic)
```

**DO NOT use `hass.data[DOMAIN]`** (deprecated pattern)

### MQTT Subscription Pattern

All MQTT entities should:

1. Subscribe in `async_added_to_hass()`
1. Unsubscribe in `async_will_remove_from_hass()`
1. Use `@callback` decorator for message handlers
1. Call `self.async_write_ha_state()` after state changes

```python
async def async_added_to_hass(self) -> None:
    await super().async_added_to_hass()

    @callback
    def message_received(msg: mqtt.ReceiveMessage) -> None:
        payload = parse_json_payload(msg.payload)
        if payload is None:
            return
        # Process payload...
        self._attr_native_value = value
        self._attr_available = True
        self.async_write_ha_state()

    await self._subscribe_topic(sensor_topic, message_received)
```

### Entity Description Pattern

Use dataclasses for entity descriptions:

```python
@dataclass(frozen=True, kw_only=True)
class NeoPoolSensorEntityDescription(SensorEntityDescription):
    json_path: str
    value_fn: Callable[[Any], Any] | None = None
```

### JSON Path Extraction

Use `helpers.get_nested_value()` for extracting values:

```python
# Extract NeoPool.pH.Data from JSON payload
value = get_nested_value(payload, "NeoPool.pH.Data")
```

### State Transformations

Define transformation functions in `helpers.py` or inline:

```python
# In const.py - mapping dictionaries
PH_STATE_MAP = {0: "No Alarm", 1: "pH too high", ...}

# In sensor description
value_fn=lambda x: PH_STATE_MAP.get(safe_int(x), f"Unknown ({x})")
```

### Logging

Use structured logging:

```python
_LOGGER.debug("Sensor %s subscribed to %s, path: %s", key, topic, json_path)
```

**DO NOT** use f-strings in logger calls (deferred formatting is more efficient)

### Type Hints

Always use type hints:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
```

## Release Management

### CRITICAL: Never Create Tags/Releases Without Explicit User Instruction

Release process:

1. Update version in `manifest.json` AND `const.py` (must match)
1. Update `CHANGELOG.md` with changes
1. Commit changes
1. Create GitHub release (triggers workflow)
1. Workflow creates ZIP and attaches to release

### Version Locations (Must Be Synchronized)

1. `custom_components/sugar_valley_neopool/manifest.json` → `"version": "X.Y.Z"`
1. `custom_components/sugar_valley_neopool/const.py` → `VERSION = "X.Y.Z"`

## NeoPool-Specific Details

### JSON Payload Structure

```json
{
  "NeoPool": {
    "Type": "Sugar Valley",
    "Temperature": 28.5,
    "pH": {
      "Data": 7.2,
      "State": 0,
      "Pump": 1,
      "Min": 7.0,
      "Max": 7.4
    },
    "Redox": {
      "Data": 750,
      "Setpoint": 700
    },
    "Hydrolysis": {
      "Data": 50,
      "Percent": {"Data": 50, "Setpoint": 60},
      "State": "POL1",
      "Runtime": {"Total": "123T04:30:00"}
    },
    "Filtration": {
      "State": 1,
      "Speed": 2,
      "Mode": 1
    },
    "Relay": {
      "State": [1, 1, 0, 0, 0, 0, 0],
      "Aux": [0, 0, 0, 0]
    },
    "Modules": {
      "pH": 1,
      "Redox": 1,
      "Hydrolysis": 1
    }
  }
}
```

### State Mappings

**pH State** (0-6):

- 0: No Alarm
- 1: pH too high
- 2: pH too low
- 3: Pump exceeded working time
- 4: pH high
- 5: pH low
- 6: Tank level low

**Filtration Mode** (0-4, 13):

- 0: Manual
- 1: Auto
- 2: Heating
- 3: Smart
- 4: Intelligent
- 13: Backwash

**Hydrolysis State**:

- OFF: Cell Inactive
- FLOW: Flow Alarm
- POL1: Polarity 1 active
- POL2: Polarity 2 active

### Commands

| Command           | Payload  | Description          |
| ----------------- | -------- | -------------------- |
| NPFiltration      | 0/1      | Filtration on/off    |
| NPFiltrationmode  | 0-4,13   | Set filtration mode  |
| NPFiltrationSpeed | 1-3      | Set filtration speed |
| NPLight           | 0/1      | Light on/off         |
| NPAux1-4          | 0/1      | Auxiliary relays     |
| NPBoost           | 0/1/2    | Boost mode           |
| NPpHMin/Max       | 0.0-14.0 | pH thresholds        |
| NPRedox           | 0-1000   | Redox setpoint (mV)  |
| NPHydrolysis      | "50 %"   | Hydrolysis setpoint  |
| NPEscape          | (empty)  | Clear error state    |

### Runtime Duration Format

NeoPool reports runtime as `DDDThh:mm:ss`:

- `123T04:30:00` = 123 days, 4 hours, 30 minutes

Use `helpers.parse_runtime_duration()` to convert to hours.

## Common Pitfalls

### 1. Array Access in JSON Paths

Relay states are arrays. Handle both direct access and array index:

```python
# NeoPool.Relay.State is [1, 1, 0, 0, 0, 0, 0]
# To get filtration relay (index 1):
json_path="NeoPool.Relay.State.1"
```

### 2. Inverted Boolean Logic

Some sensors use inverted logic:

- `FL1 = 0` means flow is OK
- `Tank = 0` means tank level is LOW

Use `invert=True` in binary sensor descriptions.

### 3. Hydrolysis Setpoint Format

Command requires specific format with space and percent sign:

```python
command_template="{value} %"  # "50 %" not "50%"
```

### 4. LWT Availability

Always subscribe to LWT topic for availability:

```python
lwt_topic = f"tele/{mqtt_topic}/LWT"
# Payloads: "Online" or "Offline"
```

## Pre-Commit Checklist (MUST DO)

**Before committing and pushing**, always run formatting and linting tools on the whole codebase:

```bash
# Python formatting and linting
ruff format .
ruff check . --fix

# Markdown formatting and linting
mdformat .
pymarkdownlnt scan .

# Type checking
mypy custom_components/sugar_valley_neopool --ignore-missing-imports
```

All commands must pass without errors before committing.

## Testing Checklist

Before committing:

- [ ] Run `ruff check .` - no errors
- [ ] Run `ruff format .` - code formatted
- [ ] Run `mdformat .` - markdown formatted
- [ ] Run `pymarkdownlnt scan .` - markdown linted
- [ ] Run `mypy` - no type errors
- [ ] Test with real device or MQTT simulator
- [ ] Verify entities appear in Home Assistant
- [ ] Test commands actually control the device
- [ ] Check availability updates correctly

## Quality Scale Tracking (MUST DO)

This integration tracks [Home Assistant Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) rules in `quality_scale.yaml`.

**When implementing new features or fixing bugs:**

1. Check if the change affects any quality scale rules
1. Update `quality_scale.yaml` status accordingly:
   - `done` - Rule is fully implemented
   - `todo` - Rule needs implementation
   - `exempt` with `comment` - Rule doesn't apply (explain why)
1. Aim to complete all Bronze tier rules first, then Silver, Gold, Platinum

**Current Status Summary:**

| Tier     | Done | Todo | Exempt |
| -------- | ---- | ---- | ------ |
| Bronze   | 12   | 1    | 5      |
| Silver   | 3    | 4    | 3      |
| Gold     | 5    | 13   | 2      |
| Platinum | 1    | 0    | 2      |

**Priority Todo Items:**

- `config-flow-test-coverage` - Create test suite
- `test-coverage` - >95% test coverage
- `diagnostics` - Implement diagnostics.py
- `parallel-updates` - Specify PARALLEL_UPDATES
- `reconfiguration-flow` - Add options flow

## Reference Documentation

- [Tasmota NeoPool Documentation](https://tasmota.github.io/docs/NeoPool/)
- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Project docs/](docs/) folder contains detailed analysis documents
