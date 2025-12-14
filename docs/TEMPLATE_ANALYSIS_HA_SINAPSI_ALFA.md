# Complete Template Analysis: ha-sinapsi-alfa

**Repository**: <https://github.com/alexdelprete/ha-sinapsi-alfa>
**Author**: Alessandro Del Prete (@alexdelprete)
**Purpose**: Home Assistant custom integration for Sinapsi Alfa energy monitoring devices via Modbus TCP
**License**: MIT
**Current Version**: 1.0.1 (as of December 2025)
**HA Minimum**: 2025.10.0
**Python Minimum**: 3.13.2

______________________________________________________________________

## 1. COMPLETE FOLDER/FILE STRUCTURE

```text
ha-sinapsi-alfa/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug.yml                    # Bug report template
│   │   ├── config.yml                 # Issue template configuration
│   │   └── feature_request.yml        # Feature request template
│   ├── workflows/
│   │   ├── dbautomerge.yml           # Dependabot auto-merge workflow
│   │   ├── lint.yml                  # Code linting workflow
│   │   ├── release.yml               # Release automation workflow
│   │   └── validate.yml              # Hassfest & HACS validation
│   ├── dependabot.yml                # Dependabot configuration
│   ├── FUNDING.yml                   # Sponsorship/funding info
│   └── release-notes-template.md     # Template for release notes
│
├── .vscode/
│   └── settings.json                 # VS Code configuration (optional)
│
├── config/
│   └── configuration.yaml            # Sample HA configuration
│
├── custom_components/
│   └── sinapsi_alfa/
│       ├── translations/
│       │   ├── en.json              # English translations
│       │   └── pt.json              # Portuguese translations
│       ├── __init__.py              # Integration initialization
│       ├── api.py                   # API client implementation
│       ├── config_flow.py           # Configuration UI flow
│       ├── const.py                 # Constants and sensor definitions
│       ├── coordinator.py           # Data update coordinator
│       ├── helpers.py               # Helper utilities
│       ├── manifest.json            # Integration manifest
│       └── sensor.py                # Sensor platform implementation
│
├── docs/
│   ├── analysis/                    # Technical analysis documents
│   ├── releases/                    # Release notes archive
│   └── sunspec-maps/                # Protocol mapping docs (device-specific)
│
├── gfxfiles/                        # Graphics and image files
│
├── scripts/
│   ├── develop                      # Development server script
│   ├── lint                         # Linting script
│   └── setup                        # Setup/installation script
│
├── .devcontainer.json               # Dev container configuration
├── .gitattributes                   # Git attributes (line endings)
├── .gitignore                       # Git ignore rules
├── .markdownlint.json               # Markdown linting config
├── .ruff.toml                       # Ruff Python linter config
├── CHANGELOG.md                     # Version history (Keep a Changelog format)
├── CLAUDE.md                        # Claude AI development guidelines
├── LICENSE                          # MIT License
├── README.md                        # Project documentation
├── hacs.json                        # HACS integration metadata
└── requirements.txt                 # Python dependencies
```

______________________________________________________________________

## 2. GITHUB ACTIONS WORKFLOWS

### 2.1 Release Workflow (`.github/workflows/release.yml`)

**Trigger**: On release publication

**Steps**:

1. Checkout repository with PAT or default token

1. Update version in `manifest.json` using `yq`:

   ```yaml
   yq -i '.version="${{ github.event.release.tag_name }}"' custom_components/sinapsi_alfa/manifest.json
   ```

1. Create ZIP archive from `custom_components/sinapsi_alfa/` directory

1. Upload ZIP to release assets using `softprops/action-gh-release@v2.5.0`

**Key Features**:

- Automatic version synchronization
- ZIP packaging for HACS compatibility
- Uses `actions/checkout@v6.0.1`

### 2.2 Validate Workflow (`.github/workflows/validate.yml`)

**Triggers**:

- Manual dispatch (`workflow_dispatch`)
- Every push
- Pull requests
- Daily schedule at midnight UTC (`cron: '0 0 * * *'`)

**Jobs**:

**Hassfest Validation**:

- Validates integration meets Home Assistant standards
- Uses `home-assistant/actions/hassfest@master`

**HACS Validation**:

- Validates HACS compatibility
- Uses `hacs/action@main` with `category: "integration"`
- Note: Includes commented option for `ignore: "brands"` once added to brands repository

### 2.3 Lint Workflow (`.github/workflows/lint.yml`)

**Triggers**:

- Pushes to `master` branch
- All pull requests

**Steps**:

1. Checkout repository
1. Setup Python 3.13 with pip caching
1. Install dependencies from `requirements.txt`
1. Run `ruff format .` to auto-format
1. Run `ruff check .` to lint
1. Auto-commit formatting changes with message "Style fixes by ruff"
   - Uses `stefanzweifel/git-auto-commit-action@v5.0.1`

**Permissions**: Write access to contents (for auto-commit)

### 2.4 Dependabot Auto-Merge (`.github/workflows/dbautomerge.yml`)

**Trigger**: All pull requests

**Conditions**:

- Only runs for Dependabot PRs
- Auto-merges unless it's a major version bump (except GitHub Actions)

**Logic**:

```yaml
if: steps.metadata.outputs.update-type != 'version-update:semver-major' ||
    steps.metadata.outputs.dependency-type == 'direct:production'
```

**Method**: Squash merge

______________________________________________________________________

## 3. PROJECT DOCUMENTATION STRUCTURE

### 3.1 README.md

**Structure**:

1. Title and badges (stars, forks, license)
1. Description
1. Features overview
1. Installation methods (HACS + Manual)
1. Configuration parameters
1. Important disclaimers

**Key Elements**:

- HACS installation button
- Clear step-by-step instructions
- Configuration UI screenshots (likely in gfxfiles/)
- Link to documentation

### 3.2 CLAUDE.md - AI Development Guidelines

