"""Tests for NeoPool light platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import CMD_LIGHT
from custom_components.sugar_valley_neopool.light import NeoPoolLight, async_setup_entry
from homeassistant.components.light import ColorMode


class TestNeoPoolLight:
    """Tests for the NeoPoolLight entity."""

    def test_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test light initialization and on/off color mode."""
        light = NeoPoolLight(mock_config_entry)

        assert light._attr_unique_id == "neopool_mqtt_ABC123_light"
        assert light._attr_is_on is None
        assert light.color_mode == ColorMode.ONOFF
        assert light.supported_color_modes == {ColorMode.ONOFF}

    @pytest.mark.asyncio
    async def test_turn_on(self, mock_config_entry: MagicMock, mock_hass: MagicMock) -> None:
        """Test light turn on publishes NPLight 1."""
        light = NeoPoolLight(mock_config_entry)
        light.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await light.async_turn_on()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_LIGHT}",
                "1",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_config_entry: MagicMock, mock_hass: MagicMock) -> None:
        """Test light turn off publishes NPLight 0."""
        light = NeoPoolLight(mock_config_entry)
        light.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await light.async_turn_off()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_LIGHT}",
                "0",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_state_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test light state updates from a SENSOR message."""
        light = NeoPoolLight(mock_config_entry)
        light.hass = mock_hass
        light.entity_id = "light.neopool_light"
        light.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await light.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Light": 1}})
        sensor_callback(mock_msg)

        assert light._attr_is_on is True
        assert light._attr_available is True

    @pytest.mark.asyncio
    async def test_state_missing_path(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test light becomes unavailable when the Light key is absent."""
        light = NeoPoolLight(mock_config_entry)
        light.hass = mock_hass
        light.entity_id = "light.neopool_light"
        light.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await light.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Other": "data"}})
        sensor_callback(mock_msg)

        assert light._attr_is_on is None
        assert light._attr_available is False


class TestAsyncSetupEntry:
    """Tests for the light platform setup."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_light(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates a single light entity."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        assert len(added_entities) == 1
        assert isinstance(added_entities[0], NeoPoolLight)


class TestNeoPoolLightEdges:
    """Edge-case coverage for the light platform."""

    @pytest.mark.asyncio
    async def test_invalid_payload_ignored(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """A non-JSON SENSOR payload is ignored without raising."""
        light = NeoPoolLight(mock_config_entry)
        light.hass = mock_hass
        light.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await light.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = "not json {{{"
        sensor_callback(mock_msg)  # must not raise
        assert light._attr_is_on is None
