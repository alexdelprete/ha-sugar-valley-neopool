# Feature Parity Plan — svasek Modbus Integration → our MQTT/Tasmota Integration

**Status:** Draft / on hold (awaiting reflection + discussion with @curzon01)
**Created:** 2026-06-16
**Scope:** Bring the MQTT/Tasmota integration toward feature parity with the
Modbus integration [`svasek/homeassistant-neopool-modbus`](https://github.com/svasek/homeassistant-neopool-modbus)
(analyzed at v4.1.1).

> **Open question to raise with @curzon01 (Tasmota NeoPool driver author):**
> Most missing features depend on **config registers that are NOT in the
> `tele/{topic}/SENSOR` payload**. If those registers could be emitted in
> SENSOR (perhaps gated behind an `NPTelePeriod`/`NPSetOption` flag to keep
> the default payload small), we would **avoid adding any polling layer** and
> could implement everything within our pure-push model. This is the
> preferred path if the driver can expose them. See "Pivotal finding" below.

---

## Pivotal finding: state-in-payload vs not

Our integration is **pure push** — it consumes only `tele/{topic}/SENSOR`,
whose field set is fixed by the driver (`NeoPoolShow()` in
`xsns_83_neopool.ino`) and cannot be extended from the HA side. This splits the
candidate features into two classes:

- **Group X — state IS in SENSOR** → implementable with today's architecture,
  no new infra: `Light`, `NeoPool.Time`, cell `Runtime.*`, all relay/module/
  cover *states*.
- **Group Y — state is a config register NOT in SENSOR** → to expose as proper
  read/write entities we must **read the register on demand** via
  `NPRead` → `stat/{topic}/RESULT`, because it never appears in telemetry.

**Write side is unblocked for everything.** `NPRead` / `NPWrite` / `NPExec` /
`NPSave` are all **built-in** driver commands (unlike `NPAux`, which needs the
Berry extension). So no firmware extension is required for any Group-Y feature —
only a request/response read layer (if we go that route).

Precedent for the round-trip already exists in our codebase: the SO157 /
STATUS2 / STATUS5 handshakes in `config_flow.py` and the dual-NodeID
acquisition both publish a command and parse a `stat/` reply.

Write-commit convention for Group-Y writes:
`NPWrite <reg> <value>` → `NPSave` (persist to EEPROM), plus `NPExec` where a
relay/timer must act immediately. Mirrors svasek's `apply=True`.

---

## Corrections vs the original 14-item gap list

After checking our code, three items are **not** gaps:

- **Pool cover state** already exists: `hydrolysis_cover` binary sensor
  (`binary_sensor.py`). Only the cover-reduction *config* is missing.
- **UV lamp state** already exists: `relay_uv_state` binary sensor.
- **Heating relay state** already exists: `relay_heating_state` binary sensor.

So the missing pieces are the **config switches/numbers/selects** behind these
states, not the state sensors.

**`#10` (filtration pump power & energy / Energy Dashboard) is intentionally
parked** — the owner wants a different implementation, planned separately.

---

## Per-feature analysis (13 features; #10 parked)

<!-- pyml disable-num-lines 40 line-length-->
| # | Feature | State source | Write mechanism | Gating (from payload) | Needs read-layer? |
|---|---------|--------------|-----------------|------------------------|-------------------|
| 1 | Light entity | `NeoPool.Light` | `NPLight 0/1` (built-in) | `Light` key present | No |
| 11 | Auto time-sync switch | `NeoPool.Time` | `NPTime 0` (built-in, already used) | always | No |
| 14 | Reset cell-runtime button | runtime in payload | `NPWrite 0x02F2 1` (+`NPSave`) | `Modules.Hydrolysis` | No (write-only) |
| 4 | UV mode switch | reg `0x0427` | `NPWrite 0x0427` | `Relay.UV` present | Yes |
| 2 | Climate mode switch | reg `0x0417` | `NPWrite 0x0417` | `Relay.Heating` + `Temperature` | Yes |
| 3 | Smart antifreeze switch | reg `0x041A` | `NPWrite 0x041A` | `Temperature` present | Yes |
| 5 | Heating temp number | reg `0x0416` | `NPWrite 0x0416` | `Relay.Heating` + `Temperature` | Yes |
| 12 | pH pump activation delay | reg `0x0433` | `NPWrite 0x0433` | pH module | Yes |
| 6 | Intelligent min filt time | reg `0x041D` | `NPWrite 0x041D` | `Temperature` + heating | Yes |
| 7 | Hydro cover reduction (enable+%) | regs `0x042C`/`0x042D` (bit-packed) | `NPWrite` read-modify-write | `Modules.Hydrolysis` | Yes |
| 8 | Hydro temp shutdown (enable+temp) | regs `0x042C`/`0x042D` (bit-packed) | `NPWrite` read-modify-write | `Modules.Hydrolysis` + `Temperature` | Yes |
| 13 | Per-relay AUX/Light timers | timer blocks `0x0434+` (15-reg, 32-bit pairs) | `NPWriteL` + `NPExec` | relay assigned | Yes (heavy) |

### Register reference (from `python-neopool-modbus` docs)

| Register | Addr | Encoding | Access |
|----------|------|----------|--------|
| `MBF_PAR_HEATING_GPIO` | 0x0415 | relay number (default 7) | R/W |
| `MBF_PAR_HEATING_TEMP` | 0x0416 | temp setpoint | R/W |
| `MBF_PAR_CLIMA_ONOFF` | 0x0417 | 0/1 | R/W |
| `MBF_PAR_SMART_ANTI_FREEZE` | 0x041A | 0/1 | R/W |
| `MBF_PAR_INTELLIGENT_TEMP` | 0x041C | temp setpoint | R/W |
| `MBF_PAR_INTELLIGENT_FILT_MIN_TIME` | 0x041D | minutes (2h–24h) | R/W |
| `MBF_PAR_UV_MODE` | 0x0427 | 0/1 | R/W |
| `MBF_PAR_UV_RELAY_GPIO` | 0x0429 | relay number | R/W |
| `MBF_PAR_TEMPERATURE_ACTIVE` | 0x040F | 0/1 | R/W |
| `MBF_PAR_HIDRO_COVER_ENABLE` | 0x042C | bits 0–1 enable flags | R/W |
| `MBF_PAR_HIDRO_COVER_REDUCTION` | 0x042D | bits 0–7 cover %; bits 8–15 shutdown temp | R/W |
| `MBF_PAR_RELAY_ACTIVATION_DELAY` | 0x0433 | seconds (system adds 10s) | R/W |
| Timer blocks | 0x0434–0x04D9 | 15-register blocks, 32-bit Low/High pairs | R/W |
| `MBF_SAVE_TO_EEPROM` (`NPSave`) | 0x02F0 | write 1 to persist | W |
| `MBF_RESET_USER_COUNTERS` | 0x02F2 | write any value to reset cell counters | W |
| `MBF_ACTION_COPY_TO_RTC` | 0x04F0 | write to sync RTC from TIME regs | W |
| `MBF_EXEC` (`NPExec`) | — | apply changes (commit) | W |

Timer block layout (each 15 registers): +0 enable/mode; +1..2 ON ts; +3..4 OFF
ts; +5..6 period; +7..8 interval; +9..10 countdown; +11..12 function code;
+13..14 work time. All multi-word values are 32-bit Low/High pairs.

---

## Implementation plan, grouped by difficulty / impact / importance

### Group 1 — Quick wins, no new infrastructure (do first)

Pure-push, high value, low effort. No read layer needed.

- **#1 Light platform.** Add `light.py` (`Platform.LIGHT`); `NeoPoolLight`
  with `ColorMode.ONOFF`, `is_on` from `NeoPool.Light`, `turn_on/off` →
  `NPLight 1/0` via existing `_publish_command`. Add `Platform.LIGHT` to
  `PLATFORMS` (`const.py`). Decide whether to keep/deprecate `switch.light`.
  Update the 4 Lovelace dashboards. ~½ day.
- **#11 Auto time-sync switch.** Persisted HA-side toggle (`entry.options` +
  `RestoreEntity`). Piggyback the central SENSOR watch in `__init__.py`: when
  enabled and `NeoPool.Time` drifts > threshold vs HA time, publish `NPTime 0`
  (same command as the existing `sync_controller_time` button). ~½ day.