**Critical Sections**:

1. **Mandatory Starting Actions**:

   - Read entire guidelines document
   - Review recent git commits
   - Run `git status`

1. **Project Architecture Overview**:

   - Core components explanation
   - Data flow patterns
   - Integration type details

1. **Coding Standards**:

   - Data storage patterns (use `runtime_data`, not `hass.data`)
   - Error handling (custom exceptions)
   - Logging patterns (use helpers, no f-strings in logger calls)
   - Type hints requirements

1. **Release Management Rules**:

   - **NEVER create tags/releases without explicit user instruction**
   - Step-by-step release process
   - Version bump requirements (manifest.json + const.py)

1. **Device-Specific Details**:

   - Sensor counts and types
   - Special value handling
   - Market-specific naming conventions

### 3.3 CHANGELOG.md

**Format**: Follows [Keep a Changelog](https://keepachangelog.com/)

**Structure**:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.0.1] - 2025-12-11

### Fixed
- Inverted import/export sensor icons

## [1.0.0] - 2025-12-07

### Added
- New feature descriptions

### Changed
- Breaking changes

### Fixed
- Bug fixes

### Performance
- Performance improvements
```

**Categories Used**:

- Added
- Changed
- Fixed
- Performance
- Dependencies
- Documentation

**Version Requirements Note**:

- Specifies minimum HA and Python versions for major releases

______________________________________________________________________

## 4. RELEASE MANAGEMENT APPROACH

### 4.1 Versioning Strategy

**Follows Semantic Versioning** (SemVer):

- MAJOR.MINOR.PATCH (e.g., 1.0.1)
- Beta releases: 1.0.0-beta.1, 1.0.0-beta.2, etc.

**Version Locations** (must be synchronized):

1. `custom_components/sinapsi_alfa/manifest.json` - `"version"` field
1. `custom_components/sinapsi_alfa/const.py` - `VERSION` constant
1. Git tags (e.g., `v1.0.1`)

### 4.2 Release Process

1. **Development Phase**:

   - Make code changes
   - Test thoroughly
   - Beta releases for major changes

1. **Pre-Release**:

   - Update `CHANGELOG.md` with all changes
   - Create release notes using `.github/release-notes-template.md`
   - Update version in `manifest.json` and `const.py`
   - Commit changes

1. **Release Creation**:

   - Create GitHub release (manual)
   - Workflow automatically:
     - Updates manifest.json version
     - Creates ZIP archive
     - Attaches to release

1. **Post-Release**:

   - Copy release notes to `docs/releases/`
   - Verify HACS picks up new release

### 4.3 Release Notes Template

**File**: `.github/release-notes-template.md`

**Sections**:

- Features & Improvements
- Bug Fixes
- Code Quality & Maintainability
- Breaking Changes (optional)
- Dependencies
- Technical Details
- Testing

**Process**: Rename to `release-notes-vX.Y.Z.md` when used

______________________________________________________________________

## 5. HA QUALITY SCALE COMPLIANCE PATTERNS

### 5.1 Bronze Tier Requirements ✓

**Config Flow**:

- ✓ UI-based setup (no YAML configuration)
- ✓ Input validation
- ✓ Duplicate prevention
- ✓ Connection testing

**Code Quality**:

- ✓ Follows Home Assistant coding standards
- ✓ Uses Ruff linter with HA-recommended rules
- ✓ Auto-formatting with Ruff
- ✓ Basic error handling

**Testing**:

- ✓ Hassfest validation
- ✓ HACS validation

**Documentation**:

- ✓ README with setup instructions
- ✓ Configuration parameter documentation

### 5.2 Silver Tier Requirements ✓

**Code Owners**:

- ✓ Defined in `manifest.json`: `"codeowners": ["@alexdelprete"]`

**Error Handling**:

- ✓ Custom exceptions (`SinapsiConnectionError`, `SinapsiModbusError`)
- ✓ Automatic recovery from connection errors
- ✓ Raises `ConfigEntryNotReady` for transient failures
- ✓ Retry logic with exponential backoff
- ✓ Distinguishes retriable vs. permanent errors

**Logging**:

- ✓ Structured logging via helpers
- ✓ Context-aware log messages
- ✓ Appropriate log levels (debug, info, warning, error)
- ✓ No sensitive data in logs

**Documentation**:

- ✓ Detailed README
- ✓ Troubleshooting guidance
- ✓ Issue templates for bug reports

### 5.3 Gold Tier Targets

**Discovery**:

- ⚠ Not applicable (requires device IP address)

**Reconfiguration**:

- ✓ Options flow for updating host, port, scan interval
- ✓ `async_reload_entry` on config changes

**Translations**:

- ✓ English (en.json)
- ✓ Portuguese (pt.json)
- ✓ Extensible structure

**Updates**:

- ⚠ Not applicable (device firmware updates not supported via integration)

**Testing**:

- ⚠ Could expand automated test coverage

### 5.4 Platinum Tier Targets

**Type Annotations**:

- ✓ Type hints on all functions
- ✓ Uses dataclasses for structured data
- ✓ Proper typing imports

**Async Code**:

- ✓ Fully asynchronous implementation
- ✓ Uses `async_add_executor_job` for sync operations (MAC address retrieval)
- ✓ No blocking I/O in event loop

**Code Quality**:

- ✓ Comprehensive Ruff rules (~100+ checks)
- ✓ Complexity limits enforced (max cyclomatic complexity: 25)
- ✓ Code comments for complex logic
- ✓ Clear variable naming

**Efficiency**:

- ✓ Batched Modbus reads (~75% request reduction)
- ✓ Data caching in coordinator
- ✓ Connection pooling via ModbusLink
- ✓ Configurable polling intervals

______________________________________________________________________

## 6. CODE ORGANIZATION PATTERNS

### 6.1 `__init__.py` - Integration Entry Point

**Structure**:

```python
"""The Sinapsi Alfa integration."""

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

