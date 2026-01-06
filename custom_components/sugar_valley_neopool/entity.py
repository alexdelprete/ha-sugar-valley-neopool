"""Base entity for NeoPool MQTT integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import NeoPoolConfigEntry, get_device_info
from .const import PAYLOAD_ONLINE

_LOGGER = logging.getLogger(__name__)


class NeoPoolEntity(Entity):
    """Base class for NeoPool entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        self._config_entry = config_entry
        self._entity_key = entity_key
        # NodeID-based pattern: neopool_mqtt_{nodeid}_{entity_key}
        nodeid = config_entry.runtime_data.nodeid
        self._attr_unique_id = f"neopool_mqtt_{nodeid}_{entity_key}"
        self._attr_device_info = get_device_info(config_entry)
        self._attr_available = False
        # Note: entity_id_mapping is applied in __init__.py after entity creation
        # via _apply_entity_id_mapping() to preserve original YAML entity IDs

    @property
    def mqtt_topic(self) -> str:
        """Return the MQTT topic prefix for this device."""
        return self._config_entry.data.get("discovery_prefix", "")


class NeoPoolMQTTEntity(NeoPoolEntity):
    """Base class for NeoPool MQTT entities with subscription support."""

    _unsubscribe_callbacks: list[Any]

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        entity_key: str,
    ) -> None:
        """Initialize the MQTT entity."""
        super().__init__(config_entry, entity_key)
        self._unsubscribe_callbacks = []

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when entity is added."""
        await super().async_added_to_hass()

        # Subscribe to availability topic (LWT)
        mqtt_topic = self.mqtt_topic
        lwt_topic = f"tele/{mqtt_topic}/LWT"

        @callback
        def availability_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle availability message."""
            self._attr_available = msg.payload == PAYLOAD_ONLINE
            self.async_write_ha_state()

        unsubscribe = await mqtt.async_subscribe(self.hass, lwt_topic, availability_received, qos=1)
        self._unsubscribe_callbacks.append(unsubscribe)

        _LOGGER.debug(
            "Subscribed to availability topic: %s for %s",
            lwt_topic,
            self.entity_id,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT topics when entity is removed."""
        for unsubscribe in self._unsubscribe_callbacks:
            unsubscribe()
        self._unsubscribe_callbacks.clear()

        _LOGGER.debug("Unsubscribed from MQTT topics for %s", self.entity_id)

    async def _subscribe_topic(
        self,
        topic: str,
        msg_callback: Callable[[mqtt.ReceiveMessage], None],
        qos: int = 1,
    ) -> None:
        """Subscribe to an MQTT topic."""
        unsubscribe = await mqtt.async_subscribe(self.hass, topic, msg_callback, qos=qos)
        self._unsubscribe_callbacks.append(unsubscribe)
        _LOGGER.debug("Subscribed to topic: %s for %s", topic, self.entity_id)

    async def _publish_command(
        self,
        command: str,
        payload: str,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Publish a command to MQTT."""
        mqtt_topic = self.mqtt_topic
        topic = f"cmnd/{mqtt_topic}/{command}"

        await mqtt.async_publish(
            self.hass,
            topic,
            payload,
            qos=qos,
            retain=retain,
        )
        _LOGGER.debug(
            "Published command: %s = %s to %s",
            command,
            payload,
            topic,
        )