- **#14 Reset cell-runtime button.** Write-only `button`, disabled by default,
  `EntityCategory.DIAGNOSTIC`, gated on `Modules.Hydrolysis`. Publishes
  `NPWrite 0x02F2 1` then `NPSave`. Introduces the small **`NPWrite` publish
  primitive** reused by Groups 2–4. ~½ day.

### Group 2 — Foundational read layer + simple scalar config entities

Gate for everything else. Build once; the rest get cheap.

- **2a — Register read/write layer (foundational).** Shared helper in
  `runtime_data` that:
  1. Publishes `NPRead {addr, count}`, resolves the matching
     `stat/{topic}/RESULT` (same pattern as SO157 handshake).
  2. Periodically refreshes a small, batched set of config registers (most
     cluster in `0x0415–0x0433`, so 1–2 `NPRead` calls with `Count` cover
     them) into a cache, fanned out via a dispatcher signal — the
     `ConnectionRateTracker` pattern already in the project.
  3. Exposes `write_register(addr, value, save=True)` → `NPWrite`/`NPSave`.

  ⚠️ Makes the integration **hybrid push+poll**. Mitigate by polling config
  registers infrequently (minutes), never per SENSOR tick. ~2–3 days incl.
  tests.

  > If @curzon01 can emit these registers in SENSOR, **skip 2a entirely** and
  > these become Group-1-style push entities.