# Constants
PLATFORMS: list[Platform] = [Platform.SENSOR]

# Runtime data structure
@dataclass
class RuntimeData:
    """Runtime data for the integration."""
    coordinator: SinapsiAlfaCoordinator

# Setup function
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    # 1. Create coordinator
    # 2. Perform first refresh
    # 3. Check connection (raise ConfigEntryNotReady if fails)
    # 4. Store in runtime_data
    # 5. Register device
    # 6. Forward setup to platforms
    # 7. Add update listener

# Unload function
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # 1. Unload platforms
    # 2. Close API connections (only if unload successful)

# Update listener
@callback
def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""

# Device registry helper
async def async_update_device_registry(
    hass: HomeAssistant, entry: ConfigEntry, coordinator
) -> None:
    """Update device registry."""

# Device removal prevention
async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device
) -> bool:
    """Prevent device deletion."""
    return False
```

**Key Patterns**:

- Uses `runtime_data` (modern approach) instead of `hass.data[DOMAIN]`
- Dataclass for type-safe runtime storage
- `ConfigEntryNotReady` for transient failures
- Update listener for config changes
- Manual device registration for better control
- Prevents device deletion (redirects to integration removal)

### 6.2 `const.py` - Constants and Definitions

**Structure**:

```python
"""Constants for the Sinapsi Alfa integration."""

from homeassistant.const import Platform
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)

# Integration identity
DOMAIN = "sinapsi_alfa"
NAME = "Sinapsi Alfa"
VERSION = "1.0.1"

# Platforms
PLATFORMS: list[Platform] = [Platform.SENSOR]

# Configuration
CONF_NAME = "name"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_NAME = "Sinapsi Alfa"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 60

# Limits
MIN_PORT = 1
MAX_PORT = 65535
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 600

# API Configuration
MODBUS_DEVICE_ID = 1
CONNECTION_TIMEOUT = 5
SOCKET_TIMEOUT = 3.0
MAX_RETRIES = 10

# Device Info
MANUFACTURER = "Sinapsi"
MODEL = "Alfa"

# Special Values
INVALID_DISCONNECTION = 65535
MAX_EVENT_VALUE = 4294967294

# Modbus Register Batches (for optimization)
MODBUS_BATCHES = [
    {"start": 1000, "count": 10, "description": "Power & Energy basics"},
    {"start": 1020, "count": 12, "description": "Daily tariffs"},
    # ... more batches
]

# Sensor Definitions
SENSOR_ENTITIES = [
    {
        "key": "power_drawn",
        "name": "Potenza Prelevata",
        "register_type": "holding",
        "register": 1000,
        "data_type": "uint32",
        "scale": 0.001,
        "unit": "kW",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:transmission-tower-import",
    },
    # ... more sensors
]
```

**Key Patterns**:

- Single source of truth for all constants
- Grouped by category (identity, config, limits, API, device, etc.)
- Sensor definitions as list of dicts (easy to iterate)
- Uses HA's device classes and state classes
- Special value definitions for edge cases
- Batch read configuration for optimization

### 6.3 `config_flow.py` - Configuration UI

**Structure**:

```python
"""Config flow for Sinapsi Alfa."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
        vol.Coerce(int), vol.Clamp(min=MIN_PORT, max=MAX_PORT)
    ),
    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
    ),
})

class SinapsiAlfaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow handler."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        errors = {}

        if user_input is not None:
            # Validate host format
            if not host_valid(user_input[CONF_HOST]):
                errors["base"] = "invalid_host"

            # Check for duplicates
            if self._host_in_configuration_exists(user_input[CONF_HOST]):
                errors["base"] = "already_configured"

            # Test connection
            unique_id = await self.get_unique_id(user_input)
            if not unique_id:
                errors["base"] = "cannot_connect"

            # Create entry
            if not errors:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )

    async def get_unique_id(self, config):
        """Get unique ID from device."""
        try:
            api = SinapsiAlfaAPI(...)
            await api.async_get_data()
            return api.data.get("serial_number")
        except (ConnectionException, SinapsiConnectionError, SinapsiModbusError):
            return False

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get options flow handler."""
        return SinapsiAlfaOptionsFlow(config_entry)

class SinapsiAlfaOptionsFlow(config_entries.OptionsFlow):
    """Options flow handler."""

    async def async_step_init(self, user_input=None):
        """Handle options step."""
        # Similar validation to user step
        # Updates config_entry.data with new values
```

**Key Patterns**:

- Voluptuous schema with `vol.Clamp()` for range validation
- Custom validation functions (e.g., `host_valid()`)
- Duplicate detection via unique ID
- Connection testing before entry creation
- Separate options flow for reconfiguration
- Clear error messages mapped to translations
- Preserves immutable fields (e.g., NAME) during reconfiguration

### 6.4 `coordinator.py` - Data Update Coordinator

**Structure**:

```python
"""Data Update Coordinator."""

from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

