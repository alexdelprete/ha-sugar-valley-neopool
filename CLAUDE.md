# Claude Code Development Guidelines for Sugar Valley NeoPool Integration

## Critical Initial Steps

> **MANDATORY: At the START of EVERY session, you MUST read this entire CLAUDE.md file.**
>
> This file contains project-specific directives, workflows, and patterns that override default behavior.
> Failure to read this file results in violations of mandatory workflows (e.g., missing release documentation),
> duplicated effort, and broken architectural patterns.

**At every session start, you MUST:**

1. **Read this entire CLAUDE.md file** for project context and mandatory procedures
1. **Review recent git commits**: `git log --oneline -20`
1. **Check current status**: `git status`
1. **Understand the MQTT data flow** before modifying entity definitions

**Key mandatory workflows documented here:**

- Release documentation (CHANGELOG.md updates)
- Version bumping (manifest.json + const.py)
- Pre-commit checks (ruff, pymarkdown)
- Quality scale tracking

## Context7 for Documentation

Always use Context7 MCP tools automatically (without being asked) when:

- Generating code that uses external libraries
- Providing setup or configuration steps
- Looking up library/API documentation

Use `resolve-library-id` first to get the library ID, then `get-library-docs` to fetch documentation.

## GitHub MCP for Repository Operations

Always use GitHub MCP tools (`mcp__github__*`) for GitHub operations instead of the `gh` CLI:

- **Issues**: `issue_read`, `issue_write`, `list_issues`, `search_issues`, `add_issue_comment`
- **Pull Requests**: `list_pull_requests`, `create_pull_request`, `pull_request_read`, `merge_pull_request`
- **Reviews**: `pull_request_review_write`, `add_comment_to_pending_review`
- **Repositories**: `search_repositories`, `get_file_contents`, `list_branches`, `list_commits`
- **Releases**: `list_releases`, `get_latest_release`, `list_tags`

Benefits over `gh` CLI:

- Direct API access without shell escaping issues
- Structured JSON responses
- Better error handling
- No subprocess overhead

## Project Overview

### What is NeoPool MQTT?

A Home Assistant custom integration for **Sugar Valley NeoPool** pool controllers connected via
**Tasmota MQTT**. The integration subscribes to MQTT topics published by Tasmota devices running
the NeoPool module and provides bidirectional control.

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

```text
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

```text
custom_components/sugar_valley_neopool/
├── __init__.py          # Integration setup, device registry, migrations
├── config_flow.py       # Config + MQTT discovery + Options/Reconfigure
├── const.py             # Constants, mappings, JSON paths
├── device_trigger.py    # Device automation triggers
├── diagnostics.py       # Downloadable diagnostics
├── entity.py            # Base MQTT entity classes
├── helpers.py           # JSON parsing, value transformations
├── icons.json           # Entity icon definitions
├── repairs.py           # Repair issues for device offline
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
├── switch.py            # Switch entities (with commands)
├── select.py            # Select entities (with commands)
├── number.py            # Number entities (with commands)
├── button.py            # Button entities (with commands)
├── manifest.json        # Integration metadata
├── quality_scale.yaml   # HA Quality Scale tracking
└── translations/        # 10 languages (de, en, es, et, fi, fr, it, nb, pt, sv)
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

## NodeID-Based Unique IDs and Automatic Migration

### Why NodeID?

The integration uses the hardware NodeID from the NeoPool controller (via Tasmota) as the foundation for all identifiers:

- **Hardware-based**: NodeID comes from the physical NeoPool controller, not software configuration
- **Stable**: Survives MQTT topic changes, Tasmota device renames, or Home Assistant reinstalls
- **Multi-device**: Naturally supports multiple NeoPool controllers without conflicts
- **Unique**: Each NeoPool controller has a unique NodeID

### Automatic Tasmota Configuration

The integration automatically configures Tasmota to expose the NodeID:

**When NodeID is hidden:**

1. Integration detects NodeID value is "hidden" or missing
1. Sends MQTT command: `cmnd/{topic}/SetOption157 1`
1. Waits 2 seconds for Tasmota to process
1. Subscribes to `tele/{topic}/SENSOR` and waits up to 10 seconds for NodeID
1. Validates NodeID is present and not "hidden"
1. Only proceeds if NodeID is successfully configured

**Implementation details:**

