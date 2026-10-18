/*
  user_config_override.h - build configuration for the NeoPool Tasmota binaries in firmware/

  The Sugar Valley NeoPool driver is not included in Tasmota's precompiled binaries.
  This file follows the official instructions (https://tasmota.github.io/docs/NeoPool/):
  the firmware workflow (.github/workflows/firmware.yml) copies it to
  tasmota/user_config_override.h in a checkout of the Tasmota release tag before building.
  Everything else uses Tasmota's defaults.
*/

#ifndef _USER_CONFIG_OVERRIDE_H_
#define _USER_CONFIG_OVERRIDE_H_

// Sugar Valley NeoPool controller driver (xsns_83_neopool)
#ifndef USE_NEOPOOL
#define USE_NEOPOOL
#endif

// Value range checks. The driver enables them by default on ESP32 only; when set it also
// enables NEOPOOL_CONNSTAT, the Modbus connection statistics (MBRequests, MBNoResponse,
// DataOutOfRange) behind the integration's connection error rate and Controller Link
// entities. Without this define ESP8266 builds have neither.
#ifndef NEOPOOL_RANGE_CHECKS
#define NEOPOOL_RANGE_CHECKS
#endif

#endif  // _USER_CONFIG_OVERRIDE_H_
