# Lovelace dashboards

Two example dashboards for the Sugar Valley NeoPool integration:

- [`ha_neopool_lovelace.yaml`](ha_neopool_lovelace.yaml) — full-width
  desktop layout using mushroom cards, mini-graph cards, and a 400-px
  masonry layout. Mirrors the structure of the original YAML-package
  dashboard, plus conditional sections for the chlorine, ionization, and
  conductivity modules and tiles for the new diagnostic entities.
- [`ha_neopool_lovelace_responsive.yaml`](ha_neopool_lovelace_responsive.yaml)
  — mobile-friendly layout using HA's built-in tile cards in a 320-px
  masonry layout. Same coverage as the full-width version.

Both files are designed to be pasted as a **view** into an existing
dashboard's `views:` array (they start with a top-level `- type:` /
`- icon:`).

## Custom-card dependencies

Install these via [HACS][hacs] before applying either dashboard.

### Required by both files

- [mini-graph-card][mini-graph-card]
- [masonry-layout (layout-card)][layout-card]

### Required by the full-width dashboard only

- [mushroom cards][mushroom] — provides `mushroom-entity-card`,
  `mushroom-select-card`, `mushroom-number-card`
- [stack-in-card][stack-in-card]
- [text-divider-row][text-divider-row]

### Optional icon packs

Both dashboards reference icons from the `phu:` (Pool & Hot-tub
Utilities) and `si:` (Simple Icons) icon packs. They render with
fallbacks if missing, but for fidelity install:

- [Pool & Hot-tub Utilities icons (`phu:`)][phu-icons]
- [Simple Icons (`si:`)][simple-icons]

## Entity-ID assumptions

Both files reference entities using the **default** device name of
`NeoPool` — i.e. entity IDs like `sensor.neopool_water_temperature`,
`switch.neopool_filtration`, etc.

If you set a different device name during setup (e.g. "Pool Backyard"),
the integration will generate slugified entity IDs accordingly
(`sensor.pool_backyard_water_temperature`). In that case, do a
find/replace on `neopool_` in the YAML before applying it.

You can confirm the actual entity IDs your install generated under
**Settings → Devices & services → NeoPool → Entities**.

## Migrated from the YAML package?

If you migrated to this integration from the
[HA-NeoPool-MQTT-Package][package-repo], your entity IDs were preserved
as the original `sensor.neopool_mqtt_*` pattern (so your existing
history and automations keep working). The two example files in this
folder will **not** match your entity IDs.

Use the original lovelace files from the package repository instead:

- [`ha_neopool_mqtt_lovelace.yaml`][upstream-full]
- [`ha_neopool_mqtt_lovelace_responsive.yaml`][upstream-responsive]

Those files continue to work unchanged for migrated installs.

## How to install

1. Install the [custom cards][hacs] listed above.
1. Open **Settings → Dashboards** → choose a dashboard → ⋮ → **Edit
   dashboard** → ⋮ → **Raw configuration editor**.
1. Under `views:`, paste the contents of one of the two YAML files in
   this folder.
1. Save. Hit ⋮ → **Refresh** if anything looks stale.

To preview without editing your main dashboard, create a new dashboard
first and paste the YAML there.

## Reporting issues

If an entity ID in either file doesn't match what your install
generated, please open an issue with the actual entity ID from your
registry — we'll either fix the dashboard or document the device-name
caveat better.

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