```python
# In config_flow.py
async def _auto_configure_nodeid(self, device_topic: str) -> dict[str, Any]:
    """Auto-configure Tasmota SetOption157 to enable NodeID."""
    await mqtt.async_publish(
        self.hass,
        f"cmnd/{device_topic}/SetOption157",
        "1",
        qos=1,
        retain=False,
    )
    await asyncio.sleep(2)
    nodeid = await self._wait_for_nodeid(device_topic)
    # Returns {"success": bool, "nodeid": str, "error": str}
```

**NodeID validation:**

```python
# In helpers.py
def validate_nodeid(nodeid: str | None) -> bool:
    """Validate NodeID is present and not 'hidden'."""
    if nodeid is None or nodeid == "":
        return False
    if isinstance(nodeid, str) and nodeid.lower() in ["hidden", "hidden_by_default"]:
        return False
    return True
```

### Unique ID Pattern

**Entity unique_id**: `neopool_mqtt_{nodeid}_{entity_key}`

- Example: `neopool_mqtt_ABC123_water_temperature`
- Generated in `entity.py` base class `__init__()` method
- NodeID comes from `config_entry.runtime_data.nodeid`
- Entity key is passed as parameter (e.g., "water_temperature", "ph_data")

**Device identifier**: `(DOMAIN, nodeid)`

- Tuple format required by Home Assistant device registry
- Example: `("sugar_valley_neopool", "ABC123")`
- Used in `async_register_device()` and `get_device_info()`

**Config entry unique_id**: `{DOMAIN}_{nodeid}`

- Example: `sugar_valley_neopool_ABC123`
- Prevents duplicate config entries for the same device
- Set in all config flow steps before creating entry

**Code locations:**

```python
# entity.py - Entity unique_id
nodeid = config_entry.runtime_data.nodeid
self._attr_unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"

# __init__.py - Device identifier
device_registry.async_get_or_create(
    config_entry_id=entry.entry_id,
    identifiers={(DOMAIN, nodeid)},
    # ...
)

# config_flow.py - Config entry unique_id
await self.async_set_unique_id(f"{DOMAIN}_{self._nodeid}")
self._abort_if_unique_id_configured()
```

### Config Flow Multi-Step Process

The integration supports three setup paths, all converging to NodeID-based configuration:

**1. YAML Migration Path:**

```text
async_step_user
    ↓
async_step_yaml_migration (checkbox)
    ↓ (if checked)
async_step_yaml_topic (input + validation)
    ↓
_validate_yaml_topic (MQTT subscribe + wait)
    ↓ (if NodeID hidden)
_auto_configure_nodeid (SetOption157 1)
    ↓
async_step_yaml_confirm (show topic + NodeID)
    ↓
async_create_entry (with CONF_MIGRATE_YAML: True)
```

**2. Manual Setup Path:**

```text
async_step_user
    ↓
async_step_yaml_migration (checkbox)
    ↓ (if not checked)
async_step_discover_device (manual input)
    ↓
_validate_yaml_topic (validates topic)
    ↓ (if NodeID hidden)
_auto_configure_nodeid (SetOption157 1)
    ↓
async_create_entry
```

**3. MQTT Discovery Path:**

```text
async_step_mqtt (auto-triggered by MQTT discovery)
    ↓
Extract NodeID from discovery payload
    ↓ (if NodeID hidden)
_auto_configure_nodeid (SetOption157 1)
    ↓
async_step_mqtt_confirm (show discovered device)
    ↓
async_create_entry
```

### Automatic YAML Migration

When users migrate from the YAML package, the integration automatically updates entities:

**Migration trigger:**

- Config flow stores `CONF_MIGRATE_YAML: True` in entry data (YAML path only)
- `async_setup_entry()` in `__init__.py` always calls `async_migrate_yaml_entities()`
- Migration runs on every setup, but only finds entities on first run

**Migration process:**

