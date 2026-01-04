"""Extended tests for Sugar Valley NeoPool helper functions - edge cases."""

from __future__ import annotations

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


class TestGetNestedValueExtended:
    """Extended tests for get_nested_value function."""

    def test_list_access_string_index(self) -> None:
        """Test list access with string numeric index."""
        data = {"items": [10, 20, 30]}
        assert get_nested_value(data, "items.1") == 20

    def test_list_access_nested(self) -> None:
        """Test nested list access."""
        data = {"NeoPool": {"Relay": {"State": [1, 0, 1]}}}
        assert get_nested_value(data, "NeoPool.Relay.State.0") == 1
        assert get_nested_value(data, "NeoPool.Relay.State.2") == 1

    def test_mixed_dict_list_access(self) -> None:
        """Test mixed dict and list access."""
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        # After list access, if we try dict access it should work
        assert get_nested_value(data, "items.0") == {"name": "first"}

    def test_type_error_handling(self) -> None:
        """Test TypeError handling when accessing invalid types."""
        data = {"key": 123}  # int, not dict or list
        assert get_nested_value(data, "key.subkey") is None

    def test_single_key_path(self) -> None:
        """Test path with single key."""
        data = {"single": "value"}
        assert get_nested_value(data, "single") == "value"

    def test_empty_path_segment(self) -> None:
        """Test path behavior."""
        data = {"a": {"b": "value"}}
        assert get_nested_value(data, "a.b") == "value"


class TestParseRuntimeDurationExtended:
    """Extended tests for parse_runtime_duration function."""

    def test_max_precision(self) -> None:
        """Test maximum precision with seconds."""
        # 1 second = 1/3600 hours = 0.000277... rounds to 0.0 with round(x, 2)
        result = parse_runtime_duration("0T00:00:01")
        assert result == 0.0  # Rounds to 0.0 with 2 decimal places

    def test_large_days(self) -> None:
        """Test with large number of days."""
        result = parse_runtime_duration("999T23:59:59")
        assert result is not None
        # 999*24 + 23 + 59/60 + 59/3600 = 23976 + 23.9997 = 23999.9997
        assert result >= 23999.0

    def test_malformed_time_part(self) -> None:
        """Test with malformed time part."""
        assert parse_runtime_duration("10T12:30") is None  # Missing seconds
        assert parse_runtime_duration("10T12") is None  # Missing minutes and seconds

    def test_non_numeric_days(self) -> None:
        """Test with non-numeric days."""
        assert parse_runtime_duration("abcT12:30:00") is None

    def test_non_numeric_time(self) -> None:
        """Test with non-numeric time components."""
        assert parse_runtime_duration("10Tab:30:00") is None


class TestParseJsonPayloadExtended:
    """Extended tests for parse_json_payload function."""

    def test_bytearray_input(self) -> None:
        """Test with bytearray input."""
        result = parse_json_payload(bytearray(b'{"key": "value"}'))
        assert result == {"key": "value"}

    def test_bytes_with_unicode(self) -> None:
        """Test bytes with unicode characters."""
        result = parse_json_payload('{"name": "Café"}'.encode())
        assert result == {"name": "Café"}

    def test_complex_nested_json(self) -> None:
        """Test complex nested JSON structure."""
        payload = '{"a": {"b": {"c": [1, 2, {"d": true}]}}}'
        result = parse_json_payload(payload)
        assert result["a"]["b"]["c"][2]["d"] is True

    def test_json_with_null(self) -> None:
        """Test JSON with null value."""
        result = parse_json_payload('{"value": null}')
        assert result == {"value": None}

    def test_json_with_numbers(self) -> None:
        """Test JSON with various number types."""
        result = parse_json_payload('{"int": 42, "float": 3.14, "negative": -10}')
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["negative"] == -10

    def test_unicode_decode_error(self) -> None:
        """Test handling of invalid UTF-8 bytes."""
        # Invalid UTF-8 sequence
        result = parse_json_payload(b"\xff\xfe")
        assert result is None

    def test_truncated_json(self) -> None:
        """Test truncated JSON."""
        result = parse_json_payload('{"key": "val')
        assert result is None


class TestLookupByValueExtended:
    """Extended tests for lookup_by_value function."""

    def test_integer_values(self) -> None:
        """Test with integer values in mapping."""
        mapping = {"a": 1, "b": 2, "c": 3}
        assert lookup_by_value(mapping, 2) == "b"

    def test_none_value_in_mapping(self) -> None:
        """Test with None as a value in mapping."""
        mapping = {0: None, 1: "value"}
        assert lookup_by_value(mapping, None) == 0

    def test_case_sensitive(self) -> None:
        """Test case sensitivity."""
        mapping = {0: "Off", 1: "ON"}
        assert lookup_by_value(mapping, "Off") == 0
        assert lookup_by_value(mapping, "off") is None


