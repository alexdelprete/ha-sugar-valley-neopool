# Sugar Valley NeoPool - Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

[![Tests][tests-shield]][tests]
[![Code Coverage][coverage-shield]][coverage]
[![Downloads][downloads-shield]][downloads]

_This project is not endorsed by, directly affiliated with, maintained,
authorized, or sponsored by Sugar Valley_

## Introduction

Home Assistant custom integration for **Sugar Valley NeoPool** controllers
connected via **Tasmota MQTT**.

NeoPool controllers are used in many pool systems for water treatment,
filtration control, and monitoring. This integration provides comprehensive
monitoring and control of your pool system through Home Assistant.

## Features

This integration provides comprehensive monitoring and control of your
NeoPool system:

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
- Relay states (pH, Filtration, Light, Acid)
- Water flow and tank level indicators

### Controls

- **Switches** - Filtration, Light, AUX1-AUX4 relays
- **Selects** - Filtration mode/speed, Boost mode
- **Numbers** - pH Min/Max, Redox setpoint, Hydrolysis setpoint
- **Buttons** - Clear error state

### Additional Features

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

## Installation through HACS

This integration is available as a custom repository in [HACS].

1. Open HACS in Home Assistant
1. Click on "Integrations"
1. Click the three dots menu → "Custom repositories"
1. Add `https://github.com/alexdelprete/ha-sugar-valley-neopool` with category
   "Integration"
1. Search for "Sugar Valley NeoPool" and install
1. Restart Home Assistant

## Manual Installation

1. Download the latest release from
   [GitHub](https://github.com/alexdelprete/ha-sugar-valley-neopool/releases)
1. Extract and copy `custom_components/sugar_valley_neopool` to your
   `config/custom_components/` directory
1. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
1. Click **Add Integration**
1. Search for "Sugar Valley NeoPool"
1. Enter:
   - **Device Name**: A friendly name for your pool controller
   - **Tasmota Device Topic**: The MQTT topic used by your Tasmota device
     (e.g., `SmartPool`)

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
   - Check the box **"Migrate from YAML package"**
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
1. **Review and confirm**: Before migration, you'll see:
   - Validated MQTT topic and NodeID
   - List of entities to be migrated
   - Confirmation checkbox (required to proceed)
1. **Migration result**: After confirming, you'll see:
   - Number of entities found and migrated
   - List of successfully migrated entities
   - Any errors that occurred

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

**Debug logging:**

To see the migration process in action, enable debug logging:

```yaml
logger:
  logs:
    custom_components.sugar_valley_neopool: debug
```

You'll see detailed logs like:

```text
Starting masked unique_id sanity check for entry abc123...
Found 45 entities with masked unique_ids
SetOption157 is disabled, enabling it to get real NodeID
Got real NodeID: 4C7525BFB344
Migrated entity sensor.neopool_ph_data: neopool_mqtt_XXXX...3435_ph_data -> neopool_mqtt_4C7525BFB344_ph_data
Migration complete: 45/45 entities migrated
```

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

You can configure a Home Assistant script to run automatically when the
device has been offline for the configured threshold. This is useful for
automated recovery actions.

### Configuration

1. Go to **Settings > Devices & Services > Sugar Valley NeoPool**
1. Click **Configure** to open the options dialog
1. Select a script from the **Recovery script** dropdown
1. The script will run when the failure threshold is reached

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

### Recommended Tasmota Configuration

```console
# REQUIRED: Enable NodeID exposure for stable entity unique IDs
SetOption157 1

# Enable NeoPool telemetry (interval in seconds)
NPTelePeriod 60

# Enable all data in telemetry
NPResult 2
```

> ⚠️ **SetOption157 is required!** Without it, the integration cannot create
> stable unique IDs for entities. See [Tasmota SetOption157](#tasmota-setoption157-required)
> for details.

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

## Contributing

Contributions are welcome! Please:

1. Fork the repository
1. Create a feature branch
1. Submit a pull request

## Coffee

_If you like this integration, I'll gladly accept some quality coffee,
but please don't feel obliged._ :)

[![BuyMeCoffee][buymecoffee-button]][buymecoffee]

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE)
file for details.

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
[HACS]: https://hacs.xyz/
[issues]: https://github.com/alexdelprete/ha-sugar-valley-neopool/issues
[releases]: https://github.com/alexdelprete/ha-sugar-valley-neopool/releases
[releases-shield]: https://img.shields.io/github/v/release/alexdelprete/ha-sugar-valley-neopool?style=for-the-badge&color=darkgreen
[tests]: https://github.com/alexdelprete/ha-sugar-valley-neopool/actions/workflows/test.yml
[tests-shield]: https://img.shields.io/github/actions/workflow/status/alexdelprete/ha-sugar-valley-neopool/test.yml?style=for-the-badge&label=Tests