```python
# __init__.py
async def async_migrate_yaml_entities(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    nodeid: str,
) -> None:
    """Migrate YAML package entities to new unique_id format."""
    entity_registry = er.async_get(hass)

    # Find YAML entities (no config_entry_id, starts with "neopool_mqtt_")
    yaml_entities = [
        entity for entity in entity_registry.entities.values()
        if entity.unique_id.startswith("neopool_mqtt_")
        and entity.config_entry_id is None
    ]

    # Update each entity
    for entity in yaml_entities:
        old_unique_id = entity.unique_id  # e.g., "neopool_mqtt_water_temperature"
        entity_key = old_unique_id.replace("neopool_mqtt_", "", 1)
        new_unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"

        # Update in registry - preserves all historical data
        entity_registry.async_update_entity(
            entity.entity_id,
            new_unique_id=new_unique_id,
            config_entry_id=entry.entry_id,
        )
```

**What gets preserved:**

- All historical data (graphs, statistics, long-term statistics)
- Entity ID (e.g., `sensor.neopool_water_temperature`)
- Entity customizations (friendly names, icons, areas, etc.)
- Automation/script references remain valid

**What changes:**

- `unique_id`: `neopool_mqtt_water_temperature` → `neopool_mqtt_ABC123_water_temperature`
- `config_entry_id`: `None` → entry ID of new integration
- Entities now appear under the integration in UI

### Topic Validation

All setup paths validate the MQTT topic before proceeding:

```python
async def _validate_yaml_topic(
    self, topic: str, timeout_seconds: int = 10
) -> dict[str, Any]:
    """Validate YAML topic by subscribing and waiting for message."""
    # Subscribe to tele/{topic}/SENSOR
    # Wait for NeoPool message or timeout
    # Extract NodeID from payload
    # Return {"valid": bool, "nodeid": str, "payload": dict}
```

**Validation criteria:**

