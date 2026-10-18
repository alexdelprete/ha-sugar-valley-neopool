"""Tests for the Tasmota firmware update entity (update platform)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_OTAURL,
    CMD_UPGRADE,
    FIRMWARE_BASE_URL,
    FIRMWARE_MANIFEST_URL,
    FIRMWARE_RETRY_SECONDS,
)
from custom_components.sugar_valley_neopool.update import (
    NeoPoolFirmwareUpdate,
    _parse_manifest,
    async_setup_entry,
)
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

_UPDATE = "custom_components.sugar_valley_neopool.update"


def _iso(delta: timedelta) -> str:
    return (dt_util.utcnow() + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifest(available_from: str | None = None, **overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "tasmota_version": "16.0.0",
        "tasmota_tag": "v16.0.0",
        "release_url": "https://github.com/arendst/Tasmota/releases/tag/v16.0.0",
        "builds": {
            "esp32": {"env": "tasmota32", "ota": {"file": "NeoPool_ESP32_tasmota32.bin"}},
            "esp32s3": {"env": "tasmota32s3", "ota": {"file": "NeoPool_ESP32S3_tasmota32s3.bin"}},
            "esp32c3": {"env": "tasmota32c3", "ota": {"file": "NeoPool_ESP32C3_tasmota32c3.bin"}},
            "esp8266": {"env": "tasmota", "ota": {"file": "NeoPool_ESP8266_tasmota.bin.gz"}},
        },
    }
    if available_from is not None:
        manifest["available_from"] = available_from
    manifest.update(overrides)
    return manifest


def _entity(entry: MagicMock, *, image: str | None = "tasmota32-neopool") -> NeoPoolFirmwareUpdate:
    entry.runtime_data.tasmota_version = "15.6.0"
    entry.runtime_data.tasmota_image = image
    ent = NeoPoolFirmwareUpdate(entry)
    ent.async_write_ha_state = MagicMock()
    ent._attr_available = True  # LWT online
    return ent


class TestSetupAndManifest:
    """Platform setup and manifest validation."""

    @pytest.mark.asyncio
    async def test_setup_adds_one_entity(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """One firmware entity per config entry."""
        added: list = []
        await async_setup_entry(mock_hass, mock_config_entry, added.extend)
        assert len(added) == 1
        assert isinstance(added[0], NeoPoolFirmwareUpdate)
        assert added[0].unique_id.endswith("_tasmota_firmware")

    @pytest.mark.parametrize(
        "data",
        [
            None,
            [],
            "x",
            {"builds": {}},
            {"tasmota_version": 16, "builds": {}},
            {"tasmota_version": "1"},
        ],
    )
    def test_parse_manifest_rejects_bad_shapes(self, data: Any) -> None:
        """Anything without a string version and a builds dict is ignored."""
        assert _parse_manifest(data) is None

    def test_parse_manifest_accepts_valid(self) -> None:
        """A well-formed manifest passes through unchanged."""
        manifest = _manifest()
        assert _parse_manifest(manifest) is manifest


class TestVersionsAndHold:
    """installed/latest version, the publishing hold, availability."""

    def test_versions_without_manifest(self, mock_config_entry: MagicMock) -> None:
        """Before the first manifest fetch: no latest version, entity unavailable."""
        ent = _entity(mock_config_entry)
        assert ent.installed_version == "15.6.0"
        assert ent.latest_version is None
        assert ent.release_url is None
        assert ent.release_summary is None
        assert ent.available is False

    def test_latest_after_hold(self, mock_config_entry: MagicMock) -> None:
        """Once available_from has passed, the manifest version is offered."""
        ent = _entity(mock_config_entry)
        ent._manifest = _manifest(available_from=_iso(timedelta(hours=-1)))
        assert ent.latest_version == "16.0.0"
        assert ent.release_url.endswith("/v16.0.0")
        assert ent.available is True

    def test_hold_reports_installed_as_latest(self, mock_config_entry: MagicMock) -> None:
        """During the hold the installed version is reported as latest (nothing offered)."""
        ent = _entity(mock_config_entry)
        ent._manifest = _manifest(available_from=_iso(timedelta(hours=12)))
        assert ent._held is True
        assert ent.latest_version == "15.6.0"

    @pytest.mark.parametrize("available_from", [None, 123, "not a date"])
    def test_missing_or_bad_hold_means_no_hold(
        self, mock_config_entry: MagicMock, available_from: Any
    ) -> None:
        """A manifest without a usable available_from is offered immediately."""
        ent = _entity(mock_config_entry)
        manifest = _manifest()
        if available_from is not None:
            manifest["available_from"] = available_from
        ent._manifest = manifest
        assert ent._held is False
        assert ent.latest_version == "16.0.0"

    def test_unavailable_when_offline_or_version_unknown(
        self, mock_config_entry: MagicMock
    ) -> None:
        """Availability needs LWT online and an installed version."""
        ent = _entity(mock_config_entry)
        ent._manifest = _manifest()
        ent._attr_available = False
        assert ent.available is False
        ent._attr_available = True
        mock_config_entry.runtime_data.tasmota_version = None
        assert ent.available is False

    def test_non_string_release_url(self, mock_config_entry: MagicMock) -> None:
        """A malformed release_url is not passed on."""
        ent = _entity(mock_config_entry)
        ent._manifest = _manifest(release_url=42)
        assert ent.release_url is None


class TestInstallability:
    """Which devices get the Install button."""

    @pytest.mark.parametrize(
        ("image", "installable"),
        [
            ("tasmota32-neopool", True),
            ("tasmota32s3-neopool", True),
            ("tasmota32c3-neopool", True),
            ("tasmota-neopool", False),  # ESP8266: never from HA
            ("tasmota32", False),  # someone's own build
            ("bluetooth", False),
            (None, False),
        ],
    )
    def test_supported_features(
        self, mock_config_entry: MagicMock, image: str | None, installable: bool
    ) -> None:
        """INSTALL only for the ESP32-family NeoPool builds."""
        ent = _entity(mock_config_entry, image=image)
        expected = UpdateEntityFeature.INSTALL if installable else UpdateEntityFeature(0)
        assert ent.supported_features == expected

    def test_release_summary_per_device_kind(self, mock_config_entry: MagicMock) -> None:
        """The summary explains Install, or why the upgrade must be done by hand."""
        ent = _entity(mock_config_entry)
        ent._manifest = _manifest()
        assert "Settings are kept" in ent.release_summary

        mock_config_entry.runtime_data.tasmota_image = "tasmota-neopool"
        assert "ESP8266" in ent.release_summary

        mock_config_entry.runtime_data.tasmota_image = "tasmota32"
        assert "'tasmota32' build" in ent.release_summary

        mock_config_entry.runtime_data.tasmota_image = None
        assert "'unknown' build" in ent.release_summary
        assert len(ent.release_summary) <= 255


class TestManifestFetch:
    """async_update fetches firmware/manifest.json."""

    @pytest.mark.asyncio
    async def test_fetch_success(
        self, hass: HomeAssistant, mock_config_entry: MagicMock, aioclient_mock: Any
    ) -> None:
        """A good manifest is stored."""
        aioclient_mock.get(FIRMWARE_MANIFEST_URL, json=_manifest())
        ent = _entity(mock_config_entry)
        ent.hass = hass
        await ent.async_update()
        assert ent._manifest is not None
        assert ent._manifest["tasmota_version"] == "16.0.0"

    @pytest.mark.asyncio
    async def test_fetch_text_plain(
        self, hass: HomeAssistant, mock_config_entry: MagicMock, aioclient_mock: Any
    ) -> None:
        """raw.githubusercontent.com serves JSON as text/plain; it is still parsed."""
        aioclient_mock.get(
            FIRMWARE_MANIFEST_URL,
            text='{"tasmota_version": "16.0.0", "builds": {}}',
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        ent = _entity(mock_config_entry)
        ent.hass = hass
        await ent.async_update()
        assert ent._manifest == {"tasmota_version": "16.0.0", "builds": {}}

    @pytest.mark.asyncio
    async def test_fetch_errors_keep_last_manifest(
        self, hass: HomeAssistant, mock_config_entry: MagicMock, aioclient_mock: Any
    ) -> None:
        """HTTP errors, bad JSON and bad shapes keep the previous manifest and retry once soon."""
        ent = _entity(mock_config_entry)
        ent.hass = hass
        previous = _manifest()
        ent._manifest = previous

        with patch(f"{_UPDATE}.async_call_later", return_value=MagicMock()) as later:
            aioclient_mock.get(FIRMWARE_MANIFEST_URL, status=500)
            await ent.async_update()
            assert ent._manifest is previous

            aioclient_mock.clear_requests()
            aioclient_mock.get(FIRMWARE_MANIFEST_URL, text="not json")
            await ent.async_update()
            assert ent._manifest is previous

            aioclient_mock.clear_requests()
            aioclient_mock.get(FIRMWARE_MANIFEST_URL, json={"unexpected": True})
            await ent.async_update()
            assert ent._manifest is previous

        # One retry pending at a time, however many fetches fail
        later.assert_called_once()
        assert later.call_args.args[1] == FIRMWARE_RETRY_SECONDS
        assert ent._cancel_retry is later.return_value

    @pytest.mark.asyncio
    async def test_fetch_success_cancels_pending_retry(
        self, hass: HomeAssistant, mock_config_entry: MagicMock, aioclient_mock: Any
    ) -> None:
        """A good fetch drops a retry scheduled by an earlier failure."""
        aioclient_mock.get(FIRMWARE_MANIFEST_URL, json=_manifest())
        ent = _entity(mock_config_entry)
        ent.hass = hass
        cancel = MagicMock()
        ent._cancel_retry = cancel
        await ent.async_update()
        cancel.assert_called_once()
        assert ent._cancel_retry is None

    def test_retry_refetches(self, mock_config_entry: MagicMock) -> None:
        """When the retry fires it clears itself and forces a manifest fetch."""
        ent = _entity(mock_config_entry)
        ent.async_schedule_update_ha_state = MagicMock()
        ent._cancel_retry = MagicMock()
        ent._async_retry_fetch(None)
        assert ent._cancel_retry is None
        ent.async_schedule_update_ha_state.assert_called_once_with(force_refresh=True)

    def test_cancel_retry_without_pending_is_noop(self, mock_config_entry: MagicMock) -> None:
        """Removing the entity with no retry pending does nothing."""
        ent = _entity(mock_config_entry)
        ent._async_cancel_retry()
        assert ent._cancel_retry is None

    @pytest.mark.asyncio
    async def test_added_to_hass_subscribes_and_fetches(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """Adding the entity subscribes to metadata updates and schedules a manifest fetch."""
        ent = _entity(mock_config_entry)
        ent.hass = mock_hass
        ent.async_schedule_update_ha_state = MagicMock()
        with (
            patch("homeassistant.components.mqtt.async_subscribe", return_value=MagicMock()),
            patch(f"{_UPDATE}.async_dispatcher_connect", return_value=MagicMock()) as connect,
        ):
            await ent.async_added_to_hass()
        connect.assert_called_once()
        ent.async_schedule_update_ha_state.assert_called_once_with(force_refresh=True)


class TestInstall:
    """async_install: OtaUrl + Upgrade 1, then wait for the new version."""

    @pytest.mark.asyncio
    async def test_install_success(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """The OTA URL points at the device's build; completes when 16.0.0 reports in."""
        ent = _entity(mock_config_entry, image="tasmota32s3-neopool")
        ent.hass = mock_hass
        ent._manifest = _manifest()
        mock_config_entry.runtime_data.available = True

        with patch.object(ent, "_publish_command", new_callable=AsyncMock) as pub:
            task = asyncio.create_task(ent.async_install(None, False))
            await asyncio.sleep(0)
            assert ent.in_progress is True
            # Not yet: an unrelated metadata refresh still reports the old version
            ent._handle_metadata_update()
            await asyncio.sleep(0)
            assert not task.done()
            # The device came back on the new firmware
            mock_config_entry.runtime_data.tasmota_version = "16.0.0"
            ent._handle_metadata_update()
            await task

        assert [c.args for c in pub.await_args_list] == [
            (CMD_OTAURL, f"{FIRMWARE_BASE_URL}NeoPool_ESP32S3_tasmota32s3.bin"),
            (CMD_UPGRADE, "1"),
        ]
        assert all(c.kwargs == {"qos": 1} for c in pub.await_args_list)
        assert ent.in_progress is False

    @pytest.mark.asyncio
    async def test_install_timeout(
        self, mock_hass: MagicMock, mock_config_entry: MagicMock
    ) -> None:
        """No new version in time -> translated error, in_progress cleared."""
        ent = _entity(mock_config_entry)
        ent.hass = mock_hass
        ent._manifest = _manifest()
        mock_config_entry.runtime_data.available = True
        with (
            patch.object(ent, "_publish_command", new_callable=AsyncMock),
            patch(f"{_UPDATE}.FIRMWARE_INSTALL_TIMEOUT_SECONDS", 0.05),
            pytest.raises(HomeAssistantError) as err,
        ):
            await ent.async_install(None, False)
        assert err.value.translation_key == "firmware_install_timeout"
        assert err.value.translation_placeholders["version"] == "16.0.0"
        assert ent.in_progress is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("image", "manifest", "online", "key"),
        [
            ("tasmota-neopool", _manifest(), True, "firmware_not_installable"),
            ("tasmota32", _manifest(), True, "firmware_not_installable"),
            ("tasmota32-neopool", None, True, "firmware_manifest_unavailable"),
            ("tasmota32-neopool", _manifest(builds={}), True, "firmware_manifest_unavailable"),
            (
                "tasmota32-neopool",
                _manifest(builds={"esp32": "bad"}),
                True,
                "firmware_manifest_unavailable",
            ),
            ("tasmota32-neopool", _manifest(), False, "firmware_device_offline"),
        ],
    )
    async def test_install_refused(
        self,
        mock_hass: MagicMock,
        mock_config_entry: MagicMock,
        image: str,
        manifest: dict | None,
        online: bool,
        key: str,
    ) -> None:
        """Refusals raise a translated error and never send a command."""
        ent = _entity(mock_config_entry, image=image)
        ent.hass = mock_hass
        ent._manifest = manifest
        mock_config_entry.runtime_data.available = online
        with (
            patch.object(ent, "_publish_command", new_callable=AsyncMock) as pub,
            pytest.raises(HomeAssistantError) as err,
        ):
            await ent.async_install(None, False)
        assert err.value.translation_key == key
        pub.assert_not_awaited()
        assert ent.in_progress is False

    def test_metadata_update_outside_install_just_writes(
        self, mock_config_entry: MagicMock
    ) -> None:
        """A metadata refresh without a pending install only re-renders the entity."""
        ent = _entity(mock_config_entry)
        ent._handle_metadata_update()
        ent.async_write_ha_state.assert_called_once()
