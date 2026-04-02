# NeoPool MQTT Documentation Index

This directory contains documentation for the Home Assistant NeoPool MQTT integration.

______________________________________________________________________

## Documentation Files

### TASMOTA_NEOPOOL_MQTT_REFERENCE.md

Complete technical reference for Tasmota NeoPool MQTT protocol: topic structure,
JSON payload format, all sensor readings, commands, state enumerations, value ranges,
and low-level Modbus register access.

### MQTT_TOPIC_QUICK_REFERENCE.md

Quick reference for MQTT topics and commands: topic patterns, command tables,
JSON path examples, state mappings, mosquitto_pub examples, and common automation patterns.

### HA_INTEGRATION_IMPLEMENTATION.md

Implementation guide for the Home Assistant custom integration: architecture, entity
definitions for all platforms (sensors, binary sensors, numbers, selects, switches),
dynamic entity creation, constants, data processing, and error handling.

### HA_MQTT_INTEGRATION_GUIDE.md

Comprehensive guide for YAML-based MQTT setup: step-by-step instructions, complete entity
configurations, automation examples, Lovelace UI cards, notifications, and troubleshooting.

### ha_neopool_mqtt_package.yaml

Ready-to-use Home Assistant YAML package. Drop into `packages/` directory for immediate
deployment. Contains all MQTT sensor, binary_sensor, number, select, and switch definitions.

______________________________________________________________________

## Quick Start

**Users (YAML):** Start with **MQTT_TOPIC_QUICK_REFERENCE.md**, deploy
**ha_neopool_mqtt_package.yaml**, customize with **HA_MQTT_INTEGRATION_GUIDE.md**.

**Developers (Custom Integration):** Read **TASMOTA_NEOPOOL_MQTT_REFERENCE.md** for protocol
details, follow **HA_INTEGRATION_IMPLEMENTATION.md** for development.

______________________________________________________________________

## Additional Resources

- [Tasmota NeoPool Documentation](https://tasmota.github.io/docs/NeoPool/)
- [Tasmota GitHub](https://github.com/arendst/Tasmota)
- [Home Assistant MQTT Documentation](https://www.home-assistant.io/integrations/mqtt/)
