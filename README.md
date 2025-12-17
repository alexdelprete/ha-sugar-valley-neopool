# Sugar Valley NeoPool - Home Assistant Integration

[![HACS Validation](https://github.com/alexdelprete/ha-neopool-mqtt/actions/workflows/validate.yml/badge.svg)](https://github.com/alexdelprete/ha-neopool-mqtt/actions/workflows/validate.yml)
[![GitHub Release](https://img.shields.io/github/v/release/alexdelprete/ha-neopool-mqtt)](https://github.com/alexdelprete/ha-neopool-mqtt/releases)
[![License](https://img.shields.io/github/license/alexdelprete/ha-neopool-mqtt)](LICENSE)

Home Assistant custom integration for **Sugar Valley NeoPool** controllers connected via **Tasmota MQTT**.

## Features

This integration provides comprehensive monitoring and control of your NeoPool system:

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

## Requirements

- Home Assistant 2024.1.0 or newer
- Tasmota firmware with NeoPool support ([Documentation](https://tasmota.github.io/docs/NeoPool/))
- MQTT broker configured in Home Assistant

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
1. Click on "Integrations"
1. Click the three dots menu → "Custom repositories"
1. Add `https://github.com/alexdelprete/ha-neopool-mqtt` with category "Integration"
1. Search for "Sugar Valley NeoPool" and install
1. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/alexdelprete/ha-neopool-mqtt/releases)
1. Extract and copy `custom_components/sugar_valley_neopool` to your `config/custom_components/` directory
1. Restart Home Assistant

### Migration from YAML Package

If you're currently using the YAML package ([`ha_neopool_mqtt_package.yaml`](docs/ha_neopool_mqtt_package.yaml)):

1. **Keep your YAML configuration** - Don't remove it yet
1. Install this custom integration through HACS or manually (see above)
1. Add the integration in Home Assistant:
   - Go to **Settings** → **Devices & Services** → **Add Integration**
   - Search for "Sugar Valley NeoPool"
   - When prompted, check the box **"Migrating from YAML package"**
   - Enter your YAML MQTT topic (default: `SmartPool`)
     - If you customized the topic in your YAML package, enter your custom topic
   - The integration will automatically:
     - Validate the MQTT topic by checking for NeoPool messages
     - Configure Tasmota with `SetOption157 1` to expose NodeID
     - Migrate all existing entities to NodeID-based unique IDs
     - Preserve all historical data (graphs, statistics, history)
     - Associate entities with the new config entry
1. **Verify migration**:
   - All your entities should appear in the new integration
   - Check that historical data is intact (graphs should show continuous data)
   - Test that controls (switches, selects, numbers) work correctly
1. After confirming everything works, remove the YAML package from your `configuration.yaml`

**No manual steps required** - the integration handles everything automatically, including Tasmota configuration!

#### Why NodeID?

The integration now uses the hardware NodeID from your NeoPool controller to create stable unique identifiers:

- **Pattern**: `neopool_mqtt_{nodeid}_{entity_key}`
- **Example**: `neopool_mqtt_ABC123_water_temperature`
- **Benefits**:
  - Stable IDs that survive MQTT topic changes
  - Support for multiple NeoPool controllers without conflicts
  - Hardware-based identification instead of software configuration

#### Troubleshooting Migration

**Problem**: "Cannot read from this MQTT topic"

- **Solution**: Verify your Tasmota device is online and publishing to the topic you entered
- Check the topic name matches exactly (case-sensitive)
- Verify MQTT broker is working: look for `tele/{topic}/SENSOR` messages

**Problem**: "Failed to configure NodeID"

- **Solution**: Manually set `SetOption157 1` in Tasmota console, then retry setup
- Some Tasmota versions may require this to be set manually

**Problem**: Entities appear duplicated after migration

- **Solution**: Remove the old YAML package configuration from `configuration.yaml` and restart Home Assistant
- The old YAML entities will be automatically migrated to the new integration

## Configuration

1. Go to **Settings** → **Devices & Services**
1. Click **Add Integration**
1. Search for "Sugar Valley NeoPool"
1. Enter:
   - **Device Name**: A friendly name for your pool controller
   - **Tasmota Device Topic**: The MQTT topic used by your Tasmota device (e.g., `SmartPool`)

The integration also supports **automatic MQTT discovery** - if your Tasmota device is publishing NeoPool data, it may be discovered automatically.

## MQTT Topic Configuration

In your Tasmota device, the MQTT topic is configured under **Configuration** → **Configure MQTT** → **Topic**.

The integration expects MQTT messages on these topics:

- `tele/{topic}/SENSOR` - Sensor data (JSON)
- `tele/{topic}/LWT` - Last Will and Testament (Online/Offline)
- `cmnd/{topic}/{command}` - Commands

## Tasmota NeoPool Setup

For detailed Tasmota NeoPool setup instructions, see the [official documentation](https://tasmota.github.io/docs/NeoPool/).

### Recommended Tasmota Configuration

```console
# Enable NeoPool telemetry
NPTelePeriod 60

# Enable all data in telemetry
NPResult 2
```

## Removal

To remove this integration from Home Assistant:

1. Go to **Settings** → **Devices & Services**
1. Find the "Sugar Valley NeoPool" integration
1. Click the three dots menu (⋮) next to it
1. Select **Delete**
1. Confirm the deletion

This will remove the integration, all associated devices, and entities from Home Assistant. Your Tasmota device and MQTT broker configuration will remain unchanged.

## Troubleshooting

### Enable Debug Logging

Add this to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.sugar_valley_neopool: debug
```

### Common Issues

1. **Entities show as unavailable**

   - Check that your Tasmota device is online and publishing to MQTT
   - Verify the MQTT topic matches your configuration
   - Check the LWT topic shows "Online"

1. **Commands not working**

   - Ensure the Tasmota device has write access to NeoPool
   - Check MQTT broker permissions

## Contributing

Contributions are welcome! Please:

1. Fork the repository
1. Create a feature branch
1. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Tasmota](https://tasmota.github.io/) for the excellent NeoPool support
- [Home Assistant](https://www.home-assistant.io/) community
- [ha-sinapsi-alfa](https://github.com/alexdelprete/ha-sinapsi-alfa) for the integration template
