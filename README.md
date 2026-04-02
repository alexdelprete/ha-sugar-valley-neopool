# Sugar Valley NeoPool - Home Assistant Integration

<!-- BEGIN SHARED:repo-sync:badges -->
<!-- Synced by repo-sync on 2026-02-20 -->

[![GitHub Release][releases-shield]][releases]
[![Buy Me A Coffee][buymecoffee-shield]][buymecoffee]
[![Tests][tests-shield]][tests]
[![Coverage][coverage-shield]][coverage]
[![GitHub Downloads][downloads-shield]][downloads]

<!-- END SHARED:repo-sync:badges -->

## Introduction

Home Assistant custom integration for **Sugar Valley NeoPool** controllers
connected via **Tasmota MQTT**. Provides comprehensive monitoring and control
of your pool system through Home Assistant.

## Features

### Sensors

- **Water Temperature** - Current pool water temperature
- **pH** - pH level, state, and pump status
- **Redox (ORP)** - Oxidation-reduction potential
- **Hydrolysis** - Chlorine production level, state, and runtime statistics
- **Filtration** - Mode and speed
- **Powerunit** - Voltage diagnostics (5V, 12V, 24-30V, 4-20mA)
- **Connection** - Modbus communication statistics

### Binary Sensors

- Module presence (pH, Redox, Hydrolysis, Chlorine, Conductivity, Ionization)
- Named relay states (Acid, Base, Redox, Chlorine, Conductivity,
  Heating, UV, Valve)
- Water flow and tank level indicators

### Controls

- **Switches** - Filtration, Light, AUX1-AUX4 relays
- **Selects** - Filtration mode/speed, Boost mode
- **Numbers** - pH Min/Max, Redox setpoint, Hydrolysis setpoint
- **Buttons** - Clear error state

### Additional Features

- **Dynamic device info**: Device registry shows actual device metadata from
  MQTT telemetry:
  - **Manufacturer**: Actual brand from `NeoPool.Type` (e.g., "Bayrol",
    "Hidrolife", "Aquascenic") instead of generic "Sugar Valley"
  - **Firmware version**: Actual firmware from `NeoPool.Powerunit.Version`
    (e.g., "V3.45 (Powerunit)")
- **Translated sensor names**: Sensor names displayed in your Home Assistant
  language (supports German, English, Spanish, Estonian, Finnish, French,
  Italian, Norwegian, Portuguese, and Swedish)
- **Options flow**: Adjust offline timeout, recovery script, repair
  notification settings, and Tasmota SetOption157 at runtime
- **Reconfigure flow**: Change device name and MQTT topic
- **Repair notifications**: Device offline issues are surfaced in Home
  Assistant's repair system with configurable threshold
- **Recovery notifications**: Detailed timing info (downtime, script execution)
  when device recovers
- **Device triggers**: Automate based on device connection events (offline,
  online, recovered)
- **Recovery script**: Optionally execute a script when failure threshold
  is reached
- **Diagnostics**: Downloadable diagnostics file for troubleshooting
- **Automatic NodeID migration**: Detects and fixes entities created with
  masked NodeIDs on startup
- All changes apply immediately without Home Assistant restart

## Requirements

