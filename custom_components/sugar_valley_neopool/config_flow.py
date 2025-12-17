"""Config flow for NeoPool MQTT integration."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import valid_subscribe_topic
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_MIGRATE_YAML,
    CONF_NODEID,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
)
from .helpers import get_nested_value, validate_nodeid

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
        self._nodeid: str | None = None
        self._yaml_topic: str | None = None
        self._migrate_yaml: bool = False

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - ask about YAML migration first."""
        return await self.async_step_yaml_migration()

    async def async_step_yaml_migration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask if user is migrating from YAML package."""
        if user_input is not None:
            self._migrate_yaml = user_input.get(CONF_MIGRATE_YAML, False)

            if self._migrate_yaml:
                # Ask for YAML topic
                return await self.async_step_yaml_topic()
            # No migration needed, continue with normal flow
            return await self.async_step_discover_device()

        return self.async_show_form(
            step_id="yaml_migration",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MIGRATE_YAML, default=False): cv.boolean,
                }
            ),
            description_placeholders={
                "info": "Check this if you're currently using the YAML package configuration"
            },
        )

    async def async_step_yaml_topic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get and validate YAML topic."""
        errors: dict[str, str] = {}

        if user_input is not None:
            yaml_topic = user_input.get("yaml_topic", "SmartPool")

            # Validate YAML topic by trying to read from it
            validation_result = await self._validate_yaml_topic(yaml_topic)

            if validation_result["valid"]:
                self._yaml_topic = yaml_topic
                self._discovery_prefix = yaml_topic

                # Extract NodeID from validation result
                nodeid = validation_result.get("nodeid")

                # If NodeID is hidden, auto-configure Tasmota
                if not validate_nodeid(nodeid):
                    config_result = await self._auto_configure_nodeid(yaml_topic)
                    if not config_result["success"]:
                        return self.async_abort(
                            reason="nodeid_configuration_failed",
                            description_placeholders={
                                "error": config_result.get("error", "Failed to enable NodeID")
                            },
                        )
                    nodeid = config_result["nodeid"]

                self._nodeid = nodeid

                # Continue to device name confirmation
                return await self.async_step_yaml_confirm()
            errors["yaml_topic"] = "invalid_yaml_topic"

        return self.async_show_form(
            step_id="yaml_topic",
            data_schema=vol.Schema(
                {
                    vol.Required("yaml_topic", default="SmartPool"): cv.string,
                }
            ),
            errors=errors,
            description_placeholders={
                "info": "Enter the MQTT topic used in your YAML configuration (default: SmartPool)"
            },
        )

    async def async_step_yaml_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm YAML migration setup."""
        if user_input is not None:
            device_name = user_input.get(CONF_DEVICE_NAME, f"NeoPool {self._yaml_topic}")

            # Set unique ID based on NodeID
            await self.async_set_unique_id(f"{DOMAIN}_{self._nodeid}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_DEVICE_NAME: device_name,
                    CONF_DISCOVERY_PREFIX: self._yaml_topic,
                    CONF_NODEID: self._nodeid,
                    CONF_MIGRATE_YAML: True,
                },
            )

        return self.async_show_form(
            step_id="yaml_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_NAME, default=f"NeoPool {self._yaml_topic}"
                    ): cv.string,
                }
            ),
            description_placeholders={
                "topic": self._yaml_topic or "",
                "nodeid": self._nodeid or "",
            },
        )

    async def async_step_discover_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device discovery."""
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
                # Try to read from the topic to get NodeID
                validation_result = await self._validate_yaml_topic(discovery_prefix)

                if not validation_result["valid"]:
                    errors["base"] = "cannot_connect"
                else:
                    nodeid = validation_result.get("nodeid")

                    # If NodeID is hidden, auto-configure Tasmota
                    if not validate_nodeid(nodeid):
                        config_result = await self._auto_configure_nodeid(discovery_prefix)
                        if not config_result["success"]:
                            return self.async_abort(
                                reason="nodeid_configuration_failed",
                                description_placeholders={
                                    "error": config_result.get("error", "Failed to enable NodeID")
                                },
                            )
                        nodeid = config_result["nodeid"]

                    # Set unique ID and check for duplicates
                    await self.async_set_unique_id(f"{DOMAIN}_{nodeid}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_name,
                        data={
                            CONF_DEVICE_NAME: device_name,
                            CONF_DISCOVERY_PREFIX: discovery_prefix,
                            CONF_NODEID: nodeid,
                        },
                    )

        return self.async_show_form(
            step_id="discover_device",
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

        # Extract NodeID from payload
        nodeid = get_nested_value(payload, "NeoPool.Powerunit.NodeID")

        # If NodeID is hidden, auto-configure Tasmota
        if not validate_nodeid(nodeid):
            config_result = await self._auto_configure_nodeid(device_topic)
            if not config_result["success"]:
                return self.async_abort(
                    reason="nodeid_configuration_failed",
                    description_placeholders={
                        "error": config_result.get("error", "Failed to enable NodeID")
                    },
                )
            nodeid = config_result["nodeid"]

        # Store discovery info and NodeID
        self._discovery_prefix = device_topic
        self._device_name = f"NeoPool {device_topic}"
        self._nodeid = nodeid

        # Set unique ID based on NodeID to prevent duplicate discoveries
        await self.async_set_unique_id(f"{DOMAIN}_{nodeid}")
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
                    CONF_NODEID: self._nodeid,
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

    async def _validate_yaml_topic(self, topic: str, timeout_seconds: int = 10) -> dict[str, Any]:
        """Validate YAML topic by subscribing and waiting for message.

        Returns dict with 'valid' boolean and optionally 'nodeid' and 'payload'.
        """
        result: dict[str, Any] = {"valid": False}
        event = asyncio.Event()

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            nonlocal result
            try:
                payload = json.loads(msg.payload)
                if "NeoPool" in payload:
                    result["valid"] = True
                    result["payload"] = payload
                    result["nodeid"] = get_nested_value(payload, "NeoPool.Powerunit.NodeID")
                    event.set()
            except (json.JSONDecodeError, TypeError):
                pass

        # Subscribe to YAML topic
        sensor_topic = f"tele/{topic}/SENSOR"
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            sensor_topic,
            message_received,
            qos=1,
        )

        try:
            # Wait for message or timeout
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for message from YAML topic: %s", sensor_topic)
        finally:
            unsubscribe()

        return result

    async def _auto_configure_nodeid(self, device_topic: str) -> dict[str, Any]:
        """Auto-configure Tasmota SetOption157 to enable NodeID.

        Returns dict with 'success' boolean and optionally 'nodeid' or 'error'.
        """
        _LOGGER.warning("NodeID is hidden. Attempting to configure Tasmota with SetOption157 1")

        # Publish command to enable NodeID
        await mqtt.async_publish(
            self.hass,
            f"cmnd/{device_topic}/SetOption157",
            "1",
            qos=1,
            retain=False,
        )

        # Wait for Tasmota to process and republish
        await asyncio.sleep(2)

        # Try to get NodeID again from next MQTT message
        nodeid = await self._wait_for_nodeid(device_topic)

        if not validate_nodeid(nodeid):
            return {
                "success": False,
                "error": "Failed to enable NodeID. Please manually set SetOption157 1 in Tasmota console",
            }

        _LOGGER.info("Successfully configured Tasmota SetOption157 1. NodeID: %s", nodeid)
        return {"success": True, "nodeid": nodeid}

    async def _wait_for_nodeid(self, device_topic: str, timeout_seconds: int = 10) -> str | None:
        """Wait for NodeID to appear in MQTT message."""
        received_nodeid: str | None = None
        event = asyncio.Event()

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            nonlocal received_nodeid
            try:
                payload = json.loads(msg.payload)
                nodeid = get_nested_value(payload, "NeoPool.Powerunit.NodeID")
                if validate_nodeid(nodeid):
                    received_nodeid = nodeid
                    event.set()
            except (json.JSONDecodeError, TypeError):
                pass

        # Subscribe to sensor topic
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            f"tele/{device_topic}/SENSOR",
            message_received,
            qos=1,
        )

        try:
            # Wait for NodeID or timeout
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for NodeID from Tasmota")
        finally:
            unsubscribe()

        return received_nodeid
