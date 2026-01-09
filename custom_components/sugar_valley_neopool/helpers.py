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


async def async_query_setoption157(hass: HomeAssistant, mqtt_topic: str) -> bool | None:
    """Query SetOption157 status from Tasmota via MQTT.

    Shared helper function used by ConfigFlow, OptionsFlow, and migration.

    Note: Tasmota can respond on different topics depending on SetOption4:
    - SetOption4 OFF (default): Response on stat/{topic}/RESULT
    - SetOption4 ON: Response on stat/{topic}/SETOPTION157

    We subscribe to both topics to handle either configuration.

    Args:
        hass: Home Assistant instance
        mqtt_topic: The MQTT topic prefix for the device

    Returns:
        True if enabled, False if disabled, None if query failed.
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
        """Handle SetOption157 response."""
        nonlocal result
        try:
            # Handle bytes/bytearray payload
            if isinstance(msg.payload, (bytes, bytearray)):
                payload_str = msg.payload.decode("utf-8")
            else:
                payload_str = msg.payload

            payload = json.loads(payload_str)
            _LOGGER.debug("Received MQTT message on %s: %s", msg.topic, payload)
            # Response format: {"SetOption157":"ON"} or {"SetOption157":"OFF"}
            so157_value = payload.get("SetOption157")
            if so157_value is not None:
                result = str(so157_value).upper() == "ON"
                _LOGGER.debug("SetOption157 status for %s: %s", mqtt_topic, result)
                event.set()
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse SetOption157 response: %s", err)

    # Subscribe to both possible response topics:
    # 1. stat/{topic}/RESULT - default Tasmota behavior (SetOption4 OFF)
    # 2. stat/{topic}/SETOPTION157 - when SetOption4 ON (differentiated topics)
    result_topic = f"stat/{mqtt_topic}/RESULT"
    setoption_topic = f"stat/{mqtt_topic}/SETOPTION157"

    _LOGGER.debug(
        "Subscribing to %s and %s for SetOption157 response",
        result_topic,
        setoption_topic,
    )

    unsubscribe_result = await mqtt.async_subscribe(hass, result_topic, message_received, qos=1)
    unsubscribe_setoption = await mqtt.async_subscribe(
        hass, setoption_topic, message_received, qos=1
    )

    try:
        # Small delay to ensure subscriptions are established before publishing
        # This addresses a race condition where the response arrives before
        # the subscriptions are fully ready
        await asyncio.sleep(0.2)

        # Send query command (empty payload queries current value)
        command_topic = f"cmnd/{mqtt_topic}/SetOption157"
        _LOGGER.debug("Publishing SetOption157 query to %s", command_topic)
        await mqtt.async_publish(hass, command_topic, "", qos=1, retain=False)

        # Wait for response with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=5.0)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for SetOption157 response from %s", mqtt_topic)
    finally:
        unsubscribe_result()
        unsubscribe_setoption()

    return result


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