- Home Assistant 2024.1.0 or newer
- Tasmota firmware with NeoPool support
  ([Documentation](https://tasmota.github.io/docs/NeoPool/))
- MQTT broker configured in Home Assistant
- **Tasmota SetOption157 enabled** (see below)

### Tasmota SetOption157 (Required)

> ⚠️ **IMPORTANT**: Tasmota `SetOption157` **MUST** be set to `1` to expose
> the NeoPool hardware NodeID. This is a **prerequisite** for the integration
> to work correctly.

The integration uses the hardware NodeID from your NeoPool controller to
create stable, unique identifiers for all entities. Without `SetOption157 1`,
the NodeID is masked (shown as `XXXX XXXX XXXX XXXX`) and entities will have
incorrect unique IDs.

**To enable SetOption157:**

```console
# In Tasmota console
SetOption157 1
```

**What happens if SetOption157 is disabled:**

- The integration will **automatically enable it** during initial setup
- If entities were created with masked NodeIDs, the integration will
  **automatically detect and migrate them** on startup (see
  [Automatic NodeID Migration](#automatic-nodeid-migration))
- The Options flow includes a SetOption157 checkbox to check/change its status

While the integration handles this automatically, it's recommended to enable
`SetOption157 1` in Tasmota **before** setting up the integration to avoid
any migration steps.

<!-- BEGIN SHARED:repo-sync:installation -->
<!-- Synced by repo-sync on 2026-02-20 -->

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
1. Click on "Integrations"
1. Click the three dots menu in the top right corner
1. Select "Custom repositories"
1. Add `https://github.com/alexdelprete/ha-sugar-valley-neopool` as an Integration
1. Click "Download" and install the integration
1. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/alexdelprete/ha-sugar-valley-neopool/releases)
1. Extract the `custom_components/sugar_valley_neopool` folder
1. Copy it to your Home Assistant `config/custom_components/` directory
1. Restart Home Assistant

<!-- END SHARED:repo-sync:installation -->

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
1. Click **Add Integration**
1. Search for "Sugar Valley NeoPool"
1. **Confirm prerequisites**: If you previously used the YAML package, you
   must have already removed it and restarted Home Assistant. Confirm that
   no active YAML package is running.
1. **Choose setup path**:
   - **Fresh installation**: Leave the migration checkbox unchecked. You'll
     be asked to enter your device name and MQTT topic.
   - **Migrate from YAML**: Check the migration checkbox to preserve your
     existing entities and historical data. See
     [Migration Steps](#migration-steps) below.

The integration also supports **automatic MQTT discovery** - if your Tasmota
device is publishing NeoPool data, it may be discovered automatically.

### Runtime Options

After installation, you can adjust runtime settings without restart:

1. Go to **Settings** > **Devices & Services** > **Sugar Valley NeoPool**
1. Click **Configure** to open the options dialog
1. Adjust the available options:
   - **Recovery script**: Script to execute when failure threshold is reached
   - **Enable repair notifications**: Toggle repair issue creation on/off
   - **Failures threshold**: Number of consecutive LWT offline messages before
     triggering notifications (1-10)
   - **Offline timeout**: How long the device must be offline before triggering
     notifications (60-3600 seconds)
   - **SetOption157 (Show NodeID)**: Enable/disable Tasmota's SetOption157 to
     expose the hardware NodeID. Shows current status and warns if disabled.
1. Click **Submit** - changes apply immediately

> 💡 **Tip**: The SetOption157 checkbox shows the current status queried from
> your Tasmota device. If it shows as disabled, check the box to enable it.
> The integration will verify the change was successful.

### Reconfiguring Connection Settings

To change the device name or MQTT topic:

1. Go to **Settings** > **Devices & Services** > **Sugar Valley NeoPool**
1. Click the **three-dot menu** (⋮) on the integration card
1. Select **Reconfigure**
1. Update the settings and click **Submit**

Note: Entity IDs are based on the device NodeID, so changing the device name
or topic will not affect your historical data or automations.

## Migration from YAML Package

If you're currently using the YAML package
([`ha_neopool_mqtt_package.yaml`](docs/ha_neopool_mqtt_package.yaml)):

> ⚠️ **CRITICAL**: You **MUST** remove the YAML package and restart Home
> Assistant **BEFORE** adding this integration. If you skip this step:
>
> - You will get **duplicate entities** (both YAML and integration entities)
> - Both sets will be active and receiving updates simultaneously
> - You'll need to manually clean up the mess afterward
>
> The YAML package creates entities dynamically - they won't "transfer" to the
> integration automatically. The migration deletes the old MQTT entities and
> recreates them with the same entity IDs to preserve history.

### Migration Steps

1. **Remove/comment out** the YAML package from your `configuration.yaml`
1. **Restart Home Assistant** - this is essential! After restart, the entities
   will remain in the registry but become "unavailable" (no longer receiving
   updates from the YAML package)
1. **Install** this custom integration through HACS or manually (see above)
1. **Add the integration** in Home Assistant:
   - Go to **Settings** → **Devices & Services** → **Add Integration**
   - Search for "Sugar Valley NeoPool"
   - Confirm that no active YAML package is running
   - Check **"Yes, migrate my entities from the old YAML package"**
1. **Auto-detection**: The integration will automatically:
   - Scan for NeoPool messages and detect your MQTT topic
   - Find migratable entities using the default `neopool_mqtt_` prefix
   - If not found, use smart detection with NeoPool-specific signatures
   - Configure Tasmota with `SetOption157 1` to expose NodeID (if needed)
1. **Active entity check**: If the integration detects entities are still
   receiving updates (YAML package still running), it will warn you and
   ask you to remove the YAML package first
1. **Custom prefix support**: If your YAML used a custom `unique_id` prefix:
   - Smart detection will find entities using NeoPool-specific signatures
     (hydrolysis_runtime, powerunit_nodeid, etc.)
   - You'll be asked to confirm the detected prefix
   - Or you can manually enter your custom prefix
   - If no entities are found at all, you can skip migration and proceed
     with a fresh device setup instead
1. **Review and confirm**: Before migration, you'll see:
   - Validated MQTT topic and NodeID
   - List of entities to be migrated
   - Confirmation checkbox (required to proceed)
1. **Migration result**: After confirming, you'll see:
   - Number of entities found and migrated
   - List of successfully migrated entities
   - Any errors that occurred

### How Auto-Detection Works

The integration uses two auto-detection mechanisms during setup:

**MQTT Topic Detection**: The integration subscribes to the wildcard topic
`tele/+/SENSOR` and waits up to 10 seconds for a message containing
`"NeoPool"` in the JSON payload. If found, the device topic is extracted
automatically. Note that the `+` wildcard only matches single-level topics
(e.g., `SmartPool`). If you use a multi-level custom Tasmota topic (e.g.,
`tasmota/GA_po_IO_Oxilife`), auto-detection won't find it and you'll be
asked to enter the topic manually.

**Entity Prefix Detection**: When migrating, the integration first searches
for entities with the default `neopool_mqtt_` prefix. If none are found, it
falls back to smart detection: it scans all MQTT platform entities and checks
if their `unique_id` values end with NeoPool-specific signatures such as
`water_temperature`, `ph_data`, `hydrolysis_runtime_total`, and others. Each
signature carries a confidence weight. If the total confidence score is high
enough, the detected prefix is presented for your confirmation. Otherwise,
you can enter a custom prefix manually or skip migration entirely.

### How History Preservation Works

The migration process preserves your historical data by:

1. **Finding** your old MQTT entities by their `unique_id` prefix
1. **Extracting** the actual `entity_id` from each entity (handles custom names)
1. **Deleting** the old MQTT entities from the entity registry
1. **Creating** new entities with the **same `entity_id`** as the deleted ones

Since Home Assistant's recorder indexes history by `entity_id`, your graphs,
statistics, and long-term data are preserved when the new entity uses the
same `entity_id` as the old one.

The integration also extracts your device name from the migrated entity IDs
to preserve any customizations (e.g., if your entities were named
`sensor.my_pool_ph_data`, the device will be named "My Pool").

### Why NodeID?

The integration uses the hardware NodeID from your NeoPool controller to
create stable unique identifiers:

- **Pattern**: `neopool_mqtt_{nodeid}_{entity_key}`
- **Example**: `neopool_mqtt_4C7525BFB344_water_temperature`
- **Benefits**:
  - Stable IDs that survive MQTT topic changes
  - Support for multiple NeoPool controllers without conflicts
  - Hardware-based identification instead of software configuration

### Automatic NodeID Migration

If entities were created with masked NodeIDs (when `SetOption157` was
disabled), the integration automatically detects and fixes them on startup.

**What is a masked NodeID?**

When Tasmota's `SetOption157` is set to `0` (default), the NodeID is masked
for privacy. Instead of the real NodeID like `4C7525BFB344`, you see something
like `XXXX XXXX XXXX XXXX 3435`. This results in entity unique IDs like:

- `neopool_mqtt_XXXX XXXX XXXX XXXX 3435_water_temperature` (masked - bad)

Instead of:

- `neopool_mqtt_4C7525BFB344_water_temperature` (real - good)

**Automatic migration process:**

On every integration startup, a sanity check runs that:

1. **Detects** entities with masked unique IDs (containing "XXXX")
2. **Checks** if `SetOption157` is enabled on Tasmota
3. **Enables** `SetOption157` if it was disabled
4. **Retrieves** the real NodeID from telemetry
5. **Normalizes** the NodeID (removes spaces, uppercase)
6. **Migrates** all entity unique IDs to use the real NodeID
7. **Updates** the config entry and device registry

**What gets preserved:**

- All historical data (graphs, statistics, long-term statistics)
- Entity IDs (e.g., `sensor.neopool_water_temperature`)
- Entity customizations (friendly names, icons, areas)
- Automation and script references

To monitor the migration process, [enable debug logging](#enable-debug-logging).

### Startup Validation and Runtime Monitoring

The integration performs automatic validation and monitoring to ensure
reliable operation.

#### Startup Validation (Every Restart)

On every Home Assistant startup, the integration runs a validation/reconciliation
process to ensure everything is properly configured:

| Check | Description | Action if Failed |
|-------|-------------|------------------|
| **Masked NodeID Detection** | Scans entities for masked IDs ("XXXX") | Enables SO157, migrates entities |
| **Config Entry NodeID** | Verifies stored NodeID is unmasked | Updates config entry |
| **Entity ID Mapping** | Checks YAML-migrated entity_ids | Renames to preserve original IDs |
| **Orphaned Entity Cleanup** | Finds replaced YAML entities | Deletes orphaned binary sensors |
| **Device Registry** | Verifies device uses real NodeID | Updates device identifier |

**Why run on every startup?**

- Users might restore backups with old entity configurations
- Tasmota configuration might change (SO157 disabled externally)
- Safer to always verify than assume persisted state is correct
- Operations are idempotent (running multiple times produces same result)

After the first successful validation, subsequent startups quickly verify
everything is aligned and log debug messages like "already correct" or
"migration not needed".

#### Runtime Monitoring (While Running)

While Home Assistant is running, the integration actively monitors:

| Monitor | Description | Action |
|---------|-------------|--------|
| **SetOption157 Enforcement** | Monitors SENSOR for masked NodeID | Re-enables SO157 automatically |
| **Device Availability** | Subscribes to LWT topic | Marks entities unavailable |

**SetOption157 Runtime Enforcement:**

The integration subscribes to `tele/{topic}/SENSOR` and checks every message
for a masked NodeID. If someone disables SO157 via Tasmota console, the
integration detects the masked NodeID pattern and automatically sends
`SetOption157 1` to re-enable it.

```text
# Example log when enforcement triggers:
WARNING Detected masked NodeID 'XXXX XXXX XXXX XXXX 3435' in SENSOR data,
        enforcing SetOption157
INFO Successfully enforced SetOption157 for SmartPool
```

**What is NOT monitored at runtime:**

- Entity unique_id alignment (requires restart)
- Entity_id mapping correctness (requires restart)
- Orphaned entities (requires restart)

These checks only run at startup because entity registry changes require
a Home Assistant restart to take effect anyway.

### Troubleshooting Migration

**Problem**: "Cannot read from this MQTT topic"

- Verify your Tasmota device is online and publishing to the topic you entered
- Check the topic name matches exactly (case-sensitive)
- Verify MQTT broker is working: look for `tele/{topic}/SENSOR` messages

**Problem**: "No migratable entities found"

- Verify entities with the `neopool_mqtt_` prefix exist in your entity registry
- Entities already owned by this integration cannot be migrated again
- The integration uses smart detection with NeoPool-specific signatures
  (hydrolysis_runtime, powerunit_nodeid, etc.) to find entities
- If smart detection finds your entities, you'll be asked to confirm the
  detected prefix and confidence level
- If automatic detection fails, you can manually enter your custom prefix

**Problem**: "YAML package still active" warning

- The integration detected entities are still receiving updates
- This means you haven't removed/commented out the YAML package yet
- **To fix**:
  1. Remove/comment out the YAML package from `configuration.yaml`
  2. Restart Home Assistant
  3. Click "Retry" in the config flow to check again

**Problem**: "Failed to configure NodeID"

- Manually set `SetOption157 1` in Tasmota console, then retry setup
- Some Tasmota versions may require this to be set manually

**Problem**: Entities appear duplicated

- This happens if you didn't remove the YAML package before adding the
  integration. The YAML package creates entities dynamically via MQTT, so:
  - The old YAML entities continue to receive updates (active)
  - The new integration creates its own entities with the migrated unique_ids
  - Both sets of entities appear and update simultaneously
- **To fix**:
  1. Remove/comment out the YAML package from `configuration.yaml`
  2. Restart Home Assistant
  3. The YAML-created entities will become unavailable
  4. You may need to manually delete the orphaned entities from
     **Settings** → **Devices & Services** → **Entities** tab
- **Prevention**: Always remove the YAML package and restart HA **before**
  running the migration wizard

**Problem**: Finding your custom unique_id prefix

If you need to find your custom prefix manually:

1. Go to **Settings** → **Devices & Services** → **Entities** tab
2. Search for any NeoPool entity (e.g., `sensor.neopool_water_temperature`)
3. Click the entity and then the gear icon to see its **Unique ID**
4. The prefix is everything before the entity key (e.g., if unique_id is
   `my_pool_water_temperature`, the prefix is `my_pool_`)

## Device Triggers

The integration provides device triggers that allow you to create automations
based on device connection events.

### Available Triggers

| Trigger | Description |
|---------|-------------|
| **Device offline** | Fires when the device goes offline (MQTT LWT) |
| **Device online** | Fires when the device comes back online |
| **Device recovered** | Fires when the device recovers after extended outage |

### How to Use Device Triggers

1. Go to **Settings > Automations & Scenes > Create Automation**
1. Click **Add Trigger** and select **Device**
1. Select your NeoPool device
1. Choose from the available triggers

### Device Trigger Automation Example

Get notified when your NeoPool device goes offline and comes back online:

```yaml
automation:
  - alias: "NeoPool Device Offline Alert"
    trigger:
      - platform: device
        domain: sugar_valley_neopool
        device_id: YOUR_DEVICE_ID
        type: device_offline
    action:
      - service: notify.mobile_app
        data:
          title: "NeoPool Offline"
          message: "The NeoPool device is unreachable. Check Tasmota device."

  - alias: "NeoPool Device Recovered"
    trigger:
      - platform: device
        domain: sugar_valley_neopool
        device_id: YOUR_DEVICE_ID
        type: device_recovered
    action:
      - service: notify.mobile_app
        data:
          title: "NeoPool Online"
          message: "The NeoPool device is back online and responding."
```

## Recovery Script

You can configure a recovery script in [Runtime Options](#runtime-options).
The script runs automatically when the device has been offline for the
configured failure threshold.

### Recovery Script Variables

When the recovery script runs, it receives context variables that you can use
in your script actions. Access these using the `trigger` context:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `device_name` | The configured device name | `"Pool Controller"` |
| `mqtt_topic` | The MQTT topic for the device | `"SmartPool"` |
| `nodeid` | The device's hardware NodeID | `"ABC123"` |
| `failures_count` | Number of consecutive failures | `3` |

### Example Recovery Script

Create a script that restarts a smart plug and sends a notification with
device details:

```yaml
script:
  neopool_recovery:
    alias: "NeoPool Recovery Script"
    sequence:
      - service: notify.mobile_app
        data:
          title: "NeoPool Recovery"
          message: >
            {{ device_name }} failed {{ failures_count }} times.
            MQTT topic: {{ mqtt_topic }}. Restarting power...
      - service: switch.turn_off
        target:
          entity_id: switch.tasmota_smart_plug
      - delay:
          seconds: 10
      - service: switch.turn_on
        target:
          entity_id: switch.tasmota_smart_plug
      - service: notify.mobile_app
        data:
          title: "NeoPool Recovery Complete"
          message: "Power cycled for {{ device_name }} (NodeID: {{ nodeid }})"
```

## MQTT Topic Configuration

In your Tasmota device, the MQTT topic is configured under
**Configuration** → **Configure MQTT** → **Topic**.

The integration expects MQTT messages on these topics:

- `tele/{topic}/SENSOR` - Sensor data (JSON)
- `tele/{topic}/LWT` - Last Will and Testament (Online/Offline)
- `cmnd/{topic}/{command}` - Commands

## Tasmota NeoPool Setup

For detailed Tasmota NeoPool setup instructions, see the
[official documentation](https://tasmota.github.io/docs/NeoPool/).
SetOption157 setup is covered in [Requirements](#tasmota-setoption157-required).

## Known Limitations

- **Single device per integration**: Each config entry supports one NeoPool
  device. To monitor multiple devices, add the integration multiple times
- **Tasmota firmware required**: The integration communicates via MQTT
  with Tasmota; direct RS485/Modbus is not supported
- **Push-based updates**: Data is received via MQTT push; frequency depends
  on your `NPTelePeriod` setting

## Troubleshooting

### Enable Debug Logging

Add this to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.sugar_valley_neopool: debug
```

After adding this configuration, restart Home Assistant for the changes to
take effect.

### Getting FULL Debug Logs

When reporting issues, it's essential to provide **complete** debug logs.
Follow these steps to capture a full debug log:

#### Step 1: Enable Debug Logging (if not already done)

Add the logger configuration shown above to your `configuration.yaml` and
restart Home Assistant.

#### Step 2: Clear Existing Logs

Before reproducing the issue, clear your log file to make it easier to find
relevant entries:

1. Go to **Settings** > **System** > **Logs**
1. Click **Clear** (top-right) to clear the current logs

#### Step 3: Reproduce the Issue

Perform the exact steps that cause the problem. For example:

- If entities go unavailable, wait for it to happen
- If a command fails, execute the command
- If setup fails, try adding/reconfiguring the integration

#### Step 4: Download the Full Log File

**Option A: From the Home Assistant UI**

1. Go to **Settings** > **System** > **Logs**
1. Click **Download full log** (top-right, download icon)
1. Save the `home-assistant.log` file

**Option B: From the File System**

The log file is located at:

- **Home Assistant OS/Supervised**: `/config/home-assistant.log`
- **Docker**: Inside your config volume, e.g., `/path/to/config/home-assistant.log`
- **Core**: In your config directory, typically `~/.homeassistant/home-assistant.log`

#### Step 5: Filter for Relevant Entries (Optional)

To extract only NeoPool-related entries, use these commands:

```bash
# Linux/macOS
grep "sugar_valley_neopool" home-assistant.log > neopool-debug.log

# Windows PowerShell
Select-String -Path home-assistant.log `
  -Pattern "sugar_valley_neopool" | Out-File neopool-debug.log
```

#### What the Debug Log Contains

With debug logging enabled, you'll see:

- **MQTT subscriptions**: Topics being subscribed to
- **MQTT messages**: Received sensor data and LWT status
- **Entity updates**: State changes and value transformations
- **Commands**: Outgoing MQTT commands
- **Migration**: Entity migration process details
- **Errors**: Detailed error messages with stack traces

**Example debug log entries:**

```text
DEBUG [custom_components.sugar_valley_neopool.sensor]
  Sensor water_temperature subscribed to tele/SmartPool/SENSOR

DEBUG [custom_components.sugar_valley_neopool.entity]
  Received MQTT message on tele/SmartPool/SENSOR

DEBUG [custom_components.sugar_valley_neopool.sensor]
  Sensor water_temperature updated: 28.5
```

### Temporary Debug Logging (Without Restart)

You can enable debug logging temporarily without restarting Home Assistant:

1. Go to **Developer Tools** > **Services**
1. Select service `logger.set_level`
1. Enter this YAML:

   ```yaml
   custom_components.sugar_valley_neopool: debug
   ```

1. Click **Call Service**

> **Note**: This method only enables debug logging until the next Home
> Assistant restart. For persistent debug logging, use the `configuration.yaml`
> method.

### Include MQTT Debug Logs (Advanced)

For MQTT-related issues, you may also need MQTT debug logs:

```yaml
logger:
  default: warning
  logs:
    custom_components.sugar_valley_neopool: debug
    homeassistant.components.mqtt: debug
```

> **Warning**: MQTT debug logging can be very verbose. Only enable it when
> specifically troubleshooting MQTT connectivity issues, and disable it
> afterward.

### View and Download Diagnostics

1. Go to **Settings** > **Devices & Services** > **Sugar Valley NeoPool**
1. Click the **three-dot menu** (⋮) on the integration card
1. Select **Download diagnostics**

The diagnostic file contains sanitized device information and configuration.
Sensitive data like NodeID and MQTT topics are automatically redacted.

### Common Issues

1. **Entities show as unavailable**

   - Check that your Tasmota device is online and publishing to MQTT
   - Verify the MQTT topic matches your configuration
   - Check the LWT topic shows "Online"

1. **Commands not working**

   - Ensure the Tasmota device has write access to NeoPool
   - Check MQTT broker permissions

### Reporting Issues

When [opening an issue][issues], please include:

1. **Diagnostic file**: Download from Settings > Devices & Services >
   Sugar Valley NeoPool > three-dot menu (⋮) > Download diagnostics
1. **Home Assistant version** (Settings > About)
1. **Integration version** (Settings > Devices & Services > Sugar Valley
   NeoPool)
1. **Full debug logs**: Follow the [Getting FULL Debug Logs](#getting-full-debug-logs)
   section above
1. **Steps to reproduce** the issue with exact actions taken

## Development

This project uses a comprehensive test suite:

```bash
# Install development dependencies
uv sync --all-extras --dev

# Run tests with coverage
uv run pytest tests/ --cov=custom_components/sugar_valley_neopool \
  --cov-report=term-missing -v

# Run linting
ruff format .
ruff check . --fix

# Run type checking
mypy custom_components/sugar_valley_neopool --ignore-missing-imports
```

**CI/CD Workflows:**

- **Tests**: Runs pytest with coverage on every push/PR to main
- **Validate**: Runs hassfest and HACS validation
- **Release**: Automatically creates ZIP on GitHub release publish with
  version validation

<!-- BEGIN SHARED:repo-sync:contributing -->
<!-- Synced by repo-sync on 2026-02-20 -->

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
1. Create a feature branch (`git checkout -b feature/my-feature`)
1. Make your changes
1. Run linting: `uvx pre-commit run --all-files`
1. Commit your changes (`git commit -m "feat: add my feature"`)
1. Push to your branch (`git push origin feature/my-feature`)
1. Open a Pull Request

Please ensure all CI checks pass before requesting a review.

<!-- END SHARED:repo-sync:contributing -->

## Coffee

_If you like this integration, I'll gladly accept some quality coffee,
but please don't feel obliged._ :)

[![BuyMeCoffee][buymecoffee-button]][buymecoffee]

<!-- BEGIN SHARED:repo-sync:license -->
<!-- Synced by repo-sync on 2026-02-20 -->

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

<!-- END SHARED:repo-sync:license -->

## Acknowledgments

- [Tasmota](https://tasmota.github.io/) for the excellent NeoPool support
- [Home Assistant](https://www.home-assistant.io/) community
- [ha-sinapsi-alfa](https://github.com/alexdelprete/ha-sinapsi-alfa) for the
  integration template

---

[buymecoffee]: https://www.buymeacoffee.com/alexdelprete
[buymecoffee-button]: https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=alexdelprete&button_colour=FFDD00&font_colour=000000&font_family=Lato&outline_colour=000000&coffee_colour=ffffff
[buymecoffee-shield]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-white?style=for-the-badge&logo=buymeacoffee&logoColor=white
[coverage]: https://codecov.io/github/alexdelprete/ha-sugar-valley-neopool
[coverage-shield]: https://img.shields.io/codecov/c/github/alexdelprete/ha-sugar-valley-neopool?style=for-the-badge
[downloads]: https://github.com/alexdelprete/ha-sugar-valley-neopool/releases
[downloads-shield]: https://img.shields.io/github/downloads/alexdelprete/ha-sugar-valley-neopool/total?style=for-the-badge
[issues]: https://github.com/alexdelprete/ha-sugar-valley-neopool/issues
[releases]: https://github.com/alexdelprete/ha-sugar-valley-neopool/releases
[releases-shield]: https://img.shields.io/github/v/release/alexdelprete/ha-sugar-valley-neopool?style=for-the-badge&color=darkgreen
[tests]: https://github.com/alexdelprete/ha-sugar-valley-neopool/actions/workflows/test.yml
[tests-shield]: https://img.shields.io/github/actions/workflow/status/alexdelprete/ha-sugar-valley-neopool/test.yml?style=for-the-badge&label=Tests
