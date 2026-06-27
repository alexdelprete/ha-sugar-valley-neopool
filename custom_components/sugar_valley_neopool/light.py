"""Light platform for NeoPool MQTT integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback

from .const import CMD_LIGHT, JSON_PATH_LIGHT
from .entity import NeoPoolMQTTEntity
from .helpers import bit_to_bool, get_nested_value, parse_json_payload

if TYPE_CHECKING:
    from homeassistant.components import mqtt
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the NeoPool light based on a config entry."""
    _LOGGER.debug("Setting up NeoPool light")

    async_add_entities([NeoPoolLight(entry)])
    _LOGGER.info("Added NeoPool light")


class NeoPoolLight(NeoPoolMQTTEntity, LightEntity):
    """Representation of the NeoPool pool light.

    The controller exposes the light as a simple on/off relay, so the entity
    is an on/off-only light. State arrives via SENSOR telemetry; on/off is
    commanded with NPLight. Confirmation comes from the immediate SENSOR echo
    (the controller pushes a SENSOR message right after a relay change), so no
    register read-back is needed.
    """

    _attr_translation_key = "light"
    _attr_name = "Light"
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, config_entry: NeoPoolConfigEntry) -> None:
        """Initialize the light."""
        super().__init__(config_entry, "light")
        # Set on the instance (not class) to satisfy both RUF012 and the
        # LightEntity instance-attribute contract.
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topic when entity is added."""
        await super().async_added_to_hass()

        sensor_topic = f"tele/{self.mqtt_topic}/SENSOR"

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle new MQTT message."""
            payload = parse_json_payload(msg.payload)
            if payload is None:
                return

            raw_value = get_nested_value(payload, JSON_PATH_LIGHT)
            if raw_value is None:
                self._attr_is_on = None
                self._attr_available = False
                self.async_write_ha_state()
                return

            self._attr_is_on = bit_to_bool(raw_value)
            self._attr_available = True
            self.async_write_ha_state()

        await self._subscribe_topic(sensor_topic, message_received)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._publish_command(CMD_LIGHT, "1")
        _LOGGER.debug("Turned on NeoPool light")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._publish_command(CMD_LIGHT, "0")
        _LOGGER.debug("Turned off NeoPool light")