- Topic must be a valid MQTT topic format
- Must receive a message within timeout (default 10 seconds)
- Message must be valid JSON
- JSON must contain "NeoPool" key (confirms it's a NeoPool device)
- NodeID is extracted from `NeoPool.Powerunit.NodeID`

**Custom topic support:**

- Integration validates ANY topic, not just default "SmartPool"
- Users can migrate from custom YAML configurations
- Topic validation ensures device is actually publishing before setup

## Release Management - CRITICAL

> **STOP: NEVER create git tags or GitHub releases without explicit user command.**
> This is a hard rule. Always stop after commit/push and wait for user instruction.

**Published releases are FROZEN** - Never modify documentation for released versions.

**Master branch = Next Release** - All commits target the next version with version bumped
in manifest.json and const.py.

### Version Bumping Rules

> **IMPORTANT: Do NOT bump version during a session. All changes go into the CURRENT unreleased version.**

- The version in `manifest.json` and `const.py` represents the NEXT release being prepared
- **NEVER bump version until user commands "tag and release"**
- Multiple features/fixes can be added to the same unreleased version
- Only bump to a NEW version number AFTER the current version is released

### Version Locations (Must Be Synchronized)

1. `custom_components/sugar_valley_neopool/manifest.json` → `"version": "X.Y.Z"`
1. `custom_components/sugar_valley_neopool/const.py` → `VERSION = "X.Y.Z"`

### Complete Release Workflow

> **IMPORTANT: Version Validation**
> The release workflow VALIDATES that tag, manifest.json, and const.py versions all match.
> You MUST update versions BEFORE creating the release, not after.

| Step | Tool | Action |
| ---- | ---- | ------ |
| 1 | Edit | Update `CHANGELOG.md` with version summary |
| 2 | Edit | Ensure `manifest.json` and `const.py` have correct version |
| 3 | Bash | Run linting: `ruff format .`, `ruff check . --fix`, `pymarkdown scan .` |
| 4 | Bash | `git add . && git commit -m "..."` |
| 5 | Bash | `git push` |
| 6 | **STOP** | Wait for user "tag and release" command |
| 7 | **Checklist** | Display Release Readiness Checklist (see below) |
| 8 | Bash | `git tag -a vX.Y.Z -m "Release vX.Y.Z"` |
| 9 | Bash | `git push --tags` |
| 10 | gh CLI | `gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes` |
| 11 | GitHub Actions | Validates versions match, then auto-uploads ZIP asset |
| 12 | Edit | Bump versions in `manifest.json` and `const.py` to next version |

### Release Readiness Checklist (MANDATORY)

> **When user commands "tag and release", ALWAYS display this checklist BEFORE proceeding.**

```markdown
## Release Readiness Checklist

| Item | Status |
|------|--------|
| Version in `manifest.json` | X.Y.Z |
| Version in `const.py` | X.Y.Z |
| CHANGELOG.md updated | Updated |
| GitHub Actions (lint/test/validate) | PASSING |
| Working tree clean | Clean |
| Git tag | vX.Y.Z created/pushed |
```

Verify ALL items before proceeding with tag creation. If any item fails, fix it first.

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

## Pre-Commit Configuration

Linting tools and settings are defined in `.pre-commit-config.yaml`:

| Hook | Tool | Purpose |
| ---- | ---- | ------- |
| ruff | `ruff check --no-fix` | Python linting |
| ruff-format | `ruff format --check` | Python formatting |
| jsonlint | `uvx --from demjson3 jsonlint` | JSON validation |
| yamllint | `uvx yamllint -d "{...}"` | YAML linting (inline config) |
| pymarkdown | `pymarkdown scan` | Markdown linting |

All hooks use `language: system` (local tools) with `verbose: true` for visibility.

## Pre-Commit Checks (MANDATORY)

> **CRITICAL: ALWAYS run pre-commit checks before ANY git commit.**
> This is a hard rule - no exceptions. Never commit without passing all checks.

```bash
uvx pre-commit run --all-files
```

Or run individual tools:

```bash
# Python formatting and linting
ruff format .
ruff check . --fix

# Markdown linting
pymarkdown scan .

# Type checking
mypy custom_components/sugar_valley_neopool --ignore-missing-imports
```

All checks must pass before committing. This applies to ALL commits, not just releases.

### Windows Shell Notes

When running shell commands on Windows, stray `nul` files may be created (Windows null device artifact).
Check for and delete them after command execution:

```bash
rm nul  # if it exists
```

## Testing Checklist

Before committing:

- [ ] Run `uvx pre-commit run --all-files` - all hooks pass
- [ ] Run `ruff check .` - no errors
- [ ] Run `ruff format .` - code formatted
- [ ] Run `pymarkdown scan .` - markdown linted
- [ ] Run `mypy` - no type errors
- [ ] Test with real device or MQTT simulator
- [ ] Verify entities appear in Home Assistant
- [ ] Test commands actually control the device
- [ ] Check availability updates correctly

> **CRITICAL: NEVER modify production code to make tests pass. Always fix the tests instead.**
> Production code is the source of truth. If tests fail, the tests are wrong - not the production code.
> The only exception is when production code has an actual bug that tests correctly identified.

## Quality Scale Tracking (MUST DO)

This integration tracks [Home Assistant Quality Scale][qs] rules in `quality_scale.yaml`.

**When implementing new features or fixing bugs:**

1. Check if the change affects any quality scale rules
1. Update `quality_scale.yaml` status accordingly:
   - `done` - Rule is fully implemented
   - `todo` - Rule needs implementation
   - `exempt` with `comment` - Rule doesn't apply (explain why)
1. Aim to complete all Bronze tier rules first, then Silver, Gold, Platinum

**Priority Todo Items:**

- `config-flow-test-coverage` - Create test suite
- `test-coverage` - >95% test coverage

## Reference Documentation

- [Tasmota NeoPool Documentation](https://tasmota.github.io/docs/NeoPool/)
- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Project docs/](docs/) folder contains detailed analysis documents

[qs]: https://developers.home-assistant.io/docs/core/integration-quality-scale/

## Do's and Don'ts

**DO:**

- Run `uvx pre-commit run --all-files` before EVERY commit
- Read CLAUDE.md at session start
- Use `runtime_data` for data storage (not `hass.data[DOMAIN]`)
- Use `@callback` decorator for MQTT message handlers
- Log with `%s` formatting (not f-strings)
- Handle missing data gracefully
- Update both manifest.json AND const.py for version bumps
- Get approval before creating tags/releases
- Subscribe to LWT topic for availability
- Use NodeID-based unique IDs for entities

**NEVER:**

- Commit without running pre-commit checks first
- Modify production code to make tests pass - fix the tests instead
- Use `hass.data[DOMAIN][entry_id]` - use `runtime_data` instead
- Shadow Python builtins (A001)
- Use f-strings in logging (G004)
- Create git tags or GitHub releases without explicit user instruction
- Forget to update VERSION in both manifest.json AND const.py
- Ignore LWT (Last Will and Testament) for availability
- Use blocking calls in async context
- Close GitHub issues without explicit user instruction
