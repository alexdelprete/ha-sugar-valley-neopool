# NeoPool MQTT Topics - Quick Reference

## MQTT Topic Overview

### Topic Structure

```text
tele/%topic%/SENSOR         # Telemetry data (periodic or on change)
cmnd/%topic%/<command>      # Send commands
stat/%topic%/RESULT         # Command responses
```

Replace `%topic%` with your device topic (e.g., "poolcontroller")

______________________________________________________________________

## Telemetry Topic

### Topic: `tele/%topic%/SENSOR`

**Published automatically at TelePeriod intervals or on value changes**

Minimal example:

```json
{
  "Time": "2025-01-15T14:30:00",
  "NeoPool": {
    "Temperature": 23.5,
    "pH": {
      "Data": 7.2,
      "State": 0
    },
    "Redox": {
      "Data": 750
    },
    "Filtration": {
      "State": 1,
      "Speed": 2,
      "Mode": 1
    },
    "Light": 0
  }
}
```

______________________________________________________________________

## Command Topics

### Filtration Control

| Topic                            | Payload       | Description                                               |
| -------------------------------- | ------------- | --------------------------------------------------------- |
| `cmnd/%topic%/NPFiltration`      | `0`           | Turn pump off                                             |
| `cmnd/%topic%/NPFiltration`      | `1`           | Turn pump on                                              |
| `cmnd/%topic%/NPFiltration`      | `1 2`         | Turn pump on at medium speed                              |
| `cmnd/%topic%/NPFiltrationmode`  | `0-4` or `13` | Set mode (Manual/Auto/Heating/Smart/Intelligent/Backwash) |
| `cmnd/%topic%/NPFiltrationspeed` | `1-3`         | Set speed (Low/Mid/High)                                  |

### Chemical Control

| Topic                       | Payload         | Description                          |
| --------------------------- | --------------- | ------------------------------------ |
| `cmnd/%topic%/NPpHMin`      | `7.0`           | Set pH minimum (0.0-14.0)            |
| `cmnd/%topic%/NPpHMax`      | `7.4`           | Set pH maximum (0.0-14.0)            |
| `cmnd/%topic%/NPRedox`      | `700`           | Set redox setpoint (0-1000 mV)       |
| `cmnd/%topic%/NPChlorine`   | `1.5`           | Set chlorine setpoint (0.0-10.0 ppm) |
| `cmnd/%topic%/NPHydrolysis` | `75`            | Set hydrolysis level (0-100% or g/h) |
| `cmnd/%topic%/NPIonization` | `5`             | Set ionization level                 |
| `cmnd/%topic%/NPBoost`      | `0` / `1` / `2` | Boost off/on/redox                   |

### Light Control

| Topic                  | Payload | Description  |
| ---------------------- | ------- | ------------ |
| `cmnd/%topic%/NPLight` | `0`     | Light off    |
| `cmnd/%topic%/NPLight` | `1`     | Light on     |
| `cmnd/%topic%/NPLight` | `2`     | Toggle light |

### Configuration

| Topic                       | Payload | Description                   |
| --------------------------- | ------- | ----------------------------- |
| `cmnd/%topic%/NPTelePeriod` | `0`     | Report only on changes        |
| `cmnd/%topic%/NPTelePeriod` | `60`    | Report every 60 seconds       |
| `cmnd/%topic%/NPTime`       | `0`     | Sync to local time            |
| `cmnd/%topic%/NPPHRes`      | `2`     | pH decimal places (0-3)       |
| `cmnd/%topic%/NPCLRes`      | `2`     | Chlorine decimal places (0-3) |
| `cmnd/%topic%/NPSetOption0` | `1`     | Enable data validation        |
| `cmnd/%topic%/NPSetOption1` | `1`     | Enable statistics (ESP32)     |

______________________________________________________________________

## JSON Paths for Sensors

Quick reference for extracting values from telemetry:

```python
# Main readings
temperature = data["NeoPool"]["Temperature"]
ph_current = data["NeoPool"]["pH"]["Data"]
ph_state = data["NeoPool"]["pH"]["State"]
redox_current = data["NeoPool"]["Redox"]["Data"]
chlorine_current = data["NeoPool"]["Chlorine"]["Data"]

# Filtration
filtration_on = data["NeoPool"]["Filtration"]["State"]  # 0/1
filtration_speed = data["NeoPool"]["Filtration"]["Speed"]  # 1/2/3
filtration_mode = data["NeoPool"]["Filtration"]["Mode"]  # 0-4, 13

# Hydrolysis
hydrolysis_level = data["NeoPool"]["Hydrolysis"]["Data"]
hydrolysis_state = data["NeoPool"]["Hydrolysis"]["State"]  # OFF/FLOW/POL1/POL2
hydrolysis_boost = data["NeoPool"]["Hydrolysis"]["Boost"]  # 0/1/2

# Light
light_on = data["NeoPool"]["Light"]  # 0/1

# Module detection
has_ph = data["NeoPool"]["Module"]["pH"]  # 0/1
has_redox = data["NeoPool"]["Module"]["Redox"]  # 0/1
has_hydrolysis = data["NeoPool"]["Module"]["Hydrolysis"]  # 0/1
```

______________________________________________________________________

## State Mappings

### pH State

```python
PH_STATES = {
    0: "OK",
    1: "pH Too High",
    2: "pH Too Low",
    3: "Pump Timeout",
    4: "pH High Warning",
    5: "pH Low Warning",
    6: "Tank Empty"
}
```

### Filtration Mode

