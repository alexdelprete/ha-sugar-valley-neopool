# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
