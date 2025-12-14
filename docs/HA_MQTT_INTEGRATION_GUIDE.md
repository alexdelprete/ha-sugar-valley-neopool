# Home Assistant MQTT Integration API Guide

This document provides a comprehensive guide to using the official Home Assistant MQTT integration
as a dependency in custom integrations. It is based on the analysis of the Home Assistant Core MQTT
component at `homeassistant/components/mqtt/`.

## Table of Contents

1. [Overview](#overview)
1. [Declaring MQTT as a Dependency](#declaring-mqtt-as-a-dependency)
1. [Publishing Messages](#publishing-messages)
1. [Subscribing to Topics](#subscribing-to-topics)
1. [Entity Base Classes](#entity-base-classes)
1. [QoS Handling](#qos-handling)
1. [Connection State Management](#connection-state-management)
1. [Discovery Patterns](#discovery-patterns)
1. [Best Practices](#best-practices)
1. [Complete Examples](#complete-examples)

______________________________________________________________________

## Overview

The Home Assistant MQTT integration provides a comprehensive framework for MQTT-based
integrations. Instead of managing MQTT connections directly, custom integrations should use the
official MQTT integration as a dependency.

### Key Benefits

- Centralized connection management
- Automatic reconnection handling
- Built-in subscription management
- Entity base classes with common functionality
- Support for MQTT discovery
- Proper QoS and retain flag handling

______________________________________________________________________

## Declaring MQTT as a Dependency

### manifest.json

Declare the MQTT integration as a dependency in your `manifest.json`:

```json
{
  "domain": "your_integration",
  "name": "Your Integration",
  "dependencies": ["mqtt"],
  "version": "1.0.0"
}
```

### Checking MQTT Availability

Before using MQTT functionality, verify the integration is available:

```python
from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.const import CONF_PLATFORM

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up your integration from a config entry."""

    # Wait for MQTT client to be available (up to 50 seconds)
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    # Check if MQTT is connected
    if mqtt.is_connected(hass):
        _LOGGER.info("MQTT is connected")

    return True
```

### Accessing MQTT Data

```python
from homeassistant.components.mqtt.models import MqttData

# Access MQTT data from hass.data
mqtt_data: MqttData = hass.data[mqtt.DATA_MQTT]

# Check connection status
is_connected = mqtt_data.client.connected
```

______________________________________________________________________

## Publishing Messages

### Using async_publish()

The primary method for publishing MQTT messages:

```python
from homeassistant.components import mqtt

async def publish_command(hass: HomeAssistant, topic: str, payload: str):
    """Publish a command to MQTT."""
    await mqtt.async_publish(
        hass=hass,
        topic=topic,
        payload=payload,
        qos=0,  # Quality of Service (0, 1, or 2)
        retain=False,  # Whether to retain the message
        encoding="utf-8"  # Payload encoding
    )
```

### Function Signature

```python
async def async_publish(
    hass: HomeAssistant,
    topic: str,
    payload: str | bytes,
    qos: int = 0,
    retain: bool = False,
    encoding: str = "utf-8"
) -> None
```

### Parameters

- **topic** (str): MQTT topic to publish to. Must not contain wildcards (+, #)
- **payload** (str | bytes): Message payload. Strings are encoded using the specified encoding
- **qos** (int): Quality of Service level (0, 1, or 2). Default: 0
- **retain** (bool): Whether the broker should retain the message. Default: False
- **encoding** (str): Character encoding for string payloads. Default: "utf-8"

### Topic Validation

Use the utility function to validate publish topics:

```python
from homeassistant.components.mqtt.util import valid_publish_topic
import voluptuous as vol

try:
    validated_topic = valid_publish_topic("your/topic/name")
except vol.Invalid as err:
    _LOGGER.error("Invalid publish topic: %s", err)
```

### Publishing with Acknowledgment

For QoS 1 and 2, the publish operation waits for acknowledgment (10-second timeout):

```python
# QoS 1: At least once delivery
await mqtt.async_publish(
    hass,
    "device/command",
    "ON",
    qos=1
)

# QoS 2: Exactly once delivery
await mqtt.async_publish(
    hass,
    "device/command",
    "START",
    qos=2
)
```

### Example: Publishing Binary Data

```python
# Publishing binary data (e.g., firmware updates)
binary_payload = b'\x00\x01\x02\x03'
await mqtt.async_publish(
    hass,
    "device/firmware/update",
    binary_payload,
    qos=1,
    retain=False
)
```

______________________________________________________________________

## Subscribing to Topics

### Using async_subscribe()

Subscribe to MQTT topics and receive messages via a callback:

```python
from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import callback

@callback
def message_received(msg: ReceiveMessage) -> None:
    """Handle received MQTT message."""
    topic = msg.topic
    payload = msg.payload
    qos = msg.qos
    retain = msg.retain

    _LOGGER.info(
        "Received message on %s: %s (QoS: %d, Retain: %s)",
        topic, payload, qos, retain
    )

async def subscribe_to_topic(hass: HomeAssistant):
    """Subscribe to an MQTT topic."""
    # Subscribe returns an unsubscribe callable
    unsubscribe = await mqtt.async_subscribe(
        hass=hass,
        topic="device/status",
        msg_callback=message_received,
        qos=0,
        encoding="utf-8"
    )

    # Store unsubscribe for cleanup
    return unsubscribe
```

### Function Signature

```python
async def async_subscribe(
    hass: HomeAssistant,
    topic: str,
    msg_callback: Callable[[ReceiveMessage], None],
    qos: int = 0,
    encoding: str | None = "utf-8"
) -> Callable[[], None]
```

### Parameters

- **topic** (str): MQTT topic to subscribe to. Supports wildcards (+ for single level, # for multi-level)
- **msg_callback** (Callable): Callback function to handle received messages
- **qos** (int): Quality of Service level (0, 1, or 2). Default: 0
- **encoding** (str | None): Character encoding for payloads. Use None for binary data. Default: "utf-8"

### Return Value

Returns an async callable that unsubscribes from the topic when called.

### ReceiveMessage Object

The callback receives a `ReceiveMessage` object with the following attributes:

```python
@dataclass(frozen=True, slots=True)
class ReceiveMessage:
    topic: str                    # Topic the message was received on
    payload: str | bytes          # Message payload (str if encoding specified,
                                  # bytes otherwise)
    qos: int                      # Quality of Service level
    retain: bool                  # Whether message was retained
    subscribed_topic: str         # Original subscription topic (if wildcards used)
    timestamp: datetime           # When message was received
```

### Wildcard Subscriptions

```python
# Single-level wildcard (+)
await mqtt.async_subscribe(
    hass,
    "devices/+/temperature",  # Matches devices/room1/temperature, devices/room2/temperature
    callback,
    qos=0
)

# Multi-level wildcard (#)
await mqtt.async_subscribe(
    hass,
    "devices/#",  # Matches devices/room1/temp, devices/room1/humid, devices/room2/status
    callback,
    qos=0
)
```

### Topic Validation

```python
from homeassistant.components.mqtt.util import valid_subscribe_topic
import voluptuous as vol

try:
    validated_topic = valid_subscribe_topic("devices/+/status")
except vol.Invalid as err:
    _LOGGER.error("Invalid subscribe topic: %s", err)
```

### Managing Subscriptions in __init__.py

```python
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

DOMAIN = "your_integration"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # Create storage for unsubscribe functions
    hass.data.setdefault(DOMAIN, {})

    # Subscribe to topics
    unsubscribe_status = await mqtt.async_subscribe(
        hass,
        "device/status",
        handle_status_message,
        qos=1
    )

    unsubscribe_data = await mqtt.async_subscribe(
        hass,
        "device/data",
        handle_data_message,
        qos=0
    )

    # Store unsubscribe functions
    hass.data[DOMAIN][entry.entry_id] = {
        "unsub_status": unsubscribe_status,
        "unsub_data": unsubscribe_data,
    }

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Get stored unsubscribe functions
    entry_data = hass.data[DOMAIN].pop(entry.entry_id)

    # Unsubscribe from all topics
    entry_data["unsub_status"]()
    entry_data["unsub_data"]()

    return True
```

______________________________________________________________________

## Entity Base Classes

The MQTT integration provides base classes for creating MQTT-enabled entities.

### MqttEntity Base Class

The primary base class for MQTT entities combines multiple mixins:

```python
from homeassistant.components.mqtt.entity import MqttEntity
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import callback

class MyMqttSensor(MqttEntity, SensorEntity):
    """MQTT-based sensor entity."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the sensor."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return SENSOR_SCHEMA

    def _setup_from_config(self, config):
        """Set up from configuration."""
        self._attr_name = config.get(CONF_NAME)
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    @callback
    def _prepare_subscribe_topics(self):
        """Prepare to subscribe to topics."""
        topics = {}

        # Add state topic subscription
        def add_subscription(topics, config_key, msg_callback):
            """Add a subscription."""
            if self._config.get(config_key) is not None:
                topics[config_key] = {
                    "topic": self._config[config_key],
                    "msg_callback": msg_callback,
                    "qos": self._config.get(CONF_QOS, 0),
                    "encoding": self._config.get(CONF_ENCODING, "utf-8"),
                }

        add_subscription(topics, CONF_STATE_TOPIC, self._state_message_received)

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self):
        """Subscribe to MQTT topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @callback
    def _state_message_received(self, msg: ReceiveMessage):
        """Handle new MQTT state messages."""
        payload = msg.payload

        # Process payload
        self._attr_native_value = payload

        # Update entity
        self.async_write_ha_state()
```

### Required Methods

1. **config_schema()** - Static method returning the configuration schema
1. **\_setup_from_config()** - Initialize entity attributes from config
1. **\_prepare_subscribe_topics()** - Prepare topic subscriptions
1. **\_subscribe_topics()** - Activate topic subscriptions

### Inherited Mixins

#### MqttAttributesMixin

Handles JSON attributes from MQTT payloads.

```python
# Configuration
config = {
    CONF_JSON_ATTRIBUTES_TOPIC: "device/attributes",
    CONF_JSON_ATTRIBUTES_TEMPLATE: "{{ value_json }}"
}

# Attributes are automatically parsed from JSON payloads
```

#### MqttAvailabilityMixin

Manages entity availability through MQTT.

```python
# Configuration
config = {
    CONF_AVAILABILITY_TOPIC: "device/status",
    CONF_PAYLOAD_AVAILABLE: "online",
    CONF_PAYLOAD_NOT_AVAILABLE: "offline",
}

# Entity automatically becomes unavailable when offline payload received
```

#### MqttDiscoveryUpdateMixin

Handles dynamic updates from MQTT discovery messages.

```python
async def discovery_update(self, discovery_payload, discovery_hash):
    """Handle updated discovery message."""
    # Automatically updates configuration from discovery
    await super().discovery_update(discovery_payload, discovery_hash)
```

#### MqttEntityDeviceInfo

Manages device registry integration.

```python
# Configuration with device info
config = {
    CONF_DEVICE: {
        "identifiers": [["domain", "device_id"]],
        "name": "Device Name",
        "manufacturer": "Manufacturer",
        "model": "Model",
        "sw_version": "1.0.0",
    }
}
```

### Helper: add_subscription()

Use the `add_subscription()` helper in entities:

```python
from homeassistant.components.mqtt import subscription

@callback
def _prepare_subscribe_topics(self):
    """Prepare to subscribe to topics."""
    topics = {}

    def add_subscription(config_key, msg_callback, qos=0):
        """Add a subscription helper."""
        if self._config.get(config_key) is not None:
            topics[config_key] = {
                "topic": self._config[config_key],
                "msg_callback": msg_callback,
                "qos": qos,
                "encoding": "utf-8",
            }

    # Add subscriptions
    add_subscription(CONF_STATE_TOPIC, self._state_received)
    add_subscription(CONF_TEMPERATURE_TOPIC, self._temp_received)
    add_subscription(CONF_MODE_TOPIC, self._mode_received, qos=1)

    self._sub_state = subscription.async_prepare_subscribe_topics(
        self.hass, self._sub_state, topics
    )
```

### Publishing from Entities

Entities can publish messages using two methods:

```python
# Method 1: Direct publish
await mqtt.async_publish(
    self.hass,
    "device/command",
    "ON",
    qos=1,
    retain=False
)

# Method 2: Using entity's publish helper (if available)
await self.async_publish(
    topic="device/command",
    payload="ON",
    qos=1,
    retain=False
)
```

### Example: MQTT Switch Entity

```python
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.mqtt.entity import MqttEntity
from homeassistant.components.mqtt import subscription
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import callback

class MqttSwitch(MqttEntity, SwitchEntity):
    """MQTT switch entity."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the switch."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

        self._attr_is_on = False
        self._optimistic = False

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return SWITCH_SCHEMA

    def _setup_from_config(self, config):
        """Set up from configuration."""
        self._attr_name = config.get(CONF_NAME)
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)

        self._command_topic = config.get(CONF_COMMAND_TOPIC)
        self._state_topic = config.get(CONF_STATE_TOPIC)

        self._payload_on = config.get(CONF_PAYLOAD_ON, "ON")
        self._payload_off = config.get(CONF_PAYLOAD_OFF, "OFF")

        # Optimistic if no state topic
        self._optimistic = self._state_topic is None

    @callback
    def _prepare_subscribe_topics(self):
        """Prepare to subscribe to topics."""
        topics = {}

        if self._state_topic:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._state_topic,
                "msg_callback": self._state_message_received,
                "qos": self._config.get(CONF_QOS, 0),
            }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self):
        """Subscribe to MQTT topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @callback
    def _state_message_received(self, msg: ReceiveMessage):
        """Handle new MQTT state messages."""
        payload = msg.payload

        if payload == self._payload_on:
            self._attr_is_on = True
        elif payload == self._payload_off:
            self._attr_is_on = False
        else:
            _LOGGER.warning("Invalid payload: %s", payload)
            return

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._payload_on,
            qos=self._config.get(CONF_QOS, 0),
            retain=self._config.get(CONF_RETAIN, False)
        )

        if self._optimistic:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._payload_off,
            qos=self._config.get(CONF_QOS, 0),
            retain=self._config.get(CONF_RETAIN, False)
        )

        if self._optimistic:
            self._attr_is_on = False
            self.async_write_ha_state()
```

______________________________________________________________________

## QoS Handling

### QoS Levels

MQTT supports three Quality of Service levels:

- **QoS 0**: At most once delivery (fire and forget)
- **QoS 1**: At least once delivery (acknowledged)
- **QoS 2**: Exactly once delivery (assured)

### Default Values

```python
from homeassistant.components.mqtt.const import DEFAULT_QOS

# Default QoS is 0
DEFAULT_QOS = 0
```

### Validation

```python
from homeassistant.components.mqtt.util import valid_qos_schema
import voluptuous as vol

# QoS schema validation
QOS_SCHEMA = vol.All(vol.Coerce(int), valid_qos_schema)

# Usage in config schema
SCHEMA = vol.Schema({
    vol.Optional(CONF_QOS, default=0): QOS_SCHEMA,
})
```

### Best Practices

1. **Use QoS 0 for frequent updates** (temperature, humidity sensors)

   ```python
   await mqtt.async_publish(hass, "sensor/temperature", "22.5", qos=0)
   ```

1. **Use QoS 1 for commands** (switch on/off, mode changes)

   ```python
   await mqtt.async_publish(hass, "switch/command", "ON", qos=1)
   ```

1. **Use QoS 2 sparingly** (critical commands only, has performance overhead)

   ```python
   await mqtt.async_publish(hass, "alarm/arm", "AWAY", qos=2)
   ```

### Retain Flag

The retain flag tells the broker to store the last message:

```python
# Retain status messages
await mqtt.async_publish(
    hass,
    "device/status",
    "online",
    qos=1,
    retain=True  # Last status is stored by broker
)

# Don't retain frequent sensor readings
await mqtt.async_publish(
    hass,
    "sensor/temperature",
    "22.5",
    qos=0,
    retain=False  # Don't store old temperature readings
)
```

### Constants

```python
from homeassistant.components.mqtt.const import (
    DEFAULT_QOS,      # 0
    DEFAULT_RETAIN,   # False
    DEFAULT_ENCODING, # "utf-8"
)
```

______________________________________________________________________

## Connection State Management

### Checking Connection Status

```python
from homeassistant.components import mqtt

def is_mqtt_connected(hass: HomeAssistant) -> bool:
    """Check if MQTT is connected."""
    return mqtt.is_connected(hass)
```

### Subscribing to Connection State Changes

Use the connection state signal to monitor connection changes:

```python
from homeassistant.components.mqtt import (
    async_subscribe_connection_status,
    CONF_BROKER,
)
from homeassistant.core import callback

@callback
def connection_status_changed(connected: bool) -> None:
    """Handle MQTT connection status changes."""
    if connected:
        _LOGGER.info("MQTT connected")
        # Re-publish birth message, re-subscribe, etc.
    else:
        _LOGGER.warning("MQTT disconnected")
        # Handle disconnection

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # Subscribe to connection status changes
    unsubscribe = async_subscribe_connection_status(
        hass,
        connection_status_changed
    )

    # Store unsubscribe for cleanup
    hass.data[DOMAIN][entry.entry_id]["unsub_connection"] = unsubscribe

    return True
```

### Connection State Signal

```python
from homeassistant.components.mqtt.const import MQTT_CONNECTION_STATE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# Alternative method using dispatcher
@callback
def _mqtt_connected():
    """Handle MQTT connection."""
    _LOGGER.info("MQTT connected")

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""

    # Subscribe to connection signal
    async_dispatcher_connect(
        hass,
        MQTT_CONNECTION_STATE,
        _mqtt_connected
    )

    return True
```

### Waiting for MQTT Client

Use the utility function to wait for MQTT to be ready:

```python
from homeassistant.components.mqtt import async_wait_for_mqtt_client

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # Wait up to 50 seconds for MQTT client
    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT not available")
        return False

    # MQTT is ready, proceed with setup
    return True
```

### Automatic Reconnection

The MQTT integration handles reconnection automatically:

- Reconnects every 10 seconds when disconnected
- Resubscribes to all topics on reconnection
- Buffers messages during disconnection (up to 8 MiB, minimum 128 KiB)

### Birth and Will Messages

Configure birth and will messages for connection status:

```python
# In MQTT integration configuration
BIRTH_MESSAGE = {
    "topic": "homeassistant/status",
    "payload": "online",
    "qos": 1,
    "retain": True,
}

WILL_MESSAGE = {
    "topic": "homeassistant/status",
    "payload": "offline",
    "qos": 1,
    "retain": True,
}
```

Entities can subscribe to the birth message topic to detect reconnection.

______________________________________________________________________

## Discovery Patterns

MQTT Discovery enables automatic entity creation without manual configuration.

### Discovery Topic Pattern

The standard discovery topic pattern is:

```text
<discovery_prefix>/<component>/<node_id>/<object_id>/config
```

- **discovery_prefix**: Default is "homeassistant"
- **component**: Entity type (sensor, binary_sensor, switch, etc.)
- **node_id**: Optional device/node identifier
- **object_id**: Unique object identifier

### Discovery Topic Examples

```text
homeassistant/sensor/pool/temperature/config
homeassistant/binary_sensor/pool/filtration/config
homeassistant/switch/pool/pump/config
homeassistant/climate/pool/heater/config
```

### Discovery Payload Structure

Discovery payloads are JSON objects with the entity configuration:

```json
{
  "name": "Pool Temperature",
  "device_class": "temperature",
  "state_topic": "pool/sensor/temperature",
  "unit_of_measurement": "°C",
  "value_template": "{{ value_json.temperature }}",
  "unique_id": "pool_temp_sensor",
  "device": {
    "identifiers": ["pool_controller_001"],
    "name": "Pool Controller",
    "manufacturer": "Company Name",
    "model": "Model X",
    "sw_version": "1.0.0"
  }
}
```

### Abbreviated Keys

MQTT Discovery supports abbreviated configuration keys to reduce payload size:

```json
{
  "~": "pool/sensor",
  "name": "Temperature",
  "stat_t": "~/temperature",
  "unit_of_meas": "°C",
  "val_tpl": "{{ value_json.temp }}",
  "uniq_id": "pool_temp"
}
```

The `~` character is replaced with the base topic throughout the payload.

### Common Discovery Fields

```python
# Device Information
CONF_DEVICE = {
    "identifiers": [["domain", "device_id"]],  # Unique device identifier(s)
    "name": "Device Name",                      # Device name
    "manufacturer": "Manufacturer",             # Manufacturer name
    "model": "Model Name",                      # Model name
    "sw_version": "1.0.0",                     # Software version
    "hw_version": "1.0",                       # Hardware version
    "configuration_url": "http://device.ip",   # Configuration URL
    "suggested_area": "Pool",                  # Suggested area
}

# Origin Information (HA 2024.2+)
CONF_ORIGIN = {
    "name": "Integration Name",
    "sw_version": "1.0.0",
    "support_url": "https://github.com/user/repo"
}

# Availability
CONF_AVAILABILITY = {
    "topic": "device/status",
    "payload_available": "online",
    "payload_not_available": "offline",
}

# Multiple Availability Topics
CONF_AVAILABILITY = [
    {
        "topic": "device/status",
        "payload_available": "online"
    },
    {
        "topic": "mqtt/status",
        "payload_available": "online"
    }
]
CONF_AVAILABILITY_MODE = "all"  # all, any, latest
```

### Publishing Discovery Messages

```python
from homeassistant.components import mqtt
import json

async def publish_discovery(hass: HomeAssistant):
    """Publish MQTT discovery configuration."""

    discovery_topic = "homeassistant/sensor/pool/temperature/config"

    config = {
        "name": "Pool Temperature",
        "device_class": "temperature",
        "state_topic": "pool/sensor/temperature",
        "unit_of_measurement": "°C",
        "value_template": "{{ value_json.temperature }}",
        "unique_id": "pool_temp_sensor",
        "device": {
            "identifiers": [["pool", "controller_001"]],
            "name": "Pool Controller",
            "manufacturer": "Company",
            "model": "Pool-1000",
            "sw_version": "1.0.0",
        },
        "availability": {
            "topic": "pool/status",
            "payload_available": "online",
            "payload_not_available": "offline",
        },
    }

    # Publish discovery message
    await mqtt.async_publish(
        hass,
        discovery_topic,
        json.dumps(config),
        qos=1,
        retain=True  # Discovery messages should be retained
    )
```

### Removing Discovered Entities

To remove a discovered entity, publish an empty payload to its discovery topic:

```python
async def remove_discovery(hass: HomeAssistant):
    """Remove discovered entity."""

    discovery_topic = "homeassistant/sensor/pool/temperature/config"

    # Empty payload removes the entity
    await mqtt.async_publish(
        hass,
        discovery_topic,
        "",
        qos=1,
        retain=True
    )
```

### Discovery Best Practices

1. **Use retain=True** for discovery messages
1. **Include device information** to group entities
1. **Use unique_id** for entity identification
1. **Include availability topics** for proper status reporting
1. **Use abbreviated keys** to reduce MQTT traffic
1. **Publish on startup** and when configuration changes
1. **Remove on shutdown** (optional, for clean uninstall)

### Complete Discovery Example

```python
import json
from homeassistant.components import mqtt
from homeassistant.const import (
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

class PoolDiscoveryManager:
    """Manage MQTT discovery for pool devices."""

    def __init__(self, hass: HomeAssistant, device_id: str):
        """Initialize discovery manager."""
        self.hass = hass
        self.device_id = device_id
        self.discovery_prefix = "homeassistant"
        self.discovered_entities = []

    def _get_device_config(self):
        """Get device configuration."""
        return {
            "identifiers": [["pool", self.device_id]],
            "name": "Pool Controller",
            "manufacturer": "Company",
            "model": "Pool-1000",
            "sw_version": "1.0.0",
            "configuration_url": f"http://{self.device_id}.local",
        }

    def _get_availability_config(self):
        """Get availability configuration."""
        return [
            {
                "topic": f"pool/{self.device_id}/status",
                "payload_available": "online",
                "payload_not_available": "offline",
            },
            {
                "topic": "homeassistant/status",
                "payload_available": "online",
                "payload_not_available": "offline",
            }
        ]

    async def publish_sensor_discovery(
        self,
        object_id: str,
        name: str,
        state_topic: str,
        device_class: str | None = None,
        unit: str | None = None,
        value_template: str | None = None,
    ):
        """Publish sensor discovery."""

        discovery_topic = (
            f"{self.discovery_prefix}/sensor/"
            f"{self.device_id}/{object_id}/config"
        )

        config = {
            "name": name,
            "state_topic": state_topic,
            "unique_id": f"{self.device_id}_{object_id}",
            "device": self._get_device_config(),
            "availability": self._get_availability_config(),
            "availability_mode": "all",
        }

        if device_class:
            config["device_class"] = device_class
        if unit:
            config["unit_of_measurement"] = unit
        if value_template:
            config["value_template"] = value_template

        await mqtt.async_publish(
            self.hass,
            discovery_topic,
            json.dumps(config),
            qos=1,
            retain=True
        )

        self.discovered_entities.append(discovery_topic)

    async def publish_switch_discovery(
        self,
        object_id: str,
        name: str,
        state_topic: str,
        command_topic: str,
        payload_on: str = "ON",
        payload_off: str = "OFF",
    ):
        """Publish switch discovery."""

        discovery_topic = (
            f"{self.discovery_prefix}/switch/"
            f"{self.device_id}/{object_id}/config"
        )

        config = {
            "name": name,
            "state_topic": state_topic,
            "command_topic": command_topic,
            "payload_on": payload_on,
            "payload_off": payload_off,
            "unique_id": f"{self.device_id}_{object_id}",
            "device": self._get_device_config(),
            "availability": self._get_availability_config(),
            "availability_mode": "all",
        }

        await mqtt.async_publish(
            self.hass,
            discovery_topic,
            json.dumps(config),
            qos=1,
            retain=True
        )

        self.discovered_entities.append(discovery_topic)

    async def remove_all_discoveries(self):
        """Remove all discovered entities."""
        for topic in self.discovered_entities:
            await mqtt.async_publish(
                self.hass,
                topic,
                "",
                qos=1,
                retain=True
            )
        self.discovered_entities.clear()

# Usage
async def setup_discovery(hass: HomeAssistant, device_id: str):
    """Set up MQTT discovery."""

    manager = PoolDiscoveryManager(hass, device_id)

    # Publish temperature sensor
    await manager.publish_sensor_discovery(
        object_id="temperature",
        name="Pool Temperature",
        state_topic=f"pool/{device_id}/temperature",
        device_class="temperature",
        unit="°C",
        value_template="{{ value_json.temp }}",
    )

    # Publish pump switch
    await manager.publish_switch_discovery(
        object_id="pump",
        name="Pool Pump",
        state_topic=f"pool/{device_id}/pump/state",
        command_topic=f"pool/{device_id}/pump/set",
        payload_on="1",
        payload_off="0",
    )

    return manager
```

______________________________________________________________________

## Best Practices

### 1. Use Appropriate QoS Levels

```python
# Frequent updates - QoS 0
await mqtt.async_publish(hass, "sensor/temperature", "22.5", qos=0)

# Commands - QoS 1
await mqtt.async_publish(hass, "switch/command", "ON", qos=1)

# Critical commands - QoS 2 (use sparingly)
await mqtt.async_publish(hass, "alarm/arm", "AWAY", qos=2)
```

### 2. Validate Topics

```python
from homeassistant.components.mqtt.util import (
    valid_publish_topic,
    valid_subscribe_topic,
)
import voluptuous as vol

# Validate before use
try:
    topic = valid_publish_topic(user_topic)
except vol.Invalid:
    _LOGGER.error("Invalid topic")
```

### 3. Handle Connection State

```python
from homeassistant.components.mqtt import async_subscribe_connection_status

@callback
def connection_changed(connected: bool):
    """Handle connection changes."""
    if connected:
        # Republish state, resubscribe, etc.
        pass

# Subscribe to connection status
unsub = async_subscribe_connection_status(hass, connection_changed)
```

### 4. Clean Up Subscriptions

```python
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    # Get stored unsubscribe functions
    entry_data = hass.data[DOMAIN].pop(entry.entry_id)

    # Call all unsubscribe functions
    for unsub in entry_data["unsubscribes"]:
        unsub()

    return True
```

### 5. Use Entity Base Classes

```python
# Prefer MqttEntity over manual subscription management
from homeassistant.components.mqtt.entity import MqttEntity

class MyEntity(MqttEntity, SensorEntity):
    """Use MqttEntity for automatic subscription handling."""
    pass
```

### 6. Implement Availability

```python
# Always include availability in discovery
config = {
    "availability": {
        "topic": "device/status",
        "payload_available": "online",
        "payload_not_available": "offline",
    }
}
```

### 7. Use Unique IDs

```python
# Always set unique_id for entities
self._attr_unique_id = f"{device_id}_{sensor_type}"
```

### 8. Retain Discovery Messages

```python
# Discovery messages should always be retained
await mqtt.async_publish(
    hass,
    discovery_topic,
    json.dumps(config),
    retain=True
)
```

### 9. Handle Encoding Properly

```python
# For text data
await mqtt.async_subscribe(
    hass,
    topic,
    callback,
    encoding="utf-8"
)

# For binary data
await mqtt.async_subscribe(
    hass,
    topic,
    callback,
    encoding=None  # Returns bytes
)
```

### 10. Use Templates for Flexibility

```python
from homeassistant.components.mqtt.models import MqttValueTemplate

# Create value template
value_template = MqttValueTemplate(
    "{{ value_json.temperature }}",
    hass=hass
)

# Render template
result = value_template.async_render(payload)
```

______________________________________________________________________

## Complete Examples

### Example 1: Simple Sensor Integration

```python
"""Simple MQTT sensor integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.helpers.entity_platform import AddEntitiesCallback

DOMAIN = "simple_mqtt_sensor"

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""

    # Wait for MQTT
    if not await mqtt.async_wait_for_mqtt_client(hass):
        return False

    # Create sensors
    sensors = [
        SimpleMqttSensor(hass, "temperature", "Temperature", "sensor/temp"),
        SimpleMqttSensor(hass, "humidity", "Humidity", "sensor/humid"),
    ]

    async_add_entities(sensors)

from homeassistant.components.sensor import SensorEntity

class SimpleMqttSensor(SensorEntity):
    """Simple MQTT sensor."""

    def __init__(self, hass, sensor_id, name, topic):
        """Initialize sensor."""
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_{sensor_id}"
        self._attr_name = name
        self._topic = topic
        self._attr_native_value = None
        self._unsubscribe = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT topic."""
        self._unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._topic,
            self._message_received,
            qos=0
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from MQTT topic."""
        if self._unsubscribe:
            self._unsubscribe()

    @callback
    def _message_received(self, msg: ReceiveMessage):
        """Handle new MQTT messages."""
        self._attr_native_value = msg.payload
        self.async_write_ha_state()
```

### Example 2: Switch with Command Publishing

```python
"""MQTT switch with command publishing."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import callback

class MqttCommandSwitch(SwitchEntity):
    """MQTT switch with command topic."""

    def __init__(self, hass, name, state_topic, command_topic):
        """Initialize the switch."""
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = f"mqtt_switch_{name}"
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._attr_is_on = False
        self._unsubscribe = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT topics."""
        if self._state_topic:
            self._unsubscribe = await mqtt.async_subscribe(
                self.hass,
                self._state_topic,
                self._state_received,
                qos=1
            )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from MQTT topics."""
        if self._unsubscribe:
            self._unsubscribe()

    @callback
    def _state_received(self, msg: ReceiveMessage):
        """Handle state updates."""
        if msg.payload == "ON":
            self._attr_is_on = True
        elif msg.payload == "OFF":
            self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            "ON",
            qos=1,
            retain=False
        )

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            "OFF",
            qos=1,
            retain=False
        )
```

### Example 3: Integration with Discovery

```python
"""MQTT integration with discovery support."""
import json
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import mqtt

DOMAIN = "mqtt_pool"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""

    # Wait for MQTT
    if not await mqtt.async_wait_for_mqtt_client(hass):
        return False

    # Store data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device_id": entry.data["device_id"],
        "unsubscribes": [],
    }

    # Subscribe to connection status
    unsub_conn = mqtt.async_subscribe_connection_status(
        hass,
        lambda connected: handle_connection(hass, entry, connected)
    )
    hass.data[DOMAIN][entry.entry_id]["unsubscribes"].append(unsub_conn)

    # Publish discovery
    await publish_discovery(hass, entry)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "switch"]
    )

    return True

@callback
def handle_connection(hass: HomeAssistant, entry: ConfigEntry, connected: bool):
    """Handle MQTT connection changes."""
    if connected:
        # Republish discovery on reconnection
        hass.async_create_task(publish_discovery(hass, entry))

async def publish_discovery(hass: HomeAssistant, entry: ConfigEntry):
    """Publish MQTT discovery messages."""
    device_id = entry.data["device_id"]

    # Device configuration
    device_config = {
        "identifiers": [["pool", device_id]],
        "name": "Pool Controller",
        "manufacturer": "Company",
        "model": "Pool-1000",
        "sw_version": "1.0.0",
    }

    # Temperature sensor
    temp_config = {
        "name": "Pool Temperature",
        "device_class": "temperature",
        "state_topic": f"pool/{device_id}/temperature",
        "unit_of_measurement": "°C",
        "unique_id": f"{device_id}_temp",
        "device": device_config,
    }

    await mqtt.async_publish(
        hass,
        f"homeassistant/sensor/{device_id}/temperature/config",
        json.dumps(temp_config),
        qos=1,
        retain=True
    )

    # Pump switch
    pump_config = {
        "name": "Pool Pump",
        "state_topic": f"pool/{device_id}/pump/state",
        "command_topic": f"pool/{device_id}/pump/set",
        "unique_id": f"{device_id}_pump",
        "device": device_config,
    }

    await mqtt.async_publish(
        hass,
        f"homeassistant/switch/{device_id}/pump/config",
        json.dumps(pump_config),
        qos=1,
        retain=True
    )

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "switch"]
    )

    if unload_ok:
        # Unsubscribe from MQTT
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        for unsub in entry_data["unsubscribes"]:
            unsub()

        # Remove discovery (optional)
        device_id = entry.data["device_id"]
        await mqtt.async_publish(
            hass,
            f"homeassistant/sensor/{device_id}/temperature/config",
            "",
            retain=True
        )
        await mqtt.async_publish(
            hass,
            f"homeassistant/switch/{device_id}/pump/config",
            "",
            retain=True
        )

    return unload_ok
```

### Example 4: Using MqttEntity Base Class

```python
"""Complete example using MqttEntity."""
from homeassistant.components.mqtt.entity import MqttEntity
from homeassistant.components.mqtt import subscription
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
import voluptuous as vol

CONF_STATE_TOPIC = "state_topic"
CONF_QOS = "qos"

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_STATE_TOPIC): str,
    vol.Optional(CONF_QOS, default=0): vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
})

class PoolTemperatureSensor(MqttEntity, SensorEntity):
    """Pool temperature sensor using MqttEntity."""

    _attr_device_class = "temperature"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, hass, config, config_entry, discovery_data=None):
        """Initialize the sensor."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

        # Initialize subscription state
        self._sub_state = None

    @staticmethod
    def config_schema():
        """Return configuration schema."""
        return SENSOR_SCHEMA

    def _setup_from_config(self, config):
        """Set up from configuration."""
        self._attr_name = "Pool Temperature"
        self._attr_unique_id = "pool_temp_sensor"

    @callback
    def _prepare_subscribe_topics(self):
        """Prepare to subscribe to topics."""
        topics = {}

        # Add state topic subscription
        topics[CONF_STATE_TOPIC] = {
            "topic": self._config[CONF_STATE_TOPIC],
            "msg_callback": self._state_message_received,
            "qos": self._config.get(CONF_QOS, 0),
            "encoding": "utf-8",
        }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            topics
        )

    async def _subscribe_topics(self):
        """Subscribe to MQTT topics."""
        await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state
        )

    @callback
    def _state_message_received(self, msg: ReceiveMessage):
        """Handle new MQTT state messages."""
        try:
            # Parse temperature value
            self._attr_native_value = float(msg.payload)
        except ValueError:
            _LOGGER.warning("Invalid temperature value: %s", msg.payload)
            return

        # Update entity state
        self.async_write_ha_state()
```

______________________________________________________________________

## Summary

This guide covers the essential APIs and patterns for integrating with the Home Assistant MQTT component:

1. **Dependency Declaration**: Add "mqtt" to dependencies in manifest.json
1. **Publishing**: Use `mqtt.async_publish()` with appropriate QoS and retain flags
1. **Subscribing**: Use `mqtt.async_subscribe()` and handle callbacks properly
1. **Entities**: Extend `MqttEntity` base class for automatic subscription management
1. **QoS**: Choose appropriate levels (0 for sensors, 1 for commands)
1. **Connection**: Monitor connection state and handle reconnections
1. **Discovery**: Use standard discovery topics and payloads for auto-configuration
1. **Best Practices**: Validate topics, clean up subscriptions, use unique IDs

By following these patterns, custom integrations can properly leverage the HA MQTT integration for
reliable, maintainable MQTT communication.

## References

- Home Assistant MQTT Integration: <https://github.com/home-assistant/core/tree/dev/homeassistant/components/mqtt>
- MQTT Documentation: <https://www.home-assistant.io/integrations/mqtt/>
- MQTT Discovery: <https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery>