- Thin entities over the layer (~½ day each), gating from payload keys:
  - **#4 UV mode** switch — `0x0427`, gate on `Relay.UV`.
  - **#2 Climate mode** switch — `0x0417`, gate on `Relay.Heating` + `Temperature`.
  - **#3 Smart antifreeze** switch — `0x041A`, gate on `Temperature`.
  - **#5 Heating temp** number — `0x0416` (skip svasek's heating↔intelligent
    auto-sync; expose plainly).
  - **#12 pH activation delay** select/number — `0x0433`.
  - **#6 Intelligent min filtration time** number — `0x041D` (minutes, 120–1440).

### Group 3 — Bit-packed hydrolysis cover/shutdown (medium-hard)

Do after Group 2; same read layer with read-modify-write bitmask care.

- **#7 + #8 together** (shared registers): `0x042C` holds the two enable bits;
  `0x042D` packs cover-% (bits 0–7) and shutdown-temp (bits 8–15). Small
  bitfield accessor; each switch/number does read-modify-write of the shared
  register so siblings don't clobber each other. 2 switches + 2 numbers,
  gated on `Modules.Hydrolysis` (+`Temperature` for #8). ~1–1.5 days.

### Group 4 — Per-relay timer scheduling (hard, separate milestone)

- **#13.** Timer blocks are 15-register structures with 32-bit Low/High pairs
  (`0x0434+`). Heaviest item. Phased approach: start with a `neopool.set_timer`
  service (start/stop/period/enable), add per-relay select entities later if
  wanted. Note: writing timer blocks via `NPWriteL`+`NPExec` could drive AUX
  relays **without** the Berry extension — worth validating as a side benefit.
  ~3–5 days.

---

## Suggested sequencing

1. **Group 1** — visible value immediately, zero architectural risk.
2. **Group 2a** — strategic investment (or skipped if SENSOR gains the regs);
   **2b** entities follow quickly.
3. **Group 3**, then **Group 4** as a distinct milestone.

## Open decisions (deferred)

1. **State strategy for Group Y:** (A) build the `NPRead` read layer; (B)
   optimistic write-only with `RestoreEntity`; (A-constrained) read layer but
   batched/infrequent only. **Preferred: avoid the layer entirely if @curzon01
   can expose the registers in SENSOR.**
2. **Starting scope:** Group 1 only / Group 1 + 2a / full plan.
3. Light platform: keep or deprecate the existing `switch.light`.

## Cross-repo note

Any user-visible numeric semantics introduced here (e.g. how cover-% or
shutdown-temp are decoded) should stay in lock-step with the companion YAML
package repo `alexdelprete/HA-NeoPool-MQTT-Package` per CLAUDE.md.
