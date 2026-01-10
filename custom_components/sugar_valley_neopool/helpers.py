"""Helper functions for NeoPool MQTT integration."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


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
    except (KeyError, IndexError, TypeError):
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
    except (ValueError, AttributeError):
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
    except (ValueError, TypeError):
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
    except (ValueError, TypeError):
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
    except (ValueError, TypeError):
        return default


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def validate_nodeid(nodeid: str | None) -> bool:
    """Validate NodeID is present and not 'hidden' or masked.

    Args:
        nodeid: The NodeID value to validate.

    Returns:
        True if NodeID is valid (present, not hidden, and not masked), False otherwise.
    """
    if nodeid is None or nodeid == "":
        return False
    if isinstance(nodeid, str):
        nodeid_lower = nodeid.lower()
        # Check for literal hidden values
        if nodeid_lower in ["hidden", "hidden_by_default"]:
            return False
        # Check for masked NodeID pattern (contains XXXX when SetOption157 is 0)
        if "xxxx" in nodeid_lower:
            return False
    return True


def normalize_nodeid(nodeid: str | None) -> str:
    """Normalize NodeID for use in unique_ids and identifiers.

    The real NodeID from Tasmota is a hex string like '4C7525BFB344'.
    Masked NodeIDs have spaces like 'XXXX XXXX XXXX XXXX XXXX 3435'.
    This function removes spaces and ensures a clean identifier.

    Args:
        nodeid: The NodeID value to normalize, or None.

    Returns:
        Normalized NodeID string (uppercase, no spaces), or empty string if None.
    """
    if not nodeid:
        return ""
    # Remove spaces and convert to uppercase for consistency
    return nodeid.replace(" ", "").upper()


def is_nodeid_masked(nodeid: str | None) -> bool:
    """Check if a NodeID from SENSOR data is masked (SetOption157 disabled).

    When SetOption157 is OFF, NodeID appears as 'XXXX XXXX XXXX XXXX XXXX 3435'.
    When SetOption157 is ON, NodeID appears as '4C7525BFB344' (clean hex).

    Args:
        nodeid: The NodeID value from NeoPool.Powerunit.NodeID.

    Returns:
        True if masked (contains XXXX or spaces), False if clean hex.
    """
    if not nodeid:
        return True  # No NodeID = treat as masked
    return "xxxx xxxx" in nodeid.lower()


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


async def async_query_setoption157(
    hass: HomeAssistant, mqtt_topic: str, wait_timeout: float = 5.0
) -> bool | None:
    """Query SetOption157 status from Tasmota via MQTT.

    Sends SO157 query command and waits for response on stat/{topic}/SO.
    Response format: {"SetOption157":"ON"} or {"SetOption157":"OFF"}

    Args:
        hass: Home Assistant instance
        mqtt_topic: The MQTT topic prefix for the device
        wait_timeout: Maximum time to wait for response (seconds)

    Returns:
        True if SO157 is ON, False if OFF, None if timeout/error.
    """
    # Import mqtt here to avoid circular imports
    from homeassistant.components import mqtt  # noqa: PLC0415
    from homeassistant.core import callback  # noqa: PLC0415

    if not mqtt_topic:
        _LOGGER.warning("No MQTT topic provided, cannot query SetOption157")
        return None

    result: bool | None = None
    event = asyncio.Event()

    @callback
    def message_received(msg: mqtt.ReceiveMessage) -> None:
        """Handle SO response message."""
        nonlocal result
        try:
            if isinstance(msg.payload, (bytes, bytearray)):
                payload_str = msg.payload.decode("utf-8")
            else:
                payload_str = msg.payload

            payload = json.loads(payload_str)
            # Response format: {"SetOption157":"ON"} or {"SetOption157":"OFF"}
            so157_value = payload.get("SetOption157")
            if so157_value is not None:
                result = so157_value.upper() == "ON"
                _LOGGER.debug("SetOption157 query result: %s", so157_value)
                event.set()
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as err:
            _LOGGER.debug("Failed to parse SO response payload: %s", err)

    # Subscribe to stat/{topic}/SO for response
    so_topic = f"stat/{mqtt_topic}/SO"
    unsubscribe = await mqtt.async_subscribe(hass, so_topic, message_received, qos=1)

    try:
        # Send SO157 query command (no payload)
        command_topic = f"cmnd/{mqtt_topic}/SO157"
        await mqtt.async_publish(hass, command_topic, "", qos=1, retain=False)
        _LOGGER.debug("Sent SO157 query to %s", mqtt_topic)

        # Wait for response
        try:
            await asyncio.wait_for(event.wait(), timeout=wait_timeout)
        except TimeoutError:
            _LOGGER.debug("Timeout waiting for SO157 response from %s", mqtt_topic)
            return None
    finally:
        unsubscribe()

    return result


async def async_ensure_setoption157_enabled(
    hass: HomeAssistant, mqtt_topic: str, max_retries: int = 2
) -> bool:
    """Ensure SetOption157 is enabled on the device.

    Checks current status, sends enable command if needed, and verifies result.

    Args:
        hass: Home Assistant instance
        mqtt_topic: The MQTT topic prefix for the device
        max_retries: Maximum attempts to enable SO157

    Returns:
        True if SO157 is ON (or successfully enabled), False if failed.
    """
    for attempt in range(max_retries):
        # Query current status
        current_status = await async_query_setoption157(hass, mqtt_topic)

        if current_status is True:
            _LOGGER.debug("SetOption157 is already ON for %s", mqtt_topic)
            return True

        if current_status is False:
            _LOGGER.info("SetOption157 is OFF for %s, enabling it", mqtt_topic)
        else:
            _LOGGER.warning(
                "Could not query SetOption157 for %s (attempt %d/%d)",
                mqtt_topic,
                attempt + 1,
                max_retries,
            )

        # Send enable command
        if not await async_set_setoption157(hass, mqtt_topic, enable=True):
            _LOGGER.error("Failed to send SetOption157 command to %s", mqtt_topic)
            continue

        # Brief delay for Tasmota to process
        await asyncio.sleep(0.5)

        # Verify it's now ON
        verified_status = await async_query_setoption157(hass, mqtt_topic)
        if verified_status is True:
            _LOGGER.info("Successfully enabled SetOption157 for %s", mqtt_topic)
            return True

        _LOGGER.warning(
            "SetOption157 verification failed for %s (attempt %d/%d)",
            mqtt_topic,
            attempt + 1,
            max_retries,
        )

    _LOGGER.error("Failed to enable SetOption157 for %s after %d attempts", mqtt_topic, max_retries)
    return False


async def async_set_setoption157(hass: HomeAssistant, mqtt_topic: str, enable: bool) -> bool:
    """Set SetOption157 on Tasmota device via MQTT.

    Args:
        hass: Home Assistant instance
        mqtt_topic: The MQTT topic prefix for the device
        enable: True to enable (show NodeID), False to disable (mask NodeID)

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
