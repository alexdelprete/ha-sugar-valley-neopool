# NeoPool MQTT Documentation Index

This directory contains comprehensive documentation for the Home Assistant NeoPool MQTT integration.

______________________________________________________________________

## Documentation Files

### 1. **TASMOTA_NEOPOOL_MQTT_REFERENCE.md** (1,670 lines)

**Complete technical reference for Tasmota NeoPool MQTT protocol**

**Contents:**

- What NeoPool is and how it works with Tasmota
- Complete MQTT topic structure (tele/, cmnd/, stat/)
- Full JSON telemetry payload structure with examples
- All sensor readings (temperature, pH, ORP, chlorine, filtration, etc.)
- All available commands with parameters and examples
- Configuration options and settings
- Low-level Modbus register access
- Data types and value ranges for every reading
- Special modes and features (filtration modes, boost, etc.)
- State enumerations and mappings

**Use this for:**

- Understanding the NeoPool MQTT protocol
- Reference for all available data points
- Command syntax and parameters
- Integration planning

______________________________________________________________________

### 2. **MQTT_TOPIC_QUICK_REFERENCE.md** (353 lines)

**Quick reference guide for MQTT topics and commands**

**Contents:**

- MQTT topic patterns (simplified)
- Command topic reference table
- JSON path examples for sensor extraction
- State mapping dictionaries (Python ready)
- Example MQTT publish commands (mosquitto_pub)
- Home Assistant YAML examples
- Common automation patterns
- Troubleshooting tips

**Use this for:**

- Quick lookup of MQTT topics
- Copy-paste command examples
- Testing MQTT communication
- Simple automations

______________________________________________________________________

### 3. **HA_INTEGRATION_IMPLEMENTATION.md** (1,091 lines)

**Detailed implementation guide for Home Assistant custom integration**

**Contents:**

- Integration architecture and file structure
- Complete entity definitions for all platforms:
  - Sensors (temperature, pH, redox, chlorine, etc.)
  - Binary sensors (flow, tank, cover, etc.)
  - Numbers (setpoints for pH, redox, chlorine)
  - Selects (filtration mode, speed, boost)
  - Switches (filtration, light, relays)
- Dynamic entity creation based on installed modules
- Constants and state mappings (const.py)
- Data processing functions (runtime parsing, validation)
- Device information structure
- Error handling strategies
- Availability templates
- Testing checklist
- Security considerations

**Use this for:**

- Creating a custom Home Assistant integration
- Entity configuration and setup
- Understanding entity types and relationships
- Implementation best practices

______________________________________________________________________

### 4. **HA_MQTT_INTEGRATION_GUIDE.md** (1,704 lines)

**Comprehensive guide for MQTT-based Home Assistant integration**

**Contents:**

- Step-by-step setup instructions
- Complete entity configurations for YAML
- All sensor, binary_sensor, number, select, and switch entities
- Automation examples
- Template sensors for advanced features
- Lovelace UI card configurations
- Notifications and alerts
- Error handling and troubleshooting
- Performance optimization tips

**Use this for:**

- Setting up NeoPool with Home Assistant via YAML
- Complete working configuration examples
- Dashboard/UI setup
- Automation ideas

______________________________________________________________________

### 5. **ha_neopool_mqtt_package.yaml** (YAML file)

**Ready-to-use Home Assistant package configuration**

**Contents:**

- Complete MQTT sensor, binary_sensor, number, select, and switch definitions
- All entities pre-configured
- State templates
- Icons and device classes
- Can be dropped into `packages/` directory

**Use this for:**

- Quick deployment of NeoPool MQTT integration
- Copy-paste configuration
- Testing setup before custom integration

______________________________________________________________________

## Quick Start Guide

### For Users (YAML Configuration)

1. Start with **MQTT_TOPIC_QUICK_REFERENCE.md** to understand the basics
1. Use **ha_neopool_mqtt_package.yaml** for immediate deployment
1. Refer to **HA_MQTT_INTEGRATION_GUIDE.md** for customization and automations

### For Developers (Custom Integration)

1. Read **TASMOTA_NEOPOOL_MQTT_REFERENCE.md** for complete protocol understanding
1. Follow **HA_INTEGRATION_IMPLEMENTATION.md** for integration development
1. Use **MQTT_TOPIC_QUICK_REFERENCE.md** for testing