class SinapsiAlfaCoordinator(DataUpdateCoordinator):
    """Manage data updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Extract config
        self.conf_name = config_entry.data.get(CONF_NAME)
        self.conf_host = config_entry.data.get(CONF_HOST)
        self.conf_port = config_entry.data.get(CONF_PORT)
        self.scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL)

        # Enforce bounds
        self.scan_interval = max(MIN_SCAN_INTERVAL,
                                  min(MAX_SCAN_INTERVAL, self.scan_interval))

        # Initialize parent
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_method=self.async_update_data,
            update_interval=timedelta(seconds=self.scan_interval),
        )

        # Create API client
        self.api = SinapsiAlfaAPI(...)

        # Tracking
        self.last_update_time = datetime.now()
        self.last_update_success = True

    async def async_update_data(self):
        """Update data."""
        try:
            self.last_update_status = await self.api.async_get_data()
            self.last_update_time = datetime.now()
            return self.last_update_status
        except Exception as ex:
            self.last_update_status = False
            raise UpdateFailed from ex
```

**Key Patterns**:

- Extends `DataUpdateCoordinator`
- Config validation in `__init__`
- Bounds enforcement for scan interval
- Single API client instance
- Timestamp and status tracking
- Raises `UpdateFailed` on errors (triggers unavailable state)
- Update interval as `timedelta`

### 6.5 `api.py` - API Client

**Structure**:

```python
"""API Client for Sinapsi Alfa."""

import socket
from getmac import get_mac_address
from modbuslink import ModbusLink

# Custom Exceptions
class SinapsiConnectionError(Exception):
    """Connection error."""
    def __init__(self, host: str, port: int, message: str):
        self.host = host
        self.port = port
        super().__init__(message)

class SinapsiModbusError(Exception):
    """Modbus protocol error."""
    def __init__(self, address: int, operation: str, message: str):
        self.address = address
        self.operation = operation
        super().__init__(message)

class SinapsiAlfaAPI:
    """API Client."""

    def __init__(self, hass, name, host, port, scan_interval):
        """Initialize API."""
        self.hass = hass
        self.name = name
        self.host = host
        self.port = port

        # Initialize data structure
        self.data = {sensor["key"]: None for sensor in SENSOR_ENTITIES}

        # Connection tracking
        self._connection_healthy = False
        self._last_successful_read = None

        # Create Modbus client
        self.modbus = ModbusLink(
            host=host,
            port=port,
            device_id=MODBUS_DEVICE_ID,
            timeout=SOCKET_TIMEOUT,
        )

    async def async_get_data(self) -> bool:
        """Get all data from device."""

        # Pre-flight check
        if not await self._check_port_open():
            raise SinapsiConnectionError(self.host, self.port, "Port closed")

        # Read all batches sequentially (avoid transaction ID conflicts)
        for batch in MODBUS_BATCHES:
            values = await self._read_batch(
                batch["start"],
                batch["count"],
                batch.get("type", "holding")
            )
            self._process_batch_values(batch, values)

        # Calculate derived values
        self._calculate_derived_values()

        self._connection_healthy = True
        self._last_successful_read = datetime.now()
        return True

    async def _read_batch(self, start: int, count: int, reg_type: str):
        """Read register batch with retries."""

        for attempt in range(MAX_RETRIES):
            try:
                if reg_type == "holding":
                    return await self.modbus.read_holding_registers(start, count)
                else:
                    return await self.modbus.read_input_registers(start, count)

            except (ConnectionError, TimeoutError) as ex:
                # Retriable errors
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise SinapsiConnectionError(self.host, self.port, str(ex))

            except (CRCError, ProtocolError) as ex:
                # Non-retriable errors
                raise SinapsiModbusError(start, "read", str(ex))

    async def _check_port_open(self) -> bool:
        """Check if TCP port is open."""
        def _sync_check():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECTION_TIMEOUT)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0

        return await self.hass.async_add_executor_job(_sync_check)

    async def get_mac_address(self) -> str:
        """Get device MAC address."""

        def _sync_get_mac():
            return get_mac_address(ip=self.host)

        for attempt in range(3):
            mac = await self.hass.async_add_executor_job(_sync_get_mac)
            if mac:
                return mac
            await asyncio.sleep(1)

        # Fallback to host:port
        return f"{self.host}:{self.port}"

    async def close(self):
        """Close connections."""
        await self.modbus.close()
```

**Key Patterns**:

- Custom exception classes with context
- Data structure initialization
- Connection health tracking
- Batch reading for efficiency
- Retry logic with exponential backoff
- Distinction between retriable and permanent errors
- Sync operations via `async_add_executor_job`
- Graceful fallbacks (MAC address)
- IPv4 forcing to avoid IPv6 timeout issues
- Resource cleanup method

### 6.6 `sensor.py` - Sensor Platform

**Structure**:

```python
"""Sensor platform."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    runtime_data: RuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    # Get device info
    manufacturer = coordinator.api.data.get("manufacturer", MANUFACTURER)
    model = coordinator.api.data.get("model", MODEL)
    serial = coordinator.api.data.get("serial_number")

    # Create sensors (filter out None values)
    sensors = [
        SinapsiAlfaSensor(
            coordinator,
            sensor,
            manufacturer,
            model,
            serial,
        )
        for sensor in SENSOR_ENTITIES
        if coordinator.api.data.get(sensor["key"]) is not None
    ]

    async_add_entities(sensors)

class SinapsiAlfaSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_def, manufacturer, model, serial):
        """Initialize sensor."""
        super().__init__(coordinator)

        self._sensor = sensor_def
        self._attr_name = sensor_def["name"]
        self._attr_unique_id = f"{DOMAIN}_{serial}_{sensor_def['key']}"
        self._attr_native_unit_of_measurement = sensor_def.get("unit")
        self._attr_device_class = sensor_def.get("device_class")
        self._attr_state_class = sensor_def.get("state_class")
        self._attr_icon = sensor_def.get("icon")

        # Set entity category for diagnostic sensors
        if not self._attr_state_class:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Device info (links sensor to device)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": coordinator.conf_name,
            "manufacturer": manufacturer,
            "model": model,
            "serial_number": serial,
            "configuration_url": f"http://{coordinator.conf_host}",
        }

    @property
    def native_value(self):
        """Return sensor value."""
        return self.coordinator.api.data.get(self._sensor["key"])

    @property
    def available(self) -> bool:
        """Return availability."""
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data."""
        self.async_write_ha_state()
```

**Key Patterns**:

- Multiple inheritance: `CoordinatorEntity` + `SensorEntity`
- `_attr_has_entity_name = True` for device-based naming
- Unique ID format: `{domain}_{serial}_{key}`
- Device info linking all sensors to same device
- Entity category for diagnostic sensors
- Native value from coordinator data
- Availability tied to coordinator success
- No polling (`should_poll = False` inherited)
- Callback decorator for update handler

### 6.7 `helpers.py` - Utility Functions

**Structure**:

```python
"""Helper utilities."""

import ipaddress
import logging
import re
from datetime import datetime, timezone

def host_valid(host: str) -> bool:
    """Validate hostname or IP address."""
    # Try parsing as IP
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    # Validate as hostname
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(pattern, host))

def unix_timestamp_to_iso8601_local_tz(unix_timestamp: int) -> str:
    """Convert Unix timestamp to ISO8601 with local timezone."""
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    local_dt = dt.astimezone()
    return local_dt.isoformat()

def log_debug(
    logger: logging.Logger, context: str, message: str, **kwargs
) -> None:
    """Structured debug logging."""
    extra = " ".join(f"[{k}={v}]" for k, v in kwargs.items())
    logger.debug("(%s) %s %s", context, message, extra)

def log_info(logger: logging.Logger, context: str, message: str, **kwargs) -> None:
    """Structured info logging."""
    extra = " ".join(f"[{k}={v}]" for k, v in kwargs.items())
    logger.info("(%s) %s %s", context, message, extra)

def log_warning(
    logger: logging.Logger, context: str, message: str, **kwargs
) -> None:
    """Structured warning logging."""
    extra = " ".join(f"[{k}={v}]" for k, v in kwargs.items())
    logger.warning("(%s) %s %s", context, message, extra)

def log_error(logger: logging.Logger, context: str, message: str, **kwargs) -> None:
    """Structured error logging."""
    extra = " ".join(f"[{k}={v}]" for k, v in kwargs.items())
    logger.error("(%s) %s %s", context, message, extra)
```

**Key Patterns**:

- Validation functions
- Type conversions
- Structured logging with context
- Keyword arguments for metadata
- No f-strings in logger calls (deferred formatting)
- Consistent logging format across integration

______________________________________________________________________

## 7. HACS INTEGRATION SETUP

### 7.1 `hacs.json`

```json
{
  "name": "Alfa by Sinapsi",
  "homeassistant": "2025.10.0",
  "content_in_root": false,
  "render_readme": true,
  "zip_release": true,
  "filename": "sinapsi_alfa.zip"
}
```

**Key Fields**:

- `name`: Display name in HACS
- `homeassistant`: Minimum HA version
- `content_in_root`: `false` (integration in `custom_components/` subdirectory)
- `render_readme`: `true` (show README in HACS)
- `zip_release`: `true` (use ZIP from releases)
- `filename`: ZIP file name pattern

### 7.2 `manifest.json`

```json
{
  "domain": "sinapsi_alfa",
  "name": "Alfa by Sinapsi",
  "codeowners": ["@alexdelprete"],
  "config_flow": true,
  "documentation": "https://github.com/alexdelprete/ha-sinapsi-alfa",
  "integration_type": "hub",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/alexdelprete/ha-sinapsi-alfa/issues",
  "loggers": ["custom_components.sinapsi_alfa"],
  "requirements": ["modbuslink>=1.2.0", "getmac>=0.9.5"],
  "single_config_entry": true,
  "version": "1.0.1"
}
```

**Key Fields**:

- `domain`: Unique integration identifier (lowercase, underscores)
- `name`: Display name
- `codeowners`: GitHub usernames for notifications
- `config_flow`: UI configuration support
- `documentation`: Link to docs
- `integration_type`: "hub" (manages device), "device", "service", etc.
- `iot_class`: "local_polling", "local_push", "cloud_polling", etc.
- `issue_tracker`: Bug reporting URL
- `loggers`: Logger names for debug logging
- `requirements`: Python dependencies (from PyPI)
- `single_config_entry`: Allow only one instance
- `version`: Current version (auto-updated by release workflow)

**Integration Types**:

- `hub`: Manages a device/service that provides multiple entities
- `device`: Single device
- `service`: Cloud service
- `helper`: Utility integration

**IoT Classes**:

- `local_polling`: Local network, polls device
- `local_push`: Local network, device pushes updates
- `cloud_polling`: Cloud service, polls API
- `cloud_push`: Cloud service, pushes updates
- `calculated`: Derives data from other integrations

______________________________________________________________________

## 8. PRE-COMMIT HOOKS AND CODE QUALITY TOOLS

### 8.1 Ruff Configuration (`.ruff.toml`)

```toml
target-version = "py313"

[lint]
select = [
    "A",     # flake8-builtins
    "ASYNC", # flake8-async
    "B",     # flake8-bugbear
    "C4",    # flake8-comprehensions
    "DTZ",   # flake8-datetimez
    "E",     # pycodestyle errors
    "F",     # Pyflakes
    "I",     # isort
    "ICN",   # flake8-import-conventions
    "N",     # pep8-naming
    "PIE",   # flake8-pie
    "PL",    # Pylint
    "PT",    # flake8-pytest-style
    "PYI",   # flake8-pyi
    "RET",   # flake8-return
    "RSE",   # flake8-raise
    "RUF",   # Ruff-specific rules
    "S",     # flake8-bandit (security)
    "SIM",   # flake8-simplify
    "T10",   # flake8-debugger
    "T20",   # flake8-print
    "TCH",   # flake8-type-checking
    "TID",   # flake8-tidy-imports
    "UP",    # pyupgrade
    "W",     # pycodestyle warnings
]

ignore = [
    "PLR0911",  # Too many return statements
    "PLR0912",  # Too many branches
    "PLR0913",  # Too many arguments
    "PLR0915",  # Too many statements
    "PLR2004",  # Magic value in comparison
    # ... others that conflict with formatter
]

[lint.flake8-pytest-style]
fixture-parentheses = false

[lint.mccabe]
max-complexity = 25

[lint.per-file-ignores]
"tests/**" = ["PLC1901"]  # Allow empty strings in tests

[format]
exclude = [
    ".vscode",
    ".devcontainer",
    ".github",
]
```

**Key Configuration**:

- Python 3.13 target
- ~100+ linting rules enabled
- Strategic ignores for false positives
- Max cyclomatic complexity: 25
- Pytest style configuration
- Format exclusions for config files

### 8.2 Markdown Linting (`.markdownlint.json`)

```json
{
  "MD024": { "siblings_only": true },
  "MD050": { "style": "asterisk" },
  "MD013": { "line_length": 120 },
  "MD033": false,
  "MD041": false
}
```

**Rules**:

- MD024: Duplicate headings only within same level
- MD050: Use asterisks for emphasis
- MD013: Max line length 120 characters
- MD033: Allow inline HTML
- MD041: Allow files without top-level heading

### 8.3 Dependabot Configuration (`.github/dependabot.yml`)

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "daily"
      time: "21:00"
      timezone: "Europe/Rome"

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
      time: "21:00"
      timezone: "Europe/Rome"
    ignore:
      - dependency-name: "homeassistant"
        # Should match homeassistant key in hacs.json
```

**Key Points**:

- Daily checks for both GitHub Actions and Python packages
- Scheduled at specific time/timezone
- Ignores Home Assistant updates (managed via hacs.json)
- Works with dbautomerge workflow

### 8.4 Git Configuration

**.gitattributes**:

```text
* text=auto eol=lf
```

- Normalizes line endings to LF (Unix-style)
- Auto-detection of text files

**.gitignore**:

```text
# artifacts
__pycache__
.pytest*
*.egg-info
*/build/*
*/dist/*

# misc
.coverage
.vscode
.zed
coverage.xml
enforce_branch_protection.sh
settings.local.json

# Home Assistant configuration
config/*
!config/configuration.yaml
```

______________________________________________________________________

## 9. TRANSLATION STRUCTURE

### 9.1 Directory Structure

```text
custom_components/sinapsi_alfa/
├── translations/
│   ├── en.json          # English (required)
│   └── pt.json          # Portuguese
└── strings.json         # Base strings (optional, usually same as en.json)
```

### 9.2 Translation File Format (`translations/en.json`)

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Alfa Connection Configuration",
        "description": "If you need help with the configuration go to: https://github.com/alexdelprete/ha-sinapsi-alfa",
        "data": {
          "name": "Custom Name of the device (used for sensors' prefix)",
          "host": "IP or hostname",
          "port": "TCP port",
          "scan_interval": "Polling Period (min: 30s max: 600s)"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_host": "Invalid hostname or IP address",
      "already_configured": "Device is already configured",
      "unknown": "Unexpected error occurred"
    },
    "abort": {
      "already_configured": "Device is already configured"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Alfa Connection Options",
        "description": "Set Connection Options",
        "data": {
          "host": "IP or hostname",
          "port": "TCP port",
          "scan_interval": "Polling Period (min: 30s max: 600s)"
        }
      }
    }
  }
}
```

**Structure**:

- `config`: Initial setup flow
  - `step`: Each step in config flow
    - `user`: User-initiated step
      - `title`: Step title
      - `description`: Help text
      - `data`: Field labels
  - `error`: Error messages (mapped from `config_flow.py`)
  - `abort`: Abort reasons
- `options`: Options flow (reconfiguration)

### 9.3 Translation Best Practices

1. **Always provide `en.json`** (English is required)
1. **Match keys exactly** with code references
1. **Use descriptive text** for user guidance
1. **Include help links** in descriptions
1. **Map error codes** from config flow
1. **Translate user-facing strings only** (not internal keys)
1. **Keep translations synchronized** across languages

______________________________________________________________________

## 10. ADDITIONAL BEST PRACTICES

### 10.1 Development Environment

**DevContainer** (`.devcontainer.json`):

- Python 3.12 base image (Debian Bullseye)
- VS Code extensions:
  - Python language support
  - Ruff linter/formatter
  - GitHub integration
  - Coverage visualization
- Format-on-save enabled
- Auto-import organization
- 4-space indentation
- Unix line endings

**Scripts**:

**`scripts/setup`**:

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
python3 -m pip install --requirement requirements.txt
```

**`scripts/develop`**:

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# Create config if not exists
[ -d config ] || mkdir config
hass --config "${PWD}/config" --script ensure_config

# Set PYTHONPATH and run
export PYTHONPATH="${PYTHONPATH}:${PWD}/custom_components"
hass --config "${PWD}/config" --debug
```

**`scripts/lint`**:

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
ruff check . --fix
```

### 10.2 Issue Templates

**Bug Report** (`.github/ISSUE_TEMPLATE/bug.yml`):

- System health data
- Checklist (debug logging, no duplicates, etc.)
- Issue description
- Reproduction steps (required)
- Debug logs (from startup to error)
- Optional diagnostics dump

**Feature Request** (`.github/ISSUE_TEMPLATE/feature_request.yml`):

- Checklist (completeness, no duplicates)
- Problem description
- Proposed solution
- Alternative approaches
- Additional context

**Config** (`.github/ISSUE_TEMPLATE/config.yml`):

```yaml
blank_issues_enabled: false
contact_links:
  - name: Support
    url: https://github.com/alexdelprete/ha-sinapsi-alfa/discussions
    about: Questions? Problems? Get help here
  - name: Feature requests
    url: https://github.com/alexdelprete/ha-sinapsi-alfa/discussions/categories/ideas
    about: Share ideas for new features
  - name: General inquiries
    url: https://github.com/alexdelprete/ha-sinapsi-alfa/discussions/categories/general
    about: For anything else or uncertain matters
```

### 10.3 Documentation Standards

**README.md Structure**:

1. Title and badges
1. Description and features
1. Installation (HACS + manual)
1. Configuration
1. Troubleshooting
1. Contributing
1. License
1. Disclaimers

**CLAUDE.md** (AI Guidelines):

- Mandatory starting checklist
- Project overview
- Architecture details
- Coding standards
- Release procedures
- Device-specific details
- Common pitfalls

**CHANGELOG.md**:

- Keep a Changelog format
- Semantic versioning
- Categorized changes
- Version requirements noted

### 10.4 Code Style Standards

**Type Hints**:

```python
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up from config entry."""
```

**Logging**:

```python
# Use helpers, not f-strings
log_debug(_LOGGER, "async_update_data", "Update completed", time=datetime.now())

