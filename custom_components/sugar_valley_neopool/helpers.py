"""Helper functions for NeoPool MQTT integration."""

from __future__ import annotations

from collections import deque
import json
import logging
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ConnectionRateTracker:
    """Sliding-window calculator for the NeoPool Modbus connection error rate.

    Consumes the raw Tasmota counters from NeoPool.Connection.* in each
    SENSOR telemetry message and reports the percentage of failed polls
    within a configurable sliding window (default: 10 minutes).

    Failures = MBNoResponse + DataOutOfRange. The first value is a Modbus
    timeout (genuine connection failure); the second is a successful poll
    that returned invalid data (data-quality issue). Both reflect "this
    request didn't yield usable data" and are summed for the rate.

    Tasmota-reboot handling: if the requests counter ever drops vs the
    oldest sample in the window, the entire window is cleared — we don't
    try to compute a rate that spans a counter reset. The next sample
    starts a new accumulation.

    The tracker is intentionally framework-agnostic — it holds state but
    doesn't subscribe to MQTT or emit HA events. The NeoPool integration
    feeds it from its existing SENSOR-watch callback and entities read
    `rate` and `samples_count` to drive their own state.
    """

    def __init__(self, window_seconds: float = 600.0) -> None:
        """Initialize the tracker with a sliding-window size in seconds."""
        self._window_seconds = window_seconds
        # Each sample: (timestamp, requests, errors)
        self._samples: deque[tuple[float, int, int]] = deque()

    @property
    def window_seconds(self) -> float:
        """Return the configured sliding-window size."""
        return self._window_seconds

    @property
    def samples_count(self) -> int:
        """Return the number of samples currently in the window."""
        return len(self._samples)

    def update(self, timestamp: float, requests: int, errors: int) -> None:
        """Add a new sample at `timestamp` and prune older samples out of the window.

        `requests` and `errors` are the absolute counter values from Tasmota at
        the time of the sample (NOT deltas). The rate is computed as the delta
        between the oldest and newest samples in the window.
        """
        cutoff = timestamp - self._window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        self._samples.append((timestamp, requests, errors))

    @property
    def rate(self) -> float | None:
        """Return the current error-rate percentage, or None if undeterminable.

        Returns None when there are fewer than two samples in the window
        (not enough data to compute a delta) or when a Tasmota-reboot was
        detected within the window (request counter dropped). Returns 0.0
        when there are samples but no requests happened in the window
        (e.g. controller idle).
        """
        if len(self._samples) < 2:
            return None

        _, oldest_req, oldest_err = self._samples[0]
        _, newest_req, newest_err = self._samples[-1]
        req_delta = newest_req - oldest_req
        err_delta = newest_err - oldest_err

        if req_delta < 0:
            # Tasmota rebooted within the window — the rate would be misleading.
            # Drop the window so subsequent samples start a clean accumulation.
            self._samples.clear()
            return None
        if req_delta == 0:
            return 0.0
        return err_delta / req_delta * 100


def get_nested_value(data: dict[str, Any], path: str) -> Any | None:
    """Get a value from nested dictionary using dot notation path.

    Example: get_nested_value(data, "NeoPool.pH.Data")
    returns data["NeoPool"]["pH"]["Data"]
    """
    keys = path.split(".")
    value = data

    try:
        for key in keys:
            if isinstance(value, dict):
                value = value[key]
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                return None
    except KeyError, IndexError, TypeError:
        return None
    else:
        return value


def parse_runtime_duration(duration_str: str) -> float | None:
    """Parse NeoPool runtime duration format (DDDThh:mm:ss) to hours.

    Example: "123T04:30:00" -> 123*24 + 4 + 30/60 = 2956.5 hours
    """
    if not duration_str or "T" not in duration_str:
        return None

    try:
        days_part, time_part = duration_str.split("T")
        days = int(days_part)
        hours, minutes, seconds = map(int, time_part.split(":"))

        total_hours = days * 24 + hours + minutes / 60 + seconds / 3600
        return round(total_hours, 2)
    except ValueError, AttributeError:
        _LOGGER.warning("Failed to parse runtime duration: %s", duration_str)
        return None


