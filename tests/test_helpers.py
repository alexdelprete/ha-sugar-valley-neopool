"""Tests for Sugar Valley NeoPool helper functions."""

from __future__ import annotations

import pytest

from custom_components.sugar_valley_neopool.helpers import (
    bit_to_bool,
    clamp,
    get_nested_value,
    int_to_bool,
    lookup_by_value,
    parse_json_payload,
    parse_runtime_duration,
    safe_float,
    safe_int,
    validate_nodeid,
)


class TestGetNestedValue:
    """Tests for get_nested_value function."""

    def test_simple_path(self) -> None:
        """Test simple single-level path."""
        data = {"key": "value"}
        assert get_nested_value(data, "key") == "value"

    def test_nested_path(self) -> None:
        """Test nested dot notation path."""
        data = {"NeoPool": {"pH": {"Data": 7.2}}}
        assert get_nested_value(data, "NeoPool.pH.Data") == 7.2

    def test_deeply_nested_path(self) -> None:
        """Test deeply nested path."""
        data = {"a": {"b": {"c": {"d": {"e": 42}}}}}
        assert get_nested_value(data, "a.b.c.d.e") == 42

    def test_missing_key(self) -> None:
        """Test missing key returns None."""
        data = {"NeoPool": {"pH": {"Data": 7.2}}}
        assert get_nested_value(data, "NeoPool.Redox.Data") is None

    def test_missing_intermediate_key(self) -> None:
        """Test missing intermediate key returns None."""
        data = {"NeoPool": {"pH": {"Data": 7.2}}}
        assert get_nested_value(data, "NeoPool.Missing.Data") is None

    def test_array_access(self) -> None:
        """Test array index access."""
        data = {"Relay": {"State": [1, 0, 1, 0]}}
        assert get_nested_value(data, "Relay.State.0") == 1
        assert get_nested_value(data, "Relay.State.1") == 0
        assert get_nested_value(data, "Relay.State.2") == 1

    def test_array_out_of_bounds(self) -> None:
        """Test array out of bounds returns None."""
        data = {"Relay": {"State": [1, 0]}}
        assert get_nested_value(data, "Relay.State.5") is None

    def test_empty_data(self) -> None:
        """Test empty dictionary."""
        assert get_nested_value({}, "key") is None

    def test_none_value(self) -> None:
        """Test None value in path."""
        data = {"key": None}
        assert get_nested_value(data, "key") is None

    def test_non_dict_intermediate(self) -> None:
        """Test non-dict intermediate value returns None."""
        data = {"key": "string_value"}
        assert get_nested_value(data, "key.subkey") is None


class TestParseRuntimeDuration:
    """Tests for parse_runtime_duration function."""

    def test_valid_duration(self) -> None:
        """Test valid duration format."""
        # 123 days, 4 hours, 30 minutes = 123*24 + 4 + 30/60 = 2956.5
        result = parse_runtime_duration("123T04:30:00")
        assert result == 2956.5

    def test_zero_duration(self) -> None:
        """Test zero duration."""
        result = parse_runtime_duration("0T00:00:00")
        assert result == 0.0

    def test_hours_only(self) -> None:
        """Test hours only."""
        result = parse_runtime_duration("0T05:00:00")
        assert result == 5.0

    def test_days_only(self) -> None:
        """Test days only."""
        result = parse_runtime_duration("10T00:00:00")
        assert result == 240.0  # 10 * 24

    def test_with_seconds(self) -> None:
        """Test duration with seconds."""
        result = parse_runtime_duration("0T01:00:30")
        assert result == pytest.approx(1.0083, rel=0.01)

    def test_missing_t_separator(self) -> None:
        """Test missing T separator."""
        assert parse_runtime_duration("123:04:30:00") is None

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert parse_runtime_duration("") is None

    def test_none_value(self) -> None:
        """Test None value."""
        assert parse_runtime_duration(None) is None  # type: ignore[arg-type]

    def test_invalid_format(self) -> None:
        """Test invalid format."""
        assert parse_runtime_duration("invalid") is None

    def test_invalid_time_part(self) -> None:
        """Test invalid time part."""
        assert parse_runtime_duration("10Tinvalid") is None