# Not this:
# _LOGGER.debug(f"Update completed at {datetime.now()}")
```

**Error Handling**:

```python
# Custom exceptions with context
try:
    result = await api.read()
except ConnectionError as ex:
    raise SinapsiConnectionError(host, port, str(ex)) from ex
```

**Async Patterns**:

```python
# Use async_add_executor_job for sync operations
mac = await hass.async_add_executor_job(get_mac_address, host)

# Not this:
# mac = get_mac_address(host)  # Blocks event loop!
```

### 10.5 Testing Approach

**Validation**:

- Hassfest (Home Assistant standards)
- HACS validation
- Ruff linting
- Manual testing with real devices

**Future Improvements**:

- Unit tests with pytest
- Integration tests
- Mock device responses
- CI/CD test automation

### 10.6 Performance Optimizations

**Batch Operations**:

- Group consecutive Modbus registers
- ~75% request reduction (20 → 5 reads)
- Sequential processing to avoid transaction conflicts

**Connection Pooling**:

- Single ModbusLink client per coordinator
- Reuse connections across reads
- Proper cleanup on unload

**Caching**:

- Data stored in coordinator
- All sensors read from cache
- No duplicate API calls

**Configurable Polling**:

- User-adjustable scan interval (30-600s)
- Bounds enforcement
- Balance between freshness and load

### 10.7 Security Considerations

**Local-Only Communication**:

- Direct IP connection (no cloud)
- User's network only
- No external data transmission

**Input Validation**:

- Host format validation
- Port range checking
- Scan interval bounds

**Error Information**:

- No sensitive data in logs
- Connection details only when needed
- Safe error messages to users

### 10.8 Accessibility and UX

**Device Naming**:

- `has_entity_name = True` for clean naming
- User-configurable device prefix
- Descriptive sensor names

**Entity Organization**:

- Device grouping (all sensors under one device)
- Entity categories (diagnostic vs. measurement)
- Appropriate device classes

**Icons**:

- MDI icons for visual clarity
- Context-appropriate (e.g., transmission tower for grid power)

**Availability**:

- Sensors marked unavailable on connection failure
- Clear distinction between "0" and "unavailable"

### 10.9 Maintenance Practices

**Dependencies**:

- Specify minimum versions (`>=1.2.0`)
- Use Dependabot for updates
- Test compatibility before merging

**Backwards Compatibility**:

- Migration code (commented out when not needed)
- Preserve unique IDs across versions
- Careful with config entry changes

**Code Ownership**:

- Defined codeowners in manifest
- GitHub notifications for maintainers
- Community contributions welcome

**Documentation Maintenance**:

- Update README with new features
- Keep CHANGELOG current
- Sync translations

______________________________________________________________________

## 11. QUALITY SCALE COMPLIANCE CHECKLIST

### Bronze Tier ✓

- [x] UI-based config flow
- [x] Input validation
- [x] Duplicate prevention
- [x] Connection testing
- [x] Ruff linting
- [x] Hassfest validation
- [x] HACS validation
- [x] Basic documentation

### Silver Tier ✓

- [x] Code owners defined
- [x] Custom exceptions
- [x] Automatic error recovery
- [x] Retry logic
- [x] ConfigEntryNotReady
- [x] Structured logging
- [x] Detailed documentation
- [x] Issue templates

### Gold Tier (Partial)

- [x] Options flow (reconfiguration)
- [x] Translations (multiple languages)
- [x] Detailed documentation
- [x] Auto-reload on config change
- [ ] Device discovery (N/A - requires IP)
- [ ] Firmware updates (N/A - device limitation)
- [ ] Comprehensive automated tests

### Platinum Tier (Partial)

- [x] Full type annotations
- [x] Fully asynchronous
- [x] Code comments
- [x] Ruff comprehensive rules
- [x] Batched operations
- [x] Data caching
- [x] Connection pooling
- [ ] 100% test coverage

______________________________________________________________________

## 12. RELEASE WORKFLOW EXAMPLE

### Step-by-Step Process

**1. Development**:

```bash
# Make changes
git checkout -b feature/new-sensor

