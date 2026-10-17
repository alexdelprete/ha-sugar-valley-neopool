# Tasmota with NeoPool

This folder contains binary files based on [Tasmota v16.0.0 Theo][tasmota-release], including the driver for the [Sugar Valley NeoPool Controller][neopool-driver], which are configured for use with the  [Sugar Valley NeoPool - Home Assistant Integration](https://github.com/alexdelprete/ha-sugar-valley-neopool).

## Initial flash

> [!WARNING]
> These files are for the **initial flash** of an ESP only.
> Do **not** use them for OTA updates or the *Upgrade by file upload* function.

For the initial flash of an ESP32/ESP8266, using [ESP_Flasher][esp-flasher] is recommended.
Choose the file that matches your ESP chip type:

| Chip type            | File                                                      | Example devices                                          |
| -------------------- | --------------------------------------------------------- | -------------------------------------------------------- |
| ESP32 (all types)    | [`tasmota32-ha-neopool.factory.bin`][esp32-factory]       | M5Stack [Atom Lite][atom-lite]                           |
| ESP32-S3 (all types) | [`tasmota32s3-ha-neopool.factory.bin`][esp32s3-factory]   | M5Stack [Atom S3][atom-s3], [Atom S3 Lite][atom-s3-lite] |
| ESP32-C3 (all types) | [`tasmota32c3-ha-neopool.factory.bin`][esp32c3-factory]   |                                                          |
| ESP8266 (all types)  | [`tasmota-ha-neopool.bin`][esp8266]                       |                                                          |

## Updating Tasmota

To update an existing Tasmota device, use the WebUI function **Firmware Upgrade** →
[**Upgrade by file upload**][tasmota-upgrade] and choose the file that matches your ESP chip type:

| Chip type            | File                                       | Example devices                                          |
| -------------------- | ------------------------------------------ | -------------------------------------------------------- |
| ESP32 (all types)    | [`tasmota32-ha-neopool.bin`][esp32]        | M5Stack [Atom Lite][atom-lite]                           |
| ESP32-S3 (all types) | [`tasmota32s3-ha-neopool.bin`][esp32s3]    | M5Stack [Atom S3][atom-s3], [Atom S3 Lite][atom-s3-lite] |
| ESP32-C3 (all types) | [`tasmota32c3-ha-neopool.bin`][esp32c3]    |                                                          |
| ESP8266 (all types)  | [`tasmota-ha-neopool.bin.gz`][esp8266-gz]  |                                                          |

<!-- Link references -->

<!-- Firmware files (relative, work in fork and origin) -->
[esp32-factory]: tasmota32-ha-neopool.factory.bin?raw=true
[esp32s3-factory]: tasmota32s3-ha-neopool.factory.bin?raw=true
[esp32c3-factory]: tasmota32c3-ha-neopool.factory.bin?raw=true
[esp8266]: tasmota-ha-neopool.bin?raw=true
[esp32]: tasmota32-ha-neopool.bin?raw=true
[esp32s3]: tasmota32s3-ha-neopool.bin?raw=true
[esp32c3]: tasmota32c3-ha-neopool.bin?raw=true
[esp8266-gz]: tasmota-ha-neopool.bin.gz?raw=true

<!-- External links -->
[tasmota]: https://github.com/arendst/Tasmota
[tasmota-release]: https://github.com/arendst/Tasmota/tree/v16.0.0
[tasmota-upgrade]: https://tasmota.github.io/docs/Upgrading/#upgrade-by-file-upload
[neopool-driver]: https://tasmota.github.io/docs/NeoPool/
[esp-flasher]: https://github.com/Jason2866/ESP_Flasher
[atom-lite]: https://docs.m5stack.com/en/core/ATOM%20Lite
[atom-s3]: https://docs.m5stack.com/en/core/AtomS3
[atom-s3-lite]: https://docs.m5stack.com/en/core/AtomS3%20Lite