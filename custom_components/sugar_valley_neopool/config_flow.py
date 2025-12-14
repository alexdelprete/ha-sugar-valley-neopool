"""Config flow for NeoPool MQTT integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.mqtt import valid_subscribe_topic
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_DEVICE_NAME, CONF_DISCOVERY_PREFIX, DEFAULT_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): cv.string,
        vol.Required(CONF_DISCOVERY_PREFIX, default="SmartPool"): cv.string,
    }
)


class NeoPoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NeoPool MQTT."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_prefix: str | None = None
        self._device_name: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME]
            discovery_prefix = user_input[CONF_DISCOVERY_PREFIX]

            # Validate MQTT topic format
            try:
                valid_subscribe_topic(f"tele/{discovery_prefix}/SENSOR")
            except vol.Invalid:
                errors["base"] = "invalid_topic"

            if not errors:
                # Check for duplicate entries
                await self.async_set_unique_id(f"{DOMAIN}_{discovery_prefix}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_DEVICE_NAME: device_name,
                        CONF_DISCOVERY_PREFIX: discovery_prefix,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"docs_url": "https://tasmota.github.io/docs/NeoPool/"},
        )

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> ConfigFlowResult:
        """Handle MQTT discovery.

        This is triggered when a device publishes to a topic matching
        the pattern defined in manifest.json mqtt key.
        """
        _LOGGER.debug("MQTT Discovery: topic=%s", discovery_info.topic)

        # Extract device name from topic
        # Expected format: tele/{device}/SENSOR
        topic_parts = discovery_info.topic.split("/")
        if len(topic_parts) >= 3 and topic_parts[0] == "tele":
            device_topic = topic_parts[1]
        else:
            return self.async_abort(reason="invalid_discovery_info")

        # Check if this looks like NeoPool data
        try:
            payload = json.loads(discovery_info.payload)
            if "NeoPool" not in payload:
                return self.async_abort(reason="not_neopool_device")
        except (json.JSONDecodeError, TypeError):
            return self.async_abort(reason="invalid_discovery_info")

        # Store discovery info
        self._discovery_prefix = device_topic
        self._device_name = f"NeoPool {device_topic}"

        # Set unique ID to prevent duplicate discoveries
        await self.async_set_unique_id(f"{DOMAIN}_{device_topic}")
        self._abort_if_unique_id_configured()

        # Show confirmation form
        return await self.async_step_mqtt_confirm()

    async def async_step_mqtt_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm MQTT discovery."""
        if user_input is not None:
            device_name = (
                user_input.get(CONF_DEVICE_NAME, self._device_name)
                or self._device_name
                or DEFAULT_DEVICE_NAME
            )
            discovery_prefix = self._discovery_prefix or ""
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_DEVICE_NAME: device_name,
                    CONF_DISCOVERY_PREFIX: discovery_prefix,
                },
            )

        return self.async_show_form(
            step_id="mqtt_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_NAME, default=self._device_name): cv.string,
                }
            ),
            description_placeholders={
                "device": self._discovery_prefix or "",
            },
        )