# Test locally
scripts/develop

# Lint
scripts/lint

# Commit
git commit -m "Add new sensor for XYZ"
git push origin feature/new-sensor
```

**2. Pre-Release**:

```bash
# Update CHANGELOG.md
## [1.1.0] - 2025-12-15

### Added
- New sensor for XYZ measurement

### Fixed
- Connection timeout issue

# Update version in TWO places:
# 1. custom_components/sinapsi_alfa/manifest.json
{
  "version": "1.1.0"
}

# 2. custom_components/sinapsi_alfa/const.py
VERSION = "1.1.0"

# Commit version bump
git commit -am "Bump version to 1.1.0"
git push
```

**3. Create Release** (GitHub UI):

- Tag: `v1.1.0`
- Title: `v1.1.0`
- Description: Copy from CHANGELOG
- Publish release

**4. Automatic Actions** (via workflow):

- Checkout code
- Update manifest.json version (redundant now, but ensures sync)
- Create `sinapsi_alfa.zip`
- Upload to release

**5. HACS Detection**:

- HACS automatically detects new release
- Users see update available
- One-click update in HACS

**6. Post-Release**:

```bash
# Copy release notes to archive
cp .github/release-notes-v1.1.0.md docs/releases/

# Clean up template
cp .github/release-notes-template.md .github/release-notes-v1.2.0.md