### For Testing/Debugging

1. Use **MQTT_TOPIC_QUICK_REFERENCE.md** for command examples
1. Check **TASMOTA_NEOPOOL_MQTT_REFERENCE.md** for data structure details
1. Reference **HA_INTEGRATION_IMPLEMENTATION.md** for validation functions

______________________________________________________________________

## Key Information Summary

### MQTT Topics

```text
tele/%topic%/SENSOR         # Telemetry (sensor data)
cmnd/%topic%/<command>      # Commands
stat/%topic%/RESULT         # Command responses
```

Replace `%topic%` with your device topic (e.g., "poolcontroller")

### Available Modules (Check Module Object)

- pH module
- Redox (ORP) module
- Hydrolysis (chlorine production) module
- Chlorine sensor module
- Conductivity module
- Ionization module

**Only installed modules will appear in telemetry!**

### Main Sensor Readings

- **Temperature:** Water temperature (°C)
- **pH:** Current pH (0-14)
- **Redox:** Oxidation-reduction potential (mV)
- **Chlorine:** Free chlorine (ppm)
- **Hydrolysis:** Chlorine production (% or g/h)
- **Filtration:** Pump state, speed, mode
- **Light:** Pool light state
- **Relays:** Up to 7 relays + 4 auxiliary

### Main Control Commands

- **NPFiltration:** Control pump on/off and speed
- **NPFiltrationmode:** Set filtration mode (Manual/Auto/Smart/etc.)
- **NPLight:** Control pool light
- **NPpHMin / NPpHMax:** Set pH range
- **NPRedox:** Set redox setpoint
- **NPChlorine:** Set chlorine setpoint
- **NPHydrolysis:** Set chlorine production level
- **NPBoost:** Control boost mode

______________________________________________________________________

## Entity Count Estimates

Based on a fully equipped NeoPool system:

| Entity Type    | Approximate Count  |
| -------------- | ------------------ |
| Sensors        | 20-30              |
| Binary Sensors | 8-12               |
| Numbers        | 5-8                |
| Selects        | 3-4                |
| Switches       | 10-15              |
| **Total**      | **46-69 entities** |

**Note:** Actual count depends on installed modules and configuration.

______________________________________________________________________

## State Enumerations

### pH State (0-6)

- 0 = OK
- 1 = pH Too High
- 2 = pH Too Low
- 3 = Pump Timeout
- 4 = pH High Warning
- 5 = pH Low Warning
- 6 = Tank Empty

### Filtration Mode (0-4, 13)

- 0 = Manual
- 1 = Auto
- 2 = Heating
- 3 = Smart
- 4 = Intelligent
- 13 = Backwash

### Filtration Speed (1-3)

- 1 = Low
- 2 = Medium
- 3 = High

### Hydrolysis State (String)

- "OFF" = Hydrolysis off
- "FLOW" = Flow alarm (no water flow)
- "POL1" = Running (polarity 1)
- "POL2" = Running (polarity 2)

### Boost Mode (0-2)

- 0 = Off
- 1 = On (independent)
- 2 = Redox (controlled by redox)

______________________________________________________________________

## Value Ranges

| Measurement  | Range  | Unit     | Typical Pool Range |
| ------------ | ------ | -------- | ------------------ |
| Temperature  | 0-40   | °C       | 15-30°C            |
| pH           | 0-14   | pH       | 7.0-7.6            |
| Redox        | 0-1000 | mV       | 650-750 mV         |
| Chlorine     | 0-10   | ppm      | 0.5-3.0 ppm        |
| Hydrolysis   | 0-100  | % or g/h | Device dependent   |
| Conductivity | 0-100  | %        | N/A                |

______________________________________________________________________

## Configuration Recommendations

### Tasmota Device Settings

```text
NPTelePeriod 0           # Report only on changes
NPSetOption0 1           # Enable data validation
NPSetOption1 1           # Enable statistics (ESP32)
NPPHRes 2                # pH with 2 decimal places
NPCLRes 2                # Chlorine with 2 decimal places
SetOption147 1           # MQTT sensor discovery
SetOption157 1           # Show NodeID (auto-configured by integration)
```

### Home Assistant

```yaml
# Enable packages (configuration.yaml)
homeassistant:
  packages: !include_dir_named packages/

# Copy ha_neopool_mqtt_package.yaml to packages/
# Adjust topic name in file to match your device
```