class TestParseJsonPayload:
    """Tests for parse_json_payload function."""

    def test_valid_json_string(self) -> None:
        """Test valid JSON string."""
        result = parse_json_payload('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_bytes(self) -> None:
        """Test valid JSON bytes."""
        result = parse_json_payload(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_nested_json(self) -> None:
        """Test nested JSON."""
        payload = '{"NeoPool": {"pH": {"Data": 7.2}}}'
        result = parse_json_payload(payload)
        assert result == {"NeoPool": {"pH": {"Data": 7.2}}}

    def test_invalid_json(self) -> None:
        """Test invalid JSON returns None."""
        assert parse_json_payload("not valid json") is None

    def test_empty_string(self) -> None:
        """Test empty string returns None."""
        assert parse_json_payload("") is None

    def test_array_json(self) -> None:
        """Test JSON array."""
        result = parse_json_payload("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_unicode_json(self) -> None:
        """Test unicode JSON."""
        result = parse_json_payload('{"name": "Piscina"}')
        assert result == {"name": "Piscina"}


class TestLookupByValue:
    """Tests for lookup_by_value function."""

    def test_found_value(self) -> None:
        """Test finding key by value."""
        mapping = {0: "Off", 1: "On", 2: "Auto"}
        assert lookup_by_value(mapping, "On") == 1

    def test_not_found(self) -> None:
        """Test value not found returns None."""
        mapping = {0: "Off", 1: "On"}
        assert lookup_by_value(mapping, "Auto") is None

    def test_empty_mapping(self) -> None:
        """Test empty mapping."""
        assert lookup_by_value({}, "value") is None

    def test_first_match(self) -> None:
        """Test returns first match for duplicate values."""
        mapping = {0: "Same", 1: "Same"}
        result = lookup_by_value(mapping, "Same")
        assert result in (0, 1)


class TestBitToBool:
    """Tests for bit_to_bool function."""

    def test_string_one(self) -> None:
        """Test string '1' returns True."""
        assert bit_to_bool("1") is True

    def test_string_zero(self) -> None:
        """Test string '0' returns False."""
        assert bit_to_bool("0") is False

    def test_int_one(self) -> None:
        """Test int 1 returns True."""
        assert bit_to_bool(1) is True

    def test_int_zero(self) -> None:
        """Test int 0 returns False."""
        assert bit_to_bool(0) is False

    def test_other_value(self) -> None:
        """Test other values return None."""
        assert bit_to_bool(2) is None
        assert bit_to_bool("2") is None
        assert bit_to_bool("yes") is None


class TestIntToBool:
    """Tests for int_to_bool function."""

    def test_positive_int(self) -> None:
        """Test positive int returns True."""
        assert int_to_bool(1) is True
        assert int_to_bool(5) is True
        assert int_to_bool(100) is True

    def test_zero(self) -> None:
        """Test zero returns False."""
        assert int_to_bool(0) is False

    def test_negative(self) -> None:
        """Test negative returns False."""
        assert int_to_bool(-1) is False

    def test_string_number(self) -> None:
        """Test string number."""
        assert int_to_bool("5") is True
        assert int_to_bool("0") is False

    def test_invalid_value(self) -> None:
        """Test invalid value returns False."""
        assert int_to_bool("invalid") is False
        assert int_to_bool(None) is False


class TestSafeFloat:
    """Tests for safe_float function."""

    def test_valid_float(self) -> None:
        """Test valid float."""
        assert safe_float(3.14) == 3.14

    def test_valid_int(self) -> None:
        """Test int converts to float."""
        assert safe_float(5) == 5.0

    def test_valid_string(self) -> None:
        """Test string converts to float."""
        assert safe_float("7.2") == 7.2

    def test_none_no_default(self) -> None:
        """Test None returns None without default."""
        assert safe_float(None) is None

    def test_none_with_default(self) -> None:
        """Test None returns default."""
        assert safe_float(None, 0.0) == 0.0

    def test_invalid_no_default(self) -> None:
        """Test invalid returns None without default."""
        assert safe_float("invalid") is None

    def test_invalid_with_default(self) -> None:
        """Test invalid returns default."""
        assert safe_float("invalid", -1.0) == -1.0


class TestSafeInt:
    """Tests for safe_int function."""

    def test_valid_int(self) -> None:
        """Test valid int."""
        assert safe_int(42) == 42

    def test_valid_float(self) -> None:
        """Test float converts to int."""
        assert safe_int(3.7) == 3

    def test_valid_string(self) -> None:
        """Test string converts to int."""
        assert safe_int("100") == 100

    def test_float_string(self) -> None:
        """Test float string converts to int."""
        assert safe_int("3.9") == 3

    def test_none_no_default(self) -> None:
        """Test None returns None without default."""
        assert safe_int(None) is None

    def test_none_with_default(self) -> None:
        """Test None returns default."""
        assert safe_int(None, 0) == 0

    def test_invalid_no_default(self) -> None:
        """Test invalid returns None without default."""
        assert safe_int("invalid") is None

    def test_invalid_with_default(self) -> None:
        """Test invalid returns default."""
        assert safe_int("invalid", -1) == -1


class TestClamp:
    """Tests for clamp function."""

    def test_value_in_range(self) -> None:
        """Test value in range stays unchanged."""
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_value_below_min(self) -> None:
        """Test value below min returns min."""
        assert clamp(-5.0, 0.0, 10.0) == 0.0

    def test_value_above_max(self) -> None:
        """Test value above max returns max."""
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_value_at_min(self) -> None:
        """Test value at min."""
        assert clamp(0.0, 0.0, 10.0) == 0.0

    def test_value_at_max(self) -> None:
        """Test value at max."""
        assert clamp(10.0, 0.0, 10.0) == 10.0


class TestValidateNodeid:
    """Tests for validate_nodeid function."""

    def test_valid_nodeid(self) -> None:
        """Test valid NodeID."""
        assert validate_nodeid("ABC123") is True
        assert validate_nodeid("12345") is True
        assert validate_nodeid("node-1") is True

    def test_none(self) -> None:
        """Test None returns False."""
        assert validate_nodeid(None) is False

    def test_empty_string(self) -> None:
        """Test empty string returns False."""
        assert validate_nodeid("") is False

    def test_hidden(self) -> None:
        """Test 'hidden' returns False."""
        assert validate_nodeid("hidden") is False
        assert validate_nodeid("Hidden") is False
        assert validate_nodeid("HIDDEN") is False

    def test_hidden_by_default(self) -> None:
        """Test 'hidden_by_default' returns False."""
        assert validate_nodeid("hidden_by_default") is False
        assert validate_nodeid("Hidden_By_Default") is False