```python
FILTRATION_MODES = {
    0: "Manual",
    1: "Auto",
    2: "Heating",
    3: "Smart",
    4: "Intelligent",
    13: "Backwash"
}
```

### Filtration Speed

```python
FILTRATION_SPEEDS = {
    1: "Low",
    2: "Medium",
    3: "High"
}
```

### Hydrolysis State

```python
HYDROLYSIS_STATES = {
    "OFF": "Off",
    "FLOW": "Flow Alarm",
    "POL1": "Running (Polarity 1)",
    "POL2": "Running (Polarity 2)"
}
```

### Boost Mode

```python
BOOST_MODES = {
    0: "Off",
    1: "On",
    2: "Redox Controlled"
}
```

______________________________________________________________________

## Example MQTT Commands

### Using mosquitto_pub

```bash
# Turn filtration on at medium speed
mosquitto_pub -t "cmnd/poolcontroller/NPFiltration" -m "1 2"

# Set pH range
mosquitto_pub -t "cmnd/poolcontroller/NPpHMin" -m "7.0"
mosquitto_pub -t "cmnd/poolcontroller/NPpHMax" -m "7.4"

# Set redox target
mosquitto_pub -t "cmnd/poolcontroller/NPRedox" -m "700"

# Enable boost mode
mosquitto_pub -t "cmnd/poolcontroller/NPBoost" -m "1"

# Set filtration to Smart mode
mosquitto_pub -t "cmnd/poolcontroller/NPFiltrationmode" -m "3"

# Turn light on
mosquitto_pub -t "cmnd/poolcontroller/NPLight" -m "1"
```

### Using Python (paho-mqtt)

```python
import paho.mqtt.client as mqtt

client = mqtt.Client()
client.connect("mqtt-broker", 1883, 60)

# Turn filtration on
client.publish("cmnd/poolcontroller/NPFiltration", "1")

# Set pH minimum
client.publish("cmnd/poolcontroller/NPpHMin", "7.0")

# Set hydrolysis level
client.publish("cmnd/poolcontroller/NPHydrolysis", "75")
```

______________________________________________________________________

## Home Assistant MQTT Subscribe Examples

```yaml
# Listen to all sensor data
mqtt:
  sensor:
    - name: "Pool Temperature"
      state_topic: "tele/poolcontroller/SENSOR"
      value_template: "{{ value_json.NeoPool.Temperature }}"
      unit_of_measurement: "°C"
      device_class: "temperature"

    - name: "Pool pH"
      state_topic: "tele/poolcontroller/SENSOR"
      value_template: "{{ value_json.NeoPool.pH.Data }}"
      unit_of_measurement: "pH"

    - name: "Pool Redox"
      state_topic: "tele/poolcontroller/SENSOR"
      value_template: "{{ value_json.NeoPool.Redox.Data }}"
      unit_of_measurement: "mV"

  switch:
    - name: "Pool Filtration"
      state_topic: "tele/poolcontroller/SENSOR"
      value_template:
        "{{ 'ON' if value_json.NeoPool.Filtration.State == 1 else 'OFF' }}"
      command_topic: "cmnd/poolcontroller/NPFiltration"
      payload_on: "1"
      payload_off: "0"

    - name: "Pool Light"
      state_topic: "tele/poolcontroller/SENSOR"
      value_template: "{{ 'ON' if value_json.NeoPool.Light == 1 else 'OFF' }}"
      command_topic: "cmnd/poolcontroller/NPLight"
      payload_on: "1"
      payload_off: "0"

  number:
    - name: "Pool pH Min"
      state_topic: "tele/poolcontroller/SENSOR"
      value_template: "{{ value_json.NeoPool.pH.Min }}"
      command_topic: "cmnd/poolcontroller/NPpHMin"
      min: 0
      max: 14
      step: 0.1
```

______________________________________________________________________

## Common Automation Patterns

### Daily Time Sync

```yaml
automation:
  - alias: "Sync Pool Controller Time"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: mqtt.publish
        data:
          topic: "cmnd/poolcontroller/NPTime"
          payload: "0"
```

### pH Alert

```yaml
automation:
  - alias: "Pool pH Alert"
    trigger:
      - platform: mqtt
        topic: "tele/poolcontroller/SENSOR"
    condition:
      - condition: template
        value_template: "{{ trigger.payload_json.NeoPool.pH.State != 0 }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Pool pH Alert"
          message: "pH state: {{ trigger.payload_json.NeoPool.pH.State }}"
```

### Auto Filtration Based on Temperature

```yaml
automation:
  - alias: "Adjust Filtration for Temperature"
    trigger:
      - platform: mqtt
        topic: "tele/poolcontroller/SENSOR"
    action:
      - service: mqtt.publish
        data:
          topic: "cmnd/poolcontroller/NPFiltrationmode"
          payload: "3"  # Smart mode
```

______________________________________________________________________

## Troubleshooting

### Check Connection Statistics

```bash
# Enable statistics (ESP32 only)
mosquitto_pub -t "cmnd/poolcontroller/NPSetOption1" -m "1"

# Check in telemetry:
# NeoPool.Connection.MBRequests
# NeoPool.Connection.MBNoError
# NeoPool.Connection.MBCRCErr
```

### Test Communication

```bash
# Subscribe to all topics
mosquitto_sub -v -t "tele/poolcontroller/#"
mosquitto_sub -v -t "stat/poolcontroller/#"

# Send a simple command
mosquitto_pub -t "cmnd/poolcontroller/NPControl" -m ""
```

### Enable Data Validation

```bash
# Prevent invalid readings from Modbus errors
mosquitto_pub -t "cmnd/poolcontroller/NPSetOption0" -m "1"
```