git commit -am "Archive release notes"
git push
```

______________________________________________________________________

## 13. MIGRATION GUIDE FOR NEW INTEGRATION

### Checklist for Creating New Integration

**1. Repository Setup**:

- [ ] Create GitHub repository
- [ ] Add LICENSE (MIT)
- [ ] Add README.md (copy structure)
- [ ] Add .gitignore (copy exact)
- [ ] Add .gitattributes (copy exact)

**2. Documentation**:

- [ ] CHANGELOG.md (start with [Unreleased])
- [ ] CLAUDE.md (adapt for your integration)
- [ ] Issue templates (copy all)
- [ ] Release notes template

**3. Code Quality**:

- [ ] .ruff.toml (copy exact)
- [ ] .markdownlint.json (copy exact)
- [ ] requirements.txt (update dependencies)

**4. GitHub Actions**:

- [ ] workflows/release.yml (update paths)
- [ ] workflows/validate.yml (copy exact)
- [ ] workflows/lint.yml (copy exact)
- [ ] workflows/dbautomerge.yml (copy exact)
- [ ] dependabot.yml (copy exact)

**5. HACS Integration**:

- [ ] hacs.json (update name, domain)
- [ ] manifest.json (update all fields)

**6. Integration Code**:

- [ ] custom_components/{domain}/__init__.py
- [ ] custom_components/{domain}/const.py
- [ ] custom_components/{domain}/config_flow.py
- [ ] custom_components/{domain}/coordinator.py
- [ ] custom_components/{domain}/api.py
- [ ] custom_components/{domain}/helpers.py
- [ ] custom_components/{domain}/sensor.py (or other platforms)
- [ ] custom_components/{domain}/manifest.json

**7. Translations**:

- [ ] translations/en.json (required)
- [ ] translations/{lang}.json (optional)

**8. Development**:

- [ ] .devcontainer.json (optional)
- [ ] .vscode/settings.json (optional)
- [ ] scripts/setup
- [ ] scripts/develop
- [ ] scripts/lint
- [ ] config/configuration.yaml

**9. Testing**:

- [ ] Test hassfest validation
- [ ] Test HACS validation
- [ ] Test config flow
- [ ] Test error handling
- [ ] Test with real device

**10. Release**:

- [ ] Update version (manifest.json + const.py)
- [ ] Update CHANGELOG.md
- [ ] Create GitHub release
- [ ] Verify ZIP creation
- [ ] Test HACS installation

______________________________________________________________________

## APPENDIX A: Key Files Reference

### A.1 Minimal Working Integration

**Absolute Minimum Files**:

```text
custom_components/{domain}/
├── __init__.py          # Setup and unload
├── manifest.json        # Integration metadata
└── const.py            # Constants
```

**Production-Ready Minimum**:

```text
custom_components/{domain}/
├── translations/
│   └── en.json         # English translations
├── __init__.py         # Setup and unload
├── api.py             # API client
├── config_flow.py     # UI configuration
├── const.py           # Constants
├── coordinator.py     # Data updates
├── helpers.py         # Utilities
├── manifest.json      # Metadata
└── sensor.py          # Sensor platform
```

### A.2 Repository Root Essentials

```text
repository/
├── .github/
│   ├── workflows/
│   │   ├── release.yml
│   │   └── validate.yml
│   └── dependabot.yml
├── custom_components/{domain}/
│   └── [integration files]
├── .gitignore
├── .ruff.toml
├── CHANGELOG.md
├── LICENSE
├── README.md
└── hacs.json
```

______________________________________________________________________

## APPENDIX B: Common Patterns Quick Reference

### B.1 Config Entry Setup

```python
async def async_setup_entry(hass, entry):
    coordinator = MyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = RuntimeData(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True
```

### B.2 Coordinator Pattern

```python
class MyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_method=self.async_update_data,
                         update_interval=timedelta(seconds=60))
        self.api = MyAPI(...)

    async def async_update_data(self):
        try:
            return await self.api.async_get_data()
        except Exception as ex:
            raise UpdateFailed from ex
```

### B.3 Sensor Entity

```python
class MySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_def):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{serial}_{key}"
        self._attr_device_info = {...}

    @property
    def native_value(self):
        return self.coordinator.api.data[self._key]
```

### B.4 Config Flow

```python
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            # Validate and test connection
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=name, data=user_input)
        return self.async_show_form(step_id="user",
                                     data_schema=SCHEMA,
                                     errors=errors)
```

______________________________________________________________________

## SUMMARY

The **ha-sinapsi-alfa** repository represents a **Gold-tier quality** Home Assistant custom
integration with strong Platinum-tier elements. It demonstrates:

1. **Professional Project Structure**: Complete CI/CD, documentation, and quality tooling
1. **Modern HA Patterns**: runtime_data, coordinator pattern, config flow, proper error handling
1. **Code Quality**: Comprehensive linting, type hints, structured logging, performance optimization
1. **Developer Experience**: DevContainer, helper scripts, clear documentation, AI guidelines
1. **User Experience**: UI configuration, translations, error recovery, clear entity organization
1. **Maintenance**: Dependabot, auto-merge, release automation, HACS integration

This template is suitable for creating production-quality integrations that meet Home Assistant's highest standards.

______________________________________________________________________

**Sources for Quality Scale Information**:

- [Quality scale - Home Assistant](https://www.home-assistant.io/docs/quality_scale/)
- [Integration quality scale | Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Integration Quality Scale: Chapter 3 · Discussion #1155](https://github.com/home-assistant/architecture/discussions/1155)
- [ADR-0022: Integration Quality Scale](https://github.com/home-assistant/architecture/blob/master/adr/0022-integration-quality-scale.md)
