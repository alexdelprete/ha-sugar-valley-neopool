"""Button platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from .const import CMD_ESCAPE, CMD_NPSAVE, CMD_NPWRITE, CMD_TIME, REG_RESET_USER_COUNTERS
from .entity import NeoPoolMQTTEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NeoPoolButtonEntityDescription(ButtonEntityDescription):
    """Describes a NeoPool button entity."""

    command: str
    payload: str = ""


BUTTON_DESCRIPTIONS: tuple[NeoPoolButtonEntityDescription, ...] = (
    NeoPoolButtonEntityDescription(
        key="clear_error",
        translation_key="clear_error",
        name="Clear Error State",
        icon="mdi:alert-remove",
        entity_category=EntityCategory.CONFIG,
        command=CMD_ESCAPE,
    ),
    NeoPoolButtonEntityDescription(
        key="sync_controller_time",
        translation_key="sync_controller_time",
        name="Sync Controller Time",
        icon="mdi:clock-check-outline",
        entity_category=EntityCategory.CONFIG,
        command=CMD_TIME,
        payload="0",  # NPTime 0 = sync controller clock to Tasmota's current time
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NeoPool buttons based on a config entry."""
    _LOGGER.debug("Setting up NeoPool buttons")

    buttons: list[ButtonEntity] = [
        NeoPoolButton(entry, description) for description in BUTTON_DESCRIPTIONS
    ]
    buttons.append(NeoPoolResetCellRuntimeButton(entry))

    async_add_entities(buttons)
    _LOGGER.info("Added %d NeoPool buttons", len(buttons))


class NeoPoolButton(NeoPoolMQTTEntity, ButtonEntity):
    """Representation of a NeoPool button."""

    entity_description: NeoPoolButtonEntityDescription

    def __init__(
        self,
        config_entry: NeoPoolConfigEntry,
        description: NeoPoolButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(config_entry, description.key)
        self.entity_description = description
        # Buttons are always available (no state to track)
        self._attr_available = True

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._publish_command(
            self.entity_description.command,
            self.entity_description.payload,
        )
        _LOGGER.debug("Pressed button %s", self.entity_description.key)


class NeoPoolResetCellRuntimeButton(NeoPoolMQTTEntity, ButtonEntity):
    """Button that resets the hydrolysis cell partial/user runtime counters.

    There is no dedicated NeoPool command for this, so it writes the
    MBF_RESET_USER_COUNTERS register (0x02F2) via NPWrite and persists with
    NPSave. The controller resets all user counters (cell partial, ION, UV) in
    one atomic operation. Disabled by default and gated to advanced users since
    it clears wear-tracking history; only relevant when a hydrolysis module is
    present.
    """

    _attr_translation_key = "reset_cell_runtime"
    _attr_name = "Reset Cell Runtime"
    _attr_icon = "mdi:counter"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, config_entry: NeoPoolConfigEntry) -> None:
        """Initialize the reset button."""
        super().__init__(config_entry, "reset_cell_runtime")
        # Buttons have no state to track.
        self._attr_available = True

    async def async_press(self) -> None:
        """Reset the user counters: NPWrite the register, then persist."""
        await self._publish_command(CMD_NPWRITE, f"0x{REG_RESET_USER_COUNTERS:04X} 1")
        await self._publish_command(CMD_NPSAVE, "")
        _LOGGER.debug("Reset hydrolysis cell runtime counters")
