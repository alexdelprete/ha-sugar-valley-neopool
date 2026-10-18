"""Update platform for NeoPool MQTT integration.

One firmware update entity for the Tasmota device that bridges the NeoPool controller. The
installed version and build come from Tasmota's Status 2 (fetched with the device metadata);
the latest version comes from firmware/manifest.json in this repository, written by the
firmware workflow. Installing sends Tasmota's own OTA commands (OtaUrl + Upgrade 1): a normal
upgrade that keeps the device's settings.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from . import metadata_signal
from .const import (
    CMD_OTAURL,
    CMD_UPGRADE,
    DOMAIN,
    FIRMWARE_BASE_URL,
    FIRMWARE_CHECK_INTERVAL_HOURS,
    FIRMWARE_ESP8266_IMAGE,
    FIRMWARE_INSTALL_TIMEOUT_SECONDS,
    FIRMWARE_INSTALLABLE_IMAGES,
    FIRMWARE_MANIFEST_URL,
    FIRMWARE_README_URL,
    FIRMWARE_RETRY_SECONDS,
)
from .entity import NeoPoolMQTTEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import NeoPoolConfigEntry

_LOGGER = logging.getLogger(__name__)

# The entity polls the manifest (a small JSON file); HA calls async_update on this interval.
SCAN_INTERVAL = timedelta(hours=FIRMWARE_CHECK_INTERVAL_HOURS)
PARALLEL_UPDATES = 1

_MANIFEST_TIMEOUT = ClientTimeout(total=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the NeoPool firmware update entity."""
    async_add_entities([NeoPoolFirmwareUpdate(entry)])


def _parse_manifest(data: Any) -> dict[str, Any] | None:
    """Return the manifest if it has the fields the entity relies on, else None."""
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("tasmota_version"), str) or not isinstance(data.get("builds"), dict):
        return None
    return data


