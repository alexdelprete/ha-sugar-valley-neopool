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
- **Options flow**: Adjust offline timeout, recovery script, and repair
  notification settings at runtime
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
- All changes apply immediately without Home Assistant restart

## Requirements

- Home Assistant 2024.1.0 or newer
- Tasmota firmware with NeoPool support
  ([Documentation](https://tasmota.github.io/docs/NeoPool/))
- MQTT broker configured in Home Assistant

## Installation through HACS

This integration is available as a custom repository in [HACS].

1. Open HACS in Home Assistant
1. Click on "Integrations"
1. Click the three dots menu → "Custom repositories"
1. Add `https://github.com/alexdelprete/ha-neopool-mqtt` with category
   "Integration"
1. Search for "Sugar Valley NeoPool" and install
1. Restart Home Assistant

## Manual Installation

1. Download the latest release from
   [GitHub](https://github.com/alexdelprete/ha-neopool-mqtt/releases)
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
   - **Failures threshold**: Number of failures before creating repair issue
     (1-10)
   - **Offline timeout**: Seconds to wait for MQTT data before considering
     device offline (60-3600)
1. Click **Submit** - changes apply immediately

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

> **Important**: You must remove the YAML package **before** adding this
> integration to avoid duplicate entities.

1. **Remove/comment out** the YAML package from your `configuration.yaml`
1. **Restart Home Assistant** - entities will become "orphaned" but remain
   in the registry with all historical data intact
1. **Install** this custom integration through HACS or manually (see above)
1. **Add the integration** in Home Assistant:
   - Go to **Settings** → **Devices & Services** → **Add Integration**
   - Search for "Sugar Valley NeoPool"
   - Check the box **"Migrating from YAML package"**
1. **Auto-detection**: The integration will attempt to:
   - Auto-detect your MQTT topic (falls back to asking you if not found)
   - Auto-detect orphaned entities with prefix `neopool_mqtt_`
   - Configure Tasmota with `SetOption157 1` to expose NodeID
1. **Review and confirm**: Before migration, you'll see:
   - Summary of validated settings (topic, NodeID)
   - List of entities to be migrated
   - Confirmation checkbox (required to proceed)
1. **Verify migration**:
   - Check the persistent notification for migration results
   - All your entities should appear in the new integration
   - Historical data should be intact (graphs show continuous data)
   - Test that controls (switches, selects, numbers) work correctly

### Why NodeID?

The integration uses the hardware NodeID from your NeoPool controller to
create stable unique identifiers:

- **Pattern**: `neopool_mqtt_{nodeid}_{entity_key}`
- **Example**: `neopool_mqtt_ABC123_water_temperature`
- **Benefits**:
  - Stable IDs that survive MQTT topic changes
  - Support for multiple NeoPool controllers without conflicts
  - Hardware-based identification instead of software configuration

### Troubleshooting Migration

**Problem**: "Cannot read from this MQTT topic"

- Verify your Tasmota device is online and publishing to the topic you entered
- Check the topic name matches exactly (case-sensitive)
- Verify MQTT broker is working: look for `tele/{topic}/SENSOR` messages

**Problem**: "No orphaned entities found"

- Make sure you removed the YAML package from `configuration.yaml`
- Make sure you restarted Home Assistant after removing the YAML package
- If you used a custom `unique_id` prefix, enter it when prompted

**Problem**: "Failed to configure NodeID"

- Manually set `SetOption157 1` in Tasmota console, then retry setup
- Some Tasmota versions may require this to be set manually

**Problem**: Entities appear duplicated

- This happens if you didn't remove the YAML package before adding the
  integration
- Remove the YAML package from `configuration.yaml` and restart Home Assistant
- The duplicates should be resolved after restart

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

### Example Recovery Script

Create a script that restarts a smart plug and sends a notification:

```yaml
script:
  neopool_recovery:
    alias: "NeoPool Recovery Script"
    sequence:
      - service: notify.mobile_app
        data:
          title: "NeoPool Recovery"
          message: "NeoPool device failed multiple times. Restarting power..."
      - service: switch.turn_off
        target:
          entity_id: switch.tasmota_smart_plug
      - delay:
          seconds: 10
      - service: switch.turn_on
        target:
          entity_id: switch.tasmota_smart_plug
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
# Enable NeoPool telemetry
NPTelePeriod 60

# Enable all data in telemetry
NPResult 2

# Enable NodeID exposure (required for this integration)
SetOption157 1
```

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
1. **Debug logs** with timestamps showing the error
1. **Steps to reproduce** the issue

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
[coverage]: https://codecov.io/github/alexdelprete/ha-neopool-mqtt
[coverage-shield]: https://img.shields.io/codecov/c/github/alexdelprete/ha-neopool-mqtt?style=for-the-badge
[downloads]: https://github.com/alexdelprete/ha-neopool-mqtt/releases
[downloads-shield]: https://img.shields.io/github/downloads/alexdelprete/ha-neopool-mqtt/total?style=for-the-badge
[HACS]: https://hacs.xyz/
[issues]: https://github.com/alexdelprete/ha-neopool-mqtt/issues
[releases]: https://github.com/alexdelprete/ha-neopool-mqtt/releases
[releases-shield]: https://img.shields.io/github/v/release/alexdelprete/ha-neopool-mqtt?style=for-the-badge&color=darkgreen
[tests]: https://github.com/alexdelprete/ha-neopool-mqtt/actions/workflows/test.yml
[tests-shield]: https://img.shields.io/github/actions/workflow/status/alexdelprete/ha-neopool-mqtt/test.yml?style=for-the-badge&label=Tests
