"""Button platform for NeoPool MQTT integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from .const import CMD_ESCAPE, CMD_TIME
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

    buttons = [NeoPoolButton(entry, description) for description in BUTTON_DESCRIPTIONS]

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
