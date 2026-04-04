# NodeID Dual Recognition — Design Document

## Problem Statement

The NeoPool MQTT integration currently **requires** Tasmota's `SetOption157`
to be set to `1` to expose the hardware NodeID. This NodeID is used as the
foundation for all entity unique IDs, device identifiers, and config entry
uniqueness.

When SO157=0 (Tasmota default), the NodeID was masked:

```text
XXXX XXXX XXXX XXXX XXXX 3435
```

Only the last 2 bytes varied, making it unsuitable as a unique identifier
(two devices could collide). The integration therefore forced SO157=1 at
setup and enforced it at runtime — adding complexity and overriding user
preferences.

### What changed in Tasmota

[Tasmota PR #24573](https://github.com/arendst/Tasmota/pull/24573) (merged
2026-03-23, by @curzon01) changed the SO157=0 behavior. Instead of masking
with `XXXX`, Tasmota now outputs a **deterministic hash** of the real NodeID.
The hash is identified by a `0xAA55` prefix in the first 2 bytes:

```text
AA55 7B3E 9F12 C4A8 2D6E 51F0
```

This hash is:

- **Deterministic**: Same real NodeID always produces the same hash
- **Unique**: Different NodeIDs produce different hashes
- **Stable**: Survives reboots, firmware updates, and reconfiguration
- **Privacy-friendly**: The real NodeID cannot be derived from the hash

This means SO157=1 is no longer required — the hashed NodeID is a perfectly
valid unique identifier.

______________________________________________________________________

## NodeID Formats

| Format | Example | Prefix | Usable | Source |
|--------|---------|--------|--------|--------|
| Real | `0026 0051 5443 5016 2036 3435` | Any | Yes | SO157=1 (any Tasmota) |
| Hashed | `AA55 7B3E 9F12 C4A8 2D6E 51F0` | `AA55` | Yes | SO157=0 (new Tasmota, post-PR) |
| Masked | `XXXX XXXX XXXX XXXX XXXX 3435` | `XXXX` | No | SO157=0 (old Tasmota, pre-PR) |

**Classification logic:**

```python
def classify_nodeid(nodeid: str) -> str:
    normalized = nodeid.upper().replace(" ", "")
    if "XXXX" in normalized:
        return "masked"
    if normalized.startswith("AA55"):
        return "hashed"
    return "real"
```

______________________________________________________________________

## Dual Recognition Design

### Core Idea

At setup, the integration reads **both** the hashed and real NodeIDs by
toggling SO157 once. Both values are stored in the config entry. At runtime,
any incoming NodeID is matched against all stored values — the device is
recognized regardless of SO157 state.

### Config Entry Storage

```python
config_entry.data = {
    "nodeid": "AA557B3E9F12C4A82D6E51F0",       # canonical (hashed)
    "nodeid_real": "002600515443501620363435",    # anchor (real)
    "nodeid_hashed": "AA557B3E9F12C4A82D6E51F0", # hashed
    "nodeid_masked": None,                        # old format (if applicable)
    # ... other config data
}
```

**Canonical ID** (`nodeid`): Used for entity unique IDs and device registry.
Set to `nodeid_hashed` when available, falls back to `nodeid_real` for old
Tasmota installations.

**Anchor ID** (`nodeid_real`): The real hardware NodeID. Never changes for a
given NeoPool controller. Used to verify device identity during Tasmota
upgrades/downgrades.

______________________________________________________________________

## Setup Flow

### `_auto_configure_nodeid()` — Optimized

```text
Step 1: Subscribe to tele/{topic}/SENSOR
        Wait for first message containing NodeID

Step 2: Classify the received NodeID
        ┌─────────────────────────────────────────┐
        │ classify_nodeid(received_nodeid)         │
        ├──────────┬──────────┬───────────────────┤
        │ "hashed" │ "real"   │ "masked"          │
        │ (AA55)   │ (normal) │ (XXXX)            │
        └────┬─────┴────┬─────┴────┬──────────────┘
             │          │          │
Step 3: Toggle SO157 to get the other format
             │          │          │
             ▼          ▼          ▼
        SO157=1      SO157=0     SO157=1
        read real    read hash   read real
        restore 0    restore 1   restore 0
             │          │          │
             ▼          ▼          ▼
        Have both   Have both   Have real +
        hashed +    real +      masked (no
        real        hashed      hash available)
             │          │          │
Step 4: Store in config entry     │
             │          │          │
Step 5: Set canonical             │
        = hashed     = hashed    = real (fallback)
```

**Key properties:**

- Always exactly **1 toggle** and **2 reads**
- SO157 is **restored** to its original state
- Works with any Tasmota version

______________________________________________________________________

## Runtime Recognition

When a SENSOR message arrives with a NodeID:

```text
incoming_nodeid = extract from payload

if normalize(incoming) == stored_hashed → RECOGNIZED (SO157=0, new Tasmota)
if normalize(incoming) == stored_real   → RECOGNIZED (SO157=1)
if normalize(incoming) == stored_masked → RECOGNIZED (SO157=0, old Tasmota)
```

**If none match but format is recognizable → Tasmota version change detected
(see next section).**

______________________________________________________________________

## Tasmota Upgrade/Downgrade Detection

### Case 1: User upgrades Tasmota (XXXX → AA55)

User had old Tasmota (canonical = real NodeID). After upgrading, SO157=0
produces a new `AA55` hash instead of the old `XXXX` mask.