def parse_json_payload(payload: str | bytes | bytearray) -> dict[str, Any] | None:
    """Parse MQTT JSON payload safely."""
    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        _LOGGER.debug("Failed to parse JSON payload: %s", ex)
        return None


def lookup_by_value(mapping: dict[Any, str], value: str) -> Any | None:
    """Reverse lookup: find key by value in a dictionary."""
    for key, val in mapping.items():
        if val == value:
            return key
    return None


def bit_to_bool(value: str | int) -> bool | None:
    """Convert bit string/int to boolean."""
    if value in ("1", 1):
        return True
    if value in ("0", 0):
        return False
    return None


def int_to_bool(value: str | int) -> bool:
    """Convert any positive integer to True."""
    try:
        return int(value) > 0
    except ValueError, TypeError:
        return False


@overload
def safe_float(value: Any) -> float | None: ...
@overload
def safe_float(value: Any, default: None) -> float | None: ...
@overload
def safe_float(value: Any, default: float) -> float: ...
def safe_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except ValueError, TypeError:
        return default


@overload
def safe_int(value: Any) -> int | None: ...
@overload
def safe_int(value: Any, default: None) -> int | None: ...
@overload
def safe_int(value: Any, default: int) -> int: ...
def safe_int(value: Any, default: int | None = None) -> int | None:
    """Safely convert value to int."""
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError, TypeError:
        return default


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def is_nodeid_masked(nodeid: str | None) -> bool:
    """Check if a NodeID is masked (old Tasmota, SetOption157=0).

    Old Tasmota masks NodeID as 'XXXX XXXX XXXX XXXX XXXX 3435'.

    Args:
        nodeid: The NodeID value from NeoPool.Powerunit.NodeID.

    Returns:
        True if masked (contains 'XXXX XXXX' pattern), False otherwise.
    """
    if not nodeid:
        return True  # No NodeID = treat as masked
    return "xxxx xxxx" in nodeid.lower()


def is_nodeid_hashed(nodeid: str | None) -> bool:
    """Check if a NodeID is hashed (new Tasmota, SetOption157=0).

    New Tasmota (post PR #24573) hashes the NodeID when SO157=0.
    The hash is indicated by 0xAA55 prefix in the first 2 bytes.

    Args:
        nodeid: The NodeID value from NeoPool.Powerunit.NodeID.

    Returns:
        True if hashed (starts with 'AA55' after normalization), False otherwise.
    """
    if not nodeid:
        return False
    return nodeid.replace(" ", "").upper().startswith("AA55")


def classify_nodeid(nodeid: str | None) -> str:
    """Classify a NodeID into its format type.

    Args:
        nodeid: The NodeID value to classify.

    Returns:
        "masked" if old Tasmota XXXX format,
        "hashed" if new Tasmota AA55 format,
        "real" if actual hardware NodeID,
        "invalid" if None/empty/hidden/non-string.
    """
    if not nodeid or not isinstance(nodeid, str):
        return "invalid"
    if nodeid.lower() in ("hidden", "hidden_by_default"):
        return "invalid"
    if is_nodeid_masked(nodeid):
        return "masked"
    if is_nodeid_hashed(nodeid):
        return "hashed"
    return "real"


def validate_nodeid(nodeid: str | None) -> bool:
    """Validate NodeID is present and usable as an identifier.

    Accepts real and hashed NodeIDs. Rejects None, empty, hidden,
    and old masked (XXXX) format.

    Args:
        nodeid: The NodeID value to validate.

    Returns:
        True if NodeID is valid and usable, False otherwise.
    """
    classification = classify_nodeid(nodeid)
    return classification in ("real", "hashed")


def normalize_nodeid(nodeid: str | None) -> str:
    """Normalize NodeID for use in unique_ids and identifiers.

    Tasmota NodeIDs have spaces between hex groups: '0026 0051 5443 5016 2036 3435'.
    This function removes spaces for clean identifiers: '002600515443501620363435'.

    Args:
        nodeid: The NodeID value to normalize, or None.

    Returns:
        Normalized NodeID string (uppercase, no spaces), or empty string if None.
    """
    if not nodeid:
        return ""
    # Remove spaces and convert to uppercase for consistency
    return nodeid.replace(" ", "").upper()


