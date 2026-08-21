# Lovelace dashboards

Four example dashboards for the Sugar Valley NeoPool integration —
two for **fresh installs** and two for users who **migrated from the
YAML package**.

## Which file should I use?

**Fresh install** (default device name `NeoPool`):

- [`ha_neopool_lovelace.yaml`](ha_neopool_lovelace.yaml) —
  full-width desktop layout (mushroom + masonry 400 px).
- [`ha_neopool_lovelace_responsive.yaml`](ha_neopool_lovelace_responsive.yaml)
  — mobile-friendly layout (tile + masonry 320 px).

**Migrated from the YAML package** (entity IDs still `neopool_mqtt_*`):

- [`ha_neopool_lovelace_migrated.yaml`](ha_neopool_lovelace_migrated.yaml)
  — full-width variant.
- [`ha_neopool_lovelace_responsive_migrated.yaml`](ha_neopool_lovelace_responsive_migrated.yaml)
  — responsive variant.

Not sure which you are? Open **Settings → Devices & services →
NeoPool → Entities** and look at one entity's ID. If it starts with
`sensor.neopool_mqtt_…` you migrated; if it starts with
`sensor.neopool_…` (no `_mqtt_`) you have a fresh install.

## Coverage

All four files cover the same scope:

- Sensors: temperature, pH, redox, hydrolysis (%) + (g/h), hydrolysis
  state / runtimes / polarity changes, pH state / pump, power-unit
  voltages, connection diagnostics.
- Controls: filtration switch, light, AUX1–AUX4 switches, clear
  error button, sync controller time button.
- Selects: filtration mode, filtration speed, boost mode.
- Setpoints: pH min / max, redox, hydrolysis, chlorine, ionization.
- Module presence and per-module relay states.
- Conditional sections that auto-hide when the relevant module
  (chlorine, ionization, conductivity) isn't installed.

The **migrated** variants additionally:

- Drop three relay-state tiles (pH / Filtration / Light) — the
  integration deletes those entities during migration because the YAML
  package's assumed fixed relay→function mapping was wrong (see
  `const.py:YAML_ENTITIES_TO_DELETE`).
- Use the package's entity-ID slugs (`hydrolysis_data`, `redox_data`,
  `connection_system_requests`, etc.) instead of the integration's
  default slugs (`hydrolysis`, `redox_orp`, `connection_requests`).

## Custom-card dependencies

Install these via [HACS][hacs] before applying any dashboard.

### Required by all four files

- [mini-graph-card][mini-graph-card]
- [masonry-layout (layout-card)][layout-card]

### Required by the full-width variants only

- [mushroom cards][mushroom] — provides `mushroom-entity-card`,
  `mushroom-select-card`, `mushroom-number-card`, `mushroom-legacy-template-card`
- [stack-in-card][stack-in-card]
- [text-divider-row][text-divider-row]

### Optional icon packs

All dashboards reference icons from the `phu:` (Pool & Hot-tub
Utilities) and `si:` (Simple Icons) icon packs. They render with
fallbacks if missing, but for fidelity install:

- [Pool & Hot-tub Utilities icons (`phu:`)][phu-icons]
- [Simple Icons (`si:`)][simple-icons]

## Entity-ID assumptions

The **fresh-install** files (`ha_neopool_lovelace.yaml`,
`ha_neopool_lovelace_responsive.yaml`) assume the default device name
`NeoPool` — i.e. entity IDs like `sensor.neopool_water_temperature`,
`switch.neopool_filtration`.

The **migrated** files (`*_migrated.yaml`) assume the device name
extracted during YAML-package migration is `Neopool Mqtt` — i.e.
entity IDs like `sensor.neopool_mqtt_water_temperature`,
`switch.neopool_mqtt_filtration_switch`. This is the standard
auto-extracted name; if you changed it manually during setup, do a
find/replace on `neopool_mqtt_` with your slug before applying.

You can confirm the actual entity IDs your install generated under
**Settings → Devices & services → NeoPool → Entities**.

## How to install

1. Install the [custom cards][hacs] listed above.
1. Open **Settings → Dashboards** → choose a dashboard → ⋮ → **Edit
   dashboard** → ⋮ → **Raw configuration editor**.
1. Under `views:`, paste the contents of one of the four YAML files in
   this folder.
1. Save. Hit ⋮ → **Refresh** if anything looks stale.

To preview without editing your main dashboard, create a new dashboard
first and paste the YAML there.

## Note for migrated users on the upstream package's lovelace files

The upstream [HA-NeoPool-MQTT-Package][package-repo] also ships
[`ha_neopool_mqtt_lovelace.yaml`][upstream-full] and
[`ha_neopool_mqtt_lovelace_responsive.yaml`][upstream-responsive].
Those continue to work after migration but with two caveats:

- Three tiles will show "entity not available" (pH / Filtration / Light
  relay states are deleted during migration).
- New entities the integration ships beyond the package (chlorine,
  ionization, conductivity, sync time, etc.) won't appear.

The `_migrated.yaml` files in this folder fix both gaps.

## Reporting issues

If an entity ID in any file doesn't match what your install generated,
please open an issue with the actual entity ID from your registry —
we'll either fix the dashboard or document the device-name caveat
better.

[hacs]: <https://hacs.xyz>
[mini-graph-card]: <https://github.com/kalkih/mini-graph-card>
[layout-card]: <https://github.com/thomasloven/lovelace-layout-card>
[mushroom]: <https://github.com/piitaya/lovelace-mushroom>
[stack-in-card]: <https://github.com/custom-cards/stack-in-card>
[text-divider-row]: <https://github.com/iantrich/text-divider-row>
[phu-icons]: <https://github.com/Mariusthvdb/custom-icons>
[simple-icons]: <https://github.com/vigonotion/hass-simpleicons>
[package-repo]: <https://github.com/alexdelprete/HA-NeoPool-MQTT-Package>
[upstream-full]: <https://github.com/alexdelprete/HA-NeoPool-MQTT-Package/blob/main/ha_neopool_mqtt_lovelace.yaml>
[upstream-responsive]: <https://github.com/alexdelprete/HA-NeoPool-MQTT-Package/blob/main/ha_neopool_mqtt_lovelace_responsive.yaml>
