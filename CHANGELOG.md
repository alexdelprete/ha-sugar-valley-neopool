# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
