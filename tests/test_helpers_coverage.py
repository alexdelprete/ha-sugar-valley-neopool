"""Additional tests for helpers.py to boost coverage to 97%+.

This file targets specific uncovered code paths:
- normalize_nodeid
- is_masked_unique_id
- extract_entity_key_from_masked_unique_id
- is_nodeid_hashed
- classify_nodeid
- async_set_setoption157
- validate_nodeid masked pattern check
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.sugar_valley_neopool.helpers import (
    async_set_setoption157,
    classify_nodeid,
    extract_entity_key_from_masked_unique_id,
    is_masked_unique_id,
    is_nodeid_hashed,
    normalize_nodeid,
    parse_json_payload,
    validate_nodeid,
)
from homeassistant.core import HomeAssistant


class TestNormalizeNodeid:
    """Tests for normalize_nodeid function."""

    def test_removes_spaces(self) -> None:
        """Test spaces are removed."""
        result = normalize_nodeid("XXXX XXXX XXXX XXXX XXXX 3435")
        assert result == "XXXXXXXXXXXXXXXXXXXX3435"

    def test_converts_to_uppercase(self) -> None:
        """Test lowercase is converted to uppercase."""
        result = normalize_nodeid("abc123def")
        assert result == "ABC123DEF"

    def test_handles_none(self) -> None:
        """Test None returns empty string."""
        result = normalize_nodeid(None)
        assert result == ""

    def test_handles_empty_string(self) -> None:
        """Test empty string returns empty string."""
        result = normalize_nodeid("")
        assert result == ""

    def test_already_normalized(self) -> None:
        """Test already normalized NodeID stays unchanged."""
        result = normalize_nodeid("4C7525BFB344")
        assert result == "4C7525BFB344"

    def test_mixed_case_with_spaces(self) -> None:
        """Test mixed case with spaces."""
        result = normalize_nodeid("AbC 123 DeF")
        assert result == "ABC123DEF"


class TestIsMaskedUniqueId:
    """Tests for is_masked_unique_id function."""

    def test_masked_unique_id_lowercase(self) -> None:
        """Test lowercase xxxx pattern is detected."""
        result = is_masked_unique_id("neopool_mqtt_xxxx_xxxx_xxxx_ph_data")
        assert result is True

    def test_masked_unique_id_uppercase(self) -> None:
        """Test uppercase XXXX pattern is detected."""
        result = is_masked_unique_id("neopool_mqtt_XXXX_XXXX_XXXX_ph_data")
        assert result is True

    def test_masked_unique_id_mixed_case(self) -> None:
        """Test mixed case XxXx pattern is detected."""
        result = is_masked_unique_id("neopool_mqtt_XxXx_temp")
        assert result is True

    def test_real_unique_id(self) -> None:
        """Test real unique_id without XXXX is not masked."""
        result = is_masked_unique_id("neopool_mqtt_4C7525BFB344_ph_data")
        assert result is False

    def test_empty_string(self) -> None:
        """Test empty string is not masked."""
        result = is_masked_unique_id("")
        assert result is False

    def test_none(self) -> None:
        """Test None is not masked."""
        result = is_masked_unique_id(None)  # type: ignore[arg-type]
        assert result is False

    def test_partial_xxxx(self) -> None:
        """Test partial xxxx (less than 4 x's) is not masked."""
        result = is_masked_unique_id("neopool_mqtt_xxx_ph_data")
        assert result is False

    def test_xxxx_in_entity_key(self) -> None:
        """Test XXXX in entity key still counts as masked."""
        # Even if unlikely, the function checks entire string
        result = is_masked_unique_id("neopool_mqtt_ABC123_xxxx_sensor")
        assert result is True


class TestExtractEntityKeyFromMaskedUniqueId:
    """Tests for extract_entity_key_from_masked_unique_id function."""

    def test_extracts_simple_key(self) -> None:
        """Test extracting simple entity key."""
        unique_id = "neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_ph_data"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        assert result == "ph_data"

    def test_extracts_compound_key(self) -> None:
        """Test extracting compound entity key."""
        unique_id = "neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_hydrolysis_runtime_total"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        assert result == "hydrolysis_runtime_total"

    def test_handles_empty_string(self) -> None:
        """Test empty string returns None."""
        result = extract_entity_key_from_masked_unique_id("")
        assert result is None

    def test_handles_none(self) -> None:
        """Test None returns None."""
        result = extract_entity_key_from_masked_unique_id(None)  # type: ignore[arg-type]
        assert result is None

    def test_invalid_prefix(self) -> None:
        """Test wrong prefix returns None."""
        result = extract_entity_key_from_masked_unique_id("other_prefix_XXXX_key")
        assert result is None

    def test_no_underscore_after_nodeid(self) -> None:
        """Test unique_id with no entity key returns None."""
        result = extract_entity_key_from_masked_unique_id("neopool_mqtt_XXXX3435")
        assert result is None

    def test_extracts_water_temperature(self) -> None:
        """Test extracting water_temperature key."""
        unique_id = "neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_water_temperature"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        assert result == "water_temperature"

    def test_extracts_single_word_key(self) -> None:
        """Test extracting single word entity key."""
        unique_id = "neopool_mqtt_XXXX XXXX XXXX XXXX XXXX 3435_filtration"
        result = extract_entity_key_from_masked_unique_id(unique_id)
        assert result == "filtration"


class TestValidateNodeidMaskedPattern:
    """Additional tests for validate_nodeid masked pattern check."""

    def test_masked_nodeid_with_xxxx(self) -> None:
        """Test NodeID containing XXXX is invalid."""
        result = validate_nodeid("XXXX XXXX XXXX XXXX XXXX 3435")
        assert result is False

    def test_masked_nodeid_lowercase_xxxx(self) -> None:
        """Test NodeID containing lowercase xxxx is invalid."""
        result = validate_nodeid("xxxx xxxx xxxx")
        assert result is False

    def test_valid_hex_nodeid(self) -> None:
        """Test valid hex NodeID is valid."""
        result = validate_nodeid("4C7525BFB344")
        assert result is True

    def test_nodeid_with_partial_x(self) -> None:
        """Test NodeID with partial x's (not xxxx) is valid."""
        result = validate_nodeid("ABC123XXY456")  # Only XX, not XXXX
        assert result is True


class TestIsNodeidHashedHelpers:
    """Tests for is_nodeid_hashed function in helpers."""

    def test_aa55_prefix_is_hashed(self) -> None:
        """Test AA55 prefix NodeID is detected as hashed."""
        assert is_nodeid_hashed("AA55 1234 5678 9ABC DEF0 1234") is True

    def test_aa55_no_spaces(self) -> None:
        """Test AA55 prefix without spaces is hashed."""
        assert is_nodeid_hashed("AA551234567890AB") is True

    def test_real_nodeid_not_hashed(self) -> None:
        """Test real NodeID is not hashed."""
        assert is_nodeid_hashed("4C7525BFB344") is False

    def test_none_not_hashed(self) -> None:
        """Test None returns False."""
        assert is_nodeid_hashed(None) is False

    def test_empty_not_hashed(self) -> None:
        """Test empty string returns False."""
        assert is_nodeid_hashed("") is False


class TestClassifyNodeidHelpers:
    """Tests for classify_nodeid function in helpers."""

    def test_classify_real(self) -> None:
        """Test real NodeID classification."""
        assert classify_nodeid("4C7525BFB344") == "real"

    def test_classify_hashed(self) -> None:
        """Test hashed NodeID classification."""
        assert classify_nodeid("AA55 1234 5678 9ABC DEF0 1234") == "hashed"

    def test_classify_masked(self) -> None:
        """Test masked NodeID classification."""
        assert classify_nodeid("XXXX XXXX XXXX XXXX XXXX 3435") == "masked"

    def test_classify_none(self) -> None:
        """Test None classification."""
        assert classify_nodeid(None) == "invalid"

    def test_classify_hidden(self) -> None:
        """Test hidden classification."""
        assert classify_nodeid("hidden") == "invalid"


class TestAsyncSetSetoption157:
    """Tests for async_set_setoption157 function."""

    @pytest.mark.asyncio
    async def test_set_enable_sends_1(self, hass: HomeAssistant) -> None:
        """Test enabling sends '1' payload."""
        with patch(
            "homeassistant.components.mqtt.async_publish", new_callable=AsyncMock
        ) as mock_publish:
            result = await async_set_setoption157(hass, "SmartPool", enable=True)

        assert result is True
        mock_publish.assert_called_once_with(
            hass, "cmnd/SmartPool/SetOption157", "1", qos=1, retain=False
        )

    @pytest.mark.asyncio
    async def test_set_disable_sends_0(self, hass: HomeAssistant) -> None:
        """Test disabling sends '0' payload."""
        with patch(
            "homeassistant.components.mqtt.async_publish", new_callable=AsyncMock
        ) as mock_publish:
            result = await async_set_setoption157(hass, "SmartPool", enable=False)

        assert result is True
        mock_publish.assert_called_once_with(
            hass, "cmnd/SmartPool/SetOption157", "0", qos=1, retain=False
        )

    @pytest.mark.asyncio
    async def test_set_empty_topic_returns_false(self, hass: HomeAssistant) -> None:
        """Test empty topic returns False without publishing."""
        with patch(
            "homeassistant.components.mqtt.async_publish", new_callable=AsyncMock
        ) as mock_publish:
            result = await async_set_setoption157(hass, "", enable=True)

        assert result is False
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_publish_exception_returns_false(self, hass: HomeAssistant) -> None:
        """Test returns False when publish raises exception."""
        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
            side_effect=Exception("MQTT Error"),
        ):
            result = await async_set_setoption157(hass, "SmartPool", enable=True)

        assert result is False


class TestParseJsonPayloadBytearray:
    """Additional tests for parse_json_payload with bytearray."""

    def test_bytearray_payload(self) -> None:
        """Test bytearray payload is decoded correctly."""
        payload = bytearray(b'{"key": "value"}')
        result = parse_json_payload(payload)
        assert result == {"key": "value"}

    def test_unicode_decode_error(self) -> None:
        """Test invalid UTF-8 bytes return None."""
        # Invalid UTF-8 sequence
        payload = b"\xff\xfe"
        result = parse_json_payload(payload)
        assert result is None
