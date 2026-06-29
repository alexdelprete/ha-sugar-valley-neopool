"""Config flow for NeoPool MQTT integration."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import valid_subscribe_topic
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.util import slugify

from .const import (
    CONF_CONFIRM_MIGRATION,
    CONF_CONNECTION_ERROR_RATE_THRESHOLD,
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_ENABLE_REPAIR_NOTIFICATION,
    CONF_FAILURES_THRESHOLD,
    CONF_MIGRATE_YAML,
    CONF_NODEID,
    CONF_OFFLINE_TIMEOUT,
    CONF_PUMP_TYPE,
    CONF_RECOVERY_SCRIPT,
    CONF_REGENERATE_ENTITY_IDS,
    CONF_UNIQUE_ID_PREFIX,
    DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD,
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENABLE_REPAIR_NOTIFICATION,
    DEFAULT_FAILURES_THRESHOLD,
    DEFAULT_MQTT_TOPIC,
    DEFAULT_OFFLINE_TIMEOUT,
    DEFAULT_PUMP_TYPE,
    DEFAULT_RECOVERY_SCRIPT,
    DEFAULT_UNIQUE_ID_PREFIX,
    DOMAIN,
    MAX_CONNECTION_ERROR_RATE_THRESHOLD,
    MAX_FAILURES_THRESHOLD,
    MAX_OFFLINE_TIMEOUT,
    MIN_CONNECTION_ERROR_RATE_THRESHOLD,
    MIN_FAILURES_THRESHOLD,
    MIN_OFFLINE_TIMEOUT,
    PUMP_TYPE_OPTIONS,
)
from .helpers import async_set_setoption157, classify_nodeid, get_nested_value, normalize_nodeid

_LOGGER = logging.getLogger(__name__)

# Signatures for auto-detecting NeoPool entities with confidence scoring
# Each signature has a weight based on how unique it is to NeoPool
NEOPOOL_SIGNATURES: dict[str, int] = {
    # Very unique - high weight (25 points)
    "hydrolysis_runtime_total": 25,
    "hydrolysis_runtime_pol1": 25,
    "hydrolysis_runtime_pol2": 25,
    # Quite unique - medium-high weight (20 points)
    "system_id": 20,
    "powerunit_4ma": 20,
    "hydrolysis_polarity_changes": 20,
    # NeoPool-specific naming - medium weight (15 points)
    "hydrolysis_state": 15,
    "hydrolysis_data": 15,
    "hydrolysis_percent": 15,
    # Somewhat unique - lower weight (10 points)
    "filtration": 10,
    "modules_ph": 10,
    "modules_redox": 10,
    "modules_hydrolysis": 10,
    "ph_data": 10,
    "redox_data": 10,
    # Supportive but less unique (5 points)
    "water_temperature": 5,
    "ph_state": 5,
    "ph_pump": 5,
}


@callback
def get_topics_from_config(hass: HomeAssistant) -> set[str | None]:
    """Return the MQTT topics already configured."""
    return {
        config_entry.data.get(CONF_DISCOVERY_PREFIX)
        for config_entry in hass.config_entries.async_entries(DOMAIN)
    }


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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NeoPoolOptionsFlow:
        """Initiate Options Flow Instance."""
        return NeoPoolOptionsFlow()

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_prefix: str | None = None
        self._device_name: str | None = None
        self._nodeid: str | None = None  # canonical (hashed or real)
        self._nodeid_hashed: str | None = None
        self._nodeid_real: str | None = None
        self._nodeid_masked: str | None = None
        self._yaml_topic: str | None = None
        self._migrate_yaml: bool = False
        self._unique_id_prefix: str = DEFAULT_UNIQUE_ID_PREFIX
        self._migrating_entities: list[RegistryEntry] = []
        self._migration_result: dict[str, Any] | None = None
        # Auto-detection state
        self._detected_prefix: str | None = None
        self._detection_confidence: int = 0
        self._matched_signatures: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - warn about YAML package removal."""
        if user_input is not None:
            return await self.async_step_yaml_migration()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm_no_yaml", default=False): cv.boolean,
                }
            ),
        )

    async def async_step_yaml_migration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask if user wants to migrate from YAML package."""
        if user_input is not None:
            self._migrate_yaml = user_input.get(CONF_MIGRATE_YAML, False)

            if self._migrate_yaml:
                # Try auto-detection first
                return await self.async_step_yaml_detect()
            # No migration needed, continue with fresh install
            return await self.async_step_discover_device()

        return self.async_show_form(
            step_id="yaml_migration",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MIGRATE_YAML, default=False): cv.boolean,
                }
            ),
        )

    async def async_step_yaml_detect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Auto-detect MQTT topic for YAML migration."""
        # Try to auto-detect the MQTT topic
        detected_topic = await self._auto_detect_topic()

        if detected_topic:
            _LOGGER.info("Auto-detected NeoPool device on topic: %s", detected_topic)
            # Validate the detected topic and get NodeID
            validation_result = await self._validate_yaml_topic(detected_topic)

            if validation_result["valid"]:
                self._yaml_topic = detected_topic
                self._discovery_prefix = detected_topic

                config_result = await self._acquire_and_store_nodeids(detected_topic)
                if not config_result["success"]:
                    # NodeID acquisition failed, ask for topic manually
                    return await self.async_step_yaml_topic()

                # Now try to find migratable entities
                return await self._check_migratable_entities()

        # Could not auto-detect, ask user for topic
        _LOGGER.debug("Could not auto-detect NeoPool topic, asking user")
        return await self.async_step_yaml_topic()

    async def async_step_yaml_topic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get and validate YAML topic (fallback when auto-detection fails)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            yaml_topic = user_input.get("yaml_topic", DEFAULT_MQTT_TOPIC)

            # Validate YAML topic by trying to read from it
            validation_result = await self._validate_yaml_topic(yaml_topic)

            if validation_result["valid"]:
                self._yaml_topic = yaml_topic
                self._discovery_prefix = yaml_topic

                config_result = await self._acquire_and_store_nodeids(yaml_topic)
                if not config_result["success"]:
                    return self.async_abort(
                        reason="nodeid_configuration_failed",
                        description_placeholders={
                            "error": config_result.get("error", "Failed to acquire NodeID")
                        },
                    )

                # Now check for migratable entities
                return await self._check_migratable_entities()

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="yaml_topic",
            data_schema=vol.Schema(
                {
                    vol.Required("yaml_topic", default=DEFAULT_MQTT_TOPIC): cv.string,
                }
            ),
            errors=errors,
        )

    async def _check_migratable_entities(self) -> ConfigFlowResult:
        """Check for migratable entities with default prefix, or ask user for custom prefix."""
        # Step 1: Try default prefix first
        entities = self._find_migratable_entities(DEFAULT_UNIQUE_ID_PREFIX)

        if entities:
            self._unique_id_prefix = DEFAULT_UNIQUE_ID_PREFIX
            self._migrating_entities = entities
            _LOGGER.info(
                "Found %d migratable entities with default prefix '%s'",
                len(entities),
                DEFAULT_UNIQUE_ID_PREFIX,
            )

            # Check if any entities are still active (YAML package still running)
            active_entities = self._find_active_entities(entities)
            if active_entities:
                _LOGGER.warning(
                    "Found %d active entities - YAML package may still be running",
                    len(active_entities),
                )
                return await self.async_step_yaml_active_warning()

            return await self.async_step_yaml_confirm()

        # Step 2: Smart search with confidence scoring
        _LOGGER.debug(
            "No entities found with default prefix '%s', trying smart detection",
            DEFAULT_UNIQUE_ID_PREFIX,
        )
        detection = self._auto_detect_neopool_prefix()

        if detection["prefix"] and detection["confidence"] >= 30:
            # Found something with reasonable confidence - ask user to confirm
            self._detected_prefix = detection["prefix"]
            self._detection_confidence = detection["confidence"]
            self._matched_signatures = detection["matched_signatures"]
            _LOGGER.info(
                "Smart detection found prefix '%s' with %d%% confidence (%d signatures)",
                detection["prefix"],
                detection["confidence"],
                len(detection["matched_signatures"]),
            )
            return await self.async_step_yaml_detect_confirm()

        # Step 3: Nothing found - offer escape path instead of dead-ending
        _LOGGER.debug(
            "Smart detection failed (prefix=%s, confidence=%d), no entities to migrate",
            detection.get("prefix"),
            detection.get("confidence", 0),
        )
        return await self.async_step_yaml_no_entities()

    def _find_migratable_entities(self, prefix: str) -> list[RegistryEntry]:
        """Find migratable entities with given unique_id prefix.

        Finds entities that match the prefix and are either:
        - Orphaned (no config_entry_id), OR
        - Owned by a different platform (e.g., "mqtt" from YAML package)
        """
        entity_registry = er.async_get(self.hass)
        entities = [
            entity
            for entity in entity_registry.entities.values()
            if entity.unique_id.startswith(prefix)
            and (entity.config_entry_id is None or entity.platform != DOMAIN)
        ]
        # Debug logging to see what was found
        _LOGGER.debug(
            "Found %d migratable entities with prefix '%s'",
            len(entities),
            prefix,
        )
        for entity in entities:
            _LOGGER.debug(
                "  - %s (unique_id=%s, platform=%s, config_entry=%s)",
                entity.entity_id,
                entity.unique_id,
                entity.platform,
                entity.config_entry_id,
            )
        return entities

    def _find_active_entities(self, entities: list[RegistryEntry]) -> list[RegistryEntry]:
        """Find entities that are currently active (have a valid state).

        An entity is considered "active" if it has a state that is not:
        - None (entity doesn't exist in state machine)
        - "unavailable" (entity exists but source is unavailable)
        - "unknown" (entity exists but state is unknown)

        If active entities are found, it means the YAML package is still running.
        """
        active_entities = []
        for entity in entities:
            state = self.hass.states.get(entity.entity_id)
            if state is not None and state.state not in ("unavailable", "unknown"):
                active_entities.append(entity)
        return active_entities

    def _auto_detect_neopool_prefix(self) -> dict[str, Any]:
        """Auto-detect NeoPool entities using signature matching.

        Scans MQTT platform entities for unique_ids ending with NeoPool signatures.
        Returns dict with prefix, confidence score, and matched signatures.
        """
        entity_registry = er.async_get(self.hass)
        mqtt_entities = [e for e in entity_registry.entities.values() if e.platform == "mqtt"]

        detected_prefix: str | None = None
        matched_signatures: list[str] = []
        total_score = 0

        for entity in mqtt_entities:
            for signature, weight in NEOPOOL_SIGNATURES.items():
                if entity.unique_id.endswith(signature):
                    # Extract prefix (everything before the signature)
                    prefix = entity.unique_id[: -len(signature)]

                    if detected_prefix is None:
                        detected_prefix = prefix
                    elif prefix != detected_prefix:
                        continue  # Different prefix, skip

                    matched_signatures.append(signature)
                    total_score += weight
                    break  # One match per entity

        # Cap confidence at 100%
        confidence = min(total_score, 100)

        return {
            "prefix": detected_prefix,
            "confidence": confidence,
            "matched_signatures": matched_signatures,
            "entity_count": len(matched_signatures),
        }

    def _format_entity_list(self, entities: list[RegistryEntry]) -> str:
        """Format entity list for display (first 5 + count)."""
        lines = [f"• `{entity.entity_id}`" for entity in entities[:5]]
        if len(entities) > 5:
            lines.append(f"• ...and {len(entities) - 5} more")
        return "\n".join(lines)

    async def async_step_yaml_no_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """No YAML entities found - offer to try custom prefix or skip to fresh setup."""
        if user_input is not None:
            if user_input.get("try_custom_prefix", False):
                return await self.async_step_yaml_prefix()
            # Skip migration, proceed to fresh device setup
            self._migrate_yaml = False
            return await self.async_step_discover_device()

        return self.async_show_form(
            step_id="yaml_no_entities",
            data_schema=vol.Schema(
                {
                    vol.Required("try_custom_prefix", default=False): cv.boolean,
                }
            ),
        )

    async def async_step_yaml_prefix(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask user for custom unique_id prefix (when default not found)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            prefix = user_input.get(CONF_UNIQUE_ID_PREFIX, "")

            if prefix:
                entities = self._find_migratable_entities(prefix)

                if entities:
                    self._unique_id_prefix = prefix
                    self._migrating_entities = entities
                    _LOGGER.info(
                        "Found %d migratable entities with custom prefix '%s'",
                        len(entities),
                        prefix,
                    )

                    # Check if any entities are still active (YAML package still running)
                    active_entities = self._find_active_entities(entities)
                    if active_entities:
                        _LOGGER.warning(
                            "Found %d active entities - YAML package may still be running",
                            len(active_entities),
                        )
                        return await self.async_step_yaml_active_warning()

                    return await self.async_step_yaml_confirm()

                errors["base"] = "no_entities_found"
            else:
                errors["base"] = "no_entities_found"

        return self.async_show_form(
            step_id="yaml_prefix",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UNIQUE_ID_PREFIX): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_yaml_detect_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show detected prefix and ask user to confirm."""
        if user_input is not None:
            if user_input.get("confirm_detection"):
                # User confirmed - use detected prefix
                self._unique_id_prefix = self._detected_prefix or DEFAULT_UNIQUE_ID_PREFIX
                entities = self._find_migratable_entities(self._unique_id_prefix)
                if entities:
                    self._migrating_entities = entities
                    _LOGGER.info(
                        "User confirmed detected prefix '%s', found %d entities",
                        self._unique_id_prefix,
                        len(entities),
                    )

                    # Check if any entities are still active
                    active_entities = self._find_active_entities(entities)
                    if active_entities:
                        return await self.async_step_yaml_active_warning()

                    return await self.async_step_yaml_confirm()

            # User rejected - ask for manual input
            return await self.async_step_yaml_prefix()

        # Format matched signatures for display
        sig_list = "\n".join(f"  ✓ {sig}" for sig in self._matched_signatures[:5])
        if len(self._matched_signatures) > 5:
            sig_list += f"\n  ... and {len(self._matched_signatures) - 5} more"

        return self.async_show_form(
            step_id="yaml_detect_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm_detection", default=True): cv.boolean,
                }
            ),
            description_placeholders={
                "prefix": self._detected_prefix or "",
                "confidence": str(self._detection_confidence),
                "entity_count": str(len(self._matched_signatures)),
                "matched_signatures": sig_list,
            },
        )

    async def async_step_yaml_active_warning(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Warn user that YAML entities are still active and must be removed first."""
        if user_input is not None:
            # User clicked "Retry" - check again if entities are still active
            active_entities = self._find_active_entities(self._migrating_entities)
            if active_entities:
                # Still active, show warning again
                _LOGGER.warning(
                    "Retry check: still found %d active entities",
                    len(active_entities),
                )
                entity_list = self._format_entity_list(active_entities)
                return self.async_show_form(
                    step_id="yaml_active_warning",
                    data_schema=vol.Schema({}),
                    description_placeholders={
                        "active_count": str(len(active_entities)),
                        "entity_list": entity_list,
                    },
                    errors={"base": "yaml_still_active"},
                )

            # Entities are no longer active, proceed to confirmation
            _LOGGER.info("Retry check: entities are no longer active, proceeding")
            return await self.async_step_yaml_confirm()

        # First time showing the warning
        active_entities = self._find_active_entities(self._migrating_entities)
        entity_list = self._format_entity_list(active_entities)

        return self.async_show_form(
            step_id="yaml_active_warning",
            data_schema=vol.Schema({}),
            description_placeholders={
                "active_count": str(len(active_entities)),
                "entity_list": entity_list,
            },
        )

    async def async_step_yaml_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show migration summary and require explicit confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User must check the confirmation checkbox
            if not user_input.get(CONF_CONFIRM_MIGRATION):
                errors["base"] = "confirmation_required"
            else:
                # User confirmed - perform migration NOW (before entry creation)
                self._migration_result = await self._perform_migration()

                # Show results step
                return await self.async_step_yaml_migration_result()

        # Build entity list for display
        entity_list = self._format_entity_list(self._migrating_entities)

        return self.async_show_form(
            step_id="yaml_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONFIRM_MIGRATION, default=False): cv.boolean,
                }
            ),
            description_placeholders={
                "topic": self._yaml_topic or "",
                "nodeid": self._nodeid or "",
                "entity_count": str(len(self._migrating_entities)),
                "entity_list": entity_list,
            },
            errors=errors,
        )

    async def _perform_migration(self) -> dict[str, Any]:
        """Execute entity migration by DELETING old MQTT entities.

        This preserves historical data because:
        1. We delete old entities from registry (platform="mqtt")
        2. We build a mapping of entity_key -> object_id (from old entity_id)
        3. New entities will be created with same entity_id, preserving history
        """
        summary: dict[str, Any] = {
            "entities_found": len(self._migrating_entities),
            "entities_migrated": 0,
            "entities_failed": [],
            "migrated_list": [],
            "entity_id_mapping": {},
        }

        entity_registry = er.async_get(self.hass)

        for entity in self._migrating_entities:
            try:
                # Extract entity_key (part after prefix in unique_id)
                entity_key = entity.unique_id.replace(self._unique_id_prefix, "", 1)

                # Get ACTUAL entity_id from registry (handles user customization)
                actual_entity_id = entity.entity_id
                object_id = actual_entity_id.split(".", 1)[1]

                # Check for collision: is this object_id used by another entity?
                collision_found = False
                for other in entity_registry.entities.values():
                    if other.entity_id != actual_entity_id:
                        if other.entity_id.endswith(f".{object_id}"):
                            summary["entities_failed"].append(
                                f"{actual_entity_id}: collision with {other.entity_id}"
                            )
                            collision_found = True
                            break

                if collision_found:
                    continue

                # Map: entity_key -> actual entity_id (includes domain for proper matching)
                # Store full entity_id to preserve domain info (sensor vs select, etc.)
                summary["entity_id_mapping"][entity_key] = actual_entity_id
                _LOGGER.debug(
                    "Added to entity_id_mapping: %s -> %s",
                    entity_key,
                    actual_entity_id,
                )

                # DELETE the old MQTT entity from registry
                entity_registry.async_remove(actual_entity_id)

                summary["entities_migrated"] += 1
                summary["migrated_list"].append(actual_entity_id)
                _LOGGER.info(
                    "Deleted MQTT entity %s (key: %s, will recreate with same entity_id)",
                    actual_entity_id,
                    entity_key,
                )
            except Exception as e:  # noqa: BLE001
                error_msg = f"{entity.entity_id}: {e}"
                summary["entities_failed"].append(error_msg)
                _LOGGER.error("Failed to migrate entity %s: %s", entity.entity_id, e)

        return summary

    def _format_migrated_entity_list(self, entity_ids: list[str]) -> str:
        """Format migrated entity list for display (first 5 + count)."""
        lines = [f"• `{entity_id}`" for entity_id in entity_ids[:5]]
        if len(entity_ids) > 5:
            lines.append(f"• ...and {len(entity_ids) - 5} more")
        return "\n".join(lines) if lines else "None"

    def _extract_device_name_from_migration(self) -> str:
        """Extract device name from migrated entity IDs.

        Analyzes the entity_id_mapping to determine the device name prefix
        used in the original YAML entities. This preserves user customizations.

        Supports two mapping formats:
        - New format: entity_key -> full entity_id (e.g., "sensor.neopool_mqtt_ph_data")
        - Old format: entity_key -> object_id only (e.g., "neopool_mqtt_ph_data")

        Example:
            "sensor.neopool_mqtt_ph_data" with key "ph_data" -> "NeoPool MQTT"
            "sensor.my_pool_ph_data" with key "ph_data" -> "My Pool"

        Returns:
            Extracted device name, or DEFAULT_DEVICE_NAME as fallback.
        """
        result = self._migration_result or {}
        entity_id_mapping = result.get("entity_id_mapping", {})

        if not entity_id_mapping:
            return DEFAULT_DEVICE_NAME

        # Try to extract from first entity
        for entity_key, target_value in entity_id_mapping.items():
            # Handle both formats:
            # - New format: "sensor.neopool_mqtt_ph_data" -> extract object_id first
            # - Old format: "neopool_mqtt_ph_data" -> use directly
            if "." in target_value:
                object_id = target_value.split(".", 1)[1]
            else:
                object_id = target_value

            # object_id is like "neopool_mqtt_ph_data", entity_key is "ph_data"
            # We need to extract "neopool_mqtt" and convert to "NeoPool MQTT"
            if object_id.endswith(f"_{entity_key}"):
                prefix = object_id[: -len(f"_{entity_key}")]
                # Convert slug to title: "neopool_mqtt" -> "NeoPool MQTT"
                # Replace underscores with spaces and title case
                device_name = prefix.replace("_", " ").title()
                _LOGGER.debug(
                    "Extracted device name '%s' from entity %s (key: %s)",
                    device_name,
                    target_value,
                    entity_key,
                )
                return device_name

        return DEFAULT_DEVICE_NAME

    async def async_step_yaml_migration_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show migration results and complete setup."""
        if user_input is not None:
            # User acknowledged results, create entry
            # Extract device name from migrated entity IDs to preserve user customizations
            # e.g., "sensor.neopool_mqtt_ph_data" -> "NeoPool MQTT"
            # e.g., "sensor.my_pool_ph_data" -> "My Pool"
            device_name = self._extract_device_name_from_migration()

            # Set unique ID based on NodeID
            await self.async_set_unique_id(f"{DOMAIN}_{self._nodeid}")
            self._abort_if_unique_id_configured()

            # Store entity_id_mapping in entry data for async_setup_entry
            result = self._migration_result or {}

            return self.async_create_entry(
                title=device_name,
                data=self._build_entry_data(
                    device_name,
                    self._yaml_topic or "",
                    **{
                        CONF_UNIQUE_ID_PREFIX: self._unique_id_prefix,
                        CONF_MIGRATE_YAML: True,
                        "entity_id_mapping": result.get("entity_id_mapping", {}),
                    },
                ),
            )

        # Format results for display
        result = self._migration_result or {}
        migrated_list = self._format_migrated_entity_list(result.get("migrated_list", []))
        failed_entries = result.get("entities_failed", [])
        failed_list = "\n".join(f"• {e}" for e in failed_entries[:5])
        if len(failed_entries) > 5:
            failed_list += f"\n• ...and {len(failed_entries) - 5} more"

        return self.async_show_form(
            step_id="yaml_migration_result",
            data_schema=vol.Schema({}),
            description_placeholders={
                "entities_found": str(result.get("entities_found", 0)),
                "entities_migrated": str(result.get("entities_migrated", 0)),
                "errors_count": str(len(failed_entries)),
                "migrated_list": migrated_list or "None",
                "failed_list": failed_list or "None",
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
                    config_result = await self._acquire_and_store_nodeids(discovery_prefix)
                    if not config_result["success"]:
                        return self.async_abort(
                            reason="nodeid_configuration_failed",
                            description_placeholders={
                                "error": config_result.get("error", "Failed to acquire NodeID")
                            },
                        )

                    # Set unique ID and check for duplicates
                    await self.async_set_unique_id(f"{DOMAIN}_{self._nodeid}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_name,
                        data=self._build_entry_data(device_name, discovery_prefix),
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
        except json.JSONDecodeError, TypeError:
            return self.async_abort(reason="invalid_discovery_info")

        # Store discovery info
        self._discovery_prefix = device_topic
        self._device_name = f"NeoPool {device_topic}"

        # Acquire dual NodeIDs
        config_result = await self._acquire_and_store_nodeids(device_topic)
        if not config_result["success"]:
            return self.async_abort(
                reason="nodeid_configuration_failed",
                description_placeholders={
                    "error": config_result.get("error", "Failed to acquire NodeID")
                },
            )

        # Set unique ID based on NodeID to prevent duplicate discoveries
        await self.async_set_unique_id(f"{DOMAIN}_{self._nodeid}")
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
                data=self._build_entry_data(device_name, discovery_prefix),
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

    async def _auto_detect_topic(self, timeout_seconds: int = 10) -> str | None:
        """Auto-detect MQTT topic by scanning for NeoPool messages.

        Subscribes to tele/+/SENSOR wildcard and looks for NeoPool payloads.
        Returns the detected topic or None if not found.
        """
        detected_topic: str | None = None
        event = asyncio.Event()

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            nonlocal detected_topic
            # Topic format: tele/{device_topic}/SENSOR
            parts = msg.topic.split("/")
            if len(parts) >= 3 and parts[0] == "tele" and parts[2] == "SENSOR":
                try:
                    payload = json.loads(msg.payload)
                    if "NeoPool" in payload:
                        detected_topic = parts[1]  # Extract device topic
                        event.set()
                except json.JSONDecodeError, TypeError:
                    pass

        # Subscribe to wildcard topic
        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            "tele/+/SENSOR",
            message_received,
            qos=0,
        )

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            _LOGGER.debug("Timeout during auto-detection of NeoPool topic")
        finally:
            unsubscribe()

        return detected_topic

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
            except json.JSONDecodeError, TypeError:
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
            # Force an immediate telemetry burst so validation does not have
            # to wait for Tasmota's TelePeriod (default 300s). SENSOR is
            # published non-retained, so without this nudge a correct topic
            # almost always times out (see issue #18). Subscribe-then-trigger
            # ordering avoids missing the response.
            await self._trigger_telemetry(topic)
            # Wait for message or timeout
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for message from YAML topic: %s", sensor_topic)
        finally:
            unsubscribe()

        return result

    async def _auto_configure_nodeid(self, device_topic: str) -> dict[str, Any]:
        """Acquire both hashed and real NodeIDs via dual recognition.

        Reads the current NodeID, classifies it, toggles SO157 once to get
        the other format, then restores SO157 to its original state.

        Returns dict with 'success' boolean and NodeID values or 'error'.
        Keys on success: 'nodeid' (canonical), 'nodeid_hashed', 'nodeid_real',
        'nodeid_masked'.
        """
        # Step 1: Read current NodeID from SENSOR
        _LOGGER.info("Reading initial NodeID from %s", device_topic)
        await self._trigger_telemetry(device_topic)
        first_nodeid = await self._wait_for_any_nodeid(device_topic)

        if not first_nodeid:
            return {
                "success": False,
                "error": "No NodeID received from device. Check MQTT connection.",
            }

        first_type = classify_nodeid(first_nodeid)
        _LOGGER.info("Received NodeID: %s (type: %s)", first_nodeid, first_type)

        if first_type == "invalid":
            return {
                "success": False,
                "error": f"Invalid NodeID received: '{first_nodeid}'",
            }

        # Step 2: Toggle SO157 to get the other format
        # Got hashed/masked (SO157=0) → toggle to 1 to get real
        # Got real (SO157=1) → toggle to 0 to get hashed/masked
        toggle_to = first_type in ("hashed", "masked")
        _LOGGER.info(
            "Toggling SetOption157 to %s to acquire second NodeID",
            "1" if toggle_to else "0",
        )
        await async_set_setoption157(self.hass, device_topic, enable=toggle_to)
        await asyncio.sleep(1)
        await self._trigger_telemetry(device_topic)
        second_nodeid = await self._wait_for_any_nodeid(device_topic)

        # Step 3: Restore SO157 to original state
        _LOGGER.info("Restoring SetOption157 to %s", "0" if toggle_to else "1")
        await async_set_setoption157(self.hass, device_topic, enable=not toggle_to)

        # Step 4: Classify and store both NodeIDs
        second_type = classify_nodeid(second_nodeid) if second_nodeid else "invalid"
        _LOGGER.info("Second NodeID: %s (type: %s)", second_nodeid, second_type)

        nodeid_hashed = None
        nodeid_real = None
        nodeid_masked = None

        for nodeid, ntype in [(first_nodeid, first_type), (second_nodeid, second_type)]:
            if ntype == "hashed":
                nodeid_hashed = normalize_nodeid(nodeid)
            elif ntype == "real":
                nodeid_real = normalize_nodeid(nodeid)
            elif ntype == "masked":
                nodeid_masked = normalize_nodeid(nodeid)

        # Must have at least the real NodeID
        if not nodeid_real:
            return {
                "success": False,
                "error": "Could not acquire real NodeID. Device may not be responding.",
            }

        # Canonical: prefer hashed (privacy), fall back to real
        canonical = nodeid_hashed or nodeid_real

        _LOGGER.info(
            "NodeID acquisition complete. Canonical: %s, Real: %s, Hashed: %s, Masked: %s",
            canonical,
            nodeid_real,
            nodeid_hashed or "N/A",
            nodeid_masked or "N/A",
        )

        return {
            "success": True,
            "nodeid": canonical,
            "nodeid_hashed": nodeid_hashed,
            "nodeid_real": nodeid_real,
            "nodeid_masked": nodeid_masked,
        }

    async def _trigger_telemetry(self, device_topic: str) -> None:
        """Trigger immediate telemetry from the device."""
        await mqtt.async_publish(
            self.hass,
            f"cmnd/{device_topic}/TelePeriod",
            "",
            qos=1,
            retain=False,
        )

    async def _wait_for_any_nodeid(
        self, device_topic: str, timeout_seconds: int = 10
    ) -> str | None:
        """Wait for any NodeID to appear in MQTT message.

        Unlike the old _wait_for_nodeid, this accepts ALL formats including
        masked (XXXX) and hashed (AA55) — classification happens in the caller.
        """
        received_nodeid: str | None = None
        event = asyncio.Event()

        @callback
        def message_received(msg: mqtt.ReceiveMessage) -> None:
            nonlocal received_nodeid
            try:
                payload = json.loads(msg.payload)
                nodeid = get_nested_value(payload, "NeoPool.Powerunit.NodeID")
                if nodeid and str(nodeid).strip():
                    received_nodeid = str(nodeid)
                    event.set()
            except json.JSONDecodeError, TypeError:
                pass

        unsubscribe = await mqtt.async_subscribe(
            self.hass,
            f"tele/{device_topic}/SENSOR",
            message_received,
            qos=1,
        )

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for NodeID from %s", device_topic)
        finally:
            unsubscribe()

        return received_nodeid

    def _build_entry_data(
        self, device_name: str, discovery_prefix: str, **extra: Any
    ) -> dict[str, Any]:
        """Build config entry data dict with all NodeID values."""
        from .const import CONF_NODEID_HASHED, CONF_NODEID_MASKED, CONF_NODEID_REAL  # noqa: PLC0415

        data: dict[str, Any] = {
            CONF_DEVICE_NAME: device_name,
            CONF_DISCOVERY_PREFIX: discovery_prefix,
            CONF_NODEID: self._nodeid,
            CONF_NODEID_HASHED: self._nodeid_hashed,
            CONF_NODEID_REAL: self._nodeid_real,
            CONF_NODEID_MASKED: self._nodeid_masked,
        }
        data.update(extra)
        return data

    async def _acquire_and_store_nodeids(self, device_topic: str) -> dict[str, Any]:
        """Acquire dual NodeIDs and store in instance variables.

        Convenience wrapper around _auto_configure_nodeid that stores
        results in self._nodeid, self._nodeid_hashed, self._nodeid_real,
        and self._nodeid_masked.

        Returns the raw result dict from _auto_configure_nodeid.
        """
        result = await self._auto_configure_nodeid(device_topic)
        if result["success"]:
            self._nodeid = result["nodeid"]
            self._nodeid_hashed = result.get("nodeid_hashed")
            self._nodeid_real = result.get("nodeid_real")
            self._nodeid_masked = result.get("nodeid_masked")
        return result

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME]
            discovery_prefix = user_input[CONF_DISCOVERY_PREFIX]
            regenerate = user_input.get(CONF_REGENERATE_ENTITY_IDS, False)

            _LOGGER.debug(
                "Reconfigure requested: name=%s, topic=%s, regenerate=%s",
                device_name,
                discovery_prefix,
                regenerate,
            )

            # Validate MQTT topic format
            try:
                valid_subscribe_topic(f"tele/{discovery_prefix}/SENSOR")
            except vol.Invalid:
                errors[CONF_DISCOVERY_PREFIX] = "invalid_topic"

            if not errors:
                # Test connection with new topic
                validation_result = await self._validate_yaml_topic(discovery_prefix)

                if not validation_result["valid"]:
                    errors["base"] = "cannot_connect"
                else:
                    config_result = await self._acquire_and_store_nodeids(discovery_prefix)
                    if not config_result["success"]:
                        errors["base"] = "nodeid_configuration_failed"

                    if not errors:
                        # Verify unique ID matches before updating
                        await self.async_set_unique_id(f"{DOMAIN}_{self._nodeid}")
                        self._abort_if_unique_id_mismatch()

                        # Regenerate entity IDs if requested and device name changed
                        old_device_name = reconfigure_entry.data.get(CONF_DEVICE_NAME)
                        regenerated_count = 0
                        if regenerate and device_name != old_device_name:
                            regenerated_count = await self._regenerate_entity_ids(
                                reconfigure_entry, device_name
                            )
                            _LOGGER.info(
                                "Regenerated %d entity IDs for new device name: %s",
                                regenerated_count,
                                device_name,
                            )

                        _LOGGER.debug(
                            "Connection test passed, applying reconfigure: nodeid=%s, "
                            "regenerated=%d",
                            self._nodeid,
                            regenerated_count,
                        )
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            title=device_name,
                            data_updates=self._build_entry_data(device_name, discovery_prefix),
                        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_NAME,
                        default=reconfigure_entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
                    ): cv.string,
                    vol.Optional(
                        CONF_REGENERATE_ENTITY_IDS,
                        default=False,
                    ): cv.boolean,
                    vol.Required(
                        CONF_DISCOVERY_PREFIX,
                        default=reconfigure_entry.data.get(
                            CONF_DISCOVERY_PREFIX, DEFAULT_MQTT_TOPIC
                        ),
                    ): cv.string,
                },
            ),
            errors=errors,
        )

    async def _regenerate_entity_ids(self, config_entry: ConfigEntry, new_device_name: str) -> int:
        """Regenerate entity IDs based on new device name.

        Returns the number of entities that were updated.
        """
        registry = er.async_get(self.hass)
        entities = er.async_entries_for_config_entry(registry, config_entry.entry_id)

        regenerated_count = 0
        for entity_entry in entities:
            # Extract entity_key from unique_id: neopool_mqtt_{nodeid}_{entity_key}
            unique_id_parts = entity_entry.unique_id.split("_")
            if len(unique_id_parts) >= 4:
                # Everything after "neopool_mqtt_{nodeid}_" is the entity_key
                entity_key = "_".join(unique_id_parts[3:])
                domain = entity_entry.entity_id.split(".")[0]
                new_entity_id = f"{domain}.{slugify(new_device_name)}_{entity_key}"

                if entity_entry.entity_id != new_entity_id:
                    # Check if the new entity_id is available
                    if not registry.async_get(new_entity_id):
                        registry.async_update_entity(
                            entity_entry.entity_id,
                            new_entity_id=new_entity_id,
                        )
                        _LOGGER.debug(
                            "Regenerated entity ID: %s -> %s",
                            entity_entry.entity_id,
                            new_entity_id,
                        )
                        regenerated_count += 1
                    else:
                        _LOGGER.warning(
                            "Cannot regenerate entity ID %s -> %s: target already exists",
                            entity_entry.entity_id,
                            new_entity_id,
                        )

        return regenerated_count


class NeoPoolOptionsFlow(OptionsFlowWithReload):
    """Config flow options handler with auto-reload."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug(
                "Options updated: enable_repair=%s, failures_threshold=%s, "
                "offline_timeout=%s, recovery_script=%s, conn_error_rate_threshold=%s",
                user_input.get(CONF_ENABLE_REPAIR_NOTIFICATION),
                user_input.get(CONF_FAILURES_THRESHOLD),
                user_input.get(CONF_OFFLINE_TIMEOUT),
                user_input.get(CONF_RECOVERY_SCRIPT),
                user_input.get(CONF_CONNECTION_ERROR_RATE_THRESHOLD),
            )
            return self.async_create_entry(data=user_input)

        return await self._show_options_form()

    async def _show_options_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show the options form."""
        # Get current options with defaults
        current_options = self.config_entry.options

        enable_repair = current_options.get(
            CONF_ENABLE_REPAIR_NOTIFICATION, DEFAULT_ENABLE_REPAIR_NOTIFICATION
        )
        failures_threshold = current_options.get(
            CONF_FAILURES_THRESHOLD, DEFAULT_FAILURES_THRESHOLD
        )
        recovery_script = current_options.get(CONF_RECOVERY_SCRIPT, DEFAULT_RECOVERY_SCRIPT)
        offline_timeout = current_options.get(CONF_OFFLINE_TIMEOUT, DEFAULT_OFFLINE_TIMEOUT)
        connection_error_rate_threshold = current_options.get(
            CONF_CONNECTION_ERROR_RATE_THRESHOLD,
            DEFAULT_CONNECTION_ERROR_RATE_THRESHOLD,
        )
        pump_type = current_options.get(CONF_PUMP_TYPE, DEFAULT_PUMP_TYPE)

        description_placeholders: dict[str, str] = {}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    # 1. Recovery script (runs when device goes offline after threshold)
                    # Use suggested_value (not default) so clearing the EntitySelector
                    # actually unsets the option. With default=, voluptuous resurrects
                    # the saved value when the field is submitted empty, making the
                    # script impossible to clear via the UI.
                    vol.Optional(
                        CONF_RECOVERY_SCRIPT,
                        description={"suggested_value": recovery_script},
                    ): EntitySelector(
                        EntitySelectorConfig(domain="script"),
                    ),
                    # 2. Enable repair notifications checkbox
                    vol.Required(
                        CONF_ENABLE_REPAIR_NOTIFICATION,
                        default=enable_repair,
                    ): cv.boolean,
                    # 3. Failures threshold as input box (not slider)
                    vol.Required(
                        CONF_FAILURES_THRESHOLD,
                        default=failures_threshold,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_FAILURES_THRESHOLD,
                            max=MAX_FAILURES_THRESHOLD,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    # 4. Offline timeout (how long device must be offline before notification)
                    vol.Required(
                        CONF_OFFLINE_TIMEOUT,
                        default=offline_timeout,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_OFFLINE_TIMEOUT,
                            max=MAX_OFFLINE_TIMEOUT,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="seconds",
                        )
                    ),
                    # 5. Connection error-rate threshold (% above which
                    # binary_sensor.connection_problem turns on)
                    vol.Required(
                        CONF_CONNECTION_ERROR_RATE_THRESHOLD,
                        default=connection_error_rate_threshold,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_CONNECTION_ERROR_RATE_THRESHOLD,
                            max=MAX_CONNECTION_ERROR_RATE_THRESHOLD,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="%",
                            step=0.1,
                        )
                    ),
                    # 6. Filtration pump type — gates the per-timer speed selects.
                    # "auto" trusts the controller's self-report (variable-speed
                    # pumps emit Filtration.Speed); override forces on/off.
                    vol.Required(
                        CONF_PUMP_TYPE,
                        default=pump_type,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(PUMP_TYPE_OPTIONS),
                            translation_key="pump_type",
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                },
            ),
            errors=errors or {},
            description_placeholders=description_placeholders,
        )
