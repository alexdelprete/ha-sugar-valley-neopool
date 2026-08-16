# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Per-timer filtration speed for variable-speed pumps.** Three new selects
  (`select.<name>_filtration_timer<n>_speed`, Slow/Medium/Fast) let each
  filtration timer run at its own speed, read/written in the bit-packed
  `MBF_PAR_FILTRATION_CONF` register. The integration **auto-detects** a
  variable-speed pump (the controller only reports `Filtration.Speed` for
  speed-capable pumps); a new **Filtration pump type** option
  (auto/variable/standard) in the integration's options can override the
  detection. The selects stay unavailable on single-speed pumps.
- **`sugar_valley_neopool.set_timer` service** to program the controller's
  built-in timers (filtration 1-3, light, AUX1-4), which then run on the
  controller independent of Home Assistant. You pick a device and timer, then
  set any of: a start+stop time, a repeat period, and a mode (auto/on/off/
  disabled). **All schedule fields are optional and applied granularly** — set
  only what you want to change and leave the rest to keep their current value
  (start and stop must be set together). Uses the built-in `NPWrite`/
  `NPWriteL`/`NPExec` commands (no Berry extension); the timer registers are not
  in the SENSOR telemetry, so the service writes them on demand. The service
  also writes each timer's function word to bind it to its relay (filtration,
  light, and AUX) — verified on hardware that an unbound timer's schedule is
  inert.
- **Pool light as a dedicated `light` entity** (`light.<name>_light`). It
  controls the same relay as before via `NPLight`, but as a proper light it
  now works with light cards, light groups, and "turn on the lights" voice
  intents. See the breaking-change note below.
- **Automatic time-sync switch** (`switch.<name>_auto_time_sync`): when on,
  the integration resyncs the controller clock (`NPTime`) whenever it drifts
  more than 60s from Home Assistant. Off by default; state is restored across
  restarts.
- **Reset cell-runtime button** (`button.<name>_reset_cell_runtime`): clears
  the hydrolysis cell partial/user runtime counters. Diagnostic and disabled
  by default.
- **Configuration controls for settings that are not in the SENSOR telemetry**,
  read on demand from the controller and kept current by command
  acknowledgments (a lightweight `NPRead`/`NPWrite` layer — no continuous
  polling). Each entity self-gates on the relevant module/relay being present:
  - Switches: **UV mode**, **Climate mode**, **Smart antifreeze**.
  - Numbers: **Heating temperature**, **Intelligent minimum filtration time**,
    **pH pump activation delay**.
  - Hydrolysis cover handling: **Cover reduction** (enable switch + percentage)
    and **Temperature shutdown** (enable switch + threshold), which share the
    controller's bit-packed registers and are written without disturbing each
    other.
- **AUX relays no longer require the Tasmota Berry extension.** AUX1–4 are now
  controlled through their controller timer block with the built-in
  `NPWrite`/`NPExec` commands (the timer's function word binds it to the relay,
  then the mode word forces on/off — verified on hardware), exposed as
  **AUX1–4 mode** selects
  (`select.<name>_aux<n>_mode`) with options **Auto** (follow schedule), **On**
  (force on), and **Off** (force off). The live relay output is exposed as
  read-only **AUX1–4** binary sensors (`binary_sensor.<name>_aux<n>`). See the
  breaking-change note below.

### Changed

- **BREAKING: the pool light moved from the `switch` platform to the `light`
  platform.** The old switch is removed automatically and replaced by a light
  entity:
  - Fresh installs: `switch.neopool_light` → `light.neopool_light`.
  - Migrated installs: `switch.neopool_mqtt_light_switch` →
    `light.neopool_mqtt_light`.

  Update any automations, scripts, or dashboards that referenced the old
  switch entity. The bundled Lovelace dashboards (fresh and migrated variants)
  have already been updated.
- **BREAKING: AUX1–4 moved from the `switch` platform to `select` (mode) +
  `binary_sensor` (state).** The old AUX switches are removed automatically:
  - Fresh installs: `switch.neopool_aux<n>` → `select.neopool_aux<n>_mode`
    plus `binary_sensor.neopool_aux<n>`.
  - Migrated installs: `switch.neopool_mqtt_aux<n>_switch` →
    `select.neopool_mqtt_aux<n>_mode` plus `binary_sensor.neopool_mqtt_aux<n>`.

  A plain switch could not represent the controller's three AUX states
  (auto/on/off); forcing "off" via a switch would silently override the
  relay's schedule. Update automations, scripts, or dashboards that toggled the
  old AUX switches to set the select instead. The bundled Lovelace dashboards
  (fresh and migrated variants) have already been updated.
