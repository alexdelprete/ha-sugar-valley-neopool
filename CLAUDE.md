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

**Key mandatory workflows documented here:**

- Release documentation (CHANGELOG.md updates)
- Version bumping (manifest.json + const.py)
- Pre-commit checks (ruff, pymarkdown)
- Quality scale tracking

## Project Overview

### What is NeoPool MQTT?

A Home Assistant custom integration for **Sugar Valley NeoPool** pool controllers connected via
**Tasmota MQTT**. The integration subscribes to MQTT topics published by Tasmota devices running
the NeoPool module and provides bidirectional control.

> **NOTE:** Always understand the MQTT data flow before modifying entity definitions.

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

### Example Lovelace Dashboards

The repo ships four example dashboards in `lovelace/`:

- `ha_neopool_lovelace.yaml` / `_responsive.yaml` — fresh installs
  (entity-ID prefix `neopool_`, from `DEFAULT_DEVICE_NAME = "NeoPool"`).
- `ha_neopool_lovelace_migrated.yaml` / `_responsive_migrated.yaml` —
  users who migrated from the YAML package (entity-ID prefix
  `neopool_mqtt_`, from `_extract_device_name_from_migration` in
  `config_flow.py`).

When renaming, adding, or removing an entity description, update the
relevant dashboard files. The migrated variants must additionally
respect:

- `YAML_TO_INTEGRATION_KEY_MAP` (slug differences vs fresh installs —
  e.g. `redox_data` vs `redox_orp`, `filtration_switch` vs `filtration`)
- `YAML_ENTITIES_TO_DELETE` (don't reference entities removed by
  migration — e.g. `relay_ph_state`, `relay_filtration_state`,
  `relay_light_state`, the four `relay_aux*_state` binary sensors)

Both are defined in `const.py`. `lovelace/README.md` documents the
custom-card dependencies and the fresh-vs-migrated selection logic.

## MQTT Coding Patterns

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

### Throttling and Cumulative Sensors

For entities that change on every SENSOR tick but don't need
recorder-row-per-tick granularity, use `min_update_interval` on
`NeoPoolSensorEntityDescription`. The in-memory value still tracks
every message; `async_write_ha_state()` is throttled. Example
patterns already in the codebase:

- `sensor.controller_time` — `min_update_interval=300.0`
  (5-minute throttle for the controller clock)