```text
1. SENSOR message arrives with unknown AA55 NodeID
2. Integration detects: starts with AA55, not in stored values
3. Toggle SO157=1, read real NodeID
4. Real matches stored_real → confirmed same device
5. Store new AA55 value as nodeid_hashed
6. Migrate entity unique_ids: real → hashed (privacy improvement)
7. Update canonical to hashed
```

### Case 2: User downgrades Tasmota (AA55 → XXXX)

User had new Tasmota (canonical = hashed). After downgrading, SO157=0
produces `XXXX` mask instead of `AA55` hash.

```text
1. SENSOR message arrives with unknown XXXX NodeID
2. Integration detects: contains XXXX, not in stored values
3. Toggle SO157=1, read real NodeID
4. Real matches stored_real → confirmed same device
5. Store XXXX as nodeid_masked
6. Keep canonical unchanged (hashed unique_ids still valid, entities
   continue working when user sets SO157=1 or re-upgrades Tasmota)
```

### Case 3: User flips SO157 after setup

No action needed — both formats are already stored and recognized.

______________________________________________________________________

## Migration Paths

### Existing users upgrading the integration

Users currently have entity unique IDs in the format:

```text
neopool_mqtt_{real_nodeid}_{entity_key}
```

After updating the integration:

1. Setup acquires both hashed and real NodeIDs
2. Integration detects existing entities use real NodeID format
3. Migrates all entity unique IDs:

```text
neopool_mqtt_{real_nodeid}_{key} → neopool_mqtt_{hashed_nodeid}_{key}
```

1. Updates config entry and device registry
1. All historical data, automations, and customizations preserved
   (entity_id unchanged, only unique_id updated)

### Users with old XXXX entities upgrading both integration and Tasmota

1. Integration detects old `XXXX` unique IDs in entity registry
2. Setup acquires hashed and real NodeIDs (new Tasmota)
3. Migrates:

```text
neopool_mqtt_{xxxx_masked}_{key} → neopool_mqtt_{hashed_nodeid}_{key}
```

### Users with old Tasmota (no upgrade)

1. Setup gets `XXXX` + real NodeID
2. Canonical = real (no hash available)
3. Entity unique IDs use real NodeID
4. When user eventually upgrades Tasmota, runtime detection (Case 1)
   triggers migration to hashed

______________________________________________________________________

## Backward Compatibility

| Tasmota Version | SO157=0 Output | Integration Behavior |
|----------------|----------------|---------------------|
| Pre-PR (old) | XXXX masked | Use real NodeID as canonical. Warn user to update Tasmota. |
| Post-PR (new) | AA55 hashed | Use hashed NodeID as canonical. Privacy by default. |

The integration works with both. No minimum Tasmota version is enforced —
old Tasmota users get a recommendation to upgrade but are not blocked.

______________________________________________________________________

## Privacy Considerations

- **Entity unique IDs**: Use hashed NodeID — the real hardware identifier
  is not exposed in entity metadata, UI, or standard logs
- **Config entry**: Stores both hashed and real, but config entry data is
  internal to Home Assistant and not exposed to users
- **Diagnostics**: The `nodeid_real` value is redacted in diagnostic
  downloads, only the hashed canonical is shown
- **Sensor entity**: The `system_id` sensor (renamed from
  `powerunit_nodeid` per curzon01's suggestion) displays whatever
  the device currently reports (hashed or real depending on SO157) —
  this matches what the user would see in the Tasmota console

______________________________________________________________________

## Edge Cases

### Multiple NeoPool devices

Each device has its own config entry with its own pair of hashed/real
NodeIDs. The dual recognition is per-config-entry. No cross-device
confusion is possible since the real NodeID (anchor) is hardware-unique.

### Config entry restored from backup

If a user restores a Home Assistant backup, the stored NodeIDs in the
config entry are restored. The integration will recognize the device
on the next SENSOR message via either stored value. No re-setup needed.

### Two devices with same last 2 bytes (old Tasmota)

With old Tasmota masking, only the last 2 bytes vary. If two devices
share those bytes, the integration falls back to real NodeID (SO157=1)
which is fully unique. This is the same behavior as before — no
regression.

______________________________________________________________________

## Summary of Changes vs Current Implementation

| Aspect | Current | New |
|--------|---------|-----|
| SO157 requirement | Mandatory SO157=1 | No requirement |
| Setup | Force SO157=1, read real NodeID | Toggle once, read both formats |
| Runtime enforcement | Monitor SENSOR, re-enable SO157 | None |
| Canonical ID | Real NodeID | Hashed NodeID (privacy) |
| Device recognition | Single NodeID match | Match against hashed, real, or masked |
| Old Tasmota support | Force SO157=1 | Fallback to real NodeID, recommend upgrade |
| Tasmota version change | Not handled | Auto-detected and migrated |
| Code complexity | SO157 query/set/enforce/migrate | Classify + dual store + match |

______________________________________________________________________

## References

- [Tasmota PR #24573](https://github.com/arendst/Tasmota/pull/24573) —
  NeoPool always output valid sensitive data
- [Forum discussion](https://community.home-assistant.io/t/632517/490) —
  SO157 prerequisite discussion with @curzon01
- Tasmota source: `xsns_83_neopool.ino`, hash implementation uses
  XOR/rotation/avalanche with `0xAA55` prefix indicator
