# Tasmota NeoPool MQTT Complete Reference

## Table of Contents

1. [Overview](#overview)
1. [MQTT Topic Structure](#mqtt-topic-structure)
1. [Telemetry JSON Structure](#telemetry-json-structure)
1. [Sensor Readings Reference](#sensor-readings-reference)
1. [Commands Reference](#commands-reference)
1. [Configuration Commands](#configuration-commands)
1. [Low-Level Register Access](#low-level-register-access)
1. [Data Types and Value Ranges](#data-types-and-value-ranges)
1. [Special Modes and Features](#special-modes-and-features)

______________________________________________________________________

## Overview

### What is NeoPool?

Sugar Valley NeoPool is a water treatment system for swimming pools distributed under various brand names:

- **Hidrolife**
- **Aquascenic**
- **Oxilife**
- **Bionet**
- **Hidroniser**
- **UVScenic**
- **Station**
- **Brilix**
- **Generic** (Sugar Valley)

### How Tasmota Integration Works

The NeoPool controller uses an RS485 interface with the Modbus protocol for communication. Tasmota provides:

- A dedicated sensor module for NeoPool devices
- Bi-directional communication via MQTT
- Complete monitoring of all sensors and states
- Full control of pool equipment (pumps, lights, chlorine, pH, etc.)
- Direct Modbus register access for advanced features

### Hardware Requirements

**Connection:**

- RS485 interface (requires TTL-UART to RS485 converter for ESP devices)
- Recommended: M5Stack Atom Lite with Tail485 addon (no separate power supply needed)
- GPIO: GPIO1 (RX) and GPIO3 (TX) recommended
- Voltage: 3.3V only
- Connectors: Use WIFI or EXTERN ports (avoid DISPLAY port if displays are connected)

______________________________________________________________________

## MQTT Topic Structure

### Topic Pattern

```text
%topic% = Device topic configured in Tasmota (default: "tasmota")
```

### Topic Types

#### 1. Telemetry Topic (Sensor Data)

```text
tele/%topic%/SENSOR
```

- **Direction:** Published by device
- **Frequency:** Every TelePeriod seconds (configurable)
- **Content:** Complete sensor readings in JSON format
- **Special:** Can be triggered on value changes with NPTelePeriod command

#### 2. Command Topic

```text
cmnd/%topic%/<command>
```

- **Direction:** Subscribe to receive commands
- **Format:** `cmnd/%topic%/NPFiltration` (example)
- **Payload:** Command-specific value or JSON

#### 3. Status/Result Topic

```text
stat/%topic%/RESULT
```

- **Direction:** Published by device
- **Content:** Response to commands, status updates
- **Format:** JSON with command results

### Example Topics

For a device with topic "poolcontroller":

```text
tele/poolcontroller/SENSOR          # Sensor telemetry
cmnd/poolcontroller/NPFiltration    # Filtration control command
cmnd/poolcontroller/NPLight         # Light control command
cmnd/poolcontroller/NPpHMin         # pH minimum setting
stat/poolcontroller/RESULT          # Command responses
```

______________________________________________________________________

## Telemetry JSON Structure

### Complete Sensor Payload

Published to: `tele/%topic%/SENSOR`

```json
{
  "Time": "2025-01-15T14:30:00",
  "NeoPool": {
    "Time": "2025-01-15T14:30:00",
    "Type": "HIDROLIFE model",
    "Module": {
      "pH": 0,
      "Redox": 1,
      "Hydrolysis": 1,
      "Chlorine": 0,
      "Conductivity": 0,
      "Ionization": 0
    },
    "Temperature": 23.5,
    "Powerunit": {
      "Version": "V1.2.3",
      "NodeID": "hidden_by_default",
      "5V": 5.1,
      "12V": 12.3,
      "24-30V": 24.8,
      "4-20mA": 15.2
    },
    "pH": {
      "Data": 7.2,
      "Min": 7.0,
      "Max": 7.4,
      "State": 0,
      "Pump": 0,
      "FL1": 0,
      "Tank": 1
    },
    "Redox": {
      "Data": 750,
      "Setpoint": 700
    },
    "Chlorine": {
      "Data": 1.5,
      "Setpoint": 1.0
    },
    "Conductivity": 85,
    "Ionization": {
      "Data": 5,
      "Setpoint": 3,
      "Max": 10
    },
    "Hydrolysis": {
      "Data": 75.0,
      "Unit": "%",
      "Setpoint": 80.0,
      "Max": 100.0,
      "Runtime": {
        "Total": "120T15:30:45",
        "Part": "5T03:22:10",
        "Pol1": "60T07:45:22",
        "Pol2": "60T07:45:23",
        "Changes": 1205
      },
      "State": "POL1",
      "Cover": 0,
      "Boost": 0,
      "Low": 0,
      "FL1": 0,
      "Redox": 1
    },
    "Filtration": {
      "State": 1,
      "Speed": 2,
      "Mode": 1
    },
    "Light": 0,
    "Relay": {
      "State": [0, 1, 0, 0, 0, 0, 1],
      "Aux": [1, 0, 0, 1],
      "Acid": 0,
      "Base": 0,
      "Redox": 1,
      "Chlorine": 0,
      "Conductivity": 0,
      "Heating": 1,
      "UV": 0,
      "Valve": 0
    },
    "Connection": {
      "Time": "2025-01-15T14:30:00",
      "MBRequests": 15234,
      "MBNoError": 15230,
      "MBIllegalFunc": 0,
      "MBNoResponse": 4,
      "DataOutOfRange": 0,
      "MBCRCErr": 0
    }
  }
}
```

### Module Object

Indicates which hardware modules are installed:

```json
"Module": {
  "pH": 0,              // 0 = not installed, 1 = installed
  "Redox": 1,
  "Hydrolysis": 1,
  "Chlorine": 0,
  "Conductivity": 0,
  "Ionization": 0
}
```

### Powerunit Object

System voltage and version information:

```json
"Powerunit": {
  "Version": "V1.2.3",    // Firmware version string
  "NodeID": "ABC123",     // Hardware NodeID (SetOption157 1 required)
  "5V": 5.1,              // 5V rail voltage (float)
  "12V": 12.3,            // 12V rail voltage (float)
  "24-30V": 24.8,         // 24-30V rail voltage (float)
  "4-20mA": 15.2          // 4-20mA current reading (float)
}
```

### pH Object

```json
"pH": {
  "Data": 7.2,       // Current pH reading (0.0-14.0)
  "Min": 7.0,        // User-defined minimum pH
  "Max": 7.4,        // User-defined maximum pH
  "State": 0,        // pH alarm state (0-6, see below)
  "Pump": 0,         // Pump state: 0=inactive, 1=on, 2=off
  "FL1": 0,          // Flow sensor 1 (0=no flow, 1=flow)
  "Tank": 1          // Tank level (0=empty, 1=ok)
}
```

**pH.State Values:**

- `0` = No alarm
- `1` = pH too high (exceeds +0.8 from setpoint)
- `2` = pH too low (exceeds -0.8 from setpoint)
- `3` = Pump timeout exceeded
- `4` = pH higher than setpoint (+0.1)
- `5` = pH lower than setpoint (-0.3)
- `6` = Tank level alarm

### Redox Object

```json
"Redox": {
  "Data": 750,        // Current redox reading in mV (0-1000)
  "Setpoint": 700     // Target redox setpoint in mV (0-1000)
}
```

### Chlorine Object

```json
"Chlorine": {
  "Data": 1.5,        // Current chlorine reading in ppm (0.0-10.0)
  "Setpoint": 1.0     // Target chlorine setpoint in ppm (0.0-10.0)
}
```

### Ionization Object

```json
"Ionization": {
  "Data": 5,          // Current ionization level (0-max)
  "Setpoint": 3,      // Target ionization setpoint (0-max)
  "Max": 10           // Maximum ionization level (device-specific)
}
```

### Hydrolysis Object

```json
"Hydrolysis": {
  "Data": 75.0,       // Current production level (% or g/h)
  "Unit": "%",        // Unit: "%" or "g/h"
  "Setpoint": 80.0,   // Target production level
  "Max": 100.0,       // Maximum production level
  "Runtime": {
    "Total": "120T15:30:45",     // Total runtime (days T hours:minutes:seconds)
    "Part": "5T03:22:10",        // Partial runtime
    "Pol1": "60T07:45:22",       // Polarity 1 runtime
    "Pol2": "60T07:45:23",       // Polarity 2 runtime
    "Changes": 1205              // Number of polarity changes
  },
  "State": "POL1",    // OFF, FLOW, POL1, POL2
  "Cover": 0,         // Pool cover sensor (0=open, 1=covered)
  "Boost": 0,         // Boost mode (0=off, 1=on, 2=redox-controlled)
  "Low": 0,           // Low production mode (0=normal, 1=low)
  "FL1": 0,           // Flow sensor 1 (0=no flow, 1=flow)
  "Redox": 1          // Redox control enabled (0=disabled, 1=enabled)
}
```

**Hydrolysis.State Values:**

- `OFF` = Hydrolysis off
- `FLOW` = Water flow alarm (no flow detected)
- `POL1` = Polarity 1 active
- `POL2` = Polarity 2 active (reversed polarity for electrode cleaning)

### Filtration Object

```json
"Filtration": {
  "State": 1,    // 0=off, 1=on
  "Speed": 2,    // 1=low, 2=mid, 3=high
  "Mode": 1      // 0-4 or 13 (see filtration modes below)
}
```

**Filtration.Mode Values:**

- `0` = Manual
- `1` = Auto (timer-based)
- `2` = Heating
- `3` = Smart
- `4` = Intelligent
- `13` = Backwash

### Relay Object

```json
"Relay": {
  "State": [0, 1, 0, 0, 0, 0, 1],  // Array of 7 relay states (0=off, 1=on)
  "Aux": [1, 0, 0, 1],              // Array of 4 auxiliary relay states
  "Acid": 0,                         // Acid dosing relay
  "Base": 0,                         // Base dosing relay
  "Redox": 1,                        // Redox control relay
  "Chlorine": 0,                     // Chlorine dosing relay
  "Conductivity": 0,                 // Conductivity control relay
  "Heating": 1,                      // Heating relay
  "UV": 0,                           // UV lamp relay
  "Valve": 0                         // Valve control relay
}
```

### Connection Object (ESP32 Only)

Requires `NPSetOption1 1` to enable:

```json
"Connection": {
  "Time": "2025-01-15T14:30:00",  // Last successful communication
  "MBRequests": 15234,             // Total Modbus requests
  "MBNoError": 15230,              // Successful requests
  "MBIllegalFunc": 0,              // Illegal function errors
  "MBNoResponse": 4,               // Timeout errors (no response)
  "DataOutOfRange": 0,             // Data validation errors
  "MBCRCErr": 0                    // CRC checksum errors
}
```

______________________________________________________________________

## Sensor Readings Reference

### Temperature

- **JSON Path:** `NeoPool.Temperature`
- **Type:** Float
- **Unit:** °C (Celsius)
- **Range:** Typically 0-40°C
- **Example:** `23.5`

### pH Readings

- **Current pH:** `NeoPool.pH.Data`
  - Type: Float
  - Range: 0.0-14.0 (typical pool range: 6.8-8.0)
  - Precision: Configurable (NPPHRes 0-3 decimal places)
- **pH Min:** `NeoPool.pH.Min`
  - Type: Float
  - Range: 0.0-14.0
- **pH Max:** `NeoPool.pH.Max`
  - Type: Float
  - Range: 0.0-14.0
- **pH State:** `NeoPool.pH.State`
  - Type: Integer
  - Range: 0-6 (alarm codes)
- **pH Pump:** `NeoPool.pH.Pump`
  - Type: Integer
  - Values: 0=inactive, 1=dosing, 2=stopped
- **pH Flow:** `NeoPool.pH.FL1`
  - Type: Binary (0/1)
- **pH Tank:** `NeoPool.pH.Tank`
  - Type: Binary (0/1, 0=empty warning)

### Redox (ORP) Readings

- **Current Redox:** `NeoPool.Redox.Data`
  - Type: Integer
  - Unit: mV (millivolts)
  - Range: 0-1000 mV
  - Typical pool range: 650-750 mV
- **Redox Setpoint:** `NeoPool.Redox.Setpoint`
  - Type: Integer
  - Unit: mV
  - Range: 0-1000 mV

### Chlorine Readings

- **Current Chlorine:** `NeoPool.Chlorine.Data`
  - Type: Float
  - Unit: ppm (parts per million)
  - Range: 0.0-10.0 ppm
  - Precision: Configurable (NPCLRes 0-3 decimal places)
  - Typical pool range: 0.5-3.0 ppm
- **Chlorine Setpoint:** `NeoPool.Chlorine.Setpoint`
  - Type: Float
  - Unit: ppm
  - Range: 0.0-10.0 ppm

### Conductivity

- **Reading:** `NeoPool.Conductivity`
- **Type:** Integer
- **Unit:** Percentage (%)
- **Range:** 0-100%

### Ionization Readings

- **Current Level:** `NeoPool.Ionization.Data`
  - Type: Integer
  - Range: 0-max (device-specific)
  - Precision: Configurable (NPIONRes 0-3 decimal places)
- **Ionization Setpoint:** `NeoPool.Ionization.Setpoint`
  - Type: Integer
  - Range: 0-max
- **Ionization Max:** `NeoPool.Ionization.Max`
  - Type: Integer
  - Device-specific maximum value

### Hydrolysis (Chlorine Production)

- **Production Level:** `NeoPool.Hydrolysis.Data`
  - Type: Float or Integer
  - Unit: % or g/h (depends on unit setting)
  - Range: 0-100 (%) or 0-max (g/h)
- **Production Setpoint:** `NeoPool.Hydrolysis.Setpoint`
  - Type: Float or Integer
  - Range: 0-100 (%) or 0-max (g/h)
- **Production State:** `NeoPool.Hydrolysis.State`
  - Type: String
  - Values: "OFF", "FLOW", "POL1", "POL2"
- **Runtime Total:** `NeoPool.Hydrolysis.Runtime.Total`
  - Type: String
  - Format: "DDDThh:mm:ss" (days T hours:minutes:seconds)
- **Runtime Pol1:** `NeoPool.Hydrolysis.Runtime.Pol1`
- **Runtime Pol2:** `NeoPool.Hydrolysis.Runtime.Pol2`
- **Polarity Changes:** `NeoPool.Hydrolysis.Runtime.Changes`
  - Type: Integer
- **Boost Mode:** `NeoPool.Hydrolysis.Boost`
  - Type: Integer
  - Values: 0=off, 1=on, 2=redox-controlled
- **Cover Status:** `NeoPool.Hydrolysis.Cover`
  - Type: Binary (0=open, 1=covered)

### Filtration

- **Pump State:** `NeoPool.Filtration.State`
  - Type: Binary (0=off, 1=on)
- **Pump Speed:** `NeoPool.Filtration.Speed`
  - Type: Integer
  - Values: 1=low, 2=mid, 3=high
- **Filtration Mode:** `NeoPool.Filtration.Mode`
  - Type: Integer
  - Values: 0=Manual, 1=Auto, 2=Heating, 3=Smart, 4=Intelligent, 13=Backwash

### Light

- **State:** `NeoPool.Light`
- **Type:** Binary (0=off, 1=on)

### Power Supply Voltages

- **5V Rail:** `NeoPool.Powerunit.5V` (Float, typical: 4.9-5.2V)
- **12V Rail:** `NeoPool.Powerunit.12V` (Float, typical: 11.8-12.5V)
- **24-30V Rail:** `NeoPool.Powerunit.24-30V` (Float, typical: 24-30V)
- **4-20mA Current:** `NeoPool.Powerunit.4-20mA` (Float, typical: 4-20mA)

______________________________________________________________________

## Commands Reference

### MQTT Command Structure

Commands are sent to: `cmnd/%topic%/<command>`

**Example:**

```text
Topic: cmnd/poolcontroller/NPFiltration
Payload: 1
```

The device responds on: `stat/%topic%/RESULT`

______________________________________________________________________

### Core Control Commands

#### NPFiltration

**Control filtration pump on/off and speed**

**Topic:** `cmnd/%topic%/NPFiltration`

**Payload:**

- `0` = Turn pump off
- `1` = Turn pump on
- `1 1` = Turn pump on, speed 1 (low)
- `1 2` = Turn pump on, speed 2 (medium)
- `1 3` = Turn pump on, speed 3 (high)

**Format:** `<state>` or `<state> <speed>`

**Examples:**

```text
NPFiltration 0        # Turn off
NPFiltration 1        # Turn on (last speed)
NPFiltration 1 2      # Turn on at medium speed
```

______________________________________________________________________

#### NPFiltrationmode

**Set filtration operating mode**

**Topic:** `cmnd/%topic%/NPFiltrationmode`

**Payload:**

- `0` = Manual mode
- `1` = Auto mode (timer-based)
- `2` = Heating mode
- `3` = Smart mode
- `4` = Intelligent mode
- `13` = Backwash mode

**Mode Descriptions:**

- **Manual (0):** Direct on/off control via NPFiltration command
- **Auto (1):** Timer-based scheduling (requires timer configuration)
- **Heating (2):** Temperature-dependent with heating integration
- **Smart (3):** Dynamic timing based on water temperature
- **Intelligent (4):** Advanced heating + filtration optimization
- **Backwash (13):** Specialized filter maintenance mode

**Examples:**

```text
NPFiltrationmode 1    # Set to Auto mode
NPFiltrationmode 3    # Set to Smart mode
```

______________________________________________________________________

#### NPFiltrationspeed

**Set filtration pump speed**

**Topic:** `cmnd/%topic%/NPFiltrationspeed`

**Payload:**

- `1` = Low speed
- `2` = Medium speed
- `3` = High speed

**Examples:**

```text
NPFiltrationspeed 2   # Set to medium speed
```

______________________________________________________________________

#### NPBoost

**Control hydrolysis boost mode**

**Topic:** `cmnd/%topic%/NPBoost`

**Payload:**

- `0` or `OFF` = Boost off
- `1` or `ON` = Boost on (independent of redox)
- `2` or `REDOX` = Boost on (respects redox settings)

**Examples:**

```text
NPBoost 0             # Disable boost
NPBoost ON            # Enable boost (ignore redox)
NPBoost REDOX         # Enable boost (respect redox limits)
```

______________________________________________________________________

#### NPLight

**Control pool light**

**Topic:** `cmnd/%topic%/NPLight`

**Payload:**

- `0` = Off
- `1` = On
- `2` = Toggle
- `3` = Auto mode
- `4` = RGB color selection
- `<state> <delay>` = Optional delay parameter

**Examples:**

```text
NPLight 0             # Turn off
NPLight 1             # Turn on
NPLight 2             # Toggle current state
NPLight 1 300         # Turn on with 300s delay
```

______________________________________________________________________

#### NPTime

**Synchronize device time**

**Topic:** `cmnd/%topic%/NPTime`

**Payload:**

- `0` = Sync with Tasmota local time
- `1` = Sync with Tasmota UTC time
- `<epoch>` = Set specific Unix timestamp

**Examples:**

```text
NPTime 0              # Sync to local time
NPTime 1              # Sync to UTC
NPTime 1673784000     # Set specific timestamp
```

______________________________________________________________________

#### NPpHMin

**Set pH minimum threshold**

**Topic:** `cmnd/%topic%/NPpHMin`

**Payload:** Float value (0.0-14.0)

**Examples:**

```text
NPpHMin 7.0           # Set minimum pH to 7.0
NPpHMin 6.8           # Set minimum pH to 6.8
```

______________________________________________________________________

#### NPpHMax

**Set pH maximum threshold**

**Topic:** `cmnd/%topic%/NPpHMax`

**Payload:** Float value (0.0-14.0)

**Examples:**

```text
NPpHMax 7.4           # Set maximum pH to 7.4
NPpHMax 7.6           # Set maximum pH to 7.6
```

______________________________________________________________________

#### NPRedox

**Set redox (ORP) setpoint**

**Topic:** `cmnd/%topic%/NPRedox`

**Payload:** Integer value (0-1000 mV)

**Examples:**

```text
NPRedox 700           # Set redox target to 700 mV
NPRedox 750           # Set redox target to 750 mV
```

______________________________________________________________________

#### NPHydrolysis

**Set hydrolysis production level**

**Topic:** `cmnd/%topic%/NPHydrolysis`

**Payload:**

- `0-100` = Percentage (when unit is %)
- `0-max` = g/h (when unit is g/h, device-specific max)

**Examples:**

```text
NPHydrolysis 75       # Set to 75% or 75 g/h
NPHydrolysis 100      # Set to maximum
NPHydrolysis 0        # Disable production
```

______________________________________________________________________

#### NPChlorine

**Set free chlorine setpoint**

**Topic:** `cmnd/%topic%/NPChlorine`

**Payload:** Float value (0.0-10.0 ppm)

**Examples:**

```text
NPChlorine 1.5        # Set chlorine target to 1.5 ppm
NPChlorine 2.0        # Set chlorine target to 2.0 ppm
```

______________________________________________________________________

#### NPIonization

**Set ionization level**

**Topic:** `cmnd/%topic%/NPIonization`

**Payload:** Integer value (0-max, device-specific)

**Examples:**

```text
NPIonization 5        # Set ionization to level 5
NPIonization 0        # Disable ionization
```

______________________________________________________________________

#### NPControl

**Display module and relay configuration**

**Topic:** `cmnd/%topic%/NPControl`

**Payload:** None (no parameters)

**Response:** Shows which modules are installed and relay assignments

**Examples:**

```text
NPControl             # Display current configuration
```

______________________________________________________________________

## Configuration Commands

### NPTelePeriod

**Configure telemetry reporting**

**Topic:** `cmnd/%topic%/NPTelePeriod`

**Payload:**

- `0` = Automatic telemetry on value changes only
- `5-3600` = Report every N seconds (overrides Tasmota TelePeriod)

**Examples:**

```text
NPTelePeriod 0        # Report only on changes
NPTelePeriod 60       # Report every 60 seconds
NPTelePeriod 300      # Report every 5 minutes
```

______________________________________________________________________

### NPOnError

**Set Modbus error retry attempts**

**Topic:** `cmnd/%topic%/NPOnError`

**Payload:** Integer (0-10 retry attempts)

**Examples:**

```text
NPOnError 3           # Retry 3 times on error
NPOnError 0           # No retries
```

______________________________________________________________________

### NPResult

**Set numeric output format**

**Topic:** `cmnd/%topic%/NPResult`

**Payload:**

- `0` = Decimal format
- `1` = Hexadecimal format

**Examples:**

```text
NPResult 0            # Use decimal format
NPResult 1            # Use hexadecimal format
```

______________________________________________________________________

### NPPHRes

**Set pH decimal precision**

**Topic:** `cmnd/%topic%/NPPHRes`

**Payload:** Integer (0-3 decimal places)

**Examples:**

```text
NPPHRes 1             # pH with 1 decimal place (7.2)
NPPHRes 2             # pH with 2 decimal places (7.25)
```

______________________________________________________________________

### NPCLRes

**Set chlorine decimal precision**

**Topic:** `cmnd/%topic%/NPCLRes`

**Payload:** Integer (0-3 decimal places)

**Examples:**

```text
NPCLRes 1             # Chlorine with 1 decimal place (1.5)
NPCLRes 2             # Chlorine with 2 decimal places (1.52)
```

______________________________________________________________________

### NPIONRes

**Set ionization decimal precision**

**Topic:** `cmnd/%topic%/NPIONRes`

**Payload:** Integer (0-3 decimal places)

**Examples:**

```text
NPIONRes 0            # Ionization as integer
NPIONRes 1            # Ionization with 1 decimal place
```

______________________________________________________________________

### NPSetOption0

**Enable data validation and correction**

**Topic:** `cmnd/%topic%/NPSetOption0`

**Payload:**

- `0` = Disable automatic correction
- `1` = Enable automatic correction of out-of-range values

**Examples:**

```text
NPSetOption0 1        # Enable validation
NPSetOption0 0        # Disable validation
```

______________________________________________________________________

### NPSetOption1

**Enable connection statistics (ESP32 only)**

**Topic:** `cmnd/%topic%/NPSetOption1`

**Payload:**

- `0` = Disable statistics
- `1` = Enable Modbus connection statistics in telemetry

**Examples:**

```text
NPSetOption1 1        # Enable statistics
NPSetOption1 0        # Disable statistics
```

______________________________________________________________________

## Low-Level Register Access

These commands provide direct Modbus register access for advanced users.

### Address Ranges

- **0x0000-0x03FF:** Read-only status registers
- **0x0400-0x04EE:** Installer parameters
- **0x0500-0x05FF:** User settings
- **0x0600-0x06FF:** Miscellaneous registers

______________________________________________________________________

### NPRead

**Read 16-bit register(s)**

**Topic:** `cmnd/%topic%/NPRead`

**Payload:** `<address>` or `<address> <count>`

**Examples:**

```text
NPRead 0x0500         # Read single register at 0x0500
NPRead 0x0500 5       # Read 5 consecutive registers starting at 0x0500
```

______________________________________________________________________

### NPReadL

**Read 32-bit register(s)**

**Topic:** `cmnd/%topic%/NPReadL`

**Payload:** `<address>` or `<address> <count>`

**Examples:**

```text
NPReadL 0x0500        # Read 32-bit value at 0x0500
NPReadL 0x0500 3      # Read 3 consecutive 32-bit values
```

______________________________________________________________________

### NPReadLSB

**Read register LSB (Least Significant Byte) only**

**Topic:** `cmnd/%topic%/NPReadLSB`

**Payload:** `<address>` or `<address> <count>`

**Examples:**

```text
NPReadLSB 0x0500      # Read LSB of register at 0x0500
```

______________________________________________________________________

### NPReadMSB

**Read register MSB (Most Significant Byte) only**

**Topic:** `cmnd/%topic%/NPReadMSB`

**Payload:** `<address>` or `<address> <count>`

**Examples:**

```text
NPReadMSB 0x0500      # Read MSB of register at 0x0500
```

______________________________________________________________________

### NPWrite

**Write 16-bit value(s) to register(s)**

**Topic:** `cmnd/%topic%/NPWrite`

**Payload:** `<address> <data>` or `<address> <data1> <data2> ...`

**Examples:**

```text
NPWrite 0x0500 1234   # Write 1234 to register 0x0500
NPWrite 0x0500 100 200 300  # Write multiple values
```

______________________________________________________________________

### NPWriteL

**Write 32-bit value(s) to register(s)**

**Topic:** `cmnd/%topic%/NPWriteL`

**Payload:** `<address> <data>` or `<address> <data1> <data2> ...`

**Examples:**

```text
NPWriteL 0x0500 123456  # Write 32-bit value to 0x0500
```

______________________________________________________________________

### NPWriteLSB

**Write LSB byte only**

**Topic:** `cmnd/%topic%/NPWriteLSB`

**Payload:** `<address> <data>` or `<address> <data1> <data2> ...`

**Examples:**

```text
NPWriteLSB 0x0500 0xFF  # Write 0xFF to LSB of register
```

______________________________________________________________________

### NPWriteMSB

**Write MSB byte only**

**Topic:** `cmnd/%topic%/NPWriteMSB`

**Payload:** `<address> <data>` or `<address> <data1> <data2> ...`

**Examples:**

```text
NPWriteMSB 0x0500 0xFF  # Write 0xFF to MSB of register
```

______________________________________________________________________

### NPBit

**Read/Write single bit in 16-bit register**

**Topic:** `cmnd/%topic%/NPBit`

**Payload:**

- `<address> <bit>` = Read bit
- `<address> <bit> <data>` = Write bit (data: 0 or 1)

**Examples:**

```text
NPBit 0x0500 5        # Read bit 5 of register 0x0500
NPBit 0x0500 5 1      # Set bit 5 to 1
NPBit 0x0500 5 0      # Clear bit 5
```

______________________________________________________________________

### NPBitL

**Read/Write single bit in 32-bit register**

**Topic:** `cmnd/%topic%/NPBitL`

**Payload:**

- `<address> <bit>` = Read bit
- `<address> <bit> <data>` = Write bit (data: 0 or 1)

**Examples:**

```text
NPBitL 0x0500 20      # Read bit 20 of 32-bit register
NPBitL 0x0500 20 1    # Set bit 20 to 1
```

______________________________________________________________________

### NPEscape

**Clear error states**

**Topic:** `cmnd/%topic%/NPEscape`

**Payload:** None

**Examples:**

```text
NPEscape              # Clear all error states
```

______________________________________________________________________

### NPExec

**Apply register changes without EEPROM save**

**Topic:** `cmnd/%topic%/NPExec`

**Payload:** None

**Description:** Applies pending register changes to active configuration without persisting to
EEPROM. Changes will be lost on device reboot.

**Examples:**

```text
NPExec                # Apply changes (temporary)
```

______________________________________________________________________

### NPSave

**Save changes to EEPROM**

**Topic:** `cmnd/%topic%/NPSave`

**Payload:** None

**Description:** Persists current configuration to device EEPROM. Changes survive device reboot.

**Examples:**

```text
NPSave                # Save configuration permanently
```

______________________________________________________________________

## Data Types and Value Ranges

### Complete Type Reference

| Data Field          | JSON Path                     | Type      | Range          | Unit     | Precision          |
| ------------------- | ----------------------------- | --------- | -------------- | -------- | ------------------ |
| Temperature         | `NeoPool.Temperature`         | Float     | 0-40           | °C       | 0.1°C              |
| pH Current          | `NeoPool.pH.Data`             | Float     | 0-14           | pH       | Configurable (0-3) |
| pH Min              | `NeoPool.pH.Min`              | Float     | 0-14           | pH       | Configurable (0-3) |
| pH Max              | `NeoPool.pH.Max`              | Float     | 0-14           | pH       | Configurable (0-3) |
| pH State            | `NeoPool.pH.State`            | Integer   | 0-6            | enum     | N/A                |
| pH Pump             | `NeoPool.pH.Pump`             | Integer   | 0-2            | enum     | N/A                |
| pH Flow             | `NeoPool.pH.FL1`              | Binary    | 0-1            | boolean  | N/A                |
| pH Tank             | `NeoPool.pH.Tank`             | Binary    | 0-1            | boolean  | N/A                |
| Redox Current       | `NeoPool.Redox.Data`          | Integer   | 0-1000         | mV       | 1 mV               |
| Redox Setpoint      | `NeoPool.Redox.Setpoint`      | Integer   | 0-1000         | mV       | 1 mV               |
| Chlorine Current    | `NeoPool.Chlorine.Data`       | Float     | 0-10           | ppm      | Configurable (0-3) |
| Chlorine Setpoint   | `NeoPool.Chlorine.Setpoint`   | Float     | 0-10           | ppm      | Configurable (0-3) |
| Conductivity        | `NeoPool.Conductivity`        | Integer   | 0-100          | %        | 1%                 |
| Ionization Current  | `NeoPool.Ionization.Data`     | Integer   | 0-max          | level    | Configurable (0-3) |
| Ionization Setpoint | `NeoPool.Ionization.Setpoint` | Integer   | 0-max          | level    | Configurable (0-3) |
| Ionization Max      | `NeoPool.Ionization.Max`      | Integer   | device         | level    | N/A                |
| Hydrolysis Current  | `NeoPool.Hydrolysis.Data`     | Float/Int | 0-100 or 0-max | % or g/h | 0.1 or 1           |
| Hydrolysis Setpoint | `NeoPool.Hydrolysis.Setpoint` | Float/Int | 0-100 or 0-max | % or g/h | 0.1 or 1           |
| Hydrolysis State    | `NeoPool.Hydrolysis.State`    | String    | enum           | N/A      | N/A                |
| Hydrolysis Boost    | `NeoPool.Hydrolysis.Boost`    | Integer   | 0-2            | enum     | N/A                |
| Hydrolysis Cover    | `NeoPool.Hydrolysis.Cover`    | Binary    | 0-1            | boolean  | N/A                |
| Filtration State    | `NeoPool.Filtration.State`    | Binary    | 0-1            | boolean  | N/A                |
| Filtration Speed    | `NeoPool.Filtration.Speed`    | Integer   | 1-3            | enum     | N/A                |
| Filtration Mode     | `NeoPool.Filtration.Mode`     | Integer   | 0-4, 13        | enum     | N/A                |
| Light               | `NeoPool.Light`               | Binary    | 0-1            | boolean  | N/A                |
| Relay State         | `NeoPool.Relay.State[n]`      | Binary    | 0-1            | boolean  | N/A                |
| Voltage 5V          | `NeoPool.Powerunit.5V`        | Float     | 4.5-5.5        | V        | 0.1V               |
| Voltage 12V         | `NeoPool.Powerunit.12V`       | Float     | 11-13          | V        | 0.1V               |
| Voltage 24-30V      | `NeoPool.Powerunit.24-30V`    | Float     | 24-30          | V        | 0.1V               |
| Current 4-20mA      | `NeoPool.Powerunit.4-20mA`    | Float     | 4-20           | mA       | 0.1mA              |

### Enumeration Details

**pH.State (Integer 0-6):**

```text
0 = OK (no alarm)
1 = pH high alarm (>setpoint + 0.8)
2 = pH low alarm (<setpoint - 0.8)
3 = Pump timeout
4 = pH slightly high (>setpoint + 0.1)
5 = pH slightly low (<setpoint - 0.3)
6 = Tank empty alarm
```

**pH.Pump (Integer 0-2):**

```text
0 = Inactive
1 = Dosing (pump on)
2 = Stopped (pump off)
```

**Hydrolysis.State (String):**

```text
"OFF"   = Hydrolysis disabled
"FLOW"  = Flow alarm (no water flow detected)
"POL1"  = Polarity 1 active (normal operation)
"POL2"  = Polarity 2 active (reverse polarity for cleaning)
```

**Hydrolysis.Boost (Integer 0-2):**

```text
0 = Boost off
1 = Boost on (independent mode)
2 = Boost on (redox-controlled mode)
```

**Filtration.Speed (Integer 1-3):**

```text
1 = Low speed
2 = Medium speed
3 = High speed
```

**Filtration.Mode (Integer):**

```text
0  = Manual
1  = Auto (timer-based)
2  = Heating
3  = Smart (temperature-dependent)
4  = Intelligent (advanced)
13 = Backwash
```

______________________________________________________________________

## Special Modes and Features

### Filtration Modes Explained

#### Manual Mode (0)

- Direct control via NPFiltration command
- No automatic scheduling
- User must manually turn pump on/off
- Suitable for manual pool maintenance

#### Auto Mode (1)

- Timer-based scheduling
- Requires configuration of timer blocks via Modbus registers
- Pump runs according to programmed schedule
- Register: MBF_PAR_TIMER_BLOCK_FILT_INT

#### Heating Mode (2)

- Temperature-dependent operation
- Integrates with pool heating system
- Adjusts filtration based on heating requirements
- Ensures proper circulation during heating cycles

#### Smart Mode (3)

- Dynamic scheduling based on water temperature
- Automatically adjusts filtration duration
- Higher temperatures = longer filtration times
- Energy-efficient operation

#### Intelligent Mode (4)

- Advanced optimization combining heating and filtration
- Learns pool behavior patterns
- Optimizes energy consumption
- Best for automated pool management

#### Backwash Mode (13)

- Specialized filter cleaning mode
- Reverses flow direction
- Used for filter maintenance
- Typically manual activation

______________________________________________________________________

### Hydrolysis Features

#### Polarity Switching

- Automatic electrode polarity reversal
- Prevents calcium buildup on electrodes
- Runtime tracked separately for POL1 and POL2
- Polarity changes counted in `Runtime.Changes`

#### Boost Mode

Three boost operating modes:

1. **Off (0):** Normal production following setpoint
1. **On (1):** Maximum production independent of redox readings
1. **Redox (2):** Boost production while respecting redox limits

#### Cover Detection

- Pool cover sensor input: `Hydrolysis.Cover`
- Reduces chlorine production when covered
- Saves chemical and energy costs
- Prevents over-chlorination

#### Flow Detection

- `Hydrolysis.FL1` monitors water flow
- State changes to "FLOW" when no flow detected
- Safety feature to prevent dry running
- Protects electrode cell

______________________________________________________________________

### pH Control Features

#### Dual Threshold System

- **Min threshold:** Lower acceptable pH limit
- **Max threshold:** Upper acceptable pH limit
- Alarm states triggered when outside range
- Automatic dosing between thresholds

#### Multi-Level Alarms

Six distinct alarm states provide graduated warnings:

1. **State 0:** Normal operation
1. **State 1:** Critical high (>0.8 above setpoint)
1. **State 2:** Critical low (\<0.8 below setpoint)
1. **State 3:** Pump timeout (dosing failure)
1. **State 4:** Warning high (>0.1 above setpoint)
1. **State 5:** Warning low (\<0.3 below setpoint)
1. **State 6:** Tank empty (chemical reservoir)

#### Tank Level Monitoring

- `pH.Tank` binary sensor
- Prevents dry running of dosing pump
- Alerts when chemical reservoir needs refilling

______________________________________________________________________

### Relay System

#### Relay Types

**General Relays (1-7):**

- Configurable for various functions
- Array index 0-6 in `Relay.State`
- Binary on/off control

**Auxiliary Relays (Aux1-4):**

- Additional control outputs
- Array index 0-3 in `Relay.Aux`
- ESP32 Berry scripting support for extended control

**Functional Assignments:**
Named relays with specific purposes:

- `Relay.Acid` - Acid dosing pump
- `Relay.Base` - Base dosing pump
- `Relay.Redox` - Redox control output
- `Relay.Chlorine` - Chlorine dosing
- `Relay.Conductivity` - Conductivity control
- `Relay.Heating` - Pool heater
- `Relay.UV` - UV sterilization lamp
- `Relay.Valve` - Valve control (multi-port, etc.)

#### Berry Script Extensions (ESP32 Only)

Advanced auxiliary relay control via Berry scripting:

- `NPAux1` - Control auxiliary relay 1
- `NPAux2` - Control auxiliary relay 2
- `NPAux3` - Control auxiliary relay 3
- `NPAux4` - Control auxiliary relay 4

Additional Berry features:

- Timer management (12 device timers)
- Configuration backup/restore
- Smart mode antifreeze control
- Firmware version queries

______________________________________________________________________

### Time Synchronization

#### NPTime Command

Prevents device clock drift by synchronizing with Tasmota:

**Options:**

- `NPTime 0` - Sync to Tasmota local time
- `NPTime 1` - Sync to Tasmota UTC time
- `NPTime <epoch>` - Set specific Unix timestamp

**Recommendation:** Set up periodic time sync (e.g., daily) via automation

______________________________________________________________________

### Telemetry Optimization

#### NPTelePeriod Feature

Two telemetry modes:

**Change-Based (`NPTelePeriod 0`):**

- Publishes only when sensor values change
- Reduces MQTT traffic
- Ideal for battery-powered ESP devices
- Recommended for most installations

**Time-Based (`NPTelePeriod 5-3600`):**

- Publishes at fixed intervals
- Overrides Tasmota's global TelePeriod
- Useful for logging/graphing requirements
- Higher network traffic

______________________________________________________________________

### Data Validation (NPSetOption0)

When enabled (`NPSetOption0 1`):

- Validates all sensor readings against min/max ranges
- Automatically corrects impossible values
- Filters out Modbus communication errors
- Improves data reliability

When disabled (`NPSetOption0 0`):

- Raw data passed through
- Useful for debugging
- May show invalid readings during communication errors

______________________________________________________________________

### Connection Diagnostics (NPSetOption1)

ESP32-only feature providing Modbus statistics:

**Metrics Tracked:**

- `MBRequests` - Total requests sent
- `MBNoError` - Successful responses
- `MBIllegalFunc` - Illegal function code errors
- `MBNoResponse` - Timeout errors
- `DataOutOfRange` - Data address errors
- `MBCRCErr` - Checksum errors

**Use Cases:**

- Troubleshooting communication issues
- Monitoring RS485 bus health
- Detecting wiring problems
- Performance optimization

______________________________________________________________________

### Decimal Precision Control

Configure display precision for chemical readings:

**NPPHRes (pH precision):**

```text
NPPHRes 0  →  7
NPPHRes 1  →  7.2
NPPHRes 2  →  7.24
NPPHRes 3  →  7.245
```

**NPCLRes (Chlorine precision):**

```text
NPCLRes 0  →  1
NPCLRes 1  →  1.5
NPCLRes 2  →  1.52
NPCLRes 3  →  1.523
```

**NPIONRes (Ionization precision):**

```text
NPIONRes 0  →  5
NPIONRes 1  →  5.0
NPIONRes 2  →  5.00
NPIONRes 3  →  5.000
```

**Impact:** Only affects display/telemetry, not internal calculations

______________________________________________________________________

### Module Detection

The `Module` object shows installed hardware:

```json
"Module": {
  "pH": 0,              // 0 = not installed, 1 = installed
  "Redox": 1,
  "Hydrolysis": 1,
  "Chlorine": 0,
  "Conductivity": 0,
  "Ionization": 0
}
```

**Benefits:**

- Auto-detect available sensors
- Skip unsupported features in Home Assistant
- Dynamic entity creation
- Hardware inventory tracking

**Only installed modules appear in telemetry data.**

______________________________________________________________________

### Runtime Tracking

Hydrolysis runtime provides maintenance insights:

**Total Runtime:**

```text
"Total": "120T15:30:45"
```

Format: DDDThh:mm:ss (days T hours:minutes:seconds)

- Example: 120 days, 15 hours, 30 minutes, 45 seconds

**Polarity Runtimes:**

- `Pol1` - Time in polarity 1
- `Pol2` - Time in polarity 2
- Should be roughly equal for balanced electrode wear

**Polarity Changes:**

- Counter increments each polarity reversal
- High numbers indicate frequent switching
- Useful for electrode lifespan estimation

______________________________________________________________________

### Recommended MQTT Settings for Home Assistant

**Discovery:**

```text
Topic prefix: homeassistant
Device topic: poolcontroller (or custom name)
```

**Telemetry:**

```text
NPTelePeriod 0        # Report on changes only
SetOption147 1        # Enable MQTT sensor discovery
```

**Precision:**

```text
NPPHRes 2             # pH: 7.25
NPCLRes 2             # Chlorine: 1.52 ppm
NPIONRes 1            # Ionization: 5.0
```

**Options:**

```text
NPSetOption0 1        # Enable data validation
NPSetOption1 1        # Enable statistics (ESP32)
SetOption157 1        # Show NodeID (REQUIRED - auto-configured by integration)
```

**Time Sync:**

```text
Rule for daily sync:
Rule1 ON Time#Minute=0 DO NPTime 0 ENDON
Rule1 1
```

______________________________________________________________________

## Integration Notes for Home Assistant

### Entity Type Recommendations

Based on the data structure, here are recommended Home Assistant entity types:

#### Sensors (Read-Only)

- Temperature (`sensor`)
- pH.Data (`sensor`)
- Redox.Data (`sensor`)
- Chlorine.Data (`sensor`)
- Conductivity (`sensor`)
- Ionization.Data (`sensor`)
- Hydrolysis.Data (`sensor`)
- Hydrolysis.Runtime.\* (`sensor`)
- Powerunit voltages (`sensor`)
- Connection statistics (`sensor`)

#### Binary Sensors

- pH.FL1 (`binary_sensor` - flow detection)
- pH.Tank (`binary_sensor` - tank level)
- Hydrolysis.Cover (`binary_sensor` - pool cover)
- Filtration.State (`binary_sensor` or `switch`)
- Light (`binary_sensor` or `switch`)
- All Relay states (`binary_sensor` or `switch`)

#### Numbers (Adjustable Setpoints)

- pH.Min (`number`, range: 0-14)
- pH.Max (`number`, range: 0-14)
- Redox.Setpoint (`number`, range: 0-1000)
- Chlorine.Setpoint (`number`, range: 0-10)
- Ionization.Setpoint (`number`, range: 0-max)
- Hydrolysis.Setpoint (`number`, range: 0-100 or 0-max)

#### Selects (Mode Selection)

- Filtration.Mode (`select`, options: Manual/Auto/Heating/Smart/Intelligent/Backwash)
- Filtration.Speed (`select`, options: Low/Medium/High)
- Hydrolysis.Boost (`select`, options: Off/On/Redox)

#### Switches (Binary Control)

- Filtration.State (`switch` via NPFiltration)
- Light (`switch` via NPLight)
- Individual relays (`switch` via low-level commands or Berry scripts)

#### Diagnostic Sensors

- pH.State (`sensor` with state mapping)
- pH.Pump (`sensor` with state mapping)
- Hydrolysis.State (`sensor`, values: OFF/FLOW/POL1/POL2)
- Module.\* (`binary_sensor` - installed modules)
- Type (`sensor` - device model)
- Powerunit.Version (`sensor` - firmware version)

______________________________________________________________________

### MQTT Subscribe Patterns

To receive all NeoPool data:

```text
tele/+/SENSOR           # All devices, sensor data
tele/poolcontroller/SENSOR  # Specific device
```

To monitor command responses:

```text
stat/+/RESULT           # All devices, command results
stat/poolcontroller/RESULT  # Specific device
```

______________________________________________________________________

### MQTT Publish Patterns

To send commands:

```text
cmnd/poolcontroller/NPFiltration "1"
cmnd/poolcontroller/NPpHMin "7.0"
cmnd/poolcontroller/NPRedox "700"
```

______________________________________________________________________

### JSON Parsing Strategy

1. **Check Module object first** - Only create entities for installed modules
1. **Parse nested objects** - pH, Redox, Chlorine, etc. are sub-objects
1. **Handle optional fields** - Not all fields present in all configurations
1. **State mapping** - Convert numeric states to friendly names
1. **Unit extraction** - Hydrolysis.Unit determines % vs g/h
1. **Runtime parsing** - Convert "DDDThh:mm:ss" format to seconds/hours

______________________________________________________________________

### Example Python Parsing

```python
import json

def parse_neopool_sensor(payload):
    """Parse NeoPool MQTT sensor payload"""
    data = json.loads(payload)
    neopool = data.get("NeoPool", {})

    # Check installed modules
    modules = neopool.get("Module", {})

    entities = {}

    # Temperature (always available)
    if "Temperature" in neopool:
        entities["temperature"] = {
            "value": neopool["Temperature"],
            "unit": "°C",
            "device_class": "temperature"
        }

    # pH module
    if modules.get("pH") == 1:
        ph = neopool.get("pH", {})
        entities["ph"] = {
            "value": ph.get("Data"),
            "min": ph.get("Min"),
            "max": ph.get("Max"),
            "state": ph.get("State"),  # Map 0-6 to friendly names
            "unit": "pH"
        }

    # Redox module
    if modules.get("Redox") == 1:
        redox = neopool.get("Redox", {})
        entities["redox"] = {
            "value": redox.get("Data"),
            "setpoint": redox.get("Setpoint"),
            "unit": "mV"
        }

    # Hydrolysis module
    if modules.get("Hydrolysis") == 1:
        hydro = neopool.get("Hydrolysis", {})
        unit = hydro.get("Unit", "%")
        entities["hydrolysis"] = {
            "value": hydro.get("Data"),
            "setpoint": hydro.get("Setpoint"),
            "state": hydro.get("State"),
            "unit": unit
        }

    # Filtration (always available)
    filt = neopool.get("Filtration", {})
    entities["filtration"] = {
        "state": filt.get("State"),
        "speed": filt.get("Speed"),
        "mode": filt.get("Mode")
    }

    return entities
```

______________________________________________________________________

## Summary

This document provides complete technical reference for integrating Tasmota NeoPool controllers with
Home Assistant via MQTT. Key points:

1. **MQTT Structure:** Clear separation of telemetry (`tele/`), commands (`cmnd/`), and status (`stat/`)
1. **Rich Data:** Comprehensive sensor readings including pH, redox, chlorine, temperature, filtration, etc.
1. **Full Control:** Commands for all major pool functions (filtration, lights, chemical dosing, etc.)
1. **Flexibility:** Low-level register access for advanced customization
1. **Reliability:** Built-in data validation, error handling, and connection monitoring
1. **Module Detection:** Dynamic feature availability based on installed hardware

For Home Assistant integration development:

- Parse the `Module` object to detect available features
- Create appropriate entity types (sensor/number/select/switch/binary_sensor)
- Map numeric states to friendly names
- Handle optional fields gracefully
- Implement proper unit conversions
- Use change-based telemetry for efficiency

______________________________________________________________________

**Document Version:** 1.0
**Last Updated:** 2025-01-15
**Source:** <https://tasmota.github.io/docs/NeoPool/>
**License:** Documentation follows Tasmota project licensing
