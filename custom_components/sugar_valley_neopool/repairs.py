"""Repair issues for Sugar Valley NeoPool integration.

https://github.com/alexdelprete/ha-sugar-valley-neopool
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Issue IDs
ISSUE_DEVICE_OFFLINE = "device_offline"

# Notification IDs
NOTIFICATION_RECOVERY = "recovery"


def create_device_offline_issue(
    hass: HomeAssistant,
    entry_id: str,
    device_name: str,
    mqtt_topic: str,
    offline_since: str,
    offline_duration: str,
) -> None:
    """Create a repair issue for device offline.

    Args:
        hass: HomeAssistant instance
        entry_id: Config entry ID
        device_name: Name of the device
        mqtt_topic: MQTT topic of the device
        offline_since: Timestamp when device went offline (locale-aware format)
        offline_duration: Duration device has been offline (compact format)

    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_DEVICE_OFFLINE}_{entry_id}",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_DEVICE_OFFLINE,
        translation_placeholders={
            "device_name": device_name,
            "mqtt_topic": mqtt_topic,
            "offline_since": offline_since,
            "offline_duration": offline_duration,
        },
    )
    _LOGGER.debug("Created repair issue for device offline: %s", device_name)


def delete_device_offline_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the device offline repair issue.

    Args:
        hass: HomeAssistant instance
        entry_id: Config entry ID

    """
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_DEVICE_OFFLINE}_{entry_id}")
    _LOGGER.debug("Deleted repair issue for entry: %s", entry_id)


def create_recovery_notification(
    hass: HomeAssistant,
    entry_id: str,
    device_name: str,
    started_at: str,
    ended_at: str,
    downtime: str,
    script_name: str | None = None,
    script_executed_at: str | None = None,
) -> None:
    """Create a persistent notification for device recovery.

    Uses persistent_notification service instead of repair issues to ensure
    the full message with timestamps is displayed properly when clicked.

    Args:
        hass: HomeAssistant instance
        entry_id: Config entry ID
        device_name: Name of the device
        started_at: Time when failure started (locale-aware format)
        ended_at: Time when device recovered (locale-aware format)
        downtime: Total downtime in compact format (e.g., "5m 23s")
        script_name: Name of the recovery script (if executed)
        script_executed_at: Time when script was executed (if executed)

    """
    # Build the notification message
    message_lines = [
        f"**{device_name}** is now responding again.",
        "",
        f"**Failure started:** {started_at}",
    ]

    if script_name and script_executed_at:
        message_lines.append(f"**Script executed:** {script_executed_at}")
        message_lines.append(f"**Recovery script:** {script_name}")

    message_lines.extend(
        [
            f"**Recovery time:** {ended_at}",
            f"**Total downtime:** {downtime}",
        ]
    )

    message = "\n".join(message_lines)
    title = f"{device_name} has recovered"
    notification_id = f"{DOMAIN}_{NOTIFICATION_RECOVERY}_{entry_id}"

    # Use persistent_notification service for immediate display
    hass.async_create_task(
        hass.services.async_call(
            domain="persistent_notification",
            service="create",
            service_data={
                "title": title,
                "message": message,
                "notification_id": notification_id,
            },
        )
    )

    _LOGGER.debug(
        "Created recovery notification for %s (started: %s, ended: %s, downtime: %s, script: %s)",
        device_name,
        started_at,
        ended_at,
        downtime,
        script_name,
    )