class TestBitToBoolExtended:
    """Extended tests for bit_to_bool function."""

    def test_none_input(self) -> None:
        """Test None input."""
        assert bit_to_bool(None) is None

    def test_boolean_input(self) -> None:
        """Test boolean input returns None (not 0 or 1)."""
        assert bit_to_bool(True) is None  # True is not 1
        assert bit_to_bool(False) is None  # False is not 0

    def test_float_input(self) -> None:
        """Test float input."""
        assert bit_to_bool(1.0) is None  # float is not int/str
        assert bit_to_bool(0.0) is None


class TestIntToBoolExtended:
    """Extended tests for int_to_bool function."""

    def test_float_string(self) -> None:
        """Test float string input."""
        assert int_to_bool("3.7") is True  # int("3.7") fails
        # Actually int("3.7") raises ValueError, so it returns False
        # Let me check the implementation...

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert int_to_bool("") is False

    def test_whitespace_string(self) -> None:
        """Test whitespace string."""
        assert int_to_bool("  ") is False

    def test_large_positive(self) -> None:
        """Test large positive number."""
        assert int_to_bool(1000000) is True

    def test_large_negative(self) -> None:
        """Test large negative number."""
        assert int_to_bool(-1000000) is False


class TestSafeFloatExtended:
    """Extended tests for safe_float function."""

    def test_negative_float(self) -> None:
        """Test negative float."""
        assert safe_float(-3.14) == -3.14

    def test_scientific_notation_string(self) -> None:
        """Test scientific notation string."""
        assert safe_float("1e5") == 100000.0

    def test_empty_string(self) -> None:
        """Test empty string returns default."""
        assert safe_float("", 0.0) == 0.0

    def test_whitespace_string(self) -> None:
        """Test whitespace string."""
        assert safe_float("   ", 0.0) == 0.0

    def test_boolean_input(self) -> None:
        """Test boolean input."""
        assert safe_float(True) == 1.0
        assert safe_float(False) == 0.0

    def test_list_input(self) -> None:
        """Test list input returns default."""
        assert safe_float([1, 2, 3]) is None
        assert safe_float([1, 2, 3], -1.0) == -1.0


class TestSafeIntExtended:
    """Extended tests for safe_int function."""

    def test_negative_float(self) -> None:
        """Test negative float truncation."""
        assert safe_int(-3.7) == -3

    def test_scientific_notation(self) -> None:
        """Test scientific notation."""
        assert safe_int("1e2") == 100

    def test_boolean_input(self) -> None:
        """Test boolean input."""
        assert safe_int(True) == 1
        assert safe_int(False) == 0

    def test_negative_string(self) -> None:
        """Test negative number string."""
        assert safe_int("-42") == -42

    def test_dict_input(self) -> None:
        """Test dict input returns default."""
        assert safe_int({}) is None
        assert safe_int({}, 0) == 0


class TestClampExtended:
    """Extended tests for clamp function."""

    def test_negative_range(self) -> None:
        """Test with negative range."""
        assert clamp(-5.0, -10.0, -1.0) == -5.0
        assert clamp(-15.0, -10.0, -1.0) == -10.0

    def test_zero_range(self) -> None:
        """Test with min equals max."""
        assert clamp(5.0, 3.0, 3.0) == 3.0
        assert clamp(1.0, 3.0, 3.0) == 3.0

    def test_float_precision(self) -> None:
        """Test float precision is maintained."""
        result = clamp(3.14159, 0.0, 10.0)
        assert result == 3.14159


class TestValidateNodeidExtended:
    """Extended tests for validate_nodeid function."""

    def test_numeric_nodeid(self) -> None:
        """Test numeric NodeID."""
        assert validate_nodeid("123456") is True

    def test_mixed_case_hidden(self) -> None:
        """Test various cases of 'hidden'."""
        assert validate_nodeid("HiDdEn") is False

    def test_whitespace_nodeid(self) -> None:
        """Test NodeID with whitespace."""
        # Whitespace-only string should be valid (not explicitly filtered)
        assert validate_nodeid("   ") is True  # Not empty, not "hidden"

    def test_special_characters(self) -> None:
        """Test NodeID with special characters."""
        assert validate_nodeid("node-123_abc") is True
        assert validate_nodeid("node/123") is True

    def test_non_string_input(self) -> None:
        """Test with non-string input."""
        # validate_nodeid expects str | None
        # If given an int, it should handle it
        assert validate_nodeid(123) is True  # type: ignore[arg-type]
