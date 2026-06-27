# Feature Parity Plan — svasek Modbus Integration → our MQTT/Tasmota Integration

**Status:** Draft / on hold — write-ACK design **resolved** with @curzon01
(discussion #16, 2026-06-26); SENSOR-emit of config registers still open.
**Created:** 2026-06-16
**Updated:** 2026-06-26 (incorporated @curzon01's write-ACK answer)
**Scope:** Bring the MQTT/Tasmota integration toward feature parity with the
Modbus integration [`svasek/homeassistant-neopool-modbus`](https://github.com/svasek/homeassistant-neopool-modbus)
(analyzed at v4.1.1).

> **Write acknowledgment — RESOLVED by @curzon01** (discussion #16, 2026-06-26):
> command writes are confirmable entirely within the pure-push model, **no
> polling**. Subscribe to `stat/{topic}/RESULT` and match the command's JSON
> key. See "Write acknowledgment" section below.
>
> **Still open with @curzon01:** whether the Group-Y config registers could be
> emitted in `tele/{topic}/SENSOR` (e.g. gated behind an
> `NPTelePeriod`/`NPSetOption` flag to keep the default payload small). This is
> **not** needed for write-ACK — only for auto-reflecting *external* (keypad)
> changes to those settings without an on-demand `NPRead`. Preferred if feasible.

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

## Write acknowledgment (confirmed design — @curzon01, discussion #16)

@curzon01 confirmed that write confirmation works fully in the push model with
**no polling**. Mechanism:

- Every `cmnd/{topic}/<cmd>` returns an immediate response on
  **`stat/{topic}/RESULT`** (default `SetOption4 0`), separate from SENSOR.
- The RESULT JSON always carries the command as a key, e.g. `{"NPBoost":"OFF"}`,
  so we **match on the JSON key regardless of topic** — exactly how Tasmota's
  own rule engine works. **No need for `SetOption4 1`** / the `stat/.../<cmd>`
  topic.
- **Most commands return the real "change done" status** — they read the
  internal status / Modbus register *after* completion and return it. A genuine
  confirmation, not a parameter echo.
- **Exactly 3 commands only echo the parameter** (weak "command received" ACK),
  because Sugar Valley takes >1000 ms to process them and Tasmota can't block:
  **`NPFiltration`**, **`NPFiltrationspeed`**, **`NPLight`**. Not changeable.

**The 3-command exception costs us nothing**, because those exact commands
control state that is already in SENSOR (`NeoPool.Light`, `Filtration.State`,
`Filtration.Speed`) and relay/setting changes push SENSOR immediately. So:

- For those 3 → take the **immediate SENSOR push** as the real confirmation
  (no delayed-`TelePeriod` rule needed).
- For everything else → use the **`stat/RESULT` readback** as a true
  "change done" ACK.

Implementation: subscribe to `stat/{topic}/RESULT` (constant `TOPIC_RESULT`
already exists in `const.py`); after publishing a command, await a RESULT JSON
containing the command key; treat the 3 echo-only commands via the SENSOR echo.

**Bonus — the read layer is lightweight, not heavy polling.** `NPRead` returns
its value on the same `stat/RESULT` channel (`{"NPRead":...}`), so reading a
Group-Y config register is an **on-demand request/response** using the identical
JSON-key-match plumbing as the ACK. Practically: one `NPRead` per needed
register at startup to populate the entity; the write-ACK then keeps
HA-initiated changes correct. Only *external keypad* changes to those settings
go unreflected without an optional low-frequency refresh.

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
  `PLATFORMS` (`const.py`). **DECIDED: replace `switch.light` immediately** —
  drop the `light` switch description from `switch.py`, remove its stale
  registry entry on setup, and create the `light` entity instead. This is a
  **breaking change** (`switch.neopool_light` → `light.neopool_light`):
  document in release notes, update all 4 Lovelace dashboards (fresh +
  migrated variants), and check the companion YAML package's light entity
  domain so the `_migrated` dashboards stay correct. ~½–1 day (migration +
  dashboards push the estimate up).
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
     `stat/{topic}/RESULT` by **JSON-key match** (same plumbing as the
     write-ACK above; same pattern as the SO157 handshake).
  2. Reads the needed config registers **once at startup** to populate entity
     state (most cluster in `0x0415–0x0433`, so 1–2 `NPRead` calls with `Count`
     cover them). The **write-ACK keeps HA-initiated changes current** — no
     continuous polling required.
  3. Exposes `write_register(addr, value, save=True)` → `NPWrite`/`NPSave`,
     confirmed via the `stat/RESULT` readback.

  Per @curzon01's confirmation this is **not** a hybrid push+poll design: it's
  on-demand request/response (startup read + per-write ACK), all event-driven.
  **DECIDED: skip the optional low-frequency refresh for v1** — pure push, no
  polling. External keypad edits to these settings won't reflect in HA until
  the next restart or next HA-side write; document this limitation. ~1.5–2 days
  incl. tests.

  > If @curzon01 later emits these registers in SENSOR, **skip even the startup
  > read** and these become pure Group-1-style push entities.

- Thin entities over the layer (~½ day each), gating from payload keys:
  - **#4 UV mode** switch — `0x0427`, gate on `Relay.UV`.
  - **#2 Climate mode** switch — `0x0417`, gate on `Relay.Heating` + `Temperature`.
  - **#3 Smart antifreeze** switch — `0x041A`, gate on `Temperature`.
  - **#5 Heating temp** number — `0x0416` (skip svasek's heating↔intelligent
    auto-sync; expose plainly).
  - **#12 pH activation delay** number (seconds) — `0x0433` (system adds 10s;
    expose raw seconds with min/max range, **DECIDED: number, not select**).
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

Reordered after @curzon01's write-ACK confirmation removed the read-layer risk:
the `stat/RESULT` round-trip (used by both the write-ACK and on-demand `NPRead`)
is the same lightweight, event-driven plumbing, so **Group 2 is no longer a
risky strategic investment** — it's cheap and unlocks the bulk of the missing
config entities.

1. **Group 1 + Group 2 together** as the first milestone:
   - Build the small `stat/RESULT` JSON-key-match helper once (it serves the
     write-ACK *and* on-demand `NPRead`) alongside the Group 1 quick wins.
   - Then land the Group 1 entities (Light, auto time-sync, reset cell-runtime)
     and the Group 2b scalar config entities (UV mode, climate, antifreeze,
     heating temp, pH delay, intelligent min time) on top of it.
2. **Group 3** — bit-packed hydro cover/shutdown (reuses the same helper).
3. **Group 4** — timers, as a distinct later milestone.

Rationale: the one piece of shared infra (`stat/RESULT` matching) is needed for
Group 1's `NPWrite` ACK anyway, so building it first makes Group 2 nearly free
to follow rather than a separate phase.

## Decisions (resolved 2026-06-26)

1. **State strategy for Group Y:** startup `NPRead` to populate + `stat/RESULT`
   write-ACK to stay current. **No continuous polling, and the optional
   low-frequency keypad-edit refresh is skipped for v1** (pure push). Still
   **preferred** to drop even the startup read if @curzon01 emits these in
   SENSOR later.
2. **Write-ACK:** `stat/{topic}/RESULT` JSON-key match; `SO4=0` default is
   sufficient; 3 echo-only commands (`NPFiltration`, `NPFiltrationspeed`,
   `NPLight`) covered by the immediate SENSOR push.
3. **Starting scope:** Group 1 + Group 2 together as the first milestone.
4. **Light platform:** **replace** `switch.light` with `light.*` immediately
   (breaking change; release notes + all 4 dashboards + registry cleanup).
5. **pH activation delay (#12):** `number` (raw seconds), not a select.

## Still open

- With @curzon01: whether config registers can be emitted in SENSOR (would
  remove the startup `NPRead` and reflect keypad edits for free). Not blocking.

## Cross-repo note

Any user-visible numeric semantics introduced here (e.g. how cover-% or
shutdown-temp are decoded) should stay in lock-step with the companion YAML
package repo `alexdelprete/HA-NeoPool-MQTT-Package` per CLAUDE.md.

---

## Implementation task breakdown — Milestone 1 (Groups 1 + 2)

File-by-file, grounded in the current code. Symbols referenced:
`NeoPoolMQTTEntity` (base, `_publish_command` / `_subscribe_topic` / LWT
availability) and `NeoPoolEntity` in `entity.py`; the central SENSOR handler
`_setup_dynamic_disable_watch`, the `NeoPoolData` runtime dataclass, the
`connection_rate_signal` dispatcher pattern, and `_cleanup_removed_entities`
in `__init__.py`; `PLATFORMS` / `CMD_*` / `TOPIC_RESULT` in `const.py`.

### A. Shared infrastructure — `stat/RESULT` command + register layer

This is the one new piece; everything in Group 2 sits on it. Build it first
(Group 1's `NPWrite` button also needs the write path).

1. **`const.py`**
   - Add commands: `CMD_NPREAD = "NPRead"`, `CMD_NPWRITE = "NPWrite"`,
     `CMD_NPSAVE = "NPSave"`, `CMD_NPEXEC = "NPExec"` (we already have
     `CMD_TIME = "NPTime"`, `TOPIC_RESULT = "stat/{device}/RESULT"`).
   - Add register-address constants (from the register table above):
     `REG_HEATING_TEMP = 0x0416`, `REG_CLIMA_ONOFF = 0x0417`,
     `REG_SMART_ANTI_FREEZE = 0x041A`, `REG_INTELLIGENT_FILT_MIN_TIME = 0x041D`,
     `REG_UV_MODE = 0x0427`, `REG_HIDRO_COVER_ENABLE = 0x042C`,
     `REG_HIDRO_COVER_REDUCTION = 0x042D`, `REG_RELAY_ACTIVATION_DELAY = 0x0433`,
     `REG_RESET_USER_COUNTERS = 0x02F2`. (Group 3 will reuse 0x042C/0x042D.)
   - Add `Platform.LIGHT` to `PLATFORMS`.
   - Add a `config_register_signal(entry)` helper (mirror
     `connection_rate_signal`) for fan-out to Group 2 entities.

2. **New `command.py`** (or fold into `helpers.py`) — a small client stored in
   `runtime_data`:
   - `async_write_register(addr, value, *, save=True, exec=False)`:
     publish `NPWrite 0x{addr:04X} {value}`, then `NPExec` if `exec`, then
     `NPSave` if `save`.
   - `async_read_register(addr, count=1, *, timeout=5) -> int | list[int]`:
     publish `NPRead {"Address":addr,"Count":count}`, await the matching
     `stat/RESULT` JSON key (`NPRead`) via a pending-future keyed by command,
     with timeout. Used once at startup.
   - `async_send_command(command, payload, *, await_ack=False)`: generic
     publish; if `await_ack`, resolve on the RESULT JSON key.

3. **`__init__.py`**
   - Extend `NeoPoolData`: `register_state: dict[int, int]` (config-register
     cache), plus the command client / pending-futures map.
   - Add **one** subscription to `stat/{topic}/RESULT` (new function, e.g.
     `_setup_result_watch`). It parses RESULT JSON, resolves pending
     read/command futures by JSON key, updates `register_state` for known
     config registers, and `async_dispatcher_send(config_register_signal(entry))`.
   - At setup, after metadata, do a **batched startup `NPRead`** over the
     `0x0415–0x0433` cluster (1–2 calls with `Count`) to populate
     `register_state`. (`0x040F`/temperature-active already comes via SENSOR.)
   - ⚠️ **Test gotcha (CLAUDE.md):** any new `mqtt.async_subscribe` inside
     `async_setup_entry` breaks ~7 existing tests. Mock `_setup_result_watch`
     (and the startup-read function) the same way `_setup_dynamic_disable_watch`
     is mocked in `test_init*.py` / `test_coverage_98.py`.

### B. Group 1 entities

1. **New `light.py`** (`Platform.LIGHT`): `NeoPoolLight(NeoPoolMQTTEntity,
   LightEntity)`, `ColorMode.ONOFF`. Subscribe to `tele/{topic}/SENSOR`,
   `is_on` from `NeoPool.Light`; `turn_on/off` → `_publish_command("NPLight",
   "1"/"0")`. Confirmation via the immediate SENSOR echo (NPLight is one of the
   3 echo-only commands). Mirror the existing switch-light availability logic.

2. **`switch.py`**: delete the `key="light"` `SwitchEntityDescription`.
   `_cleanup_removed_entities` should drop the stale `switch.neopool_light`
   registry entry on next setup — **verify it does**, else add an explicit
   removal. (Breaking: `switch.neopool_light` → `light.neopool_light`.)

3. **`#11 auto time-sync switch`** (`switch.py` or a small dedicated entity):
   HA-side toggle, state in `entry.options` + `RestoreEntity`, default **off**.
   Put the drift logic in `_setup_dynamic_disable_watch` (already parses every
   SENSOR message): if enabled and `NeoPool.Time` drifts > **60 s** from HA
   time, publish `NPTime 0`. The switch only flips a `runtime_data` flag +
   persists the option (no second SENSOR subscription).

4. **`#14 reset cell-runtime button`** (`button.py`): `EntityCategory.
   DIAGNOSTIC`, `entity_registry_enabled_default=False`, gated on
   `Modules.Hydrolysis`. On press → `async_write_register(REG_RESET_USER_
   COUNTERS, 1)` (writes 0x02F2 then `NPSave`).

### C. Group 2 entities (over the register layer)

All read state from `register_state` (populated at startup, kept current by the
write-ACK), subscribe to `config_register_signal` for updates, and write via
`async_write_register`. Gating from SENSOR payload keys.

1. **Switches** (`switch.py`): `#4 UV mode` (`REG_UV_MODE`, gate `Relay.UV`),
   `#2 climate` (`REG_CLIMA_ONOFF`, gate `Relay.Heating` + `Temperature`),
   `#3 smart antifreeze` (`REG_SMART_ANTI_FREEZE`, gate `Temperature`).
2. **Numbers** (`number.py`): `#5 heating temp` (`REG_HEATING_TEMP`),
   `#6 intelligent min time` (`REG_INTELLIGENT_FILT_MIN_TIME`, minutes
   120–1440), `#12 pH activation delay` (`REG_RELAY_ACTIVATION_DELAY`, **number
   in seconds**). Source min/max/step from register encoding / svasek's number
   defs; flag any guessed ranges for review.

### D. const / translations / icons

1. `const.py`: the constants in A1 above.
2. `translations/en.json` (source of truth) + the other 9 languages: names for
    `light`, `auto_time_sync`, `reset_cell_runtime`, `uv_mode`, `climate_mode`,
    `smart_antifreeze`, `heating_temp`, `intelligent_min_time`,
    `ph_activation_delay`.
3. `icons.json`: icons for the new entities.

### E. Tests (CI only — never run pytest locally, per CLAUDE.md)

1. Mock the two new setup functions in the existing setup-entry tests (A3
    gotcha). Add: `test_light.py`; auto-time-sync drift logic; reset button;
    each Group 2 switch/number incl. write→`register_state` update and
    `stat/RESULT` parsing; the read/write client (read timeout, JSON-key match,
    write→save sequence). Keep total coverage **≥ 97 %**.

### F. Dashboards & docs

1. Update all 4 Lovelace files: `switch.neopool_light` → `light.neopool_light`
    in both fresh and `_migrated` variants (check the YAML package's light
    entity domain for the migrated ones); optionally surface the new entities.
2. `CHANGELOG.md` + `docs/releases/vX.Y.Z.md`: **flag the light entity as a
    breaking change**. Update `quality_scale.yaml` if any rule status changes.
3. Companion package repo: no numeric-semantics changes here, so no lock-step
    edit needed for Milestone 1 (revisit at Group 3's cover-% decoding).

### Suggested PR slicing

- **PR1 — infra + light + reset button + auto-sync** (Group 1 + the shared
  `stat/RESULT` layer). Self-contained, includes the breaking light change.
- **PR2 — Group 2 switches** (UV/climate/antifreeze) on the layer.
- **PR3 — Group 2 numbers** (heating temp / intelligent min time / pH delay).

Splitting keeps the breaking light migration isolated in PR1 and each later PR
small and reviewable.