class NeoPoolFirmwareUpdate(NeoPoolMQTTEntity, UpdateEntity):
    """Tasmota firmware of the NeoPool bridge device.

    Offers Install only for the ESP32-family NeoPool builds (FIRMWARE_INSTALLABLE_IMAGES); any
    other device gets a read-only entity that still reports new versions. A newly published
    version is offered only from the manifest's "available_from" (a 24 h hold after publishing,
    so the maintainer can test it first); until then the installed version is reported as latest.
    """

    _attr_translation_key = "tasmota_firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = True  # periodic manifest check, see SCAN_INTERVAL
    _attr_title = "Tasmota NeoPool"

    def __init__(self, config_entry: NeoPoolConfigEntry) -> None:
        """Initialize the firmware update entity."""
        super().__init__(config_entry, "tasmota_firmware")
        self._manifest: dict[str, Any] | None = None
        self._install_target: str | None = None
        self._install_done: asyncio.Event | None = None
        self._cancel_retry: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to LWT and metadata updates, then fetch the manifest once."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                metadata_signal(self._config_entry),
                self._handle_metadata_update,
            )
        )
        self.async_on_remove(self._async_cancel_retry)
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_update(self) -> None:
        """Fetch firmware/manifest.json; keep the last good copy on any error.

        A failed fetch is retried after FIRMWARE_RETRY_SECONDS instead of waiting for the next
        poll: the first fetch runs while Home Assistant is still starting and can time out,
        and without a manifest the entity stays unavailable until it succeeds.
        """
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(FIRMWARE_MANIFEST_URL, timeout=_MANIFEST_TIMEOUT) as resp:
                resp.raise_for_status()
                # raw.githubusercontent.com serves JSON as text/plain
                data = await resp.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            # TimeoutError has an empty str(): log the type too
            _LOGGER.debug("Firmware manifest fetch failed: %s %s", type(err).__name__, err)
            self._async_schedule_retry()
            return
        manifest = _parse_manifest(data)
        if manifest is None:
            _LOGGER.debug("Firmware manifest has an unexpected format, ignoring it")
            self._async_schedule_retry()
            return
        self._manifest = manifest
        self._async_cancel_retry()

    @callback
    def _async_schedule_retry(self) -> None:
        """Fetch the manifest again soon (at most one retry pending)."""
        if self._cancel_retry is None:
            self._cancel_retry = async_call_later(
                self.hass, FIRMWARE_RETRY_SECONDS, self._async_retry_fetch
            )

    @callback
    def _async_retry_fetch(self, _now: Any) -> None:
        """Run the scheduled manifest retry."""
        self._cancel_retry = None
        self.async_schedule_update_ha_state(force_refresh=True)

    @callback
    def _async_cancel_retry(self) -> None:
        """Drop a pending manifest retry."""
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None

    @callback
    def _handle_metadata_update(self) -> None:
        """React to fresh device metadata (e.g. the new version after an upgrade)."""
        if (
            self._install_done is not None
            and self._install_target is not None
            and self.installed_version == self._install_target
        ):
            self._install_done.set()
        self._async_write_state()

    @property
    def _image(self) -> str | None:
        """Return the device's Tasmota build name, e.g. "tasmota32-neopool"."""
        return self._config_entry.runtime_data.tasmota_image

    @property
    def _build_key(self) -> str | None:
        """Return the manifest build this device may install, or None if read-only."""
        image = self._image
        return FIRMWARE_INSTALLABLE_IMAGES.get(image) if image else None

    @property
    def _held(self) -> bool:
        """True while the manifest's version is still inside its publishing hold."""
        if self._manifest is None:
            return False
        available_from = self._manifest.get("available_from")
        if not isinstance(available_from, str):
            return False
        when = dt_util.parse_datetime(available_from)
        return when is not None and dt_util.utcnow() < when

    @property
    def available(self) -> bool:
        """Available when the device is online and both versions are known."""
        return (
            super().available and self.installed_version is not None and self._manifest is not None
        )

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Install only for devices running an ESP32-family NeoPool build."""
        return UpdateEntityFeature.INSTALL if self._build_key else UpdateEntityFeature(0)

    @property
    def installed_version(self) -> str | None:
        """Return the Tasmota version the device runs."""
        return self._config_entry.runtime_data.tasmota_version

    @property
    def latest_version(self) -> str | None:
        """Return the manifest version, or the installed one during the publishing hold."""
        if self._manifest is None:
            return None
        if self._held:
            return self.installed_version
        return self._manifest["tasmota_version"]

    @property
    def release_url(self) -> str | None:
        """Return the Tasmota release page of the manifest version."""
        if self._manifest is None:
            return None
        url = self._manifest.get("release_url")
        return url if isinstance(url, str) else None

    @property
    def release_summary(self) -> str | None:
        """Explain what Install does, or why this device must be upgraded by hand."""
        if self._manifest is None:
            return None
        if self._build_key:
            return "Upgrades the device over the air with the NeoPool build. Settings are kept."
        if self._image == FIRMWARE_ESP8266_IMAGE:
            return (
                "Home Assistant does not upgrade ESP8266 devices. "
                f"Upgrade manually: [firmware README]({FIRMWARE_README_URL})"
            )
        return (
            f"This device runs a '{self._image or 'unknown'}' build; only the NeoPool ESP32 builds "
            f"are upgraded from Home Assistant. See the [firmware README]({FIRMWARE_README_URL})"
        )

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Send OtaUrl + Upgrade 1 and wait until the device reports the new version."""
        build_key = self._build_key
        if build_key is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_not_installable",
                translation_placeholders={"image": self._image or "unknown"},
            )
        build = (self._manifest or {}).get("builds", {}).get(build_key, {})
        ota_file = build.get("ota", {}).get("file") if isinstance(build, dict) else None
        if not ota_file or self._manifest is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_manifest_unavailable",
            )
        if not self._config_entry.runtime_data.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_device_offline",
            )

        target = self._manifest["tasmota_version"]
        url = f"{FIRMWARE_BASE_URL}{ota_file}"
        _LOGGER.info("Upgrading Tasmota %s -> %s from %s", self.installed_version, target, url)

        self._install_target = target
        self._install_done = asyncio.Event()
        self._attr_in_progress = True
        self._async_write_state()
        try:
            await self._publish_command(CMD_OTAURL, url, qos=1)
            await self._publish_command(CMD_UPGRADE, "1", qos=1)
            # The device reboots; the LWT watch re-fetches Status 2 once it is back online and
            # the metadata signal completes the wait when the new version reports in.
            async with asyncio.timeout(FIRMWARE_INSTALL_TIMEOUT_SECONDS):
                await self._install_done.wait()
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_install_timeout",
                translation_placeholders={
                    "version": target,
                    "minutes": str(FIRMWARE_INSTALL_TIMEOUT_SECONDS // 60),
                },
            ) from err
        finally:
            self._install_target = None
            self._install_done = None
            self._attr_in_progress = False
            self._async_write_state()
        _LOGGER.info("Tasmota upgraded to %s", target)