______________________________________________________________________

## Troubleshooting

### No Data Appearing

1. Check MQTT broker connection
1. Verify topic name matches device
1. Check Tasmota console: `NPControl` to verify NeoPool module
1. Subscribe to `tele/+/SENSOR` to see all devices

### Entities Not Creating

1. Verify Module object shows installed hardware
1. Check Home Assistant logs for errors
1. Confirm MQTT integration is configured
1. Restart Home Assistant after YAML changes

### Commands Not Working

1. Test with mosquitto_pub first
1. Check topic formatting: `cmnd/topic/NPFiltration`
1. Verify payload format (usually just the value)
1. Check device logs in Tasmota console

### Connection Errors

1. Enable statistics: `NPSetOption1 1`
1. Check `Connection` object in telemetry
1. Verify RS485 wiring (A to A, B to B)
1. Check Modbus address conflicts

______________________________________________________________________

## Hardware Notes

### Supported Devices

- Sugar Valley NeoPool (generic)
- Hidrolife
- Aquascenic
- Oxilife
- Bionet
- Hidroniser
- UVScenic
- Station
- Brilix

### Recommended Hardware

- **M5Stack Atom Lite** with **Tail485** addon
- Provides ESP32, 3.3V logic, and RS485 interface
- No separate power supply needed
- Compact and easy to install

### Connections

- **GPIO1 (TX)** and **GPIO3 (RX)** recommended
- Use **WIFI** or **EXTERN** connector on NeoPool
- Avoid **DISPLAY** connector if display is connected
- **3.3V logic only** (not 5V tolerant)

______________________________________________________________________

## Advanced Features

### Low-Level Register Access

For advanced users, direct Modbus register access is available:

- `NPRead` - Read registers
- `NPWrite` - Write registers
- `NPBit` - Bit manipulation
- See **TASMOTA_NEOPOOL_MQTT_REFERENCE.md** section "Low-Level Register Access"

### Berry Scripting (ESP32)

ESP32 devices support Berry scripts for:

- Custom auxiliary relay controls
- Timer management
- Configuration backup/restore
- See Tasmota documentation for details

### Time Synchronization

Prevent clock drift by syncing daily:

```yaml
automation:
  - alias: "Sync Pool Time Daily"
    trigger:
      platform: time
      at: "03:00:00"
    action:
      service: mqtt.publish
      data:
        topic: "cmnd/poolcontroller/NPTime"
        payload: "0"
```

______________________________________________________________________

## Document Versions

| Document                          | Lines     | Size       | Last Updated |
| --------------------------------- | --------- | ---------- | ------------ |
| TASMOTA_NEOPOOL_MQTT_REFERENCE.md | 1,670     | 40 KB      | 2025-12-13   |
| MQTT_TOPIC_QUICK_REFERENCE.md     | 353       | 8.3 KB     | 2025-12-13   |
| HA_INTEGRATION_IMPLEMENTATION.md  | 1,091     | 27 KB      | 2025-12-13   |
| HA_MQTT_INTEGRATION_GUIDE.md      | 1,704     | 45 KB      | 2025-12-13   |
| ha_neopool_mqtt_package.yaml      | N/A       | 29 KB      | 2025-12-13   |
| **Total**                         | **4,818** | **149 KB** |              |

______________________________________________________________________

## Contributing

Found an error or have an improvement?

1. Check the specific document for the area you want to update
1. Make changes maintaining the existing format
1. Update this README.md if adding new documents
1. Test YAML configurations before committing

______________________________________________________________________

## License

Documentation follows Tasmota project licensing.

Source: <https://tasmota.github.io/docs/NeoPool/>

______________________________________________________________________

## Additional Resources

### Official Links

- **Tasmota NeoPool Documentation:** <https://tasmota.github.io/docs/NeoPool/>
- **Tasmota GitHub:** <https://github.com/arendst/Tasmota>
- **Home Assistant MQTT Documentation:** <https://www.home-assistant.io/integrations/mqtt/>

### Related Projects

- Tasmota firmware for ESP devices
- Home Assistant MQTT integration
- NeoPool controller hardware

______________________________________________________________________

**Last Updated:** 2025-12-13
**Total Documentation:** 4,818 lines, 149 KB
**Document Count:** 5 files