def is_masked_unique_id(unique_id: str) -> bool:
    """Check if a unique_id contains a masked NodeID pattern.

    Masked NodeIDs appear when Tasmota SetOption157 is disabled (0).
    They contain 'XXXX' patterns like 'neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_ph_data'.

    Args:
        unique_id: The entity unique_id to check.

    Returns:
        True if the unique_id contains masked NodeID pattern, False otherwise.
    """
    if not unique_id:
        return False
    return "xxxx" in unique_id.lower()


def extract_entity_key_from_masked_unique_id(unique_id: str) -> str | None:
    """Extract the entity key from a masked unique_id.

    Given: 'neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_ph_data'
    Returns: 'ph_data'

    The format is: neopool_mqtt_{masked_nodeid}_{entity_key}
    where masked_nodeid contains spaces and 'XXXX' patterns.
    The masked NodeID ends with 4 hex digits (like '3435').

    Args:
        unique_id: The masked unique_id to extract from.

    Returns:
        The entity key (e.g., 'ph_data'), or None if extraction failed.
    """
    if not unique_id or not unique_id.startswith("neopool_mqtt_"):
        return None

    # Remove the prefix
    remainder = unique_id[len("neopool_mqtt_") :]

    # The masked NodeID pattern is: "XXXX XXXX XXXX XXXX XXXX HHHH" where HHHH is hex
    # After that comes an underscore and the entity_key
    # Strategy: Find the last occurrence of a pattern like "XXXX" followed by
    # spaces/hex and then underscore, and take everything after

    # Split by underscore and accumulate parts from the right until we hit
    # a part that contains "XXXX" or is just hex digits (part of NodeID)
    parts = remainder.split("_")

    # Find where the NodeID ends and entity_key begins
    # NodeID parts contain "XXXX" or are hex digits
    # Entity key parts are normal words like "ph", "data", "water", "temperature"
    entity_key_parts = []

    for i in range(len(parts) - 1, -1, -1):
        part = parts[i]
        part_lower = part.lower()

        # Check if this part is part of the NodeID
        # NodeID parts: contain "xxxx", contain spaces (joined), or are hex-only
        if "xxxx" in part_lower or " " in part:
            # This is part of NodeID, stop here
            break

        # Check if this is a hex-only part that could be the end of NodeID (like "3435")
        # But only if it's 4 chars and all hex, AND we haven't found any entity key yet
        if len(part) == 4 and all(c in "0123456789abcdefABCDEF" for c in part):
            # This could be the last part of NodeID
            # Only treat as NodeID if we haven't accumulated any entity key parts
            # OR if the previous part contains XXXX
            if not entity_key_parts:
                # Check if previous parts have XXXX pattern
                if i > 0 and "xxxx" in "_".join(parts[:i]).lower():
                    break
            # Otherwise, it might be a valid entity key part (unlikely but possible)

        entity_key_parts.insert(0, part)

    if entity_key_parts:
        return "_".join(entity_key_parts)

    return None


async def async_set_setoption157(hass: HomeAssistant, mqtt_topic: str, enable: bool) -> bool:
    """Set SetOption157 on Tasmota device via MQTT.

    Used during setup to toggle SO157 for dual NodeID acquisition.

    Args:
        hass: Home Assistant instance
        mqtt_topic: The MQTT topic prefix for the device
        enable: True to show real NodeID, False to show hashed/masked NodeID

    Returns:
        True if the command was sent successfully, False otherwise.
    """
    # Import mqtt here to avoid circular imports
    from homeassistant.components import mqtt  # noqa: PLC0415

    if not mqtt_topic:
        _LOGGER.warning("No MQTT topic provided, cannot set SetOption157")
        return False

    command_topic = f"cmnd/{mqtt_topic}/SetOption157"
    payload = "1" if enable else "0"

    try:
        await mqtt.async_publish(hass, command_topic, payload, qos=1, retain=False)
    except Exception:
        _LOGGER.exception("Failed to send SetOption157 command to %s", mqtt_topic)
        return False
    else:
        _LOGGER.debug("Sent SetOption157 %s to %s", payload, mqtt_topic)
        return True