- **BREAKING: the "Water Flow" binary sensor was removed; the FL1 sensors are
  now problem-class "Flow Alarm" entities.** (Refs #23, thanks @deZeus89.)
  "Water Flow" was an inverted duplicate of the same `Hydrolysis.FL1` bit
  behind "Hydrolysis FL1", and its name wrongly suggested it tracked pump
  water flow — FL1 is the hydrolysis module's flow-detection alarm, not the
  filtration state (that is `switch.<name>_filtration`). Now a single entity
  per FL1 bit exposes raw alarm semantics (`on` = flow alarm active):
  - Fresh installs: `binary_sensor.neopool_water_flow` is removed
    automatically; use `binary_sensor.neopool_hydrolysis_fl1` (named
    "Hydrolysis Flow Alarm"; new installs create it as
    `binary_sensor.neopool_hydrolysis_flow_alarm`). "pH FL1" is likewise
    renamed "pH Flow Alarm".
  - Migrated installs: `binary_sensor.neopool_mqtt_hydrolysis_water_flow` is
    removed automatically; use `binary_sensor.neopool_mqtt_hydrolysis_fl1`.

  Note the inverted meaning when updating automations: the old entity was `on`
  when flow was OK; the flow-alarm entities are `on` when there is a problem.
  The bundled Lovelace dashboards have already been updated.

## [1.1.3] - 2026-06-27

### Fixed

- **Topic validation no longer times out on devices with the default
  Tasmota `TelePeriod` (issue #18)**: manual setup, manual discovery, and
  reconfigure validate a topic by waiting for a `tele/{topic}/SENSOR`
  message, but Tasmota's default `TelePeriod` is 300s and SENSOR is
  published non-retained — so a perfectly correct topic almost always
  failed with "Could not receive messages from this MQTT topic".
  `_validate_yaml_topic` now publishes an immediate telemetry trigger
  (reusing `_trigger_telemetry`) right after subscribing, so validation
  succeeds within seconds regardless of `TelePeriod`. The
  `cannot_connect` error string also gained a fallback hint to set
  `TelePeriod 10` in the Tasmota console (all 10 languages). Reported by
  @megaherb.

### Documentation

- **Clarified that AUX1–4 control requires the Tasmota Berry NeoPool
  command extension** (ESP32). `NPAux<n>` is not a built-in Tasmota
  command — by design, not a bug, per the NeoPool driver author. Without
  the extension, AUX state reads work but toggles are ignored by the
  firmware. Reworded the `NPAux<n>` entry in
  `docs/TASMOTA_NEOPOOL_DRIVER_REFERENCE.md` (previously framed as a
  "firmware quirk" with a `Power<gpio>`/`NPWrite` workaround) and added a
  note to the README AUX switches feature.

## [1.1.2] - 2026-05-31

### Fixed

- **Recovery script can now be cleared via the Options flow**: the
  recovery-script `EntitySelector` used `vol.Optional(..., default=...)`,
  which made voluptuous resurrect the previously-saved value whenever the
  field was submitted empty — so clearing the script in the UI never stuck
  and the old script kept running. Switched to
  `description={"suggested_value": ...}`, which pre-fills the form for
  display without re-injecting the value when the field is left blank.
  Clearing the field now correctly unsets the option.

## [1.1.1] - 2026-05-28

### Fixed

- **HA default polling no longer bypasses the throttle on cumulative
  counters and `controller_time` (`should_poll` fix)**: NeoPool entities
  inherited HA's default `should_poll = True`, so HA's ~30-second polling
  cycle called
  `async_write_ha_state()` on its own schedule and silently bypassed the
  `min_update_interval` throttle introduced in v1.1.0. The connection
  cumulative counters were ending up at ~30s recorder cadence (matching
  the polling interval) instead of the intended hourly. Fix: set
  `_attr_should_poll = False` on `NeoPoolEntity` (the base class for
  every NeoPool entity). All NeoPool entities are MQTT-push driven, so
  polling was redundant anyway. After upgrade, the connection counters
  will write to the recorder at most once per hour as designed, and
  `controller_time` at most once per 5 minutes.
- **Cumulative entities now recover their last value across v1.0.x → v1.1.0
  upgrades**: when v1.1.0 swapped the `NeoPoolSensor` (no `RestoreEntity`
  mixin) for the new `NeoPoolCumulativeSensor` (which is a
  `RestoreEntity`), the restore-state cache had nothing for these
  entities — so the cumulative restarted from 0 on the first v1.1.0
  startup, leaving a visible drop in the entity history graph.
  `NeoPoolCumulativeSensor.async_added_to_hass` now has a two-tier
  restore: first try `RestoreEntity` (the fast path, works for v1.1.0+
  restarts), then fall back to a recorder query for the most recent
  recorded state of the entity_id. The recorder fallback is gracefully
  skipped if the `recorder` integration isn't loaded, or if no prior
  history exists. Anyone hitting this in the future during a similar
  class-swap upgrade won't see their cumulative reset.

## [1.1.0] - 2026-05-27

### Changed

- **Auto-disable entities for absent modules**: `sensor.chlorine_data`,
  `sensor.ionization_data`, `sensor.conductivity_data`,
  `number.chlorine_setpoint`, and `number.ionization_setpoint` now default
  to disabled and are automatically enabled by the integration only when
  the corresponding module is reported as installed in
  `NeoPool.Modules` (value `1`). Existing installs are migrated on next
  startup: if the module isn't present, the entity is disabled
  (`disabled_by=INTEGRATION`); if the module is present but the entity
  was previously disabled by the integration, it gets re-enabled.
  User-disabled entities are left alone. Mirrors the existing behaviour
  of `_disable_unavailable_relay_entities` for relay binary sensors.
- **Auto-disable g/h hydrolysis entities in % display mode**: when
  `NeoPool.Hydrolysis.Unit` is `"%"`, the three g/h-labeled sensors
  (`sensor.hydrolysis_data` g/h, `sensor.hydrolysis_setpoint_gh`,
  `sensor.hydrolysis_max`) are auto-disabled, since the absolute g/h
  value is unrecoverable from the telemetry in that mode. Re-enabled
  automatically when the controller is flipped back to g/h.
- **Dynamic refresh of disable state**: the integration now subscribes
  persistently to SENSOR telemetry and re-evaluates the disable rules
  whenever `NeoPool.Modules`, `NeoPool.Relay`, or
  `NeoPool.Hydrolysis.Unit` changes vs the last seen value. If any
  previously-disabled entity needs to be re-enabled (e.g. user installs
  a new module mid-session or flips the display unit), the integration
  schedules an automatic config-entry reload so the entity actually
  materializes. Disable-direction transitions don't trigger a reload.
- **State-change logs upgraded to WARNING**: entity enable/disable
  events are now logged at WARNING level (previously INFO) so they're
  visible without enabling debug logging.
- **Connection diagnostics are now lifetime cumulative**:
  `sensor.connection_requests`, `sensor.connection_responses`,
  `sensor.connection_no_response`, and `sensor.connection_out_of_range`
  used to report Tasmota's RAM counters directly, which meant they
  reset to 0 on every Tasmota restart — long-term graphs looked like a
  sawtooth. They now track the cumulative across resets in memory: the
  integration compares each new raw value to the previous one, treats a
  drop as a Tasmota-reboot signal (the new value becomes the delta from
  0), and accumulates. State persists across HA restarts via
  `RestoreEntity`. State writes are throttled to once per hour (~96
  total rows/day for all four), which still gives HA's statistics
  engine clean hourly aggregates for long-term trend graphs.
- **`sensor.controller_time` throttled to once per 5 minutes** (was
  previously disabled by default in this Unreleased section): the
  value changes on every SENSOR telemetry tick, so leaving it
  unthrottled spammed the recorder. Throttling caps it at ~288
  rows/day regardless of `TelePeriod` while keeping the entity useful
  as a sanity-check for the controller's clock and verifying the Sync
  Controller Time button worked. Now enabled by default again.
- **Generic throttle mechanism**: new `min_update_interval` attribute
  on `NeoPoolSensorEntityDescription`. When set, the entity's
  in-memory value still tracks every SENSOR message, but
  `async_write_ha_state()` (which is what creates recorder rows) is
  called at most once per interval. Available for future entities
  that would otherwise be too chatty.

### Added

- **`sensor.connection_error_rate`** — diagnostic sensor that reports
  the rolling 10-minute Modbus failure rate
  (`(no_response + out_of_range) / requests * 100`). The window is
  sliding, not lifetime, so a recent issue is reflected within minutes
  regardless of how big the lifetime denominator has grown. Returns
  `unknown` until ≥2 samples have arrived inside the window, and clears +
  restarts the window on a Tasmota reboot (so resets don't pollute the
  rate).
- **`binary_sensor.connection_problem`** — diagnostic binary sensor
  (`device_class=problem`) that turns on when the rolling rate exceeds a
  configurable threshold. Default: 5%. Configure via
  **Settings → Devices & services → NeoPool → Configure → Connection
  error-rate threshold**. Reads from the same shared
  `ConnectionRateTracker` as the rate sensor, so both stay consistent.
- **`connection_error_rate_threshold` option** in the options flow
  (range 0.1–100%, step 0.1). Triggers a config-entry reload via
  `OptionsFlowWithReload`, so the new threshold takes effect immediately
  without a HA restart.

## [1.0.1] - 2026-05-27

### Added

- **Lovelace dashboards**: Four ready-to-use example dashboards under
  [`lovelace/`](lovelace/) — two for fresh installs and two for users who
  migrated from the YAML package. Each pair has a full-width desktop layout
  (mushroom cards + masonry 400px) and a mobile-friendly responsive layout
  (tile cards + masonry 320px). Fresh-install files use the default
  `neopool_` entity-ID prefix; `_migrated.yaml` variants use the preserved
  `neopool_mqtt_*` IDs, drop tiles for the three relay-state entities that
  migration deletes, and add tiles for the new entities the integration
  ships beyond the package (chlorine, ionization, conductivity, sync
  controller time button, hydrolysis redox controlled, extra relay states).
  All four include conditional sections that hide chlorine / ionization /
  conductivity cards when those modules aren't installed. See
  [`lovelace/README.md`](lovelace/README.md) for the fresh-vs-migrated
  selection guide, installation instructions, and the full custom-card
  dependency list.

### Fixed

- **Hydrolysis sensor stuck at 0% when controller is in % mode**: The `Hydrolysis`
  (%) sensor read `NeoPool.Hydrolysis.Percent.Data`, which is only emitted by
  Tasmota firmware from November 2023 onwards and is computed with integer math
  that truncates small values to 0. The sensor now computes the percent directly
  from `Hydrolysis.Data`, `Hydrolysis.Unit`, and `Hydrolysis.Max`, so it works
  correctly regardless of the configured display unit and firmware version.

### Changed

- **`Hydrolysis (g/h)`, `Hydrolysis Setpoint (g/h)`, `Hydrolysis Max` sensors**:
  These sensors now go unavailable when the controller is in % display mode,
  instead of showing the percentage value with a misleading `g/h` unit suffix.
  When the controller is in g/h mode, behavior is unchanged.

## [1.0.0] - 2026-05-26

### Added

- **Chlorine entities**: New `chlorine_data` sensor (ppm) and `chlorine_setpoint`
  number entity (0-10 ppm) for NeoPool controllers with the chlorine module.
- **Conductivity sensor**: New `conductivity_data` sensor (%) for controllers with
  the conductivity module.
- **Hydrolysis detail sensors**: Three new read-only sensors — `hydrolysis_setpoint_gh`
  (g/h setpoint), `hydrolysis_max` (max capacity), and `hydrolysis_unit` (unit string).
- **Hydrolysis Redox Controlled**: New binary sensor indicating whether hydrolysis is
  being controlled by the redox system.
- **Controller Time sensor**: New diagnostic sensor showing the NeoPool controller's
  internal clock (`NeoPool.Time`).
- **Sync Controller Time button**: New button entity that syncs the controller clock
  to Tasmota's time via `NPTime 0`.
- **Driver reference documentation**: New `docs/TASMOTA_NEOPOOL_DRIVER_REFERENCE.md`
  with firmware internals, Modbus registers, and driver quirks.

## [0.2.19] - 2026-05-21

### Added

- **Ionization sensor and setpoint**: New `ionization_data` sensor and
  `ionization_setpoint` number entity for NeoPool controllers with copper-silver
  ionization module. Setpoint max is dynamic, read from `NeoPool.Ionization.Max`.
  Contributed by @netbasebe in #13.

### Changed

- **JSON path constants**: All entity descriptions now use `JSON_PATH_*` constants
  from `const.py` instead of hardcoded strings. Added missing constants for relay
  and redox entities.

### Fixed

- **Device info sw_version**: Tasmota firmware version now included in
  `get_device_info` sw_version field.

### Updated

- **Tasmota NeoPool Firmware**: Bundled firmware updated to v15.4.0 Sybil.

## [0.2.18] - 2026-04-04

### Added

- **Dual NodeID recognition**: Acquires both hashed (AA55 prefix) and real
  NodeIDs during setup by briefly toggling SO157. Both values are stored, so
  the device is recognized regardless of how SO157 is set afterward. Existing
  installations automatically acquire dual NodeIDs on first startup.
- **Tasmota firmware version**: Device info shows `"Tasmota X.Y.Z / Powerunit
  VX.Y"`, fetched via `Status 2` command at startup.
- **Dynamic configuration URL**: Device "Visit" link points to the actual
  Tasmota device web UI (`http://{ip}`), fetched via `Status 5` command.
  Falls back to Tasmota docs URL when device IP is unavailable.
- **Serial number**: Device info shows hashed System ID as serial number.
- **Smart relay entity disable**: Detects which named relays are present in
  SENSOR payload; only disables absent ones. Re-enables them automatically
  when they appear.

### Changed

- **SO157 no longer required**: SetOption157 is no longer a prerequisite.
  The integration works with any SO157 setting and any Tasmota version.
- **Canonical ID is hashed**: Entity unique_ids use hashed NodeID (AA55
  prefix) for privacy. Real NodeID stored as anchor for recognition.
- **Renamed sensor**: `powerunit_nodeid` → `system_id` (per @curzon01).
- Named relay entities disabled by default for new installs.
- Device removal allowed from UI.

### Fixed

- **Reliable device metadata fetch**: Status 2/5 fetched using sequential
  send-and-wait commands instead of Backlog to avoid Tasmota dropping
  commands when busy with Modbus polling and SENSOR telemetry.
- **Device migration preserves original**: Original device (with history
  and area assignments) is kept; duplicate removed during NodeID migration.
- **Canonical NodeID migration**: Standalone migration runs on every startup,
  handling entities with real NodeID unique_ids, duplicates from failed
  migrations, and device registry updates.

### Removed

- SO157 runtime enforcement.
- SO157 status display in Options flow.
- `async_query_setoption157()` and `async_ensure_setoption157_enabled()`
  helper functions.

## [0.2.17] - 2026-04-03

### Added

- **7 named relay binary sensors**: Base, Redox, Chlorine, Conductivity,
  Heating, UV, Valve (`NeoPool.Relay.*`) with translations and icons.

### Fixed

- **Modules JSON path**: Corrected `NeoPool.Module` (singular) back to
  `NeoPool.Modules` (plural) per Tasmota source code. The v0.2.16
  change was incorrect.
- **Entity availability AND logic**: Entities marked unavailable when
  JSON key absent from payload. Applied to all entity platforms.
- **Legacy entity cleanup**: Handles unique_ids without NodeID from
  YAML-migrated entities.

### Changed

- Updated `docs/ha_neopool_mqtt_package.yaml` to upstream v4.0.

## [0.2.16] - 2026-04-02

### Fixed

- **Relay.State[n] assumed mapping**: Removed 3 binary sensors
  (relay_ph_state, relay_filtration_state, relay_light_state) that
  incorrectly assumed a fixed physical relay-to-function mapping.
  The relay mapping is configurable per installation. Use named relay
  entities (Relay.Acid, Relay.Base, Relay.Redox, etc.) for functional
  status instead.
- **Module/Modules JSON path bug**: Fixed incorrect JSON path for module
  detection sensors. SENSOR telemetry uses `NeoPool.Module` (singular)
  but code was reading `NeoPool.Modules` (plural). Module presence
  binary sensors now work correctly.

### Added

- **Automatic entity cleanup**: Deprecated relay entities are
  automatically removed from the entity registry on startup.

### Removed

- `RELAY_NAMES` constant (no longer used).
- `relay_ph_state`, `relay_filtration_state`, `relay_light_state`
  binary sensors.

## [0.2.15] - 2026-03-18

### Fixed

- **Config flow stuck on fresh install** (Fixes #9): Restructured the setup
  flow into two clear steps — prerequisite confirmation and migration choice.
  Fresh installs no longer get stuck in the YAML migration path. Added escape
  path when no YAML entities are found.

### Added

- **Orphaned YAML entity cleanup**: During YAML migration, the integration now
  automatically deletes orphaned binary sensor entities that were replaced by
  switch entities (relay_aux1-4_state, relay_filtration_state, relay_light_state).
- **Auto-detection documentation**: Added README section explaining how MQTT
  topic and entity prefix auto-detection work, including limitations.
- **Local brand assets**: Added brand assets for HA 2026.3 brands proxy API.

### Changed

- **Config flow UX**: Split the initial setup into two steps — first confirm
  no active YAML package, then choose between fresh install or migration.
- **Minimum Python version**: Bumped `requires-python` to >=3.13.2 for
  HA 2026.x compatibility.

### Documentation

- **README**: Updated Initial Setup and Migration Steps sections to match
  the restructured config flow. Added "How Auto-Detection Works" subsection.

## [0.2.14] - 2026-01-12

### Added

- **Orphaned YAML entity cleanup**: During YAML migration, the integration now
  automatically deletes orphaned binary sensor entities that were replaced by
  switch entities (relay_aux1-4_state, relay_filtration_state, relay_light_state).
  These entities cannot be migrated cross-domain but are no longer needed since
  the integration's switch entities provide both state and control.

### Documentation

- **Startup validation and runtime monitoring**: Added comprehensive README
  documentation explaining the validation/reconciliation process that runs on
  every Home Assistant startup and the runtime monitoring (SetOption157
  enforcement and device availability).

## [0.2.13] - 2026-01-10

### Fixed

- **NodeID validation false positive**: Fixed `is_nodeid_masked()` incorrectly
  identifying valid unmasked NodeIDs as masked. Valid NodeIDs from Tasmota contain
  spaces between hex groups (e.g., `0026 0051 5443 5016 2036 3435`) which was
  triggering the mask detection. Changed detection from `"xxxx" in nodeid or " " in nodeid`
  to `"xxxx xxxx" in nodeid` pattern matching.

### Changed

- **Consolidated NodeID validation**: Refactored `validate_nodeid()` to use
  `is_nodeid_masked()` internally, creating a single source of truth for
  NodeID validation logic.

### Added

- **Missing entity icons**: Added icons for `boost_mode`, `connection_out_of_range`,
  `hydrolysis_runtime_pol1`, and `hydrolysis_runtime_pol2` sensors in `icons.json`.
- Changed `modules_conductivity` icon from `mdi:flash-triangle` to `mdi:water-sync`.

## [0.2.12] - 2026-01-10

### Fixed

- **SetOption157 MQTT communication reliability**: Complete overhaul of SO157
  query/set logic to fix timeout issues:
  - Fixed response topic: now correctly subscribes to `stat/{topic}/SO` instead
    of `stat/{topic}/RESULT` or `stat/{topic}/SETOPTION157`
  - Fixed command topic: uses short form `cmnd/{topic}/SO157` for queries
  - Added proper `bytes`/`bytearray` payload handling in MQTT message callbacks
  - Added 0.2s delay after subscription to prevent race conditions
  - Added `UnicodeDecodeError` handling for malformed payloads

### Added

- **Runtime SetOption157 enforcement**: Integration now monitors SENSOR data and
  automatically re-enables SO157 if NodeID becomes masked (e.g., if someone
  disables it via Tasmota console). This ensures NodeID visibility is maintained.
- **New helper functions**:
  - `is_nodeid_masked()`: Detects masked NodeID patterns (contains "XXXX" or spaces)
  - `async_query_setoption157()`: Queries current SO157 status via MQTT
  - `async_ensure_setoption157_enabled()`: Send+verify pattern with retries

### Changed

- **Removed SO157 toggle from Options flow**: SetOption157 is now automatically
  enforced by the integration - no manual control needed. The options flow now
  only displays the current SO157 status as informational text.
- Simplified options flow description text across all 10 language files

### Removed

- `setoption157` checkbox from options flow (auto-enforced now)
- `setoption157_change_failed` error message (no longer applicable)

## [0.2.11] - 2026-01-09

### Added

- **Dynamic device info from MQTT**: Device registry now shows actual device
  metadata fetched from MQTT telemetry:
  - **Manufacturer**: Shows actual brand from `NeoPool.Type` (e.g., "Bayrol",
    "Hidrolife", "Aquascenic") instead of static "Sugar Valley"
  - **Firmware version**: Shows actual firmware from `NeoPool.Powerunit.Version`
    (e.g., "V3.45 (Powerunit)") instead of integration version
- **SetOption157 checkbox in Options flow**: View and control Tasmota's
  SetOption157 setting directly from the integration options. Shows current
  status with warning if disabled.
- **Automatic masked NodeID migration**: On startup, the integration detects
  and automatically migrates entities created with masked NodeIDs (containing
  "XXXX"). The migration:
  - Enables SetOption157 on Tasmota if disabled
  - Fetches the real NodeID from telemetry
  - Updates all entity unique_ids
  - Updates config entry and device registry identifiers
  - Preserves all historical data and customizations

### Fixed

- Fixed entity key extraction from masked unique_ids during migration
- Fixed test mocks for SetOption157 MQTT operations

### Changed

- Device info no longer shows integration version as `sw_version` - now shows
  actual device firmware or nothing if unavailable

## [0.2.10] - 2026-01-07

### Fixed

- Fixed `ValueError: New entity ID should be same domain` during YAML migration
- Home Assistant's entity registry doesn't allow cross-domain entity renames
  (e.g., `binary_sensor.x` to `switch.x`)
- Added domain validation check to skip cross-domain mappings gracefully
- Removed invalid `relay_aux*_state` → `aux*` mappings from `YAML_TO_INTEGRATION_KEY_MAP`
  (binary_sensor entities cannot be mapped to switch entities)

## [0.2.9] - 2026-01-07

### Fixed

- Added missing YAML migration key mappings:
  - `ph_ctrl_fl1` → `ph_fl1` for pH flow sensor
  - `relay_aux1-4_state` → `aux1-4` for relay binary sensors to switch mappings
- Fixes migration log errors where entities were not found during YAML migration

## [0.2.8] - 2026-01-07

### Added

- Added `boost_mode` sensor (read-only) to complement the existing `boost_mode` select entity,
  matching the pattern used by `filtration_mode` and `filtration_speed`
- Added missing translations for `boost_mode`, `hydrolysis_runtime_pol1`, `hydrolysis_runtime_pol2`,
  and `connection_out_of_range` sensors to all 10 language files

## [0.2.7] - 2026-01-07

### Fixed

- Fixed hydrolysis_data sensor mapping conflict: YAML's `hydrolysis_data` (%) now correctly
  maps to integration's `hydrolysis_percent`, preventing rename ping-pong with `hydrolysis_data_gh`
- Fixed filtration_mode/speed select entity mapping: entity_id_mapping now stores full entity_id
  (with domain) instead of just object_id, allowing correct domain-aware entity lookup
- Improved `_apply_entity_id_mapping()` to support both old format (object_id only) and new
  format (full entity_id with domain) for backwards compatibility

### Removed

- Removed migration verification and persistent notifications: the verification was unreliable
  due to recorder timing issues. Migration results are now summarized in the config flow only,
  trusting that entity ID preservation works correctly

## [0.2.6] - 2026-01-07

### Fixed

- Fixed YAML migration translation map with correct YAML package entity keys:
  - `hydrolysis_data_gh` (not `hydrolysis_data_g_h`)
  - `hydrolysis_runtime_pol_changes` (not `hydrolysis_runtime_polarity_changes`)
  - `hydrolysis_ctrl_fl1_water_flow` → `hydrolysis_water_flow`
  - `hydrolysis_boost_mode` → `boost_mode`
  - `conndiag_*` variants for connection sensors
  - Added identity mappings for `modules_*` keys

### Added

- Added comprehensive debug logging for migration troubleshooting

## [0.2.5] - 2026-01-07

### Added

- Added missing sensors: `hydrolysis_runtime_pol1`, `hydrolysis_runtime_pol2`, `connection_out_of_range`

### Fixed

- Fixed YAML migration entity ID preservation: added translation map (`YAML_TO_INTEGRATION_KEY_MAP`)
  to bridge naming differences between YAML package and integration entity keys
- Fixed migration verification timing: deferred verification to next HA restart when recorder
  metadata is fully synchronized, preventing false "0 entities with history" reports

## [0.2.4] - 2026-01-06

### Fixed

- Fixed entity migration to preserve original YAML entity IDs during migration
- Fixed device name extraction from migrated entities instead of hardcoding
- Corrected translation placeholders in `yaml_migration_result` config flow step
- Fixed entity registry API usage for entity_id lookup
- Removed unused `platform_domain` argument from entity `__init__` calls
- Fixed entity migration tests for new architecture
- Corrected NodeID assertions in entity tests (TEST123 → ABC123)

### Changed

- Improved test suite reliability with correct mock data and assertions

## [0.2.3] - 2026-01-06

### Added

- Device name configuration in Options flow: users can now customize the device name
- Entity ID regeneration option: checkbox to update entity IDs when device name changes
- DIAGNOSTIC entity category added to connection sensors (requests, responses, no_response)
- **Enhanced YAML migration with history preservation**:
  - Migration now uses DELETE approach to remove old MQTT entities from registry
  - New entities are created with the same `entity_id` to preserve historical data
  - Config flow shows "what will happen" before migration and "what was done" after
  - Persistent notification with final verification assessment after setup completes
  - History verification checks if entities have data older than 1 hour
  - Clear status indicators: ✅ Successful, ⚠️ Partial, ℹ️ No History, ❌ Failed
- **Comprehensive test suite**: Achieved 99% code coverage with extended tests for all modules

### Changed

- `powerunit_nodeid` sensor is now enabled by default (was disabled by default)
- Migration now runs entirely in config flow (before entry creation) for better user feedback
- Updated all 10 translation files with `yaml_migration_result` step

### Fixed

- Fixed blank `yaml_migration_result` step in config flow - migration results now display properly
- Removed all inline `icon=` attributes from entity descriptions - icons now exclusively use `icons.json`
- Fixed test patch targets for recorder history functions

## [0.2.2] - 2026-01-06

### Added

- Active YAML entity detection: config flow now detects existing entities before migration
  and shows a summary step with migration results

### Changed

- Improved config flow: added new `yaml_migration_result` step showing migration summary
  with entity counts and unique_id prefix information

### Fixed

- Fixed test mock for `_find_active_entities` in yaml_confirm flow

## [0.2.1] - 2026-01-06

### Changed

- Improved YAML migration entity detection: now finds entities owned by other platforms (e.g., mqtt)
  in addition to orphaned entities
- Renamed internal methods from "orphaned" to "migratable" for clarity
- Updated all 10 translation files with "migratable" terminology

### Fixed

- Fixed entity detection during YAML migration - entities from YAML packages are now correctly found
- Fixed test for migratable entity detection logic

## [0.2.0] - 2026-01-05

### Added

- **NodeID-based unique IDs**: All entities now use hardware-based NodeID in unique_id pattern
  (`neopool_mqtt_{nodeid}_{entity_key}`)
- **Automatic YAML migration flow**: Guided config flow for migrating from YAML package configuration
  - Checkbox to indicate YAML package migration
  - YAML topic validation with MQTT subscription test
  - Custom topic support (not limited to default "SmartPool")
  - Automatic entity migration with history preservation
- **Automatic Tasmota configuration**: Integration automatically sends `SetOption157 1` to enable NodeID if
  hidden
- **Multi-device support**: NodeID-based identifiers enable stable configuration for multiple NeoPool controllers
- **Powerunit NodeID diagnostic sensor**: Shows the hardware NodeID from the NeoPool controller
- **Comprehensive test suite**: Added tests for all modules achieving 97%+ code coverage

### Changed

- **BREAKING**: Unique ID pattern changed from `neopool_mqtt_{key}` to `neopool_mqtt_{nodeid}_{key}`
  - Automatic migration preserves all historical data for YAML package users
  - Manual setup users will get new entities with NodeID-based IDs
- **Tasmota SetOption157**: Changed from `0` (hide NodeID) to `1` (show NodeID) - required for integration
- Device identifiers now use NodeID instead of topic name
- Config entry unique_id now based on NodeID for proper duplicate detection
- Updated GitHub Actions workflows for improved CI/CD
- Enhanced README with recovery script variables documentation

### Fixed

- Multiple instances of the same device no longer create duplicate entities
- Entity unique IDs are now stable across topic name changes
- Fixed release workflow path (was pointing to wrong directory)
- Corrected repository name in README badges and links

## [0.1.0] - 2024-12-13

### Added

- Initial release
- MQTT integration for Tasmota NeoPool devices
- Support for MQTT auto-discovery
- **Sensors:**
  - Water temperature
  - pH data, state, and pump status
  - Redox (ORP) data
  - Hydrolysis data (%, g/h), state, runtime statistics
  - Filtration mode and speed
  - Powerunit voltages and diagnostics
  - Connection statistics
- **Binary Sensors:**
  - Module presence (pH, Redox, Hydrolysis, Chlorine, Conductivity, Ionization)
  - Relay states (pH, Filtration, Light, Acid)
  - Water flow and tank level indicators
- **Switches:**
  - Filtration on/off
  - Light on/off
  - AUX1-AUX4 relays
- **Select entities:**
  - Filtration mode (Manual, Auto, Heating, Smart, Intelligent, Backwash)
  - Filtration speed (Slow, Medium, Fast)
  - Boost mode (Off, On, On Redox)
- **Number entities:**
  - pH Min/Max setpoints
  - Redox setpoint
  - Hydrolysis setpoint
- **Button:**
  - Clear error state
- Configuration flow with MQTT discovery support
- English translations