- All 4 connection lifetime counters — `min_update_interval=3600.0`
  (one row per hour, matches HA's statistics aggregation)

For Tasmota-RAM counters that reset on every Tasmota reboot
(MBRequests, MBNoResponse, etc.), use `NeoPoolCumulativeSensor` +
`NeoPoolCumulativeSensorEntityDescription`. The class extends
`NeoPoolSensor` + `RestoreEntity` and:

1. Tracks the raw counter in memory across SENSOR messages.
2. Adds the delta (`new - last_raw`) to a cumulative total.
3. Treats `new < last_raw` as a Tasmota-reboot signal — the new value
   itself becomes the delta from 0.
4. Persists the cumulative across HA restarts via `RestoreEntity`.

Throttling is independent of cumulative tracking — combine via the
description's `min_update_interval` attribute.

### Sharing State Across Entities

When multiple entities need to read the same derived value (e.g. the
`ConnectionRateTracker` feeds both `sensor.connection_error_rate` and
`binary_sensor.connection_problem`), the project convention is:

1. **Single source of truth in `entry.runtime_data`** — e.g.
   `runtime_data.connection_rate_tracker: ConnectionRateTracker`.
2. **One MQTT subscription** updates the shared state. Today this
   piggybacks on `_setup_dynamic_disable_watch` in `__init__.py`, which
   is the integration's central per-message handler.
3. **Dispatcher signal** to fan out updates. The signal name is
   produced by the `connection_rate_signal(entry)` helper so producers
   and consumers stay in sync.
4. **Consumers subscribe via `async_dispatcher_connect`** in
   `async_added_to_hass`, registered for cleanup via
   `self.async_on_remove(...)`.

Do NOT have multiple entities open their own MQTT subscriptions to
compute overlapping derived state — that risks drift between them
(different window edges, slightly different snapshots) and burns
subscriptions for no benefit.

## NodeID-Based Unique IDs and Automatic Migration

### Why NodeID?

The integration uses the hardware NodeID from the NeoPool controller (via Tasmota) as the foundation for all identifiers:

- **Hardware-based**: NodeID comes from the physical NeoPool controller, not software configuration
- **Stable**: Survives MQTT topic changes, Tasmota device renames, or Home Assistant reinstalls
- **Multi-device**: Naturally supports multiple NeoPool controllers without conflicts
- **Unique**: Each NeoPool controller has a unique NodeID

### Dual NodeID Acquisition

During setup, the integration acquires both hashed and real NodeIDs:

1. Read current NodeID from SENSOR telemetry
1. Classify: hashed (AA55 prefix), real, or masked (XXXX, old Tasmota)
1. Toggle SO157 once to get the other format
1. Restore SO157 to original state
1. Store both values in config entry

The hashed NodeID is the canonical identifier (privacy by default).
The real NodeID serves as an anchor for device recognition across
format changes. See `docs/NODEID_DUAL_RECOGNITION.md` for full design.

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
    ↓
_acquire_and_store_nodeids (dual NodeID)
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
    ↓
_acquire_and_store_nodeids (dual NodeID)
    ↓
async_create_entry
```

**3. MQTT Discovery Path:**

```text
async_step_mqtt (auto-triggered by MQTT discovery)
    ↓
_acquire_and_store_nodeids (dual NodeID)
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

    # Find migratable entities (orphaned or owned by other platforms like "mqtt")
    yaml_entities = [
        entity for entity in entity_registry.entities.values()
        if entity.unique_id.startswith("neopool_mqtt_")
        and (entity.config_entry_id is None or entity.platform != DOMAIN)
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
      "Aux": [0, 0, 0, 0],
      "Acid": 1,
      "Base": 0,
      "Redox": 1,
      "Chlorine": 0,
      "Conductivity": 0,
      "Heating": 0,
      "UV": 0,
      "Valve": 0
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
# To get physical relay 1 (index 1):
json_path="NeoPool.Relay.State.1"
```

> **NOTE:** `Relay.State[n]` are physical relay states only. Do NOT assume a fixed
> relay-to-function mapping (e.g., State[0]=pH). The mapping is configurable per installation.
> Use named relay fields (`Relay.Acid`, `Relay.Base`, `Relay.Redox`, etc.) for functional status.

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

### 5. Adding a SENSOR subscriber breaks existing setup-entry tests

Anything new that calls `mqtt.async_subscribe(...)` inside
`async_setup_entry` (or a function it calls during setup) will trip
~7 existing tests in `tests/test_init.py`, `test_init_coverage.py`,
`test_init_extended.py`, and `test_coverage_98.py` with:

```text
homeassistant.exceptions.HomeAssistantError:
Cannot subscribe to topic 'tele/SmartPool/SENSOR',
make sure MQTT is set up correctly
```

These tests already mock `async_fetch_device_metadata` to skip the
first MQTT subscribe. They need the same treatment for your new
function:

```python
patch(
    "custom_components.sugar_valley_neopool.<your_new_function>",
    new_callable=AsyncMock,
    return_value=None,
),
```

For inspiration, see the `_setup_dynamic_disable_watch` mock that
was added alongside these tests when the persistent SENSOR watch
landed.

<!-- BEGIN SHARED:repo-sync -->
<!-- Synced by repo-sync on 2026-06-27 -->

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

## CI Workflow Status and Logs

> **IMPORTANT**: Always use `gh` CLI for CI workflow status and logs — it's more efficient than GitHub MCP.

The project has 3 CI workflows: **Lint**, **Tests**, and **Validate**.

**List recent workflow runs:**

```bash
gh run list --repo alexdelprete/ha-sugar-valley-neopool --limit 5
```

**Get workflow status for a specific run:**

```bash
gh run view <run_id> --repo alexdelprete/ha-sugar-valley-neopool
```

**Get test coverage from Tests workflow logs:**

```bash
gh run view <run_id> --repo alexdelprete/ha-sugar-valley-neopool --log 2>&1 | grep "TOTAL"
```

**Quick one-liner to get latest Tests run coverage:**

```bash
# Get latest Tests run ID and fetch coverage
gh run list --repo alexdelprete/ha-sugar-valley-neopool --limit 5 | grep Tests
# Then use the run ID from the output
gh run view <run_id> --repo alexdelprete/ha-sugar-valley-neopool --log 2>&1 | grep "TOTAL"
```

## Coding Standards

### Data Storage Pattern

**DO use `runtime_data`** (modern pattern):

```python
entry.runtime_data = MyData(device_name=name)
```

**DO NOT use `hass.data[DOMAIN]`** (deprecated pattern)

### Translations (Custom Integrations)

Per [HA developer docs](https://developers.home-assistant.io/docs/internationalization/custom_integration/):

- **DO use `translations/en.json`** as the source of truth for English strings
- **DO NOT create `strings.json`** — it is a Core-only build-time feature and is ignored by custom integrations
- All translation files go in `translations/<lang>.json` (e.g., `en.json`, `de.json`, `it.json`)

### Logging

Use structured logging:

```python
_LOGGER.debug("Sensor %s subscribed to %s", key, topic)
```

**DO NOT** use f-strings in logger calls (deferred formatting is more efficient)

Use centralized logging helpers from `helpers.py` when available:

- `log_debug(logger, context, message, **kwargs)`
- `log_info(logger, context, message, **kwargs)`
- `log_warning(logger, context, message, **kwargs)`
- `log_error(logger, context, message, **kwargs)`

Always include context parameter (function name). Format: `(function_name) [key=value]: message`

**Never log manually what HA logs automatically:**

- **DataUpdateCoordinator**: Just raise `UpdateFailed` — HA handles logging automatically
- **ConfigEntryNotReady**: HA logs automatically — don't log manually
- This prevents log spam during extended outages

### Error Handling

- Use custom exceptions (not `return False`) for proper entity availability tracking
- Raise exceptions in the API layer and let the coordinator handle retries
- Define integration-specific exceptions (e.g., `ConnectionError`, `DataError`)

### Type Hints

Always use type hints for function signatures.

### Async/Await Conventions

- All coordinator methods are async
- API methods use async/await properly
- Config entry methods follow HA conventions:
  - `add_update_listener()` — sync
  - `async_on_unload()` — sync (despite the name)
  - `async_forward_entry_setups()` — async
  - `async_unload_platforms()` — async
- Never use blocking calls in async context

## Configuration Best Practices

Following HA best practices, configuration is split between `data` (initial config) and `options` (runtime tuning):

### config_entry.data (changed via Reconfigure flow)

Connection and identity parameters: name, host, port, device ID, etc.

### config_entry.options (changed via Options flow)

Runtime tuning parameters: scan_interval, timeout, etc. Use OptionsFlowWithReload for auto-reload.

### Config Flow Patterns

- Use `vol.Clamp()` for numeric inputs with min/max bounds (better UX than validation errors)
- Use `async_update_reload_and_abort()` for reconfigure flows
- Implement config entry migration (`async_migrate_entry()`) when changing config schema versions

## Entity and Device Patterns

### Device Registry

- Device identifier tuple: `(DOMAIN, unique_id)` where `unique_id` is MAC address, serial number, or similar
- Use `DeviceInfo` with manufacturer, model, sw_version, and configuration_url
- Changing host/IP should not affect entity IDs or historical data

### Entity Unique IDs

- Sensor unique_id pattern: `{device_unique_id}_{sensor_key}`
- Use stable identifiers (MAC address, serial number) — not connection parameters (IP, hostname)
- Config entry type alias: `type MyConfigEntry = ConfigEntry[RuntimeData]`

## Python Version & HA Baseline

These repos are standardized on the **Python 3.14+** toolchain:

- `pyproject.toml`: `requires-python = ">=3.14.2"` (matches Home Assistant
  core's own floor)
- `[tool.ruff]`: `target-version = "py314"`
- Minimum supported Home Assistant core: **2026.3.0** — the
  first HA release requiring Python 3.14.2. `hacs.json` is rendered from
  the same value, so HACS users on older HA don't see updates.

**Implication for source code**: code in these repos may use 3.14-only
syntax (e.g. PEP 758's parenthesis-free `except A, B:`) and is **not**
backwards-compatible with Python 3.13. Ruff with `target-version = "py314"`
will actively *rewrite* `except (A, B):` into the parenthesis-free form —
which is a SyntaxError on Python 3.13. If a contributor's toolchain
regresses to 3.13, expect lint-fixes from these repos to fail to parse
locally until the toolchain is re-aligned.

## Dependencies Best Practices

### Dependency Update Checklist

**Before updating any dependency version in `manifest.json`:**

1. Verify the new version exists on PyPI: `https://pypi.org/project/PACKAGE_NAME/`
1. Check release notes for breaking changes
1. Test locally if possible

> **WARNING**: Always verify PyPI availability before committing dependency updates. Upstream maintainers
> sometimes create GitHub releases but forget to publish to PyPI, breaking the integration for users.

## Git Workflow

### Commit Messages

Use conventional commits with Claude attribution:

```text
feat(api): implement new feature

[Description]

Co-Authored-By: Claude <noreply@anthropic.com>
```

> **NEVER put a GitHub issue-closing keyword in a commit message.**
> `close`/`closes`/`closed`, `fix`/`fixes`/`fixed`, `resolve`/`resolves`/`resolved`
> followed by `#N` auto-close that issue the moment the commit lands on the default
> branch. Reference issues with a neutral phrase only — "Refs #N", "Reported in #N",
> "Addresses #N". Issues are closed manually by the user, never by automation.

### Branch Strategy

- Default branch (`main` or `master`) = next release
- Create tags for releases
- Use pre-release flag for beta versions

## Pre-Commit Configuration

Linting tools and settings are defined in `.pre-commit-config.yaml`:

| Hook        | Tool                           | Purpose                      |
| ----------- | ------------------------------ | ---------------------------- |
| ruff        | `ruff check --no-fix`          | Python linting               |
| ruff-format | `ruff format --check`          | Python formatting            |
| jsonlint    | `uvx --from demjson3 jsonlint` | JSON validation              |
| yamllint    | `uvx yamllint -d "{...}"`      | YAML linting (inline config) |
| pymarkdown  | `pymarkdown scan`              | Markdown linting             |

All hooks use `language: system` (local tools) with `verbose: true` for visibility.

## Pre-Commit Checks (MANDATORY)

> **CRITICAL: ALWAYS run pre-commit checks before ANY git commit.**
> This is a hard rule - no exceptions. Never commit without passing all checks.

```bash
pre-commit run --all-files
```

> Use `pre-commit` directly, **not** `uvx pre-commit`. The `ty` hook
> resolves the interpreter at runtime via `$(which python)` to match the
> devcontainer venv. `uvx` would provision its own ephemeral Python 3.14
> first on PATH, and that env doesn't have Home Assistant installed —
> `ty` would false-fail with unresolved-import errors even though the
> code is fine. The git commit hook and CI's lint workflow already use
> the venv-installed `pre-commit`, so plain `pre-commit run` matches
> their behavior exactly.

Or run individual tools:

```bash
# Python formatting and linting
ruff format .
ruff check . --fix

# Markdown linting
pymarkdown scan .
```

All checks must pass before committing. This applies to ALL commits, not just releases.

### Windows Shell Notes

When running shell commands on Windows, stray `nul` files may be created (Windows null device artifact).
Check for and delete them after command execution:

```bash
rm nul  # if it exists
```

## Testing

> **CRITICAL: NEVER run pytest locally. The local environment cannot be set up correctly for
> Home Assistant integration tests. ALWAYS use GitHub Actions CI to run tests.**

To run tests:

1. Commit and push changes to the repository
1. GitHub Actions will automatically run the test workflow
1. Check the workflow results in the Actions tab or use `mcp__github__*` tools

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

[qs]: https://developers.home-assistant.io/docs/core/integration-quality-scale/

## Release Management - CRITICAL

> **STOP: NEVER create git tags or GitHub releases without explicit user command.**
> This is a hard rule. Always stop after commit/push and wait for user instruction.

**Published releases are FROZEN** - Never modify the git tag, the ZIP asset, or the
`docs/releases/vX.Y.Z.md` file in a way that changes the meaning of what shipped.

The GitHub *release body* (what shows on the release page) may be edited via
`gh release edit vX.Y.Z --notes-file docs/releases/vX.Y.Z.md` to fix typos, add
cross-references to companion files that landed on `main` shortly after the release,
or clarify scope — as long as the edit doesn't misrepresent what's actually in the
released ZIP. When you do this, also update the matching `docs/releases/vX.Y.Z.md` so
the file and the live release body stay in sync.

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

| Step | Tool           | Action                                                                  |
| ---- | -------------- | ----------------------------------------------------------------------- |
| 1    | Edit           | Update `CHANGELOG.md` with version summary                              |
| 2    | Write          | Create `docs/releases/vX.Y.Z.md` release notes (see format below)      |
| 3    | Edit           | Ensure `manifest.json` and `const.py` have correct version              |
| 4    | Bash           | Run linting: `pre-commit run --all-files`                               |
| 5    | Bash           | `git add . && git commit -m "..."`                                      |
| 6    | Bash           | `git push`                                                              |
| 7    | **STOP**       | Wait for user "tag and release" command                                 |
| 8    | **CI Check**   | Verify ALL CI workflows pass (see CI Verification below)                |
| 9    | **RRR**        | Display Release Readiness Report (see below)                            |
| 10   | Bash           | `git tag -a vX.Y.Z -m "Release vX.Y.Z"`                                |
| 11   | Bash           | `git push --tags`                                                       |
| 12   | gh CLI         | `gh release create vX.Y.Z --title "vX.Y.Z" --notes-file docs/releases/vX.Y.Z.md` |
| 13   | GitHub Actions | Validates versions match, then auto-uploads ZIP asset                   |
| 14   | Edit           | Bump versions in `manifest.json` and `const.py` to next version         |

### CI Verification (MANDATORY)

> **CRITICAL: Before tagging/releasing, ALWAYS verify ALL CI workflows are passing.**
> Use GitHub MCP tools to list workflow runs, then use `gh` CLI to get detailed logs if needed.
> NEVER proceed if any workflow is failing.

**Verification steps:**

1. Use `mcp__GitHub_MCP_Remote__actions_list` to list recent workflow runs:

   ```text
   actions_list(method="list_workflow_runs", owner="alexdelprete", repo="ha-sugar-valley-neopool")
   ```

1. Check that ALL workflows show `conclusion: "success"`:
   - Lint workflow
   - Validate workflow
   - Tests workflow

1. If any workflow is failing, use `gh` CLI to get detailed failure logs:

   ```bash
   # View failed run logs (replace <run_id> with actual ID from step 1)
   gh run view <run_id> --log-failed

   # Or view full logs for a specific run
   gh run view <run_id> --log
   ```

1. Fix failing tests/issues, commit, push, and re-verify before proceeding

### Release Notes Format (MANDATORY)

Create a release notes file at `docs/releases/vX.Y.Z.md` using this template.
This file is then used as the body when creating the GitHub release.

```markdown
# Release vX.Y.Z

[![GitHub Downloads](https://img.shields.io/github/downloads/alexdelprete/ha-sugar-valley-neopool/vX.Y.Z/total?style=for-the-badge)](https://github.com/alexdelprete/ha-sugar-valley-neopool/releases/tag/vX.Y.Z)

**Release Date:** YYYY-MM-DD

**Type:** [Major/Minor/Patch/Beta] release - Brief description.

## What's Changed

### Added

- Feature 1

### Changed

- Change 1

### Fixed

- Fix 1

**Full Changelog**:
[compare/vPREV...vX.Y.Z](https://github.com/alexdelprete/ha-sugar-valley-neopool/compare/vPREV...vX.Y.Z)
```

### Release Readiness Report (MANDATORY)

> **When user commands "tag and release", ALWAYS display the Release Readiness Report (RRR) BEFORE proceeding.**

Check CI workflows and display:

```markdown
## Release Readiness Report (RRR)

| Check | Status | Details |
|-------|--------|---------|
| **Lint** | status | date |
| **Tests** | status | date |
| **Validate** | status | date |
| **Test Coverage** | status | Minimum required: 97% |
| **Version** | X.Y.Z | manifest.json + const.py |
| **CHANGELOG.md** | status | Updated |
| **Release notes** | status | docs/releases/vX.Y.Z.md |
| **Working Tree** | status | No uncommitted changes |
```

**Test Coverage Requirement:**

> **CRITICAL: Test coverage MUST be at minimum 97%.**
> If coverage drops below 97%, flag it and do not proceed with release until fixed.

**How to get test coverage:**

```bash
gh run list --repo alexdelprete/ha-sugar-valley-neopool --limit 5 | grep Tests
gh run view <run_id> --repo alexdelprete/ha-sugar-valley-neopool --log 2>&1 | grep "TOTAL"
```

The coverage percentage is the last column in the TOTAL line.

### Issue References in Release Notes

When a release addresses a specific GitHub issue:

- Reference the issue number, but **NEVER use a GitHub closing keyword** —
  `close`/`closes`/`closed`, `fix`/`fixes`/`fixed`, `resolve`/`resolves`/`resolved`
  followed by `#N` — anywhere in commit messages, release notes, the GitHub release
  body, or PR descriptions. Those keywords auto-close the issue when the commit lands
  on the default branch. Use a neutral phrase instead: "Reported in #42",
  "Addresses #42", "Refs #42".
- Thank the user who opened the issue by name and GitHub handle.
- **NEVER close the issue** — the user will do it manually.

### After Publishing a Release

1. Immediately bump versions in `manifest.json` and `const.py` to next version
1. Create new release notes file for next version
1. Mark previous version's documentation as frozen

### Release Documentation Structure

#### Stable/Official Release Notes (e.g., v1.0.0)

- **Scope**: ALL changes since previous stable release
- **Example**: v1.1.0 includes everything since v1.0.0
- **Purpose**: Complete picture for users upgrading from last stable

#### Beta Release Notes (e.g., v1.0.0-beta.1)

- **Scope**: Only incremental changes in this beta
- **Example**: v1.0.0-beta.2 shows only what's new since beta.1
- **Purpose**: Help beta testers focus on what to test

### Documentation Files

- **`CHANGELOG.md`** (root) — quick overview of all releases, Keep a Changelog format
- **`docs/releases/`** — detailed release notes (one file per version)
- **`docs/releases/README.md`** — release directory guide and templates

## Do's and Don'ts

**DO:**

- Run `pre-commit run --all-files` before EVERY commit (NOT `uvx pre-commit` — see Pre-Commit Checks section for why)
- Read CLAUDE.md at session start
- Use `runtime_data` for data storage (not `hass.data[DOMAIN]`)
- Use `@callback` decorator for message handlers
- Log with `%s` formatting (not f-strings)
- Handle missing data gracefully
- Update both manifest.json AND const.py for version bumps
- Get approval before creating tags/releases
- Use custom exceptions for error handling
- Verify PyPI availability before updating dependencies

**NEVER:**

- Commit without running pre-commit checks first
- Modify production code to make tests pass - fix the tests instead
- Use `hass.data[DOMAIN][entry_id]` - use `runtime_data` instead
- Shadow Python builtins (A001)
- Use f-strings in logging (G004)
- Create git tags or GitHub releases without explicit user instruction
- Forget to update VERSION in both manifest.json AND const.py
- Use blocking calls in async context
- Close GitHub issues without explicit user instruction
- Log manually what HA logs automatically (coordinator errors, ConfigEntryNotReady)
- Create documentation files without user request

<!-- END SHARED:repo-sync -->

## Release Prep Notes (Sugar Valley)

**Coverage drift during a dev cycle:** A big feature commit can drop
total coverage even when it adds tests, because the added code is
larger than the added test surface. Watch `__init__.py` in particular
— it tends to absorb new setup-entry hooks (e.g., `_setup_dynamic_disable_watch`,
the connection-rate dispatcher wiring) whose callback bodies are easy
to skip in unit tests. Before tagging, pull the per-file coverage
table from the Tests workflow log, identify the largest absolute
missed-statement count, and write a focused test there if it's
project-internal logic. See the `TestSetupDynamicDisableWatch` class
in `tests/test_init_v018.py` for an example of how to cover a
SENSOR-watch callback without standing up real MQTT.

## Companion YAML Package Repo

[`alexdelprete/HA-NeoPool-MQTT-Package`](https://github.com/alexdelprete/HA-NeoPool-MQTT-Package)
is the predecessor YAML-package project this integration replaces and supports
migrating from. It exposes the same NeoPool MQTT data as HA MQTT entities defined
in `ha_neopool_mqtt_package.yaml` (Jinja `value_template`s) and ships two
companion Lovelace dashboards.

When fixing bugs in *shared* logic (anything derived from the Tasmota
`tele/SmartPool/SENSOR` payload — sensor value parsing, threshold clamping, unit
handling, hydrolysis percent computation), **check whether the same fix is
needed in the package repo**. The Jinja templates there are the equivalent of
this integration's Python `value_fn` / `payload_fn` callables. Stay in lock-step
on user-visible numeric semantics, even when the implementations diverge.

When fixing the package repo, the canonical algorithm lives in this integration
— reference the relevant function (e.g. `_hydrolysis_percent_fn` in `sensor.py`)
in inline comments on the Jinja template so the two stay coherent under future
edits.

## Reference Documentation

- [Tasmota NeoPool Documentation](https://tasmota.github.io/docs/NeoPool/)
- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Project docs/](docs/) folder contains detailed analysis documents
- [Companion YAML package repo](https://github.com/alexdelprete/HA-NeoPool-MQTT-Package)

[qs]: https://developers.home-assistant.io/docs/core/integration-quality-scale/
