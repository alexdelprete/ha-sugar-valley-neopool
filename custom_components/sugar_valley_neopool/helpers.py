"""Helper functions for NeoPool MQTT integration."""

from __future__ import annotations

import json
import logging
from typing import Any, overload

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


def parse_json_payload(payload: str | bytes) -> dict[str, Any] | None:
    """Parse MQTT JSON payload safely."""
    try:
        if isinstance(payload, bytes):
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
    """Validate NodeID is present and not 'hidden'.

    Args:
        nodeid: The NodeID value to validate.

    Returns:
        True if NodeID is valid (present and not hidden), False otherwise.
    """
    if nodeid is None or nodeid == "":
        return False
    if isinstance(nodeid, str) and nodeid.lower() in ["hidden", "hidden_by_default"]:
        return False
    return True
